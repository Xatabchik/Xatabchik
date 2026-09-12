"""Лимитер попыток email-аутентификации по адресу.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


from fastapi.responses import JSONResponse
import time
from collections import deque


def _email_auth_rate_limit_response() -> JSONResponse:
    return JSONResponse(
        {
            "ok": False,
            "error": f"Rate limit exceeded: {EMAIL_AUTH_PER_EMAIL_LIMIT} per 1 minute",
        },
        status_code=429,
    )


def _email_auth_rate_limited(email: str) -> bool:
    """True, если по этому email уже исчерпан EMAIL_AUTH_PER_EMAIL_LIMIT за окно."""
    key = (email or "").strip().lower()
    if not key:
        return False
    now = time.time()
    window = float(EMAIL_AUTH_PER_EMAIL_WINDOW_SECONDS)
    limit = int(EMAIL_AUTH_PER_EMAIL_LIMIT)
    with _EMAIL_AUTH_HITS_LOCK:
        q = _EMAIL_AUTH_HITS.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def _reject_if_email_auth_rate_limited(email: str) -> JSONResponse | None:
    if _email_auth_rate_limited(email):
        return _email_auth_rate_limit_response()
    return None


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_email_auth_rate_limit_response",
    "_email_auth_rate_limited",
    "_reject_if_email_auth_rate_limited",
]
