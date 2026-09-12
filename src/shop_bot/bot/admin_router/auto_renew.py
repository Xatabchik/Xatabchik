"""Автопродление: включение и интервал проверки.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import is_admin


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_auto_renew(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""

    # =========================================================
    # Автопродление (глобальные настройки)
    # =========================================================

    class AdminAutoRenew(StatesGroup):
        waiting_for_hours = State()

    async def show_admin_auto_renew_menu(message: types.Message, edit_message: bool = False):
        enabled = _is_true(rw_repo.get_setting("auto_renew_globally_enabled") or "false")
        try:
            hours_before = int(rw_repo.get_setting("auto_renew_hours_before") or 24)
        except Exception:
            hours_before = 24
        status = "🟢 включено" if enabled else "🔴 выключено"
        text_out = (
            "🔄 <b>Автопродление подписок</b>\n\n"
            f"Статус: <b>{status}</b>\n"
            f"Окно срабатывания: <b>{hours_before} ч.</b> до окончания\n\n"
            "Когда включено, бот автоматически списывает с баланса пользователя "
            "стоимость тарифа и продлевает ключ. Функция работает только для ключей, "
            "у которых включено автопродление на карточке ключа."
        )
        kb = keyboards.create_admin_auto_renew_keyboard(enabled=enabled)
        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")

    @admin_router.callback_query(F.data == "admin_auto_renew")
    async def admin_auto_renew_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminAutoRenew.waiting_for_hours)
        await state.clear()
        await show_admin_auto_renew_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_auto_renew_toggle")
    async def admin_auto_renew_toggle(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _is_true(rw_repo.get_setting("auto_renew_globally_enabled") or "false")
        new_val = "false" if current else "true"
        rw_repo.update_setting("auto_renew_globally_enabled", new_val)
        status_text = "включено ✅" if not current else "выключено ❌"
        await callback.answer(f"Автопродление {status_text}")
        await show_admin_auto_renew_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_auto_renew_set_hours")
    async def admin_auto_renew_set_hours(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.answer(
            "⏰ Укажите, за сколько часов до окончания срока начинать автопродление (например: 24):"
        )
        await state.set_state(AdminAutoRenew.waiting_for_hours)

    @admin_router.message(AdminAutoRenew.waiting_for_hours)
    async def admin_auto_renew_hours_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав.")
            return
        try:
            hours = int(message.text.strip())
            if hours < 1 or hours > 168:
                await message.answer("❌ Укажите значение от 1 до 168 часов.")
                return
            rw_repo.update_setting("auto_renew_hours_before", str(hours))
            await message.answer(f"✅ Окно срабатывания установлено: <b>{hours} ч.</b>", parse_mode="HTML")
            await state.clear()
            await show_admin_auto_renew_menu(message, edit_message=False)
        except ValueError:
            await message.answer("❌ Введите целое число часов (например: 24).")
