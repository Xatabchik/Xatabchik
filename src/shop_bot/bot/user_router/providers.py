"""Платёжные провайдеры Rollypay, Platega и ЮMoney: создание ссылок на оплату.
"""

import uuid
import aiohttp
import json
from urllib.parse import urlencode
from decimal import Decimal
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    create_payload_pending,
    get_plan_by_id,
    PromoUnavailableError,
)

__all__ = [
    "_rollypay_is_enabled",
    "_create_rollypay_payment_link",
    "_platega_is_enabled",
    "_platega_get_base_url",
    "_platega_get_method_code",
    "_platega_request",
    "_create_platega_payment_link",
    "_get_platega_transaction",
    "_build_yoomoney_link",
]

def _rollypay_is_enabled() -> bool:
    return bool(
        (get_setting("rollypay_api_key") or "").strip()
        and (get_setting("rollypay_signing_secret") or "").strip()
    )

async def _create_rollypay_payment_link(
    *, amount_rub, payment_id: str, description: str, customer_id: str = ""
):
    from shop_bot.modules.rollypay_api import RollyPayAPI

    api_key = (get_setting("rollypay_api_key") or "").strip()
    terminal_id = (get_setting("rollypay_terminal_id") or "").strip()
    method = (get_setting("rollypay_payment_method") or "").strip()
    bot_username = (get_setting("telegram_bot_username") or "").strip().lstrip("@")
    return_url = f"https://t.me/{bot_username}" if bot_username else ""
    client = RollyPayAPI(api_key, terminal_id)
    return await client.create_payment(
        float(amount_rub), description, payment_id, return_url, return_url,
        payment_method=method,
        customer_id=customer_id,
    )

def _platega_is_enabled() -> bool:
    return bool((get_setting("platega_merchant_id") or "").strip() and (get_setting("platega_secret") or "").strip())

def _platega_get_base_url() -> str:
    return (get_setting("platega_base_url") or "https://app.platega.io").strip().rstrip("/")

def _platega_get_method_code() -> int:
    raw = (get_setting("platega_active_methods") or "2").strip()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            code = int(part)
        except Exception:
            continue
        if code > 0:
            return code
    return 2

async def _platega_request(method: str, endpoint: str, *, json_data: dict | None = None) -> dict | None:
    import aiohttp
    url = _platega_get_base_url() + endpoint
    headers = {
        "X-MerchantId": (get_setting("platega_merchant_id") or "").strip(),
        "X-Secret": (get_setting("platega_secret") or "").strip(),
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

async def _create_platega_payment_link(*, amount_rub: Decimal, payment_id: str, description: str) -> tuple[str | None, str | None]:
    body = {
        "paymentMethod": _platega_get_method_code(),
        "paymentDetails": {"amount": float(amount_rub.quantize(Decimal('0.01'))), "currency": "RUB"},
        "description": (description or "")[:64],
        "return": f"https://t.me/{TELEGRAM_BOT_USERNAME}",
        "failedUrl": f"https://t.me/{TELEGRAM_BOT_USERNAME}",
        "payload": payment_id,
    }
    res = await _platega_request("POST", "/transaction/process", json_data=body)
    if not res:
        return None, None
    redirect_url = res.get("redirect")
    txid = res.get("transactionId") or res.get("id")
    return (str(redirect_url) if redirect_url else None, str(txid) if txid else None)

async def _get_platega_transaction(transaction_id: str) -> dict | None:
    if not transaction_id:
        return None
    return await _platega_request("GET", f"/transaction/{transaction_id}")

def _build_yoomoney_link(receiver: str, amount_rub: Decimal, label: str) -> str:
    base = "https://yoomoney.ru/quickpay/confirm.xml"
    params = {
        "receiver": (receiver or "").strip(),
        "quickpay-form": "donate",
        "targets": "Оплата подписки",
        "formcomment": "Оплата подписки",
        "short-dest": "Оплата подписки",
        "sum": f"{amount_rub:.2f}",
        "label": label,
        "successURL": f"https://t.me/{TELEGRAM_BOT_USERNAME}",

    }
    url = base + "?" + urlencode(params)
    return url


def register_providers(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_yoomoney")
    async def pay_yoomoney_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю ссылку YooMoney...")
        data = await state.get_data()
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        wallet = get_setting("yoomoney_wallet")
        secret = get_setting("yoomoney_secret")
        if not wallet or not secret:
            await callback.message.edit_text("❌ YooMoney временно недоступен.")
            await state.clear()
            return

        w = (wallet or "").strip()
        if not (w.isdigit() and len(w) >= 11):
            await callback.message.edit_text("❌ Некорректный номер кошелька YooMoney. Проверьте в панели настроек.")
            await state.clear()
            return
        price_rub = Decimal(str(data.get('final_price', plan['price'])))
        if price_rub < Decimal("1.00"):
            await callback.message.edit_text("❌ Минимальная сумма перевода YooMoney — 1 RUB. Выберите другой тариф или способ оплаты.")
            await state.clear()
            return
        user_id = callback.from_user.id
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)
        payment_id = str(uuid.uuid4())
        promo_code = (data.get("promo_code") or "").strip() if isinstance(data, dict) else ""
        promo_discount = float(data.get("promo_discount") or 0) if promo_code else 0.0
        metadata = {
            "user_id": user_id,
            "months": months,
            "duration_days": duration_days,
            "price": float(price_rub),
            "action": data.get('action'),
            "key_id": data.get('key_id'),
            "host_name": data.get('host_name'),
            "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'),
            "payment_method": "YooMoney",
            "payment_id": payment_id,
            "promo_code": promo_code,
            "promo_discount": promo_discount,
        }
        try:
            create_payload_pending(payment_id, user_id, float(price_rub), metadata)
        except PromoUnavailableError:
            await callback.message.edit_text("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
            return
        pay_url = _build_yoomoney_link(wallet, price_rub, payment_id)
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_yoomoney_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_yoomoney")
    async def topup_yoomoney_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        logger.info(f"💜 Пользователь {user_id} инициировал платеж через ЮMoney")
        
        await callback.answer("Готовлю YooMoney...")
        data = await state.get_data()
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        wallet = get_setting("yoomoney_wallet")
        secret = get_setting("yoomoney_secret")
        
        logger.info(f"💰 Детали платежа: сумма={amount_rub:.2f} RUB, кошелек={wallet}")
        
        if not wallet or not secret or amount_rub <= 0:
            logger.warning(f"❌ ЮMoney недоступен: кошелек={bool(wallet)}, секрет={bool(secret)}, сумма={amount_rub}")
            await callback.message.edit_text("❌ YooMoney временно недоступен.")
            await state.clear()
            return
        w = (wallet or "").strip()
        if not (w.isdigit() and len(w) >= 11):
            logger.warning(f"❌ Неверный формат кошелька: {w}")
            await callback.message.edit_text("❌ Некорректный номер кошелька YooMoney. Проверьте в панели настроек.")
            await state.clear()
            return
        if amount_rub < Decimal("1.00"):
            logger.warning(f"❌ Сумма слишком мала: {amount_rub}")
            await callback.message.edit_text("❌ Минимальная сумма перевода YooMoney — 1 RUB. Введите сумму побольше.")
            await state.clear()
            return
        
        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "YooMoney",
            "payment_id": payment_id,
        }
        
        logger.info(f"📝 Создаем ожидающую транзакцию: {payment_id}")
        create_payload_pending(payment_id, user_id, float(amount_rub), metadata)
        pay_url = _build_yoomoney_link(wallet, amount_rub, payment_id)
        
        logger.info(f"🔗 Сгенерирован URL платежа для пользователя {user_id}: {amount_rub:.2f} RUB")
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_yoomoney_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()
