"""
Отправка писем с кодом активации email (подтверждение адреса при веб-регистрации).

Настройки SMTP берутся из общей таблицы bot_settings (см. панель администратора,
раздел «Настройки» → «Email / SMTP»): smtp_host, smtp_port, smtp_user, smtp_password,
smtp_from_email, smtp_use_tls.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.utils import formataddr

from shop_bot.data_manager.database import get_setting

logger = logging.getLogger(__name__)

# Известные провайдеры, у которых обычная учётная запись почты недостаточна для
# SMTP-авторизации — им требуется отдельный «пароль для внешних приложений».
_APP_PASSWORD_HINTS = {
    "mail.ru": "Mail.ru требует отдельный «пароль для внешних приложений» "
                "(Настройки почты → Пароль для внешних приложений), обычный пароль от аккаунта не подойдёт.",
    "yandex.ru": "Yandex почта требует «пароль приложения» при включённой двухфакторной аутентификации.",
    "gmail.com": "Gmail требует «пароль приложения» (App Password) — обычный пароль аккаунта Google не подходит, "
                 "также нужно включить двухфакторную аутентификацию.",
}


def _get_smtp_settings() -> dict:
    host = (get_setting("smtp_host") or "").strip()
    port_raw = (get_setting("smtp_port") or "587").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    user = (get_setting("smtp_user") or "").strip()
    password = get_setting("smtp_password") or ""
    from_email = (get_setting("smtp_from_email") or user).strip()
    use_tls_raw = (get_setting("smtp_use_tls") or "true").strip().lower()
    use_tls = use_tls_raw in ("1", "true", "yes", "on")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "use_tls": use_tls,
    }


def _auth_hint_for_host(host: str) -> str:
    host_lower = (host or "").lower()
    for domain, hint in _APP_PASSWORD_HINTS.items():
        if domain in host_lower:
            return hint
    return "Проверьте логин/пароль в настройках SMTP и убедитесь, что для аккаунта разрешён доступ по SMTP."


def is_smtp_configured() -> bool:
    """Проверить, заполнены ли минимально необходимые настройки SMTP."""
    settings = _get_smtp_settings()
    return bool(settings["host"] and settings["user"] and settings["password"])


def send_activation_code(to_email: str, code: str) -> bool:
    """Отправить письмо с одноразовым кодом активации email.

    Возвращает True при успешной отправке, False в случае любой ошибки
    (ошибка подробно логируется, но не поднимается наружу, чтобы не ронять запрос).
    """
    settings = _get_smtp_settings()

    if not settings["host"] or not settings["user"] or not settings["password"]:
        logger.error(
            "SMTP не настроен (host/user/password пустые) — не удалось отправить код активации на %s. "
            "Заполните настройки Email/SMTP в админ-панели.",
            to_email,
        )
        return False

    subject = "Код подтверждения email"
    body = (
        f"Ваш код подтверждения: {code}\n\n"
        f"Код действителен 10 минут. Если вы не запрашивали регистрацию — просто игнорируйте это письмо."
    )

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = formataddr(("Xatabchik", settings["from_email"] or settings["user"]))
    message["To"] = to_email

    host = settings["host"]
    port = settings["port"]

    try:
        if port == 465:
            # Порт 465 — implicit TLS (SMTPS), STARTTLS здесь не нужен/не поддерживается.
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=15, context=context) as server:
                server.login(settings["user"], settings["password"])
                server.sendmail(settings["user"], [to_email], message.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if settings["use_tls"]:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(settings["user"], settings["password"])
                server.sendmail(settings["user"], [to_email], message.as_string())
        return True
    except smtplib.SMTPAuthenticationError as e:
        hint = _auth_hint_for_host(host)
        logger.error(
            "Не удалось отправить письмо активации на %s: SMTP-сервер отклонил логин/пароль (%s). %s",
            to_email, e, hint,
        )
        return False
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, ConnectionError, TimeoutError, OSError) as e:
        logger.error(
            "Не удалось отправить письмо активации на %s: не удалось подключиться к SMTP-серверу %s:%s (%s). "
            "Проверьте адрес/порт сервера и доступность сети из контейнера.",
            to_email, host, port, e,
        )
        return False
    except Exception as e:
        logger.error("Не удалось отправить письмо активации на %s: %s", to_email, e)
        return False
