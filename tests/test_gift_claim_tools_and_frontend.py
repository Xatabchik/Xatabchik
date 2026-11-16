"""Pending-токен подарка в Mini App и CLI аудита зависших активаций."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from conftest import insert_user, temp_db  # noqa: F401
from gift_claim_harness import gift_row, insert_full_gift, key_row

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]


def _run_pending_snippet(responses: list[dict]) -> dict:
    script = r"""
const fs = require('fs');
const vm = require('vm');
const appSrc = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
const start = "window.addEventListener('appReady', async () => {\n    const pendingToken";
const a = appSrc.indexOf(start);
const pendingSrc = appSrc.slice(a, appSrc.indexOf('// ── Профиль: смена пароля', a));
const responses = JSON.parse(process.argv[1]);
const store = { pending_action_token: 'pend-1' };
const listeners = {};
const sandbox = {
  console, JSON, Promise,
  sessionStorage: {
    getItem: (k) => (k in store ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
    removeItem: (k) => { delete store[k]; },
  },
  fetch: async () => {
    const r = responses.shift();
    if (r === 'network') throw new Error('offline');
    return { json: async () => r };
  },
  showNotification() {},
  refreshAfterGiftActivation: async () => true,
  addEventListener(name, fn) { (listeners[name] = listeners[name] || []).push(fn); },
};
sandbox.window = sandbox;
sandbox.window.getAuthToken = () => 't';
vm.runInNewContext(pendingSrc, sandbox, { filename: 'pending.js' });
const out = [];
(async () => {
  for (let i = 0; i < 3; i++) {
    sandbox.window._pendingActionToken = store.pending_action_token || null;
    await Promise.all((listeners.appReady || []).map((fn) => fn()));
    out.push(store.pending_action_token || null);
  }
  console.log(JSON.stringify(out));
})();
"""
    proc = subprocess.run(
        [NODE, "-e", script, json.dumps(responses)],
        capture_output=True, text=True, timeout=20, cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_pending_token_kept_until_final_server_answer():
    assert NODE, "нужен node"
    after = _run_pending_snippet([
        "network",
        {"ok": False, "action_type": "gift", "status": "error", "retryable": True, "message": "x"},
        {"ok": True, "action_type": "gift", "status": "activated", "retryable": False, "message": "ok"},
    ])
    assert after == ["pend-1", "pend-1", None]


def test_app_html_restores_pending_token_from_session_storage():
    html = (ROOT / "src/shop_bot/webapp/app.html").read_text(encoding="utf-8")
    assert "sessionStorage.setItem('pending_action_token'" in html
    assert "sessionStorage.getItem('pending_action_token')" in html


def test_audit_cli_reports_and_repairs_only_requested_recoverable_gift(temp_db):
    db = temp_db
    insert_user(db.DB_FILE, 9100, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=9100, gift_code="CLI-SECRET-1")
    with sqlite3.connect(db.DB_FILE) as conn:
        conn.execute(
            "UPDATE user_gifts SET is_activated = 1, activated_by_user_id = 9200 WHERE gift_id = ?", (gift_id,)
        )
        conn.commit()

    cmd = [sys.executable, str(ROOT / "tools/gift_activation_audit.py"), "--db", str(db.DB_FILE)]
    report = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert report.returncode == 0, report.stderr
    assert f"gift_id={gift_id} problem=not_transferred recoverable=True" in report.stdout
    assert "CLI-SECRET-1" not in report.stdout
    assert key_row(db.DB_FILE, key_id)["user_id"] == 9100, "без --repair ничего не меняется"

    repaired = subprocess.run(cmd + ["--repair", str(gift_id)], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert repaired.returncode == 0, repaired.stderr + repaired.stdout
    assert key_row(db.DB_FILE, key_id)["user_id"] == 9200
    assert gift_row(db.DB_FILE, gift_id)["is_activated"] == 1
