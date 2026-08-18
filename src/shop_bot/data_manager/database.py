import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import hashlib
import hmac
import json
import secrets
import time
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)


_UNSET = object()


import os
if os.path.exists("/app/project/users.db"):

    DB_FILE = Path("/app/project/users.db")
elif os.path.exists("users-20251005-173430.db"):

    DB_FILE = Path("users-20251005-173430.db")
elif os.path.exists("users.db"):

    DB_FILE = Path("users.db")
else:

    DB_FILE = Path("users.db")


def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def add_calendar_months(dt: datetime, months: int = 1) -> datetime:
    """Добавляет календарные месяцы к дате, корректно обрабатывая переполнение дней
    (например, 31 января + 1 месяц -> 28/29 февраля)."""
    import calendar
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def compute_next_traffic_reset_str(from_dt: datetime | None = None) -> str:
    """Возвращает строку даты/времени следующего ежемесячного сброса трафика (сейчас + 1 месяц)."""
    base = from_dt or datetime.now()
    return add_calendar_months(base, 1).strftime("%Y-%m-%d %H:%M:%S")


def add_months(dt: datetime, months: int = 1) -> datetime:
    """Прибавляет к дате календарные месяцы (без внешних зависимостей вроде dateutil).

    Если в целевом месяце меньше дней, чем день исходной даты (например, 31 января -> февраль),
    берётся последний день целевого месяца.
    """
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def compute_next_traffic_reset(from_dt: datetime | None = None) -> str:
    """Возвращает строку даты следующего ежемесячного сброса трафика (текущий момент + 1 месяц)."""
    base = from_dt or datetime.now()
    return add_months(base, 1).strftime("%Y-%m-%d %H:%M:%S")


def _to_datetime_str(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def _normalize_key_row(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    email = _normalize_email(data.get("email") or data.get("key_email"))
    if email:
        data["email"] = email
        data["key_email"] = email
    rem_uuid = data.get("remnawave_user_uuid") or data.get("xui_client_uuid")
    if rem_uuid:
        data["remnawave_user_uuid"] = rem_uuid
        data["xui_client_uuid"] = rem_uuid
    expire_value = data.get("expire_at") or data.get("expiry_date")
    if expire_value:
        expire_str = expire_value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(expire_value, datetime) else str(expire_value)
        data["expire_at"] = expire_str
        data["expiry_date"] = expire_str
    created_value = data.get("created_at") or data.get("created_date")
    if created_value:
        created_str = created_value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_value, datetime) else str(created_value)
        data["created_at"] = created_str
        data["created_date"] = created_str
    subscription_url = data.get("subscription_url") or data.get("connection_string")
    if subscription_url:
        data["subscription_url"] = subscription_url
        data.setdefault("connection_string", subscription_url)
    return data


def _get_table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _ensure_table_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    columns = _get_table_columns(cursor, table)
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_unique_index(cursor: sqlite3.Cursor, name: str, table: str, column: str) -> None:
    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table}({column})")


def _ensure_index(cursor: sqlite3.Cursor, name: str, table: str, column: str) -> None:
    cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({column})")


def normalize_host_name(name: str | None) -> str:
    """Normalize host name by trimming and removing invisible/unicode spaces."""
    s = (name or "").strip()
    for ch in ("\u00A0", "\u200B", "\u200C", "\u200D", "\uFEFF"):
        s = s.replace(ch, "")
    return s


def initialize_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_spent REAL DEFAULT 0,
                    total_months INTEGER DEFAULT 0,
                    trial_used BOOLEAN DEFAULT 0,
                    agreed_to_terms BOOLEAN DEFAULT 0,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT 0,
                    balance REAL DEFAULT 0,
                    referred_by INTEGER,
                    referral_balance REAL DEFAULT 0,
                    referral_balance_all REAL DEFAULT 0,
                    referral_start_bonus_received BOOLEAN DEFAULT 0,
                    referral_trial_day_bonus_received BOOLEAN DEFAULT 0
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_transactions (
                    payment_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    amount_rub REAL,
                    metadata TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referral_payout_methods (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    method_type TEXT NOT NULL,
                    bank_name TEXT,
                    requisite_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_payout_methods_user ON referral_payout_methods(user_id)")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referral_withdrawal_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    method_type TEXT NOT NULL,
                    bank_name TEXT,
                    requisite_value TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new',
                    reject_reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_withdrawal_requests_status ON referral_withdrawal_requests(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_referral_withdrawal_requests_user ON referral_withdrawal_requests(user_id)")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS webapp_auth_requests (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vpn_keys (
                    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    host_name TEXT,
                    squad_uuid TEXT,
                    remnawave_user_uuid TEXT,
                    short_uuid TEXT,
                    email TEXT UNIQUE,
                    key_email TEXT UNIQUE,
                    subscription_url TEXT,
                    expire_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    traffic_limit_bytes INTEGER,
                    traffic_limit_strategy TEXT DEFAULT 'NO_RESET',
                    tag TEXT,
                    description TEXT,
                    missing_from_server_at TIMESTAMP,
                    user_key_name TEXT,
                    traffic_boost_bytes INTEGER DEFAULT 0,
                    next_traffic_reset_at TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS key_usage_monitor (
                    key_id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    first_seen_usage_at TIMESTAMP,
                    last_reminder_at TIMESTAMP,
                    last_checked_at TIMESTAMP,
                    last_devices_count INTEGER DEFAULT 0,
                    last_traffic_bytes INTEGER DEFAULT 0,
                    overlimit_notified_count INTEGER DEFAULT 0,
                    overlimit_notified_at TIMESTAMP
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_key_usage_monitor_first_seen ON key_usage_monitor(first_seen_usage_at)")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    username TEXT,
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    payment_id TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    amount_rub REAL NOT NULL,
                    amount_currency REAL,
                    currency_name TEXT,
                    payment_method TEXT,
                    metadata TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS modules_registry (
                    module_id     TEXT PRIMARY KEY,
                    name          TEXT,
                    version       TEXT,
                    status        TEXT DEFAULT 'disabled',
                    enabled_at    TIMESTAMP,
                    error_message TEXT,
                    metadata      TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS button_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    menu_type TEXT NOT NULL,
                    button_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    callback_data TEXT,
                    url TEXT,
                    row_position INTEGER DEFAULT 0,
                    column_position INTEGER DEFAULT 0,
                    button_width INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(menu_type, button_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS xui_hosts(
                    host_name TEXT PRIMARY KEY,
                    squad_uuid TEXT UNIQUE,
                    description TEXT,
                    default_traffic_limit_bytes INTEGER,
                    default_traffic_strategy TEXT DEFAULT 'NO_RESET',
                    host_url TEXT,
                    host_username TEXT,
                    host_pass TEXT,
                    host_inbound_id INTEGER,
                    subscription_url TEXT,
                    ssh_host TEXT,
                    ssh_port INTEGER,
                    ssh_user TEXT,
                    ssh_password TEXT,
                    ssh_key_path TEXT,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    metadata TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_name TEXT,
                    squad_uuid TEXT,
                    plan_name TEXT NOT NULL,
                    months INTEGER,
                    duration_days INTEGER,
                    price REAL NOT NULL,
                    traffic_limit_bytes INTEGER,
                    traffic_limit_strategy TEXT DEFAULT 'NO_RESET',
                    hwid_device_limit INTEGER,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    metadata TEXT,
                    FOREIGN KEY (host_name) REFERENCES xui_hosts (host_name)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS traffic_packages (
                    package_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    size_gb REAL NOT NULL,
                    price REAL NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES plans (plan_id)
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_packages_plan_id ON traffic_packages(plan_id)")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS support_tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT "open",
                    subject TEXT,
                    forum_chat_id TEXT,
                    message_thread_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS support_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    content TEXT NOT NULL,
                    media TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES support_tickets (ticket_id)
                )
            ''')

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_thread ON support_tickets(forum_chat_id, message_thread_id)")
            except Exception:
                pass
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS host_speedtests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_name TEXT NOT NULL,
                    method TEXT NOT NULL,
                    ping_ms REAL,
                    jitter_ms REAL,
                    download_mbps REAL,
                    upload_mbps REAL,
                    server_name TEXT,
                    server_id TEXT,
                    ok INTEGER NOT NULL DEFAULT 1,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_speedtests_host_time ON host_speedtests(host_name, created_at DESC)")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS resource_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope TEXT NOT NULL,                -- 'local' | 'host' | 'target'
                    object_name TEXT NOT NULL,          -- 'panel' | host_name | target_name
                    cpu_percent REAL,
                    mem_percent REAL,
                    disk_percent REAL,
                    load1 REAL,
                    net_bytes_sent INTEGER,
                    net_bytes_recv INTEGER,
                    raw_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_resource_metrics_scope_time ON resource_metrics(scope, object_name, created_at DESC)")

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS speedtest_ssh_targets (
                    target_name TEXT PRIMARY KEY,
                    ssh_host TEXT NOT NULL,
                    ssh_port INTEGER DEFAULT 22,
                    ssh_user TEXT,
                    ssh_password TEXT,
                    ssh_key_path TEXT,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0,
                    metadata TEXT
                )
            ''')

            # === Franchise (managed clone bots) ===
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS managed_bots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_bot_user_id INTEGER NOT NULL UNIQUE,
                    username TEXT,
                    token TEXT NOT NULL,
                    owner_telegram_id INTEGER NOT NULL,
                    referrer_bot_id INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS factory_user_activity (
                    bot_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    messages_count INTEGER DEFAULT 0,
                    PRIMARY KEY (bot_id, user_id)
                )
            ''')
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_factory_activity_bot ON factory_user_activity(bot_id)')
            except Exception:
                pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS partner_commissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id INTEGER NOT NULL,
                    payment_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    amount_rub REAL NOT NULL,
                    commission_percent REAL NOT NULL,
                    commission_rub REAL NOT NULL,
                    payment_method TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(bot_id, payment_id)
                )
            ''')
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_partner_commissions_bot ON partner_commissions(bot_id, created_at DESC)')
            except Exception:
                pass

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS partner_withdraw_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id INTEGER NOT NULL,
                    owner_telegram_id INTEGER NOT NULL,
                    amount_rub REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_partner_withdraw_bot ON partner_withdraw_requests(bot_id, created_at DESC)')
            except Exception:
                pass

            # Partner payout requisites (bank + card/phone)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS partner_payout_requisites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id INTEGER NOT NULL,
                    owner_telegram_id INTEGER NOT NULL,
                    bank TEXT NOT NULL,
                    requisite_type TEXT NOT NULL,
                    requisite_value TEXT NOT NULL,
                    is_default INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_partner_requisites_owner ON partner_payout_requisites(bot_id, owner_telegram_id, created_at DESC)')
            except Exception:
                pass

            # Migrations for withdraw requests: store requisites snapshot
            try:
                _ensure_table_column(cursor, 'partner_withdraw_requests', 'bank', 'TEXT')
                _ensure_table_column(cursor, 'partner_withdraw_requests', 'requisite_type', 'TEXT')
                _ensure_table_column(cursor, 'partner_withdraw_requests', 'requisite_value', 'TEXT')
                _ensure_table_column(cursor, 'partner_withdraw_requests', 'requisite_id', 'INTEGER')
            except Exception:
                pass

            # === Captcha system ===
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS captcha_challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    challenge_type TEXT NOT NULL,
                    question TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    max_attempts INTEGER DEFAULT 3,
                    passed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expired_at TIMESTAMP
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_captcha_challenges_user_time ON captcha_challenges(user_id, created_at DESC)")
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_captcha_status (
                    user_id INTEGER PRIMARY KEY,
                    passed_at TIMESTAMP,
                    challenge_id INTEGER,
                    FOREIGN KEY (challenge_id) REFERENCES captcha_challenges (id)
                )
            ''')

            default_settings = {
    "enable_referral_days_bonus": "true",
                "panel_login": "admin",
                "panel_password": "admin",
                "about_text": None,
                "terms_url": None,
                "privacy_url": None,
                "support_user": None,
                "support_text": None,
                "channel_url": None,
                "channel_link": None,
                "chat_link": None,
                "force_subscription": "true",
                "receipt_email": "example@example.com",
                "telegram_bot_token": None,
                "telegram_bot_username": None,
                "auto_start_main_bot": "true",
                "auto_start_support_bot": "true",
                "trial_enabled": "true",
                "trial_duration_days": "3",
                "trial_traffic_limit_gb": "0",
                "trial_device_limit": "0",
                "trial_default_host": "",
                "enable_referrals": "true",
                "referral_percentage": "10",
                "referral_discount": "5",
                "minimum_withdrawal": "100",
                "referral_withdraw_enabled": "true",
                "referral_withdraw_sbp_enabled": "true",
                "referral_withdraw_card_enabled": "true",
                "referral_withdraw_usdt_enabled": "true",
                "referral_withdraw_sbp_banks": "Сбербанк,Тинькофф,ВТБ,Альфа-Банк,Райффайзен",
                "admin_telegram_id": None,
                "admin_telegram_ids": None,
                "yookassa_shop_id": None,
                "yookassa_secret_key": None,
                "sbp_enabled": "false",
                "cryptobot_token": None,
                "heleket_merchant_id": None,
                "heleket_api_key": None,
                "platega_base_url": "https://app.platega.io",
                "platega_merchant_id": None,
                "platega_secret": None,
                "platega_active_methods": "2,10,11,12,13",

                "domain": None,
                "ton_wallet_address": None,
                "tonapi_key": None,
                "support_forum_chat_id": None,
                "enable_fixed_referral_bonus": "false",
                "fixed_referral_bonus_amount": "50",
                "referral_reward_type": "percent_purchase",
                "referral_on_start_referrer_amount": "20",
                "backup_interval_days": "1",

                "monitoring_enabled": "true",
                "monitoring_interval_sec": "300",
                "monitoring_cpu_threshold": "90",
                "monitoring_mem_threshold": "90",
                "monitoring_disk_threshold": "90",
                "monitoring_alert_cooldown_sec": "3600",

                "inactive_usage_reminder_enabled": "true",
                "inactive_usage_reminder_interval_hours": "8",
                "inactive_usage_reminder_support_url": "",
                "remnawave_base_url": None,
                "remnawave_api_token": None,
                "remnawave_subscription_url": None,
                "remnawave_cookies": "{}",
                "remnawave_is_local_network": "false",
                "default_extension_days": "30",

                "main_menu_text": None,
                "main_menu_promo_text": "🌐 Множество локаций\n🚀 Скорость серверов 1 Гбит/с, смена IP\n📊 Безлимитный трафик\n\nСпасибо, что вы с нами!",
                "howto_intro_text": None,
                "howto_android_text": None,
                "howto_ios_text": None,
                "howto_windows_text": None,
                "howto_linux_text": None,

                # Key card buttons (key info screen)
                "key_info_show_connect_device": "true",
                "key_info_show_howto": "false",

                # Payment flow
                "payment_email_prompt_enabled": "false",

                # Captcha settings
                "captcha_enabled": "true",
                "captcha_type": "math",  # math, button
                "captcha_max_attempts": "3",
                "captcha_timeout_minutes": "15",
                "captcha_message": "👤 Привет! Ты выглядишь как бот. Пройди простую капчу чтобы подтвердить что ты человек.\n\n",

                "btn_trial_text": None,
                "btn_profile_text": None,
                "btn_my_keys_text": None,
                "btn_buy_key_text": None,
                "btn_topup_text": None,
                "btn_referral_text": None,
                "referral_share_text": "🌐Обход глушилок и блокировок на любом устройстве! 😊",
                "gift_share_text": "🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать",
                "btn_support_text": None,
                "btn_about_text": None,
                "btn_speed_text": None,
                "btn_howto_text": None,
                "btn_admin_text": None,
                "btn_back_to_menu_text": None,

                "stars_enabled": "false",
                "yoomoney_enabled": "false",
                "yoomoney_wallet": None,
                "yoomoney_secret": None,

                # Bot UI labels: payment method names in Telegram buttons
                "payment_label_balance": "💼 Оплатить с баланса",
                "payment_label_yookassa_card": "🏦 Банковская карта",
                "payment_label_yookassa_sbp": "🏦 СБП / Банковская карта",
                "payment_label_platega": "💳 Platega",
                "payment_label_rollypay": "💳 СБП",
                "payment_label_cryptobot": "💎 Криптовалюта",
                "payment_label_heleket": "💎 Криптовалюта",
                "payment_label_tonconnect": "🪙 TON Connect",
                "payment_label_stars": "⭐ Telegram Stars",
                "payment_label_yoomoney": "🏦 Банковская карта",

                "yoomoney_api_token": None,
                "yoomoney_client_id": None,
                "yoomoney_client_secret": None,
                "yoomoney_redirect_uri": None,
                "stars_per_rub": "1",

                # Franchise settings
                "franchise_enabled": "false",
                "franchise_commission_percent": "35.0",
                "franchise_min_withdraw_rub": "1500.0",

                # Auto-renewal
                "auto_renew_globally_enabled": "false",
                "auto_renew_hours_before": "24",
            }
            run_migration()
            for key, value in default_settings.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            conn.commit()
            

            initialize_default_button_configs()
            

            update_existing_my_keys_button()

            ensure_main_menu_gift_button()

            ensure_main_menu_referral_button()


            ensure_admin_plans_button()
            ensure_admin_trial_button()
            ensure_admin_auto_renew_button()
            

            try:
                cursor.execute("ALTER TABLE button_configs ADD COLUMN button_width INTEGER DEFAULT 1")
                logging.info("Added button_width column to button_configs table")
            except sqlite3.OperationalError:

                pass
            
            logging.info("База данных инициализирована")
    except sqlite3.Error as e:
        logging.error("Не удалось инициализировать базу данных: %s", e)


def _ensure_users_columns(cursor: sqlite3.Cursor) -> None:
    mapping = {
        "referred_by": "INTEGER",
        "balance": "REAL DEFAULT 0",
        "referral_balance": "REAL DEFAULT 0",
        "referral_balance_all": "REAL DEFAULT 0",
        "referral_start_bonus_received": "BOOLEAN DEFAULT 0",
        "referral_trial_day_bonus_received": "BOOLEAN DEFAULT 0",
        "subscription_expiry_notifications_enabled": "BOOLEAN DEFAULT 1",
        "auth_token": "TEXT",
        "auth_email": "TEXT",
        "auth_pass": "TEXT",
        "seller_active": "BOOLEAN DEFAULT 0",
        "seller_sale": "REAL DEFAULT 0",
        "is_unreachable": "BOOLEAN DEFAULT 0",
        "unreachable_reason": "TEXT",
        "unreachable_since": "TIMESTAMP",
    }
    for column, definition in mapping.items():
        _ensure_table_column(cursor, "users", column, definition)
    _ensure_unique_index(cursor, "idx_users_auth_token", "users", "auth_token")
    _ensure_unique_index(cursor, "idx_users_auth_email", "users", "auth_email")
    _ensure_index(cursor, "idx_users_is_unreachable", "users", "is_unreachable")


def _ensure_email_verification_columns(cursor: sqlite3.Cursor) -> None:
    """Добавляет поля для активации email (подтверждение владения адресом при веб-регистрации)."""
    is_new_migration = "email_verified" not in _get_table_columns(cursor, "users")
    mapping = {
        "email_verified": "BOOLEAN DEFAULT 0",
        "email_code_hash": "TEXT",
        "email_code_expires_at": "TIMESTAMP",
        "email_code_last_sent_at": "TIMESTAMP",
        # Новый email, ожидающий подтверждения кода при смене почты из профиля
        # (текущий auth_email остаётся действующим, пока код не подтверждён).
        "pending_email": "TEXT",
    }
    for column, definition in mapping.items():
        _ensure_table_column(cursor, "users", column, definition)
    if is_new_migration:
        # Пользователи, зарегистрированные до появления обязательной активации email,
        # уже могли входить в систему — не блокируем им доступ повторной верификацией.
        try:
            cursor.execute(
                "UPDATE users SET email_verified = 1 "
                "WHERE auth_email IS NOT NULL AND auth_pass IS NOT NULL "
                "AND email_code_hash IS NULL AND email_verified = 0"
            )
        except sqlite3.Error as e:
            logging.warning(f"Не удалось выполнить бэкфилл email_verified для существующих пользователей: {e}")


def _ensure_hosts_columns(cursor: sqlite3.Cursor) -> None:
    extras = {
        "squad_uuid": "TEXT",
        "description": "TEXT",
        "default_traffic_limit_bytes": "INTEGER",
        "default_traffic_strategy": "TEXT DEFAULT 'NO_RESET'",
        "is_active": "INTEGER DEFAULT 1",
        "sort_order": "INTEGER DEFAULT 0",
        "metadata": "TEXT",
        "subscription_url": "TEXT",
        "ssh_host": "TEXT",
        "ssh_port": "INTEGER",
        "ssh_user": "TEXT",
        "ssh_password": "TEXT",
        "ssh_key_path": "TEXT",

        "remnawave_base_url": "TEXT",
        "remnawave_api_token": "TEXT",
        "node_class": "TEXT DEFAULT 'unlim'",
        "badge": "TEXT DEFAULT '∞'",
    }
    for column, definition in extras.items():
        _ensure_table_column(cursor, "xui_hosts", column, definition)


def _ensure_plans_columns(cursor: sqlite3.Cursor) -> None:
    extras = {
        "squad_uuid": "TEXT",
        "duration_days": "INTEGER",
        "traffic_limit_bytes": "INTEGER",
        "traffic_limit_strategy": "TEXT DEFAULT 'NO_RESET'",
        "is_active": "INTEGER DEFAULT 1",
        "sort_order": "INTEGER DEFAULT 0",
        "hwid_device_limit": "INTEGER",
        "metadata": "TEXT",
        "lte_limit_bytes": "INTEGER DEFAULT 0",
        "main_reset_price_rub": "REAL DEFAULT 0",
    }
    for column, definition in extras.items():
        _ensure_table_column(cursor, "plans", column, definition)


def _ensure_traffic_packages_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traffic_packages (
            package_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            size_gb REAL NOT NULL,
            price REAL NOT NULL,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES plans (plan_id)
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_packages_plan_id ON traffic_packages(plan_id)")
    _ensure_table_column(cursor, "vpn_keys", "traffic_boost_bytes", "INTEGER DEFAULT 0")
    _ensure_table_column(cursor, "vpn_keys", "next_traffic_reset_at", "TIMESTAMP")
    _ensure_table_column(cursor, "vpn_keys", "comment_key", "TEXT")
    _ensure_table_column(cursor, "traffic_packages", "pool", "TEXT DEFAULT 'main'")
    # Идемпотентность enable/disable воркера двух пулов трафика:
    # 'enabled' | 'disabled_main' | 'disabled_premium' (legacy, host-level disable)
    # | 'disabled_premium_squad' (точечное отключение только LTE-сквада через host_squads)
    _ensure_table_column(cursor, "vpn_keys", "remote_access_state", "TEXT DEFAULT 'enabled'")


def _ensure_subscription_lte_table(cursor: sqlite3.Cursor) -> None:
    """Отдельный (независимый от основного) пул трафика LTE для «премиум»-нод.

    Пул привязан к пользователю (не к конкретному ключу/хосту), т.к. расходуется
    суммарно на всех premium-нодах его подписки.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_lte (
            user_id INTEGER PRIMARY KEY,
            lte_limit_bytes INTEGER DEFAULT 0,
            lte_used_bytes INTEGER DEFAULT 0,
            lte_boost_bytes INTEGER DEFAULT 0,
            lte_used_baseline_bytes INTEGER DEFAULT 0,
            lte_baseline_reset_requested INTEGER DEFAULT 0,
            lte_reset_at TIMESTAMP,
            premium_state TEXT DEFAULT 'enabled',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Миграция для уже существующих БД (CREATE TABLE IF NOT EXISTS не добавит колонки в старую таблицу).
    _ensure_table_column(cursor, "subscription_lte", "lte_used_baseline_bytes", "INTEGER DEFAULT 0")
    _ensure_table_column(cursor, "subscription_lte", "lte_baseline_reset_requested", "INTEGER DEFAULT 0")


def _ensure_host_squads_table(cursor: sqlite3.Cursor) -> None:
    """Классифицированные сквады хоста: 'base' (∞), 'lte' (💰) или 'other'.

    Позволяет привязать к одному хосту сразу несколько internal squad'ов Remnawave
    (двухсквадовая схема: SQUAD_BASE + SQUAD_LTE) вместо единственного `xui_hosts.squad_uuid`.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS host_squads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_name TEXT NOT NULL,
            squad_uuid TEXT NOT NULL,
            squad_class TEXT NOT NULL DEFAULT 'base',
            label TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(host_name, squad_uuid)
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_squads_host_name ON host_squads(host_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_host_squads_class ON host_squads(host_name, squad_class)")

    # Миграция: переносим существующий xui_hosts.squad_uuid как запись класса 'base',
    # если для этого хоста ещё нет ни одной записи в host_squads.
    try:
        cursor.execute("SELECT host_name, squad_uuid FROM xui_hosts WHERE squad_uuid IS NOT NULL AND TRIM(squad_uuid) <> ''")
        legacy_rows = cursor.fetchall()
        for host_name, squad_uuid in legacy_rows:
            host_name_n = normalize_host_name(host_name)
            squad_uuid_n = (squad_uuid or '').strip()
            if not host_name_n or not squad_uuid_n:
                continue
            cursor.execute("SELECT 1 FROM host_squads WHERE host_name = ?", (host_name_n,))
            if cursor.fetchone() is not None:
                continue
            cursor.execute(
                "INSERT OR IGNORE INTO host_squads (host_name, squad_uuid, squad_class, label, is_active) VALUES (?, ?, 'base', 'Base (legacy)', 1)",
                (host_name_n, squad_uuid_n),
            )
    except sqlite3.Error as e:
        logging.warning(f"Не удалось мигрировать legacy squad_uuid хостов в host_squads: {e}")


def add_host_squad(host_name: str, squad_uuid: str, squad_class: str = 'base', label: str | None = None) -> int | None:
    """Добавить сквад к хосту с классификацией ('base' | 'lte' | 'other')."""
    squad_class_n = str(squad_class or 'base').strip().lower()
    if squad_class_n not in ('base', 'lte', 'other'):
        squad_class_n = 'base'
    host_name_n = normalize_host_name(host_name)
    squad_uuid_n = (squad_uuid or '').strip()
    if not host_name_n or not squad_uuid_n:
        logging.warning("add_host_squad: host_name и squad_uuid обязательны")
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Не более одного активного сквада класса 'base'/'lte' на хост.
            if squad_class_n in ('base', 'lte'):
                cursor.execute(
                    "SELECT id FROM host_squads WHERE host_name = ? AND squad_class = ? AND is_active = 1",
                    (host_name_n, squad_class_n),
                )
                existing = cursor.fetchone()
                if existing:
                    logging.warning(
                        f"add_host_squad: у хоста '{host_name_n}' уже есть активный сквад класса '{squad_class_n}' (id={existing[0]})"
                    )
                    return None
            cursor.execute(
                "INSERT INTO host_squads (host_name, squad_uuid, squad_class, label, is_active) VALUES (?, ?, ?, ?, 1)",
                (host_name_n, squad_uuid_n, squad_class_n, (label or None)),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        logging.warning(f"add_host_squad: сквад '{squad_uuid_n}' уже привязан к хосту '{host_name_n}'")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to add host squad for '{host_name_n}': {e}")
        return None


def get_host_squads(host_name: str, *, only_active: bool = False) -> list[dict]:
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM host_squads WHERE host_name = ?"
            params: list[Any] = [host_name_n]
            if only_active:
                query += " AND is_active = 1"
            query += " ORDER BY CASE squad_class WHEN 'base' THEN 0 WHEN 'lte' THEN 1 ELSE 2 END, id"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get host squads for '{host_name}': {e}")
        return []


def get_squad_by_class(host_name: str, squad_class: str) -> dict | None:
    """Быстрый доступ к активному сквада заданного класса ('base'/'lte'/'other') хоста."""
    squad_class_n = str(squad_class or '').strip().lower()
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM host_squads WHERE host_name = ? AND squad_class = ? AND is_active = 1 ORDER BY id LIMIT 1",
                (host_name_n, squad_class_n),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get squad by class '{squad_class}' for host '{host_name}': {e}")
        return None


def set_host_squad_active(squad_id: int, is_active: bool) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE host_squads SET is_active = ? WHERE id = ?",
                (1 if is_active else 0, int(squad_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set host squad active status for id {squad_id}: {e}")
        return False


def delete_host_squad(squad_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM host_squads WHERE id = ?", (int(squad_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete host squad id {squad_id}: {e}")
        return False


def _ensure_remnawave_squads_catalog(cursor: sqlite3.Cursor) -> None:
    """Глобальный каталог сквадов Remnawave (выбираются галочками на хостах)."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS remnawave_squads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_uuid TEXT NOT NULL UNIQUE,
            squad_class TEXT NOT NULL DEFAULT 'base',
            label TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remnawave_squads_class ON remnawave_squads(squad_class)")

    # Миграция: собрать уникальные сквады из host_squads и legacy xui_hosts.squad_uuid
    try:
        cursor.execute(
            """
            SELECT squad_uuid, squad_class, label
            FROM host_squads
            WHERE squad_uuid IS NOT NULL AND TRIM(squad_uuid) <> ''
            ORDER BY id
            """
        )
        for squad_uuid, squad_class, label in cursor.fetchall():
            uuid_n = (squad_uuid or "").strip()
            if not uuid_n:
                continue
            class_n = str(squad_class or "base").strip().lower()
            if class_n not in ("base", "lte", "other"):
                class_n = "base"
            cursor.execute(
                """
                INSERT OR IGNORE INTO remnawave_squads (squad_uuid, squad_class, label, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (uuid_n, class_n, (label or None)),
            )
        cursor.execute(
            "SELECT squad_uuid FROM xui_hosts WHERE squad_uuid IS NOT NULL AND TRIM(squad_uuid) <> ''"
        )
        for (squad_uuid,) in cursor.fetchall():
            uuid_n = (squad_uuid or "").strip()
            if not uuid_n:
                continue
            cursor.execute(
                """
                INSERT OR IGNORE INTO remnawave_squads (squad_uuid, squad_class, label, is_active)
                VALUES (?, 'base', 'Base (legacy)', 1)
                """,
                (uuid_n,),
            )
    except sqlite3.Error as e:
        logging.warning(f"Не удалось мигрировать сквады в remnawave_squads: {e}")


def get_remnawave_squads(*, only_active: bool = False) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM remnawave_squads"
            if only_active:
                query += " WHERE is_active = 1"
            query += " ORDER BY CASE squad_class WHEN 'base' THEN 0 WHEN 'lte' THEN 1 ELSE 2 END, id"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to list remnawave squads: {e}")
        return []


def add_remnawave_squad(squad_uuid: str, squad_class: str = "base", label: str | None = None) -> int | None:
    squad_class_n = str(squad_class or "base").strip().lower()
    if squad_class_n not in ("base", "lte", "other"):
        squad_class_n = "base"
    uuid_n = (squad_uuid or "").strip()
    if not uuid_n:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO remnawave_squads (squad_uuid, squad_class, label, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (uuid_n, squad_class_n, (label or None)),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        logging.warning(f"add_remnawave_squad: UUID уже есть в каталоге: {uuid_n}")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to add remnawave squad: {e}")
        return None


def delete_remnawave_squad(squad_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT squad_uuid FROM remnawave_squads WHERE id = ?", (int(squad_id),))
            row = cursor.fetchone()
            if not row:
                return False
            uuid_n = row["squad_uuid"]
            cursor.execute("DELETE FROM remnawave_squads WHERE id = ?", (int(squad_id),))
            cursor.execute("DELETE FROM host_squads WHERE squad_uuid = ?", (uuid_n,))
            # Сброс legacy squad_uuid у хостов, если указывал удалённый сквад
            cursor.execute(
                "UPDATE xui_hosts SET squad_uuid = NULL WHERE TRIM(COALESCE(squad_uuid, '')) = TRIM(?)",
                (uuid_n,),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to delete remnawave squad id {squad_id}: {e}")
        return False


def seed_global_remnawave_from_hosts() -> None:
    """Если глобальные Remnawave-настройки пусты — взять из первого хоста."""
    try:
        base = (get_setting("remnawave_base_url") or "").strip()
        token = (get_setting("remnawave_api_token") or "").strip()
        sub = (get_setting("remnawave_subscription_url") or "").strip()
        if base and token and sub:
            return
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT remnawave_base_url, remnawave_api_token, subscription_url, host_url
                FROM xui_hosts
                ORDER BY host_name
                LIMIT 20
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            if not base:
                base = ((row["remnawave_base_url"] or row["host_url"] or "")).strip()
            if not token:
                token = ((row["remnawave_api_token"] or "")).strip()
            if not sub:
                sub = ((row["subscription_url"] or "")).strip()
            if base and token and sub:
                break
        if base and not (get_setting("remnawave_base_url") or "").strip():
            update_setting("remnawave_base_url", base)
        if token and not (get_setting("remnawave_api_token") or "").strip():
            update_setting("remnawave_api_token", token)
        if sub and not (get_setting("remnawave_subscription_url") or "").strip():
            update_setting("remnawave_subscription_url", sub)
    except Exception as e:
        logging.warning(f"seed_global_remnawave_from_hosts failed: {e}")


def apply_global_remnawave_to_hosts() -> int:
    """Синхронизировать глобальные Remnawave URL/token/subscription на все хосты."""
    base = (get_setting("remnawave_base_url") or "").strip() or None
    token = (get_setting("remnawave_api_token") or "").strip() or None
    sub = (get_setting("remnawave_subscription_url") or "").strip() or None
    updated = 0
    try:
        hosts = get_all_hosts()
        for host in hosts:
            name = host.get("host_name")
            if not name:
                continue
            ok_rmw = update_host_remnawave_settings(
                name,
                remnawave_base_url=base,
                remnawave_api_token=token,
            )
            ok_sub = True
            if sub is not None:
                ok_sub = update_host_subscription_url(name, sub)
            # host_url тоже держим в синхроне с панелью для speedtest/UI
            ok_url = True
            if base:
                ok_url = update_host_url(name, base)
            if ok_rmw and ok_sub and ok_url:
                updated += 1
        return updated
    except Exception as e:
        logging.error(f"apply_global_remnawave_to_hosts failed: {e}")
        return updated


def set_host_squads_from_catalog(host_name: str, catalog_ids: list[int]) -> bool:
    """Выставить привязку хоста к сквадам каталога (галочки). Синхронизирует host_squads и squad_uuid."""
    host_name_n = normalize_host_name(host_name)
    if not host_name_n:
        return False
    try:
        wanted_ids = {int(x) for x in (catalog_ids or []) if str(x).strip().isdigit() or isinstance(x, int)}
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            if cursor.fetchone() is None:
                return False

            selected: list[dict] = []
            if wanted_ids:
                placeholders = ",".join("?" for _ in wanted_ids)
                cursor.execute(
                    f"SELECT * FROM remnawave_squads WHERE id IN ({placeholders}) AND is_active = 1",
                    tuple(wanted_ids),
                )
                selected = [dict(r) for r in cursor.fetchall()]

            # Не более одного base/lte — оставляем первый по приоритету каталога
            filtered: list[dict] = []
            seen_class: set[str] = set()
            for sq in sorted(
                selected,
                key=lambda s: {"base": 0, "lte": 1}.get(str(s.get("squad_class") or ""), 2),
            ):
                cls = str(sq.get("squad_class") or "other").lower()
                if cls in ("base", "lte") and cls in seen_class:
                    continue
                if cls in ("base", "lte"):
                    seen_class.add(cls)
                filtered.append(sq)

            wanted_uuids = {(sq.get("squad_uuid") or "").strip() for sq in filtered}
            wanted_uuids.discard("")

            cursor.execute("SELECT id, squad_uuid FROM host_squads WHERE host_name = ?", (host_name_n,))
            existing = [(int(r["id"]), (r["squad_uuid"] or "").strip()) for r in cursor.fetchall()]
            for row_id, uuid_n in existing:
                if uuid_n not in wanted_uuids:
                    cursor.execute("DELETE FROM host_squads WHERE id = ?", (row_id,))

            cursor.execute("SELECT squad_uuid FROM host_squads WHERE host_name = ?", (host_name_n,))
            have = {(r["squad_uuid"] or "").strip() for r in cursor.fetchall()}
            for sq in filtered:
                uuid_n = (sq.get("squad_uuid") or "").strip()
                if not uuid_n or uuid_n in have:
                    continue
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO host_squads (host_name, squad_uuid, squad_class, label, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (
                        host_name_n,
                        uuid_n,
                        str(sq.get("squad_class") or "base").lower(),
                        sq.get("label"),
                    ),
                )

            base_uuid = None
            for sq in filtered:
                if str(sq.get("squad_class") or "").lower() == "base":
                    base_uuid = (sq.get("squad_uuid") or "").strip() or None
                    break
            cursor.execute(
                "UPDATE xui_hosts SET squad_uuid = ? WHERE TRIM(host_name) = TRIM(?)",
                (base_uuid, host_name_n),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"set_host_squads_from_catalog failed for '{host_name}': {e}")
        return False


def get_host_selected_squad_catalog_ids(host_name: str) -> list[int]:
    """ID записей каталога, привязанных к хосту через host_squads.uuid."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rs.id
                FROM remnawave_squads rs
                INNER JOIN host_squads hs ON hs.squad_uuid = rs.squad_uuid
                WHERE hs.host_name = ?
                ORDER BY rs.id
                """,
                (host_name_n,),
            )
            return [int(r[0]) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"get_host_selected_squad_catalog_ids failed for '{host_name}': {e}")
        return []


def _ensure_support_tickets_columns(cursor: sqlite3.Cursor) -> None:
    extras = {
        "forum_chat_id": "TEXT",
        "message_thread_id": "INTEGER",
    }
    for column, definition in extras.items():
        _ensure_table_column(cursor, "support_tickets", column, definition)


def _ensure_key_usage_monitor_columns(cursor: sqlite3.Cursor) -> None:
    extras = {
        "overlimit_notified_count": "INTEGER DEFAULT 0",
        "overlimit_notified_at": "TIMESTAMP",
    }
    for column, definition in extras.items():
        _ensure_table_column(cursor, "key_usage_monitor", column, definition)


def _finalize_vpn_key_indexes(cursor: sqlite3.Cursor) -> None:
    _ensure_unique_index(cursor, "uq_vpn_keys_email", "vpn_keys", "email")
    _ensure_unique_index(cursor, "uq_vpn_keys_key_email", "vpn_keys", "key_email")
    _ensure_index(cursor, "idx_vpn_keys_user_id", "vpn_keys", "user_id")
    _ensure_index(cursor, "idx_vpn_keys_rem_uuid", "vpn_keys", "remnawave_user_uuid")
    _ensure_index(cursor, "idx_vpn_keys_expire_at", "vpn_keys", "expire_at")


def _rebuild_vpn_keys_table(cursor: sqlite3.Cursor) -> None:
    columns = _get_table_columns(cursor, "vpn_keys")
    legacy_markers = {"xui_client_uuid", "expiry_date", "created_date", "connection_string"}
    required = {"remnawave_user_uuid", "email", "expire_at", "created_at", "updated_at"}
    if required.issubset(columns) and not (columns & legacy_markers):
        _ensure_table_column(cursor, "vpn_keys", "missing_from_server_at", "TIMESTAMP")
        _finalize_vpn_key_indexes(cursor)
        return

    cursor.execute("ALTER TABLE vpn_keys RENAME TO vpn_keys_legacy")
    cursor.execute('''
        CREATE TABLE vpn_keys (
            key_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            host_name TEXT,
            squad_uuid TEXT,
            remnawave_user_uuid TEXT,
            short_uuid TEXT,
            email TEXT UNIQUE,
            key_email TEXT UNIQUE,
            subscription_url TEXT,
            expire_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            traffic_limit_bytes INTEGER,
            traffic_limit_strategy TEXT DEFAULT 'NO_RESET',
            tag TEXT,
            description TEXT,
            missing_from_server_at TIMESTAMP,
            user_key_name TEXT
        )
    ''')
    old_columns = _get_table_columns(cursor, "vpn_keys_legacy")

    def has(column: str) -> bool:
        return column in old_columns

    def col(column: str, default: str = "NULL") -> str:
        return column if has(column) else default

    rem_uuid_expr = "remnawave_user_uuid" if has("remnawave_user_uuid") else ("xui_client_uuid" if has("xui_client_uuid") else "NULL")
    email_expr = "LOWER(email)" if has("email") else ("LOWER(key_email)" if has("key_email") else "NULL")
    key_email_expr = "LOWER(key_email)" if has("key_email") else ("LOWER(email)" if has("email") else "NULL")
    subscription_expr = col("subscription_url", "connection_string" if has("connection_string") else "NULL")
    expire_expr = col("expire_at", "expiry_date" if has("expiry_date") else "NULL")
    created_expr = col("created_at", "created_date" if has("created_date") else "CURRENT_TIMESTAMP")
    updated_expr = col("updated_at", created_expr)
    traffic_strategy_expr = col("traffic_limit_strategy", "'NO_RESET'")

    select_clause = ",\n            ".join([
        f"{col('key_id')} AS key_id",
        f"{col('user_id')} AS user_id",
        f"{col('host_name')} AS host_name",
        f"{col('squad_uuid')} AS squad_uuid",
        f"{rem_uuid_expr} AS remnawave_user_uuid",
        f"{col('short_uuid')} AS short_uuid",
        f"{email_expr} AS email",
        f"{key_email_expr} AS key_email",
        f"{subscription_expr} AS subscription_url",
        f"{expire_expr} AS expire_at",
        f"{created_expr} AS created_at",
        f"{updated_expr} AS updated_at",
        f"{col('traffic_limit_bytes')} AS traffic_limit_bytes",
        f"{traffic_strategy_expr} AS traffic_limit_strategy",
        f"{col('tag')} AS tag",
        f"{col('description')} AS description",
        f"{col('missing_from_server_at')} AS missing_from_server_at",
    ])

    cursor.execute(
        f"""
        INSERT INTO vpn_keys (
            key_id,
            user_id,
            host_name,
            squad_uuid,
            remnawave_user_uuid,
            short_uuid,
            email,
            key_email,
            subscription_url,
            expire_at,
            created_at,
            updated_at,
            traffic_limit_bytes,
            traffic_limit_strategy,
            tag,
            description,
            missing_from_server_at
        )
        SELECT
            {select_clause}
        FROM vpn_keys_legacy
        """
    )
    cursor.execute("DROP TABLE vpn_keys_legacy")
    cursor.execute("SELECT MAX(key_id) FROM vpn_keys")
    max_id = cursor.fetchone()[0]
    if max_id is not None:
        cursor.execute("INSERT OR REPLACE INTO sqlite_sequence(name, seq) VALUES('vpn_keys', ?)", (max_id,))
    _finalize_vpn_key_indexes(cursor)


def _ensure_vpn_keys_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vpn_keys'")
    if cursor.fetchone() is None:
        cursor.execute('''
            CREATE TABLE vpn_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                host_name TEXT,
                squad_uuid TEXT,
                remnawave_user_uuid TEXT,
                short_uuid TEXT,
                email TEXT UNIQUE,
                key_email TEXT UNIQUE,
                subscription_url TEXT,
                expire_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                traffic_limit_bytes INTEGER,
                traffic_limit_strategy TEXT DEFAULT 'NO_RESET',
                tag TEXT,
                description TEXT,
                missing_from_server_at TIMESTAMP,
                user_key_name TEXT
            )
        ''')
        _finalize_vpn_key_indexes(cursor)
        return
    _rebuild_vpn_keys_table(cursor)
    # Добавляем колонку user_key_name если её нет
    _ensure_table_column(cursor, "vpn_keys", "user_key_name", "TEXT")


def _migrate_gift_tags(cursor: sqlite3.Cursor) -> None:
    """Обновить старые теги 'gift' и 'GIFT' на новый стандарт 'user_gift'."""
    try:
        cursor.execute(
            "UPDATE vpn_keys SET tag = 'user_gift' WHERE tag IN ('gift', 'GIFT')"
        )
        affected = cursor.rowcount
        if affected > 0:
            logging.info(f"Обновлено {affected} записей: 'gift'/'GIFT' → 'user_gift'")
        else:
            logging.debug("Записей с тегом 'gift'/'GIFT' не найдено")
    except Exception as e:
        logging.warning(f"Ошибка при миграции тегов подарков: {e}")



def run_migration():
    if not DB_FILE.exists():
        logging.error("Файл базы данных отсутствует, миграция пропущена.")
        return

    logging.info("Запуск миграций базы данных: %s", DB_FILE)

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            _ensure_users_columns(cursor)
            _ensure_email_verification_columns(cursor)
            _ensure_hosts_columns(cursor)
            _ensure_plans_columns(cursor)
            _ensure_support_tickets_columns(cursor)
            _ensure_vpn_keys_schema(cursor)
            _migrate_gift_tags(cursor)  # Обновить старые теги подарков на новый стандарт
            _ensure_key_usage_monitor_columns(cursor)
            _ensure_ssh_targets_table(cursor)
            _ensure_gift_tokens_table(cursor)
            _ensure_user_gifts_table(cursor)
            _ensure_promo_tables(cursor)
            _ensure_traffic_packages_table(cursor)
            _ensure_subscription_lte_table(cursor)
            _ensure_host_squads_table(cursor)
            _ensure_remnawave_squads_catalog(cursor)
            _ensure_analytics_tables(cursor)
            _ensure_auth_pending_actions_table(cursor)
            try:
                cursor.execute(
                    "UPDATE plans SET traffic_limit_strategy = 'MONTH_ROLLING' "
                    "WHERE traffic_limit_bytes IS NOT NULL AND traffic_limit_bytes > 0 "
                    "AND (traffic_limit_strategy IS NULL OR traffic_limit_strategy NOT IN ('MONTH_ROLLING'))"
                )
            except Exception:
                logging.warning("Не удалось обновить traffic_limit_strategy существующих тарифов на MONTH_ROLLING.", exc_info=True)

            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_thread ON support_tickets(forum_chat_id, message_thread_id)")
            except Exception:
                pass

            try:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pending_transactions (
                        payment_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        amount_rub REAL,
                        metadata TEXT,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            except Exception:
                pass
            # Auto-renewal column
            _ensure_table_column(cursor, "vpn_keys", "auto_renew", "INTEGER DEFAULT 0")
            cursor.execute("PRAGMA foreign_keys = ON")
            conn.commit()
    except sqlite3.Error as e:
        logging.error("Сбой миграции базы данных: %s", e)


def insert_resource_metric(
    scope: str,
    object_name: str,
    *,
    cpu_percent: float | None = None,
    mem_percent: float | None = None,
    disk_percent: float | None = None,
    load1: float | None = None,
    net_bytes_sent: int | None = None,
    net_bytes_recv: int | None = None,
    raw_json: str | None = None,
) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO resource_metrics (
                    scope, object_name, cpu_percent, mem_percent, disk_percent, load1,
                    net_bytes_sent, net_bytes_recv, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    (scope or '').strip(),
                    (object_name or '').strip(),
                    cpu_percent, mem_percent, disk_percent, load1,
                    net_bytes_sent, net_bytes_recv, raw_json,
                )
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error("Failed to insert resource metric for %s/%s: %s", scope, object_name, e)
        return None


def get_latest_resource_metric(scope: str, object_name: str) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM resource_metrics
                WHERE scope = ? AND object_name = ?
                ORDER BY created_at DESC
                LIMIT 1
                ''',
                ((scope or '').strip(), (object_name or '').strip())
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("Failed to get latest resource metric for %s/%s: %s", scope, object_name, e)
        return None


def get_metrics_series(scope: str, object_name: str, *, since_hours: int = 24, limit: int = 500) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            


            if since_hours == 1:
                hours_filter = 2
            else:
                hours_filter = max(1, int(since_hours))
            

            cursor.execute(
                f'''
                SELECT created_at, cpu_percent, mem_percent, disk_percent, load1
                FROM resource_metrics
                WHERE scope = ? AND object_name = ?
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at ASC
                LIMIT ?
                ''',
                (
                    (scope or '').strip(),
                    (object_name or '').strip(),
                    f'-{hours_filter} hours',
                    max(10, int(limit)),
                )
            )
            rows = cursor.fetchall() or []
            

            logging.debug(f"get_metrics_series: {scope}/{object_name}, since_hours={since_hours}, found {len(rows)} records")
            
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get metrics series for %s/%s: %s", scope, object_name, e)
        return []


def create_host(name: str, url: str, user: str, passwd: str, inbound: int, subscription_url: str | None = None):
    try:
        name = normalize_host_name(name)
        url = (url or "").strip()
        user = (user or "").strip()
        passwd = passwd or ""
        try:
            inbound = int(inbound)
        except Exception:
            pass
        subscription_url = (subscription_url or None)

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, subscription_url) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, url, user, passwd, inbound, subscription_url)
                )
            except sqlite3.OperationalError:
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id) VALUES (?, ?, ?, ?, ?)",
                    (name, url, user, passwd, inbound)
                )
            conn.commit()
            logging.info(f"Успешно создан новый хост: {name}")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при создании хоста '{name}': {e}")

def update_host_subscription_url(host_name: str, subscription_url: str | None) -> bool:
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            exists = cursor.fetchone() is not None
            if not exists:
                logging.warning(f"update_host_subscription_url: хост с именем '{host_name}' не найден (после TRIM)")
                return False

            cursor.execute(
                "UPDATE xui_hosts SET subscription_url = ? WHERE TRIM(host_name) = TRIM(?)",
                (subscription_url, host_name)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить subscription_url для хоста '{host_name}': {e}")
        return False

def claim_referral_start_bonus(user_id: int) -> bool:
    """Атомарно пометить, что приглашённый получил стартовый реферальный бонус.

    Возвращает True только если этот вызов выиграл гонку: UPDATE с
    ``WHERE COALESCE(referral_start_bonus_received, 0) = 0`` и ``rowcount > 0``.
    Начислять баланс рефереру можно только после успешного claim — иначе
    параллельные /start (или pending-action) дважды кредитуют одну и ту же сумму.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET referral_start_bonus_received = 1
                WHERE telegram_id = ?
                  AND COALESCE(referral_start_bonus_received, 0) = 0
                """,
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(
            f"Не удалось атомарно пометить получение стартового реферального бонуса для пользователя {user_id}: {e}"
        )
        return False


def set_referral_start_bonus_received(user_id: int) -> bool:
    """Пометить, что пользователь получил стартовый бонус за реферальную регистрацию.

    Атомарный claim (см. ``claim_referral_start_bonus``): повторный вызов
    возвращает False и не сбрасывает флаг.
    """
    return claim_referral_start_bonus(user_id)


def set_referral_trial_day_bonus_received(user_id: int) -> bool:
    """Пометить, что за данного пользователя уже начислялся +1 день рефереру за активацию триала."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET referral_trial_day_bonus_received = 1 WHERE telegram_id = ?",
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(
            f"Не удалось пометить начисление +1 дня за триал для пользователя {user_id}: {e}"
        )
        return False

def update_host_url(host_name: str, new_url: str) -> bool:
    """Обновить URL панели XUI для указанного хоста."""
    try:
        host_name = normalize_host_name(host_name)
        new_url = (new_url or "").strip()
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_url: хост с именем '{host_name}' не найден")
                return False

            cursor.execute(
                "UPDATE xui_hosts SET host_url = ? WHERE TRIM(host_name) = TRIM(?)",
                (new_url, host_name)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить host_url для хоста '{host_name}': {e}")
        return False

def update_host_remnawave_settings(
    host_name: str,
    *,
    remnawave_base_url: str | None = None,
    remnawave_api_token: str | None = None,
    squad_uuid: str | None = None,
) -> bool:
    """Обновить Remnawave-настройки на уровне конкретного хоста.
    Пустые строки превращаются в NULL. Поля, равные None, не изменяются.
    """
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_remnawave_settings: хост не найден '{host_name_n}'")
                return False

            sets: list[str] = []
            params: list[Any] = []
            if remnawave_base_url is not None:
                value = (remnawave_base_url or '').strip() or None
                sets.append("remnawave_base_url = ?")
                params.append(value)
            if remnawave_api_token is not None:
                value = (remnawave_api_token or '').strip() or None
                sets.append("remnawave_api_token = ?")
                params.append(value)
            if squad_uuid is not None:
                value = (squad_uuid or '').strip() or None
                sets.append("squad_uuid = ?")
                params.append(value)
            if not sets:
                return True
            params.append(host_name_n)
            sql = f"UPDATE xui_hosts SET {', '.join(sets)} WHERE TRIM(host_name) = TRIM(?)"
            cursor.execute(sql, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить Remnawave-настройки для хоста '{host_name}': {e}")
        return False


def get_host_class(host_name: str) -> str:
    """Класс ноды: 'premium' (💰) или 'unlim' (∞, по умолчанию)."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT node_class FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            row = cursor.fetchone()
            return (row[0] if row and row[0] else 'unlim')
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить класс хоста '{host_name}': {e}")
        return 'unlim'


def set_host_class(host_name: str, node_class: str, badge: str | None = None) -> bool:
    """Устанавливает класс ноды ('premium'/'unlim') и её значок (по умолчанию 💰/∞)."""
    node_class = 'premium' if str(node_class).strip().lower() == 'premium' else 'unlim'
    if badge is None:
        badge = '💰' if node_class == 'premium' else '∞'
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE xui_hosts SET node_class = ?, badge = ? WHERE TRIM(host_name) = TRIM(?)",
                (node_class, badge, host_name_n),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось установить класс хоста '{host_name}': {e}")
        return False


def list_hosts_by_class(node_class: str) -> list[dict]:
    node_class = 'premium' if str(node_class).strip().lower() == 'premium' else 'unlim'
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts WHERE COALESCE(node_class, 'unlim') = ?", (node_class,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить список хостов класса '{node_class}': {e}")
        return []


def update_host_name(old_name: str, new_name: str) -> bool:
    """Переименовать хост во всех связанных таблицах (xui_hosts, plans, vpn_keys)."""
    try:
        old_name_n = normalize_host_name(old_name)
        new_name_n = normalize_host_name(new_name)
        if not new_name_n:
            logging.warning("update_host_name: new host name is empty after normalization")
            return False
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (old_name_n,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_name: исходный хост не найден '{old_name_n}'")
                return False
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (new_name_n,))
            exists_target = cursor.fetchone() is not None
            if exists_target and old_name_n.lower() != new_name_n.lower():
                logging.warning(f"update_host_name: целевое имя '{new_name_n}' уже используется")
                return False

            cursor.execute(
                "UPDATE xui_hosts SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?)",
                (new_name_n, old_name_n)
            )
            cursor.execute(
                "UPDATE plans SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?)",
                (new_name_n, old_name_n)
            )
            cursor.execute(
                "UPDATE vpn_keys SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?)",
                (new_name_n, old_name_n)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось переименовать хост с '{old_name}' на '{new_name}': {e}")
        return False

def delete_host(host_name: str):
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plans WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            cursor.execute("DELETE FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            conn.commit()
            logging.info(f"Хост '{host_name}' и его тарифы успешно удалены.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка удаления хоста '{host_name}': {e}")

def get_host(host_name: str) -> dict | None:
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            result = cursor.fetchone()
            return dict(result) if result else None
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения хоста '{host_name}': {e}")
        return None

def update_host_ssh_settings(
    host_name: str,
    ssh_host: str | None = None,
    ssh_port: int | None = None,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
    ssh_key_path: str | None = None,
) -> bool:
    """Обновить SSH-параметры для speedtest/maintenance по хосту.
    Переданные None значения очищают соответствующие поля (ставят NULL).
    """
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_ssh_settings: хост не найден '{host_name_n}'")
                return False

            cursor.execute(
                """
                UPDATE xui_hosts
                SET ssh_host = ?, ssh_port = ?, ssh_user = ?, ssh_password = ?, ssh_key_path = ?
                WHERE TRIM(host_name) = TRIM(?)
                """,
                (
                    (ssh_host or None),
                    (int(ssh_port) if ssh_port is not None else None),
                    (ssh_user or None),
                    (ssh_password if ssh_password is not None else None),
                    (ssh_key_path or None),
                    host_name_n,
                ),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить SSH-настройки для хоста '{host_name}': {e}")
        return False

def delete_key_by_id(key_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Ключ может быть привязан к неактивированному подарку (user_gifts.key_id) —
            # при удалении ключа (по истечении срока, вручную и т.д.) подарок должен
            # пропадать из списка так же, как исчезает обычный ключ.
            cursor.execute("DELETE FROM user_gifts WHERE key_id = ? AND is_activated = 0", (key_id,))
            cursor.execute("DELETE FROM vpn_keys WHERE key_id = ?", (key_id,))
            affected = cursor.rowcount
            conn.commit()
            return affected > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось удалить ключ по id {key_id}: {e}")
        return False

def update_key_comment(key_id: int, comment: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET comment_key = ? WHERE key_id = ?", (comment, key_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить комментарий ключа для {key_id}: {e}")
        return False


def update_key_name(key_id: int, new_name: str | None) -> bool:
    """
    Обновить пользовательское название ключа.
    
    Args:
        key_id: ID ключа
        new_name: Новое название (None или пустая строка для удаления)
    
    Returns:
        True если успешно, False при ошибке
    """
    try:
        # Валидация и нормализация
        if new_name:
            new_name = new_name.strip()
            if len(new_name) > 30:
                logging.warning(f"Название ключа слишком длинное ({len(new_name)} символов): {new_name[:50]}")
                return False
            if not new_name:
                new_name = None
        else:
            new_name = None
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE vpn_keys SET user_key_name = ?, updated_at = CURRENT_TIMESTAMP WHERE key_id = ?",
                (new_name, key_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить название ключа {key_id}: {e}")
        return False


def get_all_hosts() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts")
            hosts = cursor.fetchall()

            result = []
            for row in hosts:
                d = dict(row)
                d['host_name'] = normalize_host_name(d.get('host_name'))
                result.append(d)
            return result
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения списка всех хостов: {e}")
        return []

def get_speedtests(host_name: str, limit: int = 20) -> list[dict]:
    """Получить последние результаты спидтестов по хосту (ssh/net), новые сверху."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                limit_int = int(limit)
            except Exception:
                limit_int = 20
            cursor.execute(
                """
                SELECT id, host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps,
                       server_name, server_id, ok, error, created_at
                FROM host_speedtests
                WHERE TRIM(host_name) = TRIM(?)
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (host_name_n, limit_int),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить speedtest-данные для хоста '{host_name}': {e}")
        return []

def get_latest_speedtest(host_name: str) -> dict | None:
    """Получить последний по времени спидтест для хоста."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps,
                       server_name, server_id, ok, error, created_at
                FROM host_speedtests
                WHERE TRIM(host_name) = TRIM(?)
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """,
                (host_name_n,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить последний speedtest для хоста '{host_name}': {e}")
        return None

def insert_host_speedtest(
    host_name: str,
    method: str,
    ping_ms: float | None = None,
    jitter_ms: float | None = None,
    download_mbps: float | None = None,
    upload_mbps: float | None = None,
    server_name: str | None = None,
    server_id: str | None = None,
    ok: bool = True,
    error: str | None = None,
) -> bool:
    """Сохранить результат спидтеста в таблицу host_speedtests."""
    try:
        host_name_n = normalize_host_name(host_name)
        method_s = (method or '').strip().lower()
        if method_s not in ('ssh', 'net'):
            method_s = 'ssh'
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO host_speedtests
                (host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps, server_name, server_id, ok, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
                , (
                    host_name_n,
                    method_s,
                    ping_ms,
                    jitter_ms,
                    download_mbps,
                    upload_mbps,
                    server_name,
                    server_id,
                    1 if ok else 0,
                    (error or None)
                )
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось сохранить запись speedtest для '{host_name}': {e}")
        return False



def _ensure_ssh_targets_table(cursor: sqlite3.Cursor) -> None:
    """Миграция: создать таблицу speedtest_ssh_targets при необходимости и добавить недостающие столбцы."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS speedtest_ssh_targets (
            target_name TEXT PRIMARY KEY,
            ssh_host TEXT NOT NULL,
            ssh_port INTEGER DEFAULT 22,
            ssh_user TEXT,
            ssh_password TEXT,
            ssh_key_path TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)

    extras = {
        "ssh_host": "TEXT",
        "ssh_port": "INTEGER",
        "ssh_user": "TEXT",
        "ssh_password": "TEXT",
        "ssh_key_path": "TEXT",
        "description": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "sort_order": "INTEGER DEFAULT 0",
        "metadata": "TEXT",
    }
    for column, definition in extras.items():
        _ensure_table_column(cursor, "speedtest_ssh_targets", column, definition)


def _ensure_gift_tokens_table(cursor: sqlite3.Cursor) -> None:
    """Миграция для таблиц подарочных токенов."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gift_tokens (
            token TEXT PRIMARY KEY,
            host_name TEXT NOT NULL,
            days INTEGER NOT NULL,
            activation_limit INTEGER DEFAULT 1,
            activations_used INTEGER DEFAULT 0,
            expires_at TIMESTAMP,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_claimed_at TIMESTAMP,
            comment TEXT
        )
        """
    )
    _ensure_index(cursor, "idx_gift_tokens_host", "gift_tokens", "host_name")
    _ensure_index(cursor, "idx_gift_tokens_expires", "gift_tokens", "expires_at")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gift_token_claims (
            claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            key_id INTEGER,
            claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(token) REFERENCES gift_tokens(token) ON DELETE CASCADE
        )
        """
    )
    _ensure_index(cursor, "idx_gift_token_claims_token", "gift_token_claims", "token")
    _ensure_index(cursor, "idx_gift_token_claims_user", "gift_token_claims", "user_id")


def _ensure_user_gifts_table(cursor: sqlite3.Cursor) -> None:
    """Миграция для таблицы неактивированных пользовательских подарков."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_gifts (
            gift_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER NOT NULL,
            key_id INTEGER,
            host_name TEXT NOT NULL,
            plan_id INTEGER,
            gift_code TEXT UNIQUE NOT NULL,
            is_activated BOOLEAN DEFAULT 0,
            activated_by_user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            expires_at TIMESTAMP
        )
        """
    )
    _ensure_index(cursor, "idx_user_gifts_from_user", "user_gifts", "from_user_id")
    _ensure_index(cursor, "idx_user_gifts_gift_code", "user_gifts", "gift_code")
    _ensure_index(cursor, "idx_user_gifts_is_activated", "user_gifts", "is_activated")


def _ensure_auth_pending_actions_table(cursor: sqlite3.Cursor) -> None:
    """Миграция для таблицы pending action — единого механизма "открыл ссылку
    подарка/рефералки → потом авторизовался (Telegram ИЛИ email) → действие
    применяется автоматически". См. src/shop_bot/webapp/handlers.py:
    web_gift_page, web_referral_page, api_pending_action_info,
    api_pending_action_complete.
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_pending_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            action_type TEXT NOT NULL,
            gift_code TEXT,
            referrer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            consumed_at TIMESTAMP,
            consumed_by_user_id INTEGER,
            result_status TEXT
        )
        """
    )
    _ensure_unique_index(cursor, "idx_auth_pending_actions_token", "auth_pending_actions", "token")
    _ensure_index(cursor, "idx_auth_pending_actions_expires_at", "auth_pending_actions", "expires_at")
    _ensure_index(cursor, "idx_auth_pending_actions_gift_code", "auth_pending_actions", "gift_code")
    _ensure_index(cursor, "idx_auth_pending_actions_referrer_id", "auth_pending_actions", "referrer_id")


PENDING_ACTION_DEFAULT_TTL_HOURS = 24


def create_pending_action(
    action_type: str,
    *,
    gift_code: str | None = None,
    referrer_id: int | None = None,
    ttl_hours: int = PENDING_ACTION_DEFAULT_TTL_HOURS,
) -> str | None:
    """Создать pending action и вернуть одноразовый случайный токен.

    Токен — единственное, что уходит клиенту; сам контекст (какой именно
    подарок/реферер) остаётся только на сервере и не может быть подменён
    клиентом на этапе завершения (см. get_pending_action/claim_pending_action).
    """
    if action_type not in ("gift", "referral"):
        logging.error("create_pending_action: неизвестный action_type=%r", action_type)
        return None
    token = secrets.token_urlsafe(32)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO auth_pending_actions (token, action_type, gift_code, referrer_id, expires_at)
                VALUES (?, ?, ?, ?, datetime('now', ?))
                """,
                (token, action_type, gift_code, referrer_id, f"+{int(ttl_hours)} hours"),
            )
            conn.commit()
        return token
    except sqlite3.Error as e:
        logging.error("Failed to create pending action (%s): %s", action_type, e)
        return None


def get_pending_action(token: str) -> dict | None:
    """Вернуть запись pending action по токену как есть (включая уже
    истёкшие/использованные — вызывающий код сам решает, что показать
    пользователю). Не выполняет побочных эффектов."""
    if not token:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM auth_pending_actions WHERE token = ?", (str(token),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("Failed to get pending action: %s", e)
        return None


def claim_pending_action(token: str, user_id: int) -> bool:
    """Атомарно "забрать" pending action для указанного пользователя.

    Ключевой момент идемпотентности/защиты от гонки: UPDATE проверяет
    `consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP` прямо в WHERE,
    и именно `cursor.rowcount` (а не отдельный предварительный SELECT)
    определяет, успел ли именно этот вызов "выиграть" право применить действие.
    Если два параллельных запроса пришлют один и тот же pending_token —
    claim_pending_action вернёт True ровно для одного из них.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE auth_pending_actions
                SET consumed_at = CURRENT_TIMESTAMP, consumed_by_user_id = ?
                WHERE token = ? AND consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP
                """,
                (int(user_id), str(token)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to claim pending action: %s", e)
        return False


def set_pending_action_result(token: str, result_status: str) -> bool:
    """Сохранить итоговый статус применения действия — чтобы повторный вызов
    complete (тем же пользователем, для уже использованного токена) мог
    вернуть тот же самый структурированный результат без повторного выполнения
    бизнес-логики."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE auth_pending_actions SET result_status = ? WHERE token = ?",
                (result_status, str(token)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to set pending action result: %s", e)
        return False


def cleanup_expired_pending_actions(max_age_hours: int = 72) -> int:
    """Удалить давно истёкшие pending actions (профилактическая очистка,
    не обязательна для корректности — claim_pending_action и без этого не
    применит просроченный токен)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM auth_pending_actions WHERE expires_at < datetime('now', ?)",
                (f"-{int(max_age_hours)} hours",),
            )
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error("Failed to cleanup expired pending actions: %s", e)
        return 0


def _ensure_promo_tables(cursor: sqlite3.Cursor) -> None:
    """Создание таблиц промокодов и истории их использования."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT PRIMARY KEY,
            discount_percent REAL,
            discount_amount REAL,
            usage_limit_total INTEGER,
            usage_limit_per_user INTEGER,
            used_total INTEGER DEFAULT 0,
            valid_from TIMESTAMP,
            valid_until TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT,
            applicable_plan_ids TEXT,
            segment_type TEXT,
            segment_value REAL
        )
        """
    )
    _ensure_index(cursor, "idx_promo_codes_valid", "promo_codes", "valid_until")
    # Additive targeting (NULL = unconditional, same as before this feature).
    _ensure_table_column(cursor, "promo_codes", "applicable_plan_ids", "TEXT")
    _ensure_table_column(cursor, "promo_codes", "segment_type", "TEXT")
    _ensure_table_column(cursor, "promo_codes", "segment_value", "REAL")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS promo_code_usages (
            usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            applied_amount REAL,
            order_id TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(code) REFERENCES promo_codes(code) ON DELETE CASCADE
        )
        """
    )
    _ensure_index(cursor, "idx_promo_code_usages_code", "promo_code_usages", "code")
    _ensure_index(cursor, "idx_promo_code_usages_user", "promo_code_usages", "user_id")
    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_code_usages_order_id_unique ON promo_code_usages(order_id) WHERE order_id IS NOT NULL"
        )
    except Exception:
        pass
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS promo_code_reservations (
            payment_id TEXT PRIMARY KEY,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            reserved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'reserved',
            FOREIGN KEY(code) REFERENCES promo_codes(code) ON DELETE CASCADE
        )
        """
    )
    _ensure_index(cursor, "idx_promo_reservations_code_user", "promo_code_reservations", "code, user_id, status")


def _ensure_analytics_tables(cursor: sqlite3.Cursor) -> None:
    """Таблицы для раздела админки «Продажи и аналитика».

    Полностью независимы от xui_hosts (по требованию — учёт серверов/экономики
    ведётся отдельно от технической конфигурации хостов).
    """
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS server_cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_label TEXT NOT NULL,
            linked_host_name TEXT,
            provider TEXT,
            location TEXT,
            monthly_cost REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'RUB',
            status TEXT NOT NULL DEFAULT 'active',
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_index(cursor, "idx_server_cost_entries_status", "server_cost_entries", "status")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS utm_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            source TEXT,
            medium TEXT,
            campaign TEXT,
            content TEXT,
            term TEXT,
            label TEXT,
            comment TEXT,
            budget REAL,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_index(cursor, "idx_utm_links_active", "utm_links", "is_active")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS utm_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_index(cursor, "idx_utm_visits_slug", "utm_visits", "slug")
    _ensure_index(cursor, "idx_utm_visits_user", "utm_visits", "user_id")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id INTEGER,
            ref_key TEXT,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_index(cursor, "idx_analytics_events_type", "analytics_events", "event_type")

    # utm_slug на пользователе — first-touch атрибуция
    _ensure_table_column(cursor, "users", "utm_slug", "TEXT")

    # Рассылки (автоматические сообщения пользователям без активных подписок)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcast_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            text_html TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            interval_hours INTEGER NOT NULL DEFAULT 72,
            target_segment TEXT NOT NULL DEFAULT 'inactive',
            send_count INTEGER DEFAULT 0,
            last_run_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcast_sends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _ensure_index(cursor, "idx_broadcast_sends_cuid_time", "broadcast_sends", "campaign_id, user_id, sent_at")


def get_all_ssh_targets() -> list[dict]:
    """Вернуть все SSH-цели для спидтестов (включая неактивные), сортировка по sort_order, затем по имени."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM speedtest_ssh_targets ORDER BY sort_order ASC, target_name ASC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить список SSH-целей: {e}")
        return []


def get_ssh_target(target_name: str) -> dict | None:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM speedtest_ssh_targets WHERE TRIM(target_name) = TRIM(?)", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить SSH-цель '{target_name}': {e}")
        return None


def create_ssh_target(
    target_name: str,
    ssh_host: str,
    ssh_port: int | None = 22,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
    ssh_key_path: str | None = None,
    description: str | None = None,
    *,
    sort_order: int | None = 0,
    is_active: int | None = 1,
) -> bool:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO speedtest_ssh_targets
                    (target_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path, description, is_active, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    (ssh_host or '').strip(),
                    int(ssh_port) if ssh_port is not None else None,
                    (ssh_user or None),
                    (ssh_password if ssh_password is not None else None),
                    (ssh_key_path or None),
                    (description or None),
                    1 if (is_active is None or int(is_active) != 0) else 0,
                    int(sort_order or 0),
                )
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось создать SSH-цель '{target_name}': {e}")
        return False


def update_ssh_target_fields(
    target_name: str,
    *,
    ssh_host: str | None = None,
    ssh_port: int | None = None,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
    ssh_key_path: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    is_active: int | None = None,
) -> bool:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM speedtest_ssh_targets WHERE TRIM(target_name) = TRIM(?)", (name,))
            if cursor.fetchone() is None:
                logging.warning(f"update_ssh_target_fields: цель не найдена '{name}'")
                return False
            sets: list[str] = []
            params: list[Any] = []
            if ssh_host is not None:
                sets.append("ssh_host = ?")
                params.append((ssh_host or '').strip())
            if ssh_port is not None:
                try:
                    val = int(ssh_port)
                except Exception:
                    val = None
                sets.append("ssh_port = ?")
                params.append(val)
            if ssh_user is not None:
                sets.append("ssh_user = ?")
                params.append(ssh_user or None)
            if ssh_password is not None:
                sets.append("ssh_password = ?")
                params.append(ssh_password)
            if ssh_key_path is not None:
                sets.append("ssh_key_path = ?")
                params.append(ssh_key_path or None)
            if description is not None:
                sets.append("description = ?")
                params.append(description or None)
            if sort_order is not None:
                try:
                    so = int(sort_order)
                except Exception:
                    so = 0
                sets.append("sort_order = ?")
                params.append(so)
            if is_active is not None:
                sets.append("is_active = ?")
                params.append(1 if int(is_active) != 0 else 0)
            if not sets:
                return True
            params.append(name)
            sql = f"UPDATE speedtest_ssh_targets SET {', '.join(sets)} WHERE TRIM(target_name) = TRIM(?)"
            cursor.execute(sql, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить SSH-цель '{target_name}': {e}")
        return False


def delete_ssh_target(target_name: str) -> bool:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM speedtest_ssh_targets WHERE TRIM(target_name) = TRIM(?)", (name,))
            affected = cursor.rowcount
            conn.commit()
            return affected > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось удалить SSH-цель '{target_name}': {e}")
        return False

def get_admin_stats() -> dict:
    """Return aggregated statistics for the admin dashboard.
    Includes:
    - total_users: count of users
    - total_keys: count of all keys
    - active_keys: keys with expire_at in the future
    - total_income: sum of amount_rub for successful transactions
    """
    stats = {
        "total_users": 0,
        "total_keys": 0,
        "active_keys": 0,
        "total_income": 0.0,

        "today_new_users": 0,
        "today_income": 0.0,
        "today_issued_keys": 0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users")
            row = cursor.fetchone()
            stats["total_users"] = (row[0] or 0) if row else 0


            cursor.execute("SELECT COUNT(*) FROM vpn_keys")
            row = cursor.fetchone()
            stats["total_keys"] = (row[0] or 0) if row else 0


            cursor.execute("SELECT COUNT(*) FROM vpn_keys WHERE expire_at IS NOT NULL AND datetime(expire_at) > CURRENT_TIMESTAMP")
            row = cursor.fetchone()
            stats["active_keys"] = (row[0] or 0) if row else 0


            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_rub), 0)
                FROM transactions
                WHERE status IN ('paid','success','succeeded')
                  AND LOWER(COALESCE(payment_method, '')) NOT IN ('balance', 'referral_transfer', 'referral_payout', 'referraltransfer')
                """
            )
            row = cursor.fetchone()
            stats["total_income"] = float(row[0] or 0.0) if row else 0.0



            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE date(registration_date) = date('now')"
            )
            row = cursor.fetchone()
            stats["today_new_users"] = (row[0] or 0) if row else 0


            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_rub), 0)
                FROM transactions
                WHERE status IN ('paid','success','succeeded')
                  AND date(created_date) = date('now')
                  AND LOWER(COALESCE(payment_method, '')) NOT IN ('balance', 'referral_transfer', 'referral_payout', 'referraltransfer')
                """
            )
            row = cursor.fetchone()
            stats["today_income"] = float(row[0] or 0.0) if row else 0.0


            cursor.execute(
                "SELECT COUNT(*) FROM vpn_keys WHERE date(COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)) = date('now')"
            )
            row = cursor.fetchone()
            stats["today_issued_keys"] = (row[0] or 0) if row else 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get admin stats: {e}")
    return stats


# === Раздел «Продажи и аналитика»: helper с единым условием "успешная транзакция" ===
# ВАЖНО: формула должна дословно совпадать с get_admin_stats()/statistics_page(),
# чтобы цифры не расходились между разделами админки.
_SUCCESS_TX_SQL = "status IN ('paid','success','succeeded')"
_NON_BALANCE_SQL = "LOWER(COALESCE(payment_method, '')) <> 'balance'"
# Чёрный список внутренних методов: всё остальное считаем «реальными деньгами».
# Точные значения в коде: 'Balance', 'ReferralBalance' (handlers / webapp).
_REAL_MONEY_SQL = (
    "LOWER(COALESCE(payment_method, '')) NOT IN ('balance', 'referralbalance')"
)


def get_sales_overview() -> dict:
    """Главный дашборд продаж (Этап 4.1 плана): выручка/транзакции/чек/плательщики
    за сегодня, 7, 30 дней и всё время + неуспешные/ожидающие платежи.
    Переиспользует те же SQL-условия успешности, что get_admin_stats()/statistics_page().
    """
    periods = {"today": 0, "d7": 7, "d30": 30, "all": None}
    result: dict = {}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for key, days in periods.items():
                if key == "today":
                    date_filter = "date(created_date) = date('now')"
                elif days is None:
                    date_filter = "1=1"
                else:
                    date_filter = f"date(created_date) >= date('now', '-{int(days) - 1} days')"

                cursor.execute(
                    f"""
                    SELECT COUNT(*), COALESCE(SUM(amount_rub), 0), COUNT(DISTINCT user_id)
                    FROM transactions
                    WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL} AND {date_filter}
                    """
                )
                cnt, revenue, unique_payers = cursor.fetchone() or (0, 0.0, 0)
                cnt = int(cnt or 0)
                revenue = float(revenue or 0.0)
                result[key] = {
                    "transactions": cnt,
                    "revenue": revenue,
                    "unique_payers": int(unique_payers or 0),
                    "avg_check": (revenue / cnt) if cnt > 0 else 0.0,
                }

            # Неуспешные / ожидающие / отменённые (за всё время)
            cursor.execute(
                f"""
                SELECT status, COUNT(*)
                FROM transactions
                WHERE NOT ({_SUCCESS_TX_SQL})
                GROUP BY status
                """
            )
            status_breakdown = {row[0] or "unknown": int(row[1] or 0) for row in cursor.fetchall()}
            result["failed_or_pending_by_status"] = status_breakdown

            cursor.execute("SELECT COUNT(*) FROM pending_transactions WHERE status = 'pending'")
            row = cursor.fetchone()
            result["pending_payments"] = int((row[0] if row else 0) or 0)

            # Новые / повторные плательщики (по первой успешной транзакции пользователя)
            cursor.execute(
                f"""
                WITH first_tx AS (
                    SELECT user_id, MIN(date(created_date)) AS first_day
                    FROM transactions
                    WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                    GROUP BY user_id
                )
                SELECT
                    SUM(CASE WHEN first_day >= date('now', '-29 days') THEN 1 ELSE 0 END) AS new_payers_30d,
                    COUNT(*) AS total_payers
                FROM first_tx
                """
            )
            new_payers_30d, total_payers = cursor.fetchone() or (0, 0)
            result["new_payers_30d"] = int(new_payers_30d or 0)
            result["total_payers"] = int(total_payers or 0)

            # Повторные покупки: доля плательщиков с >=2 успешными транзакциями
            cursor.execute(
                f"""
                SELECT
                    SUM(CASE WHEN cnt >= 2 THEN 1 ELSE 0 END) AS repeat_payers,
                    COUNT(*) AS all_payers
                FROM (
                    SELECT user_id, COUNT(*) AS cnt
                    FROM transactions
                    WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                    GROUP BY user_id
                )
                """
            )
            repeat_payers, all_payers = cursor.fetchone() or (0, 0)
            repeat_payers = int(repeat_payers or 0)
            all_payers = int(all_payers or 0)
            result["repeat_payers"] = repeat_payers
            result["repeat_conversion_pct"] = (repeat_payers / all_payers * 100.0) if all_payers > 0 else 0.0

            # MRR (оценочный): успешные платежи за последние 30 дней по тарифам с months/duration_days,
            # нормализованные к месяцу. Явно помечается в UI как оценка.
            cursor.execute(
                f"""
                SELECT metadata, amount_rub
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND date(created_date) >= date('now', '-29 days')
                """
            )
            mrr_estimate = 0.0
            for meta_str, amount in cursor.fetchall() or []:
                try:
                    meta = json.loads(meta_str) if meta_str else {}
                except Exception:
                    meta = {}
                months = meta.get("months") if isinstance(meta, dict) else None
                try:
                    months_f = float(months) if months else 1.0
                    if months_f <= 0:
                        months_f = 1.0
                except Exception:
                    months_f = 1.0
                try:
                    mrr_estimate += float(amount or 0.0) / months_f
                except Exception:
                    pass
            result["mrr_estimate"] = mrr_estimate
    except sqlite3.Error as e:
        logging.error(f"Failed to get sales overview: {e}")
    return result


def get_revenue_series(days: int = 30) -> dict:
    """Ряд выручки/транзакций по дням для графика раздела «Продажи и аналитика».
    Использует тот же SQL-фильтр успешности, что и get_sales_overview()."""
    series = {"revenue": {}, "transactions": {}}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT date(created_date) AS day, COALESCE(SUM(amount_rub), 0), COUNT(*)
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND date(created_date) >= date('now', ?)
                GROUP BY day
                ORDER BY day
                """,
                (f"-{max(1, int(days)) - 1} days",),
            )
            for day, revenue, cnt in cursor.fetchall() or []:
                series["revenue"][day] = float(revenue or 0.0)
                series["transactions"][day] = int(cnt or 0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get revenue series: {e}")
    return series


def get_plans_analytics(limit: int = 10) -> list[dict]:
    """Аналитика по тарифам (Этап 4.4): выручка, продажи, средний чек, доля повторных покупок."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT metadata, amount_rub, user_id
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            per_plan: dict[str, dict] = {}
            user_plan_counts: dict[tuple, int] = {}
            # Действия, которые НЕ являются покупкой/продлением тарифа и не должны
            # попадать в статистику "популярные тарифы" (пополнения баланса, докупки
            # трафика/LTE, сброс трафика и т.п.).
            _NON_PLAN_ACTIONS = {"top_up", "traffic_gb_topup", "lte_gb_topup", "main_traffic_reset", "referral_payout"}
            for meta_str, amount, user_id in cursor.fetchall() or []:
                try:
                    meta = json.loads(meta_str) if meta_str else {}
                except Exception:
                    meta = {}
                action = (meta.get("action") if isinstance(meta, dict) else None)
                if action in _NON_PLAN_ACTIONS:
                    continue
                plan_name = str((meta.get("plan_name") if isinstance(meta, dict) else None) or "N/A").strip() or "N/A"
                bucket = per_plan.setdefault(plan_name, {"plan_name": plan_name, "sales": 0, "revenue": 0.0})
                bucket["sales"] += 1
                bucket["revenue"] += float(amount or 0.0)
                key = (plan_name, user_id)
                user_plan_counts[key] = user_plan_counts.get(key, 0) + 1

            repeat_by_plan: dict[str, int] = {}
            for (plan_name, _uid), cnt in user_plan_counts.items():
                if cnt >= 2:
                    repeat_by_plan[plan_name] = repeat_by_plan.get(plan_name, 0) + 1

            for plan_name, bucket in per_plan.items():
                sales = bucket["sales"]
                bucket["avg_check"] = (bucket["revenue"] / sales) if sales > 0 else 0.0
                bucket["repeat_buyers"] = repeat_by_plan.get(plan_name, 0)
                result.append(bucket)

            result.sort(key=lambda b: b["revenue"], reverse=True)
            result = result[: max(1, int(limit))]
    except sqlite3.Error as e:
        logging.error(f"Failed to get plans analytics: {e}")
    return result


def get_payment_methods_analytics() -> list[dict]:
    """Аналитика по методам оплаты (Этап 4.5): число транзакций, выручка, успешность, динамика."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(payment_method, 'N/A') AS pm,
                       SUM(CASE WHEN status IN ('paid','success','succeeded') THEN 1 ELSE 0 END) AS success_cnt,
                       SUM(CASE WHEN status IN ('paid','success','succeeded') THEN amount_rub ELSE 0 END) AS success_sum,
                       COUNT(*) AS total_cnt
                FROM transactions
                WHERE LOWER(COALESCE(payment_method, '')) <> 'balance'
                GROUP BY pm
                ORDER BY success_sum DESC
                """
            )
            for pm, success_cnt, success_sum, total_cnt in cursor.fetchall() or []:
                total_cnt = int(total_cnt or 0)
                success_cnt = int(success_cnt or 0)
                result.append({
                    "payment_method": pm,
                    "success_transactions": success_cnt,
                    "revenue": float(success_sum or 0.0),
                    "total_attempts": total_cnt,
                    "success_rate_pct": (success_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0,
                })
    except sqlite3.Error as e:
        logging.error(f"Failed to get payment methods analytics: {e}")
    return result


def get_users_without_real_payment_with_keys() -> dict:
    """Пользователи с хотя бы одним VPN-ключом, у которых нет ни одной успешной
    транзакции, оплаченной реальными деньгами.

    Реальными деньгами НЕ считаются payment_method из чёрного списка
    Balance / ReferralBalance (регистр не важен). Проверка идёт по всем успешным
    транзакциям пользователя (включая пополнения баланса), а не только по покупке ключа.
    """
    result = {"users_with_key_no_real_payment": 0}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT k.user_id)
                FROM vpn_keys k
                WHERE k.user_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM transactions t
                      WHERE t.user_id = k.user_id
                        AND {_SUCCESS_TX_SQL}
                        AND {_REAL_MONEY_SQL}
                  )
                """
            )
            result["users_with_key_no_real_payment"] = int((cursor.fetchone() or [0])[0] or 0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get users without real payment with keys: {e}")
    return result


def get_trial_key_stats() -> dict:
    """Метрики по триальным ключам и их продлениям.

    - active_trial_users: пользователи с ключом tag='trial' и expire_at в будущем
    - total_trial_used: users.trial_used = 1
    - extended_trial_*: DISTINCT user_id с успешной транзакцией action='extend',
      где metadata.key_id указывает на первый ключ пользователя (trial выдаётся
      первым), и users.trial_used = 1.

    Важно: при продлении key_id НЕ меняется (UPDATE vpn_keys), но tag
    перезаписывается на 'paid' (см. process_successful_payment в bot/handlers.py),
    поэтому нельзя фильтровать текущий tag='trial' для продлений — используем
    связку «первый ключ пользователя» + trial_used.
    """
    result = {
        "active_trial_users": 0,
        "total_trial_used": 0,
        "extended_trial_real_money": 0,
        "extended_trial_via_referral_balance": 0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM vpn_keys
                WHERE LOWER(COALESCE(tag, '')) = 'trial'
                  AND expire_at IS NOT NULL
                  AND datetime(expire_at) > CURRENT_TIMESTAMP
                """
            )
            result["active_trial_users"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute("SELECT COUNT(*) FROM users WHERE trial_used = 1")
            result["total_trial_used"] = int((cursor.fetchone() or [0])[0] or 0)

            # Первый ключ пользователя (по created_at, затем key_id).
            # Продление триала: action=extend + metadata.key_id == этот первый ключ.
            first_key_match_sql = """
                CAST(json_extract(t.metadata, '$.key_id') AS INTEGER) = (
                    SELECT k2.key_id
                    FROM vpn_keys k2
                    WHERE k2.user_id = t.user_id
                    ORDER BY datetime(COALESCE(k2.created_at, '1970-01-01')) ASC, k2.key_id ASC
                    LIMIT 1
                )
            """

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT t.user_id)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.trial_used = 1
                  AND {_SUCCESS_TX_SQL}
                  AND {_REAL_MONEY_SQL}
                  AND json_extract(t.metadata, '$.action') = 'extend'
                  AND json_extract(t.metadata, '$.key_id') IS NOT NULL
                  AND {first_key_match_sql}
                """
            )
            result["extended_trial_real_money"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT t.user_id)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.trial_used = 1
                  AND {_SUCCESS_TX_SQL}
                  AND LOWER(COALESCE(t.payment_method, '')) = 'referralbalance'
                  AND json_extract(t.metadata, '$.action') = 'extend'
                  AND json_extract(t.metadata, '$.key_id') IS NOT NULL
                  AND {first_key_match_sql}
                """
            )
            result["extended_trial_via_referral_balance"] = int((cursor.fetchone() or [0])[0] or 0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get trial key stats: {e}")
    return result


def get_referrals_analytics() -> dict:
    """Аналитика реферальной программы (Этап 6.1) поверх существующих полей/функций,
    без создания новой реферальной системы."""
    data = {
        "referrers_count": 0,
        "referrals_count": 0,
        "active_referrals": 0,
        "paying_referrals": 0,
        "accrued_total": 0.0,
        "current_balance_total": 0.0,
        "spent_total": 0.0,
        "revenue_from_referrals": 0.0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL")
            data["referrers_count"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
            data["referrals_count"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                """
                SELECT COUNT(DISTINCT k.user_id)
                FROM vpn_keys k
                JOIN users u ON u.telegram_id = k.user_id
                WHERE u.referred_by IS NOT NULL
                  AND (k.expire_at IS NULL OR datetime(k.expire_at) > CURRENT_TIMESTAMP)
                """
            )
            data["active_referrals"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT t.user_id)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.referred_by IS NOT NULL AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            data["paying_referrals"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                f"""
                SELECT COALESCE(SUM(t.amount_rub), 0)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.referred_by IS NOT NULL AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            data["revenue_from_referrals"] = float((cursor.fetchone() or [0.0])[0] or 0.0)

            cursor.execute("SELECT COALESCE(SUM(referral_balance_all), 0), COALESCE(SUM(referral_balance), 0) FROM users")
            accrued_all, balance_now = cursor.fetchone() or (0.0, 0.0)
            data["accrued_total"] = float(accrued_all or 0.0)
            data["current_balance_total"] = float(balance_now or 0.0)
            data["spent_total"] = max(0.0, data["accrued_total"] - data["current_balance_total"])
    except sqlite3.Error as e:
        logging.error(f"Failed to get referrals analytics: {e}")
    return data


def get_top_referrers(limit: int = 10) -> list[dict]:
    """Топ пользователей по рефералам: число приглашённых и число платящих рефералов."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    u.referred_by AS referrer_id,
                    ref_owner.username AS referrer_username,
                    COUNT(DISTINCT u.telegram_id) AS invited_count,
                    SUM(CASE WHEN EXISTS (
                        SELECT 1 FROM transactions t
                        WHERE t.user_id = u.telegram_id AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                    ) THEN 1 ELSE 0 END) AS paying_count,
                    ref_owner.referral_balance_all AS bonus_total,
                    ref_owner.referral_balance AS current_balance
                FROM users u
                LEFT JOIN users ref_owner ON ref_owner.telegram_id = u.referred_by
                WHERE u.referred_by IS NOT NULL
                GROUP BY u.referred_by
                ORDER BY invited_count DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            for row in cursor.fetchall():
                result.append(dict(row))
    except sqlite3.Error as e:
        logging.error(f"Failed to get top referrers: {e}")
    return result


def get_top_buyers(limit: int = 10) -> list[dict]:
    """Топ пользователей по покупкам (Этап 6.4): сумма, число успешных транзакций, средний чек."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    t.user_id,
                    u.username,
                    u.total_spent,
                    COUNT(*) AS successful_tx,
                    COALESCE(SUM(t.amount_rub), 0) AS revenue
                FROM transactions t
                LEFT JOIN users u ON u.telegram_id = t.user_id
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                GROUP BY t.user_id
                ORDER BY revenue DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            for row in cursor.fetchall():
                d = dict(row)
                cnt = int(d.get("successful_tx") or 0)
                d["avg_check"] = (float(d.get("revenue") or 0.0) / cnt) if cnt > 0 else 0.0
                result.append(d)
    except sqlite3.Error as e:
        logging.error(f"Failed to get top buyers: {e}")
    return result


def _promo_plans_label(raw_ids) -> str:
    """Человекочитаемое ограничение тарифов для карточки купона в админке."""
    if raw_ids is None or str(raw_ids).strip() == "":
        return "все тарифы"
    try:
        parsed = json.loads(raw_ids) if not isinstance(raw_ids, (list, tuple)) else list(raw_ids)
        ids = [int(x) for x in parsed]
    except Exception:
        return "все тарифы"
    if not ids:
        return "все тарифы"
    return "тарифы: " + ", ".join(str(i) for i in ids)


def _promo_segment_label(segment_type, segment_value) -> str:
    """Человекочитаемое ограничение сегмента для карточки купона в админке."""
    st = (str(segment_type).strip() if segment_type is not None else "")
    if not st:
        return "без сегмента"
    if st == "no_active_subscription":
        return "нет активной подписки"
    if st == "min_total_spent":
        try:
            value = float(segment_value)
        except (TypeError, ValueError):
            value = 0.0
        return f"сумма покупок ≥ {value:.0f} ₽"
    return st


def get_coupons_analytics() -> list[dict]:
    """Аналитика купонов/промокодов (Этап 6.3) поверх существующих таблиц
    promo_codes / promo_code_usages — без создания новой системы купонов."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
            codes = [dict(r) for r in cursor.fetchall()]

            cursor.execute(
                """
                SELECT code, COUNT(*) AS uses, COALESCE(SUM(applied_amount), 0) AS discount_sum
                FROM promo_code_usages
                GROUP BY code
                """
            )
            usage_map = {row["code"]: dict(row) for row in cursor.fetchall()}

            # Выручка по купону: сопоставляем order_id использования с payment_id транзакции,
            # при отсутствии совпадения по order_id пробуем найти по user_id+ближайшему времени.
            cursor.execute(
                f"""
                SELECT payment_id, user_id, amount_rub, created_date
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            tx_by_payment_id = {}
            tx_by_user: dict[int, list] = {}
            for payment_id, user_id, amount_rub, created_date in cursor.fetchall() or []:
                if payment_id:
                    tx_by_payment_id[payment_id] = float(amount_rub or 0.0)
                tx_by_user.setdefault(user_id, []).append(float(amount_rub or 0.0))

            cursor.execute("SELECT code, order_id, user_id FROM promo_code_usages")
            revenue_by_code: dict[str, float] = {}
            for code, order_id, user_id in cursor.fetchall() or []:
                amount = None
                if order_id and order_id in tx_by_payment_id:
                    amount = tx_by_payment_id[order_id]
                elif user_id in tx_by_user and tx_by_user[user_id]:
                    amount = tx_by_user[user_id][0]
                if amount is not None:
                    revenue_by_code[code] = revenue_by_code.get(code, 0.0) + amount

            for c in codes:
                code = c["code"]
                usage = usage_map.get(code, {"uses": 0, "discount_sum": 0.0})
                uses = int(usage.get("uses") or 0)
                limit_total = c.get("usage_limit_total")
                c["uses"] = uses
                c["discount_sum"] = float(usage.get("discount_sum") or 0.0)
                c["revenue"] = float(revenue_by_code.get(code, 0.0))
                c["usage_conversion_pct"] = (uses / limit_total * 100.0) if limit_total else None
                try:
                    c["is_expired"] = bool(c.get("valid_until")) and str(c["valid_until"]) < _now_str()
                except Exception:
                    c["is_expired"] = False
                c["days_left"] = None
                if c.get("valid_until") and not c["is_expired"]:
                    try:
                        vu_raw = str(c["valid_until"])
                        vu_dt = datetime.fromisoformat(vu_raw.replace(" ", "T")) if "T" not in vu_raw else datetime.fromisoformat(vu_raw)
                        delta = vu_dt - datetime.now()
                        c["days_left"] = max(0, delta.days + (1 if delta.seconds > 0 else 0))
                    except Exception:
                        c["days_left"] = None
                c["targeting_plans_label"] = _promo_plans_label(c.get("applicable_plan_ids"))
                c["targeting_segment_label"] = _promo_segment_label(c.get("segment_type"), c.get("segment_value"))
                result.append(c)

            result.sort(key=lambda c: c["revenue"], reverse=True)
    except sqlite3.Error as e:
        logging.error(f"Failed to get coupons analytics: {e}")
    return result


def get_server_cost_entries(*, only_active: bool = False) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM server_cost_entries"
            if only_active:
                query += " WHERE status = 'active'"
            query += " ORDER BY created_at DESC"
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get server cost entries: {e}")
        return []


def create_server_cost_entry(
    server_label: str,
    *,
    linked_host_name: str | None = None,
    provider: str | None = None,
    location: str | None = None,
    monthly_cost: float = 0.0,
    currency: str = "RUB",
    status: str = "active",
    started_at=None,
    ended_at=None,
    comment: str | None = None,
) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO server_cost_entries
                    (server_label, linked_host_name, provider, location, monthly_cost, currency, status, started_at, ended_at, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (server_label or "").strip(),
                    (linked_host_name or None),
                    (provider or None),
                    (location or None),
                    float(monthly_cost or 0.0),
                    (currency or "RUB").strip() or "RUB",
                    (status or "active").strip() or "active",
                    started_at,
                    ended_at,
                    (comment or None),
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to create server cost entry: {e}")
        return None


def update_server_cost_entry(entry_id: int, **fields) -> bool:
    allowed = {
        "server_label", "linked_host_name", "provider", "location",
        "monthly_cost", "currency", "status", "started_at", "ended_at", "comment",
    }
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return False
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(int(entry_id))
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE server_cost_entries SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update server cost entry {entry_id}: {e}")
        return False


def delete_server_cost_entry(entry_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM server_cost_entries WHERE id = ?", (int(entry_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete server cost entry {entry_id}: {e}")
        return False


def get_economics_summary() -> dict:
    """Приблизительная экономика (Этап 7.3): расходы по провайдеру/локации,
    итог расходов, сопоставление с выручкой за 30 дней (без точной unit-экономики)."""
    result = {
        "total_monthly_cost_by_currency": {},
        "by_provider": [],
        "by_location": [],
        "revenue_30d": 0.0,
        "gross_profit_estimate_by_currency": {},
    }
    try:
        entries = get_server_cost_entries(only_active=True)
        by_provider: dict[str, float] = {}
        by_location: dict[str, float] = {}
        by_currency: dict[str, float] = {}
        for e in entries:
            cost = float(e.get("monthly_cost") or 0.0)
            currency = e.get("currency") or "RUB"
            provider = e.get("provider") or "N/A"
            location = e.get("location") or "N/A"
            by_provider[provider] = by_provider.get(provider, 0.0) + cost
            by_location[location] = by_location.get(location, 0.0) + cost
            by_currency[currency] = by_currency.get(currency, 0.0) + cost

        result["total_monthly_cost_by_currency"] = by_currency
        result["by_provider"] = [{"provider": k, "monthly_cost": v} for k, v in sorted(by_provider.items(), key=lambda x: -x[1])]
        result["by_location"] = [{"location": k, "monthly_cost": v} for k, v in sorted(by_location.items(), key=lambda x: -x[1])]

        overview = get_sales_overview()
        revenue_30d = float((overview.get("d30") or {}).get("revenue") or 0.0)
        result["revenue_30d"] = revenue_30d
        # Оценка маржи только для RUB (основная валюта проекта), остальные валюты — только расходы без сопоставления.
        rub_cost = by_currency.get("RUB", 0.0)
        result["gross_profit_estimate_by_currency"]["RUB"] = revenue_30d - rub_cost
    except Exception as e:
        logging.error(f"Failed to get economics summary: {e}")
    return result


def get_revenue_forecast() -> dict:
    """Прозрачный прогноз (Этап 4.6/9): скользящее среднее за 7 дней + линейная
    экстраполяция до конца текущего месяца. Помечается как оценка в UI."""
    from calendar import monthrange
    result = {
        "daily_avg_revenue_7d": 0.0,
        "daily_avg_transactions_7d": 0.0,
        "revenue_so_far_this_month": 0.0,
        "days_left_in_month": 0,
        "forecast_revenue_month_end": 0.0,
        "forecast_transactions_month_end": 0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(amount_rub), 0), COUNT(*)
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND date(created_date) >= date('now', '-6 days')
                """
            )
            rev7, cnt7 = cursor.fetchone() or (0.0, 0)
            daily_avg_revenue = float(rev7 or 0.0) / 7.0
            daily_avg_tx = float(cnt7 or 0) / 7.0

            now = datetime.now()
            days_in_month = monthrange(now.year, now.month)[1]
            days_left = max(0, days_in_month - now.day)

            cursor.execute(
                f"""
                SELECT COALESCE(SUM(amount_rub), 0), COUNT(*)
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND strftime('%Y-%m', created_date) = strftime('%Y-%m', 'now')
                """
            )
            rev_month, cnt_month = cursor.fetchone() or (0.0, 0)

            result["daily_avg_revenue_7d"] = daily_avg_revenue
            result["daily_avg_transactions_7d"] = daily_avg_tx
            result["revenue_so_far_this_month"] = float(rev_month or 0.0)
            result["days_left_in_month"] = days_left
            result["forecast_revenue_month_end"] = float(rev_month or 0.0) + daily_avg_revenue * days_left
            result["forecast_transactions_month_end"] = int(cnt_month or 0) + round(daily_avg_tx * days_left)
    except Exception as e:
        logging.error(f"Failed to get revenue forecast: {e}")
    return result


def get_utm_links(*, only_active: bool = False) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM utm_links"
            if only_active:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get utm links: {e}")
        return []


def create_utm_link(
    slug: str,
    *,
    source: str | None = None,
    medium: str | None = None,
    campaign: str | None = None,
    content: str | None = None,
    term: str | None = None,
    label: str | None = None,
    comment: str | None = None,
    budget: float | None = None,
    created_by: int | None = None,
) -> bool:
    slug_s = re.sub(r"[^a-zA-Z0-9_\-]", "", (slug or "").strip())
    if not slug_s:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO utm_links (slug, source, medium, campaign, content, term, label, comment, budget, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (slug_s, source, medium, campaign, content, term, label, comment,
                 float(budget) if budget is not None else None, created_by),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        logging.error(f"Failed to create utm link '{slug_s}': {e}")
        return False


def delete_utm_link(slug: str) -> bool:
    """Удаляет UTM-метку вместе с накопленной статистикой посещений (utm_visits)."""
    slug_s = (slug or "").strip()
    if not slug_s:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM utm_visits WHERE slug = ?", (slug_s,))
            cursor.execute("DELETE FROM utm_links WHERE slug = ?", (slug_s,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete utm link '{slug_s}': {e}")
        return False


def log_utm_visit(slug: str, user_id: int | None, event_type: str) -> None:
    """Best-effort запись события UTM (клик/старт/регистрация/оплата). Никогда не бросает исключение наружу."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO utm_visits (slug, user_id, event_type) VALUES (?, ?, ?)",
                ((slug or "").strip(), user_id, (event_type or "").strip()),
            )
            conn.commit()
    except Exception as e:
        logging.warning(f"log_utm_visit failed for slug={slug}: {e}")


def set_user_utm_slug_if_absent(user_id: int, slug: str) -> bool:
    """First-touch атрибуция: записать utm_slug пользователю только если он ещё не задан."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET utm_slug = ? WHERE telegram_id = ? AND (utm_slug IS NULL OR utm_slug = '')",
                ((slug or "").strip(), int(user_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set utm_slug for user {user_id}: {e}")
        return False


def get_utm_analytics() -> list[dict]:
    """Эффективность UTM-меток (Этап 5.4): клики, регистрации, оплаты, выручка, ROI (если задан budget)."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            links = [dict(r) for r in cursor.execute("SELECT * FROM utm_links ORDER BY created_at DESC").fetchall()]

            cursor.execute("SELECT slug, COUNT(*) FROM utm_visits WHERE event_type = 'start' GROUP BY slug")
            clicks_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT utm_slug, COUNT(*) FROM users WHERE utm_slug IS NOT NULL AND utm_slug <> '' GROUP BY utm_slug")
            regs_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(
                f"""
                SELECT u.utm_slug, COUNT(*), COALESCE(SUM(t.amount_rub), 0)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.utm_slug IS NOT NULL AND u.utm_slug <> '' AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                GROUP BY u.utm_slug
                """
            )
            payments_map = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            for link in links:
                slug = link["slug"]
                clicks = int(clicks_map.get(slug, 0))
                regs = int(regs_map.get(slug, 0))
                pays_cnt, pays_sum = payments_map.get(slug, (0, 0.0))
                link["clicks"] = clicks
                link["registrations"] = regs
                link["payments"] = int(pays_cnt or 0)
                link["revenue"] = float(pays_sum or 0.0)
                budget = link.get("budget")
                link["roi_pct"] = ((link["revenue"] - budget) / budget * 100.0) if budget else None
                result.append(link)

            result.sort(key=lambda l: l["revenue"], reverse=True)
    except sqlite3.Error as e:
        logging.error(f"Failed to get utm analytics: {e}")
    return result


# =============================
# Рассылки
# =============================

def create_broadcast_campaign(name: str, text_html: str, interval_hours: int = 72, target_segment: str = "inactive") -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO broadcast_campaigns (name, text_html, interval_hours, target_segment) VALUES (?, ?, ?, ?)",
                (name.strip(), text_html.strip(), int(interval_hours), target_segment),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error("Failed to create broadcast campaign: %s", e)
        return None


def get_broadcast_campaigns() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM broadcast_campaigns ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to get broadcast campaigns: %s", e)
        return []


def get_broadcast_campaign(campaign_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM broadcast_campaigns WHERE id = ?", (int(campaign_id),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("Failed to get broadcast campaign %s: %s", campaign_id, e)
        return None


def update_broadcast_campaign(campaign_id: int, *, name: str, text_html: str, interval_hours: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE broadcast_campaigns SET name=?, text_html=?, interval_hours=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (name.strip(), text_html.strip(), int(interval_hours), int(campaign_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to update broadcast campaign %s: %s", campaign_id, e)
        return False


def toggle_broadcast_campaign(campaign_id: int) -> bool:
    """Flip is_active. Returns new is_active state."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_active FROM broadcast_campaigns WHERE id = ?", (int(campaign_id),))
            row = cursor.fetchone()
            if not row:
                return False
            new_state = 0 if row[0] else 1
            cursor.execute(
                "UPDATE broadcast_campaigns SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_state, int(campaign_id)),
            )
            conn.commit()
            return bool(new_state)
    except sqlite3.Error as e:
        logging.error("Failed to toggle broadcast campaign %s: %s", campaign_id, e)
        return False


def delete_broadcast_campaign(campaign_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM broadcast_sends WHERE campaign_id = ?", (int(campaign_id),))
            cursor.execute("DELETE FROM broadcast_campaigns WHERE id = ?", (int(campaign_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to delete broadcast campaign %s: %s", campaign_id, e)
        return False


# Псевдо-telegram_id для email-аккаунтов без привязки к Telegram
# (см. create_user_by_email). В этот диапазон бот писать не может.
EMAIL_ONLY_TELEGRAM_ID_MIN = 999000000000
EMAIL_ONLY_TELEGRAM_ID_MAX = 999999999999


def is_email_only_user(telegram_id: int | None) -> bool:
    """True, если пользователь зарегистрирован по email и ещё не авторизовался
    через Telegram (синтетический telegram_id с префиксом 999)."""
    try:
        tid = int(telegram_id)
    except (TypeError, ValueError):
        return False
    return EMAIL_ONLY_TELEGRAM_ID_MIN <= tid <= EMAIL_ONLY_TELEGRAM_ID_MAX


def get_inactive_subscribers() -> list[int]:
    """User IDs with no active keys (expire_at in the past or no keys at all),
    not banned, not marked unreachable (blocked the bot / deactivated account),
    and not email-only accounts without Telegram auth."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.telegram_id FROM users u
                WHERE u.is_banned = 0
                  AND (u.is_unreachable IS NULL OR u.is_unreachable = 0)
                  AND (u.telegram_id < ? OR u.telegram_id > ?)
                  AND NOT EXISTS (
                    SELECT 1 FROM vpn_keys k
                    WHERE k.user_id = u.telegram_id
                      AND k.expire_at > datetime('now')
                  )
                """,
                (EMAIL_ONLY_TELEGRAM_ID_MIN, EMAIL_ONLY_TELEGRAM_ID_MAX),
            )
            return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to get inactive subscribers: %s", e)
        return []


def get_pending_broadcast_recipients(campaign_id: int, interval_hours: int) -> list[int]:
    """Inactive users who haven't been sent this campaign in the last `interval_hours`."""
    inactive = set(get_inactive_subscribers())
    if not inactive:
        return []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT user_id FROM broadcast_sends
                WHERE campaign_id = ?
                  AND sent_at > datetime('now', '-' || ? || ' hours')
                """,
                (int(campaign_id), int(interval_hours)),
            )
            recently_sent = {row[0] for row in cursor.fetchall()}
        return [uid for uid in inactive if uid not in recently_sent]
    except sqlite3.Error as e:
        logging.error("Failed to get pending broadcast recipients: %s", e)
        return []


def record_broadcast_sends(campaign_id: int, user_ids: list[int]) -> int:
    """Insert send records and bump campaign send_count. Returns count inserted."""
    if not user_ids:
        return 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO broadcast_sends (campaign_id, user_id) VALUES (?, ?)",
                [(int(campaign_id), int(uid)) for uid in user_ids],
            )
            cursor.execute(
                "UPDATE broadcast_campaigns SET last_run_at=CURRENT_TIMESTAMP, send_count=COALESCE(send_count,0)+?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (len(user_ids), int(campaign_id)),
            )
            conn.commit()
            return len(user_ids)
    except sqlite3.Error as e:
        logging.error("Failed to record broadcast sends for campaign %s: %s", campaign_id, e)
        return 0


def mark_broadcast_run(campaign_id: int) -> None:
    """Update last_run_at even when there are no recipients (avoids tight retry loops)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE broadcast_campaigns SET last_run_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(campaign_id),),
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error("Failed to mark broadcast run for campaign %s: %s", campaign_id, e)


def get_broadcast_stats(campaign_id: int) -> dict:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), MAX(sent_at) FROM broadcast_sends WHERE campaign_id = ?", (int(campaign_id),))
            row = cursor.fetchone()
            return {"total_sends": int(row[0] or 0), "last_sent_at": row[1]}
    except sqlite3.Error as e:
        logging.error("Failed to get broadcast stats for campaign %s: %s", campaign_id, e)
        return {"total_sends": 0, "last_sent_at": None}


def get_all_keys() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys")
            return [_normalize_key_row(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get all keys: {e}")
        return []


def get_all_key_ids() -> list[int]:
    """Все key_id из vpn_keys (без фильтров/пагинации) — для bulk-действий «всем»."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key_id FROM vpn_keys ORDER BY key_id ASC")
            return [int(row[0]) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to get all key ids: %s", e)
        return []


def extend_key(key_id: int, days: int) -> tuple[bool, str | None]:
    """Продлить/сократить срок ключа на N дней (с синхронизацией Remnawave).

    Реализация делегируется в remnawave_repository (lazy import — избегаем цикла).
    """
    from shop_bot.data_manager import remnawave_repository as _rw

    return _rw.extend_key(key_id, days)


def set_key_expiry(key_id: int, new_expire_at) -> tuple[bool, str | None]:
    """Установить точную дату истечения ключа (с синхронизацией Remnawave)."""
    from shop_bot.data_manager import remnawave_repository as _rw

    return _rw.set_key_expiry(key_id, new_expire_at)


def get_keys_paginated(page: int = 1, per_page: int = 25, search: str | None = None, sort_by: str | None = None, sort_dir: str | None = None, user_id: int | None = None) -> tuple[list[dict], int]:
    try:
        page_i = max(1, int(page))
    except Exception:
        page_i = 1
    try:
        per_i = max(1, int(per_page))
    except Exception:
        per_i = 25
    offset = (page_i - 1) * per_i
    search_q = (search or "").strip()
    conditions: list = []
    params: list = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(int(user_id))
    if search_q:
        like = f"%{search_q}%"
        conditions.append(
            "(CAST(key_id AS TEXT) LIKE ? OR CAST(user_id AS TEXT) LIKE ?"
            " OR key_email LIKE ? OR email LIKE ? OR user_key_name LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_columns = {
        "user_id": "user_id",
        "host_name": "host_name",
        "created_at": "COALESCE(created_at, updated_at, key_id)",
        "expire_at": "expire_at",
    }
    sort_col = sort_columns.get((sort_by or "").strip(), sort_columns["created_at"])
    sort_direction = "ASC" if (sort_dir or "").strip().lower() == "asc" else "DESC"
    order_sql = f"ORDER BY {sort_col} {sort_direction}"
    if sort_col != sort_columns["created_at"]:
        order_sql += f", {sort_columns['created_at']} DESC"

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM vpn_keys{where_sql}", params)
            total = cursor.fetchone()[0] or 0
            cursor.execute(
                f"""
                SELECT *
                FROM vpn_keys
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                (*params, per_i, offset),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows], int(total)
    except sqlite3.Error as e:
        logging.error(f"Failed to get paginated keys: {e}")
        return [], 0


def get_keys_for_user(user_id: int) -> list[dict]:
    return get_user_keys(user_id)

def update_key_email(key_id: int, new_email: str) -> bool:
    normalized = _normalize_email(new_email) or new_email.strip()
    return update_key_fields(key_id, email=normalized)

def update_key_host(key_id: int, new_host_name: str) -> bool:
    return update_key_fields(key_id, host_name=new_host_name)

def create_gift_key(user_id: int, host_name: str, key_email: str, months: int, remnawave_user_uuid: str | None = None) -> int | None:
    """Создать подарочный ключ: expiry = now + months."""
    try:
        from datetime import timedelta

        months_value = max(1, int(months or 1))
        expiry_dt = datetime.utcnow() + timedelta(days=30 * months_value)
        expiry_ms = int(expiry_dt.timestamp() * 1000)
        uuid_value = remnawave_user_uuid or f"GIFT-{user_id}-{int(datetime.utcnow().timestamp())}"
        return add_new_key(
            user_id=user_id,
            host_name=host_name,
            remnawave_user_uuid=uuid_value,
            key_email=key_email,
            expiry_timestamp_ms=expiry_ms,
        )
    except sqlite3.Error as e:
        logging.error(f"Failed to create gift key for user {user_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to create gift key for user {user_id}: {e}")
        return None

def get_setting(key: str) -> str | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get setting '{key}': {e}")
        return None

def get_admin_ids() -> set[int]:
    """Возвращает множество ID администраторов из настроек.
    Поддерживает оба варианта: одиночный 'admin_telegram_id' и список 'admin_telegram_ids'
    через запятую/пробелы или JSON-массив.
    """
    ids: set[int] = set()
    try:
        single = get_setting("admin_telegram_id")
        if single:
            try:
                ids.add(int(single))
            except Exception:
                pass
        multi_raw = get_setting("admin_telegram_ids")
        if multi_raw:
            s = (multi_raw or "").strip()

            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    for v in arr:
                        try:
                            ids.add(int(v))
                        except Exception:
                            pass
                    return ids
            except Exception:
                pass

            parts = [p for p in re.split(r"[\s,]+", s) if p]
            for p in parts:
                try:
                    ids.add(int(p))
                except Exception:
                    pass
    except Exception as e:
        logging.warning(f"get_admin_ids failed: {e}")
    return ids

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора по списку ID из настроек."""
    try:
        return int(user_id) in get_admin_ids()
    except Exception:
        return False

def _connect_pending_db() -> sqlite3.Connection:
    """Connection helper for high-contention tables (webhooks/bot)."""
    conn = sqlite3.connect(DB_FILE, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn


def _retry_sqlite(work, attempts: int = 5, base_sleep: float = 0.05):
    for i in range(attempts):
        try:
            return work()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(base_sleep * (2 ** i))
                continue
            raise


def _ensure_pending_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS pending_transactions (
            payment_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount_rub REAL,
            metadata TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )


def _ensure_processed_payments_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS processed_payments (
            payment_id TEXT PRIMARY KEY,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )


def create_payload_pending(payment_id: str, user_id: int, amount_rub, metadata) -> bool:
    """Create/update pending payload metadata.

    Important: does NOT revive already paid rows (keeps status='paid' intact).
    """
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)

            cursor.execute(
                '''
                INSERT INTO pending_transactions (payment_id, user_id, amount_rub, metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(payment_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    amount_rub = excluded.amount_rub,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
                WHERE pending_transactions.status = 'pending'
                ''',
                (
                    pid,
                    int(user_id),
                    float(amount_rub) if amount_rub is not None else None,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            return True

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to create payload pending {pid}: {e}")
        return False


def _get_pending_metadata(payment_id: str) -> dict | None:
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT metadata FROM pending_transactions WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw = row[0] if isinstance(row, (tuple, list)) else row["metadata"]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            meta.setdefault("payment_id", pid)
            return meta

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to read pending transaction {pid}: {e}")
        return None


def get_pending_metadata(payment_id: str) -> dict | None:
    """Public wrapper to fetch pending metadata by payment_id WITHOUT marking it paid."""
    return _get_pending_metadata(payment_id)


def get_pending_status(payment_id: str) -> str | None:
    """Return status of pending transaction: 'pending', 'paid', or None if not found."""
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute("SELECT status FROM pending_transactions WHERE payment_id = ?", (pid,))
            row = cursor.fetchone()
            if not row:
                return None
            return (row[0] or "").strip() or None

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to get status for pending {pid}: {e}")
        return None


def _complete_pending(payment_id: str) -> bool:
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "UPDATE pending_transactions SET status = 'paid', updated_at = CURRENT_TIMESTAMP WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            return cursor.rowcount == 1

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to complete pending transaction {pid}: {e}")
        return False


def find_and_complete_pending_transaction(payment_id: str) -> dict | None:
    """Atomically mark pending transaction as paid and return its metadata.

    Returns None when payment_id is unknown OR already processed.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)

            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT metadata FROM pending_transactions WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            row = cursor.fetchone()
            if not row:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

            cursor.execute(
                "UPDATE pending_transactions SET status = 'paid', updated_at = CURRENT_TIMESTAMP WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            if cursor.rowcount != 1:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

            conn.commit()

            raw = row[0] if isinstance(row, (tuple, list)) else row["metadata"]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            meta.setdefault("payment_id", pid)
            return meta

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to complete pending transaction {pid}: {e}")
        return None


def get_latest_pending_for_user(user_id: int) -> dict | None:
    """Return metadata of the most recent PENDING transaction for the user (without completing it)."""
    try:
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                """
                SELECT payment_id, metadata
                FROM pending_transactions
                WHERE user_id = ? AND status = 'pending'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            pid = row[0] if isinstance(row, (tuple, list)) else row["payment_id"]
            raw = row[1] if isinstance(row, (tuple, list)) else row["metadata"]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            meta.setdefault("payment_id", pid)
            return meta
    except sqlite3.Error as e:
        logging.error(f"Failed to get latest pending for user {user_id}: {e}")
        return None


def claim_processed_payment(payment_id: str) -> bool:
    """Idempotency guard: returns True only once per payment_id."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_processed_payments_table(cursor)
            cursor.execute(
                "INSERT OR IGNORE INTO processed_payments (payment_id, processed_at) VALUES (?, CURRENT_TIMESTAMP)",
                (pid,),
            )
            return cursor.rowcount == 1

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to claim processed payment {pid}: {e}")
        return False


def unclaim_processed_payment(payment_id: str) -> bool:
    """Remove idempotency record so a failed payment can be retried."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_processed_payments_table(cursor)
            cursor.execute("DELETE FROM processed_payments WHERE payment_id = ?", (pid,))
            return cursor.rowcount > 0

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to unclaim processed payment {pid}: {e}")
        return False


def refund_payment_once(
    payment_id: str,
    user_id: int,
    amount: float,
    payment_method: str | None = None,
) -> bool:
    """Вернуть средства за невыданную услугу не более одного раза на payment_id.

    Идемпотентность через ``processed_payments`` с ключом ``refund:{payment_id}`` —
    повторный вызов (retry сети / двойной except) не зачислит сумму дважды.
    Balance → add_to_balance; ReferralBalance → add_to_referral_balance;
    прочие методы (внешние платежи) → add_to_balance (как раньше при сбое выдачи ключа).
    """
    pid = (payment_id or "").strip()
    if not pid or amount is None:
        return False
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return False
    if amount_f <= 0:
        return False

    refund_key = f"refund:{pid}"
    if not claim_processed_payment(refund_key):
        logging.info(
            "refund_payment_once: skip duplicate refund for payment_id=%s user_id=%s",
            pid,
            user_id,
        )
        return False

    pm = (payment_method or "").strip().lower()
    try:
        if pm == "referralbalance":
            ok = bool(add_to_referral_balance(int(user_id), amount_f))
        else:
            ok = bool(add_to_balance(int(user_id), amount_f))
    except Exception as e:
        logging.error(
            "refund_payment_once: credit failed for payment_id=%s user_id=%s: %s",
            pid,
            user_id,
            e,
            exc_info=True,
        )
        ok = False

    if not ok:
        # позволить повторную попытку отката
        try:
            unclaim_processed_payment(refund_key)
        except Exception:
            pass
        return False
    logging.info(
        "refund_payment_once: refunded %.2f via %s for payment_id=%s user_id=%s",
        amount_f,
        pm or "balance",
        pid,
        user_id,
    )
    return True


def cancel_pending_transaction(payment_id: str, user_id: int | None = None) -> bool:
    """Пометить неоплаченный pending как cancelled, чтобы Stars/вебхук его не закрыли.

    Меняет только ``status='pending'``. Уже paid не трогает. Если передан user_id —
    только строка этого владельца.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            if user_id is not None:
                cursor.execute(
                    """
                    UPDATE pending_transactions
                    SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE payment_id = ? AND status = 'pending' AND user_id = ?
                    """,
                    (pid, int(user_id)),
                )
            else:
                cursor.execute(
                    """
                    UPDATE pending_transactions
                    SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE payment_id = ? AND status = 'pending'
                    """,
                    (pid,),
                )
            return cursor.rowcount == 1

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to cancel pending transaction {pid}: {e}")
        return False


def reset_pending_transaction(payment_id: str) -> bool:
    """Reset a completed pending transaction back to 'pending' to allow webhook retry."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "UPDATE pending_transactions SET status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE payment_id = ?",
                (pid,),
            )
            return cursor.rowcount > 0

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to reset pending transaction {pid}: {e}")
        return False


def get_referrals_for_user(user_id: int) -> list[dict]:
    """Возвращает список пользователей, которых пригласил данный user_id.
    Поля: telegram_id, username, registration_date, total_spent.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT telegram_id, username, registration_date, total_spent
                FROM users
                WHERE referred_by = ?
                ORDER BY registration_date DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Failed to get referrals for user {user_id}: {e}")
        return []
        

def get_referral_top_rich(limit: int = 5) -> list[dict]:
    """
    Возвращает топ пользователей по количеству рефералов,
    которые пополнили баланс хотя бы один раз (total_spent > 0).
    Поля: telegram_id, rich_referrals.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT referred_by AS telegram_id,
                       COUNT(*) AS rich_referrals
                FROM users
                WHERE referred_by IS NOT NULL
                  AND referred_by <> 0
                  AND COALESCE(total_spent, 0) > 0
                GROUP BY referred_by
                HAVING rich_referrals > 0
                ORDER BY rich_referrals DESC, referred_by ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral top rich: {e}")
        return []


def get_referral_rank_and_count(user_id: int) -> tuple[int | None, int]:
    """
    Возвращает кортеж (rank, count), где:
      - rank — место пользователя в рейтинге по количеству
        рефералов с пополнением баланса (total_spent > 0),
        либо None, если пользователь не попадает в рейтинг;
      - count — количество таких рефералов у пользователя.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT referred_by AS telegram_id,
                       COUNT(*) AS rich_referrals
                FROM users
                WHERE referred_by IS NOT NULL
                  AND referred_by <> 0
                  AND COALESCE(total_spent, 0) > 0
                GROUP BY referred_by
                HAVING rich_referrals > 0
                ORDER BY rich_referrals DESC, referred_by ASC
                """
            )
            rows = cursor.fetchall()

            rank: int | None = None
            personal_count: int = 0

            for index, (telegram_id, rich_referrals) in enumerate(rows, start=1):
                if telegram_id == user_id:
                    rank = index
                    personal_count = int(rich_referrals or 0)
                    break

            if rank is None:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM users
                    WHERE referred_by = ?
                      AND COALESCE(total_spent, 0) > 0
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                personal_count = int(row[0] or 0) if row else 0

            return rank, personal_count
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral rank for user {user_id}: {e}")
        return None, 0

def get_all_settings() -> dict:
    settings = {}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM bot_settings")
            rows = cursor.fetchall()
            for row in rows:
                settings[row['key']] = row['value']
    except sqlite3.Error as e:
        logging.error(f"Failed to get all settings: {e}")
    return settings

def update_setting(key: str, value: str):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            logging.info(f"Setting '{key}' updated.")
    except sqlite3.Error as e:
        logging.error(f"Failed to update setting '{key}': {e}")


def get_button_configs(menu_type: str) -> list[dict]:
    """Get *active* button configurations for a specific menu type.

    Note: this function is used by the bot to build keyboards at runtime, so it
    intentionally filters by `is_active = 1`.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM button_configs 
                WHERE menu_type = ? AND is_active = 1 
                ORDER BY sort_order, row_position, column_position
            """, (menu_type,))
            results = [dict(row) for row in cursor.fetchall()]

            return results
    except sqlite3.Error as e:
        logging.error(f"Failed to get button configs for {menu_type}: {e}")
        return []


def get_button_configs_admin(menu_type: str, *, include_inactive: bool = True) -> list[dict]:
    """Get button configurations for admin/editor UIs.

    Unlike `get_button_configs`, this can return inactive buttons too, so that
    admins can re-enable them.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if include_inactive:
                cursor.execute(
                    """
                    SELECT * FROM button_configs
                    WHERE menu_type = ?
                    ORDER BY sort_order, row_position, column_position
                    """,
                    (menu_type,),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM button_configs
                    WHERE menu_type = ? AND is_active = 1
                    ORDER BY sort_order, row_position, column_position
                    """,
                    (menu_type,),
                )
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get (admin) button configs for {menu_type}: {e}")
        return []


def get_button_config_by_db_id(button_db_id: int) -> dict | None:
    """Get a button configuration by its numeric DB id."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM button_configs WHERE id = ?", (button_db_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get button config by id={button_db_id}: {e}")
        return None

def get_button_config(menu_type: str, button_id: str) -> dict | None:
    """Get a specific button configuration by menu_type and button_id"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM button_configs 
                WHERE menu_type = ? AND button_id = ?
            """, (menu_type, button_id))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except sqlite3.Error as e:
        logging.error(f"Failed to get button config for {menu_type}/{button_id}: {e}")
        return None

def create_button_config(
    menu_type: str,
    button_id: str,
    text: str,
    callback_data: str = None,
    url: str = None,
    row_position: int = 0,
    column_position: int = 0,
    button_width: int = 1,
    is_active: bool | int = 1,
    sort_order: int = 0,
    metadata: str = None,
) -> bool:
    """Create a new button configuration"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            active_val = 1 if bool(is_active) else 0
            cursor.execute(
                """
                INSERT OR REPLACE INTO button_configs 
                (menu_type, button_id, text, callback_data, url, row_position, column_position, button_width, is_active, sort_order, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    menu_type,
                    button_id,
                    text,
                    callback_data,
                    url,
                    row_position,
                    column_position,
                    button_width,
                    active_val,
                    sort_order,
                    metadata,
                ),
            )
            conn.commit()
            logging.info(f"Button config created: {menu_type}/{button_id}")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to create button config: {e}")
        return False

def update_button_config(button_id: int, text: str = None, callback_data: str = None, 
                        url: str = None, row_position: int = None, column_position: int = None, 
                        button_width: int = None, is_active: bool = None, sort_order: int = None, metadata: str = None) -> bool:
    """Update an existing button configuration"""
    try:
        logging.info(f"update_button_config called for {button_id}: text={text}, callback_data={callback_data}, url={url}, row={row_position}, col={column_position}, active={is_active}, sort={sort_order}")
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            

            updates = []
            params = []
            
            if text is not None:
                updates.append("text = ?")
                params.append(text)
            if callback_data is not None:
                updates.append("callback_data = ?")
                params.append(callback_data)
            if url is not None:
                updates.append("url = ?")
                params.append(url)
            if row_position is not None:
                updates.append("row_position = ?")
                params.append(row_position)
            if column_position is not None:
                updates.append("column_position = ?")
                params.append(column_position)
            if button_width is not None:
                updates.append("button_width = ?")
                params.append(button_width)
            if is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if is_active else 0)
            if sort_order is not None:
                updates.append("sort_order = ?")
                params.append(sort_order)
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(metadata)
            
            if not updates:
                return True
                
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(button_id)
            
            query = f"UPDATE button_configs SET {', '.join(updates)} WHERE id = ?"
            logging.info(f"Executing query: {query} with params: {params}")
            cursor.execute(query, params)
            
            if cursor.rowcount == 0:
                logging.warning(f"No button found with id {button_id}")
                return False
                
            conn.commit()
            logging.info(f"Button config {button_id} updated successfully")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to update button config {button_id}: {e}")
        return False

def delete_button_config(button_id: int) -> bool:
    """Delete a button configuration"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM button_configs WHERE id = ?", (button_id,))
            conn.commit()
            logging.info(f"Button config {button_id} deleted")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to delete button config {button_id}: {e}")
        return False

def update_existing_my_keys_button():
    """Update existing my_keys button to include key count template and set proper button widths"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE button_configs 
                SET text = '🔑 Мои ключи ({len(user_keys)})', updated_at = CURRENT_TIMESTAMP
                WHERE menu_type = 'main_menu' AND button_id = 'my_keys'
            """)
            if cursor.rowcount > 0:
                logging.info("Updated my_keys button text to include key count template")
            

            wide_buttons = [
                ("trial", 2),
                ("referral", 2),
                ("admin", 2),
            ]
            
            for button_id, width in wide_buttons:
                cursor.execute("""
                    UPDATE button_configs 
                    SET button_width = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE menu_type = 'main_menu' AND button_id = ?
                """, (width, button_id))
                if cursor.rowcount > 0:
                    logging.info(f"Updated {button_id} button width to {width}")
            
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update button configurations: {e}")


def ensure_main_menu_gift_button() -> None:
    """Ensure that the main menu has the gift button in button configs."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'main_menu' AND button_id = 'gift_new_key' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("main_menu", "gift_new_key", "🎁 Подарить", "gift_new_key", row_pos, 0, next_sort, 2),
            )
            conn.commit()
            logging.info("Inserted missing main_menu button: gift_new_key")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure main menu gift button: {e}")


def ensure_main_menu_referral_button() -> None:
    """Ensure that the main menu has the referral program button in button configs,
    and that it's removed from the profile menu (moved from "Мой профиль" в главное меню).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Убираем кнопку из меню "Мой профиль" (перенесена в главное меню)
            cursor.execute(
                "DELETE FROM button_configs WHERE menu_type = 'profile_menu' AND button_id = 'referral'"
            )
            if cursor.rowcount > 0:
                logging.info("Removed referral button from profile_menu (moved to main_menu)")

            cursor.execute(
                "SELECT is_active FROM button_configs WHERE menu_type = 'main_menu' AND button_id = 'referral' LIMIT 1"
            )
            row = cursor.fetchone()
            if row is not None:
                if int(row[0] or 0) != 1:
                    cursor.execute(
                        "UPDATE button_configs SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE menu_type = 'main_menu' AND button_id = 'referral'"
                    )
                    logging.info("Re-activated referral button in main_menu")
                conn.commit()
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("main_menu", "referral", "🤝 Реферальная программа", "show_referral_program", row_pos, 0, next_sort, 2),
            )
            conn.commit()
            logging.info("Inserted missing main_menu button: referral")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure main menu referral button: {e}")


def ensure_admin_plans_button():
    """Ensure that the Admin menu has a button for managing тарифы (plans).

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'admin_menu' AND button_id = 'plans' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'admin_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            row_pos = 0
            col_pos = 0
            try:
                cursor.execute(
                    "SELECT row_position, column_position FROM button_configs WHERE menu_type='admin_menu' AND button_id='back_to_menu' LIMIT 1"
                )
                row = cursor.fetchone()
                if row:
                    row_pos = int(row[0] or 0)
                    back_col = int(row[1] or 0)

                    candidate_col = 1 if back_col == 0 else back_col + 1
                    cursor.execute(
                        "SELECT 1 FROM button_configs WHERE menu_type='admin_menu' AND row_position=? AND column_position=? LIMIT 1",
                        (row_pos, candidate_col),
                    )
                    if cursor.fetchone():
                        cursor.execute(
                            "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
                        )
                        row_pos = int(cursor.fetchone()[0] or 0) + 1
                        col_pos = 0
                    else:
                        col_pos = candidate_col
                else:
                    cursor.execute(
                        "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
                    )
                    row_pos = int(cursor.fetchone()[0] or 0) + 1
                    col_pos = 0
            except Exception:
                cursor.execute(
                    "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
                )
                row_pos = int(cursor.fetchone()[0] or 0) + 1
                col_pos = 0

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("admin_menu", "plans", "🧾 Тарифы", "admin_plans", row_pos, col_pos, next_sort, 1),
            )
            conn.commit()
            logging.info("Inserted missing admin_menu button: plans")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure admin plans button: {e}")




def ensure_admin_trial_button():
    """Ensure that the Admin menu has a button for managing Trial settings.

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'admin_menu' AND button_id = 'trial_settings' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'admin_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1
            col_pos = 0

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("admin_menu", "trial_settings", "🎁 Триал", "admin_trial", row_pos, col_pos, next_sort, 1),
            )
            conn.commit()
            logging.info("Inserted missing admin_menu button: trial_settings")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure admin trial button: {e}")


def ensure_admin_auto_renew_button():
    """Ensure that the Admin settings submenu has a button for Автопродление (auto-renew).

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty. Existing databases created before this button
    was introduced (button_configs already populated for admin_settings_menu) never get it
    backfilled by "CREATE TABLE IF NOT EXISTS", so we do it here on every startup instead.
    This only inserts the row if it is truly absent, so it never overwrites an admin's
    existing customization of this button.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'admin_settings_menu' AND button_id = 'auto_renew' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'admin_settings_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type='admin_settings_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1
            col_pos = 0

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("admin_settings_menu", "auto_renew", "🔄 Автопродление", "admin_auto_renew", row_pos, col_pos, next_sort, 1),
            )
            conn.commit()
            logging.info("Inserted missing admin_settings_menu button: auto_renew")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure admin auto-renew button: {e}")


def reorder_button_configs(menu_type: str, button_orders: list[dict]) -> bool:
    """Reorder button configurations for a menu type"""
    try:
        logging.info(f"Reordering {len(button_orders)} buttons for {menu_type}")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for order_data in button_orders:
                button_id = order_data.get('button_id')
                sort_order = order_data.get('sort_order', 0)
                row_position = order_data.get('row_position', 0)
                column_position = order_data.get('column_position', 0)
                button_width = order_data.get('button_width', None)
                
                logging.info(f"Updating {button_id}: sort={sort_order}, row={row_position}, col={column_position}, width={button_width}")
                

                if button_width is not None:
                    cursor.execute(
                        """
                        UPDATE button_configs 
                        SET sort_order = ?, row_position = ?, column_position = ?, button_width = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE menu_type = ? AND button_id = ?
                        """,
                        (sort_order, row_position, column_position, int(button_width), menu_type, button_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE button_configs 
                        SET sort_order = ?, row_position = ?, column_position = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE menu_type = ? AND button_id = ?
                        """,
                        (sort_order, row_position, column_position, menu_type, button_id),
                    )
                

                if cursor.rowcount == 0:
                    logging.warning(f"No button found with menu_type={menu_type}, button_id={button_id}")
                else:
                    logging.info(f"Updated button {button_id}")
                    
            conn.commit()
            logging.info(f"Button configs reordered for {menu_type}")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to reorder button configs for {menu_type}: {e}")
        return False

def initialize_default_button_configs():
    """Initialize default button configurations for all menu types"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            

            cursor.execute("SELECT COUNT(*) FROM button_configs")
            count = cursor.fetchone()[0]
            if count > 0:
                logging.info("Button configs already exist, skipping initialization")
                return True
            

            main_menu_buttons = [
                ("trial", "🎁 Попробовать бесплатно", "get_trial", 0, 0, 0, 2),
                ("profile", "👤 Мой профиль", "show_profile", 1, 0, 1, 1),
                ("my_keys", "🔑 Мои ключи ({len(user_keys)})", "manage_keys", 1, 1, 2, 1),
                ("buy_key", "🛒 Купить ключ", "buy_new_key", 2, 0, 3, 1),
                ("topup", "💳 Пополнить баланс", "top_up_start", 2, 1, 4, 1),
                ("gift_new_key", "🎁 Подарить", "gift_new_key", 3, 0, 5, 2),
                ("referral", "🤝 Реферальная программа", "show_referral_program", 3, 1, 6, 2),
                ("support", "🆘 Поддержка", "show_help", 4, 0, 7, 1),
                ("about", "ℹ️ О проекте", "show_about", 4, 1, 8, 1),
                ("speed", "⚡ Скорость", "user_speedtest_last", 5, 0, 9, 1),
                ("howto", "❓ Как использовать", "howto_vless", 5, 1, 10, 1),
                ("admin", "⚙️ Админка", "admin_menu", 6, 0, 10, 2),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order, button_width in main_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """, ("main_menu", button_id, text, callback_data, row_pos, col_pos, sort_order, button_width))
            

            admin_menu_buttons = [
                ("users", "👥 Пользователи", "admin_users", 0, 0, 0),
                ("host_keys", "🌍 Ключи на хосте", "admin_host_keys", 0, 1, 1),
                ("gift_key", "🎁 Выдать ключ", "admin_gift_key", 1, 0, 2),
                ("promo", "🎟 Промокоды", "admin_promo_menu", 1, 1, 3),
                ("speedtest", "⚡ Тест скорости", "admin_speedtest", 2, 0, 4),
                ("monitor", "📊 Мониторинг", "admin_monitor", 2, 1, 5),
                ("backup", "🗄 Бэкап БД", "admin_backup_db", 3, 0, 6),
                ("restore", "♻️ Восстановить БД", "admin_restore_db", 3, 1, 7),
                ("admins", "👮 Администраторы", "admin_admins_menu", 4, 0, 8),
                ("broadcast", "📢 Рассылка", "start_broadcast", 4, 1, 9),
                ("trial_settings", "🎁 Триал", "admin_trial", 5, 0, 10),
                ("plans", "🧾 Тарифы", "admin_plans", 5, 1, 11),
                ("back_to_menu", "⬅️ Назад в меню", "back_to_main_menu", 6, 0, 12),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in admin_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("admin_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            

            profile_menu_buttons = [
                ("topup", "💳 Пополнить баланс", "top_up_start", 0, 0, 0),
                ("referral", "🤝 Реферальная программа", "show_referral_program", 1, 0, 1),
                ("back_to_menu", "⬅️ Назад в меню", "back_to_main_menu", 2, 0, 2),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in profile_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("profile_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            

            support_menu_buttons = [
                ("new_ticket", "✍️ Новое обращение", "support_new_ticket", 0, 0, 0),
                ("my_tickets", "📨 Мои обращения", "support_my_tickets", 1, 0, 1),
                ("external", "🆘 Внешняя поддержка", "support_external", 2, 0, 2),
                ("back_to_menu", "⬅️ Назад в меню", "back_to_main_menu", 3, 0, 3),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in support_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("support_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            
            # Admin System Menu (подменю)
            admin_system_menu_buttons = [
                ("speedtest", "⚡ Тест скорости", "admin_speedtest", 0, 0, 0),
                ("monitor", "📊 Мониторинг", "admin_monitor", 0, 1, 1),
                ("backup", "🗄 Бэкап БД", "admin_backup_db", 1, 0, 2),
                ("restore", "♻️ Восстановить БД", "admin_restore_db", 1, 1, 3),
                ("back_to_admin", "⬅️ Назад", "admin_menu", 2, 0, 4),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in admin_system_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("admin_system_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            
            # Admin Settings Menu (подменю)
            admin_settings_menu_buttons = [
                ("admins", "👮 Администраторы", "admin_admins_menu", 0, 0, 0),
                ("plans", "🧾 Тарифы", "admin_plans", 0, 1, 1),
                ("hosts", "🖥 Хосты", "admin_hosts_menu", 1, 0, 2),
                ("payments", "💳 Платежки", "admin_payments_menu", 1, 1, 3),
                ("referral", "👥 Рефералка", "admin_referral", 2, 0, 4),
                ("franchise", "💼 Франшиза", "admin_franchise", 2, 1, 5),
                ("modules", "🧩 Модули", "admin_modules", 3, 0, 6),
                ("trial", "🎁 Триал", "admin_trial", 3, 1, 7),
                ("notifications", "🔔 Уведомления", "admin_notifications_menu", 4, 0, 8),
                ("captcha", "🛡️ Капча", "admin_captcha_settings", 4, 1, 9),
                ("btn_constructor", "🧩 Конструктор кнопок", "admin_btn_constructor", 5, 0, 10),
                ("auto_renew", "🔄 Автопродление", "admin_auto_renew", 5, 1, 11),
                ("back_to_admin", "⬅️ Назад", "admin_menu", 6, 0, 12),
            ]
            
            for button_id, text, callback_data, row_pos, col_pos, sort_order in admin_settings_menu_buttons:
                cursor.execute("""
                    INSERT INTO button_configs 
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, ("admin_settings_menu", button_id, text, callback_data, row_pos, col_pos, sort_order))
            
            conn.commit()
            logging.info("Default button configurations initialized")
            return True
            
    except sqlite3.Error as e:
        logging.error(f"Failed to initialize default button configs: {e}")
        return False

def create_plan(host_name: str, plan_name: str, months: int | None, price: float, duration_days: int | None = None, traffic_limit_bytes: int | None = None, hwid_device_limit: int | None = None, lte_limit_bytes: int | None = None, main_reset_price_rub: float | None = None):
    try:
        host_name = normalize_host_name(host_name)
        # Если лимит трафика явно не указан (None) — по умолчанию считаем его равным 0 (без лимита),
        # а не NULL, чтобы избежать неоднозначности NULL/0 в дальнейшей логике (сравнения, экспорт в API и т.д.).
        traffic_limit_bytes = int(traffic_limit_bytes) if traffic_limit_bytes is not None else 0
        if traffic_limit_bytes < 0:
            traffic_limit_bytes = 0
        # Для лимита трафика стратегия имеет смысл только если лимит задан.
        # 'MONTH_ROLLING' — трафик сбрасывается ежемесячно, отсчитывая от даты создания ключа (rolling-цикл),
        # в отличие от 'MONTH', который сбрасывает трафик по календарным месяцам.
        traffic_limit_strategy = 'MONTH_ROLLING' if traffic_limit_bytes > 0 else None
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO plans (host_name, plan_name, months, duration_days, price, traffic_limit_bytes, traffic_limit_strategy, hwid_device_limit, lte_limit_bytes, main_reset_price_rub) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (host_name, plan_name, months, duration_days, price, traffic_limit_bytes, traffic_limit_strategy, hwid_device_limit, lte_limit_bytes or 0, main_reset_price_rub or 0)
            )
            conn.commit()
            logging.info(f"Created new plan '{plan_name}' for host '{host_name}'.")
    except sqlite3.Error as e:
        logging.error(f"Failed to create plan for host '{host_name}': {e}")


def get_plans_for_host(host_name: str) -> list[dict]:
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE TRIM(host_name) = TRIM(?) ORDER BY sort_order, COALESCE(duration_days, months*30, months, 0)", (host_name,))
            plans = cursor.fetchall()
            return [dict(plan) for plan in plans]
    except sqlite3.Error as e:
        logging.error(f"Failed to get plans for host '{host_name}': {e}")
        return []



def get_active_plans_for_host(host_name: str) -> list[dict]:
    """Возвращает только активные тарифы (is_active = 1) для указанного хоста."""
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM plans WHERE TRIM(host_name) = TRIM(?) AND COALESCE(is_active, 1) = 1 ORDER BY sort_order, COALESCE(duration_days, months*30, months, 0)",
                (host_name,)
            )
            plans = cursor.fetchall()
            return [dict(plan) for plan in plans]
    except sqlite3.Error as e:
        logging.error(f"Failed to get active plans for host '{host_name}': {e}")
        return []


def set_plan_active(plan_id: int, is_active: bool) -> bool:
    """Включить/выключить тариф (скрыть/показать пользователям)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plans SET is_active = ? WHERE plan_id = ?",
                (1 if is_active else 0, int(plan_id))
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set plan active status for id {plan_id}: {e}")
        return False

def get_plan_by_id(plan_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
            plan = cursor.fetchone()
            return dict(plan) if plan else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get plan by id '{plan_id}': {e}")
        return None


def get_all_plans() -> list[dict]:
    """Все тарифы (для админки промокодов и валидации applicable_plan_ids)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM plans
                ORDER BY TRIM(host_name), sort_order,
                         COALESCE(duration_days, months * 30, months, 0), plan_id
                """
            )
            return [dict(plan) for plan in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to list all plans: %s", e)
        return []


def _parse_json_metadata(raw: str | None) -> dict:
    try:
        if not raw:
            return {}
        return json.loads(raw)
    except Exception:
        return {}

def update_plan_metadata(plan_id: int, metadata: dict | None) -> bool:
    """Update plan.metadata JSON blob.

    `metadata=None` or empty dict will clear the field.
    """
    try:
        raw = None
        if metadata:
            raw = json.dumps(metadata, ensure_ascii=False)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE plans SET metadata = ? WHERE plan_id = ?", (raw, int(plan_id)))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update plan metadata for id {plan_id}: {e}")
        return False


def create_traffic_package(plan_id: int, size_gb: float, price: float, pool: str = 'main') -> int | None:
    pool = 'lte' if str(pool).strip().lower() == 'lte' else 'main'
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM traffic_packages WHERE plan_id = ? AND COALESCE(pool, 'main') = ?",
                (int(plan_id), pool)
            )
            next_sort = (cursor.fetchone()[0] or 0) + 1
            cursor.execute(
                "INSERT INTO traffic_packages (plan_id, size_gb, price, sort_order, pool) VALUES (?, ?, ?, ?, ?)",
                (int(plan_id), float(size_gb), float(price), next_sort, pool)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to create traffic package for plan {plan_id}: {e}")
        return None


def get_traffic_packages_for_plan(plan_id: int, only_active: bool = False, pool: str = 'main') -> list[dict]:
    pool = 'lte' if str(pool).strip().lower() == 'lte' else 'main'
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM traffic_packages WHERE plan_id = ? AND COALESCE(pool, 'main') = ?"
            if only_active:
                query += " AND COALESCE(is_active, 1) = 1"
            query += " ORDER BY sort_order, size_gb"
            cursor.execute(query, (int(plan_id), pool))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get traffic packages for plan {plan_id}: {e}")
        return []


def get_traffic_package_by_id(package_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traffic_packages WHERE package_id = ?", (int(package_id),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get traffic package by id {package_id}: {e}")
        return None


def update_traffic_package(package_id: int, *, size_gb: float | None = None, price: float | None = None, is_active: bool | None = None) -> bool:
    fields: dict[str, Any] = {}
    if size_gb is not None:
        fields["size_gb"] = float(size_gb)
    if price is not None:
        fields["price"] = float(price)
    if is_active is not None:
        fields["is_active"] = 1 if is_active else 0
    if not fields:
        return False
    try:
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [int(package_id)]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE traffic_packages SET {set_clause} WHERE package_id = ?", values)
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update traffic package {package_id}: {e}")
        return False


def delete_traffic_package(package_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM traffic_packages WHERE package_id = ?", (int(package_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete traffic package {package_id}: {e}")
        return False


def set_key_traffic_boost(key_id: int, boost_bytes: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE vpn_keys SET traffic_boost_bytes = ? WHERE key_id = ?",
                (int(boost_bytes), int(key_id))
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set traffic boost for key {key_id}: {e}")
        return False


def get_plan_lte_limit(plan_id: int) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT lte_limit_bytes FROM plans WHERE plan_id = ?", (int(plan_id),))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] else 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get lte_limit_bytes for plan {plan_id}: {e}")
        return 0


def get_lte_state(user_id: int) -> dict:
    """Возвращает состояние независимого LTE-пула трафика пользователя (создаёт запись при отсутствии)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscription_lte WHERE user_id = ?", (int(user_id),))
            row = cursor.fetchone()
            if row:
                return dict(row)
            cursor.execute(
                "INSERT INTO subscription_lte (user_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, premium_state) "
                "VALUES (?, 0, 0, 0, 'enabled')",
                (int(user_id),)
            )
            conn.commit()
            return {
                "user_id": int(user_id),
                "lte_limit_bytes": 0,
                "lte_used_bytes": 0,
                "lte_boost_bytes": 0,
                "lte_used_baseline_bytes": 0,
                "lte_baseline_reset_requested": 0,
                "lte_reset_at": None,
                "premium_state": "enabled",
            }
    except sqlite3.Error as e:
        logging.error(f"Failed to get LTE state for user {user_id}: {e}")
        return {
            "user_id": int(user_id),
            "lte_limit_bytes": 0,
            "lte_used_bytes": 0,
            "lte_boost_bytes": 0,
            "lte_used_baseline_bytes": 0,
            "lte_baseline_reset_requested": 0,
            "lte_reset_at": None,
            "premium_state": "enabled",
        }


def request_lte_baseline_reset(user_id: int) -> bool:
    """Помечает, что нужно сдвинуть точку отсчёта (baseline) LTE-расхода пользователя на "сейчас".

    Вызывается при докупке LTE-пакета (или ином событии, обнуляющем LTE-счётчик), чтобы
    воркер `enforce_dual_traffic_limits` на следующем проходе зафиксировал текущее сырое
    (накопительное) значение расхода по premium-нодам как новую точку отсчёта — иначе
    накопленный панелью исторический трафик по нодам мгновенно "съест" свежекупленный лимит.
    """
    get_lte_state(user_id)  # ensure row exists
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE subscription_lte SET lte_baseline_reset_requested = 1, updated_at = ? WHERE user_id = ?",
                (_now_str(), int(user_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to request LTE baseline reset for user {user_id}: {e}")
        return False


def update_lte_state(
    user_id: int,
    *,
    lte_limit_bytes: int | None = None,
    lte_used_bytes: int | None = None,
    lte_boost_bytes: int | None = None,
    lte_used_baseline_bytes: int | None = None,
    lte_baseline_reset_requested: bool | None = None,
    lte_reset_at: Any = _UNSET,
    premium_state: str | None = None,
) -> bool:
    get_lte_state(user_id)  # ensure row exists
    fields: dict[str, Any] = {}
    if lte_limit_bytes is not None:
        fields["lte_limit_bytes"] = int(lte_limit_bytes)
    if lte_used_bytes is not None:
        fields["lte_used_bytes"] = int(lte_used_bytes)
    if lte_boost_bytes is not None:
        fields["lte_boost_bytes"] = int(lte_boost_bytes)
    if lte_used_baseline_bytes is not None:
        fields["lte_used_baseline_bytes"] = int(lte_used_baseline_bytes)
    if lte_baseline_reset_requested is not None:
        fields["lte_baseline_reset_requested"] = 1 if lte_baseline_reset_requested else 0
    if lte_reset_at is not _UNSET:
        fields["lte_reset_at"] = lte_reset_at
    if premium_state is not None:
        fields["premium_state"] = premium_state
    if not fields:
        return True
    fields["updated_at"] = _now_str()
    try:
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [int(user_id)]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE subscription_lte SET {set_clause} WHERE user_id = ?", values)
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update LTE state for user {user_id}: {e}")
        return False


def delete_plan(plan_id: int) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM traffic_packages WHERE plan_id = ?", (plan_id,))
            cursor.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))
            conn.commit()
            logging.info(f"Deleted plan with id {plan_id}.")
    except sqlite3.Error as e:
        logging.error(f"Failed to delete plan with id {plan_id}: {e}")

def update_plan(plan_id: int, plan_name: str, months: int | None, price: float, *, duration_days: Any = _UNSET, traffic_limit_bytes: Any = _UNSET, hwid_device_limit: Any = _UNSET, lte_limit_bytes: Any = _UNSET, main_reset_price_rub: Any = _UNSET) -> bool:
    try:
        fields: dict[str, Any] = {
            "plan_name": plan_name,
            "months": months,
            "price": price,
        }
        if duration_days is not _UNSET:
            fields["duration_days"] = duration_days
        if traffic_limit_bytes is not _UNSET:
            fields["traffic_limit_bytes"] = traffic_limit_bytes
            try:
                fields["traffic_limit_strategy"] = 'MONTH_ROLLING' if (traffic_limit_bytes is not None and int(traffic_limit_bytes) > 0) else None
            except Exception:
                fields["traffic_limit_strategy"] = None
        if hwid_device_limit is not _UNSET:
            fields["hwid_device_limit"] = hwid_device_limit
        if lte_limit_bytes is not _UNSET:
            fields["lte_limit_bytes"] = lte_limit_bytes
        if main_reset_price_rub is not _UNSET:
            fields["main_reset_price_rub"] = main_reset_price_rub

        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [plan_id]

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE plans SET {set_clause} WHERE plan_id = ?", values)
            conn.commit()
            if cursor.rowcount == 0:
                logging.warning(f"No plan updated for id {plan_id} (not found).")
                return False
            logging.info(f"Updated plan {plan_id}: {fields}.")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to update plan {plan_id}: {e}")
        return False


def register_user_if_not_exists(telegram_id: int, username: str, referrer_id):
    """Зарегистрировать пользователя, если его ещё нет.

    ``referred_by`` выставляется только на INSERT. Уже существующая строка
    обновляет username и никогда не late-bind'ит реферера — иначе любой
    ``/start ref_<id>`` мог привязать аккаунт, у которого поле ещё пустое.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            if not row:

                cursor.execute(
                    "INSERT INTO users (telegram_id, username, registration_date, referred_by) VALUES (?, ?, ?, ?)",
                    (telegram_id, username, datetime.now(), referrer_id)
                )
            else:

                cursor.execute("UPDATE users SET username = ? WHERE telegram_id = ?", (username, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to register user {telegram_id}: {e}")

def add_to_referral_balance(user_id: int, amount: float) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE telegram_id = ?", (amount, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to add to referral balance for user {user_id}: {e}")
        return False

def set_referral_balance(user_id: int, value: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = ? WHERE telegram_id = ?", (value, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set referral balance for user {user_id}: {e}")

def set_referral_balance_all(user_id: int, value: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance_all = ? WHERE telegram_id = ?", (value, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set total referral balance for user {user_id}: {e}")

def add_to_referral_balance_all(user_id: int, amount: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET referral_balance_all = referral_balance_all + ? WHERE telegram_id = ?",
                (amount, user_id)
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to add to total referral balance for user {user_id}: {e}")

def get_referral_balance_all(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referral_balance_all FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total referral balance for user {user_id}: {e}")
        return 0.0

def get_referral_balance(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral balance for user {user_id}: {e}")
        return 0.0

def get_balance(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get balance for user {user_id}: {e}")
        return 0.0

def adjust_user_balance(user_id: int, delta: float) -> bool:
    """Скорректировать баланс пользователя на указанную дельту (может быть отрицательной)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE telegram_id = ?", (float(delta), user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to adjust balance for user {user_id}: {e}")
        return False

def adjust_user_referral_balance(user_id: int, delta: float) -> bool:
    """Скорректировать реферальный баланс пользователя на указанную дельту (может быть отрицательной)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = COALESCE(referral_balance, 0) + ? WHERE telegram_id = ?", (float(delta), user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to adjust referral balance for user {user_id}: {e}")
        return False

def set_balance(user_id: int, value: float) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (value, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set balance for user {user_id}: {e}")
        return False

def add_to_balance(user_id: int, amount: float) -> bool:
    try:
        logging.info(f"💳 Добавляем {amount:.2f} RUB к балансу пользователя {user_id}")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT telegram_id, balance FROM users WHERE telegram_id = ?", (int(user_id),))
            user_row = cursor.fetchone()
            if not user_row:
                logging.error(f"❌ Пользователь {user_id} не найден в базе данных")
                return False
            
            old_balance = user_row[1] or 0.0
            cursor.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE telegram_id = ?",
                (float(amount), int(user_id))
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                new_balance = old_balance + float(amount)
                logging.info(f"✅ Баланс обновлен: пользователь {user_id} | {old_balance:.2f} → {new_balance:.2f} RUB (+{amount:.2f})")
            else:
                logging.error(f"❌ Не удалось обновить баланс для пользователя {user_id}: строки не затронуты")
            return success
    except sqlite3.Error as e:
        logging.error(f"💥 Ошибка базы данных при пополнении баланса для пользователя {user_id}: {e}")
        return False

def deduct_from_balance(user_id: int, amount: float) -> bool:
    """Атомарное списание с основного баланса при достаточности средств."""
    if amount <= 0:
        return True
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            current = row[0] if row and row[0] is not None else 0.0
            if current < amount:
                conn.rollback()
                return False
            cursor.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE telegram_id = ?",
                (float(amount), int(user_id))
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to deduct from balance for user {user_id}: {e}")
        return False

def deduct_from_referral_balance(user_id: int, amount: float) -> bool:
    """Атомарное списание с реферального баланса при достаточности средств."""
    if amount <= 0:
        return True
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            current = row[0] if row else 0.0
            if current < amount:
                conn.rollback()
                return False
            cursor.execute("UPDATE users SET referral_balance = referral_balance - ? WHERE telegram_id = ?", (amount, user_id))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to deduct from referral balance for user {user_id}: {e}")
        return False


# =============================
# Реферальная программа: методы получения выплат и заявки на вывод
# =============================

REFERRAL_PAYOUT_METHOD_TYPES = ("sbp", "card", "usdt_trc20")
REFERRAL_WITHDRAWAL_STATUSES = ("new", "processing", "paid", "rejected")


def list_referral_payout_methods(user_id: int) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM referral_payout_methods WHERE user_id = ? ORDER BY created_at DESC",
                (int(user_id),),
            )
            return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to list referral payout methods for {user_id}: {e}")
        return []


def add_referral_payout_method(user_id: int, method_type: str, requisite_value: str, bank_name: str | None = None) -> tuple[bool, str, int | None]:
    method_type = (method_type or "").strip().lower()
    if method_type not in REFERRAL_PAYOUT_METHOD_TYPES:
        return False, "Неизвестный тип метода получения.", None
    requisite_value = (requisite_value or "").strip()
    if not requisite_value:
        return False, "Реквизиты не могут быть пустыми.", None
    if method_type == "sbp" and not (bank_name or "").strip():
        return False, "Не указан банк для СБП.", None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO referral_payout_methods (user_id, method_type, bank_name, requisite_value) VALUES (?, ?, ?, ?)",
                (int(user_id), method_type, (bank_name or "").strip() or None, requisite_value),
            )
            conn.commit()
            return True, "Метод получения добавлен.", int(cur.lastrowid)
    except sqlite3.Error as e:
        logging.error(f"Failed to add referral payout method for {user_id}: {e}")
        return False, "Ошибка базы данных.", None


def delete_referral_payout_method(method_id: int, user_id: int) -> tuple[bool, str]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM referral_payout_methods WHERE id = ? AND user_id = ?",
                (int(method_id), int(user_id)),
            )
            conn.commit()
            if cur.rowcount > 0:
                return True, "Метод получения удалён."
            return False, "Метод получения не найден."
    except sqlite3.Error as e:
        logging.error(f"Failed to delete referral payout method {method_id}: {e}")
        return False, "Ошибка базы данных."


def get_referral_payout_method(method_id: int, user_id: int | None = None) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if user_id is not None:
                cur.execute(
                    "SELECT * FROM referral_payout_methods WHERE id = ? AND user_id = ?",
                    (int(method_id), int(user_id)),
                )
            else:
                cur.execute("SELECT * FROM referral_payout_methods WHERE id = ?", (int(method_id),))
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral payout method {method_id}: {e}")
        return None


def create_webapp_auth_request(token: str) -> bool:
    """Создаёт запись ожидания подтверждения входа через deep-link бота (user_id пока NULL)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO webapp_auth_requests (token, user_id, created_at) VALUES (?, NULL, CURRENT_TIMESTAMP)",
                (str(token),),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to create webapp auth request {token}: {e}")
        return False


def confirm_webapp_auth_request(token: str, user_id: int) -> bool:
    """Подтверждает вход: бот вызывает эту функцию после получения deep-link auth_{token}."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT token FROM webapp_auth_requests WHERE token = ?", (str(token),))
            if not cursor.fetchone():
                return False
            cursor.execute(
                "UPDATE webapp_auth_requests SET user_id = ? WHERE token = ?",
                (int(user_id), str(token)),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to confirm webapp auth request {token}: {e}")
        return False


def get_webapp_auth_request(token: str, *, consume: bool = False) -> int | None:
    """Возвращает user_id, если запрос уже подтверждён ботом, иначе None.

    Если consume=True и запрос подтверждён, удаляет запись (одноразовое использование).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM webapp_auth_requests WHERE token = ?", (str(token),))
            row = cursor.fetchone()
            if not row or row[0] is None:
                return None
            user_id = int(row[0])
            if consume:
                cursor.execute("DELETE FROM webapp_auth_requests WHERE token = ?", (str(token),))
                conn.commit()
            return user_id
    except sqlite3.Error as e:
        logging.error(f"Failed to get webapp auth request {token}: {e}")
        return None


def cleanup_old_webapp_auth_requests(max_age_minutes: int = 30) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM webapp_auth_requests WHERE created_at < datetime('now', ?)",
                (f"-{int(max_age_minutes)} minutes",),
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to cleanup webapp auth requests: {e}")


def create_referral_withdrawal_request(user_id: int, amount: float, method_id: int) -> tuple[bool, str, int | None]:
    """Атомарно списывает сумму с referral_balance пользователя и создаёт заявку на вывод."""
    raw_enabled = str(get_setting("referral_withdraw_enabled") or "false").strip().lower()
    if raw_enabled not in {"1", "true", "yes", "on", "y"}:
        return False, "Вывод средств временно недоступен.", None
    try:
        amount = float(amount or 0)
    except Exception:
        return False, "Некорректная сумма.", None
    if amount <= 0:
        return False, "Некорректная сумма.", None
    try:
        min_withdraw = float(get_setting("minimum_withdrawal") or 100)
    except Exception:
        min_withdraw = 100.0
    if amount < min_withdraw:
        return False, f"Минимальная сумма для вывода — {min_withdraw:.0f} ₽", None
    method = get_referral_payout_method(method_id, user_id)
    if not method:
        return False, "Метод получения не найден.", None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (int(user_id),))
            row = cursor.fetchone()
            current = float(row[0] or 0.0) if row else 0.0
            if current < amount:
                conn.rollback()
                return False, "Сумма в заявке превышает остаток на реферальном балансе.", None
            cursor.execute(
                "UPDATE users SET referral_balance = referral_balance - ? WHERE telegram_id = ?",
                (amount, int(user_id)),
            )
            cursor.execute(
                """
                INSERT INTO referral_withdrawal_requests (user_id, amount, method_type, bank_name, requisite_value, status)
                VALUES (?, ?, ?, ?, ?, 'new')
                """,
                (int(user_id), amount, method.get("method_type"), method.get("bank_name"), method.get("requisite_value")),
            )
            new_id = cursor.lastrowid
            conn.commit()
            return True, "Заявка на вывод создана.", int(new_id)
    except sqlite3.Error as e:
        logging.error(f"Failed to create referral withdrawal request for {user_id}: {e}")
        return False, "Ошибка базы данных.", None


def list_referral_withdrawal_requests(status: str | None = None, user_id: int | None = None) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = """
                SELECT r.*, u.username AS username
                FROM referral_withdrawal_requests r
                LEFT JOIN users u ON u.telegram_id = r.user_id
            """
            conditions: list[str] = []
            params: list = []
            if status:
                conditions.append("r.status = ?")
                params.append(status)
            if user_id is not None:
                conditions.append("r.user_id = ?")
                params.append(int(user_id))
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY r.created_at DESC"
            cur.execute(query, tuple(params))
            return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to list referral withdrawal requests: {e}")
        return []


def get_referral_withdrawal_request(request_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT r.*, u.username AS username
                FROM referral_withdrawal_requests r
                LEFT JOIN users u ON u.telegram_id = r.user_id
                WHERE r.id = ?
                """,
                (int(request_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral withdrawal request {request_id}: {e}")
        return None


def update_referral_withdrawal_request_status(request_id: int, new_status: str, *, reject_reason: str | None = None) -> tuple[bool, str, dict | None]:
    """Меняет статус заявки на вывод.

    - 'paid': сумма уже была списана с referral_balance при создании заявки; дополнительно
      списывается та же сумма из общего дохода бота — созданием отрицательной "технической"
      транзакции (status='paid', payment_method='referral_payout'), чтобы доходы/аналитика
      (которые считаются как SUM(amount_rub) по успешным транзакциям) автоматически уменьшились
      без рассинхронизации данных.
    - 'rejected': сумма возвращается обратно на referral_balance пользователя.
    """
    new_status = (new_status or "").strip().lower()
    if new_status not in REFERRAL_WITHDRAWAL_STATUSES:
        return False, "Некорректный статус.", None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT * FROM referral_withdrawal_requests WHERE id = ?", (int(request_id),))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False, "Заявка не найдена.", None
            cols = [d[0] for d in cursor.description]
            req = dict(zip(cols, row))
            current_status = req.get("status")

            if current_status in ("paid", "rejected"):
                conn.rollback()
                return False, f"Заявка уже в финальном статусе «{current_status}».", None

            if new_status == "rejected":
                cursor.execute(
                    "UPDATE users SET referral_balance = COALESCE(referral_balance, 0) + ? WHERE telegram_id = ?",
                    (float(req["amount"]), int(req["user_id"])),
                )
                cursor.execute(
                    "UPDATE referral_withdrawal_requests SET status = 'rejected', reject_reason = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (reject_reason, int(request_id)),
                )
            elif new_status == "paid":
                username = None
                try:
                    cursor.execute("SELECT username FROM users WHERE telegram_id = ?", (int(req["user_id"]),))
                    u = cursor.fetchone()
                    username = u[0] if u else None
                except Exception:
                    username = None
                meta = json.dumps({
                    "action": "referral_payout",
                    "withdrawal_request_id": int(request_id),
                    "method_type": req.get("method_type"),
                    "bank_name": req.get("bank_name"),
                    "requisite_value": req.get("requisite_value"),
                })
                cursor.execute(
                    """
                    INSERT INTO transactions (username, payment_id, user_id, status, amount_rub, payment_method, metadata)
                    VALUES (?, ?, ?, 'paid', ?, 'referral_payout', ?)
                    """,
                    (username, f"refpayout:{request_id}", int(req["user_id"]), -float(req["amount"]), meta),
                )
                cursor.execute(
                    "UPDATE referral_withdrawal_requests SET status = 'paid', processed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(request_id),),
                )
            else:
                cursor.execute(
                    "UPDATE referral_withdrawal_requests SET status = ? WHERE id = ?",
                    (new_status, int(request_id)),
                )

            conn.commit()

        updated = get_referral_withdrawal_request(request_id)
        return True, "Статус заявки обновлён.", updated
    except sqlite3.Error as e:
        logging.error(f"Failed to update referral withdrawal request {request_id}: {e}")
        return False, "Ошибка базы данных.", None


def get_referral_withdrawable_stats() -> dict:
    """Сводка по заявкам на вывод (для админ-панели): счётчики по статусам и суммы."""
    out = {"new": 0, "processing": 0, "paid": 0, "rejected": 0, "new_amount": 0.0, "processing_amount": 0.0, "paid_amount": 0.0}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status, COUNT(*), COALESCE(SUM(amount),0) FROM referral_withdrawal_requests GROUP BY status")
            for status, cnt, amt in cur.fetchall() or []:
                if status in out or f"{status}_amount" in out:
                    out[status] = int(cnt or 0)
                    out[f"{status}_amount"] = float(amt or 0.0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral withdrawable stats: {e}")
    return out


def get_referral_count(user_id: int) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral count for user {user_id}: {e}")
        return 0

def get_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            user_data = cursor.fetchone()
            return dict(user_data) if user_data else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get user {telegram_id}: {e}")
        return None


def get_user_by_username(username: str):
    """Возвращает пользователя по username (без @), регистр не важен."""
    try:
        uname = (username or "").lstrip("@").strip()
        if not uname:
            return None
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?) LIMIT 1", (uname,))
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("DB: get_user_by_username failed: %s", e)
        return None

def set_terms_agreed(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET agreed_to_terms = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"Пользователь {telegram_id} согласился с условиями.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set terms agreed for user {telegram_id}: {e}")

def is_subscription_expiry_notifications_enabled(telegram_id: int) -> bool:
    """Проверить, включены ли уведомления об истечении срока ключа."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT subscription_expiry_notifications_enabled FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return True  # По умолчанию включены
            return bool(row[0])
    except sqlite3.Error as e:
        logging.error(f"Failed to check notification status for user {telegram_id}: {e}")
        return True  # По умолчанию включены при ошибке

def toggle_subscription_expiry_notifications(telegram_id: int) -> bool:
    """Переключить статус уведомлений об истечении срока. Возвращает новое состояние."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Получаем текущее состояние
            cursor.execute(
                "SELECT subscription_expiry_notifications_enabled FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = cursor.fetchone()
            current_state = row[0] if row else 1
            new_state = 1 - current_state  # Переключаем
            
            # Обновляем
            cursor.execute(
                "UPDATE users SET subscription_expiry_notifications_enabled = ? WHERE telegram_id = ?",
                (new_state, telegram_id)
            )
            conn.commit()
            logging.info(f"Пользователь {telegram_id}: уведомления об истечении ключей {'включены' if new_state else 'отключены'}")
            return bool(new_state)
    except sqlite3.Error as e:
        logging.error(f"Failed to toggle notification status for user {telegram_id}: {e}")
        return True

def update_user_stats(telegram_id: int, amount_spent: float, months_purchased: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET total_spent = total_spent + ?, total_months = total_months + ? WHERE telegram_id = ?", (amount_spent, months_purchased, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update user stats for {telegram_id}: {e}")

def get_user_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get user count: {e}")
        return 0

def get_total_keys_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vpn_keys")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total keys count: {e}")
        return 0

def get_total_spent_sum() -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_rub), 0.0)
                FROM transactions
                WHERE LOWER(COALESCE(status, '')) IN ('paid', 'completed', 'success')
                  AND LOWER(COALESCE(payment_method, '')) <> 'balance'
                """
            )
            val = cursor.fetchone()
            return (val[0] if val else 0.0) or 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total spent sum: {e}")
        return 0.0

def create_pending_transaction(payment_id: str, user_id: int, amount_rub: float, metadata: dict) -> int:
    """Create a pending transaction row in `transactions`.

    Used for TON Connect flows.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return 0
    try:
        with sqlite3.connect(DB_FILE, timeout=5.0) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass

            cursor.execute(
                "INSERT OR IGNORE INTO transactions (payment_id, user_id, status, amount_rub, metadata) VALUES (?, ?, ?, ?, ?)",
                (pid, int(user_id), 'pending', float(amount_rub), json.dumps(metadata or {}, ensure_ascii=False))
            )
            conn.commit()
            return cursor.lastrowid or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to create pending transaction: {e}")
        return 0


def find_and_complete_ton_transaction(payment_id: str, amount_ton: float) -> dict | None:
    """Atomically completes a TON transaction.

    - validates transaction exists and is still pending
    - enforces amount check against metadata (expected_amount_ton/ton_amount/amount_ton) when present
    - updates using `WHERE ... AND status='pending'` to ensure idempotency
    """
    pid = (payment_id or "").strip()
    if not pid:
        return None

    try:
        with sqlite3.connect(DB_FILE, timeout=5.0, isolation_level=None) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass

            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT metadata FROM transactions WHERE payment_id = ? AND status = 'pending'", (pid,))
            row = cursor.fetchone()
            if not row:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.warning(f"TON Webhook: payment_id unknown or already processed: {pid}")
                return None

            raw_meta = row['metadata'] if isinstance(row, dict) or hasattr(row, '__getitem__') else None
            try:
                meta = json.loads(raw_meta or "{}")
            except Exception:
                meta = {}

            expected = meta.get('expected_amount_ton')
            if expected is None:
                expected = meta.get('ton_amount')
            if expected is None:
                expected = meta.get('amount_ton')

            exp_val = None
            try:
                if expected is not None:
                    exp_val = float(expected)
            except Exception:
                exp_val = None

            try:
                amt_val = float(amount_ton)
            except Exception:
                amt_val = None

            if exp_val is not None:
                if amt_val is None:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    logger.warning(f"TON Webhook: missing amount for payment_id={pid}; expected={exp_val}")
                    return None
                tol = max(0.001, exp_val * 0.01)
                if abs(amt_val - exp_val) > tol:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    logger.warning(f"TON Webhook: amount mismatch for payment_id={pid}; got={amt_val}, expected={exp_val}, tol={tol}")
                    return None

            cursor.execute(
                "UPDATE transactions SET status = 'paid', amount_currency = ?, currency_name = 'TON', payment_method = 'TON' WHERE payment_id = ? AND status = 'pending'",
                (amt_val if amt_val is not None else amount_ton, pid)
            )
            if cursor.rowcount != 1:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

            conn.commit()
            meta.setdefault('payment_id', pid)
            return meta

    except sqlite3.Error as e:
        logging.error(f"Failed to complete TON transaction {pid}: {e}")
        return None
_TX_ACTION_LABELS = {
    "new": "Новый ключ",
    "gift": "Подарок (новый ключ)",
    "extend": "Продление ключа",
    "top_up": "Пополнение баланса",
    "traffic_gb_topup": "Докупка трафика",
    "lte_gb_topup": "Докупка LTE-пула",
    "main_traffic_reset": "Сброс основного трафика",
}

def _describe_transaction_action(metadata: dict) -> dict:
    """Формирует человекочитаемое описание действия транзакции по её metadata."""
    action = (metadata or {}).get("action")
    key_id = metadata.get("key_id") if isinstance(metadata, dict) else None
    try:
        key_id = int(key_id) if key_id not in (None, "", "None") else None
    except Exception:
        key_id = None
    label = _TX_ACTION_LABELS.get(action, "Оплата тарифа" if action is None else action)
    size_gb = metadata.get("size_gb") if isinstance(metadata, dict) else None
    # ID транзакции на стороне платёжного провайдера (если применимо и был сохранён).
    provider_transaction_id = None
    if isinstance(metadata, dict):
        provider_transaction_id = (
            metadata.get("platega_transaction_id")
            or metadata.get("cryptobot_invoice_id")
            or metadata.get("heleket_uuid")
            or metadata.get("yookassa_payment_id")
        )
    return {
        "action": action,
        "action_label": label,
        "key_id": key_id,
        "size_gb": size_gb,
        "provider_transaction_id": provider_transaction_id,
    }

def _find_nearest_key_id(cursor, user_id: int | None, host_name: str | None, created_date, window_minutes: int = 20) -> int | None:
    """Best-effort подбор ключа для старых транзакций, в metadata которых ещё не сохранялся key_id.
    Ищет ключ того же пользователя (и хоста, если известен), созданный ближе всего по времени
    к моменту транзакции (в пределах window_minutes)."""
    if not user_id or not created_date:
        return None
    try:
        if host_name:
            cursor.execute(
                """SELECT key_id, created_at FROM vpn_keys
                   WHERE user_id = ? AND host_name = ?
                   ORDER BY ABS(strftime('%s', created_at) - strftime('%s', ?)) ASC
                   LIMIT 1""",
                (int(user_id), host_name, str(created_date)),
            )
        else:
            cursor.execute(
                """SELECT key_id, created_at FROM vpn_keys
                   WHERE user_id = ?
                   ORDER BY ABS(strftime('%s', created_at) - strftime('%s', ?)) ASC
                   LIMIT 1""",
                (int(user_id), str(created_date)),
            )
        row = cursor.fetchone()
        if not row:
            return None
        key_id_val, created_at_val = row[0], row[1]
        try:
            diff = abs((datetime.fromisoformat(str(created_at_val).replace('Z', '')) - datetime.fromisoformat(str(created_date).replace('Z', ''))).total_seconds())
            if diff > window_minutes * 60:
                return None
        except Exception:
            pass
        return int(key_id_val) if key_id_val is not None else None
    except Exception:
        return None

def log_transaction(username: str, transaction_id: str | None, payment_id: str | None, user_id: int, status: str, amount_rub: float, amount_currency: float | None, currency_name: str | None, payment_method: str, metadata: str) -> bool:
    """Записывает транзакцию в таблицу `transactions`.

    ВАЖНО: используем устойчивое к блокировкам подключение (WAL + busy_timeout + retry),
    как и остальные высококонкурентные write-пути (см. _connect_pending_db/_retry_sqlite).
    Раньше здесь использовалось обычное sqlite3.connect() без retry: под конкурентной
    нагрузкой (несколько платежей одновременно) запись могла молча "потеряться" из-за
    'database is locked', при этом баланс пользователя уже был обновлён другой функцией —
    из-за этого доход в аналитике не менялся, хотя баланс пополнялся.

    Не бросает исключение наружу (некоторые вызовы в handlers.py не обёрнуты в try/except
    и не должны прерывать выдачу уже оплаченного ключа) — вместо этого возвращает False
    и подробно логирует ошибку, чтобы проблема не оставалась незамеченной.
    """
    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO transactions
                   (username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, created_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, datetime.now())
            )
            return True

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to log transaction for user {user_id}: {e}", exc_info=True)
        return False

def get_paginated_transactions(page: int = 1, per_page: int = 15) -> tuple[list[dict], int]:

    offset = (page - 1) * per_page
    transactions = []
    total = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total = cursor.fetchone()[0]

            query = "SELECT * FROM transactions ORDER BY created_date DESC LIMIT ? OFFSET ?"
            cursor.execute(query, (per_page, offset))
            
            for row in cursor.fetchall():
                transaction_dict = dict(row)
                
                metadata_str = transaction_dict.get('metadata')
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        transaction_dict['host_name'] = metadata.get('host_name', 'N/A')
                        transaction_dict['plan_name'] = metadata.get('plan_name', 'N/A')
                        transaction_dict.update(_describe_transaction_action(metadata))
                    except json.JSONDecodeError:
                        transaction_dict['host_name'] = 'Error'
                        transaction_dict['plan_name'] = 'Error'
                else:
                    transaction_dict['host_name'] = 'N/A'
                    transaction_dict['plan_name'] = 'N/A'
                    transaction_dict.update(_describe_transaction_action({}))

                # Legacy-транзакции (до появления action/key_id в metadata): пытаемся подобрать
                # ключ пользователя, максимально близкий по времени создания к транзакции.
                if not transaction_dict.get('key_id') and transaction_dict.get('action') in (None, 'new', 'extend', 'gift'):
                    host_hint = transaction_dict.get('host_name')
                    host_hint = host_hint if host_hint not in ('N/A', 'Error', None) else None
                    guessed = _find_nearest_key_id(cursor, transaction_dict.get('user_id'), host_hint, transaction_dict.get('created_date'))
                    if guessed:
                        transaction_dict['key_id'] = guessed
                        transaction_dict['key_id_guessed'] = True

                transactions.append(transaction_dict)

    except sqlite3.Error as e:
        logging.error(f"Failed to get paginated transactions: {e}")

    return transactions, total

def get_transactions_paginated(
    page: int = 1,
    per_page: int = 10,
    user_id: int | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> tuple[list[dict], int]:
    """Универсальная выборка транзакций с фильтром по пользователю, поиском и сортировкой."""
    try:
        page_i = max(1, int(page))
    except Exception:
        page_i = 1
    try:
        per_i = max(1, int(per_page))
    except Exception:
        per_i = 10
    offset = (page_i - 1) * per_i

    conditions: list = []
    params: list = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(int(user_id))
    search_q = (search or "").strip()
    if search_q:
        like = f"%{search_q}%"
        conditions.append(
            "(CAST(user_id AS TEXT) LIKE ? OR CAST(transaction_id AS TEXT) LIKE ? OR username LIKE ? OR payment_id LIKE ? OR "
            "payment_method LIKE ? OR status LIKE ? OR metadata LIKE ?)"
        )
        params.extend([like, like, like, like, like, like, like])
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_columns = {
        "date": "created_date",
        "amount": "amount_rub",
        "payment_method": "payment_method",
        "status": "status",
    }
    sort_col = sort_columns.get((sort_by or "").strip(), sort_columns["date"])
    sort_direction = "ASC" if (sort_dir or "").strip().lower() == "asc" else "DESC"
    order_sql = f"ORDER BY {sort_col} {sort_direction}"
    if sort_col != sort_columns["date"]:
        order_sql += ", created_date DESC"

    transactions: list = []
    total = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM transactions{where_sql}", params)
            total = cursor.fetchone()[0] or 0

            cursor.execute(
                f"""
                SELECT * FROM transactions
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                (*params, per_i, offset),
            )

            for row in cursor.fetchall():
                transaction_dict = dict(row)
                metadata_str = transaction_dict.get('metadata')
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        transaction_dict['host_name'] = metadata.get('host_name', 'N/A')
                        transaction_dict['plan_name'] = metadata.get('plan_name', 'N/A')
                        transaction_dict.update(_describe_transaction_action(metadata))
                    except json.JSONDecodeError:
                        transaction_dict['host_name'] = 'Error'
                        transaction_dict['plan_name'] = 'Error'
                else:
                    transaction_dict['host_name'] = 'N/A'
                    transaction_dict['plan_name'] = 'N/A'
                    transaction_dict.update(_describe_transaction_action({}))

                # Legacy-транзакции (до появления action/key_id в metadata): пытаемся подобрать
                # ключ пользователя, максимально близкий по времени создания к транзакции.
                if not transaction_dict.get('key_id') and transaction_dict.get('action') in (None, 'new', 'extend', 'gift'):
                    host_hint = transaction_dict.get('host_name')
                    host_hint = host_hint if host_hint not in ('N/A', 'Error', None) else None
                    guessed = _find_nearest_key_id(cursor, transaction_dict.get('user_id'), host_hint, transaction_dict.get('created_date'))
                    if guessed:
                        transaction_dict['key_id'] = guessed
                        transaction_dict['key_id_guessed'] = True

                transactions.append(transaction_dict)
    except sqlite3.Error as e:
        logging.error(f"Failed to get filtered transactions: {e}")

    return transactions, int(total)

def set_trial_used(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET trial_used = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
            logging.info(f"Trial period marked as used for user {telegram_id}.")
    except sqlite3.Error as e:
        logging.error(f"Failed to set trial used for user {telegram_id}: {e}")

def add_new_key(
    user_id: int,
    host_name: str | None,
    remnawave_user_uuid: str,
    key_email: str,
    expiry_timestamp_ms: int,
    *,
    squad_uuid: str | None = None,
    short_uuid: str | None = None,
    subscription_url: str | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    description: str | None = None,
    tag: str | None = None,
) -> int | None:
    host_name_norm = normalize_host_name(host_name) if host_name else None
    email_normalized = _normalize_email(key_email) or key_email.strip()
    expire_str = _to_datetime_str(expiry_timestamp_ms) or _now_str()
    created_str = _now_str()
    strategy_value = traffic_limit_strategy or "NO_RESET"
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO vpn_keys (
                    user_id,
                    host_name,
                    squad_uuid,
                    remnawave_user_uuid,
                    short_uuid,
                    email,
                    key_email,
                    subscription_url,
                    expire_at,
                    created_at,
                    updated_at,
                    traffic_limit_bytes,
                    traffic_limit_strategy,
                    tag,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    host_name_norm,
                    squad_uuid,
                    remnawave_user_uuid,
                    short_uuid,
                    email_normalized,
                    email_normalized,
                    subscription_url,
                    expire_str,
                    created_str,
                    created_str,
                    traffic_limit_bytes,
                    strategy_value,
                    tag,
                    description,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        logging.error(
            "Failed to add new key for user %s due to integrity error: %s",
            user_id,
            e,
        )
        return None
    except sqlite3.Error as e:
        logging.error("Failed to add new key for user %s: %s", user_id, e)
        return None


def _apply_key_updates(key_id: int, updates: dict[str, Any]) -> bool:
    if not updates:
        return False
    updates = dict(updates)
    updates["updated_at"] = _now_str()
    columns = ", ".join(f"{column} = ?" for column in updates)
    values = list(updates.values())
    values.append(key_id)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE vpn_keys SET {columns} WHERE key_id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to update key %s: %s", key_id, e)
        return False


def update_key_fields(
    key_id: int,
    *,
    user_id: int | None = None,
    host_name: str | None = None,
    squad_uuid: str | None = None,
    remnawave_user_uuid: str | None = None,
    short_uuid: str | None = None,
    email: str | None = None,
    subscription_url: str | None = None,
    expire_at_ms: int | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    tag: str | None = None,
    description: str | None = None,
    missing_from_server_at: Any = _UNSET,
    traffic_boost_bytes: int | None = None,
    next_traffic_reset_at: Any = _UNSET,
    remote_access_state: str | None = None,
) -> bool:
    updates: dict[str, Any] = {}
    if user_id is not None:
        updates["user_id"] = user_id
    if host_name is not None:
        updates["host_name"] = normalize_host_name(host_name)
    if squad_uuid is not None:
        updates["squad_uuid"] = squad_uuid
    if remnawave_user_uuid is not None:
        updates["remnawave_user_uuid"] = remnawave_user_uuid
    if short_uuid is not None:
        updates["short_uuid"] = short_uuid
    if email is not None:
        normalized = _normalize_email(email) or email.strip()
        updates["email"] = normalized
        updates["key_email"] = normalized
    if subscription_url is not None:
        updates["subscription_url"] = subscription_url
    if expire_at_ms is not None:
        expire_str = _to_datetime_str(expire_at_ms) or _now_str()
        updates["expire_at"] = expire_str
    if traffic_limit_bytes is not None:
        updates["traffic_limit_bytes"] = traffic_limit_bytes
    if traffic_limit_strategy is not None:
        updates["traffic_limit_strategy"] = traffic_limit_strategy or "NO_RESET"
    if tag is not None:
        updates["tag"] = tag
    if description is not None:
        updates["description"] = description
    if missing_from_server_at is not _UNSET:
        updates["missing_from_server_at"] = missing_from_server_at
    if traffic_boost_bytes is not None:
        updates["traffic_boost_bytes"] = int(traffic_boost_bytes)
    if next_traffic_reset_at is not _UNSET:
        updates["next_traffic_reset_at"] = next_traffic_reset_at
    if remote_access_state is not None:
        updates["remote_access_state"] = remote_access_state
    return _apply_key_updates(key_id, updates)


def delete_key_by_email(email: str) -> bool:
    lookup = _normalize_email(email) or email.strip()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Как и в delete_key_by_id: удаляем связанный неактивированный подарок,
            # чтобы он пропал из списка так же, как исчезает обычный просроченный ключ.
            cursor.execute(
                "SELECT key_id FROM vpn_keys WHERE email = ? OR key_email = ?",
                (lookup, lookup),
            )
            key_ids = [row[0] for row in cursor.fetchall()]
            if key_ids:
                cursor.executemany(
                    "DELETE FROM user_gifts WHERE key_id = ? AND is_activated = 0",
                    [(kid,) for kid in key_ids],
                )
            cursor.execute(
                "DELETE FROM vpn_keys WHERE email = ? OR key_email = ?",
                (lookup, lookup),
            )
            affected = cursor.rowcount
            conn.commit()
            logger.debug("delete_key_by_email('%s') affected=%s", email, affected)
            return affected > 0
    except sqlite3.Error as e:
        logging.error("Failed to delete key '%s': %s", email, e)
        return False


def get_user_keys(user_id: int) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE user_id = ? ORDER BY datetime(created_at) DESC, key_id DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get keys for user %s: %s", user_id, e)
        return []


def get_key_by_id(key_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except sqlite3.Error as e:
        logging.error("Failed to get key by ID %s: %s", key_id, e)
        return None


def get_key_by_email(key_email: str) -> dict | None:
    lookup = _normalize_email(key_email) or key_email.strip()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE email = ? OR key_email = ?",
                (lookup, lookup),
            )
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except sqlite3.Error as e:
        logging.error("Failed to get key by email %s: %s", key_email, e)
        return None


def get_key_by_remnawave_uuid(remnawave_uuid: str) -> dict | None:
    if not remnawave_uuid:
        return None
    try:
        normalized_uuid = remnawave_uuid.strip()
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE remnawave_user_uuid = ? LIMIT 1",
                (normalized_uuid,),
            )
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except sqlite3.Error as e:
        logging.error("Failed to get key by remnawave uuid %s: %s", remnawave_uuid, e)
        return None


def update_key_info(key_id: int, new_remnawave_uuid: str, new_expiry_ms: int, **kwargs) -> bool:
    return update_key_fields(
        key_id,
        remnawave_user_uuid=new_remnawave_uuid,
        expire_at_ms=new_expiry_ms,
        **kwargs,
    )


def update_key_host_and_info(
    key_id: int,
    new_host_name: str,
    new_remnawave_uuid: str,
    new_expiry_ms: int,
    **kwargs,
) -> bool:
    return update_key_fields(
        key_id,
        host_name=new_host_name,
        remnawave_user_uuid=new_remnawave_uuid,
        expire_at_ms=new_expiry_ms,
        **kwargs,
    )


def get_next_key_number(user_id: int) -> int:
    return len(get_user_keys(user_id)) + 1


def get_keys_for_host(host_name: str) -> list[dict]:
    try:
        host_name_normalized = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE TRIM(host_name) = TRIM(?)",
                (host_name_normalized,),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get keys for host '%s': %s", host_name, e)
        return []


def set_key_auto_renew(key_id: int, enabled: bool) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET auto_renew = ? WHERE key_id = ?", (1 if enabled else 0, int(key_id)))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to set auto_renew for key %s: %s", key_id, e)
        return False


def set_all_keys_auto_renew_for_user(user_id: int, enabled: bool) -> int:
    """Mass-update auto_renew for all keys of a user. Returns count of updated rows."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET auto_renew = ? WHERE user_id = ?", (1 if enabled else 0, int(user_id)))
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error("Failed to set auto_renew for all keys of user %s: %s", user_id, e)
        return 0


def get_keys_for_auto_renew(hours_before: int = 24) -> list[dict]:
    """Return keys with auto_renew=1 expiring within the next `hours_before` hours."""
    now = datetime.now()
    deadline = now + timedelta(hours=int(hours_before))
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM vpn_keys
                WHERE auto_renew = 1
                  AND expire_at IS NOT NULL
                  AND expire_at > ?
                  AND expire_at <= ?
                ORDER BY expire_at ASC
                """,
                (now.strftime("%Y-%m-%d %H:%M:%S"), deadline.strftime("%Y-%m-%d %H:%M:%S")),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get keys for auto-renewal: %s", e)
        return []


def _key_matches_search(data: dict, needle_lower: str) -> bool:
    """Регистронезависимая (в т.ч. кириллица) проверка вхождения подстроки
    в key_email, email или user_key_name. SQL LIKE/LOWER() в SQLite сворачивают
    регистр только для ASCII, поэтому сравнение делается на стороне Python."""
    for field in ("key_email", "email", "user_key_name"):
        value = data.get(field)
        if value and needle_lower in str(value).lower():
            return True
    return False


def search_user_keys_by_email(user_id: int, search_query: str) -> list[dict]:
    """Поиск ключей пользователя по key_email, email или user_key_name."""
    if not search_query or not search_query.strip():
        return []

    try:
        needle_lower = search_query.strip().lower()
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE user_id = ? ORDER BY datetime(created_at) DESC, key_id DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            normalized = (_normalize_key_row(row) for row in rows)
            return [data for data in normalized if _key_matches_search(data, needle_lower)]
    except sqlite3.Error as e:
        logging.error("Failed to search user keys by email for user %s: %s", user_id, e)
        return []


def search_all_keys_by_email(search_query: str) -> list[dict]:
    """Поиск всех ключей (администраторам) по key_email, email или user_key_name."""
    if not search_query or not search_query.strip():
        return []

    try:
        needle_lower = search_query.strip().lower()
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys ORDER BY datetime(created_at) DESC, key_id DESC",
            )
            rows = cursor.fetchall()
            normalized = (_normalize_key_row(row) for row in rows)
            return [data for data in normalized if _key_matches_search(data, needle_lower)]
    except sqlite3.Error as e:
        logging.error("Failed to search all keys by email: %s", e)
        return []


def get_all_vpn_users() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM vpn_keys")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get all vpn users: %s", e)
        return []


def update_key_status_from_server(key_email: str, client_data) -> bool:
    try:
        normalized_email = _normalize_email(key_email) or key_email.strip()
        existing = get_key_by_email(normalized_email)
        if client_data:
            if isinstance(client_data, dict):
                remote_uuid = client_data.get('uuid') or client_data.get('id')
                expire_value = client_data.get('expireAt') or client_data.get('expiryDate')
                subscription_url = client_data.get('subscriptionUrl') or client_data.get('subscription_url')
                expiry_ms = None
                if expire_value:
                    try:
                        remote_dt = datetime.fromisoformat(str(expire_value).replace('Z', '+00:00'))
                        expiry_ms = int(remote_dt.timestamp() * 1000)
                    except Exception:
                        expiry_ms = None
            else:
                remote_uuid = getattr(client_data, 'id', None) or getattr(client_data, 'uuid', None)
                expiry_ms = getattr(client_data, 'expiry_time', None)
                subscription_url = getattr(client_data, 'subscription_url', None)
            if not existing:
                return False
            return update_key_fields(
                existing['key_id'],
                remnawave_user_uuid=remote_uuid,
                expire_at_ms=expiry_ms,
                subscription_url=subscription_url,
                missing_from_server_at=None,
            )
        if existing:
            # Не удаляем ключ сразу, т.к. временные сбои Remnawave/пагинация
            # могут приводить к ложному отсутствию ключа в списке пользователей.
            # Вместо этого помечаем время, когда ключ последний раз не был найден на сервере.
            return update_key_fields(
                existing["key_id"],
                missing_from_server_at=_now_str(),
            )
        return True
    except sqlite3.Error as e:
        logging.error("Failed to update key status for %s: %s", key_email, e)
        return False


def get_daily_stats_for_charts(days: int = 30) -> dict:
    stats = {'users': {}, 'keys': {}}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date(registration_date) AS day, COUNT(*)
                FROM users
                WHERE registration_date >= date('now', ?)
                GROUP BY day
                ORDER BY day
                """,
                (f'-{days} days',),
            )
            for day, count in cursor.fetchall():
                stats['users'][day] = count

            cursor.execute(
                """
                SELECT date(COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)) AS day, COUNT(*)
                FROM vpn_keys
                WHERE COALESCE(created_at, updated_at, CURRENT_TIMESTAMP) >= date('now', ?)
                GROUP BY day
                ORDER BY day
                """,
                (f'-{days} days',),
            )
            for day, count in cursor.fetchall():
                stats['keys'][day] = count
    except sqlite3.Error as e:
        logging.error("Failed to get daily stats for charts: %s", e)
    return stats


def get_recent_transactions(limit: int = 15) -> list[dict]:
    transactions: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    k.key_id,
                    k.host_name,
                    k.created_at,
                    u.telegram_id,
                    u.username
                FROM vpn_keys k
                JOIN users u ON k.user_id = u.telegram_id
                ORDER BY datetime(k.created_at) DESC, k.key_id DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cursor.fetchall():
                transactions.append(
                    {
                        "key_id": row["key_id"],
                        "host_name": row["host_name"],
                        "created_at": row["created_at"],
                        "telegram_id": row["telegram_id"],
                        "username": row["username"],
                    }
                )
    except sqlite3.Error as e:
        logging.error("Failed to get recent transactions: %s", e)
    return transactions


def get_all_users() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY registration_date DESC")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get all users: {e}")
        return []

def get_users_paginated(
    page: int = 1,
    per_page: int = 30,
    q: str | None = None,
    *,
    sort: str | None = None,
) -> tuple[list[dict], int]:
    """Вернуть пользователей постранично и общее количество (с учётом фильтра).

    Фильтр q ищет по username (LIKE) и по текстовому представлению telegram_id.
    """
    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 30))
    offset = (page - 1) * per_page

    sort_key = (sort or "").strip().lower()
    order_by = "u.registration_date DESC"
    if sort_key in ("balance", "balance_desc"):
        order_by = "COALESCE(u.balance, 0) DESC, u.registration_date DESC"
    elif sort_key in ("balance_asc",):
        order_by = "COALESCE(u.balance, 0) ASC, u.registration_date DESC"
    elif sort_key in ("referral_balance", "referral_balance_desc"):
        order_by = "COALESCE(u.referral_balance, 0) DESC, u.registration_date DESC"
    elif sort_key in ("referral_balance_asc",):
        order_by = "COALESCE(u.referral_balance, 0) ASC, u.registration_date DESC"
    elif sort_key in ("active_keys", "active_keys_desc"):
        order_by = "active_keys_count DESC, u.registration_date DESC"
    elif sort_key in ("active_keys_asc",):
        order_by = "active_keys_count ASC, u.registration_date DESC"
    elif sort_key in ("total_spent", "total_spent_desc", "spent", "spent_desc"):
        order_by = "COALESCE(u.total_spent, 0) DESC, u.registration_date DESC"
    elif sort_key in ("total_spent_asc", "spent_asc"):
        order_by = "COALESCE(u.total_spent, 0) ASC, u.registration_date DESC"
    elif sort_key in ("registration_date", "registration_date_desc", "reg_desc"):
        order_by = "u.registration_date DESC"
    elif sort_key in ("registration_date_asc", "reg_asc"):
        order_by = "u.registration_date ASC"
    elif sort_key in ("telegram_id", "telegram_id_desc", "id_desc"):
        order_by = "u.telegram_id DESC"
    elif sort_key in ("telegram_id_asc", "id_asc"):
        order_by = "u.telegram_id ASC"
    elif sort_key in ("username", "username_desc"):
        order_by = "LOWER(COALESCE(u.username, '')) DESC, u.registration_date DESC"
    elif sort_key in ("username_asc",):
        order_by = "LOWER(COALESCE(u.username, '')) ASC, u.registration_date DESC"
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if q:
                q_like = f"%{q.strip()}%"

                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM users
                    WHERE (username LIKE ?)
                       OR (CAST(telegram_id AS TEXT) LIKE ?)
                    """,
                    (q_like, q_like),
                )
                total = cursor.fetchone()[0] or 0

                cursor.execute(
                    f"""
                    SELECT
                        u.*,
                        COUNT(k.key_id) AS keys_count,
                        COALESCE(SUM(
                            CASE
                                WHEN k.key_id IS NOT NULL
                                 AND k.missing_from_server_at IS NULL
                                 AND k.expire_at IS NOT NULL
                                 AND datetime(k.expire_at) > CURRENT_TIMESTAMP
                                THEN 1 ELSE 0
                            END
                        ), 0) AS active_keys_count
                    FROM users u
                    LEFT JOIN vpn_keys k ON k.user_id = u.telegram_id
                    WHERE (u.username LIKE ?)
                       OR (CAST(u.telegram_id AS TEXT) LIKE ?)
                    GROUP BY u.telegram_id
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    (q_like, q_like, per_page, offset),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM users")
                total = cursor.fetchone()[0] or 0
                cursor.execute(
                    f"""
                    SELECT
                        u.*,
                        COUNT(k.key_id) AS keys_count,
                        COALESCE(SUM(
                            CASE
                                WHEN k.key_id IS NOT NULL
                                 AND k.missing_from_server_at IS NULL
                                 AND k.expire_at IS NOT NULL
                                 AND datetime(k.expire_at) > CURRENT_TIMESTAMP
                                THEN 1 ELSE 0
                            END
                        ), 0) AS active_keys_count
                    FROM users u
                    LEFT JOIN vpn_keys k ON k.user_id = u.telegram_id
                    GROUP BY u.telegram_id
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                    """,
                    (per_page, offset),
                )
            users = [dict(row) for row in cursor.fetchall()]
            return users, total
    except sqlite3.Error as e:
        logging.error(f"Failed to get users paginated: {e}")
        return [], 0

def get_keys_counts_for_users(user_ids: list[int]) -> dict[int, int]:
    """Вернуть словарь {user_id: keys_count} по списку пользователей."""
    result: dict[int, int] = {}
    if not user_ids:
        return result

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(user_ids))
            query = f"SELECT user_id, COUNT(*) AS cnt FROM vpn_keys WHERE user_id IN ({placeholders}) GROUP BY user_id"
            cursor.execute(query, tuple(int(x) for x in user_ids))
            for row in cursor.fetchall() or []:
                uid = int(row[0])
                cnt = int(row[1] or 0)
                result[uid] = cnt
    except sqlite3.Error as e:
        logging.error("Failed to get keys counts for users: %s", e)
    return result

def ban_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 1 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to ban user {telegram_id}: {e}")

def unban_user(telegram_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_banned = 0 WHERE telegram_id = ?", (telegram_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to unban user {telegram_id}: {e}")


# ── Недоступность пользователя в Telegram (заблокировал бота / деактивировал аккаунт) ──
#
# Позволяет автоматически исключать таких пользователей из будущих рассылок
# (см. shop_bot.modules.telegram_reachability, вызывается из всех мест массовой
# отправки сообщений) и вести статистику по реальному количеству подписчиков.

UNREACHABLE_REASON_BLOCKED = "blocked"
UNREACHABLE_REASON_DEACTIVATED = "deactivated"

def mark_user_unreachable(telegram_id: int, reason: str) -> bool:
    """Отметить пользователя как недоступного в Telegram.

    `reason` — 'blocked' (заблокировал бота) или 'deactivated' (аккаунт удалён/деактивирован).
    Пользователь будет исключён из последующих рассылок, пока не напишет боту снова
    (см. mark_user_reachable — вызывается автоматически при любом входящем сообщении/callback).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET is_unreachable = 1,
                    unreachable_reason = ?,
                    unreachable_since = COALESCE(unreachable_since, CURRENT_TIMESTAMP)
                WHERE telegram_id = ?
                """,
                (reason, int(telegram_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to mark user {telegram_id} unreachable: {e}")
        return False

def mark_user_reachable(telegram_id: int) -> bool:
    """Снять отметку недоступности — пользователь снова взаимодействовал с ботом
    (значит, разблокировал его или его аккаунт снова активен)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET is_unreachable = 0, unreachable_reason = NULL, unreachable_since = NULL
                WHERE telegram_id = ? AND is_unreachable = 1
                """,
                (int(telegram_id),),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to mark user {telegram_id} reachable: {e}")
        return False

def get_reachability_stats() -> dict:
    """Статистика по доступности пользователей в Telegram: сколько всего
    пользователей, сколько реально доступны (не забанены и не недоступны),
    сколько заблокировали бота, сколько деактивировали аккаунт."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN is_banned = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_unreachable = 1 AND unreachable_reason = 'blocked' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_unreachable = 1 AND unreachable_reason = 'deactivated' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN (is_unreachable IS NULL OR is_unreachable = 0) AND is_banned = 0 THEN 1 ELSE 0 END)
                FROM users
                """
            )
            row = cursor.fetchone()
            total, banned, blocked_bot, deactivated, reachable = row if row else (0, 0, 0, 0, 0)
            return {
                "total": int(total or 0),
                "banned": int(banned or 0),
                "blocked_bot": int(blocked_bot or 0),
                "deactivated": int(deactivated or 0),
                "reachable": int(reachable or 0),
            }
    except sqlite3.Error as e:
        logging.error(f"Failed to get reachability stats: {e}")
        return {"total": 0, "banned": 0, "blocked_bot": 0, "deactivated": 0, "reachable": 0}

def delete_user_keys(user_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM user_gifts
                WHERE is_activated = 0 AND key_id IN (SELECT key_id FROM vpn_keys WHERE user_id = ?)
                """,
                (user_id,),
            )
            cursor.execute("DELETE FROM vpn_keys WHERE user_id = ?", (user_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to delete keys for user {user_id}: {e}")


def delete_user_completely(user_id: int) -> bool:
    """Полностью удалить пользователя и все связанные с ним данные.

    :param user_id: Telegram ID пользователя (users.telegram_id, а также user_id в связанных таблицах).
    :return: True при успешном удалении, False при ошибке.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Сначала удалить сообщения поддержки по тикетам пользователя
            cursor.execute(
                """
                DELETE FROM support_messages
                WHERE ticket_id IN (
                    SELECT ticket_id FROM support_tickets WHERE user_id = ?
                )
                """,
                (user_id,),
            )

            # Удалить тикеты поддержки
            cursor.execute(
                "DELETE FROM support_tickets WHERE user_id = ?",
                (user_id,),
            )

            # Удалить неактивированные подарки, привязанные к ключам пользователя
            cursor.execute(
                """
                DELETE FROM user_gifts
                WHERE is_activated = 0 AND key_id IN (SELECT key_id FROM vpn_keys WHERE user_id = ?)
                """,
                (user_id,),
            )

            # Удалить мониторинг использования ключей (иначе останутся "осиротевшие"
            # записи, ссылающиеся на уже удалённые key_id ниже)
            cursor.execute(
                "DELETE FROM key_usage_monitor WHERE key_id IN (SELECT key_id FROM vpn_keys WHERE user_id = ?)",
                (user_id,),
            )

            # Удалить VPN-ключи пользователя
            cursor.execute(
                "DELETE FROM vpn_keys WHERE user_id = ?",
                (user_id,),
            )

            # Удалить записи о платёжных заявках и транзакциях
            cursor.execute(
                "DELETE FROM pending_transactions WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM transactions WHERE user_id = ?",
                (user_id,),
            )

            # Удалить историю по подарочным токенам и промокодам
            cursor.execute(
                "DELETE FROM gift_token_claims WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM promo_code_usages WHERE user_id = ?",
                (user_id,),
            )

            # Удалить реферальные методы получения и заявки на вывод
            cursor.execute(
                "DELETE FROM referral_payout_methods WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM referral_withdrawal_requests WHERE user_id = ?",
                (user_id,),
            )

            # Удалить просроченные/неиспользованные заявки на вход через webapp
            cursor.execute(
                "DELETE FROM webapp_auth_requests WHERE user_id = ?",
                (user_id,),
            )

            # Удалить статус и историю прохождения капчи — иначе при повторной
            # регистрации того же telegram_id (после "удаления") has_passed_captcha()
            # найдёт старую запись и капча будет молча пропущена.
            cursor.execute(
                "DELETE FROM user_captcha_status WHERE user_id = ?",
                (user_id,),
            )
            cursor.execute(
                "DELETE FROM captcha_challenges WHERE user_id = ?",
                (user_id,),
            )

            # Обнулить ссылки на этого пользователя как реферала
            cursor.execute(
                "UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                (user_id,),
            )

            # Удалить самого пользователя (по telegram_id)
            cursor.execute(
                "DELETE FROM users WHERE telegram_id = ?",
                (user_id,),
            )

            conn.commit()
            logger.info("User %s fully deleted with all related data", user_id)
            return True
    except sqlite3.Error as e:
        logger.error("Failed to delete user %s completely: %s", user_id, e)
        return False

def create_support_ticket(user_id: int, subject: str | None = None) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    "SELECT ticket_id FROM support_tickets WHERE user_id = ? AND status = 'open' ORDER BY updated_at DESC LIMIT 1",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return int(row[0])
            except Exception:
                pass

            cursor.execute(
                "INSERT INTO support_tickets (user_id, subject) VALUES (?, ?)",
                (user_id, subject)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to create support ticket for user {user_id}: {e}")
        return None

def get_or_create_open_ticket(user_id: int, subject: str | None = None) -> tuple[int | None, bool]:
    """Возвращает ID открытого тикета пользователя и флаг, создан ли новый.
    Если открытого тикета нет — создаёт новый и возвращает (id, True).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT ticket_id FROM support_tickets WHERE user_id = ? AND status = 'open' ORDER BY updated_at DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return int(row[0]), False

            cursor.execute(
                "INSERT INTO support_tickets (user_id, subject) VALUES (?, ?)",
                (user_id, subject)
            )
            conn.commit()
            return int(cursor.lastrowid), True
    except sqlite3.Error as e:
        logging.error(f"Failed to get_or_create_open_ticket for user {user_id}: {e}")
        return None, False

def add_support_message(ticket_id: int, sender: str, content: str) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO support_messages (ticket_id, sender, content) VALUES (?, ?, ?)",
                (ticket_id, sender, content)
            )
            cursor.execute(
                "UPDATE support_tickets SET updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (ticket_id,)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to add support message to ticket {ticket_id}: {e}")
        return None

def update_ticket_thread_info(ticket_id: int, forum_chat_id: str | None, message_thread_id: int | None) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET forum_chat_id = ?, message_thread_id = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (forum_chat_id, message_thread_id, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update thread info for ticket {ticket_id}: {e}")
        return False

def get_ticket(ticket_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get ticket {ticket_id}: {e}")
        return None

def get_ticket_by_thread(forum_chat_id: str, message_thread_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM support_tickets WHERE forum_chat_id = ? AND message_thread_id = ?",
                (str(forum_chat_id), int(message_thread_id))
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get ticket by thread {forum_chat_id}/{message_thread_id}: {e}")
        return None

def get_user_tickets(user_id: int, status: str | None = None) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE user_id = ? AND status = ? ORDER BY updated_at DESC",
                    (user_id, status)
                )
            else:
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,)
                )
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get tickets for user {user_id}: {e}")
        return []

def get_ticket_messages(ticket_id: int) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM support_messages WHERE ticket_id = ? ORDER BY created_at ASC",
                (ticket_id,)
            )
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get messages for ticket {ticket_id}: {e}")
        return []

def set_ticket_status(ticket_id: int, status: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (status, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set status '{status}' for ticket {ticket_id}: {e}")
        return False

def update_ticket_subject(ticket_id: int, subject: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET subject = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (subject, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update subject for ticket {ticket_id}: {e}")
        return False

def delete_ticket(ticket_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM support_messages WHERE ticket_id = ?",
                (ticket_id,)
            )
            cursor.execute(
                "DELETE FROM support_tickets WHERE ticket_id = ?",
                (ticket_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete ticket {ticket_id}: {e}")
        return False

def get_tickets_paginated(page: int = 1, per_page: int = 20, status: str | None = None) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = ?", (status,))
                total = cursor.fetchone()[0] or 0
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE status = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (status, per_page, offset)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM support_tickets")
                total = cursor.fetchone()[0] or 0
                cursor.execute(
                    "SELECT * FROM support_tickets ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (per_page, offset)
                )
            return [dict(r) for r in cursor.fetchall()], total
    except sqlite3.Error as e:
        logging.error("Failed to get paginated support tickets: %s", e)
        return [], 0

def get_open_tickets_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error("Failed to get open tickets count: %s", e)
        return 0

def get_closed_tickets_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'closed'")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error("Failed to get closed tickets count: %s", e)
        return 0

def get_all_tickets_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error("Failed to get all tickets count: %s", e)
        return 0





# --- Key usage monitor (traffic/devices) ---

def get_key_usage_monitor(key_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM key_usage_monitor WHERE key_id = ?", (key_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get key_usage_monitor for key_id={key_id}: {e}")
        return None


def ensure_key_usage_monitor_row(key_id: int, user_id: int) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO key_usage_monitor(key_id, user_id) VALUES(?, ?)",
                (int(key_id), int(user_id)),
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure key_usage_monitor row for key_id={key_id}: {e}")


def update_key_usage_monitor(
    key_id: int,
    *,
    first_seen_usage_at: str | None = None,
    last_reminder_at: str | None = None,
    last_checked_at: str | None = None,
    last_devices_count: int | None = None,
    last_traffic_bytes: int | None = None,
    overlimit_notified_count: int | None = None,
    overlimit_notified_at: str | None = None,
) -> bool:
    fields = []
    values = []
    if first_seen_usage_at is not None:
        fields.append("first_seen_usage_at = ?")
        values.append(first_seen_usage_at)
    if last_reminder_at is not None:
        fields.append("last_reminder_at = ?")
        values.append(last_reminder_at)
    if last_checked_at is not None:
        fields.append("last_checked_at = ?")
        values.append(last_checked_at)
    if last_devices_count is not None:
        fields.append("last_devices_count = ?")
        values.append(int(last_devices_count))
    if last_traffic_bytes is not None:
        fields.append("last_traffic_bytes = ?")
        values.append(int(last_traffic_bytes))
    if overlimit_notified_count is not None:
        fields.append("overlimit_notified_count = ?")
        values.append(int(overlimit_notified_count))
    if overlimit_notified_at is not None:
        fields.append("overlimit_notified_at = ?")
        values.append(overlimit_notified_at)

    if not fields:
        return False

    values.append(int(key_id))
    sql = "UPDATE key_usage_monitor SET " + ", ".join(fields) + " WHERE key_id = ?"

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update key_usage_monitor for key_id={key_id}: {e}")
        return False

# =============================
# Franchise (managed clone bots)
# =============================

# Константы больше не используются, значения берутся из настроек
# DEPRECATED: FRANCHISE_PERCENT_DEFAULT = 35.0
# DEPRECATED: FRANCHISE_MIN_WITHDRAW_RUB = 1500.0

def get_franchise_percent_default() -> float:
    """Получить процент комиссии франшизы из настроек."""
    try:
        val = (get_setting('franchise_commission_percent') or '35.0').strip()
        return float(val)
    except Exception:
        return 35.0


def get_franchise_min_withdraw() -> float:
    """Получить минимум для вывода франшизников из настроек."""
    try:
        val = (get_setting('franchise_min_withdraw_rub') or '1500.0').strip()
        return float(val)
    except Exception:
        return 1500.0


def resolve_factory_bot_id(telegram_bot_user_id: int | None) -> int:
    """Return internal managed bot id for a Telegram bot user id.

    Root (main) bot => 0.
    """
    try:
        tg_id = int(telegram_bot_user_id or 0)
    except Exception:
        return 0
    if tg_id <= 0:
        return 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM managed_bots WHERE telegram_bot_user_id = ? AND COALESCE(is_active,1)=1 LIMIT 1", (tg_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0
    except Exception:
        return 0


MANAGED_BOT_TOKEN_PREFIX = "enc1$"


def _managed_bot_token_secret() -> bytes:
    """Ключ шифрования токенов клонов: SHOPBOT_SECRET_KEY или стабильная запись в settings."""
    env = (os.getenv("SHOPBOT_SECRET_KEY") or "").strip()
    material = env
    if not material:
        material = (get_setting("managed_bot_token_key") or "").strip()
        if not material:
            material = secrets.token_hex(32)
            update_setting("managed_bot_token_key", material)
    return hashlib.sha256(f"managed-bot-token|{material}".encode("utf-8")).digest()


def _managed_bot_token_pad(secret: bytes, nonce: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hmac.new(secret, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest())
        counter += 1
    return bytes(out[:n])


def encrypt_managed_bot_token(token: str) -> str:
    """Зашифровать токен клона для хранения. Уже enc1$ не трогаем."""
    raw_s = (token or "").strip()
    if not raw_s:
        return raw_s
    if raw_s.startswith(MANAGED_BOT_TOKEN_PREFIX):
        return raw_s
    raw = raw_s.encode("utf-8")
    secret = _managed_bot_token_secret()
    nonce = secrets.token_bytes(16)
    pad = _managed_bot_token_pad(secret, nonce, len(raw))
    cipher = bytes(a ^ b for a, b in zip(raw, pad))
    mac = hmac.new(secret, nonce + cipher, hashlib.sha256).hexdigest()
    return f"{MANAGED_BOT_TOKEN_PREFIX}{nonce.hex()}${cipher.hex()}${mac}"


def decrypt_managed_bot_token(stored: str) -> str:
    """Расшифровать токен. Legacy plaintext (без enc1$) возвращается как есть."""
    s = (stored or "").strip()
    if not s:
        return s
    if not s.startswith(MANAGED_BOT_TOKEN_PREFIX):
        return s
    try:
        nonce_hex, cipher_hex, mac = s[len(MANAGED_BOT_TOKEN_PREFIX):].split("$", 2)
        nonce = bytes.fromhex(nonce_hex)
        cipher = bytes.fromhex(cipher_hex)
        secret = _managed_bot_token_secret()
        expected = hmac.new(secret, nonce + cipher, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, mac):
            logging.error("managed bot token MAC mismatch")
            return ""
        pad = _managed_bot_token_pad(secret, nonce, len(cipher))
        return bytes(a ^ b for a, b in zip(cipher, pad)).decode("utf-8")
    except Exception as e:
        logging.error("decrypt_managed_bot_token failed: %s", e)
        return ""


def _row_with_decrypted_token(row: dict | None) -> dict | None:
    if not row:
        return row
    data = dict(row)
    if data.get("token"):
        data["token"] = decrypt_managed_bot_token(str(data["token"]))
    return data


def get_managed_bot(bot_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM managed_bots WHERE id = ? LIMIT 1", (int(bot_id),))
            row = cur.fetchone()
            return _row_with_decrypted_token(dict(row) if row else None)
    except Exception as e:
        logger.error(f"get_managed_bot failed: {e}")
        return None


def get_managed_bot_by_telegram_id(telegram_bot_user_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM managed_bots WHERE telegram_bot_user_id = ? LIMIT 1", (int(telegram_bot_user_id),))
            row = cur.fetchone()
            return _row_with_decrypted_token(dict(row) if row else None)
    except Exception as e:
        logger.error(f"get_managed_bot_by_telegram_id failed: {e}")
        return None


def list_active_managed_bots() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM managed_bots WHERE COALESCE(is_active,1)=1 ORDER BY id ASC")
            return [_row_with_decrypted_token(dict(r)) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"list_active_managed_bots failed: {e}")
        return []


def create_managed_bot(
    *,
    token: str,
    telegram_bot_user_id: int,
    username: str | None,
    owner_telegram_id: int,
    referrer_bot_id: int = 0,
) -> tuple[bool, str, int | None]:
    """Register a managed bot.

    If the telegram bot user id already exists, the current owner may rotate
    token/username. A different user cannot take over ``owner_telegram_id``.
    """
    token_s = encrypt_managed_bot_token((token or "").strip())
    if not token_s:
        return False, "Токен пустой.", None
    try:
        tg_bot_id = int(telegram_bot_user_id)
        owner_id = int(owner_telegram_id)
        ref_bot_id = int(referrer_bot_id or 0)
    except Exception:
        return False, "Некорректные параметры.", None

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            # uniqueness by telegram_bot_user_id
            cur.execute("SELECT id, owner_telegram_id FROM managed_bots WHERE telegram_bot_user_id = ? LIMIT 1", (tg_bot_id,))
            row = cur.fetchone()
            if row:
                bot_id = int(row[0])
                existing_owner = int(row[1] or 0)
                if existing_owner != owner_id:
                    return False, "Этот бот уже зарегистрирован другим владельцем.", None
                # Same owner: allow token rotation. Owner is pinned in WHERE
                # so a concurrent takeover cannot win the UPDATE.
                cur.execute(
                    """
                    UPDATE managed_bots
                    SET token = ?, username = ?, referrer_bot_id = COALESCE(?, referrer_bot_id), is_active = 1
                    WHERE id = ? AND owner_telegram_id = ?
                    """,
                    (token_s, (username or None), ref_bot_id, bot_id, owner_id),
                )
                conn.commit()
                if cur.rowcount <= 0:
                    return False, "Этот бот уже зарегистрирован другим владельцем.", None
                return True, "Бот обновлён.", bot_id

            cur.execute(
                """
                INSERT INTO managed_bots (telegram_bot_user_id, username, token, owner_telegram_id, referrer_bot_id, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (tg_bot_id, (username or None), token_s, owner_id, ref_bot_id),
            )
            conn.commit()
            bot_id = int(cur.lastrowid)
            return True, "Бот создан.", bot_id
    except sqlite3.IntegrityError:
        # Параллельный INSERT с тем же telegram_bot_user_id (UNIQUE).
        return False, "Этот бот уже зарегистрирован другим владельцем.", None
    except sqlite3.Error as e:
        logger.error(f"create_managed_bot failed: {e}")
        return False, "Ошибка БД при создании бота.", None


def record_factory_activity(bot_id: int, user_id: int) -> None:
    """Upsert activity row (unique users + messages count)."""
    try:
        b = int(bot_id or 0)
        u = int(user_id or 0)
    except Exception:
        return
    # Root (main) bot is not tracked as a franchise bot.
    if b <= 0:
        return
    if u <= 0:
        return
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO factory_user_activity (bot_id, user_id, first_seen, last_seen, messages_count)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                ON CONFLICT(bot_id, user_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    messages_count = COALESCE(messages_count,0) + 1
                """,
                (b, u),
            )
            conn.commit()
    except Exception:
        return


def _is_card_payment_method(method: str | None) -> bool:
    m = (method or "").strip().lower()
    if not m:
        return False
    if m in {"balance", "баланс"}:
        return False
    # Card-like providers (as configured in this project)
    return m in {"yookassa", "platega", "heleket", "yoomoney"}


def accrue_partner_commission(
    bot_id: int,
    payment_id: str,
    user_id: int,
    amount_rub: float,
    payment_method: str | None,
    percent: float | None = None,
) -> bool:
    """Accrue partner commission for a managed bot.

    Only card payments are counted. Internal balance payments are ignored.
    Idempotent by (bot_id, payment_id).
    """
    try:
        b = int(bot_id or 0)
    except Exception:
        b = 0
    if b <= 0:
        return False

    if not _is_card_payment_method(payment_method):
        return False

    pid = (payment_id or "").strip()
    if not pid:
        return False

    try:
        u = int(user_id)
    except Exception:
        return False

    try:
        amt = float(amount_rub)
    except Exception:
        return False
    if amt <= 0:
        return False

    p = float(percent if percent is not None else get_franchise_percent_default())
    if p <= 0:
        return False

    com = round(amt * p / 100.0, 2)
    if com <= 0:
        return False

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()

            # --- Self-purchase guard ---
            # 1. Direct: buyer == owner of this bot
            # 2. Indirect: buyer was referred by the owner (owner recruited their own customer)
            # 3. Referrer-bot chain: buyer == owner of the parent bot that created this bot
            cur.execute(
                "SELECT owner_telegram_id, COALESCE(referrer_bot_id, 0) FROM managed_bots WHERE id = ? LIMIT 1",
                (b,),
            )
            row = cur.fetchone()
            if row:
                owner_id = int(row[0] or 0)
                referrer_bot_id = int(row[1] or 0)

                if owner_id and u == owner_id:
                    logging.warning(
                        "accrue_partner_commission: skipped — self-purchase (user %d == owner %d, bot %d)",
                        u, owner_id, b,
                    )
                    return False

                # Check if buyer was referred by the owner
                cur.execute("SELECT referred_by FROM users WHERE telegram_id = ? LIMIT 1", (u,))
                user_row = cur.fetchone()
                referred_by = int((user_row[0] or 0)) if user_row else 0
                if owner_id and referred_by == owner_id:
                    logging.warning(
                        "accrue_partner_commission: skipped — buyer %d referred by owner %d (bot %d)",
                        u, owner_id, b,
                    )
                    return False

                # Check if buyer is the owner of the referrer/parent bot
                if referrer_bot_id > 0:
                    cur.execute(
                        "SELECT owner_telegram_id FROM managed_bots WHERE id = ? LIMIT 1",
                        (referrer_bot_id,),
                    )
                    ref_row = cur.fetchone()
                    ref_owner_id = int((ref_row[0] or 0)) if ref_row else 0
                    if ref_owner_id and u == ref_owner_id:
                        logging.warning(
                            "accrue_partner_commission: skipped — buyer %d is owner of referrer bot %d (bot %d)",
                            u, referrer_bot_id, b,
                        )
                        return False

            cur.execute(
                """
                INSERT OR IGNORE INTO partner_commissions
                (bot_id, payment_id, user_id, amount_rub, commission_percent, commission_rub, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (b, pid, u, amt, p, com, (payment_method or None)),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"accrue_partner_commission failed: {e}")
        return False


def get_partner_cabinet(bot_id: int) -> dict:
    """Return partner cabinet stats for managed bot."""
    try:
        b = int(bot_id or 0)
    except Exception:
        b = 0
    res = {
        "total_users": 0,
        "gross_paid_card": 0.0,
        "commission_total": 0.0,
        "commission_percent": get_franchise_percent_default(),
        "requested_withdraw": 0.0,
        "available": 0.0,
    }
    if b <= 0:
        return res

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(1) FROM factory_user_activity WHERE bot_id = ?", (b,))
            res["total_users"] = int(cur.fetchone()[0] or 0)

            cur.execute("SELECT COALESCE(SUM(amount_rub),0), COALESCE(SUM(commission_rub),0) FROM partner_commissions WHERE bot_id = ?", (b,))
            row = cur.fetchone() or (0, 0)
            res["gross_paid_card"] = float(row[0] or 0)
            res["commission_total"] = float(row[1] or 0)

            cur.execute(
                """
                SELECT COALESCE(SUM(amount_rub),0)
                FROM partner_withdraw_requests
                WHERE bot_id = ? AND status IN ('pending','approved','paid')
                """,
                (b,),
            )
            res["requested_withdraw"] = float(cur.fetchone()[0] or 0)

        res["available"] = max(0.0, float(res["commission_total"]) - float(res["requested_withdraw"]))
        return res
    except Exception as e:
        logger.error(f"get_partner_cabinet failed: {e}")
        return res




def list_partner_requisites(bot_id: int, owner_telegram_id: int) -> list[dict]:
    """Return all payout requisites for a partner (owner) within a managed bot."""
    try:
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return []
    if b <= 0 or owner <= 0:
        return []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, bot_id, owner_telegram_id, bank, requisite_type, requisite_value, is_default, created_at "
                "FROM partner_payout_requisites WHERE bot_id = ? AND owner_telegram_id = ? "
                "ORDER BY is_default DESC, created_at DESC",
                (b, owner),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.error(f"list_partner_requisites failed: {e}")
        return []


def get_default_partner_requisite(bot_id: int, owner_telegram_id: int) -> dict | None:
    """Return the default payout requisite for a partner, if any."""
    items = list_partner_requisites(bot_id, owner_telegram_id)
    for r in items:
        try:
            if int(r.get('is_default') or 0) == 1:
                return r
        except Exception:
            continue
    return items[0] if items else None


def add_partner_requisite(
    bot_id: int,
    owner_telegram_id: int,
    bank: str,
    requisite_value: str,
    requisite_type: str,
    *,
    make_default: bool | None = None,
) -> tuple[bool, str, int | None]:
    """Add a payout requisite for a partner.

    requisite_type: 'card' or 'phone'
    """
    try:
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return False, 'Некорректные данные.', None

    bank_s = (bank or '').strip()
    value_s = (requisite_value or '').strip()
    rtype = (requisite_type or '').strip().lower()

    if b <= 0 or owner <= 0:
        return False, 'Некорректные данные.', None
    if not bank_s or len(bank_s) > 120:
        return False, 'Укажите банк (до 120 символов).', None
    if not value_s or len(value_s) > 64:
        return False, 'Укажите корректные реквизиты.', None
    if rtype not in {'card', 'phone'}:
        rtype = 'card'

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # If it's the first one - force default
            cur.execute(
                "SELECT COUNT(1) FROM partner_payout_requisites WHERE bot_id = ? AND owner_telegram_id = ?",
                (b, owner),
            )
            count = int((cur.fetchone() or [0])[0] or 0)
            if count == 0:
                make_def = True
            elif make_default is None:
                make_def = False
            else:
                make_def = bool(make_default)

            if make_def:
                cur.execute(
                    "UPDATE partner_payout_requisites SET is_default = 0 WHERE bot_id = ? AND owner_telegram_id = ?",
                    (b, owner),
                )

            cur.execute(
                "INSERT INTO partner_payout_requisites (bot_id, owner_telegram_id, bank, requisite_type, requisite_value, is_default) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (b, owner, bank_s, rtype, value_s, 1 if make_def else 0),
            )
            new_id = int(cur.lastrowid or 0)
            conn.commit()

        return True, 'Реквизиты добавлены.', (new_id if new_id > 0 else None)
    except Exception as e:
        logger.error(f"add_partner_requisite failed: {e}")
        return False, 'Ошибка при сохранении реквизитов.', None


def set_default_partner_requisite(req_id: int, bot_id: int, owner_telegram_id: int) -> tuple[bool, str]:
    """Set given requisite as default for this bot/owner."""
    try:
        rid = int(req_id or 0)
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return False, 'Некорректные данные.'
    if rid <= 0 or b <= 0 or owner <= 0:
        return False, 'Некорректные данные.'

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM partner_payout_requisites WHERE id = ? AND bot_id = ? AND owner_telegram_id = ?",
                (rid, b, owner),
            )
            row = cur.fetchone()
            if not row:
                return False, 'Реквизиты не найдены.'

            cur.execute(
                "UPDATE partner_payout_requisites SET is_default = 0 WHERE bot_id = ? AND owner_telegram_id = ?",
                (b, owner),
            )
            cur.execute(
                "UPDATE partner_payout_requisites SET is_default = 1 WHERE id = ?",
                (rid,),
            )
            conn.commit()
        return True, 'Основные реквизиты обновлены.'
    except Exception as e:
        logger.error(f"set_default_partner_requisite failed: {e}")
        return False, 'Ошибка при обновлении.'


def delete_partner_requisite(req_id: int, bot_id: int, owner_telegram_id: int) -> tuple[bool, str]:
    """Delete a payout requisite."""
    try:
        rid = int(req_id or 0)
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
    except Exception:
        return False, 'Некорректные данные.'
    if rid <= 0 or b <= 0 or owner <= 0:
        return False, 'Некорректные данные.'

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT id, is_default FROM partner_payout_requisites WHERE id = ? AND bot_id = ? AND owner_telegram_id = ?",
                (rid, b, owner),
            )
            row = cur.fetchone()
            if not row:
                return False, 'Реквизиты не найдены.'
            was_default = int(row['is_default'] or 0) == 1

            cur.execute(
                "DELETE FROM partner_payout_requisites WHERE id = ? AND bot_id = ? AND owner_telegram_id = ?",
                (rid, b, owner),
            )

            if was_default:
                # Promote newest to default if any remains
                cur.execute(
                    "SELECT id FROM partner_payout_requisites WHERE bot_id = ? AND owner_telegram_id = ? ORDER BY created_at DESC LIMIT 1",
                    (b, owner),
                )
                row2 = cur.fetchone()
                if row2:
                    cur.execute(
                        "UPDATE partner_payout_requisites SET is_default = 1 WHERE id = ?",
                        (int(row2[0]),),
                    )
            conn.commit()
        return True, 'Реквизиты удалены.'
    except Exception as e:
        logger.error(f"delete_partner_requisite failed: {e}")
        return False, 'Ошибка при удалении.'


def create_withdraw_request(
    bot_id: int,
    owner_telegram_id: int,
    amount_rub: float,
    comment: str | None = None,
    *,
    bank: str | None = None,
    requisite_type: str | None = None,
    requisite_value: str | None = None,
    requisite_id: int | None = None,
) -> tuple[bool, str]:
    """Create a partner withdraw request.

    Enforces minimum (1500 RUB) and available balance.
    """
    try:
        b = int(bot_id or 0)
        owner = int(owner_telegram_id or 0)
        amt = float(amount_rub)
    except Exception:
        return False, "Некорректные данные."

    if b <= 0:
        return False, "Вывод доступен только во клонах."

    min_withdraw = get_franchise_min_withdraw()
    if amt < min_withdraw:
        return False, f"Минимальная сумма вывода: {min_withdraw:.0f} RUB."

    stats = get_partner_cabinet(b)
    available = float(stats.get("available", 0.0) or 0.0)
    if amt > available + 1e-9:
        return False, f"Недостаточно средств. Доступно: {available:.2f} RUB."

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO partner_withdraw_requests (bot_id, owner_telegram_id, amount_rub, status, comment, bank, requisite_type, requisite_value, requisite_id)
                VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                """,
                (b, owner, amt, (comment or None), (bank or None), (requisite_type or None), (requisite_value or None), (int(requisite_id) if requisite_id is not None else None)),
            )
            conn.commit()
        return True, "Заявка на вывод создана и отправлена администратору."
    except Exception as e:
        logger.error(f"create_withdraw_request failed: {e}")
        return False, "Ошибка при создании заявки."


# ============================================
# Функции для работы с пользовательскими подарками
# ============================================

def create_user_gift(
    from_user_id: int,
    host_name: str,
    plan_id: int | None = None,
    gift_code: str | None = None,
    expires_in_days: int | None = None,
) -> dict | None:
    """Создать неактивированный подарок от одного пользователя.
    
    Returns: dict with gift_id and gift_code on success, None on error.
    """
    import uuid
    
    try:
        from_user_id = int(from_user_id)
        host_name = str(host_name).strip()
        plan_id = int(plan_id) if plan_id else None
        
        if not gift_code:
            gift_code = str(uuid.uuid4())[:12]
        
        expires_at = None
        if expires_in_days:
            expires_at = (datetime.utcnow() + timedelta(days=int(expires_in_days))).isoformat()
        
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute(
                """
                INSERT INTO user_gifts (from_user_id, host_name, plan_id, gift_code, is_activated, expires_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (from_user_id, host_name, plan_id, gift_code, expires_at),
            )
            conn.commit()
            
            gift_id = cur.lastrowid
            return {
                "gift_id": gift_id,
                "gift_code": gift_code,
            }
    except sqlite3.IntegrityError:
        logger.error(f"Gift code {gift_code} already exists")
        return None
    except Exception as e:
        logger.error(f"Failed to create user gift: {e}")
        return None


def get_user_gift(gift_id: int) -> dict | None:
    """Получить информацию о подарке по ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_gifts WHERE gift_id = ?", (int(gift_id),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user gift {gift_id}: {e}")
        return None


def get_gift_by_code(gift_code: str) -> dict | None:
    """Получить информацию о подарке по коду."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_gifts WHERE gift_code = ?", (str(gift_code).strip(),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get gift by code {gift_code}: {e}")
        return None


def get_user_inactive_gifts(from_user_id: int) -> list[dict]:
    """Получить список неактивированных подарков пользователя.

    Заодно подчищает "осиротевшие" подарки — те, чей связанный ключ (vpn_keys)
    уже был удалён (например, стандартной чисткой просроченных ключей), но по
    какой-то причине запись в user_gifts не была удалена вместе с ним. Такие
    подарки не должны продолжать висеть в списке пользователя.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM user_gifts
                WHERE from_user_id = ? AND is_activated = 0
                  AND key_id IS NOT NULL
                  AND key_id NOT IN (SELECT key_id FROM vpn_keys)
                """,
                (int(from_user_id),),
            )
            if cur.rowcount:
                conn.commit()
            cur.execute(
                "SELECT * FROM user_gifts WHERE from_user_id = ? AND is_activated = 0 ORDER BY created_at DESC",
                (int(from_user_id),),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get inactive gifts for user {from_user_id}: {e}")
        return []


def activate_user_gift(
    gift_code: str,
    activated_by_user_id: int,
) -> tuple[bool, dict | None]:
    """Активировать подарок для пользователя.

    Атомарность/защита от race condition: сама активация — это одно UPDATE
    с условием `is_activated = 0` прямо в WHERE, и именно `cursor.rowcount`
    (а не предварительный SELECT) решает, "выиграл" ли этот вызов гонку.
    Так два параллельных запроса на активацию одного и того же подарка не
    могут оба посчитать себя успешными — только один получит rowcount=1.

    Returns: (success, gift_data)
    """
    try:
        gift = get_gift_by_code(gift_code)
        if not gift:
            return False, None
        
        gift_id = gift.get("gift_id")
        if gift.get("is_activated"):
            return False, gift  # Already activated
        
        expires_at = gift.get("expires_at")
        if expires_at:
            if datetime.fromisoformat(expires_at) < datetime.utcnow():
                return False, gift  # Expired
        
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_gifts
                SET is_activated = 1, activated_by_user_id = ?, activated_at = ?
                WHERE gift_code = ? AND is_activated = 0
                """,
                (int(activated_by_user_id), _now_str(), gift_code),
            )
            won_race = cur.rowcount > 0
            conn.commit()

        if not won_race:
            # Другой параллельный запрос уже успел активировать этот подарок первым.
            return False, gift
        
        gift["is_activated"] = True
        gift["activated_by_user_id"] = int(activated_by_user_id)
        gift["activated_at"] = _now_str()
        
        logging.info(f"Gift {gift_code} activated by user {activated_by_user_id}")
        return True, gift
        
    except Exception as e:
        logger.error(f"Failed to activate gift {gift_code}: {e}")
        return False, None


def _registration_age_seconds(reg_date_raw) -> float | None:
    """Возраст аккаунта в секундах, либо None если даты нет / она не парсится."""
    if not reg_date_raw:
        return None
    try:
        reg_dt = datetime.fromisoformat(str(reg_date_raw).replace("Z", "+00:00"))
        if reg_dt.tzinfo is not None:
            reg_dt = reg_dt.replace(tzinfo=None)
        return (datetime.now() - reg_dt).total_seconds()
    except Exception:
        return None


def set_referred_by_from_gift(user_id: int, from_user_id: int, *, max_age_seconds: int = 1800) -> bool:
    """Set referred_by to the gift sender when a new user activates a gift.

    Guard: skips if the user's registration_date is older than max_age_seconds
    (meaning they were already registered before this gift activation).
    """
    uid = int(user_id)
    fid = int(from_user_id)
    if fid <= 0 or fid == uid:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT referred_by, registration_date FROM users WHERE telegram_id = ?", (uid,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            current_ref, reg_date_raw = row
            if current_ref:
                return False  # already has a referrer
            age = _registration_age_seconds(reg_date_raw)
            if age is not None and age > max_age_seconds:
                logging.info(
                    "set_referred_by_from_gift: skipped user %s "
                    "(registered %.0f s ago, threshold %d s)", uid, age, max_age_seconds
                )
                return False
            cursor.execute(
                "UPDATE users SET referred_by = ? WHERE telegram_id = ? AND referred_by IS NULL",
                (fid, uid),
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logging.error("set_referred_by_from_gift failed for user %s: %s", user_id, e)
        return False


# Возможные статусы результата привязки реферала — используются как UI-статусы
# в ответе POST /api/webapp/pending-actions/complete.
REFERRAL_LINK_LINKED = "linked"
REFERRAL_LINK_ALREADY_LINKED = "already_linked"
REFERRAL_LINK_SELF_FORBIDDEN = "self_referral_forbidden"
REFERRAL_LINK_INVALID_REFERRER = "invalid_referrer"
REFERRAL_LINK_NOT_ELIGIBLE = "not_eligible"


def link_referrer_if_eligible(user_id: int, referrer_id: int, *, max_age_seconds: int | None = None) -> str:
    """Привязать пользователя к рефереру (users.referred_by), если это допустимо.

    Атомарно: UPDATE сразу проверяет условие `referred_by IS NULL` в WHERE и
    возвращает успех по `cursor.rowcount` — так что даже при параллельных
    вызовах (например, два одновременных запроса complete по одному и тому же
    pending-токену) привязка реферера не может произойти дважды и не может
    затереть уже существующего реферера.

    ``max_age_seconds``: если задан, аккаунт старше этого окна не привязывается
    (тот же guard, что у ``set_referred_by_from_gift``). Webapp pending-action
    передаёт окно, чтобы старый аккаунт с пустым ``referred_by`` нельзя было
    late-bind'ить реферальной ссылкой. Админский ручной assign вызывает без
    окна — существующая возможность назначить реферала сохраняется.

    Возвращает один из: linked, already_linked, self_referral_forbidden,
    invalid_referrer, not_eligible.
    """
    try:
        uid = int(user_id)
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return REFERRAL_LINK_INVALID_REFERRER

    if rid <= 0:
        return REFERRAL_LINK_INVALID_REFERRER
    if rid == uid:
        return REFERRAL_LINK_SELF_FORBIDDEN

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM users WHERE telegram_id = ?", (rid,))
            if not cursor.fetchone():
                return REFERRAL_LINK_INVALID_REFERRER

            cursor.execute(
                "SELECT referred_by, registration_date FROM users WHERE telegram_id = ?",
                (uid,),
            )
            row = cursor.fetchone()
            if not row:
                return REFERRAL_LINK_NOT_ELIGIBLE

            if row[0] is not None:
                return REFERRAL_LINK_ALREADY_LINKED if int(row[0]) == rid else REFERRAL_LINK_ALREADY_LINKED

            if max_age_seconds is not None:
                age = _registration_age_seconds(row[1])
                if age is not None and age > max_age_seconds:
                    logging.info(
                        "link_referrer_if_eligible: skipped user %s "
                        "(registered %.0f s ago, threshold %d s)",
                        uid, age, max_age_seconds,
                    )
                    return REFERRAL_LINK_NOT_ELIGIBLE

            cursor.execute(
                "UPDATE users SET referred_by = ? WHERE telegram_id = ? AND referred_by IS NULL AND telegram_id != ?",
                (rid, uid, rid),
            )
            conn.commit()
            if cursor.rowcount > 0:
                return REFERRAL_LINK_LINKED
            # Кто-то параллельно уже успел выставить referred_by между нашим SELECT и UPDATE.
            return REFERRAL_LINK_ALREADY_LINKED
    except Exception as e:
        logging.error("link_referrer_if_eligible failed for user %s -> referrer %s: %s", user_id, referrer_id, e)
        return REFERRAL_LINK_NOT_ELIGIBLE


REFERRAL_UNLINK_UNLINKED = "unlinked"
REFERRAL_UNLINK_NOT_LINKED = "not_linked"
REFERRAL_UNLINK_NOT_FOUND = "not_found"
REFERRAL_UNLINK_INVALID = "invalid"


def unlink_referral(invitee_id: int, referrer_id: int) -> str:
    """Снять привязку реферала: обнулить users.referred_by у invitee, если он
    действительно привязан к referrer_id.

    Возвращает: unlinked, not_linked, not_found, invalid.
    """
    try:
        uid = int(invitee_id)
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return REFERRAL_UNLINK_INVALID

    if uid <= 0 or rid <= 0 or uid == rid:
        return REFERRAL_UNLINK_INVALID

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return REFERRAL_UNLINK_NOT_FOUND
            if row[0] is None or int(row[0]) != rid:
                return REFERRAL_UNLINK_NOT_LINKED

            cursor.execute(
                "UPDATE users SET referred_by = NULL WHERE telegram_id = ? AND referred_by = ?",
                (uid, rid),
            )
            conn.commit()
            if cursor.rowcount > 0:
                return REFERRAL_UNLINK_UNLINKED
            return REFERRAL_UNLINK_NOT_LINKED
    except Exception as e:
        logging.error("unlink_referral failed for invitee %s / referrer %s: %s", invitee_id, referrer_id, e)
        return REFERRAL_UNLINK_INVALID


def unlink_all_referrals(referrer_id: int) -> tuple[bool, int]:
    """Снять привязку у всех рефералов указанного реферера.

    Возвращает (ok, removed_count).
    """
    try:
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return False, 0
    if rid <= 0:
        return False, 0

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                (rid,),
            )
            removed = int(cursor.rowcount or 0)
            conn.commit()
            return True, removed
    except Exception as e:
        logging.error("unlink_all_referrals failed for referrer %s: %s", referrer_id, e)
        return False, 0


def delete_user_gift(gift_id: int) -> bool:
    """Удалить подарок."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_gifts WHERE gift_id = ?", (int(gift_id),))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete gift {gift_id}: {e}")
        return False


def link_key_to_gift(gift_id: int, key_id: int) -> bool:
    """Связать созданный ключ с подарком."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE user_gifts SET key_id = ? WHERE gift_id = ?",
                (int(key_id), int(gift_id)),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to link key {key_id} to gift {gift_id}: {e}")
        return False


def get_gift_code_by_key_id(key_id: int) -> str | None:
    """Получить код подарка по ID ключа."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT gift_code FROM user_gifts WHERE key_id = ?", (int(key_id),))
            row = cur.fetchone()
            return row['gift_code'] if row else None
    except Exception as e:
        logger.error(f"Failed to get gift code for key {key_id}: {e}")
        return None

def get_gift_code_by_key_id(key_id: int) -> str | None:
    """Получить код подарка по ID ключа."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT gift_code FROM user_gifts WHERE key_id = ? AND is_activated = 0", (int(key_id),))
            row = cur.fetchone()
            return row['gift_code'] if row else None
    except Exception as e:
        logger.error(f"Failed to get gift code for key {key_id}: {e}")
        return None

def get_gift_info_by_key_id(key_id: int) -> tuple[int | None, str | None]:
    """Получить ID и код подарка по ID ключа. Возвращает (gift_id, gift_code) или (None, None)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT gift_id, gift_code FROM user_gifts WHERE key_id = ? AND is_activated = 0", (int(key_id),))
            row = cur.fetchone()
            if row:
                return row['gift_id'], row['gift_code']
            return None, None
    except Exception as e:
        logger.error(f"Failed to get gift info for key {key_id}: {e}")
        return None, None


# =============================================================
# WEBAPP (Telegram Mini App) support functions
# =============================================================

def get_msk_time() -> datetime:
    """Текущее время в московской зоне (UTC+3), используется для расчётов сроков в webapp."""
    from datetime import timezone as _tz
    return datetime.now(_tz.utc).astimezone(_tz(timedelta(hours=3)))


def check_transaction_exists(payment_id: str) -> bool:
    """Проверить, существует ли уже завершённая транзакция с данным payment_id.

    TON Connect пишет в ``transactions`` строку со ``status='pending'`` ещё до
    подтверждения в блокчейне. Раньше этот SELECT не фильтровал статус — из-за
    этого ``/api/check-payment`` отвечал ``paid: true`` сразу после создания
    счёта. Финальный статус TON-вебхука — ``paid`` (см. find_and_complete_ton_transaction).
    """
    if not payment_id:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 1 FROM transactions
                WHERE payment_id = ?
                  AND LOWER(TRIM(COALESCE(status, ''))) = 'paid'
                LIMIT 1
                """,
                (str(payment_id),),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check transaction existence for {payment_id}: {e}")
        return False


def payment_owned_by_user(payment_id: str, user_id: int) -> bool:
    """True, если payment_id есть в pending_transactions или transactions у этого user_id.

    Статус не фильтруем: владелец должен иметь возможность поллить и pending,
    и уже оплаченный счёт. Чужой payment_id даёт False (без различия «нет» / «чужой»).
    """
    pid = (payment_id or "").strip()
    if not pid:
        return False
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT 1 FROM pending_transactions WHERE payment_id = ? AND user_id = ? LIMIT 1",
                (pid, uid),
            )
            if cursor.fetchone() is not None:
                return True
            cursor.execute(
                "SELECT 1 FROM transactions WHERE payment_id = ? AND user_id = ? LIMIT 1",
                (pid, uid),
            )
            return cursor.fetchone() is not None

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logger.error(f"Failed to check payment ownership for {pid}: {e}")
        return False


def get_seller_user(user_id: int) -> dict | None:
    """Вернуть данные продавца (франшиза/партнёрская скидка) для пользователя.

    В текущей версии проекта отдельной "seller"-подсистемы нет (есть колонки-заглушки
    users.seller_active/seller_sale, по умолчанию выключены), функция возвращает
    запись пользователя, если seller_active включён вручную в БД, иначе None.
    """
    try:
        user = get_user(user_id)
        if user and user.get('seller_active'):
            return user
        return None
    except Exception as e:
        logger.error(f"Failed to get seller user {user_id}: {e}")
        return None


def get_device_tiers(host_name: str) -> list[dict]:
    """Вернуть тарифные планы, сгруппированные по лимиту устройств, для указанного хоста.

    Пока в проекте нет отдельной сущности "device tiers" — используем активные тарифы
    хоста (get_plans_for_host) как есть, отсортированные по hwid_device_limit.
    """
    try:
        plans = get_plans_for_host(host_name) or []
        active = [p for p in plans if p.get('is_active')]
        active.sort(key=lambda p: (p.get('hwid_device_limit') or 0))
        return active
    except Exception as e:
        logger.error(f"Failed to get device tiers for host {host_name}: {e}")
        return []


def get_user_by_auth_token(token: str) -> dict | None:
    """Найти пользователя по постоянному auth-токену (webapp)."""
    if not token:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE auth_token = ?", (str(token),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user by auth token: {e}")
        return None


def get_auth_token_by_user_id(user_id: int) -> str | None:
    """Получить уже выданный постоянный auth-токен пользователя, если есть."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("SELECT auth_token FROM users WHERE telegram_id = ?", (int(user_id),))
            row = cur.fetchone()
            return row[0] if row and row[0] else None
    except Exception as e:
        logger.error(f"Failed to get auth token for user {user_id}: {e}")
        return None


def update_user_auth_token(user_id: int, token: str) -> bool:
    """Сохранить постоянный auth-токен для пользователя (webapp)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET auth_token = ? WHERE telegram_id = ?", (str(token), int(user_id)))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update auth token for user {user_id}: {e}")
        return False


def invalidate_all_user_auth_tokens() -> int:
    """Перевыпустить все persistent auth_token пользователей (UUID4).

    Используется как remediation после компрометации токенов (например, через
    уязвимый /api/auth/telegram-direct). Старые токены в браузерах/клиентах
    перестают работать; пользователи должны войти заново.
    Возвращает число обновлённых строк.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT telegram_id FROM users WHERE auth_token IS NOT NULL AND TRIM(auth_token) != ''"
            )
            rows = cur.fetchall()
            updated = 0
            for (telegram_id,) in rows:
                cur.execute(
                    "UPDATE users SET auth_token = ? WHERE telegram_id = ?",
                    (str(uuid.uuid4()), int(telegram_id)),
                )
                updated += cur.rowcount
            conn.commit()
            return updated
    except Exception as e:
        logger.error(f"Failed to invalidate all user auth tokens: {e}")
        return 0


def hash_password(password: str) -> str:
    """Хэшировать пароль пользователя (PBKDF2-HMAC-SHA256 со случайной солью)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
    return f"pbkdf2${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    """Проверить пароль против сохранённого хэша.

    Поддерживает как новый формат (pbkdf2$salt$hash), так и старые аккаунты,
    у которых пароль ещё хранится в открытом виде (миграция «на лету»).
    """
    if not stored:
        return False
    try:
        if stored.startswith("pbkdf2$"):
            _, salt, digest = stored.split("$", 2)
            check = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000).hex()
            return hmac.compare_digest(check, digest)
    except Exception:
        return False
    # Legacy plaintext fallback for accounts created before hashing was introduced.
    return hmac.compare_digest(stored, password)


def get_user_by_email(email: str) -> dict | None:
    """Найти локального пользователя webapp по email (для входа по email+паролю)."""
    norm = _normalize_email(email)
    if not norm:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE auth_email = ?", (norm,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user by email {email}: {e}")
        return None


def create_user_by_email(email: str, password: str) -> dict | None:
    """Создать "виртуального" (не привязанного к Telegram) пользователя webapp по email+паролю.

    Использует псевдо-telegram_id с префиксом 999, чтобы не пересекаться с реальными
    Telegram ID (см. handlers.py: str(user_id).startswith("999") — признак несинхронизированного аккаунта).
    Пароль сохраняется в виде хэша (см. hash_password/verify_password).
    Аккаунт создаётся неподтверждённым (email_verified=0) до прохождения проверки кода.
    """
    norm = _normalize_email(email)
    if not norm:
        return None
    try:
        password_hash = hash_password(password)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT MAX(telegram_id) FROM users WHERE telegram_id BETWEEN ? AND ?",
                (EMAIL_ONLY_TELEGRAM_ID_MIN, EMAIL_ONLY_TELEGRAM_ID_MAX),
            )
            row = cur.fetchone()
            next_id = int(row[0]) + 1 if row and row[0] else EMAIL_ONLY_TELEGRAM_ID_MIN + 1
            cur.execute(
                """
                INSERT INTO users (telegram_id, username, agreed_to_terms, auth_email, auth_pass, email_verified, registration_date)
                VALUES (?, ?, 1, ?, ?, 0, CURRENT_TIMESTAMP)
                """,
                (next_id, norm.split('@')[0], norm, password_hash),
            )
            conn.commit()
        return get_user(next_id)
    except Exception as e:
        logger.error(f"Failed to create user by email {email}: {e}")
        return None


def update_user_password(email: str, new_password: str) -> bool:
    """Обновить (хэшированный) пароль локального webapp-аккаунта по email."""
    norm = _normalize_email(email)
    if not norm:
        return False
    try:
        password_hash = hash_password(new_password)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET auth_pass = ? WHERE auth_email = ?", (password_hash, norm))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update password for {email}: {e}")
        return False


def _hash_verification_code(user_id: int, code: str) -> str:
    return hashlib.sha256(f"{int(user_id)}:{code}".encode("utf-8")).hexdigest()


def set_email_verification_code(user_id: int, code: str, ttl_seconds: int = 600) -> bool:
    """Сохранить хэш одноразового кода подтверждения email и время его истечения."""
    try:
        code_hash = _hash_verification_code(user_id, code)
        expires_at = (datetime.utcnow() + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET email_code_hash = ?, email_code_expires_at = ?, email_code_last_sent_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
                """,
                (code_hash, expires_at, int(user_id)),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to set email verification code for user {user_id}: {e}")
        return False


def get_email_verification(user_id: int) -> dict | None:
    """Вернуть данные о статусе подтверждения email и последнем отправленном коде."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                SELECT email_verified, email_code_hash, email_code_expires_at, email_code_last_sent_at, auth_email
                FROM users WHERE telegram_id = ?
                """,
                (int(user_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get email verification for user {user_id}: {e}")
        return None


def check_email_verification_code(user_id: int, code: str) -> bool:
    """Проверить введённый код подтверждения против сохранённого хэша (с учётом срока действия)."""
    info = get_email_verification(user_id)
    if not info or not info.get("email_code_hash") or not info.get("email_code_expires_at"):
        return False
    try:
        expires_at = datetime.strptime(str(info["email_code_expires_at"]), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    if datetime.utcnow() > expires_at:
        return False
    expected = _hash_verification_code(user_id, str(code).strip())
    return hmac.compare_digest(expected, str(info["email_code_hash"]))


def mark_email_verified(user_id: int) -> bool:
    """Отметить email пользователя как подтверждённый и очистить код."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET email_verified = 1, email_code_hash = NULL, email_code_expires_at = NULL
                WHERE telegram_id = ?
                """,
                (int(user_id),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to mark email verified for user {user_id}: {e}")
        return False


def update_email_code_last_sent(user_id: int) -> bool:
    """Обновить время последней отправки кода (для rate-limit повторной отправки)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET email_code_last_sent_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (int(user_id),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update email code last sent for user {user_id}: {e}")
        return False


def update_user_password_by_id(user_id: int, new_password: str) -> bool:
    """Обновить (хэшированный) пароль webapp-аккаунта по telegram_id (смена пароля из профиля,
    когда пользователь уже авторизован и email известен только по сессии, а не по вводу)."""
    try:
        password_hash = hash_password(new_password)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET auth_pass = ? WHERE telegram_id = ?", (password_hash, int(user_id)))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update password for user {user_id}: {e}")
        return False


def set_pending_email(user_id: int, new_email: str) -> bool:
    """Сохранить новый email, ожидающий подтверждения кодом (смена почты из профиля).
    Текущий auth_email остаётся действующим для входа, пока код не подтверждён."""
    norm = _normalize_email(new_email)
    if not norm:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET pending_email = ? WHERE telegram_id = ?", (norm, int(user_id)))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to set pending email for user {user_id}: {e}")
        return False


def clear_pending_email(user_id: int) -> bool:
    """Отменить ожидающую смену email (например, пользователь передумал или запросил другой адрес)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET pending_email = NULL, email_code_hash = NULL, email_code_expires_at = NULL "
                "WHERE telegram_id = ?",
                (int(user_id),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to clear pending email for user {user_id}: {e}")
        return False


def finalize_pending_email_change(user_id: int) -> tuple[bool, str | None]:
    """Подтвердить смену email кодом: перенести `pending_email` в `auth_email`.

    Атомарно перепроверяет, что новый адрес не был занят другим аккаунтом за время
    ожидания кода (защита от гонки, если два пользователя одновременно решили
    переключиться на один и тот же email). Возвращает (ok, new_email_или_текст_ошибки).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT pending_email FROM users WHERE telegram_id = ?", (int(user_id),))
            row = cur.fetchone()
            pending = row["pending_email"] if row else None
            if not pending:
                return False, "Нет ожидающей смены email"

            cur.execute(
                "SELECT telegram_id FROM users WHERE auth_email = ? AND telegram_id != ?",
                (pending, int(user_id)),
            )
            if cur.fetchone():
                cur.execute(
                    "UPDATE users SET pending_email = NULL, email_code_hash = NULL, email_code_expires_at = NULL "
                    "WHERE telegram_id = ?",
                    (int(user_id),),
                )
                conn.commit()
                return False, "Этот email уже используется другим аккаунтом"

            cur.execute(
                """
                UPDATE users
                SET auth_email = ?, pending_email = NULL, email_verified = 1,
                    email_code_hash = NULL, email_code_expires_at = NULL
                WHERE telegram_id = ?
                """,
                (pending, int(user_id)),
            )
            conn.commit()
            return True, pending
    except sqlite3.IntegrityError:
        return False, "Этот email уже используется другим аккаунтом"
    except Exception as e:
        logger.error(f"Failed to finalize pending email change for user {user_id}: {e}")
        return False, "Ошибка базы данных"


def get_webapp_settings() -> dict:
    """Вернуть настройки Telegram Mini App (webapp) из общей таблицы bot_settings.

    Ключи:
      webapp_enabled  - "true"/"false", включён ли Mini App
      webapp_domain   - домен, на котором развёрнут Mini App
      webapp_title    - заголовок (fallback на panel_brand_title в handlers.py)
      webapp_logo     - URL логотипа (по умолчанию берётся логотип проекта img/obla.png,
                         отдаваемый через /static или отдельный роут в webapp/handlers.py)
      webapp_icon     - favicon/apple-touch-icon
      tg_fullscreen   - "true"/"false", полноэкранный режим в Telegram
    """
    keys = ["webapp_enabled", "webapp_domain", "webapp_title", "webapp_logo", "webapp_icon", "tg_fullscreen"]
    result: dict[str, Any] = {}
    for key in keys:
        try:
            value = get_setting(key)
        except Exception:
            value = None
        if key in ("webapp_enabled", "tg_fullscreen"):
            result[key] = str(value).lower() == "true" if value is not None else False
        else:
            result[key] = value or ""
    return result
