"""
Регрессия CWE-639 / CWE-862 (IDOR) в FastAPI webapp.

Гипотеза «админские эндпоинты без is_admin» в webapp/handlers.py НЕ
подтвердилась: административного CRUD (промокоды/хосты/бан/статистика по
всем) в этом слое нет — он живёт в Flask-панели за @login_required.

Зато ряд пользовательских маршрутов раньше доверял голому user_id из
запроса и позволял читать/менять чужие данные (в т.ч. списывать чужой
баланс через /api/create-payment + pay_balance). Эти тесты фиксируют, что
идентичность берётся только из auth_token / signed init_data.
"""
from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def test_create_payment_rejects_bare_user_id_without_token(temp_db, monkeypatch):
    """Критично: без токена нельзя списать чужой баланс через pay_balance."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    victim_id = 91001
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim", balance=500.0)
    database.create_plan("IdorHost", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("IdorHost")[0]["plan_id"]

    called = []

    async def fake_process(bot, meta):
        called.append(meta)

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)

    resp = _client().post(
        "/api/create-payment",
        json={
            "user_id": victim_id,
            "payment_method": "pay_balance",
            "plan_id": plan_id,
            "action": "new",
        },
    )
    assert resp.status_code == 401
    assert resp.json().get("ok") is False
    assert called == []
    assert float(database.get_user(victim_id)["balance"]) == 500.0


def test_create_payment_ignores_spoofed_user_id_when_token_present(temp_db, monkeypatch):
    """Токен атакующего + чужой user_id в теле → операция от имени владельца токена."""
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    attacker_id, victim_id = 91002, 91003
    insert_user(database.DB_FILE, telegram_id=attacker_id, username="attacker", balance=50.0)
    insert_user(database.DB_FILE, telegram_id=victim_id, username="victim2", balance=500.0)
    attacker_token = issue_auth_token(attacker_id)
    database.create_plan("IdorHost2", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("IdorHost2")[0]["plan_id"]

    called = []

    async def fake_process(bot, meta):
        called.append(meta)

    monkeypatch.setattr(handlers, "process_successful_payment", fake_process)

    resp = _client().post(
        "/api/create-payment",
        json={
            "user_id": victim_id,  # spoof
            "token": attacker_token,
            "payment_method": "pay_balance",
            "plan_id": plan_id,
            "action": "new",
        },
    )
    data = resp.json()
    # атакующий сам беден — списывать должны с его баланса (не хватает), не с жертвы
    assert data.get("ok") is False
    assert called == []
    assert float(database.get_user(victim_id)["balance"]) == 500.0
    assert float(database.get_user(attacker_id)["balance"]) == 50.0


def test_user_status_requires_token_and_scopes_to_token_owner(temp_db):
    from shop_bot.data_manager import database

    owner_id, other_id = 91010, 91011
    insert_user(database.DB_FILE, telegram_id=owner_id, username="owner", balance=77.0)
    insert_user(database.DB_FILE, telegram_id=other_id, username="other", balance=999.0)
    token = issue_auth_token(owner_id)

    client = _client()
    assert client.get(f"/api/user-status?user_id={other_id}").status_code == 401

    resp = client.get(f"/api/user-status?token={token}")
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("balance") == 77.0


def test_user_transactions_requires_token(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91020, username="txuser")
    token = issue_auth_token(91020)
    client = _client()

    assert client.get("/api/user/transactions?user_id=91020").status_code == 401
    resp = client.get(f"/api/user/transactions?token={token}")
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_payment_methods_requires_token(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91030, username="pmuser", balance=12.0)
    token = issue_auth_token(91030)
    client = _client()

    bare = client.post("/api/payment-methods", json={"user_id": 91030})
    assert bare.status_code == 401

    ok = client.post("/api/payment-methods", json={"token": token})
    assert ok.status_code == 200
    assert ok.json().get("ok") is True
    assert ok.json().get("balance") == 12.0


def test_referral_info_no_longer_falls_back_to_user_id(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91040, username="refinfo")
    token = issue_auth_token(91040)
    client = _client()

    bare = client.post("/api/user/referral-info", json={"user_id": 91040})
    assert bare.status_code == 401

    ok = client.post("/api/user/referral-info", json={"token": token})
    assert ok.json().get("ok") is True


def test_key_comment_requires_token_and_ownership(temp_db):
    import sqlite3
    from shop_bot.data_manager import database

    owner_id, attacker_id = 91050, 91051
    insert_user(database.DB_FILE, telegram_id=owner_id, username="keyowner")
    insert_user(database.DB_FILE, telegram_id=attacker_id, username="keyattacker")
    owner_token = issue_auth_token(owner_id)
    attacker_token = issue_auth_token(attacker_id)

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at)
            VALUES (?, 'Host', 'a@b.c', 'a@b.c', 'vless://x', datetime('now', '+30 days'), CURRENT_TIMESTAMP)
            """,
            (owner_id,),
        )
        key_id = cur.lastrowid
        conn.commit()

    client = _client()
    # без токена
    assert client.post(
        "/api/key/comment",
        json={"user_id": owner_id, "key_id": key_id, "comment": "pwned"},
    ).status_code == 401

    # чужой токен — ключ не найден (ownership)
    resp = client.post(
        "/api/key/comment",
        json={"token": attacker_token, "user_id": owner_id, "key_id": key_id, "comment": "pwned"},
    )
    assert resp.status_code == 200
    assert resp.json().get("ok") is False

    # свой токен — ok
    resp = client.post(
        "/api/key/comment",
        json={"token": owner_token, "key_id": key_id, "comment": "mine"},
    )
    assert resp.json().get("ok") is True


def test_index_ignores_bare_user_id_query_param(temp_db):
    """/?user_id=<victim> без token больше не рендерит чужой кабинет."""
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91060, username="pagevictim")
    database.update_setting("webapp_enabled", "true")
    client = _client()
    resp = client.get("/?user_id=91060")
    assert resp.status_code == 200
    # login page (or disabled stub), not the victim's app shell
    assert 'parseInt("91060")' not in resp.text

    token = issue_auth_token(91060)
    resp2 = client.get(f"/?token={token}")
    assert resp2.status_code == 200
    assert 'parseInt("91060")' in resp2.text


def test_support_status_requires_token(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91070, username="supuser")
    token = issue_auth_token(91070)
    client = _client()

    assert client.post("/api/support/status", json={"user_id": 91070}).status_code == 401
    resp = client.post("/api/support/status", json={"token": token})
    assert resp.status_code == 200
    assert resp.json().get("ok") is True


def test_create_topup_rejects_user_id_fallback(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=91080, username="topup")
    client = _client()
    resp = client.post(
        "/api/create-topup-payment",
        json={"user_id": 91080, "payment_method": "pay_stars", "amount": 100},
    )
    assert resp.status_code == 401
