"""Определение адреса клиента за обратным прокси (nginx).

Заголовку X-Forwarded-For можно верить только тогда, когда соединение пришло
от доверенного прокси. Внутри docker адрес прокси это шлюз docker-сети
(172.x.0.1), а не 127.0.0.1, поэтому по умолчанию доверенными считаются
loopback и частные диапазоны. Публичный адрес напрямую подключившегося клиента
никогда не доверенный: его X-Forwarded-For игнорируется.

nginx должен передавать `proxy_set_header X-Forwarded-For $remote_addr;`
(заменять заголовок, а не дописывать к клиентскому). Из цепочки берётся
правый недоверенный адрес, как делает uvicorn, поэтому подделанные клиентом
записи слева не учитываются.
"""
from __future__ import annotations

import ipaddress
import os

DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
TRUSTED_PROXIES_ENV = "SHOPBOT_TRUSTED_PROXIES"


def parse_trusted_proxies(raw: str | None = None) -> list:
    """Список адресов и сетей из строки через запятую; неверные записи пропускаются."""
    value = DEFAULT_TRUSTED_PROXIES if raw is None else raw
    networks = []
    for item in str(value).split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            continue
    return networks


def _as_ip(value: str | None):
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def _is_trusted(ip, networks) -> bool:
    return any(ip in net for net in networks if net.version == ip.version)


def resolve_client_ip(remote_addr: str | None, forwarded_for: str | None, trusted=None) -> str:
    """Адрес клиента: remote_addr, либо адрес из X-Forwarded-For за доверенным прокси."""
    remote = (remote_addr or "").strip()
    if trusted is None:
        trusted = parse_trusted_proxies(os.getenv(TRUSTED_PROXIES_ENV))
    remote_ip = _as_ip(remote)
    if remote_ip is None or not _is_trusted(remote_ip, trusted):
        return remote
    chain = [part.strip() for part in (forwarded_for or "").split(",") if part.strip()]
    candidate = None
    for part in reversed(chain):
        ip = _as_ip(part)
        if ip is None:
            return remote
        candidate = part
        if not _is_trusted(ip, trusted):
            return part
    return candidate or remote
