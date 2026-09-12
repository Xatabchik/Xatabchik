# Комментарии: `src/shop_bot/data_manager/database.py` (часть 3)

Хвост `database.py`: от `_describe_transaction_action` до `get_webapp_settings` (последние имена секции до `remnawave_repository.py` в `INVENTORY.md`). Части 1–2 — схема, pending complete/cancel, LTE CRUD (`get_key_lte_state` / `update_key_lte_state`), тарифы. Модульного docstring нет.

Имена — как в инвентаре. `get_gift_code_by_key_id` объявлена дважды (11273 и 11286); в runtime живёт вторая.

**Pending complete/cancel** (`_complete_pending`, `find_and_complete_pending_transaction`, `cancel_pending_transaction`) в этой части **нет** — они выше по файлу. Здесь: запись в `transactions` (`log_transaction`), проверка «уже paid» (`check_transaction_exists`), владение счётом без фильтра статуса (`payment_owned_by_user`).

**LTE state CRUD** тоже выше. Здесь: дата/стратегия сброса учитывает LTE-пул; `delete_key_by_email` чистит `key_lte_state`; `delete_user_keys` / `delete_user_completely` строки `key_lte_state` **не** трогают.

**Автозакрытие тикетов** — инварианты в `find_open_tickets_idle_after_admin` / `auto_close_idle_admin_tickets` (форум снаружи, см. `support_bot/idle_close.py`).

| Имя | Значение | Зачем |
|-----|----------|--------|
| `_TX_ACTION_LABELS` | new/gift/extend/top_up/traffic_gb_topup/`lte_gb_topup`/main_traffic_reset | подписи для панели |
| `UNREACHABLE_REASON_BLOCKED` / `_DEACTIVATED` | `"blocked"` / `"deactivated"` | `#` 9082–9086: исключать из рассылок |
| `TICKET_AUTO_CLOSE_DAYS_MAX` | 365 | потолок настройки |
| `TICKET_AUTO_CLOSE_BATCH` | 50 | пачка SELECT/UPDATE |
| `TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER` | текст ошибки формы | дроби не принимаем |
| `_TICKET_AUTO_CLOSE_WHOLE_RE` | `^\d+$` | только целое |
| `MANAGED_BOT_TOKEN_PREFIX` | `enc1$` | формат at-rest |
| `REFERRAL_LINK_*` / `REFERRAL_UNLINK_*` | строковые статусы | UI pending-action / админка |
| `EMAIL_ONLY_TELEGRAM_ID_MIN/MAX` | `999000000000`…`999999999999` | виртуальные webapp-id |

---

## `_describe_transaction_action` (8006–8023)

**Docstring в коде:** есть

```
Формирует человекочитаемое описание действия транзакции по её metadata.
```

`action` / `key_id` (int или None) / `size_gb` / `provider_transaction_id` (`_provider_transaction_id_from_meta`). Подпись: `_TX_ACTION_LABELS`, иначе «Оплата тарифа» при `action is None`, иначе сырой `action`. `metadata is None` → пустой dict для `.get("action")`; дальше поля читаются только если `isinstance(metadata, dict)`.

## `_find_nearest_key_id` (8025–8060)

**Docstring в коде:** есть

```
Best-effort подбор ключа для старых транзакций, в metadata которых ещё не сохранялся key_id.
Ищет ключ того же пользователя (и хоста, если известен), созданный ближе всего по времени
к моменту транзакции (в пределах window_minutes).
```

Нет `user_id` или `created_date` → None. Хост задан — фильтр `user_id + host_name`. Сортировка `ABS(strftime created_at − created_date)`. После SELECT ещё раз проверяет `diff > window_minutes * 60` (default 20); ошибка разбора дат — ключ всё равно возвращается. Любой except снаружи → None.

## `log_transaction` (8062–8128)

**Docstring в коде:** есть

```
Записывает транзакцию в таблицу `transactions`.

ВАЖНО: используем устойчивое к блокировкам подключение (WAL + busy_timeout + retry),
как и остальные высококонкурентные write-пути (см. _connect_pending_db/_retry_sqlite).
Раньше здесь использовалось обычное sqlite3.connect() без retry: под конкурентной
нагрузкой (несколько платежей одновременно) запись могла молча "потеряться" из-за
'database is locked', при этом баланс пользователя уже был обновлён другой функцией —
из-за этого доход в аналитике не менялся, хотя баланс пополнялся.

Не бросает исключение наружу (некоторые вызовы в handlers.py не обёрнуты в try/except
и не должны прерывать выдачу уже оплаченного ключа) — вместо этого возвращает False
и подробно логирует ошибку, чтобы проблема не оставалась незамеченной.
```

Это **ledger**, не pending complete/cancel: pending-строку не меняет. `sqlite3.Error` → False + error-лог.

### `log_transaction._work` (8076–8122)

**Docstring в коде:** нет

```
"""INSERT или UPDATE по payment_id: слить metadata, обновить поля; без pid — всегда INSERT."""
```

Непустой `payment_id`: SELECT metadata; если строка есть — `_tx_meta_dict` merge (`existing` затем `new_meta`), UPDATE username/user_id/status/суммы/метода/metadata. `COALESCE` не затирает currency/method пустым None. Нет строки или пустой pid — INSERT с `created_date=datetime.now()`.

## `get_paginated_transactions` (8130–8179)

**Docstring в коде:** нет

```
"""Страница transactions (ORDER BY created_date DESC): host/plan из metadata, action-label, legacy key_id."""
```

`sqlite3.connect(DB_FILE)` без retry. Битый JSON → host/plan `'Error'`. Нет metadata → `'N/A'` + `_describe_transaction_action({})`. `#` 8164–8165: нет `key_id` и `action in (None, 'new', 'extend', 'gift')` — `_find_nearest_key_id`; удача → `key_id_guessed=True`. Ошибка → `[], total` (total мог уже прочитаться).

## `get_transactions_paginated` (8181–8278)

**Docstring в коде:** есть

```
Универсальная выборка транзакций с фильтром по пользователю, поиском и сортировкой.
```

page/per_page: мусор → 1 / 10, оба `max(1, …)`. Поиск LIKE по user_id, transaction_id, username, payment_id, method, status, metadata. Сортировка только из map `date/amount/payment_method/status` (иначе date); не-date добавляет `, created_date DESC`. Тот же enrich/guess, что у `get_paginated_transactions`.

## `set_trial_used` (8280–8288)

**Docstring в коде:** нет

```
"""Выставить users.trial_used = 1 для telegram_id."""
```

Ошибка — error-лог, без raise.

## `add_new_key` (8290–8362)

**Docstring в коде:** нет

```
"""INSERT vpn_keys; вернуть lastrowid или None (IntegrityError/ошибка)."""
```

Хост — `normalize_host_name` (пусто → None). Email — `_normalize_email` или strip в `email` и `key_email`. `expire_at` из ms, иначе `_now_str()`. `traffic_limit_strategy` default `"NO_RESET"`. LTE-строку не создаёт (это `get_key_lte_state` при первом учёте).

## `_apply_key_updates` (8365–8384)

**Docstring в коде:** нет

```
"""Динамический UPDATE vpn_keys по dict; пустой updates → False. Всегда пишет updated_at."""
```

Имена колонок — ключи dict как есть. `rowcount > 0`.

## `update_key_fields` (8387–8443)

**Docstring в коде:** нет

```
"""Собрать updates из kwargs и вызвать _apply_key_updates. None у большинства полей = «не трогать»."""
```

`missing_from_server_at` и `next_traffic_reset_at` сравниваются с `_UNSET`: явный `None` пишется в колонку. `email` нормализуется в обе колонки. `traffic_limit_strategy or "NO_RESET"`. `host_name` нормализуется. `traffic_boost_bytes` — `int(...)`.

## `apply_key_monthly_reset_fields` (8446–8488)

**Docstring в коде:** есть

```
Записать `traffic_limit_strategy` и `next_traffic_reset_at` по тарифу ключа.

- MONTH_ROLLING только при лимите основного пула (это поле уходит в Remnawave).
- Дата сброса ставится, если ограничен основной ИЛИ LTE-пул.
- `restart_cycle=True` — новая покупка/смена тарифа: окно от «сейчас».
- иначе не трогаем уже проставленную будущую дату; при её отсутствии
  выравниваем по дате создания ключа.
```

План: аргумент или `resolve_plan_for_key`. Если у плана нет main-лимита, берётся `key.traffic_limit_bytes`; `> 0` → стратегия всё равно `MONTH_ROLLING`. `expire_main_boost=True` → `traffic_boost_bytes=0`. LTE-строку `key_lte_state` не меняет — только колонки ключа.

## `backfill_monthly_traffic_reset_for_existing_keys` (8491–8530)

**Docstring в коде:** есть

```
Проставить MONTH_ROLLING и дату сброса уже выданным лимитным/LTE-ключам.

Идемпотентно: будущая дата не сдвигается, стратегия переписывается только
если основной пул ограничен, а в колонке ещё не MONTH_ROLLING.
```

Триал/подарок без `plan_id` (`key_is_unbilled_trial_or_gift` и `parse_plan_id_from_key is None`) — skip. Оба лимита ≤ 0 — skip. Счётчик — фактическое изменение strategy/даты после `apply_key_monthly_reset_fields(..., restart_cycle=False)`. Ошибка одного ключа — warning, цикл дальше.

## `delete_key_by_email` (8533–8568)

**Docstring в коде:** нет

```
"""Удалить ключ(и) по email/key_email и связанные неактивированные подарки, снапшоты, LTE-state."""
```

`#` 8538–8539: как `delete_key_by_id` — неактивированный подарок уходит вместе с ключом. По каждому `key_id`: `user_gifts` (`is_activated = 0`), `key_node_usage_snapshots`, **`key_lte_state`**, затем DELETE `vpn_keys`. True если `rowcount` ключей > 0.

## `get_user_keys` (8571–8584)

**Docstring в коде:** нет

```
"""Все vpn_keys пользователя, newest first; строки через _normalize_key_row. Ошибка → []."""
```

## `get_key_by_id` (8587–8597)

**Docstring в коде:** нет

```
"""Один vpn_keys по key_id или None."""
```

## `get_key_by_email` (8600–8614)

**Docstring в коде:** нет

```
"""Первый vpn_keys, где email или key_email совпал с нормализованным адресом."""
```

## `get_key_by_remnawave_uuid` (8617–8633)

**Docstring в коде:** нет

```
"""vpn_keys по remnawave_user_uuid (strip, LIMIT 1). Пустой uuid → None."""
```

## `update_key_info` (8636–8642)

**Docstring в коде:** нет

```
"""update_key_fields: новый remnawave uuid и expire_at_ms плюс **kwargs."""
```

## `update_key_host_and_info` (8645–8658)

**Docstring в коде:** нет

```
"""update_key_fields: хост + remnawave uuid + expire_at_ms плюс **kwargs."""
```

## `get_next_key_number` (8661–8662)

**Docstring в коде:** нет

```
"""len(get_user_keys(user_id)) + 1 — следующий порядковый номер, не MAX(key_id)."""
```

## `get_keys_for_host` (8665–8679)

**Docstring в коде:** нет

```
"""vpn_keys хоста: TRIM(host_name) = TRIM(normalize_host_name(...))."""
```

## `set_key_auto_renew` (8682–8691)

**Docstring в коде:** нет

```
"""auto_renew = 1/0 для одного ключа; True если rowcount > 0."""
```

## `set_all_keys_auto_renew_for_user` (8694–8704)

**Docstring в коде:** есть

```
Mass-update auto_renew for all keys of a user. Returns count of updated rows.
```

Ошибка → 0.

## `get_keys_for_auto_renew` (8707–8730)

**Docstring в коде:** есть

```
Return keys with auto_renew=1 expiring within the next `hours_before` hours.
```

`expire_at > now` и `<= now + hours` (default 24). Уже истёкшие не попадают. Ошибка → [].

## `_key_matches_search` (8733–8741)

**Docstring в коде:** есть

```
Регистронезависимая (в т.ч. кириллица) проверка вхождения подстроки
в key_email, email или user_key_name. SQL LIKE/LOWER() в SQLite сворачивают
регистр только для ASCII, поэтому сравнение делается на стороне Python.
```

`needle_lower` уже в нижнем регистре у вызывающего.

## `search_user_keys_by_email` (8744–8763)

**Docstring в коде:** есть

```
Поиск ключей пользователя по key_email, email или user_key_name.
```

Пустой запрос → []. Грузит все ключи user_id, фильтр в Python.

## `search_all_keys_by_email` (8766–8784)

**Docstring в коде:** есть

```
Поиск всех ключей (администраторам) по key_email, email или user_key_name.
```

То же, без фильтра user_id.

## `get_all_vpn_users` (8787–8797)

**Docstring в коде:** нет

```
"""DISTINCT user_id из vpn_keys (не таблица users). Ошибка → []."""
```

## `update_key_status_from_server` (8800–8840)

**Docstring в коде:** нет

```
"""Синхронизировать ключ с payload панели: uuid/expiry/url и снять missing; нет клиента — пометить missing."""
```

Есть `client_data`, нет ключа в БД → False. Dict: `uuid`/`id`, `expireAt`/`expiryDate`, `subscriptionUrl`/`subscription_url`. Иначе атрибуты `id`/`uuid`, `expiry_time`, `subscription_url`. `#` 8830–8832: не удалять при временном отсутствии на панели — `missing_from_server_at=_now_str()`. Нет `client_data` и нет ключа → True. LTE-state не трогает.

## `get_daily_stats_for_charts` (8843–8875)

**Docstring в коде:** нет

```
"""Словари users/keys: дата → COUNT за последние `days` (default 30)."""
```

Ключи: `date(COALESCE(created_at, updated_at, CURRENT_TIMESTAMP))`.

## `get_recent_transactions` (8878–8911)

**Docstring в коде:** нет

```
"""Последние vpn_keys JOIN users (не таблица transactions): key_id, host, created_at, telegram_id, username."""
```

По коду: имя обманчиво — это свежие ключи, не ledger.

## `get_all_users` (8914–8923)

**Docstring в коде:** нет

```
"""SELECT * FROM users ORDER BY registration_date DESC. Ошибка → []."""
```

## `get_users_paginated` (8925–9041)

**Docstring в коде:** есть

```
Вернуть пользователей постранично и общее количество (с учётом фильтра).

Фильтр q ищет по username (LIKE) и по текстовому представлению telegram_id.
```

LEFT JOIN vpn_keys: `keys_count` и `active_keys_count` (ключ есть, `missing_from_server_at IS NULL`, `expire_at > CURRENT_TIMESTAMP`). `ORDER BY {order_by}` из белого списка sort-ключей (баланс, реф. баланс, active_keys, spent, registration, telegram_id, username). Ошибка → `[], 0`.

## `get_keys_counts_for_users` (9043–9061)

**Docstring в коде:** есть

```
Вернуть словарь {user_id: keys_count} по списку пользователей.
```

Пустой список → `{}`. Пользователи без ключей в dict не попадают.

## `ban_user` (9063–9070)

**Docstring в коде:** нет

```
"""users.is_banned = 1 по telegram_id."""
```

## `unban_user` (9072–9079)

**Docstring в коде:** нет

```
"""users.is_banned = 0 по telegram_id."""
```

`#` 9082–9086 (между unban и mark): недоступность для рассылок, см. `telegram_reachability`.

## `mark_user_unreachable` (9091–9115)

**Docstring в коде:** есть

```
Отметить пользователя как недоступного в Telegram.

`reason` — 'blocked' (заблокировал бота) или 'deactivated' (аккаунт удалён/деактивирован).
Пользователь будет исключён из последующих рассылок, пока не напишет боту снова
(см. mark_user_reachable — вызывается автоматически при любом входящем сообщении/callback).
```

`unreachable_since = COALESCE(unreachable_since, CURRENT_TIMESTAMP)` — повторный mark не сдвигает «с какого момента».

## `mark_user_reachable` (9117–9135)

**Docstring в коде:** есть

```
Снять отметку недоступности — пользователь снова взаимодействовал с ботом
(значит, разблокировал его или его аккаунт снова активен).
```

UPDATE только при `is_unreachable = 1`. Снимает reason и since.

## `get_reachability_stats` (9137–9166)

**Docstring в коде:** есть

```
Статистика по доступности пользователей в Telegram: сколько всего
пользователей, сколько реально доступны (не забанены и не недоступны),
сколько заблокировали бота, сколько деактивировали аккаунт.
```

Ключи: `total`, `banned`, `blocked_bot`, `deactivated`, `reachable`. Ошибка — нули.

## `delete_user_keys` (9168–9182)

**Docstring в коде:** нет

```
"""Удалить неактивированные подарки ключей пользователя и сами vpn_keys."""
```

По коду: **не** удаляет `key_lte_state` / `key_node_usage_snapshots` / `key_usage_monitor` (в отличие от `delete_key_by_email` / `delete_key_by_id`).

## `delete_user_completely` (9185–9304)

**Docstring в коде:** есть

```
Полностью удалить пользователя и все связанные с ним данные.

:param user_id: Telegram ID пользователя (users.telegram_id, а также user_id в связанных таблицах).
:return: True при успешном удалении, False при ошибке.
```

Порядок (комментарии в коде): support_messages → support_tickets → неактивированные gifts → key_usage_monitor → vpn_keys → **pending_transactions** и **transactions** → gift_token_claims → promo_code_usages → referral_payout_methods (заявки на вывод **не** трогает: история/несписанное) → webapp_auth_requests → captcha status/challenges (`#` 9273–9275: иначе повторная регистрация того же id пропустит капчу) → `referred_by = NULL` у рефералов → DELETE users. После commit — `_cleanup_ticket_media` по собранным ticket_id.

По коду: **нет** DELETE `key_lte_state` / `key_node_usage_snapshots`. Pending complete/cancel не вызываются — строки pending просто удаляются.

## `create_support_ticket` (9306–9330)

**Docstring в коде:** нет

```
"""Вернуть уже открытый тикет пользователя или INSERT нового; id или None."""
```

SELECT open ORDER BY updated_at DESC LIMIT 1 внутри try; except → всё равно INSERT. Не возвращает флаг «создан».

## `get_or_create_open_ticket` (9332–9356)

**Docstring в коде:** есть

```
Возвращает ID открытого тикета пользователя и флаг, создан ли новый.
Если открытого тикета нет — создаёт новый и возвращает (id, True).
```

Ошибка → `(None, False)`.

## `add_support_message` (9358–9374)

**Docstring в коде:** нет

```
"""INSERT support_messages и bump support_tickets.updated_at; lastrowid или None."""
```

`sender` пишется как передан (`admin` / user / `note`) — это last-sender для автозакрытия.

## `update_ticket_thread_info` (9376–9388)

**Docstring в коде:** нет

```
"""Записать forum_chat_id и message_thread_id, обновить updated_at."""
```

По коду: bump `updated_at` сбрасывает таймер idle-close (переоткрытие/привязка темы).

## `get_ticket` (9390–9400)

**Docstring в коде:** нет

```
"""SELECT * support_tickets по ticket_id или None."""
```

## `get_ticket_by_thread` (9402–9415)

**Docstring в коде:** нет

```
"""Тикет по паре forum_chat_id (str) + message_thread_id (int)."""
```

## `get_user_tickets` (9417–9435)

**Docstring в коде:** нет

```
"""Тикеты пользователя, опционально status; ORDER BY updated_at DESC."""
```

## `get_support_message` (9437–9451)

**Docstring в коде:** есть

```
Одно сообщение тикета. Нужно для отдачи вложений в панели.
```

## `resolve_db_file_path` (9454–9470)

**Docstring в коде:** есть

```
Абсолютный путь к users.db без зависимости от cwd процесса.

``os.path.abspath("users.db")`` берёт текущую папку процесса. Бот с
cwd=/xatabchik пишет в /xatabchik/ticket_files, а если Flask когда-то
стартовал из webhook_server — панель искала файлы там. Админка живёт
в src/shop_bot/webhook_server/, вложения — рядом с базой, не в исходниках.
```

Абсолютный `db_file`/`DB_FILE` → `resolve()`. Иначе `/app/project/<name>` если файл есть, иначе `Path(__file__).parents[3] / name`. `#` 9469: database.py → корень репо.

## `get_ticket_media_root` (9473–9478)

**Docstring в коде:** есть

```
Каталог вложений рядом с users.db, не в webhook_server/.
```

`TICKET_FILES_DIR` (expanduser+resolve) или `<db_parent>/ticket_files`.

## `list_closed_ticket_ids_older_than` (9481–9500)

**Docstring в коде:** есть

```
Закрытые тикеты с updated_at не новее cutoff (наивный ISO-текст SQLite).
```

cutoff с `strftime` → `"%Y-%m-%d %H:%M:%S"`, иначе `str(cutoff)`.

## `clear_support_message_media` (9503–9516)

**Docstring в коде:** есть

```
Обнуляет media у сообщений тикета после TTL/удаления файлов.
```

Только строки с `media IS NOT NULL`. Возвращает rowcount.

## `get_ticket_messages` (9519–9531)

**Docstring в коде:** нет

```
"""Все support_messages тикета по created_at ASC."""
```

## `set_ticket_status` (9533–9545)

**Docstring в коде:** нет

```
"""UPDATE status и updated_at. Статус не валидируется."""
```

По коду: `updated_at = CURRENT_TIMESTAMP` — закрытие/переоткрытие двигает порог idle-close.

## `update_ticket_subject` (9547–9559)

**Docstring в коде:** нет

```
"""UPDATE subject и updated_at."""
```

Тоже bump `updated_at`.

## `_cleanup_ticket_media` (9561–9568)

**Docstring в коде:** есть

```
Файлы вложений живут вне SQLite — удаляем каталог вместе с тикетом.
```

`ticket_media.delete_ticket_media_dir`; ошибка — error-лог, без raise.

## `delete_ticket` (9571–9590)

**Docstring в коде:** нет

```
"""DELETE messages + ticket; при rowcount тикета — _cleanup_ticket_media."""
```

Cleanup **после** commit, только если тикет реально удалён.

## `_ticket_forum_target` (9593–9606)

**Docstring в коде:** нет

```
"""Словарь ticket_id/user_id/forum_chat_id/thread_id или None, если темы нет/битая."""
```

Пустой `forum_chat_id` или `thread_id in (None, "")` → None. TypeError/ValueError → None.

---

## Автозакрытие: валидация и SQL

`validate_*` — форма настроек (отказ на дробь). `parse_*` — рантайм (мусор → 0 = выкл). Закрытие только если last message `sender='admin'` **и** `updated_at` старше порога.

## `validate_ticket_auto_close_days` (9617–9636)

**Docstring в коде:** есть

```
Для формы настроек: только целое 0–365.

Дроби вроде 7.5 / 7.0 не принимаем — иначе ``int("7.5")`` тихо превращал
значение в 0 (выключено). Пустое поле = 0.
```

`(days, None)` или `(None, TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER)`. `None` raw → `(0, None)`. `> 365` — ошибка, не клип.

## `parse_ticket_auto_close_days` (9639–9650)

**Docstring в коде:** есть

```
0 — выключено. Нецелое и мусор → 0. Целое больше 365 режем потолком.
```

Сначала validate; если не вышло — `int(str)` и `min(n, 365)` при `n > 0`.

## `get_ticket_auto_close_days` (9653–9654)

**Docstring в коде:** нет

```
"""parse_ticket_auto_close_days(get_setting('ticket_auto_close_days'))."""
```

## `find_open_tickets_idle_after_admin` (9657–9709)

**Docstring в коде:** есть

```
Открытые тикеты, где последнее сообщение — ответ админа старше ``days`` суток.

Заметки (sender=note) и сообщения пользователя сбрасывают таймер: закрываем
только если пользователь после ответа админа молчит.

``updated_at`` тоже должен быть старше порога: переоткрытие тикета без нового
ответа админа обновляет ``updated_at`` и не должно сразу закрыть его снова.
```

`days <= 0` или `limit <= 0` → `[]`. `now` default `datetime.utcnow()`. Last message = `MAX(message_id)`, не max(created_at). `ORDER BY last.created_at ASC, ticket_id ASC LIMIT`.

## `auto_close_idle_admin_tickets` (9712–9776)

**Docstring в коде:** есть

```
Закрывает найденные простаивающие тикеты. Форум — снаружи.

UPDATE ещё раз проверяет, что последнее сообщение всё ещё от админа,
оно старше порога, и ``updated_at`` тоже старше порога: иначе ответ
пользователя или переоткрытие между SELECT и UPDATE закрыли бы живой тикет.
```

Инварианты (SELECT + повтор в UPDATE / RETURNING):

| Условие | Зачем |
|---------|--------|
| `status = 'open'` | не закрывать повторно |
| last `sender = 'admin'` | user/`note` — живой диалог |
| last `created_at <= cutoff` | молчание ≥ N суток после ответа админа |
| `updated_at <= cutoff` | reopen / bump subject/thread не закрывать сразу |
| last = `ORDER BY message_id DESC LIMIT 1` | тот же критерий, что MAX(message_id) в SELECT |
| `ticket_id IN (...)` | только пачка из find |
| форум не трогает | `forum_targets` для `idle_close` |

`days_n = parse_ticket_auto_close_days(days)`; пусто/нет id → `{"count": 0, "days": days_n, "forum_targets": [], "tickets": []}`. timeout=15. SQL error → тот же empty (days сохранён). `count` = число RETURNING-строк, не размер входа.

## `bulk_close_open_tickets` (9779–9804)

**Docstring в коде:** есть

```
Один UPDATE всех открытых тикетов. Форум/уведомления — на стороне вызывающего.

Возвращает ``{"count": int, "forum_targets": list[dict]}``.
```

`BEGIN IMMEDIATE`. `count` = число выбранных open-строк (до UPDATE). Ошибка → `{0, []}`.

## `bulk_delete_all_tickets` (9807–9836)

**Docstring в коде:** есть

```
Один DELETE всех тикетов и сообщений. Вложения на диске не трогает.

Возвращает ``{"count": int, "ticket_ids": list[int], "forum_targets": list[dict]}``.
```

Сначала SELECT всех, потом DELETE messages + tickets. Медиа — `cleanup_ticket_media_ids` у вызывающего.

## `cleanup_ticket_media_ids` (9839–9852)

**Docstring в коде:** есть

```
Удаляет каталоги вложений пачкой. Ошибки по одному id не рвут остальные.
```

Не-int пропускает. `_cleanup_ticket_media` +1 даже если внутри только залогировали сбой импорта (внутренний except глотает). Внешний except — exception-лог, без +1.

## `get_tickets_paginated` (9854–9877)

**Docstring в коде:** нет

```
"""Страница support_tickets, опционально status; ORDER BY updated_at DESC."""
```

Ошибка → `[], 0`.

## `get_open_tickets_count` (9879–9887)

**Docstring в коде:** нет

```
"""COUNT тикетов со status='open'. Ошибка → 0."""
```

## `get_closed_tickets_count` (9889–9897)

**Docstring в коде:** нет

```
"""COUNT тикетов со status='closed'. Ошибка → 0."""
```

## `get_all_tickets_count` (9899–9907)

**Docstring в коде:** нет

```
"""COUNT всех support_tickets. Ошибка → 0."""
```

## `get_key_usage_monitor` (9915–9925)

**Docstring в коде:** нет

```
"""Строка key_usage_monitor по key_id или None."""
```

Напоминания о нулевом трафике / overlimit — не LTE-state.

## `ensure_key_usage_monitor_row` (9928–9938)

**Docstring в коде:** нет

```
"""INSERT OR IGNORE (key_id, user_id) в key_usage_monitor."""
```

## `update_key_usage_monitor` (9941–9990)

**Docstring в коде:** нет

```
"""Частичный UPDATE монитора: только переданные не-None поля. Пустой набор → False."""
```

Поля: first_seen_usage_at, last_reminder_at, last_checked_at, last_devices_count, last_traffic_bytes, overlimit_notified_count, overlimit_notified_at.

---

## Франшиза / managed bots

Константы `FRANCHISE_*` в коде помечены DEPRECATED — читаются настройки.

## `get_franchise_percent_default` (10000–10006)

**Docstring в коде:** есть

```
Получить процент комиссии франшизы из настроек.
```

`franchise_commission_percent`, default `35.0`.

## `get_franchise_min_withdraw` (10009–10015)

**Docstring в коде:** есть

```
Получить минимум для вывода франшизников из настроек.
```

`franchise_min_withdraw_rub`, default `1500.0`.

## `resolve_factory_bot_id` (10018–10036)

**Docstring в коде:** есть

```
Return internal managed bot id for a Telegram bot user id.

Root (main) bot => 0.
```

`tg_id <= 0` / ошибка / нет активной строки → 0. Только `COALESCE(is_active,1)=1`.

## `_managed_bot_token_secret` (10042–10051)

**Docstring в коде:** есть

```
Ключ шифрования токенов клонов: SHOPBOT_SECRET_KEY или стабильная запись в settings.
```

Нет env и settings → `secrets.token_hex(32)` пишется в `managed_bot_token_key`. Материал: `sha256("managed-bot-token|{material}")`.

## `_managed_bot_token_pad` (10054–10060)

**Docstring в коде:** нет

```
"""HMAC-SHA256 поток (secret, nonce‖counter) длиной n — pad для XOR токена."""
```

## `_backfill_encrypt_secrets_at_rest` (10063–10115)

**Docstring в коде:** есть

```
Зашифровать уже сохранённые plaintext-секреты (settings / hosts / SSH-цели).
```

`SECRET_SETTING_KEYS` в `bot_settings`; `xui_hosts.ssh_password` / `remnawave_api_token`; `speedtest_ssh_targets.ssh_password`. Уже `enc1$` не трогает. Ошибки секций — `pass`; общий sqlite — warning.

## `encrypt_managed_bot_token` (10118–10131)

**Docstring в коде:** есть

```
Зашифровать токен клона для хранения. Уже enc1$ не трогаем.
```

Пусто → как есть. Формат: `enc1${nonce.hex()}${cipher.hex()}${mac}`.

## `decrypt_managed_bot_token` (10134–10154)

**Docstring в коде:** есть

```
Расшифровать токен. Legacy plaintext (без enc1$) возвращается как есть.
```

MAC mismatch или except → `""` (не plaintext).

## `_row_with_decrypted_token` (10157–10163)

**Docstring в коде:** нет

```
"""Скопировать row и расшифровать поле token, если оно непустое."""
```

## `get_managed_bot` (10166–10176)

**Docstring в коде:** нет

```
"""managed_bots по внутреннему id, токен расшифрован. Ошибка → None."""
```

## `get_managed_bot_by_telegram_id` (10179–10189)

**Docstring в коде:** нет

```
"""managed_bots по telegram_bot_user_id, токен расшифрован."""
```

## `list_active_managed_bots` (10192–10201)

**Docstring в коде:** нет

```
"""Все активные клоны (COALESCE(is_active,1)=1), токены расшифрованы."""
```

## `update_managed_bot_active` (10204–10219)

**Docstring в коде:** есть

```
Параметризованно выставить is_active (0/1). Схему таблицы не меняет.
```

Битый bot_id/is_active → False.

## `get_managed_bots_by_owner` (10222–10245)

**Docstring в коде:** есть

```
Список клонов владельца без токена (токен не отдаём в UI).
```

Колонки: id, telegram_bot_user_id, username, owner_telegram_id, referrer_bot_id, is_active, created_at.

## `purge_managed_bot_stats` (10248–10260)

**Docstring в коде:** есть

```
Удалить активность и комиссии клона. Идемпотентно, ошибки не пробрасывает.
```

## `_purge_managed_bot_stats_on_cursor` (10263–10265)

**Docstring в коде:** нет

```
"""DELETE factory_user_activity и partner_commissions по bot_id на переданном cursor."""
```

Не трогает `partner_withdraw_requests`.

## `delete_managed_bot` (10268–10316)

**Docstring в коде:** есть

```
Удалить строку managed_bots и статистику клона.

factory_user_activity и partner_commissions очищаются. Заявки на вывод
(partner_withdraw_requests), включая approved/paid, сохраняются для аудита.

Если передан owner_telegram_id — удаляем только при совпадении владельца.
Сбой очистки статистики не блокирует удаление самой записи.
```

Нет строки / owner не совпал / `owner_id <= 0` → False.

## `get_factory_cabinet` (10319–10352)

**Docstring в коде:** есть

```
Статистика кабинета клона (пользователи/сообщения/прямые клоны/баланс).
```

База из `get_partner_cabinet`; плюс SUM(messages_count), COUNT клонов с `referrer_bot_id = b`. `b <= 0` — без этих запросов.

## `create_managed_bot` (10355–10419)

**Docstring в коде:** есть

```
Register a managed bot.

If the telegram bot user id already exists, the current owner may rotate
token/username. A different user cannot take over ``owner_telegram_id``.
```

Пустой токен после encrypt → `False, "Токен пустой.", None`. Чужой owner / IntegrityError / UPDATE rowcount 0 → «уже зарегистрирован другим владельцем». `#` 10381, 10389–10390, 10415: UNIQUE и WHERE owner против takeover.

## `record_factory_activity` (10422–10449)

**Docstring в коде:** есть

```
Upsert activity row (unique users + messages count).
```

`#` 10429: root bot (`b <= 0`) не трекаем. `u <= 0` — return. ON CONFLICT: last_seen + messages_count+1. Except — молча.

## `_is_card_payment_method` (10452–10459)

**Docstring в коде:** нет

```
"""True для yookassa/platega/heleket/yoomoney; balance/«баланс» и пусто — False."""
```

`#` 10458: «Card-like providers (as configured in this project)».

## `accrue_partner_commission` (10462–10571)

**Docstring в коде:** есть

```
Accrue partner commission for a managed bot.

Only card payments are counted. Internal balance payments are ignored.
Idempotent by (bot_id, payment_id).
```

`b <= 0` / не card / пустой pid / битый user/amount / `amt<=0` / `percent<=0` / `com<=0` → False. Self-purchase (`#` 10513–10516): buyer==owner; buyer.referred_by==owner; buyer==owner referrer-бота. `INSERT OR IGNORE` — повтор того же (bot_id, payment_id) → False.

## `get_partner_cabinet` (10574–10617)

**Docstring в коде:** есть

```
Return partner cabinet stats for managed bot.
```

users из activity; gross/commission из `partner_commissions`; requested = SUM withdraw `pending|approved|paid`; `available = max(0, commission_total - requested_withdraw)`. `b <= 0` — нули + текущий percent.

## `list_partner_requisites` (10622–10644)

**Docstring в коде:** есть

```
Return all payout requisites for a partner (owner) within a managed bot.
```

`b<=0` или `owner<=0` → []. ORDER `is_default DESC, created_at DESC`.

## `get_default_partner_requisite` (10647–10656)

**Docstring в коде:** есть

```
Return the default payout requisite for a partner, if any.
```

Первый с `is_default==1`, иначе `items[0]`, иначе None.

## `add_partner_requisite` (10659–10726)

**Docstring в коде:** есть

```
Add a payout requisite for a partner.

requisite_type: 'card' or 'phone'
```

Первая запись всегда default. `rtype` не card/phone → `'card'`. Банк ≤120, value ≤64. Возврат `(ok, message, new_id|None)`.

## `set_default_partner_requisite` (10729–10763)

**Docstring в коде:** есть

```
Set given requisite as default for this bot/owner.
```

Чужой id/owner → «Реквизиты не найдены.» Сначала сброс всех default, потом `is_default=1` по id.

## `delete_partner_requisite` (10766–10811)

**Docstring в коде:** есть

```
Delete a payout requisite.
```

Если удалили default — `#` 10796: newest remaining становится default.

## `create_withdraw_request` (10814–10862)

**Docstring в коде:** есть

```
Create a partner withdraw request.

Enforces minimum (1500 RUB) and available balance.
```

По коду минимум — `get_franchise_min_withdraw()` (настройка, fallback 1500). `b <= 0` → «только во клонах». `amt > available + 1e-9` — отказ. INSERT `status='pending'`. Не списывает комиссию заранее: available уже вычитает pending/approved/paid.

---

## Подарки и рефералы

## `create_user_gift` (10869–10917)

**Docstring в коде:** есть

```
Создать неактивированный подарок от одного пользователя.

Returns: dict with gift_id and gift_code on success, None on error.
```

Код default — `uuid4()[:12]`. `is_activated=0`. IntegrityError (дубль кода) → None.

## `get_user_gift` (10920–10931)

**Docstring в коде:** есть

```
Получить информацию о подарке по ID.
```

## `get_gift_by_code` (10934–10945)

**Docstring в коде:** есть

```
Получить информацию о подарке по коду.
```

`str(gift_code).strip()`.

## `get_user_inactive_gifts` (10948–10979)

**Docstring в коде:** есть

```
Получить список неактивированных подарков пользователя.

Заодно подчищает "осиротевшие" подарки — те, чей связанный ключ (vpn_keys)
уже был удалён (например, стандартной чисткой просроченных ключей), но по
какой-то причине запись в user_gifts не была удалена вместе с ним. Такие
подарки не должны продолжать висеть в списке пользователя.
```

DELETE orphan (`key_id IS NOT NULL` и нет в vpn_keys), затем SELECT `is_activated=0`.

## `activate_user_gift` (10982–11036)

**Docstring в коде:** есть

```
Активировать подарок для пользователя.

Атомарность/защита от race condition: сама активация — это одно UPDATE
с условием `is_activated = 0` прямо в WHERE, и именно `cursor.rowcount`
(а не предварительный SELECT) решает, "выиграл" ли этот вызов гонку.
Так два параллельных запроса на активацию одного и того же подарка не
могут оба посчитать себя успешными — только один получит rowcount=1.

Returns: (success, gift_data)
```

Нет кода → `(False, None)`. Уже активирован / просрочен `expires_at` → `(False, gift)`. Проигрыш гонки → `(False, gift)` без повторного SELECT.

## `_registration_age_seconds` (11039–11049)

**Docstring в коде:** есть

```
Возраст аккаунта в секундах, либо None если даты нет / она не парсится.
```

aware → naive, затем `datetime.now() - reg_dt`.

## `set_referred_by_from_gift` (11052–11089)

**Docstring в коде:** есть

```
Set referred_by to the gift sender when a new user activates a gift.

Guard: skips if the user's registration_date is older than max_age_seconds
(meaning they were already registered before this gift activation).
```

`fid<=0` или `fid==uid` → False. Уже есть referred_by → False. `age is None` — guard возраста не применяется. UPDATE `referred_by IS NULL`. Default окно 1800 с.

## `link_referrer_if_eligible` (11101–11170)

**Docstring в коде:** есть

```
Привязать пользователя к рефереру (users.referred_by), если это допустимо.

Атомарно: UPDATE сразу проверяет условие `referred_by IS NULL` в WHERE и
возвращает успех по `cursor.rowcount` — так что даже при параллельных
вызовах (например, два одновременных запроса complete по одному и тому же
pending-токену) привязка реферера не может произойти дважды и не может
затереть уже существующего реферера.

``max_age_seconds``: если задан, аккаунт старше этого окна не привязывается
(тот же guard, что у ``set_referred_by_from_gift``). Webapp pending-action
передаёт окно, чтобы старый аккаунт с пустым ``referred_by`` нельзя было
late-bind'ить реферальной ссылкой. Админский ручной assign вызывает без
окна — существующая возможность назначить реферала сохраняется.

Возвращает один из: linked, already_linked, self_referral_forbidden,
invalid_referrer, not_eligible.
```

Реферера нет в users → `invalid_referrer`. Invitee нет → `not_eligible`. `row[0] is not None` → `already_linked` (оба исхода одного константного return). Гонка SELECT/UPDATE → `already_linked`. except → `not_eligible`.

## `unlink_referral` (11179–11214)

**Docstring в коде:** есть

```
Снять привязку реферала: обнулить users.referred_by у invitee, если он
действительно привязан к referrer_id.

Возвращает: unlinked, not_linked, not_found, invalid.
```

`uid==rid` или ≤0 → invalid. WHERE `referred_by = rid`.

## `unlink_all_referrals` (11217–11241)

**Docstring в коде:** есть

```
Снять привязку у всех рефералов указанного реферера.

Возвращает (ok, removed_count).
```

## `delete_user_gift` (11244–11254)

**Docstring в коде:** есть

```
Удалить подарок.
```

По коду: True после commit даже при 0 строк; except → False. Ключ не удаляет.

## `link_key_to_gift` (11257–11270)

**Docstring в коде:** есть

```
Связать созданный ключ с подарком.
```

По коду: True без проверки rowcount.

## `get_gift_code_by_key_id` (11273–11284)

**Docstring в коде:** есть

```
Получить код подарка по ID ключа.
```

Первое объявление: `SELECT gift_code … WHERE key_id = ?` (любой статус). Перекрыто следующим def.

## `get_gift_code_by_key_id` (11286–11297)

**Docstring в коде:** есть

```
Получить код подарка по ID ключа.
```

Живая реализация: плюс `is_activated = 0`. Неактивированный подарок по ключу; активированный → None.

## `get_gift_info_by_key_id` (11299–11312)

**Docstring в коде:** есть

```
Получить ID и код подарка по ID ключа. Возвращает (gift_id, gift_code) или (None, None).
```

Тот же фильтр `is_activated = 0`.

---

## Webapp / платежи / auth

## `get_msk_time` (11319–11322)

**Docstring в коде:** есть

```
Текущее время в московской зоне (UTC+3), используется для расчётов сроков в webapp.
```

`datetime.now(utc).astimezone(UTC+3)`.

## `check_transaction_exists` (11325–11350)

**Docstring в коде:** есть

```
Проверить, существует ли уже завершённая транзакция с данным payment_id.

TON Connect пишет в ``transactions`` строку со ``status='pending'`` ещё до
подтверждения в блокчейне. Раньше этот SELECT не фильтровал статус — из-за
этого ``/api/check-payment`` отвечал ``paid: true`` сразу после создания
счёта. Финальный статус TON-вебхука — ``paid`` (см. find_and_complete_ton_transaction).
```

Пустой id → False. Только `LOWER(TRIM(status)) = 'paid'`. Pending-таблицу не смотрит — это не `_complete_pending`.

## `payment_owned_by_user` (11353–11387)

**Docstring в коде:** есть

```
True, если payment_id есть в pending_transactions или transactions у этого user_id.

Статус не фильтруем: владелец должен иметь возможность поллить и pending,
и уже оплаченный счёт. Чужой payment_id даёт False (без различия «нет» / «чужой»).
```

`_connect_pending_db` + `_retry_sqlite` — тот же путь, что pending complete/cancel. sqlite.Error → False.

### `payment_owned_by_user._work` (11367–11381)

**Docstring в коде:** нет

```
"""_ensure_pending_tables; SELECT 1 в pending_transactions, иначе в transactions (оба с user_id)."""
```

## `get_seller_user` (11390–11404)

**Docstring в коде:** есть

```
Вернуть данные продавца (франшиза/партнёрская скидка) для пользователя.

В текущей версии проекта отдельной "seller"-подсистемы нет (есть колонки-заглушки
users.seller_active/seller_sale, по умолчанию выключены), функция возвращает
запись пользователя, если seller_active включён вручную в БД, иначе None.
```

## `get_device_tiers` (11407–11420)

**Docstring в коде:** есть

```
Вернуть тарифные планы, сгруппированные по лимиту устройств, для указанного хоста.

Пока в проекте нет отдельной сущности "device tiers" — используем активные тарифы
хоста (get_plans_for_host) как есть, отсортированные по hwid_device_limit.
```

Фильтр `is_active`, sort по `hwid_device_limit or 0`.

## `get_user_by_auth_token` (11423–11436)

**Docstring в коде:** есть

```
Найти пользователя по постоянному auth-токену (webapp).
```

Пустой token → None.

## `get_auth_token_by_user_id` (11439–11449)

**Docstring в коде:** есть

```
Получить уже выданный постоянный auth-токен пользователя, если есть.
```

## `update_user_auth_token` (11452–11462)

**Docstring в коде:** есть

```
Сохранить постоянный auth-токен для пользователя (webapp).
```

## `invalidate_all_user_auth_tokens` (11465–11491)

**Docstring в коде:** есть

```
Перевыпустить все persistent auth_token пользователей (UUID4).

Используется как remediation после компрометации токенов (например, через
уязвимый /api/auth/telegram-direct). Старые токены в браузерах/клиентах
перестают работать; пользователи должны войти заново.
Возвращает число обновлённых строк.
```

Только строки с непустым `TRIM(auth_token)`. По одному UPDATE на id.

## `hash_password` (11494–11498)

**Docstring в коде:** есть

```
Хэшировать пароль пользователя (PBKDF2-HMAC-SHA256 со случайной солью).
```

Формат `pbkdf2${salt_hex}${digest_hex}`, 200_000 итераций, соль 16 байт hex.

## `verify_password` (11501–11517)

**Docstring в коде:** есть

```
Проверить пароль против сохранённого хэша.

Поддерживает как новый формат (pbkdf2$salt$hash), так и старые аккаунты,
у которых пароль ещё хранится в открытом виде (миграция «на лету»).
```

`hmac.compare_digest` и для plaintext. Пустой stored → False. Битый pbkdf2-разбор → False (не fallback).

## `get_user_by_email` (11520–11534)

**Docstring в коде:** есть

```
Найти локального пользователя webapp по email (для входа по email+паролю).
```

`auth_email = _normalize_email`. Пустая нормализация → None.

## `create_user_by_email` (11537–11569)

**Docstring в коде:** есть

```
Создать "виртуального" (не привязанного к Telegram) пользователя webapp по email+паролю.

Использует псевдо-telegram_id с префиксом 999, чтобы не пересекаться с реальными
Telegram ID (см. handlers.py: str(user_id).startswith("999") — признак несинхронизированного аккаунта).
Пароль сохраняется в виде хэша (см. hash_password/verify_password).
Аккаунт создаётся неподтверждённым (email_verified=0) до прохождения проверки кода.
```

`next_id = MAX(telegram_id in [MIN,MAX]) + 1` или `MIN + 1`. username = local-part email. `agreed_to_terms=1`. Возврат `get_user(next_id)`.

## `update_user_password` (11572–11586)

**Docstring в коде:** есть

```
Обновить (хэшированный) пароль локального webapp-аккаунта по email.
```

## `_hash_verification_code` (11589–11590)

**Docstring в коде:** нет

```
"""sha256(f'{user_id}:{code}') hex — хэш одноразового email-кода."""
```

## `set_email_verification_code` (11593–11612)

**Docstring в коде:** есть

```
Сохранить хэш одноразового кода подтверждения email и время его истечения.
```

TTL default 600 с, `utcnow` + strftime. Пишет hash, expires_at, last_sent_at.

## `get_email_verification` (11615–11632)

**Docstring в коде:** есть

```
Вернуть данные о статусе подтверждения email и последнем отправленном коде.
```

Поля: email_verified, email_code_hash, email_code_expires_at, email_code_last_sent_at, auth_email.

## `check_email_verification_code` (11635–11647)

**Docstring в коде:** есть

```
Проверить введённый код подтверждения против сохранённого хэша (с учётом срока действия).
```

Нет hash/expires → False. Битая дата → False. `utcnow() > expires_at` → False. Сравнение `hmac.compare_digest`. Код не сжигает.

## `mark_email_verified` (11650–11667)

**Docstring в коде:** есть

```
Отметить email пользователя как подтверждённый и очистить код.
```

`email_verified=1`, hash и expires NULL. `pending_email` не трогает.

## `update_email_code_last_sent` (11670–11683)

**Docstring в коде:** есть

```
Обновить время последней отправки кода (для rate-limit повторной отправки).
```

## `update_user_password_by_id` (11686–11698)

**Docstring в коде:** есть

```
Обновить (хэшированный) пароль webapp-аккаунта по telegram_id (смена пароля из профиля,
когда пользователь уже авторизован и email известен только по сессии, а не по вводу).
```

## `set_pending_email` (11701–11715)

**Docstring в коде:** есть

```
Сохранить новый email, ожидающий подтверждения кодом (смена почты из профиля).
Текущий auth_email остаётся действующим для входа, пока код не подтверждён.
```

Нормализация; пусто → False. Уникальность не проверяет (это `finalize_pending_email_change`).

## `clear_pending_email` (11718–11732)

**Docstring в коде:** есть

```
Отменить ожидающую смену email (например, пользователь передумал или запросил другой адрес).
```

NULL: pending_email, email_code_hash, email_code_expires_at.

## `finalize_pending_email_change` (11735–11780)

**Docstring в коде:** есть

```
Подтвердить смену email кодом: перенести `pending_email` в `auth_email`.

Атомарно перепроверяет, что новый адрес не был занят другим аккаунтом за время
ожидания кода (защита от гонки, если два пользователя одновременно решили
переключиться на один и тот же email). Возвращает (ok, new_email_или_текст_ошибки).
```

Нет pending → `(False, "Нет ожидающей смены email")`. Чужой `auth_email` — очищает pending/код, `(False, "Этот email уже используется другим аккаунтом")`. Успех: `auth_email=pending`, pending NULL, `email_verified=1`, код сброшен. IntegrityError — тот же текст про занятость.

## `get_webapp_settings` (11783–11806)

**Docstring в коде:** есть

```
Вернуть настройки Telegram Mini App (webapp) из общей таблицы bot_settings.

Ключи:
  webapp_enabled  - "true"/"false", включён ли Mini App
  webapp_domain   - домен, на котором развёрнут Mini App
  webapp_title    - заголовок (fallback на panel_brand_title в handlers.py)
  webapp_logo     - URL логотипа (по умолчанию берётся логотип проекта img/obla.png,
                     отдаваемый через /static или отдельный роут в webapp/handlers.py)
  webapp_icon     - favicon/apple-touch-icon
  tg_fullscreen   - "true"/"false", полноэкранный режим в Telegram
```

`webapp_enabled` / `tg_fullscreen`: `str(value).lower() == "true"`, нет значения → False. Остальные — `value or ""`. get_setting except → None.

---

**Покрытие инвентаря:** 144 имени (`_describe_transaction_action` … `get_webapp_settings`, включая nested `_work` и оба `get_gift_code_by_key_id`).
