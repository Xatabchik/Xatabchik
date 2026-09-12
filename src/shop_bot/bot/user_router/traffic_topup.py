"""Докупка гигабайтов основного трафика и оплата этой докупки.
"""

import uuid
from yookassa import (
    Payment,
    Configuration,
)
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
from aiogram.types import LabeledPrice
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
from shop_bot.data_manager import database

__all__: list[str] = []


def register_traffic_topup(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    def _resolve_plan_for_traffic_topup(key_id: int, user_id: int) -> tuple[dict, dict] | tuple[None, None]:
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            return None, None
        plan_id = _resolve_plan_id_for_key(key_data)
        if not plan_id:
            return None, None
        plan = get_plan_by_id(plan_id)
        if not plan or int(plan.get('traffic_limit_bytes') or 0) <= 0:
            return None, None
        return key_data, plan

    @user_router.callback_query(F.data.startswith("traffic_gb_start_"))
    @registration_required
    async def traffic_gb_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data, plan = _resolve_plan_for_traffic_topup(key_id, user_id)
        if not plan:
            await callback.message.edit_text(
                "❌ Для тарифа этого ключа не настроена докупка трафика.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        packages = database.get_traffic_packages_for_plan(plan['plan_id'], only_active=True)
        if not packages:
            await callback.message.edit_text(
                "❌ Пакеты докупки трафика для этого тарифа пока не настроены. Обратитесь к администратору.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        await state.update_data(traffic_key_id=key_id)
        await callback.message.edit_text(
            "Выберите объём докупаемого трафика:",
            reply_markup=keyboards.create_traffic_packages_keyboard(key_id, packages)
        )

    @user_router.callback_query(F.data.startswith("traffic_gb_pick_"))
    @registration_required
    async def traffic_gb_pick_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            parts = callback.data.split("_")
            package_id = int(parts[-1])
            key_id = int(parts[-2])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data, plan = _resolve_plan_for_traffic_topup(key_id, user_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: тариф ключа не найден.")
            return

        package = database.get_traffic_package_by_id(package_id)
        if not package or int(package.get('plan_id')) != int(plan['plan_id']):
            await callback.answer("Пакет не найден", show_alert=True)
            return

        await state.update_data(
            traffic_key_id=key_id,
            traffic_package_id=package_id,
            traffic_package_price=float(package.get('price') or 0),
            traffic_package_size_gb=float(package.get('size_gb') or 0),
        )

        try:
            main_balance = get_balance(user_id)
        except Exception:
            main_balance = 0.0

        size_gb = float(package.get('size_gb') or 0)
        price = float(package.get('price') or 0)
        size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"

        await callback.message.edit_text(
            f"📶 Докупка {size_txt} ГБ — {price:.0f} RUB\n"
            f"Ваш баланс: {main_balance:.0f} RUB\n\n"
            "Выберите способ оплаты:",
            reply_markup=keyboards.create_traffic_gb_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(TrafficGbTopUp.waiting_for_method)

    def _traffic_gb_metadata(data: dict, user_id: int, payment_method: str, payment_id: str) -> dict:
        price = float(data.get('traffic_package_price', 0))
        return {
            "user_id": int(user_id),
            "price": price,
            "action": "traffic_gb_topup",
            "key_id": data.get('traffic_key_id'),
            "package_id": data.get('traffic_package_id'),
            "size_gb": data.get('traffic_package_size_gb'),
            "payment_method": payment_method,
            "payment_id": payment_id,
        }

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_balance")
    async def trafficgb_pay_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на балансе.", show_alert=True)
            return
        payment_id = f"balance:{user_id}:{uuid.uuid4()}"
        metadata = _traffic_gb_metadata(data, user_id, "Balance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_referral_balance")
    async def trafficgb_pay_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return
        payment_id = f"referral_balance:{user_id}:{uuid.uuid4()}"
        metadata = _traffic_gb_metadata(data, user_id, "ReferralBalance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_yookassa")
    async def trafficgb_pay_yookassa_handler(callback: types.CallbackQuery, state: FSMContext):
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
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('traffic_package_size_gb')
        description = f"Докупка {size_gb} ГБ трафика"
        payment_id = str(uuid.uuid4())
        price_str = f"{price:.2f}"
        metadata = _traffic_gb_metadata(data, user_id, "YooKassa", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.warning(f"YooKassa traffic-gb: не удалось создать pending: {e}")
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
                logger.warning(f"YooKassa traffic-gb: не удалось сохранить provider id: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa traffic-gb payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_platega")
    async def trafficgb_pay_platega_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega временно недоступен.")
            await state.clear()
            return
        data = await state.get_data()
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('traffic_package_size_gb')
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "Platega", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url, txid = await _create_platega_payment_link(amount_rub=price, payment_id=payment_id, description=f"Докупка {size_gb} ГБ трафика")
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже.")
            await state.clear()
            return
        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, user_id, float(price), metadata2)
        except Exception:
            pass
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_rollypay")
    async def trafficgb_pay_rollypay_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП временно недоступна.")
            await state.clear()
            return
        data = await state.get_data()
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('traffic_package_size_gb')
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "RollyPay", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=price, payment_id=payment_id, description=f"Докупка {size_gb} ГБ трафика",
            customer_id=str(user_id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже.")
            await state.clear()
            return
        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, user_id, float(price), metadata2)
        except Exception:
            pass
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_heleket")
    async def trafficgb_pay_heleket_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        state_data = {
            "action": "traffic_gb_topup",
            "customer_email": None,
            "plan_id": None,
            "package_id": data.get('traffic_package_id'),
            "host_name": None,
            "key_id": data.get('traffic_key_id'),
        }
        try:
            pay_url = await _create_heleket_payment_request(
                user_id=user_id,
                price=price,
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
            logger.error(f"Failed to create traffic-gb Heleket invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_cryptobot")
    async def trafficgb_pay_cryptobot_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт в Crypto Pay...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        state_data = {
            "action": "traffic_gb_topup",
            "customer_email": None,
            "plan_id": None,
            "package_id": data.get('traffic_package_id'),
            "host_name": None,
            "key_id": data.get('traffic_key_id'),
        }
        try:
            result = await _create_cryptobot_invoice(
                user_id=user_id,
                price_rub=price,
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
            logger.error(f"Failed to create traffic-gb CryptoBot invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_yoomoney")
    async def trafficgb_pay_yoomoney_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю YooMoney...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('traffic_package_price', 0)))
        wallet = get_setting("yoomoney_wallet")
        secret = get_setting("yoomoney_secret")
        if not wallet or not secret or price <= 0:
            await callback.message.edit_text("❌ YooMoney временно недоступен.")
            await state.clear()
            return
        w = (wallet or "").strip()
        if not (w.isdigit() and len(w) >= 11):
            await callback.message.edit_text("❌ Некорректный номер кошелька YooMoney.")
            await state.clear()
            return
        if price < Decimal("1.00"):
            await callback.message.edit_text("❌ Минимальная сумма перевода YooMoney — 1 RUB.")
            await state.clear()
            return
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "YooMoney", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url = _build_yoomoney_link(wallet, price, payment_id)
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_yoomoney_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_stars")
    async def trafficgb_pay_stars_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        try:
            stars_ratio = Decimal(get_setting("stars_per_rub") or '0')
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return
        stars_amount = int((price * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) or 1
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "Telegram Stars", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.error(f"traffic-gb Stars: не удалось создать pending: {e}", exc_info=True)
        size_gb = data.get('traffic_package_size_gb')
        try:
            await callback.message.answer_invoice(
                title="Докупка трафика",
                description=f"Докупка {size_gb} ГБ трафика",
                prices=[LabeledPrice(label="Докупка трафика", amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to create traffic-gb Stars invoice: {e}")
            await callback.message.edit_text("❌ Не удалось создать счёт в Stars.")
            await state.clear()
