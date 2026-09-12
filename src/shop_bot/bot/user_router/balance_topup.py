"""Пополнение баланса и оплата звёздами Telegram.
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
from aiogram.types import (
    LabeledPrice,
    PreCheckoutQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    create_payload_pending,
    cancel_pending_transaction,
    get_pending_status,
    get_pending_metadata,
    find_and_complete_pending_transaction,
    get_plan_by_id,
)
from shop_bot.data_manager.database import get_latest_pending_for_user

__all__: list[str] = []


def register_balance_topup(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(F.data == "top_up_start")
    @registration_required
    async def topup_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Введите сумму пополнения в рублях (например, 300):\nМинимум: 10 RUB, максимум: 100000 RUB",
            reply_markup=keyboards.create_back_to_menu_keyboard()
        )
        await state.set_state(TopUpProcess.waiting_for_amount)

    @user_router.message(TopUpProcess.waiting_for_amount)
    async def topup_amount_input(message: types.Message, state: FSMContext):
        text = (message.text or "").replace(",", ".").strip()
        try:
            amount = Decimal(text)
        except Exception:
            await message.answer("❌ Введите корректную сумму, например: 300", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        if amount < Decimal("10"):
            await message.answer("❌ Минимальная сумма пополнения: 10 RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        if amount > Decimal("100000"):
            await message.answer("❌ Максимальная сумма пополнения: 100000 RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        final_amount = amount.quantize(Decimal("0.01"))
        await state.update_data(topup_amount=float(final_amount))
        await message.answer(
            f"К пополнению: {final_amount:.2f} RUB\nВыберите способ оплаты:",
            reply_markup=keyboards.create_topup_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(TopUpProcess.waiting_for_topup_method)

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_yookassa")
    async def topup_pay_yookassa(callback: types.CallbackQuery, state: FSMContext):
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
        amount = Decimal(str(data.get('topup_amount', 0)))
        if amount <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return
        user_id = callback.from_user.id
        price_str_for_api = f"{amount:.2f}"
        price_float_for_metadata = float(amount)

        try:

            customer_email = get_setting("receipt_email")
            receipt = None
            if customer_email and is_valid_email(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": f"Пополнение баланса",
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
                "price": float(price_float_for_metadata),
                "action": "top_up",
                "payment_method": "YooKassa",
                "payment_id": payment_id,
            }
            try:
                create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata)
            except Exception as e:
                logger.warning(f"YooKassa topup: не удалось создать pending для {payment_id}: {e}")

            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": f"Пополнение баланса на {price_str_for_api} RUB",
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
                logger.warning(f"YooKassa topup: не удалось сохранить provider id для {payment_id}: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Не удалось создать платеж пополнения YooKassa: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()


    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_stars")
    async def create_stars_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        user_id = callback.from_user.id

        price_rub = Decimal(str(data.get('final_price', plan['price'])))
        try:
            stars_ratio_raw = get_setting("stars_per_rub") or '0'
            stars_ratio = Decimal(stars_ratio_raw)
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return

        stars_amount = int((price_rub * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if stars_amount <= 0:
            stars_amount = 1

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "months": months,
            "duration_days": duration_days,
            "price": float(price_rub),
            "action": data.get('action'),
            "key_id": data.get('key_id'),
            "host_name": data.get('host_name'),
            "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'),
            "payment_method": "Telegram Stars",
            "payment_id": payment_id,
        }
        try:
            ok = create_payload_pending(payment_id, user_id, float(price_rub), metadata)
            logger.info(f"Создано ожидание Stars: ok={ok}, payment_id={payment_id}, user_id={user_id}, price_rub={price_rub}")
        except Exception as e:
            logger.error(f"Не удалось создать ожидание для Stars payment_id={payment_id}: {e}", exc_info=True)
            ok = False
        if not ok:
            await callback.message.answer("❌ Не удалось подготовить оплату Stars. Попробуйте ещё раз.")
            return

        title = f"Подписка на {duration_label}"
        description = f"Оплата VPN на {duration_label}"
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        try:
            invoice_msg = await callback.message.answer_invoice(
                title=title,
                description=description,
                prices=[LabeledPrice(label=title, amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
                reply_markup=keyboards.create_stars_invoice_keyboard(),
            )
            invoice_chat_id = getattr(getattr(invoice_msg, "chat", None), "id", None) or callback.message.chat.id
            invoice_message_id = getattr(invoice_msg, "message_id", None)
            await state.update_data(
                stars_payment_id=payment_id,
                stars_invoice_chat_id=invoice_chat_id,
                stars_invoice_message_id=invoice_message_id,
            )
            await state.set_state(PaymentProcess.waiting_for_stars_invoice)
        except Exception as e:
            logger.error(f"Не удалось создать счет Stars: {e}")
            try:
                cancel_pending_transaction(payment_id, user_id)
            except Exception:
                pass
            try:
                await callback.message.answer("❌ Не удалось создать счёт в Stars. Попробуйте другой способ оплаты.")
            except Exception:
                pass

    @user_router.callback_query(F.data == "payment_stars_back")
    async def payment_stars_back_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        data = await state.get_data()
        pid = str(data.get("stars_payment_id") or "").strip()
        status = (get_pending_status(pid) or "").lower() if pid else ""

        if status == "paid":
            await callback.answer("Оплата уже подтверждена.", show_alert=True)
            return

        if pid and status == "pending":
            meta = get_pending_metadata(pid) or {}
            try:
                owner_id = int(meta.get("user_id") or 0)
            except (TypeError, ValueError):
                owner_id = 0
            if owner_id and owner_id != user_id:
                await callback.answer("Счёт уже недействителен.", show_alert=True)
                return
            cancel_pending_transaction(pid, user_id)

        if not data.get("plan_id"):
            await callback.answer(
                "Сессия оплаты устарела. Выберите тариф и способ оплаты заново.",
                show_alert=True,
            )
            return

        chat_id = data.get("stars_invoice_chat_id") or (
            callback.message.chat.id if callback.message else None
        )
        message_id = data.get("stars_invoice_message_id") or (
            callback.message.message_id if callback.message else None
        )
        if chat_id and message_id:
            try:
                await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
            except TelegramBadRequest:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=int(chat_id), message_id=int(message_id), reply_markup=None
                    )
                except Exception:
                    pass
            except Exception:
                pass

        await state.update_data(
            stars_payment_id=None,
            stars_invoice_chat_id=None,
            stars_invoice_message_id=None,
        )
        await state.set_state(PaymentProcess.waiting_for_payment_method)
        await callback.answer()
        try:
            await show_payment_options(callback.message, state)
        except Exception:
            logger.error("payment_stars_back: failed to restore payment methods", exc_info=True)

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_stars")
    async def topup_stars_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения.")
            await state.clear()
            return
        try:
            stars_ratio_raw = get_setting("stars_per_rub") or '0'
            stars_ratio = Decimal(stars_ratio_raw)
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return
        stars_amount = int((amount_rub * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if stars_amount <= 0:
            stars_amount = 1
        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "Telegram Stars",
            "payment_id": payment_id,
        }
        try:
            ok = create_payload_pending(payment_id, user_id, float(amount_rub), metadata)
            logger.info(f"Создано ожидание пополнения Stars: ok={ok}, payment_id={payment_id}, user_id={user_id}, amount_rub={amount_rub}")
        except Exception as e:
            logger.error(f"Не удалось создать ожидание для пополнения Stars payment_id={payment_id}: {e}", exc_info=True)
        try:
            await callback.message.answer_invoice(
                title="Пополнение баланса",
                description=f"Пополнение на {amount_rub:.2f} RUB",
                prices=[LabeledPrice(label="Пополнение", amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Не удалось создать счет пополнения Stars: {e}")
            await callback.message.edit_text("❌ Не удалось создать счёт в Stars.")
            await state.clear()


    @user_router.pre_checkout_query()
    async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
        payload = ""
        try:
            payload = (pre_checkout_q.invoice_payload or "").strip()
        except Exception:
            payload = ""
        status = (get_pending_status(payload) or "").lower() if payload else ""
        if status in {"cancelled", "canceled", "paid"}:
            try:
                await pre_checkout_q.answer(
                    ok=False,
                    error_message="Этот счёт отменён. Выберите способ оплаты заново.",
                )
            except Exception:
                pass
            return
        try:
            await pre_checkout_q.answer(ok=True)
        except Exception:
            pass


    @user_router.message(F.successful_payment)
    async def stars_success_handler(message: types.Message, bot: Bot, state: FSMContext):
        try:
            payload = message.successful_payment.invoice_payload if message.successful_payment else None
        except Exception:
            payload = None
        if not payload:
            return
        status = (get_pending_status(payload) or "").lower()
        if status in {"cancelled", "canceled"}:
            logger.info(f"Платеж Stars: игнорируем отменённый invoice payload={payload}")
            return
        metadata = find_and_complete_pending_transaction(payload)
        if not metadata:
            logger.warning(f"Платеж Stars: метаданные не найдены для payload {payload}")

            try:
                fallback = get_latest_pending_for_user(message.from_user.id)
            except Exception as e:
                fallback = None
                logger.error(f"Платеж Stars: не удалось найти резервные данные для пользователя {message.from_user.id}: {e}", exc_info=True)
            if fallback and (fallback.get('payment_method') == 'Telegram Stars'):
                pid = fallback.get('payment_id') or payload
                logger.info(f"Платеж Stars: используем резервные данные для пользователя {message.from_user.id}, pid={pid}")
                metadata = find_and_complete_pending_transaction(pid)
        if not metadata:

            try:
                total_stars = int(getattr(message.successful_payment, 'total_amount', 0) or 0)
            except Exception:
                total_stars = 0
            try:
                stars_ratio_raw = get_setting("stars_per_rub") or '0'
                stars_ratio = Decimal(stars_ratio_raw)
            except Exception:
                stars_ratio = Decimal('0')
            if total_stars > 0 and stars_ratio > 0:
                amount_rub = (Decimal(total_stars) / stars_ratio).quantize(Decimal('0.01'))
                metadata = {
                    "user_id": message.from_user.id,
                    "price": float(amount_rub),
                    "action": "top_up",
                    "payment_method": "Telegram Stars",
                    "payment_id": payload,
                }
                logger.info(f"Платеж Stars: восстанавливаем пополнение из total_stars={total_stars}, ratio={stars_ratio}, amount_rub={amount_rub}")
            else:

                logger.warning("Платеж Stars: не удалось восстановить метаданные платежа; пропускаем")
                return

        try:
            if message.from_user and message.from_user.username:
                metadata.setdefault('tg_username', message.from_user.username)
        except Exception:
            pass
        await process_successful_payment(bot, metadata)
        try:
            await state.clear()
        except Exception:
            pass
