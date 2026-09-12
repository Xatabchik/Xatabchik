"""Досрочный сброс основного пула трафика и оплата сброса.
"""

import uuid
from yookassa import (
    Payment,
    Configuration,
)
from datetime import datetime
from decimal import Decimal
from aiogram import (
    Router,
    F,
    Bot,
    types,
)
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    deduct_from_balance,
    get_setting,
    create_payload_pending,
    get_balance,
    get_plan_by_id,
    deduct_from_referral_balance,
)
from shop_bot.data_manager import remnawave_repository as rw_repo

__all__: list[str] = []


def register_main_reset(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    def _resolve_key_for_main_reset(key_id: int, user_id: int) -> dict | None:
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            return None
        return key_data

    @user_router.callback_query(F.data.startswith("main_reset_start_"))
    @registration_required
    async def main_reset_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data = _resolve_key_for_main_reset(key_id, user_id)
        if not key_data:
            await callback.message.edit_text("❌ Ключ не найден.", reply_markup=keyboards.create_back_to_menu_keyboard())
            return

        plan = None
        try:
            plan_id_for_key = _resolve_plan_id_for_key(key_data)
            if plan_id_for_key:
                plan = get_plan_by_id(plan_id_for_key)
        except Exception:
            plan = None

        plan_traffic_limit = int((plan or {}).get('traffic_limit_bytes') or 0)
        if not plan or plan_traffic_limit <= 0:
            await callback.message.edit_text(
                "❌ Для тарифа этого ключа сброс основного трафика недоступен (тариф безлимитный).",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        try:
            price = float(plan.get('main_reset_price_rub') or 0)
        except Exception:
            price = 0.0
        if price <= 0:
            await callback.message.edit_text(
                "❌ Платный сброс основного трафика не настроен для этого тарифа. Обратитесь к администратору.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        # Дата ближайшего бесплатного (планового) сброса основного трафика по тарифу
        next_free_reset_txt = "—"
        next_reset_raw = key_data.get('next_traffic_reset_at')
        if next_reset_raw:
            try:
                next_reset_dt = datetime.fromisoformat(str(next_reset_raw).replace(' ', 'T'))
                next_free_reset_txt = next_reset_dt.strftime('%d.%m.%Y')
            except Exception:
                pass

        await state.update_data(main_reset_key_id=key_id, main_reset_price=price)
        try:
            main_balance = get_balance(user_id)
        except Exception:
            main_balance = 0.0

        await callback.message.edit_text(
            "♻️ Сбросить лимит обычного трафика\n\n"
            f"Стоимость: {price:.0f} RUB.\n\n"
            "После оплаты счётчик обычного трафика обнулится моментально, а лимит и история "
            "Мобильного LTE останутся прежними.\n\n"
            f"Следующий бесплатный сброс по тарифу: {next_free_reset_txt}.\n\n"
            f"Ваш баланс: {main_balance:.0f} RUB\n\n"
            "Выберите способ оплаты:",
            reply_markup=keyboards.create_main_reset_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(MainPoolReset.waiting_for_method)

    def _main_reset_metadata(data: dict, user_id: int, payment_method: str, payment_id: str) -> dict:
        price = float(data.get('main_reset_price', 0))
        return {
            "user_id": int(user_id),
            "price": price,
            "action": "main_traffic_reset",
            "key_id": data.get('main_reset_key_id'),
            "payment_method": payment_method,
            "payment_id": payment_id,
        }

    @user_router.callback_query(MainPoolReset.waiting_for_method, F.data == "mainreset_pay_balance")
    async def mainreset_pay_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('main_reset_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена.")
            await state.clear()
            return
        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на балансе.", show_alert=True)
            return
        payment_id = f"balance:{user_id}:{uuid.uuid4()}"
        metadata = _main_reset_metadata(data, user_id, "Balance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(MainPoolReset.waiting_for_method, F.data == "mainreset_pay_referral_balance")
    async def mainreset_pay_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('main_reset_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена.")
            await state.clear()
            return
        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return
        payment_id = f"referral_balance:{user_id}:{uuid.uuid4()}"
        metadata = _main_reset_metadata(data, user_id, "ReferralBalance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(MainPoolReset.waiting_for_method, F.data == "mainreset_pay_yookassa")
    async def mainreset_pay_yookassa_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key

        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('main_reset_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена.")
            await state.clear()
            return
        description = "Досрочный сброс основного пула трафика"
        payment_id = str(uuid.uuid4())
        price_str = f"{price:.2f}"
        metadata = _main_reset_metadata(data, user_id, "YooKassa", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.warning(f"YooKassa main-reset: не удалось создать pending: {e}")
        try:
            payment_payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": payment_id}
            }
            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, user_id, float(price), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa main-reset: не удалось сохранить provider id: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa main-reset payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()
