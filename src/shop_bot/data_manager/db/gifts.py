"""Подарочные подписки.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import hashlib
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
    "gift_code_ref",
    "transfer_user_gift",
    "find_stuck_gift_activations",
    "repair_stuck_gift_activation",
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
        logger.error(f"Gift code ref={gift_code_ref(gift_code)} already exists")
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
        logger.error(f"Failed to get gift by code ref={gift_code_ref(gift_code)}: {e}")
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
    """Активировать подарок для пользователя (совместимая обёртка).

    Раньше функция только ставила флаг `is_activated`, а ключ переносили
    отдельным вызовом: при его сбое подарок исчезал у дарителя и не появлялся
    у получателя. Теперь флаг и передача ключа — одна транзакция
    `transfer_user_gift`.

    Returns: (success, gift_data); success=True только для новой активации.
    """
    result = transfer_user_gift(gift_code, activated_by_user_id)
    return result["status"] == "activated", result.get("gift")


_GIFT_KEY_TAGS = ("user_gift", "gift")
_GIFT_TAG_SQL = "LOWER(TRIM(COALESCE(tag, ''))) IN ('user_gift', 'gift')"


def _is_gift_key_tag(tag) -> bool:
    return str(tag or "").strip().lower() in _GIFT_KEY_TAGS


def gift_code_ref(gift_code) -> str:
    """Короткий отпечаток кода подарка для логов: сам код — секрет получения."""
    code = str(gift_code or "").strip()
    if not code:
        return "-"
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:10]


def _gift_expired(expires_at) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(str(expires_at)) < datetime.utcnow()
    except ValueError:
        logging.warning("gift_transfer: нераспознанный expires_at=%r, считаем подарок бессрочным", expires_at)
        return False


class _GiftTransferAborted(Exception):
    """Условное изменение не затронуло ровно одну строку — транзакция откатывается."""


def _move_gift_key(cur, key_id: int, from_owner: int, to_user: int, now: str) -> None:
    cur.execute(
        f"""
        UPDATE vpn_keys
        SET user_id = ?, tag = '', updated_at = ?
        WHERE key_id = ? AND user_id = ? AND {_GIFT_TAG_SQL}
        """,
        (int(to_user), now, int(key_id), int(from_owner)),
    )
    if cur.rowcount != 1:
        raise _GiftTransferAborted(f"vpn_keys rowcount={cur.rowcount}")


def transfer_user_gift(gift_code: str, recipient_user_id: int) -> dict:
    """Передать подарочный ключ получателю и записать активацию — одной транзакцией.

    В одной транзакции `BEGIN IMMEDIATE` на одном соединении: проверка
    подарка и ключа, `UPDATE vpn_keys` (владелец + снятие тега `user_gift`,
    по которому ключ отличают от обычных) и `UPDATE user_gifts` с условием
    `is_activated = 0`. Каждое изменение обязано затронуть ровно одну строку,
    иначе откатываются оба. Гонку двух получателей по-прежнему решает условный
    UPDATE, а не предварительный SELECT.

    UUID, email/key_email, subscription_url, срок и лимиты ключа не меняются:
    по email/username ключ находится в Remnawave при продлении и синхронизации,
    его локальное переименование отвязало бы подписку от панели. Внешних
    вызовов нет — передача целиком локальная.

    Повтор тем же получателем идемпотентен. Запись «активирован этим
    пользователем, но ключ не передан» (результат прежней двухшаговой логики)
    доводится до конца, только если ключ всё ещё у дарителя с подарочным тегом
    (`status="recovered"`); ключ, ушедший кому-то третьему, не трогается
    (`status="inconsistent"`).

    Returns: {"ok", "status", "gift_id", "key_id", "from_user_id", "gift", "key"};
    status ∈ activated, recovered, already_activated, already_activated_by_other,
    not_found, expired, key_missing, key_unavailable, inconsistent, error.
    """
    code = str(gift_code or "").strip()
    result: dict = {
        "ok": False, "status": "error", "gift_id": None, "key_id": None,
        "from_user_id": None, "gift": None, "key": None,
    }
    try:
        uid = int(recipient_user_id)
    except (TypeError, ValueError):
        return result
    if not code or uid <= 0:
        result["status"] = "not_found"
        return result

    def _finish(status: str, ok: bool = False) -> dict:
        result["status"] = status
        result["ok"] = ok
        logging.info(
            "gift_transfer gift_id=%s user_id=%s key_id=%s result=%s",
            result["gift_id"], uid, result["key_id"], status,
        )
        return result

    conn = sqlite3.connect(DB_FILE, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        gift_row = cur.execute("SELECT * FROM user_gifts WHERE gift_code = ?", (code,)).fetchone()
        if not gift_row:
            conn.rollback()
            return _finish("not_found")
        gift = dict(gift_row)
        result["gift"] = gift
        result["gift_id"] = gift.get("gift_id")
        result["key_id"] = gift.get("key_id")
        from_user_id = int(gift.get("from_user_id") or 0)
        result["from_user_id"] = from_user_id
        key_id = gift.get("key_id")
        key_row = None
        if key_id is not None:
            key_row = cur.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (int(key_id),)).fetchone()
        key_owner = int(key_row["user_id"] or 0) if key_row else None
        key_is_gift = bool(key_row) and _is_gift_key_tag(key_row["tag"])

        if gift.get("is_activated"):
            if int(gift.get("activated_by_user_id") or 0) != uid:
                conn.rollback()
                return _finish("already_activated_by_other")
            if key_row is None:
                conn.rollback()
                return _finish("key_missing")
            if key_owner == uid and not key_is_gift:
                conn.rollback()
                result["key"] = _normalize_key_row(key_row)
                return _finish("already_activated", ok=True)
            if key_is_gift and key_owner in (uid, from_user_id):
                _move_gift_key(cur, int(key_id), key_owner, uid, _now_str())
                fresh = cur.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (int(key_id),)).fetchone()
                conn.commit()
                result["key"] = _normalize_key_row(fresh)
                return _finish("recovered", ok=True)
            conn.rollback()
            logging.warning(
                "gift_transfer: подарок %s активирован пользователем %s, но ключ %s у пользователя %s "
                "(tag=%r) — нужна ручная проверка",
                result["gift_id"], uid, key_id, key_owner, key_row["tag"],
            )
            return _finish("inconsistent")

        if _gift_expired(gift.get("expires_at")):
            conn.rollback()
            return _finish("expired")
        if key_row is None:
            conn.rollback()
            return _finish("key_missing")
        if key_owner != from_user_id or not key_is_gift:
            conn.rollback()
            logging.warning(
                "gift_transfer: ключ %s подарка %s не в подарочном состоянии (владелец %s, tag=%r)",
                key_id, result["gift_id"], key_owner, key_row["tag"],
            )
            return _finish("key_unavailable")

        now = _now_str()
        _move_gift_key(cur, int(key_id), from_user_id, uid, now)
        cur.execute(
            """
            UPDATE user_gifts
            SET is_activated = 1, activated_by_user_id = ?, activated_at = ?
            WHERE gift_id = ? AND is_activated = 0
            """,
            (uid, now, int(gift["gift_id"])),
        )
        if cur.rowcount != 1:
            raise _GiftTransferAborted(f"user_gifts rowcount={cur.rowcount}")
        fresh = cur.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (int(key_id),)).fetchone()
        conn.commit()
        gift.update(is_activated=1, activated_by_user_id=uid, activated_at=now)
        result["key"] = _normalize_key_row(fresh)
        return _finish("activated", ok=True)
    except Exception as e:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        logging.error(
            "gift_transfer gift_id=%s user_id=%s key_id=%s result=error (откат): %s",
            result["gift_id"], uid, result["key_id"], e,
        )
        result["status"] = "error"
        result["ok"] = False
        return result
    finally:
        conn.close()


_STUCK_GIFTS_SQL = f"""
    SELECT g.gift_id, g.from_user_id, g.activated_by_user_id, g.activated_at, g.key_id,
           k.key_id AS existing_key_id, k.user_id AS key_user_id, k.tag AS key_tag
    FROM user_gifts g
    LEFT JOIN vpn_keys k ON k.key_id = g.key_id
    WHERE g.is_activated = 1
      AND (
            g.activated_by_user_id IS NULL
         OR k.key_id IS NULL
         OR k.user_id IS NOT g.activated_by_user_id
         OR LOWER(TRIM(COALESCE(k.tag, ''))) IN ('user_gift', 'gift')
      )
"""


def _classify_stuck_gift(row: dict) -> tuple[str, bool]:
    if not row.get("activated_by_user_id"):
        return "no_recipient", False
    if row.get("existing_key_id") is None:
        return "key_missing", False
    owner = int(row.get("key_user_id") or 0)
    recipient = int(row["activated_by_user_id"])
    if _is_gift_key_tag(row.get("key_tag")) and owner in (recipient, int(row.get("from_user_id") or 0)):
        return "not_transferred", True
    return "owner_mismatch", False


def find_stuck_gift_activations(limit: int = 1000) -> list[dict]:
    """Подарки «активирован, но ключ у получателя не оказался» — только чтение.

    problem:
      * not_transferred — ключ всё ещё у дарителя (или у получателя) с тегом
        `user_gift`; recoverable=True, см. `repair_stuck_gift_activation`;
      * owner_mismatch — ключ у третьего пользователя: только вручную;
      * key_missing — ключа нет (часто это обычная очистка просроченного
        ключа после выдачи) — информационно;
      * no_recipient — активация без получателя: только вручную.
    Коды подарков в отчёт не попадают.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(_STUCK_GIFTS_SQL + " ORDER BY g.gift_id LIMIT ?", (int(limit),)).fetchall()
    except sqlite3.Error as e:
        logging.error("find_stuck_gift_activations failed: %s", e)
        return []
    report = []
    for row in rows:
        item = dict(row)
        problem, recoverable = _classify_stuck_gift(item)
        item["problem"] = problem
        item["recoverable"] = recoverable
        report.append(item)
    return report


def repair_stuck_gift_activation(gift_id: int) -> dict:
    """Довести одну зависшую активацию: передать ключ тому, кто записан в
    `activated_by_user_id`. Только для problem=not_transferred; флаг
    активации не сбрасывается, чужой ключ не переназначается.

    Returns: {"ok", "status", "gift_id", "key_id", "user_id"}.
    """
    out = {"ok": False, "status": "error", "gift_id": int(gift_id), "key_id": None, "user_id": None}
    conn = sqlite3.connect(DB_FILE, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        row = cur.execute(_STUCK_GIFTS_SQL + " AND g.gift_id = ?", (int(gift_id),)).fetchone()
        if not row:
            conn.rollback()
            out["status"] = "not_stuck"
            return out
        item = dict(row)
        problem, recoverable = _classify_stuck_gift(item)
        out["key_id"] = item.get("key_id")
        out["user_id"] = item.get("activated_by_user_id")
        if not recoverable:
            conn.rollback()
            out["status"] = problem
            return out
        _move_gift_key(cur, int(item["key_id"]), int(item["key_user_id"]), int(item["activated_by_user_id"]), _now_str())
        conn.commit()
        out.update(ok=True, status="repaired")
        logging.info(
            "gift_repair gift_id=%s user_id=%s key_id=%s result=repaired",
            out["gift_id"], out["user_id"], out["key_id"],
        )
        return out
    except Exception as e:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        logging.error("gift_repair gift_id=%s result=error: %s", gift_id, e)
        return out
    finally:
        conn.close()


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
