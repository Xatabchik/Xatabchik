"""Реферальная программа: тип награды, проценты, минимальные суммы.

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


def register_referral(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""






    
    # === Referral settings management ===

    class AdminReferral(StatesGroup):
        menu = State()
        waiting_for_percent = State()
        waiting_for_fixed_amount = State()
        waiting_for_start_bonus = State()
        waiting_for_min_withdrawal = State()
        waiting_for_discount = State()


    def _get_bool_setting(key: str, default: bool = False) -> bool:
        raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
        return raw in {"1", "true", "yes", "on"}


    def _get_float_setting(key: str, default: float = 0.0) -> float:
        raw = str(get_setting(key) or str(default))
        try:
            raw = raw.replace(",", ".")
            return float(raw)
        except Exception:
            return float(default)


    def _get_referral_settings_for_admin() -> dict:
        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip() or "percent_purchase"
        return {
            "enabled": _get_bool_setting("enable_referrals", default=True),
            "days_bonus": _get_bool_setting("enable_referral_days_bonus", default=True),
            "reward_type": reward_type,
            "percentage": _get_float_setting("referral_percentage", 10.0),
            "fixed_amount": _get_float_setting("fixed_referral_bonus_amount", 50.0),
            "start_bonus": _get_float_setting("referral_on_start_referrer_amount", 20.0),
            "min_withdrawal": _get_float_setting("minimum_withdrawal", 100.0),
            "discount": _get_float_setting("referral_discount", 5.0),
        }


    def _format_reward_type_human(reward_type: str) -> str:
        if reward_type == "percent_purchase":
            return "Процент от каждой покупки реферала"
        if reward_type == "fixed_purchase":
            return "Фиксированная сумма за покупку реферала"
        if reward_type == "fixed_start_referrer":
            return "Стартовый бонус пригласившему при старте по реферальной ссылке"
        return reward_type or "—"


    async def show_admin_referral_menu(message: types.Message, edit_message: bool = False):
        ref = _get_referral_settings_for_admin()
        status = "🟢 включена" if ref["enabled"] else "🔴 выключена"
        bonus_day = "✅ да" if ref["days_bonus"] else "❌ нет"

        text_out = (
            "👥 <b>Реферальная программа</b>\n\n"
            f"Статус: <b>{status}</b>\n"
            f"Бонус +1 день к подписке пригласившему: <b>{bonus_day}</b>\n"
            f"Тип начисления: <b>{_format_reward_type_human(ref['reward_type'])}</b>\n\n"
            f"Процент за покупку: <b>{ref['percentage']:.2f}%</b>\n"
            f"Фикс. сумма за покупку: <b>{ref['fixed_amount']:.2f} ₽</b>\n"
            f"Стартовый бонус пригласившему: <b>{ref['start_bonus']:.2f} ₽</b>\n"
            f"Скидка новому пользователю: <b>{ref['discount']:.2f}%</b>\n"
            f"Минимальная сумма для вывода: <b>{ref['min_withdrawal']:.2f} ₽</b>"
        )

        kb = keyboards.create_admin_referral_settings_keyboard(
            enabled=ref["enabled"],
            days_bonus_enabled=ref["days_bonus"],
            reward_type=ref["reward_type"],
        )

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_referral")
    async def admin_referral_menu_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_toggle")
    async def admin_referral_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_referral_settings_for_admin()["enabled"]
        rw_repo.update_setting("enable_referrals", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_toggle_days_bonus")
    async def admin_referral_toggle_days_bonus(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_referral_settings_for_admin()["days_bonus"]
        rw_repo.update_setting("enable_referral_days_bonus", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_set_type")
    async def admin_referral_set_type(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current_type = _get_referral_settings_for_admin()["reward_type"]
        kb = keyboards.create_admin_referral_type_keyboard(current_type)
        text = (
            "🎁 <b>Тип начисления реферального вознаграждения</b>\n\n"
            "Выберите, как начислять бонусы пригласившему:"
        )
        await callback.answer()
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data.startswith("admin_referral_type:"))
    async def admin_referral_type_chosen(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            _, value = (callback.data or "").split(":", 1)
        except Exception:
            await callback.answer("Некорректные данные.", show_alert=True)
            return
        value = (value or "").strip()
        if value not in {"percent_purchase", "fixed_purchase", "fixed_start_referrer"}:
            await callback.answer("Некорректный тип.", show_alert=True)
            return
        rw_repo.update_setting("referral_reward_type", value)
        rw_repo.update_setting("enable_fixed_referral_bonus", "true" if value == "fixed_start_referrer" else "false")
        await callback.answer("Тип обновлён.")
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_set_percent")
    async def admin_referral_set_percent(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_percent)
        await callback.answer()
        await callback.message.edit_text(
            "📊 <b>Процент вознаграждения</b>\n\n"
            "Введите процент для пригласившего (0–100):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_percent)
    async def admin_referral_percent_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число от 0 до 100.")
            return
        if val < 0 or val > 100:
            await message.answer("❌ Процент должен быть в диапазоне 0–100.")
            return
        rw_repo.update_setting("referral_percentage", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Процент вознаграждения обновлён.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_fixed_amount")
    async def admin_referral_set_fixed_amount(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_fixed_amount)
        await callback.answer()
        await callback.message.edit_text(
            "💵 <b>Фиксированная сумма за покупку</b>\n\n"
            "Введите сумму в рублях (0–100000):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_fixed_amount)
    async def admin_referral_fixed_amount_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100000).")
            return
        if val < 0 or val > 100000:
            await message.answer("❌ Некорректное значение (0–100000).")
            return
        rw_repo.update_setting("fixed_referral_bonus_amount", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Фиксированная сумма за покупку обновлена.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_start_bonus")
    async def admin_referral_set_start_bonus(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_start_bonus)
        await callback.answer()
        await callback.message.edit_text(
            "💰 <b>Стартовый бонус пригласившему</b>\n\n"
            "Введите сумму в рублях (0–100000):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_start_bonus)
    async def admin_referral_start_bonus_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100000).")
            return
        if val < 0 or val > 100000:
            await message.answer("❌ Некорректное значение (0–100000).")
            return
        rw_repo.update_setting("referral_on_start_referrer_amount", f"{val:.2f}")
        # Если задан стартовый бонус, то включаем флаг фиксированного бонуса
        rw_repo.update_setting("enable_fixed_referral_bonus", "true" if val > 0 else "false")
        await state.clear()
        await message.answer("✅ Стартовый бонус обновлён.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_min_withdrawal")
    async def admin_referral_set_min_withdrawal(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_min_withdrawal)
        await callback.answer()
        await callback.message.edit_text(
            "💳 <b>Минимальная сумма для вывода</b>\n\n"
            "Введите сумму в рублях (0–100000):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_min_withdrawal)
    async def admin_referral_min_withdrawal_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100000).")
            return
        if val < 0 or val > 100000:
            await message.answer("❌ Некорректное значение (0–100000).")
            return
        rw_repo.update_setting("minimum_withdrawal", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Минимальная сумма для вывода обновлена.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_discount")
    async def admin_referral_set_discount(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_discount)
        await callback.answer()
        await callback.message.edit_text(
            "🎟 <b>Скидка для нового пользователя</b>\n\n"
            "Введите процент скидки на первую покупку (0–100):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_discount)
    async def admin_referral_discount_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100).")
            return
        if val < 0 or val > 100:
            await message.answer("❌ Процент должен быть в диапазоне 0–100.")
            return
        rw_repo.update_setting("referral_discount", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Скидка для нового пользователя обновлена.")
        await show_admin_referral_menu(message, edit_message=False)
