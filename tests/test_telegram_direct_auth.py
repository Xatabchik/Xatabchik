"""
Регрессионные тесты для закрытия CWE-306 на POST /api/auth/telegram-direct.

Раньше эндпоинт принимал голый user_id и выдавал persistent auth_token.
Теперь требуется HMAC-валидный Telegram WebApp initData; user_id берётся
только из подписанных данных.
"""
import json
import sqlite3
import time
from urllib.parse import urlencode

import hmac
import hashlib

from conftest import (  # noqa: F401
    FAKE_BOT_TOKEN,
    app_client,
    insert_user,
    make_telegram_init_data,
    temp_db,
)


def _make_init_data_with_auth_date(user_id: int, auth_date: int, *, username: str = "tguser") -> str:
    user_json = json.dumps(
        {"id": user_id, "first_name": "Test", "username": username},
        separators=(",", ":"),
    )
    params = {"auth_date": str(auth_date), "query_id": "AAA", "user": user_json}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", FAKE_BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = signature
    return urlencode(params)


def test_telegram_direct_rejects_bare_user_id_without_signature(app_client, temp_db):
    """Старый контракт {user_id: N} больше не принимается — 401/422, токен не пишется."""
    from shop_bot.data_manager import database

    victim_id = 555001
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim")
    assert database.get_auth_token_by_user_id(victim_id) is None

    resp = app_client.post("/api/auth/telegram-direct", json={"user_id": victim_id})
    assert resp.status_code in (401, 403, 422)
    assert database.get_auth_token_by_user_id(victim_id) is None


def test_telegram_direct_rejects_missing_init_data(app_client, temp_db):
    from shop_bot.data_manager import database

    victim_id = 555002
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim2")

    resp = app_client.post("/api/auth/telegram-direct", json={})
    assert resp.status_code in (401, 403, 422)
    assert database.get_auth_token_by_user_id(victim_id) is None


def test_telegram_direct_rejects_invalid_signature_and_does_not_overwrite_token(app_client, temp_db):
    from shop_bot.data_manager import database

    victim_id = 555003
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim3")
    original = "pre-existing-token-555003"
    database.update_user_auth_token(victim_id, original)

    # Корректный формат, но чужой/битый hash
    init_data = make_telegram_init_data(victim_id)
    tampered = init_data.rsplit("hash=", 1)[0] + "hash=" + ("0" * 64)

    resp = app_client.post("/api/auth/telegram-direct", json={"init_data": tampered})
    assert resp.status_code == 401
    body = resp.json()
    assert body.get("ok") is False
    assert "token" not in body or not body.get("token")
    assert database.get_auth_token_by_user_id(victim_id) == original


def test_telegram_direct_rejects_expired_auth_date(app_client, temp_db):
    from shop_bot.data_manager import database

    victim_id = 555004
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim4")
    original = "pre-existing-token-555004"
    database.update_user_auth_token(victim_id, original)

    expired = _make_init_data_with_auth_date(victim_id, int(time.time()) - (25 * 60 * 60))
    resp = app_client.post("/api/auth/telegram-direct", json={"init_data": expired})
    assert resp.status_code == 401
    assert database.get_auth_token_by_user_id(victim_id) == original


def test_telegram_direct_accepts_valid_init_data_for_registered_user(app_client, temp_db):
    from shop_bot.data_manager import database

    user_id = 555010
    insert_user(database.DB_FILE, telegram_id=user_id, username="legit")

    init_data = make_telegram_init_data(user_id)
    resp = app_client.post("/api/auth/telegram-direct", json={"init_data": init_data})
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("token")
    assert data.get("user_id") == user_id
    assert database.get_auth_token_by_user_id(user_id) == data["token"]


def test_telegram_direct_token_belongs_only_to_signed_user(app_client, temp_db):
    """Даже если в теле когда-то был бы чужой user_id — токен выдаётся только
    для id из подписанного initData."""
    from shop_bot.data_manager import database

    attacker_id = 555020
    victim_id = 555021
    insert_user(database.DB_FILE, telegram_id=attacker_id, username="attacker")
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim5")

    # Подпись только за attacker; victim не должен получить/перезаписать токен.
    init_data = make_telegram_init_data(attacker_id)
    resp = app_client.post(
        "/api/auth/telegram-direct",
        json={"init_data": init_data, "user_id": victim_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["user_id"] == attacker_id
    assert database.get_user_by_auth_token(data["token"])["telegram_id"] == attacker_id
    assert database.get_auth_token_by_user_id(victim_id) is None


def test_auth_token_endpoint_also_rejects_invalid_signature(app_client, temp_db):
    resp = app_client.post(
        "/api/auth/token",
        json={"init_data": "auth_date=1&user=%7B%22id%22%3A1%7D&hash=" + ("ab" * 32)},
    )
    assert resp.status_code == 401
    assert resp.json().get("ok") is False


def test_invalidate_all_user_auth_tokens_rotates_existing(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7001, username="u1")
    insert_user(database.DB_FILE, telegram_id=7002, username="u2")
    database.update_user_auth_token(7001, "tok-old-1")
    database.update_user_auth_token(7002, "tok-old-2")

    n = database.invalidate_all_user_auth_tokens()
    assert n == 2
    t1 = database.get_auth_token_by_user_id(7001)
    t2 = database.get_auth_token_by_user_id(7002)
    assert t1 and t1 != "tok-old-1"
    assert t2 and t2 != "tok-old-2"
    assert t1 != t2


def test_referral_payout_list_requires_valid_token(app_client, temp_db):
    """Соседние защищённые эндпоинты не принимают чужой user_id без токена."""
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=8001, username="refuser")
    resp = app_client.post("/api/referral/payout-methods/list", json={"user_id": 8001})
    assert resp.json().get("ok") is False
    assert "unauth" in (resp.json().get("error") or "").lower()

    database.update_user_auth_token(8001, "ref-tok-8001")
    ok = app_client.post("/api/referral/payout-methods/list", json={"token": "ref-tok-8001"})
    assert ok.json().get("ok") is True
