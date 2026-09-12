"""Главное меню, капча и завершение онбординга, плюс декоратор,
требующий регистрации пользователя.
"""

from html import escape as html_escape
from functools import wraps
from decimal import Decimal
from aiogram import (
    Bot,
    types,
)
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user,
    get_user_keys,
    get_balance,
    add_to_referral_balance_all,
    add_to_referral_balance,
    get_referral_balance,
    set_terms_agreed,
    claim_referral_start_bonus,
    is_admin,
)
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.captcha_utils import create_captcha_challenge

__all__ = [
    "show_captcha",
    "show_main_menu",
    "process_successful_onboarding",
    "registration_required",
    "_maybe_pay_referral_start_bonus",
]

async def show_captcha(message: types.Message, state: FSMContext, user_id: int):
    """Показывает капчу пользователю."""
    captcha_type = get_setting("captcha_type") or "math"
    captcha_message = get_setting("captcha_message") or "👤 Привет! Ты выглядишь как бот. Пройди простую капчу чтобы подтвердить что ты человек.\n\n"
    timeout_minutes = int(get_setting("captcha_timeout_minutes") or "15")
    
    # Создаём капча-вызов
    challenge = create_captcha_challenge(user_id, captcha_type, timeout_minutes)
    
    if not challenge:
        await message.answer("❌ Ошибка при создании капчи. Попробуйте позже.")
        return
    
    challenge_id = challenge.get("id")
    question = challenge.get("question")
    
    await state.set_state(Captcha.waiting_for_answer)
    await state.update_data(captcha_challenge_id=challenge_id, captcha_type=captcha_type)
    
    if captcha_type == "button":
        # Капча с выбором смайлика - извлекаем правильный ответ из вопроса
        correct_answer = challenge.get("correct_answer")
        # Создаём клавиатуру с вариантами
        all_emojis = ["😊", "👍", "🔥", "❤️", "⭐", "✅", "🐱", "🤖", "😂", "🎉", "💪", "🚀"]
        import random
        options = random.sample(all_emojis, 4)
        if correct_answer not in options:
            options[random.randint(0, 3)] = correct_answer
        random.shuffle(options)
        
        await message.answer(
            captcha_message + question,
            reply_markup=keyboards.create_button_captcha_keyboard(options)
        )
    else:
        # Математическая капча
        await message.answer(
            captcha_message + question + "\n\n💬 Введите ответ цифрой:",
            reply_markup=keyboards.create_math_captcha_keyboard()
        )


async def show_main_menu(message: types.Message, edit_message: bool = False):
    user_id = message.chat.id
    user_db_data = get_user(user_id)
    all_user_keys = get_user_keys(user_id)
    # Объединяем обычные ключи и подарки для передачи в клавиатуру
    user_keys = all_user_keys
    try:
        gifts_count = len(rw_repo.get_user_inactive_gifts(user_id) or [])
    except Exception:
        gifts_count = 0
    
    trial_available = not (user_db_data and user_db_data.get('trial_used'))
    is_admin_flag = is_admin(user_id)

    # Данные пользователя
    # Важно: при кликах по inline-кнопкам мы редактируем сообщение, отправленное ботом,
    # поэтому message.from_user указывает на бота. В таких случаях берём имя из chat/БД.
    username = "Пользователь"
    try:
        if getattr(message, "from_user", None) and not getattr(message.from_user, "is_bot", False):
            username = (message.from_user.first_name
                        or message.from_user.username
                        or getattr(message.from_user, "full_name", None)
                        or username)
        else:
            chat = getattr(message, "chat", None)
            if chat:
                # private chat: chat содержит данные пользователя
                full = " ".join([x for x in [getattr(chat, "first_name", None), getattr(chat, "last_name", None)] if x])
                username = (full
                            or getattr(chat, "username", None)
                            or getattr(chat, "title", None)
                            or username)
            # В БД поле `username` хранит @username ИЛИ полное имя (см. /start).
            # Не переопределяем уже найденное имя пользователя (first_name/last_name)
            # значением из БД, чтобы при возврате в меню не показывался @username.
            if username == "Пользователь" and user_db_data and user_db_data.get("username"):
                username = user_db_data.get("username") or username
    except Exception:
        if username == "Пользователь":
            username = user_db_data.get("username") if (user_db_data and user_db_data.get("username")) else username

    try:
        balance_val = get_balance(user_id) or 0
    except Exception:
        balance_val = 0
    try:
        balance_str = f"{float(balance_val):.2f}"
    except Exception:
        balance_str = str(balance_val)

    try:
        ref_balance_val = get_referral_balance(user_id) or 0
    except Exception:
        ref_balance_val = 0
    try:
        ref_balance_str = f"{float(ref_balance_val):.2f}"
    except Exception:
        ref_balance_str = str(ref_balance_val)

    username_safe = html_escape(str(username or "Пользователь"))

    # Ссылки (настраиваются в админке)
    channel_link = (get_setting("channel_link")).strip()
    chat_link = (get_setting("chat_link")).strip()
    channel_link_safe = html_escape(channel_link, quote=True)
    chat_link_safe = html_escape(chat_link, quote=True)

    # Текст главного меню
    promo_text = (get_setting("main_menu_promo_text") or "").strip()
    if not promo_text:
        promo_text = (
            "🌐 Множество локаций\n"
            "🚀 Скорость серверов 1 Гбит/с, смена IP\n"
            "📊 Безлимитный трафик\n\n"
            "Спасибо, что вы с нами!"
        )
    text = (
        f"<b>👤 Профиль: {username_safe}</b>\n\n"
        f"<blockquote>—— ID: {user_id}\n"
        f"—— Баланс: {balance_str} ₽ RUB\n"
        f"—— Заработано (реф. баланс): {ref_balance_str} ₽ RUB</blockquote>\n\n"
        f"📝 <a href=\"{channel_link_safe}\">Наш канал</a> 📝\n"
        f"👉 <a href=\"{chat_link_safe}\">Наш чат</a> 👉\n\n"
        f"{promo_text}"
    )

    # Franchise: determine whether this is a managed clone and whether the current user is its owner
    factory_bot_id = 0
    try:
        factory_bot_id = rw_repo.resolve_factory_bot_id(getattr(message.bot, "id", None))
    except Exception:
        factory_bot_id = 0

    show_partner_cabinet = False
    if factory_bot_id > 0:
        try:
            info = rw_repo.get_managed_bot(factory_bot_id) or {}
            owner_id = int(info.get("owner_telegram_id") or 0)
            show_partner_cabinet = (owner_id == int(user_id))
        except Exception:
            show_partner_cabinet = False

    show_create_bot = factory_bot_id <= 0

    try:
        keyboard = keyboards.create_dynamic_main_menu_keyboard(
            user_keys,
            trial_available,
            is_admin_flag,
            show_create_bot=show_create_bot,
            show_partner_cabinet=show_partner_cabinet,
            gifts_count=gifts_count,
        )
    except Exception as e:
        logger.warning(f"Не удалось создать динамическую клавиатуру, используем статическую: {e}")
        keyboard = keyboards.create_main_menu_keyboard(
            user_keys,
            trial_available,
            is_admin_flag,
            show_create_bot=show_create_bot,
            show_partner_cabinet=show_partner_cabinet,
            gifts_count=gifts_count,
        )

    if edit_message:
        await _safe_edit_or_answer(message, text, reply_markup=keyboard, disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)

async def process_successful_onboarding(callback: types.CallbackQuery, state: FSMContext):
    """Завершает онбординг: ставит флаг согласия и открывает главное меню."""
    user_id = callback.from_user.id
    try:
        set_terms_agreed(user_id)
    except Exception as e:
        logger.error(f"Не удалось установить согласие с условиями для пользователя {user_id}: {e}")
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await show_main_menu(callback.message, edit_message=True)
    except Exception:
        try:
            await callback.message.answer("✅ Требования выполнены. Открываю меню...")
        except Exception:
            pass
    try:
        await state.clear()
    except Exception:
        pass

def registration_required(f):
    @wraps(f)
    async def decorated_function(event: types.Update, *args, **kwargs):
        user_id = event.from_user.id
        user_data = get_user(user_id)
        if user_data:
            return await f(event, *args, **kwargs)
        else:
            message_text = "Пожалуйста, для начала работы со мной, отправьте команду /start"
            if isinstance(event, types.CallbackQuery):
                await event.answer(message_text, show_alert=True)
            else:
                await event.answer(message_text)
    return decorated_function

async def _maybe_pay_referral_start_bonus(bot: Bot, user_id: int, referrer_id: int | None) -> None:
    """Выплатить рефереру фиксированный бонус за регистрацию приглашённого пользователя
    (настройка "Фиксированный бонус при старте по ссылке", referral_reward_type ==
    'fixed_start_referrer'), если это применимо и ещё не выплачено.

    Вынесено в отдельную функцию и вызывается из ВСЕХ путей завершения регистрации
    (обычный /start, капча текстом, капча кнопкой) — раньше эта логика была только в
    прямом /start-хендлере, и если у бота включена капча (а по умолчанию она включена,
    см. initialize_default_button_configs: "captcha_enabled": "true"), приглашённые
    пользователи регистрировались через отдельные капча-хендлеры, где этот бонус вообще
    не начислялся — реферер мог быть корректно привязан (`users.referred_by`), но так и
    не получал вознаграждение при этом типе награды.
    """
    if not referrer_id:
        return
    try:
        referrer_id = int(referrer_id)
    except (TypeError, ValueError):
        return
    if referrer_id <= 0 or referrer_id == user_id:
        return

    user_data = get_user(user_id)
    if not user_data:
        return

    try:
        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
    except Exception:
        reward_type = "percent_purchase"
    if reward_type != "fixed_start_referrer":
        return

    try:
        amount_raw = get_setting("referral_on_start_referrer_amount") or "20"
        start_bonus = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
    except Exception:
        start_bonus = Decimal("20.00")
    if start_bonus <= 0:
        return

    # Claim BEFORE credit: иначе два параллельных /start оба видят флаг=0 и
    # дважды начисляют одну и ту же сумму.
    try:
        claimed = claim_referral_start_bonus(user_id)
    except Exception:
        claimed = False
    if not claimed:
        return

    try:
        add_to_referral_balance(referrer_id, float(start_bonus))
    except Exception as e:
        logger.warning(f"Реферальный стартовый бонус: не удалось добавить к балансу для реферера {referrer_id}: {e}")

    try:
        add_to_referral_balance_all(referrer_id, float(start_bonus))
    except Exception as e:
        logger.warning(f"Реферальный стартовый бонус: не удалось увеличить referral_balance_all для {referrer_id}: {e}")

    try:
        display_name = user_data.get("username") or str(user_id)
        await bot.send_message(
            chat_id=referrer_id,
            text=(
                "🎁 Начисление за приглашение!\n"
                f"Новый пользователь: {display_name} (ID: {user_id})\n"
                f"Бонус: {float(start_bonus):.2f} RUB"
            )
        )
    except Exception:
        pass


