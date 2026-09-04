"""Промокоды.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import json

__all__ = (
    "_promo_plans_label",
    "_promo_segment_label",
)


def _promo_plans_label(raw_ids) -> str:
    """Человекочитаемое ограничение тарифов для карточки купона в админке."""
    if raw_ids is None or str(raw_ids).strip() == "":
        return "все тарифы"
    try:
        parsed = json.loads(raw_ids) if not isinstance(raw_ids, (list, tuple)) else list(raw_ids)
        ids = [int(x) for x in parsed]
    except Exception:
        return "все тарифы"
    if not ids:
        return "все тарифы"
    return "тарифы: " + ", ".join(str(i) for i in ids)


def _promo_segment_label(segment_type, segment_value) -> str:
    """Человекочитаемое ограничение сегмента для карточки купона в админке."""
    st = (str(segment_type).strip() if segment_type is not None else "")
    if not st:
        return "без сегмента"
    if st == "no_active_subscription":
        return "нет активной подписки"
    if st == "min_total_spent":
        try:
            value = float(segment_value)
        except (TypeError, ValueError):
            value = 0.0
        return f"сумма покупок ≥ {value:.0f} ₽"
    return st
