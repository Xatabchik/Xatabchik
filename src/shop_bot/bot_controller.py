import asyncio
import logging
import threading

from yookassa import Configuration
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramServerError,
    TelegramNetworkError,
    TelegramUnauthorizedError,
    TelegramRetryAfter,
)

from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.bot.handlers import get_user_router
from shop_bot.bot.admin_handlers import get_admin_router
from shop_bot.bot.middlewares import BanMiddleware
from shop_bot.bot import handlers
from shop_bot.factory_bot.service import ManagedBotsService
from shop_bot.factory_bot.middleware import FactoryStatsMiddleware
from shop_bot.factory_bot.runtime import set_service
from shop_bot.core.module_loader import get_global_module_loader

logger = logging.getLogger(__name__)

def _is_true(value) -> bool:
    return str(value).strip().lower() in ('true','1','on','yes','y')


class BotController:
    def __init__(self):
        self._dp = None
        self._bot = None
        self._task = None
        self._is_running = False
        self._loop = None
        self._loop_thread: threading.Thread | None = None
        self._managed_service: ManagedBotsService | None = None
        self._stop_requested = False
        # Основной бот работает в собственном изолированном event loop/потоке,
        # полностью независимом от Flask и от Support-бота: сбой/зависание
        # одного бота никак не влияет на другой.
        self._start_own_loop()

    def _start_own_loop(self) -> None:
        ready = threading.Event()

        def _runner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            # Сигнализируем "готово" только когда цикл событий реально начал
            # работать (callback выполнится уже внутри run_forever()), а не
            # сразу после создания объекта loop — иначе is_running() мог бы
            # ненадолго возвращать False сразу после старта потока (гонка).
            loop.call_soon(ready.set)
            try:
                loop.run_forever()
            finally:
                loop.close()

        self._loop_thread = threading.Thread(target=_runner, daemon=True, name="main-bot-loop")
        self._loop_thread.start()
        if not ready.wait(timeout=5):
            logger.warning("Собственный цикл событий основного бота не подтвердил готовность за 5 сек.")
        logger.info("Собственный цикл событий основного бота запущен.")

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        # Оставлено для обратной совместимости со старым кодом, который мог
        # вызывать set_loop() извне. Теперь контроллер управляет собственным
        # циклом событий самостоятельно, поэтому внешний loop игнорируется.
        logger.debug("set_loop() проигнорирован: у основного бота собственный цикл событий.")

    def get_loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    def get_bot_instance(self) -> Bot | None:
        return self._bot

    async def _start_polling(self):
        self._is_running = True
        self._stop_requested = False
        logger.info("Запущен опрос Telegram (Основной-бот).")

        max_backoff = 60.0
        backoff = 2.0
        try:
            while not self._stop_requested:
                try:
                    await self._dp.start_polling(self._bot, handle_signals=False)
                    # start_polling() возвращается штатно, когда была вызвана
                    # dp.stop_polling() (т.е. пользователь остановил бота).
                    break
                except asyncio.CancelledError:
                    logger.info("Опрос остановлен (задача отменена).")
                    break
                except TelegramUnauthorizedError as e:
                    # Неверный/отозванный токен — повторные попытки бессмысленны.
                    logger.error(f"Опрос остановлен: неверный токен бота: {e}")
                    break
                except TelegramRetryAfter as e:
                    wait_for = float(getattr(e, "retry_after", backoff) or backoff)
                    logger.warning(f"Telegram просит подождать {wait_for} сек. перед повтором опроса.")
                    await asyncio.sleep(wait_for)
                except (TelegramServerError, TelegramNetworkError) as e:
                    logger.error(
                        f"Ошибка во время опроса (временная проблема на стороне Telegram/сети): {e}. "
                        f"Повтор через {backoff:.0f} сек."
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)
                    continue
                except Exception as e:
                    logger.error(f"Ошибка во время опроса: {e}", exc_info=True)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)
                    continue
                # Успешный проход без ошибок — сбрасываем backoff
                backoff = 2.0
        finally:
            logger.info("Опрос корректно остановлен.")
            self._is_running = False
            self._task = None
            # Stop managed clone bots together with the root bot
            try:
                if self._managed_service:
                    await self._managed_service.stop_all()
            except Exception:
                pass
            if self._bot:
                await self._bot.close()
            self._bot = None
            self._dp = None

    def start(self):
        if self._is_running:
            return {"status": "error", "message": "Бот уже запущен."}

        if not self._loop or not self._loop.is_running():
            # Собственный цикл событий мог не подняться при инициализации — пробуем ещё раз.
            self._start_own_loop()
        if not self._loop or not self._loop.is_running():
            return {"status": "error", "message": "Критическая ошибка: цикл событий не установлен."}

        token = rw_repo.get_setting("telegram_bot_token")
        bot_username = rw_repo.get_setting("telegram_bot_username")
        admin_id_raw = rw_repo.get_setting("admin_telegram_id")

        try:
            admin_id = int(str(admin_id_raw).strip()) if admin_id_raw is not None else None
        except Exception:
            admin_id = None

        if not all([token, bot_username, admin_id]):
            return {
                "status": "error",
                "message": "Невозможно запустить: не все обязательные настройки Telegram заполнены (токен, username, ID админа)."
            }

        try:
            self._bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            self._dp = Dispatcher()
            


            self._dp.message.middleware(BanMiddleware())
            self._dp.callback_query.middleware(BanMiddleware())

            # Franchise context + stats middleware (tracks only managed clones, bot_id>0)
            self._dp.message.middleware(FactoryStatsMiddleware())
            self._dp.callback_query.middleware(FactoryStatsMiddleware())
            
            user_router = get_user_router()
            admin_router = get_admin_router()

            if not isinstance(user_router, Router):
                raise TypeError(f"get_user_router() must return Router instance, got: {type(user_router)}")
            if not isinstance(admin_router, Router):
                raise TypeError(f"get_admin_router() must return Router instance, got: {type(admin_router)}")
            
            self._dp.include_router(user_router)
            self._dp.include_router(admin_router)

            module_loader = get_global_module_loader()
            module_loader.discover_modules()
            module_loader.set_dispatcher(self._dp)

            # Start all managed clone bots on the same event loop (only when franchise is enabled)
            try:
                if not self._managed_service:
                    self._managed_service = ManagedBotsService(self._loop)
                    set_service(self._managed_service)
                franchise_on = _is_true(rw_repo.get_setting("franchise_enabled") or "false")
                if franchise_on:
                    asyncio.run_coroutine_threadsafe(self._managed_service.start_all(), self._loop)
                else:
                    logger.info("Франшиза отключена — клоны ботов не запускаются.")
            except Exception as e:
                logger.warning(f"Не удалось запустить клоны ботов: {e}")
            
            try:
                asyncio.run_coroutine_threadsafe(self._bot.delete_webhook(drop_pending_updates=True), self._loop)
            except Exception as e:
                logger.warning(f"Не удалось удалить вебхук перед запуском опроса: {e}")

            yookassa_shop_id = rw_repo.get_setting("yookassa_shop_id")
            yookassa_secret_key = rw_repo.get_setting("yookassa_secret_key")
            yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)

            cryptobot_token = rw_repo.get_setting("cryptobot_token")
            cryptobot_enabled = bool(cryptobot_token)

            heleket_shop_id = rw_repo.get_setting("heleket_merchant_id")
            heleket_api_key = rw_repo.get_setting("heleket_api_key")
            ton_wallet_address = rw_repo.get_setting("ton_wallet_address")
            tonapi_key = rw_repo.get_setting("tonapi_key")
            tonconnect_enabled = bool(ton_wallet_address and tonapi_key)
            heleket_enabled = bool(heleket_shop_id and heleket_api_key)



            yoomoney_raw = rw_repo.get_setting("yoomoney_enabled")
            yoomoney_wallet = rw_repo.get_setting("yoomoney_wallet")
            yoomoney_secret = rw_repo.get_setting("yoomoney_secret")
            if yoomoney_raw is None:
                # Backward-compat: if flag отсутствует, считаем включенным при заполненных реквизитах
                yoomoney_enabled = bool(yoomoney_wallet and yoomoney_secret)
            else:
                yoomoney_enabled = _is_true(yoomoney_raw)


            stars_flag = _is_true(rw_repo.get_setting("stars_enabled") or 'false')
            try:
                stars_ratio_raw = rw_repo.get_setting("stars_per_rub") or '0'
                stars_ratio = float(stars_ratio_raw)
            except Exception:
                stars_ratio = 0.0
            stars_enabled = stars_flag and (stars_ratio > 0)

            if yookassa_enabled:
                Configuration.account_id = yookassa_shop_id
                Configuration.secret_key = yookassa_secret_key
            
            handlers.PAYMENT_METHODS = {
                "yookassa": yookassa_enabled,
                "heleket": heleket_enabled,
                "cryptobot": cryptobot_enabled,
                "tonconnect": tonconnect_enabled,
                "yoomoney": yoomoney_enabled,
                "stars": stars_enabled,
            }
            handlers.TELEGRAM_BOT_USERNAME = bot_username
            handlers.ADMIN_ID = admin_id

            self._task = asyncio.run_coroutine_threadsafe(self._start_polling(), self._loop)
            logger.info("Команда на запуск передана в цикл событий.")
            return {"status": "success", "message": "Команда на запуск бота отправлена."}
            
        except Exception as e:
            logger.error(f"Не удалось запустить бота: {e}", exc_info=True)
            self._bot = None
            self._dp = None
            return {"status": "error", "message": f"Ошибка при запуске: {e}"}

    def stop(self):
        if not self._is_running:
            return {"status": "error", "message": "Бот не запущен."}

        if not self._loop or not self._dp:
            return {"status": "error", "message": "Критическая ошибка: компоненты бота недоступны."}

        logger.info("Отправляю сигнал на корректную остановку...")
        self._stop_requested = True
        asyncio.run_coroutine_threadsafe(self._dp.stop_polling(), self._loop)
        
        return {"status": "success", "message": "Команда на остановку бота отправлена."}

    def get_status(self):
        return {"is_running": self._is_running}
