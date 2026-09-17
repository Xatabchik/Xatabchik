"""Этап 1: Mini App без Tailwind CDN / Google Fonts, CSP groundwork, локальная статика.

Не проверяем UX и не печатаем auth token.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401

WEBAPP = Path("src/shop_bot/webapp")
FORBIDDEN_HOSTS = (
    "cdn.tailwindcss.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)
PAGE_FILES = (
    WEBAPP / "app.html",
    WEBAPP / "login.html",
    WEBAPP / "module" / "load.html",
    WEBAPP / "web_router" / "render_page.py",
)
TELEGRAM_SDK = "https://telegram.org/js/telegram-web-app.js"
LOCAL_CSS = "/static/css/app.css"
LOCAL_JS = "/static/js/app.js"
CSS_HREF_RE = re.compile(r"/static/css/app\.css\?v=([0-9a-f]{12})")
JS_HREF_RE = re.compile(r"/static/js/app\.js\?v=([0-9a-f]{12})")


def _css_content_hash() -> str:
    return hashlib.sha256((WEBAPP / "static" / "css" / "app.css").read_bytes()).hexdigest()[:12]


def _expected_css_href() -> str:
    return f"{LOCAL_CSS}?v={_css_content_hash()}"


def _js_content_hash() -> str:
    return hashlib.sha256((WEBAPP / "static" / "js" / "app.js").read_bytes()).hexdigest()[:12]


def _expected_js_href() -> str:
    return f"{LOCAL_JS}?v={_js_content_hash()}"


def _max_age(header: str) -> int | None:
    match = re.search(r"max-age=(\d+)", header)
    return int(match.group(1)) if match else None


def _assert_no_cdn(text: str) -> None:
    lowered = text.lower()
    for host in FORBIDDEN_HOSTS:
        assert host not in lowered, f"остался сторонний origin {host}"
    assert "tailwind.config" not in text


def _assert_webapp_csp(csp: str) -> None:
    assert "default-src 'self'" in csp
    assert "script-src 'self' https://telegram.org 'unsafe-inline'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "font-src 'self'" in csp
    assert "cdn.tailwindcss.com" not in csp
    assert "fonts.googleapis.com" not in csp
    assert "fonts.gstatic.com" not in csp
    assert "https://telegram.org" in csp
    assert "frame-ancestors 'self' https://web.telegram.org https://k.telegram.org" in csp


def test_source_html_has_no_tailwind_cdn_or_google_fonts():
    for path in PAGE_FILES:
        text = path.read_text(encoding="utf-8")
        _assert_no_cdn(text)
        assert (
            "{{ app_css_href }}" in text
            or "APP_CSS_HREF" in text
            or LOCAL_CSS in text
        ), f"{path} не ссылается на локальный CSS"


def test_app_and_login_keep_telegram_sdk_on_telegram_origin():
    app_html = (WEBAPP / "app.html").read_text(encoding="utf-8")
    login_html = (WEBAPP / "login.html").read_text(encoding="utf-8")
    assert TELEGRAM_SDK in app_html
    assert TELEGRAM_SDK in login_html
    static_js = list((WEBAPP / "static").rglob("*.js"))
    assert static_js, "Этап 2: Mini App JS лежит в /static/js/"
    assert all("telegram-web-app" not in p.name for p in static_js)
    assert (WEBAPP / "static" / "js" / "app.js").is_file()
    assert "{{ app_js_href }}" in app_html
    assert 'src="{{ app_js_href }}" defer>' in app_html
    _assert_no_cdn(app_html)
    for path in static_js:
        _assert_no_cdn(path.read_text(encoding="utf-8"))


def test_login_page_serves_local_css_and_csp(temp_db, app_client):
    resp = app_client.get("/")
    assert resp.status_code == 200
    _assert_no_cdn(resp.text)
    assert TELEGRAM_SDK in resp.text
    assert _expected_css_href() in resp.text
    assert _expected_js_href() not in resp.text
    _assert_webapp_csp(resp.headers.get("content-security-policy", ""))
    assert "no-store" in resp.headers.get("cache-control", "")


def test_authed_app_page_serves_local_css_and_csp(temp_db, app_client):
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=91001, username="assets")
    token = issue_auth_token(91001)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 200
    assert token not in resp.text
    _assert_no_cdn(resp.text)
    assert TELEGRAM_SDK in resp.text
    assert _expected_css_href() in resp.text
    assert _expected_js_href() in resp.text
    assert JS_HREF_RE.search(resp.text)
    _assert_webapp_csp(resp.headers.get("content-security-policy", ""))


def test_banned_page_has_no_cdn_and_has_csp(temp_db, app_client):
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    insert_user(database.DB_FILE, telegram_id=91002, username="banned-assets", is_banned=1)
    token = issue_auth_token(91002)
    resp = app_client.get("/", params={"token": token})
    assert resp.status_code == 403
    assert token not in resp.text
    _assert_no_cdn(resp.text)
    assert _expected_css_href() in resp.text
    _assert_webapp_csp(resp.headers.get("content-security-policy", ""))


def test_local_css_and_fonts_are_served(temp_db, app_client):
    css = app_client.get(LOCAL_CSS)
    assert css.status_code == 200
    assert "text/css" in css.headers.get("content-type", "")
    assert "bg-background-dark" in css.text
    assert "Material Symbols Rounded" in css.text
    assert "font-family: 'Inter'" in css.text or "font-family:'Inter'" in css.text
    assert css.headers.get("x-content-type-options", "").lower() == "nosniff"
    fonts = list((WEBAPP / "static" / "fonts").glob("*.woff2"))
    assert fonts, "нет локальных woff2"
    sample = fonts[0]
    font_resp = app_client.get(f"/static/fonts/{sample.name}")
    assert font_resp.status_code == 200
    assert font_resp.content[:4] in (b"wOF2", b"wOFF")
    assert font_resp.headers.get("x-content-type-options", "").lower() == "nosniff"


def test_static_cache_control_differs_for_css_and_hashed_fonts(temp_db, app_client):
    """CSS со стабильным путём нельзя кэшировать сутки; шрифты с hash — можно."""
    expected = _expected_css_href()
    login = app_client.get("/")
    assert CSS_HREF_RE.search(login.text)
    assert expected in login.text

    css = app_client.get(LOCAL_CSS)
    css_versioned = app_client.get(LOCAL_CSS, params={"v": _css_content_hash()})
    assert css.status_code == 200
    assert css_versioned.status_code == 200
    assert css.content == css_versioned.content
    css_cc = css.headers.get("cache-control", "").lower()
    assert _max_age(css_versioned.headers.get("cache-control", "")) == 0
    assert _max_age(css_cc) == 0
    assert "must-revalidate" in css_cc
    assert "immutable" not in css_cc
    assert "86400" not in css_cc

    fonts = list((WEBAPP / "static" / "fonts").glob("*.woff2"))
    assert any(re.search(r"[0-9a-f]{8,}", p.name) for p in fonts)
    font_resp = app_client.get(f"/static/fonts/{fonts[0].name}")
    font_cc = font_resp.headers.get("cache-control", "").lower()
    assert font_resp.status_code == 200
    assert _max_age(font_cc) == 31536000
    assert "immutable" in font_cc


def test_local_js_entrypoint_is_served_without_long_cache(temp_db, app_client):
    expected = _expected_js_href()
    js = app_client.get(LOCAL_JS)
    js_versioned = app_client.get(LOCAL_JS, params={"v": _js_content_hash()})
    assert js.status_code == 200
    assert js_versioned.status_code == 200
    assert js.content == js_versioned.content
    assert "function telegramVersionAtLeast(" in js.text
    assert "function openTopUpModal(" in js.text
    assert "Temporary compatibility bridge" not in js.text
    ctype = js.headers.get("content-type", "")
    assert "javascript" in ctype or "ecmascript" in ctype
    js_cc = js.headers.get("cache-control", "").lower()
    assert _max_age(js_versioned.headers.get("cache-control", "")) == 0
    assert _max_age(js_cc) == 0
    assert "must-revalidate" in js_cc
    assert "immutable" not in js_cc
    assert js.headers.get("x-content-type-options", "").lower() == "nosniff"
    assert expected.endswith(_js_content_hash())


def test_font_checksums_match_committed_woff2():
    fonts_dir = WEBAPP / "static" / "fonts"
    manifest = (fonts_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {}
    for line in manifest:
        digest, name = line.split()
        listed[name] = digest
    woff2 = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fonts_dir.glob("*.woff2")}
    assert listed == woff2, "SHA256SUMS не совпадает с файлами шрифтов"


def test_ticket_files_still_not_a_static_mount(temp_db, app_client):
    resp = app_client.get("/ticket_files")
    assert resp.status_code == 404
    nested = app_client.get("/ticket_files/anything")
    assert nested.status_code == 404


def test_public_ref_fallback_keeps_strict_csp(temp_db, app_client):
    resp = app_client.get("/ref/not-a-number")
    assert resp.status_code == 200
    csp = resp.headers.get("content-security-policy", "")
    assert "script-src 'self'" in csp
    assert "default-src 'none'" in csp
    assert "https://telegram.org" not in csp


def test_json_api_does_not_inherit_html_csp(temp_db, app_client):
    resp = app_client.get("/openapi.json")
    assert resp.status_code == 200
    assert "content-security-policy" not in {k.lower() for k in resp.headers.keys()}
