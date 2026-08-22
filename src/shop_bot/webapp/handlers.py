from typing import Any
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import aiohttp
from shop_bot.data_manager.remnawave_repository import get_setting, get_user_keys, get_msk_time, get_webapp_settings, get_user, get_referral_count, get_all_hosts, list_squads, get_plans_for_host
import os
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import html
import uuid
import asyncio
import time
import threading
from collections import deque
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, FSInputFile, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import traceback
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from shop_bot.bot.keyboards import (
    create_payment_keyboard, 
    create_yoomoney_payment_keyboard, 
    create_cryptobot_payment_keyboard
)
from shop_bot.data_manager.remnawave_repository import (
    create_payload_pending, get_plan_by_id,
    deduct_from_balance, check_transaction_exists, payment_owned_by_user, add_to_balance, log_transaction,
    add_to_referral_balance_all, add_to_referral_balance, deduct_from_referral_balance,
    get_referral_balance, get_balance, get_all_users, is_admin, update_user_stats,
    redeem_promo_code, update_promo_code_status, record_key_from_payload, get_key_by_id,
    update_key, get_key_by_email,
    list_referral_payout_methods, add_referral_payout_method, delete_referral_payout_method,
    get_referral_payout_method, get_pending_status,
)
import shop_bot.data_manager.remnawave_repository as rw_repo
from shop_bot.data_manager.database import get_seller_user, get_device_tiers, get_host, format_next_traffic_reset_display
from shop_bot.modules import remnawave_api
from shop_bot.config import get_purchase_success_text
import re
from decimal import Decimal, ROUND_HALF_UP
import logging
from urllib.parse import urlencode, quote
import hashlib
import hmac


logger = logging.getLogger(__name__)


def _create_payload_pending_or_error(payment_id, user_id, amount, meta):
    """Создать pending; если слот промокода уже занят — вернуть ошибку для API."""
    try:
        ok = create_payload_pending(payment_id, user_id, amount, meta)
    except rw_repo.PromoUnavailableError as e:
        return {"ok": False, "error": rw_repo.promo_error_message(e.reason)}
    if not ok:
        return {"ok": False, "error": "Не удалось создать платёж"}
    return None

# In-memory storage for temporary auth tokens: {token: user_id}
TEMP_AUTH_TOKENS = {}

# Max age for Telegram WebApp initData (seconds). Reject stale signed payloads.
TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60

# Rate-limit auth endpoints to reduce brute-force of tokens / initData replay.
limiter = Limiter(key_func=get_remote_address, default_limits=[])
AUTH_RATE_LIMIT = "30/minute"

# Дополнительно к IP: один и тот же email нельзя молотить с разных адресов
# (SlowAPI считает только get_remote_address). Лимит тот же 30/мин, чтобы
# не ужесточать UX; измерение идёт по нормализованному адресу, существующий
# и несуществующий email считаются одинаково (без enumeration через 429).
EMAIL_AUTH_PER_EMAIL_LIMIT = 30
EMAIL_AUTH_PER_EMAIL_WINDOW_SECONDS = 60.0
_EMAIL_AUTH_HITS: dict[str, deque[float]] = {}
_EMAIL_AUTH_HITS_LOCK = threading.Lock()


def _email_auth_rate_limit_response() -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "error": f"Rate limit exceeded: {EMAIL_AUTH_PER_EMAIL_LIMIT} per 1 minute",
        },
        status_code=429,
    )


def _email_auth_rate_limited(email: str) -> bool:
    """True, если по этому email уже исчерпан EMAIL_AUTH_PER_EMAIL_LIMIT за окно."""
    key = (email or "").strip().lower()
    if not key:
        return False
    now = time.time()
    window = float(EMAIL_AUTH_PER_EMAIL_WINDOW_SECONDS)
    limit = int(EMAIL_AUTH_PER_EMAIL_LIMIT)
    with _EMAIL_AUTH_HITS_LOCK:
        q = _EMAIL_AUTH_HITS.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def _reject_if_email_auth_rate_limited(email: str) -> JSONResponse | None:
    if _email_auth_rate_limited(email):
        return _email_auth_rate_limit_response()
    return None


def _resolve_user_from_request_token(data: dict, request: Request) -> dict | None:
    token = data.get("token") or request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token.split(" ", 1)[1]

    if not token:
        return None

    uid = TEMP_AUTH_TOKENS.get(token)
    if uid:
        return get_user(uid)
    try:
        u = rw_repo.get_user_by_auth_token(token)
        if u:
            return u
    except Exception:
        pass
    return None


def _resolve_authenticated_user(data: dict, request: Request) -> dict | None:
    """Определить текущего пользователя ИСКЛЮЧИТЕЛЬНО по доверенным источникам:
    существующей persistent auth-сессии (см. _resolve_user_from_request_token —
    тот же токен, что хранится в localStorage/cookie webapp) или по подписанным
    Telegram WebApp `init_data`.

    Специально НЕ принимает и не доверяет `user_id`, присланному клиентом в теле
    запроса — используется там, где подмена пользователя была бы небезопасна
    (например, POST /api/webapp/pending-actions/complete).
    """
    user = _resolve_user_from_request_token(data, request)
    if user:
        return user

    init_data = data.get("init_data")
    if init_data:
        bot_token = get_setting("telegram_bot_token")
        if bot_token:
            tg_user = validate_telegram_data(init_data, bot_token)
            if tg_user and tg_user.get("id"):
                return get_user(int(tg_user["id"]))
    return None


def _unauthorized(detail: str = "Unauthorized") -> JSONResponse:
    return JSONResponse({"ok": False, "error": detail}, status_code=401)


def _require_authenticated_user(
    request: Request,
    *,
    data: dict | None = None,
    token: str | None = None,
    init_data: str | None = None,
) -> dict | None:
    """Resolve caller from auth_token / Bearer / signed init_data only (CWE-862/639).

    Never trusts client-supplied user_id/telegram_id. Returns None if missing
    or banned — callers should respond with ``_unauthorized()``.
    """
    payload = dict(data or {})
    if token is not None:
        payload["token"] = token
    if init_data is not None:
        payload["init_data"] = init_data
    user = _resolve_authenticated_user(payload, request)
    if not user or user.get("is_banned"):
        return None
    return user


def _ref_setting_is_true(key: str, default: bool = False) -> bool:
    raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def _ref_method_type_enabled(method_type: str) -> bool:
    setting_key = {
        "sbp": "referral_withdraw_sbp_enabled",
        "card": "referral_withdraw_card_enabled",
        "usdt_trc20": "referral_withdraw_usdt_enabled",
    }.get((method_type or "").strip().lower())
    if not setting_key:
        return False
    return _ref_setting_is_true(setting_key)


# ===== Utility Functions =====
def get_transaction_comment(user_data: dict, action_type: str, value: any, host_name: str | None = None) -> str:
    """Короткое человекочитаемое описание платежа — для поля description в
    ЮKassa/ЮMoney и подписи Stars-инвойса.

    Раньше здесь была попытка импортировать одноимённую функцию из
    `shop_bot.bot.handlers`, которой там никогда не было — это ломало ЛЮБУЮ
    оплату из webapp (ЮKassa/ЮMoney/Stars) с `ImportError`, тихо проглоченным
    общим `except Exception` в /api/create-payment. Теперь строка собирается
    здесь же, без зависимости от модуля бота.
    """
    try:
        months = int(value or 0)
    except (TypeError, ValueError):
        months = 0

    action_label = "Продление подписки" if action_type == "extend" else "Оплата подписки"
    duration = f"на {months} мес." if months else ""

    user_id = (user_data or {}).get("id")
    username = (user_data or {}).get("username")
    who = f"@{username}" if username else (f"#{user_id}" if user_id else "")

    parts = [action_label, duration]
    if host_name:
        parts.append(f"({host_name})")
    if who:
        parts.append(f"— {who}")
    return " ".join(p for p in parts if p)

def calculate_webapp_price(price: float, user_id: int) -> float:
    try:
        user = get_user(user_id)
        if not user: return price
        
        # 1. Seller Discount
        if user.get('seller_active'):
            seller = get_seller_user(user_id)
            if seller and seller.get('seller_sale'):
                discount_percent = float(seller['seller_sale'])
                price -= price * (discount_percent / 100)
        
        # 2. Referral Discount (First purchase)
        if user.get('referred_by') and user.get('total_spent', 0) == 0:
            ref_discount = get_setting("referral_discount")
            if ref_discount:
                try:
                    d_val = float(ref_discount)
                    if d_val > 0:
                        price -= price * (d_val / 100)
                except: pass
                
    except Exception as e:
        logger.error(f"Error calculating price: {e}")
        
    return round(price, 2)

# ===== HELPER FUNCTIONS FOR PAYMENT PROCESS =====
async def notify_admin_of_purchase(bot: Bot, metadata: dict):
    from shop_bot.bot.handlers import notify_admin_of_purchase as bot_notify
    await bot_notify(bot, metadata)

async def process_successful_payment(bot: Bot, metadata: dict):
    from shop_bot.bot.handlers import process_successful_payment as bot_process
    return await bot_process(bot, metadata)

async def _send_telegram_message(user_id: int, text: str, reply_markup=None, photo=None):
    token = get_setting("telegram_bot_token")
    if not token: return False
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        if photo:
            await bot.send_photo(chat_id=user_id, photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")
        return False
    finally:
        await bot.session.close()

async def _send_invoice_stars(user_id: int, title: str, description: str, payload: str, amount: int):
    token = get_setting("telegram_bot_token")
    if not token: return False
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=amount)]
        )
        return True
    except Exception as e:
        logger.error(f"Error sending Stars invoice: {e}")
        return False
    finally:
        await bot.session.close()


from shop_bot.modules.platega_api import PlategaAPI
from shop_bot.modules.heleket_api import create_heleket_payment_request
from shop_bot.bot.keyboards import (
    create_payment_keyboard, create_cryptobot_payment_keyboard,
    create_yoomoney_payment_keyboard
)
from shop_bot.bot.handlers import create_cryptobot_api_invoice, process_successful_payment
from yookassa import Configuration as YookassaConfiguration, Payment as YookassaPayment
from aiogram.types import BufferedInputFile
import io
import qrcode
from urllib.parse import urlencode

def _build_yoomoney_link(receiver: str, amount_rub: Decimal, label: str, description: str) -> str:
    base = "https://yoomoney.ru/quickpay/confirm.xml"
    params = {
        "receiver": (receiver or "").strip(),
        "quickpay-form": "donate",
        "targets": description[:50],
        "formcomment": description,
        "short-dest": description,
        "sum": f"{amount_rub:.2f}",
        "label": label,
        "successURL": f"https://t.me/{get_setting('telegram_bot_username')}",
    }
    return base + "?" + urlencode(params)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.middleware("http")
async def _webapp_no_cache_middleware(request, call_next):
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if request.url.path == "/" or content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

ico_dir = os.path.join(os.path.dirname(__file__), "module", "ico")
if os.path.exists(ico_dir):
    app.mount("/module/ico", StaticFiles(directory=ico_dir), name="ico")

uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


# Endpoint: list referral payout methods for current user
@app.post("/api/referral/payout-methods/list")
async def api_referral_payout_methods_list(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    try:
        methods = rw_repo.list_referral_payout_methods(user.get("telegram_id"))
        for method in methods:
            method["type_enabled"] = _ref_method_type_enabled(method.get("method_type"))
    except Exception as e:
        logger.error(f"Failed to list referral payout methods: {e}")
        methods = []
    try:
        min_withdraw = float(get_setting("minimum_withdrawal") or 100)
    except Exception:
        min_withdraw = 100.0
    withdraw_enabled = _ref_setting_is_true("referral_withdraw_enabled")
    return {"ok": True, "methods": methods, "min_withdraw": min_withdraw, "withdraw_enabled": withdraw_enabled}


# Endpoint: add a new referral payout method for current user
@app.post("/api/referral/payout-methods/add")
async def api_referral_payout_methods_add(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    method_type = (data.get("method_type") or "").strip()
    requisite_value = (data.get("requisite_value") or "").strip()
    bank_name = (data.get("bank_name") or None)
    if not method_type or not requisite_value:
        return {"ok": False, "error": "Заполните все поля"}

    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": False, "error": "Вывод средств временно недоступен."}

    if not _ref_method_type_enabled(method_type):
        return {"ok": False, "error": "Этот способ временно недоступен"}

    ok, msg, new_id = rw_repo.add_referral_payout_method(
        user.get("telegram_id"), method_type, requisite_value, bank_name
    )
    return {"ok": ok, "message": msg, "method_id": new_id}


@app.post("/api/referral/available-method-types")
async def api_referral_available_method_types(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": True, "methods": [], "sbp_banks": []}

    method_configs = [
        {"type": "sbp",       "label": "СБП",         "icon": "phone_android",    "placeholder": "+7 900 000 00 00",     "setting": "referral_withdraw_sbp_enabled"},
        {"type": "card",      "label": "Номер карты",  "icon": "credit_card",      "placeholder": "Номер карты (16 цифр)", "setting": "referral_withdraw_card_enabled"},
        {"type": "usdt_trc20","label": "USDT TRC20",   "icon": "currency_bitcoin", "placeholder": "TRC20 адрес кошелька", "setting": "referral_withdraw_usdt_enabled"},
    ]
    raw_banks = get_setting("referral_withdraw_sbp_banks") or ""
    sbp_banks = [b.strip() for b in raw_banks.split(",") if b.strip()]
    enabled = []
    for m in method_configs:
        if not _ref_setting_is_true(m["setting"]):
            continue
        if m["type"] == "sbp" and not sbp_banks:
            continue
        enabled.append({"type": m["type"], "label": m["label"], "icon": m["icon"], "placeholder": m["placeholder"]})
    return {"ok": True, "methods": enabled, "sbp_banks": sbp_banks}


@app.post("/api/referral/payout-methods/delete")
async def api_referral_payout_methods_delete(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": False, "error": "Вывод средств временно недоступен."}

    method_id = data.get("method_id")
    if not method_id:
        return {"ok": False, "error": "Missing method_id"}
    method = rw_repo.get_referral_payout_method(int(method_id), user.get("telegram_id"))
    if not method:
        return {"ok": False, "error": "Method not found"}
    ok, msg = rw_repo.delete_referral_payout_method(int(method_id), user.get("telegram_id"))
    return {"ok": bool(ok), "message": msg, "error": None if ok else msg}


@app.post("/api/key/auto-renew")
async def api_key_auto_renew(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    key_id = data.get("key_id")
    enabled = data.get("enabled")
    if key_id is None or enabled is None:
        return {"ok": False, "error": "Missing key_id or enabled"}

    key = get_key_by_id(int(key_id))
    if not key or key.get("user_id") != user.get("telegram_id"):
        return {"ok": False, "error": "Key not found"}

    rw_repo.set_key_auto_renew(int(key_id), bool(enabled))
    return {"ok": True, "auto_renew": bool(enabled)}


# Endpoint: referral withdraw request from webapp
@app.post("/api/referral/request-withdrawal")
async def api_referral_request_withdraw(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": False, "error": "Вывод средств временно недоступен.", "message": "Вывод средств временно недоступен."}

    try:
        amount = float(data.get("amount") or 0)
    except Exception:
        return {"ok": False, "error": "Invalid amount"}

    if amount <= 0:
        return {"ok": False, "error": "Invalid amount"}

    method_id = int(data.get("method_id") or 0)
    ok, msg, new_id = rw_repo.create_referral_withdrawal_request(user.get("telegram_id"), amount, method_id)
    if ok and new_id:
        try:
            method = rw_repo.get_referral_payout_method(method_id, user.get("telegram_id"))
            admin_text = rw_repo.format_referral_withdrawal_admin_notice(
                request_id=new_id,
                user_id=user.get("telegram_id"),
                username=user.get("username"),
                amount=amount,
                method_type=(method or {}).get("method_type"),
                bank_name=(method or {}).get("bank_name"),
                requisite_value=(method or {}).get("requisite_value"),
            )
            for admin_id in (rw_repo.get_admin_ids() or set()):
                await _send_telegram_message(int(admin_id), admin_text)
        except Exception:
            logger.warning("Не удалось уведомить администраторов о заявке на вывод", exc_info=True)
    return {
        "ok": ok,
        "message": msg,
        "request_id": new_id,
        "has_open_request": bool(ok) or rw_repo.has_open_referral_withdrawal_request(user.get("telegram_id")),
    }


# Endpoint: list referral withdrawal request history for the current user
@app.post("/api/referral/withdrawals")
async def api_referral_list_withdrawals(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}

    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    try:
        requests_list = rw_repo.list_referral_withdrawal_requests(user_id=user.get("telegram_id"))
    except Exception as e:
        logger.error(f"Failed to list referral withdrawals for {user.get('telegram_id')}: {e}")
        return {"ok": False, "error": "Server error"}

    withdrawals = [
        {
            "id": r.get("id"),
            "amount": r.get("amount"),
            "status": r.get("status"),
            "method_type": r.get("method_type"),
            "bank_name": r.get("bank_name"),
            "requisite_value": r.get("requisite_value"),
            "reject_reason": r.get("reject_reason"),
            "created_at": r.get("created_at"),
            "processed_at": r.get("processed_at"),
        }
        for r in requests_list
    ]
    has_open_request = any((r.get("status") or "") in ("new", "processing") for r in requests_list)
    return {"ok": True, "withdrawals": withdrawals, "has_open_request": has_open_request}


def _format_remaining_details(remaining: timedelta) -> str:
    total_seconds = int(remaining.total_seconds())
    if total_seconds <= 0:
        return "0мин"

    minutes = (total_seconds // 60) % 60
    hours = (total_seconds // 3600) % 24
    days = remaining.days % 365
    years = remaining.days // 365

    parts = []
    if years > 0:
        parts.append(f"{years}г.")
    if days > 0:
        parts.append(f"{days}д.")
    if hours > 0:
        parts.append(f"{hours}ч.")
    if minutes > 0:
        parts.append(f"{minutes}мин")

    # Берем только первые две значимые части для краткости
    result_parts = parts[:2]
    return " ".join(result_parts) if result_parts else "меньше минуты"

def _format_bytes(size: Any) -> str:
    if size is None: return "0 B"
    if isinstance(size, str):
        if any(x in size for x in ['B', 'KB', 'MB', 'GB', 'TB', 'iB']):
            return size
        try: size = float(size)
        except: return "0 B"
    
    if size <= 0: return "0 B"
    power = 1024
    n = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def _process_template_placeholders(html: str, user_id: int, webapp_settings: dict, context_data: dict) -> str:
    title = webapp_settings.get("webapp_title") or get_setting("panel_brand_title") or "Xatab VPN"
    support_username = get_setting("support_contact_username") or get_setting("support_bot_username") or ""
    bot_username = get_setting("telegram_bot_username") or ""
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")

    replacements = {
        "{{ panel_brand_title }}": title,
        "{{ user_profile_card }}": context_data.get("profile_card", ""),
        "{{ key_info_section }}": context_data.get("key_section", ""),
        "{{ profile_keys_list }}": context_data.get("profile_keys_list", ""),
        "{{ setup_keys_list }}": context_data.get("setup_keys_list", ""),
        "{{ renew_keys_dropdown_options }}": context_data.get("renew_keys_options", ""),
        "{{ renew_plans_grid }}": context_data.get("renew_plans_html_data", ""),
        "{{ support_bot_username }}": support_username,
        "{{ min_price }}": context_data.get("min_price", "0 ₽"),
        "{{ webapp_logo }}": context_data.get("webapp_logo", ""),
        "{{ webapp_icon }}": context_data.get("webapp_icon", ""),
        "{{ logo_hidden }}": "hidden" if not context_data.get("webapp_logo") else "",
        "{{ user_id }}": str(user_id),
        "{{ bot_username }}": bot_username,
        "{{ webapp_domain }}": webapp_domain,
        "{{ tg_fullscreen_css }}": """
    <style>
        .tg-miniapp #main-page,
        .tg-miniapp #purchase-page,
        .tg-miniapp #renew-page,
        .tg-miniapp #setup-page,
        .tg-miniapp #profile-page,
        .tg-miniapp #support-page {
            padding-top: max(env(safe-area-inset-top), 70px) !important;
        }
    </style>
        """ if webapp_settings.get("tg_fullscreen") else "",
    }
    
    # Selected key display variants
    display_val = context_data.get("renew_selected_display", "Нет активных ключей")
    replacements["{{ renew_selected_key_display }}"] = display_val
    replacements["{{\n                                renew_selected_key_display }}"] = display_val

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    
    server_options, server_plans = _get_servers_and_plans_html(user_id)
    html = html.replace("{{ server_dropdown_options }}", server_options)
    html = html.replace("{{ server_plans_grid }}", server_plans)
    
    return html

def _process_key_data(key: dict) -> dict:
    # 1. Calculate expiry
    try:
        expire_dt = datetime.strptime(key['expiry_date'], "%Y-%m-%d %H:%M:%S")
        created_dt = datetime.strptime(key.get('created_at', key['expiry_date']), "%Y-%m-%d %H:%M:%S")
        expire_date_str = expire_dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        expire_dt = datetime.now()
        created_dt = datetime.now()
        expire_date_str = "Unknown"
    
    now = get_msk_time().replace(tzinfo=None)
    
    # 2. Days left & Detailed remaining
    delta = expire_dt - now
    days_left = delta.days
    if days_left < 0:
        days_left = 0
        
    remaining_str = _format_remaining_details(delta) if delta.total_seconds() > 0 else "Истёк"

    # 3. Progress
    total_duration = (expire_dt - created_dt).total_seconds()
    elapsed_delta = now - created_dt
    elapsed = elapsed_delta.total_seconds()
    elapsed_str = _format_remaining_details(elapsed_delta) if elapsed > 0 else "0мин"
    
    if total_duration > 0:
        percent = (elapsed / total_duration) * 100
    else:
        percent = 100
        
    percent = max(0, min(100, percent))
    percent_str = f"{percent:.1f}%"
    
    # 4. Display Name (prefer user-set name, fall back to email/uuid)
    key_name = key.get('user_key_name') or key.get('name')
    if not key_name:
        # User requested: Key #email_username (sannilo@bot.local -> Ключ #sannilo)
        email = key.get('email') or key.get('key_email') or ""
        if email.endswith("@bot.local"):
            email = email[:-10]
        
        if email:
            key_name = f"Ключ #{email}"
        elif key.get('short_uuid'):
            key_name = f"Ключ #{key.get('short_uuid')}"
        else:
            key_name = f"Ключ #{key.get('key_id')}"
        
    # 5. Subscription URL
    sub_url = key.get('subscription_url') or key.get('key') or ""

    # 6. Limits
    traffic_limit = key.get('limit_bytes')
    traffic_used = key.get('used_bytes', 0)
    
    formatted_used = _format_bytes(traffic_used)
    
    traffic_str = "∞"
    if traffic_limit:
        try:
            t_lim_float = float(traffic_limit)
            if t_lim_float > 0:
                traffic_str = _format_bytes(t_lim_float)
            else:
                traffic_str = "∞"
        except (ValueError, TypeError):
            traffic_str = "∞"
    
    hwid_limit = key.get('limit_ips')
    hwid_usage = key.get('used_ips', 0)
    
    limit_display = "∞"
    if hwid_limit is not None:
        try:
            limit_val = int(hwid_limit)
            if limit_val > 0 and limit_val < 99:
                 limit_display = str(limit_val)
            else:
                 limit_display = "∞"
        except (ValueError, TypeError):
            limit_display = "∞"

    hwid_str = f"{hwid_usage} / {limit_display}"
    
    # Safety: Created Date String
    created_date_str = created_dt.strftime("%d.%m.%Y")

    if days_left > 5:
        status_text = "Активен"
        status_color = "text-emerald-500"
        status_bg = "bg-emerald-500/10"
    elif days_left > 0:
        status_text = "Скоро"
        status_color = "text-yellow-500"
        status_bg = "bg-yellow-500/10"
    else:
        status_text = "Истёк"
        status_color = "text-red-500"
        status_bg = "bg-red-500/10"

    return {
        "key_id": key.get('key_id'),
        "name": key_name,
        "expire_date_str": expire_date_str,
        "days_left": days_left,
        "percent_str": percent_str,
        "sub_url": sub_url,
        "expiry_dt": expire_dt,
        "remaining_str": remaining_str,
        "created_date_str": created_date_str,
        "elapsed_str": elapsed_str,
        "traffic_info": f"{formatted_used} / {traffic_str}" + (
            f" (сброс {reset_txt})" if (reset_txt := format_next_traffic_reset_display(key.get("next_traffic_reset_at"))) else ""
        ), 
        "hwid_info": f"{hwid_str} уст.",
        "status_text": status_text,
        "status_color": status_color,
        "status_bg": status_bg,
        "comment_key": key.get('comment_key') or "",
        "host_name": key.get('host_name') or "",
        "user_key_name": key.get('user_key_name') or "",
        "auto_renew": bool(int(key.get('auto_renew') or 0)),
    }

def _get_key_html(key: dict) -> str:
    data = _process_key_data(key)
    
    html = f"""
        <section
            class="bg-white dark:bg-surface-dark border border-gray-200 dark:border-surface-highlight-dark rounded-2xl p-5 shadow-sm relative overflow-hidden group">
            <div class="absolute -top-10 -right-10 w-32 h-32 bg-primary/20 rounded-full blur-3xl dark:block hidden">
            </div>
            <div class="flex flex-col gap-1 mb-4">
                <!-- Row 1: Status & Date -->
                <div class="flex justify-between items-center h-6">
                    <div class="flex items-center gap-2">
                        <span class="relative flex h-3 w-3">
                            <span
                                class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                        </span>
                        <span class="font-bold text-lg text-gray-900 dark:text-white leading-none">Активна</span>
                    </div>
                    <div class="font-semibold text-sm leading-none text-right">{data['expire_date_str']}</div>
                </div>

                <!-- Row 2: Key Name & Days Left Badge -->
                <div class="flex justify-between items-center h-6">
                    <div class="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 text-sm">
                        <span class="material-symbols-rounded text-base">key</span>
                        <span>{data['name']}</span>
                    </div>
                    <div
                        class="bg-surface-highlight-dark/10 dark:bg-surface-highlight-dark px-2 py-0.5 rounded text-[10px] font-medium text-gray-600 dark:text-gray-300">
                        {data['days_left']} дн.
                    </div>
                </div>
            </div>
            <div class="mt-6">
                <div class="flex justify-between text-xs mb-2">
                    <span class="text-gray-500 dark:text-gray-400">Использовано</span>
                    <span class="font-bold text-primary">{data['percent_str']}</span>
                </div>
                <div class="w-full bg-gray-100 dark:bg-black rounded-full h-2 overflow-hidden">
                    <div class="bg-primary h-2 rounded-full progress-bar shadow-[0_0_10px_rgba(16,185,129,0.5)]" style="width: {data['percent_str']}"></div>
                </div>
            </div>
        </section>
    """
    return html

def _get_profile_card_html(user: dict | None, referral_count: int, keys_count: int, referral_earned: float = 0.0) -> str:
    if not user:
        return ""
        
    user_id = user.get("telegram_id")
    balance = user.get("balance") or 0.0
    reg_date = user.get("registration_date")
    
    # Format currency: 1 240,50 ₽
    balance_str = f"{balance:,.2f}".replace(",", " ").replace(".", ",") + " ₽"
    earned_str = f"{referral_earned:,.2f}".replace(",", " ").replace(".", ",") + " ₽"
    
    # Format date and calculate time since
    reg_date_str = "Unknown"
    time_since_str = ""
    if reg_date:
        try:
             if isinstance(reg_date, str):
                 try:
                    dt = datetime.strptime(reg_date, "%Y-%m-%d %H:%M:%S")
                 except ValueError:
                    dt = datetime.fromisoformat(reg_date)
             else:
                 dt = reg_date
                 
             reg_date_str = dt.strftime("%d.%m.%Y")
             
             # Calculate relative time
             now = get_msk_time().replace(tzinfo=None)
             diff = now - dt.replace(tzinfo=None)
             days = max(0, diff.days)
             
             if days < 31:
                 time_since_str = f"{days} д."
             elif days < 365:
                 m = days // 30
                 d = days % 30
                 time_since_str = f"{m}м. {d}д." if d > 0 else f"{m}м."
             else:
                 y = days // 365
                 rem = days % 365
                 m = rem // 30
                 d = rem % 30
                 bits = [f"{y}г."]
                 if m > 0: bits.append(f"{m}м.")
                 if d > 0: bits.append(f"{d}д.")
                 time_since_str = " ".join(bits)
        except:
             pass

    sync_btn_html = ""
    if isinstance(user_id, int) and str(user_id).startswith("999"):
         bot_username = get_setting("telegram_bot_username") or "bot"
         sync_btn_html = f'''
                    <button onclick="syncTelegram('{bot_username}')" class="mt-2 w-full bg-[#0088cc]/20 hover:bg-[#0088cc]/30 text-[#00aaff] border border-[#0088cc]/30 font-bold py-3 rounded-xl text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-sm">
                        <span class="material-symbols-rounded text-base">sync</span>
                        <span>Синхронизировать с Telegram</span>
                    </button>
         '''

    # also show available referral balance separately if present
    available_ref = user.get("referral_balance") or 0.0
    available_str = f"{available_ref:,.2f}".replace(",", " ").replace(".", ",") + " ₽"

    return f"""
            <!-- Modern Balanced User Card -->
            <div class="glass-card border border-white/10 rounded-[2rem] p-6 relative overflow-hidden shadow-xl">
                <!-- Decoration -->
                <div class="absolute -top-10 -right-10 w-32 h-32 bg-primary/5 rounded-full blur-3xl"></div>

                <div class="flex flex-col gap-5 relative z-10">
                    <!-- Top: ID and Status -->
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div
                                class="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center border border-primary/20">
                                <span class="material-symbols-rounded text-primary">person</span>
                            </div>
                            <div>
                                <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest">ID
                                    пользователя</div>
                                <div class="text-base font-black text-white tracking-tight">#{user_id}</div>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest">Баланс</div>
                            <div class="text-lg font-black text-primary tracking-tighter">{balance_str}</div>
                        </div>
                    </div>

                    <!-- Middle: Main Stats -->
                    <div class="grid grid-cols-3 gap-2">
                        <div
                            class="bg-white/5 border border-white/5 rounded-2xl p-2.5 flex flex-col items-center justify-center text-center transition-all hover:bg-white/[0.08]">
                            <span class="material-symbols-rounded text-emerald-400 text-sm mb-1 opacity-80">group</span>
                            <div class="text-[9px] text-gray-400 uppercase font-black tracking-tight leading-none mb-1">Рефералы</div>
                            <div class="text-[11px] font-black text-white">{referral_count} чел.</div>
                        </div>
                        <div
                            class="bg-white/5 border border-white/5 rounded-2xl p-2.5 flex flex-col items-center justify-center text-center transition-all hover:bg-white/[0.08]">
                            <span class="material-symbols-rounded text-yellow-400 text-sm mb-1 opacity-80">payments</span>
                            <div class="text-[9px] text-gray-400 uppercase font-black tracking-tight leading-none mb-1">Всего заработано</div>
                            <div class="text-[11px] font-black text-white truncate w-full px-1">{earned_str}</div>
                        </div>
                        <div
                            class="bg-white/5 border border-white/5 rounded-2xl p-2.5 flex flex-col items-center justify-center text-center transition-all hover:bg-white/[0.08]">
                            <span class="material-symbols-rounded text-primary text-sm mb-1 opacity-80">key</span>
                            <div class="text-[9px] text-gray-400 uppercase font-black tracking-tight leading-none mb-1">Ключи</div>
                            <div class="text-[11px] font-black text-white">{keys_count} шт.</div>
                        </div>
                    </div>

                    <!-- Referral available -->
                    <div class="mt-3 text-center">
                        <div class="text-[10px] text-gray-400 uppercase font-black tracking-tight">Доступно к выводу</div>
                        <div class="text-sm font-black text-white">{available_str}</div>
                    </div>

                    <!-- Bottom: Meta Info -->
                    <div class="flex items-center justify-center gap-2 pt-1">
                        <span class="material-symbols-rounded text-[12px] text-gray-600">calendar_today</span>
                        <span class="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Дата
                            регистрации:</span>
                        <span class="text-[10px] text-gray-300 font-black">{reg_date_str} ({time_since_str})</span>
                    </div>

                    {sync_btn_html}
                </div>
            </div>
    """

def _get_key_card_html(key: dict, badge_html: str = "", extra_content_html: str = "") -> str:
    """Render the full key-card block (used for regular keys and, with an extra
    badge/CTA, for not-yet-activated gift keys so both share the same UI)."""
    data = _process_key_data(key)

    return f"""
        <div class="glass-card border border-white/10 rounded-2xl relative overflow-hidden shadow-lg transition-all hover:border-primary/30 group mb-3">
            <div class="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 pointer-events-none"></div>

            <button class="key-toggle w-full p-3 flex items-center justify-between relative z-10 transition-colors hover:bg-white/5">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 bg-white/5 rounded-xl flex items-center justify-center group-hover:bg-primary/10 transition-colors shrink-0">
                        <span class="material-symbols-rounded text-gray-400 group-hover:text-primary transition-colors text-lg">key</span>
                    </div>
                    
                    <div class="text-left overflow-hidden">
                        <div class="text-xs font-bold text-white group-hover:text-primary transition-colors truncate">{data['name']}</div>
                        <div class="text-[9px] text-gray-500 font-medium uppercase tracking-wider truncate">
                           До {data['expire_date_str']} ({data['remaining_str']})
                        </div>
                    </div>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                     {badge_html}
                     <span class="text-[9px] {data['status_bg']} {data['status_color']} px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">{data['status_text']}</span>
                     <div class="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <span class="material-symbols-rounded text-gray-500 text-sm group-hover:text-white transition-colors rotate-icon">expand_more</span>
                     </div>
                </div>
            </button>

            <div class="key-content px-3 relative z-10 transition-all duration-300"> 
                 <div class="pb-3 pt-2 flex flex-col gap-2 border-t border-white/5">
                 
                     <!-- KEY INFO BLOCK -->
                     <div class="flex flex-col gap-1 px-1 py-1 text-[10px]">
                        <!-- Row 1: Time -->
                        <div class="flex flex-wrap justify-between items-center gap-x-2 gap-y-1 border-b border-white/5 pb-1.5 mb-1.5 opacity-90">
                            <div class="flex items-center gap-1">
                                <span class="text-gray-500 font-medium shrink-0">⏳ Осталось:</span>
                                <span class="text-gray-200 font-mono tracking-tight whitespace-nowrap">{data['remaining_str']}</span>
                            </div>
                            <div class="w-px h-3 bg-white/10"></div>
                            <div class="flex items-center gap-1">
                                <span class="text-gray-500 font-medium shrink-0">➕ Куплен:</span>
                                <span class="text-gray-200 font-mono tracking-tight whitespace-nowrap">{data['elapsed_str']}</span>
                            </div>
                        </div>
                        
                        <!-- Row 2: Limits -->
                        <div class="flex justify-between items-center opacity-90">
                            <div class="flex items-center gap-1.5">
                                <span class="text-gray-500 whitespace-nowrap">🛰 Лимит:</span>
                                <span class="text-gray-300 font-mono whitespace-nowrap">{data['traffic_info']}</span>
                            </div>
                            <div class="w-px h-3 bg-white/10 mx-1"></div>
                            <div class="flex items-center gap-1.5">
                                <span class="text-gray-500 whitespace-nowrap">📱 Лимит:</span>
                                <span class="text-gray-300 font-mono whitespace-nowrap">{data['hwid_info']}</span>
                            </div>
                        </div>
                     </div>
                 
                     <!-- COMMENTS BLOCK -->
                     <div id="comment-block-{data['key_id']}" class="{'hidden' if not data.get('comment_key') else 'flex'} items-start gap-2 bg-amber-500/8 border border-amber-500/20 rounded-xl px-3 py-2 mb-1 mt-1">
                         <span class="material-symbols-rounded text-amber-400/70 text-sm mt-0.5 shrink-0">sticky_note_2</span>
                         <span id="comment-text-{data['key_id']}" class="text-[10px] text-amber-200/80 leading-relaxed break-words">{data.get('comment_key', '')}</span>
                     </div>

                     <div class="flex items-center gap-2 bg-black/20 rounded-xl p-2 border border-white/5 group/copy hover:border-primary/30 transition-colors">
                         <div class="flex-1 min-w-0">
                             <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mb-0.5">Ссылка</div>
                             <div class="text-[10px] text-gray-300 font-mono truncate transition-colors group-hover/copy:text-white">{data['sub_url']}</div>
                         </div>
                         <button onclick="copyKey(this, '{data['sub_url']}')" 
                            class="w-7 h-7 rounded-lg bg-white/5 text-white flex items-center justify-center hover:bg-white/10 transition-all active:scale-95 shrink-0 shadow-sm">
                             <span class="material-symbols-rounded text-sm">content_copy</span>
                         </button>
                     </div>

                     <button onclick="openLinkSafe('{data['sub_url']}')"
                        class="w-full bg-white text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider shadow-[0_4px_15px_rgba(255,255,255,0.1)] hover:shadow-[0_6px_20px_rgba(255,255,255,0.2)] active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                         <span class="material-symbols-rounded text-sm">bolt</span>
                         <span>Подключить</span>
                     </button>
                     
                     <div class="grid grid-cols-3 gap-2 mt-1">
                         <button onclick="openActionModal('devices', {data['key_id']}, '{data.get('host_name', '')}')"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">devices</span>
                             <span>Устройства</span>
                         </button>
                         <button onclick="openActionModal('rename', {data['key_id']}, '{data['user_key_name']}')"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit</span>
                             <span>Название</span>
                         </button>
                         <button onclick="openActionModal('comment', {data['key_id']}, '{data.get('comment_key', '')}')"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit_note</span>
                             <span>Заметка</span>
                         </button>
                     </div>
                     <div class="grid grid-cols-2 gap-2 mt-1">
                         <button onclick="goToRenewKey({data['key_id']})"
                             class="w-full bg-primary/10 border border-primary/20 text-primary py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-primary/20 active:scale-[0.98] transition-all flex items-center justify-center gap-1">
                             <span class="material-symbols-rounded text-sm">autorenew</span>
                             <span>Продлить</span>
                         </button>
                         <button id="auto-renew-btn-{data['key_id']}" onclick="toggleKeyAutoRenew({data['key_id']}, {'true' if data['auto_renew'] else 'false'}, this)"
                             class="w-full py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider active:scale-[0.98] transition-all flex items-center justify-center gap-1 border {'border-primary/30 text-primary bg-primary/10' if data['auto_renew'] else 'border-white/5 text-white bg-white/5 hover:bg-white/10'}">
                             <span class="material-symbols-rounded text-sm">{'update' if data['auto_renew'] else 'pause_circle'}</span>
                             <span class="auto-renew-label">{'Авто: ВКЛ' if data['auto_renew'] else 'Авто: ВЫКЛ'}</span>
                         </button>
                     </div>
                     {extra_content_html}
                </div>
            </div>
        </div>
        """

def _get_profile_keys_html(keys: list) -> str:
    if not keys:
        return _get_no_key_html()

    html = ""
    for key in keys:
        html += _get_key_card_html(key)
    return html

def _get_setup_keys_html(keys: list) -> str:
    if not keys:
        return _get_no_key_html()
        
    html = ""
    for key in keys:
        data = _process_key_data(key)
        
        if data['days_left'] <= 0:
            continue
            
        html += f"""
        <div class="glass-card border border-white/10 rounded-2xl relative overflow-hidden shadow-lg transition-all hover:border-primary/30 group mb-3">
            <div class="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 pointer-events-none"></div>

            <button class="key-toggle w-full p-3 flex items-center justify-between relative z-10 transition-colors hover:bg-white/5">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 bg-white/5 rounded-xl flex items-center justify-center group-hover:bg-primary/10 transition-colors shrink-0">
                        <span class="material-symbols-rounded text-gray-400 group-hover:text-primary transition-colors text-lg">key</span>
                    </div>
                    
                    <div class="text-left overflow-hidden">
                        <div class="text-xs font-bold text-white group-hover:text-primary transition-colors truncate">{data['name']}</div>
                        <div class="text-[9px] text-gray-500 font-medium uppercase tracking-wider truncate">
                           До {data['expire_date_str']} ({data['remaining_str']})
                        </div>
                    </div>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                     <span class="text-[9px] {data['status_bg']} {data['status_color']} px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">{data['status_text']}</span>
                     <div class="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <span class="material-symbols-rounded text-gray-500 text-sm group-hover:text-white transition-colors rotate-icon">expand_more</span>
                     </div>
                </div>
            </button>

            <div class="key-content px-3 relative z-10 transition-all duration-300"> 
                 <div class="pb-3 pt-2 flex flex-col gap-2 border-t border-white/5">
                 
                     <!-- COMMENTS BLOCK -->
                     <div id="comment-block-{data['key_id']}" class="{'hidden' if not data.get('comment_key') else 'flex'} items-start gap-2 bg-amber-500/8 border border-amber-500/20 rounded-xl px-3 py-2 mb-1 mt-1">
                         <span class="material-symbols-rounded text-amber-400/70 text-sm mt-0.5 shrink-0">sticky_note_2</span>
                         <span id="comment-text-{data['key_id']}" class="text-[10px] text-amber-200/80 leading-relaxed break-words">{data.get('comment_key', '')}</span>
                     </div>

                     <div class="flex items-center gap-2 bg-black/20 rounded-xl p-2 border border-white/5 group/copy hover:border-primary/30 transition-colors">
                         <div class="flex-1 min-w-0">
                             <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mb-0.5">Ссылка</div>
                             <div class="text-[10px] text-gray-300 font-mono truncate transition-colors group-hover/copy:text-white">{data['sub_url']}</div>
                         </div>
                         <button onclick="copyKey(this, '{data['sub_url']}')" 
                            class="w-7 h-7 rounded-lg bg-white/5 text-white flex items-center justify-center hover:bg-white/10 transition-all active:scale-95 shrink-0 shadow-sm">
                             <span class="material-symbols-rounded text-sm">content_copy</span>
                         </button>
                     </div>

                     <button onclick="openLinkSafe('{data['sub_url']}')"
                        class="w-full bg-white text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider shadow-[0_4px_15px_rgba(255,255,255,0.1)] hover:shadow-[0_6px_20px_rgba(255,255,255,0.2)] active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                         <span class="material-symbols-rounded text-sm">bolt</span>
                         <span>Открыть инструкцию</span>
                     </button>
                     
                     <div class="grid grid-cols-3 gap-2 mt-1">
                         <button onclick="openActionModal('devices', {data['key_id']}, '{data.get('host_name', '')}')"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">devices</span>
                             <span>Устройства</span>
                         </button>
                         <button onclick="openActionModal('rename', {data['key_id']}, '{data['user_key_name']}')"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit</span>
                             <span>Название</span>
                         </button>
                         <button onclick="openActionModal('comment', {data['key_id']}, '{data.get('comment_key', '')}')"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit_note</span>
                             <span>Заметка</span>
                         </button>
                     </div>
                </div>
            </div>
        </div>
        """
    return html

def _get_renew_keys_html(keys: list, user_id: int | None = None) -> tuple[str, str, str]:
    if not keys:
        return "", "Нет активных ключей", _get_no_key_html()
        
    options_html = '<div class="p-1 flex flex-col gap-0.5">'
    selected_text = ""
    renew_plans_html = ""
    
    for index, key in enumerate(keys):
        data = _process_key_data(key)
        host_name = key.get('host_name', '')
        
        is_selected = (index == 0)
        check_class = "text-primary" if is_selected else "text-transparent"
        text_color = "text-white" if is_selected else "text-gray-300"
        icon_color = "text-primary" if is_selected else "text-gray-500"
        
        if is_selected:
            selected_text = f"{data['name']} • До {data['expire_date_str']}"

        options_html += f"""
        <button
            class="dropdown-option w-full p-2.5 flex items-center justify-between rounded-lg hover:bg-white/5 transition-colors"
            data-key="#{data['key_id']}" data-name="{data['name']}" data-date="{data['expire_date_str']}" data-host="{host_name}" data-index="{index}">
            <div class="flex items-center gap-2.5 overflow-hidden">
                <span class="material-symbols-rounded {icon_color} text-sm shrink-0">key</span>
                <div class="text-left overflow-hidden">
                    <div class="text-xs font-bold {text_color} truncate">{data['name']}</div>
                    <div class="flex items-center gap-2">
                        <div class="text-[9px] text-gray-400">До {data['expire_date_str']}</div>
                        <span class="text-[8px] {data['status_bg']} {data['status_color']} px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider shrink-0">{data['status_text']}</span>
                    </div>
                </div>
            </div>
            <span class="material-symbols-rounded {check_class} text-xs selected-icon shrink-0">check</span>
        </button>
        """
        
        display_style = "grid" if is_selected else "none"
        desc, grid_html = _build_plans_grid_html(host_name, user_id, f"renew-plans-{index}", display_style)
        
        renew_plans_html += f'<div id="renew-desc-content-{index}" style="display: none;">{desc}</div>'
        renew_plans_html += grid_html
    
    options_html += '</div>'
    
    return options_html, selected_text, renew_plans_html

def _get_no_key_html() -> str:
    return """
        <div class="glass-card border border-white/10 rounded-[2rem] p-5 flex flex-col items-center justify-center text-center shadow-lg mb-3">
            <div class="w-12 h-12 bg-white/5 rounded-2xl flex items-center justify-center mb-3">
                <span class="material-symbols-rounded text-2xl text-gray-500">key_off</span>
            </div>
            <h3 class="text-sm font-black text-white mb-1 tracking-tight">Нет активных ключей</h3>
            <p class="text-[10px] text-gray-400 font-medium leading-tight max-w-[180px]">
                Купите ключ, чтобы начать пользоваться VPN
            </p>
        </div>
    """



def _duration_label(months: int | None, duration_days: int | None) -> str:
    try:
        dd = int(duration_days or 0)
    except Exception:
        dd = 0
    if dd > 0:
        if dd % 30 == 0:
            mm = dd // 30
            return f"{mm} месяц" if mm == 1 else (f"{mm} месяца" if 1 < mm < 5 else f"{mm} месяцев")
        if dd % 7 == 0:
            ww = dd // 7
            return f"{ww} неделя" if ww == 1 else (f"{ww} недели" if 1 < ww < 5 else f"{ww} недель")
        return f"{dd} день" if dd == 1 else (f"{dd} дня" if 1 < dd < 5 else f"{dd} дней")
    try:
        mm = int(months or 0)
    except Exception:
        mm = 0
    if mm <= 0:
        mm = 1
    return f"{mm} месяц" if mm == 1 else (f"{mm} месяца" if 1 < mm < 5 else f"{mm} месяцев")


def _days_from_plan(plan: dict) -> int:
    try:
        dd = int(plan.get("duration_days") or 0)
    except Exception:
        dd = 0
    if dd > 0:
        return dd
    try:
        mm = int(plan.get("months") or 0)
    except Exception:
        mm = 0
    return max(1, mm or 1) * 30


def _billing_months_for_plan(plan: dict) -> float:
    return max(1.0 / 30.0, _days_from_plan(plan) / 30.0)


def _build_plans_grid_html(host_name: str, user_id: int | None, container_id: str, display_style: str = "grid") -> str:
    import re
    try:
        hosts = get_all_hosts()
        host = next((h for h in (hosts or []) if h['host_name'] == host_name), None)
    except:
        host = None

    desc = ""
    if host:
        desc = host.get('description') or "Выберите подходящий тариф:"
        desc = re.sub(r'(\s*\n\s*){2,}', '\n', desc).strip()

    try:
        plans = get_plans_for_host(host_name)
    except:
        plans = []

    active_plans = [p for p in plans if p.get('is_active')]
    if not active_plans:
        try:
            fallback_plans = []
            for fallback_host in (get_all_hosts() or []):
                fallback_host_name = fallback_host.get('host_name')
                for fp in get_plans_for_host(fallback_host_name):
                    if fp.get('is_active'):
                        fp = dict(fp)
                        fp['_purchase_host_name'] = fallback_host_name
                        fallback_plans.append(fp)
            active_plans = fallback_plans
        except Exception:
            active_plans = []

    html = f'<div id="{container_id}" class="server-plans-container grid grid-cols-2 gap-2 mt-1" style="display: {display_style};">'

    if not active_plans:
        html += '<div class="col-span-2 text-center text-[10px] text-gray-500 py-3 glass-card border border-white/5 rounded-xl">Нет доступных тарифов</div>'
    else:
        plan_count = len(active_plans)
        for plan_idx, plan in enumerate(active_plans):
            try:
                raw_price = float(plan.get('price', 0))
                final_price = int(calculate_webapp_price(raw_price, user_id))
                months = int(plan.get('months') or 0)
                duration_days = int(plan.get('duration_days') or 0)
                duration_label = _duration_label(months, duration_days)
            except (ValueError, TypeError):
                continue

            is_last_odd = (plan_idx == plan_count - 1) and (plan_count % 2 == 1)
            span_class = " col-span-2" if is_last_odd else ""

            html += f"""
            <button
                class="plan-btn glass-card border border-white/10 rounded-2xl p-3.5 flex flex-col items-center justify-center text-center transition-all active:scale-95 hover:border-primary/40 hover:bg-white/5 group{span_class}"
                data-host="{plan.get('_purchase_host_name', host_name)}" data-plan-id="{plan['plan_id']}" data-price="{final_price}" data-plan-name="{plan.get('plan_name', '')}"
                data-months="{months or 0}" data-duration-days="{duration_days or 0}"
                onclick="selectPlan(this)">
                <span
                    class="plan-label text-[9px] font-bold text-gray-500 uppercase tracking-widest mb-0.5 group-hover:text-gray-300 transition-colors">{duration_label}</span>
                <div class="flex items-baseline gap-0.5">
                    <span class="plan-price text-xl font-bold text-white">{final_price}</span>
                    <span class="text-xs font-medium text-gray-400">₽</span>
                </div>
            </button>
            """
    html += '</div>'

    return desc, html


def _get_servers_and_plans_html(user_id: int | None = None):
    try:
        hosts = get_all_hosts()
    except:
        hosts = []
        
    if not hosts:
        return "", '<div class="col-span-2 text-center text-xs text-gray-500 py-4 glass-card border border-white/5 rounded-xl">Нет доступных серверов</div>'
        
    server_options_html = '<div class="p-1 flex flex-col gap-0.5">'
    plans_html = ""
    
    for index, host in enumerate(hosts):
        host_name = host['host_name']
        
        is_selected = (index == 0)
            
        check_class = "text-primary" if is_selected else "text-transparent"
        text_color = "text-white" if is_selected else "text-gray-300"
        icon_color = "text-primary" if is_selected else "text-gray-500"
        
        server_options_html += f"""
        <button
            class="server-option w-full p-2.5 flex items-center justify-between rounded-lg hover:bg-white/5 transition-colors"
            data-server="{host_name}" data-index="{index}" onclick="selectServer(this)">
            <div class="flex items-center gap-2.5">
                <span class="material-symbols-rounded {icon_color} text-sm">public</span>
                <div class="text-left">
                    <div class="text-xs font-bold {text_color}">{host_name}</div>
                </div>
            </div>
            <span class="material-symbols-rounded {check_class} text-xs server-selected-icon">check</span>
        </button>
        """
        
        display_style = "grid" if is_selected else "none"
        desc, grid_html = _build_plans_grid_html(host_name, user_id, f"plans-{index}", display_style)
        
        plans_html += f'<div id="desc-content-{index}" style="display: none;">{desc}</div>'
        plans_html += grid_html

    server_options_html += '</div>'
    
    return server_options_html, plans_html


def _render_banned_page(webapp_settings: dict):
    title = webapp_settings.get("webapp_title") or get_setting("panel_brand_title") or "Xatab VPN"
    logo = webapp_settings.get("webapp_logo") or ""
    icon = webapp_settings.get("webapp_icon") or ""
    
    html = f"""<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..600,0..1,-50..200&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        primary: '#10b981',
                        surface: {{
                            dark: '#121212',
                            card: '#1e1e1e',
                            highlight: '#2a2a2a'
                        }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{ font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; }}
        .glass {{ background: rgba(30, 30, 30, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05); }}
    </style>
</head>
<body class="bg-surface-dark text-white h-screen flex flex-col items-center justify-center p-6 select-none overflow-hidden">
    <div class="fixed inset-0 pointer-events-none">
        <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/10 rounded-full blur-[120px]"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px]"></div>
    </div>

    <div class="relative z-10 flex flex-col items-center text-center max-w-sm w-full">
        {f'<img src="{logo}" class="h-20 mb-8 drop-shadow-[0_0_20px_rgba(16,185,129,0.3)]">' if logo else f'<div class="w-20 h-20 bg-primary/20 rounded-3xl flex items-center justify-center mb-8 border border-primary/30 shadow-[0_0_30px_rgba(16,185,129,0.2)]"><span class="material-symbols-rounded text-primary text-4xl">block</span></div>'}
        
        <h1 class="text-3xl font-black mb-3 tracking-tight">Доступ ограничен</h1>
        <p class="text-gray-400 font-medium leading-relaxed mb-8">
            Ваш аккаунт был заблокирован за нарушение правил сервиса. Использование функций WebApp временно недоступно.
        </p>

        <div class="glass rounded-[2rem] p-6 w-full border border-red-500/20 shadow-2xl">
            <div class="flex items-center gap-4 text-left">
                <div class="w-12 h-12 bg-red-500/10 rounded-2xl flex items-center justify-center shrink-0 border border-red-500/20">
                    <span class="material-symbols-rounded text-red-500">lock_person</span>
                </div>
                <div>
                    <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest mb-1">Статус аккаунта</div>
                    <div class="text-lg font-black text-red-500 leading-none">ЗАБЛОКИРОВАН</div>
                </div>
            </div>
            
            <div class="mt-6 pt-6 border-t border-white/5">
                <p class="text-[11px] text-gray-500 font-semibold mb-4 text-center">Если вы считаете, что это ошибка, обратитесь в нашу поддержку</p>
                <a href="https://t.me/{get_setting('support_bot_username')}" target="_blank"
                   class="flex items-center justify-center gap-2 w-full bg-white text-black py-4 rounded-2xl font-black text-sm uppercase tracking-wider hover:opacity-90 active:scale-[0.98] transition-all shadow-xl">
                    <span class="material-symbols-rounded text-lg">support_agent</span>
                    <span>Написать в поддержку</span>
                </a>
            </div>
        </div>

        <div class="mt-8 opacity-40 text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
            <span>{title}</span>
            <span class="w-1 h-1 bg-gray-600 rounded-full"></span>
            <span>Security Module</span>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=403)


async def _render_main_page(user_id: int):
    webapp_settings = get_webapp_settings()
    
    # 1. Check if Webapp is enabled
    if not webapp_settings.get("webapp_enabled"):
         return HTMLResponse(content="<h1>Webapp is disabled</h1>", status_code=403)
         
    # 2. Check if user is banned
    user = get_user(user_id)
    if user and user.get('is_banned'):
         return _render_banned_page(webapp_settings)
         
    # Можно использовать webapp_domen для проверок или редиректов если нужно
    # current_domain = webapp_settings.get("webapp_domen")

    key_section = _get_no_key_html()
    profile_card = ""
    profile_keys_list = _get_no_key_html()
    setup_keys_list = _get_no_key_html()
    renew_keys_options = ""
    renew_selected_key = "Нет активных ключей"
    renew_plans_html_data = _get_no_key_html()
    keys = []
    
    if user_id:
        keys = get_user_keys(user_id)
        # Sort all keys by expiry, soonest first
        try:
            keys.sort(key=lambda k: datetime.strptime(k['expiry_date'], "%Y-%m-%d %H:%M:%S"))
        except:
            pass
            
        now = get_msk_time().replace(tzinfo=None)
        
        # --- FETCH LIVE DATA ONLY FOR ACTIVE KEYS ---
        active_keys = []
        for k in keys:
            try:
                exp = datetime.strptime(k['expiry_date'], "%Y-%m-%d %H:%M:%S")
                if exp > now:
                    active_keys.append(k)
            except: pass

        if active_keys:
            try:
                # --- 1. Fetch Key Details (User info from Host) ---
                details_tasks = []
                for k in active_keys:
                    details_tasks.append(remnawave_api.get_key_details_from_host(k))
                
                details_results = await asyncio.gather(*details_tasks, return_exceptions=True)
                
                # --- 2. Fetch Subscription Info (Traffic Stats) using UUID from Details ---
                sub_tasks = []
                # Map results to keys to keep order
                key_details_map = {}
                
                for k, res in zip(active_keys, details_results):
                    if isinstance(res, Exception) or not res or not res.get('user'):
                        sub_tasks.append(asyncio.sleep(0, None)) # Skip
                        continue
                        
                    u = res['user']
                    key_details_map[k['key_id']] = u
                    
                    # Update limits from user object immediately
                    if u.get('trafficLimitBytes') is not None:
                        k['limit_bytes'] = u.get('trafficLimitBytes')
                    if u.get('hwidDeviceLimit') is not None:
                        k['limit_ips'] = u.get('hwidDeviceLimit')

                    if not k.get('email') and not k.get('key_email'):
                        api_email = u.get('username') or u.get('email') or ''
                        if api_email:
                            k['email'] = api_email
                            k['key_email'] = api_email
                        
                    # Determine UUID for subscription check
                    # BOT PRIORITY: Use DB UUID first, then API response
                    target_uuid = k.get('remnawave_user_uuid') or u.get('uuid')
                    host = k.get('host_name')
                    
                    if target_uuid:
                        sub_tasks.append(remnawave_api.get_user_by_uuid(str(target_uuid), host_name=host))
                    else:
                        sub_tasks.append(asyncio.sleep(0, None))

                sub_results = await asyncio.gather(*sub_tasks, return_exceptions=True)
                
                # --- 3. Process Subscription Results ---
                for k, sub_res in zip(active_keys, sub_results):
                    # Try to find traffic in subscription response
                    found_traffic = None
                    if not isinstance(sub_res, Exception) and sub_res and isinstance(sub_res, dict):
                        for key_name in ['usedTrafficBytes', 'trafficUsedBytes', 'traffic_used_bytes', 'usedBytes', 'trafficUsed', 'traffic', 'used_traffic']:
                            val = sub_res.get(key_name)
                            if val is not None:
                                found_traffic = val
                                break
                    
                    if found_traffic is not None:
                        k['used_bytes'] = found_traffic
                    
                    # Fallback: check User Details (u)
                    if 'used_bytes' not in k:
                        u = key_details_map.get(k['key_id'])
                        if u:
                             # Check keys in user object
                             for key_name in ['traffic', 'trafficUsed', 'used_traffic']:
                                 if u.get(key_name) is not None:
                                     try: k['used_bytes'] = int(u.get(key_name)); break
                                     except: pass
                             
                             # Final fallback: sum upload + download
                             if 'used_bytes' not in k:
                                 uploaded = int(u.get('upload') or 0)
                                 downloaded = int(u.get('download') or 0)
                                 k['used_bytes'] = uploaded + downloaded

                    # HWID Usage
                    u = key_details_map.get(k['key_id'])
                    target_uuid = None
                    if u:
                         target_uuid = u.get('uuid')
                    if not target_uuid:
                         target_uuid = k.get('remnawave_user_uuid')
                         
                    host = k.get('host_name')

                    if target_uuid and host:
                         try:
                              devs = await remnawave_api.get_connected_devices_count(target_uuid, host_name=host)
                              if devs and 'total' in devs:
                                   k['used_ips'] = int(devs['total'])
                         except: pass
            except Exception as e:
                logger.error(f"Error fetching live stats: {e}")

        # --- CALCULATE MIN PRICE ---
        min_price_val = 0.0
        try:
            all_hosts = get_all_hosts()
            prices = []
            for h in all_hosts:
                plans = get_plans_for_host(h['host_name'])
                for p in plans:
                    if p.get('is_active'):
                        try:
                            raw_p = float(p.get('price', 0))
                            final_p = calculate_webapp_price(raw_p, user_id)
                            prices.append(final_p)
                        except: continue
            if prices:
                min_price_val = min(prices)
        except Exception as e:
            logger.error(f"Error calculating min price: {e}")

        # --- GENERATE SECTIONS ---
        if keys:
            # For the main monitoring section, show only the soonest active key
            if active_keys:
                key_section = _get_key_html(active_keys[0])
            
            # Renew, Profile and Setup sections get the full list of keys
            # (Setup will filter internally, Profile shows all, Renew now shows all)
            renew_keys_options, renew_selected_key, renew_plans_html_data = _get_renew_keys_html(keys, user_id)
            renew_selected_display = renew_selected_key
            
            profile_keys_list = _get_profile_keys_html(keys)
            setup_keys_list = _get_setup_keys_html(keys)
            
        # Profile Stats
        user = get_user(user_id)
        ref_count = get_referral_count(user_id)
        ref_earned = user.get("referral_balance_all") or 0.0
        profile_card = _get_profile_card_html(user, ref_count, len(keys), ref_earned)
    
    p = os.path.join(os.path.dirname(__file__), "app.html")
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    
    context = {
        "profile_card": profile_card,
        "key_section": key_section,
        "profile_keys_list": profile_keys_list,
        "setup_keys_list": setup_keys_list,
        "renew_keys_options": renew_keys_options,
        "renew_plans_html_data": renew_plans_html_data,
        "renew_selected_display": renew_selected_display if 'renew_selected_display' in locals() else renew_selected_key,
        "min_price": f"{int(min_price_val)} ₽" if min_price_val > 0 else "0 ₽",
        "webapp_logo": webapp_settings.get("webapp_logo") or "",
        "webapp_icon": webapp_settings.get("webapp_icon") or ""
    }
    
    content = _process_template_placeholders(content, user_id, webapp_settings, context)
    return HTMLResponse(content=content)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user_id: int | None = None, token: str | None = None):
    try:
        # 1. Authorize by Token only (query param / cookie). Never trust bare
        # user_id from the query string — that was an IDOR (CWE-639): anyone
        # could open /?user_id=<victim> and get a rendered session for them.
        resolved_user_id = None
        if token:
            from shop_bot.data_manager import database
            user = database.get_user_by_auth_token(token)
            if user:
                resolved_user_id = user['telegram_id']
        user_id = resolved_user_id

        # 2. If no valid token, serve login.html
        if user_id is None:
            p = os.path.join(os.path.dirname(__file__), "login.html")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Process placeholders for login page too
                webapp_settings = get_webapp_settings()
                context = {
                    "webapp_logo": webapp_settings.get("webapp_logo") or "",
                    "webapp_icon": webapp_settings.get("webapp_icon") or ""
                }
                content = _process_template_placeholders(content, 0, webapp_settings, context)
                return HTMLResponse(content=content)
            else:
                return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)

        webapp_settings = get_webapp_settings()
        user = get_user(user_id)
        if user and user.get('is_banned'):
            return _render_banned_page(webapp_settings)

        return await _render_main_page(user_id)

    except Exception as e:
        error_details = traceback.format_exc()
        return HTMLResponse(content=f"<h1>500 Internal Server Error</h1><pre>{error_details}</pre>", status_code=500)

# ===== API Models =====

class SupportStatusRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    token: str | None = None
    init_data: str | None = None

class SupportTicketCreateRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    subject: str
    token: str | None = None
    init_data: str | None = None

class SupportMessageSendRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    ticket_id: int
    message: str
    token: str | None = None
    init_data: str | None = None

class PaymentMethodsRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    token: str | None = None
    init_data: str | None = None

class TokenRequest(BaseModel):
    init_data: str

class TelegramDirectAuthRequest(BaseModel):
    """Must carry signed Telegram WebApp initData — never a bare user_id."""
    init_data: str

class EmailAuthRequest(BaseModel):
    email: str
    password: str

class EmailVerifyRequest(BaseModel):
    email: str
    code: str

class EmailResendRequest(BaseModel):
    email: str

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetCheckRequest(BaseModel):
    email: str
    code: str

class PasswordResetVerifyRequest(BaseModel):
    email: str
    code: str
    new_password: str

# In-memory reset codes: { "email@bot.local": {"code_hash": sha256, "expires": ts} }
# Plaintext 6-digit lives only in the Telegram message, not in this dict.
PASSWORD_RESET_TOKENS = {}
PASSWORD_RESET_TTL_SECONDS = 600


def _hash_password_reset_code(email: str, code: str) -> str:
    return hashlib.sha256(f"{email.strip().lower()}:{str(code).strip()}".encode("utf-8")).hexdigest()


def _password_reset_code_matches(email: str, code: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    expected = _hash_password_reset_code(email, code or "")
    try:
        return hmac.compare_digest(expected, str(stored_hash))
    except Exception:
        return False

class SyncTgRequest(BaseModel):
    token: str
    init_data: str


class DeviceTiersRequest(BaseModel):
    host_name: str

class CreatePaymentRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    payment_method: str
    plan_id: int
    host_name: str | None = None
    action: str
    key_id: int | None = None
    promo_code: str | None = None
    tier_device_count: int | None = None
    tier_price: float = 0
    token: str | None = None
    init_data: str | None = None

class CreateTopUpPaymentRequest(BaseModel):
    payment_method: str
    amount: float
    token: str | None = None
    user_id: int | None = None  # ignored; identity from token only
    init_data: str | None = None

class ApplyPromoRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    promo_code: str
    plan_id: int | None = None
    price: float | None = None
    token: str | None = None
    init_data: str | None = None

class RenameKeyRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    new_name: str
    token: str | None = None

class DeleteAllDevicesRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    host_name: str | None = None
    token: str | None = None

class SearchKeysRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    query: str
    token: str | None = None

# ===== API Endpoints =====


def validate_telegram_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = TELEGRAM_INIT_DATA_MAX_AGE_SECONDS,
) -> dict | None:
    """Verify Telegram WebApp initData HMAC and freshness (auth_date).

    Protocol: secret = HMAC_SHA256(key=\"WebAppData\", msg=bot_token);
    compare hash with HMAC_SHA256(secret, data_check_string).
    """
    from urllib.parse import parse_qsl
    import hmac
    import hashlib
    import json

    try:
        if not init_data or len(init_data) < 10:
            logger.warning("Telegram auth: init_data is empty or too short")
            return None

        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            logger.warning("Telegram auth: hash not found in init_data")
            return None
        
        received_hash = parsed_data.pop("hash")
        
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed_data.items())
        )
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning(
                f"Telegram auth: hash mismatch. Expected={calculated_hash[:16]}... "
                f"Got={received_hash[:16]}..."
            )
            return None

        auth_date_raw = parsed_data.get("auth_date")
        if auth_date_raw is None or auth_date_raw == "":
            logger.warning("Telegram auth: auth_date missing")
            return None
        try:
            auth_date = int(auth_date_raw)
        except (TypeError, ValueError):
            logger.warning("Telegram auth: auth_date is not an integer")
            return None
        now = int(time.time())
        if auth_date > now + 60:
            logger.warning("Telegram auth: auth_date is in the future")
            return None
        if max_age_seconds is not None and (now - auth_date) > int(max_age_seconds):
            logger.warning("Telegram auth: auth_date expired")
            return None

        user_json = parsed_data.get("user")
        if user_json:
            return json.loads(user_json)
        logger.warning("Telegram auth: hash valid but no user field")
        return None
    except Exception as e:
        logger.error(f"Telegram auth validation error: {e}")
        return None


def _issue_persistent_token_for_telegram_user(user_id: int) -> dict:
    """Shared token issue/lookup used by /api/auth/token and /api/auth/telegram-direct."""
    from shop_bot.data_manager import database

    user = get_user(user_id)
    if user and user.get("is_banned"):
        return {"ok": False, "error": "Access denied", "status_code": 403}

    existing_token = database.get_auth_token_by_user_id(user_id)
    if existing_token:
        return {"ok": True, "token": existing_token, "user_id": user_id}

    token = str(uuid.uuid4())
    database.update_user_auth_token(user_id, token)
    return {"ok": True, "token": token, "user_id": user_id}


@app.get("/api/auth/request-token")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_request_auth_token(request: Request):
    from shop_bot.data_manager import database
    token = str(uuid.uuid4())[:36]
    TEMP_AUTH_TOKENS[token] = None
    try:
        database.create_webapp_auth_request(token)
        database.cleanup_old_webapp_auth_requests()
    except Exception as e:
        logger.error(f"Failed to persist webapp auth request: {e}")
    bot_username = get_setting("telegram_bot_username")
    auth_url = f"tg://resolve?domain={bot_username}&start=auth_{token}"
    return {"ok": True, "token": token, "auth_url": auth_url}

@app.get("/api/auth/check-token/{token}")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_check_auth_token(token: str, request: Request):
    from shop_bot.data_manager import database
    # 1. Check in memory (waiting for bot confirmation, same-process fast path)
    if token in TEMP_AUTH_TOKENS and TEMP_AUTH_TOKENS[token] is not None:
        user_id = TEMP_AUTH_TOKENS.pop(token)
        
        # Check existing token first
        existing_token = database.get_auth_token_by_user_id(user_id)
        if existing_token:
            return {"ok": True, "authorized": True, "user_id": user_id, "token": existing_token}
            
        # Generate persistent token
        persistent_token = str(uuid.uuid4())
        database.update_user_auth_token(user_id, persistent_token)
        return {"ok": True, "authorized": True, "user_id": user_id, "token": persistent_token}
    
    # 2. Check in DB (already authorized)
    user = database.get_user_by_auth_token(token)
    if user:
        if user.get('is_banned'):
            return {"ok": True, "authorized": False, "error": "Banned"}
        return {"ok": True, "authorized": True, "user_id": user['telegram_id'], "token": token}

    # 3. Check webapp_auth_requests table (bot confirmed login from a different process/container)
    try:
        confirmed_user_id = database.get_webapp_auth_request(token, consume=True)
    except Exception:
        confirmed_user_id = None
    if confirmed_user_id:
        if user and user.get('is_banned'):
            return {"ok": True, "authorized": False, "error": "Banned"}
        existing_token = database.get_auth_token_by_user_id(confirmed_user_id)
        if existing_token:
            return {"ok": True, "authorized": True, "user_id": confirmed_user_id, "token": existing_token}
        persistent_token = str(uuid.uuid4())
        database.update_user_auth_token(confirmed_user_id, persistent_token)
        return {"ok": True, "authorized": True, "user_id": confirmed_user_id, "token": persistent_token}

    return {"ok": True, "authorized": False}

@app.post("/api/auth/token")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_create_token(request: Request, req: TokenRequest):
    """Generate or retrieve a persistent login token using verified Telegram data."""
    token_str = get_setting("telegram_bot_token")
    if not token_str:
        return JSONResponse({"ok": False, "error": "Server configuration error"}, status_code=500)

    user_data = validate_telegram_data(req.init_data, token_str)
    
    if not user_data or not user_data.get("id"):
        return JSONResponse({"ok": False, "error": "Invalid auth data"}, status_code=401)

    result = _issue_persistent_token_for_telegram_user(int(user_data["id"]))
    status = result.pop("status_code", 200)
    if not result.get("ok"):
        return JSONResponse(result, status_code=status)
    return {"ok": True, "token": result["token"]}


@app.post("/api/auth/telegram-direct")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_telegram_direct_auth(request: Request, req: TelegramDirectAuthRequest):
    """Authenticate inside Telegram WebApp using signed initData only.

    Previously accepted a bare ``user_id`` from the client (CWE-306). User identity
    is now taken exclusively from HMAC-validated Telegram WebApp initData.
    """
    from shop_bot.data_manager import database
    try:
        token_str = get_setting("telegram_bot_token")
        if not token_str:
            return JSONResponse({"ok": False, "error": "Server configuration error"}, status_code=500)

        user_data = validate_telegram_data(req.init_data, token_str)
        if not user_data or not user_data.get("id"):
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)

        user_id = int(user_data["id"])
        user = get_user(user_id)
        if not user:
            return JSONResponse({"ok": False, "error": "User not registered"}, status_code=401)

        if user.get("is_banned"):
            return JSONResponse({"ok": False, "error": "Access denied"}, status_code=403)

        existing_token = database.get_auth_token_by_user_id(user_id)
        if existing_token:
            return {"ok": True, "token": existing_token, "user_id": user_id}

        token = str(uuid.uuid4())
        database.update_user_auth_token(user_id, token)
        return {"ok": True, "token": token, "user_id": user_id}
    except Exception as e:
        logger.error(f"Telegram direct auth error: {e}")
        return JSONResponse({"ok": False, "error": "Auth error"}, status_code=500)

def _validate_password(password: str) -> str | None:
    """Проверка пароля при регистрации / сбросе / смене.

    Раньше хватало 5 символов без цифр («ababa») — это принималось.
    Существующие аккаунты с таким паролем по-прежнему входят (login
    политику не применяет); новые пароли должны быть длиннее и смешанные.
    """
    if not isinstance(password, str):
        password = str(password or "")
    if len(password) < 8:
        return "Пароль должен содержать минимум 8 символов"
    if password.isdigit():
        return "Пароль не должен состоять только из цифр"
    if not any(c.isalpha() for c in password):
        return "Пароль должен содержать хотя бы одну букву"
    if not any(c.isdigit() for c in password):
        return "Пароль должен содержать хотя бы одну цифру"
    if len(set(password)) < 2:
        return "Пароль слишком простой — используйте разные символы"
    return None

EMAIL_RESEND_COOLDOWN_SECONDS = 60
EMAIL_CODE_TTL_SECONDS = 600


async def _issue_email_verification_code(user_id: int, email: str) -> tuple[bool, str | None]:
    """Сгенерировать, сохранить и отправить новый код подтверждения email.

    Возвращает (ok, error). Не поднимает исключения наружу.

    Отправка письма (блокирующий вызов smtplib, может делать несколько попыток
    с паузами при сетевых сбоях) выполняется в отдельном потоке через
    `asyncio.to_thread`, чтобы не блокировать event loop на время ожидания/повторов.
    """
    import random
    from shop_bot.data_manager import database
    from shop_bot.modules.email_sender import send_activation_code, is_smtp_configured

    if not is_smtp_configured():
        logger.error("Попытка отправить код активации email, но SMTP не настроен в админ-панели.")
        return False, "Отправка писем временно недоступна. Попробуйте позже или обратитесь в поддержку."

    code = f"{random.randint(0, 999999):06d}"
    if not database.set_email_verification_code(user_id, code, ttl_seconds=EMAIL_CODE_TTL_SECONDS):
        return False, "Ошибка базы данных"

    try:
        sent = await asyncio.to_thread(send_activation_code, email, code)
    except Exception as e:
        logger.error(f"Unexpected error while sending activation code to {email}: {e}")
        sent = False

    if not sent:
        return False, "Не удалось отправить письмо с кодом. Проверьте адрес почты или попробуйте позже."
    return True, None


@app.post("/api/auth/email/register")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_register(request: Request, req: EmailAuthRequest):
    from shop_bot.data_manager import database

    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited

    pw_err = _validate_password(req.password)
    if pw_err:
        return {"ok": False, "error": pw_err}

    existing = database.get_user_by_email(req.email)
    if existing:
        # Тот же ответ, что у новой регистрации — иначе по «Email уже
        # зарегистрирован» можно перебирать занятые адреса.
        return {"ok": True, "requires_verification": True, "email": req.email}

    user = database.create_user_by_email(req.email, req.password)
    if not user:
        return {"ok": False, "error": "Ошибка при регистрации"}

    ok, err = await _issue_email_verification_code(user['telegram_id'], req.email)
    if not ok:
        return {"ok": False, "error": err}

    return {"ok": True, "requires_verification": True, "email": req.email}

@app.post("/api/auth/email/verify")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_verify(request: Request, req: EmailVerifyRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    code = (req.code or "").strip()
    # Не раскрываем, существует ли email. Код обязателен всегда: раньше при
    # email_verified=1 токен выдавался без кода — достаточно было знать адрес.
    if not user or not code or not database.check_email_verification_code(user['telegram_id'], code):
        return {"ok": False, "error": "Неверный или устаревший код"}

    if not database.mark_email_verified(user['telegram_id']):
        return {"ok": False, "error": "Ошибка базы данных"}

    token = str(uuid.uuid4())
    database.update_user_auth_token(user['telegram_id'], token)
    return {"ok": True, "token": token}

@app.post("/api/auth/email/resend")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_resend(request: Request, req: EmailResendRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    if not user or user.get('email_verified'):
        return {"ok": True}

    info = database.get_email_verification(user['telegram_id']) or {}
    last_sent_raw = info.get('email_code_last_sent_at')
    if last_sent_raw:
        try:
            last_sent = datetime.strptime(str(last_sent_raw), "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < EMAIL_RESEND_COOLDOWN_SECONDS:
                return {"ok": True}
        except Exception:
            pass

    ok, err = await _issue_email_verification_code(user['telegram_id'], req.email)
    if not ok:
        return {"ok": False, "error": err}
    return {"ok": True}

@app.post("/api/auth/email/login")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_login(request: Request, req: EmailAuthRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    if not user or not database.verify_password(req.password, user.get('auth_pass')):
        return {"ok": False, "error": "Неверный email или пароль"}
        
    if user.get('is_banned'):
        return {"ok": False, "error": "Аккаунт заблокирован"}

    if not user.get('email_verified'):
        return {"ok": False, "error": "Email не подтверждён", "email_not_verified": True}

    token = str(uuid.uuid4())
    database.update_user_auth_token(user['telegram_id'], token)
    return {"ok": True, "token": token}

@app.post("/api/auth/email/reset/request")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_reset_request(request: Request, req: PasswordResetRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    # Всегда один ответ: иначе «Email не найден» / «не синхронизирован»
    # выдают, зарегистрирован ли адрес и привязан ли он к Telegram.
    if not user or database.is_email_only_user(user.get("telegram_id")):
        return {"ok": True}

    import random
    import time
    email_lower = req.email.lower().strip()
    code = str(random.randint(100000, 999999))
    PASSWORD_RESET_TOKENS[email_lower] = {
        "code_hash": _hash_password_reset_code(email_lower, code),
        "expires": time.time() + PASSWORD_RESET_TTL_SECONDS,
    }
    
    try:
        success = await _send_telegram_message(
            user['telegram_id'], 
            f"🔐 <b>Восстановление пароля</b>\n\nВаш код для сброса безопасности:\n<code>{code}</code>\n\n<i>Код действителен 10 минут. Если вы не запрашивали сброс пароля, проигнорируйте это сообщение.</i>"
        )
        if not success:
            PASSWORD_RESET_TOKENS.pop(email_lower, None)
            return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to call _send_telegram_message: {e}")
        PASSWORD_RESET_TOKENS.pop(email_lower, None)
        return {"ok": True}

    return {"ok": True}

@app.post("/api/auth/email/reset/check")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_reset_check(request: Request, req: PasswordResetCheckRequest):
    import time
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    email_lower = req.email.lower().strip()
    if email_lower not in PASSWORD_RESET_TOKENS:
        return {"ok": False, "error": "Код не запрашивался или истёк"}
        
    token_data = PASSWORD_RESET_TOKENS[email_lower]
    if time.time() > token_data["expires"]:
        return {"ok": False, "error": "Код устарел"}
        
    if not _password_reset_code_matches(email_lower, req.code, token_data.get("code_hash")):
        return {"ok": False, "error": "Неверный код"}
        
    return {"ok": True}

@app.post("/api/auth/email/reset/verify")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_reset_verify(request: Request, req: PasswordResetVerifyRequest):
    import time
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    email_lower = req.email.lower().strip()
    if email_lower not in PASSWORD_RESET_TOKENS:
        return {"ok": False, "error": "Код не запрашивался или истёк"}
        
    token_data = PASSWORD_RESET_TOKENS[email_lower]
    if time.time() > token_data["expires"]:
        del PASSWORD_RESET_TOKENS[email_lower]
        return {"ok": False, "error": "Код устарел"}
        
    if not _password_reset_code_matches(email_lower, req.code, token_data.get("code_hash")):
        return {"ok": False, "error": "Неверный код"}
        
    from shop_bot.data_manager import database
    pw_err = _validate_password(req.new_password)
    if pw_err:
        return {"ok": False, "error": pw_err}
    if not database.update_user_password(req.email, req.new_password):
        return {"ok": False, "error": "Ошибка базы данных"}
        
    del PASSWORD_RESET_TOKENS[email_lower]
    return {"ok": True}


# ── Профиль: смена пароля / email из webapp (пункт меню "Редактировать профиль") ──
#
# Доступно только пользователям, которые зарегистрировались по email+пароль
# (у них заполнен auth_email) — для чисто Telegram-аккаунтов пункт меню скрыт
# на фронтенде (см. /api/user/profile-info).
_EMAIL_FORMAT_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.post("/api/user/profile-info")
async def api_user_profile_info(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    auth_email = user.get("auth_email") or None
    return {
        "ok": True,
        "has_email_auth": bool(auth_email),
        "auth_email": auth_email,
        "email_verified": bool(user.get("email_verified")),
        "pending_email": user.get("pending_email") or None,
    }


@app.post("/api/user/profile/change-password")
async def api_user_profile_change_password(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    if not user.get("auth_email"):
        return {"ok": False, "error": "Смена пароля доступна только для аккаунтов с входом по email"}

    current_password = str(data.get("current_password") or "")
    new_password = str(data.get("new_password") or "")

    from shop_bot.data_manager import database
    if not database.verify_password(current_password, user.get("auth_pass")):
        return {"ok": False, "error": "Неверный текущий пароль"}

    pw_err = _validate_password(new_password)
    if pw_err:
        return {"ok": False, "error": pw_err}

    if not database.update_user_password_by_id(user["telegram_id"], new_password):
        return {"ok": False, "error": "Ошибка базы данных"}
    return {"ok": True, "message": "Пароль изменён"}


@app.post("/api/user/profile/change-email/request")
async def api_user_profile_change_email_request(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    if not user.get("auth_email"):
        return {"ok": False, "error": "Смена email доступна только для аккаунтов с входом по email"}

    password = str(data.get("password") or "")
    new_email = str(data.get("new_email") or "").strip().lower()

    from shop_bot.data_manager import database
    if not database.verify_password(password, user.get("auth_pass")):
        return {"ok": False, "error": "Неверный пароль"}

    if not new_email or not _EMAIL_FORMAT_RE.match(new_email):
        return {"ok": False, "error": "Некорректный формат email"}
    if new_email == (user.get("auth_email") or "").strip().lower():
        return {"ok": False, "error": "Это и есть ваш текущий email"}

    existing = database.get_user_by_email(new_email)
    if existing and existing["telegram_id"] != user["telegram_id"]:
        return {"ok": False, "error": "Этот email уже используется другим аккаунтом"}

    if not database.set_pending_email(user["telegram_id"], new_email):
        return {"ok": False, "error": "Ошибка базы данных"}

    ok, err = await _issue_email_verification_code(user["telegram_id"], new_email)
    if not ok:
        database.clear_pending_email(user["telegram_id"])
        return {"ok": False, "error": err}
    return {"ok": True, "message": f"Код подтверждения отправлен на {new_email}"}


@app.post("/api/user/profile/change-email/resend")
async def api_user_profile_change_email_resend(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    from shop_bot.data_manager import database
    pending_email = user.get("pending_email")
    if not pending_email:
        return {"ok": False, "error": "Нет ожидающей смены email"}

    info = database.get_email_verification(user["telegram_id"]) or {}
    last_sent_raw = info.get("email_code_last_sent_at")
    if last_sent_raw:
        try:
            last_sent = datetime.strptime(str(last_sent_raw), "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < EMAIL_RESEND_COOLDOWN_SECONDS:
                return {
                    "ok": False,
                    "error": f"Подождите {int(EMAIL_RESEND_COOLDOWN_SECONDS - elapsed)} сек. перед повторной отправкой",
                    "retry_after": int(EMAIL_RESEND_COOLDOWN_SECONDS - elapsed),
                }
        except Exception:
            pass

    ok, err = await _issue_email_verification_code(user["telegram_id"], pending_email)
    if not ok:
        return {"ok": False, "error": err}
    return {"ok": True}


@app.post("/api/user/profile/change-email/verify")
async def api_user_profile_change_email_verify(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    from shop_bot.data_manager import database
    if not user.get("pending_email"):
        return {"ok": False, "error": "Нет ожидающей смены email"}

    code = str(data.get("code") or "").strip()
    if not code or not database.check_email_verification_code(user["telegram_id"], code):
        return {"ok": False, "error": "Неверный или устаревший код"}

    ok, result = database.finalize_pending_email_change(user["telegram_id"])
    if not ok:
        return {"ok": False, "error": result}
    return {"ok": True, "message": "Email изменён", "auth_email": result}


@app.post("/api/user/profile/change-email/cancel")
async def api_user_profile_change_email_cancel(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    from shop_bot.data_manager import database
    database.clear_pending_email(user["telegram_id"])
    return {"ok": True}


@app.post("/api/auth/sync-tg")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_sync_tg(request: Request, req: SyncTgRequest):
    from shop_bot.data_manager import database
    user = database.get_user_by_auth_token(req.token)
    if not user:
        return {"ok": False, "error": "Не авторизован"}
        
    token_str = get_setting("telegram_bot_token")
    if not token_str:
         return {"ok": False, "error": "Server configuration error"}
         
    tg_data = validate_telegram_data(req.init_data, token_str)
    if not tg_data or not tg_data.get('id'):
         return {"ok": False, "error": "Invalid Telegram data"}
         
    tg_id = tg_data.get('id')
    tg_username = tg_data.get('username') or ''
    
    if user['telegram_id'] > 0:
         return {"ok": False, "error": "Telegram уже привязан"}
         
    res = database.link_telegram_to_email_user(user['telegram_id'], tg_id, tg_username)
    if res is True:
         return {"ok": True}
    else:
         return {"ok": False, "error": str(res)}


@app.post("/api/device-tiers")
async def api_device_tiers(req: DeviceTiersRequest):
    try:
        host_data = get_host(req.host_name)
        if not host_data:
            return {"ok": True, "device_mode": "plan", "tiers": [], "tier_lock_extend": 0}
        mode = host_data.get('device_mode', 'plan')
        lock = int(host_data.get('tier_lock_extend', 0) or 0)
        from shop_bot.data_manager import database
        base_devices = int(database.get_setting(f"base_device_{req.host_name}") or "1")
        tiers = []
        if mode == 'tiers':
            raw = get_device_tiers(req.host_name)
            tiers = [{"tier_id": t["tier_id"], "device_count": t["device_count"], "price": float(t["price"])} for t in raw]
        return {"ok": True, "device_mode": mode, "tiers": tiers, "tier_lock_extend": lock, "base_device_count": base_devices}
    except Exception as e:
        logger.error(f"API device-tiers error: {e}")
        return {"ok": False, "error": str(e)}

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
            payload = {
                "amount": {"value": f"{final_price:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{get_setting('telegram_bot_username')}"},
                "capture": True, "description": comment, "metadata": meta
            }
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
                platega = PlategaAPI(mid, key)
                url, _ = await platega.create_payment(float(final_price), desc, pid, f"https://t.me/{get_setting('telegram_bot_username')}", f"https://t.me/{get_setting('telegram_bot_username')}", 2)
                if url:
                    kb = create_payment_keyboard(url)
                    await _send_telegram_message(user_id, f"<b>Оплата через Platega</b>\n\nСумма: <b>{final_price:.2f} RUB</b>\n\n<i>Счет также доступен в WebApp.</i>", kb)
                    return {"ok": True, "payment_url": url, "payment_id": pid, "message": "Счёт создан"}
                return {"ok": False, "error": "Ошибка получения ссылки Platega"}
            except Exception as e:
                return {"ok": False, "error": f"Ошибка Platega: {e}"}

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
                platega = PlategaAPI(mid, key)
                url, _ = await platega.create_payment(float(final_price), desc, pid, f"https://t.me/{get_setting('telegram_bot_username')}", f"https://t.me/{get_setting('telegram_bot_username')}", 13)
                if url:
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
            receipt = None
            customer_email = get_setting("receipt_email")
            if customer_email and "@" in str(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": "Пополнение баланса",
                        "quantity": "1.00",
                        "amount": {"value": price_str, "currency": "RUB"},
                        "vat_code": "1",
                        "payment_subject": "service",
                        "payment_mode": "full_payment",
                    }],
                }
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
                platega = PlategaAPI(mid, key)
                url, txid = await platega.create_payment(
                    final_price,
                    "Пополнение баланса",
                    pid,
                    return_url,
                    return_url,
                    _platega_method_code_from_settings(),
                )
                if url:
                    if txid:
                        try:
                            meta2 = dict(meta)
                            meta2["platega_transaction_id"] = txid
                            create_payload_pending(pid, user_id, final_price, meta2)
                        except Exception:
                            pass
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

@app.post("/api/apply-promo")
async def api_apply_promo(req: ApplyPromoRequest, request: Request):
    """Проверить промокод и посчитать цену со скидкой.

    Промокоды в этом проекте — это ИСКЛЮЧИТЕЛЬНО скидка на покупку/продление
    ключа (см. таблицу `promo_codes`: только discount_percent/discount_amount,
    без какого-либо понятия "начислить на баланс"). Раньше здесь была мёртвая
    ветка на несуществующее поле `promo_type` ("balance"/"universal"), которая
    физически не могла сработать (в БД такой колонки никогда не было — из-за
    этого скидочная ветка тоже была недостижима: promo.get('promo_type')
    всегда возвращал None). Заодно эта мёртвая ветка теоретически позволяла бы
    напрямую зачислять баланс по промокоду, что недопустимо: активация
    промокода должна быть возможна только при покупке/продлении ключа, а не
    при пополнении баланса.
    """
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        code = req.promo_code.strip().upper()

        promo, error = rw_repo.check_promo_code_available(code, user_id, plan_id=req.plan_id)
        if not promo:
            return {"ok": False, "error": rw_repo.promo_error_message(error)}

        if req.price is None:
            return {"ok": False, "error": "Промокод действителен только при покупке или продлении ключа"}

        new_price = float(req.price)
        if promo.get('discount_percent'):
            new_price -= new_price * (float(promo['discount_percent']) / 100)
        elif promo.get('discount_amount'):
            new_price -= float(promo['discount_amount'])
        else:
            return {"ok": False, "error": "Промокод не даёт скидку"}

        return {
            "ok": True,
            "promo_type": "discount",
            "new_price": max(0, round(new_price, 2))
        }
    except Exception as e:
        logger.error(f"API apply-promo error: {e}")
        return {"ok": False, "error": str(e)}

class CheckPaymentRequest(BaseModel):
    payment_id: str
    token: str | None = None
    init_data: str | None = None


def _check_payment_unpaid() -> dict:
    """Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена.

    Один и тот же JSON и 200, чтобы не палить существование чужого payment_id
    через 401/403 или разный ``ok``.
    """
    return {"ok": True, "paid": False}


@app.post("/api/check-payment")
async def api_check_payment(req: CheckPaymentRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _check_payment_unpaid()

        if not req.payment_id or req.payment_id == "undefined" or req.payment_id == "null":
            return {"ok": False, "error": "Invalid payment_id"}

        user_id = int(user["telegram_id"])
        if not payment_owned_by_user(req.payment_id, user_id):
            return _check_payment_unpaid()

        # Subscription purchases log with the same payment_id; top_up logs a new uuid,
        # so also treat pending status 'paid' as success (webhook already completed it).
        # transactions.status must be 'paid' — TON Connect inserts a pending row first.
        exists = check_transaction_exists(req.payment_id)
        if not exists:
            try:
                pending_status = (get_pending_status(req.payment_id) or "").lower()
            except Exception:
                pending_status = ""
            if pending_status != "paid":
                return _check_payment_unpaid()

        result = {
            "ok": True,
            "paid": True,
            "message": "Оплата успешно подтверждена",
        }
        try:
            result["balance"] = float(get_balance(user_id) or 0)
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error(f"Check payment error: {e}")
        return {"ok": False, "error": str(e)}

class KeyActionRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    host_name: str | None = None
    token: str | None = None
    init_data: str | None = None

class DeleteDeviceRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    device_id: str
    host_name: str | None = None
    token: str | None = None
    init_data: str | None = None

class CommentRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    key_id: int
    comment: str
    token: str | None = None
    init_data: str | None = None

class GiftActivateRequest(BaseModel):
    user_id: int | None = None  # ignored; identity from token only
    gift_code: str
    token: str | None = None
    init_data: str | None = None

# ── Referral info ──────────────────────────────────────────────────────────
@app.post("/api/user/referral-info")
async def api_user_referral_info(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _require_authenticated_user(request, data=data)
    if not user:
        return _unauthorized()

    uid = user["telegram_id"]
    bot_username = get_setting("telegram_bot_username") or ""
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")
    bot_link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else ""
    webapp_link = f"{webapp_domain}/ref/{uid}" if webapp_domain else ""
    share_text = (get_setting("referral_share_text") or "").strip() or (
        "🌐Обход глушилок и блокировок на любом устройстве! 😊"
    )

    from shop_bot.data_manager.remnawave_repository import get_referral_count
    count = get_referral_count(uid)
    earned = float(user.get("referral_balance_all") or 0)
    available = float(user.get("referral_balance") or 0)

    return {
        "ok": True,
        "bot_link": bot_link,
        "webapp_link": webapp_link,
        "share_text": share_text,
        "count": count,
        "earned": earned,
        "available": available,
        "has_open_request": rw_repo.has_open_referral_withdrawal_request(uid),
    }

# ── User sent gifts ────────────────────────────────────────────────────────
def _gift_link_row_html(label: str, link: str, share_text: str) -> str:
    """Одна строка со ссылкой активации подарка: текст ссылки + копировать + поделиться."""
    safe_link = link.replace("'", "\\'")
    return f"""
    <div class="flex flex-col gap-1 min-w-0">
        <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider px-0.5">{label}</div>
        <div class="flex items-center gap-2 min-w-0">
            <div class="flex-1 min-w-0 bg-black/30 rounded-lg px-3 py-1.5 text-[10px] text-gray-300 font-mono truncate">{link}</div>
            <button onclick="copyToClipboard('{safe_link}', this)" class="shrink-0 bg-primary/20 text-primary rounded-lg p-1.5 hover:bg-primary/30 active:scale-95 transition-all">
                <span class="material-symbols-rounded text-sm">content_copy</span>
            </button>
            <a href="https://t.me/share/url?url={quote(link, safe='')}&text={quote(share_text, safe='')}" target="_blank"
               class="shrink-0 bg-[#0088cc]/20 text-[#00aaff] rounded-lg p-1.5 hover:bg-[#0088cc]/30 active:scale-95 transition-all">
                <span class="material-symbols-rounded text-sm">send</span>
            </a>
        </div>
    </div>"""


def _get_gift_action_block_html(gift_code: str, webapp_link: str, telegram_link: str) -> str:
    """Общий блок для неактивированного подарка: обе ссылки активации
    (webapp + Telegram), каждая со своими кнопками копировать/поделиться,
    и отдельно, с явным отступом, кнопка "Активировать себе" — специально
    подальше от остальных кнопок, чтобы не нажать её случайно."""
    share_text = (get_setting("gift_share_text") or "").strip() or (
        "🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать"
    )
    links_html = "".join(
        _gift_link_row_html(label, link, share_text)
        for label, link in (("Ссылка активации (в приложении)", webapp_link), ("Ссылка активации (в Telegram)", telegram_link))
        if link
    )
    return f"""
         <div class="flex flex-col gap-2 mt-1 pt-2 border-t border-white/5">
             <div class="flex items-center gap-2 bg-amber-500/8 border border-amber-500/20 rounded-xl px-3 py-2">
                 <span class="material-symbols-rounded text-amber-400 text-sm shrink-0">info</span>
                 <span class="text-[9px] text-amber-200/80 leading-relaxed">Подарок ещё не активирован. Активируйте его себе или поделитесь ссылкой, чтобы отдать другому пользователю.</span>
             </div>
             {links_html}
             <div class="mt-3 pt-2 border-t border-dashed border-white/10">
                 <button onclick="activateOwnGift('{gift_code}', this)"
                     class="w-full bg-amber-500 hover:bg-amber-600 text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                     <span class="material-symbols-rounded text-sm">redeem</span>
                     <span>Активировать себе</span>
                 </button>
             </div>
         </div>"""


def _get_gift_fallback_card_html(g: dict, badge_html: str, action_block_html: str) -> str:
    """Карточка подарка на случай, если связанный VPN-ключ не найден (например,
    ещё не успел создаться) — но со всеми теми же полями/кнопками, что и у
    полной карточки, чтобы подарок был полноценно управляемым в любом случае."""
    host_name = g.get("host_name") or "Подарок"
    created_at = (g.get("created_at") or "")[:10]
    return f"""
        <div class="glass-card border border-white/10 rounded-2xl p-3 flex flex-col gap-2 mb-3">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <div class="w-9 h-9 bg-white/5 rounded-xl flex items-center justify-center shrink-0">
                        <span class="material-symbols-rounded text-amber-400 text-lg">card_giftcard</span>
                    </div>
                    <div>
                        <div class="text-xs font-bold text-white">{host_name}</div>
                        <div class="text-[9px] text-gray-500">{created_at}</div>
                    </div>
                </div>
                {badge_html}
            </div>
            {action_block_html}
        </div>"""


@app.post("/api/user/gifts")
async def api_user_gifts(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _require_authenticated_user(request, data=data)
    if not user:
        return _unauthorized()

    uid = user["telegram_id"]
    from shop_bot.data_manager import database
    gifts = database.get_user_inactive_gifts(uid) or []

    bot_username = get_setting("telegram_bot_username") or ""
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")
    gift_share_text = (get_setting("gift_share_text") or "").strip() or (
        "🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать"
    )

    # Бейдж "Подарок" на карточке ключа не нужен — карточки уже находятся на
    # отдельной вкладке "Подарочные", подпись была избыточной.
    badge_html = ""

    result = []
    for g in gifts:
        code = g.get("gift_code") or ""
        webapp_link = f"{webapp_domain}/gift/{code}" if webapp_domain else ""
        telegram_link = f"https://t.me/{bot_username}?start=gift_{code}" if bot_username else ""
        # "link" оставлен для обратной совместимости (используется JS-фолбэком) — предпочитаем webapp-ссылку.
        link = webapp_link or telegram_link

        action_block_html = _get_gift_action_block_html(code, webapp_link, telegram_link)

        card_html = None
        key_id = g.get("key_id")
        gift_key = database.get_key_by_id(int(key_id)) if key_id else None
        if gift_key:
            card_html = _get_key_card_html(gift_key, badge_html=badge_html, extra_content_html=action_block_html)
        else:
            card_html = _get_gift_fallback_card_html(g, badge_html, action_block_html)

        result.append({
            "gift_id": g.get("gift_id"),
            "gift_code": code,
            "host_name": g.get("host_name"),
            "created_at": g.get("created_at"),
            "expires_at": g.get("expires_at"),
            "link": link,
            "webapp_link": webapp_link,
            "telegram_link": telegram_link,
            "card_html": card_html,
        })

    return {"ok": True, "gifts": result, "share_text": gift_share_text}

# ── Gift activation (shared business logic) ────────────────────────────────
#
# Единая точка активации подарка — используется и обычной кнопкой
# "Активировать себе" (POST /api/gift/activate), и единым сценарием
# pending action (POST /api/webapp/pending-actions/complete), чтобы не
# дублировать бизнес-логику (создание/переназначение ключа, реферал от
# дарителя) в двух местах.
def _activate_gift_for_user(user_id: int, gift_code: str) -> dict:
    """Активировать подарок `gift_code` для пользователя `user_id`.

    Возвращает структурированный результат:
        {"ok": bool, "status": str, "message": str}

    status ∈ {"activated", "already_activated", "not_found", "expired", "error"}.

    Идемпотентность: если ЭТОТ ЖЕ пользователь уже успешно активировал именно
    этот подарок ранее (например, повторный вызов после сетевого сбоя), метод
    возвращает ok=True/status="already_activated" без создания второго ключа
    и без повторного назначения реферала. Если подарок был активирован ДРУГИМ
    пользователем (обычная гонка/чужой подарок) — ok=False.

    Атомарность/защита от гонки обеспечивается на уровне
    database.activate_user_gift (условный UPDATE + проверка rowcount).
    """
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo

    try:
        gift = database.get_gift_by_code(gift_code)
        if not gift:
            return {"ok": False, "status": "not_found", "message": "Подарок не найден или код неверный"}

        if gift.get("is_activated"):
            if int(gift.get("activated_by_user_id") or 0) == int(user_id):
                # Тот же пользователь уже активировал этот подарок — идемпотентный успех.
                return {"ok": True, "status": "already_activated", "message": "Подарок уже активирован на ваш аккаунт."}
            return {"ok": False, "status": "already_activated", "message": "Этот подарок уже был активирован"}

        expires_at = gift.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(str(expires_at)) < datetime.utcnow():
                    return {"ok": False, "status": "expired", "message": "Срок действия подарка истёк"}
            except Exception:
                pass

        success, activated_gift = database.activate_user_gift(gift_code, user_id)
        if not success:
            # Либо гонка (кто-то другой успел активировать первым), либо подарок
            # истёк/удалён между проверкой и попыткой активации — перечитываем
            # текущее состояние, чтобы дать пользователю точный ответ.
            fresh = database.get_gift_by_code(gift_code) or gift
            if fresh.get("is_activated") and int(fresh.get("activated_by_user_id") or 0) == int(user_id):
                return {"ok": True, "status": "already_activated", "message": "Подарок уже активирован на ваш аккаунт."}
            return {"ok": False, "status": "already_activated" if fresh.get("is_activated") else "error", "message": "Не удалось активировать подарок"}

        # Переназначаем ключ активирующему пользователю (используем существующий сервис,
        # не создаём новый ключ).
        key_id = gift.get("key_id")
        if key_id:
            new_email = rw_repo.generate_key_email_for_user(user_id)
            rw_repo.update_key(key_id, user_id=user_id, email=new_email, tag="")

        # Привязываем реферала от дарителя (если применимо) — используя существующую
        # бизнес-логику/условия (см. set_referred_by_from_gift).
        try:
            from_user_id = int((activated_gift or gift or {}).get("from_user_id") or 0)
            if from_user_id > 0:
                database.set_referred_by_from_gift(user_id, from_user_id)
        except Exception:
            pass

        return {"ok": True, "status": "activated", "message": "Подарок успешно активирован! Ключ добавлен в ваш профиль."}
    except Exception as e:
        logger.error(f"Gift activate error for user {user_id}, gift {gift_code}: {e}")
        return {"ok": False, "status": "error", "message": str(e)}


# ── Gift activation via webapp ─────────────────────────────────────────────
@app.post("/api/gift/activate")
async def api_gift_activate(req: GiftActivateRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])

        result = _activate_gift_for_user(user_id, req.gift_code)
        if not result["ok"]:
            return {"ok": False, "error": result["message"]}
        return {"ok": True, "message": result["message"]}
    except Exception as e:
        logger.error(f"Gift activate error: {e}")
        return {"ok": False, "error": str(e)}


# ── Referral linking (shared business logic) ────────────────────────────────
#
# Единая точка привязки реферала — используется сценарием pending action.
# Обычный бот-флоу (register_user_if_not_exists / set_referred_by_from_gift)
# не тронут и продолжает работать как раньше.
_REFERRAL_LINK_MESSAGES = {
    "linked": "Вы стали участником реферальной программы!",
    "already_linked": "У вас уже был указан реферер — эта ссылка ничего не меняет.",
    "self_referral_forbidden": "Нельзя быть рефералом самого себя.",
    "invalid_referrer": "Реферальная ссылка недействительна.",
    "not_eligible": "Не удалось применить реферальную ссылку.",
}


def _apply_pending_referral(user_id: int, referrer_id: int) -> dict:
    """Привязать пользователя к рефереру и, если применимо, выплатить
    существующий стартовый бонус рефереру (тот же механизм и те же настройки,
    что использует бот при обычной регистрации по `/start ref_<id>` —
    см. reward_type == "fixed_start_referrer" в bot/handlers.py).

    Возвращает {"ok": bool, "status": str, "message": str}, где status один из:
    linked, already_linked, self_referral_forbidden, invalid_referrer, not_eligible.
    """
    from shop_bot.data_manager import database

    status = database.link_referrer_if_eligible(user_id, referrer_id, max_age_seconds=1800)
    message = _REFERRAL_LINK_MESSAGES.get(status, "Не удалось применить реферальную ссылку.")
    ok = status == "linked"

    if ok:
        try:
            reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
        except Exception:
            reward_type = "percent_purchase"

        if reward_type == "fixed_start_referrer":
            try:
                from decimal import Decimal
                amount_raw = get_setting("referral_on_start_referrer_amount") or "20"
                start_bonus = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
            except Exception:
                start_bonus = None
            if start_bonus and start_bonus > 0:
                try:
                    if rw_repo.claim_referral_start_bonus(user_id):
                        rw_repo.add_to_referral_balance(int(referrer_id), float(start_bonus))
                        rw_repo.add_to_referral_balance_all(int(referrer_id), float(start_bonus))
                except Exception as e:
                    logger.warning(f"Referral start bonus failed for referrer {referrer_id}: {e}")

    return {"ok": ok, "status": status, "message": message}


# ── Unified pending action (gift/referral link opened before login) ────────
class PendingActionCompleteRequest(BaseModel):
    pending_token: str
    token: str | None = None
    init_data: str | None = None


def _pending_action_public_info(pending: dict) -> dict:
    """Собрать безопасный (без лишних деталей) ответ для UI по pending action —
    для GET .../info (до входа) и как основа для complete (после входа)."""
    from shop_bot.data_manager import database

    action_type = pending.get("action_type")
    now = datetime.utcnow()
    try:
        expires_at = datetime.strptime(str(pending["expires_at"]), "%Y-%m-%d %H:%M:%S")
    except Exception:
        expires_at = None

    if pending.get("consumed_at"):
        return {"ok": False, "valid": False, "action_type": action_type, "error": "already_used",
                "message": "Эта ссылка уже была использована."}
    if expires_at and expires_at < now:
        return {"ok": False, "valid": False, "action_type": action_type, "error": "expired",
                "message": "Срок действия ссылки истёк."}

    if action_type == "gift":
        gift = database.get_gift_by_code(pending.get("gift_code") or "")
        if not gift:
            return {"ok": False, "valid": False, "action_type": action_type, "error": "not_found",
                    "message": "Подарок не найден."}
        if gift.get("is_activated"):
            return {"ok": False, "valid": False, "action_type": action_type, "error": "already_activated",
                    "message": "Этот подарок уже был активирован."}
        return {
            "ok": True, "valid": True, "action_type": "gift",
            "message": "Вам доступен подарок — VPN-ключ будет активирован на ваш аккаунт после входа.",
            "host_name": gift.get("host_name"),
        }

    if action_type == "referral":
        return {
            "ok": True, "valid": True, "action_type": "referral",
            "message": "Вы переходите по приглашению в сервис — после входа/регистрации вы станете рефералом.",
        }

    return {"ok": False, "valid": False, "action_type": action_type, "error": "invalid",
            "message": "Ссылка недействительна."}


@app.get("/api/webapp/pending-actions/info")
async def api_pending_action_info(pending_token: str):
    from shop_bot.data_manager import database
    pending = database.get_pending_action(pending_token)
    if not pending:
        return {"ok": False, "valid": False, "error": "invalid", "message": "Ссылка недействительна."}
    return _pending_action_public_info(pending)


@app.post("/api/webapp/pending-actions/complete")
async def api_pending_action_complete(req: PendingActionCompleteRequest, request: Request):
    """Единая точка завершения pending action ПОСЛЕ успешной авторизации.

    Безопасность:
      - пользователь определяется ИСКЛЮЧИТЕЛЬНО через _resolve_authenticated_user
        (доверенный persistent auth-токен ИЛИ подписанные Telegram init_data) —
        `user_id` в теле запроса не принимается и не может быть подменён клиентом;
      - gift_code/referrer_id/action_type берутся только из серверной записи
        auth_pending_actions по pending_token — клиент не может их переопределить;
      - claim_pending_action атомарно "забирает" токен ровно один раз, поэтому
        параллельные/повторные запросы не могут применить действие дважды
        (см. database.claim_pending_action, database.activate_user_gift,
        database.link_referrer_if_eligible — везде решение по cursor.rowcount).
    """
    from shop_bot.data_manager import database

    data = req.model_dump()
    user = _resolve_authenticated_user(data, request)
    if not user:
        return {"ok": False, "error": "unauthorized", "message": "Требуется авторизация."}
    if user.get("is_banned"):
        return {"ok": False, "error": "access_denied", "message": "Доступ запрещён."}

    user_id = int(user["telegram_id"])

    pending = database.get_pending_action(req.pending_token)
    if not pending:
        return {"ok": False, "error": "invalid", "message": "Ссылка недействительна."}

    action_type = pending.get("action_type")

    # Уже использован именно этим пользователем ранее — идемпотентно возвращаем
    # тот же результат, не выполняя бизнес-логику повторно.
    if pending.get("consumed_at"):
        if int(pending.get("consumed_by_user_id") or 0) == user_id:
            stored_status = pending.get("result_status") or "done"
            return {
                "ok": True,
                "already_completed": True,
                "action_type": action_type,
                "status": stored_status,
                "message": "Действие уже было применено к вашему аккаунту ранее.",
            }
        return {"ok": False, "error": "already_used", "message": "Эта ссылка уже была использована."}

    # Просрочен?
    try:
        expires_at = datetime.strptime(str(pending["expires_at"]), "%Y-%m-%d %H:%M:%S")
        if expires_at < datetime.utcnow():
            return {"ok": False, "error": "expired", "message": "Срок действия ссылки истёк."}
    except Exception:
        pass

    # Атомарно "забираем" токен для этого пользователя. Если не получилось —
    # значит кто-то (или этот же клиент параллельным запросом) уже успел его
    # обработать между нашими проверками выше и этим вызовом.
    if not database.claim_pending_action(req.pending_token, user_id):
        pending_after = database.get_pending_action(req.pending_token) or {}
        if int(pending_after.get("consumed_by_user_id") or 0) == user_id:
            stored_status = pending_after.get("result_status") or "done"
            return {
                "ok": True,
                "already_completed": True,
                "action_type": action_type,
                "status": stored_status,
                "message": "Действие уже было применено к вашему аккаунту ранее.",
            }
        return {"ok": False, "error": "expired", "message": "Ссылка недействительна или уже использована."}

    if action_type == "gift":
        result = _activate_gift_for_user(user_id, pending.get("gift_code") or "")
    elif action_type == "referral":
        try:
            referrer_id = int(pending.get("referrer_id") or 0)
        except (TypeError, ValueError):
            referrer_id = 0
        result = _apply_pending_referral(user_id, referrer_id)
    else:
        result = {"ok": False, "status": "invalid", "message": "Неизвестный тип действия."}

    try:
        database.set_pending_action_result(req.pending_token, result.get("status") or ("ok" if result.get("ok") else "error"))
    except Exception:
        pass

    return {
        "ok": bool(result.get("ok")),
        "action_type": action_type,
        "status": result.get("status"),
        "message": result.get("message"),
    }

@app.post("/api/key/devices")
async def api_key_devices(req: KeyActionRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.modules import remnawave_api
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}
            
        uuid_val = key.get("remnawave_user_uuid")
        if not uuid_val:
            return {"ok": False, "error": "Ключ не имеет привязки к серверу"}
            
        host = req.host_name or key.get("host_name")
        devices_data = await remnawave_api.get_connected_devices_count(uuid_val, host_name=host)
        devices = (devices_data or {}).get("devices") or []
        return {"ok": True, "devices": devices}
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/key/device/delete")
async def api_key_device_delete(req: DeleteDeviceRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.modules import remnawave_api
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}
            
        uuid_val = key.get("remnawave_user_uuid")
        if not uuid_val:
            return {"ok": False, "error": "Ключ не имеет привязки"}
            
        host = req.host_name or key.get("host_name")
        success = await remnawave_api.delete_user_device(uuid_val, req.device_id, host_name=host)
        if success:
            return {"ok": True}
        return {"ok": False, "error": "Не удалось удалить устройство"}
    except Exception as e:
        logger.error(f"Error deleting device: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/key/comment")
async def api_key_comment(req: CommentRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.data_manager.database import update_key_comment
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}

        update_key_comment(req.key_id, req.comment)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error updating comment: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/support/status")
async def api_support_status(req: SupportStatusRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_user_tickets, get_ticket_messages
        tickets = get_user_tickets(user_id) or []
        open_tickets = [t for t in tickets if t.get('status') == 'open']
        if not open_tickets:
            return {"ok": True, "has_ticket": False}
        
        ticket = max(open_tickets, key=lambda t: int(t['ticket_id']))
        messages = get_ticket_messages(ticket['ticket_id']) or []
        
        formatted_messages = []
        for m in messages:
            if m.get('sender') == 'note':
                continue
            formatted_messages.append({
                "sender": m.get("sender"),
                "content": m.get("content"),
                "created_at": m.get("created_at")
            })
            
        return {
            "ok": True, 
            "has_ticket": True, 
            "ticket_id": ticket['ticket_id'],
            "subject": ticket.get('subject', 'Обращение без темы'),
            "status": ticket.get('status'),
            "messages": formatted_messages
        }
    except Exception as e:
        logger.error(f"Error in support status: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/support/create")
async def api_support_create(req: SupportTicketCreateRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_or_create_open_ticket, add_support_message, get_setting
        
        subject_text = req.subject.strip()[:64]
        if not subject_text:
            return {"ok": False, "error": "Тема обращения не может быть пустой"}
            
        ticket_id, created_new = get_or_create_open_ticket(user_id, subject_text)
        
        if not ticket_id:
            return {"ok": False, "error": "Не удалось создать тикет"}
            
        if not created_new:
            return {"ok": False, "error": "У вас уже есть открытый тикет"}
            
        from aiogram import Bot
        token = get_setting("support_bot_token")
        if token:
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                try:
                    tg_user = await bot.get_chat(user_id)
                    username_display = f"@{tg_user.username}" if getattr(tg_user, 'username', None) else f"ID {user_id}"
                except Exception:
                    username_display = f"ID {user_id}"
                    
                notification_text = (
                    f"🆕 <b>Новое обращение (WebApp)!</b>\n\n"
                    f"👤 <b>USER:</b> (<code>{user_id}</code> - {username_display})\n"
                    f"📝 <b>ID тикета:</b> <code>#{ticket_id}</code>\n"
                    f"💬 <b>Тема:</b> <i>{subject_text}</i>\n\n"
                    f"💌 Сообщения:\n"
                    f"<blockquote>Тикет открыт через веб-приложение.</blockquote>"
                )
                
                admin_ids_str = get_setting("admin_ids") or ""
                admin_ids = [aid.strip() for aid in admin_ids_str.split(",") if aid.strip()]
                for aid in admin_ids:
                    try:
                        await bot.send_message(
                            chat_id=int(aid),
                            text=notification_text,
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin_reply_dm_{ticket_id}")]
                            ])
                        )
                    except Exception:
                        pass
            finally:
                await bot.session.close()
                    
        return {"ok": True, "ticket_id": ticket_id}
    except Exception as e:
        logger.error(f"Error in support create: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/support/send")
async def api_support_send(req: SupportMessageSendRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        from shop_bot.data_manager.remnawave_repository import get_ticket, add_support_message, get_setting
        ticket = get_ticket(req.ticket_id)
        if not ticket or ticket.get('user_id') != user_id or ticket.get('status') != 'open':
            return {"ok": False, "error": "Тикет не найден или закрыт"}
            
        add_support_message(req.ticket_id, sender="user", content=req.message)
        
        from aiogram import Bot
        token = get_setting("support_bot_token")
        if token:
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                try:
                    tg_user = await bot.get_chat(user_id)
                    username_display = f"@{tg_user.username}" if getattr(tg_user, 'username', None) else f"ID {user_id}"
                except Exception:
                    username_display = f"ID {user_id}"
                    
                notification_text = (
                    f"📨 <b>Новое сообщение (WebApp)!</b>\n\n"
                    f"👤 <b>USER:</b> (<code>{user_id}</code> - {username_display})\n"
                    f"📝 <b>ID тикета:</b> <code>#{req.ticket_id}</code>\n"
                    f"💬 <b>Тема:</b> <i>{ticket.get('subject', 'Без темы')}</i>\n\n"
                    f"💌 Сообщения:\n"
                    f"<blockquote>{req.message}</blockquote>"
                )
                
                forum_chat_id = ticket.get('forum_chat_id')
                thread_id = ticket.get('message_thread_id')
                
                if forum_chat_id and thread_id:
                    try:
                        await bot.send_message(
                            chat_id=int(forum_chat_id),
                            message_thread_id=int(thread_id),
                            text=notification_text
                        )
                    except Exception as e:
                        logger.warning(f"Error mirroring to forum: {e}")
                else:
                    admin_ids_str = get_setting("admin_ids") or ""
                    admin_ids = [aid.strip() for aid in admin_ids_str.split(",") if aid.strip()]
                    for aid in admin_ids:
                        try:
                            await bot.send_message(
                                chat_id=int(aid),
                                text=notification_text,
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin_reply_dm_{req.ticket_id}")]
                                ])
                            )
                        except Exception:
                            pass
            finally:
                await bot.session.close()
                        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error in support send: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/api/user-status")
async def api_user_status(request: Request, token: str | None = None):
    try:
        # Prefer query token; also accept Authorization header via helper.
        user = _require_authenticated_user(request, token=token)
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
            
        keys = get_user_keys(user_id)
        # Sort keys by key_id descending to get the latest one first
        formatted_keys = []
        if keys:
            keys.sort(key=lambda k: k.get('key_id', 0), reverse=True)
            formatted_keys = [_process_key_data(k) for k in keys]
        
        return {"ok": True, "keys": formatted_keys, "balance": float(user.get("balance") or 0.0)}
    except Exception as e:
        logger.error(f"User status error: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/key/rename")
async def api_key_rename(req: RenameKeyRequest, request: Request):
    try:
        user = _resolve_user_from_request_token({"token": req.token}, request)
        if not user or user.get('is_banned'):
            return {"ok": False, "error": "Access denied"}

        user_id = user.get("telegram_id")
        from shop_bot.data_manager.remnawave_repository import get_key_by_id, update_key_name
        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}

        new_name = req.new_name.strip() if req.new_name else ""
        if new_name and len(new_name) > 30:
            return {"ok": False, "error": "Название слишком длинное (макс. 30 символов)"}

        success = update_key_name(req.key_id, new_name or None)
        if success:
            return {"ok": True}
        return {"ok": False, "error": "Не удалось обновить название"}
    except Exception as e:
        logger.error(f"Error renaming key: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/key/devices/delete-all")
async def api_key_devices_delete_all(req: DeleteAllDevicesRequest, request: Request):
    try:
        user = _resolve_user_from_request_token({"token": req.token}, request)
        if not user or user.get('is_banned'):
            return {"ok": False, "error": "Access denied"}

        user_id = user.get("telegram_id")
        from shop_bot.data_manager.remnawave_repository import get_key_by_id
        from shop_bot.modules import remnawave_api

        key = get_key_by_id(req.key_id)
        if not key or key.get("user_id") != user_id:
            return {"ok": False, "error": "Ключ не найден"}

        uuid_val = key.get("remnawave_user_uuid")
        if not uuid_val:
            return {"ok": False, "error": "Ключ не имеет привязки к серверу"}

        host = req.host_name or key.get("host_name")
        devices_data = await remnawave_api.get_connected_devices_count(uuid_val, host_name=host)
        devices = (devices_data or {}).get("devices") or []

        if not devices:
            return {"ok": True, "deleted": 0}

        deleted = 0
        for d in devices:
            device_id = d.get("hwid") if isinstance(d, dict) else str(d)
            if device_id:
                success = await remnawave_api.delete_user_device(uuid_val, device_id, host_name=host)
                if success:
                    deleted += 1

        return {"ok": True, "deleted": deleted, "total": len(devices)}
    except Exception as e:
        logger.error(f"Error deleting all devices: {e}")
        return {"ok": False, "error": str(e)}

@app.get("/api/user/transactions")
async def api_user_transactions(
    request: Request,
    page: int = 1,
    per_page: int = 10,
    token: str | None = None,
):
    try:
        user = _require_authenticated_user(request, token=token)
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])

        from shop_bot.data_manager.remnawave_repository import get_transactions_paginated
        transactions, total = get_transactions_paginated(page=page, per_page=per_page, user_id=user_id)

        safe_txs = []
        for tx in transactions:
            safe_txs.append({
                "transaction_id": tx.get("transaction_id"),
                "amount_rub": tx.get("amount_rub"),
                "payment_method": tx.get("payment_method") or "—",
                "status": tx.get("status"),
                "created_date": tx.get("created_date"),
                "action_label": tx.get("action_label") or "Оплата",
                "plan_name": tx.get("plan_name") or "—",
                "host_name": tx.get("host_name") or "—",
            })

        return {
            "ok": True,
            "transactions": safe_txs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_more": (page * per_page) < total,
        }
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        return {"ok": False, "error": str(e)}

@app.post("/api/keys/search")
async def api_keys_search(req: SearchKeysRequest, request: Request):
    try:
        user = _resolve_user_from_request_token({"token": req.token}, request)
        if not user or user.get('is_banned'):
            return {"ok": False, "error": "Access denied"}

        user_id = user.get("telegram_id")
        from shop_bot.data_manager.remnawave_repository import search_user_keys_by_email
        q = (req.query or "").strip()
        if not q:
            return {"ok": False, "error": "Запрос поиска пустой"}
        if len(q) < 2:
            return {"ok": False, "error": "Минимум 2 символа для поиска"}

        keys = search_user_keys_by_email(user_id, q)
        found_keys = keys[:20]
        # Reuse the same card renderer as the main "Мои ключи" list so search
        # results get full parity: same buttons, same onclick wiring (extend,
        # rename, comment, devices, auto-renew, copy link, etc.).
        html = _get_profile_keys_html(found_keys) if found_keys else ""

        return {"ok": True, "html": html, "total": len(found_keys)}
    except Exception as e:
        logger.error(f"Error searching keys: {e}")
        return {"ok": False, "error": str(e)}

def _html_esc(value) -> str:
    """Экранировать значение для вставки в HTML-текст или атрибут (CWE-79)."""
    return html.escape("" if value is None else str(value), quote=True)


_PUBLIC_FALLBACK_CSP = (
    "default-src 'none'; "
    "img-src 'self' https: data:; "
    "style-src 'unsafe-inline'; "
    "script-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'"
)
_GIFT_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _public_fallback_response(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=content,
        status_code=status_code,
        headers={"Content-Security-Policy": _PUBLIC_FALLBACK_CSP},
    )


def _parse_public_referrer_id(referrer_id: str) -> int | None:
    """Только положительный int. Невалидный path не должен попадать в HTML/URL."""
    try:
        rid = int(str(referrer_id).strip())
    except (TypeError, ValueError):
        return None
    if rid <= 0:
        return None
    return rid


def _safe_public_gift_code(gift_code: str | None) -> str | None:
    raw = (gift_code or "").strip()
    if _GIFT_CODE_RE.fullmatch(raw):
        return raw
    return None


def _telegram_bot_deeplink(bot_username: str, start_payload: str | None = None) -> str:
    user = (bot_username or "").strip()
    if not user:
        return ""
    if start_payload:
        return f"https://t.me/{user}?start={start_payload}"
    return f"https://t.me/{user}"


def _html_telegram_btn(deeplink: str, label: str) -> str:
    if not deeplink:
        return ""
    return f"<a class='btn' href='{_html_esc(deeplink)}'>{_html_esc(label)}</a>"


def _referral_fallback_html(project_name: str, logo_url: str, deeplink: str, error_note: str = "") -> str:
    """Резервная страница рефссылки (реферер не найден/бот не настроен) —
    без единого сценария pending action, просто ссылка в Telegram, как раньше."""
    name = _html_esc(project_name)
    note = _html_esc(
        error_note or "Вас пригласили воспользоваться VPN-сервисом. Нажмите кнопку ниже, чтобы начать через Telegram."
    )
    logo = _html_esc(logo_url) if logo_url else ""
    logo_html = f"<img class='logo' src='{logo}' alt='logo'>" if logo else ""
    if deeplink and not error_note:
        action_html = _html_telegram_btn(deeplink, "Открыть в Telegram")
    elif error_note and not deeplink:
        action_html = "<p style='color:#f87171'>Бот не настроен.</p>"
    else:
        action_html = ""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Реферальная ссылка</title>
<style>body{{margin:0;background:#0d0d0d;color:#fff;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#1a1a1a;border:1px solid rgba(255,255,255,.08);border-radius:2rem;padding:2.5rem;max-width:360px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
h2{{margin:.5rem 0 .25rem;font-size:1.3rem}} p{{color:#aaa;font-size:.85rem;margin:.75rem 0 1.5rem}}
.btn{{display:block;background:#fff;color:#000;font-weight:700;text-decoration:none;padding:.9rem 1.5rem;border-radius:1rem;font-size:.875rem;text-transform:uppercase;letter-spacing:.05em;transition:.2s}}
.btn:hover{{opacity:.85}} img.logo{{width:72px;height:72px;border-radius:1rem;margin-bottom:1rem;object-fit:contain}}</style></head>
<body><div class="card">
{logo_html}
<h2>{name}</h2>
<p>{note}</p>
{action_html}
</div></body></html>"""


@app.get("/ref/{referrer_id}")
async def web_referral_page(referrer_id: str, request: Request):
    """Публичная реферальная ссылка.

    Раньше эта страница всегда вела только в Telegram (deep link), даже если
    пользователь предпочёл бы войти по email. Теперь: если referrer_id
    настоящий, создаём серверный pending action (единый сценарий — см.
    /api/webapp/pending-actions/*) и ведём на общий вход, где пользователь сам
    выбирает Telegram или email; после успешного входа привязка реферала
    применяется автоматически ровно один раз.
    """
    try:
        bot_username = get_setting("telegram_bot_username") or ""
        webapp_settings = get_webapp_settings()
        project_name = (
            webapp_settings.get("webapp_title")
            or webapp_settings.get("project_name")
            or get_setting("panel_brand_title")
            or "VPN Bot"
        )
        logo_url = webapp_settings.get("webapp_logo") or ""

        rid = _parse_public_referrer_id(referrer_id)
        if rid is None:
            # Невалидный path не отражаем в HTML/deeplink (CWE-79).
            deeplink = _telegram_bot_deeplink(bot_username)
            return _public_fallback_response(
                _referral_fallback_html(project_name, logo_url, deeplink)
            )

        deeplink = _telegram_bot_deeplink(bot_username, f"ref_{rid}")
        # Не проверяем существование telegram_id здесь: разный статус/pending_token
        # для известного и неизвестного id даёт оракул. Привязка реферера
        # валидируется позже в complete (invalid_referrer).
        from shop_bot.data_manager import database
        token = database.create_pending_action("referral", referrer_id=rid)
        if not token:
            return _public_fallback_response(
                _referral_fallback_html(project_name, logo_url, deeplink)
            )

        return RedirectResponse(url=f"/?pending_token={token}", status_code=302)
    except Exception as e:
        logger.error(f"Referral page error: {e}")
        return _public_fallback_response("<h1>Error</h1>", status_code=500)

def _gift_fallback_html(project_name: str, logo_url: str, title: str, desc: str, action_html: str = "") -> str:
    """Резервная страница подарка (не найден/уже активирован) — как и раньше,
    без pending action, потому что действие в этих случаях всё равно не имеет смысла."""
    name = _html_esc(project_name)
    safe_title = _html_esc(title)
    safe_desc = _html_esc(desc)
    logo = _html_esc(logo_url) if logo_url else ""
    logo_html = f"<img class='logo' src='{logo}' alt='logo'>" if logo else "<div class='gift-icon'>🎁</div>"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — {safe_title}</title>
<style>body{{margin:0;background:#0d0d0d;color:#fff;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#1a1a1a;border:1px solid rgba(255,255,255,.08);border-radius:2rem;padding:2.5rem;max-width:360px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
h2{{margin:.5rem 0 .25rem;font-size:1.3rem}} p{{color:#aaa;font-size:.85rem;margin:.75rem 0 1.5rem}}
.btn{{display:inline-block;background:#fff;color:#000;font-weight:700;text-decoration:none;padding:.9rem 1.5rem;border-radius:1rem;font-size:.875rem;text-transform:uppercase;letter-spacing:.05em;transition:.2s;cursor:pointer;border:none;width:100%;box-sizing:border-box}}
.btn:hover{{opacity:.85}} img.logo{{width:72px;height:72px;border-radius:1rem;margin-bottom:1rem;object-fit:contain}}
.gift-icon{{font-size:3rem;margin-bottom:.5rem}}</style></head>
<body><div class="card">
{logo_html}
<h2>{safe_title}</h2>
<p>{safe_desc}</p>
{action_html}
</div></body></html>"""


@app.get("/gift/{gift_code}")
async def web_gift_page(gift_code: str, request: Request):
    """Публичная ссылка активации подарка.

    Раньше уже авторизованный (по cookie/`?token=`) посетитель мог активировать
    подарок прямо со страницы, а неавторизованный — только через Telegram deep
    link. Теперь для валидного, ещё не активированного подарка мы создаём
    серверный pending action и ведём на единый вход (Telegram ИЛИ email);
    страница активации внутри приложения (`/?pending_token=...`) сама решает,
    показывать ли экран входа или сразу применить действие — в зависимости от
    того, авторизован ли пользователь.
    Невалидные случаи (подарок не найден / уже активирован) обрабатываются как
    раньше — без создания pending action, отдельной простой страницей.
    """
    try:
        from shop_bot.data_manager.remnawave_repository import get_gift_by_code
        bot_username = get_setting("telegram_bot_username") or ""
        webapp_settings = get_webapp_settings()
        project_name = (
            webapp_settings.get("webapp_title")
            or webapp_settings.get("project_name")
            or get_setting("panel_brand_title")
            or "VPN Bot"
        )
        logo_url = webapp_settings.get("webapp_logo") or ""

        safe_code = _safe_public_gift_code(gift_code)
        gift = get_gift_by_code(safe_code) if safe_code else None
        if bot_username and safe_code:
            deeplink = _telegram_bot_deeplink(bot_username, f"gift_{safe_code}")
        else:
            deeplink = _telegram_bot_deeplink(bot_username)

        if not gift:
            action_html = _html_telegram_btn(deeplink, "Открыть в Telegram")
            return _public_fallback_response(_gift_fallback_html(
                project_name, logo_url, "Подарочный ключ", "Активируйте подарок через Telegram.", action_html
            ))
        if gift.get("is_activated"):
            return _public_fallback_response(_gift_fallback_html(
                project_name, logo_url, "Подарок уже активирован", "Этот подарочный ключ уже был использован."
            ))

        expires_at = gift.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(str(expires_at)) < datetime.utcnow():
                    return _public_fallback_response(_gift_fallback_html(
                        project_name, logo_url, "Срок действия истёк", "Срок действия этого подарка истёк."
                    ))
            except Exception:
                pass

        from shop_bot.data_manager import database
        token = database.create_pending_action("gift", gift_code=safe_code)
        if not token:
            action_html = _html_telegram_btn(deeplink, "Активировать в Telegram")
            return _public_fallback_response(_gift_fallback_html(
                project_name, logo_url, "Подарочный VPN-ключ",
                "Нажмите кнопку ниже, чтобы активировать подарок в Telegram.", action_html
            ))

        return RedirectResponse(url=f"/?pending_token={token}", status_code=302)
    except Exception as e:
        logger.error(f"Gift page error: {e}")
        return _public_fallback_response("<h1>Error</h1>", status_code=500)

@app.get("/{path_param}")
async def dynamic_route(request: Request, path_param: str):
    try:
        if path_param.startswith("token="):
            token = path_param.split("=")[1]
            from shop_bot.data_manager import database
            user = database.get_user_by_auth_token(token)
            if user:
                webapp_settings = get_webapp_settings()
                if user.get('is_banned'):
                    return _render_banned_page(webapp_settings)
                return await _render_main_page(user['telegram_id'])
            else:
                 # Token not valid or expired -> Render Login Page
                 p = os.path.join(os.path.dirname(__file__), "login.html")
                 if os.path.exists(p):
                     with open(p, "r", encoding="utf-8") as f:
                         content = f.read()
                     
                     webapp_settings = get_webapp_settings()
                     context = {
                        "webapp_logo": webapp_settings.get("webapp_logo") or "",
                        "webapp_icon": webapp_settings.get("webapp_icon") or ""
                     }
                     content = _process_template_placeholders(content, 0, webapp_settings, context)
                     return HTMLResponse(content=content)
                 else:
                     return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)
        
        # Pass through to 404 naturally or handle other dynamic routes
        return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)
    except Exception as e:
        logger.error(f"Dynamic route error: {e}")
        return HTMLResponse(content="<h1>Error</h1>", status_code=500)
