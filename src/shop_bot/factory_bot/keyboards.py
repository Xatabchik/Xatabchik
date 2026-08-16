from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu(*, show_cabinet: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    # Owner-only partner cabinet should be the very first (top) button
    if show_cabinet:
        b.button(text="📊 Кабинет партнера", callback_data="factory_cabinet")

    b.button(text="🤖 Создать бот", callback_data="factory_create_bot")
    b.button(text="ℹ️ Инструкция", callback_data="factory_help")

    if show_cabinet:
        b.adjust(1, 1, 1)
    else:
        b.adjust(1, 1)

    return b.as_markup()

def cabinet_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗑 Удалить моего бота", callback_data="factory_del_self")
    b.button(text="💸 Запросить вывод", callback_data="partner_withdraw")
    b.button(text="⬅️ Назад", callback_data="partner_cabinet")
    b.adjust(1, 1, 1)
    return b.as_markup()

def delete_bot_confirm(bot_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"factory_del_yes:{bot_id}")
    b.button(text="❌ Отмена", callback_data="partner_cabinet")
    b.adjust(1, 1)
    return b.as_markup()

def back_only() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="factory_back")
    b.adjust(1)
    return b.as_markup()
