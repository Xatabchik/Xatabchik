"""TTL вложений закрытых тикетов: файлы снимаются, строки тикета остаются."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from conftest import temp_db  # noqa: F401

from shop_bot.support_bot.ticket_media import (
    closed_ticket_media_expired,
    parse_ticket_updated_at,
    purge_expired_closed_ticket_media,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _media_root(tmp_path: Path, monkeypatch) -> Path:
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    return root


def _set_updated_at(database, ticket_id: int, when: datetime) -> None:
    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE support_tickets SET updated_at = ? WHERE ticket_id = ?",
            (when.strftime("%Y-%m-%d %H:%M:%S"), ticket_id),
        )
        conn.commit()


def _put_png(root: Path, ticket_id: int, name: str = "shot.png") -> Path:
    folder = root / str(ticket_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(PNG)
    return path


def test_parse_and_expiry_rules():
    now = datetime(2026, 8, 30, 12, 0, 0)
    assert parse_ticket_updated_at("2026-08-20 12:00:00") == datetime(2026, 8, 20, 12, 0, 0)
    assert closed_ticket_media_expired(None, now=now) is False
    assert closed_ticket_media_expired({"status": "open", "updated_at": "2020-01-01 00:00:00"}, now=now) is False
    assert (
        closed_ticket_media_expired(
            {"status": "closed", "updated_at": "2026-08-29 12:00:00"},
            now=now,
            ttl_days=7,
        )
        is False
    )
    assert (
        closed_ticket_media_expired(
            {"status": "closed", "updated_at": "2026-08-20 12:00:00"},
            now=now,
            ttl_days=7,
        )
        is True
    )
    assert closed_ticket_media_expired({"status": "closed", "updated_at": "bad"}, now=now) is False


def test_purge_removes_old_closed_keeps_open_and_recent(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = _media_root(tmp_path, monkeypatch)
    now = datetime(2026, 8, 30, 12, 0, 0)

    old_id = database.create_support_ticket(70101, "old")
    recent_id = database.create_support_ticket(70102, "recent")
    open_id = database.create_support_ticket(70103, "open")

    database.set_ticket_status(old_id, "closed")
    database.set_ticket_status(recent_id, "closed")
    _set_updated_at(database, old_id, now - timedelta(days=10))
    _set_updated_at(database, recent_id, now - timedelta(days=2))

    old_file = _put_png(root, old_id)
    recent_file = _put_png(root, recent_id)
    open_file = _put_png(root, open_id)
    database.add_support_message(old_id, "user", "x", media=f"{old_id}/shot.png")

    result = purge_expired_closed_ticket_media(now=now, ttl_days=7)

    assert result["purged"] >= 1
    assert not old_file.exists()
    assert not (root / str(old_id)).exists()
    assert recent_file.is_file()
    assert open_file.is_file()
    assert database.get_ticket(old_id) is not None
    msgs = database.get_ticket_messages(old_id)
    assert msgs and msgs[0].get("media") is None


def test_purge_removes_orphan_folder(temp_db, tmp_path, monkeypatch):
    _media_root(tmp_path, monkeypatch)
    orphan = tmp_path / "ticket_files" / "888888"
    orphan.mkdir(parents=True)
    (orphan / "x.png").write_bytes(PNG)

    result = purge_expired_closed_ticket_media()
    assert result["orphans"] >= 1
    assert not orphan.exists()


def test_expire_on_serve_is_404_and_deletes_file(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    root = _media_root(tmp_path, monkeypatch)
    ticket_id = database.create_support_ticket(70104, "ttl-serve")
    database.set_ticket_status(ticket_id, "closed")
    _set_updated_at(database, ticket_id, datetime.utcnow() - timedelta(days=9))
    _put_png(root, ticket_id)
    message_id = database.add_support_message(ticket_id, "user", "скрин", media=f"{ticket_id}/shot.png")

    class _PanelBot:
        def get_status(self):
            return {"is_running": False}

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.get(f"/support/ticket-file/{message_id}")
    assert resp.status_code == 404
    assert not (root / str(ticket_id)).exists()
    assert database.get_ticket(ticket_id) is not None


def test_open_ticket_file_still_served(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    root = _media_root(tmp_path, monkeypatch)
    ticket_id = database.create_support_ticket(70105, "open-serve")
    _put_png(root, ticket_id)
    message_id = database.add_support_message(ticket_id, "user", "скрин", media=f"{ticket_id}/shot.png")

    class _PanelBot:
        def get_status(self):
            return {"is_running": False}

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.get(f"/support/ticket-file/{message_id}")
    assert resp.status_code == 200
    assert resp.data == PNG
    assert (root / str(ticket_id) / "shot.png").is_file()
