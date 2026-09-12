# Комментарии: `src/shop_bot/app.py`

**Это не runtime.** Одноразовый hotfix для файла панели. Модульный docstring **есть** (строки 3–11) — копируется:

```
Hotfix for shop_bot/webhook_server/app.py to resolve several syntax/runtime issues:
1) Replace erroneous decorator "@flask_@app.route" -> "@flask_app.route"
2) Fix unterminated f-string near the revoke message.
3) Ensure "enable_referral_days_bonus" is present in ALLOWED_BOOL_SETTINGS-style arrays with proper syntax.
Usage:
    python3 fix_app.py /path/to/app.py
Creates a backup app.py.bak before modifying.
```

(Фактический запуск: `python3 app.py <path>`, не `fix_app.py`.)

## `patch_file` (14–79)

**Docstring в коде:** нет

```
"""Прочитать path, применить три текстовых патча; если файл изменился — записать path.bak и перезаписать path."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 21 | replace decorator | `@flask_@app.route` → `@flask_app.route` |
| 26–30 | regex f-string | закрыть оборванный `else f"Удалось отозвать {…}` |
| 33–65 | `ensure_flag_in_list` | вставить `"enable_referral_days_bonus"` в первый `[...]` после имени списка |
| 41–52 | скобочный скан | depth по `[`/`]`, без учёта строк |
| 67–69 | три имени списков | ALLOWED_BOOL_SETTINGS / BOOLEAN_SETTINGS / ALLOWED_SETTINGS |
| 71–79 | запись | backup только если src != original |

## `patch_file.ensure_flag_in_list` (33–65)

```
"""Если список после list_name_pattern найден и флага в нём нет — дописать флаг перед закрывающей `]`."""
```

## Блок `__main__` (81–85)

Печать usage и `sys.exit(1)`, если нет ровно одного аргумента-пути.
