# Комментарии: `modules/ramadan_tracker/db_cleanup.py`

Модульного docstring нет. Хук выгрузки: открытый `db_conn` от ядра.

## `cleanup` (1–10)

**Docstring в коде:** нет

```
"""DROP пяти таблиц ramadan_tracker_*, стереть settings LIKE 'ramadan_tracker_%' и кнопку main_menu/ramadan_tracker, commit."""
```

Таблицы по коду: `ramadan_tracker_daily`, `_state`, `_rewards`, `_reward_periods`, `_reward_users`. Кнопка: `button_configs` где `menu_type = 'main_menu'` и `button_id = 'ramadan_tracker'`.
