"""Рассылки: кампании, выборка получателей и учёт отправок.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging

__all__ = (
    "create_broadcast_campaign",
    "get_broadcast_campaigns",
    "get_broadcast_campaign",
    "update_broadcast_campaign",
    "toggle_broadcast_campaign",
    "delete_broadcast_campaign",
    "get_inactive_subscribers",
    "record_broadcast_sends",
    "mark_broadcast_run",
)


# =============================
# Рассылки
# =============================

def create_broadcast_campaign(name: str, text_html: str, interval_hours: int = 72, target_segment: str = "inactive") -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO broadcast_campaigns (name, text_html, interval_hours, target_segment) VALUES (?, ?, ?, ?)",
                (name.strip(), text_html.strip(), int(interval_hours), target_segment),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error("Failed to create broadcast campaign: %s", e)
        return None


def get_broadcast_campaigns() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM broadcast_campaigns ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to get broadcast campaigns: %s", e)
        return []


def get_broadcast_campaign(campaign_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM broadcast_campaigns WHERE id = ?", (int(campaign_id),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("Failed to get broadcast campaign %s: %s", campaign_id, e)
        return None


def update_broadcast_campaign(campaign_id: int, *, name: str, text_html: str, interval_hours: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE broadcast_campaigns SET name=?, text_html=?, interval_hours=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (name.strip(), text_html.strip(), int(interval_hours), int(campaign_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to update broadcast campaign %s: %s", campaign_id, e)
        return False


def toggle_broadcast_campaign(campaign_id: int) -> bool:
    """Flip is_active. Returns new is_active state."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_active FROM broadcast_campaigns WHERE id = ?", (int(campaign_id),))
            row = cursor.fetchone()
            if not row:
                return False
            new_state = 0 if row[0] else 1
            cursor.execute(
                "UPDATE broadcast_campaigns SET is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_state, int(campaign_id)),
            )
            conn.commit()
            return bool(new_state)
    except sqlite3.Error as e:
        logging.error("Failed to toggle broadcast campaign %s: %s", campaign_id, e)
        return False


def delete_broadcast_campaign(campaign_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM broadcast_sends WHERE campaign_id = ?", (int(campaign_id),))
            cursor.execute("DELETE FROM broadcast_campaigns WHERE id = ?", (int(campaign_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to delete broadcast campaign %s: %s", campaign_id, e)
        return False


def get_inactive_subscribers() -> list[int]:
    """User IDs with no active keys (expire_at in the past or no keys at all),
    not banned, not marked unreachable (blocked the bot / deactivated account),
    and not email-only accounts without Telegram auth."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.telegram_id FROM users u
                WHERE u.is_banned = 0
                  AND (u.is_unreachable IS NULL OR u.is_unreachable = 0)
                  AND (u.telegram_id < ? OR u.telegram_id > ?)
                  AND NOT EXISTS (
                    SELECT 1 FROM vpn_keys k
                    WHERE k.user_id = u.telegram_id
                      AND k.expire_at > datetime('now')
                  )
                """,
                (EMAIL_ONLY_TELEGRAM_ID_MIN, EMAIL_ONLY_TELEGRAM_ID_MAX),
            )
            return [row[0] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to get inactive subscribers: %s", e)
        return []


def record_broadcast_sends(campaign_id: int, user_ids: list[int]) -> int:
    """Insert send records and bump campaign send_count. Returns count inserted."""
    if not user_ids:
        return 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "INSERT INTO broadcast_sends (campaign_id, user_id) VALUES (?, ?)",
                [(int(campaign_id), int(uid)) for uid in user_ids],
            )
            cursor.execute(
                "UPDATE broadcast_campaigns SET last_run_at=CURRENT_TIMESTAMP, send_count=COALESCE(send_count,0)+?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (len(user_ids), int(campaign_id)),
            )
            conn.commit()
            return len(user_ids)
    except sqlite3.Error as e:
        logging.error("Failed to record broadcast sends for campaign %s: %s", campaign_id, e)
        return 0


def mark_broadcast_run(campaign_id: int) -> None:
    """Update last_run_at even when there are no recipients (avoids tight retry loops)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE broadcast_campaigns SET last_run_at=CURRENT_TIMESTAMP WHERE id=?",
                (int(campaign_id),),
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error("Failed to mark broadcast run for campaign %s: %s", campaign_id, e)
