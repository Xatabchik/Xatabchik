"""Создание FastAPI-приложения, middleware и монтирование статики.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.

Пути к шаблонам и статике считаются от `__file__` на один каталог выше,
чем в исходнике: файл переехал в подпакет, а каталог `webapp/` остался
прежним. Это единственное место, где текст определений изменён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._core import limiter


from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import os
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def _webapp_no_cache_middleware(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=86400")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response
    content_type = response.headers.get("content-type", "")
    if path == "/" or content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        if "content-security-policy" not in response.headers:
            # Имя из _core через _link_namespace(), не значением: на импорте не нужно.
            response.headers["Content-Security-Policy"] = _WEBAPP_PAGE_CSP
    return response


ico_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "module", "ico")
if os.path.exists(ico_dir):
    app.mount("/module/ico", StaticFiles(directory=ico_dir), name="ico")

uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _hidden_not_found() -> None:
    """Как несуществующий URL: стандартный FastAPI 404, без Unauthorized."""
    raise HTTPException(status_code=404)


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "app",
    "_webapp_no_cache_middleware",
    "ico_dir",
    "uploads_dir",
    "static_dir",
    "_hidden_not_found",
]
