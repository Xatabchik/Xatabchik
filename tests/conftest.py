"""Общие фикстуры для тестов."""
import sys
from pathlib import Path

import pytest

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Свежая SQLite БД во временном файле для каждого теста."""
    from shop_bot.data_manager import database

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    database.initialize_db()
    yield database
