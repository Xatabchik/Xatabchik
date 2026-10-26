"""PR-IP: адрес клиента за nginx и docker.

На стенде nginx проксирует на 127.0.0.1:8001, а в контейнер соединение приходит
через docker-proxy, поэтому uvicorn видит шлюз docker-сети (172.x.0.1), а не
127.0.0.1. Со значением --forwarded-allow-ips по умолчанию X-Forwarded-For
игнорировался, и все клиенты для slowapi были одним адресом. Здесь проверяется,
что адрес определяется верно и не подделывается снаружи.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from conftest import temp_db  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
DOCKER_GATEWAY = "172.19.0.1"
PUBLIC_PEER = "203.0.113.9"


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def _forwarded_allow_ips_default() -> str:
    command = _compose()["services"]["xatabchik-webapp"]["command"]
    assert "--proxy-headers" in command
    match = re.search(r"--forwarded-allow-ips\s+\$\{WEBAPP_FORWARDED_ALLOW_IPS:-([^}]+)\}", command)
    assert match, command
    return match.group(1)


class _Probe:
    """ASGI-приложение, возвращающее адрес клиента так, как его увидит slowapi."""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        body = scope["client"][0].encode()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": body})


class _FixedPeer:
    """Задаёт адрес соединения (TestClient его не позволяет), как это делает сервер."""

    def __init__(self, app, peer: str):
        self.app = app
        self.peer = peer

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope, client=(self.peer, 50000))
        await self.app(scope, receive, send)


def _seen_client(peer: str, xff: str | None, trusted: str | None = None) -> str:
    from fastapi.testclient import TestClient
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    app = _FixedPeer(ProxyHeadersMiddleware(_Probe(), trusted_hosts=trusted or _forwarded_allow_ips_default()), peer)
    headers = {"X-Forwarded-For": xff} if xff is not None else {}
    return TestClient(app).get("/", headers=headers).text


def test_compose_trusts_docker_gateway_but_not_public_addresses():
    trusted = _forwarded_allow_ips_default()
    assert trusted.strip() != "*"
    assert "172.16.0.0/12" in trusted and "127.0.0.1" in trusted

    assert _seen_client(DOCKER_GATEWAY, "198.51.100.7") == "198.51.100.7"
    assert _seen_client("127.0.0.1", "198.51.100.7") == "198.51.100.7"


def test_forged_x_forwarded_for_from_public_peer_does_not_change_client():
    assert _seen_client(PUBLIC_PEER, "1.2.3.4") == PUBLIC_PEER
    assert _seen_client(PUBLIC_PEER, "1.2.3.4, 198.51.100.7") == PUBLIC_PEER


def test_forged_leftmost_entry_is_ignored_behind_trusted_proxy():
    # Если прокси дописывает адрес справа, подделка слева не принимается.
    assert _seen_client(DOCKER_GATEWAY, "1.2.3.4, 198.51.100.7") == "198.51.100.7"


def test_without_forwarded_header_peer_address_is_kept():
    assert _seen_client(DOCKER_GATEWAY, None) == DOCKER_GATEWAY


def test_old_default_trusts_only_loopback_and_collapses_clients():
    """Документирует исходную проблему: со значением uvicorn по умолчанию клиенты сливаются."""
    assert _seen_client(DOCKER_GATEWAY, "198.51.100.7", trusted="127.0.0.1") == DOCKER_GATEWAY
    assert _seen_client(DOCKER_GATEWAY, "198.51.100.8", trusted="127.0.0.1") == DOCKER_GATEWAY


def test_ports_are_published_on_loopback_only():
    services = _compose()["services"]
    for name, container_port in (("xatabchik-webapp", 8000), ("xatabchik", 1488)):
        ports = services[name].get("ports") or []
        assert ports, name
        for port in ports:
            if isinstance(port, dict):
                assert port.get("host_ip") == "127.0.0.1", (name, port)
            else:
                assert str(port).startswith("127.0.0.1:"), (name, port)
    assert not any(str(p).split(":")[-1] == "8000" and not str(p).startswith("127.0.0.1")
                   for p in services["xatabchik-webapp"]["ports"])


def test_slowapi_limits_are_separate_per_client_behind_proxy(temp_db):
    from fastapi.testclient import TestClient
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    from shop_bot.webapp import handlers

    app = _FixedPeer(ProxyHeadersMiddleware(handlers.app, trusted_hosts=_forwarded_allow_ips_default()), DOCKER_GATEWAY)
    client = TestClient(app)
    body = {"token": "nope", "init_data": "x"}

    def hit(xff: str) -> int:
        return client.post("/api/auth/sync-tg", json=body, headers={"X-Forwarded-For": xff}).status_code

    statuses_a = [hit("198.51.100.1") for _ in range(35)]
    assert 429 in statuses_a
    assert statuses_a[0] == 200

    assert hit("198.51.100.2") == 200
    assert hit("198.51.100.1") == 429


def test_slowapi_forged_header_from_outside_does_not_dodge_the_limit(temp_db):
    from fastapi.testclient import TestClient
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    from shop_bot.webapp import handlers

    app = _FixedPeer(ProxyHeadersMiddleware(handlers.app, trusted_hosts=_forwarded_allow_ips_default()), PUBLIC_PEER)
    client = TestClient(app)
    body = {"token": "nope", "init_data": "x"}

    statuses = [
        client.post("/api/auth/sync-tg", json=body, headers={"X-Forwarded-For": f"10.9.8.{i}"}).status_code
        for i in range(35)
    ]
    assert 429 in statuses


def test_slowapi_collapses_clients_with_old_default(temp_db):
    """Контроль: с прежним значением один клиент исчерпывает лимит за всех."""
    from fastapi.testclient import TestClient
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    from shop_bot.webapp import handlers

    app = _FixedPeer(ProxyHeadersMiddleware(handlers.app, trusted_hosts="127.0.0.1"), DOCKER_GATEWAY)
    client = TestClient(app)
    body = {"token": "nope", "init_data": "x"}
    for _ in range(35):
        client.post("/api/auth/sync-tg", json=body, headers={"X-Forwarded-For": "198.51.100.1"})
    assert client.post("/api/auth/sync-tg", json=body, headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 429


@pytest.mark.parametrize(
    "path",
    ["install.sh", "src/shop_bot/webapp/install.sh", "src/shop_bot/webhook_server/app.py"],
)
def test_nginx_templates_overwrite_x_forwarded_for(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert "proxy_add_x_forwarded_for" not in text
    assert re.search(r"proxy_set_header X-Forwarded-For \\?\$remote_addr;", text)


def test_nginx_templates_in_install_sh_cover_all_proxy_locations():
    for path in ("install.sh", "src/shop_bot/webapp/install.sh", "src/shop_bot/webhook_server/app.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        proxy_blocks = len(re.findall(r"proxy_pass http://127\.0\.0\.1", text))
        overwrites = len(re.findall(r"proxy_set_header X-Forwarded-For \\?\$remote_addr;", text))
        assert proxy_blocks == overwrites, (path, proxy_blocks, overwrites)


# --- Flask (панель, вебхуки): лимит входа и allowlist по IP клиента ---

def test_flask_login_buckets_are_per_client_behind_docker_gateway(temp_db):
    from shop_bot.webhook_server import app as wh_mod

    class _Bot:
        def get_status(self):
            return {"is_running": False}

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_Bot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()

    def post(xff: str):
        return client.post(
            "/login",
            data={"username": "admin", "password": "wrong"},
            headers={"X-Forwarded-For": xff},
            environ_base={"REMOTE_ADDR": DOCKER_GATEWAY},
        ).status_code

    assert [post("198.51.100.1") for _ in range(6)][-1] == 429
    assert post("198.51.100.2") == 200


def test_resolve_client_ip_unit():
    from shop_bot.core.client_ip import resolve_client_ip

    assert resolve_client_ip(PUBLIC_PEER, "1.2.3.4") == PUBLIC_PEER
    assert resolve_client_ip(DOCKER_GATEWAY, "198.51.100.7") == "198.51.100.7"
    assert resolve_client_ip(DOCKER_GATEWAY, "1.2.3.4, 198.51.100.7") == "198.51.100.7"
    assert resolve_client_ip(DOCKER_GATEWAY, "garbage") == DOCKER_GATEWAY
    assert resolve_client_ip(DOCKER_GATEWAY, "") == DOCKER_GATEWAY
    assert resolve_client_ip(DOCKER_GATEWAY, "198.51.100.7, 10.0.0.5") == "198.51.100.7"
    assert resolve_client_ip(DOCKER_GATEWAY, "10.0.0.5") == "10.0.0.5"
    assert resolve_client_ip("::1", "2001:db8::7") == "2001:db8::7"
    assert resolve_client_ip("2001:db8::99", "2001:db8::7") == "2001:db8::99"
    assert resolve_client_ip(None, "1.2.3.4") == ""
    assert resolve_client_ip(DOCKER_GATEWAY, "1.2.3.4", trusted=[]) == DOCKER_GATEWAY


def test_trusted_proxies_env_override(monkeypatch):
    from shop_bot.core.client_ip import resolve_client_ip

    monkeypatch.setenv("SHOPBOT_TRUSTED_PROXIES", "192.0.2.1")
    assert resolve_client_ip("192.0.2.1", "198.51.100.7") == "198.51.100.7"
    assert resolve_client_ip(DOCKER_GATEWAY, "198.51.100.7") == DOCKER_GATEWAY


def test_ton_webhook_allowlist_uses_resolved_client_ip(temp_db, monkeypatch):
    """Подделанный X-Forwarded-For от публичного соединения не проходит allowlist,
    а адрес за доверенным прокси проходит."""
    from shop_bot.webhook_server import app as wh_mod

    class _Bot:
        def get_status(self):
            return {"is_running": False}

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_Bot())
    flask_app.config["TESTING"] = True
    temp_db.update_setting("ton_webhook_secret", "s3cret")
    monkeypatch.setenv("SHOPBOT_TON_WEBHOOK_IP_ALLOWLIST", "198.51.100.50")
    client = flask_app.test_client()
    headers = {"X-Forwarded-For": "198.51.100.50", "X-Webhook-Secret": "s3cret"}

    forged = client.post("/ton-webhook", json={}, headers=headers, environ_base={"REMOTE_ADDR": PUBLIC_PEER})
    behind_proxy = client.post("/ton-webhook", json={}, headers=headers, environ_base={"REMOTE_ADDR": DOCKER_GATEWAY})
    other_client = client.post(
        "/ton-webhook", json={}, environ_base={"REMOTE_ADDR": DOCKER_GATEWAY},
        headers={"X-Forwarded-For": "198.51.100.51", "X-Webhook-Secret": "s3cret"},
    )

    assert forged.status_code == 403
    assert other_client.status_code == 403
    assert behind_proxy.status_code != 403
