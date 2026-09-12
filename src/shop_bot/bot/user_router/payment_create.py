"""Создание платежа выбранным способом для покупки ключа.
"""

import uuid
import qrcode
import aiohttp
from io import BytesIO
from yookassa import (
    Payment,
    Configuration,
)
from datetime import datetime
from decimal import (
    Decimal,
    ROUND_HALF_UP,
)
from aiogram import (
    Router,
    F,
    Bot,
    types,
)
from aiogram.types import BufferedInputFile
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    deduct_from_balance,
    get_setting,
    get_user,
    create_payload_pending,
    get_pending_metadata,
    find_and_complete_pending_transaction,
    get_plan_by_id,
    PromoUnavailableError,
    deduct_from_referral_balance,
)

__all__: list[str] = []


def register_payment_create(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_yookassa")
    async def create_yookassa_payment_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        
        # Ensure YooKassa configuration is set
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
            
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key
        
        data = await state.get_data()
        user_data = get_user(callback.from_user.id)
        
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        price_rub = base_price

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                base_price -= discount_amount
        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            discount_amount = promo_discount
            base_price = (base_price - discount_amount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')
        price_rub = base_price

        plan_id = data.get('plan_id')
        customer_email = data.get('customer_email')
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        
        if not customer_email:
            customer_email = get_setting("receipt_email")

        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)
        user_id = callback.from_user.id

        try:
            price_str_for_api = f"{price_rub:.2f}"
            price_float_for_metadata = float(price_rub)

            receipt = None
            if customer_email and is_valid_email(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": f"Подписка на {duration_label}",
                        "quantity": "1.00",
                        "amount": {"value": price_str_for_api, "currency": "RUB"},
                        "vat_code": "1",
                        "payment_subject": "service",
                        "payment_mode": "full_payment"
                    }]
                }
            payment_id = str(uuid.uuid4())
            metadata = {
                "user_id": int(user_id),
                "months": int(months),
                "duration_days": int(duration_days),
                "price": float(price_float_for_metadata),
                "action": action,
                "key_id": key_id,
                "host_name": host_name,
                "plan_id": plan_id,
                "customer_email": customer_email,
                "payment_method": "YooKassa",
                "promo_code": promo_code,
                "promo_discount": float(data.get("promo_discount", 0)),
                "payment_id": payment_id,
            }
            try:
                create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata)
            except PromoUnavailableError:
                await callback.message.answer("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
                return
            except Exception as e:
                logger.warning(f"YooKassa: не удалось создать pending для {payment_id}: {e}")

            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": f"Подписка на {duration_label}",
                "metadata": {"payment_id": payment_id}
            }
            if receipt:
                payment_payload['receipt'] = receipt

            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa: не удалось сохранить provider id для {payment_id}: {e}")
            
            await state.clear()
            
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_platega")
    async def pay_platega_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega не настроен. Обратитесь к администратору.")
            await state.clear()
            return

        data = await state.get_data()
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        # финальная цена (учитывает рефералку/промокод)
        base_price = Decimal(str(plan['price']))
        user_data = get_user(callback.from_user.id) or {}
        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            try:
                discount_percentage = Decimal(str(get_setting("referral_discount") or "0"))
            except Exception:
                discount_percentage = Decimal('0')
            if discount_percentage > 0:
                base_price -= (base_price * discount_percentage / 100).quantize(Decimal("0.01"))

        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            base_price = (base_price - promo_discount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')

        payment_id = str(uuid.uuid4())

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        customer_email = data.get('customer_email') or get_setting("receipt_email")

        metadata = {
            "user_id": callback.from_user.id,
            "months": months,
            "duration_days": duration_days,
            "price": float(base_price),
            "action": action,
            "key_id": key_id,
            "host_name": host_name,
            "plan_id": plan_id,
            "customer_email": customer_email,
            "payment_method": "Platega",
            "payment_id": payment_id,
            "promo_code": promo_code,
            "promo_discount": float(data.get('promo_discount', 0)),
        }

        # сохраняем pending
        try:
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata)
        except PromoUnavailableError:
            await callback.message.edit_text("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
            await state.clear()
            return

        desc = f"Подписка на {months} мес." if months else "Оплата подписки"
        pay_url, txid = await _create_platega_payment_link(amount_rub=base_price, payment_id=payment_id, description=desc)
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        # обновляем pending с id транзакции (для ручной проверки)
        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_rollypay")
    async def pay_rollypay_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП не настроена. Обратитесь к администратору.")
            await state.clear()
            return

        data = await state.get_data()
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        user_data = get_user(callback.from_user.id) or {}
        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            try:
                discount_percentage = Decimal(str(get_setting("referral_discount") or "0"))
            except Exception:
                discount_percentage = Decimal('0')
            if discount_percentage > 0:
                base_price -= (base_price * discount_percentage / 100).quantize(Decimal("0.01"))

        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            base_price = (base_price - promo_discount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')

        payment_id = str(uuid.uuid4())

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        customer_email = data.get('customer_email') or get_setting("receipt_email")

        metadata = {
            "user_id": callback.from_user.id,
            "months": months,
            "duration_days": duration_days,
            "price": float(base_price),
            "action": action,
            "key_id": key_id,
            "host_name": host_name,
            "plan_id": plan_id,
            "customer_email": customer_email,
            "payment_method": "RollyPay",
            "payment_id": payment_id,
            "promo_code": promo_code,
            "promo_discount": float(data.get('promo_discount', 0)),
        }

        try:
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata)
        except PromoUnavailableError:
            await callback.message.edit_text("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
            await state.clear()
            return

        desc = f"Подписка на {months} мес." if months else "Оплата подписки"
        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=base_price, payment_id=payment_id, description=desc,
            customer_id=str(callback.from_user.id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_cryptobot")
    async def create_cryptobot_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счет в Crypto Pay...")
        
        data = await state.get_data()
        user_data = get_user(callback.from_user.id)
        
        plan_id = data.get('plan_id')
        user_id = data.get('user_id', callback.from_user.id)
        customer_email = data.get('customer_email')
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')

        cryptobot_token = get_setting('cryptobot_token')
        if not cryptobot_token:
            logger.error(f"Attempt to create Crypto Pay invoice failed for user {user_id}: cryptobot_token is not set.")
            await callback.message.edit_text("❌ Оплата криптовалютой временно недоступна. (Администратор не указал токен).")
            await state.clear()
            return

        plan = get_plan_by_id(plan_id)
        if not plan:
            logger.error(f"Attempt to create Crypto Pay invoice failed for user {user_id}: Plan with id {plan_id} not found.")
            await callback.message.edit_text("❌ Произошла ошибка при выборе тарифа.")
            await state.clear()
            return
        
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        price_rub_decimal = base_price

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                base_price -= discount_amount
        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            discount_amount = promo_discount
            base_price = (base_price - discount_amount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')
        price_rub_decimal = base_price
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)
        
        final_price_float = float(price_rub_decimal)

        result = await _create_cryptobot_invoice(
            user_id=callback.from_user.id,
            price_rub=final_price_float,
            months=plan['months'],
            host_name=data.get('host_name'),
            state_data=data
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

    @user_router.callback_query(F.data.startswith("check_crypto_invoice:"))
    async def check_crypto_invoice_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer("Проверяю статус оплаты...")
        try:
            parts = (callback.data or "").split(":", 1)
            invoice_id_str = parts[1] if len(parts) > 1 else ""
            invoice_id = int(invoice_id_str)
        except Exception:
            await callback.message.answer("❌ Некорректный идентификатор инвойса.")
            return

        token = (get_setting("cryptobot_token") or "").strip()
        if not token:
            await callback.message.answer("❌ CryptoBot токен не задан.")
            return

        url = "https://pay.crypt.bot/api/getInvoices"
        headers = {
            "Crypto-Pay-API-Token": token,
            "Content-Type": "application/json",
        }
        body = {"invoice_ids": [invoice_id]}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body, timeout=20) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"CryptoBot getInvoices HTTP {resp.status}: {text}")
                        await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")
                        return
                    data = await resp.json(content_type=None)
        except Exception as e:
            logger.error(f"CryptoBot getInvoices failed: {e}", exc_info=True)
            await callback.message.answer("⏳ Не удалось проверить статус. Попробуйте позже.")
            return


        invoices = []
        if isinstance(data, dict) and data.get("ok"):
            res = data.get("result")
            if isinstance(res, dict) and isinstance(res.get("items"), list):
                invoices = res.get("items")
            elif isinstance(res, list):
                invoices = res

        if not invoices:
            await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")
            return

        inv = invoices[0]
        status = (inv.get("status") or inv.get("invoice_status") or "").lower()
        if status != "paid":
            await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")
            return

        payload_string = (inv.get("payload") or "").strip()
        if not payload_string:
            await callback.message.answer("⚠️ Оплата получена, но отсутствует payload. Обратитесь в поддержку.")
            return

        # New format: payload == our internal payment_id
        if ':' not in payload_string:
            internal_payment_id = payload_string
            pending = get_pending_metadata(internal_payment_id)
            if not pending:
                await callback.message.answer("✅ Платёж уже обработан или не найден.")
                return
            # Amount check (fiat RUB invoices)
            try:
                inv_amount = Decimal(str(inv.get("amount") or inv.get("fiat_amount") or inv.get("paid_amount") or '0')).quantize(Decimal('0.01'))
                exp_amount = Decimal(str(pending.get('price') or '0')).quantize(Decimal('0.01'))
                if exp_amount > 0 and inv_amount != exp_amount:
                    await callback.message.answer("⚠️ Сумма оплаты не совпала с ожидаемой. Обратитесь в поддержку.")
                    return
            except Exception:
                pass

            metadata = find_and_complete_pending_transaction(internal_payment_id)
            if not metadata:
                await callback.message.answer("✅ Платёж уже обработан.")
                return

            try:
                await process_successful_payment(bot, metadata)
                await callback.message.answer("✅ Оплата получена! Профиль/баланс скоро обновится.")
            except Exception as e:
                logger.error(f"CryptoBot manual check: process_successful_payment failed: {e}", exc_info=True)
                await callback.message.answer("⚠️ Оплата получена, но обработка не завершена. Обратитесь в поддержку.")
            return

        # Legacy format: payload was a colon-separated metadata string
        p = payload_string.split(":")
        if len(p) < 9:
            await callback.message.answer("⚠️ Оплата получена, но формат данных некорректен. Обратитесь в поддержку.")
            return

        # Amount check for legacy payload
        try:
            inv_amount = Decimal(str(inv.get("amount") or inv.get("fiat_amount") or inv.get("paid_amount") or '0')).quantize(Decimal('0.01'))
            exp_amount = Decimal(str(p[2] or '0')).quantize(Decimal('0.01'))
            if exp_amount > 0 and inv_amount != exp_amount:
                await callback.message.answer("⚠️ Сумма оплаты не совпала с ожидаемой. Обратитесь в поддержку.")
                return
        except Exception:
            pass

        metadata = {
            "user_id": p[0],
            "months": p[1],
            "price": p[2],
            "action": p[3],
            "key_id": p[4],
            "host_name": p[5],
            "plan_id": p[6],
            "customer_email": (p[7] if p[7] != 'None' else None),
            "payment_method": p[8] or 'CryptoBot',
            "transaction_id": str(invoice_id),
            "payment_id": f'cryptobot:{invoice_id}',
        }

        try:
            await process_successful_payment(bot, metadata)
            await callback.message.answer("✅ Оплата получена! Профиль/баланс скоро обновится.")
        except Exception as e:
            logger.error(f"CryptoBot manual check: process_successful_payment failed: {e}", exc_info=True)
            await callback.message.answer("⚠️ Оплата получена, но обработка не завершена. Обратитесь в поддержку.")
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_tonconnect")
    async def create_ton_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"User {callback.from_user.id}: Entered create_ton_invoice_handler.")
        data = await state.get_data()
        user_id = callback.from_user.id
        wallet_address = get_setting("ton_wallet_address")
        plan = get_plan_by_id(data.get('plan_id'))
        
        if not wallet_address or not plan:
            await callback.message.edit_text("❌ Оплата через TON временно недоступна.")
            await state.clear()
            return

        await callback.answer("Создаю ссылку и QR-код для TON Connect...")
            
        price_rub = Decimal(str(data.get('final_price', plan['price'])))

        usdt_rub_rate = await get_usdt_rub_rate()
        ton_usdt_rate = await get_ton_usdt_rate()

        if not usdt_rub_rate or not ton_usdt_rate:
            await callback.message.edit_text("❌ Не удалось получить курс TON. Попробуйте позже.")
            await state.clear()
            return

        price_ton = (price_rub / usdt_rub_rate / ton_usdt_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        amount_nanoton = int(price_ton * 1_000_000_000)
        
        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id, "months": int(plan.get('months') or 0), "duration_days": int(plan.get('duration_days') or 0), "price": float(price_rub),
            "action": data.get('action'), "key_id": data.get('key_id'),
            "host_name": data.get('host_name'), "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'), "payment_method": "TON Connect",
            "expected_amount_ton": float(price_ton)
        }
        create_pending_transaction(payment_id, user_id, float(price_rub), metadata)

        transaction_payload = {
            'messages': [{'address': wallet_address, 'amount': str(amount_nanoton), 'payload': payment_id}],
            'valid_until': int(datetime.now().timestamp()) + 600
        }

        try:
            connect_url = await _start_ton_connect_process(user_id, transaction_payload)
            
            qr_img = qrcode.make(connect_url)
            bio = BytesIO()
            qr_img.save(bio, "PNG")
            qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")

            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr_file,
                caption=(
                    f"💎 **Оплата через TON Connect**\n\n"
                    f"Сумма к оплате: `{price_ton}` **TON**\n\n"
                    f"✅ **Способ 1 (на телефоне):** Нажмите кнопку **'Открыть кошелек'** ниже.\n"
                    f"✅ **Способ 2 (на компьютере):** Отсканируйте QR-код кошельком.\n\n"
                    f"После подключения кошелька подтвердите транзакцию."
                ),
                parse_mode="Markdown",
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Failed to generate TON Connect link for user {user_id}: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось создать ссылку для TON Connect. Попробуйте позже.")
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_balance")
    async def pay_with_main_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        price = float(data.get('final_price', plan['price']))


        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на основном балансе.", show_alert=True)
            return

        promo_code = (data.get('promo_code') or '').strip() if isinstance(data, dict) else ''
        promo_discount = float(data.get('promo_discount') or 0) if promo_code else 0.0

        metadata = {
            "user_id": user_id,
            "months": months,
            "duration_days": duration_days,
            "price": price,
            "action": data.get('action'),
            "key_id": data.get('key_id'),
            "host_name": data.get('host_name'),
            "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'),
            "payment_method": "Balance",
            "chat_id": callback.message.chat.id,
            "message_id": callback.message.message_id,
            "promo_code": promo_code,
            "promo_discount": promo_discount,
        }
        # Для оплаты с внутреннего баланса у нас нет внешнего идентификатора платежа.
        # Генерируем уникальный payment_id, чтобы process_successful_payment смог
        # корректно отработать и пройти идемпотентную проверку.
        metadata.setdefault("payment_id", f"balance:{user_id}:{uuid.uuid4()}")

        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_referral_balance")
    async def pay_with_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        price = float(data.get('final_price', plan['price']))

        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return

        promo_code = (data.get('promo_code') or '').strip() if isinstance(data, dict) else ''
        promo_discount = float(data.get('promo_discount') or 0) if promo_code else 0.0

        metadata = {
            "user_id": user_id,
            "months": months,
            "duration_days": duration_days,
            "price": price,
            "action": data.get('action'),
            "key_id": data.get('key_id'),
            "host_name": data.get('host_name'),
            "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'),
            "payment_method": "ReferralBalance",
            "chat_id": callback.message.chat.id,
            "message_id": callback.message.message_id,
            "promo_code": promo_code,
            "promo_discount": promo_discount,
        }
        metadata.setdefault("payment_id", f"referral_balance:{user_id}:{uuid.uuid4()}")

        await state.clear()
        await process_successful_payment(bot, metadata)

    _STALE_PAY_CALLBACKS = {
        "pay_balance",
        "pay_referral_balance",
        "pay_stars",
        "pay_yookassa",
        "pay_platega",
        "pay_rollypay",
        "pay_cryptobot",
        "pay_heleket",
        "pay_yoomoney",
        "pay_tonconnect",
    }

    @user_router.callback_query(F.data.in_(_STALE_PAY_CALLBACKS))
    async def stale_payment_method_callback(callback: types.CallbackQuery):
        """Устаревшие pay_* после смены FSM (например, после Stars invoice).

        Регистрируется после штатных обработчиков waiting_for_payment_method,
        чтобы не перехватывать живой сценарий выбора метода.
        """
        await callback.answer(
            "Сессия оплаты устарела. Выберите тариф и способ оплаты заново.",
            show_alert=True,
        )
