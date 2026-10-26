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
from shop_bot.webapp.web_router._core import limiter
from shop_bot.webapp.web_router.models import CheckPaymentRequest, PaymentQrRequest


import base64
import io

from fastapi import Request
from shop_bot.data_manager.remnawave_repository import (
    check_transaction_exists,
    get_paid_transaction_for_user,
    get_key_by_id,
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
    (_abort_key_fulfillment / _abort_topup_fulfillment / _abort_balance_topup)
    до неё дело не доходит, и строка остаётся в status='pending'.

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
            "payment_id": req.payment_id,
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


PAYMENT_RESULT_RATE_LIMIT = "60/minute"
PAYMENT_QR_RATE_LIMIT = "30/minute"
_PAYMENT_QR_KINDS = ("gift_webapp", "gift_telegram", "key")


def _payment_result_for_user(user_id: int, payment_id: str) -> dict | None:
    """Что именно получил пользователь по оплаченному платежу.

    None — платёж чужой, не оплачен или услуга ещё не выдана (клиенту
    отвечаем нейтрально, как в /api/check-payment). Всё, что здесь
    возвращается, берётся из БД по payment_id владельца: ни ключ, ни код
    подарка не приходят от клиента.

    Ключ отдаётся только пока он принадлежит покупателю. Неактивированный
    подарок остаётся за покупателем (tag=user_gift), а после активации другим
    пользователем ключ уходит к нему — тогда ни подписку, ни ссылку
    покупателю больше не показываем.
    """
    if not payment_owned_by_user(payment_id, user_id):
        return None
    if not _payment_service_delivered(payment_id):
        return None
    tx = get_paid_transaction_for_user(payment_id, user_id)
    if not tx:
        return None

    action = tx["action"]
    result: dict = {"action": action, "key": None, "gift": None}
    key_id = int(tx.get("key_id") or 0)
    if action not in ("new", "extend", "gift") or key_id <= 0:
        return result

    key = get_key_by_id(key_id)
    key_owned = bool(key) and int(key.get("user_id") or 0) == int(user_id)
    if key_owned:
        processed = _process_key_data(key)
        result["key"] = {
            "key_id": key_id,
            "name": processed.get("name") or "",
            "expire_date_str": processed.get("expire_date_str") or "",
            "remaining_str": processed.get("remaining_str") or "",
            "sub_url": processed.get("sub_url") or "",
        }

    if action == "gift":
        gift_code = None
        if key_owned:
            from shop_bot.data_manager import database

            _gift_id, gift_code = database.get_gift_info_by_key_id(key_id)
            gift = database.get_gift_by_code(gift_code) if gift_code else None
            if not gift or int(gift.get("from_user_id") or 0) != int(user_id):
                gift_code = None
        if gift_code:
            webapp_link, telegram_link = _gift_activation_links(gift_code, absolute=True)
            result["gift"] = {
                "status": "pending",
                "gift_code": gift_code,
                "webapp_link": webapp_link,
                "telegram_link": telegram_link,
                "share_text": _gift_share_text_setting(),
            }
        else:
            result["gift"] = {"status": "activated"}
    return result


@app.post("/api/payment/result")
@limiter.limit(PAYMENT_RESULT_RATE_LIMIT)
async def api_payment_result(req: CheckPaymentRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user or not req.payment_id:
            return {"ok": True, "ready": False}
        result = _payment_result_for_user(int(user["telegram_id"]), req.payment_id.strip())
        if result is None:
            return {"ok": True, "ready": False}
        return {"ok": True, "ready": True, **result}
    except Exception as e:
        logger.error(f"Payment result error: {e}")
        return {"ok": False, "error": "Не удалось получить данные платежа"}


def _qr_data_uri(payload: str) -> str:
    import qrcode

    img = qrcode.make(payload, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@app.post("/api/payment/qr")
@limiter.limit(PAYMENT_QR_RATE_LIMIT)
async def api_payment_qr(req: PaymentQrRequest, request: Request):
    """QR для ссылки из результата платежа.

    Содержимое QR сервер выбирает сам по (payment_id, kind) из
    `_payment_result_for_user`; произвольный текст клиент передать не может,
    поэтому эндпоинт не превращается в общий генератор QR.
    """
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user or req.kind not in _PAYMENT_QR_KINDS:
            return {"ok": False, "error": "Not found"}
        result = _payment_result_for_user(int(user["telegram_id"]), (req.payment_id or "").strip())
        payload = ""
        if result:
            gift = result.get("gift") or {}
            key = result.get("key") or {}
            if req.kind == "key":
                payload = key.get("sub_url") or ""
            elif gift.get("status") == "pending":
                payload = gift.get("webapp_link" if req.kind == "gift_webapp" else "telegram_link") or ""
        if not payload:
            return {"ok": False, "error": "Not found"}
        return {"ok": True, "image": _qr_data_uri(payload)}
    except Exception as e:
        logger.error(f"Payment QR error: {e}")
        return {"ok": False, "error": "Не удалось создать QR-код"}


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
    "PAYMENT_RESULT_RATE_LIMIT",
    "PAYMENT_QR_RATE_LIMIT",
    "_payment_result_for_user",
    "api_payment_result",
    "api_payment_qr",
]
