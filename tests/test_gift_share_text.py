"""Редактируемый gift_share_text для кнопки «Поделиться» подарком."""
from conftest import temp_db  # noqa: F401


def test_gift_share_text_from_settings(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("gift_share_text", "Кастомный текст подарка")
    assert handlers._gift_share_text() == "Кастомный текст подарка"


def test_gift_share_text_falls_back_to_default(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("gift_share_text", "  ")
    assert handlers._gift_share_text() == handlers.DEFAULT_GIFT_SHARE_TEXT


def test_gift_share_text_in_settings_keys_and_content_ui():
    from pathlib import Path
    from shop_bot.webhook_server.app import ALL_SETTINGS_KEYS

    assert "gift_share_text" in ALL_SETTINGS_KEYS
    html = Path("src/shop_bot/webhook_server/templates/settings.html").read_text(encoding="utf-8")
    assert 'name="gift_share_text"' in html
    assert "gift_share_text" in html
