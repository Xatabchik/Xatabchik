"""Ссылки для приглашений и подарков плюс тексты для кнопки «Поделиться».
"""

from urllib.parse import (
    urlencode,
    quote,
)
from shop_bot.data_manager.remnawave_repository import get_setting
from shop_bot.data_manager import database

__all__ = [
    "_webapp_public_base",
    "_build_gift_links",
    "_build_referral_links",
    "DEFAULT_REFERRAL_SHARE_TEXT",
    "DEFAULT_GIFT_SHARE_TEXT",
    "_referral_share_text",
    "_gift_share_text",
    "_telegram_share_url",
]

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
