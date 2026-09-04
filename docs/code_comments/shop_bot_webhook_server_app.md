# Комментарии: `src/shop_bot/webhook_server/app.py`

Flask-панель и платёжные вебхуки. Фабрика `create_webhook_app`. Текст разбит на три части по инвентарю.

| Часть | Диапазон | Файл |
|-------|----------|------|
| 1 | `_parse_decimal_amount` … `admin_key_details_json` | [shop_bot_webhook_server_app_part1.md](shop_bot_webhook_server_app_part1.md) |
| 2 | `admin_key_change_plan_route` … `update_plan_route` | [shop_bot_webhook_server_app_part2.md](shop_bot_webhook_server_app_part2.md) |
| 3 | `_normalize_package_pool` … `_coerce_checkbox` | [shop_bot_webhook_server_app_part3.md](shop_bot_webhook_server_app_part3.md) |

Вебхуки провайдеров вызывают `_dispatch_payment_processing` → `process_successful_payment` (см. часть 3). Выдача ключа из панели идёт через Remnawave + `record_key_from_payload`, не через `process_successful_payment`.
