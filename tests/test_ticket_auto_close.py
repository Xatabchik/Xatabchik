"""Автозакрытие тикета, если после ответа админа пользователь молчит N дней."""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timedelta

import pytest

from conftest import temp_db  # noqa: F401

NOW = datetime(2026, 8, 31, 12, 0, 0)


@pytest.fixture(autouse=True)
def _reset_idle_close_flag():
    from shop_bot.support_bot import idle_close

    idle_close._idle_close_running = False
    yield
    idle_close._idle_close_running = False


def _ticket_with_messages(database, user_id: int, senders: list[str]) -> tuple[int, list[int]]:
    tid = database.create_support_ticket(user_id, "Тема")
    ids = []
    for sender in senders:
        mid = database.add_support_message(tid, sender, f"от {sender}")
        ids.append(mid)
    return tid, ids


def _created_at(database, message_id: int, when: datetime) -> None:
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE support_messages SET created_at = ? WHERE message_id = ?",
            (when.strftime("%Y-%m-%d %H:%M:%S"), int(message_id)),
        )
        conn.commit()


def test_parse_ticket_auto_close_days():
    from shop_bot.data_manager.database import parse_ticket_auto_close_days

    assert parse_ticket_auto_close_days(None) == 0
    assert parse_ticket_auto_close_days("") == 0
    assert parse_ticket_auto_close_days("abc") == 0
    assert parse_ticket_auto_close_days("-3") == 0
    assert parse_ticket_auto_close_days("0") == 0
    assert parse_ticket_auto_close_days("7") == 7
    assert parse_ticket_auto_close_days("9999") == 365


def test_idle_close_disabled_when_days_zero(temp_db):
    tid, mids = _ticket_with_messages(temp_db, 700001, ["user", "admin"])
    _created_at(temp_db, mids[-1], NOW - timedelta(days=30))
    temp_db.update_setting("ticket_auto_close_days", "0")
    result = temp_db.auto_close_idle_admin_tickets(0, now=NOW)
    assert result["count"] == 0
    assert temp_db.get_ticket(tid)["status"] == "open"


def test_does_not_close_when_last_message_is_from_user(temp_db):
    tid, mids = _ticket_with_messages(temp_db, 700002, ["user", "admin", "user"])
    _created_at(temp_db, mids[1], NOW - timedelta(days=10))
    _created_at(temp_db, mids[2], NOW - timedelta(days=9))
    found = temp_db.find_open_tickets_idle_after_admin(7, now=NOW)
    assert found == []
    result = temp_db.auto_close_idle_admin_tickets(7, now=NOW)
    assert result["count"] == 0
    assert temp_db.get_ticket(tid)["status"] == "open"


def test_does_not_close_when_last_message_is_note(temp_db):
    tid, mids = _ticket_with_messages(temp_db, 700003, ["user", "admin", "note"])
    _created_at(temp_db, mids[1], NOW - timedelta(days=10))
    _created_at(temp_db, mids[2], NOW - timedelta(days=9))
    assert temp_db.find_open_tickets_idle_after_admin(7, now=NOW) == []
    assert temp_db.get_ticket(tid)["status"] == "open"


def test_does_not_close_recent_admin_reply(temp_db):
    tid, mids = _ticket_with_messages(temp_db, 700004, ["user", "admin"])
    _created_at(temp_db, mids[-1], NOW - timedelta(days=2))
    found = temp_db.find_open_tickets_idle_after_admin(7, now=NOW)
    assert found == []
    assert temp_db.get_ticket(tid)["status"] == "open"


def test_closes_when_admin_replied_and_user_silent(temp_db):
    tid, mids = _ticket_with_messages(temp_db, 700005, ["user", "admin"])
    _created_at(temp_db, mids[-1], NOW - timedelta(days=7, seconds=1))
    found = temp_db.find_open_tickets_idle_after_admin(7, now=NOW)
    assert [r["ticket_id"] for r in found] == [tid]
    result = temp_db.auto_close_idle_admin_tickets(7, now=NOW)
    assert result["count"] == 1
    assert temp_db.get_ticket(tid)["status"] == "closed"


def test_batch_limit_leaves_the_rest_open(temp_db):
    ids = []
    for i in range(3):
        tid, mids = _ticket_with_messages(temp_db, 710000 + i, ["user", "admin"])
        _created_at(temp_db, mids[-1], NOW - timedelta(days=10))
        ids.append(tid)
    result = temp_db.auto_close_idle_admin_tickets(7, now=NOW, limit=2)
    assert result["count"] == 2
    closed = sum(1 for tid in ids if temp_db.get_ticket(tid)["status"] == "closed")
    opened = sum(1 for tid in ids if temp_db.get_ticket(tid)["status"] == "open")
    assert closed == 2
    assert opened == 1


def test_already_closed_ticket_is_skipped(temp_db):
    tid, mids = _ticket_with_messages(temp_db, 700006, ["user", "admin"])
    _created_at(temp_db, mids[-1], NOW - timedelta(days=20))
    temp_db.set_ticket_status(tid, "closed")
    assert temp_db.find_open_tickets_idle_after_admin(7, now=NOW) == []


def test_maybe_auto_close_reads_setting_and_does_not_wait(temp_db, monkeypatch):
    from shop_bot.support_bot import idle_close

    tid, mids = _ticket_with_messages(temp_db, 700007, ["user", "admin"])
    _created_at(temp_db, mids[-1], NOW - timedelta(days=8))
    temp_db.update_setting("ticket_auto_close_days", "7")

    started = threading.Event()
    released = threading.Event()

    def slow_followup(tickets, days):
        started.set()
        released.wait(timeout=5)

    monkeypatch.setattr(idle_close, "run_idle_close_followup", slow_followup)
    t0 = time.monotonic()
    n = idle_close.maybe_auto_close_idle_tickets(now=NOW, sync_followup=False)
    elapsed = time.monotonic() - t0
    assert n == 1
    assert elapsed < 0.75
    assert temp_db.get_ticket(tid)["status"] == "closed"
    assert started.wait(timeout=2)
    released.set()


def test_maybe_auto_close_noops_when_setting_disabled(temp_db, monkeypatch):
    from shop_bot.support_bot import idle_close

    tid, mids = _ticket_with_messages(temp_db, 700008, ["user", "admin"])
    _created_at(temp_db, mids[-1], NOW - timedelta(days=30))
    temp_db.update_setting("ticket_auto_close_days", "0")
    called = []
    monkeypatch.setattr(idle_close, "run_idle_close_followup", lambda *a, **k: called.append(1))
    n = idle_close.maybe_auto_close_idle_tickets(now=NOW, sync_followup=True)
    assert n == 0
    assert called == []
    assert temp_db.get_ticket(tid)["status"] == "open"


def test_scheduler_hook_calls_idle_close(temp_db, monkeypatch):
    from shop_bot.data_manager import scheduler as sched

    called = []
    monkeypatch.setattr(
        "shop_bot.support_bot.idle_close.maybe_auto_close_idle_tickets",
        lambda **k: called.append(1) or 0,
    )
    sched._maybe_auto_close_idle_tickets()
    assert called == [1]


def test_settings_page_has_auto_close_field(temp_db, monkeypatch):
    from shop_bot.webhook_server import app as wh_mod

    class _Bot:
        def get_status(self):
            return {"is_running": False}

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_Bot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
    html = client.get("/settings").get_data(as_text=True)
    assert 'name="ticket_auto_close_days"' in html
    assert "Автозакрытие тикета" in html
