"""Привязка ID платежа ЮKassa к локальному заказу (pending_transactions.metadata).

В расследованном платеже Web App ID провайдера не сохранялся: в pending его не
было, и сверить заказ с кабинетом ЮKassa можно было только вручную. Helper
дописывает ID один раз, атомарно и без перезаписи уже сохранённого значения;
решение webhook (`decide_yookassa_link`) вынесено из webhook_server/app.py,
чтобы проверять его без импорта этого модуля.
"""
from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401
from conftest import host_of_plan as _host_of_plan  # noqa: E402

PID = "local-order-1"
YK_A = "2f1a0b3c-000f-5000-9000-1edaf29243f2"
YK_B = "3e2b1c4d-000f-5000-a000-2fdbe30354a3"


_KEEP = object()


def _make_pending(database, pid=PID, metadata=None, status="pending", raw_metadata=_KEEP):
    database.create_payload_pending(pid, 777, 199.0, metadata if metadata is not None else {"action": "new", "price": 199.0})
    with sqlite3.connect(database.DB_FILE) as conn:
        if raw_metadata is not _KEEP:
            conn.execute("UPDATE pending_transactions SET metadata = ? WHERE payment_id = ?", (raw_metadata, pid))
        conn.execute(
            "UPDATE pending_transactions SET status = ?, updated_at = '2026-01-01 10:00:00' WHERE payment_id = ?",
            (status, pid),
        )


def _row(database, pid=PID):
    with sqlite3.connect(database.DB_FILE) as conn:
        return conn.execute(
            "SELECT status, updated_at, amount_rub, metadata FROM pending_transactions WHERE payment_id = ?",
            (pid,),
        ).fetchone()


def _alerts(database, kind="payment_provider_id_conflict"):
    with sqlite3.connect(database.DB_FILE) as conn:
        return conn.execute(
            "SELECT text, payment_id FROM ops_alerts WHERE kind = ? ORDER BY id", (kind,)
        ).fetchall()


# --- проверка формата -------------------------------------------------------


@pytest.mark.parametrize("value", [YK_A, YK_A.upper()])
def test_valid_yookassa_id(temp_db, value):
    assert temp_db.is_valid_yookassa_payment_id(value) is True


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        123,
        YK_A + "\n",
        "\n" + YK_A,
        YK_A[:-1],
        YK_A + "0",
        YK_A.replace("-", ""),
        "2f1a0b3c-000f-5000-9000-1edaf29243fz",
        "x' OR '1'='1",
        "a" * 10000,
        "2f1a0b3c-000f-5000-9000-1edaf29\r\n243f",
    ],
)
def test_invalid_yookassa_id(temp_db, value):
    assert temp_db.is_valid_yookassa_payment_id(value) is False


# --- helper: исходы ---------------------------------------------------------


def test_written_then_same(temp_db):
    _make_pending(temp_db)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A) == ("written", YK_A)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A) == ("same", YK_A)
    assert json.loads(_row(temp_db)[3])["yookassa_payment_id"] == YK_A


def test_conflict_never_overwrites(temp_db):
    _make_pending(temp_db)
    temp_db.link_pending_yookassa_payment_id(PID, YK_A)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_B) == ("conflict", YK_A)
    assert json.loads(_row(temp_db)[3])["yookassa_payment_id"] == YK_A


def test_no_record(temp_db):
    assert temp_db.link_pending_yookassa_payment_id("missing", YK_A) == ("no_record", None)


def test_status_updated_at_amount_and_other_keys_untouched(temp_db):
    _make_pending(temp_db, metadata={"action": "gift", "price": 199.0, "promo_code": "X1"})
    before = _row(temp_db)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A)[0] == "written"
    after = _row(temp_db)
    assert after[:3] == before[:3]
    meta_before = json.loads(before[3])
    meta_after = json.loads(after[3])
    assert meta_after.pop("yookassa_payment_id") == YK_A
    assert meta_after == meta_before


def test_paid_row_also_gets_id(temp_db):
    _make_pending(temp_db, status="paid")
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A)[0] == "written"
    assert _row(temp_db)[0] == "paid"


@pytest.mark.parametrize("raw", [None, ""])
def test_empty_or_null_metadata(temp_db, raw):
    _make_pending(temp_db, raw_metadata=raw)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A)[0] == "written"
    assert json.loads(_row(temp_db)[3]) == {"yookassa_payment_id": YK_A}


@pytest.mark.parametrize("raw", ["{not json", "[]", '"text"', "5"])
def test_broken_or_non_object_metadata_is_error_and_untouched(temp_db, raw):
    _make_pending(temp_db, raw_metadata=raw)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A) == ("error", None)
    assert _row(temp_db)[3] == raw


@pytest.mark.parametrize("stored", [None, "", 5])
def test_existing_null_empty_or_non_string_is_conflict(temp_db, stored):
    _make_pending(temp_db, raw_metadata=json.dumps({"action": "new", "yookassa_payment_id": stored}))
    result, _ = temp_db.link_pending_yookassa_payment_id(PID, YK_A)
    assert result == "conflict"
    assert json.loads(_row(temp_db)[3])["yookassa_payment_id"] == stored


@pytest.mark.parametrize(
    "payment_id,provider_id",
    [
        (PID, "x'); DROP TABLE pending_transactions; --"),
        (PID, "a" * 10000),
        (PID, YK_A + "\n"),
        (PID, "line1\nline2"),
        (PID, None),
        ("", YK_A),
        ("   ", YK_A),
        (None, YK_A),
        (12345, YK_A),
    ],
)
def test_invalid_input_does_not_touch_db(temp_db, monkeypatch, payment_id, provider_id):
    def _boom():
        raise AssertionError("БД не должна открываться при invalid")

    monkeypatch.setattr(temp_db, "_connect_pending_db", _boom)
    assert temp_db.link_pending_yookassa_payment_id(payment_id, provider_id) == ("invalid", None)


def test_sql_like_payment_id_is_parameterized(temp_db):
    pid = "x' OR '1'='1"
    _make_pending(temp_db)
    assert temp_db.link_pending_yookassa_payment_id(pid, YK_A) == ("no_record", None)
    assert "yookassa_payment_id" not in json.loads(_row(temp_db)[3])


def test_db_error_returns_error(temp_db, monkeypatch):
    def _broken():
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(temp_db, "_connect_pending_db", _broken)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A) == ("error", None)


def test_non_sqlite_error_returns_error(temp_db, monkeypatch):
    def _broken():
        raise RuntimeError("unexpected")

    monkeypatch.setattr(temp_db, "_connect_pending_db", _broken)
    assert temp_db.link_pending_yookassa_payment_id(PID, YK_A) == ("error", None)


def test_two_threads_with_different_ids(temp_db):
    _make_pending(temp_db)
    barrier = threading.Barrier(2)
    results = {}

    def _run(name, value):
        barrier.wait()
        results[name] = temp_db.link_pending_yookassa_payment_id(PID, value)[0]

    threads = [threading.Thread(target=_run, args=(n, v)) for n, v in (("a", YK_A), ("b", YK_B))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results.values()) == ["conflict", "written"]
    winner = YK_A if results["a"] == "written" else YK_B
    assert json.loads(_row(temp_db)[3])["yookassa_payment_id"] == winner


def test_log_has_ids_but_not_metadata(temp_db, caplog):
    _make_pending(temp_db, metadata={"action": "new", "price": 199.0, "customer_email": "secret@example.com"})
    with caplog.at_level("INFO"):
        temp_db.link_pending_yookassa_payment_id(PID, YK_A)
        temp_db.link_pending_yookassa_payment_id(PID, YK_B)
    text = caplog.text
    assert PID in text and YK_A in text
    assert "secret@example.com" not in text


# --- цепочка до итоговой записи transactions --------------------------------


def test_id_reaches_final_transaction_without_clobbering(temp_db):
    _make_pending(temp_db, metadata={"action": "new", "price": 199.0, "promo_code": "P1", "months": 1})
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        tx_id_before = conn.execute(
            "SELECT transaction_id FROM transactions WHERE payment_id = ?", (PID,)
        ).fetchone()[0]
    temp_db.link_pending_yookassa_payment_id(PID, YK_A)
    metadata = temp_db.find_and_complete_pending_transaction(PID)
    assert metadata["yookassa_payment_id"] == YK_A

    temp_db.log_transaction(
        username="u",
        transaction_id=None,
        payment_id=PID,
        user_id=777,
        status="paid",
        amount_rub=199.0,
        amount_currency=None,
        currency_name=None,
        payment_method="YooKassa",
        metadata=json.dumps({"action": "new", "key_id": 5, "yookassa_payment_id": metadata["yookassa_payment_id"]}),
    )
    with sqlite3.connect(temp_db.DB_FILE) as conn:
        rows = conn.execute(
            "SELECT transaction_id, status, metadata FROM transactions WHERE payment_id = ?", (PID,)
        ).fetchall()
    assert len(rows) == 1
    tx_id, status, meta_raw = rows[0]
    meta = json.loads(meta_raw)
    assert status == "paid"
    assert tx_id == tx_id_before
    assert meta["yookassa_payment_id"] == YK_A
    assert meta["promo_code"] == "P1" and meta["months"] == 1 and meta["key_id"] == 5


# --- решение webhook --------------------------------------------------------


def _decide(pid=PID, requested=YK_A, api=YK_A, pending=True):
    from shop_bot.data_manager.yookassa_link import decide_yookassa_link

    return decide_yookassa_link(pid, requested, api, pending)


def test_decide_no_pending_proceeds_without_link(temp_db, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("привязка не должна вызываться")

    monkeypatch.setattr(temp_db, "link_pending_yookassa_payment_id", _boom)
    d = _decide(pending=False)
    assert (d.action, d.set_provider_id) == ("proceed", None)


@pytest.mark.parametrize("api", [None, "", YK_B])
def test_decide_api_id_mismatch_proceeds_without_link(temp_db, api):
    _make_pending(temp_db)
    d = _decide(api=api)
    assert (d.action, d.set_provider_id) == ("proceed", None)
    assert "yookassa_payment_id" not in json.loads(_row(temp_db)[3])


def test_decide_written_and_same(temp_db):
    _make_pending(temp_db)
    assert (_decide().action, _decide().set_provider_id) == ("proceed", YK_A)
    assert json.loads(_row(temp_db)[3])["yookassa_payment_id"] == YK_A


@pytest.mark.parametrize(
    "result,expected_id",
    [("written", YK_A), ("same", YK_A), ("error", YK_A), ("invalid", None), ("no_record", None)],
)
def test_decide_outcome_mapping(temp_db, monkeypatch, result, expected_id):
    monkeypatch.setattr(temp_db, "link_pending_yookassa_payment_id", lambda pid, prov: (result, None))
    d = _decide()
    assert (d.action, d.set_provider_id) == ("proceed", expected_id)


def test_decide_conflict_blocks_writes_alert_and_dedupes(temp_db):
    _make_pending(temp_db)
    temp_db.link_pending_yookassa_payment_id(PID, YK_B)
    d1 = _decide()
    d2 = _decide()
    assert (d1.action, d1.set_provider_id) == ("block", None)
    assert (d2.action, d2.set_provider_id) == ("block", None)
    alerts = _alerts(temp_db)
    assert len(alerts) == 1
    text, alert_pid = alerts[0]
    assert alert_pid == PID
    assert PID in text and YK_A in text and YK_B in text
    assert "кабинете ЮKassa" in text
    assert json.loads(_row(temp_db)[3])["yookassa_payment_id"] == YK_B
    assert _row(temp_db)[0] == "pending"


def test_decide_conflict_alert_failure_means_retry(temp_db, monkeypatch):
    from shop_bot.data_manager import key_write_guard

    _make_pending(temp_db)
    temp_db.link_pending_yookassa_payment_id(PID, YK_B)

    def _broken(*a, **k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(key_write_guard, "add_ops_alert", _broken)
    d = _decide()
    assert (d.action, d.set_provider_id) == ("retry", None)


@pytest.mark.parametrize("stored_raw", ["<b>not-uuid</b>", None])
def test_conflict_alert_hides_non_uuid_stored_value(temp_db, stored_raw):
    _make_pending(temp_db, raw_metadata=json.dumps({"action": "new", "yookassa_payment_id": stored_raw}))
    d = _decide()
    assert d.action == "block"
    text = _alerts(temp_db)[0][0]
    assert "нестандартное значение" in text
    assert "not-uuid" not in text
    assert "None" not in text and "null" not in text


def test_conflict_alert_escapes_html(temp_db):
    pid = "ord<x>&y"
    _make_pending(temp_db, pid=pid)
    temp_db.link_pending_yookassa_payment_id(pid, YK_B)
    d = _decide(pid=pid)
    assert d.action == "block"
    text = _alerts(temp_db)[0][0]
    assert "ord&lt;x&gt;&amp;y" in text
    assert "<x>" not in text


def test_conflict_alert_kind_is_not_suppressed_as_payment_stuck(temp_db, monkeypatch):
    from shop_bot.data_manager import key_write_guard, reconciler

    _make_pending(temp_db)
    temp_db.link_pending_yookassa_payment_id(PID, YK_B)
    _decide()

    def _boom(pid):
        raise AssertionError("проверка подавления payment_stuck не должна вызываться")

    monkeypatch.setattr(reconciler, "_payment_delivery_confirmed", _boom)
    sent = []

    class _Bot:
        async def send_message(self, chat_id, text, **kw):
            sent.append(text)

    import asyncio

    monkeypatch.setattr("shop_bot.data_manager.remnawave_repository.get_admin_ids", lambda: {1})
    asyncio.run(reconciler.send_pending_alerts(_Bot()))
    assert any(YK_A in t for t in sent)
    assert key_write_guard.fetch_unsent_alerts() == []


# --- Web App: ветка pay_yookassa -------------------------------------------


class _FakeConfirmation:
    def __init__(self, url):
        self.confirmation_url = url


class _FakePaymentObject:
    def __init__(self, provider_id):
        self.id = provider_id
        self.confirmation = _FakeConfirmation("https://yookassa.test/confirm")


def _setup_webapp(database, monkeypatch, telegram_id, provider_id=YK_A):
    from shop_bot.webapp import handlers

    insert_user(database.DB_FILE, telegram_id=telegram_id, username=f"u{telegram_id}")
    token = issue_auth_token(telegram_id)
    database.update_setting("yookassa_shop_id", "test-shop-id")
    database.update_setting("yookassa_secret_key", "test-secret-key")
    host = f"LinkHost{telegram_id}"
    database.create_plan(host, "1 месяц", 1, 100.0)
    database.create_host(host, "https://panel.test", "user", "pass", 1)
    plan_id = database.get_plans_for_host(host)[0]["plan_id"]
    created = []

    class _FakeYookassaPayment:
        @staticmethod
        def create(payload, idempotence_key=None):
            created.append(payload)
            return _FakePaymentObject(provider_id)

    monkeypatch.setattr(handlers, "YookassaPayment", _FakeYookassaPayment)

    async def _fake_send(*args, **kwargs):
        return True

    monkeypatch.setattr(handlers, "_send_telegram_message", _fake_send)
    return handlers, token, plan_id, created


def _buy(handlers, token, plan_id, user_id):
    from fastapi.testclient import TestClient

    client = TestClient(handlers.app)
    return client.post("/api/create-payment", json={
        "user_id": user_id,
        "token": token,
        "payment_method": "pay_yookassa",
        "plan_id": plan_id,
        "host_name": _host_of_plan(plan_id),
        "action": "new",
    }).json()


def test_webapp_saves_provider_id(temp_db, monkeypatch):
    handlers, token, plan_id, created = _setup_webapp(temp_db, monkeypatch, 44001)
    data = _buy(handlers, token, plan_id, 44001)
    assert data["ok"] is True and data["payment_url"] == "https://yookassa.test/confirm"
    assert len(created) == 1
    meta = temp_db.get_pending_metadata(data["payment_id"])
    assert meta["yookassa_payment_id"] == YK_A
    assert meta["action"] == "new"


@pytest.mark.parametrize("mode", ["conflict", "error", "invalid", "raises"])
def test_webapp_always_returns_link_on_link_failure(temp_db, monkeypatch, mode):
    from shop_bot.webapp.web_router import payments_create

    handlers, token, plan_id, created = _setup_webapp(temp_db, monkeypatch, 44002)

    def _fake_link(pid, prov):
        if mode == "raises":
            raise RuntimeError("boom")
        return mode, None

    monkeypatch.setattr(payments_create, "link_pending_yookassa_payment_id", _fake_link)
    data = _buy(handlers, token, plan_id, 44002)
    assert data == {
        "ok": True,
        "payment_url": "https://yookassa.test/confirm",
        "payment_id": data["payment_id"],
        "message": "Счёт создан",
    }
    assert len(created) == 1


def test_webapp_non_uuid_provider_id_still_returns_link(temp_db, monkeypatch):
    handlers, token, plan_id, created = _setup_webapp(temp_db, monkeypatch, 44003, provider_id="yoo-test-payment-id")
    data = _buy(handlers, token, plan_id, 44003)
    assert data["ok"] is True and data["payment_url"] == "https://yookassa.test/confirm"
    assert "yookassa_payment_id" not in temp_db.get_pending_metadata(data["payment_id"])


def test_webhook_before_webapp_link_gives_same(temp_db, monkeypatch):
    """Webhook успел привязать ID раньше, чем Web App получил ответ create()."""
    from shop_bot.webapp.web_router import payments_create

    handlers, token, plan_id, created = _setup_webapp(temp_db, monkeypatch, 44004)
    results = []
    real_link = payments_create.link_pending_yookassa_payment_id

    def _webhook_first(pid, prov):
        real_link(pid, prov)
        res = real_link(pid, prov)
        results.append(res[0])
        return res

    monkeypatch.setattr(payments_create, "link_pending_yookassa_payment_id", _webhook_first)
    data = _buy(handlers, token, plan_id, 44004)
    assert data["ok"] is True
    assert results == ["same"]
    meta = temp_db.get_pending_metadata(data["payment_id"])
    assert meta["yookassa_payment_id"] == YK_A and meta["action"] == "new"
