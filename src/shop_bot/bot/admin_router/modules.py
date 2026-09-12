"""Раздел «Модули»: список плагинов, включение и отключение.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import html as html_escape

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager.remnawave_repository import is_admin

from shop_bot.core.module_loader import get_global_module_loader


def _build_modules_keyboard(modules: list[dict]) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mod in modules:
        module_id = mod.get("id") or ""
        name = mod.get("name") or module_id
        status = mod.get("status") or "disabled"
        if status == "enabled":
            builder.button(text=f"❌ {name}", callback_data=f"admin_module_disable:{module_id}")
        else:
            builder.button(text=f"✅ {name}", callback_data=f"admin_module_enable:{module_id}")
    builder.button(text="🔄 Обновить", callback_data="admin_modules_refresh")
    builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
    if modules:
        builder.adjust(*([1] * len(modules)), 1, 1)
    else:
        builder.adjust(1, 1)
    return builder.as_markup()


async def show_admin_modules_menu(message: types.Message, edit_message: bool = False):
    module_loader = get_global_module_loader()
    modules = module_loader.list_modules()
    if not modules:
        text = "🧩 <b>Модули</b>\n\nМодули не найдены."
    else:
        lines = ["🧩 <b>Модули</b>", ""]
        for mod in modules:
            status = mod.get("status") or "disabled"
            if status == "enabled":
                status_icon = "🟢"
                status_label = "включен"
            elif status == "error":
                status_icon = "🔴"
                status_label = "ошибка"
            else:
                status_icon = "🟡"
                status_label = "отключен"
            name = html_escape.escape(mod.get("name") or mod.get("id") or "—")
            module_id = html_escape.escape(mod.get("id") or "")
            line = f"{status_icon} <b>{name}</b> <code>{module_id}</code> — {status_label}"
            error_message = (mod.get("error_message") or "").strip()
            if error_message:
                error_safe = html_escape.escape(error_message)
                line += f"\n   ⚠️ {error_safe}"
            lines.append(line)
        text = "\n".join(lines)

    keyboard = _build_modules_keyboard(modules)
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


# __all__ — имена, которые пакет раскладывает по остальным модулям (см. __init__.py).
__all__ = [
    "_build_modules_keyboard",
    "show_admin_modules_menu",
]


def register_modules(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    @admin_router.callback_query(F.data == "admin_modules")
    async def open_admin_modules_menu_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminModules.browsing)
        await show_admin_modules_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_modules_refresh")
    async def refresh_admin_modules_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_modules_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data.startswith("admin_module_enable:"))
    async def admin_module_enable_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        module_id = callback.data.split(":", 1)[1]
        module_loader = get_global_module_loader()
        ok, message = module_loader.enable_module(module_id)
        await callback.answer(message, show_alert=not ok)
        await show_admin_modules_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data.startswith("admin_module_disable:"))
    async def admin_module_disable_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        module_id = callback.data.split(":", 1)[1]
        module_loader = get_global_module_loader()
        ok, message = module_loader.disable_module(module_id)
        await callback.answer(message, show_alert=not ok)
        await show_admin_modules_menu(callback.message, edit_message=True)
