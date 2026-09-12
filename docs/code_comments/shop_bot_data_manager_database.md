# Комментарии: `src/shop_bot/data_manager/database.py`

SQLite-доступ: схема, пользователи, ключи, платежи, тикеты, настройки. Текст разбит на три части по инвентарю.

| Часть | Диапазон | Файл |
|-------|----------|------|
| 1 | `_now_str` … `get_utm_analytics` | [shop_bot_data_manager_database_part1.md](shop_bot_data_manager_database_part1.md) |
| 2 | `create_broadcast_campaign` … `find_and_complete_ton_transaction` | [shop_bot_data_manager_database_part2.md](shop_bot_data_manager_database_part2.md) |
| 3 | `_describe_transaction_action` … конец файла | [shop_bot_data_manager_database_part3.md](shop_bot_data_manager_database_part3.md) |
