"""Подарочные ключи: карточки, список, активация.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import GiftActivateRequest


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import get_setting
from datetime import datetime
from urllib.parse import quote


def _gift_link_row_html(label: str, link: str, share_text: str) -> str:
    """Одна строка со ссылкой активации подарка: текст ссылки + копировать + поделиться."""
    safe_link = link.replace("'", "\\'")
    return f"""
    <div class="flex flex-col gap-1 min-w-0">
        <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider px-0.5">{label}</div>
        <div class="flex items-center gap-2 min-w-0">
            <div class="flex-1 min-w-0 bg-black/30 rounded-lg px-3 py-1.5 text-[10px] text-gray-300 font-mono truncate">{link}</div>
            <button onclick="copyToClipboard('{safe_link}', this)" class="shrink-0 bg-primary/20 text-primary rounded-lg p-1.5 hover:bg-primary/30 active:scale-95 transition-all">
                <span class="material-symbols-rounded text-sm">content_copy</span>
            </button>
            <a href="https://t.me/share/url?url={quote(link, safe='')}&text={quote(share_text, safe='')}" target="_blank"
               class="shrink-0 bg-[#0088cc]/20 text-[#00aaff] rounded-lg p-1.5 hover:bg-[#0088cc]/30 active:scale-95 transition-all">
                <span class="material-symbols-rounded text-sm">send</span>
            </a>
        </div>
    </div>"""


def _get_gift_action_block_html(gift_code: str, webapp_link: str, telegram_link: str) -> str:
    """Общий блок для неактивированного подарка: обе ссылки активации
    (webapp + Telegram), каждая со своими кнопками копировать/поделиться,
    и отдельно, с явным отступом, кнопка "Активировать себе" — специально
    подальше от остальных кнопок, чтобы не нажать её случайно."""
    share_text = (get_setting("gift_share_text") or "").strip() or (
        "🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать"
    )
    links_html = "".join(
        _gift_link_row_html(label, link, share_text)
        for label, link in (("Ссылка активации (в приложении)", webapp_link), ("Ссылка активации (в Telegram)", telegram_link))
        if link
    )
    return f"""
         <div class="flex flex-col gap-2 mt-1 pt-2 border-t border-white/5">
             <div class="flex items-center gap-2 bg-amber-500/8 border border-amber-500/20 rounded-xl px-3 py-2">
                 <span class="material-symbols-rounded text-amber-400 text-sm shrink-0">info</span>
                 <span class="text-[9px] text-amber-200/80 leading-relaxed">Подарок ещё не активирован. Активируйте его себе или поделитесь ссылкой, чтобы отдать другому пользователю.</span>
             </div>
             {links_html}
             <div class="mt-3 pt-2 border-t border-dashed border-white/10">
                 <button onclick="activateOwnGift('{gift_code}', this)"
                     class="w-full bg-amber-500 hover:bg-amber-600 text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                     <span class="material-symbols-rounded text-sm">redeem</span>
                     <span>Активировать себе</span>
                 </button>
             </div>
         </div>"""


def _get_gift_fallback_card_html(g: dict, badge_html: str, action_block_html: str) -> str:
    """Карточка подарка на случай, если связанный VPN-ключ не найден (например,
    ещё не успел создаться) — но со всеми теми же полями/кнопками, что и у
    полной карточки, чтобы подарок был полноценно управляемым в любом случае."""
    host_name = g.get("host_name") or "Подарок"
    created_at = (g.get("created_at") or "")[:10]
    return f"""
        <div class="glass-card border border-white/10 rounded-2xl p-3 flex flex-col gap-2 mb-3">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <div class="w-9 h-9 bg-white/5 rounded-xl flex items-center justify-center shrink-0">
                        <span class="material-symbols-rounded text-amber-400 text-lg">card_giftcard</span>
                    </div>
                    <div>
                        <div class="text-xs font-bold text-white">{host_name}</div>
                        <div class="text-[9px] text-gray-500">{created_at}</div>
                    </div>
                </div>
                {badge_html}
            </div>
            {action_block_html}
        </div>"""


@app.post("/api/user/gifts")
async def api_user_gifts(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    user = _require_authenticated_user(request, data=data)
    if not user:
        return _unauthorized()

    uid = user["telegram_id"]
    from shop_bot.data_manager import database
    gifts = database.get_user_inactive_gifts(uid) or []

    bot_username = get_setting("telegram_bot_username") or ""
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")
    gift_share_text = (get_setting("gift_share_text") or "").strip() or (
        "🎁 Получи подарочный VPN ключ! Активируй ссылку и начни использовать"
    )

    # Бейдж "Подарок" на карточке ключа не нужен — карточки уже находятся на
    # отдельной вкладке "Подарочные", подпись была избыточной.
    badge_html = ""

    result = []
    for g in gifts:
        code = g.get("gift_code") or ""
        webapp_link = f"{webapp_domain}/gift/{code}" if webapp_domain else ""
        telegram_link = f"https://t.me/{bot_username}?start=gift_{code}" if bot_username else ""
        # "link" оставлен для обратной совместимости (используется JS-фолбэком) — предпочитаем webapp-ссылку.
        link = webapp_link or telegram_link

        action_block_html = _get_gift_action_block_html(code, webapp_link, telegram_link)

        card_html = None
        key_id = g.get("key_id")
        gift_key = database.get_key_by_id(int(key_id)) if key_id else None
        if gift_key:
            card_html = _get_key_card_html(gift_key, badge_html=badge_html, extra_content_html=action_block_html)
        else:
            card_html = _get_gift_fallback_card_html(g, badge_html, action_block_html)

        result.append({
            "gift_id": g.get("gift_id"),
            "gift_code": code,
            "host_name": g.get("host_name"),
            "created_at": g.get("created_at"),
            "expires_at": g.get("expires_at"),
            "link": link,
            "webapp_link": webapp_link,
            "telegram_link": telegram_link,
            "card_html": card_html,
        })

    return {"ok": True, "gifts": result, "share_text": gift_share_text}


def _activate_gift_for_user(user_id: int, gift_code: str) -> dict:
    """Активировать подарок `gift_code` для пользователя `user_id`.

    Возвращает структурированный результат:
        {"ok": bool, "status": str, "message": str}

    status ∈ {"activated", "already_activated", "not_found", "expired", "error"}.

    Идемпотентность: если ЭТОТ ЖЕ пользователь уже успешно активировал именно
    этот подарок ранее (например, повторный вызов после сетевого сбоя), метод
    возвращает ok=True/status="already_activated" без создания второго ключа
    и без повторного назначения реферала. Если подарок был активирован ДРУГИМ
    пользователем (обычная гонка/чужой подарок) — ok=False.

    Атомарность/защита от гонки обеспечивается на уровне
    database.activate_user_gift (условный UPDATE + проверка rowcount).
    """
    from shop_bot.data_manager import database
    from shop_bot.data_manager import remnawave_repository as rw_repo

    try:
        gift = database.get_gift_by_code(gift_code)
        if not gift:
            return {"ok": False, "status": "not_found", "message": "Подарок не найден или код неверный"}

        if gift.get("is_activated"):
            if int(gift.get("activated_by_user_id") or 0) == int(user_id):
                # Тот же пользователь уже активировал этот подарок — идемпотентный успех.
                return {"ok": True, "status": "already_activated", "message": "Подарок уже активирован на ваш аккаунт."}
            return {"ok": False, "status": "already_activated", "message": "Этот подарок уже был активирован"}

        expires_at = gift.get("expires_at")
        if expires_at:
            try:
                if datetime.fromisoformat(str(expires_at)) < datetime.utcnow():
                    return {"ok": False, "status": "expired", "message": "Срок действия подарка истёк"}
            except Exception:
                pass

        success, activated_gift = database.activate_user_gift(gift_code, user_id)
        if not success:
            # Либо гонка (кто-то другой успел активировать первым), либо подарок
            # истёк/удалён между проверкой и попыткой активации — перечитываем
            # текущее состояние, чтобы дать пользователю точный ответ.
            fresh = database.get_gift_by_code(gift_code) or gift
            if fresh.get("is_activated") and int(fresh.get("activated_by_user_id") or 0) == int(user_id):
                return {"ok": True, "status": "already_activated", "message": "Подарок уже активирован на ваш аккаунт."}
            return {"ok": False, "status": "already_activated" if fresh.get("is_activated") else "error", "message": "Не удалось активировать подарок"}

        # Переназначаем ключ активирующему пользователю (используем существующий сервис,
        # не создаём новый ключ).
        key_id = gift.get("key_id")
        if key_id:
            new_email = rw_repo.generate_key_email_for_user(user_id)
            rw_repo.update_key(key_id, user_id=user_id, email=new_email, tag="")

        # Привязываем реферала от дарителя (если применимо) — используя существующую
        # бизнес-логику/условия (см. set_referred_by_from_gift).
        try:
            from_user_id = int((activated_gift or gift or {}).get("from_user_id") or 0)
            if from_user_id > 0:
                database.set_referred_by_from_gift(user_id, from_user_id)
        except Exception:
            pass

        return {"ok": True, "status": "activated", "message": "Подарок успешно активирован! Ключ добавлен в ваш профиль."}
    except Exception as e:
        logger.error(f"Gift activate error for user {user_id}, gift {gift_code}: {e}")
        return {"ok": False, "status": "error", "message": str(e)}


@app.post("/api/gift/activate")
async def api_gift_activate(req: GiftActivateRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])

        result = _activate_gift_for_user(user_id, req.gift_code)
        if not result["ok"]:
            return {"ok": False, "error": result["message"]}
        return {"ok": True, "message": result["message"]}
    except Exception as e:
        logger.error(f"Gift activate error: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_gift_link_row_html",
    "_get_gift_action_block_html",
    "_get_gift_fallback_card_html",
    "api_user_gifts",
    "_activate_gift_for_user",
    "api_gift_activate",
]
