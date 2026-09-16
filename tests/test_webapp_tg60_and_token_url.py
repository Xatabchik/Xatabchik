"""Telegram WebApp 6.0 appearance + persistent auth token не в URL.

Stage 0 — карта источников persistent auth_token в query string (до фикса):

Место | Было | Станет | Legacy | Риск
----- | ---- | ------ | ------ | ----
GET /?token= (index) | query → кабинет | 303 + cookie auth_token → / | да, redirect | cookie уже доверяют API
GET /token=<uuid> (dynamic_route) | path → кабинет | тот же 303 | да | редко, тот же cookie
login.html после входа / savedToken | location /?token= | location / (cookie уже setAuthToken) | — | без чтения cookie GET / снова login
app.html refreshAppData | fetch /?token= | apiFetch('/') + Bearer | — | HTML кабинета без query
GET /api/user-status?token= | query | Bearer / cookie; query ещё принимаем | query для старых клиентов | не логировать token
GET /api/user/transactions?token= | query | Bearer / cookie | query leftover | то же
GET /api/lte-packages?key_id=&token= | query | Bearer / cookie | query leftover | то же
GET /api/support/ticket-file (img src) | cookie, query в тестах | без изменений схемы | query leftover | img не шлёт Bearer
POST JSON token | body | body (без смены) | — | не в access log query
pending_token query | отдельный one-shot | без изменений | да | не auth_token
/api/auth/check-token/{id} | path one-shot Telegram poll | без изменений | — | не persistent auth
t.me/?start=sync_ | Telegram start payload | без изменений | — | не Mini App URL

Telegram version-sensitive (Bot API):
- ready()/expand() — 6.0, оставляем
- setHeaderColor / setBackgroundColor / HapticFeedback / isVersionAtLeast — 6.1+
- showPopup/showAlert — 6.2+, отдельный PR, здесь не трогаем
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from conftest import (  # noqa: F401
    FAKE_BOT_TOKEN,
    insert_user,
    issue_auth_token,
    make_telegram_init_data,
    no_smtp,
    register_and_verify_email_user,
    temp_db,
)
from webapp_frontend_src import mini_app_frontend_source, mini_app_html

HTML = mini_app_html()
FRONTEND = mini_app_frontend_source()
LOGIN = Path("src/shop_bot/webapp/login.html").read_text(encoding="utf-8")
NODE = shutil.which("node")

_API_TOKEN_QS = re.compile(r"""['"`]/api/[^'"`\s]*[?&]token=""")
_ROOT_TOKEN_NAV = re.compile(r"""['"`]/\?token=""")


def _client(*, follow_redirects: bool = True):
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app, follow_redirects=follow_redirects)


def _enable_webapp():
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")


def _query_has_auth_token(url: str) -> bool:
    return "token" in parse_qs(urlparse(url).query)


def _extract_html_fn(source: str, start: str, end: str) -> str:
    assert start in source
    start_idx = source.index(start)
    end_idx = source.index(end, start_idx)
    return source[start_idx:end_idx]


def _run_node(script: str) -> dict:
    assert NODE, "нужен node для проверки Telegram 6.0 mock"
    proc = subprocess.run(
        [NODE, "-e", script],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = (proc.stdout or "").strip().splitlines()[-1]
    return json.loads(payload)


def _appearance_helpers() -> str:
    return _extract_html_fn(
        FRONTEND,
        "function telegramVersionAtLeast(",
        "// --- end Telegram WebApp version-safe helpers ---",
    )


# --- Telegram 6.0 appearance -------------------------------------------------

def test_appearance_helpers_gate_header_and_background_on_6_1():
    helper = _appearance_helpers()
    assert "telegramVersionAtLeast('6.1')" in helper
    assert "isVersionAtLeast" in helper
    assert "setHeaderColor" in helper
    assert "setBackgroundColor" in helper
    assert "try" in helper
    assert "catch" in helper
    # Прямые вызовы только внутри helper, не из UI-init / updateThemeColor.
    assert "tgApp.setHeaderColor" not in FRONTEND
    assert "tgApp.setBackgroundColor" not in FRONTEND
    assert "WebApp.setHeaderColor" not in FRONTEND
    assert "safeTelegramAppearance(" in FRONTEND
    assert "safeTelegramHaptic(" in FRONTEND


def test_frontend_haptic_goes_through_version_guard():
    helper = _appearance_helpers()
    assert "HapticFeedback" in helper
    assert "notificationOccurred" in helper
    assert "WebApp.HapticFeedback.notificationOccurred" not in FRONTEND
    assert FRONTEND.count("safeTelegramHaptic(") >= 3


def test_telegram_6_0_skips_appearance_and_does_not_throw():
    helper = _appearance_helpers()
    script = f"""
{helper}
const calls = {{ header: 0, background: 0, haptic: 0 }};
global.window = {{
  Telegram: {{
    WebApp: {{
      version: '6.0',
      setHeaderColor() {{ calls.header += 1; throw new Error('WebAppMethodUnsupported'); }},
      setBackgroundColor() {{ calls.background += 1; throw new Error('WebAppMethodUnsupported'); }},
      HapticFeedback: {{
        notificationOccurred() {{ calls.haptic += 1; throw new Error('WebAppMethodUnsupported'); }}
      }}
    }}
  }}
}};
let threw = false;
try {{
  safeTelegramAppearance({{ header: '#0a0a0a', background: '#0a0a0a' }});
  safeTelegramHaptic('success');
}} catch (e) {{
  threw = true;
}}
console.log(JSON.stringify({{ calls, threw, atLeast: telegramVersionAtLeast('6.1') }}));
"""
    result = _run_node(script)
    assert result["threw"] is False
    assert result["atLeast"] is False
    assert result["calls"]["header"] == 0
    assert result["calls"]["background"] == 0
    assert result["calls"]["haptic"] == 0


def test_telegram_supported_version_calls_appearance():
    helper = _appearance_helpers()
    script = f"""
{helper}
const calls = {{ header: 0, background: 0, haptic: 0 }};
global.window = {{
  Telegram: {{
    WebApp: {{
      version: '7.0',
      isVersionAtLeast(v) {{ return true; }},
      setHeaderColor(color) {{ calls.header += 1; this._h = color; }},
      setBackgroundColor(color) {{ calls.background += 1; this._b = color; }},
      HapticFeedback: {{
        notificationOccurred(kind) {{ calls.haptic += 1; this._kind = kind; }}
      }}
    }}
  }}
}};
let threw = false;
try {{
  safeTelegramAppearance({{ header: '#0a0a0a', background: '#0a0a0a' }});
  safeTelegramHaptic('success');
}} catch (e) {{
  threw = true;
}}
console.log(JSON.stringify({{ calls, threw }}));
"""
    result = _run_node(script)
    assert result["threw"] is False
    assert result["calls"]["header"] == 1
    assert result["calls"]["background"] == 1
    assert result["calls"]["haptic"] == 1


# --- Token must not live in URL ---------------------------------------------

def test_frontend_does_not_put_auth_token_in_api_or_root_query():
    app_api = _API_TOKEN_QS.findall(FRONTEND)
    login_api = _API_TOKEN_QS.findall(LOGIN)
    app_root = _ROOT_TOKEN_NAV.findall(FRONTEND)
    login_root = _ROOT_TOKEN_NAV.findall(LOGIN)
    assert app_api == []
    assert login_api == []
    assert app_root == []
    assert login_root == []
    assert "apiFetch(" in FRONTEND
    assert "Authorization" in FRONTEND
    assert "Bearer " in FRONTEND
    assert 'appendPendingToken("/")' in LOGIN or 'appendPendingToken(\'/\')' in LOGIN


def test_user_status_and_transactions_accept_authorization_header(temp_db):
    from shop_bot.data_manager import database

    user_id = 96001
    insert_user(database.DB_FILE, telegram_id=user_id, username="beareruser", balance=42.0)
    token = issue_auth_token(user_id)
    client = _client()
    headers = {"Authorization": f"Bearer {token}"}

    status = client.get("/api/user-status", headers=headers)
    assert status.status_code == 200
    body = status.json()
    assert body.get("ok") is True
    assert body.get("balance") == 42.0
    leaked = token in status.text
    assert leaked is False

    tx = client.get("/api/user/transactions?page=1&per_page=10", headers=headers)
    assert tx.status_code == 200
    assert tx.json().get("ok") is True
    leaked_tx = token in tx.text
    assert leaked_tx is False


def test_legacy_root_token_redirects_to_clean_url(temp_db):
    from shop_bot.data_manager import database

    user_id = 96002
    insert_user(database.DB_FILE, telegram_id=user_id, username="legacyuser")
    _enable_webapp()
    token = issue_auth_token(user_id)

    raw = _client(follow_redirects=False)
    resp = raw.get("/", params={"token": token, "pending_token": "keep-me"})
    assert resp.status_code in (302, 303)
    location = resp.headers.get("location") or ""
    assert _query_has_auth_token(location) is False
    assert "pending_token=keep-me" in location
    assert (resp.headers.get("Referrer-Policy") or "") == "no-referrer"
    leaked_html = token in (resp.text or "")
    assert leaked_html is False
    assert resp.cookies.get("auth_token") is not None


def test_legacy_root_token_follow_has_no_token_in_html(temp_db):
    from shop_bot.data_manager import database

    user_id = 96003
    insert_user(database.DB_FILE, telegram_id=user_id, username="followuser")
    _enable_webapp()
    token = issue_auth_token(user_id)

    client = _client(follow_redirects=True)
    resp = client.get("/", params={"token": token})
    assert resp.status_code == 200
    assert f'parseInt("{user_id}")' in resp.text
    leaked = token in resp.text
    assert leaked is False
    assert _query_has_auth_token(str(resp.url)) is False
    assert (resp.headers.get("Referrer-Policy") or "") == "no-referrer"


def test_html_responses_send_referrer_policy_no_referrer(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=96004, username="refpol")
    _enable_webapp()
    client = _client()
    login = client.get("/")
    assert login.status_code == 200
    assert (login.headers.get("Referrer-Policy") or "") == "no-referrer"

    token = issue_auth_token(96004)
    app_page = client.get("/", headers={"Authorization": f"Bearer {token}"})
    assert app_page.status_code == 200
    assert (app_page.headers.get("Referrer-Policy") or "") == "no-referrer"
    leaked = token in app_page.text
    assert leaked is False


def test_invalid_query_token_does_not_create_session(temp_db):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=96005, username="victim")
    _enable_webapp()

    raw = _client(follow_redirects=False)
    resp = raw.get("/", params={"token": "not-a-valid-session"})
    assert resp.status_code in (302, 303)
    assert resp.cookies.get("auth_token") in (None, "")
    location = resp.headers.get("location") or ""
    assert _query_has_auth_token(location) is False

    follow = _client(follow_redirects=True)
    page = follow.get("/", params={"token": "not-a-valid-session"})
    assert page.status_code == 200
    assert 'parseInt("96005")' not in page.text
    leaked = "not-a-valid-session" in page.text
    assert leaked is False


def test_cookie_auth_opens_cabinet_without_query_token(temp_db):
    from shop_bot.data_manager import database

    user_id = 96006
    insert_user(database.DB_FILE, telegram_id=user_id, username="cookieuser")
    _enable_webapp()
    token = issue_auth_token(user_id)

    client = _client()
    client.cookies.set("auth_token", token)
    page = client.get("/")
    assert page.status_code == 200
    assert f'parseInt("{user_id}")' in page.text
    leaked = token in page.text
    assert leaked is False


def test_email_login_still_issues_token_in_json_not_url(temp_db, no_smtp):
    """Login по email не ослаблен: token остаётся в JSON, не в Location."""
    client = _client()
    issued, user_id = register_and_verify_email_user(
        client, None, "tg60-login@example.com"
    )
    assert user_id
    login = client.post(
        "/api/auth/email/login",
        json={"email": "tg60-login@example.com", "password": "Passw0rd!"},
    )
    data = login.json()
    assert data.get("ok") is True
    assert data.get("token")
    leaked = data["token"] in (login.headers.get("location") or "")
    assert leaked is False


def test_telegram_init_data_auth_still_requires_hmac(temp_db):
    from shop_bot.data_manager import database

    user_id = 96008
    insert_user(database.DB_FILE, telegram_id=user_id, username="tginit")
    database.update_setting("telegram_bot_token", FAKE_BOT_TOKEN)

    client = _client()
    denied = client.post("/api/auth/token", json={"init_data": "user=%7B%22id%22%3A96008%7D"})
    assert denied.status_code in (401, 400, 200)
    if denied.status_code == 200:
        assert denied.json().get("ok") is not True or not denied.json().get("token")

    ok = client.post("/api/auth/token", json={"init_data": make_telegram_init_data(user_id)})
    body = ok.json()
    assert body.get("token")
    leaked = body["token"] in (ok.headers.get("location") or "")
    assert leaked is False


def test_key_comment_owner_check_unchanged(temp_db):
    import sqlite3
    from shop_bot.data_manager import database

    owner_id, attacker_id = 96009, 96010
    insert_user(database.DB_FILE, telegram_id=owner_id, username="keyowner")
    insert_user(database.DB_FILE, telegram_id=attacker_id, username="keyattacker")
    owner_token = issue_auth_token(owner_id)
    attacker_token = issue_auth_token(attacker_id)

    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at)
            VALUES (?, 'Host', 'a@b.c', 'a@b.c', 'vless://x', datetime('now', '+30 days'), CURRENT_TIMESTAMP)
            """,
            (owner_id,),
        )
        key_id = cur.lastrowid
        conn.commit()

    client = _client()
    foreign = client.post(
        "/api/key/comment",
        json={"token": attacker_token, "key_id": key_id, "comment": "nope"},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert foreign.json().get("ok") is False

    mine = client.post(
        "/api/key/comment",
        json={"key_id": key_id, "comment": "ok"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert mine.json().get("ok") is True
