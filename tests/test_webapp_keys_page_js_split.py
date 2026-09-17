"""Шаг 2 split app.js: страница «Ключи» вынесена в keys-page.js 1:1."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import (
    KEYS_PAGE_JS,
    mini_app_html,
    mini_app_js,
    mini_app_keys_page_js,
)

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]


def _keys_page_hash() -> str:
    return hashlib.sha256(KEYS_PAGE_JS.read_bytes()).hexdigest()[:12]


def test_keys_page_module_holds_keys_code_and_app_js_does_not():
    html = mini_app_html()
    app_js = mini_app_js()
    keys_js = mini_app_keys_page_js()
    assert KEYS_PAGE_JS.is_file()
    assert "function toggleKeyCard(" in keys_js
    assert "function switchKeysTab(" in keys_js
    assert "const PROFILE_KEYS_PAGE_SIZE = 5" in keys_js
    assert "const GIFTS_PAGE_SIZE = 5" in keys_js
    assert "function onKeysSearchInput(" in keys_js
    assert "async function performKeysSearch(" in keys_js
    assert "async function loadUserGifts(" in keys_js
    assert "async function activateOwnGift(" in keys_js
    assert "window._loadKeysPage = async function" in keys_js
    assert "(function checkGiftParam()" in keys_js
    assert "closest('[data-profile-keys-page]')" in keys_js
    assert "closest('[data-gifts-page]')" in keys_js
    assert "closest('[data-gift-action=\"activate\"]')" in keys_js
    assert "closest('.key-toggle')" in keys_js
    assert "getElementById('keys-search-input')?.addEventListener('input', onKeysSearchInput)" in keys_js
    assert "/api/keys/search" in keys_js
    assert "/api/user/gifts" in keys_js
    assert "/api/gift/activate" in keys_js
    assert "function toggleKeyCard(" not in app_js
    assert "function switchKeysTab(" not in app_js
    assert "const PROFILE_KEYS_PAGE_SIZE = 5" not in app_js
    assert "const GIFTS_PAGE_SIZE = 5" not in app_js
    assert "function onKeysSearchInput(" not in app_js
    assert "async function activateOwnGift(" not in app_js
    assert "window._loadKeysPage = async function" not in app_js
    assert "(function checkGiftParam()" not in app_js
    assert "closest('[data-profile-keys-page]')" not in app_js
    assert "closest('[data-gifts-page]')" not in app_js
    assert "closest('[data-gift-action=\"activate\"]')" not in app_js
    assert "closest('.key-toggle')" not in app_js
    assert "window._loadHomeStats = async function" in app_js
    assert "window._loadKeysPage && window._loadKeysPage()" in app_js
    assert 'src="{{ store_js_href }}" defer>' in html
    assert 'src="{{ transactions_js_href }}" defer>' in html
    assert 'src="{{ keys_page_js_href }}" defer>' in html
    assert 'src="{{ app_js_href }}" defer>' in html
    assert html.index('src="{{ store_js_href }}" defer>') < html.index(
        'src="{{ transactions_js_href }}" defer>'
    )
    assert html.index('src="{{ transactions_js_href }}" defer>') < html.index(
        'src="{{ keys_page_js_href }}" defer>'
    )
    assert html.index('src="{{ keys_page_js_href }}" defer>') < html.index(
        'src="{{ app_js_href }}" defer>'
    )
    assert 'type="module"' not in html
    assert "eval(" not in keys_js
    assert "new Function" not in keys_js
    assert "window.toggleKeyCard = toggleKeyCard" not in keys_js
    assert "window.activateOwnGift = activateOwnGift" not in keys_js
    assert "window.switchKeysTab = switchKeysTab" not in keys_js


def test_served_page_includes_hashed_keys_page_js(temp_db, app_client):
    from conftest import insert_user, issue_auth_token
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=16901, username="keys-split")
    token = issue_auth_token(16901)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    expected = f"/static/js/keys-page.js?v={_keys_page_hash()}"
    assert expected in resp.text
    assert resp.text.index("/static/js/store.js") < resp.text.index("/static/js/transactions.js")
    assert resp.text.index("/static/js/transactions.js") < resp.text.index("/static/js/keys-page.js")
    assert resp.text.index("/static/js/keys-page.js") < resp.text.index("/static/js/app.js")
    js_resp = app_client.get("/static/js/keys-page.js")
    assert js_resp.status_code == 200
    assert "function switchKeysTab(" in js_resp.text
    assert "async function activateOwnGift(" in js_resp.text
    cc = js_resp.headers.get("cache-control", "").lower()
    assert "must-revalidate" in cc or "max-age=0" in cc


def test_keys_page_tabs_pagination_search_and_gifts_in_node():
    assert NODE, "нужен node для vm-smoke keys-page.js"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/keys-page.js', 'utf8');

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
    children: extra && extra.children || [],
    parent: extra && extra.parent || null,
    nextElementSibling: extra && extra.nextElementSibling || null,
    scrollHeight: extra && extra.scrollHeight || 0,
    attributes: Object.assign({}, extra && extra.attributes),
    addEventListener(type, fn) {
      (this.listeners[type] || (this.listeners[type] = [])).push(fn);
    },
    dispatchEvent(evt) {
      (this.listeners[evt.type] || []).forEach((fn) => fn(evt));
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
        const cls = (n.className || '').split(/\s+/);
        if (sel === '[data-profile-keys-page]' && attrs['data-profile-keys-page']) return n;
        if (sel === '[data-gifts-page]' && attrs['data-gifts-page']) return n;
        if (sel === '[data-gift-action="activate"]' && attrs['data-gift-action'] === 'activate') return n;
        if (sel === '.key-toggle' && cls.includes('key-toggle')) return n;
        n = n.parent;
      }
      return null;
    },
    querySelector(sel) {
      if (sel === '.key-toggle' && this._toggle) return this._toggle;
      if (sel === '.rotate-icon') return this._icon || null;
      return null;
    },
    querySelectorAll() { return []; },
    click() {
      (this.listeners.click || []).forEach((fn) => fn({ type: 'click', target: this, stopPropagation() {} }));
    }
  };
  node.id = id || '';
  return node;
}

const fetches = [];
const notifications = [];
const personalBtn = el('keys-tab-btn-personal', { className: 'bg-white/10 text-white' });
const giftsBtn = el('keys-tab-btn-gifts', { className: 'text-gray-400' });
const personalPanel = el('keys-tab-personal');
const giftsPanel = el('keys-tab-gifts', { className: 'hidden' });
const tabsEl = el('keys-tabs');
const searchInput = el('keys-search-input', { value: '' });
const clearBtn = el('keys-search-clear', { className: 'hidden' });
const resultsWrap = el('keys-search-results-wrap', { className: 'hidden' });
const resultsEl = el('keys-search-results');
const paginationEl = el('profile-keys-pagination', { className: 'hidden' });
const giftsContent = el('gifts-content', { className: 'hidden' });
const giftsPagination = el('gifts-pagination', { className: 'hidden' });
const giftsLoading = el('gifts-loading', { style: { display: '' } });
const cards = [];
for (let i = 0; i < 7; i++) {
  const card = el('card-' + i);
  card._toggle = { className: 'key-toggle' };
  card.querySelector = (sel) => sel === '.key-toggle' ? card._toggle : null;
  cards.push(card);
}
const keysContainer = el('profile-keys-list-container', { children: cards });
const icon = { classList: classList('') };
const body = el('key-card-body', { scrollHeight: 180 });
const toggleBtn = el('toggle-1', { className: 'key-toggle' });
toggleBtn._icon = icon;
toggleBtn.nextElementSibling = body;

const byId = {
  'keys-tab-btn-personal': personalBtn,
  'keys-tab-btn-gifts': giftsBtn,
  'keys-tab-personal': personalPanel,
  'keys-tab-gifts': giftsPanel,
  'keys-tabs': tabsEl,
  'keys-search-input': searchInput,
  'keys-search-clear': clearBtn,
  'keys-search-results-wrap': resultsWrap,
  'keys-search-results': resultsEl,
  'profile-keys-list-container': keysContainer,
  'profile-keys-pagination': paginationEl,
  'gifts-content': giftsContent,
  'gifts-pagination': giftsPagination,
  'gifts-loading': giftsLoading,
};
const documentClicks = [];
const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  setTimeout(fn) { if (typeof fn === 'function') fn(); return 1; },
  clearTimeout() {},
  parseInt, Number, String, Boolean, Array, Object, JSON, Date, Math, Error,
  Promise, Map, Set, isNaN, isFinite, encodeURIComponent, URL,
  Telegram: { WebApp: { initDataUnsafe: { user: { id: 16901 } } } },
  RENDERED_USER_ID: 16901,
  fetch(url, opts) {
    fetches.push({ url: String(url), body: opts && opts.body });
    if (String(url).indexOf('/api/keys/search') >= 0) {
      return Promise.resolve({
        json: () => Promise.resolve({ ok: true, total: 1, html: '<div class="key-toggle">hit</div>' }),
        ok: true
      });
    }
    if (String(url).indexOf('/api/gift/activate') >= 0) {
      return Promise.resolve({
        json: () => Promise.resolve({ ok: true, message: 'Подарок активирован!' }),
        ok: true
      });
    }
    return Promise.resolve({ json: () => Promise.resolve({ ok: true }), ok: true });
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
  location: { href: 'https://mini.test/', hash: '', pathname: '/' },
  history: { replaceState() {} },
  showNotification(msg, type) { notifications.push([msg, type]); },
  escapeHtmlAttr(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  },
  getAuthToken() { return 't'; },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox._currentUserId = 16901;
sandbox.addEventListener = function () {};

let threw = null;
try { vm.runInNewContext(src, sandbox, { filename: 'keys-page.js' }); }
catch (e) { threw = e && e.stack ? e.stack : String(e); }

function fireDoc(target) {
  const evt = { type: 'click', target, stopPropagation() {}, preventDefault() {} };
  documentClicks.forEach((fn) => fn(evt));
}

async function waitUntil(pred) {
  for (let i = 0; i < 20; i++) {
    if (pred()) return;
    await Promise.resolve();
  }
}

Promise.resolve()
  .then(async () => {
    giftsBtn.click();
    const giftsTab = giftsBtn.classList.contains('bg-white/10') && !giftsPanel.classList.contains('hidden');
    personalBtn.click();
    const personalTab = !personalPanel.classList.contains('hidden') && personalBtn.classList.contains('bg-white/10');

    sandbox.initProfileKeysPagination();
    const page1Visible = cards.filter((c) => c.style.display !== 'none').length;
    const page1Html = paginationEl.innerHTML;
    const nextBtn = el('pk-next', { tagName: 'BUTTON', attributes: { 'data-profile-keys-page': '1' } });
    fireDoc(nextBtn);
    const page2Visible = cards.filter((c) => c.style.display !== 'none').length;
    const page2Html = paginationEl.innerHTML;

    sandbox.window._giftsState = {
      gifts: Array.from({ length: 7 }, (_, i) => ({ gift_code: 'g' + i, card_html: '<div>gift ' + i + '</div>' })),
      page: 0
    };
    sandbox.renderGiftsPage();
    const giftsPage1 = giftsContent.innerHTML;
    const giftsNext = el('g-next', { tagName: 'BUTTON', attributes: { 'data-gifts-page': '1' } });
    fireDoc(giftsNext);
    const giftsPage2 = giftsContent.innerHTML;

    searchInput.value = 'vpn';
    searchInput.dispatchEvent({ type: 'input' });
    await waitUntil(() => resultsEl.innerHTML.indexOf('hit') >= 0);

    fireDoc(toggleBtn);
    const expanded = body.classList.contains('expanded') && body.style.maxHeight === '180px';
    fireDoc(toggleBtn);
    const collapsed = !body.classList.contains('expanded') && body.style.maxHeight === '0px';

    const giftBtn = el('gift-act', {
      tagName: 'BUTTON',
      attributes: { 'data-gift-action': 'activate', 'data-gift-code': 'GIFTCODE11' }
    });
    fireDoc(giftBtn);
    await waitUntil(() => notifications.length > 0);

    const xssHtml = sandbox._giftCardHtml({
      gift_code: '"><img src=x onerror=alert(1)>',
      host_name: 'h',
      created_at: '2026-01-01'
    });

    return {
      threw,
      clickHandlers: documentClicks.length,
      searchBound: (searchInput.listeners.input || []).length,
      giftsTab,
      personalTab,
      page1Visible,
      page2Visible,
      page1HasNext: /data-profile-keys-page="1"/.test(page1Html),
      page1HasOnclick: /onclick=/.test(page1Html),
      page2Label: /2 \/ 2/.test(page2Html),
      giftsPage1Has0: /gift 0/.test(giftsPage1),
      giftsPage1Has5: /gift 5/.test(giftsPage1),
      giftsPage2Has5: /gift 5/.test(giftsPage2),
      giftsPage2HasOnclick: /onclick=/.test(giftsPagination.innerHTML),
      searchFetch: fetches.some((f) => f.url.indexOf('/api/keys/search') >= 0),
      searchHtml: resultsEl.innerHTML,
      expanded,
      collapsed,
      giftFetch: fetches.filter((f) => f.url.indexOf('/api/gift/activate') >= 0).map((f) => f.body),
      notifications: notifications.slice(),
      giftHasAttr: /data-gift-action="activate"/.test(xssHtml),
      giftHasOnclick: /onclick=/.test(xssHtml),
      giftRawInAttr: /data-gift-code=""><img/.test(xssHtml),
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
    assert result["searchBound"] >= 1
    assert result["giftsTab"] is True
    assert result["personalTab"] is True
    assert result["page1Visible"] == 5
    assert result["page2Visible"] == 2
    assert result["page1HasNext"] is True
    assert result["page1HasOnclick"] is False
    assert result["page2Label"] is True
    assert result["giftsPage1Has0"] is True
    assert result["giftsPage1Has5"] is False
    assert result["giftsPage2Has5"] is True
    assert result["giftsPage2HasOnclick"] is False
    assert result["searchFetch"] is True
    assert "hit" in result["searchHtml"]
    assert result["expanded"] is True
    assert result["collapsed"] is True
    bodies = [json.loads(b) if isinstance(b, str) else b for b in result["giftFetch"]]
    assert any(b.get("gift_code") == "GIFTCODE11" for b in bodies)
    assert any("активирован" in str(n[0]).lower() for n in result["notifications"])
    assert result["giftHasAttr"] is True
    assert result["giftHasOnclick"] is False
    assert result["giftRawInAttr"] is False
