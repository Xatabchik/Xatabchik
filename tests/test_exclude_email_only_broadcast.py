"""
Исключение email-only пользователей (без Telegram) из рассылок.

Текущий create_user_by_email выделяет 12-значные ID 999000000000–999999999999.
Старый аллокатор давал 9-значные 999000000+n (в проде: 999000002, 999000003).
Пока пользователь не привязал реальный Telegram, боту некуда доставлять
сообщения — такие аккаунты должны исключаться из всех рассылок.
"""
import sqlite3

from conftest import insert_user, temp_db  # noqa: F401


LEGACY_EMAIL_ONLY_IDS = (999000002, 999000003)
NEW_EMAIL_ONLY_ID = 999000000042


def test_is_email_only_user_detects_virtual_ids():
    from shop_bot.data_manager import database

    assert database.is_email_only_user(999000000001) is True
    assert database.is_email_only_user(999999999999) is True
    assert database.is_email_only_user(999000002) is True
    assert database.is_email_only_user(999000003) is True
    assert database.is_email_only_user({"telegram_id": 999000002}) is True
    assert database.is_email_only_user({"telegram_id": 999000002, "auth_email": "a@x.com"}) is True
    assert database.is_email_only_user({"telegram_id": 123456789, "auth_email": "tg@x.com"}) is False
    assert database.is_email_only_user(123456789) is False
    assert database.is_email_only_user(None) is False
    assert database.is_email_only_user("not-a-number") is False
    assert database.is_email_only_user({"username": "no-id"}) is False
    assert database.is_broadcastable_user(123456789) is True
    assert database.is_broadcastable_user({"telegram_id": 123456789, "username": "", "is_banned": 0}) is True
    assert database.is_broadcastable_user(999000002) is False
    assert database.is_broadcastable_user(999000003) is False
    assert database.is_broadcastable_user(999000000001) is False


def test_get_inactive_subscribers_excludes_email_only_users(temp_db):
    from shop_bot.data_manager import database

    # Реальный Telegram-пользователь без активных ключей — должен попасть в рассылку.
    insert_user(database.DB_FILE, telegram_id=10001, username="tg_user")
    # Email-only без Telegram — должен быть исключён.
    insert_user(
        database.DB_FILE,
        telegram_id=NEW_EMAIL_ONLY_ID,
        username="email_only",
        auth_email="only@example.com",
    )
    insert_user(
        database.DB_FILE,
        telegram_id=999000002,
        username="legacy2",
        auth_email="legacy2@example.com",
    )
    insert_user(
        database.DB_FILE,
        telegram_id=999000003,
        username="legacy3",
        auth_email="legacy3@example.com",
    )
    # Забаненный реальный пользователь — тоже исключён (уже существующее правило).
    insert_user(database.DB_FILE, telegram_id=10002, username="banned", is_banned=1)
    # Недоступный реальный пользователь — исключён.
    insert_user(
        database.DB_FILE,
        telegram_id=10003,
        username="blocked",
        is_unreachable=1,
        unreachable_reason="blocked",
    )

    recipients = database.get_inactive_subscribers()
    assert 10001 in recipients
    assert NEW_EMAIL_ONLY_ID not in recipients
    assert 999000002 not in recipients
    assert 999000003 not in recipients
    assert 10002 not in recipients
    assert 10003 not in recipients


def test_get_pending_broadcast_recipients_excludes_email_only(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=20001, username="tg_ok")
    insert_user(
        database.DB_FILE,
        telegram_id=999000000100,
        username="email_skip",
        auth_email="skip@example.com",
    )
    insert_user(
        database.DB_FILE,
        telegram_id=999000002,
        username="legacy2",
        auth_email="legacy2@example.com",
    )

    campaign_id = database.create_broadcast_campaign(
        name="test",
        text_html="<b>hi</b>",
        interval_hours=72,
        target_segment="inactive",
    )
    assert campaign_id

    recipients = database.get_pending_broadcast_recipients(campaign_id, 72)
    assert 20001 in recipients
    assert 999000000100 not in recipients
    assert 999000002 not in recipients


def test_create_user_by_email_uses_virtual_id_range(temp_db):
    from shop_bot.data_manager import database

    user = database.create_user_by_email("virtual@example.com", "Passw0rd!")
    assert user is not None
    assert database.is_email_only_user(user) is True
    assert user["telegram_chat_id"] is None
    assert database.EMAIL_ONLY_TELEGRAM_ID_MIN <= user["telegram_id"] <= database.EMAIL_ONLY_TELEGRAM_ID_MAX


def _seed_mixed_audience(database, *, plan_id: int | None = None) -> dict[str, int]:
    ids = {
        "tg": 51001,
        "tg_no_username": 51002,
        "tg_with_email": 51003,
        "new_email_only": NEW_EMAIL_ONLY_ID,
        "legacy_2": 999000002,
        "legacy_3": 999000003,
    }
    insert_user(database.DB_FILE, telegram_id=ids["tg"], username="real_tg")
    insert_user(database.DB_FILE, telegram_id=ids["tg_no_username"], username="")
    insert_user(
        database.DB_FILE,
        telegram_id=ids["tg_with_email"],
        username="tg_mail",
        auth_email="linked@example.com",
    )
    insert_user(
        database.DB_FILE,
        telegram_id=ids["new_email_only"],
        username="email_only",
        auth_email="only@example.com",
    )
    insert_user(
        database.DB_FILE,
        telegram_id=ids["legacy_2"],
        username="legacy2",
        auth_email="legacy2@example.com",
    )
    insert_user(
        database.DB_FILE,
        telegram_id=ids["legacy_3"],
        username="legacy3",
        auth_email="legacy3@example.com",
    )
    if plan_id is not None:
        expire_at = "2099-01-01 00:00:00"
        for label, uid in ids.items():
            with sqlite3.connect(database.DB_FILE) as conn:
                conn.execute(
                    """
                    INSERT INTO vpn_keys (
                        user_id, host_name, email, key_email, subscription_url, expire_at, created_at, description
                    ) VALUES (?, 'BcastHost', ?, ?, 'vless://x', ?, CURRENT_TIMESTAMP, ?)
                    """,
                    (uid, f"{label}@x", f"{label}@x", expire_at, f'{{"plan_id": {int(plan_id)}}}'),
                )
                conn.commit()
    return ids


def test_broadcast_all_filtered_legacy_exclude_new_and_legacy_email_only(temp_db):
    from shop_bot.data_manager import database

    database.create_plan("BcastHost", "Start", 1, 100.0, duration_days=30)
    plan_id = database.get_plans_for_host("BcastHost")[-1]["plan_id"]
    ids = _seed_mixed_audience(database, plan_id=plan_id)
    expected_tg = {ids["tg"], ids["tg_no_username"], ids["tg_with_email"]}
    email_only = {ids["new_email_only"], ids["legacy_2"], ids["legacy_3"]}

    all_cid = database.create_broadcast_campaign(
        "all",
        "hello",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    filtered_cid = database.create_broadcast_campaign(
        "filtered",
        "hello",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan_id],
        plan_match_mode="any",
        schedule_mode="once",
    )
    legacy_cid = database.create_broadcast_campaign("legacy", "hello", 72, "inactive")

    for cid in (all_cid, filtered_cid):
        recipients = database.get_broadcast_recipients(campaign_id=cid)
        preview = database.preview_broadcast_audience(campaign_id=cid)
        assert set(recipients) == expected_tg
        assert set(recipients).isdisjoint(email_only)
        assert {row["telegram_id"] for row in preview["sample"]} == expected_tg
        assert preview["count"] == len(expected_tg)

    # У всех есть активный ключ — legacy inactive никого не берёт, в том числе email-only.
    inactive = database.get_broadcast_recipients(campaign_id=legacy_cid)
    assert inactive == []
    assert database.preview_broadcast_audience(campaign_id=legacy_cid)["count"] == 0


def test_legacy_inactive_excludes_email_only_without_keys(temp_db):
    from shop_bot.data_manager import database

    ids = _seed_mixed_audience(database)
    expected_tg = {ids["tg"], ids["tg_no_username"], ids["tg_with_email"]}
    cid = database.create_broadcast_campaign("legacy", "hello", 72, "inactive")
    recipients = database.get_broadcast_recipients(campaign_id=cid)
    preview = database.preview_broadcast_audience(campaign_id=cid)
    assert set(recipients) == expected_tg
    assert 999000002 not in recipients
    assert 999000003 not in recipients
    assert NEW_EMAIL_ONLY_ID not in recipients
    assert {row["telegram_id"] for row in preview["sample"]} == expected_tg


class _RecordingSender:
    def __init__(self):
        self.calls: list[int] = []
        self.sent: list[int] = []

    def __call__(self, uid, text):
        uid = int(uid)
        self.calls.append(uid)
        self.sent.append(uid)
        return "sent"


def test_send_skips_legacy_email_only_and_matches_preview(temp_db):
    from shop_bot.data_manager import database

    ids = _seed_mixed_audience(database)
    expected_tg = {ids["tg"], ids["tg_no_username"], ids["tg_with_email"]}
    cid = database.create_broadcast_campaign(
        "send-all",
        "hello",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    preview_ids = set(database.get_broadcast_recipients(campaign_id=cid))
    assert preview_ids == expected_tg
    sender = _RecordingSender()
    stats = database.execute_broadcast_campaign_pass(cid, sender, force_start=True)
    assert stats.get("skipped") is False
    assert set(sender.calls) == expected_tg
    assert 999000002 not in sender.calls
    assert 999000003 not in sender.calls
    assert NEW_EMAIL_ONLY_ID not in sender.calls
    assert set(sender.sent) == preview_ids
    with sqlite3.connect(database.DB_FILE) as conn:
        sent_ids = {
            int(row[0])
            for row in conn.execute(
                "SELECT user_id FROM broadcast_sends WHERE campaign_id=? AND COALESCE(status, 'sent')='sent'",
                (cid,),
            )
        }
        attempted = {
            int(row[0])
            for row in conn.execute("SELECT user_id FROM broadcast_sends WHERE campaign_id=?", (cid,))
        }
    assert sent_ids == expected_tg
    assert attempted.isdisjoint({NEW_EMAIL_ONLY_ID, 999000002, 999000003})


def test_scheduler_does_not_send_to_legacy_email_only(temp_db, tmp_path):
    import asyncio
    import sys
    import types
    from unittest.mock import AsyncMock, MagicMock

    from shop_bot.data_manager import database

    if "shop_bot.data_manager.backup_manager" not in sys.modules:
        fake_bm = types.ModuleType("shop_bot.data_manager.backup_manager")
        fake_bm.BACKUPS_DIR = tmp_path
        sys.modules["shop_bot.data_manager.backup_manager"] = fake_bm

    from shop_bot.data_manager import scheduler

    ids = _seed_mixed_audience(database)
    cid = database.create_broadcast_campaign(
        "sched-all",
        "hello",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    bot = MagicMock()
    bot.send_message = AsyncMock()
    asyncio.run(scheduler.check_broadcast_campaigns(bot))
    sent_to = [call.args[0] for call in bot.send_message.await_args_list]
    assert set(sent_to) == {ids["tg"], ids["tg_no_username"], ids["tg_with_email"]}
    assert 999000002 not in sent_to
    assert 999000003 not in sent_to
    assert NEW_EMAIL_ONLY_ID not in sent_to
