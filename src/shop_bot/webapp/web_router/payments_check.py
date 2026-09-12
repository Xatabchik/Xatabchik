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
    payment_fulfillment_claimed,
)


def _check_payment_unpaid() -> dict:
    """Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена.

    Один и тот же JSON и 200, чтобы не палить существование чужого payment_id
    через 401/403 или разный ``ok``.
    """
    return {"ok": True, "paid": False}


def _check_payment_processing() -> dict:
    """Оплата подтверждена, но услуга ещё не выдана (или выдача сорвалась).

    ``paid`` остаётся False: клиент реагирует только на ``paid`` (см.
    _tickPaymentPoll в app.html), поэтому продолжит поллинг и не покажет
    «Всё готово!» раньше, чем ключ реально создан. Контракт от этого не
    меняется — добавлены только необязательные поля.
    """
    return {
        "ok": True,
        "paid": False,
        "processing": True,
        "message": "Оплата получена, услуга ещё обрабатывается.",
    }


def _payment_confirmed(payment_id: str) -> bool:
    """Платёж подтверждён провайдером — но это ещё НЕ значит, что услуга выдана."""
    try:
        if (get_pending_status(payment_id) or "").lower() == "paid":
            return True
    except Exception:
        pass
    return check_transaction_exists(payment_id)


def _payment_service_delivered(payment_id: str) -> bool:
    """Услуга по платежу реально выдана.

    Признак — финальная запись в ledger ``transactions`` со status='paid' по
    тому же payment_id: её пишет log_transaction в самом конце
    process_successful_payment, уже ПОСЛЕ создания/продления ключа, зачисления
    баланса или применения докупки (все пять action: покупка/продление ключа,
    top_up, traffic_gb_topup, lte_gb_topup, main_traffic_reset). На путях сбоя
    (_abort_key_fulfillment / _abort_topup_fulfillment) до неё дело не доходит,
    и строка остаётся в status='pending'.

    Само по себе ``pending_transactions.status == 'paid'`` для этого негодно:
    оно означает только «подтверждение платежа принято», выставляется до
    выдачи, и из-за него /api/check-payment отвечал «Оплата успешно
    подтверждена» при пустом ключе.

    Дополнительно требуем idempotency-lock в ``processed_payments``. Это
    отсекает TON Connect: там status='paid' в ``transactions`` выставляет сам
    вебхук (find_and_complete_ton_transaction) ещё ДО выдачи, так что без
    второго условия подтверждение TON-платежа выглядело бы как выданная услуга.
    Lock ставится в начале выдачи и снимается компенсирующими ветвями при сбое.
    """
    return bool(
        check_transaction_exists(payment_id)
        and payment_fulfillment_claimed(payment_id)
    )


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

        # Успех — только по факту выдачи, а не по факту приёма платежа: иначе в
        # окне между подтверждением и созданием ключа клиент показывал
        # «Оплата успешно подтверждена» при пустом ключе, а при сорвавшейся
        # выдаче — вообще всегда.
        if not _payment_service_delivered(req.payment_id):
            if _payment_confirmed(req.payment_id):
                return _check_payment_processing()
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
    "_check_payment_processing",
    "_payment_confirmed",
    "_payment_service_delivered",
    "api_check_payment",
]
