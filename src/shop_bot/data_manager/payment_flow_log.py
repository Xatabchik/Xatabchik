"""Маркеры этапов обработки платежа: `PAYMENT_FLOW stage=... payment_id=... provider_id=...`.

Только идентификаторы и короткие служебные поля. metadata, тела webhook, суммы,
e-mail, username, gift_code, ссылки и токены сюда не передаются. Значения могут
прийти из недоверенного webhook до проверки через API, поэтому каждое поле
очищается: только безопасные символы, длина ограничена.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_MAX_LEN = 64
_UNSAFE = re.compile(r"[^A-Za-z0-9_.:\-]")


def _clean(value) -> str:
    if value is None:
        return "-"
    raw = str(value)
    text = _UNSAFE.sub("?", raw[:_MAX_LEN])
    if not text:
        return "-"
    return text + "..." if len(raw) > _MAX_LEN else text


def log_payment_stage(stage: str, payment_id, provider_id=None, **fields) -> None:
    """Записать маркер этапа платежа. Никогда не бросает исключения."""
    try:
        parts = [f"stage={_clean(stage)}", f"payment_id={_clean(payment_id)}", f"provider_id={_clean(provider_id)}"]
        parts.extend(f"{_clean(k)}={_clean(v)}" for k, v in fields.items())
        logger.info("PAYMENT_FLOW %s", " ".join(parts))
    except Exception:
        pass


def log_dispatch_done(fut, payment_id, provider_id=None) -> None:
    """done_callback для Future выдачи: только пишет исход в лог, ничего не повторяет.

    cancelled() проверяется первым: exception() у отменённого Future бросает CancelledError.
    Исход: True — ok, False — failed, None — no_result (пополнения ничего не возвращают).
    """
    try:
        if fut.cancelled():
            log_payment_stage("dispatch_done", payment_id, provider_id, outcome="cancelled")
            return
        exc = fut.exception()
        if exc is not None:
            log_payment_stage("dispatch_done", payment_id, provider_id, outcome="error", error=type(exc).__name__)
            return
        result = fut.result()
        outcome = "no_result" if result is None else ("ok" if result else "failed")
        log_payment_stage("dispatch_done", payment_id, provider_id, outcome=outcome)
    except Exception:
        pass
