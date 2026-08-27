import asyncio
import logging
import json

from datetime import datetime, timedelta

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot

from shop_bot.bot_controller import BotController
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.data_manager import resource_monitor
from shop_bot.data_manager import speedtest_runner
from shop_bot.data_manager import backup_manager

from shop_bot.modules import remnawave_api
from shop_bot.modules import telegram_reachability
from shop_bot.bot import keyboards

CHECK_INTERVAL_SECONDS = 300
NOTIFY_BEFORE_HOURS = {72, 48, 24, 1}
AUTO_RENEW_RETRY_COOLDOWN_HOURS = 6
notified_users = {}
_auto_renew_attempts: dict[int, datetime] = {}

logger = logging.getLogger(__name__)



SPEEDTEST_INTERVAL_SECONDS = 8 * 3600
SYNC_KEYS_WITH_PANELS_INTERVAL_SECONDS = 30 * 60  # heavy operation; don't run every 5 minutes
INACTIVE_USAGE_REMINDER_INTERVAL_SECONDS = 8 * 3600
FIRST_INACTIVE_REMINDER_DELAY_SECONDS = 8 * 3600
_last_speedtests_run_at: datetime | None = None
_last_backup_run_at: datetime | None = None
_last_resource_collect_at: datetime | None = None
_last_resource_alert_at: dict[tuple[str, str, str], datetime] = {}
_last_sync_keys_with_panels_at: datetime | None = None
_last_sync_with_panels_at: datetime | None = None
_last_dual_traffic_limits_at: datetime | None = None
DUAL_LIMIT_DEFAULT_INTERVAL_SECONDS = 120

def format_time_left(hours: int) -> str:
    if hours >= 24:
        days = hours // 24
        if days % 10 == 1 and days % 100 != 11:
            return f"{days} день"
        elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
            return f"{days} дня"
        else:
            return f"{days} дней"
    else:
        if hours % 10 == 1 and hours % 100 != 11:
            return f"{hours} час"
        elif 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20):
            return f"{hours} часа"
        else:
            return f"{hours} часов"

async def send_subscription_notification(bot: Bot, user_id: int, key_id: int, time_left_hours: int, expiry_date: datetime):
    try:
        time_text = format_time_left(time_left_hours)
        expiry_str = expiry_date.strftime('%d.%m.%Y в %H:%M')
        
        message = (
            f"⚠️ **Внимание!** ⚠️\n\n"
            f"Срок действия вашей подписки истекает через **{time_text}**.\n"
            f"Дата окончания: **{expiry_str}**\n\n"
            f"Продлите подписку, чтобы не остаться без доступа к VPN!"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔑 Мои ключи", callback_data="manage_keys")
        builder.button(text="➕ Продлить ключ", callback_data=f"extend_key_{key_id}")
        builder.adjust(2)
        
        await bot.send_message(chat_id=user_id, text=message, reply_markup=builder.as_markup(), parse_mode='Markdown')
        logger.debug(f"Scheduler: Отправлено уведомление пользователю {user_id} по ключу {key_id} (осталось {time_left_hours} ч).")
        
    except Exception as e:
        if not telegram_reachability.handle_send_exception(user_id, e):
            logger.error(f"Scheduler: Ошибка отправки уведомления пользователю {user_id}: {e}")

def _cleanup_notified_users(all_db_keys: list[dict]):
    if not notified_users:
        return

    logger.debug("Scheduler: Очищаю кэш уведомлений...")
    
    active_key_ids = {key['key_id'] for key in all_db_keys}
    
    users_to_check = list(notified_users.keys())
    
    cleaned_users = 0
    cleaned_keys = 0

    for user_id in users_to_check:
        keys_to_check = list(notified_users[user_id].keys())
        for key_id in keys_to_check:
            if key_id not in active_key_ids:
                del notified_users[user_id][key_id]
                cleaned_keys += 1
        
        if not notified_users[user_id]:
            del notified_users[user_id]
            cleaned_users += 1
    
    if cleaned_users > 0 or cleaned_keys > 0:
        logger.debug(f"Scheduler: Очистка завершена. Удалено записей пользователей: {cleaned_users}, ключей: {cleaned_keys}.")

async def check_expiring_subscriptions(bot: Bot):
    logger.debug("Scheduler: Проверяю истекающие подписки...")
    current_time = datetime.now()
    all_keys = rw_repo.get_all_keys()
    
    _cleanup_notified_users(all_keys)
    
    for key in all_keys:
        try:
            expiry_date = datetime.fromisoformat(key['expiry_date'])
            time_left = expiry_date - current_time

            if time_left.total_seconds() < 0:
                continue

            total_hours_left = int(time_left.total_seconds() / 3600)
            user_id = key['user_id']
            key_id = key['key_id']

            for hours_mark in NOTIFY_BEFORE_HOURS:
                if hours_mark - 1 < total_hours_left <= hours_mark:
                    notified_users.setdefault(user_id, {}).setdefault(key_id, set())
                    
                    if hours_mark not in notified_users[user_id][key_id]:
                        # Проверяем, включены ли уведомления для пользователя
                        try:
                            if not rw_repo.is_subscription_expiry_notifications_enabled(user_id):
                                logger.debug(f"Scheduler: Уведомления отключены для пользователя {user_id}, ключ {key_id}")
                                notified_users[user_id][key_id].add(hours_mark)
                                break
                        except Exception as e:
                            logger.warning(f"Scheduler: Ошибка проверки статуса уведомлений для {user_id}: {e}")
                        
                        await send_subscription_notification(bot, user_id, key_id, hours_mark, expiry_date)
                        notified_users[user_id][key_id].add(hours_mark)
                    break 
                    
        except Exception as e:
            logger.error(f"Scheduler: Ошибка обработки истечения для ключа {key.get('key_id')}: {e}")


def _parse_dt_safe(value: str | None) -> datetime | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("T", " ").replace("Z", "")
    # ожидаемые длины строк для форматов
    formats = [
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ]
    for fmt, n in formats:
        try:
            return datetime.strptime(s[:n], fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _extract_used_bytes(payload: dict | None) -> int:
    """Пытаемся извлечь использованный трафик из payload пользователя Remnawave (если поле есть)."""
    if not isinstance(payload, dict):
        return 0
    candidates = [
        "trafficUsedBytes", "traffic_used_bytes", "usedTrafficBytes",
        "trafficUsed", "traffic_used", "usedBytes", "bytesUsed",
        "up", "down",
    ]
    for k in candidates:
        v = payload.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
        if isinstance(v, str) and v.isdigit():
            try:
                iv = int(v)
                if iv > 0:
                    return iv
            except Exception:
                pass
    # иногда статистика может быть вложенной
    for key in ("traffic", "usage", "stats"):
        v = payload.get(key)
        if isinstance(v, dict):
            b = _extract_used_bytes(v)
            if b > 0:
                return b
    return 0


def _is_true(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "on", "yes", "y")


def _get_inactive_usage_reminder_enabled() -> bool:
    """Глобальный переключатель напоминаний о нулевом использовании трафика."""
    raw = rw_repo.get_setting("inactive_usage_reminder_enabled")
    if raw is None:
        raw = "true"
    return _is_true(raw)


def _get_inactive_usage_reminder_interval_hours() -> float:
    """Интервал напоминаний в часах (также используется как задержка перед первым напоминанием)."""
    raw = rw_repo.get_setting("inactive_usage_reminder_interval_hours") or "8"
    try:
        val = float(str(raw).strip().replace(",", "."))
    except Exception:
        val = 8.0
    # sane bounds: 1h..168h
    if val < 1:
        val = 1.0
    if val > 168:
        val = 168.0
    return val


def _get_inactive_usage_reminder_interval_seconds() -> int:
    return int(_get_inactive_usage_reminder_interval_hours() * 3600)


def _parse_origin_meta_from_description(description: str | None) -> dict | None:
    if not description:
        return None
    s = str(description).strip()
    if not s:
        return None
    try:
        payload = json.loads(s)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _try_int(v) -> int | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, (int, float)):
            iv = int(v)
            return iv
        s = str(v).strip()
        if not s:
            return None
        iv = int(float(s.replace(",", ".")))
        return iv
    except Exception:
        return None


def _resolve_hwid_device_limit_for_key(key: dict, remote_user: dict | None) -> int | None:
    """Определить допустимый лимит устройств для ключа.

    Приоритет:
      1) Remnawave поле hwidDeviceLimit (если есть)
      2) План из vpn_keys.description (origin meta -> plan_id)
      3) Настройка trial_device_limit (для триала)
    """
    # 1) remnawave
    if isinstance(remote_user, dict):
        for k in ("hwidDeviceLimit", "hwid_device_limit", "deviceLimit", "device_limit"):
            limit = _try_int(remote_user.get(k))
            if limit and limit > 0:
                return limit

    desc = key.get("description")
    meta = _parse_origin_meta_from_description(desc)
    is_trial = False
    plan_id = None
    if isinstance(meta, dict):
        is_trial = bool(meta.get("is_trial"))
        plan_id = meta.get("plan_id")
        if plan_id in ("", None):
            plan_id = None

    # 2) plan hwid_device_limit
    if plan_id is not None:
        try:
            plan = rw_repo.get_plan_by_id(int(plan_id)) or {}
        except Exception:
            plan = {}
        limit = _try_int(plan.get("hwid_device_limit") or plan.get("hwidDeviceLimit"))
        if limit and limit > 0:
            return limit

    # 3) trial limit from settings
    if is_trial or (str(key.get("tag") or "").strip().lower() == "trial"):
        try:
            raw = rw_repo.get_setting("trial_device_limit")
        except Exception:
            raw = None
        limit = _try_int(raw)
        if limit and limit > 0:
            return limit
    return None


def _extract_device_ids(devices_payload) -> list[str]:
    ids: list[str] = []
    if isinstance(devices_payload, list):
        for item in devices_payload:
            if isinstance(item, dict):
                v = (
                    item.get("deviceId")
                    or item.get("device_id")
                    or item.get("id")
                    or item.get("uuid")
                    or item.get("hwid")
                    or item.get("fingerprint")
                )
                if v:
                    ids.append(str(v))
            elif item is not None:
                ids.append(str(item))
    elif isinstance(devices_payload, dict):
        # иногда ответ может быть объектом с полем списка
        for k in ("devices", "items", "data", "response"):
            inner = devices_payload.get(k)
            if isinstance(inner, list):
                return _extract_device_ids(inner)
    # uniq keep order
    out = []
    seen = set()
    for v in ids:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


async def check_device_limit_violations(bot: Bot):
    """Проверяет превышение лимитов привязанных HWID устройств и уведомляет админов."""
    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    if not admin_ids:
        return

    now = datetime.now()
    cooldown = timedelta(hours=6)

    all_keys = rw_repo.get_all_keys() or []
    for key in all_keys:
        try:
            key_id = int(key.get("key_id") or 0)
            user_id = int(key.get("user_id") or 0)
            if not key_id or not user_id:
                continue

            expiry_dt = _parse_dt_safe(key.get("expiry_date") or key.get("expire_at"))
            if expiry_dt and expiry_dt < now:
                continue

            host_name = (key.get("host_name") or "").strip()
            email = (key.get("email") or key.get("key_email") or "").strip()
            if not host_name or not email:
                continue

            database.ensure_key_usage_monitor_row(key_id, user_id)
            mon = database.get_key_usage_monitor(key_id) or {}

            remote_user = None
            try:
                remote_user = await remnawave_api.get_user_by_email(email, host_name=host_name)
            except Exception:
                remote_user = None

            limit = _resolve_hwid_device_limit_for_key(key, remote_user)
            if not limit or limit <= 0:
                continue

            user_uuid = (key.get("remnawave_user_uuid") or key.get("xui_client_uuid") or "").strip()
            if (not user_uuid) and isinstance(remote_user, dict):
                user_uuid = str(remote_user.get("uuid") or remote_user.get("id") or remote_user.get("userUuid") or "").strip()
            if not user_uuid:
                continue

            devices_payload = None
            try:
                devices_payload = await remnawave_api.get_hwid_devices_for_user(str(user_uuid), host_name=host_name)
            except Exception:
                devices_payload = None

            devices_count = len(devices_payload) if isinstance(devices_payload, list) else 0
            # обновим статистику
            try:
                database.update_key_usage_monitor(
                    key_id,
                    last_checked_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                    last_devices_count=devices_count,
                )
            except Exception:
                pass

            if devices_count <= int(limit):
                # если ранее было превышение — сбрасываем, чтобы при следующем превышении уведомить снова
                if (mon.get("overlimit_notified_count") or 0) != 0 or mon.get("overlimit_notified_at"):
                    try:
                        database.update_key_usage_monitor(key_id, overlimit_notified_count=0, overlimit_notified_at=None)
                    except Exception:
                        pass
                continue

            last_count = _try_int(mon.get("overlimit_notified_count")) or 0
            last_dt = _parse_dt_safe(mon.get("overlimit_notified_at"))
            if devices_count <= last_count and last_dt and (now - last_dt) < cooldown:
                continue

            # username для удобства
            uname = None
            try:
                urow = rw_repo.get_user(user_id) or {}
                uname = urow.get("username")
            except Exception:
                uname = None

            dev_ids = _extract_device_ids(devices_payload)
            dev_ids_preview = ""
            if dev_ids:
                preview = dev_ids[:10]
                dev_ids_preview = "\n • " + "\n • ".join(preview)
                if len(dev_ids) > 10:
                    dev_ids_preview += f"\n... и еще {len(dev_ids) - 10}"

            text = (
                "⚠️ <b>Превышен лимит устройств (HWID)</b>\n\n"
                f"Пользователь: <b>{user_id}</b> {('(@' + str(uname) + ')') if uname else ''}\n"
                f"Ключ: <code>{email}</code>\n"
                f"Хост: <b>{host_name}</b>\n"
                f"Подключено устройств: <b>{devices_count}</b>\n"
                f"Лимит тарифа: <b>{int(limit)}</b>"
                + ("\n\n<b>Устройства (первые):</b>" + dev_ids_preview if dev_ids_preview else "")
            )

            for aid in admin_ids:
                try:
                    await bot.send_message(int(aid), text, parse_mode="HTML")
                except Exception:
                    pass

            try:
                database.update_key_usage_monitor(
                    key_id,
                    overlimit_notified_count=devices_count,
                    overlimit_notified_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Scheduler: Ошибка проверки лимитов устройств для key_id={key.get('key_id')}: {e}", exc_info=True)


async def check_traffic_boost_resets(bot: Bot):
    """Ежемесячный сброс трафика ключа до базовых значений тарифа.

    Дата сброса (`next_traffic_reset_at`) отсчитывается от дня покупки ключа
    и не зависит от использованного трафика. По достижении этой даты:
      - основной пул (если тариф лимитный): сброс used traffic на Remnawave,
        лимит возвращается к `plans.traffic_limit_bytes`, докупленный буст сгорает,
        `traffic_limit_strategy` остаётся MONTH_ROLLING;
      - LTE-пул (если задан `plans.lte_limit_bytes`): новый расчётный период —
        baseline переустанавливается, докупленный LTE-буст сгорает;
      - для безлимитного основного пула панель не трогаем — крутим только LTE
        и дату следующего сброса;
      - дата следующего сброса сдвигается на 1 календарный месяц вперёд.
    """
    try:
        all_keys = database.get_all_keys() if hasattr(database, "get_all_keys") else []
    except Exception:
        all_keys = []

    now = datetime.now()

    for key in all_keys:
        try:
            key_id = key.get("key_id")
            next_reset_raw = key.get("next_traffic_reset_at")
            if not next_reset_raw:
                continue

            next_reset_dt = _parse_dt_safe(next_reset_raw)
            if not next_reset_dt or next_reset_dt > now:
                continue

            plan = database.resolve_plan_for_key(key)
            main_limit = database.plan_main_limit_bytes(plan)
            if main_limit <= 0:
                main_limit = database._as_limit_bytes(key.get("traffic_limit_bytes"))
            has_main_limit = main_limit > 0
            has_lte_limit = database.should_account_lte_traffic(plan, key.get("host_name"))

            host_name = key.get("host_name")
            user_uuid = key.get("remnawave_user_uuid")
            email = key.get("key_email") or key.get("email")
            boost = int(key.get("traffic_boost_bytes") or 0)

            if has_main_limit:
                if not user_uuid and email:
                    try:
                        remote_user = await remnawave_api.get_user_by_email(email, host_name=host_name)
                        if isinstance(remote_user, dict):
                            user_uuid = remote_user.get("uuid") or remote_user.get("id") or remote_user.get("userUuid")
                    except Exception:
                        pass

                if not user_uuid:
                    logger.warning(
                        f"Scheduler: не удалось определить remnawave_user_uuid для key_id={key_id}, "
                        "сброс основного пула отложен до следующего прохода."
                    )
                    continue

                try:
                    await remnawave_api.reset_user_traffic(str(user_uuid))
                except Exception as e:
                    logger.error(
                        f"Scheduler: не удалось сбросить трафик на сервере для key_id={key_id}: {e}",
                        exc_info=True,
                    )

                if boost > 0 or int(key.get("traffic_limit_bytes") or 0) != int(main_limit):
                    try:
                        await remnawave_api.update_user_traffic_limit(
                            str(user_uuid), int(main_limit), host_name=host_name
                        )
                    except Exception as e:
                        logger.error(
                            f"Scheduler: не удалось вернуть базовый лимит трафика для key_id={key_id}: {e}",
                            exc_info=True,
                        )

            next_next_reset = database.compute_next_traffic_reset_str(from_dt=next_reset_dt)
            try:
                update_kwargs = {"next_traffic_reset_at": next_next_reset}
                if has_main_limit:
                    update_kwargs["traffic_boost_bytes"] = 0
                    update_kwargs["traffic_limit_bytes"] = int(main_limit)
                    update_kwargs["traffic_limit_strategy"] = "MONTH_ROLLING"
                database.update_key_fields(key_id, **update_kwargs)
            except Exception:
                pass

            # Новый расчётный период: LTE-пул этого КЛЮЧА обнуляет baseline, чтобы
            # не наследовать расход прошлого месяца. Вместе с baseline сгорает и
            # докупленный LTE-буст — симметрично основному пулу.
            if has_lte_limit:
                try:
                    database.request_key_lte_baseline_reset(int(key_id))
                except Exception as e:
                    logger.warning(
                        f"Scheduler: не удалось запросить сброс baseline LTE при ежемесячном сбросе key_id={key_id}: {e}"
                    )

            logger.info(
                f"Scheduler: трафик ключа key_id={key_id} сброшен до базовых значений тарифа "
                f"(main={'yes' if has_main_limit else 'no'}, lte={'yes' if has_lte_limit else 'no'}). "
                f"Следующий сброс: {next_next_reset}."
            )

        except Exception as e:
            logger.error(f"Scheduler: ошибка ежемесячного сброса трафика для key_id={key.get('key_id')}: {e}", exc_info=True)


async def enforce_dual_traffic_limits(bot: Bot | None = None):
    """Двухуровневый учёт трафика (основной пул + независимый LTE-пул на premium-нодах).

    - Основной пул = суммарный расход по ВСЕМ ключам пользователя vs (лимит тарифа + докупленный buster).
    - LTE-пул = расход по ключам на LTE-нодах vs (лимит тарифа + докупленный LTE-буст),
      см. `database.resolve_lte_limit_bytes()` — единая формула с той, что показывается
      пользователю в карточке ключа.

    Действия (идемпотентны — состояние хранится в vpn_keys.remote_access_state, чтобы не спамить API):
      * Основной исчерпан -> disable_user на ВСЕХ хостах пользователя ('disabled_main').
      * LTE исчерпан (и основной не исчерпан) -> для хостов с активным сквадом класса 'lte'
        точечно убираем ТОЛЬКО этот сквад из activeInternalSquads ('disabled_premium_squad'),
        Base-сквад остаётся активным. Хосты без такого сквада не участвуют ни в подсчёте
        LTE-расхода, ни в его энфорсинге (см. миграцию node_class -> squad_class='lte').
      * Иначе -> восстановление доступа (добавление LTE-сквада обратно либо enable_user для
        legacy-состояний 'disabled_premium'/'disabled_main').

    Если передан `bot`, пользователю отправляется уведомление при первом переходе в отключённое
    состояние LTE-пула и при восстановлении доступа к нему (не чаще одного раза за переход).
    """
    try:
        all_keys = database.get_all_keys() or []
    except Exception:
        all_keys = []

    by_user: dict[int, list[dict]] = {}
    for k in all_keys:
        try:
            uid = int(k.get("user_id") or 0)
        except Exception:
            continue
        if not uid:
            continue
        by_user.setdefault(uid, []).append(k)

    for user_id, keys in by_user.items():
        try:
            total_used = 0
            main_limit = 0
            # Состояние LTE-пула ведётся НА КЛЮЧ: лимит задаётся тарифом конкретного ключа,
            # а расход считается по нодам LTE-сквада его хоста. Пользовательская модель
            # сворачивала ключи с разными тарифами в одну строку.
            lte_exhausted_by_key: dict[Any, bool] = {}
            lte_incomplete_keys: set[Any] = set()

            for k in keys:
                key_id_for_usage = k.get("key_id")
                host_name = k.get("host_name")
                user_uuid = k.get("remnawave_user_uuid")
                if not host_name or not user_uuid:
                    continue

                # Агрегат пользователя остаётся источником для ОСНОВНОГО пула: там лимит
                # энфорсит сама панель через trafficLimitBytes, и разбивка по нодам не нужна.
                try:
                    used = await remnawave_api.get_user_used_traffic(
                        str(user_uuid),
                        host_name=host_name,
                        email=(k.get("key_email") or k.get("email") or None),
                    )
                except Exception as e:
                    logger.error(f"Scheduler[dual-limits]: не удалось получить трафик key_id={key_id_for_usage}: {e}", exc_info=True)
                    used = 0

                total_used += used

                plan = None
                plan_id = None
                try:
                    desc = k.get("description")
                    if isinstance(desc, str) and desc.strip().startswith("{"):
                        meta = json.loads(desc)
                        if isinstance(meta, dict) and meta.get("plan_id") is not None:
                            plan_id = int(meta.get("plan_id"))
                except Exception:
                    plan_id = None
                if plan_id:
                    try:
                        plan = database.get_plan_by_id(plan_id)
                    except Exception:
                        plan = None
                if plan and main_limit == 0:
                    base = int(plan.get("traffic_limit_bytes") or 0)
                    if base > 0:
                        main_limit = base + int(k.get("traffic_boost_bytes") or 0)
                # LTE-лимит тарифа читается независимо от основного: тариф может быть
                # безлимитным по основному пулу и иметь отдельный LTE-лимит.
                try:
                    plan_lte_limit = int((plan or {}).get("lte_limit_bytes") or 0)
                except Exception:
                    plan_lte_limit = 0

                # LTE-учёт только если у тарифа задан лимит И на хосте есть активный
                # сквад класса 'lte'. Безлимит и хост без сквада — не ходим в панель
                # за статистикой нод и не пишем key_lte_state / snapshots.
                try:
                    lte_squad = database.get_squad_by_class(host_name, "lte")
                except Exception:
                    lte_squad = None
                if not database.should_account_lte_traffic(plan, host_name, lte_squad=lte_squad):
                    if plan_lte_limit > 0 and not lte_squad and database.get_host_class(host_name) == "premium":
                        logger.warning(
                            "Scheduler[dual-limits]: хост '%s' помечен как premium, но активного сквада "
                            "класса 'lte' нет — расход по нему не учитывается в LTE-пуле.",
                            host_name,
                        )
                    continue

                period_start = database.resolve_key_period_start(k)
                try:
                    period_start_dt = datetime.fromisoformat(str(period_start).replace(" ", "T"))
                except Exception:
                    period_start_dt = datetime.now() - timedelta(days=30)

                premium_used = 0
                try:
                    nodes = await remnawave_api.get_lte_nodes_for_host(host_name)
                    node_uuids = [n["uuid"] for n in nodes]
                    if not node_uuids:
                        logger.warning(
                            "Scheduler[dual-limits]: у LTE-сквада хоста '%s' нет доступных нод — "
                            "расход по нему не начисляется.",
                            host_name,
                        )
                        continue
                    usage = await remnawave_api.get_user_node_usage_for_squad(
                        str(user_uuid),
                        host_name=host_name,
                        squad_uuid=str(lte_squad.get("squad_uuid") or ""),
                        node_uuids=node_uuids,
                        start_date=period_start_dt,
                        end_date=datetime.now(),
                    )
                    node_names = {n["uuid"]: n.get("node_name") for n in nodes}
                    for node_uuid, node_bytes in usage.per_node.items():
                        database.upsert_key_node_usage_snapshot(
                            key_id_for_usage,
                            node_uuid,
                            host_name=host_name,
                            used_bytes=node_bytes,
                            period_start=period_start,
                            node_name=node_names.get(node_uuid),
                        )
                    premium_used = sum(usage.per_node.values())
                    logger.info(
                        "Scheduler[dual-limits]: расход LTE key_id=%s посчитан по нодам "
                        "(путь API: %s, нод: %s, итого %s байт)",
                        key_id_for_usage, usage.path, len(usage.per_node), premium_used,
                    )
                except Exception as e:
                    # Ни нулевого расхода в снапшоты, ни исчерпания лимита — только пропуск.
                    lte_incomplete_keys.add(key_id_for_usage)
                    logger.warning(
                        "Scheduler[dual-limits]: не удалось получить расход по нодам LTE для "
                        "key_id=%s (host '%s'): %s — ключ пропущен на этом проходе.",
                        key_id_for_usage, host_name, e,
                    )
                    continue

                lte = database.get_key_lte_state(key_id_for_usage)
                if plan_lte_limit > 0 and int(lte.get("lte_limit_bytes") or 0) != plan_lte_limit:
                    # Пересинхронизация базового лимита из тарифа на каждом проходе, чтобы
                    # изменение plans.lte_limit_bytes долетало до выданных ключей.
                    # Докупленный буст при этом не трогаем.
                    database.update_key_lte_state(key_id_for_usage, lte_limit_bytes=plan_lte_limit)
                    lte["lte_limit_bytes"] = plan_lte_limit

                # --- Точка отсчёта (baseline) LTE-расхода ---
                # Панель хранит расход по нодам накопительно, поэтому сравнивать лимит нужно
                # не с сырым значением, а с разницей (raw - baseline). Baseline сдвигается на
                # границе расчётного периода, но НЕ при докупке — иначе покупка минимального
                # пакета заново выдавала бы полный лимит.
                baseline = int(lte.get("lte_used_baseline_bytes") or 0)
                if int(lte.get("lte_baseline_reset_requested") or 0):
                    baseline = premium_used
                    database.commit_key_lte_baseline(key_id_for_usage, baseline, expire_boost=True)
                    lte["lte_boost_bytes"] = 0
                    logger.info(
                        "Scheduler[dual-limits]: новый расчётный период LTE для key_id=%s — "
                        "baseline -> %s bytes, докупленный буст обнулён",
                        key_id_for_usage, baseline,
                    )
                elif not lte.get("lte_baseline_initialized_at") and premium_used > 0:
                    # Ключ существовал до появления точки отсчёта: принимаем накопленный
                    # панелью расход за baseline, иначе лимит исчерпался бы мгновенно.
                    baseline = premium_used
                    database.commit_key_lte_baseline(key_id_for_usage, baseline, expire_boost=False)
                    logger.info(
                        "Scheduler[dual-limits]: инициализирован baseline LTE для key_id=%s "
                        "-> %s bytes (первый проход)", key_id_for_usage, baseline,
                    )

                premium_used_effective = max(0, premium_used - baseline)
                database.update_key_lte_state(key_id_for_usage, lte_used_bytes=premium_used_effective)

                lte_limit_effective = database.resolve_lte_limit_bytes(lte, plan_lte_limit)
                lte_exhausted_by_key[key_id_for_usage] = (
                    lte_limit_effective > 0 and premium_used_effective >= lte_limit_effective
                )

            if lte_incomplete_keys:
                logger.warning(
                    "Scheduler[dual-limits]: неполные данные о расходе LTE для ключей %s — "
                    "их состояние на этом проходе не меняется.",
                    sorted(str(x) for x in lte_incomplete_keys),
                )

            main_exhausted = main_limit > 0 and total_used >= main_limit

            lte_transition_to_disabled = False
            lte_transition_to_enabled = False

            for k in keys:
                key_id = k.get("key_id")
                host_name = k.get("host_name")
                user_uuid = k.get("remnawave_user_uuid")
                if not host_name or not user_uuid:
                    continue

                try:
                    lte_squad = database.get_squad_by_class(host_name, "lte")
                except Exception:
                    lte_squad = None
                current_state = k.get("remote_access_state") or "enabled"
                was_lte_disabled = current_state in ("disabled_premium_squad", "disabled_premium")

                if main_exhausted:
                    desired_state = "disabled_main"
                elif lte_squad and lte_exhausted_by_key.get(key_id):
                    # Отключаем по LTE-лимиту только те ключи, чей расход в этот лимит и
                    # засчитывается (host_squads с классом 'lte'). Legacy-состояние
                    # 'disabled_premium' по-прежнему корректно снимается ветвью ниже.
                    desired_state = "disabled_premium_squad"
                elif lte_squad and key_id in lte_incomplete_keys:
                    # Достоверного расхода нет — не отключаем и не восстанавливаем доступ,
                    # оставляя текущее состояние до следующего успешного прохода.
                    continue
                else:
                    desired_state = "enabled"
                is_lte_disabled = desired_state in ("disabled_premium_squad", "disabled_premium")

                if desired_state == current_state:
                    if desired_state == "disabled_premium_squad" and lte_squad:
                        # Идемпотентная сверка с панелью. Раньше снятие сквада могло вернуть
                        # ложный успех (сравнивалась строка-UUID с массивом объектов), и в БД
                        # оказывалось 'disabled_premium_squad' при живом сквада в подписке —
                        # после чего эта ветка навсегда пропускала ключ. Повторный вызов
                        # ничего не делает, если сквад уже снят, и чинит расхождение, если нет.
                        try:
                            await remnawave_api.remove_squad_from_user(
                                str(user_uuid), lte_squad["squad_uuid"], host_name=host_name
                            )
                        except Exception as e:
                            logger.warning(
                                "Scheduler[dual-limits]: сверка снятия LTE-сквада для key_id=%s "
                                "не удалась: %s", key_id, e,
                            )
                    continue  # уже в нужном состоянии — не дёргаем API повторно

                try:
                    if desired_state == "disabled_premium_squad":
                        # Точечное отключение LTE-сквада — Base-сквад (безлимит) остаётся активным.
                        ok = await remnawave_api.remove_squad_from_user(
                            str(user_uuid), lte_squad["squad_uuid"], host_name=host_name
                        )
                    elif desired_state == "disabled_main" or desired_state == "disabled_premium":
                        ok = await remnawave_api.disable_user(str(user_uuid), host_name=host_name)
                    else:
                        # desired_state == "enabled": восстанавливаем доступ.
                        if current_state == "disabled_premium_squad" and lte_squad:
                            ok = await remnawave_api.add_squad_to_user(
                                str(user_uuid), lte_squad["squad_uuid"], host_name=host_name
                            )
                        else:
                            ok = await remnawave_api.enable_user(str(user_uuid), host_name=host_name)
                    if ok:
                        database.update_key_fields(key_id, remote_access_state=desired_state)
                        logger.info(f"Scheduler[dual-limits]: key_id={key_id} host={host_name} состояние -> {desired_state}")
                        if not was_lte_disabled and is_lte_disabled:
                            lte_transition_to_disabled = True
                        elif was_lte_disabled and not is_lte_disabled:
                            lte_transition_to_enabled = True
                except Exception as e:
                    logger.error(f"Scheduler[dual-limits]: ошибка применения состояния {desired_state} для key_id={key_id}: {e}", exc_info=True)

            # Уведомление пользователю при смене состояния LTE-пула.
            # (main_exhausted обрабатывается отдельными уведомлениями об истечении подписки/трафика.)
            if lte_transition_to_disabled and not main_exhausted:
                logger.info(f"Scheduler[dual-limits]: LTE-пул исчерпан для user_id={user_id} — доступ к premium-нодам отключён.")
                if bot is not None:
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                "⚠️ <b>Лимит LTE-трафика исчерпан</b>\n\n"
                                "Доступ к премиум-серверам (LTE-пул) временно отключён. "
                                "Основной безлимитный пул продолжает работать как обычно.\n\n"
                                "Докупите LTE-трафик в личном кабинете, чтобы восстановить доступ."
                            ),
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        if not telegram_reachability.handle_send_exception(user_id, e):
                            logger.warning(f"Scheduler[dual-limits]: не удалось отправить уведомление об исчерпании LTE user_id={user_id}: {e}")
            elif lte_transition_to_enabled:
                # Baseline здесь НЕ сдвигаем: возврат доступа происходит именно потому, что
                # расход стал меньше лимита (обычно после докупки), и сброс счётчика выдал бы
                # пользователю полный лимит заново поверх только что купленного пакета.
                logger.info(f"Scheduler[dual-limits]: LTE-пул восстановлен для user_id={user_id} — доступ к premium-нодам включён.")
                if bot is not None:
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                "✅ <b>Доступ к LTE-пулу восстановлен</b>\n\n"
                                "Премиум-серверы снова доступны."
                            ),
                            parse_mode="HTML",
                        )
                    except Exception as e:
                        if not telegram_reachability.handle_send_exception(user_id, e):
                            logger.warning(f"Scheduler[dual-limits]: не удалось отправить уведомление о восстановлении LTE user_id={user_id}: {e}")
        except Exception as e:
            logger.error(f"Scheduler[dual-limits]: ошибка обработки пользователя {user_id}: {e}", exc_info=True)


async def _legacy_check_traffic_boost_resets(bot: Bot):
    """Откатывает докупленный буст трафика после ежемесячного сброса лимита на сервере (устаревшая эвристика,
    сохранена для истории; активно используется check_traffic_boost_resets на основе next_traffic_reset_at).
    """
    try:
        all_keys = database.get_all_keys() if hasattr(database, "get_all_keys") else []
    except Exception:
        all_keys = []

    for key in all_keys:
        try:
            key_id = key.get("key_id")
            boost = int(key.get("traffic_boost_bytes") or 0)
            if boost <= 0:
                continue

            host_name = key.get("host_name")
            user_uuid = key.get("remnawave_user_uuid")
            email = key.get("key_email") or key.get("email")

            remote_user = None
            try:
                if user_uuid:
                    remote_user = await remnawave_api.get_user_by_uuid(user_uuid, host_name=host_name)
                if not remote_user and email:
                    remote_user = await remnawave_api.get_user_by_email(email, host_name=host_name)
            except Exception:
                remote_user = None

            if not remote_user:
                continue

            used_bytes = _extract_used_bytes(remote_user)

            mon = database.get_key_usage_monitor(key_id) or {}
            last_used = int(mon.get("last_traffic_bytes") or 0)

            reset_detected = last_used > 0 and used_bytes < (last_used * 0.5)

            database.update_key_usage_monitor(
                key_id,
                last_checked_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_traffic_bytes=used_bytes,
            )

            if not reset_detected:
                continue

            plan_id = None
            try:
                desc = key.get("description")
                if isinstance(desc, str) and desc.strip().startswith("{"):
                    meta = json.loads(desc)
                    if isinstance(meta, dict) and meta.get("plan_id") is not None:
                        plan_id = int(meta.get("plan_id"))
            except Exception:
                plan_id = None

            base_limit = None
            if plan_id:
                try:
                    plan = database.get_plan_by_id(plan_id)
                    if plan:
                        base_limit = plan.get("traffic_limit_bytes")
                except Exception:
                    base_limit = None

            if base_limit is None:
                continue

            try:
                if user_uuid:
                    await remnawave_api.update_user_traffic_limit(user_uuid, int(base_limit), host_name=host_name)
            except Exception as e:
                logger.error(f"Scheduler: не удалось откатить лимит трафика для key_id={key_id}: {e}", exc_info=True)
                continue

            try:
                database.update_key_fields(key_id, traffic_limit_bytes=int(base_limit), traffic_boost_bytes=0)
            except Exception:
                pass

            logger.info(f"Scheduler: буст трафика сброшен для key_id={key_id} после ежемесячного сброса лимита.")

        except Exception as e:
            logger.error(f"Scheduler: ошибка проверки сброса буста трафика для key_id={key.get('key_id')}: {e}", exc_info=True)


async def check_inactive_usage_reminders(bot: Bot):
    """Если после выдачи ключа у пользователя не было подключенных устройств/трафика — напоминать с заданным интервалом."""
    if not _get_inactive_usage_reminder_enabled():
        return

    interval_seconds = _get_inactive_usage_reminder_interval_seconds()
    first_delay_seconds = interval_seconds

    now = datetime.now()
    all_keys = rw_repo.get_all_keys() or []
    for key in all_keys:
        try:
            user_id = int(key.get("user_id") or 0)
            key_id = int(key.get("key_id") or 0)
            if not user_id or not key_id:
                continue

            expiry_dt = _parse_dt_safe(key.get("expiry_date") or key.get("expire_at"))
            if expiry_dt and expiry_dt < now:
                continue  # истёк

            created_dt = _parse_dt_safe(key.get("created_at") or key.get("created_date"))
            if created_dt and (now - created_dt).total_seconds() < first_delay_seconds:
                continue

            database.ensure_key_usage_monitor_row(key_id, user_id)
            mon = database.get_key_usage_monitor(key_id) or {}
            if mon.get("first_seen_usage_at"):
                continue

            last_reminder_dt = _parse_dt_safe(mon.get("last_reminder_at"))
            if last_reminder_dt and (now - last_reminder_dt).total_seconds() < interval_seconds:
                continue

            # Проверяем Remnawave: устройства / трафик
            host_name = key.get("host_name")
            email = key.get("email") or key.get("key_email")
            user_uuid = key.get("remnawave_user_uuid") or key.get("xui_client_uuid")

            remote_user = None
            if email and host_name:
                try:
                    remote_user = await remnawave_api.get_user_by_email(email, host_name=host_name)
                except Exception:
                    remote_user = None

            if remote_user and not user_uuid:
                user_uuid = remote_user.get("uuid") or remote_user.get("id") or remote_user.get("userUuid") or remote_user.get("user_uuid")

            devices_count = 0
            if user_uuid and host_name:
                try:
                    devices = await remnawave_api.get_hwid_devices_for_user(str(user_uuid), host_name=host_name)
                    if isinstance(devices, list):
                        devices_count = len(devices)
                except Exception:
                    devices_count = 0

            used_bytes = _extract_used_bytes(remote_user)

            # Обновим мониторинг
            database.update_key_usage_monitor(
                key_id,
                last_checked_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                last_devices_count=devices_count,
                last_traffic_bytes=used_bytes,
            )

            if devices_count > 0 or used_bytes > 0:
                database.update_key_usage_monitor(
                    key_id,
                    first_seen_usage_at=now.strftime("%Y-%m-%d %H:%M:%S"),
                )
                continue

            # Отправляем напоминание
            text = (
                "⚠️ Ваша VPN-подписка активна, но трафик не используется.\n\n"
                "<blockquote>Если у вас возникли сложности с подключением, нажмите кнопку ниже, чтобы связаться с поддержкой.</blockquote>\n\n"
                "🛠 Мы поможем вам разобраться! 💡"
            )
            connection_string = key.get("subscription_url") or key.get("connection_string")
            kb = keyboards.create_inactive_usage_reminder_keyboard(connection_string)
            await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)

            database.update_key_usage_monitor(
                key_id,
                last_reminder_at=now.strftime("%Y-%m-%d %H:%M:%S"),
            )
        except Exception as e:
            logger.error(f"Scheduler: Ошибка напоминания о неиспользовании трафика для key_id={key.get('key_id')}: {e}", exc_info=True)


async def sync_keys_with_panels():
    logger.debug("Scheduler: Запускаю синхронизацию с Remnawave API...")
    total_affected_records = 0

    squads = rw_repo.list_squads()
    if not squads:
        logger.debug("Scheduler: Сквады Remnawave не настроены. Синхронизация пропущена.")
        return

    for squad in squads:
        host_name = (squad.get('host_name') or squad.get('name') or '').strip() or 'unknown'
        squad_uuid = (squad.get('squad_uuid') or squad.get('squadUuid') or '').strip()
        if not squad_uuid:
            logger.warning("Scheduler: Сквад '%s' не имеет squad_uuid — пропускаю синхронизацию.", host_name)
            continue

        try:
            remote_users = await remnawave_api.list_users(host_name=host_name, squad_uuid=squad_uuid, size=1000)
        except Exception as exc:
            logger.error("Scheduler: Не удалось получить пользователей Remnawave для '%s': %s", host_name, exc)
            continue

        remote_by_email: dict[str, tuple[str, dict]] = {}
        for remote_user in remote_users or []:
            raw_email = (remote_user.get('email') or remote_user.get('accountEmail') or '').strip()
            if not raw_email:
                continue
            remote_by_email[raw_email.lower()] = (raw_email, remote_user)

        keys_in_db = rw_repo.get_keys_for_host(host_name) or []
        now = datetime.now()

        for db_key in keys_in_db:
            raw_email = (db_key.get('key_email') or db_key.get('email') or '').strip()
            normalized_email = raw_email.lower()
            if not raw_email:
                continue

            remote_entry = remote_by_email.pop(normalized_email, None)
            remote_email = None
            remote_user = None
            if remote_entry:
                remote_email, remote_user = remote_entry

            expiry_raw = db_key.get('expiry_date') or db_key.get('expire_at')
            try:
                expiry_date = datetime.fromisoformat(str(expiry_raw)) if expiry_raw else None
            except Exception:
                try:
                    expiry_date = datetime.fromisoformat(str(expiry_raw).replace('Z', '+00:00'))
                except Exception:
                    expiry_date = None

            if expiry_date and expiry_date < now - timedelta(days=5):
                logger.debug(
                    "Scheduler: Ключ '%s' (host '%s') просрочен более 5 дней. Удаляю пользователя из Remnawave и БД.",
                    raw_email,
                    host_name,
                )
                try:
                    await remnawave_api.delete_client_on_host(host_name, remote_email or raw_email)
                except Exception as exc:
                    logger.error(
                        "Scheduler: Не удалось удалить пользователя '%s' из Remnawave: %s",
                        raw_email,
                        exc,
                    )
                if rw_repo.delete_key_by_email(raw_email):
                    total_affected_records += 1
                continue

            if remote_user:
                expire_value = remote_user.get('expireAt') or remote_user.get('expiryDate')
                remote_dt = None
                if expire_value:
                    try:
                        remote_dt = datetime.fromisoformat(str(expire_value).replace('Z', '+00:00'))
                    except Exception:
                        remote_dt = None
                local_ms = int(expiry_date.timestamp() * 1000) if expiry_date else None
                remote_ms = int(remote_dt.timestamp() * 1000) if remote_dt else None
                subscription_url = remnawave_api.extract_subscription_url(remote_user)
                local_subscription = db_key.get('subscription_url') or db_key.get('connection_string')

                needs_update = False
                if remote_ms is not None and local_ms is not None and abs(remote_ms - local_ms) > 1000:
                    needs_update = True
                if subscription_url and subscription_url != local_subscription:
                    needs_update = True

                if needs_update:
                    if rw_repo.update_key_status_from_server(raw_email, remote_user):
                        total_affected_records += 1
                        logger.debug(
                            "Scheduler: Обновлён ключ '%s' на основе данных Remnawave (host '%s').",
                            raw_email,
                            host_name,
                        )
            else:
                logger.warning(
                    "Scheduler: Ключ '%s' (host '%s') отсутствует в Remnawave. Помечаю как отсутствующий (не удаляю) в локальной БД.",
                    raw_email,
                    host_name,
                )
                if rw_repo.update_key_status_from_server(raw_email, None):
                    total_affected_records += 1

        if remote_by_email:
            for normalized_email, (remote_email, remote_user) in remote_by_email.items():
                import re

                match = re.search(r"user(\d+)", remote_email)
                user_id = int(match.group(1)) if match else None
                if not user_id:
                    logger.warning(
                        "Scheduler: Осиротевший пользователь '%s' в Remnawave не содержит user_id — пропускаю.",
                        remote_email,
                    )
                    continue

                if not rw_repo.get_user(user_id):
                    logger.warning(
                        "Scheduler: Осиротевший пользователь '%s' ссылается на несуществующего user_id=%s.",
                        remote_email,
                        user_id,
                    )
                    continue

                if rw_repo.get_key_by_email(remote_email):
                    continue

                payload = dict(remote_user)
                payload.setdefault('host_name', host_name)
                payload.setdefault('squad_uuid', squad_uuid)
                payload.setdefault('squadUuid', squad_uuid)

                new_id = rw_repo.record_key_from_payload(
                    user_id=user_id,
                    payload=payload,
                    host_name=host_name,
                    description=payload.get('description'),
                    tag=payload.get('tag'),
                )
                if new_id:
                    total_affected_records += 1
                    logger.info(
                        "Scheduler: Привязал осиротевшего пользователя '%s' (host '%s') к user_id=%s как key_id=%s.",
                        remote_email,
                        host_name,
                        user_id,
                        new_id,
                    )
                else:
                    logger.warning(
                        "Scheduler: Не удалось привязать осиротевшего пользователя '%s' (host '%s').",
                        remote_email,
                        host_name,
                    )

    logger.debug(
        "Scheduler: Синхронизация с Remnawave API завершена. Затронуто записей: %s.",
        total_affected_records,
    )


async def _maybe_sync_keys_with_panels():
    """sync_keys_with_panels is expensive (list all users on each host).

    If it runs too often, it can delay bot responses. Throttle it.
    """
    global _last_sync_keys_with_panels_at
    now = datetime.now()
    if _last_sync_keys_with_panels_at and (now - _last_sync_keys_with_panels_at).total_seconds() < SYNC_KEYS_WITH_PANELS_INTERVAL_SECONDS:
        return
    try:
        await sync_keys_with_panels()
        _last_sync_keys_with_panels_at = now
    except Exception as e:
        logger.error(f"Scheduler: Ошибка синхронизации с панелями: {e}", exc_info=True)


async def _maybe_enforce_dual_traffic_limits(bot: Bot | None = None):
    """Учёт двух пулов трафика (основной + LTE) — интервал настраивается через bot_settings.dual_limit_interval_sec."""
    global _last_dual_traffic_limits_at
    now = datetime.now()
    try:
        interval = int(rw_repo.get_setting("dual_limit_interval_sec") or DUAL_LIMIT_DEFAULT_INTERVAL_SECONDS)
    except Exception:
        interval = DUAL_LIMIT_DEFAULT_INTERVAL_SECONDS
    if interval <= 0:
        interval = DUAL_LIMIT_DEFAULT_INTERVAL_SECONDS
    if _last_dual_traffic_limits_at and (now - _last_dual_traffic_limits_at).total_seconds() < interval:
        return
    try:
        await enforce_dual_traffic_limits(bot)
        _last_dual_traffic_limits_at = now
    except Exception as e:
        logger.error(f"Scheduler: Ошибка учёта двух пулов трафика: {e}", exc_info=True)


async def _notify_auto_renew_success(
    bot: Bot, user_id: int, key_id: int, price: float, days_added: int, key_name: str | None = None
):
    try:
        label = f"«{key_name}»" if key_name else f"#{key_id}"
        builder = InlineKeyboardBuilder()
        builder.button(text="🔑 Мои ключи", callback_data="manage_keys")
        builder.button(text="👤 Профиль", callback_data="show_profile")
        builder.adjust(2)
        await bot.send_message(
            user_id,
            f"✅ <b>Автопродление выполнено</b>\n\n"
            f"Ключ {label} продлён на <b>{days_added} дн.</b>\n"
            f"Списано: <b>{price:.0f} ₽</b> с баланса.",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error(f"Auto-renew: не удалось уведомить {user_id} об успехе: {e}")


async def _notify_auto_renew_no_balance(
    bot: Bot, user_id: int, key_id: int, price: float, key_name: str | None = None
):
    try:
        label = f"«{key_name}»" if key_name else f"#{key_id}"
        builder = InlineKeyboardBuilder()
        builder.button(text="💳 Пополнить баланс", callback_data="top_up_start")
        builder.button(text="🔑 Мои ключи", callback_data="manage_keys")
        builder.adjust(1)
        await bot.send_message(
            user_id,
            f"⚠️ <b>Автопродление не выполнено</b>\n\n"
            f"Для продления ключа {label} нужно <b>{price:.0f} ₽</b>,\n"
            f"но на балансе недостаточно средств.\n\n"
            f"Пополните баланс или отключите автопродление для этого ключа.",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.error(f"Auto-renew: не удалось уведомить {user_id} о нехватке баланса: {e}")


async def check_auto_renewals(bot: Bot):
    global _auto_renew_attempts
    if not _is_true(rw_repo.get_setting("auto_renew_globally_enabled") or "false"):
        return

    try:
        hours_before = int(rw_repo.get_setting("auto_renew_hours_before") or 24)
    except Exception:
        hours_before = 24

    logger.debug("Scheduler: Проверяю ключи для автопродления...")
    keys = rw_repo.get_keys_for_auto_renew(hours_before=hours_before)
    if not keys:
        return

    logger.info(f"Scheduler: Найдено {len(keys)} ключей для автопродления.")
    now = datetime.now()

    for key in keys:
        try:
            key_id = int(key["key_id"])
            user_id = int(key["user_id"])
            key_name = key.get("user_key_name") or None

            last_attempt = _auto_renew_attempts.get(key_id)
            if last_attempt and (now - last_attempt).total_seconds() < AUTO_RENEW_RETRY_COOLDOWN_HOURS * 3600:
                continue
            _auto_renew_attempts[key_id] = now

            meta = _parse_origin_meta_from_description(key.get("description"))
            plan = None
            if isinstance(meta, dict):
                pid = _try_int(meta.get("plan_id"))
                if pid:
                    try:
                        plan = rw_repo.get_plan_by_id(pid)
                    except Exception:
                        pass

            if not plan:
                logger.debug(f"Auto-renew: ключ {key_id} пропущен — тариф не определён.")
                continue

            price = float(plan.get("price") or 0)
            if price <= 0:
                logger.debug(f"Auto-renew: ключ {key_id} пропущен — цена тарифа = 0.")
                continue

            plan_months = int(plan.get("months") or 0)
            plan_days = int(plan.get("duration_days") or 0)
            days_to_add = plan_days if plan_days > 0 else (plan_months * 30 if plan_months > 0 else 30)

            if not rw_repo.deduct_from_balance(user_id, price):
                logger.info(f"Auto-renew: пользователь {user_id}, ключ {key_id} — нехватка баланса ({price:.2f}).")
                await _notify_auto_renew_no_balance(bot, user_id, key_id, price, key_name)
                continue

            host_name = key.get("host_name")
            email = key.get("key_email") or key.get("email")
            try:
                expire_str = key.get("expire_at") or key.get("expiry_date")
                exp_dt = _parse_dt_safe(expire_str) or now
                base_ms = max(int(exp_dt.timestamp() * 1000), int(now.timestamp() * 1000))
                new_expiry_ms = base_ms + days_to_add * 86400000

                result = await remnawave_api.create_or_update_key_on_host(
                    host_name=host_name,
                    email=email,
                    days_to_add=days_to_add,
                    expiry_timestamp_ms=new_expiry_ms,
                    traffic_limit_bytes=int(plan.get("traffic_limit_bytes") or 0),
                    traffic_limit_strategy=database.remnawave_traffic_limit_strategy_for_plan(plan),
                    plan_id=plan.get("plan_id"),
                )
                if result:
                    effective_ms = result.get("expiry_timestamp_ms") or new_expiry_ms
                    rw_repo.update_key_fields(key_id, expire_at_ms=int(effective_ms))
                    try:
                        database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=False)
                    except Exception:
                        logger.warning(
                            f"Auto-renew: не удалось обновить политику сброса трафика ключа {key_id}",
                            exc_info=True,
                        )
                    _auto_renew_attempts.pop(key_id, None)
                    logger.info(f"Auto-renew: ключ {key_id} продлён на {days_to_add} дн. (пользователь {user_id}).")
                    await _notify_auto_renew_success(bot, user_id, key_id, price, days_to_add, key_name)
                else:
                    rw_repo.add_to_balance(user_id, price)
                    logger.error(f"Auto-renew: Remnawave API вернул None для ключа {key_id}. Средства возвращены.")
            except Exception as exc:
                rw_repo.add_to_balance(user_id, price)
                logger.error(f"Auto-renew: ошибка продления ключа {key_id}: {exc}", exc_info=True)
        except Exception as exc:
            logger.error(f"Auto-renew: ошибка обработки ключа {key.get('key_id')}: {exc}", exc_info=True)


async def check_broadcast_campaigns(bot: Bot):
    """Send queued broadcast campaigns to inactive subscribers."""
    campaigns = rw_repo.get_broadcast_campaigns()
    now = datetime.now()
    for c in campaigns:
        if not c.get("is_active"):
            continue
        interval_hours = int(c.get("interval_hours") or 72)
        last_run_raw = c.get("last_run_at")
        if last_run_raw:
            last_run = _parse_dt_safe(str(last_run_raw))
            if last_run and (now - last_run).total_seconds() < interval_hours * 3600:
                continue
        campaign_id = int(c["id"])
        recipients = rw_repo.get_pending_broadcast_recipients(campaign_id, interval_hours)
        rw_repo.mark_broadcast_run(campaign_id)
        if not recipients:
            logger.debug(f"Broadcast {campaign_id}: нет получателей.")
            continue
        text = c.get("text_html") or ""
        sent_ids: list[int] = []
        failed = 0
        unreachable = 0
        for uid in recipients:
            try:
                await bot.send_message(int(uid), text, parse_mode="HTML")
                sent_ids.append(uid)
            except Exception as e:
                failed += 1
                if telegram_reachability.handle_send_exception(int(uid), e):
                    unreachable += 1
                else:
                    logger.warning(f"Broadcast {campaign_id}: не удалось отправить пользователю {uid}: {e}")
            await asyncio.sleep(0.05)  # stay within Telegram rate limits
        if sent_ids:
            rw_repo.record_broadcast_sends(campaign_id, sent_ids)
        logger.info(
            f"Broadcast {campaign_id} «{c.get('name')}»: отправлено {len(sent_ids)}, не доставлено {failed} "
            f"(из них недоступны боту {unreachable})."
        )


async def periodic_subscription_check(bot_controller: BotController):
    logger.info("Scheduler: Планировщик фоновых задач запущен.")
    await asyncio.sleep(10)

    while True:
        try:
            await _maybe_sync_keys_with_panels()
            _early_bot = bot_controller.get_bot_instance() if bot_controller.get_status().get("is_running") else None
            await _maybe_enforce_dual_traffic_limits(_early_bot)


            await _maybe_run_periodic_speedtests()


            bot = bot_controller.get_bot_instance() if bot_controller.get_status().get("is_running") else None
            if bot:
                await _maybe_run_daily_backup(bot)


            bot = bot_controller.get_bot_instance() if bot_controller.get_status().get("is_running") else None
            await _maybe_collect_resource_metrics(bot)

            if bot_controller.get_status().get("is_running"):
                bot = bot_controller.get_bot_instance()
                if bot:
                    await check_expiring_subscriptions(bot)
                    await check_auto_renewals(bot)
                    await check_broadcast_campaigns(bot)
                    await check_inactive_usage_reminders(bot)
                    await check_device_limit_violations(bot)
                    await check_traffic_boost_resets(bot)
                else:
                    logger.warning("Scheduler: Бот помечен как запущенный, но экземпляр недоступен.")
            else:
                logger.debug("Scheduler: Бот остановлен, уведомления пользователям пропущены.")

        except Exception as e:
            logger.error(f"Scheduler: Необработанная ошибка в основном цикле: {e}", exc_info=True)
            
        logger.info(f"Scheduler: Цикл завершён. Следующая проверка через {CHECK_INTERVAL_SECONDS} сек.")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def _maybe_sync_keys_with_panels():
    """Sync with Remnawave panels is expensive; throttle to reduce bot latency."""
    global _last_sync_with_panels_at
    now = datetime.now()
    if _last_sync_with_panels_at and (now - _last_sync_with_panels_at).total_seconds() < SYNC_KEYS_WITH_PANELS_INTERVAL_SECONDS:
        return
    try:
        await sync_keys_with_panels()
        _last_sync_with_panels_at = now
    except Exception as e:
        logger.error(f"Scheduler: Ошибка sync_keys_with_panels: {e}", exc_info=True)

async def _maybe_run_periodic_speedtests():
    global _last_speedtests_run_at
    now = datetime.now()
    if _last_speedtests_run_at and (now - _last_speedtests_run_at).total_seconds() < SPEEDTEST_INTERVAL_SECONDS:
        return
    try:
        await _run_speedtests_for_all_ssh_targets()
        _last_speedtests_run_at = now
    except Exception as e:
        logger.error(f"Scheduler: Ошибка запуска speedtests: {e}", exc_info=True)

async def _run_speedtests_for_all_hosts():
    hosts = rw_repo.get_all_hosts()
    if not hosts:
        logger.debug("Scheduler: Нет хостов для измерений скорости.")
        return
    logger.info(f"Scheduler: Запускаю speedtest для {len(hosts)} хост(ов)...")
    for h in hosts:
        host_name = h.get('host_name')
        if not host_name:
            continue
        try:
            logger.info(f"Scheduler: Speedtest для '{host_name}' запущен...")

            try:
                async with asyncio.timeout(180):
                    res = await speedtest_runner.run_both_for_host(host_name)
            except AttributeError:

                res = await asyncio.wait_for(speedtest_runner.run_both_for_host(host_name), timeout=180)
            ok = res.get('ok')
            err = res.get('error')
            if ok:
                logger.info(f"Scheduler: Speedtest для '{host_name}' завершён успешно")
            else:
                logger.warning(f"Scheduler: Speedtest для '{host_name}' завершён с ошибками: {err}")
        except asyncio.TimeoutError:
            logger.warning(f"Scheduler: Таймаут speedtest для хоста '{host_name}'")
        except Exception as e:
            logger.error(f"Scheduler: Ошибка выполнения speedtest для '{host_name}': {e}", exc_info=True)

async def _run_speedtests_for_all_ssh_targets():
    targets = rw_repo.get_all_ssh_targets() or []
    if not targets:
        logger.debug("Scheduler: Нет SSH-целей для измерений скорости.")
        return
    logger.info(f"Scheduler: Запускаю SSH speedtest для {len(targets)} цел(ей)...")
    for t in targets:
        target_name = (t.get('target_name') or '').strip()
        if not target_name:
            continue
        try:
            logger.info(f"Scheduler: SSH speedtest для цели '{target_name}' запущен...")
            try:
                async with asyncio.timeout(180):
                    res = await speedtest_runner.run_and_store_ssh_speedtest_for_target(target_name)
            except AttributeError:
                res = await asyncio.wait_for(speedtest_runner.run_and_store_ssh_speedtest_for_target(target_name), timeout=180)
            ok = res.get('ok')
            err = res.get('error')
            if ok:
                logger.info(f"Scheduler: SSH speedtest для цели '{target_name}' завершён успешно")
            else:
                logger.warning(f"Scheduler: SSH speedtest для цели '{target_name}' завершён с ошибками: {err}")
        except asyncio.TimeoutError:
            logger.warning(f"Scheduler: Таймаут SSH speedtest для цели '{target_name}'")
        except Exception as e:
            logger.error(f"Scheduler: Ошибка выполнения SSH speedtest для цели '{target_name}': {e}", exc_info=True)



async def _maybe_collect_resource_metrics(bot: Bot | None):
    """Периодический сбор метрик (локально + SSH на хостах) и отправка алертов при превышении порогов.
    Читает настройки:
      - monitoring_enabled (true/false)
      - monitoring_interval_sec (по умолчанию 300)
      - monitoring_cpu_threshold, monitoring_mem_threshold, monitoring_disk_threshold (проценты)
      - monitoring_alert_cooldown_sec (по умолчанию 3600)
    """
    global _last_resource_collect_at, _last_resource_alert_at
    try:
        enabled = (rw_repo.get_setting("monitoring_enabled") or "true").strip().lower() == "true"
        if not enabled:
            return
        try:
            interval_sec = int((rw_repo.get_setting("monitoring_interval_sec") or "300").strip() or 300)
        except Exception:
            interval_sec = 300
        now = datetime.now()
        if _last_resource_collect_at and (now - _last_resource_collect_at).total_seconds() < max(30, interval_sec):
            return


        def _to_int(s: str | None, default: int) -> int:
            try:
                return int((s or "").strip() or default)
            except Exception:
                return default
        cpu_thr = _to_int(rw_repo.get_setting("monitoring_cpu_threshold"), 90)
        mem_thr = _to_int(rw_repo.get_setting("monitoring_mem_threshold"), 90)
        disk_thr = _to_int(rw_repo.get_setting("monitoring_disk_threshold"), 90)
        cooldown = _to_int(rw_repo.get_setting("monitoring_alert_cooldown_sec"), 3600)


        try:
            local = resource_monitor.get_local_metrics()
            cpu_p = (local.get('cpu') or {}).get('percent')
            mem_p = (local.get('memory') or {}).get('percent')
            disks = local.get('disks') or []
            disk_p = max((d.get('percent') or 0) for d in disks) if disks else None
            rw_repo.insert_resource_metric(
                'local', 'panel',
                cpu_percent=cpu_p, mem_percent=mem_p, disk_percent=disk_p,
                load1=(local.get('cpu') or {}).get('loadavg',[None])[0] if (local.get('cpu') or {}).get('loadavg') else None,
                net_bytes_sent=(local.get('net') or {}).get('bytes_sent'),
                net_bytes_recv=(local.get('net') or {}).get('bytes_recv'),
                raw_json=json.dumps(local, ensure_ascii=False)
            )
            await _maybe_alert(bot, scope='local', name='panel', cpu=cpu_p, mem=mem_p, disk=disk_p,
                               cpu_thr=cpu_thr, mem_thr=mem_thr, disk_thr=disk_thr, cooldown_sec=cooldown)
        except Exception:
            logger.debug("Scheduler: не удалось собрать локальные метрики", exc_info=True)


        hosts = rw_repo.get_all_hosts() or []
        for h in hosts:
            name = h.get('host_name') or ''
            if not name:
                continue

            if not (h.get('ssh_host') and h.get('ssh_user')):
                continue
            try:
                rm = resource_monitor.get_remote_metrics_for_host(name)
                mem_p = (rm.get('memory') or {}).get('percent')
                disks = rm.get('disks') or []
                disk_p = max((d.get('percent') or 0) for d in disks) if disks else None
                rw_repo.insert_resource_metric(
                    'host', name,
                    mem_percent=mem_p,
                    disk_percent=disk_p,
                    load1=(rm.get('loadavg') or [None])[0],
                    raw_json=json.dumps(rm, ensure_ascii=False)
                )
                await _maybe_alert(bot, scope='host', name=name, cpu=None, mem=mem_p, disk=disk_p,
                                   cpu_thr=cpu_thr, mem_thr=mem_thr, disk_thr=disk_thr, cooldown_sec=cooldown)
            except Exception:
                logger.debug("Scheduler: не удалось собрать метрики хоста для %s", name, exc_info=True)

        _last_resource_collect_at = now
    except Exception:
        logger.error("Scheduler: Ошибка сбора метрик ресурсов", exc_info=True)


async def _maybe_run_daily_backup(bot: Bot):
    """Ежедневный автобэкап базы и отправка админам. Интервал задаётся в настройках backup_interval_days."""
    global _last_backup_run_at
    now = datetime.now()
    try:
        s = rw_repo.get_setting("backup_interval_days") or "1"
        days = int(str(s).strip() or "1")
    except Exception:
        days = 1
    if days <= 0:
        return
    interval_seconds = max(1, days) * 24 * 3600
    if _last_backup_run_at and (now - _last_backup_run_at).total_seconds() < interval_seconds:
        return
    try:
        zip_path = backup_manager.create_backup_file()
        if zip_path and zip_path.exists():
            try:
                sent = await backup_manager.send_backup_to_admins(bot, zip_path)
                logger.info(f"Scheduler: Создан бэкап {zip_path.name}, отправлен {sent} адм.")
            except Exception as e:
                logger.error(f"Scheduler: Не удалось отправить бэкап: {e}")
            try:
                backup_manager.cleanup_old_backups(keep=7)
            except Exception:
                pass
        _last_backup_run_at = now
    except Exception as e:
        logger.error(f"Scheduler: Критическая ошибка при создании и отправке бэкапа: {e}", exc_info=True)


async def _maybe_alert(
    bot: Bot | None,
    *,
    scope: str,
    name: str,
    cpu: float | None,
    mem: float | None,
    disk: float | None,
    cpu_thr: int,
    mem_thr: int,
    disk_thr: int,
    cooldown_sec: int,
):
    if not bot:
        return
    

    cpu_warning = max(50, cpu_thr - 20)
    mem_warning = max(50, mem_thr - 20)
    disk_warning = max(50, disk_thr - 20)
    
    breaches: list[dict] = []
    alerts: list[dict] = []
    

    if cpu is not None:
        if cpu >= cpu_thr:
            breaches.append({
                'type': 'Процессор',
                'value': cpu,
                'threshold': cpu_thr,
                'level': 'critical',
                'emoji': '🔴'
            })
        elif cpu >= cpu_warning:
            alerts.append({
                'type': 'Процессор',
                'value': cpu,
                'threshold': cpu_warning,
                'level': 'warning',
                'emoji': '🟡'
            })
    

    if mem is not None:
        if mem >= mem_thr:
            breaches.append({
                'type': 'Память',
                'value': mem,
                'threshold': mem_thr,
                'level': 'critical',
                'emoji': '🔴'
            })
        elif mem >= mem_warning:
            alerts.append({
                'type': 'Память',
                'value': mem,
                'threshold': mem_warning,
                'level': 'warning',
                'emoji': '🟡'
            })
    

    if disk is not None:
        if disk >= disk_thr:
            breaches.append({
                'type': 'Диск',
                'value': disk,
                'threshold': disk_thr,
                'level': 'critical',
                'emoji': '🔴'
            })
        elif disk >= disk_warning:
            alerts.append({
                'type': 'Диск',
                'value': disk,
                'threshold': disk_warning,
                'level': 'warning',
                'emoji': '🟡'
            })
    

    if breaches:
        key = (scope, name, "critical", ",".join(sorted([b['type'] for b in breaches])))
        now = datetime.now()
        last = _last_resource_alert_at.get(key)
        if not last or (now - last).total_seconds() >= max(60, cooldown_sec):
            _last_resource_alert_at[key] = now
            await _send_alert(bot, scope, name, breaches, 'critical')
    

    if alerts:
        key = (scope, name, "warning", ",".join(sorted([a['type'] for a in alerts])))
        now = datetime.now()
        last = _last_resource_alert_at.get(key)
        if not last or (now - last).total_seconds() >= max(300, cooldown_sec * 2):
            _last_resource_alert_at[key] = now
            await _send_alert(bot, scope, name, alerts, 'warning')


async def _send_alert(bot: Bot, scope: str, name: str, issues: list[dict], level: str):
    """Отправка алерта админам"""
    try:
        admin_ids = rw_repo.get_admin_ids() or set()
    except Exception:
        admin_ids = set()
    if not admin_ids:
        return
    

    if level == 'critical':
        header_emoji = "🚨"
        header_text = "КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ"
    else:
        header_emoji = "⚠️"
        header_text = "ПРЕДУПРЕЖДЕНИЕ"
    

    if scope == 'local':
        obj_name = f"🖥️ Панель ({name})"
    elif scope == 'host':
        obj_name = f"🖥️ Хост {name}"
    elif scope == 'target':
        obj_name = f"🔌 SSH-цель {name}"
    else:
        obj_name = f"❓ {scope}:{name}"
    

    text_lines = [
        f"{header_emoji} <b>{header_text}</b>",
        "",
        f"🎯 <b>Объект:</b> {obj_name}",
        f"⏰ <b>Время:</b> <code>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</code>",
        "",
        "📊 <b>Проблемы:</b>"
    ]
    
    for issue in issues:
        emoji = issue['emoji']
        type_name = issue['type']
        value = issue['value']
        threshold = issue['threshold']
        text_lines.append(f"  {emoji} <b>{type_name}:</b> {value:.1f}% (порог: {threshold}%)")
    

    text_lines.extend([
        "",
        "💡 <b>Рекомендации:</b>",
        "• Проверьте нагрузку на систему",
        "• Освободите место на диске",
        "• Перезапустите сервисы при необходимости"
    ])
    
    text = "\n".join(text_lines)
    

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, parse_mode='HTML')
        except Exception:
            continue



