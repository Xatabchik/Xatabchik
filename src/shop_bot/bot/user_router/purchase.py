"""Покупка и продление ключа: выбор хоста, тарифа, почта и промокод.
"""

from decimal import Decimal
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user,
    get_balance,
    get_plan_by_id,
    get_all_hosts,
    get_active_plans_for_host,
    check_promo_code_available,
    promo_error_message,
    get_referral_balance,
)
from shop_bot.config import CHOOSE_PAYMENT_METHOD_MESSAGE
from shop_bot.data_manager import remnawave_repository as rw_repo

__all__ = [
    "show_payment_options",
]

async def show_payment_options(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_data = get_user(message.chat.id)
    plan = get_plan_by_id(data.get('plan_id'))
    
    if not plan:
        try:
            await message.edit_text("❌ Ошибка: Тариф не найден.")
        except TelegramBadRequest:
            await message.answer("❌ Ошибка: Тариф не найден.")
        await state.clear()
        return
    
    price = Decimal(str(plan['price']))
    final_price = price
    discount_applied = False
    message_text = CHOOSE_PAYMENT_METHOD_MESSAGE

    if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
        discount_percentage_str = get_setting("referral_discount") or "0"
        discount_percentage = Decimal(discount_percentage_str)
        
        if discount_percentage > 0:
            discount_amount = (price * discount_percentage / 100).quantize(Decimal("0.01"))
            final_price = price - discount_amount

            message_text = (
                f"🎉 Как приглашенному пользователю, на вашу первую покупку предоставляется скидка {discount_percentage_str}%!\n"
                f"Старая цена: <s>{price:.2f} RUB</s>\n"
                f"<b>Новая цена: {final_price:.2f} RUB</b>\n\n"
            ) + CHOOSE_PAYMENT_METHOD_MESSAGE

    promo_code = (data.get('promo_code') or '').strip()
    promo_discount_amount = Decimal('0')

    if promo_code:
        # Re-check promo validity (it could be disabled/expired while user is on the payment screen)
        promo, promo_err = check_promo_code_available(
            promo_code, message.chat.id, plan_id=data.get("plan_id")
        )
        if promo_err:
            # Drop promo from state if it's no longer applicable
            await state.update_data(promo_code=None, promo_discount=0, promo_percent=None, promo_amount=None)
            promo_code = ''
            promo_discount_amount = Decimal('0')
            message_text = (
                "⚠️ Промокод больше недействителен и был снят.\n\n"
            ) + message_text
        else:
            try:
                percent = Decimal(str(promo.get('discount_percent') or 0))
            except Exception:
                percent = Decimal('0')
            try:
                amount = Decimal(str(promo.get('discount_amount') or 0))
            except Exception:
                amount = Decimal('0')

            if percent > 0:
                promo_discount_amount = (final_price * percent / 100).quantize(Decimal('0.01'))
            elif amount > 0:
                promo_discount_amount = amount.quantize(Decimal('0.01')) if hasattr(amount, 'quantize') else Decimal(str(amount))
            if promo_discount_amount > 0:
                # Clamp so price never becomes 0 or negative
                if promo_discount_amount >= final_price:
                    promo_discount_amount = (final_price - Decimal('0.01')).quantize(Decimal('0.01'))
                final_price = (final_price - promo_discount_amount).quantize(Decimal('0.01'))
                if final_price < Decimal('0.01'):
                    final_price = Decimal('0.01')
                message_text = (
                    f"🎟 Промокод {promo_code} применён!\n"
                    f"Старая цена: <s>{price:.2f} RUB</s>\n"
                    f"<b>Новая цена: {final_price:.2f} RUB</b>\n\n"
                ) + CHOOSE_PAYMENT_METHOD_MESSAGE

            await state.update_data(
                promo_code=promo.get('code'),
                promo_percent=float(percent) if percent and percent > 0 else None,
                promo_amount=float(amount) if amount and amount > 0 else None,
                promo_discount=float(promo_discount_amount) if promo_discount_amount > 0 else 0,
            )

    await state.update_data(final_price=float(final_price))


    try:
        main_balance = get_balance(message.chat.id)
    except Exception:
        main_balance = 0.0
    try:
        ref_balance = get_referral_balance(message.chat.id)
    except Exception:
        ref_balance = 0.0

    show_balance_btn = main_balance >= float(final_price)
    show_ref_balance_btn = ref_balance >= float(final_price)

    try:
        await message.edit_text(
            message_text,
            reply_markup=keyboards.create_payment_method_keyboard(
                payment_methods=_get_payment_methods(),
                action=data.get('action'),
                key_id=data.get('key_id'),
                show_balance=show_balance_btn,
                main_balance=main_balance,
                referral_balance=(ref_balance if show_ref_balance_btn else None),
                price=float(final_price),
                promo_applied=bool(data.get('promo_code')),
            )
        )
    except TelegramBadRequest:
        await message.answer(
            message_text,
            reply_markup=keyboards.create_payment_method_keyboard(
                payment_methods=_get_payment_methods(),
                action=data.get('action'),
                key_id=data.get('key_id'),
                show_balance=show_balance_btn,
                main_balance=main_balance,
                referral_balance=(ref_balance if show_ref_balance_btn else None),
                price=float(final_price)
            )
    )
    await state.set_state(PaymentProcess.waiting_for_payment_method)


def register_purchase(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(F.data == "gift_new_key")
    @registration_required
    async def gift_new_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        
        await callback.message.edit_text(
            "Вариант подключения:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts, action="gift")
        )

    @user_router.callback_query(F.data == "buy_new_key")
    @registration_required
    async def buy_new_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        
        await callback.message.edit_text(
            "Вариант подключения:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts, action="new")
        )

    @user_router.callback_query(F.data.startswith("select_host_new_"))
    @registration_required
    async def select_host_for_purchase_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_new_"):]
        plans = get_active_plans_for_host(host_name)
        if not plans:
            await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
            return
        await callback.message.edit_text(
            "Выберите тариф для нового ключа:", 
            reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
        )
    @user_router.callback_query(F.data.startswith("select_host_gift_"))
    @registration_required
    async def select_host_for_gift_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_gift_"):]
        plans = get_active_plans_for_host(host_name)
        if not plans:
            await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
            return
        await callback.message.edit_text(
            "Выберите тариф для подарочного ключа:", 
            reply_markup=keyboards.create_plans_keyboard(plans, action="gift", host_name=host_name)
        )


    @user_router.callback_query(F.data.startswith("extend_key_"))
    @registration_required
    async def extend_key_handler(callback: types.CallbackQuery):
        await callback.answer()

        try:
            key_id = int(callback.data.split("_")[2])
        except (IndexError, ValueError):
            await callback.message.edit_text("❌ Произошла ошибка. Неверный формат ключа.")
            return

        key_data = rw_repo.get_key_by_id(key_id)

        if not key_data or key_data['user_id'] != callback.from_user.id:
            await callback.message.edit_text("❌ Ошибка: Ключ не найден или не принадлежит вам.")
            return
        
        host_name = key_data.get('host_name')
        if not host_name:
            await callback.message.edit_text("❌ Ошибка: У этого ключа не указан сервер. Обратитесь в поддержку.")
            return

        plans = get_active_plans_for_host(host_name)

        if not plans:
            await callback.message.edit_text(
                f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены тарифы для продления."
            )
            return

        await callback.message.edit_text(
            f"Выберите тариф для продления ключа на сервере \"{host_name}\":",
            reply_markup=keyboards.create_plans_keyboard(
                plans=plans,
                action="extend",
                host_name=host_name,
                key_id=key_id
            )
        )

    @user_router.callback_query(F.data.startswith("buy_"))
    @registration_required
    async def plan_selection_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        parts = callback.data.split("_")[1:]
        action = parts[-2]
        key_id = int(parts[-1])
        plan_id = int(parts[-3])
        host_name = "_".join(parts[:-3])

        await state.update_data(
            action=action, key_id=key_id, plan_id=plan_id, host_name=host_name
        )

        email_prompt_enabled = (_is_true(get_setting("payment_email_prompt_enabled") or "false"))
        if email_prompt_enabled:
            await callback.message.edit_text(
                "📧 Пожалуйста, введите ваш email для отправки чека об оплате.\n\n"
                "Если вы не хотите указывать почту, нажмите кнопку ниже.",
                reply_markup=keyboards.create_skip_email_keyboard()
            )
            await state.set_state(PaymentProcess.waiting_for_email)
        else:
            await show_payment_options(callback.message, state)

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "back_to_plans")
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_plans")
    async def back_to_plans_handler(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        action = (data.get('action') or '').strip()


        if action == 'new':
            host_name = data.get('host_name') or ''
            if not host_name:
                await callback.message.edit_text(
                    "❌ Не удалось определить сервер. Вернитесь в меню.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                return
            plans = get_active_plans_for_host(host_name)
            if not plans:
                await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
                return
            await callback.message.edit_text(
                "Выберите тариф для нового ключа:",
                reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
            )
            return

        if action == 'extend':
            try:
                key_id = int(data.get('key_id') or 0)
            except Exception:
                key_id = 0
            if key_id <= 0:
                await callback.message.edit_text(
                    "❌ Не удалось определить ключ для продления.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                return
            key_data = rw_repo.get_key_by_id(key_id)
            if not key_data or key_data.get('user_id') != callback.from_user.id:
                await callback.message.edit_text("❌ Ошибка: Ключ не найден или не принадлежит вам.")
                return
            host_name = key_data.get('host_name')
            if not host_name:
                await callback.message.edit_text("❌ Ошибка: У этого ключа не указан сервер. Обратитесь в поддержку.")
                return
            plans = get_active_plans_for_host(host_name)
            if not plans:
                await callback.message.edit_text(
                    f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены тарифы для продления."
                )
                return
            await callback.message.edit_text(
                f"Выберите тариф для продления ключа на сервере \"{host_name}\":",
                reply_markup=keyboards.create_plans_keyboard(
                    plans=plans,
                    action="extend",
                    host_name=host_name,
                    key_id=key_id
                )
            )
            return


        await back_to_main_menu_handler(callback)

    @user_router.message(PaymentProcess.waiting_for_email)
    async def process_email_handler(message: types.Message, state: FSMContext):
        if is_valid_email(message.text or ""):
            await state.update_data(customer_email=(message.text or "").strip())
            await message.answer(f"✅ Email принят: {(message.text or '').strip()}")
            await show_payment_options(message, state)
        else:
            await message.answer("❌ Неверный формат email. Попробуйте еще раз.")

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "skip_email")
    async def skip_email_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.update_data(customer_email=None)
        await show_payment_options(callback.message, state)

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_email_prompt")
    async def back_to_email_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        email_prompt_enabled = (_is_true(get_setting("payment_email_prompt_enabled") or "false"))
        if not email_prompt_enabled:
            await back_to_plans_handler(callback, state)
            return
        await callback.message.edit_text(
            "📧 Пожалуйста, введите ваш email для отправки чека об оплате.\n\n"
            "Если вы не хотите указывать почту, нажмите кнопку ниже.",
            reply_markup=keyboards.create_skip_email_keyboard()
        )
        await state.set_state(PaymentProcess.waiting_for_email)
        
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "enter_promo_code")
    async def prompt_promo_code(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "🎟 Введите промокод. Напишите 'отмена', чтобы вернуться без изменений:",
            reply_markup=keyboards.create_cancel_keyboard("cancel_promo")
        )
        await state.set_state(PaymentProcess.waiting_for_promo_code)

    @user_router.callback_query(PaymentProcess.waiting_for_promo_code, F.data == "cancel_promo")
    async def cancel_promo_entry(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Отменено")
        await show_payment_options(callback.message, state)

    @user_router.message(PaymentProcess.waiting_for_promo_code)
    async def handle_promo_code_input(message: types.Message, state: FSMContext):
        code_raw = (message.text or '').strip()
        if not code_raw:
            await message.answer("❌ Промокод не должен быть пустым. Попробуйте снова или напишите 'отмена'.")
            return
        if code_raw.lower() in {"отмена", "cancel", "назад", "stop", "стоп"}:
            await show_payment_options(message, state)
            return
        data = await state.get_data()
        promo, error = check_promo_code_available(
            code_raw, message.from_user.id, plan_id=data.get("plan_id")
        )
        if error:
            await message.answer(f"❌ {promo_error_message(error)}")
            return
        discount_amount = Decimal(str(promo.get('discount_amount') or 0))
        percent = Decimal(str(promo.get('discount_percent') or 0))
        if percent > 0:
            data = await state.get_data()
            plan = get_plan_by_id(data.get('plan_id'))
            plan_price = Decimal(str(plan['price'])) if plan else Decimal('0')
            discount_amount = (plan_price * percent / 100).quantize(Decimal("0.01"))
        if discount_amount <= 0:
            await message.answer("❌ Промокод не даёт скидку. Обратитесь в поддержку.")
            return
        try:
            promo_amount_raw = Decimal(str(promo.get('discount_amount') or 0))
        except Exception:
            promo_amount_raw = Decimal('0')
        await state.update_data(
            promo_code=promo['code'],
            promo_percent=float(percent) if percent and percent > 0 else None,
            promo_amount=float(promo_amount_raw) if promo_amount_raw and promo_amount_raw > 0 else None,
            promo_discount=float(discount_amount),
        )
        await message.answer(f"✅ Промокод {promo['code']} применён! Скидка: {float(discount_amount):.2f} RUB.")
        await show_payment_options(message, state)
