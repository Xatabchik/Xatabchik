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
    save_ticket_media,
)


def test_declared_size_none_or_zero_is_not_a_pass():
    """Дыра PR #124: `if file_size and file_size > MAX` пропускала None/0."""
    assert declared_size_over_limit(None) is False
    assert declared_size_over_limit(0) is False
    assert declared_size_over_limit(1) is False
    assert declared_size_over_limit(TICKET_MEDIA_MAX_BYTES) is False
    assert declared_size_over_limit(TICKET_MEDIA_MAX_BYTES + 1) is True


class _DownloadBot:
    def __init__(self, payload: bytes, *, api_size=None, api_size_missing: bool = False):
        self.payload = payload
        self.downloads = 0
        self.get_file_calls = 0
        self.api_size = len(payload) if api_size is None else api_size
        self.api_size_missing = api_size_missing

    async def get_file(self, file_id):
        self.get_file_calls += 1
        size = None if self.api_size_missing else self.api_size
        return SimpleNamespace(file_id=file_id, file_size=size)

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


def test_save_rejects_when_telegram_omits_size_but_file_is_huge(temp_db, tmp_path, monkeypatch):
    """file_size=None: getFile до download, большой файл не качается."""
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    bot = _DownloadBot(b"x" * (TICKET_MEDIA_MAX_BYTES + 50), api_size=TICKET_MEDIA_MAX_BYTES + 50)
    result = asyncio.run(save_ticket_media(bot, _photo_message(None), ticket_id=7))

    assert result is None
    assert bot.get_file_calls == 1
    assert bot.downloads == 0
    leftover_files = [p for p in media_root.rglob("*") if p.is_file()] if media_root.exists() else []
    assert leftover_files == []
    assert not (media_root / "7").exists()


def test_save_skips_download_if_getfile_has_no_size(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    bot = _DownloadBot(b"\xff\xd8\xff\xe0tiny", api_size_missing=True)
    result = asyncio.run(save_ticket_media(bot, _photo_message(0), ticket_id=7))

    assert result is None
    assert bot.get_file_calls == 1
    assert bot.downloads == 0


def test_save_uses_getfile_size_then_downloads_small(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    payload = b"\xff\xd8\xff\xe0tiny"
    bot = _DownloadBot(payload, api_size=len(payload))
    result = asyncio.run(save_ticket_media(bot, _photo_message(None), ticket_id=7))

    assert result is not None
    assert bot.get_file_calls == 1
    assert bot.downloads == 1
    assert (media_root / result).read_bytes() == payload


def test_capped_download_stops_lying_file_size(temp_db, tmp_path, monkeypatch):
    """Сообщили 100 байт, качают больше 10 МБ — поток обрывается, файл не остаётся."""
    from shop_bot.data_manager import database

    media_root = tmp_path / "ticket_files"
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(media_root))

    bot = _DownloadBot(b"x" * (TICKET_MEDIA_MAX_BYTES + 80), api_size=100)
    result = asyncio.run(save_ticket_media(bot, _photo_message(100), ticket_id=7))

    assert result is None
    leftover = [p for p in media_root.rglob("*") if p.is_file()] if media_root.exists() else []
    assert leftover == []
    assert not (media_root / "7").exists()


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
    assert bot.get_file_calls == 1
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
