from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import FSInputFile


def _pick_image_path() -> Path:
    """Pick an image file from shop_bot/img.

    If multiple files exist, picks the first one in sorted order.
    Supported extensions: png, jpg, jpeg, webp, gif.
    """
    base_dir = Path(__file__).resolve().parents[1] / "img"
    if not base_dir.exists():
        raise FileNotFoundError(f"Image directory not found: {base_dir}")

    exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    files = [p for p in base_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not files:
        raise FileNotFoundError(f"No images found in: {base_dir}")

    return sorted(files)[0]


def _filter_kwargs(func, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Keep only kwargs that func(...) accepts (defensive for aiogram version differences)."""
    allowed = set(inspect.signature(func).parameters.keys())
    return {k: v for k, v in kwargs.items() if k in allowed and v is not None}


class ImageBot(Bot):
    """Bot that attaches an image from shop_bot/img to every outgoing text message.

    It transparently replaces send_message(...) with send_photo/send_animation(...),
    placing the original text into the caption.
    """

    # Telegram caption limit for photos/animations is 1024 chars.
    _CAPTION_LIMIT = 1024

    async def send_message(self, chat_id: Any, text: str, *args: Any, **kwargs: Any):
        # Allow explicit bypass in rare cases.
        if kwargs.pop("_no_image", False):
            return await super().send_message(chat_id, text, *args, **kwargs)

        # Map send_message kwargs -> caption kwargs
        parse_mode = kwargs.pop("parse_mode", None)
        entities = kwargs.pop("entities", None)

        reply_markup = kwargs.pop("reply_markup", None)
        disable_notification = kwargs.pop("disable_notification", None)
        protect_content = kwargs.pop("protect_content", None)
        reply_to_message_id = kwargs.pop("reply_to_message_id", None)
        message_thread_id = kwargs.pop("message_thread_id", None)

        # Newer/optional params that may or may not exist depending on aiogram version
        business_connection_id = kwargs.pop("business_connection_id", None)
        allow_sending_without_reply = kwargs.pop("allow_sending_without_reply", None)
        reply_parameters = kwargs.pop("reply_parameters", None)

        # Ignore send_message-only params (e.g. disable_web_page_preview, link_preview_options, etc.)
        # plus any unknown kwargs (defensive).
        # Do NOT raise here.
        _ = args
        _ = kwargs

        img_path = _pick_image_path()
        suffix = img_path.suffix.lower()

        # Split long text into multiple captioned images so each message has an image.
        chunks: list[str] = []
        s = "" if text is None else str(text)
        while s:
            chunks.append(s[: self._CAPTION_LIMIT])
            s = s[self._CAPTION_LIMIT :]
        if not chunks:
            chunks = [""]

        last_msg = None
        for i, chunk in enumerate(chunks):
            common_kwargs = {
                "chat_id": chat_id,
                "caption": chunk,
                "parse_mode": parse_mode,
                "caption_entities": entities,
                "reply_markup": reply_markup if i == 0 else None,
                "disable_notification": disable_notification,
                "protect_content": protect_content,
                "reply_to_message_id": reply_to_message_id if i == 0 else None,
                "message_thread_id": message_thread_id,
                "business_connection_id": business_connection_id,
                "allow_sending_without_reply": allow_sending_without_reply,
                "reply_parameters": reply_parameters if i == 0 else None,
            }

            if suffix == ".gif":
                call_kwargs = dict(common_kwargs)
                call_kwargs["animation"] = FSInputFile(str(img_path))
                call_kwargs = _filter_kwargs(super().send_animation, call_kwargs)
                last_msg = await super().send_animation(**call_kwargs)
            else:
                call_kwargs = dict(common_kwargs)
                call_kwargs["photo"] = FSInputFile(str(img_path))
                call_kwargs = _filter_kwargs(super().send_photo, call_kwargs)
                last_msg = await super().send_photo(**call_kwargs)

        return last_msg
