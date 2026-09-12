"""Чтение настроек реферальной программы.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


from shop_bot.data_manager.remnawave_repository import get_setting


def _ref_setting_is_true(key: str, default: bool = False) -> bool:
    raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _ref_method_type_enabled(method_type: str) -> bool:
    setting_key = {
        "sbp": "referral_withdraw_sbp_enabled",
        "card": "referral_withdraw_card_enabled",
        "usdt_trc20": "referral_withdraw_usdt_enabled",
    }.get((method_type or "").strip().lower())
    if not setting_key:
        return False
    return _ref_setting_is_true(setting_key)


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_ref_setting_is_true",
    "_ref_method_type_enabled",
]
