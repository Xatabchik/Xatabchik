"""GET /api/users/{ref}: числовой id на 3.x, UUID на 2.x не должен давать 400 traceback."""
import asyncio

from shop_bot.modules import remnawave_api as api

PANEL_USER_ID = "42"
PANEL_UUID = "00000000-0000-4000-8000-000000000001"
EMAIL = "100001-1@bot.local"
USERNAME = "100001-1"


class _Resp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def test_classify_panel_user_ref():
    assert api._classify_panel_user_ref(PANEL_USER_ID) == "id"
    assert api._classify_panel_user_ref(PANEL_UUID) == "uuid"
    assert api._classify_panel_user_ref("abc12XYZ") == "short"
    assert api._classify_panel_user_ref("") == ""


def test_get_user_by_numeric_id(monkeypatch):
    async def transport(host_name, method, path, **kw):
        assert path == f"/api/users/{PANEL_USER_ID}"
        return _Resp({"response": {"id": 42, "usedTrafficBytes": 10}}, 200)

    monkeypatch.setattr(api, "_request_for_host", transport)
    user = asyncio.run(api.get_user_by_uuid(PANEL_USER_ID, host_name="test-host"))
    assert user["id"] == 42


def test_get_user_by_uuid_v3_nan_is_not_an_error(monkeypatch):
    calls: list[str] = []

    async def transport(host_name, method, path, **kw):
        calls.append(path)
        return _Resp(
            {
                "statusCode": 400,
                "message": "Validation failed",
                "errors": [
                    {
                        "expected": "number",
                        "code": "invalid_type",
                        "received": "NaN",
                        "path": ["userId"],
                        "message": "Invalid input: expected number, received NaN",
                    }
                ],
            },
            400,
        )

    monkeypatch.setattr(api, "_request_for_host", transport)
    user = asyncio.run(api.get_user_by_uuid(PANEL_UUID, host_name="test-host"))
    assert user is None
    assert calls == [f"/api/users/{PANEL_UUID}"]


def test_get_user_by_uuid_v2_still_works(monkeypatch):
    async def transport(host_name, method, path, **kw):
        assert path == f"/api/users/{PANEL_UUID}"
        return _Resp({"response": {"uuid": PANEL_UUID, "usedTrafficBytes": 7}}, 200)

    monkeypatch.setattr(api, "_request_for_host", transport)
    user = asyncio.run(api.get_user_by_uuid(PANEL_UUID, host_name="test-host"))
    assert user["uuid"] == PANEL_UUID


def test_used_traffic_falls_back_to_username_when_uuid_unknown(monkeypatch):
    async def transport(host_name, method, path, **kw):
        if path.startswith("/api/users/") and PANEL_UUID in path and "/by-" not in path:
            return _Resp({"statusCode": 400, "message": "Validation failed"}, 400)
        if "/by-email/" in path:
            return _Resp({}, 404)
        if "/by-username/" in path:
            assert USERNAME in path
            return _Resp({"response": {"username": USERNAME, "usedTrafficBytes": 1234}}, 200)
        raise AssertionError(path)

    monkeypatch.setattr(api, "_request_for_host", transport)
    used = asyncio.run(
        api.get_user_used_traffic(PANEL_UUID, host_name="test-host", email=EMAIL)
    )
    assert used == 1234
