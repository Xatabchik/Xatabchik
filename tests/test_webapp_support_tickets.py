"""WebApp поддержка: список/закрытие тикетов и вложения только владельцу."""
from __future__ import annotations

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _user(db, telegram_id: int, username: str):
    insert_user(db.DB_FILE, telegram_id=telegram_id, username=username)
    return issue_auth_token(telegram_id)


def test_status_lists_tickets_and_hides_raw_media_path(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    token = _user(database, 92001, "sup1")
    ticket_id = database.create_support_ticket(92001, "VPN")
    dest = root / str(ticket_id)
    dest.mkdir()
    (dest / "shot.jpg").write_bytes(JPEG)
    database.add_support_message(ticket_id, "user", "скрин", media=f"{ticket_id}/shot.jpg")

    resp = _client().post("/api/support/status", json={"token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["has_ticket"] is True
    assert data["ticket_id"] == ticket_id
    assert any(t["ticket_id"] == ticket_id for t in data["tickets"])
    msg = data["messages"][0]
    assert msg["has_media"] is True
    assert msg["media_kind"] == "image"
    assert "media" not in msg
    assert "shot.jpg" not in str(data)
    assert "/ticket_files" not in str(data)


def test_close_own_ticket_and_reject_foreign(temp_db):
    from shop_bot.data_manager import database

    owner = _user(database, 92010, "owner")
    attacker = _user(database, 92011, "atk")
    ticket_id = database.create_support_ticket(92010, "Тема")
    client = _client()

    deny = client.post("/api/support/close", json={"token": attacker, "ticket_id": ticket_id})
    assert deny.status_code == 200
    assert deny.json().get("ok") is False
    assert database.get_ticket(ticket_id)["status"] == "open"

    ok = client.post("/api/support/close", json={"token": owner, "ticket_id": ticket_id})
    assert ok.status_code == 200
    assert ok.json().get("ok") is True
    assert database.get_ticket(ticket_id)["status"] == "closed"


def test_ticket_view_is_owner_only(temp_db):
    from shop_bot.data_manager import database

    owner = _user(database, 92020, "own")
    attacker = _user(database, 92021, "atk2")
    ticket_id = database.create_support_ticket(92020, "Секрет")
    database.add_support_message(ticket_id, "user", "платёжка")
    client = _client()

    assert client.post("/api/support/ticket", json={"ticket_id": ticket_id}).status_code == 401
    stolen = client.post("/api/support/ticket", json={"token": attacker, "ticket_id": ticket_id})
    assert stolen.json().get("ok") is False
    mine = client.post("/api/support/ticket", json={"token": owner, "ticket_id": ticket_id})
    assert mine.json()["ok"] is True
    assert mine.json()["subject"] == "Секрет"


def test_upload_and_download_owner_only(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    handlers._SUPPORT_LAST.clear()
    handlers._SUPPORT_HITS.clear()
    monkeypatch.setattr(handlers, "SUPPORT_MIN_INTERVAL_SECONDS", 0)

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    owner = _user(database, 92030, "own3")
    attacker = _user(database, 92031, "atk3")
    ticket_id = database.create_support_ticket(92030, "Файлы")
    client = _client()

    assert client.post(
        "/api/support/upload",
        data={"ticket_id": str(ticket_id)},
        files={"file": ("shot.jpg", JPEG, "image/jpeg")},
    ).status_code == 401

    stolen = client.post(
        "/api/support/upload",
        data={"ticket_id": str(ticket_id), "token": attacker},
        files={"file": ("shot.jpg", JPEG, "image/jpeg")},
    )
    assert stolen.json().get("ok") is False

    uploaded = client.post(
        "/api/support/upload",
        data={"ticket_id": str(ticket_id), "token": owner, "caption": "скрин"},
        files={"file": ("shot.jpg", JPEG, "image/jpeg")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json().get("ok") is True
    messages = database.get_ticket_messages(ticket_id)
    media_msg = next(m for m in messages if m.get("media"))
    message_id = media_msg["message_id"]
    saved = root / media_msg["media"]
    assert saved.is_file()
    assert saved.read_bytes() == JPEG

    no_auth = client.get(f"/api/support/ticket-file/{message_id}")
    assert no_auth.status_code == 401

    foreign = client.get(f"/api/support/ticket-file/{message_id}", params={"token": attacker})
    assert foreign.status_code == 404

    mine = client.get(f"/api/support/ticket-file/{message_id}", params={"token": owner})
    assert mine.status_code == 200
    assert mine.headers.get("X-Content-Type-Options") == "nosniff"
    assert mine.content == JPEG


def test_upload_rejects_html_and_oversize(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.support_bot.ticket_media import TICKET_MEDIA_MAX_BYTES
    from shop_bot.webapp import handlers

    handlers._SUPPORT_LAST.clear()
    handlers._SUPPORT_HITS.clear()
    monkeypatch.setattr(handlers, "SUPPORT_MIN_INTERVAL_SECONDS", 0)

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    token = _user(database, 92040, "own4")
    ticket_id = database.create_support_ticket(92040, "Плохой файл")
    client = _client()

    html = client.post(
        "/api/support/upload",
        data={"ticket_id": str(ticket_id), "token": token},
        files={"file": ("x.jpg", b"<html>xss</html>", "image/jpeg")},
    )
    assert html.json().get("ok") is False
    leftover = list(root.rglob("*")) if root.exists() else []
    assert not any(p.is_file() for p in leftover)

    huge = client.post(
        "/api/support/upload",
        data={"ticket_id": str(ticket_id), "token": token},
        files={"file": ("big.jpg", b"x" * (TICKET_MEDIA_MAX_BYTES + 20), "image/jpeg")},
    )
    assert huge.json().get("ok") is False


def test_ticket_file_accepts_cookie_without_query_token(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    token = _user(database, 92050, "cookie")
    ticket_id = database.create_support_ticket(92050, "Кука")
    dest = root / str(ticket_id)
    dest.mkdir(parents=True)
    (dest / "shot.jpg").write_bytes(JPEG)
    message_id = database.add_support_message(ticket_id, "user", "x", media=f"{ticket_id}/shot.jpg")
    client = _client()
    client.cookies.set("auth_token", token)
    resp = client.get(f"/api/support/ticket-file/{message_id}")
    assert resp.status_code == 200
    assert resp.content == JPEG
    assert "no-referrer" in (resp.headers.get("Referrer-Policy") or "")


def test_send_rejects_empty_and_clips_long_text(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    handlers._SUPPORT_LAST.clear()
    handlers._SUPPORT_HITS.clear()
    monkeypatch.setattr(handlers, "SUPPORT_MIN_INTERVAL_SECONDS", 0)
    token = _user(database, 92060, "clip")
    ticket_id = database.create_support_ticket(92060, "Текст")
    client = _client()
    empty = client.post("/api/support/send", json={"token": token, "ticket_id": ticket_id, "message": "   "})
    assert empty.json().get("ok") is False
    long_msg = "я" * 5000
    ok = client.post("/api/support/send", json={"token": token, "ticket_id": ticket_id, "message": long_msg})
    assert ok.json().get("ok") is True
    stored = database.get_ticket_messages(ticket_id)[-1]["content"]
    assert len(stored) == handlers.SUPPORT_TEXT_MAX_LEN


def test_send_rate_limit_blocks_flood(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp import handlers

    handlers._SUPPORT_LAST.clear()
    handlers._SUPPORT_HITS.clear()
    monkeypatch.setattr(handlers, "SUPPORT_MIN_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(handlers, "SUPPORT_SEND_PER_MINUTE", 2)
    token = _user(database, 92070, "flood")
    ticket_id = database.create_support_ticket(92070, "Флуд")
    client = _client()
    assert client.post("/api/support/send", json={"token": token, "ticket_id": ticket_id, "message": "1"}).json().get("ok") is True
    assert client.post("/api/support/send", json={"token": token, "ticket_id": ticket_id, "message": "2"}).json().get("ok") is True
    third = client.post("/api/support/send", json={"token": token, "ticket_id": ticket_id, "message": "3"})
    assert third.status_code == 429
    assert third.json().get("ok") is False


def test_save_ticket_media_bytes_writes_png(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.support_bot.ticket_media import save_ticket_media_bytes

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    rel = save_ticket_media_bytes(PNG, 77)
    assert rel is not None
    assert rel.endswith(".png")
    assert (root / rel).read_bytes() == PNG
