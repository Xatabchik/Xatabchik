"""Общие помощники для регрессионных тестов получения пользовательских подарков.

Бот прогоняется целиком через aiogram `Dispatcher` и настоящий пользовательский
роутер (`get_user_router()`), а вместо Telegram Bot API подставляется
`FakeSession`: она отвечает на вызовы методов и запоминает отправленные тексты.
Так проверяются и фильтры состояний FSM, и порядок регистрации хендлеров —
то, что легко пропустить, вызывая функции хендлеров напрямую.
"""
from __future__ import annotations

import itertools
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update

BOT_ID = 123456
FAKE_BOT_TOKEN = "123456:FAKE_BOT_TOKEN_FOR_TESTS"

GIFT_KEY_EXPIRE_AT = "2030-01-15 10:00:00"
GIFT_KEY_LIMIT_BYTES = 50 * 1024 ** 3


class FakeSession(BaseSession):
    """Подмена HTTP-сессии бота: без сети, с журналом вызовов."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list = []
        self.fail_text_substrings: list[str] = []
        self.chat_member_status = "member"
        self._ids = itertools.count(1000)

    def _bot_user(self) -> dict:
        return {"id": BOT_ID, "is_bot": True, "first_name": "Bot", "username": "TestVpnBot"}

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        name = type(method).__name__
        if name == "GetMe":
            from aiogram.types import User

            return User.model_validate(self._bot_user(), context={"bot": bot})
        if name in ("SendMessage", "EditMessageText"):
            text = str(getattr(method, "text", "") or "")
            if any(s in text for s in self.fail_text_substrings):
                raise TelegramNetworkError(method=method, message="simulated network failure")
            from aiogram.types import Message

            chat_id = getattr(method, "chat_id", None) or 1
            return Message.model_validate(
                {
                    "message_id": next(self._ids),
                    "date": int(datetime.now().timestamp()),
                    "chat": {"id": int(chat_id), "type": "private"},
                    "from": self._bot_user(),
                    "text": text,
                },
                context={"bot": bot},
            )
        if name == "GetChatMember":
            from aiogram.types import ChatMemberLeft, ChatMemberMember

            user = {"id": int(method.user_id), "is_bot": False, "first_name": "U"}
            if self.chat_member_status == "member":
                return ChatMemberMember.model_validate({"status": "member", "user": user}, context={"bot": bot})
            return ChatMemberLeft.model_validate({"status": "left", "user": user}, context={"bot": bot})
        return True

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        if False:  # pragma: no cover
            yield b""

    async def close(self) -> None:
        return None


class BotHarness:
    """Запуск апдейтов через настоящий роутер пользователя."""

    def __init__(self, storage: MemoryStorage | None = None) -> None:
        from shop_bot.bot.user_router.router import get_user_router

        self.session = FakeSession()
        self.bot = Bot(
            token=FAKE_BOT_TOKEN,
            session=self.session,
            default=DefaultBotProperties(parse_mode="HTML"),
        )
        self.storage = storage or MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.dp.include_router(get_user_router())
        self._ids = itertools.count(1)

    def _user(self, user_id: int) -> dict:
        return {"id": int(user_id), "is_bot": False, "first_name": f"User{user_id}", "username": f"u{user_id}"}

    async def send_text(self, user_id: int, text: str) -> None:
        n = next(self._ids)
        update = Update.model_validate(
            {
                "update_id": n,
                "message": {
                    "message_id": n,
                    "date": int(datetime.now().timestamp()),
                    "chat": {"id": int(user_id), "type": "private"},
                    "from": self._user(user_id),
                    "text": text,
                },
            },
            context={"bot": self.bot},
        )
        await self.dp.feed_update(self.bot, update)

    async def press(self, user_id: int, data: str) -> None:
        """Нажатие inline-кнопки под сообщением бота: message.from_user — это бот."""
        n = next(self._ids)
        update = Update.model_validate(
            {
                "update_id": n,
                "callback_query": {
                    "id": f"cb{n}",
                    "from": self._user(user_id),
                    "chat_instance": "ci",
                    "data": data,
                    "message": {
                        "message_id": 10_000 + n,
                        "date": int(datetime.now().timestamp()),
                        "chat": {"id": int(user_id), "type": "private"},
                        "from": self.session._bot_user(),
                        "text": "bot message",
                    },
                },
            },
            context={"bot": self.bot},
        )
        await self.dp.feed_update(self.bot, update)

    def texts(self) -> list[str]:
        return [
            str(getattr(m, "text", "") or "")
            for m in self.session.requests
            if type(m).__name__ in ("SendMessage", "EditMessageText")
        ]

    def callback_alerts(self) -> list[str]:
        return [
            str(getattr(m, "text", "") or "")
            for m in self.session.requests
            if type(m).__name__ == "AnswerCallbackQuery"
        ]

    def joined(self) -> str:
        return "\n".join(self.texts())


def configure_onboarding(database, *, captcha: str | None = None, terms: bool = False, channel: bool = False) -> None:
    """captcha: None (выключена) | "math" | "button"."""
    database.update_setting("captcha_enabled", "true" if captcha else "false")
    if captcha:
        database.update_setting("captcha_type", captcha)
    database.update_setting("terms_url", "https://example.test/terms" if terms else "")
    database.update_setting("privacy_url", "https://example.test/privacy" if terms else "")
    database.update_setting("channel_url", "https://t.me/testchannel" if channel else "")
    database.update_setting("force_subscription", "true" if channel else "false")
    database.update_setting("channel_link", "https://t.me/testchannel")
    database.update_setting("chat_link", "https://t.me/testchat")


def latest_captcha_answer(db_path: Path, user_id: int) -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT correct_answer FROM captcha_challenges WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (int(user_id),),
        ).fetchone()
    assert row, "капча не была создана"
    return str(row[0])


def insert_full_gift(
    db_path: Path,
    *,
    from_user_id: int,
    gift_code: str,
    host_name: str = "TestHost",
    link_key: bool = True,
    expires_at: str | None = None,
) -> tuple[int, int]:
    """Подарочный ключ со всеми параметрами подписки + запись user_gifts.

    Возвращает (gift_id, key_id).
    """
    from shop_bot.data_manager import database

    email = f"{from_user_id}-{gift_code.lower()}@bot.local"
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, remnawave_user_uuid, short_uuid, email, key_email,
                subscription_url, expire_at, created_at, updated_at,
                traffic_limit_bytes, traffic_limit_strategy, next_traffic_reset_at,
                tag, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, 'user_gift', ?)
            """,
            (
                from_user_id,
                host_name,
                f"uuid-{gift_code}",
                f"short-{gift_code}",
                email,
                email,
                f"https://sub.example/{gift_code}",
                GIFT_KEY_EXPIRE_AT,
                GIFT_KEY_LIMIT_BYTES,
                "MONTH_ROLLING",
                "2029-12-15 10:00:00",
                json.dumps({"plan_id": 1}),
            ),
        )
        key_id = int(cur.lastrowid)
        conn.commit()
    gift = database.create_user_gift(from_user_id=from_user_id, host_name=host_name, plan_id=1, gift_code=gift_code)
    if link_key:
        database.link_key_to_gift(gift["gift_id"], key_id)
    if expires_at:
        with sqlite3.connect(db_path) as conn:
            conn.execute("UPDATE user_gifts SET expires_at = ? WHERE gift_id = ?", (expires_at, gift["gift_id"]))
            conn.commit()
    return int(gift["gift_id"]), key_id


def key_row(db_path: Path, key_id: int) -> dict | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (int(key_id),)).fetchone()
    return dict(row) if row else None


def gift_row(db_path: Path, gift_id: int) -> dict | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM user_gifts WHERE gift_id = ?", (int(gift_id),)).fetchone()
    return dict(row) if row else None


def keys_count(db_path: Path, user_id: int) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM vpn_keys WHERE user_id = ?", (int(user_id),)).fetchone()[0])


def install_failing_trigger(db_path: Path, table: str, column: str, name: str = "fail_gift_transfer") -> None:
    """Любой UPDATE указанной колонки падает на уровне SQLite (RAISE(ABORT))."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"CREATE TRIGGER {name} BEFORE UPDATE OF {column} ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'simulated failure'); END"
        )
        conn.commit()


def drop_trigger(db_path: Path, name: str = "fail_gift_transfer") -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        conn.commit()


def assert_subscription_preserved(before: dict, after: dict) -> None:
    for column in (
        "remnawave_user_uuid",
        "short_uuid",
        "subscription_url",
        "expire_at",
        "traffic_limit_bytes",
        "traffic_limit_strategy",
        "next_traffic_reset_at",
        "host_name",
        "email",
        "key_email",
        "description",
    ):
        assert after[column] == before[column], f"{column}: {before[column]!r} -> {after[column]!r}"
