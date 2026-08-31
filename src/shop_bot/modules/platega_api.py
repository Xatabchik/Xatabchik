"""
Клиент для платёжного провайдера Platega.

Вынесен в отдельный переиспользуемый модуль, чтобы им могли пользоваться и основной
бот (aiogram, см. shop_bot.bot.handlers), и Telegram Mini App (shop_bot.webapp.handlers).

Логика идентична внутренним функциям `_platega_request`/`_create_platega_payment_link`,
которые ранее существовали только внутри `bot/handlers.py`.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

import aiohttp

logger = logging.getLogger(__name__)

_TX_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def get_transaction_sync(
    merchant_id: str,
    secret: str,
    transaction_id: str,
    base_url: str | None = None,
    timeout: int = 20,
) -> dict | None:
    """Синхронный GET /transaction/{id} для Flask-вебхука. Телу колбэка не доверяем."""
    mid = (merchant_id or "").strip()
    sec = (secret or "").strip()
    txid = str(transaction_id or "").strip()
    if not mid or not sec or not txid or not _TX_ID_RE.fullmatch(txid):
        return None
    base = (base_url or "https://app.platega.io").strip().rstrip("/")
    url = f"{base}/transaction/{txid}"
    req = urllib.request.Request(
        url,
        headers={
            "X-MerchantId": mid,
            "X-Secret": sec,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as e:
        logger.error("Platega get_transaction_sync failed txid=%s err=%s", txid, e)
        return None


class PlategaAPI:
    """Простой асинхронный клиент Platega API.

    Использование:
        api = PlategaAPI(merchant_id, secret)
        transaction_id, redirect_url = await api.create_payment(
            amount, description, payment_id, return_url, failed_url, method_code
        )
    """

    def __init__(self, merchant_id: str, secret: str, base_url: str | None = None):
        self.merchant_id = (merchant_id or "").strip()
        self.secret = (secret or "").strip()
        self.base_url = (base_url or "https://app.platega.io").strip().rstrip("/")

    async def _request(self, method: str, endpoint: str, *, json_data: dict | None = None) -> dict | None:
        url = self.base_url + endpoint
        headers = {
            "X-MerchantId": self.merchant_id,
            "X-Secret": self.secret,
            "Content-Type": "application/json",
        }
        try:
            timeout = aiohttp.ClientTimeout(total=25, connect=10, sock_read=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, headers=headers, json=json_data) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        logger.error(f"Platega API HTTP {resp.status}: {text}")
                        return None
                    if not text:
                        return None
                    try:
                        return json.loads(text)
                    except Exception:
                        return None
        except Exception as e:
            logger.error(f"Platega request failed: {e}", exc_info=True)
            return None

    async def create_payment(
        self,
        amount: float,
        description: str,
        payment_id: str,
        return_url: str,
        failed_url: str,
        method_code: int = 2,
    ) -> tuple[str | None, str | None]:
        """Создать платёж в Platega.

        Возвращает кортеж (redirect_url, transaction_id) — именно в таком порядке,
        чтобы соответствовать историческому поведению `bot/handlers.py::_create_platega_payment_link`.
        """
        body = {
            "paymentMethod": int(method_code or 2),
            "paymentDetails": {"amount": round(float(amount), 2), "currency": "RUB"},
            "description": (description or "")[:64],
            "return": return_url,
            "failedUrl": failed_url,
            "payload": payment_id,
        }
        res = await self._request("POST", "/transaction/process", json_data=body)
        if not res:
            return None, None
        redirect_url = res.get("redirect")
        txid = res.get("transactionId") or res.get("id")
        return (str(redirect_url) if redirect_url else None, str(txid) if txid else None)


    async def get_transaction(self, transaction_id: str) -> dict | None:
        """GET /transaction/{id} — сверка статуса по provider transaction ID."""
        txid = str(transaction_id or "").strip()
        if not txid:
            return None
        logger.info("Platega get_transaction provider_transaction_id=%s", txid)
        return await self._request("GET", f"/transaction/{txid}")
