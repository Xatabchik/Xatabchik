"""Пополнение баланса.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import CreateTopUpPaymentRequest


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import get_setting
import uuid
import traceback
from shop_bot.data_manager.remnawave_repository import create_payload_pending
from decimal import Decimal, ROUND_HALF_UP

from shop_bot.modules.platega_api import PlategaAPI
from shop_bot.modules.heleket_api import create_heleket_payment_request
from shop_bot.bot.keyboards import (
    create_payment_keyboard,
    create_cryptobot_payment_keyboard,
    create_yoomoney_payment_keyboard,
)
from shop_bot.bot.handlers import create_cryptobot_api_invoice
from yookassa import Configuration as YookassaConfiguration, Payment as YookassaPayment


@app.post("/api/create-topup-payment")
async def api_create_topup_payment(req: CreateTopUpPaymentRequest, request: Request):
    """Create a balance top-up payment (action=top_up), mirroring the bot TopUpProcess flow."""
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()

        user_id = int(user["telegram_id"])
        method_id = (req.payment_method or "").strip()
        if method_id in ("pay_balance", "pay_referral_balance"):
            return {"ok": False, "error": "Нельзя пополнить баланс с внутреннего баланса"}

        try:
            amount = Decimal(str(req.amount)).quantize(Decimal("0.01"))
        except Exception:
            return {"ok": False, "error": "Введите корректную сумму, например: 300"}
        if amount <= 0:
            return {"ok": False, "error": "Сумма должна быть положительной"}
        if amount < Decimal("10"):
            return {"ok": False, "error": "Минимальная сумма пополнения: 10 RUB"}
        if amount > Decimal("100000"):
            return {"ok": False, "error": "Максимальная сумма пополнения: 100000 RUB"}

        final_price = float(amount)
        bot_username = get_setting("telegram_bot_username") or ""
        return_url = f"https://t.me/{bot_username}" if bot_username else "https://t.me"

        # --- YooKassa ---
        if method_id == "pay_yookassa":
            shop_id, secret = get_setting("yookassa_shop_id"), get_setting("yookassa_secret_key")
            if not shop_id or not secret:
                return {"ok": False, "error": "YooKassa не настроена"}
            YookassaConfiguration.account_id = shop_id
            YookassaConfiguration.secret_key = secret
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "YooKassa",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            price_str = f"{amount:.2f}"
            receipt = _yookassa_receipt("Пополнение баланса", price_str)
            payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": f"Пополнение баланса на {price_str} RUB",
                "metadata": {"payment_id": pid},
            }
            if receipt:
                payload["receipt"] = receipt
            try:
                pay_obj = YookassaPayment.create(payload, uuid.uuid4())
                pay_url = pay_obj.confirmation.confirmation_url
                try:
                    provider_payment_id = getattr(pay_obj, "id", None)
                    if provider_payment_id:
                        meta2 = dict(meta)
                        meta2["yookassa_payment_id"] = str(provider_payment_id)
                        create_payload_pending(pid, user_id, final_price, meta2)
                except Exception as e:
                    logger.warning(f"YooKassa topup: failed to store provider id for {pid}: {e}")
                kb = create_payment_keyboard(pay_url)
                await _send_telegram_message(
                    user_id,
                    f"<b>Пополнение баланса через ЮKassa</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Вы можете оплатить счёт здесь или в WebApp.</i>",
                    kb,
                )
                return {"ok": True, "payment_url": pay_url, "payment_id": pid, "message": "Счёт создан"}
            except Exception as e:
                logger.error(f"YooKassa topup error: {e}")
                return {"ok": False, "error": f"Ошибка YooKassa: {e}"}

        # --- Platega ---
        if method_id == "pay_platega":
            mid, key = get_setting("platega_merchant_id"), get_setting("platega_secret")
            if not mid or not key:
                return {"ok": False, "error": "Platega не настроена"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "Platega",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            try:
                platega = _platega_api() or PlategaAPI(mid, key)
                url, txid = await platega.create_payment(
                    final_price,
                    "Пополнение баланса",
                    pid,
                    return_url,
                    return_url,
                    _platega_method_code_from_settings(),
                )
                if url:
                    _store_platega_transaction_id(pid, user_id, final_price, meta, txid)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(
                        user_id,
                        f"<b>Пополнение баланса через Platega</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счёт также доступен в WebApp.</i>",
                        kb,
                    )
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки Platega"}
            except Exception as e:
                return {"ok": False, "error": f"Ошибка Platega: {e}"}

        # --- RollyPay ---
        if method_id == "pay_rollypay":
            if not _rollypay_is_enabled():
                return {"ok": False, "error": "RollyPay не настроена"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "RollyPay",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            try:
                rollypay = _rollypay_api()
                if not rollypay:
                    return {"ok": False, "error": "RollyPay не настроена"}
                url, provider_id = await rollypay.create_payment(
                    float(final_price),
                    "Пополнение баланса",
                    pid,
                    return_url,
                    return_url,
                    payment_method=(get_setting("rollypay_payment_method") or ""),
                    customer_id=str(user_id),
                )
                if url:
                    _store_rollypay_payment_id(pid, user_id, final_price, meta, provider_id)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(
                        user_id,
                        f"<b>Пополнение баланса по СБП</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счёт также доступен в WebApp.</i>",
                        kb,
                    )
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки RollyPay"}
            except Exception as e:
                logger.error(f"RollyPay topup error: {e}", exc_info=True)
                return {"ok": False, "error": "Ошибка получения ссылки RollyPay"}

        # --- CryptoBot ---
        if method_id == "pay_cryptobot":
            if not get_setting("cryptobot_token"):
                return {"ok": False, "error": "CryptoBot не настроен"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "CryptoBot",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            try:
                res = await create_cryptobot_api_invoice(amount=final_price, payload_str=pid)
                if res:
                    kb = create_cryptobot_payment_keyboard(res[0], res[1])
                    await _send_telegram_message(
                        user_id,
                        f"<b>Пополнение баланса через CryptoBot</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счёт также доступен в WebApp.</i>",
                        kb,
                    )
                    return {"ok": True, "payment_url": res[0], "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка API CryptoBot"}
            except Exception as e:
                return {"ok": False, "error": f"Ошибка CryptoBot: {e}"}

        # --- Heleket ---
        if method_id == "pay_heleket":
            if not ((get_setting("heleket_merchant_id") or "") and (get_setting("heleket_api_key") or "")):
                return {"ok": False, "error": "Heleket не настроен"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "Heleket",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            try:
                result = await create_heleket_payment_request(
                    amount=final_price,
                    currency="RUB",
                    description="Пополнение баланса",
                    order_id=pid,
                    return_url=return_url,
                    user_id=user_id,
                    email=user.get("email") or "no-email",
                )
                if result and result.get("payment_url"):
                    pay_url = result["payment_url"]
                    kb = create_payment_keyboard(pay_url)
                    await _send_telegram_message(
                        user_id,
                        f"<b>Пополнение баланса через Crypto (Heleket)</b>\n\nСумма: <b>{final_price:.2f} RUB</b>",
                        kb,
                    )
                    return {"ok": True, "payment_url": pay_url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка создания платежа Heleket"}
            except Exception as e:
                logger.error(f"Heleket topup error: {e}")
                return {"ok": False, "error": f"Ошибка Heleket: {e}"}

        # --- YooMoney ---
        if method_id == "pay_yoomoney":
            if (get_setting("yoomoney_enabled") or "false").strip().lower() != "true":
                return {"ok": False, "error": "YooMoney недоступен"}
            wallet = (get_setting("yoomoney_wallet") or "").strip()
            secret = (get_setting("yoomoney_secret") or "").strip()
            if not wallet or not secret:
                return {"ok": False, "error": "YooMoney не настроен"}
            if not (wallet.isdigit() and len(wallet) >= 11):
                return {"ok": False, "error": "Некорректный номер кошелька YooMoney"}
            if amount < Decimal("1.00"):
                return {"ok": False, "error": "Минимальная сумма YooMoney — 1 RUB"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "YooMoney",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            link = _build_yoomoney_link(wallet, amount, pid, "Пополнение баланса")
            kb = create_yoomoney_payment_keyboard(link, pid)
            await _send_telegram_message(
                user_id,
                f"<b>Пополнение баланса через YooMoney</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счёт также доступен в WebApp.</i>",
                kb,
            )
            return {"ok": True, "payment_url": link, "payment_id": pid, "message": "Счёт создан"}

        # --- TON Connect ---
        if method_id == "pay_tonconnect":
            return {"ok": False, "error": "TON Connect пока недоступен через WebApp"}

        # --- Stars ---
        if method_id == "pay_stars":
            try:
                stars_ratio = Decimal(str(get_setting("stars_per_rub") or "0"))
            except Exception:
                stars_ratio = Decimal("0")
            if (get_setting("stars_enabled") or "false").strip().lower() != "true" or stars_ratio <= 0:
                return {"ok": False, "error": "Stars отключены"}
            stars_amount = int((amount * stars_ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if stars_amount <= 0:
                stars_amount = 1
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id,
                "price": final_price,
                "action": "top_up",
                "payment_method": "Telegram Stars",
                "payment_id": pid,
            }
            create_payload_pending(pid, user_id, final_price, meta)
            await _send_invoice_stars(
                user_id,
                "Пополнение баланса",
                f"Пополнение на {final_price:.2f} RUB",
                pid,
                stars_amount,
            )
            return {
                "ok": True,
                "message": "Счёт Stars отправлен в бот",
                "payment_id": pid,
                "payment_url": f"tg://resolve?domain={bot_username}" if bot_username else None,
                "stars": True,
            }

        return {"ok": False, "error": "Метод не поддерживается"}
    except Exception as e:
        logger.error(f"API Create TopUp Payment Error: {e}")
        return {"ok": False, "error": str(e), "details": traceback.format_exc()}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_create_topup_payment",
]
