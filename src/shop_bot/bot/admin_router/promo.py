"""Промокоды: пошаговое создание, список, включение и отключение.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import uuid
import re
from datetime import datetime, timedelta

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    is_admin,
    create_promo_code,
    list_promo_codes,
    update_promo_code_status,
)


async def show_admin_promo_menu(message: types.Message, edit_message: bool = False):
    text = (
        "🎟 <b>Управление промокодами</b>\n\n"
        "Здесь можно создавать новые промокоды, просматривать список и отключать их."
    )
    keyboard = keyboards.create_admin_promo_menu_keyboard()
    if edit_message:
        try:
            await message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


def _parse_datetime_input(raw: str) -> datetime | None:
    value = (raw or "").strip()
    if not value or value.lower() in {"skip", "нет", "не", "none"}:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    raise ValueError("Неверный формат даты. Используйте 'ГГГГ-ММ-ДД' или 'ГГГГ-ММ-ДД ЧЧ:ММ'.")


def _format_promo_line(promo: dict) -> str:
    code = promo.get("code") or "—"
    discount_percent = promo.get("discount_percent")
    discount_amount = promo.get("discount_amount")
    try:
        if discount_percent:
            discount_text = f"{float(discount_percent):.2f}%"
        else:
            discount_text = f"{float(discount_amount or 0):.2f} RUB"
    except Exception:
        discount_text = str(discount_percent or discount_amount or "—")

    status_parts: list[str] = []
    is_active = bool(promo.get("is_active"))
    status_parts.append("🟢 активен" if is_active else "🔴 отключён")

    try:
        usage_limit_total = int(promo.get("usage_limit_total") or 0)
    except Exception:
        usage_limit_total = 0
    used_total = int(promo.get("used_total") or 0)
    if usage_limit_total:
        status_parts.append(f"{used_total}/{usage_limit_total}")
        if used_total >= usage_limit_total:
            status_parts.append("лимит исчерпан")

    try:
        usage_limit_per_user = int(promo.get("usage_limit_per_user") or 0)
    except Exception:
        usage_limit_per_user = 0
    if usage_limit_per_user:
        status_parts.append(f"пользователь ≤ {usage_limit_per_user}")

    valid_until = promo.get("valid_until")
    if valid_until:
        status_parts.append(f"до {str(valid_until)[:16]}")

    plan_ids = promo.get("applicable_plan_ids")
    if plan_ids:
        status_parts.append(f"тарифы {plan_ids}")
    segment_type = (promo.get("segment_type") or "").strip()
    if segment_type == "no_active_subscription":
        status_parts.append("нет активной подписки")
    elif segment_type == "min_total_spent":
        try:
            status_parts.append(f"сумма ≥ {float(promo.get('segment_value') or 0):.0f} ₽")
        except Exception:
            status_parts.append("мин. сумма покупок")

    status_text = ", ".join(status_parts)
    return f"• <code>{code}</code> — скидка: {discount_text} | статус: {status_text}"


def _build_promo_list_keyboard(codes: list[dict], page: int = 0, page_size: int = 10) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    total = len(codes)
    start = page * page_size
    end = start + page_size
    page_items = codes[start:end]
    if not page_items:
        builder.button(text="Промокодов нет", callback_data="noop")
    for promo in page_items:
        code = promo.get("code") or "—"
        is_active = bool(promo.get("is_active"))
        label = f"{'🟢' if is_active else '🔴'} {code}"
        builder.button(text=label, callback_data=f"admin_promo_toggle_{code}")
    have_prev = start > 0
    have_next = end < total
    if have_prev:
        builder.button(text="⬅️ Назад", callback_data=f"admin_promo_page_{page-1}")
    if have_next:
        builder.button(text="Вперёд ➡️", callback_data=f"admin_promo_page_{page+1}")
    builder.button(text="⬅️ В меню", callback_data="admin_promo_menu")
    rows = [1] * len(page_items)
    tail: list[int] = []
    if have_prev or have_next:
        tail.append(2 if (have_prev and have_next) else 1)
    tail.append(1)
    builder.adjust(*(rows + tail if rows else tail))
    return builder.as_markup()


# __all__ — имена, которые пакет раскладывает по остальным модулям (см. __init__.py).
__all__ = [
    "show_admin_promo_menu",
    "_parse_datetime_input",
    "_format_promo_line",
    "_build_promo_list_keyboard",
]


def register_promo(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    class AdminPromoCreate(StatesGroup):
        waiting_for_code = State()
        waiting_for_discount_type = State()
        waiting_for_discount_value = State()
        waiting_for_total_limit = State()
        waiting_for_per_user_limit = State()
        waiting_for_valid_from = State()
        waiting_for_valid_until = State()
        waiting_for_description = State()
        waiting_for_segment = State()
        waiting_for_segment_value = State()
        waiting_for_plans = State()
        confirming = State()

    @admin_router.callback_query(F.data == "admin_promo_menu")
    async def admin_promo_menu_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await show_admin_promo_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_promo_create")
    async def admin_promo_create_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminPromoCreate.waiting_for_code)
        await callback.message.edit_text(
            "🔐 Создание промокода\n\nВыберите способ указания кода:",
            reply_markup=keyboards.create_admin_promo_code_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_code,
        F.data == "admin_promo_code_auto"
    )
    async def admin_promo_code_auto(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        code = uuid.uuid4().hex[:8].upper()
        await state.update_data(promo_code=code)
        await state.set_state(AdminPromoCreate.waiting_for_discount_type)
        try:
            await callback.message.edit_text(
                f"Код: <code>{code}</code>\n\nВыберите тип скидки:",
                reply_markup=keyboards.create_admin_promo_discount_keyboard(),
                parse_mode='HTML'
            )
        except Exception:
            await callback.message.answer(
                f"Код: <code>{code}</code>\n\nВыберите тип скидки:",
                reply_markup=keyboards.create_admin_promo_discount_keyboard(),
                parse_mode='HTML'
            )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_code,
        F.data == "admin_promo_code_custom"
    )
    async def admin_promo_code_custom(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            "Введите желаемый код (только латиница/цифры) или напишите <b>авто</b> для генерации:",
            reply_markup=keyboards.create_admin_cancel_keyboard(),
            parse_mode='HTML'
        )

    @admin_router.message(AdminPromoCreate.waiting_for_code)
    async def admin_promo_create_code(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        if not raw:
            await message.answer("❌ Введите код или напишите 'авто'.")
            return
        code = uuid.uuid4().hex[:8].upper() if raw.lower() == 'авто' or raw.lower() == 'auto' else raw.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{3,32}", code):
            await message.answer("❌ Код должен состоять из латиницы/цифр и быть длиной 3-32 символа.")
            return
        await state.update_data(promo_code=code)
        await state.set_state(AdminPromoCreate.waiting_for_discount_type)
        await message.answer(
            "Выберите тип скидки:",
            reply_markup=keyboards.create_admin_promo_discount_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_discount_type,
        F.data.in_({"admin_promo_discount_percent", "admin_promo_discount_amount"})
    )
    async def admin_promo_set_discount_type(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        discount_type = 'percent' if callback.data.endswith('percent') else 'amount'
        await state.update_data(discount_type=discount_type)
        await state.set_state(AdminPromoCreate.waiting_for_discount_value)
        prompt = "Введите процент скидки (например, 10.5):" if discount_type == 'percent' else "Введите размер скидки в RUB (например, 150):"
        await callback.message.edit_text(prompt, reply_markup=keyboards.create_admin_cancel_keyboard())

    @admin_router.message(AdminPromoCreate.waiting_for_discount_value)
    async def admin_promo_set_discount_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        discount_type = data.get('discount_type')
        raw = (message.text or '').strip().replace(',', '.')
        try:
            value = float(raw)
        except Exception:
            await message.answer("❌ Введите число.")
            return
        if value <= 0:
            await message.answer("❌ Значение должно быть положительным.")
            return
        if discount_type == 'percent' and value >= 100:
            await message.answer("❌ Процент скидки должен быть меньше 100.")
            return
        await state.update_data(discount_value=value)
        await state.set_state(AdminPromoCreate.waiting_for_total_limit)
        await message.answer(
            "Введите общий лимит активаций или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_limit_keyboard("total")
        )

    @admin_router.message(AdminPromoCreate.waiting_for_total_limit)
    async def admin_promo_set_total_limit(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().lower()
        limit_total: int | None
        if raw in {'0', '∞', 'inf', 'infinity', 'безлимит', 'нет'} or not raw:
            limit_total = None
        else:
            try:
                limit_total = int(raw)
            except Exception:
                await message.answer("❌ Введите целое число или 0 для безлимита.")
                return
            if limit_total <= 0:
                limit_total = None
        await state.update_data(usage_limit_total=limit_total)
        await state.set_state(AdminPromoCreate.waiting_for_per_user_limit)
        await message.answer(
            "Введите лимит на пользователя или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_limit_keyboard("user")
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_total_limit,
        F.data.startswith("admin_promo_limit_total_")
    )
    async def admin_promo_total_limit_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        tail = callback.data.replace("admin_promo_limit_total_", "", 1)
        if tail == "custom":
            await callback.message.edit_text(
                "Введите общий лимит активаций (целое число) или 0/∞ для безлимита:",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        limit_total = None if tail == "inf" else int(tail)
        await state.update_data(usage_limit_total=limit_total)
        await state.set_state(AdminPromoCreate.waiting_for_per_user_limit)
        await callback.message.edit_text(
            "Введите лимит на пользователя или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_limit_keyboard("user")
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_per_user_limit,
        F.data.startswith("admin_promo_limit_user_")
    )
    async def admin_promo_user_limit_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        tail = callback.data.replace("admin_promo_limit_user_", "", 1)
        if tail == "custom":
            await callback.message.edit_text(
                "Введите лимит на пользователя (целое число) или 0/∞ для безлимита:",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        limit_user = None if tail == "inf" else int(tail)
        await state.update_data(usage_limit_per_user=limit_user)
        await state.set_state(AdminPromoCreate.waiting_for_valid_from)
        await callback.message.edit_text(
            "Укажите дату начала действия или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_valid_from_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_per_user_limit)
    async def admin_promo_set_per_user_limit(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().lower()
        limit_user: int | None
        if raw in {'0', '∞', 'inf', 'infinity', 'безлимит', 'нет'} or not raw:
            limit_user = None
        else:
            try:
                limit_user = int(raw)
            except Exception:
                await message.answer("❌ Введите целое число или 0 для безлимита.")
                return
            if limit_user <= 0:
                limit_user = None
        await state.update_data(usage_limit_per_user=limit_user)
        await state.set_state(AdminPromoCreate.waiting_for_valid_from)
        await message.answer(
            "Укажите дату начала действия (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ). Напишите 'skip', чтобы пропустить:",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_valid_from)
    async def admin_promo_set_valid_from(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            valid_from = _parse_datetime_input(raw)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            return
        await state.update_data(valid_from=valid_from)
        await state.set_state(AdminPromoCreate.waiting_for_valid_until)
        await message.answer(
            "Укажите дату окончания действия или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_valid_until_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_valid_from,
        F.data.in_({
            "admin_promo_valid_from_now",
            "admin_promo_valid_from_today",
            "admin_promo_valid_from_tomorrow",
            "admin_promo_valid_from_skip",
            "admin_promo_valid_from_custom",
        })
    )
    async def admin_promo_valid_from_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        now = datetime.now()
        if callback.data.endswith("custom"):
            await callback.message.edit_text(
                "Укажите дату начала (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ):",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        if callback.data.endswith("skip"):
            valid_from = None
        elif callback.data.endswith("today"):
            valid_from = datetime(now.year, now.month, now.day)
        elif callback.data.endswith("tomorrow"):
            valid_from = datetime(now.year, now.month, now.day) + timedelta(days=1)
        else:
            valid_from = now
        await state.update_data(valid_from=valid_from)
        await state.set_state(AdminPromoCreate.waiting_for_valid_until)
        await callback.message.edit_text(
            "Укажите дату окончания действия или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_valid_until_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_valid_until)
    async def admin_promo_set_valid_until(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            valid_until = _parse_datetime_input(raw)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            return
        data = await state.get_data()
        valid_from = data.get('valid_from')
        if valid_from and valid_until and valid_until <= valid_from:
            await message.answer("❌ Дата окончания должна быть позже даты начала.")
            return
        await state.update_data(valid_until=valid_until)
        await state.set_state(AdminPromoCreate.waiting_for_description)
        await message.answer(
            "Добавьте описание/комментарий или пропустите:",
            reply_markup=keyboards.create_admin_promo_description_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_valid_until,
        F.data.in_({
            "admin_promo_valid_until_plus1d",
            "admin_promo_valid_until_plus7d",
            "admin_promo_valid_until_plus30d",
            "admin_promo_valid_until_skip",
            "admin_promo_valid_until_custom",
        })
    )
    async def admin_promo_valid_until_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("custom"):
            await callback.message.edit_text(
                "Укажите дату окончания (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ):",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        if callback.data.endswith("skip"):
            valid_until = None
        else:
            data = await state.get_data()
            base = data.get('valid_from') or datetime.now()
            if callback.data.endswith("plus1d"):
                valid_until = base + timedelta(days=1)
            elif callback.data.endswith("plus7d"):
                valid_until = base + timedelta(days=7)
            else:
                valid_until = base + timedelta(days=30)
        await state.update_data(valid_until=valid_until)
        await state.set_state(AdminPromoCreate.waiting_for_description)
        await callback.message.edit_text(
            "Добавьте описание/комментарий или пропустите:",
            reply_markup=keyboards.create_admin_promo_description_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_description)
    async def admin_promo_description(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        desc = (message.text or '').strip()
        description = None if not desc or desc.lower() in {'skip', 'пропустить', 'нет'} else desc
        await state.update_data(description=description)
        await state.set_state(AdminPromoCreate.waiting_for_segment)
        await message.answer(
            "Ограничить промокод сегментом пользователей?",
            reply_markup=keyboards.create_admin_promo_segment_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_description,
        F.data.in_({"admin_promo_desc_skip", "admin_promo_desc_custom"})
    )
    async def admin_promo_desc_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("custom"):
            await callback.message.edit_text(
                "Введите описание промокода (опционально) или нажмите Отмена:",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return

        await state.update_data(description=None)
        await state.set_state(AdminPromoCreate.waiting_for_segment)
        await callback.message.edit_text(
            "Ограничить промокод сегментом пользователей?",
            reply_markup=keyboards.create_admin_promo_segment_keyboard()
        )

    async def _show_promo_confirm(message_or_callback, state: FSMContext):
        data = await state.get_data()
        code = data.get('promo_code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        total_limit = data.get('usage_limit_total')
        per_user_limit = data.get('usage_limit_per_user')
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        description = data.get('description')
        segment_type = data.get('segment_type')
        segment_value = data.get('segment_value')
        plan_ids = data.get('applicable_plan_ids')
        if not segment_type:
            segment_text = "без ограничения"
        elif segment_type == "no_active_subscription":
            segment_text = "нет активной подписки"
        elif segment_type == "min_total_spent":
            segment_text = f"сумма покупок ≥ {float(segment_value or 0):.0f} ₽"
        else:
            segment_text = str(segment_type)
        plans_text = "все тарифы" if not plan_ids else ", ".join(str(i) for i in plan_ids)
        summary_lines = [
            "Проверьте данные промокода:",
            f"Код: <code>{code}</code>",
            f"Тип скидки: {'процент' if discount_type == 'percent' else 'фиксированная'}",
            f"Значение: {discount_value:.2f}{'%' if discount_type == 'percent' else ' RUB'}",
            f"Лимит всего: {total_limit if total_limit is not None else 'без ограничений'}",
            f"Лимит на пользователя: {per_user_limit if per_user_limit is not None else 'без ограничений'}",
            f"Действует с: {valid_from.isoformat(' ') if valid_from else '—'}",
            f"Действует до: {valid_until.isoformat(' ') if valid_until else '—'}",
            f"Описание: {description or '—'}",
            f"Тарифы: {plans_text}",
            f"Сегмент: {segment_text}",
        ]
        summary_text = "\n".join(summary_lines)
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Создать", callback_data="admin_promo_confirm")
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(1, 1)
        await state.set_state(AdminPromoCreate.confirming)
        target = message_or_callback.message if hasattr(message_or_callback, "message") and hasattr(message_or_callback, "data") else message_or_callback
        edit = getattr(target, "edit_text", None)
        if edit and hasattr(message_or_callback, "data"):
            await target.edit_text(summary_text, reply_markup=builder.as_markup(), parse_mode='HTML')
        else:
            await target.answer(summary_text, reply_markup=builder.as_markup(), parse_mode='HTML')

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_segment,
        F.data.in_({
            "admin_promo_segment_none",
            "admin_promo_segment_no_sub",
            "admin_promo_segment_min_spent",
        })
    )
    async def admin_promo_set_segment(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("none"):
            await state.update_data(segment_type=None, segment_value=None)
            await state.set_state(AdminPromoCreate.waiting_for_plans)
            await callback.message.edit_text(
                "Ограничить промокод тарифами?",
                reply_markup=keyboards.create_admin_promo_plans_keyboard()
            )
            return
        if callback.data.endswith("no_sub"):
            await state.update_data(segment_type="no_active_subscription", segment_value=None)
            await state.set_state(AdminPromoCreate.waiting_for_plans)
            await callback.message.edit_text(
                "Ограничить промокод тарифами?",
                reply_markup=keyboards.create_admin_promo_plans_keyboard()
            )
            return
        await state.update_data(segment_type="min_total_spent")
        await state.set_state(AdminPromoCreate.waiting_for_segment_value)
        await callback.message.edit_text(
            "Введите минимальную сумму покупок в рублях (только оплаченные транзакции, без pending):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_segment_value)
    async def admin_promo_set_segment_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip().replace(",", ".")
        try:
            value = float(raw)
        except Exception:
            await message.answer("❌ Введите число больше 0.")
            return
        if value <= 0:
            await message.answer("❌ Сумма должна быть больше 0.")
            return
        await state.update_data(segment_value=value)
        await state.set_state(AdminPromoCreate.waiting_for_plans)
        await message.answer(
            "Ограничить промокод тарифами?",
            reply_markup=keyboards.create_admin_promo_plans_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_plans,
        F.data.in_({"admin_promo_plans_all", "admin_promo_plans_custom"})
    )
    async def admin_promo_set_plans(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("all"):
            await state.update_data(applicable_plan_ids=None)
            await _show_promo_confirm(callback, state)
            return
        await callback.message.edit_text(
            "Введите ID тарифов через запятую (например: 1, 3, 5):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_plans)
    async def admin_promo_set_plans_custom(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        parts = [p.strip() for p in (message.text or "").replace(";", ",").split(",") if p.strip()]
        if not parts:
            await message.answer("❌ Укажите хотя бы один plan_id или вернитесь и выберите «Все тарифы».")
            return
        ids: list[int] = []
        for part in parts:
            try:
                ids.append(int(part))
            except Exception:
                await message.answer(f"❌ «{part}» не является числом.")
                return
        await state.update_data(applicable_plan_ids=ids)
        await _show_promo_confirm(message, state)

    @admin_router.callback_query(AdminPromoCreate.confirming, F.data == "admin_promo_confirm")
    async def admin_promo_confirm(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        code = data.get('promo_code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        total_limit = data.get('usage_limit_total')
        per_user_limit = data.get('usage_limit_per_user')
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        description = data.get('description')
        kwargs = {
            'code': code,
            'discount_percent': discount_value if discount_type == 'percent' else None,
            'discount_amount': discount_value if discount_type == 'amount' else None,
            'usage_limit_total': total_limit,
            'usage_limit_per_user': per_user_limit,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'created_by': callback.from_user.id,
            'description': description,
            'applicable_plan_ids': data.get('applicable_plan_ids'),
            'segment_type': data.get('segment_type'),
            'segment_value': data.get('segment_value'),
        }
        try:
            ok = create_promo_code(**kwargs)
        except ValueError as e:
            await callback.message.edit_text(f"❌ Не удалось создать промокод: {e}", reply_markup=keyboards.create_admin_promo_menu_keyboard())
            await state.clear()
            return
        if not ok:
            await callback.message.edit_text(
                "❌ Не удалось создать промокод (возможно, код уже существует).",
                reply_markup=keyboards.create_admin_promo_menu_keyboard()
            )
            await state.clear()
            return
        await state.clear()
        await callback.message.edit_text(
            f"✅ Промокод <code>{code}</code> создан!\n\nПередайте его пользователю или опубликуйте в канале.",
            reply_markup=keyboards.create_admin_promo_menu_keyboard(),
            parse_mode='HTML'
        )

    @admin_router.callback_query(F.data == "admin_promo_list")
    async def admin_promo_list(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(promo_page=0)
        codes = list_promo_codes(include_inactive=True) or []
        text_lines = ["🎟 <b>Доступные промокоды</b>"]
        if not codes:
            text_lines.append("Пока нет созданных промокодов.")
        else:
            for promo in codes[:10]:
                text_lines.append(_format_promo_line(promo))
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=_build_promo_list_keyboard(codes, page=0),
            parse_mode='HTML'
        )

    @admin_router.callback_query(F.data.startswith("admin_promo_page_"))
    async def admin_promo_change_page(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        try:
            page = int(callback.data.split('_')[-1])
        except Exception:
            page = 0
        codes = list_promo_codes(include_inactive=True) or []
        await state.update_data(promo_page=page)
        text_lines = ["🎟 <b>Доступные промокоды</b>"]
        if not codes:
            text_lines.append("Пока нет созданных промокодов.")
        else:
            start = page * 10
            for promo in codes[start:start + 10]:
                text_lines.append(_format_promo_line(promo))
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=_build_promo_list_keyboard(codes, page=page),
            parse_mode='HTML'
        )

    @admin_router.callback_query(F.data.startswith("admin_promo_toggle_"))
    async def admin_promo_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        code = callback.data.split("admin_promo_toggle_")[-1]
        codes = list_promo_codes(include_inactive=True) or []
        target = next((p for p in codes if (p.get('code') or '').upper() == code.upper()), None)
        if not target:
            await callback.answer("Промокод не найден", show_alert=True)
            return
        new_status = not bool(target.get('is_active'))
        update_promo_code_status(code, is_active=new_status)
        await callback.answer("Статус обновлён")
        page = (await state.get_data()).get('promo_page', 0)
        codes = list_promo_codes(include_inactive=True) or []
        text_lines = ["🎟 <b>Доступные промокоды</b>"]
        if not codes:
            text_lines.append("Пока нет созданных промокодов.")
        else:
            start = page * 10
            for promo in codes[start:start + 10]:
                text_lines.append(_format_promo_line(promo))
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=_build_promo_list_keyboard(codes, page=page),
            parse_mode='HTML'
        )
