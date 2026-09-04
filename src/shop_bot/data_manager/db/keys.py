"""VPN-ключи: выдача, продление, срок действия, трафик и сброс счётчиков.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
import logging
import json
from typing import Any

from ._core import _UNSET

__all__ = (
    "compute_next_traffic_reset_str",
    "compute_next_traffic_reset",
    "_as_limit_bytes",
    "key_is_unbilled_trial_or_gift",
    "format_next_traffic_reset_display",
    "compute_aligned_next_traffic_reset",
    "_normalize_key_row",
    "resolve_key_period_start",
    "_finalize_vpn_key_indexes",
    "delete_key_by_id",
    "update_key_comment",
    "update_key_name",
    "get_all_keys",
    "get_all_key_ids",
    "extend_key",
    "set_key_expiry",
    "get_keys_paginated",
    "get_keys_for_user",
    "update_key_email",
    "set_key_traffic_boost",
    "get_total_keys_count",
    "add_new_key",
    "_apply_key_updates",
    "update_key_fields",
    "apply_key_monthly_reset_fields",
    "backfill_monthly_traffic_reset_for_existing_keys",
    "delete_key_by_email",
    "get_user_keys",
    "get_key_by_id",
    "get_key_by_email",
    "update_key_info",
    "get_next_key_number",
    "set_key_auto_renew",
    "set_all_keys_auto_renew_for_user",
    "get_keys_for_auto_renew",
    "_key_matches_search",
    "search_user_keys_by_email",
    "search_all_keys_by_email",
    "get_all_vpn_users",
    "get_keys_counts_for_users",
    "delete_user_keys",
    "get_key_usage_monitor",
    "ensure_key_usage_monitor_row",
    "update_key_usage_monitor",
)


def compute_next_traffic_reset_str(from_dt: datetime | None = None) -> str:
    """Возвращает строку даты/времени следующего ежемесячного сброса трафика (сейчас + 1 месяц)."""
    base = from_dt or datetime.now()
    return add_calendar_months(base, 1).strftime("%Y-%m-%d %H:%M:%S")


def compute_next_traffic_reset(from_dt: datetime | None = None) -> str:
    """Возвращает строку даты следующего ежемесячного сброса трафика (текущий момент + 1 месяц)."""
    base = from_dt or datetime.now()
    return add_months(base, 1).strftime("%Y-%m-%d %H:%M:%S")


def _as_limit_bytes(value) -> int:
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def key_is_unbilled_trial_or_gift(key: dict | None) -> bool:
    tag = str((key or {}).get("tag") or "").strip().lower()
    if tag in {"trial", "user_gift", "gift"}:
        return True
    desc = (key or {}).get("description")
    if isinstance(desc, str) and desc.strip().startswith("{"):
        try:
            meta = json.loads(desc)
            if isinstance(meta, dict):
                if meta.get("is_trial"):
                    return True
                if str(meta.get("source") or "").strip().lower() in {"trial", "gift"}:
                    return True
        except Exception:
            pass
    return False


def format_next_traffic_reset_display(raw) -> str | None:
    """Дата ближайшего сброса для карточки ключа (`ДД.ММ.ГГГГ`) либо None."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace(" ", "T"))
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return None


def compute_aligned_next_traffic_reset(key: dict | None, *, now: datetime | None = None) -> str:
    """Следующий сброс, согласованный с текущим rolling-окном ключа.

    Если `next_traffic_reset_at` уже есть и в будущем — оставляем его.
    Иначе берём начало текущего периода (`resolve_key_period_start`) плюс месяц
    и прокручиваем вперёд, пока дата не окажется строго позже `now`.
    """
    now = now or datetime.now()
    existing = (key or {}).get("next_traffic_reset_at")
    if existing:
        try:
            existing_dt = datetime.fromisoformat(str(existing).replace(" ", "T"))
            if existing_dt > now:
                return existing_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    period_start = resolve_key_period_start(key)
    try:
        start_dt = datetime.fromisoformat(str(period_start).replace(" ", "T"))
    except Exception:
        start_dt = now
    nxt = add_calendar_months(start_dt, 1)
    for _ in range(24):
        if nxt > now:
            break
        nxt = add_calendar_months(nxt, 1)
    if nxt <= now:
        nxt = add_calendar_months(now, 1)
    return nxt.strftime("%Y-%m-%d %H:%M:%S")


def _normalize_key_row(row: sqlite3.Row | dict | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    email = _normalize_email(data.get("email") or data.get("key_email"))
    if email:
        data["email"] = email
        data["key_email"] = email
    rem_uuid = data.get("remnawave_user_uuid") or data.get("xui_client_uuid")
    if rem_uuid:
        data["remnawave_user_uuid"] = rem_uuid
        data["xui_client_uuid"] = rem_uuid
    expire_value = data.get("expire_at") or data.get("expiry_date")
    if expire_value:
        expire_str = expire_value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(expire_value, datetime) else str(expire_value)
        data["expire_at"] = expire_str
        data["expiry_date"] = expire_str
    created_value = data.get("created_at") or data.get("created_date")
    if created_value:
        created_str = created_value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_value, datetime) else str(created_value)
        data["created_at"] = created_str
        data["created_date"] = created_str
    subscription_url = data.get("subscription_url") or data.get("connection_string")
    if subscription_url:
        data["subscription_url"] = subscription_url
        data.setdefault("connection_string", subscription_url)
    return data


def resolve_key_period_start(key: dict | None) -> str:
    """Начало текущего расчётного периода ключа в формате '%Y-%m-%d %H:%M:%S'.

    Берём `next_traffic_reset_at` (конец периода) минус календарный месяц — так граница
    совпадает с той, по которой воркер сбрасывает основной пул и baseline LTE. Если поле
    ещё не заполнено, опираемся на дату создания ключа, а в последнюю очередь — на начало
    текущего месяца, чтобы период всегда был определён.
    """
    raw_next = (key or {}).get("next_traffic_reset_at")
    if raw_next:
        try:
            next_dt = datetime.fromisoformat(str(raw_next).replace(" ", "T"))
            return add_calendar_months(next_dt, -1).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    raw_created = (key or {}).get("created_at") or (key or {}).get("created_date")
    if raw_created:
        try:
            created_dt = datetime.fromisoformat(str(raw_created).replace(" ", "T"))
            now = datetime.now()
            # Rolling-цикл от даты создания: последняя годовщина, не превышающая "сейчас".
            months = (now.year - created_dt.year) * 12 + (now.month - created_dt.month)
            candidate = add_calendar_months(created_dt, months)
            if candidate > now:
                candidate = add_calendar_months(created_dt, months - 1)
            return candidate.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _finalize_vpn_key_indexes(cursor: sqlite3.Cursor) -> None:
    _ensure_unique_index(cursor, "uq_vpn_keys_email", "vpn_keys", "email")
    _ensure_unique_index(cursor, "uq_vpn_keys_key_email", "vpn_keys", "key_email")
    _ensure_index(cursor, "idx_vpn_keys_user_id", "vpn_keys", "user_id")
    _ensure_index(cursor, "idx_vpn_keys_rem_uuid", "vpn_keys", "remnawave_user_uuid")
    _ensure_index(cursor, "idx_vpn_keys_expire_at", "vpn_keys", "expire_at")

def delete_key_by_id(key_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Ключ может быть привязан к неактивированному подарку (user_gifts.key_id) —
            # при удалении ключа (по истечении срока, вручную и т.д.) подарок должен
            # пропадать из списка так же, как исчезает обычный ключ.
            cursor.execute("DELETE FROM user_gifts WHERE key_id = ? AND is_activated = 0", (key_id,))
            cursor.execute("DELETE FROM key_node_usage_snapshots WHERE key_id = ?", (key_id,))
            cursor.execute("DELETE FROM key_lte_state WHERE key_id = ?", (key_id,))
            cursor.execute("DELETE FROM vpn_keys WHERE key_id = ?", (key_id,))
            affected = cursor.rowcount
            conn.commit()
            return affected > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось удалить ключ по id {key_id}: {e}")
        return False

def update_key_comment(key_id: int, comment: str) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET comment_key = ? WHERE key_id = ?", (comment, key_id))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить комментарий ключа для {key_id}: {e}")
        return False


def update_key_name(key_id: int, new_name: str | None) -> bool:
    """
    Обновить пользовательское название ключа.
    
    Args:
        key_id: ID ключа
        new_name: Новое название (None или пустая строка для удаления)
    
    Returns:
        True если успешно, False при ошибке
    """
    try:
        # Валидация и нормализация
        if new_name:
            new_name = new_name.strip()
            if len(new_name) > 30:
                logging.warning(f"Название ключа слишком длинное ({len(new_name)} символов): {new_name[:50]}")
                return False
            if not new_name:
                new_name = None
        else:
            new_name = None
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE vpn_keys SET user_key_name = ?, updated_at = CURRENT_TIMESTAMP WHERE key_id = ?",
                (new_name, key_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить название ключа {key_id}: {e}")
        return False


def get_all_keys() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys")
            return [_normalize_key_row(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get all keys: {e}")
        return []


def get_all_key_ids() -> list[int]:
    """Все key_id из vpn_keys (без фильтров/пагинации) — для bulk-действий «всем»."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key_id FROM vpn_keys ORDER BY key_id ASC")
            return [int(row[0]) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error("Failed to get all key ids: %s", e)
        return []


def extend_key(key_id: int, days: int) -> tuple[bool, str | None]:
    """Продлить/сократить срок ключа на N дней (с синхронизацией Remnawave).

    Реализация делегируется в remnawave_repository (lazy import — избегаем цикла).
    """
    from shop_bot.data_manager import remnawave_repository as _rw

    return _rw.extend_key(key_id, days)


def set_key_expiry(key_id: int, new_expire_at) -> tuple[bool, str | None]:
    """Установить точную дату истечения ключа (с синхронизацией Remnawave)."""
    from shop_bot.data_manager import remnawave_repository as _rw

    return _rw.set_key_expiry(key_id, new_expire_at)


def get_keys_paginated(page: int = 1, per_page: int = 25, search: str | None = None, sort_by: str | None = None, sort_dir: str | None = None, user_id: int | None = None) -> tuple[list[dict], int]:
    try:
        page_i = max(1, int(page))
    except Exception:
        page_i = 1
    try:
        per_i = max(1, int(per_page))
    except Exception:
        per_i = 25
    offset = (page_i - 1) * per_i
    search_q = (search or "").strip()
    conditions: list = []
    params: list = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(int(user_id))
    if search_q:
        like = f"%{search_q}%"
        conditions.append(
            "(CAST(key_id AS TEXT) LIKE ? OR CAST(user_id AS TEXT) LIKE ?"
            " OR key_email LIKE ? OR email LIKE ? OR user_key_name LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_columns = {
        "user_id": "user_id",
        "host_name": "host_name",
        "created_at": "COALESCE(created_at, updated_at, key_id)",
        "expire_at": "expire_at",
    }
    sort_col = sort_columns.get((sort_by or "").strip(), sort_columns["created_at"])
    sort_direction = "ASC" if (sort_dir or "").strip().lower() == "asc" else "DESC"
    order_sql = f"ORDER BY {sort_col} {sort_direction}"
    if sort_col != sort_columns["created_at"]:
        order_sql += f", {sort_columns['created_at']} DESC"

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM vpn_keys{where_sql}", params)
            total = cursor.fetchone()[0] or 0
            cursor.execute(
                f"""
                SELECT *
                FROM vpn_keys
                {where_sql}
                {order_sql}
                LIMIT ? OFFSET ?
                """,
                (*params, per_i, offset),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows], int(total)
    except sqlite3.Error as e:
        logging.error(f"Failed to get paginated keys: {e}")
        return [], 0


def get_keys_for_user(user_id: int) -> list[dict]:
    return get_user_keys(user_id)

def update_key_email(key_id: int, new_email: str) -> bool:
    normalized = _normalize_email(new_email) or new_email.strip()
    return update_key_fields(key_id, email=normalized)


def set_key_traffic_boost(key_id: int, boost_bytes: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE vpn_keys SET traffic_boost_bytes = ? WHERE key_id = ?",
                (int(boost_bytes), int(key_id))
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set traffic boost for key {key_id}: {e}")
        return False

def get_total_keys_count() -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vpn_keys")
            return cursor.fetchone()[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get total keys count: {e}")
        return 0

def add_new_key(
    user_id: int,
    host_name: str | None,
    remnawave_user_uuid: str,
    key_email: str,
    expiry_timestamp_ms: int,
    *,
    squad_uuid: str | None = None,
    short_uuid: str | None = None,
    subscription_url: str | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    description: str | None = None,
    tag: str | None = None,
) -> int | None:
    host_name_norm = normalize_host_name(host_name) if host_name else None
    email_normalized = _normalize_email(key_email) or key_email.strip()
    expire_str = _to_datetime_str(expiry_timestamp_ms) or _now_str()
    created_str = _now_str()
    strategy_value = traffic_limit_strategy or "NO_RESET"
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO vpn_keys (
                    user_id,
                    host_name,
                    squad_uuid,
                    remnawave_user_uuid,
                    short_uuid,
                    email,
                    key_email,
                    subscription_url,
                    expire_at,
                    created_at,
                    updated_at,
                    traffic_limit_bytes,
                    traffic_limit_strategy,
                    tag,
                    description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    host_name_norm,
                    squad_uuid,
                    remnawave_user_uuid,
                    short_uuid,
                    email_normalized,
                    email_normalized,
                    subscription_url,
                    expire_str,
                    created_str,
                    created_str,
                    traffic_limit_bytes,
                    strategy_value,
                    tag,
                    description,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError as e:
        logging.error(
            "Failed to add new key for user %s due to integrity error: %s",
            user_id,
            e,
        )
        return None
    except sqlite3.Error as e:
        logging.error("Failed to add new key for user %s: %s", user_id, e)
        return None


def _apply_key_updates(key_id: int, updates: dict[str, Any]) -> bool:
    if not updates:
        return False
    updates = dict(updates)
    updates["updated_at"] = _now_str()
    columns = ", ".join(f"{column} = ?" for column in updates)
    values = list(updates.values())
    values.append(key_id)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE vpn_keys SET {columns} WHERE key_id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to update key %s: %s", key_id, e)
        return False


def update_key_fields(
    key_id: int,
    *,
    user_id: int | None = None,
    host_name: str | None = None,
    squad_uuid: str | None = None,
    remnawave_user_uuid: str | None = None,
    short_uuid: str | None = None,
    email: str | None = None,
    subscription_url: str | None = None,
    expire_at_ms: int | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    tag: str | None = None,
    description: str | None = None,
    missing_from_server_at: Any = _UNSET,
    traffic_boost_bytes: int | None = None,
    next_traffic_reset_at: Any = _UNSET,
    remote_access_state: str | None = None,
) -> bool:
    updates: dict[str, Any] = {}
    if user_id is not None:
        updates["user_id"] = user_id
    if host_name is not None:
        updates["host_name"] = normalize_host_name(host_name)
    if squad_uuid is not None:
        updates["squad_uuid"] = squad_uuid
    if remnawave_user_uuid is not None:
        updates["remnawave_user_uuid"] = remnawave_user_uuid
    if short_uuid is not None:
        updates["short_uuid"] = short_uuid
    if email is not None:
        normalized = _normalize_email(email) or email.strip()
        updates["email"] = normalized
        updates["key_email"] = normalized
    if subscription_url is not None:
        updates["subscription_url"] = subscription_url
    if expire_at_ms is not None:
        expire_str = _to_datetime_str(expire_at_ms) or _now_str()
        updates["expire_at"] = expire_str
    if traffic_limit_bytes is not None:
        updates["traffic_limit_bytes"] = traffic_limit_bytes
    if traffic_limit_strategy is not None:
        updates["traffic_limit_strategy"] = traffic_limit_strategy or "NO_RESET"
    if tag is not None:
        updates["tag"] = tag
    if description is not None:
        updates["description"] = description
    if missing_from_server_at is not _UNSET:
        updates["missing_from_server_at"] = missing_from_server_at
    if traffic_boost_bytes is not None:
        updates["traffic_boost_bytes"] = int(traffic_boost_bytes)
    if next_traffic_reset_at is not _UNSET:
        updates["next_traffic_reset_at"] = next_traffic_reset_at
    if remote_access_state is not None:
        updates["remote_access_state"] = remote_access_state
    return _apply_key_updates(key_id, updates)


def apply_key_monthly_reset_fields(
    key_id: int,
    plan: dict | None = None,
    *,
    restart_cycle: bool = False,
    key: dict | None = None,
    expire_main_boost: bool = False,
) -> bool:
    """Записать `traffic_limit_strategy` и `next_traffic_reset_at` по тарифу ключа.

    - MONTH_ROLLING только при лимите основного пула (это поле уходит в Remnawave).
    - Дата сброса ставится, если ограничен основной ИЛИ LTE-пул.
    - `restart_cycle=True` — новая покупка/смена тарифа: окно от «сейчас».
    - иначе не трогаем уже проставленную будущую дату; при её отсутствии
      выравниваем по дате создания ключа.
    """
    if key is None:
        try:
            key = get_key_by_id(int(key_id))
        except Exception:
            key = None
    if plan is None:
        plan = resolve_plan_for_key(key)
    strategy = remnawave_traffic_limit_strategy_for_plan(plan)
    main_limit = plan_main_limit_bytes(plan)
    if main_limit <= 0:
        main_limit = _as_limit_bytes((key or {}).get("traffic_limit_bytes"))
        if main_limit > 0:
            strategy = "MONTH_ROLLING"
    needs_date = plan_has_monthly_traffic_reset(plan) or main_limit > 0
    next_reset: Any = None
    if needs_date:
        next_reset = (
            compute_next_traffic_reset_str()
            if restart_cycle
            else compute_aligned_next_traffic_reset(key)
        )
    return update_key_fields(
        int(key_id),
        traffic_limit_strategy=strategy,
        next_traffic_reset_at=next_reset,
        traffic_boost_bytes=0 if expire_main_boost else None,
    )


def backfill_monthly_traffic_reset_for_existing_keys() -> int:
    """Проставить MONTH_ROLLING и дату сброса уже выданным лимитным/LTE-ключам.

    Идемпотентно: будущая дата не сдвигается, стратегия переписывается только
    если основной пул ограничен, а в колонке ещё не MONTH_ROLLING.
    """
    try:
        keys = get_all_keys()
    except Exception:
        logging.warning("Backfill monthly traffic reset: не удалось прочитать ключи", exc_info=True)
        return 0
    updated = 0
    for key in keys:
        try:
            if key_is_unbilled_trial_or_gift(key) and parse_plan_id_from_key(key) is None:
                continue
            plan = resolve_plan_for_key(key)
            main_limit = plan_main_limit_bytes(plan) or _as_limit_bytes((key or {}).get("traffic_limit_bytes"))
            lte_limit = plan_lte_limit_bytes(plan)
            if main_limit <= 0 and lte_limit <= 0:
                continue
            key_id = int(key.get("key_id"))
            before_strategy = key.get("traffic_limit_strategy") or "NO_RESET"
            before_date = key.get("next_traffic_reset_at")
            apply_key_monthly_reset_fields(key_id, plan, restart_cycle=False, key=key)
            after = get_key_by_id(key_id) or {}
            if (
                (after.get("traffic_limit_strategy") or "NO_RESET") != before_strategy
                or (after.get("next_traffic_reset_at") or None) != (before_date or None)
            ):
                updated += 1
        except Exception:
            logging.warning(
                "Backfill monthly traffic reset failed for key %s",
                (key or {}).get("key_id"),
                exc_info=True,
            )
    if updated:
        logging.info("Backfill monthly traffic reset: обновлено ключей: %s", updated)
    return updated


def delete_key_by_email(email: str) -> bool:
    lookup = _normalize_email(email) or email.strip()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Как и в delete_key_by_id: удаляем связанный неактивированный подарок,
            # чтобы он пропал из списка так же, как исчезает обычный просроченный ключ.
            cursor.execute(
                "SELECT key_id FROM vpn_keys WHERE email = ? OR key_email = ?",
                (lookup, lookup),
            )
            key_ids = [row[0] for row in cursor.fetchall()]
            if key_ids:
                cursor.executemany(
                    "DELETE FROM user_gifts WHERE key_id = ? AND is_activated = 0",
                    [(kid,) for kid in key_ids],
                )
                cursor.executemany(
                    "DELETE FROM key_node_usage_snapshots WHERE key_id = ?",
                    [(kid,) for kid in key_ids],
                )
                cursor.executemany(
                    "DELETE FROM key_lte_state WHERE key_id = ?",
                    [(kid,) for kid in key_ids],
                )
            cursor.execute(
                "DELETE FROM vpn_keys WHERE email = ? OR key_email = ?",
                (lookup, lookup),
            )
            affected = cursor.rowcount
            conn.commit()
            logger.debug("delete_key_by_email('%s') affected=%s", email, affected)
            return affected > 0
    except sqlite3.Error as e:
        logging.error("Failed to delete key '%s': %s", email, e)
        return False


def get_user_keys(user_id: int) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE user_id = ? ORDER BY datetime(created_at) DESC, key_id DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get keys for user %s: %s", user_id, e)
        return []


def get_key_by_id(key_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except sqlite3.Error as e:
        logging.error("Failed to get key by ID %s: %s", key_id, e)
        return None


def get_key_by_email(key_email: str) -> dict | None:
    lookup = _normalize_email(key_email) or key_email.strip()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE email = ? OR key_email = ?",
                (lookup, lookup),
            )
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except sqlite3.Error as e:
        logging.error("Failed to get key by email %s: %s", key_email, e)
        return None


def update_key_info(key_id: int, new_remnawave_uuid: str, new_expiry_ms: int, **kwargs) -> bool:
    return update_key_fields(
        key_id,
        remnawave_user_uuid=new_remnawave_uuid,
        expire_at_ms=new_expiry_ms,
        **kwargs,
    )


def get_next_key_number(user_id: int) -> int:
    return len(get_user_keys(user_id)) + 1


def set_key_auto_renew(key_id: int, enabled: bool) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET auto_renew = ? WHERE key_id = ?", (1 if enabled else 0, int(key_id)))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error("Failed to set auto_renew for key %s: %s", key_id, e)
        return False


def set_all_keys_auto_renew_for_user(user_id: int, enabled: bool) -> int:
    """Mass-update auto_renew for all keys of a user. Returns count of updated rows."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE vpn_keys SET auto_renew = ? WHERE user_id = ?", (1 if enabled else 0, int(user_id)))
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        logging.error("Failed to set auto_renew for all keys of user %s: %s", user_id, e)
        return 0


def get_keys_for_auto_renew(hours_before: int = 24) -> list[dict]:
    """Return keys with auto_renew=1 expiring within the next `hours_before` hours."""
    now = datetime.now()
    deadline = now + timedelta(hours=int(hours_before))
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM vpn_keys
                WHERE auto_renew = 1
                  AND expire_at IS NOT NULL
                  AND expire_at > ?
                  AND expire_at <= ?
                ORDER BY expire_at ASC
                """,
                (now.strftime("%Y-%m-%d %H:%M:%S"), deadline.strftime("%Y-%m-%d %H:%M:%S")),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get keys for auto-renewal: %s", e)
        return []


def _key_matches_search(data: dict, needle_lower: str) -> bool:
    """Регистронезависимая (в т.ч. кириллица) проверка вхождения подстроки
    в key_email, email или user_key_name. SQL LIKE/LOWER() в SQLite сворачивают
    регистр только для ASCII, поэтому сравнение делается на стороне Python."""
    for field in ("key_email", "email", "user_key_name"):
        value = data.get(field)
        if value and needle_lower in str(value).lower():
            return True
    return False


def search_user_keys_by_email(user_id: int, search_query: str) -> list[dict]:
    """Поиск ключей пользователя по key_email, email или user_key_name."""
    if not search_query or not search_query.strip():
        return []

    try:
        needle_lower = search_query.strip().lower()
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE user_id = ? ORDER BY datetime(created_at) DESC, key_id DESC",
                (user_id,),
            )
            rows = cursor.fetchall()
            normalized = (_normalize_key_row(row) for row in rows)
            return [data for data in normalized if _key_matches_search(data, needle_lower)]
    except sqlite3.Error as e:
        logging.error("Failed to search user keys by email for user %s: %s", user_id, e)
        return []


def search_all_keys_by_email(search_query: str) -> list[dict]:
    """Поиск всех ключей (администраторам) по key_email, email или user_key_name."""
    if not search_query or not search_query.strip():
        return []

    try:
        needle_lower = search_query.strip().lower()
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys ORDER BY datetime(created_at) DESC, key_id DESC",
            )
            rows = cursor.fetchall()
            normalized = (_normalize_key_row(row) for row in rows)
            return [data for data in normalized if _key_matches_search(data, needle_lower)]
    except sqlite3.Error as e:
        logging.error("Failed to search all keys by email: %s", e)
        return []


def get_all_vpn_users() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM vpn_keys")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get all vpn users: %s", e)
        return []

def get_keys_counts_for_users(user_ids: list[int]) -> dict[int, int]:
    """Вернуть словарь {user_id: keys_count} по списку пользователей."""
    result: dict[int, int] = {}
    if not user_ids:
        return result

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            placeholders = ",".join(["?"] * len(user_ids))
            query = f"SELECT user_id, COUNT(*) AS cnt FROM vpn_keys WHERE user_id IN ({placeholders}) GROUP BY user_id"
            cursor.execute(query, tuple(int(x) for x in user_ids))
            for row in cursor.fetchall() or []:
                uid = int(row[0])
                cnt = int(row[1] or 0)
                result[uid] = cnt
    except sqlite3.Error as e:
        logging.error("Failed to get keys counts for users: %s", e)
    return result

def delete_user_keys(user_id: int):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM user_gifts
                WHERE is_activated = 0 AND key_id IN (SELECT key_id FROM vpn_keys WHERE user_id = ?)
                """,
                (user_id,),
            )
            cursor.execute("DELETE FROM vpn_keys WHERE user_id = ?", (user_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to delete keys for user {user_id}: {e}")





# --- Key usage monitor (traffic/devices) ---

def get_key_usage_monitor(key_id: int) -> dict | None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM key_usage_monitor WHERE key_id = ?", (key_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get key_usage_monitor for key_id={key_id}: {e}")
        return None


def ensure_key_usage_monitor_row(key_id: int, user_id: int) -> None:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO key_usage_monitor(key_id, user_id) VALUES(?, ?)",
                (int(key_id), int(user_id)),
            )
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to ensure key_usage_monitor row for key_id={key_id}: {e}")


def update_key_usage_monitor(
    key_id: int,
    *,
    first_seen_usage_at: str | None = None,
    last_reminder_at: str | None = None,
    last_checked_at: str | None = None,
    last_devices_count: int | None = None,
    last_traffic_bytes: int | None = None,
    overlimit_notified_count: int | None = None,
    overlimit_notified_at: str | None = None,
) -> bool:
    fields = []
    values = []
    if first_seen_usage_at is not None:
        fields.append("first_seen_usage_at = ?")
        values.append(first_seen_usage_at)
    if last_reminder_at is not None:
        fields.append("last_reminder_at = ?")
        values.append(last_reminder_at)
    if last_checked_at is not None:
        fields.append("last_checked_at = ?")
        values.append(last_checked_at)
    if last_devices_count is not None:
        fields.append("last_devices_count = ?")
        values.append(int(last_devices_count))
    if last_traffic_bytes is not None:
        fields.append("last_traffic_bytes = ?")
        values.append(int(last_traffic_bytes))
    if overlimit_notified_count is not None:
        fields.append("overlimit_notified_count = ?")
        values.append(int(overlimit_notified_count))
    if overlimit_notified_at is not None:
        fields.append("overlimit_notified_at = ?")
        values.append(overlimit_notified_at)

    if not fields:
        return False

    values.append(int(key_id))
    sql = "UPDATE key_usage_monitor SET " + ", ".join(fields) + " WHERE key_id = ?"

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.cursor()
            cur.execute(sql, values)
            conn.commit()
            return cur.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update key_usage_monitor for key_id={key_id}: {e}")
        return False
