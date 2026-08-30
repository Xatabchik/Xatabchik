"""Квота вложений на тикет и удаление файлов вместе с тикетом."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from conftest import insert_user, temp_db  # noqa: F401

from shop_bot.support_bot.ticket_media import (
    TICKET_MEDIA_MAX_FILES,
    delete_ticket_media_dir,
    jailed_ticket_folder,
    quota_blocks_new_file,
    save_ticket_media,
    ticket_folder_usage,
)


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


def _media_root(tmp_path: Path, monkeypatch) -> Path:
    from shop_bot.data_manager import database

    root = tmp_path / "ticket_files"
    root.mkdir()
    monkeypatch.setattr(database, "get_ticket_media_root", lambda: str(root))
    return root


def test_quota_blocks_by_file_count(tmp_path):
    folder = tmp_path / "t"
    folder.mkdir()
    for i in range(2):
        (folder / f"{i}.jpg").write_bytes(b"x")
    assert quota_blocks_new_file(str(folder), max_files=2, max_total_bytes=10_000) is True
    assert quota_blocks_new_file(str(folder), max_files=3, max_total_bytes=10_000) is False


def test_quota_blocks_by_total_bytes(tmp_path):
    folder = tmp_path / "t"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"x" * 80)
    assert quota_blocks_new_file(str(folder), incoming_bytes=30, max_files=10, max_total_bytes=100) is True
    assert quota_blocks_new_file(str(folder), incoming_bytes=10, max_files=10, max_total_bytes=100) is False


def test_quota_ignores_part_files(tmp_path):
    folder = tmp_path / "t"
    folder.mkdir()
    (folder / "a.jpg.part").write_bytes(b"x" * 500)
    assert ticket_folder_usage(str(folder)) == (0, 0)
    assert quota_blocks_new_file(str(folder), max_files=1, max_total_bytes=100) is False


def test_jailed_folder_rejects_non_positive_id(tmp_path):
    root = str(tmp_path / "ticket_files")
    assert jailed_ticket_folder(0, root=root) is None
    assert jailed_ticket_folder(-3, root=root) is None
    assert jailed_ticket_folder("nope", root=root) is None


def test_save_rejects_eleventh_file_without_download(temp_db, tmp_path, monkeypatch):
    root = _media_root(tmp_path, monkeypatch)
    folder = root / "12"
    folder.mkdir()
    for i in range(TICKET_MEDIA_MAX_FILES):
        (folder / f"{i}.jpg").write_bytes(b"ok")

    bot = _DownloadBot(b"another")
    result = asyncio.run(save_ticket_media(bot, _photo_message(7), ticket_id=12))

    assert result is None
    assert bot.downloads == 0
    assert ticket_folder_usage(str(folder))[0] == TICKET_MEDIA_MAX_FILES


def test_save_rejects_when_declared_size_would_break_total_quota(temp_db, tmp_path, monkeypatch):
    from shop_bot.support_bot import ticket_media as tm

    monkeypatch.setattr(tm, "TICKET_MEDIA_MAX_TOTAL_BYTES", 100)
    root = _media_root(tmp_path, monkeypatch)
    folder = root / "13"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"x" * 80)

    bot = _DownloadBot(b"y" * 40)
    result = asyncio.run(save_ticket_media(bot, _photo_message(40), ticket_id=13))

    assert result is None
    assert bot.downloads == 0
    assert (folder / "a.jpg").is_file()
    assert ticket_folder_usage(str(folder)) == (1, 80)


def test_delete_ticket_removes_only_that_ticket_folder(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = _media_root(tmp_path, monkeypatch)
    ticket_id = database.create_support_ticket(50101, "квота")
    other_id = ticket_id + 1
    mine = Path(jailed_ticket_folder(ticket_id, root=str(root)))
    other = Path(jailed_ticket_folder(other_id, root=str(root)))
    mine.mkdir(parents=True)
    other.mkdir(parents=True)
    (mine / "shot.jpg").write_bytes(b"img")
    (other / "keep.jpg").write_bytes(b"keep")

    assert database.delete_ticket(ticket_id) is True
    assert database.get_ticket(ticket_id) is None
    assert not mine.exists()
    assert other.is_dir()
    assert (other / "keep.jpg").read_bytes() == b"keep"
    assert root.is_dir()


def test_delete_missing_ticket_does_not_touch_media_root(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = _media_root(tmp_path, monkeypatch)
    marker = root / "stay.txt"
    marker.write_text("ok")

    assert database.delete_ticket(999999) is False
    assert marker.is_file()
    assert root.is_dir()


def test_delete_ticket_media_dir_is_noop_without_folder(temp_db, tmp_path, monkeypatch):
    _media_root(tmp_path, monkeypatch)
    assert delete_ticket_media_dir(42) is True


def test_delete_user_removes_ticket_files(temp_db, tmp_path, monkeypatch):
    from shop_bot.data_manager import database

    root = _media_root(tmp_path, monkeypatch)
    user_id = 50102
    insert_user(database.DB_FILE, telegram_id=user_id, username="quota_user")
    ticket_id = database.create_support_ticket(user_id, "удаление")
    folder = Path(jailed_ticket_folder(ticket_id, root=str(root)))
    folder.mkdir(parents=True)
    (folder / "pay.jpg").write_bytes(b"secret")

    assert database.delete_user_completely(user_id) is True
    assert not folder.exists()
    assert database.get_ticket(ticket_id) is None
