"""Статус пользователя, переименование ключа, транзакции, поиск.

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
    DeleteAllDevicesRequest,
    RenameKeyRequest,
    SearchKeysRequest,
)


from fastapi import Request


from shop_bot.data_manager.remnawave_repository import get_user_keys


import html


from shop_bot.data_manager.remnawave_repository import get_key_by_id


from shop_bot.modules import remnawave_api


@app.get("/api/user-status")
async def api_user_status(request: Request, token: str | None = None):
    try:
        # Prefer query token; also accept Authorization header via helper.
        user = _require_authenticated_user(request, token=token)
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        keys = get_user_keys(user_id)
        formatted_keys = []
        if keys:
            keys = _sort_keys_newest_first(keys)
            formatted_keys = [_process_key_data(k) for k in keys]
        
        return {"ok": True, "keys": formatted_keys, "balance": float(user.get("balance") or 0.0)}
    except Exception as e:
        logger.error(f"User status error: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/key/rename")
async def api_key_rename(req: RenameKeyRequest, request: Request):
    try:
        user = _resolve_user_from_request_token({"token": req.token}, request)
        if not user or user.get('is_banned'):
            return {"ok": False, "error": "Access denied"}

        user_id = user.get("telegram_id")
        from shop_bot.data_manager.remnawave_repository import get_key_by_id, update_key_name
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}

        new_name = req.new_name.strip() if req.new_name else ""
        if new_name and len(new_name) > 30:
            return {"ok": False, "error": "Название слишком длинное (макс. 30 символов)"}

        success = update_key_name(req.key_id, new_name or None)
        if success:
            return {"ok": True}
        return {"ok": False, "error": "Не удалось обновить название"}
    except Exception as e:
        logger.error(f"Error renaming key: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/key/devices/delete-all")
async def api_key_devices_delete_all(req: DeleteAllDevicesRequest, request: Request):
    try:
        user = _resolve_user_from_request_token({"token": req.token}, request)
        if not user or user.get('is_banned'):
            return {"ok": False, "error": "Access denied"}

        user_id = user.get("telegram_id")
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

        if not devices:
            return {"ok": True, "deleted": 0}

        deleted = 0
        for d in devices:
            device_id = d.get("hwid") if isinstance(d, dict) else str(d)
            if device_id:
                success = await remnawave_api.delete_user_device(
                    uuid_val, device_id, host_name=host, email=email
                )
                if success:
                    deleted += 1

        return {"ok": True, "deleted": deleted, "total": len(devices)}
    except Exception as e:
        logger.error(f"Error deleting all devices: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/api/user/transactions")
async def api_user_transactions(
    request: Request,
    page: int = 1,
    per_page: int = 10,
    token: str | None = None,
):
    try:
        user = _require_authenticated_user(request, token=token)
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])

        from shop_bot.data_manager.remnawave_repository import get_transactions_paginated
        transactions, total = get_transactions_paginated(page=page, per_page=per_page, user_id=user_id)

        status_labels = {
            "pending": "Ожидает оплаты",
            "paid": "Оплачено",
            "success": "Оплачено",
            "succeeded": "Оплачено",
            "completed": "Оплачено",
            "cancelled": "Отменена",
            "canceled": "Отменена",
        }
        safe_txs = []
        for tx in transactions:
            raw_status = (tx.get("status") or "").strip()
            safe_txs.append({
                "transaction_id": tx.get("transaction_id"),
                "payment_id": tx.get("payment_id") or "",
                "provider_transaction_id": tx.get("provider_transaction_id") or "",
                "amount_rub": tx.get("amount_rub"),
                "payment_method": tx.get("payment_method") or "—",
                "status": raw_status,
                "status_label": status_labels.get(raw_status.lower(), raw_status or "—"),
                "created_date": tx.get("created_date"),
                "action_label": tx.get("action_label") or "Оплата",
                "plan_name": tx.get("plan_name") or "—",
                "host_name": tx.get("host_name") or "—",
            })

        return {
            "ok": True,
            "transactions": safe_txs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_more": (page * per_page) < total,
        }
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/keys/search")
async def api_keys_search(req: SearchKeysRequest, request: Request):
    try:
        user = _resolve_user_from_request_token({"token": req.token}, request)
        if not user or user.get('is_banned'):
            return {"ok": False, "error": "Access denied"}

        user_id = user.get("telegram_id")
        from shop_bot.data_manager.remnawave_repository import search_user_keys_by_email
        q = (req.query or "").strip()
        if not q:
            return {"ok": False, "error": "Запрос поиска пустой"}
        if len(q) < 2:
            return {"ok": False, "error": "Минимум 2 символа для поиска"}

        keys = search_user_keys_by_email(user_id, q)
        found_keys = keys[:20]
        # Reuse the same card renderer as the main "Мои ключи" list so search
        # results get full parity: same buttons, same onclick wiring (extend,
        # rename, comment, devices, auto-renew, copy link, etc.).
        html = _get_profile_keys_html(found_keys) if found_keys else ""

        return {"ok": True, "html": html, "total": len(found_keys)}
    except Exception as e:
        logger.error(f"Error searching keys: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_user_status",
    "api_key_rename",
    "api_key_devices_delete_all",
    "api_user_transactions",
    "api_keys_search",
]
