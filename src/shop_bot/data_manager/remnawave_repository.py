import json
import logging
import sqlite3
import time
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any

from shop_bot.data_manager import database

logger = logging.getLogger(__name__)

normalize_host_name = database.normalize_host_name


def __getattr__(name: str):
    """Модуль-level fallback (PEP 562) для `DB_FILE`.

    Раньше здесь было `DB_FILE = database.DB_FILE` — обычное присваивание,
    которое выполняется РОВНО ОДИН РАЗ, в момент первого импорта этого модуля,
    и после этого никогда не обновляется. В проде это не проблема (путь к БД
    не меняется за время жизни процесса), но в тестах, где `database.DB_FILE`
    подменяется через monkeypatch отдельно для каждого теста, `rw_repo.DB_FILE`
    оставался равным пути САМОГО ПЕРВОГО теста, из-за чего разные тесты — если
    они (сами или через любую функцию из этого модуля) трогали БД — писали и
    читали одну и ту же "чужую" временную базу, что приводило к падениям вида
    UNIQUE constraint failed / отсутствующим строкам в зависимости от порядка
    запуска тестов. Теперь `rw_repo.DB_FILE` всегда возвращает актуальное
    значение `database.DB_FILE` на момент обращения."""
    if name == "DB_FILE":
        return database.DB_FILE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# =============================
# Franchise context (current bot)
# =============================

_factory_bot_id_var: ContextVar[int] = ContextVar("factory_bot_id", default=0)


def set_current_factory_bot_id(bot_id: int) -> Any:
    """Set current factory bot id for the running handler via contextvars.

    Returns a token that can be used to reset the context.
    """
    try:
        return _factory_bot_id_var.set(int(bot_id or 0))
    except Exception:
        return _factory_bot_id_var.set(0)


def reset_current_factory_bot_id(token: Any) -> None:
    try:
        _factory_bot_id_var.reset(token)
    except Exception:
        pass


def get_current_factory_bot_id() -> int:
    try:
        return int(_factory_bot_id_var.get() or 0)
    except Exception:
        return 0


class PromoUnavailableError(Exception):
    """Промокод нельзя зарезервировать (лимит / недействителен)."""

    def __init__(self, reason: str):
        self.reason = reason or "unavailable"
        super().__init__(self.reason)


def create_payload_pending(payment_id: str, user_id: int, amount_rub, metadata) -> bool:
    """Create/update pending payload metadata.

    We inject `factory_bot_id` into metadata automatically so that:
    - successful webhooks can reply from the correct clone bot
    - partner commission can be accrued correctly

    If metadata contains a promo_code, a usage slot is reserved atomically
    before the pending row is written. Raises PromoUnavailableError when the
    slot cannot be taken (limit already exhausted).
    """
    meta = dict(metadata or {})
    if "factory_bot_id" not in meta:
        fb = get_current_factory_bot_id()
        if fb:
            meta["factory_bot_id"] = int(fb)
    promo_code = str(meta.get("promo_code") or "").strip()
    reserved = False
    if promo_code:
        applied = meta.get("promo_discount") or 0
        plan_id = None
        try:
            raw_plan = meta.get("plan_id")
            if raw_plan is not None and str(raw_plan).strip() != "":
                plan_id = int(raw_plan)
        except (TypeError, ValueError):
            plan_id = None
        promo, err = reserve_promo_code(
            promo_code,
            user_id,
            payment_id,
            applied_amount=applied,
            plan_id=plan_id,
        )
        if err or not promo:
            raise PromoUnavailableError(err or "unavailable")
        meta["promo_code"] = promo.get("code") or promo_code
        reserved = True
    ok = database.create_payload_pending(payment_id, user_id, amount_rub, meta)
    if not ok and reserved:
        try:
            release_promo_reservation(payment_id)
        except Exception:
            logger.warning("Failed to release promo reservation after pending insert failure: %s", payment_id)
    return ok


def cancel_pending_transaction(payment_id: str, user_id: int | None = None) -> bool:
    """Отменить неоплаченный pending и освободить слот промокода, если он был зарезервирован."""
    ok = database.cancel_pending_transaction(payment_id, user_id=user_id)
    if ok:
        try:
            release_promo_reservation(payment_id)
        except Exception:
            logger.warning("Failed to release promo reservation after cancelling pending %s", payment_id)
    return ok


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(database.DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _default_expire_at_ms() -> int:
    return int(datetime.utcnow().timestamp() * 1000)


def _decrypt_host_secrets(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """get_squad/list_squads читают xui_hosts напрямую — расшифровать как get_host."""
    if not row:
        return None
    return database._decrypt_row_secrets(dict(row), "ssh_password", "remnawave_api_token")


def list_squads(active_only: bool = False) -> list[dict[str, Any]]:
    query = "SELECT * FROM xui_hosts"
    params: list[Any] = []
    if active_only:
        query += " WHERE COALESCE(is_active, 1) = 1"
    query += " ORDER BY sort_order ASC, host_name ASC"
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [_decrypt_host_secrets(dict(row)) for row in cursor.fetchall()]


def get_squad(identifier: str) -> dict[str, Any] | None:
    if not identifier:
        return None
    ident = identifier.strip()
    if not ident:
        return None
    normalized = normalize_host_name(ident)
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM xui_hosts
            WHERE TRIM(host_name) = TRIM(?)
               OR TRIM(host_name) = TRIM(?)
               OR TRIM(squad_uuid) = TRIM(?)
               OR TRIM(squad_uuid) = TRIM(?)
            LIMIT 1
            """,
            (ident, normalized, ident, normalized),
        )
        row = cursor.fetchone()
        return _decrypt_host_secrets(dict(row) if row else None)


def get_key_by_id(key_id: int) -> dict | None:
    return database.get_key_by_id(key_id)


def get_key_by_email(email: str) -> dict | None:
    return database.get_key_by_email(email)


def get_key_by_remnawave_uuid(remnawave_uuid: str) -> dict | None:
    return database.get_key_by_remnawave_uuid(remnawave_uuid)


def record_key(
    user_id: int,
    squad_uuid: str,
    remnawave_user_uuid: str,
    email: str,
    *,
    host_name: str | None = None,
    expire_at_ms: int | None = None,
    short_uuid: str | None = None,
    subscription_url: str | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    tag: str | None = None,
    description: str | None = None,
) -> int | None:
    expire_ms = expire_at_ms if expire_at_ms is not None else _default_expire_at_ms()
    email_normalized = _normalize_email(email)
    host_name_norm = normalize_host_name(host_name) if host_name else None

    existing = None
    if email_normalized:
        existing = database.get_key_by_email(email_normalized)
    if not existing and remnawave_user_uuid:
        existing = database.get_key_by_remnawave_uuid(remnawave_user_uuid)

    try:
        if existing:
            key_id = existing['key_id']
            database.update_key_fields(
                key_id,
                host_name=host_name_norm or existing.get('host_name'),
                squad_uuid=squad_uuid or existing.get('squad_uuid'),
                remnawave_user_uuid=remnawave_user_uuid or existing.get('remnawave_user_uuid'),
                short_uuid=short_uuid or existing.get('short_uuid'),
                email=email_normalized or existing.get('email'),
                subscription_url=subscription_url,
                expire_at_ms=expire_ms,
                traffic_limit_bytes=traffic_limit_bytes,
                traffic_limit_strategy=traffic_limit_strategy,
                tag=tag,
                description=description,
            )
            return key_id

        return database.add_new_key(
            user_id=user_id,
            host_name=host_name_norm,
            remnawave_user_uuid=remnawave_user_uuid,
            key_email=email_normalized or email,
            expiry_timestamp_ms=expire_ms,
            squad_uuid=squad_uuid,
            short_uuid=short_uuid,
            subscription_url=subscription_url,
            traffic_limit_bytes=traffic_limit_bytes,
            traffic_limit_strategy=traffic_limit_strategy,
            description=description,
            tag=tag,
        )
    except Exception:
        logger.exception("Remnawave repository failed to record key for user %s", user_id)
        return None


def record_key_from_payload(
    user_id: int,
    payload: dict[str, Any],
    *,
    host_name: str | None = None,
    description: str | None = None,
    tag: str | None = None,
) -> int | None:
    if not payload:
        return None
    squad_uuid = (payload.get('squad_uuid') or payload.get('squadUuid') or '').strip()
    remnawave_user_uuid = str(payload.get('client_uuid') or payload.get('uuid') or payload.get('id') or '').strip()
    email = payload.get('email') or payload.get('accountEmail') or ''
    expire_at_ms = payload.get('expiry_timestamp_ms')
    if expire_at_ms is None:
        expire_iso = payload.get('expireAt') or payload.get('expiryDate')
        if expire_iso:
            try:
                expire_at_ms = int(datetime.fromisoformat(str(expire_iso).replace('Z', '+00:00')).timestamp() * 1000)
            except Exception:
                expire_at_ms = None
    return record_key(
        user_id=user_id,
        squad_uuid=squad_uuid,
        remnawave_user_uuid=remnawave_user_uuid,
        email=email,
        host_name=host_name or payload.get('host_name'),
        expire_at_ms=expire_at_ms,
        short_uuid=payload.get('short_uuid') or payload.get('shortUuid'),
        subscription_url=payload.get('subscription_url')
            or payload.get('connection_string')
            or payload.get('subscriptionUrl'),
        traffic_limit_bytes=(payload.get('traffic_limit_bytes') if payload.get('traffic_limit_bytes') is not None else payload.get('trafficLimitBytes')),
        traffic_limit_strategy=payload.get('traffic_limit_strategy') or payload.get('trafficLimitStrategy'),
        tag=tag or payload.get('tag'),
        description=description or payload.get('description'),
    )


def update_key(
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
    traffic_boost_bytes: int | None = None,
    next_traffic_reset_at: Any = database._UNSET,
    remote_access_state: str | None = None,
) -> bool:
    return database.update_key_fields(
        key_id,
        user_id=user_id,
        host_name=host_name,
        squad_uuid=squad_uuid,
        remnawave_user_uuid=remnawave_user_uuid,
        short_uuid=short_uuid,
        email=email,
        subscription_url=subscription_url,
        expire_at_ms=expire_at_ms,
        traffic_limit_bytes=traffic_limit_bytes,
        traffic_limit_strategy=traffic_limit_strategy,
        tag=tag,
        description=description,
        traffic_boost_bytes=traffic_boost_bytes,
        next_traffic_reset_at=next_traffic_reset_at,
        remote_access_state=remote_access_state,
    )


def _parse_key_expiry_dt(key: dict) -> datetime:
    """Parse key expiry from normalized row (expiry_date / expire_at)."""
    cur_expiry = key.get("expiry_date") or key.get("expire_at")
    if isinstance(cur_expiry, datetime):
        return cur_expiry.replace(tzinfo=None) if getattr(cur_expiry, "tzinfo", None) else cur_expiry
    if isinstance(cur_expiry, str):
        s = cur_expiry.strip()
        if s:
            for parser in (
                lambda x: datetime.fromisoformat(x),
                lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
                lambda x: datetime.strptime(x[:19], "%Y-%m-%d %H:%M:%S"),
            ):
                try:
                    dt = parser(s)
                    if getattr(dt, "tzinfo", None) is not None:
                        dt = dt.replace(tzinfo=None)
                    return dt
                except Exception:
                    continue
    return datetime.utcnow()


def _sync_key_expiry_ms(key_id: int, new_ms: int) -> tuple[bool, str | None, int | None]:
    """Push expiry to Remnawave, then update local DB. Returns (ok, error, final_ms)."""
    import asyncio
    from shop_bot.modules import remnawave_api

    key = get_key_by_id(key_id)
    if not key:
        return False, "not_found", None
    host = (key.get("host_name") or "").strip()
    email = (key.get("key_email") or key.get("email") or "").strip()
    if not host or not email:
        return False, "missing_host_or_email", None
    try:
        result = asyncio.run(
            remnawave_api.create_or_update_key_on_host(
                host_name=host,
                email=email,
                expiry_timestamp_ms=int(new_ms),
            )
        )
    except Exception as e:
        logger.error("extend/set key #%s Remnawave update failed: %s", key_id, e)
        return False, f"remnawave_update_failed: {e}", None
    if not result or not result.get("expiry_timestamp_ms"):
        return False, "remnawave_update_failed", None
    final_ms = int(result.get("expiry_timestamp_ms") or new_ms)
    client_uuid = result.get("client_uuid") or key.get("remnawave_user_uuid") or ""
    if not update_key(
        key_id,
        remnawave_user_uuid=client_uuid,
        expire_at_ms=final_ms,
        subscription_url=result.get("subscription_url") or result.get("connection_string"),
    ):
        return False, "db_update_failed", None
    return True, None, final_ms


def extend_key(key_id: int, days: int) -> tuple[bool, str | None]:
    """Продлить/сократить срок ключа на N дней (N может быть отрицательным).

    Синхронизирует expire с Remnawave, затем обновляет локальную БД.
    Returns (ok, error_code_or_None).
    """
    try:
        days_i = int(days)
    except Exception:
        return False, "invalid_days"
    if days_i == 0:
        return False, "zero_days"
    key = get_key_by_id(key_id)
    if not key:
        return False, "not_found"
    from datetime import timedelta

    new_dt = _parse_key_expiry_dt(key) + timedelta(days=days_i)
    new_ms = int(new_dt.timestamp() * 1000)
    ok, err, _ = _sync_key_expiry_ms(key_id, new_ms)
    return ok, err


def set_key_expiry(key_id: int, new_expire_at: datetime | str) -> tuple[bool, str | None]:
    """Установить точную дату истечения ключа; синхронизирует Remnawave + БД.

    new_expire_at: datetime или строка 'YYYY-MM-DD HH:MM[:SS]' / ISO.
    Returns (ok, error_code_or_None).
    """
    if isinstance(new_expire_at, datetime):
        new_dt = new_expire_at.replace(tzinfo=None) if getattr(new_expire_at, "tzinfo", None) else new_expire_at
    else:
        s = str(new_expire_at or "").strip()
        if not s:
            return False, "invalid_date"
        new_dt = None
        for parser in (
            lambda x: datetime.fromisoformat(x),
            lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
            lambda x: datetime.strptime(x[:19], "%Y-%m-%d %H:%M:%S"),
            lambda x: datetime.strptime(x[:16], "%Y-%m-%d %H:%M"),
            lambda x: datetime.strptime(x[:10], "%Y-%m-%d"),
        ):
            try:
                new_dt = parser(s)
                if getattr(new_dt, "tzinfo", None) is not None:
                    new_dt = new_dt.replace(tzinfo=None)
                break
            except Exception:
                continue
        if new_dt is None:
            return False, "invalid_date"
    key = get_key_by_id(key_id)
    if not key:
        return False, "not_found"
    new_ms = int(new_dt.timestamp() * 1000)
    ok, err, _ = _sync_key_expiry_ms(key_id, new_ms)
    return ok, err


def delete_key_by_email(email: str) -> bool:
    return database.delete_key_by_email(email)


def generate_key_email_for_user(user_id: int, *, domain: str = "bot.local") -> str:
    """Generate a unique key email based on Telegram ID + key number."""
    try:
        uid = int(user_id)
    except Exception:
        raise ValueError("user_id must be int")
    if uid <= 0:
        raise ValueError("user_id must be positive")
    try:
        next_number = int(database.get_next_key_number(uid))
    except Exception:
        next_number = 1
    if next_number < 1:
        next_number = 1

    number = next_number
    for _ in range(1000):
        candidate = f"{uid}-{number}@{domain}"
        if not database.get_key_by_email(candidate):
            return candidate
        number += 1

    return f"{uid}-{int(datetime.utcnow().timestamp())}@{domain}"




_LEGACY_FORWARDERS = (
    "add_support_message",
    "add_to_balance",
    "add_to_referral_balance",
    "add_to_referral_balance_all",
    # Host squads (двухпуловая схема base/lte)
    "get_host_squads",
    "add_host_squad",
    "set_host_squad_active",
    "delete_host_squad",
    "get_squad_by_class",
    "set_host_squad_overlap",
    "get_host_squad_overlap",
    "adjust_user_balance",
    "adjust_user_referral_balance",
    "ban_user",
    "create_gift_key",
    "create_host",
    "create_pending_transaction",
    "create_payload_pending",
    "claim_processed_payment",
    "unclaim_processed_payment",
    "refund_payment_once",
    "reset_pending_transaction",
    "create_plan",
    "create_support_ticket",
    "deduct_from_balance",
    "deduct_from_referral_balance",
    "delete_host",
    "delete_key_by_id",
    "delete_plan",
    "delete_ticket",
    "delete_user_keys",
    "find_and_complete_ton_transaction",
    "find_and_complete_pending_transaction",
    "get_latest_pending_for_user",
    "get_pending_status",
    "get_pending_metadata",
    "get_admin_ids",
    "get_admin_stats",
    "get_all_hosts",
    "get_all_keys",
    "get_all_settings",
    "get_all_tickets_count",
    "get_all_users",
    "get_balance",
    "get_closed_tickets_count",
    "get_daily_stats_for_charts",
    "get_host",
    "get_keys_for_host",
    "get_keys_for_user",
    "get_keys_paginated",
    "get_latest_speedtest",
    "get_next_key_number",
    "get_open_tickets_count",
    "get_paginated_transactions",
    "get_plan_by_id",
    "get_all_plans",
    "get_plans_for_host",
    "get_active_plans_for_host",
    "get_recent_transactions",
    "get_referral_balance",
    "get_referral_balance_all",
    "get_referral_count",
    "get_referrals_for_user",
    "get_setting",
    "get_speedtests",
    "get_ticket",
    "get_ticket_by_thread",
    "get_ticket_messages",
    "get_or_create_open_ticket",
    "get_tickets_paginated",
    "get_total_keys_count",
    "get_total_spent_sum",
    "get_user",
    "get_user_count",
    "get_user_keys",

    "get_users_paginated",
    "get_keys_counts_for_users",
    "get_user_tickets",
    "insert_host_speedtest",
    "initialize_db",
    "is_admin",
    "log_transaction",
    "register_user_if_not_exists",
    "search_user_keys_by_email",
    "search_all_keys_by_email",
    "run_migration",
    "claim_referral_start_bonus",
    "set_referral_start_bonus_received",
    "set_referral_trial_day_bonus_received",
    "set_terms_agreed",
    "set_ticket_status",
    "set_trial_used",
    "unban_user",
    "update_host_name",
    "update_host_remnawave_settings",
    "update_host_ssh_settings",
    "update_host_subscription_url",
    "update_host_url",
    "update_key_comment",
    "update_key_fields",
    "update_key_host",
    "update_key_host_and_info",
    "update_key_status_from_server",
    "update_plan",
    "set_plan_active",
    "update_setting",
    "update_ticket_subject",
    "update_ticket_thread_info",
    "is_subscription_expiry_notifications_enabled",
    "toggle_subscription_expiry_notifications",
    "update_user_stats",
    "set_key_auto_renew",
    "set_all_keys_auto_renew_for_user",
    "get_keys_for_auto_renew",

    # Broadcast campaigns
    "create_broadcast_campaign",
    "get_broadcast_campaigns",
    "get_broadcast_campaign",
    "update_broadcast_campaign",
    "toggle_broadcast_campaign",
    "delete_broadcast_campaign",
    "get_inactive_subscribers",
    "get_pending_broadcast_recipients",
    "is_email_only_user",
    "EMAIL_ONLY_TELEGRAM_ID_MIN",
    "EMAIL_ONLY_TELEGRAM_ID_MAX",
    "record_broadcast_sends",
    "mark_broadcast_run",
    "get_broadcast_stats",

    # Telegram reachability (blocked bot / deactivated account)
    "mark_user_unreachable",
    "mark_user_reachable",
    "get_reachability_stats",

    # Key management
    "update_key_name",
    "get_transactions_paginated",

    # User gifts (неактивированные подарки)
    "create_user_gift",
    "get_user_gift",
    "get_gift_by_code",
    "get_gift_code_by_key_id",
    "get_gift_info_by_key_id",
    "get_user_inactive_gifts",
    "activate_user_gift",
    "delete_user_gift",
    "set_referred_by_from_gift",
    "link_referrer_if_eligible",
    "unlink_referral",
    "unlink_all_referrals",
    "link_key_to_gift",

    # Unified pending action (gift / referral link opened before login)
    "create_pending_action",
    "get_pending_action",
    "claim_pending_action",
    "set_pending_action_result",
    "cleanup_expired_pending_actions",

    "get_all_ssh_targets",
    "get_ssh_target",
    "create_ssh_target",
    "update_ssh_target_fields",
    "delete_ssh_target",
    "get_ssh_known_host_key",
    "save_ssh_known_host_key",

    "insert_resource_metric",
    "get_latest_resource_metric",
    "get_metrics_series",
    "get_referral_top_rich",
    "get_referral_rank_and_count",

    # Franchise (managed clone bots)
    "resolve_factory_bot_id",
    "get_managed_bot",
    "get_managed_bot_by_telegram_id",
    "list_active_managed_bots",
    "update_managed_bot_active",
    "get_managed_bots_by_owner",
    "purge_managed_bot_stats",
    "delete_managed_bot",
    "get_factory_cabinet",
    "create_managed_bot",
    "record_factory_activity",
    "accrue_partner_commission",
    "get_partner_cabinet",
    "create_withdraw_request",
    "list_partner_requisites",
    "get_default_partner_requisite",
    "add_partner_requisite",
    "set_default_partner_requisite",
    "delete_partner_requisite",

    # Referral program: payout methods & withdrawal requests
    "list_referral_payout_methods",
    "add_referral_payout_method",
    "delete_referral_payout_method",
    "get_referral_payout_method",
    "create_referral_withdrawal_request",
    "list_referral_withdrawal_requests",
    "get_referral_withdrawal_request",
    "update_referral_withdrawal_request_status",
    "get_referral_withdrawable_stats",
    "format_referral_withdrawal_admin_notice",
    "validate_referral_payout_requisite",
    "is_referral_withdraw_method_type_enabled",
    "has_open_referral_withdrawal_request",
    "create_webapp_auth_request",
    "confirm_webapp_auth_request",
    "get_webapp_auth_request",
    "cleanup_old_webapp_auth_requests",

    # Webapp (Telegram Mini App) support
    "get_msk_time",
    "check_transaction_exists",
    "payment_owned_by_user",
    "get_seller_user",
    "get_device_tiers",
    "get_user_by_auth_token",
    "get_auth_token_by_user_id",
    "update_user_auth_token",
    "get_user_by_email",
    "create_user_by_email",
    "update_user_password",
    "hash_password",
    "verify_password",
    "set_email_verification_code",
    "get_email_verification",
    "check_email_verification_code",
    "mark_email_verified",
    "update_email_code_last_sent",
    "get_webapp_settings",
)

for _name in _LEGACY_FORWARDERS:
    if _name not in globals():
        globals()[_name] = getattr(database, _name)

__all__ = sorted(
    name for name in globals()
    if not name.startswith('_') and name not in {"logging", "sqlite3", "datetime", "Any", "database", "logger"}
)




def create_gift_token(
    token: str,
    host_name: str,
    days: int,
    *,
    activation_limit: int = 1,
    expires_at: datetime | None = None,
    created_by: int | None = None,
    comment: str | None = None,
) -> bool:
    token_s = (token or "").strip()
    if not token_s:
        raise ValueError("token is required")
    host_name_n = normalize_host_name(host_name)
    days_i = int(days)
    limit_i = int(activation_limit or 1)
    if days_i <= 0 or limit_i <= 0:
        raise ValueError("days and activation_limit must be positive")

    try:
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO gift_tokens (token, host_name, days, activation_limit, expires_at, created_by, comment)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token_s,
                    host_name_n,
                    days_i,
                    limit_i,
                    expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at,
                    created_by,
                    comment,
                ),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_gift_token(token: str) -> dict | None:
    token_s = (token or "").strip()
    if not token_s:
        return None
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gift_tokens WHERE token = ?", (token_s,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_gift_tokens(active_only: bool = False) -> list[dict]:
    query = "SELECT * FROM gift_tokens"
    params: list[Any] = []
    if active_only:
        query += " WHERE (activation_limit IS NULL OR activation_limit > activations_used)"
        query += " AND (expires_at IS NULL OR datetime(expires_at) >= datetime('now'))"
    query += " ORDER BY created_at DESC"
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]


def delete_gift_token(token: str) -> bool:
    token_s = (token or "").strip()
    if not token_s:
        return False
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gift_tokens WHERE token = ?", (token_s,))
        conn.commit()
        return cursor.rowcount > 0


def claim_gift_token(token: str, user_id: int, key_id: int | None = None) -> dict | None:
    token_s = (token or "").strip()
    if not token_s:
        return None
    user_id_i = int(user_id)
    now_iso = datetime.utcnow().isoformat()
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT token, host_name, days, activation_limit, activations_used, expires_at
            FROM gift_tokens
            WHERE token = ?
            """,
            (token_s,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        record = dict(row)
        expires_at = record.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(str(expires_at))
            except Exception:
                exp_dt = None
            if exp_dt and exp_dt < datetime.utcnow():
                return None
        activation_limit = record.get("activation_limit") or 0
        activations_used = record.get("activations_used") or 0
        if activation_limit and activations_used >= activation_limit:
            return None

        try:
            cursor.execute(
                """
                UPDATE gift_tokens
                SET activations_used = activations_used + 1,
                    last_claimed_at = ?
                WHERE token = ?
                """,
                (now_iso, token_s),
            )
            cursor.execute(
                """
                INSERT INTO gift_token_claims (token, user_id, key_id, claimed_at)
                VALUES (?, ?, ?, ?)
                """,
                (token_s, user_id_i, key_id, now_iso),
            )
            conn.commit()
            record["activations_used"] = activations_used + 1
            record["claimed_by"] = user_id_i
            record["claimed_at"] = now_iso
            record["key_id"] = key_id
            return record
        except sqlite3.Error:
            conn.rollback()
            return None




def create_promo_code(
    code: str,
    *,
    discount_percent: float | None = None,
    discount_amount: float | None = None,
    usage_limit_total: int | None = None,
    usage_limit_per_user: int | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    created_by: int | None = None,
    description: str | None = None,
    applicable_plan_ids: list[int] | str | None = None,
    segment_type: str | None = None,
    segment_value: float | None = None,
) -> bool:
    code_s = (code or "").strip().upper()
    if not code_s:
        raise ValueError("code is required")
    if (discount_percent or 0) > 0 and (discount_amount or 0) > 0:
        raise ValueError("provide either discount_percent or discount_amount, not both")
    if (discount_percent or 0) <= 0 and (discount_amount or 0) <= 0:
        raise ValueError("discount must be positive")
    if discount_percent is not None:
        try:
            dp = float(discount_percent)
        except Exception:
            raise ValueError("discount_percent must be a number")
        if dp <= 0 or dp > 100:
            raise ValueError("discount_percent must be in (0, 100]")
    if discount_amount is not None:
        try:
            da = float(discount_amount)
        except Exception:
            raise ValueError("discount_amount must be a number")
        if da <= 0:
            raise ValueError("discount_amount must be > 0")
    if usage_limit_total is not None:
        if int(usage_limit_total) <= 0:
            raise ValueError("usage_limit_total must be > 0")
    if usage_limit_per_user is not None:
        if int(usage_limit_per_user) <= 0:
            raise ValueError("usage_limit_per_user must be > 0")
    if valid_from and valid_until:
        if valid_until <= valid_from:
            raise ValueError("valid_until must be after valid_from")
    plan_ids_json = _serialize_applicable_plan_ids(applicable_plan_ids)
    segment_type_n, segment_value_n = _normalize_promo_segment(segment_type, segment_value)
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO promo_codes (
                    code, discount_percent, discount_amount,
                    usage_limit_total, usage_limit_per_user,
                    valid_from, valid_until, created_by, description,
                    applicable_plan_ids, segment_type, segment_value
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code_s,
                    float(discount_percent) if discount_percent is not None else None,
                    float(discount_amount) if discount_amount is not None else None,
                    usage_limit_total,
                    usage_limit_per_user,
                    valid_from.isoformat() if isinstance(valid_from, datetime) else valid_from,
                    valid_until.isoformat() if isinstance(valid_until, datetime) else valid_until,
                    created_by,
                    description,
                    plan_ids_json,
                    segment_type_n,
                    segment_value_n,
                ),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False


def get_promo_code(code: str) -> dict | None:
    code_s = (code or "").strip().upper()
    if not code_s:
        return None
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM promo_codes WHERE code = ?", (code_s,))
        row = cursor.fetchone()
        return dict(row) if row else None


def list_promo_codes(include_inactive: bool = True) -> list[dict]:
    query = "SELECT * FROM promo_codes"
    if not include_inactive:
        query += " WHERE is_active = 1"
    query += " ORDER BY created_at DESC"
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


PROMO_RESERVATION_TTL_HOURS = 24

# User-facing text is identical for every eligibility/limit/not-found reason so
# probing codes cannot reveal whether a coupon exists, which segment it targets,
# or whether the caller's own limit is exhausted (oracle).
PROMO_USER_ERROR = "Промокод недействителен"

PROMO_ERROR_MESSAGES = {
    "empty_code": "Введите промокод",
    "not_found": PROMO_USER_ERROR,
    "inactive": PROMO_USER_ERROR,
    "not_started": PROMO_USER_ERROR,
    "expired": PROMO_USER_ERROR,
    "total_limit_reached": PROMO_USER_ERROR,
    "user_limit_reached": PROMO_USER_ERROR,
    "plan_not_eligible": PROMO_USER_ERROR,
    "segment_not_eligible": PROMO_USER_ERROR,
    "unavailable": PROMO_USER_ERROR,
}

PROMO_SEGMENT_NO_ACTIVE_SUBSCRIPTION = "no_active_subscription"
PROMO_SEGMENT_MIN_TOTAL_SPENT = "min_total_spent"
PROMO_SEGMENT_TYPES = frozenset(
    {PROMO_SEGMENT_NO_ACTIVE_SUBSCRIPTION, PROMO_SEGMENT_MIN_TOTAL_SPENT}
)

# payment_method values that are not "money the user spent on a purchase".
_PROMO_SPENT_EXCLUDED_METHODS = ("balance", "referral_payout")


def promo_error_message(reason: str | None) -> str:
    if reason == "empty_code":
        return PROMO_ERROR_MESSAGES["empty_code"]
    return PROMO_ERROR_MESSAGES.get(reason or "", PROMO_USER_ERROR)


def _serialize_applicable_plan_ids(raw) -> str | None:
    """Validate and store plan scope as a JSON array of ints, or NULL = all plans."""
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        try:
            raw = json.loads(s)
        except Exception:
            raise ValueError("applicable_plan_ids must be a JSON array of plan_id")
    if not isinstance(raw, (list, tuple)):
        raise ValueError("applicable_plan_ids must be a list of plan_id")
    if len(raw) == 0:
        raise ValueError("applicable_plan_ids must be a non-empty list of existing plan_id")
    ids: list[int] = []
    seen: set[int] = set()
    for item in raw:
        try:
            pid = int(item)
        except (TypeError, ValueError):
            raise ValueError("applicable_plan_ids must contain integers")
        if pid <= 0:
            raise ValueError("applicable_plan_ids must contain positive plan_id")
        if pid in seen:
            continue
        if database.get_plan_by_id(pid) is None:
            raise ValueError(f"applicable_plan_ids: plan_id {pid} does not exist")
        seen.add(pid)
        ids.append(pid)
    if not ids:
        raise ValueError("applicable_plan_ids must be a non-empty list of existing plan_id")
    return json.dumps(ids)


def _normalize_promo_segment(
    segment_type: str | None, segment_value: float | None
) -> tuple[str | None, float | None]:
    st = (str(segment_type).strip() if segment_type is not None else "")
    if not st:
        return None, None
    if st not in PROMO_SEGMENT_TYPES:
        raise ValueError(
            'segment_type must be empty, "no_active_subscription", or "min_total_spent"'
        )
    if st == PROMO_SEGMENT_MIN_TOTAL_SPENT:
        try:
            value = float(segment_value)
        except (TypeError, ValueError):
            raise ValueError("segment_value is required and must be > 0 for min_total_spent")
        if value <= 0:
            raise ValueError("segment_value is required and must be > 0 for min_total_spent")
        return st, value
    return st, None


def _parse_applicable_plan_ids(raw) -> list[int] | None:
    """NULL/empty → unrestricted. Invalid JSON → empty list (fail closed)."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        try:
            ids = [int(x) for x in raw]
        except (TypeError, ValueError):
            return []
        return ids
    s = str(raw).strip()
    if not s:
        return None
    try:
        parsed = json.loads(s)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    try:
        return [int(x) for x in parsed]
    except (TypeError, ValueError):
        return []


def _coerce_plan_id(plan_id) -> int | None:
    if plan_id is None or plan_id == "":
        return None
    try:
        return int(plan_id)
    except (TypeError, ValueError):
        return None


def _user_has_active_subscription(user_id: int) -> bool:
    """True if the user has at least one vpn_keys row with expire_at > now()."""
    now = datetime.utcnow()
    keys = database.get_user_keys(int(user_id)) or []
    for key in keys:
        raw = key.get("expire_at") or key.get("expiry_date")
        if not raw:
            continue
        exp = _parse_key_expiry_dt(key)
        if exp > now:
            return True
    return False


def _user_paid_total(user_id: int, *, cursor: sqlite3.Cursor | None = None) -> float:
    """Sum of completed purchases for the user.

    Completed = transactions.status = 'paid' OR pending_transactions.status = 'paid'
    (same definition as /api/check-payment after PR #75). Pending invoices do not
    count. Internal balance transfers and referral payouts are excluded — they are
    not money the user spent on a plan.
    """
    uid = int(user_id)
    placeholders = ",".join("?" * len(_PROMO_SPENT_EXCLUDED_METHODS))
    tx_sql = f"""
        SELECT COALESCE(SUM(amount_rub), 0)
        FROM transactions
        WHERE user_id = ?
          AND LOWER(TRIM(COALESCE(status, ''))) = 'paid'
          AND LOWER(TRIM(COALESCE(payment_method, ''))) NOT IN ({placeholders})
    """
    pending_sql = """
        SELECT COALESCE(SUM(p.amount_rub), 0)
        FROM pending_transactions p
        WHERE p.user_id = ?
          AND LOWER(TRIM(COALESCE(p.status, ''))) = 'paid'
          AND NOT EXISTS (
              SELECT 1 FROM transactions t
              WHERE t.payment_id = p.payment_id
                AND LOWER(TRIM(COALESCE(t.status, ''))) = 'paid'
          )
    """
    params_tx = (uid, *_PROMO_SPENT_EXCLUDED_METHODS)

    def _sum(cur: sqlite3.Cursor) -> float:
        cur.execute(tx_sql, params_tx)
        paid = float(cur.fetchone()[0] or 0)
        try:
            cur.execute(pending_sql, (uid,))
            pending_paid = float(cur.fetchone()[0] or 0)
        except sqlite3.Error:
            pending_paid = 0.0
        return paid + pending_paid

    if cursor is not None:
        return _sum(cursor)
    with _connect() as conn:
        return _sum(conn.cursor())


def _user_matches_promo_segment(
    user_id: int,
    segment_type: str | None,
    segment_value,
    *,
    cursor: sqlite3.Cursor | None = None,
) -> bool:
    """Whether the user satisfies an optional promo segment restriction.

    segment_type is None / empty → always True (unconditional coupon).
    """
    st = (str(segment_type).strip() if segment_type is not None else "")
    if not st:
        return True
    if st == PROMO_SEGMENT_NO_ACTIVE_SUBSCRIPTION:
        return not _user_has_active_subscription(user_id)
    if st == PROMO_SEGMENT_MIN_TOTAL_SPENT:
        try:
            threshold = float(segment_value)
        except (TypeError, ValueError):
            return False
        return _user_paid_total(user_id, cursor=cursor) >= threshold
    return False


def _promo_targeting_error(
    promo: dict,
    user_id: int,
    plan_id: int | None,
    *,
    cursor: sqlite3.Cursor | None = None,
) -> str | None:
    """plan_not_eligible / segment_not_eligible, or None if targeting passes.

    Must run inside the same atomic section as limit reservation (reserve_promo_code)
    so a concurrent key/payment cannot sneak a slot after a stale preview check.
    """
    plan_ids = _parse_applicable_plan_ids(promo.get("applicable_plan_ids"))
    if plan_ids is not None:
        pid = _coerce_plan_id(plan_id)
        if pid not in plan_ids:
            return "plan_not_eligible"
    if not _user_matches_promo_segment(
        user_id,
        promo.get("segment_type"),
        promo.get("segment_value"),
        cursor=cursor,
    ):
        return "segment_not_eligible"
    return None


class _PromoTxnAbort(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _connect_promo_write() -> sqlite3.Connection:
    """Write connection with BEGIN IMMEDIATE so promo limit updates serialize."""
    conn = sqlite3.connect(database.DB_FILE, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn


def _with_promo_write(work, attempts: int = 8):
    last_err = None
    for i in range(attempts):
        conn = _connect_promo_write()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                result = work(conn)
                conn.execute("COMMIT")
                return result
            except _PromoTxnAbort as abort:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                return None, abort.reason
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        except sqlite3.OperationalError as e:
            last_err = e
            if "locked" in str(e).lower() and i < attempts - 1:
                time.sleep(0.02 * (2 ** i))
                continue
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass
    if last_err:
        raise last_err
    return None, "unavailable"


def _promo_validity_error(promo: dict, now_dt: datetime | None = None) -> str | None:
    if not promo.get("is_active"):
        return "inactive"
    now_dt = now_dt or datetime.utcnow()
    valid_from = promo.get("valid_from")
    if valid_from:
        try:
            if datetime.fromisoformat(str(valid_from)) > now_dt:
                return "not_started"
        except Exception:
            pass
    valid_until = promo.get("valid_until")
    if valid_until:
        try:
            if datetime.fromisoformat(str(valid_until)) < now_dt:
                return "expired"
        except Exception:
            pass
    return None


def _per_user_occupied(cursor: sqlite3.Cursor, code: str, user_id: int) -> int:
    cursor.execute(
        "SELECT COUNT(1) FROM promo_code_usages WHERE code = ? AND user_id = ?",
        (code, user_id),
    )
    used = int(cursor.fetchone()[0] or 0)
    try:
        cursor.execute(
            """
            SELECT COUNT(1) FROM promo_code_reservations
            WHERE code = ? AND user_id = ? AND status = 'reserved'
            """,
            (code, user_id),
        )
        reserved = int(cursor.fetchone()[0] or 0)
    except sqlite3.Error:
        reserved = 0
    return used + reserved


def _fetch_promo_row(cursor: sqlite3.Cursor, code: str) -> dict | None:
    cursor.execute(
        """
        SELECT code, discount_percent, discount_amount,
               usage_limit_total, usage_limit_per_user,
               used_total, valid_from, valid_until, is_active,
               applicable_plan_ids, segment_type, segment_value
        FROM promo_codes
        WHERE code = ?
        """,
        (code,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _atomic_increment_used_total(cursor: sqlite3.Cursor, code: str) -> int:
    """Increment used_total only if the total limit still has a free slot.

    Returns cursor.rowcount (0 → limit already exhausted / missing row).
    """
    cursor.execute(
        """
        UPDATE promo_codes
        SET used_total = COALESCE(used_total, 0) + 1
        WHERE code = ?
          AND (usage_limit_total IS NULL OR COALESCE(used_total, 0) < usage_limit_total)
        """,
        (code,),
    )
    return int(cursor.rowcount or 0)


def _decrement_used_total(cursor: sqlite3.Cursor, code: str) -> None:
    cursor.execute(
        """
        UPDATE promo_codes
        SET used_total = CASE
            WHEN COALESCE(used_total, 0) > 0 THEN used_total - 1
            ELSE 0
        END
        WHERE code = ?
        """,
        (code,),
    )


def check_promo_code_available(
    code: str,
    user_id: int,
    plan_id: int | None = None,
) -> tuple[dict | None, str | None]:
    """Проверить возможность использования промокода, не изменяя лимиты.

    Порядок внутри одной транзакции (BEGIN IMMEDIATE):
    1. промокод существует, активен, не просрочен;
    2. applicable_plan_ids — если задан и plan_id не входит в список → отказ;
    3. segment_type — если задан и сегмент не совпал → отказ;
    4. только затем проверка usage_limit_total / usage_limit_per_user.

    Финальный захват слота — атомарный reserve_promo_code / redeem_promo_code,
    который повторяет шаги 1–3 в той же секции, что и UPDATE used_total.
    """
    try:
        release_stale_promo_reservations()
    except Exception:
        pass
    code_s = (code or "").strip().upper()
    if not code_s:
        return None, "empty_code"
    user_id_i = int(user_id)
    plan_id_i = _coerce_plan_id(plan_id)

    def _work(conn: sqlite3.Connection):
        cursor = conn.cursor()
        promo = _fetch_promo_row(cursor, code_s)
        if promo is None:
            raise _PromoTxnAbort("not_found")
        validity = _promo_validity_error(promo)
        if validity:
            raise _PromoTxnAbort(validity)
        targeting = _promo_targeting_error(promo, user_id_i, plan_id_i, cursor=cursor)
        if targeting:
            raise _PromoTxnAbort(targeting)
        usage_limit_total = promo.get("usage_limit_total")
        used_total = promo.get("used_total") or 0
        if usage_limit_total and used_total >= usage_limit_total:
            raise _PromoTxnAbort("total_limit_reached")
        usage_limit_per_user = promo.get("usage_limit_per_user")
        if usage_limit_per_user:
            per_user_count = _per_user_occupied(cursor, code_s, user_id_i)
            if per_user_count >= usage_limit_per_user:
                raise _PromoTxnAbort("user_limit_reached")
        return promo, None

    result = _with_promo_write(_work)
    if isinstance(result, tuple):
        if result[1] == "expired":
            try:
                update_promo_code_status(code_s, is_active=False)
            except Exception:
                pass
        return result
    return None, "unavailable"


def reserve_promo_code(
    code: str,
    user_id: int,
    payment_id: str,
    *,
    applied_amount: float = 0.0,
    plan_id: int | None = None,
) -> tuple[dict | None, str | None]:
    """Atomically reserve one promo usage slot for a pending payment.

    Uses a single BEGIN IMMEDIATE transaction: targeting (plan/segment) first,
    then UPDATE used_total ... WHERE limit not reached, then per-user occupancy
    check. rowcount == 0 → total_limit_reached. Idempotent for the same payment_id.
    """
    try:
        release_stale_promo_reservations()
    except Exception:
        pass
    code_s = (code or "").strip().upper()
    if not code_s:
        return None, "empty_code"
    payment_id_s = (payment_id or "").strip()
    if not payment_id_s:
        return None, "unavailable"
    user_id_i = int(user_id)
    plan_id_i = _coerce_plan_id(plan_id)

    def _work(conn: sqlite3.Connection):
        cursor = conn.cursor()
        existing = None
        try:
            cursor.execute(
                "SELECT code, status FROM promo_code_reservations WHERE payment_id = ?",
                (payment_id_s,),
            )
            existing = cursor.fetchone()
        except sqlite3.Error:
            existing = None
        if existing is not None:
            status = str(existing["status"] if isinstance(existing, sqlite3.Row) else existing[1] or "")
            if status in ("reserved", "redeemed"):
                promo = _fetch_promo_row(cursor, code_s) or _fetch_promo_row(
                    cursor,
                    str(existing["code"] if isinstance(existing, sqlite3.Row) else existing[0]),
                )
                if promo:
                    return promo, None
                raise _PromoTxnAbort("not_found")
        promo = _fetch_promo_row(cursor, code_s)
        if promo is None:
            raise _PromoTxnAbort("not_found")
        validity = _promo_validity_error(promo)
        if validity:
            raise _PromoTxnAbort(validity)
        targeting = _promo_targeting_error(promo, user_id_i, plan_id_i, cursor=cursor)
        if targeting:
            raise _PromoTxnAbort(targeting)
        if _atomic_increment_used_total(cursor, code_s) == 0:
            raise _PromoTxnAbort("total_limit_reached")
        usage_limit_per_user = promo.get("usage_limit_per_user")
        if usage_limit_per_user:
            occupied = _per_user_occupied(cursor, code_s, user_id_i)
            if occupied >= int(usage_limit_per_user):
                _decrement_used_total(cursor, code_s)
                raise _PromoTxnAbort("user_limit_reached")
        try:
            cursor.execute(
                """
                INSERT INTO promo_code_reservations (payment_id, code, user_id, status)
                VALUES (?, ?, ?, 'reserved')
                """,
                (payment_id_s, code_s, user_id_i),
            )
        except sqlite3.IntegrityError:
            # Concurrent retry with the same payment_id: keep the increment
            # only if a live reservation already exists; otherwise roll back.
            cursor.execute(
                "SELECT status FROM promo_code_reservations WHERE payment_id = ?",
                (payment_id_s,),
            )
            row = cursor.fetchone()
            status = str((row["status"] if row is not None and isinstance(row, sqlite3.Row) else (row[0] if row else "")))
            if status not in ("reserved", "redeemed"):
                _decrement_used_total(cursor, code_s)
                raise _PromoTxnAbort("unavailable")
        promo["used_total"] = int(promo.get("used_total") or 0) + 1
        promo["reserved_payment_id"] = payment_id_s
        promo["applied_amount"] = float(applied_amount or 0)
        return promo, None

    result = _with_promo_write(_work)
    if isinstance(result, tuple):
        return result
    return None, "unavailable"


def release_promo_reservation(payment_id: str) -> bool:
    """Free a reserved slot (pending expired/cancelled). Never lets used_total go below 0."""
    payment_id_s = (payment_id or "").strip()
    if not payment_id_s:
        return False

    def _work(conn: sqlite3.Connection):
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT code, status FROM promo_code_reservations WHERE payment_id = ?",
                (payment_id_s,),
            )
        except sqlite3.Error:
            return False
        row = cursor.fetchone()
        if row is None:
            return False
        status = str(row["status"] if isinstance(row, sqlite3.Row) else row[1] or "")
        if status != "reserved":
            return False
        code_s = str(row["code"] if isinstance(row, sqlite3.Row) else row[0])
        cursor.execute(
            """
            UPDATE promo_code_reservations
            SET status = 'released'
            WHERE payment_id = ? AND status = 'reserved'
            """,
            (payment_id_s,),
        )
        if int(cursor.rowcount or 0) == 0:
            return False
        _decrement_used_total(cursor, code_s)
        return True

    result = _with_promo_write(_work)
    if isinstance(result, tuple):
        return False
    return bool(result)


def release_stale_promo_reservations(max_age_hours: float | None = None) -> int:
    """Release reservations older than TTL so abandoned invoices do not hold the limit forever."""
    hours = float(max_age_hours if max_age_hours is not None else PROMO_RESERVATION_TTL_HOURS)
    if hours <= 0:
        return 0
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat(sep=" ", timespec="seconds")
    try:
        with _connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT payment_id FROM promo_code_reservations
                WHERE status = 'reserved' AND datetime(reserved_at) <= datetime(?)
                """,
                (cutoff,),
            )
            ids = [str(r[0] if not isinstance(r, sqlite3.Row) else r["payment_id"]) for r in cursor.fetchall()]
    except sqlite3.Error:
        return 0
    released = 0
    for pid in ids:
        try:
            if release_promo_reservation(pid):
                released += 1
        except Exception:
            logger.warning("Failed to release stale promo reservation %s", pid, exc_info=True)
    return released


def update_promo_code_status(code: str, *, is_active: bool | None = None) -> bool:
    code_s = (code or "").strip().upper()
    if not code_s:
        return False
    sets: list[str] = []
    params: list[Any] = []
    if is_active is not None:
        sets.append("is_active = ?")
        params.append(1 if is_active else 0)
    if not sets:
        return False
    params.append(code_s)
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE promo_codes SET {', '.join(sets)} WHERE code = ?", params)
        conn.commit()
        return cursor.rowcount > 0


def delete_promo_code(code: str) -> bool:
    code_s = (code or "").strip().upper()
    if not code_s:
        return False
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM promo_codes WHERE code = ?", (code_s,))
        conn.commit()
        return cursor.rowcount > 0


def redeem_promo_code(code: str, user_id: int, *, applied_amount: float, order_id: str | None = None) -> dict | None:
    """Confirm a reserved slot (or atomically take one) and record the usage.

    If a reservation for order_id already exists, used_total is NOT incremented
    again. Legacy payments without a reservation take the slot with the same
    UPDATE ... WHERE limit check (rowcount == 0 → None).
    """
    code_s = (code or "").strip().upper()
    if not code_s:
        return None
    user_id_i = int(user_id)
    applied_amount_f = float(applied_amount)
    order_id_s = (order_id or "").strip() or None
    now_iso = datetime.utcnow().isoformat()

    def _work(conn: sqlite3.Connection):
        cursor = conn.cursor()
        reservation = None
        if order_id_s:
            try:
                cursor.execute(
                    "SELECT code, status FROM promo_code_reservations WHERE payment_id = ?",
                    (order_id_s,),
                )
                reservation = cursor.fetchone()
            except sqlite3.Error:
                reservation = None
            cursor.execute(
                "SELECT usage_id FROM promo_code_usages WHERE order_id = ?",
                (order_id_s,),
            )
            existing_usage = cursor.fetchone()
            if existing_usage is not None:
                promo = _fetch_promo_row(cursor, code_s)
                if promo:
                    promo["redeemed_by"] = user_id_i
                    promo["applied_amount"] = applied_amount_f
                    promo["order_id"] = order_id_s
                    promo["used_at"] = now_iso
                    promo["user_used_count"] = _per_user_occupied(cursor, code_s, user_id_i)
                return promo

        promo = _fetch_promo_row(cursor, code_s)
        if promo is None:
            raise _PromoTxnAbort("not_found")

        reserved_status = None
        if reservation is not None:
            reserved_status = str(
                reservation["status"] if isinstance(reservation, sqlite3.Row) else reservation[1] or ""
            )

        if reserved_status == "reserved":
            # Slot already counted in used_total at reserve time.
            pass
        elif reserved_status == "redeemed":
            promo["redeemed_by"] = user_id_i
            promo["applied_amount"] = applied_amount_f
            promo["order_id"] = order_id_s
            promo["used_at"] = now_iso
            promo["user_used_count"] = _per_user_occupied(cursor, code_s, user_id_i)
            return promo
        else:
            validity = _promo_validity_error(promo)
            if validity:
                raise _PromoTxnAbort(validity)
            if _atomic_increment_used_total(cursor, code_s) == 0:
                raise _PromoTxnAbort("total_limit_reached")
            usage_limit_per_user = promo.get("usage_limit_per_user")
            if usage_limit_per_user:
                occupied = _per_user_occupied(cursor, code_s, user_id_i)
                if occupied >= int(usage_limit_per_user):
                    _decrement_used_total(cursor, code_s)
                    raise _PromoTxnAbort("user_limit_reached")

        try:
            cursor.execute(
                """
                INSERT INTO promo_code_usages (code, user_id, applied_amount, order_id, used_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (code_s, user_id_i, applied_amount_f, order_id_s, now_iso),
            )
        except sqlite3.IntegrityError as e:
            msg = str(e).upper()
            if order_id_s and "UNIQUE" in msg:
                promo = _fetch_promo_row(cursor, code_s) or promo
                promo["redeemed_by"] = user_id_i
                promo["applied_amount"] = applied_amount_f
                promo["order_id"] = order_id_s
                promo["used_at"] = now_iso
                return promo
            raise _PromoTxnAbort("unavailable")

        if reserved_status == "reserved" and order_id_s:
            cursor.execute(
                """
                UPDATE promo_code_reservations
                SET status = 'redeemed'
                WHERE payment_id = ? AND status = 'reserved'
                """,
                (order_id_s,),
            )

        used_total = int(promo.get("used_total") or 0)
        if reserved_status != "reserved":
            used_total += 1
        promo["used_total"] = used_total
        promo["usage_limit_per_user"] = promo.get("usage_limit_per_user")
        promo["user_used_count"] = _per_user_occupied(cursor, code_s, user_id_i)
        promo["redeemed_by"] = user_id_i
        promo["applied_amount"] = applied_amount_f
        promo["order_id"] = order_id_s
        promo["used_at"] = now_iso
        return promo

    result = _with_promo_write(_work)
    if isinstance(result, tuple):
        return None
    return result

# ===== Key Search Functions =====

def search_user_keys_by_email(user_id: int, search_query: str) -> list[dict]:
    """Поиск ключей пользователя по key_email."""
    return database.search_user_keys_by_email(user_id, search_query)


def search_all_keys_by_email(search_query: str) -> list[dict]:
    """Поиск всех ключей (администраторам) по key_email."""
    return database.search_all_keys_by_email(search_query)