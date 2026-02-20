
import asyncio
import logging
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.bot.handlers import get_user_router
from shop_bot.bot.middlewares import BanMiddleware
from .middleware import FactoryStatsMiddleware

logger = logging.getLogger(__name__)

class ManagedBotsService:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._tasks: Dict[int, asyncio.Task] = {}
        self._dispatchers: Dict[int, Dispatcher] = {}
        self._bots: Dict[int, Bot] = {}


    def get_bot(self, bot_id: int):
        """Возвращает экземпляр Bot для bot_id, если он запущен."""
        return self._bots.get(int(bot_id))

    async def start_all(self):
        bots = rw_repo.list_active_managed_bots()
        for b in bots:
            bot_id = int(b["id"])
            if bot_id in self._tasks:
                continue
            try:
                await self.start_bot(bot_id)
            except Exception as e:
                logger.error(f"Ошибка при запуске bot_id={bot_id}: {e}", exc_info=True)

    async def start_bot(self, bot_id: int):
        bot_id = int(bot_id)
        if bot_id in self._tasks:
            return

        info = rw_repo.get_managed_bot(bot_id)
        if not info:
            return
        token = info.get("token")
        if not token:
            return

        # Каждый управляемый бот - это полноценный фронтенд shop-bot, работающий на одной backend/БД.
        # Он только добавляет UI партнерского кабинета (показывается условно) и начисляет партнерскую комиссию.
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()

        # Middleware для бана и статистики
        dp.message.middleware(BanMiddleware())
        dp.message.middleware(FactoryStatsMiddleware())
        dp.callback_query.middleware(BanMiddleware())
        dp.callback_query.middleware(FactoryStatsMiddleware())

        # Используем тот же пользовательский роутер, что и основной бот.
        dp.include_router(get_user_router())

        async def runner():
            logger.info(f"Менеджер бота запущен: bot_id={bot_id} (@{info.get('username')})")
            try:
                await dp.start_polling(bot)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Ошибка при запуске менеджера бота bot_id={bot_id}: {e}", exc_info=True)
            finally:
                try:
                    await bot.session.close()
                except Exception:
                    pass
                logger.info(f"Менеджер бота остановлен: bot_id={bot_id}")

        task = asyncio.create_task(runner(), name=f"managed-bot-{bot_id}")
        self._tasks[bot_id] = task
        self._dispatchers[bot_id] = dp
        self._bots[bot_id] = bot

    async def stop_all(self):
        for bot_id, task in list(self._tasks.items()):
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._dispatchers.clear()
        # боты закрываются в finally блоке runner
        self._bots.clear()
