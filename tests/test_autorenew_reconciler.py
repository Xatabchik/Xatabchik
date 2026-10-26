"""PR-A: журнал автопродления, сверка при старте, сверка зависших платежей, payment_id в выдаче."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from types import SimpleNamespace

import pytest

from conftest import insert_user, temp_db  # noqa: F401
from shop_bot.data_manager import auto_renew_ledger as ledger
from shop_bot.data_manager import key_write_guard as guard
from shop_bot.data_manager import reconciler

USER_ID = 5001
KEY_ID = 77
DAY_MS = 86400000


def _balance(database, user_id=USER_ID) -> float:
    with sqlite3.connect(database.DB_FILE) as conn:
        return float(conn.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)).fetchone()[0])


def _user(database, balance=500.0):
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="renew", balance=balance)


def _charge(database, price=100.0, target_ms=None, charge_id=None):
    return ledger.charge(
        charge_id=charge_id or ledger.make_charge_id(KEY_ID, 1_800_000_000),
        key_id=KEY_ID,
        user_id=USER_ID,
        host_name="h1",
        email="5001-1@bot.local",
        price=price,
        days=30,
        plan_id=1,
        target_ms=target_ms or int(time.time() * 1000) + 30 * DAY_MS,
    )


def _age(database, charge_id, seconds):
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE auto_renew_charges SET updated_at = ?, created_at = ? WHERE charge_id = ?",
            (time.time() - seconds, time.time() - seconds, charge_id),
        )
        conn.commit()


# --- журнал списаний -------------------------------------------------------------

def test_charge_debits_balance_and_is_idempotent(temp_db):
    _user(temp_db)
    assert _charge(temp_db) == "charged"
    assert _balance(temp_db) == 400.0
    assert _charge(temp_db) == "charged"
    assert _balance(temp_db) == 400.0, "повторный вызов по тому же сроку не должен списывать второй раз"


def test_charge_without_balance_changes_nothing(temp_db):
    _user(temp_db, balance=50.0)
    assert _charge(temp_db, price=100.0) == "no_balance"
    assert _balance(temp_db) == 50.0
    assert ledger.get_charge(ledger.make_charge_id(KEY_ID, 1_800_000_000)) is None


def test_applied_charge_is_not_charged_again(temp_db):
    _user(temp_db)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    assert _charge(temp_db) == "charged"
    assert ledger.mark_applied(cid) is True
    assert _charge(temp_db) == "applied"
    assert _balance(temp_db) == 400.0


def test_refund_happens_exactly_once(temp_db):
    _user(temp_db)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    _charge(temp_db)
    assert ledger.refund(cid) is True
    assert ledger.refund(cid) is False
    assert _balance(temp_db) == 500.0
    assert ledger.get_charge(cid)["state"] == "refunded"


def test_refund_after_applied_is_refused(temp_db):
    _user(temp_db)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    _charge(temp_db)
    ledger.mark_applied(cid)
    assert ledger.refund(cid) is False
    assert _balance(temp_db) == 400.0


def test_parallel_charges_debit_once(temp_db):
    import threading

    _user(temp_db)
    results = []

    def run():
        results.append(_charge(temp_db))

    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(results) == {"charged"}
    assert _balance(temp_db) == 400.0


def test_attempt_journal_survives_reconnect(temp_db):
    assert ledger.last_attempt_age_seconds(KEY_ID) is None
    ledger.record_attempt(KEY_ID)
    age = ledger.last_attempt_age_seconds(KEY_ID)
    assert age is not None and age < 5
    ledger.clear_attempt(KEY_ID)
    assert ledger.last_attempt_age_seconds(KEY_ID) is None


# --- сверка автопродления --------------------------------------------------------

def _patch_panel_expiry(monkeypatch, value):
    from shop_bot.modules import remnawave_api

    async def fake(host, email):
        if isinstance(value, Exception):
            raise value
        return (value is not None, value)

    monkeypatch.setattr(remnawave_api, "_read_panel_expiry_ms", fake)


def _capture_key_updates(monkeypatch):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    calls = []
    monkeypatch.setattr(rw_repo, "update_key_fields", lambda key_id, **kw: calls.append((key_id, kw)))
    return calls


def _as_restarted_process(monkeypatch):
    monkeypatch.setattr(guard, "BOOT_TS", time.time() + 10)


def test_startup_reconcile_keeps_debit_when_panel_reached_target(temp_db, monkeypatch):
    _as_restarted_process(monkeypatch)
    _user(temp_db)
    target = int(time.time() * 1000) + 30 * DAY_MS
    _charge(temp_db, target_ms=target)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    _patch_panel_expiry(monkeypatch, target + 1000)
    updates = _capture_key_updates(monkeypatch)

    result = asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace(), startup=True))

    assert result == [f"{cid}: applied"]
    assert ledger.get_charge(cid)["state"] == "applied"
    assert _balance(temp_db) == 400.0
    assert updates == [(KEY_ID, {"expire_at_ms": target + 1000})]


def test_startup_reconcile_refunds_when_panel_did_not_apply(temp_db, monkeypatch):
    _as_restarted_process(monkeypatch)
    _user(temp_db)
    target = int(time.time() * 1000) + 30 * DAY_MS
    _charge(temp_db, target_ms=target)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    _patch_panel_expiry(monkeypatch, target - 5 * DAY_MS)
    _capture_key_updates(monkeypatch)

    result = asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace(), startup=True))

    assert result == [f"{cid}: refunded"]
    assert _balance(temp_db) == 500.0
    kinds = [a["kind"] for a in guard.fetch_unsent_alerts(10)]
    assert "autorenew_refunded" in kinds
    # второй проход ничего не меняет
    assert asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace(), startup=True)) == []
    assert _balance(temp_db) == 500.0


def test_startup_reconcile_ignores_charges_of_this_process(temp_db, monkeypatch):
    _user(temp_db)
    _charge(temp_db)
    _patch_panel_expiry(monkeypatch, None)
    result = asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace(), startup=True))
    assert result == [], "запись, созданная после старта процесса, не принадлежит прошлой жизни"
    assert _balance(temp_db) == 400.0


def test_regular_reconcile_waits_for_stuck_window(temp_db, monkeypatch):
    _user(temp_db)
    target = int(time.time() * 1000) + 30 * DAY_MS
    _charge(temp_db, target_ms=target)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    _patch_panel_expiry(monkeypatch, target - DAY_MS)
    assert asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace())) == []
    _age(temp_db, cid, reconciler.AUTORENEW_STUCK_AFTER_SECONDS + 5)
    assert asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace())) == [f"{cid}: refunded"]


def test_reconcile_with_unavailable_panel_changes_nothing(temp_db, monkeypatch):
    _user(temp_db)
    _charge(temp_db)
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    _age(temp_db, cid, 2 * 3600)
    _patch_panel_expiry(monkeypatch, RuntimeError("panel down"))
    result = asyncio.run(reconciler.reconcile_auto_renew_charges(SimpleNamespace()))
    assert result == [f"{cid}: panel unavailable"]
    assert ledger.get_charge(cid)["state"] == "charged"
    assert _balance(temp_db) == 400.0
    assert [a["kind"] for a in guard.fetch_unsent_alerts(10)] == ["autorenew_unresolved"]


# --- планировщик автопродления ---------------------------------------------------

def _scheduler_env(temp_db, monkeypatch, create_impl):
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.data_manager import scheduler
    from shop_bot.modules import remnawave_api

    temp_db.update_setting("auto_renew_globally_enabled", "true")
    expire = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(1_800_000_000))
    key = {
        "key_id": KEY_ID,
        "user_id": USER_ID,
        "host_name": "h1",
        "key_email": "5001-1@bot.local",
        "expire_at": expire,
        "description": json.dumps({"plan_id": 1}),
    }
    monkeypatch.setattr(rw_repo, "get_keys_for_auto_renew", lambda hours_before=24: [dict(key)])
    monkeypatch.setattr(scheduler, "_parse_origin_meta_from_description", lambda d: {"plan_id": 1})
    monkeypatch.setattr(rw_repo, "get_plan_by_id", lambda pid: {
        "plan_id": 1, "price": 100.0, "months": 1, "duration_days": 30, "traffic_limit_bytes": 0,
    })
    monkeypatch.setattr(temp_db, "apply_key_monthly_reset_fields", lambda *a, **k: None)
    monkeypatch.setattr(remnawave_api, "create_or_update_key_on_host", create_impl)
    updates = _capture_key_updates(monkeypatch)
    notices = []

    async def ok(*a, **k):
        notices.append(("ok", a))

    async def nobal(*a, **k):
        notices.append(("no_balance", a))

    monkeypatch.setattr(scheduler, "_notify_auto_renew_success", ok)
    monkeypatch.setattr(scheduler, "_notify_auto_renew_no_balance", nobal)
    return scheduler, updates, notices


def test_scheduler_success_applies_and_keeps_debit(temp_db, monkeypatch):
    _user(temp_db)
    seen = {}

    async def create(**kw):
        seen.update(kw)
        return {"expiry_timestamp_ms": kw["expiry_timestamp_ms"]}

    scheduler, updates, notices = _scheduler_env(temp_db, monkeypatch, create)
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    assert seen["payment_id"] == cid
    assert ledger.get_charge(cid)["state"] == "applied"
    assert _balance(temp_db) == 400.0
    assert notices and notices[0][0] == "ok"
    assert updates


def test_scheduler_panel_rejection_refunds(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    _user(temp_db)

    async def create(**kw):
        raise remnawave_api.RemnawaveAPIError("Remnawave API request failed: 400 {'errorCode': 'A001'}")

    scheduler, updates, _ = _scheduler_env(temp_db, monkeypatch, create)
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    assert ledger.get_charge(cid)["state"] == "refunded"
    assert _balance(temp_db) == 500.0
    assert not updates


def test_scheduler_ambiguous_failure_keeps_charge_for_reconcile(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    _user(temp_db)

    async def create(**kw):
        raise remnawave_api.RemnawaveAmbiguousError("Remnawave API timeout: read")

    scheduler, updates, _ = _scheduler_env(temp_db, monkeypatch, create)
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    cid = ledger.make_charge_id(KEY_ID, 1_800_000_000)
    assert ledger.get_charge(cid)["state"] == "charged"
    assert _balance(temp_db) == 400.0
    assert not updates


def test_scheduler_cooldown_survives_restart_and_never_double_charges(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    _user(temp_db)
    calls = []

    async def create(**kw):
        calls.append(kw)
        raise remnawave_api.RemnawaveAmbiguousError("Remnawave API timeout: read")

    scheduler, _, _ = _scheduler_env(temp_db, monkeypatch, create)
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    assert len(calls) == 1, "журнал попыток в БД не даёт повторить попытку сразу после неё"
    assert _balance(temp_db) == 400.0


def test_scheduler_second_attempt_after_cooldown_does_not_debit_again(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    _user(temp_db)
    calls = []

    async def create(**kw):
        calls.append(kw)
        raise remnawave_api.RemnawaveAmbiguousError("Remnawave API timeout: read")

    scheduler, _, _ = _scheduler_env(temp_db, monkeypatch, create)
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute("UPDATE auto_renew_attempts SET last_attempt_at = 0")
        conn.commit()
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    assert len(calls) == 2
    assert _balance(temp_db) == 400.0


def test_scheduler_without_balance_notifies_and_does_not_touch_panel(temp_db, monkeypatch):
    _user(temp_db, balance=10.0)
    calls = []

    async def create(**kw):
        calls.append(kw)
        return {}

    scheduler, _, notices = _scheduler_env(temp_db, monkeypatch, create)
    asyncio.run(scheduler.check_auto_renewals(SimpleNamespace()))
    assert not calls
    assert [n[0] for n in notices] == ["no_balance"]
    assert _balance(temp_db) == 10.0


# --- сверка зависших платежей ----------------------------------------------------

class _Bot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))


def _pending(database, payment_id, *, status="paid", age=600, action="extend", claimed=False, tx_paid=False):
    meta = {"action": action, "user_id": USER_ID, "payment_id": payment_id}
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO pending_transactions (payment_id, user_id, amount_rub, metadata, status, updated_at) "
            "VALUES (?, ?, 100, ?, ?, datetime('now', ?))",
            (payment_id, USER_ID, json.dumps(meta), status, f"-{int(age)} seconds"),
        )
        if claimed:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_payments "
                "(payment_id TEXT PRIMARY KEY, processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute("INSERT OR IGNORE INTO processed_payments (payment_id) VALUES (?)", (payment_id,))
        if tx_paid:
            conn.execute(
                "INSERT INTO transactions (payment_id, user_id, status, amount_rub) VALUES (?, ?, 'paid', 100)",
                (payment_id, USER_ID),
            )
        conn.commit()


def _stub_fulfillment(monkeypatch, *, ok=True):
    calls = []

    async def fake(bot, metadata):
        calls.append(dict(metadata))
        return ok

    monkeypatch.setattr("shop_bot.bot.handlers.process_successful_payment", fake)
    return calls


def test_find_stuck_respects_age_window_and_confirmation(temp_db):
    _user(temp_db)
    _pending(temp_db, "young", age=30)
    _pending(temp_db, "stuck", age=600)
    _pending(temp_db, "ancient", age=3 * 86400)
    _pending(temp_db, "done", age=600, claimed=True, tx_paid=True)
    _pending(temp_db, "claim_only", age=600, claimed=True)
    _pending(temp_db, "waiting", status="pending", age=600)
    ids = sorted(r["payment_id"] for r in reconciler.find_stuck_paid_payments())
    assert ids == ["claim_only", "stuck"]


def test_mode_defaults_to_alert_and_validates(temp_db):
    assert reconciler.get_mode() == "alert"
    temp_db.update_setting("payment_reconciler_mode", "retry")
    assert reconciler.get_mode() == "retry"
    temp_db.update_setting("payment_reconciler_mode", "bogus")
    assert reconciler.get_mode() == "alert"


def test_mode_off_does_nothing(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1")
    calls = _stub_fulfillment(monkeypatch)
    temp_db.update_setting("payment_reconciler_mode", "off")
    assert asyncio.run(reconciler.reconcile_stuck_payments(_Bot())) == []
    assert not calls
    assert guard.fetch_unsent_alerts(10) == []


def test_mode_alert_only_alerts_and_dedupes(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1")
    calls = _stub_fulfillment(monkeypatch)
    for _ in range(3):
        asyncio.run(reconciler.reconcile_stuck_payments(_Bot()))
    assert not calls
    alerts = guard.fetch_unsent_alerts(10)
    assert [a["kind"] for a in alerts] == ["payment_stuck"]
    assert "p1" in alerts[0]["text"]


def test_mode_retry_claim_not_taken_retries_exactly_once_per_window(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", action="new")
    calls = _stub_fulfillment(monkeypatch)
    temp_db.update_setting("payment_reconciler_mode", "retry")
    first = asyncio.run(reconciler.reconcile_stuck_payments(_Bot()))
    second = asyncio.run(reconciler.reconcile_stuck_payments(_Bot()))
    assert first == ["p1: retry: ok"]
    assert second == ["p1: skip: лимит повторов"]
    assert len(calls) == 1
    assert calls[0]["payment_id"] == "p1"


def test_mode_retry_stops_after_max_attempts(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", action="new")
    calls = _stub_fulfillment(monkeypatch, ok=False)
    temp_db.update_setting("payment_reconciler_mode", "retry")
    for _ in range(reconciler.MAX_RETRIES + 2):
        asyncio.run(reconciler.reconcile_stuck_payments(_Bot()))
        with sqlite3.connect(temp_db.DB_FILE) as conn:
            conn.execute("UPDATE payment_reconcile_attempts SET last_attempt_at = 0")
            conn.commit()
    assert len(calls) == reconciler.MAX_RETRIES


def test_claimed_recent_payment_is_left_alone(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", age=300, claimed=True)
    calls = _stub_fulfillment(monkeypatch)
    temp_db.update_setting("payment_reconciler_mode", "retry")
    assert asyncio.run(reconciler.reconcile_stuck_payments(_Bot())) == ["p1: skip: выдача могла ещё идти"]
    assert not calls and guard.fetch_unsent_alerts(10) == []


def test_claimed_old_extend_retries_only_when_delta_is_on(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", age=1200, claimed=True, action="extend")
    calls = _stub_fulfillment(monkeypatch)
    temp_db.update_setting("payment_reconciler_mode", "retry")

    assert asyncio.run(reconciler.reconcile_stuck_payments(_Bot())) == ["p1: alert: выдача не завершена"]
    assert not calls

    temp_db.update_setting("key_write_lock_scope", "payments")
    temp_db.update_setting("key_extension_delta_scope", "payments")
    assert asyncio.run(reconciler.reconcile_stuck_payments(_Bot())) == ["p1: retry: ok"]
    assert len(calls) == 1
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        left = conn.execute("SELECT COUNT(*) FROM processed_payments WHERE payment_id = 'p1'").fetchone()[0]
    assert left == 0, "claim должен быть снят перед повтором"


def test_claimed_old_new_key_is_never_retried_automatically(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", age=1200, claimed=True, action="new")
    calls = _stub_fulfillment(monkeypatch)
    temp_db.update_setting("payment_reconciler_mode", "retry")
    temp_db.update_setting("key_write_lock_scope", "payments")
    temp_db.update_setting("key_extension_delta_scope", "payments")
    assert asyncio.run(reconciler.reconcile_stuck_payments(_Bot())) == ["p1: alert: выдача не завершена"]
    assert not calls


def test_recheck_payment_forces_retry_regardless_of_mode(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", age=20, action="extend")
    calls = _stub_fulfillment(monkeypatch)
    assert reconciler.get_mode() == "alert"
    assert asyncio.run(reconciler.recheck_payment(_Bot(), "p1")) == "Платёж p1: retry: ok"
    assert len(calls) == 1
    assert "не найдено" in asyncio.run(reconciler.recheck_payment(_Bot(), "missing"))
    assert asyncio.run(reconciler.recheck_payment(_Bot(), "  ")) == "Укажите payment_id."


def test_confirmed_payment_is_not_rechecked(temp_db, monkeypatch):
    _user(temp_db)
    _pending(temp_db, "p1", claimed=True, tx_paid=True)
    calls = _stub_fulfillment(monkeypatch)
    assert "не найдено" in asyncio.run(reconciler.recheck_payment(_Bot(), "p1"))
    assert not calls


def test_ops_iteration_takes_lock_and_sends_alerts(temp_db, monkeypatch):
    _user(temp_db)
    guard.add_ops_alert("test_kind", "тестовое оповещение")
    monkeypatch.setattr("shop_bot.data_manager.remnawave_repository.get_admin_ids", lambda: {111, 222})
    bot = _Bot()
    asyncio.run(reconciler.run_ops_iteration(bot))
    assert sorted(chat for chat, _ in bot.sent) == [111, 222]
    assert guard.fetch_unsent_alerts(10) == []

    guard.add_ops_alert("test_kind2", "ещё одно")
    assert guard.try_acquire_lock(reconciler.RECONCILER_LOCK_KEY, "other-copy", 60.0)
    bot2 = _Bot()
    asyncio.run(reconciler.run_ops_iteration(bot2))
    assert bot2.sent == [], "вторая копия сверки не должна работать, пока замок занят"


def test_process_stop_after_paid_is_finished_exactly_once_by_reconciler(temp_db, monkeypatch):
    """Платёж оплачен, процесс остановили до выдачи: сверка доводит ровно один раз."""
    _user(temp_db)
    _pending(temp_db, "p-stop", age=400, action="new")
    delivered = []

    async def fake(bot, metadata):
        pid = metadata["payment_id"]
        delivered.append(pid)
        with sqlite3.connect(temp_db.DB_FILE) as conn:
            conn.execute("INSERT OR IGNORE INTO processed_payments (payment_id) VALUES (?)", (pid,))
            conn.execute(
                "INSERT INTO transactions (payment_id, user_id, status, amount_rub) VALUES (?, ?, 'paid', 100)",
                (pid, USER_ID),
            )
            conn.commit()
        return True

    monkeypatch.setattr("shop_bot.bot.handlers.process_successful_payment", fake)
    temp_db.update_setting("payment_reconciler_mode", "retry")
    for _ in range(3):
        asyncio.run(reconciler.reconcile_stuck_payments(_Bot()))
    assert delivered == ["p-stop"]


# --- выдача передаёт payment_id в запись ключа -----------------------------------

def test_fulfillment_passes_payment_id_to_panel_write(temp_db, monkeypatch):
    from test_fulfillment_unreachable_chat import _buy_with_balance, _fake_bot_class

    _fake_bot_class(monkeypatch, send_raises=False)
    captured = []

    async def fake_create(*args, **kwargs):
        captured.append(dict(kwargs))
        return {
            "client_uuid": "uuid-pid",
            "short_uuid": "short-pid",
            "email": kwargs.get("email") or "pid@bot.local",
            "host_name": kwargs.get("host_name"),
            "squad_uuid": "squad-1",
            "subscription_url": "https://vpn.example/sub/pid",
            "connection_string": "https://vpn.example/sub/pid",
            "traffic_limit_bytes": None,
            "traffic_limit_strategy": None,
            "expiry_timestamp_ms": 1893456000000,
        }

    monkeypatch.setattr("shop_bot.modules.remnawave_api.create_or_update_key_on_host", fake_create)
    resp = _buy_with_balance(monkeypatch, user_id=4343, host_name="PidHost", username="pidbuyer")
    assert resp.json().get("paid") is True, resp.json()
    assert len(captured) == 1
    assert captured[0].get("payment_id"), "выдача обязана передать payment_id в запись ключа"


# --- схема и значения по умолчанию -----------------------------------------------

def test_initialize_db_creates_pr_a_tables_and_safe_defaults(temp_db):
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"key_write_locks", "key_extension_applied", "ops_alerts"} <= names
    assert guard.get_lock_scope() == "off"
    assert guard.get_delta_scope() == "off"
    assert reconciler.get_mode() == "alert"
