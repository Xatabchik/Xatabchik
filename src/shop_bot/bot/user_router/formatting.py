"""Форматирование подписей тарифов и сроков, расчёт числа добавляемых
дней и проверка адреса почты.
"""

import re
import json

__all__ = [
    "_format_duration_label",
    "_compute_days_to_add",
    "_tariff_label_from_origin",
    "_build_key_origin_meta",
    "is_valid_email",
]

def _format_duration_label(months: int | None, duration_days: int | None) -> str:
    try:
        dd = int(duration_days or 0)
    except Exception:
        dd = 0
    if dd and dd > 0:
        return f"{dd} дн."
    try:
        mm = int(months or 0)
    except Exception:
        mm = 0
    return f"{mm} мес." if mm else "—"


def _compute_days_to_add(months: int | None, duration_days: int | None) -> int:
    try:
        dd = int(duration_days or 0)
    except Exception:
        dd = 0
    if dd and dd > 0:
        return dd
    try:
        mm = int(months or 0)
    except Exception:
        mm = 0
    return int(mm * 30)


def _tariff_label_from_origin(*, is_trial: bool, months: int | None, duration_days: int | None) -> str:
    """Human label for subscription page tariff line.

    Requirement: show "30 дней" depending on how the key was obtained.
    """
    if is_trial:
        return "триал"
    days = _compute_days_to_add(months, duration_days)
    if days and days > 0:
        return f"{days} дней"
    return "—"


def _build_key_origin_meta(
    *,
    source: str,
    plan_id: int | None,
    plan_name: str | None,
    months: int | None,
    duration_days: int | None,
    is_trial: bool = False,
    note: str | None = None,
) -> str:
    """Store key origin info inside vpn_keys.description as JSON.

    We use this later to correctly render "🕒 Тариф:" even if host plans change.
    """
    label = _tariff_label_from_origin(is_trial=is_trial, months=months, duration_days=duration_days)
    payload = {
        "v": 1,
        "source": source,
        "is_trial": bool(is_trial),
        "plan_id": int(plan_id) if plan_id else None,
        "plan_name": plan_name or None,
        "months": int(months or 0),
        "duration_days": int(duration_days or 0),
        "tariff_label": label,
    }
    if note:
        payload["note"] = str(note)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None
