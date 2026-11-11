"""Докупка LTE-гигабайт через YooKassa в боте передаёт чек 54-ФЗ.

Без `receipt` магазин с фискализацией отклоняет платёж:
400 `Receipt is missing or illegal`.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from conftest import temp_db  # noqa: F401
from shop_bot.bot.user_router import lte_topup
from shop_bot.bot.user_router.formatting import build_yookassa_receipt


def _handler():
    from shop_bot.bot.handlers import get_user_router

    router = get_user_router()
    for h in router.observers["callback_query"].handlers:
        if getattr(h.callback, "__name__", "") == "ltegb_pay_yookassa_handler":
            return h.callback
    raise AssertionError("ltegb_pay_yookassa_handler не зарегистрирован")


def _callback():
    message = SimpleNamespace(
        answer=AsyncMock(),
        edit_text=AsyncMock(),
        chat=SimpleNamespace(id=100),
        message_id=7,
    )
    return SimpleNamespace(
        answer=AsyncMock(),
        from_user=SimpleNamespace(id=42),
        message=message,
    )


def _state():
    return SimpleNamespace(
        get_data=AsyncMock(return_value={
            "lte_package_price": 99,
            "lte_package_size_gb": 5,
            "lte_key_id": 11,
            "lte_package_id": "p5",
        }),
        clear=AsyncMock(),
    )


@pytest.fixture
def yookassa(monkeypatch):
    settings = {"yookassa_shop_id": "shop", "yookassa_secret_key": "secret", "receipt_email": "shop@example.com"}
    pending = MagicMock()
    payment_cls = MagicMock()
    payment_cls.create.return_value = SimpleNamespace(
        id="2f0e1c5a-000f-5000-9000-1b2c3d4e5f60",
        confirmation=SimpleNamespace(confirmation_url="https://yoomoney.example/pay"),
    )
    monkeypatch.setattr(lte_topup, "get_setting", lambda key: settings.get(key))
    monkeypatch.setattr(lte_topup, "create_payload_pending", pending)
    monkeypatch.setattr(lte_topup, "Payment", payment_cls)
    monkeypatch.setattr(lte_topup.keyboards, "create_yookassa_payment_keyboard", lambda *a, **k: None)
    return SimpleNamespace(settings=settings, pending=pending, payment=payment_cls)


def test_lte_gb_yookassa_payment_includes_receipt(temp_db, yookassa):
    asyncio.run(_handler()(_callback(), _state()))

    yookassa.payment.create.assert_called_once()
    payload = yookassa.payment.create.call_args.args[0]
    assert payload["amount"] == {"value": "99.00", "currency": "RUB"}
    assert payload["receipt"] == build_yookassa_receipt(
        "shop@example.com", "Докупка 5 ГБ LTE-трафика", "99.00"
    )


@pytest.mark.parametrize("email", [None, "", "not-an-email"])
def test_lte_gb_yookassa_without_valid_receipt_email_creates_nothing(temp_db, yookassa, email):
    yookassa.settings["receipt_email"] = email
    callback = _callback()
    state = _state()

    asyncio.run(_handler()(callback, state))

    yookassa.payment.create.assert_not_called()
    yookassa.pending.assert_not_called()
    callback.message.answer.assert_awaited_once()
    assert "email для чека" in callback.message.answer.await_args.args[0]
    state.clear.assert_awaited_once()
