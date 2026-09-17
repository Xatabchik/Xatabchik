"""Этап 2 PR 8: формы пароля/email профиля без inline onclick / window bridges."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
REMOVED_BRIDGES = (
    "_submitProfileChangePassword",
    "_submitProfileChangeEmailRequest",
    "_loadProfileMain",
)


def test_profile_credentials_have_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    assert 'onclick="_submitProfileChangePassword' not in html
    assert 'onclick="_submitProfileChangeEmailRequest' not in html
    assert 'onclick="_loadProfileMain' not in html
    assert 'onclick="_cancelProfileEmailChange' not in html
    assert 'onclick="_submitProfileChangePassword' not in js
    assert 'onclick="_submitProfileChangeEmailRequest' not in js
    assert 'onclick="_loadProfileMain' not in js
    assert 'onclick="_cancelProfileEmailChange' not in js
    assert "closest('[data-profile-action]')" in js
    assert 'data-profile-action="submit-password"' in js
    assert 'data-profile-action="submit-email-request"' in js
    assert 'data-profile-action="back-profile"' in js
    assert "setAttribute('data-profile-action', 'cancel-email')" in js
    assert "setAttribute('data-profile-action', 'verify-email')" in js
    assert "setAttribute('data-profile-action', 'resend-email')" in js
    assert 'type="password" id="profile-current-password"' in js
    assert 'type="password" id="profile-new-password"' in js
    assert 'type="password" id="profile-email-password"' in js
    assert "onclick=\"openTopUpModal()\"" not in html
    assert "window.processPayment = processPayment;" not in js


def test_removed_profile_credential_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window._cancelProfileEmailChange = _cancelProfileEmailChange;" not in js
    assert "window.openTopUpModal = openTopUpModal;" not in js
    assert "window.processPayment = processPayment;" not in js
    assert "window.setPurchaseMode = setPurchaseMode;" in js


def test_served_page_profile_credentials_use_delegation(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=15801, username="profile-bind")
    token = issue_auth_token(15801)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'onclick="_submitProfileChangePassword' not in html
    assert 'onclick="_submitProfileChangeEmailRequest' not in html
    assert 'onclick="_loadProfileMain' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "closest('[data-profile-action]')" in js.text
    assert 'data-profile-action="submit-password"' in js.text
    assert 'data-profile-action="submit-email-request"' in js.text
    assert "window._submitProfileChangePassword = _submitProfileChangePassword;" not in js.text
    assert "window._submitProfileChangeEmailRequest = _submitProfileChangeEmailRequest;" not in js.text
    assert "window._loadProfileMain = _loadProfileMain;" not in js.text


def test_profile_credentials_event_binding_in_node():
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

const byId = {};
function el(id, extra) {
  const node = {
    tagName: (extra && extra.tagName) || 'DIV',
    className: (extra && extra.className) || '',
    classList: classList(extra && extra.className),
    style: Object.assign({}, extra && extra.style),
    hidden: false,
    value: extra && extra.value || '',
    textContent: extra && extra.textContent || '',
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
      let n = this;
      while (n) {
        if (sel === '[data-profile-action]' && n.attributes && n.attributes['data-profile-action']) return n;
        if (sel === '[data-key-action]' && n.attributes && n.attributes['data-key-action']) return n;
        if (sel === '[data-device-action]' && n.attributes && n.attributes['data-device-action']) return n;
        n = n.parent;
      }
      return null;
    },
    contains() { return false; },
    appendChild(child) {
      this.children.push(child);
      if (child) child.parent = this;
    },
    replaceChildren(...nodes) {
      this.children = nodes.slice();
      nodes.forEach((n) => { if (n) n.parent = this; });
    },
    click() {
      (this.listeners.click || []).forEach((fn) => fn({ type: 'click', target: this, stopPropagation() {} }));
    },
    focus() {},
  };
  Object.defineProperty(node, 'id', {
    get() { return this._id || ''; },
    set(v) {
      this._id = String(v || '');
      if (this._id) byId[this._id] = this;
    }
  });
  node.id = id || '';
  if (extra && extra.className) node.classList = classList(extra.className);
  return node;
}

const contentEl = el('action-modal-content');
const modal = el('action-modal', { className: 'hidden' });
const toast = el('toast-container');
const notifications = [];
toast.appendChild = function (child) { notifications.push(child && child.textContent); };

const byIdInit = {
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
};
Object.assign(byId, byIdInit);

const docListeners = {};
const fetches = [];
const consoleLogs = [];
let passwordOk = false;

const document = {
  body: el('body'),
  documentElement: Object.assign(el('html'), { style: { setProperty() {} } }),
  readyState: 'complete',
  getElementById(id) { return byId[id] || (byId[id] = el(id)); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement(tag) { return el('', { tagName: String(tag || 'DIV').toUpperCase() }); },
  createTextNode(text) { return el('', { textContent: String(text || '') }); },
  addEventListener(type, fn) { (docListeners[type] || (docListeners[type] = [])).push(fn); },
  removeEventListener() {},
  elementFromPoint() { return null; },
};

const sandbox = {
  console: {
    log(...a) { consoleLogs.push(a.map(String).join(' ')); },
    warn(...a) { consoleLogs.push(a.map(String).join(' ')); },
    error(...a) { consoleLogs.push(a.map(String).join(' ')); },
  },
  setTimeout,
  clearTimeout,
  setInterval() { return 1; },
  clearInterval() {},
  URL,
  Event,
  requestAnimationFrame: (fn) => fn(),
  fetch: async (url, opts) => {
    const body = opts && opts.body && typeof opts.body === 'string' ? JSON.parse(opts.body) : {};
    const u = String(url);
    fetches.push({ url: u, body });
    if (u.includes('/api/user/profile-info')) {
      return { ok: true, json: async () => ({ ok: true, has_email_auth: true, auth_email: 'user@example.test', pending_email: null }) };
    }
    if (u.includes('/api/user/profile/change-password')) {
      if (!passwordOk) return { ok: true, json: async () => ({ ok: false, error: 'Неверный текущий пароль' }) };
      return { ok: true, json: async () => ({ ok: true, message: 'Пароль изменён' }) };
    }
    if (u.includes('/api/user/profile/change-email/request')) {
      return { ok: true, json: async () => ({ ok: true, message: 'Код отправлен' }) };
    }
    if (u.includes('/api/user/profile/change-email/verify')) {
      return { ok: true, json: async () => ({ ok: true, message: 'Email изменён' }) };
    }
    if (u.includes('/api/user/profile/change-email/cancel')) {
      return { ok: true, json: async () => ({ ok: true }) };
    }
    if (u.includes('/api/user/profile/change-email/resend')) {
      return { ok: true, json: async () => ({ ok: true }) };
    }
    return { ok: true, json: async () => ({ ok: true }), text: async () => '' };
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
  getComputedStyle() { return { backgroundColor: 'rgb(0,0,0)' }; },
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
  const evt = { target, type: 'click', stopPropagation() { this._stopped = true; } };
  (target.listeners.click || []).forEach((fn) => fn(evt));
  if (!evt._stopped) (docListeners.click || []).forEach((fn) => fn(evt));
}

async function waitUntil(pred) {
  for (let i = 0; i < 80; i++) {
    if (pred()) return true;
    await Promise.resolve();
  }
  return pred();
}

function actionBtn(action) {
  return el('', { attributes: { 'data-profile-action': action } });
}

function field(id) {
  return document.getElementById(id);
}

const SECRET_OLD = 'OldPassw0rd!';
const SECRET_NEW = 'NewPassw0rd!';
const SECRET_EMAIL_PW = 'Passw0rd!';
const SECRET_CODE = '654321';
const clickCountBefore = (docListeners.click || []).length;

sandbox._renderProfileChangePassword(contentEl);
const passwordMarkup = contentEl.innerHTML || '';
field('profile-current-password').value = SECRET_OLD;
field('profile-new-password').value = SECRET_NEW;
field('profile-new-password-confirm').value = 'mismatch';
click(actionBtn('submit-password'));

waitUntil(() => notifications.some((n) => n && n.includes('совпадают'))).then(() => {
  const mismatch = {
    notified: notifications.some((n) => n && n.includes('совпадают')),
    noFetch: !fetches.some((f) => f.url.includes('/change-password')),
  };
  byId['profile-new-password-confirm'].value = SECRET_NEW;
  click(actionBtn('submit-password'));
  return waitUntil(() => notifications.some((n) => n && String(n).includes('текущий пароль'))).then(() => {
    const wrong = fetches.filter((f) => f.url.includes('/change-password')).slice(-1)[0];
    const afterWrong = {
      error: notifications.some((n) => n && String(n).includes('текущий пароль')),
      body: wrong && wrong.body,
    };
    passwordOk = true;
    sandbox._renderProfileChangePassword(contentEl);
    const afterRerenderClicks = (docListeners.click || []).length;
    field('profile-current-password').value = SECRET_OLD;
    field('profile-new-password').value = SECRET_NEW;
    field('profile-new-password-confirm').value = SECRET_NEW;
    click(actionBtn('submit-password'));
    return waitUntil(() => fetches.filter((f) => f.url.includes('/change-password')).length >= 2 && notifications.some((n) => n && String(n).includes('изменён'))).then(() => {
      const okPw = fetches.filter((f) => f.url.includes('/change-password')).slice(-1)[0];
      sandbox._renderProfileChangeEmailRequest(contentEl);
      const emailMarkup = contentEl.innerHTML || '';
      field('profile-new-email').value = 'new@example.test';
      field('profile-email-password').value = SECRET_EMAIL_PW;
      click(actionBtn('submit-email-request'));
      return waitUntil(() => byId['profile-email-verify-btn']).then((ready) => {
        if (!ready) throw new Error('verify screen not rendered');
        const emailReq = fetches.filter((f) => f.url.includes('/change-email/request')).slice(-1)[0];
        field('profile-email-code').value = SECRET_CODE;
        const verifyBtn = byId['profile-email-verify-btn'];
        click(verifyBtn);
        return waitUntil(() => fetches.some((f) => f.url.includes('/change-email/verify'))).then(() => {
          const verify = fetches.filter((f) => f.url.includes('/change-email/verify')).slice(-1)[0];
          sandbox._renderProfileVerifyEmailCode(contentEl, 'new@example.test');
          click(actionBtn('cancel-email'));
          return waitUntil(() => fetches.some((f) => f.url.includes('/change-email/cancel'))).then(() => {
            click(actionBtn('back-profile'));
            return waitUntil(() => fetches.filter((f) => f.url.includes('/profile-info')).length >= 1).then(() => {
              const leakHay = [
                passwordMarkup,
                emailMarkup,
                JSON.stringify(byId['profile-password-submit-btn'] && byId['profile-password-submit-btn'].attributes || {}),
                JSON.stringify(verifyBtn && verifyBtn.attributes || {}),
                consoleLogs.join('\n'),
              ].join('\n');
              console.log(JSON.stringify({
                threw,
                clickCountBefore,
                afterRerenderClicks,
                mismatch,
                afterWrong,
                afterOk: {
                  current: okPw && okPw.body.current_password,
                  next: okPw && okPw.body.new_password,
                  token: okPw && okPw.body.token,
                },
                emailReq: emailReq && emailReq.body,
                verify: verify && verify.body,
                cancelled: fetches.some((f) => f.url.includes('/change-email/cancel')),
                backed: fetches.some((f) => f.url.includes('/profile-info')),
                passwordMarkupHasOnclick: /onclick=/.test(passwordMarkup),
                emailMarkupHasOnclick: /onclick=/.test(emailMarkup),
                passwordType: /type="password" id="profile-current-password"/.test(passwordMarkup),
                hasSubmitAction: /data-profile-action="submit-password"/.test(passwordMarkup),
                leaked: [SECRET_OLD, SECRET_NEW, SECRET_EMAIL_PW, SECRET_CODE].filter((s) => leakHay.includes(s)),
                createBridge: /window\._submitProfileChangePassword = _submitProfileChangePassword;/.test(src),
                emailBridge: /window\._submitProfileChangeEmailRequest = _submitProfileChangeEmailRequest;/.test(src),
                loadBridge: /window\._loadProfileMain = _loadProfileMain;/.test(src),
                payBridge: /window\.processPayment = processPayment;/.test(src),
              }));
            });
          });
        });
      });
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
    assert result["clickCountBefore"] >= 1
    assert result["afterRerenderClicks"] == result["clickCountBefore"]
    assert result["mismatch"]["notified"] is True
    assert result["mismatch"]["noFetch"] is True
    assert result["afterWrong"]["error"] is True
    assert result["afterWrong"]["body"]["current_password"] == "OldPassw0rd!"
    assert result["afterWrong"]["body"]["new_password"] == "NewPassw0rd!"
    assert result["afterOk"]["current"] == "OldPassw0rd!"
    assert result["afterOk"]["next"] == "NewPassw0rd!"
    assert result["afterOk"]["token"] == "t"
    assert result["emailReq"]["new_email"] == "new@example.test"
    assert result["emailReq"]["password"] == "Passw0rd!"
    assert result["verify"]["code"] == "654321"
    assert result["cancelled"] is True
    assert result["backed"] is True
    assert result["passwordMarkupHasOnclick"] is False
    assert result["emailMarkupHasOnclick"] is False
    assert result["passwordType"] is True
    assert result["hasSubmitAction"] is True
    assert result["leaked"] == []
    assert result["createBridge"] is False
    assert result["emailBridge"] is False
    assert result["loadBridge"] is False
    assert result["payBridge"] is False
