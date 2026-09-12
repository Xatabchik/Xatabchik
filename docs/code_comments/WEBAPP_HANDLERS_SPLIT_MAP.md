# Карта разделения `webapp/handlers.py`

Файл разделён на доменные модули пакета `src/shop_bot/webapp/web_router/`.
`handlers.py` остался фасадом и ре-экспортирует прежний публичный API целиком,
поэтому ни `docker-compose.yml` (`uvicorn shop_bot.webapp.handlers:app`), ни
`tests/conftest.py`, ни двадцать пять файлов тестов не изменились.

Особенность этого файла, в отличие от `bot/admin_handlers.py`: все 211 определений
уже лежали на **уровне модуля**, а не внутри фабрики, поэтому переносить их
можно было как есть — без дедента и без обёрток `register_*`. Зато появилась
другая забота: в FastAPI выбирается **первый совпавший** маршрут, значит
порядок регистрации значим, а задаёт его порядок импорта модулей.

Столбец «строки» — расположение в исходном `handlers.py` до разделения, чтобы
перенос можно было сверить с `INVENTORY.md` и `shop_bot_webapp_handlers_part*.md`.

## Почему порядок импорта задан в `__init__.py`

Маршрут регистрируется декоратором `@app.…` в момент импорта модуля, а
`@app.get('/{path_param}')` в `public_pages` — catch-all: он совпадёт с любым
путём, который не разобрали раньше. Значит он обязан остаться последним.

Порядок задан в `web_router/__init__.py` и только там. Python исполняет
`__init__` пакета раньше любого его подмодуля, поэтому прямой импорт
`web_router.support` сначала прогонит весь список импортов из `__init__` и
получит тот же порядок, что запуск через `uvicorn` или через `conftest.py`.
Это закреплено тестом `test_route_order_is_the_same_for_every_entry_point`,
который считает порядок в трёх отдельных процессах.

Группировка подобрана так, чтобы все 23 участка подряд идущих маршрутов
исходника остались неразрывными: тогда порядок импорта модулей воспроизводит
порядок маршрутов исходника, и никакой пересборки маршрутов не требуется.

## Как имена находят друг друга

До разделения всё лежало в одном пространстве имён, и функции обращались к
соседям просто по имени. После разделения это держится на трёх механизмах:

* `_link_namespace()` после импорта всех модулей раскладывает экспортируемые
  имена каждого модуля по остальным;
* `broadcast()` разносит **внешнюю** запись атрибута фасада по доменным
  модулям — это то, чем пользуется `monkeypatch` в тестах;
* имена, нужные уже на этапе импорта (декораторы, аннотации, значения по
  умолчанию), импортируются значением из `_core`, `_app` и `models`. Эти три
  модуля маршрутов не регистрируют, поэтому их ранний импорт порядок
  маршрутов не сдвигает.

PEP 562 (`__getattr__` модуля) здесь не помогает: обращение к глобальному
имени внутри функции компилируется в `LOAD_GLOBAL` и до `__getattr__` не
доходит.

## Сводка

| Модуль | Назначение | Определений | Строк | Маршрутов |
| --- | --- | ---: | ---: | ---: |
| `web_router/auth_email.py` | Регистрация, подтверждение, вход и сброс пароля по email | 8 | 267 | 7 |
| `web_router/support.py` | Поддержка: тикеты, сообщения, вложения, лимиты | 16 | 486 | 7 |
| `web_router/profile.py` | Профиль: смена пароля и адреса почты | 6 | 192 | 6 |
| `web_router/key_actions.py` | Статус пользователя, переименование ключа, транзакции, поиск | 5 | 210 | 5 |
| `web_router/referral_payouts.py` | Реквизиты для выплат по реферальной программе | 4 | 134 | 4 |
| `web_router/auth_telegram.py` | Проверка подписи Telegram `initData` и вход через Telegram | 6 | 243 | 4 |
| `web_router/key_devices.py` | Устройства ключа и комментарий к ключу | 3 | 120 | 3 |
| `web_router/public_pages.py` | Публичные страницы `/ref` и `/gift` и catch-all `/{path_param}` | 11 | 299 | 3 |
| `web_router/ticket_files_guard.py` | Запрет прямого доступа к каталогу вложений тикетов | 1 | 29 | 2 |
| `web_router/referral_withdrawals.py` | Заявки на вывод реферального баланса | 2 | 110 | 2 |
| `web_router/account_sync.py` | Привязка Telegram-аккаунта и тарифы устройств | 2 | 82 | 2 |
| `web_router/payments_create.py` | Способы оплаты и создание платежа за ключ | 4 | 637 | 2 |
| `web_router/payments_lte.py` | Докупка LTE-трафика | 3 | 398 | 2 |
| `web_router/gifts.py` | Подарочные ключи: карточки, список, активация | 6 | 254 | 2 |
| `web_router/pending_actions.py` | Отложенные действия: подарок и реферальная ссылка | 4 | 217 | 2 |
| `web_router/key_auto_renew.py` | Включение и отключение автопродления ключа | 1 | 51 | 1 |
| `web_router/render_page.py` | Сборка главной страницы Mini App и корневой маршрут `/` | 3 | 374 | 1 |
| `web_router/payments_topup.py` | Пополнение баланса | 1 | 336 | 1 |
| `web_router/payments_promo.py` | Применение промокода | 1 | 76 | 1 |
| `web_router/payments_check.py` | Проверка состояния платежа | 2 | 85 | 1 |
| `web_router/payments_platega.py` | Верификация платежа Platega | 2 | 264 | 1 |
| `web_router/referral_info.py` | Сводка по реферальной программе для пользователя | 1 | 63 | 1 |
| `web_router/_core.py` | Состояние уровня модуля: токены, лимитеры, счётчики попыток, регулярки | 29 | 104 | 0 |
| `web_router/payments_common.py` | Общая платёжная обвязка: цена, чек, отправка сообщений и инвойсов | 15 | 269 | 0 |
| `web_router/auth_limits.py` | Лимит попыток email-аутентификации в разрезе адреса | 3 | 55 | 0 |
| `web_router/auth_session.py` | Разрешение пользователя по токену или `initData` запроса | 4 | 97 | 0 |
| `web_router/referral_settings.py` | Чтение настроек реферальной программы | 2 | 34 | 0 |
| `web_router/_app.py` | Создание `FastAPI`, middleware без кеша, монтирование `/uploads` и иконок | 10 | 66 | 0 |
| `web_router/render_keys.py` | Форматирование и HTML-карточки ключей и профиля | 19 | 902 | 0 |
| `web_router/render_plans.py` | HTML-сетка тарифов и серверов | 5 | 178 | 0 |
| `web_router/models.py` | Pydantic-модели тел запросов | 29 | 235 | 0 |
| `web_router/auth_password.py` | Проверка пароля и кода сброса | 3 | 56 | 0 |
| **итого** | | **211** | **6923** | **60** |

Фасад `handlers.py` — 154 строки вместо 5828.

### Про два разных числа маршрутов

В столбце «маршрутов» посчитаны только эндпоинты приложения — те 60 маршрутов,
что объявлены декораторами `@app.get`/`@app.post`/…, то есть `APIRoute`. Функций
при этом 59: `_block_ticket_files_dir` в `ticket_files_guard` несёт два
декоратора сразу.

В снимке `app.routes`, по которому сверялось разделение, маршрутов **66**:
к тем же 60 эндпоинтам добавляются четыре служебных маршрута, которые FastAPI
создаёт сам (`/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`), и два
монтирования статики из `_app.py` (`/module/ico`, `/uploads`).

Оба числа относятся к одному и тому же приложению и до разделения были такими
же: 60 эндпоинтов и 66 записей в `app.routes`.

## Что изменилось в тексте определений

Перенос дословный, кроме двух мест, и оба вынуждены самим фактом переезда:

1. Пять выражений `os.path.dirname(__file__)` получили ещё один `dirname`:
   файл переехал на уровень глубже, а каталоги шаблонов и статики остались в
   `webapp/`. Это `ico_dir`, `uploads_dir`, `_render_main_page`, `index` и
   `dynamic_route`; закреплено тестом
   `test_static_paths_still_resolve_to_the_webapp_directory`.
2. Имя логгера прибито строкой вместо `__name__`, чтобы записи в логах
   остались от `shop_bot.webapp.handlers`.

## Известная особенность исходника

`process_successful_payment` определён на строке 324 и тут же затирается
импортом на строке 381 (`from shop_bot.bot.handlers import ...`). То есть
определение — мёртвый код, а работает функция бота. Разделение это
воспроизводит: содержимое каждого модуля выложено в порядке строк исходника,
поэтому импорт побеждает так же, как раньше. Закреплено тестом
`test_shadowing_of_process_successful_payment_is_preserved`.

## Определение → модуль

| Строки | Определение | Модуль | Маршрут |
| --- | --- | --- | --- |
| 65 | `logger` | `_core` |  |
| 68–76 | `_create_payload_pending_or_error` | `payments_common` |  |
| 79–103 | `_yookassa_receipt` | `payments_common` |  |
| 107 | `TEMP_AUTH_TOKENS` | `_core` |  |
| 110 | `TELEGRAM_INIT_DATA_MAX_AGE_SECONDS` | `_core` |  |
| 113 | `limiter` | `_core` |  |
| 114 | `AUTH_RATE_LIMIT` | `_core` |  |
| 115 | `SUPPORT_RATE_LIMIT` | `_core` |  |
| 116 | `SUPPORT_TEXT_MAX_LEN` | `_core` |  |
| 117 | `SUPPORT_CAPTION_MAX_LEN` | `_core` |  |
| 118 | `SUPPORT_MAX_MESSAGES_PER_TICKET` | `_core` |  |
| 119 | `SUPPORT_CREATE_DAILY_MAX` | `_core` |  |
| 120 | `SUPPORT_SEND_PER_MINUTE` | `_core` |  |
| 121 | `SUPPORT_UPLOAD_PER_MINUTE` | `_core` |  |
| 122 | `SUPPORT_CREATE_PER_HOUR` | `_core` |  |
| 123 | `SUPPORT_MIN_INTERVAL_SECONDS` | `_core` |  |
| 124 | `_SUPPORT_HITS` | `_core` |  |
| 125 | `_SUPPORT_LAST` | `_core` |  |
| 126 | `_SUPPORT_HITS_LOCK` | `_core` |  |
| 132 | `EMAIL_AUTH_PER_EMAIL_LIMIT` | `_core` |  |
| 133 | `EMAIL_AUTH_PER_EMAIL_WINDOW_SECONDS` | `_core` |  |
| 134 | `_EMAIL_AUTH_HITS` | `_core` |  |
| 135 | `_EMAIL_AUTH_HITS_LOCK` | `_core` |  |
| 138–145 | `_email_auth_rate_limit_response` | `auth_limits` |  |
| 148–163 | `_email_auth_rate_limited` | `auth_limits` |  |
| 166–169 | `_reject_if_email_auth_rate_limited` | `auth_limits` |  |
| 172–192 | `_resolve_user_from_request_token` | `auth_session` |  |
| 195–216 | `_resolve_authenticated_user` | `auth_session` |  |
| 219–220 | `_unauthorized` | `auth_session` |  |
| 223–243 | `_require_authenticated_user` | `auth_session` |  |
| 246–248 | `_ref_setting_is_true` | `referral_settings` |  |
| 251–259 | `_ref_method_type_enabled` | `referral_settings` |  |
| 263–290 | `get_transaction_comment` | `payments_common` |  |
| 292–317 | `calculate_webapp_price` | `payments_common` |  |
| 320–322 | `notify_admin_of_purchase` | `payments_common` |  |
| 324–326 | `process_successful_payment` | `payments_common` |  |
| 328–342 | `_send_telegram_message` | `payments_common` |  |
| 344–363 | `_send_invoice_stars` | `payments_common` |  |
| 385–390 | `_platega_api` | `payments_common` |  |
| 393–401 | `_store_platega_transaction_id` | `payments_common` |  |
| 404–408 | `_rollypay_is_enabled` | `payments_common` |  |
| 411–415 | `_rollypay_api` | `payments_common` |  |
| 418–426 | `_store_rollypay_payment_id` | `payments_common` |  |
| 429–444 | `_fulfill_webapp_paid_order` | `payments_common` |  |
| 451–463 | `_build_yoomoney_link` | `payments_common` |  |
| 465 | `app` | `_app` |  |
| 466 | `app.state.limiter` | `_app` |  |
| 467 | код уровня модуля | `_app` |  |
| 469–477 | `_webapp_no_cache_middleware` | `_app` |  |
| 479 | `ico_dir` | `_app` |  |
| 480–481 | код уровня модуля | `_app` |  |
| 483 | `uploads_dir` | `_app` |  |
| 484 | код уровня модуля | `_app` |  |
| 485 | код уровня модуля | `_app` |  |
| 488–490 | `_hidden_not_found` | `_app` |  |
| 493–497 | `_block_ticket_files_dir` | `ticket_files_guard` | `api_route '/ticket_files'`<br>`api_route '/ticket_files/{rest:path}'` |
| 501–522 | `api_referral_payout_methods_list` | `referral_payouts` | `post '/api/referral/payout-methods/list'` |
| 526–551 | `api_referral_payout_methods_add` | `referral_payouts` | `post '/api/referral/payout-methods/add'` |
| 554–581 | `api_referral_available_method_types` | `referral_payouts` | `post '/api/referral/available-method-types'` |
| 584–603 | `api_referral_payout_methods_delete` | `referral_payouts` | `post '/api/referral/payout-methods/delete'` |
| 606–627 | `api_key_auto_renew` | `key_auto_renew` | `post '/api/key/auto-renew'` |
| 631–676 | `api_referral_request_withdraw` | `referral_withdrawals` | `post '/api/referral/request-withdrawal'` |
| 680–712 | `api_referral_list_withdrawals` | `referral_withdrawals` | `post '/api/referral/withdrawals'` |
| 715–737 | `_format_remaining_details` | `render_keys` |  |
| 739–754 | `_format_bytes` | `render_keys` |  |
| 756–804 | `_process_template_placeholders` | `render_keys` |  |
| 806–813 | `_format_bytes_gb` | `render_keys` |  |
| 816–821 | `_format_gb_amount` | `render_keys` |  |
| 824–843 | `_is_key_without_billing_plan` | `render_keys` |  |
| 846–870 | `_resolve_plan_id_for_key` | `render_keys` |  |
| 873–923 | `_lte_card_state` | `render_keys` |  |
| 926–937 | `_owned_lte_key_and_plan` | `render_keys` |  |
| 940–1070 | `_process_key_data` | `render_keys` |  |
| 1072–1117 | `_get_key_html` | `render_keys` |  |
| 1119–1248 | `_get_profile_card_html` | `render_keys` |  |
| 1250–1379 | `_get_key_card_html` | `render_keys` |  |
| 1381–1392 | `_key_created_sort_tuple` | `render_keys` |  |
| 1395–1396 | `_sort_keys_newest_first` | `render_keys` |  |
| 1399–1406 | `_get_profile_keys_html` | `render_keys` |  |
| 1408–1492 | `_get_setup_keys_html` | `render_keys` |  |
| 1494–1540 | `_get_renew_keys_html` | `render_keys` |  |
| 1542–1553 | `_get_no_key_html` | `render_keys` |  |
| 1557–1576 | `_duration_label` | `render_plans` |  |
| 1579–1590 | `_days_from_plan` | `render_plans` |  |
| 1593–1594 | `_billing_months_for_plan` | `render_plans` |  |
| 1597–1665 | `_build_plans_grid_html` | `render_plans` |  |
| 1668–1711 | `_get_servers_and_plans_html` | `render_plans` |  |
| 1714–1793 | `_render_banned_page` | `render_page` |  |
| 1796–1994 | `_render_main_page` | `render_page` |  |
| 1997–2038 | `index` | `render_page` | `get '/'` |
| 2042–2045 | `SupportStatusRequest` | `models` |  |
| 2047–2051 | `SupportTicketCreateRequest` | `models` |  |
| 2053–2058 | `SupportMessageSendRequest` | `models` |  |
| 2060–2064 | `SupportTicketRequest` | `models` |  |
| 2066–2069 | `PaymentMethodsRequest` | `models` |  |
| 2071–2072 | `TokenRequest` | `models` |  |
| 2074–2076 | `TelegramDirectAuthRequest` | `models` |  |
| 2078–2080 | `EmailAuthRequest` | `models` |  |
| 2082–2084 | `EmailVerifyRequest` | `models` |  |
| 2086–2087 | `EmailResendRequest` | `models` |  |
| 2089–2090 | `PasswordResetRequest` | `models` |  |
| 2092–2094 | `PasswordResetCheckRequest` | `models` |  |
| 2096–2099 | `PasswordResetVerifyRequest` | `models` |  |
| 2103 | `PASSWORD_RESET_TOKENS` | `_core` |  |
| 2104 | `PASSWORD_RESET_TTL_SECONDS` | `_core` |  |
| 2107–2108 | `_hash_password_reset_code` | `auth_password` |  |
| 2111–2118 | `_password_reset_code_matches` | `auth_password` |  |
| 2120–2122 | `SyncTgRequest` | `models` |  |
| 2125–2126 | `DeviceTiersRequest` | `models` |  |
| 2128–2139 | `CreatePaymentRequest` | `models` |  |
| 2141–2146 | `CreateTopUpPaymentRequest` | `models` |  |
| 2148–2154 | `CreateLteTopUpPaymentRequest` | `models` |  |
| 2156–2162 | `ApplyPromoRequest` | `models` |  |
| 2164–2168 | `RenameKeyRequest` | `models` |  |
| 2170–2174 | `DeleteAllDevicesRequest` | `models` |  |
| 2176–2179 | `SearchKeysRequest` | `models` |  |
| 2184–2250 | `validate_telegram_data` | `auth_telegram` |  |
| 2253–2267 | `_issue_persistent_token_for_telegram_user` | `auth_telegram` |  |
| 2270–2283 | `api_request_auth_token` | `auth_telegram` | `get '/api/auth/request-token'` |
| 2285–2325 | `api_check_auth_token` | `auth_telegram` | `get '/api/auth/check-token/{token}'` |
| 2327–2344 | `api_create_token` | `auth_telegram` | `post '/api/auth/token'` |
| 2347–2382 | `api_telegram_direct_auth` | `auth_telegram` | `post '/api/auth/telegram-direct'` |
| 2384–2403 | `_validate_password` | `auth_password` |  |
| 2405 | `EMAIL_RESEND_COOLDOWN_SECONDS` | `_core` |  |
| 2406 | `EMAIL_CODE_TTL_SECONDS` | `_core` |  |
| 2409–2438 | `_issue_email_verification_code` | `auth_email` |  |
| 2441–2468 | `api_email_register` | `auth_email` | `post '/api/auth/email/register'` |
| 2470–2489 | `api_email_verify` | `auth_email` | `post '/api/auth/email/verify'` |
| 2491–2516 | `api_email_resend` | `auth_email` | `post '/api/auth/email/resend'` |
| 2518–2537 | `api_email_login` | `auth_email` | `post '/api/auth/email/login'` |
| 2539–2574 | `api_email_reset_request` | `auth_email` | `post '/api/auth/email/reset/request'` |
| 2576–2594 | `api_email_reset_check` | `auth_email` | `post '/api/auth/email/reset/check'` |
| 2596–2623 | `api_email_reset_verify` | `auth_email` | `post '/api/auth/email/reset/verify'` |
| 2631 | `_EMAIL_FORMAT_RE` | `_core` |  |
| 2634–2651 | `api_user_profile_info` | `profile` | `post '/api/user/profile-info'` |
| 2654–2679 | `api_user_profile_change_password` | `profile` | `post '/api/user/profile/change-password'` |
| 2682–2717 | `api_user_profile_change_email_request` | `profile` | `post '/api/user/profile/change-email/request'` |
| 2720–2753 | `api_user_profile_change_email_resend` | `profile` | `post '/api/user/profile/change-email/resend'` |
| 2756–2777 | `api_user_profile_change_email_verify` | `profile` | `post '/api/user/profile/change-email/verify'` |
| 2780–2792 | `api_user_profile_change_email_cancel` | `profile` | `post '/api/user/profile/change-email/cancel'` |
| 2795–2821 | `api_sync_tg` | `account_sync` | `post '/api/auth/sync-tg'` |
| 2824–2841 | `api_device_tiers` | `account_sync` | `post '/api/device-tiers'` |
| 2843–2900 | `api_get_payment_methods` | `payments_create` | `post '/api/payment-methods'` |
| 2903–3364 | `api_create_payment` | `payments_create` | `post '/api/create-payment'` |
| 3367–3403 | `_rollback_internal_payment` | `payments_create` |  |
| 3406–3418 | `_platega_method_code_from_settings` | `payments_create` |  |
| 3421–3713 | `api_create_topup_payment` | `payments_topup` | `post '/api/create-topup-payment'` |
| 3716–3729 | `_lte_topup_metadata` | `payments_lte` |  |
| 3732–3764 | `api_lte_packages` | `payments_lte` | `get '/api/lte-packages'` |
| 3767–4058 | `api_create_lte_topup_payment` | `payments_lte` | `post '/api/create-lte-topup-payment'` |
| 4060–4106 | `api_apply_promo` | `payments_promo` | `post '/api/apply-promo'` |
| 4108–4111 | `CheckPaymentRequest` | `models` |  |
| 4114–4120 | `_check_payment_unpaid` | `payments_check` |  |
| 4123–4163 | `api_check_payment` | `payments_check` | `post '/api/check-payment'` |
| 4166–4168 | `VerifyPlategaPaymentRequest` | `models` |  |
| 4171–4172 | `_platega_verify_error` | `payments_platega` |  |
| 4175–4388 | `api_verify_platega_payment` | `payments_platega` | `post '/api/webapp/payments/{payment_id}/verify'` |
| 4390–4395 | `KeyActionRequest` | `models` |  |
| 4397–4403 | `DeleteDeviceRequest` | `models` |  |
| 4405–4410 | `CommentRequest` | `models` |  |
| 4412–4416 | `GiftActivateRequest` | `models` |  |
| 4419–4452 | `api_user_referral_info` | `referral_info` | `post '/api/user/referral-info'` |
| 4455–4471 | `_gift_link_row_html` | `gifts` |  |
| 4474–4501 | `_get_gift_action_block_html` | `gifts` |  |
| 4504–4525 | `_get_gift_fallback_card_html` | `gifts` |  |
| 4528–4582 | `api_user_gifts` | `gifts` | `post '/api/user/gifts'` |
| 4591–4659 | `_activate_gift_for_user` | `gifts` |  |
| 4663–4679 | `api_gift_activate` | `gifts` | `post '/api/gift/activate'` |
| 4687–4693 | `_REFERRAL_LINK_MESSAGES` | `_core` |  |
| 4696–4732 | `_apply_pending_referral` | `pending_actions` |  |
| 4736–4739 | `PendingActionCompleteRequest` | `models` |  |
| 4742–4782 | `_pending_action_public_info` | `pending_actions` |  |
| 4785–4791 | `api_pending_action_info` | `pending_actions` | `get '/api/webapp/pending-actions/info'` |
| 4794–4885 | `api_pending_action_complete` | `pending_actions` | `post '/api/webapp/pending-actions/complete'` |
| 4887–4916 | `api_key_devices` | `key_devices` | `post '/api/key/devices'` |
| 4918–4948 | `api_key_device_delete` | `key_devices` | `post '/api/key/device/delete'` |
| 4950–4970 | `api_key_comment` | `key_devices` | `post '/api/key/comment'` |
| 4972–4976 | `_support_rate_response` | `support` |  |
| 4979–4989 | `_support_user_rate_limited` | `support` |  |
| 4992–5002 | `_support_too_fast` | `support` |  |
| 5005–5006 | `_clip_support_text` | `support` |  |
| 5009–5016 | `_tickets_created_today_count` | `support` |  |
| 5019–5025 | `_public_ticket_row` | `support` |  |
| 5028–5036 | `_public_ticket_messages` | `support` |  |
| 5039–5045 | `_ticket_owned_by` | `support` |  |
| 5048–5100 | `_notify_webapp_support` | `support` |  |
| 5103–5136 | `api_support_status` | `support` | `post '/api/support/status'` |
| 5138–5184 | `api_support_create` | `support` | `post '/api/support/create'` |
| 5186–5229 | `api_support_send` | `support` | `post '/api/support/send'` |
| 5232–5257 | `api_support_ticket` | `support` | `post '/api/support/ticket'` |
| 5260–5291 | `api_support_close` | `support` | `post '/api/support/close'` |
| 5294–5334 | `api_support_ticket_file` | `support` | `get '/api/support/ticket-file/{message_id}'` |
| 5337–5395 | `api_support_upload` | `support` | `post '/api/support/upload'` |
| 5397–5415 | `api_user_status` | `key_actions` | `get '/api/user-status'` |
| 5417–5440 | `api_key_rename` | `key_actions` | `post '/api/key/rename'` |
| 5442–5484 | `api_key_devices_delete_all` | `key_actions` | `post '/api/key/devices/delete-all'` |
| 5486–5538 | `api_user_transactions` | `key_actions` | `get '/api/user/transactions'` |
| 5540–5565 | `api_keys_search` | `key_actions` | `post '/api/keys/search'` |
| 5567–5569 | `_html_esc` | `public_pages` |  |
| 5572–5579 | `_PUBLIC_FALLBACK_CSP` | `_core` |  |
| 5580 | `_GIFT_CODE_RE` | `_core` |  |
| 5583–5588 | `_public_fallback_response` | `public_pages` |  |
| 5591–5599 | `_parse_public_referrer_id` | `public_pages` |  |
| 5602–5606 | `_safe_public_gift_code` | `public_pages` |  |
| 5609–5615 | `_telegram_bot_deeplink` | `public_pages` |  |
| 5618–5621 | `_html_telegram_btn` | `public_pages` |  |
| 5624–5653 | `_referral_fallback_html` | `public_pages` |  |
| 5656–5700 | `web_referral_page` | `public_pages` | `get '/ref/{referrer_id}'` |
| 5702–5725 | `_gift_fallback_html` | `public_pages` |  |
| 5728–5793 | `web_gift_page` | `public_pages` | `get '/gift/{gift_code}'` |
| 5795–5828 | `dynamic_route` | `public_pages` | `get '/{path_param}'` |
