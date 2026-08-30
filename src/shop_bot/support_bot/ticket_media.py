"""Локальные вложения тикетов поддержки.

Файлы пишутся на диск рядом с БД и отдаются только панелью под login_required.
Наружу как static / Telegram file URL они не публикуются.

Лимит 10 МБ проверяется дважды: по заявленному Telegram file_size (если он
есть и > 0) и по реальному размеру после скачивания. file_size is None / 0
не считается «файл маленький» — иначе лимит обходится.

На тикет: не больше 10 файлов и 30 МБ суммарно. При удалении тикета
каталог ``ticket_files/<ticket_id>/`` снимается вместе со строками БД.

Тип файла определяется по magic bytes (jpeg/png/gif/webp), не по имени
и не по MIME Telegram. Панель отдаёт вложение с этим MIME и nosniff.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

TICKET_MEDIA_MAX_BYTES = 10 * 1024 * 1024
TICKET_MEDIA_MAX_FILES = 10
TICKET_MEDIA_MAX_TOTAL_BYTES = 30 * 1024 * 1024
TICKET_MEDIA_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def detect_image_kind_bytes(head: bytes) -> tuple[str, str] | None:
    """Расширение и MIME по сигнатуре. None — не картинка из whitelist."""
    if not head or len(head) < 12:
        return None
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return ".gif", "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def detect_image_kind(path: str) -> tuple[str, str] | None:
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    return detect_image_kind_bytes(head)


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


def ticket_folder_usage(folder: str) -> tuple[int, int]:
    """Число финальных файлов и их суммарный размер. ``*.part`` не считаем."""
    count = 0
    total = 0
    if not folder or not os.path.isdir(folder):
        return 0, 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0, 0
    for name in names:
        if name.endswith(".part"):
            continue
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        try:
            total += os.path.getsize(path)
        except OSError:
            continue
        count += 1
    return count, total


def quota_blocks_new_file(
    folder: str,
    incoming_bytes: int | None = None,
    *,
    max_files: int | None = None,
    max_total_bytes: int | None = None,
) -> bool:
    """True, если ещё одно вложение превысит квоту тикета (10 файлов / 30 МБ)."""
    if max_files is None:
        max_files = TICKET_MEDIA_MAX_FILES
    if max_total_bytes is None:
        max_total_bytes = TICKET_MEDIA_MAX_TOTAL_BYTES
    count, total = ticket_folder_usage(folder)
    if count >= max_files:
        return True
    if total >= max_total_bytes:
        return True
    if incoming_bytes is not None:
        try:
            incoming = int(incoming_bytes)
        except (TypeError, ValueError):
            incoming = 0
        if incoming > 0 and total + incoming > max_total_bytes:
            return True
    return False


def jailed_ticket_folder(ticket_id: int, root: str | None = None) -> str | None:
    """Каталог вложений тикета строго внутри media root, иначе None."""
    try:
        tid = int(ticket_id)
    except (TypeError, ValueError):
        return None
    if tid <= 0:
        return None
    if root is None:
        from shop_bot.data_manager.database import get_ticket_media_root

        root = get_ticket_media_root()
    base = os.path.realpath(root)
    folder = os.path.realpath(os.path.join(base, str(tid)))
    if folder == base or not folder.startswith(base + os.sep):
        return None
    return folder


def delete_ticket_media_dir(ticket_id: int) -> bool:
    """Удаляет ``ticket_files/<ticket_id>/``. Не трогает соседние тикеты и корень."""
    import shutil

    folder = jailed_ticket_folder(ticket_id)
    if folder is None:
        return False
    if not os.path.isdir(folder):
        return True
    shutil.rmtree(folder, ignore_errors=True)
    return not os.path.isdir(folder)


def commit_ticket_image(part_path: str, dest_dir: str, stem: str) -> str | None:
    """Размер + magic. Возвращает ``stem.ext`` или None; ``*.part`` удаляется при отказе."""
    try:
        if not os.path.isfile(part_path):
            return None
        size = os.path.getsize(part_path)
        if size <= 0 or size > TICKET_MEDIA_MAX_BYTES:
            _unlink_quiet(part_path)
            return None
        kind = detect_image_kind(part_path)
        if kind is None:
            _unlink_quiet(part_path)
            return None
        ext, _mime = kind
        name = f"{stem}{ext}"
        final_path = os.path.join(dest_dir, name)
        os.replace(part_path, final_path)
        return name
    except Exception:
        _unlink_quiet(part_path)
        return None


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

    if not file_id:
        return None

    part_path = ""
    final_path = ""
    try:
        ticket_id = int(ticket_id)
        folder = jailed_ticket_folder(ticket_id)
        if not folder:
            return None
        incoming = None
        try:
            if declared_size is not None and int(declared_size) > 0:
                incoming = int(declared_size)
        except (TypeError, ValueError):
            incoming = None
        os.makedirs(folder, exist_ok=True)
        if quota_blocks_new_file(folder, incoming):
            return None
        stem = uuid.uuid4().hex
        part_path = os.path.join(folder, f"{stem}.part")
        await bot.download(file_id, destination=part_path)
        name = commit_ticket_image(part_path, folder, stem)
        if not name:
            return None
        final_path = os.path.join(folder, name)
        count, total = ticket_folder_usage(folder)
        if count > TICKET_MEDIA_MAX_FILES or total > TICKET_MEDIA_MAX_TOTAL_BYTES:
            _unlink_quiet(final_path)
            return None
        return f"{ticket_id}/{name}"
    except Exception as e:
        logger.error("Не удалось сохранить вложение тикета %s: %s", ticket_id, e)
        _unlink_quiet(part_path, final_path)
        return None
