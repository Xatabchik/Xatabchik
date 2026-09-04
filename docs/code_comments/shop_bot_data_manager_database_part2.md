# Комментарии: `src/shop_bot/data_manager/database.py` (часть 2)

Продолжение SQLite-слоя. Модульного docstring нет. Этот файл — инвентарь от `create_broadcast_campaign` до `find_and_complete_ton_transaction` включительно (151 имя, в том числе 12 вложенных `_work`). CRUD тикетов поддержки в этом диапазоне **нет**; из тикетов здесь только сиды кнопок `support_menu` в `initialize_default_button_configs`.

Два независимых контура «ожидающей оплаты»:

| Контур | Таблица | Создание | Атомарное закрытие |
|--------|---------|----------|-------------------|
| вебхуки (YooKassa, Heleket, CryptoBot, Platega, RollyPay, Stars) | `pending_transactions` + зеркало в `transactions` | `create_payload_pending` | `find_and_complete_pending_transaction` (только pending; ledger в paid здесь **не** ставится) |
| TON Connect | только `transactions` | `create_pending_transaction` | `find_and_complete_ton_transaction` (`pending_transactions` не трогает) |

`_connect_pending_db` открывает соединение с `isolation_level=None` (autocommit) — поэтому закрытие pending идёт через `BEGIN IMMEDIATE` внутри `_work`.

| Имя | Значение | Зачем |
|-----|----------|--------|
| `EMAIL_ONLY_TELEGRAM_ID_MIN` / `MAX` | `999000000000` / `999999999999` | `#` в коде: псевдо-telegram_id email-аккаунтов; бот писать не может |
| `SECRET_SETTING_KEYS` | yookassa/cryptobot/heleket/tonapi/remnawave/rollypay секреты | at-rest `enc1$` через `encrypt/decrypt_managed_bot_token` |
| `_PAID_TX_STATUSES` | paid, success, succeeded, completed | терминал «оплачено» для зеркала |
| `_TERMINAL_TX_STATUSES` | paid-набор + cancelled/canceled/failed/expired/chargeback | `_mirror_pending_to_ledger` не перезаписывает |
| `_PROVIDER_TX_KEYS` | platega/cryptobot/heleket/yookassa/rollypay id | TON в списке нет |
| `_KEY_LTE_DEFAULT_STATE` | нули + `premium_state=enabled` | дефолт `get_key_lte_state` |
| `REFERRAL_PAYOUT_METHOD_TYPES` | sbp, card, usdt_trc20 | |
| `REFERRAL_WITHDRAWAL_STATUSES` | new, processing, paid, rejected | |
| `MAX_OPEN_REFERRAL_WITHDRAWAL_REQUESTS` | 1 | |
| `_UNSET` | `object()` (модуль, строка 17) | отличить «не передали» от явного `None` (`lte_reset_at`, поля `update_plan`) |

---

## `create_broadcast_campaign` (4459–4471)

**Docstring в коде:** нет

```
"""INSERT в broadcast_campaigns; вернуть lastrowid или None при sqlite3.Error."""
```

`name`/`text_html` — `.strip()`; `interval_hours` — `int`; `target_segment` пишется как есть (дефолт `"inactive"`). Выборка получателей ниже **не** читает `target_segment`.

## `get_broadcast_campaigns` (4474–4483)

**Docstring в коде:** нет

```
"""Все broadcast_campaigns, ORDER BY created_at DESC; ошибка → []."""
```

## `get_broadcast_campaign` (4486–4496)

**Docstring в коде:** нет

```
"""Одна кампания по id или None."""
```

## `update_broadcast_campaign` (4499–4511)

**Docstring в коде:** нет

```
"""UPDATE name/text_html/interval_hours и updated_at; True если rowcount>0."""
```

`target_segment` и `is_active` не меняет. Keyword-only аргументы.

## `toggle_broadcast_campaign` (4514–4532)

**Docstring в коде:** есть (дословно):

```
Flip is_active. Returns new is_active state.
```

По коду: нет строки / ошибка → `False` (то же значение, что «стало неактивно»). `new_state = 0 if row[0] else 1`.

## `delete_broadcast_campaign` (4535–4545)

**Docstring в коде:** нет

```
"""Удалить sends кампании, затем саму кампанию; True если кампания удалена."""
```

`rowcount` смотрит на второй DELETE (`broadcast_campaigns`).

## `is_email_only_user` (4554–4561)

**Docstring в коде:** есть (дословно):

```
True, если пользователь зарегистрирован по email и ещё не авторизовался
    через Telegram (синтетический telegram_id с префиксом 999).
```

`int(telegram_id)` не удался → `False`. Диапазон включительный: `999000000000 … 999999999999`.

## `get_inactive_subscribers` (4564–4588)

**Docstring в коде:** есть (дословно):

```
User IDs with no active keys (expire_at in the past or no keys at all),
    not banned, not marked unreachable (blocked the bot / deactivated account),
    and not email-only accounts without Telegram auth.
```

WHERE: `is_banned=0`, `is_unreachable` NULL/0, `telegram_id` вне email-only, `NOT EXISTS` ключа с `expire_at > datetime('now')`. Ошибка → `[]`.

## `get_pending_broadcast_recipients` (4591–4611)

**Docstring в коде:** есть (дословно):

```
Inactive users who haven't been sent this campaign in the last `interval_hours`.
```

Всегда `get_inactive_subscribers()` минус `broadcast_sends` этой кампании за окно. Поле `target_segment` кампании **не** читается. Пустой inactive → `[]` без SQL.

## `record_broadcast_sends` (4614–4633)

**Docstring в коде:** есть (дословно):

```
Insert send records and bump campaign send_count. Returns count inserted.
```

Пустой `user_ids` → 0. Возвращает `len(user_ids)`, не `cursor.rowcount`. Заодно `last_run_at` и `updated_at`. Ошибка → 0.

## `mark_broadcast_run` (4636–4647)

**Docstring в коде:** есть (дословно):

```
Update last_run_at even when there are no recipients (avoids tight retry loops).
```

`send_count` не трогает. Нет return.

## `get_broadcast_stats` (4650–4659)

**Docstring в коде:** нет

```
"""COUNT/MAX(sent_at) по broadcast_sends; ошибка → total_sends=0, last_sent_at=None."""
```

## `get_all_keys` (4662–4671)

**Docstring в коде:** нет

```
"""Все строки vpn_keys без WHERE/ORDER; каждая через `_normalize_key_row`; ошибка → []."""
```

Нормализация (часть 1): email/`key_email`, uuid/`xui_client_uuid`, `expire_at`/`expiry_date`, `created_at`/`created_date`, `subscription_url`/`connection_string`.

## `get_all_key_ids` (4674–4683)

**Docstring в коде:** есть (дословно):

```
Все key_id из vpn_keys (без фильтров/пагинации) — для bulk-действий «всем».
```

`ORDER BY key_id ASC`. Ошибка → `[]`.

## `extend_key` (4686–4693)

**Docstring в коде:** есть (дословно):

```
Продлить/сократить срок ключа на N дней (с синхронизацией Remnawave).

    Реализация делегируется в remnawave_repository (lazy import — избегаем цикла).
```

Локального SQL нет. `days` может быть отрицательным — решает `_rw.extend_key`.

## `set_key_expiry` (4696–4700)

**Docstring в коде:** есть (дословно):

```
Установить точную дату истечения ключа (с синхронизацией Remnawave).
```

Тоже lazy-import `remnawave_repository.set_key_expiry`. Тип `new_expire_at` здесь не проверяется.

## `get_keys_paginated` (4703–4760)

**Docstring в коде:** нет

```
"""Страница vpn_keys + total: фильтр user_id и LIKE-поиск, whitelist-сортировка."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4705–4712 | page/per_page | не-int → 1 / 25; оба `max(1, …)` |
| 4716–4726 | WHERE | `user_id=`; search по key_id/user_id/key_email/email/user_key_name |
| 4728–4738 | ORDER | whitelist `user_id`/`host_name`/`created_at`/`expire_at`; иначе created_at; dir только `asc`, иначе DESC; вторично created_at DESC |
| 4744–4757 | SELECT | COUNT затем LIMIT/OFFSET; ряды через `_normalize_key_row` |

Ошибка → `([], 0)`.

## `get_keys_for_user` (4763–4764)

**Docstring в коде:** нет

```
"""Алиас `get_user_keys(user_id)` (vpn_keys пользователя, created_at DESC)."""
```

Тело — одна строка. Сама `get_user_keys` в части 3 (~8571).

## `update_key_email` (4766–4768)

**Docstring в коде:** нет

```
"""Нормализовать email и записать через `update_key_fields` (email + key_email)."""
```

`_normalize_email(new_email) or new_email.strip()`. Не синкает панель.

## `update_key_host` (4770–4771)

**Docstring в коде:** нет

```
"""Сменить host_name ключа через `update_key_fields` (normalize_host_name внутри)."""
```

Не синкает панель и не трогает squad/uuid.

## `create_gift_key` (4773–4794)

**Docstring в коде:** есть (дословно):

```
Создать подарочный ключ: expiry = now + months.
```

По коду: `months_value = max(1, int(months or 1))`, expiry = `utcnow + timedelta(days=30 * months_value)` — **не** календарные месяцы (`add_calendar_months`). UUID: аргумент или `GIFT-{user_id}-{unix_ts}`. Делегирует `add_new_key` (часть 3). sqlite3 и любой Exception → None.

## `get_setting` (4809–4821)

**Docstring в коде:** нет

```
"""value из bot_settings по key; секреты из SECRET_SETTING_KEYS расшифровать; нет/ошибка → None."""
```

Не-секрет возвращается как лежит в БД (без decrypt).

## `get_admin_ids` (4823–4860)

**Docstring в коде:** есть (дословно):

```
Возвращает множество ID администраторов из настроек.
    Поддерживает оба варианта: одиночный 'admin_telegram_id' и список 'admin_telegram_ids'
    через запятую/пробелы или JSON-массив.
```

Сначала `int(admin_telegram_id)`. Затем `admin_telegram_ids`: удачный `json.loads` списка — добрать int и **сразу return** (CSV-ветка не бежит). Иначе split по пробелам/запятым. Битые куски глотаются. Внешний except → warning, уже накопленный set.

## `is_admin` (4862–4867)

**Docstring в коде:** есть (дословно):

```
Проверка прав администратора по списку ID из настроек.
```

`int(user_id) in get_admin_ids()`; любой except → `False`.

## `_connect_pending_db` (4869–4880)

**Docstring в коде:** есть (дословно):

```
Connection helper for high-contention tables (webhooks/bot).
```

`timeout=5.0`, `isolation_level=None`, `Row` factory. PRAGMA WAL / synchronous=NORMAL / busy_timeout=5000; сбой pragma глотается. Соединение **не** закрывается здесь.

## `_retry_sqlite` (4883–4891)

**Docstring в коде:** нет

```
"""Вызвать work() до `attempts` раз; при OperationalError с «locked» — sleep `base_sleep*2**i` и повтор; иначе проброс."""
```

Дефолт 5 попыток, `base_sleep=0.05`. Последняя locked не ретраится — `raise`.

## `_ensure_pending_tables` (4894–4907)

**Docstring в коде:** нет

```
"""CREATE TABLE IF NOT EXISTS pending_transactions (payment_id PK, user_id, amount_rub, metadata, status default pending, timestamps)."""
```

`processed_payments` не создаёт.

## `_ensure_processed_payments_table` (4910–4918)

**Docstring в коде:** нет

```
"""CREATE TABLE IF NOT EXISTS processed_payments (payment_id PK, processed_at)."""
```

## `_tx_meta_dict` (4934–4941)

**Docstring в коде:** нет

```
"""dict как есть (копия); иначе json.loads; не-dict/ошибка → {}."""
```

## `_provider_transaction_id_from_meta` (4944–4951)

**Docstring в коде:** нет

```
"""Первое непустое из _PROVIDER_TX_KEYS; не-dict → None. TON-ключей нет."""
```

## `_mirror_pending_to_ledger` (4954–5014)

**Docstring в коде:** есть (дословно):

```
Дублирует неоплаченный счёт в ``transactions``, чтобы он был виден в истории.

    Уже оплаченную строку не перезаписывает.
```

Пустой `payment_id.strip()` → return. Сумма: `float(amount_rub)` иначе `meta.price` иначе 0. Username из `users`. Есть строка и `status.lower()` в `_TERMINAL_TX_STATUSES` (включая **chargeback**) → return. UPDATE существующих с SQL `NOT IN` без `chargeback` (до него не доходят из-за раннего return). INSERT, если строки нет. **Не** пишет `pending_transactions`.

## `create_payload_pending` (5017–5064)

**Docstring в коде:** есть (дословно):

```
Create/update pending payload metadata.

    Important: does NOT revive already paid rows (keeps status='paid' intact).
    Зеркалит неоплаченный счёт в ``transactions`` (status=pending) вместе с id провайдера.
```

Пустой pid → False. Успех `_retry_sqlite` → True даже если строка уже paid/cancelled и ON CONFLICT ничего не обновил. По коду **cancelled тоже не оживляет** (UPDATE только `WHERE status='pending'`). Зеркало — только если после операции status==`pending`.

## `create_payload_pending._work` (5027–5058)

**Docstring в коде:** нет

```
"""INSERT pending или UPDATE полей при status=pending; зеркало ledger только для pending."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5032–5049 | INSERT ON CONFLICT DO UPDATE | user_id/amount/metadata/updated_at; WHERE pending |
| 5050–5057 | SELECT status | pending → `_mirror_pending_to_ledger(..., status="pending")` |
| 5058 | return True | всегда, если SQL не упал |

## `patch_pending_metadata` (5067–5103)

**Docstring в коде:** есть (дословно):

```
Дописывает поля (id провайдера) в pending и в зеркало ``transactions``.
```

Пустой pid или пустой `extra` → False. Только строка `status='pending'`. В meta пишутся ключи с value не `None` и не `""`.

## `patch_pending_metadata._work` (5073–5097)

**Docstring в коде:** нет

```
"""SELECT pending; слить extra в JSON; UPDATE metadata; зеркало ledger."""
```

Нет строки → False.

## `_get_pending_metadata` (5106–5134)

**Docstring в коде:** нет

```
"""JSON metadata только если status='pending'; setdefault payment_id; нет/ошибка → None."""
```

Пустой pid → None без БД.

## `_get_pending_metadata._work` (5111–5128)

**Docstring в коде:** нет

```
"""SELECT metadata WHERE pending; битый JSON → {}; добавить payment_id."""
```

## `get_pending_metadata` (5137–5139)

**Docstring в коде:** есть (дословно):

```
Public wrapper to fetch pending metadata by payment_id WITHOUT marking it paid.
```

Одна строка: `return _get_pending_metadata(payment_id)`. Paid/cancelled → None (фильтр pending внутри).

## `get_pending_record` (5142–5179)

**Docstring в коде:** есть (дословно):

```
Строка pending_transactions с любым статусом (pending/cancelled/paid).
```

Пустой pid → None. Возврат: payment_id, user_id, amount_rub, metadata (dict + payment_id), status.strip().

## `get_pending_record._work` (5148–5173)

**Docstring в коде:** нет

```
"""SELECT без фильтра статуса; не-dict JSON → {}; собрать dict записи."""
```

## `revive_cancelled_invoice` (5182–5218)

**Docstring в коде:** есть (дословно):

```
Вернуть отменённый счёт в pending, если позже пришла реальная оплата.
```

Пустой pid → False. True только если pending-строка перешла из cancelled/canceled (rowcount==1). Тогда то же для `transactions`. Paid не трогает.

## `revive_cancelled_invoice._work` (5188–5212)

**Docstring в коде:** нет

```
"""UPDATE pending cancelled→pending; при успехе то же в transactions."""
```

## `prepare_pending_for_fulfillment` (5221–5231)

**Docstring в коде:** есть (дословно):

```
Metadata для выдачи: отменённый счёт поднимаем, paid не трогаем.
```

Нет записи → None. `paid` → None (выдачу не повторять). cancelled/canceled → `revive_cancelled_invoice`, затем `_get_pending_metadata` (после revive должен быть pending). Иной статус (в т.ч. уже pending) — сразу metadata.

## `get_pending_status` (5234–5254)

**Docstring в коде:** есть (дословно):

```
Return status of pending transaction: 'pending', 'paid', or None if not found.
```

По коду: любой `status.strip()` или None — в том числе `cancelled`. Пустой pid / ошибка → None. Docstring не перечисляет cancelled.

## `get_pending_status._work` (5240–5248)

**Docstring в коде:** нет

```
"""SELECT status; пустая строка → None."""
```

## `_complete_pending` (5257–5276)

**Docstring в коде:** нет

```
"""UPDATE pending→paid только при status=pending; True если ровно одна строка. Ledger не трогает."""
```

Без `BEGIN IMMEDIATE` (в отличие от `find_and_complete_pending_transaction`). Пустой pid → False.

## `_complete_pending._work` (5262–5270)

**Docstring в коде:** нет

```
"""Один UPDATE pending_transactions; вернуть rowcount==1."""
```

## `find_and_complete_pending_transaction` (5279–5331)

**Docstring в коде:** есть (дословно):

```
Atomically mark pending transaction as paid and return its metadata.

    Returns None when payment_id is unknown OR already processed.
```

Пустой pid → None. **`transactions` в paid не переводит.** Повторный вызов (уже paid) → None. Это путь вебхуков, не TON.

## `find_and_complete_pending_transaction._work` (5288–5325)

**Docstring в коде:** нет

```
"""BEGIN IMMEDIATE: SELECT pending → UPDATE paid; commit; вернуть meta с payment_id."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5293–5304 | SELECT pending | нет строки → rollback, None |
| 5306–5315 | UPDATE paid WHERE pending | rowcount≠1 → rollback, None |
| 5317–5325 | commit + parse JSON | битый JSON → {}; setdefault payment_id |

## `get_latest_pending_for_user` (5334–5363)

**Docstring в коде:** есть (дословно):

```
Return metadata of the most recent PENDING transaction for the user (without completing it).
```

`ORDER BY updated_at DESC, created_at DESC LIMIT 1`. **Без** `_retry_sqlite`. Ошибка → None.

## `claim_processed_payment` (5366–5386)

**Docstring в коде:** есть (дословно):

```
Idempotency guard: returns True only once per payment_id.
```

`INSERT OR IGNORE`; True ⇔ `rowcount==1`. Пустой pid → False. Тем же механизмом пользуется `refund_payment_once` с ключом `refund:{id}`.

## `claim_processed_payment._work` (5372–5380)

**Docstring в коде:** нет

```
"""INSERT OR IGNORE processed_payments; True если вставили."""
```

## `unclaim_processed_payment` (5389–5406)

**Docstring в коде:** есть (дословно):

```
Remove idempotency record so a failed payment can be retried.
```

True если DELETE затронул строку.

## `unclaim_processed_payment._work` (5395–5400)

**Docstring в коде:** нет

```
"""DELETE processed_payments по payment_id; rowcount>0."""
```

## `refund_payment_once` (5409–5471)

**Docstring в коде:** есть (дословно):

```
Вернуть средства за невыданную услугу не более одного раза на payment_id.

    Идемпотентность через ``processed_payments`` с ключом ``refund:{payment_id}`` —
    повторный вызов (retry сети / двойной except) не зачислит сумму дважды.
    Balance → add_to_balance; ReferralBalance → add_to_referral_balance;
    прочие методы (внешние платежи) → add_to_balance (как раньше при сбое выдачи ключа).
```

Пустой pid / не-float / `amount<=0` → False **без** claim. `payment_method.strip().lower()=="referralbalance"` → рефбаланс; иначе (в т.ч. `"balance"`, пусто, yookassa…) → `add_to_balance`. Кредит упал / вернул False: `# позволить повторную попытку отката` — `unclaim_processed_payment`. Успех кредита → True.

## `cancel_pending_transaction` (5474–5539)

**Docstring в коде:** есть (дословно):

```
Пометить неоплаченный pending как cancelled, чтобы Stars/вебхук его не закрыли.

    Меняет только ``status='pending'``. Уже paid не трогает. Если передан user_id —
    только строка этого владельца.
```

Пустой pid → False. True, если отменили pending **или** ledger **или** pending уже был `cancelled`.

## `cancel_pending_transaction._work` (5484–5533)

**Docstring в коде:** нет

```
"""Paid/чужой user_id → False; pending→cancelled; ledger pending→cancelled (опц. по user_id)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5488–5497 | SELECT + проверки | чужой user_id / paid → False |
| 5499–5509 | pending | UPDATE cancelled |
| 5511–5532 | ledger | WHERE pending; с user_id или без |
| 5533 | return | pending_cancelled or ledger_cancelled or already cancelled |

## `reset_pending_transaction` (5542–5562)

**Docstring в коде:** есть (дословно):

```
Reset a completed pending transaction back to 'pending' to allow webhook retry.
```

По коду: **нет фильтра статуса** — любая строка с этим payment_id станет pending (и paid, и cancelled). `transactions` не меняет. True если rowcount>0.

## `reset_pending_transaction._work` (5548–5556)

**Docstring в коде:** нет

```
"""UPDATE pending_transactions.status='pending' без WHERE по старому статусу."""
```

## `get_referrals_for_user` (5565–5586)

**Docstring в коде:** есть (дословно):

```
Возвращает список пользователей, которых пригласил данный user_id.
    Поля: telegram_id, username, registration_date, total_spent.
```

`WHERE referred_by = ?`, `ORDER BY registration_date DESC`. Ошибка → `[]`.

## `get_referral_top_rich` (5589–5618)

**Docstring в коде:** есть (дословно):

```
    Возвращает топ пользователей по количеству рефералов,
    которые пополнили баланс хотя бы один раз (total_spent > 0).
    Поля: telegram_id, rich_referrals.
```

Группировка по `referred_by` (это и есть telegram_id реферера). `referred_by` не NULL и не 0. `LIMIT ?` (дефолт 5). `ORDER BY rich_referrals DESC, referred_by ASC`.

## `get_referral_rank_and_count` (5621–5672)

**Docstring в коде:** есть (дословно):

```
    Возвращает кортеж (rank, count), где:
      - rank — место пользователя в рейтинге по количеству
        рефералов с пополнением баланса (total_spent > 0),
        либо None, если пользователь не попадает в рейтинг;
      - count — количество таких рефералов у пользователя.
```

Полный рейтинг в память, линейный поиск. Нет в топе → rank=None, отдельный COUNT своих rich-рефералов. Ошибка → `(None, 0)`. Сравнение `telegram_id == user_id` без `int()` — типы должны совпасть.

## `get_all_settings` (5674–5689)

**Docstring в коде:** нет

```
"""Все bot_settings → dict; SECRET_SETTING_KEYS расшифровать. Ошибка → частично/пусто."""
```

При ошибке возвращает уже накопленный `settings` (не обязательно `{}`).

## `update_setting` (5691–5702)

**Docstring в коде:** нет

```
"""INSERT OR REPLACE bot_settings; секреты шифруются. Нет return."""
```

`value is None` для секрета → шифруется `""`.

## `get_button_configs` (5705–5725)

**Docstring в коде:** есть (дословно):

```
Get *active* button configurations for a specific menu type.

    Note: this function is used by the bot to build keyboards at runtime, so it
    intentionally filters by `is_active = 1`.
```

`ORDER BY sort_order, row_position, column_position`. Ошибка → `[]`.

## `get_button_configs_admin` (5728–5759)

**Docstring в коде:** есть (дословно):

```
Get button configurations for admin/editor UIs.

    Unlike `get_button_configs`, this can return inactive buttons too, so that
    admins can re-enable them.
```

`include_inactive=True` (дефолт) — без фильтра is_active; иначе `is_active=1`.

## `get_button_config_by_db_id` (5762–5773)

**Docstring в коде:** есть (дословно):

```
Get a button configuration by its numeric DB id.
```

PK `id`, не `button_id`.

## `get_button_config` (5775–5791)

**Docstring в коде:** есть (дословно):

```
Get a specific button configuration by menu_type and button_id
```

## `create_button_config` (5793–5836)

**Docstring в коде:** есть (дословно):

```
Create a new button configuration
```

`INSERT OR REPLACE` по уникальности (menu_type, button_id). `is_active` → 0/1. True при успехе commit.

## `update_button_config` (5838–5899)

**Docstring в коде:** есть (дословно):

```
Update an existing button configuration
```

Патч только переданных не-None полей. Пустой updates → True без SQL. `WHERE id = ?` (числовой PK). rowcount==0 → False. `is_active` пишется как 1/0.

## `delete_button_config` (5901–5912)

**Docstring в коде:** есть (дословно):

```
Delete a button configuration
```

По коду: после успешного DELETE **всегда True**, даже если строки не было (`rowcount` не проверяется).

## `update_existing_my_keys_button` (5914–5946)

**Docstring в коде:** есть (дословно):

```
Update existing my_keys button to include key count template and set proper button widths
```

`main_menu/my_keys` → текст `🔑 Мои ключи ({len(user_keys)})`. Ширина 2 у trial/referral/admin. Нет return.

## `ensure_main_menu_gift_button` (5949–5983)

**Docstring в коде:** есть (дословно):

```
Ensure that the main menu has the gift button in button configs.
```

Уже есть `gift_new_key` → return. Иначе INSERT в конец (max sort/row + 1), width=2, callback `gift_new_key`. Не перезаписывает существующую.

## `ensure_main_menu_referral_button` (5986–6036)

**Docstring в коде:** есть (дословно):

```
Ensure that the main menu has the referral program button in button configs,
    and that it's removed from the profile menu (moved from "Мой профиль" в главное меню).
```

В коде `#`: убрать из «Мой профиль». DELETE `profile_menu/referral`. Если `main_menu/referral` есть и `is_active!=1` — включить; иначе INSERT (callback `show_referral_program`, width=2).

## `ensure_admin_plans_button` (6039–6109)

**Docstring в коде:** есть (дословно):

```
Ensure that the Admin menu has a button for managing тарифы (plans).

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty.
```

Уже есть `admin_menu/plans` → return. Иначе рядом с `back_to_menu` (соседняя колонка) или новая строка, если ячейка занята. callback `admin_plans`.

## `ensure_admin_trial_button` (6114–6153)

**Docstring в коде:** есть (дословно):

```
Ensure that the Admin menu has a button for managing Trial settings.

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty.
```

`admin_menu/trial_settings`, callback `admin_trial`, в конец меню.

## `ensure_admin_auto_renew_button` (6156–6199)

**Docstring в коде:** есть (дословно):

```
Ensure that the Admin settings submenu has a button for Автопродление (auto-renew).

    We keep this separate from initialize_default_button_configs(), because that initializer
    runs only when button_configs is empty. Existing databases created before this button
    was introduced (button_configs already populated for admin_settings_menu) never get it
    backfilled by "CREATE TABLE IF NOT EXISTS", so we do it here on every startup instead.
    This only inserts the row if it is truly absent, so it never overwrites an admin's
    existing customization of this button.
```

`admin_settings_menu/auto_renew`, callback `admin_auto_renew`.

## `reorder_button_configs` (6202–6248)

**Docstring в коде:** есть (дословно):

```
Reorder button configurations for a menu type
```

Для каждого элемента: sort/row/col и опционально `button_width`. Нет кнопки — warning, цикл идёт дальше. Успех транзакции → True даже если часть не найдена.

## `initialize_default_button_configs` (6250–6385)

**Docstring в коде:** есть (дословно):

```
Initialize default button configurations for all menu types
```

`COUNT(*)>0` → True, **ничего не дописывает** (backfill — `ensure_*`). Иначе INSERT: `main_menu`, `admin_menu`, `profile_menu` (там ещё есть referral — его потом вычищает `ensure_main_menu_referral_button`), `support_menu`, `admin_system_menu`, `admin_settings_menu`.

Тикеты (только сиды кнопок, не таблица тикетов):

| button_id | callback | Текст |
|-----------|----------|--------|
| `new_ticket` | `support_new_ticket` | ✍️ Новое обращение |
| `my_tickets` | `support_my_tickets` | 📨 Мои обращения |
| `external` | `support_external` | 🆘 Внешняя поддержка |

`howto` и `admin` в main_menu оба с `sort_order=10` (как в коде). Ошибка → False.

## `create_plan` (6387–6408)

**Docstring в коде:** нет. В коде `#`: None-лимит → 0; `MONTH_ROLLING` только при лимите > 0.

```
"""INSERT plans: host нормализуется; traffic_limit_bytes None/<0 → 0; стратегия MONTH_ROLLING или NULL. Нет return."""
```

`lte_limit_bytes or 0`, `main_reset_price_rub or 0`. lastrowid не возвращает.

## `get_plans_for_host` (6411–6422)

**Docstring в коде:** нет

```
"""Все тарифы хоста (включая неактивные), ORDER BY sort_order, COALESCE(duration_days, months*30, months, 0)."""
```

`TRIM(host_name)` с обеих сторон. Ошибка → `[]`.

## `get_active_plans_for_host` (6426–6441)

**Docstring в коде:** есть (дословно):

```
Возвращает только активные тарифы (is_active = 1) для указанного хоста.
```

`COALESCE(is_active, 1) = 1` — NULL считается активным.

## `set_plan_active` (6444–6457)

**Docstring в коде:** есть (дословно):

```
Включить/выключить тариф (скрыть/показать пользователям).
```

Пишет 1/0. True если rowcount>0.

## `get_plan_by_id` (6459–6469)

**Docstring в коде:** нет

```
"""Один plan по plan_id или None."""
```

## `get_all_plans` (6472–6488)

**Docstring в коде:** есть (дословно):

```
Все тарифы (для админки промокодов и валидации applicable_plan_ids).
```

Все хосты, без фильтра is_active. ORDER: TRIM(host_name), sort_order, длительность, plan_id.

## `_parse_json_metadata` (6491–6497)

**Docstring в коде:** нет

```
"""json.loads или {} при пустом/ошибке. Не проверяет, что результат dict."""
```

По коду: удачный parse не-dict (list) вернётся как list.

## `update_plan_metadata` (6499–6515)

**Docstring в коде:** есть (дословно):

```
Update plan.metadata JSON blob.

    `metadata=None` or empty dict will clear the field.
```

Пустой dict / None → SQL NULL. True если rowcount>0.

## `create_traffic_package` (6518–6546)

**Docstring в коде:** есть (дословно):

```
Пакет докупки ГБ для тарифа. `pool`: 'main' (основной трафик) или 'lte' (premium-ноды).

    TODO (известное ограничение, причина F диагностики): пакеты привязаны к `plan_id`, а
    LTE-пул расходуется на пользователя (`subscription_lte`). Поэтому при нескольких
    активных тарифах на одном хосте пакеты одного тарифа недоступны владельцам ключей
    другого — пакеты нужно заводить для каждого тарифа. Перевод привязки на
    host_name/squad_uuid потребует миграции существующих строк с неоднозначным выбором
    целевого хоста (у тарифа он один, но пакеты могли создаваться до его смены), поэтому
    сознательно вынесен за рамки этого фикса.
```

`pool` нормализуется: только `'lte'` (casefold) иначе `'main'`. sort_order = max+1 в том же (plan, pool). lastrowid или None.

## `get_traffic_packages_for_plan` (6549–6563)

**Docstring в коде:** нет

```
"""Пакеты плана и pool (main|lte); only_active → COALESCE(is_active,1)=1; ORDER sort_order, size_gb."""
```

## `get_traffic_package_by_id` (6566–6576)

**Docstring в коде:** нет

```
"""Один traffic_packages по package_id или None."""
```

## `update_traffic_package` (6579–6599)

**Docstring в коде:** нет

```
"""Патч size_gb/price/is_active; нет полей → False; True если rowcount>0."""
```

`pool` не меняет.

## `delete_traffic_package` (6602–6611)

**Docstring в коде:** нет

```
"""DELETE traffic_packages по package_id; True если удалили."""
```

## `set_key_traffic_boost` (6614–6626)

**Docstring в коде:** нет

```
"""Записать vpn_keys.traffic_boost_bytes абсолютным значением (не инкремент)."""
```

True если rowcount>0. Панель не синкает.

## `get_plan_lte_limit` (6629–6638)

**Docstring в коде:** нет

```
"""plans.lte_limit_bytes или 0 (нет строки / NULL / 0 / ошибка)."""
```

`int(row[0]) if row and row[0] else 0`.

## `get_lte_state` (6641–6690)

**Docstring в коде:** есть (дословно):

```
УСТАРЕЛО: пользовательская модель LTE-пула.

    Состояние LTE перенесено на ключ (`key_lte_state`, см. `get_key_lte_state`), потому что
    лимит задаётся тарифом конкретного ключа, а расход считается по нодам его хоста.
    Функции этой группы оставлены только ради читаемости данных, уже перенесённых
    миграцией `_migrate_subscription_lte_to_keys`, и в рантайме не используются.
```

Нет строки → INSERT в `subscription_lte` с baseline initialized = now, premium enabled. Ошибка → нулевой dict (initialized_at=None). В коде `#` про нулевой baseline у новой строки.

## `get_key_lte_state` (6705–6729)

**Docstring в коде:** есть (дословно):

```
Состояние LTE-пула конкретного ключа (создаёт строку при отсутствии).

    `lte_baseline_initialized_at` намеренно НЕ проставляется при вставке: точку отсчёта
    выставляет первый проход воркера по фактическому расходу. Для нового ключа расход
    близок к нулю, а для ключа, у которого LTE-сквад появился позже, это защищает от
    мгновенного исчерпания лимита накопленной историей нод.
```

INSERT `(key_id, premium_state, updated_at)`; дефолты из `_KEY_LTE_DEFAULT_STATE`. Ошибка → тот же дефолт.

## `update_key_lte_state` (6732–6774)

**Docstring в коде:** нет

```
"""Патч полей key_lte_state; сначала get_key_lte_state (ensure row); пустой патч → True."""
```

`lte_reset_at` пишется только если не `_UNSET` (можно записать None). Иначе поля не трогаются.

## `add_key_lte_boost_bytes` (6777–6806)

**Docstring в коде:** есть (дословно):

```
Атомарно увеличить докупленный LTE-буст КЛЮЧА. Возвращает новое значение.
```

`add<=0` / не-int → None. `BEGIN IMMEDIATE`, `lte_boost_bytes += add`, `premium_state='enabled'`. rowcount≤0 → rollback, None. Иначе SELECT нового значения.

## `commit_key_lte_baseline` (6809–6837)

**Docstring в коде:** есть (дословно):

```
Зафиксировать точку отсчёта LTE-расхода ключа одной транзакцией.
```

baseline = `max(0, int(...))`; сброс флага reset; `lte_baseline_initialized_at=now`. `expire_boost=True` → `lte_boost_bytes=0`.

## `request_key_lte_baseline_reset` (6840–6854)

**Docstring в коде:** есть (дословно):

```
Пометить начало нового расчётного периода LTE у ключа (буст сгорит вместе с baseline).
```

Только флаг `lte_baseline_reset_requested=1`. Буст здесь не обнуляет.

## `resolve_lte_limit_bytes` (6857–6876)

**Docstring в коде:** есть (дословно):

```
Единая формула эффективного LTE-лимита: лимит тарифа + докупленный буст.

    Источник истины по базовому лимиту — `plans.lte_limit_bytes`; значение в
    `subscription_lte.lte_limit_bytes` используется только как fallback (тариф ключа
    не определился). Функция обязана быть единственной формулой и для отображения
    в боте, и для энфорсинга в планировщике — раньше они расходились: UI показывал
    лимит вместе с бустом, а воркер сравнивал расход только с лимитом тарифа.
```

`plan_lte_limit_bytes<=0` → fallback `lte_state.lte_limit_bytes`. Затем `+ max(0, boost)`. Без БД.

## `add_lte_boost_bytes` (6879–6914)

**Docstring в коде:** есть (дословно):

```
Атомарно увеличить докупленный LTE-буст пользователя на `add_bytes`.

    Read-modify-write через `get_lte_state()` + `update_lte_state()` терял одну из
    покупок при двух параллельных оплатах (lost update), поэтому инкремент выполняется
    одним UPDATE внутри BEGIN IMMEDIATE. Возвращает новое значение `lte_boost_bytes`
    или None, если обновить не удалось.
```

УСТАРЕЛО вместе с `get_lte_state`: пишет `subscription_lte`, не `key_lte_state`.

## `commit_lte_baseline` (6917–6953)

**Docstring в коде:** есть (дословно):

```
Зафиксировать точку отсчёта (baseline) LTE-расхода одной транзакцией.

    `expire_boost=True` — начало нового расчётного периода: докупленный буст сгорает
    вместе со сбросом счётчика, симметрично основному пулу (там при ежемесячном сбросе
    обнуляется `vpn_keys.traffic_boost_bytes`).
    `expire_boost=False` — первичная инициализация baseline у существующей подписки:
    счётчик расхода начинаем с текущего накопительного значения панели, но уже
    оплаченный буст сохраняем.
```

Пользовательская таблица `subscription_lte`.

## `request_lte_baseline_reset` (6956–6979)

**Docstring в коде:** есть (дословно):

```
Помечает начало нового расчётного периода LTE-пула.

    Воркер `enforce_dual_traffic_limits` на следующем проходе зафиксирует текущее сырое
    (накопительное) значение расхода по LTE-нодам как новую точку отсчёта и обнулит
    докупленный буст (см. `commit_lte_baseline(expire_boost=True)`).

    ВАЖНО: этот флаг больше не выставляется при докупке LTE-пакета — покупка обязана быть
    строго аддитивной (+N ГБ к остатку), а не сбросом счётчика расхода. Иначе покупка
    минимального пакета заново выдавала полный лимит тарифа.
```

УСТАРЕЛО (user-level).

## `update_lte_state` (6982–7022)

**Docstring в коде:** нет

```
"""Патч subscription_lte (устарело); зеркало update_key_lte_state; пустой патч → True."""
```

## `delete_plan` (7025–7034)

**Docstring в коде:** нет

```
"""DELETE traffic_packages плана, затем plans. Нет return / проверки rowcount."""
```

Ключи с этим plan_id не трогает.

## `update_plan` (7036–7072)

**Docstring в коде:** нет

```
"""UPDATE name/months/price и опционально duration/traffic/hwid/lte/reset; _UNSET = не трогать."""
```

При смене `traffic_limit_bytes`: стратегия `MONTH_ROLLING` если int>0, иначе NULL (битый int → NULL). rowcount==0 → False + warning.

## `register_user_if_not_exists` (7075–7098)

**Docstring в коде:** есть (дословно):

```
Зарегистрировать пользователя, если его ещё нет.

    ``referred_by`` выставляется только на INSERT. Уже существующая строка
    обновляет username и никогда не late-bind'ит реферера — иначе любой
    ``/start ref_<id>`` мог привязать аккаунт, у которого поле ещё пустое.
```

Нет строки → INSERT с `datetime.now()` и `referrer_id`. Есть → только `username`.

## `add_to_referral_balance` (7100–7109)

**Docstring в коде:** нет

```
"""referral_balance += amount без COALESCE; True если rowcount>0."""
```

NULL+amount в SQLite → NULL.

## `set_referral_balance` (7111–7118)

**Docstring в коде:** нет

```
"""Абсолютная запись referral_balance. Нет return."""
```

## `set_referral_balance_all` (7120–7127)

**Docstring в коде:** нет

```
"""Абсолютная запись referral_balance_all (накопленный доход). Нет return."""
```

## `add_to_referral_balance_all` (7129–7139)

**Docstring в коде:** нет

```
"""referral_balance_all += amount. Нет return."""
```

## `get_referral_balance_all` (7141–7150)

**Docstring в коде:** нет

```
"""referral_balance_all или 0.0 (нет пользователя / ошибка)."""
```

## `get_referral_balance` (7152–7161)

**Docstring в коде:** нет

```
"""referral_balance или 0.0."""
```

## `get_balance` (7163–7172)

**Docstring в коде:** нет

```
"""users.balance или 0.0."""
```

## `adjust_user_balance` (7174–7184)

**Docstring в коде:** есть (дословно):

```
Скорректировать баланс пользователя на указанную дельту (может быть отрицательной).
```

`COALESCE(balance,0)+delta`. **Без** проверки «не уйти в минус». True если строка затронута.

## `adjust_user_referral_balance` (7186–7196)

**Docstring в коде:** есть (дословно):

```
Скорректировать реферальный баланс пользователя на указанную дельту (может быть отрицательной).
```

Как выше, поле `referral_balance`. Без нижнего порога.

## `set_balance` (7198–7207)

**Docstring в коде:** нет

```
"""Абсолютная запись balance; True если rowcount>0."""
```

## `add_to_balance` (7209–7236)

**Docstring в коде:** нет

```
"""Найти пользователя, затем COALESCE(balance,0)+amount; False если нет user / 0 rows / sqlite."""
```

Логи с эмодзи. Не атомарно относительно параллельного deduct (нет BEGIN IMMEDIATE). `amount` может быть отрицательным — не проверяется.

## `deduct_from_balance` (7238–7260)

**Docstring в коде:** есть (дословно):

```
Атомарное списание с основного баланса при достаточности средств.
```

`amount<=0` → True без БД. `BEGIN IMMEDIATE`; `current < amount` → rollback, False. Иначе минус и commit.

## `deduct_from_referral_balance` (7262–7281)

**Docstring в коде:** есть (дословно):

```
Атомарное списание с реферального баланса при достаточности средств.
```

Как выше. По коду: `current = row[0] if row else 0.0` — если строка есть и баланс NULL, сравнение `None < amount` может кинуть TypeError (не ловится, не sqlite3).

## `_referral_setting_is_true` (7300–7302)

**Docstring в коде:** нет

```
"""get_setting(key) в 1/true/yes/on/y; пусто → default (строка true/false)."""
```

## `is_referral_withdraw_method_type_enabled` (7305–7309)

**Docstring в коде:** нет

```
"""True, если тип есть в REFERRAL_WITHDRAW_METHOD_SETTINGS и его setting истинно. default=False."""
```

Неизвестный тип → False (ключ настроек не найден).

## `validate_referral_payout_requisite` (7312–7336)

**Docstring в коде:** есть (дословно):

```
Проверить реквизиты метода получения перед сохранением.
```

Неизвестный тип / пустое value — ошибка. sbp: банк обязателен, 10–15 цифр телефона. card: 16–19 цифр. иначе TRC20: `_REFERRAL_TRC20_RE` (`T` + 33 base58). `(ok, msg)`.

## `format_referral_withdrawal_admin_notice` (7339–7363)

**Docstring в коде:** есть (дословно):

```
Текст уведомления админам о новой заявке на вывод.
```

HTML, `html.escape`. Нет БД.

## `list_referral_payout_methods` (7366–7378)

**Docstring в коде:** нет

```
"""Все referral_payout_methods пользователя, created_at DESC; ошибка → []."""
```

## `add_referral_payout_method` (7381–7400)

**Docstring в коде:** нет

```
"""Валидация типа/реквизитов, INSERT; (ok, msg, lastrowid|None)."""
```

## `delete_referral_payout_method` (7403–7417)

**Docstring в коде:** нет

```
"""DELETE по id и user_id; не найден → (False, «не найден»)."""
```

Чжой метод не удалится (фильтр владельца).

## `get_referral_payout_method` (7420–7436)

**Docstring в коде:** нет

```
"""Строка метода; при user_id — только своего; иначе по id. Нет → None."""
```

## `create_webapp_auth_request` (7439–7452)

**Docstring в коде:** есть (дословно):

```
Создаёт запись ожидания подтверждения входа через deep-link бота (user_id пока NULL).
```

`INSERT OR REPLACE` — повтор того же token обнуляет user_id и created_at. True при успехе.

## `confirm_webapp_auth_request` (7455–7471)

**Docstring в коде:** есть (дословно):

```
Подтверждает вход: бот вызывает эту функцию после получения deep-link auth_{token}.
```

Нет token → False. Есть → UPDATE user_id, True (даже если уже был подтверждён другим user — перезапишет).

## `get_webapp_auth_request` (7474–7493)

**Docstring в коде:** есть (дословно):

```
Возвращает user_id, если запрос уже подтверждён ботом, иначе None.

    Если consume=True и запрос подтверждён, удаляет запись (одноразовое использование).
```

`user_id IS NULL` → None (ещё не подтверждён). consume удаляет только после успешного чтения.

## `cleanup_old_webapp_auth_requests` (7496–7506)

**Docstring в коде:** нет

```
"""DELETE webapp_auth_requests старше max_age_minutes (дефолт 30). Нет return."""
```

## `create_referral_withdrawal_request` (7509–7569)

**Docstring в коде:** есть (дословно):

```
Атомарно списывает сумму с referral_balance пользователя и создаёт заявку на вывод.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 7511–7513 | referral_withdraw_enabled | не 1/true/yes/on/y → отказ |
| 7514–7525 | сумма | ≤0 / < minimum_withdrawal (дефолт 100) |
| 7526–7531 | метод | нет / тип выключен |
| 7533–7546 | BEGIN + open count | ≥ MAX_OPEN (1) в new/processing → откат |
| 7547–7552 | баланс | current < amount → откат |
| 7553–7566 | UPDATE −amount, INSERT status=new | снимок method_type/bank/requisite |

`(ok, msg, id|None)`. Не проверяет `has_open_*` снаружи — тот же инвариант внутри транзакции.

## `has_open_referral_withdrawal_request` (7572–7588)

**Docstring в коде:** есть (дословно):

```
Есть ли у пользователя незакрытая заявка (new/processing).
```

Ошибка → False.

## `list_referral_withdrawal_requests` (7591–7616)

**Docstring в коде:** нет

```
"""Заявки + username; опционально status и/или user_id; ORDER created_at DESC."""
```

## `get_referral_withdrawal_request` (7619–7637)

**Docstring в коде:** нет

```
"""Одна заявка + username по id или None."""
```

## `update_referral_withdrawal_request_status` (7640–7717)

**Docstring в коде:** есть (дословно):

```
Меняет статус заявки на вывод.

    - 'paid': сумма уже была списана с referral_balance при создании заявки; дополнительно
      списывается та же сумма из общего дохода бота — созданием отрицательной "технической"
      транзакции (status='paid', payment_method='referral_payout'), чтобы доходы/аналитика
      (которые считаются как SUM(amount_rub) по успешным транзакциям) автоматически уменьшились
      без рассинхронизации данных.
    - 'rejected': сумма возвращается обратно на referral_balance пользователя.
```

Неизвестный статус → отказ. Уже paid/rejected → отказ (финал). `processing`/`new` — простой UPDATE статуса. paid: INSERT `transactions` с `payment_id=refpayout:{id}`, `amount_rub=-amount`. После commit — свежий `get_referral_withdrawal_request`. `(ok, msg, dict|None)`.

## `get_referral_withdrawable_stats` (7720–7733)

**Docstring в коде:** есть (дословно):

```
Сводка по заявкам на вывод (для админ-панели): счётчики по статусам и суммы.
```

Старт: счётчики new/processing/paid/rejected и суммы new/processing/paid. По коду GROUP BY дописывает `{status}` и `{status}_amount` (в т.ч. `rejected_amount`).

## `get_referral_count` (7736–7744)

**Docstring в коде:** нет

```
"""COUNT users.referred_by = user_id (все рефералы, не только «rich»)."""
```

## `get_user` (7746–7756)

**Docstring в коде:** нет

```
"""users.* по telegram_id или None."""
```

## `get_user_by_username` (7759–7773)

**Docstring в коде:** есть (дословно):

```
Возвращает пользователя по username (без @), регистр не важен.
```

Пустой после `lstrip("@").strip()` → None. `LOWER(username)=LOWER(?) LIMIT 1`.

## `set_terms_agreed` (7775–7783)

**Docstring в коде:** нет

```
"""agreed_to_terms=1. Нет return / проверки, что пользователь есть."""
```

## `is_subscription_expiry_notifications_enabled` (7785–7800)

**Docstring в коде:** есть (дословно):

```
Проверить, включены ли уведомления об истечении срока ключа.
```

Нет строки / ошибка → True (`# По умолчанию включены`). Иначе `bool(row[0])`.

## `toggle_subscription_expiry_notifications` (7802–7826)

**Docstring в коде:** есть (дословно):

```
Переключить статус уведомлений об истечении срока. Возвращает новое состояние.
```

Нет строки: current=1 → new=0, UPDATE 0 rows, return False. Ошибка → True. В коде `#` «Получаем текущее» / «Переключаем» / «Обновляем».

## `update_user_stats` (7828–7835)

**Docstring в коде:** нет

```
"""total_spent += amount_spent, total_months += months_purchased. Нет return."""
```

Без COALESCE: NULL+x → NULL.

## `get_user_count` (7837–7845)

**Docstring в коде:** нет

```
"""COUNT(*) users или 0."""
```

## `get_total_keys_count` (7847–7855)

**Docstring в коде:** нет

```
"""COUNT(*) vpn_keys или 0."""
```

## `get_total_spent_sum` (7857–7874)

**Docstring в коде:** нет

```
"""SUM(amount_rub) у transactions в paid/completed/success, кроме payment_method=balance."""
```

`referral_payout` (отрицательные paid) **входит** в сумму. Ошибка → 0.0.

## `create_pending_transaction` (7876–7901)

**Docstring в коде:** есть (дословно):

```
Create a pending transaction row in `transactions`.

    Used for TON Connect flows.
```

Пустой pid → 0. WAL/pragma как у pending-коннекта, но обычный `sqlite3.connect` (не `_connect_pending_db`). Только `_mirror_pending_to_ledger` — **`pending_transactions` не создаёт**. Возврат `transaction_id` или 0.

## `find_and_complete_ton_transaction` (7904–7995)

**Docstring в коде:** есть (дословно):

```
Atomically completes a TON transaction.

    - validates transaction exists and is still pending
    - enforces amount check against metadata (expected_amount_ton/ton_amount/amount_ton) when present
    - updates using `WHERE ... AND status='pending'` to ensure idempotency
```

Работает по **`transactions`**, не `pending_transactions`. Пустой pid → None. Соединение: timeout=5, `isolation_level=None`, BEGIN IMMEDIATE.

| Строки | Блок | Зачем |
|--------|------|--------|
| 7927–7935 | SELECT pending | нет/уже не pending → rollback, warning, None |
| 7943–7954 | expected | первое из expected_amount_ton, ton_amount, amount_ton; битый float → как «нет expected» |
| 7961–7976 | expected задан | нет/битый amount_ton → None; `tol = max(0.001, exp*0.01)`; \|got-exp\|>tol → None |
| 7961 | expected нет | проверку суммы **пропускает** |
| 7978–7988 | UPDATE paid | amount_currency, currency_name=TON, payment_method=TON; rowcount≠1 → None |
| 7989–7991 | commit | meta + payment_id |

Повтор вебхука (уже paid) → None. Не вызывает `_complete_pending` / не пишет `processed_payments`.

---

Инвентарь этой части: **151**.
