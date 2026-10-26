"""Сверка зависших платежей и автопродлений, рассылка оповещений админам (PR-A).

Запускается отдельной задачей раз в минуту (`run_ops_loop`) в цикле основного бота.
Две копии сверки не работают одновременно: перед проходом берётся замок `reconciler:ops`.

Режим `payment_reconciler_mode` (настройка): `off | alert | retry`, по умолчанию `alert`.
`alert` только пишет в `ops_alerts`, `retry` ещё и повторяет выдачу.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from typing import Any

from shop_bot.data_manager import auto_renew_ledger as ledger
from shop_bot.data_manager import key_write_guard as guard

logger = logging.getLogger(__name__)

RECONCILER_MODE_SETTING = "payment_reconciler_mode"
RECONCILER_MODES = ("off", "alert", "retry")

LOOP_INTERVAL_SECONDS = 60.0
STARTUP_DELAY_SECONDS = 15.0
PAID_STUCK_AFTER_SECONDS = 180.0
CLAIMED_STUCK_AFTER_SECONDS = 600.0
MAX_AGE_SECONDS = 24 * 3600.0
RETRY_SPACING_SECONDS = 600.0
MAX_RETRIES = 3
AUTORENEW_STUCK_AFTER_SECONDS = 15 * 60.0
RECONCILER_LOCK_KEY = "reconciler:ops"
RECONCILER_LOCK_TTL = 120.0

_PAID_STATUSES = ("paid", "success", "succeeded", "completed")


def get_mode() -> str:
    try:
        raw = guard._database().get_setting(RECONCILER_MODE_SETTING)
    except Exception:
        raw = None
    value = str(raw or "").strip().lower()
    return value if value in RECONCILER_MODES else "alert"


def _ensure_attempts_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_reconcile_attempts (
            payment_id TEXT PRIMARY KEY,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_attempt_at REAL NOT NULL
        )
        """
    )


def _attempts(payment_id: str) -> tuple[int, float]:
    def _work():
        with guard._conn() as conn:
            _ensure_attempts_table(conn.cursor())
            row = conn.execute(
                "SELECT attempts, last_attempt_at FROM payment_reconcile_attempts WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()
            return (int(row["attempts"]), float(row["last_attempt_at"])) if row else (0, 0.0)

    return guard._retry(_work)


def _record_attempt(payment_id: str) -> None:
    def _work():
        with guard._conn() as conn:
            _ensure_attempts_table(conn.cursor())
            conn.execute(
                "INSERT INTO payment_reconcile_attempts (payment_id, attempts, last_attempt_at) VALUES (?, 1, ?) "
                "ON CONFLICT(payment_id) DO UPDATE SET attempts = attempts + 1, last_attempt_at = excluded.last_attempt_at",
                (payment_id, time.time()),
            )

    guard._retry(_work)


def find_stuck_paid_payments(
    *, min_age: float = PAID_STUCK_AFTER_SECONDS, max_age: float = MAX_AGE_SECONDS
) -> list[dict]:
    """pending_transactions со статусом paid без подтверждённой выдачи.

    Выдача подтверждена, когда есть и итоговая запись `transactions` со статусом paid,
    и idempotency-замок в `processed_payments` (как в `_payment_service_delivered`).
    """

    def _work():
        with guard._conn() as conn:
            placeholders = ",".join("?" * len(_PAID_STATUSES))
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_payments "
                "(payment_id TEXT PRIMARY KEY, processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            try:
                rows = conn.execute(
                    f"""
                    SELECT p.payment_id, p.user_id, p.metadata, p.updated_at,
                           CAST(strftime('%s', 'now') AS INTEGER) - CAST(strftime('%s', p.updated_at) AS INTEGER) AS age_s,
                           EXISTS(SELECT 1 FROM processed_payments c WHERE c.payment_id = p.payment_id) AS claimed,
                           EXISTS(SELECT 1 FROM transactions t
                                   WHERE t.payment_id = p.payment_id
                                     AND LOWER(TRIM(COALESCE(t.status, ''))) IN ({placeholders})) AS tx_paid
                      FROM pending_transactions p
                     WHERE LOWER(TRIM(COALESCE(p.status, ''))) = 'paid'
                       AND p.updated_at IS NOT NULL
                    """,
                    _PAID_STATUSES,
                ).fetchall()
            except sqlite3.OperationalError:
                return []
            return [dict(r) for r in rows]

    out = []
    for row in guard._retry(_work):
        age = float(row.get("age_s") or 0)
        if age < min_age or age > max_age:
            continue
        if row["claimed"] and row["tx_paid"]:
            continue
        out.append(row)
    return out


def _metadata_of(row: dict) -> dict:
    try:
        meta = json.loads(row.get("metadata") or "{}")
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("payment_id", row["payment_id"])
    return meta


def _extension_recorded(payment_id: str) -> bool:
    return guard.extension_has_record(payment_id)


async def _retry_fulfillment(bot: Any, row: dict, meta: dict, *, reason: str) -> bool:
    from shop_bot.bot.handlers import process_successful_payment

    pid = row["payment_id"]
    await asyncio.to_thread(_record_attempt, pid)
    if row["claimed"]:
        from shop_bot.data_manager import remnawave_repository as rw_repo

        await asyncio.to_thread(rw_repo.unclaim_processed_payment, pid)
    logger.warning("PAYMENT_RECONCILE retry payment_id=%s reason=%s", pid, reason)
    try:
        ok = bool(await process_successful_payment(bot, meta))
    except Exception:
        logger.exception("PAYMENT_RECONCILE retry failed payment_id=%s", pid)
        ok = False
    await asyncio.to_thread(
        guard.add_ops_alert,
        "payment_reconcile_retry",
        f"Сверка повторила выдачу по платежу {pid} ({reason}): {'успешно' if ok else 'не удалась, нужна ручная проверка'}.",
    )
    return ok


async def reconcile_payment_row(bot: Any, row: dict, *, mode: str, force: bool = False) -> str:
    """Обработать один зависший платёж. Возвращает краткий итог для лога и админ-команды."""
    pid = row["payment_id"]
    meta = _metadata_of(row)
    action = str(meta.get("action") or "")
    age = float(row.get("age_s") or 0)
    claimed = bool(row["claimed"])

    if not claimed:
        if mode != "retry" and not force:
            await asyncio.to_thread(
                guard.add_ops_alert,
                "payment_stuck",
                f"Платёж {pid} (action={action}) оплачен, но выдача не начиналась ({int(age // 60)} мин). Режим сверки: {mode}.",
                dedupe_seconds=6 * 3600,
            )
            return "alert: выдача не начиналась"
        attempts, last = await asyncio.to_thread(_attempts, pid)
        if not force and (attempts >= MAX_RETRIES or time.time() - last < RETRY_SPACING_SECONDS):
            return "skip: лимит повторов"
        ok = await _retry_fulfillment(bot, row, meta, reason="claim не взят")
        return "retry: ok" if ok else "retry: не удалось"

    if age < CLAIMED_STUCK_AFTER_SECONDS and not force:
        return "skip: выдача могла ещё идти"

    delta_on = guard.get_delta_scope() == "payments"
    can_retry = action == "extend" and delta_on
    if can_retry and (mode == "retry" or force):
        attempts, last = await asyncio.to_thread(_attempts, pid)
        if not force and (attempts >= MAX_RETRIES or time.time() - last < RETRY_SPACING_SECONDS):
            return "skip: лимит повторов"
        ok = await _retry_fulfillment(bot, row, meta, reason="claim взят, продление идемпотентно")
        return "retry: ok" if ok else "retry: не удалось"

    recorded = await asyncio.to_thread(_extension_recorded, pid)
    await asyncio.to_thread(
        guard.add_ops_alert,
        "payment_stuck",
        (
            f"Платёж {pid} (action={action}) оплачен, выдача начата ({int(age // 60)} мин назад), но не завершена. "
            f"Запись продления: {'есть' if recorded else 'нет'}. "
            f"Автоповтор {'не включён' if mode != 'retry' else 'возможен только для extend при key_extension_delta_scope=payments'}; "
            f"проверьте вручную: /recheck_payment {pid}"
        ),
        dedupe_seconds=6 * 3600,
    )
    return "alert: выдача не завершена"


async def reconcile_stuck_payments(bot: Any) -> list[str]:
    mode = get_mode()
    if mode == "off":
        return []
    results = []
    rows = await asyncio.to_thread(find_stuck_paid_payments)
    for row in rows:
        try:
            outcome = await reconcile_payment_row(bot, row, mode=mode)
        except Exception:
            logger.exception("PAYMENT_RECONCILE: ошибка обработки платежа %s", row.get("payment_id"))
            outcome = "error"
        results.append(f"{row['payment_id']}: {outcome}")
    return results


async def recheck_payment(bot: Any, payment_id: str) -> str:
    """Админская команда: перепроверить один платёж независимо от режима и возраста."""
    pid = (payment_id or "").strip()
    if not pid:
        return "Укажите payment_id."
    rows = await asyncio.to_thread(find_stuck_paid_payments, min_age=0.0, max_age=10 * 365 * 86400.0)
    row = next((r for r in rows if r["payment_id"] == pid), None)
    if row is None:
        return f"Платёж {pid}: зависшей выдачи не найдено (нет записи paid в pending_transactions или выдача подтверждена)."
    outcome = await reconcile_payment_row(bot, row, mode="retry", force=True)
    return f"Платёж {pid}: {outcome}"


# --- автопродление -------------------------------------------------------------

async def reconcile_auto_renew_charges(bot: Any, *, startup: bool = False) -> list[str]:
    """Закрыть записи `charged`: срок в панели достиг цели, списание остаётся, иначе возврат."""
    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.modules import remnawave_api

    min_age = 0.0 if startup else AUTORENEW_STUCK_AFTER_SECONDS
    rows = await asyncio.to_thread(ledger.charged_older_than, min_age, before_ts=guard.BOOT_TS if startup else None)
    results = []
    for rec in rows:
        charge_id = rec["charge_id"]
        try:
            _found, panel_ms = await remnawave_api._read_panel_expiry_ms(rec["host_name"], rec["email"])
        except Exception as exc:
            logger.warning("AUTORENEW_RECONCILE: панель недоступна для %s: %s", charge_id, exc)
            if time.time() - float(rec["updated_at"]) > 3600:
                await asyncio.to_thread(
                    guard.add_ops_alert,
                    "autorenew_unresolved",
                    f"Автопродление {charge_id}: списано {rec['price']:.0f} ₽, панель недоступна больше часа, исход неизвестен.",
                    dedupe_seconds=6 * 3600,
                )
            results.append(f"{charge_id}: panel unavailable")
            continue
        if panel_ms is not None and panel_ms >= int(rec["target_ms"]):
            try:
                rw_repo.update_key_fields(int(rec["key_id"]), expire_at_ms=int(panel_ms))
            except Exception:
                logger.exception("AUTORENEW_RECONCILE: не удалось обновить срок ключа %s", rec["key_id"])
                results.append(f"{charge_id}: db update failed")
                continue
            await asyncio.to_thread(ledger.mark_applied, charge_id)
            await asyncio.to_thread(ledger.clear_attempt, int(rec["key_id"]))
            logger.info("AUTORENEW_RECONCILE: %s применено, списание оставлено", charge_id)
            results.append(f"{charge_id}: applied")
        else:
            refunded = await asyncio.to_thread(ledger.refund, charge_id)
            logger.warning("AUTORENEW_RECONCILE: %s не применено, возврат %s", charge_id, refunded)
            if refunded:
                await asyncio.to_thread(
                    guard.add_ops_alert,
                    "autorenew_refunded",
                    f"Автопродление {charge_id}: продление не подтверждено панелью, {rec['price']:.0f} ₽ возвращены на баланс пользователя {rec['user_id']}.",
                )
            results.append(f"{charge_id}: refunded")
    return results


# --- оповещения админам ----------------------------------------------------------

async def send_pending_alerts(bot: Any) -> int:
    from shop_bot.data_manager import remnawave_repository as rw_repo

    alerts = await asyncio.to_thread(guard.fetch_unsent_alerts, 20)
    if not alerts:
        return 0
    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    if not admin_ids:
        return 0
    sent_ids = []
    for alert in alerts:
        delivered = False
        for admin_id in admin_ids:
            try:
                await bot.send_message(int(admin_id), f"⚠️ {alert['text']}")
                delivered = True
            except Exception as exc:
                logger.warning("ops_alerts: не удалось отправить админу %s: %s", admin_id, exc)
        if delivered:
            sent_ids.append(alert["id"])
    await asyncio.to_thread(guard.mark_alerts_sent, sent_ids)
    return len(sent_ids)


# --- главный цикл ----------------------------------------------------------------

async def run_ops_iteration(bot: Any, *, startup: bool = False) -> None:
    owner = guard.new_owner()
    got = await asyncio.to_thread(guard.try_acquire_lock, RECONCILER_LOCK_KEY, owner, RECONCILER_LOCK_TTL)
    if not got:
        logger.debug("reconciler: другая копия сверки уже работает")
        return
    try:
        if startup:
            await reconcile_auto_renew_charges(bot, startup=True)
        else:
            await reconcile_auto_renew_charges(bot)
        await reconcile_stuck_payments(bot)
        await send_pending_alerts(bot)
        await asyncio.to_thread(guard.cleanup_old_extensions)
    finally:
        await asyncio.to_thread(guard.release_lock, RECONCILER_LOCK_KEY, owner)


async def run_ops_loop(bot_controller: Any) -> None:
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    startup = True
    while True:
        try:
            if guard.is_shutting_down():
                return
            if bot_controller.get_status().get("is_running"):
                bot = bot_controller.get_bot_instance()
                if bot:
                    await run_ops_iteration(bot, startup=startup)
                    startup = False
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("reconciler: ошибка итерации")
        await asyncio.sleep(LOOP_INTERVAL_SECONDS)
