"""Заявки на вывод реферального баланса.

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
import shop_bot.data_manager.remnawave_repository as rw_repo


@app.post("/api/referral/request-withdrawal")
async def api_referral_request_withdraw(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": False, "error": "Вывод средств временно недоступен.", "message": "Вывод средств временно недоступен."}

    try:
        amount = float(data.get("amount") or 0)
    except Exception:
        return {"ok": False, "error": "Invalid amount"}

    if amount <= 0:
        return {"ok": False, "error": "Invalid amount"}

    method_id = int(data.get("method_id") or 0)
    ok, msg, new_id = rw_repo.create_referral_withdrawal_request(user.get("telegram_id"), amount, method_id)
    if ok and new_id:
        try:
            method = rw_repo.get_referral_payout_method(method_id, user.get("telegram_id"))
            admin_text = rw_repo.format_referral_withdrawal_admin_notice(
                request_id=new_id,
                user_id=user.get("telegram_id"),
                username=user.get("username"),
                amount=amount,
                method_type=(method or {}).get("method_type"),
                bank_name=(method or {}).get("bank_name"),
                requisite_value=(method or {}).get("requisite_value"),
            )
            for admin_id in (rw_repo.get_admin_ids() or set()):
                await _send_telegram_message(int(admin_id), admin_text)
        except Exception:
            logger.warning("Не удалось уведомить администраторов о заявке на вывод", exc_info=True)
    return {
        "ok": ok,
        "message": msg,
        "request_id": new_id,
        "has_open_request": bool(ok) or rw_repo.has_open_referral_withdrawal_request(user.get("telegram_id")),
    }


@app.post("/api/referral/withdrawals")
async def api_referral_list_withdrawals(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    try:
        requests_list = rw_repo.list_referral_withdrawal_requests(user_id=user.get("telegram_id"))
    except Exception as e:
        logger.error(f"Failed to list referral withdrawals for {user.get('telegram_id')}: {e}")
        return {"ok": False, "error": "Server error"}

    withdrawals = [
        {
            "id": r.get("id"),
            "amount": r.get("amount"),
            "status": r.get("status"),
            "method_type": r.get("method_type"),
            "bank_name": r.get("bank_name"),
            "requisite_value": r.get("requisite_value"),
            "reject_reason": r.get("reject_reason"),
            "created_at": r.get("created_at"),
            "processed_at": r.get("processed_at"),
        }
        for r in requests_list
    ]
    has_open_request = any((r.get("status") or "") in ("new", "processing") for r in requests_list)
    return {"ok": True, "withdrawals": withdrawals, "has_open_request": has_open_request}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_referral_request_withdraw",
    "api_referral_list_withdrawals",
]
