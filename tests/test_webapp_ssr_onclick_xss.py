"""SSR data-* карточек ключей/планов/подарков: payload из #145/#156 не становится onclick."""
from __future__ import annotations

import html as html_lib
from html.parser import HTMLParser

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

USER_ID = 16311
EMAIL_ONLY_ID = 999000000011

XSS_PAYLOADS = (
    "<img src=x onerror=alert(1)>",
    "</span><script>alert(1)</script>",
    "');alert(1);//",
    '" onclick="alert(1)',
    "`+alert(1)+`",
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


def _assert_payload_is_text(markup: str, payload: str) -> None:
    escaped = html_lib.escape(payload, quote=True)
    assert escaped in markup, "экранированный payload должен остаться текстом"
    if escaped != payload:
        assert payload not in markup, "сырой HTML-payload не должен остаться в разметке"
    probe = _HtmlProbe()
    probe.feed(markup)
    assert "script" not in probe.tags
    assert not probe.scripts
    dangerous_event = [v for n, v in probe.event_attrs if "alert" in v or payload in v]
    assert dangerous_event == []
    assert probe.onclicks == []
    if "<img" in payload.lower():
        assert not any(t == "img" for t in probe.tags)


def _sample_key(**overrides) -> dict:
    key = {
        "key_id": 42,
        "created_at": "2026-01-01 12:00:00",
        "expiry_date": "2029-12-01 12:00:00",
        "user_key_name": "ok",
        "comment_key": "",
        "subscription_url": "https://sub.example/ok",
        "host_name": "XssHost",
        "email": "xss@bot.local",
        "auto_renew": False,
    }
    key.update(overrides)
    return key


def test_key_card_data_attrs_escape_xss_payloads(temp_db):
    from shop_bot.webapp.handlers import _get_key_card_html, _get_renew_keys_html

    for payload in XSS_PAYLOADS:
        card = _get_key_card_html(_sample_key(user_key_name=payload, comment_key=payload, host_name=payload))
        _assert_payload_is_text(card, payload)
        assert 'data-key-action="renew"' in card
        assert 'data-key-action="auto-renew"' in card
        assert 'onclick="goToRenewKey(' not in card
        assert 'onclick="toggleKeyAutoRenew(' not in card
        assert "goToRenewKey(" not in card
        assert "toggleKeyAutoRenew(" not in card

        options, selected, _plans = _get_renew_keys_html([_sample_key(user_key_name=payload, host_name=payload)])
        renew = options + selected
        _assert_payload_is_text(renew, payload)
        assert 'onclick="selectRenewKey(' not in options
        assert "selectRenewKey(" not in options


def test_plan_and_server_data_attrs_escape_xss(temp_db, monkeypatch):
    import shop_bot.webapp.web_router.render_plans as render_plans

    host_payload = '" onclick="alert(1)'
    plan_payload = "<img src=x onerror=alert(1)>"
    hosts = [{"host_name": host_payload, "description": "Выберите тариф"}]
    plans = [{
        "plan_id": '7" onclick="alert(1)',
        "plan_name": plan_payload,
        "price": 100,
        "months": 1,
        "duration_days": 0,
        "is_active": True,
    }]
    monkeypatch.setattr(render_plans, "get_all_hosts", lambda: hosts)
    monkeypatch.setattr(render_plans, "get_plans_for_host", lambda _name: plans)

    servers, grid = render_plans._get_servers_and_plans_html(16312)
    markup = servers + grid
    _assert_payload_is_text(markup, host_payload)
    _assert_payload_is_text(markup, plan_payload)
    assert 'onclick="selectPlan(' not in markup
    assert 'onclick="selectServer(' not in markup
    assert "selectPlan(" not in markup
    assert "selectServer(" not in markup
    assert 'class="server-option' in servers
    assert "plan-btn" in grid
    assert html_lib.escape(host_payload, quote=True) in servers
    assert html_lib.escape(plan_payload, quote=True) in grid


def test_gift_code_data_attr_escapes_xss(temp_db):
    from shop_bot.webapp.handlers import _get_gift_action_block_html

    for payload in XSS_PAYLOADS:
        webapp_link = f"https://app.example/gift/{payload}"
        telegram_link = f"https://t.me/bot?start=gift_{payload}"
        html = _get_gift_action_block_html(payload, webapp_link, telegram_link)
        _assert_payload_is_text(html, payload)
        assert 'onclick="activateOwnGift(' not in html
        assert 'onclick="copyToClipboard(' not in html
        assert "activateOwnGift(" not in html
        assert "copyToClipboard(" not in html
        assert 'data-gift-action="activate"' in html
        assert 'data-copy-action="clipboard"' in html


def test_sync_telegram_bot_username_escapes_xss(temp_db, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.webapp.handlers import _get_profile_card_html

    payload = '" onclick="alert(1)'
    database.update_setting("telegram_bot_username", payload)
    html = _get_profile_card_html(
        {
            "telegram_id": EMAIL_ONLY_ID,
            "balance": 0,
            "registration_date": "2026-01-01 00:00:00",
            "referral_balance": 0,
        },
        0,
        0,
    )
    _assert_payload_is_text(html, payload)
    assert 'onclick="syncTelegram(' not in html
    assert "syncTelegram(" not in html
    assert 'data-sync-telegram="1"' in html


def test_served_page_ssr_cards_escape_xss(temp_db, app_client, monkeypatch):
    import sqlite3

    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    payload = '" onclick="alert(1)'
    database.update_setting("webapp_enabled", "true")
    database.update_setting("telegram_bot_username", payload)
    insert_user(database.DB_FILE, telegram_id=EMAIL_ONLY_ID, username="ssr-xss")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, subscription_url,
                expire_at, created_at, updated_at, comment_key, user_key_name
            ) VALUES (?, ?, 'ssr@bot.local', 'ssr@bot.local',
                      'https://sub.example/ssr', datetime('now', '+30 days'),
                      CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)
            """,
            (EMAIL_ONLY_ID, payload, payload, payload),
        )
        conn.commit()

    async def _no_details(_key):
        return None

    monkeypatch.setattr(remnawave_api, "get_key_details_from_host", _no_details)
    token = issue_auth_token(EMAIL_ONLY_ID)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    html = resp.text
    assert token not in html
    start = html.index('id="profile-keys-list-container"')
    end = html.index('id="profile-keys-pagination"')
    _assert_payload_is_text(html[start:end], payload)
    assert 'data-key-action="renew"' in html
    assert 'data-sync-telegram="1"' in html
    assert 'onclick="goToRenewKey(' not in html
    assert 'onclick="syncTelegram(' not in html
    assert 'onclick="selectPlan(' not in html
    assert 'onclick="selectServer(' not in html
