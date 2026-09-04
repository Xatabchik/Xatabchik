# Комментарии: `src/shop_bot/factory_bot/middleware.py`

Статистика клонов и TTL-кэш `franchise_enabled`. Модульного docstring нет.

`_FRANCHISE_ENABLED_CACHE`: `value` / `ts`.  
`_FRANCHISE_ENABLED_TTL_SEC = 2.0`.

## `invalidate_franchise_enabled_cache` (13–15)

**Docstring в коде:** нет

```
"""Сбросить кэш: value=None, ts=0 — следующий franchise_enabled_cached() снова читает SQL."""
```

## `franchise_enabled_cached` (18–32)

**Docstring в коде:** есть

```
Лёгкий кэш флага франшизы, чтобы middleware не ходила в SQL на каждое сообщение.
```

Hit: `value is not None` и возраст `< 2.0` с `time.monotonic()`.  
Miss: `rw_repo.get_setting("franchise_enabled")`; true если строка в `1/true/yes/on` (без регистра). Исключение → `False`. Затем пишет кэш и возвращает `val`.

## `FactoryStatsMiddleware` (35–65)

**Docstring в коде:** есть

```
Tracks basic stats (messages + unique users) per factory bot instance.
```

Вешается на message и callback_query клона в `ManagedBotsService.start_bot`.

### `FactoryStatsMiddleware.__call__` (37–65)

**Docstring в коде:** нет

```
"""Если франшиза выключена — сразу handler; иначе record_factory_activity и contextvar factory_bot_id на время handler."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 43–44 | not franchise_enabled_cached | без SQL статистики |
| 47–56 | bot + event_from_user | `resolve_factory_bot_id`, `record_factory_activity`, `data["factory_bot_id"]`, `set_current_factory_bot_id`; ошибка → token=None |
| 58–65 | try/finally | handler; `reset_current_factory_bot_id(token)` если token был; сброс глотает исключение |
