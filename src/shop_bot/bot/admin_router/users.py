"""Пользователи: поиск, карточка, бан, разбан, удаление, рефералы.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_all_users,
    get_user,
    get_keys_for_user,
    ban_user,
    unban_user,
    is_admin,
    get_referral_balance_all,
    get_referrals_for_user,
)
from shop_bot.data_manager.database import delete_user_completely


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_users_1(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""



    

    class AdminUserSearch(StatesGroup):
        waiting_for_query = State()

    @admin_router.callback_query(F.data.startswith("admin_users"))
    async def admin_users_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()

        # Обработка кнопки поиска пользователя
        if callback.data == "admin_users_search":
            await state.set_state(AdminUserSearch.waiting_for_query)
            await callback.message.edit_text(
                "Введите ID пользователя или его @username для поиска:\n\n"
                "Примеры: 123456789 или @username",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return

        # Открытие списка пользователей / переключение страниц
        await state.clear()
        users = get_all_users()
        page = 0
        if callback.data.startswith("admin_users_page_"):
            try:
                page = int(callback.data.split("_")[-1])
            except Exception:
                page = 0
        await callback.message.edit_text(
            "👥 <b>Пользователи</b>",
            reply_markup=keyboards.create_admin_users_keyboard(users, page=page)
        )


    @admin_router.message(AdminUserSearch.waiting_for_query)
    async def admin_users_search_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Введите ID пользователя или его @username, либо нажмите Отмена.")
            return

        users = get_all_users() or []
        matches: list[dict] = []

        # Поиск по числовому ID
        if raw.isdigit():
            try:
                target_id = int(raw)
            except Exception:
                target_id = None
            else:
                if target_id is not None:
                    user = get_user(target_id)
                    if user:
                        matches = [user]

        # Поиск по username
        if not matches and not raw.isdigit():
            uname = raw.lstrip("@").lower()
            for u in users:
                uname_u = (u.get("username") or "").lstrip("@").lower()
                if uname_u and (uname_u == uname or uname in uname_u):
                    matches.append(u)

        # Дополнительный поиск по части ID
        if not matches and not raw.isdigit():
            for u in users:
                uid = str(u.get("telegram_id") or u.get("user_id") or u.get("id") or "")
                if uid and raw in uid:
                    matches.append(u)

        if not matches:
            await message.answer("❌ Пользователь не найден. Отправьте другой ID/username или нажмите Отмена.")
            return

        await state.clear()

        # Если найден один пользователь — показываем карточку
        if len(matches) == 1:
            u = matches[0]
            user_id = int(u.get("telegram_id") or u.get("user_id") or u.get("id"))
            user = get_user(user_id) or u

            if user.get("username"):
                uname = user.get("username").lstrip("@")
                user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
            else:
                user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"

            is_banned = user.get("is_banned", False)
            total_spent = user.get("total_spent", 0)
            balance = user.get("balance", 0)
            referral_balance = user.get("referral_balance", 0)
            referred_by = user.get("referred_by")
            keys = get_keys_for_user(user_id)
            keys_count = len(keys)

            text = (
                f"👤 <b>Пользователь {user_id}</b>\n\n"
                f"Имя пользователя: {user_tag}\n"
                f"Всего потратил: {float(total_spent):.2f} RUB\n"
                f"Баланс: {float(balance):.2f} RUB\n"
                f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
                f"Забанен: {'да' if is_banned else 'нет'}\n"
                f"Приглашён: {referred_by if referred_by else '—'}\n"
                f"Ключей: {keys_count}"
            )

            await message.answer(
                text,
                reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=is_banned)
            )
        else:
            # Если найдено несколько пользователей — показываем список с кнопками
            await message.answer(
                f"Найдено пользователей: {len(matches)}",
                reply_markup=keyboards.create_admin_users_keyboard(matches, page=0)
            )

    @admin_router.callback_query(F.data.startswith("admin_view_user_"))
    async def admin_view_user_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        user = get_user(user_id)
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return

        username = user.get('username') or '—'

        if user.get('username'):
            uname = user.get('username').lstrip('@')
            user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
        else:
            user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"
        is_banned = user.get('is_banned', False)
        total_spent = user.get('total_spent', 0)
        balance = user.get('balance', 0)
        referral_balance = user.get('referral_balance', 0)
        referred_by = user.get('referred_by')
        keys = get_keys_for_user(user_id)
        keys_count = len(keys)
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"Имя пользователя: {user_tag}\n"
            f"Всего потратил: {float(total_spent):.2f} RUB\n"
            f"Баланс: {float(balance):.2f} RUB\n"
            f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
            f"Забанен: {'да' if is_banned else 'нет'}\n"
            f"Приглашён: {referred_by if referred_by else '—'}\n"
            f"Ключей: {keys_count}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=is_banned)
        )


    @admin_router.callback_query(F.data.startswith("admin_ban_user_"))
    async def admin_ban_user(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        try:
            ban_user(user_id)
            await callback.message.answer(f"🚫 Пользователь {user_id} забанен")
            try:

                from shop_bot.data_manager.remnawave_repository import get_setting as _get_setting
                support = (_get_setting("support_bot_username") or _get_setting("support_user") or "").strip()
                kb = InlineKeyboardBuilder()
                url = None
                if support:
                    if support.startswith("@"):
                        url = f"tg://resolve?domain={support[1:]}"
                    elif support.startswith("tg://"):
                        url = support
                    elif support.startswith("http://") or support.startswith("https://"):
                        try:
                            part = support.split("/")[-1].split("?")[0]
                            if part:
                                url = f"tg://resolve?domain={part}"
                        except Exception:
                            url = support
                    else:
                        url = f"tg://resolve?domain={support}"
                if url:
                    kb.button(text="🆘 Написать в поддержку", url=url)
                else:
                    kb.button(text="🆘 Поддержка", callback_data="show_help")
                await callback.bot.send_message(
                    user_id,
                    "🚫 Ваш аккаунт заблокирован администратором. Если это ошибка — напишите в поддержку.",
                    reply_markup=kb.as_markup()
                )
            except Exception:
                pass
        except Exception as e:
            await callback.message.answer(f"❌ Не удалось забанить пользователя: {e}")
            return

        user = get_user(user_id) or {}
        username = user.get('username') or '—'
        if user.get('username'):
            uname = user.get('username').lstrip('@')
            user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
        else:
            user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"
        total_spent = user.get('total_spent', 0)
        balance = user.get('balance', 0)
        referral_balance = user.get('referral_balance', 0)
        referred_by = user.get('referred_by')
        keys = get_keys_for_user(user_id)
        keys_count = len(keys)
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"Имя пользователя: {user_tag}\n"
            f"Всего потратил: {float(total_spent):.2f} RUB\n"
            f"Баланс: {float(balance):.2f} RUB\n"
            f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
            f"Забанен: да\n"
            f"Приглашён: {referred_by if referred_by else '—'}\n"
            f"Ключей: {keys_count}"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=True)
            )
        except Exception:
            pass


def register_users_2(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""

    @admin_router.callback_query(F.data.startswith("admin_unban_user_"))
    async def admin_unban_user(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        try:
            unban_user(user_id)
            await callback.message.answer(f"✅ Пользователь {user_id} разбанен")
            try:

                kb = InlineKeyboardBuilder()
                kb.row(keyboards.get_main_menu_button())
                await callback.bot.send_message(
                    user_id,
                    "✅ Доступ к аккаунту восстановлен администратором.",
                    reply_markup=kb.as_markup()
                )
            except Exception:
                pass
        except Exception as e:
            await callback.message.answer(f"❌ Не удалось разбанить пользователя: {e}")
            return

        user = get_user(user_id) or {}
        username = user.get('username') or '—'

        if user.get('username'):
            uname = user.get('username').lstrip('@')
            user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
        else:
            user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"
        total_spent = user.get('total_spent', 0)
        balance = user.get('balance', 0)
        referral_balance = user.get('referral_balance', 0)
        referred_by = user.get('referred_by')
        keys = get_keys_for_user(user_id)
        keys_count = len(keys)
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"Имя пользователя: {user_tag}\n"
            f"Всего потратил: {float(total_spent):.2f} RUB\n"
            f"Баланс: {float(balance):.2f} RUB\n"
            f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
            f"Забанен: нет\n"
            f"Приглашён: {referred_by if referred_by else '—'}\n"
            f"Ключей: {keys_count}"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=False)
            )
        except Exception:
            pass



    @admin_router.callback_query(F.data.startswith("admin_delete_user_"))
    async def admin_delete_user(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return

        try:
            success = delete_user_completely(user_id)
        except Exception:
            logger.exception("Failed to delete user %s completely", user_id)
            success = False

        if success:
            await callback.message.answer(f"🗑 Пользователь {user_id} и все связанные с ним данные удалены.")
        else:
            await callback.message.answer("❌ Не удалось удалить пользователя. Подробности см. в логах сервера.")

    @admin_router.callback_query(F.data.startswith("admin_user_keys_"))
    async def admin_user_keys(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        
        # Разбираем callback_data. Формат может быть:
        # 1. admin_user_keys_12345 (открытие списка)
        # 2. admin_user_keys_12345_1 (переход по страницам)
        parts = callback.data.split("_")
        try:
            user_id = int(parts[3]) # Индекс 3 — это ID пользователя
            page = int(parts[4]) if len(parts) > 4 else 0 # Индекс 4 — это страница
        except (IndexError, ValueError):
            await callback.message.answer("❌ Ошибка в данных запроса")
            return

        keys = get_keys_for_user(user_id)
        
        # Редактируем сообщение, подставляя новую страницу
        await callback.message.edit_text(
            f"🔑 Ключи пользователя {user_id}:" if keys else f"У пользователя {user_id} нет ключей.",
            reply_markup=keyboards.create_admin_user_keys_keyboard(user_id, keys, page=page)
        )

    @admin_router.callback_query(F.data.startswith("admin_user_referrals_"))
    async def admin_user_referrals(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        inviter = get_user(user_id)
        if not inviter:
            await callback.message.answer("❌ Пользователь не найден")
            return
        refs = get_referrals_for_user(user_id) or []
        ref_count = len(refs)
        try:
            total_ref_earned = float(get_referral_balance_all(user_id) or 0)
        except Exception:
            total_ref_earned = 0.0

        max_items = 30
        lines = []
        for r in refs[:max_items]:
            rid = r.get('telegram_id')
            uname = r.get('username') or '—'
            rdate = r.get('registration_date') or '—'
            spent = float(r.get('total_spent') or 0)
            lines.append(f"• @{uname} (ID: {rid}) — рег: {rdate}, потратил: {spent:.2f} RUB")
        more_suffix = "\n… и ещё {}".format(ref_count - max_items) if ref_count > max_items else ""
        text = (
            f"🤝 <b>Рефералы пользователя {user_id}</b>\n\n"
            f"Всего приглашено: {ref_count}\n"
            f"Заработано по рефералке (всего): {total_ref_earned:.2f} RUB\n\n"
            + ("\n".join(lines) if lines else "Пока нет рефералов")
            + more_suffix
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ К пользователю", callback_data=f"admin_view_user_{user_id}")
        kb.button(text="⬅️ В админ-меню", callback_data="admin_menu")
        kb.adjust(1, 1)
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())
