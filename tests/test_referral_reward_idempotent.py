"""Реферальное вознаграждение начисляется по payment_id ровно один раз.

Раньше `add_to_referral_balance` вызывался без привязки к платежу. Падение между
начислением и `log_transaction` с последующей повторной обработкой (сверка,
повторная вебхук-доставка после `unclaim_processed_payment`) начисляло бонус
второй раз. Повторный `reserve_promo_code` проверяется там же.
"""
import asyncio
import json
import sqlite3
import threading
import time
import uuid

import pytest

from conftest import insert_user, temp_db  # noqa: F401
from shop_bot.bot.user_router import fulfillment

REFERRER = 7001
BUYER = 7002
HOST = "RefHost"


class _Crash(BaseException):
    """Имитация падения процесса: не перехватывается `except Exception`."""


class _FakeMessage:
    async def edit_text(self, *a, **k):
        return None

    async def delete(self):
        return None


class _FakeBot:
    id = 777

    def __init__(self, *a, **k):
        self.session = self
        self.sent = []

    async def send_message(self, *a, **k):
        self.sent.append(k.get("text") or (a[1] if len(a) > 1 else None))
        return _FakeMessage()

    async def delete_message(self, *a, **k):
        return None

    async def close(self):
        return None


def _db(database):
    return sqlite3.connect(database.DB_FILE)


def _setup(database, monkeypatch, *, reward_type="fixed_purchase"):
    insert_user(database.DB_FILE, telegram_id=REFERRER, username="referrer", referral_balance=0, referral_balance_all=0)
    insert_user(database.DB_FILE, telegram_id=BUYER, username="buyer", referred_by=REFERRER)
    database.update_setting("referral_reward_type", reward_type)
    database.update_setting("fixed_referral_bonus_amount", "50")
    database.update_setting("referral_percentage", "10")
    database.create_plan(HOST, "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host(HOST)[0]["plan_id"]
    key_id = database.add_new_key(
        BUYER, HOST, "uuid-1", f"{BUYER}-1@bot.local", int(time.time() * 1000) + 86400000, short_uuid="s1"
    )

    async def fake_create(*args, **kwargs):
        return {
            "client_uuid": "uuid-1", "short_uuid": "s1", "email": kwargs.get("email"), "host_name": HOST,
            "squad_uuid": "sq", "subscription_url": "https://vpn.example/sub", "connection_string": "https://vpn.example/sub",
            "traffic_limit_bytes": None, "traffic_limit_strategy": None,
            "expiry_timestamp_ms": int(time.time() * 1000) + 30 * 86400000,
        }

    monkeypatch.setattr("shop_bot.modules.remnawave_api.create_or_update_key_on_host", fake_create)
    monkeypatch.setattr(fulfillment, "Bot", _FakeBot)
    return plan_id, key_id


def _meta(plan_id, key_id, payment_id=None, action="extend", **extra):
    return {
        "user_id": BUYER, "months": 1, "duration_days": 0, "price": 100.0, "action": action, "key_id": key_id,
        "host_name": HOST, "plan_id": plan_id, "payment_method": "YooKassa",
        "payment_id": payment_id or str(uuid.uuid4()), **extra,
    }


def _run(meta):
    return asyncio.run(fulfillment.process_successful_payment(_FakeBot(), meta))


def _referrer(database):
    with _db(database) as c:
        return c.execute(
            "SELECT referral_balance, referral_balance_all FROM users WHERE telegram_id = ?", (REFERRER,)
        ).fetchone()


def _rewards(database, pid):
    with _db(database) as c:
        return c.execute("SELECT kind, amount FROM referral_rewards WHERE payment_id = ?", (pid,)).fetchall()


def _paid_transactions(database, pid):
    with _db(database) as c:
        return c.execute("SELECT COUNT(*) FROM transactions WHERE payment_id = ? AND status = 'paid'", (pid,)).fetchone()[0]


# --- примитив начисления ---------------------------------------------------------

def test_accrue_once_credits_both_balances_and_ignores_repeat(temp_db):
    insert_user(temp_db.DB_FILE, telegram_id=REFERRER, username="r", referral_balance=1.0, referral_balance_all=2.0)
    assert temp_db.accrue_referral_reward_once("p1", REFERRER, 50.0) == "accrued"
    assert temp_db.accrue_referral_reward_once("p1", REFERRER, 50.0) == "already"
    assert tuple(_referrer(temp_db)) == (51.0, 52.0)


def test_accrue_once_is_per_payment_and_per_kind(temp_db):
    insert_user(temp_db.DB_FILE, telegram_id=REFERRER, username="r", referral_balance=0, referral_balance_all=0)
    assert temp_db.accrue_referral_reward_once("p1", REFERRER, 10.0, kind="purchase") == "accrued"
    assert temp_db.accrue_referral_reward_once("p2", REFERRER, 10.0, kind="purchase") == "accrued"
    assert temp_db.accrue_referral_reward_once("p1", REFERRER, 10.0, kind="topup") == "accrued"
    assert tuple(_referrer(temp_db)) == (30.0, 30.0)


def test_accrue_once_failure_leaves_no_record_so_retry_can_credit(temp_db):
    assert temp_db.accrue_referral_reward_once("p1", 999999, 10.0) == "failed"
    assert temp_db.accrue_referral_reward_once("", REFERRER, 10.0) == "failed"
    assert temp_db.accrue_referral_reward_once("p1", REFERRER, 0) == "failed"
    insert_user(temp_db.DB_FILE, telegram_id=REFERRER, username="r", referral_balance=0, referral_balance_all=0)
    assert temp_db.accrue_referral_reward_once("p1", REFERRER, 10.0) == "accrued"


def test_accrue_once_parallel_calls_credit_once(temp_db):
    insert_user(temp_db.DB_FILE, telegram_id=REFERRER, username="r", referral_balance=0, referral_balance_all=0)
    results = []

    def run():
        results.append(temp_db.accrue_referral_reward_once("p-par", REFERRER, 25.0))

    threads = [threading.Thread(target=run) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["accrued"] + ["already"] * 7
    assert tuple(_referrer(temp_db)) == (25.0, 25.0)


# --- сценарий владельца: падение между начислением и log_transaction -------------

def test_crash_between_accrual_and_log_transaction_then_retry_credits_once(temp_db, monkeypatch):
    plan_id, key_id = _setup(temp_db, monkeypatch)
    pid = "pay-crash-1"
    real_log = fulfillment.log_transaction

    def crashing_log(*a, **k):
        raise _Crash()

    monkeypatch.setattr(fulfillment, "log_transaction", crashing_log)
    with pytest.raises(_Crash):
        _run(_meta(plan_id, key_id, pid))
    assert tuple(_referrer(temp_db)) == (50.0, 50.0), "бонус начислен до падения"
    assert _paid_transactions(temp_db, pid) == 0, "итоговой записи ещё нет"

    monkeypatch.setattr(fulfillment, "log_transaction", real_log)
    temp_db.unclaim_processed_payment(pid)
    assert _run(_meta(plan_id, key_id, pid)) is True

    assert tuple(_referrer(temp_db)) == (50.0, 50.0), "повторная обработка не должна начислять второй раз"
    assert _rewards(temp_db, pid) == [("purchase", 50.0)]
    assert _paid_transactions(temp_db, pid) == 1


def test_plain_redelivery_after_success_does_not_credit_again(temp_db, monkeypatch):
    plan_id, key_id = _setup(temp_db, monkeypatch)
    pid = "pay-redeliver-1"
    assert _run(_meta(plan_id, key_id, pid)) is True
    assert _run(_meta(plan_id, key_id, pid)) is True
    assert tuple(_referrer(temp_db)) == (50.0, 50.0)


def test_retry_after_unclaim_with_completed_payment_does_not_credit_again(temp_db, monkeypatch):
    plan_id, key_id = _setup(temp_db, monkeypatch)
    pid = "pay-unclaim-1"
    assert _run(_meta(plan_id, key_id, pid)) is True
    temp_db.unclaim_processed_payment(pid)
    _run(_meta(plan_id, key_id, pid))
    assert tuple(_referrer(temp_db)) == (50.0, 50.0)


def test_percent_reward_is_credited_per_distinct_payment(temp_db, monkeypatch):
    plan_id, key_id = _setup(temp_db, monkeypatch, reward_type="percent_purchase")
    assert _run(_meta(plan_id, key_id, "pay-a")) is True
    assert _run(_meta(plan_id, key_id, "pay-b")) is True
    assert tuple(_referrer(temp_db)) == (20.0, 20.0)


def test_referrer_is_notified_only_on_first_accrual(temp_db, monkeypatch):
    plan_id, key_id = _setup(temp_db, monkeypatch)
    sent = []

    async def spy(bot, user_id, text, **kw):
        sent.append((user_id, text))
        return True

    monkeypatch.setattr(fulfillment, "_deliver_to_user", spy)
    pid = "pay-notify-1"
    _run(_meta(plan_id, key_id, pid))
    temp_db.unclaim_processed_payment(pid)
    _run(_meta(plan_id, key_id, pid))
    to_referrer = [t for uid, t in sent if uid == REFERRER]
    assert len(to_referrer) == 1 and "реферальное вознаграждение" in to_referrer[0]


def test_topup_referral_reward_is_idempotent(temp_db, monkeypatch):
    _setup(temp_db, monkeypatch)
    pid = "pay-topup-1"
    meta = {
        "user_id": BUYER, "action": "top_up", "price": 200.0, "payment_method": "YooKassa", "payment_id": pid,
        "months": 0, "host_name": "", "plan_id": 0, "key_id": 0,
    }
    assert _run(dict(meta)) is True
    first = tuple(_referrer(temp_db))
    temp_db.unclaim_processed_payment(pid)
    _run(dict(meta))
    assert tuple(_referrer(temp_db)) == first
    assert first == (50.0, 50.0)
    assert _rewards(temp_db, pid) == [("topup", 50.0)]


def test_balance_payments_do_not_accrue_referral(temp_db, monkeypatch):
    plan_id, key_id = _setup(temp_db, monkeypatch)
    meta = _meta(plan_id, key_id, "pay-balance-1", payment_method="Balance")
    assert _run(meta) is True
    assert tuple(_referrer(temp_db)) == (0.0, 0.0)


# --- повторный reserve_promo_code --------------------------------------------------

def _promo(database, code="SALE10", **kw):
    with _db(database) as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(promo_codes)")]
    values = {"code": code, "discount_percent": 10, "is_active": 1, "usage_limit_total": 5, "used_total": 0}
    values.update(kw)
    values = {k: v for k, v in values.items() if k in cols}
    with _db(database) as c:
        c.execute(
            f"INSERT INTO promo_codes ({', '.join(values)}) VALUES ({', '.join('?' for _ in values)})", tuple(values.values())
        )
        c.commit()


def _used_total(database, code="SALE10"):
    with _db(database) as c:
        return c.execute("SELECT used_total FROM promo_codes WHERE code = ?", (code,)).fetchone()[0]


def test_reserve_promo_is_idempotent_for_same_payment(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw

    insert_user(temp_db.DB_FILE, telegram_id=BUYER, username="buyer")
    _promo(temp_db)
    for _ in range(3):
        promo, err = rw.reserve_promo_code("SALE10", BUYER, "pay-promo-1")
        assert err is None and promo
    assert _used_total(temp_db) == 1


def test_reserve_after_redeem_does_not_take_second_slot(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw

    insert_user(temp_db.DB_FILE, telegram_id=BUYER, username="buyer")
    _promo(temp_db)
    rw.reserve_promo_code("SALE10", BUYER, "pay-promo-2")
    assert rw.redeem_promo_code("SALE10", BUYER, applied_amount=10.0, order_id="pay-promo-2")
    promo, err = rw.reserve_promo_code("SALE10", BUYER, "pay-promo-2")
    assert err is None and promo
    assert rw.redeem_promo_code("SALE10", BUYER, applied_amount=10.0, order_id="pay-promo-2")
    assert _used_total(temp_db) == 1
    with _db(temp_db) as c:
        assert c.execute("SELECT COUNT(*) FROM promo_code_usages WHERE order_id = 'pay-promo-2'").fetchone()[0] == 1


def test_reserve_after_stale_release_takes_the_slot_again(temp_db):
    """Платёж пришёл после того, как резерв освободили по TTL: выдача не должна застревать."""
    from shop_bot.data_manager import remnawave_repository as rw

    insert_user(temp_db.DB_FILE, telegram_id=BUYER, username="buyer")
    _promo(temp_db)
    assert rw.reserve_promo_code("SALE10", BUYER, "pay-promo-3")[1] is None
    assert rw.release_promo_reservation("pay-promo-3") is True
    assert _used_total(temp_db) == 0
    promo, err = rw.reserve_promo_code("SALE10", BUYER, "pay-promo-3")
    assert err is None and promo
    assert _used_total(temp_db) == 1
    assert rw.reserve_promo_code("SALE10", BUYER, "pay-promo-3")[1] is None
    assert _used_total(temp_db) == 1


def test_reserve_after_release_respects_total_limit(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw

    insert_user(temp_db.DB_FILE, telegram_id=BUYER, username="buyer")
    insert_user(temp_db.DB_FILE, telegram_id=BUYER + 1, username="other")
    _promo(temp_db, usage_limit_total=1)
    rw.reserve_promo_code("SALE10", BUYER, "pay-promo-4")
    rw.release_promo_reservation("pay-promo-4")
    assert rw.reserve_promo_code("SALE10", BUYER + 1, "pay-promo-5")[1] is None
    promo, err = rw.reserve_promo_code("SALE10", BUYER, "pay-promo-4")
    assert promo is None and err == "total_limit_reached"
    assert _used_total(temp_db) == 1
