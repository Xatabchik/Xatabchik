"""Решение webhook ЮKassa о привязке ID платежа к локальному заказу.

Отдельно от webhook_server/app.py, чтобы проверять без его импорта. Привязка
вторична: блокирует выдачу только подтверждённый конфликт ID, остальные сбои
оставляют выдачу как была.
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass

from shop_bot.data_manager.payment_flow_log import _clean

logger = logging.getLogger(__name__)

PROVIDER_ID_CONFLICT_KIND = "payment_provider_id_conflict"
_CONFLICT_DEDUPE_SECONDS = 6 * 3600


@dataclass(frozen=True)
class YookassaLinkDecision:
    """action: proceed — выдача как обычно; block — ответ 200 без выдачи;
    retry — ответ 500, чтобы ЮKassa повторила webhook (алерт не записан)."""

    action: str
    set_provider_id: str | None = None


def _conflict_text(internal_payment_id: str, stored, api_id: str) -> str:
    from shop_bot.data_manager import database

    stored_display = html.escape(stored) if database.is_valid_yookassa_payment_id(stored) else "нестандартное значение"
    return (
        f"Платёж {html.escape(str(internal_payment_id))}: конфликт ID ЮKassa. "
        f"В заказе сохранён {stored_display}, API подтвердил {html.escape(str(api_id))}. "
        "Выдача не выполнялась, заказ остаётся pending. "
        "Проверьте оба платежа в кабинете ЮKassa."
    )


def decide_yookassa_link(internal_payment_id, requested_id, api_object_id, pending_present) -> YookassaLinkDecision:
    if not pending_present:
        return YookassaLinkDecision("proceed")

    api_id = str(api_object_id or "").strip()
    if not api_id or api_id != str(requested_id or "").strip():
        logger.warning(
            "YooKassa webhook: id в ответе API не совпадает с запрошенным, привязка пропущена payment_id=%s",
            _clean(internal_payment_id),
        )
        return YookassaLinkDecision("proceed")

    from shop_bot.data_manager import database

    result, stored = database.link_pending_yookassa_payment_id(internal_payment_id, api_id)
    if result in ("written", "same"):
        return YookassaLinkDecision("proceed", api_id)
    if result == "error":
        logger.warning("YooKassa webhook: привязка ID не удалась payment_id=%s", _clean(internal_payment_id))
        return YookassaLinkDecision("proceed", api_id)
    if result != "conflict":
        logger.warning(
            "YooKassa webhook: ID не привязан payment_id=%s result=%s", _clean(internal_payment_id), _clean(result)
        )
        return YookassaLinkDecision("proceed")

    try:
        from shop_bot.data_manager import key_write_guard

        key_write_guard.add_ops_alert(
            PROVIDER_ID_CONFLICT_KIND,
            _conflict_text(internal_payment_id, stored, api_id),
            dedupe_seconds=_CONFLICT_DEDUPE_SECONDS,
            payment_id=internal_payment_id,
        )
    except Exception:
        logger.error(
            "YooKassa webhook: не удалось записать алерт о конфликте ID payment_id=%s",
            _clean(internal_payment_id),
            exc_info=True,
        )
        return YookassaLinkDecision("retry")
    return YookassaLinkDecision("block")
