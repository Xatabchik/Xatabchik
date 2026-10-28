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


# --- Оплаченное продление с явным plan_id не обходит исчерпанный лимит --------------------


@pytest.mark.parametrize("state", ["disabled_premium_squad", "disabled_premium"])
def test_explicit_plan_id_does_not_return_squad_to_exhausted_key(temp_db, panel, state):
    database = temp_db
    _host(database)
    lte_plan = _make_plan(database, HOST, "lte", lte_gb=10)
    bigger_plan = _make_plan(database, HOST, "bigger", lte_gb=100)
    key_id, email = _key(database, lte_plan, "u-ex")
    _set(database, key_id, remote_access_state=state)

    _renew(email, plan_id=lte_plan)
    assert panel.squads == [BASE], "продление на том же тарифе"
    _renew(email, plan_id=bigger_plan)
    assert panel.squads == [BASE], "смена тарифа: сквад вернёт планировщик по факту нового лимита"


def test_explicit_plan_id_with_inherited_limit_respects_exhausted_key(temp_db, panel):
    database = temp_db
    _host(database, default_gb=50)
    plan_id = _make_plan(database, HOST, "inh", lte_gb=0)
    key_id, email = _key(database, plan_id, "u-inh")
    _set(database, key_id, remote_access_state="disabled_premium_squad")
    _renew(email, plan_id=plan_id)
    assert panel.squads == [BASE]


@pytest.mark.parametrize("state", ["enabled", "", None])
def test_explicit_plan_id_adds_squad_to_key_with_access(temp_db, panel, state):
    database = temp_db
    _host(database)
    lte_plan = _make_plan(database, HOST, "lte", lte_gb=10)
    key_id, email = _key(database, lte_plan, "u-ok")
    _set(database, key_id, remote_access_state=state)
    _renew(email, plan_id=lte_plan)
    assert panel.squads == [BASE, LTE]


def test_explicit_plan_id_for_unknown_or_foreign_key_adds_squad(temp_db, panel):
    database = temp_db
    _host(database)
    _host(database, "Other")
    lte_plan = _make_plan(database, HOST, "lte", lte_gb=10)
    key_id, email = _key(database, lte_plan, "u-moved")
    _set(database, key_id, remote_access_state="disabled_premium_squad")

    _renew("brand-new@bot.local", plan_id=lte_plan)
    assert panel.squads == [BASE, LTE], "новый ключ"
    _renew(email, host="Other", plan_id=lte_plan)
    assert panel.squads == ["squad-base-Other", "squad-Other"], "ключ числится на другом хосте: его состояние не применяется"


@pytest.mark.parametrize("state", ["disabled_premium_squad", "disabled_premium"])
def test_explicit_include_lte_squad_keeps_priority_over_exhausted_state(temp_db, panel, state):
    database = temp_db
    _host(database)
    lte_plan = _make_plan(database, HOST, "lte", lte_gb=10)
    key_id, email = _key(database, lte_plan, "u-ex")
    _set(database, key_id, remote_access_state=state)

    _renew(email, include_lte_squad=True)
    assert panel.squads == [BASE, LTE]
    _renew(email, include_lte_squad=True, plan_id=lte_plan)
    assert panel.squads == [BASE, LTE]


def test_key_lookup_happens_once_and_only_when_needed(temp_db, panel, monkeypatch):
    from shop_bot.data_manager import remnawave_repository as rw_repo

    database = temp_db
    _host(database)
    lte_plan = _make_plan(database, HOST, "own", lte_gb=10)
    plain_plan = _make_plan(database, HOST, "plain", lte_gb=0)
    _, email = _key(database, lte_plan, "u-1")
    calls = []
    original = rw_repo.get_key_by_email
    monkeypatch.setattr(rw_repo, "get_key_by_email", lambda e: (calls.append(e), original(e))[1])

    _renew(email)
    assert len(calls) == 1, "без аргументов: один поиск"
    _renew(email, plan_id=lte_plan)
    assert len(calls) == 2, "явный plan_id с LTE: один поиск для проверки исчерпанного лимита"
    _renew(email, plan_id=plain_plan)
    _renew(email, include_lte_squad=True)
    _renew(email, include_lte_squad=False)
    assert len(calls) == 2, "plan_id без LTE и явный include_lte_squad ключ не ищут"


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


# --- Настоящий process_successful_payment -------------------------------------------------


class _FakeBot:
    id = 777

    def __init__(self):
        self.session = self

    async def send_message(self, *args, **kwargs):
        class _Message:
            async def edit_text(self, *a, **k):
                return None

            async def delete(self):
                return None

        return _Message()

    async def close(self):
        return None


def _pay(database, *, action, plan_id, pid, key_id=0, user_id=1):
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    meta = {
        "user_id": user_id,
        "months": 1,
        "duration_days": 0,
        "price": 100.0,
        "action": action,
        "key_id": key_id or None,
        "host_name": HOST,
        "plan_id": plan_id,
        "payment_method": "YooKassa",
        "payment_id": pid,
    }
    database.create_payload_pending(pid, user_id, 100.0, meta)
    assert database.find_and_complete_pending_transaction(pid) is not None
    return asyncio.run(process_successful_payment(_FakeBot(), meta))


def _lte_state(database, key_id):
    state = database.get_key_lte_state(key_id)
    return {k: state.get(k) for k in ("lte_limit_bytes", "lte_boost_bytes", "lte_baseline_bytes")}


def _access(database, key_id):
    with sqlite3.connect(database.DB_FILE) as conn:
        return conn.execute("SELECT remote_access_state FROM vpn_keys WHERE key_id = ?", (key_id,)).fetchone()[0]


@pytest.fixture
def paid(temp_db, panel):
    from conftest import insert_user

    insert_user(temp_db.DB_FILE, telegram_id=1, username="buyer")
    temp_db.update_setting("telegram_bot_token", "123456:FAKE_BOT_TOKEN_FOR_TESTS")
    return temp_db


def test_paid_extend_of_exhausted_key_neither_resets_limit_nor_returns_squad(paid, panel):
    database = paid
    _host(database)
    plan_id = _make_plan(database, HOST, "own", lte_gb=10)
    key_id, _ = _key(database, plan_id, "u-ex")
    database.commit_key_lte_baseline(key_id, 12 * GB, expire_boost=False)
    _set(database, key_id, remote_access_state="disabled_premium_squad")
    state_before = _lte_state(database, key_id)

    assert _pay(database, action="extend", plan_id=plan_id, key_id=key_id, pid="lte-extend-exhausted") is True

    assert panel.squads == [BASE], "продление дошло до панели без LTE-сквада"
    assert _access(database, key_id) == "disabled_premium_squad"
    assert _lte_state(database, key_id) == state_before


def test_paid_extend_after_access_was_restored_returns_squad(paid, panel):
    database = paid
    _host(database)
    plan_id = _make_plan(database, HOST, "own", lte_gb=10)
    key_id, _ = _key(database, plan_id, "u-restored")
    _set(database, key_id, remote_access_state="disabled_premium_squad")
    assert _pay(database, action="extend", plan_id=plan_id, key_id=key_id, pid="lte-extend-blocked") is True
    assert panel.squads == [BASE]

    # Доступ вернули тем же способом, что и в бою: докупка LTE / новый месяц / повышенный лимит.
    _set(database, key_id, remote_access_state="enabled")
    assert _pay(database, action="extend", plan_id=plan_id, key_id=key_id, pid="lte-extend-restored") is True
    assert panel.squads == [BASE, LTE]


def test_paid_new_key_gets_lte_squad(paid, panel):
    database = paid
    _host(database)
    plan_id = _make_plan(database, HOST, "own", lte_gb=10)

    assert _pay(database, action="new", plan_id=plan_id, pid="lte-new-key") is True
    assert panel.squads == [BASE, LTE]
