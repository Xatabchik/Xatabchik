"""Инфраструктура доступа к БД: путь к файлу, логгер, retry, помощники дат/JSON,
чтение и запись settings и шифрование токена управляемого бота.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
import os

__all__ = (
    "logger",
    "_UNSET",
    "DB_FILE",
    "_now_str",
    "add_calendar_months",
    "add_months",
    "_to_datetime_str",
    "_normalize_email",
    "_get_table_columns",
    "_ensure_unique_index",
    "_decrypt_row_secrets",
    "_SUCCESS_TX_SQL",
    "_NON_BALANCE_SQL",
    "_REAL_MONEY_SQL",
    "EMAIL_ONLY_TELEGRAM_ID_MIN",
    "EMAIL_ONLY_TELEGRAM_ID_MAX",
    "SECRET_SETTING_KEYS",
    "get_setting",
    "_retry_sqlite",
    "get_all_settings",
    "update_setting",
    "_parse_json_metadata",
    "UNREACHABLE_REASON_BLOCKED",
    "UNREACHABLE_REASON_DEACTIVATED",
    "resolve_db_file_path",
    "MANAGED_BOT_TOKEN_PREFIX",
    "_managed_bot_token_secret",
    "encrypt_managed_bot_token",
    "decrypt_managed_bot_token",
    "get_msk_time",
    "get_webapp_settings",
)


# Имя логгера задано строкой, а не через __name__: записи в логах должны
# остаться от 'shop_bot.data_manager.database', как до разделения файла.
logger = logging.getLogger("shop_bot.data_manager.database")


_UNSET = object()


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


def _get_table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _ensure_unique_index(cursor: sqlite3.Cursor, name: str, table: str, column: str) -> None:
    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table}({column})")

def _decrypt_row_secrets(row: dict | None, *fields: str) -> dict | None:
    """Расшифровать at-rest поля (enc1$ / legacy plaintext) в копии строки."""
    if not row:
        return row
    data = dict(row)
    for field in fields:
        if data.get(field):
            data[field] = decrypt_managed_bot_token(str(data[field]))
    return data


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


# Псевдо-telegram_id для email-аккаунтов без привязки к Telegram
# (см. create_user_by_email). В этот диапазон бот писать не может.
EMAIL_ONLY_TELEGRAM_ID_MIN = 999000000000
EMAIL_ONLY_TELEGRAM_ID_MAX = 999999999999

# Секреты в bot_settings, которые хранятся at-rest тем же enc1$ HMAC-XOR,
# что и токены клонов (encrypt_managed_bot_token / decrypt_managed_bot_token).
SECRET_SETTING_KEYS = frozenset({
    "yookassa_secret_key",
    "cryptobot_token",
    "heleket_api_key",
    "tonapi_key",
    "remnawave_api_token",
    "rollypay_api_key",
    "rollypay_signing_secret",
})


def get_setting(key: str) -> str | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            value = result[0] if result else None
            if value is not None and key in SECRET_SETTING_KEYS:
                return decrypt_managed_bot_token(str(value))
            return value
    except sqlite3.Error as e:
        logging.error(f"Failed to get setting '{key}': {e}")
        return None


def _retry_sqlite(work, attempts: int = 5, base_sleep: float = 0.05):
    for i in range(attempts):
        try:
            return work()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(base_sleep * (2 ** i))
                continue
            raise

def get_all_settings() -> dict:
    settings = {}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM bot_settings")
            rows = cursor.fetchall()
            for row in rows:
                val = row['value']
                if val is not None and row['key'] in SECRET_SETTING_KEYS:
                    val = decrypt_managed_bot_token(str(val))
                settings[row['key']] = val
    except sqlite3.Error as e:
        logging.error(f"Failed to get all settings: {e}")
    return settings

def update_setting(key: str, value: str):
    try:
        stored = value
        if key in SECRET_SETTING_KEYS:
            stored = encrypt_managed_bot_token("" if value is None else str(value))
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)", (key, stored))
            conn.commit()
            logging.info(f"Setting '{key}' updated.")
    except sqlite3.Error as e:
        logging.error(f"Failed to update setting '{key}': {e}")


def _parse_json_metadata(raw: str | None) -> dict:
    try:
        if not raw:
            return {}
        return json.loads(raw)
    except Exception:
        return {}


# ── Недоступность пользователя в Telegram (заблокировал бота / деактивировал аккаунт) ──
#
# Позволяет автоматически исключать таких пользователей из будущих рассылок
# (см. shop_bot.modules.telegram_reachability, вызывается из всех мест массовой
# отправки сообщений) и вести статистику по реальному количеству подписчиков.

UNREACHABLE_REASON_BLOCKED = "blocked"
UNREACHABLE_REASON_DEACTIVATED = "deactivated"


def resolve_db_file_path(db_file=None) -> Path:
    """Абсолютный путь к users.db без зависимости от cwd процесса.

    ``os.path.abspath("users.db")`` берёт текущую папку процесса. Бот с
    cwd=/xatabchik пишет в /xatabchik/ticket_files, а если Flask когда-то
    стартовал из webhook_server — панель искала файлы там. Админка живёт
    в src/shop_bot/webhook_server/, вложения — рядом с базой, не в исходниках.
    """
    raw = Path(db_file if db_file is not None else DB_FILE)
    if raw.is_absolute():
        return raw.resolve()
    name = raw.name
    docker_db = Path("/app/project") / name
    if docker_db.is_file():
        return docker_db.resolve()
    # database.py → src/shop_bot/data_manager → корень репозитория
    return (Path(__file__).resolve().parents[3] / name).resolve()


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


# =============================================================
# WEBAPP (Telegram Mini App) support functions
# =============================================================

def get_msk_time() -> datetime:
    """Текущее время в московской зоне (UTC+3), используется для расчётов сроков в webapp."""
    from datetime import timezone as _tz
    return datetime.now(_tz.utc).astimezone(_tz(timedelta(hours=3)))


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
