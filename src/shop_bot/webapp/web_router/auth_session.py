"""Разрешение пользователя по токену запроса.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from shop_bot.data_manager.remnawave_repository import get_setting, get_user
import shop_bot.data_manager.remnawave_repository as rw_repo
from urllib.parse import urlencode

_AUTH_COOKIE_NAME = "auth_token"
_AUTH_COOKIE_MAX_AGE = 31536000


def _resolve_user_from_request_token(data: dict, request: Request) -> dict | None:
    token = data.get("token") or request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.split(" ", 1)[1]

    if not token:
        token = request.cookies.get("auth_token")

    if not token:
        return None

    uid = TEMP_AUTH_TOKENS.get(token)
    if uid:
        return get_user(uid)
    try:
        u = rw_repo.get_user_by_auth_token(token)
        if u:
            return u
    except Exception:
        pass
    return None


def _resolve_authenticated_user(data: dict, request: Request) -> dict | None:
    """Определить текущего пользователя ИСКЛЮЧИТЕЛЬНО по доверенным источникам:
    существующей persistent auth-сессии (см. _resolve_user_from_request_token —
    тот же токен, что хранится в localStorage/cookie webapp) или по подписанным
    Telegram WebApp `init_data`.

    Специально НЕ принимает и не доверяет `user_id`, присланному клиентом в теле
    запроса — используется там, где подмена пользователя была бы небезопасна
    (например, POST /api/webapp/pending-actions/complete).
    """
    user = _resolve_user_from_request_token(data, request)
    if user:
        return user

    init_data = data.get("init_data")
    if init_data:
        bot_token = get_setting("telegram_bot_token")
        if bot_token:
            tg_user = validate_telegram_data(init_data, bot_token)
            if tg_user and tg_user.get("id"):
                return get_user(int(tg_user["id"]))
    return None


def _unauthorized(detail: str = "Unauthorized") -> JSONResponse:
    return JSONResponse({"ok": False, "error": detail}, status_code=401)


def _require_authenticated_user(
    request: Request,
    *,
    data: dict | None = None,
    token: str | None = None,
    init_data: str | None = None,
) -> dict | None:
    """Resolve caller from auth_token / Bearer / signed init_data only (CWE-862/639).

    Never trusts client-supplied user_id/telegram_id. Returns None if missing
    or banned — callers should respond with ``_unauthorized()``.
    """
    payload = dict(data or {})
    if token is not None:
        payload["token"] = token
    if init_data is not None:
        payload["init_data"] = init_data
    user = _resolve_authenticated_user(payload, request)
    if not user or user.get("is_banned"):
        return None
    return user


def _root_url_without_auth_token(request: Request) -> str:
    """Корень Mini App без persistent token (и без user_id) в query string."""
    pairs = [
        (key, value)
        for key, value in request.query_params.multi_items()
        if key not in {"token", "user_id"}
    ]
    if not pairs:
        return "/"
    return "/?" + urlencode(pairs)


def _set_webapp_auth_cookie(response, token: str) -> None:
    """Тот же auth_token cookie, что ставит JS: path=/, SameSite=Lax, не HttpOnly."""
    response.set_cookie(
        key=_AUTH_COOKIE_NAME,
        value=token,
        max_age=_AUTH_COOKIE_MAX_AGE,
        path="/",
        httponly=False,
        samesite="lax",
    )


def _legacy_auth_token_redirect(request: Request, token: str | None):
    """Legacy /?token= и /token=: cookie при валидном токене, 303 на URL без token."""
    response = RedirectResponse(url=_root_url_without_auth_token(request), status_code=303)
    response.headers["Referrer-Policy"] = "no-referrer"
    token = (token or "").strip()
    if not token:
        return response
    try:
        user = rw_repo.get_user_by_auth_token(token)
    except Exception:
        user = None
    if user:
        _set_webapp_auth_cookie(response, token)
    return response


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_resolve_user_from_request_token",
    "_resolve_authenticated_user",
    "_unauthorized",
    "_require_authenticated_user",
    "_legacy_auth_token_redirect",
]
