"""Регрессия: SlowAPI на email-auth считал только IP (30/min).

С разных адресов один и тот же email можно было молотить без общего
лимита (подбор пароля / кода). Новый слой — 30/мин на нормализованный
email, поверх IP. Существующий и несуществующий адрес считаются
одинаково, чтобы 429 не enumeratил аккаунты.
"""
from __future__ import annotations

from conftest import temp_db  # noqa: F401


def test_per_email_helper_blocks_after_limit(temp_db, monkeypatch):
    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "EMAIL_AUTH_PER_EMAIL_LIMIT", 3)
    handlers._EMAIL_AUTH_HITS.clear()

    email = "spray@example.com"
    assert handlers._email_auth_rate_limited(email) is False
    assert handlers._email_auth_rate_limited(email) is False
    assert handlers._email_auth_rate_limited(email) is False
    assert handlers._email_auth_rate_limited(email) is True
    # Другой адрес не задет.
    assert handlers._email_auth_rate_limited("other@example.com") is False


def test_unknown_and_known_email_share_same_429_shape(temp_db, app_client, monkeypatch):
    """На старом коде 31-й login того же email с testclient упирался бы
    только в IP-лимит, общий на все адреса. С per-email лимитом=2 третий
    запрос к одному адресу даёт 429, другой адрес проходит."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "EMAIL_AUTH_PER_EMAIL_LIMIT", 2)
    handlers._EMAIL_AUTH_HITS.clear()

    known = "known-limit@example.com"
    unknown = "unknown-limit@example.com"
    other = "other-limit@example.com"

    user = database.create_user_by_email(known, "Passw0rd!")
    database.mark_email_verified(user["telegram_id"])

    r1 = app_client.post("/api/auth/email/login", json={"email": known, "password": "wrongpass1"})
    r2 = app_client.post("/api/auth/email/login", json={"email": known, "password": "wrongpass1"})
    r3 = app_client.post("/api/auth/email/login", json={"email": known, "password": "wrongpass1"})
    assert r1.status_code == 200 and r1.json()["ok"] is False
    assert r2.status_code == 200 and r2.json()["ok"] is False
    assert r3.status_code == 429
    assert r3.json().get("ok") is False
    assert "rate limit" in r3.json().get("error", "").lower()

    u1 = app_client.post("/api/auth/email/login", json={"email": unknown, "password": "wrongpass1"})
    u2 = app_client.post("/api/auth/email/login", json={"email": unknown, "password": "wrongpass1"})
    u3 = app_client.post("/api/auth/email/login", json={"email": unknown, "password": "wrongpass1"})
    assert u3.status_code == 429
    assert u3.json() == r3.json()

    o1 = app_client.post("/api/auth/email/login", json={"email": other, "password": "wrongpass1"})
    assert o1.status_code == 200
    assert o1.json()["ok"] is False
    assert "неверный" in o1.json().get("error", "").lower()


def test_successful_login_still_works_under_limit(temp_db, app_client, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "EMAIL_AUTH_PER_EMAIL_LIMIT", 5)
    handlers._EMAIL_AUTH_HITS.clear()

    email = "ok-limit@example.com"
    user = database.create_user_by_email(email, "Passw0rd!")
    database.mark_email_verified(user["telegram_id"])
    resp = app_client.post(
        "/api/auth/email/login", json={"email": email, "password": "Passw0rd!"}
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json().get("token")
