"""Выбор способа пополнения баланса.
"""

import uuid
import qrcode
from io import BytesIO
from datetime import datetime
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.types import BufferedInputFile
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    create_payload_pending,
)

__all__: list[str] = []


def register_topup_methods(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    
    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_platega")
    async def topup_pay_platega(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega временно недоступен.")
            await state.clear()
            return

        data = await state.get_data()
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма.")
            await state.clear()
            return

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "Platega",
            "payment_id": payment_id,
        }
        create_payload_pending(payment_id, user_id, float(amount_rub), metadata)

        pay_url, txid = await _create_platega_payment_link(amount_rub=amount_rub, payment_id=payment_id, description="Пополнение баланса")
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, user_id, float(amount_rub), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_rollypay")
    async def topup_pay_rollypay(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП временно недоступна.")
            await state.clear()
            return

        data = await state.get_data()
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма.")
            await state.clear()
            return

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "RollyPay",
            "payment_id": payment_id,
        }
        create_payload_pending(payment_id, user_id, float(amount_rub), metadata)

        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=amount_rub, payment_id=payment_id, description="Пополнение баланса",
            customer_id=str(user_id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, user_id, float(amount_rub), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_heleket")
    async def topup_pay_heleket_like(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount = float(data.get('topup_amount', 0))
        if amount <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return

        state_data = {
            "action": "top_up",
            "customer_email": None,
            "plan_id": None,
            "host_name": None,
            "key_id": None,
        }
        try:
            pay_url = await _create_heleket_payment_request(
                user_id=user_id,
                price=float(amount),
                months=0,
                host_name="",
                state_data=state_data
            )
            if pay_url:
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_payment_keyboard(pay_url)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create topup Heleket-like invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_cryptobot")
    async def topup_pay_cryptobot(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт в Crypto Pay...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount = float(data.get('topup_amount', 0))
        if amount <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return
        state_data = {
            "action": "top_up",
            "customer_email": None,
            "plan_id": None,
            "host_name": None,
            "key_id": None,
        }
        try:
            result = await _create_cryptobot_invoice(
                user_id=user_id,
                price_rub=float(amount),
                months=0,
                host_name="",
                state_data=state_data,
            )
            if result:
                pay_url, invoice_id = result
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_cryptobot_payment_keyboard(pay_url, invoice_id)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create CryptoBot topup invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_tonconnect")
    async def topup_pay_tonconnect(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю TON Connect...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return

        wallet_address = get_setting("ton_wallet_address")
        if not wallet_address:
            await callback.message.edit_text("❌ Оплата через TON временно недоступна.")
            await state.clear()
            return

        usdt_rub_rate = await get_usdt_rub_rate()
        ton_usdt_rate = await get_ton_usdt_rate()
        if not usdt_rub_rate or not ton_usdt_rate:
            await callback.message.edit_text("❌ Не удалось получить курс TON. Попробуйте позже.")
            await state.clear()
            return

        price_ton = (amount_rub / usdt_rub_rate / ton_usdt_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        amount_nanoton = int(price_ton * 1_000_000_000)

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "TON Connect",
            "expected_amount_ton": float(price_ton)
        }
        create_pending_transaction(payment_id, user_id, float(amount_rub), metadata)

        transaction_payload = {
            'messages': [{'address': wallet_address, 'amount': str(amount_nanoton), 'payload': payment_id}],
            'valid_until': int(datetime.now().timestamp()) + 600
        }

        try:
            connect_url = await _start_ton_connect_process(user_id, transaction_payload)
            qr_img = qrcode.make(connect_url)
            bio = BytesIO(); qr_img.save(bio, "PNG"); qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer_photo(
                photo=qr_file,
                caption=(
                    f"💎 Оплата через TON Connect\n\n"
                    f"Сумма к оплате: `{price_ton}` TON\n\n"
                    f"Нажмите кнопку ниже, чтобы открыть кошелёк и подтвердить перевод."
                ),
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to start TON Connect topup: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось подготовить оплату TON Connect.")
            await state.clear()
