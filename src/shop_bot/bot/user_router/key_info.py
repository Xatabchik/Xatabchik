"""Сведения о ключе из панели: устройства, трафик, тариф и синхронизация.

Модуль состоит только из хелперов и ничего не регистрирует в роутере.
"""

import re
import json
import asyncio
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user_keys,
    get_plan_by_id,
    get_plans_for_host,
    get_active_plans_for_host,
)
from shop_bot.data_manager import database
from shop_bot.modules import remnawave_api
from shop_bot.data_manager.database import delete_key_by_id

__all__ = [
    "_remnawave_key_exists",
    "_extract_connected_devices",
    "_get_connected_devices_count",
    "_get_devices_list",
    "_is_key_without_billing_plan",
    "_resolve_plan_id_for_key",
    "_extract_traffic_used_bytes",
    "_format_bytes_gb",
    "_get_tariff_info_for_key",
    "sync_user_keys_with_remnawave",
]

async def _remnawave_key_exists(key_data: dict) -> bool | None:
    """Проверяет, существует ли ключ (пользователь) в Remnawave.

    Возвращает:
    - True  — ключ найден
    - False — ключ точно удалён (404 на поддерживаемом lookup)
    - None  — не удалось проверить (ошибка API/сети или UUID на 3.x без username)
    """
    try:
        host_name = key_data.get('host_name')
        email = key_data.get('key_email') or key_data.get('email')
        user_uuid = key_data.get('remnawave_user_uuid') or key_data.get('xui_client_uuid')
        return await remnawave_api.panel_user_exists(
            user_ref=user_uuid,
            email=email,
            host_name=host_name,
        )
    except remnawave_api.RemnawaveAPIError:
        return None
    except Exception:
        return None




def _extract_connected_devices(user_payload: dict | None) -> int:
    """Возвращает количество подключённых устройств (HWID/Devices) по данным Remnawave.

    В Remnawave это поле встречается в разных форматах:
    - списком (list)
    - объектом-пейджером (dict) с полями data/items/list и т.п.
    - уже готовым числом count/total
    Поэтому парсер старается быть максимально терпимым к схеме.
    """
    if not isinstance(user_payload, dict):
        return 0

    def _count_from_value(val) -> int | None:
        if isinstance(val, list):
            return len(val)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.strip().isdigit():
            return int(val.strip())
        if isinstance(val, dict):
            # Часто список лежит внутри data/items/list/rows/results/devices/hwids
            for kk in (
                "data",
                "items",
                "list",
                "rows",
                "results",
                "devices",
                "hwids",
                "hwidDevices",
            ):
                inner = val.get(kk)
                if isinstance(inner, list):
                    return len(inner)
            # Или отдельно приходит total/count
            for kk in ("total", "count", "totalCount", "itemsCount"):
                inner = val.get(kk)
                if isinstance(inner, int):
                    return inner
                if isinstance(inner, str) and inner.strip().isdigit():
                    return int(inner.strip())
        return None

    # 1) Пробуем извлечь из наиболее вероятных ключей (camelCase + snake_case)
    list_like_keys = (
        "hwidDevices",
        "hwid_devices",
        "devices",
        "device_ids",
        "deviceIds",
        "connectedDevices",
        "connected_devices",
        "activeHwids",
        "active_hwids",
        "activeHwidDevices",
        "active_hwid_devices",
        "hwids",
        "hwidDeviceIds",
        "hwid_device_ids",
        "hwid_devices_info",
        "hwidDevicesInfo",
        "hwidDeviceInfo",
    )
    for key in list_like_keys:
        if key in user_payload:
            cnt = _count_from_value(user_payload.get(key))
            if isinstance(cnt, int):
                return max(0, cnt)

    # 2) Пробуем готовые count-поля (camelCase + snake_case)
    count_keys = (
        "activeHwidCount",
        "active_hwid_count",
        "activeHwidDeviceCount",
        "active_hwid_device_count",
        "hwidDeviceCount",
        "hwid_device_count",
        "hwidDevicesCount",
        "hwid_devices_count",
        "devicesCount",
        "devices_count",
        "connectedDevicesCount",
        "connected_devices_count",
        "connections",
    )
    for key in count_keys:
        if key in user_payload:
            cnt = _count_from_value(user_payload.get(key))
            if isinstance(cnt, int):
                return max(0, cnt)

    # 3) Иногда данные вложены в hwid/hwidInfo/deviceInfo
    nested = user_payload.get("hwid") or user_payload.get("hwidInfo") or user_payload.get("deviceInfo") or user_payload.get("devicesInfo")
    if isinstance(nested, dict):
        for key in (
            "devices",
            "deviceIds",
            "device_ids",
            "list",
            "items",
            "data",
            "hwidDevices",
            "hwid_devices",
        ):
            if key in nested:
                cnt = _count_from_value(nested.get(key))
                if isinstance(cnt, int):
                    return max(0, cnt)

    # 4) Последняя попытка: пройтись по всем ключам и найти пейджер/список с hwid/devices
    # (помогает при неожиданных изменениях схемы ответа)
    #
    # Важно: не путать количество устройств с лимитом устройств.
    # В ответах Remnawave часто встречаются поля вроде `hwidDeviceLimit`/`device_limit`,
    # и если их ошибочно принять за количество подключённых устройств — на экране
    # будет показываться лимит вместо фактического числа подключений.
    for k, v in user_payload.items():
        lk = str(k).lower()
        if ("hwid" in lk or "device" in lk) and not any(x in lk for x in ("limit", "max", "quota")):
            cnt = _count_from_value(v)
            if isinstance(cnt, int) and cnt > 0:
                return cnt

    return 0


async def _get_connected_devices_count(key_data: dict, user_payload: dict | None) -> int:
    """Надёжно получить количество подключённых HWID-устройств.

    Remnawave не всегда возвращает HWID-устройства внутри /api/users,
    поэтому если в user_payload получается 0 — делаем отдельный запрос
    /api/hwid/devices/{userUuid}.
    """

    base_cnt = _extract_connected_devices(user_payload)
    if base_cnt > 0:
        return base_cnt

    if not isinstance(user_payload, dict):
        return 0

    user_uuid = remnawave_api.panel_user_ref_from_payload(user_payload)
    host_name = (key_data or {}).get("host_name")
    email = (key_data or {}).get("key_email") or (key_data or {}).get("email")
    if not user_uuid:
        return 0

    hwid_payload = None
    try:
        hwid_payload = await remnawave_api.get_hwid_devices_for_user(
            user_uuid, host_name=host_name, email=email
        )
    except Exception:
        hwid_payload = None

    def _count_any(val) -> int:
        if val is None:
            return 0
        if isinstance(val, list):
            return len(val)
        if isinstance(val, int):
            return max(0, val)
        if isinstance(val, str) and val.strip().isdigit():
            return int(val.strip())
        if isinstance(val, dict):
            # ready counts
            for kk in ("total", "count", "totalCount", "itemsCount", "total_count", "items_count"):
                inner = val.get(kk)
                c = _count_any(inner)
                if c:
                    return c

            # common containers
            for kk in (
                "items",
                "data",
                "list",
                "rows",
                "results",
                "devices",
                "hwidDevices",
                "hwid_devices",
                "hwids",
            ):
                inner = val.get(kk)
                c = _count_any(inner)
                if c:
                    return c

            # fallback scan
            # (но не путаем лимиты устройств с количеством подключённых устройств)
            for k, v in val.items():
                lk = str(k).lower()
                if ("hwid" in lk or "device" in lk or lk in ("data", "items", "list", "rows")) and not any(
                    x in lk for x in ("limit", "max", "quota")
                ):
                    c = _count_any(v)
                    if c:
                        return c
        return 0

    return _count_any(hwid_payload)


async def _get_devices_list(key_data: dict, user_payload: dict | None) -> list[dict]:
    """Получить полный список подключённых HWID-устройств с информацией о каждом.
    
    Возвращает список словарей вида:
    {
        'hwid': 'device_id',
        'platform': 'iOS' или None,
        'osVersion': '16.0' или None,
        'deviceModel': 'iPhone 12' или None,
        'userAgent': '...' или None,
    }
    """
    if not isinstance(user_payload, dict):
        return []
    
    user_uuid = remnawave_api.panel_user_ref_from_payload(user_payload)
    host_name = (key_data or {}).get("host_name")
    email = (key_data or {}).get("key_email") or (key_data or {}).get("email")
    
    if not user_uuid:
        return []
    
    try:
        hwid_payload = await remnawave_api.get_hwid_devices_for_user(
            user_uuid, host_name=host_name, email=email
        )
    except Exception:
        return []
    
    if not hwid_payload:
        return []
    
    # Пытаемся извлечь список устройств из ответа
    devices = []
    
    # Стандартные места где могут быть устройства
    possible_containers = [
        hwid_payload if isinstance(hwid_payload, list) else None,
        hwid_payload.get("devices") if isinstance(hwid_payload, dict) else None,
        hwid_payload.get("list") if isinstance(hwid_payload, dict) else None,
        hwid_payload.get("response") if isinstance(hwid_payload, dict) else None,
        hwid_payload.get("data") if isinstance(hwid_payload, dict) else None,
        hwid_payload.get("items") if isinstance(hwid_payload, dict) else None,
    ]
    
    for container in possible_containers:
        if isinstance(container, list):
            devices = [d for d in container if isinstance(d, dict)]
            if devices:
                break
    
    return devices


def _is_key_without_billing_plan(key_data: dict) -> bool:
    """Триальный или подарочный ключ: биллингового тарифа у него нет.

    Для таких ключей `plan_id` в description намеренно None (см. вызовы
    `_build_key_origin_meta(source="trial"/"gift", plan_id=None)`), поэтому подставлять
    им «первый активный тариф хоста» нельзя: это исказило бы и лимиты в карточке
    ключа, и набор пакетов докупки.

    TODO: для подарочных ключей точный тариф известен в `user_gifts.plan_id`
    (rw_repo.get_gift_info_by_key_id) — при необходимости докупку для подарков можно
    включить, резолвя тариф оттуда, а не эвристикой по хосту.
    """
    try:
        tag = str((key_data or {}).get("tag") or "").strip().lower()
    except Exception:
        tag = ""
    if tag in {"trial", "триал"} or "gift" in tag:
        return True
    try:
        desc = (key_data or {}).get("description")
        if isinstance(desc, str) and desc.strip().startswith("{"):
            meta = json.loads(desc)
            if isinstance(meta, dict):
                if meta.get("is_trial"):
                    return True
                if str(meta.get("source") or "").strip().lower() in {"trial", "gift"}:
                    return True
    except Exception:
        pass
    return False

def _resolve_plan_id_for_key(key_data: dict) -> int | None:
    """Определяет plan_id, привязанный к ключу.

    Приоритеты:
      1) plan_id из vpn_keys.description (JSON, пишется при покупке/продлении);
      2) fallback на первый активный тариф хоста — как в `_get_tariff_info_for_key`.

    Без п.2 у ключей, выданных до появления этого поля (или с не-JSON description),
    докупка ГБ/LTE была недоступна, хотя тариф хоста существует и карточка ключа
    показывала его название через fallback в `_get_tariff_info_for_key`.
    """
    try:
        desc = (key_data or {}).get("description")
        if isinstance(desc, str) and desc.strip().startswith("{"):
            meta = json.loads(desc)
            if isinstance(meta, dict) and meta.get("plan_id") is not None:
                return int(meta.get("plan_id"))
    except Exception:
        pass

    if _is_key_without_billing_plan(key_data):
        return None

    host_name = (key_data or {}).get("host_name")
    if not host_name:
        return None
    try:
        plans = get_active_plans_for_host(host_name) or []
    except Exception:
        plans = []
    if not plans:
        return None
    try:
        return int(plans[0].get("plan_id"))
    except (TypeError, ValueError):
        return None


def _extract_traffic_used_bytes(payload: dict | None) -> int:
    """Извлекает использованный трафик из payload пользователя Remnawave (если поле есть)."""
    if not isinstance(payload, dict):
        return 0
    candidates = [
        "trafficUsedBytes", "traffic_used_bytes", "usedTrafficBytes",
        "trafficUsed", "traffic_used", "usedBytes", "bytesUsed",
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
    return 0

def _format_bytes_gb(num_bytes: int) -> str:
    try:
        gb = num_bytes / (1024 ** 3)
        return f"{gb:.2f}".rstrip('0').rstrip('.') if '.' in f"{gb:.2f}" else f"{gb:.2f}"
    except Exception:
        return "0"

def _get_tariff_info_for_key(key_data: dict, user_payload: dict | None = None) -> tuple[str, str, int]:
    """Подбирает данные тарифа для отображения в 'Мои ключи'.

    Приоритеты:
      1) точные данные из Remnawave (user_payload.hwidDeviceLimit)
      2) тариф, выбранный при покупке/продлении (vpn_keys.description JSON -> plan_id)
      3) fallback на первый активный тариф хоста
    """
    host_name = (key_data or {}).get("host_name")

    # 1) Prefer per-key origin info (stored in vpn_keys.description/tag)
    plan_name_from_key = None
    plan_id_from_key: int | None = None
    device_limit_from_key: int | None = None

    try:
        tag = (key_data or {}).get("tag") or ""
        if str(tag).strip().lower() in {"trial", "триал"}:
            plan_name_from_key = "триал"
    except Exception:
        pass

    # Extra heuristic for legacy trial keys: we often generate emails like "trial_*@bot.local".
    try:
        if plan_name_from_key is None:
            em = str((key_data or {}).get("key_email") or "")
            if em.lower().startswith("trial_") or ("@bot.local" in em.lower() and "trial" in em.lower()):
                plan_name_from_key = "триал"
    except Exception:
        pass

    try:
        desc = (key_data or {}).get("description")
        if isinstance(desc, str) and desc.strip():
            d = desc.strip()
            if plan_name_from_key is None and ("trial" in d.lower() or "триал" in d.lower()):
                plan_name_from_key = "триал"
            if d.startswith("{"):
                meta = json.loads(d)
                if isinstance(meta, dict):
                    if meta.get("tariff_label"):
                        plan_name_from_key = str(meta.get("tariff_label"))
                    elif meta.get("is_trial"):
                        plan_name_from_key = "триал"

                    # selected plan id (so we can render correct limits even if host plans list changes)
                    if meta.get("plan_id") is not None:
                        try:
                            plan_id_from_key = int(meta.get("plan_id"))
                        except Exception:
                            plan_id_from_key = None

                    # optional future field
                    for kk in ("hwid_device_limit", "device_limit", "devices_limit", "hwidDeviceLimit"):
                        if meta.get(kk) is not None:
                            try:
                                device_limit_from_key = int(meta.get(kk))
                            except Exception:
                                device_limit_from_key = None
                            break

                    if not plan_name_from_key:
                        try:
                            dd = int(meta.get("duration_days") or 0)
                        except Exception:
                            dd = 0
                        try:
                            mm = int(meta.get("months") or 0)
                        except Exception:
                            mm = 0
                        if dd > 0:
                            plan_name_from_key = f"{dd} дней"
                        elif mm > 0:
                            plan_name_from_key = f"{mm * 30} дней"
    except Exception:
        pass

    origin_locked = bool(plan_name_from_key and str(plan_name_from_key).strip())

    # 2) Prefer exact device limit from Remnawave payload
    device_limit: int | None = None
    if isinstance(user_payload, dict):
        for kk in ("hwidDeviceLimit", "deviceLimit", "device_limit", "maxDevices", "maxDeviceCount", "hwid_device_limit"):
            val = user_payload.get(kk)
            if val is not None:
                try:
                    v = int(val)
                    if v > 0:
                        device_limit = v
                        break
                except Exception:
                    pass

    # 3) Determine plan (by stored plan_id, else first active plan for host)
    plan = None
    if plan_id_from_key:
        try:
            plan = get_plan_by_id(int(plan_id_from_key))
        except Exception:
            plan = None

    if not isinstance(plan, dict):
        try:
            plans = get_active_plans_for_host(host_name) or get_plans_for_host(host_name) or []
            plan = plans[0] if plans else None
        except Exception:
            plan = None

    plan_name = plan_name_from_key
    duration_days = 0

    if isinstance(plan, dict):
        if not plan_name:
            plan_name = plan.get("plan_name")

        # If we still don't have device limit, try from plan
        if device_limit in (None, 0):
            try:
                pl_dev = plan.get("hwid_device_limit") or plan.get("hwidDeviceLimit")
                if pl_dev is not None:
                    pl_dev_int = int(pl_dev)
                    if pl_dev_int > 0:
                        device_limit = pl_dev_int
            except Exception:
                pass

        # try metadata json stored in plan (legacy)
        if device_limit in (None, 0) and plan.get("metadata"):
            try:
                meta_obj = json.loads(plan.get("metadata")) if isinstance(plan.get("metadata"), str) else plan.get("metadata")
                if isinstance(meta_obj, dict):
                    for kk in ("hwid_device_limit", "device_limit", "devices_limit", "hwidDeviceLimit"):
                        if meta_obj.get(kk) is not None:
                            v = int(meta_obj.get(kk))
                            if v > 0:
                                device_limit = v
                                break
            except Exception:
                pass

        try:
            duration_days = int(plan.get("duration_days") or 0)
        except Exception:
            duration_days = 0
        if not duration_days:
            try:
                months = int(plan.get("months") or 0)
                duration_days = months * 30 if months else 0
            except Exception:
                duration_days = 0

        if not plan_name:
            plan_name = f"{duration_days} дней" if duration_days else None
        else:
            try:
                if (not origin_locked) and isinstance(plan_name, str) and not re.search(r"\d", plan_name) and duration_days:
                    if plan_name.strip().lower() not in {"trial", "триал"}:
                        plan_name = f"{duration_days} дней"
            except Exception:
                pass

    # 4) device limit from key-origin meta (if present) — after payload, before fallbacks
    if device_limit in (None, 0) and device_limit_from_key:
        device_limit = int(device_limit_from_key)

    # 5) trial fallback
    if device_limit in (None, 0):
        try:
            tag = (key_data or {}).get("tag") or ""
            is_trial = str(tag).strip().lower() in {"trial", "триал"} or (plan_name_from_key == "триал")
        except Exception:
            is_trial = False
        if is_trial:
            try:
                raw_dev = (get_setting("trial_device_limit") or "").strip()
                if raw_dev:
                    v = int(float(raw_dev.replace(",", ".")))
                    if v > 0:
                        device_limit = v
            except Exception:
                pass

    # final fallback: if we still don't know origin, at least show current key validity window
    if not plan_name:
        try:
            created_iso = (key_data or {}).get("created_date") or (key_data or {}).get("created_at")
            expiry_iso = (key_data or {}).get("expiry_date") or (key_data or {}).get("expire_at")
            if created_iso and expiry_iso:
                cd = datetime.fromisoformat(str(created_iso))
                ed = datetime.fromisoformat(str(expiry_iso))
                days = max(0, int((ed - cd).total_seconds() // 86400))
                if days:
                    plan_name = f"{days} дней"
        except Exception:
            pass

    if not plan_name:
        plan_name = "—"
    if not device_limit:
        device_limit = 5

    group = f"{int(device_limit)} устройств📡"
    return group, plan_name, int(device_limit)

async def sync_user_keys_with_remnawave(user_id: int) -> int:
    """Синхронизирует ключи пользователя в БД с фактическими ключами в Remnawave.

    Раньше бот *сразу* удалял ключ из локальной БД, если Remnawave отвечал 404.
    При большом количестве пользователей (>500) и/или проблемах пагинации/поиска на панели
    это могло приводить к ложным 404 и массовым удалениям активных ключей.

    Новая логика безопаснее:
    - если ключ не найден, сначала помечаем его как "missing_from_server_at"
    - удаляем из БД только если ключ отсутствует повторно и "missing_from_server_at" старше 24 часов
    - если ключ снова найден — снимаем пометку missing_from_server_at

    Возвращает количество удалённых из БД ключей.
    """
    keys = get_user_keys(user_id) or []
    if not keys:
        return 0

    now_dt = datetime.utcnow()
    grace = timedelta(hours=24)

    def _parse_missing_dt(value) -> datetime | None:
        if not value:
            return None
        try:
            s = str(value).strip()
            # common formats: "YYYY-MM-DD HH:MM:SS" or ISO
            s = s.replace("Z", "+00:00")
            if " " in s and "T" not in s:
                s = s.replace(" ", "T", 1)
            dt = datetime.fromisoformat(s)
            # store as UTC-naive in DB; treat as UTC
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None

    async def _check(key: dict):
        exists = await _remnawave_key_exists(key)
        return key, exists

    tasks = [_check(k) for k in keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    removed = 0
    for item in results:
        if isinstance(item, Exception):
            continue
        key, exists = item
        key_id = key.get("key_id")
        if not key_id:
            continue

        # exists: True / False / None (None => API error; ничего не делаем)
        if exists is False:
            missing_dt = _parse_missing_dt(key.get("missing_from_server_at"))
            if missing_dt and (now_dt - missing_dt) > grace:
                try:
                    if delete_key_by_id(int(key_id)):
                        removed += 1
                except Exception:
                    pass
            else:
                # помечаем как отсутствующий, но не удаляем
                try:
                    database.update_key_fields(
                        int(key_id),
                        missing_from_server_at=now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                except Exception:
                    pass
        elif exists is True:
            # если ранее помечали как missing — снимаем
            if key.get("missing_from_server_at"):
                try:
                    database.update_key_fields(int(key_id), missing_from_server_at=None)
                except Exception:
                    pass

    return removed
