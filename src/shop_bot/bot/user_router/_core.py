"""Состояние уровня модуля и набор доступных способов оплаты.

`TELEGRAM_BOT_USERNAME`, `PAYMENT_METHODS` и `ADMIN_ID` записывает извне
`bot_controller.py` уже после старта, поэтому читать их можно только как
атрибуты модуля в момент вызова — см. docstring пакета.
"""

import logging
from shop_bot.data_manager.remnawave_repository import get_setting

__all__ = [
    "TELEGRAM_BOT_USERNAME",
    "PAYMENT_METHODS",
    "_is_true",
    "_get_payment_methods",
    "ADMIN_ID",
    "CRYPTO_BOT_TOKEN",
    "PENDING_GIFTS",
    "logger",
    "errors",
]

TELEGRAM_BOT_USERNAME = None
PAYMENT_METHODS = None

def _is_true(value) -> bool:
    return str(value).strip().lower() in ('true','1','on','yes','y')

def _get_payment_methods() -> dict:
    """Собирает доступные способы оплаты из актуальных настроек (без перезапуска бота)."""
    yookassa_shop_id = get_setting('yookassa_shop_id')
    yookassa_secret_key = get_setting('yookassa_secret_key')
    yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)

    cryptobot_token = get_setting('cryptobot_token')
    cryptobot_enabled = bool(cryptobot_token)

    heleket_shop_id = get_setting('heleket_merchant_id')
    heleket_api_key = get_setting('heleket_api_key')
    heleket_enabled = bool(heleket_shop_id and heleket_api_key)

    platega_merchant_id = get_setting('platega_merchant_id')
    platega_secret = get_setting('platega_secret')
    platega_enabled = bool(platega_merchant_id and platega_secret)

    rollypay_enabled = bool(
        (get_setting('rollypay_api_key') or '').strip()
        and (get_setting('rollypay_signing_secret') or '').strip()
    )

    ton_wallet_address = get_setting('ton_wallet_address')
    tonapi_key = get_setting('tonapi_key')
    tonconnect_enabled = bool(ton_wallet_address and tonapi_key)

    yoomoney_raw = get_setting('yoomoney_enabled')
    yoomoney_wallet = get_setting('yoomoney_wallet')
    yoomoney_secret = get_setting('yoomoney_secret')
    if yoomoney_raw is None:
        yoomoney_enabled = bool(yoomoney_wallet and yoomoney_secret)
    else:
        yoomoney_enabled = _is_true(yoomoney_raw)

    stars_flag = _is_true(get_setting('stars_enabled') or 'false')
    try:
        stars_ratio = float(get_setting('stars_per_rub') or '0')
    except Exception:
        stars_ratio = 0.0
    stars_enabled = stars_flag and (stars_ratio > 0)

    return {
        'yookassa': yookassa_enabled,
        'heleket': heleket_enabled,
        'platega': platega_enabled,
        'rollypay': rollypay_enabled,
        'cryptobot': cryptobot_enabled,
        'tonconnect': tonconnect_enabled,
        'yoomoney': yoomoney_enabled,
        'stars': stars_enabled,
    }

ADMIN_ID = None
CRYPTO_BOT_TOKEN = get_setting("cryptobot_token")

PENDING_GIFTS: dict[int, dict] = {}
# Имя логгера задано строкой, а не через __name__: записи в логах должны
# остаться от 'shop_bot.bot.handlers', как до разделения файла.
logger = logging.getLogger("shop_bot.bot.handlers")

errors = {
    "A019": "username уже занят",
    "400": "неверные данные",
    "404": "ресурс не найден",
}
