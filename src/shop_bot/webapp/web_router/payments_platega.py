"""Верификация платежа Platega.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import VerifyPlategaPaymentRequest


from fastapi import Request
from fastapi.responses import JSONResponse
from shop_bot.data_manager.remnawave_repository import (
    get_pending_metadata,
    check_transaction_exists,
    payment_owned_by_user,
    get_pending_status,
)
from decimal import Decimal

from shop_bot.modules.platega_fulfillment import (
    complete_pending_platega_payment,
    extract_platega_amount,
    is_platega_payment_method,
    mark_pending_canceled,
    normalize_platega_status,
    provider_transaction_id_from_meta,
)


def _platega_verify_error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status_code)


@app.post("/api/webapp/payments/{payment_id}/verify")
async def api_verify_platega_payment(payment_id: str, req: VerifyPlategaPaymentRequest, request: Request):
    """Сверить pending Platega-заказ с GET /transaction/{id} и выдать ключ тем же путём, что webhook."""
    user = _require_authenticated_user(request, token=req.token, init_data=req.init_data)
    if not user:
        return _unauthorized()

    pid = (payment_id or "").strip()
    if not pid or pid in {"undefined", "null"}:
        return _platega_verify_error("Некорректный платёж")

    user_id = int(user["telegram_id"])

    if not payment_owned_by_user(pid, user_id):
        logger.info(
            "Platega webapp verify: forbidden payment_id=%s user_id=%s platega_api_called=%s",
            pid,
            user_id,
            False,
        )
        return _platega_verify_error("Платёж не найден", 403)

    local_status = (get_pending_status(pid) or "").lower()
    pending_meta = get_pending_metadata(pid)
    if local_status == "paid" or (not pending_meta and check_transaction_exists(pid)):
        logger.info(
            "Platega webapp verify: already fulfilled payment_id=%s user_id=%s result=idempotent",
            pid,
            user_id,
        )
        stored_tx = provider_transaction_id_from_meta(pending_meta) if pending_meta else ""
        return {
            "ok": True,
            "status": "confirmed",
            "payment_id": pid,
            "provider_transaction_id": stored_tx,
            "key_issued": True,
        }

    if not pending_meta:
        return _platega_verify_error("Платёж не найден", 404)

    if not is_platega_payment_method(pending_meta):
        logger.info(
            "Platega webapp verify: rejected non-platega payment_id=%s method=%s user_id=%s",
            pid,
            pending_meta.get("payment_method"),
            user_id,
        )
        return _platega_verify_error("Этот платёж нельзя проверить через Platega")

    owner = pending_meta.get("user_id")
    try:
        owner_ok = int(owner) == user_id
    except (TypeError, ValueError):
        owner_ok = False
    if not owner_ok:
        return _platega_verify_error("Платёж не найден", 403)

    txid = provider_transaction_id_from_meta(pending_meta)
    if not txid:
        logger.warning("Platega webapp verify: missing provider_transaction_id payment_id=%s", pid)
        return {
            "ok": True,
            "status": "pending",
            "payment_id": pid,
            "provider_transaction_id": "",
            "key_issued": False,
        }

    try:
        client = _platega_api()
        if not client:
            return _platega_verify_error("Не удалось проверить оплату. Попробуйте позже.", 503)
        remote = await client.get_transaction(txid)
    except Exception as e:
        logger.error(
            "Platega webapp verify: API error payment_id=%s provider_transaction_id=%s user_id=%s err=%s",
            pid,
            txid,
            user_id,
            type(e).__name__,
        )
        return _platega_verify_error("Не удалось проверить оплату. Попробуйте позже.", 503)

    if not remote:
        logger.error(
            "Platega webapp verify: empty API result payment_id=%s provider_transaction_id=%s user_id=%s",
            pid,
            txid,
            user_id,
        )
        return _platega_verify_error("Не удалось проверить оплату. Попробуйте позже.", 503)

    remote_status = normalize_platega_status(remote.get("status"))
    remote_payload = str(remote.get("payload") or "").strip()
    logger.info(
        "Platega webapp verify: payment_id=%s provider_transaction_id=%s user_id=%s remote_status=%s",
        pid,
        txid,
        user_id,
        remote_status,
    )

    if remote_payload and remote_payload != pid:
        logger.warning(
            "Platega webapp verify: payload mismatch payment_id=%s remote_payload=%s",
            pid,
            remote_payload,
        )
        return {
            "ok": True,
            "status": "pending",
            "payment_id": pid,
            "provider_transaction_id": txid,
            "key_issued": False,
        }

    if remote_status == "canceled":
        mark_pending_canceled(pid, provider_transaction_id=txid)
        return {
            "ok": True,
            "status": "canceled",
            "payment_id": pid,
            "provider_transaction_id": txid,
            "key_issued": False,
        }

    if remote_status != "confirmed":
        return {
            "ok": True,
            "status": "pending",
            "payment_id": pid,
            "provider_transaction_id": txid,
            "key_issued": False,
        }

    expected = pending_meta.get("price")
    if expected is None:
        expected = pending_meta.get("amount_rub")
    got = extract_platega_amount(remote)
    if expected is not None and got is not None:
        try:
            if Decimal(str(got)) < Decimal(str(expected)):
                logger.warning(
                    "Platega webapp verify: amount mismatch payment_id=%s got=%s expected=%s",
                    pid,
                    got,
                    expected,
                )
                return {
                    "ok": True,
                    "status": "pending",
                    "payment_id": pid,
                    "provider_transaction_id": txid,
                    "key_issued": False,
                }
        except Exception:
            logger.warning("Platega webapp verify: amount parse failed payment_id=%s", pid)
            return {
                "ok": True,
                "status": "pending",
                "payment_id": pid,
                "provider_transaction_id": txid,
                "key_issued": False,
            }

    metadata = complete_pending_platega_payment(pid, provider_transaction_id=txid)
    if not metadata:
        logger.info(
            "Platega webapp verify: concurrent complete payment_id=%s user_id=%s result=idempotent",
            pid,
            user_id,
        )
        return {
            "ok": True,
            "status": "confirmed",
            "payment_id": pid,
            "provider_transaction_id": txid,
            "key_issued": True,
        }

    try:
        issued = await _fulfill_webapp_paid_order(metadata)
    except Exception as e:
        logger.error(
            "Platega webapp verify: fulfill failed payment_id=%s provider_transaction_id=%s user_id=%s",
            pid,
            txid,
            user_id,
            exc_info=True,
        )
        return {
            "ok": True,
            "status": "confirmed",
            "payment_id": pid,
            "provider_transaction_id": txid,
            "key_issued": False,
        }

    logger.info(
        "Platega webapp verify: payment_id=%s provider_transaction_id=%s user_id=%s result=confirmed key_issued=%s",
        pid,
        txid,
        user_id,
        bool(issued),
    )
    return {
        "ok": True,
        "status": "confirmed",
        "payment_id": pid,
        "provider_transaction_id": txid,
        "key_issued": bool(issued),
    }


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_platega_verify_error",
    "api_verify_platega_payment",
]
