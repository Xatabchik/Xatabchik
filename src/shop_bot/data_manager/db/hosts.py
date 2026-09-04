"""Хосты и панели (3x-ui, Remnawave): подключение, ноды и синхронизация.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
from typing import Any

__all__ = (
    "remnawave_traffic_limit_strategy_for_plan",
    "normalize_host_name",
    "upsert_key_node_usage_snapshot",
    "get_node_usage_for_key",
    "delete_node_usage_for_key",
    "seed_global_remnawave_from_hosts",
    "apply_global_remnawave_to_hosts",
    "create_host",
    "update_host_subscription_url",
    "update_host_url",
    "update_host_remnawave_settings",
    "get_host_class",
    "set_host_class",
    "list_hosts_by_class",
    "update_host_name",
    "delete_host",
    "get_host",
    "update_host_ssh_settings",
    "get_all_hosts",
    "insert_host_speedtest",
    "get_ssh_known_host_key",
    "save_ssh_known_host_key",
    "update_key_host",
    "get_plans_for_host",
    "get_active_plans_for_host",
    "get_key_by_remnawave_uuid",
    "update_key_host_and_info",
    "get_keys_for_host",
)


def remnawave_traffic_limit_strategy_for_plan(plan: dict | None) -> str:
    """Стратегия Remnawave относится только к ОСНОВНОМУ пулу.

    LTE-лимит бот считает сам. Если основной пул безлимитный, панели
    отправляем NO_RESET, даже когда LTE ограничен.
    """
    return "MONTH_ROLLING" if plan_main_limit_bytes(plan) > 0 else "NO_RESET"


def normalize_host_name(name: str | None) -> str:
    """Normalize host name by trimming and removing invisible/unicode spaces."""
    s = (name or "").strip()
    for ch in ("\u00A0", "\u200B", "\u200C", "\u200D", "\uFEFF"):
        s = s.replace(ch, "")
    return s


def upsert_key_node_usage_snapshot(
    key_id: int,
    node_uuid: str,
    *,
    host_name: str,
    used_bytes: int,
    period_start: str,
    node_name: str | None = None,
) -> bool:
    """Записать/обновить расход ключа по одной ноде за период (идемпотентно по
    UNIQUE(key_id, node_uuid, period_start))."""
    node_uuid_n = (node_uuid or "").strip()
    if not node_uuid_n or not key_id:
        return False
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO key_node_usage_snapshots
                    (key_id, node_uuid, node_name, host_name, used_bytes, period_start, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key_id, node_uuid, period_start) DO UPDATE SET
                    used_bytes = excluded.used_bytes,
                    node_name = COALESCE(excluded.node_name, key_node_usage_snapshots.node_name),
                    host_name = excluded.host_name,
                    updated_at = excluded.updated_at
                """,
                (
                    int(key_id),
                    node_uuid_n,
                    (node_name or None),
                    normalize_host_name(host_name),
                    max(0, int(used_bytes or 0)),
                    str(period_start),
                    _now_str(),
                ),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to upsert node usage snapshot for key {key_id}/{node_uuid_n}: {e}")
        return False


def get_node_usage_for_key(key_id: int, period_start: str | None = None) -> list[dict]:
    """Разбивка расхода ключа по нодам за период (по убыванию расхода).

    Без `period_start` берётся последний известный период этого ключа.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if period_start is None:
                cursor.execute(
                    "SELECT MAX(period_start) FROM key_node_usage_snapshots WHERE key_id = ?",
                    (int(key_id),),
                )
                row = cursor.fetchone()
                period_start = row[0] if row else None
                if not period_start:
                    return []
            cursor.execute(
                "SELECT * FROM key_node_usage_snapshots WHERE key_id = ? AND period_start = ? "
                "ORDER BY used_bytes DESC, node_uuid",
                (int(key_id), str(period_start)),
            )
            return [dict(r) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get node usage for key {key_id}: {e}")
        return []


def delete_node_usage_for_key(key_id: int) -> bool:
    """Удалить все снапшоты ключа (используется при удалении ключа)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM key_node_usage_snapshots WHERE key_id = ?", (int(key_id),))
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to delete node usage snapshots for key {key_id}: {e}")
        return False


def seed_global_remnawave_from_hosts() -> None:
    """Если глобальные Remnawave-настройки пусты — взять из первого хоста."""
    try:
        base = (get_setting("remnawave_base_url") or "").strip()
        token = (get_setting("remnawave_api_token") or "").strip()
        sub = (get_setting("remnawave_subscription_url") or "").strip()
        if base and token and sub:
            return
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT remnawave_base_url, remnawave_api_token, subscription_url, host_url
                FROM xui_hosts
                ORDER BY host_name
                LIMIT 20
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            if not base:
                base = ((row["remnawave_base_url"] or row["host_url"] or "")).strip()
            if not token:
                raw_token = ((row["remnawave_api_token"] or "")).strip()
                token = decrypt_managed_bot_token(raw_token) if raw_token else ""
            if not sub:
                sub = ((row["subscription_url"] or "")).strip()
            if base and token and sub:
                break
        if base and not (get_setting("remnawave_base_url") or "").strip():
            update_setting("remnawave_base_url", base)
        if token and not (get_setting("remnawave_api_token") or "").strip():
            update_setting("remnawave_api_token", token)
        if sub and not (get_setting("remnawave_subscription_url") or "").strip():
            update_setting("remnawave_subscription_url", sub)
    except Exception as e:
        logging.warning(f"seed_global_remnawave_from_hosts failed: {e}")


def apply_global_remnawave_to_hosts() -> int:
    """Синхронизировать глобальные Remnawave URL/token/subscription на все хосты."""
    base = (get_setting("remnawave_base_url") or "").strip() or None
    token = (get_setting("remnawave_api_token") or "").strip() or None
    sub = (get_setting("remnawave_subscription_url") or "").strip() or None
    updated = 0
    try:
        hosts = get_all_hosts()
        for host in hosts:
            name = host.get("host_name")
            if not name:
                continue
            ok_rmw = update_host_remnawave_settings(
                name,
                remnawave_base_url=base,
                remnawave_api_token=token,
            )
            ok_sub = True
            if sub is not None:
                ok_sub = update_host_subscription_url(name, sub)
            # host_url тоже держим в синхроне с панелью для speedtest/UI
            ok_url = True
            if base:
                ok_url = update_host_url(name, base)
            if ok_rmw and ok_sub and ok_url:
                updated += 1
        return updated
    except Exception as e:
        logging.error(f"apply_global_remnawave_to_hosts failed: {e}")
        return updated


def create_host(name: str, url: str, user: str, passwd: str, inbound: int, subscription_url: str | None = None):
    try:
        name = normalize_host_name(name)
        url = (url or "").strip()
        user = (user or "").strip()
        passwd = passwd or ""
        try:
            inbound = int(inbound)
        except Exception:
            pass
        subscription_url = (subscription_url or None)

        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, subscription_url) VALUES (?, ?, ?, ?, ?, ?)",
                    (name, url, user, passwd, inbound, subscription_url)
                )
            except sqlite3.OperationalError:
                cursor.execute(
                    "INSERT INTO xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id) VALUES (?, ?, ?, ?, ?)",
                    (name, url, user, passwd, inbound)
                )
            conn.commit()
            logging.info(f"Успешно создан новый хост: {name}")
    except sqlite3.Error as e:
        logging.error(f"Ошибка при создании хоста '{name}': {e}")

def update_host_subscription_url(host_name: str, subscription_url: str | None) -> bool:
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            exists = cursor.fetchone() is not None
            if not exists:
                logging.warning(f"update_host_subscription_url: хост с именем '{host_name}' не найден (после TRIM)")
                return False

            cursor.execute(
                "UPDATE xui_hosts SET subscription_url = ? WHERE TRIM(host_name) = TRIM(?)",
                (subscription_url, host_name)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить subscription_url для хоста '{host_name}': {e}")
        return False

def update_host_url(host_name: str, new_url: str) -> bool:
    """Обновить URL панели XUI для указанного хоста."""
    try:
        host_name = normalize_host_name(host_name)
        new_url = (new_url or "").strip()
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_url: хост с именем '{host_name}' не найден")
                return False

            cursor.execute(
                "UPDATE xui_hosts SET host_url = ? WHERE TRIM(host_name) = TRIM(?)",
                (new_url, host_name)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить host_url для хоста '{host_name}': {e}")
        return False

def update_host_remnawave_settings(
    host_name: str,
    *,
    remnawave_base_url: str | None = None,
    remnawave_api_token: str | None = None,
    squad_uuid: str | None = None,
) -> bool:
    """Обновить Remnawave-настройки на уровне конкретного хоста.
    Пустые строки превращаются в NULL. Поля, равные None, не изменяются.
    """
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_remnawave_settings: хост не найден '{host_name_n}'")
                return False

            sets: list[str] = []
            params: list[Any] = []
            if remnawave_base_url is not None:
                value = (remnawave_base_url or '').strip() or None
                sets.append("remnawave_base_url = ?")
                params.append(value)
            if remnawave_api_token is not None:
                value = (remnawave_api_token or '').strip() or None
                if value:
                    value = encrypt_managed_bot_token(value)
                sets.append("remnawave_api_token = ?")
                params.append(value)
            if squad_uuid is not None:
                value = (squad_uuid or '').strip() or None
                sets.append("squad_uuid = ?")
                params.append(value)
            if not sets:
                return True
            params.append(host_name_n)
            sql = f"UPDATE xui_hosts SET {', '.join(sets)} WHERE TRIM(host_name) = TRIM(?)"
            cursor.execute(sql, params)
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить Remnawave-настройки для хоста '{host_name}': {e}")
        return False


def get_host_class(host_name: str) -> str:
    """Класс ноды: 'premium' (💰) или 'unlim' (∞, по умолчанию)."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT node_class FROM xui_hosts WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (host_name_n,),
            )
            row = cursor.fetchone()
            return (row[0] if row and row[0] else 'unlim')
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить класс хоста '{host_name}': {e}")
        return 'unlim'


def set_host_class(host_name: str, node_class: str, badge: str | None = None) -> bool:
    """Устанавливает класс ноды ('premium'/'unlim') и её значок (по умолчанию 💰/∞)."""
    node_class = 'premium' if str(node_class).strip().lower() == 'premium' else 'unlim'
    if badge is None:
        badge = '💰' if node_class == 'premium' else '∞'
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE xui_hosts SET node_class = ?, badge = ? WHERE TRIM(host_name) = TRIM(?)",
                (node_class, badge, host_name_n),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Не удалось установить класс хоста '{host_name}': {e}")
        return False


def list_hosts_by_class(node_class: str) -> list[dict]:
    node_class = 'premium' if str(node_class).strip().lower() == 'premium' else 'unlim'
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts WHERE COALESCE(node_class, 'unlim') = ?", (node_class,))
            return [
                _decrypt_row_secrets(dict(row), "ssh_password", "remnawave_api_token")
                for row in cursor.fetchall()
            ]
    except sqlite3.Error as e:
        logging.error(f"Не удалось получить список хостов класса '{node_class}': {e}")
        return []


def update_host_name(old_name: str, new_name: str) -> bool:
    """Переименовать хост во всех связанных таблицах (xui_hosts, plans, vpn_keys, host_squads)."""
    try:
        old_name_n = normalize_host_name(old_name)
        new_name_n = normalize_host_name(new_name)
        if not new_name_n:
            logging.warning("update_host_name: new host name is empty after normalization")
            return False
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (old_name_n,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_name: исходный хост не найден '{old_name_n}'")
                return False
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (new_name_n,))
            exists_target = cursor.fetchone() is not None
            if exists_target and old_name_n.lower() != new_name_n.lower():
                logging.warning(f"update_host_name: целевое имя '{new_name_n}' уже используется")
                return False

            cursor.execute(
                "UPDATE xui_hosts SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?)",
                (new_name_n, old_name_n)
            )
            cursor.execute(
                "UPDATE plans SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?)",
                (new_name_n, old_name_n)
            )
            cursor.execute(
                "UPDATE vpn_keys SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?)",
                (new_name_n, old_name_n)
            )
            # host_squads тоже привязан к имени хоста: без переименования LTE-сквад
            # осиротеет и докупка LTE молча пропадёт у всех ключей этого хоста.
            cursor.execute(
                "UPDATE host_squads SET host_name = TRIM(?) WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (new_name_n, old_name_n)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось переименовать хост с '{old_name}' на '{new_name}': {e}")
        return False

def delete_host(host_name: str):
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plans WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            cursor.execute("DELETE FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            # Иначе привязки сквадов остаются "мусором" и могут случайно подхватиться
            # хостом, созданным позже с тем же именем.
            cursor.execute(
                "DELETE FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (host_name,),
            )
            conn.commit()
            logging.info(f"Хост '{host_name}' и его тарифы успешно удалены.")
    except sqlite3.Error as e:
        logging.error(f"Ошибка удаления хоста '{host_name}': {e}")


def get_host(host_name: str) -> dict | None:
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name,))
            result = cursor.fetchone()
            return _decrypt_row_secrets(dict(result) if result else None, "ssh_password", "remnawave_api_token")
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения хоста '{host_name}': {e}")
        return None

def update_host_ssh_settings(
    host_name: str,
    ssh_host: str | None = None,
    ssh_port: int | None = None,
    ssh_user: str | None = None,
    ssh_password: str | None = None,
    ssh_key_path: str | None = None,
) -> bool:
    """Обновить SSH-параметры для speedtest/maintenance по хосту.
    Переданные None значения очищают соответствующие поля (ставят NULL).
    """
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            if cursor.fetchone() is None:
                logging.warning(f"update_host_ssh_settings: хост не найден '{host_name_n}'")
                return False

            cursor.execute(
                """
                UPDATE xui_hosts
                SET ssh_host = ?, ssh_port = ?, ssh_user = ?, ssh_password = ?, ssh_key_path = ?
                WHERE TRIM(host_name) = TRIM(?)
                """,
                (
                    (ssh_host or None),
                    (int(ssh_port) if ssh_port is not None else None),
                    (ssh_user or None),
                    (encrypt_managed_bot_token(str(ssh_password)) if ssh_password else None),
                    (ssh_key_path or None),
                    host_name_n,
                ),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось обновить SSH-настройки для хоста '{host_name}': {e}")
        return False


def get_all_hosts() -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts")
            hosts = cursor.fetchall()

            result = []
            for row in hosts:
                d = _decrypt_row_secrets(dict(row), "ssh_password", "remnawave_api_token")
                d['host_name'] = normalize_host_name(d.get('host_name'))
                result.append(d)
            return result
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения списка всех хостов: {e}")
        return []

def insert_host_speedtest(
    host_name: str,
    method: str,
    ping_ms: float | None = None,
    jitter_ms: float | None = None,
    download_mbps: float | None = None,
    upload_mbps: float | None = None,
    server_name: str | None = None,
    server_id: str | None = None,
    ok: bool = True,
    error: str | None = None,
) -> bool:
    """Сохранить результат спидтеста в таблицу host_speedtests."""
    try:
        host_name_n = normalize_host_name(host_name)
        method_s = (method or '').strip().lower()
        if method_s not in ('ssh', 'net'):
            method_s = 'ssh'
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO host_speedtests
                (host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps, server_name, server_id, ok, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
                , (
                    host_name_n,
                    method_s,
                    ping_ms,
                    jitter_ms,
                    download_mbps,
                    upload_mbps,
                    server_name,
                    server_id,
                    1 if ok else 0,
                    (error or None)
                )
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Не удалось сохранить запись speedtest для '{host_name}': {e}")
        return False


def get_ssh_known_host_key(host: str, port: int) -> dict | None:
    try:
        host_s = (host or "").strip()
        port_i = int(port or 22)
        if not host_s:
            return None
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT host, port, key_type, key_base64 FROM ssh_known_hosts WHERE host = ? AND port = ?",
                (host_s, port_i),
            ).fetchone()
            return dict(row) if row else None
    except (sqlite3.Error, TypeError, ValueError) as e:
        logging.error("get_ssh_known_host_key failed: %s", e)
        return None


def save_ssh_known_host_key(host: str, port: int, key_type: str, key_base64: str) -> bool:
    try:
        host_s = (host or "").strip()
        port_i = int(port or 22)
        type_s = (key_type or "").strip()
        b64 = (key_base64 or "").strip()
        if not host_s or not b64:
            return False
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO ssh_known_hosts (host, port, key_type, key_base64)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(host, port) DO UPDATE SET key_type = excluded.key_type, key_base64 = excluded.key_base64
                """,
                (host_s, port_i, type_s, b64),
            )
            conn.commit()
        return True
    except (sqlite3.Error, TypeError, ValueError) as e:
        logging.error("save_ssh_known_host_key failed: %s", e)
        return False

def update_key_host(key_id: int, new_host_name: str) -> bool:
    return update_key_fields(key_id, host_name=new_host_name)


def get_plans_for_host(host_name: str) -> list[dict]:
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plans WHERE TRIM(host_name) = TRIM(?) ORDER BY sort_order, COALESCE(duration_days, months*30, months, 0)", (host_name,))
            plans = cursor.fetchall()
            return [dict(plan) for plan in plans]
    except sqlite3.Error as e:
        logging.error(f"Failed to get plans for host '{host_name}': {e}")
        return []



def get_active_plans_for_host(host_name: str) -> list[dict]:
    """Возвращает только активные тарифы (is_active = 1) для указанного хоста."""
    try:
        host_name = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM plans WHERE TRIM(host_name) = TRIM(?) AND COALESCE(is_active, 1) = 1 ORDER BY sort_order, COALESCE(duration_days, months*30, months, 0)",
                (host_name,)
            )
            plans = cursor.fetchall()
            return [dict(plan) for plan in plans]
    except sqlite3.Error as e:
        logging.error(f"Failed to get active plans for host '{host_name}': {e}")
        return []


def get_key_by_remnawave_uuid(remnawave_uuid: str) -> dict | None:
    if not remnawave_uuid:
        return None
    try:
        normalized_uuid = remnawave_uuid.strip()
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE remnawave_user_uuid = ? LIMIT 1",
                (normalized_uuid,),
            )
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except sqlite3.Error as e:
        logging.error("Failed to get key by remnawave uuid %s: %s", remnawave_uuid, e)
        return None


def update_key_host_and_info(
    key_id: int,
    new_host_name: str,
    new_remnawave_uuid: str,
    new_expiry_ms: int,
    **kwargs,
) -> bool:
    return update_key_fields(
        key_id,
        host_name=new_host_name,
        remnawave_user_uuid=new_remnawave_uuid,
        expire_at_ms=new_expiry_ms,
        **kwargs,
    )


def get_keys_for_host(host_name: str) -> list[dict]:
    try:
        host_name_normalized = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE TRIM(host_name) = TRIM(?)",
                (host_name_normalized,),
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except sqlite3.Error as e:
        logging.error("Failed to get keys for host '%s': %s", host_name, e)
        return []
