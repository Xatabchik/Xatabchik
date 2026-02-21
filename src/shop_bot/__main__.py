import logging
import threading
import asyncio
import signal
import re
import os
try:

    import colorama
    colorama_available = True
except Exception:
    colorama_available = False

from shop_bot.webhook_server.app import create_webhook_app
from shop_bot.webhook_server import app as webhook_app
from shop_bot.data_manager.scheduler import periodic_subscription_check
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.bot_controller import BotController

def main():
    if colorama_available:
        try:
            colorama.just_fix_windows_console()
        except Exception:
            pass

    class ColoredFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': '\x1b[36m',
            'INFO': '\x1b[32m',
            'WARNING': '\x1b[33m',
            'ERROR': '\x1b[31m',
            'CRITICAL': '\x1b[41m',
        }
        RESET = '\x1b[0m'

        def format(self, record: logging.LogRecord) -> str:
            level = record.levelname
            color = self.COLORS.get(level, '')
            reset = self.RESET if color else ''

            fmt = f"%(asctime)s [%(levelname)s] %(message)s"

            datefmt = "%H:%M:%S"
            base = logging.Formatter(fmt=fmt, datefmt=datefmt)
            msg = base.format(record)
            if color:

                msg = msg.replace(f"[{level}]", f"{color}[{level}]{reset}")
            return msg

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for h in list(root.handlers):
        root.removeHandler(h)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(ColoredFormatter())
    root.addHandler(ch)


    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    aio_event_logger = logging.getLogger('aiogram.event')
    aio_event_logger.setLevel(logging.INFO)
    logging.getLogger('aiogram.dispatcher').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('paramiko').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    class RussianizeAiogramFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                msg = record.getMessage()
                if 'Update id=' in msg:


                    m = re.search(r"Update id=(\d+)\s+is\s+(not handled|handled)\.\s+Duration\s+(\d+)\s+ms\s+by bot id=(\d+)", msg)
                    if m:
                        upd_id, state, dur_ms, bot_id = m.groups()
                        state_ru = 'не обработано' if state == 'not handled' else 'обработано'
                        msg = f"Обновление {upd_id} {state_ru} за {dur_ms} мс (бот {bot_id})"
                        record.msg = msg
                        record.args = ()
                    else:

                        msg = msg.replace('Update id=', 'Обновление ')
                        msg = msg.replace(' is handled.', ' обработано.')
                        msg = msg.replace(' is not handled.', ' не обработано.')
                        msg = msg.replace('Duration', 'за')
                        msg = msg.replace('by bot id=', '(бот ')
                        if msg.endswith(')') is False and 'бот ' in msg:
                            msg = msg + ')'
                        record.msg = msg
                        record.args = ()
            except Exception:
                pass
            return True


    aio_event_logger.addFilter(RussianizeAiogramFilter())
    logger = logging.getLogger(__name__)

    logger.info("Инициализация базы данных...")
    rw_repo.initialize_db()
    logger.info("Инициализация базы данных завершена.")

    bot_controller = BotController()
    flask_app = create_webhook_app(bot_controller)

    def _is_true(value) -> bool:
        return str(value).strip().lower() in ("true", "1", "on", "yes", "y")
    
    async def shutdown(sig: signal.Signals, loop: asyncio.AbstractEventLoop):
        logger.info(f"Получен сигнал: {sig.name}. Запускаю завершение работы...")
        if bot_controller.get_status()["is_running"]:
            bot_controller.stop()
            await asyncio.sleep(2)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            [task.cancel() for task in tasks]
            await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    async def start_services():
        loop = asyncio.get_running_loop()
        bot_controller.set_loop(loop)
        flask_app.config['EVENT_LOOP'] = loop
        try:
            webhook_app._support_bot_controller.set_loop(loop)
        except Exception:
            pass
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda sig=sig: asyncio.create_task(shutdown(sig, loop)))
        
        flask_port = int(os.getenv('SHOPBOT_FLASK_PORT', '1488'))
        flask_thread = threading.Thread(
            target=lambda: flask_app.run(host='0.0.0.0', port=flask_port, use_reloader=False, debug=False),
            daemon=True
        )
        flask_thread.start()
        
        logger.info(f"Flask-сервер запущен: http://0.0.0.0:{flask_port}")
            
        logger.info("Приложение запущено. Бота можно стартовать из веб-панели.")
        
        try:
            auto_main = _is_true(rw_repo.get_setting("auto_start_main_bot") or "false")
            auto_support = _is_true(rw_repo.get_setting("auto_start_support_bot") or "false")

            token = (rw_repo.get_setting("telegram_bot_token") or "").strip()
            bot_username = (rw_repo.get_setting("telegram_bot_username") or "").strip()
            admin_id_raw = (rw_repo.get_setting("admin_telegram_id") or "").strip()
            try:
                admin_id_ok = int(admin_id_raw) > 0
            except Exception:
                admin_id_ok = False
            main_ready = bool(token and bot_username and admin_id_ok)

            support_token = (rw_repo.get_setting("support_bot_token") or "").strip()
            support_username = (rw_repo.get_setting("support_bot_username") or "").strip()
            try:
                admin_ids = rw_repo.get_admin_ids()
            except Exception:
                admin_ids = set()
            support_ready = bool(support_token and support_username and admin_ids)

            if auto_main and main_ready:
                res = bot_controller.start()
                logger.info("Автозапуск основного бота: %s", res.get("message"))
            elif auto_main:
                logger.warning("Автозапуск основного бота пропущен: не хватает настроек.")

            if auto_support and support_ready:
                res = webhook_app._support_bot_controller.start()
                logger.info("Автозапуск support-бота: %s", res.get("message"))
            elif auto_support:
                logger.warning("Автозапуск support-бота пропущен: не хватает настроек.")
        except Exception as e:
            logger.warning("Не удалось выполнить автозапуск ботов: %s", e)

        asyncio.create_task(periodic_subscription_check(bot_controller))


        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:

            logger.info("Главная задача отменена, выполняю корректное завершение...")
            return

    try:
        asyncio.run(start_services())
    except asyncio.CancelledError:

        logger.info("Получен сигнал остановки, сервисы остановлены.")
    finally:
        logger.info("Приложение завершается.")

if __name__ == "__main__":
    main()
