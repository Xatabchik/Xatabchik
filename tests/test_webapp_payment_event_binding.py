"""Этап 2 PR 10: платежи и top-up без inline onclick / window bridges."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
REMOVED_BRIDGES = (
    "openTopUpModal",
    "closePaymentModal",
    "openMethodsList",
    "applyDiscountPromo",
    "processPayment",
    "changePaymentStep",
    "goToPaymentLink",
    "verifyPlategaPayment",
    "cancelPayment",
    "copySuccessKey",
    "pickLtePackage",
    "confirmMethod",
    "_topUpContinueToMethods",
    "_renderTopUpAmountStep",
    "_submitTopUpPayment",
    "_reopenTopUpPaymentLink",
    "verifyPlategaTopUp",
    "_stopTrackingTopUp",
)
KEPT_BRIDGES = ()


def _button_after(html: str, marker: str) -> str:
    return html.split(marker, 1)[1].split("</button>", 1)[0]


def test_payment_and_topup_have_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    assert "onclick=" not in _button_after(html, 'id="topup-finance-btn"')
    assert "onclick=" not in _button_after(html, 'id="method-selector-btn"')
    assert "onclick=" not in _button_after(html, 'id="apply-promo-btn"')
    assert "onclick=" not in _button_after(html, 'id="final-pay-btn"')
    assert "onclick=" not in _button_after(html, 'id="redirect-pay-btn"')
    assert "onclick=" not in _button_after(html, 'id="verify-platega-pay-btn"')
    assert "onclick=" not in _button_after(html, 'id="success-connect-btn"')
    assert 'onclick="openTopUpModal()' not in html
    assert 'onclick="processPayment()' not in html
    assert 'onclick="closePaymentModal()' not in html
    assert 'onclick="openMethodsList()' not in html
    assert 'onclick="applyDiscountPromo()' not in html
    assert 'onclick="changePaymentStep(' not in html
    assert 'onclick="goToPaymentLink()' not in html
    assert 'onclick="verifyPlategaPayment()' not in html
    assert 'onclick="cancelPayment()' not in html
    assert 'onclick="copySuccessKey()' not in html
    assert 'onclick="confirmMethod(' not in js
    assert "onclick='pickLtePackage(" not in js
    assert 'onclick="_submitTopUpPayment(' not in js
    assert 'onclick="_topUpContinueToMethods()' not in js
    assert 'onclick="_renderTopUpAmountStep(' not in js
    assert 'onclick="_reopenTopUpPaymentLink()' not in js
    assert 'onclick="verifyPlategaTopUp()' not in js
    assert 'onclick="_stopTrackingTopUp()' not in js
    assert "closest('[data-payment-action]')" in js
    assert "closest('[data-topup-action]')" in js
    assert 'data-payment-action="open-methods"' in html
    assert 'data-payment-action="process"' in html
    assert 'data-payment-action="apply-promo"' in html
    assert 'data-topup-action="continue"' in js
    assert 'data-topup-action="submit-method"' in js
    assert 'data-topup-action="preset-amount"' in js
    assert "getElementById('topup-finance-btn')?.addEventListener('click', openTopUpModal)" in js
    assert 'onclick="setPurchaseMode(' not in html
    assert "window.setPurchaseMode = setPurchaseMode;" not in js
    assert "window.openLteTopup = openLteTopup;" not in js


def test_removed_payment_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    for name in KEPT_BRIDGES:
        assert f"window.{name} = {name};" in js, name


def test_served_page_payment_use_delegation(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=16201, username="pay-bind")
    token = issue_auth_token(16201)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'onclick="openTopUpModal()' not in html
    assert 'onclick="processPayment()' not in html
    assert 'onclick="closePaymentModal()' not in html
    assert 'data-payment-action="process"' in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "closest('[data-payment-action]')" in js.text
    assert "closest('[data-topup-action]')" in js.text
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js.text, name
    assert "window.setPurchaseMode = setPurchaseMode;" not in js.text


def test_payment_event_binding_in_node():
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
    removeAttribute(name) { delete this.attributes[name]; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    closest(sel) {
      let n = this;
      while (n) {
        if (sel === '[data-topup-action]' && n.attributes && n.attributes['data-topup-action']) return n;
        if (sel === '[data-payment-action]' && n.attributes && n.attributes['data-payment-action']) return n;
        if (sel === '[data-payout-action]' && n.attributes && n.attributes['data-payout-action']) return n;
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
    scrollIntoView() {},
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

const topupFinanceBtn = el('topup-finance-btn', { tagName: 'BUTTON' });
const promoInput = el('confirm-promo-input', { tagName: 'INPUT' });
const applyPromoBtn = el('apply-promo-btn', { tagName: 'BUTTON' });
const finalPayBtn = el('final-pay-btn', { tagName: 'BUTTON' });
finalPayBtn.disabled = true;
const payModal = el('payment-modal', { className: 'hidden' });
const amountInput = el('topup-amount-input', { tagName: 'INPUT' });

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
  'withdraw-request-btn': el('withdraw-request-btn', { tagName: 'BUTTON' }),
  'referral-methods-btn': el('referral-methods-btn', { tagName: 'BUTTON' }),
  'topup-finance-btn': topupFinanceBtn,
  'confirm-promo-input': promoInput,
  'apply-promo-btn': applyPromoBtn,
  'final-pay-btn': finalPayBtn,
  'final-pay-btn-text': el('final-pay-btn-text'),
  'confirm-plan-name': el('confirm-plan-name'),
  'confirm-plan-details': el('confirm-plan-details'),
  'confirm-method-icon': el('confirm-method-icon'),
  'confirm-method-name': el('confirm-method-name'),
  'confirm-promo-wrap': el('confirm-promo-wrap'),
  'method-icon-container': el('method-icon-container'),
  'payment-modal': payModal,
  'payment-backdrop': el('payment-backdrop', { className: 'opacity-0 pointer-events-none' }),
  'payment-card': el('payment-card', { className: 'translate-y-full' }),
  'payment-step-confirm': el('payment-step-confirm', { className: '' }),
  'payment-step-select': el('payment-step-select', { className: 'hidden' }),
  'payment-step-waiting': el('payment-step-waiting', { className: 'hidden' }),
  'payment-step-success': el('payment-step-success', { className: 'hidden' }),
  'payment-step-lte-packages': el('payment-step-lte-packages', { className: 'hidden' }),
  'payment-methods-list': el('payment-methods-list'),
  'waiting-desc': el('waiting-desc'),
  'redirect-pay-btn': el('redirect-pay-btn', { tagName: 'BUTTON' }),
  'verify-platega-pay-btn': el('verify-platega-pay-btn', { tagName: 'BUTTON', className: 'hidden' }),
  'success-key': el('success-key'),
  'success-expiry': el('success-expiry'),
  'topup-amount-input': amountInput,
};
Object.assign(byId, byIdInit);

const docListeners = {};
const fetches = [];
const consoleLogs = [];
const opened = [];
const PAY_URL = 'https://yookassa.test/pay/secret-token-xyz';
const PROMO = 'SECRETPROMO';

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
    if (u.includes('/api/payment-methods')) {
      return { ok: true, json: async () => ({ ok: true, methods: [
        { id: 'pay_yookassa', name: 'YooKassa', icon: 'account_balance_wallet' },
        { id: 'pay_balance', name: 'Баланс', icon: 'account_balance', balance: 0 },
      ] }) };
    }
    if (u.includes('/api/create-topup-payment')) {
      return { ok: true, json: async () => ({ ok: true, payment_id: 'top-1', payment_url: PAY_URL }) };
    }
    if (u.includes('/api/create-payment')) {
      return { ok: true, json: async () => ({ ok: true, payment_id: 'pay-1', payment_url: PAY_URL }) };
    }
    if (u.includes('/api/apply-promo')) {
      return { ok: true, json: async () => ({ ok: true, promo_type: 'discount', new_price: 250 }) };
    }
    if (u.includes('/api/check-payment')) {
      return { ok: true, json: async () => ({ ok: true, paid: false }) };
    }
    return { ok: true, json: async () => ({ ok: true }), text: async () => '' };
  },
  document,
  localStorage: { theme: 'dark', getItem() { return null; }, setItem() {}, removeItem() {} },
  Telegram: { WebApp: { ready() {}, expand() {}, initData: '', initDataUnsafe: {}, platform: 'unknown', openLink(u) { opened.push(u); } } },
  matchMedia() { return { matches: true, addEventListener() {} } },
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() { return true; },
  location: { href: 'https://example.test/', hash: '', pathname: '/', reload() {} },
  history: { replaceState() {} },
  innerHeight: 800,
  innerWidth: 400,
  visualViewport: { height: 800, addEventListener() {} },
  getAuthToken() { return 't'; },
  getTgInitData() { return ''; },
  getComputedStyle() { return { backgroundColor: 'rgb(0,0,0)' }; },
  open(u) { opened.push(u); },
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

function topupBtn(action, extra) {
  const attrs = Object.assign({ 'data-topup-action': action }, extra || {});
  return el('', { attributes: attrs });
}
function paymentBtn(action, extra) {
  const attrs = Object.assign({ 'data-payment-action': action }, extra || {});
  return el('', { attributes: attrs });
}

const clickCountBefore = (docListeners.click || []).length;

click(topupFinanceBtn);
waitUntil(() => (contentEl.innerHTML || '').includes('topup-amount-input')).then(() => {
  const amountMarkup = contentEl.innerHTML || '';
  click(topupBtn('preset-amount', { 'data-topup-amount': '300' }));
  const presetValue = document.getElementById('topup-amount-input').value;
  document.getElementById('topup-amount-input').value = '300';
    click(topupBtn('continue'));
  return waitUntil(() => (contentEl.innerHTML || '').includes('data-topup-action="submit-method"')).then(() => {
    const methodsMarkup = contentEl.innerHTML || '';
    click(topupBtn('submit-method', { 'data-topup-index': '0' }));
    return waitUntil(() => (contentEl.innerHTML || '').includes('data-topup-action="reopen-link"')).then(() => {
      const topupCreate = fetches.filter((f) => f.url.includes('/api/create-topup-payment')).slice(-1)[0];
      const waitingMarkup = contentEl.innerHTML || '';
      sandbox._renderTopUpAmountStep(contentEl);
      const afterRerenderClicks = (docListeners.click || []).length;
      sandbox.openPaymentModal(7, 'host-a', 'new', null, 300, 'Plan', 1, 0, '1', '0');
      promoInput.value = PROMO;
      click(paymentBtn('apply-promo'));
      return waitUntil(() => applyPromoBtn.style.display === 'none' || notifications.some((n) => n && String(n).includes('Промокод'))).then(() => {
        const promoFetch = fetches.filter((f) => f.url.includes('/api/apply-promo')).slice(-1)[0];
        sandbox._paymentMethodsVisible = [
          { id: 'pay_yookassa', name: 'YooKassa', icon: 'wallet' },
        ];
        click(paymentBtn('confirm-method', { 'data-payment-index': '0' }));
        click(paymentBtn('process'));
        return waitUntil(() => fetches.some((f) => f.url.includes('/api/create-payment'))).then(() => {
          const payCreate = fetches.filter((f) => f.url.includes('/api/create-payment')).slice(-1)[0];
          click(paymentBtn('cancel'));
          const leakHay = [amountMarkup, methodsMarkup, waitingMarkup, consoleLogs.join('\n')].join('\n');
          console.log(JSON.stringify({
            threw,
            clickCountBefore,
            afterRerenderClicks,
            amountMarkupHasOnclick: /onclick=/.test(amountMarkup),
            methodsMarkupHasOnclick: /onclick=/.test(methodsMarkup),
            waitingMarkupHasOnclick: /onclick=/.test(waitingMarkup),
            hasPreset: /data-topup-action="preset-amount"/.test(amountMarkup),
            hasContinue: /data-topup-action="continue"/.test(amountMarkup),
            hasSubmitMethod: /data-topup-action="submit-method"/.test(methodsMarkup),
            hasReopen: /data-topup-action="reopen-link"/.test(waitingMarkup),
            waitingHasPayUrl: waitingMarkup.includes(PAY_URL),
            waitingHasPayUrlAttr: /data-[^=]*=[^>]*secret-token/.test(waitingMarkup),
            presetValue,
            topupCreate: topupCreate && topupCreate.body,
            promoFetch: promoFetch && promoFetch.body,
            payCreate: payCreate && payCreate.body,
            leakedPromo: leakHay.includes(PROMO) && !promoInput.value,
            leakedUrl: leakHay.includes(PAY_URL),
            topupBound: (topupFinanceBtn.listeners.click || []).length >= 1,
            topupBridge: /window\.openTopUpModal = openTopUpModal;/.test(src),
            processBridge: /window\.processPayment = processPayment;/.test(src),
            closePayBridge: /window\.closePaymentModal = closePaymentModal;/.test(src),
            submitTopUpBridge: /window\._submitTopUpPayment = _submitTopUpPayment;/.test(src),
            purchaseBridge: /window\.setPurchaseMode = setPurchaseMode;/.test(src),
            lteBridge: /window\.openLteTopup = openLteTopup;/.test(src),
          }));
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
    assert result["amountMarkupHasOnclick"] is False
    assert result["methodsMarkupHasOnclick"] is False
    assert result["waitingMarkupHasOnclick"] is False
    assert result["hasPreset"] is True
    assert result["hasContinue"] is True
    assert result["hasSubmitMethod"] is True
    assert result["hasReopen"] is True
    assert result["waitingHasPayUrl"] is False
    assert result["waitingHasPayUrlAttr"] is False
    assert result["presetValue"] == "300"
    assert result["topupCreate"]["amount"] == 300
    assert result["topupCreate"]["payment_method"] == "pay_yookassa"
    assert result["topupCreate"]["token"] == "t"
    assert result["promoFetch"]["promo_code"] == "SECRETPROMO"
    assert result["payCreate"]["payment_method"] == "pay_yookassa"
    assert result["payCreate"]["promo_code"] == "SECRETPROMO"
    assert result["payCreate"]["plan_id"] == 7
    assert result["leakedUrl"] is False
    assert result["topupBound"] is True
    assert result["topupBridge"] is False
    assert result["processBridge"] is False
    assert result["closePayBridge"] is False
    assert result["submitTopUpBridge"] is False
    assert result["purchaseBridge"] is False
    assert result["lteBridge"] is False
