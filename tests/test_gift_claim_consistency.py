"""Согласованность активации подарка и передачи ключа (БД, Mini App, pending action).

Подарок не должен «исчезать»: флаг активации в user_gifts и смена владельца в
vpn_keys фиксируются одной транзакцией, а успех возвращается только тогда,
когда ключ действительно у получателя.
"""
import sqlite3
import threading

from conftest import insert_user, issue_auth_token, make_telegram_init_data, temp_db, app_client  # noqa: F401
from gift_claim_harness import (
    assert_subscription_preserved,
    drop_trigger,
    gift_row,
    insert_full_gift,
    install_failing_trigger,
    key_row,
    keys_count,
)

SENDER = 8100
RECIPIENT = 8200
OTHER = 8300


def _activate(user_id, code):
    from shop_bot.webapp.web_router.gifts import _activate_gift_for_user

    return _activate_gift_for_user(user_id, code)


def _pending_token(app_client, code):
    r = app_client.get(f"/gift/{code}", follow_redirects=False)
    assert r.status_code in (302, 307), r.text
    return r.headers["location"].split("pending_token=")[1]


# 8. Ошибка SQL-обновления ключа — подарок не теряется
def test_key_update_failure_rolls_back_activation(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="SQLFAIL1")
    before = key_row(db.DB_FILE, key_id)
    install_failing_trigger(db.DB_FILE, "vpn_keys", "user_id")

    result = _activate(RECIPIENT, "SQLFAIL1")

    assert result["ok"] is False
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0
    assert gift_row(db.DB_FILE, gift_id)["activated_by_user_id"] is None
    assert key_row(db.DB_FILE, key_id) == before
    assert [g["gift_id"] for g in db.get_user_inactive_gifts(SENDER)] == [gift_id], "подарок остаётся у дарителя"
    assert db.get_user(RECIPIENT)["referred_by"] is None


def test_activation_flag_failure_rolls_back_key_transfer(temp_db):
    """Ключ уже переназначен внутри транзакции, но запись активации упала —
    откатывается и передача ключа."""
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="FLAGFAIL1")
    before = key_row(db.DB_FILE, key_id)
    install_failing_trigger(db.DB_FILE, "user_gifts", "is_activated")

    result = db.transfer_user_gift("FLAGFAIL1", RECIPIENT)

    assert result["ok"] is False
    assert result["status"] == "error"
    assert key_row(db.DB_FILE, key_id) == before
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0


def test_python_exception_during_transfer_rolls_back(temp_db, monkeypatch):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="PYFAIL1")
    before = key_row(db.DB_FILE, key_id)

    from shop_bot.data_manager.db import gifts as gifts_module

    def _boom():
        raise RuntimeError("clock failure")

    monkeypatch.setattr(gifts_module, "_now_str", _boom)
    result = db.transfer_user_gift("PYFAIL1", RECIPIENT)
    assert result["ok"] is False and result["status"] == "error"
    assert key_row(db.DB_FILE, key_id) == before
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0


# 9. Нет key_id или связанного ключа — нет ложного успеха
def test_gift_without_key_id_is_not_falsely_activated(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, _key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="NOKEYID1", link_key=False)

    result = _activate(RECIPIENT, "NOKEYID1")

    assert result["ok"] is False
    assert result["status"] == "key_missing"
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0
    assert keys_count(db.DB_FILE, RECIPIENT) == 0


def test_gift_with_deleted_key_is_not_falsely_activated(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="NOKEYROW1")
    with sqlite3.connect(db.DB_FILE) as conn:
        conn.execute("DELETE FROM vpn_keys WHERE key_id = ?", (key_id,))
        conn.commit()

    result = _activate(RECIPIENT, "NOKEYROW1")

    assert result["ok"] is False
    assert result["status"] == "key_missing"
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0


# 10. Повторное получение тем же пользователем
def test_repeat_activation_by_same_user_is_idempotent(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="IDEMP1")

    first = _activate(RECIPIENT, "IDEMP1")
    assert first["ok"] is True and first["status"] == "activated"
    snapshot_key = key_row(db.DB_FILE, key_id)
    snapshot_gift = gift_row(db.DB_FILE, gift_id)

    for _ in range(3):
        again = _activate(RECIPIENT, "IDEMP1")
        assert again["ok"] is True
        assert again["status"] == "already_activated"

    assert key_row(db.DB_FILE, key_id) == snapshot_key
    assert gift_row(db.DB_FILE, gift_id) == snapshot_gift
    assert keys_count(db.DB_FILE, RECIPIENT) == 1


# 11. Конкурентное получение двумя пользователями
def test_concurrent_claims_by_two_users_give_key_to_exactly_one(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    insert_user(db.DB_FILE, OTHER, "other")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="RACE2")

    barrier = threading.Barrier(8)
    results = []

    def _claim(uid):
        barrier.wait()
        results.append((uid, db.transfer_user_gift("RACE2", uid)))

    threads = [threading.Thread(target=_claim, args=(RECIPIENT if i % 2 else OTHER,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    fresh = [(uid, r) for uid, r in results if r["status"] == "activated"]
    assert len(fresh) == 1, results
    winner = fresh[0][0]
    loser = OTHER if winner == RECIPIENT else RECIPIENT
    assert key_row(db.DB_FILE, key_id)["user_id"] == winner
    assert gift_row(db.DB_FILE, gift_id)["activated_by_user_id"] == winner
    for uid, r in results:
        if uid == loser:
            assert r["ok"] is False and r["status"] == "already_activated_by_other"
        elif r is not fresh[0][1]:
            assert r["ok"] is True and r["status"] == "already_activated"
    assert keys_count(db.DB_FILE, loser) == 0


# 12. Истёкший, несуществующий и полученный другим
def test_expired_unknown_and_foreign_gift_statuses(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    exp_gift, exp_key = insert_full_gift(
        db.DB_FILE, from_user_id=SENDER, gift_code="EXP2", expires_at="2000-01-01T00:00:00"
    )
    insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="FOREIGN2")
    assert _activate(OTHER, "FOREIGN2")["status"] == "activated"

    expired = _activate(RECIPIENT, "EXP2")
    unknown = _activate(RECIPIENT, "NO-SUCH-GIFT")
    foreign = _activate(RECIPIENT, "FOREIGN2")

    assert (expired["ok"], expired["status"]) == (False, "expired")
    assert (unknown["ok"], unknown["status"]) == (False, "not_found")
    assert (foreign["ok"], foreign["status"]) == (False, "already_activated")
    assert gift_row(db.DB_FILE, exp_gift)["is_activated"] == 0
    assert key_row(db.DB_FILE, exp_key)["user_id"] == SENDER
    assert keys_count(db.DB_FILE, RECIPIENT) == 0


# 13. Старое неконсистентное состояние
def _make_legacy_stuck(db_path, gift_id, activated_by):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE user_gifts SET is_activated = 1, activated_by_user_id = ?, activated_at = '2026-01-01 00:00:00' "
            "WHERE gift_id = ?",
            (activated_by, gift_id),
        )
        conn.commit()


def test_legacy_activated_but_not_transferred_is_not_reported_as_success(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="LEGACY1")
    before = key_row(db.DB_FILE, key_id)
    _make_legacy_stuck(db.DB_FILE, gift_id, RECIPIENT)

    result = _activate(RECIPIENT, "LEGACY1")

    # Ключ ни разу не уходил другому: передаём его тому, на кого записана активация.
    assert result["ok"] is True
    assert result["status"] == "recovered"
    key = key_row(db.DB_FILE, key_id)
    assert key["user_id"] == RECIPIENT and (key["tag"] or "") == ""
    assert_subscription_preserved(before, key)

    again = _activate(RECIPIENT, "LEGACY1")
    assert (again["ok"], again["status"]) == (True, "already_activated")


def test_legacy_stuck_gift_is_not_given_to_another_user(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="LEGACY2")
    _make_legacy_stuck(db.DB_FILE, gift_id, RECIPIENT)

    result = _activate(OTHER, "LEGACY2")
    assert result["ok"] is False
    assert key_row(db.DB_FILE, key_id)["user_id"] == SENDER


def test_legacy_record_with_key_owned_by_third_party_needs_support(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="LEGACY3")
    _make_legacy_stuck(db.DB_FILE, gift_id, RECIPIENT)
    with sqlite3.connect(db.DB_FILE) as conn:
        conn.execute("UPDATE vpn_keys SET user_id = ?, tag = '' WHERE key_id = ?", (OTHER, key_id))
        conn.commit()

    result = _activate(RECIPIENT, "LEGACY3")
    assert result["ok"] is False
    assert result["status"] == "inconsistent"
    assert key_row(db.DB_FILE, key_id)["user_id"] == OTHER, "чужой ключ не перехватывается"


def test_stuck_gift_diagnostics_and_targeted_repair(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    ok_gift, _ = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="DIAG-OK")
    assert _activate(OTHER, "DIAG-OK")["status"] == "activated"
    stuck_gift, stuck_key = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="DIAG-STUCK")
    _make_legacy_stuck(db.DB_FILE, stuck_gift, RECIPIENT)
    foreign_gift, foreign_key = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="DIAG-FOREIGN")
    _make_legacy_stuck(db.DB_FILE, foreign_gift, RECIPIENT)
    with sqlite3.connect(db.DB_FILE) as conn:
        conn.execute("UPDATE vpn_keys SET user_id = ?, tag = '' WHERE key_id = ?", (OTHER, foreign_key))
        conn.commit()

    report = {r["gift_id"]: r for r in db.find_stuck_gift_activations()}
    assert ok_gift not in report
    assert report[stuck_gift]["problem"] == "not_transferred"
    assert report[stuck_gift]["recoverable"] is True
    assert report[foreign_gift]["problem"] == "owner_mismatch"
    assert report[foreign_gift]["recoverable"] is False
    assert all("gift_code" not in r for r in report.values()), "полные коды в отчёт не попадают"

    assert db.repair_stuck_gift_activation(foreign_gift)["ok"] is False
    assert key_row(db.DB_FILE, foreign_key)["user_id"] == OTHER

    repaired = db.repair_stuck_gift_activation(stuck_gift)
    assert repaired["ok"] is True
    assert key_row(db.DB_FILE, stuck_key)["user_id"] == RECIPIENT
    assert stuck_gift not in {r["gift_id"] for r in db.find_stuck_gift_activations()}
    # Флаги активации ни у одного подарка не сбрасывались.
    assert gift_row(db.DB_FILE, foreign_gift)["is_activated"] == 1


# 15. UUID, ссылка, срок, лимиты и email ключа сохраняются
def test_transfer_preserves_subscription_identity(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="KEEP1")
    before = key_row(db.DB_FILE, key_id)

    assert _activate(RECIPIENT, "KEEP1")["status"] == "activated"

    after = key_row(db.DB_FILE, key_id)
    assert_subscription_preserved(before, after)
    assert after["user_id"] == RECIPIENT
    assert keys_count(db.DB_FILE, RECIPIENT) == 1
    assert [k["key_id"] for k in db.get_user_keys(RECIPIENT)] == [key_id]
    assert db.get_user_inactive_gifts(SENDER) == []


# 16. Реферальная привязка и бонусы не дублируются
def test_referral_bound_once_after_confirmed_transfer(temp_db):
    db = temp_db
    db.update_setting("referral_reward_type", "fixed_start_referrer")
    db.update_setting("referral_on_start_referrer_amount", "25")
    db.register_user_if_not_exists(SENDER, "sender", None)
    db.register_user_if_not_exists(RECIPIENT, "fresh", None)
    insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="REF1")
    insert_full_gift(db.DB_FILE, from_user_id=OTHER, gift_code="REF2")
    db.register_user_if_not_exists(OTHER, "other", None)

    assert _activate(RECIPIENT, "REF1")["status"] == "activated"
    assert db.get_user(RECIPIENT)["referred_by"] == SENDER
    sender_after = db.get_user(SENDER)

    for _ in range(3):
        _activate(RECIPIENT, "REF1")
    # Второй подарок от другого дарителя не перепривязывает реферала.
    assert _activate(RECIPIENT, "REF2")["status"] == "activated"

    assert db.get_user(RECIPIENT)["referred_by"] == SENDER
    sender_final = db.get_user(SENDER)
    assert sender_final["referral_balance"] == sender_after["referral_balance"]
    assert sender_final["referral_balance_all"] == sender_after["referral_balance_all"]


# 7. Mini App: /gift/<code> без авторизации → вход → получение без второго открытия
def test_pending_action_is_not_consumed_by_failed_transfer(temp_db, app_client):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="WEBFAIL1")
    before = key_row(db.DB_FILE, key_id)
    pending_token = _pending_token(app_client, "WEBFAIL1")

    install_failing_trigger(db.DB_FILE, "vpn_keys", "user_id")
    init_data = make_telegram_init_data(RECIPIENT)
    first = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "init_data": init_data},
    ).json()
    assert first["ok"] is False
    assert first.get("retryable") is True
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0
    assert db.get_pending_action(pending_token)["consumed_at"] is None

    # Временная ошибка устранена — тот же pending_token (тот же переход) довершает выдачу.
    drop_trigger(db.DB_FILE)
    second = app_client.post(
        "/api/webapp/pending-actions/complete",
        json={"pending_token": pending_token, "init_data": init_data},
    ).json()
    assert second["ok"] is True
    assert second["status"] == "activated"
    key = key_row(db.DB_FILE, key_id)
    assert key["user_id"] == RECIPIENT
    assert_subscription_preserved(before, key)
    pending = db.get_pending_action(pending_token)
    assert pending["consumed_by_user_id"] == RECIPIENT
    assert pending["result_status"] == "activated"


def test_pending_action_unauthenticated_then_login_claims_once(temp_db, app_client):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="WEBLOGIN1")

    pending_token = _pending_token(app_client, "WEBLOGIN1")
    # Неавторизованный запрос ничего не меняет и не расходует ссылку.
    anon = app_client.post("/api/webapp/pending-actions/complete", json={"pending_token": pending_token}).json()
    assert anon["error"] == "unauthorized"
    assert db.get_pending_action(pending_token)["consumed_at"] is None

    token = issue_auth_token(RECIPIENT)
    done = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": token}
    ).json()
    assert done["ok"] is True and done["status"] == "activated"
    assert key_row(db.DB_FILE, key_id)["user_id"] == RECIPIENT

    again = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": token}
    ).json()
    assert again["ok"] is True and again.get("already_completed") is True
    assert keys_count(db.DB_FILE, RECIPIENT) == 1


def test_legacy_consumed_pending_with_error_result_is_retried(temp_db, app_client):
    """Старая логика расходовала ссылку ДО передачи и потом отвечала успехом
    по result_status='error'. Теперь фактическое состояние перепроверяется."""
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="WEBLEGACY1")
    pending_token = _pending_token(app_client, "WEBLEGACY1")
    assert db.claim_pending_action(pending_token, RECIPIENT)
    db.set_pending_action_result(pending_token, "error")
    _make_legacy_stuck(db.DB_FILE, gift_id, RECIPIENT)

    token = issue_auth_token(RECIPIENT)
    body = app_client.post(
        "/api/webapp/pending-actions/complete", json={"pending_token": pending_token, "token": token}
    ).json()
    assert body["ok"] is True
    assert key_row(db.DB_FILE, key_id)["user_id"] == RECIPIENT


def test_api_gift_activate_reports_failure_honestly(temp_db, app_client):
    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="APIFAIL1")
    install_failing_trigger(db.DB_FILE, "vpn_keys", "user_id")
    token = issue_auth_token(SENDER)

    body = app_client.post("/api/gift/activate", json={"gift_code": "APIFAIL1", "token": token}).json()
    assert body["ok"] is False
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 0
    assert key_row(db.DB_FILE, key_id)["tag"] == "user_gift"


def test_gift_claim_logs_do_not_contain_full_code(temp_db, caplog):
    import logging

    db = temp_db
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "recipient")
    insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="SECRETCODE123")
    with caplog.at_level(logging.DEBUG):
        _activate(RECIPIENT, "SECRETCODE123")
        _activate(RECIPIENT, "SECRETCODE123")
        _activate(OTHER, "SECRETCODE123")
    assert "SECRETCODE123" not in caplog.text
    assert "https://sub.example/SECRETCODE123" not in caplog.text
    assert "gift_claim" in caplog.text
