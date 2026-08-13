"""Регрессия: late-bind ``referred_by`` у существующего пользователя и TOCTOU
стартового реферального бонуса.

Старый ``register_user_if_not_exists`` при повторном вызове (существующая
строка, пустой ``referred_by``) делал ``UPDATE users SET referred_by = ?``.
Любой ``/start ref_<id>`` от уже зарегистрированного пользователя без реферера
привязывал аккаунт. Стартовый бонус читал флаг, кредитовал баланс, и только
потом ставил флаг — два параллельных вызова оба проходили проверку.

Новый код: ``referred_by`` только на INSERT; claim бонуса —
``UPDATE ... WHERE COALESCE(referral_start_bonus_received, 0) = 0`` до кредита.
Webapp pending-action передаёт ``max_age_seconds=1800`` (как gift); админский
assign без окна по-прежнему может привязать существующего пользователя.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from conftest import insert_user, make_telegram_init_data, temp_db  # noqa: F401


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, *args, **kwargs):
        self.sent.append((chat_id, text))


def test_existing_user_register_does_not_late_bind_referred_by(temp_db):
    """Старый код: повторный register_user_if_not_exists с referrer_id
    выставлял referred_by существующему пользователю с пустым полем."""
    database = temp_db
    database.register_user_if_not_exists(7001, "olduser", None)
    database.register_user_if_not_exists(7002, "referrer", None)
    assert database.get_user(7001)["referred_by"] is None

    # Как /start ref_7002 для уже существующего пользователя.
    database.register_user_if_not_exists(7001, "olduser", 7002)

    assert database.get_user(7001)["referred_by"] is None
    assert database.get_user(7001)["username"] == "olduser"


def test_new_user_insert_still_sets_referred_by(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7010, "referrer", None)
    database.register_user_if_not_exists(7011, "newuser", 7010)
    assert database.get_user(7011)["referred_by"] == 7010


def test_existing_referred_by_not_overwritten_on_reregister(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7020, "first", None)
    database.register_user_if_not_exists(7021, "second", None)
    database.register_user_if_not_exists(7022, "invitee", 7020)
    database.register_user_if_not_exists(7022, "invitee", 7021)
    assert database.get_user(7022)["referred_by"] == 7020


def test_username_still_updates_for_existing_user(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7030, "oldname", None)
    database.register_user_if_not_exists(7030, "newname", 7999)
    user = database.get_user(7030)
    assert user["username"] == "newname"
    assert user["referred_by"] is None


def test_claim_referral_start_bonus_only_one_winner(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7101, "invitee", None)
    assert database.claim_referral_start_bonus(7101) is True
    assert database.claim_referral_start_bonus(7101) is False
    assert database.set_referral_start_bonus_received(7101) is False
    assert database.get_user(7101)["referral_start_bonus_received"] == 1


def test_claim_referral_start_bonus_threaded_only_one_winner(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7102, "invitee", None)

    def _one():
        return database.claim_referral_start_bonus(7102)

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_one) for _ in range(8)]
        for fut in as_completed(futs):
            results.append(fut.result())

    assert results.count(True) == 1, results
    assert results.count(False) == 7
    assert database.get_user(7102)["referral_start_bonus_received"] == 1


def test_start_bonus_concurrent_handler_credits_once(temp_db):
    """Два параллельных _maybe_pay_referral_start_bonus не должны удвоить баланс.

    На старом коде (check flag → credit → set flag) этот тест падал бы:
    оба потока видели referral_start_bonus_received=0.
    """
    from shop_bot.bot import handlers as bot_handlers

    database = temp_db
    database.update_setting("referral_reward_type", "fixed_start_referrer")
    database.update_setting("referral_on_start_referrer_amount", "25")
    database.register_user_if_not_exists(7201, "referrer", None)
    database.register_user_if_not_exists(7202, "invitee", 7201)

    fake_bot = _FakeBot()

    def _one():
        asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, 7202, 7201))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_one) for _ in range(8)]
        for fut in as_completed(futs):
            fut.result()

    referrer = database.get_user(7201)
    assert referrer["referral_balance"] == 25.0
    assert referrer["referral_balance_all"] == 25.0
    assert database.get_user(7202)["referral_start_bonus_received"] == 1
    assert len(fake_bot.sent) == 1


def test_gift_still_sets_referred_by_for_fresh_user(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7301, "gifter", None)
    database.register_user_if_not_exists(7302, "fresh", None)
    assert database.set_referred_by_from_gift(7302, 7301) is True
    assert database.get_user(7302)["referred_by"] == 7301


def test_gift_does_not_set_referred_by_for_old_account(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7310, "gifter", None)
    insert_user(
        database.DB_FILE,
        telegram_id=7311,
        username="old",
        registration_date=(datetime.now() - timedelta(days=7)).isoformat(sep=" "),
    )
    assert database.set_referred_by_from_gift(7311, 7310) is False
    assert database.get_user(7311)["referred_by"] is None


def test_link_referrer_rejects_old_account_when_max_age_set(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7401, "referrer", None)
    insert_user(
        database.DB_FILE,
        telegram_id=7402,
        username="old",
        registration_date=(datetime.now() - timedelta(days=30)).isoformat(sep=" "),
    )
    status = database.link_referrer_if_eligible(7402, 7401, max_age_seconds=1800)
    assert status == "not_eligible"
    assert database.get_user(7402)["referred_by"] is None


def test_link_referrer_without_max_age_still_allows_admin_assign(temp_db):
    """Админский assign вызывает link_referrer_if_eligible без окна давности."""
    database = temp_db
    database.register_user_if_not_exists(7410, "referrer", None)
    insert_user(
        database.DB_FILE,
        telegram_id=7411,
        username="old",
        registration_date=(datetime.now() - timedelta(days=30)).isoformat(sep=" "),
    )
    status = database.link_referrer_if_eligible(7411, 7410)
    assert status == "linked"
    assert database.get_user(7411)["referred_by"] == 7410


def test_link_referrer_allows_fresh_user_within_max_age(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7420, "referrer", None)
    database.register_user_if_not_exists(7421, "fresh", None)
    status = database.link_referrer_if_eligible(7421, 7420, max_age_seconds=1800)
    assert status == "linked"
    assert database.get_user(7421)["referred_by"] == 7420


def test_old_account_cannot_late_bind_via_pending_referral(temp_db, app_client):
    """Webapp /ref/<id> + Telegram login существующего старого аккаунта
    не должен выставлять referred_by (на старом коде — выставлял)."""
    database = temp_db
    insert_user(database.DB_FILE, telegram_id=7501, username="referrer")
    insert_user(
        database.DB_FILE,
        telegram_id=7502,
        username="oldtguser",
        registration_date=(datetime.now() - timedelta(days=30)).isoformat(sep=" "),
    )

    r = app_client.get("/ref/7501", follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    pending_token = r.headers["location"].split("pending_token=")[1]

    complete = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "init_data": make_telegram_init_data(7502)},
    )
    body = complete.json()
    assert body["ok"] is False
    assert body["status"] == "not_eligible"
    assert database.get_user(7502)["referred_by"] is None
