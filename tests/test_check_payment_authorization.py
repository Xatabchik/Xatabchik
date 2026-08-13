"""Регрессия H4: POST /api/check-payment без auth палил статус чужого uuid.

До фикса любой, кто знал payment_id, получал paid true/false. Соседние
user-API после PR #63 требуют токен; этот эндпоинт — нет.

Дополнительно (не из исходной формулировки H4): TON Connect пишет в
``transactions`` строку со status='pending' до ончейн-подтверждения, а
``check_transaction_exists`` не фильтровал статус → paid: true сразу
после создания счёта. TON-вебхук ставит status='paid'.
"""
from __future__ import annotations

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


OWNER_ID = 92001
ATTACKER_ID = 92002
WEBAPP_PID = "11111111-2222-3333-4444-555555555555"
TON_PID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _check(client, payload: dict):
    return client.post("/api/check-payment", json=payload)


def _seed_users(database):
    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="payowner", balance=10.0)
    insert_user(database.DB_FILE, telegram_id=ATTACKER_ID, username="payattacker", balance=99.0)
    return issue_auth_token(OWNER_ID), issue_auth_token(ATTACKER_ID)


def _webapp_pending(database, *, payment_id: str, user_id: int, status_paid: bool = False):
    database.create_payload_pending(
        payment_id,
        user_id,
        150.0,
        {"user_id": user_id, "price": 150.0, "payment_method": "YooKassa", "payment_id": payment_id},
    )
    if status_paid:
        meta = database.find_and_complete_pending_transaction(payment_id)
        assert meta is not None


def _ton_pending(database, *, payment_id: str, user_id: int):
    database.create_pending_transaction(
        payment_id,
        user_id,
        200.0,
        {"user_id": user_id, "expected_amount_ton": 1.0, "payment_method": "TON Connect"},
    )


def test_unauthenticated_check_payment_does_not_reveal_paid_status(temp_db):
    """Без токена — тот же ответ, что для неизвестного id (не 401 и не paid:true)."""
    database = temp_db
    _seed_users(database)
    _webapp_pending(database, payment_id=WEBAPP_PID, user_id=OWNER_ID, status_paid=True)

    client = _client()
    unknown = _check(client, {"payment_id": "00000000-0000-0000-0000-000000000000"})
    bare = _check(client, {"payment_id": WEBAPP_PID})

    assert unknown.status_code == 200
    assert unknown.json() == {"ok": True, "paid": False}
    assert bare.status_code == unknown.status_code
    assert bare.json() == unknown.json()
    assert bare.json().get("paid") is False
    assert "balance" not in bare.json()


def test_other_user_cannot_see_foreign_payment_status(temp_db):
    """Токен A + payment_id B (уже paid) → paid: false, без баланса жертвы."""
    database = temp_db
    owner_token, attacker_token = _seed_users(database)
    _webapp_pending(database, payment_id=WEBAPP_PID, user_id=OWNER_ID, status_paid=True)

    client = _client()
    resp = _check(client, {"payment_id": WEBAPP_PID, "token": attacker_token})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "paid": False}

    own = _check(client, {"payment_id": WEBAPP_PID, "token": owner_token})
    assert own.json().get("ok") is True
    assert own.json().get("paid") is True


def test_owner_pending_then_paid_polling_happy_path(temp_db):
    """Легитимный поллинг: pending → paid:false; после complete → paid:true + свой баланс."""
    database = temp_db
    owner_token, _ = _seed_users(database)
    _webapp_pending(database, payment_id=WEBAPP_PID, user_id=OWNER_ID, status_paid=False)

    client = _client()
    pending = _check(client, {"payment_id": WEBAPP_PID, "token": owner_token})
    assert pending.status_code == 200
    assert pending.json().get("ok") is True
    assert pending.json().get("paid") is False

    assert database.find_and_complete_pending_transaction(WEBAPP_PID) is not None

    paid = _check(client, {"payment_id": WEBAPP_PID, "token": owner_token})
    data = paid.json()
    assert data.get("ok") is True
    assert data.get("paid") is True
    assert data.get("message") == "Оплата успешно подтверждена"
    assert data.get("balance") == 10.0


def test_ton_pending_row_is_not_paid(temp_db):
    """Строка TON в transactions со status=pending не считается оплатой."""
    database = temp_db
    owner_token, _ = _seed_users(database)
    _ton_pending(database, payment_id=TON_PID, user_id=OWNER_ID)

    assert database.check_transaction_exists(TON_PID) is False

    resp = _check(_client(), {"payment_id": TON_PID, "token": owner_token})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "paid": False}


def test_ton_paid_status_is_paid_true(temp_db):
    """После TON-вебхука (status='paid') владелец получает paid: true."""
    database = temp_db
    owner_token, attacker_token = _seed_users(database)
    _ton_pending(database, payment_id=TON_PID, user_id=OWNER_ID)
    meta = database.find_and_complete_ton_transaction(TON_PID, 1.0)
    assert meta is not None
    assert database.check_transaction_exists(TON_PID) is True

    client = _client()
    own = _check(client, {"payment_id": TON_PID, "token": owner_token})
    data = own.json()
    assert data.get("ok") is True
    assert data.get("paid") is True
    assert data.get("balance") == 10.0

    foreign = _check(client, {"payment_id": TON_PID, "token": attacker_token})
    assert foreign.json() == {"ok": True, "paid": False}
