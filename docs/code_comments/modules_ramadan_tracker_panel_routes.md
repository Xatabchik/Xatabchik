# Комментарии: `modules/ramadan_tracker/panel_routes.py`

Модульного docstring нет. Blueprint `ramadan_tracker`, prefix `/modules/ramadan_tracker`. Редиректы hardcoded (`/modules/ramadan_tracker/payouts`), не `url_for` (кроме мёртвой строки в `payouts_complete`).

Баллы в топе панели — **не** формула из README (10/10/1 за 100/20/10). SQL: `morning_adhkar=1` → +1, `evening_adhkar=1` → +1, плюс сырой `salawat_count`. Таравих в score не входит.

## `_get_global_stats` (15–37)

**Docstring в коде:** нет

```
"""Агрегаты ramadan_tracker_daily: users, morning/evening/salawat/taraweeh_total, adhkar_total=утро+вечер."""
```

`taraweeh_total` — число дней с `taraweeh_place IN ('mosque', 'home')`, не баллы.

## `_get_top_rows` (40–63)

**Docstring в коде:** нет

```
"""Топ user_id по score=Σ(утром 1 + вечером 1 + salawat_count), LIMIT (default 10)."""
```

## `_get_withdrawal_requests` (66–109)

**Docstring в коде:** нет

```
"""До 200 строк reward_users с requested_at; PRAGMA подставляет completed_at/proof_file_id если колонок ещё нет."""
```

В коде `#` про проверку колонок. С обеими колонками: pending (`completed_at IS NULL`) сверху, затем `requested_at DESC`. Без колонок — только `requested_at DESC`, в dict дописывает None.

## `index` (113–120)

**Docstring в коде:** нет

```
"""GET `/`: статистика + топ-10 в modules/ramadan_tracker/index.html."""
```

## `payouts` (124–129)

**Docstring в коде:** нет

```
"""GET `/payouts`: список запросов вывода в payouts.html."""
```

## `payouts_delete` (133–143)

**Docstring в коде:** нет

```
"""POST `/payouts/delete`: если есть withdrawal_id — SET requested_at=NULL (строку не удаляет), redirect на /payouts."""
```

## `payouts_complete` (147–162)

**Docstring в коде:** нет

```
"""POST `/payouts/complete`: SET completed_at=CURRENT_TIMESTAMP; нет колонки — проглотить OperationalError; redirect на /payouts."""
```

`proof_file_id` не трогает. Строка `return redirect(url_for("ramadan_tracker.payouts"))` после первого `return` недостижима.
