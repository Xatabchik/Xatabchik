"""
Исключение email-only пользователей (без Telegram) из рассылок.

Email-аккаунты создаются с синтетическим telegram_id в диапазоне
999000000000–999999999999 (create_user_by_email). Пока пользователь не
привязал реальный Telegram, боту некуда доставлять сообщения — такие
аккаунты должны исключаться из всех рассылок.
"""
from conftest import insert_user, temp_db  # noqa: F401


def test_is_email_only_user_detects_virtual_ids():
    from shop_bot.data_manager import database

    assert database.is_email_only_user(999000000001) is True
    assert database.is_email_only_user(999999999999) is True
    assert database.is_email_only_user(123456789) is False
    assert database.is_email_only_user(None) is False
    assert database.is_email_only_user("not-a-number") is False


def test_get_inactive_subscribers_excludes_email_only_users(temp_db):
    from shop_bot.data_manager import database

    # Реальный Telegram-пользователь без активных ключей — должен попасть в рассылку.
    insert_user(database.DB_FILE, telegram_id=10001, username="tg_user")
    # Email-only без Telegram — должен быть исключён.
    insert_user(
        database.DB_FILE,
        telegram_id=999000000042,
        username="email_only",
        auth_email="only@example.com",
    )
    # Забаненный реальный пользователь — тоже исключён (уже существующее правило).
    insert_user(database.DB_FILE, telegram_id=10002, username="banned", is_banned=1)
    # Недоступный реальный пользователь — исключён.
    insert_user(
        database.DB_FILE,
        telegram_id=10003,
        username="blocked",
        is_unreachable=1,
        unreachable_reason="blocked",
    )

    recipients = database.get_inactive_subscribers()
    assert 10001 in recipients
    assert 999000000042 not in recipients
    assert 10002 not in recipients
    assert 10003 not in recipients


def test_get_pending_broadcast_recipients_excludes_email_only(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=20001, username="tg_ok")
    insert_user(
        database.DB_FILE,
        telegram_id=999000000100,
        username="email_skip",
        auth_email="skip@example.com",
    )

    campaign_id = database.create_broadcast_campaign(
        name="test",
        text_html="<b>hi</b>",
        interval_hours=72,
        target_segment="inactive",
    )
    assert campaign_id

    recipients = database.get_pending_broadcast_recipients(campaign_id, 72)
    assert 20001 in recipients
    assert 999000000100 not in recipients


def test_create_user_by_email_uses_virtual_id_range(temp_db):
    from shop_bot.data_manager import database

    user = database.create_user_by_email("virtual@example.com", "Passw0rd!")
    assert user is not None
    assert database.is_email_only_user(user["telegram_id"]) is True
