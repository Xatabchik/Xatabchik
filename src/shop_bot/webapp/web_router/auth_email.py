"""Регистрация, подтверждение, вход и сброс пароля по email.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router._core import AUTH_RATE_LIMIT, limiter
from shop_bot.webapp.web_router.models import (
    EmailAuthRequest,
    EmailResendRequest,
    EmailVerifyRequest,
    PasswordResetCheckRequest,
    PasswordResetRequest,
    PasswordResetVerifyRequest,
)


from fastapi import Request


from datetime import datetime


import uuid


import asyncio


import time


async def _issue_email_verification_code(user_id: int, email: str) -> tuple[bool, str | None]:
    """Сгенерировать, сохранить и отправить новый код подтверждения email.

    Возвращает (ok, error). Не поднимает исключения наружу.

    Отправка письма (блокирующий вызов smtplib, может делать несколько попыток
    с паузами при сетевых сбоях) выполняется в отдельном потоке через
    `asyncio.to_thread`, чтобы не блокировать event loop на время ожидания/повторов.
    """
    import random
    from shop_bot.data_manager import database
    from shop_bot.modules.email_sender import send_activation_code, is_smtp_configured

    if not is_smtp_configured():
        logger.error("Попытка отправить код активации email, но SMTP не настроен в админ-панели.")
        return False, "Отправка писем временно недоступна. Попробуйте позже или обратитесь в поддержку."

    code = f"{random.randint(0, 999999):06d}"
    if not database.set_email_verification_code(user_id, code, ttl_seconds=EMAIL_CODE_TTL_SECONDS):
        return False, "Ошибка базы данных"

    try:
        sent = await asyncio.to_thread(send_activation_code, email, code)
    except Exception as e:
        logger.error(f"Unexpected error while sending activation code to {email}: {e}")
        sent = False

    if not sent:
        return False, "Не удалось отправить письмо с кодом. Проверьте адрес почты или попробуйте позже."
    return True, None


@app.post("/api/auth/email/register")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_register(request: Request, req: EmailAuthRequest):
    from shop_bot.data_manager import database

    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited

    pw_err = _validate_password(req.password)
    if pw_err:
        return {"ok": False, "error": pw_err}

    existing = database.get_user_by_email(req.email)
    if existing:
        # Тот же ответ, что у новой регистрации — иначе по «Email уже
        # зарегистрирован» можно перебирать занятые адреса.
        return {"ok": True, "requires_verification": True, "email": req.email}

    user = database.create_user_by_email(req.email, req.password)
    if not user:
        return {"ok": False, "error": "Ошибка при регистрации"}

    ok, err = await _issue_email_verification_code(user['telegram_id'], req.email)
    if not ok:
        return {"ok": False, "error": err}

    return {"ok": True, "requires_verification": True, "email": req.email}


@app.post("/api/auth/email/verify")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_verify(request: Request, req: EmailVerifyRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    code = (req.code or "").strip()
    # Не раскрываем, существует ли email. Код обязателен всегда: раньше при
    # email_verified=1 токен выдавался без кода — достаточно было знать адрес.
    if not user or not code or not database.check_email_verification_code(user['telegram_id'], code):
        return {"ok": False, "error": "Неверный или устаревший код"}

    if not database.mark_email_verified(user['telegram_id']):
        return {"ok": False, "error": "Ошибка базы данных"}

    token = str(uuid.uuid4())
    database.update_user_auth_token(user['telegram_id'], token)
    return {"ok": True, "token": token}


@app.post("/api/auth/email/resend")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_resend(request: Request, req: EmailResendRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    if not user or user.get('email_verified'):
        return {"ok": True}

    info = database.get_email_verification(user['telegram_id']) or {}
    last_sent_raw = info.get('email_code_last_sent_at')
    if last_sent_raw:
        try:
            last_sent = datetime.strptime(str(last_sent_raw), "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.utcnow() - last_sent).total_seconds()
            if elapsed < EMAIL_RESEND_COOLDOWN_SECONDS:
                return {"ok": True}
        except Exception:
            pass

    ok, err = await _issue_email_verification_code(user['telegram_id'], req.email)
    if not ok:
        return {"ok": False, "error": err}
    return {"ok": True}


@app.post("/api/auth/email/login")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_login(request: Request, req: EmailAuthRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    if not user or not database.verify_password(req.password, user.get('auth_pass')):
        return {"ok": False, "error": "Неверный email или пароль"}
        
    if user.get('is_banned'):
        return {"ok": False, "error": "Аккаунт заблокирован"}

    if not user.get('email_verified'):
        return {"ok": False, "error": "Email не подтверждён", "email_not_verified": True}

    token = str(uuid.uuid4())
    database.update_user_auth_token(user['telegram_id'], token)
    return {"ok": True, "token": token}


@app.post("/api/auth/email/reset/request")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_reset_request(request: Request, req: PasswordResetRequest):
    from shop_bot.data_manager import database
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    user = database.get_user_by_email(req.email)
    # Всегда один ответ: иначе «Email не найден» / «не синхронизирован»
    # выдают, зарегистрирован ли адрес и привязан ли он к Telegram.
    if not user or database.is_email_only_user(user.get("telegram_id")):
        return {"ok": True}

    import random
    import time
    email_lower = req.email.lower().strip()
    code = str(random.randint(100000, 999999))
    PASSWORD_RESET_TOKENS[email_lower] = {
        "code_hash": _hash_password_reset_code(email_lower, code),
        "expires": time.time() + PASSWORD_RESET_TTL_SECONDS,
    }
    
    try:
        success = await _send_telegram_message(
            user['telegram_id'], 
            f"🔐 <b>Восстановление пароля</b>\n\nВаш код для сброса безопасности:\n<code>{code}</code>\n\n<i>Код действителен 10 минут. Если вы не запрашивали сброс пароля, проигнорируйте это сообщение.</i>"
        )
        if not success:
            PASSWORD_RESET_TOKENS.pop(email_lower, None)
            return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to call _send_telegram_message: {e}")
        PASSWORD_RESET_TOKENS.pop(email_lower, None)
        return {"ok": True}

    return {"ok": True}


@app.post("/api/auth/email/reset/check")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_reset_check(request: Request, req: PasswordResetCheckRequest):
    import time
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    email_lower = req.email.lower().strip()
    if email_lower not in PASSWORD_RESET_TOKENS:
        return {"ok": False, "error": "Код не запрашивался или истёк"}
        
    token_data = PASSWORD_RESET_TOKENS[email_lower]
    if time.time() > token_data["expires"]:
        return {"ok": False, "error": "Код устарел"}
        
    if not _password_reset_code_matches(email_lower, req.code, token_data.get("code_hash")):
        return {"ok": False, "error": "Неверный код"}
        
    return {"ok": True}


@app.post("/api/auth/email/reset/verify")
@limiter.limit(AUTH_RATE_LIMIT)
async def api_email_reset_verify(request: Request, req: PasswordResetVerifyRequest):
    import time
    limited = _reject_if_email_auth_rate_limited(req.email)
    if limited:
        return limited
    email_lower = req.email.lower().strip()
    if email_lower not in PASSWORD_RESET_TOKENS:
        return {"ok": False, "error": "Код не запрашивался или истёк"}
        
    token_data = PASSWORD_RESET_TOKENS[email_lower]
    if time.time() > token_data["expires"]:
        del PASSWORD_RESET_TOKENS[email_lower]
        return {"ok": False, "error": "Код устарел"}
        
    if not _password_reset_code_matches(email_lower, req.code, token_data.get("code_hash")):
        return {"ok": False, "error": "Неверный код"}
        
    from shop_bot.data_manager import database
    pw_err = _validate_password(req.new_password)
    if pw_err:
        return {"ok": False, "error": pw_err}
    if not database.update_user_password(req.email, req.new_password):
        return {"ok": False, "error": "Ошибка базы данных"}
        
    del PASSWORD_RESET_TOKENS[email_lower]
    return {"ok": True}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_issue_email_verification_code",
    "api_email_register",
    "api_email_verify",
    "api_email_resend",
    "api_email_login",
    "api_email_reset_request",
    "api_email_reset_check",
    "api_email_reset_verify",
]
