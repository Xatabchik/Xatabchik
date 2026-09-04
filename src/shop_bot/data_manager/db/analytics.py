"""Аналитика и отчёты: метрики ресурсов, выручка, экономика и затраты на серверы.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
import json

__all__ = (
    "insert_resource_metric",
    "get_latest_resource_metric",
    "get_metrics_series",
    "get_speedtests",
    "get_latest_speedtest",
    "get_admin_stats",
    "get_sales_overview",
    "get_revenue_series",
    "get_trial_key_stats",
    "get_top_buyers",
    "get_coupons_analytics",
    "get_server_cost_entries",
    "create_server_cost_entry",
    "update_server_cost_entry",
    "delete_server_cost_entry",
    "get_economics_summary",
    "get_revenue_forecast",
    "get_broadcast_stats",
    "get_pending_status",
    "update_user_stats",
    "get_total_spent_sum",
    "update_key_status_from_server",
    "get_daily_stats_for_charts",
    "get_reachability_stats",
)


def insert_resource_metric(
    scope: str,
    object_name: str,
    *,
    cpu_percent: float | None = None,
    mem_percent: float | None = None,
    disk_percent: float | None = None,
    load1: float | None = None,
    net_bytes_sent: int | None = None,
    net_bytes_recv: int | None = None,
    raw_json: str | None = None,
) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO resource_metrics (
                    scope, object_name, cpu_percent, mem_percent, disk_percent, load1,
                    net_bytes_sent, net_bytes_recv, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    (scope or '').strip(),
                    (object_name or '').strip(),
                    cpu_percent, mem_percent, disk_percent, load1,
                    net_bytes_sent, net_bytes_recv, raw_json,
                )
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error("Failed to insert resource metric for %s/%s: %s", scope, object_name, e)
        return None


def get_latest_resource_metric(scope: str, object_name: str) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT * FROM resource_metrics
                WHERE scope = ? AND object_name = ?
                ORDER BY created_at DESC
                LIMIT 1
                ''',
                ((scope or '').strip(), (object_name or '').strip())
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error("Failed to get latest resource metric for %s/%s: %s", scope, object_name, e)
        return None


def get_metrics_series(scope: str, object_name: str, *, since_hours: int = 24, limit: int = 500) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            


            if since_hours == 1:
                hours_filter = 2
            else:
                hours_filter = max(1, int(since_hours))
            

            cursor.execute(
                f'''
                SELECT created_at, cpu_percent, mem_percent, disk_percent, load1
                FROM resource_metrics
                WHERE scope = ? AND object_name = ?
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at ASC
                LIMIT ?
                ''',
                (
                    (scope or '').strip(),
                    (object_name or '').strip(),
                    f'-{hours_filter} hours',
                    max(10, int(limit)),
                )
            )
            rows = cursor.fetchall() or []
            

            logging.debug(f"get_metrics_series: {scope}/{object_name}, since_hours={since_hours}, found {len(rows)} records")
            
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get metrics series for %s/%s: %s", scope, object_name, e)
        return []

def get_speedtests(host_name: str, limit: int = 20) -> list[dict]:
    """Получить последние результаты спидтестов по хосту (ssh/net), новые сверху."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                limit_int = int(limit)
            except Exception:
                limit_int = 20
            cursor.execute(
                """
                SELECT id, host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps,
                       server_name, server_id, ok, error, created_at
                FROM host_speedtests
                WHERE TRIM(host_name) = TRIM(?)
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (host_name_n, limit_int),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить speedtest-данные для хоста '{host_name}': {e}")
        return []

def get_latest_speedtest(host_name: str) -> dict | None:
    """Получить последний по времени спидтест для хоста."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps,
                       server_name, server_id, ok, error, created_at
                FROM host_speedtests
                WHERE TRIM(host_name) = TRIM(?)
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """,
                (host_name_n,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить последний speedtest для хоста '{host_name}': {e}")
        return None

def get_admin_stats() -> dict:
    """Return aggregated statistics for the admin dashboard.
    Includes:
    - total_users: count of users
    - total_keys: count of all keys
    - active_keys: keys with expire_at in the future
    - total_income: sum of amount_rub for successful transactions
    """
    stats = {
        "total_users": 0,
        "total_keys": 0,
        "active_keys": 0,
        "total_income": 0.0,

        "today_new_users": 0,
        "today_income": 0.0,
        "today_issued_keys": 0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users")
            row = cursor.fetchone()
            stats["total_users"] = (row[0] or 0) if row else 0


            cursor.execute("SELECT COUNT(*) FROM vpn_keys")
            row = cursor.fetchone()
            stats["total_keys"] = (row[0] or 0) if row else 0


            cursor.execute("SELECT COUNT(*) FROM vpn_keys WHERE expire_at IS NOT NULL AND datetime(expire_at) > CURRENT_TIMESTAMP")
            row = cursor.fetchone()
            stats["active_keys"] = (row[0] or 0) if row else 0


            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_rub), 0)
                FROM transactions
                WHERE status IN ('paid','success','succeeded')
                  AND LOWER(COALESCE(payment_method, '')) NOT IN ('balance', 'referral_transfer', 'referral_payout', 'referraltransfer')
                """
            )
            row = cursor.fetchone()
            stats["total_income"] = float(row[0] or 0.0) if row else 0.0



            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE date(registration_date) = date('now')"
            )
            row = cursor.fetchone()
            stats["today_new_users"] = (row[0] or 0) if row else 0


            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_rub), 0)
                FROM transactions
                WHERE status IN ('paid','success','succeeded')
                  AND date(created_date) = date('now')
                  AND LOWER(COALESCE(payment_method, '')) NOT IN ('balance', 'referral_transfer', 'referral_payout', 'referraltransfer')
                """
            )
            row = cursor.fetchone()
            stats["today_income"] = float(row[0] or 0.0) if row else 0.0


            cursor.execute(
                "SELECT COUNT(*) FROM vpn_keys WHERE date(COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)) = date('now')"
            )
            row = cursor.fetchone()
            stats["today_issued_keys"] = (row[0] or 0) if row else 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get admin stats: {e}")
    return stats


def get_sales_overview() -> dict:
    """Главный дашборд продаж (Этап 4.1 плана): выручка/транзакции/чек/плательщики
    за сегодня, 7, 30 дней и всё время + неуспешные/ожидающие платежи.
    Переиспользует те же SQL-условия успешности, что get_admin_stats()/statistics_page().
    """
    periods = {"today": 0, "d7": 7, "d30": 30, "all": None}
    result: dict = {}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for key, days in periods.items():
                if key == "today":
                    date_filter = "date(created_date) = date('now')"
                elif days is None:
                    date_filter = "1=1"
                else:
                    date_filter = f"date(created_date) >= date('now', '-{int(days) - 1} days')"

                cursor.execute(
                    f"""
                    SELECT COUNT(*), COALESCE(SUM(amount_rub), 0), COUNT(DISTINCT user_id)
                    FROM transactions
                    WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL} AND {date_filter}
                    """
                )
                cnt, revenue, unique_payers = cursor.fetchone() or (0, 0.0, 0)
                cnt = int(cnt or 0)
                revenue = float(revenue or 0.0)
                result[key] = {
                    "transactions": cnt,
                    "revenue": revenue,
                    "unique_payers": int(unique_payers or 0),
                    "avg_check": (revenue / cnt) if cnt > 0 else 0.0,
                }

            # Неуспешные / ожидающие / отменённые (за всё время)
            cursor.execute(
                f"""
                SELECT status, COUNT(*)
                FROM transactions
                WHERE NOT ({_SUCCESS_TX_SQL})
                GROUP BY status
                """
            )
            status_breakdown = {row[0] or "unknown": int(row[1] or 0) for row in cursor.fetchall()}
            result["failed_or_pending_by_status"] = status_breakdown

            cursor.execute("SELECT COUNT(*) FROM pending_transactions WHERE status = 'pending'")
            row = cursor.fetchone()
            result["pending_payments"] = int((row[0] if row else 0) or 0)

            # Новые / повторные плательщики (по первой успешной транзакции пользователя)
            cursor.execute(
                f"""
                WITH first_tx AS (
                    SELECT user_id, MIN(date(created_date)) AS first_day
                    FROM transactions
                    WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                    GROUP BY user_id
                )
                SELECT
                    SUM(CASE WHEN first_day >= date('now', '-29 days') THEN 1 ELSE 0 END) AS new_payers_30d,
                    COUNT(*) AS total_payers
                FROM first_tx
                """
            )
            new_payers_30d, total_payers = cursor.fetchone() or (0, 0)
            result["new_payers_30d"] = int(new_payers_30d or 0)
            result["total_payers"] = int(total_payers or 0)

            # Повторные покупки: доля плательщиков с >=2 успешными транзакциями
            cursor.execute(
                f"""
                SELECT
                    SUM(CASE WHEN cnt >= 2 THEN 1 ELSE 0 END) AS repeat_payers,
                    COUNT(*) AS all_payers
                FROM (
                    SELECT user_id, COUNT(*) AS cnt
                    FROM transactions
                    WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                    GROUP BY user_id
                )
                """
            )
            repeat_payers, all_payers = cursor.fetchone() or (0, 0)
            repeat_payers = int(repeat_payers or 0)
            all_payers = int(all_payers or 0)
            result["repeat_payers"] = repeat_payers
            result["repeat_conversion_pct"] = (repeat_payers / all_payers * 100.0) if all_payers > 0 else 0.0

            # MRR (оценочный): успешные платежи за последние 30 дней по тарифам с months/duration_days,
            # нормализованные к месяцу. Явно помечается в UI как оценка.
            cursor.execute(
                f"""
                SELECT metadata, amount_rub
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND date(created_date) >= date('now', '-29 days')
                """
            )
            mrr_estimate = 0.0
            for meta_str, amount in cursor.fetchall() or []:
                try:
                    meta = json.loads(meta_str) if meta_str else {}
                except Exception:
                    meta = {}
                months = meta.get("months") if isinstance(meta, dict) else None
                try:
                    months_f = float(months) if months else 1.0
                    if months_f <= 0:
                        months_f = 1.0
                except Exception:
                    months_f = 1.0
                try:
                    mrr_estimate += float(amount or 0.0) / months_f
                except Exception:
                    pass
            result["mrr_estimate"] = mrr_estimate
    except sqlite3.Error as e:
        logging.error(f"Failed to get sales overview: {e}")
    return result


def get_revenue_series(days: int = 30) -> dict:
    """Ряд выручки/транзакций по дням для графика раздела «Продажи и аналитика».
    Использует тот же SQL-фильтр успешности, что и get_sales_overview()."""
    series = {"revenue": {}, "transactions": {}}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT date(created_date) AS day, COALESCE(SUM(amount_rub), 0), COUNT(*)
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND date(created_date) >= date('now', ?)
                GROUP BY day
                ORDER BY day
                """,
                (f"-{max(1, int(days)) - 1} days",),
            )
            for day, revenue, cnt in cursor.fetchall() or []:
                series["revenue"][day] = float(revenue or 0.0)
                series["transactions"][day] = int(cnt or 0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get revenue series: {e}")
    return series


def get_trial_key_stats() -> dict:
    """Метрики по триальным ключам и их продлениям.

    - active_trial_users: пользователи с ключом tag='trial' и expire_at в будущем
    - total_trial_used: users.trial_used = 1
    - extended_trial_*: DISTINCT user_id с успешной транзакцией action='extend',
      где metadata.key_id указывает на первый ключ пользователя (trial выдаётся
      первым), и users.trial_used = 1.

    Важно: при продлении key_id НЕ меняется (UPDATE vpn_keys), но tag
    перезаписывается на 'paid' (см. process_successful_payment в bot/handlers.py),
    поэтому нельзя фильтровать текущий tag='trial' для продлений — используем
    связку «первый ключ пользователя» + trial_used.
    """
    result = {
        "active_trial_users": 0,
        "total_trial_used": 0,
        "extended_trial_real_money": 0,
        "extended_trial_via_referral_balance": 0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id)
                FROM vpn_keys
                WHERE LOWER(COALESCE(tag, '')) = 'trial'
                  AND expire_at IS NOT NULL
                  AND datetime(expire_at) > CURRENT_TIMESTAMP
                """
            )
            result["active_trial_users"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute("SELECT COUNT(*) FROM users WHERE trial_used = 1")
            result["total_trial_used"] = int((cursor.fetchone() or [0])[0] or 0)

            # Первый ключ пользователя (по created_at, затем key_id).
            # Продление триала: action=extend + metadata.key_id == этот первый ключ.
            first_key_match_sql = """
                CAST(json_extract(t.metadata, '$.key_id') AS INTEGER) = (
                    SELECT k2.key_id
                    FROM vpn_keys k2
                    WHERE k2.user_id = t.user_id
                    ORDER BY datetime(COALESCE(k2.created_at, '1970-01-01')) ASC, k2.key_id ASC
                    LIMIT 1
                )
            """

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT t.user_id)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.trial_used = 1
                  AND {_SUCCESS_TX_SQL}
                  AND {_REAL_MONEY_SQL}
                  AND json_extract(t.metadata, '$.action') = 'extend'
                  AND json_extract(t.metadata, '$.key_id') IS NOT NULL
                  AND {first_key_match_sql}
                """
            )
            result["extended_trial_real_money"] = int((cursor.fetchone() or [0])[0] or 0)

            cursor.execute(
                f"""
                SELECT COUNT(DISTINCT t.user_id)
                FROM transactions t
                JOIN users u ON u.telegram_id = t.user_id
                WHERE u.trial_used = 1
                  AND {_SUCCESS_TX_SQL}
                  AND LOWER(COALESCE(t.payment_method, '')) = 'referralbalance'
                  AND json_extract(t.metadata, '$.action') = 'extend'
                  AND json_extract(t.metadata, '$.key_id') IS NOT NULL
                  AND {first_key_match_sql}
                """
            )
            result["extended_trial_via_referral_balance"] = int((cursor.fetchone() or [0])[0] or 0)
    except sqlite3.Error as e:
        logging.error(f"Failed to get trial key stats: {e}")
    return result


def get_top_buyers(limit: int = 10) -> list[dict]:
    """Топ пользователей по покупкам (Этап 6.4): сумма, число успешных транзакций, средний чек."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    t.user_id,
                    u.username,
                    u.total_spent,
                    COUNT(*) AS successful_tx,
                    COALESCE(SUM(t.amount_rub), 0) AS revenue
                FROM transactions t
                LEFT JOIN users u ON u.telegram_id = t.user_id
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                GROUP BY t.user_id
                ORDER BY revenue DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            for row in cursor.fetchall():
                d = dict(row)
                cnt = int(d.get("successful_tx") or 0)
                d["avg_check"] = (float(d.get("revenue") or 0.0) / cnt) if cnt > 0 else 0.0
                result.append(d)
    except sqlite3.Error as e:
        logging.error(f"Failed to get top buyers: {e}")
    return result


def get_coupons_analytics() -> list[dict]:
    """Аналитика купонов/промокодов (Этап 6.3) поверх существующих таблиц
    promo_codes / promo_code_usages — без создания новой системы купонов."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
            codes = [dict(r) for r in cursor.fetchall()]

            cursor.execute(
                """
                SELECT code, COUNT(*) AS uses, COALESCE(SUM(applied_amount), 0) AS discount_sum
                FROM promo_code_usages
                GROUP BY code
                """
            )
            usage_map = {row["code"]: dict(row) for row in cursor.fetchall()}

            # Выручка по купону: сопоставляем order_id использования с payment_id транзакции,
            # при отсутствии совпадения по order_id пробуем найти по user_id+ближайшему времени.
            cursor.execute(
                f"""
                SELECT payment_id, user_id, amount_rub, created_date
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            tx_by_payment_id = {}
            tx_by_user: dict[int, list] = {}
            for payment_id, user_id, amount_rub, created_date in cursor.fetchall() or []:
                if payment_id:
                    tx_by_payment_id[payment_id] = float(amount_rub or 0.0)
                tx_by_user.setdefault(user_id, []).append(float(amount_rub or 0.0))

            cursor.execute("SELECT code, order_id, user_id FROM promo_code_usages")
            revenue_by_code: dict[str, float] = {}
            for code, order_id, user_id in cursor.fetchall() or []:
                amount = None
                if order_id and order_id in tx_by_payment_id:
                    amount = tx_by_payment_id[order_id]
                elif user_id in tx_by_user and tx_by_user[user_id]:
                    amount = tx_by_user[user_id][0]
                if amount is not None:
                    revenue_by_code[code] = revenue_by_code.get(code, 0.0) + amount

            for c in codes:
                code = c["code"]
                usage = usage_map.get(code, {"uses": 0, "discount_sum": 0.0})
                uses = int(usage.get("uses") or 0)
                limit_total = c.get("usage_limit_total")
                c["uses"] = uses
                c["discount_sum"] = float(usage.get("discount_sum") or 0.0)
                c["revenue"] = float(revenue_by_code.get(code, 0.0))
                c["usage_conversion_pct"] = (uses / limit_total * 100.0) if limit_total else None
                try:
                    c["is_expired"] = bool(c.get("valid_until")) and str(c["valid_until"]) < _now_str()
                except Exception:
                    c["is_expired"] = False
                c["days_left"] = None
                if c.get("valid_until") and not c["is_expired"]:
                    try:
                        vu_raw = str(c["valid_until"])
                        vu_dt = datetime.fromisoformat(vu_raw.replace(" ", "T")) if "T" not in vu_raw else datetime.fromisoformat(vu_raw)
                        delta = vu_dt - datetime.now()
                        c["days_left"] = max(0, delta.days + (1 if delta.seconds > 0 else 0))
                    except Exception:
                        c["days_left"] = None
                c["targeting_plans_label"] = _promo_plans_label(c.get("applicable_plan_ids"))
                c["targeting_segment_label"] = _promo_segment_label(c.get("segment_type"), c.get("segment_value"))
                result.append(c)

            result.sort(key=lambda c: c["revenue"], reverse=True)
    except sqlite3.Error as e:
        logging.error(f"Failed to get coupons analytics: {e}")
    return result


def get_server_cost_entries(*, only_active: bool = False) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM server_cost_entries"
            if only_active:
                query += " WHERE status = 'active'"
            query += " ORDER BY created_at DESC"
            cursor.execute(query)
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get server cost entries: {e}")
        return []


def create_server_cost_entry(
    server_label: str,
    *,
    linked_host_name: str | None = None,
    provider: str | None = None,
    location: str | None = None,
    monthly_cost: float = 0.0,
    currency: str = "RUB",
    status: str = "active",
    started_at=None,
    ended_at=None,
    comment: str | None = None,
) -> int | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO server_cost_entries
                    (server_label, linked_host_name, provider, location, monthly_cost, currency, status, started_at, ended_at, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (server_label or "").strip(),
                    (linked_host_name or None),
                    (provider or None),
                    (location or None),
                    float(monthly_cost or 0.0),
                    (currency or "RUB").strip() or "RUB",
                    (status or "active").strip() or "active",
                    started_at,
                    ended_at,
                    (comment or None),
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to create server cost entry: {e}")
        return None


def update_server_cost_entry(entry_id: int, **fields) -> bool:
    allowed = {
        "server_label", "linked_host_name", "provider", "location",
        "monthly_cost", "currency", "status", "started_at", "ended_at", "comment",
    }
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return False
    sets.append("updated_at = CURRENT_TIMESTAMP")
    params.append(int(entry_id))
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE server_cost_entries SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update server cost entry {entry_id}: {e}")
        return False


def delete_server_cost_entry(entry_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM server_cost_entries WHERE id = ?", (int(entry_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete server cost entry {entry_id}: {e}")
        return False


def get_economics_summary() -> dict:
    """Приблизительная экономика (Этап 7.3): расходы по провайдеру/локации,
    итог расходов, сопоставление с выручкой за 30 дней (без точной unit-экономики)."""
    result = {
        "total_monthly_cost_by_currency": {},
        "by_provider": [],
        "by_location": [],
        "revenue_30d": 0.0,
        "gross_profit_estimate_by_currency": {},
    }
    try:
        entries = get_server_cost_entries(only_active=True)
        by_provider: dict[str, float] = {}
        by_location: dict[str, float] = {}
        by_currency: dict[str, float] = {}
        for e in entries:
            cost = float(e.get("monthly_cost") or 0.0)
            currency = e.get("currency") or "RUB"
            provider = e.get("provider") or "N/A"
            location = e.get("location") or "N/A"
            by_provider[provider] = by_provider.get(provider, 0.0) + cost
            by_location[location] = by_location.get(location, 0.0) + cost
            by_currency[currency] = by_currency.get(currency, 0.0) + cost

        result["total_monthly_cost_by_currency"] = by_currency
        result["by_provider"] = [{"provider": k, "monthly_cost": v} for k, v in sorted(by_provider.items(), key=lambda x: -x[1])]
        result["by_location"] = [{"location": k, "monthly_cost": v} for k, v in sorted(by_location.items(), key=lambda x: -x[1])]

        overview = get_sales_overview()
        revenue_30d = float((overview.get("d30") or {}).get("revenue") or 0.0)
        result["revenue_30d"] = revenue_30d
        # Оценка маржи только для RUB (основная валюта проекта), остальные валюты — только расходы без сопоставления.
        rub_cost = by_currency.get("RUB", 0.0)
        result["gross_profit_estimate_by_currency"]["RUB"] = revenue_30d - rub_cost
    except Exception as e:
        logging.error(f"Failed to get economics summary: {e}")
    return result


def get_revenue_forecast() -> dict:
    """Прозрачный прогноз (Этап 4.6/9): скользящее среднее за 7 дней + линейная
    экстраполяция до конца текущего месяца. Помечается как оценка в UI."""
    from calendar import monthrange
    result = {
        "daily_avg_revenue_7d": 0.0,
        "daily_avg_transactions_7d": 0.0,
        "revenue_so_far_this_month": 0.0,
        "days_left_in_month": 0,
        "forecast_revenue_month_end": 0.0,
        "forecast_transactions_month_end": 0,
    }
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(amount_rub), 0), COUNT(*)
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND date(created_date) >= date('now', '-6 days')
                """
            )
            rev7, cnt7 = cursor.fetchone() or (0.0, 0)
            daily_avg_revenue = float(rev7 or 0.0) / 7.0
            daily_avg_tx = float(cnt7 or 0) / 7.0

            now = datetime.now()
            days_in_month = monthrange(now.year, now.month)[1]
            days_left = max(0, days_in_month - now.day)

            cursor.execute(
                f"""
                SELECT COALESCE(SUM(amount_rub), 0), COUNT(*)
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                  AND strftime('%Y-%m', created_date) = strftime('%Y-%m', 'now')
                """
            )
            rev_month, cnt_month = cursor.fetchone() or (0.0, 0)

            result["daily_avg_revenue_7d"] = daily_avg_revenue
            result["daily_avg_transactions_7d"] = daily_avg_tx
            result["revenue_so_far_this_month"] = float(rev_month or 0.0)
            result["days_left_in_month"] = days_left
            result["forecast_revenue_month_end"] = float(rev_month or 0.0) + daily_avg_revenue * days_left
            result["forecast_transactions_month_end"] = int(cnt_month or 0) + round(daily_avg_tx * days_left)
    except Exception as e:
        logging.error(f"Failed to get revenue forecast: {e}")
    return result


def get_broadcast_stats(campaign_id: int) -> dict:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), MAX(sent_at) FROM broadcast_sends WHERE campaign_id = ?", (int(campaign_id),))
            row = cursor.fetchone()
            return {"total_sends": int(row[0] or 0), "last_sent_at": row[1]}
    except sqlite3.Error as e:
        logging.error("Failed to get broadcast stats for campaign %s: %s", campaign_id, e)
        return {"total_sends": 0, "last_sent_at": None}


def get_pending_status(payment_id: str) -> str | None:
    """Return status of pending transaction: 'pending', 'paid', or None if not found."""
    pid = (payment_id or "").strip()
    if not pid:
        return None

    def _work():
        with _connect_pending_db() as conn:
            cursor = conn.cursor()
            _ensure_pending_tables(cursor)
            cursor.execute("SELECT status FROM pending_transactions WHERE payment_id = ?", (pid,))
            row = cursor.fetchone()
            if not row:
                return None
            return (row[0] or "").strip() or None

    try:
        return _retry_sqlite(_work)
    except sqlite3.Error as e:
        logging.error(f"Failed to get status for pending {pid}: {e}")
        return None

def update_user_stats(telegram_id: int, amount_spent: float, months_purchased: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET total_spent = total_spent + ?, total_months = total_months + ? WHERE telegram_id = ?", (amount_spent, months_purchased, telegram_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to update user stats for {telegram_id}: {e}")

def get_total_spent_sum() -> float:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COALESCE(SUM(amount_rub), 0.0)
                FROM transactions
                WHERE LOWER(COALESCE(status, '')) IN ('paid', 'completed', 'success')
                  AND LOWER(COALESCE(payment_method, '')) <> 'balance'
                """
            )
            val = cursor.fetchone()
            return (val[0] if val else 0.0) or 0.0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total spent sum: {e}")
        return 0.0


def update_key_status_from_server(key_email: str, client_data) -> bool:
    try:
        normalized_email = _normalize_email(key_email) or key_email.strip()
        existing = get_key_by_email(normalized_email)
        if client_data:
            if isinstance(client_data, dict):
                remote_uuid = client_data.get('uuid') or client_data.get('id')
                expire_value = client_data.get('expireAt') or client_data.get('expiryDate')
                subscription_url = client_data.get('subscriptionUrl') or client_data.get('subscription_url')
                expiry_ms = None
                if expire_value:
                    try:
                        remote_dt = datetime.fromisoformat(str(expire_value).replace('Z', '+00:00'))
                        expiry_ms = int(remote_dt.timestamp() * 1000)
                    except Exception:
                        expiry_ms = None
            else:
                remote_uuid = getattr(client_data, 'id', None) or getattr(client_data, 'uuid', None)
                expiry_ms = getattr(client_data, 'expiry_time', None)
                subscription_url = getattr(client_data, 'subscription_url', None)
            if not existing:
                return False
            return update_key_fields(
                existing['key_id'],
                remnawave_user_uuid=remote_uuid,
                expire_at_ms=expiry_ms,
                subscription_url=subscription_url,
                missing_from_server_at=None,
            )
        if existing:
            # Не удаляем ключ сразу, т.к. временные сбои Remnawave/пагинация
            # могут приводить к ложному отсутствию ключа в списке пользователей.
            # Вместо этого помечаем время, когда ключ последний раз не был найден на сервере.
            return update_key_fields(
                existing["key_id"],
                missing_from_server_at=_now_str(),
            )
        return True
    except sqlite3.Error as e:
        logging.error("Failed to update key status for %s: %s", key_email, e)
        return False


def get_daily_stats_for_charts(days: int = 30) -> dict:
    stats = {'users': {}, 'keys': {}}
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT date(registration_date) AS day, COUNT(*)
                FROM users
                WHERE registration_date >= date('now', ?)
                GROUP BY day
                ORDER BY day
                """,
                (f'-{days} days',),
            )
            for day, count in cursor.fetchall():
                stats['users'][day] = count

            cursor.execute(
                """
                SELECT date(COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)) AS day, COUNT(*)
                FROM vpn_keys
                WHERE COALESCE(created_at, updated_at, CURRENT_TIMESTAMP) >= date('now', ?)
                GROUP BY day
                ORDER BY day
                """,
                (f'-{days} days',),
            )
            for day, count in cursor.fetchall():
                stats['keys'][day] = count
    except sqlite3.Error as e:
        logging.error("Failed to get daily stats for charts: %s", e)
    return stats

def get_reachability_stats() -> dict:
    """Статистика по доступности пользователей в Telegram: сколько всего
    пользователей, сколько реально доступны (не забанены и не недоступны),
    сколько заблокировали бота, сколько деактивировали аккаунт."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN is_banned = 1 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_unreachable = 1 AND unreachable_reason = 'blocked' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN is_unreachable = 1 AND unreachable_reason = 'deactivated' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN (is_unreachable IS NULL OR is_unreachable = 0) AND is_banned = 0 THEN 1 ELSE 0 END)
                FROM users
                """
            )
            row = cursor.fetchone()
            total, banned, blocked_bot, deactivated, reachable = row if row else (0, 0, 0, 0, 0)
            return {
                "total": int(total or 0),
                "banned": int(banned or 0),
                "blocked_bot": int(blocked_bot or 0),
                "deactivated": int(deactivated or 0),
                "reachable": int(reachable or 0),
            }
    except sqlite3.Error as e:
        logging.error(f"Failed to get reachability stats: {e}")
        return {"total": 0, "banned": 0, "blocked_bot": 0, "deactivated": 0, "reachable": 0}
