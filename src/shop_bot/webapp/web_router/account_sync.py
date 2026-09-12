"""Синхронизация Telegram-аккаунта и тарифы устройств.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router._core import AUTH_RATE_LIMIT, limiter
from shop_bot.webapp.web_router.models import DeviceTiersRequest, SyncTgRequest


from fastapi import Request


from shop_bot.data_manager.remnawave_repository import get_setting


from shop_bot.data_manager.database import (
    get_device_tiers,
    get_host,
)


@app.post("/api/auth/sync-tg")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_sync_tg(request: Request, req: SyncTgRequest):
    from shop_bot.data_manager import database
    user = database.get_user_by_auth_token(req.token)
    if not user:
        return {"ok": False, "error": "Не авторизован"}
        
    token_str = get_setting("telegram_bot_token")
    if not token_str:
         return {"ok": False, "error": "Server configuration error"}
         
    tg_data = validate_telegram_data(req.init_data, token_str)
    if not tg_data or not tg_data.get('id'):
         return {"ok": False, "error": "Invalid Telegram data"}
         
    tg_id = tg_data.get('id')
    tg_username = tg_data.get('username') or ''
    
    if user['telegram_id'] > 0:
         return {"ok": False, "error": "Telegram уже привязан"}
         
    res = database.link_telegram_to_email_user(user['telegram_id'], tg_id, tg_username)
    if res is True:
         return {"ok": True}
    else:
         return {"ok": False, "error": str(res)}


@app.post("/api/device-tiers")
async def api_device_tiers(req: DeviceTiersRequest):
    try:
        host_data = get_host(req.host_name)
        if not host_data:
            return {"ok": True, "device_mode": "plan", "tiers": [], "tier_lock_extend": 0}
        mode = host_data.get('device_mode', 'plan')
        lock = int(host_data.get('tier_lock_extend', 0) or 0)
        from shop_bot.data_manager import database
        base_devices = int(database.get_setting(f"base_device_{req.host_name}") or "1")
        tiers = []
        if mode == 'tiers':
            raw = get_device_tiers(req.host_name)
            tiers = [{"tier_id": t["tier_id"], "device_count": t["device_count"], "price": float(t["price"])} for t in raw]
        return {"ok": True, "device_mode": mode, "tiers": tiers, "tier_lock_extend": lock, "base_device_count": base_devices}
    except Exception as e:
        logger.error(f"API device-tiers error: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_sync_tg",
    "api_device_tiers",
]
