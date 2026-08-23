"""Энфорсинг LTE-пула в планировщике (причина B диагностики + побочный эффект
двойного подсчёта расхода).

Внешний Remnawave API подменяется: проверяется только логика воркера
`enforce_dual_traffic_limits` и её согласованность с формулой лимита,
которую видит пользователь в карточке ключа.
"""
import asyncio
import json
import sqlite3

from conftest import temp_db  # noqa: F401

GB = 1024 ** 3


class _FakeRemnawave:
    """Заглушка Remnawave.

    `usage_by_uuid` — агрегат пользователя (источник ОСНОВНОГО пула, как `GET /api/users`).
    `usage_by_node` — расход по конкретным нодам (источник LTE-пула). `nodes_by_host`
    описывает, какие ноды отдаёт LTE-сквад каждого хоста.
    """

    def __init__(
        self,
        usage_by_uuid: dict[str, int],
        *,
        usage_by_node: dict[str, int] | None = None,
        nodes_by_host: dict[str, list[str]] | None = None,
        usage_path: str = "squad_scoped",
        fail_hosts: set[str] | None = None,
    ):
        self.usage_by_uuid = usage_by_uuid
        self.usage_by_node = usage_by_node or {}
        self.nodes_by_host = nodes_by_host or {}
        self.usage_path = usage_path
        self.fail_hosts = fail_hosts or set()
        self.usage_calls: list[str] = []
        self.node_usage_calls: list[tuple[str, str]] = []
        self.removed_squads: list[tuple[str, str]] = []
        self.added_squads: list[tuple[str, str]] = []
        self.disabled: list[str] = []
        self.enabled: list[str] = []

    async def get_user_used_traffic(self, user_uuid, *, host_name):
        self.usage_calls.append(str(user_uuid))
        return int(self.usage_by_uuid.get(str(user_uuid), 0))

    async def get_lte_nodes_for_host(self, host_name):
        if host_name in self.fail_hosts:
            raise RuntimeError(f"panel unreachable for {host_name}")
        return [
            {"uuid": uuid, "node_name": f"node-{uuid}"}
            for uuid in self.nodes_by_host.get(host_name, [])
        ]

    async def get_user_node_usage_for_squad(
        self, user_uuid, *, host_name, squad_uuid, node_uuids, start_date, end_date, **kwargs
    ):
        from shop_bot.modules.remnawave_api import NodeUsage

        if host_name in self.fail_hosts:
            raise RuntimeError(f"panel unreachable for {host_name}")
        self.node_usage_calls.append((str(user_uuid), host_name))
        per_node = {
            uuid: int(self.usage_by_node.get(uuid, 0))
            for uuid in node_uuids
            if self.usage_by_node.get(uuid)
        }
        return NodeUsage(per_node, self.usage_path)

    async def remove_squad_from_user(self, user_uuid, squad_uuid, *, host_name):
        self.removed_squads.append((str(user_uuid), str(squad_uuid)))
        return True

    async def add_squad_to_user(self, user_uuid, squad_uuid, *, host_name):
        self.added_squads.append((str(user_uuid), str(squad_uuid)))
        return True

    async def disable_user(self, user_uuid, *, host_name):
        self.disabled.append(str(user_uuid))
        return True

    async def enable_user(self, user_uuid, *, host_name):
        self.enabled.append(str(user_uuid))
        return True


def _setup_lte_host(database, host_name="Lte", *, lte_gb=20, traffic_gb=0):
    database.create_host(host_name, "https://panel.example", "", "", 0)
    database.add_host_squad(host_name, f"squad-{host_name}", "lte", "LTE")
    database.update_host_remnawave_settings(
        host_name, remnawave_base_url="https://panel.example", remnawave_api_token="tok"
    )
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


def _insert_key(database, *, user_id, host_name, user_uuid, plan_id, email=None, state="enabled",
                observed=True):
    """`observed=True` — ключ уже проходил через воркер с нулевым расходом (точка отсчёта 0).

    Так выглядит обычный ключ в работе: первый проход воркера фиксирует baseline сразу
    после выдачи, когда расход ещё нулевой. `observed=False` оставляет точку отсчёта
    неопределённой — состояние ключа, существовавшего до появления учёта по нодам.
    """
    email = email or f"{user_uuid}@example.com"
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, remnawave_user_uuid,
                                  subscription_url, expire_at, created_at, description,
                                  remote_access_state)
            VALUES (?, ?, ?, ?, ?, 'vless://sub', datetime('now', '+30 days'), CURRENT_TIMESTAMP, ?, ?)
            """,
            (
                user_id,
                host_name,
                email,
                email,
                user_uuid,
                json.dumps({"v": 1, "source": "purchase", "plan_id": plan_id}),
                state,
            ),
        )
        key_id = cur.lastrowid
        conn.commit()
    if observed:
        database.commit_key_lte_baseline(key_id, 0, expire_boost=False)
    return key_id


def _run_worker(database, fake):
    from shop_bot.data_manager import scheduler
    from shop_bot.modules import remnawave_api

    originals = {
        name: getattr(remnawave_api, name)
        for name in (
            "get_user_used_traffic",
            "get_lte_nodes_for_host",
            "get_user_node_usage_for_squad",
            "remove_squad_from_user",
            "add_squad_to_user",
            "disable_user",
            "enable_user",
        )
    }
    for name in originals:
        setattr(remnawave_api, name, getattr(fake, name))
    try:
        asyncio.run(scheduler.enforce_dual_traffic_limits(None))
    finally:
        for name, fn in originals.items():
            setattr(remnawave_api, name, fn)


def test_purchased_boost_keeps_access(temp_db):
    """Расход выше лимита тарифа, но докупленный буст покрывает разницу — не отключаем."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=1, host_name="Lte", user_uuid="u-1", plan_id=plan_id)
    database.add_key_lte_boost_bytes(key_id, 10 * GB)  # докупка 10 ГБ на этот ключ

    fake = _FakeRemnawave(
        {"u-1": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, fake)

    assert fake.removed_squads == [], "буст должен учитываться в лимите (20 + 10 > 25)"
    key = database.get_key_by_id(key_id)
    assert (key.get("remote_access_state") or "enabled") == "enabled"


def test_without_boost_access_is_revoked(temp_db):
    """Контроль: без буста тот же расход исчерпывает лимит и LTE-сквад снимается."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=2, host_name="Lte", user_uuid="u-2", plan_id=plan_id)

    fake = _FakeRemnawave(
        {"u-2": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, fake)

    assert fake.removed_squads == [("u-2", "squad-Lte")]
    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"


def test_boost_restores_access_without_resetting_usage(temp_db):
    """После докупки доступ возвращается, но расход НЕ обнуляется.

    Раньше возврат доступа сдвигал baseline, и пользователь получал полный лимит
    тарифа заново поверх купленного пакета (риск 6.1).
    """
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=3, host_name="Lte", user_uuid="u-3", plan_id=plan_id)

    fake = _FakeRemnawave(
        {"u-3": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, fake)
    assert fake.removed_squads, "предусловие: лимит исчерпан"

    database.add_key_lte_boost_bytes(key_id, 10 * GB)
    _run_worker(database, fake)

    assert fake.added_squads == [("u-3", "squad-Lte")]
    state = database.get_key_lte_state(key_id)
    assert state["lte_used_bytes"] == 25 * GB, "расход сохраняется, а не обнуляется"
    assert state["lte_boost_bytes"] == 10 * GB
    # Остаток строго аддитивен: лимит 30 ГБ при расходе 25 ГБ.
    assert database.resolve_lte_limit_bytes(state, 20 * GB) == 30 * GB


def test_plan_limit_increase_is_picked_up(temp_db):
    """Повышение plans.lte_limit_bytes админом долетает до существующего пользователя."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=4, host_name="Lte", user_uuid="u-4", plan_id=plan_id)

    fake = _FakeRemnawave(
        {"u-4": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, fake)
    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"

    plan = database.get_plan_by_id(plan_id)
    database.update_plan(
        plan_id, plan["plan_name"], plan["months"], plan["price"], lte_limit_bytes=50 * GB
    )
    _run_worker(database, fake)

    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 50 * GB
    assert database.get_key_by_id(key_id)["remote_access_state"] == "enabled"


def test_keys_of_same_user_have_independent_pools(temp_db):
    """Ключи одного владельца ведут РАЗДЕЛЬНЫЕ LTE-пулы: расход одного не влияет на другой,
    и докупка на одном ключе не расходуется на другом."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    database.create_host("Lte2", "https://panel.example", "", "", 0)
    database.update_host_remnawave_settings(
        "Lte2", remnawave_base_url="https://panel.example", remnawave_api_token="tok"
    )
    database.add_host_squad("Lte2", "squad-Lte2", "lte", "LTE")
    key_a = _insert_key(database, user_id=5, host_name="Lte", user_uuid="u-5a", plan_id=plan_id, email="a@e.com")
    key_b = _insert_key(database, user_id=5, host_name="Lte2", user_uuid="u-5b", plan_id=plan_id, email="b@e.com")

    fake = _FakeRemnawave(
        {"u-5a": 18 * GB, "u-5b": 3 * GB},
        usage_by_node={"node-a": 18 * GB, "node-b": 3 * GB},
        nodes_by_host={"Lte": ["node-a"], "Lte2": ["node-b"]},
    )
    _run_worker(database, fake)

    assert database.get_key_lte_state(key_a)["lte_used_bytes"] == 18 * GB
    assert database.get_key_lte_state(key_b)["lte_used_bytes"] == 3 * GB
    assert fake.removed_squads == [], "ни один ключ не превысил свой лимит в 20 ГБ"

    # Докупка адресована ключу A и не должна увеличить лимит ключа B.
    database.add_key_lte_boost_bytes(key_a, 10 * GB)
    assert database.get_key_lte_state(key_a)["lte_boost_bytes"] == 10 * GB
    assert database.get_key_lte_state(key_b)["lte_boost_bytes"] == 0


def test_key_exhausts_only_its_own_pool(temp_db):
    """Превышение лимита на одном ключе отключает premium-ноды только у него."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    database.create_host("Lte2", "https://panel.example", "", "", 0)
    database.update_host_remnawave_settings(
        "Lte2", remnawave_base_url="https://panel.example", remnawave_api_token="tok"
    )
    database.add_host_squad("Lte2", "squad-Lte2", "lte", "LTE")
    key_a = _insert_key(database, user_id=15, host_name="Lte", user_uuid="u-15a", plan_id=plan_id, email="a15@e.com")
    key_b = _insert_key(database, user_id=15, host_name="Lte2", user_uuid="u-15b", plan_id=plan_id, email="b15@e.com")

    fake = _FakeRemnawave(
        {"u-15a": 25 * GB, "u-15b": 1 * GB},
        usage_by_node={"node-a": 25 * GB, "node-b": 1 * GB},
        nodes_by_host={"Lte": ["node-a"], "Lte2": ["node-b"]},
    )
    _run_worker(database, fake)

    assert fake.removed_squads == [("u-15a", "squad-Lte")]
    assert database.get_key_by_id(key_a)["remote_access_state"] == "disabled_premium_squad"
    assert (database.get_key_by_id(key_b).get("remote_access_state") or "enabled") == "enabled"


def test_base_only_host_usage_not_billed_to_lte(temp_db):
    """Расход по хосту без LTE-сквада не попадает в LTE-пул."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    database.create_host("BaseOnly", "https://panel.example", "", "", 0)
    database.add_host_squad("BaseOnly", "squad-base", "base", "Base")
    key_id = _insert_key(database, user_id=6, host_name="BaseOnly", user_uuid="u-6b", plan_id=plan_id)

    fake = _FakeRemnawave(
        {"u-6b": 100 * GB}, usage_by_node={"node-base": 100 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, fake)

    assert database.get_key_lte_state(key_id)["lte_used_bytes"] == 0
    assert fake.removed_squads == []
    assert fake.node_usage_calls == []


def test_unlimited_lte_is_not_accounted(temp_db):
    """Безлимитный LTE (лимит 0) не ходит в статистику нод и не пишет расход, даже если сквад есть."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=0)
    key_id = _insert_key(database, user_id=61, host_name="Lte", user_uuid="u-61", plan_id=plan_id, observed=False)

    fake = _FakeRemnawave(
        {"u-61": 80 * GB},
        usage_by_node={"node-lte": 80 * GB},
        nodes_by_host={"Lte": ["node-lte"]},
    )
    _run_worker(database, fake)

    assert fake.node_usage_calls == []
    assert database.get_node_usage_for_key(key_id) == []
    assert fake.removed_squads == []
    assert (database.get_key_by_id(key_id).get("remote_access_state") or "enabled") == "enabled"


def test_should_account_lte_requires_limit_and_squad(temp_db):
    database = temp_db
    limited = _setup_lte_host(database, host_name="AccLte", lte_gb=20)
    unlimited = _setup_lte_host(database, host_name="AccUnlim", lte_gb=0)
    database.create_host("NoSquad", "https://panel.example", "", "", 0)
    database.create_plan("NoSquad", "plan-NoSquad", 1, 100.0, lte_limit_bytes=20 * GB)
    plans_ns = {p["plan_name"]: p["plan_id"] for p in database.get_plans_for_host("NoSquad")}

    assert database.should_account_lte_traffic(database.get_plan_by_id(limited), "AccLte")
    assert not database.should_account_lte_traffic(database.get_plan_by_id(unlimited), "AccUnlim")
    assert not database.should_account_lte_traffic(database.get_plan_by_id(plans_ns["plan-NoSquad"]), "NoSquad")
    assert not database.should_account_lte_traffic(None, "AccLte")


def test_existing_key_gets_baseline_initialized(temp_db):
    """Ключ, существовавший до появления учёта по нодам (точка отсчёта не определена), не
    отключается сразу из-за накопленной панелью истории — первый проход задаёт baseline."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(
        database, user_id=7, host_name="Lte", user_uuid="u-7", plan_id=plan_id, observed=False
    )

    fake = _FakeRemnawave(
        {"u-7": 900 * GB}, usage_by_node={"node-lte": 900 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )  # исторический расход панели
    _run_worker(database, fake)

    state = database.get_key_lte_state(key_id)
    assert state["lte_used_baseline_bytes"] == 900 * GB
    assert state["lte_used_bytes"] == 0
    assert state["lte_baseline_initialized_at"]
    assert database.get_key_by_id(key_id)["remote_access_state"] == "enabled"
    assert fake.removed_squads == []


def test_node_usage_snapshots_are_written(temp_db):
    """Расход пишется построчно по нодам, с именем ноды и периодом ключа."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=100)
    key_id = _insert_key(database, user_id=8, host_name="Lte", user_uuid="u-8", plan_id=plan_id)

    fake = _FakeRemnawave(
        {"u-8": 9 * GB},
        usage_by_node={"node-a": 6 * GB, "node-b": 3 * GB},
        nodes_by_host={"Lte": ["node-a", "node-b"]},
    )
    _run_worker(database, fake)

    rows = database.get_node_usage_for_key(key_id)
    assert {(r["node_uuid"], r["used_bytes"], r["node_name"]) for r in rows} == {
        ("node-a", 6 * GB, "node-node-a"),
        ("node-b", 3 * GB, "node-node-b"),
    }
    assert {r["period_start"] for r in rows} == {database.resolve_key_period_start(database.get_key_by_id(key_id))}
    assert database.get_key_lte_state(key_id)["lte_used_bytes"] == 9 * GB


def test_panel_failure_skips_key_without_zeroing(temp_db):
    """Сбой панели: ни нулевого снапшота, ни обнуления расхода, ни исчерпания лимита."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=9, host_name="Lte", user_uuid="u-9", plan_id=plan_id)

    # Успешный проход: 5 ГБ зафиксированы.
    ok_fake = _FakeRemnawave(
        {"u-9": 5 * GB}, usage_by_node={"node-lte": 5 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, ok_fake)
    assert database.get_key_lte_state(key_id)["lte_used_bytes"] == 5 * GB

    # Панель недоступна.
    failing = _FakeRemnawave(
        {"u-9": 5 * GB},
        usage_by_node={"node-lte": 5 * GB},
        nodes_by_host={"Lte": ["node-lte"]},
        fail_hosts={"Lte"},
    )
    _run_worker(database, failing)

    assert database.get_key_lte_state(key_id)["lte_used_bytes"] == 5 * GB, "расход не должен обнуляться"
    rows = database.get_node_usage_for_key(key_id)
    assert [r["used_bytes"] for r in rows] == [5 * GB], "нулевой снапшот писаться не должен"
    assert failing.removed_squads == [], "исчерпание лимита по пустым данным не засчитывается"
    assert (database.get_key_by_id(key_id).get("remote_access_state") or "enabled") == "enabled"


def test_incomplete_data_does_not_restore_access(temp_db):
    """При недостоверных данных доступ не восстанавливается (иначе — флаппинг)."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=10, host_name="Lte", user_uuid="u-10", plan_id=plan_id)

    over = _FakeRemnawave(
        {"u-10": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    _run_worker(database, over)
    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"

    failing = _FakeRemnawave(
        {"u-10": 25 * GB},
        usage_by_node={"node-lte": 25 * GB},
        nodes_by_host={"Lte": ["node-lte"]},
        fail_hosts={"Lte"},
    )
    _run_worker(database, failing)

    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"
    assert failing.added_squads == []


def test_per_node_sum_matches_previous_aggregate(temp_db):
    """Санити-регрессия перехода: на хосте с единственным LTE-сквадом без пересечений
    сумма по нодам совпадает с тем, что раньше давал агрегат пользователя."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=100)
    key_id = _insert_key(database, user_id=11, host_name="Lte", user_uuid="u-11", plan_id=plan_id)

    aggregate = 17 * GB
    fake = _FakeRemnawave(
        {"u-11": aggregate},
        usage_by_node={"node-a": 10 * GB, "node-b": 7 * GB},
        nodes_by_host={"Lte": ["node-a", "node-b"]},
    )
    _run_worker(database, fake)

    assert database.get_key_lte_state(key_id)["lte_used_bytes"] == aggregate


def test_exhausted_limit_really_patches_squad_out(temp_db):
    """Сквозная регрессия: при исчерпании лимита LTE-сквад реально убирается из подписки.

    Здесь НЕ подменяется remove_squad_from_user — работает настоящая функция, подменён
    только транспорт. Раньше тесты стабили её целиком, поэтому ложный успех (сравнение
    строки с объектами в activeInternalSquads) оставался незамеченным.
    """
    import asyncio

    from shop_bot.data_manager import scheduler
    from shop_bot.modules import remnawave_api

    database = temp_db
    base_squad, lte_squad = "squad-base-uuid", "squad-Lte"
    plan_id = _setup_lte_host(database, lte_gb=20)
    database.add_host_squad("Lte", base_squad, "base", "BASE")
    key_id = _insert_key(database, user_id=12, host_name="Lte", user_uuid="77", plan_id=plan_id)

    calls: list[tuple] = []

    async def transport(host_name, method, path, *, json_payload=None, params=None,
                        expected_status=(200,)):
        calls.append((method, path, json_payload))
        return type("R", (), {
            "status_code": 200,
            "text": "{}",
            "json": lambda self=None: {"response": {
                "id": 77,
                "activeInternalSquads": [
                    {"uuid": base_squad, "name": "BASE"},
                    {"uuid": lte_squad, "name": "LTE"},
                ],
            }},
        })()

    fake = _FakeRemnawave(
        {"77": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    originals = {
        name: getattr(remnawave_api, name)
        for name in ("get_user_used_traffic", "get_lte_nodes_for_host",
                     "get_user_node_usage_for_squad", "_request_for_host")
    }
    for name in ("get_user_used_traffic", "get_lte_nodes_for_host", "get_user_node_usage_for_squad"):
        setattr(remnawave_api, name, getattr(fake, name))
    remnawave_api._request_for_host = transport
    try:
        asyncio.run(scheduler.enforce_dual_traffic_limits(None))
    finally:
        for name, fn in originals.items():
            setattr(remnawave_api, name, fn)

    patches = [c for c in calls if c[0] == "PATCH"]
    assert patches, "LTE-сквад должен быть снят через PATCH /api/users"
    assert patches[0][2]["activeInternalSquads"] == [base_squad], "base-сквад обязан остаться"
    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"


def test_stale_disabled_state_is_reconciled_with_panel(temp_db):
    """Если в БД уже стоит disabled_premium_squad, а в подписке сквад остался (следствие
    прежнего ложного успеха), воркер обязан досняться, а не пропускать ключ навсегда."""
    import asyncio

    from shop_bot.data_manager import scheduler
    from shop_bot.modules import remnawave_api

    database = temp_db
    base_squad, lte_squad = "squad-base-uuid", "squad-Lte"
    plan_id = _setup_lte_host(database, lte_gb=20)
    database.add_host_squad("Lte", base_squad, "base", "BASE")
    key_id = _insert_key(
        database, user_id=13, host_name="Lte", user_uuid="88", plan_id=plan_id,
        state="disabled_premium_squad",
    )

    calls: list[tuple] = []

    async def transport(host_name, method, path, *, json_payload=None, params=None,
                        expected_status=(200,)):
        calls.append((method, path, json_payload))
        return type("R", (), {
            "status_code": 200, "text": "{}",
            "json": lambda self=None: {"response": {
                "id": 88,
                "activeInternalSquads": [
                    {"uuid": base_squad, "name": "BASE"},
                    {"uuid": lte_squad, "name": "LTE"},   # сквад всё ещё в подписке
                ],
            }},
        })()

    fake = _FakeRemnawave(
        {"88": 25 * GB}, usage_by_node={"node-lte": 25 * GB}, nodes_by_host={"Lte": ["node-lte"]}
    )
    originals = {
        name: getattr(remnawave_api, name)
        for name in ("get_user_used_traffic", "get_lte_nodes_for_host",
                     "get_user_node_usage_for_squad", "_request_for_host")
    }
    for name in ("get_user_used_traffic", "get_lte_nodes_for_host", "get_user_node_usage_for_squad"):
        setattr(remnawave_api, name, getattr(fake, name))
    remnawave_api._request_for_host = transport
    try:
        asyncio.run(scheduler.enforce_dual_traffic_limits(None))
    finally:
        for name, fn in originals.items():
            setattr(remnawave_api, name, fn)

    patches = [c for c in calls if c[0] == "PATCH"]
    assert patches, "расхождение БД и панели должно чиниться повторным снятием"
    assert patches[0][2]["activeInternalSquads"] == [base_squad]
    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"
