# Комментарии: `src/shop_bot/webapp/handlers.py` (часть 1)

Модульного docstring нет. FastAPI Mini App: объект `app = FastAPI()`, точка входа `shop_bot.webapp.handlers:app` (см. `WEBAPP_MINIAPP_DOCUMENTATION.md`). Одна SQLite с ботом; HTML — строковая замена `{{ ... }}` в `app.html` / `login.html`, не Jinja.

Инвентарь: `_create_payload_pending_or_error` … `SearchKeysRequest` (последняя Pydantic-модель перед `validate_telegram_data`). Auth-роуты, создание платежей и тикеты — в следующих частях.

Константы (не в инвентаре): `TEMP_AUTH_TOKENS` (in-memory `{token: user_id}`); `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = 10 * 60`; SlowAPI `limiter` + `AUTH_RATE_LIMIT`/`SUPPORT_RATE_LIMIT` `"30/minute"`; per-email лимит (`EMAIL_AUTH_PER_EMAIL_LIMIT = 30`, окно 60 с) — в коде `#`: SlowAPI считает только IP, существующий и несуществующий email одинаково. `PASSWORD_RESET_TOKENS` / `PASSWORD_RESET_TTL_SECONDS = 600` — в коде `#`: plaintext 6-digit не в dict.

После импорта на стр. 353 имя `process_successful_payment` в модуле — уже функция бота; обёртка 296–298 перекрыта.

Покрыто записей инвентаря: **84**.

---

## `_create_payload_pending_or_error` (68–76)

**Docstring в коде:** есть (дословно):

```
Создать pending; если слот промокода уже занят — вернуть ошибку для API.
```

`create_payload_pending`. `PromoUnavailableError` → `{"ok": False, "error": promo_error_message}`. `ok` ложь → `"Не удалось создать платёж"`. Успех → `None` (вызывающий продолжает).

## `_email_auth_rate_limit_response` (110–117)

**Docstring в коде:** нет

```
"""JSON 429: ok=False и текст «Rate limit exceeded: {EMAIL_AUTH_PER_EMAIL_LIMIT} per 1 minute»."""
```

Без записи в `_EMAIL_AUTH_HITS`.

## `_email_auth_rate_limited` (120–135)

**Docstring в коде:** есть (дословно):

```
True, если по этому email уже исчерпан EMAIL_AUTH_PER_EMAIL_LIMIT за окно.
```

Ключ — `email.strip().lower()`. Пустой ключ → `False` (слот не пишется). Под `_EMAIL_AUTH_HITS_LOCK`: выкинуть старше окна, если `len >= limit` — `True` без append; иначе append `now` и `False`. Проверка и учёт — в одном вызове.

## `_reject_if_email_auth_rate_limited` (138–141)

**Docstring в коде:** нет

```
"""429 JSON, если `_email_auth_rate_limited`; иначе None."""
```

## `_resolve_user_from_request_token` (144–164)

**Docstring в коде:** нет

```
"""Пользователь по token из body / Authorization Bearer / cookie auth_token; иначе None."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 145–147 | `data.token` или `Authorization` | снять префикс `Bearer ` |
| 149–150 | пусто | cookie `auth_token` |
| 152–153 | нет token | `None` |
| 155–157 | `TEMP_AUTH_TOKENS` | in-memory → `get_user(uid)` |
| 158–164 | иначе | `get_user_by_auth_token`; Exception → `None` |

`init_data` не смотрит. `is_banned` не проверяет.

## `_resolve_authenticated_user` (167–188)

**Docstring в коде:** есть (дословно):

```
Определить текущего пользователя ИСКЛЮЧИТЕЛЬНО по доверенным источникам:
    существующей persistent auth-сессии (см. _resolve_user_from_request_token —
    тот же токен, что хранится в localStorage/cookie webapp) или по подписанным
    Telegram WebApp `init_data`.

    Специально НЕ принимает и не доверяет `user_id`, присланному клиентом в теле
    запроса — используется там, где подмена пользователя была бы небезопасна
    (например, POST /api/webapp/pending-actions/complete).
```

Сначала токен. Затем `data["init_data"]` + `telegram_bot_token` + `validate_telegram_data` → `get_user(id)`. Клиентский `user_id` не читает.

## `_unauthorized` (191–192)

**Docstring в коде:** нет

```
"""JSON 401: `{ok: False, error: detail}`; detail по умолчанию Unauthorized."""
```

## `_require_authenticated_user` (195–215)

**Docstring в коде:** есть (дословно):

```
Resolve caller from auth_token / Bearer / signed init_data only (CWE-862/639).

    Never trusts client-supplied user_id/telegram_id. Returns None if missing
    or banned — callers should respond with ``_unauthorized()``.
```

Кладёт `token`/`init_data` в payload, зовёт `_resolve_authenticated_user`. `None`, если нет user или `is_banned`.

## `_ref_setting_is_true` (218–220)

**Docstring в коде:** нет

```
"""True, если настройка key в 1/true/yes/on/y; пусто → default (true/false)."""
```

`get_setting(key)` или `"true"`/`"false"` по `default`. Регистр не важен.

## `_ref_method_type_enabled` (223–231)

**Docstring в коде:** нет

```
"""True, если тип вывода sbp/card/usdt_trc20 включён своей настройкой."""
```

| `method_type` | Ключ |
|---------------|------|
| `sbp` | `referral_withdraw_sbp_enabled` |
| `card` | `referral_withdraw_card_enabled` |
| `usdt_trc20` | `referral_withdraw_usdt_enabled` |

Иной тип → `False`.

## `get_transaction_comment` (235–262)

**Docstring в коде:** есть (дословно):

```
Короткое человекочитаемое описание платежа — для поля description в
    ЮKassa/ЮMoney и подписи Stars-инвойса.

    Раньше здесь была попытка импортировать одноимённую функцию из
    `shop_bot.bot.handlers`, которой там никогда не было — это ломало ЛЮБУЮ
    оплату из webapp (ЮKassa/ЮMoney/Stars) с `ImportError`, тихо проглоченным
    общим `except Exception` в /api/create-payment. Теперь строка собирается
    здесь же, без зависимости от модуля бота.
```

`extend` → «Продление подписки», иначе «Оплата подписки». `value` → месяцы (ошибка → 0). Кто: `@username` или `#id`. Хост в скобках. Пустые куски отбрасывает.

## `calculate_webapp_price` (264–289)

**Docstring в коде:** нет. В коде `#`: Seller Discount; Referral Discount (First purchase).

```
"""Цена со скидкой продавца и реферальной скидкой на первую покупку; round 2 знака."""
```

Нет user → исходная цена. Seller: `seller_active` и `seller_sale` %. Реферал: `referred_by` и `total_spent == 0` и `referral_discount` > 0. Exception → лог, вернуть текущее `price`. **БД:** `get_user`, `get_seller_user`, `get_setting`.

## `notify_admin_of_purchase` (292–294)

**Docstring в коде:** нет

```
"""Прокси на одноимённую функцию `shop_bot.bot.handlers`."""
```

Импорт внутри тела. **Telegram** — в боте.

## `process_successful_payment` (296–298)

**Docstring в коде:** нет

```
"""Прокси на `shop_bot.bot.handlers.process_successful_payment`; вернуть её результат."""
```

Импорт внутри тела. После стр. 353 это имя в модуле — уже функция бота (обёртка перекрыта).

## `_send_telegram_message` (300–314)

**Docstring в коде:** нет

```
"""Один HTML-message или photo основному боту; без токена / сбой send → False."""
```

Новый `Bot` на вызов, в `finally` `session.close()`. **Telegram.**

## `_send_invoice_stars` (316–335)

**Docstring в коде:** нет

```
"""Инвойс Stars (XTR, пустой provider_token); без токена / сбой → False."""
```

`LabeledPrice(label=title, amount=amount)`. **Telegram.**

## `_platega_api` (357–362)

**Docstring в коде:** нет

```
"""PlategaAPI из merchant_id+secret; пустое любое → None. base_url из настройки."""
```

## `_store_platega_transaction_id` (365–373)

**Docstring в коде:** нет

```
"""Дописать platega_transaction_id в pending meta через create_payload_pending; пустой txid — no-op."""
```

Exception → `logger.warning`, без проброса.

## `_rollypay_is_enabled` (376–380)

**Docstring в коде:** нет

```
"""True, если rollypay_api_key и rollypay_signing_secret оба непустые после strip."""
```

## `_rollypay_api` (383–387)

**Docstring в коде:** нет

```
"""RollyPayAPI(api_key, terminal_id); без api_key → None. signing_secret здесь не проверяет."""
```

`terminal_id` — `rollypay_terminal_id` или `""`.

## `_store_rollypay_payment_id` (390–398)

**Docstring в коде:** нет

```
"""Дописать rollypay_payment_id в pending meta; пустой provider_id — no-op."""
```

Как `_store_platega_transaction_id`. Exception → warning.

## `_fulfill_webapp_paid_order` (401–416)

**Docstring в коде:** нет

```
"""Выдать услугу через process_successful_payment; без токена — bot=object(); закрыть session если есть."""
```

Зовёт модульное `process_successful_payment` (после 353 — функция бота). `bool(...)`. close session глотает Exception.

## `_build_yoomoney_link` (423–435)

**Docstring в коде:** нет

```
"""GET-ссылка yoomoney.ru/quickpay/confirm.xml: donate, sum 2 знака, successURL t.me/bot."""
```

`targets` — `description[:50]`. `label` — метка платежа. `receiver` strip.

## `_webapp_no_cache_middleware` (442–449)

**Docstring в коде:** нет. `@app.middleware("http")`.

```
"""Для `/` и text/html: Cache-Control no-store/no-cache, Pragma no-cache, Expires 0."""
```

Иначе заголовки не трогает.

## `_hidden_not_found` (460–462)

**Docstring в коде:** есть (дословно):

```
Как несуществующий URL: стандартный FastAPI 404, без Unauthorized.
```

`raise HTTPException(status_code=404)`. Аннотация `-> None`.

## `_block_ticket_files_dir` (467–469)

**Docstring в коде:** есть (дословно):

```
Каталог ticket_files не является static и не должен открываться по URL.
```

`GET/HEAD/POST/PUT/DELETE` на `/ticket_files` и `/ticket_files/{rest:path}`. `rest` не используется. Сразу `_hidden_not_found()`.

## `api_referral_payout_methods_list` (474–494)

**Docstring в коде:** нет. `POST /api/referral/payout-methods/list`.

```
"""Список реквизитов вывода текущего user + min_withdraw и флаг withdraw_enabled."""
```

Auth: `_resolve_user_from_request_token` (не `_require_authenticated_user`: без init_data и без проверки бана). Битый JSON → `data = {}`. На каждый method — `type_enabled`. Список упал → `[]`. `minimum_withdrawal` ошибка → `100.0`. `withdraw_enabled` = `_ref_setting_is_true("referral_withdraw_enabled")`.

## `api_referral_payout_methods_add` (499–523)

**Docstring в коде:** нет. `POST /api/referral/payout-methods/add`.

```
"""Добавить реквизит: method_type + requisite_value; bank_name опционален."""
```

Битый JSON → ошибка. Нет type/value → «Заполните все поля». Вывод выкл / тип выкл — отказ. `add_referral_payout_method(telegram_id, ...)`.

## `api_referral_available_method_types` (527–553)

**Docstring в коде:** нет. `POST /api/referral/available-method-types`.

```
"""Включённые типы вывода (sbp/card/usdt_trc20) и список банков СБП."""
```

Вывод выкл → `methods=[]`, `sbp_banks=[]`. `sbp` без банков в `referral_withdraw_sbp_banks` пропускается. В ответ без ключа `setting`.

## `api_referral_payout_methods_delete` (557–575)

**Docstring в коде:** нет. `POST /api/referral/payout-methods/delete`.

```
"""Удалить свой реквизит по method_id; чужой id → Method not found."""
```

Вывод выкл — отказ. Нет `method_id` → ошибка. Сначала `get_referral_payout_method` (владелец), потом `delete_referral_payout_method`.

## `api_key_auto_renew` (579–599)

**Docstring в коде:** нет. `POST /api/key/auto-renew`.

```
"""Вкл/выкл auto_renew своего ключа; чужой/нет ключа → Key not found."""
```

Нужны `key_id` и `enabled`. Сверка `key.user_id == user.telegram_id`. `set_key_auto_renew`.

## `api_referral_request_withdraw` (604–648)

**Docstring в коде:** нет. `POST /api/referral/request-withdrawal`.

```
"""Заявка на вывод реф. баланса: amount>0 и method_id; при успехе — Telegram админам."""
```

Вывод выкл — отказ (и `error`, и `message`). `amount` не float / ≤0 → Invalid amount. `create_referral_withdrawal_request`. Успех с `new_id`: `format_referral_withdrawal_admin_notice` + `_send_telegram_message` каждому из `get_admin_ids`; сбой уведомления — warning. `has_open_request`: успех или уже есть открытая заявка.

**БД. Telegram.**

## `api_referral_list_withdrawals` (653–684)

**Docstring в коде:** нет. `POST /api/referral/withdrawals`.

```
"""История заявок на вывод: публичные поля + has_open_request (new/processing)."""
```

Ошибка списка →  `"Server error"`. Поля строки: id, amount, status, method_type, bank_name, requisite_value, reject_reason, created_at, processed_at.

## `_format_remaining_details` (687–709)

**Docstring в коде:** нет. В коде `#`: Берём только первые две значимые части для краткости.

```
"""Краткий остаток: г./д./ч./мин, не больше двух частей; ≤0 → 0мин."""
```

Дни = `remaining.days % 365`, годы = `// 365`. Пустой `parts[:2]` → «меньше минуты».

## `_format_bytes` (711–726)

**Docstring в коде:** нет

```
"""Размер в B/KB/MB/GB/TB (1024); строка с уже готовой единицей — как есть."""
```

`None` / не-число / ≤0 → `"0 B"`. Два знака после запятой.

## `_process_template_placeholders` (728–776)

**Docstring в коде:** нет. В коде `#`: Selected key display variants.

```
"""Подставить {{ ... }} в HTML строковой заменой; затем сетку серверов/тарифов."""
```

| Плейсхолдер | Откуда |
|-------------|--------|
| `panel_brand_title` | `webapp_title` / `panel_brand_title` / `"Xatab VPN"` |
| `user_profile_card`, `key_info_section`, `profile_keys_list`, `setup_keys_list`, `renew_keys_dropdown_options`, `renew_plans_grid`, `min_price`, `webapp_logo`, `webapp_icon` | `context_data` |
| `support_bot_username` | `support_contact_username` или `support_bot_username` |
| `logo_hidden` | `"hidden"` если нет логотипа |
| `user_id`, `bot_username`, `webapp_domain` | аргумент / настройки |
| `tg_fullscreen_css` | блок `<style>` только если `tg_fullscreen` |
| `renew_selected_key_display` | и однострочный, и вариант с переносом в `{{ }}` |
| `server_dropdown_options`, `server_plans_grid` | `_get_servers_and_plans_html(user_id)` после цикла replace |

Jinja нет. Неизвестные `{{ }}` не трогает.

## `_format_bytes_gb` (778–785)

**Docstring в коде:** есть (дословно):

```
Тот же формат ГБ, что в карточке ключа бота.
```

`int(bytes)/1024³`, `:.2f`, обрезать хвостовые нули и точку. TypeError/ValueError → `"0"`.

## `_format_gb_amount` (788–793)

**Docstring в коде:** нет

```
"""ГБ из числа: целое → без дроби, иначе :g; мусор → 0."""
```

## `_is_key_without_billing_plan` (796–815)

**Docstring в коде:** есть (дословно):

```
Триал/подарок: биллингового тарифа нет — докупка LTE недоступна (как в боте).
```

`tag` в `{trial, триал}` или содержит `gift`. Либо `description` JSON: `is_trial` или `source` в `{trial, gift}`. Ошибка разбора — игнор.

## `_resolve_plan_id_for_key` (818–842)

**Docstring в коде:** есть (дословно):

```
plan_id из description JSON, иначе первый активный тариф хоста (как в боте).
```

Триал/подарок без `plan_id` в JSON → `None` (хост не смотрит). Нет `host_name` / планов / битого `plan_id` → `None`. `get_active_plans_for_host`[0].

## `_lte_card_state` (845–895)

**Docstring в коде:** есть (дословно):

```
Условия и цифры LTE-пула — те же, что в карточке ключа бота.

    Показываем блок и кнопку докупки только если:
      1) у тарифа ключа задан lte_limit_bytes > 0;
      2) на хосте ключа есть активный сквад класса lte.
    Лимит = plans.lte_limit_bytes + докупленный буст (resolve_lte_limit_bytes).
```

`empty`: `show_lte`/`show_lte_topup` False, нули, `plan=None`. Нет `plan_id` / не `should_account_lte_traffic` / нет сквада `lte` / Exception → `empty`. Иначе оба show True; строка «X ГБ / Y ГБ» + «(сброс …)» если `format_next_traffic_reset_display`.

## `_owned_lte_key_and_plan` (898–909)

**Docstring в коде:** есть (дословно):

```
Ключ принадлежит user_id и доступен для LTE-докупки. Иначе (None, None).
```

Нет ключа / `user_id` не совпал / нет `show_lte_topup` или `plan` → `(None, None)`. Иначе `(key, plan)`.

## `_process_key_data` (912–1042)

**Docstring в коде:** нет. В коде `#`: expiry, days left, progress, display name, subscription URL, limits, created date.

```
"""Словарь для карточек: имя, срок, прогресс, трафик/HWID/LTE, статус, sub_url."""
```

Дата `%Y-%m-%d %H:%M:%S`; сбой → now / `"Unknown"`. Остаток — `_format_remaining_details` или «Истёк». Прогресс от `created_at` до expiry, clamp 0–100. Имя: `user_key_name`/`name`, иначе `Ключ #` + local-part email (`@bot.local` срезается) / `short_uuid` / `key_id`. Трафик ≤0 → `∞`. HWID: `limit_ips` в (0; 99) — число, иначе `∞`. Статус: >5 дн. Активен / >0 Скоро / иначе Истёк. LTE из `_lte_card_state`. `traffic_info` + сброс через walrus `reset_txt`.

## `_get_key_html` (1044–1089)

**Docstring в коде:** нет

```
"""Компактная секция ключа на главной: имя, дата, дни, полоска percent_str."""
```

Заголовок в разметке всегда «Активна» (не `status_text`). Зовёт `_process_key_data`.

## `_get_profile_card_html` (1091–1220)

**Docstring в коде:** нет. В коде `#`: формат валюты `1 240,50 ₽`; кнопка sync.

```
"""Карточка профиля: баланс, рефералы, заработок, ключи, дата регистрации; sync для id 999*."""
```

`user` пуст → `""`. Суммы: пробел тысяч, запятая дробной, `₽`. Возраст: дн. / м.+д. / г.+м.+д. Кнопка «Синхронизировать с Telegram» только если `telegram_id` int и `str(...).startswith("999")` (email-аккаунт, см. WEBAPP_MINIAPP). «Доступно к выводу» — `referral_balance`.

## `_get_key_card_html` (1222–1351)

**Docstring в коде:** есть (дословно):

```
Render the full key-card block (used for regular keys and, with an extra
    badge/CTA, for not-yet-activated gift keys so both share the same UI).
```

Раскрываемая карточка: срок, трафик, HWID, LTE (`_html_esc` метки), комментарий, sub_url, устройства/имя/заметка, продлить, автопродление, докупка LTE. `badge_html` / `extra_content_html` вставляются как есть.

## `_key_created_sort_tuple` (1353–1364)

**Docstring в коде:** есть (дословно):

```
Sort key for newest-purchased-first: created_at desc, then key_id desc.
```

`created_at` или `created_date`, первые 19 символов `%Y-%m-%d %H:%M:%S`; сбой → `datetime.min`. Битый `key_id` → 0. Сам tuple по возрастанию; desc даёт вызывающий `reverse=True`.

## `_sort_keys_newest_first` (1367–1368)

**Docstring в коде:** нет

```
"""sorted(keys, key=_key_created_sort_tuple, reverse=True)."""
```

Новый список, исходный не мутирует.

## `_get_profile_keys_html` (1371–1378)

**Docstring в коде:** нет

```
"""Склеить `_get_key_card_html` по всем keys; пусто → `_get_no_key_html`."""
```

## `_get_setup_keys_html` (1380–1464)

**Docstring в коде:** нет

```
"""Карточки подключения (инструкция/устройства/имя/заметка); истёкшие (days_left≤0) пропуск."""
```

Пустой `keys` → `_get_no_key_html`. Если все истекли — по коду пустая строка `""`, не empty-state.

## `_get_renew_keys_html` (1466–1512)

**Docstring в коде:** нет

```
"""(options_html, selected_text, renew_plans_html): дропдаун ключей и сетки тарифов."""
```

Нет keys → `("", "Нет активных ключей", _get_no_key_html())`. Первый ключ выбран. На каждый — `_build_plans_grid_html(..., "renew-plans-{index}")` + скрытый `renew-desc-content-{index}`.

## `_get_no_key_html` (1514–1525)

**Docstring в коде:** нет

```
"""Empty-state: «Нет активных ключей» и призыв купить."""
```

Константная HTML-строка.

## `_duration_label` (1529–1548)

**Docstring в коде:** нет

```
"""Подпись срока: дни (кратно 30→месяцы, 7→недели), иначе months; months≤0 → 1 месяц."""
```

Русские окончания 1 / 2–4 / остальное. `duration_days` приоритетнее `months`.

## `_days_from_plan` (1551–1562)

**Docstring в коде:** нет

```
"""Дни плана: duration_days>0 или max(1, months)*30."""
```

## `_billing_months_for_plan` (1565–1566)

**Docstring в коде:** нет

```
"""Дни/30, но не меньше 1/30."""
```

## `_build_plans_grid_html` (1569–1637)

**Docstring в коде:** нет

```
"""Сетка активных тарифов хоста (цена через calculate_webapp_price) и текст description."""
```

По коду возвращает `(desc, html)`, несмотря на аннотацию `-> str`. Нет активных на хосте — активные планы других хостов с `_purchase_host_name`. Пусто → «Нет доступных тарифов». Нечётный последний — `col-span-2`. `import re` внутри (модульный `re` уже есть). Сбой цены/месяцев — `continue` (план пропускается).

## `_get_servers_and_plans_html` (1640–1683)

**Docstring в коде:** нет

```
"""(options_html, plans_html): дропдаун хостов и сетки тарифов; первый хост выбран."""
```

Нет хостов → `("", «Нет доступных серверов» ...)`. На каждый хост — `_build_plans_grid_html(..., "plans-{index}")` + скрытый `desc-content-{index}`.

## `_render_banned_page` (1686–1765)

**Docstring в коде:** нет

```
"""HTML 403: «Доступ ограничен» / ЗАБЛОКИРОВАН и ссылка t.me/support_bot_username."""
```

`title`/`logo` из webapp_settings (fallback `panel_brand_title` / `"Xatab VPN"`). `icon` читается и не подставляется. Не `support_contact_username`.

## `_render_main_page` (1768–1966)

**Docstring в коде:** нет. В коде `#`: webapp_enabled; бан; live stats только active; min price; секции.

```
"""Собрать app.html: карточки, тарифы, min_price; выкл → 403; бан → banned page."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1772–1773 | не `webapp_enabled` | `<h1>Webapp is disabled</h1>` 403 |
| 1776–1778 | `is_banned` | `_render_banned_page` |
| 1793–1799 | есть user_id | ключи: newest-first для профиля; expiry-asc для home/renew/setup |
| 1804–1907 | active (expiry > now) | live: `get_key_details_from_host` → uuid → traffic/HWID |
| 1909–1926 | min_price | минимум `calculate_webapp_price` по активным планам всех хостов |
| 1928–1946 | секции | home — ближайший active (`_get_key_html`); renew/setup — по expiry; профиль — newest |
| 1948–1966 | `app.html` | `_process_template_placeholders` → `HTMLResponse` |

По коду `min_price_val` задаётся только внутри `if user_id` (вызывающий `index` так и делает). Live-ошибка — лог, карточки без свежих счётчиков.

**БД. HTTP к панели Remnawave.**

## `index` (1970–2010)

**Docstring в коде:** нет. `GET /`. В коде `#`: Authorize by Token only; IDOR CWE-639 на голый `user_id`.

```
"""Кабинет по query token (get_user_by_auth_token); без токена — login.html; бан — 403."""
```

Параметр `user_id` принимается FastAPI и сразу затирается: `user_id = resolved_user_id`. По коду cookie `auth_token` здесь не читается (только query `token`), хотя комментарий упоминает cookie. Нет файла login → 404 «Login page not found». Exception → 500 HTML с `traceback.format_exc()`.

## `SupportStatusRequest` (2014–2017)

**Docstring в коде:** нет

```
"""Тело статуса поддержки: личность не из user_id."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `SupportTicketCreateRequest` (2019–2023)

**Docstring в коде:** нет

```
"""Тело создания тикета."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `subject` | тема тикета |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `SupportMessageSendRequest` (2025–2030)

**Docstring в коде:** нет

```
"""Тело сообщения в тикет."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `ticket_id` | id тикета |
| `message` | текст сообщения |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `SupportTicketRequest` (2032–2036)

**Docstring в коде:** нет

```
"""Тело операций с одним тикетом (просмотр/закрытие)."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `ticket_id` | id тикета |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `PaymentMethodsRequest` (2038–2041)

**Docstring в коде:** нет

```
"""Тело запроса доступных способов оплаты."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `TokenRequest` (2043–2044)

**Docstring в коде:** нет

```
"""Тело выдачи persistent-токена по Telegram initData."""
```

| Поле | Назначение |
|------|------------|
| `init_data` | подписанные Telegram WebApp initData |

## `TelegramDirectAuthRequest` (2046–2048)

**Docstring в коде:** есть (дословно):

```
Must carry signed Telegram WebApp initData — never a bare user_id.
```

| Поле | Назначение |
|------|------------|
| `init_data` | подписанные Telegram WebApp initData |

## `EmailAuthRequest` (2050–2052)

**Docstring в коде:** нет

```
"""Тело регистрации/логина по email+пароль."""
```

| Поле | Назначение |
|------|------------|
| `email` | адрес почты |
| `password` | пароль |

## `EmailVerifyRequest` (2054–2056)

**Docstring в коде:** нет

```
"""Тело подтверждения email кодом."""
```

| Поле | Назначение |
|------|------------|
| `email` | адрес почты |
| `code` | код подтверждения |

## `EmailResendRequest` (2058–2059)

**Docstring в коде:** нет

```
"""Тело повторной отправки кода на email."""
```

| Поле | Назначение |
|------|------------|
| `email` | адрес почты |

## `PasswordResetRequest` (2061–2062)

**Docstring в коде:** нет

```
"""Тело запроса сброса пароля (код на почту)."""
```

| Поле | Назначение |
|------|------------|
| `email` | адрес почты |

## `PasswordResetCheckRequest` (2064–2066)

**Docstring в коде:** нет

```
"""Тело проверки кода сброса (без смены пароля)."""
```

| Поле | Назначение |
|------|------------|
| `email` | адрес почты |
| `code` | код сброса |

## `PasswordResetVerifyRequest` (2068–2071)

**Docstring в коде:** нет

```
"""Тело смены пароля по коду сброса."""
```

| Поле | Назначение |
|------|------------|
| `email` | адрес почты |
| `code` | код сброса |
| `new_password` | новый пароль |

## `_hash_password_reset_code` (2079–2080)

**Docstring в коде:** нет

```
"""SHA-256 hex от `{email.strip().lower()}:{code.strip()}`."""
```

Не salt из настроек — только нормализованный email и код.

## `_password_reset_code_matches` (2083–2090)

**Docstring в коде:** нет

```
"""True, если hmac.compare_digest(hash(email, code), stored_hash); пустой hash / сбой → False."""
```

`code or ""`. Exception compare → `False`.

## `SyncTgRequest` (2092–2094)

**Docstring в коде:** нет

```
"""Тело привязки email-аккаунта к Telegram."""
```

| Поле | Назначение |
|------|------------|
| `token` | persistent auth-токен текущего (email) аккаунта |
| `init_data` | подписанные Telegram WebApp initData |

## `DeviceTiersRequest` (2097–2098)

**Docstring в коде:** нет

```
"""Тело запроса тарифных ступеней по лимиту устройств."""
```

| Поле | Назначение |
|------|------------|
| `host_name` | имя хоста |

## `CreatePaymentRequest` (2100–2111)

**Docstring в коде:** нет

```
"""Тело создания оплаты подписки / продления."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `payment_method` | способ оплаты |
| `plan_id` | id тарифа |
| `host_name` | имя хоста |
| `action` | действие (покупка/продление и т.п.) |
| `key_id` | id ключа (продление) |
| `promo_code` | промокод |
| `tier_device_count` | число устройств выбранной ступени |
| `tier_price` | надбавка ступени, по умолчанию 0 |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `CreateTopUpPaymentRequest` (2113–2118)

**Docstring в коде:** нет

```
"""Тело пополнения баланса."""
```

| Поле | Назначение |
|------|------------|
| `payment_method` | способ оплаты |
| `amount` | сумма пополнения |
| `token` | persistent auth-токен |
| `user_id` | в коде `#`: ignored; identity from token only |
| `init_data` | подписанные Telegram WebApp initData |

## `CreateLteTopUpPaymentRequest` (2120–2126)

**Docstring в коде:** нет

```
"""Тело оплаты докупки LTE-пакета."""
```

| Поле | Назначение |
|------|------------|
| `payment_method` | способ оплаты |
| `key_id` | id ключа |
| `package_id` | id пакета LTE |
| `token` | persistent auth-токен |
| `user_id` | в коде `#`: ignored; identity from token only |
| `init_data` | подписанные Telegram WebApp initData |

## `ApplyPromoRequest` (2128–2134)

**Docstring в коде:** нет

```
"""Тело проверки промокода и пересчёта цены."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `promo_code` | промокод |
| `plan_id` | id тарифа |
| `price` | цена до скидки |
| `token` | persistent auth-токен |
| `init_data` | подписанные Telegram WebApp initData |

## `RenameKeyRequest` (2136–2140)

**Docstring в коде:** нет

```
"""Тело переименования ключа."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `key_id` | id ключа |
| `new_name` | новое имя |
| `token` | persistent auth-токен |

## `DeleteAllDevicesRequest` (2142–2146)

**Docstring в коде:** нет

```
"""Тело сброса всех устройств ключа."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `key_id` | id ключа |
| `host_name` | имя хоста |
| `token` | persistent auth-токен |

## `SearchKeysRequest` (2148–2151)

**Docstring в коде:** нет

```
"""Тело поиска ключей пользователя по строке."""
```

| Поле | Назначение |
|------|------------|
| `user_id` | в коде `#`: ignored; identity from token only |
| `query` | поисковая строка |
| `token` | persistent auth-токен |

Дальше в исходнике — `validate_telegram_data` (в эту часть не входит).
