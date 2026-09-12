"""Инварианты разделения webapp/handlers.py на пакет web_router.

До разделения все 211 определений Mini App лежали в одном пространстве имён:
функции обращались к соседям и к импортированным именам просто по имени, а
тесты подменяли эти имена записью атрибута в `shop_bot.webapp.handlers`.

После разделения то же поведение держится на трёх механизмах, каждый из
которых легко сломать незаметно:

* порядок импорта модулей в `web_router/__init__.py` задаёт порядок
  регистрации маршрутов, а FastAPI выбирает первый совпавший маршрут;
* `_link_namespace()` раскладывает определения модулей по остальным модулям;
* `broadcast()` разносит внешнюю запись атрибута фасада по доменным модулям.

Тесты ниже закрепляют именно это, а не поведение самих эндпоинтов.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import inspect
import json
import os
import subprocess
import sys
import symtable
from collections import deque
from pathlib import Path

import pytest

PKG = "shop_bot.webapp.web_router"
PKG_DIR = Path("src/shop_bot/webapp/web_router")
FACADE = "shop_bot.webapp.handlers"

# Состояние уровня модуля, которое conftest.reset_rate_limiters правит НА МЕСТЕ
# (`.reset()`, `.clear()`), а не переприсваиванием. Все модули обязаны видеть
# один и тот же объект, иначе сброс лимитов между тестами перестанет работать.
SHARED_MUTABLE = ("limiter", "_EMAIL_AUTH_HITS", "_SUPPORT_HITS", "_SUPPORT_LAST")

# Имена, которые нужны уже на этапе импорта (декораторы, аннотации, значения
# по умолчанию), поэтому импортируются значением из модуля-владельца. Сами эти
# модули маршрутов не регистрируют — это проверяет
# test_no_route_module_is_imported_by_value_inside_the_package.
VALUE_IMPORT_OWNERS = ("_core", "_app", "models")


def _facade():
    return importlib.import_module(FACADE)


def _pkg():
    return importlib.import_module(PKG)


def _py_files():
    return sorted(p for p in PKG_DIR.glob("*.py") if p.name != "__init__.py")


def _module(stem):
    return importlib.import_module(f"{PKG}.{stem}")


def _rebound_names():
    """Имена, которые тесты переприсваивают на модуле handlers.

    Набор считается из AST тестов, а не задан списком: новый тест, подменяющий
    новое имя, должен автоматически попадать под проверку рассылки.
    """
    names = set()
    for path in sorted(Path("tests").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_setattr = (
                (isinstance(func, ast.Name) and func.id == "setattr")
                or (isinstance(func, ast.Attribute) and func.attr == "setattr")
            )
            if not is_setattr or len(node.args) < 2:
                continue
            target, attr = node.args[0], node.args[1]
            if not (isinstance(target, ast.Name) and target.id == "handlers"):
                continue
            if isinstance(attr, ast.Constant) and isinstance(attr.value, str):
                names.add(attr.value)
    return names


def test_tests_really_do_rebind_names_on_the_facade():
    """Страховка на сам детектор: пустой набор обесценил бы проверки ниже."""
    names = _rebound_names()
    assert len(names) >= 10, f"детектор подмен нашёл слишком мало имён: {sorted(names)}"
    # Именно эти две категории вызывали сомнение: имя приходит в модуль обычным
    # импортом из внешнего пакета, а тест его переприсваивает на фасаде.
    assert {"Bot", "YookassaPayment"} <= names


def test_broadcast_reaches_every_module_that_holds_a_rebound_name():
    """Подмена на фасаде обязана дойти до всех модулей, где имя есть.

    Имя, попавшее в модуль обычным импортом значением (`from aiogram import
    Bot`), лежит в `__dict__` этого модуля, поэтому `broadcast()` его
    переприсваивает, а тела функций читают его через LOAD_GLOBAL и видят
    подмену — ровно как до разделения, когда модуль был один.
    """
    facade = _facade()
    pkg = _pkg()

    checked = 0
    for name in sorted(_rebound_names()):
        holders = [m for m in pkg.MODULES if name in m.__dict__]
        if not holders:
            continue
        checked += 1
        originals = {m: m.__dict__[name] for m in holders}
        facade_original = facade.__dict__[name]
        sentinel = object()
        try:
            setattr(facade, name, sentinel)
            missed = [m.__name__ for m in holders if m.__dict__[name] is not sentinel]
            assert missed == [], f"broadcast не дошёл до {missed} для имени {name}"
        finally:
            # Восстанавливать надо и фасад: запись в него и есть то, что
            # рассылается, поэтому иначе sentinel утечёт в следующие тесты.
            setattr(facade, name, facade_original)
            for m, value in originals.items():
                setattr(m, name, value)
        restored = [m.__name__ for m in holders if m.__dict__[name] is not originals[m]]
        assert restored == [], f"значение {name} не восстановлено в {restored}"
        assert facade.__dict__[name] is facade_original, f"фасад не восстановил {name}"

    assert checked >= 10, "проверено подозрительно мало подменяемых имён"


def _code_names(code, seen=None):
    """Все глобальные имена, которые читает код-объект и всё вложенное в него.

    Обход рекурсивный: обращение из вложенной функции или из comprehension
    попадает в `co_names` отдельного код-объекта, а не внешней функции.
    """
    seen = seen if seen is not None else set()
    seen.update(code.co_names)
    for const in code.co_consts:
        if hasattr(const, "co_names"):
            _code_names(const, seen)
    return seen


def _reads_global(module, name):
    for obj in vars(module).values():
        if getattr(obj, "__module__", None) != module.__name__:
            continue
        # `@limiter.limit(...)` подменяет функцию обёрткой slowapi, у которой
        # свой `__code__`; `functools.wraps` оставляет ссылку в `__wrapped__`.
        obj = inspect.unwrap(obj)
        code = getattr(obj, "__code__", None)
        if code is not None and name in _code_names(code):
            return True
    return False


def test_rebound_name_is_actually_read_through_the_module_namespace():
    """Имя должно читаться из `__dict__` модуля, а не быть мёртвым импортом.

    Без этой проверки предыдущий тест мог бы пройти на модулях, которые имя
    хранят, но нигде не используют, и настоящий читатель остался бы забытым.
    """
    pkg = _pkg()
    unused = []
    for name in sorted(_rebound_names()):
        holders = [m for m in pkg.MODULES if name in m.__dict__]
        if not holders:
            continue
        readers = [m.__name__ for m in holders if _reads_global(m, name)]
        if not readers:
            unused.append(name)
    assert unused == [], f"имена никто не читает через LOAD_GLOBAL: {unused}"


def test_patched_name_is_visible_inside_a_function_body(monkeypatch):
    """Сквозная проверка: подмена на фасаде меняет результат вызова.

    `_rollypay_is_enabled` живёт в `payments_common` и читает `get_setting`
    через LOAD_GLOBAL из своего модуля.
    """
    from shop_bot.webapp import handlers

    assert handlers._rollypay_is_enabled() is False

    monkeypatch.setattr(handlers, "get_setting", lambda key, *a, **k: "x")
    assert handlers._rollypay_is_enabled() is True, "тело функции не увидело подмену"

    monkeypatch.undo()
    assert handlers._rollypay_is_enabled() is False, "подмена не откатилась"


def test_shared_mutable_state_is_one_object_everywhere():
    """Состояние, которое правят на месте, обязано быть одним объектом.

    conftest.reset_rate_limiters вызывает `.reset()` и `.clear()`, а сами
    функции копят в этих контейнерах попытки авторизации и сообщения в
    поддержку. Разошлись копии — сброс между тестами перестанет работать, а
    лимиты начнут считаться по отдельности в каждом модуле.

    Набор берётся из `_core.__all__` по типу значения, а не списком, чтобы
    новое состояние попадало под проверку само.
    """
    facade = _facade()
    pkg = _pkg()
    core = _module("_core")

    mutable = [n for n in core.__all__
               if isinstance(getattr(core, n), (dict, list, set, deque))]
    assert set(SHARED_MUTABLE) - {"limiter"} <= set(mutable), (
        f"проверка потеряла состояние из conftest: {mutable}")

    for name in sorted(set(mutable) | set(SHARED_MUTABLE)):
        holders = [m for m in pkg.MODULES if name in m.__dict__]
        assert holders, f"{name} не попал ни в один модуль"
        ids = {id(m.__dict__[name]) for m in holders}
        assert len(ids) == 1, f"{name}: модули видят разные объекты"
        assert id(getattr(facade, name)) in ids, f"{name}: фасад видит другой объект"


def _intra_package_imports():
    """(файл, модуль-владелец, имя) для каждого значениевого импорта в пакете."""
    for path in _py_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if not module.startswith(PKG):
                continue
            for alias in node.names:
                yield path, module, alias.asname or alias.name


def test_value_imports_come_only_from_owners_without_routes():
    """Ранний импорт модуля с маршрутами сдвинул бы порядок регистрации."""
    allowed = {f"{PKG}.{m}" for m in VALUE_IMPORT_OWNERS}
    offenders = sorted({f"{p.name}: from {mod}"
                        for p, mod, _ in _intra_package_imports() if mod not in allowed})
    assert offenders == [], f"неразрешённый значениевый импорт внутри пакета: {offenders}"


def test_value_imported_names_are_really_needed_at_import_time():
    """Значением можно тянуть только то, что нужно раньше `_link_namespace()`.

    Это декораторы, аннотации, значения по умолчанию, базовые классы и код
    уровня модуля. Всё остальное обязано приходить рассылкой, иначе
    `broadcast()` обновит только модуль-владельца, а копия в импортёре
    останется прежней.
    """
    offenders = []
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        needed = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                parts = list(node.decorator_list) + list(args.defaults)
                parts += [a.annotation for a in
                          [*args.posonlyargs, *args.args, *args.kwonlyargs]
                          if a.annotation is not None]
                parts += [d for d in args.kw_defaults if d is not None]
                if node.returns is not None:
                    parts.append(node.returns)
            elif isinstance(node, ast.ClassDef):
                parts = list(node.bases) + list(node.keywords) + list(node.body)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            else:
                parts = [node]
            for part in parts:
                needed |= {n.id for n in ast.walk(part) if isinstance(n, ast.Name)}

        for p, module, name in _intra_package_imports():
            if p == path and name not in needed:
                offenders.append(f"{path.name}: {name} из {module} не нужен на импорте")
    assert offenders == [], offenders


def test_no_module_value_imports_a_name_that_tests_rebind():
    """Категорически запрещённый случай: значениевый импорт подменяемого имени.

    `broadcast()` переприсваивает имя в каждом модуле, где оно есть, поэтому
    сам по себе значениевый импорт подмену не ломает. Но имя, нужное уже на
    импорте, к моменту подмены успевает попасть в декоратор или аннотацию —
    там останется прежний объект. Держим два случая разделёнными: подменяемое
    имя не должно одновременно требоваться на этапе импорта.
    """
    rebound = _rebound_names()
    offenders = sorted({f"{p.name}: {name}"
                        for p, _, name in _intra_package_imports() if name in rebound})
    assert offenders == [], (
        f"подменяемое имя импортировано значением: {offenders}")


def test_no_route_module_is_imported_by_value_inside_the_package():
    """Ранний импорт модуля с маршрутами сдвинул бы порядок регистрации.

    `_core`, `_app` и `models` маршрутов не регистрируют, поэтому их можно
    тянуть значением. Если маршрут появится в одном из них — порядок начнёт
    зависеть от того, кто первым сделал значениевый импорт.
    """
    route_decorators = ("app.get", "app.post", "app.put", "app.patch",
                        "app.delete", "app.head", "app.options", "app.api_route")
    for stem in VALUE_IMPORT_OWNERS:
        source = (PKG_DIR / f"{stem}.py").read_text(encoding="utf-8")
        found = [
            n.name for n in ast.parse(source).body
            if any(ast.unparse(d).startswith(route_decorators)
                   for d in getattr(n, "decorator_list", []))
        ]
        assert found == [], f"{stem}.py регистрирует маршруты: {found}"


def test_module_provenance_is_not_shadowed():
    """Ловит перекрытие имён между модулями пакета.

    Если два модуля определят одно имя, `_link_namespace()` разложит по
    остальным то, которое встретится раньше, а фасад отдаст последнее из
    звёздочных импортов — расхождение, которое иначе никак не заметно.
    """
    pkg = _pkg()
    facade = _facade()

    owners: dict[str, list[str]] = {}
    for module in pkg.MODULES:
        for name in getattr(module, "__all__", ()):
            owners.setdefault(name, []).append(module.__name__)
    duplicated = {n: ms for n, ms in owners.items() if len(ms) > 1}
    assert duplicated == {}, f"имя определено в нескольких модулях: {duplicated}"

    # Атрибут пакета с именем модуля не должен затеняться его же экспортом.
    for module in pkg.MODULES:
        short = module.__name__.rsplit(".", 1)[1]
        assert getattr(pkg, short) is module, f"атрибут пакета {short} затенён"
    assert callable(pkg.broadcast)

    # Фасад отдаёт ровно тот объект, который определил модуль-владелец.
    mismatched = []
    for name, (owner,) in ((n, ms) for n, ms in owners.items() if len(ms) == 1):
        if not hasattr(facade, name):
            mismatched.append(f"{name}: нет на фасаде")
            continue
        if getattr(facade, name) is not getattr(sys.modules[owner], name):
            mismatched.append(f"{name}: фасад отдаёт не объект из {owner}")
    assert mismatched == [], mismatched


def test_shadowing_of_process_successful_payment_is_preserved():
    """В исходнике определение (строка 324) затиралось импортом (строка 381).

    Это мёртвый код, и разделение обязано сохранить именно импортированную
    функцию бота, а не локальную заглушку.
    """
    from shop_bot.bot import handlers as bot_handlers

    facade = _facade()
    assert facade.process_successful_payment is bot_handlers.process_successful_payment
    payments_common = _module("payments_common")
    assert (payments_common.process_successful_payment
            is bot_handlers.process_successful_payment)


def test_logger_name_stays_on_the_old_module():
    """Записи в логах должны остаться от 'shop_bot.webapp.handlers'."""
    assert _facade().logger.name == FACADE


def test_static_paths_still_resolve_to_the_webapp_directory():
    """Файл переехал в подпакет, каталоги шаблонов и статики — нет."""
    facade = _facade()
    webapp = Path("src/shop_bot/webapp").resolve()

    assert Path(facade.ico_dir).resolve() == webapp / "module" / "ico"
    assert Path(facade.uploads_dir).resolve() == webapp / "uploads"
    assert not (PKG_DIR / "uploads").exists(), "каталог загрузок создан в подпакете"
    for name in ("app.html", "login.html"):
        assert (webapp / name).exists(), f"{name} должен лежать рядом с фасадом"


def test_every_module_file_is_wired_into_the_package():
    """Модуль, забытый в `__init__.py`, молча унёс бы с собой свои маршруты.

    Файл на диске есть, тесты на разрешимость имён его читают, но ни один
    декоратор `@app.…` в нём не исполнится, потому что модуль никто не
    импортирует.
    """
    pkg = _pkg()
    wired = {m.__name__.rsplit(".", 1)[1] for m in pkg.MODULES}
    on_disk = {p.stem for p in _py_files()}
    assert wired == on_disk, (
        f"не подключены: {sorted(on_disk - wired)}; "
        f"подключены, но файла нет: {sorted(wired - on_disk)}")


def test_route_table_consists_of_endpoints_plus_the_usual_extras():
    """Разделяет два числа, которые легко перепутать при ревью.

    В `app.routes` попадают не только эндпоинты приложения: FastAPI сам
    добавляет схему и страницы документации, а `_app.py` монтирует статику.
    Поэтому записей в `app.routes` больше, чем функций с `@app.…`.
    """
    routes = _facade().app.routes
    extras = {(type(r).__name__, r.path) for r in routes
              if type(r).__name__ != "APIRoute"}
    assert extras == {
        ("Route", "/openapi.json"),
        ("Route", "/docs"),
        ("Route", "/docs/oauth2-redirect"),
        ("Route", "/redoc"),
        ("Mount", "/module/ico"),
        ("Mount", "/uploads"),
    }, f"изменился состав служебных маршрутов и монтирований: {sorted(extras)}"

    endpoints = [r for r in routes if type(r).__name__ == "APIRoute"]
    assert len(endpoints) + len(extras) == len(routes)


def test_catch_all_route_is_registered_last():
    """`@app.get('/{path_param}')` перехватывает всё, что до него не совпало."""
    facade = _facade()
    paths = [r.path for r in facade.app.routes if getattr(r, "path", None)]
    assert paths[-1] == "/{path_param}"
    assert paths.count("/{path_param}") == 1


def test_every_global_name_in_the_package_resolves():
    """Ловит NameError, который иначе выстрелил бы только на живом запросе."""
    _pkg()

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

        namespace = _module(path.stem).__dict__
        for name in used:
            if name not in namespace and not hasattr(builtins, name):
                unresolved.add(f"{path.name}: {name}")

    assert unresolved == set(), f"неразрешимые имена: {sorted(unresolved)}"


ROUTE_PROBE = """
import importlib, json, sys
sys.path.insert(0, "src")
mode = sys.argv[1]
if mode == "prod":
    # docker-compose: uvicorn shop_bot.webapp.handlers:app
    app = getattr(importlib.import_module("shop_bot.webapp.handlers"), "app")
elif mode == "test":
    # tests/conftest.py: сначала database, затем handlers
    importlib.import_module("shop_bot.data_manager.database")
    app = importlib.import_module("shop_bot.webapp.handlers").app
elif mode == "submodule":
    # доменный модуль с маршрутами импортирован раньше фасада
    importlib.import_module("shop_bot.webapp.web_router.public_pages")
    app = importlib.import_module("shop_bot.webapp.handlers").app
print(json.dumps([[getattr(r, "path", None), getattr(r, "name", None),
                   sorted(getattr(r, "methods", None) or [])] for r in app.routes]))
"""


@pytest.mark.parametrize("mode", ["prod", "test", "submodule"])
def test_route_order_is_the_same_for_every_entry_point(mode):
    """Порядок маршрутов не должен зависеть от того, кто импортировал первым.

    Продакшен входит через `uvicorn shop_bot.webapp.handlers:app`, тесты — через
    `conftest.py`, а значениевые импорты внутри пакета могут поднять доменный
    модуль раньше остальных. Во всех случаях `web_router/__init__.py`
    исполняется раньше любого подмодуля, поэтому порядок обязан совпасть.

    Каждый режим считается в отдельном процессе: в текущем модули уже лежат в
    `sys.modules`, и порядок импорта там уже не наблюдаем.
    """
    def routes(entry_point):
        out = subprocess.run([sys.executable, "-c", ROUTE_PROBE, entry_point],
                             capture_output=True, text=True, timeout=300,
                             cwd=os.getcwd())
        assert out.returncode == 0, out.stderr[-3000:]
        return json.loads(out.stdout.strip().splitlines()[-1])

    reference = routes("prod")
    assert reference[-1][0] == "/{path_param}", "catch-all оказался не последним"
    assert routes(mode) == reference
