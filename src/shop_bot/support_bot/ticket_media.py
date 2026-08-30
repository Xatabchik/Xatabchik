"""Локальные вложения тикетов поддержки.

Файлы пишутся на диск рядом с БД и отдаются только панелью под login_required.
Наружу как static / Telegram file URL они не публикуются.

Лимит 10 МБ проверяется дважды: по заявленному Telegram file_size (если он
есть и > 0) и по реальному размеру после скачивания. file_size is None / 0
не считается «файл маленький» — иначе лимит обходится.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

TICKET_MEDIA_MAX_BYTES = 10 * 1024 * 1024
TICKET_MEDIA_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def declared_size_over_limit(
    file_size: int | None,
    max_bytes: int = TICKET_MEDIA_MAX_BYTES,
) -> bool:
    """True, если Telegram уже сообщил размер больше лимита.

    None и 0 — размер неизвестен; отказ решает проверка после download.
    """
    if file_size is None:
        return False
    try:
        size = int(file_size)
    except (TypeError, ValueError):
        return False
    return size > max_bytes


def finalize_ticket_media_download(
    part_path: str,
    final_path: str,
    max_bytes: int = TICKET_MEDIA_MAX_BYTES,
) -> bool:
    """Оставляет файл только если он не пустой и не больше лимита.

    Скачивание идёт в ``*.part``; при отказе оба пути удаляются.
    """
    try:
        if not os.path.isfile(part_path):
            return False
        size = os.path.getsize(part_path)
        if size <= 0 or size > max_bytes:
            os.unlink(part_path)
            return False
        os.replace(part_path, final_path)
        return True
    except Exception:
        for path in (part_path, final_path):
            try:
                if os.path.isfile(path):
                    os.unlink(path)
            except OSError:
                pass
        return False


def _unlink_quiet(*paths: str) -> None:
    for path in paths:
        try:
            if path and os.path.isfile(path):
                os.unlink(path)
        except OSError:
            pass


async def save_ticket_media(bot: Any, message: Any, ticket_id: int) -> str | None:
    """Сохраняет изображение из сообщения. Контракт как у прежнего хелпера.

    Возвращает относительный путь ``<ticket_id>/<uuid>.ext`` или None.
    Текст сообщения вызывающая сторона сохраняет сама — отказ по размеру
    не ломает обращение.
    """
    file_id = None
    ext = ".jpg"
    declared_size = None

    photo = message.photo[-1] if getattr(message, "photo", None) else None
    doc = getattr(message, "document", None)

    if photo:
        declared_size = getattr(photo, "file_size", None)
        if declared_size_over_limit(declared_size):
            return None
        file_id = photo.file_id
    elif doc and str(getattr(doc, "mime_type", None) or "").startswith("image/"):
        declared_size = getattr(doc, "file_size", None)
        if declared_size_over_limit(declared_size):
            return None
        file_id = doc.file_id
        candidate = os.path.splitext(str(getattr(doc, "file_name", None) or ""))[1].lower()
        if candidate in TICKET_MEDIA_EXTS:
            ext = candidate

    if not file_id:
        return None

    part_path = ""
    final_path = ""
    try:
        from shop_bot.data_manager.database import get_ticket_media_root

        ticket_id = int(ticket_id)
        folder = os.path.join(get_ticket_media_root(), str(ticket_id))
        os.makedirs(folder, exist_ok=True)
        name = f"{uuid.uuid4().hex}{ext}"
        final_path = os.path.join(folder, name)
        part_path = final_path + ".part"
        await bot.download(file_id, destination=part_path)
        if not finalize_ticket_media_download(part_path, final_path):
            return None
        return f"{ticket_id}/{name}"
    except Exception as e:
        logger.error("Не удалось сохранить вложение тикета %s: %s", ticket_id, e)
        _unlink_quiet(part_path, final_path)
        return None
