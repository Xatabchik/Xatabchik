# Комментарии: `src/shop_bot/__main__.py`

Точка входа `python -m shop_bot`. Модульного docstring нет.

## Блоки уровня модуля

| Строки | Блок | Зачем |
|--------|------|--------|
| 7–12 | `try: import colorama` | Опциональная зависимость: если нет — флаг `colorama_available = False`, процесс не падает |
| 237–238 | `if __name__ == "__main__"` | Вызов `main()` только как скрипт, не при импорте |

## `main` (строки 20–235)

**Docstring в коде:** нет

```
"""Собрать логирование, инициализировать БД, поднять Flask и event loop, опционально автозапустить ботов.

Планировщик сажается на loop основного бота, не на loop Flask. Возврат — после отмены start_services.
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 21–25 | colorama.just_fix_windows_console | Цвета в консоли Windows; ошибка игнорируется |
| 27–50 | class ColoredFormatter | Подсветка уровня в `%(levelname)s`; `format` красит только тег уровня |
| 37–50 | ColoredFormatter.format | Собирает сообщение стандартным Formatter, затем replace `[LEVEL]` |
| 52–60 | сброс root handlers | Один StreamHandler INFO, без дублей при повторном входе |
| 63–70 | уровень сторонних логгеров | werkzeug/aiogram/aiohttp/paramiko/urllib3 не засоряют INFO |
| 72–99 | RussianizeAiogramFilter | Перевод строки `Update id=… is handled` на русский; при любом исключении filter всё равно True |
| 73–99 | filter | regex полного формата; иначе пословная замена; `return True` всегда |
| 105–116 | initialize_db + media root | Схема SQLite; путь вложений логируется, сбой импорта глотается |
| 118–119 | BotController + create_webhook_app | Контроллер создаёт свой loop сразу; Flask получает ссылку на него |
| 121–122 | `_is_true` | Разбор строковых флагов настроек (`true/1/on/yes/y`) |
| 124–133 | `shutdown` | Стоп основного бота, cancel прочих asyncio-задач, `loop.stop()` |
| 135–227 | `start_services` | Flask-поток, автозапуск, планировщик, sleep-3600 до отмены |
| 143–144 | SIGINT/SIGTERM | Через `create_task(shutdown)` на loop Flask/главный |
| 146–152 | Flask thread | `SHOPBOT_FLASK_HOST`/`PORT` (дефолт 127.0.0.1:1488), daemon, без reloader |
| 158–191 | автозапуск | main: токен+username+admin_id>0; support: токен+username+admin_ids; иначе warning |
| 193–207 | `_log_bot_status_soon` | Через 3 с логирует is_running обоих ботов (уже есть `#` в коде) |
| 214–218 | планировщик | `run_coroutine_threadsafe(periodic_subscription_check, main_bot_loop)` |
| 221–227 | вечный sleep | Держит `asyncio.run`; CancelledError — штатная остановка |
| 229–235 | asyncio.run / finally | Отмена снаружи; финальный лог «Приложение завершается» |

## `main.ColoredFormatter` / `format`

**Docstring в коде:** нет

```
"""Formatter: цветной [LEVEL] в записи root-логгера (ANSI), формат HH:MM:SS [LEVEL] message."""
```

## `main.RussianizeAiogramFilter` / `filter`

**Docstring в коде:** нет

```
"""Подменить английскую строку aiogram.event про Update id на русскую; ошибки разбора глотать."""
```

## `main._is_true`

**Docstring в коде:** нет

```
"""True, если строка value в множестве true/1/on/yes/y (без учёта регистра)."""
```

## `main.shutdown`

**Docstring в коде:** нет

```
"""По SIGINT/SIGTERM остановить основного бота, отменить прочие asyncio-задачи и остановить loop."""
```

## `main.start_services`

**Docstring в коде:** нет

```
"""Запустить Flask в потоке, автозапуск ботов по настройкам, планировщик на loop основного бота, ждать отмены."""
```

## `main.start_services._log_bot_status_soon`

**Docstring в коде:** нет. В коде уже есть `#` про диагностику через 3 с.

```
"""Через 3 секунды залогировать is_running основного и support-бота после автозапуска."""
```
