# Комментарии: `src/shop_bot/data_manager/remnawave_repository.py`

Фасад над `database.py`: ContextVar франшизы, ключи Remnawave, gift-токены, атомарные промокоды. Модульного docstring нет. Около 200 имён из `database` прокидываются через `_LEGACY_FORWARDERS` (если ещё нет в `globals()`). Предпочтительный импорт хендлеров — `rw_repo`.

`normalize_host_name = database.normalize_host_name`.

| Имя | Значение | Зачем |
|-----|----------|--------|
| `_factory_bot_id_var` | ContextVar default 0 | текущий clone-бот |
| `PROMO_RESERVATION_TTL_HOURS` | 24 | TTL слота до `release_stale_promo_reservations` |
| `PROMO_USER_ERROR` | «Промокод недействителен» | `#` в коде: один текст, чтобы не оракулить код/сегмент/лимит |
| `PROMO_ERROR_MESSAGES` | map причин → тот же текст, кроме `empty_code` | |
| `PROMO_SEGMENT_*` / `PROMO_SEGMENT_TYPES` | no_active_subscription, min_total_spent | |
| `_PROMO_SPENT_EXCLUDED_METHODS` | `("balance", "referral_payout")` | не считаются «потраченными деньгами» |

## `__getattr__` (16–32)

**Docstring в коде:** есть

```
Модуль-level fallback (PEP 562) для `DB_FILE`.

Раньше здесь было `DB_FILE = database.DB_FILE` — обычное присваивание,
которое выполняется РОВНО ОДИН РАЗ, в момент первого импорта этого модуля,
и после этого никогда не обновляется. В проде это не проблема (путь к БД
не меняется за время жизни процесса), но в тестах, где `database.DB_FILE`
подменяется через monkeypatch отдельно для каждого теста, `rw_repo.DB_FILE`
оставался равным пути САМОГО ПЕРВОГО теста, из-за чего разные тесты — если
они (сами или через любую функцию из этого модуля) трогали БД — писали и
читали одну и ту же "чужую" временную базу, что приводило к падениям вида
UNIQUE constraint failed / отсутствующим строкам в зависимости от порядка
запуска тестов. Теперь `rw_repo.DB_FILE` всегда возвращает актуальное
значение `database.DB_FILE` на момент обращения.
```

Иное имя → `AttributeError`.

## `set_current_factory_bot_id` (41–49)

**Docstring в коде:** есть

```
Set current factory bot id for the running handler via contextvars.

Returns a token that can be used to reset the context.
```

`int(bot_id or 0)`; любой except → `set(0)`.

## `reset_current_factory_bot_id` (52–56)

**Docstring в коде:** нет

```
"""Сбросить ContextVar по token; ошибка игнорируется."""
```

## `get_current_factory_bot_id` (59–63)

**Docstring в коде:** нет

```
"""Вернуть int текущего factory bot id или 0 при ошибке/пустом значении."""
```

## `PromoUnavailableError` (66–71)

**Docstring в коде:** есть

```
Промокод нельзя зарезервировать (лимит / недействителен).
```

## `PromoUnavailableError.__init__` (69–71)

**Docstring в коде:** нет

```
"""Сохранить reason (пусто → 'unavailable') и передать его в Exception."""
```

## `create_payload_pending` (74–118)

**Docstring в коде:** есть

```
Create/update pending payload metadata.

We inject `factory_bot_id` into metadata automatically so that:
- successful webhooks can reply from the correct clone bot
- partner commission can be accrued correctly

If metadata contains a promo_code, a usage slot is reserved atomically
before the pending row is written. Raises PromoUnavailableError when the
slot cannot be taken (limit already exhausted).
```

`database.create_payload_pending`; если insert не ок после reserve — `release_promo_reservation`.

## `cancel_pending_transaction` (121–129)

**Docstring в коде:** есть

```
Отменить неоплаченный pending и освободить слот промокода, если он был зарезервирован.
```

Release только если `database.cancel_pending_transaction` вернул True.

## `_connect` (132–135)

**Docstring в коде:** нет

```
"""sqlite3.connect(database.DB_FILE) с row_factory=Row."""
```

## `_normalize_email` (138–139)

**Docstring в коде:** нет

```
"""email.strip().lower(); None → ''."""
```

## `_default_expire_at_ms` (142–143)

**Docstring в коде:** нет

```
"""Текущий utcnow в миллисекундах UNIX."""
```

## `_decrypt_host_secrets` (146–150)

**Docstring в коде:** есть

```
get_squad/list_squads читают xui_hosts напрямую — расшифровать как get_host.
```

None → None. Поля `ssh_password`, `remnawave_api_token`.

## `list_squads` (153–162)

**Docstring в коде:** нет

```
"""SELECT * FROM xui_hosts; при active_only — COALESCE(is_active,1)=1; сортировка sort_order, host_name; секреты расшифровать."""
```

## `get_squad` (165–187)

**Docstring в коде:** нет

```
"""Найти хост по TRIM(host_name) или TRIM(squad_uuid) — как есть и normalize_host_name; пустой identifier → None."""
```

## `get_key_by_id` (190–191)

**Docstring в коде:** нет

```
"""Проброс database.get_key_by_id."""
```

## `get_key_by_email` (194–195)

**Docstring в коде:** нет

```
"""Проброс database.get_key_by_email."""
```

## `get_key_by_remnawave_uuid` (198–199)

**Docstring в коде:** нет

```
"""Проброс database.get_key_by_remnawave_uuid."""
```

## `record_key` (202–262)

**Docstring в коде:** нет

```
"""Записать ключ: есть строка по email или remnawave uuid — update_key_fields, иначе add_new_key; ошибка → None."""
```

`expire_at_ms` None → `_default_expire_at_ms()`. Email нормализуется. host_name через `normalize_host_name`.

## `record_key_from_payload` (265–301)

**Docstring в коде:** нет

```
"""Собрать поля ключа из dict Remnawave/локального payload и вызвать record_key; пустой payload → None."""
```

expire: `expiry_timestamp_ms` или ISO `expireAt`/`expiryDate` (Z→+00:00).

## `update_key` (304–340)

**Docstring в коде:** нет

```
"""Проброс database.update_key_fields со всеми переданными полями ключа, включая boost/reset/remote_access_state."""
```

## `_parse_key_expiry_dt` (343–363)

**Docstring в коде:** есть

```
Parse key expiry from normalized row (expiry_date / expire_at).
```

datetime → naive; строка: fromisoformat / Z / `%Y-%m-%d %H:%M:%S`. По коду: если ничего не разобралось → `datetime.utcnow()`.

## `_sync_key_expiry_ms` (366–400)

**Docstring в коде:** есть

```
Push expiry to Remnawave, then update local DB. Returns (ok, error, final_ms).
```

`asyncio.run(create_or_update_key_on_host)`. Ошибки: `not_found`, `missing_host_or_email`, `remnawave_update_failed`, `db_update_failed`.

## `extend_key` (403–423)

**Docstring в коде:** есть

```
Продлить/сократить срок ключа на N дней (N может быть отрицательным).

Синхронизирует expire с Remnawave, затем обновляет локальную БД.
Returns (ok, error_code_or_None).
```

`days` не int → `invalid_days`; `0` → `zero_days`.

## `set_key_expiry` (426–460)

**Docstring в коде:** есть

```
Установить точную дату истечения ключа; синхронизирует Remnawave + БД.

new_expire_at: datetime или строка 'YYYY-MM-DD HH:MM[:SS]' / ISO.
Returns (ok, error_code_or_None).
```

Пустая/неразобранная строка → `invalid_date`. tzinfo снимается.

## `delete_key_by_email` (463–464)

**Docstring в коде:** нет

```
"""Проброс database.delete_key_by_email."""
```

## `generate_key_email_for_user` (467–489)

**Docstring в коде:** есть

```
Generate a unique key email based on Telegram ID + key number.
```

`user_id` не int / ≤0 → ValueError. Старт с `get_next_key_number` (ошибка → 1). До 1000 кандидатов `{uid}-{n}@{domain}`; все заняты → `{uid}-{utcnow timestamp}@{domain}`.

## `create_gift_token` (759–799)

**Docstring в коде:** нет

```
"""INSERT в gift_tokens; пустой token / days≤0 / activation_limit≤0 → ValueError; IntegrityError → False."""
```

host_name нормализуется. `expires_at` datetime → isoformat.

## `get_gift_token` (802–810)

**Docstring в коде:** нет

```
"""Строка gift_tokens по token или None; пустой token → None."""
```

## `list_gift_tokens` (813–823)

**Docstring в коде:** нет

```
"""Все gift_tokens; active_only — лимит не исчерпан и expires_at NULL или >= now; ORDER BY created_at DESC."""
```

## `delete_gift_token` (826–834)

**Docstring в коде:** нет

```
"""DELETE gift_tokens по token; True если rowcount>0."""
```

## `claim_gift_token` (837–895)

**Docstring в коде:** нет

```
"""Засчитать активацию токена: +1 activations_used, INSERT gift_token_claims; просрочен/лимит/нет строки → None."""
```

Проверка expires_at и `activations_used >= activation_limit` до UPDATE. sqlite3.Error → rollback, None. Повторный claim того же user в коде отдельно не запрещён.

## `create_promo_code` (900–977)

**Docstring в коде:** нет

```
"""INSERT promo_codes: код UPPER; либо percent (0,100], либо amount>0, не оба; даты/лимиты/сегмент/планы валидируются; дубль → False."""
```

`valid_until <= valid_from` → ValueError. IntegrityError → False.

## `get_promo_code` (980–988)

**Docstring в коде:** нет

```
"""Строка promo_codes по UPPER(code) или None."""
```

## `list_promo_codes` (991–999)

**Docstring в коде:** нет

```
"""Все промокоды; include_inactive=False → is_active=1; ORDER BY created_at DESC."""
```

## `promo_error_message` (1032–1035)

**Docstring в коде:** нет

```
"""Текст ошибки: empty_code отдельно, иначе PROMO_ERROR_MESSAGES или PROMO_USER_ERROR."""
```

## `_serialize_applicable_plan_ids` (1038–1071)

**Docstring в коде:** есть

```
Validate and store plan scope as a JSON array of ints, or NULL = all plans.
```

Строка → json.loads. Пустой список / несуществующий plan_id / не int / ≤0 → ValueError. Дубликаты id пропускаются.

## `_normalize_promo_segment` (1074–1092)

**Docstring в коде:** нет

```
"""Пустой type → (None,None); иначе только PROMO_SEGMENT_TYPES; min_total_spent требует value>0."""
```

## `_parse_applicable_plan_ids` (1095–1117)

**Docstring в коде:** есть

```
NULL/empty → unrestricted. Invalid JSON → empty list (fail closed).
```

list/tuple с не-int → `[]`. Не-list JSON → `[]`.

## `_coerce_plan_id` (1120–1126)

**Docstring в коде:** нет

```
"""int(plan_id) или None, если пусто/не число."""
```

## `_user_has_active_subscription` (1129–1140)

**Docstring в коде:** есть

```
True if the user has at least one vpn_keys row with expire_at > now().
```

Сравнение с `datetime.utcnow()` через `_parse_key_expiry_dt`.

## `_user_paid_total` (1143–1186)

**Docstring в коде:** есть

```
Sum of completed purchases for the user.

Completed = transactions.status = 'paid' OR pending_transactions.status = 'paid'
(same definition as /api/check-payment after PR #75). Pending invoices do not
count. Internal balance transfers and referral payouts are excluded — they are
not money the user spent on a plan.
```

Можно передать готовый cursor (та же транзакция промо).

## `_user_paid_total._sum` (1173–1181)

**Docstring в коде:** нет

```
"""SUM paid transactions (без excluded methods) + paid pending без парного paid в transactions."""
```

Ошибка SELECT pending → `pending_paid = 0.0`.

## `_user_matches_promo_segment` (1189–1211)

**Docstring в коде:** есть

```
Whether the user satisfies an optional promo segment restriction.

segment_type is None / empty → always True (unconditional coupon).
```

`no_active_subscription` → not `_user_has_active_subscription`. `min_total_spent` → paid_total ≥ threshold; плохой threshold → False. Иной type → False.

## `_promo_targeting_error` (1214–1238)

**Docstring в коде:** есть

```
plan_not_eligible / segment_not_eligible, or None if targeting passes.

Must run inside the same atomic section as limit reservation (reserve_promo_code)
so a concurrent key/payment cannot sneak a slot after a stale preview check.
```

`plan_ids is not None` и `pid not in plan_ids` (включая pid=None) → `plan_not_eligible`.

## `_PromoTxnAbort` (1241–1244)

**Docstring в коде:** нет

```
"""Исключение отката промо-транзакции: не ошибка SQLite, а отказ с reason."""
```

## `_PromoTxnAbort.__init__` (1242–1244)

**Docstring в коде:** нет

```
"""Сохранить reason и передать его в Exception."""
```

## `_connect_promo_write` (1247–1257)

**Docstring в коде:** есть

```
Write connection with BEGIN IMMEDIATE so promo limit updates serialize.
```

`timeout=30`, `isolation_level=None`, WAL + busy_timeout=30000 (ошибка PRAGMA игнорируется). BEGIN делает вызывающий.

## `_with_promo_write` (1260–1295)

**Docstring в коде:** нет

```
"""До 8 раз: BEGIN IMMEDIATE, work(conn), COMMIT; _PromoTxnAbort → ROLLBACK и (None, reason); locked → backoff 0.02*2^i."""
```

Иной Exception после BEGIN — ROLLBACK и проброс. Исчерпание locked — raise last OperationalError; иначе `(None, "unavailable")`.

## `_promo_validity_error` (1298–1316)

**Docstring в коде:** нет

```
"""inactive / not_started / expired по is_active и valid_from/until; кривые даты пропускаются; иначе None."""
```

`now_dt` default utcnow. Сравнение через `fromisoformat`.

## `_per_user_occupied` (1319–1336)

**Docstring в коде:** нет

```
"""Число usages + reservations status='reserved' для (code, user_id); нет таблицы reservations → reserved=0."""
```

## `_fetch_promo_row` (1339–1352)

**Docstring в коде:** нет

```
"""Нужные колонки promo_codes по code или None."""
```

## `_atomic_increment_used_total` (1355–1369)

**Docstring в коде:** есть

```
Increment used_total only if the total limit still has a free slot.

Returns cursor.rowcount (0 → limit already exhausted / missing row).
```

WHERE: `usage_limit_total IS NULL OR used_total < limit`.

## `_decrement_used_total` (1372–1383)

**Docstring в коде:** нет

```
"""used_total = max(used_total-1, 0) для code."""
```

## `check_promo_code_available` (1386–1442)

**Docstring в коде:** есть

```
Проверить возможность использования промокода, не изменяя лимиты.

Порядок внутри одной транзакции (BEGIN IMMEDIATE):
1. промокод существует, активен, не просрочен;
2. applicable_plan_ids — если задан и plan_id не входит в список → отказ;
3. segment_type — если задан и сегмент не совпал → отказ;
4. только затем проверка usage_limit_total / usage_limit_per_user.

Финальный захват слота — атомарный reserve_promo_code / redeem_promo_code,
который повторяет шаги 1–3 в той же секции, что и UPDATE used_total.
```

Сначала `release_stale_promo_reservations` (ошибка глотается). Пустой код → `(None, "empty_code")`. Если reason `expired` — `update_promo_code_status(..., is_active=False)`.

## `check_promo_code_available._work` (1412–1432)

**Docstring в коде:** нет

```
"""Проверки 1–4; отказ через _PromoTxnAbort; успех → (promo, None)."""
```

## `reserve_promo_code` (1445–1538)

**Docstring в коде:** есть

```
Atomically reserve one promo usage slot for a pending payment.

Uses a single BEGIN IMMEDIATE transaction: targeting (plan/segment) first,
then UPDATE used_total ... WHERE limit not reached, then per-user occupancy
check. rowcount == 0 → total_limit_reached. Idempotent for the same payment_id.
```

Пустой payment_id → `(None, "unavailable")`. Перед работой — stale release.

## `reserve_promo_code._work` (1472–1533)

**Docstring в коде:** нет

```
"""Идемпотентность по payment_id; increment used_total; per-user; INSERT reservations; IntegrityError — сверка status."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1483–1492 | уже reserved/redeemed | вернуть promo, без нового increment |
| 1502–1503 | increment rowcount 0 | total_limit_reached |
| 1505–1509 | per-user ≥ limit | decrement, user_limit_reached |
| 1518–1529 | IntegrityError INSERT | чужой/битый status → decrement + unavailable |

## `release_promo_reservation` (1541–1579)

**Docstring в коде:** есть

```
Free a reserved slot (pending expired/cancelled). Never lets used_total go below 0.
```

Пустой payment_id → False. `_with_promo_write` вернул tuple (abort) → False.

## `release_promo_reservation._work` (1547–1574)

**Docstring в коде:** нет

```
"""Если status=='reserved': UPDATE released и _decrement_used_total; иначе False."""
```

## `release_stale_promo_reservations` (1582–1608)

**Docstring в коде:** есть

```
Release reservations older than TTL so abandoned invoices do not hold the limit forever.
```

`hours <= 0` → 0. SELECT reserved с `reserved_at <= cutoff`, затем по одному `release_promo_reservation`.

## `update_promo_code_status` (1611–1627)

**Docstring в коде:** нет

```
"""UPDATE is_active, если передан; нет полей или пустой code → False; True при rowcount>0."""
```

## `delete_promo_code` (1630–1638)

**Docstring в коде:** нет

```
"""DELETE promo_codes по UPPER(code); True если удалили строку."""
```

## `redeem_promo_code` (1641–1760)

**Docstring в коде:** есть

```
Confirm a reserved slot (or atomically take one) and record the usage.

If a reservation for order_id already exists, used_total is NOT incremented
again. Legacy payments without a reservation take the slot with the same
UPDATE ... WHERE limit check (rowcount == 0 → None).
```

Пустой code → None. Abort-tuple из `_with_promo_write` → None.

## `redeem_promo_code._work` (1656–1755)

**Docstring в коде:** нет

```
"""Redeem: уже есть usage по order_id / reserved / redeemed / legacy increment; INSERT promo_code_usages."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1673–1681 | usage с этим order_id | вернуть promo без increment |
| 1693–1695 | reserved | слот уже в used_total |
| 1696–1702 | redeemed | вернуть promo |
| 1703–1714 | нет reservation | validity + increment + per-user |
| 1724–1733 | UNIQUE usages | идемпотентный возврат |
| 1735–1743 | было reserved | status → redeemed |

## `search_user_keys_by_email` (1764–1766)

**Docstring в коде:** есть

```
Поиск ключей пользователя по key_email.
```

Проброс `database.search_user_keys_by_email` (объявлено после `_LEGACY_FORWARDERS`, перекрывает форвардер).

## `search_all_keys_by_email` (1769–1771)

**Docstring в коде:** есть

```
Поиск всех ключей (администраторам) по key_email.
```

Проброс `database.search_all_keys_by_email`.
