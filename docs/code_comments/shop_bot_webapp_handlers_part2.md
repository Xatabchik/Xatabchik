# Комментарии: `src/shop_bot/webapp/handlers.py` (часть 2)

Вторая половина Mini App FastAPI: с `validate_telegram_data` до конца файла (`dynamic_route`). Часть 1 — хелперы, HTML-рендер, модели запросов до `SearchKeysRequest`. Модульного docstring нет.

Имена и диапазоны строк — как в `INVENTORY.md` секция `src/shop_bot/webapp/handlers.py`. **Записей инвентаря в этой части: 89.**

Связано: [WEBAPP_MINIAPP_DOCUMENTATION.md](../../WEBAPP_MINIAPP_DOCUMENTATION.md) §5–5.1 (initData, pending action, `/ref` `/gift`), [PAYMENTS_DOCUMENTATION.md](../../PAYMENTS_DOCUMENTATION.md) (инвойс → webhook/`verify` → `process_successful_payment`).

---

## Идентичность: только token / initData

Пользователь **никогда** не берётся из клиентского `user_id` / `telegram_id`. В части 1 это зафиксировано в `_resolve_authenticated_user` и `_require_authenticated_user` (CWE-862/639: «Never trusts client-supplied user_id»). Модели вроде `KeyActionRequest` всё ещё принимают `user_id: int | None = None` с комментарием в коде `# ignored; identity from token only` — поле игнорируется.

Источники (по коду хелперов части 1):

| Источник | Как | Кто зовёт |
|----------|-----|-----------|
| persistent token | тело/query `token`, `Authorization: Bearer`, cookie `auth_token`, либо in-memory `TEMP_AUTH_TOKENS` | `_resolve_user_from_request_token` |
| Telegram WebApp `init_data` | HMAC + `auth_date` через `validate_telegram_data`, затем `get_user(id)` | `_resolve_authenticated_user` |

`_require_authenticated_user` = то же + бан → `None` → обычно `_unauthorized()` (401).

В этой части есть исключения по коду (не домысел):

- Профиль (`/api/user/profile-*`), rename / delete-all / search ключей — только token (`_resolve_user_from_request_token`), **без** initData.
- `api_check_payment` при отсутствии сессии отдаёт нейтральный unpaid, не 401 (см. `_check_payment_unpaid`).
- `api_device_tiers` и `api_pending_action_info` — без идентичности (хост / публичный pending_token).
- `api_pending_action_complete` явно: `user_id` в теле не принимается (CWE-306 в соседнем `api_telegram_direct_auth`).

Auth-роуты: `@limiter.limit(AUTH_RATE_LIMIT)` = `30/minute`. Email-эндпоинты дополнительно `_reject_if_email_auth_rate_limited` (лимит по нормализованному email, часть 1).

---

## `validate_telegram_data` (2156–2222)

**Docstring в коде:** есть

```
Verify Telegram WebApp initData HMAC and freshness (auth_date).

    Protocol: secret = HMAC_SHA256(key="WebAppData", msg=bot_token);
    compare hash with HMAC_SHA256(secret, data_check_string).
```

Стандарт Telegram WebApp. `max_age_seconds` default `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` (10×60). В коде `#` у константы: Reject stale signed payloads.

| Строки | Блок | Зачем |
|--------|------|--------|
| 2173–2175 | коротко | пустой / `len < 10` → None |
| 2177–2180 | parse | `parse_qsl(..., keep_blank_values=True)`; нет `hash` → None |
| 2182–2196 | HMAC | pop hash; `data_check_string` = `k=v` по sorted keys через `\n`; `hmac.compare_digest` |
| 2198–2213 | freshness | нет/не int `auth_date` → None; `auth_date > now+60` (будущее) → None; старше max_age → None |
| 2215–2219 | user | JSON поля `user`; hash ок, но нет user → None |
| 2220–2222 | except | любой exception → None |

Успех — `dict` из `user` JSON (есть `id`), не весь initData.

---

## `_issue_persistent_token_for_telegram_user` (2225–2239)

**Docstring в коде:** есть

```
Shared token issue/lookup used by /api/auth/token and /api/auth/telegram-direct.
```

Бан → `{"ok": False, "error": "Access denied", "status_code": 403}`. Есть `get_auth_token_by_user_id` — вернуть его; иначе UUID + `update_user_auth_token`.

По коду: `api_telegram_direct_auth` **не** вызывает этот хелпер — дублирует ту же логику плюс «user not registered».

---

## `api_request_auth_token` (2244–2255)

**Docstring в коде:** нет. `GET /api/auth/request-token`.

```
"""Выдать временный токен логина и deep-link `tg://resolve?domain=<bot>&start=auth_<token>`."""
```

UUID[:36] в `TEMP_AUTH_TOKENS[token] = None` и `create_webapp_auth_request`. `cleanup_old_webapp_auth_requests` — ошибка только в лог. Бот подтверждает через `confirm_webapp_auth_request` (см. WEBAPP §5).

---

## `api_check_auth_token` (2259–2297)

**Docstring в коде:** нет. `GET /api/auth/check-token/{token}`. В коде `#`: in-memory fast path vs БД vs другая реплика.

```
"""Поллинг: подтверждён ли временный токен; выдать/вернуть persistent UUID."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2262–2273 | TEMP | token в памяти и value не None → pop user_id; существующий persistent или новый UUID |
| 2276–2280 | persistent | `get_user_by_auth_token(token)`: бан → authorized False «Banned»; иначе тот же token |
| 2283–2295 | webapp_auth_requests | `get_webapp_auth_request(..., consume=True)` — бот в другом процессе |
| 2297 | иначе | `authorized: False` |

По коду 2288: `if user and user.get('is_banned')` смотрит `user` из шага 2 (там он None, иначе вышли раньше) — проверка бана confirmed_user_id в этой ветке не срабатывает.

---

## `api_create_token` (2301–2316)

**Docstring в коде:** есть. `POST /api/auth/token`. Тело `TokenRequest.init_data`.

```
Generate or retrieve a persistent login token using verified Telegram data.
```

Нет `telegram_bot_token` → 500. `validate_telegram_data` без `id` → 401 «Invalid auth data». Дальше `_issue_persistent_token_for_telegram_user`. Ответ успеха: `{ok, token}` без `user_id`.

---

## `api_telegram_direct_auth` (2321–2354)

**Docstring в коде:** есть. `POST /api/auth/telegram-direct`. Тело `TelegramDirectAuthRequest` (часть 1: «Must carry signed Telegram WebApp initData — never a bare user_id»).

```
Authenticate inside Telegram WebApp using signed initData only.

    Previously accepted a bare ``user_id`` from the client (CWE-306). User identity
    is now taken exclusively from HMAC-validated Telegram WebApp initData.
```

Нет бот-токена → 500. Невалидный initData → 401. `get_user` нет → 401 «User not registered» (в отличие от `/api/auth/token`, который токен выдаёт и без строки в БД — по коду `_issue_*` зовёт `get_user` только ради бана). Бан → 403. Иначе существующий или новый persistent token + `user_id` в JSON. except → 500 «Auth error».

---

## `_validate_password` (2356–2375)

**Docstring в коде:** есть

```
Проверка пароля при регистрации / сбросе / смене.

    Раньше хватало 5 символов без цифр («ababa») — это принималось.
    Существующие аккаунты с таким паролем по-прежнему входят (login
    политику не применяет); новые пароли должны быть длиннее и смешанные.
```

Не-str → `str`. Ошибки: `< 8`; только цифры; нет буквы; нет цифры; `len(set) < 2`. Иначе None.

---

## `_issue_email_verification_code` (2381–2410)

**Docstring в коде:** есть

```
Сгенерировать, сохранить и отправить новый код подтверждения email.

    Возвращает (ok, error). Не поднимает исключения наружу.

    Отправка письма (блокирующий вызов smtplib, может делать несколько попыток
    с паузами при сетевых сбоях) выполняется в отдельном потоке через
    `asyncio.to_thread`, чтобы не блокировать event loop на время ожидания/повторов.
```

SMTP не настроен → ошибка. Код `000000`–`999999`. `set_email_verification_code(..., EMAIL_CODE_TTL_SECONDS=600)`. `send_activation_code` в `to_thread`.

Константы рядом: `EMAIL_RESEND_COOLDOWN_SECONDS = 60`.

---

## `api_email_register` (2415–2440)

**Docstring в коде:** нет. `POST /api/auth/email/register`. В коде `#`: тот же ответ, что у новой регистрации — иначе enumeration занятых адресов.

```
"""Регистрация email+пароль: виртуальный пользователь, код на почту; занятый email неотличим от нового."""
```

Rate-limit email → 429-хелпер. `_validate_password`. `get_user_by_email` есть → `{ok, requires_verification, email}` без письма. `create_user_by_email` fail → ошибка. Иначе `_issue_email_verification_code`. WEBAPP: telegram_id с префиксом `999` (email-only).

---

## `api_email_verify` (2444–2461)

**Docstring в коде:** нет. `POST /api/auth/email/verify`. В коде `#`: не раскрывать существование email; код обязателен всегда (раньше при `email_verified=1` токен без кода).

```
"""Проверить код и выдать persistent token; неверный/нет user/пустой код — одна ошибка."""
```

`check_email_verification_code` + `mark_email_verified` + новый UUID token.

---

## `api_email_resend` (2465–2488)

**Docstring в коде:** нет. `POST /api/auth/email/resend`.

```
"""Повтор кода: нет user или уже verified → `{ok: True}` без письма; cooldown 60 с тоже `{ok: True}`."""
```

По коду успех без различия «отправлено / рано / некого» — кроме fail SMTP (`ok: False`).

---

## `api_email_login` (2492–2509)

**Docstring в коде:** нет. `POST /api/auth/email/login`. Политику `_validate_password` не применяет (как в docstring `_validate_password`).

```
"""Вход email+пароль: неверный pair — одна ошибка; бан; не verified; иначе новый token."""
```

`verify_password` по `auth_pass`. Каждый логин переписывает auth token.

---

## `api_email_reset_request` (2513–2546)

**Docstring в коде:** нет. `POST /api/auth/email/reset/request`. В коде `#`: всегда один ответ — иначе оракул «есть email / привязан к TG».

```
"""Запросить код сброса: 6 цифр в Telegram (`_send_telegram_message`), hash в `PASSWORD_RESET_TOKENS`."""
```

По коду (не WEBAPP §5 про SMTP): письмо не шлётся. `is_email_only_user` или нет user → `{ok: True}` без кода. Иначе `code_hash` = `_hash_password_reset_code`, TTL `PASSWORD_RESET_TTL_SECONDS` (600). Fail отправки — pop токена, всё равно `{ok: True}`. Комментарий у dict (часть 1): plaintext только в сообщении TG.

---

## `api_email_reset_check` (2550–2566)

**Docstring в коде:** нет. `POST /api/auth/email/reset/check`.

```
"""Проверить код сброса без смены пароля: нет/истёк/неверный hash."""
```

`_password_reset_code_matches` (hmac.compare_digest). Токен не удаляется.

---

## `api_email_reset_verify` (2570–2595)

**Docstring в коде:** нет. `POST /api/auth/email/reset/verify`.

```
"""Сменить пароль по коду: `_validate_password` + `update_user_password`; успех — del токена."""
```

Истёкший код удаляется. Неверный код токен оставляет. Rate-limit по email.

---

## `api_user_profile_info` (2607–2623)

**Docstring в коде:** нет. `POST /api/user/profile-info`. Комментарий блока (2598–2602): пункт «Редактировать профиль» только у email-аккаунтов (`auth_email`); TG-only скрыт на фронте.

```
"""Флаги email-профиля: has_email_auth, auth_email, email_verified, pending_email. Identity — token."""
```

JSON fail → `data = {}`. Нет user → `Unauthorized` (не HTTP 401, тело `ok: False`).

---

## `api_user_profile_change_password` (2627–2651)

**Docstring в коде:** нет. `POST /api/user/profile/change-password`.

```
"""Смена пароля: только `auth_email`; current через `verify_password`; новый — `_validate_password`."""
```

`update_user_password_by_id`. Нет email-auth → отказ.

---

## `api_user_profile_change_email_request` (2655–2689)

**Docstring в коде:** нет. `POST /api/user/profile/change-email/request`.

```
"""Запросить смену email: пароль, `_EMAIL_FORMAT_RE`, не занят другим; `set_pending_email` + код на новый адрес."""
```

Fail письма — `clear_pending_email`. Тот же адрес → ошибка. Чужой `get_user_by_email` → «уже используется».

---

## `api_user_profile_change_email_resend` (2693–2725)

**Docstring в коде:** нет. `POST /api/user/profile/change-email/resend`.

```
"""Повтор кода на `pending_email`; cooldown 60 с → error + `retry_after` (в отличие от auth/resend)."""
```

Нет pending → ошибка.

---

## `api_user_profile_change_email_verify` (2729–2749)

**Docstring в коде:** нет. `POST /api/user/profile/change-email/verify`.

```
"""Подтвердить смену: код + `finalize_pending_email_change`; успех — новый `auth_email`."""
```

---

## `api_user_profile_change_email_cancel` (2753–2764)

**Docstring в коде:** нет. `POST /api/user/profile/change-email/cancel`.

```
"""Снять pending email (`clear_pending_email`); без проверки, был ли он."""
```

---

## `api_sync_tg` (2769–2793)

**Docstring в коде:** нет. `POST /api/auth/sync-tg`. Тело `SyncTgRequest`: token + init_data.

```
"""Привязать email-аккаунт (telegram_id ≤ 0) к реальному TG id из подписанного initData."""
```

Identity сессии — token (`get_user_by_auth_token`). Новый TG — только `validate_telegram_data`. Уже `telegram_id > 0` → «уже привязан». `link_telegram_to_email_user`; не True → `error: str(res)`.

---

## `api_device_tiers` (2797–2813)

**Docstring в коде:** нет. `POST /api/device-tiers`. **Без auth.** Тело: `host_name`.

```
"""Режим устройств хоста: plan/tiers, lock extend, base_device, список tier_id/count/price."""
```

Нет хоста → пустые tiers, mode `plan`. except → `ok: False` с `str(e)`.

---

## `api_get_payment_methods` (2816–2872)

**Docstring в коде:** нет. `POST /api/payment-methods`. `_require_authenticated_user(token, init_data)`.

```
"""Список включённых методов оплаты + балансы; id как у бота (`pay_yookassa`, …)."""
```

| # | Условие в коде | id |
|---|----------------|-----|
| 1 | yookassa shop_id + secret | `pay_yookassa` (лейбл «СБП / карта» если `sbp_enabled`) |
| 2 | platega merchant + secret | `pay_platega` |
| — | `_rollypay_is_enabled` | `pay_rollypay` |
| 3 | cryptobot_token | `pay_cryptobot` |
| 3.1 | иначе heleket merchant+key | `pay_heleket` (взаимоисключение с CryptoBot) |
| 4 | ton wallet + tonapi_key | `pay_tonconnect` |
| 5 | `stars_enabled` | `pay_stars` |
| 6 | `yoomoney_enabled` | `pay_yoomoney` |
| 7 | всегда | `pay_balance` |
| 8 | всегда | `pay_referral_balance` (в коде `#`: UI скроет при нехватке) |

`pay_platega_crypto` в этом списке **нет** — ветка есть в `api_create_payment`.

---

## `api_create_payment` (2876–3332)

**Docstring в коде:** нет. `POST /api/create-payment`. Identity: token/initData. Fulfillment внешних методов — webhook / Stars / `api_verify_platega_payment`; баланс — сразу `process_successful_payment` (PAYMENTS).

```
"""Создать pending покупки/продления/подарка: цена с сервера + промо только для new/extend/gift; инвойс провайдера или списание баланса."""
```

Общее: план из БД; `calculate_webapp_price`; months/duration_days/`_billing_months_for_plan`. `tier_price==0` → сброс `tier_device_count`. Extend + host `device_mode==tiers` + `tier_lock_extend`: если клиент не прислал tier_price — HWID с панели и цена тира.

Промо (в коде `#` 2932–2942): только `action in ("new","extend","gift")`; `check_promo_code_available`; percent или amount; `max(0, round(..., 2))`. Top-up сюда не ходит. Ошибка промо — отказ всего платежа.

Каждая внешняя ветка: UUID `pid`, meta (`user_id` из сессии, plan, action, promo, method), `_create_payload_pending_or_error` (слот промо). Затем ссылка + `_send_telegram_message` с клавиатурой.

| method_id | По коду |
|-----------|---------|
| `pay_yookassa` | SDK create; return_url t.me/bot |
| `pay_platega` | `create_payment(..., method=2)` + `_store_platega_transaction_id` |
| `pay_rollypay` | `_rollypay_api`; store provider id |
| `pay_platega_crypto` | тот же API, method **13** |
| `pay_cryptobot` | `create_cryptobot_api_invoice` из `bot/handlers` (PAYMENTS: не `modules/cryptobot_api`) |
| `pay_heleket` | `create_heleket_payment_request` |
| `pay_yoomoney` | кошелёк ≥11 цифр; min 1 RUB; `_build_yoomoney_link` |
| `pay_tonconnect` | отказ «пока недоступен через WebApp» |
| `pay_stars` | `stars_per_rub`; `_send_invoice_stars`; url `tg://resolve` |
| `pay_balance` | `deduct_from_balance` → `process_successful_payment`; fail/нет токена → `_rollback_internal_payment` |
| `pay_referral_balance` | то же с `deduct_from_referral_balance`; pid `referral_balance:{uid}:{uuid}` |
| иначе | «Метод не поддерживается» |

Внешний except функции → `ok: False` + `details=traceback`.

---

## `_rollback_internal_payment` (3335–3371)

**Docstring в коде:** есть

```
Идемпотентный откат списания Balance/ReferralBalance + лог PAYMENT_ROLLBACK.
```

`refund_payment_once`. except → error-лог, False. Всегда error-лог с `applied=did` (даже успех).

---

## `_platega_method_code_from_settings` (3374–3386)

**Docstring в коде:** нет

```
"""Первый положительный int из `platega_active_methods` (через запятую); иначе 2."""
```

---

## `api_create_topup_payment` (3390–3694)

**Docstring в коде:** есть. `POST /api/create-topup-payment`.

```
Create a balance top-up payment (action=top_up), mirroring the bot TopUpProcess flow.
```

Identity: token/initData. `pay_balance` / `pay_referral_balance` → отказ (нельзя пополнить с внутреннего). Сумма Decimal: >0, ≥10, ≤100000 RUB. Промо **нет**. Pending через `create_payload_pending` (не promo-слот).

| method_id | Отличие от create-payment |
|-----------|---------------------------|
| yookassa | description «Пополнение»; optional receipt из `receipt_email`; metadata только `{payment_id}`; store `yookassa_payment_id` |
| platega | method = `_platega_method_code_from_settings()` |
| rollypay / cryptobot / heleket / yoomoney | action `top_up` |
| tonconnect | отказ |
| stars | нужны `stars_enabled` и ratio > 0; ответ `stars: True` |

---

## `_lte_topup_metadata` (3697–3710)

**Docstring в коде:** есть

```
Метаданные те же, что бот кладёт в pending для process_successful_payment.
```

`action: "lte_gb_topup"` + user/key/package_id/size_gb/price/method/payment_id/host/plan_id. Цена/размер с пакета БД, не с клиента.

---

## `api_lte_packages` (3714–3745)

**Docstring в коде:** есть. `GET /api/lte-packages?key_id=&token=`.

```
Пакеты докупки LTE для ключа владельца. Цена/размер только с сервера.
```

`_owned_lte_key_and_plan`. Пакеты `get_traffic_packages_for_plan(..., pool="lte")`. В ответе ещё `lte_info` / `lte_label` из `_lte_card_state`.

---

## `api_create_lte_topup_payment` (3749–4035)

**Docstring в коде:** есть. `POST /api/create-lte-topup-payment`.

```
Оплата докупки LTE: те же методы, что в боте; цена берётся из пакета в БД.
```

Владение ключом + пакет: тот же plan_id, pool `lte`, active, price > 0. Клиентский price **не** используется.

Баланс / рефбаланс: deduct + `process_successful_payment` + rollback как в create-payment. Остальные: pending + инвойс (yookassa/platega/rollypay/cryptobot/heleket/yoomoney/stars). TON — отказ. YooMoney без проверки min 1 RUB (по коду нет этого if).

---

## `api_apply_promo` (4038–4083)

**Docstring в коде:** есть. `POST /api/apply-promo`.

```
Проверить промокод и посчитать цену со скидкой.

    Промокоды в этом проекте — это ИСКЛЮЧИТЕЛЬНО скидка на покупку/продление
    ключа (см. таблицу `promo_codes`: только discount_percent/discount_amount,
    без какого-либо понятия "начислить на баланс"). Раньше здесь была мёртвая
    ветка на несуществующее поле `promo_type` ("balance"/"universal"), которая
    физически не могла сработать (в БД такой колонки никогда не было — из-за
    этого скидочная ветка тоже была недостижима: promo.get('promo_type')
    всегда возвращал None). Заодно эта мёртвая ветка теоретически позволяла бы
    напрямую зачислять баланс по промокоду, что недопустимо: активация
    промокода должна быть возможна только при покупке/продлении ключа, а не
    при пополнении баланса.
```

`req.price is None` → отказ (нужна покупка/продление). Иначе пересчёт percent/amount; нет обоих → «не даёт скидку». Ответ `promo_type: "discount"` (строка для UI, колонки в БД нет). Identity: token/initData.

---

## `CheckPaymentRequest` (4085–4088)

**Docstring в коде:** нет

```
"""Тело check-payment: payment_id + token/init_data (без user_id)."""
```

Поля: `payment_id: str`, `token`, `init_data`.

---

## `_check_payment_unpaid` (4091–4097)

**Docstring в коде:** есть

```
Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена.

    Один и тот же JSON и 200, чтобы не палить существование чужого payment_id
    через 401/403 или разный ``ok``.
```

Всегда `{"ok": True, "paid": False}`.

---

## `api_check_payment` (4101–4140)

**Docstring в коде:** нет. `POST /api/check-payment`. В коде `#`: подписка логирует тот же payment_id; top_up — новый uuid, поэтому pending `paid` тоже успех; TON сначала пишет pending.

```
"""Свой ли платёж оплачен: чужой/нет сессии → unpaid; иначе transactions paid или pending status paid."""
```

Нет auth → unpaid (не 401). `undefined`/`null`/пусто → `ok: False` Invalid payment_id. `payment_owned_by_user` false → unpaid. Успех может добавить `balance`.

---

## `VerifyPlategaPaymentRequest` (4143–4145)

**Docstring в коде:** нет

```
"""Тело Platega verify: только token/init_data."""
```

---

## `_platega_verify_error` (4148–4149)

**Docstring в коде:** нет

```
"""JSON `{ok: False, error}` с заданным HTTP status (default 400)."""
```

---

## `api_verify_platega_payment` (4153–4365)

**Docstring в коде:** есть. `POST /api/webapp/payments/{payment_id}/verify`. Общий финал с webhook — `platega_fulfillment` (PAYMENTS).

```
Сверить pending Platega-заказ с GET /transaction/{id} и выдать ключ тем же путём, что webhook.
```

Identity: token/initData.

| Строки | Блок | Зачем |
|--------|------|--------|
| 4159–4172 | pid / owner | пустой pid; `payment_owned_by_user` false → 403 «не найден» (API провайдера не зовут) |
| 4174–4189 | уже paid | local paid или нет meta, но есть transaction → idempotent confirmed + key_issued |
| 4191–4209 | meta | нет meta → 404; не Platega → отказ; meta.user_id ≠ сессия → 403 |
| 4211–4220 | нет txid | pending, key_issued False |
| 4222–4244 | GET transaction | нет клиента / except / пусто → 503 |
| 4256–4268 | payload ≠ pid | pending (чужой счёт) |
| 4270–4278 | canceled | `mark_pending_canceled` |
| 4280–4287 | не confirmed | pending |
| 4289–4317 | сумма | got < expected → pending; parse fail → pending |
| 4319–4332 | complete | `complete_pending_platega_payment` None → concurrent idempotent confirmed |
| 4334–4365 | fulfill | `_fulfill_webapp_paid_order` → `process_successful_payment`; except → confirmed, key_issued False |

---

## `KeyActionRequest` (4367–4372)

**Docstring в коде:** нет. В коде `#`: `user_id` ignored; identity from token only.

```
"""key_id + optional host + token/init_data; user_id игнорируется."""
```

---

## `DeleteDeviceRequest` (4374–4380)

**Docstring в коде:** нет. То же `#` про user_id.

```
"""Удаление устройства: key_id, device_id, host, token/init_data."""
```

---

## `CommentRequest` (4382–4387)

**Docstring в коде:** нет. То же `#` про user_id.

```
"""Комментарий ключа: key_id, comment, token/init_data."""
```

---

## `GiftActivateRequest` (4389–4393)

**Docstring в коде:** нет. То же `#` про user_id.

```
"""Активация подарка: gift_code + token/init_data."""
```

---

## `api_user_referral_info` (4397–4429)

**Docstring в коде:** нет. `POST /api/user/referral-info`. Identity: `_require_authenticated_user(data)`.

```
"""Ссылки ref (бот `?start=ref_<uid>`, web `/ref/<uid>`), счётчики, флаг открытой заявки на вывод."""
```

`share_text` из настройки или дефолт. `earned` = `referral_balance_all`, `available` = `referral_balance`.

---

## `_gift_link_row_html` (4432–4448)

**Docstring в коде:** есть

```
Одна строка со ссылкой активации подарка: текст ссылки + копировать + поделиться.
```

`safe_link` = `link.replace("'", "\\'")` для onclick; в HTML текст ссылки вставляется как есть.

---

## `_get_gift_action_block_html` (4451–4478)

**Docstring в коде:** есть

```
Общий блок для неактивированного подарка: обе ссылки активации
    (webapp + Telegram), каждая со своими кнопками копировать/поделиться,
    и отдельно, с явным отступом, кнопка "Активировать себе" — специально
    подальше от остальных кнопок, чтобы не нажать её случайно.
```

Пустая ссылка пропускается. Кнопка `activateOwnGift(gift_code)`.

---

## `_get_gift_fallback_card_html` (4481–4502)

**Docstring в коде:** есть

```
Карточка подарка на случай, если связанный VPN-ключ не найден (например,
    ещё не успел создаться) — но со всеми теми же полями/кнопками, что и у
    полной карточки, чтобы подарок был полноценно управляемым в любом случае.
```

host_name / created_at[:10] + badge + action_block.

---

## `api_user_gifts` (4506–4559)

**Docstring в коде:** нет. `POST /api/user/gifts`. В коде `#`: бейдж «Подарок» не нужен — отдельная вкладка; `link` = webapp или telegram (JS-фолбэк).

```
"""Неактивированные подарки пользователя: ссылки + HTML карточки ключа или fallback."""
```

`get_user_inactive_gifts`. Есть `key_id` и ключ — `_get_key_card_html(..., extra_content_html=action)`; иначе fallback.

---

## `_activate_gift_for_user` (4568–4636)

**Docstring в коде:** есть. Комментарий блока (4561–4567): общая точка для `/api/gift/activate` и pending complete.

```
Активировать подарок `gift_code` для пользователя `user_id`.

    Возвращает структурированный результат:
        {"ok": bool, "status": str, "message": str}

    status ∈ {"activated", "already_activated", "not_found", "expired", "error"}.

    Идемпотентность: если ЭТОТ ЖЕ пользователь уже успешно активировал именно
    этот подарок ранее (например, повторный вызов после сетевого сбоя), метод
    возвращает ok=True/status="already_activated" без создания второго ключа
    и без повторного назначения реферала. Если подарок был активирован ДРУГИМ
    пользователем (обычная гонка/чужой подарок) — ok=False.

    Атомарность/защита от гонки обеспечивается на уровне
    database.activate_user_gift (условный UPDATE + проверка rowcount).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4589–4597 | lookup | нет / activated чужим / activated собой |
| 4599–4605 | expires | isoformat < utcnow → expired; parse fail — игнор |
| 4607–4615 | activate | fail → перечитать; свой already / чужой already / error |
| 4617–4622 | ключ | `update_key` на нового user + новый email, tag="" (не новый VPN-юзер) |
| 4624–4631 | реферал | `set_referred_by_from_gift` от `from_user_id` |

---

## `api_gift_activate` (4641–4656)

**Docstring в коде:** нет. `POST /api/gift/activate`.

```
"""Активировать подарок текущему пользователю (token/initData) через `_activate_gift_for_user`."""
```

Fail → `{ok: False, error: message}`.

---

## `_apply_pending_referral` (4673–4709)

**Docstring в коде:** есть

```
Привязать пользователя к рефереру и, если применимо, выплатить
    существующий стартовый бонус рефереру (тот же механизм и те же настройки,
    что использует бот при обычной регистрации по `/start ref_<id>` —
    см. reward_type == "fixed_start_referrer" в bot/handlers.py).

    Возвращает {"ok": bool, "status": str, "message": str}, где status один из:
    linked, already_linked, self_referral_forbidden, invalid_referrer, not_eligible.
```

`link_referrer_if_eligible(..., max_age_seconds=1800)`. `ok` только при `linked`. Бонус: `claim_referral_start_bonus` + add к балансу реферера. Тексты — `_REFERRAL_LINK_MESSAGES` (4664–4670).

---

## `PendingActionCompleteRequest` (4713–4716)

**Docstring в коде:** нет

```
"""complete pending: pending_token + token/init_data; user_id в модели нет."""
```

---

## `_pending_action_public_info` (4719–4759)

**Docstring в коде:** есть

```
Собрать безопасный (без лишних деталей) ответ для UI по pending action —
    для GET .../info (до входа) и как основа для complete (после входа).
```

consumed → already_used. expires_at < now → expired. gift: нет / activated / иначе valid + host_name (без gift_code). referral: valid, без referrer_id. иной type → invalid.

---

## `api_pending_action_info` (4763–4768)

**Docstring в коде:** нет. `GET /api/webapp/pending-actions/info?pending_token=`. **Без auth.**

```
"""Публичные поля pending action для баннера login.html; нет записи → invalid."""
```

Не отдаёт gift_code / referrer_id (WEBAPP §5.1).

---

## `api_pending_action_complete` (4772–4862)

**Docstring в коде:** есть. `POST /api/webapp/pending-actions/complete`.

```
Единая точка завершения pending action ПОСЛЕ успешной авторизации.

    Безопасность:
      - пользователь определяется ИСКЛЮЧИТЕЛЬНО через _resolve_authenticated_user
        (доверенный persistent auth-токен ИЛИ подписанные Telegram init_data) —
        `user_id` в теле запроса не принимается и не может быть подменён клиентом;
      - gift_code/referrer_id/action_type берутся только из серверной записи
        auth_pending_actions по pending_token — клиент не может их переопределить;
      - claim_pending_action атомарно "забирает" токен ровно один раз, поэтому
        параллельные/повторные запросы не могут применить действие дважды
        (см. database.claim_pending_action, database.activate_user_gift,
        database.link_referrer_if_eligible — везде решение по cursor.rowcount).
```

Бан → access_denied. Свой consumed → already_completed + stored status. Чужой consumed → already_used. Просрочен → expired. `claim` fail → свой already_completed или expired. gift → `_activate_gift_for_user`; referral → `_apply_pending_referral`; иначе invalid. `set_pending_action_result`.

---

## `api_key_devices` (4865–4893)

**Docstring в коде:** нет. `POST /api/key/devices`.

```
"""Список HWID устройств ключа владельца (`get_connected_devices_count`)."""
```

Чужой/нет ключа → «не найден». Нет uuid → нет привязки. host = req или ключ.

---

## `api_key_device_delete` (4896–4925)

**Docstring в коде:** нет. `POST /api/key/device/delete`.

```
"""Удалить одно устройство ключа владельца (`delete_user_device`)."""
```

---

## `api_key_comment` (4928–4947)

**Docstring в коде:** нет. `POST /api/key/comment`.

```
"""Записать комментарий ключа владельца (`update_key_comment`); длина в этом хендлере не режется."""
```

---

## `_support_rate_response` (4949–4953)

**Docstring в коде:** нет

```
"""HTTP 429: «Слишком много запросов. Подождите минуту.»"""
```

---

## `_support_user_rate_limited` (4956–4966)

**Docstring в коде:** нет

```
"""True, если в окне `window` уже ≥ limit хитов ключа `{user_id}:{action}`; иначе записать now."""
```

`_SUPPORT_HITS` + lock. Побочный эффект: при False append (счётчик растёт).

---

## `_support_too_fast` (4969–4979)

**Docstring в коде:** нет

```
"""True, если с прошлого действия user прошло меньше `SUPPORT_MIN_INTERVAL_SECONDS` (1.5)."""
```

Ключ `{uid}:gap` в `_SUPPORT_LAST`. False обновляет last.

---

## `_clip_support_text` (4982–4983)

**Docstring в коде:** нет

```
"""strip и обрезка до max_len; None → пустая строка."""
```

---

## `_tickets_created_today_count` (4986–4993)

**Docstring в коде:** нет

```
"""Сколько тикетов с `created_at`, начинающимся с сегодняшней UTC-даты YYYY-MM-DD."""
```

---

## `_public_ticket_row` (4996–5002)

**Docstring в коде:** нет

```
"""Публичные поля тикета: id, subject (или «без темы»), status, updated_at. Без user_id/форума."""
```

---

## `_public_ticket_messages` (5005–5013)

**Docstring в коде:** нет

```
"""Сообщения тикета через `public_support_message`; sender==note пропускается."""
```

Путь ticket_files наружу не отдаётся (хелпер ticket_media).

---

## `_ticket_owned_by` (5016–5022)

**Docstring в коде:** нет

```
"""True, если ticket.user_id == user_id (int); нет ticket / не int → False."""
```

---

## `_notify_webapp_support` (5025–5077)

**Docstring в коде:** нет

```
"""Уведомить support-бота: тема форума тикета или каждому admin_id с кнопкой admin_reply_dm_."""
```

Нет `support_bot_token` → return. body clip 400 + `html.escape`. Сначала forum_chat_id + thread; fail → админы. `bot.session.close` в finally.

---

## `api_support_status` (5081–5113)

**Docstring в коде:** нет. `POST /api/support/status`.

```
"""Список тикетов + если есть open — сообщения самого нового open."""
```

Identity: token/initData. `has_ticket` True только при open.

---

## `api_support_create` (5117–5161)

**Docstring в коде:** нет. `POST /api/support/create`. `@limiter.limit(SUPPORT_RATE_LIMIT)`.

```
"""Создать тикет: лимит 5/час и 8/сутки; тема 1–64; уже open → отказ; notify WebApp."""
```

`get_or_create_open_ticket`. Пустая тема после clip → ошибка.

---

## `api_support_send` (5165–5206)

**Docstring в коде:** нет. `POST /api/support/send`.

```
"""Сообщение в свой open тикет: gap + 20/мин; текст ≤2000; потолок 200 сообщений."""
```

Чужой/закрыт → «не найден или закрыт». Затем notify.

---

## `api_support_ticket` (5210–5234)

**Docstring в коде:** нет. `POST /api/support/ticket`.

```
"""Свой тикет: поля + messages + список всех тикетов; чужой id → «не найден»."""
```

`_ticket_owned_by`.

---

## `api_support_close` (5239–5268)

**Docstring в коде:** нет. `POST /api/support/close`.

```
"""Закрыть свой тикет; уже closed → `{ok, already}`; notify «закрыт (WebApp)»."""
```

---

## `api_support_ticket_file` (5272–5311)

**Docstring в коде:** есть. `GET /api/support/ticket-file/{message_id}`.

```
Вложение только владельцу. Без сессии и при чужом id — тот же 404, что у несуществующего URL.
```

`_hidden_not_found` (часть 1: стандартный FastAPI 404, без Unauthorized). TTL closed → 404. Path jail: `realpath` должен быть внутри media root + файл. `detect_image_kind` None → 404. Заголовки: nosniff, no-referrer, no-store, noindex.

---

## `api_support_upload` (5316–5372)

**Docstring в коде:** нет. `POST /api/support/upload` (multipart: file, ticket_id, token, caption, init_data).

```
"""Вложение в свой open тикет: jpeg/png/webp/PDF ≤10 МБ (`save_ticket_media_bytes`); caption ≤500."""
```

Чтение чанками 64 KiB, стоп если `> TICKET_MEDIA_MAX_BYTES`. Лимиты upload 8/мин + gap + 200 сообщений. notify «Вложение».

---

## `api_user_status` (5375–5392)

**Docstring в коде:** нет. `GET /api/user-status`. В коде `#`: query token или Authorization.

```
"""Ключи пользователя (`_process_key_data`, newest-first) и balance."""
```

---

## `api_key_rename` (5395–5417)

**Docstring в коде:** нет. `POST /api/key/rename`. Identity: **только token** (`_resolve_user_from_request_token`); бан → Access denied.

```
"""Переименовать свой ключ: пусто → None; иначе ≤30 символов (`update_key_name`)."""
```

`user_id` тела игнорируется (модель части 1).

---

## `api_key_devices_delete_all` (5420–5461)

**Docstring в коде:** нет. `POST /api/key/devices/delete-all`. Тоже только token.

```
"""Снять все HWID своего ключа: список с панели, по одному `delete_user_device`; `{deleted, total}`."""
```

Пустой список → `{ok, deleted: 0}`.

---

## `api_user_transactions` (5464–5515)

**Docstring в коде:** нет. `GET /api/user/transactions`. Identity: token (`_require_authenticated_user`).

```
"""Страница своих транзакций: безопасные поля + русские status_label; без чужих user_id."""
```

`get_transactions_paginated(..., user_id=)`. Labels: pending / paid|success|succeeded|completed / cancelled|canceled.

---

## `api_keys_search` (5518–5542)

**Docstring в коде:** нет. `POST /api/keys/search`. Только token. В коде `#`: тот же renderer, что «Мои ключи».

```
"""Поиск своих ключей по email-подстроке (≥2 символа), до 20, HTML `_get_profile_keys_html`."""
```

---

## `_html_esc` (5544–5546)

**Docstring в коде:** есть

```
Экранировать значение для вставки в HTML-текст или атрибут (CWE-79).
```

`html.escape(..., quote=True)`; None → `""`.

---

## `_public_fallback_response` (5560–5565)

**Docstring в коде:** нет

```
"""HTMLResponse с CSP публичных лендингов (`_PUBLIC_FALLBACK_CSP`: нет default, style unsafe-inline)."""
```

---

## `_parse_public_referrer_id` (5568–5576)

**Docstring в коде:** есть

```
Только положительный int. Невалидный path не должен попадать в HTML/URL.
```

---

## `_safe_public_gift_code` (5579–5583)

**Docstring в коде:** нет

```
"""Код подарка: `_GIFT_CODE_RE` `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`; иначе None."""
```

---

## `_telegram_bot_deeplink` (5586–5592)

**Docstring в коде:** нет

```
"""`https://t.me/<user>` или `?start=<payload>`; пустой username → ''."""
```

---

## `_html_telegram_btn` (5595–5598)

**Docstring в коде:** нет

```
"""`<a class='btn' href=...>` с `_html_esc` на URL и label; нет deeplink → ''."""
```

---

## `_referral_fallback_html` (5601–5630)

**Docstring в коде:** есть

```
Резервная страница рефссылки (реферер не найден/бот не настроен) —
    без единого сценария pending action, просто ссылка в Telegram, как раньше.
```

Имя/note/logo через `_html_esc`. Кнопка только если deeplink и нет error_note; error_note без deeplink — «Бот не настроен».

---

## `web_referral_page` (5634–5677)

**Docstring в коде:** есть. `GET /ref/{referrer_id}`.

```
Публичная реферальная ссылка.

    Раньше эта страница всегда вела только в Telegram (deep link), даже если
    пользователь предпочёл бы войти по email. Теперь: если referrer_id
    настоящий, создаём серверный pending action (единый сценарий — см.
    /api/webapp/pending-actions/*) и ведём на общий вход, где пользователь сам
    выбирает Telegram или email; после успешного входа привязка реферала
    применяется автоматически ровно один раз.
```

В коде `#` 5657: невалидный path не в HTML/deeplink (CWE-79). `#` 5664–5666: существование telegram_id **не** проверяют (оракул известный/неизвестный id); валидация в complete (`invalid_referrer`).

rid None → fallback без start-payload. `create_pending_action("referral", referrer_id=rid)` fail → fallback с `ref_{rid}`. Успех → 302 `/?pending_token=`. except → 500 «Error».

---

## `_gift_fallback_html` (5679–5702)

**Docstring в коде:** есть

```
Резервная страница подарка (не найден/уже активирован) — как и раньше,
    без pending action, потому что действие в этих случаях всё равно не имеет смысла.
```

title/desc/name/logo — `_html_esc`. Нет logo → emoji 🎁.

---

## `web_gift_page` (5706–5770)

**Docstring в коде:** есть. `GET /gift/{gift_code}`.

```
Публичная ссылка активации подарка.

    Раньше уже авторизованный (по cookie/`?token=`) посетитель мог активировать
    подарок прямо со страницы, а неавторизованный — только через Telegram deep
    link. Теперь для валидного, ещё не активированного подарка мы создаём
    серверный pending action и ведём на единый вход (Telegram ИЛИ email);
    страница активации внутри приложения (`/?pending_token=...`) сама решает,
    показывать ли экран входа или сразу применить действие — в зависимости от
    того, авторизован ли пользователь.
    Невалидные случаи (подарок не найден / уже активирован) обрабатываются как
    раньше — без создания pending action, отдельной простой страницей.
```

`_safe_public_gift_code` → lookup. Нет gift / невалидный код — fallback «Активируйте через Telegram» (без различия, чтобы не палить формат). activated / expired — отдельные страницы без pending. `create_pending_action("gift")` → 302 `/?pending_token=` или fallback с TG-кнопкой.

---

## `dynamic_route` (5773–5805)

**Docstring в коде:** нет. `GET /{path_param}`. В коде `#`: невалидный token → login.html; иначе 404.

```
"""Совместимость `/{token=UUID}`: валидный auth token → кабинет; бан → banned; иначе login или 404."""
```

Только если `path_param.startswith("token=")`. User из `get_user_by_auth_token`. Кабинет — `_render_main_page`. Placeholders login — `_process_template_placeholders` с user_id 0. Любой другой path → HTML 404 (не FastAPI HTTPException). except → 500.

---

**Итого записей инвентаря:** 89 (с `validate_telegram_data` по `dynamic_route`).
