"""Этап 2 PR 2: поиск/вкладки ключей и copy-key без inline HTML handlers."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
REMOVED_BRIDGES = (
    "onKeysSearchInput",
    "clearKeysSearch",
    "switchKeysTab",
    "copyKey",
)


def test_keys_search_tabs_have_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    assert 'id="keys-search-input"' in html
    assert 'id="keys-search-clear"' in html
    assert 'id="keys-tab-btn-personal"' in html
    assert 'id="keys-tab-btn-gifts"' in html
    assert "oninput=" not in html.split('id="keys-search-input"', 1)[1].split("</div>", 1)[0]
    assert "onclick=" not in html.split('id="keys-search-clear"', 1)[1].split("</button>", 1)[0]
    assert "onclick=" not in html.split('id="keys-tab-btn-personal"', 1)[1].split("</button>", 1)[0]
    assert "onclick=" not in html.split('id="keys-tab-btn-gifts"', 1)[1].split("</button>", 1)[0]
    assert "onKeysSearchInput()" not in html
    assert "clearKeysSearch()" not in html
    assert "switchKeysTab(" not in html
    assert "getElementById('keys-search-input')?.addEventListener('input', onKeysSearchInput)" in js
    assert "getElementById('keys-search-clear')?.addEventListener('click', clearKeysSearch)" in js
    assert "getElementById('keys-tab-btn-personal')?.addEventListener('click', () => switchKeysTab('personal'))" in js
    assert "getElementById('keys-tab-btn-gifts')?.addEventListener('click', () => switchKeysTab('gifts'))" in js


def test_copy_key_stays_on_data_key_action_delegation():
    html = mini_app_html()
    js = mini_app_js()
    keys = Path("src/shop_bot/webapp/web_router/render_keys.py").read_text(encoding="utf-8")
    assert 'onclick="copyKey' not in html
    assert 'onclick="copyKey' not in keys
    assert 'data-key-action="copy-key"' in keys
    assert "closest('[data-key-action]')" in js
    assert "action === 'copy-key'" in js
    assert "copyKey(btn, url)" in js
    assert "function copyKey(" in js


def test_removed_keys_handler_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.openTopUpModal = openTopUpModal;" not in js
    assert "window.processPayment = processPayment;" not in js
    assert "window.setPurchaseMode = setPurchaseMode;" not in js


def test_served_keys_page_has_listeners_not_inline_handlers(temp_db, app_client):
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    from conftest import insert_user, issue_auth_token

    insert_user(database.DB_FILE, telegram_id=15201, username="keys-bind")
    token = issue_auth_token(15201)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'id="keys-search-input"' in html
    assert "onKeysSearchInput()" not in html
    assert "clearKeysSearch()" not in html
    assert "switchKeysTab(" not in html
    assert "/static/js/app.js?v=" in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "addEventListener('input', onKeysSearchInput)" in js.text
    assert "copyKey(btn, url)" in js.text


def test_keys_search_tabs_and_copy_key_event_binding_in_node():
    assert NODE, "нужен node для проверки addEventListener"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');

function classList(initial) {
  const set = new Set(String(initial || '').split(/\s+/).filter(Boolean));
  return {
    _set: set,
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
    className: '',
    classList: classList(extra && extra.className),
    style: {},
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
    closest(sel) {
      if (sel === '[data-key-action]' && this.attributes['data-key-action']) return this;
      return null;
    },
    contains() { return false; },
    appendChild() {},
    replaceChildren() {},
  }, extra || {});
  if (!node.attributes) node.attributes = {};
  return node;
}

const searchInput = el('keys-search-input', { value: '' });
const clearBtn = el('keys-search-clear', { className: 'hidden' });
const personalBtn = el('keys-tab-btn-personal', { className: 'bg-white/10 text-white' });
const giftsBtn = el('keys-tab-btn-gifts', { className: 'text-gray-400' });
const personalPanel = el('keys-tab-personal');
const giftsPanel = el('keys-tab-gifts', { className: 'hidden' });
const tabsEl = el('keys-tabs');
const resultsWrap = el('keys-search-results-wrap', { className: 'hidden' });
const toast = el('toast-container');
toast.appendChild = function (child) { notifications.push(child && child.textContent); };
const copyBtn = el('copy-btn', {
  attributes: { 'data-key-action': 'copy-key', 'data-url': 'https://sub.example/key' }
});
copyBtn.querySelector = (sel) => sel === '.material-symbols-rounded' ? { textContent: 'content_copy' } : null;

const byId = {
  'keys-search-input': searchInput,
  'keys-search-clear': clearBtn,
  'keys-tab-btn-personal': personalBtn,
  'keys-tab-btn-gifts': giftsBtn,
  'keys-tab-personal': personalPanel,
  'keys-tab-gifts': giftsPanel,
  'keys-tabs': tabsEl,
  'keys-search-results-wrap': resultsWrap,
  'keys-search-results': el('keys-search-results'),
  'toast-container': toast,
  'profile-keys-list-container': el('profile-keys-list-container'),
  'profile-keys-pagination': el('profile-keys-pagination', { className: 'hidden' }),
  'gifts-content': el('gifts-content', { className: 'hidden' }),
  'gifts-loading': el('gifts-loading'),
};
const docListeners = {};
const copied = [];
const notifications = [];
const document = {
  body: el('body'),
  documentElement: Object.assign(el('html'), { style: { setProperty() {} } }),
  readyState: 'complete',
  getElementById(id) { return byId[id] || el(id); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement() { return el('anon'); },
  addEventListener(type, fn) { (docListeners[type] || (docListeners[type] = [])).push(fn); },
  removeEventListener() {},
  elementFromPoint() { return null; },
};

const sandbox = {
  console,
  setTimeout,
  clearTimeout,
  setInterval() { return 1; },
  clearInterval() {},
  URL,
  Event,
  requestAnimationFrame: (fn) => fn(),
  fetch: async () => ({ ok: true, json: async () => ({ ok: true, total: 0, html: '' }), text: async () => '' }),
  document,
  localStorage: { theme: 'dark', getItem() { return null; }, setItem() {}, removeItem() {} },
  Telegram: { WebApp: { ready() {}, expand() {}, initData: '', initDataUnsafe: {}, platform: 'unknown' } },
  matchMedia() { return { matches: true, addEventListener() {} }; },
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() { return true; },
  location: { href: 'https://example.test/', hash: '', pathname: '/', reload() {} },
  history: { replaceState() {} },
  innerHeight: 800,
  innerWidth: 400,
  visualViewport: { height: 800, addEventListener() {} },
  getAuthToken() { return 't'; },
  open() {},
  RENDERED_USER_ID: 1,
  navigator: { clipboard: { writeText(text) { copied.push(text); return Promise.resolve(); } } },
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

const bindings = {
  searchInput: (searchInput.listeners.input || []).length,
  clearClick: (clearBtn.listeners.click || []).length,
  personalClick: (personalBtn.listeners.click || []).length,
  giftsClick: (giftsBtn.listeners.click || []).length,
  docClick: (docListeners.click || []).length,
};

searchInput.value = 'vpn';
searchInput.dispatchEvent({ type: 'input' });
const clearVisibleAfterType = !clearBtn.classList.contains('hidden');

clearBtn.dispatchEvent({ type: 'click' });
const valueAfterClear = searchInput.value;
const clearHiddenAfterClear = clearBtn.classList.contains('hidden');

giftsBtn.dispatchEvent({ type: 'click' });
const giftsTabActive = giftsBtn.classList.contains('bg-white/10') && !giftsPanel.classList.contains('hidden');
const personalTabInactive = personalPanel.classList.contains('hidden');

personalBtn.dispatchEvent({ type: 'click' });
const personalTabActive = !personalPanel.classList.contains('hidden') && personalBtn.classList.contains('bg-white/10');

(docListeners.click || []).forEach((fn) => fn({
  target: copyBtn,
}));

Promise.resolve().then(() => {
  console.log(JSON.stringify({
    threw,
    bindings,
    clearVisibleAfterType,
    valueAfterClear,
    clearHiddenAfterClear,
    giftsTabActive,
    personalTabInactive,
    personalTabActive,
    copied,
    notifications,
    copyBridge: typeof sandbox.copyKey,
    searchBridge: Object.prototype.hasOwnProperty.call(sandbox, 'onKeysSearchInput') && sandbox.onKeysSearchInput === sandbox.window.onKeysSearchInput,
    explicitCopyAssign: /window\.copyKey = copyKey;/.test(src),
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
    assert result["threw"] is None, result["threw"]
    assert result["bindings"]["searchInput"] >= 1
    assert result["bindings"]["clearClick"] >= 1
    assert result["bindings"]["personalClick"] >= 1
    assert result["bindings"]["giftsClick"] >= 1
    assert result["bindings"]["docClick"] >= 1
    assert result["clearVisibleAfterType"] is True
    assert result["valueAfterClear"] == ""
    assert result["clearHiddenAfterClear"] is True
    assert result["giftsTabActive"] is True
    assert result["personalTabInactive"] is True
    assert result["personalTabActive"] is True
    assert "https://sub.example/key" in result["copied"]
    assert any("скопирован" in msg.lower() for msg in result["notifications"])
    assert result["explicitCopyAssign"] is False
