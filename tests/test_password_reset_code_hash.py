"""Регрессия: код сброса пароля хранился в RAM открытым текстом.

Старый PASSWORD_RESET_TOKENS[email] = {"code": "123456", "expires": ...}
и сравнение через ``!=``. Дамп процесса / чтение dict давали код;
timing ``!=`` отличал длину.

Новый код: в памяти только sha256(email:code), проверка через
hmac.compare_digest. Шестизначный код уходит только в Telegram.
"""
from __future__ import annotations

import re

from conftest import insert_user, temp_db  # noqa: F401

EMAIL = "reset-hash@example.com"
NEW_PASSWORD = "NewPassw0rd!"
TG_ID = 55001


def test_reset_code_is_hashed_in_memory_not_plaintext(temp_db, app_client, monkeypatch):
    """На старом коде в dict лежал ключ code с шестизначным значением."""
    from shop_bot.webapp import handlers

    insert_user(
        temp_db.DB_FILE,
        telegram_id=TG_ID,
        username="resethash",
        auth_email=EMAIL,
        email_verified=1,
    )
    handlers.PASSWORD_RESET_TOKENS.clear()
    sent = []

    async def _fake_send(user_id, text, reply_markup=None, photo=None):
        sent.append(text)
        return True

    monkeypatch.setattr(handlers, "_send_telegram_message", _fake_send)

    resp = app_client.post("/api/auth/email/reset/request", json={"email": EMAIL})
    assert resp.json() == {"ok": True}

    stored = handlers.PASSWORD_RESET_TOKENS[EMAIL]
    assert "code" not in stored
    code_hash = stored["code_hash"]
    assert isinstance(code_hash, str) and len(code_hash) == 64
    sent_code = re.search(r"<code>(\d{6})</code>", sent[0]).group(1)
    assert sent_code not in code_hash
    assert code_hash not in sent[0]
    assert code_hash == handlers._hash_password_reset_code(EMAIL, sent_code)


def test_reset_check_and_verify_accept_code_from_telegram(temp_db, app_client, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(
        temp_db.DB_FILE,
        telegram_id=TG_ID,
        username="resethash",
        auth_email=EMAIL,
        email_verified=1,
        auth_pass=database.hash_password("Passw0rd!"),
    )
    handlers.PASSWORD_RESET_TOKENS.clear()
    sent = []

    async def _fake_send(user_id, text, reply_markup=None, photo=None):
        sent.append(text)
        return True

    monkeypatch.setattr(handlers, "_send_telegram_message", _fake_send)
    app_client.post("/api/auth/email/reset/request", json={"email": EMAIL})
    code = re.search(r"<code>(\d{6})</code>", sent[0]).group(1)

    wrong = app_client.post(
        "/api/auth/email/reset/check", json={"email": EMAIL, "code": "000000"}
    )
    assert wrong.json()["ok"] is False

    check = app_client.post(
        "/api/auth/email/reset/check", json={"email": EMAIL, "code": code}
    )
    assert check.json()["ok"] is True

    verify = app_client.post(
        "/api/auth/email/reset/verify",
        json={"email": EMAIL, "code": code, "new_password": NEW_PASSWORD},
    )
    assert verify.json()["ok"] is True
    assert EMAIL not in handlers.PASSWORD_RESET_TOKENS

    login = app_client.post(
        "/api/auth/email/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    )
    assert login.json()["ok"] is True
    assert login.json().get("token")


def test_reset_code_from_other_email_does_not_match():
    from shop_bot.webapp.handlers import _hash_password_reset_code, _password_reset_code_matches

    h = _hash_password_reset_code("a@example.com", "123456")
    assert _password_reset_code_matches("a@example.com", "123456", h) is True
    assert _password_reset_code_matches("b@example.com", "123456", h) is False
    assert _password_reset_code_matches("a@example.com", "654321", h) is False
    assert _password_reset_code_matches("a@example.com", "123456", "") is False
