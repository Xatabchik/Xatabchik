
import time
from aiogram import BaseMiddleware
from typing import Any, Awaitable, Callable, Dict
from aiogram.types import TelegramObject

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
