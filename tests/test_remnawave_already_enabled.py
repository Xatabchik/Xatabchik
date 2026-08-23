"""enable/disable пользователя уже в нужном состоянии — не ошибка (A030/A029)."""
import asyncio

from shop_bot.modules import remnawave_api as api


class _Resp:
    def __init__(self, payload, status: int = 400):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


def test_already_enabled_is_success(monkeypatch):
    async def transport(host_name, method, path, **kw):
        assert path.endswith("/actions/enable")
        return _Resp({"message": "User already enabled", "errorCode": "A030", "path": "/api/users/63/actions/enable"})

    monkeypatch.setattr(api, "_request_for_host", transport)
    assert asyncio.run(api.enable_user("63", host_name="test")) is True


def test_already_disabled_is_success(monkeypatch):
    async def transport(host_name, method, path, **kw):
        assert path.endswith("/actions/disable")
        return _Resp({"message": "User already disabled", "errorCode": "A029"})

    monkeypatch.setattr(api, "_request_for_host", transport)
    assert asyncio.run(api.disable_user("63", host_name="test")) is True


def test_other_400_on_enable_is_failure(monkeypatch):
    async def transport(host_name, method, path, **kw):
        return _Resp({"message": "Validation error", "errorCode": "A001"})

    monkeypatch.setattr(api, "_request_for_host", transport)
    assert asyncio.run(api.enable_user("63", host_name="test")) is False


def test_already_enabled_via_exception_string():
    exc = api.RemnawaveAPIError(
        "Remnawave API request failed: 400 "
        "{'timestamp': '2026-08-23T01:00:08.856Z', "
        "'path': '/api/users/63/actions/enable', "
        "'message': 'User already enabled', 'errorCode': 'A030'}"
    )
    assert api._is_already_in_desired_state(exc, want_enabled=True) is True
    assert api._is_already_in_desired_state(exc, want_enabled=False) is False
    assert api._detail_is_already_in_desired_state(
        {"errorCode": "A030", "message": "User already enabled"}, want_enabled=True
    )
    assert not api._detail_is_already_in_desired_state(
        {"errorCode": "A001", "message": "Validation error"}, want_enabled=True
    )
