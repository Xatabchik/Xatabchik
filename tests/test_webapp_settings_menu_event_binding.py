"""Этап 2 PR 5: меню настроек без inline onclick / window bridges."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
REMOVED_BRIDGES = (
    "toggleSettingsMenu",
    "openEditProfileModal",
)


def _button_after(html: str, marker: str) -> str:
    return html.split(marker, 1)[1].split("</button>", 1)[0]


def test_settings_menu_has_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    assert 'id="menu-dots-btn"' in html
    assert 'id="settings-refresh-btn"' in html
    assert 'id="edit-profile-btn-menu"' in html
    assert "onclick=" not in _button_after(html, 'id="menu-dots-btn"')
    assert "onclick=" not in _button_after(html, 'id="settings-refresh-btn"')
    assert "onclick=" not in _button_after(html, 'id="edit-profile-btn-menu"')
    assert 'onclick="toggleSettingsMenu' not in html
    assert 'onclick="openEditProfileModal' not in html
    assert "getElementById('menu-dots-btn')?.addEventListener('click', toggleSettingsMenu)" in js
    assert "getElementById('settings-refresh-btn')?.addEventListener('click', () => location.reload())" in js
    assert "getElementById('edit-profile-btn-menu')?.addEventListener('click', () => {" in js
    assert "toggleSettingsMenu();" in js
    assert "openEditProfileModal();" in js
    assert "async function _submitProfileChangePassword(" in js
    assert "function _renderProfileChangeEmailRequest(" in js
    assert "window._submitProfileChangePassword = _submitProfileChangePassword;" in js
    assert "window._submitProfileChangeEmailRequest = _submitProfileChangeEmailRequest;" in js


def test_removed_settings_menu_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.openActionModal = openActionModal;" in js
    assert "window.openTopUpModal = openTopUpModal;" in js
    assert "window.processPayment = processPayment;" in js


def test_served_home_page_settings_menu_has_listeners_not_onclick(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=15501, username="settings-bind")
    token = issue_auth_token(15501)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'id="menu-dots-btn"' in html
    assert 'id="settings-refresh-btn"' in html
    assert 'onclick="toggleSettingsMenu' not in html
    assert 'onclick="openEditProfileModal' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "addEventListener('click', toggleSettingsMenu)" in js.text
    assert "window.toggleSettingsMenu = toggleSettingsMenu;" not in js.text
    assert "window.openEditProfileModal = openEditProfileModal;" not in js.text


def test_settings_menu_event_binding_in_node():
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
    style: {},
    hidden: false,
    value: '',
    textContent: '',
    innerHTML: '',
    disabled: false,
    listeners: {},
    children: [],
    parent: extra && extra.parent || null,
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
      if (sel === '[data-device-action]' && this.attributes['data-device-action']) return this;
      return null;
    },
    contains(other) {
      if (other === this) return true;
      let n = other;
      while (n) {
        if (n === this) return true;
        n = n.parent;
      }
      return false;
    },
    appendChild(child) {
      this.children.push(child);
      if (child) child.parent = this;
    },
    replaceChildren(...nodes) {
      this.children = nodes;
      nodes.forEach((n) => { if (n) n.parent = this; });
    },
  }, extra || {});
  if (!node.attributes) node.attributes = {};
  if (extra && extra.className) node.classList = classList(extra.className);
  return node;
}

const settingsMenu = el('settings-menu', { className: 'hidden' });
const menuDots = el('menu-dots-btn');
const refreshBtn = el('settings-refresh-btn');
const profileBtn = el('edit-profile-btn-menu', { className: 'hidden' });
profileBtn.parent = settingsMenu;
refreshBtn.parent = settingsMenu;
const logoutBtn = el('logout-btn-menu');
logoutBtn.parent = settingsMenu;
const contentEl = el('action-modal-content');
const modal = el('action-modal', { className: 'hidden' });
const toast = el('toast-container');
toast.appendChild = function (child) { notifications.push(child && child.textContent); };

const byId = {
  'settings-menu': settingsMenu,
  'menu-dots-btn': menuDots,
  'settings-refresh-btn': refreshBtn,
  'edit-profile-btn-menu': profileBtn,
  'logout-btn-menu': logoutBtn,
  'action-modal': modal,
  'action-backdrop': el('action-backdrop', { className: 'opacity-0 pointer-events-none' }),
  'action-card': el('action-card', { className: 'translate-y-full' }),
  'action-modal-title': el('action-modal-title'),
  'action-modal-content': contentEl,
  'toast-container': toast,
  'keys-search-input': el('keys-search-input'),
  'keys-search-clear': el('keys-search-clear', { className: 'hidden' }),
  'keys-tab-btn-personal': el('keys-tab-btn-personal'),
  'keys-tab-btn-gifts': el('keys-tab-btn-gifts'),
  'profile-keys-list-container': el('profile-keys-list-container'),
  'profile-keys-pagination': el('profile-keys-pagination', { className: 'hidden' }),
  'gifts-content': el('gifts-content', { className: 'hidden' }),
  'gifts-loading': el('gifts-loading'),
};

const docListeners = {};
const notifications = [];
const reloads = [];
const profileInfoPosts = [];
const document = {
  body: el('body'),
  documentElement: Object.assign(el('html'), { style: { setProperty() {} } }),
  readyState: 'complete',
  getElementById(id) { return byId[id] || el(id); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement(tag) { return el(tag || 'anon'); },
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
  fetch: async (url, opts) => {
    const body = opts && opts.body ? JSON.parse(opts.body) : {};
    if (String(url).includes('/api/user/profile-info')) {
      profileInfoPosts.push(body);
      return {
        ok: true,
        json: async () => ({ ok: true, has_email_auth: true, auth_email: 'user@example.test' }),
        text: async () => '',
      };
    }
    return { ok: true, json: async () => ({ ok: true, total: 0, html: '' }), text: async () => '' };
  },
  document,
  localStorage: { theme: 'dark', getItem() { return null; }, setItem() {}, removeItem() {} },
  Telegram: { WebApp: { ready() {}, expand() {}, initData: '', initDataUnsafe: {}, platform: 'unknown' } },
  matchMedia() { return { matches: true, addEventListener() {} }; },
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() { return true; },
  location: { href: 'https://example.test/', hash: '', pathname: '/', reload() { reloads.push(1); } },
  history: { replaceState() {} },
  innerHeight: 800,
  innerWidth: 400,
  visualViewport: { height: 800, addEventListener() {} },
  getAuthToken() { return 't'; },
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
  const evt = {
    target,
    stopPropagation() { this._stopped = true; },
  };
  (target.listeners.click || []).forEach((fn) => fn(evt));
  if (!evt._stopped) {
    (docListeners.click || []).forEach((fn) => fn(evt));
  }
}

const bindings = {
  dots: (menuDots.listeners.click || []).length,
  refresh: (refreshBtn.listeners.click || []).length,
  profile: (profileBtn.listeners.click || []).length,
  logout: (logoutBtn.listeners.click || []).length,
  docClick: (docListeners.click || []).length,
};

click(menuDots);
const opened = !settingsMenu.classList.contains('hidden');
click(document.body);
const closedOutside = settingsMenu.classList.contains('hidden');
click(menuDots);
click(refreshBtn);
const reloaded = reloads.length >= 1;

profileBtn.classList.remove('hidden');
click(profileBtn);

async function waitUntil(pred) {
  for (let i = 0; i < 30; i++) {
    if (pred()) return;
    await Promise.resolve();
  }
}

waitUntil(() => profileInfoPosts.length > 0).then(() => {
  console.log(JSON.stringify({
    threw,
    bindings,
    opened,
    closedOutside,
    reloaded,
    afterProfile: {
      menuHidden: settingsMenu.classList.contains('hidden'),
      modalHidden: modal.classList.contains('hidden'),
      title: byId['action-modal-title'].innerHTML,
      profileInfo: profileInfoPosts.length,
    },
    toggleBridge: /window\.toggleSettingsMenu = toggleSettingsMenu;/.test(src),
    profileBridge: /window\.openEditProfileModal = openEditProfileModal;/.test(src),
    passwordBridge: /window\._submitProfileChangePassword = _submitProfileChangePassword;/.test(src),
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
    assert result["bindings"]["dots"] >= 1
    assert result["bindings"]["refresh"] >= 1
    assert result["bindings"]["profile"] >= 1
    assert result["bindings"]["logout"] >= 1
    assert result["bindings"]["docClick"] >= 1
    assert result["opened"] is True
    assert result["closedOutside"] is True
    assert result["reloaded"] is True
    assert result["afterProfile"]["menuHidden"] is True
    assert result["afterProfile"]["modalHidden"] is False
    assert "Профиль" in result["afterProfile"]["title"]
    assert result["afterProfile"]["profileInfo"] >= 1
    assert result["toggleBridge"] is False
    assert result["profileBridge"] is False
    assert result["passwordBridge"] is True
