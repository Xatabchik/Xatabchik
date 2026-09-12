"""Уведомления: напоминание неактивным, интервал, ссылка на поддержку.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import html as html_escape

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_notifications(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    

    # === Notifications (inactive usage reminders) ===

    class AdminNotifications(StatesGroup):
        menu = State()
        waiting_for_interval = State()
        waiting_for_support_url = State()

    def _get_inactive_reminder_enabled() -> bool:
        return _is_true(get_setting("inactive_usage_reminder_enabled") or "true")

    def _get_inactive_reminder_interval_hours() -> float:
        raw = (get_setting("inactive_usage_reminder_interval_hours") or "8").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            val = 8.0
        if val < 1:
            val = 1.0
        if val > 168:
            val = 168.0
        return val

    def _get_inactive_reminder_support_url() -> str:
        raw = (get_setting("inactive_usage_reminder_support_url") or "").strip()
        return raw

    async def show_admin_notifications_menu(message: types.Message, edit_message: bool = False):
        enabled = _get_inactive_reminder_enabled()
        interval_h = _get_inactive_reminder_interval_hours()

        status = "🟢 включены" if enabled else "🔴 выключены"
        support_url = _get_inactive_reminder_support_url()
        support_part = support_url if support_url else "по умолчанию"

        text_out = (
            "🔔 <b>Уведомления</b>\n\n"
            "Напоминания пользователям, которые получили ключ, но ни разу не использовали трафик.\n\n"
            f"Статус: {status}\n"
            f"Интервал: <b>{interval_h:g}</b> ч.\n"
            f"Ссылка поддержки в уведомлении: <b>{html_escape.escape(support_part)}</b>\n\n"
            "Интервал применяется и к первому уведомлению после выдачи ключа."
        )

        kb = keyboards.create_admin_notifications_settings_keyboard(
            enabled=enabled,
            interval_hours=interval_h,
            support_url=support_url,
        )

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_notifications_menu")
    async def admin_notifications_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminNotifications.menu)
        await show_admin_notifications_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_inactive_reminder_toggle")
    async def admin_inactive_reminder_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_inactive_reminder_enabled()
        rw_repo.update_setting("inactive_usage_reminder_enabled", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminNotifications.menu)
        await show_admin_notifications_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_inactive_reminder_set_interval")
    async def admin_inactive_reminder_set_interval(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminNotifications.waiting_for_interval)
        await callback.message.edit_text(
            "⏱ <b>Интервал уведомлений</b>\n\n"
            "Введите интервал в часах (1–168).\n"
            "Пример: 8\n\n"
            "Подсказка: интервал также используется как задержка перед первым уведомлением.",
            reply_markup=keyboards.create_cancel_keyboard("admin_notifications_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminNotifications.waiting_for_interval)
    async def admin_inactive_reminder_interval_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            hours = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число часов (например 8).")
            return
        if hours < 1 or hours > 168:
            await message.answer("❌ Значение должно быть в диапазоне 1–168 часов.")
            return
        # store compact
        val_str = ("%s" % hours).rstrip("0").rstrip(".")
        rw_repo.update_setting("inactive_usage_reminder_interval_hours", val_str)
        await state.clear()
        await message.answer("✅ Интервал уведомлений обновлён.")
        await show_admin_notifications_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_inactive_reminder_set_support_url")
    async def admin_inactive_reminder_set_support_url(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminNotifications.waiting_for_support_url)
        current = _get_inactive_reminder_support_url().strip()
        hint = f"\n\nТекущее значение: <code>{html_escape.escape(current)}</code>" if current else ""
        await callback.message.edit_text(
            "🆘 <b>Ссылка поддержки для уведомлений</b>\n\n"
            "Введите ссылку (например https://t.me/your_support или t.me/your_support).\n"
            "Чтобы вернуть значение по умолчанию — отправьте 0." + hint,
            reply_markup=keyboards.create_cancel_keyboard("admin_notifications_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminNotifications.waiting_for_support_url)
    async def admin_inactive_reminder_support_url_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        if raw in {"0", "-", "нет", "off"}:
            rw_repo.update_setting("inactive_usage_reminder_support_url", "")
            await state.clear()
            await message.answer("✅ Ссылка поддержки сброшена (будет использоваться значение по умолчанию).")
            await show_admin_notifications_menu(message, edit_message=False)
            return

        # minimal normalization: allow t.me/... or @user
        url = raw
        if url.startswith("@"):
            url = "https://t.me/" + url.lstrip("@")
        elif not url.startswith(("http://", "https://", "tg://")):
            url = "https://" + url.lstrip("/")

        rw_repo.update_setting("inactive_usage_reminder_support_url", url)
        await state.clear()
        await message.answer("✅ Ссылка поддержки обновлена.")
        await show_admin_notifications_menu(message, edit_message=False)
