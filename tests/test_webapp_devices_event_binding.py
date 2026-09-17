"""Этап 2 PR 4: модалка устройств без inline onclick / window bridges."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
KEYS = Path("src/shop_bot/webapp/web_router/render_keys.py")
REMOVED_BRIDGES = (
    "deleteDevice",
    "renderDeviceModalPage",
    "deleteAllDevices",
)


def test_device_modal_has_no_inline_device_handlers():
    html = mini_app_html()
    js = mini_app_js()
    keys = KEYS.read_text(encoding="utf-8")
    assert 'onclick="deleteDevice' not in html
    assert 'onclick="deleteAllDevices' not in html
    assert 'onclick="renderDeviceModalPage' not in html
    assert 'onclick="deleteDevice' not in keys
    assert 'onclick="deleteAllDevices' not in keys
    assert 'data-key-action="devices"' in keys
    assert 'onclick="deleteDevice' not in js
    assert 'onclick="deleteAllDevices' not in js
    render_fn = js.split("function renderDeviceModalPage")[1].split("// ===== Rename Key")[0]
    assert "onclick=" not in render_fn
    assert 'data-device-action="delete"' in js
    assert 'data-device-action="delete-all"' in js
    assert 'data-device-action="page-prev"' in js
    assert 'data-device-action="page-next"' in js
    assert "closest('[data-device-action]')" in js
    assert "escapeHtmlAttr(" in js
    assert "deleteDevice(deviceKeyId, deviceId, deviceHost, deviceBtn)" in js
    assert "deleteAllDevices(deviceKeyId, deviceHost)" in js


def test_removed_device_handler_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.openActionModal = openActionModal;" not in js
    assert "window.openTopUpModal = openTopUpModal;" not in js
    assert "window.processPayment = processPayment;" not in js


def test_served_keys_page_devices_use_data_action_not_onclick(temp_db, app_client):
    import sqlite3

    from shop_bot.data_manager import database
    from conftest import insert_user, issue_auth_token

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=15401, username="devices-bind")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, comment_key, user_key_name
            ) VALUES (15401, 'DeviceHost', 'dev@bot.local', 'dev@bot.local',
                      'https://sub.example/dev', datetime('now', '+30 days'),
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '', 'PR4 Device Key')
            """
        )
        conn.commit()
    token = issue_auth_token(15401)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert "PR4 Device Key" in html
    assert 'data-key-action="devices"' in html
    assert 'onclick="deleteDevice' not in html
    assert 'onclick="deleteAllDevices' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "closest('[data-device-action]')" in js.text
    assert "window.deleteDevice = deleteDevice;" not in js.text
    assert "window.deleteAllDevices = deleteAllDevices;" not in js.text
    assert "window.renderDeviceModalPage = renderDeviceModalPage;" not in js.text


def test_device_modal_event_binding_in_node():
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
      if (sel === '[data-device-action]' && this.attributes['data-device-action']) return this;
      if (sel === '[data-key-action]' && this.attributes['data-key-action']) return this;
      if (sel === '.key-toggle' && (this.className || '').split(/\s+/).includes('key-toggle')) return this;
      if (sel === '#comment-save-btn' && this.id === 'comment-save-btn') return this;
      if (sel === '#comment-delete-btn' && this.id === 'comment-delete-btn') return this;
      return null;
    },
    contains() { return false; },
    appendChild() {},
    replaceChildren() {},
  }, extra || {});
  if (!node.attributes) node.attributes = {};
  return node;
}

function decodeAttr(value) {
  return String(value || '')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function parseButtons(html) {
  const buttons = [];
  const re = /<button\b([^>]*)>/g;
  let m;
  while ((m = re.exec(html))) {
    const attrs = {};
    const raw = m[1];
    const attrRe = /([:\w-]+)(?:=(?:"([^"]*)"|'([^']*)'))?/g;
    let a;
    while ((a = attrRe.exec(raw))) {
      attrs[a[1]] = a[2] != null ? a[2] : (a[3] != null ? a[3] : '');
    }
    buttons.push(attrs);
  }
  return buttons;
}

function buttonFromAttrs(attrs) {
  const decoded = {};
  for (const [k, v] of Object.entries(attrs)) decoded[k] = decodeAttr(v);
  const node = el(decoded.id || 'device-btn', { attributes: decoded });
  node.disabled = Object.prototype.hasOwnProperty.call(attrs, 'disabled');
  return node;
}

const toast = el('toast-container');
toast.appendChild = function (child) { notifications.push(child && child.textContent); };

const contentEl = el('action-modal-content');
Object.defineProperty(contentEl, 'innerHTML', {
  get() { return this._html || ''; },
  set(v) { this._html = String(v); }
});

const byId = {
  'action-modal': el('action-modal', { className: 'hidden' }),
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
const confirms = [];
const fetches = [];
const devicesAction = el('devices-action', {
  attributes: { 'data-key-action': 'devices', 'data-key-id': '61', 'data-host': 'DeviceHost\'"><img>' }
});

const XSS_HWID = 'id\'"><img src=x onerror=alert(1)>';
const XSS_UA = '<img src=x onerror=alert(1)>';
const XSS_HOST = 'DeviceHost\'"><img>';
const deviceList = [
  { hwid: XSS_HWID, userAgent: XSS_UA, createdAt: '2026-01-02T00:00:00.000Z' },
  { hwid: 'hwid-2', userAgent: 'Phone-2' },
  { hwid: 'hwid-3', userAgent: 'Phone-3' },
  { hwid: 'hwid-4', userAgent: 'Phone-4' },
  { hwid: 'hwid-5', userAgent: 'Phone-5' },
  { hwid: 'hwid-6', userAgent: 'Phone-6' },
];

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
  confirm(...args) { confirms.push(args[0]); return true; },
  fetch: async (url, opts) => {
    const body = opts && opts.body ? JSON.parse(opts.body) : {};
    fetches.push({ url: String(url), body });
    if (String(url).includes('/api/key/devices/delete-all')) {
      return { ok: true, json: async () => ({ ok: true, deleted: 6 }), text: async () => '' };
    }
    if (String(url).includes('/api/key/device/delete')) {
      return { ok: true, json: async () => ({ ok: true }), text: async () => '' };
    }
    if (String(url).includes('/api/key/devices')) {
      return { ok: true, json: async () => ({ ok: true, devices: deviceList }), text: async () => '' };
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
  location: { href: 'https://example.test/', hash: '', pathname: '/', reload() {} },
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

function fire(target) {
  (docListeners.click || []).forEach((fn) => fn({ target }));
}

async function waitUntil(pred) {
  for (let i = 0; i < 30; i++) {
    if (pred()) return;
    await Promise.resolve();
  }
}

fire(devicesAction);

waitUntil(() => (contentEl.innerHTML || '').includes('data-device-action="delete"')).then(() => {
  const page1 = contentEl.innerHTML || '';
  const buttons1 = parseButtons(page1).map(buttonFromAttrs);
  const deleteBtns = buttons1.filter((b) => b.getAttribute('data-device-action') === 'delete');
  const nextBtn = buttons1.find((b) => b.getAttribute('data-device-action') === 'page-next');
  const deleteAllBtn = buttons1.find((b) => b.getAttribute('data-device-action') === 'delete-all');
  const page1Meta = {
    hasOnclick: /onclick=/.test(page1),
    hasDeleteAction: page1.includes('data-device-action="delete"'),
    hasDeleteAll: page1.includes('data-device-action="delete-all"'),
    escapedImg: page1.includes('&lt;img'),
    rawImgTag: /<img\s/.test(page1),
    deleteCount: deleteBtns.length,
    decodedHwid: deleteBtns[0] && deleteBtns[0].getAttribute('data-device-id'),
    decodedHost: deleteBtns[0] && deleteBtns[0].getAttribute('data-host'),
    pageLabel: /1 \/ 2/.test(page1),
  };

  fire(nextBtn);
  const page2 = contentEl.innerHTML || '';
    const afterNext = {
    page: sandbox._deviceModalState && sandbox._deviceModalState.page,
    pageLabel: /2 \/ 2/.test(page2),
    hasHwid6: page2.includes('hwid-6'),
    hasXssDevice: page2.includes('onerror=alert(1)'),
  };

  const prevBtn = parseButtons(page2).map(buttonFromAttrs).find((b) => b.getAttribute('data-device-action') === 'page-prev');
  fire(prevBtn);
  const pageBack = contentEl.innerHTML || '';
  const afterPrev = {
    page: sandbox._deviceModalState && sandbox._deviceModalState.page,
    pageLabel: /1 \/ 2/.test(pageBack),
  };

  const disabledDelete = el('disabled-delete', {
    attributes: { 'data-device-action': 'delete', 'data-key-id': '61', 'data-device-id': 'nope', 'data-host': 'DeviceHost' }
  });
  disabledDelete.disabled = true;
  const fetchesBeforeDisabled = fetches.length;
  fire(disabledDelete);

  fire(deleteBtns[0]);
  return waitUntil(() => notifications.some((n) => String(n).includes('Устройство удалено'))).then(() => {
    fire(deleteAllBtn);
    return waitUntil(() => notifications.some((n) => String(n).includes('Удалено устройств'))).then(() => {
      const deletePost = fetches.find((f) => f.url.includes('/api/key/device/delete'));
      const deleteAllPost = fetches.find((f) => f.url.includes('/api/key/devices/delete-all'));
      console.log(JSON.stringify({
        threw,
        docClick: (docListeners.click || []).length,
        page1Meta,
        afterNext,
        afterPrev,
        disabledDidNotFetch: fetches.length === fetchesBeforeDisabled + (fetches.some((f) => f.url.includes('/api/key/device/delete')) ? 0 : 0) || !fetches.some((f) => f.body && f.body.device_id === 'nope'),
        deletePost,
        deleteAllPost,
        confirms,
        notifications,
        deleteBridge: /window\.deleteDevice = deleteDevice;/.test(src),
        deleteAllBridge: /window\.deleteAllDevices = deleteAllDevices;/.test(src),
        renderBridge: /window\.renderDeviceModalPage = renderDeviceModalPage;/.test(src),
      }));
    });
  });
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
    assert result["docClick"] >= 1
    assert result["page1Meta"]["hasOnclick"] is False
    assert result["page1Meta"]["hasDeleteAction"] is True
    assert result["page1Meta"]["hasDeleteAll"] is True
    assert result["page1Meta"]["escapedImg"] is True
    assert result["page1Meta"]["rawImgTag"] is False
    assert result["page1Meta"]["deleteCount"] == 5
    assert result["page1Meta"]["decodedHwid"] == """id'"><img src=x onerror=alert(1)>"""
    assert result["page1Meta"]["decodedHost"] == """DeviceHost'"><img>"""
    assert result["page1Meta"]["pageLabel"] is True
    assert result["afterNext"]["page"] == 1
    assert result["afterNext"]["pageLabel"] is True
    assert result["afterNext"]["hasHwid6"] is True
    assert result["afterNext"]["hasXssDevice"] is False
    assert result["afterPrev"]["page"] == 0
    assert result["afterPrev"]["pageLabel"] is True
    assert result["disabledDidNotFetch"] is True
    assert result["deletePost"]["body"]["key_id"] == 61
    assert result["deletePost"]["body"]["device_id"] == """id'"><img src=x onerror=alert(1)>"""
    assert result["deletePost"]["body"]["host_name"] == """DeviceHost'"><img>"""
    assert result["deleteAllPost"]["body"]["key_id"] == 61
    assert result["deleteAllPost"]["body"]["host_name"] == """DeviceHost'"><img>"""
    assert result["confirms"]
    notes = " ".join(result["notifications"]).lower()
    assert "удален" in notes
    assert result["deleteBridge"] is False
    assert result["deleteAllBridge"] is False
    assert result["renderBridge"] is False
