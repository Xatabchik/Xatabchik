"""F-10: rate-limit /login не обходится подменой X-Forwarded-For на прямом запросе."""
from __future__ import annotations

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


def _post_login(client, *, remote: str, xff: str | None = None):
    headers = {}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    return client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password"},
        headers=headers,
        environ_base={"REMOTE_ADDR": remote},
        follow_redirects=False,
    )


def test_spoofed_xff_does_not_bypass_login_rate_limit_on_direct_request(temp_db):
    client = _client(temp_db)
    remote = "203.0.113.10"
    statuses = []
    for i in range(6):
        resp = _post_login(client, remote=remote, xff=f"198.51.100.{i}")
        statuses.append(resp.status_code)
    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert statuses[5] == 429


def test_xff_is_used_only_behind_local_proxy(temp_db):
    client = _client(temp_db)
    statuses = []
    for i in range(6):
        resp = _post_login(client, remote="127.0.0.1", xff=f"198.51.100.{i}")
        statuses.append(resp.status_code)
    assert all(code == 200 for code in statuses), statuses
