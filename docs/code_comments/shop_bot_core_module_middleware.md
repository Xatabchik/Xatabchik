# Комментарии: `src/shop_bot/core/module_middleware.py`

Aiogram middleware изоляции ошибок плагина. Модульного docstring нет.

## `ModuleSafeMiddleware` (14–74)

**Docstring в коде:** есть

```
Catches module handler errors and marks the module as failed.
```

Вешается на `router.message` и `router.callback_query` в `ModuleLoader._load_router`.

### `ModuleSafeMiddleware.__init__` (17–19)

**Docstring в коде:** нет

```
"""Store module_id and the ModuleLoader used to mark errors."""
```

### `ModuleSafeMiddleware.__call__` (21–44)

**Docstring в коде:** нет

```
"""Run the handler; on CallbackQuery without this module's prefix return None; on exception mark ERROR, notify admins, return None."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 27–29 | CallbackQuery и не свой prefix | не вызывать handler (чужой callback не должен падать в этот router) |
| 30–31 | try | обычный handler |
| 32–44 | except | лог с module_id; `set_module_error`; сбой записи статуса глотается; `_notify_admins`; `return None` |

Исключение не пробрасывается в ядро.

### `ModuleSafeMiddleware._is_allowed_callback` (46–54)

**Docstring в коде:** нет

```
"""True if callback.data starts with `{module_id}:` or `mod:{module_id}:`. Empty/unreadable data → False."""
```

Чтение `event.data` в try; любое исключение → `data = ""`.

### `ModuleSafeMiddleware._notify_admins` (56–74)

**Docstring в коде:** нет

```
"""Send each admin_id a Telegram HTML alert with module_id and str(exc)[:180]. No event.bot or no admins → return."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 57–59 | нет `event.bot` | выход |
| 60–65 | `get_admin_ids()` | ошибка БД → пустой set |
| 70–74 | for admin_id | `send_message`; ошибка одного адресата — `continue` |
