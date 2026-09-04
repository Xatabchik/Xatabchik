# Комментарии: `src/shop_bot/factory_bot/service.py`

Runtime управляемых клонов на loop root-бота. Модульного docstring нет.

## `ManagedBotsService` (20–148)

**Docstring в коде:** нет

```
"""Сервис клонов: start/stop/restart polling на переданном asyncio loop, словари tasks/dispatchers/bots."""
```

### `ManagedBotsService.__init__` (21–26)

**Docstring в коде:** нет

```
"""Сохранить loop; пустые _tasks/_dispatchers/_bots и asyncio.Lock."""
```

Loop здесь не создаётся — его даёт BotController.

### `ManagedBotsService.get_bot` (28–30)

**Docstring в коде:** есть

```
Возвращает экземпляр Bot для bot_id, если он запущен.
```

`int(bot_id)`; нет в `_bots` → None.

### `ManagedBotsService._drop_bot_refs` (32–35)

**Docstring в коде:** нет

```
"""Убрать bot_id из _tasks, _dispatchers и _bots (pop, без отмены task)."""
```

### `ManagedBotsService._has_running_task` (37–39)

**Docstring в коде:** нет

```
"""True, если в _tasks есть task и он ещё не done()."""
```

### `ManagedBotsService.start_all` (41–50)

**Docstring в коде:** нет

```
"""Пройти list_active_managed_bots и start_bot тех, у кого нет running task; ошибка одного id не останавливает цикл."""
```

### `ManagedBotsService.start_bot` (52–111)

**Docstring в коде:** нет. В коде `#`: завершённый task не блокирует рестарт; клон — полный shop-фронтенд на общей БД; Ban+Factory middleware; создание клонов только в root.

```
"""Под lock: если task уже бежит — выход; иначе Bot+Dispatcher, user+owner routers, create_task(runner). Нет info/token — выход."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 54–56 | already running | return |
| 57–58 | `_drop_bot_refs` | очистить done-task после автоотключения |
| 60–65 | нет info/token | return |
| 69–81 | Bot HTML, Ban+FactoryStats, get_user_router + get_owner_cabinet_router | без admin_router |
| 83–106 | `runner` | start_polling(handle_signals=False); CancelledError ignore; Unauthorized/Forbidden → `update_managed_bot_active(0)` без токена в логе; прочее — error; finally `bot.session.close`, `_drop_bot_refs` |
| 108–111 | create_task | имя `managed-bot-{id}`; записать task/dp/bot |

### `ManagedBotsService.stop_bot` (113–132)

**Docstring в коде:** есть

```
Остановить один клон. Идемпотентно: повторный вызов безопасен.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 116–123 | dp.stop_polling | ошибка игнор |
| 124–131 | task cancel + await | CancelledError ignore; прочее — лог |
| 132 | `_drop_bot_refs` | даже если task уже не было |

Не вызывает `bot.session.close` здесь — это делает `runner.finally`.

### `ManagedBotsService.restart_bot` (134–137)

**Docstring в коде:** есть

```
Перезапуск клона (смена токена владельцем).
```

`stop_bot` затем `start_bot`.

### `ManagedBotsService.stop_all` (139–148)

**Docstring в коде:** нет

```
"""Остановить каждый id из снимка _tasks.keys(); затем clear всех трёх словарей."""
```

Ошибка одного `stop_bot` логируется, цикл продолжается.
