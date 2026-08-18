"""RollyPay API client."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://api.rollypay.io/api/v1"
TIMEOUT = aiohttp.ClientTimeout(total=20)


class RollyPayAPI:
    def __init__(self, api_key: str, terminal_id: str, signing_secret: str = ""):
        self.api_key = (api_key or "").strip()
        self.terminal_id = (terminal_id or "").strip()
        self.signing_secret = (signing_secret or "").strip()

    def _headers(self) -> dict:
        return {
            "X-API-Key": self.api_key,
            "X-Nonce": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }

    async def create_payment(
        self,
        amount,
        description: str,
        order_id: str,
        success_url: str = "",
        fail_url: str = "",
        payment_method: str = "sbp",
        customer_id: str = "",
        metadata: Optional[dict] = None,
    ):
        """Возвращает (pay_url, payment_id) или (None, None)."""
        if not self.api_key or not self.terminal_id:
            logger.error("RollyPay: не заданы api_key или terminal_id")
            return None, None

        payload: dict[str, Any] = {
            "terminal_id": self.terminal_id,
            "amount": f"{float(amount):.2f}",
            "payment_currency": "RUB",
            "order_id": order_id,
            "description": (description or "")[:250],
        }
        if payment_method:
            payload["payment_method"] = payment_method
        if customer_id:
            payload["customer_id"] = str(customer_id)
        if success_url:
            payload["success_redirect_url"] = success_url
        if fail_url:
            payload["fail_redirect_url"] = fail_url
        if metadata:
            payload["metadata"] = metadata

        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                async with session.post(
                    f"{BASE_URL}/payments", headers=self._headers(), json=payload
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        logger.error(f"RollyPay: create_payment {resp.status}: {text[:300]}")
                        return None, None
                    data = await resp.json()
        except Exception as e:
            logger.error(f"RollyPay: ошибка создания платежа: {e}", exc_info=True)
            return None, None

        pay_url = data.get("pay_url")
        if not pay_url:
            logger.error(f"RollyPay: в ответе нет pay_url: {data}")
            return None, None
        return pay_url, data.get("payment_id")

    async def get_payment(self, payment_id: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
                async with session.get(
                    f"{BASE_URL}/payments/{payment_id}", headers=self._headers()
                ) as resp:
                    if resp.status >= 400:
                        logger.error(f"RollyPay: get_payment {payment_id} -> {resp.status}")
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error(f"RollyPay: ошибка запроса платежа {payment_id}: {e}", exc_info=True)
            return None

    def verify_signature(self, raw_body: bytes, timestamp: str, signature: str) -> bool:
        """HMAC-SHA256 от строки `timestamp + "." + body`."""
        if not self.signing_secret or not signature or not timestamp:
            return False
        payload = timestamp.encode("utf-8") + b"." + raw_body
        expected = hmac.new(
            self.signing_secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature.strip())
