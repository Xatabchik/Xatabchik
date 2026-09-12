"""Реферальная программа: связывание пригласившего, начисления и выплаты.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
import re

__all__ = (
    "claim_referral_start_bonus",
    "set_referral_start_bonus_received",
    "set_referral_trial_day_bonus_received",
    "get_referrals_analytics",
    "get_top_referrers",
    "get_referrals_for_user",
    "get_referral_top_rich",
    "get_referral_rank_and_count",
    "add_to_referral_balance",
    "set_referral_balance",
    "set_referral_balance_all",
    "add_to_referral_balance_all",
    "get_referral_balance_all",
    "get_referral_balance",
    "adjust_user_referral_balance",
    "deduct_from_referral_balance",
    "REFERRAL_PAYOUT_METHOD_TYPES",
    "_REFERRAL_TRC20_RE",
    "_referral_setting_is_true",
    "validate_referral_payout_requisite",
    "list_referral_payout_methods",
    "add_referral_payout_method",
    "delete_referral_payout_method",
    "get_referral_payout_method",
    "get_referral_count",
    "REFERRAL_LINK_LINKED",
    "REFERRAL_LINK_ALREADY_LINKED",
    "REFERRAL_LINK_SELF_FORBIDDEN",
    "REFERRAL_LINK_INVALID_REFERRER",
    "REFERRAL_LINK_NOT_ELIGIBLE",
    "link_referrer_if_eligible",
    "REFERRAL_UNLINK_UNLINKED",
    "REFERRAL_UNLINK_NOT_LINKED",
    "REFERRAL_UNLINK_NOT_FOUND",
    "REFERRAL_UNLINK_INVALID",
    "unlink_referral",
    "unlink_all_referrals",
)


def claim_referral_start_bonus(user_id: int) -> bool:
    """Атомарно пометить, что приглашённый получил стартовый реферальный бонус.

    Возвращает True только если этот вызов выиграл гонку: UPDATE с
    ``WHERE COALESCE(referral_start_bonus_received, 0) = 0`` и ``rowcount > 0``.
    Начислять баланс рефереру можно только после успешного claim — иначе
    параллельные /start (или pending-action) дважды кредитуют одну и ту же сумму.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users
                SET referral_start_bonus_received = 1
                WHERE telegram_id = ?
                  AND COALESCE(referral_start_bonus_received, 0) = 0
                """,
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(
            f"Не удалось атомарно пометить получение стартового реферального бонуса для пользователя {user_id}: {e}"
        )
        return False


def set_referral_start_bonus_received(user_id: int) -> bool:
    """Пометить, что пользователь получил стартовый бонус за реферальную регистрацию.

    Атомарный claim (см. ``claim_referral_start_bonus``): повторный вызов
    возвращает False и не сбрасывает флаг.
    """
    return claim_referral_start_bonus(user_id)


def set_referral_trial_day_bonus_received(user_id: int) -> bool:
    """Пометить, что за данного пользователя уже начислялся +1 день рефереру за активацию триала."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET referral_trial_day_bonus_received = 1 WHERE telegram_id = ?",
                (user_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(
            f"Не удалось пометить начисление +1 дня за триал для пользователя {user_id}: {e}"
        )
        return False


def get_referrals_analytics() -> dict:
    """Аналитика реферальной программы (Этап 6.1) поверх существующих полей/функций,
    без создания новой реферальной системы."""
    data = {
        "referrers_count": 0,
        "referrals_count": 0,
        "active_referrals": 0,
        "paying_referrals": 0,
        "accrued_total": 0.0,
        "current_balance_total": 0.0,
        "spent_total": 0.0,
        "revenue_from_referrals": 0.0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL")
            data["referrers_count"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL")
            data["referrals_count"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                """
                SELECT COUNT(DISTINCT k.user_id)
                FROM vpn_keys k
                JOIN users u ON u.telegram_id = k.user_id
                WHERE u.referred_by IS NOT NULL
                  AND (k.expire_at IS NULL OR datetime(k.expire_at) > CURRENT_TIMESTAMP)
                """
            )
            data["active_referrals"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT t.user_id)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.referred_by IS NOT NULL AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            data["paying_referrals"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                f"""
                SELECT COALESCE(SUM(t.amount_rub), 0)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.referred_by IS NOT NULL AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            data["revenue_from_referrals"] = float((cursor.fetchone() or [0.0])[0] or 0.0)

            cursor.execute("SELECT COALESCE(SUM(referral_balance_all), 0), COALESCE(SUM(referral_balance), 0) FROM users")
            accrued_all, balance_now = cursor.fetchone() or (0.0, 0.0)
            data["accrued_total"] = float(accrued_all or 0.0)
            data["current_balance_total"] = float(balance_now or 0.0)
            data["spent_total"] = max(0.0, data["accrued_total"] - data["current_balance_total"])
    except sqlite3.Error as e:
        logging.error(f"Failed to get referrals analytics: {e}")
    return data


def get_top_referrers(limit: int = 10) -> list[dict]:
    """Топ пользователей по рефералам: число приглашённых и число платящих рефералов."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    u.referred_by AS referrer_id,
                    ref_owner.username AS referrer_username,
                    COUNT(DISTINCT u.telegram_id) AS invited_count,
                    SUM(CASE WHEN EXISTS (
                        SELECT 1 FROM transactions t
                        WHERE t.user_id = u.telegram_id AND {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                    ) THEN 1 ELSE 0 END) AS paying_count,
                    ref_owner.referral_balance_all AS bonus_total,
                    ref_owner.referral_balance AS current_balance,
                    COALESCE((
                        SELECT SUM(w.amount)
                        FROM referral_withdrawal_requests w
                        WHERE w.user_id = u.referred_by
                          AND w.status = 'paid'
                    ), 0) AS withdrawn_total
                FROM users u
                LEFT JOIN users ref_owner ON ref_owner.telegram_id = u.referred_by
                WHERE u.referred_by IS NOT NULL
                GROUP BY u.referred_by
                ORDER BY invited_count DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            for row in cursor.fetchall():
                result.append(dict(row))
    except sqlite3.Error as e:
        logging.error(f"Failed to get top referrers: {e}")
    return result


def get_referrals_for_user(user_id: int) -> list[dict]:
    """Возвращает список пользователей, которых пригласил данный user_id.
    Поля: telegram_id, username, registration_date, total_spent.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT telegram_id, username, registration_date, total_spent
                FROM users
                WHERE referred_by = ?
                ORDER BY registration_date DESC
                """,
                (user_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Failed to get referrals for user {user_id}: {e}")
        return []
        

def get_referral_top_rich(limit: int = 5) -> list[dict]:
    """
    Возвращает топ пользователей по количеству рефералов,
    которые пополнили баланс хотя бы один раз (total_spent > 0).
    Поля: telegram_id, rich_referrals.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT referred_by AS telegram_id,
                       COUNT(*) AS rich_referrals
                FROM users
                WHERE referred_by IS NOT NULL
                  AND referred_by <> 0
                  AND COALESCE(total_spent, 0) > 0
                GROUP BY referred_by
                HAVING rich_referrals > 0
                ORDER BY rich_referrals DESC, referred_by ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral top rich: {e}")
        return []


def get_referral_rank_and_count(user_id: int) -> tuple[int | None, int]:
    """
    Возвращает кортеж (rank, count), где:
      - rank — место пользователя в рейтинге по количеству
        рефералов с пополнением баланса (total_spent > 0),
        либо None, если пользователь не попадает в рейтинг;
      - count — количество таких рефералов у пользователя.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT referred_by AS telegram_id,
                       COUNT(*) AS rich_referrals
                FROM users
                WHERE referred_by IS NOT NULL
                  AND referred_by <> 0
                  AND COALESCE(total_spent, 0) > 0
                GROUP BY referred_by
                HAVING rich_referrals > 0
                ORDER BY rich_referrals DESC, referred_by ASC
                """
            )
            rows = cursor.fetchall()

            rank: int | None = None
            personal_count: int = 0

            for index, (telegram_id, rich_referrals) in enumerate(rows, start=1):
                if telegram_id == user_id:
                    rank = index
                    personal_count = int(rich_referrals or 0)
                    break

            if rank is None:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM users
                    WHERE referred_by = ?
                      AND COALESCE(total_spent, 0) > 0
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                personal_count = int(row[0] or 0) if row else 0

            return rank, personal_count
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral rank for user {user_id}: {e}")
        return None, 0

def add_to_referral_balance(user_id: int, amount: float) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = referral_balance + ? WHERE telegram_id = ?", (amount, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to add to referral balance for user {user_id}: {e}")
        return False

def set_referral_balance(user_id: int, value: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = ? WHERE telegram_id = ?", (value, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set referral balance for user {user_id}: {e}")

def set_referral_balance_all(user_id: int, value: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance_all = ? WHERE telegram_id = ?", (value, user_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to set total referral balance for user {user_id}: {e}")

def add_to_referral_balance_all(user_id: int, amount: float):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET referral_balance_all = referral_balance_all + ? WHERE telegram_id = ?",
                (amount, user_id)
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to add to total referral balance for user {user_id}: {e}")

def get_referral_balance_all(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referral_balance_all FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            return row[0] if row else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total referral balance for user {user_id}: {e}")
        return 0.0

def get_referral_balance(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral balance for user {user_id}: {e}")
        return 0.0

def adjust_user_referral_balance(user_id: int, delta: float) -> bool:
    """Скорректировать реферальный баланс пользователя на указанную дельту (может быть отрицательной)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referral_balance = COALESCE(referral_balance, 0) + ? WHERE telegram_id = ?", (float(delta), user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to adjust referral balance for user {user_id}: {e}")
        return False

def deduct_from_referral_balance(user_id: int, amount: float) -> bool:
    """Атомарное списание с реферального баланса при достаточности средств."""
    if amount <= 0:
        return True
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT referral_balance FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            current = row[0] if row else 0.0
            if current < amount:
                conn.rollback()
                return False
            cursor.execute("UPDATE users SET referral_balance = referral_balance - ? WHERE telegram_id = ?", (amount, user_id))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to deduct from referral balance for user {user_id}: {e}")
        return False


# =============================
# Реферальная программа: методы получения выплат и заявки на вывод
# =============================

REFERRAL_PAYOUT_METHOD_TYPES = ("sbp", "card", "usdt_trc20")
_REFERRAL_TRC20_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


def _referral_setting_is_true(key: str, default: bool = False) -> bool:
    raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
    return raw in {"1", "true", "yes", "on", "y"}


def validate_referral_payout_requisite(
    method_type: str, requisite_value: str, bank_name: str | None = None
) -> tuple[bool, str]:
    """Проверить реквизиты метода получения перед сохранением."""
    method_type = (method_type or "").strip().lower()
    value = (requisite_value or "").strip()
    if method_type not in REFERRAL_PAYOUT_METHOD_TYPES:
        return False, "Неизвестный тип метода получения."
    if not value:
        return False, "Реквизиты не могут быть пустыми."
    if method_type == "sbp":
        if not (bank_name or "").strip():
            return False, "Не указан банк для СБП."
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 10 or len(digits) > 15:
            return False, "Укажите номер телефона для СБП (10–15 цифр)."
        return True, ""
    if method_type == "card":
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) < 16 or len(digits) > 19:
            return False, "Номер карты должен содержать 16–19 цифр."
        return True, ""
    if not _REFERRAL_TRC20_RE.fullmatch(value):
        return False, "Укажите корректный адрес USDT TRC20 (начинается с T)."
    return True, ""


def list_referral_payout_methods(user_id: int) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM referral_payout_methods WHERE user_id = ? ORDER BY created_at DESC",
                (int(user_id),),
            )
            return [dict(r) for r in cur.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to list referral payout methods for {user_id}: {e}")
        return []


def add_referral_payout_method(user_id: int, method_type: str, requisite_value: str, bank_name: str | None = None) -> tuple[bool, str, int | None]:
    method_type = (method_type or "").strip().lower()
    if method_type not in REFERRAL_PAYOUT_METHOD_TYPES:
        return False, "Неизвестный тип метода получения.", None
    requisite_value = (requisite_value or "").strip()
    ok, msg = validate_referral_payout_requisite(method_type, requisite_value, bank_name)
    if not ok:
        return False, msg, None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO referral_payout_methods (user_id, method_type, bank_name, requisite_value) VALUES (?, ?, ?, ?)",
                (int(user_id), method_type, (bank_name or "").strip() or None, requisite_value),
            )
            conn.commit()
            return True, "Метод получения добавлен.", int(cur.lastrowid)
    except sqlite3.Error as e:
        logging.error(f"Failed to add referral payout method for {user_id}: {e}")
        return False, "Ошибка базы данных.", None


def delete_referral_payout_method(method_id: int, user_id: int) -> tuple[bool, str]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM referral_payout_methods WHERE id = ? AND user_id = ?",
                (int(method_id), int(user_id)),
            )
            conn.commit()
            if cur.rowcount > 0:
                return True, "Метод получения удалён."
            return False, "Метод получения не найден."
    except sqlite3.Error as e:
        logging.error(f"Failed to delete referral payout method {method_id}: {e}")
        return False, "Ошибка базы данных."


def get_referral_payout_method(method_id: int, user_id: int | None = None) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if user_id is not None:
                cur.execute(
                    "SELECT * FROM referral_payout_methods WHERE id = ? AND user_id = ?",
                    (int(method_id), int(user_id)),
                )
            else:
                cur.execute("SELECT * FROM referral_payout_methods WHERE id = ?", (int(method_id),))
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral payout method {method_id}: {e}")
        return None


def get_referral_count(user_id: int) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get referral count for user {user_id}: {e}")
        return 0


# Возможные статусы результата привязки реферала — используются как UI-статусы
# в ответе POST /api/webapp/pending-actions/complete.
REFERRAL_LINK_LINKED = "linked"
REFERRAL_LINK_ALREADY_LINKED = "already_linked"
REFERRAL_LINK_SELF_FORBIDDEN = "self_referral_forbidden"
REFERRAL_LINK_INVALID_REFERRER = "invalid_referrer"
REFERRAL_LINK_NOT_ELIGIBLE = "not_eligible"


def link_referrer_if_eligible(user_id: int, referrer_id: int, *, max_age_seconds: int | None = None) -> str:
    """Привязать пользователя к рефереру (users.referred_by), если это допустимо.

    Атомарно: UPDATE сразу проверяет условие `referred_by IS NULL` в WHERE и
    возвращает успех по `cursor.rowcount` — так что даже при параллельных
    вызовах (например, два одновременных запроса complete по одному и тому же
    pending-токену) привязка реферера не может произойти дважды и не может
    затереть уже существующего реферера.

    ``max_age_seconds``: если задан, аккаунт старше этого окна не привязывается
    (тот же guard, что у ``set_referred_by_from_gift``). Webapp pending-action
    передаёт окно, чтобы старый аккаунт с пустым ``referred_by`` нельзя было
    late-bind'ить реферальной ссылкой. Админский ручной assign вызывает без
    окна — существующая возможность назначить реферала сохраняется.

    Возвращает один из: linked, already_linked, self_referral_forbidden,
    invalid_referrer, not_eligible.
    """
    try:
        uid = int(user_id)
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return REFERRAL_LINK_INVALID_REFERRER

    if rid <= 0:
        return REFERRAL_LINK_INVALID_REFERRER
    if rid == uid:
        return REFERRAL_LINK_SELF_FORBIDDEN

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM users WHERE telegram_id = ?", (rid,))
            if not cursor.fetchone():
                return REFERRAL_LINK_INVALID_REFERRER

            cursor.execute(
                "SELECT referred_by, registration_date FROM users WHERE telegram_id = ?",
                (uid,),
            )
            row = cursor.fetchone()
            if not row:
                return REFERRAL_LINK_NOT_ELIGIBLE

            if row[0] is not None:
                return REFERRAL_LINK_ALREADY_LINKED if int(row[0]) == rid else REFERRAL_LINK_ALREADY_LINKED

            if max_age_seconds is not None:
                age = _registration_age_seconds(row[1])
                if age is not None and age > max_age_seconds:
                    logging.info(
                        "link_referrer_if_eligible: skipped user %s "
                        "(registered %.0f s ago, threshold %d s)",
                        uid, age, max_age_seconds,
                    )
                    return REFERRAL_LINK_NOT_ELIGIBLE

            cursor.execute(
                "UPDATE users SET referred_by = ? WHERE telegram_id = ? AND referred_by IS NULL AND telegram_id != ?",
                (rid, uid, rid),
            )
            conn.commit()
            if cursor.rowcount > 0:
                return REFERRAL_LINK_LINKED
            # Кто-то параллельно уже успел выставить referred_by между нашим SELECT и UPDATE.
            return REFERRAL_LINK_ALREADY_LINKED
    except Exception as e:
        logging.error("link_referrer_if_eligible failed for user %s -> referrer %s: %s", user_id, referrer_id, e)
        return REFERRAL_LINK_NOT_ELIGIBLE


REFERRAL_UNLINK_UNLINKED = "unlinked"
REFERRAL_UNLINK_NOT_LINKED = "not_linked"
REFERRAL_UNLINK_NOT_FOUND = "not_found"
REFERRAL_UNLINK_INVALID = "invalid"


def unlink_referral(invitee_id: int, referrer_id: int) -> str:
    """Снять привязку реферала: обнулить users.referred_by у invitee, если он
    действительно привязан к referrer_id.

    Возвращает: unlinked, not_linked, not_found, invalid.
    """
    try:
        uid = int(invitee_id)
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return REFERRAL_UNLINK_INVALID

    if uid <= 0 or rid <= 0 or uid == rid:
        return REFERRAL_UNLINK_INVALID

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referred_by FROM users WHERE telegram_id = ?", (uid,))
            row = cursor.fetchone()
            if not row:
                return REFERRAL_UNLINK_NOT_FOUND
            if row[0] is None or int(row[0]) != rid:
                return REFERRAL_UNLINK_NOT_LINKED

            cursor.execute(
                "UPDATE users SET referred_by = NULL WHERE telegram_id = ? AND referred_by = ?",
                (uid, rid),
            )
            conn.commit()
            if cursor.rowcount > 0:
                return REFERRAL_UNLINK_UNLINKED
            return REFERRAL_UNLINK_NOT_LINKED
    except Exception as e:
        logging.error("unlink_referral failed for invitee %s / referrer %s: %s", invitee_id, referrer_id, e)
        return REFERRAL_UNLINK_INVALID


def unlink_all_referrals(referrer_id: int) -> tuple[bool, int]:
    """Снять привязку у всех рефералов указанного реферера.

    Возвращает (ok, removed_count).
    """
    try:
        rid = int(referrer_id)
    except (TypeError, ValueError):
        return False, 0
    if rid <= 0:
        return False, 0

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                (rid,),
            )
            removed = int(cursor.rowcount or 0)
            conn.commit()
            return True, removed
    except Exception as e:
        logging.error("unlink_all_referrals failed for referrer %s: %s", referrer_id, e)
        return False, 0
