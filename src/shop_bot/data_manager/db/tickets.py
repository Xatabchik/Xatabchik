"""Поддержка: тикеты, сообщения, вложения и авто-закрытие.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import re
import os

__all__ = (
    "create_support_ticket",
    "get_or_create_open_ticket",
    "add_support_message",
    "update_ticket_thread_info",
    "get_ticket",
    "get_ticket_by_thread",
    "get_user_tickets",
    "get_support_message",
    "get_ticket_media_root",
    "list_closed_ticket_ids_older_than",
    "clear_support_message_media",
    "get_ticket_messages",
    "set_ticket_status",
    "update_ticket_subject",
    "_cleanup_ticket_media",
    "delete_ticket",
    "_ticket_forum_target",
    "TICKET_AUTO_CLOSE_DAYS_MAX",
    "TICKET_AUTO_CLOSE_BATCH",
    "TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER",
    "_TICKET_AUTO_CLOSE_WHOLE_RE",
    "validate_ticket_auto_close_days",
    "parse_ticket_auto_close_days",
    "get_ticket_auto_close_days",
    "find_open_tickets_idle_after_admin",
    "auto_close_idle_admin_tickets",
    "bulk_close_open_tickets",
    "bulk_delete_all_tickets",
    "cleanup_ticket_media_ids",
    "get_tickets_paginated",
    "get_open_tickets_count",
    "get_closed_tickets_count",
    "get_all_tickets_count",
)


def create_support_ticket(user_id: int, subject: str | None = None) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            try:
                cursor.execute(
                    "SELECT ticket_id FROM support_tickets WHERE user_id = ? AND status = 'open' ORDER BY updated_at DESC LIMIT 1",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return int(row[0])
            except Exception:
                pass

            cursor.execute(
                "INSERT INTO support_tickets (user_id, subject) VALUES (?, ?)",
                (user_id, subject)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to create support ticket for user {user_id}: {e}")
        return None

def get_or_create_open_ticket(user_id: int, subject: str | None = None) -> tuple[int | None, bool]:
    """Возвращает ID открытого тикета пользователя и флаг, создан ли новый.
    Если открытого тикета нет — создаёт новый и возвращает (id, True).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT ticket_id FROM support_tickets WHERE user_id = ? AND status = 'open' ORDER BY updated_at DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return int(row[0]), False

            cursor.execute(
                "INSERT INTO support_tickets (user_id, subject) VALUES (?, ?)",
                (user_id, subject)
            )
            conn.commit()
            return int(cursor.lastrowid), True
    except sqlite3.Error as e:
        logging.error(f"Failed to get_or_create_open_ticket for user {user_id}: {e}")
        return None, False

def add_support_message(ticket_id: int, sender: str, content: str, media: str | None = None) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO support_messages (ticket_id, sender, content, media) VALUES (?, ?, ?, ?)",
                (ticket_id, sender, content, media)
            )
            cursor.execute(
                "UPDATE support_tickets SET updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (ticket_id,)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to add support message to ticket {ticket_id}: {e}")
        return None

def update_ticket_thread_info(ticket_id: int, forum_chat_id: str | None, message_thread_id: int | None) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET forum_chat_id = ?, message_thread_id = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (forum_chat_id, message_thread_id, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update thread info for ticket {ticket_id}: {e}")
        return False

def get_ticket(ticket_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get ticket {ticket_id}: {e}")
        return None

def get_ticket_by_thread(forum_chat_id: str, message_thread_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM support_tickets WHERE forum_chat_id = ? AND message_thread_id = ?",
                (str(forum_chat_id), int(message_thread_id))
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get ticket by thread {forum_chat_id}/{message_thread_id}: {e}")
        return None

def get_user_tickets(user_id: int, status: str | None = None) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE user_id = ? AND status = ? ORDER BY updated_at DESC",
                    (user_id, status)
                )
            else:
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,)
                )
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get tickets for user {user_id}: {e}")
        return []

def get_support_message(message_id: int) -> dict | None:
    """Одно сообщение тикета. Нужно для отдачи вложений в панели."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM support_messages WHERE message_id = ?",
                (message_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get support message {message_id}: {e}")
        return None


def get_ticket_media_root() -> str:
    """Каталог вложений рядом с users.db, не в webhook_server/."""
    override = (os.getenv("TICKET_FILES_DIR") or "").strip()
    if override:
        return str(Path(override).expanduser().resolve())
    return str(resolve_db_file_path().parent / "ticket_files")


def list_closed_ticket_ids_older_than(cutoff) -> list[int]:
    """Закрытые тикеты с updated_at не новее cutoff (наивный ISO-текст SQLite)."""
    if hasattr(cutoff, "strftime"):
        cutoff_s = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    else:
        cutoff_s = str(cutoff)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ticket_id FROM support_tickets
                WHERE status = 'closed' AND updated_at <= ?
                """,
                (cutoff_s,),
            )
            return [int(row[0]) for row in cursor.fetchall() if row and row[0]]
    except sqlite3.Error as e:
        logging.error("Failed to list closed tickets older than %s: %s", cutoff_s, e)
        return []


def clear_support_message_media(ticket_id: int) -> int:
    """Обнуляет media у сообщений тикета после TTL/удаления файлов."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_messages SET media = NULL WHERE ticket_id = ? AND media IS NOT NULL",
                (int(ticket_id),),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
    except sqlite3.Error as e:
        logging.error("Failed to clear media refs for ticket %s: %s", ticket_id, e)
        return 0


def get_ticket_messages(ticket_id: int) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM support_messages WHERE ticket_id = ? ORDER BY created_at ASC",
                (ticket_id,)
            )
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get messages for ticket {ticket_id}: {e}")
        return []

def set_ticket_status(ticket_id: int, status: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (status, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set status '{status}' for ticket {ticket_id}: {e}")
        return False

def update_ticket_subject(ticket_id: int, subject: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET subject = ?, updated_at = CURRENT_TIMESTAMP WHERE ticket_id = ?",
                (subject, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update subject for ticket {ticket_id}: {e}")
        return False

def _cleanup_ticket_media(ticket_id: int) -> None:
    """Файлы вложений живут вне SQLite — удаляем каталог вместе с тикетом."""
    try:
        from shop_bot.support_bot.ticket_media import delete_ticket_media_dir

        delete_ticket_media_dir(ticket_id)
    except Exception as e:
        logging.error("Failed to delete ticket media for ticket %s: %s", ticket_id, e)


def delete_ticket(ticket_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM support_messages WHERE ticket_id = ?",
                (ticket_id,)
            )
            cursor.execute(
                "DELETE FROM support_tickets WHERE ticket_id = ?",
                (ticket_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            _cleanup_ticket_media(ticket_id)
        return deleted
    except sqlite3.Error as e:
        logging.error(f"Failed to delete ticket {ticket_id}: {e}")
        return False


def _ticket_forum_target(row: dict) -> dict | None:
    forum_chat_id = row.get("forum_chat_id")
    thread_id = row.get("message_thread_id")
    if not forum_chat_id or thread_id in (None, ""):
        return None
    try:
        return {
            "ticket_id": int(row["ticket_id"]),
            "user_id": row.get("user_id"),
            "forum_chat_id": forum_chat_id,
            "message_thread_id": int(thread_id),
        }
    except (TypeError, ValueError):
        return None


TICKET_AUTO_CLOSE_DAYS_MAX = 365
TICKET_AUTO_CLOSE_BATCH = 50
TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER = (
    "Автозакрытие тикета не сохранено: нужно целое число от 0 до 365."
)
_TICKET_AUTO_CLOSE_WHOLE_RE = re.compile(r"^\d+$")


def validate_ticket_auto_close_days(raw) -> tuple[int | None, str | None]:
    """Для формы настроек: только целое 0–365.

    Дроби вроде 7.5 / 7.0 не принимаем — иначе ``int("7.5")`` тихо превращал
    значение в 0 (выключено). Пустое поле = 0.
    """
    if raw is None:
        return 0, None
    try:
        s = str(raw).strip()
    except (TypeError, ValueError):
        return None, TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER
    if s == "":
        return 0, None
    if not _TICKET_AUTO_CLOSE_WHOLE_RE.fullmatch(s):
        return None, TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER
    days = int(s)
    if days > TICKET_AUTO_CLOSE_DAYS_MAX:
        return None, TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER
    return days, None


def parse_ticket_auto_close_days(raw) -> int:
    """0 — выключено. Нецелое и мусор → 0. Целое больше 365 режем потолком."""
    days, err = validate_ticket_auto_close_days(raw)
    if days is not None and err is None:
        return days
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError, AttributeError):
        return 0
    if n <= 0:
        return 0
    return min(n, TICKET_AUTO_CLOSE_DAYS_MAX)


def get_ticket_auto_close_days() -> int:
    return parse_ticket_auto_close_days(get_setting("ticket_auto_close_days"))


def find_open_tickets_idle_after_admin(
    days: int,
    *,
    now: datetime | None = None,
    limit: int = TICKET_AUTO_CLOSE_BATCH,
) -> list[dict]:
    """Открытые тикеты, где последнее сообщение — ответ админа старше ``days`` суток.

    Заметки (sender=note) и сообщения пользователя сбрасывают таймер: закрываем
    только если пользователь после ответа админа молчит.

    ``updated_at`` тоже должен быть старше порога: переоткрытие тикета без нового
    ответа админа обновляет ``updated_at`` и не должно сразу закрыть его снова.
    """
    days = parse_ticket_auto_close_days(days)
    if days <= 0:
        return []
    try:
        limit_n = int(limit)
    except (TypeError, ValueError):
        limit_n = TICKET_AUTO_CLOSE_BATCH
    if limit_n <= 0:
        return []
    moment = now or datetime.utcnow()
    cutoff_s = (moment - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.ticket_id, t.user_id, t.forum_chat_id, t.message_thread_id,
                       last.sender AS last_sender, last.created_at AS last_created_at
                FROM support_tickets t
                JOIN support_messages last
                  ON last.message_id = (
                      SELECT MAX(m.message_id)
                      FROM support_messages m
                      WHERE m.ticket_id = t.ticket_id
                  )
                WHERE t.status = 'open'
                  AND last.sender = 'admin'
                  AND last.created_at <= ?
                  AND t.updated_at <= ?
                ORDER BY last.created_at ASC, t.ticket_id ASC
                LIMIT ?
                """,
                (cutoff_s, cutoff_s, limit_n),
            )
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to find idle tickets after admin reply: %s", e)
        return []


def auto_close_idle_admin_tickets(
    days: int,
    *,
    now: datetime | None = None,
    limit: int = TICKET_AUTO_CLOSE_BATCH,
) -> dict:
    """Закрывает найденные простаивающие тикеты. Форум — снаружи.

    UPDATE ещё раз проверяет, что последнее сообщение всё ещё от админа,
    оно старше порога, и ``updated_at`` тоже старше порога: иначе ответ
    пользователя или переоткрытие между SELECT и UPDATE закрыли бы живой тикет.
    """
    days_n = parse_ticket_auto_close_days(days)
    empty = {"count": 0, "days": days_n, "forum_targets": [], "tickets": []}
    rows = find_open_tickets_idle_after_admin(days_n, now=now, limit=limit)
    if not rows:
        return empty
    ids: list[int] = []
    for row in rows:
        try:
            ids.append(int(row["ticket_id"]))
        except (TypeError, ValueError):
            continue
    if not ids:
        return empty
    moment = now or datetime.utcnow()
    cutoff_s = (moment - timedelta(days=days_n)).strftime("%Y-%m-%d %H:%M:%S")
    placeholders = ",".join("?" * len(ids))
    try:
        with sqlite3.connect(DB_FILE, timeout=15) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                UPDATE support_tickets
                SET status = 'closed', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'open'
                  AND ticket_id IN ({placeholders})
                  AND updated_at <= ?
                  AND (
                    SELECT m.sender FROM support_messages m
                    WHERE m.ticket_id = support_tickets.ticket_id
                    ORDER BY m.message_id DESC LIMIT 1
                  ) = 'admin'
                  AND (
                    SELECT m.created_at FROM support_messages m
                    WHERE m.ticket_id = support_tickets.ticket_id
                    ORDER BY m.message_id DESC LIMIT 1
                  ) <= ?
                RETURNING ticket_id, user_id, forum_chat_id, message_thread_id
                """,
                (*ids, cutoff_s, cutoff_s),
            )
            closed_rows = [dict(r) for r in cursor.fetchall()]
            conn.commit()
    except sqlite3.Error as e:
        logging.error("Failed to auto-close idle tickets: %s", e)
        return empty
    targets = [t for t in (_ticket_forum_target(r) for r in closed_rows) if t]
    return {
        "count": len(closed_rows),
        "days": days_n,
        "forum_targets": targets,
        "tickets": closed_rows,
    }


def bulk_close_open_tickets() -> dict:
    """Один UPDATE всех открытых тикетов. Форум/уведомления — на стороне вызывающего.

    Возвращает ``{"count": int, "forum_targets": list[dict]}``.
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=15) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ticket_id, user_id, forum_chat_id, message_thread_id "
                "FROM support_tickets WHERE status = 'open'"
            )
            rows = [dict(r) for r in cursor.fetchall()]
            if rows:
                cursor.execute(
                    "UPDATE support_tickets SET status = 'closed', "
                    "updated_at = CURRENT_TIMESTAMP WHERE status = 'open'"
                )
            conn.commit()
        targets = [t for t in (_ticket_forum_target(r) for r in rows) if t]
        return {"count": len(rows), "forum_targets": targets}
    except sqlite3.Error as e:
        logging.error("Failed to bulk-close open tickets: %s", e)
        return {"count": 0, "forum_targets": []}


def bulk_delete_all_tickets() -> dict:
    """Один DELETE всех тикетов и сообщений. Вложения на диске не трогает.

    Возвращает ``{"count": int, "ticket_ids": list[int], "forum_targets": list[dict]}``.
    """
    try:
        with sqlite3.connect(DB_FILE, timeout=15) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT ticket_id, user_id, forum_chat_id, message_thread_id "
                "FROM support_tickets"
            )
            rows = [dict(r) for r in cursor.fetchall()]
            if rows:
                cursor.execute("DELETE FROM support_messages")
                cursor.execute("DELETE FROM support_tickets")
            conn.commit()
        ids = []
        for r in rows:
            try:
                ids.append(int(r["ticket_id"]))
            except (TypeError, ValueError):
                continue
        targets = [t for t in (_ticket_forum_target(r) for r in rows) if t]
        return {"count": len(ids), "ticket_ids": ids, "forum_targets": targets}
    except sqlite3.Error as e:
        logging.error("Failed to bulk-delete tickets: %s", e)
        return {"count": 0, "ticket_ids": [], "forum_targets": []}


def cleanup_ticket_media_ids(ticket_ids: list[int]) -> int:
    """Удаляет каталоги вложений пачкой. Ошибки по одному id не рвут остальные."""
    cleaned = 0
    for raw in ticket_ids or []:
        try:
            tid = int(raw)
        except (TypeError, ValueError):
            continue
        try:
            _cleanup_ticket_media(tid)
            cleaned += 1
        except Exception:
            logging.exception("Failed to cleanup media for ticket %s", tid)
    return cleaned

def get_tickets_paginated(page: int = 1, per_page: int = 20, status: str | None = None) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = ?", (status,))
                total = cursor.fetchone()[0] or 0
                cursor.execute(
                    "SELECT * FROM support_tickets WHERE status = ? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (status, per_page, offset)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM support_tickets")
                total = cursor.fetchone()[0] or 0
                cursor.execute(
                    "SELECT * FROM support_tickets ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (per_page, offset)
                )
            return [dict(r) for r in cursor.fetchall()], total
    except sqlite3.Error as e:
        logging.error("Failed to get paginated support tickets: %s", e)
        return [], 0

def get_open_tickets_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error("Failed to get open tickets count: %s", e)
        return 0

def get_closed_tickets_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'closed'")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error("Failed to get closed tickets count: %s", e)
        return 0

def get_all_tickets_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM support_tickets")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error("Failed to get all tickets count: %s", e)
        return 0
