"""Вкладки «Личные» / «Подарочные»: строгое разделение по tag и is_activated."""
from __future__ import annotations

import sqlite3
from html.parser import HTMLParser
from pathlib import Path

from conftest import insert_gift_key, insert_user, issue_auth_token, temp_db  # noqa: F401
from webapp_frontend_src import mini_app_js

USER_ID = 16601


class _CardProbe(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names: list[str] = []
        self.ids: list[str] = []
        self._capture = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "div" and ad.get("data-key-id"):
            self.ids.append(ad["data-key-id"])
            if ad.get("data-key-name"):
                self.names.append(ad["data-key-name"])

    def error(self, message):
        pass


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _personal_chunk(html: str) -> str:
    start = html.index('id="profile-keys-list-container"')
    end = html.index('id="profile-keys-pagination"')
    return html[start:end]


def _insert_named_key(db_path: Path, *, user_id: int, name: str, email: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, user_key_name, tag
            ) VALUES (?, 'TabHost', ?, ?, 'https://sub.example/tab',
                      datetime('now', '+30 days'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, '')
            """,
            (user_id, email, email, name),
        )
        key_id = cur.lastrowid
        conn.commit()
    return int(key_id)


def _name_gift_key(db_path: Path, key_id: int, name: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE vpn_keys SET user_key_name = ? WHERE key_id = ?", (name, key_id))
        conn.commit()


def _seed_three_kinds(database):
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="tab-sep")
    ordinary_id = _insert_named_key(
        database.DB_FILE, user_id=USER_ID, name="Обычный ключ", email="ordinary@bot.local"
    )
    _, unact_key_id = insert_gift_key(database.DB_FILE, from_user_id=USER_ID, gift_code="unact-sep")
    _name_gift_key(database.DB_FILE, unact_key_id, "Неактивированный подарок")
    _, act_key_id = insert_gift_key(database.DB_FILE, from_user_id=USER_ID, gift_code="act-sep")
    _name_gift_key(database.DB_FILE, act_key_id, "Активированный подарок")
    from shop_bot.webapp.handlers import _activate_gift_for_user

    result = _activate_gift_for_user(USER_ID, "act-sep")
    assert result.get("ok") is True, result
    return ordinary_id, unact_key_id, act_key_id


def test_personal_keys_helper_uses_existing_gift_tag():
    from shop_bot.webapp.handlers import _is_unactivated_gift_key, _personal_keys

    keys = [
        {"key_id": 1, "tag": "", "user_key_name": "a"},
        {"key_id": 2, "tag": "user_gift", "user_key_name": "b"},
        {"key_id": 3, "tag": "gift", "user_key_name": "c"},
        {"key_id": 4, "tag": None, "user_key_name": "d"},
        {"key_id": 5, "tag": "trial", "user_key_name": "e"},
    ]
    assert _is_unactivated_gift_key(keys[1]) is True
    assert _is_unactivated_gift_key(keys[2]) is True
    personal = _personal_keys(keys)
    assert [k["key_id"] for k in personal] == [1, 4, 5]


def test_tabs_split_ordinary_unactivated_and_self_activated(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    database.update_setting("webapp_enabled", "true")
    ordinary_id, unact_key_id, act_key_id = _seed_three_kinds(database)
    token = issue_auth_token(USER_ID)

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)

    client = _client()
    page = client.get("/", params={"token": token})
    assert page.status_code == 200
    personal = _personal_chunk(page.text)
    probe = _CardProbe()
    probe.feed(personal)
    assert "Обычный ключ" in probe.names
    assert "Активированный подарок" in probe.names
    assert "Неактивированный подарок" not in probe.names
    assert str(ordinary_id) in probe.ids
    assert str(act_key_id) in probe.ids
    assert str(unact_key_id) not in probe.ids
    assert "Неактивированный подарок" not in personal

    gifts = client.post("/api/user/gifts", json={"token": token, "user_id": USER_ID})
    assert gifts.status_code == 200
    payload = gifts.json()
    assert payload.get("ok") is True
    codes = [g.get("gift_code") for g in payload.get("gifts") or []]
    assert codes == ["unact-sep"]
    html = "".join(g.get("card_html") or "" for g in payload["gifts"])
    assert "Неактивированный подарок" in html
    assert "Обычный ключ" not in html
    assert "Активированный подарок" not in html

    status = client.get("/api/user-status", params={"token": token})
    names = [k.get("name") for k in status.json().get("keys") or []]
    assert "Обычный ключ" in names
    assert "Активированный подарок" in names
    assert "Неактивированный подарок" not in names


def test_each_tab_paginates_separately(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="tab-pages")
    for i in range(7):
        _insert_named_key(
            database.DB_FILE,
            user_id=USER_ID,
            name=f"Личный {i}",
            email=f"personal-{i}@bot.local",
        )
    for i in range(7):
        _, kid = insert_gift_key(
            database.DB_FILE, from_user_id=USER_ID, gift_code=f"gift-page-{i}"
        )
        _name_gift_key(database.DB_FILE, kid, f"Подарок {i}")

    js = mini_app_js()
    assert "const PROFILE_KEYS_PAGE_SIZE = 5" in js
    assert "const GIFTS_PAGE_SIZE = 5" in js

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)
    token = issue_auth_token(USER_ID)
    client = _client()
    page = client.get("/", params={"token": token})
    personal = _personal_chunk(page.text)
    probe = _CardProbe()
    probe.feed(personal)
    assert len(probe.ids) == 7
    assert all(name.startswith("Личный ") for name in probe.names)
    assert not any(name.startswith("Подарок ") for name in probe.names)
    assert "Подарок 0" not in personal

    gifts = client.post("/api/user/gifts", json={"token": token, "user_id": USER_ID}).json()
    assert gifts.get("ok") is True
    assert len(gifts["gifts"]) == 7
    assert {g["gift_code"] for g in gifts["gifts"]} == {f"gift-page-{i}" for i in range(7)}
    combined = "".join(g.get("card_html") or "" for g in gifts["gifts"])
    assert "Личный 0" not in combined
    assert "Подарок 0" in combined
