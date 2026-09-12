# Комментарии: `src/shop_bot/data_manager/database.py` (часть 1)

SQLite-слой бота (`users.db`). Модульного docstring нет. Часть 1 — инвентарь от `_now_str` до `get_utm_analytics` включительно (хелперы дат/лимитов, `initialize_db` / миграции схемы, хосты и сквады, ключи/спидтесты/подарки/pending-actions, промо и аналитика/UTM). Функции после `get_utm_analytics` (рассылки и дальше) в этот файл не входят.

Таблицы — имена из `DATABASE_DOCUMENTATION.md` и `CREATE`/`ALTER` в этом файле; колонки не выдумывать. Путь `DB_FILE`: `/app/project/users.db` → `users-20251005-173430.db` → `users.db`.

Инвентарь: `_now_str` … `get_utm_analytics` (включая вложенные `_rebuild_vpn_keys_table.has` / `.col`).

Покрыто записей инвентаря: **134**.

| Имя | Значение | Зачем |
|-----|----------|--------|
| `_UNSET` | `object()` | сентинел `lte_squad` в `should_account_lte_traffic` |
| `DEFAULT_LTE_SQUAD_LABEL` | `"LTE"` | fallback метки LTE-сквада |
| `_SQUAD_LABEL_MAX_LEN` | 48 | обрезка `squad_display_label` |
| `PENDING_ACTION_DEFAULT_TTL_HOURS` | 24 | TTL `create_pending_action` |
| `_SUCCESS_TX_SQL` | `status IN ('paid','success','succeeded')` | `#`: общая формула «успех» для аналитики |
| `_NON_BALANCE_SQL` | method ≠ `'balance'` | продажи/графики |
| `_REAL_MONEY_SQL` | method NOT IN `'balance'`, `'referralbalance'` | «реальные деньги» |

## `_now_str` (35–36)

**Docstring в коде:** нет

```
"""Вернуть datetime.utcnow() в формате `%Y-%m-%d %H:%M:%S`."""
```

Не timezone-aware. Тем же форматом пишут снапшоты, overlap, миграцию LTE.

## `add_calendar_months` (39–47)

**Docstring в коде:** есть

```
Добавляет календарные месяцы к дате, корректно обрабатывая переполнение дней
(например, 31 января + 1 месяц -> 28/29 февраля).
```

Использует `calendar.monthrange`. `compute_next_traffic_reset_str` / `compute_aligned_next_traffic_reset` / `resolve_key_period_start` опираются на неё.

## `compute_next_traffic_reset_str` (50–53)

**Docstring в коде:** есть

```
Возвращает строку даты/времени следующего ежемесячного сброса трафика (сейчас + 1 месяц).
```

`from_dt or datetime.now()` (локальное now, не utc).

## `add_months` (56–68)

**Docstring в коде:** есть

```
Прибавляет к дате календарные месяцы (без внешних зависимостей вроде dateutil).

Если в целевом месяце меньше дней, чем день исходной даты (например, 31 января -> февраль),
берётся последний день целевого месяца.
```

Та же арифметика, что `add_calendar_months`; вызывается из `compute_next_traffic_reset`.

## `compute_next_traffic_reset` (71–74)

**Docstring в коде:** есть

```
Возвращает строку даты следующего ежемесячного сброса трафика (текущий момент + 1 месяц).
```

Параллель `compute_next_traffic_reset_str`, но через `add_months`.

## `_as_limit_bytes` (77–82)

**Docstring в коде:** нет

```
"""Привести value к int; TypeError/ValueError или n≤0 → 0."""
```

`None`/`''` → `int(0)` → 0.

## `plan_main_limit_bytes` (85–86)

**Docstring в коде:** нет

```
"""Лимит основного пула тарифа: `_as_limit_bytes(plan[traffic_limit_bytes])`."""
```

`plan is None` → `{}`.

## `plan_lte_limit_bytes` (89–90)

**Docstring в коде:** нет

```
"""LTE-лимит тарифа: `_as_limit_bytes(plan[lte_limit_bytes])`."""
```

`plan is None` → `{}`.

## `should_account_lte_traffic` (93–114)

**Docstring в коде:** есть

```
LTE-учёт (снапшоты, baseline, энфорс) только при лимите и живом скваде.

Безлимитный LTE (`lte_limit_bytes` 0/NULL) и хост без активного сквада класса
`lte` не должны порождать запросы статистики на панель и строки в
`key_lte_state` / `key_node_usage_snapshots`.
```

Сентинел `_UNSET`: если `lte_squad` передан — `bool(lte_squad)` без запроса; иначе `get_squad_by_class(host_name, "lte")`, Exception → False.

## `plan_has_monthly_traffic_reset` (117–119)

**Docstring в коде:** есть

```
Ежемесячный сброс нужен, если ограничен основной пул и/или LTE.
```

## `remnawave_traffic_limit_strategy_for_plan` (122–128)

**Docstring в коде:** есть

```
Стратегия Remnawave относится только к ОСНОВНОМУ пулу.

LTE-лимит бот считает сам. Если основной пул безлимитный, панели
отправляем NO_RESET, даже когда LTE ограничен.
```

## `parse_plan_id_from_key` (131–140)

**Docstring в коде:** нет

```
"""Достать int plan_id из JSON в key.description, если строка начинается с `{`; иначе None."""
```

description не-строка или не начинается с `{` → None. `plan_id` в (None, `""`, `"None"`) пропускается. json/int Exception → None.

## `key_is_unbilled_trial_or_gift` (143–158)

**Docstring в коде:** нет

```
"""True, если tag ∈ {trial, user_gift, gift} или description.is_trial / source ∈ {trial, gift}."""
```

tag сравнивается lower. Битый JSON в description глотается, функция идёт дальше к `return False`.

## `resolve_plan_for_key` (161–182)

**Docstring в коде:** есть

```
Тариф ключа: plan_id из description, иначе первый активный тариф хоста.

Fallback на тариф хоста не применяется к триалам и подаркам — у них нет
биллинг-тарифа, даже если на хосте есть платные планы.
```

`get_plan_by_id` Exception → None. Fallback: `get_active_plans_for_host` → первый элемент или None.

## `format_next_traffic_reset_display` (185–193)

**Docstring в коде:** есть

```
Дата ближайшего сброса для карточки ключа (`ДД.ММ.ГГГГ`) либо None.
```

Пробел в дате заменяется на `T` перед `fromisoformat`. Ошибка разбора → None.

## `compute_aligned_next_traffic_reset` (196–224)

**Docstring в коде:** есть

```
Следующий сброс, согласованный с текущим rolling-окном ключа.

Если `next_traffic_reset_at` уже есть и в будущем — оставляем его.
Иначе берём начало текущего периода (`resolve_key_period_start`) плюс месяц
и прокручиваем вперёд, пока дата не окажется строго позже `now`.
```

Цикл прокрутки не больше 24 месяцев; если всё ещё `nxt <= now` — `add_calendar_months(now, 1)`.

## `_to_datetime_str` (227–234)

**Docstring в коде:** нет

```
"""Unix-время в мс → UTC-строка `%Y-%m-%d %H:%M:%S`; None или ошибка → None."""
```

`datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc)`.

## `_normalize_email` (237–241)

**Docstring в коде:** нет

```
"""strip + lower; пустое после очистки → None."""
```

## `_normalize_key_row` (244–270)

**Docstring в коде:** нет

```
"""Свести legacy-поля строки vpn_keys к парным email/key_email, remnawave_user_uuid/xui_client_uuid, expire_at/expiry_date, created_at/created_date, subscription_url/connection_string."""
```

None → None. Даты-`datetime` форматятся `%Y-%m-%d %H:%M:%S`. `connection_string` ставится через `setdefault`, если уже было — не затирается.

## `_get_table_columns` (273–275)

**Docstring в коде:** нет

```
"""Множество имён колонок таблицы через `PRAGMA table_info`."""
```

## `_ensure_table_column` (278–281)

**Docstring в коде:** нет

```
"""`ALTER TABLE … ADD COLUMN`, если колонки ещё нет в PRAGMA."""
```

## `_ensure_unique_index` (284–285)

**Docstring в коде:** нет

```
"""`CREATE UNIQUE INDEX IF NOT EXISTS name ON table(column)`."""
```

## `_ensure_index` (288–289)

**Docstring в коде:** нет

```
"""`CREATE INDEX IF NOT EXISTS name ON table(column)`."""
```

## `normalize_host_name` (292–297)

**Docstring в коде:** есть

```
Normalize host name by trimming and removing invisible/unicode spaces.
```

Удаляет `\u00A0 \u200B \u200C \u200D \uFEFF`. `None` → `""`.

## `initialize_db` (300–891)

**Docstring в коде:** нет

```
"""Создать базовые таблицы (IF NOT EXISTS), вызвать run_migration, засеять bot_settings и кнопки меню.

Ошибка sqlite3 при создании — error-лог. После блока — `_backfill_encrypt_secrets_at_rest` (ошибка → warning).
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 304–321 | CREATE users | telegram_id PK, username, total_spent, total_months, trial_used, agreed_to_terms, registration_date, is_banned, balance, referred_by, referral_balance, referral_balance_all, referral_start_bonus_received, referral_trial_day_bonus_received |
| 323–333 | CREATE pending_transactions | payment_id PK, user_id, amount_rub, metadata, status, created_at, updated_at |
| 334–360 | CREATE referral_payout_methods / referral_withdrawal_requests | реквизиты и заявки на вывод рефералки + индексы user/status |
| 361–367 | CREATE webapp_auth_requests | token PK, user_id, created_at |
| 368–391 | CREATE vpn_keys | key_id, user_id, host_name, squad_uuid, remnawave_user_uuid, short_uuid, email, key_email, subscription_url, expire_at, created_at, updated_at, traffic_limit_bytes, traffic_limit_strategy, tag, description, missing_from_server_at, user_key_name, traffic_boost_bytes, next_traffic_reset_at |
| 393–406 | CREATE key_usage_monitor | key_id PK + first_seen/last_reminder/last_checked/last_devices_count/last_traffic_bytes/overlimit_* |
| 408–422 | CREATE transactions | username, transaction_id, payment_id UNIQUE, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata, created_date |
| 423–428 | CREATE bot_settings | key PK, value |
| 429–439 | CREATE modules_registry | module_id, name, version, status, enabled_at, error_message, metadata |
| 440–458 | CREATE button_configs | UNIQUE(menu_type, button_id) |
| 459–480 | CREATE xui_hosts | host_name PK, squad_uuid UNIQUE, description, default_traffic_*, host_url/username/pass/inbound_id, subscription_url, ssh_*, is_active, sort_order, metadata |
| 481–511 | CREATE plans / traffic_packages | FK host_name → xui_hosts; FK plan_id → plans |
| 512–539 | CREATE support_tickets / support_messages | индекс thread (ошибка → pass) |
| 540–556 | CREATE host_speedtests | idx (host_name, created_at DESC) |
| 558–573 | CREATE resource_metrics | scope/object_name; `#` в SQL: 'local'/'host'/'target' |
| 575–588 | CREATE speedtest_ssh_targets | target_name PK |
| 590–679 | franchise | managed_bots, factory_user_activity, partner_commissions, partner_withdraw_requests, partner_payout_requisites; `#` + колонки snapshot реквизитов на withdraw |
| 681–705 | captcha | captcha_challenges, user_captcha_status |
| 707–854 | default_settings | INSERT OR IGNORE в bot_settings (после `run_migration()`) |
| 854 | run_migration() | колонки/таблицы, которых нет в CREATE |
| 863–875 | кнопки | initialize_default_button_configs, update_existing_my_keys_button, ensure_main_menu_gift/referral, ensure_admin_plans/trial/auto_renew |
| 878–883 | ALTER button_width | OperationalError → колонка уже есть |
| 888–891 | после основного try | `_backfill_encrypt_secrets_at_rest` (ошибка → warning) |

## `_ensure_users_columns` (894–916)

**Docstring в коде:** нет

```
"""Дописать колонки users (рефералка, auth, seller, unreachable) и индексы auth_token / auth_email / is_unreachable."""
```

Колонки из mapping: `referred_by`, `balance`, `referral_balance`, `referral_balance_all`, `referral_start_bonus_received`, `referral_trial_day_bonus_received`, `subscription_expiry_notifications_enabled`, `auth_token`, `auth_email`, `auth_pass`, `seller_active`, `seller_sale`, `is_unreachable`, `unreachable_reason`, `unreachable_since`. Индексы: `idx_users_auth_token`, `idx_users_auth_email` (unique), `idx_users_is_unreachable`.

## `_ensure_email_verification_columns` (919–943)

**Docstring в коде:** есть

```
Добавляет поля для активации email (подтверждение владения адресом при веб-регистрации).
```

Колонки: `email_verified`, `email_code_hash`, `email_code_expires_at`, `email_code_last_sent_at`, `pending_email`. В коде `#`: pending_email — новый адрес до подтверждения смены. Если `email_verified` не было в таблице — backfill `email_verified=1` для строк с auth_email+auth_pass и пустым email_code_hash. В коде `#`: не блокировать старых пользователей повторной верификацией.

## `_ensure_hosts_columns` (946–973)

**Docstring в коде:** нет

```
"""Дописать колонки xui_hosts: сквад/описание/лимит, SSH, Remnawave, node_class/badge, squad_node_overlap."""
```

Колонки: `squad_uuid`, `description`, `default_traffic_limit_bytes`, `default_traffic_strategy`, `is_active`, `sort_order`, `metadata`, `subscription_url`, `ssh_host`, `ssh_port`, `ssh_user`, `ssh_password`, `ssh_key_path`, `remnawave_base_url`, `remnawave_api_token`, `node_class` DEFAULT `'unlim'`, `badge` DEFAULT `'∞'`, `squad_node_overlap`, `squad_node_overlap_checked_at`. В коде `#`: overlap кэшируется, чтобы карточки хоста не ходили в панель на каждый рендер.

## `_ensure_plans_columns` (976–990)

**Docstring в коде:** нет

```
"""Дописать колонки plans: duration_days, трафик, hwid, metadata, lte_limit_bytes, main_reset_price_rub."""
```

Колонки: `squad_uuid`, `duration_days`, `traffic_limit_bytes`, `traffic_limit_strategy`, `is_active`, `sort_order`, `hwid_device_limit`, `metadata`, `lte_limit_bytes`, `main_reset_price_rub`.

## `_ensure_traffic_packages_table` (993–1014)

**Docstring в коде:** нет

```
"""Создать traffic_packages и колонки vpn_keys (traffic_boost_bytes, next_traffic_reset_at, comment_key, remote_access_state) плюс pool у пакетов."""
```

CREATE `traffic_packages` (`package_id`, `plan_id`, `size_gb`, `price`, `is_active`, `sort_order`, `created_at`) + idx `idx_traffic_packages_plan_id`. Потом колонка `pool` DEFAULT `'main'`. В коде `#` про `remote_access_state`: `'enabled'` / `'disabled_main'` / `'disabled_premium'` / `'disabled_premium_squad'`.

## `_ensure_key_node_usage_snapshots_table` (1017–1043)

**Docstring в коде:** есть

```
Расход ключа по КОНКРЕТНЫМ нодам за расчётный период.

Ни `key_usage_monitor` (PK key_id, одно поле last_traffic_bytes), ни `subscription_lte`
(одна строка на пользователя) не могут хранить разбивку по нодам, поэтому нужна
отдельная таблица. `period_start` согласован с расчётным периодом ключа
(`vpn_keys.next_traffic_reset_at`, см. resolve_key_period_start).
```

CREATE `key_node_usage_snapshots` (`id`, `key_id`, `node_uuid`, `node_name`, `host_name`, `used_bytes`, `period_start`, `updated_at`), UNIQUE(key_id, node_uuid, period_start), idx `idx_key_node_usage_key_period`.

## `resolve_key_period_start` (1046–1076)

**Docstring в коде:** есть

```
Начало текущего расчётного периода ключа в формате '%Y-%m-%d %H:%M:%S'.

Берём `next_traffic_reset_at` (конец периода) минус календарный месяц — так граница
совпадает с той, по которой воркер сбрасывает основной пул и baseline LTE. Если поле
ещё не заполнено, опираемся на дату создания ключа, а в последнюю очередь — на начало
текущего месяца, чтобы период всегда был определён.
```

В коде `#`: rolling-цикл от даты создания — последняя годовщина ≤ now. Fallback: первое число текущего месяца 00:00:00.

## `upsert_key_node_usage_snapshot` (1079–1121)

**Docstring в коде:** есть

```
Записать/обновить расход ключа по одной ноде за период (идемпотентно по
UNIQUE(key_id, node_uuid, period_start)).
```

Пустой `node_uuid` или нулевой `key_id` → False. `used_bytes` клипуется `max(0, int)`. `host_name` через `normalize_host_name`. ON CONFLICT обновляет used_bytes, COALESCE(node_name), host_name, updated_at.

## `get_node_usage_for_key` (1124–1150)

**Docstring в коде:** есть

```
Разбивка расхода ключа по нодам за период (по убыванию расхода).

Без `period_start` берётся последний известный период этого ключа.
```

sqlite3.Error → `[]`.

## `delete_node_usage_for_key` (1153–1163)

**Docstring в коде:** есть

```
Удалить все снапшоты ключа (используется при удалении ключа).
```

sqlite3.Error → False.

## `_ensure_subscription_lte_table` (1166–1194)

**Docstring в коде:** есть

```
Отдельный (независимый от основного) пул трафика LTE для «премиум»-нод.

Пул привязан к пользователю (не к конкретному ключу/хосту), т.к. расходуется
суммарно на всех premium-нодах его подписки.
```

CREATE `subscription_lte` (`user_id` PK, `lte_limit_bytes`, `lte_used_bytes`, `lte_boost_bytes`, `lte_used_baseline_bytes`, `lte_baseline_reset_requested`, `lte_reset_at`, `premium_state`, `updated_at`). Потом колонки baseline (CREATE IF NOT EXISTS не добавляет их в старую таблицу — `#` в коде) и `lte_baseline_initialized_at`.

## `_ensure_key_lte_state_table` (1197–1221)

**Docstring в коде:** есть

```
Состояние LTE-пула НА КЛЮЧ (пришло на смену пользовательскому `subscription_lte`).

LTE-лимит задаётся тарифом конкретного ключа (`plans.lte_limit_bytes`), а расход
считается по нодам LTE-сквада хоста этого ключа, поэтому и остаток, и докупленный
буст, и точка отсчёта обязаны жить на ключе. Пользовательская модель сворачивала
несколько ключей с разными тарифами в одну строку.
```

CREATE `key_lte_state` (`key_id` PK, те же LTE-поля, что у subscription_lte, плюс `lte_baseline_initialized_at`). Затем `_migrate_subscription_lte_to_keys`.

## `_migrate_subscription_lte_to_keys` (1224–1326)

**Docstring в коде:** есть

```
Перенести пользовательское состояние LTE на ключи (однократно для каждой строки).

Раскладка состояния пользователя по его LTE-ключам:
  * ключ ровно один — переносим состояние 1:1, ничего не теряя и не выдавая заново;
  * ключей несколько — оплаченный буст делится поровну (остаток первому ключу), чтобы
    суммарно у пользователя осталось ровно столько оплаченного трафика, сколько он
    купил, а точка отсчёта у каждого ключа определяется заново на первом проходе
    воркера (общий baseline пользователя нельзя скопировать в каждый ключ — он бы
    вычитался многократно). Такие случаи логируются: разложение неоднозначно.

Идемпотентность — через отметку `subscription_lte.migrated_to_keys_at`: без неё
ключ, созданный уже после миграции, при следующем старте получил бы чужой буст.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1238–1247 | колонка migrated_to_keys_at | идемпотентность; ошибка SELECT → warning, return |
| 1253–1268 | ключи user | vpn_keys ⋈ host_squads class=lte is_active=1 |
| 1270–1273 | нет ключей | строку не трогать (`#`: сквад могут настроить позже) |
| 1275–1289 | 1 ключ / несколько | 1:1 vs буст поровну, остаток первому; warning если boost>0 и ключей>1 |
| 1291–1315 | INSERT OR IGNORE key_lte_state | used/baseline копируются только при одном ключе |
| 1317–1326 | UPDATE migrated_to_keys_at | отметка, даже если часть INSERT упала |

## `_ensure_host_squads_table` (1329–1409)

**Docstring в коде:** есть

```
Классифицированные сквады хоста: 'base' (∞), 'lte' (💰) или 'other'.

Позволяет привязать к одному хосту сразу несколько internal squad'ов Remnawave
(двухсквадовая схема: SQUAD_BASE + SQUAD_LTE) вместо единственного `xui_hosts.squad_uuid`.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1335–1348 | CREATE host_squads | UNIQUE(host_name, squad_uuid); idx host_name и (host_name, squad_class) |
| 1350–1380 | legacy squad_uuid | если у хоста ещё нет host_squads: premium → class lte / «LTE (legacy)», иначе base / «Base (legacy)» |
| 1382–1409 | переклассификация | только ровно один сквад с label «Base (legacy)» у premium-хоста → lte (`#`: не трогать ручные привязки) |

## `add_host_squad` (1412–1449)

**Docstring в коде:** есть

```
Добавить сквад к хосту с классификацией ('base' | 'lte' | 'other').
```

Класс вне `{base,lte,other}` → `base`. Пустые host/uuid → None. В коде `#`: не больше одного активного base/lte на хост. IntegrityError (UNIQUE host_name+squad_uuid) → None.

## `get_host_squads` (1452–1467)

**Docstring в коде:** нет

```
"""Строки host_squads хоста (TRIM + NOCASE); only_active → is_active=1; порядок base, lte, other, затем id."""
```

sqlite3.Error → `[]`.

## `get_squad_by_class` (1470–1493)

**Docstring в коде:** есть

```
Быстрый доступ к активному сквада заданного класса ('base'/'lte'/'other') хоста.

Сравнение имени хоста — через TRIM(...) COLLATE NOCASE, как и в остальных запросах
к хостам (`get_host`, `get_host_class`): `vpn_keys.host_name` и `host_squads.host_name`
могут отличаться регистром/пробелами, а от результата этого запроса зависит доступность
докупки LTE — при промахе она молча пропадала из интерфейса.
```

LIMIT 1, ORDER BY id. Ошибка → None.

## `squad_display_label` (1500–1517)

**Docstring в коде:** есть

```
Публичная метка сквада: поле `label`, если заполнено, иначе fallback.

Для LTE-пула fallback по умолчанию — «LTE». Класс сквада (`squad_class`)
остаётся внутренним идентификатором и в UI не подменяется.
```

`DEFAULT_LTE_SQUAD_LABEL = "LTE"`, `_SQUAD_LABEL_MAX_LEN = 48`. label сжимает пробелы и режется до 48. Без label и без fallback: base→`BASE`, other→`OTHER`, иначе LTE.

## `get_lte_squad_display_label` (1520–1528)

**Docstring в коде:** есть

```
Метка активного LTE-сквада хоста — то, что видит пользователь вместо «LTE».
```

Пустой host_name или Exception в `get_squad_by_class` → fallback.

## `set_host_squad_active` (1531–1543)

**Docstring в коде:** нет

```
"""UPDATE host_squads.is_active (1/0) по id; True если rowcount > 0."""
```

sqlite3.Error → False.

## `delete_host_squad` (1546–1555)

**Docstring в коде:** нет

```
"""DELETE FROM host_squads WHERE id = ?; True если удалена строка."""
```

sqlite3.Error → False. Не чистит `xui_hosts.squad_uuid`.

## `_ensure_remnawave_squads_catalog` (1558–1625)

**Docstring в коде:** есть

```
Глобальный каталог сквадов Remnawave (выбираются галочками на хостах).
```

CREATE `remnawave_squads` (`id`, `squad_uuid` UNIQUE, `squad_class`, `label`, `is_active`, `created_at`), idx `idx_remnawave_squads_class`. Миграция: INSERT OR IGNORE из `host_squads`, затем legacy `xui_hosts.squad_uuid` как `'base'`/`'Base (legacy)'`. В коде `#`: выровнять каталог в `'lte'`, если host_squads уже lte (иначе `set_host_squads_from_catalog` вернул бы base).

## `get_remnawave_squads` (1628–1641)

**Docstring в коде:** нет

```
"""Все строки remnawave_squads; only_active → is_active=1; порядок base/lte/other, затем id."""
```

sqlite3.Error → `[]`.

## `add_remnawave_squad` (1644–1668)

**Docstring в коде:** нет

```
"""INSERT в remnawave_squads; класс вне {base,lte,other} → base; пустой UUID / IntegrityError → None."""
```

IntegrityError → warning «UUID уже есть», None.

## `delete_remnawave_squad` (1671–1692)

**Docstring в коде:** нет

```
"""Удалить строку remnawave_squads, связанные host_squads и обнулить xui_hosts.squad_uuid при совпадении UUID."""
```

Нет строки → False. Хосты с этим UUID получают `squad_uuid = NULL`.

## `seed_global_remnawave_from_hosts` (1695–1732)

**Docstring в коде:** есть

```
Если глобальные Remnawave-настройки пусты — взять из первого хоста.
```

Читает `bot_settings` `remnawave_base_url` / `remnawave_api_token` / `remnawave_subscription_url`. Если все три непусты — return. Иначе до 20 строк `xui_hosts` (ORDER BY host_name): base из remnawave_base_url или host_url, token через `decrypt_managed_bot_token`, sub из subscription_url. Пишет в настройки только пустые ключи.

## `apply_global_remnawave_to_hosts` (1735–1764)

**Docstring в коде:** есть

```
Синхронизировать глобальные Remnawave URL/token/subscription на все хосты.
```

На каждый хост: `update_host_remnawave_settings` (url+token), при не-None sub — `update_host_subscription_url`, при base — `update_host_url`. Счётчик `updated` только если все три ok. В коде `#`: host_url синхронизируют для speedtest/UI.

## `set_host_squads_from_catalog` (1767–1851)

**Docstring в коде:** есть

```
Выставить привязку хоста к сквадам каталога (галочки). Синхронизирует host_squads и squad_uuid.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1769–1779 | хост | нет в xui_hosts → False |
| 1781–1788 | catalog_ids | только активные remnawave_squads с id из wanted |
| 1790–1802 | `#` не более одного base/lte | первый по приоритету base, затем lte |
| 1807–1814 | лишние host_squads | DELETE uuid, которых нет в wanted |
| 1821–1836 | недостающие | INSERT OR IGNORE |
| 1838–1846 | xui_hosts.squad_uuid | UUID первого base из filtered или NULL |

## `get_host_selected_squad_catalog_ids` (1854–1873)

**Docstring в коде:** есть

```
ID записей каталога, привязанных к хосту через host_squads.uuid.
```

JOIN `remnawave_squads` ↔ `host_squads` по `squad_uuid`. Docstring пишет `host_squads.uuid` — в таблице колонка `squad_uuid`.

## `_ensure_support_tickets_columns` (1876–1882)

**Docstring в коде:** нет

```
"""Добавить support_tickets.forum_chat_id и message_thread_id, если их нет."""
```

Только эти два поля; индекс `idx_support_tickets_thread` создаётся в `initialize_db` / `run_migration`.

## `_ensure_key_usage_monitor_columns` (1885–1891)

**Docstring в коде:** нет

```
"""Добавить key_usage_monitor.overlimit_notified_count и overlimit_notified_at, если их нет."""
```

Сама таблица `key_usage_monitor` создаётся в `initialize_db`.

## `_finalize_vpn_key_indexes` (1894–1899)

**Docstring в коде:** нет

```
"""Индексы vpn_keys: уникальные email / key_email, idx user_id / remnawave_user_uuid / expire_at."""
```

Имена: `uq_vpn_keys_email`, `uq_vpn_keys_key_email`, `idx_vpn_keys_user_id`, `idx_vpn_keys_rem_uuid`, `idx_vpn_keys_expire_at`.

## `_rebuild_vpn_keys_table` (1902–2002)

**Docstring в коде:** нет

```
"""Если схема уже новая — дописать missing_from_server_at и индексы; иначе пересоздать vpn_keys из legacy-колонок."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1903–1909 | уже новая схема | нет legacy-маркеров xui_client_uuid/expiry_date/created_date/connection_string и есть remnawave_user_uuid/email/expire_at/created_at/updated_at → только missing_from_server_at + индексы |
| 1911–1933 | rebuild | RENAME → vpn_keys_legacy, CREATE новой vpn_keys |
| 1936–1948 | has/col | выражения email/key_email LOWER, uuid/expire/created fallback |
| 1971–1996 | INSERT…SELECT | перенос; user_key_name в CREATE есть, в SELECT нет |
| 1997–2002 | drop + sqlite_sequence | MAX(key_id) |

## `_rebuild_vpn_keys_table.has` (1936–1937)

**Docstring в коде:** нет

```
"""True, если колонка есть в vpn_keys_legacy."""
```

Замыкание над `old_columns` (`PRAGMA` по `vpn_keys_legacy`).

## `_rebuild_vpn_keys_table.col` (1939–1940)

**Docstring в коде:** нет

```
"""Имя колонки, если она есть в legacy-таблице, иначе default (по умолчанию NULL)."""
```

Не проверяет SQL-инъекцию: имена колонок из PRAGMA / литерал default.

## `_ensure_vpn_keys_schema` (2005–2034)

**Docstring в коде:** нет

```
"""Создать vpn_keys, если таблицы нет; иначе _rebuild_vpn_keys_table и колонка user_key_name."""
```

CREATE без `traffic_boost_bytes` / `next_traffic_reset_at` / `comment_key` / `auto_renew` — их дописывают другие `_ensure_*`. В коде `#`: добавить `user_key_name` если нет.

## `_migrate_gift_tags` (2037–2049)

**Docstring в коде:** есть

```
Обновить старые теги 'gift' и 'GIFT' на новый стандарт 'user_gift'.
```

`UPDATE vpn_keys SET tag = 'user_gift' WHERE tag IN ('gift', 'GIFT')`.

## `run_migration` (2053–2129)

**Docstring в коде:** нет

```
"""Прогнать _ensure_* и точечные UPDATE на существующем DB_FILE; файла нет — выход без изменений."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2054–2056 | нет DB_FILE | error, return |
| 2063 | PRAGMA foreign_keys = OFF | на время ensure |
| 2064–2086 | цепочка _ensure_* | users → email → hosts → plans → tickets → vpn_keys → gift tags → usage monitor → ssh targets/known_hosts → gifts → promo → traffic_packages → subscription_lte → snapshots → host_squads → key_lte_state → remnawave catalog → analytics → pending actions |
| 2087–2094 | plans.traffic_limit_strategy | MONTH_ROLLING если traffic_limit_bytes > 0 |
| 2096–2114 | idx tickets + pending_transactions | ошибки → pass |
| 2115–2116 | `#` Auto-renewal | vpn_keys.auto_renew |
| 2117–2118 | FK ON, commit | |
| 2122–2129 | после conn | backfill_monthly_traffic_reset_for_existing_keys; _backfill_encrypt_secrets_at_rest |

## `insert_resource_metric` (2132–2165)

**Docstring в коде:** нет

```
"""INSERT в resource_metrics (scope, object_name, cpu/mem/disk/load1, net_bytes_*, raw_json); lastrowid или None."""
```

scope/object_name strip. sqlite3.Error → None.

## `get_latest_resource_metric` (2168–2186)

**Docstring в коде:** нет

```
"""Последняя строка resource_metrics по scope + object_name (ORDER BY created_at DESC LIMIT 1)."""
```

sqlite3.Error → None.

## `get_metrics_series` (2189–2227)

**Docstring в коде:** нет

```
"""Ряд created_at/cpu/mem/disk/load1 за окно часов; since_hours==1 → фильтр 2 ч; LIMIT не меньше 10."""
```

По коду: `since_hours == 1` расширяет окно до 2 часов. Возвращает не все колонки таблицы — без net_bytes_* и raw_json.

## `create_host` (2230–2257)

**Docstring в коде:** нет

```
"""INSERT в xui_hosts (host_name, host_url, host_username, host_pass, host_inbound_id, subscription_url); fallback без subscription_url."""
```

Возвращает None (нет return). OperationalError на INSERT с subscription_url — повтор без этой колонки. inbound не-int оставляют как есть (`except: pass`).

## `update_host_subscription_url` (2259–2278)

**Docstring в коде:** нет

```
"""UPDATE xui_hosts.subscription_url по TRIM(host_name); False если хоста нет."""
```

Хост ищется по TRIM без COLLATE NOCASE.

## `claim_referral_start_bonus` (2280–2306)

**Docstring в коде:** есть

```
Атомарно пометить, что приглашённый получил стартовый реферальный бонус.

Возвращает True только если этот вызов выиграл гонку: UPDATE с
``WHERE COALESCE(referral_start_bonus_received, 0) = 0`` и ``rowcount > 0``.
Начислять баланс рефереру можно только после успешного claim — иначе
параллельные /start (или pending-action) дважды кредитуют одну и ту же сумму.
```

Поле `users.referral_start_bonus_received`.

## `set_referral_start_bonus_received` (2309–2315)

**Docstring в коде:** есть

```
Пометить, что пользователь получил стартовый бонус за реферальную регистрацию.

Атомарный claim (см. ``claim_referral_start_bonus``): повторный вызов
возвращает False и не сбрасывает флаг.
```

Алиас `claim_referral_start_bonus`.

## `set_referral_trial_day_bonus_received` (2318–2333)

**Docstring в коде:** есть

```
Пометить, что за данного пользователя уже начислялся +1 день рефереру за активацию триала.
```

UPDATE без проверки «ещё не стояло» — повторный вызов тоже True, если строка есть.

## `update_host_url` (2335–2355)

**Docstring в коде:** есть

```
Обновить URL панели XUI для указанного хоста.
```

True только при `rowcount > 0` (в отличие от subscription_url, где после существования хоста всегда True).

## `update_host_remnawave_settings` (2357–2401)

**Docstring в коде:** есть

```
Обновить Remnawave-настройки на уровне конкретного хоста.
Пустые строки превращаются в NULL. Поля, равные None, не изменяются.
```

`remnawave_api_token` непустой шифруется `encrypt_managed_bot_token`. Нет ни одного поля → True без UPDATE. После UPDATE всегда True (не смотрит rowcount).

## `get_host_class` (2404–2418)

**Docstring в коде:** есть

```
Класс ноды: 'premium' (💰) или 'unlim' (∞, по умолчанию).
```

Нет строки / пустой node_class / ошибка → `'unlim'`. COLLATE NOCASE.

## `set_host_class` (2421–2438)

**Docstring в коде:** есть

```
Устанавливает класс ноды ('premium'/'unlim') и её значок (по умолчанию 💰/∞).
```

Всё кроме lower `'premium'` становится `'unlim'`.

## `set_host_squad_overlap` (2441–2467)

**Docstring в коде:** есть

```
Сохранить результат проверки пересечения нод LTE- и base-сквадов хоста.

Пустой список означает «проверено, пересечений нет» — это не то же самое, что NULL
(«не проверялось»), поэтому дата проверки пишется в обоих случаях.
```

В JSON только `uuid` и `node_name` элементов-dict с uuid. Пишет `squad_node_overlap` + `squad_node_overlap_checked_at` = `_now_str()`.

## `get_host_squad_overlap` (2470–2488)

**Docstring в коде:** есть

```
Ноды, доступные и через LTE-, и через base-сквад хоста (по последней проверке).
```

Пусто / не-list / битый JSON → `[]`. Элементы не-dict отбрасываются.

## `list_hosts_by_class` (2491–2504)

**Docstring в коде:** нет

```
"""Все xui_hosts с COALESCE(node_class, unlim) = premium|unlim (не-premium → unlim); секреты расшифрованы."""
```

Не-premium → фильтр `'unlim'`. Расшифровка `ssh_password`, `remnawave_api_token`.

## `update_host_name` (2507–2549)

**Docstring в коде:** есть

```
Переименовать хост во всех связанных таблицах (xui_hosts, plans, vpn_keys, host_squads).
```

Пустое новое имя → False. Целевое имя занято (и это не смена регистра того же) → False. В коде `#`: без UPDATE host_squads LTE-сквад осиротеет.

## `delete_host` (2551–2567)

**Docstring в коде:** нет. В коде `#` про мусор host_squads при повторном создании хоста с тем же именем.

```
"""Удалить plans, xui_hosts и host_squads хоста. vpn_keys не трогает."""
```

В коде `#`: иначе привязки сквадов подхватит хост, созданный позже с тем же именем. Ключи в `vpn_keys` не удаляются.

## `_decrypt_row_secrets` (2569–2577)

**Docstring в коде:** есть

```
Расшифровать at-rest поля (enc1$ / legacy plaintext) в копии строки.
```

Пустой row возвращается как есть. Копия dict; каждое непустое поле — `decrypt_managed_bot_token(str)`.

## `get_host` (2580–2591)

**Docstring в коде:** нет

```
"""Строка xui_hosts по TRIM(host_name); ssh_password и remnawave_api_token расшифрованы."""
```

TRIM без NOCASE. Нет строки → None.

## `update_host_ssh_settings` (2593–2632)

**Docstring в коде:** есть

```
Обновить SSH-параметры для speedtest/maintenance по хосту.
Переданные None значения очищают соответствующие поля (ставят NULL).
```

Все пять полей пишутся всегда. Пустой ssh_password → NULL (не шифруется). После нахождения хоста всегда True.

## `delete_key_by_id` (2634–2650)

**Docstring в коде:** нет. В коде `#` про неактивированные user_gifts.

```
"""Удалить ключ и связанные неактивированные user_gifts, key_node_usage_snapshots, key_lte_state."""
```

В коде `#`: неактивированный подарок (`user_gifts.key_id`, `is_activated = 0`) должен исчезнуть вместе с ключом. `affected` — rowcount последнего DELETE (`vpn_keys`).

## `update_key_comment` (2652–2661)

**Docstring в коде:** нет

```
"""UPDATE vpn_keys.comment_key по key_id; True если rowcount > 0."""
```

Не нормализует пустую строку в NULL.

## `update_key_name` (2664–2697)

**Docstring в коде:** есть

```
Обновить пользовательское название ключа.

Args:
    key_id: ID ключа
    new_name: Новое название (None или пустая строка для удаления)

Returns:
    True если успешно, False при ошибке
```

Длина > 30 → False (warning). strip пустой → NULL (`user_key_name`). Пишет `updated_at = CURRENT_TIMESTAMP`.

## `get_all_hosts` (2700–2716)

**Docstring в коде:** нет

```
"""Все строки xui_hosts; host_name через normalize_host_name; ssh_password и remnawave_api_token расшифрованы."""
```

Без ORDER BY. Ошибка → `[]`.

## `get_speedtests` (2718–2744)

**Docstring в коде:** есть

```
Получить последние результаты спидтестов по хосту (ssh/net), новые сверху.
```

limit не-int → 20. Колонки SELECT перечислены явно (не `*`).

## `get_latest_speedtest` (2746–2768)

**Docstring в коде:** есть

```
Получить последний по времени спидтест для хоста.
```

Тот же SELECT, LIMIT 1.

## `insert_host_speedtest` (2770–2813)

**Docstring в коде:** есть

```
Сохранить результат спидтеста в таблицу host_speedtests.
```

method не `ssh`/`net` (lower) → `'ssh'`. ok → 0/1.

## `_ensure_ssh_targets_table` (2817–2846)

**Docstring в коде:** есть

```
Миграция: создать таблицу speedtest_ssh_targets при необходимости и добавить недостающие столбцы.
```

CREATE + extras тех же колонок (кроме PK `target_name`) на случай старой таблицы.

## `_ensure_ssh_known_hosts_table` (2849–2860)

**Docstring в коде:** нет

```
"""CREATE TABLE IF NOT EXISTS ssh_known_hosts (host, port, key_type, key_base64), PRIMARY KEY (host, port)."""
```

Таблица из DATABASE_DOCUMENTATION («Дополнительные таблицы»): отпечатки SSH для `StoredHostKeyPolicy`.

## `get_ssh_known_host_key` (2863–2878)

**Docstring в коде:** нет

```
"""Строка ssh_known_hosts по host + port (port по умолчанию 22); пустой host → None."""
```

TypeError/ValueError/sqlite3 → None.

## `save_ssh_known_host_key` (2881–2902)

**Docstring в коде:** нет

```
"""UPSERT отпечатка в ssh_known_hosts по (host, port); пустые host/key_base64 → False."""
```

ON CONFLICT(host, port) обновляет key_type и key_base64.

## `_ensure_gift_tokens_table` (2905–2938)

**Docstring в коде:** есть

```
Миграция для таблиц подарочных токенов.
```

CREATE `gift_tokens` и `gift_token_claims`. Индексы: `idx_gift_tokens_host`, `idx_gift_tokens_expires`, `idx_gift_token_claims_token`, `idx_gift_token_claims_user`.

## `_ensure_user_gifts_table` (2941–2962)

**Docstring в коде:** есть

```
Миграция для таблицы неактивированных пользовательских подарков.
```

CREATE `user_gifts`. Индексы: `idx_user_gifts_from_user`, `idx_user_gifts_gift_code`, `idx_user_gifts_is_activated`.

## `_ensure_auth_pending_actions_table` (2965–2991)

**Docstring в коде:** есть

```
Миграция для таблицы pending action — единого механизма "открыл ссылку
подарка/рефералки → потом авторизовался (Telegram ИЛИ email) → действие
применяется автоматически". См. src/shop_bot/webapp/handlers.py:
web_gift_page, web_referral_page, api_pending_action_info,
api_pending_action_complete.
```

CREATE `auth_pending_actions`. Индексы: unique token, expires_at, gift_code, referrer_id.

## `create_pending_action` (2997–3028)

**Docstring в коде:** есть

```
Создать pending action и вернуть одноразовый случайный токен.

Токен — единственное, что уходит клиенту; сам контекст (какой именно
подарок/реферер) остаётся только на сервере и не может быть подменён
клиентом на этапе завершения (см. get_pending_action/claim_pending_action).
```

`PENDING_ACTION_DEFAULT_TTL_HOURS = 24`. action_type не `gift`/`referral` → None. Токен `secrets.token_urlsafe(32)`. `expires_at = datetime('now', '+N hours')`.

## `get_pending_action` (3031–3046)

**Docstring в коде:** есть

```
Вернуть запись pending action по токену как есть (включая уже
истёкшие/использованные — вызывающий код сам решает, что показать
пользователю). Не выполняет побочных эффектов.
```

Пустой token → None без запроса.

## `claim_pending_action` (3049–3074)

**Docstring в коде:** есть

```
Атомарно "забрать" pending action для указанного пользователя.

Ключевой момент идемпотентности/защиты от гонки: UPDATE проверяет
`consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP` прямо в WHERE,
и именно `cursor.rowcount` (а не отдельный предварительный SELECT)
определяет, успел ли именно этот вызов "выиграть" право применить действие.
Если два параллельных запроса пришлют один и тот же pending_token —
claim_pending_action вернёт True ровно для одного из них.
```

True только при `rowcount > 0`.

## `set_pending_action_result` (3077–3093)

**Docstring в коде:** есть

```
Сохранить итоговый статус применения действия — чтобы повторный вызов
complete (тем же пользователем, для уже использованного токена) мог
вернуть тот же самый структурированный результат без повторного выполнения
бизнес-логики.
```

Не проверяет, что токен уже claimed.

## `cleanup_expired_pending_actions` (3096–3111)

**Docstring в коде:** есть

```
Удалить давно истёкшие pending actions (профилактическая очистка,
не обязательна для корректности — claim_pending_action и без этого не
применит просроченный токен).
```

DELETE где `expires_at < datetime('now', '-N hours')`. Ошибка → 0.

## `_ensure_promo_tables` (3114–3175)

**Docstring в коде:** есть

```
Создание таблиц промокодов и истории их использования.
```

CREATE `promo_codes`, `promo_code_usages`, `promo_code_reservations`. Additive колонки `applicable_plan_ids` / `segment_type` / `segment_value`. Unique partial index `idx_promo_code_usages_order_id_unique` на order_id IS NOT NULL (ошибка создания глотается). В коде `#`: NULL targeting = unconditional.

## `_ensure_analytics_tables` (3178–3284)

**Docstring в коде:** есть

```
Таблицы для раздела админки «Продажи и аналитика».

Полностью независимы от xui_hosts (по требованию — учёт серверов/экономики
ведётся отдельно от технической конфигурации хостов).
```

| Таблица | Поля из CREATE |
|---------|----------------|
| server_cost_entries | id, server_label, linked_host_name, provider, location, monthly_cost, currency, status, started_at, ended_at, comment, created_at, updated_at |
| utm_links | id, slug UNIQUE, source, medium, campaign, content, term, label, comment, budget, is_active, created_by, created_at |
| utm_visits | id, slug, user_id, event_type, created_at |
| analytics_events | id, event_type, user_id, ref_key, amount, created_at |
| broadcast_campaigns | id, name, text_html, is_active, interval_hours, target_segment, send_count, last_run_at, created_at, updated_at |
| broadcast_sends | id, campaign_id, user_id, sent_at |

Также `_ensure_table_column(users, utm_slug, TEXT)` — first-touch (`#` в коде). CRUD рассылок в этой части не покрывается.

## `get_all_ssh_targets` (3287–3298)

**Docstring в коде:** есть

```
Вернуть все SSH-цели для спидтестов (включая неактивные), сортировка по sort_order, затем по имени.
```

Расшифровка `ssh_password`. Ошибка → `[]`.

## `get_ssh_target` (3301–3312)

**Docstring в коде:** нет

```
"""Строка speedtest_ssh_targets по TRIM(target_name); ssh_password расшифрован."""
```

Имя через `normalize_host_name` (как у хостов). TRIM без NOCASE.

## `create_ssh_target` (3315–3353)

**Docstring в коде:** нет

```
"""INSERT в speedtest_ssh_targets; пароль шифруется; is_active=0 только при явном 0."""
```

is_active None или ≠0 → 1. sqlite3.Error (в т.ч. UNIQUE target_name) → False.

## `update_ssh_target_fields` (3356–3420)

**Docstring в коде:** нет

```
"""Частичный UPDATE speedtest_ssh_targets только по переданным kwargs; пустой набор → True без записи."""
```

ssh_port не-int → NULL в SET. Пустой ssh_password (strip) → NULL. sort_order не-int → 0. Хост не найден → False.

## `delete_ssh_target` (3423–3434)

**Docstring в коде:** нет

```
"""DELETE FROM speedtest_ssh_targets по TRIM(target_name); True если удалена строка."""
```

sqlite3.Error → False.

## `get_admin_stats` (3436–3513)

**Docstring в коде:** есть

```
Return aggregated statistics for the admin dashboard.
Includes:
- total_users: count of users
- total_keys: count of all keys
- active_keys: keys with expire_at in the future
- total_income: sum of amount_rub for successful transactions
```

| Ключ | SQL |
|------|-----|
| total_users | COUNT users |
| total_keys | COUNT vpn_keys |
| active_keys | expire_at IS NOT NULL AND datetime(expire_at) > CURRENT_TIMESTAMP |
| total_income / today_income | SUM amount_rub, status ∈ paid/success/succeeded, method NOT IN balance, referral_transfer, referral_payout, referraltransfer |
| today_new_users | date(registration_date) = date('now') |
| today_issued_keys | date(COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)) = date('now') |

Docstring перечисляет только первые четыре ключа; today_* в теле есть. Ошибка → нули в заранее собранном dict.

## `get_sales_overview` (3528–3648)

**Docstring в коде:** есть

```
Главный дашборд продаж (Этап 4.1 плана): выручка/транзакции/чек/плательщики
за сегодня, 7, 30 дней и всё время + неуспешные/ожидающие платежи.
Переиспользует те же SQL-условия успешности, что get_admin_stats()/statistics_page().
```

В коде `#`: формула успешности «должна дословно совпадать» с get_admin_stats. По коду `_SUCCESS_TX_SQL` = status IN paid/success/succeeded, `_NON_BALANCE_SQL` = method ≠ `'balance'` (referral_transfer / referral_payout / referraltransfer **не** исключаются — в отличие от get_admin_stats).

| Ключ | Смысл |
|------|--------|
| today / d7 / d30 / all | transactions, revenue, unique_payers, avg_check |
| failed_or_pending_by_status | GROUP BY status где NOT success |
| pending_payments | COUNT pending_transactions status='pending' |
| new_payers_30d / total_payers | первая успешная дата пользователя |
| repeat_payers / repeat_conversion_pct | ≥2 успешных tx |
| mrr_estimate | сумма amount/months за 30 дней (months из metadata, ≤0 или нет → 1) |

## `get_revenue_series` (3651–3674)

**Docstring в коде:** есть

```
Ряд выручки/транзакций по дням для графика раздела «Продажи и аналитика».
Использует тот же SQL-фильтр успешности, что и get_sales_overview().
```

Ключи — даты (`date(created_date)`), значения float/int. Дни без продаж в dict нет. `days` клипуется `max(1, int(days))`.

## `get_plans_analytics` (3677–3726)

**Docstring в коде:** есть

```
Аналитика по тарифам (Этап 4.4): выручка, продажи, средний чек, доля повторных покупок.
```

Группировка по `metadata.plan_name` (нет → `"N/A"`). В коде `#`: `_NON_PLAN_ACTIONS` = top_up, traffic_gb_topup, lte_gb_topup, main_traffic_reset, referral_payout. Сортировка по revenue убыв., срез `limit` (min 1).

## `get_payment_methods_analytics` (3729–3759)

**Docstring в коде:** есть

```
Аналитика по методам оплаты (Этап 4.5): число транзакций, выручка, успешность, динамика.
```

Исключает только `payment_method = 'balance'` (не referral*). «Динамика» в docstring — в теле только агрегаты за всё время, без ряда по дням.

## `get_users_without_real_payment_with_keys` (3762–3791)

**Docstring в коде:** есть

```
Пользователи с хотя бы одним VPN-ключом, у которых нет ни одной успешной
транзакции, оплаченной реальными деньгами.

Реальными деньгами НЕ считаются payment_method из чёрного списка
Balance / ReferralBalance (регистр не важен). Проверка идёт по всем успешным
транзакциям пользователя (включая пополнения баланса), а не только по покупке ключа.
```

Фильтр `_REAL_MONEY_SQL`: не `balance` и не `referralbalance`.

## `get_trial_key_stats` (3794–3875)

**Docstring в коде:** есть

```
Метрики по триальным ключам и их продлениям.

- active_trial_users: пользователи с ключом tag='trial' и expire_at в будущем
- total_trial_used: users.trial_used = 1
- extended_trial_*: DISTINCT user_id с успешной транзакцией action='extend',
  где metadata.key_id указывает на первый ключ пользователя (trial выдаётся
  первым), и users.trial_used = 1.

Важно: при продлении key_id НЕ меняется (UPDATE vpn_keys), но tag
перезаписывается на 'paid' (см. process_successful_payment в bot/handlers.py),
поэтому нельзя фильтровать текущий tag='trial' для продлений — используем
связку «первый ключ пользователя» + trial_used.
```

Ключи результата: `active_trial_users`, `total_trial_used`, `extended_trial_real_money`, `extended_trial_via_referral_balance`. Первый ключ: `ORDER BY datetime(COALESCE(created_at, '1970-01-01')) ASC, key_id ASC`.

## `get_referrals_analytics` (3878–3938)

**Docstring в коде:** есть

```
Аналитика реферальной программы (Этап 6.1) поверх существующих полей/функций,
без создания новой реферальной системы.
```

`spent_total = max(0, accrued_total - current_balance_total)` из SUM `referral_balance_all` / `referral_balance`. `active_referrals` — DISTINCT user_id с ключом, у которого expire_at NULL или в будущем.

## `get_top_referrers` (3941–3979)

**Docstring в коде:** есть

```
Топ пользователей по рефералам: число приглашённых и число платящих рефералов.
```

GROUP BY referred_by, ORDER BY invited_count DESC. `withdrawn_total` — SUM `referral_withdrawal_requests.amount` со `status = 'paid'`.

## `get_top_buyers` (3982–4013)

**Docstring в коде:** есть

```
Топ пользователей по покупкам (Этап 6.4): сумма, число успешных транзакций, средний чек.
```

`avg_check` считается в Python из revenue/successful_tx. Также отдаёт `users.total_spent`.

## `_promo_plans_label` (4016–4027)

**Docstring в коде:** есть

```
Человекочитаемое ограничение тарифов для карточки купона в админке.
```

None/пусто/битый JSON/пустой список → «все тарифы». Иначе «тарифы: 1, 2, …».

## `_promo_segment_label` (4030–4043)

**Docstring в коде:** есть

```
Человекочитаемое ограничение сегмента для карточки купона в админке.
```

Пустой type → «без сегмента». `no_active_subscription` / `min_total_spent` (порог float, иначе 0) / иначе сырой `st`.

## `get_coupons_analytics` (4046–4122)

**Docstring в коде:** есть

```
Аналитика купонов/промокодов (Этап 6.3) поверх существующих таблиц
promo_codes / promo_code_usages — без создания новой системы купонов.
```

Выручка: `promo_code_usages.order_id` → `transactions.payment_id`; иначе первая сумма из списка tx этого user_id (не «ближайшее время» — в теле берётся `tx_by_user[user_id][0]`). Сортировка результата по revenue убыв. Поля поверх строки promo_codes: uses, discount_sum, revenue, usage_conversion_pct, is_expired, days_left, targeting_plans_label, targeting_segment_label.

## `get_server_cost_entries` (4125–4138)

**Docstring в коде:** нет

```
"""Все server_cost_entries; only_active → status='active'; ORDER BY created_at DESC."""
```

sqlite3.Error → `[]`.

## `create_server_cost_entry` (4141–4180)

**Docstring в коде:** нет

```
"""INSERT в server_cost_entries; вернуть lastrowid или None."""
```

currency/status пустые → `'RUB'` / `'active'`. monthly_cost через float.

## `update_server_cost_entry` (4183–4205)

**Docstring в коде:** нет

```
"""UPDATE разрешённых полей server_cost_entries + updated_at; неизвестные ключи игнорируются."""
```

allowed: server_label, linked_host_name, provider, location, monthly_cost, currency, status, started_at, ended_at, comment. Пустой allowed-набор → False.

## `delete_server_cost_entry` (4208–4217)

**Docstring в коде:** нет

```
"""DELETE FROM server_cost_entries WHERE id = ?; True если удалена строка."""
```

sqlite3.Error → False.

## `get_economics_summary` (4220–4256)

**Docstring в коде:** есть

```
Приблизительная экономика (Этап 7.3): расходы по провайдеру/локации,
итог расходов, сопоставление с выручкой за 30 дней (без точной unit-экономики).
```

Только `status='active'`. Маржа (`gross_profit_estimate_by_currency['RUB']`) = revenue_30d из `get_sales_overview()['d30']` минус сумма monthly_cost в RUB. Прочие валюты — только в `total_monthly_cost_by_currency`, без сопоставления с выручкой.

## `get_revenue_forecast` (4259–4308)

**Docstring в коде:** есть

```
Прозрачный прогноз (Этап 4.6/9): скользящее среднее за 7 дней + линейная
экстраполяция до конца текущего месяца. Помечается как оценка в UI.
```

Средние за 7 дней (окно `-6 days`). `days_left_in_month = max(0, days_in_month - now.day)`. forecast = факт месяца + daily_avg * days_left.

## `get_utm_links` (4311–4324)

**Docstring в коде:** нет

```
"""Все utm_links; only_active → is_active=1; ORDER BY created_at DESC."""
```

sqlite3.Error → `[]`.

## `create_utm_link` (4327–4360)

**Docstring в коде:** нет

```
"""INSERT в utm_links; slug оставляют только [a-zA-Z0-9_-]; пустой slug или IntegrityError → False."""
```

is_active не передаётся (DEFAULT 1 в таблице). IntegrityError (дубль slug) → False без лога.

## `delete_utm_link` (4363–4377)

**Docstring в коде:** есть

```
Удаляет UTM-метку вместе с накопленной статистикой посещений (utm_visits).
```

Сначала DELETE `utm_visits`, затем `utm_links`; rowcount — от второго DELETE.

## `log_utm_visit` (4380–4391)

**Docstring в коде:** есть

```
Best-effort запись события UTM (клик/старт/регистрация/оплата). Никогда не бросает исключение наружу.
```

Любой Exception → warning, без raise. Не проверяет, что slug есть в `utm_links`.

## `set_user_utm_slug_if_absent` (4394–4407)

**Docstring в коде:** есть

```
First-touch атрибуция: записать utm_slug пользователю только если он ещё не задан.
```

UPDATE `users.utm_slug` при NULL или `''`. Колонка добавляется в `_ensure_analytics_tables`.

## `get_utm_analytics` (4410–4452)

**Docstring в коде:** есть

```
Эффективность UTM-меток (Этап 5.4): клики, регистрации, оплаты, выручка, ROI (если задан budget).
```

Клики = COUNT utm_visits WHERE event_type='start' (не 'click'). Регистрации = COUNT users по utm_slug. Оплаты/выручка = успешные не-balance transactions JOIN users.utm_slug. `roi_pct` = (revenue - budget) / budget * 100, если budget truthy; иначе None. Сортировка по revenue убыв.

Покрыто записей инвентаря: **134** (`_now_str` … `get_utm_analytics` включительно, включая `_rebuild_vpn_keys_table.has` и `_rebuild_vpn_keys_table.col`).
