"""LTE-сквад у ключей с унаследованным лимитом и докупка в Mini App.

Панель Remnawave везде замокана: сквады отслеживает `_FakeRemnawave`, в Mini App
любой обход в `remnawave_api` провалил бы тест.

Кто и когда добавляет LTE-сквад ключу, получившему лимит по наследству:
  * при выдаче/продлении с `plan_id` — `create_or_update_key_on_host` (`want_lte`);
  * у уже выданного ключа — воркер `enforce_dual_traffic_limits`, один раз, когда лимит
    впервые попадает в `key_lte_state` (докупка для этого не нужна);
  * докупка сквад не добавляет, а лишь возвращает его ключу в `disabled_premium_squad`.
"""
import asyncio
import json
import sqlite3
import time

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401
from test_lte_enforcement import _FakeRemnawave, _insert_key, _run_worker
from test_lte_host_defaults import (
    GB,
    _host_with_four_plans,
    _make_plan,
    _run_topup,
    _webapp_client,
)

SQUAD = "squad-Lte"


def _setup(database, *, default_gb, keys=("u-1",)):
    database.create_host("Lte", "https://panel.example", "", "", 0)
    database.add_host_squad("Lte", SQUAD, "lte", "LTE")
    database.update_host_remnawave_settings("Lte", remnawave_base_url="https://panel.example", remnawave_api_token="tok")
    if default_gb:
        database.set_host_lte_default_limit_bytes("Lte", default_gb * GB)
    plan_id = _make_plan(database, "Lte", "plan-Lte", lte_gb=0)
    key_ids = [
        _insert_key(database, user_id=i + 1, host_name="Lte", user_uuid=uuid, plan_id=plan_id)
        for i, uuid in enumerate(keys)
    ]
    return plan_id, key_ids


def _fake(usage_gb=1, uuids=("u-1",)):
    return _FakeRemnawave(
        {u: 0 for u in uuids},
        usage_by_node={"node-lte": int(usage_gb * GB)},
        nodes_by_host={"Lte": ["node-lte"]},
    )


def _state(database, key_id):
    return database.get_key_by_id(key_id)["remote_access_state"]


# --- 2a/2b: сквад добавляет воркер, докупка не нужна -------------------------------------


def test_worker_adds_squad_to_inheriting_key_without_any_topup(temp_db):
    database = temp_db
    _, (key_id,) = _setup(database, default_gb=0)
    fake = _fake()

    _run_worker(database, fake)
    assert fake.added_squads == [] and fake.node_usage_calls == [], "лимита нет: ни учёта, ни сквада"

    database.set_host_lte_default_limit_bytes("Lte", 50 * GB)
    _run_worker(database, fake)
    assert fake.added_squads == [("u-1", SQUAD)]
    assert fake.removed_squads == []
    lte = database.get_key_lte_state(key_id)
    assert lte["lte_limit_bytes"] == 50 * GB and lte["lte_boost_bytes"] == 0, "докупки не было"
    assert _state(database, key_id) == "enabled"

    _run_worker(database, fake)
    assert fake.added_squads == [("u-1", SQUAD)], "один раз, не на каждом проходе"


def test_worker_adds_squad_only_to_keys_without_own_limit_and_with_enabled_access(temp_db):
    database = temp_db
    plan_id, (inheriting, disabled) = _setup(database, default_gb=0, keys=("u-1", "u-2"))
    own_plan = _make_plan(database, "Lte", "own", lte_gb=10)
    own = _insert_key(database, user_id=3, host_name="Lte", user_uuid="u-3", plan_id=own_plan)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("UPDATE vpn_keys SET remote_access_state = 'disabled_main' WHERE key_id = ?", (disabled,))
    database.set_host_lte_default_limit_bytes("Lte", 50 * GB)
    fake = _fake(uuids=("u-1", "u-2", "u-3"))

    _run_worker(database, fake)
    assert [u for u, _ in fake.added_squads] == ["u-1"]
    assert database.get_key_lte_state(own)["lte_limit_bytes"] == 10 * GB


def test_squad_is_not_added_by_topup_to_enabled_key_but_by_next_worker_pass(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    database = temp_db
    _, (key_id,) = _setup(database, default_gb=50)
    pkg = database.create_host_traffic_package("Lte", 5.0, 50.0, pool="lte")
    insert_user(database.DB_FILE, telegram_id=1, username="u1", balance=5000.0)
    panel_calls = []

    async def _record(*args, **kwargs):
        panel_calls.append(args)
        return True

    with monkeypatch.context() as patched:
        patched.setattr(remnawave_api, "add_squad_to_user", _record)
        patched.setattr(remnawave_api, "enable_user", _record)
        _run_topup(database, user_id=1, key_id=key_id, package_id=pkg, payment_id="balance:1:squad")
    assert database.get_key_lte_state(key_id)["lte_boost_bytes"] == 5 * GB
    assert panel_calls == [], "ключ включён: докупка панель не трогает и сквад не добавляет"

    fake = _fake()
    _run_worker(database, fake)
    assert fake.added_squads == [("u-1", SQUAD)]


def test_squad_added_first_then_removed_when_inherited_limit_already_exhausted(temp_db):
    database = temp_db
    _, (key_id,) = _setup(database, default_gb=0)
    database.set_host_lte_default_limit_bytes("Lte", 50 * GB)
    fake = _fake(usage_gb=60)

    _run_worker(database, fake)
    assert fake.added_squads == [("u-1", SQUAD)]
    assert fake.removed_squads == [("u-1", SQUAD)]
    assert _state(database, key_id) == "disabled_premium_squad"


def test_squad_add_failure_is_retried_next_pass_and_limit_not_recorded(temp_db):
    database = temp_db
    _, (key_id,) = _setup(database, default_gb=50)
    fake = _fake()
    results = iter([False, True])
    original = fake.add_squad_to_user

    async def flaky(user_uuid, squad_uuid, *, host_name):
        await original(user_uuid, squad_uuid, host_name=host_name)
        return next(results)

    fake.add_squad_to_user = flaky
    _run_worker(database, fake)
    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 0
    _run_worker(database, fake)
    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 50 * GB
    assert len(fake.added_squads) == 2


# --- 2c: дефолт хоста вернули в 0 --------------------------------------------------------


def test_default_back_to_zero_keeps_squad_and_stops_accounting(temp_db):
    database = temp_db
    _, (key_id,) = _setup(database, default_gb=50)
    fake = _fake()
    _run_worker(database, fake)
    usage_calls = len(fake.node_usage_calls)
    assert fake.added_squads == [("u-1", SQUAD)] and usage_calls == 1

    database.set_host_lte_default_limit_bytes("Lte", 0)
    _run_worker(database, fake)
    assert fake.removed_squads == [], "сквад у ключа остаётся"
    assert fake.added_squads == [("u-1", SQUAD)]
    assert len(fake.node_usage_calls) == usage_calls, "учёт по нодам остановлен"
    assert _state(database, key_id) == "enabled"


def test_default_back_to_zero_returns_squad_to_key_disabled_for_exhausted_limit(temp_db):
    database = temp_db
    _, (key_id,) = _setup(database, default_gb=50)
    fake = _fake(usage_gb=60)
    _run_worker(database, fake)
    assert _state(database, key_id) == "disabled_premium_squad"
    assert fake.removed_squads == [("u-1", SQUAD)]

    database.set_host_lte_default_limit_bytes("Lte", 0)
    _run_worker(database, fake)
    assert _state(database, key_id) == "enabled"
    assert fake.added_squads[-1] == ("u-1", SQUAD), "лимита больше нет: доступ возвращается"


# --- Mini App: /api/lte-packages и /api/create-lte-topup-payment -------------------------


class _AppBot:
    def __init__(self, *args, **kwargs):
        self.sent = []
        self.session = self

    async def close(self):
        return None

    async def send_message(self, *a, **k):
        return _Sent()


class _Sent:
    async def edit_text(self, *a, **k):
        return None

    async def delete(self):
        return None


def _patch_miniapp(monkeypatch):
    from shop_bot.modules import remnawave_api
    from shop_bot.webapp import handlers
    from shop_bot.webapp.web_router import payments_lte

    panel_calls = []

    async def _record(*args, **kwargs):
        panel_calls.append(args)
        return True

    for name in ("add_squad_to_user", "remove_squad_from_user", "enable_user", "disable_user"):
        monkeypatch.setattr(remnawave_api, name, _record)
    for module in (handlers, payments_lte):
        monkeypatch.setattr(module, "Bot", _AppBot, raising=False)
        monkeypatch.setattr(
            module, "get_setting", lambda key, *a, **k: {"telegram_bot_token": "123:TEST"}.get(key, ""), raising=False
        )
    return panel_calls


def _two_keys_of_one_user(database, host_name, plan_id, user_id):
    insert_user(database.DB_FILE, telegram_id=user_id, username=f"u{user_id}", balance=5000.0)
    ids = []
    for n in (1, 2):
        ids.append(
            database.add_new_key(
                user_id,
                host_name,
                f"uuid-{user_id}-{n}",
                f"{user_id}-{n}-lte@bot.local",
                int((time.time() + 30 * 86400) * 1000),
                description=json.dumps({"plan_id": plan_id}),
                subscription_url=f"https://sub.example/{user_id}/{n}",
            )
        )
    return ids


def _topup_via_miniapp(client, token, key_id, package_id):
    return client.post(
        "/api/create-lte-topup-payment",
        json={"token": token, "key_id": key_id, "package_id": package_id, "payment_method": "pay_balance"},
    ).json()


def test_miniapp_host_package_flow_credits_only_selected_key(temp_db, monkeypatch):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    key_a, key_b = _two_keys_of_one_user(database, host_name, plan_ids[1], 98001)
    token = issue_auth_token(98001)
    panel_calls = _patch_miniapp(monkeypatch)
    client = _webapp_client()

    listing = client.get("/api/lte-packages", params={"key_id": key_a, "token": token}).json()
    assert listing["ok"] is True
    assert [p["size_gb"] for p in listing["packages"]] == [500.0, 1500.0, 5000.0, 15000.0, 50000.0]
    host_pkg = next(p for p in database.get_host_lte_packages(host_name) if p["size_gb"] == 500)
    assert host_pkg["plan_id"] == 0
    assert next(p for p in listing["packages"] if p["size_gb"] == 500)["package_id"] == host_pkg["package_id"]

    resp = _topup_via_miniapp(client, token, key_a, host_pkg["package_id"])
    assert resp.get("ok") is True and resp.get("paid") is True, resp
    assert database.get_key_lte_state(key_a)["lte_boost_bytes"] == 500 * GB
    assert database.get_key_lte_state(key_b)["lte_boost_bytes"] == 0
    assert float(database.get_user(98001)["balance"]) == 5000.0 - 3267.0
    assert panel_calls == []


def test_miniapp_own_package_flow_credits_only_selected_key(temp_db, monkeypatch):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    own = database.create_traffic_package(plan_ids[0], 7.0, 70.0, pool="lte")
    host_pkg = database.get_host_lte_packages(host_name)[0]["package_id"]
    key_a, key_b = _two_keys_of_one_user(database, host_name, plan_ids[0], 98002)
    token = issue_auth_token(98002)
    panel_calls = _patch_miniapp(monkeypatch)
    client = _webapp_client()

    listing = client.get("/api/lte-packages", params={"key_id": key_b, "token": token}).json()
    assert [p["package_id"] for p in listing["packages"]] == [own], "собственный набор перекрывает пакеты хоста"

    assert _topup_via_miniapp(client, token, key_b, host_pkg).get("ok") is False
    assert float(database.get_user(98002)["balance"]) == 5000.0

    resp = _topup_via_miniapp(client, token, key_b, own)
    assert resp.get("ok") is True and resp.get("paid") is True, resp
    assert database.get_key_lte_state(key_b)["lte_boost_bytes"] == 7 * GB
    assert database.get_key_lte_state(key_a)["lte_boost_bytes"] == 0
    assert float(database.get_user(98002)["balance"]) == 5000.0 - 70.0
    assert panel_calls == []
