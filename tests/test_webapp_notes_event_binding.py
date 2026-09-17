"""Этап 2 PR 3: заметки ключа и accordion без inline onclick / window bridges."""
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
    "toggleKeyCard",
    "saveComment",
    "saveNote",
    "deleteNote",
)


def test_note_cards_have_no_inline_note_handlers():
    html = mini_app_html()
    js = mini_app_js()
    keys = KEYS.read_text(encoding="utf-8")
    assert 'onclick="saveComment' not in html
    assert 'onclick="saveNote' not in html
    assert 'onclick="deleteNote' not in html
    assert 'onclick="toggleKeyCard' not in html
    assert 'onclick="saveComment' not in keys
    assert 'onclick="toggleKeyCard' not in keys
    assert 'onclick="saveComment' not in js
    assert 'data-key-action="comment"' in keys
    assert "class=\"key-toggle" in keys
    assert "closest('.key-toggle')" in js
    assert "closest('#comment-save-btn')" in js
    assert "closest('#comment-delete-btn')" in js
    assert "saveComment(noteKeyId, Boolean(noteDelete))" in js
    assert 'id="comment-save-btn" data-key-id="${keyId}"' in js
    assert 'id="comment-delete-btn" data-key-id="${keyId}"' in js
    assert "addEventListener('click', () => saveComment" not in js
    assert "querySelectorAll('.key-toggle').forEach" not in js


def test_removed_note_handler_bridges_are_gone():
    js = mini_app_js()
    for name in REMOVED_BRIDGES:
        assert f"window.{name} = {name};" not in js, name
    assert "window.openActionModal = openActionModal;" in js
    assert "window.resetSupportChat = resetSupportChat;" in js
    assert "window.openTopUpModal = openTopUpModal;" in js


def test_served_keys_page_notes_use_data_action_not_onclick(temp_db, app_client):
    import sqlite3

    from shop_bot.data_manager import database
    from conftest import insert_user, issue_auth_token

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=15301, username="notes-bind")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, comment_key, user_key_name
            ) VALUES (15301, 'NoteHost', 'note@bot.local', 'note@bot.local',
                      'https://sub.example/note', datetime('now', '+30 days'),
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'старая', 'PR3 Note Key')
            """
        )
        conn.commit()
    token = issue_auth_token(15301)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert "PR3 Note Key" in html
    assert 'data-key-action="comment"' in html
    assert 'onclick="saveComment' not in html
    assert 'onclick="toggleKeyCard' not in html
    js = app_client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "closest('#comment-save-btn')" in js.text
    assert "window.toggleKeyCard = toggleKeyCard;" not in js.text


def test_note_save_delete_and_key_toggle_event_binding_in_node():
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
    scrollHeight: 120,
    addEventListener(type, fn) {
      (this.listeners[type] || (this.listeners[type] = [])).push(fn);
    },
    dispatchEvent(evt) {
      (this.listeners[evt.type] || []).forEach((fn) => fn(evt));
    },
    getAttribute(name) { return this.attributes[name] || ''; },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    querySelector(sel) {
      if (sel === '.rotate-icon') return this._icon || null;
      return null;
    },
    querySelectorAll() { return []; },
    closest(sel) {
      if (sel === '.key-toggle' && (this.className || '').split(/\s+/).includes('key-toggle')) return this;
      if (sel === '#comment-save-btn' && this.id === 'comment-save-btn') return this;
      if (sel === '#comment-delete-btn' && this.id === 'comment-delete-btn') return this;
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

const commentText = el('comment-text-60', {});
commentText.textContent = 'старая';
const commentBlock = el('comment-block-60', { className: 'flex' });
const commentInput = el('action-comment-input', { value: '' });
const saveBtn = el('comment-save-btn', { attributes: { 'data-key-id': '60' } });
const deleteBtn = el('comment-delete-btn', { attributes: { 'data-key-id': '60' } });
const icon = { classList: classList('') };
const body = el('key-card-body', { className: '' });
body.scrollHeight = 180;
const toggleBtn = el('toggle-60', { className: 'key-toggle' });
toggleBtn._icon = icon;
toggleBtn.nextElementSibling = body;
const commentAction = el('comment-action', {
  attributes: { 'data-key-action': 'comment', 'data-key-id': '60' }
});

const contentEl = el('action-modal-content');
Object.defineProperty(contentEl, 'innerHTML', {
  get() { return this._html || ''; },
  set(v) {
    this._html = String(v);
    if (String(v).includes('comment-save-btn')) {
      const kid = (/data-key-id="(\d+)"/.exec(v) || [])[1] || '60';
      saveBtn.attributes['data-key-id'] = kid;
      deleteBtn.attributes['data-key-id'] = kid;
      byId['comment-save-btn'] = saveBtn;
      byId['comment-delete-btn'] = deleteBtn;
      byId['action-comment-input'] = commentInput;
    }
  }
});

const toast = el('toast-container');
toast.appendChild = function (child) { notifications.push(child && child.textContent); };

const byId = {
  'comment-text-60': commentText,
  'comment-block-60': commentBlock,
  'action-comment-input': commentInput,
  'comment-save-btn': saveBtn,
  'comment-delete-btn': deleteBtn,
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
const commentPosts = [];
const document = {
  body: el('body'),
  documentElement: Object.assign(el('html'), { style: { setProperty() {} } }),
  readyState: 'complete',
  getElementById(id) { return byId[id] || el(id); },
  querySelector() { return null; },
  querySelectorAll(sel) {
    const m = /^\[id="([^"]+)"\]$/.exec(sel || '');
    if (m && byId[m[1]]) return [byId[m[1]]];
    return [];
  },
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
  fetch: async (url, opts) => {
    const body = opts && opts.body ? JSON.parse(opts.body) : {};
    if (String(url).includes('/api/key/comment')) {
      commentPosts.push(body);
      return { ok: true, json: async () => ({ ok: true }), text: async () => '' };
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

fire(toggleBtn);
const expandedAfterToggle = body.classList.contains('expanded') && body.style.maxHeight === '180px';
fire(toggleBtn);
const collapsedAfterToggle = !body.classList.contains('expanded') && body.style.maxHeight === '0px';

fire(commentAction);
const modalHtml = contentEl.innerHTML || '';
const openedCommentModal = modalHtml.includes('comment-save-btn') && modalHtml.includes('data-key-id="60"');
const prefillsStored = commentInput.value === 'старая';

commentInput.value = 'новая заметка';
fire(saveBtn);

async function waitUntil(pred) {
  for (let i = 0; i < 20; i++) {
    if (pred()) return;
    await Promise.resolve();
  }
}

waitUntil(() => commentPosts.some((p) => p.comment === 'новая заметка') && commentText.textContent === 'новая заметка').then(() => {
  const afterSave = {
    text: commentText.textContent,
    blockHidden: commentBlock.classList.contains('hidden'),
    saved: commentPosts.some((p) => p.comment === 'новая заметка' && p.key_id === 60),
  };
  fire(deleteBtn);
  return waitUntil(() => commentPosts.some((p) => p.comment === '') && commentBlock.classList.contains('hidden')).then(() => {
    console.log(JSON.stringify({
      threw,
      docClick: (docListeners.click || []).length,
      expandedAfterToggle,
      collapsedAfterToggle,
      openedCommentModal,
      prefillsStored,
      afterSave,
      afterDelete: {
        text: commentText.textContent,
        blockHidden: commentBlock.classList.contains('hidden'),
        deleted: commentPosts.some((p) => p.comment === '' && p.key_id === 60),
      },
      notifications,
      toggleBridge: /window\.toggleKeyCard = toggleKeyCard;/.test(src),
      saveBridge: /window\.saveComment = saveComment;/.test(src),
    }));
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
    assert result["expandedAfterToggle"] is True
    assert result["collapsedAfterToggle"] is True
    assert result["openedCommentModal"] is True
    assert result["prefillsStored"] is True
    assert result["afterSave"]["saved"] is True
    assert result["afterSave"]["text"] == "новая заметка"
    assert result["afterSave"]["blockHidden"] is False
    assert result["afterDelete"]["deleted"] is True
    assert result["afterDelete"]["text"] == ""
    assert result["afterDelete"]["blockHidden"] is True
    notes = " ".join(result["notifications"]).lower()
    assert "сохранен" in notes or "заметк" in notes
    assert "удален" in notes
    assert result["toggleBridge"] is False
    assert result["saveBridge"] is False
