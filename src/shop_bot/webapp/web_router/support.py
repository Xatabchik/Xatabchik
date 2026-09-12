"""Поддержка: тикеты, сообщения, вложения, лимиты.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router._core import SUPPORT_RATE_LIMIT, limiter
from shop_bot.webapp.web_router.models import (
    SupportMessageSendRequest,
    SupportStatusRequest,
    SupportTicketCreateRequest,
    SupportTicketRequest,
)


from fastapi import File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from shop_bot.data_manager.remnawave_repository import get_setting
import os
from datetime import datetime
import html
import time
from collections import deque
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _support_rate_response() -> JSONResponse:
    return JSONResponse(
        {"ok": False, "error": "Слишком много запросов. Подождите минуту."},
        status_code=429,
    )


def _support_user_rate_limited(user_id: int, action: str, limit: int, window: float) -> bool:
    key = f"{int(user_id)}:{action}"
    now = time.time()
    with _SUPPORT_HITS_LOCK:
        q = _SUPPORT_HITS.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def _support_too_fast(user_id: int, min_interval: float | None = None) -> bool:
    if min_interval is None:
        min_interval = SUPPORT_MIN_INTERVAL_SECONDS
    key = f"{int(user_id)}:gap"
    now = time.time()
    with _SUPPORT_HITS_LOCK:
        last = _SUPPORT_LAST.get(key, 0.0)
        if now - last < min_interval:
            return True
        _SUPPORT_LAST[key] = now
        return False


def _clip_support_text(value: str | None, max_len: int) -> str:
    return (value or "").strip()[:max_len]


def _tickets_created_today_count(tickets) -> int:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    n = 0
    for t in tickets or []:
        created = str(t.get("created_at") or "")
        if created.startswith(today):
            n += 1
    return n


def _public_ticket_row(ticket: dict) -> dict:
    return {
        "ticket_id": ticket.get("ticket_id"),
        "subject": ticket.get("subject") or "Обращение без темы",
        "status": ticket.get("status"),
        "updated_at": ticket.get("updated_at"),
    }


def _public_ticket_messages(messages) -> list[dict]:
    from shop_bot.support_bot.ticket_media import public_support_message

    items = []
    for m in messages or []:
        if m.get("sender") == "note":
            continue
        items.append(public_support_message(m))
    return items


def _ticket_owned_by(ticket: dict | None, user_id: int) -> bool:
    if not ticket:
        return False
    try:
        return int(ticket.get("user_id") or 0) == int(user_id)
    except (TypeError, ValueError):
        return False


async def _notify_webapp_support(
    user_id: int,
    ticket: dict,
    *,
    title: str,
    body: str,
) -> None:
    token = get_setting("support_bot_token")
    if not token:
        return
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        try:
            tg_user = await bot.get_chat(user_id)
            username_display = f"@{tg_user.username}" if getattr(tg_user, "username", None) else f"ID {user_id}"
        except Exception:
            username_display = f"ID {user_id}"
        safe_body = html.escape(_clip_support_text(body, 400))
        notification_text = (
            f"{title}\n\n"
            f"👤 <b>USER:</b> (<code>{user_id}</code> - {html.escape(str(username_display))} )\n"
            f"📝 <b>ID тикета:</b> <code>#{ticket.get('ticket_id')}</code>\n"
            f"💬 <b>Тема:</b> <i>{html.escape(str(ticket.get('subject') or 'Без темы')[:64])}</i>\n\n"
            f"💌 Сообщения:\n"
            f"<blockquote>{safe_body}</blockquote>"
        )
        forum_chat_id = ticket.get("forum_chat_id")
        thread_id = ticket.get("message_thread_id")
        if forum_chat_id and thread_id:
            try:
                await bot.send_message(
                    chat_id=int(forum_chat_id),
                    message_thread_id=int(thread_id),
                    text=notification_text,
                )
                return
            except Exception as e:
                logger.warning("Error mirroring webapp support to forum: %s", e)
        admin_ids_str = get_setting("admin_ids") or ""
        admin_ids = [aid.strip() for aid in admin_ids_str.split(",") if aid.strip()]
        for aid in admin_ids:
            try:
                await bot.send_message(
                    chat_id=int(aid),
                    text=notification_text,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin_reply_dm_{ticket.get('ticket_id')}")]
                    ]),
                )
            except Exception:
                pass
    finally:
        await bot.session.close()


@app.post("/api/support/status")
async def api_support_status(req: SupportStatusRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])

        from shop_bot.data_manager.remnawave_repository import get_user_tickets, get_ticket_messages

        tickets = get_user_tickets(user_id) or []
        open_tickets = [t for t in tickets if t.get("status") == "open"]
        payload = {
            "ok": True,
            "has_ticket": False,
            "tickets": [_public_ticket_row(t) for t in tickets],
        }
        if not open_tickets:
            return payload

        ticket = max(open_tickets, key=lambda t: int(t["ticket_id"]))
        payload.update({
            "has_ticket": True,
            "ticket_id": ticket["ticket_id"],
            "subject": ticket.get("subject") or "Обращение без темы",
            "status": ticket.get("status"),
            "messages": _public_ticket_messages(get_ticket_messages(ticket["ticket_id"])),
        })
        return payload
    except Exception as e:
        logger.error(f"Error in support status: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/support/create")
@limiter.limit(SUPPORT_RATE_LIMIT)
async def api_support_create(req: SupportTicketCreateRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        if _support_user_rate_limited(user_id, "create", SUPPORT_CREATE_PER_HOUR, 3600):
            return _support_rate_response()

        from shop_bot.data_manager.remnawave_repository import get_or_create_open_ticket, get_user_tickets

        if _tickets_created_today_count(get_user_tickets(user_id)) >= SUPPORT_CREATE_DAILY_MAX:
            return {"ok": False, "error": "Сегодня слишком много обращений. Напишите в открытый тикет или завтра."}

        subject_text = _clip_support_text(req.subject, 64)
        if not subject_text:
            return {"ok": False, "error": "Тема обращения не может быть пустой"}
            
        ticket_id, created_new = get_or_create_open_ticket(user_id, subject_text)
        
        if not ticket_id:
            return {"ok": False, "error": "Не удалось создать тикет"}
            
        if not created_new:
            return {"ok": False, "error": "У вас уже есть открытый тикет"}

        from shop_bot.data_manager.remnawave_repository import get_ticket

        ticket = get_ticket(ticket_id) or {"ticket_id": ticket_id, "subject": subject_text}
        try:
            await _notify_webapp_support(
                user_id,
                ticket,
                title="🆕 <b>Новое обращение (WebApp)!</b>",
                body="Тикет открыт через веб-приложение.",
            )
        except Exception as e:
            logger.warning("WebApp support notify failed: %s", e)

        return {"ok": True, "ticket_id": ticket_id}
    except Exception as e:
        logger.error(f"Error in support create: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/support/send")
@limiter.limit(SUPPORT_RATE_LIMIT)
async def api_support_send(req: SupportMessageSendRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        if _support_too_fast(user_id) or _support_user_rate_limited(
            user_id, "send", SUPPORT_SEND_PER_MINUTE, 60
        ):
            return _support_rate_response()

        from shop_bot.data_manager.remnawave_repository import (
            add_support_message,
            get_ticket,
            get_ticket_messages,
        )
        ticket = get_ticket(req.ticket_id)
        if not ticket or ticket.get('user_id') != user_id or ticket.get('status') != 'open':
            return {"ok": False, "error": "Тикет не найден или закрыт"}
        text = _clip_support_text(req.message, SUPPORT_TEXT_MAX_LEN)
        if not text:
            return {"ok": False, "error": "Сообщение пустое"}
        if len(get_ticket_messages(req.ticket_id) or []) >= SUPPORT_MAX_MESSAGES_PER_TICKET:
            return {"ok": False, "error": "В тикете слишком много сообщений. Откройте новое обращение."}

        add_support_message(req.ticket_id, sender="user", content=text)
        try:
            await _notify_webapp_support(
                user_id,
                ticket,
                title="📨 <b>Новое сообщение (WebApp)!</b>",
                body=text,
            )
        except Exception as e:
            logger.warning("WebApp support notify failed: %s", e)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error in support send: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/api/support/ticket")
async def api_support_ticket(req: SupportTicketRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        from shop_bot.data_manager.remnawave_repository import get_ticket, get_ticket_messages, get_user_tickets

        ticket = get_ticket(int(req.ticket_id))
        if not _ticket_owned_by(ticket, user_id):
            return {"ok": False, "error": "Тикет не найден"}
        tickets = get_user_tickets(user_id) or []
        return {
            "ok": True,
            "ticket_id": ticket["ticket_id"],
            "subject": ticket.get("subject") or "Обращение без темы",
            "status": ticket.get("status"),
            "messages": _public_ticket_messages(get_ticket_messages(ticket["ticket_id"])),
            "tickets": [_public_ticket_row(t) for t in tickets],
        }
    except Exception as e:
        logger.error("Error in support ticket: %s", e)
        return {"ok": False, "error": str(e)}


@app.post("/api/support/close")
@limiter.limit(SUPPORT_RATE_LIMIT)
async def api_support_close(req: SupportTicketRequest, request: Request):
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        from shop_bot.data_manager.remnawave_repository import get_ticket, set_ticket_status

        ticket = get_ticket(int(req.ticket_id))
        if not _ticket_owned_by(ticket, user_id):
            return {"ok": False, "error": "Тикет не найден"}
        if ticket.get("status") == "closed":
            return {"ok": True, "already": True}
        if not set_ticket_status(int(req.ticket_id), "closed"):
            return {"ok": False, "error": "Не удалось закрыть тикет"}
        try:
            await _notify_webapp_support(
                user_id,
                ticket,
                title="✅ <b>Тикет закрыт (WebApp)</b>",
                body="Пользователь закрыл обращение.",
            )
        except Exception as e:
            logger.warning("WebApp support close notify failed: %s", e)
        return {"ok": True}
    except Exception as e:
        logger.error("Error in support close: %s", e)
        return {"ok": False, "error": str(e)}


@app.get("/api/support/ticket-file/{message_id}")
async def api_support_ticket_file(message_id: int, request: Request, token: str | None = None):
    """Вложение только владельцу. Без сессии и при чужом id — тот же 404, что у несуществующего URL."""
    user = _require_authenticated_user(request, token=token)
    if not user:
        return _hidden_not_found()
    user_id = int(user["telegram_id"])
    from shop_bot.data_manager.database import get_support_message, get_ticket, get_ticket_media_root
    from shop_bot.support_bot.ticket_media import detect_image_kind, expire_ticket_media_if_closed_ttl

    msg = get_support_message(int(message_id))
    if not msg or not msg.get("media"):
        return _hidden_not_found()
    ticket = get_ticket(int(msg["ticket_id"]))
    if not _ticket_owned_by(ticket, user_id):
        return _hidden_not_found()
    try:
        if expire_ticket_media_if_closed_ttl(int(msg["ticket_id"])):
            return _hidden_not_found()
    except Exception:
        logger.exception("TTL webapp ticket file")
        return _hidden_not_found()

    base = os.path.realpath(get_ticket_media_root())
    full = os.path.realpath(os.path.join(base, str(msg["media"])))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        return _hidden_not_found()
    kind = detect_image_kind(full)
    if kind is None:
        return _hidden_not_found()
    _ext, mimetype = kind
    return FileResponse(
        full,
        media_type=mimetype,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "private, no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@app.post("/api/support/upload")
@limiter.limit(SUPPORT_RATE_LIMIT)
async def api_support_upload(
    request: Request,
    file: UploadFile = File(...),
    ticket_id: int = Form(...),
    token: str | None = Form(None),
    caption: str = Form(""),
    init_data: str | None = Form(None),
):
    try:
        user = _require_authenticated_user(request, token=token, init_data=init_data)
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        from shop_bot.data_manager.remnawave_repository import add_support_message, get_ticket
        from shop_bot.support_bot.ticket_media import TICKET_MEDIA_MAX_BYTES, save_ticket_media_bytes

        ticket = get_ticket(int(ticket_id))
        if not _ticket_owned_by(ticket, user_id) or ticket.get("status") != "open":
            return {"ok": False, "error": "Тикет не найден или закрыт"}
        if _support_too_fast(user_id) or _support_user_rate_limited(
            user_id, "upload", SUPPORT_UPLOAD_PER_MINUTE, 60
        ):
            return _support_rate_response()
        from shop_bot.data_manager.remnawave_repository import get_ticket_messages

        if len(get_ticket_messages(int(ticket_id)) or []) >= SUPPORT_MAX_MESSAGES_PER_TICKET:
            return {"ok": False, "error": "В тикете слишком много сообщений. Откройте новое обращение."}

        chunks: list[bytes] = []
        total = 0
        while True:
            piece = await file.read(64 * 1024)
            if not piece:
                break
            total += len(piece)
            if total > TICKET_MEDIA_MAX_BYTES:
                return {"ok": False, "error": "Файл больше 10 МБ"}
            chunks.append(piece)
        payload = b"".join(chunks)
        rel = save_ticket_media_bytes(payload, int(ticket_id))
        if not rel:
            return {"ok": False, "error": "Можно прикрепить jpeg, png, webp или PDF до 10 МБ"}
        text = _clip_support_text(caption, SUPPORT_CAPTION_MAX_LEN)
        add_support_message(int(ticket_id), sender="user", content=text, media=rel)
        try:
            await _notify_webapp_support(
                user_id,
                ticket,
                title="📎 <b>Вложение (WebApp)!</b>",
                body=text or "Файл во вложении.",
            )
        except Exception as e:
            logger.warning("WebApp support upload notify failed: %s", e)
        return {"ok": True}
    except Exception as e:
        logger.error("Error in support upload: %s", e)
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_support_rate_response",
    "_support_user_rate_limited",
    "_support_too_fast",
    "_clip_support_text",
    "_tickets_created_today_count",
    "_public_ticket_row",
    "_public_ticket_messages",
    "_ticket_owned_by",
    "_notify_webapp_support",
    "api_support_status",
    "api_support_create",
    "api_support_send",
    "api_support_ticket",
    "api_support_close",
    "api_support_ticket_file",
    "api_support_upload",
]
