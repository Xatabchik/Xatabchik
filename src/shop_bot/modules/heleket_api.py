"""
Клиент для платёжного провайдера Heleket (крипто-эквайринг).

Вынесен в отдельный переиспользуемый модуль на основе логики, которая ранее существовала
только внутри `bot/handlers.py` (`_create_heleket_payment_request`). Используется как
основным ботом, так и Telegram Mini App (shop_bot.webapp.handlers).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from decimal import Decimal

import aiohttp

from shop_bot.data_manager.database import get_setting

logger = logging.getLogger(__name__)

HELEKET_API_URL = "https://api.heleket.com/v1/payment"


async def create_heleket_payment_request(
    *,
    amount: float,
    currency: str = "RUB",
    description: str = "",
    return_url: str | None = None,
    user_id: int | None = None,
    email: str | None = None,
    order_id: str | None = None,
) -> dict | None:
    """Создать инвойс в Heleket.

    `order_id` — это идентификатор платежа (должен совпадать с payment_id, под которым
    заказ сохранён через create_payload_pending, иначе вебхук не сможет сопоставить оплату).
    `description` — произвольный текст описания заказа, отображается в кабинете Heleket.

    Возвращает dict вида {"payment_url": str, "raw": dict} при успехе, иначе None.
    """
    merchant_id = (get_setting("heleket_merchant_id") or "").strip()
    api_key = (get_setting("heleket_api_key") or "").strip()
    if not (merchant_id and api_key):
        logger.error("Heleket: не заданы merchant_id/api_key в настройках.")
        return None

    amount_str = f"{Decimal(str(amount)).quantize(Decimal('0.01'))}"

    body: dict = {
        "amount": amount_str,
        "currency": currency or "RUB",
        "order_id": order_id or f"webapp-{user_id or 0}",
    }
    if description:
        body["description"] = description[:255]


    try:
        domain = (get_setting("domain") or "").strip()
    except Exception:
        domain = ""
    if domain:
        body["url_callback"] = f"{domain.rstrip('/')}/heleket-webhook"
    if return_url:
        body["url_success"] = return_url
        body["url_return"] = return_url

    body_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    base64_payload = base64.b64encode(body_json.encode()).decode()
    sign = hashlib.md5((base64_payload + api_key).encode()).hexdigest()

    headers = {
        "merchant": merchant_id,
        "sign": sign,
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(HELEKET_API_URL, headers=headers, json=body, timeout=20) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Heleket: HTTP {resp.status}: {text}")
                    return None
                data = await resp.json(content_type=None)
                if isinstance(data, dict) and data.get("state") == 0:
                    result = data.get("result") or {}
                    pay_url = result.get("url")
                    if pay_url:
                        return {"payment_url": pay_url, "raw": data}
                logger.error(f"Heleket: неожиданный ответ API: {data}")
                return None
    except Exception as e:
        logger.error(f"Heleket: ошибка при создании инвойса: {e}", exc_info=True)
        return None
