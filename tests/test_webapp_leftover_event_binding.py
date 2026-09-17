"""Этап 2 PR 11: leftover window.* bridges из #152 без inline onclick."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js, mini_app_transactions_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
KEYS = Path("src/shop_bot/webapp/web_router/render_keys.py")
PLANS = Path("src/shop_bot/webapp/web_router/render_plans.py")
GIFTS = Path("src/shop_bot/webapp/web_router/gifts.py")
REMOVED_BRIDGES = (
    "setPurchaseMode",
    "openActionModal",
    "closeActionModal",
    "loadTransactions",
    "changeProfileKeysPage",
    "copyToClipboard",
    "activateOwnGift",
    "changeGiftsPage",
    "syncTelegram",
    "goToRenewKey",
    "toggleKeyAutoRenew",
    "openLteTopup",
)


def _button_after(html: str, marker: str) -> str:
    return html.split(marker, 1)[1].split("</button>", 1)[0]


def test_leftover_static_elements_have_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    keys = KEYS.read_text(encoding="utf-8")
    plans = PLANS.read_text(encoding="utf-8")
    gifts = GIFTS.read_text(encoding="utf-8")
    for marker in (
        'id="keys-buy-btn"',
        'id="keys-gift-btn"',
        'id="keys-renew-shortcut-btn"',
        'id="purchase-mode-self"',
        'id="purchase-mode-gift"',
        'id="server-info-toggle"',
        'id="renew-info-toggle"',
        'id="finance-tx-all-btn"',
        'id="action-modal-close-btn"',
        'id="action-backdrop"',
    ):
        chunk = html.split(marker, 1)[1][:400]
        assert "onclick=" not in chunk, marker
    assert 'onclick="setPurchaseMode(' not in html
    assert 'onclick="openActionModal(' not in html
    assert 'onclick="closeActionModal(' not in html
    assert 'onclick="toggleInfoBlock(' not in html
    assert 'onclick="toggleRenewInfoBlock(' not in html
    assert 'onclick="selectPlan(' not in html
    assert 'onclick="selectServer(' not in plans
    assert 'onclick="selectPlan(' not in plans
    assert 'onclick="goToRenewKey(' not in keys
    assert 'onclick="toggleKeyAutoRenew(' not in keys
    assert 'onclick="openLteTopup(' not in keys
    assert 'onclick="syncTelegram(' not in keys
    assert 'onclick="copyToClipboard(' not in gifts
    assert 'onclick="activateOwnGift(' not in gifts
    assert 'onclick="loadTransactions(' not in js
    assert 'onclick="changeProfileKeysPage(' not in js
    assert 'onclick="changeGiftsPage(' not in js
    assert 'onclick="copyToClipboard(' not in js
    assert 'onclick="activateOwnGift(' not in js
    assert 'onclick="closeActionModal(' not in js
    assert 'data-action-modal="close"' in html
    assert 'data-key-action="renew"' in keys
    assert 'data-key-action="auto-renew"' in keys
    assert 'data-key-action="lte-topup"' in keys
    assert 'data-copy-action="clipboard"' in gifts
    assert 'data-gift-action="activate"' in gifts
    assert "closest('[data-action-modal]')" in js
    assert "closest('[data-copy-action=\"clipboard\"]')" in js or "closest('[data-copy-action=" in js
    assert "setAttribute('data-auto-renew'" in js
    assert "onclick=" not in html
    assert "getElementById('purchase-mode-self')?.addEventListener('click', () => setPurchaseMode('new'))" in js
    assert "getElementById('finance-tx-all-btn')?.addEventListener('click', () => openActionModal('transactions', null))" not in js
    assert "getElementById('finance-tx-all-btn')?.addEventListener('click', () => openActionModal('transactions', null))" in mini_app_transactions_js()
    assert "Temporary compatibility bridge" not in js


def test_removed_leftover_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.selectPlan = function" not in js
    assert "window.selectServer = function" not in js
    assert "window.selectRenewKey = function" not in js
    assert "window.toggleInfoBlock = function" not in js
    assert "window.toggleRenewInfoBlock = function" not in js


def test_served_page_leftover_uses_data_attrs(temp_db, app_client, monkeypatch):
    import sqlite3

    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=16301, username="leftover-bind")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, comment_key, user_key_name
            ) VALUES (16301, 'LeftHost', 'left@bot.local', 'left@bot.local',
                      'https://sub.example/left', datetime('now', '+30 days'),
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '', 'PR11 Key')
            """
        )
        conn.commit()

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)
    token = issue_auth_token(16301)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert "PR11 Key" in html
    assert 'onclick="setPurchaseMode(' not in html
    assert 'onclick="openActionModal(' not in html
    assert 'onclick="closeActionModal(' not in html
    assert 'onclick="goToRenewKey(' not in html
    assert 'onclick="selectPlan(' not in html
    assert 'onclick="selectServer(' not in html
    assert 'data-key-action="renew"' in html
    assert 'data-action-modal="close"' in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "closest('[data-action-modal]')" in js.text
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js.text, name


def test_leftover_event_binding_in_node():
    assert NODE, "нужен node для проверки addEventListener"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/transactions.js', 'utf8')
  + '\n' + fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');

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
    disabled: false,
    listeners: {},
    children: [],
    parent: extra && extra.parent || null,
    previousElementSibling: extra && extra.previousElementSibling || null,
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
        if (sel === '[data-action-modal]' && attrs['data-action-modal']) return n;
        if (sel === '[data-tx-action]' && attrs['data-tx-action']) return n;
        if (sel === '[data-copy-action="clipboard"]' && attrs['data-copy-action'] === 'clipboard') return n;
        if (sel === '[data-gift-action="activate"]' && attrs['data-gift-action'] === 'activate') return n;
        if (sel === '[data-sync-telegram]' && attrs['data-sync-telegram']) return n;
        if (sel === '.plan-btn' && (n.className || '').split(/\s+/).includes('plan-btn')) return n;
        if (sel === '#renew-page') return null;
        if (sel === '[data-key-action]' && attrs['data-key-action']) return n;
        n = n.parent;
      }
      return null;
    },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    contains() { return false; },
    focus() {},
    click() {
      (this.listeners.click || []).forEach((fn) => fn({ type: 'click', target: this, stopPropagation() {} }));
    }
  };
  node.id = id || '';
  return node;
}

const fetches = [];
const copied = [];
const opened = [];
const contentEl = el('action-modal-content');
const modal = el('action-modal', { className: 'hidden' });
const purchaseSelf = el('purchase-mode-self', { tagName: 'BUTTON' });
const payBtn = el('pay-button', { tagName: 'BUTTON' });
payBtn.disabled = true;
const payText = el('pay-button-text', { textContent: 'Выберите тариф' });
const toast = el('toast-container');
toast.appendChild = function () {};

const byId = {
  'action-modal': modal,
  'action-backdrop': el('action-backdrop', { className: 'opacity-0 pointer-events-none' }),
  'action-card': el('action-card', { className: 'translate-y-full' }),
  'action-modal-title': el('action-modal-title'),
  'action-modal-content': contentEl,
  'toast-container': toast,
  'home-page': el('home-page'),
  'keys-page': el('keys-page'),
  'finance-page': el('finance-page'),
  'referral-page': el('referral-page'),
  'support-page': el('support-page'),
  'purchase-page': el('purchase-page'),
  'renew-page': el('renew-page'),
  'setup-page': el('setup-page'),
  'nav-keys': el('nav-keys', { className: 'nav-tab' }),
  'nav-finance': el('nav-finance', { className: 'nav-tab' }),
  'nav-home': el('nav-home', { className: 'nav-tab' }),
  'nav-referral': el('nav-referral', { className: 'nav-tab' }),
  'nav-support': el('nav-support', { className: 'nav-tab' }),
  'bottom-nav': el('bottom-nav'),
  'keys-search-input': el('keys-search-input'),
  'keys-search-clear': el('keys-search-clear', { className: 'hidden' }),
  'menu-dots-btn': el('menu-dots-btn'),
  'settings-menu': el('settings-menu', { className: 'hidden' }),
  'settings-refresh-btn': el('settings-refresh-btn'),
  'edit-profile-btn-menu': el('edit-profile-btn-menu'),
  'logout-btn-menu': el('logout-btn-menu'),
  'withdraw-request-btn': el('withdraw-request-btn', { tagName: 'BUTTON' }),
  'referral-methods-btn': el('referral-methods-btn', { tagName: 'BUTTON' }),
  'topup-finance-btn': el('topup-finance-btn', { tagName: 'BUTTON' }),
  'purchase-mode-self': purchaseSelf,
  'purchase-mode-gift': el('purchase-mode-gift', { tagName: 'BUTTON' }),
  'pay-button': payBtn,
  'pay-button-text': payText,
  'renew-pay-button': el('renew-pay-button', { tagName: 'BUTTON' }),
  'renew-pay-button-text': el('renew-pay-button-text'),
  'dropdown-trigger': el('dropdown-trigger', { tagName: 'BUTTON' }),
  'key-dropdown': el('key-dropdown', { className: 'pointer-events-none opacity-0 scale-95' }),
  'dropdown-arrow': el('dropdown-arrow'),
  'server-dropdown-trigger': el('server-dropdown-trigger', { tagName: 'BUTTON' }),
  'server-dropdown': el('server-dropdown', { className: 'pointer-events-none opacity-0 scale-95' }),
  'server-dropdown-arrow': el('server-dropdown-arrow'),
  'display-selected-server': el('display-selected-server'),
  'server-info-toggle': el('server-info-toggle', { tagName: 'BUTTON', className: 'hidden' }),
  'renew-info-toggle': el('renew-info-toggle', { tagName: 'BUTTON', className: 'hidden' }),
  'finance-tx-all-btn': el('finance-tx-all-btn', { tagName: 'BUTTON' }),
  'keys-buy-btn': el('keys-buy-btn', { tagName: 'BUTTON' }),
  'keys-gift-btn': el('keys-gift-btn', { tagName: 'BUTTON' }),
  'keys-renew-shortcut-btn': el('keys-renew-shortcut-btn', { tagName: 'BUTTON' }),
  'gifts-content': el('gifts-content'),
  'gifts-pagination': el('gifts-pagination', { className: 'hidden' }),
};

const documentClicks = [];
const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  setTimeout(fn) { if (typeof fn === 'function') fn(); return 1; },
  clearTimeout() {},
  setInterval() { return 1; },
  clearInterval() {},
  parseInt, Number, String, Boolean, Array, Object, JSON, Date, Math, Error, TypeError,
  Promise, Map, Set, WeakMap, isNaN, isFinite, encodeURIComponent, decodeURIComponent,
  Uint8Array, URL, TextEncoder: function () { return { encode: () => new Uint8Array() }; },
  navigator: { clipboard: { writeText: (t) => { copied.push(t); return Promise.resolve(); } } },
  localStorage: { _d: {}, getItem(k) { return this._d[k] || null; }, setItem(k,v) { this._d[k]=String(v); }, removeItem(k) { delete this._d[k]; } },
  matchMedia() { return { matches: true, addEventListener() {} }; },
  Telegram: { WebApp: { initData: '', initDataUnsafe: {}, version: '7.0', platform: 'tdesktop', ready() {}, expand() {},
    onEvent() {}, offEvent() {}, setHeaderColor() {}, setBackgroundColor() {},
    isVersionAtLeast() { return true; } } },
  fetch(url, opts) {
    fetches.push({ url, body: opts && opts.body });
    let payload = { ok: true };
    if (String(url).indexOf('/api/user/transactions') >= 0) {
      payload = { ok: true, total: 12, has_more: true, transactions: [
        { action_label: 'Пополнение', payment_method: 'YooKassa', created_date: '2026-09-17 00:00:00', amount_rub: 100, status: 'paid', status_label: 'Оплачено' }
      ]};
    }
    if (String(url).indexOf('/api/gift/activate') >= 0) {
      payload = { ok: true, message: 'activated' };
    }
    return Promise.resolve({ json: () => Promise.resolve(payload), ok: true });
  },
  document: {
    readyState: 'complete',
    body: el('body'),
    documentElement: { style: { setProperty() {} }, classList: classList('') },
    getElementById(id) { return byId[id] || null; },
    querySelector() { return null; },
    querySelectorAll(sel) {
      if (sel && sel.indexOf('.plan-btn') >= 0) return [];
      return [];
    },
    addEventListener(type, fn) {
      if (type === 'click') documentClicks.push(fn);
    },
    createElement(tag) { return el('', { tagName: String(tag).toUpperCase() }); }
  },
  window: {},
  location: { href: 'https://mini.test/', hash: '', reload() {} },
  RENDERED_USER_ID: 1,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.document.defaultView = sandbox;
sandbox.getAuthToken = function () { return 't'; };
sandbox.apiFetch = function (url, opts) { return sandbox.fetch(url, opts); };
sandbox.open = function (url) { opened.push(String(url)); };
sandbox._currentUserId = 1;
sandbox.addEventListener = function () {};
sandbox.removeEventListener = function () {};
sandbox.dispatchEvent = function () { return true; };
sandbox.getComputedStyle = function () { return { backgroundColor: 'rgb(0,0,0)' }; };
sandbox.getTgInitData = function () { return ''; };
sandbox.innerHeight = 800;
sandbox.innerWidth = 400;
sandbox.visualViewport = { height: 800, addEventListener() {} };
sandbox.history = { replaceState() {} };
sandbox.HTMLElement = function () {};
sandbox.Node = function () {};
sandbox.Event = function (type) { this.type = type; };
sandbox.requestAnimationFrame = (fn) => { fn(); return 1; };

let threw = null;
try { vm.runInNewContext(src, sandbox, { filename: 'app.js' }); }
catch (e) { threw = e && e.stack ? e.stack : String(e); }

function fireDoc(target) {
  const evt = { type: 'click', target, stopPropagation() {}, preventDefault() {} };
  documentClicks.forEach((fn) => fn(evt));
}

const beforeClicks = documentClicks.length;

modal.classList.remove('hidden');
const closeBtn = el('dyn-close', { tagName: 'BUTTON', attributes: { 'data-action-modal': 'close' } });
fireDoc(closeBtn);

const mono = el('', { textContent: 'https://t.me/bot?start=ref_1', className: 'font-mono' });
const copyBtn = el('copy-ref', { tagName: 'BUTTON', attributes: { 'data-copy-action': 'clipboard' }, previousElementSibling: mono });
fireDoc(copyBtn);

const giftBtn = el('gift-act', { tagName: 'BUTTON', attributes: { 'data-gift-action': 'activate', 'data-gift-code': 'GIFTCODE11' } });
fireDoc(giftBtn);

purchaseSelf.click();

const plan = el('plan-1', { tagName: 'BUTTON', className: 'plan-btn', attributes: {
  'data-price': '300', 'data-base-price': '300', 'data-host': 'test', 'data-plan-id': '2',
  'data-plan-name': '3 месяца', 'data-months': '3', 'data-duration-days': '0'
}});
fireDoc(plan);

const syncBtn = el('sync-tg', { tagName: 'BUTTON', attributes: { 'data-sync-telegram': '1', 'data-bot-username': 'demo_bot' } });
fireDoc(syncBtn);

const renewBtn = el('renew-1', { tagName: 'BUTTON', attributes: { 'data-key-action': 'renew', 'data-key-id': '42' } });
fireDoc(renewBtn);

const autoBtn = el('auto-1', { tagName: 'BUTTON', attributes: { 'data-key-action': 'auto-renew', 'data-key-id': '42', 'data-auto-renew': 'false' } });
autoBtn.querySelector = function () { return null; };
fireDoc(autoBtn);

Promise.resolve().then(() => null).then(() => null).then(() => null).then(() => null).then(() => {
  const giftsState = { gifts: [{ gift_code: '"><img src=x onerror=alert(1)>', host_name: 'h', created_at: '2026-01-01' }], page: 0 };
  sandbox.window._giftsState = giftsState;
  sandbox._giftsState = giftsState;
  const giftHtml = sandbox._giftCardHtml(giftsState.gifts[0]);
  return {
    threw,
    beforeClicks,
    afterClicks: documentClicks.length,
    closedHidden: modal.classList.contains('hidden') || (modal.className || '').indexOf('hidden') >= 0,
    copied: copied.slice(),
    giftFetch: fetches.filter((f) => String(f.url).indexOf('/api/gift/activate') >= 0).map((f) => f.body),
    purchaseMode: sandbox.window._purchaseMode,
    payEnabled: !payBtn.disabled,
    payPlan: payBtn.getAttribute('data-plan-id'),
    txHasOnclick: /onclick="loadTransactions/.test(src),
    txHasAction: /data-tx-action="page-next"/.test(src),
    giftHasOnclick: /onclick=/.test(giftHtml),
    giftHasAttr: /data-gift-action="activate"/.test(giftHtml),
    giftRawInOnclick: /onclick="[^"]*<img/.test(giftHtml),
    leftoverBridge: /window\.openActionModal = openActionModal;/.test(src),
    purchaseBridge: /window\.setPurchaseMode = setPurchaseMode;/.test(src),
    opened: opened.slice(),
    hash: sandbox.location.hash,
    autoFetch: fetches.filter((f) => String(f.url).indexOf('/api/key/auto-renew') >= 0).map((f) => f.body),
  };
}).then((r) => console.log(JSON.stringify(r))).catch((e) => {
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
    assert result["beforeClicks"] >= 1
    assert result["afterClicks"] == result["beforeClicks"]
    assert "https://t.me/bot?start=ref_1" in result["copied"]
    bodies = [json.loads(b) if isinstance(b, str) else b for b in result["giftFetch"]]
    assert any(b.get("gift_code") == "GIFTCODE11" for b in bodies)
    assert result["purchaseMode"] == "new"
    assert result["payEnabled"] is True
    assert result["payPlan"] == "2"
    assert result["txHasOnclick"] is False
    assert result["txHasAction"] is True
    assert result["giftHasOnclick"] is False
    assert result["giftHasAttr"] is True
    assert result["giftRawInOnclick"] is False
    assert result["leftoverBridge"] is False
    assert result["purchaseBridge"] is False
    assert result["closedHidden"] is True
    assert any("t.me/demo_bot?start=sync_t" in u for u in result["opened"])
    assert result["hash"] == "rebay"
    auto_bodies = [json.loads(b) if isinstance(b, str) else b for b in result["autoFetch"]]
    assert any(b.get("key_id") == 42 and b.get("enabled") is True for b in auto_bodies), result.get("autoFetch")
