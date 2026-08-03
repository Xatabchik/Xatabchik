import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import quote
import re
import asyncio

import httpx

from shop_bot.data_manager import remnawave_repository as rw_repo

logger = logging.getLogger(__name__)

try:
    logging.getLogger("httpx").setLevel(logging.WARNING)
except Exception:
    pass


class RemnawaveAPIError(RuntimeError):
    """Base error for Remnawave API interactions."""


# Shared HTTPX clients (connection pooling) to avoid creating a new TCP/TLS connection
# for each Remnawave request. This noticeably reduces latency and eliminates a source
# of "bot подвисает" on slow networks.
#
# ВАЖНО: каждый обработчик Flask вызывает asyncio.run(...), который создаёт НОВЫЙ
# event loop и закрывает его по завершении. httpx.AsyncClient и его пул соединений
# привязаны к тому loop'у, в котором были созданы — если переиспользовать клиент из
# уже закрытого loop'а, при попытке закрыть "протухшее" соединение получим
# "RuntimeError: Event loop is closed". Поэтому храним вместе с клиентом ссылку на
# loop, в котором он был создан, и пересоздаём клиент, если текущий loop другой.
_CLIENTS: dict[tuple[str, str, bool], httpx.AsyncClient] = {}
_CLIENTS_LOOP: dict[tuple[str, str, bool], asyncio.AbstractEventLoop] = {}
# Обычный (не asyncio.Lock) замок: он не привязан к конкретному event loop/потоку
# и защищает доступ к словарям клиентов из разных потоков/loop'ов безопасно.
_CLIENTS_LOCK = threading.Lock()

# Reasonable defaults: do not let handlers hang too long on network hiccups.
_DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0, read=20.0, write=20.0, pool=20.0)
_DEFAULT_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20)


async def _get_shared_client(config: dict[str, Any]) -> httpx.AsyncClient:
    base_url = (config.get("base_url") or "").strip().rstrip("/")
    token = (config.get("token") or "").strip()
    is_local = bool(config.get("is_local"))
    key = (base_url, token, is_local)
    loop = asyncio.get_running_loop()
    with _CLIENTS_LOCK:
        client = _CLIENTS.get(key)
        cached_loop = _CLIENTS_LOOP.get(key)
        is_stale = client is not None and (getattr(client, "is_closed", False) or cached_loop is not loop)
        if client is not None and not is_stale:
            return client
        if client is not None and is_stale:
            # Клиент был создан в другом (возможно, уже закрытом) event loop.
            # Штатно закрыть его сейчас нельзя — aclose() должен вызываться в том
            # же loop, где клиент создавался, поэтому просто отбрасываем ссылку и
            # даём сборщику мусора/ОС закрыть сокеты естественным образом.
            _CLIENTS.pop(key, None)
            _CLIENTS_LOOP.pop(key, None)
        client = httpx.AsyncClient(
            cookies=config.get("cookies") or {},
            timeout=_DEFAULT_TIMEOUT,
            limits=_DEFAULT_LIMITS,
        )
        _CLIENTS[key] = client
        _CLIENTS_LOOP[key] = loop
        return client


def _normalize_email_for_remnawave(email: str) -> str:
    """Normalize and validate email for Remnawave API.

    - Lowercases the email
    - If domain is missing or email invalid, tries to sanitize local-part by replacing
      any characters outside [a-z0-9._+-] with '_'
    - Validates with a conservative regex that excludes '/'
    - Raises RemnawaveAPIError if validation still fails
    """
    if not email:
        raise RemnawaveAPIError("email is required")
    e = (email or "").strip().lower()

    if "@" not in e:
        raise RemnawaveAPIError(f"Invalid email (no domain): {email}")
    local, domain = e.split("@", 1)

    local = re.sub(r"[^a-z0-9._+\-]", "_", local)

    local = re.sub(r"\.+", ".", local)

    local = local.strip("._-")

    if not local or not re.match(r"^[a-z0-9]", local):
        local = f"u{local}" if local else f"user{int(datetime.utcnow().timestamp())}"
    e_sanitized = f"{local}@{domain}"

    pattern = re.compile(r"^[a-z0-9](?:[a-z0-9._+\-]*[a-z0-9])?@[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?)+$")

    if ".." in e_sanitized or not pattern.match(e_sanitized):
        raise RemnawaveAPIError(f"Invalid email after normalization: {e_sanitized}")
    return e_sanitized


def _normalize_username_for_remnawave(name: str | None) -> str:
    """Normalize username to only letters, numbers, underscores and dashes.

    - Lowercase
    - Replace invalid characters with '_'
    - Trim leading/trailing '_' and '-'
    - Ensure starts with alnum; if not, prefix with 'u'
    - Limit length to 32 characters
    - Fallback to 'user<timestamp>' if empty
    """
    base = (name or "").strip().lower()
    base = re.sub(r"[^a-z0-9_\-]", "_", base)
    base = base.strip("_-")
    if not base or not re.match(r"^[a-z0-9]", base):
        base = f"u{base}" if base else f"user{int(datetime.utcnow().timestamp())}"
    if len(base) > 32:
        base = base[:32].rstrip("_-") or base[:32]

    if len(base) < 3:

        suffix = str(int(datetime.utcnow().timestamp()))
        base = (base + suffix)[:3]

        if len(base) < 3:
            base = (base + "usr")[:3]
    return base

def _load_config() -> dict[str, Any]:
    """Backward-compatible global config loader (deprecated)."""
    base_url = (rw_repo.get_setting("remnawave_base_url") or "").strip().rstrip("/")
    token = (rw_repo.get_setting("remnawave_api_token") or "").strip()
    cookies = {}
    is_local = False
    if not base_url or not token:
        raise RemnawaveAPIError("Remnawave API settings are not configured")
    return {"base_url": base_url, "token": token, "cookies": cookies, "is_local": is_local}


def _load_config_for_host(host_name: str) -> dict[str, Any]:
    """Load Remnawave API config for a specific host from xui_hosts."""
    if not host_name:
        raise RemnawaveAPIError("host_name is required")
    squad = rw_repo.get_squad(host_name)
    if not squad:
        raise RemnawaveAPIError(f"Host '{host_name}' not found")
    base_url = (squad.get("remnawave_base_url") or "").strip().rstrip("/")
    token = (squad.get("remnawave_api_token") or "").strip()
    if not base_url or not token:

        try:
            return _load_config()
        except RemnawaveAPIError:
            raise RemnawaveAPIError(f"Remnawave API settings are not configured for host '{host_name}'")
    return {"base_url": base_url, "token": token, "cookies": {}, "is_local": False}


def _build_headers(config: dict[str, Any]) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type": "application/json",
    }
    if config.get("is_local"):
        headers["X-Forwarded-Proto"] = "https"
        headers["X-Forwarded-For"] = "127.0.0.1"
    return headers


async def _request(
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    expected_status: tuple[int, ...] = (200,),
) -> httpx.Response:

    config = _load_config()
    url = f"{config['base_url']}{path}"
    headers = _build_headers(config)

    client = await _get_shared_client(config)

    try:
        full_url = httpx.URL(url).copy_merge_params(params or {})
        logger.info("➡️ Remnawave: %s %s", method.upper(), str(full_url))
    except Exception:
        pass
    t0 = time.perf_counter()
    response = await client.request(
        method=method,
        url=url,
        headers=headers,
        json=json_payload,
        params=params,
    )
    dt_ms = int((time.perf_counter() - t0) * 1000)
    try:
        status = response.status_code
        ok = "OK" if status in expected_status else "ERROR"
        logger.info("⬅️ Remnawave: %s %s — %s (%d мс)", method.upper(), path, f"{status} {ok}", dt_ms)
    except Exception:
        pass

    if response.status_code not in expected_status:
        try:
            detail = response.json()
        except json.JSONDecodeError:
            detail = response.text
        logger.warning("Remnawave API %s %s завершился ошибкой: %s", method, path, detail)
        raise RemnawaveAPIError(f"Remnawave API request failed: {response.status_code} {detail}")

    return response


async def _request_for_host(
    host_name: str,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    expected_status: tuple[int, ...] = (200,),
) -> httpx.Response:
    config = _load_config_for_host(host_name)
    url = f"{config['base_url']}{path}"
    headers = _build_headers(config)

    client = await _get_shared_client(config)

    try:
        full_url = httpx.URL(url).copy_merge_params(params or {})
        logger.info("➡️ Remnawave[%s]: %s %s", host_name, method.upper(), str(full_url))
    except Exception:
        pass
    t0 = time.perf_counter()
    response = await client.request(
        method=method,
        url=url,
        headers=headers,
        json=json_payload,
        params=params,
    )
    dt_ms = int((time.perf_counter() - t0) * 1000)
    try:
        status = response.status_code
        ok = "OK" if status in expected_status else "ERROR"
        logger.info("⬅️ Remnawave[%s]: %s %s — %s (%d мс)", host_name, method.upper(), path, f"{status} {ok}", dt_ms)
    except Exception:
        pass

    if response.status_code not in expected_status:
        try:
            detail = response.json()
        except json.JSONDecodeError:
            detail = response.text
        logger.warning("Remnawave API %s %s завершился ошибкой: %s", method, path, detail)
        raise RemnawaveAPIError(f"Remnawave API request failed: {response.status_code} {detail}")

    return response


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.isoformat().replace("+00:00", "Z")


async def get_user_by_email(email: str, *, host_name: str | None = None) -> dict[str, Any] | None:
    if not email:
        return None
    encoded_email = quote(email.strip())
    if host_name:
        response = await _request_for_host(host_name, "GET", f"/api/users/by-email/{encoded_email}", expected_status=(200, 404))
    else:
        response = await _request("GET", f"/api/users/by-email/{encoded_email}", expected_status=(200, 404))
    if response.status_code == 404:
        return None
    payload = response.json()

    data: Any
    if isinstance(payload, dict):
        inner = payload.get("response")
        data = inner if inner is not None else payload
    else:
        data = payload

    if isinstance(data, list):

        for item in data:
            if isinstance(item, dict):
                return item
        return None
    return data if isinstance(data, dict) else None


async def get_user_by_username(username: str, *, host_name: str | None = None) -> dict[str, Any] | None:
    if not username:
        return None
    encoded_username = quote(username.strip())
    if host_name:
        response = await _request_for_host(host_name, "GET", f"/api/users/by-username/{encoded_username}", expected_status=(200, 404))
    else:
        response = await _request("GET", f"/api/users/by-username/{encoded_username}", expected_status=(200, 404))
    if response.status_code == 404:
        return None
    payload = response.json()
    if isinstance(payload, dict):
        inner = payload.get("response")
        data = inner if inner is not None else payload
    else:
        data = payload
    return data if isinstance(data, dict) else None


async def get_user_by_uuid(user_uuid: str, *, host_name: str | None = None) -> dict[str, Any] | None:
    if not user_uuid:
        return None
    encoded_uuid = quote(user_uuid.strip())
    if host_name:
        response = await _request_for_host(host_name, "GET", f"/api/users/{encoded_uuid}", expected_status=(200, 404))
    else:
        response = await _request("GET", f"/api/users/{encoded_uuid}", expected_status=(200, 404))
    if response.status_code == 404:
        return None
    payload = response.json()
    return payload.get("response") if isinstance(payload, dict) else None


async def get_hwid_devices_for_user(user_uuid: str, *, host_name: str | None = None) -> Any | None:
    """Получить информацию об HWID-устройствах пользователя.

    В Remnawave HWID устройства живут отдельным endpoint'ом и не всегда
    возвращаются внутри /api/users. Поэтому для корректного подсчёта
    подключённых устройств используем этот запрос как источник истины.
    """
    if not user_uuid:
        return None

    encoded_uuid = quote(str(user_uuid).strip())
    try:
        if host_name:
            response = await _request_for_host(
                host_name,
                "GET",
                f"/api/hwid/devices/{encoded_uuid}",
                expected_status=(200, 404),
            )
        else:
            response = await _request(
                "GET",
                f"/api/hwid/devices/{encoded_uuid}",
                expected_status=(200, 404),
            )

        if response.status_code == 404:
            return None

        payload = response.json()
        if isinstance(payload, dict):
            inner = payload.get("response")
            if inner is None:
                inner = payload.get("data")
            return inner if inner is not None else payload
        return payload
    except RemnawaveAPIError:
        return None
    except Exception:
        logger.exception("Remnawave: ошибка get_hwid_devices_for_user(%s)", user_uuid)
        return None


async def delete_hwid_device(user_uuid: str, hwid: str, *, host_name: str | None = None) -> bool:
    """Удалить одно HWID-устройство пользователя через API.
    
    Args:
        user_uuid: UUID пользователя в Remnawave
        hwid: Hardware ID удаляемого устройства
        host_name: Имя хоста (если нужна привязка к конкретному хосту)
    
    Returns:
        True если успешно удалено, False в случае ошибки
    """
    if not user_uuid or not hwid:
        return False
    
    try:
        payload = {
            "userUuid": str(user_uuid).strip(),
            "hwid": str(hwid).strip(),
        }
        
        if host_name:
            response = await _request_for_host(
                host_name,
                "POST",
                "/api/hwid/devices/delete",
                json_payload=payload,
                expected_status=(200, 204, 404),
            )
        else:
            response = await _request(
                "POST",
                "/api/hwid/devices/delete",
                json_payload=payload,
                expected_status=(200, 204, 404),
            )
        
        if response.status_code == 404:
            logger.warning("Remnawave: устройство %s пользователя %s не найдено (возможно, уже удалено)", hwid, user_uuid)
            return True
        
        if response.status_code in (200, 204):
            logger.info("Remnawave: устройство %s пользователя %s успешно удалено", hwid, user_uuid)
            return True
        
        logger.error("Remnawave: ошибка удаления устройства %s (HTTP %s)", hwid, response.status_code)
        return False

    except RemnawaveAPIError as e:
        logger.error("Remnawave: ошибка API при удалении устройства %s: %s", hwid, e)
        return False
    except Exception:
        logger.exception("Remnawave: непредвиденная ошибка при удалении устройства %s", hwid)
        return False


async def get_connected_devices_count(user_uuid: str, *, host_name: str | None = None) -> dict[str, Any] | None:
    """Обёртка над get_hwid_devices_for_user для webapp: всегда возвращает
    dict с ключом "devices" (список), даже если исходный ответ Remnawave —
    просто список или пуст."""
    raw = await get_hwid_devices_for_user(user_uuid, host_name=host_name)
    if raw is None:
        return {"devices": []}
    if isinstance(raw, dict):
        devices = raw.get("devices")
        if devices is None:
            devices = raw.get("hwidDevices") or raw.get("items") or []
        return {"devices": devices}
    if isinstance(raw, list):
        return {"devices": raw}
    return {"devices": []}


async def delete_user_device(user_uuid: str, device_id: str, *, host_name: str | None = None) -> bool:
    """Алиас delete_hwid_device с именем, ожидаемым webapp/handlers.py."""
    return await delete_hwid_device(user_uuid, device_id, host_name=host_name)


async def ensure_user(
    *,
    host_name: str,
    email: str,
    squad_uuid: str,
    expire_at: datetime,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    description: str | None = None,
    tag: str | None = None,
    username: str | None = None,
    hwid_device_limit: int | None = None,
    extra_squad_uuids: list[str] | None = None,
) -> dict[str, Any]:
    if not email:
        raise RemnawaveAPIError("email is required for ensure_user")
    if not squad_uuid:
        raise RemnawaveAPIError("squad_uuid is required for ensure_user")

    active_squads = list(dict.fromkeys([squad_uuid] + list(extra_squad_uuids or [])))

    email = _normalize_email_for_remnawave(email)
    current = await get_user_by_email(email, host_name=host_name)
    expire_iso = _to_iso(expire_at)
    traffic_limit_strategy = traffic_limit_strategy or "NO_RESET"

    # hwid_device_limit can come from SQLite/settings and may be stored as TEXT
    try:
        if hwid_device_limit is not None:
            hwid_device_limit = int(hwid_device_limit)
    except Exception:
        hwid_device_limit = None

    payload: dict[str, Any]
    method: str
    path: str

    if current:
        current_expire = current.get("expireAt")
        if current_expire:
            try:
                current_dt = datetime.fromisoformat(current_expire.replace("Z", "+00:00"))
                if current_dt > expire_at:
                    expire_iso = _to_iso(current_dt)
            except ValueError:
                pass

        _current_id = current.get("id") or current.get("uuid")
        _current_username = current.get("username")
        logger.info(
            "Remnawave: найден пользователь %s (id=%s) на '%s' — обновляю срок до %s",
            email,
            _current_id,
            host_name,
            expire_iso,
        )

        payload = {
            "status": "ACTIVE",
            "expireAt": expire_iso,
            "activeInternalSquads": active_squads,
            "email": email,
        }
        # Remnawave PATCH requires at least one of: username, id
        if _current_id is not None:
            payload["id"] = _current_id
        if _current_username:
            payload["username"] = _current_username

        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if traffic_limit_strategy is not None:
            payload["trafficLimitStrategy"] = traffic_limit_strategy
        if description:
            payload["description"] = description
        if tag:
            payload["tag"] = re.sub(r"[^A-Z0-9_]", "_", tag.upper())
        if hwid_device_limit is not None:
            payload["hwidDeviceLimit"] = hwid_device_limit
        method = "PATCH"
        path = "/api/users"
    else:
        logger.info(
            "Remnawave: пользователь %s не найден на '%s' — создаю нового (сквад %s, срок до %s)",
            email,
            host_name,
            squad_uuid,
            expire_iso,
        )
        generated_username = _normalize_username_for_remnawave(username or email.split("@")[0])
        payload = {
            "username": generated_username,
            "status": "ACTIVE",
            "expireAt": expire_iso,
            "activeInternalSquads": active_squads,
            "email": email,
        }

        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if traffic_limit_strategy is not None:
            payload["trafficLimitStrategy"] = traffic_limit_strategy
        if description:
            payload["description"] = description
        if tag:
            payload["tag"] = re.sub(r"[^A-Z0-9_]", "_", tag.upper())
        if hwid_device_limit is not None:
            payload["hwidDeviceLimit"] = hwid_device_limit
        method = "POST"
        path = "/api/users"

    try:
        response = await _request_for_host(host_name, method, path, json_payload=payload, expected_status=(200, 201))
    except RemnawaveAPIError as _exc:
        # A019: username collision — user exists under a different email; find and PATCH instead.
        if method == "POST" and ("A019" in str(_exc) or "username already exists" in str(_exc).lower()):
            _uname = payload.get("username", "")
            logger.warning(
                "Remnawave: A019 на '%s' — username '%s' уже занят, ищу по username и обновляю",
                host_name, _uname,
            )
            _existing = await get_user_by_username(_uname, host_name=host_name)
            if not _existing:
                raise
            _patch: dict[str, Any] = {
                "username": _uname,
                "status": "ACTIVE",
                "expireAt": expire_iso,
                "activeInternalSquads": active_squads,
            }
            _existing_id = _existing.get("id") or _existing.get("uuid")
            if _existing_id is not None:
                _patch["id"] = _existing_id
            if traffic_limit_bytes is not None:
                _patch["trafficLimitBytes"] = traffic_limit_bytes
            if traffic_limit_strategy is not None:
                _patch["trafficLimitStrategy"] = traffic_limit_strategy
            if description:
                _patch["description"] = description
            if tag:
                _patch["tag"] = re.sub(r"[^A-Z0-9_]", "_", tag.upper())
            if hwid_device_limit is not None:
                _patch["hwidDeviceLimit"] = hwid_device_limit
            response = await _request_for_host(host_name, "PATCH", "/api/users", json_payload=_patch, expected_status=(200, 201))
        else:
            raise
    data = response.json() or {}
    result = data.get("response") if isinstance(data, dict) else None
    if not result:
        raise RemnawaveAPIError("Remnawave API returned unexpected payload")

    action = "создан" if method == "POST" else "обновлён"
    logger.info(
        "Remnawave: пользователь %s (%s) на '%s' успешно %s. Истекает: %s",
        email,
        result.get("id") or result.get("uuid"),
        host_name,
        action,
        result.get("expireAt"),
    )
    return result




async def list_users(
    host_name: str,
    squad_uuid: str | None = None,
    size: int | None = None,
    *,
    max_pages: int = 100000,
) -> list[dict[str, Any]]:
    """List users from Remnawave.

    IMPORTANT:
    - Some Remnawave deployments paginate /api/users and may return only the first N records.
    - Historically the bot used size=500 and then удалял локальные ключи, если они не попадали в первую страницу.
    - Этот helper пытается забрать *все* страницы (фактически «без лимита»), но с защитой от бесконечных циклов
      (детект дубликатов + max_pages).

    Args:
        host_name: Remnawave host name.
        squad_uuid: If provided, request users for this squad (server-side) and also apply a defensive filter.
        size: Подсказка размера страницы. Если None — параметр size не отправляется, используется дефолт панели.
        max_pages: Страховочный лимит числа запросов/страниц (на случай, если API отдаёт бесконечную ленту).

    Returns:
        A list of user dicts.
    """

    def _extract_users_from_payload(payload: Any) -> list[dict[str, Any]]:
        raw_users: Any = []
        if isinstance(payload, dict):
            body = payload.get("response") if isinstance(payload.get("response"), dict) else payload
            raw_users = body.get("users") or body.get("data") or body.get("items") or body.get("list") or []
        if not isinstance(raw_users, list):
            return []
        return [u for u in raw_users if isinstance(u, dict)]

    def _filter_by_squad(users: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not squad_uuid:
            return users
        filtered: list[dict[str, Any]] = []
        for user in users:
            squads = user.get("activeInternalSquads") or user.get("internalSquads") or []
            if isinstance(squads, list):
                for item in squads:
                    if isinstance(item, dict):
                        if item.get("uuid") == squad_uuid:
                            filtered.append(user)
                            break
                    elif isinstance(item, str) and item == squad_uuid:
                        filtered.append(user)
                        break
            elif isinstance(squads, str) and squads == squad_uuid:
                filtered.append(user)
        return filtered

    async def _fetch(params: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        resp = await _request_for_host(host_name, "GET", "/api/users", params=params, expected_status=(200,))
        payload = resp.json() or {}
        users = _extract_users_from_payload(payload)
        return users, len(users)

    # Normalize size hint ("без лимита" достигается пагинацией до последней страницы).
    # Если size=None — не отправляем size, чтобы не упираться в произвольные верхние ограничения.
    page_size: int | None
    base_params: dict[str, Any] = {}
    if size is None:
        page_size = None
    else:
        try:
            page_size = int(size)
        except Exception:
            page_size = None
        if page_size is None or page_size <= 0:
            page_size = None
        else:
            base_params["size"] = page_size
    if squad_uuid:
        base_params["squadUuid"] = squad_uuid

    all_users: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _uid(u: dict[str, Any]) -> str:
        return str(u.get("uuid") or u.get("id") or u.get("email") or u.get("accountEmail") or "")

    def _append_new(page_users: list[dict[str, Any]]) -> int:
        added = 0
        for u in _filter_by_squad(page_users):
            ident = _uid(u)
            if not ident:
                # If we can't identify, still append but don't use for duplicate detection.
                all_users.append(u)
                added += 1
                continue
            if ident in seen:
                continue
            seen.add(ident)
            all_users.append(u)
            added += 1
        return added

    # 1) First page without any pagination params (most APIs treat it as the first page)
    first_page_users, first_len = await _fetch(dict(base_params))
    _append_new(first_page_users)

    if first_len <= 0:
        return all_users

    # If size wasn't provided, we infer the page size from the first page.
    if page_size is None:
        page_size = max(1, first_len)

    # If it clearly fits in one page — return (works reliably only when size is known)
    if size is not None and first_len < page_size:
        return all_users

    # 2) Try to detect pagination style: 0-based (page=1 is second page) or 1-based (page=2 is second page)
    #    If pagination params are ignored, the second request will return duplicates; we detect that.
    page_param = "page"

    async def _try_paged(start_page: int) -> bool:
        """Return True if paging seems to work (we got new users)."""
        params = dict(base_params)
        params[page_param] = start_page
        users, _len = await _fetch(params)
        added = _append_new(users)
        if added <= 0:
            return False

        # Continue paging
        current_page = start_page + 1
        pages_done = 2  # first page + one paged request
        while pages_done < max_pages:
            params = dict(base_params)
            params[page_param] = current_page
            users, page_len = await _fetch(params)
            added2 = _append_new(users)
            pages_done += 1
            if page_len < page_size:
                break
            if added2 <= 0:
                break
            current_page += 1
        return True

    paged_ok = False
    # Try 0-based style: page=1 is the next page
    paged_ok = await _try_paged(1)
    if not paged_ok:
        # Try 1-based style: page=2 is the next page
        paged_ok = await _try_paged(2)

    if paged_ok:
        return all_users

    # 3) Fallback: try offset-style pagination (offset/skip/from). Different deployments use different names.
    offset_param_candidates = ("offset", "skip", "from")
    for offset_param in offset_param_candidates:
        params = dict(base_params)
        params[offset_param] = page_size  # next page
        users, page_len = await _fetch(params)
        added = _append_new(users)
        if added <= 0:
            continue

        # Continue offset paging
        offset = page_size * 2
        pages_done = 2
        while pages_done < max_pages:
            params = dict(base_params)
            params[offset_param] = offset
            users, page_len = await _fetch(params)
            added2 = _append_new(users)
            pages_done += 1
            if page_len < page_size:
                break
            if added2 <= 0:
                break
            offset += page_size
        return all_users

    # Pagination seems unsupported/ignored; return what we have (first page).
    logger.warning(
        "Remnawave[%s]: /api/users выглядит как ограниченный список (>= %s записей), "
        "но пагинация не сработала. Возвращаю только первую страницу.",
        host_name,
        page_size,
    )
    return all_users
async def delete_user(user_uuid: str) -> bool:
    """Глобальный вариант (устарел): удаление без привязки к хосту.
    Сохраняется для обратной совместимости, но предпочтительно использовать host-specific путь ниже.
    """
    if not user_uuid:
        return False
    encoded_uuid = quote(user_uuid.strip())
    response = await _request("DELETE", f"/api/users/{encoded_uuid}", expected_status=(200, 204, 404))
    if response.status_code == 404:
        logger.info("Remnawave: пользователь %s не найден при удалении (возможно, уже удалён)", user_uuid)
    elif response.status_code in (200, 204):
        logger.info("Remnawave: пользователь %s успешно удалён (HTTP %s)", user_uuid, response.status_code)
    return True


async def delete_user_on_host(host_name: str, user_uuid: str) -> bool:
    """Удаление пользователя на конкретном хосте, используя конфиг хоста."""
    if not user_uuid:
        return False
    encoded_uuid = quote(user_uuid.strip())
    response = await _request_for_host(host_name, "DELETE", f"/api/users/{encoded_uuid}", expected_status=(200, 204, 404))
    if response.status_code == 404:
        logger.info("Remnawave[%s]: пользователь %s не найден при удалении (возможно, уже удалён)", host_name, user_uuid)
    elif response.status_code in (200, 204):
        logger.info("Remnawave[%s]: пользователь %s успешно удалён (HTTP %s)", host_name, user_uuid, response.status_code)
    return True


async def reset_user_traffic(user_uuid: str) -> bool:
    if not user_uuid:
        return False
    encoded_uuid = quote(user_uuid.strip())
    await _request("POST", f"/api/users/{encoded_uuid}/actions/reset-traffic", expected_status=(200, 204))
    return True


async def update_user_traffic_limit(user_uuid: str, new_traffic_limit_bytes: int, *, host_name: str | None = None) -> bool:
    """Обновляет лимит трафика (trafficLimitBytes) пользователя в Remnawave."""
    if not user_uuid:
        return False
    encoded_uuid = quote(user_uuid.strip())
    payload = {"uuid": user_uuid.strip(), "trafficLimitBytes": int(new_traffic_limit_bytes)}
    if host_name:
        await _request_for_host(host_name, "PATCH", "/api/users", json_payload=payload, expected_status=(200,))
    else:
        await _request("PATCH", "/api/users", json_payload=payload, expected_status=(200,))
    return True


async def set_user_status(user_uuid: str, active: bool) -> bool:
    if not user_uuid:
        return False
    encoded_uuid = quote(user_uuid.strip())
    action = "enable" if active else "disable"
    await _request("POST", f"/api/users/{encoded_uuid}/actions/{action}", expected_status=(200, 204))
    return True


def _extract_used_traffic_bytes(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    for k in ("usedTrafficBytes", "trafficUsedBytes", "traffic_used_bytes", "usedBytes"):
        v = payload.get(k)
        if isinstance(v, (int, float)) and v > 0:
            return int(v)
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return 0


async def disable_user(user_uuid: str, *, host_name: str) -> bool:
    """POST /api/users/{uuid}/actions/disable — скрыть ноду (используется для 💰-premium нод при исчерпании LTE
    или для всех нод при исчерпании основного пула трафика)."""
    if not user_uuid:
        return False
    try:
        encoded_uuid = quote(user_uuid.strip())
        await _request_for_host(host_name, "POST", f"/api/users/{encoded_uuid}/actions/disable", expected_status=(200, 204))
        logger.info("Remnawave[%s]: пользователь %s отключён (disable)", host_name, user_uuid)
        return True
    except Exception as e:
        logger.error("Remnawave[%s]: не удалось отключить пользователя %s: %s", host_name, user_uuid, e, exc_info=True)
        return False


async def enable_user(user_uuid: str, *, host_name: str) -> bool:
    """POST /api/users/{uuid}/actions/enable — вернуть доступ пользователю на конкретном хосте."""
    if not user_uuid:
        return False
    try:
        encoded_uuid = quote(user_uuid.strip())
        await _request_for_host(host_name, "POST", f"/api/users/{encoded_uuid}/actions/enable", expected_status=(200, 204))
        logger.info("Remnawave[%s]: пользователь %s включён (enable)", host_name, user_uuid)
        return True
    except Exception as e:
        logger.error("Remnawave[%s]: не удалось включить пользователя %s: %s", host_name, user_uuid, e, exc_info=True)
        return False


async def set_user_active_squads(user_uuid: str, squad_uuids: list[str], *, host_name: str) -> bool:
    """PATCH /api/users — установить полный список activeInternalSquads пользователя.

    В отличие от enable_user/disable_user (которые полностью открывают/закрывают доступ на хосте),
    это позволяет точечно управлять членством в конкретном сквада (например, отключить только
    LTE-сквад, оставив Base-сквад активным — двухпуловая схема).
    """
    if not user_uuid:
        return False
    try:
        payload = {"uuid": user_uuid, "activeInternalSquads": list(dict.fromkeys(squad_uuids or []))}
        await _request_for_host(host_name, "PATCH", "/api/users", json_payload=payload, expected_status=(200, 201))
        logger.info(
            "Remnawave[%s]: activeInternalSquads пользователя %s обновлены -> %s",
            host_name, user_uuid, payload["activeInternalSquads"],
        )
        return True
    except Exception as e:
        logger.error(
            "Remnawave[%s]: не удалось обновить activeInternalSquads пользователя %s: %s",
            host_name, user_uuid, e, exc_info=True,
        )
        return False


async def remove_squad_from_user(user_uuid: str, squad_uuid: str, *, host_name: str) -> bool:
    """Убрать конкретный сквад из activeInternalSquads пользователя, не трогая остальные сквады."""
    if not user_uuid or not squad_uuid:
        return False
    try:
        current = await get_user_by_uuid(user_uuid, host_name=host_name)
        current_squads = list((current or {}).get("activeInternalSquads") or (current or {}).get("internalSquads") or [])
        if squad_uuid not in current_squads:
            return True  # уже отсутствует — идемпотентно
        new_squads = [s for s in current_squads if s != squad_uuid]
        return await set_user_active_squads(user_uuid, new_squads, host_name=host_name)
    except Exception as e:
        logger.error(
            "Remnawave[%s]: не удалось убрать сквад %s у пользователя %s: %s",
            host_name, squad_uuid, user_uuid, e, exc_info=True,
        )
        return False


async def add_squad_to_user(user_uuid: str, squad_uuid: str, *, host_name: str) -> bool:
    """Добавить конкретный сквад в activeInternalSquads пользователя, не трогая остальные сквады."""
    if not user_uuid or not squad_uuid:
        return False
    try:
        current = await get_user_by_uuid(user_uuid, host_name=host_name)
        current_squads = list((current or {}).get("activeInternalSquads") or (current or {}).get("internalSquads") or [])
        if squad_uuid in current_squads:
            return True  # уже присутствует — идемпотентно
        new_squads = current_squads + [squad_uuid]
        return await set_user_active_squads(user_uuid, new_squads, host_name=host_name)
    except Exception as e:
        logger.error(
            "Remnawave[%s]: не удалось добавить сквад %s пользователю %s: %s",
            host_name, squad_uuid, user_uuid, e, exc_info=True,
        )
        return False


async def get_user_used_traffic(user_uuid: str, *, host_name: str) -> int:
    """Использованный трафик (в байтах) пользователя на конкретном инстансе Remnawave. 0, если данных нет."""
    if not user_uuid:
        return 0
    try:
        payload = await get_user_by_uuid(user_uuid, host_name=host_name)
        return _extract_used_traffic_bytes(payload)
    except Exception as e:
        logger.error("Remnawave[%s]: не удалось получить использованный трафик пользователя %s: %s", host_name, user_uuid, e, exc_info=True)
        return 0


async def reset_user_traffic_on_host(user_uuid: str, *, host_name: str) -> bool:
    """POST /api/users/{uuid}/actions/reset-traffic на конкретном инстансе (host-aware вариант reset_user_traffic)."""
    if not user_uuid:
        return False
    try:
        encoded_uuid = quote(user_uuid.strip())
        await _request_for_host(host_name, "POST", f"/api/users/{encoded_uuid}/actions/reset-traffic", expected_status=(200, 204))
        return True
    except Exception as e:
        logger.error("Remnawave[%s]: не удалось сбросить трафик пользователя %s: %s", host_name, user_uuid, e, exc_info=True)
        return False


def _extract_usage_rows(response: httpx.Response) -> list[dict[str, Any]]:
    """Достаёт список записей UserUsageDto из ответа Remnawave независимо от обёртки ({"response": [...]}, просто [...])."""
    try:
        data = response.json()
    except Exception:
        return []
    if isinstance(data, dict):
        result = data.get("response")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and isinstance(result.get("data"), list):
            return result["data"]
        return []
    if isinstance(data, list):
        return data
    return []


async def get_node_usage_range(
    node_uuid: str,
    start_date: datetime,
    end_date: datetime,
    *,
    host_name: str | None = None,
) -> list[dict[str, Any]]:
    """Legacy per-node usage endpoint: GET /api/nodes/{node_uuid}/usage/range.

    Возвращает расход ВСЕХ пользователей на конкретной ноде за период
    (UserUsageDto: userUuid/user_uuid, nodeUuid/node_uuid, total, date).
    Используется как fallback, если v2.8.0+ bandwidth-stats эндпоинт недоступен.
    """
    if not node_uuid:
        return []
    params = {"start": _to_iso(start_date), "end": _to_iso(end_date)}
    try:
        encoded_uuid = quote(node_uuid.strip())
        path = f"/api/nodes/{encoded_uuid}/usage/range"
        if host_name:
            resp = await _request_for_host(host_name, "GET", path, params=params, expected_status=(200, 404))
        else:
            resp = await _request("GET", path, params=params, expected_status=(200, 404))
        if resp.status_code == 404:
            return []
        return _extract_usage_rows(resp)
    except Exception as e:
        logger.warning("Remnawave: get_node_usage_range(%s) не удался: %s", node_uuid, e)
        return []


async def get_bandwidth_stats_nodes_users(
    node_uuids: list[str],
    start_date: datetime,
    end_date: datetime,
    *,
    host_name: str | None = None,
) -> list[dict[str, Any]]:
    """v2.8.0+ endpoint: POST /api/bandwidth-stats/nodes/users.

    Пер-пользовательская статистика сразу по списку нод за период — один запрос вместо N (по ноде),
    предпочтительный путь при доступности панели версии 2.8.0+.
    """
    if not node_uuids:
        return []
    payload = {
        "nodeUuids": list(dict.fromkeys(node_uuids)),
        "start": _to_iso(start_date),
        "end": _to_iso(end_date),
    }
    try:
        path = "/api/bandwidth-stats/nodes/users"
        if host_name:
            resp = await _request_for_host(host_name, "POST", path, json_payload=payload, expected_status=(200, 404))
        else:
            resp = await _request("POST", path, json_payload=payload, expected_status=(200, 404))
        if resp.status_code == 404:
            return []
        return _extract_usage_rows(resp)
    except Exception as e:
        logger.warning("Remnawave: get_bandwidth_stats_nodes_users не удался (возможно, версия панели < 2.8.0): %s", e)
        return []


async def get_user_lte_usage_bytes(
    user_uuid: str,
    lte_node_uuids: list[str],
    start_date: datetime,
    end_date: datetime,
    *,
    host_name: str | None = None,
) -> int:
    """Суммарный расход конкретного пользователя по нодам LTE-сквада за период.

    Порядок попыток:
      1. v2.8.0+ `POST /api/bandwidth-stats/nodes/users` — один запрос сразу по всем нодам.
      2. Fallback: legacy `GET /api/nodes/{uuid}/usage/range` по каждой ноде отдельно (для старых панелей
         или если основной эндпоинт вернул 404/пусто).
    """
    if not user_uuid or not lte_node_uuids:
        return 0

    node_uuids = list(dict.fromkeys(lte_node_uuids))

    def _sum_for_user(rows: list[dict[str, Any]]) -> int:
        total = 0
        for row in rows or []:
            row_user = row.get("userUuid") or row.get("user_uuid")
            if row_user != user_uuid:
                continue
            val = row.get("total") or row.get("totalBytes") or row.get("bytes") or 0
            try:
                total += int(val)
            except (TypeError, ValueError):
                pass
        return total

    try:
        rows = await get_bandwidth_stats_nodes_users(node_uuids, start_date, end_date, host_name=host_name)
        if rows:
            total = _sum_for_user(rows)
            if total > 0:
                return total
    except Exception as e:
        logger.warning("Remnawave: v2.8.0+ bandwidth-stats недоступен, использую legacy per-node fallback: %s", e)

    total = 0
    for node_uuid in node_uuids:
        try:
            rows = await get_node_usage_range(node_uuid, start_date, end_date, host_name=host_name)
            total += _sum_for_user(rows)
        except Exception as e:
            logger.warning("Remnawave: get_node_usage_range fallback для ноды %s не удался: %s", node_uuid, e)
    return total


def extract_subscription_url(user_payload: dict[str, Any] | None) -> str | None:
    if not user_payload:
        return None
    return user_payload.get("subscriptionUrl")




async def create_or_update_key_on_host(
    host_name: str,
    email: str,
    days_to_add: int | None = None,
    expiry_timestamp_ms: int | None = None,
    *,
    description: str | None = None,
    tag: str | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    hwid_device_limit: int | None = None,
    plan_id: int | None = None,
    include_lte_squad: bool | None = None,
    raise_on_error: bool = False,
) -> dict | None:
    """Legacy совместимость: создаёт/обновляет пользователя Remnawave и возвращает данные по ключу.

    Двухпуловая схема (host_squads): помимо базового `squad_uuid` хоста (legacy-поле на xui_hosts),
    пользователь также добавляется в активный сквад класса 'lte' этого хоста (если он настроен),
    когда это уместно — то есть когда `include_lte_squad=True` ЛИБО у переданного `plan_id` задан
    `lte_limit_bytes > 0`. Если явной информации нет (plan_id не передан и include_lte_squad не задан),
    поведение как раньше — только базовый сквад (без регрессии для старых вызовов).
    """
    try:
        squad = rw_repo.get_squad(host_name)
        if not squad:
            msg = f"Host '{host_name}' not found"
            logger.error("Remnawave: не найден сквад/хост '%s'", host_name)
            if raise_on_error:
                raise RemnawaveAPIError(msg)
            return None
        squad_uuid = (squad.get('squad_uuid') or '').strip()
        if not squad_uuid:
            msg = f"Host '{host_name}' has no squad_uuid"
            logger.error("Remnawave: сквад '%s' не имеет squad_uuid", host_name)
            if raise_on_error:
                raise RemnawaveAPIError(msg)
            return None

        # Определяем, нужно ли добавить пользователя в LTE-сквад этого хоста (двухпуловая схема).
        want_lte = include_lte_squad
        if want_lte is None:
            want_lte = False
            if plan_id is not None:
                try:
                    plan = rw_repo.get_plan_by_id(int(plan_id))
                    want_lte = bool(plan) and int(plan.get('lte_limit_bytes') or 0) > 0
                except Exception:
                    want_lte = False

        extra_squad_uuids: list[str] = []
        if want_lte:
            try:
                lte_squad = rw_repo.get_squad_by_class(host_name, 'lte')
                if lte_squad and lte_squad.get('squad_uuid'):
                    lte_uuid = str(lte_squad['squad_uuid']).strip()
                    if lte_uuid and lte_uuid != squad_uuid:
                        extra_squad_uuids.append(lte_uuid)
            except Exception as e:
                logger.warning("Remnawave: не удалось определить LTE-сквад для хоста '%s': %s", host_name, e)

        if expiry_timestamp_ms is not None:
            target_dt = datetime.fromtimestamp(expiry_timestamp_ms / 1000, tz=timezone.utc)
        else:
            days = days_to_add if days_to_add is not None else int(rw_repo.get_setting('default_extension_days') or 30)
            if days <= 0:
                days = 1

            # IMPORTANT: extend from the current expiry date (if it's in the future),
            # otherwise extend from "now". This prevents losing remaining days when user renews early.
            base_dt = datetime.now(timezone.utc)
            try:
                existing = await get_user_by_email(email, host_name=host_name)
            except Exception:
                existing = None
            if isinstance(existing, dict):
                expire_at_str = existing.get('expireAt') or existing.get('expire_at') or existing.get('expire_at_str')
                if expire_at_str:
                    try:
                        exp_dt = datetime.fromisoformat(str(expire_at_str).replace('Z', '+00:00'))
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                        if exp_dt > base_dt:
                            base_dt = exp_dt
                    except Exception:
                        pass

            target_dt = base_dt + timedelta(days=days)
        traffic_limit_bytes_effective = traffic_limit_bytes if traffic_limit_bytes is not None else squad.get('default_traffic_limit_bytes')
        traffic_limit_strategy_effective = traffic_limit_strategy if traffic_limit_strategy is not None else (squad.get('default_traffic_strategy') or 'NO_RESET')

        user_payload = await ensure_user(
            host_name=host_name,
            email=email,
            squad_uuid=squad_uuid,
            expire_at=target_dt,
            traffic_limit_bytes=traffic_limit_bytes_effective,
            traffic_limit_strategy=traffic_limit_strategy_effective,
            description=description,
            tag=tag,
            username=email.split('@')[0] if email else None,
            hwid_device_limit=hwid_device_limit,
            extra_squad_uuids=extra_squad_uuids or None,
        )

        subscription_url = extract_subscription_url(user_payload) or ''
        expire_at_str = user_payload.get('expireAt')
        try:
            expire_dt = datetime.fromisoformat(expire_at_str.replace('Z', '+00:00')) if expire_at_str else target_dt
        except Exception:
            expire_dt = target_dt
        expiry_ts_ms = int(expire_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

        return {
            'client_uuid': str(user_payload.get('uuid') or user_payload.get('id') or ''),
            'short_uuid': user_payload.get('shortUuid'),
            'email': email,
            'host_name': squad.get('host_name') or host_name,
            'squad_uuid': squad_uuid,
            'subscription_url': subscription_url,
            'traffic_limit_bytes': user_payload.get('trafficLimitBytes'),
            'traffic_limit_strategy': user_payload.get('trafficLimitStrategy'),
            'expiry_timestamp_ms': expiry_ts_ms,
            'connection_string': subscription_url,
        }
    except RemnawaveAPIError as exc:
        logger.error("Remnawave: ошибка create_or_update_key_on_host %s/%s: %s", host_name, email, exc)
        if raise_on_error:
            raise
    except Exception:
        logger.exception("Remnawave: непредвиденная ошибка create_or_update_key_on_host для %s/%s", host_name, email)
        if raise_on_error:
            raise
    return None


async def get_key_details_from_host(key_data: dict) -> dict | None:
    email = key_data.get('key_email') or key_data.get('email')
    user_uuid = key_data.get('remnawave_user_uuid') or key_data.get('xui_client_uuid')
    try:
        user_payload = None
        host_name = key_data.get('host_name')
        if not host_name:

            sq = key_data.get('squad_uuid') or key_data.get('squadUuid')
            if sq:
                squad = rw_repo.get_squad(sq)
                host_name = squad.get('host_name') if squad else None
        if email:
            user_payload = await get_user_by_email(email, host_name=host_name)
        if not user_payload and user_uuid:
            user_payload = await get_user_by_uuid(user_uuid, host_name=host_name)
        if not user_payload:
            logger.warning("Remnawave: не найден пользователь для ключа %s", key_data.get('key_id'))
            return None
        subscription_url = extract_subscription_url(user_payload)
        return {
            'connection_string': subscription_url or '',
            'subscription_url': subscription_url,
            'user': user_payload,
        }
    except RemnawaveAPIError as exc:
        logger.error("Remnawave: ошибка получения деталей ключа %s: %s", key_data.get('key_id'), exc)
    except Exception:
        logger.exception("Remnawave: непредвиденная ошибка получения деталей ключа %s", key_data.get('key_id'))
    return None


async def delete_client_on_host(host_name: str, client_email: str) -> bool:
    try:

        user_payload = await get_user_by_email(client_email, host_name=host_name)
        if not user_payload:
            logger.info("Remnawave: пользователь %s уже отсутствует", client_email)
            return True
        if isinstance(user_payload, list):

            user_payload = next((u for u in user_payload if isinstance(u, dict)), None)
        user_uuid = str(user_payload.get('uuid') or user_payload.get('id') or '') if isinstance(user_payload, dict) else None
        if not user_uuid:
            logger.warning("Remnawave: нет uuid для пользователя %s", client_email)
            return False
        logger.info("Remnawave: удаляю пользователя %s (%s) на '%s'...", client_email, user_uuid, host_name)
        await delete_user_on_host(host_name, user_uuid)
        logger.info("Remnawave: пользователь %s (%s) успешно удалён на '%s'", client_email, user_uuid, host_name)
        return True
    except RemnawaveAPIError as exc:
        logger.error("Remnawave: ошибка удаления пользователя %s: %s", client_email, exc)
    except Exception:
        logger.exception("Remnawave: непредвиденная ошибка удаления пользователя %s", client_email)
    return False
