"""Stored XSS в auth_email / pending_email: ввод → БД → DOM без innerHTML/onclick.

Старые вредоносные строки уже могут лежать в users.pending_email / auth_email.
Фронт не интерполирует их в HTML и не кладёт в inline JS.
Токен авторизации в ассертах и сообщениях об ошибке не печатаем.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from conftest import insert_user, issue_auth_token, no_smtp, temp_db  # noqa: F401

USER_ID = 97001
PASSWORD = "Passw0rd!"

XSS_PAYLOADS = (
    "<img src=x onerror=alert(1)>@evil.com",
    "</span><script>alert(1)</script>@x.com",
    "');alert(1);//@x.com",
    '" onclick="alert(1)@x.com',
    "`+alert(1)+`@x.com",
    "line1\nline2@x.com",
    "back\\slash@x.com",
    "quotes ' \" `@x.com",
)


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _seed_email_user(database, *, pending_email: str | None = None, auth_email: str = "safe-user@example.com") -> str:
    from shop_bot.data_manager.database import hash_password

    insert_user(
        database.DB_FILE,
        telegram_id=USER_ID,
        username="xssemail",
        auth_email=auth_email,
        auth_pass=hash_password(PASSWORD),
        email_verified=1,
        pending_email=pending_email,
    )
    return issue_auth_token(USER_ID)


def test_normalize_auth_email_rejects_xss_payloads(temp_db):
    from shop_bot.data_manager.database import AUTH_EMAIL_MAX_LEN, normalize_auth_email

    assert normalize_auth_email("profileuser@example.com") == "profileuser@example.com"
    assert normalize_auth_email("  User+tag@Example.COM  ") == "user+tag@example.com"
    assert normalize_auth_email(None) is None
    assert normalize_auth_email("") is None
    assert normalize_auth_email("a" * (AUTH_EMAIL_MAX_LEN + 1) + "@x.com") is None
    for payload in XSS_PAYLOADS:
        assert normalize_auth_email(payload) is None, "payload must not be treated as email"


def test_change_email_api_rejects_xss_and_does_not_store(temp_db, no_smtp):
    from shop_bot.data_manager import database

    token = _seed_email_user(database)
    client = _client()
    for payload in XSS_PAYLOADS:
        resp = client.post(
            "/api/user/profile/change-email/request",
            json={"token": token, "new_email": payload, "password": PASSWORD},
        )
        body = resp.json()
        assert body.get("ok") is False
        assert "формат" in (body.get("error") or "").lower()
        assert payload not in (body.get("error") or "")
        assert token not in (body.get("error") or "")
        stored = database.get_user(USER_ID)
        assert stored["pending_email"] in (None, "")
        assert stored["auth_email"] == "safe-user@example.com"


def test_register_rejects_xss_email(temp_db):
    from shop_bot.data_manager import database

    client = _client()
    payload = "<img src=x onerror=alert(1)>@evil.com"
    resp = client.post(
        "/api/auth/email/register",
        json={"email": payload, "password": PASSWORD},
    )
    body = resp.json()
    assert body.get("ok") is False
    assert payload not in (body.get("error") or "")
    assert database.get_user_by_email(payload) is None


def test_set_pending_email_rejects_xss(temp_db):
    from shop_bot.data_manager import database

    _seed_email_user(database)
    assert database.set_pending_email(USER_ID, "<img src=x onerror=alert(1)>@evil.com") is False
    assert database.get_user(USER_ID)["pending_email"] in (None, "")


def test_old_stored_pending_is_not_promoted_to_auth_email(temp_db):
    from shop_bot.data_manager import database

    payload = "<img src=x onerror=alert(1)>@evil.com"
    token = _seed_email_user(database, pending_email=payload)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE users SET pending_email = ? WHERE telegram_id = ?",
            (payload, USER_ID),
        )
        conn.commit()
    ok, result = database.finalize_pending_email_change(USER_ID)
    assert ok is False
    user = database.get_user(USER_ID)
    assert user["auth_email"] == "safe-user@example.com"
    info = _client().post("/api/user/profile-info", json={"token": token}).json()
    assert info.get("ok") is True
    assert info.get("auth_email") == "safe-user@example.com"
    assert token not in str(info)


def test_frontend_does_not_interpolate_email_into_html_or_onclick():
    html = Path("src/shop_bot/webapp/static/js/app.js").read_text(encoding="utf-8")
    start = html.index("function _renderProfileMain")
    end = html.index("function _renderProfileChangePassword")
    profile_fn = html[start:end]
    assert "${info.auth_email" not in profile_fn
    assert "${info.pending_email" not in profile_fn
    assert "${pendingEmail}" not in profile_fn
    assert "onclick=" not in profile_fn
    assert "innerHTML" not in profile_fn
    assert "textContent" in profile_fn
    assert "_profileIconBtn(" in profile_fn
    assert "setAttribute('data-profile-action', 'cancel-email')" in profile_fn
    assert "replaceChildren" in profile_fn

    verify_start = html.index("function _renderProfileVerifyEmailCode")
    verify_end = html.index("async function _submitProfileVerifyEmailCode")
    verify_fn = html[verify_start:verify_end]
    assert "${pendingEmail}" not in verify_fn
    assert "onclick=" not in verify_fn
    assert "innerHTML" not in verify_fn
    assert "textContent" in verify_fn
    assert "setAttribute('data-profile-action', 'verify-email')" in verify_fn
    assert "setAttribute('data-profile-action', 'cancel-email')" in verify_fn
