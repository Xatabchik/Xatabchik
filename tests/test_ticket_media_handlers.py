"""Хендлеры поддержки должны вызывать save на всех путях пользователя."""
from __future__ import annotations

from pathlib import Path


HANDLERS = Path(__file__).resolve().parents[1] / "src/shop_bot/support_bot/handlers.py"


def _fn_body(name: str) -> str:
    src = HANDLERS.read_text(encoding="utf-8")
    marker = f"async def {name}("
    start = src.index(marker)
    rest = src[start + len(marker) :]
    nxt = rest.find("\n    async def ")
    nxt2 = rest.find("\n    @router.")
    cuts = [i for i in (nxt, nxt2) if i != -1]
    end = min(cuts) if cuts else len(rest)
    return rest[:end]


def test_relay_open_ticket_saves_media():
    """После создания тикета FSM сброшен — фото шло сюда без записи на диск."""
    body = _fn_body("relay_user_message_to_forum")
    assert "_save_ticket_media" in body
    assert "media=_media" in body


def test_first_ticket_message_saves_media():
    body = _fn_body("support_message_received")
    assert "_save_ticket_media" in body
    assert "media=_media" in body


def test_user_reply_saves_media():
    body = _fn_body("support_reply_received")
    assert "_save_ticket_media" in body
    assert "media=_media" in body


def test_admin_forum_reply_saves_photo_without_caption():
    body = _fn_body("forum_thread_message_handler")
    assert "_save_ticket_media" in body
    assert "if content or _media" in body
