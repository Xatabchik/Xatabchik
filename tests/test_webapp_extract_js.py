"""Этап 2 PR 1: JS Mini App вынесен в /static/js/app.js без смены поведения."""
from __future__ import annotations

import re
from pathlib import Path

from webapp_frontend_src import (
    API_JS,
    APP_HTML,
    APP_JS,
    STORE_JS,
    TELEGRAM_JS,
    UI_JS,
    mini_app_frontend_source,
    mini_app_html,
    mini_app_js,
    mini_app_keys_page_js,
)

WEBAPP = Path("src/shop_bot/webapp")
BRIDGE_NAMES = (
    "setPurchaseMode",
    "openActionModal",
    "closeActionModal",
    "loadTransactions",
    "changeProfileKeysPage",
    "copyToClipboard",
    "activateOwnGift",
    "changeGiftsPage",
    "syncTelegram",
    "goToRenewKey",
    "toggleKeyAutoRenew",
    "openLteTopup",
)


def test_app_html_no_longer_contains_monolithic_body_javascript():
    html = mini_app_html()
    scripts = re.findall(r"<script\b([^>]*)>(.*?)</script>", html, flags=re.S)
    inline = [src for attrs, src in scripts if "src=" not in attrs]
    assert len(inline) == 1, "в app.html должен остаться только head-bootstrap"
    boot = inline[0]
    assert "window.apiFetch" in boot
    assert "window.setAuthToken" in boot
    assert 'parseInt("{{ user_id }}")' in boot
    assert "function openTopUpModal" not in html
    assert "function telegramVersionAtLeast" not in html
    assert "function initApp" not in html
    assert 'src="{{ store_js_href }}" defer>' in html
    assert 'src="{{ transactions_js_href }}" defer>' in html
    assert 'src="{{ keys_page_js_href }}" defer>' in html
    assert 'src="{{ app_js_href }}" defer>' in html
    assert html.index('src="{{ store_js_href }}" defer>') < html.index(
        'src="{{ transactions_js_href }}" defer>'
    )
    assert html.index('src="{{ transactions_js_href }}" defer>') < html.index(
        'src="{{ keys_page_js_href }}" defer>'
    )
    assert html.index('src="{{ keys_page_js_href }}" defer>') < html.index(
        'src="{{ app_js_href }}" defer>'
    )
    assert 'type="module"' not in html
    assert "cdn.tailwindcss.com" not in html
    assert "eval(" not in html
    assert "new Function" not in html


def test_entrypoint_and_helper_modules_exist_and_are_local():
    assert APP_JS.is_file()
    assert STORE_JS.is_file()
    assert TELEGRAM_JS.is_file()
    assert UI_JS.is_file()
    assert API_JS.is_file()
    app_js = mini_app_js()
    telegram = TELEGRAM_JS.read_text(encoding="utf-8")
    ui = UI_JS.read_text(encoding="utf-8")
    api = API_JS.read_text(encoding="utf-8")
    assert "function telegramVersionAtLeast(" in telegram
    assert "function safeTelegramAppearance(" in telegram
    assert "function safeTelegramHaptic(" in telegram
    assert "function telegramPopupSupported(" in ui
    assert "function showLocalToast(" in ui
    assert "function safeTelegramPopup(" in ui
    assert "function showNotification(" in ui
    assert "apiFetch" in api
    assert "function telegramVersionAtLeast(" in app_js
    assert "function showLocalToast(" in app_js
    assert "function openTopUpModal(" in app_js
    assert "async function saveComment(" in app_js
    assert "function restorePendingPayment(" in app_js
    assert "eval(" not in app_js
    assert "new Function" not in app_js
    assert "cdn.tailwindcss.com" not in app_js
    assert "https://" not in telegram
    assert app_js.strip().endswith("initApp();\n}") or "initApp();" in app_js[-200:]


def test_legacy_inline_handler_bridges_are_gone():
    app_js = mini_app_js()
    keys_js = mini_app_keys_page_js()
    assert "Temporary compatibility bridge for legacy inline handlers in app.html." not in app_js
    assert "Temporary compatibility bridge" not in app_js
    for name in BRIDGE_NAMES:
        assert f"window.{name} = {name};" not in app_js, name
        assert f"window.{name} = {name};" not in keys_js, name


def test_auth_and_payment_contracts_were_not_rewritten():
    frontend = mini_app_frontend_source()
    html = mini_app_html()
    js = mini_app_js()
    assert "window.apiFetch = function (url, options)" in html
    assert "headers['Authorization'] = 'Bearer ' + token;" in html
    assert "url.searchParams.delete('token')" in html
    assert "function restorePendingPayment(" in js
    assert "function openTopUpModal(" in js
    assert "/api/check-payment" in js
    assert "/api/create-lte-topup-payment" in frontend
    assert "location.reload()" in js
    assert "pendingPayment" in js
    assert "pendingTopUp" in js


def test_inline_onclick_names_still_present_in_templates():
    html = mini_app_html()
    keys = (WEBAPP / "web_router" / "render_keys.py").read_text(encoding="utf-8")
    plans = (WEBAPP / "web_router" / "render_plans.py").read_text(encoding="utf-8")
    assert 'onclick="navigateTo(' not in html
    assert 'onclick="openTopUpModal()"' not in html
    assert 'onclick="processPayment()"' not in html
    assert 'onclick="closePaymentModal()"' not in html
    assert 'onclick="requestReferralWithdraw()' not in html
    assert 'onclick="copyKey' not in html  # copy goes through data-key-action
    assert 'oninput="onKeysSearchInput()' not in html
    assert 'onclick="clearKeysSearch()' not in html
    assert 'onclick="switchKeysTab(' not in html
    assert 'onclick="deleteDevice' not in html
    assert 'onclick="deleteAllDevices' not in html
    assert 'onclick="toggleSettingsMenu' not in html
    assert 'onclick="openEditProfileModal' not in html
    assert 'onclick="createSupportTicket' not in html
    assert 'onclick="sendSupportMessage' not in html
    assert 'onclick="closeSupportTicket' not in html
    assert 'onclick="resetSupportChat' not in html
    assert 'onclick="_submitProfileChangePassword' not in html
    assert 'onclick="_submitProfileChangeEmailRequest' not in html
    assert 'onclick="_loadProfileMain' not in html
    assert 'onclick="requestReferralWithdraw()' not in html
    assert 'onclick="openReferralMethodsModal()' not in html
    assert 'onclick="setPurchaseMode(' not in html
    assert 'onclick="openActionModal(' not in html
    assert 'onclick="closeActionModal(' not in html
    assert 'onclick="toggleInfoBlock(' not in html
    assert 'onclick="toggleRenewInfoBlock(' not in html
    assert 'onclick="selectPlan(' not in html
    assert 'onclick="goToRenewKey(' not in keys
    assert 'onclick="toggleKeyAutoRenew(' not in keys
    assert 'onclick="openLteTopup(' not in keys
    assert 'onclick="syncTelegram(' not in keys
    assert 'onclick="selectPlan(' not in plans
    assert 'onclick="selectServer(' not in plans
    assert 'data-key-action="renew"' in keys
    assert 'data-key-action="auto-renew"' in keys
    assert 'data-key-action="lte-topup"' in keys
    assert 'data-sync-telegram="1"' in keys
    assert "class=\"plan-btn " in plans or 'class="plan-btn' in plans
    assert 'class="server-option ' in plans
    assert "onclick=" not in html
