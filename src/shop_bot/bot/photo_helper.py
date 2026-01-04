import os
from typing import Any, Dict, Optional, Tuple

from aiogram import Bot
from aiogram.types import Message, FSInputFile


def _default_image_path() -> str:
    """
    Returns absolute path to default image (src/shop_bot/img/obla.png).
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))  # .../shop_bot
    return os.path.join(base_dir, "img", "obla.png")


def _get_default_photo() -> FSInputFile:
    path = _default_image_path()
    return FSInputFile(path)


async def answer_with_image(message: Message, *args: Any, **kwargs: Any):
    """
    Drop-in replacement for message.answer(...), but sends a photo with caption.
    Supports both positional (text) and keyword 'text'.
    """
    text: Optional[str] = None
    if args:
        text = args[0]
        args = args[1:]
    if text is None and "text" in kwargs:
        text = kwargs.pop("text")
    if text is None:
        text = ""

    photo = _get_default_photo()
    # message.answer_photo signature supports reply_markup, parse_mode, disable_web_page_preview, etc.
    return await message.answer_photo(photo=photo, caption=text, **kwargs)


async def send_with_image(bot: Bot, *args: Any, **kwargs: Any):
    """
    Drop-in replacement for bot.send_message(...), but sends a photo with caption.
    Supports both positional (chat_id, text) and keyword args ('chat_id', 'text').
    """
    chat_id = None
    text: Optional[str] = None

    if len(args) >= 2:
        chat_id, text = args[0], args[1]
        args = args[2:]
    else:
        if "chat_id" in kwargs:
            chat_id = kwargs.pop("chat_id")
        elif args:
            chat_id = args[0]
            args = args[1:]
        if "text" in kwargs:
            text = kwargs.pop("text")
        elif args:
            text = args[0]
            args = args[1:]

    if chat_id is None:
        raise ValueError("send_with_image: chat_id is required")

    if text is None:
        text = ""

    photo = _get_default_photo()
    return await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, **kwargs)


async def edit_with_image(message: Message, *args: Any, **kwargs: Any):
    """
    Replacement for message.edit_text(...).
    Tries to edit caption (for photo messages). If it fails (e.g., message is text),
    falls back to deleting the old message and sending a new photo message with the caption.
    Supports positional text and keyword 'text'.
    """
    text: Optional[str] = None
    if args:
        text = args[0]
        args = args[1:]
    if text is None and "text" in kwargs:
        text = kwargs.pop("text")
    if text is None:
        text = ""

    # Aiogram edit_caption uses 'caption', not 'text'
    # Also supports reply_markup.
    try:
        return await message.edit_caption(caption=text, **kwargs)
    except Exception:
        # Last resort: try to replace message
        try:
            await message.delete()
        except Exception:
            pass
        photo = _get_default_photo()
        return await message.answer_photo(photo=photo, caption=text, **kwargs)
