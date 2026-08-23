"""Докупка LTE в WebApp: те же условия и отображение, что в карточке ключа бота.

Безопасность:
- идентичность только из токена;
- цена/размер пакета с сервера;
- пакет обязан быть pool=lte, active и принадлежать тарифу ключа;
- чужой ключ недоступен.
"""
from __future__ import annotations

import json
import time

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

GB = 1024 ** 3
OWNER_ID = 96001
ATTACKER_ID = 96002
HOST = "LteHost"


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _seed_lte_key(database, *, user_id=OWNER_ID, lte_gb=20, boost_gb=0, tag=None, with_squad=True, with_package=True):
    insert_user(database.DB_FILE, telegram_id=user_id, username=f"u{user_id}", balance=500.0)
    database.create_host(HOST, "https://panel.example", "", "", 0)
    database.create_plan(
        HOST, "LTE-план", 1, 100.0,
        traffic_limit_bytes=50 * GB,
        lte_limit_bytes=int(lte_gb * GB),
    )
    plan_id = database.get_plans_for_host(HOST)[0]["plan_id"]
    if with_squad:
        database.add_host_squad(HOST, "squad-lte-1", "lte", "LTE")
    pkg_id = None
    if with_package:
        pkg_id = database.create_traffic_package(plan_id, 5.0, 149.0, pool="lte")
        database.create_traffic_package(plan_id, 10.0, 50.0, pool="main")
    key_id = database.add_new_key(
        user_id,
        HOST,
        f"uuid-{user_id}",
        f"{user_id}-lte@bot.local",
        int((time.time() + 30 * 86400) * 1000),
        description=json.dumps({"source": "trial"} if tag == "trial" else {"plan_id": plan_id}),
        tag=tag,
        subscription_url=f"https://sub.example/{user_id}",
    )
    if boost_gb:
        database.add_key_lte_boost_bytes(key_id, int(boost_gb * GB))
    return key_id, plan_id, pkg_id


def test_lte_card_shows_used_over_limit_and_topup_button(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.webapp.handlers import _get_profile_keys_html, _lte_card_state

    key_id, _, _ = _seed_lte_key(database, boost_gb=5)
    key = database.get_key_by_id(key_id)
    state = _lte_card_state(key)
    assert state["show_lte"] is True
    assert state["show_lte_topup"] is True
    # 20 ГБ тариф + 5 ГБ буст, расход 0
    assert "0 ГБ / 25 ГБ" in state["lte_info"]

    html = _get_profile_keys_html([key])
    assert "💰 LTE:" in html
    assert "0 ГБ / 25 ГБ" in html
    assert "Докупить LTE" in html
    assert f"openLteTopup({key_id})" in html


def test_lte_card_uses_squad_label_instead_of_lte(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.webapp.handlers import _get_profile_keys_html, _lte_card_state

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="u-label", balance=10.0)
    database.create_host(HOST, "https://panel.example", "", "", 0)
    database.create_plan(HOST, "LTE-план", 1, 100.0, traffic_limit_bytes=50 * GB, lte_limit_bytes=20 * GB)
    plan_id = database.get_plans_for_host(HOST)[0]["plan_id"]
    database.add_host_squad(HOST, "squad-lte-1", "lte", "5G Premium")
    key_id = database.add_new_key(
        OWNER_ID, HOST, "uuid-label", "label@bot.local",
        int((time.time() + 30 * 86400) * 1000),
        description=json.dumps({"plan_id": plan_id}),
        subscription_url="https://sub.example/label",
    )
    key = database.get_key_by_id(key_id)
    state = _lte_card_state(key)
    assert state["lte_label"] == "5G Premium"
    html = _get_profile_keys_html([key])
    assert "💰 5G Premium:" in html
    assert "Докупить 5G Premium" in html
    assert "💰 LTE:" not in html
    assert "Докупить LTE" not in html


def test_lte_hidden_without_squad_or_limit(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.webapp.handlers import _get_profile_keys_html, _lte_card_state

    key_id, _, _ = _seed_lte_key(database, with_squad=False)
    key = database.get_key_by_id(key_id)
    assert _lte_card_state(key)["show_lte_topup"] is False
    html = _get_profile_keys_html([key])
    assert "Докупить LTE" not in html
    assert "💰 LTE:" not in html


def test_lte_hidden_for_trial_key(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.webapp.handlers import _lte_card_state

    key_id, _, _ = _seed_lte_key(database, tag="trial")
    key = database.get_key_by_id(key_id)
    assert _lte_card_state(key)["show_lte_topup"] is False


def test_lte_packages_requires_auth_and_ownership(temp_db):
    from shop_bot.data_manager import database

    key_id, _, _ = _seed_lte_key(database)
    insert_user(database.DB_FILE, telegram_id=ATTACKER_ID, username="atk")
    owner_token = issue_auth_token(OWNER_ID)
    attacker_token = issue_auth_token(ATTACKER_ID)
    client = _client()

    assert client.get("/api/lte-packages", params={"key_id": key_id}).status_code == 401

    stolen = client.get("/api/lte-packages", params={"key_id": key_id, "token": attacker_token}).json()
    assert stolen.get("ok") is False

    ok = client.get("/api/lte-packages", params={"key_id": key_id, "token": owner_token}).json()
    assert ok.get("ok") is True
    sizes = [p["size_gb"] for p in ok["packages"]]
    assert sizes == [5.0]
    assert all(p["price"] == 149.0 for p in ok["packages"])


def test_lte_packages_missing_setup(temp_db):
    from shop_bot.data_manager import database

    key_id, _, _ = _seed_lte_key(database, with_package=False)
    token = issue_auth_token(OWNER_ID)
    data = _client().get("/api/lte-packages", params={"key_id": key_id, "token": token}).json()
    assert data.get("ok") is False
    assert "не настроен" in (data.get("error") or "").lower()


def test_create_lte_topup_rejects_main_pool_and_spoofed_user(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    key_id, plan_id, lte_pkg = _seed_lte_key(database)
    main_pkg = database.get_traffic_packages_for_plan(plan_id, pool="main")[0]["package_id"]
    insert_user(database.DB_FILE, telegram_id=ATTACKER_ID, username="atk2", balance=999.0)
    owner_token = issue_auth_token(OWNER_ID)
    attacker_token = issue_auth_token(ATTACKER_ID)
    client = _client()

    called = []

    async def fake_process(bot, meta):
        called.append(meta)
        return True

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)

    bad_pool = client.post(
        "/api/create-lte-topup-payment",
        json={"token": owner_token, "key_id": key_id, "package_id": main_pkg, "payment_method": "pay_balance"},
    ).json()
    assert bad_pool.get("ok") is False
    assert called == []

    stolen = client.post(
        "/api/create-lte-topup-payment",
        json={
            "token": attacker_token,
            "user_id": OWNER_ID,
            "key_id": key_id,
            "package_id": lte_pkg,
            "payment_method": "pay_balance",
        },
    ).json()
    assert stolen.get("ok") is False
    assert called == []
    assert float(database.get_user(ATTACKER_ID)["balance"]) == 999.0


def test_create_lte_topup_balance_uses_db_price_and_bot_action(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    key_id, _, pkg_id = _seed_lte_key(database)
    token = issue_auth_token(OWNER_ID)
    called = []

    async def fake_process(bot, meta):
        called.append(meta)
        return True

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)
    monkeypatch.setattr(handlers, "get_setting", lambda key, *a, **k: {
        "telegram_bot_token": "123:TEST",
    }.get(key, ""))

    resp = _client().post(
        "/api/create-lte-topup-payment",
        json={"token": token, "key_id": key_id, "package_id": pkg_id, "payment_method": "pay_balance"},
    )
    data = resp.json()
    assert data.get("ok") is True and data.get("paid") is True, data
    assert len(called) == 1
    meta = called[0]
    assert meta["action"] == "lte_gb_topup"
    assert meta["key_id"] == key_id
    assert meta["package_id"] == pkg_id
    assert meta["price"] == 149.0
    assert meta["size_gb"] == 5.0
    assert meta["user_id"] == OWNER_ID
    assert float(database.get_user(OWNER_ID)["balance"]) == 351.0


def test_webapp_html_has_lte_packages_step():
    from pathlib import Path

    html = Path("src/shop_bot/webapp/app.html").read_text(encoding="utf-8")
    assert 'id="payment-step-lte-packages"' in html
    assert "openLteTopup" in html
    assert "/api/create-lte-topup-payment" in html
    assert "confirm-promo-wrap" in html
