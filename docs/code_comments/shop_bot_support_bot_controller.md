# Комментарии: `src/shop_bot/support_bot_controller.py`

Контроллер support-бота (отдельный thread+loop). Модульного docstring нет.

## `SupportBotController` (15–132)

**Docstring в коде:** нет

```
"""Жизненный цикл support-бота: свой loop, start/stop polling, роутер get_support_router()."""
```

### `__init__` (16–26)

В коде `#` про изоляцию от основного бота и Flask.

```
"""Обнулить поля и поднять loop в потоке support-bot-loop."""
```

### `_start_own_loop` (28–47)

Ссылается на тот же приём `ready.set` внутри `run_forever`, что у BotController.

### `SupportBotController._start_own_loop._runner` (31–41)

**Docstring в коде:** нет

```
"""В потоке: new_event_loop, выставить self._loop, ready.set, run_forever, затем close."""
```

```
"""Запустить изолированный asyncio loop; ждать готовности до 5 с."""
```

### `set_loop` (49–52)

```
"""Игнорировать внешний loop (совместимость со старым API)."""
```

### `get_loop` / `get_bot_instance` (54–58)

```
"""Вернуть loop / Bot или None."""
```

### `_start_polling` (60–76)

**Отличие от основного бота:** нет цикла backoff и нет остановки клонов. Один вызов `start_polling`; CancelledError и любой Exception — выход в finally (close bot).

```
"""Запустить polling support-бота; в finally сбросить is_running и закрыть сессию Bot."""
```

### `start` (78–118)

```
"""Создать Bot+Dispatcher, подключить get_support_router, удалить webhook, запустить polling.

Требует support_bot_token, support_bot_username и admin_telegram_id или непустой get_admin_ids().
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 79–80 | уже запущен | error |
| 82–85 | нет loop | повтор _start_own_loop |
| 87–97 | настройки | без токена/username/админа — error |
| 99–113 | сборка и start_polling | success |
| 114–118 | except | обнуление, error |

### `stop` (120–129)

```
"""Вызвать dp.stop_polling на своём loop, если бот запущен и есть dp."""
```

### `get_status` (131–132)

```
"""Вернуть {'is_running': bool}."""
```
