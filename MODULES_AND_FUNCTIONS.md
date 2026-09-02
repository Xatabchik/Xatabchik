# Список модулей и функций Xatabchik

Документ собран повторным обходом репозитория (AST + граф импортов). **Исходный код не менялся.**

## Что считается модулем

Python-файл пакета приложения:

- `src/shop_bot/**` — ядро (боты, панель, Mini App, БД, интеграции);
- `modules/*` — подключаемые плагины (сканирует `module_loader`);
- корневые `migrate_*.py`, `tools/`, `simple_*.py` — утилиты вне runtime.

Пустые `__init__.py` — только маркеры пакета.

## Как читается колонка «Где вызывается»

Учтены вызовы вида `from shop_bot.x import f` и `import shop_bot.x as y` + `y.f`.  
`from shop_bot.modules import remnawave_api` + `remnawave_api.ensure_user` тоже учитывается.

Функции `database.py` часто зовут не напрямую, а как `rw_repo.get_user` (`remnawave_repository` форвардит ~200 имён). Для `database.py` такие call site’ы **включены** в «Где вызывается».

Формат сайта: `файл::оборачивающая_функция`. Вложенные хендлеры (`get_user_router.start_handler`) вызывает **aiogram Dispatcher**, не прямой импорт — они перечислены отдельной таблицей.

Точки входа без импортёров — норма: `__main__.py` (`python -m shop_bot`), `webapp/handlers.py` (`uvicorn ...:app`).

Связанные документы: [DOCUMENTATION.md](DOCUMENTATION.md), [ARCHITECTURE.md](ARCHITECTURE.md), [FUNCTIONS_AND_RELATIONS.md](FUNCTIONS_AND_RELATIONS.md), [docs/FUNCTIONS_CATALOG.md](docs/FUNCTIONS_CATALOG.md).

## Оглавление

1. **Точки входа и пакет**
   - [src/shop_bot/__init__.py](#src-shop_bot-__init__py) — 0 функц.
   - [src/shop_bot/__main__.py](#src-shop_bot-__main__py) — 7 функц.
   - [src/shop_bot/app.py](#src-shop_bot-apppy) — 2 функц.
   - [src/shop_bot/config.py](#src-shop_bot-configpy) — 4 функц.
   - [src/shop_bot/bot_controller.py](#src-shop_bot-bot_controllerpy) — 11 функц.
   - [src/shop_bot/support_bot_controller.py](#src-shop_bot-support_bot_controllerpy) — 10 функц.
2. **Пользовательский и админ Telegram-бот**
   - [src/shop_bot/bot/__init__.py](#src-shop_bot-bot-__init__py) — 0 функц.
   - [src/shop_bot/bot/handlers.py](#src-shop_bot-bot-handlerspy) — 249 функц.
   - [src/shop_bot/bot/admin_handlers.py](#src-shop_bot-bot-admin_handlerspy) — 367 функц.
   - [src/shop_bot/bot/keyboards.py](#src-shop_bot-bot-keyboardspy) — 118 функц.
   - [src/shop_bot/bot/middlewares.py](#src-shop_bot-bot-middlewarespy) — 1 функц.
   - [src/shop_bot/bot/callback_safety.py](#src-shop_bot-bot-callback_safetypy) — 6 функц.
   - [src/shop_bot/bot/photo_helper.py](#src-shop_bot-bot-photo_helperpy) — 5 функц.
   - [src/shop_bot/bot/image_bot.py](#src-shop_bot-bot-image_botpy) — 3 функц.
3. **Данные и фон**
   - [src/shop_bot/data_manager/__init__.py](#src-shop_bot-data_manager-__init__py) — 0 функц.
   - [src/shop_bot/data_manager/database.py](#src-shop_bot-data_manager-databasepy) — 429 функц.
   - [src/shop_bot/data_manager/remnawave_repository.py](#src-shop_bot-data_manager-remnawave_repositorypy) — 64 функц.
   - [src/shop_bot/data_manager/scheduler.py](#src-shop_bot-data_manager-schedulerpy) — 39 функц.
   - [src/shop_bot/data_manager/backup_manager.py](#src-shop_bot-data_manager-backup_managerpy) — 6 функц.
   - [src/shop_bot/data_manager/captcha_utils.py](#src-shop_bot-data_manager-captcha_utilspy) — 9 функц.
   - [src/shop_bot/data_manager/resource_monitor.py](#src-shop_bot-data_manager-resource_monitorpy) — 8 функц.
   - [src/shop_bot/data_manager/speedtest_runner.py](#src-shop_bot-data_manager-speedtest_runnerpy) — 25 функц.
4. **Интеграции (`shop_bot.modules`)**
   - [src/shop_bot/modules/__init__.py](#src-shop_bot-modules-__init__py) — 0 функц.
   - [src/shop_bot/modules/remnawave_api.py](#src-shop_bot-modules-remnawave_apipy) — 86 функц.
   - [src/shop_bot/modules/platega_api.py](#src-shop_bot-modules-platega_apipy) — 5 функц.
   - [src/shop_bot/modules/platega_fulfillment.py](#src-shop_bot-modules-platega_fulfillmentpy) — 7 функц.
   - [src/shop_bot/modules/rollypay_api.py](#src-shop_bot-modules-rollypay_apipy) — 7 функц.
   - [src/shop_bot/modules/heleket_api.py](#src-shop_bot-modules-heleket_apipy) — 1 функц.
   - [src/shop_bot/modules/cryptobot_api.py](#src-shop_bot-modules-cryptobot_apipy) — 1 функц.
   - [src/shop_bot/modules/email_sender.py](#src-shop_bot-modules-email_senderpy) — 6 функц.
   - [src/shop_bot/modules/telegram_reachability.py](#src-shop_bot-modules-telegram_reachabilitypy) — 2 функц.
5. **Ядро плагинов (`shop_bot.core`)**
   - [src/shop_bot/core/__init__.py](#src-shop_bot-core-__init__py) — 0 функц.
   - [src/shop_bot/core/module_loader.py](#src-shop_bot-core-module_loaderpy) — 46 функц.
   - [src/shop_bot/core/module_types.py](#src-shop_bot-core-module_typespy) — 3 функц.
   - [src/shop_bot/core/module_middleware.py](#src-shop_bot-core-module_middlewarepy) — 4 функц.
6. **Админ-панель Flask**
   - [src/shop_bot/webhook_server/__init__.py](#src-shop_bot-webhook_server-__init__py) — 0 функц.
   - [src/shop_bot/webhook_server/app.py](#src-shop_bot-webhook_server-apppy) — 241 функц.
   - [src/shop_bot/webhook_server/apply_app_fix.py](#src-shop_bot-webhook_server-apply_app_fixpy) — 1 функц.
7. **Telegram Mini App**
   - [src/shop_bot/webapp/__init__.py](#src-shop_bot-webapp-__init__py) — 0 функц.
   - [src/shop_bot/webapp/handlers.py](#src-shop_bot-webapp-handlerspy) — 144 функц.
8. **Support-бот**
   - [src/shop_bot/support_bot/__init__.py](#src-shop_bot-support_bot-__init__py) — 0 функц.
   - [src/shop_bot/support_bot/handlers.py](#src-shop_bot-support_bot-handlerspy) — 33 функц.
   - [src/shop_bot/support_bot/idle_close.py](#src-shop_bot-support_bot-idle_closepy) — 5 функц.
   - [src/shop_bot/support_bot/ticket_media.py](#src-shop_bot-support_bot-ticket_mediapy) — 27 функц.
9. **Франшиза (клоны ботов)**
   - [src/shop_bot/factory_bot/__init__.py](#src-shop_bot-factory_bot-__init__py) — 0 функц.
   - [src/shop_bot/factory_bot/service.py](#src-shop_bot-factory_bot-servicepy) — 10 функц.
   - [src/shop_bot/factory_bot/runtime.py](#src-shop_bot-factory_bot-runtimepy) — 2 функц.
   - [src/shop_bot/factory_bot/middleware.py](#src-shop_bot-factory_bot-middlewarepy) — 3 функц.
   - [src/shop_bot/factory_bot/handlers.py](#src-shop_bot-factory_bot-handlerspy) — 5 функц.
   - [src/shop_bot/factory_bot/keyboards.py](#src-shop_bot-factory_bot-keyboardspy) — 2 функц.
10. **Плагины в `modules/`**
   - [modules/example_module/__init__.py](#modules-example_module-__init__py) — 0 функц.
   - [modules/example_module/bot_handlers.py](#modules-example_module-bot_handlerspy) — 1 функц.
   - [modules/example_module/panel_routes.py](#modules-example_module-panel_routespy) — 1 функц.
   - [modules/example_module/db_schema.py](#modules-example_module-db_schemapy) — 0 функц.
   - [modules/example_module/db_cleanup.py](#modules-example_module-db_cleanuppy) — 1 функц.
   - [modules/example_module/settings_schema.py](#modules-example_module-settings_schemapy) — 0 функц.
   - [modules/ramadan_tracker/__init__.py](#modules-ramadan_tracker-__init__py) — 0 функц.
   - [modules/ramadan_tracker/bot_handlers.py](#modules-ramadan_tracker-bot_handlerspy) — 86 функц.
   - [modules/ramadan_tracker/panel_routes.py](#modules-ramadan_tracker-panel_routespy) — 7 функц.
   - [modules/ramadan_tracker/db_schema.py](#modules-ramadan_tracker-db_schemapy) — 1 функц.
   - [modules/ramadan_tracker/db_cleanup.py](#modules-ramadan_tracker-db_cleanuppy) — 1 функц.
   - [modules/ramadan_tracker/settings_schema.py](#modules-ramadan_tracker-settings_schemapy) — 0 функц.
11. **Скрипты вне пакета**
   - [tools/inspect_db.py](#tools-inspect_dbpy) — 0 функц.
   - [migrate_vless.py](#migrate_vlesspy) — 0 функц.
   - [migrate_invalidate_auth_tokens.py](#migrate_invalidate_auth_tokenspy) — 0 функц.
   - [simple_collect.py](#simple_collectpy) — 2 функц.
   - [simple_monitor_test.py](#simple_monitor_testpy) — 5 функц.

## Кто кого импортирует (пакеты)

Кратко по пакетам: какие **прод-файлы** делают `import` этого пакета.

| Пакет | Зачем | Прод-импортёры |
|-------|--------|----------------|
| `shop_bot.data_manager.database` | SQLite CRUD | `migrate_invalidate_auth_tokens.py`, `modules/ramadan_tracker/bot_handlers.py`, `modules/ramadan_tracker/panel_routes.py`, `simple_collect.py`, `simple_monitor_test.py`, `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot/keyboards.py`, `src/shop_bot/core/module_loader.py`, `src/shop_bot/core/module_middleware.py`, `src/shop_bot/data_manager/captcha_utils.py`, `src/shop_bot/data_manager/remnawave_repository.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/modules/cryptobot_api.py`, `src/shop_bot/modules/email_sender.py`, `src/shop_bot/modules/heleket_api.py`, `src/shop_bot/modules/platega_fulfillment.py`, `src/shop_bot/modules/telegram_reachability.py`, `src/shop_bot/support_bot/idle_close.py`, `src/shop_bot/support_bot/ticket_media.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.data_manager.remnawave_repository` | фасад БД + промо/ключи/франшиза | `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot/keyboards.py`, `src/shop_bot/bot/middlewares.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/data_manager/backup_manager.py`, `src/shop_bot/data_manager/database.py`, `src/shop_bot/data_manager/resource_monitor.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/data_manager/speedtest_runner.py`, `src/shop_bot/factory_bot/handlers.py`, `src/shop_bot/factory_bot/middleware.py`, `src/shop_bot/factory_bot/service.py`, `src/shop_bot/modules/platega_fulfillment.py`, `src/shop_bot/modules/remnawave_api.py`, `src/shop_bot/support_bot/handlers.py`, `src/shop_bot/support_bot_controller.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.modules.remnawave_api` | клиент Remnawave | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/data_manager/remnawave_repository.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.bot.handlers` | пользовательский бот / fulfillment | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/factory_bot/service.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.bot.admin_handlers` | админ-бот | `src/shop_bot/bot_controller.py` |
| `shop_bot.bot.keyboards` | клавиатуры | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.bot_controller` | контроллер основного бота | `src/shop_bot/__main__.py`, `src/shop_bot/data_manager/scheduler.py` |
| `shop_bot.support_bot_controller` | контроллер support-бота | `src/shop_bot/webhook_server/app.py` |
| `shop_bot.webhook_server.app` | Flask-панель | `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/keyboards.py`, `src/shop_bot/support_bot/idle_close.py` |
| `shop_bot.webapp.handlers` | Mini App | не импортируется кодом — uvicorn грузит `shop_bot.webapp.handlers:app` (сервис `xatabchik-webapp`) |
| `shop_bot.data_manager.scheduler` | планировщик | `src/shop_bot/__main__.py` |
| `shop_bot.core.module_loader` | загрузчик плагинов | `modules/ramadan_tracker/bot_handlers.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/core/__init__.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.factory_bot.service` | клоны франшизы | `src/shop_bot/bot_controller.py` |
| `shop_bot.modules.platega_api` | Platega | `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.modules.platega_fulfillment` | завершение Platega | `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.modules.rollypay_api` | RollyPay | `src/shop_bot/bot/handlers.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.modules.heleket_api` | Heleket | `src/shop_bot/webapp/handlers.py` |
| `shop_bot.modules.cryptobot_api` | CryptoBot (не импортируется) | — |
| `shop_bot.modules.email_sender` | SMTP | `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.modules.telegram_reachability` | 403 Telegram | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.support_bot.ticket_media` | вложения тикетов | `src/shop_bot/data_manager/database.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/support_bot/handlers.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.support_bot.idle_close` | автозакрытие тикетов | `src/shop_bot/data_manager/scheduler.py` |
| `shop_bot.data_manager.backup_manager` | бэкапы | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.data_manager.speedtest_runner` | speedtest | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/resource_monitor.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.data_manager.resource_monitor` | мониторинг | `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py` |
| `shop_bot.data_manager.captcha_utils` | капча | `src/shop_bot/bot/handlers.py` |

## Точки входа и пакет

<a id="src-shop_bot-__init__py"></a>

### `src/shop_bot/__init__.py`

Маркер пакета `shop_bot`. Пустой файл, символов не экспортирует.

**Импорт-путь:** `shop_bot`  
**Кто импортирует (прод):** `src/shop_bot/webapp/handlers.py`  

Функций нет.

<a id="src-shop_bot-__main__py"></a>

### `src/shop_bot/__main__.py`

Точка входа процесса панели: логирование, initialize_db, Flask-поток, автозапуск ботов, запуск планировщика на loop основного бота.

**Как запускается:** `python -m shop_bot` (Docker-сервис `xatabchik`). Другие модули его не импортируют.

**Импорт-путь:** `shop_bot.__main__`  
**Кто импортирует (прод):** не импортируется — сам импортирует `create_webhook_app`, `BotController`, `periodic_subscription_check`, `rw_repo`.  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 27 | `ColoredFormatter` | `logging.Formatter` | — |
| 72 | `RussianizeAiogramFilter` | `logging.Filter` | — |

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 20 | `main()` | Собрать логирование, БД, Flask, боты, планировщик | Запускается из `if __name__ == "__main__"` при `python -m shop_bot`; другими модулями не импортируется |

**Вложенные функции** (6), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 37 | `ColoredFormatter.main.format` | `ColoredFormatter.main` |
| 73 | `RussianizeAiogramFilter.main.filter` | `RussianizeAiogramFilter.main` |
| 121 | `main._is_true` | `main` |
| 124 | `main.shutdown` | `main` |
| 135 | `main.start_services` | `main` |
| 193 | `main.start_services._log_bot_status_soon` | `main.start_services` |

<a id="src-shop_bot-apppy"></a>

### `src/shop_bot/app.py`

Одноразовый hotfix-скрипт для патча webhook_server/app.py. Не импортируется runtime.

**Импорт-путь:** `shop_bot.app`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 14 | `patch_file(path)` | — | из прод-кода **не вызывается** |

**Вложенные функции** (1), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 33 | `patch_file.ensure_flag_in_list` | `patch_file` |

<a id="src-shop_bot-configpy"></a>

### `src/shop_bot/config.py`

HTML-тексты профиля, статуса VPN и карточки ключа для Telegram-бота.

**Импорт-путь:** `shop_bot.config`  
**Кто импортирует (прод):** `src/shop_bot/bot/handlers.py`, `src/shop_bot/webapp/handlers.py`  

**Функции верхнего уровня и методы классов:** 4

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 9 | `get_profile_text(username, total_spent, total_months, vpn_status_text)` | — | `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback` |
| 17 | `get_vpn_active_text(days_left, hours_left)` | — | `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback` |
| 23 | `get_key_info_text(key, key_number, devices_connected, plan_group, plan_name, device_limit, gift_code, domain, …)` | — | `src/shop_bot/bot/handlers.py::get_user_router.show_gift_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process`, `src/shop_bot/bot/handlers.py::get_user_router.remove_key_name`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_rename_key`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/bot/handlers.py::get_user_router.delete_device_handler` |
| 115 | `get_purchase_success_text(action, key_number, expiry_date, connection_string)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation` |

<a id="src-shop_bot-bot_controllerpy"></a>

### `src/shop_bot/bot_controller.py`

Жизненный цикл основного бота: изолированный event loop, polling, Ban/Factory middleware, подключение роутеров и клонов франшизы, кэш PAYMENT_METHODS.

**Импорт-путь:** `shop_bot.bot_controller`  
**Кто импортирует (прод):** `src/shop_bot/__main__.py`, `src/shop_bot/data_manager/scheduler.py`  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 32 | `BotController` | — | — |

**Функции верхнего уровня и методы классов:** 10

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 28 | `_is_true(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 33 | `BotController.__init__(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 47 | `BotController._start_own_loop(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 70 | `BotController.set_loop(self, loop)` | — | из прод-кода **не вызывается** |
| 76 | `BotController.get_loop(self)` | — | из прод-кода **не вызывается** |
| 79 | `BotController.get_bot_instance(self)` | — | из прод-кода **не вызывается** |
| 82 | `async BotController._start_polling(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 137 | `BotController.start(self)` | — | из прод-кода **не вызывается** |
| 271 | `BotController.stop(self)` | — | из прод-кода **не вызывается** |
| 284 | `BotController.get_status(self)` | — | из прод-кода **не вызывается** |

**Вложенные функции** (1), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 50 | `BotController._start_own_loop._runner` | `BotController._start_own_loop` |

<a id="src-shop_bot-support_bot_controllerpy"></a>

### `src/shop_bot/support_bot_controller.py`

Жизненный цикл support-бота в отдельном потоке и event loop. Стартуется из панели и __main__.

**Импорт-путь:** `shop_bot.support_bot_controller`  
**Кто импортирует (прод):** `src/shop_bot/webhook_server/app.py`  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 15 | `SupportBotController` | — | — |

**Функции верхнего уровня и методы классов:** 9

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 16 | `SupportBotController.__init__(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 28 | `SupportBotController._start_own_loop(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 49 | `SupportBotController.set_loop(self, loop)` | — | из прод-кода **не вызывается** |
| 54 | `SupportBotController.get_loop(self)` | — | из прод-кода **не вызывается** |
| 57 | `SupportBotController.get_bot_instance(self)` | — | из прод-кода **не вызывается** |
| 60 | `async SupportBotController._start_polling(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 78 | `SupportBotController.start(self)` | — | из прод-кода **не вызывается** |
| 120 | `SupportBotController.stop(self)` | — | из прод-кода **не вызывается** |
| 131 | `SupportBotController.get_status(self)` | — | из прод-кода **не вызывается** |

**Вложенные функции** (1), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 31 | `SupportBotController._start_own_loop._runner` | `SupportBotController._start_own_loop` |

## Пользовательский и админ Telegram-бот

<a id="src-shop_bot-bot-__init__py"></a>

### `src/shop_bot/bot/__init__.py`

Маркер пакета bot. Пустой.

**Импорт-путь:** `shop_bot.bot`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 7 файл(ов)

Функций нет.

<a id="src-shop_bot-bot-handlerspy"></a>

### `src/shop_bot/bot/handlers.py`

Пользовательский Telegram-магазин: онбординг, капча, покупка/продление, платежи, ключи, рефералка, подарки, тикеты, франшиза. Центральный fulfillment — process_successful_payment.

**Импорт-путь:** `shop_bot.bot.handlers`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/factory_bot/service.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 6 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 1263 | `KeyPurchase` | `StatesGroup` | — |
| 1267 | `Captcha` | `StatesGroup` | — |
| 1270 | `Onboarding` | `StatesGroup` | — |
| 1273 | `PaymentProcess` | `StatesGroup` | — |
| 1280 | `TopUpProcess` | `StatesGroup` | — |
| 1285 | `TrafficGbTopUp` | `StatesGroup` | — |
| 1290 | `LteGbTopUp` | `StatesGroup` | — |
| 1295 | `MainPoolReset` | `StatesGroup` | — |
| 1299 | `SupportDialog` | `StatesGroup` | — |
| 1312 | `FranchiseStates` | `StatesGroup` | — |
| 1319 | `KeyManagement` | `StatesGroup` | — |
| 1323 | `ReferralWithdraw` | `StatesGroup` | — |

**Функции верхнего уровня и методы классов:** 36

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 122 | `_is_true(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 125 | `_get_payment_methods()` | Собирает доступные способы оплаты из актуальных настроек (без перезапуска бота). | из прод-кода **не вызывается** |
| 190 | `_classify_key_creation_error(exc)` | внутренний хелпер | из прод-кода **не вызывается** |
| 216 | `_format_key_action_label(action, price, key_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 231 | `_log_key_creation_error(user_id, action_label, code, detail)` | внутренний хелпер | из прод-кода **не вызывается** |
| 243 | `async _notify_admins_key_creation_error(bot, user_id, code, description, action_label)` | внутренний хелпер | из прод-кода **не вызывается** |
| 271 | `async _notify_user_key_creation_error(bot, user_id, code, refund, factory_bot_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 311 | `async _handle_key_creation_failure(bot, user_id, action_label, exc, refund, factory_bot_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 332 | `async _abort_topup_fulfillment(bot, payment_id, user_id, price, payment_method, action_label, reason)` | Компенсирующая транзакция при сбое применения оплаченной докупки трафика. | из прод-кода **не вызывается** |
| 416 | `async _notify_admins_topup_desync(bot, user_id, action_label, payment_id, detail)` | Докупка применена на VPN-сервере, но не сохранилась в БД бота. | из прод-кода **не вызывается** |
| 456 | `async _abort_key_fulfillment(bot, payment_id, user_id, price, payment_method, action_label, exc, factory_bot_id, …)` | Компенсирующая транзакция при сбое выдачи ключа после оплаты. | из прод-кода **не вызывается** |
| 516 | `async _safe_edit_or_answer(message, text, **kwargs)` | Заменить `message.edit_text(...)` там, где предыдущее сообщение может | из прод-кода **не вызывается** |
| 532 | `_format_duration_label(months, duration_days)` | внутренний хелпер | из прод-кода **не вызывается** |
| 546 | `_compute_days_to_add(months, duration_days)` | внутренний хелпер | из прод-кода **не вызывается** |
| 560 | `_tariff_label_from_origin(is_trial, months, duration_days)` | Human label for subscription page tariff line. | из прод-кода **не вызывается** |
| 573 | `_build_key_origin_meta(source, plan_id, plan_name, months, duration_days, is_trial, note)` | Store key origin info inside vpn_keys.description as JSON. | из прод-кода **не вызывается** |
| 603 | `async grant_referrer_day_bonus_for_trial(referred_user_id, bot)` | Начислить рефереру +1 день только в момент активации триала рефералом. | из прод-кода **не вызывается** |
| 745 | `_webapp_public_base()` | Публичный базовый URL Mini App, если webapp включён и задан домен. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 762 | `_build_gift_links(gift_code)` | Построить обе ссылки активации подарка: в мини-приложении (webapp) и в Telegram. | из прод-кода **не вызывается** |
| 774 | `_build_referral_links(user_id, bot_username)` | Построить реферальные ссылки: (webapp_link, telegram_link). | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 791 | `_referral_share_text()` | Текст для t.me/share из настроек (Контент → referral_share_text). | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 797 | `_gift_share_text()` | Текст для t.me/share при шаринге подарка (Контент → gift_share_text). | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 803 | `_telegram_share_url(url, text)` | Собрать https://t.me/share/url?... с пробелами как %20 (не +). | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 815 | `async _activate_gift_directly(message, bot, user_id, gift_code, is_new_user)` | Активировать подарок для пользователя. | из прод-кода **не вызывается** |
| 906 | `async _create_heleket_payment_request(user_id, price, months, host_name, state_data)` | Создание инвойса в Heleket и возврат payment URL. | из прод-кода **не вызывается** |
| 1018 | `async create_cryptobot_api_invoice(amount, payload_str)` | Упрощённая обёртка для создания инвойса в Crypto Pay (CryptoBot), используемая | `src/shop_bot/webapp/handlers.py::api_create_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1068 | `async _create_cryptobot_invoice(user_id, price_rub, months, host_name, state_data)` | Создание инвойса в Crypto Pay (CryptoBot) и возврат bot_invoice_url. | из прод-кода **не вызывается** |
| 1332 | `is_valid_email(email)` | — | из прод-кода **не вызывается** |
| 1336 | `async show_captcha(message, state, user_id)` | Показывает капчу пользователю. | из прод-кода **не вызывается** |
| 1378 | `async show_main_menu(message, edit_message)` | — | из прод-кода **не вызывается** |
| 1508 | `async process_successful_onboarding(callback, state)` | Завершает онбординг: ставит флаг согласия и открывает главное меню. | из прод-кода **не вызывается** |
| 1531 | `registration_required(f)` | — | из прод-кода **не вызывается** |
| 1546 | `async _maybe_pay_referral_start_bonus(bot, user_id, referrer_id)` | Выплатить рефереру фиксированный бонус за регистрацию приглашённого пользователя | из прод-кода **не вызывается**; тесты: 5 сайт(ов) |
| 1620 | `get_user_router()` | — | `src/shop_bot/bot_controller.py::BotController.start`, `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot`; тесты: 7 сайт(ов) |
| 9297 | `async notify_admin_of_purchase(bot, metadata)` | — | `src/shop_bot/webapp/handlers.py::notify_admin_of_purchase` |
| 9404 | `async process_successful_payment(bot, metadata)` | Обработать успешную оплату и выдать услугу. | `src/shop_bot/webapp/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::_fulfill_webapp_paid_order`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment`, `src/shop_bot/webhook_server/app.py::_dispatch_payment_processing` |

**Вложенные функции** (213), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 649 | `grant_referrer_day_bonus_for_trial._parse_exp_dt` | `grant_referrer_day_bonus_for_trial` |
| 1533 | `registration_required.decorated_function` | `registration_required` |
| 1624 | `get_user_router.start_handler` | `get_user_router` |
| 1781 | `get_user_router.check_subscription_handler` | `get_user_router` |
| 1809 | `get_user_router.onboarding_fallback_handler` | `get_user_router` |
| 1817 | `get_user_router.captcha_answer_handler` | `get_user_router` |
| 1903 | `get_user_router.captcha_button_answer_handler` | `get_user_router` |
| 2001 | `get_user_router.cancel_captcha_handler` | `get_user_router` |
| 2009 | `get_user_router.main_menu_handler` | `get_user_router` |
| 2014 | `get_user_router.back_to_main_menu_handler` | `get_user_router` |
| 2020 | `get_user_router.open_main_menu_handler` | `get_user_router` |
| 2026 | `get_user_router.show_main_menu_cb` | `get_user_router` |
| 2032 | `get_user_router.profile_handler_callback` | `get_user_router` |
| 2106 | `get_user_router.toggle_expiry_notifications_handler` | `get_user_router` |
| 2121 | `get_user_router.show_inactive_gifts_handler` | `get_user_router` |
| 2146 | `get_user_router.gifts_page_handler` | `get_user_router` |
| 2177 | `get_user_router.show_gift_handler` | `get_user_router` |
| 2267 | `get_user_router.send_gift_link_handler` | `get_user_router` |
| 2333 | `get_user_router.activate_own_gift_handler` | `get_user_router` |
| 2368 | `get_user_router._resolve_plan_for_traffic_topup` | `get_user_router` |
| 2382 | `get_user_router.traffic_gb_start_handler` | `get_user_router` |
| 2415 | `get_user_router.traffic_gb_pick_handler` | `get_user_router` |
| 2460 | `get_user_router._traffic_gb_metadata` | `get_user_router` |
| 2474 | `get_user_router.trafficgb_pay_balance_handler` | `get_user_router` |
| 2494 | `get_user_router.trafficgb_pay_referral_balance_handler` | `get_user_router` |
| 2514 | `get_user_router.trafficgb_pay_yookassa_handler` | `get_user_router` |
| 2569 | `get_user_router.trafficgb_pay_platega_handler` | `get_user_router` |
| 2604 | `get_user_router.trafficgb_pay_rollypay_handler` | `get_user_router` |
| 2642 | `get_user_router.trafficgb_pay_heleket_handler` | `get_user_router` |
| 2681 | `get_user_router.trafficgb_pay_cryptobot_handler` | `get_user_router` |
| 2721 | `get_user_router.trafficgb_pay_yoomoney_handler` | `get_user_router` |
| 2752 | `get_user_router.trafficgb_pay_stars_handler` | `get_user_router` |
| 2791 | `get_user_router._resolve_plan_for_lte_topup` | `get_user_router` |
| 2805 | `get_user_router.lte_gb_start_handler` | `get_user_router` |
| 2840 | `get_user_router.lte_gb_pick_handler` | `get_user_router` |
| 2886 | `get_user_router._lte_gb_metadata` | `get_user_router` |
| 2900 | `get_user_router.ltegb_pay_balance_handler` | `get_user_router` |
| 2920 | `get_user_router.ltegb_pay_referral_balance_handler` | `get_user_router` |
| 2940 | `get_user_router.ltegb_pay_yookassa_handler` | `get_user_router` |
| 2995 | `get_user_router.ltegb_pay_platega_handler` | `get_user_router` |
| 3030 | `get_user_router.ltegb_pay_rollypay_handler` | `get_user_router` |
| 3068 | `get_user_router.ltegb_pay_heleket_handler` | `get_user_router` |
| 3107 | `get_user_router.ltegb_pay_cryptobot_handler` | `get_user_router` |
| 3147 | `get_user_router.ltegb_pay_yoomoney_handler` | `get_user_router` |
| 3178 | `get_user_router.ltegb_pay_stars_handler` | `get_user_router` |
| 3217 | `get_user_router._resolve_key_for_main_reset` | `get_user_router` |
| 3225 | `get_user_router.main_reset_start_handler` | `get_user_router` |
| 3294 | `get_user_router._main_reset_metadata` | `get_user_router` |
| 3306 | `get_user_router.mainreset_pay_balance_handler` | `get_user_router` |
| 3326 | `get_user_router.mainreset_pay_referral_balance_handler` | `get_user_router` |
| 3346 | `get_user_router.mainreset_pay_yookassa_handler` | `get_user_router` |
| 3401 | `get_user_router.topup_start_handler` | `get_user_router` |
| 3410 | `get_user_router.topup_amount_input` | `get_user_router` |
| 3435 | `get_user_router.topup_pay_yookassa` | `get_user_router` |
| 3520 | `get_user_router.create_stars_invoice_handler` | `get_user_router` |
| 3612 | `get_user_router.payment_stars_back_handler` | `get_user_router` |
| 3672 | `get_user_router.topup_stars_handler` | `get_user_router` |
| 3722 | `get_user_router.pre_checkout_handler` | `get_user_router` |
| 3745 | `get_user_router.stars_success_handler` | `get_user_router` |
| 3808 | `get_user_router._rollypay_is_enabled` | `get_user_router` |
| 3814 | `get_user_router._create_rollypay_payment_link` | `get_user_router` |
| 3831 | `get_user_router._platega_is_enabled` | `get_user_router` |
| 3834 | `get_user_router._platega_get_base_url` | `get_user_router` |
| 3837 | `get_user_router._platega_get_method_code` | `get_user_router` |
| 3851 | `get_user_router._platega_request` | `get_user_router` |
| 3877 | `get_user_router._create_platega_payment_link` | `get_user_router` |
| 3893 | `get_user_router._get_platega_transaction` | `get_user_router` |
| 3898 | `get_user_router._build_yoomoney_link` | `get_user_router` |
| 3915 | `get_user_router.pay_yoomoney_handler` | `get_user_router` |
| 3975 | `get_user_router.topup_yoomoney_handler` | `get_user_router` |
| 4026 | `get_user_router.check_platega_payment_handler` | `get_user_router` |
| 4082 | `get_user_router.check_rollypay_payment_handler` | `get_user_router` |
| 4160 | `get_user_router.check_yookassa_payment_handler` | `get_user_router` |
| 4253 | `get_user_router.check_pending_payment_handler` | `get_user_router` |
| 4340 | `get_user_router.topup_pay_platega` | `get_user_router` |
| 4385 | `get_user_router.topup_pay_rollypay` | `get_user_router` |
| 4433 | `get_user_router.topup_pay_heleket_like` | `get_user_router` |
| 4472 | `get_user_router.topup_pay_cryptobot` | `get_user_router` |
| 4511 | `get_user_router.topup_pay_tonconnect` | `get_user_router` |
| 4577 | `get_user_router.referral_program_handler` | `get_user_router` |
| 4595 | `get_user_router.referral_program_handler._to_float_setting` | `get_user_router.referral_program_handler` |
| 4603 | `get_user_router.referral_program_handler._is_true_setting` | `get_user_router.referral_program_handler` |
| 4613 | `get_user_router.referral_program_handler._fmt_num` | `get_user_router.referral_program_handler` |
| 4688 | `get_user_router.referral_top_handler` | `get_user_router` |
| 4739 | `get_user_router._ref_is_true` | `get_user_router` |
| 4743 | `get_user_router._ref_float_setting` | `get_user_router` |
| 4750 | `get_user_router._ref_withdraw_enabled` | `get_user_router` |
| 4753 | `get_user_router._ref_method_enabled` | `get_user_router` |
| 4760 | `get_user_router._ref_sbp_banks` | `get_user_router` |
| 4766 | `get_user_router._ref_mask` | `get_user_router` |
| 4774 | `get_user_router._kb_my_balance` | `get_user_router` |
| 4788 | `get_user_router.referral_my_balance` | `get_user_router` |
| 4807 | `get_user_router.referral_withdraw_requests` | `get_user_router` |
| 4841 | `get_user_router.referral_transfer_start` | `get_user_router` |
| 4865 | `get_user_router.referral_transfer_amount` | `get_user_router` |
| 4923 | `get_user_router._kb_payout_methods` | `get_user_router` |
| 4941 | `get_user_router.referral_payout_methods` | `get_user_router` |
| 4966 | `get_user_router._kb_method_types` | `get_user_router` |
| 4980 | `get_user_router.referral_payout_method_add` | `get_user_router` |
| 4992 | `get_user_router._kb_bank_choice` | `get_user_router` |
| 5002 | `get_user_router.referral_payout_method_add_type` | `get_user_router` |
| 5024 | `get_user_router.referral_payout_method_bank_choice` | `get_user_router` |
| 5042 | `get_user_router.referral_payout_method_value` | `get_user_router` |
| 5068 | `get_user_router.referral_payout_method_delete` | `get_user_router` |
| 5094 | `get_user_router.referral_withdraw_start` | `get_user_router` |
| 5139 | `get_user_router.referral_withdraw_choose_method` | `get_user_router` |
| 5165 | `get_user_router.referral_withdraw_amount` | `get_user_router` |
| 5220 | `get_user_router.about_handler` | `get_user_router` |
| 5241 | `get_user_router.user_speedtest_last_handler` | `get_user_router` |
| 5292 | `get_user_router.about_handler` | `get_user_router` |
| 5313 | `get_user_router.support_menu_handler` | `get_user_router` |
| 5334 | `get_user_router.support_external_handler` | `get_user_router` |
| 5354 | `get_user_router.support_new_ticket_handler` | `get_user_router` |
| 5367 | `get_user_router.support_subject_received` | `get_user_router` |
| 5380 | `get_user_router.support_message_received` | `get_user_router` |
| 5393 | `get_user_router.support_my_tickets_handler` | `get_user_router` |
| 5406 | `get_user_router.support_view_ticket_handler` | `get_user_router` |
| 5419 | `get_user_router.support_reply_prompt_handler` | `get_user_router` |
| 5433 | `get_user_router.support_reply_received` | `get_user_router` |
| 5445 | `get_user_router.forum_thread_message_handler` | `get_user_router` |
| 5493 | `get_user_router.support_close_ticket_handler` | `get_user_router` |
| 5506 | `get_user_router._remnawave_key_exists` | `get_user_router` |
| 5531 | `get_user_router._extract_connected_devices` | `get_user_router` |
| 5543 | `get_user_router._extract_connected_devices._count_from_value` | `get_user_router._extract_connected_devices` |
| 5657 | `get_user_router._get_connected_devices_count` | `get_user_router` |
| 5686 | `get_user_router._get_connected_devices_count._count_any` | `get_user_router._get_connected_devices_count` |
| 5735 | `get_user_router._get_devices_list` | `get_user_router` |
| 5789 | `get_user_router._is_key_without_billing_plan` | `get_user_router` |
| 5820 | `get_user_router._resolve_plan_id_for_key` | `get_user_router` |
| 5858 | `get_user_router._extract_traffic_used_bytes` | `get_user_router` |
| 5879 | `get_user_router._format_bytes_gb` | `get_user_router` |
| 5886 | `get_user_router._get_tariff_info_for_key` | `get_user_router` |
| 6090 | `get_user_router.sync_user_keys_with_remnawave` | `get_user_router` |
| 6111 | `get_user_router.sync_user_keys_with_remnawave._parse_missing_dt` | `get_user_router.sync_user_keys_with_remnawave` |
| 6128 | `get_user_router.sync_user_keys_with_remnawave._check` | `get_user_router.sync_user_keys_with_remnawave` |
| 6173 | `get_user_router.manage_keys_handler` | `get_user_router` |
| 6198 | `get_user_router.sent_gifts_handler` | `get_user_router` |
| 6215 | `get_user_router.search_my_keys_handler` | `get_user_router` |
| 6225 | `get_user_router.search_keys_input_handler` | `get_user_router` |
| 6255 | `get_user_router.search_keys_page_handler` | `get_user_router` |
| 6279 | `get_user_router.cancel_search_keys_handler` | `get_user_router` |
| 6297 | `get_user_router.rename_key_start` | `get_user_router` |
| 6341 | `get_user_router.rename_key_process` | `get_user_router` |
| 6434 | `get_user_router.remove_key_name` | `get_user_router` |
| 6509 | `get_user_router.cancel_rename_key` | `get_user_router` |
| 6576 | `get_user_router.trial_period_handler` | `get_user_router` |
| 6607 | `get_user_router.trial_host_selection_handler` | `get_user_router` |
| 6612 | `get_user_router.process_trial_key_creation` | `get_user_router` |
| 6724 | `get_user_router.show_key_handler` | `get_user_router` |
| 6876 | `get_user_router.auto_renew_key_toggle` | `get_user_router` |
| 6898 | `get_user_router.toggle_auto_renew_profile` | `get_user_router` |
| 6912 | `get_user_router.switch_server_start` | `get_user_router` |
| 6943 | `get_user_router.select_host_for_switch` | `get_user_router` |
| 7079 | `get_user_router.show_qr_handler` | `get_user_router` |
| 7101 | `get_user_router.delete_device_handler` | `get_user_router` |
| 7203 | `get_user_router.show_instruction_handler` | `get_user_router` |
| 7216 | `get_user_router.show_instruction_handler` | `get_user_router` |
| 7228 | `get_user_router.howto_android_handler` | `get_user_router` |
| 7276 | `get_user_router.howto_android_key_handler` | `get_user_router` |
| 7304 | `get_user_router.howto_ios_handler` | `get_user_router` |
| 7326 | `get_user_router.howto_ios_key_handler` | `get_user_router` |
| 7354 | `get_user_router.howto_windows_handler` | `get_user_router` |
| 7406 | `get_user_router.howto_windows_key_handler` | `get_user_router` |
| 7438 | `get_user_router.howto_linux_handler` | `get_user_router` |
| 7463 | `get_user_router.howto_linux_key_handler` | `get_user_router` |
| 7494 | `get_user_router.gift_new_key_handler` | `get_user_router` |
| 7508 | `get_user_router.buy_new_key_handler` | `get_user_router` |
| 7522 | `get_user_router.select_host_for_purchase_handler` | `get_user_router` |
| 7535 | `get_user_router.select_host_for_gift_handler` | `get_user_router` |
| 7550 | `get_user_router.extend_key_handler` | `get_user_router` |
| 7590 | `get_user_router.plan_selection_handler` | `get_user_router` |
| 7616 | `get_user_router.back_to_plans_handler` | `get_user_router` |
| 7680 | `get_user_router.process_email_handler` | `get_user_router` |
| 7689 | `get_user_router.skip_email_handler` | `get_user_router` |
| 7694 | `get_user_router.show_payment_options` | `get_user_router` |
| 7821 | `get_user_router.back_to_email_prompt_handler` | `get_user_router` |
| 7835 | `get_user_router.prompt_promo_code` | `get_user_router` |
| 7844 | `get_user_router.cancel_promo_entry` | `get_user_router` |
| 7849 | `get_user_router.handle_promo_code_input` | `get_user_router` |
| 7888 | `get_user_router.create_yookassa_payment_handler` | `get_user_router` |
| 8026 | `get_user_router.pay_platega_handler` | `get_user_router` |
| 8114 | `get_user_router.pay_rollypay_handler` | `get_user_router` |
| 8202 | `get_user_router.create_cryptobot_invoice_handler` | `get_user_router` |
| 8279 | `get_user_router.check_crypto_invoice_handler` | `get_user_router` |
| 8406 | `get_user_router.create_ton_invoice_handler` | `get_user_router` |
| 8477 | `get_user_router.pay_with_main_balance_handler` | `get_user_router` |
| 8523 | `get_user_router.pay_with_referral_balance_handler` | `get_user_router` |
| 8578 | `get_user_router.stale_payment_method_callback` | `get_user_router` |
| 8594 | `get_user_router._gift_username_catcher` | `get_user_router` |
| 8723 | `get_user_router._kb_cancel_factory` | `get_user_router` |
| 8729 | `get_user_router._kb_partner_cabinet` | `get_user_router` |
| 8738 | `get_user_router._kb_partner_withdraw` | `get_user_router` |
| 8745 | `get_user_router._kb_partner_requisites` | `get_user_router` |
| 8762 | `get_user_router._kb_partner_requisite_input` | `get_user_router` |
| 8768 | `get_user_router._mask_requisite` | `get_user_router` |
| 8781 | `get_user_router._infer_requisite_type` | `get_user_router` |
| 8793 | `get_user_router.partner_requisites` | `get_user_router` |
| 8828 | `get_user_router.partner_requisite_add` | `get_user_router` |
| 8848 | `get_user_router.partner_requisite_cancel` | `get_user_router` |
| 8864 | `get_user_router.partner_requisite_bank` | `get_user_router` |
| 8889 | `get_user_router.partner_requisite_value` | `get_user_router` |
| 8937 | `get_user_router.partner_requisite_set_default` | `get_user_router` |
| 8970 | `get_user_router.partner_requisite_delete` | `get_user_router` |
| 9002 | `get_user_router.franchise_create_bot` | `get_user_router` |
| 9028 | `get_user_router.franchise_cancel` | `get_user_router` |
| 9041 | `get_user_router.franchise_receive_token` | `get_user_router` |
| 9104 | `get_user_router.partner_cabinet` | `get_user_router` |
| 9136 | `get_user_router.partner_withdraw` | `get_user_router` |
| 9174 | `get_user_router.partner_withdraw_cancel` | `get_user_router` |
| 9191 | `get_user_router.partner_withdraw_amount` | `get_user_router` |
| 9351 | `notify_admin_of_purchase._to_int` | `notify_admin_of_purchase` |
| 9415 | `process_successful_payment._provider_ids_for_log` | `process_successful_payment` |
| 9434 | `process_successful_payment._to_int` | `process_successful_payment` |

<a id="src-shop_bot-bot-admin_handlerspy"></a>

### `src/shop_bot/bot/admin_handlers.py`

Админ-меню Telegram: хосты, тарифы, пользователи, ключи, рассылка, speedtest, модули, бэкап, франшиза, промо.

**Импорт-путь:** `shop_bot.bot.admin_handlers`  
**Кто импортирует (прод):** `src/shop_bot/bot_controller.py`  
**Тесты:** 1 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 111 | `AdminSettings` | `StatesGroup` | — |
| 116 | `AdminModules` | `StatesGroup` | — |
| 119 | `Broadcast` | `StatesGroup` | — |
| 130 | `IsAdminFilter` | `BaseFilter` | Router-level gate for admin_router (aiogram 3.x BaseFilter). |
| 150 | `AdminAccessMiddleware` | `BaseMiddleware` | When a non-admin hits admin_router, answer the callback the same way |
| 521 | `ButtonConstructor` | `StatesGroup` | — |
| 1167 | `AdminPayments` | `StatesGroup` | — |
| 1593 | `AdminReferral` | `StatesGroup` | — |
| 1916 | `AdminFranchise` | `StatesGroup` | — |
| 2064 | `AdminHosts` | `StatesGroup` | — |
| 3011 | `AdminTrial` | `StatesGroup` | — |
| 3256 | `AdminLteSettings` | `StatesGroup` | — |
| 3337 | `AdminNotifications` | `StatesGroup` | — |
| 3499 | `AdminPlans` | `StatesGroup` | — |
| 4891 | `AdminPromoCreate` | `StatesGroup` | — |
| 5940 | `AdminRestoreDB` | `StatesGroup` | — |
| 6081 | `AdminUserSearch` | `StatesGroup` | — |
| 6763 | `AdminExtendSingleKey` | `StatesGroup` | — |
| 6846 | `AdminAddAdmin` | `StatesGroup` | — |
| 6924 | `AdminRemoveAdmin` | `StatesGroup` | — |
| 7120 | `AdminEditKeyEmail` | `StatesGroup` | — |
| 7161 | `AdminGiftKey` | `StatesGroup` | — |
| 7349 | `AdminMainRefill` | `StatesGroup` | — |
| 7499 | `AdminMainDeduct` | `StatesGroup` | — |
| 7604 | `AdminHostKeys` | `StatesGroup` | — |
| 7691 | `AdminQuickDeleteKey` | `StatesGroup` | — |
| 7732 | `AdminExtendKey` | `StatesGroup` | — |
| 8919 | `AdminAutoRenew` | `StatesGroup` | — |

**Функции верхнего уровня и методы классов:** 5

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 99 | `_is_true(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 103 | `_mask_secret(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 136 | `async IsAdminFilter.__call__(self, event, event_from_user)` | внутренний хелпер | из прод-кода **не вызывается** |
| 156 | `async AdminAccessMiddleware.__call__(self, handler, event, data)` | внутренний хелпер | из прод-кода **не вызывается** |
| 178 | `get_admin_router()` | — | `src/shop_bot/bot_controller.py::BotController.start`; тесты: 2 сайт(ов) |

**Вложенные функции** (362), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 186 | `get_admin_router._format_user_mention` | `get_admin_router` |
| 203 | `get_admin_router._resolve_target_from_hash` | `get_admin_router` |
| 222 | `get_admin_router.show_admin_menu` | `get_admin_router` |
| 260 | `get_admin_router.show_admin_promo_menu` | `get_admin_router` |
| 274 | `get_admin_router._parse_datetime_input` | `get_admin_router` |
| 285 | `get_admin_router._format_promo_line` | `get_admin_router` |
| 337 | `get_admin_router._build_promo_list_keyboard` | `get_admin_router` |
| 365 | `get_admin_router.show_admin_system_menu` | `get_admin_router` |
| 381 | `get_admin_router.show_admin_settings_menu` | `get_admin_router` |
| 397 | `get_admin_router._build_modules_keyboard` | `get_admin_router` |
| 415 | `get_admin_router.show_admin_modules_menu` | `get_admin_router` |
| 454 | `get_admin_router.open_admin_menu_handler` | `get_admin_router` |
| 461 | `get_admin_router.open_admin_system_menu_handler` | `get_admin_router` |
| 470 | `get_admin_router.open_admin_settings_menu_handler` | `get_admin_router` |
| 479 | `get_admin_router.open_admin_modules_menu_handler` | `get_admin_router` |
| 488 | `get_admin_router.refresh_admin_modules_menu_handler` | `get_admin_router` |
| 496 | `get_admin_router.admin_module_enable_handler` | `get_admin_router` |
| 507 | `get_admin_router.admin_module_disable_handler` | `get_admin_router` |
| 541 | `get_admin_router._btnc_menu_label` | `get_admin_router` |
| 547 | `get_admin_router._btnc_cancel_kb` | `get_admin_router` |
| 554 | `get_admin_router._btnc_show_menu_types` | `get_admin_router` |
| 573 | `get_admin_router._btnc_build_list_kb` | `get_admin_router` |
| 616 | `get_admin_router._btnc_show_list` | `get_admin_router` |
| 633 | `get_admin_router._btnc_build_details_kb` | `get_admin_router` |
| 647 | `get_admin_router._btnc_show_details` | `get_admin_router` |
| 693 | `get_admin_router.admin_button_constructor_root` | `get_admin_router` |
| 703 | `get_admin_router.btnc_select_menu_type` | `get_admin_router` |
| 713 | `get_admin_router.btnc_open_list` | `get_admin_router` |
| 728 | `get_admin_router.btnc_open_details` | `get_admin_router` |
| 745 | `get_admin_router.btnc_toggle_active` | `get_admin_router` |
| 765 | `get_admin_router.btnc_delete_confirm` | `get_admin_router` |
| 789 | `get_admin_router.btnc_delete_do` | `get_admin_router` |
| 807 | `get_admin_router.btnc_cancel_any` | `get_admin_router` |
| 814 | `get_admin_router.btnc_action_menu` | `get_admin_router` |
| 839 | `get_admin_router.btnc_edit_field_start` | `get_admin_router` |
| 869 | `get_admin_router.btnc_edit_field_value` | `get_admin_router` |
| 924 | `get_admin_router.btnc_add_start` | `get_admin_router` |
| 941 | `get_admin_router.btnc_add_button_id` | `get_admin_router` |
| 957 | `get_admin_router.btnc_add_text` | `get_admin_router` |
| 980 | `get_admin_router.btnc_add_action_type` | `get_admin_router` |
| 995 | `get_admin_router.btnc_add_action_value` | `get_admin_router` |
| 1029 | `get_admin_router.btnc_add_row` | `get_admin_router` |
| 1050 | `get_admin_router.btnc_add_col` | `get_admin_router` |
| 1076 | `get_admin_router.btnc_add_width` | `get_admin_router` |
| 1100 | `get_admin_router.btnc_add_sort` | `get_admin_router` |
| 1128 | `get_admin_router.btnc_add_finish` | `get_admin_router` |
| 1171 | `get_admin_router._get_payments_status_for_admin` | `get_admin_router` |
| 1215 | `get_admin_router.show_admin_payments_menu` | `get_admin_router` |
| 1228 | `get_admin_router._payment_detail_text` | `get_admin_router` |
| 1344 | `get_admin_router.show_admin_payment_detail` | `get_admin_router` |
| 1357 | `get_admin_router.admin_payments_menu` | `get_admin_router` |
| 1367 | `get_admin_router.admin_payments_open` | `get_admin_router` |
| 1379 | `get_admin_router.admin_payments_toggle` | `get_admin_router` |
| 1427 | `get_admin_router._payment_prompt` | `get_admin_router` |
| 1471 | `get_admin_router._normalize_payment_input` | `get_admin_router` |
| 1479 | `get_admin_router.admin_payments_set` | `get_admin_router` |
| 1505 | `get_admin_router.admin_payments_set_value` | `get_admin_router` |
| 1546 | `get_admin_router.admin_payments_yoomoney_check` | `get_admin_router` |
| 1602 | `get_admin_router._get_bool_setting` | `get_admin_router` |
| 1607 | `get_admin_router._get_float_setting` | `get_admin_router` |
| 1616 | `get_admin_router._get_referral_settings_for_admin` | `get_admin_router` |
| 1630 | `get_admin_router._format_reward_type_human` | `get_admin_router` |
| 1640 | `get_admin_router.show_admin_referral_menu` | `get_admin_router` |
| 1673 | `get_admin_router.admin_referral_menu_entry` | `get_admin_router` |
| 1683 | `get_admin_router.admin_referral_toggle` | `get_admin_router` |
| 1695 | `get_admin_router.admin_referral_toggle_days_bonus` | `get_admin_router` |
| 1707 | `get_admin_router.admin_referral_set_type` | `get_admin_router` |
| 1722 | `get_admin_router.admin_referral_type_chosen` | `get_admin_router` |
| 1743 | `get_admin_router.admin_referral_set_percent` | `get_admin_router` |
| 1758 | `get_admin_router.admin_referral_percent_input` | `get_admin_router` |
| 1777 | `get_admin_router.admin_referral_set_fixed_amount` | `get_admin_router` |
| 1792 | `get_admin_router.admin_referral_fixed_amount_input` | `get_admin_router` |
| 1811 | `get_admin_router.admin_referral_set_start_bonus` | `get_admin_router` |
| 1826 | `get_admin_router.admin_referral_start_bonus_input` | `get_admin_router` |
| 1847 | `get_admin_router.admin_referral_set_min_withdrawal` | `get_admin_router` |
| 1862 | `get_admin_router.admin_referral_min_withdrawal_input` | `get_admin_router` |
| 1881 | `get_admin_router.admin_referral_set_discount` | `get_admin_router` |
| 1896 | `get_admin_router.admin_referral_discount_input` | `get_admin_router` |
| 1922 | `get_admin_router._get_franchise_settings_for_admin` | `get_admin_router` |
| 1932 | `get_admin_router.show_admin_franchise_menu` | `get_admin_router` |
| 1957 | `get_admin_router.admin_franchise_menu_entry` | `get_admin_router` |
| 1969 | `get_admin_router.admin_franchise_toggle` | `get_admin_router` |
| 1996 | `get_admin_router.admin_franchise_set_percent` | `get_admin_router` |
| 2007 | `get_admin_router.admin_franchise_percent_input` | `get_admin_router` |
| 2028 | `get_admin_router.admin_franchise_set_min_withdraw` | `get_admin_router` |
| 2039 | `get_admin_router.admin_franchise_min_withdraw_input` | `get_admin_router` |
| 2086 | `get_admin_router._resolve_host_from_digest` | `get_admin_router` |
| 2105 | `get_admin_router._safe` | `get_admin_router` |
| 2109 | `get_admin_router._format_host_card` | `get_admin_router` |
| 2157 | `get_admin_router.show_admin_hosts_menu` | `get_admin_router` |
| 2170 | `get_admin_router.show_admin_host_detail` | `get_admin_router` |
| 2191 | `get_admin_router.show_admin_host_squads` | `get_admin_router` |
| 2212 | `get_admin_router.admin_hosts_menu` | `get_admin_router` |
| 2222 | `get_admin_router.admin_hosts_add` | `get_admin_router` |
| 2237 | `get_admin_router.admin_hosts_add_name` | `get_admin_router` |
| 2254 | `get_admin_router.admin_hosts_add_base_url` | `get_admin_router` |
| 2271 | `get_admin_router.admin_hosts_add_api_token` | `get_admin_router` |
| 2288 | `get_admin_router.admin_hosts_add_squad_uuid` | `get_admin_router` |
| 2342 | `get_admin_router.admin_hosts_open` | `get_admin_router` |
| 2376 | `get_admin_router.admin_hosts_squads_open` | `get_admin_router` |
| 2394 | `get_admin_router.admin_hosts_squad_toggle` | `get_admin_router` |
| 2426 | `get_admin_router.admin_hosts_squad_delete` | `get_admin_router` |
| 2451 | `get_admin_router.admin_hosts_squad_add` | `get_admin_router` |
| 2470 | `get_admin_router.admin_hosts_squad_add_class` | `get_admin_router` |
| 2494 | `get_admin_router.admin_hosts_squad2_uuid` | `get_admin_router` |
| 2513 | `get_admin_router.admin_hosts_squad2_label` | `get_admin_router` |
| 2561 | `get_admin_router.admin_hosts_delete` | `get_admin_router` |
| 2580 | `get_admin_router.admin_hosts_delete_confirm` | `get_admin_router` |
| 2601 | `get_admin_router.admin_hosts_rename` | `get_admin_router` |
| 2622 | `get_admin_router.admin_hosts_toggle_class` | `get_admin_router` |
| 2663 | `get_admin_router.admin_hosts_rename_input` | `get_admin_router` |
| 2688 | `get_admin_router.admin_hosts_set_url` | `get_admin_router` |
| 2708 | `get_admin_router.admin_hosts_set_url_input` | `get_admin_router` |
| 2732 | `get_admin_router.admin_hosts_set_sub` | `get_admin_router` |
| 2753 | `get_admin_router.admin_hosts_set_sub_input` | `get_admin_router` |
| 2774 | `get_admin_router.admin_hosts_set_rmw_url` | `get_admin_router` |
| 2794 | `get_admin_router.admin_hosts_set_rmw_url_input` | `get_admin_router` |
| 2818 | `get_admin_router.admin_hosts_set_rmw_token` | `get_admin_router` |
| 2839 | `get_admin_router.admin_hosts_set_rmw_token_input` | `get_admin_router` |
| 2860 | `get_admin_router.admin_hosts_set_squad` | `get_admin_router` |
| 2880 | `get_admin_router.admin_hosts_set_squad_input` | `get_admin_router` |
| 2901 | `get_admin_router.admin_hosts_set_ssh` | `get_admin_router` |
| 2925 | `get_admin_router.admin_hosts_set_ssh_input` | `get_admin_router` |
| 2963 | `get_admin_router.admin_hosts_set_ssh_input._n` | `get_admin_router.admin_hosts_set_ssh_input` |
| 2986 | `get_admin_router.admin_hosts_to_plans` | `get_admin_router` |
| 3018 | `get_admin_router._get_trial_enabled` | `get_admin_router` |
| 3022 | `get_admin_router._format_trial_value_gb` | `get_admin_router` |
| 3035 | `get_admin_router._format_trial_value_int` | `get_admin_router` |
| 3044 | `get_admin_router._get_trial_days` | `get_admin_router` |
| 3058 | `get_admin_router.show_admin_trial_menu` | `get_admin_router` |
| 3099 | `get_admin_router.admin_trial_entry` | `get_admin_router` |
| 3110 | `get_admin_router.admin_trial_toggle` | `get_admin_router` |
| 3122 | `get_admin_router.admin_trial_set_days` | `get_admin_router` |
| 3136 | `get_admin_router.admin_trial_set_traffic` | `get_admin_router` |
| 3151 | `get_admin_router.admin_trial_set_devices` | `get_admin_router` |
| 3166 | `get_admin_router.admin_trial_set_host` | `get_admin_router` |
| 3182 | `get_admin_router.admin_trial_select_host` | `get_admin_router` |
| 3194 | `get_admin_router.admin_trial_days_input` | `get_admin_router` |
| 3213 | `get_admin_router.admin_trial_traffic_input` | `get_admin_router` |
| 3236 | `get_admin_router.admin_trial_devices_input` | `get_admin_router` |
| 3261 | `get_admin_router._get_dual_limit_interval` | `get_admin_router` |
| 3269 | `get_admin_router.show_admin_lte_settings_menu` | `get_admin_router` |
| 3290 | `get_admin_router.admin_lte_settings_entry` | `get_admin_router` |
| 3301 | `get_admin_router.admin_lte_set_interval_start` | `get_admin_router` |
| 3316 | `get_admin_router.admin_lte_set_interval_received` | `get_admin_router` |
| 3342 | `get_admin_router._get_inactive_reminder_enabled` | `get_admin_router` |
| 3345 | `get_admin_router._get_inactive_reminder_interval_hours` | `get_admin_router` |
| 3357 | `get_admin_router._get_inactive_reminder_support_url` | `get_admin_router` |
| 3361 | `get_admin_router.show_admin_notifications_menu` | `get_admin_router` |
| 3394 | `get_admin_router.admin_notifications_entry` | `get_admin_router` |
| 3405 | `get_admin_router.admin_inactive_reminder_toggle` | `get_admin_router` |
| 3417 | `get_admin_router.admin_inactive_reminder_set_interval` | `get_admin_router` |
| 3434 | `get_admin_router.admin_inactive_reminder_interval_input` | `get_admin_router` |
| 3455 | `get_admin_router.admin_inactive_reminder_set_support_url` | `get_admin_router` |
| 3473 | `get_admin_router.admin_inactive_reminder_support_url_input` | `get_admin_router` |
| 3536 | `get_admin_router._format_plan_duration` | `get_admin_router` |
| 3550 | `get_admin_router._format_traffic_gb` | `get_admin_router` |
| 3566 | `get_admin_router._format_devices` | `get_admin_router` |
| 3578 | `get_admin_router._plan_show_name_enabled` | `get_admin_router` |
| 3586 | `get_admin_router._format_plans_for_host` | `get_admin_router` |
| 3611 | `get_admin_router.admin_plans_entry` | `get_admin_router` |
| 3627 | `get_admin_router.admin_plans_back_to_admin` | `get_admin_router` |
| 3637 | `get_admin_router.admin_plans_pick_host` | `get_admin_router` |
| 3652 | `get_admin_router._format_plan_detail` | `get_admin_router` |
| 3688 | `get_admin_router.admin_plans_open_plan` | `get_admin_router` |
| 3722 | `get_admin_router._format_traffic_package_detail` | `get_admin_router` |
| 3746 | `get_admin_router.admin_plan_packages_menu` | `get_admin_router` |
| 3779 | `get_admin_router.admin_lte_packages_menu` | `get_admin_router` |
| 3814 | `get_admin_router.admin_plan_edit_lte_limit_start` | `get_admin_router` |
| 3827 | `get_admin_router.admin_plan_edit_lte_limit_received` | `get_admin_router` |
| 3873 | `get_admin_router.admin_plan_edit_main_reset_price_start` | `get_admin_router` |
| 3887 | `get_admin_router.admin_plan_edit_main_reset_price_received` | `get_admin_router` |
| 3932 | `get_admin_router.admin_pkg_add_start` | `get_admin_router` |
| 3960 | `get_admin_router.admin_pkg_size_received` | `get_admin_router` |
| 3977 | `get_admin_router.admin_pkg_price_received` | `get_admin_router` |
| 4006 | `get_admin_router.admin_pkg_open` | `get_admin_router` |
| 4031 | `get_admin_router.admin_pkg_edit_size_start` | `get_admin_router` |
| 4044 | `get_admin_router.admin_pkg_edit_size_received` | `get_admin_router` |
| 4070 | `get_admin_router.admin_pkg_edit_price_start` | `get_admin_router` |
| 4083 | `get_admin_router.admin_pkg_edit_price_received` | `get_admin_router` |
| 4109 | `get_admin_router.admin_pkg_toggle` | `get_admin_router` |
| 4135 | `get_admin_router.admin_pkg_delete` | `get_admin_router` |
| 4158 | `get_admin_router.admin_plan_edit_name` | `get_admin_router` |
| 4172 | `get_admin_router.admin_plan_edit_months` | `get_admin_router` |
| 4187 | `get_admin_router.admin_plan_edit_price` | `get_admin_router` |
| 4202 | `get_admin_router.admin_plan_edit_duration` | `get_admin_router` |
| 4216 | `get_admin_router.admin_plan_duration_months` | `get_admin_router` |
| 4227 | `get_admin_router.admin_plan_duration_days` | `get_admin_router` |
| 4238 | `get_admin_router.admin_plan_edit_traffic` | `get_admin_router` |
| 4252 | `get_admin_router.admin_plan_edit_devices` | `get_admin_router` |
| 4266 | `get_admin_router.admin_plan_toggle_active` | `get_admin_router` |
| 4295 | `get_admin_router.admin_plan_toggle_show_name` | `get_admin_router` |
| 4331 | `get_admin_router.admin_plan_delete_start` | `get_admin_router` |
| 4345 | `get_admin_router.admin_plan_delete_cancel` | `get_admin_router` |
| 4351 | `get_admin_router.admin_plan_delete_confirm` | `get_admin_router` |
| 4384 | `get_admin_router.admin_plan_edit_name_received` | `get_admin_router` |
| 4412 | `get_admin_router.admin_plan_edit_months_received` | `get_admin_router` |
| 4445 | `get_admin_router.admin_plan_edit_price_received` | `get_admin_router` |
| 4479 | `get_admin_router.admin_plan_edit_days_received` | `get_admin_router` |
| 4519 | `get_admin_router.admin_plan_edit_traffic_received` | `get_admin_router` |
| 4564 | `get_admin_router.admin_plan_edit_devices_received` | `get_admin_router` |
| 4607 | `get_admin_router.admin_plans_back_to_hosts` | `get_admin_router` |
| 4622 | `get_admin_router.admin_plans_add_start` | `get_admin_router` |
| 4646 | `get_admin_router.admin_plans_new_duration_months` | `get_admin_router` |
| 4661 | `get_admin_router.admin_plans_new_duration_days` | `get_admin_router` |
| 4675 | `get_admin_router.admin_plans_back_to_host_menu` | `get_admin_router` |
| 4701 | `get_admin_router.admin_plans_plan_name_received` | `get_admin_router` |
| 4727 | `get_admin_router.admin_plans_months_received` | `get_admin_router` |
| 4757 | `get_admin_router.admin_plan_add_days_received` | `get_admin_router` |
| 4780 | `get_admin_router.admin_plan_add_traffic_received` | `get_admin_router` |
| 4807 | `get_admin_router.admin_plan_add_devices_received` | `get_admin_router` |
| 4830 | `get_admin_router.admin_plans_price_received` | `get_admin_router` |
| 4906 | `get_admin_router.admin_promo_menu_handler` | `get_admin_router` |
| 4915 | `get_admin_router.admin_promo_create_start` | `get_admin_router` |
| 4931 | `get_admin_router.admin_promo_code_auto` | `get_admin_router` |
| 4956 | `get_admin_router.admin_promo_code_custom` | `get_admin_router` |
| 4968 | `get_admin_router.admin_promo_create_code` | `get_admin_router` |
| 4990 | `get_admin_router.admin_promo_set_discount_type` | `get_admin_router` |
| 5002 | `get_admin_router.admin_promo_set_discount_value` | `get_admin_router` |
| 5027 | `get_admin_router.admin_promo_set_total_limit` | `get_admin_router` |
| 5053 | `get_admin_router.admin_promo_total_limit_buttons` | `get_admin_router` |
| 5077 | `get_admin_router.admin_promo_user_limit_buttons` | `get_admin_router` |
| 5098 | `get_admin_router.admin_promo_set_per_user_limit` | `get_admin_router` |
| 5121 | `get_admin_router.admin_promo_set_valid_from` | `get_admin_router` |
| 5147 | `get_admin_router.admin_promo_valid_from_buttons` | `get_admin_router` |
| 5175 | `get_admin_router.admin_promo_set_valid_until` | `get_admin_router` |
| 5206 | `get_admin_router.admin_promo_valid_until_buttons` | `get_admin_router` |
| 5236 | `get_admin_router.admin_promo_description` | `get_admin_router` |
| 5252 | `get_admin_router.admin_promo_desc_buttons` | `get_admin_router` |
| 5271 | `get_admin_router._show_promo_confirm` | `get_admin_router` |
| 5327 | `get_admin_router.admin_promo_set_segment` | `get_admin_router` |
| 5356 | `get_admin_router.admin_promo_set_segment_value` | `get_admin_router` |
| 5379 | `get_admin_router.admin_promo_set_plans` | `get_admin_router` |
| 5394 | `get_admin_router.admin_promo_set_plans_custom` | `get_admin_router` |
| 5412 | `get_admin_router.admin_promo_confirm` | `get_admin_router` |
| 5461 | `get_admin_router.admin_promo_list` | `get_admin_router` |
| 5481 | `get_admin_router.admin_promo_change_page` | `get_admin_router` |
| 5506 | `get_admin_router.admin_promo_toggle` | `get_admin_router` |
| 5536 | `get_admin_router.admin_speedtest_entry` | `get_admin_router` |
| 5556 | `get_admin_router.admin_speedtest_ssh_targets` | `get_admin_router` |
| 5575 | `get_admin_router.admin_speedtest_run` | `get_admin_router` |
| 5609 | `get_admin_router.admin_speedtest_run.fmt_part` | `get_admin_router.admin_speedtest_run` |
| 5663 | `get_admin_router.admin_speedtest_run_target_hashed` | `get_admin_router` |
| 5734 | `get_admin_router.admin_speedtest_run_target` | `get_admin_router` |
| 5805 | `get_admin_router.admin_speedtest_back` | `get_admin_router` |
| 5814 | `get_admin_router.admin_speedtest_run_all` | `get_admin_router` |
| 5859 | `get_admin_router.admin_speedtest_run_all_targets` | `get_admin_router` |
| 5909 | `get_admin_router.admin_backup_db` | `get_admin_router` |
| 5944 | `get_admin_router.admin_restore_db_prompt` | `get_admin_router` |
| 5964 | `get_admin_router.admin_restore_db_receive` | `get_admin_router` |
| 5992 | `get_admin_router.admin_speedtest_autoinstall` | `get_admin_router` |
| 6017 | `get_admin_router.admin_speedtest_autoinstall_target` | `get_admin_router` |
| 6049 | `get_admin_router.admin_speedtest_autoinstall_target_hashed` | `get_admin_router` |
| 6085 | `get_admin_router.admin_users_handler` | `get_admin_router` |
| 6117 | `get_admin_router.admin_users_search_process` | `get_admin_router` |
| 6205 | `get_admin_router.admin_view_user_handler` | `get_admin_router` |
| 6251 | `get_admin_router.admin_ban_user` | `get_admin_router` |
| 6332 | `get_admin_router.admin_admins_menu_entry` | `get_admin_router` |
| 6343 | `get_admin_router.admin_view_admins` | `get_admin_router` |
| 6381 | `get_admin_router.admin_unban_user` | `get_admin_router` |
| 6444 | `get_admin_router.admin_delete_user` | `get_admin_router` |
| 6467 | `get_admin_router.admin_user_keys` | `get_admin_router` |
| 6494 | `get_admin_router.admin_user_referrals` | `get_admin_router` |
| 6542 | `get_admin_router.admin_search_user_keys_handler` | `get_admin_router` |
| 6565 | `get_admin_router.admin_search_user_keys_input_handler` | `get_admin_router` |
| 6606 | `get_admin_router.admin_search_keys_page_handler` | `get_admin_router` |
| 6634 | `get_admin_router.admin_search_all_keys_handler` | `get_admin_router` |
| 6650 | `get_admin_router.admin_search_all_keys_input_handler` | `get_admin_router` |
| 6682 | `get_admin_router.admin_cancel_search_keys_handler` | `get_admin_router` |
| 6696 | `get_admin_router.admin_edit_key` | `get_admin_router` |
| 6733 | `get_admin_router.admin_key_delete_prompt` | `get_admin_router` |
| 6767 | `get_admin_router.admin_key_extend_prompt` | `get_admin_router` |
| 6786 | `get_admin_router.admin_key_extend_process` | `get_admin_router` |
| 6850 | `get_admin_router.admin_add_admin_entry` | `get_admin_router` |
| 6863 | `get_admin_router.admin_add_admin_process` | `get_admin_router` |
| 6928 | `get_admin_router.admin_remove_admin_entry` | `get_admin_router` |
| 6941 | `get_admin_router.admin_remove_admin_process` | `get_admin_router` |
| 7013 | `get_admin_router.admin_key_delete_cancel` | `get_admin_router` |
| 7051 | `get_admin_router.admin_key_delete_confirm` | `get_admin_router` |
| 7124 | `get_admin_router.admin_key_edit_email_start` | `get_admin_router` |
| 7142 | `get_admin_router.admin_key_edit_email_commit` | `get_admin_router` |
| 7167 | `get_admin_router.admin_gift_key_entry` | `get_admin_router` |
| 7182 | `get_admin_router.admin_gift_key_for_user` | `get_admin_router` |
| 7202 | `get_admin_router.admin_gift_pick_user_page` | `get_admin_router` |
| 7218 | `get_admin_router.admin_gift_pick_user` | `get_admin_router` |
| 7237 | `get_admin_router.admin_gift_back_to_users` | `get_admin_router` |
| 7250 | `get_admin_router.admin_gift_pick_host` | `get_admin_router` |
| 7264 | `get_admin_router.admin_gift_back_to_hosts` | `get_admin_router` |
| 7278 | `get_admin_router.admin_gift_pick_days` | `get_admin_router` |
| 7354 | `get_admin_router.admin_add_balance_entry` | `get_admin_router` |
| 7366 | `get_admin_router.admin_add_balance_user` | `get_admin_router` |
| 7385 | `get_admin_router.admin_add_balance_pick_user_page` | `get_admin_router` |
| 7402 | `get_admin_router.admin_add_balance_pick_user` | `get_admin_router` |
| 7420 | `get_admin_router.handle_main_amount` | `get_admin_router` |
| 7450 | `get_admin_router.admin_key_back` | `get_admin_router` |
| 7489 | `get_admin_router.admin_noop` | `get_admin_router` |
| 7493 | `get_admin_router.admin_cancel_handler` | `get_admin_router` |
| 7504 | `get_admin_router.admin_deduct_balance_entry` | `get_admin_router` |
| 7517 | `get_admin_router.admin_deduct_balance_user` | `get_admin_router` |
| 7536 | `get_admin_router.admin_deduct_balance_pick_user_page` | `get_admin_router` |
| 7553 | `get_admin_router.admin_deduct_balance_pick_user` | `get_admin_router` |
| 7571 | `get_admin_router.handle_deduct_amount` | `get_admin_router` |
| 7608 | `get_admin_router.admin_host_keys_entry` | `get_admin_router` |
| 7622 | `get_admin_router.admin_host_keys_pick_host` | `get_admin_router` |
| 7640 | `get_admin_router.admin_hostkeys_page` | `get_admin_router` |
| 7666 | `get_admin_router.admin_hostkeys_back_to_hosts` | `get_admin_router` |
| 7683 | `get_admin_router.admin_hostkeys_back_to_users` | `get_admin_router` |
| 7695 | `get_admin_router.admin_delete_key_entry` | `get_admin_router` |
| 7707 | `get_admin_router.admin_delete_key_process` | `get_admin_router` |
| 7736 | `get_admin_router.admin_extend_key_entry` | `get_admin_router` |
| 7748 | `get_admin_router.admin_extend_key_process` | `get_admin_router` |
| 7799 | `get_admin_router.start_broadcast_handler` | `get_admin_router` |
| 7813 | `get_admin_router.broadcast_message_received_handler` | `get_admin_router` |
| 7817 | `get_admin_router.broadcast_message_received_handler._msg_json_default` | `get_admin_router.broadcast_message_received_handler` |
| 7826 | `get_admin_router.broadcast_message_received_handler._detect_parse_mode` | `get_admin_router.broadcast_message_received_handler` |
| 7870 | `get_admin_router.broadcast_parse_mode_handler` | `get_admin_router` |
| 7883 | `get_admin_router.add_button_choose_type` | `get_admin_router` |
| 7892 | `get_admin_router.add_button_prompt_handler` | `get_admin_router` |
| 7901 | `get_admin_router.add_functional_button_start` | `get_admin_router` |
| 7910 | `get_admin_router.functional_button_selected` | `get_admin_router` |
| 7919 | `get_admin_router.button_text_received_handler` | `get_admin_router` |
| 7928 | `get_admin_router.button_url_received_handler` | `get_admin_router` |
| 7939 | `get_admin_router.skip_button_handler` | `get_admin_router` |
| 7944 | `get_admin_router._escape_md2` | `get_admin_router` |
| 7958 | `get_admin_router._escape_md2._esc` | `get_admin_router._escape_md2` |
| 7969 | `get_admin_router._send_broadcast_to` | `get_admin_router` |
| 8006 | `get_admin_router.show_broadcast_preview` | `get_admin_router` |
| 8039 | `get_admin_router.confirm_broadcast_handler` | `get_admin_router` |
| 8109 | `get_admin_router.cancel_broadcast_handler` | `get_admin_router` |
| 8116 | `get_admin_router.approve_withdraw_handler` | `get_admin_router` |
| 8137 | `get_admin_router.decline_withdraw_handler` | `get_admin_router` |
| 8152 | `get_admin_router.admin_monitor_menu` | `get_admin_router` |
| 8186 | `get_admin_router.admin_monitor_local` | `get_admin_router` |
| 8285 | `get_admin_router.admin_monitor_local.get_status_emoji` | `get_admin_router.admin_monitor_local` |
| 8293 | `get_admin_router.admin_monitor_local.format_bytes` | `get_admin_router.admin_monitor_local` |
| 8302 | `get_admin_router.admin_monitor_local.format_uptime` | `get_admin_router.admin_monitor_local` |
| 8357 | `get_admin_router.admin_monitor_host` | `get_admin_router` |
| 8400 | `get_admin_router.admin_monitor_host.get_status_emoji` | `get_admin_router.admin_monitor_host` |
| 8410 | `get_admin_router.admin_monitor_host.format_uptime` | `get_admin_router.admin_monitor_host` |
| 8423 | `get_admin_router.admin_monitor_host.format_loadavg` | `get_admin_router.admin_monitor_host` |
| 8465 | `get_admin_router.admin_monitor_target` | `get_admin_router` |
| 8530 | `get_admin_router.admin_monitor_target.get_status_emoji` | `get_admin_router.admin_monitor_target` |
| 8540 | `get_admin_router.admin_monitor_target.format_uptime` | `get_admin_router.admin_monitor_target` |
| 8553 | `get_admin_router.admin_monitor_target.format_loadavg` | `get_admin_router.admin_monitor_target` |
| 8595 | `get_admin_router.admin_monitor_detailed` | `get_admin_router` |
| 8616 | `get_admin_router.admin_monitor_detailed.format_bytes` | `get_admin_router.admin_monitor_detailed` |
| 8625 | `get_admin_router.admin_monitor_detailed.format_uptime` | `get_admin_router.admin_monitor_detailed` |
| 8730 | `get_admin_router.admin_captcha_settings_handler` | `get_admin_router` |
| 8767 | `get_admin_router.admin_captcha_toggle_handler` | `get_admin_router` |
| 8781 | `get_admin_router.admin_captcha_type_handler` | `get_admin_router` |
| 8806 | `get_admin_router.admin_captcha_type_set_handler` | `get_admin_router` |
| 8820 | `get_admin_router.admin_captcha_attempts_handler` | `get_admin_router` |
| 8834 | `get_admin_router.admin_captcha_attempts_input_handler` | `get_admin_router` |
| 8853 | `get_admin_router.admin_captcha_timeout_handler` | `get_admin_router` |
| 8867 | `get_admin_router.admin_captcha_timeout_input_handler` | `get_admin_router` |
| 8886 | `get_admin_router.admin_captcha_message_handler` | `get_admin_router` |
| 8900 | `get_admin_router.admin_captcha_message_input_handler` | `get_admin_router` |
| 8922 | `get_admin_router.show_admin_auto_renew_menu` | `get_admin_router` |
| 8947 | `get_admin_router.admin_auto_renew_entry` | `get_admin_router` |
| 8957 | `get_admin_router.admin_auto_renew_toggle` | `get_admin_router` |
| 8969 | `get_admin_router.admin_auto_renew_set_hours` | `get_admin_router` |
| 8980 | `get_admin_router.admin_auto_renew_hours_input` | `get_admin_router` |

<a id="src-shop_bot-bot-keyboardspy"></a>

### `src/shop_bot/bot/keyboards.py`

Сборщики InlineKeyboardMarkup для пользовательских и админских экранов, в том числе динамические кнопки из button_configs.

**Импорт-путь:** `shop_bot.bot.keyboards`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 3 файл(ов)

**Функции верхнего уровня и методы классов:** 112

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 28 | `_normalize_url(url)` | внутренний хелпер | из прод-кода **не вызывается** |
| 40 | `_get_notifications_support_url()` | Support URL for inactive usage reminder notifications (admin-configurable). | из прод-кода **не вызывается** |
| 46 | `_ru_days(n)` | Русское склонение слова "день". | из прод-кода **не вызывается** |
| 63 | `create_main_menu_keyboard(user_keys, trial_available, is_admin, show_create_bot, show_partner_cabinet, gifts_count)` | — | `src/shop_bot/bot/handlers.py::show_main_menu` |
| 171 | `create_admin_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_menu` |
| 189 | `create_admin_system_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_system_menu` |
| 201 | `create_admin_settings_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_settings_menu`; тесты: 1 сайт(ов) |
| 221 | `create_admin_lte_settings_keyboard(dual_limit_interval_sec)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_lte_settings_menu` |
| 230 | `create_admin_payments_menu_keyboard(status)` | Меню выбора платежной системы. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_payments_menu` |
| 248 | `create_admin_payment_detail_keyboard(provider, flags)` | Клавиатура управления конкретной платежкой. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_payment_detail` |
| 299 | `create_admin_payments_cancel_keyboard(back_callback)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_payments_set` |
| 305 | `create_admin_referral_settings_keyboard(enabled, days_bonus_enabled, reward_type)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_referral_menu` |
| 341 | `create_admin_franchise_settings_keyboard(enabled)` | Создаёт клавиатуру настроек франшизы | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_franchise_menu` |
| 360 | `create_admin_auto_renew_keyboard(enabled)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_auto_renew_menu` |
| 370 | `create_admin_referral_type_keyboard(current_type)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_set_type` |
| 390 | `_host_digest(host_name)` | Safe stable digest for callback_data. | из прод-кода **не вызывается** |
| 400 | `create_admin_hosts_menu_keyboard(hosts)` | Hosts list + add button. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_hosts_menu` |
| 421 | `create_admin_host_manage_keyboard(host_digest, node_class)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_host_detail` |
| 445 | `create_admin_hosts_cancel_keyboard(back_cb)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add_name`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add_base_url`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add_api_token`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad_add_class`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad2_uuid`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_rename`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_url`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_sub`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_rmw_url`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_rmw_token`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_squad` и ещё 1 |
| 452 | `create_admin_hosts_delete_confirm_keyboard(host_digest)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_delete` |
| 460 | `create_admin_host_squads_keyboard(host_digest, squads)` | Список сквадов хоста с переключением активности и удалением. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_host_squads` |
| 491 | `create_admin_squad_class_keyboard(host_digest)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad_add` |
| 502 | `create_admin_trial_settings_keyboard(trial_enabled, days, traffic_text, devices_text, default_host)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_trial_menu` |
| 531 | `create_admin_trial_host_keyboard(hosts)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_set_host` |
| 542 | `create_admin_notifications_settings_keyboard(enabled, interval_hours, support_url)` | Настройки уведомлений о неиспользовании трафика. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_notifications_menu` |
| 571 | `create_admin_plans_host_menu_keyboard(plans)` | Меню тарифов для выбранного хоста (админка). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_to_plans`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_pick_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_back_to_host_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_delete_confirm` |
| 622 | `create_admin_plan_manage_keyboard(plan)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_open_plan`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_lte_limit_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_main_reset_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_toggle_active`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_toggle_show_name`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_name_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_months_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_days_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_traffic_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_devices_received` |
| 677 | `create_admin_traffic_packages_keyboard(plan_id, packages, pool)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_packages_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_lte_packages_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_delete` |
| 703 | `create_admin_traffic_package_manage_keyboard(package_id, plan_id, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_open`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_size_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_toggle` |
| 716 | `create_admin_plans_duration_type_keyboard()` | Выбор единиц срока тарифа при создании. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_plan_name_received` |
| 727 | `create_admin_plan_duration_type_keyboard()` | Выбор единиц срока тарифа при редактировании. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_months`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_duration` |
| 737 | `create_admin_plan_delete_confirm_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_delete_start` |
| 746 | `create_admin_plan_edit_flow_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_lte_limit_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_main_reset_price_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_add_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_size_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_price_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_name`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_price`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_duration_months`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_duration_days`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_traffic`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_devices`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_name_received` и ещё 5 |
| 754 | `create_admin_plans_flow_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_add_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_new_duration_months`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_new_duration_days`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_months_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_add_days_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_add_traffic_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_add_devices_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_plan_name_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_price_received` |
| 761 | `create_admins_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_admins_menu_entry` |
| 770 | `create_admin_users_keyboard(users, page, page_size)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_search_process` |
| 798 | `create_admin_user_actions_keyboard(user_id, is_banned)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_view_user_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_search_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_ban_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_unban_user` |
| 816 | `create_keys_management_keyboard(keys, page, gift_keys)` | Клавиатура списка ключей пользователя (раздел 'Мои ключи') с пагинацией. | `src/shop_bot/bot/handlers.py::get_user_router.manage_keys_handler`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_search_keys_handler`, `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process`, `src/shop_bot/bot/handlers.py::get_user_router.remove_key_name`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_rename_key` |
| 866 | `create_sent_gifts_keyboard(gift_keys, page)` | Клавиатура раздела «Отправленные подарки». | `src/shop_bot/bot/handlers.py::get_user_router.sent_gifts_handler` |
| 905 | `create_admin_user_keys_keyboard(user_id, keys, page)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_user_keys`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_back`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm` |
| 954 | `create_admin_key_actions_keyboard(key_id, user_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_extend_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_edit_key`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_cancel` |
| 966 | `create_admin_delete_key_confirm_keyboard(key_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_delete_key_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_prompt` |
| 973 | `create_cancel_keyboard(callback)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_set_percent`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_set_fixed_amount`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_set_start_bonus`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_set_min_withdrawal`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_set_discount`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_set_days`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_set_traffic`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_set_devices`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_lte_set_interval_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_inactive_reminder_set_interval`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_inactive_reminder_set_support_url`, `src/shop_bot/bot/handlers.py::get_user_router.prompt_promo_code` |
| 979 | `create_admin_cancel_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_code_custom`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_discount_type`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_per_user_limit`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_segment`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_plans`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_cancel_search_keys_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_extend_prompt`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_admin_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_remove_admin_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_edit_email_start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_balance_user` и ещё 20 |
| 983 | `create_admin_promo_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_promo_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_confirm` |
| 992 | `create_admin_promo_discount_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_create_code`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_code_auto` |
| 1000 | `create_admin_promo_code_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_create_start` |
| 1008 | `create_admin_promo_limit_keyboard(kind)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_discount_value`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_total_limit`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_total_limit_buttons` |
| 1020 | `create_admin_promo_valid_from_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_user_limit_buttons` |
| 1031 | `create_admin_promo_valid_until_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_valid_from`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_valid_from_buttons` |
| 1042 | `create_admin_promo_description_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_valid_until`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_valid_until_buttons` |
| 1051 | `create_admin_promo_segment_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_description`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_desc_buttons` |
| 1061 | `create_admin_promo_plans_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_segment_value`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_set_segment` |
| 1069 | `create_broadcast_parse_mode_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.broadcast_message_received_handler` |
| 1079 | `create_broadcast_options_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.broadcast_parse_mode_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.broadcast_message_received_handler` |
| 1087 | `create_broadcast_confirmation_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_broadcast_preview` |
| 1094 | `create_broadcast_cancel_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.start_broadcast_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.add_button_prompt_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.button_text_received_handler` |
| 1099 | `create_about_keyboard(channel_url, terms_url, privacy_url)` | — | `src/shop_bot/bot/handlers.py::get_user_router.about_handler` |
| 1114 | `create_support_keyboard(support_user)` | Кнопка техподдержки (всегда ведёт на фиксированный URL). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.handle_deduct_amount`, `src/shop_bot/bot/handlers.py::_notify_user_key_creation_error`, `src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`, `src/shop_bot/bot/handlers.py::get_user_router.support_external_handler`, `src/shop_bot/bot/handlers.py::get_user_router.about_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_menu_handler`, `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 1125 | `create_support_bot_link_keyboard(support_bot_username)` | — | `src/shop_bot/bot/handlers.py::get_user_router.about_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_menu_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_external_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_new_ticket_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_subject_received`, `src/shop_bot/bot/handlers.py::get_user_router.support_message_received`, `src/shop_bot/bot/handlers.py::get_user_router.support_my_tickets_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_view_ticket_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_reply_prompt_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_reply_received`, `src/shop_bot/bot/handlers.py::get_user_router.support_close_ticket_handler` |
| 1135 | `create_inactive_usage_reminder_keyboard(connection_string)` | Клавиатура для напоминания, если пользователь не подключил устройство. | `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 1164 | `create_support_menu_keyboard(has_external)` | — | из прод-кода **не вызывается** |
| 1174 | `create_tickets_list_keyboard(tickets)` | — | из прод-кода **не вызывается** |
| 1186 | `create_ticket_actions_keyboard(ticket_id, is_open)` | — | из прод-кода **не вызывается** |
| 1195 | `create_host_selection_keyboard(hosts, action)` | — | `src/shop_bot/bot/handlers.py::get_user_router.switch_server_start`, `src/shop_bot/bot/handlers.py::get_user_router.gift_new_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.buy_new_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.trial_period_handler` |
| 1204 | `create_plans_keyboard(plans, action, host_name, key_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_purchase_handler`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_gift_handler`, `src/shop_bot/bot/handlers.py::get_user_router.extend_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.back_to_plans_handler` |
| 1257 | `create_payment_method_keyboard(payment_methods, action, key_id, show_balance, main_balance, referral_balance, price, promo_applied)` | — | `src/shop_bot/bot/handlers.py::get_user_router.show_payment_options` |
| 1346 | `create_skip_email_keyboard()` | — | `src/shop_bot/bot/handlers.py::get_user_router.back_to_email_prompt_handler`, `src/shop_bot/bot/handlers.py::get_user_router.plan_selection_handler` |
| 1353 | `create_stars_invoice_keyboard()` | Кнопки под системной Pay ⭐: сначала Pay (требование Telegram), затем Назад. | `src/shop_bot/bot/handlers.py::get_user_router.create_stars_invoice_handler`; тесты: 1 сайт(ов) |
| 1362 | `create_ton_connect_keyboard(connect_url)` | — | `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_tonconnect`, `src/shop_bot/bot/handlers.py::get_user_router.create_ton_invoice_handler` |
| 1369 | `create_payment_keyboard(payment_url)` | — | `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_heleket_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_heleket_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_heleket_like`, `src/shop_bot/webapp/handlers.py::api_create_payment`, `src/shop_bot/webapp/handlers.py::api_create_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 1376 | `create_yoomoney_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_yoomoney_handler`, `src/shop_bot/webapp/handlers.py::api_create_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1384 | `create_yookassa_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_yookassa_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_yookassa_handler`, `src/shop_bot/bot/handlers.py::get_user_router.mainreset_pay_yookassa_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_yookassa`, `src/shop_bot/bot/handlers.py::get_user_router.create_yookassa_payment_handler` |
| 1392 | `create_platega_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_platega_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_platega_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_platega`, `src/shop_bot/bot/handlers.py::get_user_router.pay_platega_handler` |
| 1401 | `create_rollypay_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_rollypay_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_rollypay_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_rollypay`, `src/shop_bot/bot/handlers.py::get_user_router.pay_rollypay_handler` |
| 1410 | `create_cryptobot_payment_keyboard(payment_url, invoice_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.create_cryptobot_invoice_handler`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_cryptobot_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_cryptobot_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_cryptobot`, `src/shop_bot/webapp/handlers.py::api_create_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1418 | `create_topup_payment_method_keyboard(payment_methods)` | — | `src/shop_bot/bot/handlers.py::get_user_router.topup_amount_input` |
| 1466 | `create_traffic_packages_keyboard(key_id, packages)` | — | `src/shop_bot/bot/handlers.py::get_user_router.traffic_gb_start_handler` |
| 1488 | `create_traffic_gb_payment_method_keyboard(payment_methods)` | — | `src/shop_bot/bot/handlers.py::get_user_router.traffic_gb_pick_handler` |
| 1536 | `create_lte_packages_keyboard(key_id, packages, lte_label)` | Пакеты докупки независимого LTE-пула (premium-ноды 💰). | `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_start_handler`; тесты: 1 сайт(ов) |
| 1560 | `create_lte_gb_payment_method_keyboard(payment_methods)` | Выбор способа оплаты докупки LTE-пула (полный аналог create_traffic_gb_payment_method_keyboard, | `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_pick_handler` |
| 1610 | `create_main_reset_payment_method_keyboard(payment_methods)` | Выбор способа оплаты разовой платной перезагрузки основного пула трафика. | `src/shop_bot/bot/handlers.py::get_user_router.main_reset_start_handler` |
| 1660 | `create_rename_key_keyboard(key_id, has_name)` | Клавиатура для переименования ключа. | `src/shop_bot/bot/handlers.py::get_user_router.rename_key_start` |
| 1670 | `create_search_keys_results_keyboard(keys, page)` | Клавиатура с результатами поиска ключей. | `src/shop_bot/bot/handlers.py::get_user_router.search_keys_input_handler`, `src/shop_bot/bot/handlers.py::get_user_router.search_keys_page_handler` |
| 1712 | `create_admin_search_keys_cancel_keyboard()` | Клавиатура для отмены поиска ключей администратором. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_user_keys_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_all_keys_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_user_keys_input_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_all_keys_input_handler` |
| 1718 | `create_admin_search_keys_results_keyboard(keys, page, user_id)` | Клавиатура с результатами поиска ключей (для админа). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_user_keys_input_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_keys_page_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_all_keys_input_handler` |
| 1763 | `create_gifts_management_keyboard(gifts, page)` | Клавиатура для управления неактивными подарками. | `src/shop_bot/bot/handlers.py::get_user_router.show_inactive_gifts_handler`, `src/shop_bot/bot/handlers.py::get_user_router.gifts_page_handler` |
| 1800 | `create_gift_info_keyboard(gift_id, key_id, is_activated, connection_string, devices_list, gift_link)` | Клавиатура для информации о подарке (как обычный ключ, но без продления). | `src/shop_bot/bot/handlers.py::get_user_router.show_gift_handler` |
| 1850 | `create_key_info_keyboard(key_id, connection_string, devices_list, gift_code, gift_id, show_traffic_topup, show_lte_topup, show_main_reset, …)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process`, `src/shop_bot/bot/handlers.py::get_user_router.remove_key_name`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_rename_key`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/bot/handlers.py::get_user_router.delete_device_handler`; тесты: 1 сайт(ов) |
| 1906 | `create_howto_vless_keyboard()` | — | `src/shop_bot/bot/handlers.py::get_user_router.howto_android_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_windows_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_android_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_ios_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_windows_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_linux_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_instruction_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_ios_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_linux_handler` |
| 1916 | `create_howto_vless_keyboard_key(key_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.howto_android_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_ios_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_windows_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.howto_linux_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_instruction_handler` |
| 1926 | `create_back_to_menu_keyboard()` | — | `src/shop_bot/bot/handlers.py::get_user_router.topup_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_close_ticket_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_inactive_gifts_handler`, `src/shop_bot/bot/handlers.py::get_user_router.gifts_page_handler`, `src/shop_bot/bot/handlers.py::get_user_router.traffic_gb_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.main_reset_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_amount_input`, `src/shop_bot/bot/handlers.py::get_user_router.support_external_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_new_ticket_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_my_tickets_handler`, `src/shop_bot/bot/handlers.py::get_user_router.support_view_ticket_handler` и ещё 6 |
| 1931 | `create_profile_keyboard(show_notification_toggle, notifications_enabled, gifts_count, auto_renew_any_enabled, show_auto_renew_toggle)` | — | `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 1955 | `create_welcome_keyboard(channel_url, is_subscription_forced)` | — | `src/shop_bot/bot/handlers.py::get_user_router.start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_answer_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_button_answer_handler` |
| 1970 | `get_main_menu_button()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_unban_user`, `src/shop_bot/webhook_server/app.py::create_webhook_app.unban_user_route` |
| 1973 | `get_buy_button()` | — | из прод-кода **не вызывается** |
| 1977 | `create_admin_users_pick_keyboard(users, page, page_size, action)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_key_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_user_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_back_to_users`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_balance_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_balance_pick_user_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_deduct_balance_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_deduct_balance_pick_user_page` |
| 2002 | `create_admin_hosts_pick_keyboard(hosts, action)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_back_to_hosts`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_key_for_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_back_to_hosts`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_host_keys_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hostkeys_back_to_hosts`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_back_to_host_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hostkeys_page` |
| 2032 | `create_admin_ssh_targets_keyboard(ssh_targets)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_ssh_targets` |
| 2056 | `create_admin_keys_for_host_keyboard(host_name, keys, page, page_size)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_host_keys_pick_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hostkeys_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_back` |
| 2113 | `create_admin_months_pick_keyboard(action)` | — | из прод-кода **не вызывается** |
| 2122 | `create_dynamic_keyboard(menu_type, user_keys, trial_available, is_admin, show_create_bot, show_partner_cabinet, gifts_count)` | Create a keyboard based on database configuration | из прод-кода **не вызывается** |
| 2442 | `create_dynamic_main_menu_keyboard(user_keys, trial_available, is_admin, show_create_bot, show_partner_cabinet, gifts_count)` | Create main menu keyboard using dynamic configuration | `src/shop_bot/bot/handlers.py::show_main_menu` |
| 2462 | `create_dynamic_admin_menu_keyboard()` | Create admin menu keyboard using dynamic configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_menu` |
| 2465 | `create_dynamic_admin_system_menu_keyboard()` | Create admin system submenu keyboard using dynamic configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_system_menu` |
| 2470 | `create_dynamic_admin_settings_menu_keyboard()` | Create admin settings submenu keyboard using dynamic configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_settings_menu` |
| 2475 | `create_dynamic_profile_keyboard()` | Create profile keyboard using dynamic configuration | из прод-кода **не вызывается** |
| 2479 | `create_dynamic_support_menu_keyboard()` | Create support menu keyboard using dynamic configuration | из прод-кода **не вызывается** |
| 2497 | `create_broadcast_button_type_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.add_button_choose_type` |
| 2505 | `create_broadcast_actions_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.add_functional_button_start` |
| 2518 | `create_math_captcha_keyboard()` | Клавиатура для математической капчи с текстовым полем. | `src/shop_bot/bot/handlers.py::show_captcha` |
| 2525 | `create_button_captcha_keyboard(emoji_options)` | Клавиатура для капчи с выбором кнопки (смайлик или текст). | `src/shop_bot/bot/handlers.py::show_captcha` |

**Вложенные функции** (6), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 232 | `create_admin_payments_menu_keyboard._mark` | `create_admin_payments_menu_keyboard` |
| 1269 | `create_payment_method_keyboard._label` | `create_payment_method_keyboard` |
| 1421 | `create_topup_payment_method_keyboard._label` | `create_topup_payment_method_keyboard` |
| 1491 | `create_traffic_gb_payment_method_keyboard._label` | `create_traffic_gb_payment_method_keyboard` |
| 1565 | `create_lte_gb_payment_method_keyboard._label` | `create_lte_gb_payment_method_keyboard` |
| 1614 | `create_main_reset_payment_method_keyboard._label` | `create_main_reset_payment_method_keyboard` |

<a id="src-shop_bot-bot-middlewarespy"></a>

### `src/shop_bot/bot/middlewares.py`

BanMiddleware: блок забаненных, сброс is_unreachable при любом апдейте.

**Импорт-путь:** `shop_bot.bot.middlewares`  
**Кто импортирует (прод):** `src/shop_bot/bot_controller.py`, `src/shop_bot/factory_bot/service.py`  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 7 | `BanMiddleware` | `BaseMiddleware` | — |

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 8 | `async BanMiddleware.__call__(self, handler, event, data)` | внутренний хелпер | из прод-кода **не вызывается** |

<a id="src-shop_bot-bot-callback_safetypy"></a>

### `src/shop_bot/bot/callback_safety.py`

Безопасный ACK callback_query и ловушка ошибок — в основном для админ-хендлеров.

**Импорт-путь:** `shop_bot.bot.callback_safety`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`  

**Функции верхнего уровня и методы классов:** 3

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 14 | `fast_callback_answer(arg)` | Fast ACK for callback queries. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_payments_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_payments_open`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_payments_toggle`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_payments_set`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_payments_yoomoney_check`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_requests`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_start`, `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_methods`, `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_add`, `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_add_type`, `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_bank_choice` и ещё 13 |
| 51 | `catch_callback_errors(func)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`, `src/shop_bot/bot/handlers.py::get_user_router` |
| 67 | `async handle_unknown_callback(callback)` | — | `src/shop_bot/bot/handlers.py::<module>` |

**Вложенные функции** (3), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 26 | `fast_callback_answer._ack` | `fast_callback_answer` |
| 40 | `fast_callback_answer.wrapper` | `fast_callback_answer` |
| 53 | `catch_callback_errors.wrapper` | `catch_callback_errors` |

<a id="src-shop_bot-bot-photo_helperpy"></a>

### `src/shop_bot/bot/photo_helper.py`

Отправка/правка сообщений с картинкой img/obla.png. В текущем runtime хендлеры не импортируют.

**Импорт-путь:** `shop_bot.bot.photo_helper`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 5

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 8 | `_default_image_path()` | Returns absolute path to default image (src/shop_bot/img/obla.png). | из прод-кода **не вызывается** |
| 16 | `_get_default_photo()` | внутренний хелпер | из прод-кода **не вызывается** |
| 21 | `async answer_with_image(message, *args, **kwargs)` | Drop-in replacement for message.answer(...), but sends a photo with caption. | из прод-кода **не вызывается** |
| 40 | `async send_with_image(bot, *args, **kwargs)` | Drop-in replacement for bot.send_message(...), but sends a photo with caption. | из прод-кода **не вызывается** |
| 73 | `async edit_with_image(message, *args, **kwargs)` | Replacement for message.edit_text(...). | из прод-кода **не вызывается** |

<a id="src-shop_bot-bot-image_botpy"></a>

### `src/shop_bot/bot/image_bot.py`

Подкласс aiogram.Bot, подменяющий send_message на фото. Не подключён.

**Импорт-путь:** `shop_bot.bot.image_bot`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 35 | `ImageBot` | `Bot` | Bot that attaches an image from shop_bot/img to every outgoing text message. |

**Функции верхнего уровня и методы классов:** 3

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 11 | `_pick_image_path()` | Pick an image file from shop_bot/img. | из прод-кода **не вызывается** |
| 29 | `_filter_kwargs(func, kwargs)` | Keep only kwargs that func(...) accepts (defensive for aiogram version differences). | из прод-кода **не вызывается** |
| 45 | `async ImageBot.send_message(self, chat_id, text, *args, **kwargs)` | — | из прод-кода **не вызывается** |

## Данные и фон

<a id="src-shop_bot-data_manager-__init__py"></a>

### `src/shop_bot/data_manager/__init__.py`

Маркер пакета data_manager. Пустой.

**Импорт-путь:** `shop_bot.data_manager`  
**Кто импортирует (прод):** `modules/ramadan_tracker/bot_handlers.py`, `modules/ramadan_tracker/panel_routes.py`, `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/core/module_loader.py`, `src/shop_bot/core/module_middleware.py`, `src/shop_bot/data_manager/backup_manager.py`, `src/shop_bot/data_manager/captcha_utils.py`, `src/shop_bot/data_manager/database.py`, `src/shop_bot/data_manager/remnawave_repository.py`, `src/shop_bot/data_manager/resource_monitor.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/data_manager/speedtest_runner.py`, `src/shop_bot/factory_bot/handlers.py`, `src/shop_bot/factory_bot/middleware.py`, `src/shop_bot/factory_bot/service.py`, `src/shop_bot/modules/remnawave_api.py`, `src/shop_bot/modules/telegram_reachability.py`, `src/shop_bot/support_bot/idle_close.py`, `src/shop_bot/support_bot_controller.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 47 файл(ов)

Функций нет.

<a id="src-shop_bot-data_manager-databasepy"></a>

### `src/shop_bot/data_manager/database.py`

SQLite: схема, миграции, CRUD всех сущностей. Большинство функций также доступны через remnawave_repository (форвардеры).

**Импорт-путь:** `shop_bot.data_manager.database`  
**Кто импортирует (прод):** `migrate_invalidate_auth_tokens.py`, `modules/ramadan_tracker/bot_handlers.py`, `modules/ramadan_tracker/panel_routes.py`, `simple_collect.py`, `simple_monitor_test.py`, `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot/keyboards.py`, `src/shop_bot/core/module_loader.py`, `src/shop_bot/core/module_middleware.py`, `src/shop_bot/data_manager/captcha_utils.py`, `src/shop_bot/data_manager/remnawave_repository.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/modules/cryptobot_api.py`, `src/shop_bot/modules/email_sender.py`, `src/shop_bot/modules/heleket_api.py`, `src/shop_bot/modules/platega_fulfillment.py`, `src/shop_bot/modules/telegram_reachability.py`, `src/shop_bot/support_bot/idle_close.py`, `src/shop_bot/support_bot/ticket_media.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 42 файл(ов)

**Функции верхнего уровня и методы классов:** 413

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 35 | `_now_str()` | внутренний хелпер | из прод-кода **не вызывается** |
| 39 | `add_calendar_months(dt, months)` | Добавляет календарные месяцы к дате, корректно обрабатывая переполнение дней | из прод-кода **не вызывается** |
| 50 | `compute_next_traffic_reset_str(from_dt)` | Возвращает строку даты/времени следующего ежемесячного сброса трафика (сейчас + 1 месяц). | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 56 | `add_months(dt, months)` | Прибавляет к дате календарные месяцы (без внешних зависимостей вроде dateutil). | из прод-кода **не вызывается** |
| 71 | `compute_next_traffic_reset(from_dt)` | Возвращает строку даты следующего ежемесячного сброса трафика (текущий момент + 1 месяц). | из прод-кода **не вызывается** |
| 77 | `_as_limit_bytes(value)` | внутренний хелпер | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 85 | `plan_main_limit_bytes(plan)` | — | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 89 | `plan_lte_limit_bytes(plan)` | — | из прод-кода **не вызывается** |
| 93 | `should_account_lte_traffic(plan, host_name, lte_squad)` | LTE-учёт (снапшоты, baseline, энфорс) только при лимите и живом скваде. | `src/shop_bot/bot/handlers.py::get_user_router._resolve_plan_for_lte_topup`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webapp/handlers.py::_lte_card_state`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json` |
| 117 | `plan_has_monthly_traffic_reset(plan)` | Ежемесячный сброс нужен, если ограничен основной пул и/или LTE. | из прод-кода **не вызывается** |
| 122 | `remnawave_traffic_limit_strategy_for_plan(plan)` | Стратегия Remnawave относится только к ОСНОВНОМУ пулу. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/data_manager/scheduler.py::check_auto_renewals`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_change_plan_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 131 | `parse_plan_id_from_key(key)` | — | из прод-кода **не вызывается** |
| 143 | `key_is_unbilled_trial_or_gift(key)` | — | из прод-кода **не вызывается** |
| 161 | `resolve_plan_for_key(key, allow_host_fallback)` | Тариф ключа: plan_id из description, иначе первый активный тариф хоста. | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 185 | `format_next_traffic_reset_display(raw)` | Дата ближайшего сброса для карточки ключа (`ДД.ММ.ГГГГ`) либо None. | `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/webapp/handlers.py::_lte_card_state`, `src/shop_bot/webapp/handlers.py::_process_key_data`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json` |
| 196 | `compute_aligned_next_traffic_reset(key, now)` | Следующий сброс, согласованный с текущим rolling-окном ключа. | из прод-кода **не вызывается** |
| 227 | `_to_datetime_str(ts_ms)` | внутренний хелпер | из прод-кода **не вызывается** |
| 237 | `_normalize_email(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 244 | `_normalize_key_row(row)` | внутренний хелпер | из прод-кода **не вызывается** |
| 273 | `_get_table_columns(cursor, table)` | внутренний хелпер | из прод-кода **не вызывается** |
| 278 | `_ensure_table_column(cursor, table, column, definition)` | внутренний хелпер | из прод-кода **не вызывается** |
| 284 | `_ensure_unique_index(cursor, name, table, column)` | внутренний хелпер | из прод-кода **не вызывается** |
| 288 | `_ensure_index(cursor, name, table, column)` | внутренний хелпер | из прод-кода **не вызывается** |
| 292 | `normalize_host_name(name)` | Normalize host name by trimming and removing invisible/unicode spaces. | `src/shop_bot/data_manager/remnawave_repository.py::<module>` |
| 300 | `initialize_db()` | — | `src/shop_bot/__main__.py::main`; тесты: 1 сайт(ов) |
| 894 | `_ensure_users_columns(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 919 | `_ensure_email_verification_columns(cursor)` | Добавляет поля для активации email (подтверждение владения адресом при веб-регистрации). | из прод-кода **не вызывается** |
| 946 | `_ensure_hosts_columns(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 976 | `_ensure_plans_columns(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 993 | `_ensure_traffic_packages_table(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1017 | `_ensure_key_node_usage_snapshots_table(cursor)` | Расход ключа по КОНКРЕТНЫМ нодам за расчётный период. | из прод-кода **не вызывается** |
| 1046 | `resolve_key_period_start(key)` | Начало текущего расчётного периода ключа в формате '%Y-%m-%d %H:%M:%S'. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json` |
| 1079 | `upsert_key_node_usage_snapshot(key_id, node_uuid, host_name, used_bytes, period_start, node_name)` | Записать/обновить расход ключа по одной ноде за период (идемпотентно по | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1124 | `get_node_usage_for_key(key_id, period_start)` | Разбивка расхода ключа по нодам за период (по убыванию расхода). | `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json` |
| 1153 | `delete_node_usage_for_key(key_id)` | Удалить все снапшоты ключа (используется при удалении ключа). | из прод-кода **не вызывается** |
| 1166 | `_ensure_subscription_lte_table(cursor)` | Отдельный (независимый от основного) пул трафика LTE для «премиум»-нод. | из прод-кода **не вызывается** |
| 1197 | `_ensure_key_lte_state_table(cursor)` | Состояние LTE-пула НА КЛЮЧ (пришло на смену пользовательскому `subscription_lte`). | из прод-кода **не вызывается** |
| 1224 | `_migrate_subscription_lte_to_keys(cursor)` | Перенести пользовательское состояние LTE на ключи (однократно для каждой строки). | из прод-кода **не вызывается** |
| 1329 | `_ensure_host_squads_table(cursor)` | Классифицированные сквады хоста: 'base' (∞), 'lte' (💰) или 'other'. | из прод-кода **не вызывается** |
| 1412 | `add_host_squad(host_name, squad_uuid, squad_class, label)` | Добавить сквад к хосту с классификацией ('base' \| 'lte' \| 'other'). | `src/shop_bot/webhook_server/app.py::create_webhook_app.add_host_squad_route`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad2_label`; тесты: 4 сайт(ов) |
| 1452 | `get_host_squads(host_name, only_active)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad_toggle`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_host_squads` |
| 1470 | `get_squad_by_class(host_name, squad_class)` | Быстрый доступ к активному сквада заданного класса ('base'/'lte'/'other') хоста. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_toggle_class`, `src/shop_bot/bot/admin_handlers.py::get_admin_router._format_host_card`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webapp/handlers.py::_lte_card_state`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route`, `src/shop_bot/modules/remnawave_api.py::get_squad_nodes_for_class`, `src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host` |
| 1500 | `squad_display_label(squad, fallback)` | Публичная метка сквада: поле `label`, если заполнено, иначе fallback. | `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/webapp/handlers.py::_lte_card_state`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`; тесты: 1 сайт(ов) |
| 1520 | `get_lte_squad_display_label(host_name, fallback)` | Метка активного LTE-сквада хоста — то, что видит пользователь вместо «LTE». | `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_pick_handler`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`; тесты: 1 сайт(ов) |
| 1531 | `set_host_squad_active(squad_id, is_active)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.toggle_host_squad_route`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad_toggle` |
| 1546 | `delete_host_squad(squad_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_host_squad_route`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad_delete` |
| 1558 | `_ensure_remnawave_squads_catalog(cursor)` | Глобальный каталог сквадов Remnawave (выбираются галочками на хостах). | из прод-кода **не вызывается** |
| 1628 | `get_remnawave_squads(only_active)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 1644 | `add_remnawave_squad(squad_uuid, squad_class, label)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.add_remnawave_squad_route`; тесты: 1 сайт(ов) |
| 1671 | `delete_remnawave_squad(squad_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_remnawave_squad_route` |
| 1695 | `seed_global_remnawave_from_hosts()` | Если глобальные Remnawave-настройки пусты — взять из первого хоста. | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 1735 | `apply_global_remnawave_to_hosts()` | Синхронизировать глобальные Remnawave URL/token/subscription на все хосты. | `src/shop_bot/webhook_server/app.py::create_webhook_app.update_remnawave_settings_route` |
| 1767 | `set_host_squads_from_catalog(host_name, catalog_ids)` | Выставить привязку хоста к сквадам каталога (галочки). Синхронизирует host_squads и squad_uuid. | `src/shop_bot/webhook_server/app.py::create_webhook_app.update_host_squad_selection_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.add_host_route` |
| 1854 | `get_host_selected_squad_catalog_ids(host_name)` | ID записей каталога, привязанных к хосту через host_squads.uuid. | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 1876 | `_ensure_support_tickets_columns(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1885 | `_ensure_key_usage_monitor_columns(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1894 | `_finalize_vpn_key_indexes(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1902 | `_rebuild_vpn_keys_table(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 2005 | `_ensure_vpn_keys_schema(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 2037 | `_migrate_gift_tags(cursor)` | Обновить старые теги 'gift' и 'GIFT' на новый стандарт 'user_gift'. | из прод-кода **не вызывается** |
| 2053 | `run_migration()` | — | `src/shop_bot/data_manager/backup_manager.py::restore_from_file` |
| 2132 | `insert_resource_metric(scope, object_name, cpu_percent, mem_percent, disk_percent, load1, net_bytes_sent, net_bytes_recv, …)` | — | `simple_collect.py::collect_metrics_simple`, `simple_monitor_test.py::insert_test_metric`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_local`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_target`, `src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics` |
| 2168 | `get_latest_resource_metric(scope, object_name)` | — | `simple_collect.py::collect_metrics_simple` |
| 2189 | `get_metrics_series(scope, object_name, since_hours, limit)` | — | `simple_collect.py::collect_metrics_simple`, `src/shop_bot/webhook_server/app.py::create_webhook_app.monitor_series_json` |
| 2230 | `create_host(name, url, user, passwd, inbound, subscription_url)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add_squad_uuid`, `src/shop_bot/webhook_server/app.py::create_webhook_app.add_host_route`; тесты: 4 сайт(ов) |
| 2259 | `update_host_subscription_url(host_name, subscription_url)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_sub_input`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_host_subscription_route` |
| 2280 | `claim_referral_start_bonus(user_id)` | Атомарно пометить, что приглашённый получил стартовый реферальный бонус. | `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`, `src/shop_bot/webapp/handlers.py::_apply_pending_referral` |
| 2309 | `set_referral_start_bonus_received(user_id)` | Пометить, что пользователь получил стартовый бонус за реферальную регистрацию. | из прод-кода **не вызывается** |
| 2318 | `set_referral_trial_day_bonus_received(user_id)` | Пометить, что за данного пользователя уже начислялся +1 день рефереру за активацию триала. | `src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial` |
| 2335 | `update_host_url(host_name, new_url)` | Обновить URL панели XUI для указанного хоста. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_url_input`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_host_url_route` |
| 2357 | `update_host_remnawave_settings(host_name, remnawave_base_url, remnawave_api_token, squad_uuid)` | Обновить Remnawave-настройки на уровне конкретного хоста. | `src/shop_bot/webhook_server/app.py::create_webhook_app.update_host_remnawave_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.add_host_route`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add_squad_uuid`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_rmw_url_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_rmw_token_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_squad_input` |
| 2404 | `get_host_class(host_name)` | Класс ноды: 'premium' (💰) или 'unlim' (∞, по умолчанию). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_host_detail`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_toggle_class`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route` |
| 2421 | `set_host_class(host_name, node_class, badge)` | Устанавливает класс ноды ('premium'/'unlim') и её значок (по умолчанию 💰/∞). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_toggle_class` |
| 2441 | `set_host_squad_overlap(host_name, overlap_nodes)` | Сохранить результат проверки пересечения нод LTE- и base-сквадов хоста. | `src/shop_bot/modules/remnawave_api.py::refresh_host_squad_overlap` |
| 2470 | `get_host_squad_overlap(host_name)` | Ноды, доступные и через LTE-, и через base-сквад хоста (по последней проверке). | `src/shop_bot/bot/admin_handlers.py::get_admin_router._format_host_card`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 2491 | `list_hosts_by_class(node_class)` | — | из прод-кода **не вызывается** |
| 2507 | `update_host_name(old_name, new_name)` | Переименовать хост во всех связанных таблицах (xui_hosts, plans, vpn_keys, host_squads). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_rename_input`, `src/shop_bot/webhook_server/app.py::create_webhook_app.rename_host_route` |
| 2551 | `delete_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_delete_confirm`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_host_route` |
| 2569 | `_decrypt_row_secrets(row, *fields)` | Расшифровать at-rest поля (enc1$ / legacy plaintext) в копии строки. | `src/shop_bot/data_manager/remnawave_repository.py::_decrypt_host_secrets` |
| 2580 | `get_host(host_name)` | — | `src/shop_bot/webapp/handlers.py::api_device_tiers`, `src/shop_bot/webapp/handlers.py::api_create_payment`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_host_detail`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_add_squad_uuid`, `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`, `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_net_probe`, `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest`, `src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_host` |
| 2593 | `update_host_ssh_settings(host_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path)` | Обновить SSH-параметры для speedtest/maintenance по хосту. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_set_ssh_input`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_host_ssh_route` |
| 2634 | `delete_key_by_id(key_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.sync_user_keys_with_remnawave`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_key_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.sweep_expired_keys_route` |
| 2652 | `update_key_comment(key_id, comment)` | — | `src/shop_bot/webapp/handlers.py::api_key_comment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_key_comment_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 2664 | `update_key_name(key_id, new_name)` | Обновить пользовательское название ключа. | `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process`, `src/shop_bot/bot/handlers.py::get_user_router.remove_key_name`, `src/shop_bot/webapp/handlers.py::api_key_rename` |
| 2700 | `get_all_hosts()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_set_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_key_for_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_back_to_hosts`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_host_keys_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hostkeys_back_to_hosts`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_hosts_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_back_to_hosts`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_all`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hostkeys_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router._resolve_host_from_digest` и ещё 22 |
| 2718 | `get_speedtests(host_name, limit)` | Получить последние результаты спидтестов по хосту (ssh/net), новые сверху. | `src/shop_bot/webhook_server/app.py::create_webhook_app.host_speedtests_json` |
| 2746 | `get_latest_speedtest(host_name)` | Получить последний по времени спидтест для хоста. | `src/shop_bot/bot/handlers.py::get_user_router.user_speedtest_last_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 2770 | `insert_host_speedtest(host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps, server_name, server_id, …)` | Сохранить результат спидтеста в таблицу host_speedtests. | `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_net_probe`, `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest`, `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest_for_target` |
| 2817 | `_ensure_ssh_targets_table(cursor)` | Миграция: создать таблицу speedtest_ssh_targets при необходимости и добавить недостающие столбцы. | из прод-кода **не вызывается** |
| 2849 | `_ensure_ssh_known_hosts_table(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 2863 | `get_ssh_known_host_key(host, port)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_apply_ssh_host_key_policy` |
| 2881 | `save_ssh_known_host_key(host, port, key_type, key_base64)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_apply_ssh_host_key_policy._save`; тесты: 1 сайт(ов) |
| 2905 | `_ensure_gift_tokens_table(cursor)` | Миграция для таблиц подарочных токенов. | из прод-кода **не вызывается** |
| 2941 | `_ensure_user_gifts_table(cursor)` | Миграция для таблицы неактивированных пользовательских подарков. | из прод-кода **не вызывается** |
| 2965 | `_ensure_auth_pending_actions_table(cursor)` | Миграция для таблицы pending action — единого механизма "открыл ссылку | из прод-кода **не вызывается** |
| 2997 | `create_pending_action(action_type, gift_code, referrer_id, ttl_hours)` | Создать pending action и вернуть одноразовый случайный токен. | `src/shop_bot/webapp/handlers.py::web_referral_page`, `src/shop_bot/webapp/handlers.py::web_gift_page`; тесты: 2 сайт(ов) |
| 3031 | `get_pending_action(token)` | Вернуть запись pending action по токену как есть (включая уже | `src/shop_bot/webapp/handlers.py::api_pending_action_info`, `src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 3049 | `claim_pending_action(token, user_id)` | Атомарно "забрать" pending action для указанного пользователя. | `src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 3077 | `set_pending_action_result(token, result_status)` | Сохранить итоговый статус применения действия — чтобы повторный вызов | `src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 3096 | `cleanup_expired_pending_actions(max_age_hours)` | Удалить давно истёкшие pending actions (профилактическая очистка, | из прод-кода **не вызывается** |
| 3114 | `_ensure_promo_tables(cursor)` | Создание таблиц промокодов и истории их использования. | из прод-кода **не вызывается** |
| 3178 | `_ensure_analytics_tables(cursor)` | Таблицы для раздела админки «Продажи и аналитика». | из прод-кода **не вызывается** |
| 3287 | `get_all_ssh_targets()` | Вернуть все SSH-цели для спидтестов (включая неактивные), сортировка по sort_order, затем по имени. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_ssh_targets`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_all_targets`, `src/shop_bot/bot/admin_handlers.py::get_admin_router._resolve_target_from_hash`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_target`, `src/shop_bot/bot/handlers.py::get_user_router.user_speedtest_last_handler`, `src/shop_bot/data_manager/scheduler.py::_run_speedtests_for_all_ssh_targets`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.monitor_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.run_all_ssh_target_speedtests_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 3301 | `get_ssh_target(target_name)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target`, `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest_for_target`, `src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_target` |
| 3315 | `create_ssh_target(target_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path, description, sort_order, …)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.create_ssh_target_route` |
| 3356 | `update_ssh_target_fields(target_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path, description, sort_order, …)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.update_ssh_target_route` |
| 3423 | `delete_ssh_target(target_name)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_ssh_target_route` |
| 3436 | `get_admin_stats()` | Return aggregated statistics for the admin dashboard. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_menu`, `src/shop_bot/webhook_server/app.py::create_webhook_app.statistics_page`; тесты: 1 сайт(ов) |
| 3528 | `get_sales_overview()` | Главный дашборд продаж (Этап 4.1 плана): выручка/транзакции/чек/плательщики | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_overview_page` |
| 3651 | `get_revenue_series(days)` | Ряд выручки/транзакций по дням для графика раздела «Продажи и аналитика». | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_overview_charts_json` |
| 3677 | `get_plans_analytics(limit)` | Аналитика по тарифам (Этап 4.4): выручка, продажи, средний чек, доля повторных покупок. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_plans_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_forecast_page` |
| 3729 | `get_payment_methods_analytics()` | Аналитика по методам оплаты (Этап 4.5): число транзакций, выручка, успешность, динамика. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_payment_methods_page` |
| 3762 | `get_users_without_real_payment_with_keys()` | Пользователи с хотя бы одним VPN-ключом, у которых нет ни одной успешной | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_overview_page`; тесты: 4 сайт(ов) |
| 3794 | `get_trial_key_stats()` | Метрики по триальным ключам и их продлениям. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_overview_page`; тесты: 5 сайт(ов) |
| 3878 | `get_referrals_analytics()` | Аналитика реферальной программы (Этап 6.1) поверх существующих полей/функций, | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_referrals_page` |
| 3941 | `get_top_referrers(limit)` | Топ пользователей по рефералам: число приглашённых и число платящих рефералов. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_referrals_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.referral_program_top_page`; тесты: 1 сайт(ов) |
| 3982 | `get_top_buyers(limit)` | Топ пользователей по покупкам (Этап 6.4): сумма, число успешных транзакций, средний чек. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_referrals_page` |
| 4016 | `_promo_plans_label(raw_ids)` | Человекочитаемое ограничение тарифов для карточки купона в админке. | из прод-кода **не вызывается** |
| 4030 | `_promo_segment_label(segment_type, segment_value)` | Человекочитаемое ограничение сегмента для карточки купона в админке. | из прод-кода **не вызывается** |
| 4046 | `get_coupons_analytics()` | Аналитика купонов/промокодов (Этап 6.3) поверх существующих таблиц | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_coupons_page` |
| 4125 | `get_server_cost_entries(only_active)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_economics_page` |
| 4141 | `create_server_cost_entry(server_label, linked_host_name, provider, location, monthly_cost, currency, status, started_at, …)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_economics_create_route` |
| 4183 | `update_server_cost_entry(entry_id, **fields)` | — | из прод-кода **не вызывается** |
| 4208 | `delete_server_cost_entry(entry_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_economics_delete_route` |
| 4220 | `get_economics_summary()` | Приблизительная экономика (Этап 7.3): расходы по провайдеру/локации, | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_economics_page` |
| 4259 | `get_revenue_forecast()` | Прозрачный прогноз (Этап 4.6/9): скользящее среднее за 7 дней + линейная | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_overview_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_forecast_page` |
| 4311 | `get_utm_links(only_active)` | — | из прод-кода **не вызывается** |
| 4327 | `create_utm_link(slug, source, medium, campaign, content, term, label, comment, …)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_utm_create_route` |
| 4363 | `delete_utm_link(slug)` | Удаляет UTM-метку вместе с накопленной статистикой посещений (utm_visits). | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_utm_delete_route` |
| 4380 | `log_utm_visit(slug, user_id, event_type)` | Best-effort запись события UTM (клик/старт/регистрация/оплата). Никогда не бросает исключение наружу. | `src/shop_bot/bot/handlers.py::get_user_router.start_handler` |
| 4394 | `set_user_utm_slug_if_absent(user_id, slug)` | First-touch атрибуция: записать utm_slug пользователю только если он ещё не задан. | `src/shop_bot/bot/handlers.py::get_user_router.start_handler` |
| 4410 | `get_utm_analytics()` | Эффективность UTM-меток (Этап 5.4): клики, регистрации, оплаты, выручка, ROI (если задан budget). | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_utm_page` |
| 4459 | `create_broadcast_campaign(name, text_html, interval_hours, target_segment)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_create`; тесты: 1 сайт(ов) |
| 4474 | `get_broadcast_campaigns()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_page`, `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns` |
| 4486 | `get_broadcast_campaign(campaign_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_delete`, `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_send_now` |
| 4499 | `update_broadcast_campaign(campaign_id, name, text_html, interval_hours)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_update` |
| 4514 | `toggle_broadcast_campaign(campaign_id)` | Flip is_active. Returns new is_active state. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_toggle` |
| 4535 | `delete_broadcast_campaign(campaign_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_delete` |
| 4554 | `is_email_only_user(telegram_id)` | True, если пользователь зарегистрирован по email и ещё не авторизовался | `src/shop_bot/bot/admin_handlers.py::get_admin_router.confirm_broadcast_handler`, `src/shop_bot/webapp/handlers.py::api_email_reset_request`; тесты: 2 сайт(ов) |
| 4564 | `get_inactive_subscribers()` | User IDs with no active keys (expire_at in the past or no keys at all), | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 4591 | `get_pending_broadcast_recipients(campaign_id, interval_hours)` | Inactive users who haven't been sent this campaign in the last `interval_hours`. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_send_now`, `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`; тесты: 1 сайт(ов) |
| 4614 | `record_broadcast_sends(campaign_id, user_ids)` | Insert send records and bump campaign send_count. Returns count inserted. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_send_now`, `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns` |
| 4636 | `mark_broadcast_run(campaign_id)` | Update last_run_at even when there are no recipients (avoids tight retry loops). | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_send_now`, `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns` |
| 4650 | `get_broadcast_stats(campaign_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_broadcasts_page` |
| 4662 | `get_all_keys()` | — | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::check_expiring_subscriptions`, `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`, `src/shop_bot/webhook_server/app.py::create_webhook_app.sweep_expired_keys_route` |
| 4674 | `get_all_key_ids()` | Все key_id из vpn_keys (без фильтров/пагинации) — для bulk-действий «всем». | `src/shop_bot/webhook_server/app.py::create_webhook_app.bulk_extend_all_keys_route` |
| 4686 | `extend_key(key_id, days)` | Продлить/сократить срок ключа на N дней (с синхронизацией Remnawave). | `src/shop_bot/webhook_server/app.py::create_webhook_app._apply_bulk_expiry_to_ids` |
| 4696 | `set_key_expiry(key_id, new_expire_at)` | Установить точную дату истечения ключа (с синхронизацией Remnawave). | `src/shop_bot/webhook_server/app.py::create_webhook_app._apply_bulk_expiry_to_ids` |
| 4703 | `get_keys_paginated(page, per_page, search, sort_by, sort_dir, user_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_keys_pagination_partial`, `src/shop_bot/webhook_server/app.py::create_webhook_app.user_keys_partial`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_global_search_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_keys_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_keys_table_partial` |
| 4763 | `get_keys_for_user(user_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_view_user_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_ban_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_unban_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_user_keys`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_search_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_back`, `src/shop_bot/webhook_server/app.py::create_webhook_app.bulk_extend_user_keys_route` |
| 4766 | `update_key_email(key_id, new_email)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_edit_email_commit` |
| 4770 | `update_key_host(key_id, new_host_name)` | — | из прод-кода **не вызывается** |
| 4773 | `create_gift_key(user_id, host_name, key_email, months, remnawave_user_uuid)` | Создать подарочный ключ: expiry = now + months. | из прод-кода **не вызывается** |
| 4809 | `get_setting(key)` | — | `src/shop_bot/modules/cryptobot_api.py::create_cryptobot_api_invoice`, `src/shop_bot/modules/email_sender.py::_get_smtp_settings`, `src/shop_bot/modules/email_sender.py::_get_service_name`, `src/shop_bot/modules/heleket_api.py::create_heleket_payment_request`, `src/shop_bot/webapp/handlers.py::api_device_tiers`, `src/shop_bot/webapp/handlers.py::api_create_payment`, `modules/ramadan_tracker/bot_handlers.py::_create_withdrawal_ticket`, `modules/ramadan_tracker/bot_handlers.py::_build_support_url`, `simple_monitor_test.py::test_settings`, `src/shop_bot/__main__.py::main.start_services`, `src/shop_bot/bot_controller.py::BotController.start`, `src/shop_bot/support_bot_controller.py::SupportBotController.start` и ещё 219 |
| 4823 | `get_admin_ids()` | Возвращает множество ID администраторов из настроек. | `src/shop_bot/core/module_middleware.py::ModuleSafeMiddleware._notify_admins`, `src/shop_bot/__main__.py::main.start_services`, `src/shop_bot/support_bot_controller.py::SupportBotController.start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_admin_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_remove_admin_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_view_admins`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_target_hashed`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_target`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_all`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_all_targets`, `src/shop_bot/bot/handlers.py::_notify_admins_key_creation_error` и ещё 11 |
| 4862 | `is_admin(user_id)` | Проверка прав администратора по списку ID из настроек. | `modules/ramadan_tracker/bot_handlers.py::_is_admin`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.open_admin_menu_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.open_admin_system_menu_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.open_admin_settings_menu_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.open_admin_modules_menu_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.refresh_admin_modules_menu_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_module_enable_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_module_disable_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_button_constructor_root`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_select_menu_type`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_open_list`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_open_details` и ещё 262 |
| 4869 | `_connect_pending_db()` | Connection helper for high-contention tables (webhooks/bot). | из прод-кода **не вызывается** |
| 4883 | `_retry_sqlite(work, attempts, base_sleep)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4894 | `_ensure_pending_tables(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4910 | `_ensure_processed_payments_table(cursor)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4934 | `_tx_meta_dict(raw)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4944 | `_provider_transaction_id_from_meta(metadata)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4954 | `_mirror_pending_to_ledger(cursor, payment_id, user_id, amount_rub, metadata, status)` | Дублирует неоплаченный счёт в ``transactions``, чтобы он был виден в истории. | из прод-кода **не вызывается** |
| 5017 | `create_payload_pending(payment_id, user_id, amount_rub, metadata)` | Create/update pending payload metadata. | `src/shop_bot/data_manager/remnawave_repository.py::create_payload_pending`, `src/shop_bot/bot/handlers.py::_create_heleket_payment_request`, `src/shop_bot/bot/handlers.py::_create_cryptobot_invoice`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_platega_handler`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_rollypay_handler`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_platega_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_rollypay_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_platega`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_rollypay` и ещё 17; тесты: 12 сайт(ов) |
| 5067 | `patch_pending_metadata(payment_id, extra)` | Дописывает поля (id провайдера) в pending и в зеркало ``transactions``. | `src/shop_bot/bot/handlers.py::create_cryptobot_api_invoice`, `src/shop_bot/bot/handlers.py::_create_cryptobot_invoice`, `src/shop_bot/bot/handlers.py::_create_heleket_payment_request`, `src/shop_bot/modules/heleket_api.py::create_heleket_payment_request`, `src/shop_bot/modules/platega_fulfillment.py::mark_pending_canceled`; тесты: 1 сайт(ов) |
| 5106 | `_get_pending_metadata(payment_id)` | внутренний хелпер | `src/shop_bot/bot/handlers.py::get_user_router.check_platega_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_rollypay_payment_handler` |
| 5137 | `get_pending_metadata(payment_id)` | Public wrapper to fetch pending metadata by payment_id WITHOUT marking it paid. | `src/shop_bot/bot/handlers.py::get_user_router.check_yookassa_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_crypto_invoice_handler`, `src/shop_bot/bot/handlers.py::get_user_router.payment_stars_back_handler`, `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.yoomoney_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.cryptobot_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.heleket_webhook_handler`; тесты: 2 сайт(ов) |
| 5142 | `get_pending_record(payment_id)` | Строка pending_transactions с любым статусом (pending/cancelled/paid). | `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler` |
| 5182 | `revive_cancelled_invoice(payment_id)` | Вернуть отменённый счёт в pending, если позже пришла реальная оплата. | из прод-кода **не вызывается** |
| 5221 | `prepare_pending_for_fulfillment(payment_id)` | Metadata для выдачи: отменённый счёт поднимаем, paid не трогаем. | `src/shop_bot/webhook_server/app.py::create_webhook_app.yookassa_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler` |
| 5234 | `get_pending_status(payment_id)` | Return status of pending transaction: 'pending', 'paid', or None if not found. | `src/shop_bot/bot/handlers.py::get_user_router.check_pending_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.stars_success_handler`, `src/shop_bot/bot/handlers.py::get_user_router.payment_stars_back_handler`, `src/shop_bot/bot/handlers.py::get_user_router.pre_checkout_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_platega_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_rollypay_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_yookassa_payment_handler`, `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webapp/handlers.py::api_check_payment`; тесты: 9 сайт(ов) |
| 5257 | `_complete_pending(payment_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5279 | `find_and_complete_pending_transaction(payment_id)` | Atomically mark pending transaction as paid and return its metadata. | `src/shop_bot/modules/platega_fulfillment.py::complete_pending_platega_payment`, `src/shop_bot/bot/handlers.py::get_user_router.stars_success_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_rollypay_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_yookassa_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_platega_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_crypto_invoice_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_pending_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router._gift_username_catcher`, `src/shop_bot/webhook_server/app.py::create_webhook_app.yookassa_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.yoomoney_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.cryptobot_webhook_handler` и ещё 1; тесты: 3 сайт(ов) |
| 5334 | `get_latest_pending_for_user(user_id)` | Return metadata of the most recent PENDING transaction for the user (without completing it). | `src/shop_bot/bot/handlers.py::get_user_router._gift_username_catcher`, `src/shop_bot/bot/handlers.py::get_user_router.stars_success_handler` |
| 5366 | `claim_processed_payment(payment_id)` | Idempotency guard: returns True only once per payment_id. | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 5389 | `unclaim_processed_payment(payment_id)` | Remove idempotency record so a failed payment can be retried. | `src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`, `src/shop_bot/bot/handlers.py::_abort_key_fulfillment`, `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 5409 | `refund_payment_once(payment_id, user_id, amount, payment_method)` | Вернуть средства за невыданную услугу не более одного раза на payment_id. | `src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`, `src/shop_bot/bot/handlers.py::_abort_key_fulfillment`, `src/shop_bot/webapp/handlers.py::_rollback_internal_payment`; тесты: 2 сайт(ов) |
| 5474 | `cancel_pending_transaction(payment_id, user_id)` | Пометить неоплаченный pending как cancelled, чтобы Stars/вебхук его не закрыли. | `src/shop_bot/data_manager/remnawave_repository.py::cancel_pending_transaction`, `src/shop_bot/bot/handlers.py::get_user_router.payment_stars_back_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_platega_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_rollypay_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_yookassa_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.create_stars_invoice_handler`, `src/shop_bot/modules/platega_fulfillment.py::mark_pending_canceled`, `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.yookassa_webhook_handler`; тесты: 4 сайт(ов) |
| 5542 | `reset_pending_transaction(payment_id)` | Reset a completed pending transaction back to 'pending' to allow webhook retry. | `src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`, `src/shop_bot/bot/handlers.py::_abort_key_fulfillment` |
| 5565 | `get_referrals_for_user(user_id)` | Возвращает список пользователей, которых пригласил данный user_id. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_user_referrals`, `src/shop_bot/webhook_server/app.py::create_webhook_app.user_referrals_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.user_details_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_balance_page` |
| 5589 | `get_referral_top_rich(limit)` | Возвращает топ пользователей по количеству рефералов, | `src/shop_bot/bot/handlers.py::get_user_router.referral_top_handler` |
| 5621 | `get_referral_rank_and_count(user_id)` | Возвращает кортеж (rank, count), где: | `src/shop_bot/bot/handlers.py::get_user_router.referral_top_handler` |
| 5674 | `get_all_settings()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.inject_current_year`, `src/shop_bot/webhook_server/app.py::create_webhook_app.login_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.get_common_template_data`, `src/shop_bot/webhook_server/app.py::create_webhook_app.referral_program_settings_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 5691 | `update_setting(key, value)` | — | `simple_monitor_test.py::test_settings`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_toggle`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_toggle_days_bonus`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_type_chosen`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_percent_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_fixed_amount_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_start_bonus_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_min_withdrawal_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_referral_discount_input`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_toggle`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_select_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_trial_days_input` и ещё 29; тесты: 68 сайт(ов) |
| 5705 | `get_button_configs(menu_type)` | Get *active* button configurations for a specific menu type. | `src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 5728 | `get_button_configs_admin(menu_type, include_inactive)` | Get button configurations for admin/editor UIs. | `src/shop_bot/bot/admin_handlers.py::get_admin_router._btnc_show_list`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_add_action_value`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_add_width`, `src/shop_bot/webhook_server/app.py::create_webhook_app.get_button_configs_api` |
| 5762 | `get_button_config_by_db_id(button_db_id)` | Get a button configuration by its numeric DB id. | `src/shop_bot/bot/admin_handlers.py::get_admin_router._btnc_show_details`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_toggle_active` |
| 5775 | `get_button_config(menu_type, button_id)` | Get a specific button configuration by menu_type and button_id | из прод-кода **не вызывается** |
| 5793 | `create_button_config(menu_type, button_id, text, callback_data, url, row_position, column_position, button_width, …)` | Create a new button configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_add_finish`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_button_config_api` |
| 5838 | `update_button_config(button_id, text, callback_data, url, row_position, column_position, button_width, is_active, …)` | Update an existing button configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_toggle_active`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_edit_field_value`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_button_config_api` |
| 5901 | `delete_button_config(button_id)` | Delete a button configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router.btnc_delete_do`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_button_config_api` |
| 5914 | `update_existing_my_keys_button()` | Update existing my_keys button to include key count template and set proper button widths | из прод-кода **не вызывается** |
| 5949 | `ensure_main_menu_gift_button()` | Ensure that the main menu has the gift button in button configs. | из прод-кода **не вызывается** |
| 5986 | `ensure_main_menu_referral_button()` | Ensure that the main menu has the referral program button in button configs, | из прод-кода **не вызывается** |
| 6039 | `ensure_admin_plans_button()` | Ensure that the Admin menu has a button for managing тарифы (plans). | из прод-кода **не вызывается** |
| 6114 | `ensure_admin_trial_button()` | Ensure that the Admin menu has a button for managing Trial settings. | из прод-кода **не вызывается** |
| 6156 | `ensure_admin_auto_renew_button()` | Ensure that the Admin settings submenu has a button for Автопродление (auto-renew). | из прод-кода **не вызывается** |
| 6202 | `reorder_button_configs(menu_type, button_orders)` | Reorder button configurations for a menu type | `src/shop_bot/webhook_server/app.py::create_webhook_app.reorder_button_configs_api` |
| 6250 | `initialize_default_button_configs()` | Initialize default button configurations for all menu types | из прод-кода **не вызывается** |
| 6387 | `create_plan(host_name, plan_name, months, price, duration_days, traffic_limit_bytes, hwid_device_limit, lte_limit_bytes, …)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_price_received`, `src/shop_bot/webhook_server/app.py::create_webhook_app.add_plan_route`; тесты: 17 сайт(ов) |
| 6411 | `get_plans_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router._format_plans_for_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_to_plans`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_pick_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_back_to_host_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_delete_confirm`, `src/shop_bot/bot/handlers.py::get_user_router._get_tariff_info_for_key`, `src/shop_bot/webapp/handlers.py::_build_plans_grid_html`, `src/shop_bot/webapp/handlers.py::_render_main_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_get_plans_for_host_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json`; тесты: 16 сайт(ов) |
| 6426 | `get_active_plans_for_host(host_name)` | Возвращает только активные тарифы (is_active = 1) для указанного хоста. | `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_purchase_handler`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_gift_handler`, `src/shop_bot/bot/handlers.py::get_user_router.extend_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.back_to_plans_handler`, `src/shop_bot/bot/handlers.py::get_user_router._resolve_plan_id_for_key`, `src/shop_bot/bot/handlers.py::get_user_router._get_tariff_info_for_key`, `src/shop_bot/webapp/handlers.py::_resolve_plan_id_for_key` |
| 6444 | `set_plan_active(plan_id, is_active)` | Включить/выключить тариф (скрыть/показать пользователям). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_toggle_active`, `src/shop_bot/webhook_server/app.py::create_webhook_app.toggle_plan_route` |
| 6459 | `get_plan_by_id(plan_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plans_open_plan`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_packages_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_lte_packages_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_lte_limit_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_main_reset_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_toggle_active`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_toggle_show_name`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_name_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_months_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_days_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_traffic_received` и ещё 34 |
| 6472 | `get_all_plans()` | Все тарифы (для админки промокодов и валидации applicable_plan_ids). | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_coupons_page` |
| 6491 | `_parse_json_metadata(raw)` | внутренний хелпер | из прод-кода **не вызывается** |
| 6499 | `update_plan_metadata(plan_id, metadata)` | Update plan.metadata JSON blob. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_toggle_show_name` |
| 6518 | `create_traffic_package(plan_id, size_gb, price, pool)` | Пакет докупки ГБ для тарифа. `pool`: 'main' (основной трафик) или 'lte' (premium-ноды). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_price_received`, `src/shop_bot/webhook_server/app.py::create_webhook_app.add_traffic_package_route`; тесты: 1 сайт(ов) |
| 6549 | `get_traffic_packages_for_plan(plan_id, only_active, pool)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_packages_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_lte_packages_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_delete`, `src/shop_bot/bot/handlers.py::get_user_router.traffic_gb_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_start_handler`, `src/shop_bot/webapp/handlers.py::api_lte_packages`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_get_traffic_packages_for_plan_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`; тесты: 1 сайт(ов) |
| 6566 | `get_traffic_package_by_id(package_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_open`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_size_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_toggle`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_delete`, `src/shop_bot/bot/handlers.py::get_user_router.traffic_gb_pick_handler`, `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_pick_handler`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.toggle_traffic_package_route` |
| 6579 | `update_traffic_package(package_id, size_gb, price, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_size_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_edit_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_toggle`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_traffic_package_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.toggle_traffic_package_route` |
| 6602 | `delete_traffic_package(package_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_pkg_delete`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_traffic_package_route` |
| 6614 | `set_key_traffic_boost(key_id, boost_bytes)` | — | из прод-кода **не вызывается** |
| 6629 | `get_plan_lte_limit(plan_id)` | — | из прод-кода **не вызывается** |
| 6641 | `get_lte_state(user_id)` | УСТАРЕЛО: пользовательская модель LTE-пула. | из прод-кода **не вызывается** |
| 6705 | `get_key_lte_state(key_id)` | Состояние LTE-пула конкретного ключа (создаёт строку при отсутствии). | `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webapp/handlers.py::_lte_card_state`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json` |
| 6732 | `update_key_lte_state(key_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, lte_used_baseline_bytes, lte_baseline_reset_requested, lte_reset_at, premium_state)` | — | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 6777 | `add_key_lte_boost_bytes(key_id, add_bytes)` | Атомарно увеличить докупленный LTE-буст КЛЮЧА. Возвращает новое значение. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route`; тесты: 1 сайт(ов) |
| 6809 | `commit_key_lte_baseline(key_id, baseline_bytes, expire_boost)` | Зафиксировать точку отсчёта LTE-расхода ключа одной транзакцией. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 6840 | `request_key_lte_baseline_reset(key_id)` | Пометить начало нового расчётного периода LTE у ключа (буст сгорит вместе с baseline). | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 6857 | `resolve_lte_limit_bytes(lte_state, plan_lte_limit_bytes)` | Единая формула эффективного LTE-лимита: лимит тарифа + докупленный буст. | `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webapp/handlers.py::_lte_card_state` |
| 6879 | `add_lte_boost_bytes(user_id, add_bytes)` | Атомарно увеличить докупленный LTE-буст пользователя на `add_bytes`. | из прод-кода **не вызывается** |
| 6917 | `commit_lte_baseline(user_id, baseline_bytes, expire_boost)` | Зафиксировать точку отсчёта (baseline) LTE-расхода одной транзакцией. | из прод-кода **не вызывается** |
| 6956 | `request_lte_baseline_reset(user_id)` | Помечает начало нового расчётного периода LTE-пула. | из прод-кода **не вызывается** |
| 6982 | `update_lte_state(user_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, lte_used_baseline_bytes, lte_baseline_reset_requested, lte_reset_at, premium_state)` | — | из прод-кода **не вызывается** |
| 7025 | `delete_plan(plan_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_delete_confirm`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_plan_route` |
| 7036 | `update_plan(plan_id, plan_name, months, price, duration_days, traffic_limit_bytes, hwid_device_limit, lte_limit_bytes, …)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_name_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_months_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_price_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_days_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_traffic_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_devices_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_lte_limit_received`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_plan_edit_main_reset_price_received`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_plan_route` |
| 7075 | `register_user_if_not_exists(telegram_id, username, referrer_id)` | Зарегистрировать пользователя, если его ещё нет. | `src/shop_bot/bot/handlers.py::get_user_router.start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_answer_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_button_answer_handler`; тесты: 1 сайт(ов) |
| 7100 | `add_to_referral_balance(user_id, amount)` | — | `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_amount`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::_apply_pending_referral` |
| 7111 | `set_referral_balance(user_id, value)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.approve_withdraw_handler` |
| 7120 | `set_referral_balance_all(user_id, value)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.approve_withdraw_handler` |
| 7129 | `add_to_referral_balance_all(user_id, amount)` | — | `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::_apply_pending_referral` |
| 7141 | `get_referral_balance_all(user_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_user_referrals`, `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/bot/handlers.py::get_user_router.referral_program_handler` |
| 7152 | `get_referral_balance(user_id)` | — | `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/bot/handlers.py::get_user_router.show_payment_options`, `src/shop_bot/bot/handlers.py::get_user_router.referral_program_handler`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_start`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_amount`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_start`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_choose_method`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_amount`, `src/shop_bot/webapp/handlers.py::api_get_payment_methods`, `src/shop_bot/webhook_server/app.py::create_webhook_app.adjust_referral_balance_route` |
| 7163 | `get_balance(user_id)` | — | `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/bot/handlers.py::get_user_router.traffic_gb_pick_handler`, `src/shop_bot/bot/handlers.py::get_user_router.lte_gb_pick_handler`, `src/shop_bot/bot/handlers.py::get_user_router.main_reset_start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_payment_options`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_amount`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::api_check_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_balance_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.adjust_balance_route`; тесты: 2 сайт(ов) |
| 7174 | `adjust_user_balance(user_id, delta)` | Скорректировать баланс пользователя на указанную дельту (может быть отрицательной). | `src/shop_bot/webhook_server/app.py::create_webhook_app.adjust_balance_route` |
| 7186 | `adjust_user_referral_balance(user_id, delta)` | Скорректировать реферальный баланс пользователя на указанную дельту (может быть отрицательной). | `src/shop_bot/webhook_server/app.py::create_webhook_app.adjust_referral_balance_route` |
| 7198 | `set_balance(user_id, value)` | — | из прод-кода **не вызывается** |
| 7209 | `add_to_balance(user_id, amount)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.handle_main_amount`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_amount`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 7238 | `deduct_from_balance(user_id, amount)` | Атомарное списание с основного баланса при достаточности средств. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.handle_deduct_amount`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_balance_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_balance_handler`, `src/shop_bot/bot/handlers.py::get_user_router.mainreset_pay_balance_handler`, `src/shop_bot/bot/handlers.py::get_user_router.pay_with_main_balance_handler`, `src/shop_bot/data_manager/scheduler.py::check_auto_renewals`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 7262 | `deduct_from_referral_balance(user_id, amount)` | Атомарное списание с реферального баланса при достаточности средств. | `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_referral_balance_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_referral_balance_handler`, `src/shop_bot/bot/handlers.py::get_user_router.mainreset_pay_referral_balance_handler`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_amount`, `src/shop_bot/bot/handlers.py::get_user_router.pay_with_referral_balance_handler`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 7300 | `_referral_setting_is_true(key, default)` | внутренний хелпер | из прод-кода **не вызывается** |
| 7305 | `is_referral_withdraw_method_type_enabled(method_type)` | — | из прод-кода **не вызывается** |
| 7312 | `validate_referral_payout_requisite(method_type, requisite_value, bank_name)` | Проверить реквизиты метода получения перед сохранением. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 7339 | `format_referral_withdrawal_admin_notice(request_id, user_id, username, amount, method_type, bank_name, requisite_value)` | Текст уведомления админам о новой заявке на вывод. | `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_amount`, `src/shop_bot/webapp/handlers.py::api_referral_request_withdraw`; тесты: 1 сайт(ов) |
| 7366 | `list_referral_payout_methods(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_methods`, `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_value`, `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_delete`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_start`, `src/shop_bot/webapp/handlers.py::api_referral_payout_methods_list`; тесты: 1 сайт(ов) |
| 7381 | `add_referral_payout_method(user_id, method_type, requisite_value, bank_name)` | — | `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_value`, `src/shop_bot/webapp/handlers.py::api_referral_payout_methods_add`; тесты: 14 сайт(ов) |
| 7403 | `delete_referral_payout_method(method_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.referral_payout_method_delete`, `src/shop_bot/webapp/handlers.py::api_referral_payout_methods_delete` |
| 7420 | `get_referral_payout_method(method_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_choose_method`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_amount`, `src/shop_bot/webapp/handlers.py::api_referral_payout_methods_delete`, `src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 7439 | `create_webapp_auth_request(token)` | Создаёт запись ожидания подтверждения входа через deep-link бота (user_id пока NULL). | `src/shop_bot/webapp/handlers.py::api_request_auth_token`; тесты: 1 сайт(ов) |
| 7455 | `confirm_webapp_auth_request(token, user_id)` | Подтверждает вход: бот вызывает эту функцию после получения deep-link auth_{token}. | `src/shop_bot/bot/handlers.py::get_user_router.start_handler` |
| 7474 | `get_webapp_auth_request(token, consume)` | Возвращает user_id, если запрос уже подтверждён ботом, иначе None. | `src/shop_bot/webapp/handlers.py::api_check_auth_token` |
| 7496 | `cleanup_old_webapp_auth_requests(max_age_minutes)` | — | `src/shop_bot/webapp/handlers.py::api_request_auth_token` |
| 7509 | `create_referral_withdrawal_request(user_id, amount, method_id)` | Атомарно списывает сумму с referral_balance пользователя и создаёт заявку на вывод. | `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_amount`, `src/shop_bot/webapp/handlers.py::api_referral_request_withdraw`; тесты: 7 сайт(ов) |
| 7572 | `has_open_referral_withdrawal_request(user_id)` | Есть ли у пользователя незакрытая заявка (new/processing). | `src/shop_bot/webapp/handlers.py::api_user_referral_info`, `src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 7591 | `list_referral_withdrawal_requests(status, user_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.referral_program_requests_page`, `src/shop_bot/bot/handlers.py::get_user_router.referral_withdraw_requests`, `src/shop_bot/webapp/handlers.py::api_referral_list_withdrawals`; тесты: 3 сайт(ов) |
| 7619 | `get_referral_withdrawal_request(request_id)` | — | из прод-кода **не вызывается** |
| 7640 | `update_referral_withdrawal_request_status(request_id, new_status, reject_reason)` | Меняет статус заявки на вывод. | `src/shop_bot/webhook_server/app.py::create_webhook_app.referral_program_request_status_route`; тесты: 4 сайт(ов) |
| 7720 | `get_referral_withdrawable_stats()` | Сводка по заявкам на вывод (для админ-панели): счётчики по статусам и суммы. | `src/shop_bot/webhook_server/app.py::create_webhook_app.get_common_template_data` |
| 7736 | `get_referral_count(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.referral_program_handler`, `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/webapp/handlers.py::api_user_referral_info`, `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 7746 | `get_user(telegram_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_view_user_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_user_referrals`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_ban_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_unban_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_days`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.approve_withdraw_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_search_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_view_admins`, `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`, `src/shop_bot/bot/handlers.py::registration_required.decorated_function`, `src/shop_bot/bot/handlers.py::get_user_router.start_handler` и ещё 27; тесты: 26 сайт(ов) |
| 7759 | `get_user_by_username(username)` | Возвращает пользователя по username (без @), регистр не важен. | `src/shop_bot/bot/handlers.py::get_user_router._gift_username_catcher` |
| 7775 | `set_terms_agreed(telegram_id)` | — | `src/shop_bot/bot/handlers.py::process_successful_onboarding`, `src/shop_bot/bot/handlers.py::get_user_router.start_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_answer_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_button_answer_handler` |
| 7785 | `is_subscription_expiry_notifications_enabled(telegram_id)` | Проверить, включены ли уведомления об истечении срока ключа. | `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/data_manager/scheduler.py::check_expiring_subscriptions` |
| 7802 | `toggle_subscription_expiry_notifications(telegram_id)` | Переключить статус уведомлений об истечении срока. Возвращает новое состояние. | `src/shop_bot/bot/handlers.py::get_user_router.toggle_expiry_notifications_handler` |
| 7828 | `update_user_stats(telegram_id, amount_spent, months_purchased)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 7837 | `get_user_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_stats_partial` |
| 7847 | `get_total_keys_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_stats_partial` |
| 7857 | `get_total_spent_sum()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_stats_partial` |
| 7876 | `create_pending_transaction(payment_id, user_id, amount_rub, metadata)` | Create a pending transaction row in `transactions`. | из прод-кода **не вызывается** |
| 7904 | `find_and_complete_ton_transaction(payment_id, amount_ton)` | Atomically completes a TON transaction. | `src/shop_bot/webhook_server/app.py::create_webhook_app.ton_webhook_handler` |
| 8006 | `_describe_transaction_action(metadata)` | Формирует человекочитаемое описание действия транзакции по её metadata. | из прод-кода **не вызывается** |
| 8025 | `_find_nearest_key_id(cursor, user_id, host_name, created_date, window_minutes)` | Best-effort подбор ключа для старых транзакций, в metadata которых ещё не сохранялся key_id. | из прод-кода **не вызывается** |
| 8062 | `log_transaction(username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, …)` | Записывает транзакцию в таблицу `transactions`. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router.referral_transfer_amount`; тесты: 1 сайт(ов) |
| 8130 | `get_paginated_transactions(page, per_page)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_transactions_partial` |
| 8181 | `get_transactions_paginated(page, per_page, user_id, search, sort_by, sort_dir)` | Универсальная выборка транзакций с фильтром по пользователю, поиском и сортировкой. | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_transactions_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_transactions_csv`, `src/shop_bot/webhook_server/app.py::create_webhook_app.user_transactions_partial`, `src/shop_bot/webhook_server/app.py::create_webhook_app.user_details_json`, `src/shop_bot/webapp/handlers.py::api_user_transactions`; тесты: 5 сайт(ов) |
| 8280 | `set_trial_used(telegram_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation` |
| 8290 | `add_new_key(user_id, host_name, remnawave_user_uuid, key_email, expiry_timestamp_ms, squad_uuid, short_uuid, subscription_url, …)` | — | `src/shop_bot/data_manager/remnawave_repository.py::record_key`; тесты: 2 сайт(ов) |
| 8365 | `_apply_key_updates(key_id, updates)` | внутренний хелпер | из прод-кода **не вызывается** |
| 8387 | `update_key_fields(key_id, user_id, host_name, squad_uuid, remnawave_user_uuid, short_uuid, email, subscription_url, …)` | — | `src/shop_bot/bot/handlers.py::get_user_router.sync_user_keys_with_remnawave`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/remnawave_repository.py::update_key`, `src/shop_bot/data_manager/remnawave_repository.py::record_key`, `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_change_plan_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_traffic_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route`, `src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 8446 | `apply_key_monthly_reset_fields(key_id, plan, restart_cycle, key, expire_main_boost)` | Записать `traffic_limit_strategy` и `next_traffic_reset_at` по тарифу ключа. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::check_auto_renewals`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_change_plan_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 8491 | `backfill_monthly_traffic_reset_for_existing_keys()` | Проставить MONTH_ROLLING и дату сброса уже выданным лимитным/LTE-ключам. | из прод-кода **не вызывается** |
| 8533 | `delete_key_by_email(email)` | — | `src/shop_bot/data_manager/remnawave_repository.py::delete_key_by_email`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8571 | `get_user_keys(user_id)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_user_has_active_subscription`, `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/bot/handlers.py::get_user_router.manage_keys_handler`, `src/shop_bot/bot/handlers.py::get_user_router.sent_gifts_handler`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_search_keys_handler`, `src/shop_bot/bot/handlers.py::get_user_router.toggle_auto_renew_profile`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial`, `src/shop_bot/bot/handlers.py::get_user_router.sync_user_keys_with_remnawave`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process` и ещё 9 |
| 8587 | `get_key_by_id(key_id)` | — | `src/shop_bot/data_manager/remnawave_repository.py::get_key_by_id`, `src/shop_bot/webapp/handlers.py::api_user_gifts`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_change_plan_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_traffic_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_delete_device_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_delete_all_devices_route`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_edit_key`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_prompt`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_extend_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_cancel` и ещё 32; тесты: 9 сайт(ов) |
| 8600 | `get_key_by_email(key_email)` | — | `src/shop_bot/data_manager/remnawave_repository.py::get_key_by_email`, `src/shop_bot/data_manager/remnawave_repository.py::record_key`, `src/shop_bot/data_manager/remnawave_repository.py::generate_key_email_for_user`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_delete_key_process`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 8617 | `get_key_by_remnawave_uuid(remnawave_uuid)` | — | `src/shop_bot/data_manager/remnawave_repository.py::get_key_by_remnawave_uuid`, `src/shop_bot/data_manager/remnawave_repository.py::record_key` |
| 8636 | `update_key_info(key_id, new_remnawave_uuid, new_expiry_ms, **kwargs)` | — | из прод-кода **не вызывается** |
| 8645 | `update_key_host_and_info(key_id, new_host_name, new_remnawave_uuid, new_expiry_ms, **kwargs)` | — | из прод-кода **не вызывается** |
| 8661 | `get_next_key_number(user_id)` | — | `src/shop_bot/data_manager/remnawave_repository.py::generate_key_email_for_user`, `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation` |
| 8665 | `get_keys_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_host_keys_pick_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hostkeys_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_back`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8682 | `set_key_auto_renew(key_id, enabled)` | — | `src/shop_bot/bot/handlers.py::get_user_router.auto_renew_key_toggle`, `src/shop_bot/webapp/handlers.py::api_key_auto_renew` |
| 8694 | `set_all_keys_auto_renew_for_user(user_id, enabled)` | Mass-update auto_renew for all keys of a user. Returns count of updated rows. | `src/shop_bot/bot/handlers.py::get_user_router.toggle_auto_renew_profile` |
| 8707 | `get_keys_for_auto_renew(hours_before)` | Return keys with auto_renew=1 expiring within the next `hours_before` hours. | `src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 8733 | `_key_matches_search(data, needle_lower)` | Регистронезависимая (в т.ч. кириллица) проверка вхождения подстроки | из прод-кода **не вызывается** |
| 8744 | `search_user_keys_by_email(user_id, search_query)` | Поиск ключей пользователя по key_email, email или user_key_name. | `src/shop_bot/data_manager/remnawave_repository.py::search_user_keys_by_email`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_user_keys_input_handler`, `src/shop_bot/bot/handlers.py::get_user_router.search_keys_input_handler`, `src/shop_bot/webapp/handlers.py::api_keys_search` |
| 8766 | `search_all_keys_by_email(search_query)` | Поиск всех ключей (администраторам) по key_email, email или user_key_name. | `src/shop_bot/data_manager/remnawave_repository.py::search_all_keys_by_email`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_all_keys_input_handler` |
| 8787 | `get_all_vpn_users()` | — | из прод-кода **не вызывается** |
| 8800 | `update_key_status_from_server(key_email, client_data)` | — | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8843 | `get_daily_stats_for_charts(days)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.dashboard_charts_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.statistics_page` |
| 8878 | `get_recent_transactions(limit)` | — | из прод-кода **не вызывается** |
| 8914 | `get_all_users()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_key_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_user_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_back_to_users`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_balance_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_balance_pick_user_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_deduct_balance_entry`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_deduct_balance_pick_user_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.confirm_broadcast_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_users_search_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_add_admin_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_remove_admin_process` и ещё 2 |
| 8925 | `get_users_paginated(page, per_page, q, sort)` | Вернуть пользователей постранично и общее количество (с учётом фильтра). | `src/shop_bot/webhook_server/app.py::create_webhook_app.users_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.users_table_partial`, `src/shop_bot/webhook_server/app.py::create_webhook_app.users_pagination_partial`, `src/shop_bot/webhook_server/app.py::create_webhook_app.users_search_json`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_global_search_json` |
| 9043 | `get_keys_counts_for_users(user_ids)` | Вернуть словарь {user_id: keys_count} по списку пользователей. | из прод-кода **не вызывается** |
| 9063 | `ban_user(telegram_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_ban_user`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_ban_user`, `src/shop_bot/webhook_server/app.py::create_webhook_app.ban_user_route` |
| 9072 | `unban_user(telegram_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_unban_user`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_unban_user`, `src/shop_bot/webhook_server/app.py::create_webhook_app.unban_user_route` |
| 9091 | `mark_user_unreachable(telegram_id, reason)` | Отметить пользователя как недоступного в Telegram. | `src/shop_bot/modules/telegram_reachability.py::handle_send_exception` |
| 9117 | `mark_user_reachable(telegram_id)` | Снять отметку недоступности — пользователь снова взаимодействовал с ботом | `src/shop_bot/bot/middlewares.py::BanMiddleware.__call__` |
| 9137 | `get_reachability_stats()` | Статистика по доступности пользователей в Telegram: сколько всего | `src/shop_bot/webhook_server/app.py::create_webhook_app.statistics_page` |
| 9168 | `delete_user_keys(user_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.revoke_keys_route` |
| 9185 | `delete_user_completely(user_id)` | Полностью удалить пользователя и все связанные с ним данные. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_delete_user`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_user_route`; тесты: 8 сайт(ов) |
| 9306 | `create_support_ticket(user_id, subject)` | — | из прод-кода **не вызывается**; тесты: 20 сайт(ов) |
| 9332 | `get_or_create_open_ticket(user_id, subject)` | Возвращает ID открытого тикета пользователя и флаг, создан ли новый. | `src/shop_bot/support_bot/handlers.py::get_support_router.support_message_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.relay_user_message_to_forum`, `src/shop_bot/webapp/handlers.py::api_support_create` |
| 9358 | `add_support_message(ticket_id, sender, content, media)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.support_message_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_reply_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_note_receive`, `src/shop_bot/support_bot/handlers.py::get_support_router.relay_user_message_to_forum`, `src/shop_bot/support_bot/handlers.py::get_support_router.forum_thread_message_handler`, `src/shop_bot/webapp/handlers.py::api_support_send`, `src/shop_bot/webapp/handlers.py::api_support_upload`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_page`; тесты: 14 сайт(ов) |
| 9376 | `update_ticket_thread_info(ticket_id, forum_chat_id, message_thread_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.support_message_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_reply_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.relay_user_message_to_forum`; тесты: 1 сайт(ов) |
| 9390 | `get_ticket(ticket_id)` | — | `src/shop_bot/support_bot/ticket_media.py::expire_ticket_media_if_closed_ttl`, `src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_message_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_view_ticket_handler`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_reply_prompt_handler`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_reply_received`, `src/shop_bot/support_bot/handlers.py::get_support_router.support_close_ticket_handler`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_close_ticket`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_reopen_ticket`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_delete_ticket`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_toggle_star`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_show_user` и ещё 15; тесты: 6 сайт(ов) |
| 9402 | `get_ticket_by_thread(forum_chat_id, message_thread_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.forum_thread_message_handler` |
| 9417 | `get_user_tickets(user_id, status)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.support_my_tickets_handler`, `src/shop_bot/support_bot/handlers.py::get_support_router.my_tickets_text_button`, `src/shop_bot/support_bot/handlers.py::get_support_router._get_latest_open_ticket`, `src/shop_bot/webapp/handlers.py::api_support_status`, `src/shop_bot/webapp/handlers.py::api_support_ticket`, `src/shop_bot/webapp/handlers.py::api_support_create` |
| 9437 | `get_support_message(message_id)` | Одно сообщение тикета. Нужно для отдачи вложений в панели. | `src/shop_bot/webapp/handlers.py::api_support_ticket_file`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_file` |
| 9454 | `resolve_db_file_path(db_file)` | Абсолютный путь к users.db без зависимости от cwd процесса. | из прод-кода **не вызывается** |
| 9473 | `get_ticket_media_root()` | Каталог вложений рядом с users.db, не в webhook_server/. | `src/shop_bot/__main__.py::main`, `src/shop_bot/data_manager/scheduler.py::_ticket_files_present`, `src/shop_bot/support_bot/ticket_media.py::jailed_ticket_folder`, `src/shop_bot/support_bot/ticket_media.py::ticket_media_on_disk`, `src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media`, `src/shop_bot/webapp/handlers.py::api_support_ticket_file`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_file`; тесты: 3 сайт(ов) |
| 9481 | `list_closed_ticket_ids_older_than(cutoff)` | Закрытые тикеты с updated_at не новее cutoff (наивный ISO-текст SQLite). | `src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 9503 | `clear_support_message_media(ticket_id)` | Обнуляет media у сообщений тикета после TTL/удаления файлов. | `src/shop_bot/support_bot/ticket_media.py::expire_ticket_media_if_closed_ttl`, `src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 9519 | `get_ticket_messages(ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.support_view_ticket_handler`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_list_notes`, `src/shop_bot/webapp/handlers.py::api_support_ticket`, `src/shop_bot/webapp/handlers.py::api_support_status`, `src/shop_bot/webapp/handlers.py::api_support_send`, `src/shop_bot/webapp/handlers.py::api_support_upload`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_messages_api`; тесты: 3 сайт(ов) |
| 9533 | `set_ticket_status(ticket_id, status)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.support_close_ticket_handler`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_close_ticket`, `src/shop_bot/support_bot/handlers.py::get_support_router.admin_reopen_ticket`, `src/shop_bot/webapp/handlers.py::api_support_close`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_page`; тесты: 3 сайт(ов) |
| 9547 | `update_ticket_subject(ticket_id, subject)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.admin_toggle_star` |
| 9561 | `_cleanup_ticket_media(ticket_id)` | Файлы вложений живут вне SQLite — удаляем каталог вместе с тикетом. | из прод-кода **не вызывается** |
| 9571 | `delete_ticket(ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router.admin_delete_ticket`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_support_ticket_route`; тесты: 2 сайт(ов) |
| 9593 | `_ticket_forum_target(row)` | внутренний хелпер | из прод-кода **не вызывается** |
| 9617 | `validate_ticket_auto_close_days(raw)` | Для формы настроек: только целое 0–365. | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`; тесты: 1 сайт(ов) |
| 9639 | `parse_ticket_auto_close_days(raw)` | 0 — выключено. Нецелое и мусор → 0. Целое больше 365 режем потолком. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 9653 | `get_ticket_auto_close_days()` | — | `src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets` |
| 9657 | `find_open_tickets_idle_after_admin(days, now, limit)` | Открытые тикеты, где последнее сообщение — ответ админа старше ``days`` суток. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 9712 | `auto_close_idle_admin_tickets(days, now, limit)` | Закрывает найденные простаивающие тикеты. Форум — снаружи. | `src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets`; тесты: 1 сайт(ов) |
| 9779 | `bulk_close_open_tickets()` | Один UPDATE всех открытых тикетов. Форум/уведомления — на стороне вызывающего. | `src/shop_bot/webhook_server/app.py::create_webhook_app.support_bulk_close_route` |
| 9807 | `bulk_delete_all_tickets()` | Один DELETE всех тикетов и сообщений. Вложения на диске не трогает. | `src/shop_bot/webhook_server/app.py::create_webhook_app.support_bulk_delete_route` |
| 9839 | `cleanup_ticket_media_ids(ticket_ids)` | Удаляет каталоги вложений пачкой. Ошибки по одному id не рвут остальные. | `src/shop_bot/webhook_server/app.py::run_bulk_ticket_followup` |
| 9854 | `get_tickets_paginated(page, per_page, status)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.support_table_partial`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_list_page` |
| 9879 | `get_open_tickets_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.support_list_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.inject_current_year`, `src/shop_bot/webhook_server/app.py::create_webhook_app.get_common_template_data`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_open_count_partial` |
| 9889 | `get_closed_tickets_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.support_list_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.inject_current_year`, `src/shop_bot/webhook_server/app.py::create_webhook_app.get_common_template_data` |
| 9899 | `get_all_tickets_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.support_list_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.inject_current_year`, `src/shop_bot/webhook_server/app.py::create_webhook_app.get_common_template_data` |
| 9915 | `get_key_usage_monitor(key_id)` | — | `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`, `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 9928 | `ensure_key_usage_monitor_row(key_id, user_id)` | — | `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 9941 | `update_key_usage_monitor(key_id, first_seen_usage_at, last_reminder_at, last_checked_at, last_devices_count, last_traffic_bytes, overlimit_notified_count, overlimit_notified_at)` | — | `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`, `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations` |
| 10000 | `get_franchise_percent_default()` | Получить процент комиссии франшизы из настроек. | `src/shop_bot/bot/admin_handlers.py::get_admin_router._get_franchise_settings_for_admin`, `src/shop_bot/bot/handlers.py::get_user_router.partner_cabinet` |
| 10009 | `get_franchise_min_withdraw()` | Получить минимум для вывода франшизников из настроек. | `src/shop_bot/bot/admin_handlers.py::get_admin_router._get_franchise_settings_for_admin`, `src/shop_bot/bot/handlers.py::get_user_router.partner_cabinet`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount` |
| 10018 | `resolve_factory_bot_id(telegram_bot_user_id)` | Return internal managed bot id for a Telegram bot user id. | `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisites`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_add`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_bank`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_value`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_set_default`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_delete`, `src/shop_bot/bot/handlers.py::get_user_router.partner_cabinet`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount`, `src/shop_bot/bot/handlers.py::get_user_router.franchise_create_bot`, `src/shop_bot/bot/handlers.py::process_successful_payment` и ещё 3 |
| 10042 | `_managed_bot_token_secret()` | Ключ шифрования токенов клонов: SHOPBOT_SECRET_KEY или стабильная запись в settings. | из прод-кода **не вызывается** |
| 10054 | `_managed_bot_token_pad(secret, nonce, n)` | внутренний хелпер | из прод-кода **не вызывается** |
| 10063 | `_backfill_encrypt_secrets_at_rest()` | Зашифровать уже сохранённые plaintext-секреты (settings / hosts / SSH-цели). | из прод-кода **не вызывается** |
| 10118 | `encrypt_managed_bot_token(token)` | Зашифровать токен клона для хранения. Уже enc1$ не трогаем. | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page` |
| 10134 | `decrypt_managed_bot_token(stored)` | Расшифровать токен. Legacy plaintext (без enc1$) возвращается как есть. | `src/shop_bot/webhook_server/app.py::create_webhook_app.settings_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.login_page` |
| 10157 | `_row_with_decrypted_token(row)` | внутренний хелпер | из прод-кода **не вызывается** |
| 10166 | `get_managed_bot(bot_id)` | — | `src/shop_bot/bot/handlers.py::_notify_user_key_creation_error`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisites`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_add`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_bank`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_value`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_set_default`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_delete`, `src/shop_bot/bot/handlers.py::get_user_router.partner_cabinet`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount`, `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router.cabinet` и ещё 3; тесты: 6 сайт(ов) |
| 10179 | `get_managed_bot_by_telegram_id(telegram_bot_user_id)` | — | из прод-кода **не вызывается** |
| 10192 | `list_active_managed_bots()` | — | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_all` |
| 10204 | `update_managed_bot_active(bot_id, is_active)` | Параметризованно выставить is_active (0/1). Схему таблицы не меняет. | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot.runner` |
| 10222 | `get_managed_bots_by_owner(owner_telegram_id)` | Список клонов владельца без токена (токен не отдаём в UI). | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 10248 | `purge_managed_bot_stats(bot_id)` | Удалить активность и комиссии клона. Идемпотентно, ошибки не пробрасывает. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 10263 | `_purge_managed_bot_stats_on_cursor(cur, bot_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 10268 | `delete_managed_bot(bot_id, owner_telegram_id)` | Удалить строку managed_bots и статистику клона. | `src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router.delete_bot_confirm`, `src/shop_bot/webhook_server/app.py::create_webhook_app.franchise_delete_bot_route`; тесты: 1 сайт(ов) |
| 10319 | `get_factory_cabinet(bot_id)` | Статистика кабинета клона (пользователи/сообщения/прямые клоны/баланс). | `src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router.cabinet` |
| 10355 | `create_managed_bot(token, telegram_bot_user_id, username, owner_telegram_id, referrer_bot_id)` | Register a managed bot. | `src/shop_bot/bot/handlers.py::get_user_router.franchise_receive_token`; тесты: 6 сайт(ов) |
| 10422 | `record_factory_activity(bot_id, user_id)` | Upsert activity row (unique users + messages count). | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__`; тесты: 2 сайт(ов) |
| 10452 | `_is_card_payment_method(method)` | внутренний хелпер | из прод-кода **не вызывается** |
| 10462 | `accrue_partner_commission(bot_id, payment_id, user_id, amount_rub, payment_method, percent)` | Accrue partner commission for a managed bot. | `src/shop_bot/bot/handlers.py::process_successful_payment`; тесты: 2 сайт(ов) |
| 10574 | `get_partner_cabinet(bot_id)` | Return partner cabinet stats for managed bot. | `src/shop_bot/bot/handlers.py::get_user_router.partner_cabinet`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount` |
| 10622 | `list_partner_requisites(bot_id, owner_telegram_id)` | Return all payout requisites for a partner (owner) within a managed bot. | `src/shop_bot/bot/handlers.py::get_user_router.partner_requisites`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_value`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_set_default`, `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_delete`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount` |
| 10647 | `get_default_partner_requisite(bot_id, owner_telegram_id)` | Return the default payout requisite for a partner, if any. | `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw`, `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount` |
| 10659 | `add_partner_requisite(bot_id, owner_telegram_id, bank, requisite_value, requisite_type, make_default)` | Add a payout requisite for a partner. | `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_value` |
| 10729 | `set_default_partner_requisite(req_id, bot_id, owner_telegram_id)` | Set given requisite as default for this bot/owner. | `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_set_default` |
| 10766 | `delete_partner_requisite(req_id, bot_id, owner_telegram_id)` | Delete a payout requisite. | `src/shop_bot/bot/handlers.py::get_user_router.partner_requisite_delete` |
| 10814 | `create_withdraw_request(bot_id, owner_telegram_id, amount_rub, comment, bank, requisite_type, requisite_value, requisite_id)` | Create a partner withdraw request. | `src/shop_bot/bot/handlers.py::get_user_router.partner_withdraw_amount` |
| 10869 | `create_user_gift(from_user_id, host_name, plan_id, gift_code, expires_in_days)` | Создать неактивированный подарок от одного пользователя. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route`; тесты: 1 сайт(ов) |
| 10920 | `get_user_gift(gift_id)` | Получить информацию о подарке по ID. | `src/shop_bot/bot/handlers.py::get_user_router.show_gift_handler`, `src/shop_bot/bot/handlers.py::get_user_router.send_gift_link_handler`, `src/shop_bot/bot/handlers.py::get_user_router.activate_own_gift_handler`; тесты: 5 сайт(ов) |
| 10934 | `get_gift_by_code(gift_code)` | Получить информацию о подарке по коду. | `src/shop_bot/webapp/handlers.py::_activate_gift_for_user`, `src/shop_bot/webapp/handlers.py::_pending_action_public_info`, `src/shop_bot/bot/handlers.py::_activate_gift_directly`, `src/shop_bot/webapp/handlers.py::web_gift_page` |
| 10948 | `get_user_inactive_gifts(from_user_id)` | Получить список неактивированных подарков пользователя. | `src/shop_bot/webapp/handlers.py::api_user_gifts`, `src/shop_bot/bot/handlers.py::get_user_router.show_inactive_gifts_handler`, `src/shop_bot/bot/handlers.py::get_user_router.gifts_page_handler`, `src/shop_bot/bot/handlers.py::show_main_menu`, `src/shop_bot/bot/handlers.py::get_user_router.profile_handler_callback`, `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 10982 | `activate_user_gift(gift_code, activated_by_user_id)` | Активировать подарок для пользователя. | `src/shop_bot/webapp/handlers.py::_activate_gift_for_user`, `src/shop_bot/bot/handlers.py::_activate_gift_directly` |
| 11039 | `_registration_age_seconds(reg_date_raw)` | Возраст аккаунта в секундах, либо None если даты нет / она не парсится. | из прод-кода **не вызывается** |
| 11052 | `set_referred_by_from_gift(user_id, from_user_id, max_age_seconds)` | Set referred_by to the gift sender when a new user activates a gift. | `src/shop_bot/webapp/handlers.py::_activate_gift_for_user`, `src/shop_bot/bot/handlers.py::_activate_gift_directly` |
| 11101 | `link_referrer_if_eligible(user_id, referrer_id, max_age_seconds)` | Привязать пользователя к рефереру (users.referred_by), если это допустимо. | `src/shop_bot/webapp/handlers.py::_apply_pending_referral`, `src/shop_bot/webhook_server/app.py::create_webhook_app.assign_referral_route` |
| 11179 | `unlink_referral(invitee_id, referrer_id)` | Снять привязку реферала: обнулить users.referred_by у invitee, если он | `src/shop_bot/webhook_server/app.py::create_webhook_app.remove_referral_route` |
| 11217 | `unlink_all_referrals(referrer_id)` | Снять привязку у всех рефералов указанного реферера. | `src/shop_bot/webhook_server/app.py::create_webhook_app.remove_all_referrals_route` |
| 11244 | `delete_user_gift(gift_id)` | Удалить подарок. | из прод-кода **не вызывается** |
| 11257 | `link_key_to_gift(gift_id, key_id)` | Связать созданный ключ с подарком. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route`; тесты: 1 сайт(ов) |
| 11273 | `get_gift_code_by_key_id(key_id)` | Получить код подарка по ID ключа. | из прод-кода **не вызывается** |
| 11286 | `get_gift_code_by_key_id(key_id)` | Получить код подарка по ID ключа. | из прод-кода **не вызывается** |
| 11299 | `get_gift_info_by_key_id(key_id)` | Получить ID и код подарка по ID ключа. Возвращает (gift_id, gift_code) или (None, None). | `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process`, `src/shop_bot/bot/handlers.py::get_user_router.remove_key_name`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_rename_key`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/bot/handlers.py::get_user_router.delete_device_handler` |
| 11319 | `get_msk_time()` | Текущее время в московской зоне (UTC+3), используется для расчётов сроков в webapp. | `src/shop_bot/webapp/handlers.py::_process_key_data`, `src/shop_bot/webapp/handlers.py::_render_main_page`, `src/shop_bot/webapp/handlers.py::_get_profile_card_html` |
| 11325 | `check_transaction_exists(payment_id)` | Проверить, существует ли уже завершённая транзакция с данным payment_id. | `src/shop_bot/webapp/handlers.py::api_check_payment`, `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 11353 | `payment_owned_by_user(payment_id, user_id)` | True, если payment_id есть в pending_transactions или transactions у этого user_id. | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webapp/handlers.py::api_check_payment` |
| 11390 | `get_seller_user(user_id)` | Вернуть данные продавца (франшиза/партнёрская скидка) для пользователя. | `src/shop_bot/webapp/handlers.py::calculate_webapp_price` |
| 11407 | `get_device_tiers(host_name)` | Вернуть тарифные планы, сгруппированные по лимиту устройств, для указанного хоста. | `src/shop_bot/webapp/handlers.py::api_device_tiers`, `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 11423 | `get_user_by_auth_token(token)` | Найти пользователя по постоянному auth-токену (webapp). | `src/shop_bot/webapp/handlers.py::api_check_auth_token`, `src/shop_bot/webapp/handlers.py::api_sync_tg`, `src/shop_bot/webapp/handlers.py::index`, `src/shop_bot/webapp/handlers.py::dynamic_route`, `src/shop_bot/webapp/handlers.py::_resolve_user_from_request_token`; тесты: 1 сайт(ов) |
| 11439 | `get_auth_token_by_user_id(user_id)` | Получить уже выданный постоянный auth-токен пользователя, если есть. | `src/shop_bot/webapp/handlers.py::_issue_persistent_token_for_telegram_user`, `src/shop_bot/webapp/handlers.py::api_check_auth_token`, `src/shop_bot/webapp/handlers.py::api_telegram_direct_auth`; тесты: 9 сайт(ов) |
| 11452 | `update_user_auth_token(user_id, token)` | Сохранить постоянный auth-токен для пользователя (webapp). | `src/shop_bot/webapp/handlers.py::_issue_persistent_token_for_telegram_user`, `src/shop_bot/webapp/handlers.py::api_email_verify`, `src/shop_bot/webapp/handlers.py::api_email_login`, `src/shop_bot/webapp/handlers.py::api_check_auth_token`, `src/shop_bot/webapp/handlers.py::api_telegram_direct_auth`; тесты: 7 сайт(ов) |
| 11465 | `invalidate_all_user_auth_tokens()` | Перевыпустить все persistent auth_token пользователей (UUID4). | `migrate_invalidate_auth_tokens.py::<module>`; тесты: 1 сайт(ов) |
| 11494 | `hash_password(password)` | Хэшировать пароль пользователя (PBKDF2-HMAC-SHA256 со случайной солью). | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 11501 | `verify_password(password, stored)` | Проверить пароль против сохранённого хэша. | `src/shop_bot/webapp/handlers.py::api_user_profile_change_password`, `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request`, `src/shop_bot/webapp/handlers.py::api_email_login` |
| 11520 | `get_user_by_email(email)` | Найти локального пользователя webapp по email (для входа по email+паролю). | `src/shop_bot/webapp/handlers.py::api_email_register`, `src/shop_bot/webapp/handlers.py::api_email_verify`, `src/shop_bot/webapp/handlers.py::api_email_resend`, `src/shop_bot/webapp/handlers.py::api_email_login`, `src/shop_bot/webapp/handlers.py::api_email_reset_request`, `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request`; тесты: 5 сайт(ов) |
| 11537 | `create_user_by_email(email, password)` | Создать "виртуального" (не привязанного к Telegram) пользователя webapp по email+паролю. | `src/shop_bot/webapp/handlers.py::api_email_register`; тесты: 4 сайт(ов) |
| 11572 | `update_user_password(email, new_password)` | Обновить (хэшированный) пароль локального webapp-аккаунта по email. | `src/shop_bot/webapp/handlers.py::api_email_reset_verify` |
| 11589 | `_hash_verification_code(user_id, code)` | внутренний хелпер | из прод-кода **не вызывается** |
| 11593 | `set_email_verification_code(user_id, code, ttl_seconds)` | Сохранить хэш одноразового кода подтверждения email и время его истечения. | `src/shop_bot/webapp/handlers.py::_issue_email_verification_code` |
| 11615 | `get_email_verification(user_id)` | Вернуть данные о статусе подтверждения email и последнем отправленном коде. | `src/shop_bot/webapp/handlers.py::api_email_resend`, `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_resend` |
| 11635 | `check_email_verification_code(user_id, code)` | Проверить введённый код подтверждения против сохранённого хэша (с учётом срока действия). | `src/shop_bot/webapp/handlers.py::api_email_verify`, `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_verify` |
| 11650 | `mark_email_verified(user_id)` | Отметить email пользователя как подтверждённый и очистить код. | `src/shop_bot/webapp/handlers.py::api_email_verify`; тесты: 4 сайт(ов) |
| 11670 | `update_email_code_last_sent(user_id)` | Обновить время последней отправки кода (для rate-limit повторной отправки). | из прод-кода **не вызывается** |
| 11686 | `update_user_password_by_id(user_id, new_password)` | Обновить (хэшированный) пароль webapp-аккаунта по telegram_id (смена пароля из профиля, | `src/shop_bot/webapp/handlers.py::api_user_profile_change_password` |
| 11701 | `set_pending_email(user_id, new_email)` | Сохранить новый email, ожидающий подтверждения кодом (смена почты из профиля). | `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request` |
| 11718 | `clear_pending_email(user_id)` | Отменить ожидающую смену email (например, пользователь передумал или запросил другой адрес). | `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_cancel`, `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request` |
| 11735 | `finalize_pending_email_change(user_id)` | Подтвердить смену email кодом: перенести `pending_email` в `auth_email`. | `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_verify` |
| 11783 | `get_webapp_settings()` | Вернуть настройки Telegram Mini App (webapp) из общей таблицы bot_settings. | `src/shop_bot/bot/handlers.py::_webapp_public_base`, `src/shop_bot/webapp/handlers.py::_render_main_page`, `src/shop_bot/webapp/handlers.py::index`, `src/shop_bot/webapp/handlers.py::web_referral_page`, `src/shop_bot/webapp/handlers.py::web_gift_page`, `src/shop_bot/webapp/handlers.py::dynamic_route` |

**Вложенные функции** (16), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 1936 | `_rebuild_vpn_keys_table.has` | `_rebuild_vpn_keys_table` |
| 1939 | `_rebuild_vpn_keys_table.col` | `_rebuild_vpn_keys_table` |
| 5027 | `create_payload_pending._work` | `create_payload_pending` |
| 5073 | `patch_pending_metadata._work` | `patch_pending_metadata` |
| 5111 | `_get_pending_metadata._work` | `_get_pending_metadata` |
| 5148 | `get_pending_record._work` | `get_pending_record` |
| 5188 | `revive_cancelled_invoice._work` | `revive_cancelled_invoice` |
| 5240 | `get_pending_status._work` | `get_pending_status` |
| 5262 | `_complete_pending._work` | `_complete_pending` |
| 5288 | `find_and_complete_pending_transaction._work` | `find_and_complete_pending_transaction` |
| 5372 | `claim_processed_payment._work` | `claim_processed_payment` |
| 5395 | `unclaim_processed_payment._work` | `unclaim_processed_payment` |
| 5484 | `cancel_pending_transaction._work` | `cancel_pending_transaction` |
| 5548 | `reset_pending_transaction._work` | `reset_pending_transaction` |
| 8076 | `log_transaction._work` | `log_transaction` |
| 11367 | `payment_owned_by_user._work` | `payment_owned_by_user` |

<a id="src-shop_bot-data_manager-remnawave_repositorypy"></a>

### `src/shop_bot/data_manager/remnawave_repository.py`

Фасад над database.py: ContextVar франшизы, промокоды, запись ключей, подарки-токены. Предпочтительная точка импорта для хендлеров (как rw_repo).

**Импорт-путь:** `shop_bot.data_manager.remnawave_repository`  
**Кто импортирует (прод):** `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot/keyboards.py`, `src/shop_bot/bot/middlewares.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/data_manager/backup_manager.py`, `src/shop_bot/data_manager/database.py`, `src/shop_bot/data_manager/resource_monitor.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/data_manager/speedtest_runner.py`, `src/shop_bot/factory_bot/handlers.py`, `src/shop_bot/factory_bot/middleware.py`, `src/shop_bot/factory_bot/service.py`, `src/shop_bot/modules/platega_fulfillment.py`, `src/shop_bot/modules/remnawave_api.py`, `src/shop_bot/support_bot/handlers.py`, `src/shop_bot/support_bot_controller.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 5 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 66 | `PromoUnavailableError` | `Exception` | Промокод нельзя зарезервировать (лимит / недействителен). |
| 1241 | `_PromoTxnAbort` | `Exception` | — |

**Функции верхнего уровня и методы классов:** 59

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 16 | `__getattr__(name)` | Модуль-level fallback (PEP 562) для `DB_FILE`. | из прод-кода **не вызывается** |
| 41 | `set_current_factory_bot_id(bot_id)` | Set current factory bot id for the running handler via contextvars. | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__` |
| 52 | `reset_current_factory_bot_id(token)` | — | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__` |
| 59 | `get_current_factory_bot_id()` | — | из прод-кода **не вызывается** |
| 69 | `PromoUnavailableError.__init__(self, reason)` | внутренний хелпер | из прод-кода **не вызывается** |
| 74 | `create_payload_pending(payment_id, user_id, amount_rub, metadata)` | Create/update pending payload metadata. | `src/shop_bot/bot/handlers.py::_create_heleket_payment_request`, `src/shop_bot/bot/handlers.py::_create_cryptobot_invoice`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_platega_handler`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_rollypay_handler`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_platega_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_rollypay_handler`, `src/shop_bot/bot/handlers.py::get_user_router.ltegb_pay_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_yoomoney_handler`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_platega`, `src/shop_bot/bot/handlers.py::get_user_router.topup_pay_rollypay`, `src/shop_bot/bot/handlers.py::get_user_router.trafficgb_pay_yookassa_handler` и ещё 16; тесты: 1 сайт(ов) |
| 121 | `cancel_pending_transaction(payment_id, user_id)` | Отменить неоплаченный pending и освободить слот промокода, если он был зарезервирован. | `src/shop_bot/bot/handlers.py::get_user_router.payment_stars_back_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_platega_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_rollypay_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.check_yookassa_payment_handler`, `src/shop_bot/bot/handlers.py::get_user_router.create_stars_invoice_handler`, `src/shop_bot/modules/platega_fulfillment.py::mark_pending_canceled`, `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.yookassa_webhook_handler` |
| 132 | `_connect()` | внутренний хелпер | из прод-кода **не вызывается** |
| 138 | `_normalize_email(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 142 | `_default_expire_at_ms()` | внутренний хелпер | из прод-кода **не вызывается** |
| 146 | `_decrypt_host_secrets(row)` | get_squad/list_squads читают xui_hosts напрямую — расшифровать как get_host. | из прод-кода **не вызывается** |
| 153 | `list_squads(active_only)` | — | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`; тесты: 1 сайт(ов) |
| 165 | `get_squad(identifier)` | — | `src/shop_bot/modules/remnawave_api.py::_load_config_for_host`, `src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host`, `src/shop_bot/modules/remnawave_api.py::get_key_details_from_host`, `src/shop_bot/webhook_server/app.py::create_webhook_app.sweep_expired_keys_route`; тесты: 1 сайт(ов) |
| 190 | `get_key_by_id(key_id)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_edit_key`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_prompt`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_extend_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_cancel`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_back`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_extend_key_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_delete_key_process`, `src/shop_bot/bot/handlers.py::get_user_router._resolve_plan_for_traffic_topup`, `src/shop_bot/bot/handlers.py::get_user_router._resolve_plan_for_lte_topup`, `src/shop_bot/bot/handlers.py::get_user_router._resolve_key_for_main_reset`, `src/shop_bot/bot/handlers.py::get_user_router.rename_key_start` и ещё 24 |
| 194 | `get_key_by_email(email)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_delete_key_process`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 198 | `get_key_by_remnawave_uuid(remnawave_uuid)` | — | из прод-кода **не вызывается** |
| 202 | `record_key(user_id, squad_uuid, remnawave_user_uuid, email, host_name, expire_at_ms, short_uuid, subscription_url, …)` | — | из прод-кода **не вызывается** |
| 265 | `record_key_from_payload(user_id, payload, host_name, description, tag)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_days`, `src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial`, `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router._gift_username_catcher`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 304 | `update_key(key_id, user_id, host_name, squad_uuid, remnawave_user_uuid, short_uuid, email, subscription_url, …)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_extend_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_extend_key_process`, `src/shop_bot/bot/handlers.py::_activate_gift_directly`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::_activate_gift_for_user`, `src/shop_bot/webhook_server/app.py::create_webhook_app.adjust_key_expiry_route` |
| 343 | `_parse_key_expiry_dt(key)` | Parse key expiry from normalized row (expiry_date / expire_at). | из прод-кода **не вызывается** |
| 366 | `_sync_key_expiry_ms(key_id, new_ms)` | Push expiry to Remnawave, then update local DB. Returns (ok, error, final_ms). | из прод-кода **не вызывается** |
| 403 | `extend_key(key_id, days)` | Продлить/сократить срок ключа на N дней (N может быть отрицательным). | `src/shop_bot/data_manager/database.py::extend_key` |
| 426 | `set_key_expiry(key_id, new_expire_at)` | Установить точную дату истечения ключа; синхронизирует Remnawave + БД. | `src/shop_bot/data_manager/database.py::set_key_expiry` |
| 463 | `delete_key_by_email(email)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 467 | `generate_key_email_for_user(user_id, domain)` | Generate a unique key email based on Telegram ID + key number. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_days`, `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::_activate_gift_directly`, `src/shop_bot/bot/handlers.py::get_user_router._gift_username_catcher`, `src/shop_bot/webapp/handlers.py::_activate_gift_for_user`, `src/shop_bot/webhook_server/app.py::create_webhook_app.generate_key_email_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_ajax_route` |
| 759 | `create_gift_token(token, host_name, days, activation_limit, expires_at, created_by, comment)` | — | из прод-кода **не вызывается** |
| 802 | `get_gift_token(token)` | — | из прод-кода **не вызывается** |
| 813 | `list_gift_tokens(active_only)` | — | из прод-кода **не вызывается** |
| 826 | `delete_gift_token(token)` | — | из прод-кода **не вызывается** |
| 837 | `claim_gift_token(token, user_id, key_id)` | — | из прод-кода **не вызывается** |
| 900 | `create_promo_code(code, discount_percent, discount_amount, usage_limit_total, usage_limit_per_user, valid_from, valid_until, created_by, …)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_confirm`, `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_coupons_create_route`; тесты: 28 сайт(ов) |
| 980 | `get_promo_code(code)` | — | из прод-кода **не вызывается**; тесты: 13 сайт(ов) |
| 991 | `list_promo_codes(include_inactive)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_list`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_change_page`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_toggle` |
| 1032 | `promo_error_message(reason)` | — | `src/shop_bot/bot/handlers.py::get_user_router.handle_promo_code_input`, `src/shop_bot/webapp/handlers.py::_create_payload_pending_or_error`, `src/shop_bot/webapp/handlers.py::api_apply_promo`, `src/shop_bot/webapp/handlers.py::api_create_payment`; тесты: 2 сайт(ов) |
| 1038 | `_serialize_applicable_plan_ids(raw)` | Validate and store plan scope as a JSON array of ints, or NULL = all plans. | из прод-кода **не вызывается** |
| 1074 | `_normalize_promo_segment(segment_type, segment_value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1095 | `_parse_applicable_plan_ids(raw)` | NULL/empty → unrestricted. Invalid JSON → empty list (fail closed). | из прод-кода **не вызывается** |
| 1120 | `_coerce_plan_id(plan_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1129 | `_user_has_active_subscription(user_id)` | True if the user has at least one vpn_keys row with expire_at > now(). | из прод-кода **не вызывается** |
| 1143 | `_user_paid_total(user_id, cursor)` | Sum of completed purchases for the user. | из прод-кода **не вызывается** |
| 1189 | `_user_matches_promo_segment(user_id, segment_type, segment_value, cursor)` | Whether the user satisfies an optional promo segment restriction. | из прод-кода **не вызывается** |
| 1214 | `_promo_targeting_error(promo, user_id, plan_id, cursor)` | plan_not_eligible / segment_not_eligible, or None if targeting passes. | из прод-кода **не вызывается** |
| 1242 | `_PromoTxnAbort.__init__(self, reason)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1247 | `_connect_promo_write()` | Write connection with BEGIN IMMEDIATE so promo limit updates serialize. | из прод-кода **не вызывается** |
| 1260 | `_with_promo_write(work, attempts)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1298 | `_promo_validity_error(promo, now_dt)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1319 | `_per_user_occupied(cursor, code, user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1339 | `_fetch_promo_row(cursor, code)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1355 | `_atomic_increment_used_total(cursor, code)` | Increment used_total only if the total limit still has a free slot. | из прод-кода **не вызывается** |
| 1372 | `_decrement_used_total(cursor, code)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1386 | `check_promo_code_available(code, user_id, plan_id)` | Проверить возможность использования промокода, не изменяя лимиты. | `src/shop_bot/bot/handlers.py::get_user_router.handle_promo_code_input`, `src/shop_bot/bot/handlers.py::get_user_router.show_payment_options`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::api_apply_promo`, `src/shop_bot/webapp/handlers.py::api_create_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app._handle_promo_after_payment`; тесты: 5 сайт(ов) |
| 1445 | `reserve_promo_code(code, user_id, payment_id, applied_amount, plan_id)` | Atomically reserve one promo usage slot for a pending payment. | `src/shop_bot/bot/handlers.py::process_successful_payment`; тесты: 12 сайт(ов) |
| 1541 | `release_promo_reservation(payment_id)` | Free a reserved slot (pending expired/cancelled). Never lets used_total go below 0. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 1582 | `release_stale_promo_reservations(max_age_hours)` | Release reservations older than TTL so abandoned invoices do not hold the limit forever. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 1611 | `update_promo_code_status(code, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_promo_toggle`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_coupons_toggle_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app._handle_promo_after_payment` |
| 1630 | `delete_promo_code(code)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.analytics_coupons_delete_route` |
| 1641 | `redeem_promo_code(code, user_id, applied_amount, order_id)` | Confirm a reserved slot (or atomically take one) and record the usage. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app._handle_promo_after_payment`; тесты: 2 сайт(ов) |
| 1764 | `search_user_keys_by_email(user_id, search_query)` | Поиск ключей пользователя по key_email. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_user_keys_input_handler`, `src/shop_bot/bot/handlers.py::get_user_router.search_keys_input_handler`, `src/shop_bot/webapp/handlers.py::api_keys_search` |
| 1769 | `search_all_keys_by_email(search_query)` | Поиск всех ключей (администраторам) по key_email. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_search_all_keys_input_handler` |

**Вложенные функции** (5), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 1173 | `_user_paid_total._sum` | `_user_paid_total` |
| 1412 | `check_promo_code_available._work` | `check_promo_code_available` |
| 1472 | `reserve_promo_code._work` | `reserve_promo_code` |
| 1547 | `release_promo_reservation._work` | `release_promo_reservation` |
| 1656 | `redeem_promo_code._work` | `redeem_promo_code` |

<a id="src-shop_bot-data_manager-schedulerpy"></a>

### `src/shop_bot/data_manager/scheduler.py`

Фоновый цикл каждые 300 с на loop основного бота: уведомления, автопродление, LTE, бэкапы, тикеты, speedtest, рассылки.

**Импорт-путь:** `shop_bot.data_manager.scheduler`  
**Кто импортирует (прод):** `src/shop_bot/__main__.py`  
**Тесты:** 4 файл(ов)

**Функции верхнего уровня и методы классов:** 38

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 45 | `format_time_left(hours)` | — | из прод-кода **не вызывается** |
| 62 | `async send_subscription_notification(bot, user_id, key_id, time_left_hours, expiry_date)` | — | из прод-кода **не вызывается** |
| 86 | `_cleanup_notified_users(all_db_keys)` | внутренний хелпер | из прод-кода **не вызывается** |
| 113 | `async check_expiring_subscriptions(bot)` | — | из прод-кода **не вызывается** |
| 154 | `_parse_dt_safe(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 178 | `_extract_used_bytes(payload)` | Пытаемся извлечь использованный трафик из payload пользователя Remnawave (если поле есть). | из прод-кода **не вызывается** |
| 208 | `_is_true(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 212 | `_get_inactive_usage_reminder_enabled()` | Глобальный переключатель напоминаний о нулевом использовании трафика. | из прод-кода **не вызывается** |
| 220 | `_get_inactive_usage_reminder_interval_hours()` | Интервал напоминаний в часах (также используется как задержка перед первым напоминанием). | из прод-кода **не вызывается** |
| 235 | `_get_inactive_usage_reminder_interval_seconds()` | внутренний хелпер | из прод-кода **не вызывается** |
| 239 | `_parse_origin_meta_from_description(description)` | внутренний хелпер | из прод-кода **не вызывается** |
| 252 | `_try_int(v)` | внутренний хелпер | из прод-кода **не вызывается** |
| 270 | `_resolve_hwid_device_limit_for_key(key, remote_user)` | Определить допустимый лимит устройств для ключа. | из прод-кода **не вызывается** |
| 317 | `_extract_device_ids(devices_payload)` | внутренний хелпер | из прод-кода **не вызывается** |
| 350 | `async check_device_limit_violations(bot)` | Проверяет превышение лимитов привязанных HWID устройств и уведомляет админов. | из прод-кода **не вызывается** |
| 479 | `async check_traffic_boost_resets(bot)` | Ежемесячный сброс трафика ключа до базовых значений тарифа. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 592 | `async enforce_dual_traffic_limits(bot)` | Двухуровневый учёт трафика (основной пул + независимый LTE-пул на premium-нодах). | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 920 | `async _legacy_check_traffic_boost_resets(bot)` | Откатывает докупленный буст трафика после ежемесячного сброса лимита на сервере (устаревшая эвристика, | из прод-кода **не вызывается** |
| 1007 | `async check_inactive_usage_reminders(bot)` | Если после выдачи ключа у пользователя не было подключенных устройств/трафика — напоминать с заданным интервалом. | из прод-кода **не вызывается** |
| 1103 | `async sync_keys_with_panels()` | — | из прод-кода **не вызывается** |
| 1268 | `async _maybe_sync_keys_with_panels()` | sync_keys_with_panels is expensive (list all users on each host). | из прод-кода **не вызывается** |
| 1284 | `async _maybe_enforce_dual_traffic_limits(bot)` | Учёт двух пулов трафика (основной + LTE) — интервал настраивается через bot_settings.dual_limit_interval_sec. | из прод-кода **не вызывается** |
| 1303 | `async _notify_auto_renew_success(bot, user_id, key_id, price, days_added, key_name)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1324 | `async _notify_auto_renew_no_balance(bot, user_id, key_id, price, key_name)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1346 | `async check_auto_renewals(bot)` | — | из прод-кода **не вызывается** |
| 1443 | `async check_broadcast_campaigns(bot)` | Send queued broadcast campaigns to inactive subscribers. | из прод-кода **не вызывается** |
| 1489 | `_ticket_files_present()` | Дешёвая проверка: нет каталога или он пуст — TTL не запускаем. | из прод-кода **не вызывается** |
| 1501 | `_maybe_purge_closed_ticket_media()` | TTL вложений. Отдельный task не создаём; если файлов нет — сразу выход. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 1521 | `_maybe_auto_close_idle_tickets()` | После ответа админа пользователь молчит N дней — закрываем тикет. SQL сразу, Telegram в фоне. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 1531 | `async periodic_subscription_check(bot_controller)` | — | `src/shop_bot/__main__.py::main.start_services` |
| 1576 | `async _maybe_sync_keys_with_panels()` | Sync with Remnawave panels is expensive; throttle to reduce bot latency. | из прод-кода **не вызывается** |
| 1588 | `async _maybe_run_periodic_speedtests()` | внутренний хелпер | из прод-кода **не вызывается** |
| 1599 | `async _run_speedtests_for_all_hosts()` | внутренний хелпер | из прод-кода **не вызывается** |
| 1629 | `async _run_speedtests_for_all_ssh_targets()` | внутренний хелпер | из прод-кода **не вызывается** |
| 1659 | `async _maybe_collect_resource_metrics(bot)` | Периодический сбор метрик (локально + SSH на хостах) и отправка алертов при превышении порогов. | из прод-кода **не вызывается** |
| 1742 | `async _maybe_run_daily_backup(bot)` | Ежедневный автобэкап базы и отправка админам. Интервал задаётся в настройках backup_interval_days. | из прод-кода **не вызывается** |
| 1773 | `async _maybe_alert(bot, scope, name, cpu, mem, disk, cpu_thr, mem_thr, …)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1873 | `async _send_alert(bot, scope, name, issues, level)` | Отправка алерта админам | из прод-кода **не вызывается** |

**Вложенные функции** (1), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 1681 | `_maybe_collect_resource_metrics._to_int` | `_maybe_collect_resource_metrics` |

<a id="src-shop_bot-data_manager-backup_managerpy"></a>

### `src/shop_bot/data_manager/backup_manager.py`

ZIP-бэкап users.db, отправка админам, restore, ротация архивов.

**Импорт-путь:** `shop_bot.data_manager.backup_manager`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py`  

**Функции верхнего уровня и методы классов:** 6

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 25 | `_timestamp()` | внутренний хелпер | из прод-кода **не вызывается** |
| 29 | `create_backup_file()` | Создаёт zip-архив с консистентной копией SQLite-БД. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_backup_db`, `src/shop_bot/data_manager/scheduler.py::_maybe_run_daily_backup`, `src/shop_bot/webhook_server/app.py::create_webhook_app.backup_db_route` |
| 64 | `cleanup_old_backups(keep)` | Хранить только N последних архивов, остальные удалять. | `src/shop_bot/data_manager/scheduler.py::_maybe_run_daily_backup` |
| 77 | `async send_backup_to_admins(bot, zip_path, request_timeout, max_attempts)` | Отправляет архив всем администраторам. Возвращает число успешных отправок. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_backup_db`, `src/shop_bot/data_manager/scheduler.py::_maybe_run_daily_backup` |
| 139 | `validate_db_file(db_path)` | Простая валидация файла БД: доступность основных таблиц. | из прод-кода **не вызывается** |
| 162 | `restore_from_file(uploaded_path)` | Восстанавливает основную БД из переданного файла .db или .zip (внутри .db). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_restore_db_receive`, `src/shop_bot/webhook_server/app.py::create_webhook_app.restore_db_route` |

<a id="src-shop_bot-data_manager-captcha_utilspy"></a>

### `src/shop_bot/data_manager/captcha_utils.py`

Генерация и проверка math/button капчи при регистрации.

**Импорт-путь:** `shop_bot.data_manager.captcha_utils`  
**Кто импортирует (прод):** `src/shop_bot/bot/handlers.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 9

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 21 | `_now_str()` | внутренний хелпер | из прод-кода **не вызывается** |
| 25 | `_expire_time_str(minutes)` | Возвращает время истечения капчи (через N минут). | из прод-кода **не вызывается** |
| 31 | `generate_math_captcha()` | Генерирует математическую задачу и правильный ответ. | из прод-кода **не вызывается** |
| 55 | `generate_button_captcha()` | Генерирует капчу с нажатием на кнопку. | из прод-кода **не вызывается** |
| 75 | `create_captcha_challenge(user_id, challenge_type, timeout_minutes)` | Создаёт новый капча-вызов для пользователя. | `src/shop_bot/bot/handlers.py::show_captcha`; тесты: 3 сайт(ов) |
| 118 | `check_captcha_answer(challenge_id, user_answer, max_attempts)` | Проверяет ответ на капчу. | `src/shop_bot/bot/handlers.py::get_user_router.captcha_answer_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_button_answer_handler` |
| 184 | `get_active_captcha_challenge(user_id)` | Получает активный капча-вызов для пользователя. | из прод-кода **не вызывается** |
| 233 | `has_passed_captcha(user_id)` | Проверяет, прошла ли капчу пользователь при регистрации. | `src/shop_bot/bot/handlers.py::get_user_router.start_handler`; тесты: 2 сайт(ов) |
| 251 | `mark_user_passed_captcha(user_id, challenge_id)` | Помечает пользователя как прошедшего капчу. | `src/shop_bot/bot/handlers.py::get_user_router.captcha_answer_handler`, `src/shop_bot/bot/handlers.py::get_user_router.captcha_button_answer_handler`; тесты: 2 сайт(ов) |

<a id="src-shop_bot-data_manager-resource_monitorpy"></a>

### `src/shop_bot/data_manager/resource_monitor.py`

Метрики CPU/RAM/диск/сеть локально (psutil) и по SSH.

**Импорт-путь:** `shop_bot.data_manager.resource_monitor`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py`  

**Функции верхнего уровня и методы классов:** 8

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 19 | `_safe_percent(numerator, denominator)` | внутренний хелпер | из прод-кода **не вызывается** |
| 29 | `get_local_metrics()` | Собрать базовые метрики локальной системы (панели). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_detailed`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_local`, `src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics`, `src/shop_bot/webhook_server/app.py::create_webhook_app.monitor_local_json` |
| 215 | `_parse_free_m(text)` | внутренний хелпер | из прод-кода **не вызывается** |
| 245 | `_parse_loadavg(text)` | внутренний хелпер | из прод-кода **не вызывается** |
| 253 | `_parse_df_h(text)` | внутренний хелпер | из прод-кода **не вызывается** |
| 281 | `_compute_cpu_percent(loadavg, cpu_count)` | внутренний хелпер | из прод-кода **не вызывается** |
| 294 | `get_remote_metrics_for_host(host_name)` | Собрать базовые метрики по SSH для хоста из xui_hosts. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_host`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_local`, `src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics`, `src/shop_bot/webhook_server/app.py::create_webhook_app.monitor_host_json` |
| 419 | `get_remote_metrics_for_target(target_name)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_monitor_target`, `src/shop_bot/webhook_server/app.py::create_webhook_app.monitor_target_json` |

<a id="src-shop_bot-data_manager-speedtest_runnerpy"></a>

### `src/shop_bot/data_manager/speedtest_runner.py`

SSH Ookla-speedtest и HTTP net-probe хостов; политика SSH host key.

**Импорт-путь:** `shop_bot.data_manager.speedtest_runner`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/resource_monitor.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 2 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 18 | `StoredHostKeyPolicy` | `paramiko.MissingHostKeyPolicy` | Принимает host key только если он совпадает с сохранённым, либо |

**Функции верхнего уровня и методы классов:** 21

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 24 | `StoredHostKeyPolicy.__init__(self, expected_b64, accept_new, on_save)` | внутренний хелпер | из прод-кода **не вызывается** |
| 35 | `StoredHostKeyPolicy.missing_host_key(self, client, hostname, key)` | — | из прод-кода **не вызывается** |
| 49 | `_apply_ssh_host_key_policy(ssh, ssh_host, ssh_port, accept_new_host_key)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 67 | `_parse_host_port_from_url(url)` | внутренний хелпер | из прод-кода **не вызывается** |
| 83 | `_parse_host_port_from_url(url)` | внутренний хелпер | из прод-кода **не вызывается** |
| 96 | `_is_blocked_probe_ip(ip_obj)` | внутренний хелпер | из прод-кода **не вызывается** |
| 107 | `_probe_target_error(url)` | Return an error string if the probe URL must not be contacted. | из прод-кода **не вызывается** |
| 135 | `async net_probe_for_host(host_row)` | Lightweight network probe from panel to host_url: TCP connect + HTTP GET / (HEAD). | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 203 | `_ssh_exec_json(ssh, commands)` | Try commands sequentially; expect JSON on stdout. Returns (json_obj, error). | из прод-кода **не вызывается** |
| 229 | `_parse_ookla_json(data)` | внутренний хелпер | из прод-кода **не вызывается** |
| 249 | `_parse_speedtest_cli_json(data)` | внутренний хелпер | из прод-кода **не вызывается** |
| 269 | `async ssh_speedtest_for_host(host_row, accept_new_host_key)` | Run speedtest on remote host via SSH. Tries Ookla CLI first, then speedtest-cli. | из прод-кода **не вызывается** |
| 345 | `async run_and_store_net_probe(host_name)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.run_host_speedtest_route` |
| 365 | `async run_and_store_ssh_speedtest(host_name, accept_new_host_key)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app.run_host_speedtest_route` |
| 385 | `async run_both_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_all`, `src/shop_bot/data_manager/scheduler.py::_run_speedtests_for_all_hosts`, `src/shop_bot/webhook_server/app.py::create_webhook_app.run_all_speedtests_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.run_host_speedtest_route` |
| 410 | `_ssh_connect(host_row, accept_new_host_key)` | внутренний хелпер | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`, `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 438 | `_ssh_exec(ssh, cmd, timeout)` | внутренний хелпер | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`, `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 446 | `async auto_install_speedtest_on_host(host_name, accept_new_host_key)` | Attempt to auto-install Ookla speedtest or speedtest-cli on remote host via SSH. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_autoinstall`, `src/shop_bot/webhook_server/app.py::create_webhook_app.auto_install_speedtest_route` |
| 593 | `_target_to_host_row(target)` | внутренний хелпер | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 603 | `async run_and_store_ssh_speedtest_for_target(target_name, accept_new_host_key)` | Выполнить SSH-спидтест для отдельной цели (speedtest_ssh_targets) и сохранить результат как host_speedtests с именем цели. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_target_hashed`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_target`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_run_all_targets`, `src/shop_bot/data_manager/scheduler.py::_run_speedtests_for_all_ssh_targets`, `src/shop_bot/webhook_server/app.py::create_webhook_app.run_ssh_target_speedtest_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.run_all_ssh_target_speedtests_route` |
| 625 | `async auto_install_speedtest_on_target(target_name, accept_new_host_key)` | Автоустановка speedtest на отдельной SSH-цели. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_autoinstall_target`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_speedtest_autoinstall_target_hashed`, `src/shop_bot/webhook_server/app.py::create_webhook_app.auto_install_speedtest_on_target_route` |

**Вложенные функции** (4), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 59 | `_apply_ssh_host_key_policy._save` | `_apply_ssh_host_key_policy` |
| 294 | `ssh_speedtest_for_host._run_ssh` | `ssh_speedtest_for_host` |
| 454 | `auto_install_speedtest_on_host._install` | `auto_install_speedtest_on_host` |
| 631 | `auto_install_speedtest_on_target._install` | `auto_install_speedtest_on_target` |

## Интеграции (`shop_bot.modules`)

<a id="src-shop_bot-modules-__init__py"></a>

### `src/shop_bot/modules/__init__.py`

Маркер пакета интеграций (платежи, Remnawave, почта). Пустой.

**Импорт-путь:** `shop_bot.modules`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/data_manager/remnawave_repository.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 12 файл(ов)

Функций нет.

<a id="src-shop_bot-modules-remnawave_apipy"></a>

### `src/shop_bot/modules/remnawave_api.py`

HTTP-клиент Remnawave Platform: пользователи, ключи, сквады, HWID, LTE-статистика.

**Импорт-путь:** `shop_bot.modules.remnawave_api`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/data_manager/remnawave_repository.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 10 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 24 | `RemnawaveAPIError` | `RuntimeError` | Base error for Remnawave API interactions. |
| 1539 | `RemnawavePathUnsupportedError` | `RemnawaveAPIError` | Путь не поддерживается этой версией панели (404 / 400 / 422 на валидации параметра). |
| 1741 | `NodeUsage` | `NamedTuple` | Расход пользователя по нодам за период + идентификатор сработавшего пути API. |

**Функции верхнего уровня и методы классов:** 76

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 34 | `_detail_is_already_in_desired_state(detail, want_enabled)` | True, если панель ответила, что пользователь уже enable/disable — это успех. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 47 | `_is_already_in_desired_state(exc, want_enabled)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 76 | `_inflight_semaphore()` | внутренний хелпер | из прод-кода **не вызывается** |
| 86 | `async _client_request(client, **kwargs)` | Один HTTP-запрос к панели с лимитом параллелизма. | из прод-кода **не вызывается** |
| 103 | `async gather_limited(coros, limit, return_exceptions)` | asyncio.gather с потолком параллелизма — для списка ключей в WebApp. | `src/shop_bot/webapp/handlers.py::_render_main_page`; тесты: 1 сайт(ов) |
| 118 | `async _get_shared_client(config)` | внутренний хелпер | из прод-кода **не вызывается** |
| 147 | `_normalize_email_for_remnawave(email)` | Normalize and validate email for Remnawave API. | из прод-кода **не вызывается** |
| 181 | `_normalize_username_for_remnawave(name)` | Normalize username to only letters, numbers, underscores and dashes. | из прод-кода **не вызывается** |
| 208 | `_load_config()` | Backward-compatible global config loader (deprecated). | из прод-кода **не вызывается** |
| 219 | `_load_config_for_host(host_name)` | Load Remnawave API config for a specific host from xui_hosts. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 237 | `_build_headers(config)` | внутренний хелпер | из прод-кода **не вызывается** |
| 248 | `async _request(method, path, json_payload, params, expected_status)` | внутренний хелпер | из прод-кода **не вызывается** |
| 296 | `async _request_for_host(host_name, method, path, json_payload, params, expected_status)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 344 | `_to_iso(dt)` | внутренний хелпер | из прод-кода **не вызывается** |
| 351 | `_extract_user_from_api_payload(payload)` | Normalize Remnawave user lookup payloads (wrapped, list, or bare dict). | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 366 | `async get_user_by_email(email, host_name)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 379 | `async get_user_by_username(username, host_name)` | — | из прод-кода **не вызывается** |
| 398 | `_classify_panel_user_ref(user_ref)` | id — числовой userId 3.x; uuid — старый идентификатор 2.x; short — shortUuid. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 410 | `_username_from_email(email)` | Локальная часть email → username, как при создании пользователя в панели. | из прод-кода **не вызывается** |
| 419 | `_panel_numeric_user_id(user)` | Числовой userId 3.x из payload пользователя, если он есть. | из прод-кода **не вызывается** |
| 432 | `panel_user_ref_from_payload(user)` | Идентификатор для путей `{userId}`: на 3.x это числовой id, на 2.x — uuid. | `src/shop_bot/bot/handlers.py::get_user_router._get_connected_devices_count`, `src/shop_bot/bot/handlers.py::get_user_router._get_devices_list`, `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`, `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`, `src/shop_bot/webapp/handlers.py::_render_main_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_traffic_route`; тесты: 1 сайт(ов) |
| 444 | `_panel_user_get_path(user_ref)` | Путь GET пользователя и допустимые статусы (3.x ждёт число, UUID даёт 400 NaN). | из прод-кода **не вызывается** |
| 457 | `_panel_hwid_devices_path(user_ref)` | GET /api/hwid/devices/{userId}: 3.x ждёт число, UUID даёт 400 NaN. | из прод-кода **не вызывается** |
| 469 | `async get_user_by_uuid(user_uuid, host_name)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/webapp/handlers.py::_render_main_page`, `src/shop_bot/webapp/handlers.py::api_create_payment`; тесты: 3 сайт(ов) |
| 483 | `async lookup_panel_user(user_ref, email, host_name)` | Найти пользователя панели: id / uuid / shortUuid, затем email, затем username. | `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`, `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`, `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_traffic_route` |
| 512 | `async panel_user_exists(user_ref, email, host_name)` | Есть ли пользователь на панели. | `src/shop_bot/bot/handlers.py::get_user_router._remnawave_key_exists`; тесты: 3 сайт(ов) |
| 545 | `_extract_hwid_devices_payload(payload)` | внутренний хелпер | из прод-кода **не вызывается** |
| 556 | `async _get_hwid_devices_by_ref(user_ref, host_name)` | внутренний хелпер | из прод-кода **не вызывается** |
| 569 | `async get_hwid_devices_for_user(user_uuid, host_name, email)` | Получить информацию об HWID-устройствах пользователя. | `src/shop_bot/bot/handlers.py::get_user_router._get_connected_devices_count`, `src/shop_bot/bot/handlers.py::get_user_router._get_devices_list`, `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`, `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_delete_all_devices_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_details_json`; тесты: 3 сайт(ов) |
| 616 | `async _resolve_hwid_owner(user_uuid, host_name, user_id, email)` | Числовой userId 3.x и/или uuid 2.x для HWID API. | из прод-кода **не вызывается** |
| 640 | `async delete_hwid_device(user_uuid, hwid, host_name, user_id, email)` | Удалить одно HWID-устройство пользователя через API. | `src/shop_bot/bot/handlers.py::get_user_router.delete_device_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_delete_device_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_delete_all_devices_route`; тесты: 2 сайт(ов) |
| 705 | `async get_connected_devices_count(user_uuid, host_name, email)` | Обёртка над get_hwid_devices_for_user для webapp: всегда возвращает | `src/shop_bot/webapp/handlers.py::api_key_devices`, `src/shop_bot/webapp/handlers.py::api_key_devices_delete_all`, `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 727 | `async delete_user_device(user_uuid, device_id, host_name, email, user_id)` | Алиас delete_hwid_device с именем, ожидаемым webapp/handlers.py. | `src/shop_bot/webapp/handlers.py::api_key_device_delete`, `src/shop_bot/webapp/handlers.py::api_key_devices_delete_all` |
| 741 | `async ensure_user(host_name, email, squad_uuid, expire_at, traffic_limit_bytes, traffic_limit_strategy, description, tag, …)` | — | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 924 | `async list_users(host_name, squad_uuid, size, max_pages)` | List users from Remnawave. | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 1111 | `async delete_user(user_uuid)` | Глобальный вариант (устарел): удаление без привязки к хосту. | из прод-кода **не вызывается** |
| 1126 | `async delete_user_on_host(host_name, user_uuid)` | Удаление пользователя на конкретном хосте, используя конфиг хоста. | из прод-кода **не вызывается** |
| 1139 | `async reset_user_traffic(user_uuid)` | — | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 1147 | `async update_user_traffic_limit(user_uuid, new_traffic_limit_bytes, host_name)` | Обновляет лимит трафика (trafficLimitBytes) пользователя в Remnawave. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`, `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_traffic_route` |
| 1160 | `async set_user_status(user_uuid, active)` | — | из прод-кода **не вызывается** |
| 1187 | `_extract_used_traffic_bytes(payload)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1199 | `async disable_user(user_uuid, host_name)` | POST /api/users/{uuid}/actions/disable — скрыть ноду (используется для 💰-premium нод при исчерпании LTE | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`; тесты: 1 сайт(ов) |
| 1230 | `async enable_user(user_uuid, host_name)` | POST /api/users/{uuid}/actions/enable — вернуть доступ пользователю на конкретном хосте. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route`; тесты: 2 сайт(ов) |
| 1260 | `async set_user_active_squads(user_uuid, squad_uuids, host_name)` | PATCH /api/users — установить полный список activeInternalSquads пользователя. | из прод-кода **не вызывается** |
| 1290 | `extract_active_squad_uuids(user_payload)` | UUID активных internal-сквадов пользователя из ответа панели. | из прод-кода **не вызывается** |
| 1314 | `async remove_squad_from_user(user_uuid, squad_uuid, host_name)` | Убрать конкретный сквад из activeInternalSquads пользователя, не трогая остальные сквады. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1337 | `async add_squad_to_user(user_uuid, squad_uuid, host_name)` | Добавить конкретный сквад в activeInternalSquads пользователя, не трогая остальные сквады. | `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_add_lte_traffic_route` |
| 1356 | `async get_user_used_traffic(user_uuid, host_name, email)` | Использованный трафик (в байтах) пользователя на конкретном инстансе Remnawave. 0, если данных нет. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`; тесты: 1 сайт(ов) |
| 1377 | `async reset_user_traffic_on_host(user_uuid, host_name)` | POST /api/users/{uuid}/actions/reset-traffic на конкретном инстансе (host-aware вариант reset_user_traffic). | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 1390 | `_extract_usage_rows(response)` | Достаёт список записей UserUsageDto из ответа Remnawave независимо от обёртки ({"response": [...]}, просто [...]). | из прод-кода **не вызывается** |
| 1408 | `async get_node_usage_range(node_uuid, start_date, end_date, host_name)` | Legacy per-node usage endpoint: GET /api/nodes/{node_uuid}/usage/range. | из прод-кода **не вызывается** |
| 1439 | `async get_bandwidth_stats_nodes_users(node_uuids, start_date, end_date, host_name)` | v2.8.0+ endpoint: POST /api/bandwidth-stats/nodes/users. | из прод-кода **не вызывается** |
| 1472 | `async get_user_lte_usage_bytes(user_uuid, lte_node_uuids, start_date, end_date, host_name)` | Суммарный расход конкретного пользователя по нодам LTE-сквада за период. | из прод-кода **не вызывается** |
| 1557 | `invalidate_squad_nodes_cache(squad_uuid)` | Сбросить кэш нод сквада (целиком или по одному squad_uuid), включая негативный. | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 1569 | `async _request_optional_path(host_name, method, path, params, json_payload)` | Запрос к пути, которого может не быть в этой версии панели. | из прод-кода **не вызывается** |
| 1600 | `async get_squad_accessible_nodes(squad_uuid, host_name, use_cache)` | Ноды, доступные через internal squad: `GET /api/internal-squads/{uuid}/accessible-nodes`. | из прод-кода **не вызывается** |
| 1702 | `async get_squad_nodes_for_class(host_name, squad_class)` | Ноды активного сквада заданного класса ('lte'/'base') у хоста. | из прод-кода **не вызывается** |
| 1728 | `async get_lte_nodes_for_host(host_name)` | Ноды активного LTE-сквада хоста (с именами — для карточки ключа и снапшотов). | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1733 | `async get_lte_node_uuids_for_host(host_name)` | UUID нод активного LTE-сквада хоста. | из прод-кода **не вызывается** |
| 1763 | `_panel_instance_key(host_name)` | Идентификатор инстанса панели (base_url) для кэша поддержки путей. | из прод-кода **не вызывается** |
| 1771 | `reset_usage_path_cache()` | Сбросить кэш решений о поддерживаемых путях (используется в тестах). | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 1777 | `_usage_path_unsupported(instance_key, path)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1790 | `_mark_usage_path_unsupported(instance_key, path)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1801 | `_as_api_date(dt)` | Оба семейства эндпоинтов ждут дату в формате YYYY-MM-DD. | из прод-кода **не вызывается** |
| 1808 | `_to_int_bytes(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1821 | `async resolve_panel_user_id(user_uuid, host_name, user_payload, email)` | Числовой `id` пользователя панели (нужен путям 3.3.2). | из прод-кода **не вызывается** |
| 1855 | `_sum_squad_scoped_days(payload, allowed_nodes)` | 3.3.2: `{response: {days: [{date, nodes: [{uuid, totalBytes}]}]}}` -> сумма по нодам. | из прод-кода **не вызывается** |
| 1869 | `_sum_user_series(payload, allowed_nodes)` | 2.8.1/3.3.2: `{response: {series\|topNodes: [{uuid, total}]}}` -> расход по нодам. | из прод-кода **не вызывается** |
| 1891 | `_sum_legacy_rows(payload, user_uuid, allowed_nodes)` | 2.8.1 legacy: плоский список `{userUuid, nodeUuid, total, date}` -> расход по нодам. | из прод-кода **не вызывается** |
| 1910 | `async get_user_node_usage_for_squad(user_uuid, host_name, squad_uuid, node_uuids, start_date, end_date, panel_user_id, user_payload, …)` | Расход пользователя по нодам LTE-сквада за период — с разбивкой по нодам. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 2093 | `async get_squad_node_overlap(host_name)` | Ноды, доступные одновременно через LTE- и base-сквад хоста. | из прод-кода **не вызывается** |
| 2108 | `async refresh_host_squad_overlap(host_name)` | Перепроверить пересечение сквадов хоста и сохранить результат для карточек. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_hosts_squad2_label`, `src/shop_bot/webhook_server/app.py::create_webhook_app.update_host_squad_selection_route` |
| 2130 | `extract_subscription_url(user_payload)` | — | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 2138 | `async create_or_update_key_on_host(host_name, email, days_to_add, expiry_timestamp_ms, description, tag, traffic_limit_bytes, traffic_limit_strategy, …)` | Legacy совместимость: создаёт/обновляет пользователя Remnawave и возвращает данные по ключу. | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_extend_process`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_gift_pick_days`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_extend_key_process`, `src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/bot/handlers.py::get_user_router._gift_username_catcher`, `src/shop_bot/bot/handlers.py::process_successful_payment`, `src/shop_bot/bot/handlers.py::get_user_router.process_trial_key_creation`, `src/shop_bot/data_manager/remnawave_repository.py::_sync_key_expiry_ms`, `src/shop_bot/data_manager/scheduler.py::check_auto_renewals`, `src/shop_bot/webhook_server/app.py::create_webhook_app.admin_key_change_plan_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.create_key_route` и ещё 2 |
| 2274 | `async get_key_details_from_host(key_data)` | — | `src/shop_bot/bot/handlers.py::get_user_router.rename_key_process`, `src/shop_bot/bot/handlers.py::get_user_router.remove_key_name`, `src/shop_bot/bot/handlers.py::get_user_router.cancel_rename_key`, `src/shop_bot/bot/handlers.py::get_user_router.show_key_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_qr_handler`, `src/shop_bot/bot/handlers.py::get_user_router.delete_device_handler`, `src/shop_bot/bot/handlers.py::get_user_router.show_gift_handler`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/webapp/handlers.py::_render_main_page`; тесты: 2 сайт(ов) |
| 2302 | `async delete_client_on_host(host_name, client_email)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_key_delete_confirm`, `src/shop_bot/bot/handlers.py::get_user_router.select_host_for_switch`, `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`, `src/shop_bot/webhook_server/app.py::create_webhook_app.revoke_keys_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_user_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.delete_key_route`, `src/shop_bot/webhook_server/app.py::create_webhook_app.sweep_expired_keys_route` |

**Вложенные функции** (10), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 111 | `gather_limited._run` | `gather_limited` |
| 949 | `list_users._extract_users_from_payload` | `list_users` |
| 958 | `list_users._filter_by_squad` | `list_users` |
| 977 | `list_users._fetch` | `list_users` |
| 1004 | `list_users._uid` | `list_users` |
| 1007 | `list_users._append_new` | `list_users` |
| 1042 | `list_users._try_paged` | `list_users` |
| 1492 | `get_user_lte_usage_bytes._sum_for_user` | `get_user_lte_usage_bytes` |
| 1638 | `get_squad_accessible_nodes._remember_failure` | `get_squad_accessible_nodes` |
| 1970 | `get_user_node_usage_for_squad._numeric_id` | `get_user_node_usage_for_squad` |

<a id="src-shop_bot-modules-platega_apipy"></a>

### `src/shop_bot/modules/platega_api.py`

Клиент Platega: создание платежа и сверка статуса (sync для Flask, async для Mini App).

**Импорт-путь:** `shop_bot.modules.platega_api`  
**Кто импортирует (прод):** `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 2 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 61 | `PlategaAPI` | — | Простой асинхронный клиент Platega API. |

**Функции верхнего уровня и методы классов:** 5

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 26 | `get_transaction_sync(merchant_id, secret, transaction_id, base_url, timeout)` | Синхронный GET /transaction/{id} для Flask-вебхука. Телу колбэка не доверяем. | `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler` |
| 71 | `PlategaAPI.__init__(self, merchant_id, secret, base_url)` | внутренний хелпер | из прод-кода **не вызывается** |
| 76 | `async PlategaAPI._request(self, method, endpoint, json_data)` | внутренний хелпер | из прод-кода **не вызывается** |
| 101 | `async PlategaAPI.create_payment(self, amount, description, payment_id, return_url, failed_url, method_code)` | Создать платёж в Platega. | из прод-кода **не вызывается** |
| 131 | `async PlategaAPI.get_transaction(self, transaction_id)` | GET /transaction/{id} — сверка статуса по provider transaction ID. | из прод-кода **не вызывается** |

<a id="src-shop_bot-modules-platega_fulfillmentpy"></a>

### `src/shop_bot/modules/platega_fulfillment.py`

Идемпотентное завершение/отмена Platega-платежа для вебхука и Mini App verify.

**Импорт-путь:** `shop_bot.modules.platega_fulfillment`  
**Кто импортирует (прод):** `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 7

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 18 | `is_platega_payment_method(pending_meta)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 25 | `provider_transaction_id_from_meta(pending_meta)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler` |
| 33 | `normalize_platega_status(raw)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler`; тесты: 1 сайт(ов) |
| 42 | `extract_platega_amount(payload)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 53 | `remote_is_canceled(remote, payment_id)` | True только если API провайдера подтвердил отмену этого счёта. | `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler`; тесты: 1 сайт(ов) |
| 66 | `mark_pending_canceled(payment_id, provider_transaction_id)` | Пометить счёт отменённым в pending и в истории транзакций. | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler` |
| 90 | `complete_pending_platega_payment(payment_id, provider_transaction_id)` | Атомарно закрыть pending и вернуть metadata. | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`, `src/shop_bot/webhook_server/app.py::create_webhook_app.platega_webhook_handler` |

<a id="src-shop_bot-modules-rollypay_apipy"></a>

### `src/shop_bot/modules/rollypay_api.py`

Клиент RollyPay с фиксированным BASE_URL, HMAC вебхука, создание/сверка платежа.

**Импорт-путь:** `shop_bot.modules.rollypay_api`  
**Кто импортирует (прод):** `src/shop_bot/bot/handlers.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 1 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 85 | `RollyPayAPI` | — | — |

**Функции верхнего уровня и методы классов:** 7

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 27 | `_safe_id(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 34 | `verify_webhook_signature(raw_body, timestamp, signature, signing_secret, tolerance, now)` | HMAC-SHA256(`{unix_ts}.{raw_body}`) в заголовке X-Signature, как в SDK RollyPay. | `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler`; тесты: 1 сайт(ов) |
| 61 | `get_payment_sync(api_key, payment_id, timeout)` | Синхронный GET /payments/{id} для Flask-вебхука. Не доверяем телу колбэка. | `src/shop_bot/webhook_server/app.py::create_webhook_app.rollypay_webhook_handler` |
| 86 | `RollyPayAPI.__init__(self, api_key, terminal_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 90 | `RollyPayAPI._headers(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 98 | `async RollyPayAPI.create_payment(self, amount, description, order_id, success_url, fail_url, payment_method, customer_id)` | Возвращает (pay_url, provider_payment_id) или (None, None). | из прод-кода **не вызывается** |
| 161 | `async RollyPayAPI.get_payment(self, payment_id)` | — | из прод-кода **не вызывается** |

<a id="src-shop_bot-modules-heleket_apipy"></a>

### `src/shop_bot/modules/heleket_api.py`

Создание крипто-инвойса Heleket. Mini App импортирует модуль; основной бот дублирует логику у себя.

**Импорт-путь:** `shop_bot.modules.heleket_api`  
**Кто импортирует (прод):** `src/shop_bot/webapp/handlers.py`  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 26 | `async create_heleket_payment_request(amount, currency, description, return_url, user_id, email, order_id)` | Создать инвойс в Heleket. | `src/shop_bot/webapp/handlers.py::api_create_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`, `src/shop_bot/webapp/handlers.py::api_create_payment` |

<a id="src-shop_bot-modules-cryptobot_apipy"></a>

### `src/shop_bot/modules/cryptobot_api.py`

Клиент Crypto Pay. В runtime не импортируется — дубль живёт в bot/handlers.py.

**Импорт-путь:** `shop_bot.modules.cryptobot_api`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 23 | `async create_cryptobot_api_invoice(amount, payload_str)` | Создать инвойс в Crypto Pay (CryptoBot) в фиате RUB. | из прод-кода **не вызывается** |

<a id="src-shop_bot-modules-email_senderpy"></a>

### `src/shop_bot/modules/email_sender.py`

SMTP-отправка кодов активации/сброса для email-регистрации Mini App.

**Импорт-путь:** `shop_bot.modules.email_sender`  
**Кто импортирует (прод):** `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 6

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 36 | `_get_service_name()` | Название сервиса для From/Subject писем (не хардкод репозитория). | из прод-кода **не вызывается** |
| 45 | `_get_smtp_settings()` | внутренний хелпер | из прод-кода **не вызывается** |
| 67 | `_auth_hint_for_host(host)` | внутренний хелпер | из прод-кода **не вызывается** |
| 75 | `is_smtp_configured()` | Проверить, заполнены ли минимально необходимые настройки SMTP. | `src/shop_bot/webapp/handlers.py::_issue_email_verification_code`, `src/shop_bot/webhook_server/app.py::create_webhook_app.smtp_test_route` |
| 81 | `_send_once(host, port, settings, to_email, message, connect_timeout)` | внутренний хелпер | из прод-кода **не вызывается** |
| 99 | `send_activation_code(to_email, code, max_attempts, retry_delay_seconds)` | Отправить письмо с одноразовым кодом активации email. | `src/shop_bot/webapp/handlers.py::_issue_email_verification_code`, `src/shop_bot/webhook_server/app.py::create_webhook_app.smtp_test_route` |

<a id="src-shop_bot-modules-telegram_reachabilitypy"></a>

### `src/shop_bot/modules/telegram_reachability.py`

Классификация Telegram 403 (blocked/deactivated) и пометка пользователя unreachable.

**Импорт-путь:** `shop_bot.modules.telegram_reachability`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/webhook_server/app.py`  

**Функции верхнего уровня и методы классов:** 2

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 30 | `classify_unreachable_error(exc)` | Определить, означает ли ошибка отправки недоступность пользователя в Telegram. | из прод-кода **не вызывается** |
| 49 | `handle_send_exception(user_id, exc)` | Проверить ошибку отправки сообщения пользователю и, если она означает | `src/shop_bot/bot/admin_handlers.py::get_admin_router.confirm_broadcast_handler`, `src/shop_bot/data_manager/scheduler.py::send_subscription_notification`, `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`, `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`, `src/shop_bot/webhook_server/app.py::_dispatch_bot_notification._send` |

## Ядро плагинов (`shop_bot.core`)

<a id="src-shop_bot-core-__init__py"></a>

### `src/shop_bot/core/__init__.py`

Реэкспорт ModuleLoader, ModuleMeta, ModuleStatus, get_global_module_loader.

**Импорт-путь:** `shop_bot.core`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  
**Тесты:** 1 файл(ов)

Функций нет.

<a id="src-shop_bot-core-module_loaderpy"></a>

### `src/shop_bot/core/module_loader.py`

Discover/enable/disable/delete плагинов из modules/, ZIP-импорт, регистрация router и Flask blueprint.

**Импорт-путь:** `shop_bot.core.module_loader`  
**Кто импортирует (прод):** `modules/ramadan_tracker/bot_handlers.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/core/__init__.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 1 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 68 | `_LoadedModule` | — | — |
| 80 | `ModuleLoader` | — | Discovers, loads, and manages plugin modules. |

**Функции верхнего уровня и методы классов:** 46

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 83 | `ModuleLoader.__init__(self, modules_path, db_file)` | внутренний хелпер | из прод-кода **не вызывается** |
| 94 | `ModuleLoader.set_dispatcher(self, dispatcher)` | Attach aiogram dispatcher for module router registration. | из прод-кода **не вызывается** |
| 99 | `ModuleLoader.set_flask_app(self, app)` | Attach Flask app for module blueprint registration. | из прод-кода **не вызывается** |
| 104 | `ModuleLoader.discover_modules(self)` | Discover module manifests under the modules directory. | из прод-кода **не вызывается** |
| 133 | `ModuleLoader.list_modules(self)` | Return a list of modules with status for UI usage. | из прод-кода **не вызывается** |
| 179 | `ModuleLoader.get_module_status(self, module_id)` | Return current status for a module. | из прод-кода **не вызывается** |
| 190 | `ModuleLoader.load_module(self, module_id)` | Import module code and prepare its hooks. | из прод-кода **не вызывается** |
| 228 | `ModuleLoader.unload_module(self, module_id)` | Unload module hooks and imported code. | из прод-кода **не вызывается** |
| 243 | `ModuleLoader.enable_module(self, module_id, from_startup)` | Enable a module and register its hooks. | из прод-кода **не вызывается** |
| 273 | `ModuleLoader.disable_module(self, module_id)` | Disable a module without deleting its data. | из прод-кода **не вызывается** |
| 286 | `ModuleLoader.delete_module(self, module_id)` | Delete a module and remove its data. | из прод-кода **не вызывается** |
| 307 | `ModuleLoader.get_menu_items(self)` | Collect panel menu items from enabled modules. | из прод-кода **не вызывается** |
| 319 | `ModuleLoader.get_settings_schema(self, module_id)` | Return module settings schema if available. | из прод-кода **не вызывается** |
| 330 | `ModuleLoader.get_settings_values(self, module_id)` | Return current values for module settings. | из прод-кода **не вызывается** |
| 347 | `ModuleLoader.set_module_error(self, module_id, message)` | Mark module as failed with error message. | из прод-кода **не вызывается** |
| 351 | `ModuleLoader._activate_enabled_modules(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 366 | `ModuleLoader._load_manifest(self, module_path)` | внутренний хелпер | из прод-кода **не вызывается** |
| 375 | `ModuleLoader._validate_module_meta(self, meta, folder_name)` | внутренний хелпер | из прод-кода **не вызывается** |
| 387 | `ModuleLoader._import_from_path(self, file_path, module_name)` | внутренний хелпер | из прод-кода **не вызывается** |
| 396 | `ModuleLoader._load_router(self, module_id, meta, module_path, names)` | внутренний хелпер | из прод-кода **не вызывается** |
| 411 | `ModuleLoader._load_blueprint(self, module_id, meta, module_path, names)` | внутренний хелпер | из прод-кода **не вызывается** |
| 424 | `ModuleLoader._load_schema_sql(self, meta, module_path, names)` | внутренний хелпер | из прод-кода **не вызывается** |
| 446 | `ModuleLoader._load_cleanup(self, meta, module_path, names)` | внутренний хелпер | из прод-кода **не вызывается** |
| 459 | `ModuleLoader._load_settings_schema(self, meta, module_path, names)` | внутренний хелпер | из прод-кода **не вызывается** |
| 472 | `ModuleLoader._validate_schema(self, module_id, statements)` | внутренний хелпер | из прод-кода **не вызывается** |
| 480 | `ModuleLoader._apply_schema(self, module_id, statements)` | внутренний хелпер | из прод-кода **не вызывается** |
| 491 | `ModuleLoader._ensure_settings_defaults(self, module_id, settings)` | внутренний хелпер | из прод-кода **не вызывается** |
| 514 | `ModuleLoader._delete_settings_prefix(self, module_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 519 | `ModuleLoader._attach_router(self, module_id, router)` | внутренний хелпер | из прод-кода **не вызывается** |
| 540 | `ModuleLoader._detach_router(self, dispatcher, router)` | Detach router from dispatcher. | из прод-кода **не вызывается** |
| 554 | `ModuleLoader._register_blueprint(self, module_id, blueprint)` | Store blueprint routes in a registry for dynamic dispatch. | из прод-кода **не вызывается** |
| 600 | `ModuleLoader._unregister_blueprint(self, module_id)` | Remove registered blueprint routes from the registry. | из прод-кода **не вызывается** |
| 608 | `ModuleLoader._get_dependents(self, module_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 615 | `ModuleLoader._delete_module_files(self, module_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 625 | `ModuleLoader._normalize_zip_member_name(name)` | Normalize a ZIP member path; return None if the name is unsafe. | из прод-кода **не вызывается** |
| 644 | `ModuleLoader._is_allowed_module_member(cls, relative_path)` | Allow only module source/manifest/assets; reject scripts and binaries. | из прод-кода **не вызывается** |
| 659 | `ModuleLoader._resolve_extract_path(self, target_root, relative_path)` | Resolve extract destination and ensure it stays under target_root (zip-slip). | из прод-кода **не вызывается** |
| 677 | `ModuleLoader.import_module_from_zip(self, zip_file_path, auto_enable)` | Import a module from a ZIP file. | из прод-кода **не вызывается** |
| 826 | `ModuleLoader._upsert_registry(self, meta)` | внутренний хелпер | из прод-кода **не вызывается** |
| 843 | `ModuleLoader._insert_registry(self, meta)` | внутренний хелпер | из прод-кода **не вызывается** |
| 856 | `ModuleLoader._delete_registry(self, module_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 861 | `ModuleLoader._set_status(self, module_id, status, error_message)` | внутренний хелпер | из прод-кода **не вызывается** |
| 874 | `ModuleLoader._set_module_buttons_active(self, module_id, active)` | Enable or disable buttons associated with a module. | из прод-кода **не вызывается** |
| 888 | `ModuleLoader._get_registry_row(self, module_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 896 | `ModuleLoader._fetch_registry_rows(self)` | внутренний хелпер | из прод-кода **не вызывается** |
| 910 | `get_global_module_loader()` | — | `src/shop_bot/bot_controller.py::BotController.start`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.show_admin_modules_menu`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_module_enable_handler`, `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_module_disable_handler`, `src/shop_bot/webhook_server/app.py::create_webhook_app`, `modules/ramadan_tracker/bot_handlers.py::_get_settings` |

<a id="src-shop_bot-core-module_typespy"></a>

### `src/shop_bot/core/module_types.py`

Типы манифеста плагина: ModuleMeta, ModuleStatus, ModuleInfo.

**Импорт-путь:** `shop_bot.core.module_types`  
**Кто импортирует (прод):** `modules/example_module/__init__.py`, `modules/ramadan_tracker/__init__.py`, `src/shop_bot/core/__init__.py`, `src/shop_bot/core/module_loader.py`  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 8 | `ModuleStatus` | `str`, `Enum` | Runtime status for a plugin module. |
| 18 | `ModuleMeta` | — | Module manifest metadata. |
| 69 | `ModuleInfo` | — | Public-facing module information for UIs. |

**Функции верхнего уровня и методы классов:** 3

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 35 | `ModuleMeta.from_dict(cls, data)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._load_manifest` |
| 51 | `ModuleMeta.to_dict(self)` | — | из прод-кода **не вызывается** |
| 79 | `ModuleInfo.to_dict(self)` | — | из прод-кода **не вызывается** |

<a id="src-shop_bot-core-module_middlewarepy"></a>

### `src/shop_bot/core/module_middleware.py`

ModuleSafeMiddleware: изоляция ошибок плагина и whitelist callback_data.

**Импорт-путь:** `shop_bot.core.module_middleware`  
**Кто импортирует (прод):** `src/shop_bot/core/module_loader.py`  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 14 | `ModuleSafeMiddleware` | `BaseMiddleware` | Catches module handler errors and marks the module as failed. |

**Функции верхнего уровня и методы классов:** 4

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 17 | `ModuleSafeMiddleware.__init__(self, module_id, module_loader)` | внутренний хелпер | из прод-кода **не вызывается** |
| 21 | `async ModuleSafeMiddleware.__call__(self, handler, event, data)` | внутренний хелпер | из прод-кода **не вызывается** |
| 46 | `ModuleSafeMiddleware._is_allowed_callback(self, event)` | внутренний хелпер | из прод-кода **не вызывается** |
| 56 | `async ModuleSafeMiddleware._notify_admins(self, event, exc)` | внутренний хелпер | из прод-кода **не вызывается** |

## Админ-панель Flask

<a id="src-shop_bot-webhook_server-__init__py"></a>

### `src/shop_bot/webhook_server/__init__.py`

Маркер пакета панели. Пустой.

**Импорт-путь:** `shop_bot.webhook_server`  
**Кто импортирует (прод):** `src/shop_bot/__main__.py`, `src/shop_bot/support_bot/idle_close.py`  
**Тесты:** 20 файл(ов)

Функций нет.

<a id="src-shop_bot-webhook_server-apppy"></a>

### `src/shop_bot/webhook_server/app.py`

Flask-админка: CRUD, аналитика, вебхуки платежей, модули, франшиза, support, монитор.

**Импорт-путь:** `shop_bot.webhook_server.app`  
**Кто импортирует (прод):** `src/shop_bot/__main__.py`, `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/keyboards.py`, `src/shop_bot/support_bot/idle_close.py`  
**Тесты:** 23 файл(ов)

**Функции верхнего уровня и методы классов:** 17

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 144 | `_parse_decimal_amount(value, log_prefix)` | внутренний хелпер | из прод-кода **не вызывается** |
| 160 | `_setting_flag_enabled(raw)` | внутренний хелпер | из прод-кода **не вызывается** |
| 164 | `_pending_method_allowed(pending_meta, *allowed)` | True if pending metadata.payment_method matches one of the allowed provider names. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 172 | `_pending_expected_amount(pending_meta)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 181 | `_platega_amount_covers_order(got_amount, expected_amount)` | Platega callback amount is what the customer paid. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 190 | `_extract_platega_webhook_amount(payload)` | Platega callback: top-level `amount`, with paymentDetails.amount as fallback. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 202 | `_dispatch_payment_processing(metadata)` | Fulfill paid orders even when the polling bot loop isn't running. | из прод-кода **не вызывается** |
| 250 | `_dispatch_bot_notification(user_id, text)` | Отправляет произвольное текстовое уведомление пользователю бота из админ-панели | из прод-кода **не вызывается** |
| 438 | `franchise_settings()` | Возвращает текущее состояние франшизы. | `src/shop_bot/bot/admin_handlers.py::get_admin_router._get_franchise_settings_for_admin`, `src/shop_bot/bot/keyboards.py::create_main_menu_keyboard`, `src/shop_bot/bot/keyboards.py::create_dynamic_keyboard`; тесты: 1 сайт(ов) |
| 450 | `franchise_menu_button_visible()` | Видимость пункта «Франшиза» в меню веб-админки (независимо от franchise_enabled). | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 459 | `_run_on_root_bot_loop(action, wait, timeout)` | Запустить coroutine action(service) на loop root-бота из Flask-потока. | из прод-кода **не вызывается** |
| 493 | `_apply_franchise_runtime(enabled)` | Включить/выключить все клоны на уже работающем event loop. | из прод-кода **не вызывается** |
| 506 | `toggle_franchise_settings()` | Переключает состояние франшизы (ВКЛ/ВЫКЛ). | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_franchise_toggle` |
| 531 | `_forum_coro_wait(loop, coro, timeout)` | внутренний хелпер | из прод-кода **не вызывается** |
| 536 | `run_bulk_ticket_followup(action, forum_targets, media_ticket_ids, bot, loop, gap_sec, call_timeout)` | Форум и файлы после массового SQL. Не вызывать из HTTP-потока в проде. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 615 | `create_webhook_app(bot_controller_instance)` | — | `src/shop_bot/__main__.py::main`; тесты: 31 сайт(ов) |
| 7526 | `_coerce_checkbox(value)` | внутренний хелпер | из прод-кода **не вызывается** |

**Вложенные функции** (224), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 231 | `_dispatch_payment_processing._worker` | `_dispatch_payment_processing` |
| 232 | `_dispatch_payment_processing._worker._run` | `_dispatch_payment_processing._worker` |
| 267 | `_dispatch_bot_notification._send` | `_dispatch_bot_notification` |
| 282 | `_dispatch_bot_notification._worker` | `_dispatch_bot_notification` |
| 283 | `_dispatch_bot_notification._worker._run` | `_dispatch_bot_notification._worker` |
| 665 | `create_webhook_app._handle_promo_after_payment` | `create_webhook_app` |
| 760 | `create_webhook_app.inject_current_year` | `create_webhook_app` |
| 799 | `create_webhook_app.login_required` | `create_webhook_app` |
| 801 | `create_webhook_app.login_required.decorated_function` | `create_webhook_app.login_required` |
| 811 | `create_webhook_app._rate_limit_login` | `create_webhook_app` |
| 824 | `create_webhook_app._login_client_ip` | `create_webhook_app` |
| 833 | `create_webhook_app._verify_panel_password` | `create_webhook_app` |
| 846 | `create_webhook_app.login_page` | `create_webhook_app` |
| 890 | `create_webhook_app.logout_page` | `create_webhook_app` |
| 895 | `create_webhook_app.get_common_template_data` | `create_webhook_app` |
| 943 | `create_webhook_app.update_brand_title_route` | `create_webhook_app` |
| 955 | `create_webhook_app.index` | `create_webhook_app` |
| 960 | `create_webhook_app.dashboard_page` | `create_webhook_app` |
| 1004 | `create_webhook_app.run_speedtests_route` | `create_webhook_app` |
| 1014 | `create_webhook_app.dashboard_stats_partial` | `create_webhook_app` |
| 1026 | `create_webhook_app.dashboard_transactions_partial` | `create_webhook_app` |
| 1034 | `create_webhook_app.dashboard_charts_json` | `create_webhook_app` |
| 1041 | `create_webhook_app.statistics_page` | `create_webhook_app` |
| 1197 | `create_webhook_app.statistics_page._labels` | `create_webhook_app.statistics_page` |
| 1285 | `create_webhook_app.analytics_overview_page` | `create_webhook_app` |
| 1303 | `create_webhook_app.analytics_overview_charts_json` | `create_webhook_app` |
| 1310 | `create_webhook_app.analytics_transactions_page` | `create_webhook_app` |
| 1335 | `create_webhook_app.analytics_transactions_csv` | `create_webhook_app` |
| 1368 | `create_webhook_app.analytics_plans_page` | `create_webhook_app` |
| 1375 | `create_webhook_app.analytics_payment_methods_page` | `create_webhook_app` |
| 1382 | `create_webhook_app.analytics_referrals_page` | `create_webhook_app` |
| 1398 | `create_webhook_app.analytics_coupons_page` | `create_webhook_app` |
| 1406 | `create_webhook_app.analytics_coupons_create_route` | `create_webhook_app` |
| 1458 | `create_webhook_app.analytics_coupons_toggle_route` | `create_webhook_app` |
| 1469 | `create_webhook_app.analytics_coupons_delete_route` | `create_webhook_app` |
| 1479 | `create_webhook_app.analytics_utm_page` | `create_webhook_app` |
| 1493 | `create_webhook_app.analytics_utm_create_route` | `create_webhook_app` |
| 1514 | `create_webhook_app.analytics_utm_delete_route` | `create_webhook_app` |
| 1527 | `create_webhook_app._referral_program_common` | `create_webhook_app` |
| 1537 | `create_webhook_app.referral_program_page` | `create_webhook_app` |
| 1542 | `create_webhook_app.referral_program_settings_page` | `create_webhook_app` |
| 1557 | `create_webhook_app.referral_program_settings_route` | `create_webhook_app` |
| 1580 | `create_webhook_app.referral_program_top_page` | `create_webhook_app` |
| 1593 | `create_webhook_app.referral_program_requests_page` | `create_webhook_app` |
| 1608 | `create_webhook_app.referral_program_request_status_route` | `create_webhook_app` |
| 1647 | `create_webhook_app.analytics_economics_page` | `create_webhook_app` |
| 1661 | `create_webhook_app.analytics_economics_create_route` | `create_webhook_app` |
| 1677 | `create_webhook_app.analytics_economics_delete_route` | `create_webhook_app` |
| 1684 | `create_webhook_app.analytics_forecast_page` | `create_webhook_app` |
| 1700 | `create_webhook_app.analytics_broadcasts_page` | `create_webhook_app` |
| 1714 | `create_webhook_app.analytics_broadcasts_create` | `create_webhook_app` |
| 1735 | `create_webhook_app.analytics_broadcasts_update` | `create_webhook_app` |
| 1752 | `create_webhook_app.analytics_broadcasts_toggle` | `create_webhook_app` |
| 1759 | `create_webhook_app.analytics_broadcasts_delete` | `create_webhook_app` |
| 1768 | `create_webhook_app.analytics_broadcasts_send_now` | `create_webhook_app` |
| 1800 | `create_webhook_app._build_nginx_config` | `create_webhook_app` |
| 1825 | `create_webhook_app._build_nginx_ssl_config` | `create_webhook_app` |
| 1867 | `create_webhook_app.webapp_nginx_config_route` | `create_webhook_app` |
| 1882 | `create_webhook_app.webapp_setup_route` | `create_webhook_app` |
| 1889 | `create_webhook_app.webapp_setup_route._step` | `create_webhook_app.webapp_setup_route` |
| 1892 | `create_webhook_app.webapp_setup_route._run` | `create_webhook_app.webapp_setup_route` |
| 1934 | `create_webhook_app.webapp_setup_route._nginx_reload` | `create_webhook_app.webapp_setup_route` |
| 1949 | `create_webhook_app.webapp_setup_route._nginx_start` | `create_webhook_app.webapp_setup_route` |
| 2033 | `create_webhook_app.webapp_setup_route._find_traefik_dynamic_dir` | `create_webhook_app.webapp_setup_route` |
| 2133 | `create_webhook_app.webapp_setup_route._write_traefik_config` | `create_webhook_app.webapp_setup_route` |
| 2247 | `create_webhook_app.webapp_check_route` | `create_webhook_app` |
| 2267 | `create_webhook_app.monitor_page` | `create_webhook_app` |
| 2282 | `create_webhook_app.monitor_local_json` | `create_webhook_app` |
| 2291 | `create_webhook_app.monitor_host_json` | `create_webhook_app` |
| 2300 | `create_webhook_app.monitor_target_json` | `create_webhook_app` |
| 2310 | `create_webhook_app.monitor_series_json` | `create_webhook_app` |
| 2325 | `create_webhook_app.support_table_partial` | `create_webhook_app` |
| 2334 | `create_webhook_app.support_open_count_partial` | `create_webhook_app` |
| 2350 | `create_webhook_app.users_page` | `create_webhook_app` |
| 2395 | `create_webhook_app.users_table_partial` | `create_webhook_app` |
| 2427 | `create_webhook_app.user_keys_partial` | `create_webhook_app` |
| 2442 | `create_webhook_app.user_transactions_partial` | `create_webhook_app` |
| 2465 | `create_webhook_app.user_referrals_json` | `create_webhook_app` |
| 2474 | `create_webhook_app.users_search_json` | `create_webhook_app` |
| 2503 | `create_webhook_app.admin_global_search_json` | `create_webhook_app` |
| 2549 | `create_webhook_app.assign_referral_route` | `create_webhook_app` |
| 2583 | `create_webhook_app.remove_referral_route` | `create_webhook_app` |
| 2601 | `create_webhook_app.remove_all_referrals_route` | `create_webhook_app` |
| 2620 | `create_webhook_app.users_pagination_partial` | `create_webhook_app` |
| 2632 | `create_webhook_app.user_details_json` | `create_webhook_app` |
| 2686 | `create_webhook_app.adjust_balance_route` | `create_webhook_app` |
| 2727 | `create_webhook_app.adjust_referral_balance_route` | `create_webhook_app` |
| 2766 | `create_webhook_app.admin_keys_page` | `create_webhook_app` |
| 2808 | `create_webhook_app.admin_keys_table_partial` | `create_webhook_app` |
| 2823 | `create_webhook_app.admin_keys_pagination_partial` | `create_webhook_app` |
| 2841 | `create_webhook_app._resolve_key_plan` | `create_webhook_app` |
| 2855 | `create_webhook_app.admin_key_details_json` | `create_webhook_app` |
| 3001 | `create_webhook_app.admin_key_change_plan_route` | `create_webhook_app` |
| 3089 | `create_webhook_app.admin_key_add_traffic_route` | `create_webhook_app` |
| 3150 | `create_webhook_app.admin_key_add_lte_traffic_route` | `create_webhook_app` |
| 3213 | `create_webhook_app.admin_key_delete_device_route` | `create_webhook_app` |
| 3243 | `create_webhook_app.admin_key_delete_all_devices_route` | `create_webhook_app` |
| 3296 | `create_webhook_app.admin_get_plans_for_host_json` | `create_webhook_app` |
| 3314 | `create_webhook_app.create_key_route` | `create_webhook_app` |
| 3402 | `create_webhook_app.create_key_ajax_route` | `create_webhook_app` |
| 3655 | `create_webhook_app.generate_key_email_route` | `create_webhook_app` |
| 3668 | `create_webhook_app.delete_key_route` | `create_webhook_app` |
| 3685 | `create_webhook_app.adjust_key_expiry_route` | `create_webhook_app` |
| 3759 | `create_webhook_app.sweep_expired_keys_route` | `create_webhook_app` |
| 3835 | `create_webhook_app._parse_bulk_expiry_params` | `create_webhook_app` |
| 3855 | `create_webhook_app._apply_bulk_expiry_to_ids` | `create_webhook_app` |
| 3877 | `create_webhook_app._flash_bulk_expiry_result` | `create_webhook_app` |
| 3891 | `create_webhook_app._dispatch_bulk_expiry` | `create_webhook_app` |
| 3905 | `create_webhook_app._dispatch_bulk_expiry._run` | `create_webhook_app._dispatch_bulk_expiry` |
| 3947 | `create_webhook_app._dispatch_bulk_expiry._job` | `create_webhook_app._dispatch_bulk_expiry` |
| 3978 | `create_webhook_app.bulk_extend_keys_route` | `create_webhook_app` |
| 4010 | `create_webhook_app.bulk_extend_all_keys_route` | `create_webhook_app` |
| 4034 | `create_webhook_app.bulk_extend_user_keys_route` | `create_webhook_app` |
| 4070 | `create_webhook_app.update_key_comment_route` | `create_webhook_app` |
| 4079 | `create_webhook_app.update_host_ssh_route` | `create_webhook_app` |
| 4102 | `create_webhook_app.run_ssh_target_speedtest_route` | `create_webhook_app` |
| 4128 | `create_webhook_app.run_all_ssh_target_speedtests_route` | `create_webhook_app` |
| 4163 | `create_webhook_app.run_host_speedtest_route` | `create_webhook_app` |
| 4195 | `create_webhook_app.host_speedtests_json` | `create_webhook_app` |
| 4211 | `create_webhook_app.run_all_speedtests_route` | `create_webhook_app` |
| 4246 | `create_webhook_app.auto_install_speedtest_route` | `create_webhook_app` |
| 4274 | `create_webhook_app.admin_balance_page` | `create_webhook_app` |
| 4294 | `create_webhook_app.support_list_page` | `create_webhook_app` |
| 4316 | `create_webhook_app._schedule_bulk_ticket_followup` | `create_webhook_app` |
| 4335 | `create_webhook_app._schedule_bulk_ticket_followup._job` | `create_webhook_app._schedule_bulk_ticket_followup` |
| 4347 | `create_webhook_app.support_bulk_close_route` | `create_webhook_app` |
| 4367 | `create_webhook_app.support_bulk_delete_route` | `create_webhook_app` |
| 4388 | `create_webhook_app.support_ticket_page` | `create_webhook_app` |
| 4492 | `create_webhook_app.support_ticket_messages_api` | `create_webhook_app` |
| 4507 | `create_webhook_app.block_ticket_files_dir` | `create_webhook_app` |
| 4511 | `create_webhook_app.support_ticket_file` | `create_webhook_app` |
| 4567 | `create_webhook_app.delete_support_ticket_route` | `create_webhook_app` |
| 4607 | `create_webhook_app.settings_page` | `create_webhook_app` |
| 4842 | `create_webhook_app._as_bool` | `create_webhook_app` |
| 4845 | `create_webhook_app._get_module_info` | `create_webhook_app` |
| 4851 | `create_webhook_app._build_module_settings_form` | `create_webhook_app` |
| 4881 | `create_webhook_app.modules_page` | `create_webhook_app` |
| 4888 | `create_webhook_app.module_enable_route` | `create_webhook_app` |
| 4895 | `create_webhook_app.module_disable_route` | `create_webhook_app` |
| 4902 | `create_webhook_app.module_delete_route` | `create_webhook_app` |
| 4909 | `create_webhook_app.module_settings_page` | `create_webhook_app` |
| 4946 | `create_webhook_app.module_page_proxy` | `create_webhook_app` |
| 4995 | `create_webhook_app.module_page_proxy.wrapped_render_template` | `create_webhook_app.module_page_proxy` |
| 5025 | `create_webhook_app.module_upload_route` | `create_webhook_app` |
| 5077 | `create_webhook_app.create_ssh_target_route` | `create_webhook_app` |
| 5106 | `create_webhook_app.update_ssh_target_route` | `create_webhook_app` |
| 5132 | `create_webhook_app.delete_ssh_target_route` | `create_webhook_app` |
| 5141 | `create_webhook_app.auto_install_speedtest_on_target_route` | `create_webhook_app` |
| 5169 | `create_webhook_app.smtp_test_route` | `create_webhook_app` |
| 5207 | `create_webhook_app.backup_db_route` | `create_webhook_app` |
| 5222 | `create_webhook_app.restore_db_route` | `create_webhook_app` |
| 5267 | `create_webhook_app.update_remnawave_settings_route` | `create_webhook_app` |
| 5290 | `create_webhook_app.add_remnawave_squad_route` | `create_webhook_app` |
| 5303 | `create_webhook_app.delete_remnawave_squad_route` | `create_webhook_app` |
| 5310 | `create_webhook_app.update_host_squad_selection_route` | `create_webhook_app` |
| 5344 | `create_webhook_app.update_host_subscription_route` | `create_webhook_app` |
| 5359 | `create_webhook_app.update_host_url_route` | `create_webhook_app` |
| 5371 | `create_webhook_app.update_host_remnawave_route` | `create_webhook_app` |
| 5390 | `create_webhook_app.add_host_squad_route` | `create_webhook_app` |
| 5404 | `create_webhook_app.toggle_host_squad_route` | `create_webhook_app` |
| 5412 | `create_webhook_app.delete_host_squad_route` | `create_webhook_app` |
| 5419 | `create_webhook_app.rename_host_route` | `create_webhook_app` |
| 5431 | `create_webhook_app.start_support_bot_route` | `create_webhook_app` |
| 5436 | `create_webhook_app._wait_for_stop` | `create_webhook_app` |
| 5447 | `create_webhook_app.stop_support_bot_route` | `create_webhook_app` |
| 5455 | `create_webhook_app.start_bot_route` | `create_webhook_app` |
| 5462 | `create_webhook_app.stop_bot_route` | `create_webhook_app` |
| 5470 | `create_webhook_app.stop_both_bots_route` | `create_webhook_app` |
| 5489 | `create_webhook_app._soft_stop_controller` | `create_webhook_app` |
| 5498 | `create_webhook_app.restart_both_bots_route` | `create_webhook_app` |
| 5525 | `create_webhook_app.start_both_bots_route` | `create_webhook_app` |
| 5544 | `create_webhook_app.ban_user_route` | `create_webhook_app` |
| 5591 | `create_webhook_app.unban_user_route` | `create_webhook_app` |
| 5615 | `create_webhook_app.delete_user_route` | `create_webhook_app` |
| 5668 | `create_webhook_app.revoke_keys_route` | `create_webhook_app` |
| 5714 | `create_webhook_app.add_host_route` | `create_webhook_app` |
| 5769 | `create_webhook_app.delete_host_route` | `create_webhook_app` |
| 5776 | `create_webhook_app.add_plan_route` | `create_webhook_app` |
| 5827 | `create_webhook_app.delete_plan_route` | `create_webhook_app` |
| 5834 | `create_webhook_app.toggle_plan_route` | `create_webhook_app` |
| 5851 | `create_webhook_app.update_plan_route` | `create_webhook_app` |
| 5909 | `create_webhook_app._normalize_package_pool` | `create_webhook_app` |
| 5915 | `create_webhook_app.admin_get_traffic_packages_for_plan_json` | `create_webhook_app` |
| 5934 | `create_webhook_app.add_traffic_package_route` | `create_webhook_app` |
| 5958 | `create_webhook_app.update_traffic_package_route` | `create_webhook_app` |
| 5985 | `create_webhook_app.toggle_traffic_package_route` | `create_webhook_app` |
| 5997 | `create_webhook_app.delete_traffic_package_route` | `create_webhook_app` |
| 6004 | `create_webhook_app._get_client_ip` | `create_webhook_app` |
| 6014 | `create_webhook_app._is_ip_allowed` | `create_webhook_app` |
| 6020 | `create_webhook_app._debug_endpoints_allowed` | `create_webhook_app` |
| 6026 | `create_webhook_app._http_json` | `create_webhook_app` |
| 6038 | `create_webhook_app._yookassa_get_payment` | `create_webhook_app` |
| 6053 | `create_webhook_app._cryptobot_verify_signature` | `create_webhook_app` |
| 6068 | `create_webhook_app._cryptobot_get_invoice` | `create_webhook_app` |
| 6090 | `create_webhook_app._require_ton_webhook_secret` | `create_webhook_app` |
| 6106 | `create_webhook_app.yookassa_webhook_handler` | `create_webhook_app` |
| 6217 | `create_webhook_app.test_webhook` | `create_webhook_app` |
| 6227 | `create_webhook_app.debug_all_requests` | `create_webhook_app` |
| 6252 | `create_webhook_app.yoomoney_webhook_handler` | `create_webhook_app` |
| 6360 | `create_webhook_app.platega_webhook_handler` | `create_webhook_app` |
| 6478 | `create_webhook_app.rollypay_webhook_handler` | `create_webhook_app` |
| 6629 | `create_webhook_app.cryptobot_webhook_handler` | `create_webhook_app` |
| 6778 | `create_webhook_app.heleket_webhook_handler` | `create_webhook_app` |
| 6866 | `create_webhook_app.ton_webhook_handler` | `create_webhook_app` |
| 6926 | `create_webhook_app._ym_get_redirect_uri` | `create_webhook_app` |
| 6938 | `create_webhook_app.yoomoney_connect_route` | `create_webhook_app` |
| 6960 | `create_webhook_app.yoomoney_callback_route` | `create_webhook_app` |
| 7007 | `create_webhook_app.yoomoney_check_route` | `create_webhook_app` |
| 7053 | `create_webhook_app.get_button_configs_api` | `create_webhook_app` |
| 7066 | `create_webhook_app.create_button_config_api` | `create_webhook_app` |
| 7098 | `create_webhook_app.update_button_config_api` | `create_webhook_app` |
| 7130 | `create_webhook_app.delete_button_config_api` | `create_webhook_app` |
| 7145 | `create_webhook_app.reorder_button_configs_api` | `create_webhook_app` |
| 7169 | `create_webhook_app._franchise_db_connect` | `create_webhook_app` |
| 7174 | `create_webhook_app._franchise_totals` | `create_webhook_app` |
| 7234 | `create_webhook_app._franchise_list_bots` | `create_webhook_app` |
| 7293 | `create_webhook_app._franchise_get_bot` | `create_webhook_app` |
| 7309 | `create_webhook_app._franchise_bot_stats` | `create_webhook_app` |
| 7362 | `create_webhook_app.franchise_page` | `create_webhook_app` |
| 7371 | `create_webhook_app.franchise_bot_page` | `create_webhook_app` |
| 7437 | `create_webhook_app.franchise_toggle_bot_route` | `create_webhook_app` |
| 7466 | `create_webhook_app.franchise_delete_bot_route` | `create_webhook_app` |
| 7493 | `create_webhook_app.franchise_withdraw_status_route` | `create_webhook_app` |
| 7516 | `create_webhook_app.button_constructor_page` | `create_webhook_app` |

<a id="src-shop_bot-webhook_server-apply_app_fixpy"></a>

### `src/shop_bot/webhook_server/apply_app_fix.py`

Ручной regex-патч списков настроек в app.py. Не вызывается из runtime.

**Импорт-путь:** `shop_bot.webhook_server.apply_app_fix`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 13 | `normalize_list(block, must_have)` | — | из прод-кода **не вызывается** |

## Telegram Mini App

<a id="src-shop_bot-webapp-__init__py"></a>

### `src/shop_bot/webapp/__init__.py`

Маркер пакета Mini App. Пустой.

**Импорт-путь:** `shop_bot.webapp`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  
**Тесты:** 22 файл(ов)

Функций нет.

<a id="src-shop_bot-webapp-handlerspy"></a>

### `src/shop_bot/webapp/handlers.py`

FastAPI Telegram Mini App: auth, ключи, оплата, тикеты, подарки/реф-лендинги. Отдельный контейнер.

**Импорт-путь:** `shop_bot.webapp.handlers`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  
**Тесты:** 23 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 2014 | `SupportStatusRequest` | `BaseModel` | — |
| 2019 | `SupportTicketCreateRequest` | `BaseModel` | — |
| 2025 | `SupportMessageSendRequest` | `BaseModel` | — |
| 2032 | `SupportTicketRequest` | `BaseModel` | — |
| 2038 | `PaymentMethodsRequest` | `BaseModel` | — |
| 2043 | `TokenRequest` | `BaseModel` | — |
| 2046 | `TelegramDirectAuthRequest` | `BaseModel` | Must carry signed Telegram WebApp initData — never a bare user_id. |
| 2050 | `EmailAuthRequest` | `BaseModel` | — |
| 2054 | `EmailVerifyRequest` | `BaseModel` | — |
| 2058 | `EmailResendRequest` | `BaseModel` | — |
| 2061 | `PasswordResetRequest` | `BaseModel` | — |
| 2064 | `PasswordResetCheckRequest` | `BaseModel` | — |
| 2068 | `PasswordResetVerifyRequest` | `BaseModel` | — |
| 2092 | `SyncTgRequest` | `BaseModel` | — |
| 2097 | `DeviceTiersRequest` | `BaseModel` | — |
| 2100 | `CreatePaymentRequest` | `BaseModel` | — |
| 2113 | `CreateTopUpPaymentRequest` | `BaseModel` | — |
| 2120 | `CreateLteTopUpPaymentRequest` | `BaseModel` | — |
| 2128 | `ApplyPromoRequest` | `BaseModel` | — |
| 2136 | `RenameKeyRequest` | `BaseModel` | — |
| 2142 | `DeleteAllDevicesRequest` | `BaseModel` | — |
| 2148 | `SearchKeysRequest` | `BaseModel` | — |
| 4085 | `CheckPaymentRequest` | `BaseModel` | — |
| 4143 | `VerifyPlategaPaymentRequest` | `BaseModel` | — |
| 4367 | `KeyActionRequest` | `BaseModel` | — |
| 4374 | `DeleteDeviceRequest` | `BaseModel` | — |
| 4382 | `CommentRequest` | `BaseModel` | — |
| 4389 | `GiftActivateRequest` | `BaseModel` | — |
| 4713 | `PendingActionCompleteRequest` | `BaseModel` | — |

**Функции верхнего уровня и методы классов:** 144

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 68 | `_create_payload_pending_or_error(payment_id, user_id, amount, meta)` | Создать pending; если слот промокода уже занят — вернуть ошибку для API. | из прод-кода **не вызывается** |
| 110 | `_email_auth_rate_limit_response()` | внутренний хелпер | из прод-кода **не вызывается** |
| 120 | `_email_auth_rate_limited(email)` | True, если по этому email уже исчерпан EMAIL_AUTH_PER_EMAIL_LIMIT за окно. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 138 | `_reject_if_email_auth_rate_limited(email)` | внутренний хелпер | из прод-кода **не вызывается** |
| 144 | `_resolve_user_from_request_token(data, request)` | внутренний хелпер | из прод-кода **не вызывается** |
| 167 | `_resolve_authenticated_user(data, request)` | Определить текущего пользователя ИСКЛЮЧИТЕЛЬНО по доверенным источникам: | из прод-кода **не вызывается** |
| 191 | `_unauthorized(detail)` | внутренний хелпер | из прод-кода **не вызывается** |
| 195 | `_require_authenticated_user(request, data, token, init_data)` | Resolve caller from auth_token / Bearer / signed init_data only (CWE-862/639). | из прод-кода **не вызывается** |
| 218 | `_ref_setting_is_true(key, default)` | внутренний хелпер | из прод-кода **не вызывается** |
| 223 | `_ref_method_type_enabled(method_type)` | внутренний хелпер | из прод-кода **не вызывается** |
| 235 | `get_transaction_comment(user_data, action_type, value, host_name)` | Короткое человекочитаемое описание платежа — для поля description в | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 264 | `calculate_webapp_price(price, user_id)` | — | из прод-кода **не вызывается** |
| 292 | `async notify_admin_of_purchase(bot, metadata)` | — | из прод-кода **не вызывается** |
| 296 | `async process_successful_payment(bot, metadata)` | — | из прод-кода **не вызывается** |
| 300 | `async _send_telegram_message(user_id, text, reply_markup, photo)` | внутренний хелпер | из прод-кода **не вызывается** |
| 316 | `async _send_invoice_stars(user_id, title, description, payload, amount)` | внутренний хелпер | из прод-кода **не вызывается** |
| 357 | `_platega_api()` | внутренний хелпер | из прод-кода **не вызывается** |
| 365 | `_store_platega_transaction_id(payment_id, user_id, amount, meta, txid)` | внутренний хелпер | из прод-кода **не вызывается** |
| 376 | `_rollypay_is_enabled()` | внутренний хелпер | из прод-кода **не вызывается** |
| 383 | `_rollypay_api()` | внутренний хелпер | из прод-кода **не вызывается** |
| 390 | `_store_rollypay_payment_id(payment_id, user_id, amount, meta, provider_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 401 | `async _fulfill_webapp_paid_order(metadata)` | внутренний хелпер | из прод-кода **не вызывается** |
| 423 | `_build_yoomoney_link(receiver, amount_rub, label, description)` | внутренний хелпер | из прод-кода **не вызывается** |
| 442 | `async _webapp_no_cache_middleware(request, call_next)` | внутренний хелпер | из прод-кода **не вызывается** |
| 460 | `_hidden_not_found()` | Как несуществующий URL: стандартный FastAPI 404, без Unauthorized. | из прод-кода **не вызывается** |
| 467 | `async _block_ticket_files_dir(rest)` | Каталог ticket_files не является static и не должен открываться по URL. | из прод-кода **не вызывается** |
| 474 | `async api_referral_payout_methods_list(request)` | — | из прод-кода **не вызывается** |
| 499 | `async api_referral_payout_methods_add(request)` | — | из прод-кода **не вызывается** |
| 527 | `async api_referral_available_method_types(request)` | — | из прод-кода **не вызывается** |
| 557 | `async api_referral_payout_methods_delete(request)` | — | из прод-кода **не вызывается** |
| 579 | `async api_key_auto_renew(request)` | — | из прод-кода **не вызывается** |
| 604 | `async api_referral_request_withdraw(request)` | — | из прод-кода **не вызывается** |
| 653 | `async api_referral_list_withdrawals(request)` | — | из прод-кода **не вызывается** |
| 687 | `_format_remaining_details(remaining)` | внутренний хелпер | из прод-кода **не вызывается** |
| 711 | `_format_bytes(size)` | внутренний хелпер | из прод-кода **не вызывается** |
| 728 | `_process_template_placeholders(html, user_id, webapp_settings, context_data)` | внутренний хелпер | из прод-кода **не вызывается** |
| 778 | `_format_bytes_gb(num_bytes)` | Тот же формат ГБ, что в карточке ключа бота. | из прод-кода **не вызывается** |
| 788 | `_format_gb_amount(size_gb)` | внутренний хелпер | из прод-кода **не вызывается** |
| 796 | `_is_key_without_billing_plan(key_data)` | Триал/подарок: биллингового тарифа нет — докупка LTE недоступна (как в боте). | из прод-кода **не вызывается** |
| 818 | `_resolve_plan_id_for_key(key_data)` | plan_id из description JSON, иначе первый активный тариф хоста (как в боте). | из прод-кода **не вызывается** |
| 845 | `_lte_card_state(key)` | Условия и цифры LTE-пула — те же, что в карточке ключа бота. | из прод-кода **не вызывается**; тесты: 4 сайт(ов) |
| 898 | `_owned_lte_key_and_plan(user_id, key_id)` | Ключ принадлежит user_id и доступен для LTE-докупки. Иначе (None, None). | из прод-кода **не вызывается** |
| 912 | `_process_key_data(key)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1044 | `_get_key_html(key)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1091 | `_get_profile_card_html(user, referral_count, keys_count, referral_earned)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1222 | `_get_key_card_html(key, badge_html, extra_content_html)` | Render the full key-card block (used for regular keys and, with an extra | из прод-кода **не вызывается** |
| 1353 | `_key_created_sort_tuple(key)` | Sort key for newest-purchased-first: created_at desc, then key_id desc. | из прод-кода **не вызывается** |
| 1367 | `_sort_keys_newest_first(keys)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 1371 | `_get_profile_keys_html(keys)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 4 сайт(ов) |
| 1380 | `_get_setup_keys_html(keys)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1466 | `_get_renew_keys_html(keys, user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1514 | `_get_no_key_html()` | внутренний хелпер | из прод-кода **не вызывается** |
| 1529 | `_duration_label(months, duration_days)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1551 | `_days_from_plan(plan)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1565 | `_billing_months_for_plan(plan)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1569 | `_build_plans_grid_html(host_name, user_id, container_id, display_style)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1640 | `_get_servers_and_plans_html(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1686 | `_render_banned_page(webapp_settings)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1768 | `async _render_main_page(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1970 | `async index(request, user_id, token)` | — | из прод-кода **не вызывается** |
| 2079 | `_hash_password_reset_code(email, code)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 2083 | `_password_reset_code_matches(email, code, stored_hash)` | внутренний хелпер | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 2156 | `validate_telegram_data(init_data, bot_token, max_age_seconds)` | Verify Telegram WebApp initData HMAC and freshness (auth_date). | из прод-кода **не вызывается** |
| 2225 | `_issue_persistent_token_for_telegram_user(user_id)` | Shared token issue/lookup used by /api/auth/token and /api/auth/telegram-direct. | из прод-кода **не вызывается** |
| 2244 | `async api_request_auth_token(request)` | — | из прод-кода **не вызывается** |
| 2259 | `async api_check_auth_token(token, request)` | — | из прод-кода **не вызывается** |
| 2301 | `async api_create_token(request, req)` | Generate or retrieve a persistent login token using verified Telegram data. | из прод-кода **не вызывается** |
| 2321 | `async api_telegram_direct_auth(request, req)` | Authenticate inside Telegram WebApp using signed initData only. | из прод-кода **не вызывается** |
| 2356 | `_validate_password(password)` | Проверка пароля при регистрации / сбросе / смене. | из прод-кода **не вызывается**; тесты: 5 сайт(ов) |
| 2381 | `async _issue_email_verification_code(user_id, email)` | Сгенерировать, сохранить и отправить новый код подтверждения email. | из прод-кода **не вызывается** |
| 2415 | `async api_email_register(request, req)` | — | из прод-кода **не вызывается** |
| 2444 | `async api_email_verify(request, req)` | — | из прод-кода **не вызывается** |
| 2465 | `async api_email_resend(request, req)` | — | из прод-кода **не вызывается** |
| 2492 | `async api_email_login(request, req)` | — | из прод-кода **не вызывается** |
| 2513 | `async api_email_reset_request(request, req)` | — | из прод-кода **не вызывается** |
| 2550 | `async api_email_reset_check(request, req)` | — | из прод-кода **не вызывается** |
| 2570 | `async api_email_reset_verify(request, req)` | — | из прод-кода **не вызывается** |
| 2607 | `async api_user_profile_info(request)` | — | из прод-кода **не вызывается** |
| 2627 | `async api_user_profile_change_password(request)` | — | из прод-кода **не вызывается** |
| 2655 | `async api_user_profile_change_email_request(request)` | — | из прод-кода **не вызывается** |
| 2693 | `async api_user_profile_change_email_resend(request)` | — | из прод-кода **не вызывается** |
| 2729 | `async api_user_profile_change_email_verify(request)` | — | из прод-кода **не вызывается** |
| 2753 | `async api_user_profile_change_email_cancel(request)` | — | из прод-кода **не вызывается** |
| 2769 | `async api_sync_tg(request, req)` | — | из прод-кода **не вызывается** |
| 2797 | `async api_device_tiers(req)` | — | из прод-кода **не вызывается** |
| 2816 | `async api_get_payment_methods(req, request)` | — | из прод-кода **не вызывается** |
| 2876 | `async api_create_payment(req, request)` | — | из прод-кода **не вызывается** |
| 3335 | `_rollback_internal_payment(payment_id, user_id, amount, payment_method, plan_id, reason)` | Идемпотентный откат списания Balance/ReferralBalance + лог PAYMENT_ROLLBACK. | из прод-кода **не вызывается** |
| 3374 | `_platega_method_code_from_settings()` | внутренний хелпер | из прод-кода **не вызывается** |
| 3390 | `async api_create_topup_payment(req, request)` | Create a balance top-up payment (action=top_up), mirroring the bot TopUpProcess flow. | из прод-кода **не вызывается** |
| 3697 | `_lte_topup_metadata(user_id, key_id, package, payment_method, payment_id, host_name)` | Метаданные те же, что бот кладёт в pending для process_successful_payment. | из прод-кода **не вызывается** |
| 3714 | `async api_lte_packages(request, key_id, token)` | Пакеты докупки LTE для ключа владельца. Цена/размер только с сервера. | из прод-кода **не вызывается** |
| 3749 | `async api_create_lte_topup_payment(req, request)` | Оплата докупки LTE: те же методы, что в боте; цена берётся из пакета в БД. | из прод-кода **не вызывается** |
| 4038 | `async api_apply_promo(req, request)` | Проверить промокод и посчитать цену со скидкой. | из прод-кода **не вызывается** |
| 4091 | `_check_payment_unpaid()` | Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена. | из прод-кода **не вызывается** |
| 4101 | `async api_check_payment(req, request)` | — | из прод-кода **не вызывается** |
| 4148 | `_platega_verify_error(message, status_code)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4153 | `async api_verify_platega_payment(payment_id, req, request)` | Сверить pending Platega-заказ с GET /transaction/{id} и выдать ключ тем же путём, что webhook. | из прод-кода **не вызывается** |
| 4397 | `async api_user_referral_info(request)` | — | из прод-кода **не вызывается** |
| 4432 | `_gift_link_row_html(label, link, share_text)` | Одна строка со ссылкой активации подарка: текст ссылки + копировать + поделиться. | из прод-кода **не вызывается** |
| 4451 | `_get_gift_action_block_html(gift_code, webapp_link, telegram_link)` | Общий блок для неактивированного подарка: обе ссылки активации | из прод-кода **не вызывается** |
| 4481 | `_get_gift_fallback_card_html(g, badge_html, action_block_html)` | Карточка подарка на случай, если связанный VPN-ключ не найден (например, | из прод-кода **не вызывается** |
| 4506 | `async api_user_gifts(request)` | — | из прод-кода **не вызывается** |
| 4568 | `_activate_gift_for_user(user_id, gift_code)` | Активировать подарок `gift_code` для пользователя `user_id`. | из прод-кода **не вызывается** |
| 4641 | `async api_gift_activate(req, request)` | — | из прод-кода **не вызывается** |
| 4673 | `_apply_pending_referral(user_id, referrer_id)` | Привязать пользователя к рефереру и, если применимо, выплатить | из прод-кода **не вызывается** |
| 4719 | `_pending_action_public_info(pending)` | Собрать безопасный (без лишних деталей) ответ для UI по pending action — | из прод-кода **не вызывается** |
| 4763 | `async api_pending_action_info(pending_token)` | — | из прод-кода **не вызывается** |
| 4772 | `async api_pending_action_complete(req, request)` | Единая точка завершения pending action ПОСЛЕ успешной авторизации. | из прод-кода **не вызывается** |
| 4865 | `async api_key_devices(req, request)` | — | из прод-кода **не вызывается** |
| 4896 | `async api_key_device_delete(req, request)` | — | из прод-кода **не вызывается** |
| 4928 | `async api_key_comment(req, request)` | — | из прод-кода **не вызывается** |
| 4949 | `_support_rate_response()` | внутренний хелпер | из прод-кода **не вызывается** |
| 4956 | `_support_user_rate_limited(user_id, action, limit, window)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4969 | `_support_too_fast(user_id, min_interval)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4982 | `_clip_support_text(value, max_len)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4986 | `_tickets_created_today_count(tickets)` | внутренний хелпер | из прод-кода **не вызывается** |
| 4996 | `_public_ticket_row(ticket)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5005 | `_public_ticket_messages(messages)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5016 | `_ticket_owned_by(ticket, user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5025 | `async _notify_webapp_support(user_id, ticket, title, body)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5081 | `async api_support_status(req, request)` | — | из прод-кода **не вызывается** |
| 5117 | `async api_support_create(req, request)` | — | из прод-кода **не вызывается** |
| 5165 | `async api_support_send(req, request)` | — | из прод-кода **не вызывается** |
| 5210 | `async api_support_ticket(req, request)` | — | из прод-кода **не вызывается** |
| 5239 | `async api_support_close(req, request)` | — | из прод-кода **не вызывается** |
| 5272 | `async api_support_ticket_file(message_id, request, token)` | Вложение только владельцу. Без сессии и при чужом id — тот же 404, что у несуществующего URL. | из прод-кода **не вызывается** |
| 5316 | `async api_support_upload(request, file, ticket_id, token, caption, init_data)` | — | из прод-кода **не вызывается** |
| 5375 | `async api_user_status(request, token)` | — | из прод-кода **не вызывается** |
| 5395 | `async api_key_rename(req, request)` | — | из прод-кода **не вызывается** |
| 5420 | `async api_key_devices_delete_all(req, request)` | — | из прод-кода **не вызывается** |
| 5464 | `async api_user_transactions(request, page, per_page, token)` | — | из прод-кода **не вызывается** |
| 5518 | `async api_keys_search(req, request)` | — | из прод-кода **не вызывается** |
| 5544 | `_html_esc(value)` | Экранировать значение для вставки в HTML-текст или атрибут (CWE-79). | из прод-кода **не вызывается** |
| 5560 | `_public_fallback_response(content, status_code)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5568 | `_parse_public_referrer_id(referrer_id)` | Только положительный int. Невалидный path не должен попадать в HTML/URL. | из прод-кода **не вызывается** |
| 5579 | `_safe_public_gift_code(gift_code)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5586 | `_telegram_bot_deeplink(bot_username, start_payload)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5595 | `_html_telegram_btn(deeplink, label)` | внутренний хелпер | из прод-кода **не вызывается** |
| 5601 | `_referral_fallback_html(project_name, logo_url, deeplink, error_note)` | Резервная страница рефссылки (реферер не найден/бот не настроен) — | из прод-кода **не вызывается** |
| 5634 | `async web_referral_page(referrer_id, request)` | Публичная реферальная ссылка. | из прод-кода **не вызывается** |
| 5679 | `_gift_fallback_html(project_name, logo_url, title, desc, action_html)` | Резервная страница подарка (не найден/уже активирован) — как и раньше, | из прод-кода **не вызывается** |
| 5706 | `async web_gift_page(gift_code, request)` | Публичная ссылка активации подарка. | из прод-кода **не вызывается** |
| 5773 | `async dynamic_route(request, path_param)` | — | из прод-кода **не вызывается** |

## Support-бот

<a id="src-shop_bot-support_bot-__init__py"></a>

### `src/shop_bot/support_bot/__init__.py`

Маркер пакета support-бота. Пустой.

**Импорт-путь:** `shop_bot.support_bot`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  
**Тесты:** 3 файл(ов)

Функций нет.

<a id="src-shop_bot-support_bot-handlerspy"></a>

### `src/shop_bot/support_bot/handlers.py`

Тикеты: DM пользователя ↔ форум-топики админов, модерация, бан, заметки.

**Импорт-путь:** `shop_bot.support_bot.handlers`  
**Кто импортирует (прод):** `src/shop_bot/support_bot_controller.py`  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 32 | `SupportDialog` | `StatesGroup` | — |
| 38 | `AdminDialog` | `StatesGroup` | — |

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 42 | `get_support_router()` | — | `src/shop_bot/support_bot_controller.py::SupportBotController.start` |

**Вложенные функции** (32), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 45 | `get_support_router._user_main_reply_kb` | `get_support_router` |
| 54 | `get_support_router._is_user_banned` | `get_support_router` |
| 63 | `get_support_router._get_latest_open_ticket` | `get_support_router` |
| 73 | `get_support_router._admin_actions_kb` | `get_support_router` |
| 116 | `get_support_router._is_admin` | `get_support_router` |
| 127 | `get_support_router.start_handler` | `get_support_router` |
| 165 | `get_support_router.support_new_ticket_handler` | `get_support_router` |
| 190 | `get_support_router.support_subject_received` | `get_support_router` |
| 205 | `get_support_router._save_ticket_media` | `get_support_router` |
| 212 | `get_support_router.support_message_received` | `get_support_router` |
| 322 | `get_support_router.support_my_tickets_handler` | `get_support_router` |
| 339 | `get_support_router.support_view_ticket_handler` | `get_support_router` |
| 372 | `get_support_router.support_reply_prompt_handler` | `get_support_router` |
| 397 | `get_support_router.support_reply_received` | `get_support_router` |
| 497 | `get_support_router.forum_thread_message_handler` | `get_support_router` |
| 567 | `get_support_router.support_close_ticket_handler` | `get_support_router` |
| 613 | `get_support_router.admin_close_ticket` | `get_support_router` |
| 652 | `get_support_router.admin_reopen_ticket` | `get_support_router` |
| 691 | `get_support_router.admin_delete_ticket` | `get_support_router` |
| 746 | `get_support_router.admin_toggle_star` | `get_support_router` |
| 818 | `get_support_router.admin_show_user` | `get_support_router` |
| 845 | `get_support_router._support_contact_markup` | `get_support_router` |
| 869 | `get_support_router._notify_user_about_ban` | `get_support_router` |
| 880 | `get_support_router.admin_ban_user` | `get_support_router` |
| 911 | `get_support_router.admin_unban_user` | `get_support_router` |
| 945 | `get_support_router.admin_note_prompt` | `get_support_router` |
| 962 | `get_support_router.admin_list_notes` | `get_support_router` |
| 987 | `get_support_router.admin_note_receive` | `get_support_router` |
| 1008 | `get_support_router.start_text_button` | `get_support_router` |
| 1019 | `get_support_router.new_ticket_text_button` | `get_support_router` |
| 1030 | `get_support_router.my_tickets_text_button` | `get_support_router` |
| 1044 | `get_support_router.relay_user_message_to_forum` | `get_support_router` |

<a id="src-shop_bot-support_bot-idle_closepy"></a>

### `src/shop_bot/support_bot/idle_close.py`

Автозакрытие тикетов после N дней молчания пользователя с follow-up в форум.

**Импорт-путь:** `shop_bot.support_bot.idle_close`  
**Кто импортирует (прод):** `src/shop_bot/data_manager/scheduler.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 5

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 18 | `_ru_days_word(n)` | внутренний хелпер | из прод-кода **не вызывается** |
| 30 | `_forum_wait(loop, coro, timeout)` | внутренний хелпер | из прод-кода **не вызывается** |
| 35 | `run_idle_close_followup(tickets, days)` | Темы форума и короткое уведомление пользователю. Не из HTTP-потока. | из прод-кода **не вызывается** |
| 123 | `maybe_auto_close_idle_tickets(now, sync_followup)` | Закрывает пачку простаивающих тикетов. Telegram — в фоне, SQL сразу. | `src/shop_bot/data_manager/scheduler.py::_maybe_auto_close_idle_tickets`; тесты: 2 сайт(ов) |
| 154 | `_run_followup_safe(tickets, days)` | внутренний хелпер | из прод-кода **не вызывается** |

<a id="src-shop_bot-support_bot-ticket_mediapy"></a>

### `src/shop_bot/support_bot/ticket_media.py`

Хранение вложений тикетов: квоты, magic-bytes, path jail, TTL 7 дней.

**Импорт-путь:** `shop_bot.support_bot.ticket_media`  
**Кто импортирует (прод):** `src/shop_bot/data_manager/database.py`, `src/shop_bot/data_manager/scheduler.py`, `src/shop_bot/support_bot/handlers.py`, `src/shop_bot/webapp/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 7 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 134 | `_CappedSeekBuffer` | `io.BytesIO` | BytesIO с seek (его зовёт aiogram) и потолком, чтобы не держать 20 МБ в RAM. |

**Функции верхнего уровня и методы классов:** 27

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 41 | `detect_image_kind_bytes(head)` | Расширение и MIME по сигнатуре. None — не jpeg/png/webp/pdf. | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 56 | `detect_image_kind(path)` | — | `src/shop_bot/webapp/handlers.py::api_support_ticket_file`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_file`; тесты: 1 сайт(ов) |
| 65 | `media_kind_from_stored(media)` | image \| pdf \| file по имени на диске. Сырой путь наружу не отдаём. | из прод-кода **не вызывается** |
| 79 | `public_support_message(m)` | Поля сообщения для панели/JSON без пути ticket_files. | `src/shop_bot/webapp/handlers.py::_public_ticket_messages`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_page`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_messages_api`; тесты: 1 сайт(ов) |
| 93 | `positive_file_size(file_size)` | Положительный размер в байтах или None, если Telegram его не дал. | из прод-кода **не вызывается** |
| 106 | `async resolve_telegram_file_size(bot, file_id, declared_size)` | Размер до download. Всегда getFile, если бот его умеет. | из прод-кода **не вызывается** |
| 137 | `_CappedSeekBuffer.__init__(self, max_bytes)` | внутренний хелпер | из прод-кода **не вызывается** |
| 142 | `_CappedSeekBuffer.write(self, b)` | — | из прод-кода **не вызывается** |
| 154 | `async download_ticket_media_capped(bot, source, part_path, max_bytes)` | Качаем в буфер с seek и потолком 10 МБ, затем на диск. | из прод-кода **не вызывается** |
| 196 | `declared_size_over_limit(file_size, max_bytes)` | True, если Telegram уже сообщил размер больше лимита. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 213 | `ticket_folder_usage(folder)` | Число финальных файлов и их суммарный размер. ``*.part`` не считаем. | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 237 | `quota_blocks_new_file(folder, incoming_bytes, max_files, max_total_bytes)` | True, если ещё одно вложение превысит квоту тикета (10 файлов / 30 МБ). | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 264 | `jailed_ticket_folder(ticket_id, root)` | Каталог вложений тикета строго внутри media root, иначе None. | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 283 | `closed_ttl_days()` | — | из прод-кода **не вызывается** |
| 292 | `parse_ticket_updated_at(value)` | — | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 308 | `closed_ticket_media_expired(ticket, now, ttl_days)` | True, если тикет закрыт дольше TTL — файлы пора снять. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 325 | `ticket_media_on_disk(root)` | True, если в ticket_files есть хоть одна запись. Без SQL и без полного обхода. | из прод-кода **не вызывается**; тесты: 2 сайт(ов) |
| 340 | `expire_ticket_media_if_closed_ttl(ticket_id, now)` | Если тикет закрыт дольше TTL — удаляет файлы и обнуляет media. True = истекло. | `src/shop_bot/webapp/handlers.py::api_support_ticket_file`, `src/shop_bot/webhook_server/app.py::create_webhook_app.support_ticket_file` |
| 352 | `purge_expired_closed_ticket_media(now, ttl_days)` | Снимает каталоги закрытых тикетов старше TTL и осиротевшие папки. | `src/shop_bot/data_manager/scheduler.py::_maybe_purge_closed_ticket_media`; тесты: 2 сайт(ов) |
| 421 | `maybe_purge_expired_closed_ticket_media()` | Не чаще раза в час. Нет файлов — сразу выход, таймер не заводим. | из прод-кода **не вызывается** |
| 437 | `delete_ticket_media_dir(ticket_id)` | Удаляет ``ticket_files/<ticket_id>/``. Не трогает соседние тикеты и корень. | `src/shop_bot/data_manager/database.py::_cleanup_ticket_media`; тесты: 1 сайт(ов) |
| 450 | `commit_ticket_image(part_path, dest_dir, stem)` | Размер + magic. Возвращает ``stem.ext`` или None; ``*.part`` удаляется при отказе. | из прод-кода **не вызывается**; тесты: 3 сайт(ов) |
| 487 | `remove_empty_ticket_folder(folder)` | Снимает пустой ``ticket_files/<id>/`` после неудачного save. | из прод-кода **не вызывается**; тесты: 1 сайт(ов) |
| 496 | `_unlink_quiet(*paths)` | внутренний хелпер | из прод-кода **не вызывается** |
| 505 | `document_may_be_ticket_media(doc)` | Документ можно скачать: картинка или PDF. Тип всё равно подтвердит magic. | из прод-кода **не вызывается** |
| 516 | `save_ticket_media_bytes(payload, ticket_id)` | Сохраняет вложение из WebApp (байты), те же jail/квота/magic, что у бота. | `src/shop_bot/webapp/handlers.py::api_support_upload`; тесты: 2 сайт(ов) |
| 566 | `async save_ticket_media(bot, message, ticket_id)` | Сохраняет изображение из сообщения. Контракт как у прежнего хелпера. | `src/shop_bot/support_bot/handlers.py::get_support_router._save_ticket_media`; тесты: 14 сайт(ов) |

## Франшиза (клоны ботов)

<a id="src-shop_bot-factory_bot-__init__py"></a>

### `src/shop_bot/factory_bot/__init__.py`

Маркер пакета франшизных клонов. Пустой.

**Импорт-путь:** `shop_bot.factory_bot`  
**Кто импортирует (прод):** `src/shop_bot/factory_bot/handlers.py`  
**Тесты:** 1 файл(ов)

Функций нет.

<a id="src-shop_bot-factory_bot-servicepy"></a>

### `src/shop_bot/factory_bot/service.py`

ManagedBotsService: start/stop/restart клонов на loop root-бота.

**Импорт-путь:** `shop_bot.factory_bot.service`  
**Кто импортирует (прод):** `src/shop_bot/bot_controller.py`  
**Тесты:** 1 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 20 | `ManagedBotsService` | — | — |

**Функции верхнего уровня и методы классов:** 9

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 21 | `ManagedBotsService.__init__(self, loop)` | внутренний хелпер | из прод-кода **не вызывается** |
| 28 | `ManagedBotsService.get_bot(self, bot_id)` | Возвращает экземпляр Bot для bot_id, если он запущен. | из прод-кода **не вызывается** |
| 32 | `ManagedBotsService._drop_bot_refs(self, bot_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 37 | `ManagedBotsService._has_running_task(self, bot_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 41 | `async ManagedBotsService.start_all(self)` | — | из прод-кода **не вызывается** |
| 52 | `async ManagedBotsService.start_bot(self, bot_id)` | — | из прод-кода **не вызывается** |
| 113 | `async ManagedBotsService.stop_bot(self, bot_id)` | Остановить один клон. Идемпотентно: повторный вызов безопасен. | из прод-кода **не вызывается** |
| 134 | `async ManagedBotsService.restart_bot(self, bot_id)` | Перезапуск клона (смена токена владельцем). | из прод-кода **не вызывается** |
| 139 | `async ManagedBotsService.stop_all(self)` | — | из прод-кода **не вызывается** |

**Вложенные функции** (1), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 83 | `ManagedBotsService.start_bot.runner` | `ManagedBotsService.start_bot` |

<a id="src-shop_bot-factory_bot-runtimepy"></a>

### `src/shop_bot/factory_bot/runtime.py`

Глобальный singleton ManagedBotsService (set_service/get_service).

**Импорт-путь:** `shop_bot.factory_bot.runtime`  
**Кто импортирует (прод):** `src/shop_bot/bot/admin_handlers.py`, `src/shop_bot/bot/handlers.py`, `src/shop_bot/bot_controller.py`, `src/shop_bot/factory_bot/handlers.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 2

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 7 | `set_service(service)` | — | `src/shop_bot/bot_controller.py::BotController.start` |
| 11 | `get_service()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router.admin_franchise_toggle`, `src/shop_bot/bot/handlers.py::get_user_router.franchise_receive_token`, `src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router.delete_bot_confirm`, `src/shop_bot/webhook_server/app.py::_run_on_root_bot_loop` |

<a id="src-shop_bot-factory_bot-middlewarepy"></a>

### `src/shop_bot/factory_bot/middleware.py`

FactoryStatsMiddleware и кэш franchise_enabled; пишет активность клона.

**Импорт-путь:** `shop_bot.factory_bot.middleware`  
**Кто импортирует (прод):** `src/shop_bot/bot_controller.py`, `src/shop_bot/factory_bot/service.py`, `src/shop_bot/webhook_server/app.py`  
**Тесты:** 1 файл(ов)

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 35 | `FactoryStatsMiddleware` | `BaseMiddleware` | Tracks basic stats (messages + unique users) per factory bot instance. |

**Функции верхнего уровня и методы классов:** 3

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 13 | `invalidate_franchise_enabled_cache()` | — | `src/shop_bot/webhook_server/app.py::_apply_franchise_runtime`; тесты: 1 сайт(ов) |
| 18 | `franchise_enabled_cached()` | Лёгкий кэш флага франшизы, чтобы middleware не ходила в SQL на каждое сообщение. | из прод-кода **не вызывается** |
| 37 | `async FactoryStatsMiddleware.__call__(self, handler, event, data)` | внутренний хелпер | из прод-кода **не вызывается** |

<a id="src-shop_bot-factory_bot-handlerspy"></a>

### `src/shop_bot/factory_bot/handlers.py`

Кабинет владельца клона: статистика и удаление своего бота.

**Импорт-путь:** `shop_bot.factory_bot.handlers`  
**Кто импортирует (прод):** `src/shop_bot/factory_bot/service.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 2

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 19 | `_parse_bot_id_from_callback(data, prefix)` | внутренний хелпер | из прод-кода **не вызывается** |
| 31 | `get_owner_cabinet_router()` | Кабинет владельца текущего клона: просмотр и удаление ЭТОГО бота. | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot`; тесты: 2 сайт(ов) |

**Вложенные функции** (3), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 36 | `get_owner_cabinet_router.cabinet` | `get_owner_cabinet_router` |
| 60 | `get_owner_cabinet_router.delete_self_ask` | `get_owner_cabinet_router` |
| 78 | `get_owner_cabinet_router.delete_bot_confirm` | `get_owner_cabinet_router` |

<a id="src-shop_bot-factory_bot-keyboardspy"></a>

### `src/shop_bot/factory_bot/keyboards.py`

Клавиатуры кабинета владельца клона.

**Импорт-путь:** `shop_bot.factory_bot.keyboards`  
**Кто импортирует (прод):** `src/shop_bot/factory_bot/handlers.py`  
**Тесты:** 1 файл(ов)

**Функции верхнего уровня и методы классов:** 2

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 4 | `cabinet_menu()` | — | `src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router.cabinet`; тесты: 1 сайт(ов) |
| 12 | `delete_bot_confirm(bot_id)` | — | `src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router.delete_self_ask`; тесты: 1 сайт(ов) |

## Плагины в `modules/`

<a id="modules-example_module-__init__py"></a>

### `modules/example_module/__init__.py`

Манифест шаблонного плагина (MODULE_META).

**Импорт-путь:** `modules.example_module`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="modules-example_module-bot_handlerspy"></a>

### `modules/example_module/bot_handlers.py`

Пример Telegram-router плагина.

**Импорт-путь:** `modules.example_module.bot_handlers`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 7 | `async example_ping(callback)` | — | из прод-кода **не вызывается** |

<a id="modules-example_module-panel_routespy"></a>

### `modules/example_module/panel_routes.py`

Пример Flask-blueprint плагина.

**Импорт-путь:** `modules.example_module.panel_routes`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 12 | `index()` | — | из прод-кода **не вызывается** |

<a id="modules-example_module-db_schemapy"></a>

### `modules/example_module/db_schema.py`

Пример SCHEMA_SQL.

**Импорт-путь:** `modules.example_module.db_schema`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="modules-example_module-db_cleanuppy"></a>

### `modules/example_module/db_cleanup.py`

Пример cleanup при удалении модуля.

**Импорт-путь:** `modules.example_module.db_cleanup`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 1 | `cleanup(db_conn)` | — | из прод-кода **не вызывается** |

<a id="modules-example_module-settings_schemapy"></a>

### `modules/example_module/settings_schema.py`

Пример SETTINGS.

**Импорт-путь:** `modules.example_module.settings_schema`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="modules-ramadan_tracker-__init__py"></a>

### `modules/ramadan_tracker/__init__.py`

Манифест плагина «Рамадан трекер».

**Импорт-путь:** `modules.ramadan_tracker`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="modules-ramadan_tracker-bot_handlerspy"></a>

### `modules/ramadan_tracker/bot_handlers.py`

Трекинг практик, баллы, призовой фонд, выплаты, тикеты вывода.

**Импорт-путь:** `modules.ramadan_tracker.bot_handlers`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Классы**

| Строка | Класс | Базы | Назначение |
|------:|-------|------|------------|
| 27 | `WithdrawalStates` | `StatesGroup` | — |

**Функции верхнего уровня и методы классов:** 85

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 33 | `async open_ramadan_tracker(message)` | — | из прод-кода **не вызывается** |
| 41 | `async open_ramadan_tracker_callback(callback)` | — | из прод-кода **не вызывается** |
| 49 | `async show_adhkar_menu(callback)` | — | из прод-кода **не вызывается** |
| 56 | `async show_adhkar_morning(callback)` | — | из прод-кода **не вызывается** |
| 63 | `async show_adhkar_evening(callback)` | — | из прод-кода **не вызывается** |
| 70 | `async mark_morning_read(callback)` | — | из прод-кода **не вызывается** |
| 79 | `async mark_morning_missed(callback)` | — | из прод-кода **не вызывается** |
| 88 | `async mark_evening_read(callback)` | — | из прод-кода **не вызывается** |
| 97 | `async mark_evening_missed(callback)` | — | из прод-кода **не вызывается** |
| 106 | `async show_salawat_menu(callback)` | — | из прод-кода **не вызывается** |
| 113 | `async add_salawat_one(callback)` | — | из прод-кода **не вызывается** |
| 122 | `async show_taraweeh_menu(callback)` | — | из прод-кода **не вызывается** |
| 129 | `async mark_taraweeh_mosque(callback)` | — | из прод-кода **не вызывается** |
| 138 | `async mark_taraweeh_home(callback)` | — | из прод-кода **не вызывается** |
| 147 | `async mark_taraweeh_missed(callback)` | — | из прод-кода **не вызывается** |
| 156 | `async show_today_stats(callback)` | — | из прод-кода **не вызывается** |
| 163 | `async show_total_stats(callback)` | — | из прод-кода **не вызывается** |
| 170 | `async show_top(callback)` | — | из прод-кода **не вызывается** |
| 178 | `async reward_top_user(callback)` | — | из прод-кода **не вызывается** |
| 191 | `async request_withdraw(callback)` | — | из прод-кода **не вызывается** |
| 229 | `async show_admin_menu(callback)` | — | из прод-кода **не вызывается** |
| 239 | `async show_admin_stats(callback)` | — | из прод-кода **не вызывается** |
| 249 | `async show_admin_top(callback)` | — | из прод-кода **не вызывается** |
| 259 | `async show_admin_withdrawals(callback)` | — | из прод-кода **не вызывается** |
| 269 | `async delete_withdrawal_request(callback)` | — | из прод-кода **не вызывается** |
| 292 | `async complete_withdrawal_request(callback, state)` | — | из прод-кода **не вызывается** |
| 321 | `async complete_without_proof(callback, state)` | — | из прод-кода **не вызывается** |
| 341 | `async handle_proof_photo(message, state)` | — | из прод-кода **не вызывается** |
| 370 | `_build_menu_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 393 | `_build_today_stats_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 407 | `_build_total_stats_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 419 | `_build_adhkar_menu_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 430 | `_build_adhkar_detail_text(user_id, field)` | внутренний хелпер | из прод-кода **не вызывается** |
| 438 | `_build_salawat_menu_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 450 | `_build_taraweeh_menu_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 461 | `_build_top_text(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 487 | `_build_admin_menu_text()` | внутренний хелпер | из прод-кода **не вызывается** |
| 491 | `_build_admin_stats_text()` | внутренний хелпер | из прод-кода **не вызывается** |
| 504 | `_build_admin_top_text()` | внутренний хелпер | из прод-кода **не вызывается** |
| 516 | `_build_admin_withdrawals_text()` | внутренний хелпер | из прод-кода **не вызывается** |
| 534 | `_build_admin_withdrawals_keyboard()` | внутренний хелпер | из прод-кода **не вызывается** |
| 562 | `_build_menu_keyboard(is_admin)` | внутренний хелпер | из прод-кода **не вызывается** |
| 577 | `_build_back_keyboard(is_admin)` | внутренний хелпер | из прод-кода **не вызывается** |
| 586 | `_build_top_keyboard(is_admin, can_withdraw)` | внутренний хелпер | из прод-кода **не вызывается** |
| 597 | `_build_adhkar_menu_keyboard()` | внутренний хелпер | из прод-кода **не вызывается** |
| 606 | `_build_adhkar_detail_keyboard(period)` | внутренний хелпер | из прод-кода **не вызывается** |
| 615 | `_build_salawat_menu_keyboard()` | внутренний хелпер | из прод-кода **не вызывается** |
| 623 | `_build_taraweeh_menu_keyboard()` | внутренний хелпер | из прод-кода **не вызывается** |
| 633 | `_build_admin_menu_keyboard()` | внутренний хелпер | из прод-кода **не вызывается** |
| 643 | `_build_admin_back_keyboard()` | внутренний хелпер | из прод-кода **не вызывается** |
| 650 | `_safe_edit(callback, text, keyboard)` | внутренний хелпер | из прод-кода **не вызывается** |
| 665 | `_today_str()` | внутренний хелпер | из прод-кода **не вызывается** |
| 669 | `_is_admin(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 673 | `_get_settings()` | внутренний хелпер | из прод-кода **не вызывается** |
| 690 | `_to_bool(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 698 | `_to_int(value, default)` | внутренний хелпер | из прод-кода **не вызывается** |
| 705 | `_to_float(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 712 | `_get_daily_row(user_id, day)` | внутренний хелпер | из прод-кода **не вызывается** |
| 734 | `_ensure_daily_row(user_id, day)` | внутренний хелпер | из прод-кода **не вызывается** |
| 744 | `_set_adhkar_status(user_id, field, status)` | внутренний хелпер | из прод-кода **не вызывается** |
| 765 | `_add_salawat(user_id, amount)` | внутренний хелпер | из прод-кода **не вызывается** |
| 783 | `_set_taraweeh(user_id, place)` | внутренний хелпер | из прод-кода **не вызывается** |
| 812 | `_get_total_stats(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 837 | `_get_global_stats()` | внутренний хелпер | из прод-кода **не вызывается** |
| 862 | `_get_top_rows(limit)` | внутренний хелпер | из прод-кода **не вызывается** |
| 888 | `_ensure_auto_payout(bot)` | внутренний хелпер | из прод-кода **не вызывается** |
| 906 | `_generate_rewards(manual, bot)` | внутренний хелпер | из прод-кода **не вызывается** |
| 944 | `_reward_already_given(period_end)` | внутренний хелпер | из прод-кода **не вызывается** |
| 954 | `_save_reward(period_end, user_id, amount)` | внутренний хелпер | из прод-кода **не вызывается** |
| 967 | `_period_generated(period_end)` | внутренний хелпер | из прод-кода **не вызывается** |
| 977 | `_save_reward_period(period_end, prize_fund, winners_count)` | внутренний хелпер | из прод-кода **не вызывается** |
| 991 | `_save_reward_users(period_end, rows, shares, amounts)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1006 | `_notify_winners(bot, period_end, winners, amounts)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1035 | `_get_reward_for_user(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1055 | `_get_withdrawal_requests(limit)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1074 | `_delete_withdrawal_request(withdrawal_id)` | Удаляет запрос на вывод по ID. | из прод-кода **не вызывается** |
| 1089 | `_mark_withdrawal_completed(withdrawal_id, proof_file_id)` | Отмечает запрос на вывод как выполненный с опциональным скриншотом. | из прод-кода **не вызывается** |
| 1104 | `_mark_withdraw_requested(user_id, period_end)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1118 | `_format_taraweeh_place(place)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1128 | `_format_adhkar_status(value)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1136 | `_parse_prize_shares(raw, winners_count)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1157 | `_allocate_prize_fund(prize_fund, shares)` | внутренний хелпер | из прод-кода **не вызывается** |
| 1170 | `_build_support_url()` | внутренний хелпер | из прод-кода **не вызывается** |
| 1181 | `async _create_withdrawal_ticket(user_id, username, full_name, amount, period_end, bot)` | Создает тикет в support-боте для запроса на вывод выигрыша. | из прод-кода **не вызывается** |
| 1291 | `_mask_user_id(user_id)` | внутренний хелпер | из прод-кода **не вызывается** |

**Вложенные функции** (1), обычно хендлеры/хелперы внутри фабрики роутера. Вызываются aiogram/Flask, а не прямым импортом.

| Строка | Имя | Где объявлена |
|------:|-----|----------------|
| 677 | `_get_settings._get` | `_get_settings` |

<a id="modules-ramadan_tracker-panel_routespy"></a>

### `modules/ramadan_tracker/panel_routes.py`

Страницы статистики и выплат в админке.

**Импорт-путь:** `modules.ramadan_tracker.panel_routes`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 7

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 15 | `_get_global_stats()` | внутренний хелпер | из прод-кода **не вызывается** |
| 40 | `_get_top_rows(limit)` | внутренний хелпер | из прод-кода **не вызывается** |
| 66 | `_get_withdrawal_requests(limit)` | внутренний хелпер | из прод-кода **не вызывается** |
| 113 | `index()` | — | из прод-кода **не вызывается** |
| 124 | `payouts()` | — | из прод-кода **не вызывается** |
| 133 | `payouts_delete()` | — | из прод-кода **не вызывается** |
| 147 | `payouts_complete()` | — | из прод-кода **не вызывается** |

<a id="modules-ramadan_tracker-db_schemapy"></a>

### `modules/ramadan_tracker/db_schema.py`

Таблицы ramadan_tracker_* и миграции колонок.

**Импорт-путь:** `modules.ramadan_tracker.db_schema`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 5 | `SCHEMA_SQL()` | Генерирует SQL схему и автоматически выполняет миграции. | из прод-кода **не вызывается** |

<a id="modules-ramadan_tracker-db_cleanuppy"></a>

### `modules/ramadan_tracker/db_cleanup.py`

DROP таблиц и настроек модуля.

**Импорт-путь:** `modules.ramadan_tracker.db_cleanup`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 1

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 1 | `cleanup(db_conn)` | — | из прод-кода **не вызывается** |

<a id="modules-ramadan_tracker-settings_schemapy"></a>

### `modules/ramadan_tracker/settings_schema.py`

prize_fund, winners_count, prize_shares.

**Импорт-путь:** `modules.ramadan_tracker.settings_schema`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

## Скрипты вне пакета

<a id="tools-inspect_dbpy"></a>

### `tools/inspect_db.py`

CLI просмотра SQLite (не runtime).

**Импорт-путь:** `tools/inspect_db.py`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="migrate_vlesspy"></a>

### `migrate_vless.py`

Одноразовая миграция VLESS-полей.

**Импорт-путь:** `migrate_vless.py`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="migrate_invalidate_auth_tokenspy"></a>

### `migrate_invalidate_auth_tokens.py`

Инвалидация всех webapp auth-токенов.

**Импорт-путь:** `migrate_invalidate_auth_tokens.py`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

Функций нет.

<a id="simple_collectpy"></a>

### `simple_collect.py`

Внешний скрипт сбора метрик, не часть shop_bot.

**Импорт-путь:** `simple_collect.py`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 2

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 13 | `collect_metrics_simple()` | Простой сбор метрик | из прод-кода **не вызывается** |
| 93 | `main()` | Основная функция | из прод-кода **не вызывается** |

<a id="simple_monitor_testpy"></a>

### `simple_monitor_test.py`

Ручной тест мониторинга, не часть shop_bot.

**Импорт-путь:** `simple_monitor_test.py`  
**Кто импортирует (прод):** никто (модуль не подключён к runtime или только маркер пакета).  

**Функции верхнего уровня и методы классов:** 5

| Строка | Сигнатура | Назначение | Где вызывается |
|------:|-----------|------------|----------------|
| 14 | `test_database()` | Проверяем базу данных | из прод-кода **не вызывается** |
| 90 | `test_settings()` | Проверяем настройки | из прод-кода **не вызывается** |
| 117 | `test_metrics_collection()` | Тестируем сбор метрик без psutil | из прод-кода **не вызывается** |
| 145 | `insert_test_metric()` | Вставляем тестовую метрику | из прод-кода **не вызывается** |
| 187 | `main()` | Основная функция | из прод-кода **не вызывается** |
