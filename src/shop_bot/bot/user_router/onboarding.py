"""Вход в бота: /start с deep-link, онбординг, капча и главное меню.
"""

from html import escape as html_escape
from aiogram import (
    Router,
    F,
    Bot,
    types,
)
from aiogram.filters import (
    CommandObject,
    CommandStart,
)
from aiogram.fsm.context import FSMContext
from aiogram.enums import ChatMemberStatus
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user,
    register_user_if_not_exists,
    set_terms_agreed,
)
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.captcha_utils import (
    check_captcha_answer,
    has_passed_captcha,
    mark_user_passed_captcha,
)
from shop_bot.data_manager.database import (
    log_utm_visit,
    set_user_utm_slug_if_absent,
)

# Имя нужно уже на этапе импорта (декоратор применяется при
# определении функции), поэтому импортируется явно, а не через
# связывание пространств имён в __init__.
from .menu import registration_required

__all__ = [
    "back_to_main_menu_handler",
]

@registration_required
async def back_to_main_menu_handler(callback: types.CallbackQuery):
    await callback.answer()
    await show_main_menu(callback.message, edit_message=True)


def register_onboarding(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.message(CommandStart())
    async def start_handler(message: types.Message, state: FSMContext, bot: Bot, command: CommandObject):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        referrer_id = None

        # Обрабатываем вход через веб-приложение (deep-link авторизация)
        if command.args and command.args.startswith('auth_'):
            auth_token = command.args[5:]
            try:
                register_user_if_not_exists(user_id, username, None)
                ok = rw_repo.confirm_webapp_auth_request(auth_token, user_id)
                if ok:
                    await message.answer("✅ Вход выполнен! Вернитесь во вкладку с веб-приложением — она обновится автоматически.")
                else:
                    await message.answer("⚠️ Ссылка для входа устарела. Попробуйте открыть веб-приложение заново.")
            except Exception:
                logger.warning("Не удалось обработать auth_ deep-link", exc_info=True)
                await message.answer("⚠️ Не удалось выполнить вход. Попробуйте ещё раз.")
            return

        # Обрабатываем активацию подарка
        if command.args and command.args.startswith('gift_'):
            gift_code = command.args[5:]  # Убираем "gift_"

            # Запоминаем ДО регистрации — нужно для определения нового пользователя
            _gift_user_is_new = (get_user(user_id) is None)

            # Пользователь должен быть зарегистрирован или зарегистрируется
            register_user_if_not_exists(user_id, username, None)

            # Проверяем, нужна ли капча для активации подарка
            captcha_enabled = get_setting("captcha_enabled") == "true"

            if captcha_enabled and not has_passed_captcha(user_id):
                # Сохраняем gift_code и флаг нового пользователя в FSM
                await state.update_data(gift_code=gift_code, is_gift_activation=True, gift_user_is_new=_gift_user_is_new)
                await show_captcha(message, state, user_id)
                return
            else:
                # Капча отключена или уже пройдена, активируем подарок
                await _activate_gift_directly(message, bot, user_id, gift_code, is_new_user=_gift_user_is_new)
                return
        
        # Обрабатываем реферальную ссылку
        if command.args and command.args.startswith('ref_'):
            try:
                potential_referrer_id = int(command.args.split('_')[1])
                if potential_referrer_id != user_id:
                    referrer_id = potential_referrer_id
                    logger.info(f"Новый пользователь {user_id} пришел по реферальной ссылке от {referrer_id}")
            except (IndexError, ValueError):
                logger.warning(f"Получен неверный реферальный код: {command.args}")

        # Обрабатываем UTM-метку (best-effort, не должно ломать регистрацию/капчу)
        if command.args and command.args.startswith('utm_'):
            try:
                utm_slug = command.args[4:].strip()
                if utm_slug:
                    log_utm_visit(utm_slug, user_id, 'start')
                    set_user_utm_slug_if_absent(user_id, utm_slug)
            except Exception:
                logger.warning(f"Не удалось обработать UTM-метку: {command.args}", exc_info=True)

        # Проверяем, нужна ли капча
        captcha_enabled = get_setting("captcha_enabled") == "true"
        user_exists = get_user(user_id) is not None
        
        # Капча нужна только новым пользователям при первой регистрации
        if captcha_enabled and not user_exists:
            # НЕ регистрируем пользователя здесь - только показываем капчу
            # Регистрация произойдёт после успешного прохождения капчи

            # Сохраняем реферальную информацию в FSM для последующей регистрации.
            # ВАЖНО: обновляем только если пришла НОВАЯ реферальная ссылка — если
            # пользователь уже ждёт капчу (например, прошло много времени и он
            # просто написал "/start" заново без параметра рефссылки), referrer_id
            # здесь будет None, и его НЕЛЬЗЯ сохранять — это затрёт уже сохранённое
            # значение из первого перехода по ссылке (FSMContext.update_data делает
            # обычный dict.update, а не "установить, если ещё не задано").
            if referrer_id:
                await state.update_data(referred_by=referrer_id)
            else:
                existing_state_data = await state.get_data()
                referrer_id = existing_state_data.get("referred_by")
            
            # Если капча уже пройдена ранее - пропускаем
            if not has_passed_captcha(user_id):
                # Показываем капчу
                await show_captcha(message, state, user_id)
                return
            # Если капча была пройдена ранее, продолжаем регистрацию
            # Зарегистрируем пользователя сейчас
            register_user_if_not_exists(user_id, username, referrer_id)
        else:
            # Капча отключена или пользователь уже существует
            register_user_if_not_exists(user_id, username, referrer_id)

        # Важно: +1 день за реферала начисляем только после того, как реферал активирует триал.

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        user_data = get_user(user_id)

        await _maybe_pay_referral_start_bonus(bot, user_id, referrer_id)

        if user_data and user_data.get('agreed_to_terms'):
            await message.answer(
                f"👋 Снова здравствуйте, <b>{html_escape(str(message.from_user.full_name or 'Пользователь'))}</b>!",
                reply_markup=keyboards.main_reply_keyboard
            )
            await show_main_menu(message)
            return

        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        channel_url = get_setting("channel_url")

        if not channel_url and (not terms_url or not privacy_url):
            set_terms_agreed(user_id)
            await show_main_menu(message)
            return

        is_subscription_forced = get_setting("force_subscription") == "true"
        
        show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)

        if not show_welcome_screen:
            set_terms_agreed(user_id)
            await show_main_menu(message)
            return

        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
        
        if is_subscription_forced and channel_url:
            welcome_parts.append("Для доступа ко всем функциям, пожалуйста, подпишитесь на наш канал.")
        
        if terms_url and privacy_url:
            welcome_parts.append(
                "Также необходимо ознакомиться и принять наши "
                f"<a href='{terms_url}'>Условия использования</a> и "
                f"<a href='{privacy_url}'>Политику конфиденциальности</a>."
            )
        
        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
        final_text = "\n".join(welcome_parts)
        
        await message.answer(
            final_text,
            reply_markup=keyboards.create_welcome_keyboard(
                channel_url=channel_url,
                is_subscription_forced=is_subscription_forced
            ),
            disable_web_page_preview=True
        )
        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)

    @user_router.callback_query(Onboarding.waiting_for_subscription_and_agreement, F.data == "check_subscription_and_agree")
    async def check_subscription_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        channel_url = get_setting("channel_url")
        is_subscription_forced = get_setting("force_subscription") == "true"

        if not is_subscription_forced or not channel_url:
            await process_successful_onboarding(callback, state)
            return
            
        try:
            if '@' not in channel_url and 't.me/' not in channel_url:
                logger.error(f"Неверный формат URL канала: {channel_url}. Пропускаем проверку подписки.")
                await process_successful_onboarding(callback, state)
                return

            channel_id = '@' + channel_url.split('/')[-1] if 't.me/' in channel_url else channel_url
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await process_successful_onboarding(callback, state)
            else:
                await callback.answer("Вы еще не подписались на канал. Пожалуйста, подпишитесь и попробуйте снова.", show_alert=True)

        except Exception as e:
            logger.error(f"Ошибка при проверке подписки для user_id {user_id} на канал {channel_url}: {e}")
            await callback.answer("Не удалось проверить подписку. Убедитесь, что бот является администратором канала. Попробуйте позже.", show_alert=True)

    @user_router.message(Onboarding.waiting_for_subscription_and_agreement)
    async def onboarding_fallback_handler(message: types.Message):
        await message.answer("Пожалуйста, выполните требуемые действия и нажмите на кнопку в сообщении выше.")

    # =============================
    # Captcha handlers
    # =============================
    
    @user_router.message(Captcha.waiting_for_answer)
    async def captcha_answer_handler(message: types.Message, state: FSMContext):
        """Обработчик текстового ответа на математическую капчу."""
        user_id = message.from_user.id
        
        try:
            data = await state.get_data()
            challenge_id = data.get("captcha_challenge_id")
            captcha_type = data.get("captcha_type", "math")
            referred_by = data.get("referred_by")  # Получаем сохранённую реферальную информацию
            
            if not challenge_id:
                await message.answer("❌ Сессия капчи истекла. Напишите /start для новой попытки.")
                await state.clear()
                return
            
            user_answer = message.text
            success, msg = check_captcha_answer(challenge_id, user_answer)
            
            if success:
                # Капча пройдена
                mark_user_passed_captcha(user_id, challenge_id)
                await message.answer(msg)
                
                # 🔴 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ в БД после успешного прохождения капчи
                # Используем сохранённую реферальную информацию
                username = message.from_user.username or message.from_user.full_name
                register_user_if_not_exists(user_id, username, referred_by)
                # Тот же фиксированный бонус рефереру, что и в прямом /start без капчи
                # (см. _maybe_pay_referral_start_bonus) — раньше здесь не начислялся вообще.
                await _maybe_pay_referral_start_bonus(message.bot, user_id, referred_by)
        
                # Проверяем, активируем ли мы подарок
                gift_code = data.get("gift_code")
                if gift_code:
                    # Captcha is only shown to new users — default True, but honour FSM flag if stored
                    _is_new = data.get("gift_user_is_new", True)
                    await state.clear()
                    await _activate_gift_directly(message, message.bot, user_id, gift_code, is_new_user=_is_new)
                    return

                # Продолжаем onboarding
                await state.clear()

                # Выполняем логику регистрации с согласием
                terms_url = get_setting("terms_url")
                privacy_url = get_setting("privacy_url")
                channel_url = get_setting("channel_url")

                if not channel_url and (not terms_url or not privacy_url):
                    set_terms_agreed(user_id)
                    # Переходим прямо в главное меню
                    await show_main_menu(message)
                else:
                    # Показываем экран приветствия с согласием
                    is_subscription_forced = get_setting("force_subscription") == "true"
                    show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)
                    
                    if not show_welcome_screen:
                        set_terms_agreed(user_id)
                        await show_main_menu(message)
                    else:
                        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
                        if is_subscription_forced and channel_url:
                            welcome_parts.append(f"🔗 <a href='{channel_url}'>Подпишись на канал</a>\n")
                        if terms_url and privacy_url:
                            welcome_parts.append(f"📋 Прочитай <a href='{terms_url}'>Условия</a> и <a href='{privacy_url}'>Политику</a>\n")
                        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
                        final_text = "\n".join(welcome_parts)
                        await message.answer(
                            final_text,
                            reply_markup=keyboards.create_welcome_keyboard(
                                channel_url=channel_url,
                                is_subscription_forced=is_subscription_forced
                            ),
                            disable_web_page_preview=True
                        )
                        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)
            else:
                # Неправильный ответ
                await message.answer(msg)
        
        except Exception as e:
            logger.error(f"Error in captcha_answer_handler: {e}", exc_info=True)
            await message.answer("❌ Ошибка при проверке ответа. Попробуйте снова.")
    
    @user_router.callback_query(Captcha.waiting_for_answer, F.data.startswith("captcha_answer:"))
    async def captcha_button_answer_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик ответа на капчу с выбором кнопки."""
        user_id = callback.from_user.id
        user_answer = callback.data.split(":", 1)[1]
        
        try:
            data = await state.get_data()
            challenge_id = data.get("captcha_challenge_id")
            referred_by = data.get("referred_by")  # Получаем сохранённую реферальную информацию
            
            if not challenge_id:
                await callback.answer("❌ Сессия капчи истекла. Напишите /start для новой попытки.", show_alert=True)
                await state.clear()
                return
            
            success, msg = check_captcha_answer(challenge_id, user_answer)
            
            if success:
                # Капча пройдена
                mark_user_passed_captcha(user_id, challenge_id)
                await callback.answer(msg, show_alert=True)
                
                # 🔴 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ в БД после успешного прохождения капчи
                # Используем сохранённую реферальную информацию
                username = callback.from_user.username or callback.from_user.full_name
                register_user_if_not_exists(user_id, username, referred_by)
                # Тот же фиксированный бонус рефереру, что и в прямом /start без капчи
                # (см. _maybe_pay_referral_start_bonus) — раньше здесь не начислялся вообще.
                await _maybe_pay_referral_start_bonus(callback.bot, user_id, referred_by)
                
                # Проверяем, активируем ли мы подарок
                gift_code = data.get("gift_code")
                if gift_code:
                    _is_new = data.get("gift_user_is_new", True)
                    await state.clear()
                    await _activate_gift_directly(callback.message, callback.bot, user_id, gift_code, is_new_user=_is_new)
                    return

                # Продолжаем onboarding
                await state.clear()

                # Выполняем логику регистрации с согласием
                terms_url = get_setting("terms_url")
                privacy_url = get_setting("privacy_url")
                channel_url = get_setting("channel_url")

                if not channel_url and (not terms_url or not privacy_url):
                    set_terms_agreed(user_id)
                    # Редактируем или отправляем главное меню
                    try:
                        await show_main_menu(callback.message, edit_message=True)
                    except Exception:
                        await show_main_menu(callback.message, edit_message=False)
                else:
                    # Показываем экран приветствия с согласием
                    is_subscription_forced = get_setting("force_subscription") == "true"
                    show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)
                    
                    if not show_welcome_screen:
                        set_terms_agreed(user_id)
                        try:
                            await show_main_menu(callback.message, edit_message=True)
                        except Exception:
                            await show_main_menu(callback.message, edit_message=False)
                    else:
                        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
                        if is_subscription_forced and channel_url:
                            welcome_parts.append(f"🔗 <a href='{channel_url}'>Подпишись на канал</a>\n")
                        if terms_url and privacy_url:
                            welcome_parts.append(f"📋 Прочитай <a href='{terms_url}'>Условия</a> и <a href='{privacy_url}'>Политику</a>\n")
                        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
                        final_text = "\n".join(welcome_parts)
                        try:
                            await callback.message.edit_text(
                                final_text,
                                reply_markup=keyboards.create_welcome_keyboard(
                                    channel_url=channel_url,
                                    is_subscription_forced=is_subscription_forced
                                )
                            )
                        except Exception:
                            await callback.message.answer(
                                final_text,
                                reply_markup=keyboards.create_welcome_keyboard(
                                    channel_url=channel_url,
                                    is_subscription_forced=is_subscription_forced
                                )
                            )
                        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)
            else:
                # Неправильный ответ
                await callback.answer(msg, show_alert=True)
        
        except Exception as e:
            logger.error(f"Error in captcha_button_answer_handler: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при проверке ответа. Попробуйте снова.", show_alert=True)
    
    @user_router.callback_query(Captcha.waiting_for_answer, F.data == "cancel_captcha")
    async def cancel_captcha_handler(callback: types.CallbackQuery, state: FSMContext):
        """Отмена капчи."""
        await callback.answer("❌ Капча отменена. Напишите /start для новой попытки.")
        await state.clear()
        await callback.message.delete()

    @user_router.message(F.text == "🏠 Главное меню")
    @registration_required
    async def main_menu_handler(message: types.Message):
        await show_main_menu(message)
    user_router.callback_query(F.data == 'back_to_main_menu')(back_to_main_menu_handler)

    @user_router.callback_query(F.data == "open_main_menu")
    @registration_required
    async def open_main_menu_handler(callback: types.CallbackQuery):
        await callback.answer()
        await show_main_menu(callback.message, edit_message=False)

    @user_router.callback_query(F.data == "show_main_menu")
    @registration_required
    async def show_main_menu_cb(callback: types.CallbackQuery):
        await callback.answer()
        await show_main_menu(callback.message, edit_message=True)
