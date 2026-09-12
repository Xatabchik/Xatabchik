"""Сводка по реферальной программе для пользователя.

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


from shop_bot.data_manager.remnawave_repository import get_setting, get_referral_count


import shop_bot.data_manager.remnawave_repository as rw_repo


@app.post("/api/user/referral-info")
async def api_user_referral_info(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _require_authenticated_user(request, data=data)
    if not user:
        return _unauthorized()

    uid = user["telegram_id"]
    bot_username = get_setting("telegram_bot_username") or ""
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")
    bot_link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else ""
    webapp_link = f"{webapp_domain}/ref/{uid}" if webapp_domain else ""
    share_text = (get_setting("referral_share_text") or "").strip() or (
        "🌐Обход глушилок и блокировок на любом устройстве! 😊"
    )

    from shop_bot.data_manager.remnawave_repository import get_referral_count
    count = get_referral_count(uid)
    earned = float(user.get("referral_balance_all") or 0)
    available = float(user.get("referral_balance") or 0)

    return {
        "ok": True,
        "bot_link": bot_link,
        "webapp_link": webapp_link,
        "share_text": share_text,
        "count": count,
        "earned": earned,
        "available": available,
        "has_open_request": rw_repo.has_open_referral_withdrawal_request(uid),
    }


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_user_referral_info",
]
