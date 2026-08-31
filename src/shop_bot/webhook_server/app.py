import os
import re
import subprocess
import logging
import asyncio
import threading
import json
import sqlite3
import hashlib
import hmac
import bcrypt
import pyotp
import html as html_escape
import base64
import time
import uuid
from decimal import Decimal
from hmac import compare_digest
from datetime import datetime, timezone, timedelta
from functools import wraps
from math import ceil
from flask import Flask, request, render_template, redirect, url_for, flash, session, current_app, jsonify, send_file, Response, abort
from flask_wtf.csrf import CSRFProtect, generate_csrf
import secrets
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

from shop_bot.modules import remnawave_api
from shop_bot.modules import telegram_reachability
from shop_bot.modules.platega_fulfillment import (
    complete_pending_platega_payment,
    mark_pending_canceled,
    normalize_platega_status,
)
from shop_bot.bot import handlers
from shop_bot.bot import keyboards
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from shop_bot.support_bot_controller import SupportBotController
from shop_bot.data_manager import speedtest_runner
from shop_bot.data_manager import resource_monitor
from shop_bot.data_manager import backup_manager
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import (
    get_all_settings, update_setting, get_all_hosts, get_plans_for_host, get_all_plans,
    create_host, delete_host, create_plan, delete_plan, update_plan, set_plan_active, get_user_count,
    get_total_keys_count, get_total_spent_sum, get_daily_stats_for_charts,
    get_recent_transactions, get_paginated_transactions, get_all_users, get_user_keys,
    ban_user, unban_user, delete_user_keys, get_setting, find_and_complete_ton_transaction,
    find_and_complete_pending_transaction,
    cancel_pending_transaction,
    get_tickets_paginated, get_open_tickets_count, get_ticket, get_ticket_messages,
    add_support_message, set_ticket_status, delete_ticket,
    get_closed_tickets_count, get_all_tickets_count, update_host_subscription_url,
    update_host_url, update_host_name, update_host_ssh_settings, get_latest_speedtest, get_speedtests,
    get_all_keys, get_keys_for_user, delete_key_by_id, update_key_comment, get_keys_paginated,
    get_balance, adjust_user_balance, get_referrals_for_user,
    get_referral_balance, adjust_user_referral_balance,
    link_referrer_if_eligible, unlink_referral, unlink_all_referrals,

    get_users_paginated, get_keys_counts_for_users,

    get_all_ssh_targets, get_ssh_target, create_ssh_target, update_ssh_target_fields, delete_ssh_target,
    get_user,
    get_admin_stats,
)
from shop_bot.data_manager.database import (
    get_button_configs, get_button_configs_admin, create_button_config, update_button_config, 
    delete_button_config, reorder_button_configs
)
from shop_bot.data_manager.database import update_host_remnawave_settings, get_plan_by_id, SECRET_SETTING_KEYS
from shop_bot.data_manager.database import (
    add_host_squad,
    get_host_squads,
    set_host_squad_active,
    delete_host_squad,
    get_remnawave_squads,
    add_remnawave_squad,
    delete_remnawave_squad,
    seed_global_remnawave_from_hosts,
    apply_global_remnawave_to_hosts,
    set_host_squads_from_catalog,
    get_host_selected_squad_catalog_ids,
    get_host_squad_overlap,
    squad_display_label,
    get_lte_squad_display_label,
)
from shop_bot.data_manager.database import (
    create_traffic_package, get_traffic_packages_for_plan, get_traffic_package_by_id,
    update_traffic_package, delete_traffic_package,
)
from shop_bot.data_manager.database import (
    get_key_by_id, update_key_fields, set_key_traffic_boost,
    get_squad_by_class, get_host_class,
    get_key_lte_state, add_key_lte_boost_bytes,
    get_node_usage_for_key, resolve_key_period_start,
    should_account_lte_traffic,
    apply_key_monthly_reset_fields, remnawave_traffic_limit_strategy_for_plan,
    format_next_traffic_reset_display,
)
from shop_bot.data_manager.database import (
    encrypt_managed_bot_token,
    decrypt_managed_bot_token,
)
from shop_bot.data_manager.database import get_transactions_paginated
from shop_bot.data_manager.database import get_all_key_ids, extend_key, set_key_expiry
from shop_bot.data_manager.database import (
    get_sales_overview, get_revenue_series, get_plans_analytics,
    get_payment_methods_analytics, get_referrals_analytics, get_top_referrers,
    get_top_buyers, get_coupons_analytics, get_server_cost_entries,
    create_server_cost_entry, update_server_cost_entry, delete_server_cost_entry,
    get_economics_summary, get_revenue_forecast, get_utm_links, create_utm_link,
    get_utm_analytics, delete_utm_link,
    get_users_without_real_payment_with_keys, get_trial_key_stats,
    delete_user_completely,
)
from shop_bot.data_manager.database import (
    create_broadcast_campaign, get_broadcast_campaigns, get_broadcast_campaign,
    update_broadcast_campaign, toggle_broadcast_campaign, delete_broadcast_campaign,
    get_pending_broadcast_recipients, record_broadcast_sends, mark_broadcast_run,
    get_broadcast_stats,
)
from shop_bot.data_manager.database import (
    list_referral_payout_methods, list_referral_withdrawal_requests,
    get_referral_withdrawal_request, update_referral_withdrawal_request_status,
    get_referral_withdrawable_stats,
)
from shop_bot.core.module_loader import get_global_module_loader

_bot_controller = None
_support_bot_controller = SupportBotController()

def _parse_decimal_amount(value, *, log_prefix: str) -> Decimal | None:
    try:
        if value is None:
            raise ValueError("amount is None")
        if isinstance(value, str):
            cleaned = value.strip().replace(",", ".").replace(" ", "")
        else:
            cleaned = str(value)
        if not cleaned:
            raise ValueError("amount is empty")
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except Exception as e:
        logger.warning(f"{log_prefix}: amount parse error: value={value!r} error={e}")
        return None


def _setting_flag_enabled(raw) -> bool:
    return str(raw or "").strip().lower() in ("true", "1", "on", "yes", "y")


def _pending_method_allowed(pending_meta: dict | None, *allowed: str) -> bool:
    """True if pending metadata.payment_method matches one of the allowed provider names."""
    if not isinstance(pending_meta, dict):
        return False
    method = str(pending_meta.get("payment_method") or "").strip().lower()
    return method in {name.strip().lower() for name in allowed}


def _pending_expected_amount(pending_meta: dict | None) -> Decimal | None:
    if not isinstance(pending_meta, dict):
        return None
    raw = pending_meta.get("price")
    if raw is None:
        raw = pending_meta.get("amount_rub")
    return _parse_decimal_amount(raw, log_prefix="pending amount")


def _platega_amount_covers_order(got_amount: Decimal, expected_amount: Decimal) -> bool:
    """Platega callback amount is what the customer paid.

    The provider may add its own fee on top of the order we created
    (e.g. 107.00 charged vs 100.00 pending). Underpayment is still rejected.
    """
    return got_amount >= expected_amount


def _extract_platega_webhook_amount(payload: dict):
    """Platega callback: top-level `amount`, with paymentDetails.amount as fallback."""
    if not isinstance(payload, dict):
        return None
    if payload.get("amount") is not None:
        return payload.get("amount")
    details = payload.get("paymentDetails") or payload.get("payment_details") or {}
    if isinstance(details, dict) and details.get("amount") is not None:
        return details.get("amount")
    return None


def _dispatch_payment_processing(metadata: dict) -> None:
    """Fulfill paid orders even when the polling bot loop isn't running.

    If the main bot + EVENT_LOOP are available, schedule into that loop.
    Otherwise, run in a background thread using a temporary Bot instance.
    """
    payment_processor = handlers.process_successful_payment

    loop = None
    try:
        loop = _bot_controller.get_loop()
    except Exception:
        loop = None

    live_bot = None
    try:
        live_bot = _bot_controller.get_bot_instance() if _bot_controller else None
    except Exception:
        live_bot = None

    if live_bot and loop and getattr(loop, "is_running", lambda: False)():
        asyncio.run_coroutine_threadsafe(payment_processor(live_bot, metadata), loop)
        return

    token = (get_setting("telegram_bot_token") or "").strip()
    if not token:
        logger.error("Payment processing: telegram_bot_token is missing; cannot fulfill paid order")
        return

    def _worker():
        async def _run():
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                await payment_processor(bot, metadata)
            finally:
                try:
                    await bot.close()
                except Exception:
                    pass

        try:
            asyncio.run(_run())
        except Exception as e:
            logger.error(f"Payment processing: background fulfillment failed: {e}", exc_info=True)

    threading.Thread(target=_worker, name="shopbot-payment-fulfillment", daemon=True).start()


def _dispatch_bot_notification(user_id: int, text: str) -> None:
    """Отправляет произвольное текстовое уведомление пользователю бота из админ-панели
    (используется, например, при смене статуса заявки на вывод реферальных средств).
    Использует ту же схему диспетчеризации, что и обработка платежей: живой Bot-инстанс
    из работающего event loop, либо временный Bot в отдельном потоке."""
    loop = None
    try:
        loop = _bot_controller.get_loop()
    except Exception:
        loop = None

    live_bot = None
    try:
        live_bot = _bot_controller.get_bot_instance() if _bot_controller else None
    except Exception:
        live_bot = None

    async def _send(bot_instance):
        try:
            await bot_instance.send_message(int(user_id), text)
        except Exception as e:
            if not telegram_reachability.handle_send_exception(int(user_id), e):
                logger.warning(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

    if live_bot and loop and getattr(loop, "is_running", lambda: False)():
        asyncio.run_coroutine_threadsafe(_send(live_bot), loop)
        return

    token = (get_setting("telegram_bot_token") or "").strip()
    if not token:
        return

    def _worker():
        async def _run():
            bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            try:
                await _send(bot)
            finally:
                try:
                    await bot.close()
                except Exception:
                    pass
        try:
            asyncio.run(_run())
        except Exception as e:
            logger.error(f"Notification dispatch failed: {e}", exc_info=True)

    threading.Thread(target=_worker, name="shopbot-user-notification", daemon=True).start()



ALL_SETTINGS_KEYS = [
    "panel_login",
    "panel_password",
    "panel_totp_enabled",
    "panel_totp_secret",
    "about_text",
    "terms_url",
    "privacy_url",
    "support_user",
    "support_text",
    "channel_url",
    "channel_link",
    "chat_link",
    "telegram_bot_token",
    "telegram_bot_username",
    "admin_telegram_id",
    "auto_start_main_bot",
    "auto_start_support_bot",
    "yookassa_shop_id",
    "yookassa_secret_key",
    "sbp_enabled",
    "receipt_email",
    "cryptobot_token",
    "heleket_merchant_id",
    "heleket_api_key",
    "platega_base_url",
    "platega_merchant_id",
    "platega_secret",
    "platega_active_methods",
    "rollypay_api_key",
    "rollypay_terminal_id",
    "rollypay_signing_secret",
    "rollypay_payment_method",
    "domain",
    "referral_percentage",
    "referral_discount",
    "ton_wallet_address",
    "tonapi_key",
    "force_subscription",
    "trial_enabled",
    "trial_duration_days",
    "trial_traffic_limit_gb",
    "trial_device_limit",
    "trial_default_host",
    "enable_referrals",
    "minimum_withdrawal",
    "enable_fixed_referral_bonus",
    "fixed_referral_bonus_amount",
    "referral_reward_type",
    "referral_on_start_referrer_amount",
    "support_forum_chat_id",
    "support_bot_token",
    "support_bot_username",
    "panel_brand_title",
    "main_menu_text",
    "main_menu_promo_text",
    "howto_intro_text",
    "howto_android_text",
    "howto_ios_text",
    "howto_windows_text",
    "howto_linux_text",
    "btn_trial_text",
    "btn_profile_text",
    "btn_my_keys_text",
    "btn_buy_key_text",
    "btn_topup_text",
    "btn_referral_text",
    "referral_share_text",
    "gift_share_text",
    "btn_support_text",
    "btn_about_text",
    "btn_speed_text",
    "btn_howto_text",
    "btn_admin_text",
    "btn_back_to_menu_text",
    "backup_interval_days",
    "monitoring_enabled",
    "monitoring_interval_sec",
    "monitoring_cpu_threshold",
    "monitoring_mem_threshold",
    "monitoring_disk_threshold",
    "monitoring_alert_cooldown_sec",
    "yoomoney_enabled",
    "yoomoney_wallet",
    "yoomoney_secret",

    "payment_label_balance",
    "payment_label_yookassa_card",
    "payment_label_yookassa_sbp",
    "payment_label_platega",
    "payment_label_rollypay",
    "payment_label_cryptobot",
    "payment_label_heleket",
    "payment_label_tonconnect",
    "payment_label_stars",
    "payment_label_yoomoney",

    "stars_per_rub",
    "stars_enabled",
    "yoomoney_api_token",
    "yoomoney_client_id",
    "yoomoney_client_secret",
    "yoomoney_redirect_uri",
    "key_info_show_connect_device",
    "key_info_show_howto",
    "payment_email_prompt_enabled",
    "enable_referral_days_bonus",
    "franchise_enabled",
    "franchise_menu_button_visible",
    "franchise_commission_percent",
    "franchise_min_withdraw_rub",

    "auto_renew_globally_enabled",
    "auto_renew_hours_before",

    "webapp_enabled",
    "webapp_domain",
    "webapp_port",
    "webapp_ssl_email",
    "webapp_title",
    "webapp_logo",
    "webapp_icon",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "smtp_from_email",
    "smtp_use_tls",
    "remnawave_base_url",
    "remnawave_api_token",
    "remnawave_subscription_url",
]


# === Franchise settings management (module level) ===

def franchise_settings() -> bool:
    """
    Возвращает текущее состояние франшизы.
    True = включена, False = выключена
    """
    try:
        val = (get_setting('franchise_enabled') or 'false').strip().lower()
        return val in ('1', 'true', 'yes', 'on')
    except Exception:
        return False


def franchise_menu_button_visible() -> bool:
    """Видимость пункта «Франшиза» в меню веб-админки (независимо от franchise_enabled)."""
    try:
        val = (get_setting('franchise_menu_button_visible') or 'false').strip().lower()
        return val in ('1', 'true', 'yes', 'on')
    except Exception:
        return False


def _run_on_root_bot_loop(action, *, wait: bool = True, timeout: float = 5.0) -> None:
    """Запустить coroutine action(service) на loop root-бота из Flask-потока.

    Не падает, если сервис/loop ещё не созданы. Не блокирует HTTP дольше timeout.
    """
    try:
        from shop_bot.factory_bot.runtime import get_service
        svc = get_service()
        if svc is None:
            logger.warning("ManagedBotsService недоступен — изменение сохранено в БД и применится при запуске root-бота.")
            return
        loop = _bot_controller.get_loop() if _bot_controller else None
        if loop is None or not loop.is_running():
            logger.warning("Цикл root-бота недоступен — изменение франшизы применится при следующем запуске.")
            return
        coro = action(svc)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            running.create_task(coro)
            return
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        if not wait:
            return
        try:
            fut.result(timeout=timeout)
        except Exception as e:
            logger.warning(f"Не удалось выполнить действие клонов на loop root-бота: {e}")
    except Exception as e:
        logger.warning(f"Не удалось связать действие франшизы с ManagedBotsService: {e}")


def _apply_franchise_runtime(enabled: bool) -> None:
    """Включить/выключить все клоны на уже работающем event loop."""
    try:
        from shop_bot.factory_bot.middleware import invalidate_franchise_enabled_cache
        invalidate_franchise_enabled_cache()
    except Exception:
        pass
    if enabled:
        _run_on_root_bot_loop(lambda svc: svc.start_all())
    else:
        _run_on_root_bot_loop(lambda svc: svc.stop_all())


def toggle_franchise_settings() -> bool:
    """
    Переключает состояние франшизы (ВКЛ/ВЫКЛ).
    Возвращает новое состояние: True = включена, False = выключена
    Сразу запускает или останавливает клонов, если root-бот уже работает.
    """
    try:
        current = (get_setting('franchise_enabled') or 'false').strip().lower()
        current_enabled = current in ('1', 'true', 'yes', 'on')
        new_value = 'false' if current_enabled else 'true'
        rw_repo.update_setting('franchise_enabled', new_value)
        enabled = new_value == 'true'
        _apply_franchise_runtime(enabled)
        return enabled
    except Exception:
        return False

# === End Franchise settings ===


def create_webhook_app(bot_controller_instance):
    global _bot_controller
    _bot_controller = bot_controller_instance

    app_file_path = os.path.abspath(__file__)
    app_dir = os.path.dirname(app_file_path)
    template_dir = os.path.join(app_dir, 'templates')
    template_file = os.path.join(template_dir, 'login.html')

    logger.debug("--- ДИАГНОСТИЧЕСКАЯ ИНФОРМАЦИЯ ---")
    logger.debug(f"Текущая рабочая директория: {os.getcwd()}")
    logger.debug(f"Путь к исполняемому app.py: {app_file_path}")
    logger.debug(f"Директория app.py: {app_dir}")
    logger.debug(f"Ожидаемая директория шаблонов: {template_dir}")
    logger.debug(f"Ожидаемый путь к login.html: {template_file}")
    logger.debug(f"Директория шаблонов существует? -> {os.path.isdir(template_dir)}")
    logger.debug(f"Файл login.html существует? -> {os.path.isfile(template_file)}")
    logger.debug("--- КОНЕЦ ДИАГНОСТИКИ ---")
    
    flask_app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static'
    )

    module_loader = get_global_module_loader()
    module_loader.discover_modules()
    module_loader.set_flask_app(flask_app)
    

    flask_app.config['SECRET_KEY'] = os.getenv('SHOPBOT_SECRET_KEY') or secrets.token_hex(32)
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
    # Cap request body size (module ZIP uploads and form posts).
    flask_app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024  # 12 MiB

    flask_app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv("SHOPBOT_SESSION_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=os.getenv("SHOPBOT_SESSION_SECURE", "false").lower() in ("1","true","yes"),
    )
    flask_app.config["ENABLE_DEBUG_ENDPOINTS"] = os.getenv("SHOPBOT_ENABLE_DEBUG_ENDPOINTS", "false").lower() in ("1","true","yes")
    flask_app.config["DEBUG_IP_ALLOWLIST"] = [ip.strip() for ip in os.getenv("SHOPBOT_DEBUG_IP_ALLOWLIST", "127.0.0.1,::1").split(",") if ip.strip()]
    flask_app.config["TON_WEBHOOK_SECRET"] = os.getenv("SHOPBOT_TON_WEBHOOK_SECRET") or ""



    csrf = CSRFProtect()
    csrf.init_app(flask_app)


    def _handle_promo_after_payment(metadata: dict) -> None:
        try:
            promo_code = (metadata.get('promo_code') or '').strip()
        except Exception:
            promo_code = ''
        if not promo_code:
            return
        try:
            user_id = int(metadata.get('user_id') or 0)
        except Exception:
            user_id = 0
        try:
            applied_amount = float(metadata.get('promo_discount') or 0)
        except Exception:
            applied_amount = 0.0
        order_id = metadata.get('payment_id') or metadata.get('transaction_id') or None

        promo_info = None
        availability_error = None
        try:
            promo_info = rw_repo.redeem_promo_code(promo_code, user_id, applied_amount=applied_amount, order_id=order_id)
        except Exception as e:
            logger.warning(f"Промо: не удалось активировать код {promo_code}: {e}")

        if promo_info is None:
            try:
                _, availability_error = rw_repo.check_promo_code_available(
                    promo_code,
                    user_id,
                    plan_id=metadata.get("plan_id") if isinstance(metadata, dict) else None,
                )
            except Exception as e:
                logger.warning(f"Промо: не удалось повторно проверить доступность для {promo_code}: {e}")

        should_deactivate = False
        user_limit_reached = False
        if promo_info:
            try:
                limit_total = promo_info.get('usage_limit_total') or 0
                used_total = promo_info.get('used_total') or 0
                if limit_total and used_total >= limit_total:
                    should_deactivate = True
            except Exception:
                pass
            try:
                limit_user = promo_info.get('usage_limit_per_user') or 0
                user_used = promo_info.get('user_used_count') or 0
                if limit_user and user_used >= limit_user:
                    user_limit_reached = True
            except Exception:
                pass
        else:
            if availability_error == "total_limit_reached":
                should_deactivate = True
            if availability_error == "user_limit_reached":
                user_limit_reached = True

        deact_ok = False
        if should_deactivate:
            try:
                deact_ok = rw_repo.update_promo_code_status(promo_code, is_active=False)
            except Exception as e:
                logger.warning(f"Промо: не удалось деактивировать код {promo_code}: {e}")
                deact_ok = False


        try:
            bot = _bot_controller.get_bot_instance()
            loop = _bot_controller.get_loop()
            try:
                admin_ids = list(rw_repo.get_admin_ids() or [])
            except Exception:
                admin_ids = []
            if bot and loop and loop.is_running() and admin_ids:
                if should_deactivate:
                    status_msg = "Код отключён." if deact_ok else "Не удалось отключить код — проверьте панель."
                elif user_limit_reached:
                    status_msg = "Достигнут лимит на пользователя; код остаётся активным для остальных."
                elif availability_error:
                    status_msg = f"Статус: {availability_error}."
                else:
                    status_msg = "Лимит не достигнут, код остаётся активным."
                text = (
                    f"🎟 Промокод {promo_code} использован пользователем {user_id} на скидку {applied_amount:.2f} RUB. "
                    f"{status_msg}"
                )
                for aid in admin_ids:
                    try:
                        asyncio.run_coroutine_threadsafe(bot.send_message(int(aid), text), loop)
                    except Exception:
                        continue
        except Exception:
            pass

    @flask_app.context_processor
    def inject_current_year():
        """Inject common variables into all templates"""
        bot_status = _bot_controller.get_status()
        support_bot_status = _support_bot_controller.get_status()
        settings = get_all_settings()
        required_for_start = ['telegram_bot_token', 'telegram_bot_username', 'admin_telegram_id']
        required_support_for_start = ['support_bot_token', 'support_bot_username']
        all_settings_ok = all(settings.get(key) for key in required_for_start)
        try:
            admin_ids = rw_repo.get_admin_ids()
        except Exception:
            admin_ids = set()
        support_settings_ok = all(settings.get(key) for key in required_support_for_start) and bool(admin_ids)
        try:
            open_tickets_count = get_open_tickets_count()
            closed_tickets_count = get_closed_tickets_count()
            all_tickets_count = get_all_tickets_count()
        except Exception:
            open_tickets_count = 0
            closed_tickets_count = 0
            all_tickets_count = 0
        
        return {
            'current_year': datetime.utcnow().year,
            'csrf_token': generate_csrf,
            "bot_status": bot_status,
            "all_settings_ok": all_settings_ok,
            "support_bot_status": support_bot_status,
            "support_settings_ok": support_settings_ok,
            "open_tickets_count": open_tickets_count,
            "closed_tickets_count": closed_tickets_count,
            "all_tickets_count": all_tickets_count,
            "brand_title": settings.get('panel_brand_title') or 'Xatabchik',
            "panel_login": (settings.get('panel_login') or '').strip(),
            "franchise_enabled": franchise_settings(),
            "franchise_menu_button_visible": franchise_menu_button_visible(),
            "module_menu_items": module_loader.get_menu_items(),
        }

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login_page'))
            return f(*args, **kwargs)
        return decorated_function

    # In-memory brute-force protection for panel login (CWE-307).
    # 5 attempts / 5 minutes per client IP.
    _login_attempts = {}

    def _rate_limit_login(ip: str, limit: int = 5, window_sec: int = 300) -> bool:
        now = time.time()
        attempts = _login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < window_sec]
        if len(attempts) >= limit:
            _login_attempts[ip] = attempts
            return False
        attempts.append(now)
        _login_attempts[ip] = attempts
        return True

    _TRUSTED_PROXY_REMOTE_ADDRS = frozenset({"127.0.0.1", "::1"})

    def _login_client_ip() -> str:
        """IP for login rate-limit. Honor X-Forwarded-For only behind a local proxy."""
        remote = (request.remote_addr or "").strip()
        if remote in _TRUSTED_PROXY_REMOTE_ADDRS:
            xff = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            if xff:
                return xff
        return remote or "unknown"

    def _verify_panel_password(stored: str, provided: str) -> bool:
        """Verify panel password. Prefers bcrypt hashes; legacy plaintext uses compare_digest."""
        if not stored:
            return False
        try:
            if stored.startswith("$2"):
                return bool(bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8")))
        except Exception:
            pass
        # legacy/plaintext — constant-time compare (CWE-208)
        return compare_digest(str(stored), str(provided))

    @flask_app.route('/login', methods=['GET', 'POST'])
    def login_page():
        # Инициализируем сессию для генерации CSRF токена
        if 'session_init' not in session:
            session['session_init'] = True
        
        settings = get_all_settings()
        totp_enabled = str(settings.get('panel_totp_enabled') or '').lower() in ('1', 'true', 'yes', 'on')
        if request.method == 'POST':
            ip = _login_client_ip()
            if not _rate_limit_login(ip):
                flash('Слишком много попыток. Подождите несколько минут.', 'danger')
                return render_template('login.html', totp_enabled=totp_enabled), 429
            username = request.form.get('username') or ''
            password = request.form.get('password') or ''
            stored_user = settings.get('panel_login') or ''
            stored_pass = settings.get('panel_password') or ''
            # Constant-time username compare (avoids timing oracle on login name).
            user_ok = compare_digest(str(username), str(stored_user)) if stored_user else False
            pass_ok = _verify_panel_password(str(stored_pass), str(password))
            totp_ok = True
            if user_ok and pass_ok and totp_enabled:
                secret = decrypt_managed_bot_token(settings.get('panel_totp_secret') or '')
                code = (request.form.get('totp') or '').strip()
                totp_ok = bool(secret) and bool(pyotp.TOTP(secret).verify(code, valid_window=1))
            if user_ok and pass_ok and totp_ok:
                # migrate legacy/plaintext password to bcrypt hash (CWE-916)
                if not str(stored_pass).startswith('$2'):
                    try:
                        new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        update_setting('panel_password', new_hash)
                    except Exception as e:
                        logger.warning(f'Panel password hash migration failed: {e}')
                # Panel admin session flag — intentionally isolated from webapp user
                # auth_token / database.get_user_by_auth_token. A stolen user token
                # cannot set session['logged_in']; only this password login path can.
                session['logged_in'] = True
                session.permanent = bool(request.form.get('remember_me'))
                return redirect(url_for('dashboard_page'))
            else:
                flash('Неверный логин или пароль', 'danger')
        return render_template('login.html', totp_enabled=totp_enabled)

    @flask_app.route('/logout', methods=['POST'])
    @login_required
    def logout_page():
        session.pop('logged_in', None)
        flash('Вы успешно вышли.', 'success')
        return redirect(url_for('login_page'))

    def get_common_template_data():
        bot_status = _bot_controller.get_status()
        support_bot_status = _support_bot_controller.get_status()
        settings = get_all_settings()
        required_for_start = ['telegram_bot_token', 'telegram_bot_username', 'admin_telegram_id']
        required_support_for_start = ['support_bot_token', 'support_bot_username']
        all_settings_ok = all(settings.get(key) for key in required_for_start)
        try:
            admin_ids = rw_repo.get_admin_ids()
        except Exception:
            admin_ids = set()
        support_settings_ok = all(settings.get(key) for key in required_support_for_start) and bool(admin_ids)
        try:
            open_tickets_count = get_open_tickets_count()
            closed_tickets_count = get_closed_tickets_count()
            all_tickets_count = get_all_tickets_count()
        except Exception:
            open_tickets_count = 0
            closed_tickets_count = 0
            all_tickets_count = 0
        try:
            referral_requests_stats = get_referral_withdrawable_stats()
        except Exception:
            referral_requests_stats = {}
        # Hosts for global user-details modal (issue-key host select) on any page
        try:
            common_hosts = get_all_hosts() or []
        except Exception:
            common_hosts = []
        return {
            "referral_requests_stats": referral_requests_stats,
            "bot_status": bot_status,
            "all_settings_ok": all_settings_ok,
            "support_bot_status": support_bot_status,
            "support_settings_ok": support_settings_ok,
            "open_tickets_count": open_tickets_count,
            "closed_tickets_count": closed_tickets_count,
            "all_tickets_count": all_tickets_count,
            "brand_title": settings.get('panel_brand_title') or 'Xatabchik',
            "panel_login": (settings.get('panel_login') or '').strip(),
            "franchise_enabled": franchise_settings(),
            "franchise_menu_button_visible": franchise_menu_button_visible(),
            "module_menu_items": module_loader.get_menu_items(),
            "hosts": common_hosts,
        }

    @flask_app.route('/brand-title', methods=['POST'])
    @login_required
    def update_brand_title_route():
        title = (request.form.get('title') or '').strip()
        if not title:
            return jsonify({"ok": False, "error": "empty"}), 400
        try:
            update_setting('panel_brand_title', title)
            return jsonify({"ok": True, "title": title})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route('/')
    @login_required
    def index():
        return redirect(url_for('dashboard_page'))

    @flask_app.route('/dashboard')
    @login_required
    def dashboard_page():
        hosts = []
        ssh_targets = []
        try:
            hosts = get_all_hosts()
            ssh_targets = get_all_ssh_targets()
        except Exception:
            hosts = []
            ssh_targets = []
        for h in hosts:
            try:
                h['latest_speedtest'] = get_latest_speedtest(h['host_name'])
            except Exception:
                h['latest_speedtest'] = None
        stats = {
            "user_count": get_user_count(),
            "total_keys": get_total_keys_count(),
            "total_spent": get_total_spent_sum(),
            "host_count": len(hosts)
        }
        
        page = request.args.get('page', 1, type=int)
        per_page = 8
        
        transactions, total_transactions = get_paginated_transactions(page=page, per_page=per_page)
        total_pages = ceil(total_transactions / per_page)
        
        chart_data = get_daily_stats_for_charts(days=30)
        common_data = get_common_template_data()
        common_data['hosts'] = hosts
        
        return render_template(
            'dashboard.html',
            ssh_targets=ssh_targets,
            stats=stats,
            chart_data=chart_data,
            transactions=transactions,
            current_page=page,
            total_pages=total_pages,
            **common_data
        )

    @flask_app.route('/dashboard/run-speedtests', methods=['POST'])
    @login_required
    def run_speedtests_route():
        try:
            speedtest_runner.run_speedtests_for_all_hosts()
            return jsonify({"ok": True})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


    @flask_app.route('/dashboard/stats.partial')
    @login_required
    def dashboard_stats_partial():
        stats = {
            "user_count": get_user_count(),
            "total_keys": get_total_keys_count(),
            "total_spent": get_total_spent_sum(),
            "host_count": len(get_all_hosts())
        }
        common_data = get_common_template_data()
        return render_template('partials/dashboard_stats.html', stats=stats, **common_data)

    @flask_app.route('/dashboard/transactions.partial')
    @login_required
    def dashboard_transactions_partial():
        page = request.args.get('page', 1, type=int)
        per_page = 8
        transactions, total_transactions = get_paginated_transactions(page=page, per_page=per_page)
        return render_template('partials/dashboard_transactions.html', transactions=transactions)

    @flask_app.route('/dashboard/charts.json')
    @login_required
    def dashboard_charts_json():
        data = get_daily_stats_for_charts(days=30)
        return jsonify(data)


    @flask_app.route('/statistics')
    @login_required
    def statistics_page():
        """Страница статистики (обзор)."""
        # Hosts / servers
        try:
            hosts = get_all_hosts() or []
        except Exception:
            hosts = []

        servers_total = len(hosts)
        servers_active = 0
        for h in hosts:
            try:
                servers_active += 1 if int(h.get('is_active', 1) or 0) == 1 else 0
            except Exception:
                servers_active += 1
        servers_disabled = max(0, servers_total - servers_active)

        # Admin stats
        try:
            a = get_admin_stats() or {}
        except Exception:
            a = {}

        clients_total = int(a.get('total_users') or 0)
        clients_today_new = int(a.get('today_new_users') or 0)

        # Active clients = users having at least one non-expired key
        clients_active = 0
        try:
            db_path = str(rw_repo.database.DB_FILE)
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT user_id)
                    FROM vpn_keys
                    WHERE expire_at IS NULL
                       OR datetime(expire_at) > CURRENT_TIMESTAMP
                    """
                )
                row = cur.fetchone()
                clients_active = int(row[0] or 0) if row else 0
        except Exception:
            clients_active = 0
        clients_no_sub = max(0, clients_total - clients_active)

        # Payments (transactions)
        payments_total = 0
        payments_sum = 0.0
        payments_today = 0
        payments_today_sum = 0.0
        try:
            db_path = str(rw_repo.database.DB_FILE)
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(amount_rub), 0)
                    FROM transactions
                    WHERE status IN ('paid','success','succeeded')
                      AND LOWER(COALESCE(payment_method, '')) <> 'balance'
                    """
                )
                row = cur.fetchone() or (0, 0)
                payments_total = int(row[0] or 0)
                payments_sum = float(row[1] or 0.0)

                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(amount_rub), 0)
                    FROM transactions
                    WHERE status IN ('paid','success','succeeded')
                      AND date(created_date) = date('now')
                      AND LOWER(COALESCE(payment_method, '')) <> 'balance'
                    """
                )
                row = cur.fetchone() or (0, 0)
                payments_today = int(row[0] or 0)
                payments_today_sum = float(row[1] or 0.0)
        except Exception:
            pass

        # Referrals
        referrals_total = 0
        referrals_today = 0
        try:
            db_path = str(rw_repo.database.DB_FILE)
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
                referrals_total = int((cur.fetchone() or [0])[0] or 0)
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM users
                    WHERE referred_by IS NOT NULL
                      AND date(registration_date) = date('now')
                    """
                )
                referrals_today = int((cur.fetchone() or [0])[0] or 0)
        except Exception:
            pass

        # Gifts (user-to-user gifted subscriptions, see user_gifts table)
        gifts_total = 0
        gifts_used = 0
        gifts_pending = 0
        try:
            db_path = str(rw_repo.database.DB_FILE)
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(CASE WHEN is_activated THEN 1 ELSE 0 END), 0)
                    FROM user_gifts
                    """
                )
                row = cur.fetchone() or (0, 0)
                gifts_total = int(row[0] or 0)
                gifts_used = int(row[1] or 0)
                gifts_pending = max(0, gifts_total - gifts_used)
        except Exception:
            pass

        # Reachability (real subscribers vs. those who blocked the bot / deleted their account)
        try:
            reachability = rw_repo.get_reachability_stats() or {}
        except Exception:
            reachability = {}

        metrics = {
            'clients_total': clients_total,
            'clients_active': clients_active,
            'clients_no_sub': clients_no_sub,
            'clients_today_new': clients_today_new,
            'payments_total': payments_total,
            'payments_sum': payments_sum,
            'payments_today': payments_today,
            'payments_today_sum': payments_today_sum,
            'referrals_total': referrals_total,
            'referrals_today': referrals_today,
            'servers_total': servers_total,
            'servers_active': servers_active,
            'servers_disabled': servers_disabled,
            'gifts_total': gifts_total,
            'gifts_used': gifts_used,
            'gifts_pending': gifts_pending,
            'reachable_users': reachability.get('reachable', 0),
            'blocked_bot_users': reachability.get('blocked_bot', 0),
            'deactivated_users': reachability.get('deactivated', 0),
        }

        # Charts
        daily = get_daily_stats_for_charts(days=30) or {'users': {}, 'keys': {}}

        from datetime import date
        def _labels(days: int) -> list[str]:
            today = date.today()
            return [(today - timedelta(days=i)).isoformat() for i in reversed(range(days))]

        labels30 = _labels(30)
        labels7 = _labels(7)

        payments_map: dict[str, float] = {}
        referrals_map: dict[str, int] = {}
        plans_labels: list[str] = []
        plans_values: list[int] = []
        try:
            db_path = str(rw_repo.database.DB_FILE)
            with sqlite3.connect(db_path) as conn:
                cur = conn.cursor()

                # Payments series (last 7 days)
                cur.execute(
                    """
                    SELECT date(created_date) AS day, COALESCE(SUM(amount_rub), 0)
                    FROM transactions
                    WHERE status IN ('paid','success','succeeded')
                      AND date(created_date) >= date('now', '-6 days')
                      AND LOWER(COALESCE(payment_method, '')) <> 'balance'
                    GROUP BY day
                    ORDER BY day
                    """
                )
                for day, total in cur.fetchall() or []:
                    payments_map[str(day)] = float(total or 0.0)

                # Referrals series (last 30 days)
                cur.execute(
                    """
                    SELECT date(registration_date) AS day, COUNT(*)
                    FROM users
                    WHERE referred_by IS NOT NULL
                      AND date(registration_date) >= date('now', '-29 days')
                    GROUP BY day
                    ORDER BY day
                    """
                )
                for day, cnt in cur.fetchall() or []:
                    referrals_map[str(day)] = int(cnt or 0)

                # Plans popularity (all time, based on metadata.plan_name)
                cur.execute(
                    """
                    SELECT metadata
                    FROM transactions
                    WHERE status IN ('paid','success','succeeded')
                    """
                )
                counts: dict[str, int] = {}
                for (meta,) in cur.fetchall() or []:
                    if not meta:
                        name = 'N/A'
                    else:
                        try:
                            m = json.loads(meta)
                            name = (m.get('plan_name') or 'N/A')
                        except Exception:
                            name = 'N/A'
                    name = str(name).strip() or 'N/A'
                    counts[name] = counts.get(name, 0) + 1
                top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
                plans_labels = [k for k, _ in top]
                plans_values = [v for _, v in top]
        except Exception:
            pass

        chart_data = {
            'users': daily.get('users') or {},
            'keys': daily.get('keys') or {},
            'payments': payments_map,
            'referrals': referrals_map,
            'plans': {'labels': plans_labels, 'values': plans_values},
            'labels30': labels30,
            'labels7': labels7,
        }

        common_data = get_common_template_data()
        return render_template('statistics.html', metrics=metrics, chart_data=chart_data, **common_data)

    # === Раздел «Продажи и аналитика» ===

    @flask_app.route('/analytics')
    @login_required
    def analytics_overview_page():
        overview = get_sales_overview()
        forecast = get_revenue_forecast()
        users_no_real_pay = get_users_without_real_payment_with_keys()
        trial_stats = get_trial_key_stats()
        common_data = get_common_template_data()
        return render_template(
            'analytics/overview.html',
            active_tab='overview',
            overview=overview,
            forecast=forecast,
            users_no_real_pay=users_no_real_pay,
            trial_stats=trial_stats,
            **common_data,
        )

    @flask_app.route('/analytics/overview_charts.json')
    @login_required
    def analytics_overview_charts_json():
        days = request.args.get('days', 30, type=int)
        series = get_revenue_series(days=days)
        return jsonify(series)

    @flask_app.route('/analytics/transactions')
    @login_required
    def analytics_transactions_page():
        page = request.args.get('page', 1, type=int)
        per_page = 20
        search = request.args.get('q')
        sort_by = request.args.get('sort_by')
        sort_dir = request.args.get('sort_dir')
        transactions, total = get_transactions_paginated(
            page=page, per_page=per_page, search=search, sort_by=sort_by, sort_dir=sort_dir,
        )
        total_pages = max(1, ceil(total / per_page))
        common_data = get_common_template_data()
        return render_template(
            'analytics/transactions.html',
            active_tab='transactions',
            transactions=transactions,
            current_page=page,
            total_pages=total_pages,
            search=search or '',
            sort_by=sort_by or '',
            sort_dir=sort_dir or '',
            **common_data,
        )

    @flask_app.route('/analytics/transactions.csv')
    @login_required
    def analytics_transactions_csv():
        import csv
        import io
        search = request.args.get('q')
        sort_by = request.args.get('sort_by')
        sort_dir = request.args.get('sort_dir')
        transactions, _total = get_transactions_paginated(
            page=1, per_page=100000, search=search, sort_by=sort_by, sort_dir=sort_dir,
        )
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=';')
        writer.writerow(['ID', 'Пользователь', 'Сумма RUB', 'Статус', 'Метод оплаты', 'ID провайдера', 'Тариф', 'Действие', 'Дата'])
        for t in transactions:
            writer.writerow([
                t.get('transaction_id'),
                t.get('username') or t.get('user_id'),
                t.get('amount_rub'),
                t.get('status'),
                t.get('payment_method'),
                t.get('provider_transaction_id'),
                t.get('plan_name'),
                t.get('action_label'),
                t.get('created_date'),
            ])
        from flask import Response
        return Response(
            buf.getvalue().encode('utf-8-sig'),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=transactions.csv'},
        )

    @flask_app.route('/analytics/plans')
    @login_required
    def analytics_plans_page():
        plans = get_plans_analytics(limit=50)
        common_data = get_common_template_data()
        return render_template('analytics/plans.html', active_tab='plans', plans=plans, **common_data)

    @flask_app.route('/analytics/payment-methods')
    @login_required
    def analytics_payment_methods_page():
        methods = get_payment_methods_analytics()
        common_data = get_common_template_data()
        return render_template('analytics/payment_methods.html', active_tab='payment_methods', methods=methods, **common_data)

    @flask_app.route('/analytics/referrals')
    @login_required
    def analytics_referrals_page():
        referrals = get_referrals_analytics()
        top_referrers = get_top_referrers(limit=15)
        top_buyers = get_top_buyers(limit=15)
        common_data = get_common_template_data()
        return render_template(
            'analytics/referrals.html',
            active_tab='referrals',
            referrals=referrals,
            top_referrers=top_referrers,
            top_buyers=top_buyers,
            **common_data,
        )

    @flask_app.route('/analytics/coupons')
    @login_required
    def analytics_coupons_page():
        coupons = get_coupons_analytics()
        plans = get_all_plans() or []
        common_data = get_common_template_data()
        return render_template('analytics/coupons.html', active_tab='coupons', coupons=coupons, plans=plans, **common_data)

    @flask_app.route('/analytics/coupons/create', methods=['POST'])
    @login_required
    def analytics_coupons_create_route():
        code = (request.form.get('code') or '').strip()
        discount_percent = (request.form.get('discount_percent') or '').strip()
        discount_amount = (request.form.get('discount_amount') or '').strip()
        usage_limit_total = (request.form.get('usage_limit_total') or '').strip()
        usage_limit_per_user = (request.form.get('usage_limit_per_user') or '').strip()
        valid_from_raw = (request.form.get('valid_from') or '').strip()
        valid_until_raw = (request.form.get('valid_until') or '').strip()
        description = (request.form.get('description') or '').strip() or None
        segment_type_raw = (request.form.get('segment_type') or '').strip() or None
        segment_value_raw = (request.form.get('segment_value') or '').strip()
        plan_ids_raw = request.form.getlist('applicable_plan_ids')

        try:
            valid_from = datetime.fromisoformat(valid_from_raw) if valid_from_raw else None
            valid_until = datetime.fromisoformat(valid_until_raw) if valid_until_raw else None
            applicable_plan_ids = None
            if plan_ids_raw:
                applicable_plan_ids = [int(x) for x in plan_ids_raw if str(x).strip()]
                if not applicable_plan_ids:
                    applicable_plan_ids = None
            segment_value = float(segment_value_raw) if segment_value_raw else None
            ok = rw_repo.create_promo_code(
                code,
                discount_percent=float(discount_percent) if discount_percent else None,
                discount_amount=float(discount_amount) if discount_amount else None,
                usage_limit_total=int(usage_limit_total) if usage_limit_total else None,
                usage_limit_per_user=int(usage_limit_per_user) if usage_limit_per_user else None,
                valid_from=valid_from,
                valid_until=valid_until,
                created_by=session.get('admin_id'),
                description=description,
                applicable_plan_ids=applicable_plan_ids,
                segment_type=segment_type_raw,
                segment_value=segment_value,
            )
        except ValueError as e:
            flash(f'Не удалось создать купон: {e}', 'danger')
            return redirect(url_for('analytics_coupons_page'))
        except Exception:
            logger.warning('Ошибка создания промокода', exc_info=True)
            flash('Не удалось создать купон: некорректные данные.', 'danger')
            return redirect(url_for('analytics_coupons_page'))

        if ok:
            flash(f'Купон {code.strip().upper()} создан.', 'success')
        else:
            flash('Не удалось создать купон: код уже существует или занят.', 'danger')
        return redirect(url_for('analytics_coupons_page'))

    @flask_app.route('/analytics/coupons/<path:code>/toggle', methods=['POST'])
    @login_required
    def analytics_coupons_toggle_route(code):
        make_active = (request.form.get('is_active') == '1')
        ok = rw_repo.update_promo_code_status(code, is_active=make_active)
        if ok:
            flash(f'Купон {code.strip().upper()} {"активирован" if make_active else "деактивирован"}.', 'success')
        else:
            flash('Не удалось изменить статус купона.', 'danger')
        return redirect(url_for('analytics_coupons_page'))

    @flask_app.route('/analytics/coupons/<path:code>/delete', methods=['POST'])
    @login_required
    def analytics_coupons_delete_route(code):
        ok = rw_repo.delete_promo_code(code)
        if ok:
            flash(f'Купон {code.strip().upper()} удалён.', 'success')
        else:
            flash('Не удалось удалить купон.', 'danger')
        return redirect(url_for('analytics_coupons_page'))

    @flask_app.route('/analytics/utm')
    @login_required
    def analytics_utm_page():
        links = get_utm_analytics()
        bot_username = (get_setting('telegram_bot_username') or '').strip()
        common_data = get_common_template_data()
        return render_template(
            'analytics/utm.html',
            active_tab='utm',
            links=links,
            bot_username=bot_username,
            **common_data,
        )

    @flask_app.route('/analytics/utm/create', methods=['POST'])
    @login_required
    def analytics_utm_create_route():
        slug = (request.form.get('slug') or '').strip()
        ok = create_utm_link(
            slug,
            source=request.form.get('source') or None,
            medium=request.form.get('medium') or None,
            campaign=request.form.get('campaign') or None,
            content=request.form.get('content') or None,
            term=request.form.get('term') or None,
            label=request.form.get('label') or None,
            comment=request.form.get('comment') or None,
            budget=request.form.get('budget') or None,
        )
        if ok:
            flash('UTM-метка создана.', 'success')
        else:
            flash('Не удалось создать метку (пустой/занятый slug).', 'danger')
        return redirect(url_for('analytics_utm_page'))

    @flask_app.route('/analytics/utm/<path:slug>/delete', methods=['POST'])
    @login_required
    def analytics_utm_delete_route(slug):
        ok = delete_utm_link(slug)
        if ok:
            flash(f'UTM-метка "{slug}" удалена.', 'success')
        else:
            flash('Не удалось удалить метку.', 'danger')
        return redirect(url_for('analytics_utm_page'))

    # === Раздел «Рефералка» ===

    REFERRAL_METHOD_LABELS = {"sbp": "СБП", "card": "Номер карты", "usdt_trc20": "USDT TRC20"}
    REFERRAL_STATUS_LABELS = {"new": "Новая", "processing": "В обработке", "paid": "Выплачено", "rejected": "Отклонена"}

    def _referral_program_common():
        # referral_requests_stats уже приходит из get_common_template_data()
        # (используется в сайдбаре для бейджа), поэтому здесь его не дублируем.
        return {
            "referral_method_labels": REFERRAL_METHOD_LABELS,
            "referral_status_labels": REFERRAL_STATUS_LABELS,
        }

    @flask_app.route('/referral-program')
    @login_required
    def referral_program_page():
        return redirect(url_for('referral_program_requests_page'))

    @flask_app.route('/referral-program/settings', methods=['GET'])
    @login_required
    def referral_program_settings_page():
        settings = get_all_settings()
        sbp_banks = [b.strip() for b in (settings.get('referral_withdraw_sbp_banks') or '').split(',') if b.strip()]
        common_data = get_common_template_data()
        return render_template(
            'referral_program/settings.html',
            active_tab='settings',
            settings=settings,
            sbp_banks=sbp_banks,
            **_referral_program_common(),
            **common_data,
        )

    @flask_app.route('/referral-program/settings', methods=['POST'])
    @login_required
    def referral_program_settings_route():
        checkbox_keys = [
            "referral_withdraw_enabled",
            "referral_withdraw_sbp_enabled",
            "referral_withdraw_card_enabled",
            "referral_withdraw_usdt_enabled",
        ]
        for key in checkbox_keys:
            values = request.form.getlist(key) or ['off']
            raw = values[-1]
            update_setting(key, 'true' if str(raw).lower() in ('on', 'true', '1', 'yes') else 'false')

        for key in ("referral_reward_type", "minimum_withdrawal", "referral_percentage",
                    "fixed_referral_bonus_amount", "referral_on_start_referrer_amount",
                    "referral_discount", "referral_withdraw_sbp_banks"):
            if key in request.form:
                update_setting(key, request.form.get(key))

        flash('Настройки реферальной программы сохранены.', 'success')
        return redirect(url_for('referral_program_settings_page'))

    @flask_app.route('/referral-program/top')
    @login_required
    def referral_program_top_page():
        top_referrers = get_top_referrers(limit=50)
        common_data = get_common_template_data()
        return render_template(
            'referral_program/top.html',
            active_tab='top',
            top_referrers=top_referrers,
            **_referral_program_common(),
            **common_data,
        )

    @flask_app.route('/referral-program/requests')
    @login_required
    def referral_program_requests_page():
        status_filter = (request.args.get('status') or '').strip().lower() or None
        requests_list = list_referral_withdrawal_requests(status=status_filter)
        common_data = get_common_template_data()
        return render_template(
            'referral_program/requests.html',
            active_tab='requests',
            requests_list=requests_list,
            status_filter=status_filter or '',
            **_referral_program_common(),
            **common_data,
        )

    @flask_app.route('/referral-program/requests/<int:request_id>/status', methods=['POST'])
    @login_required
    def referral_program_request_status_route(request_id):
        new_status = (request.form.get('status') or '').strip().lower()
        reject_reason = (request.form.get('reject_reason') or '').strip() or None
        ok, msg, updated = update_referral_withdrawal_request_status(
            request_id, new_status, reject_reason=reject_reason,
        )
        if ok and updated:
            try:
                user_id = int(updated.get('user_id'))
                amount = float(updated.get('amount') or 0)
                method_label = REFERRAL_METHOD_LABELS.get(updated.get('method_type'), updated.get('method_type'))
                if new_status == 'paid':
                    text = (
                        f"✅ Ваша заявка на вывод {amount:.2f} ₽ ({method_label}) выплачена.\n"
                        "Спасибо, что участвуете в реферальной программе!"
                    )
                    _dispatch_bot_notification(user_id, text)
                elif new_status == 'processing':
                    text = (
                        f"⏳ Ваша заявка на вывод {amount:.2f} ₽ ({method_label}) взята в обработку."
                    )
                    _dispatch_bot_notification(user_id, text)
                elif new_status == 'rejected':
                    reason_safe = html_escape.escape(reject_reason) if reject_reason else ""
                    reason_line = f"\nПричина: {reason_safe}" if reason_safe else ""
                    text = (
                        f"❌ Ваша заявка на вывод {amount:.2f} ₽ ({method_label}) отклонена.{reason_line}\n"
                        "Сумма возвращена на ваш реферальный баланс."
                    )
                    _dispatch_bot_notification(user_id, text)
            except Exception:
                logger.warning('Не удалось отправить уведомление по заявке на вывод', exc_info=True)
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
        return redirect(request.referrer or url_for('referral_program_requests_page'))

    @flask_app.route('/analytics/economics')
    @login_required
    def analytics_economics_page():
        entries = get_server_cost_entries()
        summary = get_economics_summary()
        common_data = get_common_template_data()
        return render_template(
            'analytics/economics.html',
            active_tab='economics',
            entries=entries,
            summary=summary,
            **common_data,
        )

    @flask_app.route('/analytics/economics/create', methods=['POST'])
    @login_required
    def analytics_economics_create_route():
        create_server_cost_entry(
            request.form.get('server_label') or '',
            linked_host_name=request.form.get('linked_host_name') or None,
            provider=request.form.get('provider') or None,
            location=request.form.get('location') or None,
            monthly_cost=float(request.form.get('monthly_cost') or 0),
            currency=request.form.get('currency') or 'RUB',
            status=request.form.get('status') or 'active',
            comment=request.form.get('comment') or None,
        )
        flash('Запись о расходах добавлена.', 'success')
        return redirect(url_for('analytics_economics_page'))

    @flask_app.route('/analytics/economics/<int:entry_id>/delete', methods=['POST'])
    @login_required
    def analytics_economics_delete_route(entry_id: int):
        delete_server_cost_entry(entry_id)
        flash('Запись удалена.', 'success')
        return redirect(url_for('analytics_economics_page'))

    @flask_app.route('/analytics/forecast')
    @login_required
    def analytics_forecast_page():
        forecast = get_revenue_forecast()
        plans = get_plans_analytics(limit=5)
        common_data = get_common_template_data()
        return render_template(
            'analytics/forecast.html',
            active_tab='forecast',
            forecast=forecast,
            plans=plans,
            **common_data,
        )

    # ─── Рассылки ───────────────────────────────────────────────────────────────

    @flask_app.route('/analytics/broadcasts')
    @login_required
    def analytics_broadcasts_page():
        campaigns = get_broadcast_campaigns()
        for c in campaigns:
            c['stats'] = get_broadcast_stats(c['id'])
        common_data = get_common_template_data()
        return render_template(
            'analytics/broadcasts.html',
            active_tab='broadcasts',
            campaigns=campaigns,
            **common_data,
        )

    @flask_app.route('/analytics/broadcasts/create', methods=['POST'])
    @login_required
    def analytics_broadcasts_create():
        name = (request.form.get('name') or '').strip()
        text_html = (request.form.get('text_html') or '').strip()
        interval_hours = request.form.get('interval_hours', '72')
        target_segment = request.form.get('target_segment', 'inactive')
        if not name or not text_html:
            flash('Заполните название и текст рассылки.', 'danger')
            return redirect(url_for('analytics_broadcasts_page'))
        try:
            interval_hours = max(1, int(interval_hours))
        except (ValueError, TypeError):
            interval_hours = 72
        cid = create_broadcast_campaign(name, text_html, interval_hours, target_segment)
        if cid:
            flash(f'Рассылка «{name}» создана.', 'success')
        else:
            flash('Ошибка при создании рассылки.', 'danger')
        return redirect(url_for('analytics_broadcasts_page'))

    @flask_app.route('/analytics/broadcasts/<int:campaign_id>/update', methods=['POST'])
    @login_required
    def analytics_broadcasts_update(campaign_id):
        name = (request.form.get('name') or '').strip()
        text_html = (request.form.get('text_html') or '').strip()
        interval_hours = request.form.get('interval_hours', '72')
        if not name or not text_html:
            flash('Заполните название и текст рассылки.', 'danger')
            return redirect(url_for('analytics_broadcasts_page'))
        try:
            interval_hours = max(1, int(interval_hours))
        except (ValueError, TypeError):
            interval_hours = 72
        ok = update_broadcast_campaign(campaign_id, name=name, text_html=text_html, interval_hours=interval_hours)
        flash('Рассылка обновлена.' if ok else 'Ошибка при обновлении.', 'success' if ok else 'danger')
        return redirect(url_for('analytics_broadcasts_page'))

    @flask_app.route('/analytics/broadcasts/<int:campaign_id>/toggle', methods=['POST'])
    @login_required
    def analytics_broadcasts_toggle(campaign_id):
        new_state = toggle_broadcast_campaign(campaign_id)
        flash(f"Рассылка {'включена' if new_state else 'выключена'}.", 'success')
        return redirect(url_for('analytics_broadcasts_page'))

    @flask_app.route('/analytics/broadcasts/<int:campaign_id>/delete', methods=['POST'])
    @login_required
    def analytics_broadcasts_delete(campaign_id):
        c = get_broadcast_campaign(campaign_id)
        ok = delete_broadcast_campaign(campaign_id)
        name = (c or {}).get('name', f'#{campaign_id}')
        flash(f'Рассылка «{name}» удалена.' if ok else 'Ошибка при удалении.', 'success' if ok else 'danger')
        return redirect(url_for('analytics_broadcasts_page'))

    @flask_app.route('/analytics/broadcasts/<int:campaign_id>/send-now', methods=['POST'])
    @login_required
    def analytics_broadcasts_send_now(campaign_id):
        c = get_broadcast_campaign(campaign_id)
        if not c:
            flash('Рассылка не найдена.', 'danger')
            return redirect(url_for('analytics_broadcasts_page'))
        interval_hours = int(c.get('interval_hours') or 72)
        recipients = get_pending_broadcast_recipients(campaign_id, interval_hours)
        mark_broadcast_run(campaign_id)
        if not recipients:
            flash('Нет пользователей для отправки (все уже получили или нет неактивных).', 'warning')
            return redirect(url_for('analytics_broadcasts_page'))
        text = c.get('text_html') or ''
        sent = 0
        failed = 0
        for uid in recipients:
            try:
                _dispatch_bot_notification(int(uid), text)
                sent += 1
            except Exception:
                failed += 1
        if sent:
            record_broadcast_sends(campaign_id, recipients)
        flash(f'Отправлено: {sent}, не доставлено: {failed}.', 'success' if sent else 'warning')
        return redirect(url_for('analytics_broadcasts_page'))

    # ─── Webapp auto-setup ────────────────────────────────────────────────────

    _DOMAIN_RE = re.compile(r'^[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]{0,61}[a-z0-9])?)+$')
    _EMAIL_RE  = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,253}\.[^@\s]{2,}$')

    _ACME_WEBROOT = "/var/www/html"

    def _build_nginx_config(domain: str, port: int) -> str:
        """HTTP-only config; serves ACME webroot so certbot --webroot works."""
        return (
            f"server {{\n"
            f"    listen 80;\n"
            f"    listen [::]:80;\n"
            f"    server_name {domain};\n"
            f"    client_max_body_size 100M;\n\n"
            f"    location /.well-known/acme-challenge/ {{\n"
            f"        root /var/www/html;\n"
            f"        try_files $uri =404;\n"
            f"    }}\n\n"
            f"    location / {{\n"
            f"        proxy_pass http://127.0.0.1:{port};\n"
            f"        proxy_set_header Host $host;\n"
            f"        proxy_set_header X-Real-IP $remote_addr;\n"
            f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            f"        proxy_set_header X-Forwarded-Proto $scheme;\n"
            f"        proxy_http_version 1.1;\n"
            f"        proxy_set_header Upgrade $http_upgrade;\n"
            f"        proxy_set_header Connection \"upgrade\";\n"
            f"    }}\n"
            f"}}\n"
        )

    def _build_nginx_ssl_config(domain: str, port: int) -> str:
        """Full SSL config: HTTP → HTTPS redirect + HTTPS reverse proxy."""
        cert = f"/etc/letsencrypt/live/{domain}"
        return (
            f"server {{\n"
            f"    listen 80;\n"
            f"    listen [::]:80;\n"
            f"    server_name {domain};\n"
            f"    location /.well-known/acme-challenge/ {{\n"
            f"        root /var/www/html;\n"
            f"        try_files $uri =404;\n"
            f"    }}\n"
            f"    location / {{ return 301 https://$host$request_uri; }}\n"
            f"}}\n\n"
            f"server {{\n"
            f"    listen 443 ssl;\n"
            f"    listen [::]:443 ssl;\n"
            f"    server_name {domain};\n"
            f"    client_max_body_size 100M;\n\n"
            f"    ssl_certificate {cert}/fullchain.pem;\n"
            f"    ssl_certificate_key {cert}/privkey.pem;\n"
            f"    ssl_protocols TLSv1.2 TLSv1.3;\n"
            f"    ssl_ciphers HIGH:!aNULL:!MD5;\n\n"
            f"    location /.well-known/acme-challenge/ {{\n"
            f"        root /var/www/html;\n"
            f"        try_files $uri =404;\n"
            f"    }}\n\n"
            f"    location / {{\n"
            f"        proxy_pass http://127.0.0.1:{port};\n"
            f"        proxy_set_header Host $host;\n"
            f"        proxy_set_header X-Real-IP $remote_addr;\n"
            f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            f"        proxy_set_header X-Forwarded-Proto $scheme;\n"
            f"        proxy_http_version 1.1;\n"
            f"        proxy_set_header Upgrade $http_upgrade;\n"
            f"        proxy_set_header Connection \"upgrade\";\n"
            f"    }}\n"
            f"}}\n"
        )

    @flask_app.route('/settings/webapp/nginx-config')
    @login_required
    def webapp_nginx_config_route():
        domain = (get_setting('webapp_domain') or '').strip().lower()
        port_str = (get_setting('webapp_port') or '8001').strip()
        try:
            port_int = max(1, min(65535, int(port_str)))
        except (ValueError, TypeError):
            port_int = 8001
        if not domain:
            return Response("# Домен не указан — сохраните настройки сначала.\n", mimetype='text/plain')
        cfg = _build_nginx_config(domain, port_int)
        return Response(cfg, mimetype='text/plain',
                        headers={"Content-Disposition": "attachment; filename=remnawave-webapp.conf"})

    @flask_app.route('/settings/webapp/setup', methods=['POST'])
    @login_required
    def webapp_setup_route():
        domain = (request.form.get('webapp_domain') or '').strip().lower()
        email  = (request.form.get('ssl_email') or '').strip()
        port_s = (request.form.get('webapp_port') or '8001').strip()

        steps = []

        def _step(name, status, message):
            steps.append({"name": name, "status": status, "message": message})

        def _run(name, cmd, timeout=90, extra_env=None):
            try:
                env = ({**os.environ, **extra_env}) if extra_env else None
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
                ok = r.returncode == 0
                _step(name, "ok" if ok else "error", ((r.stdout + r.stderr).strip()[:800]) or ("OK" if ok else "ошибка"))
                return ok
            except FileNotFoundError:
                _step(name, "skip", f"Команда не найдена: {cmd[0]}")
                return False
            except subprocess.TimeoutExpired:
                _step(name, "error", "Таймаут выполнения")
                return False
            except Exception as exc:
                _step(name, "error", str(exc)[:400])
                return False

        # --- Validate inputs ---
        if not _DOMAIN_RE.match(domain):
            return jsonify({"success": False, "steps": [{"name": "Валидация", "status": "error", "message": "Некорректный домен (допустимы латинские буквы, цифры, дефис, точки)."}]})
        if not _EMAIL_RE.match(email):
            return jsonify({"success": False, "steps": [{"name": "Валидация", "status": "error", "message": "Некорректный e-mail для Let's Encrypt."}]})
        try:
            port_int = int(port_s)
            if not (1 <= port_int <= 65535):
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"success": False, "steps": [{"name": "Валидация", "status": "error", "message": "Некорректный порт (1–65535)."}]})

        _step("Валидация", "ok", f"Домен: {domain}, порт: {port_int}")

        # --- Save settings ---
        update_setting('webapp_domain', domain)
        update_setting('webapp_port', str(port_int))
        update_setting('webapp_ssl_email', email)
        _step("Сохранение настроек", "ok", "Домен, порт и e-mail сохранены в базе.")

        nginx_conf_name = "remnawave-webapp"
        nginx_conf_path = f"/etc/nginx/sites-available/{nginx_conf_name}.conf"
        nginx_link_path = f"/etc/nginx/sites-enabled/{nginx_conf_name}.conf"
        nginx_cfg = _build_nginx_config(domain, port_int)

        def _nginx_reload(step_name):
            """Try nginx -s reload first (works in Docker), fall back to service/systemctl."""
            for cmd in (["nginx", "-s", "reload"], ["service", "nginx", "reload"], ["systemctl", "reload", "nginx"]):
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    if r.returncode == 0:
                        _step(step_name, "ok", " ".join(cmd))
                        return True
                except FileNotFoundError:
                    continue
                except Exception:
                    continue
            _step(step_name, "error", "Не удалось перезагрузить Nginx ни одним из методов")
            return False

        def _nginx_start():
            """Start nginx after fresh install (Docker-compatible)."""
            for cmd in (["service", "nginx", "start"], ["nginx"]):
                try:
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                    if r.returncode == 0:
                        _step("Запуск Nginx", "ok", " ".join(cmd))
                        return True
                except FileNotFoundError:
                    continue
                except Exception:
                    continue
            _step("Запуск Nginx", "error", "Не удалось запустить Nginx")
            return False

        # --- Check / install nginx ---
        nginx_installed = _run("Проверка Nginx", ["which", "nginx"])
        if not nginx_installed:
            # 'which nginx' failing is expected before installation — demote to skip
            steps[-1]["status"] = "skip"
            steps[-1]["message"] = "Nginx не установлен, будет установлен"
            _run("Обновление пакетной базы", ["apt-get", "update", "-qq"], timeout=120)
            _run("Установка Nginx + certbot", [
                "apt-get", "install", "-y", "--no-install-recommends",
                "nginx", "certbot", "python3-certbot-nginx"
            ], timeout=300, extra_env={"DEBIAN_FRONTEND": "noninteractive"})
            _nginx_start()

        # --- Create ACME webroot (needed by nginx config and certbot) ---
        try:
            os.makedirs(_ACME_WEBROOT, exist_ok=True)
            _step("Директория ACME-webroot", "ok", _ACME_WEBROOT)
        except Exception as exc:
            _step("Директория ACME-webroot", "error", str(exc)[:300])

        # --- Write nginx config ---
        wrote_cfg = False
        try:
            os.makedirs(os.path.dirname(nginx_conf_path), exist_ok=True)
            with open(nginx_conf_path, 'w') as fh:
                fh.write(nginx_cfg)
            _step("Конфиг Nginx", "ok", f"Записан: {nginx_conf_path}")
            wrote_cfg = True
        except PermissionError:
            # Try sudo tee
            r = subprocess.run(["sudo", "tee", nginx_conf_path],
                               input=nginx_cfg, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                _step("Конфиг Nginx", "ok", f"Записан через sudo: {nginx_conf_path}")
                wrote_cfg = True
            else:
                _step("Конфиг Nginx", "error",
                      "Нет прав записи. Скопируйте конфигурацию вручную (кнопка «Скачать конфиг»).")
        except Exception as exc:
            _step("Конфиг Nginx", "error", str(exc)[:400])

        if not wrote_cfg:
            return jsonify({"success": False, "steps": steps, "nginx_config": nginx_cfg})

        # --- Create symlink ---
        if not os.path.lexists(nginx_link_path):
            try:
                os.makedirs(os.path.dirname(nginx_link_path), exist_ok=True)
                os.symlink(nginx_conf_path, nginx_link_path)
                _step("Symlink sites-enabled", "ok", "Создан")
            except PermissionError:
                _run("Symlink sites-enabled", ["sudo", "bash", "-c",
                     f"mkdir -p {os.path.dirname(nginx_link_path)} && "
                     f"ln -sf {nginx_conf_path} {nginx_link_path}"])
            except Exception as exc:
                _step("Symlink sites-enabled", "error", str(exc)[:300])
        else:
            _step("Symlink sites-enabled", "ok", "Уже существует")

        # --- Test and reload nginx ---
        if not _run("Проверка конфига Nginx", ["nginx", "-t"]):
            return jsonify({"success": False, "steps": steps, "nginx_config": nginx_cfg})

        _nginx_reload("Перезагрузка Nginx")

        # --- SSL: auto-detect Traefik (filesystem-first) or fall back to certbot ---
        import json as _json
        import re as _re2

        def _find_traefik_dynamic_dir() -> tuple:
            """Return (dynamic_dir, cert_resolver) scanning filesystem then docker."""
            cert_resolver = "letsencrypt"

            # 1. Scan writable candidate dirs directly (no docker needed)
            for cdir in (
                "/opt/traefik/dynamic",
                "/etc/traefik/dynamic",
                "/var/traefik/dynamic",
                "/usr/local/etc/traefik/dynamic",
            ):
                if not os.path.isdir(cdir):
                    continue
                try:
                    tp = os.path.join(cdir, ".wtest")
                    with open(tp, "w") as _f:
                        _f.write("")
                    os.unlink(tp)
                    return cdir, cert_resolver
                except Exception:
                    continue

            # 2. Infer dynamic dir from traefik.yml
            for cfg_path in (
                "/etc/traefik/traefik.yml",
                "/usr/local/etc/traefik/traefik.yml",
            ):
                try:
                    with open(cfg_path) as _f:
                        _content = _f.read()
                    _m = _re2.search(r'directory:\s*["\']?([^\s"\'#\n]+)', _content)
                    if _m:
                        cdir = _m.group(1).rstrip("/")
                        if os.path.isdir(cdir) and "/remnawave" not in cdir:
                            try:
                                tp = os.path.join(cdir, ".wtest")
                                with open(tp, "w") as _f:
                                    _f.write("")
                                os.unlink(tp)
                                _mr = _re2.search(
                                    r"certificatesResolvers:\s*\n\s+(\w+)", _content
                                )
                                if _mr:
                                    cert_resolver = _mr.group(1)
                                return cdir, cert_resolver
                            except Exception:
                                pass
                except Exception:
                    continue

            # 3. Try docker / sudo docker as last resort
            for _prefix in ([], ["sudo"]):
                try:
                    _dc = _prefix + ["docker"]
                    _r = subprocess.run(
                        _dc + ["ps", "--filter", "name=traefik", "--format", "{{.Names}}"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if _r.returncode != 0 or not _r.stdout.strip():
                        continue
                    _ctr = _r.stdout.strip().splitlines()[0]
                    _r2 = subprocess.run(
                        _dc + ["inspect", "--format", "{{json .Mounts}}", _ctr],
                        capture_output=True, text=True, timeout=10,
                    )
                    if _r2.returncode != 0:
                        continue
                    for _mount in _json.loads(_r2.stdout or "[]"):
                        _dst = _mount.get("Destination", "")
                        _src = _mount.get("Source", "")
                        if not _src or not any(
                            kw in _dst for kw in ("/dynamic", "/conf", "/rules", "/config")
                        ):
                            continue
                        if not os.path.isdir(_src):
                            continue
                        try:
                            tp = os.path.join(_src, ".wtest")
                            with open(tp, "w") as _f:
                                _f.write("")
                            os.unlink(tp)
                            # Try to read cert resolver from container
                            _r3 = subprocess.run(
                                _dc + ["exec", _ctr, "cat", "/etc/traefik/traefik.yml"],
                                capture_output=True, text=True, timeout=10,
                            )
                            if _r3.returncode == 0:
                                _mr = _re2.search(
                                    r"certificatesResolvers:\s*\n\s+(\w+)", _r3.stdout
                                )
                                if _mr:
                                    cert_resolver = _mr.group(1)
                            return _src, cert_resolver
                        except Exception:
                            continue
                except Exception:
                    continue

            return None, cert_resolver

        def _write_traefik_config(dynamic_dir: str, cert_resolver: str) -> tuple:
            # Detect Docker bridge gateway so Traefik (in Docker) can reach host services
            host_ip = "172.17.0.1"
            for _prefix in ([], ["sudo"]):
                try:
                    _r = subprocess.run(
                        _prefix + ["docker", "network", "inspect", "bridge",
                                   "--format", "{{range .IPAM.Config}}{{.Gateway}}{{end}}"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if _r.returncode == 0 and _r.stdout.strip():
                        host_ip = _r.stdout.strip()
                        break
                except Exception:
                    continue

            svc = f"webapp-{domain.replace('.', '-').replace('_', '-')}"
            cfg_yaml = (
                f"http:\n"
                f"  routers:\n"
                f"    {svc}:\n"
                f'      rule: "Host(`{domain}`)"\n'
                f"      service: {svc}\n"
                f"      entryPoints:\n"
                f"        - websecure\n"
                f"      tls:\n"
                f"        certResolver: {cert_resolver}\n"
                f"  services:\n"
                f"    {svc}:\n"
                f"      loadBalancer:\n"
                f"        servers:\n"
                f'          - url: "http://{host_ip}:{port_int}"\n'
            )
            cfg_path = os.path.join(dynamic_dir, "webapp.yml")
            try:
                os.makedirs(dynamic_dir, exist_ok=True)
                with open(cfg_path, "w") as _f:
                    _f.write(cfg_yaml)
                return True, (
                    f"Конфиг записан: {cfg_path} "
                    f"(certResolver: {cert_resolver}, upstream: {host_ip}:{port_int})"
                )
            except Exception as exc:
                return False, f"Не удалось записать {cfg_path}: {exc}"

        traefik_dir, traefik_resolver = _find_traefik_dynamic_dir()

        if traefik_dir:
            # Traefik detected — skip certbot entirely; Traefik handles ACME via TLS-ALPN
            _step("Обнаружен Traefik", "ok", f"Конфиг директория: {traefik_dir}")
            t_ok, t_msg = _write_traefik_config(traefik_dir, traefik_resolver)
            _step("Конфигурация Traefik", "ok" if t_ok else "error", t_msg)
            # Traefik auto-watches the dir; SIGHUP forces immediate reload
            for _prefix in ([], ["sudo"]):
                try:
                    _r = subprocess.run(
                        _prefix + ["docker", "kill", "-s", "HUP", "traefik"],
                        capture_output=True, text=True, timeout=10,
                    )
                    if _r.returncode == 0:
                        _step("Reload Traefik", "ok", "SIGHUP отправлен")
                        break
                except Exception:
                    continue
        else:
            # No Traefik found: try install.sh (handles nginx install + certbot --nginx)
            _install_sh = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "install.sh")
            )
            if os.path.isfile(_install_sh):
                try:
                    os.chmod(_install_sh, 0o755)
                except Exception:
                    pass
                _run(
                    "Установка Nginx + SSL (install.sh)",
                    ["bash", _install_sh],
                    timeout=300,
                    extra_env={
                        "WEBAPP_DOMAIN": domain,
                        "WEBAPP_EMAIL": email,
                        "WEBAPP_PORT": str(port_int),
                        "DEBIAN_FRONTEND": "noninteractive",
                    },
                )
            else:
                # install.sh not found — certbot webroot (nginx must own port 80)
                certbot_ok = _run("SSL-сертификат (Let's Encrypt)", [
                    "certbot", "certonly", "--webroot",
                    "-w", _ACME_WEBROOT,
                    "-d", domain,
                    "--email", email,
                    "--agree-tos", "--non-interactive", "--no-eff-email",
                ], timeout=180)

                if certbot_ok:
                    ssl_cfg = _build_nginx_ssl_config(domain, port_int)
                    try:
                        with open(nginx_conf_path, "w") as fh:
                            fh.write(ssl_cfg)
                        _step("Конфиг Nginx (HTTPS)", "ok", f"SSL-конфиг записан: {nginx_conf_path}")
                    except Exception as exc:
                        _step("Конфиг Nginx (HTTPS)", "error", str(exc)[:300])
                    _nginx_reload("Финальная перезагрузка Nginx")
                else:
                    _step("SSL", "error",
                          "certbot не удался, и директория Traefik не обнаружена. "
                          "Проверьте, что nginx занимает порт 80, или добавьте конфиг Traefik вручную.")

        all_ok = all(s["status"] in ("ok", "skip") for s in steps)
        return jsonify({"success": all_ok, "steps": steps})

    @flask_app.route('/settings/webapp/check', methods=['POST'])
    @login_required
    def webapp_check_route():
        domain = (get_setting('webapp_domain') or '').strip()
        if not domain:
            return jsonify({"ok": False, "message": "Домен не задан. Сохраните настройки."})
        url = f"https://{domain}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "XatabchikBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return jsonify({"ok": True, "message": f"Доступен ✓  (HTTP {resp.status})"})
        except Exception as exc:
            # Try HTTP fallback
            try:
                req2 = urllib.request.Request(f"http://{domain}/", headers={"User-Agent": "XatabchikBot/1.0"})
                with urllib.request.urlopen(req2, timeout=8) as resp2:
                    return jsonify({"ok": True, "message": f"HTTP доступен (статус {resp2.status}), но HTTPS не отвечает: {exc}"})
            except Exception as exc2:
                return jsonify({"ok": False, "message": f"Недоступен по HTTPS: {exc}. HTTP: {exc2}"})

    @flask_app.route('/monitor')
    @login_required
    def monitor_page():
        hosts = []
        ssh_targets = []
        try:
            hosts = get_all_hosts()
            ssh_targets = get_all_ssh_targets()
        except Exception:
            hosts = []
            ssh_targets = []
        common_data = get_common_template_data()
        common_data['hosts'] = hosts
        return render_template('monitor.html', ssh_targets=ssh_targets, **common_data)

    @flask_app.route('/monitor/local.json')
    @login_required
    def monitor_local_json():
        try:
            data = resource_monitor.get_local_metrics()
        except Exception as e:
            data = {"ok": False, "error": str(e)}
        return jsonify(data)

    @flask_app.route('/monitor/host/<host_name>.json')
    @login_required
    def monitor_host_json(host_name: str):
        try:
            data = resource_monitor.get_remote_metrics_for_host(host_name)
        except Exception as e:
            data = {"ok": False, "error": str(e)}
        return jsonify(data)

    @flask_app.route('/monitor/target/<target_name>.json')
    @login_required
    def monitor_target_json(target_name: str):
        try:
            data = resource_monitor.get_remote_metrics_for_target(target_name)
        except Exception as e:
            data = {"ok": False, "error": str(e)}
        return jsonify(data)


    @flask_app.route('/monitor/series/<scope>/<name>.json')
    @login_required
    def monitor_series_json(scope: str, name: str):
        try:
            hours = int(request.args.get('hours', '24') or '24')
        except Exception:
            hours = 24
        
        try:
            series = rw_repo.get_metrics_series(scope, name, since_hours=hours, limit=1000)
            return jsonify({"ok": True, "items": series})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


    @flask_app.route('/support/table.partial')
    @login_required
    def support_table_partial():
        status = request.args.get('status') or None
        page = request.args.get('page', 1, type=int)
        per_page = 12
        tickets, total = get_tickets_paginated(page=page, per_page=per_page, status=status)
        return render_template('partials/support_table.html', tickets=tickets)

    @flask_app.route('/support/open-count.partial')
    @login_required
    def support_open_count_partial():
        try:
            count = get_open_tickets_count() or 0
        except Exception:
            count = 0

        if count and count > 0:
            html = (
                f'<span class="nav-badge nav-badge-success" title="Открытые тикеты">{count}</span>'
            )
        else:
            html = ''
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @flask_app.route('/users')
    @login_required
    def users_page():

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        q = (request.args.get('q') or '').strip()
        sort = (request.args.get('sort') or '').strip()

        users, total = get_users_paginated(page=page, per_page=per_page, q=q or None, sort=sort or None)

        for user in users:
            uid = user['telegram_id']

            try:

                user['balance'] = float(user.get('balance') or 0.0)
            except Exception:
                user['balance'] = 0.0
            try:
                user['referral_balance'] = float(user.get('referral_balance') or 0.0)
            except Exception:
                user['referral_balance'] = 0.0
            try:
                user['keys_count'] = int(user.get('keys_count') or 0)
            except Exception:
                user['keys_count'] = 0
            try:
                user['active_keys_count'] = int(user.get('active_keys_count') or 0)
            except Exception:
                user['active_keys_count'] = 0
            try:
                user['total_spent'] = float(user.get('total_spent') or 0.0)
            except Exception:
                user['total_spent'] = 0.0


        from math import ceil
        total_pages = ceil(total / per_page) if per_page else 1

        common_data = get_common_template_data()
        common_data['hosts'] = get_all_hosts() or []
        return render_template('users.html', users=users, current_page=page, total_pages=total_pages, q=q, per_page=per_page, sort=sort, **common_data)


    @flask_app.route('/users/table.partial')
    @login_required
    def users_table_partial():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        q = (request.args.get('q') or '').strip()
        sort = (request.args.get('sort') or '').strip()
        users, total = get_users_paginated(page=page, per_page=per_page, q=q or None, sort=sort or None)
        for user in users:
            try:
                user['balance'] = float(user.get('balance') or 0.0)
            except Exception:
                user['balance'] = 0.0
            try:
                user['referral_balance'] = float(user.get('referral_balance') or 0.0)
            except Exception:
                user['referral_balance'] = 0.0
            try:
                user['keys_count'] = int(user.get('keys_count') or 0)
            except Exception:
                user['keys_count'] = 0
            try:
                user['active_keys_count'] = int(user.get('active_keys_count') or 0)
            except Exception:
                user['active_keys_count'] = 0
            try:
                user['total_spent'] = float(user.get('total_spent') or 0.0)
            except Exception:
                user['total_spent'] = 0.0
        return render_template('partials/users_table.html', users=users, sort=sort)


    @flask_app.route('/users/<int:user_id>/keys.partial')
    @login_required
    def user_keys_partial(user_id: int):
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = (request.args.get('search') or '').strip()
        try:
            keys, total = get_keys_paginated(page=page, per_page=per_page, search=search or None, user_id=user_id)
        except Exception:
            keys, total = [], 0
        total_pages = ceil(total / per_page) if per_page else 1
        html = render_template('partials/admin_keys_table.html', keys=keys)
        return jsonify({"ok": True, "html": html, "current_page": page, "total_pages": total_pages, "total": total})


    @flask_app.route('/users/<int:user_id>/transactions.partial')
    @login_required
    def user_transactions_partial(user_id: int):
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = (request.args.get('search') or '').strip()
        sort_by = (request.args.get('sort') or '').strip()
        sort_dir = (request.args.get('dir') or '').strip()
        try:
            transactions, total = get_transactions_paginated(
                page=page, per_page=per_page, user_id=user_id,
                search=search or None, sort_by=sort_by or None, sort_dir=sort_dir or None,
            )
        except Exception:
            transactions, total = [], 0
        total_pages = ceil(total / per_page) if per_page else 1
        html = render_template('partials/user_transactions_table.html', transactions=transactions)
        return jsonify({
            "ok": True, "html": html, "current_page": page, "total_pages": total_pages,
            "total": total, "sort": sort_by, "dir": sort_dir,
        })


    @flask_app.route('/users/<int:user_id>/referrals.json')
    @login_required
    def user_referrals_json(user_id: int):
        try:
            refs = get_referrals_for_user(user_id) or []
            return jsonify({"ok": True, "items": refs, "count": len(refs)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route('/users/search.json')
    @login_required
    def users_search_json():
        """Живой поиск пользователей по ID/username — для модалки "Назначить реферала"
        на карточке пользователя (и для любых будущих похожих подборов пользователя)."""
        q = (request.args.get('q') or '').strip()
        try:
            exclude_id = int(request.args.get('exclude', 0) or 0)
        except (TypeError, ValueError):
            exclude_id = 0
        if not q:
            return jsonify({"ok": True, "items": []})
        try:
            users, _total = get_users_paginated(page=1, per_page=8, q=q, sort=None)
        except Exception as e:
            logger.error(f"users_search_json failed: {e}")
            return jsonify({"ok": False, "error": "search_failed"}), 500

        items = [
            {
                "telegram_id": u.get("telegram_id"),
                "username": u.get("username"),
                "referred_by": u.get("referred_by"),
            }
            for u in (users or [])
            if u.get("telegram_id") != exclude_id
        ]
        return jsonify({"ok": True, "items": items})

    @flask_app.route('/admin/search.json')
    @login_required
    def admin_global_search_json():
        """Живой поиск по пользователям и ключам для топбара админки."""
        q = (request.args.get('q') or '').strip().lstrip('@')
        if not q:
            return jsonify({"ok": True, "users": [], "keys": []})
        try:
            limit = int(request.args.get('limit', 6) or 6)
        except (TypeError, ValueError):
            limit = 6
        limit = max(1, min(limit, 12))

        users_out = []
        keys_out = []
        try:
            users, _ = get_users_paginated(page=1, per_page=limit, q=q, sort=None)
            users_out = [
                {
                    "type": "user",
                    "telegram_id": u.get("telegram_id"),
                    "username": u.get("username"),
                }
                for u in (users or [])
            ]
        except Exception as e:
            logger.error("admin_global_search_json users failed: %s", e)

        try:
            keys, _ = get_keys_paginated(page=1, per_page=limit, search=q)
            keys_out = [
                {
                    "type": "key",
                    "key_id": k.get("key_id"),
                    "user_id": k.get("user_id"),
                    "email": k.get("key_email") or k.get("email"),
                    "host_name": k.get("host_name"),
                    "user_key_name": k.get("user_key_name"),
                }
                for k in (keys or [])
            ]
        except Exception as e:
            logger.error("admin_global_search_json keys failed: %s", e)

        return jsonify({"ok": True, "users": users_out, "keys": keys_out, "q": q})

    @flask_app.route('/users/<int:referrer_id>/referrals/assign', methods=['POST'])
    @login_required
    def assign_referral_route(referrer_id: int):
        """Вручную назначить реферала: пользователь `user_id` (из формы) становится
        приглашённым текущим пользователем `referrer_id` (users.referred_by)."""
        try:
            invitee_id = int(request.form.get('user_id', '0') or '0')
        except (TypeError, ValueError):
            invitee_id = 0

        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not invitee_id:
            payload = {"ok": False, "error": "Не указан пользователь"}
            if wants_json:
                return jsonify(payload), 400
            flash(payload["error"], 'danger')
            return redirect(url_for('users_page'))

        status = link_referrer_if_eligible(invitee_id, referrer_id)
        status_messages = {
            "linked": (True, f"Пользователь #{invitee_id} назначен рефералом."),
            "already_linked": (False, "У этого пользователя уже есть реферер."),
            "self_referral_forbidden": (False, "Пользователь не может быть рефералом самого себя."),
            "invalid_referrer": (False, "Текущий пользователь не найден."),
            "not_eligible": (False, "Не удалось назначить реферала — пользователь не найден или недоступен."),
        }
        ok, message = status_messages.get(status, (False, "Не удалось назначить реферала."))

        if wants_json:
            return jsonify({"ok": ok, "status": status, "message": message})
        flash(message, 'success' if ok else 'danger')
        return redirect(url_for('users_page'))

    @flask_app.route('/users/<int:referrer_id>/referrals/<int:invitee_id>/remove', methods=['POST'])
    @login_required
    def remove_referral_route(referrer_id: int, invitee_id: int):
        """Снять одного реферала с карточки реферера (обнулить users.referred_by)."""
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        status = unlink_referral(invitee_id, referrer_id)
        status_messages = {
            "unlinked": (True, f"Реферал #{invitee_id} удалён из списка."),
            "not_linked": (False, "Этот пользователь не является рефералом текущего пользователя."),
            "not_found": (False, "Пользователь не найден."),
            "invalid": (False, "Некорректные параметры."),
        }
        ok, message = status_messages.get(status, (False, "Не удалось удалить реферала."))
        if wants_json:
            return jsonify({"ok": ok, "status": status, "message": message})
        flash(message, 'success' if ok else 'danger')
        return redirect(url_for('users_page'))

    @flask_app.route('/users/<int:referrer_id>/referrals/remove-all', methods=['POST'])
    @login_required
    def remove_all_referrals_route(referrer_id: int):
        """Снять всех рефералов у указанного реферера."""
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        ok, removed = unlink_all_referrals(referrer_id)
        if ok:
            if removed:
                message = f"Удалено рефералов: {removed}."
            else:
                message = "У пользователя нет рефералов."
        else:
            message = "Не удалось удалить рефералов."
        if wants_json:
            return jsonify({"ok": ok, "removed": removed, "message": message})
        flash(message, 'success' if ok else 'danger')
        return redirect(url_for('users_page'))


    @flask_app.route('/users/pagination.partial')
    @login_required
    def users_pagination_partial():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        q = (request.args.get('q') or '').strip()
        sort = (request.args.get('sort') or '').strip()
        _, total = get_users_paginated(page=page, per_page=per_page, q=q or None, sort=sort or None)
        from math import ceil
        total_pages = ceil(total / per_page) if per_page else 1
        return render_template('partials/users_pagination.html', current_page=page, total_pages=total_pages, q=q, per_page=per_page, sort=sort)

    @flask_app.route('/users/<int:user_id>/details.json')
    @login_required
    def user_details_json(user_id: int):
        user = get_user(user_id)
        if not user:
            return jsonify({"ok": False, "error": "not_found"}), 404

        try:
            keys = get_user_keys(user_id) or []
        except Exception:
            keys = []
        keys_count = len(keys)
        active_keys_count = 0
        now = datetime.now()
        for k in keys:
            try:
                expire_raw = k.get('expiry_date') or k.get('expire_at')
                if not expire_raw:
                    continue
                expire_dt = datetime.strptime(str(expire_raw)[:19], "%Y-%m-%d %H:%M:%S")
                if expire_dt > now and not k.get('missing_from_server_at'):
                    active_keys_count += 1
            except Exception:
                continue

        try:
            refs = get_referrals_for_user(user_id) or []
        except Exception:
            refs = []

        try:
            _, transactions_count = get_transactions_paginated(page=1, per_page=1, user_id=user_id)
        except Exception:
            transactions_count = 0

        return jsonify({
            "ok": True,
            "user": {
                "telegram_id": user.get('telegram_id'),
                "username": user.get('username'),
                "is_banned": bool(user.get('is_banned')),
                "is_unreachable": bool(user.get('is_unreachable')),
                "unreachable_reason": user.get('unreachable_reason'),
                "balance": float(user.get('balance') or 0.0),
                "referral_balance": float(user.get('referral_balance') or 0.0),
                "total_spent": float(user.get('total_spent') or 0.0),
                "registration_date": user.get('registration_date'),
                "keys_count": keys_count,
                "active_keys_count": active_keys_count,
                "transactions_count": transactions_count,
            },
            "referrals": refs,
        })

    @flask_app.route('/users/<int:user_id>/balance/adjust', methods=['POST'])
    @login_required
    def adjust_balance_route(user_id: int):
        try:
            delta = float(request.form.get('delta', '0') or '0')
        except ValueError:

            wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if wants_json:
                return jsonify({"ok": False, "error": "invalid_amount"}), 400
            flash('Некорректная сумма изменения баланса.', 'danger')
            return redirect(url_for('users_page'))

        ok = adjust_user_balance(user_id, delta)
        message = 'Баланс изменён.' if ok else 'Не удалось изменить баланс.'
        category = 'success' if ok else 'danger'
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": ok, "message": message})
        flash(message, category)

        try:
            if ok:
                bot = _bot_controller.get_bot_instance()
                if bot:
                    sign = '+' if delta >= 0 else ''
                    text = f"💳 Ваш баланс был изменён администратором: {sign}{delta:.2f} RUB\nТекущий баланс: {get_balance(user_id):.2f} RUB"
                    loop = _bot_controller.get_loop()
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=user_id, text=text), loop)
                        logger.info(f"Запланирована отправка уведомления о балансе пользователю {user_id}")
                    else:

                        logger.warning("Цикл событий (EVENT_LOOP) не запущен; использую резервный asyncio.run для уведомления о балансе")
                        asyncio.run(bot.send_message(chat_id=user_id, text=text))
                else:
                    logger.warning("Экземпляр бота отсутствует; не могу отправить уведомление о балансе")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о балансе: {e}")
        return redirect(url_for('users_page'))

    @flask_app.route('/users/<int:user_id>/referral-balance/adjust', methods=['POST'])
    @login_required
    def adjust_referral_balance_route(user_id: int):
        try:
            delta = float(request.form.get('delta', '0') or '0')
        except ValueError:
            wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            if wants_json:
                return jsonify({"ok": False, "error": "invalid_amount"}), 400
            flash('Некорректная сумма изменения реферального баланса.', 'danger')
            return redirect(url_for('users_page'))

        ok = adjust_user_referral_balance(user_id, delta)
        message = 'Реферальный баланс изменён.' if ok else 'Не удалось изменить реферальный баланс.'
        category = 'success' if ok else 'danger'
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": ok, "message": message})
        flash(message, category)

        try:
            if ok:
                bot = _bot_controller.get_bot_instance()
                if bot:
                    sign = '+' if delta >= 0 else ''
                    text = f"🤝 Ваш реферальный баланс был изменён администратором: {sign}{delta:.2f} RUB\nТекущий реферальный баланс: {get_referral_balance(user_id):.2f} RUB"
                    loop = _bot_controller.get_loop()
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=user_id, text=text), loop)
                        logger.info(f"Запланирована отправка уведомления о реферальном балансе пользователю {user_id}")
                    else:
                        logger.warning("Цикл событий (EVENT_LOOP) не запущен; использую резервный asyncio.run для уведомления о реферальном балансе")
                        asyncio.run(bot.send_message(chat_id=user_id, text=text))
                else:
                    logger.warning("Экземпляр бота отсутствует; не могу отправить уведомление о реферальном балансе")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о реферальном балансе: {e}")
        return redirect(url_for('users_page'))

    @flask_app.route('/admin/keys')
    @login_required
    def admin_keys_page():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        search = (request.args.get('search') or '').strip()
        sort_by = (request.args.get('sort') or '').strip()
        sort_dir = (request.args.get('dir') or '').strip()
        keys = []
        total = 0
        try:
            keys, total = get_keys_paginated(page=page, per_page=per_page, search=search, sort_by=sort_by, sort_dir=sort_dir)
        except Exception:
            keys = []
            total = 0
        hosts = []
        try:
            hosts = get_all_hosts()
        except Exception:
            hosts = []
        users = []
        try:
            users = get_all_users()
        except Exception:
            users = []
        total_pages = ceil(total / per_page) if per_page else 1
        common_data = get_common_template_data()
        common_data['hosts'] = hosts
        return render_template(
            'admin_keys.html',
            keys=keys,
            users=users,
            current_page=page,
            total_pages=total_pages,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
            **common_data,
        )


    @flask_app.route('/admin/keys/table.partial')
    @login_required
    def admin_keys_table_partial():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        search = (request.args.get('search') or '').strip()
        sort_by = (request.args.get('sort') or '').strip()
        sort_dir = (request.args.get('dir') or '').strip()
        keys = []
        try:
            keys, _ = get_keys_paginated(page=page, per_page=per_page, search=search, sort_by=sort_by, sort_dir=sort_dir)
        except Exception:
            keys = []
        return render_template('partials/admin_keys_table.html', keys=keys)

    @flask_app.route('/admin/keys/pagination.partial')
    @login_required
    def admin_keys_pagination_partial():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        search = (request.args.get('search') or '').strip()
        sort_by = (request.args.get('sort') or '').strip()
        sort_dir = (request.args.get('dir') or '').strip()
        _, total = get_keys_paginated(page=page, per_page=per_page, search=search, sort_by=sort_by, sort_dir=sort_dir)
        total_pages = ceil(total / per_page) if per_page else 1
        return render_template(
            'partials/admin_keys_pagination.html',
            current_page=page,
            total_pages=total_pages,
            per_page=per_page,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

    def _resolve_key_plan(key: dict) -> dict | None:
        """Определяет актуальный тариф ключа по plan_id, сохранённому в его description."""
        try:
            desc = key.get('description')
            if isinstance(desc, str) and desc.strip().startswith('{'):
                meta = json.loads(desc)
                if isinstance(meta, dict) and meta.get('plan_id') is not None:
                    return get_plan_by_id(int(meta.get('plan_id')))
        except Exception:
            pass
        return None

    @flask_app.route('/admin/keys/<int:key_id>/details')
    @login_required
    def admin_key_details_json(key_id: int):
        key = get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404

        owner = None
        try:
            owner = get_user(key.get('user_id'))
        except Exception:
            owner = None

        plan = None
        plan_id = None
        try:
            desc = key.get('description')
            if isinstance(desc, str) and desc.strip().startswith('{'):
                meta = json.loads(desc)
                if isinstance(meta, dict) and meta.get('plan_id') is not None:
                    plan_id = int(meta.get('plan_id'))
        except Exception:
            plan_id = None
        if plan_id:
            try:
                plan = get_plan_by_id(plan_id)
            except Exception:
                plan = None

        host_name = key.get('host_name')
        plans_for_host = []
        try:
            plans_for_host = get_plans_for_host(host_name) or []
        except Exception:
            plans_for_host = []

        subscription_url = key.get('subscription_url') or key.get('connection_string')
        qr_data_url = None
        if subscription_url:
            try:
                import qrcode
                from io import BytesIO
                buf = BytesIO()
                qrcode.make(subscription_url).save(buf, format='PNG')
                qr_data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
            except Exception as e:
                logger.warning(f"Не удалось сгенерировать QR для ключа {key_id}: {e}")
                qr_data_url = None

        devices = []
        try:
            user_uuid = key.get('remnawave_user_uuid')
            key_email = key.get('key_email') or key.get('email')
            if user_uuid:
                hwid_payload = asyncio.run(
                    remnawave_api.get_hwid_devices_for_user(
                        user_uuid, host_name=host_name, email=key_email
                    )
                )
                if isinstance(hwid_payload, dict):
                    for container_key in ('devices', 'response', 'data', 'items'):
                        container = hwid_payload.get(container_key)
                        if isinstance(container, list):
                            devices = [d for d in container if isinstance(d, dict)]
                            break
                elif isinstance(hwid_payload, list):
                    devices = [d for d in hwid_payload if isinstance(d, dict)]
        except Exception as e:
            logger.warning(f"Не удалось получить устройства ключа {key_id}: {e}")
            devices = []

        lte_state = None
        node_usage_rows = []
        node_usage_period_start = None
        account_lte = should_account_lte_traffic(plan, host_name)
        if account_lte:
            try:
                # LTE-пул принадлежит ключу, а не пользователю.
                lte_state = get_key_lte_state(key_id)
            except Exception:
                lte_state = None
            try:
                node_usage_period_start = resolve_key_period_start(key)
                node_usage_rows = get_node_usage_for_key(key_id, node_usage_period_start)
            except Exception as e:
                logger.warning(f"Не удалось получить расход по нодам для ключа {key_id}: {e}")

        return jsonify({
            "ok": True,
            "key": {
                "key_id": key.get('key_id'),
                "user_id": key.get('user_id'),
                "host_name": host_name,
                "key_email": key.get('key_email') or key.get('email'),
                "expire_at": key.get('expire_at') or key.get('expiry_date'),
                "created_at": key.get('created_at') or key.get('created_date'),
                "comment": (key.get('comment_key') or key.get('comment') or ''),
                "comment_key": (key.get('comment_key') or ''),
                "tag": key.get('tag'),
                "traffic_limit_bytes": key.get('traffic_limit_bytes'),
                "traffic_boost_bytes": key.get('traffic_boost_bytes') or 0,
                "traffic_limit_strategy": key.get('traffic_limit_strategy') or "NO_RESET",
                "next_traffic_reset_at": key.get('next_traffic_reset_at'),
                "next_traffic_reset_display": format_next_traffic_reset_display(key.get('next_traffic_reset_at')),
                "hwid_device_limit": (plan or {}).get('hwid_device_limit'),
                "subscription_url": subscription_url,
            },
            "owner": {
                "telegram_id": key.get('user_id'),
                "username": (owner or {}).get('username'),
                "balance": (owner or {}).get('balance'),
            } if owner else {"telegram_id": key.get('user_id')},
            "plan": ({
                "plan_id": plan.get('plan_id'),
                "plan_name": plan.get('plan_name'),
                "months": plan.get('months'),
                "price": plan.get('price'),
                "traffic_limit_bytes": plan.get('traffic_limit_bytes'),
                "hwid_device_limit": plan.get('hwid_device_limit'),
                "lte_limit_bytes": plan.get('lte_limit_bytes'),
            } if plan else None),
            "plans_for_host": [
                {
                    "plan_id": p.get('plan_id'),
                    "plan_name": p.get('plan_name'),
                    "months": p.get('months'),
                    "price": p.get('price'),
                } for p in plans_for_host
            ],
            "qr_data_url": qr_data_url,
            "devices": devices,
            "account_lte": account_lte,
            "lte_state": lte_state,
            # Разбивка расхода по нодам LTE-сквада за текущий расчётный период.
            # Название ноды намеренно не отдаётся в карточку ключа — только идентификатор.
            "node_usage": [
                {
                    "node_uuid": r.get('node_uuid'),
                    "used_bytes": r.get('used_bytes') or 0,
                    "updated_at": r.get('updated_at'),
                }
                for r in node_usage_rows
            ],
            "node_usage_period_start": node_usage_period_start,
        })

    @flask_app.route('/admin/keys/<int:key_id>/change-plan', methods=['POST'])
    @login_required
    def admin_key_change_plan_route(key_id: int):
        key = get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404
        plan_id = request.form.get('plan_id', type=int)
        if not plan_id:
            return jsonify({"ok": False, "error": "plan_required"}), 400
        plan = get_plan_by_id(plan_id)
        if not plan:
            return jsonify({"ok": False, "error": "plan_not_found"}), 404

        host_name = key.get('host_name')
        email = key.get('key_email') or key.get('email')
        if not host_name or not email:
            return jsonify({"ok": False, "error": "invalid_key"}), 400

        # Сохраняем текущий срок действия ключа неизменным
        expiry_ms = None
        try:
            expire_at_str = key.get('expire_at') or key.get('expiry_date')
            if expire_at_str:
                dt = datetime.strptime(str(expire_at_str)[:19], "%Y-%m-%d %H:%M:%S")
                expiry_ms = int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
        except Exception:
            expiry_ms = None

        # ВАЖНО: если у тарифа лимит не задан (None/0 в БД означает "без ограничения"),
        # нужно явно передать 0 в Remnawave, а не None — иначе create_or_update_key_on_host
        # подставит дефолтный лимит сквада (squad.default_traffic_limit_bytes), и смена на
        # безлимитный тариф не снимет действовавшее ранее ограничение (баг: лимит "прилипал"
        # в зависимости от подключённого сквада, а не от выбранного тарифа).
        plan_traffic_limit = plan.get('traffic_limit_bytes')
        try:
            plan_traffic_limit = int(plan_traffic_limit) if plan_traffic_limit not in (None, '') else 0
        except Exception:
            plan_traffic_limit = 0
        if plan_traffic_limit < 0:
            plan_traffic_limit = 0

        plan_device_limit = plan.get('hwid_device_limit')
        try:
            plan_device_limit = int(plan_device_limit) if plan_device_limit not in (None, '') else 0
        except Exception:
            plan_device_limit = 0
        if plan_device_limit < 0:
            plan_device_limit = 0

        plan_traffic_strategy = remnawave_traffic_limit_strategy_for_plan(plan)

        try:
            result = asyncio.run(remnawave_api.create_or_update_key_on_host(
                host_name, email,
                expiry_timestamp_ms=expiry_ms,
                description=key.get('description'),
                tag=key.get('tag'),
                traffic_limit_bytes=plan_traffic_limit,
                traffic_limit_strategy=plan_traffic_strategy,
                hwid_device_limit=plan_device_limit,
                plan_id=plan_id,
            ))
        except Exception as e:
            logger.error(f"Смена тарифа ключа {key_id}: ошибка remnawave: {e}")
            result = None
        if not result:
            return jsonify({"ok": False, "error": "host_failed"}), 500

        try:
            new_description = json.dumps({
                "plan_id": plan_id,
                "plan_name": plan.get('plan_name'),
                "months": plan.get('months'),
            })
            update_key_fields(
                key_id,
                traffic_limit_bytes=plan_traffic_limit,
                traffic_boost_bytes=0,
                description=new_description,
            )
            apply_key_monthly_reset_fields(
                key_id, plan, restart_cycle=True, expire_main_boost=True
            )
        except Exception as e:
            logger.warning(f"Не удалось обновить локальную запись ключа {key_id} после смены тарифа: {e}")

        return jsonify({"ok": True, "plan_id": plan_id, "plan_name": plan.get('plan_name')})

    @flask_app.route('/admin/keys/<int:key_id>/add-traffic', methods=['POST'])
    @login_required
    def admin_key_add_traffic_route(key_id: int):
        key = get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404
        gb = request.form.get('gb', type=float)
        if not gb or gb <= 0:
            return jsonify({"ok": False, "error": "invalid_amount"}), 400

        # Докупка трафика бессмысленна (и вредна) для тарифов без ограничения трафика:
        # если у тарифа лимит не задан (0/None), ключ безлимитный, и наложение "буста"
        # превратило бы его в ограниченный. Поэтому запрещаем такую докупку.
        plan_for_check = _resolve_key_plan(key)
        if not plan_for_check or int(plan_for_check.get('traffic_limit_bytes') or 0) <= 0:
            return jsonify({"ok": False, "error": "unlimited_plan"}), 400

        add_bytes = int(gb * 1024 * 1024 * 1024)
        host_name = key.get('host_name')
        user_uuid = key.get('remnawave_user_uuid')
        email = key.get('key_email') or key.get('email')
        current_boost = int(key.get('traffic_boost_bytes') or 0)

        user_payload = None
        try:
            user_payload = asyncio.run(
                remnawave_api.lookup_panel_user(user_uuid, email=email, host_name=host_name)
            )
            if user_payload:
                resolved = remnawave_api.panel_user_ref_from_payload(user_payload)
                if resolved:
                    user_uuid = resolved
        except Exception as e:
            logger.error(f"Добавление трафика ключу {key_id}: ошибка получения пользователя Remnawave: {e}")

        current_limit = None
        if isinstance(user_payload, dict):
            current_limit = user_payload.get('trafficLimitBytes')
        if current_limit is None:
            current_limit = key.get('traffic_limit_bytes') or 0

        new_limit = int(current_limit or 0) + add_bytes
        new_boost = current_boost + add_bytes

        if not user_uuid:
            return jsonify({"ok": False, "error": "no_remote_user"}), 400
        try:
            ok_remote = asyncio.run(remnawave_api.update_user_traffic_limit(user_uuid, new_limit, host_name=host_name))
        except Exception as e:
            logger.error(f"Добавление трафика ключу {key_id}: ошибка обновления лимита в Remnawave: {e}")
            ok_remote = False
        if not ok_remote:
            return jsonify({"ok": False, "error": "host_failed"}), 500

        try:
            update_key_fields(key_id, traffic_limit_bytes=new_limit, traffic_boost_bytes=new_boost)
        except Exception as e:
            logger.warning(f"Не удалось обновить локальную запись ключа {key_id} после добавления трафика: {e}")

        return jsonify({"ok": True, "new_limit_bytes": new_limit, "traffic_boost_bytes": new_boost})

    @flask_app.route('/admin/keys/<int:key_id>/add-lte-traffic', methods=['POST'])
    @login_required
    def admin_key_add_lte_traffic_route(key_id: int):
        key = get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404
        gb = request.form.get('gb', type=float)
        if not gb or gb <= 0:
            return jsonify({"ok": False, "error": "invalid_amount"}), 400

        # LTE-докупка доступна только тарифам, у которых явно задан LTE-пул.
        plan_for_check = _resolve_key_plan(key)
        if not plan_for_check or int(plan_for_check.get('lte_limit_bytes') or 0) <= 0:
            return jsonify({"ok": False, "error": "no_lte_plan"}), 400

        add_bytes = int(gb * 1024 * 1024 * 1024)
        user_id = key.get('user_id')
        host_name = key.get('host_name')

        # Начисление строго аддитивно (+N ГБ к остатку) и атомарно, и адресовано КЛЮЧУ:
        # LTE-пул живёт на ключе. Baseline расхода не сдвигаем, иначе выдача пары ГБ
        # обнуляла бы весь накопленный расход.
        try:
            new_boost = add_key_lte_boost_bytes(key_id, add_bytes)
        except Exception as e:
            logger.error(f"Добавление LTE-трафика ключу {key_id}: ошибка обновления lte_state: {e}")
            return jsonify({"ok": False, "error": "lte_state_failed"}), 500
        if new_boost is None:
            logger.error(f"Добавление LTE-трафика ключу {key_id}: не удалось начислить буст (user_id={user_id})")
            return jsonify({"ok": False, "error": "lte_state_failed"}), 500

        # Немедленно возвращаем доступ на premium-нодах, если ключ был отключён из-за исчерпания LTE
        try:
            lte_squad = get_squad_by_class(host_name, 'lte') if host_name else None
            is_premium = get_host_class(host_name) == 'premium' if host_name else False
            user_uuid = key.get('remnawave_user_uuid')
            state = key.get('remote_access_state')
            if user_uuid and state in ('disabled_premium', 'disabled_premium_squad') and (is_premium or lte_squad):
                # При точечном отключении из подписки убирался только LTE-сквад, поэтому
                # enable_user его не вернёт — нужен add_squad_to_user (как в боте).
                if state == 'disabled_premium_squad' and lte_squad:
                    ok_restore = asyncio.run(
                        remnawave_api.add_squad_to_user(
                            user_uuid, lte_squad['squad_uuid'], host_name=host_name
                        )
                    )
                else:
                    ok_restore = asyncio.run(remnawave_api.enable_user(user_uuid, host_name=host_name))
                if ok_restore:
                    update_key_fields(key_id, remote_access_state='enabled')
                else:
                    # Буст начислен, но доступ на сервере не восстановлен — воркер
                    # enforce_dual_traffic_limits дожмёт это на следующем проходе.
                    logger.error(
                        "Докупка LTE ключу %s: не удалось восстановить доступ на хосте '%s' "
                        "(состояние %s осталось в БД)",
                        key_id, host_name, state,
                    )
        except Exception as e:
            logger.error(f"Не удалось восстановить доступ ключа {key_id} после докупки LTE: {e}", exc_info=True)

        return jsonify({"ok": True, "lte_boost_bytes": new_boost})

    @flask_app.route('/admin/keys/<int:key_id>/devices/delete', methods=['POST'])
    @login_required
    def admin_key_delete_device_route(key_id: int):
        key = get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404
        hwid = (request.form.get('hwid') or '').strip()
        if not hwid:
            return jsonify({"ok": False, "error": "hwid_required"}), 400

        user_uuid = key.get('remnawave_user_uuid')
        host_name = key.get('host_name')
        key_email = key.get('key_email') or key.get('email')
        if not user_uuid:
            return jsonify({"ok": False, "error": "no_remote_user"}), 400

        try:
            ok_remote = asyncio.run(
                remnawave_api.delete_hwid_device(
                    user_uuid, hwid, host_name=host_name, email=key_email
                )
            )
        except Exception as e:
            logger.error(f"Удаление устройства {hwid} ключа {key_id}: ошибка Remnawave: {e}")
            ok_remote = False
        if not ok_remote:
            return jsonify({"ok": False, "error": "host_failed"}), 500

        return jsonify({"ok": True, "hwid": hwid})

    @flask_app.route('/admin/keys/<int:key_id>/devices/delete-all', methods=['POST'])
    @login_required
    def admin_key_delete_all_devices_route(key_id: int):
        key = get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404

        user_uuid = key.get('remnawave_user_uuid')
        host_name = key.get('host_name')
        key_email = key.get('key_email') or key.get('email')
        if not user_uuid:
            return jsonify({"ok": False, "error": "no_remote_user"}), 400

        devices = []
        try:
            hwid_payload = asyncio.run(
                remnawave_api.get_hwid_devices_for_user(
                    user_uuid, host_name=host_name, email=key_email
                )
            )
            if isinstance(hwid_payload, dict):
                for container_key in ('devices', 'response', 'data', 'items'):
                    container = hwid_payload.get(container_key)
                    if isinstance(container, list):
                        devices = [d for d in container if isinstance(d, dict)]
                        break
            elif isinstance(hwid_payload, list):
                devices = [d for d in hwid_payload if isinstance(d, dict)]
        except Exception as e:
            logger.warning(f"Не удалось получить устройства ключа {key_id} перед массовым удалением: {e}")
            devices = []

        deleted = 0
        failed = 0
        for d in devices:
            hwid = d.get('hwid') or d.get('hwId') or d.get('id')
            if not hwid:
                continue
            try:
                ok_remote = asyncio.run(
                    remnawave_api.delete_hwid_device(
                        user_uuid, hwid, host_name=host_name, email=key_email
                    )
                )
            except Exception:
                ok_remote = False
            if ok_remote:
                deleted += 1
            else:
                failed += 1

        return jsonify({"ok": failed == 0, "deleted": deleted, "failed": failed, "total": len(devices)})

    @flask_app.route('/admin/hosts/<host_name>/plans')
    @login_required
    def admin_get_plans_for_host_json(host_name: str):
        try:
            plans = get_plans_for_host(host_name)
            data = [
                {
                    "plan_id": p.get('plan_id'),
                    "plan_name": p.get('plan_name'),
                    "months": p.get('months'),
                    "price": p.get('price'),
                    "hwid_device_limit": p.get('hwid_device_limit'),
                } for p in plans
            ]
            return jsonify({"ok": True, "items": data})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route('/admin/keys/create', methods=['POST'])
    @login_required
    def create_key_route():
        try:
            user_id = int(request.form.get('user_id'))
            host_name = (request.form.get('host_name') or '').strip()
            Remnawave_uuid = (request.form.get('Remnawave_client_uuid') or '').strip()
            key_email = (request.form.get('key_email') or '').strip()
            expiry = request.form.get('expiry_date') or ''
            hwid_device_limit_raw = request.form.get('hwid_device_limit')

            expiry_ms = int(datetime.fromisoformat(expiry).timestamp() * 1000) if expiry else 0
        except Exception:
            flash('Проверьте поля ключа.', 'danger')
            return redirect(request.referrer or url_for('admin_keys_page'))

        if not Remnawave_uuid:
            Remnawave_uuid = str(uuid.uuid4())

        if not key_email:
            try:
                key_email = rw_repo.generate_key_email_for_user(user_id)
            except Exception:
                key_email = f"{user_id}-{int(time.time())}@bot.local"

        hwid_device_limit = None
        if hwid_device_limit_raw is not None and str(hwid_device_limit_raw).strip() != "":
            try:
                hwid_device_limit = max(0, int(float(hwid_device_limit_raw)))
            except Exception:
                hwid_device_limit = None

        result = None
        try:
            result = asyncio.run(
                remnawave_api.create_or_update_key_on_host(
                    host_name,
                    key_email,
                    expiry_timestamp_ms=expiry_ms or None,
                    hwid_device_limit=hwid_device_limit,
                )
            )
        except Exception as e:
            logger.error(f"Не удалось создать/обновить ключ на хосте: {e}")
            result = None
        if not result:
            flash('Не удалось создать ключ на хосте. Проверьте доступность панели.', 'danger')
            return redirect(request.referrer or url_for('admin_keys_page'))


        try:
            Remnawave_uuid = result.get('client_uuid') or Remnawave_uuid
            expiry_ms = result.get('expiry_timestamp_ms') or expiry_ms
        except Exception:
            pass


        new_id = rw_repo.record_key_from_payload(
            user_id=user_id,
            payload=result,
            host_name=host_name,
        )
        flash(('Ключ добавлен.' if new_id else 'Ошибка при добавлении ключа.'), 'success' if new_id else 'danger')


        try:
            bot = _bot_controller.get_bot_instance()
            if bot and new_id:
                text = (
                    '🔐 Ваш ключ готов!\n'
                    f'Сервер: {host_name}\n'
                    'Выдан администратором через панель.\n'
                )
                if result and result.get('connection_string'):
                    cs = html_escape.escape(result['connection_string'])
                    text += f"\nПодключение:\n<pre><code>{cs}</code></pre>"
                loop = _bot_controller.get_loop()
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', disable_web_page_preview=True),
                        loop
                    )
                else:
                    asyncio.run(bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', disable_web_page_preview=True))
        except Exception as e:
            logger.warning(f"Не удалось уведомить пользователя о новом ключе: {e}")
        return redirect(request.referrer or url_for('admin_keys_page'))

    @flask_app.route('/admin/keys/create-ajax', methods=['POST'])
    @login_required
    def create_key_ajax_route():
        """Создание ключа через панель: персонального либо универсального подарочного токена."""
        mode = (request.form.get('mode') or 'personal').strip()
        host_name = (request.form.get('host_name') or '').strip()
        if not host_name:
            return jsonify({"ok": False, "error": "host_required"}), 400

        comment = (request.form.get('comment') or '').strip()
        plan_id = request.form.get('plan_id')
        if not plan_id:
            return jsonify({"ok": False, "error": "plan_required"}), 400
        custom_days_raw = request.form.get('custom_days')
        hwid_device_limit_raw = request.form.get('hwid_device_limit')
        expiry_str = (request.form.get('expiry_date') or '').strip()
        expiry_ms: int | None = None
        if expiry_str:
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                expiry_ms = int(expiry_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
            except Exception:
                return jsonify({"ok": False, "error": "invalid_expiry"}), 400

        days_total = 0
        plan_device_limit = None
        plan = get_plan_by_id(plan_id)
        if not plan:
            return jsonify({"ok": False, "error": "plan_not_found"}), 404
        try:
            months = int(plan.get('months') or 0)
        except Exception:
            months = 0
        days_total += months * 30
        plan_device_limit = plan.get('hwid_device_limit')
        try:
            plan_traffic_limit = int(plan.get('traffic_limit_bytes') or 0)
        except Exception:
            plan_traffic_limit = 0
        if plan_traffic_limit < 0:
            plan_traffic_limit = 0
        plan_traffic_strategy = remnawave_traffic_limit_strategy_for_plan(plan)
        try:
            plan_id_int = int(plan_id)
        except Exception:
            plan_id_int = None
        origin_desc = json.dumps({
            "v": 1,
            "source": "admin",
            "plan_id": plan_id_int,
            "plan_name": plan.get("plan_name"),
            "months": plan.get("months"),
        }, ensure_ascii=False)
        if custom_days_raw:
            try:
                days_total += int(custom_days_raw)
            except Exception:
                pass

        hwid_device_limit = None
        if hwid_device_limit_raw is not None and str(hwid_device_limit_raw).strip() != "":
            try:
                hwid_device_limit = max(0, int(float(hwid_device_limit_raw)))
            except Exception:
                hwid_device_limit = None
        if hwid_device_limit is None and plan_device_limit is not None:
            try:
                hwid_device_limit = max(0, int(plan_device_limit))
            except Exception:
                hwid_device_limit = None

        if mode == 'personal':
            try:
                user_id = int(request.form.get('user_id'))
                key_email = (request.form.get('key_email') or '').strip().lower()
            except Exception as e:
                logger.error(f"create_key_ajax_route: неверные параметры персонального режима: {e}")
                return jsonify({"ok": False, "error": "bad_request"}), 400
            if not key_email:
                try:
                    key_email = rw_repo.generate_key_email_for_user(user_id)
                except Exception:
                    key_email = f"{user_id}-{int(time.time())}@bot.local"
            target_user = get_user(user_id)
            if not target_user:
                return jsonify({"ok": False, "error": "user_not_found"}), 404

            if expiry_ms is None and days_total > 0:
                expiry_ms = int((datetime.utcnow() + timedelta(days=days_total)).replace(tzinfo=timezone.utc).timestamp() * 1000)

            try:
                result = asyncio.run(remnawave_api.create_or_update_key_on_host(
                    host_name,
                    key_email,
                    expiry_timestamp_ms=expiry_ms or None,
                    hwid_device_limit=hwid_device_limit,
                    traffic_limit_bytes=plan_traffic_limit,
                    traffic_limit_strategy=plan_traffic_strategy,
                    plan_id=plan_id_int,
                ))
            except Exception as e:
                result = None
                logger.error(f"create_key_ajax_route: ошибка панели/хоста: {e}")
            if not result:
                return jsonify({"ok": False, "error": "host_failed"}), 500

            key_id = rw_repo.record_key_from_payload(
                user_id=user_id,
                payload=result,
                host_name=host_name,
                description=origin_desc,
            )
            if not key_id:
                return jsonify({"ok": False, "error": "db_failed"}), 500
            try:
                apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
            except Exception:
                logger.warning(f"Не удалось проставить политику сброса трафика для ключа {key_id}", exc_info=True)
            if comment:
                try:
                    update_key_comment(key_id, comment)
                except Exception:
                    logger.warning(f"Не удалось сохранить комментарий ключа {key_id}", exc_info=True)


            try:
                bot = _bot_controller.get_bot_instance()
                if bot and key_id:
                    text = (
                        '🔐 Ваш ключ готов!\n'
                        f'Сервер: {host_name}\n'
                        'Выдан администратором через панель.\n'
                    )
                    if result and result.get('connection_string'):
                        cs = html_escape.escape(result['connection_string'])
                        text += f"\nПодключение:\n<pre><code>{cs}</code></pre>"
                    loop = _bot_controller.get_loop()
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', disable_web_page_preview=True),
                            loop
                        )
                    else:
                        asyncio.run(bot.send_message(chat_id=user_id, text=text, parse_mode='HTML', disable_web_page_preview=True))
            except Exception as e:
                logger.warning(f"Не удалось уведомить пользователя (ajax): {e}")

            return jsonify({
                "ok": True,
                "key_id": key_id,
                "uuid": result.get('client_uuid'),
                "expiry_ms": result.get('expiry_timestamp_ms'),
                "connection": result.get('connection_string')
            })

        if mode == 'gift':
            # Подарочный ключ создаётся так же, как в Telegram-боте: генерируется
            # неактивированная запись в user_gifts + ссылка активации вида
            # {domain}/start?start=gift_<code>. Единственное отличие от "боевого"
            # подарка от пользователя — здесь нет реального "отправителя" (Telegram-аккаунта),
            # поэтому from_user_id проставляется как системный (0), а ключ до момента
            # активации получателем не привязан ни к какому Telegram-аккаунту.
            if expiry_ms is None and days_total > 0:
                expiry_ms = int((datetime.utcnow() + timedelta(days=days_total)).replace(tzinfo=timezone.utc).timestamp() * 1000)

            base_local = f"gift-{uuid.uuid4().hex[:8]}"
            domain_local = "bot.local"
            attempt = 0
            while True:
                candidate_email = f"{base_local if attempt == 0 else base_local + '-' + str(attempt)}@{domain_local}"
                if not rw_repo.get_key_by_email(candidate_email):
                    break
                attempt += 1

            try:
                result = asyncio.run(remnawave_api.create_or_update_key_on_host(
                    host_name,
                    candidate_email,
                    expiry_timestamp_ms=expiry_ms or None,
                    description=comment or 'Gift key (created via admin panel)',
                    tag='user_gift',
                    hwid_device_limit=hwid_device_limit,
                    traffic_limit_bytes=plan_traffic_limit,
                    traffic_limit_strategy=plan_traffic_strategy,
                    plan_id=plan_id_int,
                ))
            except Exception as e:
                logger.error(f"Создание подарочного ключа: ошибка remnawave: {e}")
                result = None
            if not result:
                return jsonify({"ok": False, "error": "host_failed"}), 500

            key_id = rw_repo.record_key_from_payload(
                user_id=0,
                payload=result,
                host_name=host_name,
                tag='user_gift',
                description=origin_desc,
            )
            if not key_id:
                return jsonify({"ok": False, "error": "db_failed"}), 500
            try:
                apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
            except Exception:
                logger.warning(f"Не удалось проставить политику сброса трафика для подарочного ключа {key_id}", exc_info=True)
            if comment:
                try:
                    update_key_comment(key_id, comment)
                except Exception:
                    logger.warning(f"Не удалось сохранить комментарий подарочного ключа {key_id}", exc_info=True)

            gift_result = None
            try:
                gift_result = rw_repo.create_user_gift(
                    from_user_id=0,
                    host_name=host_name,
                    plan_id=int(plan_id) if plan_id else None,
                )
            except Exception as e:
                logger.error(f"Не удалось создать запись о подарке (admin panel): {e}")
                gift_result = None
            if not gift_result:
                return jsonify({"ok": False, "error": "gift_record_failed"}), 500

            try:
                rw_repo.link_key_to_gift(gift_result['gift_id'], key_id)
            except Exception as e:
                logger.warning(f"Не удалось связать ключ {key_id} с подарком {gift_result.get('gift_id')}: {e}")

            gift_code = gift_result.get('gift_code')
            domain = (get_setting("domain") or "").strip()
            bot_username = (get_setting("telegram_bot_username") or "").strip()
            if domain:
                gift_link = f"{domain.rstrip('/')}/start?start=gift_{gift_code}"
            elif bot_username:
                gift_link = f"https://t.me/{bot_username}?start=gift_{gift_code}"
            else:
                gift_link = None

            return jsonify({
                "ok": True,
                "key_id": key_id,
                "gift_code": gift_code,
                "gift_link": gift_link,
                "email": candidate_email,
                "uuid": result.get('client_uuid'),
                "expiry_ms": result.get('expiry_timestamp_ms') or expiry_ms,
                "connection": result.get('connection_string'),
                "note": "Подарочный ключ создан. Ссылка активируется один раз — до активации ключ не привязан к аккаунту.",
            })

        return jsonify({"ok": False, "error": "unsupported_mode"}), 400

    @flask_app.route('/admin/keys/generate-email')
    @login_required
    def generate_key_email_route():
        try:
            user_id = int(request.args.get('user_id'))
        except Exception:
            return jsonify({"ok": False, "error": "invalid user_id"}), 400
        try:
            candidate_email = rw_repo.generate_key_email_for_user(user_id)
            return jsonify({"ok": True, "email": candidate_email})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route('/admin/keys/<int:key_id>/delete', methods=['POST'])
    @login_required
    def delete_key_route(key_id: int):

        try:
            key = rw_repo.get_key_by_id(key_id)
            if key:
                try:
                    asyncio.run(remnawave_api.delete_client_on_host(key['host_name'], key['key_email']))
                except Exception:
                    pass
        except Exception:
            pass
        ok = delete_key_by_id(key_id)
        flash('Ключ удалён.' if ok else 'Не удалось удалить ключ.', 'success' if ok else 'danger')
        return redirect(request.referrer or url_for('admin_keys_page'))

    @flask_app.route('/admin/keys/<int:key_id>/adjust-expiry', methods=['POST'])
    @login_required
    def adjust_key_expiry_route(key_id: int):
        try:
            delta_days = int(request.form.get('delta_days', '0'))
        except Exception:
            return jsonify({"ok": False, "error": "invalid_delta"}), 400
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            return jsonify({"ok": False, "error": "not_found"}), 404
        try:

            cur_expiry = key.get('expiry_date')
            if isinstance(cur_expiry, str):
                try:
                    exp_dt = datetime.fromisoformat(cur_expiry)
                except Exception:

                    try:
                        exp_dt = datetime.strptime(cur_expiry, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        exp_dt = datetime.utcnow()
            else:
                exp_dt = cur_expiry or datetime.utcnow()
            new_dt = exp_dt + timedelta(days=delta_days)
            new_ms = int(new_dt.timestamp() * 1000)


            try:
                result = asyncio.run(remnawave_api.create_or_update_key_on_host(
                    host_name=key.get('host_name'),
                    email=key.get('key_email'),
                    expiry_timestamp_ms=new_ms
                ))
            except Exception as e:
                result = None
            if not result or not result.get('expiry_timestamp_ms'):
                return jsonify({"ok": False, "error": "remnawave_update_failed"}), 500


            client_uuid = result.get('client_uuid') or key.get('remnawave_user_uuid') or ''
            if not rw_repo.update_key(
                key_id,
                remnawave_user_uuid=client_uuid,
                expire_at_ms=int(result.get('expiry_timestamp_ms') or new_ms),
                subscription_url=result.get('subscription_url') or result.get('connection_string'),
            ):
                return jsonify({"ok": False, "error": "db_update_failed"}), 500


            try:
                user_id = key.get('user_id')
                new_ms_final = int(result.get('expiry_timestamp_ms'))
                new_dt_local = datetime.fromtimestamp(new_ms_final/1000)
                text = (
                    "🗓️ Срок вашего VPN-ключа изменён администратором.\n"
                    f"Хост: {key.get('host_name')}\n"
                    f"Email ключа: {key.get('key_email')}\n"
                    f"Новая дата истечения: {new_dt_local.strftime('%Y-%m-%d %H:%M')}"
                )
                if user_id:
                    bot = _bot_controller.get_bot_instance()
                    loop = _bot_controller.get_loop()
                    if bot and loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=user_id, text=text), loop)
                    elif bot:
                        asyncio.run(bot.send_message(chat_id=user_id, text=text))
            except Exception:
                pass

            return jsonify({"ok": True, "new_expiry_ms": int(result.get('expiry_timestamp_ms'))})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route('/admin/keys/sweep-expired', methods=['POST'])
    @login_required
    def sweep_expired_keys_route():
        removed = 0
        failed = 0
        now = datetime.utcnow()
        keys = get_all_keys()
        for k in keys:
            exp = k.get('expiry_date')
            exp_dt = None
            try:
                if isinstance(exp, str):
                    s = exp.strip()
                    if s:
                        try:

                            exp_dt = datetime.fromisoformat(s)
                        except Exception:
                            try:
                                exp_dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                            except Exception:

                                try:
                                    exp_dt = datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
                                except Exception:
                                    exp_dt = None
                else:
                    exp_dt = exp
            except Exception:
                exp_dt = None

            try:
                if exp_dt is not None and getattr(exp_dt, 'tzinfo', None) is not None:
                    exp_dt = exp_dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
            if not exp_dt or exp_dt > now:
                continue

            try:
                try:

                    host_for_delete = (k.get('host_name') or '').strip()
                    if not host_for_delete:
                        try:
                            sq = (k.get('squad_uuid') or k.get('squadUuid') or '').strip()
                            if sq:
                                squad = rw_repo.get_squad(sq)
                                if squad and squad.get('host_name'):
                                    host_for_delete = squad.get('host_name')
                        except Exception:
                            pass
                    if host_for_delete:
                        asyncio.run(remnawave_api.delete_client_on_host(host_for_delete, k.get('key_email')))
                except Exception:
                    pass
                delete_key_by_id(k.get('key_id'))
                removed += 1

                try:
                    bot = _bot_controller.get_bot_instance()
                    loop = _bot_controller.get_loop()
                    text = (
                        "Ваш ключ был автоматически удалён по истечении срока.\n"
                        f"Хост: {k.get('host_name')}\nEmail: {k.get('key_email')}\n"
                        "При необходимости вы можете оформить новый ключ."
                    )
                    if bot and loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=k.get('user_id'), text=text), loop)
                    else:
                        asyncio.run(bot.send_message(chat_id=k.get('user_id'), text=text))
                except Exception:
                    pass
            except Exception:
                failed += 1
        flash(f"Удалено истёкших ключей: {removed}. Ошибок: {failed}.", 'success' if failed == 0 else 'warning')
        return redirect(request.referrer or url_for('admin_keys_page'))

    def _parse_bulk_expiry_params():
        """Общие параметры модалки bulk-extend: mode=days|date + days / expire_at."""
        mode = (request.form.get('mode') or 'days').strip().lower()
        if mode not in ('days', 'date'):
            mode = 'days'
        days = None
        expire_at = None
        if mode == 'days':
            try:
                days = int(request.form.get('days', '0'))
            except Exception:
                days = None
            if days is None or days == 0:
                return None, 'Укажите ненулевое число дней (можно отрицательное).'
        else:
            expire_at = (request.form.get('expire_at') or '').strip()
            if not expire_at:
                return None, 'Укажите дату истечения.'
        return {'mode': mode, 'days': days, 'expire_at': expire_at}, None

    def _apply_bulk_expiry_to_ids(key_ids: list[int], params: dict) -> tuple[int, int, list[int]]:
        ok_n = 0
        fail_n = 0
        failed_ids: list[int] = []
        for kid in key_ids:
            try:
                if params['mode'] == 'days':
                    ok, err = extend_key(int(kid), int(params['days']))
                else:
                    ok, err = set_key_expiry(int(kid), params['expire_at'])
                if ok:
                    ok_n += 1
                else:
                    fail_n += 1
                    failed_ids.append(int(kid))
                    logger.warning("bulk expiry: key #%s failed: %s", kid, err)
            except Exception as e:
                fail_n += 1
                failed_ids.append(int(kid))
                logger.warning("bulk expiry: key #%s exception: %s", kid, e)
        return ok_n, fail_n, failed_ids

    def _flash_bulk_expiry_result(ok_n: int, fail_n: int, failed_ids: list[int]):
        msg = f"Успешно: {ok_n}, Ошибок: {fail_n}."
        if fail_n > 0 and failed_ids:
            preview = ", ".join(f"#{i}" for i in failed_ids[:30])
            more = f" … (+{len(failed_ids) - 30})" if len(failed_ids) > 30 else ""
            msg += f" Ошибки по ключам: {preview}{more}."
        flash(msg, 'success' if fail_n == 0 else 'warning')

    # Массовое изменение срока держит HTTP дольше nginx proxy_read_timeout (~60с):
    # каждый ключ — отдельный Remnawave-запрос. Ключи успевают обновиться, браузер
    # получает 504. Поэтому в проде работа уходит в фон, а ответ отдаём сразу.
    _bulk_expiry_lock = threading.Lock()
    _bulk_expiry_running = False

    def _dispatch_bulk_expiry(
        *,
        key_ids: list[int],
        params: dict,
        admin_who: str,
        label: str,
        log_extra: str = "",
        fallback_endpoint: str = "admin_keys_page",
    ):
        nonlocal _bulk_expiry_running
        ids_copy = list(key_ids)
        params_copy = dict(params)
        dest = request.referrer or url_for(fallback_endpoint)

        def _run():
            logger.info(
                "Admin bulk-extend %s: admin=%s total=%s mode=%s days=%s expire_at=%s%s",
                label,
                admin_who,
                len(ids_copy),
                params_copy["mode"],
                params_copy.get("days"),
                params_copy.get("expire_at"),
                log_extra,
            )
            ok_n, fail_n, failed_ids = _apply_bulk_expiry_to_ids(ids_copy, params_copy)
            logger.info(
                "Admin bulk-extend %s done: admin=%s ok=%s fail=%s%s",
                label,
                admin_who,
                ok_n,
                fail_n,
                log_extra,
            )
            if fail_n and failed_ids:
                preview = ", ".join(f"#{i}" for i in failed_ids[:30])
                more = f" … (+{len(failed_ids) - 30})" if len(failed_ids) > 30 else ""
                logger.warning(
                    "Admin bulk-extend %s failed ids: %s%s", label, preview, more
                )
            return ok_n, fail_n, failed_ids

        if current_app.config.get("BULK_EXTEND_SYNC"):
            ok_n, fail_n, failed_ids = _run()
            _flash_bulk_expiry_result(ok_n, fail_n, failed_ids)
            return redirect(dest)

        with _bulk_expiry_lock:
            if _bulk_expiry_running:
                flash(
                    "Массовое изменение срока уже выполняется. Дождитесь окончания и повторите.",
                    "warning",
                )
                return redirect(dest)
            _bulk_expiry_running = True

        def _job():
            nonlocal _bulk_expiry_running
            try:
                _run()
            except Exception:
                logger.exception(
                    "Admin bulk-extend %s crashed: admin=%s", label, admin_who
                )
            finally:
                with _bulk_expiry_lock:
                    _bulk_expiry_running = False

        try:
            threading.Thread(
                target=_job, name="shopbot-bulk-expiry", daemon=True
            ).start()
        except Exception:
            with _bulk_expiry_lock:
                _bulk_expiry_running = False
            raise

        flash(
            f"Запущено изменение срока для {len(ids_copy)} ключей. "
            "Обработка идёт в фоне и может занять несколько минут — страница не ждёт "
            "окончания. Итог пишется в логи панели.",
            "warning",
        )
        return redirect(dest)

    @flask_app.route('/admin/keys/bulk-extend', methods=['POST'])
    @login_required
    def bulk_extend_keys_route():
        """Режим 1: изменить срок у выбранных key_ids (чекбоксы на странице)."""
        raw_ids = request.form.getlist('key_ids')
        key_ids: list[int] = []
        for v in raw_ids:
            try:
                key_ids.append(int(v))
            except Exception:
                continue
        # unique, stable order
        key_ids = list(dict.fromkeys(key_ids))
        if not key_ids:
            flash('Не выбрано ни одного ключа.', 'warning')
            return redirect(request.referrer or url_for('admin_keys_page'))

        params, err = _parse_bulk_expiry_params()
        if err:
            flash(err, 'danger')
            return redirect(request.referrer or url_for('admin_keys_page'))

        admin_who = (session.get('username') or get_setting('panel_login') or 'admin')
        return _dispatch_bulk_expiry(
            key_ids=key_ids,
            params=params,
            admin_who=admin_who,
            label="SELECTED",
            log_extra=f" ids_sample={key_ids[:20]}",
            fallback_endpoint="admin_keys_page",
        )

    @flask_app.route('/admin/keys/bulk-extend-all', methods=['POST'])
    @login_required
    def bulk_extend_all_keys_route():
        """Режим 2: изменить срок у ВСЕХ ключей в vpn_keys (игнорирует фильтры/выбор)."""
        params, err = _parse_bulk_expiry_params()
        if err:
            flash(err, 'danger')
            return redirect(request.referrer or url_for('admin_keys_page'))

        # Игнорируем любые переданные key_ids — только полный список из БД
        key_ids = get_all_key_ids()
        if not key_ids:
            flash('В базе нет ключей.', 'warning')
            return redirect(request.referrer or url_for('admin_keys_page'))

        admin_who = (session.get('username') or get_setting('panel_login') or 'admin')
        return _dispatch_bulk_expiry(
            key_ids=key_ids,
            params=params,
            admin_who=admin_who,
            label="ALL",
            fallback_endpoint="admin_keys_page",
        )

    @flask_app.route('/admin/keys/bulk-extend-user', methods=['POST'])
    @login_required
    def bulk_extend_user_keys_route():
        """Изменить срок у всех ключей одного пользователя (карточка пользователя)."""
        try:
            user_id = int(request.form.get('user_id') or 0)
        except (TypeError, ValueError):
            user_id = 0
        if user_id <= 0:
            flash('Не указан пользователь.', 'warning')
            return redirect(request.referrer or url_for('users_page'))

        params, err = _parse_bulk_expiry_params()
        if err:
            flash(err, 'danger')
            return redirect(request.referrer or url_for('users_page'))

        key_ids = [
            int(k['key_id'])
            for k in (get_keys_for_user(user_id) or [])
            if k.get('key_id') is not None
        ]
        if not key_ids:
            flash('У пользователя нет ключей.', 'warning')
            return redirect(request.referrer or url_for('users_page'))

        admin_who = (session.get('username') or get_setting('panel_login') or 'admin')
        return _dispatch_bulk_expiry(
            key_ids=key_ids,
            params=params,
            admin_who=admin_who,
            label="USER",
            log_extra=f" user_id={user_id}",
            fallback_endpoint="users_page",
        )

    @flask_app.route('/admin/keys/<int:key_id>/comment', methods=['POST'])
    @login_required
    def update_key_comment_route(key_id: int):
        comment = (request.form.get('comment') or '').strip()
        ok = update_key_comment(key_id, comment)
        flash('Комментарий обновлён.' if ok else 'Не удалось обновить комментарий.', 'success' if ok else 'danger')
        return redirect(request.referrer or url_for('admin_keys_page'))


    @flask_app.route('/admin/hosts/ssh/update', methods=['POST'])
    @login_required
    def update_host_ssh_route():
        host_name = (request.form.get('host_name') or '').strip()
        ssh_host = (request.form.get('ssh_host') or '').strip() or None
        ssh_port_raw = (request.form.get('ssh_port') or '').strip()
        ssh_user = (request.form.get('ssh_user') or '').strip() or None
        ssh_password = (request.form.get('ssh_password') or '').strip()
        ssh_key_path = (request.form.get('ssh_key_path') or '').strip() or None
        ssh_port = None
        try:
            ssh_port = int(ssh_port_raw) if ssh_port_raw else None
        except Exception:
            ssh_port = None
        if not ssh_password:
            existing = get_host(host_name) or {}
            ssh_password = existing.get('ssh_password')
        ok = update_host_ssh_settings(host_name, ssh_host=ssh_host, ssh_port=ssh_port, ssh_user=ssh_user,
                                      ssh_password=ssh_password, ssh_key_path=ssh_key_path)
        flash('SSH-параметры обновлены.' if ok else 'Не удалось обновить SSH-параметры.', 'success' if ok else 'danger')
        return redirect(request.referrer or url_for('settings_page'))


    @flask_app.route('/admin/ssh-targets/<target_name>/speedtest/run', methods=['POST'])
    @login_required
    def run_ssh_target_speedtest_route(target_name: str):
        logger.info(f"Панель: запущен спидтест для SSH-цели '{target_name}'")
        try:
            accept_new = str(request.form.get("accept_new_host_key") or "").strip().lower() in (
                "1", "true", "on", "yes",
            )
            res = asyncio.run(
                speedtest_runner.run_and_store_ssh_speedtest_for_target(
                    target_name, accept_new_host_key=accept_new
                )
            )
        except Exception as e:
            res = {"ok": False, "error": str(e)}
        if res and res.get('ok'):
            logger.info(f"Панель: спидтест для SSH-цели '{target_name}' завершён успешно")
        else:
            logger.warning(f"Панель: спидтест для SSH-цели '{target_name}' завершился с ошибкой: {res.get('error') if res else 'unknown'}")
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify(res)
        flash(('Тест выполнен.' if res and res.get('ok') else f"Ошибка теста: {res.get('error') if res else 'unknown'}"), 'success' if res and res.get('ok') else 'danger')
        return redirect(request.referrer or url_for('settings_page', tab='hosts'))


    @flask_app.route('/admin/ssh-targets/speedtests/run-all', methods=['POST'])
    @login_required
    def run_all_ssh_target_speedtests_route():
        logger.info("Панель: запуск спидтеста ДЛЯ ВСЕХ SSH-целей")
        try:
            targets = get_all_ssh_targets()
        except Exception:
            targets = []
        errors = []
        ok_count = 0
        total = 0
        for t in targets or []:
            name = (t.get('target_name') or '').strip()
            if not name:
                continue
            total += 1
            try:
                res = asyncio.run(speedtest_runner.run_and_store_ssh_speedtest_for_target(name))
                if res and res.get('ok'):
                    ok_count += 1
                else:
                    errors.append(f"{name}: {res.get('error') if res else 'unknown'}")
            except Exception as e:
                errors.append(f"{name}: {e}")
        logger.info(f"Панель: завершён спидтест ДЛЯ ВСЕХ SSH-целей: ок={ok_count}, всего={total}")
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": len(errors) == 0, "done": ok_count, "total": total, "errors": errors})
        if errors:
            flash(f"SSH цели: выполнено {ok_count}/{total}. Ошибки: {'; '.join(errors[:3])}{'…' if len(errors) > 3 else ''}", 'warning')
        else:
            flash(f"SSH цели: тесты скорости выполнены для всех ({ok_count}/{total})", 'success')
        return redirect(request.referrer or url_for('dashboard_page'))


    @flask_app.route('/admin/hosts/<host_name>/speedtest/run', methods=['POST'])
    @login_required
    def run_host_speedtest_route(host_name: str):
        method = (request.form.get('method') or '').strip().lower()
        logger.info(f"Панель: запущен спидтест для хоста '{host_name}', метод='{method or 'both'}'")
        try:
            accept_new = str(request.form.get("accept_new_host_key") or "").strip().lower() in (
                "1", "true", "on", "yes",
            )
            if method == 'ssh':
                res = asyncio.run(
                    speedtest_runner.run_and_store_ssh_speedtest(
                        host_name, accept_new_host_key=accept_new
                    )
                )
            elif method == 'net':
                res = asyncio.run(speedtest_runner.run_and_store_net_probe(host_name))
            else:

                res = asyncio.run(speedtest_runner.run_both_for_host(host_name))
        except Exception as e:
            res = {'ok': False, 'error': str(e)}
        if res and res.get('ok'):
            logger.info(f"Панель: спидтест для хоста '{host_name}' завершён успешно")
        else:
            logger.warning(f"Панель: спидтест для хоста '{host_name}' завершился с ошибкой: {res.get('error') if res else 'unknown'}")
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify(res)
        flash(('Тест выполнен.' if res and res.get('ok') else f"Ошибка теста: {res.get('error') if res else 'unknown'}"), 'success' if res and res.get('ok') else 'danger')
        return redirect(request.referrer or url_for('settings_page'))

    @flask_app.route('/admin/hosts/<host_name>/speedtests.json')
    @login_required
    def host_speedtests_json(host_name: str):
        try:
            limit = int(request.args.get('limit') or 20)
        except Exception:
            limit = 20
        try:
            items = get_speedtests(host_name, limit=limit) or []
            return jsonify({
                'ok': True,
                'items': items
            })
        except Exception as e:
            return jsonify({'ok': False, 'error': str(e)}), 500

    @flask_app.route('/admin/speedtests/run-all', methods=['POST'])
    @login_required
    def run_all_speedtests_route():

        logger.info("Панель: запуск спидтеста ДЛЯ ВСЕХ хостов")
        try:
            hosts = get_all_hosts()
        except Exception:
            hosts = []
        errors = []
        ok_count = 0
        for h in hosts:
            name = h.get('host_name')
            if not name:
                continue
            try:
                res = asyncio.run(speedtest_runner.run_both_for_host(name))
                if res and res.get('ok'):
                    ok_count += 1
                else:
                    errors.append(f"{name}: {res.get('error') if res else 'unknown'}")
            except Exception as e:
                errors.append(f"{name}: {e}")
        logger.info(f"Панель: завершён спидтест ДЛЯ ВСЕХ хостов: ок={ok_count}, всего={len(hosts)}")

        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": len(errors) == 0, "done": ok_count, "total": len(hosts), "errors": errors})
        if errors:
            flash(f"Выполнено для {ok_count}/{len(hosts)}. Ошибки: {'; '.join(errors[:3])}{'…' if len(errors) > 3 else ''}", 'warning')
        else:
            flash(f"Тесты скорости выполнены для всех хостов: {ok_count}/{len(hosts)}", 'success')
        return redirect(request.referrer or url_for('dashboard_page'))


    @flask_app.route('/admin/hosts/<host_name>/speedtest/install', methods=['POST'])
    @login_required
    def auto_install_speedtest_route(host_name: str):
        accept_new = str(request.form.get("accept_new_host_key") or "").strip().lower() in (
            "1", "true", "on", "yes",
        )
        try:
            res = asyncio.run(
                speedtest_runner.auto_install_speedtest_on_host(
                    host_name, accept_new_host_key=accept_new
                )
            )
        except Exception as e:
            res = {'ok': False, 'log': str(e)}
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": bool(res.get('ok')), "log": res.get('log')})
        flash(('Установка завершена успешно.' if res.get('ok') else 'Не удалось установить speedtest на хост.') , 'success' if res.get('ok') else 'danger')

        try:
            log = res.get('log') or ''
            short = '\n'.join((log.splitlines() or [])[-20:])
            if short:
                flash(short, 'secondary')
        except Exception:
            pass
        return redirect(request.referrer or url_for('settings_page'))

    @flask_app.route('/admin/balance')
    @login_required
    def admin_balance_page():
        try:
            user_id = request.args.get('user_id', type=int)
        except Exception:
            user_id = None
        user = None
        balance = None
        referrals = []
        if user_id:
            try:
                user = get_user(user_id)
                balance = get_balance(user_id)
                referrals = get_referrals_for_user(user_id)
            except Exception:
                pass
        common_data = get_common_template_data()
        return render_template('admin_balance.html', user=user, balance=balance, referrals=referrals, **common_data)

    @flask_app.route('/support')
    @login_required
    def support_list_page():
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        per_page = 12
        tickets, total = get_tickets_paginated(page=page, per_page=per_page, status=status if status in ['open', 'closed'] else None)
        total_pages = ceil(total / per_page) if per_page else 1
        open_count = get_open_tickets_count()
        closed_count = get_closed_tickets_count()
        all_count = get_all_tickets_count()
        common_data = get_common_template_data()
        return render_template(
            'support.html',
            tickets=tickets,
            current_page=page,
            total_pages=total_pages,
            filter_status=status,
            open_count=open_count,
            closed_count=closed_count,
            all_count=all_count,
            **common_data
        )

    @flask_app.route('/support/<int:ticket_id>', methods=['GET', 'POST'])
    @login_required
    def support_ticket_page(ticket_id):
        ticket = get_ticket(ticket_id)
        if not ticket:
            flash('Тикет не найден.', 'danger')
            return redirect(url_for('support_list_page'))

        if request.method == 'POST':
            message = (request.form.get('message') or '').strip()
            action = request.form.get('action')
            if action == 'reply':
                if not message:
                    flash('Сообщение не может быть пустым.', 'warning')
                else:
                    add_support_message(ticket_id, sender='admin', content=message)
                    try:
                        bot = _support_bot_controller.get_bot_instance()
                        loop = _support_bot_controller.get_loop()
                        user_chat_id = ticket.get('user_id')
                        if bot and loop and loop.is_running() and user_chat_id:
                            text = f"Ответ по тикету #{ticket_id}:\n\n{message}"
                            asyncio.run_coroutine_threadsafe(bot.send_message(user_chat_id, text), loop)
                        else:
                            logger.error("Ответ поддержки: support-бот или цикл событий недоступны; сообщение пользователю не отправлено.")
                    except Exception as e:
                        logger.error(f"Ответ поддержки: не удалось отправить сообщение пользователю {ticket.get('user_id')} через support-бота: {e}", exc_info=True)
                    try:
                        bot = _support_bot_controller.get_bot_instance()
                        loop = _support_bot_controller.get_loop()
                        forum_chat_id = ticket.get('forum_chat_id')
                        thread_id = ticket.get('message_thread_id')
                        if bot and loop and loop.is_running() and forum_chat_id and thread_id:
                            text = f"💬 Ответ админа из панели по тикету #{ticket_id}:\n\n{message}"
                            asyncio.run_coroutine_threadsafe(
                                bot.send_message(chat_id=int(forum_chat_id), text=text, message_thread_id=int(thread_id)),
                                loop
                            )
                    except Exception as e:
                        logger.warning(f"Ответ поддержки: не удалось отзеркалить сообщение в тему форума для тикета {ticket_id}: {e}")
                    flash('Ответ отправлен.', 'success')
                return redirect(url_for('support_ticket_page', ticket_id=ticket_id))
            elif action == 'close':
                if ticket.get('status') != 'closed' and set_ticket_status(ticket_id, 'closed'):
                    try:
                        bot = _support_bot_controller.get_bot_instance()
                        loop = _support_bot_controller.get_loop()
                        forum_chat_id = ticket.get('forum_chat_id')
                        thread_id = ticket.get('message_thread_id')
                        if bot and loop and loop.is_running() and forum_chat_id and thread_id:
                            asyncio.run_coroutine_threadsafe(
                                bot.close_forum_topic(chat_id=int(forum_chat_id), message_thread_id=int(thread_id)),
                                loop
                            )
                    except Exception as e:
                        logger.warning(f"Закрытие тикета: не удалось закрыть тему форума для тикета {ticket_id}: {e}")
                    try:
                        bot = _support_bot_controller.get_bot_instance()
                        loop = _support_bot_controller.get_loop()
                        user_chat_id = ticket.get('user_id')
                        if bot and loop and loop.is_running() and user_chat_id:
                            text = f"✅ Ваш тикет #{ticket_id} был закрыт администратором. Вы можете создать новое обращение при необходимости."
                            asyncio.run_coroutine_threadsafe(bot.send_message(int(user_chat_id), text), loop)
                    except Exception as e:
                        logger.warning(f"Закрытие тикета: не удалось уведомить пользователя {ticket.get('user_id')} о закрытии тикета #{ticket_id}: {e}")
                    flash('Тикет закрыт.', 'success')
                else:
                    flash('Не удалось закрыть тикет.', 'danger')
                return redirect(url_for('support_ticket_page', ticket_id=ticket_id))
            elif action == 'open':
                if ticket.get('status') != 'open' and set_ticket_status(ticket_id, 'open'):
                    try:
                        bot = _support_bot_controller.get_bot_instance()
                        loop = _support_bot_controller.get_loop()
                        forum_chat_id = ticket.get('forum_chat_id')
                        thread_id = ticket.get('message_thread_id')
                        if bot and loop and loop.is_running() and forum_chat_id and thread_id:
                            asyncio.run_coroutine_threadsafe(
                                bot.reopen_forum_topic(chat_id=int(forum_chat_id), message_thread_id=int(thread_id)),
                                loop
                            )
                    except Exception as e:
                        logger.warning(f"Открытие тикета: не удалось переоткрыть тему форума для тикета {ticket_id}: {e}")

                    try:
                        bot = _support_bot_controller.get_bot_instance()
                        loop = _support_bot_controller.get_loop()
                        user_chat_id = ticket.get('user_id')
                        if bot and loop and loop.is_running() and user_chat_id:
                            text = f"🔓 Ваш тикет #{ticket_id} снова открыт. Вы можете продолжить переписку."
                            asyncio.run_coroutine_threadsafe(bot.send_message(int(user_chat_id), text), loop)
                    except Exception as e:
                        logger.warning(f"Открытие тикета: не удалось уведомить пользователя {ticket.get('user_id')} об открытии тикета #{ticket_id}: {e}")
                    flash('Тикет открыт.', 'success')
                else:
                    flash('Не удалось открыть тикет.', 'danger')
                return redirect(url_for('support_ticket_page', ticket_id=ticket_id))

        from shop_bot.support_bot.ticket_media import public_support_message

        messages = [public_support_message(m) for m in (get_ticket_messages(ticket_id) or [])]
        common_data = get_common_template_data()
        return render_template('ticket.html', ticket=ticket, messages=messages, **common_data)

    @flask_app.route('/support/<int:ticket_id>/messages.json')
    @login_required
    def support_ticket_messages_api(ticket_id):
        from shop_bot.support_bot.ticket_media import public_support_message

        ticket = get_ticket(ticket_id)
        if not ticket:
            return jsonify({"error": "not_found"}), 404
        items = [public_support_message(m) for m in (get_ticket_messages(ticket_id) or [])]
        return jsonify({
            "ticket_id": ticket_id,
            "status": ticket.get('status'),
            "messages": items
        })

    @flask_app.route('/ticket_files', defaults={'rest': ''}, methods=['GET', 'HEAD', 'POST'])
    @flask_app.route('/ticket_files/<path:rest>', methods=['GET', 'HEAD', 'POST'])
    def block_ticket_files_dir(rest: str):
        abort(404)

    @flask_app.route('/support/ticket-file/<int:message_id>')
    def support_ticket_file(message_id: int):
        """Отдаёт вложение тикета.

        Без сессии панели — глухой 404, не редирект на логин:
        иначе URL сам подсказывает, что файл существует.
        """
        import os
        from flask import send_file, abort
        from shop_bot.data_manager.database import get_support_message, get_ticket_media_root
        from shop_bot.support_bot.ticket_media import (
            detect_image_kind,
            expire_ticket_media_if_closed_ttl,
        )

        if 'logged_in' not in session:
            abort(404)

        msg = get_support_message(message_id)
        if not msg or not msg.get('media'):
            abort(404)

        try:
            if expire_ticket_media_if_closed_ttl(int(msg['ticket_id'])):
                abort(404)
        except Exception:
            logger.exception(
                "TTL вложения тикета %s при отдаче, файл не отдаём",
                msg.get("ticket_id"),
            )
            abort(404)

        base = os.path.realpath(get_ticket_media_root())
        full = os.path.realpath(os.path.join(base, str(msg['media'])))

        # значение из БД не считаем доверенным: путь вида "../../users.db"
        # иначе отдал бы наружу саму базу
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            abort(404)

        kind = detect_image_kind(full)
        if kind is None:
            abort(404)
        _ext, mimetype = kind
        response = send_file(
            full,
            mimetype=mimetype,
            download_name=os.path.basename(full),
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @flask_app.route('/support/<int:ticket_id>/delete', methods=['POST'])
    @login_required
    def delete_support_ticket_route(ticket_id: int):
        ticket = get_ticket(ticket_id)
        if not ticket:
            flash('Тикет не найден.', 'danger')
            return redirect(url_for('support_list_page'))
        try:
            bot = _support_bot_controller.get_bot_instance()
            loop = _support_bot_controller.get_loop()
            forum_chat_id = ticket.get('forum_chat_id')
            thread_id = ticket.get('message_thread_id')
            if bot and loop and loop.is_running() and forum_chat_id and thread_id:
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        bot.delete_forum_topic(chat_id=int(forum_chat_id), message_thread_id=int(thread_id)),
                        loop
                    )
                    fut.result(timeout=5)
                except Exception as e:
                    logger.warning(f"Удаление темы форума не удалось для тикета {ticket_id} (чат {forum_chat_id}, тема {thread_id}): {e}. Пытаюсь закрыть тему как фолбэк.")
                    try:
                        fut2 = asyncio.run_coroutine_threadsafe(
                            bot.close_forum_topic(chat_id=int(forum_chat_id), message_thread_id=int(thread_id)),
                            loop
                        )
                        fut2.result(timeout=5)
                    except Exception as e2:
                        logger.warning(f"Фолбэк-закрытие темы форума также не удалось для тикета {ticket_id}: {e2}")
            else:
                logger.error("Удаление тикета: support-бот или цикл событий недоступны, либо отсутствуют forum_chat_id/message_thread_id; тема не удалена.")
        except Exception as e:
            logger.warning(f"Не удалось обработать удаление темы форума для тикета {ticket_id} перед удалением: {e}")
        if delete_ticket(ticket_id):
            flash(f"Тикет #{ticket_id} удалён.", 'success')
            return redirect(request.referrer or url_for('support_list_page'))
        else:
            flash(f"Не удалось удалить тикет #{ticket_id}.", 'danger')
            return redirect(url_for('support_ticket_page', ticket_id=ticket_id))

    @flask_app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings_page():
        if request.method == 'POST':

            webapp_logo_file = request.files.get('webapp_logo_file')
            if webapp_logo_file and webapp_logo_file.filename:
                try:
                    from werkzeug.utils import secure_filename
                    allowed_ext = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}
                    orig_name = secure_filename(webapp_logo_file.filename)
                    ext = os.path.splitext(orig_name)[1].lower()
                    if ext not in allowed_ext:
                        flash('Недопустимый формат логотипа. Разрешены: png, jpg, jpeg, webp, gif, svg.', 'danger')
                    else:
                        uploads_dir = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'webapp', 'uploads'
                        )
                        os.makedirs(uploads_dir, exist_ok=True)
                        dest_filename = f"webapp_logo{ext}"
                        dest_path = os.path.join(uploads_dir, dest_filename)
                        webapp_logo_file.save(dest_path)
                        version = int(datetime.now().timestamp())
                        update_setting('webapp_logo', f"/uploads/{dest_filename}?v={version}")
                except Exception as e:
                    logger.error(f"Не удалось сохранить логотип Webapp: {e}", exc_info=True)
                    flash('Не удалось сохранить загруженный логотип.', 'danger')

            if 'panel_password' in request.form and request.form.get('panel_password'):
                try:
                    raw_pass = request.form.get('panel_password') or ''
                    new_hash = bcrypt.hashpw(raw_pass.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    update_setting('panel_password', new_hash)
                except Exception as e:
                    logger.error(f"Не удалось обновить пароль панели: {e}", exc_info=True)


            
            checkbox_keys = [
                "enable_referrals",
                "enable_referral_days_bonus",
                "force_subscription",
                "key_info_show_connect_device",
                "key_info_show_howto",
                "payment_email_prompt_enabled",
                "auto_start_main_bot",
                "auto_start_support_bot",
                "monitoring_enabled",
                "sbp_enabled",
                "stars_enabled",
                "trial_enabled",
                "yoomoney_enabled",
                "franchise_enabled",
                "franchise_menu_button_visible",
                "webapp_enabled",
                "auto_renew_globally_enabled",
                "smtp_use_tls",
            ]
            for checkbox_key in checkbox_keys:
                values = request.form.getlist(checkbox_key) or ['off']
                raw = values[-1]
                value = 'true' if str(raw).lower() in ('on','true','1','yes') else 'false'
                update_setting(checkbox_key, value)

            try:
                _apply_franchise_runtime(franchise_settings())
            except Exception as e:
                logger.warning(f"Не удалось применить франшизу после сохранения настроек: {e}")

            for key in ALL_SETTINGS_KEYS:
                if key in checkbox_keys or key == 'panel_password' or key == 'panel_totp_enabled':
                    continue
                if key == 'smtp_password' and not (request.form.get(key) or '').strip():
                    # Пустое поле пароля SMTP при сохранении не должно затирать уже сохранённый пароль.
                    continue
                if key == 'remnawave_api_token' and not (request.form.get(key) or '').strip():
                    continue
                if key == 'panel_totp_secret':
                    continue
                if key in SECRET_SETTING_KEYS and not (request.form.get(key) or '').strip():
                    continue
                if key in request.form:
                    update_setting(key, request.form.get(key))

            want_totp = False
            totp_box = request.form.getlist('panel_totp_enabled') or ['off']
            want_totp = str(totp_box[-1]).lower() in ('on', 'true', '1', 'yes')
            was_totp = str(get_setting('panel_totp_enabled') or '').lower() in ('1', 'true', 'yes', 'on')
            totp_secret = decrypt_managed_bot_token(get_setting('panel_totp_secret') or '')
            if want_totp:
                if not totp_secret:
                    totp_secret = pyotp.random_base32()
                    update_setting('panel_totp_secret', encrypt_managed_bot_token(totp_secret))
                confirm = (request.form.get('panel_totp_confirm') or '').strip()
                if was_totp:
                    update_setting('panel_totp_enabled', 'true')
                elif totp_secret and pyotp.TOTP(totp_secret).verify(confirm, valid_window=1):
                    update_setting('panel_totp_enabled', 'true')
                    flash('TOTP включён. Дальше для входа нужен код из приложения.', 'success')
                else:
                    update_setting('panel_totp_enabled', 'false')
                    flash(
                        'Отсканируйте QR в приложении на телефоне (или введите секрет вручную) '
                        'и сохраните настройки с кодом из приложения — тогда TOTP включится.',
                        'warning',
                    )
            else:
                update_setting('panel_totp_enabled', 'false')

            flash('Настройки сохранены.', 'success')
            next_hash = (request.form.get('next_hash') or '').strip() or '#panel'
            next_tab = (next_hash[1:] if next_hash.startswith('#') else next_hash) or 'panel'
            return redirect(url_for('settings_page', tab=next_tab))

        current_settings = get_all_settings()
        try:
            seed_global_remnawave_from_hosts()
            current_settings = get_all_settings()
        except Exception:
            pass
        hosts = get_all_hosts()
        try:
            remnawave_squads = get_remnawave_squads()
        except Exception:
            remnawave_squads = []
        for sq in remnawave_squads:
            cls = str(sq.get("squad_class") or "").strip().lower()
            if cls == "lte":
                name = squad_display_label(sq)
                sq["class_badge"] = f"{name} 💰"
                sq["class_badge_compact"] = name
            elif cls == "base":
                sq["class_badge"] = "BASE ∞"
                sq["class_badge_compact"] = "BASE"
            else:
                sq["class_badge"] = "OTHER"
                sq["class_badge_compact"] = "OTHER"
        for host in hosts:
            host['plans'] = get_plans_for_host(host['host_name'])
            for plan in host['plans']:
                # Пулы докупки раздельные: 'main' (основной трафик) и 'lte' (💰 premium-ноды).
                # Раньше здесь читался только main, поэтому LTE-пакеты, созданные в
                # Telegram-админке, были не видны, а форма добавления писала в main — и
                # докупка LTE у пользователей отвечала «пакеты не настроены».
                try:
                    plan['traffic_packages'] = get_traffic_packages_for_plan(plan['plan_id'], pool='main')
                except Exception:
                    plan['traffic_packages'] = []
                try:
                    plan['lte_traffic_packages'] = get_traffic_packages_for_plan(plan['plan_id'], pool='lte')
                except Exception:
                    plan['lte_traffic_packages'] = []

            try:
                host['latest_speedtest'] = get_latest_speedtest(host['host_name'])
            except Exception:
                host['latest_speedtest'] = None

            try:
                host['squads'] = get_host_squads(host['host_name'])
            except Exception:
                host['squads'] = []
            host['lte_label'] = get_lte_squad_display_label(host.get('host_name'))
            try:
                host['selected_squad_ids'] = set(get_host_selected_squad_catalog_ids(host['host_name']))
            except Exception:
                host['selected_squad_ids'] = set()
            # Результат последней проверки пересечения сквадов — из БД, без обращения к панели
            # на каждый рендер страницы.
            try:
                host['squad_node_overlap'] = get_host_squad_overlap(host['host_name'])
            except Exception:
                host['squad_node_overlap'] = []

        try:
            ssh_targets = get_all_ssh_targets()
        except Exception:
            ssh_targets = []
        

        backups = []
        try:
            from pathlib import Path
            bdir = backup_manager.BACKUPS_DIR
            for p in sorted(bdir.glob('db-backup-*.zip'), key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    st = p.stat()
                    backups.append({
                        'name': p.name,
                        'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'),
                        'size': st.st_size
                    })
                except Exception:
                    pass
        except Exception:
            backups = []

        common_data = get_common_template_data()
        common_data['hosts'] = hosts
        totp_qr_data_uri = ""
        totp_secret_display = ""
        totp_plain = decrypt_managed_bot_token(current_settings.get("panel_totp_secret") or "")
        if totp_plain:
            totp_secret_display = totp_plain
            issuer = (current_settings.get("panel_brand_title") or "Xatabchik").strip() or "Xatabchik"
            account = (current_settings.get("panel_login") or "admin").strip() or "admin"
            provisioning_uri = pyotp.TOTP(totp_plain).provisioning_uri(
                name=account, issuer_name=issuer
            )
            try:
                import qrcode
                from io import BytesIO
                buf = BytesIO()
                qrcode.make(provisioning_uri).save(buf, format="PNG")
                totp_qr_data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception as e:
                logger.warning(f"Не удалось сгенерировать QR для TOTP панели: {e}")
        return render_template(
            'settings.html',
            settings=current_settings,
            ssh_targets=ssh_targets,
            backups=backups,
            remnawave_squads=remnawave_squads,
            totp_qr_data_uri=totp_qr_data_uri,
            totp_secret_display=totp_secret_display,
            **common_data,
        )


    def _as_bool(value: str | None) -> bool:
        return str(value or "").strip().lower() in ("1", "true", "yes", "on")

    def _get_module_info(module_id: str) -> dict | None:
        for item in module_loader.list_modules():
            if item.get("id") == module_id:
                return item
        return None

    def _build_module_settings_form(module_id: str) -> list[dict]:
        schema = module_loader.get_settings_schema(module_id)
        if not schema:
            return []
        values = module_loader.get_settings_values(module_id)
        items: list[dict] = []
        for item in schema:
            key = item.get("key")
            if not key:
                continue
            full_key = f"{module_id}_{key}"
            raw_value = values.get(full_key)
            if raw_value is None:
                raw_value = item.get("default")
            field_type = (item.get("type") or "text").strip().lower()
            if field_type == "boolean":
                value = _as_bool(raw_value)
            else:
                value = "" if raw_value is None else raw_value
            items.append({
                "key": key,
                "full_key": full_key,
                "label": item.get("label") or key,
                "type": field_type,
                "value": value,
            })
        return items

    @flask_app.route('/modules/', methods=['GET'])
    @login_required
    def modules_page():
        modules = module_loader.list_modules()
        common_data = get_common_template_data()
        return render_template('modules.html', modules=modules, **common_data)

    @flask_app.route('/modules/<module_id>/enable', methods=['POST'])
    @login_required
    def module_enable_route(module_id: str):
        ok, message = module_loader.enable_module(module_id)
        flash(message, 'success' if ok else 'danger')
        return redirect(url_for('modules_page'))

    @flask_app.route('/modules/<module_id>/disable', methods=['POST'])
    @login_required
    def module_disable_route(module_id: str):
        ok, message = module_loader.disable_module(module_id)
        flash(message, 'success' if ok else 'danger')
        return redirect(url_for('modules_page'))

    @flask_app.route('/modules/<module_id>/delete', methods=['POST'])
    @login_required
    def module_delete_route(module_id: str):
        ok, message = module_loader.delete_module(module_id)
        flash(message, 'success' if ok else 'danger')
        return redirect(url_for('modules_page'))

    @flask_app.route('/modules/<module_id>/settings', methods=['GET', 'POST'])
    @login_required
    def module_settings_page(module_id: str):
        module_info = _get_module_info(module_id)
        if not module_info:
            flash('Модуль не найден.', 'danger')
            return redirect(url_for('modules_page'))
        if request.method == 'POST':
            schema = module_loader.get_settings_schema(module_id)
            for item in schema:
                key = item.get("key")
                if not key:
                    continue
                full_key = f"{module_id}_{key}"
                field_type = (item.get("type") or "text").strip().lower()
                if field_type == "boolean":
                    value = 'true' if _as_bool(request.form.get(full_key)) else 'false'
                else:
                    value = request.form.get(full_key, "")
                update_setting(full_key, value)
            flash('Настройки модуля сохранены.', 'success')
            return redirect(url_for('module_settings_page', module_id=module_id))

        settings_items = _build_module_settings_form(module_id)
        if not settings_items:
            flash('У этого модуля нет настроек.', 'warning')
            return redirect(url_for('modules_page'))

        common_data = get_common_template_data()
        return render_template(
            'module_settings.html',
            module=module_info,
            settings_items=settings_items,
            **common_data,
        )

    @flask_app.route('/modules/<module_id>/', defaults={'subpath': ''}, methods=['GET', 'POST'])
    @flask_app.route('/modules/<module_id>/<path:subpath>', methods=['GET', 'POST'])
    @login_required
    def module_page_proxy(module_id: str, subpath: str = ''):
        """Proxy request to module's panel routes if they exist."""
        from flask import request
        
        # Check if module has registered routes
        if not hasattr(flask_app, '_module_route_registry'):
            common_data = get_common_template_data()
            return render_template(
                'module_page_placeholder.html',
                module_id=module_id,
                subpath=subpath,
                message='Модуль не имеет панели (blueprint не зарегистрирован).',
                **common_data,
            )
        
        view_functions = flask_app._module_route_registry.get(module_id)
        if not view_functions:
            common_data = get_common_template_data()
            return render_template(
                'module_page_placeholder.html',
                module_id=module_id,
                subpath=subpath,
                message='Модуль не имеет панели.',
                **common_data,
            )
        
        # Determine which view function to call
        # For root path "/" use "index", for "/payouts/delete" try "payouts_delete", etc.
        if not subpath or subpath == '':
            func_name = 'index'
        else:
            # Try full path with slashes replaced by underscores first
            # "/payouts/delete" -> "payouts_delete"
            func_name = subpath.strip('/').replace('/', '_')
        
        # Get view function - try exact match first
        view_func = view_functions.get(func_name)
        
        # If not found and path has segments, try first segment only
        if not view_func and '/' in subpath:
            func_name = subpath.strip('/').split('/')[0]
            view_func = view_functions.get(func_name)
        
        if view_func:
            # Call the view function with app context and inject common template data
            # Temporarily wrap render_template to add context processor data
            import flask as flask_module
            original_render_template = flask_module.render_template
            
            def wrapped_render_template(template_name_or_list, **kwargs):
                # Inject context from context_processor
                context_data = inject_current_year()
                # Merge: kwargs override context_data
                merged = {**context_data, **kwargs}
                return original_render_template(template_name_or_list, **merged)
            
            # Temporarily replace render_template
            flask_module.render_template = wrapped_render_template
            try:
                result = view_func()
            finally:
                # Restore original render_template
                flask_module.render_template = original_render_template
            
            return result
        
        # Debug info
        available = list(view_functions.keys())
        common_data = get_common_template_data()
        return render_template(
            'module_page_placeholder.html',
            module_id=module_id,
            subpath=subpath,
            message=f'Функция "{func_name}" не найдена. Доступные: {available}',
            **common_data,
        )

    @flask_app.route('/modules/upload', methods=['POST'])
    @login_required
    def module_upload_route():
        """Upload and install a module from ZIP file."""
        from werkzeug.utils import secure_filename
        import tempfile
        from pathlib import Path
        from shop_bot.core.module_loader import MAX_MODULE_ZIP_BYTES
        
        # Check if file is present
        if 'module_file' not in request.files:
            flash('Файл модуля не выбран.', 'danger')
            return redirect(url_for('modules_page'))
        
        file = request.files['module_file']
        if not file or file.filename == '':
            flash('Файл модуля не выбран.', 'danger')
            return redirect(url_for('modules_page'))
        
        # Validate file extension
        if not file.filename.lower().endswith('.zip'):
            flash('Файл должен быть ZIP архивом.', 'danger')
            return redirect(url_for('modules_page'))

        # Reject oversized uploads early when Content-Length is present.
        content_length = request.content_length
        if content_length is not None and content_length > MAX_MODULE_ZIP_BYTES + (1024 * 1024):
            flash('Файл слишком большой (макс. 10 МБ).', 'danger')
            return redirect(url_for('modules_page'))
        
        # Save to temporary file
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_zip = Path(tmpdir) / secure_filename(file.filename)
                file.save(str(tmp_zip))
                if tmp_zip.stat().st_size > MAX_MODULE_ZIP_BYTES:
                    flash('Файл слишком большой (макс. 10 МБ).', 'danger')
                    return redirect(url_for('modules_page'))
                
                # Import module from ZIP
                ok, message = module_loader.import_module_from_zip(tmp_zip, auto_enable=True)
                
                if ok:
                    flash(f'✅ {message}', 'success')
                else:
                    flash(f'❌ Ошибка: {message}', 'danger')
        except Exception as e:
            logger.error(f"Module upload error: {e}", exc_info=True)
            flash(f'❌ Ошибка загрузки: {e}', 'danger')
        
        return redirect(url_for('modules_page'))

    @flask_app.route('/admin/ssh-targets/create', methods=['POST'])
    @login_required
    def create_ssh_target_route():
        name = (request.form.get('target_name') or '').strip()
        ssh_host = (request.form.get('ssh_host') or '').strip()
        ssh_port = request.form.get('ssh_port')
        ssh_user = (request.form.get('ssh_user') or '').strip() or None
        ssh_password = request.form.get('ssh_password')
        ssh_key_path = (request.form.get('ssh_key_path') or '').strip() or None
        description = (request.form.get('description') or '').strip() or None
        try:
            ssh_port_val = int(ssh_port) if ssh_port else 22
        except Exception:
            ssh_port_val = 22
        if not name or not ssh_host:
            flash('Укажите имя цели и SSH хост.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))
        ok = create_ssh_target(
            target_name=name,
            ssh_host=ssh_host,
            ssh_port=ssh_port_val,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            ssh_key_path=ssh_key_path,
            description=description,
        )
        flash('SSH-цель добавлена.' if ok else 'Не удалось добавить SSH-цель.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/admin/ssh-targets/<target_name>/update', methods=['POST'])
    @login_required
    def update_ssh_target_route(target_name: str):
        ssh_host = (request.form.get('ssh_host') or '').strip() if 'ssh_host' in request.form else None
        ssh_port_raw = (request.form.get('ssh_port') or '').strip() if 'ssh_port' in request.form else None
        ssh_user = (request.form.get('ssh_user') or '').strip() if 'ssh_user' in request.form else None
        raw_ssh_password = request.form.get('ssh_password') if 'ssh_password' in request.form else None
        ssh_password = (raw_ssh_password or '').strip() or None
        ssh_key_path = (request.form.get('ssh_key_path') or '').strip() if 'ssh_key_path' in request.form else None
        description = (request.form.get('description') or '').strip() if 'description' in request.form else None
        try:
            ssh_port = int(ssh_port_raw) if ssh_port_raw else None
        except Exception:
            ssh_port = None
        ok = update_ssh_target_fields(
            target_name,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            ssh_key_path=ssh_key_path,
            description=description,
        )
        flash('SSH-цель обновлена.' if ok else 'Не удалось обновить SSH-цель.', 'success' if ok else 'danger')
        return redirect(request.referrer or url_for('settings_page', tab='hosts'))

    @flask_app.route('/admin/ssh-targets/<target_name>/delete', methods=['POST'])
    @login_required
    def delete_ssh_target_route(target_name: str):
        ok = delete_ssh_target(target_name)
        flash('SSH-цель удалена.' if ok else 'Не удалось удалить SSH-цель.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    

    @flask_app.route('/admin/ssh-targets/<target_name>/speedtest/install', methods=['POST'])
    @login_required
    def auto_install_speedtest_on_target_route(target_name: str):
        accept_new = str(request.form.get("accept_new_host_key") or "").strip().lower() in (
            "1", "true", "on", "yes",
        )
        try:
            res = asyncio.run(
                speedtest_runner.auto_install_speedtest_on_target(
                    target_name, accept_new_host_key=accept_new
                )
            )
        except Exception as e:
            res = {'ok': False, 'log': str(e)}
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": bool(res.get('ok')), "log": res.get('log')})
        flash(('Установка завершена успешно.' if res.get('ok') else 'Не удалось установить speedtest на цель.') , 'success' if res.get('ok') else 'danger')
        try:
            log = res.get('log') or ''
            short = '\n'.join((log.splitlines() or [])[-20:])
            if short:
                flash(short, 'secondary')
        except Exception:
            pass
        return redirect(request.referrer or url_for('settings_page', tab='hosts'))


    @flask_app.route('/settings/smtp/test', methods=['POST'])
    @login_required
    def smtp_test_route():
        for key in ("smtp_host", "smtp_port", "smtp_user", "smtp_from_email"):
            if key in request.form:
                update_setting(key, request.form.get(key))
        if (request.form.get('smtp_password') or '').strip():
            update_setting('smtp_password', request.form.get('smtp_password'))
        use_tls_raw = request.form.get('smtp_use_tls')
        update_setting('smtp_use_tls', 'true' if str(use_tls_raw or '').lower() in ('on', 'true', '1', 'yes') else 'false')

        to_email = (request.form.get('smtp_test_email') or '').strip()
        if not to_email:
            flash('Укажите адрес для тестового письма.', 'danger')
            return redirect(url_for('settings_page', tab='email'))

        try:
            from shop_bot.modules.email_sender import send_activation_code, is_smtp_configured
            if not is_smtp_configured():
                flash('Заполните host/логин/пароль SMTP перед проверкой.', 'danger')
                return redirect(url_for('settings_page', tab='email'))

            ok = send_activation_code(to_email, "000000")
            if ok:
                flash(f'Тестовое письмо успешно отправлено на {to_email}.', 'success')
            else:
                flash(
                    'Не удалось отправить тестовое письмо — проверьте логи сервера для подробностей '
                    '(частая причина: неверный логин/пароль или для этого провайдера нужен '
                    '«пароль для внешних приложений»).',
                    'danger',
                )
        except Exception as e:
            logger.error(f"Ошибка при тестовой отправке SMTP письма: {e}", exc_info=True)
            flash('Ошибка при отправке тестового письма.', 'danger')

        return redirect(url_for('settings_page', tab='email'))

    @flask_app.route('/admin/db/backup', methods=['POST'])
    @login_required
    def backup_db_route():
        try:
            zip_path = backup_manager.create_backup_file()
            if not zip_path or not os.path.isfile(zip_path):
                flash('Не удалось создать бэкап БД.', 'danger')
                return redirect(request.referrer or url_for('settings_page', tab='panel'))

            return send_file(str(zip_path), as_attachment=True, download_name=os.path.basename(zip_path))
        except Exception as e:
            logger.error(f"Ошибка резервного копирования БД: {e}")
            flash('Ошибка при создании бэкапа.', 'danger')
            return redirect(request.referrer or url_for('settings_page', tab='panel'))

    @flask_app.route('/admin/db/restore', methods=['POST'])
    @login_required
    def restore_db_route():
        try:

            existing = (request.form.get('existing_backup') or '').strip()
            ok = False
            if existing:

                base = backup_manager.BACKUPS_DIR
                candidate = (base / existing).resolve()
                if str(candidate).startswith(str(base.resolve())) and os.path.isfile(candidate):
                    ok = backup_manager.restore_from_file(candidate)
                else:
                    flash('Выбранный бэкап не найден.', 'danger')
                    return redirect(request.referrer or url_for('settings_page', tab='panel'))
            else:

                file = request.files.get('db_file')
                if not file or file.filename == '':
                    flash('Файл для восстановления не выбран.', 'warning')
                    return redirect(request.referrer or url_for('settings_page', tab='panel'))
                filename = file.filename.lower()
                if not (filename.endswith('.zip') or filename.endswith('.db')):
                    flash('Поддерживаются только файлы .zip или .db', 'warning')
                    return redirect(request.referrer or url_for('settings_page', tab='panel'))
                ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
                dest_dir = backup_manager.BACKUPS_DIR
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                dest_path = dest_dir / f"uploaded-{ts}-{os.path.basename(filename)}"
                file.save(dest_path)
                ok = backup_manager.restore_from_file(dest_path)
            if ok:
                flash('Восстановление выполнено успешно.', 'success')
            else:
                flash('Восстановление не удалось. Проверьте файл и повторите.', 'danger')
            return redirect(request.referrer or url_for('settings_page', tab='panel'))
        except Exception as e:
            logger.error(f"Ошибка восстановления БД: {e}", exc_info=True)
            flash('Ошибка при восстановлении БД.', 'danger')
            return redirect(request.referrer or url_for('settings_page', tab='panel'))

    @flask_app.route('/settings/remnawave', methods=['POST'])
    @login_required
    def update_remnawave_settings_route():
        base_url = (request.form.get('remnawave_base_url') or '').strip()
        api_token = (request.form.get('remnawave_api_token') or '').strip()
        sub_url = (request.form.get('remnawave_subscription_url') or '').strip()

        update_setting('remnawave_base_url', base_url)
        if api_token:
            update_setting('remnawave_api_token', api_token)
        update_setting('remnawave_subscription_url', sub_url)

        synced = 0
        try:
            synced = apply_global_remnawave_to_hosts()
        except Exception as e:
            logger.error(f"apply_global_remnawave_to_hosts failed: {e}")
            flash('Настройки Remnawave сохранены, но синхронизация на хосты не удалась.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))

        flash(f'Настройки Remnawave сохранены и применены к хостам ({synced}).', 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/add-remnawave-squad', methods=['POST'])
    @login_required
    def add_remnawave_squad_route():
        squad_uuid = (request.form.get('squad_uuid') or '').strip()
        squad_class = (request.form.get('squad_class') or 'base').strip().lower()
        label = (request.form.get('label') or '').strip()
        if not squad_uuid:
            flash('Укажите Squad UUID.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))
        squad_id = add_remnawave_squad(squad_uuid, squad_class, label or None)
        flash('Сквад добавлен в каталог.' if squad_id else 'Не удалось добавить сквад (возможно, такой UUID уже есть).', 'success' if squad_id else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/delete-remnawave-squad/<int:squad_id>', methods=['POST'])
    @login_required
    def delete_remnawave_squad_route(squad_id: int):
        ok = delete_remnawave_squad(squad_id)
        flash('Сквад удалён из каталога.' if ok else 'Не удалось удалить сквад.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/update-host-squad-selection', methods=['POST'])
    @login_required
    def update_host_squad_selection_route():
        host_name = (request.form.get('host_name') or '').strip()
        if not host_name:
            flash('Не указан хост.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))
        raw_ids = request.form.getlist('squad_ids')
        catalog_ids: list[int] = []
        for value in raw_ids:
            try:
                catalog_ids.append(int(value))
            except Exception:
                continue
        ok = set_host_squads_from_catalog(host_name, catalog_ids)
        flash('Сквады хоста обновлены.' if ok else 'Не удалось обновить сквады хоста.', 'success' if ok else 'danger')
        if ok:
            # Пересечение нод LTE- и base-сквада не блокирует сохранение, но админ должен
            # знать: трафик таких нод попадёт в LTE-пул, хотя их же отдаёт base-сквад.
            try:
                overlap = asyncio.run(remnawave_api.refresh_host_squad_overlap(host_name))
            except Exception as e:
                overlap = []
                logger.warning(f"Проверка пересечения сквадов хоста '{host_name}' не удалась: {e}")
            if overlap:
                nodes_txt = ', '.join(f"{n.get('node_name') or '—'} ({n.get('uuid')})" for n in overlap)
                flash(
                    f"⚠️ Ноды доступны и через LTE-, и через base-сквад: {nodes_txt}. "
                    "Их трафик будет засчитываться в LTE-пул — исправляется настройкой "
                    "inbound'ов сквадов в Remnawave.",
                    'warning',
                )
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/update-host-subscription', methods=['POST'])
    @login_required
    def update_host_subscription_route():
        host_name = (request.form.get('host_name') or '').strip()
        sub_url = (request.form.get('host_subscription_url') or '').strip()
        if not host_name:
            flash('Не указан хост для обновления ссылки подписки.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))
        ok = update_host_subscription_url(host_name, sub_url or None)
        if ok:
            flash('Ссылка подписки для хоста обновлена.', 'success')
        else:
            flash('Не удалось обновить ссылку подписки для хоста (возможно, хост не найден).', 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/update-host-url', methods=['POST'])
    @login_required
    def update_host_url_route():
        host_name = (request.form.get('host_name') or '').strip()
        new_url = (request.form.get('host_url') or '').strip()
        if not host_name or not new_url:
            flash('Укажите имя хоста и новый URL.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))
        ok = update_host_url(host_name, new_url)
        flash('URL хоста обновлён.' if ok else 'Не удалось обновить URL хоста.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/update-host-remnawave', methods=['POST'])
    @login_required
    def update_host_remnawave_route():
        host_name = (request.form.get('host_name') or '').strip()
        base_url = (request.form.get('remnawave_base_url') or '').strip()
        api_token = (request.form.get('remnawave_api_token') or '').strip()
        squad_uuid = (request.form.get('squad_uuid') or '').strip()
        if not host_name:
            flash('Не указан хост для обновления Remnawave-настроек.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))
        ok = update_host_remnawave_settings(
            host_name,
            remnawave_base_url=base_url or None,
            remnawave_api_token=api_token or None,
            squad_uuid=squad_uuid or None,
        )
        flash('Remnawave-настройки обновлены.' if ok else 'Не удалось обновить Remnawave-настройки.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/add-host-squad', methods=['POST'])
    @login_required
    def add_host_squad_route():
        host_name = (request.form.get('host_name') or '').strip()
        squad_uuid = (request.form.get('squad_uuid') or '').strip()
        squad_class = (request.form.get('squad_class') or 'base').strip().lower()
        label = (request.form.get('label') or '').strip()
        if not host_name or not squad_uuid:
            flash('Укажите host и Squad UUID.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))
        squad_id = add_host_squad(host_name, squad_uuid, squad_class, label or None)
        flash('Сквад добавлен.' if squad_id else 'Не удалось добавить сквад (возможно, уже есть активный сквад этого класса или дубликат UUID).', 'success' if squad_id else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/toggle-host-squad/<int:squad_id>', methods=['POST'])
    @login_required
    def toggle_host_squad_route(squad_id: int):
        is_active = (request.form.get('is_active') or '1') == '1'
        ok = set_host_squad_active(squad_id, is_active)
        flash('Статус сквада обновлён.' if ok else 'Не удалось обновить статус сквада.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/delete-host-squad/<int:squad_id>', methods=['POST'])
    @login_required
    def delete_host_squad_route(squad_id: int):
        ok = delete_host_squad(squad_id)
        flash('Сквад удалён.' if ok else 'Не удалось удалить сквад.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/rename-host', methods=['POST'])
    @login_required
    def rename_host_route():
        old_name = (request.form.get('old_host_name') or '').strip()
        new_name = (request.form.get('new_host_name') or '').strip()
        if not old_name or not new_name:
            flash('Введите старое и новое имя хоста.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))
        ok = update_host_name(old_name, new_name)
        flash('Имя хоста обновлено.' if ok else 'Не удалось переименовать хост.', 'success' if ok else 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/start-support-bot', methods=['POST'])
    @login_required
    def start_support_bot_route():
        result = _support_bot_controller.start()
        flash(result['message'], 'success' if result['status'] == 'success' else 'danger')
        return redirect(request.referrer or url_for('settings_page'))

    def _wait_for_stop(controller, timeout: float = 5.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            status = controller.get_status() or {}
            if not status.get('is_running'):
                return True
            time.sleep(0.1)
        return False

    @flask_app.route('/stop-support-bot', methods=['POST'])
    @login_required
    def stop_support_bot_route():
        result = _support_bot_controller.stop()
        _wait_for_stop(_support_bot_controller)
        flash(result['message'], 'success' if result['status'] == 'success' else 'danger')
        return redirect(request.referrer or url_for('settings_page'))

    @flask_app.route('/start-bot', methods=['POST'])
    @login_required
    def start_bot_route():
        result = _bot_controller.start()
        flash(result['message'], 'success' if result['status'] == 'success' else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/stop-bot', methods=['POST'])
    @login_required
    def stop_bot_route():
        result = _bot_controller.stop()
        _wait_for_stop(_bot_controller)
        flash(result['message'], 'success' if result['status'] == 'success' else 'danger')
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/stop-both-bots', methods=['POST'])
    @login_required
    def stop_both_bots_route():
        main_result = _bot_controller.stop()
        support_result = _support_bot_controller.stop()

        statuses = []
        categories = []
        for name, res in [('Основной бот', main_result), ('Support-бот', support_result)]:
            if res.get('status') == 'success':
                statuses.append(f"{name}: остановлен")
                categories.append('success')
            else:
                statuses.append(f"{name}: ошибка — {res.get('message')}")
                categories.append('danger')
        _wait_for_stop(_bot_controller)
        _wait_for_stop(_support_bot_controller)
        category = 'danger' if 'danger' in categories else 'success'
        flash(' | '.join(statuses), category)
        return redirect(request.referrer or url_for('dashboard_page'))

    def _soft_stop_controller(controller):
        """Остановить контроллер; если уже остановлен — считать успехом (для перезапуска)."""
        status = controller.get_status() or {}
        if not status.get('is_running'):
            return {"status": "success", "message": "уже остановлен"}
        return controller.stop()

    @flask_app.route('/restart-both-bots', methods=['POST'])
    @login_required
    def restart_both_bots_route():
        """Остановить оба бота, дождаться остановки и сразу запустить снова — без ручного stop→start."""
        _soft_stop_controller(_bot_controller)
        _soft_stop_controller(_support_bot_controller)
        _wait_for_stop(_bot_controller, timeout=8.0)
        _wait_for_stop(_support_bot_controller, timeout=8.0)
        # Небольшая пауза, чтобы polling/сокеты успели освободиться перед новым start.
        time.sleep(0.5)

        main_result = _bot_controller.start()
        support_result = _support_bot_controller.start()

        statuses = []
        categories = []
        for name, res in [('Основной бот', main_result), ('Support-бот', support_result)]:
            if res.get('status') == 'success':
                statuses.append(f"{name}: перезапущен")
                categories.append('success')
            else:
                statuses.append(f"{name}: ошибка — {res.get('message')}")
                categories.append('danger')
        category = 'danger' if 'danger' in categories else 'success'
        flash(' | '.join(statuses), category)
        return redirect(request.referrer or url_for('dashboard_page'))

    @flask_app.route('/start-both-bots', methods=['POST'])
    @login_required
    def start_both_bots_route():
        main_result = _bot_controller.start()
        support_result = _support_bot_controller.start()

        statuses = []
        categories = []
        for name, res in [('Основной бот', main_result), ('Support-бот', support_result)]:
            if res.get('status') == 'success':
                statuses.append(f"{name}: запущен")
                categories.append('success')
            else:
                statuses.append(f"{name}: ошибка — {res.get('message')}")
                categories.append('danger')
        category = 'danger' if 'danger' in categories else 'success'
        flash(' | '.join(statuses), category)
        return redirect(request.referrer or url_for('settings_page'))

    @flask_app.route('/users/ban/<int:user_id>', methods=['POST'])
    @login_required
    def ban_user_route(user_id):
        ban_user(user_id)
        flash(f'Пользователь {user_id} был заблокирован.', 'success')

        try:
            bot = _bot_controller.get_bot_instance()
            if bot:
                text = "🚫 Ваш аккаунт заблокирован администратором. Если это ошибка — напишите в поддержку."

                try:
                    support = (get_setting("support_bot_username") or get_setting("support_user") or "").strip()
                except Exception:
                    support = ""
                kb = InlineKeyboardBuilder()
                url: str | None = None
                if support:
                    if support.startswith("@"):
                        url = f"tg://resolve?domain={support[1:]}"
                    elif support.startswith("tg://"):
                        url = support
                    elif support.startswith("http://") or support.startswith("https://"):
                        try:
                            part = support.split("/")[-1].split("?")[0]
                            if part:
                                url = f"tg://resolve?domain={part}"
                        except Exception:
                            url = support
                    else:
                        url = f"tg://resolve?domain={support}"
                if url:
                    kb.button(text="🆘 Написать в поддержку", url=url)
                else:
                    kb.button(text="🆘 Поддержка", callback_data="show_help")
                loop = _bot_controller.get_loop()
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        bot.send_message(chat_id=user_id, text=text, reply_markup=kb.as_markup()),
                        loop
                    )
                else:
                    asyncio.run(bot.send_message(chat_id=user_id, text=text, reply_markup=kb.as_markup()))
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о бане пользователю {user_id}: {e}")
        return redirect(url_for('users_page'))

    @flask_app.route('/users/unban/<int:user_id>', methods=['POST'])
    @login_required
    def unban_user_route(user_id):
        unban_user(user_id)
        flash(f'Пользователь {user_id} был разблокирован.', 'success')

        try:
            bot = _bot_controller.get_bot_instance()
            if bot:
                kb = InlineKeyboardBuilder()
                kb.row(keyboards.get_main_menu_button())
                text = "✅ Доступ к аккаунту восстановлен администратором."
                loop = _bot_controller.get_loop()
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        bot.send_message(chat_id=user_id, text=text, reply_markup=kb.as_markup()),
                        loop
                    )
                else:
                    asyncio.run(bot.send_message(chat_id=user_id, text=text, reply_markup=kb.as_markup()))
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о разбане пользователю {user_id}: {e}")
        return redirect(url_for('users_page'))

    @flask_app.route('/users/delete/<int:user_id>', methods=['POST'])
    @login_required
    def delete_user_route(user_id):
        """Полное удаление пользователя (как admin_delete_user в боте).

        Дополнительно best-effort удаляет клиентов с хостов Remnawave, чтобы
        не оставлять «осиротевшие» ключи на панели.
        """
        user = get_user(user_id)
        if not user:
            wants_json = (
                'application/json' in (request.headers.get('Accept') or '')
                or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            )
            message = f'Пользователь {user_id} не найден.'
            if wants_json:
                return jsonify({"ok": False, "message": message}), 404
            flash(message, 'danger')
            return redirect(url_for('users_page'))

        keys_to_revoke = get_user_keys(user_id) or []
        for key in keys_to_revoke:
            try:
                asyncio.run(remnawave_api.delete_client_on_host(key.get('host_name'), key.get('key_email')))
            except Exception as e:
                logger.warning(
                    "delete_user_route: failed to delete key %s on host %s: %s",
                    key.get('key_id'), key.get('host_name'), e,
                )

        try:
            ok = bool(delete_user_completely(user_id))
        except Exception:
            logger.exception("Failed to delete user %s completely from admin panel", user_id)
            ok = False

        wants_json = (
            'application/json' in (request.headers.get('Accept') or '')
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )
        if ok:
            message = f'Пользователь {user_id} и все связанные данные удалены.'
            if wants_json:
                return jsonify({"ok": True, "message": message, "deleted_user_id": user_id}), 200
            flash(message, 'success')
            return redirect(url_for('users_page'))

        message = f'Не удалось удалить пользователя {user_id}. Подробности см. в логах.'
        if wants_json:
            return jsonify({"ok": False, "message": message}), 500
        flash(message, 'danger')
        return redirect(url_for('users_page'))

    @flask_app.route('/users/revoke/<int:user_id>', methods=['POST'])
    @login_required
    def revoke_keys_route(user_id):
        keys_to_revoke = get_user_keys(user_id)
        success_count = 0
        total = len(keys_to_revoke)

        for key in keys_to_revoke:
            result = asyncio.run(remnawave_api.delete_client_on_host(key['host_name'], key['key_email']))
            if result:
                success_count += 1


        delete_user_keys(user_id)


        try:
            bot = _bot_controller.get_bot_instance()
            if bot:
                text = (
                    "❌ Ваши VPN‑ключи были отозваны администратором.\n"
                    f"Всего ключей: {total}\n"
                    f"Отозвано: {success_count}"
                )
                loop = _bot_controller.get_loop()
                if loop and loop.is_running():
                    asyncio.run_coroutine_threadsafe(bot.send_message(chat_id=user_id, text=text), loop)
                else:
                    asyncio.run(bot.send_message(chat_id=user_id, text=text))
        except Exception:
            pass

        message = (
            f"Все {total} ключей для пользователя {user_id} были успешно отозваны." if success_count == total
            else f"Удалось отозвать {success_count} из {total} ключей для пользователя {user_id}. Проверьте логи."
        )
        category = 'success' if success_count == total else 'warning'


        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if wants_json:
            return jsonify({"ok": success_count == total, "message": message, "revoked": success_count, "total": total}), 200

        flash(message, category)
        return redirect(url_for('users_page'))

    @flask_app.route('/add-host', methods=['POST'])
    @login_required
    def add_host_route():
        name = (request.form.get('host_name') or '').strip()
        if not name:
            flash('Укажите название хоста.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))

        base_url = (get_setting('remnawave_base_url') or '').strip()
        api_token = (get_setting('remnawave_api_token') or '').strip()
        sub_url = (get_setting('remnawave_subscription_url') or '').strip() or None
        if not base_url or not api_token:
            flash('Сначала заполните настройки Remnawave (URL и API Token) в блоке сверху.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))

        try:
            create_host(
                name=name,
                url=base_url,
                user='',
                passwd='',
                inbound=0,
                subscription_url=sub_url,
            )
        except Exception as e:
            logger.error(f"Не удалось создать хост '{name}': {e}")
            flash(f"Не удалось создать хост '{name}'.", 'danger')
            return redirect(url_for('settings_page', tab='hosts'))

        try:
            update_host_remnawave_settings(
                name,
                remnawave_base_url=base_url,
                remnawave_api_token=api_token,
                squad_uuid=None,
            )
        except Exception as e:
            logger.error(f"Не удалось сохранить Remnawave-настройки для '{name}': {e}")
            flash('Хост создан, но Remnawave-настройки сохранить не удалось.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))

        # Опционально: сразу отметить выбранные сквады каталога
        raw_ids = request.form.getlist('squad_ids')
        catalog_ids: list[int] = []
        for value in raw_ids:
            try:
                catalog_ids.append(int(value))
            except Exception:
                continue
        if catalog_ids:
            set_host_squads_from_catalog(name, catalog_ids)

        flash(f"Хост '{name}' успешно добавлен.", 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/delete-host/<host_name>', methods=['POST'])
    @login_required
    def delete_host_route(host_name):
        delete_host(host_name)
        flash(f"Хост '{host_name}' и все его тарифы были удалены.", 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/add-plan', methods=['POST'])
    @login_required
    def add_plan_route():
        traffic_gb_raw = (request.form.get('traffic_limit_gb') or '').strip()
        devices_raw = (request.form.get('hwid_device_limit') or '').strip()
        lte_gb_raw = (request.form.get('lte_limit_gb') or '').strip()
        reset_price_raw = (request.form.get('main_reset_price_rub') or '').strip()

        traffic_limit_bytes = 0
        if traffic_gb_raw:
            try:
                gb = float(traffic_gb_raw)
                traffic_limit_bytes = int(gb * 1024 * 1024 * 1024) if gb > 0 else 0
            except (TypeError, ValueError):
                traffic_limit_bytes = 0

        hwid_device_limit = None
        if devices_raw:
            try:
                hwid_device_limit = int(devices_raw)
            except (TypeError, ValueError):
                hwid_device_limit = None

        lte_limit_bytes = 0
        if lte_gb_raw:
            try:
                lte_gb = float(lte_gb_raw)
                lte_limit_bytes = int(lte_gb * 1024 * 1024 * 1024) if lte_gb > 0 else 0
            except (TypeError, ValueError):
                lte_limit_bytes = 0

        main_reset_price_rub = 0.0
        if reset_price_raw:
            try:
                main_reset_price_rub = float(reset_price_raw)
            except (TypeError, ValueError):
                main_reset_price_rub = 0.0

        create_plan(
            host_name=request.form['host_name'],
            plan_name=request.form['plan_name'],
            months=int(request.form['months']),
            price=float(request.form['price']),
            traffic_limit_bytes=traffic_limit_bytes,
            hwid_device_limit=hwid_device_limit,
            lte_limit_bytes=lte_limit_bytes,
            main_reset_price_rub=main_reset_price_rub,
        )
        flash(f"Новый тариф для хоста '{request.form['host_name']}' добавлен.", 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/delete-plan/<int:plan_id>', methods=['POST'])
    @login_required
    def delete_plan_route(plan_id):
        delete_plan(plan_id)
        flash("Тариф успешно удален.", 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/toggle-plan/<int:plan_id>', methods=['POST'])
    @login_required
    def toggle_plan_route(plan_id):
        current_active = True
        try:
            from shop_bot.data_manager.database import get_plan_by_id as _get_plan_by_id
            plan = _get_plan_by_id(plan_id)
            current_active = bool(int(plan.get('is_active', 1) or 0)) if plan else True
        except Exception:
            pass
        ok = set_plan_active(plan_id, not current_active)
        if ok:
            flash('Статус тарифа изменён.', 'success')
        else:
            flash('Не удалось изменить статус тарифа.', 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/update-plan/<int:plan_id>', methods=['POST'])
    @login_required
    def update_plan_route(plan_id):
        plan_name = (request.form.get('plan_name') or '').strip()
        months = request.form.get('months')
        price = request.form.get('price')
        try:
            months_int = int(months)
            price_float = float(price)
        except (TypeError, ValueError):
            flash('Некорректные значения для месяцев или цены.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))

        if not plan_name:
            flash('Название тарифа не может быть пустым.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))

        kwargs = {}

        traffic_gb_raw = request.form.get('traffic_limit_gb')
        if traffic_gb_raw is not None:
            traffic_gb_raw = traffic_gb_raw.strip()
            try:
                gb = float(traffic_gb_raw) if traffic_gb_raw else 0.0
                kwargs['traffic_limit_bytes'] = int(gb * 1024 * 1024 * 1024) if gb > 0 else 0
            except (TypeError, ValueError):
                pass

        devices_raw = request.form.get('hwid_device_limit')
        if devices_raw is not None:
            devices_raw = devices_raw.strip()
            try:
                kwargs['hwid_device_limit'] = int(devices_raw) if devices_raw else None
            except (TypeError, ValueError):
                pass

        lte_gb_raw = request.form.get('lte_limit_gb')
        if lte_gb_raw is not None:
            lte_gb_raw = lte_gb_raw.strip()
            try:
                lte_gb = float(lte_gb_raw) if lte_gb_raw else 0.0
                kwargs['lte_limit_bytes'] = int(lte_gb * 1024 * 1024 * 1024) if lte_gb > 0 else 0
            except (TypeError, ValueError):
                pass

        reset_price_raw = request.form.get('main_reset_price_rub')
        if reset_price_raw is not None:
            reset_price_raw = reset_price_raw.strip()
            try:
                kwargs['main_reset_price_rub'] = float(reset_price_raw) if reset_price_raw else 0.0
            except (TypeError, ValueError):
                pass

        ok = update_plan(plan_id, plan_name, months_int, price_float, **kwargs)
        if ok:
            flash('Тариф обновлён.', 'success')
        else:
            flash('Не удалось обновить тариф (возможно, он не найден).', 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    def _normalize_package_pool(raw) -> str:
        """Пул пакета докупки: 'lte' (💰 premium-ноды) или 'main' (основной трафик)."""
        return 'lte' if str(raw or '').strip().lower() == 'lte' else 'main'

    @flask_app.route('/admin/plans/<int:plan_id>/packages')
    @login_required
    def admin_get_traffic_packages_for_plan_json(plan_id: int):
        pool = _normalize_package_pool(request.args.get('pool'))
        try:
            packages = get_traffic_packages_for_plan(plan_id, pool=pool)
            data = [
                {
                    "package_id": p.get('package_id'),
                    "plan_id": p.get('plan_id'),
                    "size_gb": p.get('size_gb'),
                    "price": p.get('price'),
                    "is_active": bool(p.get('is_active')),
                } for p in packages
            ]
            return jsonify({"ok": True, "items": data})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @flask_app.route('/add-traffic-package', methods=['POST'])
    @login_required
    def add_traffic_package_route():
        try:
            plan_id = int(request.form['plan_id'])
            size_gb = float(request.form['size_gb'])
            price = float(request.form['price'])
        except (KeyError, TypeError, ValueError):
            flash('Проверьте поля пакета ГБ.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))

        # Пул обязателен: без него пакет всегда уходил в 'main', и докупка LTE
        # у пользователей отвечала «пакеты не настроены».
        pool = _normalize_package_pool(request.form.get('pool'))
        if pool == 'lte':
            plan = get_plan_by_id(plan_id)
            if not plan or int(plan.get('lte_limit_bytes') or 0) <= 0:
                flash('Сначала задайте LTE-лимит тарифа («LTE пул, ГБ»), иначе LTE-пакеты не будут доступны.', 'danger')
                return redirect(url_for('settings_page', tab='hosts'))

        create_traffic_package(plan_id, size_gb, price, pool=pool)
        flash('LTE-пакет ГБ добавлен.' if pool == 'lte' else 'Пакет ГБ добавлен.', 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/update-traffic-package/<int:package_id>', methods=['POST'])
    @login_required
    def update_traffic_package_route(package_id):
        size_gb = request.form.get('size_gb')
        price = request.form.get('price')
        is_active_raw = request.form.get('is_active')

        kwargs = {}
        try:
            if size_gb is not None and str(size_gb).strip() != '':
                kwargs['size_gb'] = float(size_gb)
            if price is not None and str(price).strip() != '':
                kwargs['price'] = float(price)
        except (TypeError, ValueError):
            flash('Некорректные значения для пакета ГБ.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))

        if is_active_raw is not None:
            kwargs['is_active'] = str(is_active_raw).lower() in ('on', 'true', '1', 'yes')

        ok = update_traffic_package(package_id, **kwargs)
        if ok:
            flash('Пакет ГБ обновлён.', 'success')
        else:
            flash('Не удалось обновить пакет ГБ (возможно, он не найден).', 'danger')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/toggle-traffic-package/<int:package_id>', methods=['POST'])
    @login_required
    def toggle_traffic_package_route(package_id):
        pkg = get_traffic_package_by_id(package_id)
        if not pkg:
            flash('Пакет ГБ не найден.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))
        new_state = not bool(pkg.get('is_active'))
        update_traffic_package(package_id, is_active=new_state)
        flash('Статус пакета ГБ изменён.', 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/delete-traffic-package/<int:package_id>', methods=['POST'])
    @login_required
    def delete_traffic_package_route(package_id):
        delete_traffic_package(package_id)
        flash('Пакет ГБ удалён.', 'success')
        return redirect(url_for('settings_page', tab='hosts'))



    def _get_client_ip() -> str:
        """Best-effort client IP (supports reverse proxy via X-Forwarded-For)."""
        try:
            xff = request.headers.get('X-Forwarded-For')
            if xff:
                return xff.split(',')[0].strip()
        except Exception:
            pass
        return request.remote_addr or ''

    def _is_ip_allowed(allowlist: list[str]) -> bool:
        if not allowlist:
            return False
        ip = _get_client_ip()
        return ip in allowlist

    def _debug_endpoints_allowed() -> bool:
        if not flask_app.config.get('ENABLE_DEBUG_ENDPOINTS'):
            return False
        allow = flask_app.config.get('DEBUG_IP_ALLOWLIST') or []
        return _is_ip_allowed(allow)

    def _http_json(url: str, *, method: str = 'GET', headers: dict | None = None, body: dict | None = None, timeout: int = 20) -> dict:
        """Minimal JSON HTTP client via urllib (avoids extra deps)."""
        h = headers or {}
        data_bytes = None
        if body is not None:
            data_bytes = json.dumps(body).encode('utf-8')
            h = {**h, 'Content-Type': 'application/json'}
        req = urllib.request.Request(url, data=data_bytes, headers=h, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return json.loads(raw.decode('utf-8'))

    def _yookassa_get_payment(payment_id: str) -> dict | None:
        shop_id = (get_setting('yookassa_shop_id') or '').strip()
        secret_key = (get_setting('yookassa_secret_key') or '').strip()
        if not shop_id or not secret_key:
            logger.error('YooKassa webhook: missing yookassa_shop_id/yookassa_secret_key')
            return None
        auth = base64.b64encode(f"{shop_id}:{secret_key}".encode('utf-8')).decode('ascii')
        headers = {'Authorization': f'Basic {auth}'}
        url = f"https://api.yookassa.ru/v3/payments/{payment_id}"
        try:
            return _http_json(url, method='GET', headers=headers, body=None, timeout=20)
        except Exception as e:
            logger.error(f"YooKassa webhook: failed to fetch payment {payment_id}: {e}", exc_info=True)
            return None

    def _cryptobot_verify_signature(raw_body: bytes) -> bool:
        token = (get_setting('cryptobot_token') or '').strip()
        if not token:
            logger.error('CryptoBot webhook: missing cryptobot_token (cannot verify signature)')
            return False
        sig = request.headers.get('crypto-pay-api-signature') or request.headers.get('Crypto-Pay-API-Signature')
        if not sig:
            logger.warning('CryptoBot webhook: missing crypto-pay-api-signature header')
            return False
        secret = hashlib.sha256(token.encode('utf-8')).digest()
        expected = hashlib.new('sha256')
        import hmac
        expected_hex = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
        return compare_digest(expected_hex, sig)

    def _cryptobot_get_invoice(invoice_id: int) -> dict | None:
        token = (get_setting('cryptobot_token') or '').strip()
        if not token:
            return None
        headers = {'Crypto-Pay-API-Token': token}
        url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
        try:
            data = _http_json(url, method='GET', headers=headers, body=None, timeout=20)
        except Exception as e:
            logger.error(f"CryptoBot webhook: failed to fetch invoice {invoice_id}: {e}", exc_info=True)
            return None
        try:
            if not isinstance(data, dict) or not data.get('ok'):
                return None
            res = data.get('result')
            items = res.get('items') if isinstance(res, dict) else None
            if isinstance(items, list) and items:
                return items[0]
        except Exception:
            pass
        return None

    def _require_ton_webhook_secret() -> bool:
        secret = (get_setting('ton_webhook_secret') or '').strip() or (flask_app.config.get('TON_WEBHOOK_SECRET') or '').strip()
        if not secret:
            logger.error('TON webhook is enabled but ton_webhook_secret is not configured')
            return False
        header = (request.headers.get('X-Webhook-Secret') or request.headers.get('X-Ton-Webhook-Secret') or '').strip()
        if not header:
            auth = (request.headers.get('Authorization') or '').strip()
            if auth.lower().startswith('bearer '):
                header = auth.split(' ', 1)[1].strip()
        if not header:
            return False
        return compare_digest(header, secret)

    @csrf.exempt
    @flask_app.route('/yookassa-webhook', methods=['POST'])
    def yookassa_webhook_handler():
        """YooKassa webhook (secure).

        Не доверяем входящему payload. Берём provider payment_id из webhook,
        затем запрашиваем платеж в YooKassa API по секретному ключу и проверяем:
        - status == succeeded
        - amount/currency совпадают с pending
        - payment_id (internal) ещё не обработан (pending статус + idempotency)
        """
        try:
            payload = request.get_json(silent=True) or {}

            # provider payment id приходит в payload['object']['id']
            provider_payment_id = None
            if isinstance(payload, dict):
                obj = payload.get('object') or {}
                if isinstance(obj, dict):
                    provider_payment_id = obj.get('id') or payload.get('payment_id')

            if not provider_payment_id:
                logger.warning("YooKassa webhook: missing provider payment id")
                return 'Bad Request', 400

            shop_id = (get_setting('yookassa_shop_id') or '').strip()
            secret_key = (get_setting('yookassa_secret_key') or '').strip()
            if not shop_id or not secret_key:
                logger.error("YooKassa webhook: YooKassa is not configured (shop_id/secret_key)")
                return 'Misconfigured', 500

            # Validate by calling YooKassa API
            auth = base64.b64encode(f"{shop_id}:{secret_key}".encode('utf-8')).decode('ascii')
            url = f"https://api.yookassa.ru/v3/payments/{provider_payment_id}"
            try:
                data = _http_json(url, headers={"Authorization": f"Basic {auth}"}, timeout=20)
            except Exception as e:
                logger.error(f"YooKassa webhook: failed to fetch payment {provider_payment_id}: {e}", exc_info=True)
                return 'Error', 502

            if not isinstance(data, dict):
                logger.error(f"YooKassa webhook: unexpected API response type for {provider_payment_id}: {type(data)}")
                return 'Error', 502

            status = (data.get('status') or '').strip().lower()
            if status != 'succeeded':
                if status == 'canceled':
                    meta = data.get('metadata') or {}
                    if not isinstance(meta, dict):
                        meta = {}
                    internal_payment_id = (meta.get('payment_id') or '').strip()
                    if internal_payment_id:
                        cancel_pending_transaction(internal_payment_id)
                else:
                    logger.info(f"YooKassa webhook: payment {provider_payment_id} status={status} (ignored)")
                return 'OK', 200

            amount_obj = data.get('amount') or {}
            value_str = (amount_obj.get('value') or '').strip()
            currency = (amount_obj.get('currency') or '').strip().upper()
            meta = data.get('metadata') or {}
            if not isinstance(meta, dict):
                meta = {}

            internal_payment_id = (meta.get('payment_id') or '').strip()
            if not internal_payment_id:
                logger.warning(f"YooKassa webhook: payment {provider_payment_id} has no internal payment_id in metadata")
                return 'OK', 200

            # Сверка ожидаемой суммы/валюты с pending (если есть pending)
            pending_meta = None
            try:
                pending_meta = rw_repo.get_pending_metadata(internal_payment_id)
            except Exception as e:
                logger.error(f"YooKassa webhook: failed to read pending for {internal_payment_id}: {e}", exc_info=True)

            if pending_meta:
                expected_amount = _parse_decimal_amount(
                    pending_meta.get('price') or pending_meta.get('amount_rub') or '0',
                    log_prefix=f"YooKassa webhook pending payment_id={internal_payment_id}",
                )
                got_amount = _parse_decimal_amount(
                    value_str,
                    log_prefix=f"YooKassa webhook payment payment_id={internal_payment_id}",
                )
                if expected_amount is None or got_amount is None:
                    return 'OK', 200

                if currency and currency != 'RUB':
                    logger.warning(f"YooKassa webhook: currency mismatch for {internal_payment_id}: got={currency}, expected=RUB")
                    return 'OK', 200

                if got_amount != expected_amount:
                    logger.warning(f"YooKassa webhook: amount mismatch for {internal_payment_id}: got={got_amount}, expected={expected_amount}")
                    return 'OK', 200

            # Atomically mark pending paid and get metadata (idempotency)
            metadata = find_and_complete_pending_transaction(internal_payment_id)
            if not metadata:
                # already processed / unknown
                return 'OK', 200

            # Ensure payment_method present
            metadata.setdefault('payment_method', 'YooKassa')
            _dispatch_payment_processing(metadata)

            return 'OK', 200
        except Exception as e:
            logger.error(f"Ошибка в обработчике вебхука YooKassa: {e}", exc_info=True)
            return 'Error', 500

    @csrf.exempt
    @flask_app.route('/test-webhook', methods=['GET', 'POST'])
    def test_webhook():
        """Тестовый endpoint. В продакшне отключен по умолчанию."""
        if not _debug_endpoints_allowed():
            return 'Not Found', 404
        if request.method == 'GET':
            return f"Webhook server is running! Time: {datetime.now()}"
        return f"POST received! Data: {request.get_json(silent=True) or request.form.to_dict()}"

    @csrf.exempt
    @flask_app.route('/debug-all', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def debug_all_requests():
        """Опасный debug endpoint: возвращает заголовки/куки/данные. В продакшне отключен по умолчанию."""
        if not _debug_endpoints_allowed():
            return 'Not Found', 404

        # Никогда не логируем сюда cookies/authorization в явном виде.
        try:
            hdrs = dict(request.headers)
            for k in list(hdrs.keys()):
                if k.lower() in ('authorization', 'cookie', 'set-cookie'):
                    hdrs[k] = '[REDACTED]'
        except Exception:
            hdrs = {}

        return {
            "method": request.method,
            "headers": hdrs,
            "form": request.form.to_dict(),
            "json": request.get_json(silent=True),
            "args": request.args.to_dict(),
            "timestamp": datetime.now().isoformat()
        }

    @csrf.exempt
    @flask_app.route('/yoomoney-webhook', methods=['POST'])
    def yoomoney_webhook_handler():
        """ЮMoney HTTP уведомление (кнопка/ссылка p2p). Подпись: sha1(notification_type&operation_id&amount&currency&datetime&sender&codepro&notification_secret&label)."""
        logger.info("🔔 Получен webhook от ЮMoney")
        
        try:
            form = request.form
            logger.info(f"📋 Данные webhook: {dict(form)}")
            
            required = [
                'notification_type', 'operation_id', 'amount', 'currency', 'datetime', 'sender', 'codepro', 'label', 'sha1_hash'
            ]
            if not all(k in form for k in required):
                logger.warning(f"❌ Отсутствуют обязательные поля. Доступно: {list(form.keys())}")
                return 'Bad Request', 400

            if not _setting_flag_enabled(get_setting('yoomoney_enabled')):
                logger.warning("YooMoney webhook: yoomoney_enabled is off")
                return 'Forbidden', 403

            secret = (get_setting('yoomoney_secret') or '').strip()
            if not secret:
                logger.error("YooMoney webhook отключён: пустой yoomoney_secret")
                return 'Forbidden', 403

            notification_type = form.get('notification_type', '')
            logger.info(f"📝 Тип уведомления: {notification_type}")
            if notification_type != 'p2p-incoming':
                logger.info(f"⏭️  Игнорируем тип уведомления: {notification_type}")
                return 'OK', 200
            

            codepro = form.get('codepro', '')
            if codepro.lower() == 'true':
                logger.info("🧪 Игнорируем тестовый платеж (codepro=true)")
                return 'OK', 200
            
            signature_str = "&".join([
                form.get('notification_type',''),
                form.get('operation_id',''),
                form.get('amount',''),
                form.get('currency',''),
                form.get('datetime',''),
                form.get('sender',''),
                form.get('codepro',''),
                secret,
                form.get('label',''),
            ])
            expected = hashlib.sha1(signature_str.encode('utf-8')).hexdigest()
            provided = (form.get('sha1_hash') or '').lower()
            if not compare_digest(expected, provided):
                logger.warning("🔐 Неверная подпись")
                return 'Forbidden', 403
            

            payment_id = (form.get('label') or '').strip()
            if not payment_id:
                logger.warning("🏷️  Пустой label")
                return 'OK', 200

            pending_meta = None
            try:
                pending_meta = rw_repo.get_pending_metadata(payment_id)
            except Exception as e:
                logger.error(f"YooMoney webhook: failed to read pending for {payment_id}: {e}", exc_info=True)

            if not pending_meta:
                logger.warning(f"❌ Метаданные не найдены для платежа: {payment_id}")
                return 'OK', 200

            if not _pending_method_allowed(pending_meta, "YooMoney"):
                logger.warning(
                    f"YooMoney webhook: payment_id={payment_id} is not a YooMoney pending "
                    f"(payment_method={pending_meta.get('payment_method')!r})"
                )
                return 'OK', 200

            expected_amount = _pending_expected_amount(pending_meta)
            got_amount = _parse_decimal_amount(
                form.get('amount'),
                log_prefix=f"YooMoney webhook payment_id={payment_id}",
            )
            if expected_amount is None or got_amount is None:
                logger.warning(f"YooMoney webhook: amount missing/unparseable for payment_id={payment_id}")
                return 'OK', 200
            if got_amount != expected_amount:
                logger.warning(
                    f"YooMoney webhook: amount mismatch for {payment_id}: got={got_amount}, expected={expected_amount}"
                )
                return 'OK', 200
            
            logger.info(f"💰 Обрабатываем платеж: {payment_id}")
            metadata = find_and_complete_pending_transaction(payment_id)
            if not metadata:
                logger.warning(f"❌ Метаданные не найдены для платежа: {payment_id}")
                return 'OK', 200
            
            logger.info(f"✅ Найдены метаданные для платежа {payment_id}: пользователь={metadata.get('user_id')}, сумма={metadata.get('price')}")
            metadata.setdefault('payment_method', 'YooMoney')
            _dispatch_payment_processing(metadata)
            logger.info(f"🚀 Запущена обработка платежа: {payment_id}")
            return 'OK', 200
        except Exception as e:
            logger.error(f"💥 Ошибка в webhook ЮMoney: {e}", exc_info=True)
            return 'Error', 500

    
    @csrf.exempt
    @flask_app.route('/platega-webhook', methods=['GET', 'POST'])
    def platega_webhook_handler():
        """Platega webhook. Авторизация: заголовки X-MerchantId / X-Secret. Payload содержит статус и поле payload (наш payment_id)."""
        try:
            if request.method == 'GET':
                return jsonify({
                    "status": "ok",
                    "service": "platega_webhook",
                    "enabled": bool((get_setting('platega_merchant_id') or '') and (get_setting('platega_secret') or ''))
                }), 200

            expected_merchant = (get_setting('platega_merchant_id') or '').strip()
            expected_secret = (get_setting('platega_secret') or '').strip()
            if not expected_merchant or not expected_secret:
                logger.error("Platega webhook отключён: не настроены credentials")
                return 'Forbidden', 403

            merchant_id = request.headers.get("X-MerchantId") or ""
            secret = request.headers.get("X-Secret") or ""
            if not (
                compare_digest(str(merchant_id), expected_merchant)
                and compare_digest(str(secret), expected_secret)
            ):
                return 'Unauthorized', 401

            try:
                payload = request.get_json(force=True)
            except Exception:
                return 'Bad Request', 400

            if not isinstance(payload, dict):
                return 'Bad Request', 400

            status_raw = str(payload.get('status') or '').upper().strip()
            payment_id = str(payload.get('payload') or '').strip()
            platega_transaction_id = str(payload.get('id') or '').strip()

            if not payment_id:
                return 'OK', 200

            if normalize_platega_status(status_raw) == "canceled":
                if platega_transaction_id:
                    try:
                        from shop_bot.data_manager.database import patch_pending_metadata
                        patch_pending_metadata(payment_id, {"platega_transaction_id": platega_transaction_id})
                    except Exception:
                        pass
                mark_pending_canceled(payment_id, provider_transaction_id=platega_transaction_id or None)
                return 'OK', 200

            # Обрабатываем только успешное подтверждение
            if status_raw == 'CONFIRMED':
                pending_meta = None
                try:
                    pending_meta = rw_repo.get_pending_metadata(payment_id)
                except Exception as e:
                    logger.error(f"Platega webhook: failed to read pending for {payment_id}: {e}", exc_info=True)

                if not pending_meta:
                    logger.warning(f"Platega webhook: no pending transaction for payment_id={payment_id}")
                    return 'OK', 200

                if not _pending_method_allowed(pending_meta, "Platega", "Platega Crypto"):
                    logger.warning(
                        f"Platega webhook: payment_id={payment_id} is not a Platega pending "
                        f"(payment_method={pending_meta.get('payment_method')!r})"
                    )
                    return 'OK', 200

                expected_amount = _pending_expected_amount(pending_meta)
                got_amount = _parse_decimal_amount(
                    _extract_platega_webhook_amount(payload),
                    log_prefix=f"Platega webhook payment_id={payment_id}",
                )
                if expected_amount is None or got_amount is None:
                    logger.warning(f"Platega webhook: amount missing/unparseable for payment_id={payment_id}")
                    return 'OK', 200
                if not _platega_amount_covers_order(got_amount, expected_amount):
                    logger.warning(
                        f"Platega webhook: amount mismatch for {payment_id}: got={got_amount}, expected={expected_amount}"
                    )
                    return 'OK', 200

                metadata = complete_pending_platega_payment(
                    payment_id,
                    provider_transaction_id=platega_transaction_id or None,
                )
                if metadata:
                    try:
                        _handle_promo_after_payment(metadata)
                    except Exception:
                        pass
                    _dispatch_payment_processing(metadata)
            return 'OK', 200
        except Exception as e:
            logger.error(f"Ошибка в обработчике вебхука Platega: {e}", exc_info=True)
            return 'Error', 500

    @csrf.exempt
    @flask_app.route('/rollypay-webhook', methods=['POST'])
    def rollypay_webhook_handler():
        """RollyPay webhook.

        HMAC по сырому телу (X-Signature / X-Timestamp), затем GET платежа в API.
        Телу колбэка не доверяем: статус, сумма и order_id — только из ответа API.
        """
        try:
            from shop_bot.modules.rollypay_api import get_payment_sync, verify_webhook_signature

            api_key = (get_setting('rollypay_api_key') or '').strip()
            signing_secret = (get_setting('rollypay_signing_secret') or '').strip()
            if not signing_secret or not api_key:
                logger.error('RollyPay webhook: не настроены api_key/signing_secret')
                return 'Not configured', 503

            raw = request.get_data(cache=True) or b''
            timestamp = request.headers.get('X-Timestamp', '')
            signature = request.headers.get('X-Signature', '')
            if not verify_webhook_signature(raw, timestamp, signature, signing_secret):
                logger.warning('RollyPay webhook: подпись не прошла проверку')
                return 'Forbidden', 403

            try:
                payload = json.loads(raw.decode('utf-8'))
            except Exception:
                return 'Bad Request', 400
            if not isinstance(payload, dict):
                return 'Bad Request', 400

            event_type = str(payload.get('event_type') or '').strip()
            if event_type in ('payment.chargeback', 'payment.refunded', 'refund_request.completed', 'payment.canceled', 'payment.expired'):
                cancel_pid = str(payload.get('order_id') or '').strip()
                if cancel_pid:
                    cancel_pending_transaction(cancel_pid)
                logger.error(
                    'RollyPay: возврат/чарджбек/отмена order_id=%s provider_id=%s — без автозачисления',
                    payload.get('order_id'),
                    payload.get('payment_id'),
                )
                return 'OK', 200
            if event_type != 'payment.paid':
                return 'OK', 200

            payment_id = str(payload.get('order_id') or '').strip()
            provider_payment_id = str(payload.get('payment_id') or '').strip()
            if not payment_id or not provider_payment_id:
                return 'OK', 200

            pending_meta = None
            try:
                pending_meta = rw_repo.get_pending_metadata(payment_id)
            except Exception as e:
                logger.error(f"RollyPay webhook: failed to read pending for {payment_id}: {e}", exc_info=True)
            if not pending_meta:
                logger.warning(f"RollyPay webhook: no pending transaction for payment_id={payment_id}")
                return 'OK', 200
            if not _pending_method_allowed(pending_meta, "RollyPay"):
                logger.warning(
                    f"RollyPay webhook: payment_id={payment_id} is not a RollyPay pending "
                    f"(payment_method={pending_meta.get('payment_method')!r})"
                )
                return 'OK', 200

            remote = get_payment_sync(api_key, provider_payment_id)
            if not isinstance(remote, dict):
                logger.error("RollyPay webhook: API lookup failed payment_id=%s", payment_id)
                return 'Service Unavailable', 503

            remote_status = str(remote.get('status') or '').strip().lower()
            if remote_status != 'paid':
                if remote_status in {'canceled', 'cancelled', 'expired', 'chargeback'}:
                    cancel_pending_transaction(payment_id)
                logger.info(
                    "RollyPay webhook: API status=%s payment_id=%s (ignored)",
                    remote_status,
                    payment_id,
                )
                return 'OK', 200

            remote_order = str(remote.get('order_id') or '').strip()
            if remote_order != payment_id:
                logger.warning(
                    "RollyPay webhook: order_id mismatch payment_id=%s remote_order=%s",
                    payment_id,
                    remote_order,
                )
                return 'OK', 200

            expected_amount = _pending_expected_amount(pending_meta)
            got_amount = _parse_decimal_amount(
                remote.get('amount'),
                log_prefix=f"RollyPay webhook payment_id={payment_id}",
            )
            if expected_amount is None or got_amount is None:
                logger.warning(f"RollyPay webhook: amount missing/unparseable for payment_id={payment_id}")
                return 'OK', 200
            if got_amount.quantize(Decimal('0.01')) != expected_amount.quantize(Decimal('0.01')):
                logger.warning(
                    f"RollyPay webhook: amount mismatch for {payment_id}: got={got_amount}, expected={expected_amount}"
                )
                return 'OK', 200

            currency = str(remote.get('payment_currency') or remote.get('currency') or '').strip().upper()
            if currency and currency != 'RUB':
                logger.warning(f"RollyPay webhook: currency mismatch for {payment_id}: {currency}")
                return 'OK', 200

            metadata = find_and_complete_pending_transaction(payment_id)
            if metadata:
                metadata.setdefault('payment_method', 'RollyPay')
                metadata['rollypay_payment_id'] = provider_payment_id
                try:
                    _handle_promo_after_payment(metadata)
                except Exception:
                    pass
                _dispatch_payment_processing(metadata)
            return 'OK', 200
        except Exception as e:
            logger.error(f"Ошибка в обработчике вебхука RollyPay: {e}", exc_info=True)
            return 'Error', 500

    @csrf.exempt
    @flask_app.route('/cryptobot-webhook', methods=['POST'])
    def cryptobot_webhook_handler():
        """Crypto Pay API webhook (secure).

        - Проверяем подпись `crypto-pay-api-signature` (HMAC-SHA256 по сырым байтам тела)
        - Дополнительно валидируем invoice через API (getInvoices)
        - Idempotency: если payload это internal payment_id → закрываем pending атомарно.
          Если payload старого формата → используем processed_payments ключ `cryptobot:<invoice_id>`.
        """
        try:
            token = (get_setting('cryptobot_token') or '').strip()
            if not token:
                logger.error('CryptoBot webhook: cryptobot_token is not configured')
                return 'Misconfigured', 500

            # cache=True so HMAC and JSON see the same bytes (cache=False would drain the stream).
            raw_body = request.get_data(cache=True) or b''
            signature = (request.headers.get('crypto-pay-api-signature') or request.headers.get('Crypto-Pay-API-Signature') or '').strip()
            if not signature:
                logger.warning('CryptoBot webhook: missing crypto-pay-api-signature header')
                return 'Forbidden', 403

            # expected signature: HMAC-SHA256(body) with secret = SHA256(app_token)
            secret = hashlib.sha256(token.encode('utf-8')).digest()
            expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
            if not compare_digest(expected, signature):
                logger.warning('CryptoBot webhook: invalid signature')
                return 'Forbidden', 403

            try:
                request_data = json.loads(raw_body.decode('utf-8')) if raw_body else {}
            except Exception:
                request_data = {}
            if not isinstance(request_data, dict):
                return 'Bad Request', 400

            if request_data.get('update_type') != 'invoice_paid':
                return 'OK', 200

            payload_obj = request_data.get('payload') or {}
            if not isinstance(payload_obj, dict):
                payload_obj = {}

            invoice_id = payload_obj.get('invoice_id')
            try:
                invoice_id_int = int(invoice_id)
            except Exception:
                invoice_id_int = None

            payload_str = (payload_obj.get('payload') or '').strip()
            if not payload_str:
                logger.warning('CryptoBot webhook: invoice_paid but payload is empty')
                return 'OK', 200

            # Fetch invoice details from Crypto Pay API to validate status/amount.
            # Crypto Pay returns { ok, result: { items: [...] } } — parse via _cryptobot_get_invoice.
            invoice = None
            if invoice_id_int is not None:
                invoice = _cryptobot_get_invoice(invoice_id_int)
                if not isinstance(invoice, dict):
                    logger.warning(
                        f"CryptoBot webhook: amount verification failed "
                        f"(invoice fetch/parse returned nothing) invoice_id={invoice_id_int}"
                    )

            if isinstance(invoice, dict):
                status = (invoice.get('status') or '').strip().lower()
                if status != 'paid':
                    logger.info(f"CryptoBot webhook: invoice {invoice_id_int} status={status} (ignored)")
                    return 'OK', 200

            # New format: payload == internal payment_id (uuid). Then we have pending with expected price.
            if ':' not in payload_str:
                internal_payment_id = payload_str

                pending_meta = None
                try:
                    pending_meta = rw_repo.get_pending_metadata(internal_payment_id)
                except Exception:
                    pending_meta = None

                if pending_meta and isinstance(invoice, dict):
                    try:
                        from decimal import Decimal
                        expected_amount = Decimal(str(pending_meta.get('price') or pending_meta.get('amount_rub') or '0')).quantize(Decimal('0.01'))
                        got_amount = Decimal(str(invoice.get('amount') or '0')).quantize(Decimal('0.01'))
                        fiat = (invoice.get('fiat') or '').upper()
                    except Exception:
                        logger.warning(f"CryptoBot webhook: amount parse error for payment_id={internal_payment_id}")
                        return 'OK', 200

                    if fiat and fiat != 'RUB':
                        logger.warning(f"CryptoBot webhook: fiat mismatch for {internal_payment_id}: got={fiat}, expected=RUB")
                        return 'OK', 200
                    if got_amount != expected_amount:
                        logger.warning(f"CryptoBot webhook: amount mismatch for {internal_payment_id}: got={got_amount}, expected={expected_amount}")
                        return 'OK', 200
                elif pending_meta and not isinstance(invoice, dict):
                    logger.warning(
                        f"CryptoBot webhook: amount verification could not run for payment_id={internal_payment_id}; "
                        f"refusing to complete pending without a verified invoice"
                    )
                    return 'OK', 200

                metadata = find_and_complete_pending_transaction(internal_payment_id)
                if not metadata:
                    return 'OK', 200

                metadata.setdefault('payment_method', 'CryptoBot')
                if invoice_id_int is not None:
                    metadata['cryptobot_invoice_id'] = str(invoice_id_int)
                _dispatch_payment_processing(metadata)
                return 'OK', 200

            # Legacy format (colon-separated): keep compatibility but still idempotent via processed_payments
            parts = payload_str.split(':')
            if len(parts) < 9:
                logger.error(f"CryptoBot webhook: invalid legacy payload format: {payload_str}")
                return 'Bad Request', 400

            metadata = {
                'user_id': parts[0],
                'months': parts[1],
                'price': parts[2],
                'action': parts[3],
                'key_id': parts[4],
                'host_name': parts[5],
                'plan_id': parts[6],
                'customer_email': parts[7] if parts[7] != 'None' else None,
                'payment_method': parts[8],
            }
            if len(parts) >= 10:
                metadata['promo_code'] = (parts[9] if parts[9] != 'None' else None)
            if len(parts) >= 11:
                metadata['promo_discount'] = parts[10]

            if invoice_id_int is not None:
                metadata['payment_id'] = f"cryptobot:{invoice_id_int}"
                metadata['cryptobot_invoice_id'] = str(invoice_id_int)

            _dispatch_payment_processing(metadata)

            return 'OK', 200

        except Exception as e:
            logger.error(f"Ошибка в обработчике вебхука CryptoBot: {e}", exc_info=True)
            return 'Error', 500

    @csrf.exempt
    @flask_app.route('/heleket-webhook', methods=['POST'])
    def heleket_webhook_handler():
        try:
            data = request.json
            logger.info(f"Получен вебхук Heleket: {data}")

            api_key = get_setting("heleket_api_key")
            if not api_key: return 'Error', 500

            sign = data.pop("sign", None)
            if not sign: return 'Error', 400
                
            sorted_data_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
            
            base64_encoded = base64.b64encode(sorted_data_str.encode()).decode()
            raw_string = f"{base64_encoded}{api_key}"
            expected_sign = hashlib.md5(raw_string.encode()).hexdigest()

            if not compare_digest(expected_sign, sign):
                logger.warning("Heleket вебхук: недействительная подпись.")
                return 'Forbidden', 403

            if data.get('status') in ["paid", "paid_over"]:
                order_id = str(data.get('order_id') or '').strip()
                if not order_id:
                    # Legacy invoices stored payment_id only inside description JSON.
                    try:
                        desc_meta = json.loads(data.get('description') or '{}')
                        if isinstance(desc_meta, dict):
                            order_id = str(desc_meta.get('payment_id') or '').strip()
                    except Exception:
                        order_id = ''
                if not order_id:
                    logger.warning("Heleket webhook: missing order_id/payment_id")
                    return 'OK', 200

                pending_meta = None
                try:
                    pending_meta = rw_repo.get_pending_metadata(order_id)
                except Exception as e:
                    logger.error(f"Heleket webhook: failed to read pending for {order_id}: {e}", exc_info=True)

                if not pending_meta:
                    logger.warning(f"Heleket webhook: no pending transaction for order_id={order_id}")
                    return 'OK', 200

                if not _pending_method_allowed(pending_meta, "Heleket"):
                    logger.warning(
                        f"Heleket webhook: order_id={order_id} is not a Heleket pending "
                        f"(payment_method={pending_meta.get('payment_method')!r})"
                    )
                    return 'OK', 200

                expected_amount = _pending_expected_amount(pending_meta)
                got_amount = _parse_decimal_amount(
                    data.get('amount') if data.get('amount') is not None else data.get('payment_amount'),
                    log_prefix=f"Heleket webhook order_id={order_id}",
                )
                if expected_amount is None or got_amount is None:
                    logger.warning(f"Heleket webhook: amount missing/unparseable for order_id={order_id}")
                    return 'OK', 200
                if got_amount != expected_amount:
                    logger.warning(
                        f"Heleket webhook: amount mismatch for {order_id}: got={got_amount}, expected={expected_amount}"
                    )
                    return 'OK', 200

                metadata = find_and_complete_pending_transaction(order_id)
                if not metadata:
                    return 'OK', 200

                try:
                    _handle_promo_after_payment(metadata)
                except Exception:
                    pass

                metadata.setdefault('payment_method', 'Heleket')
                heleket_uuid = str(data.get('uuid') or '').strip()
                if heleket_uuid:
                    metadata['heleket_uuid'] = heleket_uuid
                _dispatch_payment_processing(metadata)
            
            return 'OK', 200
        except Exception as e:
            logger.error(f"Ошибка в обработчике вебхука Heleket: {e}", exc_info=True)
            return 'Error', 500
        
    @csrf.exempt
    @flask_app.route('/ton-webhook', methods=['POST'])
    def ton_webhook_handler():
        """TonAPI webhook (hardened):
        - requires secret header/token (SHOPBOT_TON_WEBHOOK_SECRET or setting ton_webhook_secret)
        - optional IP allowlist (SHOPBOT_TON_WEBHOOK_IP_ALLOWLIST)
        - amount check + idempotency enforced inside find_and_complete_ton_transaction
        """
        try:
            if not _require_ton_webhook_secret():
                return 'Forbidden', 403

            # Optional IP allowlist
            allowlist_raw = (os.getenv('SHOPBOT_TON_WEBHOOK_IP_ALLOWLIST') or '').strip()
            if allowlist_raw:
                allow = {ip.strip() for ip in allowlist_raw.split(',') if ip.strip()}
                if allow and _get_client_ip() not in allow:
                    logger.warning(f"Ton webhook: rejected by IP allowlist. ip={_get_client_ip()}")
                    return 'Forbidden', 403

            data = request.get_json(silent=True) or {}
            logger.info(f"Получен вебхук TonAPI: {data}")

            # TonAPI webhook payload (tonconsole / rt.tonapi.io) includes txs or in_progress_txs arrays
            txs = []
            if isinstance(data, dict):
                txs.extend(data.get('in_progress_txs', []) or [])
                txs.extend(data.get('txs', []) or [])

            for tx in txs:
                if not isinstance(tx, dict):
                    continue
                in_msg = tx.get('in_msg') or {}
                if not isinstance(in_msg, dict):
                    continue
                payment_id = (in_msg.get('decoded_comment') or '').strip()
                if not payment_id:
                    continue

                try:
                    amount_nano = int(in_msg.get('value', 0) or 0)
                except Exception:
                    amount_nano = 0
                amount_ton = float(amount_nano / 1_000_000_000)

                metadata = find_and_complete_ton_transaction(payment_id, amount_ton)
                if not metadata:
                    continue

                logger.info(f"TON Payment successful for payment_id: {payment_id}")
                metadata.setdefault('payment_method', 'Ton')
                _dispatch_payment_processing(metadata)

            return 'OK', 200
        except Exception as e:
            logger.error(f"Ошибка в обработчике вебхука TonAPI: {e}", exc_info=True)
            return 'Error', 500





    def _ym_get_redirect_uri():
        try:
            saved = (get_setting("yoomoney_redirect_uri") or "").strip()
        except Exception:
            saved = ""
        if saved:
            return saved
        root = request.url_root.rstrip('/')
        return f"{root}/yoomoney/callback"

    @flask_app.route('/yoomoney/connect')
    @login_required
    def yoomoney_connect_route():
        client_id = (get_setting('yoomoney_client_id') or '').strip()
        if not client_id:
            flash('Укажите YooMoney client_id в настройках.', 'warning')
            return redirect(url_for('settings_page', tab='payments'))
        redirect_uri = _ym_get_redirect_uri()
        scope = 'operation-history operation-details account-info'
        state = secrets.token_urlsafe(32)
        session['yoomoney_oauth_state'] = state
        qs = urllib.parse.urlencode({
            'client_id': client_id,
            'response_type': 'code',
            'scope': scope,
            'redirect_uri': redirect_uri,
            'state': state,
        })
        url = f"https://yoomoney.ru/oauth/authorize?{qs}"
        return redirect(url)

    @csrf.exempt
    @flask_app.route('/yoomoney/callback')
    @login_required
    def yoomoney_callback_route():
        expected_state = session.pop('yoomoney_oauth_state', None)
        got_state = (request.args.get('state') or '').strip()
        if (
            not expected_state
            or not got_state
            or not compare_digest(str(expected_state), str(got_state))
        ):
            flash('YooMoney: неверный или отсутствующий state.', 'danger')
            return redirect(url_for('settings_page', tab='payments'))
        code = (request.args.get('code') or '').strip()
        if not code:
            flash('YooMoney: не получен code из OAuth.', 'danger')
            return redirect(url_for('settings_page', tab='payments'))
        client_id = (get_setting('yoomoney_client_id') or '').strip()
        client_secret = (get_setting('yoomoney_client_secret') or '').strip()
        redirect_uri = _ym_get_redirect_uri()
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
        }
        if client_secret:
            data['client_secret'] = client_secret
        try:
            encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request('https://yoomoney.ru/oauth/token', data=encoded, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_text = resp.read().decode('utf-8', errors='ignore')
            try:
                payload = json.loads(resp_text)
            except Exception:
                payload = {}
            token = (payload.get('access_token') or '').strip()
            if not token:
                flash(f"Не удалось получить access_token от YooMoney: {payload}", 'danger')
                return redirect(url_for('settings_page', tab='payments'))
            update_setting('yoomoney_api_token', token)
            flash('YooMoney: токен успешно сохранён.', 'success')
        except Exception as e:
            logger.error(f"YooMoney OAuth callback error: {e}", exc_info=True)
            flash(f'Ошибка при обмене кода на токен: {e}', 'danger')
        return redirect(url_for('settings_page', tab='payments'))

    @flask_app.route('/yoomoney/check', methods=['GET','POST'])
    @login_required
    def yoomoney_check_route():
        token = (get_setting('yoomoney_api_token') or '').strip()
        if not token:
            flash('YooMoney: токен не задан.', 'warning')
            return redirect(url_for('settings_page', tab='payments'))

        try:
            req = urllib.request.Request('https://yoomoney.ru/api/account-info', headers={'Authorization': f'Bearer {token}'}, method='POST')
            with urllib.request.urlopen(req, timeout=15) as resp:
                ai_text = resp.read().decode('utf-8', errors='ignore')
                ai_status = resp.status
                ai_headers = dict(resp.headers)
        except Exception as e:
            flash(f'YooMoney account-info: ошибка запроса: {e}', 'danger')
            return redirect(url_for('settings_page', tab='payments'))
        try:
            ai = json.loads(ai_text)
        except Exception:
            ai = {}
        if ai_status != 200:
            www = ai_headers.get('WWW-Authenticate', '')
            flash(f"YooMoney account-info HTTP {ai_status}. {www}", 'danger')
            return redirect(url_for('settings_page', tab='payments'))
        account = ai.get('account') or ai.get('account_number') or '—'

        try:
            body = urllib.parse.urlencode({'records': '1'}).encode('utf-8')
            req2 = urllib.request.Request('https://yoomoney.ru/api/operation-history', data=body, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req2, timeout=15) as resp2:
                oh_text = resp2.read().decode('utf-8', errors='ignore')
                oh_status = resp2.status
        except Exception as e:
            flash(f'YooMoney operation-history: ошибка запроса: {e}', 'warning')
            oh_status = None
        if oh_status == 200:
            flash(f'YooMoney: токен валиден. Кошелёк: {account}', 'success')
        elif oh_status is not None:
            flash(f'YooMoney operation-history HTTP {oh_status}. Проверьте scope operation-history и соответствие кошелька.', 'danger')
        else:
            flash('YooMoney: не удалось проверить operation-history.', 'warning')
        return redirect(url_for('settings_page', tab='payments'))


    @flask_app.route('/api/button-configs/<menu_type>')
    @login_required
    @csrf.exempt
    def get_button_configs_api(menu_type):
        """Get button configurations for a specific menu type (including inactive for admin)"""
        try:
            # Для конструктора кнопок возвращаем ВСЕ кнопки (включая неактивные)
            configs = get_button_configs_admin(menu_type, include_inactive=True)
            return jsonify({'success': True, 'data': configs})
        except Exception as e:
            logger.error(f"Error getting button configs for {menu_type}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/button-configs', methods=['POST'])
    @login_required
    @csrf.exempt
    def create_button_config_api():
        """Create a new button configuration"""
        try:
            data = request.json
            required_fields = ['menu_type', 'button_id', 'text']
            for field in required_fields:
                if field not in data:
                    return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

            success = create_button_config(
                menu_type=data['menu_type'],
                button_id=data['button_id'],
                text=data['text'],
                callback_data=data.get('callback_data'),
                url=data.get('url'),
                row_position=data.get('row_position', 0),
                column_position=data.get('column_position', 0),
                button_width=data.get('button_width', 1),
                metadata=data.get('metadata')
            )
            
            if success:
                return jsonify({'success': True, 'message': 'Button configuration created'})
            else:
                return jsonify({'success': False, 'error': 'Failed to create button configuration'}), 500
        except Exception as e:
            logger.error(f"Error creating button config: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/button-configs/<int:button_id>', methods=['PUT'])
    @login_required
    @csrf.exempt
    def update_button_config_api(button_id):
        """Update an existing button configuration"""
        try:
            data = request.json
            logger.info(f"API update request for button {button_id}: {data}")
            
            success = update_button_config(
                button_id=button_id,
                text=data.get('text'),
                callback_data=data.get('callback_data'),
                url=data.get('url'),
                row_position=data.get('row_position'),
                column_position=data.get('column_position'),
                button_width=data.get('button_width'),
                is_active=data.get('is_active'),
                sort_order=data.get('sort_order'),
                metadata=data.get('metadata')
            )
            
            if success:
                logger.info(f"Successfully updated button {button_id}")
                return jsonify({'success': True, 'message': 'Button configuration updated'})
            else:
                logger.error(f"Failed to update button {button_id}")
                return jsonify({'success': False, 'error': 'Failed to update button configuration'}), 500
        except Exception as e:
            logger.error(f"Error updating button config {button_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/button-configs/<int:button_id>', methods=['DELETE'])
    @login_required
    @csrf.exempt
    def delete_button_config_api(button_id):
        """Delete a button configuration"""
        try:
            success = delete_button_config(button_id)
            if success:
                return jsonify({'success': True, 'message': 'Button configuration deleted'})
            else:
                return jsonify({'success': False, 'error': 'Failed to delete button configuration'}), 500
        except Exception as e:
            logger.error(f"Error deleting button config {button_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    @flask_app.route('/api/button-configs/<menu_type>/reorder', methods=['POST'])
    @login_required
    @csrf.exempt
    def reorder_button_configs_api(menu_type):
        """Reorder button configurations for a menu type"""
        try:
            data = request.json
            button_orders = data.get('button_orders', [])


            
            success = reorder_button_configs(menu_type, button_orders)
            
            if success:
                logger.info(f"Successfully reordered buttons for {menu_type}")
                return jsonify({'success': True, 'message': 'Button configurations reordered'})
            else:
                logger.error(f"Failed to reorder buttons for {menu_type}")
                return jsonify({'success': False, 'error': 'Failed to reorder button configurations'}), 500
        except Exception as e:
            logger.error(f"Error reordering button configs for {menu_type}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # =============================
    # Franchise (managed clone bots) — web panel
    # =============================

    def _franchise_db_connect():
        conn = sqlite3.connect(rw_repo.DB_FILE)
        conn.row_factory = sqlite3.Row
        return conn

    def _franchise_totals() -> dict:
        res = {
            "total_bots": 0,
            "active_bots": 0,
            "total_users": 0,
            "gross_paid_card": 0.0,
            "commission_total": 0.0,
            "requested_withdraw": 0.0,
            "pending_withdraw": 0.0,
            # Backward/templating compatibility (some templates may refer to *_sum)
            "pending_withdraw_sum": 0.0,
            "pending_withdraw_count": 0,
            "available_total": 0.0,
        }
        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1), SUM(CASE WHEN COALESCE(is_active,1)=1 THEN 1 ELSE 0 END) FROM managed_bots")
                row = cur.fetchone() or (0, 0)
                res["total_bots"] = int(row[0] or 0)
                res["active_bots"] = int(row[1] or 0)

                cur.execute("SELECT COUNT(1) FROM factory_user_activity")
                res["total_users"] = int((cur.fetchone() or [0])[0] or 0)

                cur.execute("SELECT COALESCE(SUM(amount_rub),0), COALESCE(SUM(commission_rub),0) FROM partner_commissions")
                row = cur.fetchone() or (0, 0)
                res["gross_paid_card"] = float(row[0] or 0)
                res["commission_total"] = float(row[1] or 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount_rub),0)
                    FROM partner_withdraw_requests
                    WHERE status IN ('pending','approved','paid')
                    """
                )
                res["requested_withdraw"] = float((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount_rub),0), COUNT(1)
                    FROM partner_withdraw_requests
                    WHERE status = 'pending'
                    """
                )
                row = cur.fetchone() or (0, 0)
                res["pending_withdraw"] = float(row[0] or 0)
                res["pending_withdraw_count"] = int(row[1] or 0)

                # Keep compatibility alias
                res["pending_withdraw_sum"] = res["pending_withdraw"]

            res["pending_withdraw_sum"] = float(res.get("pending_withdraw") or 0)

            res["available_total"] = max(0.0, res["commission_total"] - res["requested_withdraw"])
        except Exception:
            pass
        return res

    def _franchise_list_bots(q: str | None = None) -> list[dict]:
        q = (q or "").strip()
        where = ""
        params = []

        if q:
            q_norm = q.lstrip('@').strip()
            if q_norm.isdigit():
                # allow searching by internal id, telegram bot id, owner telegram id
                where = "WHERE mb.id = ? OR mb.telegram_bot_user_id = ? OR mb.owner_telegram_id = ?"
                v = int(q_norm)
                params.extend([v, v, v])
            else:
                where = "WHERE COALESCE(mb.username,'') LIKE ?"
                params.append(f"%{q_norm}%")

        sql = f"""
            SELECT
                mb.id,
                mb.telegram_bot_user_id,
                mb.username,
                mb.owner_telegram_id,
                mb.referrer_bot_id,
                mb.is_active,
                mb.created_at,
                (SELECT COUNT(1) FROM factory_user_activity fua WHERE fua.bot_id = mb.id) AS users_count,
                (SELECT COALESCE(SUM(messages_count),0) FROM factory_user_activity fua WHERE fua.bot_id = mb.id) AS messages_total,
                (SELECT COALESCE(SUM(amount_rub),0) FROM partner_commissions pc WHERE pc.bot_id = mb.id) AS gross_paid_card,
                (SELECT COALESCE(SUM(commission_rub),0) FROM partner_commissions pc WHERE pc.bot_id = mb.id) AS commission_total,
                (SELECT COALESCE(SUM(amount_rub),0) FROM partner_withdraw_requests pw WHERE pw.bot_id = mb.id AND pw.status IN ('pending','approved','paid')) AS requested_withdraw,
                (SELECT COALESCE(SUM(amount_rub),0) FROM partner_withdraw_requests pw WHERE pw.bot_id = mb.id AND pw.status = 'pending') AS pending_withdraw,
                (SELECT COUNT(1) FROM partner_withdraw_requests pw WHERE pw.bot_id = mb.id AND pw.status = 'pending') AS pending_withdraw_count,
                mb.token
            FROM managed_bots mb
            {where}
            ORDER BY mb.id DESC
            LIMIT 300
        """

        bots = []
        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall() or []
                for r in rows:
                    d = dict(r)
                    d["is_active"] = bool(int(d.get("is_active") or 0))
                    d["token_masked"] = "задан" if (d.get("token") or "").strip() else ""
                    d.pop("token", None)
                    try:
                        d["available"] = max(0.0, float(d.get("commission_total") or 0) - float(d.get("requested_withdraw") or 0))
                    except Exception:
                        d["available"] = 0.0
                    bots.append(d)
        except Exception:
            bots = []
        return bots

    def _franchise_get_bot(bot_id: int) -> dict | None:
        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM managed_bots WHERE id = ? LIMIT 1", (int(bot_id),))
                row = cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                d["is_active"] = bool(int(d.get("is_active") or 0))
                d["token_masked"] = "задан" if (d.get("token") or "").strip() else ""
                d.pop("token", None)
                return d
        except Exception:
            return None

    def _franchise_bot_stats(bot_id: int) -> dict:
        res = {
            "users_count": 0,
            "messages_total": 0,
            "gross_paid_card": 0.0,
            "commission_total": 0.0,
            "requested_withdraw": 0.0,
            "pending_withdraw": 0.0,
            "pending_withdraw_count": 0,
            "available": 0.0,
        }
        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(1), COALESCE(SUM(messages_count),0) FROM factory_user_activity WHERE bot_id = ?", (int(bot_id),))
                row = cur.fetchone() or (0, 0)
                res["users_count"] = int(row[0] or 0)
                res["messages_total"] = int(row[1] or 0)

                cur.execute("SELECT COALESCE(SUM(amount_rub),0), COALESCE(SUM(commission_rub),0) FROM partner_commissions WHERE bot_id = ?", (int(bot_id),))
                row = cur.fetchone() or (0, 0)
                res["gross_paid_card"] = float(row[0] or 0)
                res["commission_total"] = float(row[1] or 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount_rub),0)
                    FROM partner_withdraw_requests
                    WHERE bot_id = ? AND status IN ('pending','approved','paid')
                    """,
                    (int(bot_id),),
                )
                res["requested_withdraw"] = float((cur.fetchone() or [0])[0] or 0)

                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount_rub),0), COUNT(1)
                    FROM partner_withdraw_requests
                    WHERE bot_id = ? AND status = 'pending'
                    """,
                    (int(bot_id),),
                )
                row = cur.fetchone() or (0, 0)
                res["pending_withdraw"] = float(row[0] or 0)
                res["pending_withdraw_count"] = int(row[1] or 0)

            res["available"] = max(0.0, res["commission_total"] - res["requested_withdraw"])
        except Exception:
            pass
        return res

    @flask_app.route('/franchise')
    @login_required
    def franchise_page():
        q = (request.args.get('q') or '').strip()
        totals = _franchise_totals()
        bots = _franchise_list_bots(q=q)
        common_data = get_common_template_data()
        return render_template('franchise.html', totals=totals, bots=bots, q=q, **common_data)

    @flask_app.route('/franchise/bot/<int:bot_id>')
    @login_required
    def franchise_bot_page(bot_id: int):
        bot = _franchise_get_bot(bot_id)
        if not bot:
            flash('Бот не найден.', 'warning')
            return redirect(url_for('franchise_page'))

        stats = _franchise_bot_stats(bot_id)
        activity = []
        commissions = []
        withdraws = []

        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT user_id, first_seen, last_seen, messages_count
                    FROM factory_user_activity
                    WHERE bot_id = ?
                    ORDER BY last_seen DESC
                    LIMIT 200
                    """,
                    (int(bot_id),),
                )
                activity = [dict(r) for r in (cur.fetchall() or [])]

                cur.execute(
                    """
                    SELECT id, payment_id, user_id, amount_rub, commission_percent, commission_rub, payment_method, created_at
                    FROM partner_commissions
                    WHERE bot_id = ?
                    ORDER BY created_at DESC
                    LIMIT 200
                    """,
                    (int(bot_id),),
                )
                commissions = [dict(r) for r in (cur.fetchall() or [])]

                cur.execute(
                    """
                    SELECT id, owner_telegram_id, amount_rub, status, comment, bank, requisite_type, requisite_value, created_at
                    FROM partner_withdraw_requests
                    WHERE bot_id = ?
                    ORDER BY created_at DESC
                    LIMIT 200
                    """,
                    (int(bot_id),),
                )
                withdraws = [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            activity, commissions, withdraws = [], [], []

        common_data = get_common_template_data()
        return render_template(
            'franchise_bot.html',
            bot=bot,
            stats=stats,
            activity=activity,
            commissions=commissions,
            withdraw_requests=withdraws,
            withdraws=withdraws,
            **common_data,
        )

    @flask_app.route('/franchise/bot/<int:bot_id>/toggle', methods=['POST'])
    @login_required
    def franchise_toggle_bot_route(bot_id: int):
        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COALESCE(is_active,1) FROM managed_bots WHERE id = ? LIMIT 1", (int(bot_id),))
                row = cur.fetchone()
                if not row:
                    flash('Бот не найден.', 'warning')
                    return redirect(url_for('franchise_page'))
                current = int(row[0] or 0)
                new_val = 0 if current == 1 else 1
                cur.execute("UPDATE managed_bots SET is_active = ? WHERE id = ?", (new_val, int(bot_id)))
                conn.commit()
        except Exception:
            flash('Не удалось обновить статус бота.', 'danger')
            return redirect(request.referrer or url_for('franchise_page'))

        try:
            _run_on_root_bot_loop(
                lambda svc, i=int(bot_id), v=new_val: svc.start_bot(i) if v == 1 else svc.stop_bot(i)
            )
        except Exception as e:
            logger.warning(f"Не удалось применить is_active для bot_id={bot_id} на лету: {e}")

        flash('Статус бота обновлён.', 'success')
        return redirect(request.referrer or url_for('franchise_page'))

    @flask_app.route('/franchise/bot/<int:bot_id>/delete', methods=['POST'])
    @login_required
    def franchise_delete_bot_route(bot_id: int):
        bot_id = int(bot_id)
        existing = _franchise_get_bot(bot_id)
        if not existing:
            flash('Бот не найден.', 'warning')
            return redirect(url_for('franchise_page'))

        try:
            _run_on_root_bot_loop(lambda svc, i=bot_id: svc.stop_bot(i))
        except Exception as e:
            logger.warning(f"Не удалось остановить bot_id={bot_id} перед удалением: {e}")

        try:
            deleted = rw_repo.delete_managed_bot(bot_id)
        except Exception:
            logger.error(f"Не удалось удалить managed bot id={bot_id}", exc_info=True)
            deleted = False

        if not deleted:
            flash('Не удалось удалить бота.', 'danger')
            return redirect(request.referrer or url_for('franchise_page'))

        flash('Бот удалён. Активность клона очищена. Одобренные/выплаченные заявки на вывод сохранены.', 'success')
        return redirect(url_for('franchise_page'))

    @flask_app.route('/franchise/withdraw/<int:req_id>/status', methods=['POST'])
    @login_required
    def franchise_withdraw_status_route(req_id: int):
        status = (request.form.get('status') or '').strip().lower()
        if status not in {'pending', 'approved', 'paid', 'rejected'}:
            flash('Некорректный статус.', 'warning')
            return redirect(request.referrer or url_for('franchise_page'))

        try:
            with _franchise_db_connect() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE partner_withdraw_requests SET status = ? WHERE id = ?", (status, int(req_id)))
                conn.commit()
                if cur.rowcount <= 0:
                    flash('Заявка не найдена.', 'warning')
                    return redirect(request.referrer or url_for('franchise_page'))
        except Exception:
            flash('Не удалось обновить статус заявки.', 'danger')
            return redirect(request.referrer or url_for('franchise_page'))

        flash('Статус заявки обновлён.', 'success')
        return redirect(request.referrer or url_for('franchise_page'))

    @flask_app.route('/button-constructor')
    @login_required
    def button_constructor_page():
        """Button constructor page"""
        template_data = get_common_template_data()
        return render_template('button_constructor.html', **template_data)

    return flask_app




def _coerce_checkbox(value: str) -> str:
    # HTML checkbox returns "on" when checked; hidden fallback sends "off" always.
    return "true" if str(value).lower() in ("on", "true", "1", "yes") else "false"
