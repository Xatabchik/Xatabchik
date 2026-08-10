"""Метрики аналитики: ключ без реальных денег + статистика триалов/продлений."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

from conftest import insert_user, temp_db  # noqa: F401


def _insert_key(
    db_path,
    *,
    user_id: int,
    tag: str | None = None,
    expire_at: str | None = None,
    created_at: str | None = None,
    email: str | None = None,
) -> int:
    email = email or f"u{user_id}-{_utcnow().timestamp()}@test.local"
    expire_at = expire_at or (_utcnow() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    created_at = created_at or _utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at, tag)
            VALUES (?, 'TestHost', ?, ?, 'vless://x', ?, ?, ?)
            """,
            (user_id, email, email, expire_at, created_at, tag),
        )
        conn.commit()
        return int(cur.lastrowid)


def _insert_tx(
    db_path,
    *,
    user_id: int,
    payment_method: str,
    status: str = "paid",
    amount_rub: float = 100.0,
    action: str | None = None,
    key_id: int | None = None,
    payment_id: str | None = None,
) -> None:
    meta = {}
    if action is not None:
        meta["action"] = action
    if key_id is not None:
        meta["key_id"] = key_id
        meta["plan_id"] = 1
    payment_id = payment_id or f"tx:{user_id}:{payment_method}:{action}:{key_id}:{_utcnow().timestamp()}"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO transactions
                (username, payment_id, user_id, status, amount_rub, payment_method, metadata, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"user{user_id}",
                payment_id,
                user_id,
                status,
                amount_rub,
                payment_method,
                json.dumps(meta, ensure_ascii=False),
                _utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()


def test_user_with_key_and_no_payments_counted(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7001, username="nopay")
    _insert_key(database.DB_FILE, user_id=7001, tag="trial")

    stats = database.get_users_without_real_payment_with_keys()
    assert stats["users_with_key_no_real_payment"] == 1


def test_user_paid_by_card_not_counted(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7002, username="cardpay")
    _insert_key(database.DB_FILE, user_id=7002, tag="paid")
    _insert_tx(database.DB_FILE, user_id=7002, payment_method="YooMoney", action="new")

    stats = database.get_users_without_real_payment_with_keys()
    assert stats["users_with_key_no_real_payment"] == 0


def test_user_paid_only_referral_balance_is_counted(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7003, username="refonly")
    key_id = _insert_key(database.DB_FILE, user_id=7003, tag="paid")
    _insert_tx(
        database.DB_FILE,
        user_id=7003,
        payment_method="ReferralBalance",
        action="new",
        key_id=key_id,
    )

    stats = database.get_users_without_real_payment_with_keys()
    assert stats["users_with_key_no_real_payment"] == 1


def test_balance_purchase_after_real_topup_not_counted(temp_db):
    """Пополнил картой → купил с Balance: реальная оплата уже была."""
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7004, username="topup")
    key_id = _insert_key(database.DB_FILE, user_id=7004, tag="paid")
    _insert_tx(database.DB_FILE, user_id=7004, payment_method="Cryptobot", action="top_up", amount_rub=200)
    _insert_tx(database.DB_FILE, user_id=7004, payment_method="Balance", action="new", key_id=key_id)

    stats = database.get_users_without_real_payment_with_keys()
    assert stats["users_with_key_no_real_payment"] == 0


def test_active_and_expired_trial_keys(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7101, username="trial_active", trial_used=1)
    insert_user(database.DB_FILE, telegram_id=7102, username="trial_expired", trial_used=1)
    insert_user(database.DB_FILE, telegram_id=7103, username="no_trial", trial_used=0)

    future = (_utcnow() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    past = (_utcnow() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_key(database.DB_FILE, user_id=7101, tag="trial", expire_at=future)
    _insert_key(database.DB_FILE, user_id=7102, tag="trial", expire_at=past)

    stats = database.get_trial_key_stats()
    assert stats["active_trial_users"] == 1
    assert stats["total_trial_used"] == 2


def test_extended_trial_real_money(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7201, username="ext_real", trial_used=1)
    # Как в проде: после extend tag становится paid, key_id тот же.
    t0 = (_utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    key_id = _insert_key(
        database.DB_FILE,
        user_id=7201,
        tag="paid",
        created_at=t0,
        expire_at=(_utcnow() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    _insert_tx(
        database.DB_FILE,
        user_id=7201,
        payment_method="Platega",
        action="extend",
        key_id=key_id,
    )

    stats = database.get_trial_key_stats()
    assert stats["extended_trial_real_money"] == 1
    assert stats["extended_trial_via_referral_balance"] == 0


def test_extended_trial_via_referral_balance(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7202, username="ext_ref", trial_used=1)
    t0 = (_utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    key_id = _insert_key(database.DB_FILE, user_id=7202, tag="paid", created_at=t0)
    _insert_tx(
        database.DB_FILE,
        user_id=7202,
        payment_method="ReferralBalance",
        action="extend",
        key_id=key_id,
    )

    stats = database.get_trial_key_stats()
    assert stats["extended_trial_via_referral_balance"] == 1
    assert stats["extended_trial_real_money"] == 0


def test_extend_of_second_paid_key_not_counted_as_trial_extend(temp_db):
    """Продлили второй (платный) ключ — это не продление триала."""
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7203, username="two_keys", trial_used=1)
    t0 = (_utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    t1 = (_utcnow() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_key(database.DB_FILE, user_id=7203, tag="paid", created_at=t0, email="first@test.local")
    second_id = _insert_key(database.DB_FILE, user_id=7203, tag="paid", created_at=t1, email="second@test.local")
    _insert_tx(
        database.DB_FILE,
        user_id=7203,
        payment_method="YooMoney",
        action="extend",
        key_id=second_id,
    )

    stats = database.get_trial_key_stats()
    assert stats["extended_trial_real_money"] == 0
    assert stats["extended_trial_via_referral_balance"] == 0


def test_balance_extend_of_trial_not_in_real_or_referral_buckets(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7204, username="ext_bal", trial_used=1)
    t0 = (_utcnow() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    key_id = _insert_key(database.DB_FILE, user_id=7204, tag="paid", created_at=t0)
    _insert_tx(
        database.DB_FILE,
        user_id=7204,
        payment_method="Balance",
        action="extend",
        key_id=key_id,
    )

    stats = database.get_trial_key_stats()
    assert stats["extended_trial_real_money"] == 0
    assert stats["extended_trial_via_referral_balance"] == 0
