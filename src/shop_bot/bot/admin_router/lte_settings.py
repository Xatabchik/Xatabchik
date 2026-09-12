"""Настройки LTE: интервал двойного лимита.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

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


def register_lte_settings(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    # === LTE / dual traffic pool settings ===

    class AdminLteSettings(StatesGroup):
        menu = State()
        waiting_for_interval = State()


    def _get_dual_limit_interval() -> int:
        try:
            val = int(float(get_setting("dual_limit_interval_sec") or 120))
        except Exception:
            val = 120
        return val if val > 0 else 120


    async def show_admin_lte_settings_menu(message: types.Message, edit_message: bool = False):
        interval = _get_dual_limit_interval()
        text_out = (
            "💰 <b>LTE / Сброс основного трафика</b>\n\n"
            f"Интервал проверки лимитов (сек): <b>{interval}</b>\n\n"
            "Класс ноды (♾/💰) настраивается в карточке хоста: «🖥 Хосты» → выбрать хост.\n"
            "LTE-лимит, LTE-пакеты и цена сброса основного трафика настраиваются в карточке тарифа: "
            "«🧾 Тарифы» → выбрать тариф. Цена сброса уникальна для каждого тарифа и доступна только "
            "тарифам с лимитом трафика."
        )
        kb = keyboards.create_admin_lte_settings_keyboard(dual_limit_interval_sec=interval)
        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_lte_settings_menu")
    async def admin_lte_settings_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminLteSettings.menu)
        await show_admin_lte_settings_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_lte_set_interval")
    async def admin_lte_set_interval_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminLteSettings.waiting_for_interval)
        await callback.message.edit_text(
            "⏱ <b>Интервал проверки двойных лимитов трафика</b>\n\n"
            "Введите интервал в секундах (например, 120):",
            reply_markup=keyboards.create_cancel_keyboard("admin_lte_settings_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminLteSettings.waiting_for_interval)
    async def admin_lte_set_interval_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            interval = int(float(raw.replace(",", ".")))
            if interval <= 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите положительное целое число секунд, например: 120")
            return
        rw_repo.update_setting("dual_limit_interval_sec", str(interval))
        await state.set_state(AdminLteSettings.menu)
        await message.answer("✅ Интервал проверки обновлён.")
        await show_admin_lte_settings_menu(message, edit_message=False)
