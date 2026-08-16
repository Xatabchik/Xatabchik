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
    b.button(text="🤖 Мои боты", callback_data="factory_my_bots")
    b.button(text="💸 Запросить вывод", callback_data="factory_withdraw")
    b.button(text="⬅️ Назад", callback_data="factory_back")
    b.adjust(1, 1, 1)
    return b.as_markup()

def my_bots_menu(bots: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bot in bots:
        bot_id = int(bot.get("id") or 0)
        if bot_id <= 0:
            continue
        b.button(text=f"🗑 Удалить #{bot_id}", callback_data=f"factory_del:{bot_id}")
    b.button(text="⬅️ Назад", callback_data="factory_cabinet")
    b.adjust(1)
    return b.as_markup()

def delete_bot_confirm(bot_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"factory_del_yes:{bot_id}")
    b.button(text="❌ Отмена", callback_data="factory_my_bots")
    b.adjust(1, 1)
    return b.as_markup()

def back_only() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="factory_back")
    b.adjust(1)
    return b.as_markup()
