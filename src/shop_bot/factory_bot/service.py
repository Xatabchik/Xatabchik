
import asyncio
import logging
from typing import Dict

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramUnauthorizedError

from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.bot.handlers import get_user_router
from shop_bot.bot.middlewares import BanMiddleware
from .handlers import get_factory_router
from .middleware import FactoryStatsMiddleware, OwnerCabinetEnhanceMiddleware

logger = logging.getLogger(__name__)


class ManagedBotsService:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self._tasks: Dict[int, asyncio.Task] = {}
        self._dispatchers: Dict[int, Dispatcher] = {}
        self._bots: Dict[int, Bot] = {}
        self._lock = asyncio.Lock()

    def get_bot(self, bot_id: int):
        """Возвращает экземпляр Bot для bot_id, если он запущен."""
        return self._bots.get(int(bot_id))

    def _drop_bot_refs(self, bot_id: int) -> None:
        self._tasks.pop(bot_id, None)
        self._dispatchers.pop(bot_id, None)
        self._bots.pop(bot_id, None)

    def _has_running_task(self, bot_id: int) -> bool:
        task = self._tasks.get(bot_id)
        return task is not None and not task.done()

    async def start_all(self):
        bots = rw_repo.list_active_managed_bots()
        for b in bots:
            bot_id = int(b["id"])
            if self._has_running_task(bot_id):
                continue
            try:
                await self.start_bot(bot_id)
            except Exception as e:
                logger.error(f"Ошибка при запуске bot_id={bot_id}: {e}", exc_info=True)

    async def start_bot(self, bot_id: int):
        bot_id = int(bot_id)
        async with self._lock:
            if self._has_running_task(bot_id):
                return
            # Завершённый task (автоотключение / ошибка) не должен блокировать повторный старт.
            self._drop_bot_refs(bot_id)

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
            dp.message.middleware(OwnerCabinetEnhanceMiddleware())
            dp.callback_query.middleware(BanMiddleware())
            dp.callback_query.middleware(FactoryStatsMiddleware())
            dp.callback_query.middleware(OwnerCabinetEnhanceMiddleware())

            # Пользовательский роутер (магазин) + кабинет франшизы (мои боты / удаление).
            dp.include_router(get_user_router())
            dp.include_router(get_factory_router())

            async def runner():
                logger.info(f"Менеджер бота запущен: bot_id={bot_id} (@{info.get('username')})")
                try:
                    await dp.start_polling(bot, handle_signals=False)
                except asyncio.CancelledError:
                    pass
                except (TelegramUnauthorizedError, TelegramForbiddenError):
                    logger.error(f"Бот-франчайзи {bot_id} отключён: невалидный токен")
                    try:
                        rw_repo.update_managed_bot_active(bot_id, 0)
                    except Exception:
                        logger.error(
                            f"Не удалось пометить bot_id={bot_id} неактивным после ошибки токена",
                            exc_info=True,
                        )
                except Exception as e:
                    logger.error(f"Ошибка при запуске менеджера бота bot_id={bot_id}: {e}", exc_info=True)
                finally:
                    try:
                        await bot.session.close()
                    except Exception:
                        pass
                    self._drop_bot_refs(bot_id)
                    logger.info(f"Менеджер бота остановлен: bot_id={bot_id}")

            task = asyncio.create_task(runner(), name=f"managed-bot-{bot_id}")
            self._tasks[bot_id] = task
            self._dispatchers[bot_id] = dp
            self._bots[bot_id] = bot

    async def stop_bot(self, bot_id: int):
        """Остановить один клон. Идемпотентно: повторный вызов безопасен."""
        bot_id = int(bot_id)
        async with self._lock:
            dp = self._dispatchers.get(bot_id)
            task = self._tasks.get(bot_id)
            if dp is not None:
                try:
                    await dp.stop_polling()
                except Exception:
                    pass
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Ошибка при остановке bot_id={bot_id}: {e}", exc_info=True)
            self._drop_bot_refs(bot_id)

    async def restart_bot(self, bot_id: int):
        """Перезапуск клона (смена токена владельцем)."""
        await self.stop_bot(bot_id)
        await self.start_bot(bot_id)

    async def stop_all(self):
        bot_ids = list(self._tasks.keys())
        for bot_id in bot_ids:
            try:
                await self.stop_bot(bot_id)
            except Exception as e:
                logger.error(f"Ошибка при остановке bot_id={bot_id}: {e}", exc_info=True)
        self._tasks.clear()
        self._dispatchers.clear()
        self._bots.clear()
