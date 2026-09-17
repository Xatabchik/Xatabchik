"""Этап 2 PR 7: саппорт-чат без inline onclick / window bridges."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
REMOVED_BRIDGES = (
    "closeSupportTicket",
    "createSupportTicket",
    "sendSupportMessage",
    "resetSupportChat",
)
SUPPORT_IDS = (
    "support-create-btn",
    "support-send-btn",
    "support-close-btn",
    "support-reset-btn",
    "support-attach-btn",
)


def _button_after(html: str, marker: str) -> str:
    return html.split(marker, 1)[1].split("</button>", 1)[0]


def test_support_chat_has_no_inline_handlers():
    html = mini_app_html()
    js = mini_app_js()
    for btn_id in SUPPORT_IDS:
        assert f'id="{btn_id}"' in html
        assert "onclick=" not in _button_after(html, f'id="{btn_id}"')
    assert 'onclick="createSupportTicket' not in html
    assert 'onclick="sendSupportMessage' not in html
    assert 'onclick="closeSupportTicket' not in html
    assert 'onclick="resetSupportChat' not in html
    assert "getElementById('support-create-btn')?.addEventListener('click', createSupportTicket)" in js
    assert "getElementById('support-send-btn')?.addEventListener('click', sendSupportMessage)" in js
    assert "getElementById('support-close-btn')?.addEventListener('click', closeSupportTicket)" in js
    assert "getElementById('support-reset-btn')?.addEventListener('click', resetSupportChat)" in js
    assert "getElementById('support-attach-btn')?.addEventListener('click', () => {" in js
    assert "onclick=\"openTopUpModal()\"" not in html
    assert "window.processPayment = processPayment;" not in js
    # Сообщения чата — createElement, без onclick; список тикетов уже точечный listener при render.
    assert "container.replaceChildren()" in js
    assert "btn.addEventListener('click', () => openSupportTicket(t.ticket_id))" in js


def test_removed_support_handler_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.openTopUpModal = openTopUpModal;" not in js
    assert "window.processPayment = processPayment;" not in js
    assert "window.setPurchaseMode = setPurchaseMode;" not in js


def test_served_page_support_has_listeners_not_onclick(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=15701, username="support-bind")
    token = issue_auth_token(15701)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert 'id="support-create-btn"' in html
    assert 'id="support-reset-btn"' in html
    assert 'onclick="createSupportTicket' not in html
    assert 'onclick="sendSupportMessage' not in html
    assert 'onclick="closeSupportTicket' not in html
    assert 'onclick="resetSupportChat' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "addEventListener('click', createSupportTicket)" in js.text
    assert "addEventListener('click', sendSupportMessage)" in js.text
    assert "window.createSupportTicket = createSupportTicket;" not in js.text
    assert "window.sendSupportMessage = sendSupportMessage;" not in js.text
    assert "window.closeSupportTicket = closeSupportTicket;" not in js.text
    assert "window.resetSupportChat = resetSupportChat;" not in js.text


def test_support_chat_event_binding_in_node():
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
  const node = {
    id: id || '',
    tagName: (extra && extra.tagName) || 'DIV',
    className: (extra && extra.className) || '',
    classList: classList(extra && extra.className),
    style: Object.assign({}, extra && extra.style),
    hidden: false,
    value: extra && extra.value || '',
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
    appendChild(child) {
      this.children.push(child);
      if (child) child.parent = this;
    },
    replaceChildren(...nodes) {
      this.children = nodes.slice();
      nodes.forEach((n) => { if (n) n.parent = this; });
    },
    click() {
      (this.listeners.click || []).forEach((fn) => fn({ type: 'click', target: this }));
    },
    focus() {},
  };
  Object.defineProperty(node, 'childElementCount', { get() { return this.children.length; } });
  if (extra && extra.className) node.classList = classList(extra.className);
  return node;
}

function collectText(node) {
  const parts = [];
  function walk(n) {
    if (!n) return;
    if (n.textContent) parts.push(n.textContent);
    (n.children || []).forEach(walk);
  }
  walk(node);
  return parts.join(' ');
}

const createBtn = el('support-create-btn');
const sendBtn = el('support-send-btn');
const closeBtn = el('support-close-btn', { className: 'hidden' });
const resetBtn = el('support-reset-btn');
const attachBtn = el('support-attach-btn');
const fileInput = el('support-file-input');
fileInput.click = function () { fileClicks.push(1); };
const subjectInput = el('support-subject-input', { tagName: 'INPUT' });
const messageInput = el('support-message-input', { tagName: 'TEXTAREA' });
const messages = el('support-messages-container');
const ticketsList = el('support-tickets-list', { className: 'hidden' });
const loading = el('support-loading');
const createView = el('support-create-view', { className: 'hidden' });
const chatView = el('support-chat-view', { className: 'hidden' });
const headerTitle = el('support-header-title');
const statusBadge = el('support-status-badge', { className: 'hidden' });
const inputArea = el('support-input-area');
const closedArea = el('support-closed-area', { className: 'hidden' });
const toast = el('toast-container');
const notifications = [];
const fileClicks = [];
toast.appendChild = function (child) { notifications.push(child && child.textContent); };

const byId = {
  'support-create-btn': createBtn,
  'support-send-btn': sendBtn,
  'support-close-btn': closeBtn,
  'support-reset-btn': resetBtn,
  'support-attach-btn': attachBtn,
  'support-file-input': fileInput,
  'support-subject-input': subjectInput,
  'support-message-input': messageInput,
  'support-messages-container': messages,
  'support-tickets-list': ticketsList,
  'support-loading': loading,
  'support-create-view': createView,
  'support-chat-view': chatView,
  'support-header-title': headerTitle,
  'support-status-badge': statusBadge,
  'support-input-area': inputArea,
  'support-closed-area': closedArea,
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

const docListeners = {};
const fetches = [];
const ticket = { ticket_id: 7, subject: '', status: null, messages: [] };

const document = {
  body: el('body'),
  documentElement: Object.assign(el('html'), { style: { setProperty() {} } }),
  readyState: 'complete',
  getElementById(id) { return byId[id] || el(id); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement(tag) { return el(tag || 'anon', { tagName: String(tag || 'DIV').toUpperCase() }); },
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
    const body = opts && opts.body && typeof opts.body === 'string' ? JSON.parse(opts.body) : {};
    const u = String(url);
    fetches.push({ url: u, body });
    if (u.includes('/api/support/create')) {
      ticket.subject = body.subject;
      ticket.status = 'open';
      ticket.messages = [];
      return { ok: true, json: async () => ({ ok: true, ticket_id: ticket.ticket_id }) };
    }
    if (u.includes('/api/support/send')) {
      ticket.messages.push({
        sender: 'user',
        content: body.message,
        created_at: '2026-09-17 01:00:00',
      });
      return { ok: true, json: async () => ({ ok: true }) };
    }
    if (u.includes('/api/support/close')) {
      ticket.status = 'closed';
      return { ok: true, json: async () => ({ ok: true }) };
    }
    if (u.includes('/api/support/ticket')) {
      return {
        ok: true,
        json: async () => ({
          ok: true,
          ticket_id: ticket.ticket_id,
          subject: ticket.subject,
          status: ticket.status,
          messages: ticket.messages.slice(),
        }),
      };
    }
    if (u.includes('/api/support/status')) {
      return {
        ok: true,
        json: async () => ({
          ok: true,
          has_ticket: ticket.status === 'open',
          tickets: [{ ticket_id: ticket.ticket_id, subject: ticket.subject, status: ticket.status, updated_at: '2026-09-17' }],
        }),
      };
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
  (target.listeners.click || []).forEach((fn) => fn({ target, type: 'click', stopPropagation() {} }));
}

async function waitUntil(pred) {
  for (let i = 0; i < 40; i++) {
    if (pred()) return true;
    await Promise.resolve();
  }
  return pred();
}

const bindings = {
  create: (createBtn.listeners.click || []).length,
  send: (sendBtn.listeners.click || []).length,
  close: (closeBtn.listeners.click || []).length,
  reset: (resetBtn.listeners.click || []).length,
  attach: (attachBtn.listeners.click || []).length,
  keypress: (messageInput.listeners.keypress || []).length,
};

subjectInput.value = 'Не работает VPN';
click(createBtn);

waitUntil(() => fetches.some((f) => f.url.includes('/api/support/create')) && !chatView.classList.contains('hidden')).then(() => {
  const afterCreate = {
    created: fetches.some((f) => f.url.includes('/api/support/create') && f.body.subject === 'Не работает VPN'),
    chatOpen: !chatView.classList.contains('hidden'),
    createHidden: createView.classList.contains('hidden'),
    title: headerTitle.textContent,
  };
  messageInput.value = 'Первое сообщение';
  click(sendBtn);
  return waitUntil(() => collectText(messages).includes('Первое сообщение')).then(() => {
    const afterFirstSend = {
      sent: fetches.filter((f) => f.url.includes('/api/support/send')).map((f) => f.body.message),
      history: collectText(messages),
      sendStillBound: (sendBtn.listeners.click || []).length,
    };
    messageInput.value = 'Второе сообщение';
    click(sendBtn);
    return waitUntil(() => collectText(messages).includes('Второе сообщение')).then(() => {
      const afterSecondSend = {
        sent: fetches.filter((f) => f.url.includes('/api/support/send')).map((f) => f.body.message),
        history: collectText(messages),
        sendStillBound: (sendBtn.listeners.click || []).length,
      };
      click(closeBtn);
      return waitUntil(() => ticket.status === 'closed' && !closedArea.classList.contains('hidden')).then(() => {
        const afterClose = {
          closed: fetches.some((f) => f.url.includes('/api/support/close') && f.body.ticket_id === 7),
          closedAreaVisible: !closedArea.classList.contains('hidden'),
          inputHidden: inputArea.classList.contains('hidden'),
        };
        click(resetBtn);
        return waitUntil(() => !createView.classList.contains('hidden') && fetches.some((f) => f.url.includes('/api/support/status'))).then(() => {
          const afterReset = {
            createVisible: !createView.classList.contains('hidden'),
            chatHidden: chatView.classList.contains('hidden'),
            title: headerTitle.textContent,
            createStillBound: (createBtn.listeners.click || []).length,
            sendStillBound: (sendBtn.listeners.click || []).length,
          };
          subjectInput.value = 'Второй тикет';
          click(createBtn);
          return waitUntil(() => fetches.filter((f) => f.url.includes('/api/support/create')).length >= 2 && !chatView.classList.contains('hidden')).then(() => {
            click(attachBtn);
            console.log(JSON.stringify({
              threw,
              bindings,
              afterCreate,
              afterFirstSend,
              afterSecondSend,
              afterClose,
              afterReset,
              afterReopen: {
                created: fetches.filter((f) => f.url.includes('/api/support/create')).map((f) => f.body.subject),
                chatOpen: !chatView.classList.contains('hidden'),
                createStillBound: (createBtn.listeners.click || []).length,
              },
              attachOpenedFile: fileClicks.length >= 1,
              createBridge: /window\.createSupportTicket = createSupportTicket;/.test(src),
              sendBridge: /window\.sendSupportMessage = sendSupportMessage;/.test(src),
              closeBridge: /window\.closeSupportTicket = closeSupportTicket;/.test(src),
              resetBridge: /window\.resetSupportChat = resetSupportChat;/.test(src),
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
    assert result["bindings"]["create"] >= 1
    assert result["bindings"]["send"] >= 1
    assert result["bindings"]["close"] >= 1
    assert result["bindings"]["reset"] >= 1
    assert result["bindings"]["attach"] >= 1
    assert result["afterCreate"]["created"] is True
    assert result["afterCreate"]["chatOpen"] is True
    assert "VPN" in result["afterCreate"]["title"] or "Тикет" in result["afterCreate"]["title"]
    assert "Первое сообщение" in result["afterFirstSend"]["sent"]
    assert "Первое сообщение" in result["afterFirstSend"]["history"]
    assert result["afterFirstSend"]["sendStillBound"] == 1
    assert "Второе сообщение" in result["afterSecondSend"]["sent"]
    assert "Второе сообщение" in result["afterSecondSend"]["history"]
    assert result["afterSecondSend"]["sendStillBound"] == 1
    assert result["afterClose"]["closed"] is True
    assert result["afterClose"]["closedAreaVisible"] is True
    assert result["afterReset"]["createVisible"] is True
    assert result["afterReset"]["chatHidden"] is True
    assert result["afterReset"]["createStillBound"] == 1
    assert "Второй тикет" in result["afterReopen"]["created"]
    assert result["afterReopen"]["chatOpen"] is True
    assert result["afterReopen"]["createStillBound"] == 1
    assert result["attachOpenedFile"] is True
    assert result["createBridge"] is False
    assert result["sendBridge"] is False
    assert result["closeBridge"] is False
    assert result["resetBridge"] is False
    assert result["payBridge"] is False
