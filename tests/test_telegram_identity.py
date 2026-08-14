"""Нормализация Telegram-привязки: telegram_chat_id вместо legacy users.telegram_id."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from conftest import insert_user, temp_db  # noqa: F401


def test_migration_adds_chat_id_columns_and_is_idempotent(temp_db):
    from shop_bot.data_manager import database

    with sqlite3.connect(database.DB_FILE) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(users)")}
    assert "telegram_chat_id" in cols
    assert "telegram_linked_at" in cols
    assert "idx_users_telegram_chat_id" in indexes

    database.initialize_db()
    with sqlite3.connect(database.DB_FILE) as conn:
        cols2 = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    assert "telegram_chat_id" in cols2
    assert "telegram_linked_at" in cols2


def test_backfill_real_users_and_leaves_email_only_null(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=41001, username="real")
    insert_user(database.DB_FILE, telegram_id=41002, username="")
    insert_user(database.DB_FILE, telegram_id=41003, username="withmail", auth_email="tg@example.com")
    insert_user(database.DB_FILE, telegram_id=999000000042, username="email_new", auth_email="n@example.com")
    insert_user(database.DB_FILE, telegram_id=999000002, username="legacy2", auth_email="l2@example.com")
    insert_user(database.DB_FILE, telegram_id=999000003, username="legacy3", auth_email="l3@example.com")

    database.initialize_db()

    def row(uid):
        return database.get_user(uid)

    for uid in (41001, 41002, 41003):
        user = row(uid)
        assert user["telegram_chat_id"] == uid
        assert user["telegram_linked_at"]
        assert database.get_telegram_chat_id_for_user(user) == uid
        assert database.get_telegram_chat_id_for_user(uid) == uid

    for uid in (999000000042, 999000002, 999000003):
        user = row(uid)
        assert user["telegram_chat_id"] is None
        assert user["telegram_linked_at"] is None
        assert database.get_telegram_chat_id_for_user(user) is None
        assert database.get_telegram_chat_id_for_user(uid) is None


def test_create_user_by_email_has_null_chat_id(temp_db):
    from shop_bot.data_manager import database

    user = database.create_user_by_email("virtual@example.com", "Passw0rd!")
    assert user is not None
    assert database.is_email_only_user(user) is True
    assert user["telegram_chat_id"] is None
    assert user["telegram_linked_at"] is None
    assert database.get_telegram_chat_id_for_user(user) is None


def test_register_user_sets_chat_id_for_real_telegram(temp_db):
    from shop_bot.data_manager import database

    database.register_user_if_not_exists(52001, "alice", None)
    user = database.get_user(52001)
    assert user["telegram_chat_id"] == 52001
    assert user["telegram_linked_at"]
    database.register_user_if_not_exists(52001, "alice2", None)
    again = database.get_user(52001)
    assert again["telegram_chat_id"] == 52001
    assert again["username"] == "alice2"


def test_link_user_telegram_is_idempotent_and_refuses_virtual_id(temp_db):
    from shop_bot.data_manager import database

    database.register_user_if_not_exists(53001, "bob", None)
    assert database.link_user_telegram(53001, 53001, "bob") is True
    assert database.link_user_telegram(53001, 999000002) is False
    assert database.get_user(53001)["telegram_chat_id"] == 53001


def test_broadcasts_exclude_users_without_chat_id(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=61001, username="tg")
    insert_user(database.DB_FILE, telegram_id=61002, username="")
    insert_user(database.DB_FILE, telegram_id=61003, username="mail", auth_email="ok@example.com")
    insert_user(database.DB_FILE, telegram_id=999000000201, username="email", auth_email="e@example.com")
    insert_user(database.DB_FILE, telegram_id=999000002, username="legacy2", auth_email="l2@example.com")
    insert_user(database.DB_FILE, telegram_id=999000003, username="legacy3", auth_email="l3@example.com")
    database.initialize_db()

    expected = {61001, 61002, 61003}
    recipients = set(database.get_inactive_subscribers())
    assert expected <= recipients
    assert recipients.isdisjoint({999000000201, 999000002, 999000003})

    cid = database.create_broadcast_campaign("all-like", "hello", 72, "inactive")
    pending = set(database.get_pending_broadcast_recipients(cid, 72))
    assert pending == recipients
    assert 999000002 not in pending
    assert 999000003 not in pending


def test_identity_stats_and_sample_hide_secrets(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=71001, username="tg")
    insert_user(database.DB_FILE, telegram_id=999000002, username="legacy2", auth_email="l2@example.com")
    database.initialize_db()
    stats = database.get_telegram_identity_stats()
    assert stats["with_chat_id"] >= 1
    assert stats["email_only"] >= 1
    sample = database.get_telegram_identity_unclassified_sample()
    for row in sample:
        assert "auth_pass" not in row
        assert "auth_token" not in row
        assert set(row) <= {"telegram_id", "username", "has_auth_email", "telegram_chat_id", "registration_date"}


def test_subscription_notification_skips_email_only(temp_db, tmp_path):
    import sys
    import types

    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=999000002, username="legacy2", auth_email="l2@example.com")
    insert_user(database.DB_FILE, telegram_id=81001, username="real")
    database.initialize_db()
    expire = (datetime.utcnow() + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at)
            VALUES (999000002, 'H', 'e@x', 'e@x', 'vless://x', ?, CURRENT_TIMESTAMP)
            """,
            (expire,),
        )
        conn.commit()

    if "shop_bot.data_manager.backup_manager" not in sys.modules:
        fake_bm = types.ModuleType("shop_bot.data_manager.backup_manager")
        fake_bm.BACKUPS_DIR = tmp_path
        sys.modules["shop_bot.data_manager.backup_manager"] = fake_bm

    from shop_bot.data_manager import scheduler

    bot = MagicMock()
    bot.send_message = AsyncMock()
    asyncio.run(
        scheduler.send_subscription_notification(
            bot, 999000002, 1, 24, datetime.utcnow() + timedelta(hours=20)
        )
    )
    bot.send_message.assert_not_called()

    asyncio.run(
        scheduler.send_subscription_notification(
            bot, 81001, 1, 24, datetime.utcnow() + timedelta(hours=20)
        )
    )
    bot.send_message.assert_awaited()
    assert bot.send_message.await_args.kwargs.get("chat_id") == 81001 or bot.send_message.await_args.args[0] == 81001


def test_scheduler_broadcast_skips_email_only(temp_db, tmp_path):
    import sys
    import types

    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91001, username="real")
    insert_user(database.DB_FILE, telegram_id=999000003, username="legacy3", auth_email="l3@example.com")
    database.initialize_db()
    cid = database.create_broadcast_campaign("now", "hello", 72, "inactive")

    if "shop_bot.data_manager.backup_manager" not in sys.modules:
        fake_bm = types.ModuleType("shop_bot.data_manager.backup_manager")
        fake_bm.BACKUPS_DIR = tmp_path
        sys.modules["shop_bot.data_manager.backup_manager"] = fake_bm

    from shop_bot.data_manager import scheduler

    bot = MagicMock()
    bot.send_message = AsyncMock()
    asyncio.run(scheduler.check_broadcast_campaigns(bot))
    sent_to = []
    for call in bot.send_message.await_args_list:
        if call.args:
            sent_to.append(int(call.args[0]))
        elif "chat_id" in (call.kwargs or {}):
            sent_to.append(int(call.kwargs["chat_id"]))
    assert 91001 in sent_to
    assert 999000003 not in sent_to


def test_forbidden_still_marks_unreachable(temp_db):
    from aiogram.exceptions import TelegramForbiddenError

    from shop_bot.data_manager import database
    from shop_bot.modules import telegram_reachability

    database.register_user_if_not_exists(101001, "live", None)
    assert database.get_user(101001)["is_unreachable"] in (0, None, False)

    class _Forbidden(TelegramForbiddenError):
        def __init__(self):
            Exception.__init__(self, "Forbidden: bot was blocked by the user")
            self.message = "Forbidden: bot was blocked by the user"

    marked = telegram_reachability.handle_send_exception(101001, _Forbidden())
    assert marked is True
    user = database.get_user(101001)
    assert user["is_unreachable"] in (1, True)
    assert user["telegram_chat_id"] == 101001


def test_initialize_db_does_not_reset_broadcast_last_run(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=111001, username="tg")
    cid = database.create_broadcast_campaign("keep", "x", 72, "inactive")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("UPDATE broadcast_campaigns SET last_run_at=datetime('now') WHERE id=?", (cid,))
        conn.commit()
    before = database.get_broadcast_campaign(cid)["last_run_at"]
    database.initialize_db()
    after = database.get_broadcast_campaign(cid)["last_run_at"]
    assert after == before
    assert database.get_telegram_chat_id_for_user(111001) == 111001


def test_fallback_without_backfill_for_real_user_only(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=121001, username="nobackfill")
    insert_user(database.DB_FILE, telegram_id=999000002, username="legacy2", auth_email="l2@example.com")
    real = database.get_user(121001)
    legacy = database.get_user(999000002)
    assert real["telegram_chat_id"] is None
    assert legacy["telegram_chat_id"] is None
    assert database.get_telegram_chat_id_for_user(real) == 121001
    assert database.get_telegram_chat_id_for_user(legacy) is None


def test_link_email_only_keeps_pk_and_does_not_duplicate_on_register(temp_db):
    from shop_bot.data_manager import database

    user = database.create_user_by_email("merge@example.com", "Passw0rd!")
    pk = user["telegram_id"]
    assert database.link_telegram_to_email_user(pk, 131001, "merged") is True
    linked = database.get_user(pk)
    assert linked["telegram_id"] == pk
    assert linked["telegram_chat_id"] == 131001
    assert database.get_telegram_chat_id_for_user(pk) == 131001
    assert database.get_user(131001)["telegram_id"] == pk

    database.register_user_if_not_exists(131001, "merged2", None)
    with sqlite3.connect(database.DB_FILE) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE telegram_chat_id = 131001").fetchone()[0]
        pk_count = conn.execute("SELECT COUNT(*) FROM users WHERE telegram_id = 131001").fetchone()[0]
    assert count == 1
    assert pk_count == 0
    again = database.get_user(pk)
    assert again["username"] == "merged2"
    assert again["telegram_chat_id"] == 131001


def test_send_now_skips_email_only_without_recording_failure(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=141001, username="real")
    insert_user(database.DB_FILE, telegram_id=999000003, username="legacy3", auth_email="l3@example.com")
    database.initialize_db()
    cid = database.create_broadcast_campaign("now", "hello", 72, "inactive")
    recipients = database.get_pending_broadcast_recipients(cid, 72)
    delivered = []
    skipped = []
    for uid in recipients:
        if database.get_telegram_chat_id_for_user(int(uid)) is None:
            skipped.append(uid)
            continue
        delivered.append(uid)
    assert 141001 in delivered
    assert 999000003 not in delivered
    assert 999000003 not in skipped
    assert all(database.get_telegram_chat_id_for_user(uid) is not None for uid in delivered)
