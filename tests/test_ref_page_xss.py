"""Регрессия reflected XSS (CWE-79) в GET /ref/{referrer_id} и GET /gift/{gift_code}.

До фикса сырой path попадал в href fallback-страницы:

    deeplink = f"https://t.me/{bot}?start=ref_{referrer_id}"
    action_html = f"<a class='btn' href='{deeplink}'>Открыть в Telegram</a>"

PoC: /ref/1'%3E%3Cimg%20src=x%20onerror=alert(1)%3E
     /ref/1'%20onmouseover='alert(1)
"""
from __future__ import annotations

from conftest import insert_gift_key, insert_user, temp_db  # noqa: F401

IMG_XSS = "1'><img src=x onerror=alert(1)>"
HOVER_XSS = "1' onmouseover='alert(1)"
# Те же payload, что в задаче, в percent-encoding.
IMG_XSS_ENCODED = "/ref/1'%3E%3Cimg%20src=x%20onerror=alert(1)%3E"
HOVER_XSS_ENCODED = "/ref/1'%20onmouseover='alert(1)"


def _assert_no_reflected_xss(body: str) -> None:
    lowered = body.lower()
    assert "<img src=x" not in lowered
    assert "onerror=alert(1)" not in lowered
    assert "onmouseover='alert(1)" not in lowered
    assert 'onmouseover="alert(1)' not in lowered
    assert "onmouseover=alert" not in lowered


def test_ref_img_xss_payload_is_not_reflected(temp_db, app_client):
    r = app_client.get(f"/ref/{IMG_XSS}")
    assert r.status_code == 200
    _assert_no_reflected_xss(r.text)
    assert IMG_XSS not in r.text
    assert "script-src 'self'" in r.headers.get("content-security-policy", "")


def test_ref_onmouseover_xss_payload_is_not_in_href(temp_db, app_client):
    r = app_client.get(f"/ref/{HOVER_XSS}")
    assert r.status_code == 200
    _assert_no_reflected_xss(r.text)
    assert HOVER_XSS not in r.text
    assert "onmouseover=" not in r.text.lower()
    # Невалидный id не попадает в start=ref_...
    assert "start=ref_1'" not in r.text
    assert "script-src 'self'" in r.headers.get("content-security-policy", "")


def test_ref_encoded_poc_urls_are_not_reflected(temp_db, app_client):
    img = app_client.get(IMG_XSS_ENCODED)
    hover = app_client.get(HOVER_XSS_ENCODED)
    assert img.status_code == 200
    assert hover.status_code == 200
    _assert_no_reflected_xss(img.text)
    _assert_no_reflected_xss(hover.text)


def test_ref_existing_user_still_redirects_to_pending(temp_db, app_client):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=44001, username="refxss")
    r = app_client.get("/ref/44001", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "pending_token=" in r.headers.get("location", "")


def test_ref_unknown_numeric_id_neutral_fallback_with_telegram_deeplink(temp_db, app_client):
    """Валидный numeric id — тот же ответ, что и для существующего пользователя
    (302 + pending_token), без оракула существования."""
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=44001, username="refxss")
    existing = app_client.get("/ref/44001", follow_redirects=False)
    unknown = app_client.get("/ref/44099", follow_redirects=False)
    assert unknown.status_code == existing.status_code
    assert unknown.status_code in (302, 307)
    assert "pending_token=" in (existing.headers.get("location") or "")
    assert "pending_token=" in (unknown.headers.get("location") or "")
    assert (existing.headers.get("location") or "").split("pending_token=")[0] == (
        (unknown.headers.get("location") or "").split("pending_token=")[0]
    )


def test_gift_xss_payload_is_not_reflected(temp_db, app_client):
    img = app_client.get(f"/gift/{IMG_XSS}")
    hover = app_client.get(f"/gift/{HOVER_XSS}")
    assert img.status_code == 200
    assert hover.status_code == 200
    _assert_no_reflected_xss(img.text)
    _assert_no_reflected_xss(hover.text)
    assert IMG_XSS not in img.text
    assert HOVER_XSS not in hover.text
    assert "start=gift_1'" not in img.text
    assert "start=gift_1'" not in hover.text
    assert "script-src 'self'" in img.headers.get("content-security-policy", "")


def test_gift_valid_code_still_redirects(temp_db, app_client):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=44002, username="gifterxss")
    insert_gift_key(database.DB_FILE, from_user_id=44002, gift_code="GIFT-XSS-OK")
    r = app_client.get("/gift/GIFT-XSS-OK", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "pending_token=" in r.headers.get("location", "")


def test_gift_unknown_safe_code_fallback_deeplink(temp_db, app_client):
    r = app_client.get("/gift/GIFT-MISSING", follow_redirects=False)
    assert r.status_code == 200
    assert "https://t.me/TestVpnBot?start=gift_GIFT-MISSING" in r.text
    assert "Открыть в Telegram" in r.text
    _assert_no_reflected_xss(r.text)
