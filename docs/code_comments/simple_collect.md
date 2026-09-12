# Комментарии: `simple_collect.py`

Модульный docstring в коде:

```
Упрощенный скрипт для принудительного сбора метрик
```

`sys.path` += `src/`. Ручной прогон, не часть пакета бота.

## `collect_metrics_simple` (13–91)

**Docstring в коде:** есть

```
Простой сбор метрик
```

psutil: CPU (interval=1), RAM, диск `/`. Пишет `insert_resource_metric(scope='local', object_name='panel', …)` с raw_json timestamp. Потом `get_latest_resource_metric` и `get_metrics_series(..., since_hours=1, limit=10)`. True только если insert дал id и latest найден. ImportError (нет psutil) → False.

| Строки | Блок | Зачем |
|--------|------|--------|
| 19–31 | psutil | сбор и печать |
| 34–48 | insert | local/panel |
| 50–75 | проверка | latest + серия 1ч → True |
| 76–81 | нет id / нет latest | False |
| 83–91 | ImportError / Exception | False |

## `main` (93–108)

**Docstring в коде:** есть

```
Основная функция
```

Зовёт `collect_metrics_simple()`; печать успеха (ссылка `/monitor`, период 1ч) или просьба поставить psutil.
