"""Общий снимок фронтенда Mini App: шаблон + статический entrypoint."""
from __future__ import annotations

from pathlib import Path

WEBAPP = Path("src/shop_bot/webapp")
APP_HTML = WEBAPP / "app.html"
APP_JS = WEBAPP / "static" / "js" / "app.js"
TELEGRAM_JS = WEBAPP / "static" / "js" / "telegram.js"
UI_JS = WEBAPP / "static" / "js" / "ui.js"
API_JS = WEBAPP / "static" / "js" / "api.js"
STORE_JS = WEBAPP / "static" / "js" / "store.js"
TRANSACTIONS_JS = WEBAPP / "static" / "js" / "transactions.js"


def mini_app_html() -> str:
    return APP_HTML.read_text(encoding="utf-8")


def mini_app_js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def mini_app_store_js() -> str:
    return STORE_JS.read_text(encoding="utf-8")


def mini_app_transactions_js() -> str:
    return TRANSACTIONS_JS.read_text(encoding="utf-8")


def mini_app_frontend_source() -> str:
    """HTML + domain JS + app.js: структурные тесты, которые раньше читали только app.html."""
    return mini_app_html() + "\n" + mini_app_transactions_js() + "\n" + mini_app_js()
