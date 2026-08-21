"""Ежемесячный сброс основного и LTE-пулов от даты покупки ключа.

Проверяем:
  * MONTH_ROLLING только при лимите основного пула (это поле уходит в Remnawave);
  * дата сброса ставится и для LTE-only тарифов (безлимитный основной);
  * воркер для LTE-only не трогает панель, а только крутит период LTE;
  * воркер для лимитного основного возвращает лимит к базе тарифа и сжигает буст;
  * бэкфилл существующих ключей выравнивает дату по created_at.
"""
import asyncio
import json
import sqlite3
from datetime import datetime, timedelta

from conftest import temp_db  # noqa: F401

GB = 1024 ** 3


def _create_host_and_plan(database, host_name, *, traffic_gb=0, lte_gb=0):
    database.create_host(host_name, "https://panel.example", "", "", 0)
    database.create_plan(
        host_name,
        f"plan-{host_name}",
        1,
        100.0,
        traffic_limit_bytes=int(traffic_gb * GB),
        lte_limit_bytes=int(lte_gb * GB),
    )
    plans = {p["plan_name"]: p["plan_id"] for p in database.get_plans_for_host(host_name)}
    return plans[f"plan-{host_name}"]


def _insert_key(
    database,
    *,
    user_id,
    host_name,
    user_uuid,
    plan_id,
    traffic_limit_bytes=0,
    traffic_limit_strategy="NO_RESET",
    next_traffic_reset_at=None,
    created_at=None,
    tag="paid",
    traffic_boost_bytes=0,
):
    created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    email = f"{user_uuid}@example.com"
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, remnawave_user_uuid,
                subscription_url, expire_at, created_at, description, tag,
                traffic_limit_bytes, traffic_limit_strategy, next_traffic_reset_at,
                traffic_boost_bytes
            ) VALUES (?, ?, ?, ?, ?, 'vless://sub', datetime('now', '+30 days'), ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                host_name,
                email,
                email,
                user_uuid,
                created_at,
                json.dumps({"v": 1, "source": "purchase", "plan_id": plan_id}),
                tag,
                traffic_limit_bytes,
                traffic_limit_strategy,
                next_traffic_reset_at,
                traffic_boost_bytes,
            ),
        )
        key_id = cur.lastrowid
        conn.commit()
    return key_id


class _FakePanel:
    def __init__(self):
        self.reset_calls = []
        self.limit_calls = []
        self.email_lookups = []

    async def reset_user_traffic(self, user_uuid):
        self.reset_calls.append(str(user_uuid))
        return True

    async def update_user_traffic_limit(self, user_uuid, new_limit, *, host_name=None):
        self.limit_calls.append((str(user_uuid), int(new_limit), host_name))
        return True

    async def get_user_by_email(self, email, *, host_name=None):
        self.email_lookups.append((email, host_name))
        return None


def _run_reset_worker(database, fake):
    from shop_bot.data_manager import scheduler
    from shop_bot.modules import remnawave_api

    originals = {
        name: getattr(remnawave_api, name)
        for name in ("reset_user_traffic", "update_user_traffic_limit", "get_user_by_email")
    }
    for name in originals:
        setattr(remnawave_api, name, getattr(fake, name))
    try:
        asyncio.run(scheduler.check_traffic_boost_resets(bot=None))
    finally:
        for name, fn in originals.items():
            setattr(remnawave_api, name, fn)


def test_strategy_is_month_rolling_only_for_main_limit(temp_db):
    database = temp_db
    limited = {"traffic_limit_bytes": 50 * GB, "lte_limit_bytes": 0}
    lte_only = {"traffic_limit_bytes": 0, "lte_limit_bytes": 20 * GB}
    unlimited = {"traffic_limit_bytes": 0, "lte_limit_bytes": 0}
    both = {"traffic_limit_bytes": 50 * GB, "lte_limit_bytes": 10 * GB}

    assert database.remnawave_traffic_limit_strategy_for_plan(limited) == "MONTH_ROLLING"
    assert database.remnawave_traffic_limit_strategy_for_plan(lte_only) == "NO_RESET"
    assert database.remnawave_traffic_limit_strategy_for_plan(unlimited) == "NO_RESET"
    assert database.remnawave_traffic_limit_strategy_for_plan(both) == "MONTH_ROLLING"
    assert database.plan_has_monthly_traffic_reset(limited)
    assert database.plan_has_monthly_traffic_reset(lte_only)
    assert not database.plan_has_monthly_traffic_reset(unlimited)


def test_apply_fields_sets_date_for_lte_only_without_month_rolling(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "LteOnly", traffic_gb=0, lte_gb=20)
    plan = database.get_plan_by_id(plan_id)
    key_id = _insert_key(
        database, user_id=1, host_name="LteOnly", user_uuid="u-lte", plan_id=plan_id
    )

    assert database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
    key = database.get_key_by_id(key_id)
    assert key["traffic_limit_strategy"] == "NO_RESET"
    assert key["next_traffic_reset_at"]
    reset_dt = datetime.fromisoformat(str(key["next_traffic_reset_at"]).replace(" ", "T"))
    assert reset_dt > datetime.now()
    assert database.format_next_traffic_reset_display(key["next_traffic_reset_at"])


def test_apply_fields_sets_month_rolling_for_limited_main(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "Limited", traffic_gb=50, lte_gb=0)
    plan = database.get_plan_by_id(plan_id)
    key_id = _insert_key(
        database,
        user_id=2,
        host_name="Limited",
        user_uuid="u-main",
        plan_id=plan_id,
        traffic_limit_bytes=50 * GB,
    )

    assert database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
    key = database.get_key_by_id(key_id)
    assert key["traffic_limit_strategy"] == "MONTH_ROLLING"
    assert key["next_traffic_reset_at"]


def test_apply_fields_clears_date_for_fully_unlimited(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "Unlim", traffic_gb=0, lte_gb=0)
    plan = database.get_plan_by_id(plan_id)
    key_id = _insert_key(
        database,
        user_id=3,
        host_name="Unlim",
        user_uuid="u-unlim",
        plan_id=plan_id,
        next_traffic_reset_at="2026-01-01 00:00:00",
        traffic_limit_strategy="MONTH_ROLLING",
    )

    assert database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=False)
    key = database.get_key_by_id(key_id)
    assert key["traffic_limit_strategy"] == "NO_RESET"
    assert not key.get("next_traffic_reset_at")


def test_extend_keeps_existing_future_reset_date(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "Keep", traffic_gb=30, lte_gb=10)
    plan = database.get_plan_by_id(plan_id)
    future = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S")
    key_id = _insert_key(
        database,
        user_id=4,
        host_name="Keep",
        user_uuid="u-keep",
        plan_id=plan_id,
        traffic_limit_bytes=30 * GB,
        traffic_limit_strategy="NO_RESET",
        next_traffic_reset_at=future,
        traffic_boost_bytes=5 * GB,
    )

    database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=False)
    key = database.get_key_by_id(key_id)
    assert str(key["next_traffic_reset_at"]).startswith(future[:16])
    assert key["traffic_limit_strategy"] == "MONTH_ROLLING"
    assert int(key.get("traffic_boost_bytes") or 0) == 5 * GB


def test_backfill_aligns_missing_date_to_created_at(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "Old", traffic_gb=0, lte_gb=15)
    created = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0) - timedelta(days=10)
    key_id = _insert_key(
        database,
        user_id=5,
        host_name="Old",
        user_uuid="u-old",
        plan_id=plan_id,
        created_at=created.strftime("%Y-%m-%d %H:%M:%S"),
    )

    n = database.backfill_monthly_traffic_reset_for_existing_keys()
    assert n >= 1
    key = database.get_key_by_id(key_id)
    expected = database.add_calendar_months(created, 1).strftime("%Y-%m-%d %H:%M:%S")
    assert key["next_traffic_reset_at"] == expected
    assert key["traffic_limit_strategy"] == "NO_RESET"


def test_backfill_sets_month_rolling_on_existing_limited_keys(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "Legacy", traffic_gb=40, lte_gb=0)
    key_id = _insert_key(
        database,
        user_id=6,
        host_name="Legacy",
        user_uuid="u-legacy",
        plan_id=plan_id,
        traffic_limit_bytes=40 * GB,
        traffic_limit_strategy="NO_RESET",
    )

    database.backfill_monthly_traffic_reset_for_existing_keys()
    key = database.get_key_by_id(key_id)
    assert key["traffic_limit_strategy"] == "MONTH_ROLLING"
    assert key["next_traffic_reset_at"]


def test_backfill_skips_trial_without_plan_id(temp_db):
    database = temp_db
    _create_host_and_plan(database, "TrialHost", traffic_gb=20, lte_gb=0)
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, remnawave_user_uuid,
                subscription_url, expire_at, created_at, description, tag,
                traffic_limit_bytes, traffic_limit_strategy
            ) VALUES (7, 'TrialHost', 'trial@example.com', 'trial@example.com', 'u-trial',
                      'vless://sub', datetime('now', '+3 days'), CURRENT_TIMESTAMP,
                      ?, 'trial', ?, 'NO_RESET')
            """,
            (json.dumps({"v": 1, "source": "trial", "is_trial": True}), 5 * GB),
        )
        key_id = cur.lastrowid
        conn.commit()

    database.backfill_monthly_traffic_reset_for_existing_keys()
    key = database.get_key_by_id(key_id)
    assert key["traffic_limit_strategy"] == "NO_RESET"
    assert not key.get("next_traffic_reset_at")


def test_scheduler_limited_main_resets_panel_and_burns_boost(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "MainReset", traffic_gb=50, lte_gb=10)
    past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    key_id = _insert_key(
        database,
        user_id=8,
        host_name="MainReset",
        user_uuid="u-reset-main",
        plan_id=plan_id,
        traffic_limit_bytes=70 * GB,
        traffic_limit_strategy="MONTH_ROLLING",
        next_traffic_reset_at=past,
        traffic_boost_bytes=20 * GB,
    )
    database.add_key_lte_boost_bytes(key_id, 5 * GB)

    fake = _FakePanel()
    _run_reset_worker(database, fake)

    assert fake.reset_calls == ["u-reset-main"]
    assert fake.limit_calls == [("u-reset-main", 50 * GB, "MainReset")]
    key = database.get_key_by_id(key_id)
    assert int(key["traffic_boost_bytes"] or 0) == 0
    assert int(key["traffic_limit_bytes"] or 0) == 50 * GB
    assert key["traffic_limit_strategy"] == "MONTH_ROLLING"
    reset_dt = datetime.fromisoformat(str(key["next_traffic_reset_at"]).replace(" ", "T"))
    assert reset_dt > datetime.now()
    lte = database.get_key_lte_state(key_id)
    assert int(lte["lte_baseline_reset_requested"] or 0) == 1


def test_scheduler_lte_only_skips_panel_and_rolls_lte_period(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "LteReset", traffic_gb=0, lte_gb=20)
    past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    key_id = _insert_key(
        database,
        user_id=9,
        host_name="LteReset",
        user_uuid="u-reset-lte",
        plan_id=plan_id,
        traffic_limit_bytes=0,
        traffic_limit_strategy="NO_RESET",
        next_traffic_reset_at=past,
    )
    database.add_key_lte_boost_bytes(key_id, 8 * GB)

    fake = _FakePanel()
    _run_reset_worker(database, fake)

    assert fake.reset_calls == []
    assert fake.limit_calls == []
    key = database.get_key_by_id(key_id)
    reset_dt = datetime.fromisoformat(str(key["next_traffic_reset_at"]).replace(" ", "T"))
    assert reset_dt > datetime.now()
    lte = database.get_key_lte_state(key_id)
    assert int(lte["lte_baseline_reset_requested"] or 0) == 1


def test_scheduler_future_date_is_not_processed(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "Future", traffic_gb=20, lte_gb=0)
    future = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_key(
        database,
        user_id=10,
        host_name="Future",
        user_uuid="u-future",
        plan_id=plan_id,
        traffic_limit_bytes=20 * GB,
        next_traffic_reset_at=future,
        traffic_boost_bytes=3 * GB,
    )

    fake = _FakePanel()
    _run_reset_worker(database, fake)
    assert fake.reset_calls == []


def test_create_plan_stores_month_rolling_for_limited_tariff(temp_db):
    database = temp_db
    plan_id = _create_host_and_plan(database, "PlanStrat", traffic_gb=25, lte_gb=5)
    plan = database.get_plan_by_id(plan_id)
    assert plan["traffic_limit_strategy"] == "MONTH_ROLLING"
    plan_id_unlim = _create_host_and_plan(database, "PlanUnlim", traffic_gb=0, lte_gb=5)
    plan_unlim = database.get_plan_by_id(plan_id_unlim)
    assert not plan_unlim.get("traffic_limit_strategy")
