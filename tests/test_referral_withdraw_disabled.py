"""Вывод реферальных средств: при referral_withdraw_enabled=false
заявки запрещены на API и в БД, а list отдаёт withdraw_enabled=false."""
from conftest import insert_user, temp_db  # noqa: F401


def _auth_token(handlers, user_id: int) -> str:
    token = f"test-ref-withdraw-{user_id}"
    handlers.TEMP_AUTH_TOKENS[token] = user_id
    return token


def test_payout_methods_list_reports_withdraw_disabled(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=61001, username="wd1", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "false")

    client = TestClient(handlers.app)
    token = _auth_token(handlers, 61001)
    resp = client.post("/api/referral/payout-methods/list", json={"token": token})
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("withdraw_enabled") is False


def test_request_withdrawal_rejected_when_disabled(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=61002, username="wd2", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_sbp_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    ok, msg, method_id = database.add_referral_payout_method(
        61002, "sbp", "+79001234567", bank_name="Сбер"
    )
    assert ok and method_id, msg

    database.update_setting("referral_withdraw_enabled", "false")

    client = TestClient(handlers.app)
    token = _auth_token(handlers, 61002)
    resp = client.post(
        "/api/referral/request-withdrawal",
        json={"token": token, "amount": 200, "method_id": method_id},
    )
    data = resp.json()
    assert data.get("ok") is False
    assert "недоступен" in (data.get("error") or data.get("message") or "").lower()

    user = database.get_user(61002)
    assert float(user["referral_balance"]) == 500.0
    assert database.list_referral_withdrawal_requests(user_id=61002) == []


def test_create_withdrawal_db_rejects_when_disabled(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=61003, username="wd3", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    ok, msg, method_id = database.add_referral_payout_method(
        61003, "card", "4111111111111111"
    )
    assert ok and method_id, msg

    database.update_setting("referral_withdraw_enabled", "false")
    ok2, msg2, new_id = database.create_referral_withdrawal_request(61003, 200, method_id)
    assert ok2 is False
    assert new_id is None
    assert "недоступен" in (msg2 or "").lower()
    assert float(database.get_user(61003)["referral_balance"]) == 500.0


def test_request_withdrawal_allowed_when_enabled(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=61004, username="wd4", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    ok, msg, method_id = database.add_referral_payout_method(
        61004, "card", "4111111111111111"
    )
    assert ok and method_id, msg

    client = TestClient(handlers.app)
    token = _auth_token(handlers, 61004)
    resp = client.post(
        "/api/referral/request-withdrawal",
        json={"token": token, "amount": 150, "method_id": method_id},
    )
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("request_id")
    assert float(database.get_user(61004)["referral_balance"]) == 350.0
