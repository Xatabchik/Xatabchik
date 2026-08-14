"""
Регрессия CWE-362 (TOCTOU) лимита промокодов.

Старый код: check_promo_code_available делал SELECT, redeem_promo_code
отдельным UPDATE used_total = used_total + 1 без WHERE по лимиту — два
параллельных платежа оба проходили проверку при usage_limit_total=1.

Новый код: атомарный UPDATE ... WHERE used_total < usage_limit_total
(rowcount == 0 → отказ) + резерв слота при создании pending.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def _make_plan(database, host_name: str, price: float = 100.0) -> int:
    database.create_plan(host_name, "1 месяц", 1, price)
    return database.get_plans_for_host(host_name)[0]["plan_id"]


def test_reserve_limit_one_only_one_winner_sequential(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("LIMIT1", discount_percent=90, usage_limit_total=1)
    promo_a, err_a = rw_repo.reserve_promo_code("LIMIT1", 101, "pay-a", applied_amount=90)
    promo_b, err_b = rw_repo.reserve_promo_code("LIMIT1", 102, "pay-b", applied_amount=90)

    assert promo_a is not None and err_a is None
    assert promo_b is None
    assert err_b == "total_limit_reached"
    assert int(rw_repo.get_promo_code("LIMIT1")["used_total"] or 0) == 1


def test_reserve_rowcount_zero_is_explicit_error_not_silent_success(temp_db):
    """rowcount == 0 после UPDATE не должен выглядеть как успех."""
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("ROW0", discount_percent=10, usage_limit_total=1)
    ok, _ = rw_repo.reserve_promo_code("ROW0", 201, "pay-row0-1")
    assert ok is not None
    fail, err = rw_repo.reserve_promo_code("ROW0", 202, "pay-row0-2")
    assert fail is None
    assert err == "total_limit_reached"
    assert int(rw_repo.get_promo_code("ROW0")["used_total"] or 0) == 1


def test_reserve_limit_one_only_one_winner_threaded(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("RACE1", discount_percent=50, usage_limit_total=1)

    def _one(i: int):
        return rw_repo.reserve_promo_code("RACE1", 300 + i, f"pay-race-{i}", applied_amount=50)

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
    assert int(rw_repo.get_promo_code("RACE1")["used_total"] or 0) == 1


def test_per_user_limit_one_blocks_second_reservation_same_user(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("PERUSER", discount_percent=10, usage_limit_per_user=1)
    ok1, err1 = rw_repo.reserve_promo_code("PERUSER", 401, "pay-u1-a")
    ok2, err2 = rw_repo.reserve_promo_code("PERUSER", 401, "pay-u1-b")
    ok_other, err_other = rw_repo.reserve_promo_code("PERUSER", 402, "pay-u2-a")

    assert ok1 is not None and err1 is None
    assert ok2 is None and err2 == "user_limit_reached"
    assert ok_other is not None and err_other is None
    assert int(rw_repo.get_promo_code("PERUSER")["used_total"] or 0) == 2


def test_per_user_limit_threaded_same_user(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("PERUSER2", discount_percent=10, usage_limit_per_user=1)

    def _one(i: int):
        return rw_repo.reserve_promo_code("PERUSER2", 501, f"pay-pu-{i}")

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_one, i) for i in range(6)]
        for fut in as_completed(futs):
            results.append(fut.result())

    wins = [r for r in results if r[0] is not None]
    assert len(wins) == 1, results
    assert all(r[1] == "user_limit_reached" for r in results if r[0] is None)
    assert int(rw_repo.get_promo_code("PERUSER2")["used_total"] or 0) == 1


def test_happy_path_unlimited_and_limit_greater_than_one(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("FREE", discount_percent=10)
    a, ea = rw_repo.reserve_promo_code("FREE", 601, "pay-free-a")
    b, eb = rw_repo.reserve_promo_code("FREE", 602, "pay-free-b")
    assert a and b and ea is None and eb is None
    assert int(rw_repo.get_promo_code("FREE")["used_total"] or 0) == 2

    rw_repo.create_promo_code("TWO", discount_percent=10, usage_limit_total=2)
    c, ec = rw_repo.reserve_promo_code("TWO", 603, "pay-two-a")
    d, ed = rw_repo.reserve_promo_code("TWO", 604, "pay-two-b")
    e, ee = rw_repo.reserve_promo_code("TWO", 605, "pay-two-c")
    assert c and d and ec is None and ed is None
    assert e is None and ee == "total_limit_reached"
    assert int(rw_repo.get_promo_code("TWO")["used_total"] or 0) == 2


def test_release_reservation_restores_slot(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("REL1", discount_percent=10, usage_limit_total=1)
    ok, _ = rw_repo.reserve_promo_code("REL1", 701, "pay-rel")
    assert ok is not None
    assert rw_repo.release_promo_reservation("pay-rel") is True
    assert int(rw_repo.get_promo_code("REL1")["used_total"] or 0) == 0
    # повторный release не уводит used_total в минус
    assert rw_repo.release_promo_reservation("pay-rel") is False
    assert int(rw_repo.get_promo_code("REL1")["used_total"] or 0) == 0
    ok2, err2 = rw_repo.reserve_promo_code("REL1", 702, "pay-rel-2")
    assert ok2 is not None and err2 is None


def test_redeem_after_reserve_does_not_double_increment(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("ONCE", discount_percent=10, usage_limit_total=1)
    rw_repo.reserve_promo_code("ONCE", 801, "pay-once", applied_amount=10)
    redeemed = rw_repo.redeem_promo_code("ONCE", 801, applied_amount=10, order_id="pay-once")
    assert redeemed is not None
    assert int(rw_repo.get_promo_code("ONCE")["used_total"] or 0) == 1
    # идемпотентный повтор
    again = rw_repo.redeem_promo_code("ONCE", 801, applied_amount=10, order_id="pay-once")
    assert again is not None
    assert int(rw_repo.get_promo_code("ONCE")["used_total"] or 0) == 1


def test_redeem_without_prior_reserve_is_atomic(temp_db):
    """Легаси-путь (слот не резервировали на pending) тоже не должен превысить лимит."""
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("LEGACY1", discount_percent=10, usage_limit_total=1)

    def _one(i: int):
        return rw_repo.redeem_promo_code("LEGACY1", 900 + i, applied_amount=10, order_id=f"legacy-{i}")

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(_one, i) for i in range(6)]
        for fut in as_completed(futs):
            results.append(fut.result())

    wins = [r for r in results if r is not None]
    assert len(wins) == 1, results
    assert int(rw_repo.get_promo_code("LEGACY1")["used_total"] or 0) == 1


def test_create_payload_pending_raises_when_promo_slot_gone(temp_db):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("PEND1", discount_percent=10, usage_limit_total=1)
    meta = {"promo_code": "PEND1", "promo_discount": 10, "payment_method": "YooKassa"}
    assert rw_repo.create_payload_pending("p1", 1001, 90.0, meta) is True
    try:
        rw_repo.create_payload_pending("p2", 1002, 90.0, meta)
        raised = False
    except rw_repo.PromoUnavailableError as e:
        raised = True
        assert e.reason == "total_limit_reached"
    assert raised
    assert int(rw_repo.get_promo_code("PEND1")["used_total"] or 0) == 1


def test_create_payment_second_user_gets_promo_unavailable(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=11001, username="promo-a")
    insert_user(database.DB_FILE, telegram_id=11002, username="promo-b")
    token_a = issue_auth_token(11001)
    token_b = issue_auth_token(11002)
    database.update_setting("stars_per_rub", "2")
    rw_repo.create_promo_code("LIMIT1WEB", discount_percent=50, usage_limit_total=1)
    plan_id = _make_plan(database, "PromoRaceHost", price=100.0)

    async def fake_send_invoice_stars(user_id, title, description, payload, amount):
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_send_invoice_stars)
    client = TestClient(handlers.app)

    body = {
        "payment_method": "pay_stars",
        "plan_id": plan_id,
        "action": "new",
        "promo_code": "LIMIT1WEB",
    }
    resp_a = client.post("/api/create-payment", json={**body, "user_id": 11001, "token": token_a})
    resp_b = client.post("/api/create-payment", json={**body, "user_id": 11002, "token": token_b})
    assert resp_a.json().get("ok") is True, resp_a.json()
    data_b = resp_b.json()
    assert data_b.get("ok") is False
    assert data_b.get("error") == rw_repo.promo_error_message("total_limit_reached")
    assert "недействителен" in (data_b.get("error") or "").lower()
    assert int(rw_repo.get_promo_code("LIMIT1WEB")["used_total"] or 0) == 1


def test_stale_reservation_release_by_ttl(temp_db):
    import sqlite3
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo

    rw_repo.create_promo_code("STALE", discount_percent=10, usage_limit_total=1)
    rw_repo.reserve_promo_code("STALE", 1201, "pay-stale")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE promo_code_reservations SET reserved_at = datetime('now', '-25 hours') WHERE payment_id = ?",
            ("pay-stale",),
        )
        conn.commit()
    n = rw_repo.release_stale_promo_reservations()
    assert n >= 1
    assert int(rw_repo.get_promo_code("STALE")["used_total"] or 0) == 0
    ok, err = rw_repo.reserve_promo_code("STALE", 1202, "pay-stale-2")
    assert ok is not None and err is None
