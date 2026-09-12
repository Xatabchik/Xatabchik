# Комментарии: `simple_monitor_test.py`

Модульный docstring в коде:

```
Упрощенный скрипт для тестирования мониторинга без дополнительных зависимостей
```

`sys.path` += `src/`. Диагностика, не pytest.

## `test_database` (14–88)

**Docstring в коде:** есть

```
Проверяем базу данных
```

Ищет первый существующий из `users-20251005-173430.db`, `users.db`, `/app/project/users.db`. Нет файла / нет таблицы `resource_metrics` → False. Есть таблица: печатает COUNT; пусто → False. Иначе последние 3 строки и COUNT `local`/`panel` за последний час. True **только** если count_1h > 0.

## `test_settings` (90–115)

**Docstring в коде:** есть

```
Проверяем настройки
```

Читает `monitoring_enabled` и `monitoring_interval_sec`. По коду: если `monitoring_enabled != "true"` — **пишет** `update_setting("monitoring_enabled", "true")` и `monitoring_interval_sec` = `"300"`. Exception → False, иначе True.

## `test_metrics_collection` (117–143)

**Docstring в коде:** есть

```
Тестируем сбор метрик без psutil
```

По коду: всё же `import psutil` и снимает CPU/RAM/диск. ImportError → warning и **True** (не падает). Другой Exception → False.

## `insert_test_metric` (145–185)

**Docstring в коде:** есть

```
Вставляем тестовую метрику
```

psutil + `insert_resource_metric(local/panel)`. Есть metric_id → True. ImportError → True (пропуск). Иначе False.

## `main` (187–230)

**Docstring в коде:** есть

```
Основная функция
```

Порядок: database → settings → metrics; insert только если `metrics_ok`, иначе `insert_ok = True`. «Готова к работе», если db_ok **и** settings_ok (метрики могут быть ложными).
