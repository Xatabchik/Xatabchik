"""Обращения к платёжным провайдерам Heleket и CryptoBot.
"""

import uuid
import aiohttp
import hashlib
import json
import base64
from decimal import Decimal
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    create_payload_pending,
    PromoUnavailableError,
)

__all__ = [
    "_create_heleket_payment_request",
    "create_cryptobot_api_invoice",
    "_create_cryptobot_invoice",
]

async def _create_heleket_payment_request(
    user_id: int,
    price: float,
    months: int,
    host_name: str | None,
    state_data: dict,
) -> str | None:
    """
    Создание инвойса в Heleket и возврат payment URL.

    Требования API:
      - POST https://api.heleket.com/v1/payment
      - Заголовки: merchant, sign (md5(base64(json_body)+API_KEY))
      - Тело (минимум): { amount, currency, order_id }
      - Дополнительно: url_callback (наш вебхук), description (положим JSON метаданных)
    """

    merchant_id = (get_setting("heleket_merchant_id") or "").strip()
    api_key = (get_setting("heleket_api_key") or "").strip()
    if not (merchant_id and api_key):
        logger.error("Heleket: не заданы merchant_id/api_key в настройках.")
        return None


    payment_id = str(uuid.uuid4())


    metadata = {
        "user_id": int(user_id),
        "months": int(months or 0),
        "price": float(Decimal(str(price)).quantize(Decimal("0.01"))),
        "action": state_data.get("action"),
        "key_id": state_data.get("key_id"),
        "host_name": host_name or state_data.get("host_name"),
        "plan_id": state_data.get("plan_id"),
        "package_id": state_data.get("package_id"),
        "customer_email": state_data.get("customer_email"),
        "payment_method": "Heleket",
        "payment_id": payment_id,
        "promo_code": state_data.get("promo_code"),
        "promo_discount": state_data.get("promo_discount"),
    }


    try:
        create_payload_pending(payment_id, user_id, float(metadata["price"]), metadata)
    except PromoUnavailableError:
        logger.warning("Heleket: промокод больше недоступен, слот не зарезервирован")
        return None
    except Exception as e:
        logger.warning(f"Heleket: не удалось создать pending: {e}")


    amount_str = f"{Decimal(str(price)).quantize(Decimal('0.01'))}"
    body: dict = {
        "amount": amount_str,
        "currency": "RUB",
        "order_id": payment_id,

        "description": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    }

    try:
        domain = (get_setting("domain") or "").strip()
    except Exception:
        domain = ""
    if domain:


        cb = f"{domain.rstrip('/')}/heleket-webhook"
        body["url_callback"] = cb


    body_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    base64_payload = base64.b64encode(body_json.encode()).decode()
    sign = hashlib.md5((base64_payload + api_key).encode()).hexdigest()

    headers = {
        "merchant": merchant_id,
        "sign": sign,
        "Content-Type": "application/json",
    }

    url = "https://api.heleket.com/v1/payment"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=20) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Heleket: HTTP {resp.status}: {text}")
                    return None
                data = await resp.json(content_type=None)

                if isinstance(data, dict) and data.get("state") == 0:
                    try:
                        result = data.get("result") or {}
                        pay_url = result.get("url")
                        heleket_uuid = result.get("uuid")
                        if heleket_uuid:
                            from shop_bot.data_manager.database import patch_pending_metadata
                            patch_pending_metadata(payment_id, {"heleket_uuid": str(heleket_uuid)})
                        if pay_url:
                            return pay_url
                    except Exception:
                        pass
                logger.error(f"Heleket: неожиданный ответ API: {data}")
                return None
    except Exception as e:
        logger.error(f"Heleket: ошибка при создании инвойса: {e}", exc_info=True)
        return None

async def create_cryptobot_api_invoice(amount: float, payload_str: str) -> tuple[str, int] | None:
    """
    Упрощённая обёртка для создания инвойса в Crypto Pay (CryptoBot), используемая
    из webapp (shop_bot/webapp/handlers.py). В отличие от _create_cryptobot_invoice,
    не создаёт pending-транзакцию (это уже делает вызывающий код) и принимает
    готовый payload (обычно payment_id).

    Возвращает (bot_invoice_url, invoice_id) либо None при ошибке.
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
    url = "https://pay.crypt.bot/api/createInvoice"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=20) as resp:
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
                        from shop_bot.data_manager.database import patch_pending_metadata
                        patch_pending_metadata(payload_str, {"cryptobot_invoice_id": str(invoice_id)})
                        return pay_url, int(invoice_id)
                logger.error(f"CryptoBot: неожиданный ответ API: {data}")
                return None
    except Exception as e:
        logger.error(f"CryptoBot: ошибка при создании инвойса (api wrapper): {e}", exc_info=True)
        return None


async def _create_cryptobot_invoice(
    user_id: int,
    price_rub: float,
    months: int,
    host_name: str | None,
    state_data: dict,
) -> tuple[str, int] | None:
    """
    Создание инвойса в Crypto Pay (CryptoBot) и возврат bot_invoice_url.

    Эндпоинт: POST https://pay.crypt.bot/api/createInvoice
    Заголовки: { 'Crypto-Pay-API-Token': <token>, 'Content-Type': 'application/json' }

    Мы создаём инвойс в фиате RUB, чтобы не конвертировать курсы вручную.
    В payload записываем строку, которую ожидает наш вебхук '/cryptobot-webhook'.
    """
    token = (get_setting("cryptobot_token") or "").strip()
    if not token:
        logger.error("CryptoBot: не указан токен API в настройках.")
        return None



    action = state_data.get("action")
    key_id = state_data.get("key_id")
    plan_id = state_data.get("plan_id")
    customer_email = state_data.get("customer_email")
    pm = "CryptoBot"
    promo_code = state_data.get("promo_code")
    promo_discount = state_data.get("promo_discount")

    payment_id = str(uuid.uuid4())
    metadata = {
        "user_id": int(user_id),
        "months": int(months or 0),
        "price": float(Decimal(str(price_rub)).quantize(Decimal("0.01"))),
        "action": action,
        "key_id": key_id,
        "host_name": (host_name or state_data.get("host_name")),
        "plan_id": plan_id,
        "package_id": state_data.get("package_id"),
        "customer_email": customer_email,
        "payment_method": "CryptoBot",
        "promo_code": promo_code,
        "promo_discount": float(Decimal(str(promo_discount)).quantize(Decimal("0.01"))) if promo_discount else 0.0,
        "payment_id": payment_id,
    }
    try:
        create_payload_pending(payment_id, int(user_id), float(metadata["price"]), metadata)
    except PromoUnavailableError:
        logger.warning("CryptoBot: промокод больше недоступен, слот не зарезервирован")
        return None
    except Exception as e:
        logger.warning(f"CryptoBot: не удалось создать pending для {payment_id}: {e}")


    price_str = f"{Decimal(str(price_rub)).quantize(Decimal('0.01'))}"
    parts = [
        str(int(user_id)),
        str(int(months or 0)),
        price_str,
        str(action or ""),
        str(key_id if key_id is not None else "None"),
        str((host_name or state_data.get('host_name') or "")),
        str(plan_id if plan_id is not None else "None"),
        str(customer_email if customer_email is not None else "None"),
        pm,
    ]

    parts.append(str(promo_code if promo_code else "None"))
    try:
        promo_discount_str = f"{Decimal(str(promo_discount)).quantize(Decimal('0.01'))}" if promo_discount else "0"
    except Exception:
        promo_discount_str = "0"
    parts.append(promo_discount_str)
    payload_str = payment_id

    body = {
        "amount": price_str,
        "currency_type": "fiat",
        "fiat": "RUB",
        "payload": payment_id,


    }

    headers = {
        "Crypto-Pay-API-Token": token,
        "Content-Type": "application/json",
    }

    url = "https://pay.crypt.bot/api/createInvoice"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=20) as resp:
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
                        from shop_bot.data_manager.database import patch_pending_metadata
                        patch_pending_metadata(payment_id, {"cryptobot_invoice_id": str(invoice_id)})
                        return pay_url, int(invoice_id)
                logger.error(f"CryptoBot: неожиданный ответ API: {data}")
                return None
    except Exception as e:
        logger.error(f"CryptoBot: ошибка при создании инвойса: {e}", exc_info=True)
        return None


    payment_id = str(uuid.uuid4())


    metadata = {
        "user_id": int(user_id),
        "months": int(months or 0),
        "price": float(Decimal(str(price)).quantize(Decimal("0.01"))),
        "action": state_data.get("action"),
        "key_id": state_data.get("key_id"),
        "host_name": host_name or state_data.get("host_name"),
        "plan_id": state_data.get("plan_id"),
        "customer_email": state_data.get("customer_email"),
        "payment_method": "Heleket",
        "payment_id": payment_id,
    }


    try:
        create_payload_pending(payment_id, user_id, float(metadata["price"]), metadata)
    except Exception as e:
        logger.warning(f"Heleket: не удалось создать pending: {e}")


    amount_str = f"{Decimal(str(price)).quantize(Decimal('0.01'))}"
    body: dict = {
        "amount": amount_str,
        "currency": "RUB",
        "order_id": payment_id,

        "description": json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
    }

    try:
        domain = (get_setting("domain") or "").strip()
    except Exception:
        domain = ""
    if domain:


        cb = f"{domain.rstrip('/')}/heleket-webhook"
        body["url_callback"] = cb


    body_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    base64_payload = base64.b64encode(body_json.encode()).decode()
    sign = hashlib.md5((base64_payload + api_key).encode()).hexdigest()

    headers = {
        "merchant": merchant_id,
        "sign": sign,
        "Content-Type": "application/json",
    }

    url = "https://api.heleket.com/v1/payment"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=body, timeout=20) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"Heleket: HTTP {resp.status}: {text}")
                    return None
                data = await resp.json(content_type=None)

                if isinstance(data, dict) and data.get("state") == 0:
                    try:
                        result = data.get("result") or {}
                        pay_url = result.get("url")
                        if pay_url:
                            return pay_url
                    except Exception:
                        pass
                logger.error(f"Heleket: неожиданный ответ API: {data}")
                return None
    except Exception as e:
        logger.error(f"Heleket: ошибка при создании инвойса: {e}", exc_info=True)
        return None
