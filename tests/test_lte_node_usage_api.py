"""Точный учёт LTE-трафика по нодам: мост «сквад -> ноды» и версионно-толерантная цепочка.

Фикстуры повторяют РЕАЛЬНЫЕ формы ответов двух сред, снятые с контракта
remnawave/backend по тегам:

  2.8.1 — секции bandwidth-stats/internal-squads нет (404); per-user статистика
          живёт по UUID (`GET /api/bandwidth-stats/users/{userUuid}` -> series/topNodes)
          и в legacy-варианте (`.../legacy` -> плоские строки userUuid/nodeUuid/total).
  3.3.2 — есть squad-scoped путь
          (`GET /api/bandwidth-stats/internal-squads/{squad}/users/{userId}/usage`
          -> days[].nodes[]{uuid,totalBytes}); per-user путь ключуется числовым id,
          секции LEGACY нет (404).

Тесты покрывают обе ветки цепочки, а не только ту, что сработает на тестовой
панели, — иначе ветка, нужная проду, осталась бы непроверенной до первого запуска.
"""
import asyncio
from datetime import datetime

import pytest

from conftest import temp_db  # noqa: F401

GB = 1024 ** 3
START = datetime(2026, 8, 1)
END = datetime(2026, 8, 20)


class _Resp:
    def __init__(self, payload, status: int = 200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _restore_transport():
    """Тесты подменяют транспорт модуля — возвращаем оригинал, чтобы патч не утёк дальше."""
    from shop_bot.modules import remnawave_api

    original = remnawave_api._request_for_host
    yield
    remnawave_api._request_for_host = original
    remnawave_api.invalidate_squad_nodes_cache()
    remnawave_api.reset_usage_path_cache()


def _api():
    from shop_bot.modules import remnawave_api

    remnawave_api.invalidate_squad_nodes_cache()
    remnawave_api.reset_usage_path_cache()
    return remnawave_api


def _host(database, name: str, *, squads: dict[str, str], base_url="https://panel.example"):
    """Хост с указанными сквадами: {'lte': uuid, 'base': uuid}."""
    database.create_host(name, base_url, "", "", 0)
    database.update_host_remnawave_settings(
        name, remnawave_base_url=base_url, remnawave_api_token="tok"
    )
    for squad_class, squad_uuid in squads.items():
        database.add_host_squad(name, squad_uuid, squad_class, squad_class.upper())


def _accessible_nodes_payload(squad_uuid: str, nodes: list[tuple[str, str]]):
    """Форма ответа accessible-nodes (идентична в 2.8.1 и 3.3.2)."""
    return {
        "response": {
            "squadUuid": squad_uuid,
            "accessibleNodes": [
                {
                    "uuid": uuid,
                    "nodeName": name,
                    "countryCode": "DE",
                    "configProfileUuid": "cfg-1",
                    "configProfileName": "default",
                    "activeInbounds": ["inbound-1"],
                }
                for uuid, name in nodes
            ],
        }
    }


def _router(api, routes, *, calls: list[str] | None = None):
    """Подменяет транспорт: routes — список (подстрока пути, _Resp)."""

    async def fake_request(host_name, method, path, *, params=None, json_payload=None,
                           expected_status=(200,)):
        if calls is not None:
            calls.append(path)
        for pattern, resp in routes:
            if pattern in path:
                if resp.status_code not in expected_status:
                    raise api.RemnawaveAPIError(f"HTTP {resp.status_code} на {path}")
                return resp
        raise AssertionError(f"неожиданный путь в тесте: {path}")

    api._request_for_host = fake_request


# --- мост «сквад -> ноды» ---------------------------------------------------


def test_lte_nodes_resolved_through_squad_uuid(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [("/accessible-nodes", _Resp(_accessible_nodes_payload(
        "squad-lte", [("n1", "DE-1"), ("n2", "NL-1")])))], calls=calls)

    assert asyncio.run(api.get_lte_node_uuids_for_host("H")) == ["n1", "n2"]
    assert calls == ["/api/internal-squads/squad-lte/accessible-nodes"]
    assert [n["node_name"] for n in asyncio.run(api.get_lte_nodes_for_host("H"))] == ["DE-1", "NL-1"]


def test_lte_nodes_cached_by_squad_uuid(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [("/accessible-nodes", _Resp(_accessible_nodes_payload("squad-lte", [("n1", "DE-1")])))], calls=calls)

    asyncio.run(api.get_lte_node_uuids_for_host("H"))
    asyncio.run(api.get_lte_node_uuids_for_host("H"))
    assert len(calls) == 1, "второй вызов должен читаться из кэша"

    api.invalidate_squad_nodes_cache("squad-lte")
    asyncio.run(api.get_lte_node_uuids_for_host("H"))
    assert len(calls) == 2


def test_missing_lte_squad_is_empty_list_not_error(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"base": "squad-base"})
    _router(api, [("/accessible-nodes", _Resp(_accessible_nodes_payload("squad-base", [("n1", "DE-1")])))])

    assert asyncio.run(api.get_lte_node_uuids_for_host("H")) == []


def test_api_failure_raises_instead_of_empty_list(temp_db):
    """«Не удалось узнать» обязано отличаться от «нод нет», иначе получим нулевой расход."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [("/accessible-nodes", _Resp({"error": "boom"}, 500))])

    with pytest.raises(api.RemnawaveAPIError):
        asyncio.run(api.get_lte_node_uuids_for_host("H"))


def test_two_hosts_on_same_panel_resolve_independently(temp_db):
    """Два host_name с одинаковыми base_url/token — одна панель, но разные сквады.

    host_name — только ключ маршрутизации, поэтому списки нод не должны смешиваться,
    а общий сквад двух хостов обязан переиспользовать один кэш.
    """
    database, api = temp_db, _api()
    _host(database, "Host-A", squads={"lte": "squad-a"})
    _host(database, "Host-B", squads={"lte": "squad-b"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/squad-a/", _Resp(_accessible_nodes_payload("squad-a", [("a1", "A-1")]))),
        ("/internal-squads/squad-b/", _Resp(_accessible_nodes_payload("squad-b", [("b1", "B-1")]))),
    ], calls=calls)

    assert asyncio.run(api.get_lte_node_uuids_for_host("Host-A")) == ["a1"]
    assert asyncio.run(api.get_lte_node_uuids_for_host("Host-B")) == ["b1"]
    assert len(calls) == 2, "разные сквады -> разные записи кэша"

    # Третий хост той же панели, указывающий на сквад A: кэш по squad_uuid переиспользуется.
    _host(database, "Host-C", squads={"lte": "squad-a"})
    assert asyncio.run(api.get_lte_node_uuids_for_host("Host-C")) == ["a1"]
    assert len(calls) == 2, "общий squad_uuid не должен приводить к новому запросу"


# --- пересечение сквадов ----------------------------------------------------


def test_squad_overlap_detected_and_persisted_without_blocking(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"base": "squad-base", "lte": "squad-lte"})
    _router(api, [
        ("/internal-squads/squad-base/", _Resp(_accessible_nodes_payload(
            "squad-base", [("shared", "SHARED"), ("only-base", "BASE-1")]))),
        ("/internal-squads/squad-lte/", _Resp(_accessible_nodes_payload(
            "squad-lte", [("shared", "SHARED"), ("only-lte", "LTE-1")]))),
    ])

    overlap = asyncio.run(api.refresh_host_squad_overlap("H"))

    assert [n["uuid"] for n in overlap] == ["shared"]
    assert database.get_host_squad_overlap("H") == [{"uuid": "shared", "node_name": "SHARED"}]
    # Сквады остались на месте: обнаружение пересечения ничего не блокирует и не удаляет.
    assert {s["squad_class"] for s in database.get_host_squads("H")} == {"base", "lte"}


def test_no_overlap_is_recorded_as_checked_empty(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"base": "squad-base", "lte": "squad-lte"})
    _router(api, [
        ("/internal-squads/squad-base/", _Resp(_accessible_nodes_payload("squad-base", [("b1", "B-1")]))),
        ("/internal-squads/squad-lte/", _Resp(_accessible_nodes_payload("squad-lte", [("l1", "L-1")]))),
    ])

    assert asyncio.run(api.refresh_host_squad_overlap("H")) == []
    assert database.get_host_squad_overlap("H") == []


# --- цепочка путей: 3.3.2 ---------------------------------------------------


def _usage(api, host="H", squad="squad-lte", nodes=("n1", "n2"), user="user-uuid-1"):
    return asyncio.run(api.get_user_node_usage_for_squad(
        user, host_name=host, squad_uuid=squad, node_uuids=list(nodes),
        start_date=START, end_date=END, panel_user_id=4242,
    ))


SQUAD_SCOPED_332 = ("/bandwidth-stats/internal-squads/squad-lte/users/4242/usage", _Resp({
    "response": {"days": [
        {"date": "2026-08-01", "nodes": [{"uuid": "n1", "totalBytes": 3 * GB},
                                         {"uuid": "n2", "totalBytes": 1 * GB}]},
        {"date": "2026-08-02", "nodes": [{"uuid": "n1", "totalBytes": 2 * GB}]},
        # Нода вне LTE-сквада не должна попасть в расход.
        {"date": "2026-08-03", "nodes": [{"uuid": "foreign", "totalBytes": 90 * GB}]},
    ]}
}))

USER_BY_ID_332 = ("/bandwidth-stats/users/4242", _Resp({
    "response": {
        "categories": ["2026-08-01"],
        "sparklineData": [1],
        "topNodes": [{"uuid": "n1", "color": "#1", "name": "DE-1", "countryCode": "DE", "total": 4 * GB}],
        "series": [
            {"uuid": "n1", "name": "DE-1", "color": "#1", "countryCode": "DE", "total": 4 * GB, "data": []},
            {"uuid": "n2", "name": "NL-1", "color": "#2", "countryCode": "NL", "total": 2 * GB, "data": []},
            {"uuid": "base-node", "name": "BASE", "color": "#3", "countryCode": "DE", "total": 80 * GB, "data": []},
        ],
    }
}))


def test_chain_uses_squad_scoped_path_on_332(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [SQUAD_SCOPED_332], calls=calls)

    result = _usage(api)

    assert result.path == api.USAGE_PATH_SQUAD_SCOPED
    assert result.per_node == {"n1": 5 * GB, "n2": 1 * GB}
    assert len(calls) == 1, "при успехе первого пути остальные не запрашиваются"


def test_chain_falls_back_to_user_by_id_when_squad_scoped_absent(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        USER_BY_ID_332,
    ])

    result = _usage(api)

    assert result.path == api.USAGE_PATH_USER_BY_ID
    # base-нода отфильтрована списком нод LTE-сквада; series/topNodes не удвоили n1.
    assert result.per_node == {"n1": 4 * GB, "n2": 2 * GB}


# --- цепочка путей: 2.8.1 ---------------------------------------------------


USER_BY_UUID_281 = ("/bandwidth-stats/users/user-uuid-1", _Resp({
    "response": {
        "categories": ["2026-08-01"],
        "sparklineData": [1],
        "topNodes": [],
        "series": [
            {"uuid": "n1", "name": "DE-1", "color": "#1", "countryCode": "DE", "total": 7 * GB, "data": []},
            {"uuid": "n2", "name": "NL-1", "color": "#2", "countryCode": "NL", "total": 1 * GB, "data": []},
        ],
    }
}))

USER_LEGACY_281 = ("/bandwidth-stats/users/user-uuid-1/legacy", _Resp({
    "response": [
        {"userUuid": "user-uuid-1", "nodeUuid": "n1", "nodeName": "DE-1", "countryCode": "DE",
         "total": 5 * GB, "date": "2026-08-01T00:00:00Z"},
        {"userUuid": "user-uuid-1", "nodeUuid": "n2", "nodeName": "NL-1", "countryCode": "NL",
         "total": 2 * GB, "date": "2026-08-01T00:00:00Z"},
        # Строки другого пользователя обязаны отфильтроваться.
        {"userUuid": "другой-user", "nodeUuid": "n1", "nodeName": "DE-1", "countryCode": "DE",
         "total": 99 * GB, "date": "2026-08-01T00:00:00Z"},
    ]
}))


def test_chain_uses_user_by_uuid_on_281(temp_db):
    """2.8.1: squad-scoped отсутствует (404), числовой id отвергается (400) -> путь по UUID."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        ("/bandwidth-stats/users/4242", _Resp({"message": "uuid expected"}, 400)),
        USER_BY_UUID_281,
    ], calls=calls)

    result = _usage(api)

    assert result.path == api.USAGE_PATH_USER_BY_UUID
    assert result.per_node == {"n1": 7 * GB, "n2": 1 * GB}
    assert any("4242" in c for c in calls), "числовой id должен быть проверен до UUID"


def test_chain_uses_legacy_rows_on_281(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        ("/bandwidth-stats/users/4242", _Resp(None, 404)),
        ("/bandwidth-stats/users/user-uuid-1/legacy", USER_LEGACY_281[1]),
        ("/bandwidth-stats/users/user-uuid-1", _Resp({"response": {"series": [], "topNodes": []}})),
    ])

    result = _usage(api)

    assert result.path == api.USAGE_PATH_USER_LEGACY
    assert result.per_node == {"n1": 5 * GB, "n2": 2 * GB}


def test_unsupported_path_decision_is_cached_per_panel_instance(temp_db):
    """404 запоминается по инстансу панели (base_url), а не переспрашивается каждый раз."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        USER_BY_ID_332,
    ], calls=calls)

    _usage(api)
    first_pass = [c for c in calls if "internal-squads" in c and "/users/" in c]
    _usage(api)
    second_pass = [c for c in calls if "internal-squads" in c and "/users/" in c]

    assert len(first_pass) == 1
    assert len(second_pass) == 1, "неподдерживаемый путь не должен зондироваться повторно"


# --- отказоустойчивость -----------------------------------------------------


def test_no_working_path_raises_instead_of_zero(temp_db):
    """Ни один путь не дал данных -> явная ошибка, а не нулевой расход."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        ("/bandwidth-stats/users/", _Resp(None, 404)),
        ("/bandwidth-stats/nodes/users", _Resp(None, 404)),
        ("/usage/range", _Resp(None, 404)),
    ])

    with pytest.raises(api.RemnawavePathUnsupportedError):
        _usage(api)


def test_server_error_is_strict_fail_safe(temp_db):
    """5xx — не повод идти к следующему кандидату: пробрасываем ошибку наверх."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [("/internal-squads/squad-lte/users/", _Resp({"e": "boom"}, 500))], calls=calls)

    with pytest.raises(api.RemnawaveAPIError):
        _usage(api)
    assert len(calls) == 1, "после 5xx остальные пути не опрашиваются"


def test_empty_node_list_short_circuits(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [])

    result = asyncio.run(api.get_user_node_usage_for_squad(
        "user-uuid-1", host_name="H", squad_uuid="squad-lte", node_uuids=[],
        start_date=START, end_date=END,
    ))
    assert result.per_node == {} and result.path == "none"


def test_failing_squad_is_negatively_cached(temp_db):
    """Битый squad_uuid не опрашивается заново на каждый ключ того же сквада,
    но ошибка всё равно пробрасывается (не превращается в пустой список)."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-broken"})
    calls: list[str] = []

    async def failing(host_name, method, path, **kw):
        calls.append(path)
        raise api.RemnawaveAPIError("HTTP 500 {'errorCode': 'A154'}")

    api._request_for_host = failing

    for _ in range(5):
        with pytest.raises(api.RemnawaveAPIError):
            asyncio.run(api.get_lte_node_uuids_for_host("H"))
    assert len(calls) == 1, "повторные обращения должны читаться из негативного кэша"

    api.invalidate_squad_nodes_cache("squad-broken")
    with pytest.raises(api.RemnawaveAPIError):
        asyncio.run(api.get_lte_node_uuids_for_host("H"))
    assert len(calls) == 2


def test_numeric_identifier_used_without_extra_request(temp_db):
    """3.3.2 не отдаёт uuid у пользователя, поэтому remnawave_user_uuid хранит числовой id —
    берём его напрямую, без запроса к панели."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []

    async def transport(host_name, method, path, **kw):
        calls.append(path)
        raise AssertionError("для числового id обращение к панели не требуется")

    api._request_for_host = transport

    assert asyncio.run(api.resolve_panel_user_id("64", host_name="H")) == 64
    assert calls == []


def test_auth_error_is_reported_as_auth_not_missing_squad(temp_db):
    """403 от панели — это авторизация, а не «сквада нет»: сообщение должно вести
    администратора к API-токену и его скоупам, а не к проверке UUID."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [("/accessible-nodes", _Resp(
        {"message": "Forbidden resource", "error": "Forbidden", "statusCode": 403}, 403))])

    with pytest.raises(api.RemnawaveAPIError) as exc:
        asyncio.run(api.get_lte_node_uuids_for_host("H"))
    text = str(exc.value)
    assert "403" in text and "токен" in text.lower()
    assert "не найден" not in text


def test_missing_squad_is_reported_as_404(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [("/accessible-nodes", _Resp({"statusCode": 404}, 404))])

    with pytest.raises(api.RemnawaveAPIError) as exc:
        asyncio.run(api.get_lte_node_uuids_for_host("H"))
    assert "не найден" in str(exc.value)


def test_auth_error_does_not_zero_usage_or_disable_key(temp_db):
    """403 не должен трактоваться как «путь не поддерживается» и обнулять расход:
    иначе отозванный токен молча выключил бы учёт LTE у всех."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    _router(api, [
        ("/accessible-nodes", _Resp({"response": {"squadUuid": "squad-lte", "accessibleNodes": [
            {"uuid": "n1", "nodeName": "DE-1", "countryCode": "DE",
             "configProfileUuid": "c", "configProfileName": "d", "activeInbounds": []}]}})),
        ("/bandwidth-stats/", _Resp({"message": "Forbidden resource", "statusCode": 403}, 403)),
    ])

    with pytest.raises(api.RemnawaveAPIError):
        _usage(api, nodes=("n1",))


# --- снятие/возврат LTE-сквада -----------------------------------------------

BASE_SQUAD = "8249a32f-8bda-4d7b-9267-2b453bbad542"
LTE_SQUAD = "9a356172-ac82-49a1-90e9-a101d514bf03"


def _user_response(squads=(BASE_SQUAD, LTE_SQUAD), *, numeric_id=53):
    """Форма ответа панели: activeInternalSquads — массив ОБЪЕКТОВ (2.8.1 и 3.3.2)."""
    return {"response": {
        "id": numeric_id,
        "shortUuid": "eQs2-NcvuD8XHXAh",
        "activeInternalSquads": [{"uuid": u, "name": f"squad-{u[:4]}"} for u in squads],
    }}


def _squad_router(api, calls):
    async def transport(host_name, method, path, *, json_payload=None, params=None,
                        expected_status=(200,)):
        calls.append((method, path, json_payload))
        return _Resp(_user_response())

    api._request_for_host = transport


def test_active_squads_parsed_from_objects(temp_db):
    _, api = temp_db, _api()
    payload = _user_response()["response"]
    assert api.extract_active_squad_uuids(payload) == [BASE_SQUAD, LTE_SQUAD]
    # Совместимость: если панель когда-нибудь отдаст массив строк — тоже понимаем.
    assert api.extract_active_squad_uuids({"activeInternalSquads": [LTE_SQUAD]}) == [LTE_SQUAD]
    assert api.extract_active_squad_uuids(None) == []


def test_remove_squad_actually_patches_panel(temp_db):
    """Регрессия: сравнение строки с объектами давало ложный «уже снят», и LTE-сквад
    оставался в подписке при исчерпании лимита."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": LTE_SQUAD})
    calls: list[tuple] = []
    _squad_router(api, calls)

    assert asyncio.run(api.remove_squad_from_user("53", LTE_SQUAD, host_name="H")) is True

    patches = [c for c in calls if c[0] == "PATCH"]
    assert len(patches) == 1, "PATCH обязан уйти в панель"
    body = patches[0][2]
    assert body["activeInternalSquads"] == [BASE_SQUAD], "LTE снят, base сохранён"
    # 3.3.2: у пользователя нет uuid, идентификация по числовому id.
    assert body == {"id": 53, "activeInternalSquads": [BASE_SQUAD]}


def test_remove_squad_uses_uuid_identity_on_281(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": LTE_SQUAD})
    calls: list[tuple] = []
    _squad_router(api, calls)

    uuid_ident = "c0ffee00-1111-2222-3333-444444444444"
    asyncio.run(api.remove_squad_from_user(uuid_ident, LTE_SQUAD, host_name="H"))

    body = [c for c in calls if c[0] == "PATCH"][0][2]
    assert body == {"uuid": uuid_ident, "activeInternalSquads": [BASE_SQUAD]}


def test_remove_absent_squad_is_idempotent_without_patch(temp_db):
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": LTE_SQUAD})
    calls: list[tuple] = []
    _squad_router(api, calls)

    assert asyncio.run(api.remove_squad_from_user("53", "нет-такого-сквада", host_name="H")) is True
    assert [c for c in calls if c[0] == "PATCH"] == []


def test_add_squad_sends_uuid_strings_only(temp_db):
    """В PATCH уходят строки-UUID, а не объекты из ответа панели."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": LTE_SQUAD})
    calls: list[tuple] = []

    async def transport(host_name, method, path, *, json_payload=None, params=None,
                        expected_status=(200,)):
        calls.append((method, path, json_payload))
        return _Resp(_user_response(squads=(BASE_SQUAD,)))

    api._request_for_host = transport

    assert asyncio.run(api.add_squad_to_user("53", LTE_SQUAD, host_name="H")) is True
    body = [c for c in calls if c[0] == "PATCH"][0][2]
    assert body["activeInternalSquads"] == [BASE_SQUAD, LTE_SQUAD]
    assert all(isinstance(x, str) for x in body["activeInternalSquads"])


def test_query_window_includes_next_day_for_timezone_skew(temp_db):
    """Верхняя граница диапазона — сутки вперёд: панель агрегирует по датам своего
    часового пояса, и расход текущих суток не должен теряться на границе."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    seen: dict = {}

    async def transport(host_name, method, path, *, params=None, json_payload=None,
                        expected_status=(200,)):
        seen.update(params or {})
        return _Resp({"response": {"days": [
            {"date": "2026-08-20", "nodes": [{"uuid": "n1", "totalBytes": GB}]}]}})

    api._request_for_host = transport
    _usage(api, nodes=("n1",))

    assert seen["start"] == "2026-08-01"
    assert seen["end"] == "2026-08-21", "END должен быть на сутки больше запрошенного"


def test_zero_usage_is_a_valid_answer_not_a_failure(temp_db):
    """Панель ответила по рабочему пути, но расхода за период нет — это значимый нуль.

    Раньше пустой ответ считался «путь не сработал», цепочка доходила до конца и бросала
    ошибку, из-за чего ключ без трафика на LTE-нодах вечно пропускался с предупреждением
    и никогда не получал точку отсчёта.
    """
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp({"response": {"days": []}})),
        ("/bandwidth-stats/users/", _Resp({"response": {"series": [], "topNodes": []}})),
        ("/bandwidth-stats/nodes/users", _Resp(None, 404)),
        ("/usage/range", _Resp(None, 404)),
    ], calls=calls)

    result = _usage(api, nodes=("n1",))

    assert result.per_node == {}
    assert result.path == api.USAGE_PATH_SQUAD_SCOPED
    # Ответ squad-scoped авторитетен и когда пуст: остальные пути дёргать незачем.
    assert len([c for c in calls if "bandwidth-stats" in c]) == 1, calls


def test_numeric_identity_is_not_queried_twice(temp_db):
    """Когда в ключе хранится числовой id, оба per-user кандидата дают один URL —
    второй запрос был бы точной копией первого."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/", _Resp(None, 404)),
        ("/bandwidth-stats/users/4242", _Resp({"response": {"series": [], "topNodes": []}})),
        ("/bandwidth-stats/nodes/users", _Resp(None, 404)),
        ("/usage/range", _Resp(None, 404)),
    ], calls=calls)

    asyncio.run(api.get_user_node_usage_for_squad(
        "4242", host_name="H", squad_uuid="squad-lte", node_uuids=["n1"],
        start_date=START, end_date=END, panel_user_id=4242,
    ))

    user_calls = [c for c in calls if "/bandwidth-stats/users/" in c and not c.endswith("/legacy")]
    assert len(user_calls) == 1, user_calls


V3_NAN = {
    "statusCode": 400,
    "message": "Validation failed",
    "errors": [{"expected": "number", "code": "invalid_type", "received": "NaN",
                "path": ["userId"], "message": "Invalid input: expected number, received NaN"}],
}
STORED_UUID = "00000000-0000-4000-8000-0000000000aa"
KEY_EMAIL = "100001-1@bot.local"
KEY_USERNAME = "100001-1"


def test_uuid_plus_email_uses_numeric_squad_scoped_on_3x(temp_db):
    """Ключ с UUID + email: lookup by-username даёт числовой id, bandwidth-stats — только им."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        (f"/api/users/{STORED_UUID}", _Resp(V3_NAN, 400)),
        ("/by-email/", _Resp({}, 404)),
        (f"/by-username/{KEY_USERNAME}", _Resp({"response": {"id": 4242, "username": KEY_USERNAME}})),
        SQUAD_SCOPED_332,
        ("/bandwidth-stats/users/", _Resp({"should": "not probe uuid"}, 400)),
    ], calls=calls)

    result = asyncio.run(api.get_user_node_usage_for_squad(
        STORED_UUID, host_name="H", squad_uuid="squad-lte", node_uuids=["n1", "n2"],
        start_date=START, end_date=END, email=KEY_EMAIL,
    ))

    assert result.path == api.USAGE_PATH_SQUAD_SCOPED
    assert result.per_node == {"n1": 5 * GB, "n2": 1 * GB}
    stats = [c for c in calls if "bandwidth-stats" in c]
    assert stats == ["/api/bandwidth-stats/internal-squads/squad-lte/users/4242/usage"], calls
    assert any(f"/by-username/{KEY_USERNAME}" in c for c in calls)


def test_missing_numeric_id_does_not_poison_squad_scoped_cache(temp_db):
    """UUID без email не должен помечать squad-scoped как «панель не умеет» — соседний ключ с id живой."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        (f"/api/users/{STORED_UUID}", _Resp(V3_NAN, 400)),
        ("/internal-squads/squad-lte/users/4242/usage", SQUAD_SCOPED_332[1]),
        ("/bandwidth-stats/users/", _Resp(None, 404)),
        ("/bandwidth-stats/nodes/users", _Resp(None, 404)),
        ("/usage/range", _Resp(None, 404)),
    ], calls=calls)

    with pytest.raises(api.RemnawavePathUnsupportedError):
        asyncio.run(api.get_user_node_usage_for_squad(
            STORED_UUID, host_name="H", squad_uuid="squad-lte", node_uuids=["n1", "n2"],
            start_date=START, end_date=END,
        ))

    result = asyncio.run(api.get_user_node_usage_for_squad(
        "4242", host_name="H", squad_uuid="squad-lte", node_uuids=["n1", "n2"],
        start_date=START, end_date=END, panel_user_id=4242,
    ))
    assert result.path == api.USAGE_PATH_SQUAD_SCOPED
    assert result.per_node["n1"] == 5 * GB
    squad_calls = [c for c in calls if "internal-squads/squad-lte/users/4242/usage" in c]
    assert len(squad_calls) == 1, calls


def test_numeric_user_path_200_does_not_probe_uuid_on_3x(temp_db):
    """3.x приняла числовой userId (200, пустой series) — UUID в bandwidth-stats не зондруем."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        ("/bandwidth-stats/users/4242", _Resp({"response": {"series": [], "topNodes": []}})),
        (f"/bandwidth-stats/users/{STORED_UUID}", _Resp({"should": "not be called"}, 400)),
        ("/bandwidth-stats/nodes/users", _Resp(None, 404)),
        ("/usage/range", _Resp(None, 404)),
    ], calls=calls)

    result = asyncio.run(api.get_user_node_usage_for_squad(
        STORED_UUID, host_name="H", squad_uuid="squad-lte", node_uuids=["n1"],
        start_date=START, end_date=END, panel_user_id=4242,
    ))

    assert result.path == api.USAGE_PATH_USER_BY_ID
    assert result.per_node == {}
    stats = [c for c in calls if "bandwidth-stats" in c]
    assert "/api/bandwidth-stats/users/4242" in stats
    assert not any(STORED_UUID in c for c in stats)
    assert not any(c.endswith("/legacy") for c in stats)


def test_legacy_wrapper_is_probed_once_per_instance(temp_db):
    """Исторический путь неприменим ни к 2.8.1, ни к 3.3.2 — после первой неудачи он не
    должен опрашиваться на каждом ключе (иначе панель получает поток заведомых 400)."""
    database, api = temp_db, _api()
    _host(database, "H", squads={"lte": "squad-lte"})
    calls: list[str] = []
    _router(api, [
        ("/internal-squads/squad-lte/users/", _Resp(None, 404)),
        ("/bandwidth-stats/users/", _Resp(None, 404)),
        ("/bandwidth-stats/nodes/users", _Resp(None, 404)),
        ("/usage/range", _Resp(None, 404)),
    ], calls=calls)

    for _ in range(3):
        with pytest.raises(api.RemnawavePathUnsupportedError):
            _usage(api, nodes=("n1",))

    legacy_calls = [c for c in calls if "nodes/users" in c or "usage/range" in c]
    assert len(legacy_calls) <= 2, f"исторический путь опрошен повторно: {legacy_calls}"
