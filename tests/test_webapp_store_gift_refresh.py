"""Store, Фаза 3: активация подарка обновляет gifts и ключи без reload."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from conftest import insert_gift_key, insert_user, issue_auth_token
from webapp_frontend_src import STORE_JS, mini_app_js, mini_app_keys_page_js, mini_app_store_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
USER_ID = 16602


def _store_hash() -> str:
    return hashlib.sha256(STORE_JS.read_bytes()).hexdigest()[:12]


def _body(src: str, start: str, end: str) -> str:
    assert start in src, start
    a = src.index(start)
    b = src.index(end, a)
    return src[a:b]


def test_gift_activation_uses_store_instead_of_reload():
    store = mini_app_store_js()
    js = mini_app_js()
    keys_js = mini_app_keys_page_js()
    activate = _body(keys_js, "async function activateOwnGift(", "window._loadKeysPage = async function")
    url_block = _body(keys_js, "// ── Auto-activate gift from URL param", "document.addEventListener('click'")
    pending = _body(js, "// ── Единый сценарий pending action", "// ── Профиль: смена пароля")
    assert "async function refreshAfterGiftActivation(" in store
    assert "function applyGiftsAndKeysToDom(" in store
    assert "store.subscribe(applyGiftsAndKeysToDom)" in store
    assert "window.refreshAfterGiftActivation =" not in store
    assert "window.refreshAfterGiftActivation =" not in js
    assert "window.refreshAfterGiftActivation =" not in keys_js
    assert "location.reload()" not in activate
    assert "location.reload()" not in url_block
    assert "location.reload()" not in pending
    assert "await refreshAfterGiftActivation({ giftCode: giftCode })" in activate
    assert "await refreshAfterGiftActivation({ giftCode: giftCode })" in url_block
    assert "await refreshAfterGiftActivation({ giftCode: d.gift_code || '' })" in pending
    assert js.count("location.reload()") == 1
    assert "getElementById('settings-refresh-btn')?.addEventListener('click', () => location.reload())" in js
    assert "setTimeout(() => window.location.reload(), 500)" not in js
    assert "setTimeout(() => window.location.reload(), 500)" not in keys_js


def test_refresh_after_gift_activation_updates_both_slices_without_reload():
    assert NODE, "нужен node для vm-smoke Store gifts"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

const giftsContent = { classList: { contains() { return true; }, remove() {}, add() {} }, innerHTML: 'OLD-GIFT' };
const keysList = { innerHTML: 'OLD-KEYS', querySelectorAll() { return []; } };
const loading = { style: { display: '' } };
const pagination = { classList: { add() {}, remove() {} }, innerHTML: '' };
let reloadCount = 0;
let notify = [];
let renderedGifts = null;
let paged = 0;

const sandbox = {
  console, Set, Object, Number, Array, String, Promise, JSON,
  DOMParser: class {
    parseFromString(html) {
      return {
        getElementById(id) {
          if (id !== 'profile-keys-list-container') return null;
          return { innerHTML: '<div data-key-id="9" data-key-name="Из подарка"><button class="key-toggle"><div class="text-xs font-bold">Из подарка</div></button></div>' };
        }
      };
    }
  },
  fetch: async (url) => {
    const u = String(url);
    if (u.indexOf('/api/user/gifts') >= 0) {
      return { ok: true, json: async () => ({ ok: true, gifts: [] }), text: async () => '' };
    }
    if (u.indexOf('/api/user-status') >= 0) {
      return { ok: true, json: async () => ({ ok: true, keys: [{ key_id: 9, name: 'Из подарка' }], balance: 1 }), text: async () => '' };
    }
    return { ok: true, json: async () => ({}), text: async () => '<div id="profile-keys-list-container"><div data-key-id="9" data-key-name="Из подарка"></div></div>' };
  },
  document: {
    getElementById(id) {
      if (id === 'gifts-content') return giftsContent;
      if (id === 'gifts-loading') return loading;
      if (id === 'gifts-pagination') return pagination;
      if (id === 'profile-keys-list-container') return keysList;
      return null;
    },
    querySelectorAll() { return []; },
    querySelector() { return null; },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
  renderGiftsPage() { renderedGifts = sandbox.window._giftsState.gifts.slice(); },
  initProfileKeysPagination() { paged += 1; },
  GIFTS_PAGE_SIZE: 5,
};
sandbox.apiFetch = sandbox.fetch;
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.getAuthToken = () => 't';
sandbox.window._currentUserId = 1;
sandbox.window._giftsState = { gifts: [{ gift_code: 'ABC', card_html: '<div data-gift-action="activate"></div>' }], page: 0 };

vm.runInNewContext(src, sandbox, { filename: 'store.js' });
sandbox.refreshAfterGiftActivation({ giftCode: 'ABC' }).then((ok) => {
  console.log(JSON.stringify({
    ok, reloadCount,
    gifts: sandbox.__store.state.gifts,
    keyNames: sandbox.__store.state.keyNames,
    keysHtml: sandbox.__store.state.keysListHtml && sandbox.__store.state.keysListHtml.indexOf('data-key-id="9"') >= 0,
    keysDom: keysList.innerHTML.indexOf('data-key-id="9"') >= 0,
    giftsDomEmpty: giftsContent.innerHTML.indexOf('Нет неактивированных подарков') >= 0,
    renderedGifts,
    paged,
    notify,
    balanceUntouched: sandbox.__store.state.balance,
  }));
});
"""
    proc = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    assert result["ok"] is True
    assert result["reloadCount"] == 0
    assert result["gifts"] == []
    assert result["keyNames"]["9"] == "Из подарка"
    assert result["keysHtml"] is True
    assert result["keysDom"] is True
    assert result["giftsDomEmpty"] is True
    assert result["paged"] == 1
    assert result["notify"] == []
    assert result["balanceUntouched"] is None


def test_gift_refresh_network_error_keeps_lists_or_uses_fallback():
    assert NODE, "нужен node для vm-smoke ошибки сети gifts"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

function makeSandbox(fetchImpl, extras) {
  const giftsContent = { classList: { contains() { return true; }, remove() {}, add() {} }, innerHTML: 'KEEP-GIFT' };
  const keysList = {
    innerHTML: 'KEEP-KEYS',
    querySelectorAll() { return []; },
  };
  extras.giftsContent = giftsContent;
  extras.keysList = keysList;
  const sandbox = {
    console, Set, Object, Number, Array, String, Promise, JSON,
    DOMParser: class { parseFromString() { return { getElementById() { return null; } }; } },
    fetch: fetchImpl,
    apiFetch: fetchImpl,
    document: {
      getElementById(id) {
        if (id === 'gifts-content') return giftsContent;
        if (id === 'gifts-loading') return { style: { display: '' } };
        if (id === 'gifts-pagination') return { classList: { add() {}, remove() {} }, innerHTML: '' };
        if (id === 'profile-keys-list-container') return keysList;
        return null;
      },
      querySelectorAll() { return []; },
    },
    location: { reload() { extras.reloadCount += 1; } },
    showNotification(msg, type) { extras.notify.push([msg, type]); },
    renderGiftsPage() { extras.rendered = (sandbox.window._giftsState.gifts || []).map((g) => g.gift_code); },
    initProfileKeysPagination() {},
    GIFTS_PAGE_SIZE: 5,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.window.getAuthToken = () => 't';
  sandbox.window._giftsState = { gifts: [{ gift_code: 'ABC', card_html: '<div class="gift-card" data-key-id="9"></div>' }], page: 0 };
  vm.runInNewContext(src, sandbox, { filename: 'store.js' });
  sandbox.__store.setState({
    gifts: [{ gift_code: 'ABC', card_html: '<div class="gift-card" data-key-id="9"></div>' }],
  });
  extras.sandbox = sandbox;
  return sandbox;
}

const fail = async () => { throw new Error('network down'); };
const noFallback = { reloadCount: 0, notify: [] };
const withFallback = { reloadCount: 0, notify: [] };

Promise.resolve()
  .then(() => {
    const sb = makeSandbox(fail, noFallback);
    return sb.refreshAfterGiftActivation({}).then((ok) => {
      noFallback.ok = ok;
      noFallback.gifts = sb.__store.state.gifts;
      noFallback.giftsDom = noFallback.giftsContent.innerHTML;
      noFallback.keysDom = noFallback.keysList.innerHTML;
    });
  })
  .then(() => {
    const sb = makeSandbox(fail, withFallback);
    return sb.refreshAfterGiftActivation({ giftCode: 'ABC' }).then((ok) => {
      withFallback.ok = ok;
      withFallback.gifts = sb.__store.state.gifts;
      withFallback.giftsDom = withFallback.giftsContent.innerHTML;
      withFallback.keysDom = withFallback.keysList.innerHTML;
      withFallback.reloadCount = withFallback.reloadCount;
    });
  })
  .then(() => console.log(JSON.stringify({ noFallback: {
    ok: noFallback.ok, reloadCount: noFallback.reloadCount, notify: noFallback.notify,
    giftsDom: noFallback.giftsDom, keysDom: noFallback.keysDom,
    giftsCodes: (noFallback.gifts || []).map((g) => g.gift_code),
  }, withFallback: {
    ok: withFallback.ok, reloadCount: withFallback.reloadCount, notify: withFallback.notify,
    gifts: withFallback.gifts, keysDom: withFallback.keysDom,
  } })));
"""
    proc = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    no_fb = result["noFallback"]
    assert no_fb["ok"] is False
    assert no_fb["reloadCount"] == 0
    assert no_fb["giftsDom"] == "KEEP-GIFT"
    assert no_fb["keysDom"] == "KEEP-KEYS"
    assert no_fb["giftsCodes"] == ["ABC"]
    assert no_fb["notify"] == [["Не удалось обновить список ключей", "error"]]

    fb = result["withFallback"]
    assert fb["ok"] is True
    assert fb["reloadCount"] == 0
    assert fb["gifts"] == []
    assert "gift-card" in fb["keysDom"]
    assert fb["notify"] == []


def test_three_gift_entry_points_call_shared_refresh_without_reload():
    assert NODE, "нужен node для трёх точек входа активации"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const appSrc = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
const keysSrc = fs.readFileSync('src/shop_bot/webapp/static/js/keys-page.js', 'utf8');
const storeSrc = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8');
function sliceApp(start, end) {
  const a = appSrc.indexOf(start);
  const b = appSrc.indexOf(end, a);
  return appSrc.slice(a, b);
}
function sliceKeys(start, end) {
  const a = keysSrc.indexOf(start);
  const b = keysSrc.indexOf(end, a);
  return keysSrc.slice(a, b);
}
const activateSrc = sliceKeys('async function activateOwnGift(', 'window._loadKeysPage = async function');
const urlSrc = sliceKeys('(function checkGiftParam()', 'document.addEventListener(\'click\'');
const pendingSrc = sliceApp("window.addEventListener('appReady', async () => {\n    const pendingToken", '// ── Профиль: смена пароля');

let reloads = 0;
const calls = [];
const listeners = {};
const sandbox = {
  console, Set, Object, Number, Array, String, Promise, JSON, URL,
  RENDERED_USER_ID: 1,
  fetch: async (url) => {
    const u = String(url);
    if (u.indexOf('/api/gift/activate') >= 0 || u.indexOf('/api/webapp/pending-actions/complete') >= 0) {
      return { json: async () => ({ ok: true, message: 'Подарок активирован!', action_type: 'gift', status: 'activated', gift_code: 'ABC' }) };
    }
    throw new Error('no other fetches in this smoke');
  },
  document: { getElementById() { return null; } },
  location: { href: 'https://example.test/?activate_gift=ABC', pathname: '/', reload() { reloads += 1; } },
  history: { replaceState() {} },
  showNotification() {},
  addEventListener(name, fn) { (listeners[name] = listeners[name] || []).push(fn); },
  refreshAfterGiftActivation: async (opts) => { calls.push(opts || {}); return true; },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.Telegram = { WebApp: { initDataUnsafe: { user: { id: 1 } } } };
sandbox.window.getAuthToken = () => 't';
sandbox.window._currentUserId = 1;
sandbox.window._pendingActionToken = 'pend-1';
sandbox.window.addEventListener = sandbox.addEventListener;

vm.runInNewContext(
  storeSrc + '\n' + activateSrc + '\n' + urlSrc + '\n' + pendingSrc + '\n',
  sandbox,
  { filename: 'gift-entries.js' }
);
sandbox.refreshAfterGiftActivation = async (opts) => { calls.push(opts || {}); return true; };
Promise.resolve()
  .then(() => sandbox.activateOwnGift('ABC', { disabled: false, innerHTML: 'x' }))
  .then(() => Promise.all((listeners.appReady || []).map((fn) => fn())))
  .then(() => {
    console.log(JSON.stringify({ reloads, calls }));
  });
"""
    proc = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    assert result["reloads"] == 0
    codes = [c.get("giftCode") for c in result["calls"]]
    assert codes.count("ABC") >= 2
    assert len(result["calls"]) == 3


def test_served_page_and_activate_moves_gift_to_personal(temp_db, app_client, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="store-gift")
    _gift_id, key_id = insert_gift_key(
        database.DB_FILE, from_user_id=USER_ID, gift_code="store-gift-code"
    )
    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "UPDATE vpn_keys SET user_key_name = ? WHERE key_id = ?",
            ("Подарок для Store", key_id),
        )
        conn.commit()

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)
    token = issue_auth_token(USER_ID)
    before = app_client.get("/", params={"token": token})
    assert before.status_code == 200
    expected = f"/static/js/store.js?v={_store_hash()}"
    assert expected in before.text
    personal = before.text.split('id="profile-keys-list-container"', 1)[1].split(
        'id="profile-keys-pagination"', 1
    )[0]
    assert "Подарок для Store" not in personal
    gifts_before = app_client.post(
        "/api/user/gifts", json={"token": token, "user_id": USER_ID}
    ).json()
    assert [g["gift_code"] for g in gifts_before["gifts"]] == ["store-gift-code"]

    activated = app_client.post(
        "/api/gift/activate",
        json={"gift_code": "store-gift-code", "token": token, "user_id": USER_ID},
    )
    assert activated.status_code == 200
    assert activated.json().get("ok") is True

    after = app_client.get("/", params={"token": token})
    personal_after = after.text.split('id="profile-keys-list-container"', 1)[1].split(
        'id="profile-keys-pagination"', 1
    )[0]
    assert "Подарок для Store" in personal_after
    gifts_after = app_client.post(
        "/api/user/gifts", json={"token": token, "user_id": USER_ID}
    ).json()
    assert gifts_after.get("gifts") == []
    store_js = app_client.get("/static/js/store.js")
    assert "async function refreshAfterGiftActivation(" in store_js.text
