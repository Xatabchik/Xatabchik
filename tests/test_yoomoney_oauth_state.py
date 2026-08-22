"""F-09: YooMoney OAuth callback принимает code только с валидным state из session."""
from __future__ import annotations

import json

from conftest import temp_db  # noqa: F401


class _FakeBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None


class _FakeUrlOpen:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[object] = []

    def __call__(self, req, timeout=15):
        self.calls.append(req)
        return _FakeHttpResp(json.dumps(self.payload).encode("utf-8"))


class _FakeHttpResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _client(temp_db, monkeypatch, *, logged_in: bool = True):
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    if logged_in:
        with client.session_transaction() as sess:
            sess["logged_in"] = True
    return flask_app, client


def test_yoomoney_callback_rejects_missing_state(temp_db, monkeypatch):
    temp_db.update_setting("yoomoney_client_id", "ym-client")
    opener = _FakeUrlOpen({"access_token": "should-not-save"})
    monkeypatch.setattr("urllib.request.urlopen", opener)

    _, client = _client(temp_db, monkeypatch)
    resp = client.get("/yoomoney/callback?code=abc", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert opener.calls == []
    assert not (temp_db.get_setting("yoomoney_api_token") or "").strip()


def test_yoomoney_callback_rejects_wrong_state(temp_db, monkeypatch):
    temp_db.update_setting("yoomoney_client_id", "ym-client")
    opener = _FakeUrlOpen({"access_token": "should-not-save"})
    monkeypatch.setattr("urllib.request.urlopen", opener)

    _, client = _client(temp_db, monkeypatch)
    with client.session_transaction() as sess:
        sess["yoomoney_oauth_state"] = "expected-state"
    resp = client.get("/yoomoney/callback?code=abc&state=other-state", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert opener.calls == []
    assert not (temp_db.get_setting("yoomoney_api_token") or "").strip()


def test_yoomoney_callback_accepts_valid_state(temp_db, monkeypatch):
    temp_db.update_setting("yoomoney_client_id", "ym-client")
    opener = _FakeUrlOpen({"access_token": "ym-access-ok"})
    monkeypatch.setattr("urllib.request.urlopen", opener)

    _, client = _client(temp_db, monkeypatch)
    connect = client.get("/yoomoney/connect", follow_redirects=False)
    assert connect.status_code in (302, 303)
    location = connect.headers.get("Location") or ""
    assert "state=" in location
    with client.session_transaction() as sess:
        state = sess.get("yoomoney_oauth_state")
    assert state
    assert f"state={state}" in location

    resp = client.get(f"/yoomoney/callback?code=abc&state={state}", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert len(opener.calls) == 1
    assert temp_db.get_setting("yoomoney_api_token") == "ym-access-ok"


def test_yoomoney_callback_requires_login(temp_db, monkeypatch):
    opener = _FakeUrlOpen({"access_token": "should-not-save"})
    monkeypatch.setattr("urllib.request.urlopen", opener)
    _, client = _client(temp_db, monkeypatch, logged_in=False)
    resp = client.get("/yoomoney/callback?code=abc&state=x", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in (resp.headers.get("Location") or "")
    assert opener.calls == []
