
from aiogram import BaseMiddleware
from typing import Any, Awaitable, Callable, Dict
from aiogram.types import TelegramObject

from shop_bot.data_manager import remnawave_repository as rw_repo

class FactoryStatsMiddleware(BaseMiddleware):
    """Tracks basic stats (messages + unique users) per factory bot instance."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
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
