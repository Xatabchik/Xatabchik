# Каталог комментариев (код не менялся)

Каждый файл здесь соответствует одному `.py` исходнику. Текст — то, что по правилам проекта стояло бы в docstring / `#`, плюс разбор блоков.

| Файл | Содержание |
|------|------------|
| [INVENTORY.md](INVENTORY.md) | Полный список функций и классов к комментированию |
| [CODE_COMMENTING_RULES.md](../../CODE_COMMENTING_RULES.md) | Стиль, снятый с существующих комментариев в репо |

Очередь из инвентаря (50 исходников). Готовый файл в каталоге — модуль прокомментирован.

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
| 10 | `src/shop_bot/bot/keyboards.py` | в работе |
| 11 | `src/shop_bot/bot/handlers.py` | в работе |
| 12 | `src/shop_bot/bot/admin_handlers.py` | в работе |
| 13 | `src/shop_bot/data_manager/database.py` | в работе |
| 14 | `src/shop_bot/data_manager/remnawave_repository.py` | в работе |
| 15 | `src/shop_bot/data_manager/scheduler.py` | в работе |
| 16 | `src/shop_bot/data_manager/backup_manager.py` | в работе |
| 17 | `src/shop_bot/data_manager/captcha_utils.py` | в работе |
| 18 | `src/shop_bot/data_manager/resource_monitor.py` | в работе |
| 19 | `src/shop_bot/data_manager/speedtest_runner.py` | в работе |
| 20 | `src/shop_bot/modules/remnawave_api.py` | в работе |
| 21 | `src/shop_bot/modules/platega_api.py` | [shop_bot_modules_platega_api.md](shop_bot_modules_platega_api.md) |
| 22 | `src/shop_bot/modules/platega_fulfillment.py` | [shop_bot_modules_platega_fulfillment.md](shop_bot_modules_platega_fulfillment.md) |
| 23 | `src/shop_bot/modules/rollypay_api.py` | [shop_bot_modules_rollypay_api.md](shop_bot_modules_rollypay_api.md) |
| 24 | `src/shop_bot/modules/heleket_api.py` | [shop_bot_modules_heleket_api.md](shop_bot_modules_heleket_api.md) |
| 25 | `src/shop_bot/modules/cryptobot_api.py` | [shop_bot_modules_cryptobot_api.md](shop_bot_modules_cryptobot_api.md) |
| 26 | `src/shop_bot/modules/email_sender.py` | [shop_bot_modules_email_sender.md](shop_bot_modules_email_sender.md) |
| 27 | `src/shop_bot/modules/telegram_reachability.py` | [shop_bot_modules_telegram_reachability.md](shop_bot_modules_telegram_reachability.md) |
| 28–50 | core, панель, Mini App, support, франшиза, плагины | в работе |

**Docstring в коде: есть** — текст скопирован из исходника дословно.  
**Docstring в коде: нет** — предлагаемый комментарий написан по прочитанному телу функции, исходник не трогали.

Вложенные хендлеры (внутри `get_user_router` / `get_admin_router` / `create_webhook_app`) комментируются в файле того же исходника.
