# Комментарии: `src/shop_bot/webapp/handlers.py`

FastAPI Mini App: auth, каталог, платежи, ключи. Текст разбит на две части по инвентарю.

| Часть | Диапазон | Файл |
|-------|----------|------|
| 1 | `_create_payload_pending_or_error` … `SearchKeysRequest` | [shop_bot_webapp_handlers_part1.md](shop_bot_webapp_handlers_part1.md) |
| 2 | `validate_telegram_data` … `dynamic_route` | [shop_bot_webapp_handlers_part2.md](shop_bot_webapp_handlers_part2.md) |

Идентичность пользователя — только token / signed `initData` (не query `user_id`).
