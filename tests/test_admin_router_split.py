"""Инварианты разделения bot/admin_handlers.py на пакет admin_router.

До разделения всё лежало в одном пространстве имён: 288 хендлеров были
вложенными функциями фабрики `get_admin_router()` и обращались к соседям
просто по имени. Тесты ниже закрепляют то, что после разделения легко
сломать незаметно: состав публичного API фасада, рассылку подменённых
атрибутов по доменным модулям, разрешимость имён и порядок регистрации.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import symtable
from pathlib import Path

import pytest

from conftest import temp_db  # noqa: F401

PKG_DIR = Path("src/shop_bot/bot/admin_router")

# Имена уровня модуля, которые admin_handlers.py отдавал наружу до разделения.
FACADE_NAMES = (
    "AdminAccessMiddleware",
    "AdminModules",
    "AdminSettings",
    "Broadcast",
    "IsAdminFilter",
    "_is_true",
    "_mask_secret",
    "get_admin_router",
    "logger",
)

# `admin_plan_back` вызывается в `admin_plan_delete_cancel`, но не определён
# нигде в исходном admin_handlers.py: это был LOAD_GLOBAL -> NameError и до
# разделения. Разделение поведение не меняет, поэтому имя остаётся в списке
# ожидаемых. Любое НОВОЕ неразрешимое имя — регрессия переноса.
KNOWN_UNRESOLVED = {"admin_plan_back"}


def _pkg():
    return importlib.import_module("shop_bot.bot.admin_router")


def _facade():
    return importlib.import_module("shop_bot.bot.admin_handlers")


def _py_files():
    return sorted(p for p in PKG_DIR.glob("*.py") if p.name != "__init__.py")


def test_facade_reexports_everything_it_had_before_split():
    facade = _facade()
    core = importlib.import_module("shop_bot.bot.admin_router.core")
    router = importlib.import_module("shop_bot.bot.admin_router.router")

    for name in FACADE_NAMES:
        assert hasattr(facade, name), f"фасад потерял {name}"

    for name in FACADE_NAMES:
        if name == "get_admin_router":
            assert getattr(facade, name) is router.get_admin_router
        else:
            assert getattr(facade, name) is getattr(core, name), f"{name}: не тот объект"


def test_logger_name_stays_on_the_old_module():
    """Записи в логах должны остаться от 'shop_bot.bot.admin_handlers'."""
    assert _facade().logger.name == "shop_bot.bot.admin_handlers"


def test_setattr_on_facade_reaches_the_internal_caller():
    """Подмена атрибута фасада видна вложенному хендлеру и откатывается.

    `show_admin_menu` физически живёт в admin_router/menu.py и читает
    `get_admin_stats` через LOAD_GLOBAL из своего модуля, поэтому запись на
    фасад обязана дойти именно туда.
    """
    facade = _facade()
    menu = importlib.import_module("shop_bot.bot.admin_router.menu")

    assert "get_admin_stats" in menu.__dict__, "menu.py должен видеть get_admin_stats"
    original = facade.get_admin_stats
    sentinel = object()
    try:
        facade.get_admin_stats = sentinel
        assert menu.get_admin_stats is sentinel, "broadcast не дошёл до доменного модуля"
    finally:
        facade.get_admin_stats = original
    assert menu.get_admin_stats is original, "broadcast не откатил значение"


def test_monkeypatch_on_facade_propagates_and_restores(monkeypatch):
    """Тот же путь, но ровно так, как им пользуется существующий тест авторизации."""
    facade = _facade()
    menu = importlib.import_module("shop_bot.bot.admin_router.menu")
    original = menu.get_admin_stats

    def _spy():
        return {}

    monkeypatch.setattr(facade, "get_admin_stats", _spy)
    assert menu.get_admin_stats is _spy
    monkeypatch.undo()
    assert menu.get_admin_stats is original


def test_package_modules_are_not_shadowed_by_package_attributes():
    """Модуль с именем `broadcast` затенял бы функцию `broadcast()` пакета."""
    pkg = _pkg()
    for module in pkg.MODULES:
        short = module.__name__.rsplit(".", 1)[1]
        assert getattr(pkg, short) is module, f"атрибут пакета {short} затенён"
    assert callable(pkg.broadcast)


def test_no_module_imports_a_broadcast_managed_name_by_value():
    """Значениевый импорт рассылаемого имени не догонит подмену на фасаде.

    Поднятые на уровень модуля определения приходят соседям через
    `_link_namespace()`, а не через `from .core import ...`: иначе
    `broadcast()` обновил бы только модуль-владелец.
    """
    pkg = _pkg()
    shared = {n for m in pkg.MODULES for n in getattr(m, "__all__", ())}
    assert shared, "пакет должен что-то раскладывать по модулям"

    offenders = []
    for path in _py_files():
        owner_all = set(getattr(importlib.import_module(
            f"shop_bot.bot.admin_router.{path.stem}"), "__all__", ()))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not (node.module or "").startswith("shop_bot.bot.admin_router"):
                continue
            for alias in node.names:
                name = alias.asname or alias.name
                if name in shared and name not in owner_all:
                    offenders.append(f"{path.name}: {name}")
    assert offenders == []


def test_every_global_name_in_the_package_resolves():
    """Ловит NameError, который иначе выстрелил бы при нажатии кнопки."""
    pkg = _pkg()

    def load_globals(table, out):
        if table.get_type() != "module":
            for sym in table.get_symbols():
                if sym.is_global() and not sym.is_assigned():
                    out.add(sym.get_name())
        for child in table.get_children():
            load_globals(child, out)

    unresolved = set()
    for path in _py_files():
        source = path.read_text(encoding="utf-8")
        table = symtable.symtable(source, str(path), "exec")
        used: set[str] = set()
        load_globals(table, used)
        for sym in table.get_symbols():
            if sym.is_referenced() and not (sym.is_assigned() or sym.is_imported()):
                used.add(sym.get_name())

        namespace = importlib.import_module(
            f"shop_bot.bot.admin_router.{path.stem}").__dict__
        for name in used:
            if name not in namespace and not hasattr(builtins, name):
                unresolved.add(f"{path.name}: {name}")

    assert unresolved == {f"plans.py: {n}" for n in KNOWN_UNRESOLVED}, (
        "изменился набор неразрешимых имён — сломался перенос или починили "
        f"старый баг: {sorted(unresolved)}"
    )


@pytest.mark.parametrize(
    "event,expected",
    [("message", 83), ("callback_query", 205)],
)
def test_handler_counts_per_observer(temp_db, event, expected):
    """Сегмент, потерянный при сборке роутера, не проявился бы иначе никак."""
    router = _facade().get_admin_router()
    assert len(router.observers[event].handlers) == expected


def test_router_registers_every_segment_exactly_once():
    """Порядок и состав вызовов register_* в get_admin_router.

    В aiogram хендлеры одного типа события проверяются в порядке регистрации,
    поэтому и состав, и порядок значимы.
    """
    source = (PKG_DIR / "router.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    factory = next(n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "get_admin_router")
    called = [
        node.value.func.id
        for node in factory.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id.startswith("register_")
    ]
    imported = [
        alias.name
        for node in tree.body if isinstance(node, ast.ImportFrom)
        for alias in node.names if alias.name.startswith("register_")
    ]
    assert len(called) == 33
    assert len(set(called)) == len(called), "сегмент зарегистрирован дважды"
    assert called == imported, "порядок вызовов должен совпадать с порядком импортов"

    defined = set()
    for path in _py_files():
        module = importlib.import_module(f"shop_bot.bot.admin_router.{path.stem}")
        defined |= {n for n in vars(module) if n.startswith("register_")}
    assert defined == set(called), "не все register_* попадают в роутер"


def test_factory_body_only_wires_the_router():
    """Тела хендлеров не должны вернуться в get_admin_router.

    Фабрика снова стала короткой: создание роутера, фильтры, middleware,
    вызовы register_* и return.
    """
    source = (PKG_DIR / "router.py").read_text(encoding="utf-8")
    factory = next(n for n in ast.parse(source).body
                   if isinstance(n, ast.FunctionDef) and n.name == "get_admin_router")
    assert not [n for n in ast.walk(factory)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n is not factory]
