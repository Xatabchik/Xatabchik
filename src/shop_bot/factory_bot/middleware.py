
import time
from aiogram import BaseMiddleware
from typing import Any, Awaitable, Callable, Dict
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, TelegramObject

from shop_bot.data_manager import remnawave_repository as rw_repo

_FRANCHISE_ENABLED_CACHE: dict[str, Any] = {"value": None, "ts": 0.0}
_FRANCHISE_ENABLED_TTL_SEC = 2.0


def invalidate_franchise_enabled_cache() -> None:
    _FRANCHISE_ENABLED_CACHE["value"] = None
    _FRANCHISE_ENABLED_CACHE["ts"] = 0.0


def franchise_enabled_cached() -> bool:
    """Лёгкий кэш флага франшизы, чтобы middleware не ходила в SQL на каждое сообщение."""
    now = time.monotonic()
    cached = _FRANCHISE_ENABLED_CACHE.get("value")
    ts = float(_FRANCHISE_ENABLED_CACHE.get("ts") or 0.0)
    if cached is not None and (now - ts) < _FRANCHISE_ENABLED_TTL_SEC:
        return bool(cached)
    try:
        raw = rw_repo.get_setting("franchise_enabled") or "false"
        val = str(raw).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        val = False
    _FRANCHISE_ENABLED_CACHE["value"] = val
    _FRANCHISE_ENABLED_CACHE["ts"] = now
    return val


def _markup_has_callback(markup: InlineKeyboardMarkup | None, callback_data: str) -> bool:
    if not markup:
        return False
    for row in markup.inline_keyboard or []:
        for btn in row:
            if getattr(btn, "callback_data", None) == callback_data:
                return True
    return False


def with_delete_self_button(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    if _markup_has_callback(markup, "factory_del_self"):
        return markup or InlineKeyboardMarkup(inline_keyboard=[])
    extra = [InlineKeyboardButton(text="🗑 Удалить моего бота", callback_data="factory_del_self")]
    rows = [list(row) for row in (markup.inline_keyboard if markup else [])]
    insert_at = None
    for i, row in enumerate(rows):
        if any(getattr(btn, "callback_data", None) == "partner_withdraw" for btn in row):
            insert_at = i + 1
            break
    if insert_at is None:
        insert_at = len(rows)
        if rows:
            last_cbs = [getattr(btn, "callback_data", None) for btn in rows[-1]]
            last_text = " ".join(getattr(btn, "text", "") or "" for btn in rows[-1])
            if "back_to_main_menu" in last_cbs or last_text.startswith("⬅️"):
                insert_at = len(rows) - 1
    rows.insert(insert_at, extra)
    return InlineKeyboardMarkup(inline_keyboard=rows)


class FactoryStatsMiddleware(BaseMiddleware):
    """Tracks basic stats (messages + unique users) per factory bot instance."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not franchise_enabled_cached():
            return await handler(event, data)

        token = None
        try:
            bot = data.get("bot")
            event_from = data.get("event_from_user")
            if bot and event_from:
                bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
                rw_repo.record_factory_activity(bot_id, event_from.id)
                data["factory_bot_id"] = bot_id
                token = rw_repo.set_current_factory_bot_id(bot_id)
        except Exception:
            token = None

        try:
            return await handler(event, data)
        finally:
            if token is not None:
                try:
                    rw_repo.reset_current_factory_bot_id(token)
                except Exception:
                    pass


class OwnerCabinetEnhanceMiddleware(BaseMiddleware):
    """Добавляет кнопку удаления текущего клона в живой partner_cabinet."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        result = await handler(event, data)
        try:
            if not isinstance(event, CallbackQuery):
                return result
            if getattr(event, "data", None) != "partner_cabinet":
                return result
            if not event.from_user or not event.message:
                return result
            bot = data.get("bot")
            bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None) if bot else None)
            if int(bot_id or 0) <= 0:
                return result
            info = rw_repo.get_managed_bot(bot_id) or {}
            owner_id = int(info.get("owner_telegram_id") or 0)
            if int(event.from_user.id) != owner_id:
                return result
            markup = event.message.reply_markup
            new_markup = with_delete_self_button(markup)
            if new_markup is markup:
                return result
            await event.message.edit_reply_markup(reply_markup=new_markup)
        except Exception:
            pass
        return result
