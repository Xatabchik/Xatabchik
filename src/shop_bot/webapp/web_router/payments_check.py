"""Проверка состояния платежа.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import CheckPaymentRequest


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import (
    check_transaction_exists,
    payment_owned_by_user,
    get_balance,
    get_pending_status,
)


def _check_payment_unpaid() -> dict:
    """Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена.

    Один и тот же JSON и 200, чтобы не палить существование чужого payment_id
    через 401/403 или разный ``ok``.
    """
    return {"ok": True, "paid": False}


@app.post("/api/check-payment")
async def api_check_payment(req: CheckPaymentRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _check_payment_unpaid()

        if not req.payment_id or req.payment_id == "undefined" or req.payment_id == "null":
            return {"ok": False, "error": "Invalid payment_id"}

        user_id = int(user["telegram_id"])
        if not payment_owned_by_user(req.payment_id, user_id):
            return _check_payment_unpaid()

        # Subscription purchases log with the same payment_id; top_up logs a new uuid,
        # so also treat pending status 'paid' as success (webhook already completed it).
        # transactions.status must be 'paid' — TON Connect inserts a pending row first.
        exists = check_transaction_exists(req.payment_id)
        if not exists:
            try:
                pending_status = (get_pending_status(req.payment_id) or "").lower()
            except Exception:
                pending_status = ""
            if pending_status != "paid":
                return _check_payment_unpaid()

        result = {
            "ok": True,
            "paid": True,
            "message": "Оплата успешно подтверждена",
        }
        try:
            result["balance"] = float(get_balance(user_id) or 0)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error(f"Check payment error: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_check_payment_unpaid",
    "api_check_payment",
]
