"""Store, Фаза 1: фундамент + точечный refresh баланса после top-up."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import (
    APP_HTML,
    APP_JS,
    STORE_JS,
    mini_app_html,
    mini_app_js,
    mini_app_store_js,
)

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
KEYS = Path("src/shop_bot/webapp/web_router/render_keys.py")
REMAINING_RELOAD_MARKERS = (
    "getElementById('settings-refresh-btn')?.addEventListener('click', () => location.reload())",
    "setTimeout(() => window.location.reload(), 500)",
)


def _store_hash() -> str:
    return hashlib.sha256(STORE_JS.read_bytes()).hexdigest()[:12]


def test_store_js_is_minimal_pubsub_and_linked_before_app_js():
    html = mini_app_html()
    store = mini_app_store_js()
    js = mini_app_js()
    keys = KEYS.read_text(encoding="utf-8")
    assert STORE_JS.is_file()
    assert "subscribe(fn)" in store
    assert "setState(patch)" in store
    assert "async function refreshBalance(" in store
    assert "/api/user-status" in store
    assert "window.store =" not in store
    assert "window.refreshBalance =" not in store
    assert "window.store =" not in js
    assert "window.refreshBalance =" not in js
    assert 'src="{{ store_js_href }}" defer>' in html
    assert html.index('src="{{ store_js_href }}" defer>') < html.index(
        'src="{{ app_js_href }}" defer>'
    )
    assert 'type="module"' not in html
    assert "await refreshBalance({ fallbackBalance: paidData && paidData.balance })" in js
    assert "await refreshBalance({ silent: true })" in js
    assert "id=\"home-balance\"" in keys
    assert 'id="finance-balance" data-balance-display' in html
    assert 'id="topup-success-balance" data-balance-display' in js
    for marker in REMAINING_RELOAD_MARKERS:
        assert marker in js, marker


def test_other_location_reload_sites_were_not_migrated():
    js = mini_app_js()
    assert js.count("location.reload()") == 2
    assert "setTimeout(() => window.location.reload(), 700)" not in js
    assert "setTimeout(() => window.location.reload(), 1200)" not in js


def test_served_page_includes_hashed_store_js(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=16401, username="store-bal")
    token = issue_auth_token(16401)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    expected = f"/static/js/store.js?v={_store_hash()}"
    assert expected in resp.text
    assert 'id="home-balance"' in resp.text
    assert 'data-balance-display' in resp.text
    store_resp = app_client.get("/static/js/store.js")
    assert store_resp.status_code == 200
    assert "async function refreshBalance(" in store_resp.text


def test_refresh_balance_updates_all_dom_nodes_without_reload():
    assert NODE, "нужен node для vm-smoke Store"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

function el(id, extra) {
  const node = {
    id: id || '',
    textContent: extra && extra.textContent || '0.00 ₽',
    attributes: Object.assign({}, extra && extra.attributes),
    getAttribute(name) { return this.attributes[name] || ''; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
  };
  return node;
}

const home = el('home-balance', { textContent: '10.00 ₽', attributes: { 'data-balance-display': '' } });
const finance = el('finance-balance', { textContent: '10.00 ₽', attributes: { 'data-balance-display': '' } });
const success = el('topup-success-balance', { textContent: '…', attributes: { 'data-balance-display': '' } });
const byId = { 'home-balance': home, 'finance-balance': finance, 'topup-success-balance': success };
const extras = [home, finance, success];
let reloadCount = 0;
let notify = [];

const sandbox = {
  console,
  Set,
  Object,
  Number,
  fetch: async () => ({ ok: true, json: async () => ({ ok: true, balance: 150.5 }) }),
  apiFetch: async () => ({ ok: true, json: async () => ({ ok: true, balance: 150.5 }) }),
  document: {
    getElementById(id) { return byId[id] || null; },
    querySelectorAll(sel) { return sel === '[data-balance-display]' ? extras : []; },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.runInNewContext(src, sandbox, { filename: 'store.js' });
sandbox.refreshBalance().then((ok) => {
  console.log(JSON.stringify({
    ok,
    reloadCount,
    storeBalance: sandbox.__store.state.balance,
    home: home.textContent,
    finance: finance.textContent,
    success: success.textContent,
    notify,
    hasWindowStoreAssign: false,
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
    assert result["storeBalance"] == 150.5
    assert result["home"] == "150.50 ₽"
    assert result["finance"] == "150.50 ₽"
    assert result["success"] == "150.50 ₽"
    assert result["notify"] == []


def test_refresh_balance_network_error_keeps_old_value_without_reload():
    assert NODE, "нужен node для vm-smoke ошибки сети"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

function el(id, extra) {
  return { id, textContent: extra.textContent };
}
const home = el('home-balance', { textContent: '10.00 ₽' });
const finance = el('finance-balance', { textContent: '10.00 ₽' });
const success = el('topup-success-balance', { textContent: '10.00 ₽' });
const byId = { 'home-balance': home, 'finance-balance': finance, 'topup-success-balance': success };
let reloadCount = 0;
let notify = [];

function run(fetchImpl, options) {
  reloadCount = 0;
  notify = [];
  home.textContent = '10.00 ₽';
  finance.textContent = '10.00 ₽';
  success.textContent = '10.00 ₽';
  const sandbox = {
    console, Set, Object, Number,
    fetch: fetchImpl,
    apiFetch: fetchImpl,
    document: {
      getElementById(id) { return byId[id] || null; },
      querySelectorAll() { return [home, finance, success]; },
    },
    location: { reload() { reloadCount += 1; } },
    showNotification(msg, type) { notify.push([msg, type]); },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.runInNewContext(src, sandbox, { filename: 'store.js' });
  return sandbox.refreshBalance(options).then((ok) => ({
    ok,
    reloadCount,
    storeBalance: sandbox.__store.state.balance,
    home: home.textContent,
    finance: finance.textContent,
    success: success.textContent,
    notify,
  }));
}

const fail = async () => { throw new Error('network down'); };
Promise.resolve()
  .then(() => run(fail, {}))
  .then((noFallback) => run(fail, { fallbackBalance: 42 }).then((withFallback) => {
    console.log(JSON.stringify({ noFallback, withFallback }));
  }));
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
    assert no_fb["storeBalance"] is None
    assert no_fb["home"] == "10.00 ₽"
    assert no_fb["finance"] == "10.00 ₽"
    assert no_fb["success"] == "10.00 ₽"
    assert no_fb["notify"] == [["Не удалось обновить баланс", "error"]]

    fb = result["withFallback"]
    assert fb["ok"] is True
    assert fb["reloadCount"] == 0
    assert fb["storeBalance"] == 42
    assert fb["home"] == "42.00 ₽"
    assert fb["finance"] == "42.00 ₽"
    assert fb["success"] == "42.00 ₽"
    assert fb["notify"] == []
