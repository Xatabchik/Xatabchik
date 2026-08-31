"""RollyPay: HMAC вебхука, сверка суммы/метода с pending, GET у провайдера."""
from __future__ import annotations

import json
import time

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


class _FakeBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None

    def get_bot_instance(self):
        return None


def _flask_client(temp_db):
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app.test_client()


def _pending(*, payment_id: str, user_id: int, amount: float, method: str = "RollyPay") -> None:
    from shop_bot.data_manager import database

    database.create_payload_pending(
        payment_id,
        user_id,
        amount,
        {
            "user_id": user_id,
            "price": amount,
            "payment_method": method,
            "payment_id": payment_id,
            "action": "new",
        },
    )


def _pending_status(payment_id: str) -> str | None:
    from shop_bot.data_manager import database

    return database.get_pending_status(payment_id)


def _sign(body: bytes, secret: str, ts: int | None = None) -> dict[str, str]:
    import hashlib
    import hmac

    timestamp = str(ts if ts is not None else int(time.time()))
    payload = timestamp.encode("utf-8") + b"." + body
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return {"X-Timestamp": timestamp, "X-Signature": signature}


def test_rollypay_signature_rejects_stale_and_wrong_secret():
    from shop_bot.modules.rollypay_api import verify_webhook_signature

    body = b'{"event_type":"payment.paid"}'
    secret = "signing-secret"
    now = 1_700_000_000
    headers = _sign(body, secret, ts=now)
    assert verify_webhook_signature(body, headers["X-Timestamp"], headers["X-Signature"], secret, now=now)
    assert not verify_webhook_signature(body, headers["X-Timestamp"], headers["X-Signature"], secret, now=now + 301)
    assert not verify_webhook_signature(body, headers["X-Timestamp"], "deadbeef", secret, now=now)
    assert not verify_webhook_signature(body, headers["X-Timestamp"], headers["X-Signature"], "", now=now)


def test_rollypay_webhook_unconfigured_returns_503(temp_db):
    pid = "rp-unconfigured"
    _pending(payment_id=pid, user_id=501, amount=100.0)
    client = _flask_client(temp_db)
    body = json.dumps({"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-1"}).encode()
    resp = client.post("/rollypay-webhook", data=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 503
    assert _pending_status(pid) == "pending"


def test_rollypay_webhook_bad_signature_returns_403(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-bad-sig"
    _pending(payment_id=pid, user_id=502, amount=100.0)
    client = _flask_client(temp_db)
    body = json.dumps({"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-1"}).encode()
    headers = _sign(body, "wrong-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 403
    assert _pending_status(pid) == "pending"


def test_rollypay_webhook_rejects_other_provider_pending(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-cross"
    _pending(payment_id=pid, user_id=503, amount=200.0, method="YooKassa")
    monkeypatch.setattr(
        rollypay_api,
        "get_payment_sync",
        lambda *a, **k: {"status": "paid", "order_id": pid, "amount": "200.00", "payment_currency": "RUB"},
    )
    client = _flask_client(temp_db)
    body = json.dumps({"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-x"}).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_rollypay_webhook_chargeback_does_not_complete(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-cb"
    _pending(payment_id=pid, user_id=504, amount=150.0)
    monkeypatch.setattr(
        rollypay_api,
        "get_payment_sync",
        lambda *a, **k: {"status": "chargeback", "order_id": pid, "amount": "150.00"},
    )
    client = _flask_client(temp_db)
    body = json.dumps(
        {"event_type": "payment.chargeback", "order_id": pid, "payment_id": "prov-cb"}
    ).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 200
    assert _pending_status(pid) == "cancelled"


def test_rollypay_webhook_cancel_keeps_pending_if_api_says_paid(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-cancel-paid"
    _pending(payment_id=pid, user_id=506, amount=150.0)
    monkeypatch.setattr(
        rollypay_api,
        "get_payment_sync",
        lambda *a, **k: {"status": "paid", "order_id": pid, "amount": "150.00"},
    )
    client = _flask_client(temp_db)
    body = json.dumps(
        {"event_type": "payment.canceled", "order_id": pid, "payment_id": "prov-live"}
    ).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_rollypay_paid_revives_cancelled_invoice(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-revive"
    _pending(payment_id=pid, user_id=507, amount=150.0)
    assert database.cancel_pending_transaction(pid)
    assert _pending_status(pid) == "cancelled"
    monkeypatch.setattr(
        rollypay_api,
        "get_payment_sync",
        lambda *a, **k: {
            "status": "paid",
            "order_id": pid,
            "amount": "150.00",
            "payment_currency": "RUB",
        },
    )
    client = _flask_client(temp_db)
    body = json.dumps(
        {"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-rev"}
    ).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_rollypay_webhook_amount_mismatch_keeps_pending(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-underpay"
    _pending(payment_id=pid, user_id=505, amount=500.0)
    monkeypatch.setattr(
        rollypay_api,
        "get_payment_sync",
        lambda *a, **k: {
            "status": "paid",
            "order_id": pid,
            "amount": "1.00",
            "payment_currency": "RUB",
        },
    )
    client = _flask_client(temp_db)
    body = json.dumps({"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-1"}).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_rollypay_webhook_completes_when_api_confirms_paid(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-ok"
    _pending(payment_id=pid, user_id=506, amount=150.0)
    monkeypatch.setattr(
        rollypay_api,
        "get_payment_sync",
        lambda *a, **k: {
            "status": "paid",
            "order_id": pid,
            "amount": "150.00",
            "payment_currency": "RUB",
        },
    )
    client = _flask_client(temp_db)
    body = json.dumps({"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-ok"}).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_rollypay_webhook_api_failure_returns_503(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import rollypay_api

    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    pid = "rp-503"
    _pending(payment_id=pid, user_id=507, amount=80.0)
    monkeypatch.setattr(rollypay_api, "get_payment_sync", lambda *a, **k: None)
    client = _flask_client(temp_db)
    body = json.dumps({"event_type": "payment.paid", "order_id": pid, "payment_id": "prov-503"}).encode()
    headers = _sign(body, "real-secret")
    headers["Content-Type"] = "application/json"
    resp = client.post("/rollypay-webhook", data=body, headers=headers)
    assert resp.status_code == 503
    assert _pending_status(pid) == "pending"


def test_create_payment_rollypay_stores_pending(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=50801, username="rpuser")
    token = issue_auth_token(50801)
    database.update_setting("rollypay_api_key", "api-key")
    database.update_setting("rollypay_signing_secret", "real-secret")
    database.create_plan("TestHost", "1 месяц", 1, 200.0)
    plan_id = database.get_plans_for_host("TestHost")[0]["plan_id"]

    class _FakeAPI:
        async def create_payment(self, *args, **kwargs):
            return "https://rollypay.io/pay/test", "prov-create"

    monkeypatch.setattr(handlers, "_rollypay_api", lambda: _FakeAPI())

    async def _ok_send(*a, **k):
        return None

    monkeypatch.setattr(handlers, "_send_telegram_message", _ok_send)

    client = TestClient(handlers.app)
    resp = client.post(
        "/api/create-payment",
        json={
            "user_id": 50801,
            "token": token,
            "payment_method": "pay_rollypay",
            "plan_id": plan_id,
            "action": "new",
            "host_name": "TestHost",
        },
    )
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("payment_url") == "https://rollypay.io/pay/test"
    pid = data.get("payment_id")
    assert pid
    assert database.get_pending_status(pid) == "pending"
    meta = database.get_pending_metadata(pid)
    assert meta.get("payment_method") == "RollyPay"
    assert meta.get("rollypay_payment_id") == "prov-create"
