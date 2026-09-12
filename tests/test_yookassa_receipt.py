"""Регрессия: платежи YooKassa из webapp уходили без чека.

`/api/create-payment` и `/api/create-lte-topup-payment` формировали payload без
поля `receipt`, хотя магазину с включённой фискализацией (54-ФЗ) чек обязателен.
Создание платежа падало на стороне YooKassa:

    YooKassa error: {'type': 'error', 'description': 'Receipt is missing or
    illegal', 'parameter': 'receipt', 'code': 'invalid_request'}

Эндпоинт при этом отвечал HTTP 200 с `{"ok": false, ...}`, то есть оплатить
подписку из webapp было нельзя вообще. Пополнение баланса
(`/api/create-topup-payment`) чек уже отправляло — расхождение между соседними
эндпоинтами одного файла.
"""
from __future__ import annotations

import pytest

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

RECEIPT_EMAIL = "receipts@example.com"


class _FakeConfirmation:
    def __init__(self, url: str) -> None:
        self.confirmation_url = url


class _FakePaymentObject:
    def __init__(self) -> None:
        self.id = "yoo-test-payment-id"
        self.confirmation = _FakeConfirmation("https://yookassa.test/confirm")


def _stub_yookassa(monkeypatch, handlers) -> list[dict]:
    """Перехватить payload, уходящий в YooKassa, без обращения к сети."""
    created: list[dict] = []

    class _FakeYookassaPayment:
        @staticmethod
        def create(payload, idempotence_key=None):
            created.append(payload)
            return _FakePaymentObject()

    monkeypatch.setattr(handlers, "YookassaPayment", _FakeYookassaPayment)

    async def _fake_send(*args, **kwargs):
        return True

    monkeypatch.setattr(handlers, "_send_telegram_message", _fake_send)
    return created


def _configure_yookassa(database, *, receipt_email: str | None) -> None:
    database.update_setting("yookassa_shop_id", "test-shop-id")
    database.update_setting("yookassa_secret_key", "test-secret-key")
    database.update_setting("telegram_bot_username", "TestVpnBot")
    if receipt_email is not None:
        database.update_setting("receipt_email", receipt_email)


def _buy_subscription(handlers, token: str, plan_id: int, user_id: int) -> dict:
    from fastapi.testclient import TestClient

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": user_id,
        "token": token,
        "payment_method": "pay_yookassa",
        "plan_id": plan_id,
        "action": "new",
    })
    return resp.json()


def test_subscription_payment_includes_receipt(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=43001, username="yoouser")
    token = issue_auth_token(43001)
    _configure_yookassa(database, receipt_email=RECEIPT_EMAIL)
    database.create_plan("YooHost", "3 месяца", 3, 300.0)
    plan_id = database.get_plans_for_host("YooHost")[0]["plan_id"]

    created = _stub_yookassa(monkeypatch, handlers)
    data = _buy_subscription(handlers, token, plan_id, 43001)

    assert data.get("ok") is True, data
    assert len(created) == 1
    payload = created[0]
    assert "receipt" in payload, "чек не отправлен — YooKassa ответит Receipt is missing"

    receipt = payload["receipt"]
    assert receipt["customer"]["email"] == RECEIPT_EMAIL
    assert len(receipt["items"]) == 1
    item = receipt["items"][0]
    assert item["description"] == "Подписка на 3 месяца"
    assert item["quantity"] == "1.00"
    assert item["vat_code"] == "1"
    assert item["payment_subject"] == "service"
    assert item["payment_mode"] == "full_payment"


def test_receipt_total_matches_payment_amount(temp_db, monkeypatch):
    """Сумма позиций должна совпадать с суммой платежа, иначе чек отклоняется."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=43002, username="yoouser2")
    token = issue_auth_token(43002)
    _configure_yookassa(database, receipt_email=RECEIPT_EMAIL)
    database.create_plan("YooHost2", "1 месяц", 1, 149.5)
    plan_id = database.get_plans_for_host("YooHost2")[0]["plan_id"]

    created = _stub_yookassa(monkeypatch, handlers)
    data = _buy_subscription(handlers, token, plan_id, 43002)

    assert data.get("ok") is True, data
    payload = created[0]
    assert payload["receipt"]["items"][0]["amount"] == payload["amount"]


def test_no_receipt_when_receipt_email_cleared(temp_db, monkeypatch):
    """Почту для чеков можно очистить ('-' в админке сохраняет пустую строку).

    Магазину без фискализации чек не нужен, и платёж должен уходить как раньше —
    то же поведение, что у бота.
    """
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=43003, username="yoouser3")
    token = issue_auth_token(43003)
    _configure_yookassa(database, receipt_email="")
    database.create_plan("YooHost3", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("YooHost3")[0]["plan_id"]

    created = _stub_yookassa(monkeypatch, handlers)
    data = _buy_subscription(handlers, token, plan_id, 43003)

    assert data.get("ok") is True, data
    assert "receipt" not in created[0]


def test_receipt_is_sent_with_default_receipt_email(temp_db, monkeypatch):
    """По умолчанию настройка заполнена плейсхолдером, а не пуста.

    Значит на чистой установке чек уходит, а не пропускается, — иначе фикс не
    помог бы магазину с фискализацией до ручной настройки почты.
    """
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    assert database.get_setting("receipt_email") == "example@example.com"

    insert_user(database.DB_FILE, telegram_id=43004, username="yoouser4")
    token = issue_auth_token(43004)
    _configure_yookassa(database, receipt_email=None)
    database.create_plan("YooHost4", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("YooHost4")[0]["plan_id"]

    created = _stub_yookassa(monkeypatch, handlers)
    data = _buy_subscription(handlers, token, plan_id, 43004)

    assert data.get("ok") is True, data
    assert created[0]["receipt"]["customer"]["email"] == "example@example.com"


@pytest.mark.parametrize("email", ["", "   ", "not-an-email", None])
def test_helper_skips_receipt_for_unusable_email(temp_db, monkeypatch, email):
    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "get_setting", lambda key, *a, **k: email)
    assert handlers._yookassa_receipt("Подписка на 1 месяц", "100.00") is None


def test_helper_builds_receipt_for_configured_email(temp_db, monkeypatch):
    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "get_setting", lambda key, *a, **k: RECEIPT_EMAIL)
    receipt = handlers._yookassa_receipt("Докупка 10 ГБ LTE-трафика", "250.00")

    assert receipt is not None
    assert receipt["customer"] == {"email": RECEIPT_EMAIL}
    assert receipt["items"][0]["description"] == "Докупка 10 ГБ LTE-трафика"
    assert receipt["items"][0]["amount"] == {"value": "250.00", "currency": "RUB"}
