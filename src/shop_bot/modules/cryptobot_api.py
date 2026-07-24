"""
Клиент для платёжного провайдера Crypto Pay (CryptoBot).

Вынесен в отдельный переиспользуемый модуль (не трогая bot/handlers.py), на основе
логики, которая ранее существовала только внутри `bot/handlers.py`
(`_create_cryptobot_invoice`). Используется Telegram Mini App (shop_bot.webapp.handlers).
"""

from __future__ import annotations

import logging
from decimal import Decimal

import aiohttp

from shop_bot.data_manager.database import get_setting

logger = logging.getLogger(__name__)

CRYPTOBOT_API_URL = "https://pay.crypt.bot/api/createInvoice"


async def create_cryptobot_api_invoice(
    *,
    amount: float,
    payload_str: str,
) -> tuple[str, int] | None:
    """Создать инвойс в Crypto Pay (CryptoBot) в фиате RUB.

    Возвращает (bot_invoice_url, invoice_id) при успехе, иначе None.
    """
    token = (get_setting("cryptobot_token") or "").strip()
    if not token:
        logger.error("CryptoBot: не указан токен API в настройках.")
        return None

    price_str = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"

    body = {
        "amount": price_str,
        "currency_type": "fiat",
        "fiat": "RUB",
        "payload": payload_str,
    }

    headers = {
        "Crypto-Pay-API-Token": token,
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(CRYPTOBOT_API_URL, headers=headers, json=body, timeout=20) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"CryptoBot: HTTP {resp.status}: {text}")
                    return None
                data = await resp.json(content_type=None)
                if isinstance(data, dict) and data.get("ok") and isinstance(data.get("result"), dict):
                    res = data["result"]
                    pay_url = res.get("bot_invoice_url") or res.get("invoice_url")
                    invoice_id = res.get("invoice_id")
                    if pay_url and invoice_id is not None:
                        return pay_url, int(invoice_id)
                logger.error(f"CryptoBot: неожиданный ответ API: {data}")
                return None
    except Exception as e:
        logger.error(f"CryptoBot: ошибка при создании инвойса: {e}", exc_info=True)
        return None
