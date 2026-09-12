"""Автопродление ключа.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import get_key_by_id
import shop_bot.data_manager.remnawave_repository as rw_repo


@app.post("/api/key/auto-renew")
async def api_key_auto_renew(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    key_id = data.get("key_id")
    enabled = data.get("enabled")
    if key_id is None or enabled is None:
        return {"ok": False, "error": "Missing key_id or enabled"}

    key = get_key_by_id(int(key_id))
    if not key or key.get("user_id") != user.get("telegram_id"):
        return {"ok": False, "error": "Key not found"}

    rw_repo.set_key_auto_renew(int(key_id), bool(enabled))
    return {"ok": True, "auto_renew": bool(enabled)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_key_auto_renew",
]
