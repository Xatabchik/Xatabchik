"""Каталог вложений — рядом с users.db, не в webhook_server и не от cwd."""
from __future__ import annotations

from pathlib import Path

from shop_bot.data_manager import database
from shop_bot.support_bot.ticket_media import remove_empty_ticket_folder


def test_ticket_media_root_follows_absolute_db(tmp_path, monkeypatch):
    monkeypatch.delenv("TICKET_FILES_DIR", raising=False)
    db = tmp_path / "users.db"
    monkeypatch.setattr(database, "DB_FILE", db)
    assert Path(database.get_ticket_media_root()) == (tmp_path / "ticket_files").resolve()


def test_ticket_media_root_ignores_process_cwd(tmp_path, monkeypatch):
    """Раньше abspath(users.db) давал cwd/ticket_files — панель из webhook_server не видела файлы."""
    monkeypatch.delenv("TICKET_FILES_DIR", raising=False)
    monkeypatch.setattr(database, "DB_FILE", Path("users.db"))
    cwd = tmp_path / "webhook_server"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    root = Path(database.get_ticket_media_root())
    assert root != (cwd / "ticket_files").resolve()
    assert root.name == "ticket_files"
    assert root.is_absolute()
    assert "webhook_server" not in root.parts


def test_ticket_files_dir_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom_media"
    monkeypatch.setenv("TICKET_FILES_DIR", str(custom))
    assert Path(database.get_ticket_media_root()) == custom.resolve()


def test_remove_empty_ticket_folder_keeps_files(tmp_path):
    folder = tmp_path / "12"
    folder.mkdir()
    (folder / "keep.jpg").write_bytes(b"x")
    remove_empty_ticket_folder(str(folder))
    assert folder.is_dir()
    assert (folder / "keep.jpg").is_file()
    empty = tmp_path / "13"
    empty.mkdir()
    remove_empty_ticket_folder(str(empty))
    assert not empty.exists()
