# Комментарии: `src/shop_bot/webhook_server/apply_app_fix.py`

Одноразовый патчер `app.py`: бэкап `*.bak`, затем regex по `ALL_SETTINGS_KEYS` и `checkbox_keys`. Модульного docstring нет.

Скрипт (не функция): `argv[1]` — путь; иначе usage и `sys.exit(1)`. После правок пишет файл и печатает путь бэкапа.

В коде `#`: запятая перед `]`; разворот элементов; сборка «по одному на строку»; `checkbox_keys` list или set — привести к списку.

## `normalize_list` (13–23)

**Docstring в коде:** нет

```
"""Собрать отсортированный Python-list из quoted-строк block плюс must_have; убрать ведущую запятую перед ]."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 15 | `re.sub` `(?m)^\s*,\s*\]` | битый хвост списка |
| 17–20 | findall `"..."` + set | уникальные ключи; добавить must_have |
| 22–23 | join sorted | формат `[\n    "a",\n    "b"\n]` |

Вызовы в скрипте: `must_have={"enable_referral_days_bonus"}` для обоих присваиваний.
