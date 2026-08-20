"""Регрессионные тесты докупки трафика на LTE-нодах.

Покрывают причины из диагностики докупки:
  A — рассинхронизация пулов main/lte между веб-панелью и Telegram-админкой;
  B — докупленный LTE-буст не участвовал в энфорсинге, лимит тарифа не пересинхронизировался;
  C — plan_id ключа определялся только из description без fallback;
  D — хрупкая привязка host_squads к host_name (регистр, переименование, удаление);
  E — premium-хост при миграции получал squad_class='base' вместо 'lte';
  6.1 — покупка сбрасывала счётчик расхода вместо аддитивного начисления.

Внешние API (Remnawave) не поднимаются: проверяются функции работы с БД и
HTTP-роуты веб-панели.
"""
from conftest import temp_db  # noqa: F401

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


def _make_plan(database, host_name="Alpha", plan_name="M1", *, traffic_gb=50, lte_gb=20):
    database.create_host(host_name, "https://panel.example", "", "", 0)
    database.create_plan(
        host_name,
        plan_name,
        1,
        100.0,
        traffic_limit_bytes=int(traffic_gb * GB),
        lte_limit_bytes=int(lte_gb * GB),
    )
    plans = {p["plan_name"]: p["plan_id"] for p in database.get_plans_for_host(host_name)}
    return plans[plan_name]


# --- Причина A: пулы main/lte ------------------------------------------------


def test_web_panel_creates_package_in_requested_pool(temp_db):
    """Веб-форма пишет пакет в указанный пул, а не всегда в 'main'."""
    database = temp_db
    plan_id = _make_plan(database)
    client = _web_client(database)

    assert client.post(
        "/add-traffic-package",
        data={"plan_id": plan_id, "size_gb": 10, "price": 99, "pool": "main"},
    ).status_code in (302, 303)
    assert client.post(
        "/add-traffic-package",
        data={"plan_id": plan_id, "size_gb": 5, "price": 149, "pool": "lte"},
    ).status_code in (302, 303)

    main_pool = database.get_traffic_packages_for_plan(plan_id, pool="main")
    lte_pool = database.get_traffic_packages_for_plan(plan_id, pool="lte")
    assert [p["size_gb"] for p in main_pool] == [10.0]
    assert [p["size_gb"] for p in lte_pool] == [5.0]


def test_web_panel_shows_both_pools(temp_db):
    """LTE-пакет, созданный в Telegram-админке, виден в веб-панели (раньше — нет)."""
    database = temp_db
    plan_id = _make_plan(database)
    database.create_traffic_package(plan_id, 10.0, 99.0, pool="main")
    database.create_traffic_package(plan_id, 25.0, 299.0, pool="lte")
    client = _web_client(database)

    body = client.get("/settings?tab=hosts").get_data(as_text=True)
    assert "основной пул" in body
    assert "LTE-пул" in body
    assert "25.0 ГБ" in body  # LTE-пакет отрисован
    assert "10.0 ГБ" in body  # main-пакет отрисован


def test_web_panel_rejects_lte_package_without_plan_lte_limit(temp_db):
    """LTE-пакет для тарифа без LTE-лимита не создаётся (как в Telegram-админке)."""
    database = temp_db
    plan_id = _make_plan(database, plan_name="NoLte", lte_gb=0)
    client = _web_client(database)

    client.post(
        "/add-traffic-package",
        data={"plan_id": plan_id, "size_gb": 5, "price": 149, "pool": "lte"},
    )
    assert database.get_traffic_packages_for_plan(plan_id, pool="lte") == []


def test_legacy_packages_without_pool_are_main(temp_db):
    """Строки, созданные до появления колонки pool (NULL), остаются в основном пуле."""
    import sqlite3

    database = temp_db
    plan_id = _make_plan(database)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO traffic_packages (plan_id, size_gb, price, sort_order, pool) VALUES (?, ?, ?, ?, NULL)",
            (plan_id, 7.0, 77.0, 1),
        )
        conn.commit()

    assert [p["size_gb"] for p in database.get_traffic_packages_for_plan(plan_id, pool="main")] == [7.0]
    assert database.get_traffic_packages_for_plan(plan_id, pool="lte") == []


# --- Причина B / риск 6.1: формула лимита и аддитивность ---------------------


def test_resolve_lte_limit_prefers_plan_and_adds_boost(temp_db):
    database = temp_db
    state = {"lte_limit_bytes": 10 * GB, "lte_boost_bytes": 5 * GB}
    # Лимит тарифа — источник истины, сохранённое значение — только fallback.
    assert database.resolve_lte_limit_bytes(state, 20 * GB) == 25 * GB
    assert database.resolve_lte_limit_bytes(state, 0) == 15 * GB
    assert database.resolve_lte_limit_bytes(None, 0) == 0
    assert database.resolve_lte_limit_bytes({}, 20 * GB) == 20 * GB


def test_add_lte_boost_is_additive_and_does_not_reset_usage(temp_db):
    """Покупка = +N ГБ к остатку; счётчик расхода и baseline не сбрасываются."""
    database = temp_db
    database.update_lte_state(101, lte_limit_bytes=20 * GB, lte_used_bytes=18 * GB)
    database.commit_lte_baseline(101, 100 * GB, expire_boost=False)

    assert database.add_lte_boost_bytes(101, 5 * GB) == 5 * GB
    assert database.add_lte_boost_bytes(101, 10 * GB) == 15 * GB

    state = database.get_lte_state(101)
    assert state["lte_boost_bytes"] == 15 * GB
    assert state["lte_used_bytes"] == 18 * GB, "расход не должен обнуляться покупкой"
    assert state["lte_used_baseline_bytes"] == 100 * GB, "baseline не сдвигается покупкой"
    assert int(state["lte_baseline_reset_requested"] or 0) == 0
    assert database.resolve_lte_limit_bytes(state, 20 * GB) == 35 * GB


def test_add_lte_boost_rejects_non_positive(temp_db):
    database = temp_db
    assert database.add_lte_boost_bytes(102, 0) is None
    assert database.add_lte_boost_bytes(102, -5) is None


def test_period_reset_expires_boost(temp_db):
    """На границе расчётного периода буст сгорает вместе со сбросом baseline."""
    database = temp_db
    database.update_lte_state(103, lte_limit_bytes=20 * GB)
    database.add_lte_boost_bytes(103, 5 * GB)
    database.request_lte_baseline_reset(103)
    assert int(database.get_lte_state(103)["lte_baseline_reset_requested"]) == 1

    database.commit_lte_baseline(103, 250 * GB, expire_boost=True)

    state = database.get_lte_state(103)
    assert state["lte_boost_bytes"] == 0
    assert state["lte_used_baseline_bytes"] == 250 * GB
    assert int(state["lte_baseline_reset_requested"] or 0) == 0
    assert state["lte_baseline_initialized_at"]


def test_new_subscription_baseline_is_marked_initialized(temp_db):
    """Новая подписка считается от нуля: baseline = 0 и он сразу помечен определённым,
    поэтому одноразовый backfill по историческому расходу к ней не применяется."""
    database = temp_db
    state = database.get_lte_state(104)
    assert state["lte_used_baseline_bytes"] == 0
    assert state["lte_baseline_initialized_at"], "новая строка должна быть помечена сразу"


def test_baseline_backfill_applies_only_to_pre_migration_rows(temp_db):
    """Строки, созданные до появления колонки, остаются с NULL — им нужен backfill."""
    import sqlite3

    database = temp_db
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO subscription_lte (user_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, "
            "premium_state, lte_baseline_initialized_at) VALUES (?, 0, 0, 0, 'enabled', NULL)",
            (105,),
        )
        conn.commit()

    assert database.get_lte_state(105)["lte_baseline_initialized_at"] is None
    database.commit_lte_baseline(105, 42 * GB, expire_boost=False)
    state = database.get_lte_state(105)
    assert state["lte_baseline_initialized_at"]
    assert state["lte_used_baseline_bytes"] == 42 * GB


# --- Причина D: привязка host_squads ----------------------------------------


def test_get_squad_by_class_ignores_case_and_spaces(temp_db):
    database = temp_db
    database.create_host("Alpha", "https://panel.example", "", "", 0)
    assert database.add_host_squad("Alpha", "uuid-lte", "lte", "LTE")

    assert database.get_squad_by_class("Alpha", "lte")
    assert database.get_squad_by_class("alpha", "lte")
    assert database.get_squad_by_class("  ALPHA  ", "lte")
    assert database.get_squad_by_class("Alpha", "base") is None


def test_rename_host_keeps_lte_squad_binding(temp_db):
    database = temp_db
    database.create_host("Alpha", "https://panel.example", "", "", 0)
    database.add_host_squad("Alpha", "uuid-lte", "lte", "LTE")

    assert database.update_host_name("Alpha", "Alpha-renamed")

    assert database.get_squad_by_class("Alpha-renamed", "lte"), "привязка должна переехать"
    assert database.get_squad_by_class("Alpha", "lte") is None


def test_delete_host_removes_squad_rows(temp_db):
    database = temp_db
    database.create_host("Alpha", "https://panel.example", "", "", 0)
    database.add_host_squad("Alpha", "uuid-lte", "lte", "LTE")

    database.delete_host("Alpha")

    assert database.get_host_squads("Alpha") == []


# --- Причина E: миграция классов сквадов ------------------------------------


def test_premium_host_legacy_squad_migrates_as_lte(temp_db):
    """Legacy squad_uuid premium-хоста переносится с классом 'lte', обычного — 'base'."""
    import sqlite3

    database = temp_db
    database.create_host("Prem", "https://panel.example", "", "", 0)
    database.update_host_remnawave_settings("Prem", squad_uuid="uuid-prem")
    database.set_host_class("Prem", "premium")
    database.create_host("Norm", "https://panel.example", "", "", 0)
    database.update_host_remnawave_settings("Norm", squad_uuid="uuid-norm")

    # Состояние "до миграции": привязок ещё нет.
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute("DELETE FROM host_squads")
        conn.commit()

    database.initialize_db()

    assert [s["squad_class"] for s in database.get_host_squads("Prem")] == ["lte"]
    assert [s["squad_class"] for s in database.get_host_squads("Norm")] == ["base"]
    catalog = {s["squad_uuid"]: s["squad_class"] for s in database.get_remnawave_squads()}
    assert catalog["uuid-prem"] == "lte"
    assert catalog["uuid-norm"] == "base"


def test_legacy_base_squad_of_premium_host_is_reclassified(temp_db):
    """Автоматически созданную ранее запись 'Base (legacy)' у premium-хоста
    переклассифицируем; ручные привязки и dual-squad хосты не трогаем."""
    database = temp_db
    for name in ("Auto", "Manual", "Dual"):
        database.create_host(name, "https://panel.example", "", "", 0)
        database.set_host_class(name, "premium")
    database.add_host_squad("Auto", "uuid-auto", "base", "Base (legacy)")
    database.add_host_squad("Manual", "uuid-manual", "base", "Мой базовый сквад")
    database.add_host_squad("Dual", "uuid-dual-base", "base", "Base (legacy)")
    database.add_host_squad("Dual", "uuid-dual-lte", "lte", "LTE")

    database.initialize_db()

    assert [s["squad_class"] for s in database.get_host_squads("Auto")] == ["lte"]
    assert [s["squad_class"] for s in database.get_host_squads("Manual")] == ["base"]
    assert sorted(s["squad_class"] for s in database.get_host_squads("Dual")) == ["base", "lte"]


def test_migrations_are_idempotent(temp_db):
    database = temp_db
    database.create_host("Prem", "https://panel.example", "", "", 0)
    database.update_host_remnawave_settings("Prem", squad_uuid="uuid-prem")
    database.set_host_class("Prem", "premium")

    for _ in range(3):
        database.initialize_db()

    squads = database.get_host_squads("Prem")
    assert len(squads) == 1 and squads[0]["squad_class"] == "lte"
