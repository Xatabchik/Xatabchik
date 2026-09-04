# Комментарии: `src/shop_bot/data_manager/scheduler.py`

Фоновый цикл основного бота: истечение ключей, автопродление, рассылки, LTE/dual pool, sync с Remnawave, бэкапы, мониторинг, тикеты. Модульного docstring нет. Точка входа — `periodic_subscription_check` (тик 300 с). См. `SCHEDULER_DOCUMENTATION.md`.

`_maybe_sync_keys_with_panels` объявлена дважды (1268 и 1576); в runtime живёт вторая (перекрывает имя). `_legacy_check_traffic_boost_resets` и `_run_speedtests_for_all_hosts` в цикле не вызываются.

| Имя | Значение | Зачем |
|-----|----------|--------|
| `CHECK_INTERVAL_SECONDS` | 300 | пауза основного цикла |
| `NOTIFY_BEFORE_HOURS` | `{72, 48, 24, 1}` | окна напоминаний об истечении |
| `AUTO_RENEW_RETRY_COOLDOWN_HOURS` | 6 | пауза между попытками автопродления одного ключа |
| `SPEEDTEST_INTERVAL_SECONDS` | `8 * 3600` | троттлинг SSH-speedtest |
| `SYNC_KEYS_WITH_PANELS_INTERVAL_SECONDS` | `30 * 60` | `# heavy operation; don't run every 5 minutes` |
| `INACTIVE_USAGE_REMINDER_INTERVAL_SECONDS` / `FIRST_INACTIVE_REMINDER_DELAY_SECONDS` | `8 * 3600` | константы модуля; фактический интервал читается из настроек |
| `DUAL_LIMIT_DEFAULT_INTERVAL_SECONDS` | 120 | fallback `dual_limit_interval_sec` |
| `TICKET_MEDIA_PURGE_INTERVAL_SECONDS` | 3600 | TTL-проход вложений |

Модульные кэши: `notified_users`, `_auto_renew_attempts`, `_last_*_at`, `_last_resource_alert_at`.

## `format_time_left` (45–60)

**Docstring в коде:** нет

```
"""Русская фраза «N день/дня/дней» при hours≥24, иначе «N час/часа/часов» (правила %10/%100)."""
```

## `send_subscription_notification` (62–84)

**Docstring в коде:** нет

```
"""Отправить пользователю Markdown-напоминание об истечении и кнопки manage_keys / extend_key_{id}."""
```

Ошибка send: `telegram_reachability.handle_send_exception`; если не 403-unreachable — error-лог.

## `_cleanup_notified_users` (86–111)

**Docstring в коде:** нет

```
"""Убрать из notified_users ключи, которых нет в all_db_keys, и пустые словари пользователей."""
```

## `check_expiring_subscriptions` (113–151)

**Docstring в коде:** нет

```
"""Пройти get_all_keys и напомнить, если осталось (mark-1, mark] часов из NOTIFY_BEFORE_HOURS и метка ещё не слалась."""
```

Просроченные (`time_left < 0`) пропускаются. Даже при выключенных уведомлениях метка пишется в кэш (`break` после add).

| Строки | Блок | Зачем |
|--------|------|--------|
| 137–142 | not is_subscription_expiry_notifications_enabled | add hours_mark, break без send |
| 146–148 | иначе | send + add + break |

## `_parse_dt_safe` (154–175)

**Docstring в коде:** нет

```
"""Разобрать дату: пусто→None; T/Z нормализуются; форматы YYYY-MM-DD[ HH:MM[:SS]], иначе fromisoformat; провал→None."""
```

В коде `#`: ожидаемые длины строк для форматов.

## `_extract_used_bytes` (178–205)

**Docstring в коде:** есть

```
Пытаемся извлечь использованный трафик из payload пользователя Remnawave (если поле есть).
```

Не-dict → 0. Первое положительное из списка ключей (включая `up`/`down` по отдельности, не сумма). Иначе рекурсия в `traffic`/`usage`/`stats`.

## `_is_true` (208–209)

**Docstring в коде:** нет

```
"""True, если строка value в true/1/on/yes/y (регистр не важен)."""
```

## `_get_inactive_usage_reminder_enabled` (212–217)

**Docstring в коде:** есть

```
Глобальный переключатель напоминаний о нулевом использовании трафика.
```

Нет настройки → `"true"`.

## `_get_inactive_usage_reminder_interval_hours` (220–232)

**Docstring в коде:** есть

```
Интервал напоминаний в часах (также используется как задержка перед первым напоминанием).
```

Настройка `inactive_usage_reminder_interval_hours`, default 8; запятая→точка; клип 1..168.

## `_get_inactive_usage_reminder_interval_seconds` (235–236)

**Docstring в коде:** нет

```
"""Интервал напоминаний в секундах: hours * 3600."""
```

## `_parse_origin_meta_from_description` (239–249)

**Docstring в коде:** нет

```
"""json.loads(description) если получился dict; иначе None."""
```

## `_try_int` (252–267)

**Docstring в коде:** нет

```
"""Привести к int: None/пусто→None; bool/int/float; строка через float(запятая→точка); ошибка→None."""
```

## `_resolve_hwid_device_limit_for_key` (270–314)

**Docstring в коде:** есть

```
Определить допустимый лимит устройств для ключа.

Приоритет:
  1) Remnawave поле hwidDeviceLimit (если есть)
  2) План из vpn_keys.description (origin meta -> plan_id)
  3) Настройка trial_device_limit (для триала)
```

Лимит учитывается только если `> 0`. Триал: `meta.is_trial` или `tag == "trial"`.

## `_extract_device_ids` (317–347)

**Docstring в коде:** нет

```
"""Список уникальных id устройств из list/dict (deviceId/id/uuid/hwid/…); dict → рекурсия в devices/items/data/response."""
```

## `check_device_limit_violations` (350–476)

**Docstring в коде:** есть

```
Проверяет превышение лимитов привязанных HWID устройств и уведомляет админов.
```

Нет admin_ids → выход. Просроченные ключи пропускаются. Cooldown 6 ч, если `devices_count <= last_count`. HTML-сообщение админам; статистика в `key_usage_monitor`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 392–394 | нет лимита | continue |
| 421–428 | count ≤ limit | сброс overlimit_* если были |
| 432–433 | count ≤ last и cooldown | не слать снова |
| 461–472 | send + update overlimit |

## `check_traffic_boost_resets` (479–589)

**Docstring в коде:** есть

```
Ежемесячный сброс трафика ключа до базовых значений тарифа.

Дата сброса (`next_traffic_reset_at`) отсчитывается от дня покупки ключа
и не зависит от использованного трафика. По достижении этой даты:
  - основной пул (если тариф лимитный): сброс used traffic на Remnawave,
    лимит возвращается к `plans.traffic_limit_bytes`, докупленный буст сгорает,
    `traffic_limit_strategy` остаётся MONTH_ROLLING;
  - LTE-пул (если задан `plans.lte_limit_bytes`): новый расчётный период —
    baseline переустанавливается, докупленный LTE-буст сгорает;
  - для безлимитного основного пула панель не трогаем — крутим только LTE
    и дату следующего сброса;
  - дата следующего сброса сдвигается на 1 календарный месяц вперёд.
```

Нет `next_traffic_reset_at` или дата в будущем — skip. Нет uuid при has_main_limit — continue без сдвига даты. HTTP: `reset_user_traffic`, `update_user_traffic_limit`. БД: `update_key_fields`, `request_key_lte_baseline_reset`.

## `enforce_dual_traffic_limits` (592–917)

**Docstring в коде:** есть

```
Двухуровневый учёт трафика (основной пул + независимый LTE-пул на premium-нодах).

- Основной пул = суммарный расход по ВСЕМ ключам пользователя vs (лимит тарифа + докупленный buster).
- LTE-пул = расход по ключам на LTE-нодах vs (лимит тарифа + докупленный LTE-буст),
  см. `database.resolve_lte_limit_bytes()` — единая формула с той, что показывается
  пользователю в карточке ключа.

Действия (идемпотентны — состояние хранится в vpn_keys.remote_access_state, чтобы не спамить API):
  * Основной исчерпан -> disable_user на ВСЕХ хостах пользователя ('disabled_main').
  * LTE исчерпан (и основной не исчерпан) -> для хостов с активным сквадом класса 'lte'
    точечно убираем ТОЛЬКО этот сквад из activeInternalSquads ('disabled_premium_squad'),
    Base-сквад остаётся активным. Хосты без такого сквада не участвуют ни в подсчёте
    LTE-расхода, ни в его энфорсинге (см. миграцию node_class -> squad_class='lte').
  * Иначе -> восстановление доступа (добавление LTE-сквада обратно либо enable_user для
    legacy-состояний 'disabled_premium'/'disabled_main').

Если передан `bot`, пользователю отправляется уведомление при первом переходе в отключённое
состояние LTE-пула и при восстановлении доступа к нему (не чаще одного раза за переход).
```

Группировка ключей по user_id. Ошибка статистики нод → ключ в `lte_incomplete_keys`, состояние не меняется. Telegram: HTML про исчерпание/восстановление LTE; `handle_send_exception`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 647–657 | get_user_used_traffic | сумма в основной пул |
| 692–699 | not should_account_lte_traffic | без снапшотов LTE |
| 708–751 | ноды LTE-сквада | snapshots; ошибка → incomplete |
| 767–784 | baseline reset / first init | commit_key_lte_baseline |
| 820–832 | desired_state | main / lte / incomplete skip / enabled |
| 835–851 | state уже нужный | сверка remove_squad если disabled_premium_squad |
| 854–868 | смена | remove_squad / disable_user / add_squad / enable_user |
| 881–915 | бот | уведомления LTE-перехода |

## `_legacy_check_traffic_boost_resets` (920–1004)

**Docstring в коде:** есть

```
Откатывает докупленный буст трафика после ежемесячного сброса лимита на сервере (устаревшая эвристика,
сохранена для истории; активно используется check_traffic_boost_resets на основе next_traffic_reset_at).
```

По коду: сброс, если `last_used > 0 and used_bytes < last_used * 0.5`. Не вызывается из `periodic_subscription_check`.

## `check_inactive_usage_reminders` (1007–1100)

**Docstring в коде:** есть

```
Если после выдачи ключа у пользователя не было подключенных устройств/трафика — напоминать с заданным интервалом.
```

Выключенный флаг → return. Пропуск: истёк, моложе first_delay, уже `first_seen_usage_at`, не вышел интервал с `last_reminder_at`. Устройства или used_bytes > 0 → пишется `first_seen_usage_at`. Иначе HTML + `create_inactive_usage_reminder_keyboard`.

## `sync_keys_with_panels` (1103–1265)

**Docstring в коде:** нет

```
"""Сверить vpn_keys каждого сквада с list_users: просрочка>5д удалить, расхождение обновить, orphan userN привязать."""
```

Нет сквадов — выход. Нет `squad_uuid` — skip хоста.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1156–1172 | expiry < now-5d | delete_client_on_host + delete_key_by_email |
| 1187–1200 | remote есть, drift>1с или другой subscription_url | update_key_status_from_server |
| 1201–1208 | нет на панели | update_key_status_from_server(None), не удалять |
| 1210–1260 | remote без локальной строки | email `user(\d+)` → record_key_from_payload |

## `_maybe_sync_keys_with_panels` (1268–1281)

**Docstring в коде:** есть

```
sync_keys_with_panels is expensive (list all users on each host).

If it runs too often, it can delay bot responses. Throttle it.
```

Троттлинг по `_last_sync_keys_with_panels_at`. Имя перекрыто объявлением на 1576–1586.

## `_maybe_enforce_dual_traffic_limits` (1284–1300)

**Docstring в коде:** есть

```
Учёт двух пулов трафика (основной + LTE) — интервал настраивается через bot_settings.dual_limit_interval_sec.
```

Интервал ≤0 → 120. Вызывает `enforce_dual_traffic_limits(bot)`.

## `_notify_auto_renew_success` (1303–1321)

**Docstring в коде:** нет

```
"""HTML: ключ продлён, списано с баланса; кнопки manage_keys и show_profile."""
```

## `_notify_auto_renew_no_balance` (1324–1343)

**Docstring в коде:** нет

```
"""HTML: нехватка баланса; кнопки top_up_start и manage_keys."""
```

## `check_auto_renewals` (1346–1440)

**Docstring в коде:** нет

```
"""Если auto_renew_globally_enabled: списать баланс, продлить ключ на панели, иначе вернуть деньги и уведомить."""
```

Ключи из `get_keys_for_auto_renew(hours_before)`. Нет plan / price≤0 — skip. Дни: `duration_days` или `months*30` или 30. Cooldown `AUTO_RENEW_RETRY_COOLDOWN_HOURS` через `_auto_renew_attempts`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1398–1401 | deduct_from_balance False | notify no_balance |
| 1411–1432 | create_or_update_key_on_host ok | update expire, apply_key_monthly_reset_fields(restart_cycle=False), pop attempt, notify success |
| 1433–1438 | None / Exception | add_to_balance refund |

## `check_broadcast_campaigns` (1443–1482)

**Docstring в коде:** есть

```
Send queued broadcast campaigns to inactive subscribers.
```

Неактивные кампании skip. `mark_broadcast_run` до рассылки. `sleep(0.05)` между send. 403 → `handle_send_exception`. Успехи → `record_broadcast_sends`.

## `_ticket_files_present` (1489–1498)

**Docstring в коде:** есть

```
Дешёвая проверка: нет каталога или он пуст — TTL не запускаем.
```

## `_maybe_purge_closed_ticket_media` (1501–1518)

**Docstring в коде:** есть

```
TTL вложений. Отдельный task не создаём; если файлов нет — сразу выход.
```

Не чаще раза в 3600 с. Зовут `purge_expired_closed_ticket_media`.

## `_maybe_auto_close_idle_tickets` (1521–1528)

**Docstring в коде:** есть

```
После ответа админа пользователь молчит N дней — закрываем тикет. SQL сразу, Telegram в фоне.
```

Обёртка `idle_close.maybe_auto_close_idle_tickets`.

## `periodic_subscription_check` (1531–1573)

**Docstring в коде:** нет

```
"""Вечный цикл фоновых задач основного бота: sleep 10, затем тик CHECK_INTERVAL_SECONDS."""
```

Пользовательские проверки только если `bot_controller` running и есть Bot. Метрики/speedtest/sync — и без бота (алерты/бэкап требуют Bot).

| Строки | Блок | Зачем |
|--------|------|--------|
| 1537–1541 | всегда | sync, dual limits, ticket purge/close |
| 1544 | speedtest SSH-цели | |
| 1548–1553 | bot | backup, resource metrics |
| 1555–1563 | running+bot | expiry, autorenew, broadcast, inactive, hwid, monthly reset |

## `_maybe_sync_keys_with_panels` (1576–1586)

**Docstring в коде:** есть

```
Sync with Remnawave panels is expensive; throttle to reduce bot latency.
```

Второе объявление: троттлинг по `_last_sync_with_panels_at` (другой глобал, чем у 1268). Это имя, которое видит цикл.

## `_maybe_run_periodic_speedtests` (1588–1597)

**Docstring в коде:** нет

```
"""Не чаще SPEEDTEST_INTERVAL_SECONDS вызвать _run_speedtests_for_all_ssh_targets."""
```

Хостовый `_run_speedtests_for_all_hosts` отсюда не зовётся.

## `_run_speedtests_for_all_hosts` (1599–1627)

**Docstring в коде:** нет

```
"""Для каждого xui-хоста run_both_for_host с таймаутом 180 с (asyncio.timeout или wait_for)."""
```

В основном цикле не вызывается.

## `_run_speedtests_for_all_ssh_targets` (1629–1655)

**Docstring в коде:** нет

```
"""Для каждой speedtest_ssh_targets: run_and_store_ssh_speedtest_for_target, таймаут 180 с."""
```

## `_maybe_collect_resource_metrics` (1659–1739)

**Docstring в коде:** есть

```
Периодический сбор метрик (локально + SSH на хостах) и отправка алертов при превышении порогов.
Читает настройки:
  - monitoring_enabled (true/false)
  - monitoring_interval_sec (по умолчанию 300)
  - monitoring_cpu_threshold, monitoring_mem_threshold, monitoring_disk_threshold (проценты)
  - monitoring_alert_cooldown_sec (по умолчанию 3600)
```

`monitoring_enabled` не `"true"` → return. Интервал не меньше 30 с. Локально: cpu/mem/disk + net. Хосты только с `ssh_host` и `ssh_user`; cpu в insert/alert для хоста не передаётся. Вложенный `_to_int` (1681–1685) в инвентаре нет.

## `_maybe_run_daily_backup` (1742–1770)

**Docstring в коде:** есть

```
Ежедневный автобэкап базы и отправка админам. Интервал задаётся в настройках backup_interval_days.
```

`days <= 0` → return (выкл). Иначе `days * 86400`. `create_backup_file` → `send_backup_to_admins` → `cleanup_old_backups(keep=7)`. `_last_backup_run_at` ставится даже если zip не создался (если не было критического except вокруг всего блока — ставится в конце try после попытки).

По коду: `_last_backup_run_at = now` внутри try после create/send/cleanup, в том числе когда `zip_path` пуст.

## `_maybe_alert` (1773–1870)

**Docstring в коде:** нет

```
"""Сравнить cpu/mem/disk с порогами; critical и warning с разным cooldown; без bot — выход."""
```

Warning-порог = `max(50, thr-20)`. Critical cooldown `max(60, cooldown_sec)`; warning `max(300, cooldown_sec*2)`. Ключ кэша: `(scope, name, level, типы)`.

## `_send_alert` (1873–1933)

**Docstring в коде:** есть

```
Отправка алерта админам
```

HTML админам из `get_admin_ids()`. scope local/host/target иначе `scope:name`. Ошибка send глотается.
