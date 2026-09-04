# Комментарии: `src/shop_bot/bot/photo_helper.py`

В runtime хендлеры этот модуль не импортируют.

## `_default_image_path` (8–13)

**Docstring в коде:** есть

```
Returns absolute path to default image (src/shop_bot/img/obla.png).
```

`parents`: `dirname(dirname(__file__))` = пакет `shop_bot`, затем `img/obla.png`.

## `_get_default_photo` (16–18)

**Docstring в коде:** нет

```
"""Обернуть путь _default_image_path в aiogram.types.FSInputFile."""
```

## `answer_with_image` (21–37)

**Docstring в коде:** есть

```
Drop-in replacement for message.answer(...), but sends a photo with caption.
Supports both positional (text) and keyword 'text'.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 27–33 | разбор text | args[0] или kwargs['text'], иначе пустая подпись |
| 35–37 | answer_photo | caption=text, остальные kwargs как у answer_photo |

## `send_with_image` (40–70)

**Docstring в коде:** есть

```
Drop-in replacement for bot.send_message(...), but sends a photo with caption.
Supports both positional (chat_id, text) and keyword args ('chat_id', 'text').
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 48–61 | разбор chat_id/text | два позиционных или kwargs; остаток args сдвигается |
| 63–64 | нет chat_id | ValueError |
| 69–70 | send_photo | |

## `edit_with_image` (73–100)

**Docstring в коде:** есть

```
Replacement for message.edit_text(...).
Tries to edit caption (for photo messages). If it fails (e.g., message is text),
falls back to deleting the old message and sending a new photo message with the caption.
Supports positional text and keyword 'text'.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 91–92 | edit_caption | штатный путь для фото-сообщений |
| 93–100 | except | delete старого (ошибка игнор) + answer_photo |
