"""UX/FSM Telegram Stars в покупке ключа: скрыть старые pay_*, Back под invoice.

До фикса create_stars_invoice_handler слал invoice и делал state.clear(),
а сообщение «Выберите удобный способ оплаты» оставляло клавиатуру pay_*.
Нажатие pay_balance после Stars не попадало в PaymentProcess-хендлер и
уходило в admin-фильтр («У вас нет прав»).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    AnswerCallbackQuery,
    AnswerPreCheckoutQuery,
    DeleteMessage,
    EditMessageReplyMarkup,
    EditMessageText,
    SendInvoice,
    SendMessage,
    TelegramMethod,
)
from aiogram.methods.base import TelegramType
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    PreCheckoutQuery,
    Update,
    User,
)

from conftest import insert_user, temp_db  # noqa: F401

USER_ID = 55101
_TEST_BOT_TOKEN = "123456789:AATestTokenForStarsInvoiceBack"
STALE_ALERT = "Сессия оплаты устарела. Выберите тариф и способ оплаты заново."


class _RecordingSession(BaseSession):
    def __init__(self) -> None:
        super().__init__()
        self.methods: list[TelegramMethod[Any]] = []

    async def close(self) -> None:
        return None

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: Optional[int] = None,
    ) -> TelegramType:
        self.methods.append(method)
        if isinstance(method, SendInvoice):
            return Message(
                message_id=99,
                date=datetime.now(timezone.utc),
                chat=Chat(id=USER_ID, type="private"),
            )
        return True  # type: ignore[return-value]

    async def stream_content(  # type: ignore[override]
        self,
        url: str,
        headers: Optional[dict[str, Any]] = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ):
        if False:
            yield b""


def _user() -> User:
    return User(id=USER_ID, is_bot=False, first_name="Buyer")


def _chat() -> Chat:
    return Chat(id=USER_ID, type="private")


def _message(*, message_id: int = 1) -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=_chat(),
        from_user=_user(),
    )


def _seed_plan(database) -> int:
    from shop_bot.data_manager import remnawave_repository as rw_repo

    insert_user(database.DB_FILE, telegram_id=USER_ID, username="starbuyer", balance=500.0)
    database.create_plan("StarsHost", "1 месяц", 1, 100.0)
    database.update_setting("stars_per_rub", "2")
    database.update_setting("stars_enabled", "true")
    rw_repo.create_promo_code("SAVE10", discount_percent=10)
    return database.get_plans_for_host("StarsHost")[0]["plan_id"]


async def _prepare_purchase_fsm(bot: Bot, storage: MemoryStorage, plan_id: int, **extra):
    from shop_bot.bot.handlers import PaymentProcess

    key = StorageKey(bot_id=bot.id, chat_id=USER_ID, user_id=USER_ID)
    from aiogram.fsm.context import FSMContext

    ctx = FSMContext(storage=storage, key=key)
    await ctx.set_state(PaymentProcess.waiting_for_payment_method)
    payload = {
        "plan_id": plan_id,
        "host_name": "StarsHost",
        "action": "new",
        "key_id": 0,
        "final_price": 100.0,
        "customer_email": "buyer@example.com",
        "promo_code": "SAVE10",
        "promo_discount": 10.0,
    }
    payload.update(extra)
    await ctx.update_data(**payload)
    return ctx


def _run(coro):
    return asyncio.run(coro)


def test_stars_invoice_keyboard_has_pay_then_back():
    from shop_bot.bot.keyboards import create_stars_invoice_keyboard

    markup = create_stars_invoice_keyboard()
    rows = markup.inline_keyboard
    assert rows[0][0].pay is True
    assert rows[1][0].callback_data == "payment_stars_back"
    assert "Назад" in (rows[1][0].text or "")


def test_pay_stars_removes_old_keyboard_and_sends_invoice_with_back(temp_db):
    from shop_bot.bot.handlers import PaymentProcess, get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        ctx = await _prepare_purchase_fsm(bot, storage, plan_id)
        cb = CallbackQuery(
            id="cb-stars",
            from_user=_user(),
            chat_instance="inst",
            data="pay_stars",
            message=_message(message_id=10),
        )
        await dp.feed_update(bot, Update(update_id=1, callback_query=cb))
        return ctx

    ctx = _run(_go())
    data = asyncio.run(ctx.get_data())
    state = asyncio.run(ctx.get_state())

    assert any(isinstance(m, DeleteMessage) or isinstance(m, EditMessageReplyMarkup) for m in session.methods), session.methods
    invoices = [m for m in session.methods if isinstance(m, SendInvoice)]
    assert len(invoices) == 1
    inv = invoices[0]
    assert inv.currency == "XTR"
    markup = inv.reply_markup
    assert markup is not None
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert any(getattr(btn, "pay", False) for btn in buttons)
    assert any(getattr(btn, "callback_data", None) == "payment_stars_back" for btn in buttons)
    assert state == PaymentProcess.waiting_for_stars_invoice.state
    assert data.get("plan_id") == plan_id
    assert data.get("promo_code") == "SAVE10"
    assert data.get("stars_payment_id")
    assert database.get_pending_status(data["stars_payment_id"]) == "pending"


def test_stars_back_cancels_pending_and_restores_methods(temp_db):
    from shop_bot.bot.handlers import PaymentProcess, get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        ctx = await _prepare_purchase_fsm(bot, storage, plan_id)
        await dp.feed_update(
            bot,
            Update(
                update_id=1,
                callback_query=CallbackQuery(
                    id="cb-stars",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_stars",
                    message=_message(message_id=10),
                ),
            ),
        )
        data = await ctx.get_data()
        pid = data["stars_payment_id"]
        session.methods.clear()
        await dp.feed_update(
            bot,
            Update(
                update_id=2,
                callback_query=CallbackQuery(
                    id="cb-back",
                    from_user=_user(),
                    chat_instance="inst",
                    data="payment_stars_back",
                    message=_message(message_id=99),
                ),
            ),
        )
        return ctx, pid

    ctx, pid = _run(_go())
    assert database.get_pending_status(pid) == "cancelled"
    assert database.find_and_complete_pending_transaction(pid) is None
    state = asyncio.run(ctx.get_state())
    data = asyncio.run(ctx.get_data())
    assert state == PaymentProcess.waiting_for_payment_method.state
    assert data.get("plan_id") == plan_id
    assert data.get("promo_code") == "SAVE10"
    assert data.get("host_name") == "StarsHost"
    assert data.get("action") == "new"
    assert data.get("customer_email") == "buyer@example.com"
    assert any(isinstance(m, DeleteMessage) for m in session.methods)
    restored = [
        m
        for m in session.methods
        if isinstance(m, (EditMessageText, SendMessage))
        and "Выберите удобный способ оплаты" in (getattr(m, "text", None) or "")
    ]
    assert restored, session.methods


def test_pay_balance_works_after_stars_back(temp_db, monkeypatch):
    from shop_bot.bot import handlers as handlers_mod
    from shop_bot.bot.handlers import get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    psp: list[dict] = []
    deducts: list[tuple] = []

    def _deduct(user_id, amount):
        deducts.append((user_id, amount))
        return True

    async def _psp(bot, metadata):
        psp.append(metadata)
        return True

    monkeypatch.setattr(handlers_mod, "deduct_from_balance", _deduct)
    monkeypatch.setattr(handlers_mod, "process_successful_payment", _psp)

    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        ctx = await _prepare_purchase_fsm(bot, storage, plan_id)
        await dp.feed_update(
            bot,
            Update(
                update_id=1,
                callback_query=CallbackQuery(
                    id="cb-stars",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_stars",
                    message=_message(message_id=10),
                ),
            ),
        )
        await dp.feed_update(
            bot,
            Update(
                update_id=2,
                callback_query=CallbackQuery(
                    id="cb-back",
                    from_user=_user(),
                    chat_instance="inst",
                    data="payment_stars_back",
                    message=_message(message_id=99),
                ),
            ),
        )
        await dp.feed_update(
            bot,
            Update(
                update_id=3,
                callback_query=CallbackQuery(
                    id="cb-bal",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_balance",
                    message=_message(message_id=11),
                ),
            ),
        )
        return ctx

    _run(_go())
    assert deducts == [(USER_ID, 90.0)]
    assert len(psp) == 1
    assert psp[0]["payment_method"] == "Balance"
    assert psp[0]["user_id"] == USER_ID


def test_stale_pay_balance_after_stars_does_not_charge(temp_db, monkeypatch):
    from shop_bot.bot import handlers as handlers_mod
    from shop_bot.bot.handlers import get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    deducts: list = []
    psp: list = []
    monkeypatch.setattr(handlers_mod, "deduct_from_balance", lambda *a, **k: deducts.append(a) or True)
    monkeypatch.setattr(handlers_mod, "process_successful_payment", lambda *a, **k: psp.append(a) or True)

    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        await _prepare_purchase_fsm(bot, storage, plan_id)
        await dp.feed_update(
            bot,
            Update(
                update_id=1,
                callback_query=CallbackQuery(
                    id="cb-stars",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_stars",
                    message=_message(message_id=10),
                ),
            ),
        )
        session.methods.clear()
        await dp.feed_update(
            bot,
            Update(
                update_id=2,
                callback_query=CallbackQuery(
                    id="cb-stale",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_balance",
                    message=_message(message_id=10),
                ),
            ),
        )

    _run(_go())
    assert deducts == []
    assert psp == []
    answers = [m for m in session.methods if isinstance(m, AnswerCallbackQuery)]
    assert any(getattr(m, "text", None) == STALE_ALERT and getattr(m, "show_alert", False) for m in answers), session.methods


def test_stars_back_is_idempotent(temp_db):
    from shop_bot.bot.handlers import PaymentProcess, get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        ctx = await _prepare_purchase_fsm(bot, storage, plan_id)
        await dp.feed_update(
            bot,
            Update(
                update_id=1,
                callback_query=CallbackQuery(
                    id="cb-stars",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_stars",
                    message=_message(message_id=10),
                ),
            ),
        )
        data = await ctx.get_data()
        pid = data["stars_payment_id"]
        for i, cb_id in enumerate(("cb-back1", "cb-back2"), start=2):
            await dp.feed_update(
                bot,
                Update(
                    update_id=i,
                    callback_query=CallbackQuery(
                        id=cb_id,
                        from_user=_user(),
                        chat_instance="inst",
                        data="payment_stars_back",
                        message=_message(message_id=99),
                    ),
                ),
            )
        return ctx, pid

    ctx, pid = _run(_go())
    assert database.get_pending_status(pid) == "cancelled"
    assert asyncio.run(ctx.get_state()) == PaymentProcess.waiting_for_payment_method.state
    assert asyncio.run(ctx.get_data()).get("plan_id") == plan_id


def test_stars_back_after_paid_does_not_change_anything(temp_db, monkeypatch):
    from shop_bot.bot import handlers as handlers_mod
    from shop_bot.bot.handlers import get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    psp: list = []
    monkeypatch.setattr(handlers_mod, "process_successful_payment", lambda *a, **k: psp.append(1) or True)
    monkeypatch.setattr(handlers_mod, "deduct_from_balance", lambda *a, **k: (_ for _ in ()).throw(AssertionError("deduct")))

    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        ctx = await _prepare_purchase_fsm(bot, storage, plan_id)
        await dp.feed_update(
            bot,
            Update(
                update_id=1,
                callback_query=CallbackQuery(
                    id="cb-stars",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_stars",
                    message=_message(message_id=10),
                ),
            ),
        )
        data = await ctx.get_data()
        pid = data["stars_payment_id"]
        assert database.find_and_complete_pending_transaction(pid) is not None
        await ctx.clear()
        balance_before = database.get_balance(USER_ID)
        session.methods.clear()
        await dp.feed_update(
            bot,
            Update(
                update_id=2,
                callback_query=CallbackQuery(
                    id="cb-back-paid",
                    from_user=_user(),
                    chat_instance="inst",
                    data="payment_stars_back",
                    message=_message(message_id=99),
                ),
            ),
        )
        return pid, balance_before

    pid, balance_before = _run(_go())
    assert database.get_pending_status(pid) == "paid"
    assert database.get_balance(USER_ID) == balance_before
    assert psp == []
    answers = [m for m in session.methods if isinstance(m, AnswerCallbackQuery)]
    assert answers
    assert not any(isinstance(m, SendInvoice) for m in session.methods)


def test_pre_checkout_rejects_cancelled_stars_invoice(temp_db):
    from shop_bot.bot.handlers import get_user_router
    from shop_bot.data_manager import database

    plan_id = _seed_plan(database)
    session = _RecordingSession()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(get_user_router())
    bot = Bot(token=_TEST_BOT_TOKEN, session=session)

    async def _go():
        ctx = await _prepare_purchase_fsm(bot, storage, plan_id)
        await dp.feed_update(
            bot,
            Update(
                update_id=1,
                callback_query=CallbackQuery(
                    id="cb-stars",
                    from_user=_user(),
                    chat_instance="inst",
                    data="pay_stars",
                    message=_message(message_id=10),
                ),
            ),
        )
        pid = (await ctx.get_data())["stars_payment_id"]
        await dp.feed_update(
            bot,
            Update(
                update_id=2,
                callback_query=CallbackQuery(
                    id="cb-back",
                    from_user=_user(),
                    chat_instance="inst",
                    data="payment_stars_back",
                    message=_message(message_id=99),
                ),
            ),
        )
        session.methods.clear()
        pcq = PreCheckoutQuery(
            id="pcq-1",
            from_user=_user(),
            currency="XTR",
            total_amount=200,
            invoice_payload=pid,
        )
        await dp.feed_update(bot, Update(update_id=3, pre_checkout_query=pcq))
        return pid

    pid = _run(_go())
    assert database.get_pending_status(pid) == "cancelled"
    answers = [m for m in session.methods if isinstance(m, AnswerPreCheckoutQuery)]
    assert answers
    assert answers[0].ok is False


def test_cancel_pending_does_not_touch_paid_row(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=USER_ID, username="x")
    pid = "paid-keep"
    database.create_payload_pending(pid, USER_ID, 10.0, {"user_id": USER_ID, "payment_id": pid})
    assert database.find_and_complete_pending_transaction(pid) is not None
    assert database.cancel_pending_transaction(pid, USER_ID) is False
    assert database.get_pending_status(pid) == "paid"
