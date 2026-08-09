"""
Тесты единого сценария pending action: пользователь открывает ссылку подарка
(`/gift/<code>`) или реферальную ссылку (`/ref/<id>`), затем авторизуется
через Telegram ИЛИ через email — и в обоих случаях исходное действие
(активация подарка / привязка реферала) применяется сервером ровно один раз,
после успешной авторизации.

Запуск: `pytest tests/` из корня репозитория (зависимости — см. pyproject.toml
`[project.optional-dependencies].dev`, плюс основные зависимости проекта).
"""
import sqlite3
import threading

import pytest

from conftest import insert_gift_key, insert_user, make_telegram_init_data, register_and_verify_email_user


def _pending_token_from_redirect(response) -> str:
    assert response.status_code in (302, 307), response.text
    location = response.headers["location"]
    assert "pending_token=" in location
    return location.split("pending_token=")[1]


# ── 1) Неавторизован → открывает /gift/<code> → входит через Telegram → подарок активируется ──
def test_gift_link_telegram_login_activates_gift(temp_db, app_client, monkeypatch):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1001, username="gifter")
    insert_user(database.DB_FILE, telegram_id=2001, username="recipient")
    gift_id, key_id = insert_gift_key(database.DB_FILE, from_user_id=1001, gift_code="GIFT-TG-1")

    r = app_client.get("/gift/GIFT-TG-1", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    info = app_client.get(f"/api/webapp/pending-actions/info?pending_token={pending_token}")
    assert info.json() == {
        "ok": True,
        "valid": True,
        "action_type": "gift",
        "message": "Вам доступен подарок — VPN-ключ будет активирован на ваш аккаунт после входа.",
        "host_name": "TestHost",
    }

    init_data = make_telegram_init_data(2001)
    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "init_data": init_data},
    )
    body = complete.json()
    assert body["ok"] is True
    assert body["status"] == "activated"

    key = database.get_key_by_id(key_id)
    assert key["user_id"] == 2001
    gift = database.get_user_gift(gift_id)
    assert gift["is_activated"] == 1
    assert gift["activated_by_user_id"] == 2001


# ── 2) Неавторизован → /gift/<code> → регистрируется по email → подарок активируется после регистрации ──
def test_gift_link_email_register_activates_gift(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1002, username="gifter")
    gift_id, key_id = insert_gift_key(database.DB_FILE, from_user_id=1002, gift_code="GIFT-EMAIL-REG")

    r = app_client.get("/gift/GIFT-EMAIL-REG", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    auth_token, new_user_id = register_and_verify_email_user(app_client, database.DB_FILE, "newgiftuser@example.com")

    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "token": auth_token},
    )
    body = complete.json()
    assert body["ok"] is True
    assert body["status"] == "activated"

    key = database.get_key_by_id(key_id)
    assert key["user_id"] == new_user_id
    assert database.get_user_gift(gift_id)["is_activated"] == 1


# ── 3) Неавторизован → /gift/<code> → входит в СУЩЕСТВУЮЩИЙ email-аккаунт → подарок активируется ──
def test_gift_link_email_login_existing_account_activates_gift(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1003, username="gifter")
    gift_id, key_id = insert_gift_key(database.DB_FILE, from_user_id=1003, gift_code="GIFT-EMAIL-LOGIN")

    # Аккаунт уже существует и подтверждён (создан заранее, до перехода по ссылке).
    email = "existinguser@example.com"
    auth_token, existing_user_id = register_and_verify_email_user(app_client, database.DB_FILE, email)

    r = app_client.get("/gift/GIFT-EMAIL-LOGIN", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    # Логинимся заново (как если бы это была новая сессия/устройство).
    login = app_client.post("/api/auth/email/login", json={"email": email, "password": "Passw0rd!"})
    fresh_token = login.json()["token"]

    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "token": fresh_token},
    )
    body = complete.json()
    assert body["ok"] is True
    assert body["status"] == "activated"

    key = database.get_key_by_id(key_id)
    assert key["user_id"] == existing_user_id
    assert database.get_user_gift(gift_id)["is_activated"] == 1


# ── 4) Подарок нельзя активировать дважды параллельными запросами ──
def test_gift_cannot_be_activated_twice_by_parallel_requests(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1004, username="gifter")
    gift_id, key_id = insert_gift_key(database.DB_FILE, from_user_id=1004, gift_code="GIFT-RACE")

    r = app_client.get("/gift/GIFT-RACE", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    auth_token, user_id = register_and_verify_email_user(app_client, database.DB_FILE, "raceuser@example.com")

    results = []

    def _complete():
        resp = app_client.post(
            "/api/webapp/pending-actions/complete",
            json={"pending_token": pending_token, "token": auth_token},
        )
        results.append(resp.json())

    threads = [threading.Thread(target=_complete) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    winners = [r for r in results if not r.get("already_completed")]
    assert len(winners) == 1, f"expected exactly 1 genuine winner, got {winners}"
    assert winners[0]["status"] == "activated"
    assert all(r["ok"] for r in results), "no request should report failure for its own re-check"

    # Ключ переназначен ровно на активировавшего пользователя, подарок активирован один раз.
    key = database.get_key_by_id(key_id)
    assert key["user_id"] == user_id
    assert database.get_user_gift(gift_id)["is_activated"] == 1


# ── 5) Просроченный / уже использованный pending token не работает ──
def test_expired_pending_token_is_rejected(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1005, username="gifter")
    insert_gift_key(database.DB_FILE, from_user_id=1005, gift_code="GIFT-EXPIRED")

    expired_token = database.create_pending_action("gift", gift_code="GIFT-EXPIRED", ttl_hours=0)
    # ttl_hours=0 -> expires_at считается как datetime('now','+0 hours') == "сейчас";
    # чуть подождём, чтобы гарантированно оказаться в прошлом относительно СУБД.
    import time
    time.sleep(1.1)

    info = app_client.get(f"/api/webapp/pending-actions/info?pending_token={expired_token}")
    assert info.json()["valid"] is False
    assert info.json()["error"] == "expired"

    auth_token, _ = register_and_verify_email_user(app_client, database.DB_FILE, "expireduser@example.com")
    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": expired_token, "token": auth_token},
    )
    body = complete.json()
    assert body["ok"] is False
    assert body["error"] == "expired"


def test_used_pending_token_is_rejected_for_a_different_user(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1006, username="gifter")
    insert_gift_key(database.DB_FILE, from_user_id=1006, gift_code="GIFT-USED")

    r = app_client.get("/gift/GIFT-USED", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    token_a, _ = register_and_verify_email_user(app_client, database.DB_FILE, "usera@example.com")
    first = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "token": token_a},
    )
    assert first.json()["ok"] is True

    token_b, _ = register_and_verify_email_user(app_client, database.DB_FILE, "userb@example.com")
    second = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "token": token_b},
    )
    body = second.json()
    assert body["ok"] is False
    assert body["error"] == "already_used"


# ── 6) Неавторизован → /ref/<id> → регистрируется по email → referred_by устанавливается ──
def test_referral_link_email_register_sets_referred_by(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=3001, username="referrer")

    r = app_client.get("/ref/3001", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    info = app_client.get(f"/api/webapp/pending-actions/info?pending_token={pending_token}")
    assert info.json()["ok"] is True
    assert info.json()["action_type"] == "referral"

    auth_token, new_user_id = register_and_verify_email_user(app_client, database.DB_FILE, "refbyemail@example.com")
    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "token": auth_token},
    )
    body = complete.json()
    assert body["ok"] is True
    assert body["status"] == "linked"

    user = database.get_user(new_user_id)
    assert user["referred_by"] == 3001


# ── 7) Тот же флоу работает при Telegram-входе ──
def test_referral_link_telegram_login_sets_referred_by(temp_db, app_client):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=3002, username="referrer")
    insert_user(database.DB_FILE, telegram_id=4002, username="newtguser")

    r = app_client.get("/ref/3002", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    init_data = make_telegram_init_data(4002)
    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "init_data": init_data},
    )
    body = complete.json()
    assert body["ok"] is True
    assert body["status"] == "linked"

    user = database.get_user(4002)
    assert user["referred_by"] == 3002


# ── 8) Пользователь не может стать рефералом самого себя ──
def test_user_cannot_be_referral_of_self(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    auth_token, user_id = register_and_verify_email_user(app_client, database.DB_FILE, "selfref@example.com")

    r = app_client.get(f"/ref/{user_id}", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "token": auth_token},
    )
    body = complete.json()
    assert body["ok"] is False
    assert body["status"] == "self_referral_forbidden"

    user = database.get_user(user_id)
    assert user["referred_by"] is None


# ── 9) Существующий referred_by не перезаписывается ──
def test_existing_referred_by_is_not_overwritten(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=3003, username="first_referrer")
    insert_user(database.DB_FILE, telegram_id=3004, username="second_referrer")

    auth_token, user_id = register_and_verify_email_user(app_client, database.DB_FILE, "doublereferral@example.com")

    r1 = app_client.get("/ref/3003", follow_redirects=False)
    token1 = _pending_token_from_redirect(r1)
    complete1 = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": token1, "token": auth_token}
    )
    assert complete1.json()["status"] == "linked"

    r2 = app_client.get("/ref/3004", follow_redirects=False)
    token2 = _pending_token_from_redirect(r2)
    complete2 = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": token2, "token": auth_token}
    )
    body2 = complete2.json()
    assert body2["ok"] is False
    assert body2["status"] == "already_linked"

    user = database.get_user(user_id)
    assert user["referred_by"] == 3003, "referred_by must remain the FIRST referrer, not be overwritten"


# ── 10) Повторный вызов complete не повторяет бонус и не меняет данные ──
def test_repeat_complete_call_does_not_repeat_bonus_or_change_data(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    database.update_setting("referral_reward_type", "fixed_start_referrer")
    database.update_setting("referral_on_start_referrer_amount", "35")
    insert_user(database.DB_FILE, telegram_id=3005, username="referrer")

    r = app_client.get("/ref/3005", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    auth_token, user_id = register_and_verify_email_user(app_client, database.DB_FILE, "bonusrepeat@example.com")

    first = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": auth_token}
    )
    assert first.json()["status"] == "linked"

    referrer_after_first = database.get_user(3005)
    assert referrer_after_first["referral_balance"] == 35.0

    # Повторяем тот же самый запрос несколько раз.
    for _ in range(3):
        again = app_client.post(
            "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": auth_token}
        )
        body = again.json()
        assert body["ok"] is True
        assert body.get("already_completed") is True

    referrer_final = database.get_user(3005)
    assert referrer_final["referral_balance"] == 35.0, "bonus must not be paid more than once"
    assert referrer_final["referral_balance_all"] == 35.0

    user = database.get_user(user_id)
    assert user["referred_by"] == 3005


def test_repeat_gift_complete_call_does_not_create_second_key(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1007, username="gifter")
    gift_id, key_id = insert_gift_key(database.DB_FILE, from_user_id=1007, gift_code="GIFT-REPEAT")

    r = app_client.get("/gift/GIFT-REPEAT", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)
    auth_token, user_id = register_and_verify_email_user(app_client, database.DB_FILE, "giftrepeat@example.com")

    first = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": auth_token}
    )
    assert first.json()["status"] == "activated"

    for _ in range(3):
        again = app_client.post(
            "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": auth_token}
        )
        assert again.json()["ok"] is True
        assert again.json().get("already_completed") is True

    with sqlite3.connect(database.DB_FILE) as conn:
        keys_count = conn.execute(
            "SELECT COUNT(*) FROM vpn_keys WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    assert keys_count == 1, "repeated complete() must not create a second VPN key"


# ── 11) Невалидный токен и невалидный подарок/реферер возвращают безопасную ошибку ──
def test_invalid_pending_token_and_targets_return_safe_errors(temp_db, app_client, no_smtp):
    from shop_bot.data_manager import database

    auth_token, _ = register_and_verify_email_user(app_client, database.DB_FILE, "safeerrors@example.com")

    # Совсем несуществующий токен.
    resp = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": "this-token-does-not-exist", "token": auth_token},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["ok"] is False
    assert body["error"] == "invalid"
    assert "gift_code" not in body and "referrer_id" not in body  # ничего лишнего не утекает

    info_resp = app_client.get("/api/webapp/pending-actions/info?pending_token=this-token-does-not-exist")
    assert info_resp.json()["valid"] is False

    # Подарок, который был удалён/никогда не существовал, но pending action на него всё же создан.
    ghost_token = database.create_pending_action("gift", gift_code="NO-SUCH-GIFT-CODE")
    ghost_complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": ghost_token, "token": auth_token},
    )
    ghost_body = ghost_complete.json()
    assert ghost_body["ok"] is False
    assert ghost_body["status"] == "not_found"

    # Реферер, которого не существует.
    bad_ref_token = database.create_pending_action("referral", referrer_id=999999999)
    bad_ref_complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": bad_ref_token, "token": auth_token},
    )
    bad_ref_body = bad_ref_complete.json()
    assert bad_ref_body["ok"] is False
    assert bad_ref_body["status"] == "invalid_referrer"


# ── Дополнительно: complete() никогда не доверяет user_id, присланному клиентом ──
def test_complete_never_trusts_client_supplied_user_id(temp_db, app_client, no_smtp):
    """Если бы сервер доверял user_id из тела запроса, можно было бы активировать
    чужой подарок без входа в систему вообще — просто угадав чужой telegram_id.
    Убедимся, что без валидного auth-токена/init_data запрос всегда unauthorized,
    независимо от того, что ещё передано в теле."""
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=1008, username="gifter")
    insert_user(database.DB_FILE, telegram_id=9999, username="victim")
    gift_id, key_id = insert_gift_key(database.DB_FILE, from_user_id=1008, gift_code="GIFT-NOSPOOF")

    r = app_client.get("/gift/GIFT-NOSPOOF", follow_redirects=False)
    pending_token = _pending_token_from_redirect(r)

    resp = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "user_id": 9999},  # игнорируется — не наш параметр
    )
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "unauthorized"

    # Подарок не должен быть тронут.
    assert database.get_user_gift(gift_id)["is_activated"] == 0
    key = database.get_key_by_id(key_id)
    assert key["user_id"] == 1008
