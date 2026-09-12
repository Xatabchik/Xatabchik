import asyncio
import logging
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

from . import remnawave_repository as rw_repo

logger = logging.getLogger(__name__)


BACKUPS_DIR = Path("/app/project/backups")
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


DB_FILE: Path = rw_repo.DB_FILE


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_backup_file() -> Path | None:
    """
    Создаёт zip-архив с консистентной копией SQLite-БД.
    Возвращает путь к архиву или None при ошибке.
    """
    try:
        if not DB_FILE.exists():
            logger.error(f"Бэкап: файл БД не найден: {DB_FILE}")
            return None
        ts = _timestamp()
        tmp_db_copy = BACKUPS_DIR / f"users-{ts}.db"
        zip_path = BACKUPS_DIR / f"db-backup-{ts}.zip"


        with sqlite3.connect(DB_FILE) as src:
            with sqlite3.connect(tmp_db_copy) as dst:
                src.backup(dst)


        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_db_copy, arcname=tmp_db_copy.name)


        try:
            tmp_db_copy.unlink(missing_ok=True)
        except Exception:
            pass

        logger.info(f"Бэкап: создан файл {zip_path}")
        return zip_path
    except Exception as e:
        logger.error(f"Бэкап: не удалось создать архив: {e}", exc_info=True)
        return None


def cleanup_old_backups(keep: int = 7) -> None:
    """Хранить только N последних архивов, остальные удалять."""
    try:
        files = sorted(BACKUPS_DIR.glob("db-backup-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        for f in files[keep:]:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Бэкап: не удалось очистить старые архивы: {e}")


def _is_ssl_shutdown_timeout(exc: BaseException) -> bool:
    """aiohttp часто рвёт уже завершённый upload на SSL close_notify."""
    parts = [str(exc)]
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        parts.append(str(cause))
    text = " ".join(parts).lower()
    return "ssl shutdown timed out" in text


async def _upload_bot(source_bot: Bot, timeout: float) -> tuple[Bot, bool]:
    """Отдельная HTTP-сессия, чтобы долгий upload не портил polling."""
    token = getattr(source_bot, "token", None)
    if not token:
        return source_bot, False
    try:
        import inspect

        from aiohttp import TCPConnector
        from aiogram.client.session.aiohttp import AiohttpSession

        session = AiohttpSession(timeout=float(timeout), limit=2)
        session._connector_init["force_close"] = True
        if "ssl_shutdown_timeout" in inspect.signature(TCPConnector.__init__).parameters:
            session._connector_init["ssl_shutdown_timeout"] = 0
        return Bot(token=token, session=session), True
    except Exception as e:
        logger.warning(f"Бэкап: не удалось создать отдельную сессию отправки: {e}")
        return source_bot, False


async def send_backup_to_admins(bot: Bot, zip_path: Path, request_timeout: int = 180, max_attempts: int = 3) -> int:
    """
    Отправляет архив всем администраторам. Возвращает число успешных отправок.

    Загрузка большого файла может занимать больше времени, чем стандартный
    таймаут HTTP-клиента aiogram, поэтому здесь используется увеличенный
    request_timeout и несколько попыток с задержкой при сетевых сбоях.
    """
    cnt = 0
    upload_bot, owns_session = await _upload_bot(bot, request_timeout)
    try:
        try:
            admin_ids = list(rw_repo.get_admin_ids() or [])
        except Exception:
            admin_ids = []
        if not admin_ids:
            logger.warning("Бэкап: нет администраторов для отправки архива")
            return 0
        caption = f"🗄 Бэкап БД: {zip_path.name}"
        for uid in admin_ids:
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    file = FSInputFile(str(zip_path))
                    await upload_bot.send_document(
                        chat_id=int(uid),
                        document=file,
                        caption=caption,
                        request_timeout=request_timeout,
                    )
                    cnt += 1
                    last_error = None
                    break
                except TelegramRetryAfter as e:
                    last_error = e
                    wait_s = getattr(e, "retry_after", 5) or 5
                    logger.warning(
                        f"Бэкап: администратор {uid} — flood control, ждём {wait_s}с (попытка {attempt}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_s)
                except (TelegramNetworkError, TimeoutError, asyncio.TimeoutError, OSError) as e:
                    if _is_ssl_shutdown_timeout(e):
                        logger.warning(
                            f"Бэкап: SSL shutdown timeout после отправки администратору {uid}; "
                            "файл, скорее всего, уже доставлен — повтор не делаем."
                        )
                        cnt += 1
                        last_error = None
                        break
                    last_error = e
                    logger.warning(
                        f"Бэкап: тайм-аут/сетевая ошибка при отправке администратору {uid} "
                        f"(попытка {attempt}/{max_attempts}): {e}"
                    )
                    if attempt < max_attempts:
                        await asyncio.sleep(3 * attempt)
                except Exception as e:
                    last_error = e
                    logger.error(f"Бэкап: не удалось отправить администратору {uid}: {e}")
                    break
            if last_error is not None:
                logger.error(
                    f"Бэкап: не удалось отправить администратору {uid} после {max_attempts} попыток: {last_error}"
                )
        return cnt
    except Exception as e:
        logger.error(f"Бэкап: ошибка при рассылке архива: {e}", exc_info=True)
        return cnt
    finally:
        if owns_session:
            try:
                await upload_bot.session.close()
            except Exception:
                pass



def validate_db_file(db_path: Path) -> bool:
    """
    Простая валидация файла БД: доступность основных таблиц.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()

            required_tables = {
                'users', 'vpn_keys', 'transactions', 'bot_settings', 'xui_hosts'
            }
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            present = {row[0] for row in cur.fetchall()}
            missing = required_tables - present
            if missing:
                logger.warning(f"Восстановление: в загруженной БД отсутствуют таблицы: {missing}")

            return 'users' in present and 'bot_settings' in present
    except Exception as e:
        logger.error(f"Восстановление: ошибка валидации файла БД: {e}")
        return False


def restore_from_file(uploaded_path: Path) -> bool:
    """
    Восстанавливает основную БД из переданного файла .db или .zip (внутри .db).
    Делает резервную копию текущей БД на случай отката.
    """
    try:
        if not uploaded_path.exists():
            logger.error(f"Восстановление: файл не найден: {uploaded_path}")
            return False


        tmp_dir = BACKUPS_DIR / f"restore-{_timestamp()}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        candidate_db: Path | None = None

        if uploaded_path.suffix.lower() == '.zip':
            try:
                with zipfile.ZipFile(uploaded_path, 'r') as zf:
                    for n in zf.namelist():
                        if n.lower().endswith('.db'):
                            zf.extract(n, path=tmp_dir)
                            candidate_db = tmp_dir / n
                            break
            except Exception as e:
                logger.error(f"Восстановление: не удалось распаковать архив: {e}")
                return False
        else:

            candidate_db = uploaded_path

        if not candidate_db or not candidate_db.exists():
            logger.error("Восстановление: в переданном файле не найдено .db")
            return False


        if not validate_db_file(candidate_db):
            logger.error("Восстановление: файл БД не прошёл проверку")
            return False


        backup_before = BACKUPS_DIR / f"before-restore-{_timestamp()}.zip"
        cur_backup = create_backup_file()
        if cur_backup and cur_backup.exists():
            try:
                shutil.copy(cur_backup, backup_before)
            except Exception:
                pass


        with sqlite3.connect(candidate_db) as src:
            with sqlite3.connect(DB_FILE) as dst:
                src.backup(dst)
        

        try:
            rw_repo.run_migration()
        except Exception:
            pass

        logger.info("Восстановление: база данных успешно заменена")
        return True
    except Exception as e:
        logger.error(f"Восстановление: ошибка: {e}", exc_info=True)
        return False
