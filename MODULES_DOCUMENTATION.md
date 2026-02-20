# Модули (Plugins) для Xatabchik

Этот документ описывает модульную систему и требования к сторонним модулям.

## Обзор

Модульная система позволяет добавлять обработчики бота и страницы панели без изменения ядра. Модули обнаруживаются в директории `modules/` при старте и могут включаться/выключаться во время работы через панель или Telegram-админку.

Ключевые свойства:
- Изоляция ошибок: сбои модулей не падают на ядро.
- Удаление данных при удалении модуля.
- Горячее включение/выключение без перезапуска процесса.
- Поддержка зависимостей между модулями.

## Структура модуля

Каждый модуль — это папка в `modules/`:

```
modules/
  my_module/
    __init__.py
    bot_handlers.py
    panel_routes.py
    db_schema.py
    db_cleanup.py
    settings_schema.py
```

Обязателен только `__init__.py`. Остальные файлы опциональны.

## Манифест модуля (`__init__.py`)

Модуль должен экспортировать `MODULE_META` типа `ModuleMeta`.

Пример:

```python
from shop_bot.core.module_types import ModuleMeta

MODULE_META = ModuleMeta(
    id="my_module",
    name="My Module",
    version="1.0.0",
    description="Module description",
    author="Author",
    requires=["other_module"],
    bot_entry="bot_handlers",
    panel_entry="panel_routes",
    db_schema="db_schema",
    db_cleanup="db_cleanup",
    settings_schema="settings_schema",
    menu_items=[
        {"label": "My Module", "url": "/modules/my_module/", "icon": "plug"}
    ],
)
```

### Поля манифеста

- `id`: уникальный идентификатор модуля. Должен совпадать с именем папки и соответствовать regex `[a-z0-9_]+`.
- `name`: читаемое название.
- `version`: версия (семантическая).
- `description`: описание.
- `author`: автор модуля.
- `requires`: список зависимостей (id модулей).
- `bot_entry`: имя файла (без .py), где определен `router`.
- `panel_entry`: имя файла (без .py), где определен `bp`.
- `db_schema`: имя файла (без .py), где определен `SCHEMA_SQL`.
- `db_cleanup`: имя файла (без .py), где определен `cleanup(db_conn)`.
- `settings_schema`: имя файла (без .py), где определен `SETTINGS`.
- `menu_items`: пункты меню панели, которые появятся в сайдбаре при включенном модуле.

## Интеграция с ботом (aiogram)

Если указан `bot_entry`, модуль должен экспортировать `router: aiogram.Router`.

```python
from aiogram import Router, F, types

router = Router()

@router.callback_query(F.data == "mod:my_module:ping")
async def handle_ping(callback: types.CallbackQuery) -> None:
    await callback.answer("pong")
```

### Безопасность callback_data

Чтобы модуль не мог перезаписать обработчики ядра, callback_data должен начинаться с одного из префиксов:
- `mod:<module_id>:`
- `<module_id>:`

Пример для модуля `my_module`:
- `mod:my_module:ping`
- `my_module:action`

Если callback_data не соответствует префиксу модуля, middleware его блокирует.

## Интеграция с панелью (Flask)

Если указан `panel_entry`, модуль должен экспортировать `bp: flask.Blueprint`.

```python
from flask import Blueprint, render_template

bp = Blueprint(
    "my_module",
    __name__,
    url_prefix="/modules/my_module",
    template_folder="templates",
)

@bp.route("/")
def index():
    return render_template("modules/my_module/index.html")
```

Рекомендуемый префикс URL: `/modules/<module_id>/`.

## Схема БД и удаление данных

### Схема

Если указан `db_schema`, модуль должен экспортировать `SCHEMA_SQL` (строка или список SQL-операторов).

Все таблицы модуля должны иметь префикс `<module_id>_`.

```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS my_module_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL
);
"""
```

### Очистка

Если указан `db_cleanup`, модуль должен экспортировать `cleanup(db_conn)`.

```python
def cleanup(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS my_module_items")
    cursor.execute("DELETE FROM bot_settings WHERE key LIKE 'my_module_%'")
    db_conn.commit()
```

Если `db_cleanup` не указан, при удалении модуля ядро удалит только настройки с префиксом `<module_id>_`. Таблицы модуля должны удаляться явно в `cleanup`.

## Настройки модуля

Если указан `settings_schema`, модуль должен экспортировать `SETTINGS`:

```python
SETTINGS = [
    {"key": "api_url", "label": "API URL", "type": "text", "default": ""},
    {"key": "enabled", "label": "Enable", "type": "boolean", "default": False},
    {"key": "max_count", "label": "Max", "type": "number", "default": 10},
]
```

Настройки хранятся в `bot_settings` с префиксом `<module_id>_`.

Поддерживаемые типы:
- `text`
- `number`
- `boolean`

## Жизненный цикл модуля

- **Discover**: при старте модули сканируются и регистрируются в `modules_registry`.
- **Enable**: применяется схема БД, создаются дефолтные настройки, подключаются Router и Blueprint.
- **Disable**: Router и Blueprint отключаются, данные остаются.
- **Delete**: запускается `cleanup`, удаляются настройки, удаляется запись из `modules_registry`, удаляется директория модуля.

Важно: удаление модуля физически удаляет его папку на диске.

## Изоляция ошибок

- Все импорты модулей внутри `try/except`.
- Ошибки логируются, модуль получает статус `error`.
- Ошибки обработчиков ловятся middleware и отправляются администраторам.

## Зависимости

Если модуль объявляет `requires`, его можно включить только после включения всех зависимостей. Удаление модуля, от которого зависят другие, блокируется.

## Правила безопасности

- Callback-данные должны иметь разрешенный префикс модуля.
- Таблицы БД должны быть с префиксом `<module_id>_`.
- Управление модулями доступно только администраторам.

## Шаблон модуля

Готовый шаблон находится в `modules/example_module/` (бот, панель, схема, очистка, настройки).
