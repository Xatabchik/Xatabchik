"""Этап 2 PR 9: реферальные выплаты без inline onclick / window bridges."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
REMOVED_BRIDGES = (
    "requestReferralWithdraw",
    "openReferralMethodsModal",
    "_loadReferralPayoutMethods",
    "_selectPayoutType",
    "_selectPayoutBankByIndex",
    "_submitPayoutMethod",
    "_renderPayoutTypeStep",
    "_renderPayoutBankStep",
)


def _button_after(html: str, marker: str) -> str:
    return html.split(marker, 1)[1].split("</button>", 1)[0]


def test_referral_payout_have_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    assert "onclick=" not in _button_after(html, 'id="withdraw-request-btn"')
    assert "onclick=" not in _button_after(html, 'id="referral-methods-btn"')
    assert 'onclick="requestReferralWithdraw()' not in html
    assert 'onclick="openReferralMethodsModal()' not in html
    assert 'onclick="_selectPayoutType(' not in js
    assert 'onclick="_selectPayoutBankByIndex(' not in js
    assert 'onclick="_submitPayoutMethod()' not in js
    assert 'onclick="_loadReferralPayoutMethods(' not in js
    assert 'onclick="_renderPayoutTypeStep(' not in js
    assert 'onclick="_renderPayoutBankStep(' not in js
    assert "closest('[data-payout-action]')" in js
    assert 'data-payout-action="select-type"' in js
    assert 'data-payout-action="select-bank"' in js
    assert 'data-payout-action="submit-method"' in js
    assert 'data-payout-action="back-methods"' in js
    assert 'data-payout-action="back-type"' in js
    assert "data-payout-action=\"${backAction}\"" in js
    assert "'back-bank'" in js
    assert "getElementById('withdraw-request-btn')?.addEventListener('click', requestReferralWithdraw)" in js
    assert "getElementById('referral-methods-btn')?.addEventListener('click', openReferralMethodsModal)" in js
    assert 'onclick="openTopUpModal()"' not in html
    assert "window.processPayment = processPayment;" not in js


def test_removed_referral_payout_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.openTopUpModal = openTopUpModal;" not in js
    assert "window.processPayment = processPayment;" not in js
    assert "window.closePaymentModal = closePaymentModal;" not in js
    assert "window.setPurchaseMode = setPurchaseMode;" not in js
    assert "window.openActionModal = openActionModal;" not in js


def test_served_page_referral_payout_use_delegation(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=16101, username="payout-bind")
    token = issue_auth_token(16101)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'onclick="requestReferralWithdraw()' not in html
    assert 'onclick="openReferralMethodsModal()' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "closest('[data-payout-action]')" in js.text
    assert 'data-payout-action="submit-method"' in js.text
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js.text, name


def test_referral_payout_event_binding_in_node():
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
        if (sel === '[data-payout-action]' && n.attributes && n.attributes['data-payout-action']) return n;
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

const withdrawBtn = el('withdraw-request-btn', { tagName: 'BUTTON' });
const methodsBtn = el('referral-methods-btn', { tagName: 'BUTTON' });

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
  'withdraw-request-btn': withdrawBtn,
  'referral-methods-btn': methodsBtn,
};
Object.assign(byId, byIdInit);

const docListeners = {};
const fetches = [];
const consoleLogs = [];

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
    if (u.includes('/api/referral/payout-methods/list')) {
      return { ok: true, json: async () => ({ ok: true, methods: [], min_withdraw: 100, withdraw_enabled: true }) };
    }
    if (u.includes('/api/referral/available-method-types')) {
      return { ok: true, json: async () => ({
        ok: true,
        methods: [
          { type: 'card', label: 'Номер карты', icon: 'credit_card' },
          { type: 'sbp', label: 'СБП', icon: 'phone_android' },
        ],
        sbp_banks: ['Сбербанк', 'Т-Банк'],
      }) };
    }
    if (u.includes('/api/referral/payout-methods/add')) {
      const digits = String(body.requisite_value || '').replace(/\D/g, '');
      if (body.method_type === 'card' && digits.length < 16) {
        return { ok: true, json: async () => ({ ok: false, message: 'Номер карты должен содержать 16–19 цифр.' }) };
      }
      if (body.method_type === 'sbp' && digits.length < 10) {
        return { ok: true, json: async () => ({ ok: false, message: 'Укажите номер телефона для СБП (10–15 цифр).' }) };
      }
      return { ok: true, json: async () => ({ ok: true, message: 'Метод добавлен' }) };
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

function payoutBtn(action, index) {
  const attrs = { 'data-payout-action': action };
  if (index != null) attrs['data-payout-index'] = String(index);
  return el('', { attributes: attrs });
}

const SECRET_CARD = '4111111111111111';
const SECRET_PHONE = '+79001234567';
const clickCountBefore = (docListeners.click || []).length;

sandbox._referralWithdrawEnabled = true;
sandbox._referralMinWithdraw = 100;
sandbox._referralAvailableBalance = 10;
click(withdrawBtn);

waitUntil(() => notifications.some((n) => n && String(n).includes('Минимальная сумма'))).then(() => {
  const insufficient = {
    notified: notifications.some((n) => n && String(n).includes('Минимальная сумма')),
    noWithdrawFetch: !fetches.some((f) => f.url.includes('/request-withdrawal')),
  };
  click(methodsBtn);
  return waitUntil(() => fetches.some((f) => f.url.includes('/payout-methods/list'))).then(() => {
    sandbox._payoutMethodState = {
      methods: [
        { type: 'card', label: 'Номер карты', icon: 'credit_card' },
        { type: 'sbp', label: 'СБП', icon: 'phone_android' },
      ],
      sbpBanks: ['Сбербанк', 'Т-Банк'],
      type: null,
      bank: null,
    };
    sandbox._renderPayoutTypeStep(contentEl);
    const typeMarkup = contentEl.innerHTML || '';
    click(payoutBtn('select-type', 0));
    const cardMarkup = contentEl.innerHTML || '';
    click(payoutBtn('submit-method'));
    return waitUntil(() => notifications.some((n) => n && String(n).includes('Введите реквизиты'))).then(() => {
      const emptyNoFetch = !fetches.some((f) => f.url.includes('/payout-methods/add'));
      document.getElementById('payout-requisite-input').value = '1234';
      click(payoutBtn('submit-method'));
      return waitUntil(() => notifications.some((n) => n && String(n).includes('16–19'))).then(() => {
        const invalid = fetches.filter((f) => f.url.includes('/payout-methods/add')).slice(-1)[0];
        sandbox._renderPayoutRequisiteStep(contentEl);
        const afterRerenderClicks = (docListeners.click || []).length;
        document.getElementById('payout-requisite-input').value = SECRET_CARD;
        click(payoutBtn('submit-method'));
        return waitUntil(() => fetches.filter((f) => f.url.includes('/payout-methods/add')).length >= 2 && notifications.some((n) => n && String(n).includes('добавлен'))).then(() => {
          const okCard = fetches.filter((f) => f.url.includes('/payout-methods/add')).slice(-1)[0];
          sandbox._payoutMethodState.type = null;
          sandbox._payoutMethodState.bank = null;
          sandbox._renderPayoutTypeStep(contentEl);
          click(payoutBtn('select-type', 1));
          const bankMarkup = contentEl.innerHTML || '';
          click(payoutBtn('select-bank', 0));
          const sbpMarkup = contentEl.innerHTML || '';
          document.getElementById('payout-requisite-input').value = SECRET_PHONE;
          click(payoutBtn('submit-method'));
          return waitUntil(() => fetches.filter((f) => f.url.includes('/payout-methods/add')).length >= 3).then(() => {
            const okSbp = fetches.filter((f) => f.url.includes('/payout-methods/add')).slice(-1)[0];
            const leakHay = [
              typeMarkup, cardMarkup, bankMarkup, sbpMarkup,
              JSON.stringify((payoutBtn('submit-method')).attributes),
              consoleLogs.join('\n'),
            ].join('\n');
            console.log(JSON.stringify({
              threw,
              clickCountBefore,
              afterRerenderClicks,
              insufficient,
              emptyNoFetch,
              typeMarkupHasOnclick: /onclick=/.test(typeMarkup),
              cardMarkupHasOnclick: /onclick=/.test(cardMarkup),
              bankMarkupHasOnclick: /onclick=/.test(bankMarkup),
              hasSelectType: /data-payout-action="select-type"/.test(typeMarkup),
              hasSelectBank: /data-payout-action="select-bank"/.test(bankMarkup),
              hasSubmit: /data-payout-action="submit-method"/.test(cardMarkup),
              bankUsesIndex: /data-payout-index="0"/.test(bankMarkup) && !/data-payout-index="Сбербанк"/.test(bankMarkup),
              invalidBody: invalid && invalid.body,
              okCard: okCard && okCard.body,
              okSbp: okSbp && okSbp.body,
              leaked: [SECRET_CARD, SECRET_PHONE].filter((s) => leakHay.includes(s)),
              withdrawBound: (withdrawBtn.listeners.click || []).length >= 1,
              methodsBound: (methodsBtn.listeners.click || []).length >= 1,
              withdrawBridge: /window\.requestReferralWithdraw = requestReferralWithdraw;/.test(src),
              methodsBridge: /window\.openReferralMethodsModal = openReferralMethodsModal;/.test(src),
              typeBridge: /window\._selectPayoutType = _selectPayoutType;/.test(src),
              submitBridge: /window\._submitPayoutMethod = _submitPayoutMethod;/.test(src),
              payBridge: /window\.processPayment = processPayment;/.test(src),
            }));
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
    assert result["insufficient"]["notified"] is True
    assert result["insufficient"]["noWithdrawFetch"] is True
    assert result["emptyNoFetch"] is True
    assert result["typeMarkupHasOnclick"] is False
    assert result["cardMarkupHasOnclick"] is False
    assert result["bankMarkupHasOnclick"] is False
    assert result["hasSelectType"] is True
    assert result["hasSelectBank"] is True
    assert result["hasSubmit"] is True
    assert result["bankUsesIndex"] is True
    assert result["invalidBody"]["requisite_value"] == "1234"
    assert result["invalidBody"]["method_type"] == "card"
    assert result["okCard"]["requisite_value"] == "4111111111111111"
    assert result["okCard"]["method_type"] == "card"
    assert result["okCard"]["token"] == "t"
    assert result["okSbp"]["requisite_value"] == "+79001234567"
    assert result["okSbp"]["method_type"] == "sbp"
    assert result["okSbp"]["bank_name"] == "Сбербанк"
    assert result["leaked"] == []
    assert result["withdrawBound"] is True
    assert result["methodsBound"] is True
    assert result["withdrawBridge"] is False
    assert result["methodsBridge"] is False
    assert result["typeBridge"] is False
    assert result["submitBridge"] is False
    assert result["payBridge"] is False
