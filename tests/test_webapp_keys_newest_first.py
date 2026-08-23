"""Страница ключей WebApp: новые сверху, без тизера настройки, «Подключить» после покупки."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

USER_ID = 94001


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _insert_key(
    db_path: Path,
    *,
    user_id: int,
    email: str,
    created_at: str,
    expire_at: str,
    user_key_name: str,
    subscription_url: str,
) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, user_key_name
            ) VALUES (?, 'TestHost', ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, email, subscription_url, expire_at, created_at, created_at, user_key_name),
        )
        key_id = cur.lastrowid
        conn.commit()
    return key_id


def _seed_two_keys(database):
    """Старый ключ истекает раньше нового — сортировка по expiry и по покупке расходятся."""
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="keysuser")
    old_id = _insert_key(
        database.DB_FILE,
        user_id=USER_ID,
        email="old-key@bot.local",
        created_at="2025-01-01 12:00:00",
        expire_at="2028-01-01 12:00:00",
        user_key_name="Старый ключ",
        subscription_url="https://sub.example/old",
    )
    new_id = _insert_key(
        database.DB_FILE,
        user_id=USER_ID,
        email="new-key@bot.local",
        created_at="2026-08-20 18:00:00",
        expire_at="2029-12-01 12:00:00",
        user_key_name="Новый ключ",
        subscription_url="https://sub.example/new",
    )
    return old_id, new_id


def test_sort_keys_newest_first_uses_created_at_then_key_id():
    from shop_bot.webapp.handlers import _sort_keys_newest_first

    keys = [
        {"key_id": 1, "created_at": "2025-01-01 00:00:00", "user_key_name": "oldest"},
        {"key_id": 3, "created_at": "2026-08-01 00:00:00", "user_key_name": "newest"},
        {"key_id": 2, "created_at": "2026-08-01 00:00:00", "user_key_name": "same-day-lower-id"},
    ]
    ordered = _sort_keys_newest_first(keys)
    assert [k["key_id"] for k in ordered] == [3, 2, 1]


def test_profile_keys_html_renders_newest_card_first():
    from shop_bot.webapp.handlers import _get_profile_keys_html

    html = _get_profile_keys_html(
        [
            {
                "key_id": 30,
                "created_at": "2026-08-20 18:00:00",
                "expiry_date": "2029-12-01 12:00:00",
                "user_key_name": "Новый ключ",
                "subscription_url": "https://sub.example/new",
            },
            {
                "key_id": 10,
                "created_at": "2025-01-01 12:00:00",
                "expiry_date": "2028-01-01 12:00:00",
                "user_key_name": "Старый ключ",
                "subscription_url": "https://sub.example/old",
            },
        ]
    )
    assert html.find("Новый ключ") < html.find("Старый ключ")
    assert 'onclick="openLinkSafe(\'https://sub.example/new\')"' in html
    assert ">Подключить</span>" in html


def test_keys_page_html_has_connect_cta_and_no_setup_teaser():
    html = Path("src/shop_bot/webapp/app.html").read_text(encoding="utf-8")
    keys_start = html.index('id="keys-page"')
    keys_end = html.index("======= Конец КЛЮЧИ")
    keys_chunk = html[keys_start:keys_end]
    assert "Настройка подключения" not in keys_chunk
    assert "Инструкции для ваших устройств" not in keys_chunk
    assert "hash='setup'" not in keys_chunk

    success_start = html.index('id="payment-step-success"')
    success_end = html.index('id="toast-container"')
    success_chunk = html[success_start:success_end]
    assert 'id="success-connect-btn"' in success_chunk
    assert "openLinkSafe" in success_chunk
    assert "Подключить" in success_chunk
    assert "Как подключиться" not in success_chunk


def test_keys_page_renders_newest_key_first(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    database.update_setting("webapp_enabled", "true")
    old_id, new_id = _seed_two_keys(database)
    token = issue_auth_token(USER_ID)

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)

    resp = _client().get("/", params={"token": token})
    assert resp.status_code == 200
    body = resp.text
    assert "Webapp is disabled" not in body

    container_start = body.index('id="profile-keys-list-container"')
    container_end = body.index('id="profile-keys-pagination"')
    list_html = body[container_start:container_end]
    assert list_html.find("Новый ключ") < list_html.find("Старый ключ")
    assert f"goToRenewKey({new_id})" in list_html
    assert f"goToRenewKey({old_id})" in list_html

    assert "Настройка подключения" not in body
    assert "Инструкции для ваших устройств" not in body
    assert "Как подключиться" not in body
    assert 'id="success-connect-btn"' in body
    assert ">Подключить</span>" in body


def test_user_status_returns_newest_key_first(temp_db):
    from shop_bot.data_manager import database

    _seed_two_keys(database)
    token = issue_auth_token(USER_ID)

    resp = _client().get("/api/user-status", params={"token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    names = [k.get("user_key_name") or k.get("name") for k in data["keys"]]
    assert names[0] == "Новый ключ"
    assert names[1] == "Старый ключ"
    assert data["keys"][0]["sub_url"] == "https://sub.example/new"
