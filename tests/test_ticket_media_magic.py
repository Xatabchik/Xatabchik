"""Magic bytes вложений тикета и nosniff при отдаче в панели."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from conftest import temp_db  # noqa: F401

from shop_bot.support_bot.ticket_media import (
    commit_ticket_image,
    detect_image_kind,
    detect_image_kind_bytes,
    public_support_message,
    save_ticket_media,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
GIF = b"GIF89a" + b"\x01\x00\x01\x00\x00\x00\x00"
WEBP = b"RIFF" + b"\x10\x00\x00\x00" + b"WEBP" + b"xxxx"
PDF = b"%PDF-1.4\n%dummy"


class _DownloadBot:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.downloads = 0

    async def download(self, file_id, destination):
        self.downloads += 1
        if hasattr(destination, "write"):
            destination.write(self.payload)
            return
        with open(destination, "wb") as fh:
            fh.write(self.payload)


def _photo_message(file_size):
    photo = SimpleNamespace(file_id="photo-1", file_size=file_size)
    return SimpleNamespace(photo=[photo], document=None)


def _doc_message(*, mime: str, name: str, payload_size: int):
    doc = SimpleNamespace(
        file_id="doc-1",
        file_size=payload_size,
        mime_type=mime,
        file_name=name,
    )
    return SimpleNamespace(photo=None, document=doc)


class _PanelBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None


def test_detect_known_image_signatures():
    assert detect_image_kind_bytes(JPEG) == (".jpg", "image/jpeg")
    assert detect_image_kind_bytes(PNG) == (".png", "image/png")
    assert detect_image_kind_bytes(WEBP) == (".webp", "image/webp")
    assert detect_image_kind_bytes(PDF) == (".pdf", "application/pdf")
    assert detect_image_kind_bytes(GIF) is None


def test_detect_rejects_html_svg_and_short():
    assert detect_image_kind_bytes(b"<html><img>") is None
    assert detect_image_kind_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'>") is None
    assert detect_image_kind_bytes(b"%PDF") is None
    assert detect_image_kind_bytes(b"\xff\xd8") is None


def test_commit_rejects_gif(tmp_path):
    part = tmp_path / "x.part"
    part.write_bytes(GIF)
    assert commit_ticket_image(str(part), str(tmp_path), "abc") is None
    assert not part.exists()
    assert list(tmp_path.iterdir()) == []


def test_commit_uses_png_ext_not_declared_name(tmp_path):
    part = tmp_path / "x.part"
    part.write_bytes(PNG)
    name = commit_ticket_image(str(part), str(tmp_path), "abc")
    assert name == "abc.png"
    assert (tmp_path / "abc.png").read_bytes() == PNG
    assert not part.exists()


def test_commit_rejects_html_disguised_as_image(tmp_path):
    part = tmp_path / "x.part"
    part.write_bytes(b"<html>not an image</html>")
    assert commit_ticket_image(str(part), str(tmp_path), "abc") is None
    assert not part.exists()
    assert list(tmp_path.iterdir()) == []


def test_save_rejects_html_even_if_telegram_says_jpeg(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    bot = _DownloadBot(b"<script>alert(1)</script>")
    result = asyncio.run(save_ticket_media(bot, _photo_message(20), ticket_id=21))
    assert result is None
    leftover = [p for p in root.rglob("*") if p.is_file()] if root.exists() else []
    assert leftover == []
    assert not (root / "21").exists()


def test_save_png_document_named_jpg_keeps_png_ext(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    bot = _DownloadBot(PNG)
    msg = _doc_message(mime="image/jpeg", name="receipt.jpg", payload_size=len(PNG))
    result = asyncio.run(save_ticket_media(bot, msg, ticket_id=22))
    assert result is not None
    assert result.endswith(".png")
    assert (root / result).read_bytes() == PNG


def test_ticket_file_serves_nosniff_and_real_mime(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))

    ticket_id = database.create_support_ticket(60101, "magic")
    rel = f"{ticket_id}/shot.png"
    dest = root / str(ticket_id)
    dest.mkdir()
    (dest / "shot.png").write_bytes(PNG)
    message_id = database.add_support_message(ticket_id, "user", "скрин", media=rel)

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.get(f"/support/ticket-file/{message_id}")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type", "").startswith("image/png")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.data == PNG


def test_ticket_file_html_on_disk_is_not_served(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))

    ticket_id = database.create_support_ticket(60102, "html")
    rel = f"{ticket_id}/evil.jpg"
    dest = root / str(ticket_id)
    dest.mkdir()
    (dest / "evil.jpg").write_bytes(b"<html>xss</html>")
    message_id = database.add_support_message(ticket_id, "user", "x", media=rel)

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.get(f"/support/ticket-file/{message_id}")
    assert resp.status_code == 404
    assert b"<html>" not in resp.data


def test_detect_image_kind_reads_file(tmp_path):
    p = tmp_path / "a.webp"
    p.write_bytes(WEBP)
    assert detect_image_kind(str(p)) == (".webp", "image/webp")


def test_save_jpeg_document_with_octet_stream_mime(temp_db, tmp_path, monkeypatch):
    """Скриншот «как файл» часто приходит как application/octet-stream."""
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    bot = _DownloadBot(JPEG)
    msg = _doc_message(mime="application/octet-stream", name="screen.jpg", payload_size=len(JPEG))
    result = asyncio.run(save_ticket_media(bot, msg, ticket_id=25))
    assert result is not None
    assert result.endswith(".jpg")
    assert (root / result).read_bytes() == JPEG


def test_save_pdf_document(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    bot = _DownloadBot(PDF)
    msg = _doc_message(mime="application/pdf", name="check.pdf", payload_size=len(PDF))
    result = asyncio.run(save_ticket_media(bot, msg, ticket_id=23))
    assert result is not None
    assert result.endswith(".pdf")
    assert (root / result).read_bytes() == PDF


def test_save_rejects_zip_named_pdf(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    bot = _DownloadBot(b"PK\x03\x04not-a-pdf")
    msg = _doc_message(mime="application/pdf", name="x.pdf", payload_size=20)
    result = asyncio.run(save_ticket_media(bot, msg, ticket_id=24))
    assert result is None


def test_ticket_file_serves_pdf_with_nosniff(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))

    ticket_id = database.create_support_ticket(60103, "pdf")
    rel = f"{ticket_id}/doc.pdf"
    dest = root / str(ticket_id)
    dest.mkdir()
    (dest / "doc.pdf").write_bytes(PDF)
    message_id = database.add_support_message(ticket_id, "user", "чек", media=rel)

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.get(f"/support/ticket-file/{message_id}")
    assert resp.status_code == 200
    assert resp.headers.get("Content-Type", "").startswith("application/pdf")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.data == PDF


def test_public_support_message_hides_path():
    out = public_support_message({
        "sender": "user",
        "content": "чек",
        "media": "12/deadbeef.png",
        "message_id": 99,
        "created_at": "2026-01-01 00:00:00",
    })
    assert out["has_media"] is True
    assert out["media_kind"] == "image"
    assert out["message_id"] == 99
    assert "media" not in out
    assert "deadbeef" not in str(out)

    pdf = public_support_message({"media": "3/ab.pdf", "message_id": 1, "content": ""})
    assert pdf["media_kind"] == "pdf"
    assert "ab.pdf" not in str(pdf)

    empty = public_support_message({"content": "hi", "media": None, "message_id": 2})
    assert empty["has_media"] is False
    assert empty["media_kind"] is None


def test_messages_json_has_no_raw_media_path(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webhook_server import app as wh_mod

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))

    ticket_id = database.create_support_ticket(60104, "json")
    secret = f"{ticket_id}/cafebabe.png"
    dest = root / str(ticket_id)
    dest.mkdir()
    (dest / "cafebabe.png").write_bytes(PNG)
    mid = database.add_support_message(ticket_id, "user", "скрин", media=secret)
    database.add_support_message(ticket_id, "user", "pdf", media=f"{ticket_id}/aa.pdf")

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.get(f"/support/{ticket_id}/messages.json")
    assert resp.status_code == 200
    body = resp.get_json()
    dumped = resp.get_data(as_text=True)
    assert "cafebabe" not in dumped
    assert "aa.pdf" not in dumped
    assert "/ticket_files" not in dumped
    items = body["messages"]
    assert items[0]["has_media"] is True
    assert items[0]["media_kind"] == "image"
    assert items[0]["message_id"] == mid
    assert "media" not in items[0]
    assert items[1]["media_kind"] == "pdf"
