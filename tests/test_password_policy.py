"""Регрессия: слабый _validate_password принимал «ababa» (5 букв без цифр).

Старый код: длина ≥ 5, не только цифры, хотя бы 2 разных символа.
Новый: минимум 8, буква и цифра. Login существующих слабых паролей
не тронут — политика только на register / reset / change-password.
"""
from __future__ import annotations

from shop_bot.webapp.handlers import _validate_password

from conftest import app_client, no_smtp, register_and_verify_email_user, temp_db  # noqa: F401


def test_ababa_is_rejected():
    """На старом коде _validate_password('ababa') возвращал None."""
    err = _validate_password("ababa")
    assert err is not None
    assert "8" in err or "цифр" in err.lower() or "букв" in err.lower()


def test_short_letter_password_rejected():
    assert _validate_password("abcd") is not None
    assert _validate_password("abcdefg") is not None  # 7 букв, без цифры и короче 8


def test_letters_only_eight_chars_rejected():
    """Раньше abcdefgh (8 букв) проходил — нет цифр, но длина ≥ 5."""
    err = _validate_password("abcdefgh")
    assert err is not None
    assert "цифр" in err.lower()


def test_digits_only_still_rejected():
    assert _validate_password("12345") is not None
    assert _validate_password("12345678") is not None


def test_passw0rd_still_accepted():
    assert _validate_password("Passw0rd!") is None
    assert _validate_password("NewPassw0rd!") is None


def test_register_rejects_ababa(temp_db, app_client):
    resp = app_client.post(
        "/api/auth/email/register",
        json={"email": "weak@example.com", "password": "ababa"},
    )
    body = resp.json()
    assert body["ok"] is False
    assert "error" in body
    from shop_bot.data_manager import database
    assert database.get_user_by_email("weak@example.com") is None


def test_register_still_accepts_strong_password(temp_db, app_client, no_smtp):
    resp = app_client.post(
        "/api/auth/email/register",
        json={"email": "strong@example.com", "password": "Passw0rd!"},
    )
    assert resp.json()["ok"] is True
    from shop_bot.data_manager import database
    assert database.get_user_by_email("strong@example.com") is not None


def test_change_password_rejects_ababa(temp_db, app_client, no_smtp):
    token, _uid = register_and_verify_email_user(
        app_client, temp_db.DB_FILE, "pwpolicy@example.com"
    )
    resp = app_client.post(
        "/api/user/profile/change-password",
        json={
            "token": token,
            "current_password": "Passw0rd!",
            "new_password": "ababa",
        },
    )
    assert resp.json()["ok"] is False


def test_login_still_works_for_legacy_short_password(temp_db, app_client):
    """Политика не применяется на login — старый короткий пароль остаётся валидным."""
    from shop_bot.data_manager import database

    user = database.create_user_by_email("legacy@example.com", "ababa")
    database.mark_email_verified(user["telegram_id"])
    resp = app_client.post(
        "/api/auth/email/login",
        json={"email": "legacy@example.com", "password": "ababa"},
    )
    assert resp.json()["ok"] is True
    assert resp.json().get("token")
