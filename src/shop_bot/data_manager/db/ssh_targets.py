"""SSH-цели для удалённого управления серверами.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
from typing import Any

__all__ = (
    "_ensure_ssh_targets_table",
    "get_all_ssh_targets",
    "get_ssh_target",
    "create_ssh_target",
    "update_ssh_target_fields",
    "delete_ssh_target",
)


def _ensure_ssh_targets_table(cursor: sqlite3.Cursor) -> None:
    """Миграция: создать таблицу speedtest_ssh_targets при необходимости и добавить недостающие столбцы."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS speedtest_ssh_targets (
            target_name TEXT PRIMARY KEY,
            ssh_host TEXT NOT NULL,
            ssh_port INTEGER DEFAULT 22,
            ssh_user TEXT,
            ssh_password TEXT,
            ssh_key_path TEXT,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)

    extras = {
        "ssh_host": "TEXT",
        "ssh_port": "INTEGER",
        "ssh_user": "TEXT",
        "ssh_password": "TEXT",
        "ssh_key_path": "TEXT",
        "description": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "sort_order": "INTEGER DEFAULT 0",
        "metadata": "TEXT",
    }
    for column, definition in extras.items():
        _ensure_table_column(cursor, "speedtest_ssh_targets", column, definition)


def get_all_ssh_targets() -> list[dict]:
    """Вернуть все SSH-цели для спидтестов (включая неактивные), сортировка по sort_order, затем по имени."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM speedtest_ssh_targets ORDER BY sort_order ASC, target_name ASC")
            rows = cursor.fetchall()
            return [_decrypt_row_secrets(dict(r), "ssh_password") for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить список SSH-целей: {e}")
        return []


def get_ssh_target(target_name: str) -> dict | None:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM speedtest_ssh_targets WHERE TRIM(target_name) = TRIM(?)", (name,))
            row = cursor.fetchone()
            return _decrypt_row_secrets(dict(row) if row else None, "ssh_password")
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить SSH-цель '{target_name}': {e}")
        return None


def create_ssh_target(
    target_name: str,
    ssh_host: str,
    ssh_port: int | None = 22,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
    ssh_key_path: str | None = None,
    description: str | None = None,
    *,
    sort_order: int | None = 0,
    is_active: int | None = 1,
) -> bool:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO speedtest_ssh_targets
                    (target_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path, description, is_active, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    (ssh_host or '').strip(),
                    int(ssh_port) if ssh_port is not None else None,
                    (ssh_user or None),
                    (encrypt_managed_bot_token(str(ssh_password)) if ssh_password else None),
                    (ssh_key_path or None),
                    (description or None),
                    1 if (is_active is None or int(is_active) != 0) else 0,
                    int(sort_order or 0),
                )
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось создать SSH-цель '{target_name}': {e}")
        return False


def update_ssh_target_fields(
    target_name: str,
    *,
    ssh_host: str | None = None,
    ssh_port: int | None = None,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
    ssh_key_path: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
    is_active: int | None = None,
) -> bool:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM speedtest_ssh_targets WHERE TRIM(target_name) = TRIM(?)", (name,))
            if cursor.fetchone() is None:
                logging.warning(f"update_ssh_target_fields: цель не найдена '{name}'")
                return False
            sets: list[str] = []
            params: list[Any] = []
            if ssh_host is not None:
                sets.append("ssh_host = ?")
                params.append((ssh_host or '').strip())
            if ssh_port is not None:
                try:
                    val = int(ssh_port)
                except Exception:
                    val = None
                sets.append("ssh_port = ?")
                params.append(val)
            if ssh_user is not None:
                sets.append("ssh_user = ?")
                params.append(ssh_user or None)
            if ssh_password is not None:
                stored_pw = encrypt_managed_bot_token(str(ssh_password)) if str(ssh_password).strip() else None
                sets.append("ssh_password = ?")
                params.append(stored_pw)
            if ssh_key_path is not None:
                sets.append("ssh_key_path = ?")
                params.append(ssh_key_path or None)
            if description is not None:
                sets.append("description = ?")
                params.append(description or None)
            if sort_order is not None:
                try:
                    so = int(sort_order)
                except Exception:
                    so = 0
                sets.append("sort_order = ?")
                params.append(so)
            if is_active is not None:
                sets.append("is_active = ?")
                params.append(1 if int(is_active) != 0 else 0)
            if not sets:
                return True
            params.append(name)
            sql = f"UPDATE speedtest_ssh_targets SET {', '.join(sets)} WHERE TRIM(target_name) = TRIM(?)"
            cursor.execute(sql, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить SSH-цель '{target_name}': {e}")
        return False


def delete_ssh_target(target_name: str) -> bool:
    try:
        name = normalize_host_name(target_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM speedtest_ssh_targets WHERE TRIM(target_name) = TRIM(?)", (name,))
            affected = cursor.rowcount
            conn.commit()
            return affected > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось удалить SSH-цель '{target_name}': {e}")
        return False
