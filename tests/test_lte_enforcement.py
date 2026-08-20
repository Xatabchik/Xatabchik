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
    """Заглушка Remnawave: расход задаётся на Remnawave-пользователя (как в панели)."""

    def __init__(self, usage_by_uuid: dict[str, int]):
        self.usage_by_uuid = usage_by_uuid
        self.usage_calls: list[str] = []
        self.removed_squads: list[tuple[str, str]] = []
        self.added_squads: list[tuple[str, str]] = []
        self.disabled: list[str] = []
        self.enabled: list[str] = []

    async def get_user_used_traffic(self, user_uuid, *, host_name):
        self.usage_calls.append(str(user_uuid))
        return int(self.usage_by_uuid.get(str(user_uuid), 0))

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


def _insert_key(database, *, user_id, host_name, user_uuid, plan_id, email=None, state="enabled"):
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
    return key_id


def _run_worker(database, fake):
    from shop_bot.data_manager import scheduler
    from shop_bot.modules import remnawave_api

    originals = {
        name: getattr(remnawave_api, name)
        for name in (
            "get_user_used_traffic",
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
    database.add_lte_boost_bytes(1, 10 * GB)  # докупка 10 ГБ

    fake = _FakeRemnawave({"u-1": 25 * GB})
    _run_worker(database, fake)

    assert fake.removed_squads == [], "буст должен учитываться в лимите (20 + 10 > 25)"
    key = database.get_key_by_id(key_id)
    assert (key.get("remote_access_state") or "enabled") == "enabled"


def test_without_boost_access_is_revoked(temp_db):
    """Контроль: без буста тот же расход исчерпывает лимит и LTE-сквад снимается."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=2, host_name="Lte", user_uuid="u-2", plan_id=plan_id)

    fake = _FakeRemnawave({"u-2": 25 * GB})
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
    _insert_key(database, user_id=3, host_name="Lte", user_uuid="u-3", plan_id=plan_id)

    fake = _FakeRemnawave({"u-3": 25 * GB})
    _run_worker(database, fake)
    assert fake.removed_squads, "предусловие: лимит исчерпан"

    database.add_lte_boost_bytes(3, 10 * GB)
    _run_worker(database, fake)

    assert fake.added_squads == [("u-3", "squad-Lte")]
    state = database.get_lte_state(3)
    assert state["lte_used_bytes"] == 25 * GB, "расход сохраняется, а не обнуляется"
    assert state["lte_boost_bytes"] == 10 * GB
    # Остаток строго аддитивен: лимит 30 ГБ при расходе 25 ГБ.
    assert database.resolve_lte_limit_bytes(state, 20 * GB) == 30 * GB


def test_plan_limit_increase_is_picked_up(temp_db):
    """Повышение plans.lte_limit_bytes админом долетает до существующего пользователя."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=4, host_name="Lte", user_uuid="u-4", plan_id=plan_id)

    fake = _FakeRemnawave({"u-4": 25 * GB})
    _run_worker(database, fake)
    assert database.get_key_by_id(key_id)["remote_access_state"] == "disabled_premium_squad"

    plan = database.get_plan_by_id(plan_id)
    database.update_plan(
        plan_id, plan["plan_name"], plan["months"], plan["price"], lte_limit_bytes=50 * GB
    )
    _run_worker(database, fake)

    assert database.get_lte_state(4)["lte_limit_bytes"] == 50 * GB
    assert database.get_key_by_id(key_id)["remote_access_state"] == "enabled"


def test_usage_counted_once_per_remnawave_user(temp_db):
    """Два LTE-ключа с одним Remnawave-пользователем не задваивают его расход."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    _insert_key(database, user_id=5, host_name="Lte", user_uuid="u-5", plan_id=plan_id, email="a@e.com")
    database.create_host("Lte2", "https://panel.example", "", "", 0)
    database.add_host_squad("Lte2", "squad-Lte2", "lte", "LTE")
    _insert_key(database, user_id=5, host_name="Lte2", user_uuid="u-5", plan_id=plan_id, email="b@e.com")

    fake = _FakeRemnawave({"u-5": 12 * GB})
    _run_worker(database, fake)

    # 12 ГБ, а не 24 ГБ — иначе лимит 20 ГБ был бы "исчерпан" на пустом месте.
    assert database.get_lte_state(5)["lte_used_bytes"] == 12 * GB
    assert fake.removed_squads == []


def test_base_only_host_usage_not_billed_to_lte(temp_db):
    """Расход по хосту без LTE-сквада не попадает в LTE-пул."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    database.create_host("BaseOnly", "https://panel.example", "", "", 0)
    database.add_host_squad("BaseOnly", "squad-base", "base", "Base")
    _insert_key(database, user_id=6, host_name="BaseOnly", user_uuid="u-6b", plan_id=plan_id)

    fake = _FakeRemnawave({"u-6b": 100 * GB})
    _run_worker(database, fake)

    assert database.get_lte_state(6)["lte_used_bytes"] == 0
    assert fake.removed_squads == []


def test_existing_subscription_gets_baseline_initialized(temp_db):
    """Подписка, созданная до появления baseline, не отключается сразу из-за
    накопительного исторического расхода панели (одноразовый backfill)."""
    database = temp_db
    plan_id = _setup_lte_host(database, lte_gb=20)
    key_id = _insert_key(database, user_id=7, host_name="Lte", user_uuid="u-7", plan_id=plan_id)
    # Имитируем строку, созданную до миграции: отметки инициализации нет.
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO subscription_lte (user_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, "
            "premium_state, lte_baseline_initialized_at) VALUES (?, 0, 0, 0, 'enabled', NULL)",
            (7,),
        )
        conn.commit()

    fake = _FakeRemnawave({"u-7": 900 * GB})  # исторический расход панели
    _run_worker(database, fake)

    state = database.get_lte_state(7)
    assert state["lte_used_baseline_bytes"] == 900 * GB
    assert state["lte_used_bytes"] == 0
    assert state["lte_baseline_initialized_at"]
    assert database.get_key_by_id(key_id)["remote_access_state"] == "enabled"
    assert fake.removed_squads == []
