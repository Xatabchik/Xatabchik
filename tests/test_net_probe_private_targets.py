"""F-03: net_probe_for_host не открывает TCP/HTTP к loopback/link-local/private."""
from __future__ import annotations

import asyncio

import pytest

from shop_bot.data_manager import speedtest_runner


def _run(host_url: str) -> dict:
    return asyncio.run(speedtest_runner.net_probe_for_host({"host_url": host_url}))


@pytest.fixture()
def no_network(monkeypatch):
    async def _forbid_open(*_a, **_k):
        raise AssertionError("TCP connect must not run for a blocked probe target")

    class _ForbidSession:
        def __init__(self, *args, **kwargs):
            raise AssertionError("HTTP client must not run for a blocked probe target")

    monkeypatch.setattr(speedtest_runner.asyncio, "open_connection", _forbid_open)
    monkeypatch.setattr(speedtest_runner.aiohttp, "ClientSession", _ForbidSession)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8080/status",
        "https://169.254.169.254/",
        "http://10.0.0.8/",
        "http://192.168.1.10/api",
        "http://172.16.0.5/",
    ],
)
def test_net_probe_rejects_blocked_literal_ips_before_network(no_network, url):
    result = _run(url)
    assert result["ok"] is False
    assert result["error"] == "Blocked destination address"
    assert result["ping_ms"] is None
    assert result["http_ms"] is None


def test_net_probe_rejects_localhost_before_network(no_network):
    result = _run("http://localhost/")
    assert result["ok"] is False
    assert result["error"] == "Blocked destination address"


def test_net_probe_rejects_non_http_scheme_before_network(no_network):
    result = _run("file://localhost/tmp/probe")
    assert result["ok"] is False
    assert result["error"] == "Unsupported URL scheme"


def test_net_probe_rejects_ftp_scheme_before_network(no_network):
    result = _run("ftp://example.com/")
    assert result["ok"] is False
    assert result["error"] == "Unsupported URL scheme"
