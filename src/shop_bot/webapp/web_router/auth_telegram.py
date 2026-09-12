"""Проверка Telegram initData и вход через Telegram.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router._core import (
    AUTH_RATE_LIMIT,
    TELEGRAM_INIT_DATA_MAX_AGE_SECONDS,
    limiter,
)
from shop_bot.webapp.web_router.models import TelegramDirectAuthRequest, TokenRequest


from fastapi import Request
from fastapi.responses import JSONResponse
from shop_bot.data_manager.remnawave_repository import get_setting, get_user
import uuid
import time


def validate_telegram_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = TELEGRAM_INIT_DATA_MAX_AGE_SECONDS,
) -> dict | None:
    """Verify Telegram WebApp initData HMAC and freshness (auth_date).

    Protocol: secret = HMAC_SHA256(key=\"WebAppData\", msg=bot_token);
    compare hash with HMAC_SHA256(secret, data_check_string).
    """
    from urllib.parse import parse_qsl
    import hmac
    import hashlib
    import json

    try:
        if not init_data or len(init_data) < 10:
            logger.warning("Telegram auth: init_data is empty or too short")
            return None

        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            logger.warning("Telegram auth: hash not found in init_data")
            return None
        
        received_hash = parsed_data.pop("hash")
        
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning(
                f"Telegram auth: hash mismatch. Expected={calculated_hash[:16]}... "
                f"Got={received_hash[:16]}..."
            )
            return None

        auth_date_raw = parsed_data.get("auth_date")
        if auth_date_raw is None or auth_date_raw == "":
            logger.warning("Telegram auth: auth_date missing")
            return None
        try:
            auth_date = int(auth_date_raw)
        except (TypeError, ValueError):
            logger.warning("Telegram auth: auth_date is not an integer")
            return None
        now = int(time.time())
        if auth_date > now + 60:
            logger.warning("Telegram auth: auth_date is in the future")
            return None
        if max_age_seconds is not None and (now - auth_date) > int(max_age_seconds):
            logger.warning("Telegram auth: auth_date expired")
            return None

        user_json = parsed_data.get("user")
        if user_json:
            return json.loads(user_json)
        logger.warning("Telegram auth: hash valid but no user field")
        return None
    except Exception as e:
        logger.error(f"Telegram auth validation error: {e}")
        return None


def _issue_persistent_token_for_telegram_user(user_id: int) -> dict:
    """Shared token issue/lookup used by /api/auth/token and /api/auth/telegram-direct."""
    from shop_bot.data_manager import database

    user = get_user(user_id)
    if user and user.get("is_banned"):
        return {"ok": False, "error": "Access denied", "status_code": 403}

    existing_token = database.get_auth_token_by_user_id(user_id)
    if existing_token:
        return {"ok": True, "token": existing_token, "user_id": user_id}

    token = str(uuid.uuid4())
    database.update_user_auth_token(user_id, token)
    return {"ok": True, "token": token, "user_id": user_id}


@app.get("/api/auth/request-token")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_request_auth_token(request: Request):
    from shop_bot.data_manager import database
    token = str(uuid.uuid4())[:36]
    TEMP_AUTH_TOKENS[token] = None
    try:
        database.create_webapp_auth_request(token)
        database.cleanup_old_webapp_auth_requests()
    except Exception as e:
        logger.error(f"Failed to persist webapp auth request: {e}")
    bot_username = get_setting("telegram_bot_username")
    auth_url = f"tg://resolve?domain={bot_username}&start=auth_{token}"
    return {"ok": True, "token": token, "auth_url": auth_url}


@app.get("/api/auth/check-token/{token}")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_check_auth_token(token: str, request: Request):
    from shop_bot.data_manager import database
    # 1. Check in memory (waiting for bot confirmation, same-process fast path)
    if token in TEMP_AUTH_TOKENS and TEMP_AUTH_TOKENS[token] is not None:
        user_id = TEMP_AUTH_TOKENS.pop(token)
        
        # Check existing token first
        existing_token = database.get_auth_token_by_user_id(user_id)
        if existing_token:
            return {"ok": True, "authorized": True, "user_id": user_id, "token": existing_token}
            
        # Generate persistent token
        persistent_token = str(uuid.uuid4())
        database.update_user_auth_token(user_id, persistent_token)
        return {"ok": True, "authorized": True, "user_id": user_id, "token": persistent_token}
    
    # 2. Check in DB (already authorized)
    user = database.get_user_by_auth_token(token)
    if user:
        if user.get('is_banned'):
            return {"ok": True, "authorized": False, "error": "Banned"}
        return {"ok": True, "authorized": True, "user_id": user['telegram_id'], "token": token}

    # 3. Check webapp_auth_requests table (bot confirmed login from a different process/container)
    try:
        confirmed_user_id = database.get_webapp_auth_request(token, consume=True)
    except Exception:
        confirmed_user_id = None
    if confirmed_user_id:
        if user and user.get('is_banned'):
            return {"ok": True, "authorized": False, "error": "Banned"}
        existing_token = database.get_auth_token_by_user_id(confirmed_user_id)
        if existing_token:
            return {"ok": True, "authorized": True, "user_id": confirmed_user_id, "token": existing_token}
        persistent_token = str(uuid.uuid4())
        database.update_user_auth_token(confirmed_user_id, persistent_token)
        return {"ok": True, "authorized": True, "user_id": confirmed_user_id, "token": persistent_token}

    return {"ok": True, "authorized": False}


@app.post("/api/auth/token")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_create_token(request: Request, req: TokenRequest):
    """Generate or retrieve a persistent login token using verified Telegram data."""
    token_str = get_setting("telegram_bot_token")
    if not token_str:
        return JSONResponse({"ok": False, "error": "Server configuration error"}, status_code=500)

    user_data = validate_telegram_data(req.init_data, token_str)
    
    if not user_data or not user_data.get("id"):
        return JSONResponse({"ok": False, "error": "Invalid auth data"}, status_code=401)

    result = _issue_persistent_token_for_telegram_user(int(user_data["id"]))
    status = result.pop("status_code", 200)
    if not result.get("ok"):
        return JSONResponse(result, status_code=status)
    return {"ok": True, "token": result["token"]}


@app.post("/api/auth/telegram-direct")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_telegram_direct_auth(request: Request, req: TelegramDirectAuthRequest):
    """Authenticate inside Telegram WebApp using signed initData only.

    Previously accepted a bare ``user_id`` from the client (CWE-306). User identity
    is now taken exclusively from HMAC-validated Telegram WebApp initData.
    """
    from shop_bot.data_manager import database
    try:
        token_str = get_setting("telegram_bot_token")
        if not token_str:
            return JSONResponse({"ok": False, "error": "Server configuration error"}, status_code=500)

        user_data = validate_telegram_data(req.init_data, token_str)
        if not user_data or not user_data.get("id"):
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

        user_id = int(user_data["id"])
        user = get_user(user_id)
        if not user:
            return JSONResponse({"ok": False, "error": "User not registered"}, status_code=401)

        if user.get("is_banned"):
            return JSONResponse({"ok": False, "error": "Access denied"}, status_code=403)

        existing_token = database.get_auth_token_by_user_id(user_id)
        if existing_token:
            return {"ok": True, "token": existing_token, "user_id": user_id}

        token = str(uuid.uuid4())
        database.update_user_auth_token(user_id, token)
        return {"ok": True, "token": token, "user_id": user_id}
    except Exception as e:
        logger.error(f"Telegram direct auth error: {e}")
        return JSONResponse({"ok": False, "error": "Auth error"}, status_code=500)


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "validate_telegram_data",
    "_issue_persistent_token_for_telegram_user",
    "api_request_auth_token",
    "api_check_auth_token",
    "api_create_token",
    "api_telegram_direct_auth",
]
