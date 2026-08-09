"""Отправка писем со SMTP (используется для активации email при веб-регистрации).

Реализовано на стандартном smtplib + email.mime, без новых pip-зависимостей.
Настройки SMTP берутся из общей таблицы настроек бота (get_setting/update_setting):
    smtp_host        — адрес SMTP-сервера
    smtp_port        — порт SMTP-сервера
    smtp_user        — логин для авторизации на SMTP-сервере
    smtp_password    — пароль для авторизации на SMTP-сервере
    smtp_from_email  — email-адрес отправителя (поле "From")
    smtp_use_tls     — "true"/"false", использовать ли STARTTLS
"""

import logging
import smtplib
from email.mime.text import MIMEText

from shop_bot.data_manager.database import get_setting

logger = logging.getLogger(__name__)


def _smtp_settings() -> dict:
    return {
        "host": (get_setting("smtp_host") or "").strip(),
        "port": (get_setting("smtp_port") or "587").strip(),
        "user": (get_setting("smtp_user") or "").strip(),
        "password": get_setting("smtp_password") or "",
        "from_email": (get_setting("smtp_from_email") or "").strip(),
        "use_tls": str(get_setting("smtp_use_tls") or "true").strip().lower() in ("1", "true", "yes", "on"),
    }


def send_activation_code(to_email: str, code: str) -> bool:
    """Отправить письмо с одноразовым кодом активации email. Возвращает True/False."""
    settings = _smtp_settings()
    if not settings["host"] or not settings["from_email"]:
        logger.error(
            "Отправка письма активации невозможна: не настроены smtp_host/smtp_from_email в панели настроек."
        )
        return False

    subject = "Код подтверждения email"
    body = (
        f"Здравствуйте!\n\n"
        f"Ваш код подтверждения email: {code}\n\n"
        f"Код действителен 15 минут. Если вы не регистрировались в нашем сервисе, "
        f"просто проигнорируйте это письмо."
    )

    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings["from_email"]
    message["To"] = to_email

    try:
        port = int(settings["port"] or 587)
    except (TypeError, ValueError):
        port = 587

    try:
        with smtplib.SMTP(settings["host"], port, timeout=15) as server:
            if settings["use_tls"]:
                server.starttls()
            if settings["user"]:
                server.login(settings["user"], settings["password"])
            server.sendmail(settings["from_email"], [to_email], message.as_string())
        return True
    except Exception as e:
        logger.error(f"Не удалось отправить письмо активации на {to_email}: {e}", exc_info=True)
        return False
