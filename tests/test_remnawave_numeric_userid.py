"""GET /api/users/{ref} и /api/hwid/devices/{ref}: числовой id на 3.x, UUID не должен давать 400 traceback."""
import asyncio

from shop_bot.modules import remnawave_api as api

PANEL_USER_ID = "42"
PANEL_UUID = "00000000-0000-4000-8000-000000000001"
EMAIL = "100001-1@bot.local"
USERNAME = "100001-1"
SUB_URL = "https://sub.example/key"

V3_NAN = {
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
}


class _Resp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _v3_transport():
    """3.x: UUID в {userId} → 400; by-email снят; живой lookup — username и числовой id."""
    calls: list[tuple[str, tuple[int, ...] | None]] = []

    async def transport(host_name, method, path, **kw):
        calls.append((path, kw.get("expected_status")))
        if path == f"/api/users/{PANEL_UUID}" or path == f"/api/hwid/devices/{PANEL_UUID}":
            return _Resp(V3_NAN, 400)
        if path == f"/api/users/{PANEL_USER_ID}":
            return _Resp(
                {
                    "response": {
                        "id": 42,
                        "username": USERNAME,
                        "subscriptionUrl": SUB_URL,
                        "usedTrafficBytes": 1234,
                    }
                },
                200,
            )
        if path == f"/api/hwid/devices/{PANEL_USER_ID}":
            return _Resp({"response": [{"hwid": "dev-1"}]}, 200)
        if "/by-email/" in path:
            return _Resp({}, 404)
        if "/by-username/" in path:
            assert USERNAME in path
            return _Resp(
                {
                    "response": {
                        "id": 42,
                        "username": USERNAME,
                        "subscriptionUrl": SUB_URL,
                        "usedTrafficBytes": 1234,
                    }
                },
                200,
            )
        raise AssertionError(path)

    return transport, calls


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
        return _Resp(V3_NAN, 400)

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


def test_panel_user_ref_prefers_numeric_id():
    assert api.panel_user_ref_from_payload({"id": 42, "uuid": PANEL_UUID}) == PANEL_USER_ID
    assert api.panel_user_ref_from_payload({"uuid": PANEL_UUID}) == PANEL_UUID
    assert api.panel_user_ref_from_payload(None) == ""


def test_hwid_uuid_v3_resolves_numeric_id_via_username(monkeypatch):
    transport, calls = _v3_transport()
    monkeypatch.setattr(api, "_request_for_host", transport)
    devices = asyncio.run(
        api.get_hwid_devices_for_user(PANEL_UUID, host_name="test-host", email=EMAIL)
    )
    assert devices == [{"hwid": "dev-1"}]
    hwid_uuid_call = next(c for c in calls if c[0] == f"/api/hwid/devices/{PANEL_UUID}")
    assert 400 in (hwid_uuid_call[1] or ())
    assert any(c[0] == f"/api/hwid/devices/{PANEL_USER_ID}" for c in calls)
    assert any("/by-username/" in c[0] for c in calls)


def test_hwid_uuid_v3_without_email_is_not_an_error(monkeypatch):
    transport, calls = _v3_transport()
    monkeypatch.setattr(api, "_request_for_host", transport)
    devices = asyncio.run(api.get_hwid_devices_for_user(PANEL_UUID, host_name="test-host"))
    assert devices is None
    hwid_uuid_call = next(c for c in calls if c[0] == f"/api/hwid/devices/{PANEL_UUID}")
    assert 400 in (hwid_uuid_call[1] or ())
    assert not any(c[0] == f"/api/hwid/devices/{PANEL_USER_ID}" for c in calls)


def test_hwid_numeric_id_direct(monkeypatch):
    transport, _calls = _v3_transport()
    monkeypatch.setattr(api, "_request_for_host", transport)
    devices = asyncio.run(
        api.get_hwid_devices_for_user(PANEL_USER_ID, host_name="test-host")
    )
    assert devices == [{"hwid": "dev-1"}]


def test_key_details_found_via_username_on_v3(monkeypatch):
    transport, _calls = _v3_transport()
    monkeypatch.setattr(api, "_request_for_host", transport)
    details = asyncio.run(
        api.get_key_details_from_host(
            {
                "key_id": 1,
                "key_email": EMAIL,
                "remnawave_user_uuid": PANEL_UUID,
                "host_name": "test-host",
            }
        )
    )
    assert details is not None
    assert details["connection_string"] == SUB_URL
    assert details["user"]["id"] == 42


def test_panel_user_exists_true_via_username_on_v3(monkeypatch):
    transport, _calls = _v3_transport()
    monkeypatch.setattr(api, "_request_for_host", transport)
    exists = asyncio.run(
        api.panel_user_exists(user_ref=PANEL_UUID, email=EMAIL, host_name="test-host")
    )
    assert exists is True


def test_panel_user_exists_false_when_username_404(monkeypatch):
    async def transport(host_name, method, path, **kw):
        if path == f"/api/users/{PANEL_UUID}":
            return _Resp(V3_NAN, 400)
        if "/by-email/" in path or "/by-username/" in path:
            return _Resp({}, 404)
        raise AssertionError(path)

    monkeypatch.setattr(api, "_request_for_host", transport)
    exists = asyncio.run(
        api.panel_user_exists(user_ref=PANEL_UUID, email=EMAIL, host_name="test-host")
    )
    assert exists is False


def test_panel_user_exists_uncertain_when_uuid_nan_without_email(monkeypatch):
    async def transport(host_name, method, path, **kw):
        assert path == f"/api/users/{PANEL_UUID}"
        return _Resp(V3_NAN, 400)

    monkeypatch.setattr(api, "_request_for_host", transport)
    exists = asyncio.run(
        api.panel_user_exists(user_ref=PANEL_UUID, email=None, host_name="test-host")
    )
    assert exists is None


DEVICE_HWID = "00000000-0000-4000-8000-000000000002"


def test_delete_hwid_sends_numeric_userid_when_uuid_stored(monkeypatch):
    posted: list[dict] = []

    async def transport(host_name, method, path, **kw):
        if path == "/api/hwid/devices/delete":
            posted.append(kw.get("json_payload") or {})
            return _Resp({"response": {"ok": True}}, 200)
        if path == f"/api/users/{PANEL_UUID}":
            return _Resp(V3_NAN, 400)
        if "/by-email/" in path:
            return _Resp({}, 404)
        if "/by-username/" in path:
            return _Resp({"response": {"id": 42, "username": USERNAME}}, 200)
        raise AssertionError(path)

    monkeypatch.setattr(api, "_request_for_host", transport)
    ok = asyncio.run(
        api.delete_hwid_device(PANEL_UUID, DEVICE_HWID, host_name="test-host", email=EMAIL)
    )
    assert ok is True
    assert posted == [
        {"hwid": DEVICE_HWID, "userId": 42, "userUuid": PANEL_UUID}
    ]


def test_delete_hwid_numeric_ref_sends_userid_without_lookup(monkeypatch):
    posted: list[dict] = []

    async def transport(host_name, method, path, **kw):
        if path == "/api/hwid/devices/delete":
            posted.append(kw.get("json_payload") or {})
            return _Resp({}, 200)
        raise AssertionError(path)

    monkeypatch.setattr(api, "_request_for_host", transport)
    ok = asyncio.run(
        api.delete_hwid_device(PANEL_USER_ID, DEVICE_HWID, host_name="test-host")
    )
    assert ok is True
    assert posted == [{"hwid": DEVICE_HWID, "userId": 42}]
