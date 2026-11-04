"""Кнопка «Найти ключ» должна получить клавиатуру отмены.

Тело create_search_keys_cancel_keyboard когда-то оказалось после return
внутри create_main_reset_payment_method_keyboard, и поиск падал с
AttributeError.
"""
from shop_bot.bot.keyboards import (
    create_main_reset_payment_method_keyboard,
    create_search_keys_cancel_keyboard,
)


def _callbacks(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_search_keys_cancel_keyboard_is_a_single_cancel_button():
    markup = create_search_keys_cancel_keyboard()
    buttons = [button for row in markup.inline_keyboard for button in row]
    assert len(buttons) == 1
    assert buttons[0].text == "❌ Отмена"
    assert buttons[0].callback_data == "cancel_search_keys"


def test_main_reset_payment_keyboard_does_not_include_key_search_cancel():
    markup = create_main_reset_payment_method_keyboard({})
    assert "cancel_search_keys" not in _callbacks(markup)
    assert "back_to_main_menu" in _callbacks(markup)
