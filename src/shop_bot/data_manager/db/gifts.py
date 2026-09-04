"""Подарочные подписки.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
import uuid

__all__ = (
    "create_gift_key",
    "ensure_main_menu_gift_button",
    "create_user_gift",
    "get_user_gift",
    "get_gift_by_code",
    "get_user_inactive_gifts",
    "activate_user_gift",
    "set_referred_by_from_gift",
    "delete_user_gift",
    "link_key_to_gift",
    "get_gift_code_by_key_id",
    "get_gift_info_by_key_id",
)


def create_gift_key(user_id: int, host_name: str, key_email: str, months: int, remnawave_user_uuid: str | None = None) -> int | None:
    """Создать подарочный ключ: expiry = now + months."""
    try:
        from datetime import timedelta

        months_value = max(1, int(months or 1))
        expiry_dt = datetime.utcnow() + timedelta(days=30 * months_value)
        expiry_ms = int(expiry_dt.timestamp() * 1000)
        uuid_value = remnawave_user_uuid or f"GIFT-{user_id}-{int(datetime.utcnow().timestamp())}"
        return add_new_key(
            user_id=user_id,
            host_name=host_name,
            remnawave_user_uuid=uuid_value,
            key_email=key_email,
            expiry_timestamp_ms=expiry_ms,
        )
    except sqlite3.Error as e:
        logging.error(f"Failed to create gift key for user {user_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to create gift key for user {user_id}: {e}")
        return None


def ensure_main_menu_gift_button() -> None:
    """Ensure that the main menu has the gift button in button configs."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT 1 FROM button_configs WHERE menu_type = 'main_menu' AND button_id = 'gift_new_key' LIMIT 1"
            )
            if cursor.fetchone():
                return

            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            next_sort = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                "SELECT COALESCE(MAX(row_position), 0) FROM button_configs WHERE menu_type = 'main_menu'"
            )
            row_pos = int(cursor.fetchone()[0] or 0) + 1

            cursor.execute(
                """
                INSERT INTO button_configs
                    (menu_type, button_id, text, callback_data, row_position, column_position, sort_order, button_width, is_active)
                VALUES
                    (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                ("main_menu", "gift_new_key", "🎁 Подарить", "gift_new_key", row_pos, 0, next_sort, 2),
            )
            conn.commit()
            logging.info("Inserted missing main_menu button: gift_new_key")
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure main menu gift button: {e}")


# ============================================
# Функции для работы с пользовательскими подарками
# ============================================

def create_user_gift(
    from_user_id: int,
    host_name: str,
    plan_id: int | None = None,
    gift_code: str | None = None,
    expires_in_days: int | None = None,
) -> dict | None:
    """Создать неактивированный подарок от одного пользователя.
    
    Returns: dict with gift_id and gift_code on success, None on error.
    """
    import uuid
    
    try:
        from_user_id = int(from_user_id)
        host_name = str(host_name).strip()
        plan_id = int(plan_id) if plan_id else None
        
        if not gift_code:
            gift_code = str(uuid.uuid4())[:12]
        
        expires_at = None
        if expires_in_days:
            expires_at = (datetime.utcnow() + timedelta(days=int(expires_in_days))).isoformat()
        
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute(
                """
                INSERT INTO user_gifts (from_user_id, host_name, plan_id, gift_code, is_activated, expires_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (from_user_id, host_name, plan_id, gift_code, expires_at),
            )
            conn.commit()
            
            gift_id = cur.lastrowid
            return {
                "gift_id": gift_id,
                "gift_code": gift_code,
            }
    except sqlite3.IntegrityError:
        logger.error(f"Gift code {gift_code} already exists")
        return None
    except Exception as e:
        logger.error(f"Failed to create user gift: {e}")
        return None


def get_user_gift(gift_id: int) -> dict | None:
    """Получить информацию о подарке по ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_gifts WHERE gift_id = ?", (int(gift_id),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get user gift {gift_id}: {e}")
        return None


def get_gift_by_code(gift_code: str) -> dict | None:
    """Получить информацию о подарке по коду."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_gifts WHERE gift_code = ?", (str(gift_code).strip(),))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Failed to get gift by code {gift_code}: {e}")
        return None


def get_user_inactive_gifts(from_user_id: int) -> list[dict]:
    """Получить список неактивированных подарков пользователя.

    Заодно подчищает "осиротевшие" подарки — те, чей связанный ключ (vpn_keys)
    уже был удалён (например, стандартной чисткой просроченных ключей), но по
    какой-то причине запись в user_gifts не была удалена вместе с ним. Такие
    подарки не должны продолжать висеть в списке пользователя.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                """
                DELETE FROM user_gifts
                WHERE from_user_id = ? AND is_activated = 0
                  AND key_id IS NOT NULL
                  AND key_id NOT IN (SELECT key_id FROM vpn_keys)
                """,
                (int(from_user_id),),
            )
            if cur.rowcount:
                conn.commit()
            cur.execute(
                "SELECT * FROM user_gifts WHERE from_user_id = ? AND is_activated = 0 ORDER BY created_at DESC",
                (int(from_user_id),),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to get inactive gifts for user {from_user_id}: {e}")
        return []


def activate_user_gift(
    gift_code: str,
    activated_by_user_id: int,
) -> tuple[bool, dict | None]:
    """Активировать подарок для пользователя.

    Атомарность/защита от race condition: сама активация — это одно UPDATE
    с условием `is_activated = 0` прямо в WHERE, и именно `cursor.rowcount`
    (а не предварительный SELECT) решает, "выиграл" ли этот вызов гонку.
    Так два параллельных запроса на активацию одного и того же подарка не
    могут оба посчитать себя успешными — только один получит rowcount=1.

    Returns: (success, gift_data)
    """
    try:
        gift = get_gift_by_code(gift_code)
        if not gift:
            return False, None
        
        gift_id = gift.get("gift_id")
        if gift.get("is_activated"):
            return False, gift  # Already activated
        
        expires_at = gift.get("expires_at")
        if expires_at:
            if datetime.fromisoformat(expires_at) < datetime.utcnow():
                return False, gift  # Expired
        
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE user_gifts
                SET is_activated = 1, activated_by_user_id = ?, activated_at = ?
                WHERE gift_code = ? AND is_activated = 0
                """,
                (int(activated_by_user_id), _now_str(), gift_code),
            )
            won_race = cur.rowcount > 0
            conn.commit()

        if not won_race:
            # Другой параллельный запрос уже успел активировать этот подарок первым.
            return False, gift
        
        gift["is_activated"] = True
        gift["activated_by_user_id"] = int(activated_by_user_id)
        gift["activated_at"] = _now_str()
        
        logging.info(f"Gift {gift_code} activated by user {activated_by_user_id}")
        return True, gift
        
    except Exception as e:
        logger.error(f"Failed to activate gift {gift_code}: {e}")
        return False, None


def set_referred_by_from_gift(user_id: int, from_user_id: int, *, max_age_seconds: int = 1800) -> bool:
    """Set referred_by to the gift sender when a new user activates a gift.

    Guard: skips if the user's registration_date is older than max_age_seconds
    (meaning they were already registered before this gift activation).
    """
    uid = int(user_id)
    fid = int(from_user_id)
    if fid <= 0 or fid == uid:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT referred_by, registration_date FROM users WHERE telegram_id = ?", (uid,)
            )
            row = cursor.fetchone()
            if not row:
                return False
            current_ref, reg_date_raw = row
            if current_ref:
                return False  # already has a referrer
            age = _registration_age_seconds(reg_date_raw)
            if age is not None and age > max_age_seconds:
                logging.info(
                    "set_referred_by_from_gift: skipped user %s "
                    "(registered %.0f s ago, threshold %d s)", uid, age, max_age_seconds
                )
                return False
            cursor.execute(
                "UPDATE users SET referred_by = ? WHERE telegram_id = ? AND referred_by IS NULL",
                (fid, uid),
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logging.error("set_referred_by_from_gift failed for user %s: %s", user_id, e)
        return False


def delete_user_gift(gift_id: int) -> bool:
    """Удалить подарок."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_gifts WHERE gift_id = ?", (int(gift_id),))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete gift {gift_id}: {e}")
        return False


def link_key_to_gift(gift_id: int, key_id: int) -> bool:
    """Связать созданный ключ с подарком."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE user_gifts SET key_id = ? WHERE gift_id = ?",
                (int(key_id), int(gift_id)),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to link key {key_id} to gift {gift_id}: {e}")
        return False


def get_gift_code_by_key_id(key_id: int) -> str | None:
    """Получить код подарка по ID ключа."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT gift_code FROM user_gifts WHERE key_id = ?", (int(key_id),))
            row = cur.fetchone()
            return row['gift_code'] if row else None
    except Exception as e:
        logger.error(f"Failed to get gift code for key {key_id}: {e}")
        return None

def get_gift_code_by_key_id(key_id: int) -> str | None:
    """Получить код подарка по ID ключа."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT gift_code FROM user_gifts WHERE key_id = ? AND is_activated = 0", (int(key_id),))
            row = cur.fetchone()
            return row['gift_code'] if row else None
    except Exception as e:
        logger.error(f"Failed to get gift code for key {key_id}: {e}")
        return None

def get_gift_info_by_key_id(key_id: int) -> tuple[int | None, str | None]:
    """Получить ID и код подарка по ID ключа. Возвращает (gift_id, gift_code) или (None, None)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT gift_id, gift_code FROM user_gifts WHERE key_id = ? AND is_activated = 0", (int(key_id),))
            row = cur.fetchone()
            if row:
                return row['gift_id'], row['gift_code']
            return None, None
    except Exception as e:
        logger.error(f"Failed to get gift info for key {key_id}: {e}")
        return None, None
