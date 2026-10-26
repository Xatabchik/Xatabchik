"""Замок записи ключа, журнал применённых продлений и оповещения админов (PR-A).

Всё состояние лежит в SQLite (`users.db`): бот, вебхуки и webapp работают в разных
процессах и контейнерах с общим bind mount, поэтому `asyncio.Lock` не подходит.

Таблицы:

* `key_write_locks`   — замок на пару «хост + email», TTL защищает от упавшего владельца;
* `key_extension_applied` — источник истины «продление по этому payment_id применено»
  (`started` записывается до PATCH в панель, `done` после ответа);
* `ops_alerts`        — очередь оповещений админам, читается планировщиком.

Режимы (настройки, по умолчанию `off`):

* `key_write_lock_scope`: `off | payments | all`;
* `key_extension_delta_scope`: `off | payments`.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

LOCK_TTL_SECONDS = 300.0
LOCK_WAIT_SECONDS = 360.0
LOCK_POLL_SECONDS = 0.25
EXTENSION_RETENTION_DAYS = 90

LOCK_SCOPE_SETTING = "key_write_lock_scope"
DELTA_SCOPE_SETTING = "key_extension_delta_scope"
LOCK_SCOPES = ("off", "payments", "all")
DELTA_SCOPES = ("off", "payments")

LOCK_TIMEOUT_MARKER = "KEY_WRITE_LOCK_TIMEOUT"

BOOT_ID = uuid.uuid4().hex[:12]
BOOT_TS = time.time()

# Записи в панель, которые идут прямо сейчас в этом процессе. При остановке службы
# `wait_inflight` даёт им завершиться до отмены задач (см. __main__.shutdown).
_inflight_cond = threading.Condition()
_inflight_count = 0
_shutting_down = False


@contextlib.contextmanager
def track_inflight():
    global _inflight_count
    with _inflight_cond:
        _inflight_count += 1
    try:
        yield
    finally:
        with _inflight_cond:
            _inflight_count -= 1
            _inflight_cond.notify_all()


def inflight_count() -> int:
    with _inflight_cond:
        return _inflight_count


def request_shutdown() -> None:
    """Попросить фоновые циклы не начинать новую работу (автопродление, сверка)."""
    global _shutting_down
    _shutting_down = True


def is_shutting_down() -> bool:
    return _shutting_down


def wait_inflight(timeout: float = 30.0) -> bool:
    """Дождаться завершения текущих записей в панель. True, если все завершились."""
    deadline = time.monotonic() + max(0.0, timeout)
    with _inflight_cond:
        while _inflight_count > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            _inflight_cond.wait(remaining)
    return True


def _service_name() -> str:
    return (os.getenv("SHOPBOT_SERVICE_NAME") or os.getenv("HOSTNAME") or "shopbot").strip() or "shopbot"


def new_owner() -> str:
    """Владелец замка: `<служба>:<boot_id>:<случайная часть>`."""
    return f"{_service_name()}:{BOOT_ID}:{uuid.uuid4().hex[:12]}"


def _database():
    from shop_bot.data_manager import database

    return database


@contextlib.contextmanager
def _conn():
    conn = _database()._connect_pending_db()
    try:
        ensure_tables(conn.cursor())
        yield conn
    finally:
        conn.close()


def ensure_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS key_write_locks (
            lock_key TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS key_extension_applied (
            payment_id TEXT PRIMARY KEY,
            lock_key TEXT NOT NULL,
            state TEXT NOT NULL,
            target_ms INTEGER NOT NULL,
            created_at REAL NOT NULL,
            source TEXT,
            days INTEGER
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_key_extension_applied_lock ON key_extension_applied(lock_key, state)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_alerts (
            id INTEGER PRIMARY KEY,
            kind TEXT,
            text TEXT,
            created_at REAL,
            sent INTEGER DEFAULT 0
        )
        """
    )


def _retry(work):
    return _database()._retry_sqlite(work)


def _normalized_scope(raw: Any, allowed: tuple[str, ...]) -> str:
    value = str(raw or "").strip().lower()
    return value if value in allowed else "off"


def get_lock_scope() -> str:
    try:
        return _normalized_scope(_database().get_setting(LOCK_SCOPE_SETTING), LOCK_SCOPES)
    except Exception:
        return "off"


def get_delta_scope() -> str:
    try:
        return _normalized_scope(_database().get_setting(DELTA_SCOPE_SETTING), DELTA_SCOPES)
    except Exception:
        return "off"


def make_lock_key(host_name: str, normalized_email: str) -> str:
    return f"{(host_name or '').strip()}|{(normalized_email or '').strip().lower()}"


def try_acquire_lock(lock_key: str, owner: str, ttl: float = LOCK_TTL_SECONDS, now: float | None = None) -> bool:
    """Захватить замок: INSERT OR IGNORE, затем перехват просроченного замка."""
    ts = time.time() if now is None else float(now)

    def _work() -> bool:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO key_write_locks (lock_key, owner, expires_at) VALUES (?, ?, ?)",
                (lock_key, owner, ts + ttl),
            )
            if cur.rowcount == 1:
                return True
            cur.execute(
                "UPDATE key_write_locks SET owner = ?, expires_at = ? WHERE lock_key = ? AND expires_at < ?",
                (owner, ts + ttl, lock_key, ts),
            )
            return cur.rowcount == 1

    return bool(_retry(_work))


def release_lock(lock_key: str, owner: str) -> bool:
    """Освободить замок только если он всё ещё наш."""

    def _work() -> bool:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM key_write_locks WHERE lock_key = ? AND owner = ?", (lock_key, owner))
            return cur.rowcount == 1

    try:
        return bool(_retry(_work))
    except sqlite3.Error as exc:
        logger.warning("key_write_guard: не удалось освободить замок %s: %s", lock_key, exc)
        return False


def clear_stale_locks_of_service(service_prefix: str | None = None) -> int:
    """При старте службы удалить замки её прошлых запусков (свой префикс, чужой boot_id)."""
    prefix = f"{service_prefix or _service_name()}:"

    def _work() -> int:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM key_write_locks WHERE owner LIKE ? AND owner NOT LIKE ?",
                (prefix + "%", f"{prefix}{BOOT_ID}:%"),
            )
            return cur.rowcount

    try:
        return int(_retry(_work) or 0)
    except sqlite3.Error as exc:
        logger.warning("key_write_guard: очистка замков прошлого запуска не удалась: %s", exc)
        return 0


class LockResult:
    """Итог попытки захвата замка. `acquired=False` значит «выполняем без замка»."""

    __slots__ = ("lock_key", "owner", "acquired", "reason")

    def __init__(self, lock_key: str, owner: str, acquired: bool, reason: str = ""):
        self.lock_key = lock_key
        self.owner = owner
        self.acquired = acquired
        self.reason = reason


async def acquire_lock(
    lock_key: str,
    *,
    owner: str | None = None,
    wait: float = LOCK_WAIT_SECONDS,
    ttl: float = LOCK_TTL_SECONDS,
    poll: float = LOCK_POLL_SECONDS,
    context: str = "",
) -> LockResult:
    """Ждать замок до `wait` секунд. По таймауту: лог, оповещение, продолжение без замка.

    Платёж к этому моменту уже принят, поэтому отказывать в выдаче нельзя: защита не
    сработала, но об этом узнают по метке KEY_WRITE_LOCK_TIMEOUT в логе и по `ops_alerts`.
    """
    own = owner or new_owner()
    deadline = time.monotonic() + max(0.0, wait)
    while True:
        try:
            if await asyncio.to_thread(try_acquire_lock, lock_key, own, ttl):
                return LockResult(lock_key, own, True)
        except sqlite3.Error as exc:
            logger.error("%s: ошибка БД при захвате замка %s (%s), выполняю без замка: %s", LOCK_TIMEOUT_MARKER, lock_key, context, exc)
            return LockResult(lock_key, own, False, "db_error")
        if time.monotonic() >= deadline:
            break
        await asyncio.sleep(poll)
    text = f"Не дождался замка записи ключа {lock_key} за {int(wait)} с ({context}); выполняю без замка."
    logger.error("%s: %s", LOCK_TIMEOUT_MARKER, text)
    try:
        await asyncio.to_thread(add_ops_alert, "key_write_lock_timeout", text)
    except Exception:
        logger.exception("key_write_guard: не удалось записать ops_alert о таймауте замка")
    return LockResult(lock_key, own, False, "timeout")


async def release_lock_async(result: LockResult) -> None:
    if not result.acquired:
        return
    await asyncio.to_thread(release_lock, result.lock_key, result.owner)


# --- журнал применённых продлений -------------------------------------------------

def extension_get(payment_id: str) -> dict | None:
    def _work():
        with _conn() as conn:
            row = conn.execute(
                "SELECT payment_id, lock_key, state, target_ms, created_at, source, days "
                "FROM key_extension_applied WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()
            return dict(row) if row else None

    return _retry(_work)


def extension_start(payment_id: str, lock_key: str, target_ms: int, source: str | None, days: int | None) -> None:
    def _work():
        with _conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO key_extension_applied "
                "(payment_id, lock_key, state, target_ms, created_at, source, days) "
                "VALUES (?, ?, 'started', ?, ?, ?, ?)",
                (payment_id, lock_key, int(target_ms), time.time(), source, days),
            )

    _retry(_work)


def extension_done(payment_id: str, target_ms: int) -> None:
    def _work():
        with _conn() as conn:
            conn.execute(
                "UPDATE key_extension_applied SET state = 'done', target_ms = ? WHERE payment_id = ?",
                (int(target_ms), payment_id),
            )

    _retry(_work)


def extension_delete(payment_id: str) -> None:
    def _work():
        with _conn() as conn:
            conn.execute("DELETE FROM key_extension_applied WHERE payment_id = ?", (payment_id,))

    _retry(_work)


def extensions_started_for_lock(lock_key: str, exclude_payment_id: str | None = None) -> list[dict]:
    def _work():
        with _conn() as conn:
            rows = conn.execute(
                "SELECT payment_id, lock_key, state, target_ms, created_at, source, days "
                "FROM key_extension_applied WHERE lock_key = ? AND state = 'started' AND payment_id <> ?",
                (lock_key, exclude_payment_id or ""),
            ).fetchall()
            return [dict(r) for r in rows]

    return _retry(_work)


def extension_has_record(payment_id: str) -> bool:
    try:
        return extension_get(payment_id) is not None
    except sqlite3.Error:
        return False


def cleanup_old_extensions(days: int = EXTENSION_RETENTION_DAYS, now: float | None = None) -> int:
    cutoff = (time.time() if now is None else now) - days * 86400

    def _work():
        with _conn() as conn:
            cur = conn.execute(
                "DELETE FROM key_extension_applied WHERE state = 'done' AND created_at < ?", (cutoff,)
            )
            return cur.rowcount

    return int(_retry(_work) or 0)


def label_transaction_extension(payment_id: str, info: dict) -> None:
    """Необязательная метка для людей. Сверка на неё не опирается; сбой не важен."""
    try:
        def _work():
            with _conn() as conn:
                conn.execute(
                    "UPDATE transactions SET metadata = json_set(COALESCE(NULLIF(metadata, ''), '{}'), '$.extension', json(?)) "
                    "WHERE payment_id = ?",
                    (json.dumps(info, ensure_ascii=False), payment_id),
                )

        _retry(_work)
    except Exception:
        logger.debug("key_write_guard: метка продления в transactions пропущена", exc_info=True)


# --- ops_alerts ------------------------------------------------------------------

def add_ops_alert(kind: str, text: str, *, dedupe_seconds: float = 0.0) -> int | None:
    """Добавить оповещение. С `dedupe_seconds` не дублирует такой же текст за окно."""

    def _work():
        with _conn() as conn:
            if dedupe_seconds > 0:
                row = conn.execute(
                    "SELECT 1 FROM ops_alerts WHERE kind = ? AND text = ? AND created_at > ? LIMIT 1",
                    (kind, text, time.time() - dedupe_seconds),
                ).fetchone()
                if row:
                    return None
            cur = conn.execute(
                "INSERT INTO ops_alerts (kind, text, created_at, sent) VALUES (?, ?, ?, 0)",
                (kind, text, time.time()),
            )
            return cur.lastrowid

    return _retry(_work)


def fetch_unsent_alerts(limit: int = 20) -> list[dict]:
    def _work():
        with _conn() as conn:
            rows = conn.execute(
                "SELECT id, kind, text, created_at FROM ops_alerts WHERE sent = 0 ORDER BY id LIMIT ?",
                (int(limit),),
            ).fetchall()
            return [dict(r) for r in rows]

    return _retry(_work)


def mark_alerts_sent(ids: list[int]) -> None:
    if not ids:
        return

    def _work():
        with _conn() as conn:
            conn.executemany("UPDATE ops_alerts SET sent = 1 WHERE id = ?", [(int(i),) for i in ids])

    _retry(_work)


def check_wal_mode() -> str | None:
    """Вернуть текущий journal_mode; при значении не WAL пишет предупреждение в лог."""
    try:
        with _conn() as conn:
            mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    except Exception as exc:
        logger.warning("key_write_guard: не удалось проверить journal_mode: %s", exc)
        return None
    if mode != "wal":
        logger.warning(
            "SQLite journal_mode=%s, ожидается wal: замки в БД и конкурентная запись работают "
            "корректно только на обычной локальной файловой системе Linux.",
            mode,
        )
    return mode
