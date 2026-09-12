"""Публичные страницы /ref и /gift и catch-all.

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
from shop_bot.webapp.web_router._app import app


from fastapi import Request


from fastapi.responses import HTMLResponse, RedirectResponse


from shop_bot.data_manager.remnawave_repository import get_setting, get_webapp_settings


import os


from datetime import datetime


import html


def _html_esc(value) -> str:
    """Экранировать значение для вставки в HTML-текст или атрибут (CWE-79)."""
    return html.escape("" if value is None else str(value), quote=True)


def _public_fallback_response(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        content=content,
        status_code=status_code,
        headers={"Content-Security-Policy": _PUBLIC_FALLBACK_CSP},
    )


def _parse_public_referrer_id(referrer_id: str) -> int | None:
    """Только положительный int. Невалидный path не должен попадать в HTML/URL."""
    try:
        rid = int(str(referrer_id).strip())
    except (TypeError, ValueError):
        return None
    if rid <= 0:
        return None
    return rid


def _safe_public_gift_code(gift_code: str | None) -> str | None:
    raw = (gift_code or "").strip()
    if _GIFT_CODE_RE.fullmatch(raw):
        return raw
    return None


def _telegram_bot_deeplink(bot_username: str, start_payload: str | None = None) -> str:
    user = (bot_username or "").strip()
    if not user:
        return ""
    if start_payload:
        return f"https://t.me/{user}?start={start_payload}"
    return f"https://t.me/{user}"


def _html_telegram_btn(deeplink: str, label: str) -> str:
    if not deeplink:
        return ""
    return f"<a class='btn' href='{_html_esc(deeplink)}'>{_html_esc(label)}</a>"


def _referral_fallback_html(project_name: str, logo_url: str, deeplink: str, error_note: str = "") -> str:
    """Резервная страница рефссылки (реферер не найден/бот не настроен) —
    без единого сценария pending action, просто ссылка в Telegram, как раньше."""
    name = _html_esc(project_name)
    note = _html_esc(
        error_note or "Вас пригласили воспользоваться VPN-сервисом. Нажмите кнопку ниже, чтобы начать через Telegram."
    )
    logo = _html_esc(logo_url) if logo_url else ""
    logo_html = f"<img class='logo' src='{logo}' alt='logo'>" if logo else ""
    if deeplink and not error_note:
        action_html = _html_telegram_btn(deeplink, "Открыть в Telegram")
    elif error_note and not deeplink:
        action_html = "<p style='color:#f87171'>Бот не настроен.</p>"
    else:
        action_html = ""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — Реферальная ссылка</title>
<style>body{{margin:0;background:#0d0d0d;color:#fff;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#1a1a1a;border:1px solid rgba(255,255,255,.08);border-radius:2rem;padding:2.5rem;max-width:360px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
h2{{margin:.5rem 0 .25rem;font-size:1.3rem}} p{{color:#aaa;font-size:.85rem;margin:.75rem 0 1.5rem}}
.btn{{display:block;background:#fff;color:#000;font-weight:700;text-decoration:none;padding:.9rem 1.5rem;border-radius:1rem;font-size:.875rem;text-transform:uppercase;letter-spacing:.05em;transition:.2s}}
.btn:hover{{opacity:.85}} img.logo{{width:72px;height:72px;border-radius:1rem;margin-bottom:1rem;object-fit:contain}}</style></head>
<body><div class="card">
{logo_html}
<h2>{name}</h2>
<p>{note}</p>
{action_html}
</div></body></html>"""


@app.get("/ref/{referrer_id}")
async def web_referral_page(referrer_id: str, request: Request):
    """Публичная реферальная ссылка.

    Раньше эта страница всегда вела только в Telegram (deep link), даже если
    пользователь предпочёл бы войти по email. Теперь: если referrer_id
    настоящий, создаём серверный pending action (единый сценарий — см.
    /api/webapp/pending-actions/*) и ведём на общий вход, где пользователь сам
    выбирает Telegram или email; после успешного входа привязка реферала
    применяется автоматически ровно один раз.
    """
    try:
        bot_username = get_setting("telegram_bot_username") or ""
        webapp_settings = get_webapp_settings()
        project_name = (
            webapp_settings.get("webapp_title")
            or webapp_settings.get("project_name")
            or get_setting("panel_brand_title")
            or "VPN Bot"
        )
        logo_url = webapp_settings.get("webapp_logo") or ""

        rid = _parse_public_referrer_id(referrer_id)
        if rid is None:
            # Невалидный path не отражаем в HTML/deeplink (CWE-79).
            deeplink = _telegram_bot_deeplink(bot_username)
            return _public_fallback_response(
                _referral_fallback_html(project_name, logo_url, deeplink)
            )

        deeplink = _telegram_bot_deeplink(bot_username, f"ref_{rid}")
        # Не проверяем существование telegram_id здесь: разный статус/pending_token
        # для известного и неизвестного id даёт оракул. Привязка реферера
        # валидируется позже в complete (invalid_referrer).
        from shop_bot.data_manager import database
        token = database.create_pending_action("referral", referrer_id=rid)
        if not token:
            return _public_fallback_response(
                _referral_fallback_html(project_name, logo_url, deeplink)
            )

        return RedirectResponse(url=f"/?pending_token={token}", status_code=302)
    except Exception as e:
        logger.error(f"Referral page error: {e}")
        return _public_fallback_response("<h1>Error</h1>", status_code=500)


def _gift_fallback_html(project_name: str, logo_url: str, title: str, desc: str, action_html: str = "") -> str:
    """Резервная страница подарка (не найден/уже активирован) — как и раньше,
    без pending action, потому что действие в этих случаях всё равно не имеет смысла."""
    name = _html_esc(project_name)
    safe_title = _html_esc(title)
    safe_desc = _html_esc(desc)
    logo = _html_esc(logo_url) if logo_url else ""
    logo_html = f"<img class='logo' src='{logo}' alt='logo'>" if logo else "<div class='gift-icon'>🎁</div>"
    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — {safe_title}</title>
<style>body{{margin:0;background:#0d0d0d;color:#fff;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#1a1a1a;border:1px solid rgba(255,255,255,.08);border-radius:2rem;padding:2.5rem;max-width:360px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
h2{{margin:.5rem 0 .25rem;font-size:1.3rem}} p{{color:#aaa;font-size:.85rem;margin:.75rem 0 1.5rem}}
.btn{{display:inline-block;background:#fff;color:#000;font-weight:700;text-decoration:none;padding:.9rem 1.5rem;border-radius:1rem;font-size:.875rem;text-transform:uppercase;letter-spacing:.05em;transition:.2s;cursor:pointer;border:none;width:100%;box-sizing:border-box}}
.btn:hover{{opacity:.85}} img.logo{{width:72px;height:72px;border-radius:1rem;margin-bottom:1rem;object-fit:contain}}
.gift-icon{{font-size:3rem;margin-bottom:.5rem}}</style></head>
<body><div class="card">
{logo_html}
<h2>{safe_title}</h2>
<p>{safe_desc}</p>
{action_html}
</div></body></html>"""


@app.get("/gift/{gift_code}")
async def web_gift_page(gift_code: str, request: Request):
    """Публичная ссылка активации подарка.

    Раньше уже авторизованный (по cookie/`?token=`) посетитель мог активировать
    подарок прямо со страницы, а неавторизованный — только через Telegram deep
    link. Теперь для валидного, ещё не активированного подарка мы создаём
    серверный pending action и ведём на единый вход (Telegram ИЛИ email);
    страница активации внутри приложения (`/?pending_token=...`) сама решает,
    показывать ли экран входа или сразу применить действие — в зависимости от
    того, авторизован ли пользователь.
    Невалидные случаи (подарок не найден / уже активирован) обрабатываются как
    раньше — без создания pending action, отдельной простой страницей.
    """
    try:
        from shop_bot.data_manager.remnawave_repository import get_gift_by_code
        bot_username = get_setting("telegram_bot_username") or ""
        webapp_settings = get_webapp_settings()
        project_name = (
            webapp_settings.get("webapp_title")
            or webapp_settings.get("project_name")
            or get_setting("panel_brand_title")
            or "VPN Bot"
        )
        logo_url = webapp_settings.get("webapp_logo") or ""

        safe_code = _safe_public_gift_code(gift_code)
        gift = get_gift_by_code(safe_code) if safe_code else None
        if bot_username and safe_code:
            deeplink = _telegram_bot_deeplink(bot_username, f"gift_{safe_code}")
        else:
            deeplink = _telegram_bot_deeplink(bot_username)

        if not gift:
            action_html = _html_telegram_btn(deeplink, "Открыть в Telegram")
            return _public_fallback_response(_gift_fallback_html(
                project_name, logo_url, "Подарочный ключ", "Активируйте подарок через Telegram.", action_html
            ))
        if gift.get("is_activated"):
            return _public_fallback_response(_gift_fallback_html(
                project_name, logo_url, "Подарок уже активирован", "Этот подарочный ключ уже был использован."
            ))

        expires_at = gift.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(str(expires_at)) < datetime.utcnow():
                    return _public_fallback_response(_gift_fallback_html(
                        project_name, logo_url, "Срок действия истёк", "Срок действия этого подарка истёк."
                    ))
            except Exception:
                pass

        from shop_bot.data_manager import database
        token = database.create_pending_action("gift", gift_code=safe_code)
        if not token:
            action_html = _html_telegram_btn(deeplink, "Активировать в Telegram")
            return _public_fallback_response(_gift_fallback_html(
                project_name, logo_url, "Подарочный VPN-ключ",
                "Нажмите кнопку ниже, чтобы активировать подарок в Telegram.", action_html
            ))

        return RedirectResponse(url=f"/?pending_token={token}", status_code=302)
    except Exception as e:
        logger.error(f"Gift page error: {e}")
        return _public_fallback_response("<h1>Error</h1>", status_code=500)


@app.get("/{path_param}")
async def dynamic_route(request: Request, path_param: str):
    try:
        if path_param.startswith("token="):
            token = path_param.split("=")[1]
            from shop_bot.data_manager import database
            user = database.get_user_by_auth_token(token)
            if user:
                webapp_settings = get_webapp_settings()
                if user.get('is_banned'):
                    return _render_banned_page(webapp_settings)
                return await _render_main_page(user['telegram_id'])
            else:
                 # Token not valid or expired -> Render Login Page
                 p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "login.html")
                 if os.path.exists(p):
                     with open(p, "r", encoding="utf-8") as f:
                         content = f.read()
                     
                     webapp_settings = get_webapp_settings()
                     context = {
                        "webapp_logo": webapp_settings.get("webapp_logo") or "",
                        "webapp_icon": webapp_settings.get("webapp_icon") or ""
                     }
                     content = _process_template_placeholders(content, 0, webapp_settings, context)
                     return HTMLResponse(content=content)
                 else:
                     return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)
        
        # Pass through to 404 naturally or handle other dynamic routes
        return HTMLResponse(content="<h1>404 Not Found</h1>", status_code=404)
    except Exception as e:
        logger.error(f"Dynamic route error: {e}")
        return HTMLResponse(content="<h1>Error</h1>", status_code=500)


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_html_esc",
    "_public_fallback_response",
    "_parse_public_referrer_id",
    "_safe_public_gift_code",
    "_telegram_bot_deeplink",
    "_html_telegram_btn",
    "_referral_fallback_html",
    "web_referral_page",
    "_gift_fallback_html",
    "web_gift_page",
    "dynamic_route",
]
