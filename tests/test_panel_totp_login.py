"""Quick-win: опциональный TOTP на /login. Выключенный 2FA не меняет admin/admin."""
from __future__ import annotations

import pyotp

from conftest import temp_db  # noqa: F401


class _FakeBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None


def _client(temp_db):
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_login_page_hides_totp_when_disabled(temp_db):
    client = _client(temp_db)
    body = client.get("/login").get_data(as_text=True)
    assert 'name="totp"' not in body
    assert "Код TOTP" not in body


def test_login_page_shows_totp_when_enabled(temp_db):
    secret = pyotp.random_base32()
    temp_db.update_setting("panel_totp_enabled", "true")
    temp_db.update_setting("panel_totp_secret", temp_db.encrypt_managed_bot_token(secret))
    client = _client(temp_db)
    body = client.get("/login").get_data(as_text=True)
    assert 'name="totp"' in body
    assert "Код TOTP" in body


def test_login_succeeds_without_totp_when_disabled(temp_db):
    client = _client(temp_db)
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


def test_login_rejects_incorrect_totp(temp_db):
    secret = pyotp.random_base32()
    temp_db.update_setting("panel_totp_enabled", "true")
    temp_db.update_setting("panel_totp_secret", temp_db.encrypt_managed_bot_token(secret))
    client = _client(temp_db)
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin", "totp": "000000"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert not sess.get("logged_in")


def test_login_accepts_correct_totp(temp_db):
    secret = pyotp.random_base32()
    temp_db.update_setting("panel_totp_enabled", "true")
    temp_db.update_setting("panel_totp_secret", temp_db.encrypt_managed_bot_token(secret))
    client = _client(temp_db)
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin", "totp": pyotp.TOTP(secret).now()},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with client.session_transaction() as sess:
        assert sess.get("logged_in") is True


def _settings_client(temp_db):
    client = _client(temp_db)
    with client.session_transaction() as sess:
        sess["logged_in"] = True
    return client


def test_settings_enable_totp_without_code_stays_off_and_shows_qr(temp_db):
    client = _settings_client(temp_db)
    resp = client.post(
        "/settings",
        data={"panel_totp_enabled": "true", "next_hash": "#panel"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert (temp_db.get_setting("panel_totp_enabled") or "").lower() != "true"
    assert temp_db.get_setting("panel_totp_secret")
    body = resp.get_data(as_text=True)
    assert 'src="data:image/png;base64,' in body
    assert 'id="panel_totp_secret_display"' in body
    assert "otpauth://" not in body
    assert 'name="panel_totp_confirm"' in body


def test_settings_enable_totp_with_app_code(temp_db):
    client = _settings_client(temp_db)
    client.post(
        "/settings",
        data={"panel_totp_enabled": "true", "next_hash": "#panel"},
        follow_redirects=True,
    )
    secret = temp_db.decrypt_managed_bot_token(temp_db.get_setting("panel_totp_secret") or "")
    resp = client.post(
        "/settings",
        data={
            "panel_totp_enabled": "true",
            "panel_totp_confirm": pyotp.TOTP(secret).now(),
            "next_hash": "#panel",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert (temp_db.get_setting("panel_totp_enabled") or "").lower() == "true"
    body = resp.get_data(as_text=True)
    assert 'src="data:image/png;base64,' in body
    assert 'name="panel_totp_confirm"' not in body
