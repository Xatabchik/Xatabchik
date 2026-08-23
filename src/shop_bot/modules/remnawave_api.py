import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, NamedTuple, Sequence
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


# Remnawave backend-contract: enable/disable уже в нужном состоянии — HTTP 400.
# A030 User already enabled, A029 User already disabled.
_ALREADY_ENABLED = ("A030", "already enabled")
_ALREADY_DISABLED = ("A029", "already disabled")


def _detail_is_already_in_desired_state(detail, *, want_enabled: bool) -> bool:
    """True, если панель ответила, что пользователь уже enable/disable — это успех."""
    code, phrase = _ALREADY_ENABLED if want_enabled else _ALREADY_DISABLED
    if isinstance(detail, dict):
        err = str(detail.get("errorCode") or "").strip().upper()
        if err == code:
            return True
        text = str(detail.get("message") or "")
    else:
        text = str(detail or "")
    return code in text or phrase in text.lower()


def _is_already_in_desired_state(exc: BaseException, *, want_enabled: bool) -> bool:
    return _detail_is_already_in_desired_state(str(exc or ""), want_enabled=want_enabled)


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
            if inner is None:
                inner = payload.get("list")
            return inner if inner is not None else payload
        return payload
    except RemnawaveAPIError:
        return None
    except Exception:
        logger.exception("Remnawave: ошибка get_hwid_devices_for_user(%s)", user_uuid)
        return None


async def delete_hwid_device(
    user_uuid: str | None,
    hwid: str,
    *,
    host_name: str | None = None,
    user_id: int | None = None,
) -> bool:
    """Удалить одно HWID-устройство пользователя через API."""
    if (not user_uuid and user_id is None) or not hwid:
        return False

    try:
        payload: dict[str, Any] = {"hwid": str(hwid).strip()}
        # New Remnawave: userId (int); old Remnawave: userUuid (str)
        if user_id is not None:
            payload["userId"] = int(user_id)
        if user_uuid:
            payload["userUuid"] = str(user_uuid).strip()
        
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

        _current_uuid = current.get("uuid")   # old Remnawave field
        _current_id = current.get("id")         # new Remnawave field (int)
        _current_username = current.get("username")
        logger.info(
            "Remnawave: найден пользователь %s (id=%s) на '%s' — обновляю срок до %s",
            email,
            _current_id or _current_uuid,
            host_name,
            expire_iso,
        )

        payload = {
            "status": "ACTIVE",
            "expireAt": expire_iso,
            "activeInternalSquads": active_squads,
            "email": email,
        }
        # Send all known identifier fields for compat with old (uuid) and new (id/username) Remnawave
        if _current_uuid:
            payload["uuid"] = _current_uuid
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
            _existing_uuid = _existing.get("uuid")
            _existing_id = _existing.get("id")
            if _existing_uuid:
                _patch["uuid"] = _existing_uuid
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
    try:
        resp = await _request(
            "POST", f"/api/users/{encoded_uuid}/actions/{action}",
            expected_status=(200, 204, 400),
        )
        if getattr(resp, "status_code", 200) == 400:
            try:
                detail = resp.json()
            except Exception:
                detail = getattr(resp, "text", "") or ""
            if _detail_is_already_in_desired_state(detail, want_enabled=active):
                logger.info("Remnawave: пользователь %s уже %s — пропускаем", user_uuid, action)
                return True
            raise RemnawaveAPIError(f"Remnawave API request failed: 400 {detail}")
        return True
    except RemnawaveAPIError as e:
        if _is_already_in_desired_state(e, want_enabled=active):
            logger.info("Remnawave: пользователь %s уже %s — пропускаем", user_uuid, action)
            return True
        raise


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
        resp = await _request_for_host(
            host_name, "POST", f"/api/users/{encoded_uuid}/actions/disable",
            expected_status=(200, 204, 400),
        )
        if getattr(resp, "status_code", 200) == 400:
            try:
                detail = resp.json()
            except Exception:
                detail = getattr(resp, "text", "") or ""
            if _detail_is_already_in_desired_state(detail, want_enabled=False):
                logger.info("Remnawave[%s]: пользователь %s уже отключён — пропускаем", host_name, user_uuid)
                return True
            logger.error("Remnawave[%s]: не удалось отключить пользователя %s: %s", host_name, user_uuid, detail)
            return False
        logger.info("Remnawave[%s]: пользователь %s отключён (disable)", host_name, user_uuid)
        return True
    except Exception as e:
        if _is_already_in_desired_state(e, want_enabled=False):
            logger.info("Remnawave[%s]: пользователь %s уже отключён — пропускаем", host_name, user_uuid)
            return True
        logger.error("Remnawave[%s]: не удалось отключить пользователя %s: %s", host_name, user_uuid, e, exc_info=True)
        return False


async def enable_user(user_uuid: str, *, host_name: str) -> bool:
    """POST /api/users/{uuid}/actions/enable — вернуть доступ пользователю на конкретном хосте."""
    if not user_uuid:
        return False
    try:
        encoded_uuid = quote(user_uuid.strip())
        resp = await _request_for_host(
            host_name, "POST", f"/api/users/{encoded_uuid}/actions/enable",
            expected_status=(200, 204, 400),
        )
        if getattr(resp, "status_code", 200) == 400:
            try:
                detail = resp.json()
            except Exception:
                detail = getattr(resp, "text", "") or ""
            if _detail_is_already_in_desired_state(detail, want_enabled=True):
                logger.info("Remnawave[%s]: пользователь %s уже включён — пропускаем", host_name, user_uuid)
                return True
            logger.error("Remnawave[%s]: не удалось включить пользователя %s: %s", host_name, user_uuid, detail)
            return False
        logger.info("Remnawave[%s]: пользователь %s включён (enable)", host_name, user_uuid)
        return True
    except Exception as e:
        if _is_already_in_desired_state(e, want_enabled=True):
            logger.info("Remnawave[%s]: пользователь %s уже включён — пропускаем", host_name, user_uuid)
            return True
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
        # PATCH /api/users идентифицирует пользователя по `uuid` (2.8.1) либо по числовому
        # `id` (3.3.2, где поля uuid у пользователя нет вовсе). Что именно хранится в
        # vpn_keys.remnawave_user_uuid, видно по самому значению.
        stored = str(user_uuid).strip()
        payload: dict[str, Any] = {"id": int(stored)} if stored.isdigit() else {"uuid": stored}
        payload["activeInternalSquads"] = list(dict.fromkeys(squad_uuids or []))
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


def extract_active_squad_uuids(user_payload: dict[str, Any] | None) -> list[str]:
    """UUID активных internal-сквадов пользователя из ответа панели.

    ВАЖНО: `activeInternalSquads` в ответе — массив ОБЪЕКТОВ (`{uuid, name, ...}`), и в
    2.8.1, и в 3.3.2, тогда как `PATCH /api/users` принимает массив строк-UUID. Сравнение
    строки с объектами всегда давало «сквада нет», из-за чего remove_squad_from_user
    возвращал ложный успех и LTE-сквад не снимался при исчерпании лимита.
    """
    raw = (user_payload or {}).get("activeInternalSquads")
    if raw is None:
        raw = (user_payload or {}).get("internalSquads") or []
    result: list[str] = []
    for item in raw or []:
        if isinstance(item, str):
            uuid_value = item.strip()
        elif isinstance(item, dict):
            uuid_value = str(item.get("uuid") or item.get("squadUuid") or "").strip()
        else:
            continue
        if uuid_value and uuid_value not in result:
            result.append(uuid_value)
    return result


async def remove_squad_from_user(user_uuid: str, squad_uuid: str, *, host_name: str) -> bool:
    """Убрать конкретный сквад из activeInternalSquads пользователя, не трогая остальные сквады."""
    if not user_uuid or not squad_uuid:
        return False
    try:
        current = await get_user_by_uuid(user_uuid, host_name=host_name)
        current_squads = extract_active_squad_uuids(current)
        if squad_uuid not in current_squads:
            logger.info(
                "Remnawave[%s]: сквад %s уже отсутствует у пользователя %s (активные: %s)",
                host_name, squad_uuid, user_uuid, current_squads,
            )
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
        current_squads = extract_active_squad_uuids(current)
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


# ==========================================================================================
# Точный учёт LTE-трафика по конкретным нодам сквада.
#
# Матрица путей снята с контракта remnawave/backend по тегам 2.8.1 и 3.3.2 (см. описание PR):
#
#   GET /api/internal-squads/{squadUuid}/accessible-nodes
#       2.8.1 ✅ | 3.3.2 ✅ — схема ответа идентична.
#
# `host_name` во всех функциях ниже — исключительно ключ маршрутизации к панели
# (_request_for_host → _load_config_for_host → base_url/token). Он НЕ идентифицирует ноду
# или сквад, поэтому кэш скоупится по squad_uuid, а решение о поддержке пути — по base_url
# инстанса панели.
# ==========================================================================================


class RemnawavePathUnsupportedError(RemnawaveAPIError):
    """Путь не поддерживается этой версией панели (404 / 400 / 422 на валидации параметра).

    Отделено от сетевых и 5xx-ошибок намеренно: «версия не умеет этот путь» — повод
    попробовать следующего кандидата в цепочке, а «панель недоступна» — повод пропустить
    ключ на этом проходе и НЕ записывать нулевой расход.
    """


_SQUAD_NODES_TTL_SECONDS = 600  # 10 минут
# Короткий негативный кэш: битый/несуществующий squad_uuid не должен опрашиваться
# заново на каждый ключ этого сквада (воркер ходит раз в dual_limit_interval_sec).
_SQUAD_NODES_FAILURE_TTL_SECONDS = 120
_squad_nodes_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_squad_nodes_failures: dict[str, tuple[float, str]] = {}
_squad_nodes_cache_lock = threading.Lock()


def invalidate_squad_nodes_cache(squad_uuid: str | None = None) -> None:
    """Сбросить кэш нод сквада (целиком или по одному squad_uuid), включая негативный."""
    with _squad_nodes_cache_lock:
        if squad_uuid:
            key = str(squad_uuid).strip()
            _squad_nodes_cache.pop(key, None)
            _squad_nodes_failures.pop(key, None)
        else:
            _squad_nodes_cache.clear()
            _squad_nodes_failures.clear()


async def _request_optional_path(
    host_name: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_payload: dict[str, Any] | None = None,
) -> httpx.Response | None:
    """Запрос к пути, которого может не быть в этой версии панели.

    Возвращает None, если панель ответила 404 (маршрута нет) либо 400/422 (маршрут есть,
    но параметр другого типа — например, числовой userId вместо UUID в 3.3.2 против 2.8.1).
    Сетевые ошибки и 5xx пробрасываются как RemnawaveAPIError/httpx-исключения.
    """
    response = await _request_for_host(
        host_name,
        method,
        path,
        params=params,
        json_payload=json_payload,
        expected_status=(200, 400, 404, 422),
    )
    if response.status_code in (400, 404, 422):
        logger.debug(
            "Remnawave[%s]: путь %s не поддерживается (%s) — пробую следующего кандидата",
            host_name, path, response.status_code,
        )
        return None
    return response


async def get_squad_accessible_nodes(
    squad_uuid: str,
    *,
    host_name: str,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Ноды, доступные через internal squad: `GET /api/internal-squads/{uuid}/accessible-nodes`.

    Возвращает список словарей нод (`uuid`, `nodeName`, `countryCode`, `configProfileUuid`,
    `configProfileName`, `activeInbounds`) — схема подтверждена для 2.8.1 и 3.3.2.

    Пустой список означает «у сквада действительно нет доступных нод». Любой сбой запроса —
    исключение, а не пустой список: иначе «не удалось узнать» было бы неотличимо от «нод нет»
    и привело бы к нулевому расходу и ложному «лимит не исчерпан».

    Кэш TTL 10 минут с ключом `squad_uuid` (не `host_name`: два разных host_name, смотрящих
    в одну панель, обязаны переиспользовать один и тот же список нод).
    """
    squad_uuid_n = (squad_uuid or "").strip()
    if not squad_uuid_n:
        return []

    if use_cache:
        with _squad_nodes_cache_lock:
            cached = _squad_nodes_cache.get(squad_uuid_n)
        if cached and (time.monotonic() - cached[0]) < _SQUAD_NODES_TTL_SECONDS:
            return list(cached[1])
        # Негативный кэш: если панель уже ответила ошибкой на этот сквад, не дёргаем её
        # заново для каждого ключа того же сквада — иначе один битый squad_uuid даёт
        # N запросов за проход воркера. Ошибка при этом всё равно пробрасывается.
        with _squad_nodes_cache_lock:
            failed = _squad_nodes_failures.get(squad_uuid_n)
        if failed and (time.monotonic() - failed[0]) < _SQUAD_NODES_FAILURE_TTL_SECONDS:
            raise RemnawaveAPIError(failed[1])

    encoded = quote(squad_uuid_n)
    path = f"/api/internal-squads/{encoded}/accessible-nodes"

    def _remember_failure(message: str) -> RemnawaveAPIError:
        with _squad_nodes_cache_lock:
            _squad_nodes_failures[squad_uuid_n] = (time.monotonic(), message)
        logger.warning(message)
        return RemnawaveAPIError(message)

    try:
        # 401/403 и 404 разбираем отдельно: у них принципиально разные причины и разные
        # действия администратора, а по тексту «500 {...}» это неотличимо.
        response = await _request_for_host(
            host_name, "GET", path, expected_status=(200, 401, 403, 404)
        )
    except Exception as e:
        raise _remember_failure(
            f"Remnawave[{host_name}]: не удалось получить ноды сквада {squad_uuid_n}: {e}"
        ) from e

    if response.status_code in (401, 403):
        raise _remember_failure(
            f"Remnawave[{host_name}]: панель отклонила запрос нод сквада {squad_uuid_n} "
            f"({response.status_code}). Это авторизация, а не отсутствие сквада: проверьте "
            "API-токен хоста и его скоупы (нужны права на чтение internal-squads / "
            "accessible-nodes). Токен из сессии веб-панели живёт недолго — нужен постоянный "
            "API-токен."
        )
    if response.status_code == 404:
        raise _remember_failure(
            f"Remnawave[{host_name}]: сквад {squad_uuid_n} не найден на панели (404). "
            "Проверьте, что этот UUID есть в GET /api/internal-squads — это должен быть "
            "internal squad, а не external-сквад и не config profile."
        )

    with _squad_nodes_cache_lock:
        _squad_nodes_failures.pop(squad_uuid_n, None)
    payload = response.json()
    body = payload.get("response") if isinstance(payload, dict) else None
    raw_nodes = (body or {}).get("accessibleNodes") if isinstance(body, dict) else None
    if not isinstance(raw_nodes, list):
        raise RemnawaveAPIError(
            f"Remnawave: неожиданный ответ accessible-nodes для сквада {squad_uuid_n}"
        )

    nodes: list[dict[str, Any]] = []
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_uuid = str(item.get("uuid") or "").strip()
        if not node_uuid:
            continue
        nodes.append(
            {
                "uuid": node_uuid,
                "node_name": item.get("nodeName") or item.get("name"),
                "country_code": item.get("countryCode"),
                "config_profile_uuid": item.get("configProfileUuid"),
                "active_inbounds": item.get("activeInbounds") or [],
            }
        )

    with _squad_nodes_cache_lock:
        _squad_nodes_cache[squad_uuid_n] = (time.monotonic(), list(nodes))
    return nodes


async def get_squad_nodes_for_class(host_name: str, squad_class: str) -> list[dict[str, Any]]:
    """Ноды активного сквада заданного класса ('lte'/'base') у хоста.

    Пустой список, если сквад такого класса не настроен — это легитимная конфигурация
    (лог info, не ошибка). Сбой обращения к панели пробрасывается наверх.
    """
    if not host_name:
        return []
    try:
        squad_cfg = rw_repo.get_squad_by_class(host_name, squad_class)
    except Exception as e:
        logger.error(
            "Remnawave[%s]: не удалось прочитать сквад класса '%s' из БД: %s",
            host_name, squad_class, e,
        )
        raise RemnawaveAPIError(f"Не удалось прочитать сквад класса '{squad_class}'") from e
    squad_uuid = str((squad_cfg or {}).get("squad_uuid") or "").strip()
    if not squad_uuid:
        logger.info(
            "Remnawave[%s]: сквад класса '%s' не настроен — список нод пуст.",
            host_name, squad_class,
        )
        return []
    return await get_squad_accessible_nodes(squad_uuid, host_name=host_name)


async def get_lte_nodes_for_host(host_name: str) -> list[dict[str, Any]]:
    """Ноды активного LTE-сквада хоста (с именами — для карточки ключа и снапшотов)."""
    return await get_squad_nodes_for_class(host_name, "lte")


async def get_lte_node_uuids_for_host(host_name: str) -> list[str]:
    """UUID нод активного LTE-сквада хоста.

    `[]` — LTE-сквад не настроен (легитимно). Сбой обращения к панели — исключение.
    """
    return [n["uuid"] for n in await get_lte_nodes_for_host(host_name)]


class NodeUsage(NamedTuple):
    """Расход пользователя по нодам за период + идентификатор сработавшего пути API."""

    per_node: dict[str, int]
    path: str


# Кэш решения «какой путь поддерживает эта панель» — на уровне ИНСТАНСА панели (base_url),
# а не host_name: два host_name с одинаковыми base_url/token — это одна панель, и повторно
# зондировать её незачем. TTL позволяет подхватить апгрейд панели без рестарта бота.
_USAGE_PATH_TTL_SECONDS = 3600
_usage_path_state: dict[str, dict[str, Any]] = {}
_usage_path_lock = threading.Lock()

# Идентификаторы путей цепочки (порядок = приоритет).
USAGE_PATH_SQUAD_SCOPED = "squad_scoped"          # 3.3.2
USAGE_PATH_USER_BY_ID = "user_by_id"              # 3.3.2
USAGE_PATH_USER_BY_UUID = "user_by_uuid"          # 2.8.1
USAGE_PATH_USER_LEGACY = "user_legacy_by_uuid"    # 2.8.1
USAGE_PATH_LEGACY_WRAPPER = "legacy_wrapper"      # исторический get_user_lte_usage_bytes


def _panel_instance_key(host_name: str) -> str:
    """Идентификатор инстанса панели (base_url) для кэша поддержки путей."""
    try:
        return (_load_config_for_host(host_name).get("base_url") or "").strip().rstrip("/")
    except Exception:
        return ""


def reset_usage_path_cache() -> None:
    """Сбросить кэш решений о поддерживаемых путях (используется в тестах)."""
    with _usage_path_lock:
        _usage_path_state.clear()


def _usage_path_unsupported(instance_key: str, path: str) -> bool:
    if not instance_key:
        return False
    with _usage_path_lock:
        state = _usage_path_state.get(instance_key)
        if not state:
            return False
        if (time.monotonic() - state.get("ts", 0.0)) >= _USAGE_PATH_TTL_SECONDS:
            _usage_path_state.pop(instance_key, None)
            return False
        return path in state.get("unsupported", set())


def _mark_usage_path_unsupported(instance_key: str, path: str) -> None:
    if not instance_key:
        return
    with _usage_path_lock:
        state = _usage_path_state.setdefault(instance_key, {"unsupported": set(), "ts": time.monotonic()})
        if (time.monotonic() - state.get("ts", 0.0)) >= _USAGE_PATH_TTL_SECONDS:
            state["unsupported"] = set()
            state["ts"] = time.monotonic()
        state["unsupported"].add(path)


def _as_api_date(dt: datetime) -> str:
    """Оба семейства эндпоинтов ждут дату в формате YYYY-MM-DD."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _to_int_bytes(value: Any) -> int:
    try:
        if isinstance(value, bool):
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.strip():
            return int(float(value.strip()))
    except (TypeError, ValueError):
        return 0
    return 0


async def resolve_panel_user_id(
    user_uuid: str,
    *,
    host_name: str,
    user_payload: dict[str, Any] | None = None,
) -> int | None:
    """Числовой `id` пользователя панели (нужен путям 3.3.2).

    В 3.3.2 у пользователя вообще нет поля `uuid` (только `id` и `shortUuid`), поэтому
    `vpn_keys.remnawave_user_uuid` там хранит уже числовой id — в этом случае берём его
    напрямую, без лишнего запроса к панели (который к тому же может не отвечать).
    В 2.8.1 хранится UUID, и числовой id приходится доставать из payload.
    """
    stored = (user_uuid or "").strip()
    if stored.isdigit():
        return int(stored)
    payload = user_payload
    if payload is None:
        payload = await get_user_by_uuid(user_uuid, host_name=host_name)
    raw = (payload or {}).get("id")
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _sum_squad_scoped_days(payload: Any, allowed_nodes: set[str] | None) -> dict[str, int]:
    """3.3.2: `{response: {days: [{date, nodes: [{uuid, totalBytes}]}]}}` -> сумма по нодам."""
    body = payload.get("response") if isinstance(payload, dict) else None
    days = (body or {}).get("days") if isinstance(body, dict) else None
    per_node: dict[str, int] = {}
    for day in days or []:
        for node in (day or {}).get("nodes") or []:
            node_uuid = str((node or {}).get("uuid") or "").strip()
            if not node_uuid or (allowed_nodes is not None and node_uuid not in allowed_nodes):
                continue
            per_node[node_uuid] = per_node.get(node_uuid, 0) + _to_int_bytes(node.get("totalBytes"))
    return per_node


def _sum_user_series(payload: Any, allowed_nodes: set[str]) -> dict[str, int]:
    """2.8.1/3.3.2: `{response: {series|topNodes: [{uuid, total}]}}` -> расход по нодам.

    `uuid` в series/topNodes — это UUID ноды; фильтруем по нодам LTE-сквада, т.к. эндпоинт
    отдаёт расход пользователя по ВСЕМ нодам.
    """
    body = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(body, dict):
        return {}
    per_node: dict[str, int] = {}
    for key in ("series", "topNodes"):
        for row in body.get(key) or []:
            node_uuid = str((row or {}).get("uuid") or "").strip()
            if not node_uuid or node_uuid not in allowed_nodes:
                continue
            value = _to_int_bytes(row.get("total"))
            # series и topNodes описывают один и тот же период — берём максимум, а не сумму,
            # чтобы не удвоить расход, если присутствуют оба списка.
            per_node[node_uuid] = max(per_node.get(node_uuid, 0), value)
    return per_node


def _sum_legacy_rows(payload: Any, user_uuid: str, allowed_nodes: set[str]) -> dict[str, int]:
    """2.8.1 legacy: плоский список `{userUuid, nodeUuid, total, date}` -> расход по нодам."""
    rows = payload.get("response") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return {}
    per_node: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_user = str(row.get("userUuid") or row.get("user_uuid") or "").strip()
        if row_user != user_uuid:
            continue
        node_uuid = str(row.get("nodeUuid") or row.get("node_uuid") or "").strip()
        if not node_uuid or node_uuid not in allowed_nodes:
            continue
        per_node[node_uuid] = per_node.get(node_uuid, 0) + _to_int_bytes(row.get("total"))
    return per_node


async def get_user_node_usage_for_squad(
    user_uuid: str,
    *,
    host_name: str,
    squad_uuid: str,
    node_uuids: Sequence[str],
    start_date: datetime,
    end_date: datetime,
    panel_user_id: int | None = None,
    user_payload: dict[str, Any] | None = None,
) -> NodeUsage:
    """Расход пользователя по нодам LTE-сквада за период — с разбивкой по нодам.

    Версионно-толерантная цепочка (подтверждена по контракту 2.8.1 и 3.3.2):

      1. `GET /api/bandwidth-stats/internal-squads/{squadUuid}/users/{userId}/usage`
         — 3.3.2, числовой userId, ответ `days[].nodes[]{uuid,totalBytes}`, уже
         заскоупленный нодами сквада. В 2.8.1 секции INTERNAL_SQUADS нет -> 404.
      2. `GET /api/bandwidth-stats/users/{userId}` — 3.3.2 (числовой id) и
      3. `GET /api/bandwidth-stats/users/{userUuid}` — 2.8.1 (UUID): один и тот же
         маршрут с разным типом параметра, ответ `series[]/topNodes[]{uuid,total}` по
         всем нодам, фильтруем списком нод сквада.
      4. `GET /api/bandwidth-stats/users/{userUuid}/legacy` — 2.8.1, плоские строки
         `{userUuid,nodeUuid,total,date}`. В 3.3.2 секции LEGACY нет -> 404.
      5. Исторический `get_user_lte_usage_bytes` — оставлен как последний кандидат без
         изменения его логики выбора пути. Разбивку он дать не может (только сумму), а
         оба его эндпоинта на 2.8.1/3.3.2 неприменимы (`/api/nodes/{uuid}/usage/range`
         отсутствует в обеих версиях, а у `POST /bandwidth-stats/nodes/users` другое тело
         и график вместо строк), поэтому его нулевой результат трактуется как «данных
         нет», а не как «расход нулевой».

    Ошибки: 404/400/422 -> путь/тип параметра не поддерживается версией, пробуем
    следующего кандидата и запоминаем решение по инстансу панели. Сетевая ошибка или 5xx
    -> строгий fail-safe: пробрасываем RemnawaveAPIError, чтобы вызывающий пропустил ключ
    и НЕ записал нулевой расход. Если ни один путь не дал данных -> RemnawavePathUnsupportedError.
    """
    user_uuid_n = (user_uuid or "").strip()
    allowed = {str(u).strip() for u in (node_uuids or []) if str(u).strip()}
    if not user_uuid_n or not allowed:
        return NodeUsage({}, "none")

    instance_key = _panel_instance_key(host_name)
    # Путь, который ответил корректно (пусть и без данных): отличает «расхода нет»
    # от «панель не умеет ни одного пути».
    answered_path: str | None = None
    start_txt = _as_api_date(start_date)
    # Верхнюю границу берём на сутки вперёд: эндпоинты статистики оперируют ДАТАМИ, а не
    # моментами времени, и панель агрегирует расход по своему часовому поясу. Без запаса
    # расход текущих суток мог не попасть в диапазон при расхождении TZ бота и панели.
    end_txt = _as_api_date(end_date + timedelta(days=1))
    top_limit = max(20, len(allowed) + 5)
    squad_uuid_n = (squad_uuid or "").strip()

    async def _numeric_id() -> int | None:
        nonlocal panel_user_id
        if panel_user_id is None:
            panel_user_id = await resolve_panel_user_id(
                user_uuid_n, host_name=host_name, user_payload=user_payload
            )
        return panel_user_id

    # 1. squad-scoped (3.3.2)
    if squad_uuid_n and not _usage_path_unsupported(instance_key, USAGE_PATH_SQUAD_SCOPED):
        numeric_id = await _numeric_id()
        if numeric_id is None:
            _mark_usage_path_unsupported(instance_key, USAGE_PATH_SQUAD_SCOPED)
        else:
            response = await _request_optional_path(
                host_name,
                "GET",
                f"/api/bandwidth-stats/internal-squads/{quote(squad_uuid_n)}/users/{numeric_id}/usage",
                params={"start": start_txt, "end": end_txt},
            )
            if response is None:
                _mark_usage_path_unsupported(instance_key, USAGE_PATH_SQUAD_SCOPED)
            else:
                # Ответ этого пути авторитетен и когда он пустой: эндпоинт заскоуплен
                # нодами сквада и зануляет все дни диапазона, поэтому «нет строк» здесь
                # означает «расхода не было», а не «путь не дал данных». Остальные
                # кандидаты нужны только если самого пути на панели нет (404).
                return NodeUsage(
                    _sum_squad_scoped_days(response.json(), allowed), USAGE_PATH_SQUAD_SCOPED
                )

    # 2/3. per-user разбивка по нодам: 3.3.2 — числовой id, 2.8.1 — UUID.
    tried_idents: set[str] = set()
    for path_id in (USAGE_PATH_USER_BY_ID, USAGE_PATH_USER_BY_UUID):
        if _usage_path_unsupported(instance_key, path_id):
            continue
        if path_id == USAGE_PATH_USER_BY_ID:
            ident: Any = await _numeric_id()
            if ident is None:
                _mark_usage_path_unsupported(instance_key, path_id)
                continue
        else:
            ident = quote(user_uuid_n)
        # Когда в ключе хранится уже числовой id (3.3.2), оба кандидата дают один и тот же
        # URL — второй запрос был бы точной копией первого.
        if str(ident) in tried_idents:
            continue
        tried_idents.add(str(ident))
        response = await _request_optional_path(
            host_name,
            "GET",
            f"/api/bandwidth-stats/users/{ident}",
            params={"start": start_txt, "end": end_txt, "topNodesLimit": top_limit},
        )
        if response is None:
            _mark_usage_path_unsupported(instance_key, path_id)
            continue
        answered_path = answered_path or path_id
        per_node = _sum_user_series(response.json(), allowed)
        if per_node:
            return NodeUsage(per_node, path_id)

    # 4. legacy per-user (2.8.1)
    if not _usage_path_unsupported(instance_key, USAGE_PATH_USER_LEGACY):
        response = await _request_optional_path(
            host_name,
            "GET",
            f"/api/bandwidth-stats/users/{quote(user_uuid_n)}/legacy",
            params={"start": start_txt, "end": end_txt},
        )
        if response is None:
            _mark_usage_path_unsupported(instance_key, USAGE_PATH_USER_LEGACY)
        else:
            answered_path = answered_path or USAGE_PATH_USER_LEGACY
            per_node = _sum_legacy_rows(response.json(), user_uuid_n, allowed)
            if per_node:
                return NodeUsage(per_node, USAGE_PATH_USER_LEGACY)

    # 5. исторический путь — только как сумма, без разбивки. Он неприменим ни к 2.8.1, ни к
    # 3.3.2 (см. матрицу), поэтому после первой неудачи помечаем его неподдерживаемым, чтобы
    # не долбить панель заведомо неверным запросом на каждом ключе и каждом проходе.
    if not _usage_path_unsupported(instance_key, USAGE_PATH_LEGACY_WRAPPER):
        total = await get_user_lte_usage_bytes(
            user_uuid_n, list(allowed), start_date, end_date, host_name=host_name
        )
        if total > 0:
            logger.warning(
                "Remnawave[%s]: разбивка по нодам недоступна, использован исторический "
                "get_user_lte_usage_bytes (сумма %s байт распределена на одну запись)",
                host_name, total,
            )
            # Разбивки нет — кладём сумму на первую ноду сквада, чтобы не потерять расход.
            return NodeUsage({sorted(allowed)[0]: total}, USAGE_PATH_LEGACY_WRAPPER)
        _mark_usage_path_unsupported(instance_key, USAGE_PATH_LEGACY_WRAPPER)

    if answered_path:
        # Панель ответила по рабочему пути, но расхода за период нет. Это ЗНАЧИМЫЙ нуль:
        # трактовать его как сбой нельзя, иначе ключ без трафика на LTE-нодах вечно
        # пропускался бы с предупреждением и никогда не получал бы точку отсчёта.
        logger.info(
            "Remnawave[%s]: расход по нодам сквада %s за период нулевой (путь %s)",
            host_name, squad_uuid_n or "—", answered_path,
        )
        return NodeUsage({}, answered_path)

    raise RemnawavePathUnsupportedError(
        f"Remnawave[{host_name}]: ни один путь статистики по нодам не поддерживается "
        f"панелью для пользователя {user_uuid_n} (сквад {squad_uuid_n or '—'})"
    )


async def get_squad_node_overlap(host_name: str) -> list[dict[str, Any]]:
    """Ноды, доступные одновременно через LTE- и base-сквад хоста.

    Такое пересечение означает, что расход на этих нодах будет считаться в LTE-пул, хотя
    они же отдаются базовым (безлимитным) сквадом. Исправить это можно только настройкой
    inbound'ов сквадов на стороне Remnawave — код лишь обнаруживает и предупреждает.
    """
    lte_nodes = await get_lte_nodes_for_host(host_name)
    if not lte_nodes:
        return []
    base_nodes = await get_squad_nodes_for_class(host_name, "base")
    base_uuids = {n["uuid"] for n in base_nodes}
    return [n for n in lte_nodes if n["uuid"] in base_uuids]


async def refresh_host_squad_overlap(host_name: str) -> list[dict[str, Any]]:
    """Перепроверить пересечение сквадов хоста и сохранить результат для карточек.

    Вызывается при сохранении сквадов хоста. Пересечение НЕ блокирует сохранение — это
    предупреждение: устранить его можно только правкой inbound'ов сквадов в Remnawave.
    """
    invalidate_squad_nodes_cache()
    overlap = await get_squad_node_overlap(host_name)
    if overlap:
        logger.warning(
            "Remnawave[%s]: ноды доступны одновременно через LTE- и base-сквад — их трафик "
            "попадёт в LTE-пул, хотя они же отдаются безлимитным сквадом. Пересечение: %s",
            host_name,
            ", ".join(f"{n.get('node_name') or '—'} ({n['uuid']})" for n in overlap),
        )
    try:
        rw_repo.set_host_squad_overlap(host_name, overlap)
    except Exception as e:
        logger.warning("Remnawave[%s]: не удалось сохранить результат проверки сквадов: %s", host_name, e)
    return overlap


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
            if days == 0:
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
