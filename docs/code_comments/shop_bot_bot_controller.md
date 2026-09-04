# Комментарии: `src/shop_bot/bot_controller.py`

Жизненный цикл основного Telegram-бота. Модульного docstring нет.

## `_is_true` (28–29)

**Docstring в коде:** нет

```
"""True, если строка value в true/1/on/yes/y (регистр не важен)."""
```

## `BotController` (32–285)

**Docstring в коде:** нет

```
"""Контроллер основного бота: свой thread+loop, start/stop polling, клоны франшизы, кэш PAYMENT_METHODS."""
```

### `BotController.__init__` (33–45)

**Docstring в коде:** нет. В коде `#` про изоляцию loop от Flask и support-бота.

```
"""Обнулить runtime-поля и сразу поднять собственный event loop в daemon-потоке."""
```

### `BotController._start_own_loop` (47–68)

**Docstring в коде:** нет. В коде `#` про `ready.set` только внутри `run_forever` (гонка is_running).

```
"""Создать новый asyncio loop в потоке main-bot-loop; ждать ready не более 5 с."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
### `BotController._start_own_loop._runner` (50–62)

**Docstring в коде:** нет

```
"""В потоке: new_event_loop, выставить self._loop, ready.set, run_forever, затем close."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 50–62 | `_runner` | new_event_loop, call_soon(ready.set), run_forever, close |
| 66–67 | if not ready.wait(5) | warning, но поток уже запущен |

### `BotController.set_loop` (70–74)

**Docstring в коде:** нет. В коде `#`: внешний loop игнорируется (обратная совместимость).

```
"""Принять loop и не использовать его — у контроллера свой цикл."""
```

### `BotController.get_loop` (76–77)

**Docstring в коде:** нет

```
"""Вернуть собственный loop или None, если поток ещё не выставил self._loop."""
```

### `BotController.get_bot_instance` (79–80)

**Docstring в коде:** нет

```
"""Вернуть текущий aiogram.Bot или None, если polling не собран / уже закрыт."""
```

### `BotController._start_polling` (82–135)

**Docstring в коде:** нет

```
"""Цикл start_polling с backoff; по выходу остановить клоны, закрыть bot, обнулить dp.

handle_signals=False — сигналы обрабатывает __main__, не aiogram.
TelegramUnauthorizedError — выход без ретрая. RetryAfter / server / network / прочее — sleep и повтор.
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 90–121 | while not _stop_requested | повтор polling до стопа |
| 93–95 | успешный return start_polling | break: вызван stop_polling |
| 96–98 | CancelledError | break |
| 99–102 | Unauthorized | break, лог |
| 103–106 | RetryAfter | sleep retry_after |
| 107–114 | Server/Network | sleep backoff, backoff×2 до 60 |
| 115–119 | прочий Exception | то же |
| 120–121 | после успешного прохода | backoff=2 (на практике после break не достигается) |
| 122–135 | finally | is_running=False, stop_all клонов, bot.close, обнуление |

### `BotController.start` (137–269)

**Docstring в коде:** нет

```
"""Собрать Bot+Dispatcher, middleware, роутеры, плагины, клоны, PAYMENT_METHODS; запустить polling на своём loop.

Возвращает dict status/message. Не стартует, если уже is_running или нет токена/username/admin_id.
platega в handlers.PAYMENT_METHODS не записывается (только yookassa, heleket, cryptobot, tonconnect, yoomoney, stars, rollypay).
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 138–139 | already running | error |
| 141–145 | loop мёртв | повтор _start_own_loop; если снова нет — error |
| 147–160 | настройки Telegram | admin_id int; без трёх полей — error |
| 162–189 | Bot, Ban+Factory middleware, user/admin routers, module_loader | TypeError если router не Router |
| 191–201 | франшиза | ManagedBotsService + start_all только при franchise_enabled |
| 203–206 | delete_webhook | drop_pending_updates, ошибка → warning |
| 208–257 | флаги платежей | YooKassa Configuration; yoomoney: None флага → включено при wallet+secret |
| 261–263 | run_coroutine_threadsafe _start_polling | success |
| 265–269 | except | обнулить bot/dp, error |

### `BotController.stop` (271–282)

**Docstring в коде:** нет

```
"""Поставить _stop_requested и вызвать dp.stop_polling на своём loop. Не ждёт завершения потока."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 272–273 | не запущен | error |
| 275–276 | нет loop/dp | error |

### `BotController.get_status` (284–285)

**Docstring в коде:** нет

```
"""Вернуть {'is_running': bool} — флаг, выставляемый в _start_polling/finally."""
```
