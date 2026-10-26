"""Ветка «только дни» в create_or_update_key_on_host на Remnawave 3.x.

На 3.x GET /api/users/by-email/{email} снят и всегда отвечает 404. Раньше ветка
`days_to_add` без `expiry_timestamp_ms` смотрела только by-email, не находила
пользователя и считала срок от «сейчас»: оставшиеся дни терялись. Теперь после
by-email выполняется lookup по username (как в ensure_user).
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from shop_bot.modules import remnawave_api as api

HOST = "h1"
USERNAME = "100001-1"
EMAIL = f"{USERNAME}@bot.local"
SQUAD = {"host_name": HOST, "squad_uuid": "11111111-1111-4111-8111-111111111111"}


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Panel:
    def __init__(self, expire, *, by_email=False):
        self.user = {"id": 5, "uuid": None, "username": USERNAME, "expireAt": _iso(expire), "shortUuid": "s"}
        self.by_email = by_email
        self.patched = []

    async def transport(self, host_name, method, path, **kw):
        if method == "GET" and "/by-email/" in path:
            return _Resp({"response": dict(self.user)} if self.by_email else {}, 200 if self.by_email else 404)
        if method == "GET" and "/by-username/" in path:
            return _Resp({"response": dict(self.user)}, 200)
        if method == "PATCH":
            payload = kw.get("json_payload") or {}
            self.patched.append(payload["expireAt"])
            self.user["expireAt"] = payload["expireAt"]
            return _Resp({"response": dict(self.user)}, 200)
        raise AssertionError(f"unexpected {method} {path}")


@pytest.fixture()
def env(monkeypatch):
    monkeypatch.setattr(api.rw_repo, "get_squad", lambda host: dict(SQUAD))
    monkeypatch.setattr(api.rw_repo, "get_squad_by_class", lambda host, cls: None)

    def make(panel):
        monkeypatch.setattr(api, "_request_for_host", panel.transport)
        return panel

    return make


def _extend(days):
    return asyncio.run(api.create_or_update_key_on_host(HOST, EMAIL, days_to_add=days, raise_on_error=True))


def _days_from(now, iso):
    return (datetime.fromisoformat(iso.replace("Z", "+00:00")) - now).total_seconds() / 86400


def test_days_only_extends_from_current_expiry_when_by_email_is_removed(env):
    now = datetime.now(timezone.utc)
    panel = env(Panel(now + timedelta(days=10)))
    _extend(30)
    assert _days_from(now, panel.user["expireAt"]) == pytest.approx(40, abs=0.01)


def test_days_only_still_works_when_by_email_is_available(env):
    now = datetime.now(timezone.utc)
    panel = env(Panel(now + timedelta(days=10), by_email=True))
    _extend(30)
    assert _days_from(now, panel.user["expireAt"]) == pytest.approx(40, abs=0.01)


def test_days_only_on_expired_key_counts_from_now(env):
    now = datetime.now(timezone.utc)
    panel = env(Panel(now - timedelta(days=5)))
    _extend(30)
    assert _days_from(now, panel.user["expireAt"]) == pytest.approx(30, abs=0.01)
