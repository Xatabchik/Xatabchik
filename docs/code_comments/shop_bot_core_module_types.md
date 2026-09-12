# Комментарии: `src/shop_bot/core/module_types.py`

Типы манифеста плагина (`ModuleMeta`), статуса и карточки для UI. Модульного docstring нет. Существующие docstring классов — английские.

## `ModuleStatus` (8–14)

**Docstring в коде:** есть

```
Runtime status for a plugin module.
```

`str, Enum`: `enabled` / `disabled` / `error` / `missing`.

## `ModuleMeta` (18–65)

**Docstring в коде:** есть

```
Module manifest metadata.
```

`frozen` dataclass: id, name, version, description, author, requires, bot_entry, panel_entry, db_schema, db_cleanup, settings_schema, menu_items.

### `ModuleMeta.from_dict` (35–49)

**Docstring в коде:** нет

```
"""Build ModuleMeta from a dict: strip string fields; empty optional entries become None; requires/menu_items via list()."""
```

`id`/`name`/`version`/`description`/`author`: `str(data.get(...) or "").strip()`.  
`bot_entry` и остальные optional: `data.get(...) or None`.  
`requires` / `menu_items`: `list(data.get(...) or [])` — не копирует вложенные dict глубоко.

### `ModuleMeta.to_dict` (51–65)

**Docstring в коде:** нет

```
"""Return a plain dict of all fields; requires and menu_items as new lists."""
```

## `ModuleInfo` (69–93)

**Docstring в коде:** есть

```
Public-facing module information for UIs.
```

Не frozen. Поля: meta, status, enabled_at, error_message, has_settings, path.

### `ModuleInfo.to_dict` (79–93)

**Docstring в коде:** нет

```
"""Flatten meta + status.value + enabled_at/error_message/has_settings/path for JSON/UI. Omits bot_entry/panel_entry/db_* /settings_schema."""
```

`requires` и `menu_items` — копии списков из meta.
