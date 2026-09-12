"""Способы оплаты и создание платежа за ключ.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import CreatePaymentRequest, PaymentMethodsRequest


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import get_setting
import uuid
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import traceback
from shop_bot.data_manager.remnawave_repository import (
    get_plan_by_id,
    deduct_from_balance,
    deduct_from_referral_balance,
    get_referral_balance,
    get_key_by_id,
)
import shop_bot.data_manager.remnawave_repository as rw_repo
from shop_bot.data_manager.database import (
    get_device_tiers,
    get_host,
)
from shop_bot.modules import remnawave_api
from decimal import Decimal

from shop_bot.modules.platega_api import PlategaAPI
from shop_bot.modules.heleket_api import create_heleket_payment_request
from shop_bot.bot.keyboards import (
    create_payment_keyboard,
    create_cryptobot_payment_keyboard,
    create_yoomoney_payment_keyboard,
)
from shop_bot.bot.handlers import create_cryptobot_api_invoice, process_successful_payment
from yookassa import Configuration as YookassaConfiguration, Payment as YookassaPayment


@app.post("/api/payment-methods")
async def api_get_payment_methods(req: PaymentMethodsRequest, request: Request):
    user = _require_authenticated_user(
        request, token=req.token, init_data=req.init_data
    )
    if not user:
        return _unauthorized()
    user_id = int(user["telegram_id"])
    
    methods = []
    
    # 1. YooKassa
    if (get_setting("yookassa_shop_id") or "") and (get_setting("yookassa_secret_key") or ""):
        label = "Банковская карта"
        if (get_setting("sbp_enabled") or "false").strip().lower() == "true":
            label = "СБП / Банковская карта"
        methods.append({"id": "pay_yookassa", "name": label, "icon": "credit_card"})

    # 2. Platega
    if (get_setting("platega_merchant_id") or "").strip() and (get_setting("platega_secret") or "").strip():
        methods.append({"id": "pay_platega", "name": get_setting("payment_label_platega") or "Platega", "icon": "payments"})

    if _rollypay_is_enabled():
        methods.append({"id": "pay_rollypay", "name": get_setting("payment_label_rollypay") or "СБП", "icon": "payments"})

    # 3. CryptoBot
    if get_setting("cryptobot_token"):
        methods.append({"id": "pay_cryptobot", "name": "Криптовалюта", "icon": "currency_bitcoin"})
    # 3.1 Heleket (alternative crypto)
    elif (get_setting("heleket_merchant_id") or "") and (get_setting("heleket_api_key") or ""):
        methods.append({"id": "pay_heleket", "name": "Криптовалюта", "icon": "currency_bitcoin"})

    # 4. TON Connect
    if (get_setting("ton_wallet_address") or "") and (get_setting("tonapi_key") or ""):
        methods.append({"id": "pay_tonconnect", "name": "TON Connect", "icon": "wallet"})

    # 5. Telegram Stars
    if (get_setting("stars_enabled") or "false").strip().lower() == "true":
        methods.append({"id": "pay_stars", "name": "Telegram Stars", "icon": "star"})

    # 6. YooMoney
    if (get_setting("yoomoney_enabled") or "false").strip().lower() == "true":
        methods.append({"id": "pay_yoomoney", "name": get_setting("payment_label_yoomoney") or "YooMoney", "icon": "account_balance_wallet"})

    # 7. Balance
    balance = float(user.get('balance', 0)) if user else 0
    methods.append({"id": "pay_balance", "name": f"Баланс ({balance:.0f} RUB)", "icon": "account_balance", "balance": balance})

    # 8. Referral balance (как в боте: кнопка есть в списке, UI скрывает при недостатке средств)
    ref_balance = float(get_referral_balance(user_id) or 0) if user else 0.0
    methods.append({
        "id": "pay_referral_balance",
        "name": f"Реферальный баланс ({ref_balance:.0f} RUB)",
        "icon": "diamond",
        "balance": ref_balance,
    })

    return {"ok": True, "methods": methods, "balance": balance, "referral_balance": ref_balance}


@app.post("/api/create-payment")
async def api_create_payment(req: CreatePaymentRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        plan_id = req.plan_id
        method_id = req.payment_method
        
        plan = get_plan_by_id(plan_id)
        if not plan:
            return {"ok": False, "error": "Тариф не найден"}
        
        final_price = calculate_webapp_price(float(plan['price']), user_id) 
        
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        billing_months = _billing_months_for_plan(plan)
        
        tier_device_count = req.tier_device_count
        tier_price_per_month = req.tier_price
        
        if tier_price_per_month == 0:
            tier_device_count = None
        
        if req.action == 'extend' and req.key_id:
            host_data = get_host(req.host_name) if req.host_name else None
            if host_data and host_data.get('device_mode') == 'tiers' and int(host_data.get('tier_lock_extend', 0) or 0):
                if not tier_price_per_month: 
                    key = get_key_by_id(req.key_id)
                    if key and key.get('remnawave_user_uuid'):
                        try:
                            user_info = await remnawave_api.get_user_by_uuid(key['remnawave_user_uuid'], host_name=req.host_name)
                            if user_info:
                                hwid = int(user_info.get('hwidDeviceLimit') or 1)
                                if hwid > 1:
                                    from shop_bot.data_manager import database
                                    base_devices = int(database.get_setting(f"base_device_{req.host_name}", "1"))
                                    tiers = get_device_tiers(req.host_name)
                                    for t in tiers:
                                        if t['device_count'] == hwid:
                                            tier_device_count = hwid
                                            diff = hwid - base_devices
                                            if diff < 0: diff = 0
                                            tier_price_per_month = float(diff * t['price'])
                                            break
                        except Exception as e:
                            logger.error(f"Auto-detect hwid error: {e}")
        
        if tier_price_per_month > 0:
            final_price += tier_price_per_month * billing_months
            
        action_name = req.action

        # --- APPLY PROMO DISCOUNT ---
        # Промокод — это ИСКЛЮЧИТЕЛЬНО скидка на покупку/продление/подарочную
        # покупку ключа (см. /api/apply-promo), поэтому здесь он намеренно
        # применяется только для этого набора action. Пополнение баланса
        # создаётся через отдельный эндпоинт /api/create-topup-payment, у
        # которого нет и не должно быть поля promo_code — этот if — защита на
        # случай, если сюда когда-нибудь передадут промокод вместе с другим action.
        # (Раньше здесь было мёртвое условие `promo.get('promo_type') ==
        # 'discount'` — в БД такой колонки нет и не было, поэтому скидка
        # никогда фактически не применялась к реальной сумме платежа, даже
        # если пользователь успешно "применил" промокод в интерфейсе.)
        applied_promo_code = None
        promo_discount_amount = 0.0
        if req.promo_code and action_name in ("new", "extend", "gift"):
            promo, error = rw_repo.check_promo_code_available(
                req.promo_code, user_id, plan_id=plan_id
            )
            if error:
                return {"ok": False, "error": rw_repo.promo_error_message(error)}
            if promo and (promo.get('discount_percent') or promo.get('discount_amount')):
                price_before_promo = final_price
                if promo.get('discount_percent'):
                    final_price -= final_price * (float(promo['discount_percent']) / 100)
                elif promo.get('discount_amount'):
                    final_price -= float(promo['discount_amount'])
                final_price = max(0, round(final_price, 2))
                promo_discount_amount = round(price_before_promo - final_price, 2)
                applied_promo_code = promo.get('code') or req.promo_code.strip().upper()
        
        # --- YooKassa ---
        if method_id == "pay_yookassa":
            shop_id, secret = get_setting("yookassa_shop_id"), get_setting("yookassa_secret_key")
            if not shop_id or not secret: return {"ok": False, "error": "YooKassa не настроена"}
            YookassaConfiguration.account_id = shop_id
            YookassaConfiguration.secret_key = secret
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "YooKassa", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
            if pending_err:
                return pending_err
            comment = get_transaction_comment({"id": user_id, "username": user.get("username")}, action_name, months, req.host_name)
            price_str = f"{final_price:.2f}"
            payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{get_setting('telegram_bot_username')}"},
                "capture": True, "description": comment, "metadata": meta
            }
            receipt = _yookassa_receipt(f"Подписка на {_duration_label(months, duration_days)}", price_str)
            if receipt:
                payload["receipt"] = receipt
            try:
                pay_obj = YookassaPayment.create(payload, pid)
                pay_url = pay_obj.confirmation.confirmation_url
                
                kb = create_payment_keyboard(pay_url)
                await _send_telegram_message(user_id, f"<b>Оплата через ЮKassa</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Вы можете оплатить счет здесь или в WebApp.</i>", kb)
                
                return {"ok": True, "payment_url": pay_url, "payment_id": pid, "message": "Счёт создан"}
            except Exception as e:
                logger.error(f"YooKassa error: {e}")
                return {"ok": False, "error": f"Ошибка YooKassa: {e}"}

        # --- Platega ---
        elif method_id == "pay_platega":
            mid, key = get_setting("platega_merchant_id"), get_setting("platega_secret")
            if not mid or not key: return {"ok": False, "error": "Platega не настроена"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "Platega", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
            if pending_err:
                return pending_err
            desc = f"Order {pid}"
            try:
                platega = _platega_api() or PlategaAPI(mid, key)
                url, txid = await platega.create_payment(float(final_price), desc, pid, f"https://t.me/{get_setting('telegram_bot_username')}", f"https://t.me/{get_setting('telegram_bot_username')}", 2)
                if url:
                    _store_platega_transaction_id(pid, user_id, float(final_price), meta, txid)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(user_id, f"<b>Оплата через Platega</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счет также доступен в WebApp.</i>", kb)
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки Platega"}
            except Exception as e:
                return {"ok": False, "error": f"Ошибка Platega: {e}"}

        # --- RollyPay ---
        elif method_id == "pay_rollypay":
            if not _rollypay_is_enabled():
                return {"ok": False, "error": "RollyPay не настроена"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "RollyPay", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
            if pending_err:
                return pending_err
            comment = get_transaction_comment({"id": user_id, "username": user.get("username")}, action_name, months, req.host_name)
            return_url = f"https://t.me/{get_setting('telegram_bot_username')}"
            try:
                rollypay = _rollypay_api()
                if not rollypay:
                    return {"ok": False, "error": "RollyPay не настроена"}
                url, provider_id = await rollypay.create_payment(
                    float(final_price), comment, pid, return_url, return_url,
                    payment_method=(get_setting("rollypay_payment_method") or ""),
                    customer_id=str(user_id),
                )
                if url:
                    _store_rollypay_payment_id(pid, user_id, float(final_price), meta, provider_id)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(user_id, f"<b>Оплата по СБП</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счет также доступен в WebApp.</i>", kb)
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки RollyPay"}
            except Exception as e:
                logger.error(f"RollyPay error: {e}", exc_info=True)
                return {"ok": False, "error": "Ошибка получения ссылки RollyPay"}

        # --- Platega Crypto ---
        elif method_id == "pay_platega_crypto":
            mid, key = get_setting("platega_merchant_id"), get_setting("platega_secret")
            if not mid or not key: return {"ok": False, "error": "Platega не настроена"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "Platega Crypto", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
            if pending_err:
                return pending_err
            desc = f"Order {pid}"
            try:
                platega = _platega_api() or PlategaAPI(mid, key)
                url, txid = await platega.create_payment(float(final_price), desc, pid, f"https://t.me/{get_setting('telegram_bot_username')}", f"https://t.me/{get_setting('telegram_bot_username')}", 13)
                if url:
                    _store_platega_transaction_id(pid, user_id, float(final_price), meta, txid)
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(user_id, f"<b>Оплата через Platega (Crypto)</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счет также доступен в WebApp.</i>", kb)
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки Platega Crypto"}
            except Exception as e:
                 return {"ok": False, "error": f"Ошибка Platega Crypto: {e}"}

         # --- CryptoBot ---
        elif method_id == "pay_cryptobot":
             pid = str(uuid.uuid4())
             meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "CryptoBot", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
             pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
             if pending_err:
                 return pending_err
             # payload_str format MUST match what bot expects. Using a generic format for now or just ID
             # safe encoded payload
             payload_str = f"{pid}" 
             
             try:
                 # Note: create_cryptobot_api_invoice IS imported now
                 res = await create_cryptobot_api_invoice(amount=float(final_price), payload_str=payload_str)
                 if res:
                     # res[0] is url, res[1] is invoice_id
                     kb = create_cryptobot_payment_keyboard(res[0], res[1])
                     await _send_telegram_message(user_id, f"<b>Оплата через CryptoBot</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счет также доступен в WebApp.</i>", kb)
                     return {"ok": True, "payment_url": res[0], "payment_id": pid, "message": "Счёт создан"}
                 return {"ok": False, "error": "Ошибка API CryptoBot"}
             except Exception as e:
                 return {"ok": False, "error": f"Ошибка CryptoBot: {e}"}
             
        # --- Heleket ---
        elif method_id == "pay_heleket":
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "Heleket", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
            if pending_err:
                return pending_err
            
            try:
                result = await create_heleket_payment_request(
                    amount=float(final_price), 
                    currency="RUB", 
                    description=f"Payment for {req.host_name}",
                    order_id=pid,
                    return_url=f"https://t.me/{get_setting('telegram_bot_username')}",
                    user_id=user_id,
                    email=user.get('email', 'no-email')
                )
                
                if result and result.get('payment_url'):
                    pay_url = result['payment_url']
                    kb = create_payment_keyboard(pay_url)
                    await _send_telegram_message(user_id, f"<b>Оплата через Crypto (Heleket)</b>\n\nСумма: <b>{final_price:.2f} RUB</b>", kb)
                    return {"ok": True, "payment_url": pay_url, "payment_id": pid}
                else:
                     return {"ok": False, "error": "Ошибка создания платежа Heleket"}

            except Exception as e:
                logger.error(f"Heleket error: {e}")
                return {"ok": False, "error": f"Ошибка Heleket: {e}"}
                
        # --- YooMoney ---
        elif method_id == "pay_yoomoney":
             wallet = (get_setting("yoomoney_wallet") or "").strip()
             secret = (get_setting("yoomoney_secret") or "").strip()
             if not wallet or not secret:
                 return {"ok": False, "error": "YooMoney не настроен"}
             if not (wallet.isdigit() and len(wallet) >= 11):
                 return {"ok": False, "error": "Некорректный номер кошелька YooMoney"}
             if Decimal(str(final_price)) < Decimal("1.00"):
                 return {"ok": False, "error": "Минимальная сумма YooMoney — 1 RUB"}
             pid = str(uuid.uuid4())
             meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "YooMoney", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
             pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
             if pending_err:
                 return pending_err
             desc = get_transaction_comment({"id": user_id, "username": user.get("username")}, action_name, months, req.host_name)
             link = _build_yoomoney_link(wallet, Decimal(str(final_price)), pid, desc)
             
             kb = create_yoomoney_payment_keyboard(link, pid)
             await _send_telegram_message(user_id, f"<b>Оплата через YooMoney</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счет также доступен в WebApp.</i>", kb)
             
             return {"ok": True, "payment_url": link, "payment_id": pid, "message": "Счёт создан"}

        # --- TON Connect ---
        elif method_id == "pay_tonconnect":
             return {"ok": False, "error": "TON Connect пока недоступен через WebApp"}

        # --- Stars ---
        elif method_id == "pay_stars":
             try:
                stars_ratio = float(get_setting("stars_per_rub") or 0)
             except: stars_ratio = 0
             if stars_ratio <= 0: return {"ok": False, "error": "Stars отключены"}
             stars_amount = max(1, int((final_price * stars_ratio)))
             pid = str(uuid.uuid4())
             meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": float(final_price),
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "Telegram Stars", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
             pending_err = _create_payload_pending_or_error(pid, user_id, float(final_price), meta)
             if pending_err:
                 return pending_err
             title = f"{'Подписка' if action_name == 'new' else 'Продление'} на {months} мес."
             desc = get_transaction_comment({"id": user_id, "username": user.get("username")}, action_name, months, req.host_name)
             await _send_invoice_stars(user_id, title, desc, pid, stars_amount)
             bot_username = get_setting('telegram_bot_username')
             return {"ok": True, "message": "Счёт Stars отправлен в бот", "payment_url": f"tg://resolve?domain={bot_username}"}

        # --- Balance ---
        elif method_id == "pay_balance":
            amount = float(final_price)
            if not deduct_from_balance(user_id, amount):
                return {"ok": False, "error": "Недостаточно средств"}
            pid = str(uuid.uuid4())
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": amount,
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "Balance", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            token = get_setting("telegram_bot_token")
            if not token:
                _rollback_internal_payment(
                    payment_id=pid,
                    user_id=user_id,
                    amount=amount,
                    payment_method="Balance",
                    plan_id=plan_id,
                    reason="telegram_bot_token missing after deduct",
                )
                return {"ok": False, "error": "Бот не настроен (нет токена)"}

            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                fulfilled = await process_successful_payment(bot, meta)
            except Exception as e:
                _rollback_internal_payment(
                    payment_id=pid,
                    user_id=user_id,
                    amount=amount,
                    payment_method="Balance",
                    plan_id=plan_id,
                    reason=e,
                )
                return {
                    "ok": False,
                    "error": "Не удалось создать ключ, средства возвращены на баланс",
                }
            finally:
                await bot.session.close()
            if not fulfilled:
                # process_successful_payment already refunded via refund_payment_once;
                # call again for safety — idempotent, no double credit.
                _rollback_internal_payment(
                    payment_id=pid,
                    user_id=user_id,
                    amount=amount,
                    payment_method="Balance",
                    plan_id=plan_id,
                    reason="process_successful_payment returned False",
                )
                return {
                    "ok": False,
                    "error": "Не удалось создать ключ, средства возвращены на баланс",
                }
            return {"ok": True, "message": "Оплачено с баланса!", "paid": True}

        # --- Referral balance (зеркало pay_referral_balance в боте) ---
        elif method_id == "pay_referral_balance":
            amount = float(final_price)
            if not deduct_from_referral_balance(user_id, amount):
                return {"ok": False, "error": "Недостаточно средств на реферальном балансе"}
            pid = f"referral_balance:{user_id}:{uuid.uuid4()}"
            meta = {
                "user_id": user_id, "months": months, "duration_days": duration_days, "price": amount,
                "action": action_name, "key_id": req.key_id, "host_name": req.host_name,
                "plan_id": plan_id, "payment_method": "ReferralBalance", "payment_id": pid,
                "tier_device_count": tier_device_count,
                "promo_code": applied_promo_code, "promo_discount": promo_discount_amount
            }
            token = get_setting("telegram_bot_token")
            if not token:
                _rollback_internal_payment(
                    payment_id=pid,
                    user_id=user_id,
                    amount=amount,
                    payment_method="ReferralBalance",
                    plan_id=plan_id,
                    reason="telegram_bot_token missing after deduct",
                )
                return {"ok": False, "error": "Бот не настроен (нет токена)"}

            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                fulfilled = await process_successful_payment(bot, meta)
            except Exception as e:
                _rollback_internal_payment(
                    payment_id=pid,
                    user_id=user_id,
                    amount=amount,
                    payment_method="ReferralBalance",
                    plan_id=plan_id,
                    reason=e,
                )
                return {
                    "ok": False,
                    "error": "Не удалось создать ключ, средства возвращены на реферальный баланс",
                }
            finally:
                await bot.session.close()
            if not fulfilled:
                _rollback_internal_payment(
                    payment_id=pid,
                    user_id=user_id,
                    amount=amount,
                    payment_method="ReferralBalance",
                    plan_id=plan_id,
                    reason="process_successful_payment returned False",
                )
                return {
                    "ok": False,
                    "error": "Не удалось создать ключ, средства возвращены на реферальный баланс",
                }
            return {"ok": True, "message": "Оплачено с реферального баланса!", "paid": True}

        return {"ok": False, "error": "Метод не поддерживается"}
    except Exception as e:
        logger.error(f"API Create Payment Error: {e}")
        return {"ok": False, "error": str(e), "details": traceback.format_exc()}


def _rollback_internal_payment(
    *,
    payment_id: str,
    user_id: int,
    amount: float,
    payment_method: str,
    plan_id: int | None = None,
    reason: object = None,
) -> bool:
    """Идемпотентный откат списания Balance/ReferralBalance + лог PAYMENT_ROLLBACK."""
    try:
        from shop_bot.data_manager.remnawave_repository import refund_payment_once

        did = bool(refund_payment_once(payment_id, int(user_id), float(amount), payment_method))
    except Exception as e:
        logger.error(
            "PAYMENT_ROLLBACK failed payment_id=%s user_id=%s amount=%s plan_id=%s err=%s original=%s",
            payment_id,
            user_id,
            amount,
            plan_id,
            e,
            reason,
            exc_info=True,
        )
        return False
    logger.error(
        "PAYMENT_ROLLBACK payment_id=%s user_id=%s amount=%.2f method=%s plan_id=%s applied=%s reason=%s",
        payment_id,
        user_id,
        float(amount),
        payment_method,
        plan_id,
        did,
        reason,
    )
    return did


def _platega_method_code_from_settings() -> int:
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


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_get_payment_methods",
    "api_create_payment",
    "_rollback_internal_payment",
    "_platega_method_code_from_settings",
]
