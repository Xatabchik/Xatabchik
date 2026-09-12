"""Регрессия H4: POST /api/check-payment без auth палил статус чужого uuid.

До фикса любой, кто знал payment_id, получал paid true/false. Соседние
user-API после PR #63 требуют токен; этот эндпоинт — нет.

Дополнительно (не из исходной формулировки H4): TON Connect пишет в
``transactions`` строку со status='pending' до ончейн-подтверждения, а
``check_transaction_exists`` не фильтровал статус → paid: true сразу
после создания счёта. TON-вебхук ставит status='paid'.

ВНИМАНИЕ про ожидания ниже: часть тестов этого файла раньше утверждала, что
подтверждения платежа достаточно для ``paid: true``. Это и есть исправленное
ложноположительное срабатывание (см. tests/test_check_payment_fulfilled.py):
подтверждение оплаты и выдача услуги — разные события. Проверки безопасности
(чужой/анонимный запрос получает нейтральный ответ) остались без изменений,
поменялись только ожидания для ВЛАДЕЛЬЦА платежа.
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


def _simulate_successful_fulfillment(database, *, payment_id: str, user_id: int, amount: float):
    """Повторить то, что делает process_successful_payment при успешной выдаче.

    Нужны ровно два следа: idempotency-lock (берётся в начале выдачи и
    снимается компенсацией при сбое) и финальная запись в ledger со
    status='paid' по тому же payment_id (пишется последней, уже после того как
    услуга оказана).
    """
    assert database.claim_processed_payment(payment_id) is True
    assert database.log_transaction(
        username="payowner",
        transaction_id=None,
        payment_id=payment_id,
        user_id=user_id,
        status="paid",
        amount_rub=amount,
        amount_currency=None,
        currency_name=None,
        payment_method="YooKassa",
        metadata='{"action": "top_up"}',
    ) is True


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
    """Токен A + payment_id B (уже выданный) → нейтральный ответ, без баланса жертвы."""
    database = temp_db
    owner_token, attacker_token = _seed_users(database)
    _webapp_pending(database, payment_id=WEBAPP_PID, user_id=OWNER_ID, status_paid=True)
    _simulate_successful_fulfillment(
        database, payment_id=WEBAPP_PID, user_id=OWNER_ID, amount=150.0
    )

    client = _client()
    resp = _check(client, {"payment_id": WEBAPP_PID, "token": attacker_token})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "paid": False}

    own = _check(client, {"payment_id": WEBAPP_PID, "token": owner_token})
    assert own.json().get("ok") is True
    assert own.json().get("paid") is True


def test_owner_pending_then_paid_polling_happy_path(temp_db):
    """Легитимный поллинг владельца: счёт создан → оплата принята → услуга выдана."""
    database = temp_db
    owner_token, _ = _seed_users(database)
    _webapp_pending(database, payment_id=WEBAPP_PID, user_id=OWNER_ID, status_paid=False)

    client = _client()
    pending = _check(client, {"payment_id": WEBAPP_PID, "token": owner_token})
    assert pending.status_code == 200
    assert pending.json() == {"ok": True, "paid": False}

    assert database.find_and_complete_pending_transaction(WEBAPP_PID) is not None

    # Оплата принята, но услуга ещё не выдана — успех показывать нельзя.
    processing = _check(client, {"payment_id": WEBAPP_PID, "token": owner_token})
    assert processing.json().get("paid") is False
    assert processing.json().get("processing") is True

    _simulate_successful_fulfillment(
        database, payment_id=WEBAPP_PID, user_id=OWNER_ID, amount=150.0
    )

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


def test_ton_webhook_confirmation_alone_is_not_paid_true(temp_db):
    """TON-вебхук ставит status='paid' в transactions ДО выдачи — это не успех.

    Для TON подтверждение и выдача пишут в одну и ту же строку ``transactions``,
    поэтому одного status='paid' недостаточно: нужен ещё idempotency-lock,
    который берётся уже внутри выдачи.
    """
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
    assert data.get("paid") is False
    assert data.get("processing") is True
    assert "balance" not in data

    foreign = _check(client, {"payment_id": TON_PID, "token": attacker_token})
    assert foreign.json() == {"ok": True, "paid": False}


def test_ton_paid_after_fulfillment_is_paid_true(temp_db):
    """После того как выдача по TON-платежу завершилась, владелец видит paid: true."""
    database = temp_db
    owner_token, attacker_token = _seed_users(database)
    _ton_pending(database, payment_id=TON_PID, user_id=OWNER_ID)
    assert database.find_and_complete_ton_transaction(TON_PID, 1.0) is not None
    _simulate_successful_fulfillment(
        database, payment_id=TON_PID, user_id=OWNER_ID, amount=200.0
    )

    client = _client()
    data = _check(client, {"payment_id": TON_PID, "token": owner_token}).json()
    assert data.get("ok") is True
    assert data.get("paid") is True
    assert data.get("balance") == 10.0

    foreign = _check(client, {"payment_id": TON_PID, "token": attacker_token})
    assert foreign.json() == {"ok": True, "paid": False}
