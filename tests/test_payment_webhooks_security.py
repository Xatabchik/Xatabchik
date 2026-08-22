"""
Регрессия hardening платёжных вебхуков (Приоритет 1 аудита):

- POST /platega-webhook: пустые credentials → 403; compare_digest; сверка суммы
  и payment_method с pending.
- POST /yoomoney-webhook: пустой secret / выключенный флаг → 403; сверка суммы;
  hmac.compare_digest для sha1_hash.
- POST /heleket-webhook: order_id + pending + сумма, затем find_and_complete
  (больше не fulfill из description JSON в обход pending).
- POST /cryptobot-webhook: разбор Crypto Pay `{result: {items: [...]}}` и
  отказ закрыть pending при несовпадении суммы.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal

from conftest import temp_db  # noqa: F401


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


def _pending(*, payment_id: str, user_id: int, amount: float, method: str) -> None:
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


def _yoomoney_form(label: str, amount: str, secret: str) -> dict:
    form = {
        "notification_type": "p2p-incoming",
        "operation_id": "op-1",
        "amount": amount,
        "currency": "643",
        "datetime": "2026-08-12T00:00:00.000Z",
        "sender": "410011111111111",
        "codepro": "false",
        "label": label,
    }
    signature_str = "&".join(
        [
            form["notification_type"],
            form["operation_id"],
            form["amount"],
            form["currency"],
            form["datetime"],
            form["sender"],
            form["codepro"],
            secret,
            form["label"],
        ]
    )
    form["sha1_hash"] = hashlib.sha1(signature_str.encode("utf-8")).hexdigest()
    return form


def _heleket_signed_body(payload: dict, api_key: str) -> dict:
    body = dict(payload)
    body.pop("sign", None)
    sorted_data_str = json.dumps(body, sort_keys=True, separators=(",", ":"))
    b64 = base64.b64encode(sorted_data_str.encode()).decode()
    body["sign"] = hashlib.md5(f"{b64}{api_key}".encode()).hexdigest()
    return body


def _cryptobot_signature(raw_body: bytes, token: str) -> str:
    secret = hashlib.sha256(token.encode("utf-8")).digest()
    return hmac.new(secret, raw_body, hashlib.sha256).hexdigest()


# ----- helpers (pure) -----


def test_pending_method_allowed_matches_platega_and_crypto():
    from shop_bot.webhook_server.app import _pending_method_allowed

    assert _pending_method_allowed({"payment_method": "Platega"}, "Platega", "Platega Crypto")
    assert _pending_method_allowed({"payment_method": "Platega Crypto"}, "Platega", "Platega Crypto")
    assert not _pending_method_allowed({"payment_method": "YooKassa"}, "Platega", "Platega Crypto")
    assert not _pending_method_allowed(None, "Platega")


def test_extract_platega_webhook_amount_reads_top_level_and_details():
    from shop_bot.webhook_server.app import _extract_platega_webhook_amount

    assert _extract_platega_webhook_amount({"amount": 150.5}) == 150.5
    assert _extract_platega_webhook_amount({"paymentDetails": {"amount": "99.00"}}) == "99.00"
    assert _extract_platega_webhook_amount({}) is None


def test_pending_expected_amount_uses_price():
    from shop_bot.webhook_server.app import _pending_expected_amount

    assert _pending_expected_amount({"price": "100.00"}) == Decimal("100.00")
    assert _pending_expected_amount({"amount_rub": 50}) == Decimal("50.00")


# ----- Platega -----


def test_platega_webhook_empty_credentials_returns_403(temp_db, caplog):
    """Старый код пропускал пустые X-MerchantId/X-Secret, если настройки пустые."""
    pid = "platega-empty-creds"
    _pending(payment_id=pid, user_id=101, amount=500.0, method="YooKassa")
    client = _flask_client(temp_db)

    with caplog.at_level("ERROR"):
        resp = client.post(
            "/platega-webhook",
            json={"status": "CONFIRMED", "payload": pid, "id": "tx-1", "amount": 500.0},
            headers={"X-MerchantId": "", "X-Secret": ""},
        )
    assert resp.status_code == 403
    assert _pending_status(pid) == "pending"
    assert any("Platega webhook отключён: не настроены credentials" in rec.message for rec in caplog.records)


def test_platega_webhook_wrong_secret_returns_401(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    pid = "platega-wrong-secret"
    _pending(payment_id=pid, user_id=102, amount=100.0, method="Platega")
    client = _flask_client(temp_db)

    resp = client.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "amount": 100.0},
        headers={"X-MerchantId": "mid-1", "X-Secret": "nope"},
    )
    assert resp.status_code == 401
    assert _pending_status(pid) == "pending"


def test_platega_amount_covers_order_allows_provider_fee():
    from shop_bot.webhook_server.app import _platega_amount_covers_order

    assert _platega_amount_covers_order(Decimal("100.00"), Decimal("100.00")) is True
    assert _platega_amount_covers_order(Decimal("107.00"), Decimal("100.00")) is True
    assert _platega_amount_covers_order(Decimal("99.99"), Decimal("100.00")) is False


def test_platega_webhook_rejects_amount_mismatch(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    pid = "platega-underpay"
    _pending(payment_id=pid, user_id=103, amount=500.0, method="Platega")
    client = _flask_client(temp_db)

    resp = client.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "id": "tx-2", "amount": 1.0},
        headers={"X-MerchantId": "mid-1", "X-Secret": "real-secret"},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_platega_webhook_completes_when_callback_amount_includes_fee(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    pid = "platega-fee-ok"
    _pending(payment_id=pid, user_id=108, amount=100.0, method="Platega")
    client = _flask_client(temp_db)

    resp = client.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "id": "tx-fee", "amount": 107.0},
        headers={"X-MerchantId": "mid-1", "X-Secret": "real-secret"},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_platega_webhook_rejects_other_provider_pending(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    pid = "platega-cross-provider"
    _pending(payment_id=pid, user_id=104, amount=200.0, method="YooKassa")
    client = _flask_client(temp_db)

    resp = client.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "amount": 200.0},
        headers={"X-MerchantId": "mid-1", "X-Secret": "real-secret"},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_platega_webhook_completes_matching_platega_pending(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    pid = "platega-ok"
    _pending(payment_id=pid, user_id=105, amount=150.0, method="Platega")
    client = _flask_client(temp_db)

    resp = client.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "id": "tx-ok", "amount": 150.0, "currency": "RUB"},
        headers={"X-MerchantId": "mid-1", "X-Secret": "real-secret"},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_platega_webhook_completes_platega_crypto_pending(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("platega_merchant_id", "mid-1")
    database.update_setting("platega_secret", "real-secret")
    pid = "platega-crypto-ok"
    _pending(payment_id=pid, user_id=106, amount=80.0, method="Platega Crypto")
    client = _flask_client(temp_db)

    resp = client.post(
        "/platega-webhook",
        json={"status": "CONFIRMED", "payload": pid, "amount": "80.00"},
        headers={"X-MerchantId": "mid-1", "X-Secret": "real-secret"},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


# ----- YooMoney -----


def test_yoomoney_webhook_empty_secret_returns_403(temp_db):
    """Старый код считал sha1 с пустым secret — подпись можно было подделать."""
    from shop_bot.data_manager import database

    database.update_setting("yoomoney_enabled", "true")
    database.update_setting("yoomoney_secret", "")
    pid = "ym-empty-secret"
    _pending(payment_id=pid, user_id=201, amount=300.0, method="YooMoney")
    client = _flask_client(temp_db)

    form = _yoomoney_form(pid, "300.00", secret="")
    resp = client.post("/yoomoney-webhook", data=form)
    assert resp.status_code == 403
    assert _pending_status(pid) == "pending"


def test_yoomoney_webhook_disabled_flag_returns_403(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("yoomoney_enabled", "false")
    database.update_setting("yoomoney_secret", "ym-secret")
    pid = "ym-disabled"
    _pending(payment_id=pid, user_id=202, amount=300.0, method="YooMoney")
    client = _flask_client(temp_db)

    form = _yoomoney_form(pid, "300.00", secret="ym-secret")
    resp = client.post("/yoomoney-webhook", data=form)
    assert resp.status_code == 403
    assert _pending_status(pid) == "pending"


def test_yoomoney_webhook_rejects_amount_mismatch(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("yoomoney_enabled", "true")
    database.update_setting("yoomoney_secret", "ym-secret")
    pid = "ym-underpay"
    _pending(payment_id=pid, user_id=203, amount=5000.0, method="YooMoney")
    client = _flask_client(temp_db)

    form = _yoomoney_form(pid, "1.00", secret="ym-secret")
    resp = client.post("/yoomoney-webhook", data=form)
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_yoomoney_webhook_completes_matching_amount(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("yoomoney_enabled", "true")
    database.update_setting("yoomoney_secret", "ym-secret")
    pid = "ym-ok"
    _pending(payment_id=pid, user_id=204, amount=250.0, method="YooMoney")
    client = _flask_client(temp_db)

    form = _yoomoney_form(pid, "250.00", secret="ym-secret")
    resp = client.post("/yoomoney-webhook", data=form)
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_yoomoney_webhook_rejects_wrong_hash(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("yoomoney_enabled", "true")
    database.update_setting("yoomoney_secret", "ym-secret")
    pid = "ym-bad-hash"
    _pending(payment_id=pid, user_id=205, amount=250.0, method="YooMoney")
    client = _flask_client(temp_db)

    form = _yoomoney_form(pid, "250.00", secret="ym-secret")
    form["sha1_hash"] = "0" * 40
    resp = client.post("/yoomoney-webhook", data=form)
    assert resp.status_code == 403
    assert _pending_status(pid) == "pending"


# ----- Heleket -----


def test_heleket_webhook_does_not_fulfill_from_description_without_pending_match(temp_db):
    """Старый код dispatch'ил metadata из description, минуя pending."""
    from shop_bot.data_manager import database

    database.update_setting("heleket_api_key", "heleket-key")
    pid = "heleket-no-pending"
    client = _flask_client(temp_db)

    payload = {
        "uuid": "hk-1",
        "order_id": pid,
        "amount": "100.00",
        "status": "paid",
        "description": json.dumps(
            {"user_id": 301, "price": 100.0, "payment_method": "Heleket", "payment_id": pid, "action": "new"}
        ),
    }
    resp = client.post("/heleket-webhook", json=_heleket_signed_body(payload, "heleket-key"))
    assert resp.status_code == 200
    assert _pending_status(pid) is None


def test_heleket_webhook_rejects_amount_mismatch(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("heleket_api_key", "heleket-key")
    pid = "heleket-underpay"
    _pending(payment_id=pid, user_id=302, amount=400.0, method="Heleket")
    client = _flask_client(temp_db)

    payload = {
        "uuid": "hk-2",
        "order_id": pid,
        "amount": "1.00",
        "status": "paid",
        "description": json.dumps({"payment_id": pid, "price": 400.0}),
    }
    resp = client.post("/heleket-webhook", json=_heleket_signed_body(payload, "heleket-key"))
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_heleket_webhook_completes_pending_on_matching_order_id_and_amount(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("heleket_api_key", "heleket-key")
    pid = "heleket-ok"
    _pending(payment_id=pid, user_id=303, amount=120.0, method="Heleket")
    client = _flask_client(temp_db)

    payload = {
        "uuid": "hk-ok",
        "order_id": pid,
        "amount": "120.00",
        "status": "paid",
        "description": json.dumps({"payment_id": pid, "price": 120.0, "payment_method": "Heleket"}),
    }
    resp = client.post("/heleket-webhook", json=_heleket_signed_body(payload, "heleket-key"))
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_heleket_webhook_rejects_other_provider_pending(temp_db):
    from shop_bot.data_manager import database

    database.update_setting("heleket_api_key", "heleket-key")
    pid = "heleket-cross"
    _pending(payment_id=pid, user_id=304, amount=120.0, method="YooKassa")
    client = _flask_client(temp_db)

    payload = {"uuid": "hk-x", "order_id": pid, "amount": "120.00", "status": "paid"}
    resp = client.post("/heleket-webhook", json=_heleket_signed_body(payload, "heleket-key"))
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


# ----- CryptoBot -----


def test_cryptobot_webhook_parses_result_items_and_rejects_amount_mismatch(temp_db, monkeypatch):
    """Старый код ждал result как list и никогда не сверял сумму с getInvoices."""
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    token = "cb-token"
    database.update_setting("cryptobot_token", token)
    pid = "cb-underpay"
    _pending(payment_id=pid, user_id=401, amount=300.0, method="CryptoBot")

    invoice_payload = {
        "ok": True,
        "result": {"items": [{"status": "paid", "amount": "1.00", "fiat": "RUB"}]},
    }

    class _Resp:
        def read(self):
            return json.dumps(invoice_payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(wh_mod.urllib.request, "urlopen", lambda *a, **k: _Resp())

    client = _flask_client(temp_db)
    body = {
        "update_type": "invoice_paid",
        "payload": {"invoice_id": 999, "payload": pid},
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    resp = client.post(
        "/cryptobot-webhook",
        data=raw,
        content_type="application/json",
        headers={"crypto-pay-api-signature": _cryptobot_signature(raw, token)},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"


def test_cryptobot_webhook_completes_when_items_amount_matches(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    token = "cb-token"
    database.update_setting("cryptobot_token", token)
    pid = "cb-ok"
    _pending(payment_id=pid, user_id=402, amount=300.0, method="CryptoBot")

    invoice_payload = {
        "ok": True,
        "result": {"items": [{"status": "paid", "amount": "300.00", "fiat": "RUB"}]},
    }

    class _Resp:
        def read(self):
            return json.dumps(invoice_payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(wh_mod.urllib.request, "urlopen", lambda *a, **k: _Resp())

    client = _flask_client(temp_db)
    body = {
        "update_type": "invoice_paid",
        "payload": {"invoice_id": 1001, "payload": pid},
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    resp = client.post(
        "/cryptobot-webhook",
        data=raw,
        content_type="application/json",
        headers={"crypto-pay-api-signature": _cryptobot_signature(raw, token)},
    )
    assert resp.status_code == 200
    assert _pending_status(pid) == "paid"


def test_cryptobot_webhook_logs_and_refuses_when_invoice_unparseable(temp_db, monkeypatch, caplog):
    """result-as-list (баг старого парсера) больше не считается успешной сверкой."""
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    token = "cb-token"
    database.update_setting("cryptobot_token", token)
    pid = "cb-bad-shape"
    _pending(payment_id=pid, user_id=403, amount=300.0, method="CryptoBot")

    invoice_payload = {
        "ok": True,
        "result": [{"status": "paid", "amount": "300.00", "fiat": "RUB"}],
    }

    class _Resp:
        def read(self):
            return json.dumps(invoice_payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(wh_mod.urllib.request, "urlopen", lambda *a, **k: _Resp())

    client = _flask_client(temp_db)
    body = {
        "update_type": "invoice_paid",
        "payload": {"invoice_id": 1002, "payload": pid},
    }
    raw = json.dumps(body, separators=(",", ":")).encode()
    with caplog.at_level("WARNING"):
        resp = client.post(
            "/cryptobot-webhook",
            data=raw,
            content_type="application/json",
            headers={"crypto-pay-api-signature": _cryptobot_signature(raw, token)},
        )
    assert resp.status_code == 200
    assert _pending_status(pid) == "pending"
    assert any("amount verification failed" in rec.message for rec in caplog.records)
