"""ЮKassa webhook: не-платёжные события и 404 от API не должны вызывать бесконечные ретраи."""
from __future__ import annotations

import io
import urllib.error
import urllib.request

from conftest import temp_db  # noqa: F401


class _FakeBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None

    def get_bot_instance(self):
        return None


def _flask_client():
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    database.update_setting("yookassa_shop_id", "123456")
    database.update_setting("yookassa_secret_key", "test_secret")
    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app.test_client()


def _raise_http(code: int):
    def _urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "", {}, io.BytesIO(b""))

    return _urlopen


def test_yookassa_webhook_ignores_non_payment_events(temp_db, monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: calls.append(a) or None)
    client = _flask_client()
    resp = client.post(
        "/yookassa-webhook",
        json={"type": "notification", "event": "refund.succeeded", "object": {"id": "refund-1", "payment_id": "pay-1"}},
    )
    assert resp.status_code == 200
    assert calls == []


def test_yookassa_webhook_acknowledges_unknown_payment(temp_db, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_http(404))
    client = _flask_client()
    resp = client.post(
        "/yookassa-webhook",
        json={"type": "notification", "event": "payment.succeeded", "object": {"id": "foreign-payment"}},
    )
    assert resp.status_code == 200


def test_yookassa_webhook_retries_on_api_failure(temp_db, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", _raise_http(500))
    client = _flask_client()
    resp = client.post(
        "/yookassa-webhook",
        json={"type": "notification", "event": "payment.succeeded", "object": {"id": "some-payment"}},
    )
    assert resp.status_code == 502
