"""Support-бот: невалидный токен не должен ронять polling с traceback."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock

from aiogram.exceptions import TelegramUnauthorizedError

from shop_bot.support_bot_controller import SupportBotController


class _FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeBot:
    def __init__(self):
        self.session = _FakeSession()
        self.closed = False

    async def close(self):
        self.closed = True


class _UnauthorizedDispatcher:
    async def start_polling(self, bot, handle_signals=False):
        raise TelegramUnauthorizedError(method=MagicMock(), message="Unauthorized")


def test_support_polling_unauthorized_stops_without_traceback(monkeypatch, caplog):
    monkeypatch.setattr(SupportBotController, "_start_own_loop", lambda self: None)
    ctrl = SupportBotController()
    ctrl._loop = None
    bot = _FakeBot()
    ctrl._bot = bot
    ctrl._dp = _UnauthorizedDispatcher()

    with caplog.at_level(logging.ERROR):
        asyncio.run(ctrl._start_polling())

    assert ctrl._is_running is False
    assert ctrl._bot is None
    assert ctrl._dp is None
    assert bot.session.closed is True
    messages = " ".join(rec.message for rec in caplog.records)
    assert "неверный или отозванный токен" in messages
    assert not any(rec.exc_info for rec in caplog.records)
