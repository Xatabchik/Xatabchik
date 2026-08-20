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
