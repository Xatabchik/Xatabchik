"""Экран успеха оплаты в Mini App: что куплено, ссылки подарка и QR.

Раньше окно «Всё готово!» брало первый ключ из /api/user-status, а он не
содержит неактивированных подарков — пользователь видел чужой ключ и ни одной
ссылки подарка. Теперь результат берётся по payment_id владельца:
/api/payment/result и /api/payment/qr.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401
from webapp_frontend_src import mini_app_html, mini_app_js

NODE = shutil.which("node")
ROOT = Path(__file__).resolve().parents[1]

OWNER_ID = 74001
STRANGER_ID = 74002
RECEIVER_ID = 74003
HOST = "ResultHost"
PNG_PREFIX = "data:image/png;base64,"


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _post(path: str, payload: dict) -> dict:
    return _client().post(path, json=payload).json()


def _fake_bot(monkeypatch, *, marker: str):
    class _FakeMessage:
        async def edit_text(self, text, **kwargs):
            return None

        async def delete(self):
            return None

    class _FakeBot:
        id = 777

        def __init__(self):
            self.session = self

        async def send_message(self, *args, **kwargs):
            return _FakeMessage()

        async def close(self):
            return None

    sub_url = f"https://vpn.example/sub/{marker}"

    async def fake_create(*args, **kwargs):
        return {
            "client_uuid": f"uuid-{marker}",
            "short_uuid": f"short-{marker}",
            "email": f"{marker}@bot.local",
            "host_name": HOST,
            "squad_uuid": "squad-1",
            "subscription_url": sub_url,
            "connection_string": sub_url,
            "traffic_limit_bytes": None,
            "traffic_limit_strategy": None,
            "expiry_timestamp_ms": 1893456000000,
        }

    monkeypatch.setattr(
        "shop_bot.modules.remnawave_api.create_or_update_key_on_host", fake_create
    )
    return _FakeBot(), sub_url


def _seed(database):
    insert_user(database.DB_FILE, telegram_id=OWNER_ID, username="owner")
    insert_user(database.DB_FILE, telegram_id=STRANGER_ID, username="stranger")
    insert_user(database.DB_FILE, telegram_id=RECEIVER_ID, username="receiver")
    database.update_setting("telegram_bot_token", "123456:FAKE_BOT_TOKEN_FOR_TESTS")
    database.update_setting("telegram_bot_username", "TestVpnBot")
    database.update_setting("webapp_domain", "app.example.com")
    database.create_plan(HOST, "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host(HOST)[0]["plan_id"]
    return (
        issue_auth_token(OWNER_ID),
        issue_auth_token(STRANGER_ID),
        plan_id,
    )


def _buy(database, monkeypatch, *, action: str, plan_id: int, pid: str, marker: str):
    from shop_bot.bot.user_router.fulfillment import process_successful_payment

    meta = {
        "user_id": OWNER_ID,
        "months": 1,
        "duration_days": 0,
        "price": 100.0,
        "action": action,
        "key_id": None,
        "host_name": HOST,
        "plan_id": plan_id,
        "payment_method": "YooKassa",
        "payment_id": pid,
    }
    database.create_payload_pending(pid, OWNER_ID, 100.0, meta)
    assert database.find_and_complete_pending_transaction(pid) is not None
    bot, sub_url = _fake_bot(monkeypatch, marker=marker)
    assert asyncio.run(process_successful_payment(bot, meta)) is True
    return sub_url


def test_gift_result_returns_gift_key_and_links_not_another_key(temp_db, monkeypatch):
    database = temp_db
    owner_token, _, plan_id = _seed(database)
    own_sub = _buy(
        database, monkeypatch, action="new", plan_id=plan_id,
        pid="bbbb0000-0000-0000-0000-000000000001", marker="own",
    )
    gift_sub = _buy(
        database, monkeypatch, action="gift", plan_id=plan_id,
        pid="bbbb0000-0000-0000-0000-000000000002", marker="giftkey",
    )

    data = _post(
        "/api/payment/result",
        {"payment_id": "bbbb0000-0000-0000-0000-000000000002", "token": owner_token},
    )
    assert data["ok"] is True and data["ready"] is True, data
    assert data["action"] == "gift"
    assert data["key"]["sub_url"] == gift_sub != own_sub

    gift = data["gift"]
    assert gift["status"] == "pending"
    code = gift["gift_code"]
    assert code
    assert gift["webapp_link"] == f"https://app.example.com/gift/{code}"
    assert gift["telegram_link"] == f"https://t.me/TestVpnBot?start=gift_{code}"
    assert gift["share_text"]

    # Обычная покупка: приходит именно купленный ключ, подарка нет.
    plain = _post(
        "/api/payment/result",
        {"payment_id": "bbbb0000-0000-0000-0000-000000000001", "token": owner_token},
    )
    assert plain["ready"] is True and plain["action"] == "new"
    assert plain["key"]["sub_url"] == own_sub
    assert plain["gift"] is None


def test_result_is_neutral_for_stranger_anonymous_and_unknown(temp_db, monkeypatch):
    database = temp_db
    owner_token, stranger_token, plan_id = _seed(database)
    pid = "bbbb0000-0000-0000-0000-000000000003"
    _buy(database, monkeypatch, action="gift", plan_id=plan_id, pid=pid, marker="neutral")

    neutral = {"ok": True, "ready": False}
    assert _post("/api/payment/result", {"payment_id": pid, "token": stranger_token}) == neutral
    assert _post("/api/payment/result", {"payment_id": pid}) == neutral
    assert _post("/api/payment/result", {"payment_id": pid, "token": "bad"}) == neutral
    assert _post("/api/payment/result", {"payment_id": "nope", "token": owner_token}) == neutral


def test_result_not_ready_until_service_delivered(temp_db):
    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "bbbb0000-0000-0000-0000-000000000004"
    meta = {"user_id": OWNER_ID, "price": 100.0, "action": "gift", "plan_id": plan_id,
            "host_name": HOST, "payment_method": "YooKassa", "payment_id": pid}
    database.create_payload_pending(pid, OWNER_ID, 100.0, meta)
    assert database.find_and_complete_pending_transaction(pid) is not None
    data = _post("/api/payment/result", {"payment_id": pid, "token": owner_token})
    assert data == {"ok": True, "ready": False}


def test_result_hides_gift_after_someone_else_activated_it(temp_db, monkeypatch):
    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "bbbb0000-0000-0000-0000-000000000005"
    _buy(database, monkeypatch, action="gift", plan_id=plan_id, pid=pid, marker="taken")
    code = _post("/api/payment/result", {"payment_id": pid, "token": owner_token})["gift"]["gift_code"]

    from shop_bot.webapp.web_router.gifts import _activate_gift_for_user

    assert _activate_gift_for_user(RECEIVER_ID, code)["status"] == "activated"

    data = _post("/api/payment/result", {"payment_id": pid, "token": owner_token})
    assert data["ready"] is True and data["action"] == "gift"
    assert data["key"] is None
    assert data["gift"] == {"status": "activated"}
    assert "sub.example" not in json.dumps(data) and "vpn.example" not in json.dumps(data)

    for kind in ("key", "gift_webapp", "gift_telegram"):
        qr = _post("/api/payment/qr", {"payment_id": pid, "kind": kind, "token": owner_token})
        assert qr["ok"] is False, (kind, qr)


def test_qr_is_built_server_side_for_owner_only(temp_db, monkeypatch):
    database = temp_db
    owner_token, stranger_token, plan_id = _seed(database)
    gift_pid = "bbbb0000-0000-0000-0000-000000000006"
    key_pid = "bbbb0000-0000-0000-0000-000000000007"
    _buy(database, monkeypatch, action="gift", plan_id=plan_id, pid=gift_pid, marker="qrgift")
    _buy(database, monkeypatch, action="new", plan_id=plan_id, pid=key_pid, marker="qrkey")

    for kind in ("gift_webapp", "gift_telegram", "key"):
        data = _post("/api/payment/qr", {"payment_id": gift_pid, "kind": kind, "token": owner_token})
        assert data["ok"] is True, (kind, data)
        assert data["image"].startswith(PNG_PREFIX)
        assert len(data["image"]) > len(PNG_PREFIX) + 100

    # У обычной покупки нет подарка — QR подарка не выдаётся.
    assert _post("/api/payment/qr", {"payment_id": key_pid, "kind": "gift_webapp", "token": owner_token})["ok"] is False
    assert _post("/api/payment/qr", {"payment_id": key_pid, "kind": "key", "token": owner_token})["ok"] is True

    # Чужой пользователь, аноним, неизвестный kind — отказ без утечки данных.
    assert _post("/api/payment/qr", {"payment_id": gift_pid, "kind": "key", "token": stranger_token})["ok"] is False
    assert _post("/api/payment/qr", {"payment_id": gift_pid, "kind": "key"})["ok"] is False
    assert _post("/api/payment/qr", {"payment_id": gift_pid, "kind": "https://evil.example", "token": owner_token})["ok"] is False


def test_qr_payload_cannot_be_supplied_by_client(temp_db, monkeypatch):
    """Лишние поля запроса (data/text/url) игнорируются — QR строится только из БД."""
    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "bbbb0000-0000-0000-0000-000000000008"
    _buy(database, monkeypatch, action="gift", plan_id=plan_id, pid=pid, marker="inject")
    captured = []

    import qrcode

    real_make = qrcode.make

    def spy(data, *args, **kwargs):
        captured.append(data)
        return real_make(data, *args, **kwargs)

    monkeypatch.setattr(qrcode, "make", spy)
    data = _post(
        "/api/payment/qr",
        {"payment_id": pid, "kind": "key", "token": owner_token,
         "data": "https://evil.example/phish", "text": "https://evil.example", "url": "https://evil.example"},
    )
    assert data["ok"] is True
    assert captured == ["https://vpn.example/sub/inject"]


def test_check_payment_and_balance_responses_carry_payment_id(temp_db, monkeypatch):
    database = temp_db
    owner_token, _, plan_id = _seed(database)
    pid = "bbbb0000-0000-0000-0000-000000000009"
    _buy(database, monkeypatch, action="gift", plan_id=plan_id, pid=pid, marker="pidcheck")
    data = _post("/api/check-payment", {"payment_id": pid, "token": owner_token})
    assert data["paid"] is True and data["payment_id"] == pid


# --- фронтенд ---------------------------------------------------------------


def _success_js_block() -> str:
    js = mini_app_js()
    a = js.index("function _isHttpUrl(")
    b = js.index("function copySuccessKey(")
    return js[a:b]


def test_success_screen_does_not_use_innerhtml_for_server_data():
    block = _success_js_block()
    assert "innerHTML" not in block
    assert "insertAdjacentHTML" not in block
    assert "outerHTML" not in block
    assert "eval(" not in block
    assert "/api/payment/result" in block and "/api/payment/qr" in block
    assert "indexOf('data:image/png;base64,') === 0" in block


def test_success_screen_markup_has_gift_block_and_qr_controls():
    html = mini_app_html()
    for el_id in (
        "success-title", "success-subtitle", "success-gift-block", "success-gift-links",
        "success-key-card", "success-key-qr-btn", "success-key-qr", "success-key-qr-img",
    ):
        assert f'id="{el_id}"' in html, el_id


def test_success_screen_renders_gift_rows_via_dom_and_filters_unsafe_links():
    assert NODE, "нужен node для vm-теста экрана успеха"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync('src/shop_bot/webapp/static/js/app.js', 'utf8');
const a = src.indexOf('function _isHttpUrl(');
const b = src.indexOf('function copySuccessKey(');
const block = src.slice(a, b);

function makeEl(tag) {
  const el = {
    tag, className: '', children: [], style: {}, attrs: {}, hidden: false,
    classes: new Set(),
    set innerHTML(v) { throw new Error('innerHTML must not be used: ' + v); },
    get innerHTML() { return ''; },
    appendChild(c) { this.children.push(c); return c; },
    replaceChildren() { this.children = []; },
    removeAttribute(n) { delete this.attrs[n]; },
    classList: null,
  };
  el.classList = {
    add: (...c) => c.forEach((x) => el.classes.add(x)),
    remove: (...c) => c.forEach((x) => el.classes.delete(x)),
    contains: (c) => el.classes.has(c),
    toggle: (c, on) => { (on ? el.classes.add(c) : el.classes.delete(c)); },
  };
  el.textContent = '';
  return el;
}
const byId = {};
for (const id of ['success-title','success-subtitle','success-gift-block','success-gift-links',
  'success-key-card','success-connect-btn','success-key-label','success-key-qr','success-key-qr-img',
  'success-key-qr-btn','success-key','success-expiry']) byId[id] = makeEl('div');

const fetchCalls = [];
const sandbox = {
  console,
  document: { getElementById: (id) => byId[id] || null, createElement: makeEl },
  window: { getAuthToken: () => 'tok', getTgInitData: () => '', open() {} },
  navigator: {},
  fetch: async (url, opts) => {
    fetchCalls.push([url, JSON.parse(opts.body)]);
    return { json: async () => ({ ok: true, image: 'data:text/html;base64,PHNjcmlwdD4=' }) };
  },
  showNotification() {},
  encodeURIComponent,
  Object,
  JSON,
  String,
  Promise,
};
sandbox.window.Telegram = undefined;
vm.createContext(sandbox);
vm.runInContext(block + `
this.__api = { _renderSuccessGift, _resetSuccessScreen, _fetchPaymentQr, _isHttpUrl };
`, sandbox);
const api = sandbox.__api;

api._resetSuccessScreen();
const evil = 'https://app.example.com/gift/"><img src=x onerror=alert(1)>';
api._renderSuccessGift({
  action: 'gift',
  key: { key_id: 1, name: 'n', expire_date_str: '01.01.2030', remaining_str: '5д', sub_url: 'https://vpn.example/sub/x' },
  gift: { status: 'pending', gift_code: 'abc', share_text: 'hi',
          webapp_link: evil, telegram_link: 'javascript:alert(1)' },
}, 'pid-1');

const rows = byId['success-gift-links'].children;
const texts = [];
(function walk(n) { if (n.textContent) texts.push(n.textContent); (n.children || []).forEach(walk); })(byId['success-gift-links']);
(async () => {
  const qr = await api._fetchPaymentQr('pid-1', 'key');
  console.log(JSON.stringify({
    rows: rows.length,
    texts,
    title: byId['success-title'].textContent,
    keyText: byId['success-key'].textContent,
    giftBlockHidden: byId['success-gift-block'].classes.has('hidden'),
    foreignQr: qr,
    fetch: fetchCalls,
  }));
})();
"""
    out = subprocess.run(
        [NODE, "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["rows"] == 1, data
    assert any("<img src=x onerror=alert(1)>" in t for t in data["texts"]), data
    assert not any(t.startswith("javascript:") for t in data["texts"]), data
    assert data["title"] == "Подарок готов!"
    assert data["keyText"] == "https://vpn.example/sub/x"
    assert data["giftBlockHidden"] is False
    assert data["foreignQr"] is None
    assert data["fetch"] == [["/api/payment/qr", {"token": "tok", "init_data": "", "payment_id": "pid-1", "kind": "key"}]]
