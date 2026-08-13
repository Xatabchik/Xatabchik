"""Регрессия: enumeration email на register/reset и выдача токена без кода.

Старый код:
- POST /api/auth/email/register при занятом адресе возвращал
  «Email уже зарегистрирован»;
- POST /api/auth/email/reset/request — «Email не найден» или
  «не синхронизирован с Telegram»;
- POST /api/auth/email/verify при email_verified=1 выдавал auth_token
  без проверки кода (достаточно знать адрес).

Новый код: register/reset/resend не отличают существующий адрес от
несуществующего. Verify всегда требует валидный код.
"""
from __future__ import annotations

from conftest import (  # noqa: F401
    app_client,
    insert_user,
    no_smtp,
    register_and_verify_email_user,
    temp_db,
)

EMAIL_A = "taken@example.com"
EMAIL_UNKNOWN = "nobody-enum@example.com"
PASSWORD = "Passw0rd!"


def test_register_existing_email_same_success_does_not_overwrite(temp_db, app_client, no_smtp):
    """Старый код: второй register того же email → ok=False, «уже зарегистрирован»."""
    from shop_bot.data_manager import database

    first = app_client.post(
        "/api/auth/email/register", json={"email": EMAIL_A, "password": PASSWORD}
    )
    assert first.json()["ok"] is True
    assert first.json().get("requires_verification") is True
    user = database.get_user_by_email(EMAIL_A)
    uid = user["telegram_id"]
    pass_hash = user["auth_pass"]

    second = app_client.post(
        "/api/auth/email/register", json={"email": EMAIL_A, "password": "OtherPass1"}
    )
    body = second.json()
    assert body["ok"] is True
    assert body.get("requires_verification") is True
    assert "уже зарегистрирован" not in str(body).lower()
    assert "error" not in body or not body.get("error")

    again = database.get_user_by_email(EMAIL_A)
    assert again["telegram_id"] == uid
    assert again["auth_pass"] == pass_hash


def test_register_new_and_existing_same_response_shape(temp_db, app_client, no_smtp):
    new = app_client.post(
        "/api/auth/email/register", json={"email": "fresh-enum@example.com", "password": PASSWORD}
    )
    app_client.post(
        "/api/auth/email/register", json={"email": EMAIL_A, "password": PASSWORD}
    )
    taken = app_client.post(
        "/api/auth/email/register", json={"email": EMAIL_A, "password": PASSWORD}
    )
    assert set(new.json().keys()) == set(taken.json().keys())
    assert new.json()["ok"] is True and taken.json()["ok"] is True
    assert new.json().get("requires_verification") is True
    assert taken.json().get("requires_verification") is True


def test_reset_unknown_email_returns_ok(temp_db, app_client):
    from shop_bot.webapp import handlers

    handlers.PASSWORD_RESET_TOKENS.clear()
    resp = app_client.post("/api/auth/email/reset/request", json={"email": EMAIL_UNKNOWN})
    body = resp.json()
    assert body == {"ok": True}
    assert EMAIL_UNKNOWN.lower() not in handlers.PASSWORD_RESET_TOKENS


def test_reset_email_only_user_returns_ok_without_storing_code(temp_db, app_client, no_smtp):
    from shop_bot.webapp import handlers

    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, EMAIL_A)
    assert str(uid).startswith("999")
    handlers.PASSWORD_RESET_TOKENS.clear()

    resp = app_client.post("/api/auth/email/reset/request", json={"email": EMAIL_A})
    body = resp.json()
    assert body["ok"] is True
    assert "не найден" not in str(body).lower()
    assert "синхронизирован" not in str(body).lower()
    assert EMAIL_A.lower() not in handlers.PASSWORD_RESET_TOKENS
    assert token  # исходный логин не затронут


def test_reset_telegram_linked_user_still_sends_code(temp_db, app_client, monkeypatch):
    from shop_bot.webapp import handlers

    insert_user(
        temp_db.DB_FILE,
        telegram_id=44001,
        username="tgmail",
        auth_email=EMAIL_A,
        email_verified=1,
    )
    handlers.PASSWORD_RESET_TOKENS.clear()
    sent = []

    async def _fake_send(user_id, text, reply_markup=None, photo=None):
        sent.append((user_id, text))
        return True

    monkeypatch.setattr(handlers, "_send_telegram_message", _fake_send)

    resp = app_client.post("/api/auth/email/reset/request", json={"email": EMAIL_A})
    assert resp.json() == {"ok": True}
    assert len(sent) == 1
    assert sent[0][0] == 44001
    assert EMAIL_A.lower() in handlers.PASSWORD_RESET_TOKENS
    stored = handlers.PASSWORD_RESET_TOKENS[EMAIL_A.lower()]
    assert "code" not in stored
    assert stored.get("code_hash")
    import re
    sent_code = re.search(r"<code>(\d{6})</code>", sent[0][1]).group(1)
    assert sent_code not in stored["code_hash"]
    assert stored["code_hash"] not in sent[0][1]


def test_reset_unknown_and_email_only_same_body(temp_db, app_client, no_smtp):
    from shop_bot.webapp import handlers

    register_and_verify_email_user(app_client, temp_db.DB_FILE, EMAIL_A)
    handlers.PASSWORD_RESET_TOKENS.clear()
    unknown = app_client.post("/api/auth/email/reset/request", json={"email": EMAIL_UNKNOWN})
    taken = app_client.post("/api/auth/email/reset/request", json={"email": EMAIL_A})
    assert unknown.json() == taken.json() == {"ok": True}


def test_verify_unknown_email_same_error_as_bad_code(temp_db, app_client, no_smtp):
    app_client.post(
        "/api/auth/email/register", json={"email": EMAIL_A, "password": PASSWORD}
    )
    bad = app_client.post(
        "/api/auth/email/verify", json={"email": EMAIL_A, "code": "000000"}
    )
    missing = app_client.post(
        "/api/auth/email/verify", json={"email": EMAIL_UNKNOWN, "code": "000000"}
    )
    assert missing.json() == bad.json()
    assert missing.json()["ok"] is False
    assert "не найден" not in missing.json().get("error", "").lower()
    assert "token" not in missing.json() or not missing.json().get("token")


def test_verify_does_not_issue_token_without_valid_code(temp_db, app_client, no_smtp):
    """Старый код: email_verified=1 → токен без кода."""
    from shop_bot.data_manager import database

    email = "verified-enum@example.com"
    old_token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, email)

    resp = app_client.post(
        "/api/auth/email/verify", json={"email": email, "code": "123456"}
    )
    body = resp.json()
    assert body["ok"] is False
    assert not body.get("token")
    assert database.get_auth_token_by_user_id(uid) == old_token


def test_verify_with_real_code_still_issues_token(temp_db, app_client, no_smtp):
    email = "need-code@example.com"
    reg = app_client.post(
        "/api/auth/email/register", json={"email": email, "password": PASSWORD}
    )
    assert reg.json()["ok"] is True
    code = no_smtp[email]
    resp = app_client.post(
        "/api/auth/email/verify", json={"email": email, "code": code}
    )
    body = resp.json()
    assert body["ok"] is True
    assert body.get("token")


def test_resend_unknown_and_verified_return_ok(temp_db, app_client, no_smtp):
    unknown = app_client.post("/api/auth/email/resend", json={"email": EMAIL_UNKNOWN})
    assert unknown.json()["ok"] is True
    assert "не найден" not in str(unknown.json()).lower()

    register_and_verify_email_user(app_client, temp_db.DB_FILE, EMAIL_A)
    verified = app_client.post("/api/auth/email/resend", json={"email": EMAIL_A})
    assert verified.json()["ok"] is True
    assert "подтверждён" not in str(verified.json()).lower()
    assert unknown.json() == verified.json()
