"""
Промокод в этом проекте — исключительно скидка на покупку/продление/подарочную
покупку VPN-ключа. Он НЕ должен работать при пополнении баланса.

Регрессионные тесты для:
1. /api/apply-promo — только discount-промокоды, требует price, больше не
   поддерживает мёртвые "balance"/"universal" промо-типы (раньше их можно было
   активировать напрямую на баланс через отдельную кнопку на странице покупки —
   этот вход в интерфейсе убран).
2. /api/create-payment — скидка по промокоду реально уменьшает сумму счёта
   (раньше было мёртвое условие promo.get('promo_type') == 'discount', которое
   не могло сработать, т.к. такой колонки в БД нет — скидка визуально
   "применялась" в интерфейсе, но реальный счёт создавался на полную цену).
   Промокод применяется для action in ("new", "extend", "gift") и НЕ должен
   применяться для action == "top_up" (защита на уровне сервера, даже если
   каким-то образом promo_code окажется в теле запроса с этим action).
3. /api/create-topup-payment — модель запроса не содержит поля promo_code вовсе.
"""
from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def _make_plan(database, host_name: str, price: float = 100.0) -> int:
    database.create_plan(host_name, "1 месяц", 1, price)
    return database.get_plans_for_host(host_name)[0]["plan_id"]


def test_apply_promo_requires_price(temp_db):
    """Промокод нельзя "активировать" без контекста покупки (без price) —
    раньше это было единственным способом активировать бонусный промокод
    напрямую (кнопка на странице покупки открывала модалку без price/plan_id)."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51001, username="promouser1")
    token = issue_auth_token(51001)
    from shop_bot.data_manager import remnawave_repository as rw_repo
    rw_repo.create_promo_code("SAVE10", discount_percent=10)

    client = TestClient(handlers.app)
    resp = client.post("/api/apply-promo", json={"user_id": 51001, "token": token, "promo_code": "SAVE10"})
    data = resp.json()
    assert data.get("ok") is False
    assert "покуп" in data.get("error", "").lower() or "продлен" in data.get("error", "").lower()


def test_apply_promo_discount_math(temp_db):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51002, username="promouser2")
    token = issue_auth_token(51002)
    rw_repo.create_promo_code("HALF50", discount_percent=50)

    client = TestClient(handlers.app)
    resp = client.post("/api/apply-promo", json={"user_id": 51002, "token": token, "promo_code": "HALF50", "price": 200})
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("promo_type") == "discount"
    assert data.get("new_price") == 100.0


def test_apply_promo_no_longer_credits_balance_directly(temp_db):
    """Дожимаем главный сценарий бага: даже без price активация НЕ должна
    как-либо трогать баланс пользователя (раньше могла — через мёртвую ветку
    promo_type == 'balance', которая физически не могла сработать, но сама
    возможность такого дизайна была недопустима)."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51003, username="promouser3")
    token = issue_auth_token(51003)
    rw_repo.create_promo_code("HALF50B", discount_percent=50)
    balance_before = database.get_user(51003).get("balance") or 0

    client = TestClient(handlers.app)
    resp = client.post("/api/apply-promo", json={"user_id": 51003, "token": token, "promo_code": "HALF50B"})
    assert resp.json().get("ok") is False

    balance_after = database.get_user(51003).get("balance") or 0
    assert balance_after == balance_before


def test_create_payment_stars_new_action_applies_promo_discount(temp_db, monkeypatch):
    """Скидка по промокоду должна реально уменьшать сумму СОЗДАВАЕМОГО счёта,
    а не только отображаемую в интерфейсе цену."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51004, username="promouser4")
    token = issue_auth_token(51004)
    database.update_setting("stars_per_rub", "2")
    rw_repo.create_promo_code("HALFSTARS", discount_percent=50)
    plan_id = _make_plan(database, "PromoHost1", price=100.0)

    invoices = []

    async def fake_send_invoice_stars(user_id, title, description, payload, amount):
        invoices.append(amount)
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_send_invoice_stars)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 51004,
        "token": token,
        "payment_method": "pay_stars",
        "plan_id": plan_id,
        "action": "new",
        "promo_code": "HALFSTARS",
    })
    assert resp.json().get("ok") is True
    assert len(invoices) == 1
    # Без скидки было бы 100 * 2 = 200 звёзд; со скидкой 50% — 50 * 2 = 100.
    assert invoices[0] == 100, invoices


def test_create_payment_gift_action_also_applies_promo_discount(temp_db, monkeypatch):
    """action == 'gift' (покупка ключа в подарок) — такая же полноценная покупка
    ключа, промокод должен работать и здесь, не только для 'new'/'extend'."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51005, username="promouser5")
    token = issue_auth_token(51005)
    database.update_setting("stars_per_rub", "2")
    rw_repo.create_promo_code("GIFTPROMO", discount_percent=50)
    plan_id = _make_plan(database, "PromoHost2", price=100.0)

    invoices = []

    async def fake_send_invoice_stars(user_id, title, description, payload, amount):
        invoices.append(amount)
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_send_invoice_stars)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 51005,
        "token": token,
        "payment_method": "pay_stars",
        "plan_id": plan_id,
        "action": "gift",
        "promo_code": "GIFTPROMO",
    })
    assert resp.json().get("ok") is True
    assert invoices[0] == 100, invoices


def test_create_payment_top_up_action_never_applies_promo_discount(temp_db, monkeypatch):
    """Защита на уровне сервера: даже если бы promo_code каким-то образом попал
    в тело запроса /api/create-payment вместе с action='top_up', скидка не
    должна применяться. (В обычной работе webapp это не может произойти —
    пополнение баланса создаётся через отдельный /api/create-topup-payment без
    поля promo_code вовсе — но эндпоинт /api/create-payment сам по себе не
    должен доверять action бездумно.)"""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=51006, username="promouser6")
    token = issue_auth_token(51006)
    database.update_setting("stars_per_rub", "2")
    rw_repo.create_promo_code("NOTOPUP", discount_percent=50)
    plan_id = _make_plan(database, "PromoHost3", price=100.0)

    invoices = []

    async def fake_send_invoice_stars(user_id, title, description, payload, amount):
        invoices.append(amount)
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_send_invoice_stars)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 51006,
        "token": token,
        "payment_method": "pay_stars",
        "plan_id": plan_id,
        "action": "top_up",
        "promo_code": "NOTOPUP",
    })
    assert resp.json().get("ok") is True
    # Без скидки: 100 * 2 = 200 звёзд. Промокод НЕ должен был применяться.
    assert invoices[0] == 200, invoices


def test_create_topup_payment_request_has_no_promo_field():
    """CreateTopUpPaymentRequest структурно не может нести promo_code — это
    единственный по-настоящему надёжный барьер против применения промокода
    при пополнении баланса."""
    from shop_bot.webapp.handlers import CreateTopUpPaymentRequest

    assert "promo_code" not in CreateTopUpPaymentRequest.model_fields


def test_promo_activation_button_removed_from_purchase_and_renew_pages():
    """Раньше на страницах покупки/продления была отдельная кнопка
    "Активировать промокод", открывающая модалку активации бонусного промокода
    (на баланс/дни) в обход покупки — теперь такого входа не должно быть."""
    import re
    from pathlib import Path

    app_html = Path(__file__).resolve().parents[1] / "src" / "shop_bot" / "webapp" / "app.html"
    content = app_html.read_text(encoding="utf-8")
    assert "openPromoModal" not in content
    assert "activateBonusPromo" not in content
    assert "promo_activation" not in content
