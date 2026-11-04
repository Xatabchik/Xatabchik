"""Поиск ключей в разделе «Мои ключи» Telegram-бота."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import CallbackQuery, Chat, Message, Sticker, Update, User

from conftest import insert_user, temp_db  # noqa: F401

USER_ID = 55201
OTHER_USER_ID = 55202
_TEST_BOT_TOKEN = "123456789:AATestTokenForUserKeySearch"


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
        if isinstance(method, SendMessage):
            return Message(
                message_id=500 + len(self.methods),
                date=datetime.now(timezone.utc),
                chat=_chat(),
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


def _user() -> User:
    return User(id=USER_ID, is_bot=False, first_name="Searcher")


def _chat() -> Chat:
    return Chat(id=USER_ID, type="private")


def _text_message(text: str, message_id: int = 1) -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=_chat(),
        from_user=_user(),
        text=text,
    )


def _sticker_message(message_id: int = 1) -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=_chat(),
        from_user=_user(),
        sticker=Sticker(
            file_id="sticker-file",
            file_unique_id="sticker-unique",
            type="regular",
            width=512,
            height=512,
            is_animated=False,
            is_video=False,
        ),
    )


def _callback(data: str) -> CallbackQuery:
    return CallbackQuery(
        id=f"cb-{data}",
        from_user=_user(),
        chat_instance="inst",
        data=data,
        message=Message(
            message_id=10,
            date=datetime.now(timezone.utc),
            chat=_chat(),
            from_user=User(id=1, is_bot=True, first_name="Bot"),
            text="Ваши ключи:",
        ),
    )


def _insert_key(db_path, *, user_id: int, email: str, name: str | None = None, tag: str | None = None) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at, tag, user_key_name)
            VALUES (?, 'SearchHost', ?, ?, 'vless://sub', datetime('now', '+30 days'), CURRENT_TIMESTAMP, ?, ?)
            """,
            (user_id, email, email, tag, name),
        )
        conn.commit()
        return int(cur.lastrowid)


class _Harness:
    def __init__(self) -> None:
        from shop_bot.bot.handlers import get_user_router

        self.session = _RecordingSession()
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.dp.include_router(get_user_router())
        self.bot = Bot(token=_TEST_BOT_TOKEN, session=self.session)
        self.ctx = FSMContext(
            storage=self.storage,
            key=StorageKey(bot_id=self.bot.id, chat_id=USER_ID, user_id=USER_ID),
        )
        self._update_id = 0

    async def feed_message(self, message: Message):
        self._update_id += 1
        return await self.dp.feed_update(self.bot, Update(update_id=self._update_id, message=message))

    async def feed_callback(self, data: str):
        self._update_id += 1
        return await self.dp.feed_update(self.bot, Update(update_id=self._update_id, callback_query=_callback(data)))

    def sent_texts(self) -> list[str]:
        return [m.text for m in self.session.methods if isinstance(m, SendMessage)]


def _setup(temp_db) -> _Harness:
    insert_user(temp_db.DB_FILE, telegram_id=USER_ID, username="searcher")
    return _Harness()


def test_sticker_in_search_state_asks_for_text_and_keeps_search(temp_db):
    h = _setup(temp_db)

    async def _go():
        await h.feed_callback("search_my_keys")
        h.session.methods.clear()
        await h.feed_message(_sticker_message())
        return await h.ctx.get_state()

    state = asyncio.run(_go())

    assert state == "search_keys_state"
    replies = [m for m in h.session.methods if isinstance(m, SendMessage)]
    assert len(replies) == 1
    assert "текстом" in replies[0].text
    callbacks = [b.callback_data for row in replies[0].reply_markup.inline_keyboard for b in row]
    assert callbacks == ["cancel_search_keys"]


def _result_callbacks(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_search_with_results_leaves_input_mode_but_keeps_pagination(temp_db):
    from aiogram.methods import EditMessageReplyMarkup

    h = _setup(temp_db)
    key_ids = [_insert_key(temp_db.DB_FILE, user_id=USER_ID, email=f"office-{i}@example.com") for i in range(7)]

    async def _go():
        await h.feed_callback("search_my_keys")
        await h.feed_message(_text_message("office"))
        state_after_search = await h.ctx.get_state()
        h.session.methods.clear()
        await h.feed_message(_text_message("office", message_id=2))
        texts_after_second_message = h.sent_texts()
        await h.feed_callback("search_keys_page_1")
        return state_after_search, texts_after_second_message

    state_after_search, texts_after_second_message = asyncio.run(_go())

    assert state_after_search is None
    assert not any(t.startswith("🔍 Найдено") for t in texts_after_second_message)
    edits = [m for m in h.session.methods if isinstance(m, EditMessageReplyMarkup)]
    assert len(edits) == 1
    page_two = [c for c in _result_callbacks(edits[0].reply_markup) if c.startswith("show_key_")]
    assert len(page_two) == 2
    assert set(page_two) <= {f"show_key_{kid}" for kid in key_ids}


def test_search_pagination_ignores_admin_search_results(temp_db):
    from aiogram.methods import EditMessageReplyMarkup

    h = _setup(temp_db)
    own_key = _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="mine@example.com")
    foreign_key = _insert_key(temp_db.DB_FILE, user_id=OTHER_USER_ID, email="foreign@example.com")

    async def _go():
        await h.feed_callback("search_my_keys")
        await h.feed_message(_text_message("mine"))
        foreign = temp_db.get_key_by_id(foreign_key)
        await h.ctx.update_data(search_results=[foreign])
        h.session.methods.clear()
        await h.feed_callback("search_keys_page_0")

    asyncio.run(_go())

    edits = [m for m in h.session.methods if isinstance(m, EditMessageReplyMarkup)]
    assert len(edits) == 1
    callbacks = _result_callbacks(edits[0].reply_markup)
    assert f"show_key_{own_key}" in callbacks
    assert f"show_key_{foreign_key}" not in callbacks


def test_search_without_results_stays_in_input_mode(temp_db):
    h = _setup(temp_db)
    _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="mine@example.com")

    async def _go():
        await h.feed_callback("search_my_keys")
        await h.feed_message(_text_message("nothing-like-this"))
        return await h.ctx.get_state()

    assert asyncio.run(_go()) == "search_keys_state"
    assert any(t.startswith("❌ Ключи не найдены") for t in h.sent_texts())


def test_single_character_query_is_rejected_and_stays_in_input_mode(temp_db):
    h = _setup(temp_db)
    _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="mine@example.com")

    async def _go():
        await h.feed_callback("search_my_keys")
        h.session.methods.clear()
        await h.feed_message(_text_message(" m "))
        return await h.ctx.get_state()

    assert asyncio.run(_go()) == "search_keys_state"
    texts = h.sent_texts()
    assert texts == ["❌ Минимум 2 символа для поиска"]


def test_two_character_query_searches(temp_db):
    h = _setup(temp_db)
    _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="mine@example.com")

    async def _go():
        await h.feed_callback("search_my_keys")
        await h.feed_message(_text_message("mi"))

    asyncio.run(_go())
    assert any(t.startswith("🔍 Найдено 1") for t in h.sent_texts())


def test_cancel_search_lists_gifts_separately_like_my_keys(temp_db):
    from aiogram.methods import EditMessageText

    h = _setup(temp_db)
    own_key = _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="mine@example.com")
    gift_key = _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="gift@example.com", tag="user_gift")

    async def _go():
        await h.feed_callback("search_my_keys")
        h.session.methods.clear()
        await h.feed_callback("cancel_search_keys")
        return await h.ctx.get_state(), await h.ctx.get_data()

    state, data = asyncio.run(_go())

    assert state is None
    assert data == {}
    edits = [m for m in h.session.methods if isinstance(m, EditMessageText)]
    assert len(edits) == 1
    assert edits[0].text == "Ваши ключи:"
    callbacks = _result_callbacks(edits[0].reply_markup)
    assert f"show_key_{own_key}" in callbacks
    assert f"show_key_{gift_key}" not in callbacks
    assert "sent_gifts" in callbacks


def test_cancel_search_with_only_gifts_still_shows_list(temp_db):
    from aiogram.methods import EditMessageText

    h = _setup(temp_db)
    _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="gift@example.com", tag="gift")

    asyncio.run(h.feed_callback("cancel_search_keys"))

    edits = [m for m in h.session.methods if isinstance(m, EditMessageText)]
    assert edits[0].text == "Ваши ключи:"
    assert "sent_gifts" in _result_callbacks(edits[0].reply_markup)


def test_sent_gifts_lists_only_gift_keys(temp_db):
    from aiogram.methods import EditMessageText

    h = _setup(temp_db)
    own_key = _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="mine@example.com")
    gift_key = _insert_key(temp_db.DB_FILE, user_id=USER_ID, email="gift@example.com", tag=" User_Gift ")

    asyncio.run(h.feed_callback("sent_gifts"))

    edits = [m for m in h.session.methods if isinstance(m, EditMessageText)]
    shown = [c for c in _result_callbacks(edits[0].reply_markup) if c.startswith("show_key_")]
    assert shown == [f"show_key_{gift_key}"]
    assert f"show_key_{own_key}" not in shown


def test_blank_text_in_search_state_asks_for_text(temp_db):
    h = _setup(temp_db)

    async def _go():
        await h.feed_callback("search_my_keys")
        h.session.methods.clear()
        await h.feed_message(_text_message("   "))
        return await h.ctx.get_state()

    assert asyncio.run(_go()) == "search_keys_state"
    assert any("текстом" in t for t in h.sent_texts())
