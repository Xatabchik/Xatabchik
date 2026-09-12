"""Stars и TON Connect доступны в webapp только из Telegram Mini App.

Инвойс Telegram Stars доставляется сообщением в чат с ботом. Для сессии,
открытой в браузере (вход по email), доставлять его некуда: у email-аккаунта
`telegram_id` синтетический, и Telegram на такой chat_id отвечает «chat not
found». Раньше сервер всё равно создавал pending-транзакцию и пытался отправить
инвойс — пользователь видел «Счёт Stars отправлен в бот», но счёта не было.

Единственный достоверный признак Telegram-контекста — подписанные
`init_data` (HMAC по токену бота + свежесть auth_date). Здесь проверяется, что
опираемся именно на него, а не на persistent auth-токен, не на диапазон
`telegram_id` и не на клиентские поля: обычный Telegram-пользователь может
войти в webapp по email из браузера, и тогда Stars ему тоже недоступен.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from urllib.parse import urlencode

from conftest import (  # noqa: F401
    FAKE_BOT_TOKEN,
    app_client,
    insert_user,
    issue_auth_token,
    make_telegram_init_data,
    no_smtp,
    register_and_verify_email_user,
    temp_db,
)

TELEGRAM_ONLY_ERROR = "Этот способ оплаты доступен только при входе через Telegram."

TG_USER_ID = 71001
OTHER_TG_USER_ID = 71002
HOST = "StarsHost"


def _signed_init_data(user_id: int, *, auth_date: int | None = None, tamper: bool = False) -> str:
    """Как conftest.make_telegram_init_data, но с контролем auth_date и подписи."""
    user_json = json.dumps({"id": user_id, "first_name": "Tg", "username": "tg"}, separators=(",", ":"))
    params = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAA",
        "user": user_json,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", FAKE_BOT_TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if tamper:
        params["hash"] = "0" * 64
    return urlencode(params)


def _enable_stars(database) -> int:
    database.update_setting("stars_enabled", "true")
    database.update_setting("stars_per_rub", "2")
    # TON настроен полностью — проверяем, что его всё равно не предлагают.
    database.update_setting("ton_wallet_address", "EQtest")
    database.update_setting("tonapi_key", "tonapi-test")
    database.create_plan(HOST, "1 месяц", 1, 100.0)
    return database.get_plans_for_host(HOST)[0]["plan_id"]


def _spy_stars_invoice(monkeypatch) -> list[dict]:
    """Перехватывает отправку Stars-инвойса, чтобы не звать настоящий Telegram."""
    from shop_bot.webapp import handlers

    calls: list[dict] = []

    async def fake_invoice(user_id, title, description, payload, amount):
        calls.append({"user_id": user_id, "payload": payload, "amount": amount})
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_invoice)
    return calls


def _pending_rows(database) -> list[tuple]:
    with sqlite3.connect(database.DB_FILE) as conn:
        try:
            return conn.execute("SELECT payment_id, user_id FROM pending_transactions").fetchall()
        except sqlite3.OperationalError:
            return []


def _method_ids(app_client, payload: dict) -> list[str]:
    resp = app_client.post("/api/payment-methods", json=payload)
    data = resp.json()
    assert data.get("ok") is True, data
    return [m["id"] for m in data["methods"]]


def _create_payment(app_client, payload: dict) -> dict:
    base = {"plan_id": payload.pop("plan_id"), "host_name": HOST, "action": "new"}
    return app_client.post("/api/create-payment", json={**base, **payload}).json()


# --- /api/payment-methods -----------------------------------------------------


def test_email_only_user_is_not_offered_stars_or_ton(temp_db, app_client, no_smtp):
    """Вход по email через persistent-токен: Stars и TON в списке отсутствуют."""
    database = temp_db
    _enable_stars(database)
    token, user_id = register_and_verify_email_user(
        app_client, database.DB_FILE, "stars-off@example.com"
    )
    assert database.is_email_only_user(user_id)

    ids = _method_ids(app_client, {"token": token})
    assert "pay_stars" not in ids, ids
    assert "pay_tonconnect" not in ids, ids
    # Обычные методы на месте — скрыли только Telegram-зависимые.
    assert "pay_balance" in ids, ids


def test_telegram_session_without_init_data_is_not_offered_stars(temp_db, app_client):
    """Обычный Telegram-пользователь, но сессия браузерная: Stars не предлагаем.

    Именно этот случай нельзя отличить по `telegram_id` — он настоящий.
    """
    database = temp_db
    _enable_stars(database)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    token = issue_auth_token(TG_USER_ID)

    assert "pay_stars" not in _method_ids(app_client, {"token": token})


def test_telegram_mini_app_is_offered_stars(temp_db, app_client):
    """С валидными init_data Stars остаётся доступным."""
    database = temp_db
    _enable_stars(database)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    token = issue_auth_token(TG_USER_ID)

    ids = _method_ids(
        app_client, {"token": token, "init_data": make_telegram_init_data(TG_USER_ID)}
    )
    assert "pay_stars" in ids, ids


def test_ton_is_never_offered_in_webapp(temp_db, app_client):
    """TON Connect не предлагаем даже в Telegram: поток в webapp не реализован.

    Все три create-эндпоинта отвечают «TON Connect пока недоступен через
    WebApp», поэтому кнопка была заведомо нерабочей.
    """
    database = temp_db
    _enable_stars(database)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    token = issue_auth_token(TG_USER_ID)

    ids = _method_ids(
        app_client, {"token": token, "init_data": make_telegram_init_data(TG_USER_ID)}
    )
    assert "pay_tonconnect" not in ids, ids


# --- /api/create-payment ------------------------------------------------------


def test_email_only_user_cannot_create_stars_payment(temp_db, app_client, no_smtp, monkeypatch):
    """Ручной запрос Stars от email-аккаунта: отказ, ни pending, ни инвойса."""
    database = temp_db
    plan_id = _enable_stars(database)
    invoices = _spy_stars_invoice(monkeypatch)
    token, user_id = register_and_verify_email_user(
        app_client, database.DB_FILE, "stars-manual@example.com"
    )

    data = _create_payment(
        app_client, {"plan_id": plan_id, "token": token, "payment_method": "pay_stars"}
    )
    assert data == {"ok": False, "error": TELEGRAM_ONLY_ERROR}, data
    assert invoices == [], "инвойс не должен даже пытаться уйти"
    assert _pending_rows(database) == [], "pending-транзакция не должна создаваться"


def test_telegram_user_without_init_data_cannot_create_stars_payment(
    temp_db, app_client, monkeypatch
):
    """Persistent-токен сам по себе не доказывает, что сессия открыта из Telegram."""
    database = temp_db
    plan_id = _enable_stars(database)
    invoices = _spy_stars_invoice(monkeypatch)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    token = issue_auth_token(TG_USER_ID)

    data = _create_payment(
        app_client, {"plan_id": plan_id, "token": token, "payment_method": "pay_stars"}
    )
    assert data == {"ok": False, "error": TELEGRAM_ONLY_ERROR}, data
    assert invoices == []
    assert _pending_rows(database) == []


def test_valid_telegram_context_passes_the_stars_check(temp_db, app_client, monkeypatch):
    """Валидные init_data того же пользователя — Stars создаётся как раньше."""
    database = temp_db
    plan_id = _enable_stars(database)
    invoices = _spy_stars_invoice(monkeypatch)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    token = issue_auth_token(TG_USER_ID)

    data = _create_payment(
        app_client,
        {
            "plan_id": plan_id,
            "token": token,
            "init_data": make_telegram_init_data(TG_USER_ID),
            "payment_method": "pay_stars",
        },
    )
    assert data.get("ok") is True, data
    assert len(invoices) == 1, invoices
    assert invoices[0]["user_id"] == TG_USER_ID
    assert invoices[0]["amount"] == 200  # 100 RUB * stars_per_rub=2
    assert [row[1] for row in _pending_rows(database)] == [TG_USER_ID]


def test_tampered_expired_or_foreign_init_data_is_rejected(temp_db, app_client, monkeypatch):
    """Подделанная подпись, просроченный auth_date и чужой аккаунт — отказ."""
    database = temp_db
    plan_id = _enable_stars(database)
    invoices = _spy_stars_invoice(monkeypatch)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    insert_user(database.DB_FILE, telegram_id=OTHER_TG_USER_ID, username="other", balance=500.0)
    token = issue_auth_token(TG_USER_ID)

    variants = {
        "подделанный hash": _signed_init_data(TG_USER_ID, tamper=True),
        "просроченный auth_date": _signed_init_data(TG_USER_ID, auth_date=int(time.time()) - 3600),
        "init_data другого пользователя": _signed_init_data(OTHER_TG_USER_ID),
    }
    for label, init_data in variants.items():
        data = _create_payment(
            app_client,
            {
                "plan_id": plan_id,
                "token": token,
                "init_data": init_data,
                "payment_method": "pay_stars",
            },
        )
        assert data == {"ok": False, "error": TELEGRAM_ONLY_ERROR}, (label, data)

    assert invoices == []
    assert _pending_rows(database) == []


def test_ton_is_refused_without_creating_pending(temp_db, app_client, no_smtp):
    """TON: вне Telegram — telegram-only отказ, внутри — прежнее «недоступен».

    Ни в одном из случаев pending-транзакция не создаётся, то есть видимость
    работающего метода не появляется.
    """
    database = temp_db
    plan_id = _enable_stars(database)
    insert_user(database.DB_FILE, telegram_id=TG_USER_ID, username="tguser", balance=500.0)
    tg_token = issue_auth_token(TG_USER_ID)
    email_token, _ = register_and_verify_email_user(
        app_client, database.DB_FILE, "ton@example.com"
    )

    from_browser = _create_payment(
        app_client,
        {"plan_id": plan_id, "token": email_token, "payment_method": "pay_tonconnect"},
    )
    assert from_browser == {"ok": False, "error": TELEGRAM_ONLY_ERROR}, from_browser

    from_telegram = _create_payment(
        app_client,
        {
            "plan_id": plan_id,
            "token": tg_token,
            "init_data": make_telegram_init_data(TG_USER_ID),
            "payment_method": "pay_tonconnect",
        },
    )
    assert from_telegram.get("ok") is False, from_telegram
    assert "TON Connect" in from_telegram.get("error", ""), from_telegram

    assert _pending_rows(database) == []


# --- пополнение баланса и докупка LTE ----------------------------------------


def test_topup_and_lte_endpoints_refuse_stars_outside_telegram(
    temp_db, app_client, no_smtp, monkeypatch
):
    """Проверка стоит во всех трёх create-эндпоинтах, а не только в основном."""
    database = temp_db
    _enable_stars(database)
    invoices = _spy_stars_invoice(monkeypatch)
    token, _ = register_and_verify_email_user(
        app_client, database.DB_FILE, "topup-stars@example.com"
    )

    topup = app_client.post(
        "/api/create-topup-payment",
        json={"token": token, "amount": 300, "payment_method": "pay_stars"},
    ).json()
    assert topup == {"ok": False, "error": TELEGRAM_ONLY_ERROR}, topup

    lte = app_client.post(
        "/api/create-lte-topup-payment",
        json={"token": token, "key_id": 1, "package_id": 1, "payment_method": "pay_stars"},
    ).json()
    assert lte == {"ok": False, "error": TELEGRAM_ONLY_ERROR}, lte

    assert invoices == []
    assert _pending_rows(database) == []
