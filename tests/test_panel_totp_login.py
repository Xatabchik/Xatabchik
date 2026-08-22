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
