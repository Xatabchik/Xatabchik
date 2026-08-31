"""Массовые «закрыть все» / «удалить все» тикеты: быстрый SQL, Telegram не в HTTP."""
from __future__ import annotations

import threading
import time

from conftest import temp_db  # noqa: F401


class _PanelBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None

    def get_bot_instance(self):
        return None


def _client(temp_db, monkeypatch, *, sync: bool = True):
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    flask_app.config["BULK_TICKETS_SYNC"] = sync
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"
    return client, flask_app, wh_mod


def _make_tickets(database, n: int, *, open_n: int | None = None, with_forum: bool = False):
    if open_n is None:
        open_n = n
    ids = []
    for i in range(n):
        tid = database.create_support_ticket(300000 + i, f"Тема {i}")
        database.add_support_message(tid, "user", f"Сообщение {i}")
        if with_forum:
            database.update_ticket_thread_info(tid, "1001", 2000 + i)
        if i >= open_n:
            database.set_ticket_status(tid, "closed")
        ids.append(tid)
    return ids


def test_list_page_shows_bulk_actions(temp_db, monkeypatch):
    _make_tickets(temp_db, 2)
    client, _, _ = _client(temp_db, monkeypatch)
    html = client.get("/support").get_data(as_text=True)
    assert 'action="/support/bulk-close"' in html
    assert 'action="/support/bulk-delete"' in html
    assert "Закрыть все тикеты" in html
    assert "Удалить все тикеты" in html
    assert "data-busy-on-submit" in html
    assert 'disabled' not in html.split('title="Закрыть все открытые тикеты"')[1][:80]


def test_bulk_close_updates_only_open_tickets(temp_db, monkeypatch):
    ids = _make_tickets(temp_db, 4, open_n=3)
    client, _, _ = _client(temp_db, monkeypatch)

    resp = client.post("/support/bulk-close", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert (resp.headers.get("Location") or "").endswith("/support")

    assert temp_db.get_open_tickets_count() == 0
    assert temp_db.get_closed_tickets_count() == 4
    assert temp_db.get_all_tickets_count() == 4
    for tid in ids:
        row = temp_db.get_ticket(tid)
        assert row is not None
        assert row["status"] == "closed"


def test_bulk_delete_removes_tickets_messages_and_media(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.support_bot.ticket_media import save_ticket_media_bytes

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    ids = _make_tickets(temp_db, 3, open_n=1)
    rel = save_ticket_media_bytes(b"\xff\xd8\xff\xe0tiny", ids[0])
    assert rel
    temp_db.add_support_message(ids[0], "user", "файл", media=rel)
    assert (media_root / str(ids[0])).is_dir()

    client, _, _ = _client(temp_db, monkeypatch, sync=True)
    resp = client.post("/support/bulk-delete", follow_redirects=False)
    assert resp.status_code in (302, 303)

    assert temp_db.get_all_tickets_count() == 0
    assert temp_db.get_ticket(ids[0]) is None
    assert temp_db.get_ticket_messages(ids[0]) == []
    leftover = [p for p in media_root.rglob("*") if p.is_file()] if media_root.exists() else []
    assert leftover == []
    assert not (media_root / str(ids[0])).exists()


def test_bulk_delete_http_does_not_wait_for_followup(temp_db, monkeypatch):
    _make_tickets(temp_db, 8)
    started = threading.Event()
    released = threading.Event()

    def slow_followup(**kwargs):
        started.set()
        released.wait(timeout=5)

    from shop_bot.webhook_server import app as wh_mod

    monkeypatch.setattr(wh_mod, "run_bulk_ticket_followup", slow_followup)
    client, _, _ = _client(temp_db, monkeypatch, sync=False)

    t0 = time.monotonic()
    resp = client.post("/support/bulk-delete", follow_redirects=False)
    elapsed = time.monotonic() - t0

    assert resp.status_code in (302, 303)
    assert elapsed < 0.75
    assert temp_db.get_all_tickets_count() == 0
    assert started.wait(timeout=2)
    released.set()


def test_bulk_close_http_does_not_wait_for_forum(temp_db, monkeypatch):
    _make_tickets(temp_db, 5, with_forum=True)
    started = threading.Event()
    released = threading.Event()

    def slow_followup(**kwargs):
        started.set()
        released.wait(timeout=5)

    from shop_bot.webhook_server import app as wh_mod

    monkeypatch.setattr(wh_mod, "run_bulk_ticket_followup", slow_followup)
    client, _, _ = _client(temp_db, monkeypatch, sync=False)

    t0 = time.monotonic()
    resp = client.post("/support/bulk-close", follow_redirects=False)
    elapsed = time.monotonic() - t0

    assert resp.status_code in (302, 303)
    assert elapsed < 0.75
    assert temp_db.get_open_tickets_count() == 0
    assert started.wait(timeout=2)
    released.set()


def test_bulk_routes_require_login(temp_db, monkeypatch):
    _make_tickets(temp_db, 1)
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()

    close = client.post("/support/bulk-close", follow_redirects=False)
    delete = client.post("/support/bulk-delete", follow_redirects=False)
    assert close.status_code in (302, 303)
    assert delete.status_code in (302, 303)
    assert "/login" in (close.headers.get("Location") or "")
    assert "/login" in (delete.headers.get("Location") or "")
    assert temp_db.get_all_tickets_count() == 1


def test_bulk_close_empty_is_noop(temp_db, monkeypatch):
    client, _, _ = _client(temp_db, monkeypatch)
    resp = client.post("/support/bulk-close", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert temp_db.get_all_tickets_count() == 0


def test_followup_paces_forum_calls(temp_db, monkeypatch):
    from shop_bot.webhook_server import app as wh_mod

    calls = []

    def fake_wait(loop, coro, timeout):
        calls.append(timeout)
        try:
            coro.close()
        except Exception:
            pass

    class _Loop:
        def is_running(self):
            return True

    class _Bot:
        async def close_forum_topic(self, chat_id, message_thread_id):
            return None

    monkeypatch.setattr(wh_mod, "_forum_coro_wait", fake_wait)
    targets = [
        {"ticket_id": 1, "forum_chat_id": "10", "message_thread_id": 11},
        {"ticket_id": 2, "forum_chat_id": "10", "message_thread_id": 12},
        {"ticket_id": 3, "forum_chat_id": "10", "message_thread_id": 13},
    ]
    t0 = time.monotonic()
    wh_mod.run_bulk_ticket_followup(
        action="close",
        forum_targets=targets,
        bot=_Bot(),
        loop=_Loop(),
        gap_sec=0.05,
        call_timeout=1,
    )
    elapsed = time.monotonic() - t0
    assert len(calls) == 3
    assert elapsed >= 0.08
