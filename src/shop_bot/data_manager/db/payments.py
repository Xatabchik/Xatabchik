"""Платежи и транзакции: инвойсы, pending actions, пополнения и возвраты.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
import json
import secrets

__all__ = (
    "PENDING_ACTION_DEFAULT_TTL_HOURS",
    "create_pending_action",
    "get_pending_action",
    "claim_pending_action",
    "set_pending_action_result",
    "cleanup_expired_pending_actions",
    "get_payment_methods_analytics",
    "get_users_without_real_payment_with_keys",
    "get_pending_broadcast_recipients",
    "_connect_pending_db",
    "_PAID_TX_STATUSES",
    "_TERMINAL_TX_STATUSES",
    "_PROVIDER_TX_KEYS",
    "_tx_meta_dict",
    "_provider_transaction_id_from_meta",
    "_mirror_pending_to_ledger",
    "create_payload_pending",
    "patch_pending_metadata",
    "_get_pending_metadata",
    "get_pending_metadata",
    "get_pending_record",
    "revive_cancelled_invoice",
    "prepare_pending_for_fulfillment",
    "_complete_pending",
    "find_and_complete_pending_transaction",
    "get_latest_pending_for_user",
    "claim_processed_payment",
    "unclaim_processed_payment",
    "refund_payment_once",
    "cancel_pending_transaction",
    "reset_pending_transaction",
    "get_balance",
    "adjust_user_balance",
    "set_balance",
    "add_to_balance",
    "deduct_from_balance",
    "create_pending_transaction",
    "find_and_complete_ton_transaction",
    "_TX_ACTION_LABELS",
    "_describe_transaction_action",
    "_find_nearest_key_id",
    "log_transaction",
    "get_paginated_transactions",
    "get_transactions_paginated",
    "get_recent_transactions",
    "check_transaction_exists",
    "payment_owned_by_user",
    "set_pending_email",
    "clear_pending_email",
    "finalize_pending_email_change",
)


PENDING_ACTION_DEFAULT_TTL_HOURS = 24


def create_pending_action(
    action_type: str,
    *,
    gift_code: str | None = None,
    referrer_id: int | None = None,
    ttl_hours: int = PENDING_ACTION_DEFAULT_TTL_HOURS,
) -> str | None:
    """Создать pending action и вернуть одноразовый случайный токен.

    Токен — единственное, что уходит клиенту; сам контекст (какой именно
    подарок/реферер) остаётся только на сервере и не может быть подменён
    клиентом на этапе завершения (см. get_pending_action/claim_pending_action).
    """
    if action_type not in ("gift", "referral"):
        logging.error("create_pending_action: неизвестный action_type=%r", action_type)
        return None
    token = secrets.token_urlsafe(32)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO auth_pending_actions (token, action_type, gift_code, referrer_id, expires_at)
                VALUES (?, ?, ?, ?, datetime('now', ?))
                """,
                (token, action_type, gift_code, referrer_id, f"+{int(ttl_hours)} hours"),
            )
            conn.commit()
        return token
    except sqlite3.Error as e:
        logging.error("Failed to create pending action (%s): %s", action_type, e)
        return None


def get_pending_action(token: str) -> dict | None:
    """Вернуть запись pending action по токену как есть (включая уже
    истёкшие/использованные — вызывающий код сам решает, что показать
    пользователю). Не выполняет побочных эффектов."""
    if not token:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM auth_pending_actions WHERE token = ?", (str(token),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("Failed to get pending action: %s", e)
        return None


def claim_pending_action(token: str, user_id: int) -> bool:
    """Атомарно "забрать" pending action для указанного пользователя.

    Ключевой момент идемпотентности/защиты от гонки: UPDATE проверяет
    `consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP` прямо в WHERE,
    и именно `cursor.rowcount` (а не отдельный предварительный SELECT)
    определяет, успел ли именно этот вызов "выиграть" право применить действие.
    Если два параллельных запроса пришлют один и тот же pending_token —
    claim_pending_action вернёт True ровно для одного из них.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE auth_pending_actions
                SET consumed_at = CURRENT_TIMESTAMP, consumed_by_user_id = ?
                WHERE token = ? AND consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP
                """,
                (int(user_id), str(token)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to claim pending action: %s", e)
        return False


def set_pending_action_result(token: str, result_status: str) -> bool:
    """Сохранить итоговый статус применения действия — чтобы повторный вызов
    complete (тем же пользователем, для уже использованного токена) мог
    вернуть тот же самый структурированный результат без повторного выполнения
    бизнес-логики."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE auth_pending_actions SET result_status = ? WHERE token = ?",
                (result_status, str(token)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to set pending action result: %s", e)
        return False


def cleanup_expired_pending_actions(max_age_hours: int = 72) -> int:
    """Удалить давно истёкшие pending actions (профилактическая очистка,
    не обязательна для корректности — claim_pending_action и без этого не
    применит просроченный токен)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM auth_pending_actions WHERE expires_at < datetime('now', ?)",
                (f"-{int(max_age_hours)} hours",),
            )
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error("Failed to cleanup expired pending actions: %s", e)
        return 0


def get_payment_methods_analytics() -> list[dict]:
    """Аналитика по методам оплаты (Этап 4.5): число транзакций, выручка, успешность, динамика."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COALESCE(payment_method, 'N/A') AS pm,
                       SUM(CASE WHEN status IN ('paid','success','succeeded') THEN 1 ELSE 0 END) AS success_cnt,
                       SUM(CASE WHEN status IN ('paid','success','succeeded') THEN amount_rub ELSE 0 END) AS success_sum,
                       COUNT(*) AS total_cnt
                FROM transactions
                WHERE LOWER(COALESCE(payment_method, '')) <> 'balance'
                GROUP BY pm
                ORDER BY success_sum DESC
                """
            )
            for pm, success_cnt, success_sum, total_cnt in cursor.fetchall() or []:
                total_cnt = int(total_cnt or 0)
                success_cnt = int(success_cnt or 0)
                result.append({
                    "payment_method": pm,
                    "success_transactions": success_cnt,
                    "revenue": float(success_sum or 0.0),
                    "total_attempts": total_cnt,
                    "success_rate_pct": (success_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0,
                })
    except sqlite3.Error as e:
        logging.error(f"Failed to get payment methods analytics: {e}")
    return result


def get_users_without_real_payment_with_keys() -> dict:
    """Пользователи с хотя бы одним VPN-ключом, у которых нет ни одной успешной
    транзакции, оплаченной реальными деньгами.

    Реальными деньгами НЕ считаются payment_method из чёрного списка
    Balance / ReferralBalance (регистр не важен). Проверка идёт по всем успешным
    транзакциям пользователя (включая пополнения баланса), а не только по покупке ключа.
    """
    result = {"users_with_key_no_real_payment": 0}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT k.user_id)
                FROM vpn_keys k
                WHERE k.user_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM transactions t
                      WHERE t.user_id = k.user_id
                        AND {_SUCCESS_TX_SQL}
                        AND {_REAL_MONEY_SQL}
                  )
                """
            )
            result["users_with_key_no_real_payment"] = int((cursor.fetchone() or [0])[0] or 0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get users without real payment with keys: {e}")
    return result


def get_pending_broadcast_recipients(campaign_id: int, interval_hours: int) -> list[int]:
    """Inactive users who haven't been sent this campaign in the last `interval_hours`."""
    inactive = set(get_inactive_subscribers())
    if not inactive:
        return []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT user_id FROM broadcast_sends
                WHERE campaign_id = ?
                  AND sent_at > datetime('now', '-' || ? || ' hours')
                """,
                (int(campaign_id), int(interval_hours)),
            )
            recently_sent = {row[0] for row in cursor.fetchall()}
        return [uid for uid in inactive if uid not in recently_sent]
    except sqlite3.Error as e:
        logging.error("Failed to get pending broadcast recipients: %s", e)
        return []

def _connect_pending_db() -> sqlite3.Connection:
    """Connection helper for high-contention tables (webhooks/bot)."""
    conn = sqlite3.connect(DB_FILE, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn


_PAID_TX_STATUSES = frozenset({"paid", "success", "succeeded", "completed"})
_TERMINAL_TX_STATUSES = _PAID_TX_STATUSES | frozenset(
    {"cancelled", "canceled", "failed", "expired", "chargeback"}
)
_PROVIDER_TX_KEYS = (
    "platega_transaction_id",
    "cryptobot_invoice_id",
    "heleket_uuid",
    "yookassa_payment_id",
    "rollypay_payment_id",
)


def _tx_meta_dict(raw) -> dict:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _provider_transaction_id_from_meta(metadata: dict | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in _PROVIDER_TX_KEYS:
        value = metadata.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _mirror_pending_to_ledger(
    cursor: sqlite3.Cursor,
    payment_id: str,
    user_id: int,
    amount_rub,
    metadata,
    status: str = "pending",
) -> None:
    """Дублирует неоплаченный счёт в ``transactions``, чтобы он был виден в истории.

    Уже оплаченную строку не перезаписывает.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return
    meta = _tx_meta_dict(metadata)
    meta_json = json.dumps(meta, ensure_ascii=False)
    payment_method = meta.get("payment_method")
    try:
        amount = float(amount_rub) if amount_rub is not None else float(meta.get("price") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    username = None
    try:
        cursor.execute("SELECT username FROM users WHERE telegram_id = ?", (int(user_id),))
        row = cursor.fetchone()
        if row:
            username = row[0] if not isinstance(row, sqlite3.Row) else row["username"]
    except Exception:
        username = None

    cursor.execute("SELECT status, metadata FROM transactions WHERE payment_id = ?", (pid,))
    existing = cursor.fetchone()
    if existing:
        current_status = (existing[0] or "").strip().lower()
        if current_status in _TERMINAL_TX_STATUSES:
            return
        cursor.execute(
            """
            UPDATE transactions
               SET username = COALESCE(?, username),
                   user_id = ?,
                   amount_rub = ?,
                   payment_method = COALESCE(?, payment_method),
                   metadata = ?,
                   status = ?
             WHERE payment_id = ?
               AND LOWER(TRIM(COALESCE(status, ''))) NOT IN
                   ('paid', 'success', 'succeeded', 'completed', 'cancelled', 'canceled', 'failed', 'expired')
            """,
            (username, int(user_id), amount, payment_method, meta_json, status, pid),
        )
        return
    cursor.execute(
        """
        INSERT INTO transactions
            (username, payment_id, user_id, status, amount_rub, payment_method, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (username, pid, int(user_id), status, amount, payment_method, meta_json),
    )


def create_payload_pending(payment_id: str, user_id: int, amount_rub, metadata) -> bool:
    """Create/update pending payload metadata.

    Important: does NOT revive already paid rows (keeps status='paid' intact).
    Зеркалит неоплаченный счёт в ``transactions`` (status=pending) вместе с id провайдера.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)

            cursor.execute(
                '''
                INSERT INTO pending_transactions (payment_id, user_id, amount_rub, metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(payment_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    amount_rub = excluded.amount_rub,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
                WHERE pending_transactions.status = 'pending'
                ''',
                (
                    pid,
                    int(user_id),
                    float(amount_rub) if amount_rub is not None else None,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            cursor.execute(
                "SELECT status FROM pending_transactions WHERE payment_id = ?",
                (pid,),
            )
            pending_row = cursor.fetchone()
            pending_status = (pending_row[0] or "").strip().lower() if pending_row else ""
            if pending_status == "pending":
                _mirror_pending_to_ledger(cursor, pid, int(user_id), amount_rub, metadata, status="pending")
            return True

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to create payload pending {pid}: {e}")
        return False


def patch_pending_metadata(payment_id: str, extra: dict) -> bool:
    """Дописывает поля (id провайдера) в pending и в зеркало ``transactions``."""
    pid = (payment_id or "").strip()
    if not pid or not extra:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT user_id, amount_rub, metadata FROM pending_transactions WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            row = cursor.fetchone()
            if not row:
                return False
            meta = _tx_meta_dict(row[2])
            for key, value in extra.items():
                if value not in (None, ""):
                    meta[key] = value
            cursor.execute(
                """
                UPDATE pending_transactions
                   SET metadata = ?, updated_at = CURRENT_TIMESTAMP
                 WHERE payment_id = ? AND status = 'pending'
                """,
                (json.dumps(meta, ensure_ascii=False), pid),
            )
            _mirror_pending_to_ledger(cursor, pid, int(row[0]), row[1], meta, status="pending")
            return True

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to patch pending metadata {pid}: {e}")
        return False


def _get_pending_metadata(payment_id: str) -> dict | None:
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT metadata FROM pending_transactions WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw = row[0] if isinstance(row, (tuple, list)) else row["metadata"]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            meta.setdefault("payment_id", pid)
            return meta

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to read pending transaction {pid}: {e}")
        return None


def get_pending_metadata(payment_id: str) -> dict | None:
    """Public wrapper to fetch pending metadata by payment_id WITHOUT marking it paid."""
    return _get_pending_metadata(payment_id)


def get_pending_record(payment_id: str) -> dict | None:
    """Строка pending_transactions с любым статусом (pending/cancelled/paid)."""
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT user_id, amount_rub, metadata, status FROM pending_transactions WHERE payment_id = ?",
                (pid,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            raw = row[2]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            if not isinstance(meta, dict):
                meta = {}
            meta.setdefault("payment_id", pid)
            return {
                "payment_id": pid,
                "user_id": row[0],
                "amount_rub": row[1],
                "metadata": meta,
                "status": (row[3] or "").strip(),
            }

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to read pending record {pid}: {e}")
        return None


def revive_cancelled_invoice(payment_id: str) -> bool:
    """Вернуть отменённый счёт в pending, если позже пришла реальная оплата."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                """
                UPDATE pending_transactions
                   SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                 WHERE payment_id = ?
                   AND LOWER(TRIM(COALESCE(status, ''))) IN ('cancelled', 'canceled')
                """,
                (pid,),
            )
            revived = cursor.rowcount == 1
            if revived:
                cursor.execute(
                    """
                    UPDATE transactions
                       SET status = 'pending'
                     WHERE payment_id = ?
                       AND LOWER(TRIM(COALESCE(status, ''))) IN ('cancelled', 'canceled')
                    """,
                    (pid,),
                )
            return revived

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to revive cancelled invoice {pid}: {e}")
        return False


def prepare_pending_for_fulfillment(payment_id: str) -> dict | None:
    """Metadata для выдачи: отменённый счёт поднимаем, paid не трогаем."""
    rec = get_pending_record(payment_id)
    if not rec:
        return None
    status = (rec.get("status") or "").strip().lower()
    if status == "paid":
        return None
    if status in ("cancelled", "canceled"):
        revive_cancelled_invoice(payment_id)
    return _get_pending_metadata(payment_id)


def _complete_pending(payment_id: str) -> bool:
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "UPDATE pending_transactions SET status = 'paid', updated_at = CURRENT_TIMESTAMP WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            return cursor.rowcount == 1

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to complete pending transaction {pid}: {e}")
        return False


def find_and_complete_pending_transaction(payment_id: str) -> dict | None:
    """Atomically mark pending transaction as paid and return its metadata.

    Returns None when payment_id is unknown OR already processed.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)

            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "SELECT metadata FROM pending_transactions WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            row = cursor.fetchone()
            if not row:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

            cursor.execute(
                "UPDATE pending_transactions SET status = 'paid', updated_at = CURRENT_TIMESTAMP WHERE payment_id = ? AND status = 'pending'",
                (pid,),
            )
            if cursor.rowcount != 1:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

            conn.commit()

            raw = row[0] if isinstance(row, (tuple, list)) else row["metadata"]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            meta.setdefault("payment_id", pid)
            return meta

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to complete pending transaction {pid}: {e}")
        return None


def get_latest_pending_for_user(user_id: int) -> dict | None:
    """Return metadata of the most recent PENDING transaction for the user (without completing it)."""
    try:
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                """
                SELECT payment_id, metadata
                FROM pending_transactions
                WHERE user_id = ? AND status = 'pending'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            pid = row[0] if isinstance(row, (tuple, list)) else row["payment_id"]
            raw = row[1] if isinstance(row, (tuple, list)) else row["metadata"]
            try:
                meta = json.loads(raw or "{}")
            except Exception:
                meta = {}
            meta.setdefault("payment_id", pid)
            return meta
    except sqlite3.Error as e:
        logging.error(f"Failed to get latest pending for user {user_id}: {e}")
        return None


def claim_processed_payment(payment_id: str) -> bool:
    """Idempotency guard: returns True only once per payment_id."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_processed_payments_table(cursor)
            cursor.execute(
                "INSERT OR IGNORE INTO processed_payments (payment_id, processed_at) VALUES (?, CURRENT_TIMESTAMP)",
                (pid,),
            )
            return cursor.rowcount == 1

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to claim processed payment {pid}: {e}")
        return False


def unclaim_processed_payment(payment_id: str) -> bool:
    """Remove idempotency record so a failed payment can be retried."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_processed_payments_table(cursor)
            cursor.execute("DELETE FROM processed_payments WHERE payment_id = ?", (pid,))
            return cursor.rowcount > 0

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to unclaim processed payment {pid}: {e}")
        return False


def refund_payment_once(
    payment_id: str,
    user_id: int,
    amount: float,
    payment_method: str | None = None,
) -> bool:
    """Вернуть средства за невыданную услугу не более одного раза на payment_id.

    Идемпотентность через ``processed_payments`` с ключом ``refund:{payment_id}`` —
    повторный вызов (retry сети / двойной except) не зачислит сумму дважды.
    Balance → add_to_balance; ReferralBalance → add_to_referral_balance;
    прочие методы (внешние платежи) → add_to_balance (как раньше при сбое выдачи ключа).
    """
    pid = (payment_id or "").strip()
    if not pid or amount is None:
        return False
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return False
    if amount_f <= 0:
        return False

    refund_key = f"refund:{pid}"
    if not claim_processed_payment(refund_key):
        logging.info(
            "refund_payment_once: skip duplicate refund for payment_id=%s user_id=%s",
            pid,
            user_id,
        )
        return False

    pm = (payment_method or "").strip().lower()
    try:
        if pm == "referralbalance":
            ok = bool(add_to_referral_balance(int(user_id), amount_f))
        else:
            ok = bool(add_to_balance(int(user_id), amount_f))
    except Exception as e:
        logging.error(
            "refund_payment_once: credit failed for payment_id=%s user_id=%s: %s",
            pid,
            user_id,
            e,
            exc_info=True,
        )
        ok = False

    if not ok:
        # позволить повторную попытку отката
        try:
            unclaim_processed_payment(refund_key)
        except Exception:
            pass
        return False
    logging.info(
        "refund_payment_once: refunded %.2f via %s for payment_id=%s user_id=%s",
        amount_f,
        pm or "balance",
        pid,
        user_id,
    )
    return True


def cancel_pending_transaction(payment_id: str, user_id: int | None = None) -> bool:
    """Пометить неоплаченный pending как cancelled, чтобы Stars/вебхук его не закрыли.

    Меняет только ``status='pending'``. Уже paid не трогает. Если передан user_id —
    только строка этого владельца.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT user_id, status FROM pending_transactions WHERE payment_id = ?",
                (pid,),
            )
            pending_row = cursor.fetchone()
            if pending_row and user_id is not None and int(pending_row[0]) != int(user_id):
                return False
            pending_status = (pending_row[1] or "").strip().lower() if pending_row else ""
            if pending_status == "paid":
                return False

            pending_cancelled = False
            if pending_status == "pending":
                cursor.execute(
                    """
                    UPDATE pending_transactions
                    SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE payment_id = ? AND status = 'pending'
                    """,
                    (pid,),
                )
                pending_cancelled = cursor.rowcount == 1

            if user_id is not None:
                cursor.execute(
                    """
                    UPDATE transactions
                       SET status = 'cancelled'
                     WHERE payment_id = ?
                       AND user_id = ?
                       AND LOWER(TRIM(COALESCE(status, ''))) = 'pending'
                    """,
                    (pid, int(user_id)),
                )
            else:
                cursor.execute(
                    """
                    UPDATE transactions
                       SET status = 'cancelled'
                     WHERE payment_id = ?
                       AND LOWER(TRIM(COALESCE(status, ''))) = 'pending'
                    """,
                    (pid,),
                )
            ledger_cancelled = cursor.rowcount == 1
            return pending_cancelled or ledger_cancelled or pending_status == "cancelled"

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to cancel pending transaction {pid}: {e}")
        return False


def reset_pending_transaction(payment_id: str) -> bool:
    """Reset a completed pending transaction back to 'pending' to allow webhook retry."""
    pid = (payment_id or "").strip()
    if not pid:
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "UPDATE pending_transactions SET status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE payment_id = ?",
                (pid,),
            )
            return cursor.rowcount > 0

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to reset pending transaction {pid}: {e}")
        return False

def get_balance(user_id: int) -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get balance for user {user_id}: {e}")
        return 0.0

def adjust_user_balance(user_id: int, delta: float) -> bool:
    """Скорректировать баланс пользователя на указанную дельту (может быть отрицательной)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE telegram_id = ?", (float(delta), user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to adjust balance for user {user_id}: {e}")
        return False

def set_balance(user_id: int, value: float) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (value, user_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set balance for user {user_id}: {e}")
        return False

def add_to_balance(user_id: int, amount: float) -> bool:
    try:
        logging.info(f"💳 Добавляем {amount:.2f} RUB к балансу пользователя {user_id}")
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT telegram_id, balance FROM users WHERE telegram_id = ?", (int(user_id),))
            user_row = cursor.fetchone()
            if not user_row:
                logging.error(f"❌ Пользователь {user_id} не найден в базе данных")
                return False
            
            old_balance = user_row[1] or 0.0
            cursor.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE telegram_id = ?",
                (float(amount), int(user_id))
            )
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                new_balance = old_balance + float(amount)
                logging.info(f"✅ Баланс обновлен: пользователь {user_id} | {old_balance:.2f} → {new_balance:.2f} RUB (+{amount:.2f})")
            else:
                logging.error(f"❌ Не удалось обновить баланс для пользователя {user_id}: строки не затронуты")
            return success
    except sqlite3.Error as e:
        logging.error(f"💥 Ошибка базы данных при пополнении баланса для пользователя {user_id}: {e}")
        return False

def deduct_from_balance(user_id: int, amount: float) -> bool:
    """Атомарное списание с основного баланса при достаточности средств."""
    if amount <= 0:
        return True
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
            row = cursor.fetchone()
            current = row[0] if row and row[0] is not None else 0.0
            if current < amount:
                conn.rollback()
                return False
            cursor.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) - ? WHERE telegram_id = ?",
                (float(amount), int(user_id))
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to deduct from balance for user {user_id}: {e}")
        return False

def create_pending_transaction(payment_id: str, user_id: int, amount_rub: float, metadata: dict) -> int:
    """Create a pending transaction row in `transactions`.

    Used for TON Connect flows.
    """
    pid = (payment_id or "").strip()
    if not pid:
        return 0
    try:
        with sqlite3.connect(DB_FILE, timeout=5.0) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass

            _mirror_pending_to_ledger(cursor, pid, int(user_id), amount_rub, metadata, status="pending")
            conn.commit()
            cursor.execute("SELECT transaction_id FROM transactions WHERE payment_id = ?", (pid,))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.Error as e:
        logging.error(f"Failed to create pending transaction: {e}")
        return 0


def find_and_complete_ton_transaction(payment_id: str, amount_ton: float) -> dict | None:
    """Atomically completes a TON transaction.

    - validates transaction exists and is still pending
    - enforces amount check against metadata (expected_amount_ton/ton_amount/amount_ton) when present
    - updates using `WHERE ... AND status='pending'` to ensure idempotency
    """
    pid = (payment_id or "").strip()
    if not pid:
        return None

    try:
        with sqlite3.connect(DB_FILE, timeout=5.0, isolation_level=None) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=5000;")
            except Exception:
                pass

            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT metadata FROM transactions WHERE payment_id = ? AND status = 'pending'", (pid,))
            row = cursor.fetchone()
            if not row:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.warning(f"TON Webhook: payment_id unknown or already processed: {pid}")
                return None

            raw_meta = row['metadata'] if isinstance(row, dict) or hasattr(row, '__getitem__') else None
            try:
                meta = json.loads(raw_meta or "{}")
            except Exception:
                meta = {}

            expected = meta.get('expected_amount_ton')
            if expected is None:
                expected = meta.get('ton_amount')
            if expected is None:
                expected = meta.get('amount_ton')

            exp_val = None
            try:
                if expected is not None:
                    exp_val = float(expected)
            except Exception:
                exp_val = None

            try:
                amt_val = float(amount_ton)
            except Exception:
                amt_val = None

            if exp_val is not None:
                if amt_val is None:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    logger.warning(f"TON Webhook: missing amount for payment_id={pid}; expected={exp_val}")
                    return None
                tol = max(0.001, exp_val * 0.01)
                if abs(amt_val - exp_val) > tol:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    logger.warning(f"TON Webhook: amount mismatch for payment_id={pid}; got={amt_val}, expected={exp_val}, tol={tol}")
                    return None

            cursor.execute(
                "UPDATE transactions SET status = 'paid', amount_currency = ?, currency_name = 'TON', payment_method = 'TON' WHERE payment_id = ? AND status = 'pending'",
                (amt_val if amt_val is not None else amount_ton, pid)
            )
            if cursor.rowcount != 1:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return None

            conn.commit()
            meta.setdefault('payment_id', pid)
            return meta

    except sqlite3.Error as e:
        logging.error(f"Failed to complete TON transaction {pid}: {e}")
        return None
_TX_ACTION_LABELS = {
    "new": "Новый ключ",
    "gift": "Подарок (новый ключ)",
    "extend": "Продление ключа",
    "top_up": "Пополнение баланса",
    "traffic_gb_topup": "Докупка трафика",
    "lte_gb_topup": "Докупка LTE-пула",
    "main_traffic_reset": "Сброс основного трафика",
}

def _describe_transaction_action(metadata: dict) -> dict:
    """Формирует человекочитаемое описание действия транзакции по её metadata."""
    action = (metadata or {}).get("action")
    key_id = metadata.get("key_id") if isinstance(metadata, dict) else None
    try:
        key_id = int(key_id) if key_id not in (None, "", "None") else None
    except Exception:
        key_id = None
    label = _TX_ACTION_LABELS.get(action, "Оплата тарифа" if action is None else action)
    size_gb = metadata.get("size_gb") if isinstance(metadata, dict) else None
    provider_transaction_id = _provider_transaction_id_from_meta(metadata if isinstance(metadata, dict) else None)
    return {
        "action": action,
        "action_label": label,
        "key_id": key_id,
        "size_gb": size_gb,
        "provider_transaction_id": provider_transaction_id,
    }

def _find_nearest_key_id(cursor, user_id: int | None, host_name: str | None, created_date, window_minutes: int = 20) -> int | None:
    """Best-effort подбор ключа для старых транзакций, в metadata которых ещё не сохранялся key_id.
    Ищет ключ того же пользователя (и хоста, если известен), созданный ближе всего по времени
    к моменту транзакции (в пределах window_minutes)."""
    if not user_id or not created_date:
        return None
    try:
        if host_name:
            cursor.execute(
                """SELECT key_id, created_at FROM vpn_keys
                   WHERE user_id = ? AND host_name = ?
                   ORDER BY ABS(strftime('%s', created_at) - strftime('%s', ?)) ASC
                   LIMIT 1""",
                (int(user_id), host_name, str(created_date)),
            )
        else:
            cursor.execute(
                """SELECT key_id, created_at FROM vpn_keys
                   WHERE user_id = ?
                   ORDER BY ABS(strftime('%s', created_at) - strftime('%s', ?)) ASC
                   LIMIT 1""",
                (int(user_id), str(created_date)),
            )
        row = cursor.fetchone()
        if not row:
            return None
        key_id_val, created_at_val = row[0], row[1]
        try:
            diff = abs((datetime.fromisoformat(str(created_at_val).replace('Z', '')) - datetime.fromisoformat(str(created_date).replace('Z', ''))).total_seconds())
            if diff > window_minutes * 60:
                return None
        except Exception:
            pass
        return int(key_id_val) if key_id_val is not None else None
    except Exception:
        return None

def log_transaction(username: str, transaction_id: str | None, payment_id: str | None, user_id: int, status: str, amount_rub: float, amount_currency: float | None, currency_name: str | None, payment_method: str, metadata: str) -> bool:
    """Записывает транзакцию в таблицу `transactions`.

    ВАЖНО: используем устойчивое к блокировкам подключение (WAL + busy_timeout + retry),
    как и остальные высококонкурентные write-пути (см. _connect_pending_db/_retry_sqlite).
    Раньше здесь использовалось обычное sqlite3.connect() без retry: под конкурентной
    нагрузкой (несколько платежей одновременно) запись могла молча "потеряться" из-за
    'database is locked', при этом баланс пользователя уже был обновлён другой функцией —
    из-за этого доход в аналитике не менялся, хотя баланс пополнялся.

    Не бросает исключение наружу (некоторые вызовы в handlers.py не обёрнуты в try/except
    и не должны прерывать выдачу уже оплаченного ключа) — вместо этого возвращает False
    и подробно логирует ошибку, чтобы проблема не оставалась незамеченной.
    """
    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            pid = (str(payment_id).strip() if payment_id is not None else "")
            new_meta = metadata if isinstance(metadata, str) else json.dumps(metadata or {}, ensure_ascii=False)
            if pid:
                cursor.execute(
                    "SELECT metadata FROM transactions WHERE payment_id = ?",
                    (pid,),
                )
                existing = cursor.fetchone()
                if existing:
                    merged = _tx_meta_dict(existing[0])
                    merged.update(_tx_meta_dict(new_meta))
                    cursor.execute(
                        """
                        UPDATE transactions
                           SET username = COALESCE(?, username),
                               user_id = ?,
                               status = ?,
                               amount_rub = ?,
                               amount_currency = COALESCE(?, amount_currency),
                               currency_name = COALESCE(?, currency_name),
                               payment_method = COALESCE(?, payment_method),
                               metadata = ?
                         WHERE payment_id = ?
                        """,
                        (
                            username,
                            user_id,
                            status,
                            amount_rub,
                            amount_currency,
                            currency_name,
                            payment_method,
                            json.dumps(merged, ensure_ascii=False),
                            pid,
                        ),
                    )
                    return True
            cursor.execute(
                """INSERT INTO transactions
                   (username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, created_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, new_meta, datetime.now())
            )
            return True

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logging.error(f"Failed to log transaction for user {user_id}: {e}", exc_info=True)
        return False

def get_paginated_transactions(page: int = 1, per_page: int = 15) -> tuple[list[dict], int]:

    offset = (page - 1) * per_page
    transactions = []
    total = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total = cursor.fetchone()[0]

            query = "SELECT * FROM transactions ORDER BY created_date DESC LIMIT ? OFFSET ?"
            cursor.execute(query, (per_page, offset))
            
            for row in cursor.fetchall():
                transaction_dict = dict(row)
                
                metadata_str = transaction_dict.get('metadata')
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        transaction_dict['host_name'] = metadata.get('host_name', 'N/A')
                        transaction_dict['plan_name'] = metadata.get('plan_name', 'N/A')
                        transaction_dict.update(_describe_transaction_action(metadata))
                    except json.JSONDecodeError:
                        transaction_dict['host_name'] = 'Error'
                        transaction_dict['plan_name'] = 'Error'
                else:
                    transaction_dict['host_name'] = 'N/A'
                    transaction_dict['plan_name'] = 'N/A'
                    transaction_dict.update(_describe_transaction_action({}))

                # Legacy-транзакции (до появления action/key_id в metadata): пытаемся подобрать
                # ключ пользователя, максимально близкий по времени создания к транзакции.
                if not transaction_dict.get('key_id') and transaction_dict.get('action') in (None, 'new', 'extend', 'gift'):
                    host_hint = transaction_dict.get('host_name')
                    host_hint = host_hint if host_hint not in ('N/A', 'Error', None) else None
                    guessed = _find_nearest_key_id(cursor, transaction_dict.get('user_id'), host_hint, transaction_dict.get('created_date'))
                    if guessed:
                        transaction_dict['key_id'] = guessed
                        transaction_dict['key_id_guessed'] = True

                transactions.append(transaction_dict)

    except sqlite3.Error as e:
        logging.error(f"Failed to get paginated transactions: {e}")

    return transactions, total

def get_transactions_paginated(
    page: int = 1,
    per_page: int = 10,
    user_id: int | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
) -> tuple[list[dict], int]:
    """Универсальная выборка транзакций с фильтром по пользователю, поиском и сортировкой."""
    try:
        page_i = max(1, int(page))
    except Exception:
        page_i = 1
    try:
        per_i = max(1, int(per_page))
    except Exception:
        per_i = 10
    offset = (page_i - 1) * per_i

    conditions: list = []
    params: list = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(int(user_id))
    search_q = (search or "").strip()
    if search_q:
        like = f"%{search_q}%"
        conditions.append(
            "(CAST(user_id AS TEXT) LIKE ? OR CAST(transaction_id AS TEXT) LIKE ? OR username LIKE ? OR payment_id LIKE ? OR "
            "payment_method LIKE ? OR status LIKE ? OR metadata LIKE ?)"
        )
        params.extend([like, like, like, like, like, like, like])
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_columns = {
        "date": "created_date",
        "amount": "amount_rub",
        "payment_method": "payment_method",
        "status": "status",
    }
    sort_col = sort_columns.get((sort_by or "").strip(), sort_columns["date"])
    sort_direction = "ASC" if (sort_dir or "").strip().lower() == "asc" else "DESC"
    order_sql = f"ORDER BY {sort_col} {sort_direction}"
    if sort_col != sort_columns["date"]:
        order_sql += ", created_date DESC"

    transactions: list = []
    total = 0
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(f"SELECT COUNT(*) FROM transactions{where_sql}", params)
            total = cursor.fetchone()[0] or 0

            cursor.execute(
                f"""
                SELECT * FROM transactions
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                (*params, per_i, offset),
            )

            for row in cursor.fetchall():
                transaction_dict = dict(row)
                metadata_str = transaction_dict.get('metadata')
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        transaction_dict['host_name'] = metadata.get('host_name', 'N/A')
                        transaction_dict['plan_name'] = metadata.get('plan_name', 'N/A')
                        transaction_dict.update(_describe_transaction_action(metadata))
                    except json.JSONDecodeError:
                        transaction_dict['host_name'] = 'Error'
                        transaction_dict['plan_name'] = 'Error'
                else:
                    transaction_dict['host_name'] = 'N/A'
                    transaction_dict['plan_name'] = 'N/A'
                    transaction_dict.update(_describe_transaction_action({}))

                # Legacy-транзакции (до появления action/key_id в metadata): пытаемся подобрать
                # ключ пользователя, максимально близкий по времени создания к транзакции.
                if not transaction_dict.get('key_id') and transaction_dict.get('action') in (None, 'new', 'extend', 'gift'):
                    host_hint = transaction_dict.get('host_name')
                    host_hint = host_hint if host_hint not in ('N/A', 'Error', None) else None
                    guessed = _find_nearest_key_id(cursor, transaction_dict.get('user_id'), host_hint, transaction_dict.get('created_date'))
                    if guessed:
                        transaction_dict['key_id'] = guessed
                        transaction_dict['key_id_guessed'] = True

                transactions.append(transaction_dict)
    except sqlite3.Error as e:
        logging.error(f"Failed to get filtered transactions: {e}")

    return transactions, int(total)


def get_recent_transactions(limit: int = 15) -> list[dict]:
    transactions: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    k.key_id,
                    k.host_name,
                    k.created_at,
                    u.telegram_id,
                    u.username
                FROM vpn_keys k
                JOIN users u ON k.user_id = u.telegram_id
                ORDER BY datetime(k.created_at) DESC, k.key_id DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cursor.fetchall():
                transactions.append(
                    {
                        "key_id": row["key_id"],
                        "host_name": row["host_name"],
                        "created_at": row["created_at"],
                        "telegram_id": row["telegram_id"],
                        "username": row["username"],
                    }
                )
    except sqlite3.Error as e:
        logging.error("Failed to get recent transactions: %s", e)
    return transactions


def check_transaction_exists(payment_id: str) -> bool:
    """Проверить, существует ли уже завершённая транзакция с данным payment_id.

    TON Connect пишет в ``transactions`` строку со ``status='pending'`` ещё до
    подтверждения в блокчейне. Раньше этот SELECT не фильтровал статус — из-за
    этого ``/api/check-payment`` отвечал ``paid: true`` сразу после создания
    счёта. Финальный статус TON-вебхука — ``paid`` (см. find_and_complete_ton_transaction).
    """
    if not payment_id:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 1 FROM transactions
                WHERE payment_id = ?
                  AND LOWER(TRIM(COALESCE(status, ''))) = 'paid'
                LIMIT 1
                """,
                (str(payment_id),),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check transaction existence for {payment_id}: {e}")
        return False


def payment_owned_by_user(payment_id: str, user_id: int) -> bool:
    """True, если payment_id есть в pending_transactions или transactions у этого user_id.

    Статус не фильтруем: владелец должен иметь возможность поллить и pending,
    и уже оплаченный счёт. Чужой payment_id даёт False (без различия «нет» / «чужой»).
    """
    pid = (payment_id or "").strip()
    if not pid:
        return False
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute(
                "SELECT 1 FROM pending_transactions WHERE payment_id = ? AND user_id = ? LIMIT 1",
                (pid, uid),
            )
            if cursor.fetchone() is not None:
                return True
            cursor.execute(
                "SELECT 1 FROM transactions WHERE payment_id = ? AND user_id = ? LIMIT 1",
                (pid, uid),
            )
            return cursor.fetchone() is not None

    try:
        return bool(_retry_sqlite(_work))
    except sqlite3.Error as e:
        logger.error(f"Failed to check payment ownership for {pid}: {e}")
        return False


def set_pending_email(user_id: int, new_email: str) -> bool:
    """Сохранить новый email, ожидающий подтверждения кодом (смена почты из профиля).
    Текущий auth_email остаётся действующим для входа, пока код не подтверждён."""
    norm = _normalize_email(new_email)
    if not norm:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET pending_email = ? WHERE telegram_id = ?", (norm, int(user_id)))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to set pending email for user {user_id}: {e}")
        return False


def clear_pending_email(user_id: int) -> bool:
    """Отменить ожидающую смену email (например, пользователь передумал или запросил другой адрес)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET pending_email = NULL, email_code_hash = NULL, email_code_expires_at = NULL "
                "WHERE telegram_id = ?",
                (int(user_id),),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to clear pending email for user {user_id}: {e}")
        return False


def finalize_pending_email_change(user_id: int) -> tuple[bool, str | None]:
    """Подтвердить смену email кодом: перенести `pending_email` в `auth_email`.

    Атомарно перепроверяет, что новый адрес не был занят другим аккаунтом за время
    ожидания кода (защита от гонки, если два пользователя одновременно решили
    переключиться на один и тот же email). Возвращает (ok, new_email_или_текст_ошибки).
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT pending_email FROM users WHERE telegram_id = ?", (int(user_id),))
            row = cur.fetchone()
            pending = row["pending_email"] if row else None
            if not pending:
                return False, "Нет ожидающей смены email"

            cur.execute(
                "SELECT telegram_id FROM users WHERE auth_email = ? AND telegram_id != ?",
                (pending, int(user_id)),
            )
            if cur.fetchone():
                cur.execute(
                    "UPDATE users SET pending_email = NULL, email_code_hash = NULL, email_code_expires_at = NULL "
                    "WHERE telegram_id = ?",
                    (int(user_id),),
                )
                conn.commit()
                return False, "Этот email уже используется другим аккаунтом"

            cur.execute(
                """
                UPDATE users
                SET auth_email = ?, pending_email = NULL, email_verified = 1,
                    email_code_hash = NULL, email_code_expires_at = NULL
                WHERE telegram_id = ?
                """,
                (pending, int(user_id)),
            )
            conn.commit()
            return True, pending
    except sqlite3.IntegrityError:
        return False, "Этот email уже используется другим аккаунтом"
    except Exception as e:
        logger.error(f"Failed to finalize pending email change for user {user_id}: {e}")
        return False, "Ошибка базы данных"
