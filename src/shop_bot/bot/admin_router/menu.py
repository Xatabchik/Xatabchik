"""Корневые меню админки: главное, системное и меню настроек.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_admin_stats,
    is_admin,
)


async def show_admin_menu(message: types.Message, edit_message: bool = False):

    stats = get_admin_stats() or {}
    today_new = stats.get('today_new_users', 0)
    today_income = float(stats.get('today_income', 0) or 0)
    today_keys = stats.get('today_issued_keys', 0)
    total_users = stats.get('total_users', 0)
    total_income = float(stats.get('total_income', 0) or 0)
    total_keys = stats.get('total_keys', 0)
    active_keys = stats.get('active_keys', 0)

    text = (
        "📊 <b>Панель Администратора</b>\n\n"
        "<b>За сегодня:</b>\n"
        f"👥 Новых пользователей: {today_new}\n"
        f"💰 Доход: {today_income:.2f} RUB\n"
        f"🔑 Выдано ключей: {today_keys}\n\n"
        "<b>За все время:</b>\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"💰 Общий доход: {total_income:.2f} RUB\n"
        f"🔑 Всего ключей: {total_keys}\n\n"
        "<b>Состояние ключей:</b>\n"
        f"✅ Активных: {active_keys}"
    )

    try:
        keyboard = keyboards.create_dynamic_admin_menu_keyboard()
    except Exception as e:
        logger.warning(f"Не удалось создать динамическую админ-клавиатуру, используем статическую: {e}")
        keyboard = keyboards.create_admin_menu_keyboard()
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            pass
    else:
        await message.answer(text, reply_markup=keyboard)


async def show_admin_system_menu(message: types.Message, edit_message: bool = False):
    text = "🖥 <b>Система</b>\n\nВыберите действие:"
    try:
        keyboard = keyboards.create_dynamic_admin_system_menu_keyboard()
    except Exception as e:
        logger.warning(f"Не удалось создать динамическую клавиатуру 'Система', используем статическую: {e}")
        keyboard = keyboards.create_admin_system_menu_keyboard()
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            pass
    else:
        await message.answer(text, reply_markup=keyboard)


async def show_admin_settings_menu(message: types.Message, edit_message: bool = False):
    text = "⚙️ <b>Настройки</b>\n\nВыберите раздел:"
    try:
        keyboard = keyboards.create_dynamic_admin_settings_menu_keyboard()
    except Exception as e:
        logger.warning(f"Не удалось создать динамическую клавиатуру 'Настройки', используем статическую: {e}")
        keyboard = keyboards.create_admin_settings_menu_keyboard()
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            pass
    else:
        await message.answer(text, reply_markup=keyboard)


# __all__ — имена, которые пакет раскладывает по остальным модулям (см. __init__.py).
__all__ = [
    "show_admin_menu",
    "show_admin_system_menu",
    "show_admin_settings_menu",
]


def register_menu_1(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    @admin_router.callback_query(F.data == "admin_menu")
    async def open_admin_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_menu(callback.message, edit_message=True)
    @admin_router.callback_query(F.data == "admin_system_menu")
    async def open_admin_system_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_system_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_settings_menu")
    async def open_admin_settings_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_settings_menu(callback.message, edit_message=True)


def register_menu_2(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    @admin_router.callback_query(F.data == "noop")
    async def admin_noop(callback: types.CallbackQuery):
        await callback.answer()

    @admin_router.callback_query(F.data == "admin_cancel")
    async def admin_cancel_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Отменено")
        await state.clear()
        await show_admin_menu(callback.message, edit_message=True)
