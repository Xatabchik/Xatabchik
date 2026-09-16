"""Telegram WebApp 6.0 не умеет showPopup: успех API не должен оставлять кнопку в loading.

Проверки структурные (как test_webapp_payment_poll / topup_modal) плюс короткий
прогон извлечённых функций в Node: fallback-toast и reset в finally.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from webapp_frontend_src import mini_app_frontend_source, mini_app_html

HTML = mini_app_frontend_source()
APP_HTML = mini_app_html()
LOGIN = Path("src/shop_bot/webapp/login.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _body(start: str, end: str) -> str:
    assert start in HTML, f"не найдено объявление {start!r}"
    start_idx = HTML.index(start)
    end_idx = HTML.index(end, start_idx)
    return HTML[start_idx:end_idx]


def test_mobile_web_app_capable_meta_exists_without_html_refactor():
    for text in (APP_HTML, LOGIN):
        assert 'name="apple-mobile-web-app-capable"' in text
        assert 'name="mobile-web-app-capable"' in text
        assert 'content="yes"' in text


def test_key_comment_and_rename_handlers_do_not_call_telegram_popup_directly():
    comment = _body("async function saveComment(", "async function applyDiscountPromo(")
    rename = _body("async function renameKey(", "async function deleteAllDevices(")
    for body in (comment, rename):
        assert "showPopup" not in body
        assert "showAlert" not in body
        assert "showNotification(" in body
        assert "finally" in body
        assert "btn.disabled = false" in body
        assert "btn.innerHTML = originalContent" in body


def test_show_notification_goes_through_safe_telegram_popup():
    helper = _body("function telegramPopupSupported(", "let activeTierData")
    assert "function safeTelegramPopup(" in helper
    assert "function showLocalToast(" in helper
    assert "isVersionAtLeast('6.2')" in helper
    assert "showLocalToast" in helper
    notify = _body("function showNotification(", "let activeTierData")
    assert "safeTelegramPopup(" in notify
    assert "WebApp.showAlert(message)" not in notify
    assert "showAlert(message)" not in notify


def test_no_direct_show_alert_left_in_app_html():
    assert "WebApp.showAlert(" not in HTML
    assert "WebApp.showPopup(" not in HTML
    assert "safeTelegramPopup(" in HTML
    assert "tg.showPopup(" in HTML
    assert "telegramPopupSupported()" in HTML


def test_copy_key_uses_show_notification_not_telegram_alert():
    copy_key = _body("function copyKey(", "function changePaymentStep(")
    assert "showNotification(" in copy_key
    assert "showAlert" not in copy_key
    assert "showPopup" not in copy_key


def _run_node(script: str) -> dict:
    assert NODE, "нужен node для поведенческой проверки fallback"
    proc = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    line = proc.stdout.strip().splitlines()[-1]
    return json.loads(line)


def test_unsupported_telegram_api_uses_local_toast_and_does_not_throw():
    result = _run_node(r"""
const fs = require('fs');
const html = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
function sliceFn(start, end) {
  const a = html.indexOf(start);
  const b = html.indexOf(end, a);
  if (a < 0 || b < 0) throw new Error('slice ' + start);
  return html.slice(a, b);
}
const helperSrc = sliceFn('function telegramPopupSupported(', 'let activeTierData');
const toasts = [];
const calls = { showPopup: 0, showAlert: 0 };
const document = {
  getElementById(id) {
    if (id !== 'toast-container') return null;
    return { appendChild(el) { toasts.push(el.textContent); } };
  },
  createElement() {
    return { className: '', textContent: '', classList: { add() {}, remove() {} }, remove() {} };
  }
};
const window = {
  Telegram: {
    WebApp: {
      version: '6.0',
      isVersionAtLeast(v) { return false; },
      showPopup() { calls.showPopup += 1; throw new Error('WebAppMethodUnsupported'); },
      showAlert() { calls.showAlert += 1; throw new Error('WebAppMethodUnsupported'); },
    }
  }
};
global.window = window;
global.document = document;
global.requestAnimationFrame = (fn) => fn();
eval(helperSrc);
showNotification('Комментарий сохранен!', 'info');
showNotification('Название обновлено!', 'success');
console.log(JSON.stringify({ toasts, calls, supported: telegramPopupSupported() }));
""")
    assert result["supported"] is False
    assert result["calls"]["showPopup"] == 0
    assert result["calls"]["showAlert"] == 0
    assert "Комментарий сохранен!" in result["toasts"]
    assert "Название обновлено!" in result["toasts"]


def test_supported_telegram_popup_is_used_and_rejected_promise_falls_back():
    result = _run_node(r"""
const fs = require('fs');
const html = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
function sliceFn(start, end) {
  const a = html.indexOf(start);
  const b = html.indexOf(end, a);
  return html.slice(a, b);
}
const helperSrc = sliceFn('function telegramPopupSupported(', 'let activeTierData');
const toasts = [];
const calls = { showPopup: 0 };
const document = {
  getElementById(id) {
    if (id !== 'toast-container') return null;
    return { appendChild(el) { toasts.push(el.textContent); } };
  },
  createElement() {
    return { className: '', textContent: '', classList: { add() {}, remove() {} }, remove() {} };
  }
};
const windowOk = {
  Telegram: {
    WebApp: {
      version: '7.0',
      isVersionAtLeast(v) { return true; },
      showPopup(params) { calls.showPopup += 1; return { then() {} }; }
    }
  }
};
global.document = document;
global.requestAnimationFrame = (fn) => fn();
global.window = windowOk;
eval(helperSrc);
showNotification('ok-popup', 'info');
const windowReject = {
  Telegram: {
    WebApp: {
      version: '7.0',
      isVersionAtLeast() { return true; },
      showPopup() {
        calls.showPopup += 1;
        return Promise.reject(new Error('WebAppMethodUnsupported'));
      }
    }
  }
};
global.window = windowReject;
showNotification('fallback-after-reject', 'error');
setTimeout(() => {
  console.log(JSON.stringify({ toasts, calls }));
}, 20);
""")
    assert result["calls"]["showPopup"] >= 2
    assert "ok-popup" not in result["toasts"]
    assert "fallback-after-reject" in result["toasts"]


def test_save_comment_and_rename_reset_loading_in_finally_when_popup_throws():
    result = _run_node(r"""
const fs = require('fs');
const html = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
function sliceFn(start, end) {
  const a = html.indexOf(start);
  const b = html.indexOf(end, a);
  return html.slice(a, b);
}
const helperSrc = sliceFn('function telegramPopupSupported(', 'let activeTierData');
const saveSrc = sliceFn('async function saveComment(', 'async function applyDiscountPromo(');
const renameSrc = sliceFn('async function renameKey(', 'async function deleteAllDevices(');

function makeBtn(html) {
  return { innerHTML: html, disabled: false };
}
const saveBtn = makeBtn('save-note');
const delBtn = makeBtn('del-note');
const renameBtn = makeBtn('save-name');
const toasts = [];
const document = {
  buttons: {
    'comment-save-btn': saveBtn,
    'comment-delete-btn': delBtn,
    'action-rename-btn': renameBtn,
    'action-comment-input': { value: 'hello' },
    'action-rename-input': { value: 'Work VPN' },
    'toast-container': { appendChild(el) { toasts.push(el.textContent); } },
  },
  getElementById(id) { return this.buttons[id] || null; },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement() {
    return { className: '', textContent: '', classList: { add() {}, remove() {} }, remove() {} };
  }
};
const windowObj = {
  Telegram: {
    WebApp: {
      version: '6.0',
      isVersionAtLeast() { return false; },
      showAlert() { throw new Error('WebAppMethodUnsupported'); },
      showPopup() { throw new Error('WebAppMethodUnsupported'); },
    }
  },
  getAuthToken() { return 't'; },
  location: { reload() {} }
};
global.window = windowObj;
global.document = document;
global.requestAnimationFrame = (fn) => fn();
global.RENDERED_USER_ID = 1;
global.fetch = async () => ({ json: async () => ({ ok: true }) });
global.closeActionModal = () => {};
eval(helperSrc);
eval(saveSrc);
eval(renameSrc);
(async () => {
  saveBtn.innerHTML = 'save-note';
  await saveComment(42, false);
  const afterSave = { disabled: saveBtn.disabled, html: saveBtn.innerHTML };
  delBtn.innerHTML = 'del-note';
  await saveComment(42, true);
  const afterDel = { disabled: delBtn.disabled, html: delBtn.innerHTML };
  renameBtn.innerHTML = 'save-name';
  await renameKey(42, false);
  const afterRename = { disabled: renameBtn.disabled, html: renameBtn.innerHTML };
  console.log(JSON.stringify({ afterSave, afterDel, afterRename, toasts }));
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
""")
    assert result["afterSave"] == {"disabled": False, "html": "save-note"}
    assert result["afterDel"] == {"disabled": False, "html": "del-note"}
    assert result["afterRename"] == {"disabled": False, "html": "save-name"}
    assert any("сохранен" in t.lower() or "заметк" in t.lower() for t in result["toasts"])
    assert any("Название обновлено" in t for t in result["toasts"])
