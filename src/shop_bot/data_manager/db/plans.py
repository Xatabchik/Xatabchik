"""Тарифные планы, пакеты трафика и уровни устройств.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
import json
from typing import Any

from ._core import _UNSET

__all__ = (
    "plan_main_limit_bytes",
    "plan_has_monthly_traffic_reset",
    "parse_plan_id_from_key",
    "resolve_plan_for_key",
    "get_plans_analytics",
    "create_plan",
    "set_plan_active",
    "get_plan_by_id",
    "get_all_plans",
    "update_plan_metadata",
    "create_traffic_package",
    "get_traffic_packages_for_plan",
    "get_traffic_package_by_id",
    "update_traffic_package",
    "delete_traffic_package",
    "delete_plan",
    "update_plan",
    "get_device_tiers",
)


def plan_main_limit_bytes(plan: dict | None) -> int:
    return _as_limit_bytes((plan or {}).get("traffic_limit_bytes"))


def plan_has_monthly_traffic_reset(plan: dict | None) -> bool:
    """Ежемесячный сброс нужен, если ограничен основной пул и/или LTE."""
    return plan_main_limit_bytes(plan) > 0 or plan_lte_limit_bytes(plan) > 0


def parse_plan_id_from_key(key: dict | None) -> int | None:
    desc = (key or {}).get("description")
    if isinstance(desc, str) and desc.strip().startswith("{"):
        try:
            meta = json.loads(desc)
            if isinstance(meta, dict) and meta.get("plan_id") not in (None, "", "None"):
                return int(meta.get("plan_id"))
        except Exception:
            return None
    return None


def resolve_plan_for_key(key: dict | None, *, allow_host_fallback: bool = True) -> dict | None:
    """Тариф ключа: plan_id из description, иначе первый активный тариф хоста.

    Fallback на тариф хоста не применяется к триалам и подаркам — у них нет
    биллинг-тарифа, даже если на хосте есть платные планы.
    """
    plan_id = parse_plan_id_from_key(key)
    if plan_id is not None:
        try:
            return get_plan_by_id(plan_id)
        except Exception:
            return None
    if not allow_host_fallback or key_is_unbilled_trial_or_gift(key):
        return None
    host_name = (key or {}).get("host_name")
    if not host_name:
        return None
    try:
        plans = get_active_plans_for_host(host_name) or []
    except Exception:
        plans = []
    return plans[0] if plans else None


def get_plans_analytics(limit: int = 10) -> list[dict]:
    """Аналитика по тарифам (Этап 4.4): выручка, продажи, средний чек, доля повторных покупок."""
    result: list[dict] = []
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT metadata, amount_rub, user_id
                FROM transactions
                WHERE {_SUCCESS_TX_SQL} AND {_NON_BALANCE_SQL}
                """
            )
            per_plan: dict[str, dict] = {}
            user_plan_counts: dict[tuple, int] = {}
            # Действия, которые НЕ являются покупкой/продлением тарифа и не должны
            # попадать в статистику "популярные тарифы" (пополнения баланса, докупки
            # трафика/LTE, сброс трафика и т.п.).
            _NON_PLAN_ACTIONS = {"top_up", "traffic_gb_topup", "lte_gb_topup", "main_traffic_reset", "referral_payout"}
            for meta_str, amount, user_id in cursor.fetchall() or []:
                try:
                    meta = json.loads(meta_str) if meta_str else {}
                except Exception:
                    meta = {}
                action = (meta.get("action") if isinstance(meta, dict) else None)
                if action in _NON_PLAN_ACTIONS:
                    continue
                plan_name = str((meta.get("plan_name") if isinstance(meta, dict) else None) or "N/A").strip() or "N/A"
                bucket = per_plan.setdefault(plan_name, {"plan_name": plan_name, "sales": 0, "revenue": 0.0})
                bucket["sales"] += 1
                bucket["revenue"] += float(amount or 0.0)
                key = (plan_name, user_id)
                user_plan_counts[key] = user_plan_counts.get(key, 0) + 1

            repeat_by_plan: dict[str, int] = {}
            for (plan_name, _uid), cnt in user_plan_counts.items():
                if cnt >= 2:
                    repeat_by_plan[plan_name] = repeat_by_plan.get(plan_name, 0) + 1

            for plan_name, bucket in per_plan.items():
                sales = bucket["sales"]
                bucket["avg_check"] = (bucket["revenue"] / sales) if sales > 0 else 0.0
                bucket["repeat_buyers"] = repeat_by_plan.get(plan_name, 0)
                result.append(bucket)

            result.sort(key=lambda b: b["revenue"], reverse=True)
            result = result[: max(1, int(limit))]
    except sqlite3.Error as e:
        logging.error(f"Failed to get plans analytics: {e}")
    return result

def create_plan(host_name: str, plan_name: str, months: int | None, price: float, duration_days: int | None = None, traffic_limit_bytes: int | None = None, hwid_device_limit: int | None = None, lte_limit_bytes: int | None = None, main_reset_price_rub: float | None = None):
    try:
        host_name = normalize_host_name(host_name)
        # Если лимит трафика явно не указан (None) — по умолчанию считаем его равным 0 (без лимита),
        # а не NULL, чтобы избежать неоднозначности NULL/0 в дальнейшей логике (сравнения, экспорт в API и т.д.).
        traffic_limit_bytes = int(traffic_limit_bytes) if traffic_limit_bytes is not None else 0
        if traffic_limit_bytes < 0:
            traffic_limit_bytes = 0
        # Для лимита трафика стратегия имеет смысл только если лимит задан.
        # 'MONTH_ROLLING' — трафик сбрасывается ежемесячно, отсчитывая от даты создания ключа (rolling-цикл),
        # в отличие от 'MONTH', который сбрасывает трафик по календарным месяцам.
        traffic_limit_strategy = 'MONTH_ROLLING' if traffic_limit_bytes > 0 else None
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO plans (host_name, plan_name, months, duration_days, price, traffic_limit_bytes, traffic_limit_strategy, hwid_device_limit, lte_limit_bytes, main_reset_price_rub) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (host_name, plan_name, months, duration_days, price, traffic_limit_bytes, traffic_limit_strategy, hwid_device_limit, lte_limit_bytes or 0, main_reset_price_rub or 0)
            )
            conn.commit()
            logging.info(f"Created new plan '{plan_name}' for host '{host_name}'.")
    except sqlite3.Error as e:
        logging.error(f"Failed to create plan for host '{host_name}': {e}")


def set_plan_active(plan_id: int, is_active: bool) -> bool:
    """Включить/выключить тариф (скрыть/показать пользователям)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plans SET is_active = ? WHERE plan_id = ?",
                (1 if is_active else 0, int(plan_id))
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set plan active status for id {plan_id}: {e}")
        return False

def get_plan_by_id(plan_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
            plan = cursor.fetchone()
            return dict(plan) if plan else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get plan by id '{plan_id}': {e}")
        return None


def get_all_plans() -> list[dict]:
    """Все тарифы (для админки промокодов и валидации applicable_plan_ids)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM plans
                ORDER BY TRIM(host_name), sort_order,
                         COALESCE(duration_days, months * 30, months, 0), plan_id
                """
            )
            return [dict(plan) for plan in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to list all plans: %s", e)
        return []

def update_plan_metadata(plan_id: int, metadata: dict | None) -> bool:
    """Update plan.metadata JSON blob.

    `metadata=None` or empty dict will clear the field.
    """
    try:
        raw = None
        if metadata:
            raw = json.dumps(metadata, ensure_ascii=False)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE plans SET metadata = ? WHERE plan_id = ?", (raw, int(plan_id)))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update plan metadata for id {plan_id}: {e}")
        return False


def create_traffic_package(plan_id: int, size_gb: float, price: float, pool: str = 'main') -> int | None:
    """Пакет докупки ГБ для тарифа. `pool`: 'main' (основной трафик) или 'lte' (premium-ноды).

    TODO (известное ограничение, причина F диагностики): пакеты привязаны к `plan_id`, а
    LTE-пул расходуется на пользователя (`subscription_lte`). Поэтому при нескольких
    активных тарифах на одном хосте пакеты одного тарифа недоступны владельцам ключей
    другого — пакеты нужно заводить для каждого тарифа. Перевод привязки на
    host_name/squad_uuid потребует миграции существующих строк с неоднозначным выбором
    целевого хоста (у тарифа он один, но пакеты могли создаваться до его смены), поэтому
    сознательно вынесен за рамки этого фикса.
    """
    pool = 'lte' if str(pool).strip().lower() == 'lte' else 'main'
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM traffic_packages WHERE plan_id = ? AND COALESCE(pool, 'main') = ?",
                (int(plan_id), pool)
            )
            next_sort = (cursor.fetchone()[0] or 0) + 1
            cursor.execute(
                "INSERT INTO traffic_packages (plan_id, size_gb, price, sort_order, pool) VALUES (?, ?, ?, ?, ?)",
                (int(plan_id), float(size_gb), float(price), next_sort, pool)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Failed to create traffic package for plan {plan_id}: {e}")
        return None


def get_traffic_packages_for_plan(plan_id: int, only_active: bool = False, pool: str = 'main') -> list[dict]:
    pool = 'lte' if str(pool).strip().lower() == 'lte' else 'main'
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM traffic_packages WHERE plan_id = ? AND COALESCE(pool, 'main') = ?"
            if only_active:
                query += " AND COALESCE(is_active, 1) = 1"
            query += " ORDER BY sort_order, size_gb"
            cursor.execute(query, (int(plan_id), pool))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get traffic packages for plan {plan_id}: {e}")
        return []


def get_traffic_package_by_id(package_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM traffic_packages WHERE package_id = ?", (int(package_id),))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get traffic package by id {package_id}: {e}")
        return None


def update_traffic_package(package_id: int, *, size_gb: float | None = None, price: float | None = None, is_active: bool | None = None) -> bool:
    fields: dict[str, Any] = {}
    if size_gb is not None:
        fields["size_gb"] = float(size_gb)
    if price is not None:
        fields["price"] = float(price)
    if is_active is not None:
        fields["is_active"] = 1 if is_active else 0
    if not fields:
        return False
    try:
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [int(package_id)]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE traffic_packages SET {set_clause} WHERE package_id = ?", values)
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update traffic package {package_id}: {e}")
        return False


def delete_traffic_package(package_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM traffic_packages WHERE package_id = ?", (int(package_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete traffic package {package_id}: {e}")
        return False


def delete_plan(plan_id: int) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM traffic_packages WHERE plan_id = ?", (plan_id,))
            cursor.execute("DELETE FROM plans WHERE plan_id = ?", (plan_id,))
            conn.commit()
            logging.info(f"Deleted plan with id {plan_id}.")
    except sqlite3.Error as e:
        logging.error(f"Failed to delete plan with id {plan_id}: {e}")

def update_plan(plan_id: int, plan_name: str, months: int | None, price: float, *, duration_days: Any = _UNSET, traffic_limit_bytes: Any = _UNSET, hwid_device_limit: Any = _UNSET, lte_limit_bytes: Any = _UNSET, main_reset_price_rub: Any = _UNSET) -> bool:
    try:
        fields: dict[str, Any] = {
            "plan_name": plan_name,
            "months": months,
            "price": price,
        }
        if duration_days is not _UNSET:
            fields["duration_days"] = duration_days
        if traffic_limit_bytes is not _UNSET:
            fields["traffic_limit_bytes"] = traffic_limit_bytes
            try:
                fields["traffic_limit_strategy"] = 'MONTH_ROLLING' if (traffic_limit_bytes is not None and int(traffic_limit_bytes) > 0) else None
            except Exception:
                fields["traffic_limit_strategy"] = None
        if hwid_device_limit is not _UNSET:
            fields["hwid_device_limit"] = hwid_device_limit
        if lte_limit_bytes is not _UNSET:
            fields["lte_limit_bytes"] = lte_limit_bytes
        if main_reset_price_rub is not _UNSET:
            fields["main_reset_price_rub"] = main_reset_price_rub

        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [plan_id]

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE plans SET {set_clause} WHERE plan_id = ?", values)
            conn.commit()
            if cursor.rowcount == 0:
                logging.warning(f"No plan updated for id {plan_id} (not found).")
                return False
            logging.info(f"Updated plan {plan_id}: {fields}.")
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to update plan {plan_id}: {e}")
        return False


def get_device_tiers(host_name: str) -> list[dict]:
    """Вернуть тарифные планы, сгруппированные по лимиту устройств, для указанного хоста.

    Пока в проекте нет отдельной сущности "device tiers" — используем активные тарифы
    хоста (get_plans_for_host) как есть, отсортированные по hwid_device_limit.
    """
    try:
        plans = get_plans_for_host(host_name) or []
        active = [p for p in plans if p.get('is_active')]
        active.sort(key=lambda p: (p.get('hwid_device_limit') or 0))
        return active
    except Exception as e:
        logger.error(f"Failed to get device tiers for host {host_name}: {e}")
        return []
