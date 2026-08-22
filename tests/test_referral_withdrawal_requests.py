"""Жизненный цикл заявок на вывод реферальных средств."""
import sqlite3

from conftest import insert_user, temp_db  # noqa: F401


VALID_TRC20 = "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"


def _enable_withdraw(database, *, method="card"):
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_sbp_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("referral_withdraw_usdt_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    if method == "sbp":
        return database.add_referral_payout_method(62001, "sbp", "+79001234567", bank_name="Сбер")
    if method == "usdt":
        return database.add_referral_payout_method(62001, "usdt_trc20", VALID_TRC20)
    return database.add_referral_payout_method(62001, "card", "4111111111111111")


def test_validate_referral_payout_requisite(temp_db):
    from shop_bot.data_manager import database

    ok, msg = database.validate_referral_payout_requisite("sbp", "+7 900 123-45-67", "Сбер")
    assert ok, msg
    ok, msg = database.validate_referral_payout_requisite("sbp", "abc", "Сбер")
    assert ok is False
    assert "телефон" in msg.lower()
    ok, msg = database.validate_referral_payout_requisite("sbp", "+79001234567", None)
    assert ok is False
    assert "банк" in msg.lower()

    ok, msg = database.validate_referral_payout_requisite("card", "4111 1111 1111 1111")
    assert ok, msg
    ok, msg = database.validate_referral_payout_requisite("card", "1234")
    assert ok is False
    assert "16" in msg

    ok, msg = database.validate_referral_payout_requisite("usdt_trc20", VALID_TRC20)
    assert ok, msg
    ok, msg = database.validate_referral_payout_requisite("usdt_trc20", "not-a-wallet")
    assert ok is False


def test_add_payout_method_rejects_invalid_requisites(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=62010, username="badreq")
    ok, msg, method_id = database.add_referral_payout_method(62010, "card", "1")
    assert ok is False
    assert method_id is None
    assert database.list_referral_payout_methods(62010) == []


def test_create_rejects_disabled_method_type(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=62001, username="wd", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    ok, msg, method_id = database.add_referral_payout_method(62001, "card", "4111111111111111")
    assert ok and method_id, msg

    database.update_setting("referral_withdraw_card_enabled", "false")
    ok2, msg2, new_id = database.create_referral_withdrawal_request(62001, 150, method_id)
    assert ok2 is False
    assert new_id is None
    assert "недоступен" in (msg2 or "").lower()
    assert float(database.get_user(62001)["referral_balance"]) == 500.0
    assert database.list_referral_withdrawal_requests(user_id=62001) == []


def test_create_rejects_second_open_request(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=62001, username="wd", referral_balance=500.0)
    _enable_withdraw(database)
    ok, msg, method_id = database.add_referral_payout_method(62001, "card", "4111111111111111")
    assert ok and method_id, msg

    ok1, msg1, first_id = database.create_referral_withdrawal_request(62001, 150, method_id)
    assert ok1 and first_id, msg1
    ok2, msg2, second_id = database.create_referral_withdrawal_request(62001, 150, method_id)
    assert ok2 is False
    assert second_id is None
    assert "уже есть заявка" in (msg2 or "").lower()
    assert float(database.get_user(62001)["referral_balance"]) == 350.0
    assert len(database.list_referral_withdrawal_requests(user_id=62001)) == 1


def test_paid_creates_negative_transaction_and_blocks_repeat(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=62001, username="wd", referral_balance=500.0)
    ok, msg, method_id = database.add_referral_payout_method(62001, "card", "4111111111111111")
    assert ok and method_id, msg
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")

    ok, msg, request_id = database.create_referral_withdrawal_request(62001, 150, method_id)
    assert ok and request_id, msg
    assert float(database.get_user(62001)["referral_balance"]) == 350.0

    ok_paid, paid_msg, updated = database.update_referral_withdrawal_request_status(request_id, "paid")
    assert ok_paid, paid_msg
    assert updated["status"] == "paid"
    assert float(database.get_user(62001)["referral_balance"]) == 350.0

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT amount_rub, payment_method, payment_id FROM transactions WHERE payment_id = ?",
            (f"refpayout:{request_id}",),
        )
        row = cur.fetchone()
    assert row is not None
    assert float(row[0]) == -150.0
    assert row[1] == "referral_payout"

    ok_again, again_msg, _ = database.update_referral_withdrawal_request_status(request_id, "paid")
    assert ok_again is False
    assert "финальном" in (again_msg or "")
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM transactions WHERE payment_id = ?", (f"refpayout:{request_id}",))
        assert cur.fetchone()[0] == 1


def test_reject_refunds_balance_and_allows_new_request(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=62001, username="wd", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    ok, msg, method_id = database.add_referral_payout_method(62001, "card", "4111111111111111")
    assert ok and method_id, msg

    ok, msg, request_id = database.create_referral_withdrawal_request(62001, 150, method_id)
    assert ok and request_id, msg
    ok_rej, rej_msg, updated = database.update_referral_withdrawal_request_status(
        request_id, "rejected", reject_reason="неверные реквизиты"
    )
    assert ok_rej, rej_msg
    assert updated["status"] == "rejected"
    assert updated["reject_reason"] == "неверные реквизиты"
    assert float(database.get_user(62001)["referral_balance"]) == 500.0

    ok2, msg2, second_id = database.create_referral_withdrawal_request(62001, 120, method_id)
    assert ok2 and second_id, msg2
    assert float(database.get_user(62001)["referral_balance"]) == 380.0


def test_processing_then_paid(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=62001, username="wd", referral_balance=400.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    ok, msg, method_id = database.add_referral_payout_method(62001, "card", "4111111111111111")
    assert ok and method_id, msg
    ok, msg, request_id = database.create_referral_withdrawal_request(62001, 200, method_id)
    assert ok and request_id, msg

    ok_proc, proc_msg, updated = database.update_referral_withdrawal_request_status(request_id, "processing")
    assert ok_proc, proc_msg
    assert updated["status"] == "processing"
    assert float(database.get_user(62001)["referral_balance"]) == 200.0

    ok2, msg2, second_id = database.create_referral_withdrawal_request(62001, 100, method_id)
    assert ok2 is False
    assert second_id is None

    ok_paid, paid_msg, paid = database.update_referral_withdrawal_request_status(request_id, "paid")
    assert ok_paid, paid_msg
    assert paid["status"] == "paid"


def test_format_admin_notice_escapes_html(temp_db):
    from shop_bot.data_manager import database

    text = database.format_referral_withdrawal_admin_notice(
        request_id=7,
        user_id=123,
        username="bad<script>",
        amount=150,
        method_type="sbp",
        bank_name="Сбер",
        requisite_value="<b>phone</b>",
    )
    assert "#7" in text
    assert "123" in text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&lt;b&gt;phone&lt;/b&gt;" in text
    assert "СБП" in text


def test_webapp_notifies_all_admin_ids(temp_db, monkeypatch):
    from fastapi.testclient import TestClient
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=62020, username="wdweb", referral_balance=500.0)
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    database.update_setting("admin_telegram_id", "7001")
    database.update_setting("admin_telegram_ids", "7001,7002")
    ok, msg, method_id = database.add_referral_payout_method(62020, "card", "4111111111111111")
    assert ok and method_id, msg

    sent = []

    async def _fake_send(user_id, text, reply_markup=None, photo=None):
        sent.append((user_id, text))
        return True

    monkeypatch.setattr(handlers, "_send_telegram_message", _fake_send)
    handlers.TEMP_AUTH_TOKENS["test-ref-wd-notify"] = 62020
    client = TestClient(handlers.app)
    resp = client.post(
        "/api/referral/request-withdrawal",
        json={"token": "test-ref-wd-notify", "amount": 150, "method_id": method_id},
    )
    data = resp.json()
    assert data.get("ok") is True, data
    notified = {item[0] for item in sent}
    assert notified == {7001, 7002}
    assert all("Новая заявка на вывод" in item[1] for item in sent)
