"""Устройства ключа и комментарий к ключу.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import (
    CommentRequest,
    DeleteDeviceRequest,
    KeyActionRequest,
)


from fastapi import Request


@app.post("/api/key/devices")
async def api_key_devices(req: KeyActionRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.modules import remnawave_api
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}
            
        uuid_val = key.get("remnawave_user_uuid")
        if not uuid_val:
            return {"ok": False, "error": "Ключ не имеет привязки к серверу"}
            
        host = req.host_name or key.get("host_name")
        email = key.get("key_email") or key.get("email")
        devices_data = await remnawave_api.get_connected_devices_count(
            uuid_val, host_name=host, email=email
        )
        devices = (devices_data or {}).get("devices") or []
        return {"ok": True, "devices": devices}
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/key/device/delete")
async def api_key_device_delete(req: DeleteDeviceRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.modules import remnawave_api
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}
            
        uuid_val = key.get("remnawave_user_uuid")
        if not uuid_val:
            return {"ok": False, "error": "Ключ не имеет привязки"}
            
        host = req.host_name or key.get("host_name")
        email = key.get("key_email") or key.get("email")
        success = await remnawave_api.delete_user_device(
            uuid_val, req.device_id, host_name=host, email=email
        )
        if success:
            return {"ok": True}
        return {"ok": False, "error": "Не удалось удалить устройство"}
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/key/comment")
async def api_key_comment(req: CommentRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.data_manager.database import normalize_key_comment, update_key_comment
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}

        comment, error = normalize_key_comment(req.comment)
        if error:
            return {"ok": False, "error": error}

        update_key_comment(req.key_id, comment)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error updating comment: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_key_devices",
    "api_key_device_delete",
    "api_key_comment",
]
