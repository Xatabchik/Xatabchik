"""WebApp не должен забивать пул httpx при загрузке многих ключей."""
import asyncio

import httpx
import pytest

from shop_bot.modules import remnawave_api as api


class _Resp:
    status_code = 200

    def json(self):
        return {"response": {"uuid": "u1", "email": "a@b.c"}}


@pytest.fixture(autouse=True)
def _reset_sems():
    api._REQUEST_SEMS.clear()
    yield
    api._REQUEST_SEMS.clear()


def test_inflight_requests_are_capped(monkeypatch):
    inflight = 0
    peak = 0

    class _Client:
        async def request(self, **kwargs):
            nonlocal inflight, peak
            inflight += 1
            peak = max(peak, inflight)
            await asyncio.sleep(0.02)
            inflight -= 1
            return _Resp()

    async def fake_client(_config):
        return _Client()

    monkeypatch.setattr(api, "_get_shared_client", fake_client)
    monkeypatch.setattr(api, "_load_config_for_host", lambda _h: {
        "base_url": "https://panel.example", "token": "t", "cookies": {}, "is_local": False,
    })

    async def run():
        await asyncio.gather(*[
            api._request_for_host("H", "GET", f"/api/users/{i}", expected_status=(200,))
            for i in range(40)
        ])

    asyncio.run(run())
    assert peak <= api._MAX_INFLIGHT
    assert peak >= 1


def test_pool_timeout_becomes_api_error_without_traceback_path(monkeypatch):
    class _Client:
        async def request(self, **kwargs):
            raise httpx.PoolTimeout("pool exhausted")

    async def fake_client(_config):
        return _Client()

    monkeypatch.setattr(api, "_get_shared_client", fake_client)
    monkeypatch.setattr(api, "_load_config_for_host", lambda _h: {
        "base_url": "https://panel.example", "token": "t", "cookies": {}, "is_local": False,
    })

    with pytest.raises(api.RemnawaveAPIError, match="timeout"):
        asyncio.run(api._request_for_host("H", "GET", "/api/users/1"))

    details = asyncio.run(api.get_key_details_from_host({
        "key_id": 15722,
        "key_email": "user@example.com",
        "host_name": "H",
    }))
    assert details is None


def test_gather_limited_respects_limit():
    inflight = 0
    peak = 0

    async def work(_i):
        nonlocal inflight, peak
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0.01)
        inflight -= 1
        return _i

    out = asyncio.run(api.gather_limited([work(i) for i in range(20)], limit=4))
    assert out == list(range(20))
    assert peak <= 4
