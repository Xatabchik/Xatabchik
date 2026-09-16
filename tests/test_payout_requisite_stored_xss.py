"""Stored XSS в реквизитах/банке: ввод → БД → маска → DOM без innerHTML.

Старые вредоносные bank_name / requisite_value уже могут лежать в таблице.
Список API не отдаёт сырой HTML; фронт рисует textContent.
Токен авторизации в ассертах и ошибках не печатаем.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

OWNER_ID = 98001
OTHER_ID = 98002
XSS_BANK = "<img src=x onerror=alert(1)>"
XSS_REQ = "</span><script>alert(1)</script>"
XSS_JS = "');alert(1);//"


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _enable_withdraw(database) -> None:
    database.update_setting("referral_withdraw_enabled", "true")
    database.update_setting("referral_withdraw_sbp_enabled", "true")
    database.update_setting("referral_withdraw_card_enabled", "true")
    database.update_setting("referral_withdraw_usdt_enabled", "true")
    database.update_setting("minimum_withdrawal", "100")
    database.update_setting("referral_withdraw_sbp_banks", "Сбер,Тинькофф")


def _seed_owner(database, *, balance: float = 500.0) -> str:
    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="payxss", referral_balance=balance)
    return issue_auth_token(OWNER_ID)


def test_sanitize_and_mask_reject_xss(temp_db):
    from shop_bot.data_manager import database

    assert database.sanitize_payout_bank_name("Сбер") == "Сбер"
    assert database.sanitize_payout_bank_name(XSS_BANK) is None
    assert database.sanitize_payout_bank_name(XSS_JS) is None
    assert database.sanitize_payout_bank_name("`+alert(1)+`") is None
    assert database.sanitize_payout_bank_name("line1\nline2") is None
    assert database.mask_referral_requisite(XSS_REQ, "card") == "••••"
    assert database.mask_referral_requisite("<img src=x onerror=alert(1)>") == "••••"
    assert database.mask_referral_requisite("4111111111111111", "card") == "************1111"
    ok, msg = database.validate_referral_payout_requisite("card", "4111111111111111", XSS_BANK)
    assert ok is False
    assert "банк" in msg.lower()
    ok, msg = database.validate_referral_payout_requisite("sbp", "+79001234567", XSS_BANK)
    assert ok is False


def test_add_api_rejects_xss_bank_and_requisite(temp_db):
    from shop_bot.data_manager import database

    _enable_withdraw(database)
    token = _seed_owner(database)
    client = _client()

    bank_resp = client.post(
        "/api/referral/payout-methods/add",
        json={
            "token": token,
            "method_type": "sbp",
            "requisite_value": "+79001234567",
            "bank_name": XSS_BANK,
        },
    )
    bank_body = bank_resp.json()
    assert bank_body.get("ok") is False
    assert XSS_BANK not in str(bank_body)
    assert token not in str(bank_body)

    req_resp = client.post(
        "/api/referral/payout-methods/add",
        json={
            "token": token,
            "method_type": "card",
            "requisite_value": XSS_REQ,
            "bank_name": None,
        },
    )
    req_body = req_resp.json()
    assert req_body.get("ok") is False
    assert XSS_REQ not in str(req_body)
    assert database.list_referral_payout_methods(OWNER_ID) == []

    off_list = client.post(
        "/api/referral/payout-methods/add",
        json={
            "token": token,
            "method_type": "sbp",
            "requisite_value": "+79001234567",
            "bank_name": "ДругойБанк",
        },
    ).json()
    assert off_list.get("ok") is False
    assert "списк" in (off_list.get("error") or off_list.get("message") or "").lower()


def test_list_masks_old_stored_xss_and_omits_raw_value(temp_db):
    from shop_bot.data_manager import database

    _enable_withdraw(database)
    token = _seed_owner(database)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO referral_payout_methods (user_id, method_type, bank_name, requisite_value)
            VALUES (?, 'card', ?, ?)
            """,
            (OWNER_ID, XSS_BANK, XSS_REQ),
        )
        conn.commit()

    listed = _client().post("/api/referral/payout-methods/list", json={"token": token}).json()
    assert listed.get("ok") is True
    methods = listed.get("methods") or []
    assert len(methods) == 1
    item = methods[0]
    assert item.get("bank_name") is None
    assert item.get("requisite_masked") == "••••"
    assert "requisite_value" not in item
    dumped = str(listed)
    assert XSS_BANK not in dumped
    assert XSS_REQ not in dumped
    assert token not in dumped
    assert "<img" not in dumped
    assert "<script" not in dumped


def test_cannot_delete_or_withdraw_foreign_method(temp_db):
    from shop_bot.data_manager import database

    _enable_withdraw(database)
    owner_token = _seed_owner(database)
    insert_user(database.DB_FILE, telegram_id=OTHER_ID, username="otherpay", referral_balance=500.0)
    other_token = issue_auth_token(OTHER_ID)
    ok, msg, method_id = database.add_referral_payout_method(OWNER_ID, "card", "4111111111111111")
    assert ok and method_id, msg

    client = _client()
    deleted = client.post(
        "/api/referral/payout-methods/delete",
        json={"token": other_token, "method_id": method_id},
    ).json()
    assert deleted.get("ok") is False
    assert database.get_referral_payout_method(method_id, OWNER_ID) is not None

    stolen = client.post(
        "/api/referral/request-withdrawal",
        json={"token": other_token, "amount": 150, "method_id": method_id},
    ).json()
    assert stolen.get("ok") is False
    assert float(database.get_user(OTHER_ID)["referral_balance"]) == 500.0
    assert database.list_referral_withdrawal_requests(user_id=OTHER_ID) == []
    assert database.get_referral_payout_method(method_id, OWNER_ID) is not None
    assert owner_token not in str(deleted) + str(stolen)
    assert other_token not in str(deleted) + str(stolen)


def test_list_does_not_leak_other_users_methods(temp_db):
    from shop_bot.data_manager import database

    _enable_withdraw(database)
    owner_token = _seed_owner(database)
    insert_user(database.DB_FILE, telegram_id=OTHER_ID, username="otherpay")
    other_token = issue_auth_token(OTHER_ID)
    ok, msg, method_id = database.add_referral_payout_method(OWNER_ID, "card", "4111111111111111")
    assert ok and method_id, msg

    listed = _client().post("/api/referral/payout-methods/list", json={"token": other_token}).json()
    assert listed.get("ok") is True
    assert listed.get("methods") == []
    assert owner_token not in str(listed)


def test_frontend_payout_renderers_use_textcontent_not_innerhtml_interpolation():
    html = Path("src/shop_bot/webapp/app.html").read_text(encoding="utf-8")
    withdraw_fn = html[html.index("function _renderWithdrawForm"): html.index("function _selectWithdrawMethod")]
    assert "${_maskRequisite" not in withdraw_fn
    assert "${label}" not in withdraw_fn
    assert "m.bank_name" not in withdraw_fn or "textContent" in withdraw_fn
    assert "onclick=" not in withdraw_fn
    assert "replaceChildren" in withdraw_fn
    assert "addEventListener" in withdraw_fn
    assert "_payoutRequisiteText" in withdraw_fn

    load_fn = html[html.index("async function _loadReferralPayoutMethods"): html.index("async function _deletePayoutMethod")]
    assert "${_maskRequisite" not in load_fn
    assert "onclick=\"_deletePayoutMethod" not in load_fn
    assert "replaceChildren" in load_fn
    assert "addEventListener" in load_fn

    assert "if (!digits) return s;" not in html
    assert "return '••••';" in html
