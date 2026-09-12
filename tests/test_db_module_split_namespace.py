"""Регрессия на разделение `database.py` по доменным модулям `data_manager/db/`.

До разделения все функции лежали в одном модуле и читали `DB_FILE` и друг друга
по голому имени из одного словаря. На этом держатся подмены в тестах: фикстура
`temp_db` делает `monkeypatch.setattr(database, "DB_FILE", tmp_path / "test.db")`,
а отдельные тесты подменяют функции (например
`find_open_tickets_idle_after_admin`). Если запись в атрибут фасада перестанет
доходить до доменных модулей, тесты продолжат импортироваться без ошибок, но
начнут писать в боевую БД — падений не будет, поэтому инвариант проверяется здесь
явно.
"""
import ast
import sqlite3
from pathlib import Path

import pytest

from shop_bot.data_manager import database
from shop_bot.data_manager import db as db_package

DB_DIR = Path(database.__file__).parent / "db"

# Мутируемые в рантайме/тестах глобалы: значение нельзя копировать при импорте.
MUTABLE_GLOBALS = ("DB_FILE",)


def test_db_file_patch_reaches_every_domain_module(tmp_path, monkeypatch):
    db_path = tmp_path / "patched.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)

    stale = [m.__name__ for m in db_package.MODULES if m.__dict__.get("DB_FILE") != db_path]
    assert stale == [], f"модули не увидели подмену DB_FILE: {stale}"


def test_patched_db_file_is_where_data_is_written(tmp_path, monkeypatch):
    db_path = tmp_path / "written.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)

    database.initialize_db()
    database.register_user_if_not_exists(777001, "split-probe", None)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM users WHERE telegram_id = ?", (777001,)).fetchone()[0]
    assert count == 1


def test_db_file_is_restored_after_monkeypatch_teardown(temp_db):
    """После teardown фикстуры значение должно вернуться во все модули.

    Иначе следующий тест унаследовал бы путь предыдущего — ровно тот баг, что
    описан в docstring `remnawave_repository.__getattr__`.
    """
    stale = [m.__name__ for m in db_package.MODULES if m.__dict__.get("DB_FILE") != database.DB_FILE]
    assert stale == [], f"модули расходятся с фасадом: {stale}"


def test_function_patch_reaches_internal_caller(monkeypatch):
    """`auto_close_idle_admin_tickets` вызывает соседа по голому имени."""
    from shop_bot.data_manager.db import tickets

    sentinel = object()
    monkeypatch.setattr(database, "find_open_tickets_idle_after_admin", lambda *a, **k: sentinel)
    assert tickets.find_open_tickets_idle_after_admin() is sentinel


@pytest.mark.parametrize("module_path", sorted(DB_DIR.glob("*.py")), ids=lambda p: p.name)
def test_domain_modules_never_copy_mutable_globals_at_import(module_path):
    """Статический запрет на `from ._core import DB_FILE` и аналоги.

    Такой импорт скопировал бы значение один раз, на момент импорта модуля, и
    подмену в тестах он бы уже не увидел.
    """
    tree = ast.parse(module_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            copied = [a.name for a in node.names if a.name in MUTABLE_GLOBALS]
            assert not copied, f"{module_path.name}: импорт значения {copied} на уровне модуля"
        if isinstance(node, ast.Import):
            copied = [a.name for a in node.names if a.name in MUTABLE_GLOBALS]
            assert not copied, f"{module_path.name}: импорт значения {copied} на уровне модуля"


def test_facade_reexports_every_domain_name():
    missing = []
    for module in db_package.MODULES:
        for name in module.__all__:
            if not hasattr(database, name):
                missing.append(f"{module.__name__}.{name}")
    assert missing == [], f"фасад не ре-экспортирует: {missing}"


def test_unset_sentinel_is_shared_by_identity():
    """`_UNSET` сравнивается через `is`, поэтому копия объекта недопустима."""
    from shop_bot.data_manager.db import _core

    for module in db_package.MODULES:
        if "_UNSET" in module.__dict__:
            assert module._UNSET is _core._UNSET, module.__name__
    assert database._UNSET is _core._UNSET
