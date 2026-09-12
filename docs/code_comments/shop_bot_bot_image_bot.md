# Комментарии: `src/shop_bot/bot/image_bot.py`

Подкласс Bot не подключён в BotController.

## `_pick_image_path` (11–26)

**Docstring в коде:** есть

```
Pick an image file from shop_bot/img.

If multiple files exist, picks the first one in sorted order.
Supported extensions: png, jpg, jpeg, webp, gif.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 18–19 | нет каталога | FileNotFoundError |
| 23–24 | нет файлов | FileNotFoundError |
| 26 | return sorted(files)[0] | детерминированный выбор |

## `_filter_kwargs` (29–32)

**Docstring в коде:** есть

```
Keep only kwargs that func(...) accepts (defensive for aiogram version differences).
```

Отбрасывает ключи не из signature и значения None.

## `ImageBot` (35–111)

**Docstring в коде:** есть

```
Bot that attaches an image from shop_bot/img to every outgoing text message.

It transparently replaces send_message(...) with send_photo/send_animation(...),
placing the original text into the caption.
```

`_CAPTION_LIMIT = 1024` — лимит подписи Telegram (комментарий в коде, строка 42–43).

### `ImageBot.send_message` (45–111)

**Docstring в коде:** нет

```
"""Вместо send_message отправить фото/gif с текстом в caption; длинный текст — несколько сообщений по 1024 символа.

kwargs _no_image=True вызывает super().send_message без картинки.
reply_markup и reply_to только на первом чанке. Неизвестные kwargs send_message отбрасываются молча.
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 47–48 | _no_image | обход |
| 51–69 | вынуть kwargs | map на caption; send_message-only параметры игнор |
| 75–81 | нарезка текста | цикл срезами 1024 |
| 100–109 | gif vs иное | send_animation / send_photo после _filter_kwargs |
| 111 | return last_msg | последнее отправленное сообщение |
