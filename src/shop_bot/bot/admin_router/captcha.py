"""Капча: включение, тип, число попыток, таймаут, текст.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_captcha(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""

    # =============================
    # Captcha settings (Admin)
    # =============================
    
    @admin_router.callback_query(F.data == "admin_captcha_settings")
    async def admin_captcha_settings_handler(callback: types.CallbackQuery):
        """Показать страницу настроек капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        captcha_enabled = get_setting("captcha_enabled") == "true"
        captcha_type = get_setting("captcha_type") or "math"
        max_attempts = get_setting("captcha_max_attempts") or "3"
        timeout = get_setting("captcha_timeout_minutes") or "15"
        
        text = (
            "🤖 <b>Система капчи</b>\n\n"
            f"<b>Статус:</b> {'✅ Включена' if captcha_enabled else '❌ Отключена'}\n"
            f"<b>Тип:</b> {captcha_type}\n"
            f"<b>Макс. попыток:</b> {max_attempts}\n"
            f"<b>Timeout (мин):</b> {timeout}\n\n"
            "Выберите действие:"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text=f"{'✅ Отключить' if captcha_enabled else '❌ Включить'}", 
                      callback_data="admin_captcha_toggle")
        builder.button(text="📝 Тип капчи", callback_data="admin_captcha_type")
        builder.button(text="🔢 Макс. попыток", callback_data="admin_captcha_attempts")
        builder.button(text="⏱️ Timeout", callback_data="admin_captcha_timeout")
        builder.button(text="💬 Сообщение", callback_data="admin_captcha_message")
        builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
        builder.adjust(2)
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup())
    
    @admin_router.callback_query(F.data == "admin_captcha_toggle")
    async def admin_captcha_toggle_handler(callback: types.CallbackQuery):
        """Включить/отключить капчу."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        current = get_setting("captcha_enabled") == "true"
        new_value = "false" if current else "true"
        rw_repo.update_setting("captcha_enabled", new_value)
        
        await callback.answer(f"✅ Капча {'отключена' if not current else 'включена'}", show_alert=True)
        await admin_captcha_settings_handler(callback)
    
    @admin_router.callback_query(F.data == "admin_captcha_type")
    async def admin_captcha_type_handler(callback: types.CallbackQuery):
        """Выбрать тип капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_type") or "math"
        
        text = "📝 <b>Выберите тип капчи:</b>\n\n1️⃣ <b>Математическая</b> - решение примера (45+27=?)\n2️⃣ <b>Кнопочная</b> - выбор правильного смайлика"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Математическая" if current == "math" else "❌ Математическая", 
                      callback_data="admin_captcha_type_set:math")
        builder.button(text="✅ Кнопочная" if current == "button" else "❌ Кнопочная", 
                      callback_data="admin_captcha_type_set:button")
        builder.button(text="⬅️ Назад", callback_data="admin_captcha_settings")
        builder.adjust(2)
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup())
    
    @admin_router.callback_query(F.data.startswith("admin_captcha_type_set:"))
    async def admin_captcha_type_set_handler(callback: types.CallbackQuery):
        """Установить тип капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        captcha_type = callback.data.split(":", 1)[1]
        rw_repo.update_setting("captcha_type", captcha_type)
        
        type_name = "математическая" if captcha_type == "math" else "кнопочная"
        await callback.answer(f"✅ Тип капчи установлен: {type_name}", show_alert=True)
        await admin_captcha_settings_handler(callback)
    
    @admin_router.callback_query(F.data == "admin_captcha_attempts")
    async def admin_captcha_attempts_handler(callback: types.CallbackQuery, state: FSMContext):
        """Установить максимальное количество попыток."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_max_attempts") or "3"
        text = f"🔢 <b>Текущее значение:</b> {current} попыток\n\n<b>Введите новое значение (целое число от 1 до 10):</b>"
        
        await state.set_state(AdminSettings.waiting_for_captcha_attempts)
        await callback.message.edit_text(text, reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="admin_captcha_settings").as_markup())
    
    @admin_router.message(AdminSettings.waiting_for_captcha_attempts)
    async def admin_captcha_attempts_input_handler(message: types.Message, state: FSMContext):
        """Обработать ввод количества попыток."""
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        try:
            value = int(message.text.strip())
            if value < 1 or value > 10:
                await message.answer("Значение должно быть от 1 до 10.")
                return
            
            rw_repo.update_setting("captcha_max_attempts", str(value))
            await message.answer(f"✅ Максимум попыток установлено: {value}")
            await state.clear()
        except ValueError:
            await message.answer("Пожалуйста, введите целое число.")
    
    @admin_router.callback_query(F.data == "admin_captcha_timeout")
    async def admin_captcha_timeout_handler(callback: types.CallbackQuery, state: FSMContext):
        """Установить timeout капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_timeout_minutes") or "15"
        text = f"⏱️ <b>Текущее значение:</b> {current} минут\n\n<b>Введите новое значение (от 5 до 120 минут):</b>"
        
        await state.set_state(AdminSettings.waiting_for_captcha_timeout)
        await callback.message.edit_text(text, reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="admin_captcha_settings").as_markup())
    
    @admin_router.message(AdminSettings.waiting_for_captcha_timeout)
    async def admin_captcha_timeout_input_handler(message: types.Message, state: FSMContext):
        """Обработать ввод timeout."""
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        try:
            value = int(message.text.strip())
            if value < 5 or value > 120:
                await message.answer("Значение должно быть от 5 до 120 минут.")
                return
            
            rw_repo.update_setting("captcha_timeout_minutes", str(value))
            await message.answer(f"✅ Timeout капчи установлено: {value} минут")
            await state.clear()
        except ValueError:
            await message.answer("Пожалуйста, введите целое число.")
    
    @admin_router.callback_query(F.data == "admin_captcha_message")
    async def admin_captcha_message_handler(callback: types.CallbackQuery, state: FSMContext):
        """Установить кастомное сообщение к капче."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_message") or "👤 Привет! Ты выглядишь как бот. Пройди простую капчу..."
        text = f"💬 <b>Текущее сообщение:</b>\n{current}\n\n<b>Введите новое сообщение (до 200 символов):</b>"
        
        await state.set_state(AdminSettings.waiting_for_captcha_message)
        await callback.message.edit_text(text, reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="admin_captcha_settings").as_markup())
    
    @admin_router.message(AdminSettings.waiting_for_captcha_message)
    async def admin_captcha_message_input_handler(message: types.Message, state: FSMContext):
        """Обработать ввод сообщения."""
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        msg = message.text.strip()
        if len(msg) > 200:
            await message.answer("Сообщение должно быть не более 200 символов.")
            return
        
        rw_repo.update_setting("captcha_message", msg)
        await message.answer("✅ Сообщение капчи обновлено")
        await state.clear()
