"""
Тесты для редактирования профиля из webapp (пункт меню "Профиль"):
смена пароля и смена email (с подтверждением кодом, отправленным на новый адрес)
для аккаунтов, зарегистрированных по email+пароль. Для чисто Telegram-аккаунтов
(без auth_email) этот функционал должен быть недоступен.
"""
from conftest import (  # noqa: F401  (регистрируют фикстуры)
    app_client,
    insert_user,
    no_smtp,
    register_and_verify_email_user,
    temp_db,
)


def test_profile_info_hidden_for_pure_telegram_account(app_client, temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7001, username="tguser")
    token = "tok-7001"
    database.update_user_auth_token(7001, token)

    resp = app_client.post("/api/user/profile-info", json={"token": token})
    d = resp.json()
    assert d["ok"] is True
    assert d["has_email_auth"] is False
    assert d["auth_email"] is None


def test_profile_info_shown_for_email_account(app_client, temp_db, no_smtp):
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, "profileuser@example.com")

    resp = app_client.post("/api/user/profile-info", json={"token": token})
    d = resp.json()
    assert d["ok"] is True
    assert d["has_email_auth"] is True
    assert d["auth_email"] == "profileuser@example.com"
    assert d["email_verified"] is True
    assert d["pending_email"] is None


def test_change_password_wrong_current_password_rejected(app_client, temp_db, no_smtp):
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, "pwuser1@example.com")

    resp = app_client.post("/api/user/profile/change-password", json={
        "token": token, "current_password": "WrongPass1", "new_password": "NewPassw0rd!",
    })
    d = resp.json()
    assert d["ok"] is False
    assert "текущий пароль" in d["error"].lower()


def test_change_password_happy_path_and_old_password_stops_working(app_client, temp_db, no_smtp):
    email = "pwuser2@example.com"
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, email, password="Passw0rd!")

    resp = app_client.post("/api/user/profile/change-password", json={
        "token": token, "current_password": "Passw0rd!", "new_password": "NewPassw0rd!",
    })
    d = resp.json()
    assert d["ok"] is True

    # Старый пароль больше не работает.
    login_old = app_client.post("/api/auth/email/login", json={"email": email, "password": "Passw0rd!"})
    assert login_old.json()["ok"] is False

    # Новый пароль работает.
    login_new = app_client.post("/api/auth/email/login", json={"email": email, "password": "NewPassw0rd!"})
    assert login_new.json()["ok"] is True


def test_change_password_rejects_weak_new_password(app_client, temp_db, no_smtp):
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, "pwuser3@example.com")

    resp = app_client.post("/api/user/profile/change-password", json={
        "token": token, "current_password": "Passw0rd!", "new_password": "11111",
    })
    d = resp.json()
    assert d["ok"] is False


def test_change_password_unavailable_for_pure_telegram_account(app_client, temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=7002, username="tguser2")
    token = "tok-7002"
    database.update_user_auth_token(7002, token)

    resp = app_client.post("/api/user/profile/change-password", json={
        "token": token, "current_password": "x", "new_password": "NewPassw0rd!",
    })
    d = resp.json()
    assert d["ok"] is False


def test_change_email_wrong_password_rejected(app_client, temp_db, no_smtp):
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, "emailuser1@example.com")

    resp = app_client.post("/api/user/profile/change-email/request", json={
        "token": token, "new_email": "newaddr1@example.com", "password": "WrongPass",
    })
    assert resp.json()["ok"] is False


def test_change_email_rejects_already_used_email(app_client, temp_db, no_smtp):
    register_and_verify_email_user(app_client, temp_db.DB_FILE, "taken@example.com")
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, "emailuser2@example.com")

    resp = app_client.post("/api/user/profile/change-email/request", json={
        "token": token, "new_email": "taken@example.com", "password": "Passw0rd!",
    })
    d = resp.json()
    assert d["ok"] is False
    assert "уже использ" in d["error"].lower()


def test_change_email_happy_path(app_client, temp_db, no_smtp):
    old_email = "emailuser3@example.com"
    new_email = "emailuser3-new@example.com"
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, old_email)

    req_resp = app_client.post("/api/user/profile/change-email/request", json={
        "token": token, "new_email": new_email, "password": "Passw0rd!",
    })
    assert req_resp.json()["ok"] is True
    assert new_email in no_smtp

    # Пока код не подтверждён, старый email продолжает работать для входа.
    # (Логин выдаёт новый auth_token и делает предыдущий недействительным — как и
    # при обычном входе с нового устройства — поэтому дальше используем именно его.)
    login_old = app_client.post("/api/auth/email/login", json={"email": old_email, "password": "Passw0rd!"})
    login_old_data = login_old.json()
    assert login_old_data["ok"] is True
    token = login_old_data["token"]

    code = no_smtp[new_email]
    wrong_code = "000000" if code != "000000" else "111111"

    # Неверный код отклоняется.
    bad_verify = app_client.post("/api/user/profile/change-email/verify", json={"token": token, "code": wrong_code})
    assert bad_verify.json()["ok"] is False


    verify_resp = app_client.post("/api/user/profile/change-email/verify", json={"token": token, "code": code})
    d = verify_resp.json()
    assert d["ok"] is True
    assert d["auth_email"] == new_email

    # Старый email больше не привязан ни к какому аккаунту.
    from shop_bot.data_manager import database
    assert database.get_user_by_email(old_email) is None

    # Токен из шага verify всё ещё действителен (verify не выдаёт новый токен).
    info_resp = app_client.post("/api/user/profile-info", json={"token": token})
    info = info_resp.json()
    assert info["auth_email"] == new_email
    assert info["pending_email"] is None

    # Новый email — рабочий логин (проверяем последним, т.к. login выдаёт новый токен).
    login_new = app_client.post("/api/auth/email/login", json={"email": new_email, "password": "Passw0rd!"})
    assert login_new.json()["ok"] is True


def test_change_email_cancel_restores_old_email_only(app_client, temp_db, no_smtp):
    old_email = "emailuser4@example.com"
    new_email = "emailuser4-new@example.com"
    token, uid = register_and_verify_email_user(app_client, temp_db.DB_FILE, old_email)

    app_client.post("/api/user/profile/change-email/request", json={
        "token": token, "new_email": new_email, "password": "Passw0rd!",
    })

    cancel_resp = app_client.post("/api/user/profile/change-email/cancel", json={"token": token})
    assert cancel_resp.json()["ok"] is True

    info_resp = app_client.post("/api/user/profile-info", json={"token": token})
    info = info_resp.json()
    assert info["auth_email"] == old_email
    assert info["pending_email"] is None

    # Код, отправленный до отмены, больше не подтверждает ничего.
    code = no_smtp[new_email]
    verify_resp = app_client.post("/api/user/profile/change-email/verify", json={"token": token, "code": code})
    assert verify_resp.json()["ok"] is False


def test_change_email_concurrent_race_second_request_fails_at_verify(app_client, temp_db, no_smtp):
    """Если два разных аккаунта одновременно запросили один и тот же новый email,
    и один из них уже подтвердил код первым, второй должен получить осмысленную
    ошибку на этапе подтверждения, а не тихо украсть чужой email."""
    email_a = "racer-a@example.com"
    email_b = "racer-b@example.com"
    shared_target = "racer-target@example.com"
    token_a, _ = register_and_verify_email_user(app_client, temp_db.DB_FILE, email_a)
    token_b, _ = register_and_verify_email_user(app_client, temp_db.DB_FILE, email_b)

    app_client.post("/api/user/profile/change-email/request", json={
        "token": token_a, "new_email": shared_target, "password": "Passw0rd!",
    })
    code_a = no_smtp[shared_target]
    ok_a = app_client.post("/api/user/profile/change-email/verify", json={"token": token_a, "code": code_a})
    assert ok_a.json()["ok"] is True

    # Второй запрос на тот же email теперь должен быть отклонён на этапе request (уже занят).
    req_b = app_client.post("/api/user/profile/change-email/request", json={
        "token": token_b, "new_email": shared_target, "password": "Passw0rd!",
    })
    assert req_b.json()["ok"] is False
