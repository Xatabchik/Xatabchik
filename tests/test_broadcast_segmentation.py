"""Расширенная сегментация рассылок: фильтры, runs, дедупликация, once/recurring."""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest

from conftest import insert_user, temp_db  # noqa: F401


def _make_plan(database, host_name: str, plan_name: str = "Plan", price: float = 100.0) -> int:
    database.create_plan(host_name, plan_name, 1, price, duration_days=30)
    return database.get_plans_for_host(host_name)[-1]["plan_id"]


def _insert_key(db_path, *, user_id: int, expire_at: str, email: str, plan_id: int | None = None) -> None:
    description = json.dumps({"plan_id": plan_id}) if plan_id is not None else None
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url, expire_at, created_at, description
            ) VALUES (?, 'BcastHost', ?, ?, 'vless://x', ?, CURRENT_TIMESTAMP, ?)
            """,
            (user_id, email, email, expire_at, description),
        )
        conn.commit()


def _paid_tx(database, *, user_id: int, payment_id: str, amount: float, method: str = "YooKassa", status: str = "paid") -> None:
    database.log_transaction(
        "bcast-user",
        None,
        payment_id,
        user_id,
        status,
        amount,
        None,
        None,
        method,
        "{}",
    )


def _future(days: int = 10) -> str:
    return (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def _past(days: int = 10) -> str:
    return (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


class RecordingSender:
    def __init__(self, fail_for=None):
        self.sent: list[int] = []
        self.calls: list[int] = []
        self.fail_for = set(fail_for or [])

    def __call__(self, uid, text):
        uid = int(uid)
        self.calls.append(uid)
        if uid in self.fail_for:
            raise RuntimeError("send failed")
        self.sent.append(uid)
        return "sent"


def _run_pass(database, sender=None, *, campaign_id=None, force_start=False):
    sender = sender or RecordingSender()
    campaigns = [database.get_broadcast_campaign(campaign_id)] if campaign_id else database.get_broadcast_campaigns()
    for campaign in campaigns:
        if not campaign:
            continue
        database.execute_broadcast_campaign_pass(int(campaign["id"]), sender, force_start=force_start)
    return sender


def test_legacy_inactive_campaign_without_new_fields(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=101, username="inactive")
    insert_user(database.DB_FILE, telegram_id=102, username="active")
    _insert_key(database.DB_FILE, user_id=102, expire_at=_future(), email="a@x", plan_id=1)

    cid = database.create_broadcast_campaign("old", "<b>hi</b>", 72, "inactive")
    campaign = database.get_broadcast_campaign(cid)
    assert campaign["target_mode"] is None
    assert campaign["schedule_mode"] is None
    assert campaign["target_segment"] == "inactive"

    recipients = database.get_pending_broadcast_recipients(cid, 72)
    assert 101 in recipients
    assert 102 not in recipients


def test_target_mode_all_excludes_email_only(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=201, username="tg")
    insert_user(database.DB_FILE, telegram_id=999000000201, username="email", auth_email="e@x.com")
    insert_user(database.DB_FILE, telegram_id=202, username="banned", is_banned=1)
    cid = database.create_broadcast_campaign(
        "all",
        "hello",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    recipients = database.get_broadcast_recipients(campaign_id=cid)
    assert recipients == [201]


def test_multiple_active_keys_same_plan_one_user(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=301, username="same-plan")
    plan = _make_plan(temp_db, "SamePlanHost", "Start")
    _insert_key(database.DB_FILE, user_id=301, expire_at=_future(), email="k1@x", plan_id=plan)
    _insert_key(database.DB_FILE, user_id=301, expire_at=_future(), email="k2@x", plan_id=plan)
    cid = database.create_broadcast_campaign(
        "plans",
        "x",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan],
        plan_match_mode="any",
        schedule_mode="once",
    )
    assert database.get_broadcast_recipients(campaign_id=cid) == [301]


def test_multiple_distinct_plans_still_one_recipient(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=302, username="two-plans")
    plan_a = _make_plan(temp_db, "HostA", "Start")
    plan_b = _make_plan(temp_db, "HostB", "Pro")
    _insert_key(database.DB_FILE, user_id=302, expire_at=_future(), email="a@x", plan_id=plan_a)
    _insert_key(database.DB_FILE, user_id=302, expire_at=_future(), email="b@x", plan_id=plan_b)
    cid = database.create_broadcast_campaign(
        "any",
        "x",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan_a, plan_b],
        plan_match_mode="any",
        schedule_mode="once",
    )
    assert database.get_broadcast_recipients(campaign_id=cid) == [302]


def test_plan_match_mode_any_and_all(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=401, username="only-a")
    insert_user(database.DB_FILE, telegram_id=402, username="a-and-b")
    insert_user(database.DB_FILE, telegram_id=403, username="only-b")
    plan_a = _make_plan(temp_db, "MatchA", "A")
    plan_b = _make_plan(temp_db, "MatchB", "B")
    _insert_key(database.DB_FILE, user_id=401, expire_at=_future(), email="a1@x", plan_id=plan_a)
    _insert_key(database.DB_FILE, user_id=402, expire_at=_future(), email="a2@x", plan_id=plan_a)
    _insert_key(database.DB_FILE, user_id=402, expire_at=_future(), email="b2@x", plan_id=plan_b)
    _insert_key(database.DB_FILE, user_id=403, expire_at=_future(), email="b3@x", plan_id=plan_b)

    any_id = database.create_broadcast_campaign(
        "any",
        "x",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan_a, plan_b],
        plan_match_mode="any",
        schedule_mode="once",
    )
    all_id = database.create_broadcast_campaign(
        "all",
        "x",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan_a, plan_b],
        plan_match_mode="all",
        schedule_mode="once",
    )
    assert set(database.get_broadcast_recipients(campaign_id=any_id)) == {401, 402, 403}
    assert database.get_broadcast_recipients(campaign_id=all_id) == [402]


def test_expired_keys_are_ignored(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=501, username="expired")
    insert_user(database.DB_FILE, telegram_id=502, username="live")
    plan = _make_plan(temp_db, "ExpHost", "Start")
    _insert_key(database.DB_FILE, user_id=501, expire_at=_past(), email="old@x", plan_id=plan)
    _insert_key(database.DB_FILE, user_id=502, expire_at=_future(), email="new@x", plan_id=plan)
    cid = database.create_broadcast_campaign(
        "exp",
        "x",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan],
        plan_match_mode="any",
        schedule_mode="once",
    )
    assert database.get_broadcast_recipients(campaign_id=cid) == [502]


def test_min_max_distinct_active_plans(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=601, username="one")
    insert_user(database.DB_FILE, telegram_id=602, username="two")
    insert_user(database.DB_FILE, telegram_id=603, username="zero")
    plan_a = _make_plan(temp_db, "CntA", "A")
    plan_b = _make_plan(temp_db, "CntB", "B")
    _insert_key(database.DB_FILE, user_id=601, expire_at=_future(), email="c1@x", plan_id=plan_a)
    _insert_key(database.DB_FILE, user_id=601, expire_at=_future(), email="c1b@x", plan_id=plan_a)
    _insert_key(database.DB_FILE, user_id=602, expire_at=_future(), email="c2a@x", plan_id=plan_a)
    _insert_key(database.DB_FILE, user_id=602, expire_at=_future(), email="c2b@x", plan_id=plan_b)

    exact_one = database.create_broadcast_campaign(
        "one",
        "x",
        24,
        "none",
        target_mode="filtered",
        min_distinct_active_plans=1,
        max_distinct_active_plans=1,
        schedule_mode="once",
    )
    min_two = database.create_broadcast_campaign(
        "two",
        "x",
        24,
        "none",
        target_mode="filtered",
        min_distinct_active_plans=2,
        schedule_mode="once",
    )
    assert database.get_broadcast_recipients(campaign_id=exact_one) == [601]
    assert database.get_broadcast_recipients(campaign_id=min_two) == [602]


def test_spend_range_paid_only_excludes_pending_balance_referral(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=701, username="low")
    insert_user(database.DB_FILE, telegram_id=702, username="ok")
    insert_user(database.DB_FILE, telegram_id=703, username="pending")
    insert_user(database.DB_FILE, telegram_id=704, username="balance")
    insert_user(database.DB_FILE, telegram_id=705, username="ref")
    insert_user(database.DB_FILE, telegram_id=706, username="pending-paid")
    insert_user(database.DB_FILE, telegram_id=707, username="failed")

    _paid_tx(temp_db, user_id=701, payment_id="p701", amount=500)
    _paid_tx(temp_db, user_id=702, payment_id="p702", amount=1500)
    temp_db.create_payload_pending("pend-703", 703, 9999.0, {"payment_method": "YooKassa"})
    _paid_tx(temp_db, user_id=704, payment_id="p704", amount=2000, method="balance")
    _paid_tx(temp_db, user_id=705, payment_id="p705", amount=2000, method="referral_payout")
    temp_db.create_payload_pending("pend-paid-706", 706, 1800.0, {"payment_method": "YooKassa"})
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute("UPDATE pending_transactions SET status='paid' WHERE payment_id='pend-paid-706'")
        conn.commit()
    _paid_tx(temp_db, user_id=707, payment_id="p707", amount=5000, status="failed")

    cid = database.create_broadcast_campaign(
        "spend",
        "x",
        24,
        "none",
        target_mode="filtered",
        spend_min_rub=1000,
        spend_max_rub=2000,
        schedule_mode="once",
    )
    recipients = set(database.get_broadcast_recipients(campaign_id=cid))
    assert 702 in recipients
    assert 706 in recipients
    assert 701 not in recipients
    assert 703 not in recipients
    assert 704 not in recipients
    assert 705 not in recipients
    assert 707 not in recipients


def test_combined_filters_and_legacy_segment(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=801, username="combo-ok")
    insert_user(database.DB_FILE, telegram_id=802, username="has-key")
    insert_user(database.DB_FILE, telegram_id=803, username="low-spend")
    plan = _make_plan(temp_db, "ComboHost", "Start")
    _insert_key(database.DB_FILE, user_id=802, expire_at=_future(), email="live@x", plan_id=plan)
    _paid_tx(temp_db, user_id=801, payment_id="c801", amount=1500)
    _paid_tx(temp_db, user_id=802, payment_id="c802", amount=1500)
    _paid_tx(temp_db, user_id=803, payment_id="c803", amount=100)

    cid = database.create_broadcast_campaign(
        "combo",
        "x",
        24,
        "inactive",
        target_mode="filtered",
        min_distinct_active_plans=0,
        max_distinct_active_plans=0,
        spend_min_rub=1000,
        schedule_mode="once",
    )
    assert database.get_broadcast_recipients(campaign_id=cid) == [801]


def test_preview_matches_selector_and_does_not_write(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=901, username="p1")
    insert_user(database.DB_FILE, telegram_id=902, username="p2")
    cfg = database.build_broadcast_campaign_config(
        name="preview",
        text_html="x",
        target_mode="all",
        schedule_mode="once",
        target_segment="none",
    )
    preview = database.preview_broadcast_audience(cfg)
    recipients = database.get_broadcast_recipients(cfg)
    assert preview["count"] == len(recipients) == 2
    assert {row["user_id"] for row in preview["sample"]} == {901, 902}
    with sqlite3.connect(database.DB_FILE) as conn:
        assert conn.execute("SELECT COUNT(*) FROM broadcast_sends").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM broadcast_runs").fetchone()[0] == 0


def test_in_run_dedup_and_scheduler_success(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1001, username="u1")
    insert_user(database.DB_FILE, telegram_id=1002, username="u2")
    plan = _make_plan(temp_db, "DedupHost", "Start")
    _insert_key(database.DB_FILE, user_id=1001, expire_at=_future(), email="d1a@x", plan_id=plan)
    _insert_key(database.DB_FILE, user_id=1001, expire_at=_future(), email="d1b@x", plan_id=plan)
    cid = database.create_broadcast_campaign(
        "dedup",
        "hello",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan],
        schedule_mode="once",
    )
    bot = RecordingSender()
    _run_pass(database, bot, campaign_id=cid)
    assert bot.sent == [1001]
    assert bot.calls.count(1001) == 1
    campaign = database.get_broadcast_campaign(cid)
    assert campaign["status"] == "completed"
    assert campaign["is_active"] == 0

    bot2 = RecordingSender()
    _run_pass(database, bot2, campaign_id=cid)
    assert bot2.sent == []


def test_send_failure_does_not_stop_others_and_is_not_dedup_blocked(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1101, username="ok")
    insert_user(database.DB_FILE, telegram_id=1102, username="fail")
    insert_user(database.DB_FILE, telegram_id=1103, username="ok2")
    cid = database.create_broadcast_campaign(
        "fail-cont",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    bot = RecordingSender(fail_for={1102})
    _run_pass(database, bot, campaign_id=cid)
    assert 1101 in bot.sent
    assert 1103 in bot.sent
    assert 1102 not in bot.sent
    run = database.get_latest_broadcast_run(cid)
    assert run["failed_count"] >= 1
    assert run["sent_count"] == 2
    with sqlite3.connect(database.DB_FILE) as conn:
        rows = conn.execute(
            "SELECT user_id, status FROM broadcast_sends WHERE campaign_id=?",
            (cid,),
        ).fetchall()
    by_user = {int(r[0]): r[1] for r in rows}
    assert by_user.get(1101) == "sent"
    assert by_user.get(1103) == "sent"
    assert 1102 not in by_user


def test_parallel_run_start_creates_one_run(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1201, username="p")
    cid = database.create_broadcast_campaign(
        "parallel",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="recurring",
    )

    def _start():
        return database.try_start_broadcast_run(cid)

    with ThreadPoolExecutor(max_workers=8) as pool:
        runs = list(pool.map(lambda _: _start(), range(8)))
    ids = {r["id"] for r in runs if r}
    assert len(ids) == 1
    with sqlite3.connect(database.DB_FILE) as conn:
        assert conn.execute("SELECT COUNT(*) FROM broadcast_runs WHERE campaign_id=?", (cid,)).fetchone()[0] == 1


def test_parallel_claim_one_user_one_send(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1301, username="claim")
    cid = database.create_broadcast_campaign(
        "claim",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    run = database.try_start_broadcast_run(cid)
    assert run

    def _claim():
        return database.claim_broadcast_recipient(run["id"], cid, 1301)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: _claim(), range(8)))
    assert sum(1 for ok in results if ok) == 1


def test_recurring_waits_for_interval_then_allows_new_run(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1401, username="r")
    cid = database.create_broadcast_campaign(
        "rec",
        "x",
        72,
        "none",
        target_mode="all",
        schedule_mode="recurring",
    )
    bot = RecordingSender()
    _run_pass(database, bot, campaign_id=cid)
    assert bot.sent == [1401]
    run1 = database.get_latest_broadcast_run(cid)["id"]

    bot2 = RecordingSender()
    _run_pass(database, bot2, campaign_id=cid)
    assert bot2.sent == []
    assert database.get_latest_broadcast_run(cid)["id"] == run1

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE broadcast_campaigns SET last_run_at=datetime('now','-80 hours'), next_run_at=datetime('now','-1 hours') WHERE id=?",
            (cid,),
        )
        conn.commit()
    bot3 = RecordingSender()
    _run_pass(database, bot3, campaign_id=cid)
    assert bot3.sent == [1401]
    run2 = database.get_latest_broadcast_run(cid)["id"]
    assert run2 != run1


def test_same_user_can_receive_in_two_recurring_runs(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1501, username="again")
    cid = database.create_broadcast_campaign(
        "again",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="recurring",
    )
    _run_pass(database, RecordingSender(), campaign_id=cid)
    run2 = database.try_start_broadcast_run(cid, force=True)
    assert run2
    bot = RecordingSender()
    _run_pass(database, bot, campaign_id=cid)
    assert bot.sent == [1501]


def test_edit_does_not_create_run_or_reset_history(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1601, username="edit")
    cid = database.create_broadcast_campaign(
        "edit",
        "old",
        24,
        "none",
        target_mode="all",
        schedule_mode="recurring",
    )
    _run_pass(database, RecordingSender(), campaign_id=cid)
    before = database.get_broadcast_stats(cid)["total_sends"]
    run_id = database.get_latest_broadcast_run(cid)["id"]
    ok = database.update_broadcast_campaign(
        cid,
        name="edit2",
        text_html="new",
        interval_hours=48,
        target_mode="all",
        target_segment="none",
        schedule_mode="recurring",
        update_filters=True,
    )
    assert ok
    assert database.get_active_broadcast_run(cid) is None
    assert database.get_latest_broadcast_run(cid)["id"] == run_id
    assert database.get_broadcast_stats(cid)["total_sends"] == before
    campaign = database.get_broadcast_campaign(cid)
    assert campaign["text_html"] == "new"


def test_disabled_campaign_does_not_start_run(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1701, username="off")
    cid = database.create_broadcast_campaign(
        "off",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="recurring",
    )
    database.toggle_broadcast_campaign(cid)
    _run_pass(database, RecordingSender(), campaign_id=cid)
    assert database.get_latest_broadcast_run(cid) is None


def test_legacy_does_not_fire_immediately_after_recent_last_run(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1801, username="legacy")
    cid = database.create_broadcast_campaign("legacy", "x", 72, "inactive")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("UPDATE broadcast_campaigns SET last_run_at=datetime('now') WHERE id=?", (cid,))
        conn.commit()
    bot = RecordingSender()
    _run_pass(database, bot, campaign_id=cid)
    assert bot.sent == []
    assert database.get_latest_broadcast_run(cid) is None


def test_validation_rejects_bad_ranges_and_plan_json(temp_db):
    from shop_bot.data_manager import database

    with pytest.raises(database.BroadcastFilterError):
        database.validate_broadcast_filters(min_distinct_active_plans=3, max_distinct_active_plans=1)
    with pytest.raises(database.BroadcastFilterError):
        database.validate_broadcast_filters(spend_min_rub=100, spend_max_rub=10)
    with pytest.raises(database.BroadcastFilterError):
        database.validate_broadcast_filters(plan_ids="{not-json")
    with pytest.raises(database.BroadcastFilterError):
        database.validate_broadcast_filters(plan_ids=["x"])
    with pytest.raises(database.BroadcastFilterError):
        database.validate_broadcast_filters(min_distinct_active_plans=-1)
    with pytest.raises(database.BroadcastFilterError):
        database.validate_broadcast_filters(schedule_mode="weekly")


def test_target_mode_all_ignores_posted_filters(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1901, username="no-plan")
    cfg = database.build_broadcast_campaign_config(
        name="ignore",
        text_html="x",
        target_mode="all",
        plan_ids=[999],
        min_distinct_active_plans=5,
        spend_min_rub=99999,
        target_segment="inactive",
        schedule_mode="once",
    )
    assert cfg["plan_ids"] is None
    assert cfg["min_distinct_active_plans"] is None
    assert cfg["spend_min_rub"] is None
    assert database.get_broadcast_recipients(cfg) == [1901]


def test_audience_label_readable(temp_db):
    from shop_bot.data_manager import database

    plan = _make_plan(temp_db, "LblHost", "Pro")
    cid = database.create_broadcast_campaign(
        "lbl",
        "x",
        24,
        "none",
        target_mode="filtered",
        plan_ids=[plan],
        plan_match_mode="any",
        min_distinct_active_plans=2,
        spend_min_rub=1500,
        schedule_mode="recurring",
    )
    campaign = database.get_broadcast_campaign(cid)
    label = database.format_broadcast_audience_label(campaign, {plan: {"plan_name": "Pro"}})
    assert "Pro" in label
    assert "хотя бы один" in label
    assert "от 2" in label
    assert "1 500" in label or "1500" in label


def test_preview_set_equals_send_set(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=2101, username="a")
    insert_user(database.DB_FILE, telegram_id=2102, username="b")
    insert_user(database.DB_FILE, telegram_id=999000000210, username="email", auth_email="z@x.com")
    cid = database.create_broadcast_campaign(
        "same-set",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    preview_ids = set(database.get_broadcast_recipients(campaign_id=cid))
    assert preview_ids == {2101, 2102}
    sender = RecordingSender()
    _run_pass(database, sender, campaign_id=cid)
    assert set(sender.sent) == preview_ids


def test_once_campaign_completes_and_clone_is_fresh(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=2001, username="once")
    cid = database.create_broadcast_campaign(
        "once",
        "x",
        24,
        "none",
        target_mode="all",
        schedule_mode="once",
    )
    _run_pass(database, RecordingSender(), campaign_id=cid)
    campaign = database.get_broadcast_campaign(cid)
    assert campaign["status"] == "completed"
    assert campaign["completed_at"]
    assert database.try_start_broadcast_run(cid, force=True) is None
    clone_id = database.clone_broadcast_campaign(cid)
    clone = database.get_broadcast_campaign(clone_id)
    assert clone["status"] is None
    assert clone["is_active"] == 1
    assert database.get_latest_broadcast_run(clone_id) is None
