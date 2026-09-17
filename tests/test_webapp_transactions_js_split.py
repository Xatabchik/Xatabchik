"""Шаг 1 split app.js: история операций вынесена в transactions.js 1:1."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import (
    TRANSACTIONS_JS,
    mini_app_html,
    mini_app_js,
    mini_app_transactions_js,
)

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]


def _tx_hash() -> str:
    return hashlib.sha256(TRANSACTIONS_JS.read_bytes()).hexdigest()[:12]


def test_transactions_module_holds_history_code_and_app_js_does_not():
    html = mini_app_html()
    app_js = mini_app_js()
    tx_js = mini_app_transactions_js()
    assert TRANSACTIONS_JS.is_file()
    assert "async function loadTransactions(" in tx_js
    assert "window._loadFinancePage = async function" in tx_js
    assert "closest('[data-tx-action]')" in tx_js
    assert "getElementById('finance-tx-all-btn')?.addEventListener('click', () => openActionModal('transactions', null))" in tx_js
    assert "/api/user/transactions?page=' + _txPage + '&per_page=10'" in tx_js
    assert "/api/user/transactions?page=1&per_page=3" in tx_js
    assert "data-tx-action=\"page-next\"" in tx_js
    assert "async function loadTransactions(" not in app_js
    assert "window._loadFinancePage = async function" not in app_js
    assert "closest('[data-tx-action]')" not in app_js
    assert "getElementById('finance-tx-all-btn')" not in app_js
    assert "loadTransactions(1)" in app_js
    assert "window._loadFinancePage && window._loadFinancePage()" in app_js
    assert 'src="{{ store_js_href }}" defer>' in html
    assert 'src="{{ transactions_js_href }}" defer>' in html
    assert 'src="{{ app_js_href }}" defer>' in html
    assert html.index('src="{{ store_js_href }}" defer>') < html.index(
        'src="{{ transactions_js_href }}" defer>'
    )
    assert html.index('src="{{ transactions_js_href }}" defer>') < html.index(
        'src="{{ app_js_href }}" defer>'
    )
    assert 'type="module"' not in html
    assert "eval(" not in tx_js
    assert "new Function" not in tx_js
    assert "window.loadTransactions = loadTransactions" not in tx_js


def test_served_page_includes_hashed_transactions_js(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=16801, username="tx-split")
    token = issue_auth_token(16801)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    expected = f"/static/js/transactions.js?v={_tx_hash()}"
    assert expected in resp.text
    assert resp.text.index("/static/js/store.js") < resp.text.index("/static/js/transactions.js")
    assert resp.text.index("/static/js/transactions.js") < resp.text.index("/static/js/app.js")
    js_resp = app_client.get("/static/js/transactions.js")
    assert js_resp.status_code == 200
    assert "async function loadTransactions(" in js_resp.text
    cc = js_resp.headers.get("cache-control", "").lower()
    assert "must-revalidate" in cc or "max-age=0" in cc


def test_load_transactions_pagination_and_finance_preview_in_node():
    assert NODE, "нужен node для vm-smoke transactions.js"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/transactions.js', 'utf8');

function classList(initial) {
  const set = new Set(String(initial || '').split(/\s+/).filter(Boolean));
  return {
    add(name) { set.add(name); },
    remove(name) { set.delete(name); },
    toggle(name, force) {
      if (force === true) set.add(name);
      else if (force === false) set.delete(name);
      else if (set.has(name)) set.delete(name);
      else set.add(name);
    },
    contains(name) { return set.has(name); },
    toString() { return [...set].join(' '); }
  };
}

function el(id, extra) {
  const node = {
    tagName: (extra && extra.tagName) || 'DIV',
    className: (extra && extra.className) || '',
    classList: classList(extra && extra.className),
    style: Object.assign({}, extra && extra.style),
    value: extra && extra.value || '',
    textContent: extra && extra.textContent || '',
    innerHTML: extra && extra.innerHTML || '',
    disabled: !!(extra && extra.disabled),
    listeners: {},
    children: [],
    parent: extra && extra.parent || null,
    attributes: Object.assign({}, extra && extra.attributes),
    addEventListener(type, fn) {
      (this.listeners[type] || (this.listeners[type] = [])).push(fn);
    },
    getAttribute(name) {
      if (this.attributes[name] != null) return this.attributes[name];
      return '';
    },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    closest(sel) {
      let n = this;
      while (n) {
        const attrs = n.attributes || {};
        if (sel === '[data-tx-action]' && attrs['data-tx-action']) return n;
        n = n.parent;
      }
      return null;
    },
    click() {
      (this.listeners.click || []).forEach((fn) => fn({ type: 'click', target: this, stopPropagation() {} }));
    }
  };
  node.id = id || '';
  return node;
}

const fetches = [];
const opened = [];
const contentEl = el('action-modal-content');
const previewEl = el('finance-transactions-preview');
const allBtn = el('finance-tx-all-btn', { tagName: 'BUTTON' });
const byId = {
  'action-modal-content': contentEl,
  'finance-transactions-preview': previewEl,
  'finance-tx-all-btn': allBtn,
};
const documentClicks = [];
const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  setTimeout(fn) { if (typeof fn === 'function') fn(); return 1; },
  clearTimeout() {},
  parseInt, Number, String, Boolean, Array, Object, JSON, Date, Math, Error,
  Promise, Map, Set, isNaN, isFinite, encodeURIComponent,
  Telegram: { WebApp: { initDataUnsafe: { user: { id: 16801 } } } },
  RENDERED_USER_ID: 16801,
  fetch(url) {
    fetches.push(String(url));
    const pageMatch = String(url).match(/page=(\d+)/);
    const page = pageMatch ? parseInt(pageMatch[1], 10) : 1;
    const perMatch = String(url).match(/per_page=(\d+)/);
    const per = perMatch ? parseInt(perMatch[1], 10) : 10;
    const txs = [];
    for (let i = 0; i < 12; i++) {
      txs.push({
        action_label: 'Операция ' + (i + 1),
        payment_method: 'YooKassa',
        created_date: '2026-09-17 00:00:00',
        amount_rub: 100 + i,
        status: 'paid',
        status_label: 'Оплачено',
        provider_transaction_id: 'p' + i
      });
    }
    const start = (page - 1) * per;
    return Promise.resolve({
      json: () => Promise.resolve({
        ok: true,
        total: 12,
        has_more: start + per < 12,
        transactions: txs.slice(start, start + per)
      }),
      ok: true
    });
  },
  document: {
    readyState: 'complete',
    getElementById(id) { return byId[id] || null; },
    addEventListener(type, fn) {
      if (type === 'click') documentClicks.push(fn);
    },
    createElement(tag) { return el('', { tagName: String(tag).toUpperCase() }); }
  },
  window: {},
  location: { href: 'https://mini.test/', hash: '' },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.apiFetch = function (url, opts) { return sandbox.fetch(url, opts); };
sandbox.refreshBalance = async function () { return true; };
sandbox.openActionModal = function (type, keyId) { opened.push([type, keyId]); };

let threw = null;
try { vm.runInNewContext(src, sandbox, { filename: 'transactions.js' }); }
catch (e) { threw = e && e.stack ? e.stack : String(e); }

function fireDoc(target) {
  const evt = { type: 'click', target, stopPropagation() {}, preventDefault() {} };
  documentClicks.forEach((fn) => fn(evt));
}

Promise.resolve()
  .then(async () => {
    await sandbox.loadTransactions(1);
    const page1 = contentEl.innerHTML;
    const nextBtn = el('tx-next', { tagName: 'BUTTON', attributes: { 'data-tx-action': 'page-next' } });
    fireDoc(nextBtn);
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await sandbox._loadFinancePage();
    allBtn.click();
    return {
      threw,
      page1HasNext: /data-tx-action="page-next"/.test(page1),
      page1HasOnclick: /onclick=/.test(page1),
      page1Label: /Операция 1/.test(page1),
      page2: contentEl.innerHTML,
      fetches: fetches.slice(),
      preview: previewEl.innerHTML,
      opened: opened.slice(),
      clickHandlers: documentClicks.length,
    };
  })
  .then((r) => console.log(JSON.stringify(r)))
  .catch((e) => {
    console.log(JSON.stringify({ threw: String(e && e.stack || e) }));
    process.exitCode = 1;
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
    assert result.get("threw") in (None, "null") or result["threw"] is None, result.get("threw")
    assert result["clickHandlers"] == 1
    assert result["page1HasNext"] is True
    assert result["page1HasOnclick"] is False
    assert result["page1Label"] is True
    assert "Операция 11" in result["page2"]
    assert "/api/user/transactions?page=1&per_page=10" in result["fetches"]
    assert "/api/user/transactions?page=2&per_page=10" in result["fetches"]
    assert "/api/user/transactions?page=1&per_page=3" in result["fetches"]
    assert "Операция 1" in result["preview"]
    assert "Операция 4" not in result["preview"]
    assert result["opened"] == [["transactions", None]]
