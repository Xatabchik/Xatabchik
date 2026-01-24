import os
import logging
import asyncio
import threading
import json
import sqlite3
import hashlib
import hmac
import bcrypt
import html as html_escape
import base64
import time
import uuid
from decimal import Decimal
from hmac import compare_digest
from datetime import datetime, timezone, timedelta
from functools import wraps
from math import ceil
from flask import Flask, request, render_template, redirect, url_for, flash, session, current_app, jsonify, send_file
from flask_wtf.csrf import CSRFProtect, generate_csrf
import secrets
import urllib.parse
import urllib.request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

from shop_bot.modules import remnawave_api
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
    get_all_settings, update_setting, get_all_hosts, get_plans_for_host,
    create_host, delete_host, create_plan, delete_plan, update_plan, get_user_count,
    get_total_keys_count, get_total_spent_sum, get_daily_stats_for_charts,
    get_recent_transactions, get_paginated_transactions, get_all_users, get_user_keys,
    ban_user, unban_user, delete_user_keys, get_setting, find_and_complete_ton_transaction,
    find_and_complete_pending_transaction,
    get_tickets_paginated, get_open_tickets_count, get_ticket, get_ticket_messages,
    add_support_message, set_ticket_status, delete_ticket,
    get_closed_tickets_count, get_all_tickets_count, update_host_subscription_url,
    update_host_url, update_host_name, update_host_ssh_settings, get_latest_speedtest, get_speedtests,
    get_all_keys, get_keys_for_user, delete_key_by_id, update_key_comment, get_keys_paginated,
    get_balance, adjust_user_balance, get_referrals_for_user,

    get_users_paginated, get_keys_counts_for_users,

    get_all_ssh_targets, get_ssh_target, create_ssh_target, update_ssh_target_fields, delete_ssh_target,
    get_user,
    get_admin_stats,
    list_gift_tokens,
)
from shop_bot.data_manager.database import (
    get_button_configs, create_button_config, update_button_config, 
    delete_button_config, reorder_button_configs
)
from shop_bot.data_manager.database import update_host_remnawave_settings, get_plan_by_id

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


def _dispatch_payment_processing(metadata: dict) -> None:
    """Fulfill paid orders even when the polling bot loop isn't running.

    If the main bot + EVENT_LOOP are available, schedule into that loop.
    Otherwise, run in a background thread using a temporary Bot instance.
    """
    payment_processor = handlers.process_successful_payment

    loop = None
    try:
        loop = current_app.config.get('EVENT_LOOP')
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

ALL_SETTINGS_KEYS = [
    "panel_login",
    "panel_password",
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
]

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
    

    flask_app.config['SECRET_KEY'] = os.getenv('SHOPBOT_SECRET_KEY') or secrets.token_hex(32)
    flask_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    flask_app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv("SHOPBOT_SESSION_SAMESITE", "Lax"),
        SESSION_COOKIE_SECURE=os.getenv("SHOPBOT_SESSION_SECURE", "true").lower() in ("1","true","yes"),
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
                _, availability_error = rw_repo.check_promo_code_available(promo_code, user_id)
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
            loop = current_app.config.get('EVENT_LOOP')
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

        return {
            'current_year': datetime.utcnow().year,
            'csrf_token': generate_csrf
        }

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login_page'))
            return f(*args, **kwargs)
        return decorated_function

    _login_attempts = {}

    def _rate_limit_login(ip: str, limit: int = 10, window_sec: int = 600) -> bool:
        now = time.time()
        attempts = _login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < window_sec]
        if len(attempts) >= limit:
            _login_attempts[ip] = attempts
            return False
        attempts.append(now)
        _login_attempts[ip] = attempts
        return True

    def _verify_panel_password(stored: str, provided: str) -> bool:
        if not stored:
            return False
        try:
            if stored.startswith("$2"):
                return bool(bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8")))
        except Exception:
            pass
        # legacy/plaintext
        return compare_digest(str(stored), str(provided))

    @flask_app.route('/login', methods=['GET', 'POST'])
    def login_page():
        settings = get_all_settings()
        if request.method == 'POST':
            ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[0].strip()
            if not _rate_limit_login(ip):
                flash('Слишком много попыток. Подождите несколько минут.', 'danger')
                return render_template('login.html'), 429
            username = request.form.get('username') or ''
            password = request.form.get('password') or ''
            stored_user = settings.get('panel_login') or ''
            stored_pass = settings.get('panel_password') or ''
            if username == stored_user and _verify_panel_password(str(stored_pass), str(password)):
                # migrate legacy/plaintext password to bcrypt hash
                if not str(stored_pass).startswith('$2'):
                    try:
                        new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        update_setting('panel_password', new_hash)
                    except Exception as e:
                        logger.warning(f'Panel password hash migration failed: {e}')
                session['logged_in'] = True
                session.permanent = bool(request.form.get('remember_me'))
                return redirect(url_for('dashboard_page'))
            else:
                flash('Неверный логин или пароль', 'danger')
        return render_template('login.html')

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
        return {
            "bot_status": bot_status,
            "all_settings_ok": all_settings_ok,
            "support_bot_status": support_bot_status,
            "support_settings_ok": support_settings_ok,
            "open_tickets_count": open_tickets_count,
            "closed_tickets_count": closed_tickets_count,
            "all_tickets_count": all_tickets_count,
            "brand_title": settings.get('panel_brand_title') or 'Remnawave Control',
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
        
        return render_template(
            'dashboard.html',
            hosts=hosts,
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

        # Gifts
        gifts_total = 0
        gifts_used = 0
        gifts_activations = 0
        try:
            tokens = list_gift_tokens(active_only=False) or []
            gifts_total = len(tokens)
            for t in tokens:
                try:
                    gifts_used += int(t.get('activations_used') or 0)
                except Exception:
                    pass
                try:
                    gifts_activations += int(t.get('activation_limit') or 1)
                except Exception:
                    gifts_activations += 1
        except Exception:
            pass

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
            'gifts_activations': gifts_activations,
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
        return render_template('monitor.html', hosts=hosts, ssh_targets=ssh_targets, **common_data)

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
                '<span class="badge bg-green-lt" title="Открытые тикеты">'
                '<span class="status-dot status-dot-animated bg-green"></span>'
                f" {count}</span>"
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
                user['keys_count'] = int(user.get('keys_count') or 0)
            except Exception:
                user['keys_count'] = 0
            try:
                user['active_keys_count'] = int(user.get('active_keys_count') or 0)
            except Exception:
                user['active_keys_count'] = 0


        from math import ceil
        total_pages = ceil(total / per_page) if per_page else 1

        common_data = get_common_template_data()
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
                user['keys_count'] = int(user.get('keys_count') or 0)
            except Exception:
                user['keys_count'] = 0
            try:
                user['active_keys_count'] = int(user.get('active_keys_count') or 0)
            except Exception:
                user['active_keys_count'] = 0
        return render_template('partials/users_table.html', users=users)


    @flask_app.route('/users/<int:user_id>/keys.partial')
    @login_required
    def user_keys_partial(user_id: int):
        try:
            keys = get_user_keys(user_id)
        except Exception:
            keys = []
        return render_template('partials/user_keys_table.html', keys=keys)


    @flask_app.route('/users/<int:user_id>/referrals.json')
    @login_required
    def user_referrals_json(user_id: int):
        try:
            refs = get_referrals_for_user(user_id) or []
            return jsonify({"ok": True, "items": refs, "count": len(refs)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500


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
                    loop = current_app.config.get('EVENT_LOOP')
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

    @flask_app.route('/admin/keys')
    @login_required
    def admin_keys_page():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        keys = []
        total = 0
        try:
            keys, total = get_keys_paginated(page=page, per_page=per_page)
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
        return render_template(
            'admin_keys.html',
            keys=keys,
            hosts=hosts,
            users=users,
            current_page=page,
            total_pages=total_pages,
            per_page=per_page,
            **common_data,
        )


    @flask_app.route('/admin/keys/table.partial')
    @login_required
    def admin_keys_table_partial():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        keys = []
        try:
            keys, _ = get_keys_paginated(page=page, per_page=per_page)
        except Exception:
            keys = []
        return render_template('partials/admin_keys_table.html', keys=keys)

    @flask_app.route('/admin/keys/pagination.partial')
    @login_required
    def admin_keys_pagination_partial():
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        _, total = get_keys_paginated(page=page, per_page=per_page)
        total_pages = ceil(total / per_page) if per_page else 1
        return render_template(
            'partials/admin_keys_pagination.html',
            current_page=page,
            total_pages=total_pages,
            per_page=per_page,
        )

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
                loop = current_app.config.get('EVENT_LOOP')
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
        if plan_id:
            plan = get_plan_by_id(plan_id)
            if plan:
                try:
                    months = int(plan.get('months') or 0)
                except Exception:
                    months = 0
                days_total += months * 30
                plan_device_limit = plan.get('hwid_device_limit')
        if custom_days_raw:
            try:
                days_total += max(0, int(custom_days_raw))
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
                description=comment,
            )
            if not key_id:
                return jsonify({"ok": False, "error": "db_failed"}), 500


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
                    loop = current_app.config.get('EVENT_LOOP')
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


            expiry_ms: int | None = None
            if expiry_str:
                try:
                    expiry_dt = datetime.fromisoformat(expiry_str)
                    expiry_ms = int(expiry_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
                except Exception:
                    return jsonify({"ok": False, "error": "invalid_expiry"}), 400
            if expiry_ms is None and days_total > 0:
                expiry_ms = int((datetime.utcnow() + timedelta(days=days_total)).replace(tzinfo=timezone.utc).timestamp() * 1000)


            base_local = f"gift-{uuid.uuid4().hex[:8]}"
            domain = "bot.local"
            attempt = 0
            while True:
                candidate_email = f"{base_local if attempt == 0 else base_local + '-' + str(attempt)}@{domain}"
                if not rw_repo.get_key_by_email(candidate_email):
                    break
                attempt += 1


            try:
                result = asyncio.run(remnawave_api.create_or_update_key_on_host(
                    host_name,
                    candidate_email,
                    expiry_timestamp_ms=expiry_ms or None,
                    description=comment or 'Gift key (created via admin panel)',
                    tag='GIFT',
                    hwid_device_limit=hwid_device_limit,
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
                description=comment or 'Gift key',
            )
            if not key_id:
                return jsonify({"ok": False, "error": "db_failed"}), 500


            return jsonify({
                "ok": True,
                "key_id": key_id,
                "email": candidate_email,
                "uuid": result.get('client_uuid'),
                "expiry_ms": result.get('expiry_timestamp_ms') or expiry_ms,
                "connection": result.get('connection_string'),
                "note": "Gift key created (not bound to Telegram user)."
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
                    loop = current_app.config.get('EVENT_LOOP')
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
                    loop = current_app.config.get('EVENT_LOOP')
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
        ssh_password = request.form.get('ssh_password')
        ssh_key_path = (request.form.get('ssh_key_path') or '').strip() or None
        ssh_port = None
        try:
            ssh_port = int(ssh_port_raw) if ssh_port_raw else None
        except Exception:
            ssh_port = None
        ok = update_host_ssh_settings(host_name, ssh_host=ssh_host, ssh_port=ssh_port, ssh_user=ssh_user,
                                      ssh_password=ssh_password, ssh_key_path=ssh_key_path)
        flash('SSH-параметры обновлены.' if ok else 'Не удалось обновить SSH-параметры.', 'success' if ok else 'danger')
        return redirect(request.referrer or url_for('settings_page'))


    @flask_app.route('/admin/ssh-targets/<target_name>/speedtest/run', methods=['POST'])
    @login_required
    def run_ssh_target_speedtest_route(target_name: str):
        logger.info(f"Панель: запущен спидтест для SSH-цели '{target_name}'")
        try:
            res = asyncio.run(speedtest_runner.run_and_store_ssh_speedtest_for_target(target_name))
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
            if method == 'ssh':
                res = asyncio.run(speedtest_runner.run_and_store_ssh_speedtest(host_name))
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

        try:
            res = asyncio.run(speedtest_runner.auto_install_speedtest_on_host(host_name))
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
                        loop = current_app.config.get('EVENT_LOOP')
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
                        loop = current_app.config.get('EVENT_LOOP')
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
                        loop = current_app.config.get('EVENT_LOOP')
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
                        loop = current_app.config.get('EVENT_LOOP')
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
                        loop = current_app.config.get('EVENT_LOOP')
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
                        loop = current_app.config.get('EVENT_LOOP')
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

        messages = get_ticket_messages(ticket_id)
        common_data = get_common_template_data()
        return render_template('ticket.html', ticket=ticket, messages=messages, **common_data)

    @flask_app.route('/support/<int:ticket_id>/messages.json')
    @login_required
    def support_ticket_messages_api(ticket_id):
        ticket = get_ticket(ticket_id)
        if not ticket:
            return jsonify({"error": "not_found"}), 404
        messages = get_ticket_messages(ticket_id) or []
        items = [
            {
                "sender": m.get('sender'),
                "content": m.get('content'),
                "created_at": m.get('created_at')
            }
            for m in messages
        ]
        return jsonify({
            "ticket_id": ticket_id,
            "status": ticket.get('status'),
            "messages": items
        })

    @flask_app.route('/support/<int:ticket_id>/delete', methods=['POST'])
    @login_required
    def delete_support_ticket_route(ticket_id: int):
        ticket = get_ticket(ticket_id)
        if not ticket:
            flash('Тикет не найден.', 'danger')
            return redirect(url_for('support_list_page'))
        try:
            bot = _support_bot_controller.get_bot_instance()
            loop = current_app.config.get('EVENT_LOOP')
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
            ]
            for checkbox_key in checkbox_keys:
                values = request.form.getlist(checkbox_key) or ['off']
                raw = values[-1]
                value = 'true' if str(raw).lower() in ('on','true','1','yes') else 'false'
                update_setting(checkbox_key, value)

            for key in ALL_SETTINGS_KEYS:
                if key in checkbox_keys or key == 'panel_password':
                    continue
                if key in request.form:
                    update_setting(key, request.form.get(key))

            flash('Настройки сохранены.', 'success')
            next_hash = (request.form.get('next_hash') or '').strip() or '#panel'
            next_tab = (next_hash[1:] if next_hash.startswith('#') else next_hash) or 'panel'
            return redirect(url_for('settings_page', tab=next_tab))

        current_settings = get_all_settings()
        hosts = get_all_hosts()
        for host in hosts:
            host['plans'] = get_plans_for_host(host['host_name'])

            try:
                host['latest_speedtest'] = get_latest_speedtest(host['host_name'])
            except Exception:
                host['latest_speedtest'] = None

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
        return render_template('settings.html', settings=current_settings, hosts=hosts, ssh_targets=ssh_targets, backups=backups, **common_data)


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
        ssh_password = request.form.get('ssh_password') if 'ssh_password' in request.form else None
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
        try:
            res = asyncio.run(speedtest_runner.auto_install_speedtest_on_target(target_name))
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
        loop = current_app.config.get('EVENT_LOOP')
        if loop and loop.is_running():
            _support_bot_controller.set_loop(loop)
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

    @flask_app.route('/start-both-bots', methods=['POST'])
    @login_required
    def start_both_bots_route():
        main_result = _bot_controller.start()
        loop = current_app.config.get('EVENT_LOOP')
        if loop and loop.is_running():
            _support_bot_controller.set_loop(loop)
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
                loop = current_app.config.get('EVENT_LOOP')
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
                loop = current_app.config.get('EVENT_LOOP')
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
                loop = current_app.config.get('EVENT_LOOP')
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
        base_url = (request.form.get('remnawave_base_url') or '').strip()
        api_token = (request.form.get('remnawave_api_token') or '').strip()
        squad_uuid = (request.form.get('squad_uuid') or '').strip()
        if not name or not base_url or not api_token:
            flash('Укажите название хоста, базовый URL и API токен.', 'danger')
            return redirect(url_for('settings_page', tab='hosts'))


        try:
            create_host(
                name=name,
                url=base_url,
                user='',
                passwd='',
                inbound=0,
                subscription_url=None,
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
                squad_uuid=squad_uuid or None,
            )
        except Exception as e:
            logger.error(f"Не удалось сохранить Remnawave-настройки для '{name}': {e}")
            flash('Хост создан, но Remnawave-настройки сохранить не удалось.', 'warning')
            return redirect(url_for('settings_page', tab='hosts'))

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
        create_plan(
            host_name=request.form['host_name'],
            plan_name=request.form['plan_name'],
            months=int(request.form['months']),
            price=float(request.form['price'])
        )
        flash(f"Новый тариф для хоста '{request.form['host_name']}' добавлен.", 'success')
        return redirect(url_for('settings_page', tab='hosts'))

    @flask_app.route('/delete-plan/<int:plan_id>', methods=['POST'])
    @login_required
    def delete_plan_route(plan_id):
        delete_plan(plan_id)
        flash("Тариф успешно удален.", 'success')
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

        ok = update_plan(plan_id, plan_name, months_int, price_float)
        if ok:
            flash('Тариф обновлён.', 'success')
        else:
            flash('Не удалось обновить тариф (возможно, он не найден).', 'danger')
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
                # Не финальный успех — игнорируем.
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
            

            notification_type = form.get('notification_type', '')
            logger.info(f"📝 Тип уведомления: {notification_type}")
            if notification_type != 'p2p-incoming':
                logger.info(f"⏭️  Игнорируем тип уведомления: {notification_type}")
                return 'OK', 200
            

            codepro = form.get('codepro', '')
            if codepro.lower() == 'true':
                logger.info("🧪 Игнорируем тестовый платеж (codepro=true)")
                return 'OK', 200
            
            secret = get_setting('yoomoney_secret') or ''
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
            if expected != provided:
                logger.warning("🔐 Неверная подпись")
                return 'Forbidden', 403
            

            payment_id = form.get('label')
            if not payment_id:
                logger.warning("🏷️  Пустой label")
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

            merchant_id = request.headers.get("X-MerchantId", "")
            secret = request.headers.get("X-Secret", "")
            if (
                merchant_id != (get_setting('platega_merchant_id') or '')
                or secret != (get_setting('platega_secret') or '')
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

            if not payment_id:
                return 'OK', 200

            # Обрабатываем только успешное подтверждение
            if status_raw == 'CONFIRMED':
                metadata = find_and_complete_pending_transaction(payment_id)
                if metadata:
                    metadata.setdefault('payment_method', 'Platega')
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

            raw_body = request.get_data(cache=False) or b''
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

            request_data = request.get_json(silent=True) or {}
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

            # Fetch invoice details from Crypto Pay API to validate status/amount
            invoice = None
            if invoice_id_int is not None:
                try:
                    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id_int}"
                    resp = _http_json(url, headers={"Crypto-Pay-API-Token": token}, timeout=20)
                    if isinstance(resp, dict) and resp.get('ok') and isinstance(resp.get('result'), list) and resp['result']:
                        invoice = resp['result'][0]
                except Exception as e:
                    logger.error(f"CryptoBot webhook: failed to fetch invoice {invoice_id_int}: {e}", exc_info=True)

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

                metadata = find_and_complete_pending_transaction(internal_payment_id)
                if not metadata:
                    return 'OK', 200

                metadata.setdefault('payment_method', 'CryptoBot')
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
                metadata_str = data.get('description')
                if not metadata_str: return 'Error', 400
                
                metadata = json.loads(metadata_str)

                try:
                    _handle_promo_after_payment(metadata)
                except Exception:
                    pass

                metadata.setdefault('payment_method', 'Heleket')
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
        qs = urllib.parse.urlencode({
            'client_id': client_id,
            'response_type': 'code',
            'scope': scope,
            'redirect_uri': redirect_uri,
        })
        url = f"https://yoomoney.ru/oauth/authorize?{qs}"
        return redirect(url)

    @csrf.exempt
    @flask_app.route('/yoomoney/callback')
    def yoomoney_callback_route():
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
        """Get button configurations for a specific menu type"""
        try:
            configs = get_button_configs(menu_type)
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

    def _mask_token(token: str | None) -> str:
        t = (token or "").strip()
        if not t:
            return ""
        if len(t) <= 12:
            return t[:3] + "…" + t[-3:]
        return t[:6] + "…" + t[-4:]

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
                    d["token_masked"] = _mask_token(d.get("token"))
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
                d["token_masked"] = _mask_token(d.get("token"))
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

        flash('Статус бота обновлён.', 'success')
        return redirect(request.referrer or url_for('franchise_page'))

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
