"""/api/check-payment показывает успех только после фактической выдачи услуги.

Раньше достаточным условием для ``paid: true`` было
``pending_transactions.status == 'paid'``. Но этот статус означает лишь, что
подтверждение платежа принято: выдача (создание ключа, зачисление баланса,
применение докупки) идёт уже после него и может упасть. В результате webapp
показывал «Оплата успешно подтверждена», хотя ключа не существовало — в том
числе навсегда, если выдача сорвалась.

Признак успеха теперь — финальная запись в ledger ``transactions`` со
status='paid' по тому же payment_id (её пишет log_transaction в самом конце
process_successful_payment) плюс непогашенный idempotency-lock в
``processed_payments``. Компенсирующие ветви при сбое выдачи лок снимают, а до
финальной записи не доходят.

Выдача здесь запускается настоящим `process_successful_payment`, а не
имитацией, чтобы критерий проверялся против реального кода.
"""
from __future__ import annotations

import asyncio

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

OWNER_ID = 73001
STRANGER_ID = 73002
HOST = "FulfillHost"


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _check(payload: dict) -> dict:
    return _client().post("/api/check-payment", json=payload).json()


def _fake_bot(monkeypatch, *, panel_result):
    """Бот-заглушка и панель Remnawave с управляемым результатом."""

    class _FakeMessage:
        async def edit_text(self, text, **kwargs):
            return None

        async def delete(self):
            return None

    class _FakeBot:
        id = 777

        def __init__(self, *args, **kwargs):
            self.session = self

        async def send_message(self, *args, **kwargs):
            return _FakeMessage()

        async def send_photo(self, *args, **kwargs):
            return _FakeMessage()

        async def close(self):
            return None

    async def fake_create(*args, **kwargs):
        return panel_result

    monkeypatch.setattr(
        "shop_bot.modules.remnawave_api.create_or_update_key_on_host", fake_create
    )
    return _FakeBot()


def _panel_ok(marker: str = "ok") -> dict:
    sub_url = f"https://vpn.example/sub/{marker}"
    return {
        "client_uuid": f"uuid-{marker}",
        "short_uuid": f"short-{marker}",
        "email": f"{marker}@bot.local",
        "host_name": HOST,
        "squad_uuid": "squad-1",
        "subscription_url": sub_url,
        "connection_string": sub_url,
        "traffic_limit_bytes": None,
        "traffic_limit_strategy": None,
        "expiry_timestamp_ms": 1893456000000,
    }


def _seed(database, *, with_plan: bool = True):
    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner", balance=10.0)
    insert_user(database.DB_FILE, telegram_id=STRANGER_ID, username="stranger", balance=99.0)
    database.update_setting("telegram_bot_token", "123456:FAKE_BOT_TOKEN_FOR_TESTS")
    plan_id = None
    if with_plan:
        database.create_plan(HOST, "1 месяц", 1, 100.0)
        plan_id = database.get_plans_for_host(HOST)[0]["plan_id"]
    return issue_auth_token(OWNER_ID), issue_auth_token(STRANGER_ID), plan_id


def _confirmed_invoice(database, *, payment_id: str, meta: dict, amount: float):
    """Счёт создан и оплата подтверждена вебхуком — но выдача ещё не начиналась."""
    database.create_payload_pending(payment_id, OWNER_ID, amount, meta)
    assert database.find_and_complete_pending_transaction(payment_id) is not None
    assert (database.get_pending_status(payment_id) or "").lower() == "paid"


def _key_purchase_meta(payment_id: str, plan_id: int) -> dict:
    return {
        "user_id": OWNER_ID,
        "months": 1,
        "duration_days": 0,
        "price": 100.0,
        "action": "new",
        "key_id": None,
        "host_name": HOST,
        "plan_id": plan_id,
        "payment_method": "YooKassa",
        "payment_id": payment_id,
    }


def _top_up_meta(payment_id: str) -> dict:
    return {
        "user_id": OWNER_ID,
        "price": 300.0,
        "action": "top_up",
        "payment_method": "YooKassa",
        "payment_id": payment_id,
    }


# --- подтверждение платежа само по себе не успех ------------------------------


def test_confirmed_but_not_fulfilled_is_not_paid(temp_db):
    """pending уже 'paid', выдача ещё не прошла → paid остаётся false."""
    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "aaaa0000-0000-0000-0000-000000000001"
    _confirmed_invoice(
        database, payment_id=pid, meta=_key_purchase_meta(pid, plan_id), amount=100.0
    )

    data = _check({"payment_id": pid, "token": owner_token})
    assert data.get("paid") is False, data
    assert data.get("processing") is True, data
    assert data.get("message") == "Оплата получена, услуга ещё обрабатывается."
    # Главное: старого ложного сообщения об успехе больше нет.
    assert data.get("message") != "Оплата успешно подтверждена"
    assert database.get_user_keys(OWNER_ID) == []


def test_failed_fulfillment_never_reports_paid(temp_db, monkeypatch):
    """Панель не создала ключ → компенсация, и успех не показывается никогда."""
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "aaaa0000-0000-0000-0000-000000000002"
    meta = _key_purchase_meta(pid, plan_id)
    _confirmed_invoice(database, payment_id=pid, meta=meta, amount=100.0)

    bot = _fake_bot(monkeypatch, panel_result=None)
    assert asyncio.run(process_successful_payment(bot, meta)) is False

    assert database.get_user_keys(OWNER_ID) == []
    data = _check({"payment_id": pid, "token": owner_token})
    assert data.get("paid") is False, data


# --- успешная выдача: покупка ключа и пополнение баланса ----------------------


def test_key_purchase_is_paid_only_after_the_key_exists(temp_db, monkeypatch):
    """Покупка ключа: до выдачи — processing, после — paid: true."""
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "aaaa0000-0000-0000-0000-000000000003"
    meta = _key_purchase_meta(pid, plan_id)
    _confirmed_invoice(database, payment_id=pid, meta=meta, amount=100.0)

    assert _check({"payment_id": pid, "token": owner_token}).get("paid") is False

    bot = _fake_bot(monkeypatch, panel_result=_panel_ok("keypaid"))
    assert asyncio.run(process_successful_payment(bot, meta)) is True

    keys = database.get_user_keys(OWNER_ID)
    assert len(keys) == 1, keys

    data = _check({"payment_id": pid, "token": owner_token})
    assert data.get("ok") is True, data
    assert data.get("paid") is True, data
    assert data.get("message") == "Оплата успешно подтверждена"
    assert "processing" not in data


def test_top_up_is_paid_only_after_balance_is_credited(temp_db, monkeypatch):
    """Пополнение баланса: тот же критерий работает и для второго пути."""
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    database = temp_db
    owner_token, _, _ = _seed(database, with_plan=False)
    pid = "aaaa0000-0000-0000-0000-000000000004"
    meta = _top_up_meta(pid)
    _confirmed_invoice(database, payment_id=pid, meta=meta, amount=300.0)

    before = _check({"payment_id": pid, "token": owner_token})
    assert before.get("paid") is False, before
    assert before.get("processing") is True, before
    assert float(database.get_user(OWNER_ID)["balance"]) == 10.0

    bot = _fake_bot(monkeypatch, panel_result=None)
    asyncio.run(process_successful_payment(bot, meta))

    assert float(database.get_user(OWNER_ID)["balance"]) == 310.0

    data = _check({"payment_id": pid, "token": owner_token})
    assert data.get("paid") is True, data
    assert data.get("balance") == 310.0


# --- чужой payment_id ---------------------------------------------------------


def test_foreign_payment_id_gets_the_same_neutral_answer(temp_db, monkeypatch):
    """Чужой и несуществующий id отвечают одинаково — ни статуса, ни processing."""
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    database = temp_db
    owner_token, stranger_token, plan_id = _seed(database)
    pid = "aaaa0000-0000-0000-0000-000000000005"
    meta = _key_purchase_meta(pid, plan_id)
    _confirmed_invoice(database, payment_id=pid, meta=meta, amount=100.0)

    unknown = _check({"payment_id": "ffffffff-ffff-ffff-ffff-ffffffffffff", "token": stranger_token})
    assert unknown == {"ok": True, "paid": False}, unknown

    # Пока выдача не прошла: владелец видит processing, чужой — нейтральный ответ.
    assert _check({"payment_id": pid, "token": owner_token}).get("processing") is True
    foreign_processing = _check({"payment_id": pid, "token": stranger_token})
    assert foreign_processing == unknown, foreign_processing

    bot = _fake_bot(monkeypatch, panel_result=_panel_ok("foreign"))
    assert asyncio.run(process_successful_payment(bot, meta)) is True

    # После выдачи чужой ответ по-прежнему неотличим от «нет такого платежа».
    assert _check({"payment_id": pid, "token": owner_token}).get("paid") is True
    foreign_paid = _check({"payment_id": pid, "token": stranger_token})
    assert foreign_paid == unknown, foreign_paid
    assert "balance" not in foreign_paid
