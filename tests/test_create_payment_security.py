"""PR-0: безопасность /api/create-payment (extend / new / gift).

Раньше эндпоинт не сверял владельца ключа, брал host_name из запроса, искал
тариф через get_plan_by_id (без проверки хоста и активности) и доверял
клиентскому tier_price. Здесь фиксируется, что хост, ключ и тариф определяются
только по серверным данным, а выдача при продлении работает с хостом ключа.
"""
from __future__ import annotations

import asyncio
import sqlite3

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

OWNER, ATTACKER = 81001, 81002


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _insert_key(db_path, *, user_id: int, host_name: str | None, email: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at)
            VALUES (?, ?, ?, ?, 'vless://sub', datetime('now', '+10 days'), CURRENT_TIMESTAMP)
            """,
            (user_id, host_name, email, email),
        )
        conn.commit()
        return cur.lastrowid


def _host_with_plan(database, name: str, *, price: float = 100.0, months: int = 1) -> int:
    database.create_host(name, "https://panel.test", "user", "pass", 1)
    database.create_plan(name, f"{months} мес", months, price)
    return database.get_plans_for_host(name)[-1]["plan_id"]


class _Env:
    """Общая обвязка: два пользователя, два хоста, перехват выдачи."""

    def __init__(self, database, monkeypatch):
        from shop_bot.webapp import handlers

        self.database = database
        insert_user(database.DB_FILE, telegram_id=OWNER, username="owner", balance=1000.0)
        insert_user(database.DB_FILE, telegram_id=ATTACKER, username="attacker", balance=1000.0)
        self.owner_token = issue_auth_token(OWNER)
        self.attacker_token = issue_auth_token(ATTACKER)
        self.plan_a = _host_with_plan(database, "HostA", price=100.0)
        self.plan_b = _host_with_plan(database, "HostB", price=10.0)
        self.calls: list[dict] = []

        async def fake_process(bot, meta):
            self.calls.append(dict(meta))
            return True

        monkeypatch.setattr(handlers, "process_successful_payment", fake_process)
        self.client = _client()

    def pay(self, token: str, **body):
        payload = {"token": token, "payment_method": "pay_balance", "tier_price": 0}
        payload.update(body)
        return self.client.post("/api/create-payment", json=payload).json()

    def balance(self, user_id: int) -> float:
        return float(self.database.get_user(user_id)["balance"])


def test_extend_foreign_key_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    data = env.pay(env.attacker_token, action="extend", key_id=key_id, host_name="HostA", plan_id=env.plan_a)

    assert data.get("ok") is False
    assert data.get("error") == "Ключ не найден"
    assert env.calls == []
    assert env.balance(ATTACKER) == 1000.0


def test_extend_foreign_key_with_other_host_is_rejected(temp_db, monkeypatch):
    """Сценарий из аудита: чужой ключ + host_name другого хоста + дешёвый тариф."""
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    data = env.pay(env.attacker_token, action="extend", key_id=key_id, host_name="HostB", plan_id=env.plan_b)

    assert data.get("ok") is False
    assert data.get("error") == "Ключ не найден"
    assert env.calls == []
    assert env.balance(ATTACKER) == 1000.0


def test_extend_missing_key_gives_same_error_as_foreign_key(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    for key_id in (None, 0, -5, 999999):
        data = env.pay(env.attacker_token, action="extend", key_id=key_id, host_name="HostA", plan_id=env.plan_a)
        assert data.get("ok") is False
        assert data.get("error") == "Ключ не найден"
    assert env.calls == []


def test_extend_by_owner_uses_host_of_key_not_request(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    data = env.pay(env.owner_token, action="extend", key_id=key_id, host_name="HostB", plan_id=env.plan_a)

    assert data.get("ok") is True, data
    assert len(env.calls) == 1
    meta = env.calls[0]
    assert meta["host_name"] == "HostA"
    assert meta["key_id"] == key_id
    assert meta["plan_id"] == env.plan_a
    assert meta["price"] == 100.0
    assert env.balance(OWNER) == 900.0


def test_extend_by_owner_without_host_name_in_request(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    data = env.pay(env.owner_token, action="extend", key_id=key_id, plan_id=env.plan_a)

    assert data.get("ok") is True, data
    assert env.calls[0]["host_name"] == "HostA"


def test_extend_with_plan_of_another_host_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    data = env.pay(env.owner_token, action="extend", key_id=key_id, host_name="HostB", plan_id=env.plan_b)

    assert data.get("ok") is False
    assert data.get("error") == "Тариф не найден"
    assert env.calls == []
    assert env.balance(OWNER) == 1000.0


def test_inactive_plan_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute("UPDATE plans SET is_active = 0 WHERE plan_id = ?", (env.plan_a,))
        conn.commit()

    extend = env.pay(env.owner_token, action="extend", key_id=key_id, plan_id=env.plan_a)
    new = env.pay(env.owner_token, action="new", host_name="HostA", plan_id=env.plan_a)

    assert extend.get("ok") is False and extend.get("error") == "Тариф не найден"
    assert new.get("ok") is False and new.get("error") == "Тариф не найден"
    assert env.calls == []


def test_unknown_plan_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    data = env.pay(env.owner_token, action="new", host_name="HostA", plan_id=987654)

    assert data.get("ok") is False
    assert data.get("error") == "Тариф не найден"


def test_new_with_plan_of_another_host_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    data = env.pay(env.owner_token, action="new", host_name="HostA", plan_id=env.plan_b)

    assert data.get("ok") is False
    assert data.get("error") == "Тариф не найден"
    assert env.calls == []


def test_new_and_gift_with_nonexistent_host_are_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    for action in ("new", "gift"):
        for host in ("NoSuchHost", "", None):
            data = env.pay(env.owner_token, action=action, host_name=host, plan_id=env.plan_a)
            assert data.get("ok") is False, (action, host, data)
            assert data.get("error") == "Сервер не найден"
    assert env.calls == []


def test_new_and_gift_on_host_flagged_inactive_keep_selling(temp_db, monkeypatch):
    """PR-0 не меняет правила продаж: xui_hosts.is_active раньше не влиял на покупку."""
    env = _Env(temp_db, monkeypatch)
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute("UPDATE xui_hosts SET is_active = 0 WHERE host_name = 'HostA'")
        conn.commit()

    for action in ("new", "gift"):
        data = env.pay(env.owner_token, action=action, host_name="HostA", plan_id=env.plan_a)
        assert data.get("ok") is True, (action, data)
    assert [c["host_name"] for c in env.calls] == ["HostA", "HostA"]


def test_extend_key_without_host_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    for host in (None, "", "   "):
        key_id = _insert_key(
            temp_db.DB_FILE, user_id=OWNER, host_name=host, email=f"nohost-{abs(hash(host))}@bot.local"
        )
        data = env.pay(env.owner_token, action="extend", key_id=key_id, host_name="HostA", plan_id=env.plan_a)
        assert data.get("ok") is False, (host, data)
        assert "не указан сервер" in (data.get("error") or "")
    assert env.calls == []
    assert env.balance(OWNER) == 1000.0


def test_unknown_action_is_rejected(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    for action in ("top_up", "lte_gb_topup", "", "NEW; DROP"):
        data = env.pay(env.owner_token, action=action, host_name="HostA", plan_id=env.plan_a)
        assert data.get("ok") is False, (action, data)
    assert env.calls == []


def test_key_id_is_dropped_for_new_and_gift(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    foreign_key = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    new = env.pay(env.attacker_token, action="new", host_name="HostA", plan_id=env.plan_a, key_id=foreign_key)
    gift = env.pay(env.attacker_token, action="gift", host_name="HostA", plan_id=env.plan_a, key_id=foreign_key)

    assert new.get("ok") is True and gift.get("ok") is True, (new, gift)
    assert [c["action"] for c in env.calls] == ["new", "gift"]
    assert [c["key_id"] for c in env.calls] == [None, None]


def test_host_name_in_metadata_is_canonical_for_new(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    data = env.pay(env.owner_token, action="new", host_name="  HostA ", plan_id=env.plan_a)

    assert data.get("ok") is True, data
    assert env.calls[0]["host_name"] == "HostA"


def test_inflated_tier_price_does_not_change_amount(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")

    data = env.pay(
        env.owner_token, action="extend", key_id=key_id, plan_id=env.plan_a,
        tier_price=5000, tier_device_count=50,
    )

    assert data.get("ok") is True, data
    assert env.calls[0]["price"] == 100.0
    assert env.calls[0]["tier_device_count"] is None
    assert env.balance(OWNER) == 900.0


def test_negative_and_garbage_tier_price_do_not_change_amount(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    for tier_price in (-100, -0.01, 0):
        env.calls.clear()
        data = env.pay(
            env.owner_token, action="new", host_name="HostA", plan_id=env.plan_a,
            tier_price=tier_price, tier_device_count=-3,
        )
        assert data.get("ok") is True, (tier_price, data)
        assert env.calls[0]["price"] == 100.0
    assert env.balance(OWNER) == 700.0

    garbage = env.client.post("/api/create-payment", json={
        "token": env.owner_token, "payment_method": "pay_balance", "action": "new",
        "host_name": "HostA", "plan_id": env.plan_a, "tier_price": "NaN-ish",
    })
    assert garbage.status_code == 422
    assert env.balance(OWNER) == 700.0


def _make_tiers_host(database, monkeypatch, *, lock_extend: bool):
    """В схеме xui_hosts нет колонок device_mode/tier_lock_extend, поэтому режим
    ступеней задаём подменой get_host (так же его читает payments_create)."""
    from shop_bot.webapp.web_router import payments_create

    real_get_host = payments_create.get_host

    def fake_get_host(name):
        row = real_get_host(name)
        if row and row.get("host_name") == "HostA":
            row = {**row, "device_mode": "tiers", "tier_lock_extend": 1 if lock_extend else 0}
        return row

    monkeypatch.setattr(payments_create, "get_host", fake_get_host)
    database.update_setting("base_device_HostA", "1")
    monkeypatch.setattr(
        payments_create,
        "get_device_tiers",
        lambda host: [{"tier_id": 1, "device_count": 3, "price": 20.0}],
    )


def test_tier_surcharge_is_computed_on_server_for_tiers_host(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)
    _make_tiers_host(temp_db, monkeypatch, lock_extend=False)

    cheap = env.pay(
        env.owner_token, action="new", host_name="HostA", plan_id=env.plan_a,
        tier_device_count=3, tier_price=0.01,
    )

    assert cheap.get("ok") is True, cheap
    # (3 - 1) устройств * 20 ₽ * 1 мес. + тариф 100 ₽; клиентские 0.01 ₽ не учитываются.
    assert env.calls[0]["price"] == 140.0
    assert env.calls[0]["tier_device_count"] == 3

    env.calls.clear()
    unknown = env.pay(
        env.owner_token, action="new", host_name="HostA", plan_id=env.plan_a,
        tier_device_count=99, tier_price=9999,
    )
    assert unknown.get("ok") is True, unknown
    assert env.calls[0]["price"] == 100.0
    assert env.calls[0]["tier_device_count"] is None


def test_tier_lock_extend_uses_panel_device_limit_not_client(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    env = _Env(temp_db, monkeypatch)
    _make_tiers_host(temp_db, monkeypatch, lock_extend=True)
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name="HostA", email="owner-a@bot.local")
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute("UPDATE vpn_keys SET remnawave_user_uuid = 'panel-uuid' WHERE key_id = ?", (key_id,))
        conn.commit()

    async def fake_get_user(user_uuid, host_name=None):
        assert host_name == "HostA"
        return {"hwidDeviceLimit": 3}

    monkeypatch.setattr(remnawave_api, "get_user_by_uuid", fake_get_user)

    data = env.pay(
        env.owner_token, action="extend", key_id=key_id, plan_id=env.plan_a,
        tier_device_count=1, tier_price=0,
    )

    assert data.get("ok") is True, data
    assert env.calls[0]["price"] == 140.0
    assert env.calls[0]["tier_device_count"] == 3


def test_gift_by_any_user_still_works_on_active_host(temp_db, monkeypatch):
    env = _Env(temp_db, monkeypatch)

    data = env.pay(env.attacker_token, action="gift", host_name="HostB", plan_id=env.plan_b)

    assert data.get("ok") is True, data
    assert env.calls[0]["host_name"] == "HostB"
    assert env.calls[0]["key_id"] is None
    assert env.balance(ATTACKER) == 990.0


def _run_extend_fulfillment(temp_db, monkeypatch, *, key_host, meta_host):
    from shop_bot.bot.user_router import fulfillment
    from shop_bot.modules import remnawave_api

    insert_user(temp_db.DB_FILE, telegram_id=OWNER, username="owner")
    key_id = _insert_key(temp_db.DB_FILE, user_id=OWNER, host_name=key_host, email="owner-a@bot.local")
    plan_a = _host_with_plan(temp_db, "HostA", price=100.0)
    _host_with_plan(temp_db, "HostB", price=10.0)

    seen: list[dict] = []

    async def fake_create(*args, **kwargs):
        seen.append(dict(kwargs))
        return None

    monkeypatch.setattr(remnawave_api, "create_or_update_key_on_host", fake_create)

    class _Bot:
        id = 1

        def __init__(self, *a, **kw):
            self.session = self

        async def send_message(self, *a, **kw):
            return None

        async def delete_message(self, *a, **kw):
            return None

        async def close(self):
            return None

    async def abort_stub(*a, **kw):
        return None

    monkeypatch.setattr(fulfillment, "_abort_key_fulfillment", abort_stub)

    meta = {
        "user_id": OWNER, "months": 1, "price": 100.0, "action": "extend",
        "key_id": key_id, "host_name": meta_host, "plan_id": plan_a,
        "payment_method": "Balance", "payment_id": "pr0-fulfil-1",
    }
    result = asyncio.run(fulfillment.process_successful_payment(_Bot(), meta))
    assert result is False  # заглушка панели вернула None, выдача отменена
    return key_id, seen


def test_fulfillment_extend_uses_host_of_key_when_metadata_differs(temp_db, monkeypatch, caplog):
    """process_successful_payment: хост из metadata (в т.ч. от старых pending-платежей)
    не должен перенаправлять продление на другой хост, и это попадает в лог."""
    with caplog.at_level("WARNING"):
        key_id, seen = _run_extend_fulfillment(temp_db, monkeypatch, key_host="HostA", meta_host="HostB")

    assert len(seen) == 1
    assert seen[0]["host_name"] == "HostA"
    assert seen[0]["email"] == "owner-a@bot.local"
    warnings = [r.getMessage() for r in caplog.records if "не совпадает с хостом ключа" in r.getMessage()]
    assert len(warnings) == 1
    assert "payment_id=pr0-fulfil-1" in warnings[0]
    assert f"key_id={key_id}" in warnings[0]
    assert "metadata_host='HostB'" in warnings[0] and "key_host='HostA'" in warnings[0]


def test_fulfillment_extend_matching_host_does_not_warn(temp_db, monkeypatch, caplog):
    with caplog.at_level("WARNING"):
        _, seen = _run_extend_fulfillment(temp_db, monkeypatch, key_host="HostA", meta_host="HostA")

    assert seen[0]["host_name"] == "HostA"
    assert not [r for r in caplog.records if "host_name в metadata" in r.getMessage() or "нет host_name" in r.getMessage()]


def test_fulfillment_extend_falls_back_to_metadata_host_and_warns(temp_db, monkeypatch, caplog):
    with caplog.at_level("WARNING"):
        key_id, seen = _run_extend_fulfillment(temp_db, monkeypatch, key_host="", meta_host="HostA")

    assert seen[0]["host_name"] == "HostA"
    warnings = [r.getMessage() for r in caplog.records if "у ключа нет host_name" in r.getMessage()]
    assert len(warnings) == 1
    assert "payment_id=pr0-fulfil-1" in warnings[0] and f"key_id={key_id}" in warnings[0]
