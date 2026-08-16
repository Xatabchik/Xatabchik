"""Франшиза: runtime start/stop клонов, автоотключение, удаление, меню."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock

from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.base import BaseSession
from aiogram.methods import GetMe, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import CallbackQuery, Chat, Message, User

from conftest import temp_db  # noqa: F401

OWNER_A = 91011
OWNER_B = 91012
TG_BOT_ID = 555000333
TOKEN_A = "555000333:AAOwnerAToken________________"


class _FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeBot:
    def __init__(self, token, default=None):
        self.token = token
        self.session = _FakeSession()
        self.id = TG_BOT_ID


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


def _make_unauthorized():
    from aiogram.exceptions import TelegramUnauthorizedError

    return TelegramUnauthorizedError(method=GetMe(), message="Unauthorized")


def _patch_service_aiogram(monkeypatch, polling_impl):
    from shop_bot.factory_bot import service as svc_mod

    monkeypatch.setattr(svc_mod, "Bot", _FakeBot)
    monkeypatch.setattr(Dispatcher, "start_polling", polling_impl)
    monkeypatch.setattr(svc_mod, "get_user_router", lambda: Router())
    monkeypatch.setattr(svc_mod, "get_owner_cabinet_router", lambda: Router())


def test_stop_bot_and_start_bot_are_idempotent(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.factory_bot.service import ManagedBotsService

    hang = asyncio.Event()

    async def _hang_polling(self, *args, **kwargs):
        hang.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    _patch_service_aiogram(monkeypatch, _hang_polling)

    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_runtime_bot",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True

    async def _run():
        loop = asyncio.get_running_loop()
        svc = ManagedBotsService(loop)
        await svc.stop_bot(bot_id)
        await svc.stop_bot(999999)

        await svc.start_bot(bot_id)
        await asyncio.wait_for(hang.wait(), timeout=2)
        assert bot_id in svc._tasks
        hang.clear()

        await svc.start_bot(bot_id)
        assert bot_id in svc._tasks

        await svc.stop_bot(bot_id)
        assert bot_id not in svc._tasks
        await svc.stop_bot(bot_id)

        await svc.start_bot(bot_id)
        await asyncio.wait_for(hang.wait(), timeout=2)
        await svc.restart_bot(bot_id)
        await svc.stop_all()
        assert svc._tasks == {}

    asyncio.run(_run())


def test_unauthorized_auto_disables_managed_bot(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.factory_bot.service import ManagedBotsService

    async def _raise_unauth(self, *args, **kwargs):
        raise _make_unauthorized()

    _patch_service_aiogram(monkeypatch, _raise_unauth)

    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_bad_token",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True
    assert int(database.get_managed_bot(bot_id)["is_active"] or 0) == 1

    async def _run():
        loop = asyncio.get_running_loop()
        svc = ManagedBotsService(loop)
        await svc.start_bot(bot_id)
        for _ in range(50):
            row = database.get_managed_bot(bot_id)
            if row is not None and int(row["is_active"] or 0) == 0:
                break
            await asyncio.sleep(0.05)
        row = database.get_managed_bot(bot_id)
        assert row is not None
        assert int(row["is_active"] or 0) == 0
        assert row["owner_telegram_id"] == OWNER_A
        assert row["token"] == TOKEN_A
        await svc.stop_bot(bot_id)
        await svc.start_bot(bot_id)
        for _ in range(50):
            row = database.get_managed_bot(bot_id)
            if row is not None and int(row["is_active"] or 0) == 0:
                break
            await asyncio.sleep(0.05)
        await svc.stop_bot(bot_id)

    asyncio.run(_run())


def test_delete_managed_bot_requires_owner(temp_db):
    database = temp_db
    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_del_bot",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True
    database.record_factory_activity(bot_id, OWNER_A)
    database.accrue_partner_commission(bot_id, "pay-1", 777001, 100.0, "yookassa", 35.0)

    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO partner_withdraw_requests (bot_id, owner_telegram_id, amount_rub, status) VALUES (?, ?, 50, 'paid')",
            (bot_id, OWNER_A),
        )
        conn.execute(
            "INSERT INTO partner_withdraw_requests (bot_id, owner_telegram_id, amount_rub, status) VALUES (?, ?, 20, 'pending')",
            (bot_id, OWNER_A),
        )
        conn.execute(
            "INSERT INTO partner_withdraw_requests (bot_id, owner_telegram_id, amount_rub, status) VALUES (?, ?, 30, 'approved')",
            (bot_id, OWNER_A),
        )
        conn.commit()

    assert database.delete_managed_bot(bot_id, owner_telegram_id=OWNER_B) is False
    assert database.get_managed_bot(bot_id) is not None
    with sqlite3.connect(database.DB_FILE) as conn:
        activity_left = conn.execute(
            "SELECT COUNT(1) FROM factory_user_activity WHERE bot_id = ?", (bot_id,)
        ).fetchone()[0]
        commissions_left = conn.execute(
            "SELECT COUNT(1) FROM partner_commissions WHERE bot_id = ?", (bot_id,)
        ).fetchone()[0]
    assert int(activity_left) == 1
    assert int(commissions_left) == 1

    listed = database.get_managed_bots_by_owner(OWNER_A)
    assert len(listed) == 1
    assert "token" not in listed[0]

    assert database.delete_managed_bot(bot_id, owner_telegram_id=OWNER_A) is True
    assert database.get_managed_bot(bot_id) is None
    assert database.get_managed_bots_by_owner(OWNER_A) == []

    with sqlite3.connect(database.DB_FILE) as conn:
        activity_left = conn.execute(
            "SELECT COUNT(1) FROM factory_user_activity WHERE bot_id = ?", (bot_id,)
        ).fetchone()[0]
        commissions_left = conn.execute(
            "SELECT COUNT(1) FROM partner_commissions WHERE bot_id = ?", (bot_id,)
        ).fetchone()[0]
        withdraws = conn.execute(
            "SELECT status FROM partner_withdraw_requests WHERE bot_id = ? ORDER BY status",
            (bot_id,),
        ).fetchall()
    assert int(activity_left) == 0
    assert int(commissions_left) == 0
    assert [row[0] for row in withdraws] == ["approved", "paid", "pending"]

    database.purge_managed_bot_stats(bot_id)
    database.purge_managed_bot_stats(bot_id)


def test_factory_delete_handler_rejects_non_owner(temp_db, monkeypatch):
    from aiogram.types import Update
    from shop_bot.data_manager import database
    from shop_bot.factory_bot.handlers import get_owner_cabinet_router

    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_handler_bot",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True

    class _FakeManaged:
        def __init__(self):
            self.stopped: list[int] = []

        async def stop_bot(self, managed_id: int):
            self.stopped.append(int(managed_id))

    fake_svc = _FakeManaged()
    monkeypatch.setattr("shop_bot.factory_bot.handlers.get_service", lambda: fake_svc)

    session = _RecordingSession()

    async def _feed(user_id: int, data: str, telegram_bot_user_id: int = TG_BOT_ID):
        dp = Dispatcher()
        dp.include_router(get_owner_cabinet_router())
        bot = Bot(token=f"{telegram_bot_user_id}:AATestTokenForFranchiseDelete", session=session)
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

    asyncio.run(_feed(OWNER_B, f"factory_del_yes:{bot_id}"))
    assert database.get_managed_bot(bot_id) is not None
    assert fake_svc.stopped == []

    asyncio.run(_feed(OWNER_B, "factory_del_self"))
    assert database.get_managed_bot(bot_id) is not None

    asyncio.run(_feed(OWNER_A, f"factory_del_yes:{bot_id}"))
    assert database.get_managed_bot(bot_id) is None
    assert fake_svc.stopped == [bot_id]


def test_factory_del_self_confirms_current_clone_only(temp_db, monkeypatch):
    from aiogram.types import Update
    from shop_bot.data_manager import database
    from shop_bot.factory_bot.handlers import get_owner_cabinet_router

    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_self_del",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True

    session = _RecordingSession()

    async def _feed(user_id: int):
        dp = Dispatcher()
        dp.include_router(get_owner_cabinet_router())
        bot = Bot(token=f"{TG_BOT_ID}:AATestTokenForFranchiseDelete", session=session)
        user = User(id=user_id, is_bot=False, first_name="Test")
        chat = Chat(id=user_id, type="private")
        msg = Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=chat,
            from_user=user,
        )
        cb = CallbackQuery(
            id="cb-self",
            from_user=user,
            chat_instance="inst",
            data="factory_del_self",
            message=msg,
        )
        await dp.feed_update(bot, Update(update_id=2, callback_query=cb))

    asyncio.run(_feed(OWNER_A))
    assert database.get_managed_bot(bot_id) is not None
    from aiogram.methods import EditMessageText

    edits = [m for m in session.methods if isinstance(m, EditMessageText)]
    assert edits
    assert f"factory_del_yes:{bot_id}" in (edits[-1].reply_markup.inline_keyboard[0][0].callback_data or "")
    assert "factory_my_bots" not in str(session.methods)


def test_franchise_menu_visibility_flags(temp_db):
    from shop_bot.webhook_server.app import franchise_menu_button_visible, franchise_settings
    from shop_bot.data_manager import database

    assert franchise_settings() is False
    assert franchise_menu_button_visible() is False

    database.update_setting("franchise_enabled", "true")
    database.update_setting("franchise_menu_button_visible", "false")
    assert franchise_settings() is True
    assert franchise_menu_button_visible() is False

    database.update_setting("franchise_enabled", "false")
    database.update_setting("franchise_menu_button_visible", "true")
    assert franchise_settings() is False
    assert franchise_menu_button_visible() is True


def test_franchise_menu_template_uses_independent_flag():
    html = Path("src/shop_bot/webhook_server/templates/base.html").read_text(encoding="utf-8")
    assert html.count("franchise_enabled or franchise_menu_button_visible") == 2
    assert "{% if franchise_enabled %}" not in html


def test_franchise_delete_route_stops_and_deletes(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod
    from shop_bot.factory_bot import runtime as factory_runtime

    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_web_del",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True

    database.record_factory_activity(bot_id, OWNER_A)
    database.accrue_partner_commission(bot_id, "pay-web", 777002, 80.0, "yookassa", 35.0)

    class _FakeSvc:
        def __init__(self):
            self.stopped: list[int] = []

        async def stop_bot(self, managed_id: int):
            self.stopped.append(int(managed_id))

    fake = _FakeSvc()
    monkeypatch.setattr(factory_runtime, "get_service", lambda: fake)
    monkeypatch.setattr(wh_mod, "_bot_controller", MagicMock(get_loop=lambda: None))

    flask_app = wh_mod.create_webhook_app(MagicMock(get_status=lambda: {"is_running": False}, get_loop=lambda: None))
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.post(f"/franchise/bot/{bot_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert database.get_managed_bot(bot_id) is None
    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        activity_left = conn.execute(
            "SELECT COUNT(1) FROM factory_user_activity WHERE bot_id = ?", (bot_id,)
        ).fetchone()[0]
        commissions_left = conn.execute(
            "SELECT COUNT(1) FROM partner_commissions WHERE bot_id = ?", (bot_id,)
        ).fetchone()[0]
    assert int(activity_left) == 0
    assert int(commissions_left) == 0


def test_middleware_skips_when_franchise_disabled(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.factory_bot.middleware import FactoryStatsMiddleware, invalidate_franchise_enabled_cache

    database.update_setting("franchise_enabled", "false")
    invalidate_franchise_enabled_cache()
    called = {"n": 0}

    async def handler(event, data):
        called["n"] += 1
        return "ok"

    mw = FactoryStatsMiddleware()

    async def _run():
        result = await mw(handler, MagicMock(), {"bot": MagicMock(id=1), "event_from_user": MagicMock(id=2)})
        assert result == "ok"

    asyncio.run(_run())
    assert called["n"] == 1


def test_clone_service_does_not_include_factory_router():
    src = Path("src/shop_bot/factory_bot/service.py").read_text(encoding="utf-8")
    assert "get_owner_cabinet_router()" in src
    assert "get_factory_router" not in src


def test_factory_bot_has_no_create_bot_or_my_bots():
    handlers = Path("src/shop_bot/factory_bot/handlers.py").read_text(encoding="utf-8")
    keyboards = Path("src/shop_bot/factory_bot/keyboards.py").read_text(encoding="utf-8")
    for src in (handlers, keyboards):
        assert "factory_create_bot" not in src
        assert "factory_my_bots" not in src
        assert "Создать бот" not in src
        assert "Мои боты" not in src
        assert "get_factory_router" not in src
    from shop_bot.factory_bot import handlers as h
    assert not hasattr(h, "get_factory_router")


def test_cabinet_menu_uses_delete_self_not_my_bots():
    from shop_bot.factory_bot.keyboards import cabinet_menu, delete_bot_confirm

    markup = cabinet_menu()
    callbacks = [
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
    ]
    assert "factory_del_self" in callbacks
    assert "factory_my_bots" not in callbacks
    confirm = delete_bot_confirm(7)
    confirm_cb = [
        btn.callback_data
        for row in confirm.inline_keyboard
        for btn in row
    ]
    assert "factory_del_yes:7" in confirm_cb
    assert "factory_my_bots" not in confirm_cb
