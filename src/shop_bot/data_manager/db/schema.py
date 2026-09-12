"""Создание и миграции схемы БД: initialize_db, run_migration и помощники
добавления таблиц, колонок и индексов.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
from typing import Any

__all__ = (
    "_ensure_table_column",
    "_ensure_index",
    "initialize_db",
    "_ensure_users_columns",
    "_ensure_email_verification_columns",
    "_ensure_hosts_columns",
    "_ensure_plans_columns",
    "_ensure_traffic_packages_table",
    "_ensure_key_node_usage_snapshots_table",
    "_ensure_subscription_lte_table",
    "_ensure_key_lte_state_table",
    "_migrate_subscription_lte_to_keys",
    "_ensure_host_squads_table",
    "_ensure_support_tickets_columns",
    "_ensure_key_usage_monitor_columns",
    "_rebuild_vpn_keys_table",
    "_ensure_vpn_keys_schema",
    "_migrate_gift_tags",
    "run_migration",
    "_ensure_ssh_known_hosts_table",
    "_ensure_gift_tokens_table",
    "_ensure_user_gifts_table",
    "_ensure_auth_pending_actions_table",
    "_ensure_promo_tables",
    "_ensure_analytics_tables",
    "_ensure_pending_tables",
    "_ensure_processed_payments_table",
    "_backfill_encrypt_secrets_at_rest",
)


def _ensure_table_column(cursor: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    columns = _get_table_columns(cursor, table)
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_index(cursor: sqlite3.Cursor, name: str, table: str, column: str) -> None:
    cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({column})")


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
                "rollypay_api_key": None,
                "rollypay_terminal_id": None,
                "rollypay_signing_secret": None,
                "rollypay_payment_method": "",

                "domain": None,
                "ton_wallet_address": None,
                "tonapi_key": None,
                "support_forum_chat_id": None,
                "ticket_auto_close_days": "0",
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
                "franchise_menu_button_visible": "false",
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
    try:
        _backfill_encrypt_secrets_at_rest()
    except Exception:
        logging.warning("Backfill encrypt secrets at rest завершился с ошибкой.", exc_info=True)


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
        # Результат последней проверки пересечения нод LTE- и base-сквадов хоста (JSON-список).
        # Хранится, чтобы карточки хоста в боте и веб-панели показывали предупреждение без
        # обращения к панели на каждый рендер.
        "squad_node_overlap": "TEXT",
        "squad_node_overlap_checked_at": "TIMESTAMP",
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


def _ensure_key_node_usage_snapshots_table(cursor: sqlite3.Cursor) -> None:
    """Расход ключа по КОНКРЕТНЫМ нодам за расчётный период.

    Ни `key_usage_monitor` (PK key_id, одно поле last_traffic_bytes), ни `subscription_lte`
    (одна строка на пользователя) не могут хранить разбивку по нодам, поэтому нужна
    отдельная таблица. `period_start` согласован с расчётным периодом ключа
    (`vpn_keys.next_traffic_reset_at`, см. resolve_key_period_start).
    """
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS key_node_usage_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id INTEGER NOT NULL,
            node_uuid TEXT NOT NULL,
            node_name TEXT,
            host_name TEXT NOT NULL,
            used_bytes INTEGER NOT NULL DEFAULT 0,
            period_start TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(key_id, node_uuid, period_start)
        )
        '''
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_key_node_usage_key_period "
        "ON key_node_usage_snapshots(key_id, period_start)"
    )


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
    # Отметка о том, что точка отсчёта (baseline) уже определена. Нужна, чтобы отличить
    # "baseline = 0, потому что подписка новая и расход считается с нуля" от "baseline
    # никогда не выставлялся" (строки, созданные до появления этого механизма): во втором
    # случае накопительный расход панели мгновенно исчерпал бы LTE-лимит после обновления
    # бота. Строки, существовавшие до миграции, остаются с NULL и получают одноразовый
    # backfill в воркере; новые строки помечаются сразу при вставке (см. get_lte_state).
    _ensure_table_column(cursor, "subscription_lte", "lte_baseline_initialized_at", "TIMESTAMP")


def _ensure_key_lte_state_table(cursor: sqlite3.Cursor) -> None:
    """Состояние LTE-пула НА КЛЮЧ (пришло на смену пользовательскому `subscription_lte`).

    LTE-лимит задаётся тарифом конкретного ключа (`plans.lte_limit_bytes`), а расход
    считается по нодам LTE-сквада хоста этого ключа, поэтому и остаток, и докупленный
    буст, и точка отсчёта обязаны жить на ключе. Пользовательская модель сворачивала
    несколько ключей с разными тарифами в одну строку.
    """
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS key_lte_state (
            key_id INTEGER PRIMARY KEY,
            lte_limit_bytes INTEGER DEFAULT 0,
            lte_used_bytes INTEGER DEFAULT 0,
            lte_boost_bytes INTEGER DEFAULT 0,
            lte_used_baseline_bytes INTEGER DEFAULT 0,
            lte_baseline_reset_requested INTEGER DEFAULT 0,
            lte_baseline_initialized_at TIMESTAMP,
            lte_reset_at TIMESTAMP,
            premium_state TEXT DEFAULT 'enabled',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )
    _migrate_subscription_lte_to_keys(cursor)


def _migrate_subscription_lte_to_keys(cursor: sqlite3.Cursor) -> None:
    """Перенести пользовательское состояние LTE на ключи (однократно для каждой строки).

    Раскладка состояния пользователя по его LTE-ключам:
      * ключ ровно один — переносим состояние 1:1, ничего не теряя и не выдавая заново;
      * ключей несколько — оплаченный буст делится поровну (остаток первому ключу), чтобы
        суммарно у пользователя осталось ровно столько оплаченного трафика, сколько он
        купил, а точка отсчёта у каждого ключа определяется заново на первом проходе
        воркера (общий baseline пользователя нельзя скопировать в каждый ключ — он бы
        вычитался многократно). Такие случаи логируются: разложение неоднозначно.

    Идемпотентность — через отметку `subscription_lte.migrated_to_keys_at`: без неё
    ключ, созданный уже после миграции, при следующем старте получил бы чужой буст.
    """
    try:
        _ensure_table_column(cursor, "subscription_lte", "migrated_to_keys_at", "TIMESTAMP")
        cursor.execute(
            "SELECT * FROM subscription_lte WHERE migrated_to_keys_at IS NULL"
        )
        columns = [c[0] for c in cursor.description]
        rows = [dict(zip(columns, r)) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.warning(f"Миграция subscription_lte -> key_lte_state пропущена: {e}")
        return

    now = _now_str()
    for row in rows:
        user_id = row.get("user_id")
        try:
            cursor.execute(
                """
                SELECT k.key_id
                FROM vpn_keys k
                JOIN host_squads hs
                  ON TRIM(hs.host_name) = TRIM(k.host_name) COLLATE NOCASE
                 AND hs.squad_class = 'lte' AND hs.is_active = 1
                WHERE k.user_id = ?
                ORDER BY k.key_id
                """,
                (user_id,),
            )
            key_ids = [int(r[0]) for r in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.warning(f"Миграция LTE-состояния user_id={user_id}: не удалось найти ключи: {e}")
            continue

        if not key_ids:
            # Переносить некуда (нет ключей на хостах с LTE-сквадом) — строку не трогаем,
            # чтобы состояние не потерялось, если сквад настроят позже.
            continue

        boost_total = int(row.get("lte_boost_bytes") or 0)
        single = len(key_ids) == 1
        if single:
            shares = [boost_total]
        else:
            per_key = boost_total // len(key_ids)
            shares = [per_key] * len(key_ids)
            shares[0] += boost_total - per_key * len(key_ids)
            if boost_total > 0:
                logging.warning(
                    "Миграция LTE-состояния user_id=%s: у пользователя %s LTE-ключей, "
                    "докупленный буст %s байт разделён поровну %s — при необходимости "
                    "перераспределите вручную в key_lte_state.",
                    user_id, len(key_ids), boost_total, shares,
                )

        for key_id, boost_share in zip(key_ids, shares):
            try:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO key_lte_state (
                        key_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes,
                        lte_used_baseline_bytes, lte_baseline_reset_requested,
                        lte_baseline_initialized_at, lte_reset_at, premium_state, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key_id,
                        int(row.get("lte_limit_bytes") or 0),
                        int(row.get("lte_used_bytes") or 0) if single else 0,
                        int(boost_share),
                        int(row.get("lte_used_baseline_bytes") or 0) if single else 0,
                        int(row.get("lte_baseline_reset_requested") or 0),
                        row.get("lte_baseline_initialized_at") if single else None,
                        row.get("lte_reset_at"),
                        row.get("premium_state") or "enabled",
                        now,
                    ),
                )
            except sqlite3.Error as e:
                logging.warning(f"Миграция LTE-состояния key_id={key_id}: {e}")

        try:
            cursor.execute(
                "UPDATE subscription_lte SET migrated_to_keys_at = ? WHERE user_id = ?",
                (now, user_id),
            )
            logging.info(
                "Миграция LTE-состояния: user_id=%s -> ключи %s", user_id, key_ids
            )
        except sqlite3.Error as e:
            logging.warning(f"Миграция LTE-состояния user_id={user_id}: не удалось отметить строку: {e}")


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

    # Миграция: переносим существующий xui_hosts.squad_uuid в host_squads, если для этого
    # хоста ещё нет ни одной записи. Класс определяем по node_class хоста: у 💰-premium ноды
    # единственный сквад и есть LTE-сквад, и раньше он ошибочно переносился как 'base' —
    # из-за чего вся LTE-логика (докупка, энфорсинг) считала ноду ненастроенной.
    try:
        cursor.execute(
            "SELECT host_name, squad_uuid, COALESCE(node_class, 'unlim') "
            "FROM xui_hosts WHERE squad_uuid IS NOT NULL AND TRIM(squad_uuid) <> ''"
        )
        legacy_rows = cursor.fetchall()
        for host_name, squad_uuid, node_class in legacy_rows:
            host_name_n = normalize_host_name(host_name)
            squad_uuid_n = (squad_uuid or '').strip()
            if not host_name_n or not squad_uuid_n:
                continue
            cursor.execute(
                "SELECT 1 FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (host_name_n,),
            )
            if cursor.fetchone() is not None:
                continue
            is_premium = str(node_class or '').strip().lower() == 'premium'
            squad_class_legacy = 'lte' if is_premium else 'base'
            label_legacy = 'LTE (legacy)' if is_premium else 'Base (legacy)'
            cursor.execute(
                "INSERT OR IGNORE INTO host_squads (host_name, squad_uuid, squad_class, label, is_active) "
                "VALUES (?, ?, ?, ?, 1)",
                (host_name_n, squad_uuid_n, squad_class_legacy, label_legacy),
            )
    except sqlite3.Error as e:
        logging.warning(f"Не удалось мигрировать legacy squad_uuid хостов в host_squads: {e}")

    # Доп. миграция для инсталляций, где перенос выше уже отработал в предыдущей версии и
    # записал premium-ноду как 'base'. Переклассифицируем только автоматически созданные
    # записи ('Base (legacy)') у premium-хостов, у которых ровно один сквад и ещё нет lte —
    # чтобы не затронуть привязки, которые администратор задал руками.
    try:
        cursor.execute(
            """
            UPDATE host_squads
               SET squad_class = 'lte', label = 'LTE (legacy)'
             WHERE squad_class = 'base'
               AND label = 'Base (legacy)'
               AND TRIM(host_name) IN (
                     SELECT TRIM(host_name) FROM xui_hosts
                      WHERE LOWER(COALESCE(node_class, 'unlim')) = 'premium'
                   )
               AND (
                     SELECT COUNT(*) FROM host_squads hs2
                      WHERE TRIM(hs2.host_name) = TRIM(host_squads.host_name) COLLATE NOCASE
                   ) = 1
            """
        )
        if cursor.rowcount:
            logging.info(
                "host_squads: %s legacy-сквад(ов) premium-хостов переклассифицированы как 'lte'",
                cursor.rowcount,
            )
    except sqlite3.Error as e:
        logging.warning(f"Не удалось переклассифицировать legacy-сквады premium-хостов: {e}")


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
            _ensure_ssh_known_hosts_table(cursor)
            _ensure_gift_tokens_table(cursor)
            _ensure_user_gifts_table(cursor)
            _ensure_promo_tables(cursor)
            _ensure_traffic_packages_table(cursor)
            _ensure_subscription_lte_table(cursor)
            _ensure_key_node_usage_snapshots_table(cursor)
            _ensure_host_squads_table(cursor)
            # После host_squads: миграция состояния LTE на ключи опирается на привязку
            # хостов к LTE-сквадам, чтобы понять, каким ключам это состояние принадлежит.
            _ensure_key_lte_state_table(cursor)
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
        return
    try:
        backfill_monthly_traffic_reset_for_existing_keys()
    except Exception:
        logging.warning("Backfill monthly traffic reset завершился с ошибкой.", exc_info=True)
    try:
        _backfill_encrypt_secrets_at_rest()
    except Exception:
        logging.warning("Backfill encrypt secrets at rest завершился с ошибкой.", exc_info=True)


def _ensure_ssh_known_hosts_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ssh_known_hosts (
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            key_type TEXT,
            key_base64 TEXT NOT NULL,
            PRIMARY KEY (host, port)
        )
        """
    )


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


def _backfill_encrypt_secrets_at_rest() -> None:
    """Зашифровать уже сохранённые plaintext-секреты (settings / hosts / SSH-цели)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT key, value FROM bot_settings WHERE key IN ({})".format(
                        ",".join("?" * len(SECRET_SETTING_KEYS))
                    ),
                    tuple(SECRET_SETTING_KEYS),
                )
                for key, value in cursor.fetchall():
                    raw = (value or "").strip()
                    if raw and not raw.startswith(MANAGED_BOT_TOKEN_PREFIX):
                        cursor.execute(
                            "UPDATE bot_settings SET value = ? WHERE key = ?",
                            (encrypt_managed_bot_token(raw), key),
                        )
            except sqlite3.Error:
                pass
            try:
                cursor.execute("SELECT host_name, ssh_password, remnawave_api_token FROM xui_hosts")
                for host_name, ssh_password, api_token in cursor.fetchall():
                    sets: list[str] = []
                    params: list[Any] = []
                    if ssh_password and not str(ssh_password).startswith(MANAGED_BOT_TOKEN_PREFIX):
                        sets.append("ssh_password = ?")
                        params.append(encrypt_managed_bot_token(str(ssh_password)))
                    if api_token and not str(api_token).startswith(MANAGED_BOT_TOKEN_PREFIX):
                        sets.append("remnawave_api_token = ?")
                        params.append(encrypt_managed_bot_token(str(api_token)))
                    if sets:
                        params.append(host_name)
                        cursor.execute(
                            f"UPDATE xui_hosts SET {', '.join(sets)} WHERE host_name = ?",
                            params,
                        )
            except sqlite3.Error:
                pass
            try:
                cursor.execute("SELECT target_name, ssh_password FROM speedtest_ssh_targets")
                for target_name, ssh_password in cursor.fetchall():
                    if ssh_password and not str(ssh_password).startswith(MANAGED_BOT_TOKEN_PREFIX):
                        cursor.execute(
                            "UPDATE speedtest_ssh_targets SET ssh_password = ? WHERE target_name = ?",
                            (encrypt_managed_bot_token(str(ssh_password)), target_name),
                        )
            except sqlite3.Error:
                pass
            conn.commit()
    except sqlite3.Error as e:
        logging.warning("Не удалось выполнить backfill шифрования секретов: %s", e)
