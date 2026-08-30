"""Локальные вложения тикетов поддержки.

Файлы пишутся на диск рядом с БД и отдаются только панелью под login_required.
Наружу как static / Telegram file URL они не публикуются.

Лимит 10 МБ: заявленный file_size или getFile. Если размера нет — качаем
в память с потолком 10 МБ и проверяем после.

На тикет: не больше 10 файлов и 30 МБ суммарно. При удалении тикета
каталог ``ticket_files/<ticket_id>/`` снимается вместе со строками БД.

Тип файла определяется по magic bytes (jpeg/png/webp/pdf), не по имени
и не по MIME Telegram. GIF не принимаем. Панель отдаёт MIME и nosniff.

Вложения закрытого тикета хранятся ``TICKET_MEDIA_CLOSED_TTL_DAYS`` суток
(по ``updated_at`` закрытия), затем каталог удаляется. Строки тикета в БД
не трогаем.
"""
from __future__ import annotations

import io
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

TICKET_MEDIA_MAX_BYTES = 10 * 1024 * 1024
TICKET_MEDIA_MAX_FILES = 10
TICKET_MEDIA_MAX_TOTAL_BYTES = 30 * 1024 * 1024
TICKET_MEDIA_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".pdf")
TICKET_MEDIA_CLOSED_TTL_DAYS = 7
TICKET_MEDIA_PURGE_INTERVAL_SECONDS = 3600

_last_purge_monotonic = 0.0


def detect_image_kind_bytes(head: bytes) -> tuple[str, str] | None:
    """Расширение и MIME по сигнатуре. None — не jpeg/png/webp/pdf."""
    if not head:
        return None
    if len(head) >= 3 and head.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(head) >= 8 and head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp", "image/webp"
    if len(head) >= 5 and head.startswith(b"%PDF-"):
        return ".pdf", "application/pdf"
    return None


def detect_image_kind(path: str) -> tuple[str, str] | None:
    try:
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    return detect_image_kind_bytes(head)


def media_kind_from_stored(media: str | None) -> str | None:
    """image | pdf | file по имени на диске. Сырой путь наружу не отдаём."""
    if not media:
        return None
    name = str(media).replace("\\", "/").rsplit("/", 1)[-1].lower()
    if not name or ".." in name:
        return None
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return "image"
    return "file"


def public_support_message(m: dict) -> dict:
    """Поля сообщения для панели/JSON без пути ticket_files."""
    raw = m.get("media")
    has_media = bool(raw) and str(raw).strip() not in ("", "None")
    return {
        "sender": m.get("sender"),
        "content": m.get("content"),
        "message_id": m.get("message_id"),
        "created_at": m.get("created_at"),
        "has_media": has_media,
        "media_kind": media_kind_from_stored(raw) if has_media else None,
    }


def positive_file_size(file_size: Any) -> int | None:
    """Положительный размер в байтах или None, если Telegram его не дал."""
    if file_size is None:
        return None
    try:
        size = int(file_size)
    except (TypeError, ValueError):
        return None
    if size <= 0:
        return None
    return size


async def resolve_telegram_file_size(
    bot: Any,
    file_id: str,
    declared_size: Any = None,
) -> tuple[int | None, Any]:
    """Размер до download. Всегда getFile, если бот его умеет.

    Возвращает (размер или None, объект для bot.download).
    Download по File надёжнее, чем по голому file_id: локальный Bot API
    отдаёт file_path, без него папка тикета создавалась пустой.
    None — размер неизвестен; вызывающая сторона всё равно может качать
    с потолком 10 МБ.
    """
    known = positive_file_size(declared_size)
    get_file = getattr(bot, "get_file", None)
    if get_file is None:
        return known, file_id
    try:
        tg_file = await get_file(file_id)
    except Exception:
        logger.warning("getFile для вложения тикета не удался")
        return known, file_id
    api_size = positive_file_size(getattr(tg_file, "file_size", None) if tg_file is not None else None)
    size = api_size if api_size is not None else known
    source = tg_file if tg_file is not None else file_id
    return size, source


async def download_ticket_media_capped(
    bot: Any,
    source: Any,
    part_path: str,
    max_bytes: int = TICKET_MEDIA_MAX_BYTES,
) -> bool:
    """Качаем в BytesIO (у него есть seek — aiogram его вызывает), затем на диск.

    Путь + aiofiles раньше мог молча не создать файл; BytesIO это обходит.
    """
    buf = io.BytesIO()
    try:
        file_path = getattr(source, "file_path", None)
        download_file = getattr(bot, "download_file", None)
        if file_path and download_file is not None:
            await download_file(file_path, destination=buf)
        else:
            await bot.download(source, destination=buf)
        data = buf.getvalue()
        if not data:
            logger.warning("Вложение тикета: download вернул пусто")
            return False
        if len(data) > max_bytes:
            logger.warning("Вложение тикета: после download размер %s, лимит %s", len(data), max_bytes)
            return False
        parent = os.path.dirname(part_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(part_path, "wb") as fh:
            fh.write(data)
        return True
    except Exception:
        logger.exception("Не удалось скачать вложение тикета")
        _unlink_quiet(part_path)
        return False


def declared_size_over_limit(
    file_size: int | None,
    max_bytes: int = TICKET_MEDIA_MAX_BYTES,
) -> bool:
    """True, если Telegram уже сообщил размер больше лимита.

    None и 0 — размер неизвестен; тогда нужен getFile, не download.
    """
    if file_size is None:
        return False
    try:
        size = int(file_size)
    except (TypeError, ValueError):
        return False
    return size > max_bytes


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


def closed_ttl_days() -> int:
    raw = os.environ.get("TICKET_MEDIA_CLOSED_TTL_DAYS", str(TICKET_MEDIA_CLOSED_TTL_DAYS))
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = TICKET_MEDIA_CLOSED_TTL_DAYS
    return max(1, min(days, 3650))


def parse_ticket_updated_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def closed_ticket_media_expired(
    ticket: dict | None,
    *,
    now: datetime | None = None,
    ttl_days: int | None = None,
) -> bool:
    """True, если тикет закрыт дольше TTL — файлы пора снять."""
    if not ticket or (ticket.get("status") or "") != "closed":
        return False
    updated = parse_ticket_updated_at(ticket.get("updated_at"))
    if updated is None:
        return False
    days = closed_ttl_days() if ttl_days is None else max(1, int(ttl_days))
    moment = now or datetime.utcnow()
    return updated <= moment - timedelta(days=days)


def ticket_media_on_disk(root: str | None = None) -> bool:
    """True, если в ticket_files есть хоть одна запись. Без SQL и без полного обхода."""
    if root is None:
        from shop_bot.data_manager.database import get_ticket_media_root

        root = get_ticket_media_root()
    try:
        if not root or not os.path.isdir(root):
            return False
        with os.scandir(root) as it:
            return next(it, None) is not None
    except OSError:
        return False


def expire_ticket_media_if_closed_ttl(ticket_id: int, *, now: datetime | None = None) -> bool:
    """Если тикет закрыт дольше TTL — удаляет файлы и обнуляет media. True = истекло."""
    from shop_bot.data_manager.database import clear_support_message_media, get_ticket

    ticket = get_ticket(int(ticket_id))
    if not closed_ticket_media_expired(ticket, now=now):
        return False
    delete_ticket_media_dir(int(ticket_id))
    clear_support_message_media(int(ticket_id))
    return True


def purge_expired_closed_ticket_media(
    *,
    now: datetime | None = None,
    ttl_days: int | None = None,
) -> dict[str, int]:
    """Снимает каталоги закрытых тикетов старше TTL и осиротевшие папки."""
    from shop_bot.data_manager.database import (
        clear_support_message_media,
        get_ticket,
        get_ticket_media_root,
        list_closed_ticket_ids_older_than,
    )

    moment = now or datetime.utcnow()
    days = closed_ttl_days() if ttl_days is None else max(1, int(ttl_days))
    if not ticket_media_on_disk(get_ticket_media_root()):
        return {"purged": 0, "orphans": 0}
    cutoff = moment - timedelta(days=days)
    purged = 0
    orphans = 0
    seen: set[int] = set()

    for tid in list_closed_ticket_ids_older_than(cutoff):
        if tid in seen:
            continue
        seen.add(tid)
        delete_ticket_media_dir(tid)
        clear_support_message_media(tid)
        purged += 1

    try:
        root = get_ticket_media_root()
        names = os.listdir(root) if os.path.isdir(root) else []
    except OSError:
        names = []
    for name in names:
        if not name.isdigit():
            continue
        tid = int(name)
        if tid in seen:
            continue
        folder = jailed_ticket_folder(tid)
        if not folder or not os.path.isdir(folder):
            continue
        ticket = get_ticket(tid)
        if ticket is None:
            try:
                mtime = datetime.utcfromtimestamp(os.path.getmtime(folder))
            except OSError:
                continue
            if mtime <= moment - timedelta(days=days):
                delete_ticket_media_dir(tid)
                orphans += 1
            continue
        if closed_ticket_media_expired(ticket, now=moment, ttl_days=days):
            delete_ticket_media_dir(tid)
            clear_support_message_media(tid)
            purged += 1
            seen.add(tid)

    if purged or orphans:
        logger.info(
            "TTL вложений закрытых тикетов: снято папок %s, сирот %s",
            purged,
            orphans,
        )
    return {"purged": purged, "orphans": orphans}


def maybe_purge_expired_closed_ticket_media() -> dict[str, int] | None:
    """Не чаще раза в час. Нет файлов — сразу выход, таймер не заводим."""
    global _last_purge_monotonic
    if not ticket_media_on_disk():
        return None
    now = time.monotonic()
    if now - _last_purge_monotonic < TICKET_MEDIA_PURGE_INTERVAL_SECONDS:
        return None
    _last_purge_monotonic = now
    try:
        return purge_expired_closed_ticket_media()
    except Exception:
        logger.exception("Не удалось почистить вложения закрытых тикетов")
        return None


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
            logger.warning(
                "Вложение тикета: после download размер %s, лимит %s",
                size,
                TICKET_MEDIA_MAX_BYTES,
            )
            _unlink_quiet(part_path)
            return None
        kind = detect_image_kind(part_path)
        if kind is None:
            try:
                with open(part_path, "rb") as fh:
                    head_hex = fh.read(16).hex()
            except OSError:
                head_hex = "unreadable"
            logger.warning(
                "Вложение тикета: не jpeg/png/webp/pdf, заголовок %s",
                head_hex,
            )
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


def remove_empty_ticket_folder(folder: str) -> None:
    """Снимает пустой ``ticket_files/<id>/`` после неудачного save."""
    try:
        if folder and os.path.isdir(folder) and not os.listdir(folder):
            os.rmdir(folder)
    except OSError:
        pass


def _unlink_quiet(*paths: str) -> None:
    for path in paths:
        try:
            if path and os.path.isfile(path):
                os.unlink(path)
        except OSError:
            pass


def document_may_be_ticket_media(doc: Any) -> bool:
    """Документ можно скачать: картинка или PDF. Тип всё равно подтвердит magic."""
    mime = str(getattr(doc, "mime_type", None) or "").lower()
    name = str(getattr(doc, "file_name", None) or "").lower()
    if mime.startswith("image/"):
        return True
    if mime in ("application/pdf", "application/x-pdf"):
        return True
    return name.endswith(TICKET_MEDIA_EXTS)


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
            logger.warning("Тикет %s: фото больше лимита (%s)", ticket_id, declared_size)
            return None
        file_id = photo.file_id
    elif doc and document_may_be_ticket_media(doc):
        declared_size = getattr(doc, "file_size", None)
        if declared_size_over_limit(declared_size):
            logger.warning("Тикет %s: документ больше лимита (%s)", ticket_id, declared_size)
            return None
        file_id = doc.file_id

    if not file_id:
        return None

    part_path = ""
    final_path = ""
    folder = ""
    saved = False
    try:
        known_size, download_source = await resolve_telegram_file_size(
            bot, file_id, declared_size
        )
        if declared_size_over_limit(known_size):
            logger.warning("Тикет %s: getFile/size %s больше лимита", ticket_id, known_size)
            return None
        if known_size is None:
            logger.info("Тикет %s: размер неизвестен, качаем с потолком %s", ticket_id, TICKET_MEDIA_MAX_BYTES)
        ticket_id = int(ticket_id)
        folder = jailed_ticket_folder(ticket_id) or ""
        if not folder:
            logger.warning("Тикет %s: каталог вложений вне jail", ticket_id)
            return None
        os.makedirs(folder, exist_ok=True)
        if quota_blocks_new_file(folder, known_size):
            logger.warning("Тикет %s: квота вложений исчерпана", ticket_id)
            return None
        stem = uuid.uuid4().hex
        part_path = os.path.join(folder, f"{stem}.part")
        if not await download_ticket_media_capped(bot, download_source, part_path):
            return None
        name = commit_ticket_image(part_path, folder, stem)
        if not name:
            logger.warning("Тикет %s: файл отклонён (размер или не jpeg/png/webp/pdf)", ticket_id)
            return None
        final_path = os.path.join(folder, name)
        count, total = ticket_folder_usage(folder)
        if count > TICKET_MEDIA_MAX_FILES or total > TICKET_MEDIA_MAX_TOTAL_BYTES:
            _unlink_quiet(final_path)
            logger.warning("Тикет %s: квота после записи, файл удалён", ticket_id)
            return None
        maybe_purge_expired_closed_ticket_media()
        logger.info("Тикет %s: вложение сохранено %s", ticket_id, final_path)
        saved = True
        return f"{ticket_id}/{name}"
    except Exception as e:
        logger.error("Не удалось сохранить вложение тикета %s: %s", ticket_id, e)
        _unlink_quiet(part_path, final_path)
        return None
    finally:
        if folder and not saved:
            remove_empty_ticket_folder(folder)
