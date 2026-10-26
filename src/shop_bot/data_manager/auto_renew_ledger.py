"""Журнал автопродления: запись о списании до обращения к панели (PR-A).

Идемпотентность держится на `charge_id = autorenew:<key_id>:<срок ключа в секундах>`:
пока срок ключа в БД не изменился, повторная попытка находит ту же запись и не
списывает деньги второй раз. Списание и запись делаются в одной SQLite-транзакции,
возврат и смена состояния тоже, поэтому падение процесса не оставляет деньги без записи.

Состояния записи: `charged` (деньги списаны, продление не подтверждено),
`applied` (продление применено), `refunded` (деньги возвращены).

Попытки (кулдаун) хранятся в `auto_renew_attempts`, а не в памяти процесса.
"""
from __future__ import annotations

import contextlib
import logging
import sqlite3
import time

from shop_bot.data_manager.key_write_guard import _conn, _retry

logger = logging.getLogger(__name__)

STATE_CHARGED = "charged"
STATE_APPLIED = "applied"
STATE_REFUNDED = "refunded"


def ensure_tables(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auto_renew_charges (
            charge_id TEXT PRIMARY KEY,
            key_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            host_name TEXT,
            email TEXT,
            price REAL NOT NULL,
            days INTEGER NOT NULL,
            plan_id INTEGER,
            target_ms INTEGER NOT NULL,
            state TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_auto_renew_charges_state ON auto_renew_charges(state, updated_at)"
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS auto_renew_attempts (
            key_id INTEGER PRIMARY KEY,
            last_attempt_at REAL NOT NULL
        )
        """
    )


@contextlib.contextmanager
def _ledger_conn():
    with _conn() as conn:
        ensure_tables(conn.cursor())
        yield conn


def make_charge_id(key_id: int, expire_ts_seconds: int) -> str:
    return f"autorenew:{int(key_id)}:{int(expire_ts_seconds)}"


def get_charge(charge_id: str) -> dict | None:
    def _work():
        with _ledger_conn() as conn:
            row = conn.execute("SELECT * FROM auto_renew_charges WHERE charge_id = ?", (charge_id,)).fetchone()
            return dict(row) if row else None

    return _retry(_work)


def charge(
    *,
    charge_id: str,
    key_id: int,
    user_id: int,
    host_name: str | None,
    email: str | None,
    price: float,
    days: int,
    plan_id: int | None,
    target_ms: int,
) -> str:
    """Списать деньги и записать это одной транзакцией.

    Возвращает:
    * `charged`      — списано сейчас или было списано раньше и продление не подтверждено;
    * `applied`      — по этому сроку ключа продление уже применено, ничего делать не нужно;
    * `no_balance`   — на балансе недостаточно средств.
    """
    now = time.time()

    def _work() -> str:
        with _ledger_conn() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                row = cur.execute(
                    "SELECT state FROM auto_renew_charges WHERE charge_id = ?", (charge_id,)
                ).fetchone()
                if row and row["state"] == STATE_CHARGED:
                    cur.execute("COMMIT")
                    return STATE_CHARGED
                if row and row["state"] == STATE_APPLIED:
                    cur.execute("COMMIT")
                    return STATE_APPLIED
                bal = cur.execute("SELECT balance FROM users WHERE telegram_id = ?", (int(user_id),)).fetchone()
                current = bal["balance"] if bal and bal["balance"] is not None else 0.0
                if current < price:
                    cur.execute("COMMIT")
                    return "no_balance"
                cur.execute(
                    "UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE telegram_id = ?",
                    (float(price), int(user_id)),
                )
                cur.execute(
                    """
                    INSERT INTO auto_renew_charges
                        (charge_id, key_id, user_id, host_name, email, price, days, plan_id,
                         target_ms, state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'charged', ?, ?)
                    ON CONFLICT(charge_id) DO UPDATE SET
                        price = excluded.price, days = excluded.days, plan_id = excluded.plan_id,
                        target_ms = excluded.target_ms, state = 'charged', updated_at = excluded.updated_at
                    """,
                    (charge_id, int(key_id), int(user_id), host_name, email, float(price), int(days),
                     plan_id, int(target_ms), now, now),
                )
                cur.execute("COMMIT")
                return STATE_CHARGED
            except BaseException:
                try:
                    cur.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    return str(_retry(_work))


def mark_applied(charge_id: str) -> bool:
    def _work():
        with _ledger_conn() as conn:
            cur = conn.execute(
                "UPDATE auto_renew_charges SET state = 'applied', updated_at = ? "
                "WHERE charge_id = ? AND state = 'charged'",
                (time.time(), charge_id),
            )
            return cur.rowcount == 1

    return bool(_retry(_work))


def refund(charge_id: str) -> bool:
    """Вернуть списание ровно один раз: смена состояния и баланс в одной транзакции."""

    def _work() -> bool:
        with _ledger_conn() as conn:
            cur = conn.cursor()
            cur.execute("BEGIN IMMEDIATE")
            try:
                row = cur.execute(
                    "SELECT user_id, price FROM auto_renew_charges WHERE charge_id = ? AND state = 'charged'",
                    (charge_id,),
                ).fetchone()
                if not row:
                    cur.execute("COMMIT")
                    return False
                cur.execute(
                    "UPDATE auto_renew_charges SET state = 'refunded', updated_at = ? WHERE charge_id = ?",
                    (time.time(), charge_id),
                )
                cur.execute(
                    "UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE telegram_id = ?",
                    (float(row["price"]), int(row["user_id"])),
                )
                cur.execute("COMMIT")
                return True
            except BaseException:
                try:
                    cur.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    return bool(_retry(_work))


def charged_older_than(seconds: float, *, before_ts: float | None = None) -> list[dict]:
    """Записи `charged`, к которым давно никто не прикасался (живой попытки нет)."""
    cutoff = time.time() - seconds
    if before_ts is not None:
        cutoff = min(cutoff, before_ts)

    def _work():
        with _ledger_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM auto_renew_charges WHERE state = 'charged' AND updated_at < ? ORDER BY created_at",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]

    return _retry(_work)


# --- журнал попыток (кулдаун) ---------------------------------------------------

def last_attempt_age_seconds(key_id: int) -> float | None:
    def _work():
        with _ledger_conn() as conn:
            row = conn.execute(
                "SELECT last_attempt_at FROM auto_renew_attempts WHERE key_id = ?", (int(key_id),)
            ).fetchone()
            return float(row["last_attempt_at"]) if row else None

    ts = _retry(_work)
    return None if ts is None else max(0.0, time.time() - ts)


def record_attempt(key_id: int) -> None:
    def _work():
        with _ledger_conn() as conn:
            conn.execute(
                "INSERT INTO auto_renew_attempts (key_id, last_attempt_at) VALUES (?, ?) "
                "ON CONFLICT(key_id) DO UPDATE SET last_attempt_at = excluded.last_attempt_at",
                (int(key_id), time.time()),
            )

    _retry(_work)


def clear_attempt(key_id: int) -> None:
    def _work():
        with _ledger_conn() as conn:
            conn.execute("DELETE FROM auto_renew_attempts WHERE key_id = ?", (int(key_id),))

    _retry(_work)
