"""Общая идемпотентная финализация Platega-платежа (webhook и WebApp verify)."""

from __future__ import annotations

import logging

from shop_bot.data_manager.database import find_and_complete_pending_transaction, patch_pending_metadata
from shop_bot.data_manager.remnawave_repository import cancel_pending_transaction

logger = logging.getLogger(__name__)

PLATEGA_METHODS = ("Platega", "Platega Crypto")
_TERMINAL_CANCELED = frozenset(
    {"CANCELED", "CANCELLED", "CHARGEBACKED", "FAILED", "EXPIRED"}
)


def is_platega_payment_method(pending_meta: dict | None) -> bool:
    if not isinstance(pending_meta, dict):
        return False
    method = str(pending_meta.get("payment_method") or "").strip().lower()
    return method in {name.lower() for name in PLATEGA_METHODS}


def provider_transaction_id_from_meta(pending_meta: dict | None) -> str:
    if not isinstance(pending_meta, dict):
        return ""
    return str(
        pending_meta.get("platega_transaction_id") or pending_meta.get("transaction_id") or ""
    ).strip()


def normalize_platega_status(raw: str | None) -> str:
    status = str(raw or "").upper().strip()
    if status == "CONFIRMED":
        return "confirmed"
    if status in _TERMINAL_CANCELED:
        return "canceled"
    return "pending"


def extract_platega_amount(payload: dict | None):
    if not isinstance(payload, dict):
        return None
    if payload.get("amount") is not None:
        return payload.get("amount")
    details = payload.get("paymentDetails") or payload.get("payment_details") or {}
    if isinstance(details, dict) and details.get("amount") is not None:
        return details.get("amount")
    return None


def mark_pending_canceled(
    payment_id: str,
    *,
    provider_transaction_id: str | None = None,
) -> bool:
    """Пометить счёт отменённым в pending и в истории транзакций."""
    pid = (payment_id or "").strip()
    if not pid:
        return False
    if provider_transaction_id:
        try:
            patch_pending_metadata(pid, {"platega_transaction_id": str(provider_transaction_id)})
        except Exception:
            logger.warning("Platega: не удалось сохранить id провайдера перед отменой %s", pid)
    ok = bool(cancel_pending_transaction(pid))
    if ok:
        logger.info(
            "Pending invoice canceled: payment_id=%s provider_transaction_id=%s",
            pid,
            provider_transaction_id or "",
        )
    return ok


def complete_pending_platega_payment(
    payment_id: str,
    *,
    provider_transaction_id: str | None = None,
) -> dict | None:
    """Атомарно закрыть pending и вернуть metadata.

    None — заказа нет или он уже оплачен (второй вызов безопасен).
    """
    metadata = find_and_complete_pending_transaction(payment_id)
    if not metadata:
        return None
    metadata.setdefault("payment_method", "Platega")
    if provider_transaction_id:
        metadata["platega_transaction_id"] = str(provider_transaction_id)
    logger.info(
        "Platega pending completed: payment_id=%s provider_transaction_id=%s user_id=%s",
        payment_id,
        provider_transaction_id or metadata.get("platega_transaction_id") or "",
        metadata.get("user_id"),
    )
    return metadata
