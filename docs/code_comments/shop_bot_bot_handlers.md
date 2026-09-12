# Комментарии: `src/shop_bot/bot/handlers.py`

Пользовательский Telegram-роутер и единственный fulfillment платной выдачи. Файл большой — текст разбит на две части по инвентарю.

| Часть | Диапазон | Файл |
|-------|----------|------|
| 1 | `_is_true` … `get_user_router.topup_pay_tonconnect` | [shop_bot_bot_handlers_part1.md](shop_bot_bot_handlers_part1.md) |
| 2 | `referral_program_handler` … `process_successful_payment` | [shop_bot_bot_handlers_part2.md](shop_bot_bot_handlers_part2.md) |

`process_successful_payment` — единственная точка выдачи после оплаты (вебхук, Stars, «проверить», баланс). Триал в неё **не** входит (`process_trial_key_creation`).
