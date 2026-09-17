"""Store, Фаза 4: fallback saveComment обновляет keyComments без reload."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import shutil
import subprocess
from pathlib import Path

from conftest import insert_user, issue_auth_token
from webapp_frontend_src import STORE_JS, mini_app_js, mini_app_store_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]
USER_ID = 16701
XSS_PAYLOAD = "<img src=x onerror=alert(1)>"


def _store_hash() -> str:
    return hashlib.sha256(STORE_JS.read_bytes()).hexdigest()[:12]


def _save_comment_body() -> str:
    js = mini_app_js()
    start = "async function saveComment("
    end = "async function applyDiscountPromo("
    assert start in js
    start_idx = js.index(start)
    end_idx = js.index(end, start_idx)
    return js[start_idx:end_idx]


def _insert_key(db_path: Path, *, user_id: int, email: str, comment_key: str = "") -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, user_key_name, comment_key
            ) VALUES (?, 'CommentHost', ?, ?, 'https://sub.example/comment',
                      datetime('now', '+30 days'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)
            """,
            (user_id, email, email, "Ключ для заметки", comment_key),
        )
        key_id = cur.lastrowid
        conn.commit()
    return int(key_id)


def test_save_comment_uses_store_instead_of_reload():
    store = mini_app_store_js()
    js = mini_app_js()
    save = _save_comment_body()
    assert "keyComments: {}" in store
    assert "function applyKeyCommentsToDom(" in store
    assert "function setKeyComment(" in store
    assert "store.subscribe(applyKeyCommentsToDom)" in store
    assert "texts[i].textContent = text" in store
    assert "innerHTML =" not in store.split("function applyKeyCommentsToDom(")[1].split("function setKeyComment(")[0]
    assert "window.setKeyComment =" not in store
    assert "window.setKeyComment =" not in js
    assert "location.reload()" not in save
    assert "setTimeout(() => window.location.reload(), 500)" not in js
    assert "setKeyComment(keyId, comment)" in save
    assert js.count("location.reload()") == 1
    assert "getElementById('settings-refresh-btn')?.addEventListener('click', () => location.reload())" in js


def test_set_key_comment_patches_dom_without_reload():
    assert NODE, "нужен node для vm-smoke Store comment"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';

function classList(initial) {
  const set = new Set(String(initial || '').split(/\s+/).filter(Boolean));
  return {
    add(name) { set.add(name); },
    remove(name) { set.delete(name); },
    contains(name) { return set.has(name); },
    toString() { return [...set].join(' '); }
  };
}

const textEl = { textContent: 'старая', innerHTML: 'старая' };
const blockEl = { classList: classList('flex') };
let liveText = textEl;
let liveBlock = blockEl;
let reloadCount = 0;
let notify = [];

const sandbox = {
  console, Set, Object, Number, Array, String,
  document: {
    getElementById() { return null; },
    querySelector() { return null; },
    querySelectorAll(sel) {
      if (sel === '[id="comment-text-42"]') return liveText ? [liveText] : [];
      if (sel === '[id="comment-block-42"]') return liveBlock ? [liveBlock] : [];
      if (sel === '[data-balance-display]') return [];
      return [];
    },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.runInNewContext(src, sandbox, { filename: 'store.js' });
sandbox.setKeyComment(42, 'новая заметка');
const afterFirst = {
  reloadCount,
  storeText: sandbox.__store.state.keyComments['42'].text,
  hasComment: sandbox.__store.state.keyComments['42'].hasComment,
  text: textEl.textContent,
  innerHTMLUntouched: textEl.innerHTML,
  hidden: blockEl.classList.contains('hidden'),
  flex: blockEl.classList.contains('flex'),
  notify,
};
const rebuiltText = { textContent: 'SSR stale', innerHTML: 'SSR stale' };
const rebuiltBlock = { classList: classList('hidden') };
liveText = rebuiltText;
liveBlock = rebuiltBlock;
sandbox.__store.setState({ keyComments: Object.assign({}, sandbox.__store.state.keyComments) });
liveText = null;
liveBlock = null;
sandbox.setKeyComment(42, 'скрытая');
console.log(JSON.stringify({
  afterFirst,
  afterRebuild: {
    reloadCount,
    text: rebuiltText.textContent,
    hidden: rebuiltBlock.classList.contains('hidden'),
    flex: rebuiltBlock.classList.contains('flex'),
    innerHTMLUntouched: rebuiltText.innerHTML,
  },
  afterMissing: {
    reloadCount,
    storeText: sandbox.__store.state.keyComments['42'].text,
    hasComment: sandbox.__store.state.keyComments['42'].hasComment,
    notify,
    oldTextStill: textEl.textContent,
  },
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
    first = result["afterFirst"]
    assert first["reloadCount"] == 0
    assert first["storeText"] == "новая заметка"
    assert first["hasComment"] is True
    assert first["text"] == "новая заметка"
    assert first["innerHTMLUntouched"] == "старая"
    assert first["hidden"] is False
    assert first["flex"] is True
    assert first["notify"] == []
    rebuilt = result["afterRebuild"]
    assert rebuilt["reloadCount"] == 0
    assert rebuilt["text"] == "новая заметка"
    assert rebuilt["hidden"] is False
    assert rebuilt["flex"] is True
    assert rebuilt["innerHTMLUntouched"] == "SSR stale"
    missing = result["afterMissing"]
    assert missing["reloadCount"] == 0
    assert missing["storeText"] == "скрытая"
    assert missing["hasComment"] is True
    assert missing["notify"] == []
    assert missing["oldTextStill"] == "новая заметка"


def test_save_comment_network_error_keeps_store_and_dom_without_reload():
    assert NODE, "нужен node для vm-smoke ошибки сети comment"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const storeSrc = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8');
const appSrc = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
const start = appSrc.indexOf('async function saveComment(');
const end = appSrc.indexOf('async function applyDiscountPromo(', start);
const src = storeSrc + '\n' + appSrc.slice(start, end) + '\nglobalThis.__store = store;\n';

function classList(initial) {
  const set = new Set(String(initial || '').split(/\s+/).filter(Boolean));
  return {
    add(name) { set.add(name); },
    remove(name) { set.delete(name); },
    contains(name) { return set.has(name); },
  };
}

const textEl = { textContent: 'старая', innerHTML: 'старая' };
const blockEl = { classList: classList('flex') };
const input = { value: 'не должно сохраниться' };
const btn = { innerHTML: 'save', disabled: false };
let reloadCount = 0;
let notify = [];
let closed = 0;

const sandbox = {
  console, Set, Object, Number, Array, String, Promise, JSON,
  fetch: async () => { throw new Error('network down'); },
  document: {
    getElementById(id) {
      if (id === 'action-comment-input') return input;
      if (id === 'comment-save-btn') return btn;
      return null;
    },
    querySelectorAll(sel) {
      if (sel === '[id="comment-text-7"]') return [textEl];
      if (sel === '[id="comment-block-7"]') return [blockEl];
      return [];
    },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
  closeActionModal() { closed += 1; },
  RENDERED_USER_ID: 1,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.getAuthToken = () => 't';

vm.runInNewContext(src, sandbox, { filename: 'comment.js' });
sandbox.saveComment(7, false).then(() => {
  console.log(JSON.stringify({
    reloadCount,
    closed,
    notify,
    storeComments: sandbox.__store.state.keyComments,
    text: textEl.textContent,
    hidden: blockEl.classList.contains('hidden'),
    btnDisabled: btn.disabled,
    btnHtml: btn.innerHTML,
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
    assert result["reloadCount"] == 0
    assert result["closed"] == 0
    assert result["notify"] == [["Ошибка сети", "error"]]
    assert result["storeComments"] == {}
    assert result["text"] == "старая"
    assert result["hidden"] is False
    assert result["btnDisabled"] is False
    assert result["btnHtml"] == "save"


def test_save_comment_missing_nodes_updates_store_without_reload_or_error_toast():
    assert NODE, "нужен node для vm-smoke comment без DOM"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const storeSrc = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8');
const appSrc = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
const start = appSrc.indexOf('async function saveComment(');
const end = appSrc.indexOf('async function applyDiscountPromo(', start);
const src = storeSrc + '\n' + appSrc.slice(start, end) + '\nglobalThis.__store = store;\n';

const input = { value: 'заметка без карточки' };
const btn = { innerHTML: 'save', disabled: false };
let reloadCount = 0;
let notify = [];
let closed = 0;

const sandbox = {
  console, Set, Object, Number, Array, String, Promise, JSON,
  fetch: async () => ({ ok: true, json: async () => ({ ok: true }) }),
  document: {
    getElementById(id) {
      if (id === 'action-comment-input') return input;
      if (id === 'comment-save-btn') return btn;
      return null;
    },
    querySelectorAll() { return []; },
  },
  location: { reload() { reloadCount += 1; } },
  showNotification(msg, type) { notify.push([msg, type]); },
  closeActionModal() { closed += 1; },
  RENDERED_USER_ID: 1,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.window.getAuthToken = () => 't';

vm.runInNewContext(src, sandbox, { filename: 'comment.js' });
sandbox.saveComment(9, false).then(() => {
  console.log(JSON.stringify({
    reloadCount,
    closed,
    notify,
    store: sandbox.__store.state.keyComments['9'],
    btnDisabled: btn.disabled,
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
    assert result["reloadCount"] == 0
    assert result["closed"] == 1
    assert result["notify"] == [["Комментарий сохранен!", "info"]]
    assert result["store"] == {"text": "заметка без карточки", "hasComment": True}
    assert result["btnDisabled"] is False


def test_set_key_comment_xss_payload_uses_textcontent_not_innerhtml():
    assert NODE, "нужен node для vm-smoke XSS comment"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/store.js', 'utf8')
  + '\nglobalThis.__store = store;\n';
const payload = '<img src=x onerror=alert(1)>';
const textEl = { textContent: 'safe', innerHTML: 'safe' };
const blockEl = {
  classList: {
    add() {},
    remove() {},
    contains() { return false; },
  }
};
const sandbox = {
  console, Set, Object, Number, Array, String,
  document: {
    getElementById() { return null; },
    querySelector() { return null; },
    querySelectorAll(sel) {
      if (sel === '[id="comment-text-3"]') return [textEl];
      if (sel === '[id="comment-block-3"]') return [blockEl];
      return [];
    },
  },
  location: { reload() {} },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.runInNewContext(src, sandbox, { filename: 'store.js' });
sandbox.setKeyComment(3, payload);
console.log(JSON.stringify({
  text: textEl.textContent,
  innerHTML: textEl.innerHTML,
  storeText: sandbox.__store.state.keyComments['3'].text,
}));
""".replace("PAYLOAD_PLACEHOLDER", XSS_PAYLOAD)
    proc = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    assert result["text"] == XSS_PAYLOAD
    assert result["innerHTML"] == "safe"
    assert result["storeText"] == XSS_PAYLOAD
    apply_src = mini_app_store_js().split("function _applyOneKeyCommentToDom(")[1].split("store.subscribe(applyKeyCommentsToDom)")[0]
    assert "innerHTML" not in apply_src
    assert "textContent = text" in apply_src


def test_served_page_and_comment_api_roundtrip(temp_db, app_client):
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="store-comment")
    key_id = _insert_key(
        database.DB_FILE, user_id=USER_ID, email="comment@bot.local", comment_key="старая"
    )
    token = issue_auth_token(USER_ID)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    expected = f"/static/js/store.js?v={_store_hash()}"
    assert expected in resp.text
    assert f'id="comment-block-{key_id}"' in resp.text
    assert f'id="comment-text-{key_id}"' in resp.text
    assert "старая" in resp.text
    store_resp = app_client.get("/static/js/store.js")
    assert store_resp.status_code == 200
    assert "function setKeyComment(" in store_resp.text
    assert "function applyKeyCommentsToDom(" in store_resp.text

    saved = app_client.post(
        "/api/key/comment",
        json={"user_id": USER_ID, "key_id": key_id, "comment": XSS_PAYLOAD, "token": token},
    )
    assert saved.status_code == 200
    assert saved.json().get("ok") is True
    stored = database.get_key_by_id(key_id)["comment_key"]
    assert stored == XSS_PAYLOAD
    hard = app_client.get("/", params={"token": token})
    chunk = hard.text.split('id="profile-keys-list-container"', 1)[1].split(
        'id="profile-keys-pagination"', 1
    )[0]
    assert XSS_PAYLOAD not in chunk
    assert "&lt;img src=x onerror=alert(1)&gt;" in chunk
    assert f'id="comment-text-{key_id}"' in chunk
