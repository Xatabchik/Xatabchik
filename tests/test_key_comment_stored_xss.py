"""Stored XSS в заметке и имени ключа: ввод → БД → HTML → не в inline JS.

Старые вредоносные строки уже могут лежать в comment_key / user_key_name.
Экранирование на выдаче обязательно даже если новый ввод нормализован.
Токен авторизации в ассертах и сообщениях об ошибке не печатаем.
"""
from __future__ import annotations

import html as html_lib
import sqlite3
from html.parser import HTMLParser
from pathlib import Path

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

USER_ID = 96001

XSS_PAYLOADS = (
    "<img src=x onerror=alert(1)>",
    "</span><script>alert(1)</script>",
    "');alert(1);//",
    '" onclick="alert(1)',
    "`+alert(1)+`",
    "line1\nline2",
    "back\\slash",
    "quotes ' \" `",
)


class _HtmlProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.onclicks: list[str] = []
        self.event_attrs: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self._in_script = False
        self._script_chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "script":
            self._in_script = True
            self._script_chunks = []
        for name, value in attrs:
            if name and name.startswith("on") and value:
                self.event_attrs.append((name, value))
                if name == "onclick":
                    self.onclicks.append(value)

    def handle_endtag(self, tag):
        if tag == "script":
            self.scripts.append("".join(self._script_chunks))
            self._in_script = False
            self._script_chunks = []

    def handle_data(self, data):
        if self._in_script:
            self._script_chunks.append(data)


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


def _insert_key(db_path: Path, *, comment_key: str | None = None, user_key_name: str | None = None,
                subscription_url: str = "https://sub.example/ok") -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, comment_key, user_key_name
            ) VALUES (?, 'XssHost', 'xss@bot.local', 'xss@bot.local', ?,
                      datetime('now', '+30 days'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)
            """,
            (USER_ID, subscription_url, comment_key, user_key_name),
        )
        key_id = cur.lastrowid
        conn.commit()
    return int(key_id)


def _seed_user(database) -> str:
    insert_user(database.DB_FILE, telegram_id=USER_ID, username="xssuser")
    database.update_setting("webapp_enabled", "true")
    return issue_auth_token(USER_ID)


def _assert_payload_is_text(markup: str, payload: str) -> None:
    """Payload виден как текст, не как теги/атрибуты и не внутри onclick."""
    escaped = html_lib.escape(payload, quote=True)
    assert escaped in markup, "экранированный payload должен остаться текстом"
    if escaped != payload:
        assert payload not in markup, "сырой HTML-payload не должен остаться в разметке"

    probe = _HtmlProbe()
    probe.feed(markup)
    assert "script" not in probe.tags, "payload не должен создать <script>"
    assert not probe.scripts, "payload не должен дать тело script"
    dangerous_event = [v for n, v in probe.event_attrs if "alert" in v or payload in v]
    assert dangerous_event == [], "payload не должен попасть в on*-атрибут"
    for onclick in probe.onclicks:
        assert payload not in onclick
        assert "alert(1)" not in onclick

    if "<img" in payload.lower():
        assert not any(t == "img" for t in probe.tags), "payload не должен создать <img>"


def _card_for(comment: str | None = None, name: str | None = None, url: str = "https://sub.example/ok") -> str:
    from shop_bot.webapp.handlers import _get_key_card_html, _get_setup_keys_html

    key = {
        "key_id": 42,
        "created_at": "2026-01-01 12:00:00",
        "expiry_date": "2029-12-01 12:00:00",
        "user_key_name": name,
        "comment_key": comment,
        "subscription_url": url,
        "host_name": "XssHost",
        "email": "xss@bot.local",
    }
    return _get_key_card_html(key) + _get_setup_keys_html([key])


def test_old_stored_comment_payloads_render_as_text(temp_db):
    """Уже лежащие в БД payload не становятся тегами и не попадают в onclick."""
    for payload in XSS_PAYLOADS:
        html = _card_for(comment=payload)
        _assert_payload_is_text(html, payload)
        assert 'data-key-action="comment"' in html
        assert f"openActionModal('comment'" not in html


def test_old_stored_name_and_url_payloads_render_as_text(temp_db):
    name = "<img src=x onerror=alert(1)>"
    url = "https://evil.example/'onclick=alert(1)//"
    html = _card_for(name=name, url=url)
    _assert_payload_is_text(html, name)
    assert html_lib.escape(url, quote=True) in html
    assert "openLinkSafe(" not in html
    assert "copyKey(" not in html
    assert 'data-key-action="open-key"' in html
    assert 'data-key-action="rename"' in html


def test_comment_api_normalizes_and_clears(temp_db):
    from shop_bot.data_manager import database

    token = _seed_user(database)
    key_id = _insert_key(database.DB_FILE, comment_key="старое")
    client = _client()

    too_long = "x" * (database.KEY_COMMENT_MAX_LEN + 1)
    resp = client.post(
        "/api/key/comment",
        json={"token": token, "key_id": key_id, "comment": too_long},
    )
    assert resp.json().get("ok") is False
    assert database.get_key_by_id(key_id)["comment_key"] == "старое"

    resp = client.post(
        "/api/key/comment",
        json={"token": token, "key_id": key_id, "comment": "  \n\t  "},
    )
    assert resp.json().get("ok") is True
    assert database.get_key_by_id(key_id)["comment_key"] in (None, "")

    resp = client.post(
        "/api/key/comment",
        json={"token": token, "key_id": key_id, "comment": "  ок\x00 заметка  "},
    )
    assert resp.json().get("ok") is True
    stored = database.get_key_by_id(key_id)["comment_key"]
    assert stored == "ок заметка"
    assert "\x00" not in stored


def test_comment_api_stores_payload_but_page_escapes_it(temp_db, monkeypatch):
    """Новый XSS-ввод сохраняется как текст; SSR и search отдают его экранированным."""
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    token = _seed_user(database)
    key_id = _insert_key(database.DB_FILE)
    payload = "<img src=x onerror=alert(1)>"
    client = _client()
    resp = client.post(
        "/api/key/comment",
        json={"token": token, "key_id": key_id, "comment": payload},
    )
    assert resp.json().get("ok") is True
    assert database.get_key_by_id(key_id)["comment_key"] == payload

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)

    page = client.get("/", params={"token": token})
    assert page.status_code == 200
    assert token not in page.text
    start = page.text.index('id="profile-keys-list-container"')
    end = page.text.index('id="profile-keys-pagination"')
    _assert_payload_is_text(page.text[start:end], payload)

    search = client.post(
        "/api/keys/search",
        json={"token": token, "query": "xss"},
    )
    body = search.json()
    assert body.get("ok") is True
    _assert_payload_is_text(body.get("html") or "", payload)


def test_frontend_does_not_interpolate_comment_into_html_or_onclick():
    html = Path("src/shop_bot/webapp/app.html").read_text(encoding="utf-8")
    comment_fn = html[html.index("type === 'comment'"): html.index("function formatCooldownRemaining")]
    assert "${extraData}" not in comment_fn
    assert "storedCommentEl.textContent" in comment_fn
    assert "commentInput.value = storedComment" in comment_fn
    assert 'onclick="saveComment' not in comment_fn
    assert 'data-key-action' in html
    assert "comment-text-" in html
    assert "openActionModal('comment', ${" not in html


def test_normalize_key_comment_unit():
    from shop_bot.data_manager.db.keys import KEY_COMMENT_MAX_LEN, normalize_key_comment

    assert normalize_key_comment(None) == (None, None)
    assert normalize_key_comment("") == (None, None)
    assert normalize_key_comment("   ") == (None, None)
    value, err = normalize_key_comment("  a\r\nb  ")
    assert err is None
    assert value == "a\nb"
    value, err = normalize_key_comment("x" * (KEY_COMMENT_MAX_LEN + 1))
    assert value is None
    assert err
    assert "x" * 20 not in err
