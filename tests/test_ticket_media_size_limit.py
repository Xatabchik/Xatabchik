"""Лимит 10 МБ на вложения тикетов: заявленный размер и проверка после download.

Файлы не отдаются без логина в панель. Хендлеры магазина не затрагиваются.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from conftest import temp_db  # noqa: F401

from shop_bot.support_bot.ticket_media import (
    TICKET_MEDIA_MAX_BYTES,
    declared_size_over_limit,
    finalize_ticket_media_download,
    save_ticket_media,
)


def test_declared_size_none_or_zero_is_not_a_pass():
    """Дыра PR #124: `if file_size and file_size > MAX` пропускала None/0."""
    assert declared_size_over_limit(None) is False
    assert declared_size_over_limit(0) is False
    assert declared_size_over_limit(1) is False
    assert declared_size_over_limit(TICKET_MEDIA_MAX_BYTES) is False
    assert declared_size_over_limit(TICKET_MEDIA_MAX_BYTES + 1) is True


def test_finalize_keeps_file_under_limit(tmp_path):
    part = tmp_path / "a.jpg.part"
    final = tmp_path / "a.jpg"
    part.write_bytes(b"ok-image")
    assert finalize_ticket_media_download(str(part), str(final)) is True
    assert final.is_file()
    assert final.read_bytes() == b"ok-image"
    assert not part.exists()


def test_finalize_rejects_oversize_and_deletes_part(tmp_path):
    part = tmp_path / "big.jpg.part"
    final = tmp_path / "big.jpg"
    part.write_bytes(b"x" * (TICKET_MEDIA_MAX_BYTES + 1))
    assert finalize_ticket_media_download(str(part), str(final)) is False
    assert not part.exists()
    assert not final.exists()


def test_finalize_rejects_empty_file(tmp_path):
    part = tmp_path / "empty.jpg.part"
    final = tmp_path / "empty.jpg"
    part.write_bytes(b"")
    assert finalize_ticket_media_download(str(part), str(final)) is False
    assert not part.exists()
    assert not final.exists()


class _DownloadBot:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.downloads = 0

    async def download(self, file_id, destination):
        self.downloads += 1
        with open(destination, "wb") as fh:
            fh.write(self.payload)


def _photo_message(file_size):
    photo = SimpleNamespace(file_id="photo-1", file_size=file_size)
    return SimpleNamespace(photo=[photo], document=None)


def test_save_rejects_when_telegram_omits_size_but_file_is_huge(temp_db, tmp_path, monkeypatch):
    """file_size=None больше не обходит лимит: после download файл выбрасывается."""
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    bot = _DownloadBot(b"x" * (TICKET_MEDIA_MAX_BYTES + 50))
    result = asyncio.run(save_ticket_media(bot, _photo_message(None), ticket_id=7))

    assert result is None
    assert bot.downloads == 1
    leftover_files = [p for p in media_root.rglob("*") if p.is_file()]
    assert leftover_files == []


def test_save_rejects_declared_oversize_without_download(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    bot = _DownloadBot(b"should-not-write")
    result = asyncio.run(
        save_ticket_media(
            bot,
            _photo_message(TICKET_MEDIA_MAX_BYTES + 1),
            ticket_id=8,
        )
    )

    assert result is None
    assert bot.downloads == 0
    assert not media_root.exists() or list(media_root.rglob("*")) == []


def test_save_keeps_small_image(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    payload = b"\xff\xd8\xff\xe0tiny"
    bot = _DownloadBot(payload)
    result = asyncio.run(save_ticket_media(bot, _photo_message(len(payload)), ticket_id=9))

    assert result is not None
    assert result.startswith("9/")
    assert result.endswith(".jpg")
    saved = media_root / result
    assert saved.is_file()
    assert saved.read_bytes() == payload
    assert list(media_root.rglob("*.part")) == []


class _PanelBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None


def test_ticket_file_is_not_public(temp_db):
    """Вложения не доступны снаружи: без сессии панели — редирект на логин."""
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()

    with client.session_transaction() as sess:
        sess.pop("logged_in", None)

    resp = client.get("/support/ticket-file/1", follow_redirects=False)
    assert resp.status_code in (301, 302, 303, 401)
    location = (resp.headers.get("Location") or "").lower()
    assert "login" in location or resp.status_code == 401
    assert resp.status_code != 200
