from __future__ import annotations

import asyncio
import logging
import sqlite3
from urllib.parse import quote
from datetime import date, datetime
from typing import Any

from aiogram import Router, F, types, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.core.module_loader import get_global_module_loader
from shop_bot.data_manager import database

MODULE_ID = "ramadan_tracker"
CALLBACK_PREFIX = f"mod:{MODULE_ID}:"

logger = logging.getLogger(__name__)
router = Router()


class WithdrawalStates(StatesGroup):
    waiting_proof = State()


@router.message(Command("ramadan"))
@router.message(Command("ramadan_tracker"))
async def open_ramadan_tracker(message: types.Message) -> None:
    _ensure_auto_payout(getattr(message, "bot", None))
    text = _build_menu_text(user_id=message.from_user.id)
    keyboard = _build_menu_keyboard(is_admin=_is_admin(message.from_user.id))
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}menu")
async def open_ramadan_tracker_callback(callback: types.CallbackQuery) -> None:
    _ensure_auto_payout(getattr(callback.message, "bot", None))
    text = _build_menu_text(user_id=callback.from_user.id)
    keyboard = _build_menu_keyboard(is_admin=_is_admin(callback.from_user.id))
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_menu")
async def show_adhkar_menu(callback: types.CallbackQuery) -> None:
    text = _build_adhkar_menu_text(callback.from_user.id)
    keyboard = _build_adhkar_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_morning")
async def show_adhkar_morning(callback: types.CallbackQuery) -> None:
    text = _build_adhkar_detail_text(callback.from_user.id, field="morning_adhkar")
    keyboard = _build_adhkar_detail_keyboard("morning")
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_evening")
async def show_adhkar_evening(callback: types.CallbackQuery) -> None:
    text = _build_adhkar_detail_text(callback.from_user.id, field="evening_adhkar")
    keyboard = _build_adhkar_detail_keyboard("evening")
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_morning_read")
async def mark_morning_read(callback: types.CallbackQuery) -> None:
    result = _set_adhkar_status(callback.from_user.id, field="morning_adhkar", status=1)
    await callback.answer(result, show_alert=False)
    text = _build_adhkar_detail_text(callback.from_user.id, field="morning_adhkar")
    keyboard = _build_adhkar_detail_keyboard("morning")
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_morning_missed")
async def mark_morning_missed(callback: types.CallbackQuery) -> None:
    result = _set_adhkar_status(callback.from_user.id, field="morning_adhkar", status=-1)
    await callback.answer(result, show_alert=False)
    text = _build_adhkar_detail_text(callback.from_user.id, field="morning_adhkar")
    keyboard = _build_adhkar_detail_keyboard("morning")
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_evening_read")
async def mark_evening_read(callback: types.CallbackQuery) -> None:
    result = _set_adhkar_status(callback.from_user.id, field="evening_adhkar", status=1)
    await callback.answer(result, show_alert=False)
    text = _build_adhkar_detail_text(callback.from_user.id, field="evening_adhkar")
    keyboard = _build_adhkar_detail_keyboard("evening")
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}adhkar_evening_missed")
async def mark_evening_missed(callback: types.CallbackQuery) -> None:
    result = _set_adhkar_status(callback.from_user.id, field="evening_adhkar", status=-1)
    await callback.answer(result, show_alert=False)
    text = _build_adhkar_detail_text(callback.from_user.id, field="evening_adhkar")
    keyboard = _build_adhkar_detail_keyboard("evening")
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}salawat_menu")
async def show_salawat_menu(callback: types.CallbackQuery) -> None:
    text = _build_salawat_menu_text(callback.from_user.id)
    keyboard = _build_salawat_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}salawat_add")
async def add_salawat_one(callback: types.CallbackQuery) -> None:
    _add_salawat(callback.from_user.id, amount=1)
    await callback.answer("+1 салават", show_alert=False)
    text = _build_salawat_menu_text(callback.from_user.id)
    keyboard = _build_salawat_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}taraweeh_menu")
async def show_taraweeh_menu(callback: types.CallbackQuery) -> None:
    text = _build_taraweeh_menu_text(callback.from_user.id)
    keyboard = _build_taraweeh_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}taraweeh_mosque")
async def mark_taraweeh_mosque(callback: types.CallbackQuery) -> None:
    result = _set_taraweeh(callback.from_user.id, place="mosque")
    await callback.answer(result, show_alert=False)
    text = _build_taraweeh_menu_text(callback.from_user.id)
    keyboard = _build_taraweeh_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}taraweeh_home")
async def mark_taraweeh_home(callback: types.CallbackQuery) -> None:
    result = _set_taraweeh(callback.from_user.id, place="home")
    await callback.answer(result, show_alert=False)
    text = _build_taraweeh_menu_text(callback.from_user.id)
    keyboard = _build_taraweeh_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}taraweeh_missed")
async def mark_taraweeh_missed(callback: types.CallbackQuery) -> None:
    result = _set_taraweeh(callback.from_user.id, place="missed")
    await callback.answer(result, show_alert=False)
    text = _build_taraweeh_menu_text(callback.from_user.id)
    keyboard = _build_taraweeh_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}stats_today")
async def show_today_stats(callback: types.CallbackQuery) -> None:
    text = _build_today_stats_text(callback.from_user.id)
    keyboard = _build_back_keyboard(is_admin=_is_admin(callback.from_user.id))
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}stats_total")
async def show_total_stats(callback: types.CallbackQuery) -> None:
    text = _build_total_stats_text(callback.from_user.id)
    keyboard = _build_back_keyboard(is_admin=_is_admin(callback.from_user.id))
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}top")
async def show_top(callback: types.CallbackQuery) -> None:
    _ensure_auto_payout(getattr(callback.message, "bot", None))
    text, can_withdraw = _build_top_text(callback.from_user.id)
    keyboard = _build_top_keyboard(is_admin=_is_admin(callback.from_user.id), can_withdraw=can_withdraw)
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}reward")
async def reward_top_user(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return

    ok, message = _generate_rewards(manual=True, bot=getattr(callback.message, "bot", None))
    await callback.answer(message, show_alert=not ok)
    text = _build_menu_text(user_id=callback.from_user.id)
    keyboard = _build_menu_keyboard(is_admin=True)
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}withdraw")
async def request_withdraw(callback: types.CallbackQuery) -> None:
    _ensure_auto_payout(getattr(callback.message, "bot", None))
    reward = _get_reward_for_user(callback.from_user.id)
    if not reward:
        await callback.answer("Вы не в списке победителей", show_alert=True)
        return
    support_url = _build_support_url()
    if not support_url:
        await callback.answer("Support-бот не настроен", show_alert=True)
        return
    
    # Создаем тикет в support-боте
    ticket_created = await _create_withdrawal_ticket(
        callback.from_user.id,
        callback.from_user.username,
        callback.from_user.full_name,
        reward["amount"],
        reward["period_end"],
        getattr(callback.message, "bot", None)
    )
    
    _mark_withdraw_requested(callback.from_user.id, reward["period_end"])
    
    if ticket_created:
        await callback.message.answer(
            f"✅ Запрос на вывод {reward['amount']:.2f} ₽ создан.\n"
            "Ожидайте ответа администратора в support-боте."
        )
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="Запросить вывод", url=support_url)
        await callback.message.answer(
            "Для запроса вывода нажмите кнопку ниже.",
            reply_markup=builder.as_markup(),
        )


@router.callback_query(F.data == f"{CALLBACK_PREFIX}admin_menu")
async def show_admin_menu(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    text = _build_admin_menu_text()
    keyboard = _build_admin_menu_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}admin_stats")
async def show_admin_stats(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    text = _build_admin_stats_text()
    keyboard = _build_admin_back_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}admin_top")
async def show_admin_top(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    text = _build_admin_top_text()
    keyboard = _build_admin_back_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data == f"{CALLBACK_PREFIX}admin_withdrawals")
async def show_admin_withdrawals(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    text = _build_admin_withdrawals_text()
    keyboard = _build_admin_withdrawals_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}delete_withdrawal:"))
async def delete_withdrawal_request(callback: types.CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    # callback_data format: mod:ramadan_tracker:delete_withdrawal:ID
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Неверный формат данных", show_alert=True)
        return
    
    withdrawal_id = int(parts[-1])  # Берем последний элемент - это ID
    _delete_withdrawal_request(withdrawal_id)
    
    await callback.answer("✅ Запрос удален", show_alert=True)
    
    # Обновляем список
    text = _build_admin_withdrawals_text()
    keyboard = _build_admin_withdrawals_keyboard()
    await _safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}complete_withdrawal:"))
async def complete_withdrawal_request(callback: types.CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    # callback_data format: mod:ramadan_tracker:complete_withdrawal:ID
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Неверный формат данных", show_alert=True)
        return
    
    withdrawal_id = int(parts[-1])
    
    # Предлагаем прикрепить скриншот или пропустить
    builder = InlineKeyboardBuilder()
    builder.button(text="⏩ Без скриншота", callback_data=f"{CALLBACK_PREFIX}complete_no_proof:{withdrawal_id}")
    builder.button(text="❌ Отмена", callback_data=f"{CALLBACK_PREFIX}admin_withdrawals")
    
    await state.set_state(WithdrawalStates.waiting_proof)
    await state.update_data(withdrawal_id=withdrawal_id)
    
    await callback.message.answer(
        "📸 Отправьте скриншот подтверждения выплаты или нажмите 'Без скриншота':",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}complete_no_proof:"))
async def complete_without_proof(callback: types.CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    parts = callback.data.split(":")
    withdrawal_id = int(parts[-1])
    
    _mark_withdrawal_completed(withdrawal_id, None)
    
    await state.clear()
    await callback.answer("✅ Запрос отмечен как выполнен", show_alert=True)
    
    # Возвращаемся к списку
    text = _build_admin_withdrawals_text()
    keyboard = _build_admin_withdrawals_keyboard()
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.message(WithdrawalStates.waiting_proof, F.photo)
async def handle_proof_photo(message: types.Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("Недостаточно прав")
        await state.clear()
        return
    
    data = await state.get_data()
    withdrawal_id = data.get("withdrawal_id")
    
    if not withdrawal_id:
        await message.answer("Ошибка: ID запроса не найден")
        await state.clear()
        return
    
    # Берем самое большое фото
    photo = message.photo[-1]
    file_id = photo.file_id
    
    _mark_withdrawal_completed(withdrawal_id, file_id)
    
    await state.clear()
    await message.answer("✅ Запрос отмечен как выполнен с прикрепленным скриншотом")
    
    # Показываем обновленный список
    text = _build_admin_withdrawals_text()
    keyboard = _build_admin_withdrawals_keyboard()
    await message.answer(text, reply_markup=keyboard)


def _build_menu_text(*, user_id: int) -> str:
    today = _today_str()
    daily = _get_daily_row(user_id, today)
    totals = _get_total_stats(user_id)

    morning = _format_adhkar_status(daily.get("morning_adhkar"))
    evening = _format_adhkar_status(daily.get("evening_adhkar"))
    taraweeh = _format_taraweeh_place(daily.get("taraweeh_place"))

    return (
        "Рамадан трекер\n"
        f"Дата: {today}\n\n"
        f"Утренние азкары: {morning}\n"
        f"Вечерние азкары: {evening}\n"
        f"Салаваты сегодня: {daily.get('salawat_count', 0)}\n"
        f"Таравих: {taraweeh}\n\n"
        "Итого за месяц:\n"
        f"Азкары: {totals['adhkar_total']} (утро {totals['morning_total']}, вечер {totals['evening_total']})\n"
        f"Салаваты: {totals['salawat_total']}\n"
        f"Таравих: {totals['taraweeh_total']}"
    )


def _build_today_stats_text(user_id: int) -> str:
    today = _today_str()
    daily = _get_daily_row(user_id, today)
    taraweeh = _format_taraweeh_place(daily.get("taraweeh_place"))
    return (
        "Статистика за сегодня\n"
        f"Дата: {today}\n\n"
        f"Утренние азкары: {_format_adhkar_status(daily.get('morning_adhkar'))}\n"
        f"Вечерние азкары: {_format_adhkar_status(daily.get('evening_adhkar'))}\n"
        f"Салаваты: {daily.get('salawat_count', 0)}\n"
        f"Таравих: {taraweeh}"
    )


def _build_total_stats_text(user_id: int) -> str:
    totals = _get_total_stats(user_id)
    return (
        "Статистика за весь месяц\n\n"
        f"Утренние азкары: {totals['morning_total']}\n"
        f"Вечерние азкары: {totals['evening_total']}\n"
        f"Азкары всего: {totals['adhkar_total']}\n"
        f"Салаваты: {totals['salawat_total']}\n"
        f"Таравих: {totals['taraweeh_total']}"
    )


def _build_adhkar_menu_text(user_id: int) -> str:
    today = _today_str()
    daily = _get_daily_row(user_id, today)
    return (
        "Азкары\n"
        f"Дата: {today}\n\n"
        f"Утренние: {_format_adhkar_status(daily.get('morning_adhkar'))}\n"
        f"Вечерние: {_format_adhkar_status(daily.get('evening_adhkar'))}"
    )


def _build_adhkar_detail_text(user_id: int, *, field: str) -> str:
    today = _today_str()
    daily = _get_daily_row(user_id, today)
    label = "Утренние азкары" if field == "morning_adhkar" else "Вечерние азкары"
    status = _format_adhkar_status(daily.get(field))
    return f"{label}\nДата: {today}\n\nСтатус: {status}"


def _build_salawat_menu_text(user_id: int) -> str:
    today = _today_str()
    daily = _get_daily_row(user_id, today)
    totals = _get_total_stats(user_id)
    return (
        "Салаваты\n"
        f"Дата: {today}\n\n"
        f"Сегодня: {daily.get('salawat_count', 0)}\n"
        f"Всего за месяц: {totals['salawat_total']}"
    )


def _build_taraweeh_menu_text(user_id: int) -> str:
    today = _today_str()
    daily = _get_daily_row(user_id, today)
    taraweeh = _format_taraweeh_place(daily.get("taraweeh_place"))
    return (
        "Таравих\n"
        f"Дата: {today}\n\n"
        f"Статус: {taraweeh}"
    )


def _build_top_text(user_id: int) -> tuple[str, bool]:
    settings = _get_settings()
    limit = settings.get("top_limit", 10)
    rows = _get_top_rows(limit)
    if not rows:
        return "Топ пока пуст. Начните отмечать азкары и салаваты.", False

    lines = ["Топ участников по азкарам и салаватам:\n"]
    for idx, row in enumerate(rows, start=1):
        masked = _mask_user_id(row["user_id"])
        lines.append(f"{idx}. {masked} — {row['score']}")
    can_withdraw = False
    reward = _get_reward_for_user(user_id)
    if reward:
        amount = float(reward.get("amount") or 0)
        requested = reward.get("requested_at")
        lines.append("")
        lines.append(f"Вы победитель! Приз: {amount:.2f} ₽")
        if requested:
            lines.append("Запрос на вывод уже отправлен.")
        else:
            can_withdraw = True
            lines.append("Нажмите кнопку ниже, чтобы запросить вывод.")
    return "\n".join(lines), can_withdraw


def _build_admin_menu_text() -> str:
    return "Админка модуля\n\nВыберите раздел:"


def _build_admin_stats_text() -> str:
    stats = _get_global_stats()
    return (
        "Статистика модуля (все пользователи)\n\n"
        f"Пользователей: {stats['users']}\n"
        f"Утренние азкары: {stats['morning_total']}\n"
        f"Вечерние азкары: {stats['evening_total']}\n"
        f"Азкары всего: {stats['adhkar_total']}\n"
        f"Салаваты: {stats['salawat_total']}\n"
        f"Таравих: {stats['taraweeh_total']}"
    )


def _build_admin_top_text() -> str:
    settings = _get_settings()
    limit = settings.get("top_limit", 10)
    rows = _get_top_rows(limit)
    if not rows:
        return "Топ пока пуст."
    lines = ["Топ участников (полные ID):\n"]
    for idx, row in enumerate(rows, start=1):
        lines.append(f"{idx}. {row['user_id']} — {row['score']}")
    return "\n".join(lines)


def _build_admin_withdrawals_text() -> str:
    rows = _get_withdrawal_requests()
    if not rows:
        return "История запросов пуста."
    lines = ["История запросов на вывод:\n"]
    for idx, row in enumerate(rows, start=1):
        masked_id = _mask_user_id(row['user_id'])
        status = "✅ Выполнен" if row.get('completed_at') else "⏳ Ожидает"
        proof = " 📎" if row.get('proof_file_id') else ""
        lines.append(
            f"{idx}. ID: {masked_id} | {row['amount']:.2f} ₽ | {status}{proof}\n"
            f"   Период: {row['period_end']} | Запрос: {row['requested_at']}"
        )
        if row.get('completed_at'):
            lines.append(f"   Выполнено: {row['completed_at']}")
    return "\n".join(lines)


def _build_admin_withdrawals_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    rows = _get_withdrawal_requests()
    
    # Кнопки выполнения для невыполненных запросов
    pending_rows = [r for r in rows if not r.get('completed_at')]
    for idx, row in enumerate(pending_rows, start=1):
        builder.button(
            text=f"✅ {idx}",
            callback_data=f"{CALLBACK_PREFIX}complete_withdrawal:{row['id']}"
        )
    
    # Разделитель если есть кнопки выполнения
    if pending_rows:
        builder.adjust(5)  # 5 кнопок выполнения в ряд
    
    # Кнопки удаления для всех запросов
    for idx, row in enumerate(rows, start=1):
        builder.button(
            text=f"❌ {idx}",
            callback_data=f"{CALLBACK_PREFIX}delete_withdrawal:{row['id']}"
        )
    
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}admin_menu")
    builder.adjust(5)  # По 5 кнопок в ряд
    return builder.as_markup()


def _build_menu_keyboard(*, is_admin: bool) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Азкары", callback_data=f"{CALLBACK_PREFIX}adhkar_menu")
    builder.button(text="Салаваты", callback_data=f"{CALLBACK_PREFIX}salawat_menu")
    builder.button(text="Таравих", callback_data=f"{CALLBACK_PREFIX}taraweeh_menu")
    builder.button(text="📊 Статистика дня", callback_data=f"{CALLBACK_PREFIX}stats_today")
    builder.button(text="📈 Статистика всего", callback_data=f"{CALLBACK_PREFIX}stats_total")
    builder.button(text="🏆 Топ месяца", callback_data=f"{CALLBACK_PREFIX}top")
    if is_admin:
        builder.button(text="⚙️ Админка модуля", callback_data=f"{CALLBACK_PREFIX}admin_menu")
        builder.button(text="💰 Начислить награду", callback_data=f"{CALLBACK_PREFIX}reward")
    builder.adjust(2)
    return builder.as_markup()


def _build_back_keyboard(*, is_admin: bool) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}menu")
    if is_admin:
        builder.button(text="💰 Начислить награду", callback_data=f"{CALLBACK_PREFIX}reward")
    builder.adjust(2)
    return builder.as_markup()


def _build_top_keyboard(*, is_admin: bool, can_withdraw: bool) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_withdraw:
        builder.button(text="Запросить вывод", callback_data=f"{CALLBACK_PREFIX}withdraw")
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}menu")
    if is_admin:
        builder.button(text="💰 Начислить награду", callback_data=f"{CALLBACK_PREFIX}reward")
    builder.adjust(2)
    return builder.as_markup()


def _build_adhkar_menu_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Утренние", callback_data=f"{CALLBACK_PREFIX}adhkar_morning")
    builder.button(text="Вечерние", callback_data=f"{CALLBACK_PREFIX}adhkar_evening")
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}menu")
    builder.adjust(2, 1)
    return builder.as_markup()


def _build_adhkar_detail_keyboard(period: str) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Читал", callback_data=f"{CALLBACK_PREFIX}adhkar_{period}_read")
    builder.button(text="❌ Пропустил", callback_data=f"{CALLBACK_PREFIX}adhkar_{period}_missed")
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}adhkar_menu")
    builder.adjust(2, 1)
    return builder.as_markup()


def _build_salawat_menu_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕", callback_data=f"{CALLBACK_PREFIX}salawat_add")
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}menu")
    builder.adjust(2)
    return builder.as_markup()


def _build_taraweeh_menu_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Дома", callback_data=f"{CALLBACK_PREFIX}taraweeh_home")
    builder.button(text="🕌 В мечети", callback_data=f"{CALLBACK_PREFIX}taraweeh_mosque")
    builder.button(text="❌ Пропустил", callback_data=f"{CALLBACK_PREFIX}taraweeh_missed")
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}menu")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def _build_admin_menu_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data=f"{CALLBACK_PREFIX}admin_stats")
    builder.button(text="🏆 Топ", callback_data=f"{CALLBACK_PREFIX}admin_top")
    builder.button(text="📤 Запросы на вывод", callback_data=f"{CALLBACK_PREFIX}admin_withdrawals")
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}menu")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def _build_admin_back_keyboard() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data=f"{CALLBACK_PREFIX}admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def _safe_edit(
    callback: types.CallbackQuery,
    text: str,
    keyboard: types.InlineKeyboardMarkup,
) -> Any:
    try:
        return callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return None
        return callback.message.answer(text, reply_markup=keyboard)
    except Exception:
        return callback.message.answer(text, reply_markup=keyboard)


def _today_str() -> str:
    return date.today().isoformat()


def _is_admin(user_id: int) -> bool:
    return database.is_admin(int(user_id))


def _get_settings() -> dict[str, Any]:
    loader = get_global_module_loader()
    raw = loader.get_settings_values(MODULE_ID)

    def _get(key: str, default: Any) -> Any:
        return raw.get(f"{MODULE_ID}_{key}", default)

    return {
        "end_date": str(_get("end_date", "") or ""),
        "reward_amount": _to_float(_get("reward_amount", 0)),
        "reward_enabled": _to_bool(_get("reward_enabled", False)),
        "top_limit": _to_int(_get("top_limit", 10), 10),
        "winners_count": _to_int(_get("winners_count", 3), 3),
        "prize_shares": str(_get("prize_shares", "") or "").strip(),
    }


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _get_daily_row(user_id: int, day: str) -> dict[str, Any]:
    _ensure_daily_row(user_id, day)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT morning_adhkar, evening_adhkar, salawat_count, taraweeh_place
              FROM ramadan_tracker_daily
             WHERE user_id = ? AND date = ?
            """,
            (int(user_id), day),
        )
        row = cursor.fetchone()
        return dict(row) if row else {
            "morning_adhkar": 0,
            "evening_adhkar": 0,
            "salawat_count": 0,
            "taraweeh_place": None,
        }


def _ensure_daily_row(user_id: int, day: str) -> None:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO ramadan_tracker_daily (user_id, date) VALUES (?, ?)",
            (int(user_id), day),
        )
        conn.commit()


def _set_adhkar_status(user_id: int, *, field: str, status: int) -> str:
    if field not in {"morning_adhkar", "evening_adhkar"}:
        return "Неверный тип азкара"
    if status not in {1, -1}:
        return "Неверный статус"
    today = _today_str()
    _ensure_daily_row(user_id, today)
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE ramadan_tracker_daily
               SET {field} = ?, updated_at = CURRENT_TIMESTAMP
             WHERE user_id = ? AND date = ?
            """,
            (int(status), int(user_id), today),
        )
        conn.commit()
    return "Отмечено"


def _add_salawat(user_id: int, *, amount: int) -> None:
    today = _today_str()
    _ensure_daily_row(user_id, today)
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE ramadan_tracker_daily
               SET salawat_count = salawat_count + ?, updated_at = CURRENT_TIMESTAMP
             WHERE user_id = ? AND date = ?
            """,
            (int(amount), int(user_id), today),
        )
        conn.commit()




def _set_taraweeh(user_id: int, *, place: str) -> str:
    if place not in {"mosque", "home", "missed"}:
        return "Неверный вариант"

    today = _today_str()
    _ensure_daily_row(user_id, today)
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT taraweeh_place FROM ramadan_tracker_daily WHERE user_id = ? AND date = ?",
            (int(user_id), today),
        )
        row = cursor.fetchone()
        current = row[0] if row else None
        if current == place:
            return "Уже отмечено"

        cursor.execute(
            """
            UPDATE ramadan_tracker_daily
               SET taraweeh_place = ?, updated_at = CURRENT_TIMESTAMP
             WHERE user_id = ? AND date = ?
            """,
            (place, int(user_id), today),
        )
        conn.commit()
        return "Отмечено"


def _get_total_stats(user_id: int) -> dict[str, int]:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN morning_adhkar = 1 THEN 1 ELSE 0 END), 0) AS morning_total,
                COALESCE(SUM(CASE WHEN evening_adhkar = 1 THEN 1 ELSE 0 END), 0) AS evening_total,
                COALESCE(SUM(salawat_count), 0) AS salawat_total,
                COALESCE(SUM(CASE WHEN taraweeh_place IN ('mosque', 'home') THEN 1 ELSE 0 END), 0) AS taraweeh_total
            FROM ramadan_tracker_daily
            WHERE user_id = ?
            """,
            (int(user_id),),
        )
        row = cursor.fetchone() or (0, 0, 0, 0)
        return {
            "morning_total": int(row[0]),
            "evening_total": int(row[1]),
            "salawat_total": int(row[2]),
            "taraweeh_total": int(row[3]),
            "adhkar_total": int(row[0]) + int(row[1]),
        }


def _get_global_stats() -> dict[str, int]:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COALESCE(COUNT(DISTINCT user_id), 0) AS users_total,
                COALESCE(SUM(CASE WHEN morning_adhkar = 1 THEN 1 ELSE 0 END), 0) AS morning_total,
                COALESCE(SUM(CASE WHEN evening_adhkar = 1 THEN 1 ELSE 0 END), 0) AS evening_total,
                COALESCE(SUM(salawat_count), 0) AS salawat_total,
                COALESCE(SUM(CASE WHEN taraweeh_place IN ('mosque', 'home') THEN 1 ELSE 0 END), 0) AS taraweeh_total
            FROM ramadan_tracker_daily
            """
        )
        row = cursor.fetchone() or (0, 0, 0, 0, 0)
        return {
            "users": int(row[0]),
            "morning_total": int(row[1]),
            "evening_total": int(row[2]),
            "salawat_total": int(row[3]),
            "taraweeh_total": int(row[4]),
            "adhkar_total": int(row[1]) + int(row[2]),
        }


def _get_top_rows(limit: int) -> list[dict[str, Any]]:
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                user_id,
                COALESCE(
                    SUM(
                        CASE WHEN morning_adhkar = 1 THEN 1 ELSE 0 END
                        + CASE WHEN evening_adhkar = 1 THEN 1 ELSE 0 END
                        + salawat_count
                    ),
                    0
                ) AS score
            FROM ramadan_tracker_daily
            GROUP BY user_id
            ORDER BY score DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [dict(row) for row in cursor.fetchall()]


def _ensure_auto_payout(bot: Any | None = None) -> None:
    settings = _get_settings()
    if not settings.get("reward_enabled"):
        return
    end_date_raw = settings.get("end_date", "")
    if not end_date_raw:
        return
    try:
        end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return
    if date.today() < end_date:
        return
    if _period_generated(end_date_raw):
        return
    _generate_rewards(manual=False, bot=bot)


def _generate_rewards(*, manual: bool, bot: Any | None = None) -> tuple[bool, str]:
    settings = _get_settings()
    if not settings.get("reward_enabled"):
        return False, "Награда отключена в настройках"

    end_date_raw = settings.get("end_date", "")
    if not end_date_raw:
        return False, "Не задана дата окончания"

    try:
        end_date = datetime.strptime(end_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return False, "Неверный формат даты окончания"

    if date.today() < end_date and manual:
        return False, "Рано: период еще не завершен"

    if _period_generated(end_date_raw):
        return False, "Награда за этот период уже распределена"

    prize_fund = float(settings.get("reward_amount", 0) or 0)
    if prize_fund <= 0:
        return False, "Призовой фонд должен быть больше нуля"

    winners_count = max(int(settings.get("winners_count") or 1), 1)
    top_rows = _get_top_rows(winners_count)
    if not top_rows:
        return False, "Нет данных для начисления"

    shares = _parse_prize_shares(settings.get("prize_shares", ""), len(top_rows))
    amounts = _allocate_prize_fund(prize_fund, shares)

    _save_reward_period(end_date_raw, prize_fund, len(top_rows))
    _save_reward_users(end_date_raw, top_rows, shares, amounts)
    _notify_winners(bot, end_date_raw, top_rows, amounts)
    return True, "Награда распределена"


def _reward_already_given(period_end: str) -> bool:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM ramadan_tracker_rewards WHERE period_end = ?",
            (period_end,),
        )
        return cursor.fetchone() is not None


def _save_reward(period_end: str, user_id: int, amount: float) -> None:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO ramadan_tracker_rewards (period_end, rewarded_user_id, amount)
            VALUES (?, ?, ?)
            """,
            (period_end, int(user_id), float(amount)),
        )
        conn.commit()


def _period_generated(period_end: str) -> bool:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM ramadan_tracker_reward_periods WHERE period_end = ?",
            (period_end,),
        )
        return cursor.fetchone() is not None


def _save_reward_period(period_end: str, prize_fund: float, winners_count: int) -> None:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO ramadan_tracker_reward_periods
                (period_end, prize_fund, winners_count)
            VALUES (?, ?, ?)
            """,
            (period_end, float(prize_fund), int(winners_count)),
        )
        conn.commit()


def _save_reward_users(period_end: str, rows: list[dict[str, Any]], shares: list[float], amounts: list[float]) -> None:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        for row, share, amount in zip(rows, shares, amounts, strict=False):
            cursor.execute(
                """
                INSERT OR REPLACE INTO ramadan_tracker_reward_users
                    (period_end, user_id, score, share, amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (period_end, int(row["user_id"]), int(row.get("score", 0) or 0), float(share), float(amount)),
            )
        conn.commit()


def _notify_winners(bot: Any | None, period_end: str, winners: list[dict[str, Any]], amounts: list[float]) -> None:
    if not bot:
        return
    support_url = _build_support_url()
    for idx, row in enumerate(winners):
        user_id = int(row.get("user_id") or 0)
        if not user_id:
            continue
        amount = amounts[idx] if idx < len(amounts) else 0.0
        text = (
            "Поздравляем! Вы в числе победителей Рамадан трекера.\n"
            f"Период: {period_end}\n"
            f"Место: {idx + 1}\n"
            f"Приз: {amount:.2f} ₽\n\n"
            "Откройте /ramadan → Топ месяца, чтобы запросить вывод."
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop:
            reply_markup = None
            if support_url:
                builder = InlineKeyboardBuilder()
                builder.button(text="Запросить вывод", url=support_url)
                reply_markup = builder.as_markup()
            loop.create_task(bot.send_message(user_id, text, reply_markup=reply_markup))


def _get_reward_for_user(user_id: int) -> dict[str, Any] | None:
    settings = _get_settings()
    end_date_raw = settings.get("end_date", "")
    if not end_date_raw:
        return None
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT period_end, amount, requested_at
            FROM ramadan_tracker_reward_users
            WHERE period_end = ? AND user_id = ?
            """,
            (end_date_raw, int(user_id)),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def _get_withdrawal_requests(limit: int = 50) -> list[dict[str, Any]]:
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, period_end, user_id, amount, requested_at, completed_at, proof_file_id
            FROM ramadan_tracker_reward_users
            WHERE requested_at IS NOT NULL
            ORDER BY 
                CASE WHEN completed_at IS NULL THEN 0 ELSE 1 END,
                requested_at DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [dict(row) for row in cursor.fetchall()]


def _delete_withdrawal_request(withdrawal_id: int) -> None:
    """Удаляет запрос на вывод по ID."""
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE ramadan_tracker_reward_users
            SET requested_at = NULL
            WHERE id = ?
            """,
            (withdrawal_id,),
        )
        conn.commit()


def _mark_withdrawal_completed(withdrawal_id: int, proof_file_id: str | None) -> None:
    """Отмечает запрос на вывод как выполненный с опциональным скриншотом."""
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE ramadan_tracker_reward_users
            SET completed_at = CURRENT_TIMESTAMP, proof_file_id = ?
            WHERE id = ?
            """,
            (proof_file_id, withdrawal_id),
        )
        conn.commit()


def _mark_withdraw_requested(user_id: int, period_end: str) -> None:
    with sqlite3.connect(database.DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE ramadan_tracker_reward_users
               SET requested_at = CURRENT_TIMESTAMP
             WHERE period_end = ? AND user_id = ? AND requested_at IS NULL
            """,
            (period_end, int(user_id)),
        )
        conn.commit()


def _format_taraweeh_place(place: Any) -> str:
    if place == "mosque":
        return "в мечети"
    if place == "home":
        return "дома"
    if place == "missed":
        return "пропущен"
    return "—"


def _format_adhkar_status(value: Any) -> str:
    if value == 1:
        return "читал"
    if value == -1:
        return "пропустил"
    return "—"


def _parse_prize_shares(raw: str, winners_count: int) -> list[float]:
    if raw:
        parts = [p.strip() for p in raw.replace("/", ",").split(",") if p.strip()]
        values: list[float] = []
        for part in parts:
            try:
                values.append(float(part))
            except ValueError:
                continue
        if values:
            values = values[:winners_count]
            if len(values) < winners_count:
                values.extend([0.0] * (winners_count - len(values)))
            total = sum(values)
            if total > 0:
                return [v / total for v in values]
    weights = [float(winners_count - idx) for idx in range(winners_count)]
    total = sum(weights) or 1.0
    return [w / total for w in weights]


def _allocate_prize_fund(prize_fund: float, shares: list[float]) -> list[float]:
    amounts: list[float] = []
    remaining = float(prize_fund)
    for idx, share in enumerate(shares):
        if idx == len(shares) - 1:
            amounts.append(round(remaining, 2))
        else:
            amount = round(prize_fund * share, 2)
            amounts.append(amount)
            remaining -= amount
    return amounts


def _build_support_url() -> str | None:
    raw = (database.get_setting("support_bot_username") or "").strip()
    if not raw:
        return None
    username = raw[1:] if raw.startswith("@") else raw
    if not username:
        return None
    text = quote("Запрос вывода выигрыша")
    return f"https://t.me/{username}?text={text}"


async def _create_withdrawal_ticket(
    user_id: int,
    username: str | None,
    full_name: str,
    amount: float,
    period_end: str,
    bot: Any
) -> bool:
    """Создает тикет в support-боте для запроса на вывод выигрыша."""
    try:
        # Работаем напрямую с БД - создаем тикет
        with sqlite3.connect(database.DB_FILE) as conn:
            cursor = conn.cursor()
            
            # Проверяем, есть ли уже открытый тикет
            cursor.execute(
                "SELECT ticket_id FROM support_tickets WHERE user_id = ? AND status = 'open' ORDER BY updated_at DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            
            # Создаем новый тикет
            subject = f"⭐ Запрос на вывод выигрыша {amount:.2f} ₽"
            created_new = False
            
            if row:
                ticket_id = row[0]
            else:
                cursor.execute(
                    "INSERT INTO support_tickets (user_id, subject) VALUES (?, ?)",
                    (user_id, subject)
                )
                ticket_id = cursor.lastrowid
                created_new = True
            
            if not ticket_id:
                logger.warning(f"Failed to create support ticket for user {user_id}")
                return False
            
            # Добавляем сообщение в тикет
            message_text = (
                f"Запрос на вывод выигрыша\n"
                f"Сумма: {amount:.2f} ₽\n"
                f"Период: {period_end}\n"
                f"Трекер: Рамадан"
            )
            cursor.execute(
                "INSERT INTO support_messages (ticket_id, sender, content) VALUES (?, ?, ?)",
                (ticket_id, "user", message_text)
            )
            conn.commit()
        
        # Если настроен форум поддержки, создаем топик через support-бота
        if created_new:
            support_forum_chat_id = database.get_setting("support_forum_chat_id")
            support_bot_token = database.get_setting("support_bot_token")
            
            if support_forum_chat_id and support_bot_token:
                try:
                    # Создаем временный инстанс support-бота
                    support_bot = Bot(token=support_bot_token)
                    
                    chat_id = int(support_forum_chat_id)
                    author_tag = f"@{username}" if username else full_name or str(user_id)
                    
                    # Создаем топик в форуме
                    topic_name = f"#{ticket_id} 🏆 Вывод {amount:.2f}₽ • от {author_tag}"
                    forum_topic = await support_bot.create_forum_topic(chat_id=chat_id, name=topic_name)
                    thread_id = forum_topic.message_thread_id
                    
                    # Обновляем тикет с информацией о топике
                    with sqlite3.connect(database.DB_FILE) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE support_tickets SET forum_chat_id = ?, message_thread_id = ? WHERE ticket_id = ?",
                            (str(chat_id), int(thread_id), ticket_id)
                        )
                        conn.commit()
                    
                    # Отправляем уведомление в топик
                    header = (
                        f"🏆 Запрос на вывод выигрыша\n"
                        f"Тикет: #{ticket_id}\n"
                        f"Пользователь: {author_tag} (ID: {user_id})\n"
                        f"Сумма: {amount:.2f} ₽\n"
                        f"Период: {period_end}\n"
                        f"Трекер: Рамадан трекер\n\n"
                        f"📝 {message_text}"
                    )
                    await support_bot.send_message(
                        chat_id=chat_id,
                        text=header,
                        message_thread_id=thread_id
                    )
                    
                    # Закрываем сессию support-бота
                    await support_bot.session.close()
                    
                    logger.info(f"Created forum topic for withdrawal ticket #{ticket_id}")
                except Exception as e:
                    logger.warning(f"Failed to create forum topic for ticket {ticket_id}: {e}")
        
        logger.info(f"Created withdrawal ticket #{ticket_id} for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating withdrawal ticket: {e}")
        return False


def _mask_user_id(user_id: int) -> str:
    raw = str(user_id)
    if len(raw) <= 4:
        return "***"
    return f"{raw[:4]}***"
