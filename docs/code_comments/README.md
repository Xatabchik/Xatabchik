# Каталог комментариев (код не менялся)

Каждый файл здесь соответствует одному `.py` исходнику. Текст — то, что по правилам проекта стояло бы в docstring / `#`, плюс разбор неочевидных блоков.

| Файл | Содержание |
|------|------------|
| [INVENTORY.md](INVENTORY.md) | Полный список функций и классов к комментированию |
| [CODE_COMMENTING_RULES.md](../../CODE_COMMENTING_RULES.md) | Стиль, снятый с существующих комментариев в репо |

**Docstring в коде: есть** — текст скопирован из исходника дословно.  
**Docstring в коде: нет** — предлагаемый комментарий написан по прочитанному телу функции, исходник не трогали.

Вложенные хендлеры (внутри `get_user_router` / `get_admin_router` / `create_webhook_app`) комментируются в файле того же исходника.

Крупные исходники разбиты на части; индексный файл указывает диапазоны.

| № | Исходник | Комментарии |
|--:|----------|-------------|
| 1 | `src/shop_bot/__main__.py` | [shop_bot__main__.md](shop_bot__main__.md) |
| 2 | `src/shop_bot/app.py` | [shop_bot_app.md](shop_bot_app.md) |
| 3 | `src/shop_bot/config.py` | [shop_bot_config.md](shop_bot_config.md) |
| 4 | `src/shop_bot/bot_controller.py` | [shop_bot_bot_controller.md](shop_bot_bot_controller.md) |
| 5 | `src/shop_bot/support_bot_controller.py` | [shop_bot_support_bot_controller.md](shop_bot_support_bot_controller.md) |
| 6 | `src/shop_bot/bot/middlewares.py` | [shop_bot_bot_middlewares.md](shop_bot_bot_middlewares.md) |
| 7 | `src/shop_bot/bot/callback_safety.py` | [shop_bot_bot_callback_safety.md](shop_bot_bot_callback_safety.md) |
| 8 | `src/shop_bot/bot/photo_helper.py` | [shop_bot_bot_photo_helper.md](shop_bot_bot_photo_helper.md) |
| 9 | `src/shop_bot/bot/image_bot.py` | [shop_bot_bot_image_bot.md](shop_bot_bot_image_bot.md) |
| 10 | `src/shop_bot/bot/keyboards.py` | [shop_bot_bot_keyboards.md](shop_bot_bot_keyboards.md) |
| 11 | `src/shop_bot/bot/handlers.py` | [shop_bot_bot_handlers.md](shop_bot_bot_handlers.md) |
| 12 | `src/shop_bot/bot/admin_handlers.py` | [shop_bot_bot_admin_handlers.md](shop_bot_bot_admin_handlers.md) |
| 13 | `src/shop_bot/data_manager/database.py` | [shop_bot_data_manager_database.md](shop_bot_data_manager_database.md) |
| 14 | `src/shop_bot/data_manager/remnawave_repository.py` | [shop_bot_data_manager_remnawave_repository.md](shop_bot_data_manager_remnawave_repository.md) |
| 15 | `src/shop_bot/data_manager/scheduler.py` | [shop_bot_data_manager_scheduler.md](shop_bot_data_manager_scheduler.md) |
| 16 | `src/shop_bot/data_manager/backup_manager.py` | [shop_bot_data_manager_backup_manager.md](shop_bot_data_manager_backup_manager.md) |
| 17 | `src/shop_bot/data_manager/captcha_utils.py` | [shop_bot_data_manager_captcha_utils.md](shop_bot_data_manager_captcha_utils.md) |
| 18 | `src/shop_bot/data_manager/resource_monitor.py` | [shop_bot_data_manager_resource_monitor.md](shop_bot_data_manager_resource_monitor.md) |
| 19 | `src/shop_bot/data_manager/speedtest_runner.py` | [shop_bot_data_manager_speedtest_runner.md](shop_bot_data_manager_speedtest_runner.md) |
| 20 | `src/shop_bot/modules/remnawave_api.py` | [shop_bot_modules_remnawave_api.md](shop_bot_modules_remnawave_api.md) |
| 21 | `src/shop_bot/modules/platega_api.py` | [shop_bot_modules_platega_api.md](shop_bot_modules_platega_api.md) |
| 22 | `src/shop_bot/modules/platega_fulfillment.py` | [shop_bot_modules_platega_fulfillment.md](shop_bot_modules_platega_fulfillment.md) |
| 23 | `src/shop_bot/modules/rollypay_api.py` | [shop_bot_modules_rollypay_api.md](shop_bot_modules_rollypay_api.md) |
| 24 | `src/shop_bot/modules/heleket_api.py` | [shop_bot_modules_heleket_api.md](shop_bot_modules_heleket_api.md) |
| 25 | `src/shop_bot/modules/cryptobot_api.py` | [shop_bot_modules_cryptobot_api.md](shop_bot_modules_cryptobot_api.md) |
| 26 | `src/shop_bot/modules/email_sender.py` | [shop_bot_modules_email_sender.md](shop_bot_modules_email_sender.md) |
| 27 | `src/shop_bot/modules/telegram_reachability.py` | [shop_bot_modules_telegram_reachability.md](shop_bot_modules_telegram_reachability.md) |
| 28 | `src/shop_bot/core/module_types.py` | [shop_bot_core_module_types.md](shop_bot_core_module_types.md) |
| 29 | `src/shop_bot/core/module_middleware.py` | [shop_bot_core_module_middleware.md](shop_bot_core_module_middleware.md) |
| 30 | `src/shop_bot/core/module_loader.py` | [shop_bot_core_module_loader.md](shop_bot_core_module_loader.md) |
| 31 | `src/shop_bot/webhook_server/app.py` | [shop_bot_webhook_server_app.md](shop_bot_webhook_server_app.md) |
| 32 | `src/shop_bot/webhook_server/apply_app_fix.py` | [shop_bot_webhook_server_apply_app_fix.md](shop_bot_webhook_server_apply_app_fix.md) |
| 33 | `src/shop_bot/webapp/handlers.py` | [shop_bot_webapp_handlers.md](shop_bot_webapp_handlers.md) |
| 34 | `src/shop_bot/support_bot/handlers.py` | [shop_bot_support_bot_handlers.md](shop_bot_support_bot_handlers.md) |
| 35 | `src/shop_bot/support_bot/idle_close.py` | [shop_bot_support_bot_idle_close.md](shop_bot_support_bot_idle_close.md) |
| 36 | `src/shop_bot/support_bot/ticket_media.py` | [shop_bot_support_bot_ticket_media.md](shop_bot_support_bot_ticket_media.md) |
| 37 | `src/shop_bot/factory_bot/runtime.py` | [shop_bot_factory_bot_runtime.md](shop_bot_factory_bot_runtime.md) |
| 38 | `src/shop_bot/factory_bot/middleware.py` | [shop_bot_factory_bot_middleware.md](shop_bot_factory_bot_middleware.md) |
| 39 | `src/shop_bot/factory_bot/keyboards.py` | [shop_bot_factory_bot_keyboards.md](shop_bot_factory_bot_keyboards.md) |
| 40 | `src/shop_bot/factory_bot/handlers.py` | [shop_bot_factory_bot_handlers.md](shop_bot_factory_bot_handlers.md) |
| 41 | `src/shop_bot/factory_bot/service.py` | [shop_bot_factory_bot_service.md](shop_bot_factory_bot_service.md) |
| 42 | `modules/example_module/bot_handlers.py` | [modules_example_module_bot_handlers.md](modules_example_module_bot_handlers.md) |
| 43 | `modules/example_module/db_cleanup.py` | [modules_example_module_db_cleanup.md](modules_example_module_db_cleanup.md) |
| 44 | `modules/example_module/panel_routes.py` | [modules_example_module_panel_routes.md](modules_example_module_panel_routes.md) |
| 45 | `modules/ramadan_tracker/bot_handlers.py` | [modules_ramadan_tracker_bot_handlers.md](modules_ramadan_tracker_bot_handlers.md) |
| 46 | `modules/ramadan_tracker/db_cleanup.py` | [modules_ramadan_tracker_db_cleanup.md](modules_ramadan_tracker_db_cleanup.md) |
| 47 | `modules/ramadan_tracker/db_schema.py` | [modules_ramadan_tracker_db_schema.md](modules_ramadan_tracker_db_schema.md) |
| 48 | `modules/ramadan_tracker/panel_routes.py` | [modules_ramadan_tracker_panel_routes.md](modules_ramadan_tracker_panel_routes.md) |
| 49 | `simple_collect.py` | [simple_collect.md](simple_collect.md) |
| 50 | `simple_monitor_test.py` | [simple_monitor_test.md](simple_monitor_test.md) |
