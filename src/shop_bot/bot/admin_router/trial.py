"""Пробный период: включение, длительность, трафик, устройства, хост.

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
    get_all_hosts,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_trial(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


# === Trial settings management ===

    class AdminTrial(StatesGroup):
        menu = State()
        waiting_for_days = State()
        waiting_for_traffic = State()
        waiting_for_devices = State()


    def _get_trial_enabled() -> bool:
        return str(get_setting("trial_enabled") or "false").strip().lower() == "true"


    def _format_trial_value_gb(raw: str | None) -> str:
        s = (raw or "0").strip()
        try:
            gb = float(s.replace(",", "."))
        except Exception:
            gb = 0.0
        if gb <= 0:
            return "без лимита"
        if abs(gb - int(gb)) < 1e-9:
            return f"{int(gb)} ГБ"
        return f"{gb} ГБ"


    def _format_trial_value_int(raw: str | None) -> str:
        s = (raw or "0").strip()
        try:
            val = int(float(s.replace(",", ".")))
        except Exception:
            val = 0
        return "без лимита" if val <= 0 else str(val)


    def _get_trial_days() -> int:
        raw = (get_setting("trial_duration_days") or "3").strip()
        try:
            days = int(float(raw.replace(",", ".")))
        except Exception:
            days = 3
        if days < 1:
            days = 1
        if days > 365:
            days = 365
        return days



    async def show_admin_trial_menu(message: types.Message, edit_message: bool = False):
        enabled = _get_trial_enabled()
        days = _get_trial_days()
        traffic_txt = _format_trial_value_gb(get_setting("trial_traffic_limit_gb"))
        devices_txt = _format_trial_value_int(get_setting("trial_device_limit"))
        default_host = (get_setting("trial_default_host") or "").strip()

        status = "🟢 включён" if enabled else "🔴 выключен"
        host_line = (
            f"Группа тарифов: <b>{default_host}</b>"
            if default_host
            else "Группа тарифов: <b>авто (все доступные)</b>"
        )
        text_out = (
            "🎁 <b>Пробный период (Trial)</b>\n\n"
            f"Статус: {status}\n"
            f"Длительность: <b>{days}</b> дн.\n"
            f"Лимит трафика: <b>{traffic_txt}</b>\n"
            f"Лимит устройств: <b>{devices_txt}</b>\n"
            f"{host_line}\n\n"
            "Подсказка: 0 = без лимита (для трафика и устройств)."
        )

        kb = keyboards.create_admin_trial_settings_keyboard(
            trial_enabled=enabled,
            days=days,
            traffic_text=traffic_txt,
            devices_text=devices_txt,
            default_host=default_host,
        )

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_trial")
    async def admin_trial_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminTrial.menu)
        await show_admin_trial_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_trial_toggle")
    async def admin_trial_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_trial_enabled()
        rw_repo.update_setting("trial_enabled", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminTrial.menu)
        await show_admin_trial_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_trial_set_days")
    async def admin_trial_set_days(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.waiting_for_days)
        await callback.message.edit_text(
            "⏳ <b>Длительность триала</b>\n\n"
            "Введите количество дней (1–365):",
            reply_markup=keyboards.create_cancel_keyboard("admin_trial"),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data == "admin_trial_set_traffic")
    async def admin_trial_set_traffic(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.waiting_for_traffic)
        await callback.message.edit_text(
            "📶 <b>Лимит трафика на триал</b>\n\n"
            "Введите лимит в ГБ (например 1 или 0.5).\n"
            "0 — без лимита:",
            reply_markup=keyboards.create_cancel_keyboard("admin_trial"),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data == "admin_trial_set_devices")
    async def admin_trial_set_devices(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.waiting_for_devices)
        await callback.message.edit_text(
            "📱 <b>Лимит устройств на триал (HWID)</b>\n\n"
            "Введите максимальное число устройств.\n"
            "0 — без лимита:",
            reply_markup=keyboards.create_cancel_keyboard("admin_trial"),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data == "admin_trial_set_host")
    async def admin_trial_set_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.menu)
        hosts = get_all_hosts()
        await callback.message.edit_text(
            "🖥 <b>Группа тарифов по умолчанию для триала</b>\n\n"
            "Выберите группу тарифов, в которой будут создаваться пробные ключи.\n"
            "<b>Авто</b> — пользователь выбирает сам (или берётся единственная доступная).",
            reply_markup=keyboards.create_admin_trial_host_keyboard(hosts),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data.startswith("admin_trial_select_host_"))
    async def admin_trial_select_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        host_name = callback.data[len("admin_trial_select_host_"):]
        rw_repo.update_setting("trial_default_host", host_name)
        label = f"«{host_name}»" if host_name else "авто"
        await callback.answer(f"✅ Группа тарифов триала: {label}", show_alert=True)
        await state.set_state(AdminTrial.menu)
        await show_admin_trial_menu(callback.message, edit_message=True)

    @admin_router.message(AdminTrial.waiting_for_days)
    async def admin_trial_days_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            days = int(float(raw.replace(",", ".")))
        except Exception:
            await message.answer("❌ Введите целое число дней (1–365).")
            return
        if days < 1 or days > 365:
            await message.answer("❌ Значение должно быть в диапазоне 1–365.")
            return
        rw_repo.update_setting("trial_duration_days", str(days))
        await state.clear()
        await message.answer("✅ Длительность триала обновлена.")
        await show_admin_trial_menu(message, edit_message=False)


    @admin_router.message(AdminTrial.waiting_for_traffic)
    async def admin_trial_traffic_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            gb = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (например 1 или 0.5), либо 0.")
            return
        if gb < 0 or gb > 10000:
            await message.answer("❌ Слишком большое/некорректное значение.")
            return
        if gb == 0:
            val_str = "0"
        else:
            val_str = ("%s" % gb).rstrip("0").rstrip(".")
        rw_repo.update_setting("trial_traffic_limit_gb", val_str)
        await state.clear()
        await message.answer("✅ Лимит трафика триала обновлён.")
        await show_admin_trial_menu(message, edit_message=False)


    @admin_router.message(AdminTrial.waiting_for_devices)
    async def admin_trial_devices_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = int(float(raw.replace(",", ".")))
        except Exception:
            await message.answer("❌ Введите целое число, либо 0.")
            return
        if val < 0 or val > 1000:
            await message.answer("❌ Некорректное значение (0–1000).")
            return
        rw_repo.update_setting("trial_device_limit", str(val))
        await state.clear()
        await message.answer("✅ Лимит устройств триала обновлён.")
        await show_admin_trial_menu(message, edit_message=False)
