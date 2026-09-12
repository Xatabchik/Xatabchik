# Комментарии: `modules/ramadan_tracker/db_schema.py`

Модульного docstring нет. Ядро ждёт `SCHEMA_SQL()` → список SQL-строк.

## `SCHEMA_SQL` (5–117)

**Docstring в коде:** есть

```
Генерирует SQL схему и автоматически выполняет миграции.
```

По коду: **не выполняет** DDL против рабочей `database.DB_FILE`. Собирает statements и возвращает список. Проверка колонок идёт по другому пути: `Path(__file__).parent.parent.parent / "shop_bot" / "data" / "database.db"` (корень репо + `shop_bot/data/database.db`). Если файла нет или PRAGMA упал — миграций нет, только `base_schema`.

`base_schema` (один элемент списка): CREATE IF NOT EXISTS пяти таблиц; INSERT OR IGNORE кнопки `🌙 Рамадан трекер` / `mod:ramadan_tracker:menu` в `main_menu`; UPDATE той же кнопки (text, callback, width=2, active=1).

Миграции (если таблица есть и колонки нет):

- `completed_at TIMESTAMP DEFAULT NULL`
- `proof_file_id TEXT DEFAULT NULL`

на `ramadan_tracker_reward_users`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 10 | db_file | не DB_FILE ядра |
| 13–85 | base_schema | таблицы + кнопка меню |
| 90–110 | PRAGMA table_info | только если db_file.exists() |
| 112–117 | result | `[base_schema] + ALTER…` |
