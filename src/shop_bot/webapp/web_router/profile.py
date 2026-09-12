"""Профиль: смена пароля и адреса почты.

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


from datetime import datetime


@app.post("/api/user/profile-info")
async def api_user_profile_info(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    auth_email = user.get("auth_email") or None
    return {
        "ok": True,
        "has_email_auth": bool(auth_email),
        "auth_email": auth_email,
        "email_verified": bool(user.get("email_verified")),
        "pending_email": user.get("pending_email") or None,
    }


@app.post("/api/user/profile/change-password")
async def api_user_profile_change_password(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    if not user.get("auth_email"):
        return {"ok": False, "error": "Смена пароля доступна только для аккаунтов с входом по email"}

    current_password = str(data.get("current_password") or "")
    new_password = str(data.get("new_password") or "")

    from shop_bot.data_manager import database
    if not database.verify_password(current_password, user.get("auth_pass")):
        return {"ok": False, "error": "Неверный текущий пароль"}

    pw_err = _validate_password(new_password)
    if pw_err:
        return {"ok": False, "error": pw_err}

    if not database.update_user_password_by_id(user["telegram_id"], new_password):
        return {"ok": False, "error": "Ошибка базы данных"}
    return {"ok": True, "message": "Пароль изменён"}


@app.post("/api/user/profile/change-email/request")
async def api_user_profile_change_email_request(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}
    if not user.get("auth_email"):
        return {"ok": False, "error": "Смена email доступна только для аккаунтов с входом по email"}

    password = str(data.get("password") or "")
    new_email = str(data.get("new_email") or "").strip().lower()

    from shop_bot.data_manager import database
    if not database.verify_password(password, user.get("auth_pass")):
        return {"ok": False, "error": "Неверный пароль"}

    if not new_email or not _EMAIL_FORMAT_RE.match(new_email):
        return {"ok": False, "error": "Некорректный формат email"}
    if new_email == (user.get("auth_email") or "").strip().lower():
        return {"ok": False, "error": "Это и есть ваш текущий email"}

    existing = database.get_user_by_email(new_email)
    if existing and existing["telegram_id"] != user["telegram_id"]:
        return {"ok": False, "error": "Этот email уже используется другим аккаунтом"}

    if not database.set_pending_email(user["telegram_id"], new_email):
        return {"ok": False, "error": "Ошибка базы данных"}

    ok, err = await _issue_email_verification_code(user["telegram_id"], new_email)
    if not ok:
        database.clear_pending_email(user["telegram_id"])
        return {"ok": False, "error": err}
    return {"ok": True, "message": f"Код подтверждения отправлен на {new_email}"}


@app.post("/api/user/profile/change-email/resend")
async def api_user_profile_change_email_resend(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    from shop_bot.data_manager import database
    pending_email = user.get("pending_email")
    if not pending_email:
        return {"ok": False, "error": "Нет ожидающей смены email"}

    info = database.get_email_verification(user["telegram_id"]) or {}
    last_sent_raw = info.get("email_code_last_sent_at")
    if last_sent_raw:
        try:
            last_sent = datetime.strptime(str(last_sent_raw), "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < EMAIL_RESEND_COOLDOWN_SECONDS:
                return {
                    "ok": False,
                    "error": f"Подождите {int(EMAIL_RESEND_COOLDOWN_SECONDS - elapsed)} сек. перед повторной отправкой",
                    "retry_after": int(EMAIL_RESEND_COOLDOWN_SECONDS - elapsed),
                }
        except Exception:
            pass

    ok, err = await _issue_email_verification_code(user["telegram_id"], pending_email)
    if not ok:
        return {"ok": False, "error": err}
    return {"ok": True}


@app.post("/api/user/profile/change-email/verify")
async def api_user_profile_change_email_verify(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    from shop_bot.data_manager import database
    if not user.get("pending_email"):
        return {"ok": False, "error": "Нет ожидающей смены email"}

    code = str(data.get("code") or "").strip()
    if not code or not database.check_email_verification_code(user["telegram_id"], code):
        return {"ok": False, "error": "Неверный или устаревший код"}

    ok, result = database.finalize_pending_email_change(user["telegram_id"])
    if not ok:
        return {"ok": False, "error": result}
    return {"ok": True, "message": "Email изменён", "auth_email": result}


@app.post("/api/user/profile/change-email/cancel")
async def api_user_profile_change_email_cancel(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _resolve_user_from_request_token(data, request)
    if not user:
        return {"ok": False, "error": "Unauthorized"}

    from shop_bot.data_manager import database
    database.clear_pending_email(user["telegram_id"])
    return {"ok": True}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_user_profile_info",
    "api_user_profile_change_password",
    "api_user_profile_change_email_request",
    "api_user_profile_change_email_resend",
    "api_user_profile_change_email_verify",
    "api_user_profile_change_email_cancel",
]
