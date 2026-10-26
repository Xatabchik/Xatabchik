"""Лимиты slowapi на роутах с параметрами пути.

`@limiter.limit` по умолчанию считает лимит по URL запроса вместе со значением
параметра, поэтому у `/api/auth/check-token/{token}` каждый новый токен получал
свою корзину, и перебор токенов с одного адреса лимит не упирал. Такие роуты
обязаны использовать `shared_limit` с общим `scope`.
"""
from __future__ import annotations

from collections import Counter

from conftest import temp_db  # noqa: F401

from shop_bot.webapp.web_router._core import AUTH_CHECK_TOKEN_RATE_LIMIT

CHECK_TOKEN_LIMIT = int(AUTH_CHECK_TOKEN_RATE_LIMIT.split("/")[0])


def _limited_routes_with_path_params(handlers):
    from fastapi.routing import APIRoute
    from shop_bot.webapp.web_router._core import limiter

    found = []
    for route in handlers.app.routes:
        if not isinstance(route, APIRoute) or not route.param_convertors:
            continue
        name = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        for lim in limiter._route_limits.get(name, []):
            found.append((route.path, name, lim.scope))
    return found


def test_routes_with_path_params_use_shared_scope(temp_db):
    from shop_bot.webapp import handlers

    routes = _limited_routes_with_path_params(handlers)
    assert routes, "ожидался хотя бы один лимитируемый роут с параметром пути"
    unscoped = [(path, name) for path, name, scope in routes if not scope]
    assert not unscoped, (
        "роуты с параметром пути и @limiter.limit считают лимит по URL, "
        f"используйте shared_limit(scope=...): {unscoped}"
    )


def test_check_token_limit_applies_across_different_tokens(app_client):
    codes = Counter(
        app_client.get(f"/api/auth/check-token/token-{i}").status_code
        for i in range(CHECK_TOKEN_LIMIT + 5)
    )
    assert codes[429] == 5, codes
    assert codes[200] == CHECK_TOKEN_LIMIT, codes


def test_check_token_same_token_repeated_is_limited_too(app_client):
    codes = Counter(
        app_client.get("/api/auth/check-token/same-token").status_code
        for _ in range(CHECK_TOKEN_LIMIT + 3)
    )
    assert codes[429] == 3, codes


def test_check_token_scope_is_not_shared_with_other_routes(app_client):
    for i in range(CHECK_TOKEN_LIMIT + 2):
        app_client.get(f"/api/auth/check-token/token-{i}")
    resp = app_client.get("/api/auth/request-token")
    assert resp.status_code == 200
