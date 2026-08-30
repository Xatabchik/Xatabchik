"""Неоплаченные счета попадают в историю транзакций вместе с id провайдера."""
from __future__ import annotations

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def test_create_payload_pending_mirrors_unpaid_ledger_with_provider_id(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=93001, username="payer")
    pid = "pay-pending-1"
    database.create_payload_pending(
        pid,
        93001,
        199.0,
        {
            "user_id": 93001,
            "action": "new",
            "price": 199.0,
            "payment_method": "Platega",
            "payment_id": pid,
            "platega_transaction_id": "plt-abc-1",
        },
    )

    rows, total = database.get_transactions_paginated(page=1, per_page=10, user_id=93001)
    assert total == 1
    assert rows[0]["status"] == "pending"
    assert rows[0]["payment_id"] == pid
    assert rows[0]["provider_transaction_id"] == "plt-abc-1"
    assert float(rows[0]["amount_rub"]) == 199.0
    assert rows[0]["payment_method"] == "Platega"


def test_patch_pending_metadata_updates_provider_id_on_ledger(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=93002, username="crypto")
    pid = "pay-crypto-1"
    database.create_payload_pending(
        pid,
        93002,
        50.0,
        {"user_id": 93002, "action": "top_up", "payment_method": "CryptoBot", "payment_id": pid},
    )
    assert database.patch_pending_metadata(pid, {"cryptobot_invoice_id": "778899"})

    rows, _ = database.get_transactions_paginated(page=1, per_page=10, user_id=93002)
    assert rows[0]["status"] == "pending"
    assert rows[0]["provider_transaction_id"] == "778899"


def test_log_transaction_updates_same_pending_row(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=93003, username="paid")
    pid = "pay-same-row"
    database.create_payload_pending(
        pid,
        93003,
        80.0,
        {
            "user_id": 93003,
            "action": "top_up",
            "payment_method": "YooKassa",
            "yookassa_payment_id": "yk-1",
            "payment_id": pid,
        },
    )
    assert database.log_transaction(
        username="paid",
        transaction_id=None,
        payment_id=pid,
        user_id=93003,
        status="paid",
        amount_rub=80.0,
        amount_currency=None,
        currency_name=None,
        payment_method="YooKassa",
        metadata='{"action": "top_up"}',
    )

    rows, total = database.get_transactions_paginated(page=1, per_page=10, user_id=93003)
    assert total == 1
    assert rows[0]["status"] == "paid"
    assert rows[0]["provider_transaction_id"] == "yk-1"


def test_cancel_pending_marks_ledger_cancelled(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=93004, username="stars")
    pid = "pay-stars-1"
    database.create_payload_pending(pid, 93004, 10.0, {"user_id": 93004, "payment_id": pid})
    assert database.cancel_pending_transaction(pid, 93004)

    rows, _ = database.get_transactions_paginated(page=1, per_page=10, user_id=93004)
    assert rows[0]["status"] == "cancelled"


def test_webapp_user_transactions_include_unpaid_and_provider_id(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=93005, username="web")
    token = issue_auth_token(93005)
    pid = "pay-webapp-1"
    database.create_payload_pending(
        pid,
        93005,
        300.0,
        {
            "user_id": 93005,
            "action": "extend",
            "payment_method": "RollyPay",
            "rollypay_payment_id": "rp-55",
            "payment_id": pid,
        },
    )

    client = TestClient(handlers.app)
    resp = client.get(f"/api/user/transactions?token={token}&page=1&per_page=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["total"] == 1
    tx = data["transactions"][0]
    assert tx["status"] == "pending"
    assert tx["status_label"] == "Ожидает оплаты"
    assert tx["provider_transaction_id"] == "rp-55"
    assert tx["payment_id"] == pid


def test_unpaid_does_not_count_as_income(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=93006, username="stats")
    database.create_payload_pending(
        "pay-income-1",
        93006,
        500.0,
        {"user_id": 93006, "payment_method": "Platega", "platega_transaction_id": "x"},
    )
    stats = database.get_admin_stats()
    assert float(stats.get("total_income") or 0) == 0.0
