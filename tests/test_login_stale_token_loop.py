"""Цикл GET / -> login.html -> GET / при устаревшем auth_token.

Сервер отдаёт login.html, когда токен из cookie не принят. Если login.html при
сохранённом токене слепо уходит на "/", получается бесконечный цикл (в логах
повторяются `GET /` и `GET /static/css/app.css 304`).
"""
from __future__ import annotations

from pathlib import Path

from conftest import temp_db  # noqa: F401

LOGIN_HTML = Path("src/shop_bot/webapp/login.html")


def test_stale_auth_token_cookie_gets_login_page(app_client):
    app_client.cookies.set("auth_token", "stale-token-not-in-db")
    resp = app_client.get("/")
    assert resp.status_code == 200
    assert "check-token" in resp.text, "ожидалась страница входа"


def test_login_page_redirects_with_saved_token_only_once_per_window():
    html = LOGIN_HTML.read_text(encoding="utf-8")
    guard = html.index("login_redirect_at")
    redirect = html.index('window.location.href = appendPendingToken("/");', guard)
    remove = html.index("removeAuthToken();", redirect)
    assert guard < redirect < remove
    assert "Date.now() - lastTry > 15000" in html
