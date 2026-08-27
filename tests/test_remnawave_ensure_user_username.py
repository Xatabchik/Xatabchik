"""ensure_user: если by-email 404, но username уже есть — PATCH, а не POST (A019)."""
import asyncio
from datetime import datetime, timezone

from shop_bot.modules import remnawave_api as api

# Шаблон как у generate_key_email_for_user: {user_id}-{n}@bot.local
USER_ID = 100001
KEY_N = 1
USERNAME = f"{USER_ID}-{KEY_N}"
EMAIL = f"{USERNAME}@bot.local"
SQUAD_UUID = "11111111-1111-4111-8111-111111111111"


class _Resp:
    def __init__(self, payload, status: int = 200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _expire():
    return datetime(2026, 9, 29, 12, 31, 26, tzinfo=timezone.utc)


def _run_ensure(**kwargs):
    return asyncio.run(
        api.ensure_user(
            host_name="test",
            email=EMAIL,
            squad_uuid=SQUAD_UUID,
            expire_at=_expire(),
            username=USERNAME,
            **kwargs,
        )
    )


def test_ensure_user_patches_when_email_missing_but_username_exists(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def transport(host_name, method, path, **kw):
        calls.append((method, path))
        payload = kw.get("json_payload")
        if method == "GET" and "/by-email/" in path:
            return _Resp({}, 404)
        if method == "GET" and "/by-username/" in path:
            return _Resp(
                {
                    "response": {
                        "uuid": "u-1",
                        "id": 1,
                        "username": USERNAME,
                        "expireAt": "2026-01-01T00:00:00Z",
                    }
                },
                200,
            )
        if method == "PATCH" and path == "/api/users":
            assert payload["username"] == USERNAME
            assert payload["email"] == EMAIL
            assert payload["id"] == 1
            return _Resp(
                {"response": {"uuid": "u-1", "id": 1, "expireAt": "2026-09-29T12:31:26Z"}},
                200,
            )
        if method == "POST":
            raise AssertionError("POST /api/users must not be called when username exists")
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(api, "_request_for_host", transport)
    result = _run_ensure()
    assert result["uuid"] == "u-1"
    assert ("POST", "/api/users") not in calls
    assert ("PATCH", "/api/users") in calls


def test_ensure_user_posts_when_neither_email_nor_username_exists(monkeypatch):
    async def transport(host_name, method, path, **kw):
        if method == "GET":
            return _Resp({}, 404)
        if method == "POST" and path == "/api/users":
            payload = kw.get("json_payload") or {}
            assert payload["username"] == USERNAME
            return _Resp(
                {"response": {"uuid": "new-u", "username": USERNAME, "expireAt": "2026-09-29T12:31:26Z"}},
                201,
            )
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(api, "_request_for_host", transport)
    result = _run_ensure()
    assert result["uuid"] == "new-u"


def test_ensure_user_a019_fallback_still_patches(monkeypatch):
    username_hits = {"n": 0}

    async def transport(host_name, method, path, **kw):
        if method == "GET" and "/by-email/" in path:
            return _Resp({}, 404)
        if method == "GET" and "/by-username/" in path:
            username_hits["n"] += 1
            if username_hits["n"] == 1:
                return _Resp({}, 404)
            return _Resp({"response": {"uuid": "u-1", "id": 1, "username": USERNAME}}, 200)
        if method == "POST":
            raise api.RemnawaveAPIError(
                "Remnawave API request failed: 400 "
                "{'message': 'User username already exists', 'errorCode': 'A019'}"
            )
        if method == "PATCH":
            payload = kw.get("json_payload") or {}
            assert payload.get("email") == EMAIL
            return _Resp({"response": {"uuid": "u-1", "expireAt": "2026-09-29T12:31:26Z"}}, 200)
        raise AssertionError(f"unexpected {method} {path}")

    monkeypatch.setattr(api, "_request_for_host", transport)
    result = _run_ensure()
    assert result["uuid"] == "u-1"


def test_extract_user_from_list_payload():
    user = api._extract_user_from_api_payload(
        {"response": [{"username": USERNAME, "uuid": "u-1"}]}
    )
    assert user == {"username": USERNAME, "uuid": "u-1"}
