"""Продление без `plan_id` не должно снимать LTE-сквад у существующего ключа.

Панель принимает `activeInternalSquads` целиком, поэтому `create_or_update_key_on_host`
обязан знать, нужен ли ключу LTE-сквад. Если вызов не передаёт ни `plan_id`, ни
`include_lte_squad`, тариф берётся по существующему ключу из локальной БД.

Панель замокана на уровне HTTP-шлюза (`_request_for_host`): тест видит настоящий payload
PATCH/POST, а любая попытка реального сетевого обращения роняет тест.
"""
import asyncio
import json
import socket
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from conftest import temp_db  # noqa: F401
from test_lte_enforcement import _insert_key
from test_lte_host_defaults import GB, _make_plan

BASE = "squad-base"
LTE = "squad-Lte"
HOST = "Lte"


class _Panel:
    def __init__(self):
        self.requests: list[tuple[str, str, dict]] = []
        self.lookups: list[str] = []

    @property
    def squads(self) -> list[str]:
        assert self.requests, "запрос к панели не отправлялся"
        return self.requests[-1][2]["activeInternalSquads"]


@pytest.fixture
def panel(temp_db, monkeypatch):
    from shop_bot.modules import remnawave_api

    state = _Panel()
    future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def _no_network(*args, **kwargs):
        raise AssertionError("реальное сетевое обращение к панели")

    async def request(host_name, method, path, *, json_payload=None, params=None, expected_status=(200,)):
        state.requests.append((method, path, dict(json_payload or {})))
        body = {"uuid": "panel-uuid", "id": 1, "username": "u", "expireAt": future}
        return httpx.Response(200, json={"response": body})

    async def existing_user(*args, **kwargs):
        state.lookups.append("panel")
        return {"uuid": "panel-uuid", "id": 1, "username": "u", "expireAt": future}

    monkeypatch.setattr(socket.socket, "connect", _no_network)
    monkeypatch.setattr(remnawave_api, "_request_for_host", request)
    monkeypatch.setattr(remnawave_api, "get_user_by_email", existing_user)
    monkeypatch.setattr(remnawave_api, "get_user_by_username", existing_user)
    monkeypatch.setattr(remnawave_api, "lookup_panel_user", existing_user)
    return state


def _host(database, name=HOST, *, default_gb=0):
    database.create_host(name, "https://panel.example", "", "", 0)
    database.update_host_remnawave_settings(
        name, remnawave_base_url="https://panel.example", remnawave_api_token="tok", squad_uuid=BASE if name == HOST else f"squad-base-{name}"
    )
    database.add_host_squad(name, f"squad-{name}", "lte", "LTE")
    if default_gb:
        database.set_host_lte_default_limit_bytes(name, default_gb * GB)


def _key(database, plan_id, uuid, *, host=HOST, user_id=1):
    return _insert_key(database, user_id=user_id, host_name=host, user_uuid=uuid, plan_id=plan_id), f"{uuid}@example.com"


def _set(database, key_id, **fields):
    sets = ", ".join(f"{k} = ?" for k in fields)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(f"UPDATE vpn_keys SET {sets} WHERE key_id = ?", (*fields.values(), key_id))


def _renew(email, host=HOST, **kwargs):
    from shop_bot.modules import remnawave_api

    return asyncio.run(
        remnawave_api.create_or_update_key_on_host(host, email, days_to_add=30, raise_on_error=True, **kwargs)
    )


# --- Ключи с LTE-лимитом сохраняют сквад --------------------------------------------------


def test_renewal_without_plan_id_keeps_lte_squad_for_own_limit(temp_db, panel):
    database = temp_db
    _host(database)
    _, email = _key(database, _make_plan(database, HOST, "own", lte_gb=10), "u-own")
    _renew(email)
    assert panel.squads == [BASE, LTE]


def test_renewal_without_plan_id_keeps_lte_squad_for_inherited_limit(temp_db, panel):
    database = temp_db
    _host(database, default_gb=50)
    _, email = _key(database, _make_plan(database, HOST, "inh", lte_gb=0), "u-inh")
    _renew(email)
    assert panel.squads == [BASE, LTE]


def test_renewal_without_lte_limit_adds_no_lte_squad(temp_db, panel):
    database = temp_db
    _host(database)
    _, email = _key(database, _make_plan(database, HOST, "none", lte_gb=0), "u-none")
    _renew(email)
    assert panel.squads == [BASE]


# --- Без тарифа поведение прежнее ---------------------------------------------------------


def test_keys_without_billing_plan_stay_base_only(temp_db, panel):
    database = temp_db
    _host(database, default_gb=50)
    plan_id = _make_plan(database, HOST, "paid", lte_gb=10)
    cases = {}
    for index, (name, fields) in enumerate({
        "trial": {"tag": "trial", "description": json.dumps({"v": 1, "source": "trial", "is_trial": True})},
        "gift": {"tag": "user_gift", "description": json.dumps({"v": 1, "source": "gift"})},
        "bonus": {"tag": "paid", "description": "Referral trial bonus +1 day"},
        "legacy": {"tag": "paid", "description": json.dumps({"v": 1, "source": "purchase"})},
    }.items()):
        key_id, email = _key(database, plan_id, f"u-{name}", user_id=index + 10)
        _set(database, key_id, **fields)
        cases[name] = email
    for name, email in cases.items():
        panel.requests.clear()
        _renew(email)
        assert panel.squads == [BASE], f"{name}: LTE-сквад не должен добавляться"


def test_unknown_key_and_key_of_other_host_stay_base_only(temp_db, panel):
    database = temp_db
    _host(database, default_gb=50)
    _host(database, "Other")
    plan_id = _make_plan(database, HOST, "p", lte_gb=10)
    _, email = _key(database, plan_id, "u-moved")

    _renew("nobody@bot.local")
    assert panel.squads == [BASE]
    panel.requests.clear()
    _renew(email, host="Other")
    assert panel.squads == ["squad-base-Other"], "ключ числится на другом хосте (перенос): вывод по ключу не применяется"


# --- Ключ с исчерпанным LTE ---------------------------------------------------------------


@pytest.mark.parametrize("state", ["disabled_premium_squad", "disabled_premium"])
def test_renewal_does_not_return_lte_squad_to_exhausted_key(temp_db, panel, state):
    database = temp_db
    _host(database)
    key_id, email = _key(database, _make_plan(database, HOST, "own", lte_gb=10), "u-ex")
    _set(database, key_id, remote_access_state=state)

    _renew(email)
    assert panel.squads == [BASE]

    _set(database, key_id, remote_access_state="enabled")
    _renew(email)
    assert panel.squads == [BASE, LTE]


# --- Явные аргументы приоритетнее ---------------------------------------------------------


def test_explicit_arguments_override_inference(temp_db, panel):
    database = temp_db
    _host(database)
    lte_plan = _make_plan(database, HOST, "lte", lte_gb=10)
    plain_plan = _make_plan(database, HOST, "plain", lte_gb=0)
    key_id, email = _key(database, lte_plan, "u-1")

    _renew(email, include_lte_squad=False)
    assert panel.squads == [BASE]
    _renew(email, plan_id=plain_plan)
    assert panel.squads == [BASE], "явный plan_id без LTE снимает сквад (смена тарифа)"

    _key_id2, email2 = _key(database, plain_plan, "u-2", user_id=2)
    _renew(email2, include_lte_squad=True)
    assert panel.squads == [BASE, LTE]
    _renew(email2, plan_id=lte_plan)
    assert panel.squads == [BASE, LTE]

    _set(database, key_id, remote_access_state="disabled_premium_squad")
    _renew(email, plan_id=lte_plan)
    assert panel.squads == [BASE, LTE], "путь покупки/продления с plan_id работает как раньше"


def test_key_lookup_happens_once_and_only_without_explicit_arguments(temp_db, panel, monkeypatch):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    database = temp_db
    _host(database)
    plan_id = _make_plan(database, HOST, "own", lte_gb=10)
    _, email = _key(database, plan_id, "u-1")
    calls = []
    original = rw_repo.get_key_by_email
    monkeypatch.setattr(rw_repo, "get_key_by_email", lambda e: (calls.append(e), original(e))[1])

    _renew(email)
    assert len(calls) == 1
    _renew(email, plan_id=plan_id)
    _renew(email, include_lte_squad=True)
    assert len(calls) == 1


# --- Вызовы из кода -----------------------------------------------------------------------


def test_admin_expiry_sync_keeps_lte_squad(temp_db, panel):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    database = temp_db
    _host(database, default_gb=50)
    key_id, _ = _key(database, _make_plan(database, HOST, "inh", lte_gb=0), "u-sync")
    new_ms = int((datetime.now(timezone.utc) + timedelta(days=20)).timestamp() * 1000)

    ok, error, _ = rw_repo._sync_key_expiry_ms(key_id, new_ms)
    assert ok, error
    assert panel.squads == [BASE, LTE]


def test_referral_bonus_on_paid_key_keeps_lte_but_on_bonus_key_does_not(temp_db, panel):
    from shop_bot.modules import remnawave_api

    database = temp_db
    _host(database, default_gb=50)
    plan_id = _make_plan(database, HOST, "inh", lte_gb=0)
    paid_id, paid_email = _key(database, plan_id, "u-paid")
    bonus_id, bonus_email = _key(database, plan_id, "u-bonus", user_id=2)
    _set(database, bonus_id, description="Referral trial bonus +1 day")

    for email in (paid_email, bonus_email):
        asyncio.run(
            remnawave_api.create_or_update_key_on_host(
                host_name=HOST, email=email, days_to_add=1, description="Бонус за активацию триала рефералом (+1 день)"
            )
        )
        if email == paid_email:
            assert panel.squads == [BASE, LTE]
        else:
            assert panel.squads == [BASE]
