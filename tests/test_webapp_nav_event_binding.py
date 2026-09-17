"""Этап 2 PR 6: нижнее меню без inline onclick / window.navigateTo."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
NAV_IDS = ("nav-keys", "nav-finance", "nav-home", "nav-referral", "nav-support")


def _button_after(html: str, marker: str) -> str:
    return html.split(marker, 1)[1].split("</button>", 1)[0]


def test_bottom_nav_has_no_inline_navigate_handlers():
    html = mini_app_html()
    js = mini_app_js()
    for nav_id in NAV_IDS:
        assert f'id="{nav_id}"' in html
        assert "onclick=" not in _button_after(html, f'id="{nav_id}"')
    assert 'onclick="navigateTo(' not in html
    assert "getElementById('nav-keys')?.addEventListener('click', () => navigateTo('keys'))" in js
    assert "getElementById('nav-finance')?.addEventListener('click', () => navigateTo('finance'))" in js
    assert "getElementById('nav-home')?.addEventListener('click', () => navigateTo('home'))" in js
    assert "getElementById('nav-referral')?.addEventListener('click', () => navigateTo('referral'))" in js
    assert "getElementById('nav-support')?.addEventListener('click', () => navigateTo('support'))" in js
    assert "function handleHashChange(" in js
    assert "window.addEventListener('hashchange', handleHashChange)" in js
    assert "getElementById('support-create-btn')?.addEventListener('click', createSupportTicket)" in js


def test_removed_navigate_bridge_is_gone():
    js = mini_app_js()
    assert "window.navigateTo = navigateTo;" not in js
    assert "window.openTopUpModal = openTopUpModal;" not in js
    assert "window.processPayment = processPayment;" not in js
    assert "window.setPurchaseMode = setPurchaseMode;" in js


def test_served_page_nav_has_listeners_not_onclick(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=15601, username="nav-bind")
    token = issue_auth_token(15601)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'id="nav-keys"' in html
    assert 'onclick="navigateTo(' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "addEventListener('click', () => navigateTo('keys'))" in js.text
    assert "window.navigateTo = navigateTo;" not in js.text


def test_bottom_nav_event_binding_in_node():
    assert NODE, "нужен node для проверки addEventListener"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');

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
  const node = Object.assign({
    id: id || '',
    className: (extra && extra.className) || '',
    classList: classList(extra && extra.className),
    style: Object.assign({ display: extra && extra.display || '' }, extra && extra.style),
    hidden: false,
    value: '',
    textContent: '',
    innerHTML: '',
    disabled: false,
    listeners: {},
    children: [],
    attributes: Object.assign({}, extra && extra.attributes),
    addEventListener(type, fn) {
      (this.listeners[type] || (this.listeners[type] = [])).push(fn);
    },
    dispatchEvent(evt) {
      (this.listeners[evt.type] || []).forEach((fn) => fn(evt));
    },
    getAttribute(name) { return this.attributes[name] || ''; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    closest() { return null; },
    contains() { return false; },
    appendChild() {},
    replaceChildren() {},
  }, extra || {});
  if (!node.attributes) node.attributes = {};
  if (!node.style) node.style = {};
  if (extra && extra.className) node.classList = classList(extra.className);
  return node;
}

const homePage = el('home-page', { display: 'flex' });
const keysPage = el('keys-page', { display: 'none' });
const financePage = el('finance-page', { display: 'none' });
const referralPage = el('referral-page', { display: 'none' });
const supportPage = el('support-page', { display: 'none' });
const purchasePage = el('purchase-page', { display: 'none' });
const renewPage = el('renew-page', { display: 'none' });
const setupPage = el('setup-page', { display: 'none' });
const navKeys = el('nav-keys', { className: 'nav-tab text-gray-500' });
const navFinance = el('nav-finance', { className: 'nav-tab text-gray-500' });
const navHome = el('nav-home', { className: 'nav-tab text-primary' });
const navReferral = el('nav-referral', { className: 'nav-tab text-gray-500' });
const navSupport = el('nav-support', { className: 'nav-tab text-gray-500' });
const bottomNav = el('bottom-nav');
bottomNav.style = { display: 'flex' };

const byId = {
  'home-page': homePage,
  'keys-page': keysPage,
  'finance-page': financePage,
  'referral-page': referralPage,
  'support-page': supportPage,
  'purchase-page': purchasePage,
  'renew-page': renewPage,
  'setup-page': setupPage,
  'nav-keys': navKeys,
  'nav-finance': navFinance,
  'nav-home': navHome,
  'nav-referral': navReferral,
  'nav-support': navSupport,
  'bottom-nav': bottomNav,
  'keys-search-input': el('keys-search-input'),
  'keys-search-clear': el('keys-search-clear', { className: 'hidden' }),
  'keys-tab-btn-personal': el('keys-tab-btn-personal'),
  'keys-tab-btn-gifts': el('keys-tab-btn-gifts'),
  'settings-menu': el('settings-menu', { className: 'hidden' }),
  'menu-dots-btn': el('menu-dots-btn'),
  'settings-refresh-btn': el('settings-refresh-btn'),
  'edit-profile-btn-menu': el('edit-profile-btn-menu', { className: 'hidden' }),
  'logout-btn-menu': el('logout-btn-menu'),
};

const docListeners = {};
const winListeners = {};
let locHash = '';
const document = {
  body: el('body'),
  documentElement: Object.assign(el('html'), { style: { setProperty() {} } }),
  readyState: 'complete',
  getElementById(id) { return byId[id] || el(id); },
  querySelector() { return null; },
  querySelectorAll(sel) {
    if (sel === '.nav-tab') return [navKeys, navFinance, navHome, navReferral, navSupport];
    return [];
  },
  createElement() { return el('anon'); },
  addEventListener(type, fn) { (docListeners[type] || (docListeners[type] = [])).push(fn); },
  removeEventListener() {},
  elementFromPoint() { return null; },
};

const location = {
  href: 'https://example.test/',
  pathname: '/',
  reload() {},
};
Object.defineProperty(location, 'hash', {
  get() { return locHash; },
  set(v) {
    const next = (v === '' || v == null) ? '' : (String(v).startsWith('#') ? String(v) : '#' + String(v));
    if (next === locHash) return;
    locHash = next;
    (winListeners.hashchange || []).forEach((fn) => fn({ type: 'hashchange' }));
  },
});

const sandbox = {
  console,
  setTimeout,
  clearTimeout,
  setInterval() { return 1; },
  clearInterval() {},
  URL,
  Event,
  requestAnimationFrame: (fn) => fn(),
  fetch: async () => ({ ok: true, json: async () => ({ ok: true, tickets: [] }), text: async () => '' }),
  document,
  localStorage: { theme: 'dark', getItem() { return null; }, setItem() {}, removeItem() {} },
  Telegram: { WebApp: { ready() {}, expand() {}, initData: '', initDataUnsafe: {}, platform: 'unknown' } },
  matchMedia() { return { matches: true, addEventListener() {} }; },
  addEventListener(type, fn) { (winListeners[type] || (winListeners[type] = [])).push(fn); },
  removeEventListener() {},
  dispatchEvent() { return true; },
  location,
  history: { replaceState() {} },
  innerHeight: 800,
  innerWidth: 400,
  visualViewport: { height: 800, addEventListener() {} },
  getAuthToken() { return 't'; },
  getComputedStyle() { return { backgroundColor: 'rgb(0, 0, 0)' }; },
  open() {},
  RENDERED_USER_ID: 1,
  navigator: { clipboard: { writeText() { return Promise.resolve(); } } },
};
sandbox.apiFetch = sandbox.fetch;
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

let threw = null;
try {
  vm.runInNewContext(src, sandbox, { filename: 'app.js' });
} catch (e) {
  threw = e && e.stack ? e.stack : String(e);
}

function click(target) {
  (target.listeners.click || []).forEach((fn) => fn({ target, stopPropagation() {} }));
}

const bindings = {
  keys: (navKeys.listeners.click || []).length,
  finance: (navFinance.listeners.click || []).length,
  home: (navHome.listeners.click || []).length,
  referral: (navReferral.listeners.click || []).length,
  support: (navSupport.listeners.click || []).length,
  hashchange: (winListeners.hashchange || []).length,
};

click(navKeys);
const afterKeys = {
  hash: location.hash,
  keysVisible: keysPage.style.display === 'flex',
  homeHidden: homePage.style.display === 'none',
  keysActive: navKeys.classList.contains('text-primary'),
};
click(navFinance);
const afterFinance = {
  hash: location.hash,
  financeVisible: financePage.style.display === 'flex',
  keysHidden: keysPage.style.display === 'none',
};
click(navReferral);
const afterReferral = { hash: location.hash, referralVisible: referralPage.style.display === 'flex' };
click(navSupport);
const afterSupport = { hash: location.hash, supportVisible: supportPage.style.display === 'flex' };
click(navHome);
const afterHome = {
  hash: location.hash,
  homeVisible: homePage.style.display === 'flex',
  supportHidden: supportPage.style.display === 'none',
  homeActive: navHome.classList.contains('text-primary'),
};

console.log(JSON.stringify({
  threw,
  bindings,
  afterKeys,
  afterFinance,
  afterReferral,
  afterSupport,
  afterHome,
  navBridge: /window\.navigateTo = navigateTo;/.test(src),
  referralBridge: /window\.requestReferralWithdraw = requestReferralWithdraw;/.test(src),
  methodsBridge: /window\.openReferralMethodsModal = openReferralMethodsModal;/.test(src),
  payBridge: /window\.processPayment = processPayment;/.test(src),
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
    assert result["threw"] is None, result["threw"]
    assert result["bindings"]["keys"] >= 1
    assert result["bindings"]["finance"] >= 1
    assert result["bindings"]["home"] >= 1
    assert result["bindings"]["referral"] >= 1
    assert result["bindings"]["support"] >= 1
    assert result["bindings"]["hashchange"] >= 1
    assert result["afterKeys"]["hash"] in {"#keys", "keys"}
    assert result["afterKeys"]["keysVisible"] is True
    assert result["afterKeys"]["homeHidden"] is True
    assert result["afterKeys"]["keysActive"] is True
    assert result["afterFinance"]["hash"] in {"#finance", "finance"}
    assert result["afterFinance"]["financeVisible"] is True
    assert result["afterReferral"]["referralVisible"] is True
    assert result["afterSupport"]["supportVisible"] is True
    assert result["afterHome"]["hash"] in {"", "#"}
    assert result["afterHome"]["homeVisible"] is True
    assert result["afterHome"]["supportHidden"] is True
    assert result["afterHome"]["homeActive"] is True
    assert result["navBridge"] is False
    assert result["referralBridge"] is False
    assert result["methodsBridge"] is False
    assert result["payBridge"] is False
