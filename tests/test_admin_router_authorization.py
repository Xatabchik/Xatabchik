"""
Авторизация admin_router: глобальный IsAdminFilter.

До фикса callback admin_cancel / btnc_cancel не проверяли is_admin и отдавали
админ-меню (доход, пользователи, ключи) любому, кто прислал callback_data.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from conftest import temp_db  # noqa: F401

ADMIN_ID = 77001
USER_ID = 88001
_TEST_BOT_TOKEN = "123456789:AATestTokenForAdminRouterAuthTests"


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


def _observer_has_is_admin_filter(observer) -> bool:
    from shop_bot.bot.admin_handlers import IsAdminFilter

    filters = observer._handler.filters or []
    return any(isinstance(f.callback, IsAdminFilter) for f in filters)


def _feed_admin_callback(user_id: int, data: str, session: _RecordingSession) -> None:
    from shop_bot.bot.admin_handlers import get_admin_router

    async def _run() -> None:
        dp = Dispatcher()
        dp.include_router(get_admin_router())
        bot = Bot(token=_TEST_BOT_TOKEN, session=session)
        user = User(id=user_id, is_bot=False, first_name="Test")
        chat = Chat(id=user_id, type="private")
        msg = Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=user,
        )
        cb = CallbackQuery(
            id="cb-1",
            from_user=user,
            chat_instance="inst",
            data=data,
            message=msg,
        )
        await dp.feed_update(bot, Update(update_id=1, callback_query=cb))

    asyncio.run(_run())


def test_non_admin_admin_cancel_does_not_open_admin_menu(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.bot import admin_handlers as ah

    database.update_setting("admin_telegram_id", str(ADMIN_ID))
    stats_calls: list[int] = []

    def _spy_stats():
        stats_calls.append(1)
        return {
            "today_new_users": 1,
            "today_income": 100,
            "today_issued_keys": 1,
            "total_users": 10,
            "total_income": 500,
            "total_keys": 5,
            "active_keys": 3,
        }

    monkeypatch.setattr(ah, "get_admin_stats", _spy_stats)
    session = _RecordingSession()
    _feed_admin_callback(USER_ID, "admin_cancel", session)

    assert stats_calls == []
    answers = [m for m in session.methods if isinstance(m, AnswerCallbackQuery)]
    assert answers, session.methods
    assert any(
        (getattr(m, "text", None) == "У вас нет прав." and getattr(m, "show_alert", False))
        for m in answers
    )


def test_non_admin_btnc_cancel_does_not_open_settings_menu(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.bot import keyboards

    database.update_setting("admin_telegram_id", str(ADMIN_ID))
    kb_calls: list[str] = []

    def _spy_settings_kb():
        kb_calls.append("settings")
        return keyboards.create_admin_settings_menu_keyboard()

    monkeypatch.setattr(keyboards, "create_dynamic_admin_settings_menu_keyboard", _spy_settings_kb)
    monkeypatch.setattr(keyboards, "create_admin_settings_menu_keyboard", _spy_settings_kb)
    session = _RecordingSession()
    _feed_admin_callback(USER_ID, "btnc_cancel", session)

    assert kb_calls == []
    answers = [m for m in session.methods if isinstance(m, AnswerCallbackQuery)]
    assert any(getattr(m, "text", None) == "У вас нет прав." for m in answers)


def test_admin_admin_cancel_still_opens_menu(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.bot import admin_handlers as ah

    database.update_setting("admin_telegram_id", str(ADMIN_ID))
    stats_calls: list[int] = []

    def _spy_stats():
        stats_calls.append(1)
        return {
            "today_new_users": 0,
            "today_income": 0,
            "today_issued_keys": 0,
            "total_users": 0,
            "total_income": 0,
            "total_keys": 0,
            "active_keys": 0,
        }

    monkeypatch.setattr(ah, "get_admin_stats", _spy_stats)
    session = _RecordingSession()
    _feed_admin_callback(ADMIN_ID, "admin_cancel", session)
    assert stats_calls == [1]


def test_admin_router_root_filter_covers_every_observer_with_handlers(temp_db):
    """Новые хендлеры на admin_router автоматически попадают под is_admin."""
    from shop_bot.bot.admin_handlers import get_admin_router

    router = get_admin_router()
    observers_with_handlers = [
        (name, observer)
        for name, observer in router.observers.items()
        if observer.handlers
    ]
    assert observers_with_handlers, "admin_router должен иметь хендлеры"
    missing = [
        name
        for name, observer in observers_with_handlers
        if not _observer_has_is_admin_filter(observer)
    ]
    assert missing == [], f"observers without IsAdminFilter: {missing}"
    assert router.callback_query.handlers


def test_franchise_clones_do_not_include_admin_router():
    from pathlib import Path

    src = Path("src/shop_bot/factory_bot/service.py").read_text(encoding="utf-8")
    assert "get_user_router" in src
    assert "get_admin_router" not in src
    assert "include_router(get_user_router())" in src
