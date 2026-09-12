# Комментарии: `src/shop_bot/bot/admin_handlers.py`

Админский Telegram-роутер `get_admin_router()`. Текст разбит на три части по инвентарю.

> Код разъехался по доменным модулям `src/shop_bot/bot/admin_router/`, а
> `admin_handlers.py` остался фасадом с прежним публичным API. Диапазоны имён
> ниже относятся к исходному файлу до разделения; какое определение в каком
> модуле оказалось — в [ADMIN_HANDLERS_SPLIT_MAP.md](ADMIN_HANDLERS_SPLIT_MAP.md).

| Часть | Диапазон | Файл |
|-------|----------|------|
| 1 | `_is_true` … `admin_hosts_toggle_class` | [shop_bot_bot_admin_handlers_part1.md](shop_bot_bot_admin_handlers_part1.md) |
| 2 | `admin_hosts_rename_input` … `admin_promo_confirm` | [shop_bot_bot_admin_handlers_part2.md](shop_bot_bot_admin_handlers_part2.md) |
| 3 | `admin_promo_list` … `admin_auto_renew_hours_input` | [shop_bot_bot_admin_handlers_part3.md](shop_bot_bot_admin_handlers_part3.md) |
