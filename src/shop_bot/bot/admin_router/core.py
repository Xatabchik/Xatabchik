"""Общие определения админки: состояния FSM, фильтр доступа, middleware, хелперы.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import logging
import html as html_escape
import hashlib
from typing import Any, Awaitable, Callable, Dict

from aiogram import types, BaseMiddleware
from aiogram.filters import BaseFilter
from aiogram.fsm.state import State, StatesGroup

from shop_bot.data_manager.remnawave_repository import (
    get_all_ssh_targets,
    is_admin,
)


# Имя логгера прибито строкой, а не взято из __name__: после разделения
# записи в логах должны остаться от 'shop_bot.bot.admin_handlers'.
logger = logging.getLogger("shop_bot.bot.admin_handlers")


def _is_true(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "on", "yes", "y")


def _mask_secret(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return "—"
    if len(v) <= 6:
        return "•" * len(v)
    return f"{v[:2]}•••{v[-2:]}"


class AdminSettings(StatesGroup):
    waiting_for_captcha_attempts = State()
    waiting_for_captcha_timeout = State()
    waiting_for_captcha_message = State()


class AdminModules(StatesGroup):
    browsing = State()


class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_parse_mode = State()
    waiting_for_button_option = State()
    waiting_for_button_type = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_action_select = State()
    waiting_for_confirmation = State()


class IsAdminFilter(BaseFilter):
    """Router-level gate for admin_router (aiogram 3.x BaseFilter).

    Only telegram_ids from admin_telegram_id / admin_telegram_ids pass.
    """

    async def __call__(
        self,
        event: types.TelegramObject,
        event_from_user: types.User | None = None,
    ) -> bool:
        user = event_from_user or getattr(event, "from_user", None)
        if user is None:
            return False
        try:
            return bool(is_admin(user.id))
        except Exception:
            return False


class AdminAccessMiddleware(BaseMiddleware):
    """When a non-admin hits admin_router, answer the callback the same way
    existing handlers do (`У вас нет прав.`) instead of leaving Telegram spinning.
    Messages are ignored silently (same as a failed router filter).
    """

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        uid = getattr(user, "id", None)
        try:
            allowed = bool(uid is not None and is_admin(uid))
        except Exception:
            allowed = False
        if not allowed:
            if isinstance(event, types.CallbackQuery):
                try:
                    await event.answer("У вас нет прав.", show_alert=True)
                except Exception:
                    pass
            return None
        return await handler(event, data)


def _format_user_mention(u: types.User) -> str:
    try:
        if u.username:
            uname = u.username.lstrip('@')
            return f"@{uname}"

        full_name = (u.full_name or u.first_name or "Администратор").strip()

        try:
            safe_name = html_escape.escape(full_name)
        except Exception:
            safe_name = full_name
        return f"<a href='tg://user?id={u.id}'>{safe_name}</a>"
    except Exception:
        return str(getattr(u, 'id', '—'))


def _resolve_target_from_hash(cb_data: str) -> str | None:
    try:
        digest = cb_data.split(':', 1)[1]
    except Exception:
        return None
    try:
        targets = get_all_ssh_targets() or []
    except Exception:
        targets = []
    for t in targets:
        name = t.get('target_name')
        try:
            h = hashlib.sha1((name or '').encode('utf-8', 'ignore')).hexdigest()
        except Exception:
            h = hashlib.sha1(str(name).encode('utf-8', 'ignore')).hexdigest()
        if h == digest:
            return name
    return None


# __all__ — имена, которые пакет раскладывает по остальным модулям (см. __init__.py).
__all__ = [
    "_is_true",
    "_mask_secret",
    "AdminSettings",
    "AdminModules",
    "Broadcast",
    "IsAdminFilter",
    "AdminAccessMiddleware",
    "logger",
    "_format_user_mention",
    "_resolve_target_from_hash",
]
