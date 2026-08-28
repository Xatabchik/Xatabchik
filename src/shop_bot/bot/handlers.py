import logging
import os
import uuid
import math
import qrcode
import aiohttp
import re
import hashlib
import json
import base64
import asyncio
import time

from html import escape as html_escape

from urllib.parse import urlencode, quote
from hmac import compare_digest
from functools import wraps
from io import BytesIO
from yookassa import Payment, Configuration
from datetime import datetime, timedelta, timezone
from aiosend import CryptoPay, TESTNET
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from pytonconnect import TonConnect
from .callback_safety import fast_callback_answer, catch_callback_errors, handle_unknown_callback
from aiogram import Router, F, Bot, types, html
from aiogram.types import BufferedInputFile, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    add_to_balance,
    deduct_from_balance,
    get_setting,
    get_user,
    register_user_if_not_exists,
    get_next_key_number,
    create_payload_pending,
    cancel_pending_transaction,
    claim_processed_payment,
    unclaim_processed_payment,
    refund_payment_once,
    reset_pending_transaction,
    get_pending_status,
    get_pending_metadata,
    find_and_complete_pending_transaction,
    get_user_keys,
    get_balance,
    get_referral_count,
    get_plan_by_id,
    get_all_hosts,
    get_plans_for_host,
    get_active_plans_for_host,
    redeem_promo_code,
    reserve_promo_code,
    PromoUnavailableError,
    check_promo_code_available,
    promo_error_message,
    update_promo_code_status,
    record_key_from_payload,
    add_to_referral_balance_all,
    add_to_referral_balance,
    deduct_from_referral_balance,
    get_referral_balance_all,
    get_referral_balance,
    list_referral_payout_methods,
    add_referral_payout_method,
    delete_referral_payout_method,
    get_referral_payout_method,
    create_referral_withdrawal_request,
    list_referral_withdrawal_requests,
    get_referral_top_rich,
    get_referral_rank_and_count,
    get_all_users,
    set_terms_agreed,
    claim_referral_start_bonus,
    set_referral_trial_day_bonus_received,
    set_trial_used,
    set_key_auto_renew,
    set_all_keys_auto_renew_for_user,
    update_user_stats,
    log_transaction,
    is_admin,
)

from shop_bot.config import (
    get_profile_text,
    get_vpn_active_text,
    VPN_INACTIVE_TEXT,
    VPN_NO_DATA_TEXT,
    get_key_info_text,
    CHOOSE_PAYMENT_METHOD_MESSAGE,
    get_purchase_success_text
)
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.data_manager.captcha_utils import (
    create_captcha_challenge,
    check_captcha_answer,
    get_active_captcha_challenge,
    has_passed_captcha,
    mark_user_passed_captcha,
)
from shop_bot.factory_bot.runtime import get_service
from shop_bot.modules import remnawave_api
from shop_bot.data_manager.database import get_latest_pending_for_user, get_user_by_username
from shop_bot.data_manager.database import delete_key_by_id
from shop_bot.data_manager.database import _get_pending_metadata
from shop_bot.data_manager.database import get_franchise_min_withdraw, get_franchise_percent_default
from shop_bot.data_manager.database import log_utm_visit, set_user_utm_slug_if_absent

TELEGRAM_BOT_USERNAME = None
PAYMENT_METHODS = None

def _is_true(value) -> bool:
    return str(value).strip().lower() in ('true','1','on','yes','y')

def _get_payment_methods() -> dict:
    """Собирает доступные способы оплаты из актуальных настроек (без перезапуска бота)."""
    yookassa_shop_id = get_setting('yookassa_shop_id')
    yookassa_secret_key = get_setting('yookassa_secret_key')
    yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)

    cryptobot_token = get_setting('cryptobot_token')
    cryptobot_enabled = bool(cryptobot_token)

    heleket_shop_id = get_setting('heleket_merchant_id')
    heleket_api_key = get_setting('heleket_api_key')
    heleket_enabled = bool(heleket_shop_id and heleket_api_key)

    platega_merchant_id = get_setting('platega_merchant_id')
    platega_secret = get_setting('platega_secret')
    platega_enabled = bool(platega_merchant_id and platega_secret)

    rollypay_enabled = bool(
        (get_setting('rollypay_api_key') or '').strip()
        and (get_setting('rollypay_signing_secret') or '').strip()
    )

    ton_wallet_address = get_setting('ton_wallet_address')
    tonapi_key = get_setting('tonapi_key')
    tonconnect_enabled = bool(ton_wallet_address and tonapi_key)

    yoomoney_raw = get_setting('yoomoney_enabled')
    yoomoney_wallet = get_setting('yoomoney_wallet')
    yoomoney_secret = get_setting('yoomoney_secret')
    if yoomoney_raw is None:
        yoomoney_enabled = bool(yoomoney_wallet and yoomoney_secret)
    else:
        yoomoney_enabled = _is_true(yoomoney_raw)

    stars_flag = _is_true(get_setting('stars_enabled') or 'false')
    try:
        stars_ratio = float(get_setting('stars_per_rub') or '0')
    except Exception:
        stars_ratio = 0.0
    stars_enabled = stars_flag and (stars_ratio > 0)

    return {
        'yookassa': yookassa_enabled,
        'heleket': heleket_enabled,
        'platega': platega_enabled,
        'rollypay': rollypay_enabled,
        'cryptobot': cryptobot_enabled,
        'tonconnect': tonconnect_enabled,
        'yoomoney': yoomoney_enabled,
        'stars': stars_enabled,
    }

ADMIN_ID = None
CRYPTO_BOT_TOKEN = get_setting("cryptobot_token")

PENDING_GIFTS: dict[int, dict] = {}
logger = logging.getLogger(__name__)

errors = {
    "A019": "username уже занят",
    "400": "неверные данные",
    "404": "ресурс не найден",
}


def _classify_key_creation_error(exc: Exception | None) -> tuple[str, str, str]:
    raw = str(exc) if exc else ""
    status = None
    detail = raw
    try:
        m = re.search(r"request failed:\s*(\d+)\s*(.*)", raw, flags=re.IGNORECASE)
        if m:
            status = m.group(1)
            detail = (m.group(2) or "").strip() or raw
    except Exception:
        pass

    detail_l = (detail or "").lower()
    if "username" in detail_l and any(word in detail_l for word in ("already", "exists", "occupied", "taken", "занят")):
        code = "A019"
    elif status in errors:
        code = status
    else:
        code = status or "400"
    description = errors.get(code, "неизвестная ошибка")
    short_detail = (detail or "").strip()
    if len(short_detail) > 200:
        short_detail = short_detail[:200] + "..."
    return code, description, short_detail


def _format_key_action_label(action: str | None, *, price: float | None = None, key_id: int | None = None) -> str:
    action_s = (action or "").strip().lower()
    if action_s == "new":
        return f"покупка тарифа {price:.0f} RUB" if price is not None else "покупка тарифа"
    if action_s == "extend":
        if price is not None:
            return f"продление ключа #{key_id or '—'} ({price:.0f} RUB)"
        return f"продление ключа #{key_id or '—'}"
    if action_s == "trial":
        return "пробный ключ"
    if action_s == "gift":
        return f"подарочный ключ {price:.0f} RUB" if price is not None else "подарочный ключ"
    return action or "операция"


def _log_key_creation_error(user_id: int, action_label: str, code: str, detail: str) -> None:
    ts = datetime.utcnow().isoformat()
    logger.error(
        "Key creation error: time=%s user_id=%s action=%s code=%s detail=%s",
        ts,
        user_id,
        action_label,
        code,
        detail,
    )


async def _notify_admins_key_creation_error(
    bot: Bot,
    *,
    user_id: int,
    code: str,
    description: str,
    action_label: str,
) -> None:
    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    if not admin_ids:
        return
    text = (
        "🚨 Ошибка создания ключа\n"
        f"👤 ID: {user_id}\n"
        f"🔢 Код: {code}\n"
        f"📝 Описание: {description}\n"
        f"📋 Действие: {action_label}"
    )
    for aid in admin_ids:
        try:
            await bot.send_message(int(aid), text)
        except Exception:
            continue


async def _notify_user_key_creation_error(
    bot: Bot,
    *,
    user_id: int,
    code: str,
    refund: bool = True,
    factory_bot_id: int = 0,
) -> None:
    lines = ["❌ Не удалось создать ключ."]
    if refund:
        lines.append("Средства возвращены на ваш баланс в боте.")
    lines.append(f"Код ошибки: {code}")
    lines.append("Попробуй позже или напиши в поддержку.")
    text = "\n".join(lines)
    markup = keyboards.create_support_keyboard()
    # Franchise users may only have started the clone bot — try it first.
    if factory_bot_id > 0:
        try:
            info = rw_repo.get_managed_bot(factory_bot_id)
            token = (info or {}).get("token")
            if token:
                tmp = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
                try:
                    await tmp.send_message(chat_id=user_id, text=text, reply_markup=markup)
                    return
                except Exception:
                    pass
                finally:
                    try:
                        await tmp.close()
                    except Exception:
                        pass
        except Exception:
            pass
    try:
        await bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
    except Exception:
        pass


async def _handle_key_creation_failure(
    bot: Bot,
    *,
    user_id: int,
    action_label: str,
    exc: Exception | None,
    refund: bool = True,
    factory_bot_id: int = 0,
) -> None:
    code, description, detail = _classify_key_creation_error(exc)
    _log_key_creation_error(user_id, action_label, code, detail)
    await _notify_user_key_creation_error(bot, user_id=user_id, code=code, refund=refund, factory_bot_id=factory_bot_id)
    await _notify_admins_key_creation_error(
        bot,
        user_id=user_id,
        code=code,
        description=description,
        action_label=action_label,
    )


async def _abort_topup_fulfillment(
    bot: Bot,
    *,
    payment_id: str,
    user_id: int,
    price: float,
    payment_method: str | None,
    action_label: str,
    reason: str,
) -> bool:
    """Компенсирующая транзакция при сбое применения оплаченной докупки трафика.

    Аналог `_abort_key_fulfillment` для докупки ГБ/LTE (там сообщения про создание ключа
    неуместны). Раньше эти ветви просто писали пользователю «не удалось применить» и
    выходили: платёж оставался помеченным в `processed_payments`, повторная доставка
    вебхука отбрасывалась, автовозврата не было — деньги списаны, услуга не оказана.

    1) снимает idempotency-lock (чтобы ретрай вебхука мог применить докупку заново),
    2) один раз возвращает средства (Balance / ReferralBalance / внешние → баланс),
    3) уведомляет пользователя и админов.

    Возвращает True, если refund реально зачислен (первичный вызов).
    """
    try:
        rw_repo.unclaim_processed_payment(payment_id)
        rw_repo.reset_pending_transaction(payment_id)
    except Exception:
        pass

    did_refund = False
    if price and float(price) > 0:
        try:
            did_refund = bool(
                refund_payment_once(payment_id, int(user_id), float(price), payment_method)
            )
        except Exception:
            did_refund = False

    logger.error(
        "TOPUP_ROLLBACK payment_id=%s user_id=%s amount=%s method=%s action=%s reason=%s refunded=%s",
        payment_id,
        user_id,
        price,
        payment_method,
        action_label,
        reason,
        did_refund,
    )

    lines = ["⚠️ Оплата получена, но применить докупку не удалось."]
    if did_refund:
        lines.append("Средства возвращены на ваш баланс в боте — попробуйте ещё раз.")
    else:
        lines.append("Платёж не потерян: обратитесь в поддержку, мы применим докупку вручную.")
    try:
        await bot.send_message(
            chat_id=user_id,
            text="\n".join(lines),
            reply_markup=keyboards.create_support_keyboard(),
        )
    except Exception:
        pass

    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    admin_text = (
        "🚨 Не удалось применить оплаченную докупку\n"
        f"👤 ID: {user_id}\n"
        f"📋 Действие: {action_label}\n"
        f"🧾 payment_id: {payment_id}\n"
        f"💰 Сумма: {price}\n"
        f"🔢 Причина: {reason}\n"
        f"↩️ Возврат: {'да' if did_refund else 'нет'}"
    )
    for aid in admin_ids:
        try:
            await bot.send_message(int(aid), admin_text)
        except Exception:
            continue
    return did_refund


async def _notify_admins_topup_desync(
    bot: Bot,
    *,
    user_id: int,
    action_label: str,
    payment_id: str,
    detail: str,
) -> None:
    """Докупка применена на VPN-сервере, но не сохранилась в БД бота.

    Возврат средств здесь недопустим (услуга фактически оказана), но расхождение нужно
    починить вручную: локальный `traffic_boost_bytes` используется при ежемесячном сбросе
    лимита, и без него бот вернёт ключ к базовому лимиту тарифа.
    """
    logger.error(
        "TOPUP_DB_DESYNC user_id=%s action=%s payment_id=%s detail=%s",
        user_id,
        action_label,
        payment_id,
        detail,
    )
    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    text = (
        "🚨 Докупка применена на сервере, но не записана в БД бота\n"
        f"👤 ID: {user_id}\n"
        f"📋 Действие: {action_label}\n"
        f"🧾 payment_id: {payment_id}\n"
        f"📝 Детали: {detail}\n"
        "Требуется ручная сверка лимита ключа."
    )
    for aid in admin_ids:
        try:
            await bot.send_message(int(aid), text)
        except Exception:
            continue


async def _abort_key_fulfillment(
    bot: Bot,
    *,
    payment_id: str,
    user_id: int,
    price: float,
    payment_method: str | None,
    action_label: str,
    exc: Exception | None,
    factory_bot_id: int = 0,
    processing_message=None,
    fail_text: str = "❌ Не удалось создать ключ.",
) -> bool:
    """Компенсирующая транзакция при сбое выдачи ключа после оплаты.

    1) снимает idempotency-lock (webhook может ретраить),
    2) один раз возвращает средства (Balance / ReferralBalance / внешние → баланс),
    3) уведомляет пользователя и админов.

    Возвращает True, если refund реально зачислен (первичный вызов).
    """
    try:
        rw_repo.unclaim_processed_payment(payment_id)
        rw_repo.reset_pending_transaction(payment_id)
    except Exception:
        pass

    did_refund = False
    if price and float(price) > 0:
        try:
            did_refund = bool(
                refund_payment_once(payment_id, int(user_id), float(price), payment_method)
            )
        except Exception:
            did_refund = False
        if did_refund:
            logger.error(
                "PAYMENT_ROLLBACK payment_id=%s user_id=%s amount=%.2f method=%s error=%s",
                payment_id,
                user_id,
                float(price),
                payment_method,
                exc,
            )

    await _handle_key_creation_failure(
        bot,
        user_id=user_id,
        action_label=action_label,
        exc=exc,
        refund=did_refund,
        factory_bot_id=factory_bot_id,
    )
    if processing_message is not None:
        try:
            await processing_message.edit_text(fail_text)
        except Exception:
            pass
    return did_refund

async def _safe_edit_or_answer(message: types.Message, text: str, **kwargs) -> None:
    """Заменить `message.edit_text(...)` там, где предыдущее сообщение может
    оказаться нетекстовым (счёт на оплату Stars/ЮKassa, фото рассылки и т.п.) —
    у таких сообщений нет текста для редактирования, и Telegram отвечает
    `Bad Request: there is no text in the message to edit`. В этом случае
    вместо падения хендлера отправляем новое сообщение с тем же контентом.
    """
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest:
        try:
            await message.answer(text, **kwargs)
        except TelegramBadRequest:
            pass


def _format_duration_label(months: int | None, duration_days: int | None) -> str:
    try:
        dd = int(duration_days or 0)
    except Exception:
        dd = 0
    if dd and dd > 0:
        return f"{dd} дн."
    try:
        mm = int(months or 0)
    except Exception:
        mm = 0
    return f"{mm} мес." if mm else "—"


def _compute_days_to_add(months: int | None, duration_days: int | None) -> int:
    try:
        dd = int(duration_days or 0)
    except Exception:
        dd = 0
    if dd and dd > 0:
        return dd
    try:
        mm = int(months or 0)
    except Exception:
        mm = 0
    return int(mm * 30)


def _tariff_label_from_origin(*, is_trial: bool, months: int | None, duration_days: int | None) -> str:
    """Human label for subscription page tariff line.

    Requirement: show "30 дней" depending on how the key was obtained.
    """
    if is_trial:
        return "триал"
    days = _compute_days_to_add(months, duration_days)
    if days and days > 0:
        return f"{days} дней"
    return "—"


def _build_key_origin_meta(
    *,
    source: str,
    plan_id: int | None,
    plan_name: str | None,
    months: int | None,
    duration_days: int | None,
    is_trial: bool = False,
    note: str | None = None,
) -> str:
    """Store key origin info inside vpn_keys.description as JSON.

    We use this later to correctly render "🕒 Тариф:" even if host plans change.
    """
    label = _tariff_label_from_origin(is_trial=is_trial, months=months, duration_days=duration_days)
    payload = {
        "v": 1,
        "source": source,
        "is_trial": bool(is_trial),
        "plan_id": int(plan_id) if plan_id else None,
        "plan_name": plan_name or None,
        "months": int(months or 0),
        "duration_days": int(duration_days or 0),
        "tariff_label": label,
    }
    if note:
        payload["note"] = str(note)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


async def grant_referrer_day_bonus_for_trial(*, referred_user_id: int, bot: Bot) -> None:
    """Начислить рефереру +1 день только в момент активации триала рефералом."""
    try:
        referred_user_id_i = int(referred_user_id or 0)
    except Exception:
        return
    if not referred_user_id_i:
        return

    try:
        user_data = get_user(referred_user_id_i) or {}
    except Exception:
        user_data = {}

    referrer_id = user_data.get("referred_by")
    if not referrer_id:
        return

    # чтобы не начислять дважды
    if user_data.get("referral_trial_day_bonus_received"):
        return

    # глобальный тумблер (оставляем для обратной совместимости)
    try:
        enabled = (get_setting("enable_referral_days_bonus") or "false").strip().lower() == "true"
    except Exception:
        enabled = False
    if not enabled:
        return

    try:
        referrer_id_i = int(referrer_id)
    except Exception:
        return
    if referrer_id_i <= 0 or referrer_id_i == referred_user_id_i:
        return

    # выбираем ключ реферера для продления: активный с максимальным сроком, иначе самый дальний
    ref_keys = []
    try:
        ref_keys = get_user_keys(referrer_id_i) or []
    except Exception:
        ref_keys = []

    now_utc = datetime.now(timezone.utc)

    def _parse_exp_dt(v) -> datetime | None:
        if not v:
            return None
        s = str(v).strip()
        if not s:
            return None
        try:
            # нормализуем ISO
            ss = s.replace("Z", "+00:00")
            if " " in ss and "T" not in ss:
                ss = ss.replace(" ", "T", 1)
            dt = datetime.fromisoformat(ss)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            # запасной парсер
            formats = [
                ("%Y-%m-%d %H:%M:%S", 19),
                ("%Y-%m-%d %H:%M", 16),
                ("%Y-%m-%d", 10),
            ]
            for fmt, n in formats:
                try:
                    dt = datetime.strptime(s[:n], fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
        return None

    scored = []
    for k in ref_keys:
        exp_dt = _parse_exp_dt(k.get("expiry_date") or k.get("expire_at"))
        if exp_dt:
            scored.append((exp_dt, k))

    active = [pair for pair in scored if pair[0] > now_utc]
    chosen = None
    if active:
        chosen = max(active, key=lambda x: x[0])[1]
    elif scored:
        chosen = max(scored, key=lambda x: x[0])[1]

    # host для бонуса
    bonus_host = None
    if chosen and chosen.get("host_name"):
        bonus_host = chosen.get("host_name")
    if not bonus_host:
        bonus_host = get_setting("referral_days_bonus_host") or None
    if not bonus_host:
        hosts = get_all_hosts() or []
        if hosts:
            bonus_host = hosts[0].get("host_name")
    if not bonus_host:
        return

    target_email = None
    if chosen:
        target_email = chosen.get("key_email") or chosen.get("email")
    if not target_email:
        target_email = f"tg{referrer_id_i}+trialref{int(now_utc.timestamp())}@ref.local"

    try:
        result = await remnawave_api.create_or_update_key_on_host(
            host_name=str(bonus_host),
            email=str(target_email),
            days_to_add=1,
            description="Бонус за активацию триала рефералом (+1 день)",
        )
    except Exception:
        result = None

    if not result:
        return

    try:
        record_key_from_payload(
            user_id=referrer_id_i,
            payload=result,
            host_name=str(bonus_host),
            description="Referral trial bonus +1 day",
        )
    except Exception:
        pass

    try:
        set_referral_trial_day_bonus_received(referred_user_id_i)
    except Exception:
        pass

    try:
        await bot.send_message(referrer_id_i, "🎁 Вам начислен бонус: +1 день к подписке за то, что ваш реферал активировал триал.")
    except Exception:
        pass


def _webapp_public_base() -> str | None:
    """Публичный базовый URL Mini App, если webapp включён и задан домен.

    В настройках домен хранится без схемы (app.example.com) — для ссылок,
    которыми делятся из бота, добавляем https://.
    """
    settings = database.get_webapp_settings()
    if not settings.get("webapp_enabled"):
        return None
    domain = (settings.get("webapp_domain") or "").strip().rstrip("/")
    if not domain:
        return None
    if not domain.startswith(("http://", "https://")):
        domain = f"https://{domain}"
    return domain


def _build_gift_links(gift_code: str) -> tuple[str | None, str | None]:
    """Построить обе ссылки активации подарка: в мини-приложении (webapp) и в Telegram.

    Возвращает (webapp_link, telegram_link) — то же самое, что показывает
    веб-приложение на своей странице подарков.
    """
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")
    webapp_link = f"{webapp_domain}/gift/{gift_code}" if webapp_domain else None
    telegram_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=gift_{gift_code}" if TELEGRAM_BOT_USERNAME else None
    return webapp_link, telegram_link


def _build_referral_links(user_id: int, bot_username: str | None = None) -> tuple[str | None, str | None]:
    """Построить реферальные ссылки: (webapp_link, telegram_link).

    Веб-ссылка возвращается только если Mini App включён в настройках
    и задан webapp_domain — иначе None.
    """
    username = (bot_username or TELEGRAM_BOT_USERNAME or get_setting("telegram_bot_username") or "").strip()
    telegram_link = f"https://t.me/{username}?start=ref_{int(user_id)}" if username else None
    base = _webapp_public_base()
    webapp_link = f"{base}/ref/{int(user_id)}" if base else None
    return webapp_link, telegram_link


DEFAULT_REFERRAL_SHARE_TEXT = "🌐Обход глушилок и блокировок на любом устройстве! 😊"
DEFAULT_GIFT_SHARE_TEXT = "🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать"


def _referral_share_text() -> str:
    """Текст для t.me/share из настроек (Контент → referral_share_text)."""
    raw = (get_setting("referral_share_text") or "").strip()
    return raw or DEFAULT_REFERRAL_SHARE_TEXT


def _gift_share_text() -> str:
    """Текст для t.me/share при шаринге подарка (Контент → gift_share_text)."""
    raw = (get_setting("gift_share_text") or "").strip()
    return raw or DEFAULT_GIFT_SHARE_TEXT


def _telegram_share_url(url: str, text: str) -> str:
    """Собрать https://t.me/share/url?... с пробелами как %20 (не +).

    Telegram подставляет text в поле ввода как есть; quote_plus даёт «+»
    вместо пробелов, и они остаются плюсами в черновике сообщения.
    """
    return "https://t.me/share/url?" + urlencode(
        {"url": url, "text": text},
        quote_via=quote,
    )


async def _activate_gift_directly(
    message: types.Message, bot: Bot, user_id: int, gift_code: str,
    *, is_new_user: bool = False
) -> None:
    """Активировать подарок для пользователя."""
    try:
        gift = rw_repo.get_gift_by_code(gift_code)
        if not gift:
            await message.answer(
                "❌ Подарок не найден. Возможно, срок его действия истёк или код неверный.",
                reply_markup=keyboards.main_reply_keyboard
            )
            return
        
        if gift.get('is_activated'):
            await message.answer(
                "⚠️ Этот подарок уже был активирован.",
                reply_markup=keyboards.main_reply_keyboard
            )
            return
        
        # Активируем подарок
        success, activated_gift = rw_repo.activate_user_gift(gift_code, user_id)
        if not success:
            await message.answer(
                "❌ Не удалось активировать подарок. Попробуйте позже.",
                reply_markup=keyboards.main_reply_keyboard
            )
            return

        # Привязываем нового пользователя к отправителю подарка как реферала
        if is_new_user:
            try:
                from_user_id = int((activated_gift or gift or {}).get("from_user_id") or 0)
                if from_user_id > 0:
                    rw_repo.set_referred_by_from_gift(user_id, from_user_id)
            except Exception:
                pass
        
        # Получаем информацию о ключе
        key_id = gift.get('key_id')
        if key_id:
            key_data = rw_repo.get_key_by_id(key_id)
            if key_data:
                # Переассоциируем ключ на нового пользователя
                try:
                    # Генерируем новый email для пользователя
                    new_email = rw_repo.generate_key_email_for_user(user_id)
                    
                    # Обновляем ключ в БД
                    rw_repo.update_key(
                        key_id,
                        user_id=user_id,
                        email=new_email,
                        tag="",  # Убираем тег "user_gift" чтобы ключ появился в списке ключей
                    )
                    
                    success_msg = (
                        "🎁 <b>Подарок успешно активирован!</b>\n\n"
                        f"✅ Ключ добавлен в ваш профиль\n"
                        f"🖥️ Сервер: {key_data.get('host_name', 'Unknown')}\n"
                        f"📅 Истекает: {key_data.get('expiry_date', 'Unknown')}"
                    )
                    await message.answer(success_msg, reply_markup=keyboards.main_reply_keyboard)
                    await show_main_menu(message)
                    
                except Exception as e:
                    logger.error(f"Error reassigning gift key {key_id} to user {user_id}: {e}")
                    await message.answer(
                        "⚠️ Подарок активирован, но произошла ошибка при привязке ключа. Свяжитесь с поддержкой.",
                        reply_markup=keyboards.main_reply_keyboard
                    )
            else:
                await message.answer(
                    "⚠️ Подарок активирован, но ключ не найден. Свяжитесь с поддержкой.",
                    reply_markup=keyboards.main_reply_keyboard
                )
        else:
            await message.answer(
                "⚠️ Подарок активирован, но информация о ключе недоступна.",
                reply_markup=keyboards.main_reply_keyboard
            )
    
    except Exception as e:
        logger.error(f"Error activating gift {gift_code} for user {user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при активации подарка. Попробуйте позже.",
            reply_markup=keyboards.main_reply_keyboard
        )


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

class KeyPurchase(StatesGroup):
    waiting_for_host_selection = State()
    waiting_for_plan_selection = State()

class Captcha(StatesGroup):
    waiting_for_answer = State()

class Onboarding(StatesGroup):
    waiting_for_subscription_and_agreement = State()

class PaymentProcess(StatesGroup):
    waiting_for_email = State()
    waiting_for_payment_method = State()
    waiting_for_promo_code = State()
    waiting_for_stars_invoice = State()

 
class TopUpProcess(StatesGroup):
    waiting_for_amount = State()
    waiting_for_topup_method = State()


class TrafficGbTopUp(StatesGroup):
    waiting_for_package = State()
    waiting_for_method = State()


class LteGbTopUp(StatesGroup):
    waiting_for_package = State()
    waiting_for_method = State()


class MainPoolReset(StatesGroup):
    waiting_for_method = State()


class SupportDialog(StatesGroup):
    waiting_for_subject = State()
    waiting_for_message = State()
    waiting_for_reply = State()


# =============================
# Franchise (managed clone bots)
# =============================

TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")


class FranchiseStates(StatesGroup):
    waiting_bot_token = State()
    waiting_withdraw_amount = State()
    waiting_requisites_bank = State()
    waiting_requisites_value = State()


class KeyManagement(StatesGroup):
    waiting_for_rename = State()


class ReferralWithdraw(StatesGroup):
    waiting_method_type = State()
    waiting_method_bank = State()
    waiting_method_value = State()
    waiting_withdraw_choose_method = State()
    waiting_withdraw_amount = State()
    waiting_transfer_amount = State()


def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None

async def show_captcha(message: types.Message, state: FSMContext, user_id: int):
    """Показывает капчу пользователю."""
    captcha_type = get_setting("captcha_type") or "math"
    captcha_message = get_setting("captcha_message") or "👤 Привет! Ты выглядишь как бот. Пройди простую капчу чтобы подтвердить что ты человек.\n\n"
    timeout_minutes = int(get_setting("captcha_timeout_minutes") or "15")
    
    # Создаём капча-вызов
    challenge = create_captcha_challenge(user_id, captcha_type, timeout_minutes)
    
    if not challenge:
        await message.answer("❌ Ошибка при создании капчи. Попробуйте позже.")
        return
    
    challenge_id = challenge.get("id")
    question = challenge.get("question")
    
    await state.set_state(Captcha.waiting_for_answer)
    await state.update_data(captcha_challenge_id=challenge_id, captcha_type=captcha_type)
    
    if captcha_type == "button":
        # Капча с выбором смайлика - извлекаем правильный ответ из вопроса
        correct_answer = challenge.get("correct_answer")
        # Создаём клавиатуру с вариантами
        all_emojis = ["😊", "👍", "🔥", "❤️", "⭐", "✅", "🐱", "🤖", "😂", "🎉", "💪", "🚀"]
        import random
        options = random.sample(all_emojis, 4)
        if correct_answer not in options:
            options[random.randint(0, 3)] = correct_answer
        random.shuffle(options)
        
        await message.answer(
            captcha_message + question,
            reply_markup=keyboards.create_button_captcha_keyboard(options)
        )
    else:
        # Математическая капча
        await message.answer(
            captcha_message + question + "\n\n💬 Введите ответ цифрой:",
            reply_markup=keyboards.create_math_captcha_keyboard()
        )


async def show_main_menu(message: types.Message, edit_message: bool = False):
    user_id = message.chat.id
    user_db_data = get_user(user_id)
    all_user_keys = get_user_keys(user_id)
    # Объединяем обычные ключи и подарки для передачи в клавиатуру
    user_keys = all_user_keys
    try:
        gifts_count = len(rw_repo.get_user_inactive_gifts(user_id) or [])
    except Exception:
        gifts_count = 0
    
    trial_available = not (user_db_data and user_db_data.get('trial_used'))
    is_admin_flag = is_admin(user_id)

    # Данные пользователя
    # Важно: при кликах по inline-кнопкам мы редактируем сообщение, отправленное ботом,
    # поэтому message.from_user указывает на бота. В таких случаях берём имя из chat/БД.
    username = "Пользователь"
    try:
        if getattr(message, "from_user", None) and not getattr(message.from_user, "is_bot", False):
            username = (message.from_user.first_name
                        or message.from_user.username
                        or getattr(message.from_user, "full_name", None)
                        or username)
        else:
            chat = getattr(message, "chat", None)
            if chat:
                # private chat: chat содержит данные пользователя
                full = " ".join([x for x in [getattr(chat, "first_name", None), getattr(chat, "last_name", None)] if x])
                username = (full
                            or getattr(chat, "username", None)
                            or getattr(chat, "title", None)
                            or username)
            # В БД поле `username` хранит @username ИЛИ полное имя (см. /start).
            # Не переопределяем уже найденное имя пользователя (first_name/last_name)
            # значением из БД, чтобы при возврате в меню не показывался @username.
            if username == "Пользователь" and user_db_data and user_db_data.get("username"):
                username = user_db_data.get("username") or username
    except Exception:
        if username == "Пользователь":
            username = user_db_data.get("username") if (user_db_data and user_db_data.get("username")) else username

    try:
        balance_val = get_balance(user_id) or 0
    except Exception:
        balance_val = 0
    try:
        balance_str = f"{float(balance_val):.2f}"
    except Exception:
        balance_str = str(balance_val)

    try:
        ref_balance_val = get_referral_balance(user_id) or 0
    except Exception:
        ref_balance_val = 0
    try:
        ref_balance_str = f"{float(ref_balance_val):.2f}"
    except Exception:
        ref_balance_str = str(ref_balance_val)

    username_safe = html_escape(str(username or "Пользователь"))

    # Ссылки (настраиваются в админке)
    channel_link = (get_setting("channel_link")).strip()
    chat_link = (get_setting("chat_link")).strip()
    channel_link_safe = html_escape(channel_link, quote=True)
    chat_link_safe = html_escape(chat_link, quote=True)

    # Текст главного меню
    promo_text = (get_setting("main_menu_promo_text") or "").strip()
    if not promo_text:
        promo_text = (
            "🌐 Множество локаций\n"
            "🚀 Скорость серверов 1 Гбит/с, смена IP\n"
            "📊 Безлимитный трафик\n\n"
            "Спасибо, что вы с нами!"
        )
    text = (
        f"<b>👤 Профиль: {username_safe}</b>\n\n"
        f"<blockquote>—— ID: {user_id}\n"
        f"—— Баланс: {balance_str} ₽ RUB\n"
        f"—— Заработано (реф. баланс): {ref_balance_str} ₽ RUB</blockquote>\n\n"
        f"📝 <a href=\"{channel_link_safe}\">Наш канал</a> 📝\n"
        f"👉 <a href=\"{chat_link_safe}\">Наш чат</a> 👉\n\n"
        f"{promo_text}"
    )

    # Franchise: determine whether this is a managed clone and whether the current user is its owner
    factory_bot_id = 0
    try:
        factory_bot_id = rw_repo.resolve_factory_bot_id(getattr(message.bot, "id", None))
    except Exception:
        factory_bot_id = 0

    show_partner_cabinet = False
    if factory_bot_id > 0:
        try:
            info = rw_repo.get_managed_bot(factory_bot_id) or {}
            owner_id = int(info.get("owner_telegram_id") or 0)
            show_partner_cabinet = (owner_id == int(user_id))
        except Exception:
            show_partner_cabinet = False

    show_create_bot = factory_bot_id <= 0

    try:
        keyboard = keyboards.create_dynamic_main_menu_keyboard(
            user_keys,
            trial_available,
            is_admin_flag,
            show_create_bot=show_create_bot,
            show_partner_cabinet=show_partner_cabinet,
            gifts_count=gifts_count,
        )
    except Exception as e:
        logger.warning(f"Не удалось создать динамическую клавиатуру, используем статическую: {e}")
        keyboard = keyboards.create_main_menu_keyboard(
            user_keys,
            trial_available,
            is_admin_flag,
            show_create_bot=show_create_bot,
            show_partner_cabinet=show_partner_cabinet,
            gifts_count=gifts_count,
        )

    if edit_message:
        await _safe_edit_or_answer(message, text, reply_markup=keyboard, disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)

async def process_successful_onboarding(callback: types.CallbackQuery, state: FSMContext):
    """Завершает онбординг: ставит флаг согласия и открывает главное меню."""
    user_id = callback.from_user.id
    try:
        set_terms_agreed(user_id)
    except Exception as e:
        logger.error(f"Не удалось установить согласие с условиями для пользователя {user_id}: {e}")
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await show_main_menu(callback.message, edit_message=True)
    except Exception:
        try:
            await callback.message.answer("✅ Требования выполнены. Открываю меню...")
        except Exception:
            pass
    try:
        await state.clear()
    except Exception:
        pass

def registration_required(f):
    @wraps(f)
    async def decorated_function(event: types.Update, *args, **kwargs):
        user_id = event.from_user.id
        user_data = get_user(user_id)
        if user_data:
            return await f(event, *args, **kwargs)
        else:
            message_text = "Пожалуйста, для начала работы со мной, отправьте команду /start"
            if isinstance(event, types.CallbackQuery):
                await event.answer(message_text, show_alert=True)
            else:
                await event.answer(message_text)
    return decorated_function

async def _maybe_pay_referral_start_bonus(bot: Bot, user_id: int, referrer_id: int | None) -> None:
    """Выплатить рефереру фиксированный бонус за регистрацию приглашённого пользователя
    (настройка "Фиксированный бонус при старте по ссылке", referral_reward_type ==
    'fixed_start_referrer'), если это применимо и ещё не выплачено.

    Вынесено в отдельную функцию и вызывается из ВСЕХ путей завершения регистрации
    (обычный /start, капча текстом, капча кнопкой) — раньше эта логика была только в
    прямом /start-хендлере, и если у бота включена капча (а по умолчанию она включена,
    см. initialize_default_button_configs: "captcha_enabled": "true"), приглашённые
    пользователи регистрировались через отдельные капча-хендлеры, где этот бонус вообще
    не начислялся — реферер мог быть корректно привязан (`users.referred_by`), но так и
    не получал вознаграждение при этом типе награды.
    """
    if not referrer_id:
        return
    try:
        referrer_id = int(referrer_id)
    except (TypeError, ValueError):
        return
    if referrer_id <= 0 or referrer_id == user_id:
        return

    user_data = get_user(user_id)
    if not user_data:
        return

    try:
        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
    except Exception:
        reward_type = "percent_purchase"
    if reward_type != "fixed_start_referrer":
        return

    try:
        amount_raw = get_setting("referral_on_start_referrer_amount") or "20"
        start_bonus = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
    except Exception:
        start_bonus = Decimal("20.00")
    if start_bonus <= 0:
        return

    # Claim BEFORE credit: иначе два параллельных /start оба видят флаг=0 и
    # дважды начисляют одну и ту же сумму.
    try:
        claimed = claim_referral_start_bonus(user_id)
    except Exception:
        claimed = False
    if not claimed:
        return

    try:
        add_to_referral_balance(referrer_id, float(start_bonus))
    except Exception as e:
        logger.warning(f"Реферальный стартовый бонус: не удалось добавить к балансу для реферера {referrer_id}: {e}")

    try:
        add_to_referral_balance_all(referrer_id, float(start_bonus))
    except Exception as e:
        logger.warning(f"Реферальный стартовый бонус: не удалось увеличить referral_balance_all для {referrer_id}: {e}")

    try:
        display_name = user_data.get("username") or str(user_id)
        await bot.send_message(
            chat_id=referrer_id,
            text=(
                "🎁 Начисление за приглашение!\n"
                f"Новый пользователь: {display_name} (ID: {user_id})\n"
                f"Бонус: {float(start_bonus):.2f} RUB"
            )
        )
    except Exception:
        pass


def get_user_router() -> Router:
    user_router = Router()

    @user_router.message(CommandStart())
    async def start_handler(message: types.Message, state: FSMContext, bot: Bot, command: CommandObject):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        referrer_id = None

        # Обрабатываем вход через веб-приложение (deep-link авторизация)
        if command.args and command.args.startswith('auth_'):
            auth_token = command.args[5:]
            try:
                register_user_if_not_exists(user_id, username, None)
                ok = rw_repo.confirm_webapp_auth_request(auth_token, user_id)
                if ok:
                    await message.answer("✅ Вход выполнен! Вернитесь во вкладку с веб-приложением — она обновится автоматически.")
                else:
                    await message.answer("⚠️ Ссылка для входа устарела. Попробуйте открыть веб-приложение заново.")
            except Exception:
                logger.warning("Не удалось обработать auth_ deep-link", exc_info=True)
                await message.answer("⚠️ Не удалось выполнить вход. Попробуйте ещё раз.")
            return

        # Обрабатываем активацию подарка
        if command.args and command.args.startswith('gift_'):
            gift_code = command.args[5:]  # Убираем "gift_"

            # Запоминаем ДО регистрации — нужно для определения нового пользователя
            _gift_user_is_new = (get_user(user_id) is None)

            # Пользователь должен быть зарегистрирован или зарегистрируется
            register_user_if_not_exists(user_id, username, None)

            # Проверяем, нужна ли капча для активации подарка
            captcha_enabled = get_setting("captcha_enabled") == "true"

            if captcha_enabled and not has_passed_captcha(user_id):
                # Сохраняем gift_code и флаг нового пользователя в FSM
                await state.update_data(gift_code=gift_code, is_gift_activation=True, gift_user_is_new=_gift_user_is_new)
                await show_captcha(message, state, user_id)
                return
            else:
                # Капча отключена или уже пройдена, активируем подарок
                await _activate_gift_directly(message, bot, user_id, gift_code, is_new_user=_gift_user_is_new)
                return
        
        # Обрабатываем реферальную ссылку
        if command.args and command.args.startswith('ref_'):
            try:
                potential_referrer_id = int(command.args.split('_')[1])
                if potential_referrer_id != user_id:
                    referrer_id = potential_referrer_id
                    logger.info(f"Новый пользователь {user_id} пришел по реферальной ссылке от {referrer_id}")
            except (IndexError, ValueError):
                logger.warning(f"Получен неверный реферальный код: {command.args}")

        # Обрабатываем UTM-метку (best-effort, не должно ломать регистрацию/капчу)
        if command.args and command.args.startswith('utm_'):
            try:
                utm_slug = command.args[4:].strip()
                if utm_slug:
                    log_utm_visit(utm_slug, user_id, 'start')
                    set_user_utm_slug_if_absent(user_id, utm_slug)
            except Exception:
                logger.warning(f"Не удалось обработать UTM-метку: {command.args}", exc_info=True)

        # Проверяем, нужна ли капча
        captcha_enabled = get_setting("captcha_enabled") == "true"
        user_exists = get_user(user_id) is not None
        
        # Капча нужна только новым пользователям при первой регистрации
        if captcha_enabled and not user_exists:
            # НЕ регистрируем пользователя здесь - только показываем капчу
            # Регистрация произойдёт после успешного прохождения капчи

            # Сохраняем реферальную информацию в FSM для последующей регистрации.
            # ВАЖНО: обновляем только если пришла НОВАЯ реферальная ссылка — если
            # пользователь уже ждёт капчу (например, прошло много времени и он
            # просто написал "/start" заново без параметра рефссылки), referrer_id
            # здесь будет None, и его НЕЛЬЗЯ сохранять — это затрёт уже сохранённое
            # значение из первого перехода по ссылке (FSMContext.update_data делает
            # обычный dict.update, а не "установить, если ещё не задано").
            if referrer_id:
                await state.update_data(referred_by=referrer_id)
            else:
                existing_state_data = await state.get_data()
                referrer_id = existing_state_data.get("referred_by")
            
            # Если капча уже пройдена ранее - пропускаем
            if not has_passed_captcha(user_id):
                # Показываем капчу
                await show_captcha(message, state, user_id)
                return
            # Если капча была пройдена ранее, продолжаем регистрацию
            # Зарегистрируем пользователя сейчас
            register_user_if_not_exists(user_id, username, referrer_id)
        else:
            # Капча отключена или пользователь уже существует
            register_user_if_not_exists(user_id, username, referrer_id)

        # Важно: +1 день за реферала начисляем только после того, как реферал активирует триал.

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        user_data = get_user(user_id)

        await _maybe_pay_referral_start_bonus(bot, user_id, referrer_id)

        if user_data and user_data.get('agreed_to_terms'):
            await message.answer(
                f"👋 Снова здравствуйте, <b>{html_escape(str(message.from_user.full_name or 'Пользователь'))}</b>!",
                reply_markup=keyboards.main_reply_keyboard
            )
            await show_main_menu(message)
            return

        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        channel_url = get_setting("channel_url")

        if not channel_url and (not terms_url or not privacy_url):
            set_terms_agreed(user_id)
            await show_main_menu(message)
            return

        is_subscription_forced = get_setting("force_subscription") == "true"
        
        show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)

        if not show_welcome_screen:
            set_terms_agreed(user_id)
            await show_main_menu(message)
            return

        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
        
        if is_subscription_forced and channel_url:
            welcome_parts.append("Для доступа ко всем функциям, пожалуйста, подпишитесь на наш канал.")
        
        if terms_url and privacy_url:
            welcome_parts.append(
                "Также необходимо ознакомиться и принять наши "
                f"<a href='{terms_url}'>Условия использования</a> и "
                f"<a href='{privacy_url}'>Политику конфиденциальности</a>."
            )
        
        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
        final_text = "\n".join(welcome_parts)
        
        await message.answer(
            final_text,
            reply_markup=keyboards.create_welcome_keyboard(
                channel_url=channel_url,
                is_subscription_forced=is_subscription_forced
            ),
            disable_web_page_preview=True
        )
        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)

    @user_router.callback_query(Onboarding.waiting_for_subscription_and_agreement, F.data == "check_subscription_and_agree")
    async def check_subscription_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        channel_url = get_setting("channel_url")
        is_subscription_forced = get_setting("force_subscription") == "true"

        if not is_subscription_forced or not channel_url:
            await process_successful_onboarding(callback, state)
            return
            
        try:
            if '@' not in channel_url and 't.me/' not in channel_url:
                logger.error(f"Неверный формат URL канала: {channel_url}. Пропускаем проверку подписки.")
                await process_successful_onboarding(callback, state)
                return

            channel_id = '@' + channel_url.split('/')[-1] if 't.me/' in channel_url else channel_url
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            
            if member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                await process_successful_onboarding(callback, state)
            else:
                await callback.answer("Вы еще не подписались на канал. Пожалуйста, подпишитесь и попробуйте снова.", show_alert=True)

        except Exception as e:
            logger.error(f"Ошибка при проверке подписки для user_id {user_id} на канал {channel_url}: {e}")
            await callback.answer("Не удалось проверить подписку. Убедитесь, что бот является администратором канала. Попробуйте позже.", show_alert=True)

    @user_router.message(Onboarding.waiting_for_subscription_and_agreement)
    async def onboarding_fallback_handler(message: types.Message):
        await message.answer("Пожалуйста, выполните требуемые действия и нажмите на кнопку в сообщении выше.")

    # =============================
    # Captcha handlers
    # =============================
    
    @user_router.message(Captcha.waiting_for_answer)
    async def captcha_answer_handler(message: types.Message, state: FSMContext):
        """Обработчик текстового ответа на математическую капчу."""
        user_id = message.from_user.id
        
        try:
            data = await state.get_data()
            challenge_id = data.get("captcha_challenge_id")
            captcha_type = data.get("captcha_type", "math")
            referred_by = data.get("referred_by")  # Получаем сохранённую реферальную информацию
            
            if not challenge_id:
                await message.answer("❌ Сессия капчи истекла. Напишите /start для новой попытки.")
                await state.clear()
                return
            
            user_answer = message.text
            success, msg = check_captcha_answer(challenge_id, user_answer)
            
            if success:
                # Капча пройдена
                mark_user_passed_captcha(user_id, challenge_id)
                await message.answer(msg)
                
                # 🔴 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ в БД после успешного прохождения капчи
                # Используем сохранённую реферальную информацию
                username = message.from_user.username or message.from_user.full_name
                register_user_if_not_exists(user_id, username, referred_by)
                # Тот же фиксированный бонус рефереру, что и в прямом /start без капчи
                # (см. _maybe_pay_referral_start_bonus) — раньше здесь не начислялся вообще.
                await _maybe_pay_referral_start_bonus(message.bot, user_id, referred_by)
        
                # Проверяем, активируем ли мы подарок
                gift_code = data.get("gift_code")
                if gift_code:
                    # Captcha is only shown to new users — default True, but honour FSM flag if stored
                    _is_new = data.get("gift_user_is_new", True)
                    await state.clear()
                    await _activate_gift_directly(message, message.bot, user_id, gift_code, is_new_user=_is_new)
                    return

                # Продолжаем onboarding
                await state.clear()

                # Выполняем логику регистрации с согласием
                terms_url = get_setting("terms_url")
                privacy_url = get_setting("privacy_url")
                channel_url = get_setting("channel_url")

                if not channel_url and (not terms_url or not privacy_url):
                    set_terms_agreed(user_id)
                    # Переходим прямо в главное меню
                    await show_main_menu(message)
                else:
                    # Показываем экран приветствия с согласием
                    is_subscription_forced = get_setting("force_subscription") == "true"
                    show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)
                    
                    if not show_welcome_screen:
                        set_terms_agreed(user_id)
                        await show_main_menu(message)
                    else:
                        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
                        if is_subscription_forced and channel_url:
                            welcome_parts.append(f"🔗 <a href='{channel_url}'>Подпишись на канал</a>\n")
                        if terms_url and privacy_url:
                            welcome_parts.append(f"📋 Прочитай <a href='{terms_url}'>Условия</a> и <a href='{privacy_url}'>Политику</a>\n")
                        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
                        final_text = "\n".join(welcome_parts)
                        await message.answer(
                            final_text,
                            reply_markup=keyboards.create_welcome_keyboard(
                                channel_url=channel_url,
                                is_subscription_forced=is_subscription_forced
                            ),
                            disable_web_page_preview=True
                        )
                        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)
            else:
                # Неправильный ответ
                await message.answer(msg)
        
        except Exception as e:
            logger.error(f"Error in captcha_answer_handler: {e}", exc_info=True)
            await message.answer("❌ Ошибка при проверке ответа. Попробуйте снова.")
    
    @user_router.callback_query(Captcha.waiting_for_answer, F.data.startswith("captcha_answer:"))
    async def captcha_button_answer_handler(callback: types.CallbackQuery, state: FSMContext):
        """Обработчик ответа на капчу с выбором кнопки."""
        user_id = callback.from_user.id
        user_answer = callback.data.split(":", 1)[1]
        
        try:
            data = await state.get_data()
            challenge_id = data.get("captcha_challenge_id")
            referred_by = data.get("referred_by")  # Получаем сохранённую реферальную информацию
            
            if not challenge_id:
                await callback.answer("❌ Сессия капчи истекла. Напишите /start для новой попытки.", show_alert=True)
                await state.clear()
                return
            
            success, msg = check_captcha_answer(challenge_id, user_answer)
            
            if success:
                # Капча пройдена
                mark_user_passed_captcha(user_id, challenge_id)
                await callback.answer(msg, show_alert=True)
                
                # 🔴 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ в БД после успешного прохождения капчи
                # Используем сохранённую реферальную информацию
                username = callback.from_user.username or callback.from_user.full_name
                register_user_if_not_exists(user_id, username, referred_by)
                # Тот же фиксированный бонус рефереру, что и в прямом /start без капчи
                # (см. _maybe_pay_referral_start_bonus) — раньше здесь не начислялся вообще.
                await _maybe_pay_referral_start_bonus(callback.bot, user_id, referred_by)
                
                # Проверяем, активируем ли мы подарок
                gift_code = data.get("gift_code")
                if gift_code:
                    _is_new = data.get("gift_user_is_new", True)
                    await state.clear()
                    await _activate_gift_directly(callback.message, callback.bot, user_id, gift_code, is_new_user=_is_new)
                    return

                # Продолжаем onboarding
                await state.clear()

                # Выполняем логику регистрации с согласием
                terms_url = get_setting("terms_url")
                privacy_url = get_setting("privacy_url")
                channel_url = get_setting("channel_url")

                if not channel_url and (not terms_url or not privacy_url):
                    set_terms_agreed(user_id)
                    # Редактируем или отправляем главное меню
                    try:
                        await show_main_menu(callback.message, edit_message=True)
                    except Exception:
                        await show_main_menu(callback.message, edit_message=False)
                else:
                    # Показываем экран приветствия с согласием
                    is_subscription_forced = get_setting("force_subscription") == "true"
                    show_welcome_screen = (is_subscription_forced and channel_url) or (terms_url and privacy_url)
                    
                    if not show_welcome_screen:
                        set_terms_agreed(user_id)
                        try:
                            await show_main_menu(callback.message, edit_message=True)
                        except Exception:
                            await show_main_menu(callback.message, edit_message=False)
                    else:
                        welcome_parts = ["<b>Добро пожаловать!</b>\n"]
                        if is_subscription_forced and channel_url:
                            welcome_parts.append(f"🔗 <a href='{channel_url}'>Подпишись на канал</a>\n")
                        if terms_url and privacy_url:
                            welcome_parts.append(f"📋 Прочитай <a href='{terms_url}'>Условия</a> и <a href='{privacy_url}'>Политику</a>\n")
                        welcome_parts.append("\nПосле этого нажмите кнопку ниже.")
                        final_text = "\n".join(welcome_parts)
                        try:
                            await callback.message.edit_text(
                                final_text,
                                reply_markup=keyboards.create_welcome_keyboard(
                                    channel_url=channel_url,
                                    is_subscription_forced=is_subscription_forced
                                )
                            )
                        except Exception:
                            await callback.message.answer(
                                final_text,
                                reply_markup=keyboards.create_welcome_keyboard(
                                    channel_url=channel_url,
                                    is_subscription_forced=is_subscription_forced
                                )
                            )
                        await state.set_state(Onboarding.waiting_for_subscription_and_agreement)
            else:
                # Неправильный ответ
                await callback.answer(msg, show_alert=True)
        
        except Exception as e:
            logger.error(f"Error in captcha_button_answer_handler: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при проверке ответа. Попробуйте снова.", show_alert=True)
    
    @user_router.callback_query(Captcha.waiting_for_answer, F.data == "cancel_captcha")
    async def cancel_captcha_handler(callback: types.CallbackQuery, state: FSMContext):
        """Отмена капчи."""
        await callback.answer("❌ Капча отменена. Напишите /start для новой попытки.")
        await state.clear()
        await callback.message.delete()

    @user_router.message(F.text == "🏠 Главное меню")
    @registration_required
    async def main_menu_handler(message: types.Message):
        await show_main_menu(message)

    @user_router.callback_query(F.data == "back_to_main_menu")
    @registration_required
    async def back_to_main_menu_handler(callback: types.CallbackQuery):
        await callback.answer()
        await show_main_menu(callback.message, edit_message=True)

    @user_router.callback_query(F.data == "open_main_menu")
    @registration_required
    async def open_main_menu_handler(callback: types.CallbackQuery):
        await callback.answer()
        await show_main_menu(callback.message, edit_message=False)

    @user_router.callback_query(F.data == "show_main_menu")
    @registration_required
    async def show_main_menu_cb(callback: types.CallbackQuery):
        await callback.answer()
        await show_main_menu(callback.message, edit_message=True)

    @user_router.callback_query(F.data == "show_profile")
    @registration_required
    async def profile_handler_callback(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        user_keys = get_user_keys(user_id)
        if not user_db_data:
            await callback.answer("Не удалось получить данные профиля.", show_alert=True)
            return
        username = html_escape(str(user_db_data.get('username', 'Пользователь') or 'Пользователь'))
        total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
        now = datetime.now()
        active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
        if active_keys:
            latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
            latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
            time_left = latest_expiry_date - now
            vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
        elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
        else: vpn_status_text = VPN_NO_DATA_TEXT
        final_text = get_profile_text(username, total_spent, total_months, vpn_status_text)

        try:
            main_balance = get_balance(user_id)
        except Exception:
            main_balance = 0.0
        final_text += f"\n\n💼 <b>Основной баланс:</b> {main_balance:.0f} RUB"

        try:
            referral_count = get_referral_count(user_id)
        except Exception:
            referral_count = 0
        try:
            total_ref_earned = float(get_referral_balance_all(user_id))
        except Exception:
            total_ref_earned = 0.0
        final_text += (
            f"\n🤝 <b>Рефералы:</b> {referral_count}"
            f"\n💰 <b>Заработано по рефералке (всего):</b> {total_ref_earned:.2f} RUB"
        )
        
        # Показываем кнопку уведомлений только если ключей больше 10
        show_notification_toggle = len(user_keys) > 10 if user_keys else False
        try:
            gifts_count = len(rw_repo.get_user_inactive_gifts(user_id) or [])
        except Exception:
            gifts_count = len(
                [k for k in (user_keys or []) if str(k.get('tag') or '').strip().lower() in ('user_gift', 'gift')]
            )
        notifications_enabled = True
        if show_notification_toggle:
            try:
                notifications_enabled = rw_repo.is_subscription_expiry_notifications_enabled(user_id)
            except Exception:
                notifications_enabled = True

        # Автопродление: показываем переключатель если у пользователя есть хотя бы один ключ с тарифом
        non_gift_keys = [k for k in user_keys if str(k.get("tag") or "").strip().lower() not in ("user_gift", "gift")]
        show_auto_renew_toggle = bool(non_gift_keys)
        auto_renew_any_enabled = any(bool(int(k.get("auto_renew") or 0)) for k in non_gift_keys)

        await _safe_edit_or_answer(
            callback.message,
            final_text,
            reply_markup=keyboards.create_profile_keyboard(
                show_notification_toggle=show_notification_toggle,
                notifications_enabled=notifications_enabled,
                gifts_count=gifts_count,
                show_auto_renew_toggle=show_auto_renew_toggle,
                auto_renew_any_enabled=auto_renew_any_enabled,
            )
        )

    @user_router.callback_query(F.data == "toggle_expiry_notifications")
    @registration_required
    async def toggle_expiry_notifications_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            new_state = rw_repo.toggle_subscription_expiry_notifications(user_id)
            state_text = "✅ Уведомления включены" if new_state else "❌ Уведомления отключены"
            await callback.answer(state_text, show_alert=True)
            # Обновляем профиль пользователя
            await profile_handler_callback(callback)
        except Exception as e:
            logger.error(f"Ошибка при переключении уведомлений для {user_id}: {e}")
            await callback.answer("❌ Ошибка при переключении уведомлений", show_alert=True)

    @user_router.callback_query(F.data == "show_inactive_gifts")
    @registration_required
    async def show_inactive_gifts_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        
        try:
            gifts = rw_repo.get_user_inactive_gifts(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении неактивных подарков для {user_id}: {e}")
            await callback.answer("❌ Ошибка при получении списка подарков", show_alert=True)
            return
        
        if not gifts:
            await callback.message.edit_text(
                "🎁 У вас нет неактивных подарков.\n\nВы можете купить подарок в главном меню.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        
        await callback.message.edit_text(
            "🎁 <b>Ваши неактивные подарки:</b>",
            reply_markup=keyboards.create_gifts_management_keyboard(gifts, page=0)
        )

    @user_router.callback_query(F.data.startswith("gifts_page_"))
    @registration_required
    async def gifts_page_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        
        # Получаем номер страницы
        try:
            page = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        try:
            gifts = rw_repo.get_user_inactive_gifts(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении подарков для страницы {page}: {e}")
            await callback.answer("❌ Ошибка при получении списка подарков", show_alert=True)
            return
        
        if not gifts:
            await callback.message.edit_text(
                "🎁 У вас нет неактивных подарков.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        
        await callback.message.edit_reply_markup(
            reply_markup=keyboards.create_gifts_management_keyboard(gifts, page=page)
        )

    @user_router.callback_query(F.data.startswith("show_gift_"))
    @registration_required
    async def show_gift_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        
        try:
            gift_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных подарка", show_alert=True)
            return
        
        await callback.message.edit_text("Загружаю информацию о подарке...")
        
        try:
            # Получаем информацию о подарке
            gift = rw_repo.get_user_gift(gift_id)
            if not gift:
                await callback.message.edit_text("❌ Подарок не найден")
                return
            
            # Проверяем что подарок принадлежит пользователю
            if gift.get('from_user_id') != user_id:
                await callback.answer("❌ Это не ваш подарок", show_alert=True)
                return
            
            key_id = gift.get('key_id')
            gift_code = gift.get('gift_code')
            is_activated = gift.get('is_activated', False)
            
            # Получаем ключ из БД
            if not key_id:
                await callback.message.edit_text("❌ Ключ для этого подарка не найден")
                return
            
            key_data = rw_repo.get_key_by_id(key_id)
            if not key_data:
                await callback.message.edit_text("❌ Данные ключа не найдены")
                return
            
            # Получаем детали ключа с сервера (как в show_key_handler)
            try:
                details = await remnawave_api.get_key_details_from_host(key_data)
                if not details or not details.get('connection_string'):
                    await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                    return
            except Exception as e:
                logger.error(f"Error getting key details for gift {gift_id}: {e}")
                await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                return

            connection_string = details['connection_string']
            
            # Получаем информацию о тарифе
            user_payload = details.get('user') if isinstance(details, dict) else None
            devices_connected = await _get_connected_devices_count(key_data, user_payload)
            devices_list = await _get_devices_list(key_data, user_payload)
            plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
            
            # Формируем ссылки активации подарка — и в webapp, и в Telegram, как в мини-приложении
            gift_link, gift_telegram_link = None, None
            if gift_code and not is_activated:
                gift_link, gift_telegram_link = _build_gift_links(gift_code)
            
            # Выводим ключ как обычно
            gift_text = get_key_info_text(
                key_data,
                key_number=1,
                devices_connected=devices_connected,
                plan_group=plan_group,
                plan_name=plan_name,
                device_limit=device_limit,
                gift_code=gift_code,
                is_gift_activated=is_activated,
                gift_link=gift_link,
                gift_telegram_link=gift_telegram_link,
            )
            
            await callback.message.edit_text(
                gift_text,
                reply_markup=keyboards.create_gift_info_keyboard(
                    gift_id, key_id, is_activated, connection_string, devices_list, gift_link
                ),
                disable_web_page_preview=True
            )
        
        except Exception as e:
            logger.error(f"Error showing gift {gift_id}: {e}", exc_info=True)
            await callback.message.edit_text("❌ Произошла ошибка при получении информации о подарке.")

    @user_router.callback_query(F.data.startswith("send_gift_link_"))
    @registration_required
    async def send_gift_link_handler(callback: types.CallbackQuery):
        """Отправка ссылки подарка пользователю."""
        await callback.answer()
        user_id = callback.from_user.id
        
        try:
            gift_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных подарка", show_alert=True)
            return
        
        try:
            # Получаем информацию о подарке
            gift = rw_repo.get_user_gift(gift_id)
            if not gift:
                await callback.answer("❌ Подарок не найден", show_alert=True)
                return
            
            # Проверяем что подарок принадлежит пользователю
            if gift.get('from_user_id') != user_id:
                await callback.answer("❌ Это не ваш подарок", show_alert=True)
                return
            
            gift_code = gift.get('gift_code')
            
            if not gift_code:
                await callback.answer("❌ Не удалось сформировать ссылку подарка", show_alert=True)
                return
            
            # Формируем обе ссылки подарка — в мини-приложении и в Telegram
            gift_link, gift_telegram_link = _build_gift_links(gift_code)
            
            if not gift_link and not gift_telegram_link:
                await callback.answer("❌ Не удалось сформировать ссылку подарка", show_alert=True)
                return
            
            share_text = _gift_share_text()
            
            text_parts = ["🎁 <b>Ссылки активации подарка</b> (нажмите, чтобы скопировать):\n"]
            builder = InlineKeyboardBuilder()
            if gift_link:
                text_parts.append(f"<i>В приложении:</i>\n<code>{html_escape(gift_link)}</code>\n")
                builder.button(
                    text="📤 Поделиться (в приложении)",
                    url=_telegram_share_url(gift_link, share_text),
                )
            if gift_telegram_link:
                text_parts.append(f"<i>В Telegram:</i>\n<code>{html_escape(gift_telegram_link)}</code>\n")
                builder.button(
                    text="📤 Поделиться (в Telegram)",
                    url=_telegram_share_url(gift_telegram_link, share_text),
                )
            builder.button(text="⬅️ Назад", callback_data=f"show_gift_{gift_id}")
            builder.adjust(1)
            
            await callback.message.edit_text(
                "".join(text_parts),
                reply_markup=builder.as_markup()
            )
            
        except Exception as e:
            logger.error(f"Error sending gift link {gift_id}: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при отправке ссылки", show_alert=True)

    @user_router.callback_query(F.data.startswith("activate_own_gift_"))
    @registration_required
    async def activate_own_gift_handler(callback: types.CallbackQuery):
        """Активировать собственный неактивированный подарок себе (аналог webapp-кнопки 'Активировать себе')."""
        await callback.answer()
        user_id = callback.from_user.id

        try:
            gift_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных подарка", show_alert=True)
            return

        try:
            gift = rw_repo.get_user_gift(gift_id)
            if not gift:
                await callback.answer("❌ Подарок не найден", show_alert=True)
                return

            if gift.get('from_user_id') != user_id:
                await callback.answer("❌ Это не ваш подарок", show_alert=True)
                return

            if gift.get('is_activated'):
                await callback.answer("⚠️ Этот подарок уже был активирован", show_alert=True)
                return

            gift_code = gift.get('gift_code')
            if not gift_code:
                await callback.answer("❌ Не удалось активировать подарок", show_alert=True)
                return

            await _activate_gift_directly(callback.message, callback.bot, user_id, gift_code, is_new_user=False)
        except Exception as e:
            logger.error(f"Error activating own gift {gift_id} for user {user_id}: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при активации подарка", show_alert=True)

    def _resolve_plan_for_traffic_topup(key_id: int, user_id: int) -> tuple[dict, dict] | tuple[None, None]:
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            return None, None
        plan_id = _resolve_plan_id_for_key(key_data)
        if not plan_id:
            return None, None
        plan = get_plan_by_id(plan_id)
        if not plan or int(plan.get('traffic_limit_bytes') or 0) <= 0:
            return None, None
        return key_data, plan

    @user_router.callback_query(F.data.startswith("traffic_gb_start_"))
    @registration_required
    async def traffic_gb_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data, plan = _resolve_plan_for_traffic_topup(key_id, user_id)
        if not plan:
            await callback.message.edit_text(
                "❌ Для тарифа этого ключа не настроена докупка трафика.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        packages = database.get_traffic_packages_for_plan(plan['plan_id'], only_active=True)
        if not packages:
            await callback.message.edit_text(
                "❌ Пакеты докупки трафика для этого тарифа пока не настроены. Обратитесь к администратору.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        await state.update_data(traffic_key_id=key_id)
        await callback.message.edit_text(
            "Выберите объём докупаемого трафика:",
            reply_markup=keyboards.create_traffic_packages_keyboard(key_id, packages)
        )

    @user_router.callback_query(F.data.startswith("traffic_gb_pick_"))
    @registration_required
    async def traffic_gb_pick_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            parts = callback.data.split("_")
            package_id = int(parts[-1])
            key_id = int(parts[-2])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data, plan = _resolve_plan_for_traffic_topup(key_id, user_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: тариф ключа не найден.")
            return

        package = database.get_traffic_package_by_id(package_id)
        if not package or int(package.get('plan_id')) != int(plan['plan_id']):
            await callback.answer("Пакет не найден", show_alert=True)
            return

        await state.update_data(
            traffic_key_id=key_id,
            traffic_package_id=package_id,
            traffic_package_price=float(package.get('price') or 0),
            traffic_package_size_gb=float(package.get('size_gb') or 0),
        )

        try:
            main_balance = get_balance(user_id)
        except Exception:
            main_balance = 0.0

        size_gb = float(package.get('size_gb') or 0)
        price = float(package.get('price') or 0)
        size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"

        await callback.message.edit_text(
            f"📶 Докупка {size_txt} ГБ — {price:.0f} RUB\n"
            f"Ваш баланс: {main_balance:.0f} RUB\n\n"
            "Выберите способ оплаты:",
            reply_markup=keyboards.create_traffic_gb_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(TrafficGbTopUp.waiting_for_method)

    def _traffic_gb_metadata(data: dict, user_id: int, payment_method: str, payment_id: str) -> dict:
        price = float(data.get('traffic_package_price', 0))
        return {
            "user_id": int(user_id),
            "price": price,
            "action": "traffic_gb_topup",
            "key_id": data.get('traffic_key_id'),
            "package_id": data.get('traffic_package_id'),
            "size_gb": data.get('traffic_package_size_gb'),
            "payment_method": payment_method,
            "payment_id": payment_id,
        }

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_balance")
    async def trafficgb_pay_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на балансе.", show_alert=True)
            return
        payment_id = f"balance:{user_id}:{uuid.uuid4()}"
        metadata = _traffic_gb_metadata(data, user_id, "Balance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_referral_balance")
    async def trafficgb_pay_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return
        payment_id = f"referral_balance:{user_id}:{uuid.uuid4()}"
        metadata = _traffic_gb_metadata(data, user_id, "ReferralBalance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_yookassa")
    async def trafficgb_pay_yookassa_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key

        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('traffic_package_size_gb')
        description = f"Докупка {size_gb} ГБ трафика"
        payment_id = str(uuid.uuid4())
        price_str = f"{price:.2f}"
        metadata = _traffic_gb_metadata(data, user_id, "YooKassa", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.warning(f"YooKassa traffic-gb: не удалось создать pending: {e}")
        try:
            payment_payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": payment_id}
            }
            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, user_id, float(price), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa traffic-gb: не удалось сохранить provider id: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa traffic-gb payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_platega")
    async def trafficgb_pay_platega_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega временно недоступен.")
            await state.clear()
            return
        data = await state.get_data()
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('traffic_package_size_gb')
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "Platega", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url, txid = await _create_platega_payment_link(amount_rub=price, payment_id=payment_id, description=f"Докупка {size_gb} ГБ трафика")
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже.")
            await state.clear()
            return
        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, user_id, float(price), metadata2)
        except Exception:
            pass
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_rollypay")
    async def trafficgb_pay_rollypay_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП временно недоступна.")
            await state.clear()
            return
        data = await state.get_data()
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('traffic_package_size_gb')
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "RollyPay", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=price, payment_id=payment_id, description=f"Докупка {size_gb} ГБ трафика",
            customer_id=str(user_id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже.")
            await state.clear()
            return
        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, user_id, float(price), metadata2)
        except Exception:
            pass
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_heleket")
    async def trafficgb_pay_heleket_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        state_data = {
            "action": "traffic_gb_topup",
            "customer_email": None,
            "plan_id": None,
            "package_id": data.get('traffic_package_id'),
            "host_name": None,
            "key_id": data.get('traffic_key_id'),
        }
        try:
            pay_url = await _create_heleket_payment_request(
                user_id=user_id,
                price=price,
                months=0,
                host_name="",
                state_data=state_data
            )
            if pay_url:
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_payment_keyboard(pay_url)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create traffic-gb Heleket invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_cryptobot")
    async def trafficgb_pay_cryptobot_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт в Crypto Pay...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('traffic_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        state_data = {
            "action": "traffic_gb_topup",
            "customer_email": None,
            "plan_id": None,
            "package_id": data.get('traffic_package_id'),
            "host_name": None,
            "key_id": data.get('traffic_key_id'),
        }
        try:
            result = await _create_cryptobot_invoice(
                user_id=user_id,
                price_rub=price,
                months=0,
                host_name="",
                state_data=state_data,
            )
            if result:
                pay_url, invoice_id = result
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_cryptobot_payment_keyboard(pay_url, invoice_id)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create traffic-gb CryptoBot invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_yoomoney")
    async def trafficgb_pay_yoomoney_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю YooMoney...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('traffic_package_price', 0)))
        wallet = get_setting("yoomoney_wallet")
        secret = get_setting("yoomoney_secret")
        if not wallet or not secret or price <= 0:
            await callback.message.edit_text("❌ YooMoney временно недоступен.")
            await state.clear()
            return
        w = (wallet or "").strip()
        if not (w.isdigit() and len(w) >= 11):
            await callback.message.edit_text("❌ Некорректный номер кошелька YooMoney.")
            await state.clear()
            return
        if price < Decimal("1.00"):
            await callback.message.edit_text("❌ Минимальная сумма перевода YooMoney — 1 RUB.")
            await state.clear()
            return
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "YooMoney", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url = _build_yoomoney_link(wallet, price, payment_id)
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_yoomoney_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == "trafficgb_pay_stars")
    async def trafficgb_pay_stars_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('traffic_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        try:
            stars_ratio = Decimal(get_setting("stars_per_rub") or '0')
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return
        stars_amount = int((price * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) or 1
        payment_id = str(uuid.uuid4())
        metadata = _traffic_gb_metadata(data, user_id, "Telegram Stars", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.error(f"traffic-gb Stars: не удалось создать pending: {e}", exc_info=True)
        size_gb = data.get('traffic_package_size_gb')
        try:
            await callback.message.answer_invoice(
                title="Докупка трафика",
                description=f"Докупка {size_gb} ГБ трафика",
                prices=[LabeledPrice(label="Докупка трафика", amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to create traffic-gb Stars invoice: {e}")
            await callback.message.edit_text("❌ Не удалось создать счёт в Stars.")
            await state.clear()

    def _resolve_plan_for_lte_topup(key_id: int, user_id: int) -> tuple[dict, dict] | tuple[None, None]:
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            return None, None
        plan_id = _resolve_plan_id_for_key(key_data)
        if not plan_id:
            return None, None
        plan = get_plan_by_id(plan_id)
        if not database.should_account_lte_traffic(plan, key_data.get('host_name')):
            return None, None
        return key_data, plan

    @user_router.callback_query(F.data.startswith("lte_gb_start_"))
    @registration_required
    async def lte_gb_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data, plan = _resolve_plan_for_lte_topup(key_id, user_id)
        if not plan:
            await callback.message.edit_text(
                "❌ Для тарифа этого ключа не настроена докупка LTE.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        packages = database.get_traffic_packages_for_plan(plan['plan_id'], only_active=True, pool='lte')
        lte_label = database.get_lte_squad_display_label(key_data.get("host_name"))
        lte_label_html = html_escape(lte_label)
        if not packages:
            await callback.message.edit_text(
                f"❌ Пакеты докупки {lte_label_html} для этого тарифа пока не настроены. Обратитесь к администратору.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        await state.update_data(lte_key_id=key_id)
        await callback.message.edit_text(
            f"Выберите объём докупаемого {lte_label_html}-трафика (💰 premium-ноды):",
            reply_markup=keyboards.create_lte_packages_keyboard(key_id, packages, lte_label=lte_label)
        )

    @user_router.callback_query(F.data.startswith("lte_gb_pick_"))
    @registration_required
    async def lte_gb_pick_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            parts = callback.data.split("_")
            package_id = int(parts[-1])
            key_id = int(parts[-2])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data, plan = _resolve_plan_for_lte_topup(key_id, user_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: тариф ключа не найден.")
            return

        package = database.get_traffic_package_by_id(package_id)
        if not package or int(package.get('plan_id')) != int(plan['plan_id']):
            await callback.answer("Пакет не найден", show_alert=True)
            return

        await state.update_data(
            lte_key_id=key_id,
            lte_package_id=package_id,
            lte_package_price=float(package.get('price') or 0),
            lte_package_size_gb=float(package.get('size_gb') or 0),
        )

        try:
            main_balance = get_balance(user_id)
        except Exception:
            main_balance = 0.0

        size_gb = float(package.get('size_gb') or 0)
        price = float(package.get('price') or 0)
        size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"
        lte_label_html = html_escape(database.get_lte_squad_display_label(key_data.get("host_name")))

        await callback.message.edit_text(
            f"💰 Докупка {size_txt} ГБ {lte_label_html} — {price:.0f} RUB\n"
            f"Ваш баланс: {main_balance:.0f} RUB\n\n"
            "Выберите способ оплаты:",
            reply_markup=keyboards.create_lte_gb_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(LteGbTopUp.waiting_for_method)

    def _lte_gb_metadata(data: dict, user_id: int, payment_method: str, payment_id: str) -> dict:
        price = float(data.get('lte_package_price', 0))
        return {
            "user_id": int(user_id),
            "price": price,
            "action": "lte_gb_topup",
            "key_id": data.get('lte_key_id'),
            "package_id": data.get('lte_package_id'),
            "size_gb": data.get('lte_package_size_gb'),
            "payment_method": payment_method,
            "payment_id": payment_id,
        }

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_balance")
    async def ltegb_pay_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('lte_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на балансе.", show_alert=True)
            return
        payment_id = f"balance:{user_id}:{uuid.uuid4()}"
        metadata = _lte_gb_metadata(data, user_id, "Balance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_referral_balance")
    async def ltegb_pay_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('lte_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return
        payment_id = f"referral_balance:{user_id}:{uuid.uuid4()}"
        metadata = _lte_gb_metadata(data, user_id, "ReferralBalance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_yookassa")
    async def ltegb_pay_yookassa_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key

        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('lte_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('lte_package_size_gb')
        description = f"Докупка {size_gb} ГБ LTE-трафика"
        payment_id = str(uuid.uuid4())
        price_str = f"{price:.2f}"
        metadata = _lte_gb_metadata(data, user_id, "YooKassa", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.warning(f"YooKassa lte-gb: не удалось создать pending: {e}")
        try:
            payment_payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": payment_id}
            }
            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, user_id, float(price), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa lte-gb: не удалось сохранить provider id: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa lte-gb payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_platega")
    async def ltegb_pay_platega_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega временно недоступен.")
            await state.clear()
            return
        data = await state.get_data()
        price = Decimal(str(data.get('lte_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('lte_package_size_gb')
        payment_id = str(uuid.uuid4())
        metadata = _lte_gb_metadata(data, user_id, "Platega", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url, txid = await _create_platega_payment_link(amount_rub=price, payment_id=payment_id, description=f"Докупка {size_gb} ГБ LTE")
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже.")
            await state.clear()
            return
        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, user_id, float(price), metadata2)
        except Exception:
            pass
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_rollypay")
    async def ltegb_pay_rollypay_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП временно недоступна.")
            await state.clear()
            return
        data = await state.get_data()
        price = Decimal(str(data.get('lte_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        size_gb = data.get('lte_package_size_gb')
        payment_id = str(uuid.uuid4())
        metadata = _lte_gb_metadata(data, user_id, "RollyPay", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=price, payment_id=payment_id, description=f"Докупка {size_gb} ГБ LTE",
            customer_id=str(user_id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже.")
            await state.clear()
            return
        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, user_id, float(price), metadata2)
        except Exception:
            pass
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_heleket")
    async def ltegb_pay_heleket_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('lte_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        state_data = {
            "action": "lte_gb_topup",
            "customer_email": None,
            "plan_id": None,
            "package_id": data.get('lte_package_id'),
            "host_name": None,
            "key_id": data.get('lte_key_id'),
        }
        try:
            pay_url = await _create_heleket_payment_request(
                user_id=user_id,
                price=price,
                months=0,
                host_name="",
                state_data=state_data
            )
            if pay_url:
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_payment_keyboard(pay_url)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create lte-gb Heleket invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_cryptobot")
    async def ltegb_pay_cryptobot_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт в Crypto Pay...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('lte_package_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        state_data = {
            "action": "lte_gb_topup",
            "customer_email": None,
            "plan_id": None,
            "package_id": data.get('lte_package_id'),
            "host_name": None,
            "key_id": data.get('lte_key_id'),
        }
        try:
            result = await _create_cryptobot_invoice(
                user_id=user_id,
                price_rub=price,
                months=0,
                host_name="",
                state_data=state_data,
            )
            if result:
                pay_url, invoice_id = result
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_cryptobot_payment_keyboard(pay_url, invoice_id)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create lte-gb CryptoBot invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_yoomoney")
    async def ltegb_pay_yoomoney_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю YooMoney...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('lte_package_price', 0)))
        wallet = get_setting("yoomoney_wallet")
        secret = get_setting("yoomoney_secret")
        if not wallet or not secret or price <= 0:
            await callback.message.edit_text("❌ YooMoney временно недоступен.")
            await state.clear()
            return
        w = (wallet or "").strip()
        if not (w.isdigit() and len(w) >= 11):
            await callback.message.edit_text("❌ Некорректный номер кошелька YooMoney.")
            await state.clear()
            return
        if price < Decimal("1.00"):
            await callback.message.edit_text("❌ Минимальная сумма перевода YooMoney — 1 RUB.")
            await state.clear()
            return
        payment_id = str(uuid.uuid4())
        metadata = _lte_gb_metadata(data, user_id, "YooMoney", payment_id)
        create_payload_pending(payment_id, user_id, float(price), metadata)
        pay_url = _build_yoomoney_link(wallet, price, payment_id)
        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_yoomoney_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == "ltegb_pay_stars")
    async def ltegb_pay_stars_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('lte_package_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена пакета.")
            await state.clear()
            return
        try:
            stars_ratio = Decimal(get_setting("stars_per_rub") or '0')
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return
        stars_amount = int((price * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP)) or 1
        payment_id = str(uuid.uuid4())
        metadata = _lte_gb_metadata(data, user_id, "Telegram Stars", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.error(f"lte-gb Stars: не удалось создать pending: {e}", exc_info=True)
        size_gb = data.get('lte_package_size_gb')
        try:
            await callback.message.answer_invoice(
                title="Докупка LTE",
                description=f"Докупка {size_gb} ГБ LTE-трафика",
                prices=[LabeledPrice(label="Докупка LTE", amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to create lte-gb Stars invoice: {e}")
            await callback.message.edit_text("❌ Не удалось создать счёт в Stars.")
            await state.clear()

    def _resolve_key_for_main_reset(key_id: int, user_id: int) -> dict | None:
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            return None
        return key_data

    @user_router.callback_query(F.data.startswith("main_reset_start_"))
    @registration_required
    async def main_reset_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.answer("Ошибка данных", show_alert=True)
            return

        key_data = _resolve_key_for_main_reset(key_id, user_id)
        if not key_data:
            await callback.message.edit_text("❌ Ключ не найден.", reply_markup=keyboards.create_back_to_menu_keyboard())
            return

        plan = None
        try:
            plan_id_for_key = _resolve_plan_id_for_key(key_data)
            if plan_id_for_key:
                plan = get_plan_by_id(plan_id_for_key)
        except Exception:
            plan = None

        plan_traffic_limit = int((plan or {}).get('traffic_limit_bytes') or 0)
        if not plan or plan_traffic_limit <= 0:
            await callback.message.edit_text(
                "❌ Для тарифа этого ключа сброс основного трафика недоступен (тариф безлимитный).",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        try:
            price = float(plan.get('main_reset_price_rub') or 0)
        except Exception:
            price = 0.0
        if price <= 0:
            await callback.message.edit_text(
                "❌ Платный сброс основного трафика не настроен для этого тарифа. Обратитесь к администратору.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return

        # Дата ближайшего бесплатного (планового) сброса основного трафика по тарифу
        next_free_reset_txt = "—"
        next_reset_raw = key_data.get('next_traffic_reset_at')
        if next_reset_raw:
            try:
                next_reset_dt = datetime.fromisoformat(str(next_reset_raw).replace(' ', 'T'))
                next_free_reset_txt = next_reset_dt.strftime('%d.%m.%Y')
            except Exception:
                pass

        await state.update_data(main_reset_key_id=key_id, main_reset_price=price)
        try:
            main_balance = get_balance(user_id)
        except Exception:
            main_balance = 0.0

        await callback.message.edit_text(
            "♻️ Сбросить лимит обычного трафика\n\n"
            f"Стоимость: {price:.0f} RUB.\n\n"
            "После оплаты счётчик обычного трафика обнулится моментально, а лимит и история "
            "Мобильного LTE останутся прежними.\n\n"
            f"Следующий бесплатный сброс по тарифу: {next_free_reset_txt}.\n\n"
            f"Ваш баланс: {main_balance:.0f} RUB\n\n"
            "Выберите способ оплаты:",
            reply_markup=keyboards.create_main_reset_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(MainPoolReset.waiting_for_method)

    def _main_reset_metadata(data: dict, user_id: int, payment_method: str, payment_id: str) -> dict:
        price = float(data.get('main_reset_price', 0))
        return {
            "user_id": int(user_id),
            "price": price,
            "action": "main_traffic_reset",
            "key_id": data.get('main_reset_key_id'),
            "payment_method": payment_method,
            "payment_id": payment_id,
        }

    @user_router.callback_query(MainPoolReset.waiting_for_method, F.data == "mainreset_pay_balance")
    async def mainreset_pay_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('main_reset_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена.")
            await state.clear()
            return
        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на балансе.", show_alert=True)
            return
        payment_id = f"balance:{user_id}:{uuid.uuid4()}"
        metadata = _main_reset_metadata(data, user_id, "Balance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(MainPoolReset.waiting_for_method, F.data == "mainreset_pay_referral_balance")
    async def mainreset_pay_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        price = float(data.get('main_reset_price', 0))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена.")
            await state.clear()
            return
        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return
        payment_id = f"referral_balance:{user_id}:{uuid.uuid4()}"
        metadata = _main_reset_metadata(data, user_id, "ReferralBalance", payment_id)
        metadata["chat_id"] = callback.message.chat.id
        metadata["message_id"] = callback.message.message_id
        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(MainPoolReset.waiting_for_method, F.data == "mainreset_pay_yookassa")
    async def mainreset_pay_yookassa_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key

        data = await state.get_data()
        user_id = callback.from_user.id
        price = Decimal(str(data.get('main_reset_price', 0)))
        if price <= 0:
            await callback.message.edit_text("❌ Некорректная цена.")
            await state.clear()
            return
        description = "Досрочный сброс основного пула трафика"
        payment_id = str(uuid.uuid4())
        price_str = f"{price:.2f}"
        metadata = _main_reset_metadata(data, user_id, "YooKassa", payment_id)
        try:
            create_payload_pending(payment_id, user_id, float(price), metadata)
        except Exception as e:
            logger.warning(f"YooKassa main-reset: не удалось создать pending: {e}")
        try:
            payment_payload = {
                "amount": {"value": price_str, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": payment_id}
            }
            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, user_id, float(price), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa main-reset: не удалось сохранить provider id: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa main-reset payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    @user_router.callback_query(F.data == "top_up_start")
    @registration_required
    async def topup_start_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Введите сумму пополнения в рублях (например, 300):\nМинимум: 10 RUB, максимум: 100000 RUB",
            reply_markup=keyboards.create_back_to_menu_keyboard()
        )
        await state.set_state(TopUpProcess.waiting_for_amount)

    @user_router.message(TopUpProcess.waiting_for_amount)
    async def topup_amount_input(message: types.Message, state: FSMContext):
        text = (message.text or "").replace(",", ".").strip()
        try:
            amount = Decimal(text)
        except Exception:
            await message.answer("❌ Введите корректную сумму, например: 300", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        if amount < Decimal("10"):
            await message.answer("❌ Минимальная сумма пополнения: 10 RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        if amount > Decimal("100000"):
            await message.answer("❌ Максимальная сумма пополнения: 100000 RUB", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        final_amount = amount.quantize(Decimal("0.01"))
        await state.update_data(topup_amount=float(final_amount))
        await message.answer(
            f"К пополнению: {final_amount:.2f} RUB\nВыберите способ оплаты:",
            reply_markup=keyboards.create_topup_payment_method_keyboard(PAYMENT_METHODS)
        )
        await state.set_state(TopUpProcess.waiting_for_topup_method)

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_yookassa")
    async def topup_pay_yookassa(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        
        # Ensure YooKassa configuration is set
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
            
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key
        
        data = await state.get_data()
        amount = Decimal(str(data.get('topup_amount', 0)))
        if amount <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return
        user_id = callback.from_user.id
        price_str_for_api = f"{amount:.2f}"
        price_float_for_metadata = float(amount)

        try:

            customer_email = get_setting("receipt_email")
            receipt = None
            if customer_email and is_valid_email(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": f"Пополнение баланса",
                        "quantity": "1.00",
                        "amount": {"value": price_str_for_api, "currency": "RUB"},
                        "vat_code": "1",
                        "payment_subject": "service",
                        "payment_mode": "full_payment"
                    }]
                }

            payment_id = str(uuid.uuid4())
            metadata = {
                "user_id": int(user_id),
                "price": float(price_float_for_metadata),
                "action": "top_up",
                "payment_method": "YooKassa",
                "payment_id": payment_id,
            }
            try:
                create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata)
            except Exception as e:
                logger.warning(f"YooKassa topup: не удалось создать pending для {payment_id}: {e}")

            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": f"Пополнение баланса на {price_str_for_api} RUB",
                "metadata": {"payment_id": payment_id}
            }
            if receipt:
                payment_payload['receipt'] = receipt
            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa topup: не удалось сохранить provider id для {payment_id}: {e}")
            await state.clear()
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Не удалось создать платеж пополнения YooKassa: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()


    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_stars")
    async def create_stars_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        user_id = callback.from_user.id

        price_rub = Decimal(str(data.get('final_price', plan['price'])))
        try:
            stars_ratio_raw = get_setting("stars_per_rub") or '0'
            stars_ratio = Decimal(stars_ratio_raw)
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return

        stars_amount = int((price_rub * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if stars_amount <= 0:
            stars_amount = 1

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)

        payment_id = str(uuid.uuid4())
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
            "payment_method": "Telegram Stars",
            "payment_id": payment_id,
        }
        try:
            ok = create_payload_pending(payment_id, user_id, float(price_rub), metadata)
            logger.info(f"Создано ожидание Stars: ok={ok}, payment_id={payment_id}, user_id={user_id}, price_rub={price_rub}")
        except Exception as e:
            logger.error(f"Не удалось создать ожидание для Stars payment_id={payment_id}: {e}", exc_info=True)
            ok = False
        if not ok:
            await callback.message.answer("❌ Не удалось подготовить оплату Stars. Попробуйте ещё раз.")
            return

        title = f"Подписка на {duration_label}"
        description = f"Оплата VPN на {duration_label}"
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        try:
            invoice_msg = await callback.message.answer_invoice(
                title=title,
                description=description,
                prices=[LabeledPrice(label=title, amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
                reply_markup=keyboards.create_stars_invoice_keyboard(),
            )
            invoice_chat_id = getattr(getattr(invoice_msg, "chat", None), "id", None) or callback.message.chat.id
            invoice_message_id = getattr(invoice_msg, "message_id", None)
            await state.update_data(
                stars_payment_id=payment_id,
                stars_invoice_chat_id=invoice_chat_id,
                stars_invoice_message_id=invoice_message_id,
            )
            await state.set_state(PaymentProcess.waiting_for_stars_invoice)
        except Exception as e:
            logger.error(f"Не удалось создать счет Stars: {e}")
            try:
                cancel_pending_transaction(payment_id, user_id)
            except Exception:
                pass
            try:
                await callback.message.answer("❌ Не удалось создать счёт в Stars. Попробуйте другой способ оплаты.")
            except Exception:
                pass

    @user_router.callback_query(F.data == "payment_stars_back")
    async def payment_stars_back_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        user_id = callback.from_user.id
        data = await state.get_data()
        pid = str(data.get("stars_payment_id") or "").strip()
        status = (get_pending_status(pid) or "").lower() if pid else ""

        if status == "paid":
            await callback.answer("Оплата уже подтверждена.", show_alert=True)
            return

        if pid and status == "pending":
            meta = get_pending_metadata(pid) or {}
            try:
                owner_id = int(meta.get("user_id") or 0)
            except (TypeError, ValueError):
                owner_id = 0
            if owner_id and owner_id != user_id:
                await callback.answer("Счёт уже недействителен.", show_alert=True)
                return
            cancel_pending_transaction(pid, user_id)

        if not data.get("plan_id"):
            await callback.answer(
                "Сессия оплаты устарела. Выберите тариф и способ оплаты заново.",
                show_alert=True,
            )
            return

        chat_id = data.get("stars_invoice_chat_id") or (
            callback.message.chat.id if callback.message else None
        )
        message_id = data.get("stars_invoice_message_id") or (
            callback.message.message_id if callback.message else None
        )
        if chat_id and message_id:
            try:
                await bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
            except TelegramBadRequest:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=int(chat_id), message_id=int(message_id), reply_markup=None
                    )
                except Exception:
                    pass
            except Exception:
                pass

        await state.update_data(
            stars_payment_id=None,
            stars_invoice_chat_id=None,
            stars_invoice_message_id=None,
        )
        await state.set_state(PaymentProcess.waiting_for_payment_method)
        await callback.answer()
        try:
            await show_payment_options(callback.message, state)
        except Exception:
            logger.error("payment_stars_back: failed to restore payment methods", exc_info=True)

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_stars")
    async def topup_stars_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю счёт в Telegram Stars...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения.")
            await state.clear()
            return
        try:
            stars_ratio_raw = get_setting("stars_per_rub") or '0'
            stars_ratio = Decimal(stars_ratio_raw)
        except Exception:
            stars_ratio = Decimal('0')
        if stars_ratio <= 0:
            await callback.message.edit_text("❌ Оплата в Stars временно недоступна.")
            await state.clear()
            return
        stars_amount = int((amount_rub * stars_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        if stars_amount <= 0:
            stars_amount = 1
        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "Telegram Stars",
            "payment_id": payment_id,
        }
        try:
            ok = create_payload_pending(payment_id, user_id, float(amount_rub), metadata)
            logger.info(f"Создано ожидание пополнения Stars: ok={ok}, payment_id={payment_id}, user_id={user_id}, amount_rub={amount_rub}")
        except Exception as e:
            logger.error(f"Не удалось создать ожидание для пополнения Stars payment_id={payment_id}: {e}", exc_info=True)
        try:
            await callback.message.answer_invoice(
                title="Пополнение баланса",
                description=f"Пополнение на {amount_rub:.2f} RUB",
                prices=[LabeledPrice(label="Пополнение", amount=stars_amount)],
                payload=payment_id,
                currency="XTR",
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Не удалось создать счет пополнения Stars: {e}")
            await callback.message.edit_text("❌ Не удалось создать счёт в Stars.")
            await state.clear()


    @user_router.pre_checkout_query()
    async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
        payload = ""
        try:
            payload = (pre_checkout_q.invoice_payload or "").strip()
        except Exception:
            payload = ""
        status = (get_pending_status(payload) or "").lower() if payload else ""
        if status in {"cancelled", "canceled", "paid"}:
            try:
                await pre_checkout_q.answer(
                    ok=False,
                    error_message="Этот счёт отменён. Выберите способ оплаты заново.",
                )
            except Exception:
                pass
            return
        try:
            await pre_checkout_q.answer(ok=True)
        except Exception:
            pass


    @user_router.message(F.successful_payment)
    async def stars_success_handler(message: types.Message, bot: Bot, state: FSMContext):
        try:
            payload = message.successful_payment.invoice_payload if message.successful_payment else None
        except Exception:
            payload = None
        if not payload:
            return
        status = (get_pending_status(payload) or "").lower()
        if status in {"cancelled", "canceled"}:
            logger.info(f"Платеж Stars: игнорируем отменённый invoice payload={payload}")
            return
        metadata = find_and_complete_pending_transaction(payload)
        if not metadata:
            logger.warning(f"Платеж Stars: метаданные не найдены для payload {payload}")

            try:
                fallback = get_latest_pending_for_user(message.from_user.id)
            except Exception as e:
                fallback = None
                logger.error(f"Платеж Stars: не удалось найти резервные данные для пользователя {message.from_user.id}: {e}", exc_info=True)
            if fallback and (fallback.get('payment_method') == 'Telegram Stars'):
                pid = fallback.get('payment_id') or payload
                logger.info(f"Платеж Stars: используем резервные данные для пользователя {message.from_user.id}, pid={pid}")
                metadata = find_and_complete_pending_transaction(pid)
        if not metadata:

            try:
                total_stars = int(getattr(message.successful_payment, 'total_amount', 0) or 0)
            except Exception:
                total_stars = 0
            try:
                stars_ratio_raw = get_setting("stars_per_rub") or '0'
                stars_ratio = Decimal(stars_ratio_raw)
            except Exception:
                stars_ratio = Decimal('0')
            if total_stars > 0 and stars_ratio > 0:
                amount_rub = (Decimal(total_stars) / stars_ratio).quantize(Decimal('0.01'))
                metadata = {
                    "user_id": message.from_user.id,
                    "price": float(amount_rub),
                    "action": "top_up",
                    "payment_method": "Telegram Stars",
                    "payment_id": payload,
                }
                logger.info(f"Платеж Stars: восстанавливаем пополнение из total_stars={total_stars}, ratio={stars_ratio}, amount_rub={amount_rub}")
            else:

                logger.warning("Платеж Stars: не удалось восстановить метаданные платежа; пропускаем")
                return

        try:
            if message.from_user and message.from_user.username:
                metadata.setdefault('tg_username', message.from_user.username)
        except Exception:
            pass
        await process_successful_payment(bot, metadata)
        try:
            await state.clear()
        except Exception:
            pass



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
        method = (get_setting("rollypay_payment_method") or "sbp").strip()
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

    
    @user_router.callback_query(F.data.startswith("check_platega:"))
    async def check_platega_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return

        # сначала проверим локально
        try:
            status = (get_pending_status(pid) or "").lower()
        except Exception:
            status = ""
        if status == "paid":
            await callback.answer("✅ Оплата уже получена и обработана.", show_alert=True)
            return

        meta = None
        try:
            meta = _get_pending_metadata(pid)
        except Exception:
            meta = None
        txid = None
        if isinstance(meta, dict):
            txid = meta.get("platega_transaction_id") or meta.get("transaction_id")

        if not txid:
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        remote = await _get_platega_transaction(str(txid))
        if not remote:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return

        remote_status = str(remote.get("status") or "").upper()
        if remote_status == "CONFIRMED":
            metadata = find_and_complete_pending_transaction(pid)
            if not metadata:
                await callback.answer("✅ Оплата подтверждена, но транзакция уже обработана.", show_alert=True)
                return
            try:
                await process_successful_payment(bot, metadata)
                await callback.answer("✅ Оплата получена! Обрабатываю…", show_alert=True)
            except Exception as e:
                logger.error(f"Platega manual check: process_successful_payment failed: {e}", exc_info=True)
                await callback.answer("⚠️ Оплата получена, но обработка не завершена. Напишите в поддержку.", show_alert=True)
            return

        if remote_status in {"FAILED", "CANCELED", "EXPIRED"}:
            await callback.answer(f"❌ Платеж завершился со статусом: {remote_status}", show_alert=True)
            return

        await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)

    @user_router.callback_query(F.data.startswith("check_rollypay:"))
    async def check_rollypay_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return

        try:
            status = (get_pending_status(pid) or "").lower()
        except Exception:
            status = ""
        if status == "paid":
            await callback.answer("✅ Оплата уже получена и обработана.", show_alert=True)
            return

        meta = None
        try:
            meta = _get_pending_metadata(pid)
        except Exception:
            meta = None
        if not isinstance(meta, dict) or str(meta.get("payment_method") or "") != "RollyPay":
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        txid = meta.get("rollypay_payment_id")
        if not txid:
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        from shop_bot.modules.rollypay_api import RollyPayAPI

        api_key = (get_setting("rollypay_api_key") or "").strip()
        if not api_key:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return
        remote = await RollyPayAPI(api_key, get_setting("rollypay_terminal_id") or "").get_payment(str(txid))
        if not remote:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return

        remote_status = str(remote.get("status") or "").strip().lower()
        if remote_status != "paid":
            if remote_status in {"expired", "canceled", "chargeback"}:
                await callback.answer(f"❌ Платеж завершился со статусом: {remote_status}", show_alert=True)
                return
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        if str(remote.get("order_id") or "").strip() != str(pid):
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        try:
            expected = Decimal(str(meta.get("price")))
            got = Decimal(str(remote.get("amount")))
        except Exception:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return
        if got.quantize(Decimal("0.01")) != expected.quantize(Decimal("0.01")):
            logger.warning("RollyPay manual check: amount mismatch payment_id=%s got=%s expected=%s", pid, got, expected)
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        metadata = find_and_complete_pending_transaction(pid)
        if not metadata:
            await callback.answer("✅ Оплата подтверждена, но транзакция уже обработана.", show_alert=True)
            return
        metadata.setdefault("payment_method", "RollyPay")
        metadata["rollypay_payment_id"] = str(txid)
        try:
            await process_successful_payment(bot, metadata)
            await callback.answer("✅ Оплата получена! Обрабатываю…", show_alert=True)
        except Exception as e:
            logger.error(f"RollyPay manual check: process_successful_payment failed: {e}", exc_info=True)
            await callback.answer("⚠️ Оплата получена, но обработка не завершена. Напишите в поддержку.", show_alert=True)

    @user_router.callback_query(F.data.startswith("check_yookassa:"))
    async def check_yookassa_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return

        status = ""
        try:
            status = (get_pending_status(pid) or "").lower()
        except Exception as e:
            logger.error(f"YooKassa manual check: failed to read local status for {pid}: {e}")
        if status == "paid":
            await callback.answer("✅ Оплата уже подтверждена. Профиль/баланс скоро обновится.", show_alert=True)
            return

        pending_meta = None
        try:
            pending_meta = get_pending_metadata(pid)
        except Exception as e:
            logger.error(f"YooKassa manual check: failed to read pending metadata for {pid}: {e}")

        if not pending_meta:
            await callback.answer("❌ Платёж не найден. Попробуйте позже.", show_alert=True)
            return

        provider_payment_id = (pending_meta.get("yookassa_payment_id") or "").strip()
        if not provider_payment_id:
            await callback.answer("⚠️ Не удалось проверить оплату. Попробуйте позже.", show_alert=True)
            return

        shop_id = (get_setting("yookassa_shop_id") or "").strip()
        secret_key = (get_setting("yookassa_secret_key") or "").strip()
        if not shop_id or not secret_key:
            await callback.answer("⚠️ YooKassa не настроен. Обратитесь к администратору.", show_alert=True)
            return

        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

        try:
            payment = Payment.find_one(provider_payment_id)
        except Exception as e:
            logger.error(f"YooKassa manual check: failed to fetch payment {provider_payment_id}: {e}", exc_info=True)
            await callback.answer("⚠️ Не удалось проверить оплату через YooKassa. Попробуйте позже.", show_alert=True)
            return

        remote_status = (getattr(payment, "status", "") or "").lower()
        if remote_status != "succeeded":
            if remote_status == "canceled":
                await callback.answer("❌ Платёж отменён.", show_alert=True)
                return
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        amount_obj = getattr(payment, "amount", None)
        if isinstance(amount_obj, dict):
            value_str = amount_obj.get("value")
            currency = (amount_obj.get("currency") or "").upper()
        else:
            value_str = getattr(amount_obj, "value", None)
            currency = (getattr(amount_obj, "currency", "") or "").upper()

        try:
            expected_amount = Decimal(str(pending_meta.get('price') or pending_meta.get('amount_rub') or '0')).quantize(Decimal('0.01'))
            got_amount = Decimal(str(value_str or '0')).quantize(Decimal('0.01'))
        except Exception as e:
            logger.warning(f"YooKassa manual check: amount parse error for {pid}: value={value_str} error={e}")
            await callback.answer("⚠️ Не удалось проверить сумму оплаты. Попробуйте позже.", show_alert=True)
            return

        if currency and currency != "RUB":
            logger.warning(f"YooKassa manual check: currency mismatch for {pid}: got={currency}, expected=RUB")
            await callback.answer("❌ Валюта платежа не совпадает. Обратитесь в поддержку.", show_alert=True)
            return
        if got_amount != expected_amount:
            logger.warning(f"YooKassa manual check: amount mismatch for {pid}: got={got_amount}, expected={expected_amount}")
            await callback.answer("❌ Сумма платежа не совпадает. Обратитесь в поддержку.", show_alert=True)
            return

        metadata = find_and_complete_pending_transaction(pid)
        if not metadata:
            await callback.answer("✅ Оплата подтверждена, но транзакция уже обработана.", show_alert=True)
            return
        try:
            await process_successful_payment(bot, metadata)
            await callback.answer("✅ Оплата получена! Обрабатываю…", show_alert=True)
        except Exception as e:
            logger.error(f"YooKassa manual check: process_successful_payment failed: {e}", exc_info=True)
            await callback.answer("⚠️ Оплата получена, но обработка не завершена. Напишите в поддержку.", show_alert=True)

    @user_router.callback_query(F.data.startswith("check_pending:"))
    async def check_pending_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return
        
        logger.info(f"🔍 Проверяем статус платежа: {pid}")
        
        try:
            status = get_pending_status(pid) or ""
            logger.info(f"📊 Локальный статус: {status}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки локального статуса для {pid}: {e}")
            status = ""
        if status and status.lower() == 'paid':
            logger.info(f"✅ Платеж уже обработан локально: {pid}")
            await callback.answer("✅ Оплата получена! Профиль/баланс скоро обновится.", show_alert=True)
            return


        token = (get_setting('yoomoney_api_token') or '').strip()
        if not token:
            logger.warning(f"⚠️ Нет токена API ЮMoney для платежа {pid}")
            if not status:
                await callback.answer("❌ Платёж не найден. Проверьте позже.", show_alert=True)
            else:
                await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)
            return

        try:
            logger.info(f"🌐 Проверяем платеж через API ЮMoney: {pid}")
            async with aiohttp.ClientSession() as session:
                data = {"label": pid, "records": "10"}
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                async with session.post("https://yoomoney.ru/api/operation-history", data=data, headers=headers, timeout=15) as resp:
                    text = await resp.text()
                    logger.info(f"📡 Ответ API: статус={resp.status}")
                    if resp.status != 200:
                        await callback.answer("⚠️ Не удалось проверить оплату через YooMoney. Попробуйте позже.", show_alert=True)
                        return
        except Exception as e:
            logger.error(f"💥 Ошибка проверки API для {pid}: {e}")
            await callback.answer("⚠️ Ошибка связи с YooMoney. Попробуйте позже.", show_alert=True)
            return
        try:
            payload = json.loads(text)
        except Exception as e:
            logger.error(f"💥 Не удалось разобрать ответ API: {e}")
            payload = {}
        ops = payload.get('operations') or []
        logger.info(f"📋 Найдено операций: {len(ops)}")
        paid = False
        for op in ops:
            try:
                op_label = str(op.get('label'))
                op_status = str(op.get('status','')).lower()
                if op_label == pid and op_status in {"success","done"}:
                    paid = True
                    logger.info(f"✅ Найдена оплаченная операция: {op_label} | {op_status}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Ошибка обработки операции: {e}")
                continue
        if paid:
            logger.info(f"🎉 Платеж подтвержден через API, обрабатываем: {pid}")
            try:
                metadata = find_and_complete_pending_transaction(pid)
            except Exception as e:
                logger.error(f"💥 Ошибка поиска ожидающей транзакции: {e}")
                metadata = None
            if metadata:
                try:
                    await process_successful_payment(bot, metadata)
                except Exception as e:
                    logger.error(f"💥 Ошибка в process_successful_payment: {e}")
            await callback.answer("✅ Оплата получена! Профиль/баланс скоро обновится.", show_alert=True)
            return

        logger.info(f"⏳ Платеж не найден или еще не оплачен: {pid}")
        await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)
    
    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_platega")
    async def topup_pay_platega(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega временно недоступен.")
            await state.clear()
            return

        data = await state.get_data()
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма.")
            await state.clear()
            return

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "Platega",
            "payment_id": payment_id,
        }
        create_payload_pending(payment_id, user_id, float(amount_rub), metadata)

        pay_url, txid = await _create_platega_payment_link(amount_rub=amount_rub, payment_id=payment_id, description="Пополнение баланса")
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, user_id, float(amount_rub), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_rollypay")
    async def topup_pay_rollypay(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП временно недоступна.")
            await state.clear()
            return

        data = await state.get_data()
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма.")
            await state.clear()
            return

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "RollyPay",
            "payment_id": payment_id,
        }
        create_payload_pending(payment_id, user_id, float(amount_rub), metadata)

        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=amount_rub, payment_id=payment_id, description="Пополнение баланса",
            customer_id=str(user_id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, user_id, float(amount_rub), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_heleket")
    async def topup_pay_heleket_like(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount = float(data.get('topup_amount', 0))
        if amount <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return

        state_data = {
            "action": "top_up",
            "customer_email": None,
            "plan_id": None,
            "host_name": None,
            "key_id": None,
        }
        try:
            pay_url = await _create_heleket_payment_request(
                user_id=user_id,
                price=float(amount),
                months=0,
                host_name="",
                state_data=state_data
            )
            if pay_url:
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_payment_keyboard(pay_url)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create topup Heleket-like invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_cryptobot")
    async def topup_pay_cryptobot(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счёт в Crypto Pay...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount = float(data.get('topup_amount', 0))
        if amount <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return
        state_data = {
            "action": "top_up",
            "customer_email": None,
            "plan_id": None,
            "host_name": None,
            "key_id": None,
        }
        try:
            result = await _create_cryptobot_invoice(
                user_id=user_id,
                price_rub=float(amount),
                months=0,
                host_name="",
                state_data=state_data,
            )
            if result:
                pay_url, invoice_id = result
                await callback.message.edit_text(
                    "Нажмите на кнопку ниже для оплаты:",
                    reply_markup=keyboards.create_cryptobot_payment_keyboard(pay_url, invoice_id)
                )
                await state.clear()
            else:
                await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
        except Exception as e:
            logger.error(f"Failed to create CryptoBot topup invoice: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")
            await state.clear()

    @user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == "topup_pay_tonconnect")
    async def topup_pay_tonconnect(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Готовлю TON Connect...")
        data = await state.get_data()
        user_id = callback.from_user.id
        amount_rub = Decimal(str(data.get('topup_amount', 0)))
        if amount_rub <= 0:
            await callback.message.edit_text("❌ Некорректная сумма пополнения. Повторите ввод.")
            await state.clear()
            return

        wallet_address = get_setting("ton_wallet_address")
        if not wallet_address:
            await callback.message.edit_text("❌ Оплата через TON временно недоступна.")
            await state.clear()
            return

        usdt_rub_rate = await get_usdt_rub_rate()
        ton_usdt_rate = await get_ton_usdt_rate()
        if not usdt_rub_rate or not ton_usdt_rate:
            await callback.message.edit_text("❌ Не удалось получить курс TON. Попробуйте позже.")
            await state.clear()
            return

        price_ton = (amount_rub / usdt_rub_rate / ton_usdt_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        amount_nanoton = int(price_ton * 1_000_000_000)

        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id,
            "price": float(amount_rub),
            "action": "top_up",
            "payment_method": "TON Connect",
            "expected_amount_ton": float(price_ton)
        }
        create_pending_transaction(payment_id, user_id, float(amount_rub), metadata)

        transaction_payload = {
            'messages': [{'address': wallet_address, 'amount': str(amount_nanoton), 'payload': payment_id}],
            'valid_until': int(datetime.now().timestamp()) + 600
        }

        try:
            connect_url = await _start_ton_connect_process(user_id, transaction_payload)
            qr_img = qrcode.make(connect_url)
            bio = BytesIO(); qr_img.save(bio, "PNG"); qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer_photo(
                photo=qr_file,
                caption=(
                    f"💎 Оплата через TON Connect\n\n"
                    f"Сумма к оплате: `{price_ton}` TON\n\n"
                    f"Нажмите кнопку ниже, чтобы открыть кошелёк и подтвердить перевод."
                ),
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()
        except Exception as e:
            logger.error(f"Failed to start TON Connect topup: {e}", exc_info=True)
            await callback.message.edit_text("❌ Не удалось подготовить оплату TON Connect.")
            await state.clear()

    @user_router.callback_query(F.data == "show_referral_program")
    @registration_required
    async def referral_program_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_data = get_user(user_id)
        bot_username = (await callback.bot.get_me()).username

        webapp_link, referral_link = _build_referral_links(user_id, bot_username)
        referral_count = get_referral_count(user_id)
        try:
            total_ref_earned = float(get_referral_balance_all(user_id))
        except Exception:
            total_ref_earned = 0.0
        try:
            available_ref_balance = float(get_referral_balance(user_id))
        except Exception:
            available_ref_balance = 0.0

        # Referral bonuses text is driven by admin settings
        def _to_float_setting(key: str, default: float) -> float:
            raw = str(get_setting(key) or str(default)).strip()
            try:
                raw = raw.replace(",", ".")
                return float(raw)
            except Exception:
                return float(default)

        def _is_true_setting(key: str, default: bool = False) -> bool:
            raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
            return raw in {"1", "true", "yes", "on", "y"}

        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip() or "percent_purchase"
        percent = _to_float_setting("referral_percentage", 10.0)
        fixed_amount = _to_float_setting("fixed_referral_bonus_amount", 50.0)
        start_bonus = _to_float_setting("referral_on_start_referrer_amount", 20.0)
        days_bonus_enabled = _is_true_setting("enable_referral_days_bonus", default=True)

        def _fmt_num(x: float, decimals: int = 2) -> str:
            try:
                s = f"{x:.{decimals}f}"
                return s.rstrip("0").rstrip(".")
            except Exception:
                return str(x)

        if reward_type == "fixed_purchase":
            main_bonus = f"{_fmt_num(fixed_amount, 2)} ₽ бонуса"
        elif reward_type == "fixed_start_referrer":
            main_bonus = f"{_fmt_num(start_bonus, 2)} ₽ бонуса при старте"
        else:
            main_bonus = f"{_fmt_num(percent, 2)}% бонуса"

        extra_bonus = " +1 день подписки" if days_bonus_enabled else ""
        bonuses_line = f"<b>🏆 Бонусы за приглашения:</b>🌟 {main_bonus}{extra_bonus}"

        withdraw_enabled = _ref_withdraw_enabled()
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        can_withdraw_now = withdraw_enabled and available_ref_balance >= min_withdraw

        text_lines = [
            "👥 <b>Реферальная программа</b>",
            "",
        ]
        if referral_link:
            text_lines.append(f"<b>Ссылка в Telegram:</b>\n<code>{html_escape(referral_link)}</code>")
            text_lines.append("")
        if webapp_link:
            text_lines.append(f"<b>Ссылка на сайт:</b>\n<code>{html_escape(webapp_link)}</code>")
            text_lines.append("")
        text_lines.extend([
            "<b>🤝 Приглашайте друзей и получайте бонусы на каждом уровне! 💰</b>",
            "",
            bonuses_line,
            "",
            "<b>📊 Статистика приглашений:</b>",
            f"<b>👥 Приглашено пользователей:</b> {referral_count}",
            "",
            f"<b>💰 Заработано по рефералке (всего):</b> {total_ref_earned:.2f} ₽",
            f"<b>💼 Доступно к выводу:</b> {available_ref_balance:.2f} ₽",
        ])
        if withdraw_enabled:
            text_lines.append(f"<b>ℹ️ Минимальная сумма для вывода:</b> {min_withdraw:.0f} ₽")
        text = "\n".join(text_lines)

        share_text = _referral_share_text()

        builder = InlineKeyboardBuilder()
        if referral_link:
            share_tg = _telegram_share_url(referral_link, share_text)
            builder.button(
                text="📩 Поделиться (Telegram)" if webapp_link else "📩 Поделиться",
                url=share_tg,
            )
        if webapp_link:
            share_web = _telegram_share_url(webapp_link, share_text)
            builder.button(text="🌐 Поделиться (сайт)", url=share_web)
        builder.button(text="🔄 Перевести на баланс", callback_data="referral_transfer_start")
        if can_withdraw_now:
            builder.button(text="💸 Вывести", callback_data="referral_withdraw_start")
        if withdraw_enabled:
            builder.button(text="🧾 Способы получения", callback_data="referral_payout_methods")
            builder.button(text="📋 Запросы на вывод", callback_data="referral_withdraw_requests")
        builder.button(text="🏆 Топ-5", callback_data="show_referral_top")
        builder.button(text="⬅️ Назад", callback_data="back_to_main_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup(), disable_web_page_preview=True
        )


    
    @user_router.callback_query(F.data == "show_referral_top")
    @registration_required
    async def referral_top_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id

        rank, personal_count = get_referral_rank_and_count(user_id)
        top_users = get_referral_top_rich(5)

        lines: list[str] = []
        lines.append(
            "Здесь можно увидеть топ людей, которые пригласили "
            "наибольшее количество рефералов в сервис.\n"
            "Учитываются те богачи, которые пополнили баланс хотя бы раз.\n"
        )

        lines.append("\n<b>Твоё место в рейтинге:</b>")
        if rank is not None and personal_count > 0:
            lines.append(f"\n{rank}. <code>{user_id}</code> - {personal_count} чел.")
        else:
            lines.append(
                "\nПока ты не участвуешь в рейтинге. "
                "Пригласи пользователей, которые пополнят баланс, "
                "и появишься здесь."
            )

        lines.append("\n\n<b>🏆 Топ-5 пригласивших:</b>\n")
        if top_users:
            for index, row in enumerate(top_users, start=1):
                uid = row.get("telegram_id") or row.get("referred_by")
                count = int(row.get("rich_referrals") or row.get("ref_count") or 0)
                uid_str = str(uid)
                if len(uid_str) > 5:
                    masked = uid_str[:5] + "*****"
                else:
                    masked = uid_str + "*****"
                lines.append(f"<blockquote>{index}. {masked} - {count} чел.</blockquote>")
        else:
            lines.append("\n\nПока ещё нет пользователей, которые попали бы в рейтинг.")

        text = "\n".join(lines)

        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="show_referral_program")
        builder.button(text="🏠 Главное меню", callback_data="back_to_main_menu")
        builder.adjust(1, 1)
        await callback.message.edit_text(text, reply_markup=builder.as_markup())


    # =============================
    # Referral balance / withdrawal
    # =============================

    def _ref_is_true(key: str, default: bool = False) -> bool:
        raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
        return raw in {"1", "true", "yes", "on", "y"}

    def _ref_float_setting(key: str, default: float) -> float:
        raw = str(get_setting(key) or str(default)).strip().replace(",", ".")
        try:
            return float(raw)
        except Exception:
            return float(default)

    def _ref_withdraw_enabled() -> bool:
        return _ref_is_true("referral_withdraw_enabled", False)

    def _ref_method_enabled(method_type: str) -> dict:
        return {
            "sbp": _ref_is_true("referral_withdraw_sbp_enabled", False),
            "card": _ref_is_true("referral_withdraw_card_enabled", False),
            "usdt_trc20": _ref_is_true("referral_withdraw_usdt_enabled", False),
        }.get(method_type, False)

    def _ref_sbp_banks() -> list[str]:
        raw = get_setting("referral_withdraw_sbp_banks") or ""
        return [b.strip() for b in raw.split(",") if b.strip()]

    _REF_METHOD_LABELS = {"sbp": "СБП", "card": "Номер карты", "usdt_trc20": "USDT TRC20"}

    def _ref_mask(value: str) -> str:
        s = (value or "").strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return html_escape(s)
        last4 = digits[-4:]
        return "*" * max(0, len(digits) - 4) + last4

    def _kb_my_balance(withdraw_enabled: bool, can_withdraw_now: bool = False) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="🔄 Перевести на баланс", callback_data="referral_transfer_start")
        if can_withdraw_now:
            b.button(text="💸 Вывести", callback_data="referral_withdraw_start")
        if withdraw_enabled:
            b.button(text="🧾 Способы получения", callback_data="referral_payout_methods")
            b.button(text="📋 Запросы на вывод", callback_data="referral_withdraw_requests")
        b.button(text="⬅️ Назад", callback_data="show_referral_program")
        b.adjust(1)
        return b.as_markup()

    @user_router.callback_query(F.data == "referral_my_balance")
    @registration_required
    async def referral_my_balance(callback: types.CallbackQuery, state: FSMContext):
        # Оставлено для обратной совместимости со старыми сообщениями/кнопками —
        # теперь баланс отображается прямо на экране "Реферальная программа".
        await callback.answer()
        try:
            await state.clear()
        except Exception:
            pass
        await referral_program_handler(callback)

    _REF_STATUS_LABELS = {
        "new": "🕓 На рассмотрении",
        "processing": "⏳ В обработке",
        "paid": "✅ Выплачено",
        "rejected": "❌ Отклонено",
    }

    @user_router.callback_query(F.data == "referral_withdraw_requests")
    @catch_callback_errors
    async def referral_withdraw_requests(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        user_id = cb.from_user.id
        requests = list_referral_withdrawal_requests(user_id=user_id) or []
        lines = ["📋 <b>Запросы на вывод</b>", ""]
        if not requests:
            lines.append("У вас пока нет заявок на вывод средств.")
        else:
            for r in requests[:20]:
                status = _REF_STATUS_LABELS.get(r.get("status"), r.get("status"))
                amount = float(r.get("amount") or 0.0)
                label = _REF_METHOD_LABELS.get(r.get("method_type"), r.get("method_type"))
                masked = _ref_mask(str(r.get("requisite_value") or ""))
                extra = f" ({r.get('bank_name')})" if r.get("bank_name") else ""
                created = r.get("created_at") or ""
                lines.append(
                    f"• <b>{amount:.2f} ₽</b> — {label}{extra} •{masked}\n"
                    f"  Статус: {status}\n"
                    f"  Дата: {created}"
                )
                if r.get("status") == "rejected" and r.get("reject_reason"):
                    lines.append(f"  Причина: {html_escape(str(r.get('reject_reason')))}")
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Назад", callback_data="show_referral_program")
        b.adjust(1)
        await cb.message.edit_text("\n".join(lines), reply_markup=b.as_markup(), disable_web_page_preview=True)
        await fast_callback_answer(cb)


    @user_router.callback_query(F.data == "referral_transfer_start")
    @catch_callback_errors
    async def referral_transfer_start(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        user_id = cb.from_user.id
        balance = float(get_referral_balance(user_id) or 0.0)
        if balance <= 0:
            await cb.answer("На реферальном балансе нет средств.", show_alert=True)
            return
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="referral_my_balance")
        b.adjust(1)
        await state.set_state(ReferralWithdraw.waiting_transfer_amount)
        await cb.message.edit_text(
            f"🔄 <b>Перевод на основной баланс</b>\n\nДоступно на реферальном балансе: <b>{balance:.2f} ₽</b>\n\n"
            f"Введите сумму для перевода (например: <code>{balance:.0f}</code>), "
            f"минимальная сумма не ограничена:",
            reply_markup=b.as_markup(),
        )
        await fast_callback_answer(cb)

    @user_router.message(ReferralWithdraw.waiting_transfer_amount)
    @registration_required
    async def referral_transfer_amount(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer("Не понял сумму. Пришлите число, например 100.")
            return
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
        current = float(get_referral_balance(user_id) or 0.0)
        if amount > current:
            await message.answer(f"На реферальном балансе недостаточно средств. Доступно: {current:.2f} ₽.")
            return
        if not deduct_from_referral_balance(user_id, amount):
            await message.answer("❌ Не удалось списать средства с реферального баланса. Попробуйте позже.")
            return
        ok = add_to_balance(user_id, amount)
        if not ok:
            # Откатываем списание, если зачисление не удалось
            try:
                add_to_referral_balance(user_id, amount)
            except Exception:
                logger.error(f"Не удалось откатить перевод реферального баланса для {user_id} после неудачного зачисления.")
            await message.answer("❌ Не удалось зачислить средства на основной баланс. Попробуйте позже.")
            return
        try:
            log_username = message.from_user.username or f"@{user_id}"
            log_transaction(
                username=log_username,
                transaction_id=None,
                payment_id=str(uuid.uuid4()),
                user_id=user_id,
                status='paid',
                amount_rub=amount,
                amount_currency=None,
                currency_name=None,
                payment_method='ReferralTransfer',
                metadata=json.dumps({"action": "referral_transfer"})
            )
        except Exception as e:
            logger.warning(f"Не удалось залогировать перевод реферального баланса для {user_id}: {e}")
        try:
            await state.clear()
        except Exception:
            pass
        new_ref_balance = float(get_referral_balance(user_id) or 0.0)
        new_main_balance = float(get_balance(user_id) or 0.0)
        withdraw_enabled_now = _ref_withdraw_enabled()
        min_withdraw_now = _ref_float_setting("minimum_withdrawal", 100.0)
        await message.answer(
            f"✅ Переведено {amount:.2f} ₽ на основной баланс.\n\n"
            f"Реферальный баланс: {new_ref_balance:.2f} ₽\n"
            f"Основной баланс: {new_main_balance:.2f} ₽",
            reply_markup=_kb_my_balance(withdraw_enabled_now, new_ref_balance >= min_withdraw_now)
        )

    def _kb_payout_methods(items: list[dict], withdraw_enabled: bool) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        if withdraw_enabled:
            b.button(text="➕ Добавить способ", callback_data="referral_payout_method_add")
        for m in items[:20]:
            mid = int(m.get("id") or 0)
            if mid <= 0:
                continue
            label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
            masked = _ref_mask(str(m.get("requisite_value") or ""))
            extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
            b.button(text=f"🗑 {label}{extra} •{masked}", callback_data=f"rpm_delete:{mid}")
        b.button(text="⬅️ Назад", callback_data="referral_my_balance")
        b.adjust(1)
        return b.as_markup()

    @user_router.callback_query(F.data == "referral_payout_methods")
    @catch_callback_errors
    async def referral_payout_methods(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        withdraw_enabled = _ref_withdraw_enabled()
        if not withdraw_enabled:
            await cb.answer("Вывод средств временно недоступен.", show_alert=True)
            return
        user_id = cb.from_user.id
        items = list_referral_payout_methods(user_id) or []
        lines = ["🧾 <b>Способы получения</b>", ""]
        if not items:
            lines.append("Пока нет сохранённых способов получения.\nНажмите «Добавить способ».")
        else:
            for i, m in enumerate(items, 1):
                label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
                masked = _ref_mask(str(m.get("requisite_value") or ""))
                extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
                lines.append(f"{i}. {label}{extra}: <code>{masked}</code>")
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=_kb_payout_methods(items, withdraw_enabled), disable_web_page_preview=True
        )
        await fast_callback_answer(cb)

    def _kb_method_types() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        if _ref_method_enabled("sbp"):
            b.button(text="🏦 СБП", callback_data="rpm_add_type:sbp")
        if _ref_method_enabled("card"):
            b.button(text="💳 Номер карты", callback_data="rpm_add_type:card")
        if _ref_method_enabled("usdt_trc20"):
            b.button(text="💵 USDT TRC20", callback_data="rpm_add_type:usdt_trc20")
        b.button(text="❌ Отмена", callback_data="referral_payout_methods")
        b.adjust(1)
        return b.as_markup()

    @user_router.callback_query(F.data == "referral_payout_method_add")
    @catch_callback_errors
    async def referral_payout_method_add(cb: types.CallbackQuery, state: FSMContext):
        if not _ref_withdraw_enabled():
            await cb.answer("Недоступно.", show_alert=True)
            return
        if not (_ref_method_enabled("sbp") or _ref_method_enabled("card") or _ref_method_enabled("usdt_trc20")):
            await cb.answer("Администратор пока не подключил ни одного способа получения.", show_alert=True)
            return
        await cb.message.edit_text(
            "Выберите способ получения:", reply_markup=_kb_method_types()
        )
        await fast_callback_answer(cb)

    def _kb_bank_choice(banks: list[str]) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        for i, bank in enumerate(banks[:30]):
            b.button(text=bank, callback_data=f"rpm_bank:{i}")
        b.button(text="❌ Отмена", callback_data="referral_payout_methods")
        b.adjust(2)
        return b.as_markup()

    @user_router.callback_query(F.data.startswith("rpm_add_type:"))
    @catch_callback_errors
    async def referral_payout_method_add_type(cb: types.CallbackQuery, state: FSMContext):
        method_type = (cb.data or "").split(":", 1)[1]
        if not _ref_method_enabled(method_type):
            await cb.answer("Этот способ временно недоступен.", show_alert=True)
            return
        await state.update_data(rpm_type=method_type)
        if method_type == "sbp":
            banks = _ref_sbp_banks()
            if not banks:
                await cb.answer("Список банков не настроен администратором.", show_alert=True)
                return
            await state.update_data(rpm_banks=banks)
            await state.set_state(ReferralWithdraw.waiting_method_bank)
            await cb.message.edit_text("🏦 Выберите банк:", reply_markup=_kb_bank_choice(banks))
        else:
            await state.set_state(ReferralWithdraw.waiting_method_value)
            prompt = "💳 Введите номер карты:" if method_type == "card" else "💵 Введите адрес кошелька USDT TRC20:"
            await cb.message.edit_text(prompt, reply_markup=_kb_payout_methods([], True))
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data.startswith("rpm_bank:"), ReferralWithdraw.waiting_method_bank)
    @catch_callback_errors
    async def referral_payout_method_bank_choice(cb: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        banks = data.get("rpm_banks") or []
        try:
            idx = int((cb.data or "").split(":", 1)[1])
            bank = banks[idx]
        except Exception:
            await cb.answer("Некорректный выбор.", show_alert=True)
            return
        await state.update_data(rpm_bank=bank)
        await state.set_state(ReferralWithdraw.waiting_method_value)
        await cb.message.edit_text(
            f"🏦 Банк: <b>{html_escape(bank)}</b>\n\nВведите номер телефона (СБП):",
        )
        await fast_callback_answer(cb)

    @user_router.message(ReferralWithdraw.waiting_method_value)
    @registration_required
    async def referral_payout_method_value(message: types.Message, state: FSMContext):
        data = await state.get_data()
        method_type = data.get("rpm_type")
        bank = data.get("rpm_bank")
        value = (message.text or "").strip()
        if not value:
            await message.answer("Значение не может быть пустым. Попробуйте снова.")
            return
        ok, msg, _new_id = add_referral_payout_method(message.from_user.id, method_type, value, bank_name=bank)
        await message.answer(("✅ " if ok else "❌ ") + msg)
        try:
            await state.clear()
        except Exception:
            pass
        items = list_referral_payout_methods(message.from_user.id) or []
        withdraw_enabled = _ref_withdraw_enabled()
        lines = ["🧾 <b>Способы получения</b>", ""]
        for i, m in enumerate(items, 1):
            label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
            masked = _ref_mask(str(m.get("requisite_value") or ""))
            extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
            lines.append(f"{i}. {label}{extra}: <code>{masked}</code>")
        await message.answer("\n".join(lines), reply_markup=_kb_payout_methods(items, withdraw_enabled))

    @user_router.callback_query(F.data.startswith("rpm_delete:"))
    @catch_callback_errors
    async def referral_payout_method_delete(cb: types.CallbackQuery, state: FSMContext):
        try:
            mid = int((cb.data or "").split(":", 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        ok, msg = delete_referral_payout_method(mid, cb.from_user.id)
        await cb.answer(("✅ " if ok else "❌ ") + msg, show_alert=not ok)
        items = list_referral_payout_methods(cb.from_user.id) or []
        withdraw_enabled = _ref_withdraw_enabled()
        lines = ["🧾 <b>Способы получения</b>", ""]
        if not items:
            lines.append("Пока нет сохранённых способов получения.")
        else:
            for i, m in enumerate(items, 1):
                label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
                masked = _ref_mask(str(m.get("requisite_value") or ""))
                extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
                lines.append(f"{i}. {label}{extra}: <code>{masked}</code>")
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=_kb_payout_methods(items, withdraw_enabled), disable_web_page_preview=True
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "referral_withdraw_start")
    @catch_callback_errors
    async def referral_withdraw_start(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        if not _ref_withdraw_enabled():
            await cb.answer("Вывод средств временно недоступен.", show_alert=True)
            return
        user_id = cb.from_user.id
        balance = float(get_referral_balance(user_id) or 0.0)
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        if balance < min_withdraw:
            await cb.answer(
                f"Минимальная сумма для вывода {min_withdraw:.0f} ₽. У вас {balance:.2f} ₽.", show_alert=True
            )
            return
        items = [
            m for m in (list_referral_payout_methods(user_id) or [])
            if _ref_method_enabled((m.get("method_type") or "").strip().lower())
        ]
        if not items:
            await cb.message.edit_text(
                "🧾 Сначала добавьте способ получения средств.",
                reply_markup=_kb_payout_methods([], True),
            )
            await fast_callback_answer(cb)
            return
        b = InlineKeyboardBuilder()
        for m in items[:20]:
            mid = int(m.get("id") or 0)
            label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
            masked = _ref_mask(str(m.get("requisite_value") or ""))
            extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
            b.button(text=f"{label}{extra} •{masked}", callback_data=f"rwd_method:{mid}")
        b.button(text="❌ Отмена", callback_data="referral_my_balance")
        b.adjust(1)
        await state.set_state(ReferralWithdraw.waiting_withdraw_choose_method)
        await cb.message.edit_text(
            f"💸 <b>Вывод средств</b>\n\nДоступно: <b>{balance:.2f} ₽</b>\n\nВыберите способ получения:",
            reply_markup=b.as_markup(),
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data.startswith("rwd_method:"), ReferralWithdraw.waiting_withdraw_choose_method)
    @catch_callback_errors
    async def referral_withdraw_choose_method(cb: types.CallbackQuery, state: FSMContext):
        try:
            mid = int((cb.data or "").split(":", 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        method = get_referral_payout_method(mid, cb.from_user.id)
        if not method:
            await cb.answer("Способ получения не найден.", show_alert=True)
            return
        balance = float(get_referral_balance(cb.from_user.id) or 0.0)
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        await state.update_data(rwd_method_id=mid)
        await state.set_state(ReferralWithdraw.waiting_withdraw_amount)
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="referral_withdraw_start")
        b.adjust(1)
        await cb.message.edit_text(
            f"Доступно: <b>{balance:.2f} ₽</b>\nМинимум: <b>{min_withdraw:.0f} ₽</b>\n\n"
            f"Введите сумму для вывода числом (например: <code>{min_withdraw:.0f}</code>):",
            reply_markup=b.as_markup(),
        )
        await fast_callback_answer(cb)

    @user_router.message(ReferralWithdraw.waiting_withdraw_amount)
    @registration_required
    async def referral_withdraw_amount(message: types.Message, state: FSMContext):
        if not _ref_withdraw_enabled():
            await message.answer("Вывод средств временно недоступен.")
            try:
                await state.clear()
            except Exception:
                pass
            return
        data = await state.get_data()
        method_id = data.get("rwd_method_id")
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer(f"Не понял сумму. Пришлите число, например {min_withdraw:.0f}.")
            return
        if amount < min_withdraw:
            await message.answer(f"Минимальная сумма для вывода: {min_withdraw:.0f} ₽.")
            return
        ok, msg, new_id = create_referral_withdrawal_request(message.from_user.id, amount, int(method_id))
        await message.answer(("✅ " if ok else "❌ ") + msg)
        if ok and new_id:
            method = get_referral_payout_method(int(method_id))
            admin_text = rw_repo.format_referral_withdrawal_admin_notice(
                request_id=new_id,
                user_id=message.from_user.id,
                username=message.from_user.username,
                amount=amount,
                method_type=(method or {}).get("method_type"),
                bank_name=(method or {}).get("bank_name"),
                requisite_value=(method or {}).get("requisite_value"),
            )
            for admin_id in (rw_repo.get_admin_ids() or set()):
                try:
                    await message.bot.send_message(int(admin_id), admin_text, parse_mode="HTML")
                except Exception:
                    logger.warning(
                        "Не удалось уведомить администратора %s о заявке на вывод",
                        admin_id,
                        exc_info=True,
                    )
        try:
            await state.clear()
        except Exception:
            pass
        withdraw_enabled = _ref_withdraw_enabled()
        balance = float(get_referral_balance(message.from_user.id) or 0.0)
        min_withdraw_now = _ref_float_setting("minimum_withdrawal", 100.0)
        lines = ["💼 <b>Мой баланс</b>", "", f"Реферальный баланс: <b>{balance:.2f} ₽</b>"]
        await message.answer("\n".join(lines), reply_markup=_kb_my_balance(withdraw_enabled, balance >= min_withdraw_now))


    @user_router.callback_query(F.data == "show_about")
    @registration_required
    async def about_handler(callback: types.CallbackQuery):
        await callback.answer()
        
        about_text = get_setting("about_text")
        terms_url = get_setting("terms_url")
        privacy_url = get_setting("privacy_url")
        channel_url = get_setting("channel_url")

        final_text = about_text if about_text else "Информация о проекте не добавлена."

        keyboard = keyboards.create_about_keyboard(channel_url, terms_url, privacy_url)

        await callback.message.edit_text(
            final_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )


    @user_router.callback_query(F.data == "user_speedtest_last")
    @registration_required
    async def user_speedtest_last_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            targets = rw_repo.get_all_ssh_targets() or []
        except Exception:
            targets = []
        lines = []
        for t in targets:
            name = (t.get('target_name') or '').strip()
            if not name:
                continue
            try:
                last = rw_repo.get_latest_speedtest(name)
            except Exception:
                last = None
            if not last:
                lines.append(f"• <b>{name}</b>: данных нет")
                continue
            ping = last.get('ping_ms')
            down = last.get('download_mbps')
            up = last.get('upload_mbps')
            ok_badge = '✅' if last.get('ok') else '❌'
            ping_s = f"{float(ping):.2f}" if isinstance(ping, (int, float)) else '—'
            down_s = f"{float(down):.0f}" if isinstance(down, (int, float)) else '—'
            up_s = f"{float(up):.0f}" if isinstance(up, (int, float)) else '—'
            ts_raw = last.get('created_at') or ''
            ts_s = ''
            if ts_raw:
                try:
                    dt = datetime.fromisoformat(str(ts_raw).replace('Z', '+00:00'))

                    ts_s = dt.strftime('%d.%m %H:%M')
                except Exception:
                    ts_s = str(ts_raw)

            lines.append(
                f"• <b>{name}</b> — SSH: {ok_badge} · ⏱ {ping_s} ms · ↓ {down_s} Mbps · ↑ {up_s} Mbps · 🕒 {ts_s}"
            )
        text = (
            "⚡ <b>Последние результаты Speedtest</b>\n"
            + ("\n".join(lines) if lines else "(цели не настроены)")
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ В меню", callback_data="back_to_main_menu")
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())

    @user_router.callback_query(F.data == "show_help")
    @registration_required
    async def about_handler(callback: types.CallbackQuery):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        support_text = get_setting("support_text") or "Раздел поддержки. Нажмите кнопку ниже, чтобы открыть чат с поддержкой."
        if support_bot_username:
            await callback.message.edit_text(
                support_text,
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            support_user = get_setting("support_user")
            if support_user:
                await callback.message.edit_text(
                    "Для связи с поддержкой используйте кнопку ниже.",
                    reply_markup=keyboards.create_support_keyboard(support_user)
                )
            else:
                await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    @user_router.callback_query(F.data == "support_menu")
    @registration_required
    async def support_menu_handler(callback: types.CallbackQuery):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        support_text = get_setting("support_text") or "Раздел поддержки. Нажмите кнопку ниже, чтобы открыть чат с поддержкой."
        if support_bot_username:
            await callback.message.edit_text(
                support_text,
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            support_user = get_setting("support_user")
            if support_user:
                await callback.message.edit_text(
                    "Для связи с поддержкой используйте кнопку ниже.",
                    reply_markup=keyboards.create_support_keyboard(support_user)
                )
            else:
                await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    @user_router.callback_query(F.data == "support_external")
    @registration_required
    async def support_external_handler(callback: types.CallbackQuery):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await callback.message.edit_text(
                get_setting("support_text") or "Раздел поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
            return
        support_user = get_setting("support_user")
        if not support_user:
            await callback.message.edit_text("Внешний контакт поддержки не настроен.", reply_markup=keyboards.create_back_to_menu_keyboard())
            return
        await callback.message.edit_text(
            "Для связи с поддержкой используйте кнопку ниже.",
            reply_markup=keyboards.create_support_keyboard(support_user)
        )

    @user_router.callback_query(F.data == "support_new_ticket")
    @registration_required
    async def support_new_ticket_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await callback.message.edit_text(
                "Раздел поддержки вынесен в отдельного бота.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    @user_router.message(SupportDialog.waiting_for_subject)
    @registration_required
    async def support_subject_received(message: types.Message, state: FSMContext):
        await state.clear()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await message.answer(
                "Создание тикетов доступно в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await message.answer("Контакты поддержки не настроены.")

    @user_router.message(SupportDialog.waiting_for_message)
    @registration_required
    async def support_message_received(message: types.Message, state: FSMContext, bot: Bot):
        await state.clear()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await message.answer(
                "Создание тикетов доступно в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await message.answer("Контакты поддержки не настроены.")

    @user_router.callback_query(F.data == "support_my_tickets")
    @registration_required
    async def support_my_tickets_handler(callback: types.CallbackQuery):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await callback.message.edit_text(
                "Список обращений доступен в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    @user_router.callback_query(F.data.startswith("support_view_"))
    @registration_required
    async def support_view_ticket_handler(callback: types.CallbackQuery):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await callback.message.edit_text(
                "Просмотр тикетов доступен в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    @user_router.callback_query(F.data.startswith("support_reply_"))
    @registration_required
    async def support_reply_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await callback.message.edit_text(
                "Отправка ответов доступна в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    @user_router.message(SupportDialog.waiting_for_reply)
    @registration_required
    async def support_reply_received(message: types.Message, state: FSMContext, bot: Bot):
        await state.clear()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await message.answer(
                "Отправка ответов доступна в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
        else:
            await message.answer("Контакты поддержки не настроены.")

    @user_router.message(F.is_topic_message == True)
    async def forum_thread_message_handler(message: types.Message, bot: Bot):
        try:
            support_bot_username = get_setting("support_bot_username")
            me = await bot.get_me()
            if support_bot_username and (me.username or "").lower() != support_bot_username.lower():
                return
            if not message.message_thread_id:
                return
            forum_chat_id = message.chat.id
            thread_id = message.message_thread_id
            ticket = get_ticket_by_thread(str(forum_chat_id), int(thread_id))
            if not ticket:
                return
            user_id = int(ticket.get('user_id'))
            if message.from_user and message.from_user.id == me.id:
                return

            is_admin_by_setting = is_admin(message.from_user.id)
            is_admin_in_chat = False
            try:
                member = await bot.get_chat_member(chat_id=forum_chat_id, user_id=message.from_user.id)
                is_admin_in_chat = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
            except Exception:
                pass
            if not (is_admin_by_setting or is_admin_in_chat):
                return
            content = (message.text or message.caption or "").strip()
            if content:
                add_support_message(ticket_id=int(ticket['ticket_id']), sender='admin', content=content)
            header = await bot.send_message(
                chat_id=user_id,
                text=f"💬 Ответ поддержки по тикету #{ticket['ticket_id']}"
            )
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_to_message_id=header.message_id
                )
            except Exception:
                if content:
                    await bot.send_message(chat_id=user_id, text=content)
        except Exception as e:
            logger.warning(f"Failed to relay forum thread message: {e}")

    @user_router.callback_query(F.data.startswith("support_close_"))
    @registration_required
    async def support_close_ticket_handler(callback: types.CallbackQuery):
        await callback.answer()
        support_bot_username = get_setting("support_bot_username")
        if support_bot_username:
            await callback.message.edit_text(
                "Управление тикетами доступно в отдельном боте поддержки.",
                reply_markup=keyboards.create_support_bot_link_keyboard(support_bot_username)
            )
            return
        await callback.message.edit_text("Контакты поддержки не настроены.", reply_markup=keyboards.create_back_to_menu_keyboard())

    

    async def _remnawave_key_exists(key_data: dict) -> bool | None:
        """Проверяет, существует ли ключ (пользователь) в Remnawave.

        Возвращает:
        - True  — ключ найден
        - False — ключ точно удалён (404 на поддерживаемом lookup)
        - None  — не удалось проверить (ошибка API/сети или UUID на 3.x без username)
        """
        try:
            host_name = key_data.get('host_name')
            email = key_data.get('key_email') or key_data.get('email')
            user_uuid = key_data.get('remnawave_user_uuid') or key_data.get('xui_client_uuid')
            return await remnawave_api.panel_user_exists(
                user_ref=user_uuid,
                email=email,
                host_name=host_name,
            )
        except remnawave_api.RemnawaveAPIError:
            return None
        except Exception:
            return None


    

    def _extract_connected_devices(user_payload: dict | None) -> int:
        """Возвращает количество подключённых устройств (HWID/Devices) по данным Remnawave.

        В Remnawave это поле встречается в разных форматах:
        - списком (list)
        - объектом-пейджером (dict) с полями data/items/list и т.п.
        - уже готовым числом count/total
        Поэтому парсер старается быть максимально терпимым к схеме.
        """
        if not isinstance(user_payload, dict):
            return 0

        def _count_from_value(val) -> int | None:
            if isinstance(val, list):
                return len(val)
            if isinstance(val, int):
                return val
            if isinstance(val, str) and val.strip().isdigit():
                return int(val.strip())
            if isinstance(val, dict):
                # Часто список лежит внутри data/items/list/rows/results/devices/hwids
                for kk in (
                    "data",
                    "items",
                    "list",
                    "rows",
                    "results",
                    "devices",
                    "hwids",
                    "hwidDevices",
                ):
                    inner = val.get(kk)
                    if isinstance(inner, list):
                        return len(inner)
                # Или отдельно приходит total/count
                for kk in ("total", "count", "totalCount", "itemsCount"):
                    inner = val.get(kk)
                    if isinstance(inner, int):
                        return inner
                    if isinstance(inner, str) and inner.strip().isdigit():
                        return int(inner.strip())
            return None

        # 1) Пробуем извлечь из наиболее вероятных ключей (camelCase + snake_case)
        list_like_keys = (
            "hwidDevices",
            "hwid_devices",
            "devices",
            "device_ids",
            "deviceIds",
            "connectedDevices",
            "connected_devices",
            "activeHwids",
            "active_hwids",
            "activeHwidDevices",
            "active_hwid_devices",
            "hwids",
            "hwidDeviceIds",
            "hwid_device_ids",
            "hwid_devices_info",
            "hwidDevicesInfo",
            "hwidDeviceInfo",
        )
        for key in list_like_keys:
            if key in user_payload:
                cnt = _count_from_value(user_payload.get(key))
                if isinstance(cnt, int):
                    return max(0, cnt)

        # 2) Пробуем готовые count-поля (camelCase + snake_case)
        count_keys = (
            "activeHwidCount",
            "active_hwid_count",
            "activeHwidDeviceCount",
            "active_hwid_device_count",
            "hwidDeviceCount",
            "hwid_device_count",
            "hwidDevicesCount",
            "hwid_devices_count",
            "devicesCount",
            "devices_count",
            "connectedDevicesCount",
            "connected_devices_count",
            "connections",
        )
        for key in count_keys:
            if key in user_payload:
                cnt = _count_from_value(user_payload.get(key))
                if isinstance(cnt, int):
                    return max(0, cnt)

        # 3) Иногда данные вложены в hwid/hwidInfo/deviceInfo
        nested = user_payload.get("hwid") or user_payload.get("hwidInfo") or user_payload.get("deviceInfo") or user_payload.get("devicesInfo")
        if isinstance(nested, dict):
            for key in (
                "devices",
                "deviceIds",
                "device_ids",
                "list",
                "items",
                "data",
                "hwidDevices",
                "hwid_devices",
            ):
                if key in nested:
                    cnt = _count_from_value(nested.get(key))
                    if isinstance(cnt, int):
                        return max(0, cnt)

        # 4) Последняя попытка: пройтись по всем ключам и найти пейджер/список с hwid/devices
        # (помогает при неожиданных изменениях схемы ответа)
        #
        # Важно: не путать количество устройств с лимитом устройств.
        # В ответах Remnawave часто встречаются поля вроде `hwidDeviceLimit`/`device_limit`,
        # и если их ошибочно принять за количество подключённых устройств — на экране
        # будет показываться лимит вместо фактического числа подключений.
        for k, v in user_payload.items():
            lk = str(k).lower()
            if ("hwid" in lk or "device" in lk) and not any(x in lk for x in ("limit", "max", "quota")):
                cnt = _count_from_value(v)
                if isinstance(cnt, int) and cnt > 0:
                    return cnt

        return 0


    async def _get_connected_devices_count(key_data: dict, user_payload: dict | None) -> int:
        """Надёжно получить количество подключённых HWID-устройств.

        Remnawave не всегда возвращает HWID-устройства внутри /api/users,
        поэтому если в user_payload получается 0 — делаем отдельный запрос
        /api/hwid/devices/{userUuid}.
        """

        base_cnt = _extract_connected_devices(user_payload)
        if base_cnt > 0:
            return base_cnt

        if not isinstance(user_payload, dict):
            return 0

        user_uuid = remnawave_api.panel_user_ref_from_payload(user_payload)
        host_name = (key_data or {}).get("host_name")
        email = (key_data or {}).get("key_email") or (key_data or {}).get("email")
        if not user_uuid:
            return 0

        hwid_payload = None
        try:
            hwid_payload = await remnawave_api.get_hwid_devices_for_user(
                user_uuid, host_name=host_name, email=email
            )
        except Exception:
            hwid_payload = None

        def _count_any(val) -> int:
            if val is None:
                return 0
            if isinstance(val, list):
                return len(val)
            if isinstance(val, int):
                return max(0, val)
            if isinstance(val, str) and val.strip().isdigit():
                return int(val.strip())
            if isinstance(val, dict):
                # ready counts
                for kk in ("total", "count", "totalCount", "itemsCount", "total_count", "items_count"):
                    inner = val.get(kk)
                    c = _count_any(inner)
                    if c:
                        return c

                # common containers
                for kk in (
                    "items",
                    "data",
                    "list",
                    "rows",
                    "results",
                    "devices",
                    "hwidDevices",
                    "hwid_devices",
                    "hwids",
                ):
                    inner = val.get(kk)
                    c = _count_any(inner)
                    if c:
                        return c

                # fallback scan
                # (но не путаем лимиты устройств с количеством подключённых устройств)
                for k, v in val.items():
                    lk = str(k).lower()
                    if ("hwid" in lk or "device" in lk or lk in ("data", "items", "list", "rows")) and not any(
                        x in lk for x in ("limit", "max", "quota")
                    ):
                        c = _count_any(v)
                        if c:
                            return c
            return 0

        return _count_any(hwid_payload)


    async def _get_devices_list(key_data: dict, user_payload: dict | None) -> list[dict]:
        """Получить полный список подключённых HWID-устройств с информацией о каждом.
        
        Возвращает список словарей вида:
        {
            'hwid': 'device_id',
            'platform': 'iOS' или None,
            'osVersion': '16.0' или None,
            'deviceModel': 'iPhone 12' или None,
            'userAgent': '...' или None,
        }
        """
        if not isinstance(user_payload, dict):
            return []
        
        user_uuid = remnawave_api.panel_user_ref_from_payload(user_payload)
        host_name = (key_data or {}).get("host_name")
        email = (key_data or {}).get("key_email") or (key_data or {}).get("email")
        
        if not user_uuid:
            return []
        
        try:
            hwid_payload = await remnawave_api.get_hwid_devices_for_user(
                user_uuid, host_name=host_name, email=email
            )
        except Exception:
            return []
        
        if not hwid_payload:
            return []
        
        # Пытаемся извлечь список устройств из ответа
        devices = []
        
        # Стандартные места где могут быть устройства
        possible_containers = [
            hwid_payload if isinstance(hwid_payload, list) else None,
            hwid_payload.get("devices") if isinstance(hwid_payload, dict) else None,
            hwid_payload.get("list") if isinstance(hwid_payload, dict) else None,
            hwid_payload.get("response") if isinstance(hwid_payload, dict) else None,
            hwid_payload.get("data") if isinstance(hwid_payload, dict) else None,
            hwid_payload.get("items") if isinstance(hwid_payload, dict) else None,
        ]
        
        for container in possible_containers:
            if isinstance(container, list):
                devices = [d for d in container if isinstance(d, dict)]
                if devices:
                    break
        
        return devices


    def _is_key_without_billing_plan(key_data: dict) -> bool:
        """Триальный или подарочный ключ: биллингового тарифа у него нет.

        Для таких ключей `plan_id` в description намеренно None (см. вызовы
        `_build_key_origin_meta(source="trial"/"gift", plan_id=None)`), поэтому подставлять
        им «первый активный тариф хоста» нельзя: это исказило бы и лимиты в карточке
        ключа, и набор пакетов докупки.

        TODO: для подарочных ключей точный тариф известен в `user_gifts.plan_id`
        (rw_repo.get_gift_info_by_key_id) — при необходимости докупку для подарков можно
        включить, резолвя тариф оттуда, а не эвристикой по хосту.
        """
        try:
            tag = str((key_data or {}).get("tag") or "").strip().lower()
        except Exception:
            tag = ""
        if tag in {"trial", "триал"} or "gift" in tag:
            return True
        try:
            desc = (key_data or {}).get("description")
            if isinstance(desc, str) and desc.strip().startswith("{"):
                meta = json.loads(desc)
                if isinstance(meta, dict):
                    if meta.get("is_trial"):
                        return True
                    if str(meta.get("source") or "").strip().lower() in {"trial", "gift"}:
                        return True
        except Exception:
            pass
        return False

    def _resolve_plan_id_for_key(key_data: dict) -> int | None:
        """Определяет plan_id, привязанный к ключу.

        Приоритеты:
          1) plan_id из vpn_keys.description (JSON, пишется при покупке/продлении);
          2) fallback на первый активный тариф хоста — как в `_get_tariff_info_for_key`.

        Без п.2 у ключей, выданных до появления этого поля (или с не-JSON description),
        докупка ГБ/LTE была недоступна, хотя тариф хоста существует и карточка ключа
        показывала его название через fallback в `_get_tariff_info_for_key`.
        """
        try:
            desc = (key_data or {}).get("description")
            if isinstance(desc, str) and desc.strip().startswith("{"):
                meta = json.loads(desc)
                if isinstance(meta, dict) and meta.get("plan_id") is not None:
                    return int(meta.get("plan_id"))
        except Exception:
            pass

        if _is_key_without_billing_plan(key_data):
            return None

        host_name = (key_data or {}).get("host_name")
        if not host_name:
            return None
        try:
            plans = get_active_plans_for_host(host_name) or []
        except Exception:
            plans = []
        if not plans:
            return None
        try:
            return int(plans[0].get("plan_id"))
        except (TypeError, ValueError):
            return None


    def _extract_traffic_used_bytes(payload: dict | None) -> int:
        """Извлекает использованный трафик из payload пользователя Remnawave (если поле есть)."""
        if not isinstance(payload, dict):
            return 0
        candidates = [
            "trafficUsedBytes", "traffic_used_bytes", "usedTrafficBytes",
            "trafficUsed", "traffic_used", "usedBytes", "bytesUsed",
        ]
        for k in candidates:
            v = payload.get(k)
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
            if isinstance(v, str) and v.isdigit():
                try:
                    iv = int(v)
                    if iv > 0:
                        return iv
                except Exception:
                    pass
        return 0

    def _format_bytes_gb(num_bytes: int) -> str:
        try:
            gb = num_bytes / (1024 ** 3)
            return f"{gb:.2f}".rstrip('0').rstrip('.') if '.' in f"{gb:.2f}" else f"{gb:.2f}"
        except Exception:
            return "0"

    def _get_tariff_info_for_key(key_data: dict, user_payload: dict | None = None) -> tuple[str, str, int]:
        """Подбирает данные тарифа для отображения в 'Мои ключи'.

        Приоритеты:
          1) точные данные из Remnawave (user_payload.hwidDeviceLimit)
          2) тариф, выбранный при покупке/продлении (vpn_keys.description JSON -> plan_id)
          3) fallback на первый активный тариф хоста
        """
        host_name = (key_data or {}).get("host_name")

        # 1) Prefer per-key origin info (stored in vpn_keys.description/tag)
        plan_name_from_key = None
        plan_id_from_key: int | None = None
        device_limit_from_key: int | None = None

        try:
            tag = (key_data or {}).get("tag") or ""
            if str(tag).strip().lower() in {"trial", "триал"}:
                plan_name_from_key = "триал"
        except Exception:
            pass

        # Extra heuristic for legacy trial keys: we often generate emails like "trial_*@bot.local".
        try:
            if plan_name_from_key is None:
                em = str((key_data or {}).get("key_email") or "")
                if em.lower().startswith("trial_") or ("@bot.local" in em.lower() and "trial" in em.lower()):
                    plan_name_from_key = "триал"
        except Exception:
            pass

        try:
            desc = (key_data or {}).get("description")
            if isinstance(desc, str) and desc.strip():
                d = desc.strip()
                if plan_name_from_key is None and ("trial" in d.lower() or "триал" in d.lower()):
                    plan_name_from_key = "триал"
                if d.startswith("{"):
                    meta = json.loads(d)
                    if isinstance(meta, dict):
                        if meta.get("tariff_label"):
                            plan_name_from_key = str(meta.get("tariff_label"))
                        elif meta.get("is_trial"):
                            plan_name_from_key = "триал"

                        # selected plan id (so we can render correct limits even if host plans list changes)
                        if meta.get("plan_id") is not None:
                            try:
                                plan_id_from_key = int(meta.get("plan_id"))
                            except Exception:
                                plan_id_from_key = None

                        # optional future field
                        for kk in ("hwid_device_limit", "device_limit", "devices_limit", "hwidDeviceLimit"):
                            if meta.get(kk) is not None:
                                try:
                                    device_limit_from_key = int(meta.get(kk))
                                except Exception:
                                    device_limit_from_key = None
                                break

                        if not plan_name_from_key:
                            try:
                                dd = int(meta.get("duration_days") or 0)
                            except Exception:
                                dd = 0
                            try:
                                mm = int(meta.get("months") or 0)
                            except Exception:
                                mm = 0
                            if dd > 0:
                                plan_name_from_key = f"{dd} дней"
                            elif mm > 0:
                                plan_name_from_key = f"{mm * 30} дней"
        except Exception:
            pass

        origin_locked = bool(plan_name_from_key and str(plan_name_from_key).strip())

        # 2) Prefer exact device limit from Remnawave payload
        device_limit: int | None = None
        if isinstance(user_payload, dict):
            for kk in ("hwidDeviceLimit", "deviceLimit", "device_limit", "maxDevices", "maxDeviceCount", "hwid_device_limit"):
                val = user_payload.get(kk)
                if val is not None:
                    try:
                        v = int(val)
                        if v > 0:
                            device_limit = v
                            break
                    except Exception:
                        pass

        # 3) Determine plan (by stored plan_id, else first active plan for host)
        plan = None
        if plan_id_from_key:
            try:
                plan = get_plan_by_id(int(plan_id_from_key))
            except Exception:
                plan = None

        if not isinstance(plan, dict):
            try:
                plans = get_active_plans_for_host(host_name) or get_plans_for_host(host_name) or []
                plan = plans[0] if plans else None
            except Exception:
                plan = None

        plan_name = plan_name_from_key
        duration_days = 0

        if isinstance(plan, dict):
            if not plan_name:
                plan_name = plan.get("plan_name")

            # If we still don't have device limit, try from plan
            if device_limit in (None, 0):
                try:
                    pl_dev = plan.get("hwid_device_limit") or plan.get("hwidDeviceLimit")
                    if pl_dev is not None:
                        pl_dev_int = int(pl_dev)
                        if pl_dev_int > 0:
                            device_limit = pl_dev_int
                except Exception:
                    pass

            # try metadata json stored in plan (legacy)
            if device_limit in (None, 0) and plan.get("metadata"):
                try:
                    meta_obj = json.loads(plan.get("metadata")) if isinstance(plan.get("metadata"), str) else plan.get("metadata")
                    if isinstance(meta_obj, dict):
                        for kk in ("hwid_device_limit", "device_limit", "devices_limit", "hwidDeviceLimit"):
                            if meta_obj.get(kk) is not None:
                                v = int(meta_obj.get(kk))
                                if v > 0:
                                    device_limit = v
                                    break
                except Exception:
                    pass

            try:
                duration_days = int(plan.get("duration_days") or 0)
            except Exception:
                duration_days = 0
            if not duration_days:
                try:
                    months = int(plan.get("months") or 0)
                    duration_days = months * 30 if months else 0
                except Exception:
                    duration_days = 0

            if not plan_name:
                plan_name = f"{duration_days} дней" if duration_days else None
            else:
                try:
                    if (not origin_locked) and isinstance(plan_name, str) and not re.search(r"\d", plan_name) and duration_days:
                        if plan_name.strip().lower() not in {"trial", "триал"}:
                            plan_name = f"{duration_days} дней"
                except Exception:
                    pass

        # 4) device limit from key-origin meta (if present) — after payload, before fallbacks
        if device_limit in (None, 0) and device_limit_from_key:
            device_limit = int(device_limit_from_key)

        # 5) trial fallback
        if device_limit in (None, 0):
            try:
                tag = (key_data or {}).get("tag") or ""
                is_trial = str(tag).strip().lower() in {"trial", "триал"} or (plan_name_from_key == "триал")
            except Exception:
                is_trial = False
            if is_trial:
                try:
                    raw_dev = (get_setting("trial_device_limit") or "").strip()
                    if raw_dev:
                        v = int(float(raw_dev.replace(",", ".")))
                        if v > 0:
                            device_limit = v
                except Exception:
                    pass

        # final fallback: if we still don't know origin, at least show current key validity window
        if not plan_name:
            try:
                created_iso = (key_data or {}).get("created_date") or (key_data or {}).get("created_at")
                expiry_iso = (key_data or {}).get("expiry_date") or (key_data or {}).get("expire_at")
                if created_iso and expiry_iso:
                    cd = datetime.fromisoformat(str(created_iso))
                    ed = datetime.fromisoformat(str(expiry_iso))
                    days = max(0, int((ed - cd).total_seconds() // 86400))
                    if days:
                        plan_name = f"{days} дней"
            except Exception:
                pass

        if not plan_name:
            plan_name = "—"
        if not device_limit:
            device_limit = 5

        group = f"{int(device_limit)} устройств📡"
        return group, plan_name, int(device_limit)

    async def sync_user_keys_with_remnawave(user_id: int) -> int:
        """Синхронизирует ключи пользователя в БД с фактическими ключами в Remnawave.

        Раньше бот *сразу* удалял ключ из локальной БД, если Remnawave отвечал 404.
        При большом количестве пользователей (>500) и/или проблемах пагинации/поиска на панели
        это могло приводить к ложным 404 и массовым удалениям активных ключей.

        Новая логика безопаснее:
        - если ключ не найден, сначала помечаем его как "missing_from_server_at"
        - удаляем из БД только если ключ отсутствует повторно и "missing_from_server_at" старше 24 часов
        - если ключ снова найден — снимаем пометку missing_from_server_at

        Возвращает количество удалённых из БД ключей.
        """
        keys = get_user_keys(user_id) or []
        if not keys:
            return 0

        now_dt = datetime.utcnow()
        grace = timedelta(hours=24)

        def _parse_missing_dt(value) -> datetime | None:
            if not value:
                return None
            try:
                s = str(value).strip()
                # common formats: "YYYY-MM-DD HH:MM:SS" or ISO
                s = s.replace("Z", "+00:00")
                if " " in s and "T" not in s:
                    s = s.replace(" ", "T", 1)
                dt = datetime.fromisoformat(s)
                # store as UTC-naive in DB; treat as UTC
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                return None

        async def _check(key: dict):
            exists = await _remnawave_key_exists(key)
            return key, exists

        tasks = [_check(k) for k in keys]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        removed = 0
        for item in results:
            if isinstance(item, Exception):
                continue
            key, exists = item
            key_id = key.get("key_id")
            if not key_id:
                continue

            # exists: True / False / None (None => API error; ничего не делаем)
            if exists is False:
                missing_dt = _parse_missing_dt(key.get("missing_from_server_at"))
                if missing_dt and (now_dt - missing_dt) > grace:
                    try:
                        if delete_key_by_id(int(key_id)):
                            removed += 1
                    except Exception:
                        pass
                else:
                    # помечаем как отсутствующий, но не удаляем
                    try:
                        database.update_key_fields(
                            int(key_id),
                            missing_from_server_at=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    except Exception:
                        pass
            elif exists is True:
                # если ранее помечали как missing — снимаем
                if key.get("missing_from_server_at"):
                    try:
                        database.update_key_fields(int(key_id), missing_from_server_at=None)
                    except Exception:
                        pass

        return removed
    @user_router.callback_query(F.data.in_({"manage_keys"}) | F.data.startswith("keys_page_"))
    @registration_required
    async def manage_keys_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        page = 0
        if callback.data.startswith("keys_page_"):
            page = int(callback.data.split("_")[-1])

        if page == 0:
            try:
                await sync_user_keys_with_remnawave(user_id)
            except Exception:
                pass

        all_user_keys = get_user_keys(user_id)
        user_keys = [key for key in all_user_keys if str(key.get('tag') or '').strip().lower() not in ('user_gift', 'gift')]
        gift_keys = [key for key in all_user_keys if str(key.get('tag') or '').strip().lower() in ('user_gift', 'gift')]

        has_any = bool(user_keys or gift_keys)
        await callback.message.edit_text(
            "Ваши ключи:" if has_any else "У вас пока нет ключей.",
            reply_markup=keyboards.create_keys_management_keyboard(user_keys, page=page, gift_keys=gift_keys)
        )

    @user_router.callback_query(F.data.in_({"sent_gifts"}) | F.data.startswith("gift_keys_page_"))
    @registration_required
    async def sent_gifts_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        page = 0
        if callback.data.startswith("gift_keys_page_"):
            page = int(callback.data.split("_")[-1])

        all_user_keys = get_user_keys(user_id)
        gift_keys = [key for key in all_user_keys if str(key.get('tag') or '').strip().lower() in ('user_gift', 'gift')]

        await callback.message.edit_text(
            "🎁 Отправленные подарки:" if gift_keys else "У вас нет отправленных подарков.",
            reply_markup=keyboards.create_sent_gifts_keyboard(gift_keys, page=page)
        )

    @user_router.callback_query(F.data == "search_my_keys")
    @registration_required
    async def search_my_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.set_state("search_keys_state")
        await callback.message.edit_text(
            "🔍 Введите название или email ключа для поиска:",
            reply_markup=keyboards.create_search_keys_cancel_keyboard()
        )

    @user_router.message(StateFilter("search_keys_state"))
    @registration_required
    async def search_keys_input_handler(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        search_query = message.text.strip()
        
        if not search_query:
            await message.answer("❌ Пожалуйста, введите email для поиска")
            return
        
        # Импортируем функцию поиска
        from shop_bot.data_manager.remnawave_repository import search_user_keys_by_email
        
        found_keys = search_user_keys_by_email(user_id, search_query)
        
        if not found_keys:
            await message.answer(
                "❌ Ключи не найдены. Попробуйте другой email.",
                reply_markup=keyboards.create_search_keys_cancel_keyboard()
            )
            return
        
        # Сохраняем результаты в state
        await state.update_data(search_results=found_keys)
        
        await message.answer(
            f"🔍 Найдено {len(found_keys)} ключ(ей):",
            reply_markup=keyboards.create_search_keys_results_keyboard(found_keys, page=0)
        )

    @user_router.callback_query(F.data.startswith("search_keys_page_"))
    @registration_required
    async def search_keys_page_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        # Получаем номер страницы
        try:
            page = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        # Получаем результаты из state
        data = await state.get_data()
        search_results = data.get('search_results', [])
        
        if not search_results:
            await callback.answer("❌ Результаты поиска потеряны. Попробуйте снова.", show_alert=True)
            return
        
        await callback.message.edit_reply_markup(
            reply_markup=keyboards.create_search_keys_results_keyboard(search_results, page=page)
        )

    @user_router.callback_query(F.data == "cancel_search_keys")
    @registration_required
    async def cancel_search_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        
        user_id = callback.from_user.id
        user_keys = get_user_keys(user_id)
        
        await callback.message.edit_text(
            "Ваши ключи:" if user_keys else "У вас пока нет ключей.",
            reply_markup=keyboards.create_keys_management_keyboard(user_keys, page=0)
        )

    # =============================
    # Переименование ключей
    # =============================

    @user_router.callback_query(F.data.startswith("rename_key_"))
    @registration_required
    async def rename_key_start(callback: types.CallbackQuery, state: FSMContext):
        """Начало процесса переименования ключа."""
        await callback.answer()
        
        try:
            key_id = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id)
        
        # Проверка прав доступа
        if not key_data or key_data.get('user_id') != user_id:
            await callback.answer("❌ Ключ не найден или не принадлежит вам", show_alert=True)
            return
        
        # Сохраняем key_id в state
        await state.update_data(key_id=key_id)
        await state.set_state(KeyManagement.waiting_for_rename)
        
        current_name = key_data.get('user_key_name')
        has_name = bool(current_name)
        
        message_text = "📝 <b>Переименование ключа</b>\n\n"
        if current_name:
            message_text += f"<b>Текущее название:</b> {html_escape(current_name)}\n\n"
        
        message_text += (
            "Введите новое название для ключа.\n\n"
            "⚠️ <b>Ограничения:</b>\n"
            "• Максимум 30 символов\n"
            "• Можно использовать emoji ✨\n\n"
            "Используйте кнопки ниже для отмены или удаления названия."
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboards.create_rename_key_keyboard(key_id, has_name=has_name)
        )

    @user_router.message(StateFilter(KeyManagement.waiting_for_rename))
    @registration_required
    async def rename_key_process(message: types.Message, state: FSMContext):
        """Обработка ввода нового названия ключа."""
        user_id = message.from_user.id
        new_name = message.text.strip()
        
        # Получаем key_id из state
        data = await state.get_data()
        key_id = data.get('key_id')
        
        if not key_id:
            await message.answer("❌ Ошибка: ключ не найден. Попробуйте снова.")
            await state.clear()
            return
        
        # Проверка прав доступа
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            await message.answer("❌ Ключ не найден или не принадлежит вам")
            await state.clear()
            return
        
        # Валидация длины
        if len(new_name) > 30:
            await message.answer(
                f"❌ Название слишком длинное ({len(new_name)} символов).\n"
                f"Максимум 30 символов. Попробуйте короче."
            )
            return
        
        if not new_name:
            await message.answer("❌ Название не может быть пустым. Введите текст или используйте кнопку 'Удалить название'.")
            return
        
        # Обновление названия в БД
        from shop_bot.data_manager.database import update_key_name
        
        success = update_key_name(key_id, new_name)
        
        if not success:
            await message.answer("❌ Не удалось обновить название. Попробуйте ещё раз.")
            await state.clear()
            return
        
        await state.clear()
        
        # Показываем обновлённую карточку ключа
        await message.answer("✅ Название ключа обновлено!")
        
        # Получаем обновлённые данные ключа и показываем карточку
        try:
            key_data = rw_repo.get_key_by_id(key_id)
            details = await remnawave_api.get_key_details_from_host(key_data)
            
            if details and details.get('connection_string'):
                connection_string = details['connection_string']
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
                
                user_payload = details.get('user') if isinstance(details, dict) else None
                devices_connected = await _get_connected_devices_count(key_data, user_payload)
                devices_list = await _get_devices_list(key_data, user_payload)
                plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                
                gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                
                final_text = get_key_info_text(
                    key_data,
                    key_number,
                    devices_connected=devices_connected,
                    plan_group=plan_group,
                    plan_name=plan_name,
                    device_limit=device_limit,
                    gift_code=gift_code,
                )
                
                await message.answer(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                )
            else:
                await message.answer(
                    "Название обновлено, но не удалось загрузить детали ключа.",
                    reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
                )
        except Exception as e:
            logger.error(f"Error showing updated key {key_id}: {e}")
            await message.answer(
                "Название обновлено!",
                reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
            )

    @user_router.callback_query(F.data.startswith("remove_key_name_"))
    @registration_required
    async def remove_key_name(callback: types.CallbackQuery, state: FSMContext):
        """Удаление названия ключа."""
        await callback.answer()
        
        try:
            key_id = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id)
        
        # Проверка прав доступа
        if not key_data or key_data.get('user_id') != user_id:
            await callback.answer("❌ Ключ не найден или не принадлежит вам", show_alert=True)
            return
        
        # Удаление названия (устанавливаем None)
        from shop_bot.data_manager.database import update_key_name
        
        success = update_key_name(key_id, None)
        
        if not success:
            await callback.answer("❌ Не удалось удалить название", show_alert=True)
            return
        
        await state.clear()
        await callback.message.edit_text("✅ Название ключа удалено!")
        
        # Показываем обновлённую карточку ключа
        try:
            key_data = rw_repo.get_key_by_id(key_id)
            details = await remnawave_api.get_key_details_from_host(key_data)
            
            if details and details.get('connection_string'):
                connection_string = details['connection_string']
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
                
                user_payload = details.get('user') if isinstance(details, dict) else None
                devices_connected = await _get_connected_devices_count(key_data, user_payload)
                devices_list = await _get_devices_list(key_data, user_payload)
                plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                
                gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                
                final_text = get_key_info_text(
                    key_data,
                    key_number,
                    devices_connected=devices_connected,
                    plan_group=plan_group,
                    plan_name=plan_name,
                    device_limit=device_limit,
                    gift_code=gift_code,
                )
                
                await callback.message.answer(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                )
            else:
                await callback.message.answer(
                    "Название удалено!",
                    reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
                )
        except Exception as e:
            logger.error(f"Error showing updated key {key_id}: {e}")
            await callback.message.answer(
                "Название удалено!",
                reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
            )

    @user_router.callback_query(F.data.startswith("cancel_rename_key_"))
    @registration_required
    async def cancel_rename_key(callback: types.CallbackQuery, state: FSMContext):
        """Отмена переименования ключа."""
        await callback.answer()
        await state.clear()
        
        try:
            key_id = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id)
        
        # Проверка прав доступа
        if not key_data or key_data.get('user_id') != user_id:
            await callback.answer("❌ Ключ не найден", show_alert=True)
            return
        
        # Показываем карточку ключа
        try:
            details = await remnawave_api.get_key_details_from_host(key_data)
            
            if details and details.get('connection_string'):
                connection_string = details['connection_string']
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
                
                user_payload = details.get('user') if isinstance(details, dict) else None
                devices_connected = await _get_connected_devices_count(key_data, user_payload)
                devices_list = await _get_devices_list(key_data, user_payload)
                plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                
                gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                
                final_text = get_key_info_text(
                    key_data,
                    key_number,
                    devices_connected=devices_connected,
                    plan_group=plan_group,
                    plan_name=plan_name,
                    device_limit=device_limit,
                    gift_code=gift_code,
                )
                
                await callback.message.edit_text(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось загрузить данные ключа",
                    reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
                )
        except Exception as e:
            logger.error(f"Error showing key {key_id}: {e}")
            await callback.message.edit_text(
                "⬅️ Отменено",
                reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
            )

    # =============================
    # Trial period
    # =============================

    @user_router.callback_query(F.data == "get_trial")
    @registration_required
    async def trial_period_handler(callback: types.CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        user_db_data = get_user(user_id)
        if user_db_data and user_db_data.get('trial_used'):
            await callback.answer("Вы уже использовали бесплатный пробный период.", show_alert=True)
            return

        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для создания пробного ключа.")
            return

        # Если в настройках задан хост по умолчанию — пропускаем выбор
        default_host = (get_setting("trial_default_host") or "").strip()
        if default_host and any(h['host_name'] == default_host for h in hosts):
            await callback.answer()
            await process_trial_key_creation(callback.message, default_host)
            return

        if len(hosts) == 1:
            await callback.answer()
            await process_trial_key_creation(callback.message, hosts[0]['host_name'])
        else:
            await callback.answer()
            await callback.message.edit_text(
                "Вариант подключения:",
                reply_markup=keyboards.create_host_selection_keyboard(hosts, action="trial")
            )

    @user_router.callback_query(F.data.startswith("select_host_trial_"))
    @registration_required
    async def trial_host_selection_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_trial_"):]
        await process_trial_key_creation(callback.message, host_name)

    async def process_trial_key_creation(message: types.Message, host_name: str):
        user_id = message.chat.id
        await message.edit_text(
            f"Отлично! Создаю для вас бесплатный ключ на {get_setting('trial_duration_days')} дня "
            f"(вариант подключения «{host_name}»)..."
        )

        try:

            try:
                candidate_email = rw_repo.generate_key_email_for_user(user_id)
            except Exception:
                candidate_email = f"{user_id}-{int(datetime.now().timestamp())}@bot.local"

            # --- Trial limits (optional) ---
            traffic_limit_bytes = None
            hwid_device_limit = None
            try:
                raw_gb = (get_setting('trial_traffic_limit_gb') or '').strip()
                if raw_gb:
                    gb = float(raw_gb.replace(',', '.'))
                    if gb > 0:
                        traffic_limit_bytes = int(gb * 1024 * 1024 * 1024)
            except Exception:
                traffic_limit_bytes = None

            try:
                raw_dev = (get_setting('trial_device_limit') or '').strip()
                if raw_dev:
                    dev = int(float(raw_dev.replace(',', '.')))
                    if dev > 0:
                        hwid_device_limit = dev
            except Exception:
                hwid_device_limit = None

            try:
                result = await remnawave_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=candidate_email,
                    days_to_add=int(get_setting("trial_duration_days")),
                    traffic_limit_bytes=traffic_limit_bytes,
                    traffic_limit_strategy='NO_RESET' if traffic_limit_bytes is not None else None,
                    hwid_device_limit=hwid_device_limit,
                    raise_on_error=True,
                )
            except Exception as exc:
                await _handle_key_creation_failure(
                    message.bot,
                    user_id=user_id,
                    action_label=_format_key_action_label("trial"),
                    exc=exc,
                    refund=False,
                )
                try:
                    await message.edit_text("❌ Не удалось создать ключ.")
                except Exception:
                    pass
                return
            if not result:
                await _handle_key_creation_failure(
                    message.bot,
                    user_id=user_id,
                    action_label=_format_key_action_label("trial"),
                    exc=RuntimeError("trial key creation returned empty response"),
                    refund=False,
                )
                try:
                    await message.edit_text("❌ Не удалось создать ключ.")
                except Exception:
                    pass
                return

            set_trial_used(user_id)

            # +1 день рефереру начисляем только после успешного создания триал-ключа.
            try:
                await grant_referrer_day_bonus_for_trial(referred_user_id=user_id, bot=message.bot)
            except Exception:
                pass

            # Persist origin info so "🕒 Тариф" shows "триал".
            try:
                td = int(get_setting("trial_duration_days") or 0)
            except Exception:
                td = 0
            origin_desc = _build_key_origin_meta(
                source="trial",
                plan_id=None,
                plan_name="trial",
                months=0,
                duration_days=td,
                is_trial=True,
            )
            new_key_id = rw_repo.record_key_from_payload(
                user_id=user_id,
                payload=result,
                host_name=host_name,
                tag="trial",
                description=origin_desc,
            )
            
            await message.delete()
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
            final_text = get_purchase_success_text("new", get_next_key_number(user_id) -1, new_expiry_date, result['connection_string'])
            await message.answer(text=final_text, reply_markup=keyboards.create_key_info_keyboard(new_key_id, result.get('connection_string')))

        except Exception as e:
            logger.error(f"Error creating trial key for user {user_id} on host {host_name}: {e}", exc_info=True)
            await message.edit_text("❌ Произошла ошибка при создании пробного ключа.")

    @user_router.callback_query(F.data.startswith("show_key_"))
    @registration_required
    async def show_key_handler(callback: types.CallbackQuery):
        key_id_to_show = int(callback.data.split("_")[2])
        # Answer callback immediately to avoid Telegram client "spinner" and perceived hangs.
        try:
            await callback.answer()
        except Exception:
            pass
        await callback.message.edit_text("Загружаю информацию о ключе...")
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id_to_show)

        if not key_data or key_data['user_id'] != user_id:
            await callback.message.edit_text("❌ Ошибка: ключ не найден.")
            return
            
        try:
            details = await remnawave_api.get_key_details_from_host(key_data)
            if not details or not details.get('connection_string'):
                # Если ключ удалён в Remnawave, удалим его и локально, чтобы не висел в списке.
                try:
                    exists = await _remnawave_key_exists(key_data)
                except Exception:
                    exists = None
                if exists is False:
                    try:
                        delete_key_by_id(key_id_to_show)
                    except Exception:
                        pass
                    await callback.message.edit_text(
                        "❌ Этот ключ был удалён на сервере и уже убран из бота.",
                        reply_markup=keyboards.create_back_to_menu_keyboard()
                    )
                    return

                await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                return

            connection_string = details['connection_string']
            expiry_date = datetime.fromisoformat(key_data['expiry_date'])
            created_date = datetime.fromisoformat(key_data['created_date'])
            
            all_user_keys = get_user_keys(user_id)
            key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id_to_show), 0)
            
            user_payload = details.get('user') if isinstance(details, dict) else None
            devices_connected = await _get_connected_devices_count(key_data, user_payload)
            devices_list = await _get_devices_list(key_data, user_payload)
            plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
            
            # Получаем информацию о подарке, если это подарок
            gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id_to_show)
            domain = (get_setting("domain") or "").strip()
            
            # Определяем, доступна ли докупка ГБ (тариф ключа имеет ограничение трафика)
            show_traffic_topup = False
            plan_traffic_limit_bytes = 0
            plan_lte_limit_bytes = 0
            plan_main_reset_price = 0.0
            plan_for_key = None
            try:
                plan_id_for_key = _resolve_plan_id_for_key(key_data)
                if plan_id_for_key:
                    plan_for_key = get_plan_by_id(plan_id_for_key)
                    if plan_for_key:
                        plan_traffic_limit_bytes = int(plan_for_key.get('traffic_limit_bytes') or 0)
                        plan_lte_limit_bytes = int(plan_for_key.get('lte_limit_bytes') or 0)
                        plan_main_reset_price = float(plan_for_key.get('main_reset_price_rub') or 0)
                        if plan_traffic_limit_bytes > 0:
                            show_traffic_topup = True
            except Exception:
                show_traffic_topup = False

            # Объём использованного трафика и дата ближайшего ежемесячного сброса
            # (если тариф лимитирован по ГБ и/или LTE).
            traffic_info_text = None
            next_reset_display = database.format_next_traffic_reset_display(
                key_data.get('next_traffic_reset_at')
            )
            try:
                if plan_traffic_limit_bytes > 0:
                    used_bytes = _extract_traffic_used_bytes(user_payload)
                    boost_bytes = int(key_data.get('traffic_boost_bytes') or 0)
                    total_limit_bytes = plan_traffic_limit_bytes + boost_bytes
                    used_gb_txt = _format_bytes_gb(used_bytes)
                    total_gb_txt = _format_bytes_gb(total_limit_bytes)
                    traffic_info_text = f"♾ Основной: {used_gb_txt} ГБ / {total_gb_txt} ГБ"
                    if next_reset_display:
                        traffic_info_text += f" (сброс {next_reset_display})"
            except Exception:
                traffic_info_text = None

            # Показываем блок LTE-пула (💰 premium-ноды), если у тарифа есть отдельный LTE-лимит
            # И у хоста ключа реально настроен активный сквад класса 'lte' (host_squads).
            show_lte_topup = False
            lte_display_label = "LTE"
            # Сброс основного трафика доступен только тарифам с лимитом основного трафика и заданной ценой
            show_main_reset = show_traffic_topup and plan_main_reset_price > 0
            try:
                host_name_for_lte = key_data.get('host_name')
                if database.should_account_lte_traffic(plan_for_key, host_name_for_lte):
                    lte_squad_cfg = database.get_squad_by_class(host_name_for_lte, 'lte')
                    show_lte_topup = True
                    lte_display_label = database.squad_display_label(lte_squad_cfg)
                    # LTE-пул принадлежит КЛЮЧУ: докупка на одном ключе не расходуется
                    # на других ключах того же пользователя.
                    lte_state = database.get_key_lte_state(key_id_to_show)
                    lte_used = int(lte_state.get('lte_used_bytes') or 0)
                    # Та же формула, что энфорсит планировщик (лимит тарифа + докупленный
                    # буст) — раньше показанный лимит и проверяемый расходились.
                    lte_total = database.resolve_lte_limit_bytes(lte_state, plan_lte_limit_bytes)
                    lte_used_txt = _format_bytes_gb(lte_used)
                    lte_total_txt = _format_bytes_gb(lte_total)
                    # Названия хостов/нод в карточке ключа не показываем: пользователю
                    # достаточно суммарного LTE-лимита, а разбивка по нодам доступна
                    # администратору в веб-панели (key_node_usage_snapshots).
                    lte_line = f"💰 {html_escape(lte_display_label)}: {lte_used_txt} ГБ / {lte_total_txt} ГБ"
                    if next_reset_display:
                        lte_line += f" (сброс {next_reset_display})"
                    traffic_info_text = f"{traffic_info_text}\n{lte_line}" if traffic_info_text else lte_line
            except Exception:
                pass

            final_text = get_key_info_text(
                key_data,
                key_number,
                devices_connected=devices_connected,
                plan_group=plan_group,
                plan_name=plan_name,
                device_limit=device_limit,
                gift_code=gift_code,
                domain=domain,
                traffic_info_text=traffic_info_text,
            )
            
            await callback.message.edit_text(
                text=final_text,
                reply_markup=keyboards.create_key_info_keyboard(
                    key_id_to_show, connection_string, devices_list=devices_list,
                    gift_code=gift_code, gift_id=gift_id,
                    show_traffic_topup=show_traffic_topup,
                    show_lte_topup=show_lte_topup,
                    show_main_reset=show_main_reset,
                    auto_renew=bool(int(key_data.get("auto_renew") or 0)),
                    lte_label=lte_display_label,
                )
            )
        except Exception as e:
            logger.error(f"Error showing key {key_id_to_show}: {e}")
            await callback.message.edit_text("❌ Произошла ошибка при получении данных ключа.")

    @user_router.callback_query(F.data.startswith("auto_renew_key_"))
    @registration_required
    async def auto_renew_key_toggle(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int(callback.data[len("auto_renew_key_"):])
        except ValueError:
            await callback.answer("Некорректный ID ключа.", show_alert=True)
            return

        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data["user_id"] != callback.from_user.id:
            await callback.answer("Ключ не найден.", show_alert=True)
            return

        new_state = not bool(int(key_data.get("auto_renew") or 0))
        rw_repo.set_key_auto_renew(key_id, new_state)
        state_text = "✅ Автопродление включено" if new_state else "❌ Автопродление отключено"
        await callback.answer(state_text, show_alert=True)
        # Обновляем карточку ключа
        await show_key_handler(callback.model_copy(update={"data": f"show_key_{key_id}"}))

    @user_router.callback_query(F.data == "toggle_auto_renew_profile")
    @registration_required
    async def toggle_auto_renew_profile(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_keys = rw_repo.get_user_keys(user_id)
        any_enabled = any(bool(int(k.get("auto_renew") or 0)) for k in user_keys)
        # Инвертируем: если хоть один включён — выключаем все, иначе включаем все
        new_state = not any_enabled
        rw_repo.set_all_keys_auto_renew_for_user(user_id, new_state)
        state_text = "✅ Автопродление включено для всех ключей" if new_state else "❌ Автопродление отключено для всех ключей"
        await callback.answer(state_text, show_alert=True)
        await profile_handler_callback(callback)

    @user_router.callback_query(F.data.startswith("switch_server_"))
    @registration_required
    async def switch_server_start(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int(callback.data[len("switch_server_"):])
        except ValueError:
            await callback.answer("Некорректный идентификатор ключа.", show_alert=True)
            return

        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != callback.from_user.id:
            await callback.answer("Ключ не найден.", show_alert=True)
            return

        hosts = get_all_hosts()
        if not hosts:
            await callback.answer("Нет доступных серверов.", show_alert=True)
            return

        current_host = key_data.get('host_name')
        hosts = [h for h in hosts if h.get('host_name') != current_host]
        if not hosts:
            await callback.answer("Другие серверы отсутствуют.", show_alert=True)
            return

        await callback.message.edit_text(
            "Выберите новый сервер (локацию) для этого ключа:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts, action=f"switch_{key_id}")
        )

    @user_router.callback_query(F.data.startswith("select_host_switch_"))
    @registration_required
    async def select_host_for_switch(callback: types.CallbackQuery):
        await callback.answer()
        payload = callback.data[len("select_host_switch_"):]
        parts = payload.split("_", 1)
        if len(parts) != 2:
            await callback.answer("Некорректные данные выбора сервера.", show_alert=True)
            return
        try:
            key_id = int(parts[0])
        except ValueError:
            await callback.answer("Некорректный идентификатор ключа.", show_alert=True)
            return
        new_host_name = parts[1]

        key_data = rw_repo.get_key_by_id(key_id)

        if not key_data or key_data.get('user_id') != callback.from_user.id:
            await callback.answer("Ключ не найден.", show_alert=True)
            return

        old_host = key_data.get('host_name')
        if not old_host:
            await callback.answer("Для ключа не указан текущий сервер.", show_alert=True)
            return
        if new_host_name == old_host:
            await callback.answer("Это уже текущий сервер.", show_alert=True)
            return


        try:
            expiry_dt = datetime.fromisoformat(key_data['expiry_date'])
            expiry_timestamp_ms_exact = int(expiry_dt.timestamp() * 1000)
        except Exception:

            now_dt = datetime.now()
            expiry_timestamp_ms_exact = int((now_dt + timedelta(days=1)).timestamp() * 1000)

        await callback.message.edit_text(
            f"⏳ Переношу ключ на сервер \"{new_host_name}\"..."
        )

        email = key_data.get('key_email')
        try:
            plan_id_for_move = _resolve_plan_id_for_key(key_data)
            plan_for_move = get_plan_by_id(plan_id_for_move) if plan_id_for_move else None
            move_limit = int((plan_for_move or {}).get('traffic_limit_bytes') or key_data.get('traffic_limit_bytes') or 0)
            if move_limit < 0:
                move_limit = 0
            move_strategy = (
                database.remnawave_traffic_limit_strategy_for_plan(plan_for_move)
                if plan_for_move is not None
                else (key_data.get('traffic_limit_strategy') or 'NO_RESET')
            )

            result = await remnawave_api.create_or_update_key_on_host(
                new_host_name,
                email,
                days_to_add=None,
                expiry_timestamp_ms=expiry_timestamp_ms_exact,
                plan_id=plan_id_for_move,
                traffic_limit_bytes=move_limit,
                traffic_limit_strategy=move_strategy,
            )
            if not result:
                await callback.message.edit_text(
                    f"❌ Не удалось перенести ключ на сервер \"{new_host_name}\". Попробуйте позже."
                )
                return


            try:
                await remnawave_api.delete_client_on_host(old_host, email)
            except Exception:
                pass


            update_key_host_and_info(
                key_id=key_id,
                new_host_name=new_host_name,
                new_remnawave_uuid=result['client_uuid'],
                new_expiry_ms=result['expiry_timestamp_ms']
            )


            try:
                updated_key = rw_repo.get_key_by_id(key_id)
                details = await remnawave_api.get_key_details_from_host(updated_key)
                if details and details.get('connection_string'):
                    connection_string = details['connection_string']
                    expiry_date = datetime.fromisoformat(updated_key['expiry_date'])
                    created_date = datetime.fromisoformat(updated_key['created_date'])
                    all_user_keys = get_user_keys(callback.from_user.id)
                    key_number = next((i + 1 for i, k in enumerate(all_user_keys) if k['key_id'] == key_id), 0)
                    user_payload = details.get('user') if isinstance(details, dict) else None
                    devices_connected = await _get_connected_devices_count(updated_key, user_payload)
                    plan_group, plan_name, device_limit = _get_tariff_info_for_key(updated_key, user_payload)
                    
                    # Получаем информацию о подарке, если это подарок
                    gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                    domain = (get_setting("domain") or "").strip()
                    
                    final_text = get_key_info_text(
                        updated_key,
                        key_number,
                        devices_connected=devices_connected,
                        plan_group=plan_group,
                        plan_name=plan_name,
                        device_limit=device_limit,
                        gift_code=gift_code,
                        domain=domain,
                    )
                    await callback.message.edit_text(
                        text=final_text,
                        reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, gift_code=gift_code, gift_id=gift_id)
                    )
                else:

                    await callback.message.edit_text(
                        f"✅ Готово! Ключ перенесён на сервер \"{new_host_name}\".\n"
                        "Обновите подписку/конфиг в клиенте, если требуется.",
                        reply_markup=keyboards.create_back_to_menu_keyboard()
                    )
            except Exception:
                await callback.message.edit_text(
                    f"✅ Готово! Ключ перенесён на сервер \"{new_host_name}\".\n"
                    "Обновите подписку/конфиг в клиенте, если требуется.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Error switching key {key_id} to host {new_host_name}: {e}", exc_info=True)
            await callback.message.edit_text(
                "❌ Произошла ошибка при переносе ключа. Попробуйте позже."
            )

    @user_router.callback_query(F.data.startswith("show_qr_"))
    @registration_required
    async def show_qr_handler(callback: types.CallbackQuery):
        await callback.answer("Генерирую QR-код...")
        key_id = int(callback.data.split("_")[2])
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != callback.from_user.id: return
        
        try:
            details = await remnawave_api.get_key_details_from_host(key_data)
            if not details or not details['connection_string']:
                await callback.answer("Ошибка: Не удалось сгенерировать QR-код.", show_alert=True)
                return

            connection_string = details['connection_string']
            qr_img = qrcode.make(connection_string)
            bio = BytesIO(); qr_img.save(bio, "PNG"); bio.seek(0)
            qr_code_file = BufferedInputFile(bio.read(), filename="vpn_qr.png")
            await callback.message.answer_photo(photo=qr_code_file)
        except Exception as e:
            logger.error(f"Error showing QR for key {key_id}: {e}")

    @user_router.callback_query(F.data.startswith("delete_device_"))
    @registration_required
    async def delete_device_handler(callback: types.CallbackQuery):
        """Обработчик удаления HWID-устройства с ключа."""
        try:
            await callback.answer("Удаляю устройство...")
        except Exception:
            pass
        
        # Парсим callback data вида: delete_device_{key_id}_{hwid}
        parts = callback.data[len("delete_device_"):].split("_", 1)
        if len(parts) != 2:
            await callback.answer("❌ Некорректные данные устройства", show_alert=True)
            return
        
        try:
            key_id = int(parts[0])
        except ValueError:
            await callback.answer("❌ Некорректный идентификатор ключа", show_alert=True)
            return
        
        hwid = parts[1]
        
        # Проверяем что ключ принадлежит пользователю
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data['user_id'] != callback.from_user.id:
            await callback.answer("❌ Ключ не найден или вам недоступен", show_alert=True)
            return
        
        try:
            # Получаем данные пользователя из Remnawave (нужен integer id для нового API)
            user_uuid = key_data.get('remnawave_user_uuid') or key_data.get('xui_client_uuid')
            user_id: int | None = None
            details = await remnawave_api.get_key_details_from_host(key_data)
            if details and isinstance(details.get('user'), dict):
                up = details['user']
                if not user_uuid:
                    user_uuid = up.get('uuid') or up.get('userUuid')
                raw_id = up.get('id')
                if raw_id is not None:
                    try:
                        user_id = int(raw_id)
                    except (ValueError, TypeError):
                        pass

            if not user_uuid and user_id is None:
                await callback.answer("❌ Не удалось получить информацию об аккаунте", show_alert=True)
                return
            
            # Пытаемся удалить устройство через API
            host_name = key_data.get('host_name')
            email = key_data.get('key_email') or key_data.get('email')
            success = await remnawave_api.delete_hwid_device(
                user_uuid, hwid, host_name=host_name, user_id=user_id, email=email
            )
            
            if success:
                await callback.answer("✅ Устройство успешно удалено!", show_alert=True)
                
                # Обновляем экран с информацией о ключе
                try:
                    details = await remnawave_api.get_key_details_from_host(key_data)
                    if details and isinstance(details.get('user'), dict):
                        user_payload = details['user']
                        devices_list = await _get_devices_list(key_data, user_payload)
                        devices_connected = await _get_connected_devices_count(key_data, user_payload)
                        
                        plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                        
                        all_user_keys = get_user_keys(callback.from_user.id)
                        key_number = next((i + 1 for i, k in enumerate(all_user_keys) if k['key_id'] == key_id), 0)
                        
                        # Получаем информацию о подарке, если это подарок
                        gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                        domain = (get_setting("domain") or "").strip()
                        
                        final_text = get_key_info_text(
                            key_data,
                            key_number,
                            devices_connected=devices_connected,
                            plan_group=plan_group,
                            plan_name=plan_name,
                            device_limit=device_limit,
                            gift_code=gift_code,
                            domain=domain,
                        )
                        
                        # Обновляем сообщение
                        await callback.message.edit_text(
                            text=final_text,
                            reply_markup=keyboards.create_key_info_keyboard(key_id, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                        )
                except Exception as e:
                    logger.warning(f"Could not refresh key info after device deletion: {e}")
                    # Всё равно уведомляем пользователя о успехе
            else:
                await callback.answer("❌ Не удалось удалить устройство. Попробуйте позже.", show_alert=True)
        
        except Exception as e:
            logger.error(f"Error deleting device {hwid} from key {key_id}: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при удалении устройства", show_alert=True)

    @user_router.callback_query(F.data.startswith("howto_vless_"))
    @registration_required
    async def show_instruction_handler(callback: types.CallbackQuery):
        await callback.answer()
        key_id = int(callback.data.split("_")[2])

        intro_text = get_setting("howto_intro_text") or "Выберите вашу платформу для инструкции по подключению VLESS:"
        await callback.message.edit_text(
            intro_text,
            reply_markup=keyboards.create_howto_vless_keyboard_key(key_id),
            disable_web_page_preview=True
        )
    
    @user_router.callback_query(F.data.startswith("howto_vless"))
    @registration_required
    async def show_instruction_handler(callback: types.CallbackQuery):
        await callback.answer()

        intro_text = get_setting("howto_intro_text") or "Выберите вашу платформу для инструкции по подключению VLESS:"
        await callback.message.edit_text(
            intro_text,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data == "howto_android")
    @registration_required
    async def howto_android_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_android_text") or (
            "<b>Подключение на Android</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из Google Play Store.\n"
            "2. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "   • Откройте V2RayTun.\n"
            "   • Нажмите на значок + в правом нижнем углу.\n"
            "   • Выберите «Импортировать конфигурацию из буфера обмена» (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Нажмите на кнопку подключения (значок «V» или воспроизведения). Возможно, потребуется разрешение на создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard()

        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup

        if current_markup and hasattr(current_markup, "model_dump"):
            current_markup_dump = current_markup.model_dump()
        else:
            current_markup_dump = current_markup

        if markup and hasattr(markup, "model_dump"):
            new_markup_dump = markup.model_dump()
        else:
            new_markup_dump = markup

        if current_text == text and current_markup_dump == new_markup_dump:
            return

        try:
            await callback.message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise
            logger.debug(
                "Skipping edit_text for howto_android_handler: message is not modified"
            )

    @user_router.callback_query(F.data.startswith("howto_android_"))
    @registration_required
    async def howto_android_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_android_text") or (
            "<b>Подключение на Android</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из Google Play Store.\n"
            "2. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "    Откройте V2RayTun.\n"
            "    Нажмите на значок + в правом нижнем углу.\n"
            "    Выберите <Импортировать конфигурацию из буфера обмена> (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Нажмите на кнопку подключения (значок <V> или воспроизведения). Возможно, потребуется разрешение на создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "howto_ios")
    @registration_required
    async def howto_ios_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_ios_text") or (
            "<b>Подключение на iOS (iPhone/iPad)</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из App Store.\n"
            "2. <b>Скопируйте свой ключ (vless://):</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "   • Откройте V2RayTun.\n"
            "   • Нажмите на значок +.\n"
            "   • Выберите «Импортировать конфигурацию из буфера обмена» (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Включите главный переключатель в V2RayTun. Возможно, потребуется разрешить создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data.startswith("howto_ios_"))
    @registration_required
    async def howto_ios_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_ios_text") or (
            "<b>Подключение на iOS (iPhone/iPad)</b>\n\n"
            "1. <b>Установите приложение V2RayTun:</b> Загрузите и установите приложение V2RayTun из App Store.\n"
            "2. <b>Скопируйте свой ключ (vless://):</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "3. <b>Импортируйте конфигурацию:</b>\n"
            "    Откройте V2RayTun.\n"
            "    Нажмите на значок +.\n"
            "    Выберите <Импортировать конфигурацию из буфера обмена> (или аналогичный пункт).\n"
            "4. <b>Выберите сервер:</b> Выберите появившийся сервер в списке.\n"
            "5. <b>Подключитесь к VPN:</b> Включите главный переключатель в V2RayTun. Возможно, потребуется разрешить создание VPN-подключения.\n"
            "6. <b>Проверьте подключение:</b> После подключения проверьте свой IP-адрес, например, на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "howto_windows")
    @registration_required
    async def howto_windows_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_windows_text") or (
            "<b>Подключение на Windows</b>\n\n"
            "1. <b>Установите приложение Nekoray:</b> Загрузите Nekoray с https://github.com/MatsuriDayo/Nekoray/releases. Выберите подходящую версию (например, Nekoray-x64.exe).\n"
            "2. <b>Распакуйте архив:</b> Распакуйте скачанный архив в удобное место.\n"
            "3. <b>Запустите Nekoray.exe:</b> Откройте исполняемый файл.\n"
            "4. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "5. <b>Импортируйте конфигурацию:</b>\n"
            "   • В Nekoray нажмите «Сервер» (Server).\n"
            "   • Выберите «Импортировать из буфера обмена».\n"
            "   • Nekoray автоматически импортирует конфигурацию.\n"
            "6. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите «Серверы» → «Обновить все серверы».\n"
            "7. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "8. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "9. <b>Подключитесь к VPN:</b> Нажмите «Подключить» (Connect).\n"
            "10. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard()

        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup

        if current_markup and hasattr(current_markup, "model_dump"):
            current_markup_dump = current_markup.model_dump()
        else:
            current_markup_dump = current_markup

        if markup and hasattr(markup, "model_dump"):
            new_markup_dump = markup.model_dump()
        else:
            new_markup_dump = markup

        if current_text == text and current_markup_dump == new_markup_dump:
            return

        try:
            await callback.message.edit_text(
                text,
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise
            logger.debug(
                "Skipping edit_text for howto_windows_handler: message is not modified"
            )

    @user_router.callback_query(F.data.startswith("howto_windows_"))
    @registration_required
    async def howto_windows_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_windows_text") or (
            "<b>Подключение на Windows</b>\n\n"
            "1. <b>Установите приложение Nekoray:</b> Загрузите Nekoray с https://github.com/MatsuriDayo/Nekoray/releases. Выберите подходящую версию (например, Nekoray-x64.exe).\n"
            "2. <b>Распакуйте архив:</b> Распакуйте скачанный архив в удобное место.\n"
            "3. <b>Запустите Nekoray.exe:</b> Откройте исполняемый файл.\n"
            "4. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "5. <b>Импортируйте конфигурацию:</b>\n"
            "    В Nekoray нажмите <Сервер> (Server).\n"
            "    Выберите <Импортировать из буфера обмена>.\n"
            "    Nekoray автоматически импортирует конфигурацию.\n"
            "6. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите <Серверы>  <Обновить все серверы>.\n"
            "7. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "8. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "9. <b>Подключитесь к VPN:</b> Нажмите <Подключить> (Connect).\n"
            "10. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "howto_linux")
    @registration_required
    async def howto_linux_handler(callback: types.CallbackQuery):
        await callback.answer()
        text = get_setting("howto_linux_text") or (
            "<b>Подключение на Linux</b>\n\n"
            "1. <b>Скачайте и распакуйте Nekoray:</b> Перейдите на https://github.com/MatsuriDayo/Nekoray/releases и скачайте архив для Linux. Распакуйте его в удобную папку.\n"
            "2. <b>Запустите Nekoray:</b> Откройте терминал, перейдите в папку с Nekoray и выполните <code>./nekoray</code> (или используйте графический запуск, если доступен).\n"
            "3. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел «Моя подписка» в нашем боте и скопируйте свой ключ.\n"
            "4. <b>Импортируйте конфигурацию:</b>\n"
            "   • В Nekoray нажмите «Сервер» (Server).\n"
            "   • Выберите «Импортировать из буфера обмена».\n"
            "   • Nekoray автоматически импортирует конфигурацию.\n"
            "5. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите «Серверы» → «Обновить все серверы».\n"
            "6. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "7. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "8. <b>Подключитесь к VPN:</b> Нажмите «Подключить» (Connect).\n"
            "9. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_howto_vless_keyboard(),
            disable_web_page_preview=True
        )

    @user_router.callback_query(F.data.startswith("howto_linux_"))
    @registration_required
    async def howto_linux_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        try:
            key_id = int((callback.data or "").split("_")[2])
        except Exception:
            key_id = 0
        text = get_setting("howto_linux_text") or (
            "<b>Подключение на Linux</b>\n\n"
            "1. <b>Скачайте и распакуйте Nekoray:</b> Перейдите на https://github.com/MatsuriDayo/Nekoray/releases и скачайте архив для Linux. Распакуйте его в удобную папку.\n"
            "2. <b>Запустите Nekoray:</b> Откройте терминал, перейдите в папку с Nekoray и выполните <code>./nekoray</code> (или используйте графический запуск, если доступен).\n"
            "3. <b>Скопируйте свой ключ (vless://)</b> Перейдите в раздел <Моя подписка> в нашем боте и скопируйте свой ключ.\n"
            "4. <b>Импортируйте конфигурацию:</b>\n"
            "    В Nekoray нажмите <Сервер> (Server).\n"
            "    Выберите <Импортировать из буфера обмена>.\n"
            "    Nekoray автоматически импортирует конфигурацию.\n"
            "5. <b>Обновите серверы (если нужно):</b> Если серверы не появились, нажмите <Серверы>  <Обновить все серверы>.\n"
            "6. Сверху включите пункт 'Режим TUN' ('Tun Mode')\n"
            "7. <b>Выберите сервер:</b> В главном окне выберите появившийся сервер.\n"
            "8. <b>Подключитесь к VPN:</b> Нажмите <Подключить> (Connect).\n"
            "9. <b>Проверьте подключение:</b> Откройте браузер и проверьте IP на https://whatismyipaddress.com/. Он должен отличаться от вашего реального IP."
        )
        markup = keyboards.create_howto_vless_keyboard_key(key_id) if key_id > 0 else keyboards.create_howto_vless_keyboard()
        try:
            await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except TelegramBadRequest as exc:
            error_message = getattr(exc, "message", str(exc))
            if "message is not modified" not in error_message.lower():
                raise

    @user_router.callback_query(F.data == "gift_new_key")
    @registration_required
    async def gift_new_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        
        await callback.message.edit_text(
            "Вариант подключения:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts, action="gift")
        )

    @user_router.callback_query(F.data == "buy_new_key")
    @registration_required
    async def buy_new_key_handler(callback: types.CallbackQuery):
        await callback.answer()
        hosts = get_all_hosts()
        if not hosts:
            await callback.message.edit_text("❌ В данный момент нет доступных серверов для покупки.")
            return
        
        await callback.message.edit_text(
            "Вариант подключения:",
            reply_markup=keyboards.create_host_selection_keyboard(hosts, action="new")
        )

    @user_router.callback_query(F.data.startswith("select_host_new_"))
    @registration_required
    async def select_host_for_purchase_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_new_"):]
        plans = get_active_plans_for_host(host_name)
        if not plans:
            await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
            return
        await callback.message.edit_text(
            "Выберите тариф для нового ключа:", 
            reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
        )
    @user_router.callback_query(F.data.startswith("select_host_gift_"))
    @registration_required
    async def select_host_for_gift_handler(callback: types.CallbackQuery):
        await callback.answer()
        host_name = callback.data[len("select_host_gift_"):]
        plans = get_active_plans_for_host(host_name)
        if not plans:
            await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
            return
        await callback.message.edit_text(
            "Выберите тариф для подарочного ключа:", 
            reply_markup=keyboards.create_plans_keyboard(plans, action="gift", host_name=host_name)
        )


    @user_router.callback_query(F.data.startswith("extend_key_"))
    @registration_required
    async def extend_key_handler(callback: types.CallbackQuery):
        await callback.answer()

        try:
            key_id = int(callback.data.split("_")[2])
        except (IndexError, ValueError):
            await callback.message.edit_text("❌ Произошла ошибка. Неверный формат ключа.")
            return

        key_data = rw_repo.get_key_by_id(key_id)

        if not key_data or key_data['user_id'] != callback.from_user.id:
            await callback.message.edit_text("❌ Ошибка: Ключ не найден или не принадлежит вам.")
            return
        
        host_name = key_data.get('host_name')
        if not host_name:
            await callback.message.edit_text("❌ Ошибка: У этого ключа не указан сервер. Обратитесь в поддержку.")
            return

        plans = get_active_plans_for_host(host_name)

        if not plans:
            await callback.message.edit_text(
                f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены тарифы для продления."
            )
            return

        await callback.message.edit_text(
            f"Выберите тариф для продления ключа на сервере \"{host_name}\":",
            reply_markup=keyboards.create_plans_keyboard(
                plans=plans,
                action="extend",
                host_name=host_name,
                key_id=key_id
            )
        )

    @user_router.callback_query(F.data.startswith("buy_"))
    @registration_required
    async def plan_selection_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        parts = callback.data.split("_")[1:]
        action = parts[-2]
        key_id = int(parts[-1])
        plan_id = int(parts[-3])
        host_name = "_".join(parts[:-3])

        await state.update_data(
            action=action, key_id=key_id, plan_id=plan_id, host_name=host_name
        )

        email_prompt_enabled = (_is_true(get_setting("payment_email_prompt_enabled") or "false"))
        if email_prompt_enabled:
            await callback.message.edit_text(
                "📧 Пожалуйста, введите ваш email для отправки чека об оплате.\n\n"
                "Если вы не хотите указывать почту, нажмите кнопку ниже.",
                reply_markup=keyboards.create_skip_email_keyboard()
            )
            await state.set_state(PaymentProcess.waiting_for_email)
        else:
            await show_payment_options(callback.message, state)

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "back_to_plans")
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_plans")
    async def back_to_plans_handler(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        await state.clear()
        action = (data.get('action') or '').strip()


        if action == 'new':
            host_name = data.get('host_name') or ''
            if not host_name:
                await callback.message.edit_text(
                    "❌ Не удалось определить сервер. Вернитесь в меню.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                return
            plans = get_active_plans_for_host(host_name)
            if not plans:
                await callback.message.edit_text(f"❌ Для сервера \"{host_name}\" не настроены тарифы.")
                return
            await callback.message.edit_text(
                "Выберите тариф для нового ключа:",
                reply_markup=keyboards.create_plans_keyboard(plans, action="new", host_name=host_name)
            )
            return

        if action == 'extend':
            try:
                key_id = int(data.get('key_id') or 0)
            except Exception:
                key_id = 0
            if key_id <= 0:
                await callback.message.edit_text(
                    "❌ Не удалось определить ключ для продления.",
                    reply_markup=keyboards.create_back_to_menu_keyboard()
                )
                return
            key_data = rw_repo.get_key_by_id(key_id)
            if not key_data or key_data.get('user_id') != callback.from_user.id:
                await callback.message.edit_text("❌ Ошибка: Ключ не найден или не принадлежит вам.")
                return
            host_name = key_data.get('host_name')
            if not host_name:
                await callback.message.edit_text("❌ Ошибка: У этого ключа не указан сервер. Обратитесь в поддержку.")
                return
            plans = get_active_plans_for_host(host_name)
            if not plans:
                await callback.message.edit_text(
                    f"❌ Извините, для сервера \"{host_name}\" в данный момент не настроены тарифы для продления."
                )
                return
            await callback.message.edit_text(
                f"Выберите тариф для продления ключа на сервере \"{host_name}\":",
                reply_markup=keyboards.create_plans_keyboard(
                    plans=plans,
                    action="extend",
                    host_name=host_name,
                    key_id=key_id
                )
            )
            return


        await back_to_main_menu_handler(callback)

    @user_router.message(PaymentProcess.waiting_for_email)
    async def process_email_handler(message: types.Message, state: FSMContext):
        if is_valid_email(message.text or ""):
            await state.update_data(customer_email=(message.text or "").strip())
            await message.answer(f"✅ Email принят: {(message.text or '').strip()}")
            await show_payment_options(message, state)
        else:
            await message.answer("❌ Неверный формат email. Попробуйте еще раз.")

    @user_router.callback_query(PaymentProcess.waiting_for_email, F.data == "skip_email")
    async def skip_email_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.update_data(customer_email=None)
        await show_payment_options(callback.message, state)

    async def show_payment_options(message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_data = get_user(message.chat.id)
        plan = get_plan_by_id(data.get('plan_id'))
        
        if not plan:
            try:
                await message.edit_text("❌ Ошибка: Тариф не найден.")
            except TelegramBadRequest:
                await message.answer("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        
        price = Decimal(str(plan['price']))
        final_price = price
        discount_applied = False
        message_text = CHOOSE_PAYMENT_METHOD_MESSAGE

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            
            if discount_percentage > 0:
                discount_amount = (price * discount_percentage / 100).quantize(Decimal("0.01"))
                final_price = price - discount_amount

                message_text = (
                    f"🎉 Как приглашенному пользователю, на вашу первую покупку предоставляется скидка {discount_percentage_str}%!\n"
                    f"Старая цена: <s>{price:.2f} RUB</s>\n"
                    f"<b>Новая цена: {final_price:.2f} RUB</b>\n\n"
                ) + CHOOSE_PAYMENT_METHOD_MESSAGE

        promo_code = (data.get('promo_code') or '').strip()
        promo_discount_amount = Decimal('0')

        if promo_code:
            # Re-check promo validity (it could be disabled/expired while user is on the payment screen)
            promo, promo_err = check_promo_code_available(
                promo_code, message.chat.id, plan_id=data.get("plan_id")
            )
            if promo_err:
                # Drop promo from state if it's no longer applicable
                await state.update_data(promo_code=None, promo_discount=0, promo_percent=None, promo_amount=None)
                promo_code = ''
                promo_discount_amount = Decimal('0')
                message_text = (
                    "⚠️ Промокод больше недействителен и был снят.\n\n"
                ) + message_text
            else:
                try:
                    percent = Decimal(str(promo.get('discount_percent') or 0))
                except Exception:
                    percent = Decimal('0')
                try:
                    amount = Decimal(str(promo.get('discount_amount') or 0))
                except Exception:
                    amount = Decimal('0')

                if percent > 0:
                    promo_discount_amount = (final_price * percent / 100).quantize(Decimal('0.01'))
                elif amount > 0:
                    promo_discount_amount = amount.quantize(Decimal('0.01')) if hasattr(amount, 'quantize') else Decimal(str(amount))
                if promo_discount_amount > 0:
                    # Clamp so price never becomes 0 or negative
                    if promo_discount_amount >= final_price:
                        promo_discount_amount = (final_price - Decimal('0.01')).quantize(Decimal('0.01'))
                    final_price = (final_price - promo_discount_amount).quantize(Decimal('0.01'))
                    if final_price < Decimal('0.01'):
                        final_price = Decimal('0.01')
                    message_text = (
                        f"🎟 Промокод {promo_code} применён!\n"
                        f"Старая цена: <s>{price:.2f} RUB</s>\n"
                        f"<b>Новая цена: {final_price:.2f} RUB</b>\n\n"
                    ) + CHOOSE_PAYMENT_METHOD_MESSAGE

                await state.update_data(
                    promo_code=promo.get('code'),
                    promo_percent=float(percent) if percent and percent > 0 else None,
                    promo_amount=float(amount) if amount and amount > 0 else None,
                    promo_discount=float(promo_discount_amount) if promo_discount_amount > 0 else 0,
                )

        await state.update_data(final_price=float(final_price))


        try:
            main_balance = get_balance(message.chat.id)
        except Exception:
            main_balance = 0.0
        try:
            ref_balance = get_referral_balance(message.chat.id)
        except Exception:
            ref_balance = 0.0

        show_balance_btn = main_balance >= float(final_price)
        show_ref_balance_btn = ref_balance >= float(final_price)

        try:
            await message.edit_text(
                message_text,
                reply_markup=keyboards.create_payment_method_keyboard(
                    payment_methods=_get_payment_methods(),
                    action=data.get('action'),
                    key_id=data.get('key_id'),
                    show_balance=show_balance_btn,
                    main_balance=main_balance,
                    referral_balance=(ref_balance if show_ref_balance_btn else None),
                    price=float(final_price),
                    promo_applied=bool(data.get('promo_code')),
                )
            )
        except TelegramBadRequest:
            await message.answer(
                message_text,
                reply_markup=keyboards.create_payment_method_keyboard(
                    payment_methods=_get_payment_methods(),
                    action=data.get('action'),
                    key_id=data.get('key_id'),
                    show_balance=show_balance_btn,
                    main_balance=main_balance,
                    referral_balance=(ref_balance if show_ref_balance_btn else None),
                    price=float(final_price)
                )
        )
        await state.set_state(PaymentProcess.waiting_for_payment_method)

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "back_to_email_prompt")
    async def back_to_email_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        email_prompt_enabled = (_is_true(get_setting("payment_email_prompt_enabled") or "false"))
        if not email_prompt_enabled:
            await back_to_plans_handler(callback, state)
            return
        await callback.message.edit_text(
            "📧 Пожалуйста, введите ваш email для отправки чека об оплате.\n\n"
            "Если вы не хотите указывать почту, нажмите кнопку ниже.",
            reply_markup=keyboards.create_skip_email_keyboard()
        )
        await state.set_state(PaymentProcess.waiting_for_email)
        
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "enter_promo_code")
    async def prompt_promo_code(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "🎟 Введите промокод. Напишите 'отмена', чтобы вернуться без изменений:",
            reply_markup=keyboards.create_cancel_keyboard("cancel_promo")
        )
        await state.set_state(PaymentProcess.waiting_for_promo_code)

    @user_router.callback_query(PaymentProcess.waiting_for_promo_code, F.data == "cancel_promo")
    async def cancel_promo_entry(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Отменено")
        await show_payment_options(callback.message, state)

    @user_router.message(PaymentProcess.waiting_for_promo_code)
    async def handle_promo_code_input(message: types.Message, state: FSMContext):
        code_raw = (message.text or '').strip()
        if not code_raw:
            await message.answer("❌ Промокод не должен быть пустым. Попробуйте снова или напишите 'отмена'.")
            return
        if code_raw.lower() in {"отмена", "cancel", "назад", "stop", "стоп"}:
            await show_payment_options(message, state)
            return
        data = await state.get_data()
        promo, error = check_promo_code_available(
            code_raw, message.from_user.id, plan_id=data.get("plan_id")
        )
        if error:
            await message.answer(f"❌ {promo_error_message(error)}")
            return
        discount_amount = Decimal(str(promo.get('discount_amount') or 0))
        percent = Decimal(str(promo.get('discount_percent') or 0))
        if percent > 0:
            data = await state.get_data()
            plan = get_plan_by_id(data.get('plan_id'))
            plan_price = Decimal(str(plan['price'])) if plan else Decimal('0')
            discount_amount = (plan_price * percent / 100).quantize(Decimal("0.01"))
        if discount_amount <= 0:
            await message.answer("❌ Промокод не даёт скидку. Обратитесь в поддержку.")
            return
        try:
            promo_amount_raw = Decimal(str(promo.get('discount_amount') or 0))
        except Exception:
            promo_amount_raw = Decimal('0')
        await state.update_data(
            promo_code=promo['code'],
            promo_percent=float(percent) if percent and percent > 0 else None,
            promo_amount=float(promo_amount_raw) if promo_amount_raw and promo_amount_raw > 0 else None,
            promo_discount=float(discount_amount),
        )
        await message.answer(f"✅ Промокод {promo['code']} применён! Скидка: {float(discount_amount):.2f} RUB.")
        await show_payment_options(message, state)

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_yookassa")
    async def create_yookassa_payment_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        
        # Ensure YooKassa configuration is set
        yookassa_shop_id = get_setting("yookassa_shop_id")
        yookassa_secret_key = get_setting("yookassa_secret_key")
        
        if not yookassa_shop_id or not yookassa_secret_key:
            await callback.message.answer("❌ YooKassa не настроен. Обратитесь к администратору.")
            await state.clear()
            return
            
        Configuration.account_id = yookassa_shop_id
        Configuration.secret_key = yookassa_secret_key
        
        data = await state.get_data()
        user_data = get_user(callback.from_user.id)
        
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        price_rub = base_price

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                base_price -= discount_amount
        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            discount_amount = promo_discount
            base_price = (base_price - discount_amount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')
        price_rub = base_price

        plan_id = data.get('plan_id')
        customer_email = data.get('customer_email')
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        
        if not customer_email:
            customer_email = get_setting("receipt_email")

        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)
        user_id = callback.from_user.id

        try:
            price_str_for_api = f"{price_rub:.2f}"
            price_float_for_metadata = float(price_rub)

            receipt = None
            if customer_email and is_valid_email(customer_email):
                receipt = {
                    "customer": {"email": customer_email},
                    "items": [{
                        "description": f"Подписка на {duration_label}",
                        "quantity": "1.00",
                        "amount": {"value": price_str_for_api, "currency": "RUB"},
                        "vat_code": "1",
                        "payment_subject": "service",
                        "payment_mode": "full_payment"
                    }]
                }
            payment_id = str(uuid.uuid4())
            metadata = {
                "user_id": int(user_id),
                "months": int(months),
                "duration_days": int(duration_days),
                "price": float(price_float_for_metadata),
                "action": action,
                "key_id": key_id,
                "host_name": host_name,
                "plan_id": plan_id,
                "customer_email": customer_email,
                "payment_method": "YooKassa",
                "promo_code": promo_code,
                "promo_discount": float(data.get("promo_discount", 0)),
                "payment_id": payment_id,
            }
            try:
                create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata)
            except PromoUnavailableError:
                await callback.message.answer("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
                return
            except Exception as e:
                logger.warning(f"YooKassa: не удалось создать pending для {payment_id}: {e}")

            payment_payload = {
                "amount": {"value": price_str_for_api, "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{TELEGRAM_BOT_USERNAME}"},
                "capture": True,
                "description": f"Подписка на {duration_label}",
                "metadata": {"payment_id": payment_id}
            }
            if receipt:
                payment_payload['receipt'] = receipt

            payment = Payment.create(payment_payload, uuid.uuid4())
            try:
                provider_payment_id = getattr(payment, "id", None)
                if provider_payment_id:
                    metadata2 = dict(metadata)
                    metadata2["yookassa_payment_id"] = str(provider_payment_id)
                    create_payload_pending(payment_id, int(user_id), float(price_float_for_metadata), metadata2)
            except Exception as e:
                logger.warning(f"YooKassa: не удалось сохранить provider id для {payment_id}: {e}")
            
            await state.clear()
            
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_yookassa_payment_keyboard(payment.confirmation.confirmation_url, payment_id)
            )
        except Exception as e:
            logger.error(f"Failed to create YooKassa payment: {e}", exc_info=True)
            await callback.message.answer("Не удалось создать ссылку на оплату.")
            await state.clear()

    
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_platega")
    async def pay_platega_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку Platega...")
        if not _platega_is_enabled():
            await callback.message.edit_text("❌ Platega не настроен. Обратитесь к администратору.")
            await state.clear()
            return

        data = await state.get_data()
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        # финальная цена (учитывает рефералку/промокод)
        base_price = Decimal(str(plan['price']))
        user_data = get_user(callback.from_user.id) or {}
        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            try:
                discount_percentage = Decimal(str(get_setting("referral_discount") or "0"))
            except Exception:
                discount_percentage = Decimal('0')
            if discount_percentage > 0:
                base_price -= (base_price * discount_percentage / 100).quantize(Decimal("0.01"))

        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            base_price = (base_price - promo_discount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')

        payment_id = str(uuid.uuid4())

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        customer_email = data.get('customer_email') or get_setting("receipt_email")

        metadata = {
            "user_id": callback.from_user.id,
            "months": months,
            "duration_days": duration_days,
            "price": float(base_price),
            "action": action,
            "key_id": key_id,
            "host_name": host_name,
            "plan_id": plan_id,
            "customer_email": customer_email,
            "payment_method": "Platega",
            "payment_id": payment_id,
            "promo_code": promo_code,
            "promo_discount": float(data.get('promo_discount', 0)),
        }

        # сохраняем pending
        try:
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata)
        except PromoUnavailableError:
            await callback.message.edit_text("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
            await state.clear()
            return

        desc = f"Подписка на {months} мес." if months else "Оплата подписки"
        pay_url, txid = await _create_platega_payment_link(amount_rub=base_price, payment_id=payment_id, description=desc)
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку Platega. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        # обновляем pending с id транзакции (для ручной проверки)
        try:
            metadata2 = dict(metadata)
            metadata2["platega_transaction_id"] = txid
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_platega_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_rollypay")
    async def pay_rollypay_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю ссылку на оплату...")
        if not _rollypay_is_enabled():
            await callback.message.edit_text("❌ Оплата по СБП не настроена. Обратитесь к администратору.")
            await state.clear()
            return

        data = await state.get_data()
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        user_data = get_user(callback.from_user.id) or {}
        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            try:
                discount_percentage = Decimal(str(get_setting("referral_discount") or "0"))
            except Exception:
                discount_percentage = Decimal('0')
            if discount_percentage > 0:
                base_price -= (base_price * discount_percentage / 100).quantize(Decimal("0.01"))

        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            base_price = (base_price - promo_discount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')

        payment_id = str(uuid.uuid4())

        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')
        customer_email = data.get('customer_email') or get_setting("receipt_email")

        metadata = {
            "user_id": callback.from_user.id,
            "months": months,
            "duration_days": duration_days,
            "price": float(base_price),
            "action": action,
            "key_id": key_id,
            "host_name": host_name,
            "plan_id": plan_id,
            "customer_email": customer_email,
            "payment_method": "RollyPay",
            "payment_id": payment_id,
            "promo_code": promo_code,
            "promo_discount": float(data.get('promo_discount', 0)),
        }

        try:
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata)
        except PromoUnavailableError:
            await callback.message.edit_text("❌ Промокод больше недоступен. Выберите оплату без него или другой промокод.")
            await state.clear()
            return

        desc = f"Подписка на {months} мес." if months else "Оплата подписки"
        pay_url, provider_id = await _create_rollypay_payment_link(
            amount_rub=base_price, payment_id=payment_id, description=desc,
            customer_id=str(callback.from_user.id),
        )
        if not pay_url:
            await callback.message.edit_text("❌ Не удалось создать ссылку. Попробуйте позже или выберите другой способ оплаты.")
            await state.clear()
            return

        try:
            metadata2 = dict(metadata)
            metadata2["rollypay_payment_id"] = provider_id
            create_payload_pending(payment_id, callback.from_user.id, float(base_price), metadata2)
        except Exception:
            pass

        await callback.message.edit_text(
            "Нажмите на кнопку ниже для оплаты:",
            reply_markup=keyboards.create_rollypay_payment_keyboard(pay_url, payment_id)
        )
        await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_cryptobot")
    async def create_cryptobot_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Создаю счет в Crypto Pay...")
        
        data = await state.get_data()
        user_data = get_user(callback.from_user.id)
        
        plan_id = data.get('plan_id')
        user_id = data.get('user_id', callback.from_user.id)
        customer_email = data.get('customer_email')
        host_name = data.get('host_name')
        action = data.get('action')
        key_id = data.get('key_id')

        cryptobot_token = get_setting('cryptobot_token')
        if not cryptobot_token:
            logger.error(f"Attempt to create Crypto Pay invoice failed for user {user_id}: cryptobot_token is not set.")
            await callback.message.edit_text("❌ Оплата криптовалютой временно недоступна. (Администратор не указал токен).")
            await state.clear()
            return

        plan = get_plan_by_id(plan_id)
        if not plan:
            logger.error(f"Attempt to create Crypto Pay invoice failed for user {user_id}: Plan with id {plan_id} not found.")
            await callback.message.edit_text("❌ Произошла ошибка при выборе тарифа.")
            await state.clear()
            return
        
        plan_id = data.get('plan_id')
        plan = get_plan_by_id(plan_id)

        if not plan:
            await callback.message.answer("Произошла ошибка при выборе тарифа.")
            await state.clear()
            return

        base_price = Decimal(str(plan['price']))
        price_rub_decimal = base_price

        if user_data.get('referred_by') and user_data.get('total_spent', 0) == 0:
            discount_percentage_str = get_setting("referral_discount") or "0"
            discount_percentage = Decimal(discount_percentage_str)
            if discount_percentage > 0:
                discount_amount = (base_price * discount_percentage / 100).quantize(Decimal("0.01"))
                base_price -= discount_amount
        promo_code = data.get('promo_code')
        promo_discount = Decimal(str(data.get('promo_discount', 0)))
        if promo_code and promo_discount > 0:
            discount_amount = promo_discount
            base_price = (base_price - discount_amount).quantize(Decimal("0.01"))
            if base_price < Decimal('0.01'):
                base_price = Decimal('0.01')
        price_rub_decimal = base_price
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        duration_label = _format_duration_label(months, duration_days)
        
        final_price_float = float(price_rub_decimal)

        result = await _create_cryptobot_invoice(
            user_id=callback.from_user.id,
            price_rub=final_price_float,
            months=plan['months'],
            host_name=data.get('host_name'),
            state_data=data
        )
        
        if result:
            pay_url, invoice_id = result
            await callback.message.edit_text(
                "Нажмите на кнопку ниже для оплаты:",
                reply_markup=keyboards.create_cryptobot_payment_keyboard(pay_url, invoice_id)
            )
            await state.clear()
        else:
            await callback.message.edit_text("❌ Не удалось создать счёт в CryptoBot. Попробуйте другой способ оплаты.")

    @user_router.callback_query(F.data.startswith("check_crypto_invoice:"))
    async def check_crypto_invoice_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer("Проверяю статус оплаты...")
        try:
            parts = (callback.data or "").split(":", 1)
            invoice_id_str = parts[1] if len(parts) > 1 else ""
            invoice_id = int(invoice_id_str)
        except Exception:
            await callback.message.answer("❌ Некорректный идентификатор инвойса.")
            return

        token = (get_setting("cryptobot_token") or "").strip()
        if not token:
            await callback.message.answer("❌ CryptoBot токен не задан.")
            return

        url = "https://pay.crypt.bot/api/getInvoices"
        headers = {
            "Crypto-Pay-API-Token": token,
            "Content-Type": "application/json",
        }
        body = {"invoice_ids": [invoice_id]}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=body, timeout=20) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"CryptoBot getInvoices HTTP {resp.status}: {text}")
                        await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")
                        return
                    data = await resp.json(content_type=None)
        except Exception as e:
            logger.error(f"CryptoBot getInvoices failed: {e}", exc_info=True)
            await callback.message.answer("⏳ Не удалось проверить статус. Попробуйте позже.")
            return


        invoices = []
        if isinstance(data, dict) and data.get("ok"):
            res = data.get("result")
            if isinstance(res, dict) and isinstance(res.get("items"), list):
                invoices = res.get("items")
            elif isinstance(res, list):
                invoices = res

        if not invoices:
            await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")
            return

        inv = invoices[0]
        status = (inv.get("status") or inv.get("invoice_status") or "").lower()
        if status != "paid":
            await callback.message.answer("⏳ Оплата ещё не поступила. Попробуйте позже.")
            return

        payload_string = (inv.get("payload") or "").strip()
        if not payload_string:
            await callback.message.answer("⚠️ Оплата получена, но отсутствует payload. Обратитесь в поддержку.")
            return

        # New format: payload == our internal payment_id
        if ':' not in payload_string:
            internal_payment_id = payload_string
            pending = get_pending_metadata(internal_payment_id)
            if not pending:
                await callback.message.answer("✅ Платёж уже обработан или не найден.")
                return
            # Amount check (fiat RUB invoices)
            try:
                inv_amount = Decimal(str(inv.get("amount") or inv.get("fiat_amount") or inv.get("paid_amount") or '0')).quantize(Decimal('0.01'))
                exp_amount = Decimal(str(pending.get('price') or '0')).quantize(Decimal('0.01'))
                if exp_amount > 0 and inv_amount != exp_amount:
                    await callback.message.answer("⚠️ Сумма оплаты не совпала с ожидаемой. Обратитесь в поддержку.")
                    return
            except Exception:
                pass

            metadata = find_and_complete_pending_transaction(internal_payment_id)
            if not metadata:
                await callback.message.answer("✅ Платёж уже обработан.")
                return

            try:
                await process_successful_payment(bot, metadata)
                await callback.message.answer("✅ Оплата получена! Профиль/баланс скоро обновится.")
            except Exception as e:
                logger.error(f"CryptoBot manual check: process_successful_payment failed: {e}", exc_info=True)
                await callback.message.answer("⚠️ Оплата получена, но обработка не завершена. Обратитесь в поддержку.")
            return

        # Legacy format: payload was a colon-separated metadata string
        p = payload_string.split(":")
        if len(p) < 9:
            await callback.message.answer("⚠️ Оплата получена, но формат данных некорректен. Обратитесь в поддержку.")
            return

        # Amount check for legacy payload
        try:
            inv_amount = Decimal(str(inv.get("amount") or inv.get("fiat_amount") or inv.get("paid_amount") or '0')).quantize(Decimal('0.01'))
            exp_amount = Decimal(str(p[2] or '0')).quantize(Decimal('0.01'))
            if exp_amount > 0 and inv_amount != exp_amount:
                await callback.message.answer("⚠️ Сумма оплаты не совпала с ожидаемой. Обратитесь в поддержку.")
                return
        except Exception:
            pass

        metadata = {
            "user_id": p[0],
            "months": p[1],
            "price": p[2],
            "action": p[3],
            "key_id": p[4],
            "host_name": p[5],
            "plan_id": p[6],
            "customer_email": (p[7] if p[7] != 'None' else None),
            "payment_method": p[8] or 'CryptoBot',
            "transaction_id": str(invoice_id),
            "payment_id": f'cryptobot:{invoice_id}',
        }

        try:
            await process_successful_payment(bot, metadata)
            await callback.message.answer("✅ Оплата получена! Профиль/баланс скоро обновится.")
        except Exception as e:
            logger.error(f"CryptoBot manual check: process_successful_payment failed: {e}", exc_info=True)
            await callback.message.answer("⚠️ Оплата получена, но обработка не завершена. Обратитесь в поддержку.")
    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_tonconnect")
    async def create_ton_invoice_handler(callback: types.CallbackQuery, state: FSMContext):
        logger.info(f"User {callback.from_user.id}: Entered create_ton_invoice_handler.")
        data = await state.get_data()
        user_id = callback.from_user.id
        wallet_address = get_setting("ton_wallet_address")
        plan = get_plan_by_id(data.get('plan_id'))
        
        if not wallet_address or not plan:
            await callback.message.edit_text("❌ Оплата через TON временно недоступна.")
            await state.clear()
            return

        await callback.answer("Создаю ссылку и QR-код для TON Connect...")
            
        price_rub = Decimal(str(data.get('final_price', plan['price'])))

        usdt_rub_rate = await get_usdt_rub_rate()
        ton_usdt_rate = await get_ton_usdt_rate()

        if not usdt_rub_rate or not ton_usdt_rate:
            await callback.message.edit_text("❌ Не удалось получить курс TON. Попробуйте позже.")
            await state.clear()
            return

        price_ton = (price_rub / usdt_rub_rate / ton_usdt_rate).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        amount_nanoton = int(price_ton * 1_000_000_000)
        
        payment_id = str(uuid.uuid4())
        metadata = {
            "user_id": user_id, "months": int(plan.get('months') or 0), "duration_days": int(plan.get('duration_days') or 0), "price": float(price_rub),
            "action": data.get('action'), "key_id": data.get('key_id'),
            "host_name": data.get('host_name'), "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'), "payment_method": "TON Connect",
            "expected_amount_ton": float(price_ton)
        }
        create_pending_transaction(payment_id, user_id, float(price_rub), metadata)

        transaction_payload = {
            'messages': [{'address': wallet_address, 'amount': str(amount_nanoton), 'payload': payment_id}],
            'valid_until': int(datetime.now().timestamp()) + 600
        }

        try:
            connect_url = await _start_ton_connect_process(user_id, transaction_payload)
            
            qr_img = qrcode.make(connect_url)
            bio = BytesIO()
            qr_img.save(bio, "PNG")
            qr_file = BufferedInputFile(bio.getvalue(), "ton_qr.png")

            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr_file,
                caption=(
                    f"💎 **Оплата через TON Connect**\n\n"
                    f"Сумма к оплате: `{price_ton}` **TON**\n\n"
                    f"✅ **Способ 1 (на телефоне):** Нажмите кнопку **'Открыть кошелек'** ниже.\n"
                    f"✅ **Способ 2 (на компьютере):** Отсканируйте QR-код кошельком.\n\n"
                    f"После подключения кошелька подтвердите транзакцию."
                ),
                parse_mode="Markdown",
                reply_markup=keyboards.create_ton_connect_keyboard(connect_url)
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Failed to generate TON Connect link for user {user_id}: {e}", exc_info=True)
            await callback.message.answer("❌ Не удалось создать ссылку для TON Connect. Попробуйте позже.")
            await state.clear()

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_balance")
    async def pay_with_main_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        price = float(data.get('final_price', plan['price']))


        if not deduct_from_balance(user_id, price):
            await callback.answer("Недостаточно средств на основном балансе.", show_alert=True)
            return

        promo_code = (data.get('promo_code') or '').strip() if isinstance(data, dict) else ''
        promo_discount = float(data.get('promo_discount') or 0) if promo_code else 0.0

        metadata = {
            "user_id": user_id,
            "months": months,
            "duration_days": duration_days,
            "price": price,
            "action": data.get('action'),
            "key_id": data.get('key_id'),
            "host_name": data.get('host_name'),
            "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'),
            "payment_method": "Balance",
            "chat_id": callback.message.chat.id,
            "message_id": callback.message.message_id,
            "promo_code": promo_code,
            "promo_discount": promo_discount,
        }
        # Для оплаты с внутреннего баланса у нас нет внешнего идентификатора платежа.
        # Генерируем уникальный payment_id, чтобы process_successful_payment смог
        # корректно отработать и пройти идемпотентную проверку.
        metadata.setdefault("payment_id", f"balance:{user_id}:{uuid.uuid4()}")

        await state.clear()
        await process_successful_payment(bot, metadata)

    @user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == "pay_referral_balance")
    async def pay_with_referral_balance_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        data = await state.get_data()
        user_id = callback.from_user.id
        plan = get_plan_by_id(data.get('plan_id'))
        if not plan:
            await callback.message.edit_text("❌ Ошибка: Тариф не найден.")
            await state.clear()
            return
        months = int(plan.get('months') or 0)
        duration_days = int(plan.get('duration_days') or 0)
        price = float(data.get('final_price', plan['price']))

        if not deduct_from_referral_balance(user_id, price):
            await callback.answer("Недостаточно средств на реферальном балансе.", show_alert=True)
            return

        promo_code = (data.get('promo_code') or '').strip() if isinstance(data, dict) else ''
        promo_discount = float(data.get('promo_discount') or 0) if promo_code else 0.0

        metadata = {
            "user_id": user_id,
            "months": months,
            "duration_days": duration_days,
            "price": price,
            "action": data.get('action'),
            "key_id": data.get('key_id'),
            "host_name": data.get('host_name'),
            "plan_id": data.get('plan_id'),
            "customer_email": data.get('customer_email'),
            "payment_method": "ReferralBalance",
            "chat_id": callback.message.chat.id,
            "message_id": callback.message.message_id,
            "promo_code": promo_code,
            "promo_discount": promo_discount,
        }
        metadata.setdefault("payment_id", f"referral_balance:{user_id}:{uuid.uuid4()}")

        await state.clear()
        await process_successful_payment(bot, metadata)

    _STALE_PAY_CALLBACKS = {
        "pay_balance",
        "pay_referral_balance",
        "pay_stars",
        "pay_yookassa",
        "pay_platega",
        "pay_rollypay",
        "pay_cryptobot",
        "pay_heleket",
        "pay_yoomoney",
        "pay_tonconnect",
    }

    @user_router.callback_query(F.data.in_(_STALE_PAY_CALLBACKS))
    async def stale_payment_method_callback(callback: types.CallbackQuery):
        """Устаревшие pay_* после смены FSM (например, после Stars invoice).

        Регистрируется после штатных обработчиков waiting_for_payment_method,
        чтобы не перехватывать живой сценарий выбора метода.
        """
        await callback.answer(
            "Сессия оплаты устарела. Выберите тариф и способ оплаты заново.",
            show_alert=True,
        )



    
    @user_router.message(StateFilter(None), F.text)
    @registration_required
    async def _gift_username_catcher(message: types.Message):
        logger.info(f"Gift catcher: incoming text from {message.from_user.id}: {message.text}")
        text = (message.text or "").strip()
        if not text:
            return
        if text.startswith("@"):
            text = text[1:]
        import re as _re
        if not _re.match(r"^[A-Za-z0-9_]{5,}$", text):
            return
        
        pending = None
        try:
            pending = get_latest_pending_for_user(message.from_user.id)
        except Exception as e:
            logger.info(f"Gift catcher: DB not available or error: {e}")
        if not pending:
            try:
                pending = PENDING_GIFTS.get(int(message.from_user.id))
                if pending:
                    logger.info(f"Gift catcher: fallback cache hit for {message.from_user.id}: {pending}")
            except Exception:
                pending = None
        if not pending or (pending.get("type") != "gift"):
            logger.info(f"Gift catcher: no pending gift for {message.from_user.id}")
            return
        
        host_name = pending.get("host_name")
        months = int(pending.get("months") or 0)
        duration_days = int(pending.get("duration_days") or 0)
        days_to_add = int(pending.get("days_to_add") or 0)
        if days_to_add <= 0:
            days_to_add = _compute_days_to_add(months, duration_days)
        recipient_user = None
        try:
            recipient_user = get_user_by_username(text)
        except Exception:
            recipient_user = None
        recipient_email = None
        if recipient_user and recipient_user.get("telegram_id"):
            try:
                recipient_id = int(recipient_user["telegram_id"])
            except Exception:
                recipient_id = None
            if recipient_id:
                try:
                    recipient_email = rw_repo.generate_key_email_for_user(recipient_id)
                except Exception:
                    recipient_email = f"{recipient_id}-{int(time.time())}@bot.local"
        if not recipient_email:
            recipient_email = f"gift-{uuid.uuid4().hex[:8]}@bot.local"
        
        try:
            result = await remnawave_api.create_or_update_key_on_host(
                host_name=host_name,
                email=recipient_email,
                days_to_add=int(days_to_add),
                description=f"Gift for @{text} from {message.from_user.id}",
                raise_on_error=True,
            )
        except Exception as exc:
            try:
                price = float(pending.get("price") or 0.0)
            except Exception:
                price = None
            await _handle_key_creation_failure(
                message.bot,
                user_id=message.from_user.id,
                action_label=_format_key_action_label("gift", price=price),
                exc=exc,
                refund=True,
            )
            return
        
        if not result:
            try:
                price = float(pending.get("price") or 0.0)
            except Exception:
                price = None
            await _handle_key_creation_failure(
                message.bot,
                user_id=message.from_user.id,
                action_label=_format_key_action_label("gift", price=price),
                exc=RuntimeError("gift key creation returned empty response"),
                refund=True,
            )
            return
        
        # Привязываем ключ к локальному аккаунту получателя, если он уже пользовался ботом
        try:
            ru = recipient_user or get_user_by_username(text)
            if ru and ru.get('telegram_id'):
                rw_repo.record_key_from_payload(
                    user_id=int(ru['telegram_id']),
                    payload=result,
                    host_name=host_name,
                    tag="paid",
                    description=_build_key_origin_meta(
                        source="gift",
                        plan_id=None,
                        plan_name=None,
                        months=months,
                        duration_days=duration_days,
                        is_trial=False,
                        note=f"Gift received from {message.from_user.id}",
                    )
                )
                logger.info(f"Gift: key attached to local user {ru['telegram_id']}")
        except Exception as e:
            logger.warning(f"Gift: failed to record gifted key for recipient: {e}")
        
        try:
            pid = pending.get("payment_id")
            if pid:
                find_and_complete_pending_transaction(str(pid))
        except Exception:
            pass
        try:
            PENDING_GIFTS.pop(int(message.from_user.id), None)
        except Exception:
            pass
        
        await message.reply("✅ Подарочный ключ создан для пользователя @{}\nКлюч уже активен в панели, пользователь сможет подключиться сразу.".format(text))


    # =============================
    # Franchise (clone bots)
    # =============================

    def _kb_cancel_factory() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="factory_cancel")
        b.adjust(1)
        return b.as_markup()

    def _kb_partner_cabinet() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="💳 Реквизиты", callback_data="partner_requisites")
        b.button(text="💸 Вывод средств", callback_data="partner_withdraw")
        b.button(text="🗑 Удалить моего бота", callback_data="factory_del_self")
        b.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
        b.adjust(1, 1, 1, 1)
        return b.as_markup()

    def _kb_partner_withdraw() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="partner_withdraw_cancel")
        b.adjust(1)
        return b.as_markup()


    def _kb_partner_requisites(items: list[dict] | None = None) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="➕ Добавить карту", callback_data="partner_requisite_add")
        items = items or []
        # One row per action to keep callback_data short and stable
        for r in items[:20]:
            rid = int(r.get("id") or 0)
            if rid <= 0:
                continue
            is_def = int(r.get("is_default") or 0) == 1
            if not is_def:
                b.button(text=f"✅ Сделать основной #{rid}", callback_data=f"req_set_default:{rid}")
            b.button(text=f"🗑 Удалить #{rid}", callback_data=f"req_delete:{rid}")
        b.button(text="⬅️ Назад", callback_data="partner_cabinet")
        b.adjust(1)
        return b.as_markup()

    def _kb_partner_requisite_input() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="partner_requisite_cancel")
        b.adjust(1)
        return b.as_markup()

    def _mask_requisite(value: str, rtype: str) -> str:
        s = (value or '').strip()
        digits = ''.join(ch for ch in s if ch.isdigit())
        if not digits:
            return s
        last4 = digits[-4:]
        masked = '*' * max(0, len(digits) - 4) + last4
        # group in 4s for cards
        if (rtype or '').lower() == 'card' and len(digits) >= 12:
            parts = [masked[max(0, i-4):i] for i in range(len(masked), 0, -4)]
            masked = ' '.join(reversed(parts))
        return masked

    def _infer_requisite_type(value: str) -> str:
        digits = ''.join(ch for ch in (value or '') if ch.isdigit())
        # heuristic: 10-12 digits - чаще телефон, 13-19 - чаще карта
        if 10 <= len(digits) <= 12:
            return 'phone'
        if 13 <= len(digits) <= 19:
            return 'card'
        # fallback
        return 'card'

    @user_router.callback_query(F.data == "partner_requisites")
    @catch_callback_errors
    async def partner_requisites(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        try:
            await state.clear()
        except Exception:
            pass
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Реквизиты доступны только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Доступно только владельцу.", show_alert=True)
            return

        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        lines = ["💳 <b>Реквизиты</b>", ""]
        if not items:
            lines.append("Пока нет привязанных реквизитов.")
            lines.append("Нажмите <b>«Добавить карту»</b> и укажите банк и номер карты или телефона.")
        else:
            for i, r in enumerate(items, 1):
                bank = html_escape(str(r.get('bank') or ''))
                rtype = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rtype == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rtype)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank} — {label}: <code>{masked}</code> (id={r.get('id')})")
        text = "\n".join(lines)
        await cb.message.edit_text(text, reply_markup=_kb_partner_requisites(items), disable_web_page_preview=True)
        await fast_callback_answer(cb)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_requisite_add")
    @catch_callback_errors
    async def partner_requisite_add(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Доступно только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Только владелец.", show_alert=True)
            return

        await state.set_state(FranchiseStates.waiting_requisites_bank)
        await cb.message.edit_text(
            "🏦 <b>Добавление реквизитов</b>\n\nВведите название банка (например: <code>Тинькофф</code>):",
            reply_markup=_kb_partner_requisite_input(),
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_requisite_cancel")
    @catch_callback_errors
    async def partner_requisite_cancel(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        try:
            await state.clear()
        except Exception:
            pass
        try:
            await partner_requisites(cb, state, bot)
        except Exception:
            try:
                await partner_cabinet(cb, bot)
            except Exception:
                pass
        await fast_callback_answer(cb)

    @user_router.message(FranchiseStates.waiting_requisites_bank)
    @registration_required
    async def partner_requisite_bank(message: types.Message, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(message.from_user.id) != owner_id:
            await message.answer("Только владелец.")
            try:
                await state.clear()
            except Exception:
                pass
            return

        bank = (message.text or '').strip()
        if not bank:
            await message.answer("Укажите банк текстом.")
            return
        await state.update_data(req_bank=bank)
        await state.set_state(FranchiseStates.waiting_requisites_value)
        await message.answer(
            "💳 Теперь пришлите <b>номер карты</b> или <b>номер телефона</b> (как удобно):",
            reply_markup=_kb_partner_requisite_input(),
        )

    @user_router.message(FranchiseStates.waiting_requisites_value)
    @registration_required
    async def partner_requisite_value(message: types.Message, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(message.from_user.id) != owner_id:
            await message.answer("Только владелец.")
            try:
                await state.clear()
            except Exception:
                pass
            return

        data = await state.get_data()
        bank = (data.get('req_bank') or '').strip()
        value = (message.text or '').strip()
        if not bank:
            await message.answer("Не вижу банк. Попробуйте ещё раз.")
            await state.set_state(FranchiseStates.waiting_requisites_bank)
            return
        if not value:
            await message.answer("Укажите номер карты или телефона.")
            return

        rtype = _infer_requisite_type(value)
        ok, msg, _new_id = rw_repo.add_partner_requisite(bot_id, owner_id, bank, value, rtype)
        await message.answer(("✅ " if ok else "❌ ") + msg)
        try:
            await state.clear()
        except Exception:
            pass

        # show list
        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        lines = ["💳 <b>Реквизиты</b>", ""]
        if not items:
            lines.append("Пока нет привязанных реквизитов.")
        else:
            for i, r in enumerate(items, 1):
                bank_e = html_escape(str(r.get('bank') or ''))
                rt = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rt == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rt)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank_e} — {label}: <code>{masked}</code> (id={r.get('id')})")
        await message.answer("\n".join(lines), reply_markup=_kb_partner_requisites(items))

    @user_router.callback_query(F.data.startswith("req_set_default:"))
    @catch_callback_errors
    async def partner_requisite_set_default(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if bot_id <= 0 or int(cb.from_user.id) != owner_id:
            await cb.answer("Недостаточно прав.", show_alert=True)
            return
        try:
            rid = int((cb.data or '').split(':', 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        ok, msg = rw_repo.set_default_partner_requisite(rid, bot_id, owner_id)
        await cb.answer(("✅ " if ok else "❌ ") + msg, show_alert=not ok)
        # refresh
        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        try:
            await partner_requisites(cb, state, bot)
        except Exception:
            # rebuild text quickly
            lines = ["💳 <b>Реквизиты</b>", ""]
            for i, r in enumerate(items, 1):
                bank_e = html_escape(str(r.get('bank') or ''))
                rt = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rt == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rt)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank_e} — {label}: <code>{masked}</code> (id={r.get('id')})")
            await cb.message.edit_text("\n".join(lines), reply_markup=_kb_partner_requisites(items), disable_web_page_preview=True)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data.startswith("req_delete:"))
    @catch_callback_errors
    async def partner_requisite_delete(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if bot_id <= 0 or int(cb.from_user.id) != owner_id:
            await cb.answer("Недостаточно прав.", show_alert=True)
            return
        try:
            rid = int((cb.data or '').split(':', 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        ok, msg = rw_repo.delete_partner_requisite(rid, bot_id, owner_id)
        await cb.answer(("✅ " if ok else "❌ ") + msg, show_alert=not ok)
        # refresh list
        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        lines = ["💳 <b>Реквизиты</b>", ""]
        if not items:
            lines.append("Пока нет привязанных реквизитов.")
        else:
            for i, r in enumerate(items, 1):
                bank_e = html_escape(str(r.get('bank') or ''))
                rt = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rt == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rt)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank_e} — {label}: <code>{masked}</code> (id={r.get('id')})")
        await cb.message.edit_text("\n".join(lines), reply_markup=_kb_partner_requisites(items), disable_web_page_preview=True)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "factory_create_bot")
    @catch_callback_errors
    async def franchise_create_bot(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        # Creation is allowed only from the root bot UI
        try:
            current_bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        except Exception:
            current_bot_id = 0
        if current_bot_id > 0:
            await cb.answer("Создание бота доступно только в основном боте.", show_alert=True)
            return

        text = (
            "🤖 <b>Отправьте Token вашего бота</b>\n\n"
            "1. Перейдите в @BotFather\n"
            "2. Создайте нового бота (/newbot)\n"
            "3. Скопируйте API TOKEN\n"
            "4. Пришлите его в этот чат сообщением 👇"
        )
        await state.set_state(FranchiseStates.waiting_bot_token)
        try:
            await cb.message.edit_text(text, reply_markup=_kb_cancel_factory())
        except Exception:
            await cb.message.answer(text, reply_markup=_kb_cancel_factory())
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "factory_cancel")
    @catch_callback_errors
    async def franchise_cancel(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        try:
            await show_main_menu(cb.message, edit_message=True)
        except Exception:
            pass
        await fast_callback_answer(cb)

    @user_router.message(FranchiseStates.waiting_bot_token)
    @registration_required
    async def franchise_receive_token(message: types.Message, state: FSMContext, bot: Bot):
        token = (message.text or "").strip()
        if not TOKEN_RE.match(token):
            await message.answer("Похоже, это не токен. Пришлите токен в формате <code>123456:ABC...</code>.")
            return

        # Validate token
        try:
            tmp_bot = Bot(token=token)
            me = await tmp_bot.get_me()
            try:
                await tmp_bot.close()
            except Exception:
                try:
                    await tmp_bot.session.close()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            await message.answer("Не получилось проверить токен. Убедитесь, что он правильный и бот не заблокирован.")
            return

        ok, msg, new_bot_id = rw_repo.create_managed_bot(
            token=token,
            telegram_bot_user_id=me.id,
            username=getattr(me, "username", None),
            owner_telegram_id=message.from_user.id,
            referrer_bot_id=0,
        )
        if not ok or not new_bot_id:
            await message.answer(f"❌ {msg}")
            try:
                await state.clear()
            except Exception:
                pass
            return

        # Start the new bot immediately (if service is running)
        service = get_service()
        if service:
            try:
                await service.start_bot(new_bot_id)
            except Exception as e:
                logger.warning(f"Failed to start managed bot {new_bot_id}: {e}")

        uname = f"@{me.username}" if getattr(me, "username", None) else f"(id {me.id})"
        await message.answer(
            f"✅ Бот {uname} подключён.\n\n"
            "Откройте его и нажмите /start — у владельца появится кнопка «Личный кабинет»."
        )
        try:
            await state.clear()
        except Exception:
            pass

        # Return user to main menu
        try:
            await show_main_menu(message)
        except Exception:
            pass

    @user_router.callback_query(F.data == "partner_cabinet")
    @catch_callback_errors
    async def partner_cabinet(cb: types.CallbackQuery, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Кабинет доступен только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Кабинет доступен только владельцу.", show_alert=True)
            return

        st = rw_repo.get_partner_cabinet(bot_id) or {}
        gross = float(st.get("gross_paid_card", 0.0) or 0.0)
        com_total = float(st.get("commission_total", 0.0) or 0.0)
        avail = float(st.get("available", 0.0) or 0.0)
        users = int(st.get("total_users", 0) or 0)

        text = (
            "👤 <b>Личный кабинет</b>\n\n"
            f"Бот: @{info.get('username') or 'без_username'}\n"
            f"Пользователей: <b>{users}</b>\n\n"
            f"Оплачено картой: <b>{gross:.2f} ₽</b>\n"
            f"Ваш процент: <b>{get_franchise_percent_default():.1f}%</b>\n"
            f"Ваш доход: <b>{com_total:.2f} ₽</b>\n"
            f"Доступно к выводу: <b>{avail:.2f} ₽</b>\n\n"
            f"ℹ️ Минимальная сумма вывода: <b>{get_franchise_min_withdraw():.0f} ₽</b>\n"
        )
        await cb.message.edit_text(text, reply_markup=_kb_partner_cabinet(), disable_web_page_preview=True)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_withdraw")
    @catch_callback_errors
    async def partner_withdraw(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Вывод доступен только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Только владелец.", show_alert=True)
            return

        st = rw_repo.get_partner_cabinet(bot_id) or {}
        avail = float(st.get("available", 0.0) or 0.0)

        # Require payout requisites
        default_req = rw_repo.get_default_partner_requisite(bot_id, owner_id)
        if not default_req:
            items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
            await cb.message.edit_text(
                "💳 <b>Реквизиты не указаны</b>\n\n"
                "Сначала добавьте реквизиты для вывода (банк + номер карты или телефона).",
                reply_markup=_kb_partner_requisites(items),
            )
            await fast_callback_answer(cb)
            return

        await state.set_state(FranchiseStates.waiting_withdraw_amount)
        await cb.message.edit_text(
            "💸 <b>Вывод средств</b>\n\n"
            f"Доступно: <b>{avail:.2f} ₽</b>\n"
            f"Минимум: <b>{get_franchise_min_withdraw():.0f} ₽</b>\n\n"
            f"Введите сумму для вывода числом (например: <code>{get_franchise_min_withdraw():.0f}</code>):",
            reply_markup=_kb_partner_withdraw(),
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_withdraw_cancel")
    @catch_callback_errors
    async def partner_withdraw_cancel(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        # show cabinet again
        try:
            await partner_cabinet(cb, cb.bot)
        except Exception:
            try:
                await show_main_menu(cb.message, edit_message=True)
            except Exception:
                pass
        await fast_callback_answer(cb)

    @user_router.message(FranchiseStates.waiting_withdraw_amount)
    @registration_required
    async def partner_withdraw_amount(message: types.Message, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(message.from_user.id) != owner_id:
            await message.answer("Только владелец.")
            try:
                await state.clear()
            except Exception:
                pass
            return

        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer(f"Не понял сумму. Пришлите число, например <code>{get_franchise_min_withdraw():.0f}</code>.")
            return

        # Attach payout requisites snapshot to the withdraw request
        default_req = rw_repo.get_default_partner_requisite(bot_id, owner_id)
        if not default_req:
            await message.answer(
                "💳 Реквизиты не указаны. Сначала добавьте банк и номер карты/телефона, затем повторите вывод.",
                reply_markup=_kb_partner_requisites(rw_repo.list_partner_requisites(bot_id, owner_id) or []),
            )
            try:
                await state.clear()
            except Exception:
                pass
            return

        bank = str(default_req.get('bank') or '')
        rtype = str(default_req.get('requisite_type') or 'card')
        rvalue = str(default_req.get('requisite_value') or '')
        rid = int(default_req.get('id') or 0) or None

        ok, msg = rw_repo.create_withdraw_request(
            bot_id,
            owner_id,
            amount,
            bank=bank,
            requisite_type=rtype,
            requisite_value=rvalue,
            requisite_id=rid,
        )
        await message.answer(("✅ " if ok else "❌ ") + msg)

        # Notify admin from the ROOT bot token so the admin always receives it
        if ok:
            try:
                admin_id_raw = get_setting("admin_telegram_id")
                admin_id = int(str(admin_id_raw).strip()) if admin_id_raw else None
            except Exception:
                admin_id = None

            if admin_id:
                try:
                    root_token = (get_setting("telegram_bot_token") or "").strip()
                    if root_token:
                        tmp = Bot(token=root_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
                        try:
                            await tmp.send_message(
                                admin_id,
                                (
                                    "💸 <b>Заявка на вывод</b>\n"
                                    f"Бот: @{info.get('username') or 'без_username'} (bot_id={bot_id})\n"
                                    f"Владелец: <code>{owner_id}</code>\n"
                                    f"Сумма: <b>{amount:.2f} ₽</b>\n"
                                    f"Реквизиты: <b>{html_escape(str(default_req.get('bank') or ''))}</b> — <code>{html_escape(str(default_req.get('requisite_value') or ''))}</code>"
                                ),
                            )
                        finally:
                            try:
                                await tmp.close()
                            except Exception:
                                try:
                                    await tmp.session.close()
                                except Exception:
                                    pass
                except Exception:
                    pass

        try:
            await state.clear()
        except Exception:
            pass

        # Show cabinet again
        try:
            st = rw_repo.get_partner_cabinet(bot_id) or {}
            await message.answer(
                "📊 Обновляю кабинет...",
            )
            # reuse cabinet view
            fake_cb = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message)
            # Can't construct reliably; instead just show main menu which contains cabinet button
        except Exception:
            pass
        try:
            await show_main_menu(message)
        except Exception:
            pass

    return user_router

async def notify_admin_of_purchase(bot: Bot, metadata: dict):
    try:
        admin_id_raw = get_setting("admin_telegram_id")
        if not admin_id_raw:
            return
        admin_id = int(admin_id_raw)
        user_id = metadata.get('user_id')
        host_name = metadata.get('host_name')
        months = metadata.get('months')
        price = metadata.get('price')
        action = metadata.get('action')
        payment_method = metadata.get('payment_method') or 'Unknown'

        payment_method_map = {
            'Balance': 'Баланс',
            'ReferralBalance': 'Реферальный баланс',
            'Card': 'Карта',
            'Crypto': 'Крипто',
            'USDT': 'USDT',
            'TON': 'TON',
        }
        payment_method_display = payment_method_map.get(payment_method, payment_method)
        plan_id = metadata.get('plan_id')
        try:
            plan_id_int = int(plan_id) if plan_id not in (None, '', 'None') else 0
        except Exception:
            plan_id_int = 0
        plan = get_plan_by_id(plan_id_int) if plan_id_int else None
        plan_name = plan.get('plan_name', 'Unknown') if plan else 'Unknown'

        duration_label = None
        if plan:
            duration_label = _format_duration_label(plan.get("months"), plan.get("duration_days"))
        else:
            duration_label = _format_duration_label(months, metadata.get("duration_days"))

        text = (
            "📥 Новая оплата\n"
            f"👤 Пользователь: {user_id}\n"
            f"🗺️ Хост: {host_name}\n"
            f"📦 Тариф: {plan_name} ({duration_label})\n"
            f"💳 Метод: {payment_method_display}\n"
            f"💰 Сумма: {float(price):.2f} RUB\n"
            f"⚙️ Действие: {'Новый ключ' if action == 'new' else 'Подарок' if action == 'gift' else 'Продление'}"
        )

        promo_code = (metadata.get('promo_code') or '').strip() if isinstance(metadata, dict) else ''
        if promo_code:
            try:
                applied_amount = float(metadata.get('promo_applied_amount') or metadata.get('promo_discount') or 0)
            except Exception:
                applied_amount = 0.0
            text += f"\n🎟 Промокод: {promo_code} (-{applied_amount:.2f} RUB)"

            def _to_int(val):
                try:
                    if val in (None, '', 'None'):
                        return None
                    return int(val)
                except Exception:
                    return None

            total_limit = _to_int(metadata.get('promo_usage_total_limit'))
            total_used = _to_int(metadata.get('promo_usage_total_used'))
            per_user_limit = _to_int(metadata.get('promo_usage_per_user_limit'))
            per_user_used = _to_int(metadata.get('promo_usage_per_user_used'))

            extra_lines = []
            if total_limit:
                extra_lines.append(f"Общий лимит: {total_used or 0}/{total_limit}")
            elif total_used is not None:
                extra_lines.append(f"Общий использований: {total_used}")

            if per_user_limit:
                extra_lines.append(f"Лимит на пользователя: {per_user_used or 0}/{per_user_limit}")

            status_parts = []
            if metadata.get('promo_disabled'):
                reason = (metadata.get('promo_disabled_reason') or '').strip()
                reason_map = {
                    'total_limit': 'исчерпан общий лимит',
                    'expired': 'истёк срок действия'
                }
                status_parts.append(f"Промокод отключён ({reason_map.get(reason, reason or 'причина неизвестна')})")
            else:
                if metadata.get('promo_user_limit_reached'):
                    status_parts.append('Достигнут лимит на пользователя')
                if metadata.get('promo_expired'):
                    status_parts.append('Срок действия истёк')
                availability_err = metadata.get('promo_availability_error')
                if availability_err:
                    status_parts.append(f"Статус доступности: {availability_err}")

            if metadata.get('promo_disable_failed'):
                status_parts.append('Не удалось отключить код (проверьте вручную)')
            if metadata.get('promo_redeem_failed'):
                status_parts.append('Redeem не выполнен — проверьте вручную')

            if extra_lines:
                text += "\n📊 " + " | ".join(extra_lines)
            if status_parts:
                text += "\n⚠️ " + " | ".join(status_parts)

        await bot.send_message(admin_id, text)
    except Exception as e:
        logger.warning(f"notify_admin_of_purchase failed: {e}")

async def process_successful_payment(bot: Bot, metadata: dict) -> bool:
    """Обработать успешную оплату и выдать услугу.

    Returns:
        True — услуга выдана (или платёж уже был обработан ранее).
        False — выдача не удалась; для Balance/ReferralBalance/внешних методов
        средства возвращены через ``refund_payment_once`` (идемпотентно).
    """
    candidate_email = None  # default for gift flow
    logger.info("💳 Обрабатываем успешный платеж")

    def _provider_ids_for_log(meta: dict) -> dict:
        """Извлекает ID транзакции/инвойса на стороне платёжного провайдера из исходных
        metadata, чтобы не потерять их при пересборке metadata для log_transaction."""
        out = {}
        if not isinstance(meta, dict):
            return out
        for k in ("platega_transaction_id", "cryptobot_invoice_id", "heleket_uuid", "yookassa_payment_id"):
            v = meta.get(k)
            if v:
                out[k] = v
        return out

    try:
        action = metadata.get('action')
        user_id = int(metadata.get('user_id'))
        price = float(metadata.get('price'))
        logger.info(f"📊 Детали платежа: действие={action}, пользователь={user_id}, сумма={price:.2f} RUB")
        

        def _to_int(val, default=0):
            try:
                if val in (None, '', 'None', 'null'):
                    return default
                return int(val)
            except (ValueError, TypeError):
                return default

        months = _to_int(metadata.get('months'), 0)
        key_id = _to_int(metadata.get('key_id'), 0)
        host_name = metadata.get('host_name', '')
        plan_id = _to_int(metadata.get('plan_id'), 0)
        duration_days_meta = _to_int(metadata.get('duration_days'), 0)
        customer_email = metadata.get('customer_email')
        payment_method = metadata.get('payment_method')

        payment_id = (metadata.get("payment_id") or metadata.get("transaction_id") or "").strip()
        if not payment_id:
            logger.error(f"process_successful_payment: missing payment_id in metadata; refusing to process: {metadata}")
            return False
        try:
            if not claim_processed_payment(payment_id):
                logger.info(f"process_successful_payment: duplicate payment ignored: {payment_id}")
                return True
        except Exception as e:
            logger.error(f"process_successful_payment: idempotency check failed for {payment_id}: {e}", exc_info=True)
            return False

        promo_code_early = ""
        try:
            promo_code_early = (metadata.get("promo_code") or "").strip()
        except Exception:
            promo_code_early = ""
        if promo_code_early:
            try:
                applied_early = float(metadata.get("promo_discount") or 0)
            except Exception:
                applied_early = 0.0
            promo_ok, promo_err = reserve_promo_code(
                promo_code_early,
                user_id,
                payment_id,
                applied_amount=applied_early,
                plan_id=metadata.get("plan_id") if isinstance(metadata, dict) else None,
            )
            if promo_err or not promo_ok:
                logger.warning(
                    "process_successful_payment: promo reserve failed code=%s payment_id=%s err=%s",
                    promo_code_early,
                    payment_id,
                    promo_err,
                )
                try:
                    unclaim_processed_payment(payment_id)
                except Exception:
                    pass
                return False

                # Franchise: accrue partner commission for payments made through a managed clone bot.
        try:
            factory_bot_id = int((metadata or {}).get("factory_bot_id") or 0)
        except Exception:
            factory_bot_id = 0
        if factory_bot_id <= 0:
            try:
                factory_bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
            except Exception:
                factory_bot_id = 0
        if factory_bot_id > 0:
            try:
                rw_repo.accrue_partner_commission(factory_bot_id, str(payment_id), int(user_id), float(price), payment_method, 35.0)
            except Exception:
                pass

        chat_id_to_delete = metadata.get('chat_id')
        message_id_to_delete = metadata.get('message_id')
        
    except (ValueError, TypeError) as e:
        logger.error(f"FATAL: Could not parse metadata. Error: {e}. Metadata: {metadata}")
        return False

    if chat_id_to_delete and message_id_to_delete:
        try:
            await bot.delete_message(chat_id=chat_id_to_delete, message_id=message_id_to_delete)
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete payment message: {e}")

    if action == "traffic_gb_topup":
        key_id_tg = _to_int(metadata.get('key_id'), 0)
        package_id_tg = _to_int(metadata.get('package_id'), 0)
        logger.info(f"📶 Обрабатываем докупку трафика: пользователь={user_id}, key_id={key_id_tg}, package_id={package_id_tg}")
        try:
            key_data = rw_repo.get_key_by_id(key_id_tg) if key_id_tg else None
            package = database.get_traffic_package_by_id(package_id_tg) if package_id_tg else None
            if not key_data or not package:
                logger.error(f"traffic_gb_topup: ключ или пакет не найден (key_id={key_id_tg}, package_id={package_id_tg})")
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="traffic_gb_topup",
                    reason=f"key_or_package_not_found(key_id={key_id_tg}, package_id={package_id_tg})",
                )
                return

            size_gb = float(package.get('size_gb') or 0)
            add_bytes = int(size_gb * 1024 * 1024 * 1024)

            host_name = key_data.get('host_name')
            user_uuid = key_data.get('remnawave_user_uuid')
            current_boost = int(key_data.get('traffic_boost_bytes') or 0)

            user_payload = None
            try:
                if user_uuid:
                    user_payload = await remnawave_api.get_user_by_uuid(user_uuid, host_name=host_name)
                if not user_payload:
                    email = key_data.get('key_email') or key_data.get('email')
                    if email:
                        user_payload = await remnawave_api.get_user_by_email(email, host_name=host_name)
                        if user_payload and not user_uuid:
                            user_uuid = user_payload.get('uuid')
            except Exception as e:
                logger.error(f"traffic_gb_topup: не удалось получить пользователя Remnawave: {e}", exc_info=True)

            current_limit = None
            if isinstance(user_payload, dict):
                current_limit = user_payload.get('trafficLimitBytes')
            if current_limit is None:
                current_limit = key_data.get('traffic_limit_bytes') or 0

            new_limit = int(current_limit or 0) + add_bytes
            new_boost = current_boost + add_bytes

            ok_remote = False
            if user_uuid:
                try:
                    ok_remote = await remnawave_api.update_user_traffic_limit(user_uuid, new_limit, host_name=host_name)
                except Exception as e:
                    logger.error(f"traffic_gb_topup: ошибка обновления лимита в Remnawave: {e}", exc_info=True)
                    ok_remote = False

            if not ok_remote:
                # Лимит на сервере не изменён — состояние консистентно, можно вернуть деньги
                # и позволить повторить попытку (в т.ч. ретраем вебхука).
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="traffic_gb_topup",
                    reason="remnawave_limit_update_failed" if user_uuid else "no_remote_user",
                )
                return

            # Лимит на сервере уже поднят: возврат средств здесь был бы неверным (услуга
            # оказана), поэтому локальную запись пишем с повторами, а при устойчивом сбое
            # поднимаем алерт админам вместо тихого расхождения БД и панели.
            local_write_error: Exception | None = None
            for attempt in range(3):
                try:
                    rw_repo.update_key(key_id_tg, traffic_limit_bytes=new_limit, traffic_boost_bytes=new_boost)
                    local_write_error = None
                    break
                except Exception as e:
                    local_write_error = e
                    logger.error(
                        f"traffic_gb_topup: не удалось обновить локальную запись ключа {key_id_tg} "
                        f"(попытка {attempt + 1}/3): {e}",
                        exc_info=True,
                    )
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
            if local_write_error is not None:
                await _notify_admins_topup_desync(
                    bot,
                    user_id=user_id,
                    action_label="traffic_gb_topup",
                    payment_id=payment_id,
                    detail=(
                        f"key_id={key_id_tg} лимит на сервере={new_limit} "
                        f"boost={new_boost} ошибка={local_write_error}"
                    ),
                )

            try:
                log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
                if not log_username:
                    user_info = get_user(user_id)
                    log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=str(uuid.uuid4()),
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price),
                    amount_currency=None,
                    currency_name=None,
                    payment_method=payment_method or 'Unknown',
                    metadata=json.dumps({"action": "traffic_gb_topup", "key_id": key_id_tg, "size_gb": size_gb, **_provider_ids_for_log(metadata)})
                )
            except Exception:
                pass

            try:
                update_user_stats(user_id, float(price), 0)
            except Exception:
                pass

            size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"
            try:
                await bot.send_message(
                    user_id,
                    f"✅ Оплата получена! К вашему тарифу добавлено {size_txt} ГБ трафика.\n"
                    f"Новый лимит трафика действует до ближайшего ежемесячного сброса, после чего вернётся к базовому значению тарифа."
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"traffic_gb_topup: непредвиденная ошибка обработки платежа: {e}", exc_info=True)
        return

    if action == "lte_gb_topup":
        key_id_lte = _to_int(metadata.get('key_id'), 0)
        package_id_lte = _to_int(metadata.get('package_id'), 0)
        logger.info(f"💰 Обрабатываем докупку LTE: пользователь={user_id}, key_id={key_id_lte}, package_id={package_id_lte}")
        try:
            key_data = rw_repo.get_key_by_id(key_id_lte) if key_id_lte else None
            package = database.get_traffic_package_by_id(package_id_lte) if package_id_lte else None
            if not key_data or not package:
                logger.error(f"lte_gb_topup: ключ или пакет не найден (key_id={key_id_lte}, package_id={package_id_lte})")
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="lte_gb_topup",
                    reason=f"key_or_package_not_found(key_id={key_id_lte}, package_id={package_id_lte})",
                )
                return

            size_gb = float(package.get('size_gb') or 0)
            add_bytes = int(size_gb * 1024 * 1024 * 1024)

            # Докупка строго аддитивна: +N ГБ к остатку. Инкремент атомарный (одна транзакция),
            # иначе две параллельные оплаты теряли одну из покупок (read-modify-write).
            # Точку отсчёта расхода (baseline) здесь НЕ сдвигаем: вместе с учётом буста в
            # энфорсинге это выдавало бы полный лимит тарифа заново за цену минимального пакета.
            # Буст начисляется КОНКРЕТНОМУ ключу, который выбрал пользователь: LTE-пул живёт
            # на ключе, и докупка на одном ключе не должна расходоваться на другом.
            new_boost = database.add_key_lte_boost_bytes(key_id_lte, add_bytes)
            if new_boost is None:
                # Ничего не начислено и на сервере ничего не менялось — состояние
                # консистентно, возвращаем деньги и снимаем idempotency-lock.
                logger.error(
                    f"lte_gb_topup: не удалось начислить LTE-буст ключу {key_id_lte} "
                    f"(user_id={user_id}, add_bytes={add_bytes})"
                )
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="lte_gb_topup",
                    reason="lte_boost_update_failed",
                )
                return

            # Возвращаем доступ на premium-нодах ТОЛЬКО оплаченному ключу: докупка на одном
            # ключе не должна включать premium-ноды на других ключах пользователя.
            try:
                host_name_uk = key_data.get('host_name')
                try:
                    lte_squad_uk = database.get_squad_by_class(host_name_uk, 'lte')
                except Exception:
                    lte_squad_uk = None
                is_premium_uk = database.get_host_class(host_name_uk) == 'premium'
                uuid_uk = key_data.get('remnawave_user_uuid')
                state_uk = key_data.get('remote_access_state')
                if (
                    uuid_uk
                    and (is_premium_uk or lte_squad_uk)
                    and state_uk in ('disabled_premium', 'disabled_premium_squad')
                ):
                    if state_uk == 'disabled_premium_squad' and lte_squad_uk:
                        ok = await remnawave_api.add_squad_to_user(
                            uuid_uk, lte_squad_uk['squad_uuid'], host_name=host_name_uk
                        )
                    else:
                        ok = await remnawave_api.enable_user(uuid_uk, host_name=host_name_uk)
                    if ok:
                        database.update_key_fields(key_id_lte, remote_access_state='enabled')
                    else:
                        logger.error(
                            f"lte_gb_topup: не удалось вернуть доступ ключу {key_id_lte} "
                            f"(host '{host_name_uk}', состояние {state_uk})"
                        )
            except Exception as e:
                logger.error(f"lte_gb_topup: ошибка восстановления доступа ключа {key_id_lte}: {e}", exc_info=True)

            try:
                log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
                if not log_username:
                    user_info = get_user(user_id)
                    log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=str(uuid.uuid4()),
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price),
                    amount_currency=None,
                    currency_name=None,
                    payment_method=payment_method or 'Unknown',
                    metadata=json.dumps({"action": "lte_gb_topup", "key_id": key_id_lte, "size_gb": size_gb, **_provider_ids_for_log(metadata)})
                )
            except Exception:
                pass

            try:
                update_user_stats(user_id, float(price), 0)
            except Exception:
                pass

            size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"
            lte_label_html = html_escape(database.get_lte_squad_display_label(key_data.get("host_name")))
            try:
                await bot.send_message(
                    user_id,
                    f"✅ Оплата получена! К вашему пулу {lte_label_html} (💰 premium-ноды) добавлено {size_txt} ГБ.\n"
                    f"Доступ на premium-нодах восстановлен."
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"lte_gb_topup: непредвиденная ошибка обработки платежа: {e}", exc_info=True)
        return

    if action == "main_traffic_reset":
        key_id_mr = _to_int(metadata.get('key_id'), 0)
        logger.info(f"♻️ Обрабатываем сброс основного пула: пользователь={user_id}, key_id={key_id_mr}")
        try:
            key_data = rw_repo.get_key_by_id(key_id_mr) if key_id_mr else None
            if not key_data:
                logger.error(f"main_traffic_reset: ключ не найден (key_id={key_id_mr})")
                await bot.send_message(user_id, "⚠️ Оплата получена, но не удалось найти ключ для сброса. Обратитесь в поддержку.")
                return

            reset_errors = 0
            try:
                user_keys = get_user_keys(user_id)
            except Exception:
                user_keys = [key_data]

            for uk in (user_keys or [key_data]):
                try:
                    uuid_uk = uk.get('remnawave_user_uuid')
                    host_name_uk = uk.get('host_name')
                    if not uuid_uk:
                        continue
                    ok = await remnawave_api.reset_user_traffic_on_host(uuid_uk, host_name=host_name_uk)
                    if not ok:
                        reset_errors += 1
                        continue
                    try:
                        await remnawave_api.enable_user(uuid_uk, host_name=host_name_uk)
                    except Exception:
                        pass
                    try:
                        database.update_key_fields(uk.get('key_id'), traffic_boost_bytes=0, remote_access_state='enabled')
                    except Exception:
                        pass
                except Exception as e:
                    reset_errors += 1
                    logger.error(f"main_traffic_reset: ошибка сброса ключа {uk.get('key_id')}: {e}", exc_info=True)

            try:
                log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
                if not log_username:
                    user_info = get_user(user_id)
                    log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=str(uuid.uuid4()),
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price),
                    amount_currency=None,
                    currency_name=None,
                    payment_method=payment_method or 'Unknown',
                    metadata=json.dumps({"action": "main_traffic_reset", "key_id": key_id_mr, **_provider_ids_for_log(metadata)})
                )
            except Exception:
                pass

            try:
                update_user_stats(user_id, float(price), 0)
            except Exception:
                pass

            if reset_errors == 0:
                try:
                    await bot.send_message(user_id, "✅ Оплата получена! Основной пул трафика сброшен, доступ восстановлен на всех нодах.")
                except Exception:
                    pass
            else:
                try:
                    await bot.send_message(user_id, "⚠️ Оплата получена, но часть узлов не удалось сбросить. Обратитесь в поддержку, если доступ не восстановился.")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"main_traffic_reset: непредвиденная ошибка обработки платежа: {e}", exc_info=True)
        return

    if action == "top_up":
        logger.info(f"💰 Обрабатываем пополнение баланса для пользователя {user_id}: {float(price):.2f} RUB")
        ok = False
        try:
            ok = add_to_balance(user_id, float(price))
            if ok:
                logger.info(f"✅ Баланс успешно обновлен для пользователя {user_id}: +{float(price):.2f} RUB")
            else:
                logger.error(f"❌ Не удалось обновить баланс для пользователя {user_id}")
        except Exception as e:
            logger.error(f"💥 Ошибка при пополнении баланса для пользователя {user_id}: {e}", exc_info=True)
            ok = False
        
        # Обновляем total_spent при пополнении баланса (учитываем как инвестицию в сервис)
        try:
            update_user_stats(user_id, float(price), 0)  # Добавляем потраченные деньги, 0 месяцев
            logger.info(f"📊 Обновлены статистика пользователя {user_id}: +{float(price):.2f} RUB в total_spent")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить статистику пользователя {user_id}: {e}")

        try:

            log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
            if not log_username:
                user_info = get_user(user_id)
                log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
            logged_ok = log_transaction(
                username=log_username,
                transaction_id=None,
                payment_id=str(uuid.uuid4()),
                user_id=user_id,
                status='paid',
                amount_rub=float(price),
                amount_currency=None,
                currency_name=None,
                payment_method=payment_method or 'Unknown',
                metadata=json.dumps({"action": "top_up", **_provider_ids_for_log(metadata)})
            )
            if logged_ok:
                logger.info(
                    f"🧾 Транзакция пополнения баланса записана в 'transactions': user={user_id}, "
                    f"amount={float(price):.2f} RUB, payment_method={payment_method or 'Unknown'}"
                )
            else:
                logger.error(
                    f"💥 Не удалось записать транзакцию пополнения баланса в 'transactions' для user={user_id}, "
                    f"amount={float(price):.2f} RUB, payment_method={payment_method or 'Unknown'}. "
                    f"Это пополнение НЕ попадёт в доходы/аналитику! Подробности см. выше в логе "
                    f"('Failed to log transaction for user...')."
                )
        except Exception as e:
            logger.error(
                f"💥 Непредвиденная ошибка при записи транзакции пополнения баланса для user={user_id}, "
                f"amount={float(price):.2f} RUB: {e}. Это пополнение НЕ попадёт в доходы/аналитику!",
                exc_info=True,
            )



        try:
            pm_for_ref = (payment_method or '').strip().lower()
            if pm_for_ref in ('balance', 'referralbalance'):
                logger.info(f"Referral(top_up): skip accrual for user {user_id} because top-up was made from internal balance.")
            else:
                user_data = get_user(user_id) or {}
                referrer_id = user_data.get('referred_by')
                if referrer_id:
                    try:
                        referrer_id = int(referrer_id)
                    except Exception:
                        logger.warning(f"Referral(top_up): invalid referrer_id={referrer_id} for user {user_id}")
                        referrer_id = None
                if referrer_id:
                    try:
                        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
                    except Exception:
                        reward_type = "percent_purchase"
                    reward = Decimal("0")
                    if reward_type == "fixed_start_referrer":
                        reward = Decimal("0")
                    elif reward_type == "fixed_purchase":
                        try:
                            amount_raw = get_setting("fixed_referral_bonus_amount") or "50"
                            reward = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
                        except Exception:
                            reward = Decimal("50.00")
                    else:

                        try:
                            percentage = Decimal(get_setting("referral_percentage") or "0")
                        except Exception:
                            percentage = Decimal("0")
                        reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
                    logger.info(f"Referral(top_up): user={user_id}, referrer={referrer_id}, type={reward_type}, reward={float(reward):.2f}")
                    if float(reward) > 0:
                        try:
                            ok_ref = add_to_referral_balance(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Referral(top_up): add_to_referral_balance failed for referrer {referrer_id}: {e}")
                            ok_ref = False
                        try:
                            add_to_referral_balance_all(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Referral(top_up): failed to increment referral_balance_all for {referrer_id}: {e}")
                        referrer_username = user_data.get('username', 'пользователь')
                        if ok_ref:
                            try:
                                await bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        "💰 Вам начислено реферальное вознаграждение за пополнение баланса!\n"
                                        f"Пользователь: {referrer_username} (ID: {user_id})\n"
                                        f"Сумма: {float(reward):.2f} RUB"
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"Referral(top_up): could not send reward notification to {referrer_id}: {e}")
        except Exception as e:
            logger.warning(f"Referral(top_up): unexpected error while processing reward for user {user_id}: {e}")


        try:
            current_balance = 0.0
            try:
                current_balance = float(get_balance(user_id))
            except Exception:
                pass
            try:
                gifts_count = len(rw_repo.get_user_inactive_gifts(user_id) or [])
            except Exception:
                gifts_count = 0
            if ok:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ Оплата получена!\n"
                        f"💼 Баланс пополнен на {float(price):.2f} RUB.\n"
                        f"Текущий баланс: {current_balance:.2f} RUB."
                    ),
                    reply_markup=keyboards.create_profile_keyboard(gifts_count=gifts_count)
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "⚠️ Оплата получена, но не удалось обновить баланс. "
                        "Обратитесь в поддержку."
                    ),
                    reply_markup=keyboards.create_support_keyboard()
                )
        except Exception as e:
            logger.error(f"Failed to send top-up notification to user {user_id}: {e}")
        

        try:
            admins = [u for u in (get_all_users() or []) if is_admin(u.get('telegram_id') or 0)]
            for a in admins:
                admin_id = a.get('telegram_id')
                if admin_id:
                    await bot.send_message(admin_id, f"📥 Пополнение: пользователь {user_id}, сумма {float(price):.2f} RUB")
        except Exception:
            pass
        return

    processing_message = await bot.send_message(
        chat_id=user_id,
        text=f"✅ Оплата получена! Обрабатываю ваш запрос на сервере \"{host_name}\"..."
    )
    key_issued = False
    try:
        email = ""

        price = float(metadata.get('price'))
        result = None

        if action == "new":
            try:
                candidate_email = rw_repo.generate_key_email_for_user(user_id)
            except Exception:
                candidate_email = f"{user_id}-{int(time.time())}@bot.local"
        elif action == "gift":
            # Генерируем временный email для подарка (он будет использован, пока подарок не активирован)
            # uuid уже импортирован на уровне модуля (см. верх файла) — НЕ импортируем повторно здесь:
            # локальный `import uuid` делает имя `uuid` локальным для ВСЕЙ функции
            # process_successful_payment, из-за чего более ранние ветки (top_up и т.д.)
            # падали с UnboundLocalError на uuid.uuid4().
            gift_code = str(uuid.uuid4())[:12]
            candidate_email = f"gift-{gift_code}@bot.local"
        else:

            existing_key = rw_repo.get_key_by_id(key_id)
            if not existing_key or not existing_key.get('key_email'):
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=key_id),
                    exc=RuntimeError("key not found for extend"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось найти ключ для продления.",
                )
                return False
            candidate_email = existing_key['key_email']

        # plan-based duration & limits
        plan = get_plan_by_id(plan_id) if plan_id else None
        plan_months = months
        plan_days = duration_days_meta
        traffic_limit_bytes = None
        traffic_limit_strategy = None
        hwid_device_limit = None
        if plan:
            try:
                plan_months = int(plan.get('months') or 0)
            except Exception:
                plan_months = months
            try:
                plan_days = int(plan.get('duration_days') or 0)
            except Exception:
                plan_days = duration_days_meta
            traffic_limit_bytes = plan.get('traffic_limit_bytes')
            traffic_limit_strategy = plan.get('traffic_limit_strategy')
            hwid_device_limit = plan.get('hwid_device_limit')

            # Ensure numeric type for Remnawave (SQLite may store numbers as TEXT)
            try:
                if hwid_device_limit is not None:
                    hwid_device_limit = int(hwid_device_limit)
            except Exception:
                hwid_device_limit = None

            # In admin UI, 0 values are stored as NULL. For Remnawave we must send 0 to explicitly remove an existing cap.
            # Traffic: 0 means unlimited.
            if traffic_limit_bytes is None:
                traffic_limit_bytes = 0
            # Devices: 0 means unlimited.
            if hwid_device_limit is None:
                hwid_device_limit = 0

        # normalize limits (traffic_limit_bytes=0 means "no limit" and must be sent to Remnawave to clear an existing cap)
        try:
            if traffic_limit_bytes is not None and int(traffic_limit_bytes) < 0:
                traffic_limit_bytes = 0
        except Exception:
            pass
        try:
            if hwid_device_limit is not None and int(hwid_device_limit) < 0:
                hwid_device_limit = 0
        except Exception:
            pass

        # Remnawave MONTH_ROLLING — только при лимите ОСНОВНОГО пула. LTE-лимит
        # крутит бот сам; для безлимитного основного явно шлём NO_RESET, чтобы
        # не унаследовать дефолт сквада и не оставить None (панель подставила бы
        # squad.default_traffic_strategy).
        traffic_limit_strategy = database.remnawave_traffic_limit_strategy_for_plan(plan)

        days_to_add = _compute_days_to_add(plan_months, plan_days)
        if days_to_add <= 0:
            days_to_add = _compute_days_to_add(months, duration_days_meta)
        if days_to_add <= 0:
            days_to_add = int(months * 30) if months else 30

        # Store tariff origin in key.description so the subscription page shows correct "🕒 Тариф".
        try:
            plan_id_int = int(plan_id) if plan_id not in (None, '', 'None') else None
        except Exception:
            plan_id_int = None
        plan_name_meta = plan.get('plan_name') if isinstance(plan, dict) else None
        origin_desc = _build_key_origin_meta(
            source="extend" if action == "extend" else "purchase",
            plan_id=plan_id_int,
            plan_name=plan_name_meta,
            months=int(plan_months or 0),
            duration_days=int(plan_days or 0),
            is_trial=False,
        )
        origin_tag = "paid"

        # For renewals: extend from current expiry (if it's in the future) so we don't lose remaining days.
        expiry_timestamp_ms = None
        if action == "extend" and key_id:
            try:
                exp_str = None
                try:
                    existing_key = rw_repo.get_key_by_id(key_id) or {}
                    exp_str = existing_key.get('expire_at') or existing_key.get('expiry_date')
                except Exception:
                    exp_str = None

                exp_ms = None
                if exp_str:
                    exp_norm = str(exp_str).replace('Z', '+00:00').replace(' ', 'T').replace('/', '-')
                    try:
                        exp_dt = datetime.fromisoformat(exp_norm)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                        exp_ms = int(exp_dt.timestamp() * 1000)
                    except Exception:
                        exp_ms = None

                now_ms = int(time.time() * 1000)
                base_ms = max(exp_ms or 0, now_ms)
                expiry_timestamp_ms = base_ms + int(days_to_add) * 86400000
            except Exception:
                expiry_timestamp_ms = None

        try:
            result = await remnawave_api.create_or_update_key_on_host(
                host_name=host_name,
                email=candidate_email,
                days_to_add=int(days_to_add),
                expiry_timestamp_ms=expiry_timestamp_ms,
                traffic_limit_bytes=traffic_limit_bytes,
                traffic_limit_strategy=traffic_limit_strategy,
                hwid_device_limit=hwid_device_limit,
                plan_id=plan_id_int,
                raise_on_error=True,
            )
        except Exception as exc:
            action_label = _format_key_action_label(action, price=price, key_id=key_id)
            await _abort_key_fulfillment(
                bot,
                payment_id=payment_id,
                user_id=user_id,
                price=price,
                payment_method=payment_method,
                action_label=action_label,
                exc=exc,
                factory_bot_id=factory_bot_id,
                processing_message=processing_message,
            )
            return False
        if action != "gift" and not result:
            action_label = _format_key_action_label(action, price=price, key_id=key_id)
            await _abort_key_fulfillment(
                bot,
                payment_id=payment_id,
                user_id=user_id,
                price=price,
                payment_method=payment_method,
                action_label=action_label,
                exc=RuntimeError("key creation returned empty response"),
                factory_bot_id=factory_bot_id,
                processing_message=processing_message,
            )
            return False

        if action == "new":
            key_id = rw_repo.record_key_from_payload(
                user_id=user_id,
                payload=result,
                host_name=host_name,
                tag=origin_tag,
                description=origin_desc,
            )
            if not key_id:
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=0),
                    exc=RuntimeError("failed to persist key after Remnawave create"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось сохранить ключ. Попробуйте позже.",
                )
                return False
            try:
                database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
            except Exception:
                logger.warning(f"Не удалось установить дату сброса трафика для нового ключа {key_id}", exc_info=True)
            key_issued = True
        
        elif action == "gift":
            # Создаём запись о неактивированном подарке
            # uuid уже импортирован на уровне модуля — см. комментарий выше по функции.
            gift_code_unique = str(uuid.uuid4())[:16]
            
            # Использовуем candidate_email для получения key_id (ключ был создан на хосте)
            if result:
                try:
                    # Сохраняем ключ в БД с информацией о подарке
                    key_id = rw_repo.record_key_from_payload(
                        user_id=user_id,
                        payload=result,
                        host_name=host_name,
                        tag="user_gift",  # Специальный тег для подарков
                        description=origin_desc,
                    )
                    
                    if  key_id:
                        # Создаём запись в user_gifts
                        gift_result = rw_repo.create_user_gift(
                            from_user_id=user_id,
                            host_name=host_name,
                            plan_id=plan_id,
                            gift_code=gift_code_unique,
                        )
                        try:
                            database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
                        except Exception:
                            logger.warning(f"Не удалось установить дату сброса трафика для подарочного ключа {key_id}", exc_info=True)
                        
                        if gift_result:
                            # Обновляем связь между подарком и ключом
                            rw_repo.link_key_to_gift(gift_result['gift_id'], key_id)
                            
                            # Формируем ссылку для активации подарка
                            domain = (get_setting("domain") or "").strip()
                            if domain:
                                gift_link = f"{domain.rstrip('/')}/start?start=gift_{gift_code_unique}"
                            else:
                                gift_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=gift_{gift_code_unique}" if TELEGRAM_BOT_USERNAME else None
                            
                            # Отправляем информацию пользователю
                            gift_message = (
                                "🎁 <b>Подарок успешно куплен!</b>\n\n"
                                f"Тип: Подарок на {days_to_add} дней\n"
                                f"Сервер: {host_name}\n"
                                f"Цена: {price:.2f} RUB\n\n"
                                "<b>Вы можете:</b>\n"
                                "1️⃣ Использовать подарок сами (подарочный ключ будет добавлен в ваш профиль)\n"
                                f"2️⃣ Поделиться ссылкой: <code>{gift_link}</code>\n\n"
                                "Ссылка активируется один раз - первый переходящий по ней получит ключ.\n"
                                "Пока подарок не активирован, вы можете его использовать или видеть в разделе 'Неактивные подарки'."
                            )
                            
                            # Формируем клавиатуру с кнопкой поделиться
                            share_keyboard_builder = InlineKeyboardBuilder()
                            if gift_link:
                                share_text = _gift_share_text()
                                share_url = _telegram_share_url(gift_link, share_text)
                                share_keyboard_builder.button(text="📤 Поделиться подарком", url=share_url)
                            share_keyboard_builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
                            share_keyboard_builder.adjust(1)
                            
                            await processing_message.edit_text(gift_message, reply_markup=share_keyboard_builder.as_markup())
                            key_issued = True
                        else:
                            await _abort_key_fulfillment(
                                bot,
                                payment_id=payment_id,
                                user_id=user_id,
                                price=price,
                                payment_method=payment_method,
                                action_label=_format_key_action_label(action, price=price, key_id=key_id),
                                exc=RuntimeError("failed to create gift record"),
                                factory_bot_id=factory_bot_id,
                                processing_message=processing_message,
                                fail_text="❌ Не удалось создать запись о подарке.",
                            )
                            return False
                    else:
                        await _abort_key_fulfillment(
                            bot,
                            payment_id=payment_id,
                            user_id=user_id,
                            price=price,
                            payment_method=payment_method,
                            action_label=_format_key_action_label(action, price=price, key_id=0),
                            exc=RuntimeError("failed to persist gift key"),
                            factory_bot_id=factory_bot_id,
                            processing_message=processing_message,
                            fail_text="❌ Не удалось сохранить ключ подарка.",
                        )
                        return False
                        
                except Exception as e:
                    logger.error(f"Gift creation error: {e}", exc_info=True)
                    await _abort_key_fulfillment(
                        bot,
                        payment_id=payment_id,
                        user_id=user_id,
                        price=price,
                        payment_method=payment_method,
                        action_label=_format_key_action_label(action, price=price, key_id=0),
                        exc=e,
                        factory_bot_id=factory_bot_id,
                        processing_message=processing_message,
                        fail_text="❌ Ошибка при создании подарка.",
                    )
                    return False
            else:
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=0),
                    exc=RuntimeError("gift key creation returned empty response"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось создать ключ подарка.",
                )
                return False

        elif action == "extend":
            if not rw_repo.update_key(
                key_id,
                remnawave_user_uuid=result['client_uuid'],
                expire_at_ms=result['expiry_timestamp_ms'],
                traffic_limit_bytes=result.get('traffic_limit_bytes'),
                traffic_limit_strategy=result.get('traffic_limit_strategy'),
                tag=origin_tag,
                description=origin_desc,
            ):
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=key_id),
                    exc=RuntimeError("failed to update key after Remnawave extend"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось обновить информацию о ключе. Попробуйте позже.",
                )
                return False
            try:
                # Продление покупает срок, а не сбрасывает трафик: rolling-окно
                # остаётся от дня покупки. Если даты ещё не было (старые ключи) —
                # выравниваем по created_at. Безлимитный основной + LTE-лимит
                # дату сохраняет; полностью безлимитный — очищает.
                database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=False)
            except Exception:
                logger.warning(f"Не удалось обновить дату сброса трафика при продлении ключа {key_id}", exc_info=True)
            key_issued = True


        try:
            pm_for_ref = (payment_method or '').strip().lower()
            if pm_for_ref in ('balance', 'referralbalance'):
                logger.info(f"Referral: skip accrual for user {user_id} because payment was made from internal balance.")
            else:
                user_data = get_user(user_id) or {}
                referrer_id = user_data.get('referred_by')
                if referrer_id:
                    try:
                        referrer_id = int(referrer_id)
                    except Exception:
                        logger.warning(f"Referral: invalid referrer_id={referrer_id} for user {user_id}")
                        referrer_id = None
                if referrer_id:

                    try:
                        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
                    except Exception:
                        reward_type = "percent_purchase"
                    reward = Decimal("0")
                    if reward_type == "fixed_start_referrer":
                        reward = Decimal("0")
                    elif reward_type == "fixed_purchase":
                        try:
                            amount_raw = get_setting("fixed_referral_bonus_amount") or "50"
                            reward = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
                        except Exception:
                            reward = Decimal("50.00")
                    else:

                        try:
                            percentage = Decimal(get_setting("referral_percentage") or "0")
                        except Exception:
                            percentage = Decimal("0")
                        reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
                    logger.info(f"Referral: user={user_id}, referrer={referrer_id}, type={reward_type}, reward={float(reward):.2f}")
                    if float(reward) > 0:
                        try:
                            ok = add_to_referral_balance(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Referral: add_to_referral_balance failed for referrer {referrer_id}: {e}")
                            ok = False
                        try:
                            add_to_referral_balance_all(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Failed to increment referral_balance_all for {referrer_id}: {e}")
                        referrer_username = user_data.get('username', 'пользователь')
                        if ok:
                            try:
                                await bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        "💰 Вам начислено реферальное вознаграждение!\n"
                                        f"Пользователь: {referrer_username} (ID: {user_id})\n"
                                        f"Сумма: {float(reward):.2f} RUB"
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"Could not send referral reward notification to {referrer_id}: {e}")
        except Exception as e:
            logger.warning(f"Referral: unexpected error while processing reward for user {user_id}: {e}")


        pm = (payment_method or '').strip().lower()
        spent_for_stats = 0.0 if pm in ('balance', 'referralbalance') else price
        # статистика в месяцах: для тарифов в днях округляем вверх до месяцев
        months_for_stats = months
        try:
            if months_for_stats <= 0:
                eff_days = _compute_days_to_add(plan_months if 'plan_months' in locals() else months, plan_days if 'plan_days' in locals() else duration_days_meta)
                months_for_stats = int(math.ceil(eff_days / 30)) if eff_days > 0 else 0
        except Exception:
            months_for_stats = months
        update_user_stats(user_id, spent_for_stats, months_for_stats)
        
        user_info = get_user(user_id)

        log_username = user_info.get('username', 'N/A') if user_info else 'N/A'
        log_status = 'paid'
        log_amount_rub = float(price)
        log_method = metadata.get('payment_method', 'Unknown')
        
        log_metadata = json.dumps({
            "action": action,
            "key_id": key_id,
            "plan_id": metadata.get('plan_id'),
            "plan_name": get_plan_by_id(metadata.get('plan_id')).get('plan_name', 'Unknown') if get_plan_by_id(metadata.get('plan_id')) else 'Unknown',
            "host_name": metadata.get('host_name'),
            "customer_email": metadata.get('customer_email'),
            **_provider_ids_for_log(metadata),
        })


        payment_id_for_log = metadata.get('payment_id') or str(uuid.uuid4())

        log_transaction(
            username=log_username,
            transaction_id=None,
            payment_id=payment_id_for_log,
            user_id=user_id,
            status=log_status,
            amount_rub=log_amount_rub,
            amount_currency=None,
            currency_name=None,
            payment_method=log_method,
            metadata=log_metadata
        )
        
        try:
            promo_code_val = (metadata.get('promo_code') or '').strip()
        except Exception:
            promo_code_val = ''
        if promo_code_val:
            try:
                applied_amount = float(metadata.get('promo_discount') or 0)
            except Exception:
                applied_amount = 0.0
            promo_info = None
            availability_error = None
            try:
                promo_info = redeem_promo_code(
                    promo_code_val,
                    user_id,
                    applied_amount=applied_amount,
                    order_id=payment_id_for_log
                )
            except Exception as e:
                logger.warning(f"Promo: redeem failed for code {promo_code_val}: {e}")
            should_disable = False
            disable_reason = None
            if promo_info:
                try:
                    limit_user = promo_info.get('usage_limit_per_user') or 0
                    user_used = promo_info.get('user_used_count') or 0
                    metadata['promo_usage_per_user_limit'] = limit_user
                    metadata['promo_usage_per_user_used'] = user_used
                    if limit_user and user_used >= limit_user:
                        metadata['promo_user_limit_reached'] = True
                except Exception:
                    pass
                try:
                    limit_total = promo_info.get('usage_limit_total') or 0
                    used_total = promo_info.get('used_total') or 0
                    metadata['promo_usage_total_limit'] = limit_total
                    metadata['promo_usage_total_used'] = used_total
                    if limit_total and used_total >= limit_total:
                        should_disable = True
                        disable_reason = 'total_limit'
                except Exception:
                    pass
            else:
                metadata['promo_redeem_failed'] = True
                try:
                    _, availability_error = check_promo_code_available(
                        promo_code_val,
                        user_id,
                        plan_id=(metadata.get("plan_id") if isinstance(metadata, dict) else None),
                    )
                except Exception as e:
                    logger.warning(f"Promo: availability check failed for code {promo_code_val}: {e}")
                    availability_error = None
                if availability_error:
                    metadata['promo_availability_error'] = availability_error
                if availability_error == 'user_limit_reached':
                    metadata['promo_user_limit_reached'] = True
                if availability_error == 'total_limit_reached':
                    should_disable = True
                    disable_reason = 'total_limit'
                if availability_error == 'expired':
                    should_disable = True
                    disable_reason = 'expired'
                    metadata['promo_expired'] = True
            if should_disable:
                try:
                    if update_promo_code_status(promo_code_val, is_active=False):
                        metadata['promo_disabled'] = True
                        metadata['promo_disabled_reason'] = disable_reason
                    else:
                        metadata['promo_disable_failed'] = True
                except Exception as e:
                    logger.warning(f"Promo: failed to deactivate code {promo_code_val}: {e}")
                    metadata['promo_disable_failed'] = True
            metadata['promo_applied_amount'] = applied_amount
        
        await processing_message.delete()
        
        connection_string = None
        new_expiry_date = None
        try:
            connection_string = result.get('connection_string') if isinstance(result, dict) else None
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000) if isinstance(result, dict) and 'expiry_timestamp_ms' in result else None
        except Exception:
            connection_string = None
            new_expiry_date = None
        
        all_user_keys = get_user_keys(user_id)
        key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))

        # Получаем информацию о подарке для этого ключа, если это подарок
        if action == 'gift':
            gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
        else:
            gift_id, gift_code = None, None
        domain = (get_setting("domain") or "").strip()

        final_text = get_purchase_success_text(
            action="extend" if action == "extend" else "new",
            key_number=key_number,
            expiry_date=new_expiry_date or datetime.now(),
            connection_string=connection_string or ""
        )
        
        # Для подарков добавляем ссылку активации выше ссылки подписки
        if gift_code:
            if domain:
                gift_activation_link = f"{domain.rstrip('/')}/start?start=gift_{gift_code}"
            else:
                gift_activation_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=gift_{gift_code}" if TELEGRAM_BOT_USERNAME else None
            
            if gift_activation_link:
                # Добавляем ссылку активации перед ссылкой подписки
                final_text = final_text.replace(
                    f"<code>{html_escape(connection_string or '')}</code>",
                    f"🎁 <b>Ссылка активации подарка:</b>\n<code>{gift_activation_link}</code>\n\n"
                    f"📱 <b>Ссылка подписки:</b>\n<code>{html_escape(connection_string or '')}</code>"
                )
        
        await bot.send_message(
            chat_id=user_id,
            text=final_text,
            reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, gift_code=gift_code, gift_id=gift_id)
        )

        try:
            await notify_admin_of_purchase(bot, metadata)
        except Exception as e:
            logger.warning(f"Failed to notify admin of purchase: {e}")

        return True
        
    except Exception as e:
        logger.error(f"Error processing payment for user {user_id} on host {host_name}: {e}", exc_info=True)
        if not key_issued:
            try:
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=key_id),
                    exc=e,
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message if 'processing_message' in locals() else None,
                    fail_text="❌ Ошибка при выдаче ключа.",
                )
            except Exception:
                try:
                    await processing_message.edit_text("❌ Ошибка при выдаче ключа.")
                except Exception:
                    try:
                        await bot.send_message(chat_id=user_id, text="❌ Ошибка при выдаче ключа.")
                    except Exception:
                        pass
            return False
        try:
            await processing_message.edit_text("❌ Ошибка при выдаче ключа.")
        except Exception:
            try:
                await bot.send_message(chat_id=user_id, text="❌ Ошибка при выдаче ключа.")
            except Exception:
                pass
        # Ключ уже выдан — считаем оплату успешной, несмотря на ошибку нотификации/пост-обработки.
        return True



# fallback for unknown callbacks
try:
    router.callback_query.register(handle_unknown_callback)
except Exception:
    pass
