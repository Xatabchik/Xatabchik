"""
Таргетинг промокодов: applicable_plan_ids и segment_type.

Аддитивная фича — NULL/пустые поля ведут себя как безусловный купон.
Проверки тарифа и сегмента живут внутри check_promo_code_available /
reserve_promo_code (та же BEGIN IMMEDIATE секция, что и лимиты), чтобы не
открыть TOCTOU. Пользовательский текст ошибки одинаков для всех причин
отказа — защита от оракула по сегменту/тарифу/существованию кода.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def _make_plan(database, host_name: str, price: float = 100.0, plan_name: str = "1 месяц") -> int:
    database.create_plan(host_name, plan_name, 1, price)
    return database.get_plans_for_host(host_name)[-1]["plan_id"]


def _insert_key(db_path, *, user_id: int, expire_at: str, email: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at)
            VALUES (?, 'PromoHost', ?, ?, 'vless://x', ?, CURRENT_TIMESTAMP)
            """,
            (user_id, email, email, expire_at),
        )
        conn.commit()


def _paid_tx(database, *, user_id: int, payment_id: str, amount: float, method: str = "YooKassa") -> None:
    database.log_transaction(
        "promo-user",
        None,
        payment_id,
        user_id,
        "paid",
        amount,
        None,
        None,
        method,
        "{}",
    )


def _neutral(rw_repo, reason: str) -> str:
    return rw_repo.promo_error_message(reason)


def test_unconditional_promo_still_works_on_any_plan_any_user(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    plan_a = _make_plan(temp_db, "HostA")
    plan_b = _make_plan(temp_db, "HostB")
    rw_repo.create_promo_code("OPEN", discount_percent=10)

    ok_a, err_a = rw_repo.check_promo_code_available("OPEN", 101, plan_id=plan_a)
    ok_b, err_b = rw_repo.check_promo_code_available("OPEN", 202, plan_id=plan_b)
    assert ok_a is not None and err_a is None
    assert ok_b is not None and err_b is None

    reserved, rerr = rw_repo.reserve_promo_code("OPEN", 101, "pay-open", plan_id=plan_b)
    assert reserved is not None and rerr is None


def test_applicable_plan_ids_allows_listed_plan_and_rejects_other(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(temp_db.DB_FILE, telegram_id=61001, username="plan-user")
    token = issue_auth_token(61001)
    plan_ok = _make_plan(temp_db, "PlanHostOk")
    plan_no = _make_plan(temp_db, "PlanHostNo")
    rw_repo.create_promo_code("PLAN1", discount_percent=20, applicable_plan_ids=[plan_ok])

    promo, err = rw_repo.check_promo_code_available("PLAN1", 61001, plan_id=plan_ok)
    assert promo is not None and err is None
    fail, ferr = rw_repo.check_promo_code_available("PLAN1", 61001, plan_id=plan_no)
    assert fail is None and ferr == "plan_not_eligible"

    client = TestClient(handlers.app)
    resp_ok = client.post(
        "/api/apply-promo",
        json={"user_id": 61001, "token": token, "promo_code": "PLAN1", "plan_id": plan_ok, "price": 200},
    )
    resp_no = client.post(
        "/api/apply-promo",
        json={"user_id": 61001, "token": token, "promo_code": "PLAN1", "plan_id": plan_no, "price": 200},
    )
    assert resp_ok.json().get("ok") is True
    assert resp_no.json().get("ok") is False
    assert resp_no.json().get("error") == _neutral(rw_repo, "total_limit_reached")
    assert resp_no.json().get("error") == _neutral(rw_repo, "plan_not_eligible")


def test_no_active_subscription_segment(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(temp_db.DB_FILE, telegram_id=61002, username="nosub")
    insert_user(temp_db.DB_FILE, telegram_id=61003, username="hassub")
    token_no = issue_auth_token(61002)
    token_yes = issue_auth_token(61003)
    plan_id = _make_plan(temp_db, "SegHost")
    rw_repo.create_promo_code(
        "NOSUB",
        discount_percent=15,
        segment_type="no_active_subscription",
    )
    future = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_key(temp_db.DB_FILE, user_id=61003, expire_at=future, email="active@example.com")

    ok, err = rw_repo.check_promo_code_available("NOSUB", 61002, plan_id=plan_id)
    assert ok is not None and err is None
    fail, ferr = rw_repo.check_promo_code_available("NOSUB", 61003, plan_id=plan_id)
    assert fail is None and ferr == "segment_not_eligible"

    client = TestClient(handlers.app)
    resp_ok = client.post(
        "/api/apply-promo",
        json={"user_id": 61002, "token": token_no, "promo_code": "NOSUB", "plan_id": plan_id, "price": 100},
    )
    resp_no = client.post(
        "/api/apply-promo",
        json={"user_id": 61003, "token": token_yes, "promo_code": "NOSUB", "plan_id": plan_id, "price": 100},
    )
    assert resp_ok.json().get("ok") is True
    assert resp_no.json().get("ok") is False
    assert resp_no.json().get("error") == _neutral(rw_repo, "user_limit_reached")


def test_min_total_spent_counts_only_paid_not_pending(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    insert_user(temp_db.DB_FILE, telegram_id=61004, username="spent-low")
    insert_user(temp_db.DB_FILE, telegram_id=61005, username="spent-high")
    insert_user(temp_db.DB_FILE, telegram_id=61006, username="spent-pending")
    plan_id = _make_plan(temp_db, "SpentHost")
    rw_repo.create_promo_code(
        "VIP1K",
        discount_percent=25,
        segment_type="min_total_spent",
        segment_value=1000,
    )

    _paid_tx(temp_db, user_id=61004, payment_id="paid-500", amount=500)
    _paid_tx(temp_db, user_id=61005, payment_id="paid-1500", amount=1500)
    temp_db.create_payload_pending(
        "pend-9999",
        61006,
        9999.0,
        {"user_id": 61006, "payment_method": "YooKassa"},
    )

    low, low_err = rw_repo.check_promo_code_available("VIP1K", 61004, plan_id=plan_id)
    high, high_err = rw_repo.check_promo_code_available("VIP1K", 61005, plan_id=plan_id)
    pending, pending_err = rw_repo.check_promo_code_available("VIP1K", 61006, plan_id=plan_id)

    assert low is None and low_err == "segment_not_eligible"
    assert high is not None and high_err is None
    assert pending is None and pending_err == "segment_not_eligible"

    # pending_transactions.status='paid' DOES count (same as check-payment after PR #75)
    insert_user(temp_db.DB_FILE, telegram_id=61007, username="spent-pending-paid")
    temp_db.create_payload_pending(
        "pend-paid-1200",
        61007,
        1200.0,
        {"user_id": 61007, "payment_method": "YooKassa"},
    )
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute(
            "UPDATE pending_transactions SET status = 'paid' WHERE payment_id = ?",
            ("pend-paid-1200",),
        )
        conn.commit()
    ok_pending_paid, err_pending_paid = rw_repo.check_promo_code_available(
        "VIP1K", 61007, plan_id=plan_id
    )
    assert ok_pending_paid is not None and err_pending_paid is None


def test_plan_and_segment_must_both_match(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    insert_user(temp_db.DB_FILE, telegram_id=61008, username="combo-ok")
    insert_user(temp_db.DB_FILE, telegram_id=61009, username="combo-sub")
    plan_ok = _make_plan(temp_db, "ComboOk")
    plan_no = _make_plan(temp_db, "ComboNo")
    rw_repo.create_promo_code(
        "COMBO",
        discount_percent=30,
        applicable_plan_ids=[plan_ok],
        segment_type="no_active_subscription",
    )
    future = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    _insert_key(temp_db.DB_FILE, user_id=61009, expire_at=future, email="combo-sub@example.com")

    ok, err = rw_repo.check_promo_code_available("COMBO", 61008, plan_id=plan_ok)
    assert ok is not None and err is None

    wrong_plan, wp_err = rw_repo.check_promo_code_available("COMBO", 61008, plan_id=plan_no)
    assert wrong_plan is None and wp_err == "plan_not_eligible"

    wrong_seg, ws_err = rw_repo.check_promo_code_available("COMBO", 61009, plan_id=plan_ok)
    assert wrong_seg is None and ws_err == "segment_not_eligible"


def test_targeting_refusal_reasons_share_neutral_user_text(temp_db):
    """Оракул: UI/API не должен различать not_found / plan / segment / лимиты."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(temp_db.DB_FILE, telegram_id=61010, username="oracle")
    token = issue_auth_token(61010)
    plan_ok = _make_plan(temp_db, "OracleOk")
    plan_no = _make_plan(temp_db, "OracleNo")
    rw_repo.create_promo_code("ORPLAN", discount_percent=10, applicable_plan_ids=[plan_ok])
    rw_repo.create_promo_code(
        "ORSEG",
        discount_percent=10,
        segment_type="min_total_spent",
        segment_value=1000,
    )
    rw_repo.create_promo_code("ORLIM", discount_percent=10, usage_limit_total=1)
    rw_repo.reserve_promo_code("ORLIM", 1, "pay-orlim", plan_id=plan_ok)

    client = TestClient(handlers.app)

    def _apply(code: str, plan_id: int) -> str:
        resp = client.post(
            "/api/apply-promo",
            json={"user_id": 61010, "token": token, "promo_code": code, "plan_id": plan_id, "price": 100},
        )
        data = resp.json()
        assert data.get("ok") is False, data
        return data.get("error") or ""

    msg_limit = _apply("ORLIM", plan_ok)
    msg_plan = _apply("ORPLAN", plan_no)
    msg_seg = _apply("ORSEG", plan_ok)
    msg_missing = _apply("NOSUCHCODE", plan_ok)
    msg_user_limit = _neutral(rw_repo, "user_limit_reached")
    msg_total = _neutral(rw_repo, "total_limit_reached")

    assert msg_limit == msg_plan == msg_seg == msg_missing == msg_user_limit == msg_total
    assert msg_limit == rw_repo.PROMO_USER_ERROR
    assert _neutral(rw_repo, "plan_not_eligible") == _neutral(rw_repo, "segment_not_eligible")
    assert _neutral(rw_repo, "not_found") == _neutral(rw_repo, "total_limit_reached")


def test_segment_coupon_limit_one_stays_atomic_under_threads(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    plan_id = _make_plan(temp_db, "RaceSegHost")
    rw_repo.create_promo_code(
        "SEGRACE",
        discount_percent=40,
        usage_limit_total=1,
        segment_type="no_active_subscription",
    )

    def _one(i: int):
        return rw_repo.reserve_promo_code(
            "SEGRACE",
            7000 + i,
            f"pay-segrace-{i}",
            plan_id=plan_id,
        )

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_one, i) for i in range(8)]
        for fut in as_completed(futs):
            results.append(fut.result())

    wins = [r for r in results if r[0] is not None]
    losses = [r for r in results if r[0] is None]
    assert len(wins) == 1, results
    assert len(losses) == 7
    assert all(r[1] == "total_limit_reached" for r in losses)
    assert int(rw_repo.get_promo_code("SEGRACE")["used_total"] or 0) == 1


def test_create_promo_code_validates_targeting(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    plan_id = _make_plan(temp_db, "ValHost")
    try:
        rw_repo.create_promo_code("BADPLANS", discount_percent=10, applicable_plan_ids=[])
        assert False, "empty plan list must be rejected"
    except ValueError:
        pass
    try:
        rw_repo.create_promo_code("BADPLANX", discount_percent=10, applicable_plan_ids=[999999])
        assert False, "unknown plan_id must be rejected"
    except ValueError:
        pass
    try:
        rw_repo.create_promo_code(
            "BADSEG",
            discount_percent=10,
            segment_type="min_total_spent",
            segment_value=0,
        )
        assert False, "segment_value <= 0 must be rejected"
    except ValueError:
        pass
    try:
        rw_repo.create_promo_code("BADTYPE", discount_percent=10, segment_type="vip")
        assert False, "unknown segment_type must be rejected"
    except ValueError:
        pass

    assert rw_repo.create_promo_code(
        "OKTGT",
        discount_percent=10,
        applicable_plan_ids=[plan_id],
        segment_type="min_total_spent",
        segment_value=100,
    )


def test_create_payment_plan_mismatch_uses_neutral_message(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(temp_db.DB_FILE, telegram_id=61011, username="pay-tgt")
    token = issue_auth_token(61011)
    temp_db.update_setting("stars_per_rub", "2")
    plan_ok = _make_plan(temp_db, "PayTgtOk")
    plan_no = _make_plan(temp_db, "PayTgtNo")
    rw_repo.create_promo_code("PAYPLAN", discount_percent=50, applicable_plan_ids=[plan_ok])

    async def fake_send_invoice_stars(user_id, title, description, payload, amount):
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_send_invoice_stars)
    client = TestClient(handlers.app)
    resp = client.post(
        "/api/create-payment",
        json={
            "user_id": 61011,
            "token": token,
            "payment_method": "pay_stars",
            "plan_id": plan_no,
            "action": "new",
            "promo_code": "PAYPLAN",
        },
    )
    data = resp.json()
    assert data.get("ok") is False
    assert data.get("error") == _neutral(rw_repo, "total_limit_reached")
