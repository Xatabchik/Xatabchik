# Комментарии: `src/shop_bot/webhook_server/app.py` (часть 2)

Продолжение вложенных хендлеров `create_webhook_app`: ключи (смена тарифа, трафик, устройства, создание, срок, bulk-extend), SSH/спидтесты, поддержка, настройки и модули, хосты/сквады, старт-стоп ботов, пользователи, тарифы — от `admin_key_change_plan_route` до `update_plan_route`. Модульного docstring нет.

Все имена ниже — вложенные в `create_webhook_app`. У маршрутов стоит `@login_required`, кроме `block_ticket_files_dir` и `support_ticket_file` (там своя проверка сессии).

Маршруты этой части **не** вызывают `process_successful_payment`. Выдача ключа из панели (`create_key_route`, `create_key_ajax_route`) идёт напрямую: `remnawave_api.create_or_update_key_on_host` + `record_key_from_payload`. Оплаченный fulfillment вебхуков — в следующих частях (`_dispatch_payment_processing`).

---

## `create_webhook_app.admin_key_change_plan_route` (3001–3085)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/change-plan`.

```
"""Сменить тариф ключа на панели Remnawave и в локальной записи, не трогая срок действия."""
```

В коде `#`: срок не менять; лимит тарифа `None`/0 → явно `0` в Remnawave (иначе `create_or_update_key_on_host` подставит дефолт сквада и безлимит «прилипнет»).

| Строки | Блок | Зачем |
|--------|------|--------|
| 3002–3015 | key / plan / host+email | 404/400: `not_found`, `plan_required`, `plan_not_found`, `invalid_key` |
| 3018–3025 | expiry_ms | `expire_at` или `expiry_date`, первые 19 символов `%Y-%m-%d %H:%M:%S` UTC; ошибка → None |
| 3032–3048 | лимиты | traffic и hwid: не число/`None`/`''` → 0; отрицательные → 0 |
| 3048 | strategy | `remnawave_traffic_limit_strategy_for_plan(plan)` |
| 3051–3065 | панель | `create_or_update_key_on_host` (+ `plan_id`); Exception / пустой result → 500 `host_failed` |
| 3067–3083 | локально | description JSON `plan_id`/`plan_name`/`months`; `traffic_boost_bytes=0`; `apply_key_monthly_reset_fields(..., restart_cycle=True, expire_main_boost=True)`; сбой — warning, JSON всё равно ok |

`process_successful_payment` не вызывается.

## `create_webhook_app.admin_key_add_traffic_route` (3089–3146)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/add-traffic`.

```
"""Добавить основной трафик ключу (ГБ → байты) на панели и в `traffic_boost_bytes`."""
```

В коде `#`: докупка запрещена, если у тарифа лимит 0/`None` (безлимит не должен стать ограниченным бустом).

| Строки | Блок | Зачем |
|--------|------|--------|
| 3093–3102 | gb / план | `gb` ≤0 → `invalid_amount`; `_resolve_key_plan` без лимита → `unlimited_plan` |
| 3111–3120 | lookup | `lookup_panel_user` + `panel_user_ref_from_payload` (обновить uuid) |
| 3122–3129 | лимит | `trafficLimitBytes` панели, иначе локальный; `new_limit` / `new_boost` = текущее + add_bytes |
| 3131–3139 | панель | нет uuid → `no_remote_user`; `update_user_traffic_limit` не ok → `host_failed` |
| 3141–3144 | БД | `update_key_fields`; сбой — warning, JSON ok |

## `create_webhook_app.admin_key_add_lte_traffic_route` (3150–3209)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/add-lte-traffic`.

```
"""Начислить LTE-буст ключу и по возможности сразу вернуть premium-доступ."""
```

В коде `#`: только тариф с `lte_limit_bytes` > 0; начисление аддитивное и атомарное на ключ (baseline не сдвигать); при `disabled_premium_squad` — `add_squad_to_user`, не `enable_user`; если restore не вышел — буст уже есть, дожмёт `enforce_dual_traffic_limits`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 3154–3161 | gb / план | ≤0 → `invalid_amount`; нет LTE-пула → `no_lte_plan` |
| 3170–3177 | boost | `add_key_lte_boost_bytes`; Exception / None → 500 `lte_state_failed` |
| 3180–3207 | restore | сквад класса `lte` / хост `premium`; state `disabled_premium` → `enable_user`; `disabled_premium_squad` + сквад → `add_squad_to_user`; ok → `remote_access_state='enabled'` |

JSON: `{"ok": True, "lte_boost_bytes": new_boost}` даже если restore упал.

## `create_webhook_app.admin_key_delete_device_route` (3213–3239)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/devices/delete`.

```
"""Удалить одно HWID-устройство ключа на Remnawave по полю формы `hwid`."""
```

Нет ключа → 404; пустой hwid → `hwid_required`; нет `remnawave_user_uuid` → `no_remote_user`. `delete_hwid_device`; не ok → `host_failed`. Локальную таблицу устройств не трогает.

## `create_webhook_app.admin_key_delete_all_devices_route` (3243–3292)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/devices/delete-all`.

```
"""Снять все HWID ключа: список с панели, затем `delete_hwid_device` по каждому."""
```

Список: `get_hwid_devices_for_user`; dict — первый list среди `devices`/`response`/`data`/`items`; иначе list payload. Ошибка получения → пустой список (не 500). hwid из `hwid` / `hwId` / `id`. JSON: `ok` = `failed == 0`, плюс `deleted`/`failed`/`total` (total = длина сырого списка, включая записи без hwid).

## `create_webhook_app.admin_get_plans_for_host_json` (3296–3310)

**Docstring в коде:** нет. GET `/admin/hosts/<host_name>/plans`.

```
"""JSON тарифов хоста: plan_id, plan_name, months, price, hwid_device_limit."""
```

`get_plans_for_host`; Exception → 500 с `str(e)`.

## `create_webhook_app.create_key_route` (3314–3398)

**Docstring в коде:** нет. POST `/admin/keys/create` (обычная форма, не ajax).

```
"""Создать персональный ключ на хосте и записать в БД; уведомить пользователя в Telegram."""
```

`process_successful_payment` не вызывается.

| Строки | Блок | Зачем |
|--------|------|--------|
| 3316–3326 | поля | user_id/host/uuid/email/expiry/hwid; битый разбор → flash «Проверьте поля ключа.» |
| 3328–3335 | дефолты | пустой uuid → `uuid4`; пустой email → `generate_key_email_for_user` или `{user_id}-{ts}@bot.local` |
| 3337–3342 | hwid | пусто → None; иначе `max(0, int(float(...)))` |
| 3346–3359 | панель | `create_or_update_key_on_host` без plan/traffic; пустой result → flash danger |
| 3362–3374 | БД | uuid/expiry из payload; `record_key_from_payload` |
| 3377–3397 | Telegram | если bot и new_id: HTML с connection_string; loop running → `run_coroutine_threadsafe`, иначе `asyncio.run` |

Редирект на referrer или `admin_keys_page`.

## `create_webhook_app.create_key_ajax_route` (3402–3651)

**Docstring в коде:** есть (дословно):

```
"""Создание ключа через панель: персонального либо универсального подарочного токена."""
```

POST `/admin/keys/create-ajax`. `process_successful_payment` не вызывается. `mode` по умолчанию `personal`.

Общая подготовка: host и `plan_id` обязательны; `expiry_date` ISO → UTC ms или `invalid_expiry`; дни = `months*30` + `custom_days`; лимит/strategy с тарифа; description JSON `v=1, source=admin, plan_id, plan_name, months`. Форма hwid перекрывает тарифный.

### mode `personal` (3471–3553)

user_id + email (или generate / fallback `@bot.local`); нет пользователя → `user_not_found`. Если нет expiry и `days_total>0` — now+days UTC. Панель → `record_key_from_payload` + `apply_key_monthly_reset_fields(restart_cycle=True)` + опционально comment. Telegram — как в `create_key_route`. JSON: key_id, uuid, expiry_ms, connection.

### mode `gift` (3555–3649)

В коде `#`: как подарок в боте (`user_gifts` + ссылка `gift_<code>`), но `from_user_id=0`, до активации ключ ничей.

Email `gift-{hex}@bot.local` с суффиксом `-N` пока `get_key_by_email` свободен. Панель: tag `user_gift`, description comment или `'Gift key (created via admin panel)'`. Запись `user_id=0`, tag `user_gift`. `create_user_gift(from_user_id=0)` → `link_key_to_gift`. Ссылка: `domain/start?start=gift_{code}`, иначе `t.me/{bot_username}?start=gift_{code}`, иначе None. Нет gift_result → 500 `gift_record_failed` (ключ к этому моменту уже в БД).

Иной mode → 400 `unsupported_mode`.

## `create_webhook_app.generate_key_email_route` (3655–3664)

**Docstring в коде:** нет. GET `/admin/keys/generate-email`.

```
"""Сгенерировать email ключа для `user_id` из query (`generate_key_email_for_user`)."""
```

Не int → 400 `invalid user_id`. Exception генерации → 500 `str(e)`.

## `create_webhook_app.delete_key_route` (3668–3681)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/delete`.

```
"""Best-effort удалить клиента на хосте, затем `delete_key_by_id`; flash и редирект."""
```

Ошибки Remnawave и чтения ключа глотаются. Локальное удаление выполняется всегда.

## `create_webhook_app.adjust_key_expiry_route` (3685–3755)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/adjust-expiry`.

```
"""Сдвинуть срок ключа на `delta_days` (панель + БД) и уведомить владельца."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3687–3692 | delta / key | не int → `invalid_delta`; нет ключа → 404 |
| 3695–3708 | текущая дата | isoformat, иначе `%Y-%m-%d %H:%M:%S`, иначе utcnow; + timedelta |
| 3711–3720 | панель | `create_or_update_key_on_host` только с новым expiry; нет `expiry_timestamp_ms` → 500 |
| 3723–3730 | БД | `update_key` uuid / expire_at_ms / subscription_url; fail → `db_update_failed` |
| 3733–3751 | Telegram | дата из payload; loop running → threadsafe, иначе `asyncio.run` |

Внешний except → 500 `str(e)`.

## `create_webhook_app.sweep_expired_keys_route` (3759–3833)

**Docstring в коде:** нет. POST `/admin/keys/sweep-expired`.

```
"""Пройти все ключи: истёкшие удалить на хосте и в БД, уведомить владельца."""
```

Дата: isoformat, `Z`→`+00:00`, `%Y-%m-%d %H:%M:%S`; aware → UTC naive. `exp_dt > now` или нет даты — skip. Хост пустой → хост сквада по `squad_uuid`. `delete_client_on_host` вложенный except pass; затем всегда `delete_key_by_id` и `removed += 1`. Ошибка внешнего try → `failed += 1`. Flash: «Удалено … Ошибок: …».

## `create_webhook_app._parse_bulk_expiry_params` (3835–3853)

**Docstring в коде:** есть (дословно):

```
"""Общие параметры модалки bulk-extend: mode=days|date + days / expire_at."""
```

`mode` не `days`/`date` → `days`. days: `None` или `0` → ошибка (отрицательные дни допустимы). date: пустой `expire_at` → ошибка. Успех: `({mode, days, expire_at}, None)`.

## `create_webhook_app._apply_bulk_expiry_to_ids` (3855–3875)

**Docstring в коде:** нет

```
"""Для каждого id: `extend_key(days)` или `set_key_expiry(expire_at)`; вернуть ok/fail/failed_ids."""
```

Не ok и Exception считаются fail; id пишется в `failed_ids`.

## `create_webhook_app._flash_bulk_expiry_result` (3877–3883)

**Docstring в коде:** нет

```
"""Flash итога bulk-extend: счётчики и до 30 id ошибок (+ хвост)."""
```

`fail_n==0` → success, иначе warning.

## `create_webhook_app._dispatch_bulk_expiry` (3891–3974)

**Docstring в коде:** нет

```
"""Запустить массовое изменение срока: синхронно при `BULK_EXTEND_SYNC`, иначе фон + сразу redirect."""
```

В коде `#` перед функцией: HTTP дольше nginx `proxy_read_timeout`; без фона браузер ловит 504.

`BULK_EXTEND_SYNC` → `_run()` + flash результата. Иначе lock: уже running → flash «уже выполняется»; иначе daemon-поток `shopbot-bulk-expiry`. Старт потока упал → сбросить флаг и re-raise. Фоновый итог только в лог (flash «идёт в фоне»).

### `create_webhook_app._dispatch_bulk_expiry._run` (3905–3931)

**Docstring в коде:** нет

```
"""Пролог/эпилог в лог и вызов `_apply_bulk_expiry_to_ids`; вернуть ok/fail/ids."""
```

### `create_webhook_app._dispatch_bulk_expiry._job` (3947–3957)

**Docstring в коде:** нет

```
"""Обёртка фона: `_run()`, exception в лог, в `finally` снять `_bulk_expiry_running`."""
```

## `create_webhook_app.bulk_extend_keys_route` (3978–4006)

**Docstring в коде:** есть (дословно):

```
"""Режим 1: изменить срок у выбранных key_ids (чекбоксы на странице)."""
```

POST `/admin/keys/bulk-extend`. В коде `#`: unique, stable order (`dict.fromkeys`). Пустой выбор / ошибка params → flash. `label="SELECTED"`, sample первых 20 id.

## `create_webhook_app.bulk_extend_all_keys_route` (4010–4030)

**Docstring в коде:** есть (дословно):

```
"""Режим 2: изменить срок у ВСЕХ ключей в vpn_keys (игнорирует фильтры/выбор)."""
```

POST `/admin/keys/bulk-extend-all`. В коде `#`: переданные key_ids игнор — только `get_all_key_ids()`. Пустая БД → flash. `label="ALL"`.

## `create_webhook_app.bulk_extend_user_keys_route` (4034–4066)

**Docstring в коде:** есть (дословно):

```
"""Изменить срок у всех ключей одного пользователя (карточка пользователя)."""
```

POST `/admin/keys/bulk-extend-user`. `user_id` ≤0 → `users_page`. Ключи из `get_keys_for_user`. `label="USER"`, `fallback_endpoint="users_page"`.

## `create_webhook_app.update_key_comment_route` (4070–4074)

**Docstring в коде:** нет. POST `/admin/keys/<key_id>/comment`.

```
"""Записать комментарий ключа (`update_key_comment`) и редирект на список ключей."""
```

## `create_webhook_app.update_host_ssh_route` (4079–4097)

**Docstring в коде:** нет. POST `/admin/hosts/ssh/update`.

```
"""Обновить SSH хоста; пустой пароль в форме оставить прежний из `get_host`."""
```

Порт не int → None. Редирект `settings_page`.

## `create_webhook_app.run_ssh_target_speedtest_route` (4102–4123)

**Docstring в коде:** нет. POST `/admin/ssh-targets/<target_name>/speedtest/run`.

```
"""Запустить спидтест SSH-цели; JSON если Accept/XHR, иначе flash и settings?tab=hosts."""
```

`accept_new_host_key` если форма в {1,true,on,yes}. `run_and_store_ssh_speedtest_for_target`.

## `create_webhook_app.run_all_ssh_target_speedtests_route` (4128–4158)

**Docstring в коде:** нет. POST `/admin/ssh-targets/speedtests/run-all`.

```
"""Последовательно прогнать спидтест всех SSH-целей; JSON или flash на dashboard."""
```

Пустое `target_name` skip. `accept_new_host_key` не передаётся. Flash ошибок — первые 3.

## `create_webhook_app.run_host_speedtest_route` (4163–4191)

**Docstring в коде:** нет. POST `/admin/hosts/<host_name>/speedtest/run`.

```
"""Спидтест хоста: method `ssh` / `net` / иначе оба (`run_both_for_host`)."""
```

ssh: `accept_new_host_key`. JSON или flash → `settings_page`.

## `create_webhook_app.host_speedtests_json` (4195–4207)

**Docstring в коде:** нет. GET `/admin/hosts/<host_name>/speedtests.json`.

```
"""Последние спидтесты хоста (`get_speedtests`, limit query default 20)."""
```

## `create_webhook_app.run_all_speedtests_route` (4211–4241)

**Docstring в коде:** нет. POST `/admin/speedtests/run-all`.

```
"""`run_both_for_host` для каждого хоста; JSON или flash на dashboard."""
```

## `create_webhook_app.auto_install_speedtest_route` (4246–4270)

**Docstring в коде:** нет. POST `/admin/hosts/<host_name>/speedtest/install`.

```
"""Поставить speedtest на хост (`auto_install_speedtest_on_host`); хвост лога во flash."""
```

## `create_webhook_app.admin_balance_page` (4274–4290)

**Docstring в коде:** нет. GET `/admin/balance`.

```
"""Страница баланса: если есть `user_id` — user, balance, referrals; иначе пустые."""
```

Ошибки чтения глотаются. Шаблон `admin_balance.html`.

## `create_webhook_app.support_list_page` (4294–4314)

**Docstring в коде:** нет. GET `/support`.

```
"""Список тикетов: фильтр open/closed, страница по 12, счётчики, шаблон `support.html`."""
```

Иной `status` → без фильтра (`None`).

## `create_webhook_app._schedule_bulk_ticket_followup` (4316–4343)

**Docstring в коде:** нет

```
"""После массового SQL: форум/медиа через `run_bulk_ticket_followup` (sync или daemon)."""
```

`BULK_TICKETS_SYNC` → сразу в HTTP-потоке. Иначе поток `shopbot-bulk-tickets-{action}`. bot/loop — с support-контроллера на момент вызова.

### `create_webhook_app._schedule_bulk_ticket_followup._job` (4335–4339)

**Docstring в коде:** нет

```
"""Фон: `run_bulk_ticket_followup(**kwargs)`; падение — `logger.exception`."""
```

## `create_webhook_app.support_bulk_close_route` (4347–4363)

**Docstring в коде:** нет. POST `/support/bulk-close`.

```
"""Закрыть все открытые тикеты в БД и в фоне закрыть темы форума."""
```

`count==0` → «Нет открытых тикетов.» Иначе `action="close"`, flash что список уже обновлён.

## `create_webhook_app.support_bulk_delete_route` (4367–4384)

**Docstring в коде:** нет. POST `/support/bulk-delete`.

```
"""Удалить все тикеты в БД; фон — форум и файлы (`media_ticket_ids`)."""
```

## `create_webhook_app.support_ticket_page` (4388–4488)

**Docstring в коде:** нет. GET/POST `/support/<ticket_id>`.

```
"""Карточка тикета: ответ админа, закрыть/открыть; GET рисует `ticket.html`."""
```

Нет тикета → flash + список.

| action | По коду |
|--------|---------|
| `reply` | пустое message → warning; иначе `add_support_message(sender='admin')`; текст пользователю support-ботом; зеркало в форум-тред; нет loop — error-лог, пользователю не уйдёт |
| `close` | только если статус не `closed` и `set_ticket_status` ok: `close_forum_topic` + уведомление пользователю |
| `open` | зеркально: `reopen_forum_topic` + «снова открыт» |

GET: `public_support_message` на каждое сообщение.

## `create_webhook_app.support_ticket_messages_api` (4492–4503)

**Docstring в коде:** нет. GET `/support/<ticket_id>/messages.json`.

```
"""JSON переписки тикета: status + `public_support_message` для каждого сообщения."""
```

Нет тикета → `{"error":"not_found"}` 404.

## `create_webhook_app.block_ticket_files_dir` (4507–4508)

**Docstring в коде:** нет. GET/HEAD/POST `/ticket_files` и `/ticket_files/<path>`. Без `login_required`.

```
"""Всегда `abort(404)`: прямой листинг каталога вложений закрыт."""
```

## `create_webhook_app.support_ticket_file` (4511–4563)

**Docstring в коде:** есть (дословно):

```
"""Отдаёт вложение тикета.

        Без сессии панели — глухой 404, не редирект на логин:
        иначе URL сам подсказывает, что файл существует.
        """
```

GET `/support/ticket-file/<message_id>`. Нет `@login_required` — проверка `'logged_in' not in session` → 404.

| Строки | Блок | Зачем |
|--------|------|--------|
| 4528–4530 | msg | нет сообщения / нет `media` → 404 |
| 4532–4540 | TTL | `expire_ticket_media_if_closed_ttl` или Exception → 404 |
| 4542–4548 | path jail | `realpath` join; в коде `#`: путь из БД не доверенный; не под `base+sep` или не файл → 404 |
| 4550–4563 | тип | `detect_image_kind` None → 404; nosniff / no-referrer / no-store / noindex |

## `create_webhook_app.delete_support_ticket_route` (4567–4603)

**Docstring в коде:** нет. POST `/support/<ticket_id>/delete`.

```
"""Удалить тему форума (фолбэк close) и затем `delete_ticket`; редирект на список или карточку."""
```

`delete_forum_topic` timeout 5 с; fail → `close_forum_topic` 5 с. Нет bot/loop/forum ids — error-лог, БД всё равно удаляется.

## `create_webhook_app.settings_page` (4607–4839)

**Docstring в коде:** нет. GET/POST `/settings`.

```
"""Сохранить настройки панели (POST) или отрисовать `settings.html` со всем контекстом хостов."""
```

### POST (4608–4725)

| Строки | Блок | Зачем |
|--------|------|--------|
| 4610–4632 | логотип | webapp_logo: png/jpg/jpeg/webp/gif/svg → `webapp/uploads/webapp_logo{ext}` + `?v=timestamp` |
| 4634–4640 | пароль | непустое `panel_password` → bcrypt, `update_setting` |
| 4644–4668 | чекбоксы | список ключей; last value в {on,true,1,yes} → `'true'` иначе `'false'` |
| 4670–4673 | франшиза | `_apply_franchise_runtime(franchise_settings())` |
| 4675–4695 | ALL_SETTINGS_KEYS | skip checkbox / panel_password / panel_totp_enabled / panel_totp_secret; пустые smtp_password, remnawave_api_token, SECRET_SETTING_KEYS не затирают; `ticket_auto_close_days` через `validate_ticket_auto_close_days` |
| 4697–4720 | TOTP | want+нет секрета → random_base32; уже был включён → просто `'true'`; иначе verify confirm window=1; без кода — `'false'` + flash про QR |
| 4722–4725 | редирект | `next_hash` → tab |

### GET (4727–4838)

`seed_global_remnawave_from_hosts`. Сквады: badge lte / BASE / OTHER. На каждом хосте: тарифы + пакеты `main` и `lte` (в коде `#`: раньше читался только main), latest_speedtest, squads, selected ids, overlap из БД без панели. SSH-цели, zip-бэкапы `db-backup-*.zip`. TOTP QR (issuer = brand title, account = panel_login).

## `create_webhook_app._as_bool` (4842–4843)

**Docstring в коде:** нет

```
"""True, если строка в {1, true, yes, on} (strip, lower)."""
```

## `create_webhook_app._get_module_info` (4845–4849)

**Docstring в коде:** нет

```
"""Найти модуль в `module_loader.list_modules()` по `id` или вернуть None."""
```

## `create_webhook_app._build_module_settings_form` (4851–4877)

**Docstring в коде:** нет

```
"""Собрать поля формы настроек модуля: схема + значения, boolean через `_as_bool`."""
```

`full_key = f"{module_id}_{key}"`. Нет raw → `default`. Нет schema → `[]`.

## `create_webhook_app.modules_page` (4881–4884)

**Docstring в коде:** нет. GET `/modules/`.

```
"""Список модулей: `modules.html` + `list_modules()`."""
```

## `create_webhook_app.module_enable_route` (4888–4891)

**Docstring в коде:** нет. POST `/modules/<module_id>/enable`.

```
"""`module_loader.enable_module`; flash message и редирект на список."""
```

## `create_webhook_app.module_disable_route` (4895–4898)

**Docstring в коде:** нет. POST `/modules/<module_id>/disable`.

```
"""`module_loader.disable_module`; flash и редирект на список."""
```

## `create_webhook_app.module_delete_route` (4902–4905)

**Docstring в коде:** нет. POST `/modules/<module_id>/delete`.

```
"""`module_loader.delete_module`; flash и редирект на список."""
```

## `create_webhook_app.module_settings_page` (4909–4941)

**Docstring в коде:** нет. GET/POST `/modules/<module_id>/settings`.

```
"""GET/POST настроек модуля по схеме; нет модуля или полей — редирект на список."""
```

POST: boolean → `'true'`/`'false'` через `_as_bool`; иначе сырая строка; `update_setting(full_key)`. GET без items → «нет настроек».

## `create_webhook_app.module_page_proxy` (4946–5021)

**Docstring в коде:** есть (дословно):

```
"""Proxy request to module's panel routes if they exist."""
```

GET/POST `/modules/<module_id>/` и `/modules/<module_id>/<path:subpath>`.

В коде `#`: нет registry → placeholder; `/` → `index`; иначе `subpath` с `/`→`_`; нет точного имени и есть `/` — первый сегмент; wrap `flask.render_template` + `inject_current_year()` (kwargs побеждают); restore в `finally`. Нет функции — placeholder со списком available.

## `create_webhook_app.module_upload_route` (5025–5073)

**Docstring в коде:** есть (дословно):

```
"""Upload and install a module from ZIP file."""
```

POST `/modules/upload`. В коде `#`: файл обязателен; только `.zip`; ранний отказ по Content-Length (`MAX_MODULE_ZIP_BYTES + 1MiB`); размер файла после save; `import_module_from_zip(..., auto_enable=True)`.

## `create_webhook_app.create_ssh_target_route` (5077–5102)

**Docstring в коде:** нет. POST `/admin/ssh-targets/create`.

```
"""Создать SSH-цель: имя + ssh_host обязательны; порт по умолчанию 22."""
```

Редирект `settings_page?tab=hosts`.

## `create_webhook_app.update_ssh_target_route` (5106–5128)

**Docstring в коде:** нет. POST `/admin/ssh-targets/<target_name>/update`.

```
"""Частично обновить поля SSH-цели: в форму не попавшие ключи остаются None."""
```

Пустой пароль после strip → None (в отличие от `update_host_ssh_route`).

## `create_webhook_app.delete_ssh_target_route` (5132–5135)

**Docstring в коде:** нет. POST `/admin/ssh-targets/<target_name>/delete`.

```
"""Удалить SSH-цель (`delete_ssh_target`) и вернуться на вкладку hosts."""
```

## `create_webhook_app.auto_install_speedtest_on_target_route` (5141–5164)

**Docstring в коде:** нет. POST `/admin/ssh-targets/<target_name>/speedtest/install`.

```
"""Поставить speedtest на SSH-цель; JSON или flash + хвост лога."""
```

## `create_webhook_app.smtp_test_route` (5169–5203)

**Docstring в коде:** нет. POST `/settings/smtp/test`.

```
"""Сохранить SMTP-поля из формы и отправить тестовый код `000000` на `smtp_test_email`."""
```

Пустой пароль не пишется. Нет адреса / `not is_smtp_configured` → danger, tab=email. `send_activation_code(to_email, "000000")`.

## `create_webhook_app.backup_db_route` (5207–5218)

**Docstring в коде:** нет. POST `/admin/db/backup`.

```
"""Собрать zip бэкапа (`create_backup_file`) и отдать как attachment."""
```

Нет файла → flash, tab=panel.

## `create_webhook_app.restore_db_route` (5222–5263)

**Docstring в коде:** нет. POST `/admin/db/restore`.

```
"""Восстановить БД из выбранного zip в BACKUPS_DIR или из загруженного .zip/.db."""
```

`existing_backup`: `resolve()` должен начинаться с `BACKUPS_DIR.resolve()` (path jail). Иначе upload: только `.zip`/`.db` → `uploaded-{ts}-{basename}`.

## `create_webhook_app.update_remnawave_settings_route` (5267–5286)

**Docstring в коде:** нет. POST `/settings/remnawave`.

```
"""Записать глобальные Remnawave URL/token/sub и `apply_global_remnawave_to_hosts`."""
```

Пустой token не затирает сохранённый. Sync Exception → warning «сохранены, но синхронизация не удалась».

## `create_webhook_app.add_remnawave_squad_route` (5290–5299)

**Docstring в коде:** нет. POST `/add-remnawave-squad`.

```
"""Добавить сквад в глобальный каталог (`add_remnawave_squad`); класс default `base`."""
```

Пустой UUID → warning.

## `create_webhook_app.delete_remnawave_squad_route` (5303–5306)

**Docstring в коде:** нет. POST `/delete-remnawave-squad/<squad_id>`.

```
"""Удалить сквад из каталога (`delete_remnawave_squad`)."""
```

## `create_webhook_app.update_host_squad_selection_route` (5310–5340)

**Docstring в коде:** нет. POST `/update-host-squad-selection`.

```
"""Выставить сквады хоста из каталога и проверить пересечение нод LTE/base."""
```

В коде `#`: overlap не блокирует save, но трафик таких нод попадёт в LTE-пул. После ok: `refresh_host_squad_overlap`; непустой список → warning с именами/uuid.

## `create_webhook_app.update_host_subscription_route` (5344–5355)

**Docstring в коде:** нет. POST `/update-host-subscription`.

```
"""Записать `host_subscription_url` хоста (пусто → None)."""
```

## `create_webhook_app.update_host_url_route` (5359–5367)

**Docstring в коде:** нет. POST `/update-host-url`.

```
"""Сменить URL хоста; оба поля обязательны."""
```

## `create_webhook_app.update_host_remnawave_route` (5371–5386)

**Docstring в коде:** нет. POST `/update-host-remnawave`.

```
"""Записать Remnawave URL/token/squad_uuid хоста (пустые строки → None)."""
```

## `create_webhook_app.add_host_squad_route` (5390–5400)

**Docstring в коде:** нет. POST `/add-host-squad`.

```
"""Привязать сквад к хосту (`add_host_squad`); класс default `base`."""
```

Flash при fail: «уже есть активный сквад этого класса или дубликат UUID» — текст UI, не отдельная проверка в маршруте.

## `create_webhook_app.toggle_host_squad_route` (5404–5408)

**Docstring в коде:** нет. POST `/toggle-host-squad/<squad_id>`.

```
"""`set_host_squad_active`: форма `is_active=='1'` иначе выключить."""
```

## `create_webhook_app.delete_host_squad_route` (5412–5415)

**Docstring в коде:** нет. POST `/delete-host-squad/<squad_id>`.

```
"""Удалить привязку сквада хоста (`delete_host_squad`)."""
```

## `create_webhook_app.rename_host_route` (5419–5427)

**Docstring в коде:** нет. POST `/rename-host`.

```
"""Переименовать хост: `update_host_name(old_host_name, new_host_name)`."""
```

## `create_webhook_app.start_support_bot_route` (5431–5434)

**Docstring в коде:** нет. POST `/start-support-bot`.

```
"""Запустить support-бот (`_support_bot_controller.start`) и flash status/message."""
```

Редирект referrer или settings.

## `create_webhook_app._wait_for_stop` (5436–5443)

**Docstring в коде:** нет

```
"""Ждать до `timeout` с (default 5), пока `controller.get_status().is_running` станет ложью."""
```

Шаг 0.1 с. Истечение → False (маршрут всё равно продолжает flash).

## `create_webhook_app.stop_support_bot_route` (5447–5451)

**Docstring в коде:** нет. POST `/stop-support-bot`.

```
"""Остановить support-бот, дождаться `_wait_for_stop`, flash."""
```

## `create_webhook_app.start_bot_route` (5455–5458)

**Docstring в коде:** нет. POST `/start-bot`.

```
"""Запустить основной бот; редирект на dashboard."""
```

## `create_webhook_app.stop_bot_route` (5462–5466)

**Docstring в коде:** нет. POST `/stop-bot`.

```
"""Остановить основной бот, `_wait_for_stop`, flash; редирект на dashboard."""
```

## `create_webhook_app.stop_both_bots_route` (5470–5487)

**Docstring в коде:** нет. POST `/stop-both-bots`.

```
"""Остановить оба контроллера, дождаться каждый, flash «Основной | Support»."""
```

Категория danger, если хоть один не success.

## `create_webhook_app._soft_stop_controller` (5489–5494)

**Docstring в коде:** есть (дословно):

```
"""Остановить контроллер; если уже остановлен — считать успехом (для перезапуска)."""
```

Не running → `{"status":"success","message":"уже остановлен"}` без `stop()`.

## `create_webhook_app.restart_both_bots_route` (5498–5521)

**Docstring в коде:** есть (дословно):

```
"""Остановить оба бота, дождаться остановки и сразу запустить снова — без ручного stop→start."""
```

`_wait_for_stop(..., timeout=8.0)` на каждый. В коде `#`: пауза 0.5 с, чтобы polling/сокеты освободились. Затем `start()` обоих; flash «перезапущен» / ошибка.

## `create_webhook_app.start_both_bots_route` (5525–5540)

**Docstring в коде:** нет. POST `/start-both-bots`.

```
"""Запустить оба бота и flash статусы; редирект на settings."""
```

## `create_webhook_app.ban_user_route` (5544–5587)

**Docstring в коде:** нет. POST `/users/ban/<user_id>`.

```
"""`ban_user` и уведомить в Telegram: текст бана + кнопка поддержки."""
```

URL поддержки: `@` → `tg://resolve`; уже `tg://`; http(s) → последний path-сегмент как domain; иначе как domain. Нет support setting → callback `show_help`. Ошибка отправки — warning, бан уже записан.

## `create_webhook_app.unban_user_route` (5591–5611)

**Docstring в коде:** нет. POST `/users/unban/<user_id>`.

```
"""`unban_user` и прислать «доступ восстановлен» с кнопкой главного меню."""
```

## `create_webhook_app.delete_user_route` (5615–5664)

**Docstring в коде:** есть (дословно):

```
"""Полное удаление пользователя (как admin_delete_user в боте).

        Дополнительно best-effort удаляет клиентов с хостов Remnawave, чтобы
        не оставлять «осиротевшие» ключи на панели.
        """
```

POST `/users/delete/<user_id>`. Нет user → 404 JSON или flash. Для каждого ключа `delete_client_on_host` (ошибка — warning). Затем `delete_user_completely`. Accept/XHR → JSON `{ok, message, deleted_user_id?}`.

## `create_webhook_app.revoke_keys_route` (5668–5710)

**Docstring в коде:** нет. POST `/users/revoke/<user_id>`.

```
"""Снять все ключи пользователя на хостах, затем `delete_user_keys`; уведомить в Telegram."""
```

`delete_user_keys` вызывается всегда, даже если часть `delete_client_on_host` не ok. JSON `{ok, message, revoked, total}` при XHR. `ok` = `success_count == total`.

## `create_webhook_app.add_host_route` (5714–5765)

**Docstring в коде:** нет. POST `/add-host`.

```
"""Создать хост из глобальных Remnawave-настроек и опционально отметить сквады каталога."""
```

Нет имени → danger. Нет global URL/token → warning, хост не создаётся. `create_host(url=base_url, user='', passwd='', inbound=0)` → `update_host_remnawave_settings`. В коде `#`: `squad_ids` из формы необязательны.

## `create_webhook_app.delete_host_route` (5769–5772)

**Docstring в коде:** нет. POST `/delete-host/<host_name>`.

```
"""`delete_host` и flash, что хост и его тарифы удалены."""
```

Проверки существования нет.

## `create_webhook_app.add_plan_route` (5776–5823)

**Docstring в коде:** нет. POST `/add-plan`.

```
"""Создать тариф: ГБ→байты (0 = без лимита), устройства, LTE-пул, цена сброса main."""
```

`host_name`/`plan_name`/`months`/`price` из формы без try (битое months/price — необработанный exception). ГБ ≤0 или не число → 0 байт. hwid: пусто/не int → None. `main_reset_price_rub` не число → 0.0.

## `create_webhook_app.delete_plan_route` (5827–5830)

**Docstring в коде:** нет. POST `/delete-plan/<plan_id>`.

```
"""`delete_plan(plan_id)` и flash «Тариф успешно удален.»"""
```

## `create_webhook_app.toggle_plan_route` (5834–5847)

**Docstring в коде:** нет. POST `/toggle-plan/<plan_id>`.

```
"""Инвертировать `is_active` тарифа (`set_plan_active`); нет плана — считать текущий True."""
```

Локальный импорт `get_plan_by_id as _get_plan_by_id`. Exception чтения → `current_active=True` → выключит.

## `create_webhook_app.update_plan_route` (5851–5907)

**Docstring в коде:** нет. POST `/update-plan/<plan_id>`.

```
"""Обновить имя/месяцы/цену тарифа и опционально лимиты/LTE/цену сброса, если поля в форме."""
```

Не int/float months/price или пустое имя → danger, без `update_plan`. Опциональные kwargs только если ключ **присутствует** в form (пустое traffic/lte → 0 байт; пустой hwid → None; пустой reset → 0.0). Непарсибельные опциональные — ключ не кладётся. `update_plan(plan_id, plan_name, months_int, price_float, **kwargs)`.

---

**Count:** 88
