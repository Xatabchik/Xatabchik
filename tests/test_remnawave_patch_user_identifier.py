"""PATCH /api/users: тело запроса обязано нести идентификатор пользователя.

На 3.3.2 панель опознаёт пользователя по числовому `id`, на 2.8.1 — по `uuid`.
`update_user_traffic_limit` посылала только `uuid`, поэтому на 3.3.2 докупка
трафика падала с 400 'At least one of username, id must be provided', а бот
откатывал платёж и возвращал деньги:

    TOPUP_ROLLBACK ... action=traffic_gb_topup reason=remnawave_limit_update_failed

Структурный тест внизу проходит по всем местам PATCH /api/users, а не только по
починенному: новый вызов без идентификатора должен ломать тест сразу.
"""
import ast
import asyncio
from pathlib import Path

import pytest

from shop_bot.modules import remnawave_api as api

PANEL_USER_ID = "117"
PANEL_UUID = "00000000-0000-4000-8000-000000000001"
SHORT_UUID = "abc12XYZ"
NEW_LIMIT = 32212254720

API_SOURCE = "src/shop_bot/modules/remnawave_api.py"
IDENTIFIER_KEYS = {"uuid", "id", "username"}
IDENTIFIER_HELPER = "_user_patch_identifier"


class _Resp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _patch_recorder(monkeypatch, attr: str = "_request_for_host"):
    """Подменяет транспорт и возвращает список отправленных PATCH-тел."""
    sent: list[dict] = []

    async def transport(*args, **kw):
        method, path = (args[1], args[2]) if attr == "_request_for_host" else (args[0], args[1])
        assert method == "PATCH"
        assert path == "/api/users"
        sent.append(kw.get("json_payload") or {})
        return _Resp({"response": {"ok": True}}, 200)

    monkeypatch.setattr(api, attr, transport)
    return sent


def test_update_traffic_limit_sends_numeric_id_on_v3(monkeypatch):
    """Ровно тот случай из лога: в ключе хранится 117, панель ждёт id."""
    sent = _patch_recorder(monkeypatch)
    ok = asyncio.run(
        api.update_user_traffic_limit(PANEL_USER_ID, NEW_LIMIT, host_name="test-host")
    )

    assert ok is True
    assert sent == [{"id": 117, "trafficLimitBytes": NEW_LIMIT}]


def test_update_traffic_limit_sends_uuid_on_v2(monkeypatch):
    sent = _patch_recorder(monkeypatch)
    ok = asyncio.run(
        api.update_user_traffic_limit(PANEL_UUID, NEW_LIMIT, host_name="test-host")
    )

    assert ok is True
    assert sent == [{"uuid": PANEL_UUID, "trafficLimitBytes": NEW_LIMIT}]


def test_update_traffic_limit_without_host_also_sends_identifier(monkeypatch):
    """Ветка без host_name идёт через глобальный _request и правится так же."""
    sent = _patch_recorder(monkeypatch, attr="_request")
    ok = asyncio.run(api.update_user_traffic_limit(PANEL_USER_ID, NEW_LIMIT))

    assert ok is True
    assert sent == [{"id": 117, "trafficLimitBytes": NEW_LIMIT}]


def test_update_traffic_limit_ignores_empty_ref(monkeypatch):
    sent = _patch_recorder(monkeypatch)
    assert asyncio.run(api.update_user_traffic_limit("", NEW_LIMIT, host_name="h")) is False
    assert sent == []


@pytest.mark.parametrize(
    "squad_ref, expected",
    [(PANEL_USER_ID, {"id": 117}), (PANEL_UUID, {"uuid": PANEL_UUID})],
)
def test_active_squads_identifier_unchanged(monkeypatch, squad_ref, expected):
    """Общий хелпер не должен менять поведение set_user_active_squads."""
    sent = _patch_recorder(monkeypatch)
    squads = ["squad-a", "squad-b"]
    ok = asyncio.run(api.set_user_active_squads(squad_ref, squads, host_name="test-host"))

    assert ok is True
    assert sent == [{**expected, "activeInternalSquads": squads}]


@pytest.mark.parametrize(
    "user_ref, expected",
    [
        (PANEL_USER_ID, {"id": 117}),
        (PANEL_UUID, {"uuid": PANEL_UUID}),
        (SHORT_UUID, {"uuid": SHORT_UUID}),
        ("  117  ", {"id": 117}),
    ],
)
def test_identifier_helper(user_ref, expected):
    assert api._user_patch_identifier(user_ref) == expected


def _nodes_outside_nested_functions(func: ast.AST):
    """Узлы тела функции без вложенных def — чтобы область видимости была точной."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _assignments(own_nodes):
    """Присваивания функции как пары (цель, значение) — Assign и AnnAssign вместе."""
    for node in own_nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                yield target, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            yield node.target, node.value


def _names_from_panel_response(own_nodes) -> set[str]:
    """Имена, значение которых пришло из ответа панели (через .get)."""
    names = set()
    for target, value in _assignments(own_nodes):
        if not isinstance(target, ast.Name):
            continue
        for node in ast.walk(value):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
            ):
                names.add(target.id)
                break
    return names


def _identifier_sources(own_nodes, payload_name: str):
    """Выражения, которыми в payload попадают ключи uuid/id/username."""
    for target, value in _assignments(own_nodes):
        # payload["uuid"] = <expr>
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == payload_name
            and isinstance(target.slice, ast.Constant)
            and target.slice.value in IDENTIFIER_KEYS
        ):
            yield value
        # payload = {"uuid": <expr>, ...} либо payload = <expr>
        elif isinstance(target, ast.Name) and target.id == payload_name:
            literal_keys = False
            for node in ast.walk(value):
                if not isinstance(node, ast.Dict):
                    continue
                for key, item in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in IDENTIFIER_KEYS:
                        literal_keys = True
                        yield item
            if not literal_keys:
                yield value


def _is_version_aware(value: ast.AST, panel_names: set[str]) -> bool:
    """Идентификатор допустим: из хелпера либо из ответа панели, но не из ref как есть."""
    for node in ast.walk(value):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == IDENTIFIER_HELPER:
                return True
        if isinstance(node, ast.Name) and node.id in panel_names:
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
        ):
            return True
    return False


def _patch_calls_with_raw_identifier(path: str) -> list[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    problems = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        own = list(_nodes_outside_nested_functions(func))
        panel_names = _names_from_panel_response(own)

        for node in own:
            if not isinstance(node, ast.Call):
                continue
            args = [a for a in node.args if isinstance(a, ast.Constant)]
            if not any(a.value == "PATCH" for a in args):
                continue
            if not any(a.value == "/api/users" for a in args):
                continue
            payload = next(
                (kw.value for kw in node.keywords if kw.arg == "json_payload"), None
            )
            if not isinstance(payload, ast.Name):
                continue

            sources = list(_identifier_sources(own, payload.id))
            if not sources:
                problems.append(
                    f"{path}:{node.lineno} в {func.name}() — payload {payload.id} без id/uuid/username"
                )
            elif not any(_is_version_aware(src, panel_names) for src in sources):
                problems.append(
                    f"{path}:{node.lineno} в {func.name}() — идентификатор payload {payload.id} "
                    f"взят напрямую, минуя {IDENTIFIER_HELPER}()"
                )
    return problems


def test_every_user_patch_resolves_identifier_by_panel_version():
    """Идентификатор в PATCH берётся из хелпера или из ответа панели, но не из ref как есть.

    Сохранённый ref — это либо uuid (2.8.1), либо число (3.3.2), и отправлять его
    всегда как `uuid` нельзя: на 3.3.2 панель отвечает 400, а бот считает это
    сбоем оплаты и откатывает платёж.
    """
    problems = _patch_calls_with_raw_identifier(API_SOURCE)
    assert problems == [], "PATCH /api/users с неверным идентификатором:\n" + "\n".join(problems)
