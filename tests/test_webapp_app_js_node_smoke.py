"""Smoke: static Mini App entrypoint parses and binds window bridges in Node."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]


def test_app_js_loads_with_dom_stub_and_exposes_legacy_bridges():
    assert NODE, "нужен node для smoke-загрузки app.js"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');

function el() {
  return {
    classList: { add() {}, remove() {}, toggle() {}, contains() { return true; } },
    style: {},
    addEventListener() {},
    removeEventListener() {},
    getAttribute() { return ''; },
    setAttribute() {},
    querySelector() { return null; },
    querySelectorAll() { return []; },
    appendChild() {},
    replaceChildren() {},
    textContent: '',
    innerHTML: '',
    className: '',
    id: '',
    disabled: false,
    value: '',
    href: '',
  };
}

const body = el();
const documentElement = Object.assign(el(), { style: { setProperty() {} } });
const document = {
  body,
  documentElement,
  readyState: 'complete',
  getElementById() { return el(); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  createElement() { return el(); },
  addEventListener() {},
  removeEventListener() {},
  elementFromPoint() { return null; },
};
const localStorage = {
  theme: 'dark',
  getItem() { return null; },
  setItem() {},
  removeItem() {},
};
const errors = [];
const sandbox = {
  console,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  URL,
  Event,
  requestAnimationFrame: (fn) => fn(),
  fetch: async () => ({ ok: true, json: async () => ({ ok: true }), text: async () => '' }),
  document,
  localStorage,
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
  navigator: { clipboard: { write() { return Promise.resolve(); } } },
};
sandbox.apiFetch = sandbox.fetch;
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.process = { on() {} };

let threw = null;
try {
  vm.runInNewContext(src, sandbox, { filename: 'app.js' });
} catch (e) {
  threw = e && e.stack ? e.stack : String(e);
}
const bridges = [
  'openTopUpModal', 'copyKey', 'navigateTo',
  'closePaymentModal', 'openActionModal', 'processPayment', 'goToRenewKey',
];
const present = {};
for (const name of bridges) {
  present[name] = typeof sandbox[name];
}
console.log(JSON.stringify({
  threw,
  present,
  hasInitApp: typeof sandbox.initApp,
  rendered: sandbox._currentUserId,
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
    assert result["threw"] is None, result["threw"]
    assert result["hasInitApp"] == "function"
    assert result["rendered"] == 1
    for name, kind in result["present"].items():
        assert kind == "function", name
