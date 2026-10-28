"""LTE-параметры уровня хоста: дефолтный лимит и общий список пакетов докупки.

Правило разрешения: собственные настройки тарифа (override) -> настройки хоста -> ничего.
Покрывает модель данных и миграции, единый резолвер, веб-панель, докупку в WebApp,
fulfillment, воркер лимитов и обратную совместимость пакетов тарифов.
"""
import asyncio
import json
import sqlite3
import time

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401
from test_lte_enforcement import _FakeRemnawave, _insert_key, _run_worker

GB = 1024 ** 3


def _web_client(temp_db):
    from shop_bot.webhook_server import app as wh_mod

    class _FakeBot:
        def get_status(self):
            return {"is_running": False}

        def get_bot_instance(self):
            return None

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
    return client


def _make_host(database, host_name="Alpha", *, default_gb=0, squad=True):
    database.create_host(host_name, "https://panel.example", "", "", 0)
    if default_gb:
        database.set_host_lte_default_limit_bytes(host_name, int(default_gb * GB))
    if squad:
        database.add_host_squad(host_name, f"squad-{host_name}", "lte", "LTE")


def _make_plan(database, host_name="Alpha", plan_name="M1", *, months=1, lte_gb=0, traffic_gb=0):
    database.create_plan(
        host_name,
        plan_name,
        months,
        100.0 * months,
        traffic_limit_bytes=int(traffic_gb * GB),
        lte_limit_bytes=int(lte_gb * GB),
    )
    plans = {p["plan_name"]: p["plan_id"] for p in database.get_plans_for_host(host_name)}
    return plans[plan_name]


GRID = [(500, 3267), (1500, 8400), (5000, 25667), (15000, 72800), (50000, 233333)]


def _host_with_four_plans(database, host_name="До 100 устройств"):
    _make_host(database, host_name, default_gb=100)
    plan_ids = [
        _make_plan(database, host_name, f"{m} мес.", months=m) for m in (1, 3, 6, 12)
    ]
    for size, price in GRID:
        assert database.create_host_traffic_package(host_name, size, price, pool="lte")
    return host_name, plan_ids


# --- Миграции ----------------------------------------------------------------


def test_migration_is_idempotent_and_keeps_data(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=7)
    plan_id = _make_plan(database, lte_gb=3)
    pkg_id = database.create_traffic_package(plan_id, 5.0, 99.0, pool="lte")

    database.run_migration()
    database.run_migration()

    with sqlite3.connect(database.DB_FILE) as conn:
        host_cols = [r[1] for r in conn.execute("PRAGMA table_info(xui_hosts)")]
        pkg_cols = [r[1] for r in conn.execute("PRAGMA table_info(traffic_packages)")]
        indexes = [r[1] for r in conn.execute("PRAGMA index_list(traffic_packages)")]
    assert host_cols.count("lte_default_limit_bytes") == 1
    assert pkg_cols.count("host_name") == 1
    assert "idx_traffic_packages_host_pool" in indexes
    assert database.get_host_lte_default_limit_bytes("Alpha") == 7 * GB
    assert database.get_traffic_package_by_id(pkg_id)["size_gb"] == 5.0
    assert database.get_plan_by_id(plan_id)["lte_limit_bytes"] == 3 * GB


def test_old_database_without_new_columns_upgrades_without_behaviour_change(temp_db):
    """База до миграции: колонок нет, у хоста пусто, всё работает как раньше."""
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, lte_gb=20)
    own = database.create_traffic_package(plan_id, 5.0, 149.0, pool="lte")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("ALTER TABLE xui_hosts DROP COLUMN lte_default_limit_bytes")
        conn.execute("DROP INDEX idx_traffic_packages_host_pool")
        conn.execute("ALTER TABLE traffic_packages DROP COLUMN host_name")
        conn.commit()

    database.run_migration()

    plan = database.get_plan_by_id(plan_id)
    assert database.resolve_plan_lte_limit_bytes(plan) == 20 * GB
    assert [p["package_id"] for p in database.get_lte_packages_for_plan(plan)] == [own]
    assert database.lte_packages_source(plan) == "plan"
    assert database.get_host_lte_packages("Alpha") == []


def test_host_package_sentinel_does_not_hit_foreign_key(temp_db):
    """plan_id = 0 формально нарушает FK на plans, но соединения проекта FK не включают."""
    database = temp_db
    _make_host(database, "Alpha")
    with sqlite3.connect(database.DB_FILE) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    assert database.create_host_traffic_package("Alpha", 10.0, 99.0, pool="lte")


# --- Резолвер лимита ---------------------------------------------------------


def test_host_without_default_keeps_plan_zero_limit_unaccounted(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan = database.get_plan_by_id(_make_plan(database, lte_gb=0))
    assert database.resolve_plan_lte_limit_bytes(plan) == 0
    assert database.plan_lte_limit_bytes(plan) == 0
    assert database.should_account_lte_traffic(plan, "Alpha") is False


def test_plan_inherits_host_default_and_own_limit_wins(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=100)
    inheriting = database.get_plan_by_id(_make_plan(database, plan_name="inherit", lte_gb=0))
    own = database.get_plan_by_id(_make_plan(database, plan_name="own", lte_gb=30))

    assert database.resolve_plan_lte_limit_bytes(inheriting) == 100 * GB
    assert database.resolve_plan_lte_limit_bytes(own) == 30 * GB
    assert database.should_account_lte_traffic(inheriting, "Alpha") is True
    assert database.should_account_lte_traffic(own, "Alpha") is True
    # Запись plans.lte_limit_bytes — это override и остаётся как есть.
    assert database.get_plan_by_id(inheriting["plan_id"])["lte_limit_bytes"] in (0, None)


def test_resetting_host_default_to_zero_behaves_like_zeroed_plan_limit(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=100)
    plan = database.get_plan_by_id(_make_plan(database, lte_gb=0))
    assert database.should_account_lte_traffic(plan, "Alpha") is True

    assert database.set_host_lte_default_limit_bytes("Alpha", 0) is True
    assert database.resolve_plan_lte_limit_bytes(plan) == 0
    assert database.should_account_lte_traffic(plan, "Alpha") is False
    assert database.set_host_lte_default_limit_bytes("Нет такого", 5 * GB) is False


def test_host_default_lookup_ignores_case_and_spaces(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=5)
    assert database.get_host_lte_default_limit_bytes("  alpha ") == 5 * GB
    plan = {"plan_id": 1, "host_name": " ALPHA", "lte_limit_bytes": 0}
    assert database.resolve_plan_lte_limit_bytes(plan) == 5 * GB


def test_monthly_reset_needed_for_inherited_limit(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan = database.get_plan_by_id(_make_plan(database, lte_gb=0))
    assert database.plan_has_monthly_traffic_reset(plan) is False
    database.set_host_lte_default_limit_bytes("Alpha", 10 * GB)
    assert database.plan_has_monthly_traffic_reset(plan) is True


# --- Пакеты: override -> хост -> ничего --------------------------------------


def test_four_plans_share_five_host_packages_and_price_edit_hits_all(temp_db):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database)

    for plan_id in plan_ids:
        plan = database.get_plan_by_id(plan_id)
        packages = database.get_lte_packages_for_plan(plan, only_active=True)
        assert [(p["size_gb"], p["price"]) for p in packages] == [(float(s), float(p)) for s, p in GRID]
        assert database.lte_packages_source(plan) == "host"

    first = database.get_host_lte_packages(host_name)[0]
    assert database.update_traffic_package(first["package_id"], price=3000.0)
    for plan_id in plan_ids:
        plan = database.get_plan_by_id(plan_id)
        assert database.get_lte_packages_for_plan(plan)[0]["price"] == 3000.0

    database.update_traffic_package(first["package_id"], is_active=False)
    for plan_id in plan_ids:
        plan = database.get_plan_by_id(plan_id)
        assert len(database.get_lte_packages_for_plan(plan, only_active=True)) == 4


def test_own_packages_override_host_and_all_disabled_hides_topup(temp_db):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database)
    plan = database.get_plan_by_id(plan_ids[0])
    own = database.create_traffic_package(plan_ids[0], 7.0, 70.0, pool="lte")

    assert [p["package_id"] for p in database.get_lte_packages_for_plan(plan)] == [own]
    assert database.lte_packages_source(plan) == "plan"
    # Остальные тарифы хоста по-прежнему видят пакеты хоста.
    other = database.get_plan_by_id(plan_ids[1])
    assert len(database.get_lte_packages_for_plan(other)) == 5

    database.update_traffic_package(own, is_active=False)
    assert database.get_lte_packages_for_plan(plan, only_active=True) == []
    assert len(database.get_lte_packages_for_plan(plan)) == 1
    assert database.lte_packages_source(plan) == "plan"


def test_source_none_without_any_packages(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan = database.get_plan_by_id(_make_plan(database, lte_gb=5))
    assert database.lte_packages_source(plan) == "none"
    assert database.get_lte_packages_for_plan(plan) == []


def test_main_pool_packages_untouched_by_host_logic(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, traffic_gb=50)
    database.create_traffic_package(plan_id, 10.0, 99.0, pool="main")
    assert database.create_host_traffic_package("Alpha", 10.0, 99.0, pool="main") is None
    assert len(database.get_traffic_packages_for_plan(plan_id, pool="main")) == 1
    assert database.get_traffic_packages_for_plan(0, pool="lte") == []


def test_package_of_host_a_does_not_apply_to_plan_of_host_b(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    _make_host(database, "Beta")
    plan_a = database.get_plan_by_id(_make_plan(database, "Alpha", "A", lte_gb=5))
    plan_b = database.get_plan_by_id(_make_plan(database, "Beta", "B", lte_gb=5))
    pkg_a = database.get_traffic_package_by_id(database.create_host_traffic_package("Alpha", 5.0, 50.0))

    assert database.lte_package_applies_to_plan(pkg_a, plan_a) is True
    assert database.lte_package_applies_to_plan(pkg_a, plan_b) is False
    assert database.get_lte_packages_for_plan(plan_b) == []


def test_package_applies_regardless_of_host_name_case_and_spaces(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan = database.get_plan_by_id(_make_plan(database, "Alpha", "A", lte_gb=5))
    pkg = database.get_traffic_package_by_id(database.create_host_traffic_package(" ALPHA ", 5.0, 50.0))
    assert pkg["host_name"] == "ALPHA"
    assert database.lte_package_applies_to_plan(pkg, plan) is True
    assert database.get_lte_packages_for_plan(plan)[0]["package_id"] == pkg["package_id"]


def test_main_pool_package_never_applies_as_lte(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, lte_gb=5)
    main_id = database.create_traffic_package(plan_id, 10.0, 99.0, pool="main")
    plan = database.get_plan_by_id(plan_id)
    assert database.lte_package_applies_to_plan(database.get_traffic_package_by_id(main_id), plan) is False


def test_legacy_plan_package_applies_only_to_its_plan(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan_1 = database.get_plan_by_id(_make_plan(database, plan_name="one", lte_gb=5))
    plan_2 = database.get_plan_by_id(_make_plan(database, plan_name="two", lte_gb=5))
    pkg = database.get_traffic_package_by_id(
        database.create_traffic_package(plan_1["plan_id"], 5.0, 50.0, pool="lte")
    )
    assert database.lte_package_applies_to_plan(pkg, plan_1) is True
    assert database.lte_package_applies_to_plan(pkg, plan_2) is False


# --- Хост: переименование, удаление; тариф: удаление -------------------------


def test_rename_host_keeps_packages_and_delete_removes_them(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=10)
    plan_id = _make_plan(database)
    database.create_host_traffic_package("Alpha", 5.0, 50.0)

    assert database.update_host_name("Alpha", "Омега 2")
    plan = database.get_plan_by_id(plan_id)
    assert plan["host_name"] == "Омега 2"
    assert len(database.get_host_lte_packages("Омега 2")) == 1
    assert database.get_host_lte_packages("Alpha") == []
    assert len(database.get_lte_packages_for_plan(plan)) == 1
    assert database.get_host_lte_default_limit_bytes("Омега 2") == 10 * GB

    database.delete_host("Омега 2")
    assert database.get_host_lte_packages("Омега 2") == []
    with sqlite3.connect(database.DB_FILE) as conn:
        left = conn.execute("SELECT COUNT(*) FROM traffic_packages WHERE plan_id = 0").fetchone()[0]
    assert left == 0


def test_delete_host_does_not_touch_other_hosts_packages(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    _make_host(database, "Beta")
    database.create_host_traffic_package("Alpha", 5.0, 50.0)
    database.create_host_traffic_package("Beta", 6.0, 60.0)
    database.delete_host("Alpha")
    assert [p["size_gb"] for p in database.get_host_lte_packages("Beta")] == [6.0]


def test_delete_plan_removes_only_its_packages(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, lte_gb=5)
    other_id = _make_plan(database, plan_name="other", lte_gb=5)
    database.create_traffic_package(plan_id, 5.0, 50.0, pool="lte")
    keep = database.create_traffic_package(other_id, 6.0, 60.0, pool="lte")
    database.create_host_traffic_package("Alpha", 7.0, 70.0)

    database.delete_plan(plan_id)
    database.delete_plan(0)

    assert len(database.get_host_lte_packages("Alpha")) == 1
    assert [p["package_id"] for p in database.get_traffic_packages_for_plan(other_id, pool="lte")] == [keep]


def test_copy_plan_packages_to_host_skips_duplicates(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, lte_gb=5)
    database.create_traffic_package(plan_id, 5.0, 50.0, pool="lte")
    off = database.create_traffic_package(plan_id, 10.0, 90.0, pool="lte")
    database.update_traffic_package(off, is_active=False)
    database.create_host_traffic_package("Alpha", 5.0, 50.0)

    assert database.copy_plan_lte_packages_to_host(plan_id, "Alpha") == 1
    assert database.copy_plan_lte_packages_to_host(plan_id, "Alpha") == 0
    host_pkgs = database.get_host_lte_packages("Alpha")
    assert [(p["size_gb"], p["is_active"]) for p in host_pkgs] == [(5.0, 1), (10.0, 0)]
    assert len(database.get_traffic_packages_for_plan(plan_id, pool="lte")) == 2


# --- Веб-панель --------------------------------------------------------------


def test_web_adds_toggles_edits_deletes_host_packages(temp_db):
    database = temp_db
    _make_host(database, "Хост с пробелом")
    client = _web_client(database)

    resp = client.post(
        "/add-traffic-package",
        data={"host_name": "Хост с пробелом", "size_gb": 500, "price": 3267, "pool": "lte"},
    )
    assert resp.status_code in (302, 303)
    pkgs = database.get_host_lte_packages("Хост с пробелом")
    assert [(p["size_gb"], p["price"], p["plan_id"]) for p in pkgs] == [(500.0, 3267.0, 0)]
    pkg_id = pkgs[0]["package_id"]

    client.post(f"/update-traffic-package/{pkg_id}", data={"host_name": "Хост с пробелом", "size_gb": 600, "price": 4000})
    assert database.get_traffic_package_by_id(pkg_id)["size_gb"] == 600.0

    client.post(f"/toggle-traffic-package/{pkg_id}", data={"host_name": "Хост с пробелом"})
    assert database.get_traffic_package_by_id(pkg_id)["is_active"] == 0

    client.post(f"/delete-traffic-package/{pkg_id}", data={"host_name": "Хост с пробелом"})
    assert database.get_traffic_package_by_id(pkg_id) is None


def test_web_rejects_non_positive_host_package_values_and_main_pool(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    client = _web_client(database)
    for size, price in ((0, 10), (-5, 10), (5, 0), (5, -1)):
        client.post("/add-traffic-package", data={"host_name": "Alpha", "size_gb": size, "price": price, "pool": "lte"})
    client.post("/add-traffic-package", data={"host_name": "Alpha", "size_gb": 5, "price": 5, "pool": "main"})
    client.post("/add-traffic-package", data={"host_name": "Alpha", "plan_id": 1, "size_gb": 5, "price": 5, "pool": "lte"})
    assert database.get_host_lte_packages("Alpha") == []

    pkg_id = database.create_host_traffic_package("Alpha", 5.0, 50.0)
    client.post(f"/update-traffic-package/{pkg_id}", data={"host_name": "Alpha", "size_gb": 0})
    client.post(f"/update-traffic-package/{pkg_id}", data={"host_name": "Alpha", "price": -3})
    pkg = database.get_traffic_package_by_id(pkg_id)
    assert (pkg["size_gb"], pkg["price"]) == (5.0, 50.0)


def test_web_scope_mismatch_does_not_touch_foreign_package(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    _make_host(database, "Beta")
    pkg_id = database.create_host_traffic_package("Alpha", 5.0, 50.0)
    client = _web_client(database)

    client.post(f"/delete-traffic-package/{pkg_id}", data={"host_name": "Beta"})
    client.post(f"/toggle-traffic-package/{pkg_id}", data={"host_name": "Beta"})
    client.post(f"/update-traffic-package/{pkg_id}", data={"host_name": "Beta", "price": 1})
    pkg = database.get_traffic_package_by_id(pkg_id)
    assert pkg is not None and pkg["is_active"] == 1 and pkg["price"] == 50.0


def test_web_plan_package_guard_uses_effective_limit(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, lte_gb=0)
    client = _web_client(database)

    client.post("/add-traffic-package", data={"plan_id": plan_id, "size_gb": 5, "price": 50, "pool": "lte"})
    assert database.get_traffic_packages_for_plan(plan_id, pool="lte") == []

    database.set_host_lte_default_limit_bytes("Alpha", 10 * GB)
    client.post("/add-traffic-package", data={"plan_id": plan_id, "size_gb": 5, "price": 50, "pool": "lte"})
    assert len(database.get_traffic_packages_for_plan(plan_id, pool="lte")) == 1


def test_web_saves_host_default_limit(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    client = _web_client(database)

    client.post("/update-host-lte-default", data={"host_name": "Alpha", "lte_default_limit_gb": "250.5"})
    assert database.get_host_lte_default_limit_bytes("Alpha") == int(250.5 * GB)
    client.post("/update-host-lte-default", data={"host_name": "Alpha", "lte_default_limit_gb": "abc"})
    assert database.get_host_lte_default_limit_bytes("Alpha") == int(250.5 * GB)
    client.post("/update-host-lte-default", data={"host_name": "Alpha", "lte_default_limit_gb": "0"})
    assert database.get_host_lte_default_limit_bytes("Alpha") == 0


def test_web_copy_packages_from_plan(temp_db):
    database = temp_db
    _make_host(database, "Alpha")
    _make_host(database, "Beta")
    plan_id = _make_plan(database, "Alpha", "A", lte_gb=5)
    foreign = _make_plan(database, "Beta", "B", lte_gb=5)
    database.create_traffic_package(plan_id, 5.0, 50.0, pool="lte")
    database.create_traffic_package(foreign, 9.0, 90.0, pool="lte")
    client = _web_client(database)

    client.post("/copy-plan-lte-packages-to-host", data={"host_name": "Alpha", "source_plan_id": foreign})
    assert database.get_host_lte_packages("Alpha") == []
    client.post("/copy-plan-lte-packages-to-host", data={"host_name": "Alpha", "source_plan_id": plan_id})
    client.post("/copy-plan-lte-packages-to-host", data={"host_name": "Alpha", "source_plan_id": plan_id})
    assert [(p["size_gb"], p["price"]) for p in database.get_host_lte_packages("Alpha")] == [(5.0, 50.0)]
    assert len(database.get_traffic_packages_for_plan(plan_id, pool="lte")) == 1


def test_settings_page_shows_host_block_source_labels_and_squad_warning(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=100, squad=False)
    inheriting = _make_plan(database, "Alpha", "inherit", lte_gb=0)
    overriding = _make_plan(database, "Alpha", "override", lte_gb=0)
    database.create_host_traffic_package("Alpha", 500.0, 3267.0)
    database.create_traffic_package(overriding, 7.0, 70.0, pool="lte")
    client = _web_client(database)

    body = client.get("/settings?tab=hosts").get_data(as_text=True)
    assert "LTE хоста" in body
    assert "нет активного сквада класса LTE" in body
    assert "500.0 ГБ — 3267.0 RUB" in body
    assert "наследуется от хоста: 100.0 ГБ" in body
    assert "Используются пакеты хоста (1 шт.)" in body
    assert "Пакеты тарифа (переопределяют хост)" in body
    assert "Первый собственный пакет полностью заменит список хоста" in body
    assert "Взять пакеты из тарифа" in body
    # Лимит унаследован — блок «Сначала задайте…» не показывается.
    assert "Сначала задайте «LTE пул, ГБ" not in body

    database.add_host_squad("Alpha", "squad-alpha", "lte", "LTE")
    body = client.get("/settings?tab=hosts").get_data(as_text=True)
    assert "нет активного сквада класса LTE" not in body

    database.set_host_lte_default_limit_bytes("Alpha", 0)
    body = client.get("/settings?tab=hosts").get_data(as_text=True)
    assert "Сначала задайте «LTE пул, ГБ" in body


# --- WebApp: докупка ---------------------------------------------------------


def _webapp_client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _seed_key(database, host_name, plan_id, user_id, *, uuid_suffix=""):
    insert_user(database.DB_FILE, telegram_id=user_id, username=f"u{user_id}", balance=5000.0)
    return database.add_new_key(
        user_id,
        host_name,
        f"uuid-{user_id}{uuid_suffix}",
        f"{user_id}-lte@bot.local",
        int((time.time() + 30 * 86400) * 1000),
        description=json.dumps({"plan_id": plan_id}),
        subscription_url=f"https://sub.example/{user_id}",
    )


def test_webapp_shows_host_packages_for_inheriting_plan(temp_db):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    key_id = _seed_key(database, host_name, plan_ids[2], 97001)
    token = issue_auth_token(97001)

    data = _webapp_client().get("/api/lte-packages", params={"key_id": key_id, "token": token}).json()
    assert data["ok"] is True, data
    assert [p["size_gb"] for p in data["packages"]] == [float(s) for s, _ in GRID]
    # Лимит унаследован от хоста: 0 ГБ / 100 ГБ.
    assert "0 ГБ / 100 ГБ" in data["lte_info"]


def test_webapp_override_hides_host_packages_and_all_disabled_hides_topup(temp_db):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    own = database.create_traffic_package(plan_ids[0], 7.0, 70.0, pool="lte")
    key_id = _seed_key(database, host_name, plan_ids[0], 97002)
    token = issue_auth_token(97002)
    client = _webapp_client()

    data = client.get("/api/lte-packages", params={"key_id": key_id, "token": token}).json()
    assert [p["size_gb"] for p in data["packages"]] == [7.0]

    database.update_traffic_package(own, is_active=False)
    data = client.get("/api/lte-packages", params={"key_id": key_id, "token": token}).json()
    assert data["ok"] is False


def test_webapp_topup_metadata_carries_key_plan_id_for_host_package(temp_db, monkeypatch):
    from shop_bot.webapp import handlers

    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    key_id = _seed_key(database, host_name, plan_ids[1], 97003)
    token = issue_auth_token(97003)
    pkg = database.get_host_lte_packages(host_name)[0]
    called = []

    async def fake_process(bot, meta):
        called.append(meta)
        return True

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)
    monkeypatch.setattr(handlers, "get_setting", lambda key, *a, **k: {"telegram_bot_token": "123:TEST"}.get(key, ""))

    data = _webapp_client().post(
        "/api/create-lte-topup-payment",
        json={"token": token, "key_id": key_id, "package_id": pkg["package_id"], "payment_method": "pay_balance"},
    ).json()
    assert data.get("ok") is True and data.get("paid") is True, data
    assert called[0]["plan_id"] == plan_ids[1]
    assert called[0]["package_id"] == pkg["package_id"]
    assert called[0]["price"] == 3267.0


def test_webapp_rejects_foreign_host_and_hidden_host_packages(temp_db, monkeypatch):
    from shop_bot.webapp import handlers

    database = temp_db
    host_a, plans_a = _host_with_four_plans(database, "Alpha")
    _make_host(database, "Beta", default_gb=50)
    plan_b = _make_plan(database, "Beta", "B1")
    key_b = _seed_key(database, "Beta", plan_b, 97004)
    foreign_pkg = database.get_host_lte_packages(host_a)[0]["package_id"]
    token = issue_auth_token(97004)
    called = []

    async def fake_process(bot, meta):
        called.append(meta)
        return True

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)
    monkeypatch.setattr(handlers, "get_setting", lambda key, *a, **k: {"telegram_bot_token": "123:TEST"}.get(key, ""))
    client = _webapp_client()

    resp = client.post(
        "/api/create-lte-topup-payment",
        json={"token": token, "key_id": key_b, "package_id": foreign_pkg, "payment_method": "pay_balance"},
    ).json()
    assert resp.get("ok") is False
    assert called == []
    assert float(database.get_user(97004)["balance"]) == 5000.0

    # У тарифа со своим набором пакеты хоста купить нельзя, даже зная package_id.
    host_pkg_a = database.get_host_lte_packages(host_a)[0]["package_id"]
    database.create_traffic_package(plans_a[0], 7.0, 70.0, pool="lte")
    key_a = _seed_key(database, host_a, plans_a[0], 97005)
    resp = client.post(
        "/api/create-lte-topup-payment",
        json={"token": issue_auth_token(97005), "key_id": key_a, "package_id": host_pkg_a, "payment_method": "pay_balance"},
    ).json()
    assert resp.get("ok") is False
    assert called == []


def test_lte_card_state_uses_inherited_limit(temp_db):
    from shop_bot.webapp.handlers import _lte_card_state

    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    key_id = _seed_key(database, host_name, plan_ids[0], 97006)
    state = _lte_card_state(database.get_key_by_id(key_id))
    assert state["show_lte_topup"] is True
    assert state["lte_total_bytes"] == 100 * GB

    database.set_host_lte_default_limit_bytes(host_name, 0)
    assert _lte_card_state(database.get_key_by_id(key_id))["show_lte_topup"] is False


# --- Fulfillment -------------------------------------------------------------


class _FakeSentMessage:
    async def edit_text(self, *a, **k):
        return None

    async def delete(self):
        return None


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, *a, **k):
        self.sent.append((a, k))
        return _FakeSentMessage()


def _run_topup(database, *, user_id, key_id, package_id, payment_id, plan_id=None, price=50.0):
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    meta = {
        "user_id": user_id,
        "price": price,
        "action": "lte_gb_topup",
        "key_id": key_id,
        "package_id": package_id,
        "payment_method": "Balance",
        "payment_id": payment_id,
    }
    if plan_id is not None:
        meta["plan_id"] = plan_id
    return asyncio.run(process_successful_payment(_FakeBot(), meta))


def test_fulfillment_credits_host_package_to_key_of_same_host(temp_db):
    database = temp_db
    host_name, plan_ids = _host_with_four_plans(database, "Alpha")
    key_id = _seed_key(database, host_name, plan_ids[0], 97010)
    pkg = database.get_host_lte_packages(host_name)[0]

    _run_topup(database, user_id=97010, key_id=key_id, package_id=pkg["package_id"], payment_id="balance:97010:ok")
    assert database.get_key_lte_state(key_id)["lte_boost_bytes"] == int(500 * GB)


def test_fulfillment_rejects_package_of_other_host_and_refunds(temp_db):
    database = temp_db
    host_a, _ = _host_with_four_plans(database, "Alpha")
    _make_host(database, "Beta", default_gb=50)
    plan_b = _make_plan(database, "Beta", "B1")
    key_b = _seed_key(database, "Beta", plan_b, 97011)
    foreign_pkg = database.get_host_lte_packages(host_a)[0]["package_id"]

    _run_topup(database, user_id=97011, key_id=key_b, package_id=foreign_pkg, payment_id="balance:97011:x", price=3267.0)

    assert database.get_key_lte_state(key_b)["lte_boost_bytes"] == 0
    assert float(database.get_user(97011)["balance"]) >= 5000.0 + 3267.0 - 1e-6


def test_fulfillment_rejects_plan_package_of_other_plan(temp_db):
    database = temp_db
    _make_host(database, "Alpha", default_gb=10)
    plan_1 = _make_plan(database, plan_name="one")
    plan_2 = _make_plan(database, plan_name="two")
    pkg_of_plan_2 = database.create_traffic_package(plan_2, 5.0, 50.0, pool="lte")
    key_1 = _seed_key(database, "Alpha", plan_1, 97012)

    _run_topup(database, user_id=97012, key_id=key_1, package_id=pkg_of_plan_2, payment_id="balance:97012:x")
    assert database.get_key_lte_state(key_1)["lte_boost_bytes"] == 0


def test_fulfillment_still_accepts_legacy_plan_package_payment(temp_db):
    """Платёж, созданный до миграции с пакетом тарифа, проходит как раньше."""
    database = temp_db
    _make_host(database, "Alpha")
    plan_id = _make_plan(database, lte_gb=20)
    pkg = database.create_traffic_package(plan_id, 5.0, 50.0, pool="lte")
    key_id = _seed_key(database, "Alpha", plan_id, 97013)

    _run_topup(database, user_id=97013, key_id=key_id, package_id=pkg, payment_id="balance:97013:ok")
    assert database.get_key_lte_state(key_id)["lte_boost_bytes"] == int(5 * GB)


# --- Воркер лимитов ----------------------------------------------------------


def _worker_setup(database, *, plan_lte_gb=0, default_gb=100, state="enabled"):
    database.create_host("Lte", "https://panel.example", "", "", 0)
    database.add_host_squad("Lte", "squad-Lte", "lte", "LTE")
    database.update_host_remnawave_settings("Lte", remnawave_base_url="https://panel.example", remnawave_api_token="tok")
    if default_gb:
        database.set_host_lte_default_limit_bytes("Lte", default_gb * GB)
    plan_id = _make_plan(database, "Lte", "plan-Lte", lte_gb=plan_lte_gb)
    key_id = _insert_key(database, user_id=1, host_name="Lte", user_uuid="u-1", plan_id=plan_id, state=state)
    return plan_id, key_id


def test_worker_accounts_inherited_limit_and_adds_lte_squad_once(temp_db):
    database = temp_db
    _, key_id = _worker_setup(database)
    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": GB}, nodes_by_host={"Lte": ["node-lte"]})

    _run_worker(database, fake)
    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 100 * GB
    assert fake.added_squads == [("u-1", "squad-Lte")]
    assert fake.node_usage_calls

    _run_worker(database, fake)
    assert fake.added_squads == [("u-1", "squad-Lte")], "сквад добавляется один раз, а не на каждом проходе"


def test_worker_propagates_changed_host_default_to_key_state(temp_db):
    database = temp_db
    _, key_id = _worker_setup(database)
    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": GB}, nodes_by_host={"Lte": ["node-lte"]})
    _run_worker(database, fake)

    database.set_host_lte_default_limit_bytes("Lte", 150 * GB)
    _run_worker(database, fake)
    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 150 * GB


def test_worker_retries_squad_when_add_fails_and_skips_disabled_keys(temp_db):
    database = temp_db
    _, key_id = _worker_setup(database)
    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": GB}, nodes_by_host={"Lte": ["node-lte"]})

    async def failing_add(user_uuid, squad_uuid, *, host_name):
        return False

    fake.add_squad_to_user = failing_add
    _run_worker(database, fake)
    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 0, "лимит не фиксируется, пока сквад не добавлен"


def test_worker_does_not_add_squad_to_key_with_own_plan_limit(temp_db):
    """Прежнее поведение для тарифов с собственным лимитом не меняется."""
    database = temp_db
    _, key_id = _worker_setup(database, plan_lte_gb=20, default_gb=100)
    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": GB}, nodes_by_host={"Lte": ["node-lte"]})
    _run_worker(database, fake)
    assert fake.added_squads == []
    assert database.get_key_lte_state(key_id)["lte_limit_bytes"] == 20 * GB


def test_worker_skips_hosts_without_any_limit(temp_db):
    database = temp_db
    _, key_id = _worker_setup(database, plan_lte_gb=0, default_gb=0)
    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": GB}, nodes_by_host={"Lte": ["node-lte"]})
    _run_worker(database, fake)
    assert fake.node_usage_calls == []
    assert fake.added_squads == []


def test_worker_enforces_inherited_limit(temp_db):
    database = temp_db
    _, key_id = _worker_setup(database, default_gb=10)
    database.commit_key_lte_baseline(key_id, 0, expire_boost=False)
    fake = _FakeRemnawave({"u-1": 0}, usage_by_node={"node-lte": 11 * GB}, nodes_by_host={"Lte": ["node-lte"]})
    _run_worker(database, fake)
    assert ("u-1", "squad-Lte") in fake.removed_squads


# --- Выдача ключа ------------------------------------------------------------


def test_key_creation_adds_lte_squad_for_inherited_limit(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    database = temp_db
    _make_host(database, "Alpha", default_gb=100)
    database.update_host_remnawave_settings("Alpha", squad_uuid="squad-base")
    plan_id = _make_plan(database, "Alpha", "M1", lte_gb=0)
    captured = {}

    async def fake_write(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(remnawave_api, "_write_key_on_host", fake_write)
    asyncio.run(remnawave_api.create_or_update_key_on_host("Alpha", "a@bot.local", days_to_add=30, plan_id=plan_id))
    assert captured["extra_squad_uuids"] == ["squad-Alpha"]

    database.set_host_lte_default_limit_bytes("Alpha", 0)
    captured.clear()
    asyncio.run(remnawave_api.create_or_update_key_on_host("Alpha", "a@bot.local", days_to_add=30, plan_id=plan_id))
    assert captured["extra_squad_uuids"] == []


# --- Telegram-админка --------------------------------------------------------


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def _texts(markup):
    return [b.text for row in markup.inline_keyboard for b in row]


def test_admin_host_keyboard_has_lte_limit_and_packages_buttons():
    from shop_bot.bot import keyboards

    kb = keyboards.create_admin_host_manage_keyboard("abc123", "unlim", 100 * GB)
    assert "admin_hosts_lte_limit:abc123" in _callbacks(kb)
    assert "admin_hosts_lte_packages:abc123" in _callbacks(kb)
    assert "💰 LTE-лимит хоста: 100 ГБ" in _texts(kb)
    kb = keyboards.create_admin_host_manage_keyboard("abc123")
    assert "💰 LTE-лимит хоста: не задан" in _texts(kb)


def test_admin_host_packages_view_and_keyboards(temp_db):
    from shop_bot.bot import keyboards
    from shop_bot.bot.admin_router.plans import _host_lte_packages_view

    database = temp_db
    _make_host(database, "Alpha")
    text, kb = _host_lte_packages_view("Alpha")
    assert "Пакеты пока не настроены" in text
    assert "admin_pkg_add_host_lte" in _callbacks(kb)

    pkg_id = database.create_host_traffic_package("Alpha", 500.0, 3267.0)
    _text, kb = _host_lte_packages_view("Alpha")
    assert f"admin_pkg_open_{pkg_id}" in _callbacks(kb)

    manage = keyboards.create_admin_traffic_package_manage_keyboard(pkg_id, 0, True, host_scope=True)
    assert "admin_pkg_back_host" in _callbacks(manage)


def test_admin_plan_keyboard_marks_inherited_limit(temp_db):
    from shop_bot.bot import keyboards

    database = temp_db
    _make_host(database, "Alpha", default_gb=100)
    inheriting = database.get_plan_by_id(_make_plan(database, plan_name="inherit"))
    own = database.get_plan_by_id(_make_plan(database, plan_name="own", lte_gb=30))
    assert "💰 LTE-лимит: 100 ГБ (хост)" in _texts(keyboards.create_admin_plan_manage_keyboard(inheriting))
    assert "💰 LTE-лимит: 30 ГБ" in _texts(keyboards.create_admin_plan_manage_keyboard(own))
