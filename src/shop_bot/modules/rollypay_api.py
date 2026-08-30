"""Клиент RollyPay: создание платежа, сверка статуса, проверка HMAC вебхука.

Базовый URL зафиксирован (без настройки из админки) — так нельзя увести запросы
на чужой хост. Выводы USDT в этот модуль не входят.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://api.rollypay.io/api/v1"
WEBHOOK_TIMESTAMP_TOLERANCE_SEC = 300
_PAYMENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _safe_id(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw or not _PAYMENT_ID_RE.fullmatch(raw):
        return None
    return raw


def verify_webhook_signature(
    raw_body: bytes,
    timestamp: str | int | None,
    signature: str | None,
    signing_secret: str,
    *,
    tolerance: int | None = WEBHOOK_TIMESTAMP_TOLERANCE_SEC,
    now: float | None = None,
) -> bool:
    """HMAC-SHA256(`{unix_ts}.{raw_body}`) в заголовке X-Signature, как в SDK RollyPay."""
    secret = (signing_secret or "").strip()
    sig = (signature or "").strip()
    if not secret or not sig:
        return False
    try:
        timestamp_int = int(str(timestamp).strip())
    except (TypeError, ValueError, AttributeError):
        return False
    clock = time.time() if now is None else now
    if tolerance is not None and abs(clock - timestamp_int) > tolerance:
        return False
    body = raw_body if isinstance(raw_body, (bytes, bytearray)) else str(raw_body or "").encode("utf-8")
    payload = str(timestamp_int).encode("utf-8") + b"." + bytes(body)
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def get_payment_sync(api_key: str, payment_id: str, timeout: int = 20) -> Optional[dict]:
    """Синхронный GET /payments/{id} для Flask-вебхука. Не доверяем телу колбэка."""
    key = (api_key or "").strip()
    pid = _safe_id(payment_id)
    if not key or not pid:
        return None
    url = f"{BASE_URL}/payments/{pid}"
    headers = {
        "X-API-Key": key,
        "X-Nonce": str(uuid.uuid4()),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as e:
        logger.error("RollyPay get_payment_sync failed payment_id=%s err=%s", pid, e)
        return None


class RollyPayAPI:
    def __init__(self, api_key: str, terminal_id: str = ""):
        self.api_key = (api_key or "").strip()
        self.terminal_id = (terminal_id or "").strip()

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "X-Nonce": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
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
    ) -> tuple[str | None, str | None]:
        """Возвращает (pay_url, provider_payment_id) или (None, None)."""
        if not self.api_key:
            logger.error("RollyPay: не задан api_key")
            return None, None
        oid = _safe_id(order_id)
        if not oid:
            logger.error("RollyPay: некорректный order_id")
            return None, None

        payload: dict[str, Any] = {
            "amount": f"{float(amount):.2f}",
            "payment_currency": "RUB",
            "order_id": oid,
            "description": (description or "")[:250],
        }
        if self.terminal_id:
            payload["terminal_id"] = self.terminal_id
        method = (payment_method or "").strip()
        if method:
            payload["payment_method"] = method
        if customer_id:
            payload["customer_id"] = str(customer_id)[:80]
        if success_url:
            payload["success_redirect_url"] = success_url
        if fail_url:
            payload["fail_redirect_url"] = fail_url

        import aiohttp

        timeout = aiohttp.ClientTimeout(total=20, connect=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{BASE_URL}/payments", headers=self._headers(), json=payload
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        logger.error("RollyPay create_payment HTTP %s: %s", resp.status, text[:200])
                        return None, None
                    data = json.loads(text) if text else {}
        except Exception as e:
            logger.error("RollyPay create_payment failed: %s", e, exc_info=True)
            return None, None

        if not isinstance(data, dict):
            return None, None
        pay_url = data.get("pay_url")
        provider_id = data.get("payment_id")
        if not pay_url:
            logger.error("RollyPay create_payment: нет pay_url")
            return None, None
        return str(pay_url), (str(provider_id) if provider_id else None)

    async def get_payment(self, payment_id: str) -> Optional[dict]:
        pid = _safe_id(payment_id)
        if not self.api_key or not pid:
            return None
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=20, connect=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{BASE_URL}/payments/{pid}", headers=self._headers()
                ) as resp:
                    if resp.status >= 400:
                        logger.error("RollyPay get_payment HTTP %s id=%s", resp.status, pid)
                        return None
                    data = await resp.json(content_type=None)
                    return data if isinstance(data, dict) else None
        except Exception as e:
            logger.error("RollyPay get_payment failed id=%s err=%s", pid, e, exc_info=True)
            return None
