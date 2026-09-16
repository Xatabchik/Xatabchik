"""Состояние уровня модуля и лимитеры Mini App.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


import threading
from collections import deque
from slowapi import Limiter
from slowapi.util import get_remote_address
import re
import logging

# Имя логгера прибито строкой, а не взято из __name__: после разделения
# записи в логах должны остаться от 'shop_bot.webapp.handlers'.
logger = logging.getLogger("shop_bot.webapp.handlers")

TEMP_AUTH_TOKENS = {}

TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = 10 * 60

limiter = Limiter(key_func=get_remote_address, default_limits=[])
AUTH_RATE_LIMIT = "30/minute"
SUPPORT_RATE_LIMIT = "30/minute"
SUPPORT_TEXT_MAX_LEN = 2000
SUPPORT_CAPTION_MAX_LEN = 500
SUPPORT_MAX_MESSAGES_PER_TICKET = 200
SUPPORT_CREATE_DAILY_MAX = 8
SUPPORT_SEND_PER_MINUTE = 20
SUPPORT_UPLOAD_PER_MINUTE = 8
SUPPORT_CREATE_PER_HOUR = 5
SUPPORT_MIN_INTERVAL_SECONDS = 1.5
_SUPPORT_HITS: dict[str, deque[float]] = {}
_SUPPORT_LAST: dict[str, float] = {}
_SUPPORT_HITS_LOCK = threading.Lock()

EMAIL_AUTH_PER_EMAIL_LIMIT = 30
EMAIL_AUTH_PER_EMAIL_WINDOW_SECONDS = 60.0
_EMAIL_AUTH_HITS: dict[str, deque[float]] = {}
_EMAIL_AUTH_HITS_LOCK = threading.Lock()

PASSWORD_RESET_TOKENS = {}
PASSWORD_RESET_TTL_SECONDS = 600

EMAIL_RESEND_COOLDOWN_SECONDS = 60
EMAIL_CODE_TTL_SECONDS = 600

# Совпадает с database.normalize_auth_email: без < > " ' ` и управляющих.
_EMAIL_FORMAT_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9._%+-]{0,62}[a-z0-9])?@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$",
    re.IGNORECASE,
)

_REFERRAL_LINK_MESSAGES = {
    "linked": "Вы стали участником реферальной программы!",
    "already_linked": "У вас уже был указан реферер — эта ссылка ничего не меняет.",
    "self_referral_forbidden": "Нельзя быть рефералом самого себя.",
    "invalid_referrer": "Реферальная ссылка недействительна.",
    "not_eligible": "Не удалось применить реферальную ссылку.",
}

_PUBLIC_FALLBACK_CSP = (
    "default-src 'none'; "
    "img-src 'self' https: data:; "
    "style-src 'unsafe-inline'; "
    "script-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'"
)

# Этап 1: CSP на Mini App / login / banned. Inline JS и <style> ещё в HTML,
# поэтому script-src/style-src временно с 'unsafe-inline'. Tailwind CDN и
# Google Fonts убраны — font-src только 'self'. Telegram SDK не вендорим.
# web.telegram.org открывает Mini App в iframe — frame-ancestors не 'none'.
_WEBAPP_PAGE_CSP = (
    "default-src 'self'; "
    "script-src 'self' https://telegram.org 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "img-src 'self' https: data:; "
    "connect-src 'self' https://telegram.org https://web.telegram.org; "
    "frame-src 'self' https://telegram.org https://web.telegram.org; "
    "frame-ancestors 'self' https://web.telegram.org https://k.telegram.org; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)
_GIFT_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "logger",
    "TEMP_AUTH_TOKENS",
    "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS",
    "limiter",
    "AUTH_RATE_LIMIT",
    "SUPPORT_RATE_LIMIT",
    "SUPPORT_TEXT_MAX_LEN",
    "SUPPORT_CAPTION_MAX_LEN",
    "SUPPORT_MAX_MESSAGES_PER_TICKET",
    "SUPPORT_CREATE_DAILY_MAX",
    "SUPPORT_SEND_PER_MINUTE",
    "SUPPORT_UPLOAD_PER_MINUTE",
    "SUPPORT_CREATE_PER_HOUR",
    "SUPPORT_MIN_INTERVAL_SECONDS",
    "_SUPPORT_HITS",
    "_SUPPORT_LAST",
    "_SUPPORT_HITS_LOCK",
    "EMAIL_AUTH_PER_EMAIL_LIMIT",
    "EMAIL_AUTH_PER_EMAIL_WINDOW_SECONDS",
    "_EMAIL_AUTH_HITS",
    "_EMAIL_AUTH_HITS_LOCK",
    "PASSWORD_RESET_TOKENS",
    "PASSWORD_RESET_TTL_SECONDS",
    "EMAIL_RESEND_COOLDOWN_SECONDS",
    "EMAIL_CODE_TTL_SECONDS",
    "_EMAIL_FORMAT_RE",
    "_REFERRAL_LINK_MESSAGES",
    "_PUBLIC_FALLBACK_CSP",
    "_WEBAPP_PAGE_CSP",
    "_GIFT_CODE_RE",
]
