"""Живое состояние карточек ключей в Mini App: автопродление и устройства.

Карточка показывала «Лимит: 0 / ∞», потому что число устройств искалось по
несуществующему полю `total` и только для активных ключей главной страницы.
Теперь лимит и число устройств считаются как в боте для всех карточек, а
открытая страница ключей подтягивает свежее состояние через
/api/keys/live-state.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")

OWNER_ID = 75001
STRANGER_ID = 75002
HOST = "LiveHost"


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _add_key(database, user_id: int, uuid_: str, **kwargs) -> int:
    kid = database.add_new_key(
        user_id,
        HOST,
        uuid_,
        f"{uuid_}@bot.local",
        int((time.time() + 30 * 86400) * 1000),
        short_uuid=f"s-{uuid_}",
        subscription_url=f"https://vpn.example/sub/{uuid_}",
        **kwargs,
    )
    assert kid
    return kid


def _patch_panel(monkeypatch, *, user_payload, hwid_response):
    from shop_bot.modules import remnawave_api

    async def fake_details(key):
        return {"user": dict(user_payload)} if user_payload is not None else None

    async def fake_user(uuid_, host_name=None):
        return {"usedTrafficBytes": 1024}

    async def fake_hwid(ref, host_name=None, email=None):
        return hwid_response

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", fake_details)
    monkeypatch.setattr(remnawave_api, "get_user_by_uuid", fake_user)
    monkeypatch.setattr(remnawave_api, "get_hwid_devices_for_user", fake_hwid)


def test_count_hwid_devices_payload_shapes():
    from shop_bot.webapp.web_router.render_keys import _count_hwid_devices_payload as count

    assert count(None) is None
    assert count([]) == 0
    assert count([{"hwid": "a"}, {"hwid": "b"}]) == 2
    assert count({"devices": [{"hwid": "a"}]}) == 1
    assert count({"total": 3}) == 3
    assert count({}) == 0


def test_enrich_sets_connected_devices_and_limit(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp.web_router.render_keys import _enrich_keys_live, _process_key_data

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner")
    kid = _add_key(database, OWNER_ID, "u-live-1")
    _patch_panel(
        monkeypatch,
        user_payload={"uuid": "u-live-1", "hwidDeviceLimit": 5},
        hwid_response={"devices": [{"hwid": "a"}, {"hwid": "b"}, {"hwid": "c"}]},
    )
    key = database.get_key_by_id(kid)
    asyncio.run(_enrich_keys_live([key]))
    assert _process_key_data(key)["hwid_info"] == "3 / 5"


def test_enrich_shows_dash_when_panel_unavailable(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp.web_router.render_keys import _enrich_keys_live, _process_key_data

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner")
    kid = _add_key(database, OWNER_ID, "u-live-2")
    _patch_panel(monkeypatch, user_payload=None, hwid_response=None)
    key = database.get_key_by_id(kid)
    asyncio.run(_enrich_keys_live([key]))
    assert _process_key_data(key)["hwid_info"].startswith("— /")


def test_live_state_returns_only_own_keys_with_fresh_auto_renew(temp_db, monkeypatch):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner")
    insert_user(database.DB_FILE, telegram_id=STRANGER_ID, username="stranger")
    own = _add_key(database, OWNER_ID, "u-own")
    foreign = _add_key(database, STRANGER_ID, "u-foreign")
    token = issue_auth_token(OWNER_ID)
    _patch_panel(
        monkeypatch,
        user_payload={"uuid": "u-own", "hwidDeviceLimit": 3},
        hwid_response={"devices": [{"hwid": "a"}]},
    )

    assert database.set_key_auto_renew(own, True)

    body = _client().post("/api/keys/live-state", json={"token": token}).json()
    assert body["ok"] is True
    by_id = {k["key_id"]: k for k in body["keys"]}
    assert set(by_id) == {own}
    assert foreign not in by_id
    assert by_id[own]["auto_renew"] is True
    assert by_id[own]["hwid_info"] == "1 / 3"

    assert database.set_key_auto_renew(own, False)
    body = _client().post("/api/keys/live-state", json={"token": token}).json()
    assert body["keys"][0]["auto_renew"] is False


def test_live_state_requires_auth(temp_db):
    res = _client().post("/api/keys/live-state", json={"token": "nope"})
    assert res.status_code in (200, 401, 403)
    assert not res.json().get("keys")


def test_auto_renew_endpoint_reports_actual_state_and_rejects_foreign(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner")
    insert_user(database.DB_FILE, telegram_id=STRANGER_ID, username="stranger")
    own = _add_key(database, OWNER_ID, "u-ar-own")
    foreign = _add_key(database, STRANGER_ID, "u-ar-foreign")
    token = issue_auth_token(OWNER_ID)

    ok = _client().post(
        "/api/key/auto-renew", json={"token": token, "key_id": own, "enabled": True}
    ).json()
    assert ok == {"ok": True, "auto_renew": True}
    assert int(database.get_key_by_id(own)["auto_renew"]) == 1

    denied = _client().post(
        "/api/key/auto-renew", json={"token": token, "key_id": foreign, "enabled": True}
    ).json()
    assert denied["ok"] is False
    assert int(database.get_key_by_id(foreign).get("auto_renew") or 0) == 0


def test_card_has_hwid_hook_for_live_updates(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp.web_router.render_keys import _get_key_card_html

    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner")
    kid = _add_key(database, OWNER_ID, "u-card")
    html = _get_key_card_html(database.get_key_by_id(kid))
    assert f'data-key-hwid="{kid}"' in html
    assert f'data-key-action="auto-renew" data-key-id="{kid}"' in html


@pytest.mark.skipif(NODE is None, reason="node не установлен")
def test_js_sync_updates_all_duplicate_cards_without_innerhtml(tmp_path):
    js = (ROOT / "src/shop_bot/webapp/static/js/app.js").read_text(encoding="utf-8")
    start = js.index("const _AUTO_RENEW_ON_CLASSES")
    end = js.index("async function toggleKeyAutoRenew(")
    snippet = js[start:end]
    assert "innerHTML" not in snippet

    script = tmp_path / "t.js"
    script.write_text(
        """
const assert = require('assert');
function mkClassList(initial) {
  const set = new Set(initial);
  return {
    add: (...c) => c.forEach((x) => set.add(x)),
    remove: (...c) => c.forEach((x) => set.delete(x)),
    has: (x) => set.has(x),
  };
}
function mkBtn(id) {
  const icon = { textContent: 'pause_circle' };
  const label = { textContent: 'Авто: ВЫКЛ' };
  const attrs = { 'data-key-id': String(id), 'data-key-action': 'auto-renew', 'data-auto-renew': 'false' };
  return {
    icon, label, attrs,
    classList: mkClassList(['border-white/5', 'text-white', 'bg-white/5', 'hover:bg-white/10']),
    getAttribute: (n) => attrs[n],
    setAttribute: (n, v) => { attrs[n] = v; },
    querySelector: (s) => (s === '.auto-renew-label' ? label : icon),
  };
}
function mkHwid(id) {
  return { textContent: '0 / ∞', getAttribute: () => String(id) };
}
const buttons = [mkBtn(7), mkBtn(7), mkBtn(8)];
const hwids = [mkHwid(7), mkHwid(8)];
global.document = {
  querySelectorAll: (sel) => (sel.includes('auto-renew') ? buttons : hwids),
  querySelector: () => null,
  addEventListener: () => {},
};
global.window = {};
"""
        + snippet
        + """
_applyAutoRenewState(7, true);
assert.strictEqual(buttons[0].attrs['data-auto-renew'], 'true');
assert.strictEqual(buttons[1].attrs['data-auto-renew'], 'true');
assert.strictEqual(buttons[2].attrs['data-auto-renew'], 'false');
assert.strictEqual(buttons[1].label.textContent, 'Авто: ВКЛ');
assert.ok(buttons[0].classList.has('text-primary'));
assert.ok(!buttons[0].classList.has('bg-white/5'));
_applyAutoRenewState(7, false);
assert.ok(buttons[0].classList.has('bg-white/5'));
assert.ok(!buttons[0].classList.has('text-primary'));
_applyKeyHwidInfo(8, '2 / 5');
assert.strictEqual(hwids[1].textContent, '2 / 5');
assert.strictEqual(hwids[0].textContent, '0 / ∞');
_applyKeyHwidInfo(8, { evil: 1 });
assert.strictEqual(hwids[1].textContent, '2 / 5');
"""
    )
    res = subprocess.run([NODE, str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
