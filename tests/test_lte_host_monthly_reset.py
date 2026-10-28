"""Сброс LTE-трафика у ключей, чей лимит пришёл по наследству от хоста.

Модель сброса не меняется: даты `next_traffic_reset_at` лежат на ключах. Но у ключа
тарифа с `lte_limit_bytes = 0` дата пуста, пока лимит не появился — и
`check_traffic_boost_resets` такие ключи пропускает. Поэтому при смене дефолта хоста
с 0 на >0 дата проставляется идемпотентным backfill'ом по ключам этого хоста.
"""
import asyncio
import sqlite3
import types
from datetime import datetime, timedelta

from conftest import temp_db  # noqa: F401
from test_lte_enforcement import _FakeRemnawave, _insert_key
from test_lte_host_defaults import GB, _make_host, _make_plan, _web_client
from test_monthly_traffic_reset import _FakePanel, _run_reset_worker


def _key_date(database, key_id):
    return database.get_key_by_id(key_id).get("next_traffic_reset_at") or None


def _set_key_date(database, key_id, value):
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("UPDATE vpn_keys SET next_traffic_reset_at = ? WHERE key_id = ?", (value, key_id))


def _set_default_without_backfill(database, host_name, value):
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("UPDATE xui_hosts SET lte_default_limit_bytes = ? WHERE host_name = ?", (value, host_name))


def _inheriting_key(database, host_name="Alpha", *, uuid="u-1", user_id=1, default_gb=0):
    _make_host(database, host_name, default_gb=default_gb)
    plan_id = _make_plan(database, host_name, f"plan-{host_name}", lte_gb=0)
    key_id = _insert_key(database, user_id=user_id, host_name=host_name, user_uuid=uuid, plan_id=plan_id)
    return plan_id, key_id


def _run_enforce_worker(database, fake):
    from test_lte_enforcement import _run_worker

    _run_worker(database, fake)


# --- 1. Ключ тарифа без своего лимита на хосте с дефолтом получает дату сброса ----------


def test_host_backfill_sets_reset_date_for_inheriting_key(temp_db):
    database = temp_db
    _, key_id = _inheriting_key(database)
    _set_default_without_backfill(database, "Alpha", 50 * GB)
    assert _key_date(database, key_id) is None

    assert database.backfill_monthly_traffic_reset_for_host("Alpha") == 1
    date = _key_date(database, key_id)
    assert date and datetime.fromisoformat(date.replace(" ", "T")) > datetime.now()

    assert database.backfill_monthly_traffic_reset_for_host("Alpha") == 0, "идемпотентно"
    assert _key_date(database, key_id) == date


def test_host_backfill_touches_only_keys_of_that_host(temp_db):
    database = temp_db
    _, key_a = _inheriting_key(database, "Alpha", uuid="u-a", user_id=1)
    _, key_b = _inheriting_key(database, "Beta", uuid="u-b", user_id=2, default_gb=10)
    _set_default_without_backfill(database, "Alpha", 50 * GB)
    _set_key_date(database, key_b, None)

    database.backfill_monthly_traffic_reset_for_host("alpha ")
    assert _key_date(database, key_a)
    assert _key_date(database, key_b) is None
    assert database.backfill_monthly_traffic_reset_for_host("") == 0
    assert database.backfill_monthly_traffic_reset_for_host("Нет такого") == 0


def test_host_backfill_keeps_future_date_and_skips_keys_without_limit(temp_db):
    database = temp_db
    _, key_id = _inheriting_key(database)
    future = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S")
    _set_key_date(database, key_id, future)
    _set_default_without_backfill(database, "Alpha", 50 * GB)
    database.backfill_monthly_traffic_reset_for_host("Alpha")
    assert _key_date(database, key_id) == future

    _make_host(database, "Free")
    plan_free = _make_plan(database, "Free", "plan-Free", lte_gb=0)
    free_key = _insert_key(database, user_id=3, host_name="Free", user_uuid="u-free", plan_id=plan_free)
    database.backfill_monthly_traffic_reset_for_host("Free")
    assert _key_date(database, free_key) is None


def test_setting_default_from_zero_triggers_host_backfill(temp_db):
    database = temp_db
    _, key_id = _inheriting_key(database)
    assert _key_date(database, key_id) is None

    assert database.set_host_lte_default_limit_bytes("Alpha", 50 * GB) is True
    date = _key_date(database, key_id)
    assert date

    # >0 -> >0 backfill не нужен и уже стоящую дату не двигает.
    assert database.set_host_lte_default_limit_bytes("Alpha", 80 * GB) is True
    assert _key_date(database, key_id) == date


def test_web_panel_default_change_backfills_host_keys(temp_db):
    database = temp_db
    _, key_id = _inheriting_key(database)
    client = _web_client(database)

    client.post("/update-host-lte-default", data={"host_name": "Alpha", "lte_default_limit_gb": "40"})
    assert _key_date(database, key_id)


def test_telegram_admin_default_change_backfills_host_keys(temp_db, monkeypatch):
    from shop_bot.bot.admin_handlers import get_admin_router

    database = temp_db
    _, key_id = _inheriting_key(database)
    handler = next(
        h.callback
        for h in get_admin_router().message.handlers
        if h.callback.__name__ == "admin_hosts_lte_limit_input"
    )

    answers = []

    class _Message:
        text = "40"
        from_user = types.SimpleNamespace(id=1)

        async def answer(self, text, **kwargs):
            answers.append(text)

    class _State:
        async def get_data(self):
            return {"host_name": "Alpha"}

        async def clear(self):
            pass

    from shop_bot.bot.admin_router import hosts as hosts_module

    async def _no_detail(*args, **kwargs):
        pass

    monkeypatch.setattr(hosts_module, "is_admin", lambda user_id: True, raising=False)
    monkeypatch.setattr(hosts_module, "show_admin_host_detail", _no_detail, raising=False)
    monkeypatch.setattr(hosts_module, "show_admin_hosts_menu", _no_detail, raising=False)
    asyncio.run(handler(_Message(), _State()))

    assert database.get_host_lte_default_limit_bytes("Alpha") == 40 * GB
    assert _key_date(database, key_id)


# --- 2. По наступлении даты сгорает буст и сдвигается baseline --------------------------


def test_due_reset_burns_boost_and_moves_baseline_of_inheriting_key(temp_db):
    database = temp_db
    _, key_id = _inheriting_key(database)
    database.set_host_lte_default_limit_bytes("Alpha", 20 * GB)
    database.update_host_remnawave_settings("Alpha", remnawave_base_url="https://panel.example", remnawave_api_token="tok")
    database.add_key_lte_boost_bytes(key_id, 8 * GB)

    past = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    _set_key_date(database, key_id, past)

    _run_reset_worker(database, _FakePanel())
    lte = database.get_key_lte_state(key_id)
    assert int(lte["lte_baseline_reset_requested"] or 0) == 1
    assert int(lte["lte_boost_bytes"]) == 8 * GB, "буст сгорает на проходе энфорсера, а не здесь"
    new_date = datetime.fromisoformat(_key_date(database, key_id).replace(" ", "T"))
    assert new_date > datetime.now()

    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": 3 * GB}, nodes_by_host={"Alpha": ["node-lte"]})
    _run_enforce_worker(database, fake)
    lte = database.get_key_lte_state(key_id)
    assert int(lte["lte_boost_bytes"]) == 0
    assert int(lte["lte_used_baseline_bytes"]) == 3 * GB
    assert int(lte["lte_baseline_reset_requested"] or 0) == 0


# --- 3. Пакет хоста сгорает при сбросе так же, как пакет тарифа -------------------------


def test_host_package_topup_expires_at_reset_like_plan_package(temp_db):
    database = temp_db
    plan_id, host_key = _inheriting_key(database, uuid="u-host", user_id=1)
    database.set_host_lte_default_limit_bytes("Alpha", 20 * GB)
    own_plan = _make_plan(database, "Alpha", "own", lte_gb=10)
    plan_key = _insert_key(database, user_id=2, host_name="Alpha", user_uuid="u-plan", plan_id=own_plan)
    database.update_host_remnawave_settings("Alpha", remnawave_base_url="https://panel.example", remnawave_api_token="tok")

    host_pkg = database.create_host_traffic_package("Alpha", 5.0, 50.0, pool="lte")
    plan_pkg = database.create_traffic_package(own_plan, 5.0, 50.0, pool="lte")
    assert database.get_traffic_package_by_id(host_pkg)["plan_id"] == 0
    assert database.get_traffic_package_by_id(plan_pkg)["plan_id"] == own_plan
    database.add_key_lte_boost_bytes(host_key, int(5 * GB))
    database.add_key_lte_boost_bytes(plan_key, int(5 * GB))
    assert database.get_key_lte_state(host_key)["lte_boost_bytes"] == int(5 * GB)

    past = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    _set_key_date(database, host_key, past)
    _set_key_date(database, plan_key, past)

    _run_reset_worker(database, _FakePanel())
    fake = _FakeRemnawave(
        {"u-host": 0, "u-plan": 0}, usage_by_node={"node-lte": GB}, nodes_by_host={"Alpha": ["node-lte"]}
    )
    _run_enforce_worker(database, fake)

    for key_id in (host_key, plan_key):
        lte = database.get_key_lte_state(key_id)
        assert int(lte["lte_boost_bytes"]) == 0
        assert int(lte["lte_used_baseline_bytes"]) == GB
    assert database.resolve_lte_limit_bytes(database.get_key_lte_state(host_key), 20 * GB) == 20 * GB


# --- 4. Смена дефолта с >0 на 0 не ломает уже стоящую дату -------------------------------


def test_default_back_to_zero_keeps_existing_reset_date_and_worker_still_rolls_it(temp_db):
    database = temp_db
    _, key_id = _inheriting_key(database)
    database.set_host_lte_default_limit_bytes("Alpha", 50 * GB)
    date = _key_date(database, key_id)
    assert date

    assert database.set_host_lte_default_limit_bytes("Alpha", 0) is True
    assert _key_date(database, key_id) == date
    assert database.backfill_monthly_traffic_reset_for_host("Alpha") == 0
    assert _key_date(database, key_id) == date

    past = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    _set_key_date(database, key_id, past)
    fake = _FakePanel()
    _run_reset_worker(database, fake)

    assert fake.reset_calls == [] and fake.limit_calls == []
    assert datetime.fromisoformat(_key_date(database, key_id).replace(" ", "T")) > datetime.now()
    assert int(database.get_key_lte_state(key_id)["lte_baseline_reset_requested"] or 0) == 0


def test_reset_worker_does_not_query_host_default_per_key(temp_db, monkeypatch):
    database = temp_db
    _, key_id = _inheriting_key(database)
    database.set_host_lte_default_limit_bytes("Alpha", 50 * GB)
    _set_key_date(database, key_id, (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))

    def _boom(*args, **kwargs):
        raise AssertionError("per-key host default lookup")

    monkeypatch.setattr(database, "get_host_lte_default_limit_bytes", _boom)
    from shop_bot.data_manager.db import lte as lte_module

    monkeypatch.setattr(lte_module, "get_host_lte_default_limit_bytes", _boom)
    _run_reset_worker(database, _FakePanel())
    assert int(database.get_key_lte_state(key_id)["lte_baseline_reset_requested"] or 0) == 1
