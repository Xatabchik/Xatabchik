# Комментарии: `src/shop_bot/webhook_server/app.py` (часть 3)

Хвост `create_webhook_app` (с `_normalize_package_pool`) и модульный `_coerce_checkbox`. Части 1–2 — логин, дашборд, ключи, настройки, боты. Модульного docstring нет.

Инвентарь: `_normalize_package_pool` … `_coerce_checkbox` (после `return flask_app`). Имена — как в `INVENTORY.md`.

Платёжные вебхуки **не** вызывают `process_successful_payment` напрямую: после закрытия pending вызывают `_dispatch_payment_processing(metadata)`, а тот уже ставит `handlers.process_successful_payment` в loop бота или во временный `Bot` в фоне. Ниже «dispatch» — только этот путь. OAuth ЮMoney, debug и конструктор кнопок **не** диспатчат оплату.

Общая модель (PAYMENTS_DOCUMENTATION.md): pending → вебхук/проверка → `find_and_complete_pending_transaction` / аналог → выдача только в `process_successful_payment`. CSRF у колбэков провайдеров снят (`@csrf.exempt`).

---

## `create_webhook_app._normalize_package_pool` (5909–5911)

**Docstring в коде:** есть (дословно):

```
Пул пакета докупки: 'lte' (💰 premium-ноды) или 'main' (основной трафик).
```

`str(raw).strip().lower() == 'lte'` → `'lte'`; иначе `'main'` (в т.ч. пусто / None).

---

## `create_webhook_app.admin_get_traffic_packages_for_plan_json` (5915–5930)

**Docstring в коде:** нет. GET `/admin/plans/<plan_id>/packages`. `@login_required`.

```
"""JSON пакетов ГБ тарифа: query `pool` через `_normalize_package_pool`; ошибка БД → 500."""
```

Поля item: `package_id`, `plan_id`, `size_gb`, `price`, `is_active` (bool). Успех: `{"ok": True, "items": data}`.

---

## `create_webhook_app.add_traffic_package_route` (5934–5954)

**Docstring в коде:** нет. POST `/add-traffic-package`. `@login_required`.

```
"""Создать пакет ГБ: plan_id / size_gb / price из формы; пул обязателен; LTE — только при lte_limit_bytes > 0."""
```

В коде `#`: пул обязателен — без него пакет всегда уходил в `main`, и докупка LTE у пользователей отвечала «пакеты не настроены».

| Строки | Блок | Зачем |
|--------|------|--------|
| 5936–5941 | parse form | KeyError/TypeError/ValueError → flash, redirect `settings_page` tab=hosts |
| 5945–5950 | pool == lte | нет тарифа или `lte_limit_bytes` ≤ 0 → flash, без create |
| 5952–5954 | `create_traffic_package` | flash «LTE-пакет» или «Пакет ГБ» |

---

## `create_webhook_app.update_traffic_package_route` (5958–5981)

**Docstring в коде:** нет. POST `/update-traffic-package/<package_id>`. `@login_required`.

```
"""Частично обновить пакет: size_gb / price / is_active из формы; пустые числа пропускаются."""
```

`is_active` истинно, если строка в `on`/`true`/`1`/`yes`. Нет `kwargs` или `update_traffic_package` False → flash «не найден». Редирект hosts.

---

## `create_webhook_app.toggle_traffic_package_route` (5985–5993)

**Docstring в коде:** нет. POST `/toggle-traffic-package/<package_id>`. `@login_required`.

```
"""Инвертировать `is_active` пакета; нет строки → flash «не найден»."""
```

---

## `create_webhook_app.delete_traffic_package_route` (5997–6000)

**Docstring в коде:** нет. POST `/delete-traffic-package/<package_id>`. `@login_required`.

```
"""Удалить пакет ГБ (`delete_traffic_package`) и вернуться на вкладку hosts."""
```

---

## `create_webhook_app._get_client_ip` (6004–6012)

**Docstring в коде:** есть (дословно):

```
Best-effort client IP (supports reverse proxy via X-Forwarded-For).
```

Первый хоп `X-Forwarded-For` (до запятой); исключение / нет заголовка → `request.remote_addr` или `''`. Вызовы: `_is_ip_allowed`, `ton_webhook_handler`.

---

## `create_webhook_app._is_ip_allowed` (6014–6018)

**Docstring в коде:** нет

```
"""True, если allowlist непуст и `_get_client_ip()` входит в него; пустой список → False."""
```

---

## `create_webhook_app._debug_endpoints_allowed` (6020–6024)

**Docstring в коде:** нет

```
"""True только при `ENABLE_DEBUG_ENDPOINTS` и IP из `DEBUG_IP_ALLOWLIST`."""
```

Нет флага → False. Пустой allowlist → False (через `_is_ip_allowed`).

---

## `create_webhook_app._http_json` (6026–6036)

**Docstring в коде:** есть (дословно):

```
Minimal JSON HTTP client via urllib (avoids extra deps).
```

`body is not None` → JSON + `Content-Type`. `urlopen` timeout default 20. Исключения **не** ловит. Вызовы: `_yookassa_get_payment`, `_cryptobot_get_invoice`, инлайн в `yookassa_webhook_handler`.

---

## `create_webhook_app._yookassa_get_payment` (6038–6051)

**Docstring в коде:** нет

```
"""GET платежа YooKassa v3 по shop_id:secret; нет ключей / ошибка HTTP → None + лог."""
```

По коду: **в этом файле не вызывается** — `yookassa_webhook_handler` повторяет тот же GET сам.

---

## `create_webhook_app._cryptobot_verify_signature` (6053–6066)

**Docstring в коде:** нет

```
"""HMAC-SHA256 сырого тела: secret = SHA256(cryptobot_token); заголовок crypto-pay-api-signature."""
```

Нет токена / нет заголовка → False. Сравнение `compare_digest`. По коду: **в этом файле не вызывается** — хендлер считает HMAC сам.

---

## `create_webhook_app._cryptobot_get_invoice` (6068–6088)

**Docstring в коде:** нет

```
"""GET getInvoices?invoice_ids=…; вернуть первый item из result.items или None."""
```

Нет токена / HTTP-ошибка / не `ok` / пустой items → None. Вызов: `cryptobot_webhook_handler`.

---

## `create_webhook_app._require_ton_webhook_secret` (6090–6102)

**Docstring в коде:** нет

```
"""Сверить секрет TON: настройка `ton_webhook_secret` или config `TON_WEBHOOK_SECRET` с заголовком."""
```

Заголовок: `X-Webhook-Secret` / `X-Ton-Webhook-Secret`, иначе `Authorization: Bearer …`. Пустой секрет → error-лог, False. Пустой header → False. `compare_digest`.

---

## `create_webhook_app.yookassa_webhook_handler` (6106–6213)

**Docstring в коде:** есть (дословно):

```
YooKassa webhook (secure).

Не доверяем входящему payload. Берём provider payment_id из webhook,
затем запрашиваем платеж в YooKassa API по секретному ключу и проверяем:
- status == succeeded
- amount/currency совпадают с pending
- payment_id (internal) ещё не обработан (pending статус + idempotency)
```

POST `/yookassa-webhook`. `@csrf.exempt`. **Auth:** не HMAC тела — сверка через GET `api.yookassa.ru/v3/payments/{id}` с Basic `shop_id:secret_key`. Нет shop_id/secret → 500 Misconfigured. Сбой GET → 502.

| Строки | Блок | Зачем |
|--------|------|--------|
| 6119–6127 | object.id / payment_id | нет id → 400 |
| 6148–6159 | status ≠ succeeded | `canceled` + metadata.payment_id → `cancel_pending_transaction`; иначе ignore; 200 без dispatch |
| 6168–6171 | нет internal payment_id | 200 без dispatch |
| 6180–6198 | pending есть | сумма (`price`/`amount_rub` vs value) и валюта RUB; mismatch / parse fail → 200 без выдачи |
| 6201–6208 | `find_and_complete_pending_transaction` | None (уже обработан / неизвестен) → 200; иначе `payment_method` default `YooKassa`, **`_dispatch_payment_processing` → `process_successful_payment`** |

`_handle_promo_after_payment` здесь нет.

---

## `create_webhook_app.test_webhook` (6217–6223)

**Docstring в коде:** есть (дословно):

```
Тестовый endpoint. В продакшне отключен по умолчанию.
```

GET/POST `/test-webhook`. `@csrf.exempt`. Нет `_debug_endpoints_allowed()` → 404. GET — время; POST — json/form. **Не** dispatch оплаты.

---

## `create_webhook_app.debug_all_requests` (6227–6248)

**Docstring в коде:** есть (дословно):

```
Опасный debug endpoint: возвращает заголовки/куки/данные. В продакшне отключен по умолчанию.
```

`/debug-all` GET/POST/PUT/DELETE. `@csrf.exempt`. Тот же 404 без debug allowlist. В коде `#`: никогда не логируем cookies/authorization в явном виде — в ответе `authorization`/`cookie`/`set-cookie` → `[REDACTED]`. **Не** dispatch оплаты.

---

## `create_webhook_app.yoomoney_webhook_handler` (6252–6355)

**Docstring в коде:** есть (дословно):

```
ЮMoney HTTP уведомление (кнопка/ссылка p2p). Подпись: sha1(notification_type&operation_id&amount&currency&datetime&sender&codepro&notification_secret&label).
```

POST `/yoomoney-webhook`. `@csrf.exempt`.

**Auth / отсев:**

- нет обязательных полей формы (в т.ч. `sha1_hash`) → 400;
- `yoomoney_enabled` выключен → 403;
- пустой `yoomoney_secret` → 403;
- `notification_type` ≠ `p2p-incoming` → 200 ignore;
- `codepro=true` → 200 (тестовый);
- SHA1 строки полей+secret ≠ `sha1_hash` → 403 (`compare_digest`).

`label` = внутренний `payment_id`. Нет pending / метод не YooMoney (`_pending_method_allowed`) / сумма ≠ ожидаемой → 200 без выдачи.

Успех: `find_and_complete_pending_transaction` → `payment_method` default `YooMoney` → **`_dispatch_payment_processing` → `process_successful_payment`**. Промо-хелпер не вызывается.

---

## `create_webhook_app.platega_webhook_handler` (6360–6474)

**Docstring в коде:** есть (дословно):

```
Platega webhook. Авторизация: заголовки X-MerchantId / X-Secret. Payload содержит статус и поле payload (наш payment_id).
```

GET/POST `/platega-webhook`. `@csrf.exempt`. GET — health JSON (`enabled`, если заданы merchant+secret). **Не** dispatch.

**Auth POST:** нет credentials в настройках → 403; `X-MerchantId`/`X-Secret` через `compare_digest` → иначе 401.

`payload` JSON = наш payment_id; `id` = tx провайдера.

| Строки | Блок | Зачем |
|--------|------|--------|
| 6399–6426 | normalize → canceled | не Platega / уже paid / нет txid → 200; GET провайдера `get_transaction_sync`; `remote_is_canceled` → `mark_pending_canceled`; API fail → 503 |
| 6429–6470 | `status_raw == 'CONFIRMED'` | pending + метод Platega/Platega Crypto; сумма через `_extract_platega_webhook_amount` и `_platega_amount_covers_order` (≥ expected); `complete_pending_platega_payment`; `_handle_promo_after_payment` (исключение глотается); **`_dispatch_payment_processing` → `process_successful_payment`** |

Иной статус → 200 без выдачи.

---

## `create_webhook_app.rollypay_webhook_handler` (6478–6625)

**Docstring в коде:** есть (дословно):

```
RollyPay webhook.

HMAC по сырому телу (X-Signature / X-Timestamp), затем GET платежа в API.
Телу колбэка не доверяем: статус, сумма и order_id — только из ответа API.
```

POST `/rollypay-webhook`. `@csrf.exempt`.

**Auth:** нет `rollypay_api_key`/`rollypay_signing_secret` → 503; `verify_webhook_signature(raw, X-Timestamp, X-Signature, secret)` → иначе 403.

Тело читается `get_data(cache=True)` (те же байты для HMAC и JSON).

| Строки | Блок | Зачем |
|--------|------|--------|
| 6507–6545 | chargeback/refund/canceled/expired | pending RollyPay + GET API; remote `paid` — ignore cancel; remote cancel-статус и order_id совпал → `cancel_pending_transaction`; **без** dispatch |
| 6546–6547 | не `payment.paid` | 200 |
| 6554–6621 | paid | pending RollyPay; API status≠paid → cancel если canceled/expired/chargeback; order_id и сумма (quantize 0.01) и валюта RUB с **remote**; `find_and_complete_pending_transaction`; promo (глоток); **`_dispatch_payment_processing` → `process_successful_payment`** |

В metadata кладётся `rollypay_payment_id`.

---

## `create_webhook_app.cryptobot_webhook_handler` (6629–6774)

**Docstring в коде:** есть (дословно):

```
Crypto Pay API webhook (secure).

- Проверяем подпись `crypto-pay-api-signature` (HMAC-SHA256 по сырым байтам тела)
- Дополнительно валидируем invoice через API (getInvoices)
- Idempotency: если payload это internal payment_id → закрываем pending атомарно.
  Если payload старого формата → используем processed_payments ключ `cryptobot:<invoice_id>`.
```

POST `/cryptobot-webhook`. `@csrf.exempt`.

**Auth:** нет `cryptobot_token` → 500; нет заголовка подписи → 403; HMAC (secret = SHA256(token)) ≠ подписи → 403. В коде `#`: `cache=True`, чтобы HMAC и JSON видели одни байты.

`update_type` ≠ `invoice_paid` → 200. Пустой `payload.payload` → 200.

Invoice: `_cryptobot_get_invoice`; если dict и status ≠ `paid` → 200 без выдачи.

**Новый формат** (`:` нет в payload_str): внутренний payment_id. Есть pending и invoice — сверка amount (quantize 0.01) и fiat RUB. Есть pending, но invoice не dict — отказ закрыть pending. `find_and_complete_pending_transaction` → `payment_method` default `CryptoBot`, опционально `cryptobot_invoice_id` → **`_dispatch_payment_processing` → `process_successful_payment`**.

**Legacy** (colon, ≥9 полей): metadata из частей (user_id, months, price, action, key_id, host_name, plan_id, email, payment_method, promo…); `payment_id` = `cryptobot:{invoice_id}`. **Тоже** `_dispatch_payment_processing` → `process_successful_payment`. `find_and_complete_pending_transaction` в этой ветке нет.

---

## `create_webhook_app.heleket_webhook_handler` (6778–6862)

**Docstring в коде:** нет. POST `/heleket-webhook`. `@csrf.exempt`.

```
"""Вебхук Heleket: MD5-подпись тела+api_key; paid/paid_over — сверка суммы pending и dispatch выдачи."""
```

**Auth:** нет `heleket_api_key` → 500; нет `sign` → 400; `sign` снимается из dict (`pop`); MD5(`base64(sorted_json)+api_key`) ≠ sign → 403.

Статус не `paid`/`paid_over` → 200 без выдачи. `order_id`; пусто — legacy `description` JSON `payment_id`. Нет pending / метод не Heleket / сумма (`amount` или `payment_amount`) ≠ expected → 200.

Успех: `find_and_complete_pending_transaction`; `_handle_promo_after_payment` (глоток); `payment_method` default `Heleket`; `heleket_uuid` если есть → **`_dispatch_payment_processing` → `process_successful_payment`**.

По коду: повторного GET к API провайдера нет — доверяет подписанному телу.

---

## `create_webhook_app.ton_webhook_handler` (6866–6920)

**Docstring в коде:** есть (дословно):

```
TonAPI webhook (hardened):
- requires secret header/token (SHOPBOT_TON_WEBHOOK_SECRET or setting ton_webhook_secret)
- optional IP allowlist (SHOPBOT_TON_WEBHOOK_IP_ALLOWLIST)
- amount check + idempotency enforced inside find_and_complete_ton_transaction
```

POST `/ton-webhook`. `@csrf.exempt`.

**Auth:** `_require_ton_webhook_secret()` False → 403. Если env `SHOPBOT_TON_WEBHOOK_IP_ALLOWLIST` непуст и IP не в множестве → 403.

JSON: массивы `in_progress_txs` и `txs`. У каждой tx `in_msg.decoded_comment` = payment_id; `value` наноTON → TON. `find_and_complete_ton_transaction(payment_id, amount_ton)` None → следующая tx. Иначе `payment_method` default `Ton` → **`_dispatch_payment_processing` → `process_successful_payment`**. Всегда 200 в конце (кроме 403/500).

---

## `create_webhook_app._ym_get_redirect_uri` (6926–6934)

**Docstring в коде:** нет

```
"""Redirect URI OAuth ЮMoney: настройка `yoomoney_redirect_uri` или `{url_root}/yoomoney/callback`."""
```

Ошибка `get_setting` → как пустая строка.

---

## `create_webhook_app.yoomoney_connect_route` (6938–6955)

**Docstring в коде:** нет. GET `/yoomoney/connect`. `@login_required`.

```
"""Редирект на OAuth ЮMoney: state в session; scope operation-history/details/account-info."""
```

Нет `yoomoney_client_id` → flash, settings payments. **Не** dispatch оплаты.

---

## `create_webhook_app.yoomoney_callback_route` (6960–7003)

**Docstring в коде:** нет. GET `/yoomoney/callback`. `@csrf.exempt`, `@login_required`.

```
"""Обменять OAuth code на access_token; проверить state; сохранить `yoomoney_api_token`."""
```

`session.pop('yoomoney_oauth_state')` vs `?state` через `compare_digest`; нет/mismatch → flash danger. Нет `code` → flash. POST `yoomoney.ru/oauth/token`; нет `access_token` → flash payload. **Не** dispatch оплаты.

---

## `create_webhook_app.yoomoney_check_route` (7007–7047)

**Docstring в коде:** нет. GET/POST `/yoomoney/check`. `@login_required`.

```
"""Проверить токен: POST account-info и operation-history; flash кошелёк или HTTP/scope ошибку."""
```

Нет `yoomoney_api_token` → warning. account-info ≠ 200 → danger + WWW-Authenticate. **Не** dispatch оплаты.

---

## `create_webhook_app.get_button_configs_api` (7053–7061)

**Docstring в коде:** есть (дословно):

```
Get button configurations for a specific menu type (including inactive for admin)
```

GET `/api/button-configs/<menu_type>`. `@login_required`, `@csrf.exempt`. В коде `#`: для конструктора возвращаем **все** кнопки (`include_inactive=True`). Исключение → 500 JSON.

---

## `create_webhook_app.create_button_config_api` (7066–7093)

**Docstring в коде:** есть (дословно):

```
Create a new button configuration
```

POST `/api/button-configs`. `@login_required`, `@csrf.exempt`. Обязательны `menu_type`, `button_id`, `text`; иначе 400. Опционально callback_data, url, row/column_position (default 0), button_width (default 1), metadata. `create_button_config` False → 500.

---

## `create_webhook_app.update_button_config_api` (7098–7125)

**Docstring в коде:** есть (дословно):

```
Update an existing button configuration
```

PUT `/api/button-configs/<button_id>`. `@login_required`, `@csrf.exempt`. Поля через `.get` (могут быть None). False → 500.

---

## `create_webhook_app.delete_button_config_api` (7130–7140)

**Docstring в коде:** есть (дословно):

```
Delete a button configuration
```

DELETE `/api/button-configs/<button_id>`. `@login_required`, `@csrf.exempt`. `delete_button_config` False → 500.

---

## `create_webhook_app.reorder_button_configs_api` (7145–7163)

**Docstring в коде:** есть (дословно):

```
Reorder button configurations for a menu type
```

POST `/api/button-configs/<menu_type>/reorder`. `@login_required`, `@csrf.exempt`. Тело: `button_orders` (default `[]`). `reorder_button_configs` False → 500.

---

## `create_webhook_app._franchise_db_connect` (7169–7172)

**Docstring в коде:** нет

```
"""sqlite3.connect(rw_repo.DB_FILE) с row_factory=Row."""
```

---

## `create_webhook_app._franchise_totals` (7174–7232)

**Docstring в коде:** нет

```
"""Агрегаты франшизы: боты, пользователи, комиссии, заявки на вывод, available_total."""
```

В коде `#`: alias `pending_withdraw_sum` для шаблонов. Исключение глотается — нули из начального dict. `available_total` = max(0, commission_total − requested_withdraw); requested = сумма заявок pending/approved/paid.

---

## `create_webhook_app._franchise_list_bots` (7234–7291)

**Docstring в коде:** нет

```
"""До 300 клонов из managed_bots + подзапросы статистики; поиск по id или username."""
```

Цифровой `q` (без `@`) — WHERE id / telegram_bot_user_id / owner_telegram_id. Иначе LIKE по username. `token` из результата убирается; `token_masked` = «задан» или `''`. `available` = commission − requested. Ошибка SQL → `[]`.

---

## `create_webhook_app._franchise_get_bot` (7293–7307)

**Docstring в коде:** нет

```
"""Одна строка managed_bots по id; token снят, is_active bool; нет/ошибка → None."""
```

---

## `create_webhook_app._franchise_bot_stats` (7309–7358)

**Docstring в коде:** нет

```
"""Счётчики одного бота: activity, partner_commissions, withdraw pending/requested, available."""
```

Исключение глотается — нули. `available` = max(0, commission − requested).

---

## `create_webhook_app.franchise_page` (7362–7367)

**Docstring в коде:** нет. GET `/franchise`. `@login_required`.

```
"""Список клонов и totals; query `q`; шаблон franchise.html + get_common_template_data."""
```

---

## `create_webhook_app.franchise_bot_page` (7371–7433)

**Docstring в коде:** нет. GET `/franchise/bot/<bot_id>`. `@login_required`.

```
"""Карточка клона: stats, до 200 activity/commissions/withdraws; нет бота → flash и список."""
```

Шаблон `franchise_bot.html`; в контекст и `withdraw_requests`, и `withdraws` (один список).

---

## `create_webhook_app.franchise_toggle_bot_route` (7437–7462)

**Docstring в коде:** нет. POST `/franchise/bot/<bot_id>/toggle`. `@login_required`.

```
"""Инвертировать managed_bots.is_active и на loop root-бота start_bot/stop_bot."""
```

Нет строки → flash, список. Сбой SQL → danger. `_run_on_root_bot_loop`: `v==1` → `svc.start_bot`, иначе `stop_bot`; сбой runtime — warning, flash всё равно «обновлён».

---

## `create_webhook_app.franchise_delete_bot_route` (7466–7489)

**Docstring в коде:** нет. POST `/franchise/bot/<bot_id>/delete`. `@login_required`.

```
"""Остановить клон на loop, затем `rw_repo.delete_managed_bot`; нет строки / False → flash."""
```

Flash успеха: «Активность клона очищена. Одобренные/выплаченные заявки на вывод сохранены.» (текст ответа, не проверка SQL здесь).

---

## `create_webhook_app.franchise_withdraw_status_route` (7493–7512)

**Docstring в коде:** нет. POST `/franchise/withdraw/<req_id>/status`. `@login_required`.

```
"""Сменить status заявки вывода на pending/approved/paid/rejected; rowcount 0 → не найдена."""
```

Иной status → warning, без UPDATE.

---

## `create_webhook_app.button_constructor_page` (7516–7519)

**Docstring в коде:** есть (дословно):

```
Button constructor page
```

GET `/button-constructor`. `@login_required`. `button_constructor.html` + `get_common_template_data`. После этого `create_webhook_app` делает `return flask_app`.

---

## `_coerce_checkbox` (7526–7528)

**Docstring в коде:** нет. Модульная функция **снаружи** `create_webhook_app`.

```
"""Строка чекбокса → 'true'/'false': on/true/1/yes, иначе false."""
```

В коде `#`: HTML checkbox returns "on" when checked; hidden fallback sends "off" always.

По коду / каталогу функций: из прод-кода **не вызывается**.

---

**Записей инвентаря в этом файле: 44.**
