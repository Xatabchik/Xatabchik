"""LTE-хосты и squad'ы Remnawave.

Модуль выделен из `database.py` без изменения кода функций; единый публичный
API по-прежнему предоставляет фасад `shop_bot.data_manager.database`.
"""
import sqlite3
import logging
import json
from typing import Any

from ._core import _UNSET

__all__ = (
    "plan_lte_limit_bytes",
    "should_account_lte_traffic",
    "add_host_squad",
    "get_host_squads",
    "get_squad_by_class",
    "DEFAULT_LTE_SQUAD_LABEL",
    "_SQUAD_LABEL_MAX_LEN",
    "squad_display_label",
    "get_lte_squad_display_label",
    "set_host_squad_active",
    "delete_host_squad",
    "_ensure_remnawave_squads_catalog",
    "get_remnawave_squads",
    "add_remnawave_squad",
    "delete_remnawave_squad",
    "set_host_squads_from_catalog",
    "get_host_selected_squad_catalog_ids",
    "set_host_squad_overlap",
    "get_host_squad_overlap",
    "get_plan_lte_limit",
    "get_lte_state",
    "_KEY_LTE_DEFAULT_STATE",
    "get_key_lte_state",
    "update_key_lte_state",
    "add_key_lte_boost_bytes",
    "commit_key_lte_baseline",
    "request_key_lte_baseline_reset",
    "resolve_lte_limit_bytes",
    "add_lte_boost_bytes",
    "commit_lte_baseline",
    "request_lte_baseline_reset",
    "update_lte_state",
)


def plan_lte_limit_bytes(plan: dict | None) -> int:
    return _as_limit_bytes((plan or {}).get("lte_limit_bytes"))


def should_account_lte_traffic(
    plan: dict | None,
    host_name: str | None,
    *,
    lte_squad: Any = _UNSET,
) -> bool:
    """LTE-учёт (снапшоты, baseline, энфорс) только при лимите и живом скваде.

    Безлимитный LTE (`lte_limit_bytes` 0/NULL) и хост без активного сквада класса
    `lte` не должны порождать запросы статистики на панель и строки в
    `key_lte_state` / `key_node_usage_snapshots`.
    """
    if plan_lte_limit_bytes(plan) <= 0:
        return False
    if not host_name:
        return False
    if lte_squad is not _UNSET:
        return bool(lte_squad)
    try:
        return bool(get_squad_by_class(host_name, "lte"))
    except Exception:
        return False


def add_host_squad(host_name: str, squad_uuid: str, squad_class: str = 'base', label: str | None = None) -> int | None:
    """Добавить сквад к хосту с классификацией ('base' | 'lte' | 'other')."""
    squad_class_n = str(squad_class or 'base').strip().lower()
    if squad_class_n not in ('base', 'lte', 'other'):
        squad_class_n = 'base'
    host_name_n = normalize_host_name(host_name)
    squad_uuid_n = (squad_uuid or '').strip()
    if not host_name_n or not squad_uuid_n:
        logging.warning("add_host_squad: host_name и squad_uuid обязательны")
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Не более одного активного сквада класса 'base'/'lte' на хост.
            if squad_class_n in ('base', 'lte'):
                cursor.execute(
                    "SELECT id FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE "
                    "AND squad_class = ? AND is_active = 1",
                    (host_name_n, squad_class_n),
                )
                existing = cursor.fetchone()
                if existing:
                    logging.warning(
                        f"add_host_squad: у хоста '{host_name_n}' уже есть активный сквад класса '{squad_class_n}' (id={existing[0]})"
                    )
                    return None
            cursor.execute(
                "INSERT INTO host_squads (host_name, squad_uuid, squad_class, label, is_active) VALUES (?, ?, ?, ?, 1)",
                (host_name_n, squad_uuid_n, squad_class_n, (label or None)),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        logging.warning(f"add_host_squad: сквад '{squad_uuid_n}' уже привязан к хосту '{host_name_n}'")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to add host squad for '{host_name_n}': {e}")
        return None


def get_host_squads(host_name: str, *, only_active: bool = False) -> list[dict]:
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE"
            params: list[Any] = [host_name_n]
            if only_active:
                query += " AND is_active = 1"
            query += " ORDER BY CASE squad_class WHEN 'base' THEN 0 WHEN 'lte' THEN 1 ELSE 2 END, id"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to get host squads for '{host_name}': {e}")
        return []


def get_squad_by_class(host_name: str, squad_class: str) -> dict | None:
    """Быстрый доступ к активному сквада заданного класса ('base'/'lte'/'other') хоста.

    Сравнение имени хоста — через TRIM(...) COLLATE NOCASE, как и в остальных запросах
    к хостам (`get_host`, `get_host_class`): `vpn_keys.host_name` и `host_squads.host_name`
    могут отличаться регистром/пробелами, а от результата этого запроса зависит доступность
    докупки LTE — при промахе она молча пропадала из интерфейса.
    """
    squad_class_n = str(squad_class or '').strip().lower()
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE "
                "AND squad_class = ? AND is_active = 1 ORDER BY id LIMIT 1",
                (host_name_n, squad_class_n),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to get squad by class '{squad_class}' for host '{host_name}': {e}")
        return None


DEFAULT_LTE_SQUAD_LABEL = "LTE"
_SQUAD_LABEL_MAX_LEN = 48


def squad_display_label(squad: dict | None, *, fallback: str | None = None) -> str:
    """Публичная метка сквада: поле `label`, если заполнено, иначе fallback.

    Для LTE-пула fallback по умолчанию — «LTE». Класс сквада (`squad_class`)
    остаётся внутренним идентификатором и в UI не подменяется.
    """
    raw = str((squad or {}).get("label") or "").strip()
    raw = " ".join(raw.split())
    if raw:
        return raw[:_SQUAD_LABEL_MAX_LEN]
    if fallback is not None:
        return str(fallback)
    cls = str((squad or {}).get("squad_class") or "").strip().lower()
    if cls == "base":
        return "BASE"
    if cls == "other":
        return "OTHER"
    return DEFAULT_LTE_SQUAD_LABEL


def get_lte_squad_display_label(host_name: str | None, *, fallback: str = DEFAULT_LTE_SQUAD_LABEL) -> str:
    """Метка активного LTE-сквада хоста — то, что видит пользователь вместо «LTE»."""
    if not host_name:
        return fallback
    try:
        squad = get_squad_by_class(host_name, "lte")
    except Exception:
        squad = None
    return squad_display_label(squad, fallback=fallback)


def set_host_squad_active(squad_id: int, is_active: bool) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE host_squads SET is_active = ? WHERE id = ?",
                (1 if is_active else 0, int(squad_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to set host squad active status for id {squad_id}: {e}")
        return False


def delete_host_squad(squad_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM host_squads WHERE id = ?", (int(squad_id),))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to delete host squad id {squad_id}: {e}")
        return False


def _ensure_remnawave_squads_catalog(cursor: sqlite3.Cursor) -> None:
    """Глобальный каталог сквадов Remnawave (выбираются галочками на хостах)."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS remnawave_squads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            squad_uuid TEXT NOT NULL UNIQUE,
            squad_class TEXT NOT NULL DEFAULT 'base',
            label TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remnawave_squads_class ON remnawave_squads(squad_class)")

    # Миграция: собрать уникальные сквады из host_squads и legacy xui_hosts.squad_uuid
    try:
        cursor.execute(
            """
            SELECT squad_uuid, squad_class, label
            FROM host_squads
            WHERE squad_uuid IS NOT NULL AND TRIM(squad_uuid) <> ''
            ORDER BY id
            """
        )
        for squad_uuid, squad_class, label in cursor.fetchall():
            uuid_n = (squad_uuid or "").strip()
            if not uuid_n:
                continue
            class_n = str(squad_class or "base").strip().lower()
            if class_n not in ("base", "lte", "other"):
                class_n = "base"
            cursor.execute(
                """
                INSERT OR IGNORE INTO remnawave_squads (squad_uuid, squad_class, label, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (uuid_n, class_n, (label or None)),
            )
        cursor.execute(
            "SELECT squad_uuid FROM xui_hosts WHERE squad_uuid IS NOT NULL AND TRIM(squad_uuid) <> ''"
        )
        for (squad_uuid,) in cursor.fetchall():
            uuid_n = (squad_uuid or "").strip()
            if not uuid_n:
                continue
            cursor.execute(
                """
                INSERT OR IGNORE INTO remnawave_squads (squad_uuid, squad_class, label, is_active)
                VALUES (?, 'base', 'Base (legacy)', 1)
                """,
                (uuid_n,),
            )
        # Если legacy-сквад premium-хоста был переклассифицирован в 'lte' (см.
        # _ensure_host_squads_table), выравниваем и каталог: иначе сохранение галочек
        # сквадов в веб-панели (set_host_squads_from_catalog) вернуло бы класс 'base'.
        cursor.execute(
            """
            UPDATE remnawave_squads
               SET squad_class = 'lte'
             WHERE squad_class = 'base'
               AND label = 'Base (legacy)'
               AND squad_uuid IN (SELECT squad_uuid FROM host_squads WHERE squad_class = 'lte')
            """
        )
    except sqlite3.Error as e:
        logging.warning(f"Не удалось мигрировать сквады в remnawave_squads: {e}")


def get_remnawave_squads(*, only_active: bool = False) -> list[dict]:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = "SELECT * FROM remnawave_squads"
            if only_active:
                query += " WHERE is_active = 1"
            query += " ORDER BY CASE squad_class WHEN 'base' THEN 0 WHEN 'lte' THEN 1 ELSE 2 END, id"
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"Failed to list remnawave squads: {e}")
        return []


def add_remnawave_squad(squad_uuid: str, squad_class: str = "base", label: str | None = None) -> int | None:
    squad_class_n = str(squad_class or "base").strip().lower()
    if squad_class_n not in ("base", "lte", "other"):
        squad_class_n = "base"
    uuid_n = (squad_uuid or "").strip()
    if not uuid_n:
        return None
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO remnawave_squads (squad_uuid, squad_class, label, is_active)
                VALUES (?, ?, ?, 1)
                """,
                (uuid_n, squad_class_n, (label or None)),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        logging.warning(f"add_remnawave_squad: UUID уже есть в каталоге: {uuid_n}")
        return None
    except sqlite3.Error as e:
        logging.error(f"Failed to add remnawave squad: {e}")
        return None


def delete_remnawave_squad(squad_id: int) -> bool:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT squad_uuid FROM remnawave_squads WHERE id = ?", (int(squad_id),))
            row = cursor.fetchone()
            if not row:
                return False
            uuid_n = row["squad_uuid"]
            cursor.execute("DELETE FROM remnawave_squads WHERE id = ?", (int(squad_id),))
            cursor.execute("DELETE FROM host_squads WHERE squad_uuid = ?", (uuid_n,))
            # Сброс legacy squad_uuid у хостов, если указывал удалённый сквад
            cursor.execute(
                "UPDATE xui_hosts SET squad_uuid = NULL WHERE TRIM(COALESCE(squad_uuid, '')) = TRIM(?)",
                (uuid_n,),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"Failed to delete remnawave squad id {squad_id}: {e}")
        return False


def set_host_squads_from_catalog(host_name: str, catalog_ids: list[int]) -> bool:
    """Выставить привязку хоста к сквадам каталога (галочки). Синхронизирует host_squads и squad_uuid."""
    host_name_n = normalize_host_name(host_name)
    if not host_name_n:
        return False
    try:
        wanted_ids = {int(x) for x in (catalog_ids or []) if str(x).strip().isdigit() or isinstance(x, int)}
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM xui_hosts WHERE TRIM(host_name) = TRIM(?)", (host_name_n,))
            if cursor.fetchone() is None:
                return False

            selected: list[dict] = []
            if wanted_ids:
                placeholders = ",".join("?" for _ in wanted_ids)
                cursor.execute(
                    f"SELECT * FROM remnawave_squads WHERE id IN ({placeholders}) AND is_active = 1",
                    tuple(wanted_ids),
                )
                selected = [dict(r) for r in cursor.fetchall()]

            # Не более одного base/lte — оставляем первый по приоритету каталога
            filtered: list[dict] = []
            seen_class: set[str] = set()
            for sq in sorted(
                selected,
                key=lambda s: {"base": 0, "lte": 1}.get(str(s.get("squad_class") or ""), 2),
            ):
                cls = str(sq.get("squad_class") or "other").lower()
                if cls in ("base", "lte") and cls in seen_class:
                    continue
                if cls in ("base", "lte"):
                    seen_class.add(cls)
                filtered.append(sq)

            wanted_uuids = {(sq.get("squad_uuid") or "").strip() for sq in filtered}
            wanted_uuids.discard("")

            cursor.execute(
                "SELECT id, squad_uuid FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (host_name_n,),
            )
            existing = [(int(r["id"]), (r["squad_uuid"] or "").strip()) for r in cursor.fetchall()]
            for row_id, uuid_n in existing:
                if uuid_n not in wanted_uuids:
                    cursor.execute("DELETE FROM host_squads WHERE id = ?", (row_id,))

            cursor.execute(
                "SELECT squad_uuid FROM host_squads WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (host_name_n,),
            )
            have = {(r["squad_uuid"] or "").strip() for r in cursor.fetchall()}
            for sq in filtered:
                uuid_n = (sq.get("squad_uuid") or "").strip()
                if not uuid_n or uuid_n in have:
                    continue
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO host_squads (host_name, squad_uuid, squad_class, label, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (
                        host_name_n,
                        uuid_n,
                        str(sq.get("squad_class") or "base").lower(),
                        sq.get("label"),
                    ),
                )

            base_uuid = None
            for sq in filtered:
                if str(sq.get("squad_class") or "").lower() == "base":
                    base_uuid = (sq.get("squad_uuid") or "").strip() or None
                    break
            cursor.execute(
                "UPDATE xui_hosts SET squad_uuid = ? WHERE TRIM(host_name) = TRIM(?)",
                (base_uuid, host_name_n),
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        logging.error(f"set_host_squads_from_catalog failed for '{host_name}': {e}")
        return False


def get_host_selected_squad_catalog_ids(host_name: str) -> list[int]:
    """ID записей каталога, привязанных к хосту через host_squads.uuid."""
    try:
        host_name_n = normalize_host_name(host_name)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rs.id
                FROM remnawave_squads rs
                INNER JOIN host_squads hs ON hs.squad_uuid = rs.squad_uuid
                WHERE TRIM(hs.host_name) = TRIM(?) COLLATE NOCASE
                ORDER BY rs.id
                """,
                (host_name_n,),
            )
            return [int(r[0]) for r in cursor.fetchall()]
    except sqlite3.Error as e:
        logging.error(f"get_host_selected_squad_catalog_ids failed for '{host_name}': {e}")
        return []


def set_host_squad_overlap(host_name: str, overlap_nodes: list[dict] | None) -> bool:
    """Сохранить результат проверки пересечения нод LTE- и base-сквадов хоста.

    Пустой список означает «проверено, пересечений нет» — это не то же самое, что NULL
    («не проверялось»), поэтому дата проверки пишется в обоих случаях.
    """
    try:
        payload = json.dumps(
            [
                {"uuid": n.get("uuid"), "node_name": n.get("node_name")}
                for n in (overlap_nodes or [])
                if isinstance(n, dict) and n.get("uuid")
            ],
            ensure_ascii=False,
        )
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE xui_hosts SET squad_node_overlap = ?, squad_node_overlap_checked_at = ? "
                "WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (payload, _now_str(), normalize_host_name(host_name)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except (sqlite3.Error, TypeError, ValueError) as e:
        logging.error(f"Failed to store squad node overlap for host '{host_name}': {e}")
        return False


def get_host_squad_overlap(host_name: str) -> list[dict]:
    """Ноды, доступные и через LTE-, и через base-сквад хоста (по последней проверке)."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT squad_node_overlap FROM xui_hosts "
                "WHERE TRIM(host_name) = TRIM(?) COLLATE NOCASE",
                (normalize_host_name(host_name),),
            )
            row = cursor.fetchone()
        raw = row[0] if row else None
        if not raw:
            return []
        parsed = json.loads(raw)
        return [p for p in parsed if isinstance(p, dict)] if isinstance(parsed, list) else []
    except (sqlite3.Error, json.JSONDecodeError) as e:
        logging.error(f"Failed to read squad node overlap for host '{host_name}': {e}")
        return []


def get_plan_lte_limit(plan_id: int) -> int:
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT lte_limit_bytes FROM plans WHERE plan_id = ?", (int(plan_id),))
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] else 0
    except sqlite3.Error as e:
        logging.error(f"Failed to get lte_limit_bytes for plan {plan_id}: {e}")
        return 0


def get_lte_state(user_id: int) -> dict:
    """УСТАРЕЛО: пользовательская модель LTE-пула.

    Состояние LTE перенесено на ключ (`key_lte_state`, см. `get_key_lte_state`), потому что
    лимит задаётся тарифом конкретного ключа, а расход считается по нодам его хоста.
    Функции этой группы оставлены только ради читаемости данных, уже перенесённых
    миграцией `_migrate_subscription_lte_to_keys`, и в рантайме не используются.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscription_lte WHERE user_id = ?", (int(user_id),))
            row = cursor.fetchone()
            if row:
                return dict(row)
            # Новая подписка: baseline = 0 и он сразу считается определённым — расход
            # начинаем считать с нуля. Backfill по факту расхода нужен только строкам,
            # созданным до появления lte_baseline_initialized_at.
            created_at = _now_str()
            cursor.execute(
                "INSERT INTO subscription_lte (user_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, "
                "premium_state, lte_baseline_initialized_at) VALUES (?, 0, 0, 0, 'enabled', ?)",
                (int(user_id), created_at)
            )
            conn.commit()
            return {
                "user_id": int(user_id),
                "lte_limit_bytes": 0,
                "lte_used_bytes": 0,
                "lte_boost_bytes": 0,
                "lte_used_baseline_bytes": 0,
                "lte_baseline_reset_requested": 0,
                "lte_baseline_initialized_at": created_at,
                "lte_reset_at": None,
                "premium_state": "enabled",
            }
    except sqlite3.Error as e:
        logging.error(f"Failed to get LTE state for user {user_id}: {e}")
        return {
            "user_id": int(user_id),
            "lte_limit_bytes": 0,
            "lte_used_bytes": 0,
            "lte_boost_bytes": 0,
            "lte_used_baseline_bytes": 0,
            "lte_baseline_reset_requested": 0,
            "lte_baseline_initialized_at": None,
            "lte_reset_at": None,
            "premium_state": "enabled",
        }


_KEY_LTE_DEFAULT_STATE = {
    "lte_limit_bytes": 0,
    "lte_used_bytes": 0,
    "lte_boost_bytes": 0,
    "lte_used_baseline_bytes": 0,
    "lte_baseline_reset_requested": 0,
    "lte_baseline_initialized_at": None,
    "lte_reset_at": None,
    "premium_state": "enabled",
}


def get_key_lte_state(key_id: int) -> dict:
    """Состояние LTE-пула конкретного ключа (создаёт строку при отсутствии).

    `lte_baseline_initialized_at` намеренно НЕ проставляется при вставке: точку отсчёта
    выставляет первый проход воркера по фактическому расходу. Для нового ключа расход
    близок к нулю, а для ключа, у которого LTE-сквад появился позже, это защищает от
    мгновенного исчерпания лимита накопленной историей нод.
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM key_lte_state WHERE key_id = ?", (int(key_id),))
            row = cursor.fetchone()
            if row:
                return dict(row)
            cursor.execute(
                "INSERT INTO key_lte_state (key_id, premium_state, updated_at) VALUES (?, 'enabled', ?)",
                (int(key_id), _now_str()),
            )
            conn.commit()
            return {"key_id": int(key_id), **_KEY_LTE_DEFAULT_STATE}
    except sqlite3.Error as e:
        logging.error(f"Failed to get LTE state for key {key_id}: {e}")
        return {"key_id": int(key_id), **_KEY_LTE_DEFAULT_STATE}


def update_key_lte_state(
    key_id: int,
    *,
    lte_limit_bytes: int | None = None,
    lte_used_bytes: int | None = None,
    lte_boost_bytes: int | None = None,
    lte_used_baseline_bytes: int | None = None,
    lte_baseline_reset_requested: bool | None = None,
    lte_reset_at: Any = _UNSET,
    premium_state: str | None = None,
) -> bool:
    get_key_lte_state(key_id)  # ensure row exists
    fields: dict[str, Any] = {}
    if lte_limit_bytes is not None:
        fields["lte_limit_bytes"] = int(lte_limit_bytes)
    if lte_used_bytes is not None:
        fields["lte_used_bytes"] = int(lte_used_bytes)
    if lte_boost_bytes is not None:
        fields["lte_boost_bytes"] = int(lte_boost_bytes)
    if lte_used_baseline_bytes is not None:
        fields["lte_used_baseline_bytes"] = int(lte_used_baseline_bytes)
    if lte_baseline_reset_requested is not None:
        fields["lte_baseline_reset_requested"] = 1 if lte_baseline_reset_requested else 0
    if lte_reset_at is not _UNSET:
        fields["lte_reset_at"] = lte_reset_at
    if premium_state is not None:
        fields["premium_state"] = premium_state
    if not fields:
        return True
    fields["updated_at"] = _now_str()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE key_lte_state SET {set_clause} WHERE key_id = ?",
                list(fields.values()) + [int(key_id)],
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update LTE state for key {key_id}: {e}")
        return False


def add_key_lte_boost_bytes(key_id: int, add_bytes: int) -> int | None:
    """Атомарно увеличить докупленный LTE-буст КЛЮЧА. Возвращает новое значение."""
    try:
        add = int(add_bytes or 0)
    except (TypeError, ValueError):
        return None
    if add <= 0:
        return None
    get_key_lte_state(key_id)  # ensure row exists
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "UPDATE key_lte_state "
                "SET lte_boost_bytes = COALESCE(lte_boost_bytes, 0) + ?, "
                "    premium_state = 'enabled', updated_at = ? "
                "WHERE key_id = ?",
                (add, _now_str(), int(key_id)),
            )
            if cursor.rowcount <= 0:
                conn.rollback()
                return None
            cursor.execute("SELECT lte_boost_bytes FROM key_lte_state WHERE key_id = ?", (int(key_id),))
            row = cursor.fetchone()
            conn.commit()
            return int(row[0] or 0) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to add LTE boost for key {key_id}: {e}")
        return None


def commit_key_lte_baseline(key_id: int, baseline_bytes: int, *, expire_boost: bool) -> bool:
    """Зафиксировать точку отсчёта LTE-расхода ключа одной транзакцией."""
    get_key_lte_state(key_id)  # ensure row exists
    try:
        baseline = max(0, int(baseline_bytes or 0))
    except (TypeError, ValueError):
        baseline = 0
    sets = [
        "lte_used_baseline_bytes = ?",
        "lte_baseline_reset_requested = 0",
        "lte_baseline_initialized_at = ?",
        "updated_at = ?",
    ]
    values: list[Any] = [baseline, _now_str(), _now_str()]
    if expire_boost:
        sets.append("lte_boost_bytes = 0")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                f"UPDATE key_lte_state SET {', '.join(sets)} WHERE key_id = ?",
                values + [int(key_id)],
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to commit LTE baseline for key {key_id}: {e}")
        return False


def request_key_lte_baseline_reset(key_id: int) -> bool:
    """Пометить начало нового расчётного периода LTE у ключа (буст сгорит вместе с baseline)."""
    get_key_lte_state(key_id)  # ensure row exists
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE key_lte_state SET lte_baseline_reset_requested = 1, updated_at = ? WHERE key_id = ?",
                (_now_str(), int(key_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to request LTE baseline reset for key {key_id}: {e}")
        return False


def resolve_lte_limit_bytes(lte_state: dict | None, plan_lte_limit_bytes: int = 0) -> int:
    """Единая формула эффективного LTE-лимита: лимит тарифа + докупленный буст.

    Источник истины по базовому лимиту — `plans.lte_limit_bytes`; значение в
    `subscription_lte.lte_limit_bytes` используется только как fallback (тариф ключа
    не определился). Функция обязана быть единственной формулой и для отображения
    в боте, и для энфорсинга в планировщике — раньше они расходились: UI показывал
    лимит вместе с бустом, а воркер сравнивал расход только с лимитом тарифа.
    """
    base = int(plan_lte_limit_bytes or 0)
    if base <= 0:
        try:
            base = int((lte_state or {}).get("lte_limit_bytes") or 0)
        except (TypeError, ValueError):
            base = 0
    try:
        boost = int((lte_state or {}).get("lte_boost_bytes") or 0)
    except (TypeError, ValueError):
        boost = 0
    return max(0, base) + max(0, boost)


def add_lte_boost_bytes(user_id: int, add_bytes: int) -> int | None:
    """Атомарно увеличить докупленный LTE-буст пользователя на `add_bytes`.

    Read-modify-write через `get_lte_state()` + `update_lte_state()` терял одну из
    покупок при двух параллельных оплатах (lost update), поэтому инкремент выполняется
    одним UPDATE внутри BEGIN IMMEDIATE. Возвращает новое значение `lte_boost_bytes`
    или None, если обновить не удалось.
    """
    try:
        add = int(add_bytes or 0)
    except (TypeError, ValueError):
        return None
    if add <= 0:
        return None
    get_lte_state(user_id)  # ensure row exists
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                "UPDATE subscription_lte "
                "SET lte_boost_bytes = COALESCE(lte_boost_bytes, 0) + ?, "
                "    premium_state = 'enabled', updated_at = ? "
                "WHERE user_id = ?",
                (add, _now_str(), int(user_id)),
            )
            if cursor.rowcount <= 0:
                conn.rollback()
                return None
            cursor.execute("SELECT lte_boost_bytes FROM subscription_lte WHERE user_id = ?", (int(user_id),))
            row = cursor.fetchone()
            conn.commit()
            return int(row[0] or 0) if row else None
    except sqlite3.Error as e:
        logging.error(f"Failed to add LTE boost for user {user_id}: {e}")
        return None


def commit_lte_baseline(user_id: int, baseline_bytes: int, *, expire_boost: bool) -> bool:
    """Зафиксировать точку отсчёта (baseline) LTE-расхода одной транзакцией.

    `expire_boost=True` — начало нового расчётного периода: докупленный буст сгорает
    вместе со сбросом счётчика, симметрично основному пулу (там при ежемесячном сбросе
    обнуляется `vpn_keys.traffic_boost_bytes`).
    `expire_boost=False` — первичная инициализация baseline у существующей подписки:
    счётчик расхода начинаем с текущего накопительного значения панели, но уже
    оплаченный буст сохраняем.
    """
    get_lte_state(user_id)  # ensure row exists
    try:
        baseline = max(0, int(baseline_bytes or 0))
    except (TypeError, ValueError):
        baseline = 0
    sets = [
        "lte_used_baseline_bytes = ?",
        "lte_baseline_reset_requested = 0",
        "lte_baseline_initialized_at = ?",
        "updated_at = ?",
    ]
    values: list[Any] = [baseline, _now_str(), _now_str()]
    if expire_boost:
        sets.append("lte_boost_bytes = 0")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute(
                f"UPDATE subscription_lte SET {', '.join(sets)} WHERE user_id = ?",
                values + [int(user_id)],
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to commit LTE baseline for user {user_id}: {e}")
        return False


def request_lte_baseline_reset(user_id: int) -> bool:
    """Помечает начало нового расчётного периода LTE-пула.

    Воркер `enforce_dual_traffic_limits` на следующем проходе зафиксирует текущее сырое
    (накопительное) значение расхода по LTE-нодам как новую точку отсчёта и обнулит
    докупленный буст (см. `commit_lte_baseline(expire_boost=True)`).

    ВАЖНО: этот флаг больше не выставляется при докупке LTE-пакета — покупка обязана быть
    строго аддитивной (+N ГБ к остатку), а не сбросом счётчика расхода. Иначе покупка
    минимального пакета заново выдавала полный лимит тарифа.
    """
    get_lte_state(user_id)  # ensure row exists
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE subscription_lte SET lte_baseline_reset_requested = 1, updated_at = ? WHERE user_id = ?",
                (_now_str(), int(user_id)),
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to request LTE baseline reset for user {user_id}: {e}")
        return False


def update_lte_state(
    user_id: int,
    *,
    lte_limit_bytes: int | None = None,
    lte_used_bytes: int | None = None,
    lte_boost_bytes: int | None = None,
    lte_used_baseline_bytes: int | None = None,
    lte_baseline_reset_requested: bool | None = None,
    lte_reset_at: Any = _UNSET,
    premium_state: str | None = None,
) -> bool:
    get_lte_state(user_id)  # ensure row exists
    fields: dict[str, Any] = {}
    if lte_limit_bytes is not None:
        fields["lte_limit_bytes"] = int(lte_limit_bytes)
    if lte_used_bytes is not None:
        fields["lte_used_bytes"] = int(lte_used_bytes)
    if lte_boost_bytes is not None:
        fields["lte_boost_bytes"] = int(lte_boost_bytes)
    if lte_used_baseline_bytes is not None:
        fields["lte_used_baseline_bytes"] = int(lte_used_baseline_bytes)
    if lte_baseline_reset_requested is not None:
        fields["lte_baseline_reset_requested"] = 1 if lte_baseline_reset_requested else 0
    if lte_reset_at is not _UNSET:
        fields["lte_reset_at"] = lte_reset_at
    if premium_state is not None:
        fields["premium_state"] = premium_state
    if not fields:
        return True
    fields["updated_at"] = _now_str()
    try:
        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [int(user_id)]
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE subscription_lte SET {set_clause} WHERE user_id = ?", values)
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logging.error(f"Failed to update LTE state for user {user_id}: {e}")
        return False
