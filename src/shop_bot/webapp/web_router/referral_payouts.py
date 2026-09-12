"""Реквизиты для выплат по реферальной программе.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app


from fastapi import Request


from shop_bot.data_manager.remnawave_repository import get_setting


import shop_bot.data_manager.remnawave_repository as rw_repo


@app.post("/api/referral/payout-methods/list")
async def api_referral_payout_methods_list(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    try:
        methods = rw_repo.list_referral_payout_methods(user.get("telegram_id"))
        for method in methods:
            method["type_enabled"] = _ref_method_type_enabled(method.get("method_type"))
    except Exception as e:
        logger.error(f"Failed to list referral payout methods: {e}")
        methods = []
    try:
        min_withdraw = float(get_setting("minimum_withdrawal") or 100)
    except Exception:
        min_withdraw = 100.0
    withdraw_enabled = _ref_setting_is_true("referral_withdraw_enabled")
    return {"ok": True, "methods": methods, "min_withdraw": min_withdraw, "withdraw_enabled": withdraw_enabled}


@app.post("/api/referral/payout-methods/add")
async def api_referral_payout_methods_add(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    method_type = (data.get("method_type") or "").strip()
    requisite_value = (data.get("requisite_value") or "").strip()
    bank_name = (data.get("bank_name") or None)
    if not method_type or not requisite_value:
        return {"ok": False, "error": "Заполните все поля"}

    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": False, "error": "Вывод средств временно недоступен."}

    if not _ref_method_type_enabled(method_type):
        return {"ok": False, "error": "Этот способ временно недоступен"}

    ok, msg, new_id = rw_repo.add_referral_payout_method(
        user.get("telegram_id"), method_type, requisite_value, bank_name
    )
    return {"ok": ok, "message": msg, "method_id": new_id}


@app.post("/api/referral/available-method-types")
async def api_referral_available_method_types(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": True, "methods": [], "sbp_banks": []}

    method_configs = [
        {"type": "sbp",       "label": "СБП",         "icon": "phone_android",    "placeholder": "+7 900 000 00 00",     "setting": "referral_withdraw_sbp_enabled"},
        {"type": "card",      "label": "Номер карты",  "icon": "credit_card",      "placeholder": "Номер карты (16 цифр)", "setting": "referral_withdraw_card_enabled"},
        {"type": "usdt_trc20","label": "USDT TRC20",   "icon": "currency_bitcoin", "placeholder": "TRC20 адрес кошелька", "setting": "referral_withdraw_usdt_enabled"},
    ]
    raw_banks = get_setting("referral_withdraw_sbp_banks") or ""
    sbp_banks = [b.strip() for b in raw_banks.split(",") if b.strip()]
    enabled = []
    for m in method_configs:
        if not _ref_setting_is_true(m["setting"]):
            continue
        if m["type"] == "sbp" and not sbp_banks:
            continue
        enabled.append({"type": m["type"], "label": m["label"], "icon": m["icon"], "placeholder": m["placeholder"]})
    return {"ok": True, "methods": enabled, "sbp_banks": sbp_banks}


@app.post("/api/referral/payout-methods/delete")
async def api_referral_payout_methods_delete(request: Request):
    try:
        data = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    if not _ref_setting_is_true("referral_withdraw_enabled"):
        return {"ok": False, "error": "Вывод средств временно недоступен."}

    method_id = data.get("method_id")
    if not method_id:
        return {"ok": False, "error": "Missing method_id"}
    method = rw_repo.get_referral_payout_method(int(method_id), user.get("telegram_id"))
    if not method:
        return {"ok": False, "error": "Method not found"}
    ok, msg = rw_repo.delete_referral_payout_method(int(method_id), user.get("telegram_id"))
    return {"ok": bool(ok), "message": msg, "error": None if ok else msg}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_referral_payout_methods_list",
    "api_referral_payout_methods_add",
    "api_referral_available_method_types",
    "api_referral_payout_methods_delete",
]
