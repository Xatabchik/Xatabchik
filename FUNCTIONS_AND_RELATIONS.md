# Функции и взаимосвязи

Документ отвечает на три вопроса по каждому крупному модулю: **что это**, **где используется**, **зачем**. Полный табличный каталог (имя, строка, сигнатура, эвристика вызовов) — [docs/FUNCTIONS_CATALOG.md](docs/FUNCTIONS_CATALOG.md). Архитектура процессов — [ARCHITECTURE.md](ARCHITECTURE.md).

Индекс собран обходом AST: **~2100** функций/методов в **50** Python-файлах исходников (без `tests/` и vendor).

---

## 1. Точки входа и контроллеры

### `shop_bot.__main__.main`

Запускает процесс панели. Вызывает:

| Функция | Зачем |
|---------|--------|
| `rw_repo.initialize_db` | Создать/мигрировать SQLite |
| `database.get_ticket_media_root` | Залогировать каталог вложений |
| `BotController()` / `.start()` | Основной бот |
| `create_webhook_app` | Flask-приложение панели |
| `webhook_app._support_bot_controller.start` | Support-бот при автозапуске |
| `periodic_subscription_check` | Фоновые задачи на loop основного бота |

### `BotController` (`bot_controller.py`)

| Метод | Где используется | Зачем |
|-------|------------------|--------|
| `start` / `stop` / `get_status` | Flask `/start-bot`, `/stop-bot`, шапка панели; `__main__` автозапуск | Управление polling |
| `get_loop` / `get_bot_instance` | Scheduler, вебхуки (`_dispatch_payment_processing`), франшиза | Доступ к Bot и loop из других потоков |
| `_start_polling` | Внутри `start` | Retry Telegram network errors |
| `_start_own_loop` | Конструктор | Изолированный asyncio loop |

При `start`:

- вешает `BanMiddleware` и `FactoryStatsMiddleware`;
- подключает `get_user_router()` + `get_admin_router()`;
- `module_loader.discover_modules()` + `set_dispatcher`;
- при `franchise_enabled` — `ManagedBotsService.start_all()`;
- заполняет `handlers.PAYMENT_METHODS` (кэш на момент старта; **platega в этот кэш не входит**, live-чтение есть в `_get_payment_methods` и клавиатурах).

### `SupportBotController`

Аналог для support-бота. Используется панелью (`/start-support-bot`) и `idle_close.py` (`get_bot_instance` / `get_loop` для уведомлений в форум).

### `ManagedBotsService` (`factory_bot/service.py`)

| Метод | Кто вызывает | Зачем |
|-------|--------------|--------|
| `start_all` / `stop_all` | `BotController.start`, панель `toggle_franchise_settings`, админ-хендлер франшизы | Поднять/погасить все клоны |
| `start_bot` / `stop_bot` / `restart_bot` | Панель `/franchise/bot/<id>/toggle`, ротация токена | Один клон |
| `get_bot` | Хендлеры, которым нужен инстанс конкретного клона | Отправка от имени клона |

`factory_bot/runtime.py`: `set_service` / `get_service` — глобальная ссылка, чтобы Telegram-хендлеры могли остановить клон при удалении.

---

## 2. Слой данных

### `database.py` — источник правды

~430 функций. Все таблицы SQLite живут здесь (`initialize_db`, `run_migration`). Группы:

| Группа | Примеры функций | Кто использует |
|--------|-----------------|----------------|
| Пользователи | `register_user_if_not_exists`, `get_user`, `ban_user`, `delete_user_completely` | Бот, панель, Mini App, scheduler |
| Баланс / рефералка | `add_to_balance`, `deduct_from_balance`, `add_to_referral_balance`, `create_referral_withdrawal_request` | Оплата, вывод, аналитика |
| Ключи | `add_new_key`, `get_user_keys`, `extend_key`, `set_key_auto_renew`, `update_key_name` | Fulfillment, ЛК, админка |
| Хосты / сквады | `create_host`, `get_host_squads`, `add_remnawave_squad` | Настройки, Remnawave API |
| Тарифы / пакеты | `create_plan`, `create_traffic_package`, `get_lte_state`, `add_key_lte_boost_bytes` | Покупка, LTE-воркер |
| Платежи | `create_payload_pending`, `find_and_complete_pending_transaction`, `claim_processed_payment` | Все провайдеры |
| Тикеты | `create_support_ticket`, `auto_close_idle_admin_tickets`, `bulk_delete_all_tickets` | Support, панель, Mini App |
| Франшиза | `create_managed_bot`, `accrue_partner_commission`, `get_partner_cabinet` | Factory + fulfillment |
| Подарки | `create_user_gift`, `activate_user_gift` | Бот, Mini App `/gift/` |
| Auth Mini App | `create_webapp_auth_request`, `get_user_by_auth_token`, `get_webapp_settings` | Mini App + бот `auth_*` |
| Аналитика | `get_admin_stats`, `get_sales_overview`, `get_utm_analytics` | Flask `/analytics/*` |
| Капча | вызывается через `captcha_utils` | Онбординг |

Полный список — каталог, файл `src/shop_bot/data_manager/database.py`. Схема таблиц — [DATABASE_DOCUMENTATION.md](DATABASE_DOCUMENTATION.md).

### `remnawave_repository.py` — фасад

Большинство имён **проксируются** в `database.*` (`_LEGACY_FORWARDERS` + `__getattr__` для `DB_FILE`).

Собственная логика (не простой forward):

| Функция | Зачем | Кто вызывает |
|---------|--------|--------------|
| `set_current_factory_bot_id` / `get_current_factory_bot_id` | ContextVar клона для комиссий | `FactoryStatsMiddleware`, `create_payload_pending` |
| `create_payload_pending` | Пишет `factory_bot_id` в metadata | Бот, Mini App, панель |
| `record_key` / `record_key_from_payload` / `update_key` | Нормализация ключа из ответа панели | Fulfillment, админ-выдача |
| `extend_key` / `set_key_expiry` | Продление в БД | Fulfillment, bulk-extend |
| `create_promo_code` … `redeem_promo_code` | Резерв/гонка/сегменты промо | Бот, Mini App, аналитика |
| `create_gift_token` / `claim_gift_token` | Админские многоразовые токены | Админ-бот |
| `list_squads` / `get_squad` | Сквады + расшифровка секретов | Remnawave API, панель |
| `search_user_keys_by_email` / `search_all_keys_by_email` | Поиск ключей | Бот, панель, Mini App |

Правило: **импортируйте `remnawave_repository` из хендлеров**, не `database` напрямую — так франшизный контекст и промокоды не разъедутся. Исключения есть (`handlers.py` местами импортирует `database` для UTM, LTE, удаления ключа).

---

## 3. Remnawave API

`modules/remnawave_api.py` — единственный HTTP-клиент панели VPN.

| Кластер | Функции | Кто вызывает |
|---------|---------|--------------|
| Поиск пользователя | `lookup_panel_user`, `get_user_by_uuid/email/username`, `panel_user_exists` | Создание ключа, сверка |
| Выдача | `ensure_user`, `create_or_update_key_on_host` | `process_successful_payment`, триал, админ-подарок, автопродление |
| Удаление | `delete_client_on_host`, `delete_user_on_host` | Админ, синхронизация orphan-ключей |
| Устройства | `get_hwid_devices_for_user`, `delete_hwid_device` | ЛК бота и Mini App |
| LTE / dual pool | `get_user_lte_usage_bytes`, `get_user_node_usage_for_squad`, `set_user_active_squads` | `scheduler.enforce_dual_traffic_limits` |
| Список | `list_users` | `sync_keys_with_panels` |

Без этого модуля бот не умеет выдавать конфиги. Репозиторий только запоминает результат.

---

## 4. Платежные модули

| Модуль | Публичные функции | Кто реально импортирует | Дубль в боте |
|--------|-------------------|-------------------------|--------------|
| `platega_api` | `PlategaAPI`, `get_transaction_sync` | Mini App, Flask webhook | да, `_create_platega_payment_link` |
| `platega_fulfillment` | `complete_pending_platega_payment`, нормализация статуса/суммы | Flask + Mini App verify | нет |
| `rollypay_api` | `RollyPayAPI`, `verify_webhook_signature`, `get_payment_sync` | Бот, Mini App, Flask | нет |
| `heleket_api` | `create_heleket_payment_request` | Mini App | да, `_create_heleket_payment_request` |
| `cryptobot_api` | `create_cryptobot_api_invoice` | **никто** (мёртвый модуль) | да, `handlers.create_cryptobot_invoice` — его импортирует Mini App |
| YooKassa / YooMoney / TON / Stars | SDK / inline в handlers и Flask | бот + Flask | — |

Детали провайдеров и вебхуков: [PAYMENTS_DOCUMENTATION.md](PAYMENTS_DOCUMENTATION.md).

---

## 5. Telegram-бот (пользователь)

Фабрика: `get_user_router()` в `bot/handlers.py`.

Центральная бизнес-функция:

**`process_successful_payment`** — единственная точка выдачи услуги после оплаты. Её вызывают:

- вебхуки Flask через `_dispatch_payment_processing`;
- Mini App после verify / check-payment;
- хендлер Stars `successful_payment`;
- оплата с баланса / реф. баланса внутри бота.

Остальные хендлеры — UI-обёртки (выбор хоста, тарифа, промо, способа оплаты). Карта экранов: [BOT_HANDLERS_DOCUMENTATION.md](BOT_HANDLERS_DOCUMENTATION.md).

`bot/keyboards.py` — чистые сборщики `InlineKeyboardMarkup`. Динамические кнопки читают `button_configs` из БД (конструктор в панели).

`config.py` — только строки HTML для профиля и карточки ключа (`get_profile_text`, `get_key_info_text`, `get_purchase_success_text`).

---

## 6. Telegram-бот (админ)

Фабрика: `get_admin_router()` + `IsAdminFilter` / `AdminAccessMiddleware`.

Не ходит в платежные вебхуки. Ходит в:

- `database` / `rw_repo` — пользователи, ключи, настройки;
- `remnawave_api` — выдача/удаление ключа с панели;
- `speedtest_runner`, `resource_monitor`, `backup_manager`;
- `module_loader` — вкл/выкл плагинов;
- `telegram_reachability.handle_send_exception` — рассылка.

---

## 7. Flask-панель

Фабрика: `create_webhook_app(bot_controller)`.

| Кластер маршрутов | Функции-хелперы | Связь |
|-------------------|-----------------|--------|
| Логин / CSRF / TOTP | `_verify_panel_password`, `_rate_limit_login` | Только панель |
| Пользователи / ключи | partial-рендеры, ban/delete/revoke | `rw_repo` + `remnawave_api` |
| Вебхуки `/<provider>-webhook` | `_dispatch_payment_processing` | → `process_successful_payment` |
| Модули `/modules/*` | `get_global_module_loader` | ZIP, enable, proxy-роуты |
| Франшиза `/franchise*` | `_apply_franchise_runtime` | `ManagedBotsService` |
| Support `/support*` | `run_bulk_ticket_followup` | `database` + `ticket_media` |
| Monitor / speedtest | — | `resource_monitor`, `speedtest_runner` |
| Backup | — | `backup_manager` |

Полный список URL: [ADMIN_PANEL_DOCUMENTATION.md](ADMIN_PANEL_DOCUMENTATION.md).

---

## 8. Mini App (FastAPI)

`webapp/handlers.py` — отдельный процесс, общая БД.

Auth: постоянный `auth_token`, Telegram `initData`, email+пароль, deep-link `auth_*` (бот вызывает `confirm_webapp_auth_request`).

Оплата и ключи вызывают те же `rw_repo` + `remnawave_api` + `process_successful_payment`. Тикеты — те же таблицы, что у support-бота, вложения через `ticket_media.save_ticket_media_bytes`.

Подробности: [WEBAPP_MINIAPP_DOCUMENTATION.md](WEBAPP_MINIAPP_DOCUMENTATION.md).

---

## 9. Планировщик

`periodic_subscription_check` крутится вечно на loop основного бота (тик 300 с). Внутри троттлит:

| Задача | Модуль | Зачем |
|--------|--------|--------|
| `check_expiring_subscriptions` | `Bot.send_message` | Напоминания 72/48/24/1 ч |
| `check_auto_renewals` | `remnawave_api` + баланс | Списание и продление |
| `enforce_dual_traffic_limits` | `remnawave_api` LTE | Снять/вернуть LTE-сквад |
| `sync_keys_with_panels` | `list_users` | Пометить пропавшие ключи |
| `check_broadcast_campaigns` | `telegram_reachability` | Плановые рассылки |
| `_maybe_run_daily_backup` | `backup_manager` | ZIP админам |
| `_maybe_collect_resource_metrics` | `resource_monitor` | Дашборд + алерты |
| `_maybe_run_periodic_speedtests` | `speedtest_runner` | SSH-цели раз в 8 ч |
| `_maybe_auto_close_idle_tickets` | `idle_close` | Тикеты без ответа пользователя |
| `_maybe_purge_closed_ticket_media` | `ticket_media` | TTL вложений |

[SCHEDULER_DOCUMENTATION.md](SCHEDULER_DOCUMENTATION.md).

---

## 10. Support и вложения

```
support_bot/handlers.get_support_router
        ├─ ticket CRUD          → database
        ├─ save_ticket_media    → ticket_media
        └─ форум createForumTopic / closeForumTopic
idle_close.maybe_auto_close_idle_tickets
        └─ database.auto_close_idle_admin_tickets
                + уведомление через SupportBotController
ticket_media
        ├─ бот / Mini App / панель (скачивание)
        ├─ database.delete_ticket (чистит папку)
        └─ scheduler purge
```

[SUPPORT_BOT_DOCUMENTATION.md](SUPPORT_BOT_DOCUMENTATION.md).

---

## 11. Плагины

```
module_loader.discover_modules  →  modules_registry
enable_module
    ├─ SCHEMA_SQL
    ├─ дефолтные SETTINGS
    ├─ router + ModuleSafeMiddleware  → Dispatcher
    └─ blueprint / proxy registry     → Flask
```

Манифест: `ModuleMeta` в `core/module_types.py`.  
Шаблон: `modules/example_module/`.  
Боевой пример: `modules/ramadan_tracker/` (свой README).

Публичные методы лоадера: `discover_modules`, `enable_module`, `disable_module`, `delete_module`, `import_module_from_zip`, `set_dispatcher`, `set_flask_app`, `get_menu_items`, `get_settings_schema`.

[MODULES_DOCUMENTATION.md](MODULES_DOCUMENTATION.md).

---

## 12. Вспомогательные модули

| Модуль | Функции | Используется | Не используется |
|--------|---------|--------------|-----------------|
| `email_sender` | `is_smtp_configured`, `send_activation_code` | Панель SMTP-тест, Mini App email | — |
| `telegram_reachability` | `classify_unreachable_error`, `handle_send_exception` | Scheduler, админ-рассылка, Flask | — |
| `captcha_utils` | `create_captcha_challenge`, `check_captcha_answer`, `has_passed_captcha` | `bot/handlers` онбординг | — |
| `callback_safety` | `fast_callback_answer`, `catch_callback_errors` | `admin_handlers` | пользовательские хендлеры |
| `photo_helper` / `image_bot` | отправка с картинкой | **не подключены** в текущем runtime | мёртвый код |
| `cryptobot_api` | `create_cryptobot_api_invoice` | **не импортируется** | дубль в handlers |
| `webhook_server/apply_app_fix.py` | regex-патч app.py | ручной запуск | не вызывается из runtime |
| `shop_bot/app.py` | hotfix Flask | ручной запуск | не вызывается из runtime |

---

## 13. Сквозная схема вызовов (оплата → ключ)

```
пользователь нажимает «Оплатить»
    handlers.pay_*  /  webapp.api_create_payment
        rw_repo.create_payload_pending
        platega_api / rollypay_api / YooKassa / …
провайдер → Flask /<name>-webhook
        verify signature / get_transaction_sync
        find_and_complete_pending_transaction  или  platega_fulfillment
        _dispatch_payment_processing
            → loop основного бота
                handlers.process_successful_payment
                    remnawave_api.create_or_update_key_on_host
                    rw_repo.record_key_from_payload / extend_key
                    update_user_stats / referral / accrue_partner_commission
                    notify_admin_of_purchase
                    сообщение пользователю (root-бот или клон по factory_bot_id)
```

---

## 14. Как читать каталог

В [docs/FUNCTIONS_CATALOG.md](docs/FUNCTIONS_CATALOG.md) колонка «Кто вызывает» — совпадение **по имени функции**, не по объекту. Ложные срабатывания возможны (`get`, `start`). Для точной связи смотрите этот файл и импорты в начале модуля.
