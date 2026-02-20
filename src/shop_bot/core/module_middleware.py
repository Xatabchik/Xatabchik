from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Iterable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, CallbackQuery

from shop_bot.data_manager import database

logger = logging.getLogger(__name__)


class ModuleSafeMiddleware(BaseMiddleware):
    """Catches module handler errors and marks the module as failed."""

    def __init__(self, module_id: str, module_loader: Any):
        self._module_id = module_id
        self._module_loader = module_loader

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            if not self._is_allowed_callback(event):
                return None
        try:
            return await handler(event, data)
        except Exception as exc:
            logger.error(
                "Module handler error (%s): %s",
                self._module_id,
                exc,
                exc_info=True,
            )
            try:
                self._module_loader.set_module_error(self._module_id, str(exc))
            except Exception:
                pass
            await self._notify_admins(event, exc)
            return None

    def _is_allowed_callback(self, event: CallbackQuery) -> bool:
        try:
            data = (event.data or "").strip()
        except Exception:
            data = ""
        if not data:
            return False
        allowed_prefixes = (f"{self._module_id}:", f"mod:{self._module_id}:")
        return data.startswith(allowed_prefixes)

    async def _notify_admins(self, event: TelegramObject, exc: Exception) -> None:
        bot = getattr(event, "bot", None)
        if not bot:
            return
        try:
            admin_ids = database.get_admin_ids() or set()
        except Exception:
            admin_ids = set()
        if not admin_ids:
            return
        text = (
            "⚠️ Ошибка в модуле: <b>{module}</b>\n"
            "Причина: <code>{error}</code>"
        ).format(module=self._module_id, error=str(exc)[:180])
        for admin_id in admin_ids:
            try:
                await bot.send_message(int(admin_id), text)
            except Exception:
                continue
