"""
Регрессия: списание Balance/ReferralBalance без выдачи ключа должно
откатываться (компенсирующая транзакция), а клиент получать ok:false —
не paid:true.

Раньше process_successful_payment при Host 'None' not found / любом сбое
Remnawave молча return'ил без исключения и без возврата Balance, а
/api/create-payment считал оплату успешной.
"""
from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def test_pay_balance_rolls_back_when_key_provision_fails(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules.remnawave_api import RemnawaveAPIError
    from shop_bot.webapp import handlers

    user_id = 92001
    insert_user(database.DB_FILE, telegram_id=user_id, username="rollback", balance=500.0)
    token = issue_auth_token(user_id)
    database.update_setting("telegram_bot_token", "123456:FAKE_BOT_TOKEN_FOR_TESTS")
    database.create_plan("RollHost", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("RollHost")[0]["plan_id"]

    async def boom_create(*args, **kwargs):
        raise RemnawaveAPIError("Host 'None' not found")

    monkeypatch.setattr(
        "shop_bot.modules.remnawave_api.create_or_update_key_on_host",
        boom_create,
    )

    # Bot.send_message / session used inside process_successful_payment
    class _FakeMsg:
        async def edit_text(self, *a, **k):
            return None

        async def delete(self):
            return None

    class _FakeBot:
        def __init__(self, *a, **k):
            self.session = self

        async def send_message(self, *a, **k):
            return _FakeMsg()

        async def close(self):
            return None

        async def session_close(self):
            return None

    # aiogram Bot used both in webapp branch and inside process_successful_payment
    monkeypatch.setattr(handlers, "Bot", _FakeBot)
    monkeypatch.setattr("shop_bot.bot.handlers.Bot", _FakeBot)

    async def _noop_notify(*a, **k):
        return None

    monkeypatch.setattr("shop_bot.bot.handlers._handle_key_creation_failure", _noop_notify)
    monkeypatch.setattr("shop_bot.bot.handlers._notify_user_key_creation_error", _noop_notify)
    monkeypatch.setattr("shop_bot.bot.handlers._notify_admins_key_creation_error", _noop_notify)

    balance_before = float(database.get_user(user_id)["balance"])
    resp = _client().post(
        "/api/create-payment",
        json={
            "token": token,
            "payment_method": "pay_balance",
            "plan_id": plan_id,
            "host_name": None,  # triggers Host 'None' not found in real code; mocked boom anyway
            "action": "new",
        },
    )
    data = resp.json()
    assert data.get("ok") is False, data
    assert data.get("paid") is not True
    assert "возвращ" in (data.get("error") or "").lower()

    balance_after = float(database.get_user(user_id)["balance"])
    assert balance_after == balance_before


def test_pay_balance_rollback_is_idempotent(temp_db):
    from shop_bot.data_manager import database

    user_id = 92002
    insert_user(database.DB_FILE, telegram_id=user_id, username="idem", balance=100.0)
    pid = "balance-refund-idem-1"

    assert database.refund_payment_once(pid, user_id, 40.0, "Balance") is True
    assert float(database.get_user(user_id)["balance"]) == 140.0
    # second call must not credit again
    assert database.refund_payment_once(pid, user_id, 40.0, "Balance") is False
    assert float(database.get_user(user_id)["balance"]) == 140.0


def test_pay_referral_balance_rolls_back_when_provision_returns_false(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    user_id = 92003
    insert_user(database.DB_FILE, telegram_id=user_id, username="refroll", referral_balance=300.0)
    token = issue_auth_token(user_id)
    database.update_setting("telegram_bot_token", "123456:FAKE_BOT_TOKEN_FOR_TESTS")
    database.create_plan("RefRollHost", "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host("RefRollHost")[0]["plan_id"]

    async def fake_fail(bot, meta):
        # Simulate process_successful_payment already refunding then returning False
        database.refund_payment_once(
            meta["payment_id"], meta["user_id"], meta["price"], meta["payment_method"]
        )
        return False

    monkeypatch.setattr(handlers, "process_successful_payment", fake_fail)

    before = float(database.get_user(user_id)["referral_balance"])
    resp = _client().post(
        "/api/create-payment",
        json={
            "token": token,
            "payment_method": "pay_referral_balance",
            "plan_id": plan_id,
            "host_name": "RefRollHost",
            "action": "new",
        },
    )
    data = resp.json()
    assert data.get("ok") is False
    assert data.get("paid") is not True
    after = float(database.get_user(user_id)["referral_balance"])
    assert after == before
