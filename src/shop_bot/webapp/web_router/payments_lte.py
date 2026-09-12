"""Докупка LTE-трафика.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import CreateLteTopUpPaymentRequest


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import get_setting
import uuid
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from shop_bot.data_manager.remnawave_repository import (
    create_payload_pending,
    deduct_from_balance,
    deduct_from_referral_balance,
)
from shop_bot.data_manager.database import (
    get_traffic_packages_for_plan,
    get_traffic_package_by_id,
)
from decimal import Decimal, ROUND_HALF_UP

from shop_bot.modules.platega_api import PlategaAPI
from shop_bot.modules.heleket_api import create_heleket_payment_request
from shop_bot.bot.keyboards import (
    create_payment_keyboard,
    create_cryptobot_payment_keyboard,
    create_yoomoney_payment_keyboard,
)
from shop_bot.bot.handlers import create_cryptobot_api_invoice, process_successful_payment
from yookassa import Configuration as YookassaConfiguration, Payment as YookassaPayment


def _lte_topup_metadata(user_id: int, key_id: int, package: dict, payment_method: str, payment_id: str, host_name: str | None) -> dict:
    """Метаданные те же, что бот кладёт в pending для process_successful_payment."""
    return {
        "user_id": int(user_id),
        "price": float(package.get("price") or 0),
        "action": "lte_gb_topup",
        "key_id": int(key_id),
        "package_id": int(package.get("package_id") or 0),
        "size_gb": float(package.get("size_gb") or 0),
        "payment_method": payment_method,
        "payment_id": payment_id,
        "host_name": host_name,
        "plan_id": int(package.get("plan_id") or 0),
    }


@app.get("/api/lte-packages")
async def api_lte_packages(request: Request, key_id: int, token: str | None = None):
    """Пакеты докупки LTE для ключа владельца. Цена/размер только с сервера."""
    user = _require_authenticated_user(request, token=token)
    if not user:
        return _unauthorized()
    user_id = int(user["telegram_id"])
    key, plan = _owned_lte_key_and_plan(user_id, key_id)
    if not key or not plan:
        return {"ok": False, "error": "Для тарифа этого ключа не настроена докупка LTE."}

    packages = get_traffic_packages_for_plan(int(plan["plan_id"]), only_active=True, pool="lte")
    if not packages:
        return {"ok": False, "error": "Пакеты докупки LTE для этого тарифа пока не настроены. Обратитесь к администратору."}

    lte = _lte_card_state(key)
    items = []
    for pkg in packages:
        size_gb = float(pkg.get("size_gb") or 0)
        price = float(pkg.get("price") or 0)
        items.append({
            "package_id": int(pkg["package_id"]),
            "size_gb": size_gb,
            "size_txt": _format_gb_amount(size_gb),
            "price": price,
        })
    return {
        "ok": True,
        "key_id": int(key["key_id"]),
        "lte_info": lte.get("lte_info") or "",
        "lte_label": lte.get("lte_label") or "LTE",
        "packages": items,
    }


@app.post("/api/create-lte-topup-payment")
async def api_create_lte_topup_payment(req: CreateLteTopUpPaymentRequest, request: Request):
    """Оплата докупки LTE: те же методы, что в боте; цена берётся из пакета в БД."""
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        key, plan = _owned_lte_key_and_plan(user_id, req.key_id)
        if not key or not plan:
            return {"ok": False, "error": "Для тарифа этого ключа не настроена докупка LTE."}

        package = get_traffic_package_by_id(int(req.package_id))
        if (
            not package
            or int(package.get("plan_id") or 0) != int(plan["plan_id"])
            or str(package.get("pool") or "main").strip().lower() != "lte"
            or int(package.get("is_active") if package.get("is_active") is not None else 1) != 1
        ):
            return {"ok": False, "error": "Пакет не найден"}

        try:
            price = float(package.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0
        if price <= 0:
            return {"ok": False, "error": "Некорректная цена пакета."}

        size_gb = float(package.get("size_gb") or 0)
        size_txt = _format_gb_amount(size_gb)
        lte_label = (_lte_card_state(key).get("lte_label") or "LTE")
        description = f"Докупка {size_txt} ГБ {lte_label}-трафика"
        method_id = (req.payment_method or "").strip()
        host_name = key.get("host_name")
        bot_username = get_setting("telegram_bot_username") or ""
        return_url = f"https://t.me/{bot_username}" if bot_username else "https://t.me"

        if method_id == "pay_balance":
            if not deduct_from_balance(user_id, price):
                return {"ok": False, "error": "Недостаточно средств"}
            pid = f"balance:{user_id}:{uuid.uuid4()}"
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "Balance", pid, host_name)
            token = get_setting("telegram_bot_token")
            if not token:
                _rollback_internal_payment(
                    payment_id=pid, user_id=user_id, amount=price,
                    payment_method="Balance", reason="telegram_bot_token missing after deduct",
                )
                return {"ok": False, "error": "Бот не настроен (нет токена)"}
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                await process_successful_payment(bot, meta)
            except Exception as e:
                _rollback_internal_payment(
                    payment_id=pid, user_id=user_id, amount=price,
                    payment_method="Balance", reason=e,
                )
                return {"ok": False, "error": "Не удалось применить докупку, средства возвращены на баланс"}
            finally:
                await bot.session.close()
            return {"ok": True, "message": "Оплачено с баланса!", "paid": True}

        if method_id == "pay_referral_balance":
            if not deduct_from_referral_balance(user_id, price):
                return {"ok": False, "error": "Недостаточно средств на реферальном балансе"}
            pid = f"referral_balance:{user_id}:{uuid.uuid4()}"
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "ReferralBalance", pid, host_name)
            token = get_setting("telegram_bot_token")
            if not token:
                _rollback_internal_payment(
                    payment_id=pid, user_id=user_id, amount=price,
                    payment_method="ReferralBalance", reason="telegram_bot_token missing after deduct",
                )
                return {"ok": False, "error": "Бот не настроен (нет токена)"}
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                await process_successful_payment(bot, meta)
            except Exception as e:
                _rollback_internal_payment(
                    payment_id=pid, user_id=user_id, amount=price,
                    payment_method="ReferralBalance", reason=e,
                )
                return {"ok": False, "error": "Не удалось применить докупку, средства возвращены на реферальный баланс"}
            finally:
                await bot.session.close()
            return {"ok": True, "message": "Оплачено с реферального баланса!", "paid": True}

        if method_id == "pay_yookassa":
            shop_id, secret = get_setting("yookassa_shop_id"), get_setting("yookassa_secret_key")
            if not shop_id or not secret:
                return {"ok": False, "error": "YooKassa не настроена"}
            YookassaConfiguration.account_id = shop_id
            YookassaConfiguration.secret_key = secret
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "YooKassa", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            price_str = f"{price:.2f}"
            payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": pid},
            }
            receipt = _yookassa_receipt(description, price_str)
            if receipt:
                payload["receipt"] = receipt
            try:
                pay_obj = YookassaPayment.create(payload, pid)
                pay_url = pay_obj.confirmation.confirmation_url
                try:
                    provider_payment_id = getattr(pay_obj, "id", None)
                    if provider_payment_id:
                        meta2 = dict(meta)
                        meta2["yookassa_payment_id"] = str(provider_payment_id)
                        create_payload_pending(pid, user_id, price, meta2)
                except Exception as e:
                    logger.warning("YooKassa lte-gb: failed to store provider id for %s: %s", pid, e)
                kb = create_payment_keyboard(pay_url)
                await _send_telegram_message(
                    user_id,
                    f"<b>Докупка LTE через ЮKassa</b>\n\n{description}\nСумма: <b>{price:.2f} RUB</b>",
                    kb,
                )
                return {"ok": True, "payment_url": pay_url, "payment_id": pid, "message": "Счёт создан"}
            except Exception as e:
                logger.error(f"YooKassa lte-gb error: {e}")
                return {"ok": False, "error": f"Ошибка YooKassa: {e}"}

        if method_id == "pay_platega":
            mid, key_secret = get_setting("platega_merchant_id"), get_setting("platega_secret")
            if not mid or not key_secret:
                return {"ok": False, "error": "Platega не настроена"}
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "Platega", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            try:
                platega = _platega_api() or PlategaAPI(mid, key_secret)
                url, txid = await platega.create_payment(
                    price, description, pid, return_url, return_url, _platega_method_code_from_settings(),
                )
                if url:
                    _store_platega_transaction_id(pid, user_id, price, meta, txid)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(
                        user_id,
                        f"<b>Докупка LTE через Platega</b>\n\n{description}\nСумма: <b>{price:.2f} RUB</b>",
                        kb,
                    )
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки Platega"}
            except Exception as e:
                return {"ok": False, "error": f"Ошибка Platega: {e}"}

        if method_id == "pay_rollypay":
            if not _rollypay_is_enabled():
                return {"ok": False, "error": "RollyPay не настроена"}
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "RollyPay", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            try:
                rollypay = _rollypay_api()
                if not rollypay:
                    return {"ok": False, "error": "RollyPay не настроена"}
                url, provider_id = await rollypay.create_payment(
                    price, description, pid, return_url, return_url,
                    payment_method=(get_setting("rollypay_payment_method") or ""),
                    customer_id=str(user_id),
                )
                if url:
                    _store_rollypay_payment_id(pid, user_id, price, meta, provider_id)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(
                        user_id,
                        f"<b>Докупка LTE по СБП</b>\n\n{description}\nСумма: <b>{price:.2f} RUB</b>",
                        kb,
                    )
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки RollyPay"}
            except Exception as e:
                logger.error(f"RollyPay lte-gb error: {e}", exc_info=True)
                return {"ok": False, "error": "Ошибка получения ссылки RollyPay"}

        if method_id == "pay_cryptobot":
            if not get_setting("cryptobot_token"):
                return {"ok": False, "error": "CryptoBot не настроен"}
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "CryptoBot", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            try:
                res = await create_cryptobot_api_invoice(amount=price, payload_str=pid)
                if res:
                    kb = create_cryptobot_payment_keyboard(res[0], res[1])
                    await _send_telegram_message(
                        user_id,
                        f"<b>Докупка LTE через CryptoBot</b>\n\n{description}\nСумма: <b>{price:.2f} RUB</b>",
                        kb,
                    )
                    return {"ok": True, "payment_url": res[0], "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка API CryptoBot"}
            except Exception as e:
                return {"ok": False, "error": f"Ошибка CryptoBot: {e}"}

        if method_id == "pay_heleket":
            if not ((get_setting("heleket_merchant_id") or "") and (get_setting("heleket_api_key") or "")):
                return {"ok": False, "error": "Heleket не настроен"}
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "Heleket", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            try:
                result = await create_heleket_payment_request(
                    amount=price, currency="RUB", description=description, order_id=pid,
                    return_url=return_url, user_id=user_id, email=user.get("email") or "no-email",
                )
                if result and result.get("payment_url"):
                    pay_url = result["payment_url"]
                    kb = create_payment_keyboard(pay_url)
                    await _send_telegram_message(
                        user_id,
                        f"<b>Докупка LTE через Crypto (Heleket)</b>\n\n{description}\nСумма: <b>{price:.2f} RUB</b>",
                        kb,
                    )
                    return {"ok": True, "payment_url": pay_url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка создания платежа Heleket"}
            except Exception as e:
                logger.error(f"Heleket lte-gb error: {e}")
                return {"ok": False, "error": f"Ошибка Heleket: {e}"}

        if method_id == "pay_yoomoney":
            if (get_setting("yoomoney_enabled") or "false").strip().lower() != "true":
                return {"ok": False, "error": "YooMoney недоступен"}
            wallet = (get_setting("yoomoney_wallet") or "").strip()
            secret = (get_setting("yoomoney_secret") or "").strip()
            if not wallet or not secret:
                return {"ok": False, "error": "YooMoney не настроен"}
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "YooMoney", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            link = _build_yoomoney_link(wallet, Decimal(str(price)), pid, description)
            kb = create_yoomoney_payment_keyboard(link, pid)
            await _send_telegram_message(
                user_id,
                f"<b>Докупка LTE через YooMoney</b>\n\n{description}\nСумма: <b>{price:.2f} RUB</b>",
                kb,
            )
            return {"ok": True, "payment_url": link, "payment_id": pid, "message": "Счёт создан"}

        if method_id == "pay_tonconnect":
            return {"ok": False, "error": "TON Connect пока недоступен через WebApp"}

        if method_id == "pay_stars":
            try:
                stars_ratio = Decimal(str(get_setting("stars_per_rub") or "0"))
            except Exception:
                stars_ratio = Decimal("0")
            if (get_setting("stars_enabled") or "false").strip().lower() != "true" or stars_ratio <= 0:
                return {"ok": False, "error": "Stars отключены"}
            stars_amount = int((Decimal(str(price)) * stars_ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            if stars_amount <= 0:
                stars_amount = 1
            pid = str(uuid.uuid4())
            meta = _lte_topup_metadata(user_id, int(key["key_id"]), package, "Telegram Stars", pid, host_name)
            pending_err = _create_payload_pending_or_error(pid, user_id, price, meta)
            if pending_err:
                return pending_err
            await _send_invoice_stars(user_id, "Докупка LTE", description, pid, stars_amount)
            return {
                "ok": True,
                "message": "Счёт Stars отправлен в бот",
                "payment_id": pid,
                "payment_url": f"tg://resolve?domain={bot_username}" if bot_username else None,
                "stars": True,
            }

        return {"ok": False, "error": "Метод не поддерживается"}
    except Exception as e:
        logger.error(f"API Create LTE topup Error: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_lte_topup_metadata",
    "api_lte_packages",
    "api_create_lte_topup_payment",
]
