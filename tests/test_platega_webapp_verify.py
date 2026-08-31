"""WebApp-проверка Platega: GET /transaction/{id} и общий идемпотентный путь выдачи."""
from __future__ import annotations

import pytest
from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

OWNER_ID = 93001
ATTACKER_ID = 93002


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _flask_client(temp_db):
    from shop_bot.webhook_server.app import create_webhook_app

    class _FakeBot:
        def get_status(self):
            return {"is_running": False}

        def get_loop(self):
            return None

        def get_bot_instance(self):
            return None

    flask_app = create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _seed(database, *, method="Platega", txid="plt-tx-1", amount=150.0, user_id=OWNER_ID, pid="wa-platega-1"):
    insert_user(database.DB_FILE, telegram_id=user_id, username="pltowner", balance=0)
    token = issue_auth_token(user_id)
    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    database.update_setting("platega_base_url", "https://app.platega.io")
    database.create_payload_pending(
        pid,
        user_id,
        amount,
        {
            "user_id": user_id,
            "price": amount,
            "payment_method": method,
            "payment_id": pid,
            "platega_transaction_id": txid,
            "action": "new",
            "months": 1,
        },
    )
    return token, pid, txid


def _verify(client, token, pid, **extra):
    return client.post(
        f"/api/webapp/payments/{pid}/verify",
        json={"token": token, **extra},
    )


@pytest.fixture
def fulfill_calls(monkeypatch):
    calls = []

    async def fake_process(bot, metadata):
        calls.append(dict(metadata))
        return True

    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)
    monkeypatch.setattr("shop_bot.bot.handlers.process_successful_payment", fake_process)
    return calls


def test_verify_confirmed_fulfills_once(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, txid = _seed(temp_db)

    async def fake_get(self, transaction_id):
        assert transaction_id == txid
        return {"id": txid, "status": "CONFIRMED", "amount": 150.0, "payload": pid}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    client = _client()
    resp = _verify(client, token, pid)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "confirmed"
    assert data["payment_id"] == pid
    assert data["provider_transaction_id"] == txid
    assert data["key_issued"] is True
    assert len(fulfill_calls) == 1
    assert temp_db.get_pending_status(pid) == "paid"


def test_verify_pending_does_not_fulfill(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, txid = _seed(temp_db)

    async def fake_get(self, transaction_id):
        return {"id": txid, "status": "PENDING", "payload": pid}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    resp = _verify(_client(), token, pid)
    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "status": "pending",
        "payment_id": pid,
        "provider_transaction_id": txid,
        "key_issued": False,
    }
    assert fulfill_calls == []
    assert temp_db.get_pending_status(pid) == "pending"


def test_verify_canceled_does_not_fulfill(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, txid = _seed(temp_db)

    async def fake_get(self, transaction_id):
        return {"id": txid, "status": "CANCELED", "payload": pid}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    resp = _verify(_client(), token, pid)
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"
    assert resp.json()["key_issued"] is False
    assert fulfill_calls == []
    assert temp_db.get_pending_status(pid) == "cancelled"
    rows, _ = temp_db.get_transactions_paginated(page=1, per_page=5, user_id=OWNER_ID)
    assert rows[0]["status"] == "cancelled"


def test_verify_chargebacked_is_canceled(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, txid = _seed(temp_db, pid="wa-platega-cb")

    async def fake_get(self, transaction_id):
        return {"id": txid, "status": "CHARGEBACKED"}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    resp = _verify(_client(), token, pid)
    assert resp.json()["status"] == "canceled"
    assert fulfill_calls == []
    assert temp_db.get_pending_status(pid) == "cancelled"


def test_verify_foreign_user_forbidden_does_not_call_platega(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, _txid = _seed(temp_db)
    insert_user(temp_db.DB_FILE, telegram_id=ATTACKER_ID, username="attacker")
    attacker_token = issue_auth_token(ATTACKER_ID)
    called = []

    async def fake_get(self, transaction_id):
        called.append(transaction_id)
        return {"status": "CONFIRMED"}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    resp = _verify(_client(), attacker_token, pid)
    assert resp.status_code == 403
    assert resp.json()["ok"] is False
    assert called == []
    assert fulfill_calls == []
    assert temp_db.get_pending_status(pid) == "pending"


def test_verify_rejects_non_platega_method(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, _txid = _seed(temp_db, method="YooKassa", pid="wa-yookassa-1")
    called = []

    async def fake_get(self, transaction_id):
        called.append(transaction_id)
        return {"status": "CONFIRMED"}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    resp = _verify(_client(), token, pid)
    assert resp.status_code == 400
    assert resp.json()["ok"] is False
    assert called == []
    assert fulfill_calls == []


def test_verify_and_webhook_are_idempotent(temp_db, monkeypatch, fulfill_calls):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, txid = _seed(temp_db, pid="wa-platega-race")

    async def fake_get(self, transaction_id):
        return {"id": txid, "status": "CONFIRMED", "amount": 150.0, "payload": pid}

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    client = _client()
    first = _verify(client, token, pid)
    second = _verify(client, token, pid)
    assert first.json()["status"] == "confirmed"
    assert second.json()["status"] == "confirmed"
    assert second.json()["key_issued"] is True
    assert len(fulfill_calls) == 1

    flask = _flask_client(temp_db)
    hook = flask.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "id": txid, "amount": 150.0},
        headers={"X-MerchantId": "mid-1", "X-Secret": "real-secret"},
    )
    assert hook.status_code == 200
    assert temp_db.get_pending_status(pid) == "paid"
    assert len(fulfill_calls) == 1


def test_verify_platega_api_error_keeps_pending(temp_db, monkeypatch, fulfill_calls, caplog):
    from shop_bot.modules.platega_api import PlategaAPI

    token, pid, _txid = _seed(temp_db, pid="wa-platega-timeout")

    async def fake_get(self, transaction_id):
        raise TimeoutError("platega timeout")

    monkeypatch.setattr(PlategaAPI, "get_transaction", fake_get)
    resp = _verify(_client(), token, pid)
    assert resp.status_code == 503
    assert resp.json()["ok"] is False
    assert "позже" in resp.json()["error"].lower()
    assert "real-secret" not in resp.json()["error"]
    assert fulfill_calls == []
    assert temp_db.get_pending_status(pid) == "pending"
    assert any("Platega webapp verify: API error" in rec.message for rec in caplog.records)


def test_create_payment_stores_platega_transaction_id(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules.platega_api import PlategaAPI
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="buyer")
    token = issue_auth_token(OWNER_ID)
    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    database.create_plan("PlategaHost", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("PlategaHost")[0]["plan_id"]

    async def fake_create(self, *args, **kwargs):
        return "https://pay.example/x", "plt-created-99"

    async def fake_send(*args, **kwargs):
        return True

    monkeypatch.setattr(PlategaAPI, "create_payment", fake_create)
    monkeypatch.setattr(handlers, "_send_telegram_message", fake_send)

    resp = _client().post(
        "/api/create-payment",
        json={
            "token": token,
            "payment_method": "pay_platega",
            "plan_id": plan_id,
            "action": "new",
        },
    )
    data = resp.json()
    assert data.get("ok") is True, data
    meta = database.get_pending_metadata(data["payment_id"])
    assert meta["platega_transaction_id"] == "plt-created-99"


def test_app_html_has_platega_verify_controls():
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "src/shop_bot/webapp/app.html").read_text(encoding="utf-8")
    assert "Проверить оплату" in html
    assert "/api/webapp/payments/" in html
    assert "verifyPlategaPayment" in html
    assert "verifyPlategaTopUp" in html


def test_normalize_platega_status_mapping():
    from shop_bot.modules.platega_fulfillment import normalize_platega_status, remote_is_canceled

    assert normalize_platega_status("CONFIRMED") == "confirmed"
    assert normalize_platega_status("CANCELED") == "canceled"
    assert normalize_platega_status("CHARGEBACKED") == "canceled"
    assert normalize_platega_status("PENDING") == "pending"
    assert remote_is_canceled({"status": "CANCELED", "payload": "p1"}, "p1") is True
    assert remote_is_canceled({"status": "PENDING", "payload": "p1"}, "p1") is False
    assert remote_is_canceled({"status": "CANCELED", "payload": "other"}, "p1") is False


def test_platega_api_get_transaction_uses_shared_request(monkeypatch):
    import asyncio
    from shop_bot.modules.platega_api import PlategaAPI

    seen = []

    async def fake_request(self, method, endpoint, *, json_data=None):
        seen.append((method, endpoint, json_data))
        return {"id": "abc", "status": "CONFIRMED"}

    monkeypatch.setattr(PlategaAPI, "_request", fake_request)
    api = PlategaAPI("mid", "secret")
    res = asyncio.run(api.get_transaction("abc"))
    assert res["status"] == "CONFIRMED"
    assert seen == [("GET", "/transaction/abc", None)]
