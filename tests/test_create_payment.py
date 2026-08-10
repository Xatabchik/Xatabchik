"""
Регрессионные тесты для /api/create-payment и get_transaction_comment.

Баг: get_transaction_comment() в src/shop_bot/webapp/handlers.py пытался
импортировать одноимённую функцию из shop_bot.bot.handlers, которой там
никогда не существовало. Это ломало АБСОЛЮТНО ЛЮБУЮ оплату из webapp
(ЮKassa, ЮMoney, Telegram Stars) — запрос завершался HTTP 200 с
{"ok": false, "error": "cannot import name 'get_transaction_comment' ..."},
и пользователь не мог оплатить подписку через webapp вообще.
"""
from conftest import insert_user, temp_db  # noqa: F401  (регистрирует фикстуру)


def test_get_transaction_comment_is_self_contained_new_action():
    """Функция не должна дёргать shop_bot.bot.handlers — там её нет и не было."""
    from shop_bot.webapp.handlers import get_transaction_comment

    comment = get_transaction_comment({"id": 123, "username": "ivan"}, "new", 3, "Germany")
    assert isinstance(comment, str) and comment
    assert "Оплата подписки" in comment
    assert "3 мес." in comment
    assert "Germany" in comment
    assert "@ivan" in comment


def test_get_transaction_comment_extend_action_without_username():
    from shop_bot.webapp.handlers import get_transaction_comment

    comment = get_transaction_comment({"id": 456, "username": None}, "extend", 1, None)
    assert "Продление подписки" in comment
    assert "1 мес." in comment
    assert "#456" in comment


def test_get_transaction_comment_handles_missing_months():
    from shop_bot.webapp.handlers import get_transaction_comment

    comment = get_transaction_comment({"id": 789}, "new", None, None)
    assert isinstance(comment, str) and comment


def test_create_payment_stars_end_to_end(temp_db, monkeypatch):
    """Полный прогон /api/create-payment с payment_method=pay_stars — раньше падал
    с ImportError внутри get_transaction_comment ещё до отправки счёта."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=42001, username="staruser")
    database.update_setting("stars_per_rub", "2")

    database.create_plan("TestHost", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("TestHost")[0]["plan_id"]

    sent_invoices = []

    async def fake_send_invoice_stars(user_id, title, description, payload, amount):
        sent_invoices.append(
            {"user_id": user_id, "title": title, "description": description, "payload": payload, "amount": amount}
        )
        return True

    monkeypatch.setattr(handlers, "_send_invoice_stars", fake_send_invoice_stars)

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 42001,
        "payment_method": "pay_stars",
        "plan_id": plan_id,
        "action": "new",
    })
    data = resp.json()
    assert data.get("ok") is True, data
    assert len(sent_invoices) == 1
    assert "Оплата подписки" in sent_invoices[0]["description"]
    assert sent_invoices[0]["amount"] >= 1


def test_create_payment_stars_disabled_returns_clean_error(temp_db):
    """Если Stars не настроены (stars_per_rub<=0), должна вернуться понятная ошибка,
    а не попытка импорта/отправки счёта."""
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=42002, username="staruser2")
    database.update_setting("stars_per_rub", "0")
    database.create_plan("TestHost2", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("TestHost2")[0]["plan_id"]

    client = TestClient(handlers.app)
    resp = client.post("/api/create-payment", json={
        "user_id": 42002,
        "payment_method": "pay_stars",
        "plan_id": plan_id,
        "action": "new",
    })
    data = resp.json()
    assert data.get("ok") is False
    assert "Stars" in (data.get("error") or "")
