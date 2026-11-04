"""gift_catcher не должен перехватывать команды.

Хендлер ловит любой текст без FSM и стоит в user_router, который подключён
раньше admin_router. Если он матчит команду, aiogram на нём останавливает
поиск, и /recheck_payment до админского хендлера не доходит.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from aiogram import Bot, Dispatcher, Router, types
from aiogram.client.session.base import BaseSession
from aiogram.filters import Command
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetMe, SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, Message, Update, User

from conftest import insert_user, temp_db  # noqa: F401

ADMIN_ID = 77101
USER_ID = 88101
BOT_USERNAME = "TestVpnBot"
_TEST_BOT_TOKEN = "123456789:AATestTokenForGiftCatcherCommands"


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
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="Bot", username=BOT_USERNAME)  # type: ignore[return-value]
        if isinstance(method, SendMessage):
            return Message(  # type: ignore[return-value]
                message_id=900 + len(self.methods),
                date=datetime.now(timezone.utc),
                chat=Chat(id=int(method.chat_id), type="private"),
                text=method.text,
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


def _message(user_id: int, text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=user_id, type="private"),
        from_user=User(id=user_id, is_bot=False, first_name="Test"),
        text=text,
    )


def _feed(routers: list[Router], user_id: int, text: str, *, state: str | None = None) -> _RecordingSession:
    session = _RecordingSession()

    async def _run() -> None:
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        for router in routers:
            dp.include_router(router)
        bot = Bot(token=_TEST_BOT_TOKEN, session=session)
        if state is not None:
            key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
            await storage.set_state(key, state)
        await dp.feed_update(bot, Update(update_id=1, message=_message(user_id, text)))

    asyncio.run(_run())
    return session


def _next_router_with_command(seen: list[str]) -> Router:
    """Роутер после user_router с тем же фильтром, что у /recheck_payment."""
    router = Router()

    @router.message(Command(commands=["recheck_payment"]))
    async def _handler(message: types.Message):
        seen.append(message.text or "")

    return router


def _sent_texts(session: _RecordingSession) -> list[str]:
    return [m.text for m in session.methods if isinstance(m, SendMessage)]


def _gift_pending(monkeypatch) -> list[dict]:
    from shop_bot.bot.user_router import gift_catcher
    from shop_bot.modules import remnawave_api

    pending = {"type": "gift", "host_name": "h1", "months": 1, "payment_id": "gift-test-pid"}
    monkeypatch.setattr(gift_catcher, "get_latest_pending_for_user", lambda uid: dict(pending))
    calls: list[dict] = []

    async def _fake_create(**kwargs):
        calls.append(kwargs)
        return {"client_uuid": "u", "email": kwargs.get("email")}

    monkeypatch.setattr(remnawave_api, "create_or_update_key_on_host", _fake_create)
    return calls


@pytest.mark.parametrize(
    "text",
    ["/recheck_payment p-123", "/recheck_payment", f"/recheck_payment@{BOT_USERNAME} p-123"],
)
def test_command_passes_gift_catcher_to_next_router(temp_db, monkeypatch, text):
    from shop_bot.bot.handlers import get_user_router

    insert_user(temp_db.DB_FILE, telegram_id=USER_ID, username="buyer_one")
    create_calls = _gift_pending(monkeypatch)
    seen: list[str] = []
    session = _feed([get_user_router(), _next_router_with_command(seen)], USER_ID, text)
    assert seen == [text]
    assert create_calls == []
    assert not any("Подарочный ключ" in (t or "") for t in _sent_texts(session))


def test_command_from_unregistered_user_is_not_swallowed_by_gift_catcher(temp_db, monkeypatch):
    from shop_bot.bot.handlers import get_user_router

    seen: list[str] = []
    session = _feed([get_user_router(), _next_router_with_command(seen)], USER_ID, "/recheck_payment p-1")
    assert seen == ["/recheck_payment p-1"]
    assert not any("/start" in (t or "") for t in _sent_texts(session))


def test_recipient_username_still_handled_by_gift_catcher(temp_db, monkeypatch):
    from shop_bot.bot.handlers import get_user_router

    insert_user(temp_db.DB_FILE, telegram_id=USER_ID, username="buyer_one")
    create_calls = _gift_pending(monkeypatch)
    seen: list[str] = []
    session = _feed([get_user_router(), _next_router_with_command(seen)], USER_ID, "@recipient_user")
    assert seen == []
    assert len(create_calls) == 1
    assert any("@recipient_user" in (t or "") for t in _sent_texts(session))


def test_gift_catcher_still_requires_registration(temp_db, monkeypatch):
    from shop_bot.bot.handlers import get_user_router

    create_calls = _gift_pending(monkeypatch)
    session = _feed([get_user_router()], USER_ID, "@recipient_user")
    assert create_calls == []
    assert any("/start" in (t or "") for t in _sent_texts(session))


def test_gift_catcher_ignores_text_inside_fsm_state(temp_db, monkeypatch):
    from shop_bot.bot.handlers import get_user_router

    insert_user(temp_db.DB_FILE, telegram_id=USER_ID, username="buyer_one")
    create_calls = _gift_pending(monkeypatch)
    _feed([get_user_router()], USER_ID, "@recipient_user", state="SomeStates:waiting")
    assert create_calls == []


# Ниже — настоящий admin_router. admin_handlers импортирует backup_manager, который
# при импорте создаёт /app/project/backups; без этого каталога (как в CI) тесты не запускаются.

def _bot_routers():
    from shop_bot.bot.admin_handlers import get_admin_router
    from shop_bot.bot.handlers import get_user_router

    return [get_user_router(), get_admin_router()]


def _spy_recheck(monkeypatch) -> list[str]:
    from shop_bot.data_manager import reconciler

    calls: list[str] = []

    async def _fake(bot, payment_id):
        calls.append(payment_id)
        return f"Платёж {payment_id}: проверено"

    monkeypatch.setattr(reconciler, "recheck_payment", _fake)
    return calls


@pytest.mark.parametrize(
    "text, expected",
    [("/recheck_payment p-123", "p-123"), (f"/recheck_payment@{BOT_USERNAME} p-123", "p-123")],
)
def test_admin_recheck_payment_reaches_admin_router(temp_db, monkeypatch, text, expected):
    temp_db.update_setting("admin_telegram_id", str(ADMIN_ID))
    insert_user(temp_db.DB_FILE, telegram_id=ADMIN_ID, username="admin_one")
    calls = _spy_recheck(monkeypatch)
    session = _feed(_bot_routers(), ADMIN_ID, text)
    assert calls == [expected]
    assert any("проверено" in (t or "") for t in _sent_texts(session))


def test_admin_recheck_payment_without_id_shows_usage(temp_db, monkeypatch):
    temp_db.update_setting("admin_telegram_id", str(ADMIN_ID))
    insert_user(temp_db.DB_FILE, telegram_id=ADMIN_ID, username="admin_one")
    calls = _spy_recheck(monkeypatch)
    session = _feed(_bot_routers(), ADMIN_ID, "/recheck_payment")
    assert calls == []
    assert any("Использование" in (t or "") for t in _sent_texts(session))


def test_non_admin_recheck_payment_is_not_executed(temp_db, monkeypatch):
    temp_db.update_setting("admin_telegram_id", str(ADMIN_ID))
    insert_user(temp_db.DB_FILE, telegram_id=USER_ID, username="buyer_one")
    calls = _spy_recheck(monkeypatch)
    _feed(_bot_routers(), USER_ID, "/recheck_payment p-123")
    assert calls == []
