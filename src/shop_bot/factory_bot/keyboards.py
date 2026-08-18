from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def cabinet_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💸 Запросить вывод", callback_data="partner_withdraw")
    b.button(text="🗑 Удалить моего бота", callback_data="factory_del_self")
    b.button(text="⬅️ Назад", callback_data="partner_cabinet")
    b.adjust(1, 1, 1)
    return b.as_markup()

def delete_bot_confirm(bot_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"factory_del_yes:{bot_id}")
    b.button(text="❌ Отмена", callback_data="partner_cabinet")
    b.adjust(1, 1)
    return b.as_markup()
