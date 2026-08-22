"""
Регрессионные тесты для delete_user_completely: полное удаление пользователя
должно чистить ВСЕ связанные с ним данные, а не только основную запись в
`users`. Главный найденный баг — не удалялся статус прохождения капчи
(`user_captcha_status` / `captcha_challenges`), из-за чего при повторной
регистрации того же telegram_id (после "удаления" пользователя) капча молча
пропускалась: has_passed_captcha() находил старую запись, оставшуюся от
удалённого аккаунта.
"""
import sqlite3

from conftest import insert_user, temp_db  # noqa: F401  (регистрирует фикстуру)


def test_delete_user_completely_removes_user_row(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=9001, username="todelete")
    assert database.get_user(9001) is not None

    assert database.delete_user_completely(9001) is True
    assert database.get_user(9001) is None


def test_delete_user_completely_clears_captcha_status(temp_db):
    """Основной баг: has_passed_captcha() должен вернуть False после удаления —
    иначе капча при повторной регистрации того же telegram_id не показывается."""
    from shop_bot.data_manager import database
    from shop_bot.data_manager.captcha_utils import (
        create_captcha_challenge,
        has_passed_captcha,
        mark_user_passed_captcha,
    )

    user_id = 9002
    insert_user(database.DB_FILE, telegram_id=user_id, username="captchauser")

    challenge = create_captcha_challenge(user_id, "math")
    assert challenge is not None
    mark_user_passed_captcha(user_id, challenge["id"])
    assert has_passed_captcha(user_id) is True

    assert database.delete_user_completely(user_id) is True

    assert has_passed_captcha(user_id) is False


def test_delete_user_completely_clears_captcha_challenges_history(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.data_manager.captcha_utils import create_captcha_challenge

    user_id = 9003
    insert_user(database.DB_FILE, telegram_id=user_id, username="captchauser2")
    create_captcha_challenge(user_id, "math")
    create_captcha_challenge(user_id, "button")

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM captcha_challenges WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 2

    database.delete_user_completely(user_id)

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM captcha_challenges WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 0


def test_recreated_account_with_same_telegram_id_must_pass_captcha_again(temp_db):
    """Полная имитация репортованного сценария: пользователь проходит капчу,
    администратор удаляет его, тот же человек (тот же telegram_id) снова пишет
    /start — капча обязана сработать заново, как для нового пользователя."""
    from shop_bot.data_manager import database
    from shop_bot.data_manager.captcha_utils import (
        create_captcha_challenge,
        has_passed_captcha,
        mark_user_passed_captcha,
    )

    user_id = 9004
    database.register_user_if_not_exists(user_id, "returninguser", None)
    challenge = create_captcha_challenge(user_id, "math")
    mark_user_passed_captcha(user_id, challenge["id"])
    assert has_passed_captcha(user_id) is True

    assert database.delete_user_completely(user_id) is True

    # Тот же человек пишет /start заново — с точки зрения бота это "новый" пользователь.
    assert database.get_user(user_id) is None
    assert has_passed_captcha(user_id) is False  # капча должна показаться снова

    # Регистрация после (гипотетического) успешного повторного прохождения капчи
    # не должна воскрешать старый статус.
    database.register_user_if_not_exists(user_id, "returninguser", None)
    assert has_passed_captcha(user_id) is False


def test_delete_user_completely_clears_referral_payout_data(temp_db):
    """Методы получения удаляются, заявки на вывод остаются админу."""
    from shop_bot.data_manager import database

    user_id = 9005
    insert_user(database.DB_FILE, telegram_id=user_id, username="refuser")
    ok, msg, method_id = database.add_referral_payout_method(user_id, "card", "1234567812345678")
    assert ok, msg

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO referral_withdrawal_requests (user_id, amount, method_type, requisite_value) "
            "VALUES (?, 500, 'card', '1234567812345678')",
            (user_id,),
        )
        conn.commit()

    database.delete_user_completely(user_id)

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM referral_payout_methods WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM referral_withdrawal_requests WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 1


def test_delete_user_completely_clears_webapp_auth_requests(temp_db):
    from shop_bot.data_manager import database

    user_id = 9006
    insert_user(database.DB_FILE, telegram_id=user_id, username="webappuser")
    token = "test-auth-token-9006"
    database.create_webapp_auth_request(token)
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE webapp_auth_requests SET user_id = ? WHERE token = ?", (user_id, token))
        conn.commit()

    database.delete_user_completely(user_id)

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM webapp_auth_requests WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 0


def test_delete_user_completely_clears_key_usage_monitor(temp_db):
    from shop_bot.data_manager import database

    user_id = 9007
    insert_user(database.DB_FILE, telegram_id=user_id, username="keyuser")
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at) "
            "VALUES (?, 'Host', 'a@example.com', 'a@example.com', 'vless://x', datetime('now', '+30 days'), CURRENT_TIMESTAMP)",
            (user_id,),
        )
        key_id = cur.lastrowid
        cur.execute(
            "INSERT INTO key_usage_monitor (key_id, user_id, last_checked_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key_id, user_id),
        )
        conn.commit()

    database.delete_user_completely(user_id)

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM key_usage_monitor WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT COUNT(*) FROM vpn_keys WHERE user_id = ?", (user_id,))
        assert cur.fetchone()[0] == 0
