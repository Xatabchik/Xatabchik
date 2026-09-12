# Комментарии: `src/shop_bot/bot/middlewares.py`

## `BanMiddleware` (7–77)

**Docstring в коде:** нет

```
"""Aiogram middleware: снять is_unreachable при любом апдейте; забаненным не вызывать handler, показать бан и кнопку поддержки."""
```

### `BanMiddleware.__call__` (8–77)

**Docstring в коде:** нет. В коде `#` (20–22): взаимодействие значит, что пользователь снова доступен для рассылок.

```
"""Пропустить event без from_user; иначе get_user, mark_user_reachable, при is_banned — ответ и return без handler."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 15–16 | нет event_from_user | сразу handler (каналы и т.п.) |
| 23–27 | is_unreachable | mark_user_reachable, ошибки глотать |
| 29–75 | is_banned | собрать URL поддержки из support_bot_username / support_user |
| 38–51 | разбор support | @username → tg://resolve; tg:// как есть; http(s) → последний path segment; иначе как domain |
| 52–55 | кнопка | URL или callback `show_help` |
| 58–68 | CallbackQuery | answer alert + send_message в личку |
| 69–74 | Message | answer с клавиатурой; fallback без markup |
| 75 | return | handler не вызывается |
| 77 | иначе | обычный handler |
