"""Store, Фаза 2: точечный refresh названия ключа после rename без reload."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

from webapp_frontend_src import (
    STORE_JS,
    mini_app_js,
    mini_app_store_js,
)

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
USER_ID = 16502


def _store_hash() -> str:
    return hashlib.sha256(STORE_JS.read_bytes()).hexdigest()[:12]


def _rename_body() -> str:
    js = mini_app_js()
    start = "async function renameKey("
    end = "async function deleteAllDevices("
    assert start in js
    start_idx = js.index(start)
    end_idx = js.index(end, start_idx)
    return js[start_idx:end_idx]


def _insert_key(db_path: Path, *, user_id: int, email: str, user_key_name: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, user_key_name
            ) VALUES (?, 'RenameHost', ?, ?, 'https://sub.example/rename',
                      datetime('now', '+30 days'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            """,
            (user_id, email, email, user_key_name),
        )
        key_id = cur.lastrowid
        conn.commit()
    return int(key_id)


def test_rename_uses_store_keynames_instead_of_reload():
    store = mini_app_store_js()
    js = mini_app_js()
    rename = _rename_body()
    assert "keyNames: {}" in store
    assert "async function refreshKeyName(" in store
    assert "function applyKeyNamesToDom(" in store
    assert "store.subscribe(applyKeyNamesToDom)" in store
    assert "window.refreshKeyName =" not in store
    assert "window.refreshKeyName =" not in js
    assert "setTimeout(() => window.location.reload(), 700)" not in js
    assert "location.reload()" not in rename
    assert "await refreshKeyName(keyId, { fallbackName: newName })" in rename
    assert "Название обновлено!" in rename
    assert "Название удалено" in rename
    assert js.count("location.reload()") == 2
    assert "getElementById('settings-refresh-btn')?.addEventListener('click', () => location.reload())" in js
    assert "setTimeout(() => window.location.reload(), 500)" in js
    assert "setTimeout(() => window.location.reload(), 1200)" not in js
    assert "setTimeout(() => location.reload(), 1800)" not in js


def test_refresh_key_name_updates_cards_dropdown_and_display_without_reload():
    assert NODE, "нужен node для vm-smoke Store rename"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

function node(extra) {
  const n = Object.assign({
    textContent: '',
    attributes: {},
    children: [],
    getAttribute(name) { return this.attributes[name] || ''; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    querySelector(sel) {
      if (sel.indexOf('font-bold') >= 0) return this.title || null;
      return null;
    },
  }, extra || {});
  n.attributes = Object.assign({}, extra && extra.attributes);
  return n;
}

const cardTitle = { textContent: 'Старое имя' };
const card = node({
  attributes: { 'data-key-id': '42', 'data-key-name': 'Старое имя' },
  title: cardTitle,
});
const rebuiltTitle = { textContent: 'SSR stale' };
let liveCard = card;
const optTitle = { textContent: 'Старое имя' };
const opt = node({
  attributes: { 'data-key': '#42', 'data-name': 'Старое имя', 'data-date': '01.01.2027' },
  title: optTitle,
});
const display = { id: 'display-selected-key', textContent: 'Старое имя • До 01.01.2027' };
let reloadCount = 0;
let notify = [];

const sandbox = {
  console, Set, Object, Number, Array, String,
  fetch: async () => ({ ok: true, json: async () => ({
    ok: true, balance: 10, keys: [{ key_id: 42, name: 'Рабочий VPN' }],
  }) }),
  apiFetch: async () => ({ ok: true, json: async () => ({
    ok: true, balance: 10, keys: [{ key_id: 42, name: 'Рабочий VPN' }],
  }) }),
  document: {
    getElementById(id) { return id === 'display-selected-key' ? display : null; },
    querySelector(sel) {
      if (sel === '.dropdown-option[data-key="#42"]') return opt;
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '[data-key-id="42"]') return [liveCard];
      if (sel === '.dropdown-option[data-key="#42"]') return [opt];
      if (sel === '[data-balance-display]') return [];
      return [];
    },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.selectedKeyId = '42';

vm.runInNewContext(src, sandbox, { filename: 'store.js' });
sandbox.refreshKeyName(42, { fallbackName: 'локальный fallback' }).then((ok) => {
  const afterFirst = {
    ok, reloadCount,
    storeName: sandbox.__store.state.keyNames['42'],
    cardName: card.getAttribute('data-key-name'),
    cardTitle: cardTitle.textContent,
    optName: opt.getAttribute('data-name'),
    optTitle: optTitle.textContent,
    display: display.textContent,
    notify,
    balanceUntouched: sandbox.__store.state.balance,
  };
  liveCard = node({
    attributes: { 'data-key-id': '42', 'data-key-name': 'innerHTML rebuild' },
    title: rebuiltTitle,
  });
  sandbox.__store.setState({ keyNames: Object.assign({}, sandbox.__store.state.keyNames) });
  console.log(JSON.stringify({
    afterFirst,
    afterRebuild: {
      reloadCount,
      rebuiltName: liveCard.getAttribute('data-key-name'),
      rebuiltTitle: rebuiltTitle.textContent,
      oldCardStill: card.getAttribute('data-key-name'),
    },
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
    first = result["afterFirst"]
    assert first["ok"] is True
    assert first["reloadCount"] == 0
    assert first["storeName"] == "Рабочий VPN"
    assert first["cardName"] == "Рабочий VPN"
    assert first["cardTitle"] == "Рабочий VPN"
    assert first["optName"] == "Рабочий VPN"
    assert first["optTitle"] == "Рабочий VPN"
    assert first["display"] == "Рабочий VPN • До 01.01.2027"
    assert first["notify"] == []
    assert first["balanceUntouched"] is None
    rebuilt = result["afterRebuild"]
    assert rebuilt["reloadCount"] == 0
    assert rebuilt["rebuiltName"] == "Рабочий VPN"
    assert rebuilt["rebuiltTitle"] == "Рабочий VPN"


def test_refresh_key_name_network_error_keeps_old_value_without_reload():
    assert NODE, "нужен node для vm-smoke ошибки сети rename"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

function node(extra) {
  const n = {
    textContent: extra.textContent || '',
    attributes: Object.assign({}, extra.attributes),
    title: extra.title,
    getAttribute(name) { return this.attributes[name] || ''; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    querySelector() { return this.title || null; },
  };
  return n;
}

const title = { textContent: 'Старое имя' };
const card = node({
  textContent: '',
  attributes: { 'data-key-id': '7', 'data-key-name': 'Старое имя' },
  title,
});
let reloadCount = 0;
let notify = [];

function run(fetchImpl, options) {
  reloadCount = 0;
  notify = [];
  title.textContent = 'Старое имя';
  card.setAttribute('data-key-name', 'Старое имя');
  const sandbox = {
    console, Set, Object, Number, Array, String,
    fetch: fetchImpl,
    apiFetch: fetchImpl,
    document: {
      getElementById() { return null; },
      querySelector() { return null; },
      querySelectorAll(sel) {
        if (sel === '[data-key-id="7"]') return [card];
        return [];
      },
    },
    location: { reload() { reloadCount += 1; } },
    showNotification(msg, type) { notify.push([msg, type]); },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.runInNewContext(src, sandbox, { filename: 'store.js' });
  return sandbox.refreshKeyName(7, options).then((ok) => ({
    ok, reloadCount,
    storeName: sandbox.__store.state.keyNames['7'] || null,
    cardName: card.getAttribute('data-key-name'),
    title: title.textContent,
    notify,
  }));
}

const fail = async () => { throw new Error('network down'); };
Promise.resolve()
  .then(() => run(fail, {}))
  .then((noFallback) => run(fail, { fallbackName: 'Office' }).then((withName) =>
    run(fail, { fallbackName: '' }).then((emptyName) => {
      console.log(JSON.stringify({ noFallback, withName, emptyName }));
    })
  ));
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
    assert no_fb["storeName"] is None
    assert no_fb["cardName"] == "Старое имя"
    assert no_fb["title"] == "Старое имя"
    assert no_fb["notify"] == [["Не удалось обновить название ключа", "error"]]

    named = result["withName"]
    assert named["ok"] is True
    assert named["reloadCount"] == 0
    assert named["storeName"] == "Office"
    assert named["cardName"] == "Office"
    assert named["title"] == "Office"
    assert named["notify"] == []

    emptied = result["emptyName"]
    assert emptied["ok"] is True
    assert emptied["reloadCount"] == 0
    assert emptied["storeName"] == "Ключ #7"
    assert emptied["cardName"] == "Ключ #7"
    assert emptied["notify"] == []


def test_rename_key_action_refreshes_dom_without_reload():
    assert NODE, "нужен node для vm-smoke renameKey"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const storeSrc = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8');
const appSrc = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
const a = appSrc.indexOf('async function renameKey(');
const b = appSrc.indexOf('async function deleteAllDevices(', a);
const renameSrc = appSrc.slice(a, b);

const title = { textContent: 'Старое имя' };
const card = {
  attributes: { 'data-key-id': '42', 'data-key-name': 'Старое имя' },
  getAttribute(name) { return this.attributes[name] || ''; },
  setAttribute(name, value) { this.attributes[name] = String(value); },
  querySelector() { return title; },
};
const renameBtn = { innerHTML: 'save-name', disabled: false };
let reloadCount = 0;
let notify = [];
let closed = 0;
const fetches = [];

const sandbox = {
  console, Set, Object, Number, Array, String,
  RENDERED_USER_ID: 1,
  fetch: async (url, opts) => {
    fetches.push(url);
    if (String(url).indexOf('/api/key/rename') >= 0) {
      return { ok: true, json: async () => ({ ok: true }) };
    }
    return { ok: true, json: async () => ({
      ok: true, keys: [{ key_id: 42, name: 'Рабочий VPN' }],
    }) };
  },
  document: {
    getElementById(id) {
      if (id === 'action-rename-btn') return renameBtn;
      if (id === 'action-rename-input') return { value: 'Рабочий VPN' };
      return null;
    },
    querySelector() { return null; },
    querySelectorAll(sel) {
      if (sel === '[data-key-id="42"]') return [card];
      return [];
    },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
  closeActionModal() { closed += 1; },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.Telegram = { WebApp: { initDataUnsafe: { user: { id: 1 } } } };
sandbox.window.getAuthToken = () => 't';
sandbox.apiFetch = sandbox.fetch;

vm.runInNewContext(storeSrc + '\n' + renameSrc + '\n', sandbox, { filename: 'rename.js' });
sandbox.renameKey(42, false).then(() => {
  console.log(JSON.stringify({
    reloadCount,
    closed,
    notify,
    cardName: card.getAttribute('data-key-name'),
    title: title.textContent,
    btnHtml: renameBtn.innerHTML,
    btnDisabled: renameBtn.disabled,
    fetches,
    storeName: sandbox.store ? sandbox.store.state.keyNames['42'] : null,
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
    assert result["reloadCount"] == 0
    assert result["closed"] == 1
    assert result["notify"] == [["Название обновлено!", "success"]]
    assert result["cardName"] == "Рабочий VPN"
    assert result["title"] == "Рабочий VPN"
    assert result["btnDisabled"] is False
    assert result["btnHtml"] == "save-name"
    assert any("/api/key/rename" in str(u) for u in result["fetches"])
    assert any("/api/user-status" in str(u) for u in result["fetches"])


def test_served_page_includes_key_cards_and_hashed_store_js(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="store-rename")
    key_id = _insert_key(
        database.DB_FILE,
        user_id=USER_ID,
        email="rename@bot.local",
        user_key_name="До переименования",
    )
    token = issue_auth_token(USER_ID)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    expected = f"/static/js/store.js?v={_store_hash()}"
    assert expected in resp.text
    assert f'data-key-id="{key_id}"' in resp.text
    assert 'data-key-name="До переименования"' in resp.text
    store_resp = app_client.get("/static/js/store.js")
    assert store_resp.status_code == 200
    assert "async function refreshKeyName(" in store_resp.text
    assert "async function refreshBalance(" in store_resp.text

    renamed = app_client.post(
        "/api/key/rename",
        json={"user_id": USER_ID, "key_id": key_id, "new_name": "Рабочий VPN", "token": token},
    )
    assert renamed.status_code == 200
    assert renamed.json().get("ok") is True
    status = app_client.get("/api/user-status", params={"token": token})
    assert status.status_code == 200
    payload = status.json()
    assert payload.get("ok") is True
    match = next(k for k in payload["keys"] if int(k["key_id"]) == key_id)
    assert match["name"] == "Рабочий VPN"
    hard = app_client.get("/", params={"token": token})
    assert 'data-key-name="Рабочий VPN"' in hard.text
