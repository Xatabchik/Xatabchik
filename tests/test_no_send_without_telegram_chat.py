"""Аккаунту без Telegram-чата не пишем — и даже не пробуем.

Аккаунт, зарегистрированный по email, получает синтетический telegram_id из
диапазона 999… (см. `is_email_only_user`). Чата с таким id в Telegram не
существует, поэтому любой sendMessage заведомо отвечает «Bad Request: chat not
found». Раньше и webapp, и бот всё равно делали запрос на каждом платеже:

    xatabchik-webapp | Error sending telegram message: Telegram server says -
                       Bad Request: chat not found
    xatabchik        | Failed to send top-up notification to user
                       999000000003: ... Bad Request: chat not found

Рассылка бота такие аккаунты пропускает ещё до обращения к API
(см. admin_router/mailing.py) — здесь то же сделано для платёжных уведомлений.

Отказ от отправки не должен ничего отменять: счёт создаётся, баланс
зачисляется. Контрольные тесты следят за тем, чтобы обычный Telegram-аккаунт
сообщения по-прежнему получал.
"""
from __future__ import annotations

import asyncio

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

EMAIL_ONLY_ID = 999000000003
TELEGRAM_ID = 74001


class _SpyBot:
    """Заглушка aiogram.Bot, считающая обращения к Telegram API."""

    created: list["_SpyBot"] = []
    sent: list[dict] = []

    def __init__(self, *args, **kwargs):
        type(self).created.append(self)
        self.session = self

    async def send_message(self, **kwargs):
        type(self).sent.append(kwargs)
        return None

    async def send_photo(self, **kwargs):
        type(self).sent.append(kwargs)
        return None

    async def close(self):
        return None


def _spy_bot(monkeypatch, handlers):
    class _Spy(_SpyBot):
        created: list = []
        sent: list = []

    monkeypatch.setattr(handlers, "Bot", _Spy)
    return _Spy


def _configure_yookassa(database) -> None:
    database.update_setting("yookassa_shop_id", "test-shop-id")
    database.update_setting("yookassa_secret_key", "test-secret-key")


class _FakeConfirmation:
    def __init__(self, url: str) -> None:
        self.confirmation_url = url


class _FakePaymentObject:
    id = "yoo-topup-id"

    def __init__(self) -> None:
        self.confirmation = _FakeConfirmation("https://yookassa.test/confirm")


def _stub_yookassa(monkeypatch, handlers) -> None:
    class _FakeYookassaPayment:
        @staticmethod
        def create(payload, idempotence_key=None):
            return _FakePaymentObject()

    monkeypatch.setattr(handlers, "YookassaPayment", _FakeYookassaPayment)


def _top_up(handlers, *, token: str, user_id: int, amount: float = 100.0) -> dict:
    from fastapi.testclient import TestClient

    client = TestClient(handlers.app)
    resp = client.post("/api/create-topup-payment", json={
        "token": token,
        "user_id": user_id,
        "amount": amount,
        "payment_method": "pay_yookassa",
    })
    return resp.json()


# --- webapp -------------------------------------------------------------------


def test_webapp_does_not_ask_telegram_about_an_account_without_chat(temp_db, monkeypatch):
    """Отправка не доходит до API: Bot даже не создаётся."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=EMAIL_ONLY_ID, username="mailonly")
    spy = _spy_bot(monkeypatch, handlers)

    assert asyncio.run(handlers._send_telegram_message(EMAIL_ONLY_ID, "Счёт создан")) is False
    assert spy.created == [], "к Telegram обратились, хотя чата нет"
    assert spy.sent == []


def test_webapp_still_writes_to_a_real_telegram_user(temp_db, monkeypatch):
    """Контроль: обычному пользователю сообщение уходит как раньше."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=TELEGRAM_ID, username="tguser")
    spy = _spy_bot(monkeypatch, handlers)

    assert asyncio.run(handlers._send_telegram_message(TELEGRAM_ID, "Счёт создан")) is True
    assert len(spy.created) == 1
    assert [c["chat_id"] for c in spy.sent] == [TELEGRAM_ID]


def test_topup_invoice_for_an_account_without_chat_is_created_without_telegram(temp_db, monkeypatch):
    """Счёт на пополнение создаётся, но попытки написать в чат нет."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=EMAIL_ONLY_ID, username="mailonly")
    token = issue_auth_token(EMAIL_ONLY_ID)
    _configure_yookassa(database)
    _stub_yookassa(monkeypatch, handlers)
    spy = _spy_bot(monkeypatch, handlers)

    data = _top_up(handlers, token=token, user_id=EMAIL_ONLY_ID)

    assert data.get("ok") is True, data
    assert data.get("payment_url") == "https://yookassa.test/confirm"
    assert data.get("payment_id")
    assert spy.created == [], "webapp дёрнул Telegram на аккаунте без чата"


def test_topup_invoice_for_a_telegram_user_is_still_announced(temp_db, monkeypatch):
    """Контроль: обычному пользователю ссылка на оплату по-прежнему приходит."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=TELEGRAM_ID, username="tguser")
    token = issue_auth_token(TELEGRAM_ID)
    _configure_yookassa(database)
    _stub_yookassa(monkeypatch, handlers)
    spy = _spy_bot(monkeypatch, handlers)

    data = _top_up(handlers, token=token, user_id=TELEGRAM_ID)

    assert data.get("ok") is True, data
    assert [c["chat_id"] for c in spy.sent] == [TELEGRAM_ID]


# --- бот: уведомление о зачислении -------------------------------------------


class _RecordingBot:
    id = 778

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.session = self

    async def send_message(self, *args, **kwargs):
        if args:
            kwargs.setdefault("chat_id", args[0])
            if len(args) > 1:
                kwargs.setdefault("text", args[1])
        self.sent.append(kwargs)
        return None

    async def close(self):
        return None


def _run_top_up(database, *, user_id: int, amount: float = 100.0) -> _RecordingBot:
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    payment_id = f"topup-{user_id}"
    meta = {
        "user_id": user_id,
        "price": amount,
        "action": "top_up",
        "payment_method": "YooKassa",
        "payment_id": payment_id,
    }
    database.create_payload_pending(payment_id, user_id, amount, meta)
    assert database.find_and_complete_pending_transaction(payment_id) is not None

    bot = _RecordingBot()
    asyncio.run(process_successful_payment(bot, meta))
    return bot


def test_top_up_notification_is_skipped_for_an_account_without_chat(temp_db):
    """Баланс зачислен, но в недоступный чат бот не стучался."""
    database = temp_db
    insert_user(database.DB_FILE, telegram_id=EMAIL_ONLY_ID, username="mailonly", balance=0.0)

    bot = _run_top_up(database, user_id=EMAIL_ONLY_ID)

    assert float(database.get_user(EMAIL_ONLY_ID)["balance"]) == 100.0
    assert [s for s in bot.sent if s.get("chat_id") == EMAIL_ONLY_ID] == [], bot.sent


def test_top_up_notification_still_reaches_a_telegram_user(temp_db):
    """Контроль: обычный пользователь узнаёт о зачислении как раньше."""
    database = temp_db
    insert_user(database.DB_FILE, telegram_id=TELEGRAM_ID, username="tguser", balance=0.0)

    bot = _run_top_up(database, user_id=TELEGRAM_ID)

    assert float(database.get_user(TELEGRAM_ID)["balance"]) == 100.0
    mine = [s for s in bot.sent if s.get("chat_id") == TELEGRAM_ID]
    assert len(mine) == 1, bot.sent
    assert "Баланс пополнен на 100.00 RUB" in mine[0]["text"]
