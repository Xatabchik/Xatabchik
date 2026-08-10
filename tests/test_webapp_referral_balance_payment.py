"""
Оплата реферальным балансом в WebApp (зеркало bot pay_referral_balance).

Покрывает:
1. /api/payment-methods отдаёт pay_referral_balance с текущим балансом
2. /api/create-payment списывает реферальный баланс и вызывает process_successful_payment
3. Недостаточно средств → ошибка без списания
4. /api/create-topup-payment отклоняет pay_referral_balance
"""
from conftest import insert_user, temp_db  # noqa: F401


def test_payment_methods_includes_referral_balance(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51001, username="refpay", referral_balance=150.0)

    client = TestClient(handlers.app)
    resp = client.post("/api/payment-methods", json={"user_id": 51001})
    data = resp.json()
    assert data.get("ok") is True, data
    methods = {m["id"]: m for m in data.get("methods") or []}
    assert "pay_referral_balance" in methods
    assert methods["pay_referral_balance"]["balance"] == 150.0
    assert "150" in methods["pay_referral_balance"]["name"]
    assert data.get("referral_balance") == 150.0


def test_create_payment_with_referral_balance_success(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51002, username="refpay2", referral_balance=200.0)
    database.create_plan("RefHost", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("RefHost")[0]["plan_id"]

    captured = []

    async def fake_process(bot, meta):
        captured.append(meta)

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 51002,
        "payment_method": "pay_referral_balance",
        "plan_id": plan_id,
        "host_name": "RefHost",
        "action": "new",
    })
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("paid") is True
    assert len(captured) == 1
    assert captured[0]["payment_method"] == "ReferralBalance"
    assert captured[0]["price"] == 100.0
    assert str(captured[0]["payment_id"]).startswith("referral_balance:51002:")

    user = database.get_user(51002)
    assert float(user["referral_balance"]) == 100.0


def test_create_payment_referral_balance_insufficient(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51003, username="refpay3", referral_balance=10.0)
    database.create_plan("RefHost2", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("RefHost2")[0]["plan_id"]

    called = []

    async def fake_process(bot, meta):
        called.append(meta)

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 51003,
        "payment_method": "pay_referral_balance",
        "plan_id": plan_id,
        "action": "new",
    })
    data = resp.json()
    assert data.get("ok") is False
    assert "реферальн" in (data.get("error") or "").lower()
    assert called == []
    user = database.get_user(51003)
    assert float(user["referral_balance"]) == 10.0


def test_create_payment_referral_balance_refunds_on_processing_error(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51004, username="refpay4", referral_balance=200.0)
    database.create_plan("RefHost3", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("RefHost3")[0]["plan_id"]

    async def boom(bot, meta):
        raise RuntimeError("provision failed")

    monkeypatch.setattr(handlers, "process_successful_payment", boom)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 51004,
        "payment_method": "pay_referral_balance",
        "plan_id": plan_id,
        "action": "new",
    })
    data = resp.json()
    assert data.get("ok") is False
    user = database.get_user(51004)
    assert float(user["referral_balance"]) == 200.0, "средства должны вернуться при ошибке обработки"


def test_topup_rejects_referral_balance_method(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51005, username="refpay5", referral_balance=500.0)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-topup-payment", json={
        "user_id": 51005,
        "payment_method": "pay_referral_balance",
        "amount": 100,
    })
    data = resp.json()
    assert data.get("ok") is False
    assert "баланс" in (data.get("error") or "").lower()
