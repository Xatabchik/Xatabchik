"""
Редактируемый referral_share_text и корректный URL для t.me/share
(пробелы как %20, не +).
"""
from urllib.parse import parse_qs, unquote, urlparse

from conftest import temp_db  # noqa: F401


def test_telegram_share_url_uses_percent20_not_plus():
    from shop_bot.bot import handlers

    url = handlers._telegram_share_url(
        "https://t.me/TestBot?start=ref_1",
        "🌐Обход глушилок и блокировок на любом устройстве! 😊",
    )
    assert " " not in url
    # quote_plus давал бы «Обход+глушилок» — Telegram оставляет плюсы как есть
    assert "+глушилок+" not in url
    assert "%20" in url

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "t.me"
    assert parsed.path == "/share/url"
    qs = parse_qs(parsed.query)
    assert qs["url"] == ["https://t.me/TestBot?start=ref_1"]
    assert qs["text"] == ["🌐Обход глушилок и блокировок на любом устройстве! 😊"]


def test_referral_share_text_from_settings(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("referral_share_text", "Мой кастомный текст для шаринга")
    assert handlers._referral_share_text() == "Мой кастомный текст для шаринга"


def test_referral_share_text_falls_back_to_default(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("referral_share_text", "   ")
    assert handlers._referral_share_text() == handlers.DEFAULT_REFERRAL_SHARE_TEXT


def test_referral_info_api_returns_share_text(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers as web_handlers
    from conftest import insert_user

    insert_user(database.DB_FILE, telegram_id=88001, username="shareuser")
    database.update_setting("referral_share_text", "Кастомный шаринг")
    database.update_setting("telegram_bot_username", "TestVpnBot")

    client = TestClient(web_handlers.app)
    resp = client.post("/api/user/referral-info", json={"user_id": 88001})
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("share_text") == "Кастомный шаринг"
