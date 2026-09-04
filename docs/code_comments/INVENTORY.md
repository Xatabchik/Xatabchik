# Инвентарь комментирования

Список составлен по документации ([MODULES_AND_FUNCTIONS.md](../../MODULES_AND_FUNCTIONS.md), [ARCHITECTURE.md](../../ARCHITECTURE.md)) и повторному AST-обходу. **Код не изменяется.**

Правила текста: [CODE_COMMENTING_RULES.md](../../CODE_COMMENTING_RULES.md).
Готовые аннотации: каталог `docs/code_comments/`.

| Поле | Смысл |
|------|--------|
| docstring в коде | Уже есть `"""` — в каталоге копируется дословно, плюс блоки |
| нет docstring | Предлагаемый текст только в markdown |
| вложенная | Хендлер/хелпер внутри фабрики роутера |

**К комментированию:** 2187 объявлений (функции+методы+вложенные+классы) в 50 файлах.  
Уже с docstring: 653. Без docstring: 1439. Классов: 95.

## Очередь файлов

1. `src/shop_bot/__main__.py` — 7 функц., 2 кл., без docstring: 7
2. `src/shop_bot/app.py` — 2 функц., 0 кл., без docstring: 2
3. `src/shop_bot/config.py` — 4 функц., 0 кл., без docstring: 4
4. `src/shop_bot/bot_controller.py` — 11 функц., 1 кл., без docstring: 11
5. `src/shop_bot/support_bot_controller.py` — 10 функц., 1 кл., без docstring: 10
6. `src/shop_bot/bot/middlewares.py` — 1 функц., 1 кл., без docstring: 1
7. `src/shop_bot/bot/callback_safety.py` — 5 функц., 0 кл., без docstring: 4
8. `src/shop_bot/bot/photo_helper.py` — 5 функц., 0 кл., без docstring: 1
9. `src/shop_bot/bot/image_bot.py` — 3 функц., 1 кл., без docstring: 1
10. `src/shop_bot/bot/keyboards.py` — 118 функц., 0 кл., без docstring: 83
11. `src/shop_bot/bot/handlers.py` — 247 функц., 12 кл., без docstring: 204
12. `src/shop_bot/bot/admin_handlers.py` — 356 функц., 28 кл., без docstring: 331
13. `src/shop_bot/data_manager/database.py` — 429 функц., 0 кл., без docstring: 180
14. `src/shop_bot/data_manager/remnawave_repository.py` — 64 функц., 2 кл., без docstring: 39
15. `src/shop_bot/data_manager/scheduler.py` — 38 функц., 0 кл., без docstring: 19
16. `src/shop_bot/data_manager/backup_manager.py` — 6 функц., 0 кл., без docstring: 1
17. `src/shop_bot/data_manager/captcha_utils.py` — 9 функц., 0 кл., без docstring: 1
18. `src/shop_bot/data_manager/resource_monitor.py` — 8 функц., 0 кл., без docstring: 6
19. `src/shop_bot/data_manager/speedtest_runner.py` — 25 функц., 1 кл., без docstring: 18
20. `src/shop_bot/modules/remnawave_api.py` — 86 функц., 3 кл., без docstring: 31
21. `src/shop_bot/modules/platega_api.py` — 5 функц., 1 кл., без docstring: 2
22. `src/shop_bot/modules/platega_fulfillment.py` — 7 функц., 0 кл., без docstring: 4
23. `src/shop_bot/modules/rollypay_api.py` — 7 функц., 1 кл., без docstring: 4
24. `src/shop_bot/modules/heleket_api.py` — 1 функц., 0 кл., без docstring: 0
25. `src/shop_bot/modules/cryptobot_api.py` — 1 функц., 0 кл., без docstring: 0
26. `src/shop_bot/modules/email_sender.py` — 6 функц., 0 кл., без docstring: 3
27. `src/shop_bot/modules/telegram_reachability.py` — 2 функц., 0 кл., без docstring: 0
28. `src/shop_bot/core/module_types.py` — 3 функц., 3 кл., без docstring: 3
29. `src/shop_bot/core/module_middleware.py` — 4 функц., 1 кл., без docstring: 4
30. `src/shop_bot/core/module_loader.py` — 46 функц., 2 кл., без docstring: 24
31. `src/shop_bot/webhook_server/app.py` — 240 функц., 0 кл., без docstring: 186
32. `src/shop_bot/webhook_server/apply_app_fix.py` — 1 функц., 0 кл., без docstring: 1
33. `src/shop_bot/webapp/handlers.py` — 144 функц., 29 кл., без docstring: 102
34. `src/shop_bot/support_bot/handlers.py` — 33 функц., 2 кл., без docstring: 33
35. `src/shop_bot/support_bot/idle_close.py` — 5 функц., 0 кл., без docstring: 3
36. `src/shop_bot/support_bot/ticket_media.py` — 27 функц., 1 кл., без docstring: 6
37. `src/shop_bot/factory_bot/runtime.py` — 2 функц., 0 кл., без docstring: 2
38. `src/shop_bot/factory_bot/middleware.py` — 3 функц., 1 кл., без docstring: 2
39. `src/shop_bot/factory_bot/keyboards.py` — 2 функц., 0 кл., без docstring: 2
40. `src/shop_bot/factory_bot/handlers.py` — 5 функц., 0 кл., без docstring: 4
41. `src/shop_bot/factory_bot/service.py` — 9 функц., 1 кл., без docstring: 6
42. `modules/example_module/bot_handlers.py` — 1 функц., 0 кл., без docstring: 1
43. `modules/example_module/db_cleanup.py` — 1 функц., 0 кл., без docstring: 1
44. `modules/example_module/panel_routes.py` — 1 функц., 0 кл., без docstring: 1
45. `modules/ramadan_tracker/bot_handlers.py` — 86 функц., 1 кл., без docstring: 83
46. `modules/ramadan_tracker/db_cleanup.py` — 1 функц., 0 кл., без docstring: 1
47. `modules/ramadan_tracker/db_schema.py` — 1 функц., 0 кл., без docstring: 0
48. `modules/ramadan_tracker/panel_routes.py` — 7 функц., 0 кл., без docstring: 7
49. `simple_collect.py` — 2 функц., 0 кл., без docstring: 0
50. `simple_monitor_test.py` — 5 функц., 0 кл., без docstring: 0

## `src/shop_bot/__main__.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 20–235 | `main` | function | **нет** |
| 27–50 | `ColoredFormatter` | class | **нет** |
| 37–50 | `ColoredFormatter.main.format` | nested | **нет** |
| 72–99 | `RussianizeAiogramFilter` | class | **нет** |
| 73–99 | `RussianizeAiogramFilter.main.filter` | nested | **нет** |
| 121–122 | `main._is_true` | nested | **нет** |
| 124–133 | `main.shutdown` | nested | **нет** |
| 135–227 | `main.start_services` | nested | **нет** |
| 193–205 | `main.start_services._log_bot_status_soon` | nested | **нет** |

## `src/shop_bot/app.py`

Модульный docstring: Hotfix for shop_bot/webhook_server/app.py to resolve several syntax/runtime issues:

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 14–79 | `patch_file` | function | **нет** |
| 33–65 | `patch_file.ensure_flag_in_list` | nested | **нет** |

## `src/shop_bot/config.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 9–15 | `get_profile_text` | function | **нет** |
| 17–21 | `get_vpn_active_text` | function | **нет** |
| 23–113 | `get_key_info_text` | function | **нет** |
| 115–124 | `get_purchase_success_text` | function | **нет** |

## `src/shop_bot/bot_controller.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 28–29 | `_is_true` | function | **нет** |
| 32–285 | `BotController` | class | **нет** |
| 33–45 | `BotController.__init__` | method | **нет** |
| 47–68 | `BotController._start_own_loop` | method | **нет** |
| 50–62 | `BotController._start_own_loop._runner` | nested | **нет** |
| 70–74 | `BotController.set_loop` | method | **нет** |
| 76–77 | `BotController.get_loop` | method | **нет** |
| 79–80 | `BotController.get_bot_instance` | method | **нет** |
| 82–135 | `BotController._start_polling` | method | **нет** |
| 137–269 | `BotController.start` | method | **нет** |
| 271–282 | `BotController.stop` | method | **нет** |
| 284–285 | `BotController.get_status` | method | **нет** |

## `src/shop_bot/support_bot_controller.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 15–132 | `SupportBotController` | class | **нет** |
| 16–26 | `SupportBotController.__init__` | method | **нет** |
| 28–47 | `SupportBotController._start_own_loop` | method | **нет** |
| 31–41 | `SupportBotController._start_own_loop._runner` | nested | **нет** |
| 49–52 | `SupportBotController.set_loop` | method | **нет** |
| 54–55 | `SupportBotController.get_loop` | method | **нет** |
| 57–58 | `SupportBotController.get_bot_instance` | method | **нет** |
| 60–76 | `SupportBotController._start_polling` | method | **нет** |
| 78–118 | `SupportBotController.start` | method | **нет** |
| 120–129 | `SupportBotController.stop` | method | **нет** |
| 131–132 | `SupportBotController.get_status` | method | **нет** |

## `src/shop_bot/bot/middlewares.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 7–77 | `BanMiddleware` | class | **нет** |
| 8–77 | `BanMiddleware.__call__` | method | **нет** |

## `src/shop_bot/bot/callback_safety.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 14–49 | `fast_callback_answer` | function | есть: Fast ACK for callback queries. |
| 40–47 | `fast_callback_answer.wrapper` | nested | **нет** |
| 51–63 | `catch_callback_errors` | function | **нет** |
| 53–62 | `catch_callback_errors.wrapper` | nested | **нет** |
| 67–73 | `handle_unknown_callback` | function | **нет** |

## `src/shop_bot/bot/photo_helper.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 8–13 | `_default_image_path` | function | есть: Returns absolute path to default image (src/shop_bot/img/obla.png). |
| 16–18 | `_get_default_photo` | function | **нет** |
| 21–37 | `answer_with_image` | function | есть: Drop-in replacement for message.answer(...), but sends a photo with caption. |
| 40–70 | `send_with_image` | function | есть: Drop-in replacement for bot.send_message(...), but sends a photo with caption. |
| 73–100 | `edit_with_image` | function | есть: Replacement for message.edit_text(...). |

## `src/shop_bot/bot/image_bot.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 11–26 | `_pick_image_path` | function | есть: Pick an image file from shop_bot/img. |
| 29–32 | `_filter_kwargs` | function | есть: Keep only kwargs that func(...) accepts (defensive for aiogram version differences). |
| 35–111 | `ImageBot` | class | есть: Bot that attaches an image from shop_bot/img to every outgoing text message. |
| 45–111 | `ImageBot.send_message` | method | **нет** |

## `src/shop_bot/bot/keyboards.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 28–37 | `_normalize_url` | function | **нет** |
| 40–43 | `_get_notifications_support_url` | function | есть: Support URL for inactive usage reminder notifications (admin-configurable). |
| 46–56 | `_ru_days` | function | есть: Русское склонение слова "день". |
| 63–169 | `create_main_menu_keyboard` | function | **нет** |
| 171–186 | `create_admin_menu_keyboard` | function | **нет** |
| 189–197 | `create_admin_system_menu_keyboard` | function | **нет** |
| 201–218 | `create_admin_settings_menu_keyboard` | function | **нет** |
| 221–227 | `create_admin_lte_settings_keyboard` | function | **нет** |
| 230–245 | `create_admin_payments_menu_keyboard` | function | есть: Меню выбора платежной системы. |
| 232–233 | `create_admin_payments_menu_keyboard._mark` | nested | **нет** |
| 248–296 | `create_admin_payment_detail_keyboard` | function | есть: Клавиатура управления конкретной платежкой. |
| 299–302 | `create_admin_payments_cancel_keyboard` | function | **нет** |
| 305–338 | `create_admin_referral_settings_keyboard` | function | **нет** |
| 341–357 | `create_admin_franchise_settings_keyboard` | function | есть: Создаёт клавиатуру настроек франшизы |
| 360–367 | `create_admin_auto_renew_keyboard` | function | **нет** |
| 370–385 | `create_admin_referral_type_keyboard` | function | **нет** |
| 390–397 | `_host_digest` | function | есть: Safe stable digest for callback_data. |
| 400–418 | `create_admin_hosts_menu_keyboard` | function | есть: Hosts list + add button. |
| 421–442 | `create_admin_host_manage_keyboard` | function | **нет** |
| 445–449 | `create_admin_hosts_cancel_keyboard` | function | **нет** |
| 452–457 | `create_admin_hosts_delete_confirm_keyboard` | function | **нет** |
| 460–488 | `create_admin_host_squads_keyboard` | function | есть: Список сквадов хоста с переключением активности и удалением. |
| 491–498 | `create_admin_squad_class_keyboard` | function | **нет** |
| 502–528 | `create_admin_trial_settings_keyboard` | function | **нет** |
| 531–540 | `create_admin_trial_host_keyboard` | function | **нет** |
| 542–567 | `create_admin_notifications_settings_keyboard` | function | есть: Настройки уведомлений о неиспользовании трафика. |
| 571–619 | `create_admin_plans_host_menu_keyboard` | function | есть: Меню тарифов для выбранного хоста (админка). |
| 622–674 | `create_admin_plan_manage_keyboard` | function | **нет** |
| 677–700 | `create_admin_traffic_packages_keyboard` | function | **нет** |
| 703–712 | `create_admin_traffic_package_manage_keyboard` | function | **нет** |
| 716–724 | `create_admin_plans_duration_type_keyboard` | function | есть: Выбор единиц срока тарифа при создании. |
| 727–735 | `create_admin_plan_duration_type_keyboard` | function | есть: Выбор единиц срока тарифа при редактировании. |
| 737–742 | `create_admin_plan_delete_confirm_keyboard` | function | **нет** |
| 746–751 | `create_admin_plan_edit_flow_keyboard` | function | **нет** |
| 754–759 | `create_admin_plans_flow_keyboard` | function | **нет** |
| 761–768 | `create_admins_menu_keyboard` | function | **нет** |
| 770–796 | `create_admin_users_keyboard` | function | **нет** |
| 798–814 | `create_admin_user_actions_keyboard` | function | **нет** |
| 816–863 | `create_keys_management_keyboard` | function | есть: Клавиатура списка ключей пользователя (раздел 'Мои ключи') с пагинацией. |
| 866–902 | `create_sent_gifts_keyboard` | function | есть: Клавиатура раздела «Отправленные подарки». |
| 905–952 | `create_admin_user_keys_keyboard` | function | **нет** |
| 954–964 | `create_admin_key_actions_keyboard` | function | **нет** |
| 966–971 | `create_admin_delete_key_confirm_keyboard` | function | **нет** |
| 973–976 | `create_cancel_keyboard` | function | **нет** |
| 979–980 | `create_admin_cancel_keyboard` | function | **нет** |
| 983–989 | `create_admin_promo_menu_keyboard` | function | **нет** |
| 992–998 | `create_admin_promo_discount_keyboard` | function | **нет** |
| 1000–1006 | `create_admin_promo_code_keyboard` | function | **нет** |
| 1008–1018 | `create_admin_promo_limit_keyboard` | function | **нет** |
| 1020–1029 | `create_admin_promo_valid_from_keyboard` | function | **нет** |
| 1031–1040 | `create_admin_promo_valid_until_keyboard` | function | **нет** |
| 1042–1048 | `create_admin_promo_description_keyboard` | function | **нет** |
| 1051–1058 | `create_admin_promo_segment_keyboard` | function | **нет** |
| 1061–1067 | `create_admin_promo_plans_keyboard` | function | **нет** |
| 1069–1076 | `create_broadcast_parse_mode_keyboard` | function | **нет** |
| 1079–1085 | `create_broadcast_options_keyboard` | function | **нет** |
| 1087–1092 | `create_broadcast_confirmation_keyboard` | function | **нет** |
| 1094–1097 | `create_broadcast_cancel_keyboard` | function | **нет** |
| 1099–1112 | `create_about_keyboard` | function | **нет** |
| 1114–1123 | `create_support_keyboard` | function | есть: Кнопка техподдержки (всегда ведёт на фиксированный URL). |
| 1125–1133 | `create_support_bot_link_keyboard` | function | **нет** |
| 1135–1162 | `create_inactive_usage_reminder_keyboard` | function | есть: Клавиатура для напоминания, если пользователь не подключил устройство. |
| 1164–1172 | `create_support_menu_keyboard` | function | **нет** |
| 1174–1184 | `create_tickets_list_keyboard` | function | **нет** |
| 1186–1193 | `create_ticket_actions_keyboard` | function | **нет** |
| 1195–1202 | `create_host_selection_keyboard` | function | **нет** |
| 1204–1254 | `create_plans_keyboard` | function | **нет** |
| 1257–1343 | `create_payment_method_keyboard` | function | **нет** |
| 1269–1274 | `create_payment_method_keyboard._label` | nested | **нет** |
| 1346–1351 | `create_skip_email_keyboard` | function | **нет** |
| 1353–1359 | `create_stars_invoice_keyboard` | function | есть: Кнопки под системной Pay ⭐: сначала Pay (требование Telegram), затем Назад. |
| 1362–1367 | `create_ton_connect_keyboard` | function | **нет** |
| 1369–1374 | `create_payment_keyboard` | function | **нет** |
| 1376–1382 | `create_yoomoney_payment_keyboard` | function | **нет** |
| 1384–1390 | `create_yookassa_payment_keyboard` | function | **нет** |
| 1392–1398 | `create_platega_payment_keyboard` | function | **нет** |
| 1401–1407 | `create_rollypay_payment_keyboard` | function | **нет** |
| 1410–1416 | `create_cryptobot_payment_keyboard` | function | **нет** |
| 1418–1463 | `create_topup_payment_method_keyboard` | function | **нет** |
| 1421–1426 | `create_topup_payment_method_keyboard._label` | nested | **нет** |
| 1466–1485 | `create_traffic_packages_keyboard` | function | **нет** |
| 1488–1533 | `create_traffic_gb_payment_method_keyboard` | function | **нет** |
| 1491–1496 | `create_traffic_gb_payment_method_keyboard._label` | nested | **нет** |
| 1536–1557 | `create_lte_packages_keyboard` | function | есть: Пакеты докупки независимого LTE-пула (premium-ноды 💰). |
| 1560–1607 | `create_lte_gb_payment_method_keyboard` | function | есть: Выбор способа оплаты докупки LTE-пула (полный аналог create_traffic_gb_payment_method_keyboard, |
| 1565–1570 | `create_lte_gb_payment_method_keyboard._label` | nested | **нет** |
| 1610–1657 | `create_main_reset_payment_method_keyboard` | function | есть: Выбор способа оплаты разовой платной перезагрузки основного пула трафика. |
| 1614–1619 | `create_main_reset_payment_method_keyboard._label` | nested | **нет** |
| 1660–1667 | `create_rename_key_keyboard` | function | есть: Клавиатура для переименования ключа. |
| 1670–1710 | `create_search_keys_results_keyboard` | function | есть: Клавиатура с результатами поиска ключей. |
| 1712–1716 | `create_admin_search_keys_cancel_keyboard` | function | есть: Клавиатура для отмены поиска ключей администратором. |
| 1718–1761 | `create_admin_search_keys_results_keyboard` | function | есть: Клавиатура с результатами поиска ключей (для админа). |
| 1763–1798 | `create_gifts_management_keyboard` | function | есть: Клавиатура для управления неактивными подарками. |
| 1800–1848 | `create_gift_info_keyboard` | function | есть: Клавиатура для информации о подарке (как обычный ключ, но без продления). |
| 1850–1905 | `create_key_info_keyboard` | function | **нет** |
| 1906–1914 | `create_howto_vless_keyboard` | function | **нет** |
| 1916–1924 | `create_howto_vless_keyboard_key` | function | **нет** |
| 1926–1929 | `create_back_to_menu_keyboard` | function | **нет** |
| 1931–1953 | `create_profile_keyboard` | function | **нет** |
| 1955–1968 | `create_welcome_keyboard` | function | **нет** |
| 1970–1971 | `get_main_menu_button` | function | **нет** |
| 1973–1974 | `get_buy_button` | function | **нет** |
| 1977–2000 | `create_admin_users_pick_keyboard` | function | **нет** |
| 2002–2029 | `create_admin_hosts_pick_keyboard` | function | **нет** |
| 2032–2054 | `create_admin_ssh_targets_keyboard` | function | **нет** |
| 2056–2111 | `create_admin_keys_for_host_keyboard` | function | **нет** |
| 2113–2119 | `create_admin_months_pick_keyboard` | function | **нет** |
| 2122–2440 | `create_dynamic_keyboard` | function | есть: Create a keyboard based on database configuration |
| 2442–2460 | `create_dynamic_main_menu_keyboard` | function | есть: Create main menu keyboard using dynamic configuration |
| 2462–2464 | `create_dynamic_admin_menu_keyboard` | function | есть: Create admin menu keyboard using dynamic configuration |
| 2465–2467 | `create_dynamic_admin_system_menu_keyboard` | function | есть: Create admin system submenu keyboard using dynamic configuration |
| 2470–2472 | `create_dynamic_admin_settings_menu_keyboard` | function | есть: Create admin settings submenu keyboard using dynamic configuration |
| 2475–2477 | `create_dynamic_profile_keyboard` | function | есть: Create profile keyboard using dynamic configuration |
| 2479–2481 | `create_dynamic_support_menu_keyboard` | function | есть: Create support menu keyboard using dynamic configuration |
| 2497–2503 | `create_broadcast_button_type_keyboard` | function | **нет** |
| 2505–2512 | `create_broadcast_actions_keyboard` | function | **нет** |
| 2518–2522 | `create_math_captcha_keyboard` | function | есть: Клавиатура для математической капчи с текстовым полем. |
| 2525–2541 | `create_button_captcha_keyboard` | function | есть: Клавиатура для капчи с выбором кнопки (смайлик или текст). |

## `src/shop_bot/bot/handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 122–123 | `_is_true` | function | **нет** |
| 125–175 | `_get_payment_methods` | function | есть: Собирает доступные способы оплаты из актуальных настроек (без перезапуска бота). |
| 190–213 | `_classify_key_creation_error` | function | **нет** |
| 216–228 | `_format_key_action_label` | function | **нет** |
| 231–240 | `_log_key_creation_error` | function | **нет** |
| 243–268 | `_notify_admins_key_creation_error` | function | **нет** |
| 271–308 | `_notify_user_key_creation_error` | function | **нет** |
| 311–329 | `_handle_key_creation_failure` | function | **нет** |
| 332–413 | `_abort_topup_fulfillment` | function | есть: Компенсирующая транзакция при сбое применения оплаченной докупки трафика. |
| 416–453 | `_notify_admins_topup_desync` | function | есть: Докупка применена на VPN-сервере, но не сохранилась в БД бота. |
| 456–514 | `_abort_key_fulfillment` | function | есть: Компенсирующая транзакция при сбое выдачи ключа после оплаты. |
| 516–529 | `_safe_edit_or_answer` | function | есть: Заменить `message.edit_text(...)` там, где предыдущее сообщение может |
| 532–543 | `_format_duration_label` | function | **нет** |
| 546–557 | `_compute_days_to_add` | function | **нет** |
| 560–570 | `_tariff_label_from_origin` | function | есть: Human label for subscription page tariff line. |
| 573–600 | `_build_key_origin_meta` | function | есть: Store key origin info inside vpn_keys.description as JSON. |
| 603–742 | `grant_referrer_day_bonus_for_trial` | function | есть: Начислить рефереру +1 день только в момент активации триала рефералом. |
| 649–677 | `grant_referrer_day_bonus_for_trial._parse_exp_dt` | nested | **нет** |
| 745–759 | `_webapp_public_base` | function | есть: Публичный базовый URL Mini App, если webapp включён и задан домен. |
| 762–771 | `_build_gift_links` | function | есть: Построить обе ссылки активации подарка: в мини-приложении (webapp) и в Telegram. |
| 774–784 | `_build_referral_links` | function | есть: Построить реферальные ссылки: (webapp_link, telegram_link). |
| 791–794 | `_referral_share_text` | function | есть: Текст для t.me/share из настроек (Контент → referral_share_text). |
| 797–800 | `_gift_share_text` | function | есть: Текст для t.me/share при шаринге подарка (Контент → gift_share_text). |
| 803–812 | `_telegram_share_url` | function | есть: Собрать https://t.me/share/url?... с пробелами как %20 (не +). |
| 815–903 | `_activate_gift_directly` | function | есть: Активировать подарок для пользователя. |
| 906–1016 | `_create_heleket_payment_request` | function | есть: Создание инвойса в Heleket и возврат payment URL. |
| 1018–1065 | `create_cryptobot_api_invoice` | function | есть: Упрощённая обёртка для создания инвойса в Crypto Pay (CryptoBot), используемая |
| 1068–1261 | `_create_cryptobot_invoice` | function | есть: Создание инвойса в Crypto Pay (CryptoBot) и возврат bot_invoice_url. |
| 1263–1265 | `KeyPurchase` | class | **нет** |
| 1267–1268 | `Captcha` | class | **нет** |
| 1270–1271 | `Onboarding` | class | **нет** |
| 1273–1277 | `PaymentProcess` | class | **нет** |
| 1280–1282 | `TopUpProcess` | class | **нет** |
| 1285–1287 | `TrafficGbTopUp` | class | **нет** |
| 1290–1292 | `LteGbTopUp` | class | **нет** |
| 1295–1296 | `MainPoolReset` | class | **нет** |
| 1299–1302 | `SupportDialog` | class | **нет** |
| 1312–1316 | `FranchiseStates` | class | **нет** |
| 1319–1320 | `KeyManagement` | class | **нет** |
| 1323–1329 | `ReferralWithdraw` | class | **нет** |
| 1332–1334 | `is_valid_email` | function | **нет** |
| 1336–1375 | `show_captcha` | function | есть: Показывает капчу пользователю. |
| 1378–1506 | `show_main_menu` | function | **нет** |
| 1508–1529 | `process_successful_onboarding` | function | есть: Завершает онбординг: ставит флаг согласия и открывает главное меню. |
| 1531–1544 | `registration_required` | function | **нет** |
| 1533–1543 | `registration_required.decorated_function` | nested | **нет** |
| 1546–1617 | `_maybe_pay_referral_start_bonus` | function | есть: Выплатить рефереру фиксированный бонус за регистрацию приглашённого пользователя |
| 1620–9295 | `get_user_router` | function | **нет** |
| 1624–1778 | `get_user_router.start_handler` | nested | **нет** |
| 1781–1806 | `get_user_router.check_subscription_handler` | nested | **нет** |
| 1809–1810 | `get_user_router.onboarding_fallback_handler` | nested | **нет** |
| 1817–1900 | `get_user_router.captcha_answer_handler` | nested | есть: Обработчик текстового ответа на математическую капчу. |
| 1903–1998 | `get_user_router.captcha_button_answer_handler` | nested | есть: Обработчик ответа на капчу с выбором кнопки. |
| 2001–2005 | `get_user_router.cancel_captcha_handler` | nested | есть: Отмена капчи. |
| 2009–2010 | `get_user_router.main_menu_handler` | nested | **нет** |
| 2014–2016 | `get_user_router.back_to_main_menu_handler` | nested | **нет** |
| 2020–2022 | `get_user_router.open_main_menu_handler` | nested | **нет** |
| 2026–2028 | `get_user_router.show_main_menu_cb` | nested | **нет** |
| 2032–2102 | `get_user_router.profile_handler_callback` | nested | **нет** |
| 2106–2117 | `get_user_router.toggle_expiry_notifications_handler` | nested | **нет** |
| 2121–2142 | `get_user_router.show_inactive_gifts_handler` | nested | **нет** |
| 2146–2173 | `get_user_router.gifts_page_handler` | nested | **нет** |
| 2177–2263 | `get_user_router.show_gift_handler` | nested | **нет** |
| 2267–2329 | `get_user_router.send_gift_link_handler` | nested | есть: Отправка ссылки подарка пользователю. |
| 2333–2366 | `get_user_router.activate_own_gift_handler` | nested | есть: Активировать собственный неактивированный подарок себе (аналог webapp-кнопки 'Активировать себе'). |
| 2368–2378 | `get_user_router._resolve_plan_for_traffic_topup` | nested | **нет** |
| 2382–2411 | `get_user_router.traffic_gb_start_handler` | nested | **нет** |
| 2415–2458 | `get_user_router.traffic_gb_pick_handler` | nested | **нет** |
| 2460–2471 | `get_user_router._traffic_gb_metadata` | nested | **нет** |
| 2474–2491 | `get_user_router.trafficgb_pay_balance_handler` | nested | **нет** |
| 2494–2511 | `get_user_router.trafficgb_pay_referral_balance_handler` | nested | **нет** |
| 2514–2566 | `get_user_router.trafficgb_pay_yookassa_handler` | nested | **нет** |
| 2569–2601 | `get_user_router.trafficgb_pay_platega_handler` | nested | **нет** |
| 2604–2639 | `get_user_router.trafficgb_pay_rollypay_handler` | nested | **нет** |
| 2642–2678 | `get_user_router.trafficgb_pay_heleket_handler` | nested | **нет** |
| 2681–2718 | `get_user_router.trafficgb_pay_cryptobot_handler` | nested | **нет** |
| 2721–2749 | `get_user_router.trafficgb_pay_yoomoney_handler` | nested | **нет** |
| 2752–2789 | `get_user_router.trafficgb_pay_stars_handler` | nested | **нет** |
| 2791–2801 | `get_user_router._resolve_plan_for_lte_topup` | nested | **нет** |
| 2805–2836 | `get_user_router.lte_gb_start_handler` | nested | **нет** |
| 2840–2884 | `get_user_router.lte_gb_pick_handler` | nested | **нет** |
| 2886–2897 | `get_user_router._lte_gb_metadata` | nested | **нет** |
| 2900–2917 | `get_user_router.ltegb_pay_balance_handler` | nested | **нет** |
| 2920–2937 | `get_user_router.ltegb_pay_referral_balance_handler` | nested | **нет** |
| 2940–2992 | `get_user_router.ltegb_pay_yookassa_handler` | nested | **нет** |
| 2995–3027 | `get_user_router.ltegb_pay_platega_handler` | nested | **нет** |
| 3030–3065 | `get_user_router.ltegb_pay_rollypay_handler` | nested | **нет** |
| 3068–3104 | `get_user_router.ltegb_pay_heleket_handler` | nested | **нет** |
| 3107–3144 | `get_user_router.ltegb_pay_cryptobot_handler` | nested | **нет** |
| 3147–3175 | `get_user_router.ltegb_pay_yoomoney_handler` | nested | **нет** |
| 3178–3215 | `get_user_router.ltegb_pay_stars_handler` | nested | **нет** |
| 3217–3221 | `get_user_router._resolve_key_for_main_reset` | nested | **нет** |
| 3225–3292 | `get_user_router.main_reset_start_handler` | nested | **нет** |
| 3294–3303 | `get_user_router._main_reset_metadata` | nested | **нет** |
| 3306–3323 | `get_user_router.mainreset_pay_balance_handler` | nested | **нет** |
| 3326–3343 | `get_user_router.mainreset_pay_referral_balance_handler` | nested | **нет** |
| 3346–3397 | `get_user_router.mainreset_pay_yookassa_handler` | nested | **нет** |
| 3401–3407 | `get_user_router.topup_start_handler` | nested | **нет** |
| 3410–3432 | `get_user_router.topup_amount_input` | nested | **нет** |
| 3435–3516 | `get_user_router.topup_pay_yookassa` | nested | **нет** |
| 3520–3609 | `get_user_router.create_stars_invoice_handler` | nested | **нет** |
| 3612–3669 | `get_user_router.payment_stars_back_handler` | nested | **нет** |
| 3672–3718 | `get_user_router.topup_stars_handler` | nested | **нет** |
| 3722–3741 | `get_user_router.pre_checkout_handler` | nested | **нет** |
| 3745–3804 | `get_user_router.stars_success_handler` | nested | **нет** |
| 3808–3812 | `get_user_router._rollypay_is_enabled` | nested | **нет** |
| 3814–3829 | `get_user_router._create_rollypay_payment_link` | nested | **нет** |
| 3831–3832 | `get_user_router._platega_is_enabled` | nested | **нет** |
| 3834–3835 | `get_user_router._platega_get_base_url` | nested | **нет** |
| 3837–3849 | `get_user_router._platega_get_method_code` | nested | **нет** |
| 3851–3875 | `get_user_router._platega_request` | nested | **нет** |
| 3877–3891 | `get_user_router._create_platega_payment_link` | nested | **нет** |
| 3893–3896 | `get_user_router._get_platega_transaction` | nested | **нет** |
| 3898–3912 | `get_user_router._build_yoomoney_link` | nested | **нет** |
| 3915–3972 | `get_user_router.pay_yoomoney_handler` | nested | **нет** |
| 3975–4022 | `get_user_router.topup_yoomoney_handler` | nested | **нет** |
| 4026–4079 | `get_user_router.check_platega_payment_handler` | nested | **нет** |
| 4082–4157 | `get_user_router.check_rollypay_payment_handler` | nested | **нет** |
| 4160–4250 | `get_user_router.check_yookassa_payment_handler` | nested | **нет** |
| 4253–4337 | `get_user_router.check_pending_payment_handler` | nested | **нет** |
| 4340–4382 | `get_user_router.topup_pay_platega` | nested | **нет** |
| 4385–4430 | `get_user_router.topup_pay_rollypay` | nested | **нет** |
| 4433–4469 | `get_user_router.topup_pay_heleket_like` | nested | **нет** |
| 4472–4508 | `get_user_router.topup_pay_cryptobot` | nested | **нет** |
| 4511–4573 | `get_user_router.topup_pay_tonconnect` | nested | **нет** |
| 4577–4682 | `get_user_router.referral_program_handler` | nested | **нет** |
| 4595–4601 | `get_user_router.referral_program_handler._to_float_setting` | nested | **нет** |
| 4603–4605 | `get_user_router.referral_program_handler._is_true_setting` | nested | **нет** |
| 4613–4618 | `get_user_router.referral_program_handler._fmt_num` | nested | **нет** |
| 4688–4732 | `get_user_router.referral_top_handler` | nested | **нет** |
| 4739–4741 | `get_user_router._ref_is_true` | nested | **нет** |
| 4743–4748 | `get_user_router._ref_float_setting` | nested | **нет** |
| 4750–4751 | `get_user_router._ref_withdraw_enabled` | nested | **нет** |
| 4753–4758 | `get_user_router._ref_method_enabled` | nested | **нет** |
| 4760–4762 | `get_user_router._ref_sbp_banks` | nested | **нет** |
| 4766–4772 | `get_user_router._ref_mask` | nested | **нет** |
| 4774–4784 | `get_user_router._kb_my_balance` | nested | **нет** |
| 4788–4796 | `get_user_router.referral_my_balance` | nested | **нет** |
| 4807–4836 | `get_user_router.referral_withdraw_requests` | nested | **нет** |
| 4841–4861 | `get_user_router.referral_transfer_start` | nested | **нет** |
| 4865–4921 | `get_user_router.referral_transfer_amount` | nested | **нет** |
| 4923–4937 | `get_user_router._kb_payout_methods` | nested | **нет** |
| 4941–4964 | `get_user_router.referral_payout_methods` | nested | **нет** |
| 4966–4976 | `get_user_router._kb_method_types` | nested | **нет** |
| 4980–4990 | `get_user_router.referral_payout_method_add` | nested | **нет** |
| 4992–4998 | `get_user_router._kb_bank_choice` | nested | **нет** |
| 5002–5020 | `get_user_router.referral_payout_method_add_type` | nested | **нет** |
| 5024–5038 | `get_user_router.referral_payout_method_bank_choice` | nested | **нет** |
| 5042–5064 | `get_user_router.referral_payout_method_value` | nested | **нет** |
| 5068–5090 | `get_user_router.referral_payout_method_delete` | nested | **нет** |
| 5094–5135 | `get_user_router.referral_withdraw_start` | nested | **нет** |
| 5139–5161 | `get_user_router.referral_withdraw_choose_method` | nested | **нет** |
| 5165–5215 | `get_user_router.referral_withdraw_amount` | nested | **нет** |
| 5220–5236 | `get_user_router.about_handler` | nested | **нет** |
| 5241–5288 | `get_user_router.user_speedtest_last_handler` | nested | **нет** |
| 5292–5309 | `get_user_router.about_handler` | nested | **нет** |
| 5313–5330 | `get_user_router.support_menu_handler` | nested | **нет** |
| 5334–5350 | `get_user_router.support_external_handler` | nested | **нет** |
| 5354–5363 | `get_user_router.support_new_ticket_handler` | nested | **нет** |
| 5367–5376 | `get_user_router.support_subject_received` | nested | **нет** |
| 5380–5389 | `get_user_router.support_message_received` | nested | **нет** |
| 5393–5402 | `get_user_router.support_my_tickets_handler` | nested | **нет** |
| 5406–5415 | `get_user_router.support_view_ticket_handler` | nested | **нет** |
| 5419–5429 | `get_user_router.support_reply_prompt_handler` | nested | **нет** |
| 5433–5442 | `get_user_router.support_reply_received` | nested | **нет** |
| 5445–5489 | `get_user_router.forum_thread_message_handler` | nested | **нет** |
| 5493–5502 | `get_user_router.support_close_ticket_handler` | nested | **нет** |
| 5506–5526 | `get_user_router._remnawave_key_exists` | nested | есть: Проверяет, существует ли ключ (пользователь) в Remnawave. |
| 5531–5654 | `get_user_router._extract_connected_devices` | nested | есть: Возвращает количество подключённых устройств (HWID/Devices) по данным Remnawave. |
| 5543–5572 | `get_user_router._extract_connected_devices._count_from_value` | nested | **нет** |
| 5657–5732 | `get_user_router._get_connected_devices_count` | nested | есть: Надёжно получить количество подключённых HWID-устройств. |
| 5686–5730 | `get_user_router._get_connected_devices_count._count_any` | nested | **нет** |
| 5735–5786 | `get_user_router._get_devices_list` | nested | есть: Получить полный список подключённых HWID-устройств с информацией о каждом. |
| 5789–5818 | `get_user_router._is_key_without_billing_plan` | nested | есть: Триальный или подарочный ключ: биллингового тарифа у него нет. |
| 5820–5855 | `get_user_router._resolve_plan_id_for_key` | nested | есть: Определяет plan_id, привязанный к ключу. |
| 5858–5877 | `get_user_router._extract_traffic_used_bytes` | nested | есть: Извлекает использованный трафик из payload пользователя Remnawave (если поле есть). |
| 5879–5884 | `get_user_router._format_bytes_gb` | nested | **нет** |
| 5886–6088 | `get_user_router._get_tariff_info_for_key` | nested | есть: Подбирает данные тарифа для отображения в 'Мои ключи'. |
| 6090–6170 | `get_user_router.sync_user_keys_with_remnawave` | nested | есть: Синхронизирует ключи пользователя в БД с фактическими ключами в Remnawave. |
| 6111–6126 | `get_user_router.sync_user_keys_with_remnawave._parse_missing_dt` | nested | **нет** |
| 6128–6130 | `get_user_router.sync_user_keys_with_remnawave._check` | nested | **нет** |
| 6173–6194 | `get_user_router.manage_keys_handler` | nested | **нет** |
| 6198–6211 | `get_user_router.sent_gifts_handler` | nested | **нет** |
| 6215–6221 | `get_user_router.search_my_keys_handler` | nested | **нет** |
| 6225–6251 | `get_user_router.search_keys_input_handler` | nested | **нет** |
| 6255–6275 | `get_user_router.search_keys_page_handler` | nested | **нет** |
| 6279–6289 | `get_user_router.cancel_search_keys_handler` | nested | **нет** |
| 6297–6337 | `get_user_router.rename_key_start` | nested | есть: Начало процесса переименования ключа. |
| 6341–6430 | `get_user_router.rename_key_process` | nested | есть: Обработка ввода нового названия ключа. |
| 6434–6505 | `get_user_router.remove_key_name` | nested | есть: Удаление названия ключа. |
| 6509–6568 | `get_user_router.cancel_rename_key` | nested | есть: Отмена переименования ключа. |
| 6576–6603 | `get_user_router.trial_period_handler` | nested | **нет** |
| 6607–6610 | `get_user_router.trial_host_selection_handler` | nested | **нет** |
| 6612–6720 | `get_user_router.process_trial_key_creation` | nested | **нет** |
| 6724–6872 | `get_user_router.show_key_handler` | nested | **нет** |
| 6876–6894 | `get_user_router.auto_renew_key_toggle` | nested | **нет** |
| 6898–6908 | `get_user_router.toggle_auto_renew_profile` | nested | **нет** |
| 6912–6939 | `get_user_router.switch_server_start` | nested | **нет** |
| 6943–7075 | `get_user_router.select_host_for_switch` | nested | **нет** |
| 7079–7097 | `get_user_router.show_qr_handler` | nested | **нет** |
| 7101–7199 | `get_user_router.delete_device_handler` | nested | есть: Обработчик удаления HWID-устройства с ключа. |
| 7203–7212 | `get_user_router.show_instruction_handler` | nested | **нет** |
| 7216–7224 | `get_user_router.show_instruction_handler` | nested | **нет** |
| 7228–7272 | `get_user_router.howto_android_handler` | nested | **нет** |
| 7276–7300 | `get_user_router.howto_android_key_handler` | nested | **нет** |
| 7304–7322 | `get_user_router.howto_ios_handler` | nested | **нет** |
| 7326–7350 | `get_user_router.howto_ios_key_handler` | nested | **нет** |
| 7354–7402 | `get_user_router.howto_windows_handler` | nested | **нет** |
| 7406–7434 | `get_user_router.howto_windows_key_handler` | nested | **нет** |
| 7438–7459 | `get_user_router.howto_linux_handler` | nested | **нет** |
| 7463–7490 | `get_user_router.howto_linux_key_handler` | nested | **нет** |
| 7494–7504 | `get_user_router.gift_new_key_handler` | nested | **нет** |
| 7508–7518 | `get_user_router.buy_new_key_handler` | nested | **нет** |
| 7522–7532 | `get_user_router.select_host_for_purchase_handler` | nested | **нет** |
| 7535–7545 | `get_user_router.select_host_for_gift_handler` | nested | **нет** |
| 7550–7586 | `get_user_router.extend_key_handler` | nested | **нет** |
| 7590–7612 | `get_user_router.plan_selection_handler` | nested | **нет** |
| 7616–7677 | `get_user_router.back_to_plans_handler` | nested | **нет** |
| 7680–7686 | `get_user_router.process_email_handler` | nested | **нет** |
| 7689–7692 | `get_user_router.skip_email_handler` | nested | **нет** |
| 7694–7818 | `get_user_router.show_payment_options` | nested | **нет** |
| 7821–7832 | `get_user_router.back_to_email_prompt_handler` | nested | **нет** |
| 7835–7841 | `get_user_router.prompt_promo_code` | nested | **нет** |
| 7844–7846 | `get_user_router.cancel_promo_entry` | nested | **нет** |
| 7849–7885 | `get_user_router.handle_promo_code_input` | nested | **нет** |
| 7888–8022 | `get_user_router.create_yookassa_payment_handler` | nested | **нет** |
| 8026–8111 | `get_user_router.pay_platega_handler` | nested | **нет** |
| 8114–8199 | `get_user_router.pay_rollypay_handler` | nested | **нет** |
| 8202–8276 | `get_user_router.create_cryptobot_invoice_handler` | nested | **нет** |
| 8279–8404 | `get_user_router.check_crypto_invoice_handler` | nested | **нет** |
| 8406–8474 | `get_user_router.create_ton_invoice_handler` | nested | **нет** |
| 8477–8520 | `get_user_router.pay_with_main_balance_handler` | nested | **нет** |
| 8523–8562 | `get_user_router.pay_with_referral_balance_handler` | nested | **нет** |
| 8578–8587 | `get_user_router.stale_payment_method_callback` | nested | есть: Устаревшие pay_* после смены FSM (например, после Stars invoice). |
| 8594–8716 | `get_user_router._gift_username_catcher` | nested | **нет** |
| 8723–8727 | `get_user_router._kb_cancel_factory` | nested | **нет** |
| 8729–8736 | `get_user_router._kb_partner_cabinet` | nested | **нет** |
| 8738–8742 | `get_user_router._kb_partner_withdraw` | nested | **нет** |
| 8745–8760 | `get_user_router._kb_partner_requisites` | nested | **нет** |
| 8762–8766 | `get_user_router._kb_partner_requisite_input` | nested | **нет** |
| 8768–8779 | `get_user_router._mask_requisite` | nested | **нет** |
| 8781–8789 | `get_user_router._infer_requisite_type` | nested | **нет** |
| 8793–8824 | `get_user_router.partner_requisites` | nested | **нет** |
| 8828–8844 | `get_user_router.partner_requisite_add` | nested | **нет** |
| 8848–8860 | `get_user_router.partner_requisite_cancel` | nested | **нет** |
| 8864–8885 | `get_user_router.partner_requisite_bank` | nested | **нет** |
| 8889–8933 | `get_user_router.partner_requisite_value` | nested | **нет** |
| 8937–8966 | `get_user_router.partner_requisite_set_default` | nested | **нет** |
| 8970–8998 | `get_user_router.partner_requisite_delete` | nested | **нет** |
| 9002–9024 | `get_user_router.franchise_create_bot` | nested | **нет** |
| 9028–9037 | `get_user_router.franchise_cancel` | nested | **нет** |
| 9041–9100 | `get_user_router.franchise_receive_token` | nested | **нет** |
| 9104–9132 | `get_user_router.partner_cabinet` | nested | **нет** |
| 9136–9170 | `get_user_router.partner_withdraw` | nested | **нет** |
| 9174–9187 | `get_user_router.partner_withdraw_cancel` | nested | **нет** |
| 9191–9293 | `get_user_router.partner_withdraw_amount` | nested | **нет** |
| 9297–9402 | `notify_admin_of_purchase` | function | **нет** |
| 9404–10666 | `process_successful_payment` | function | есть: Обработать успешную оплату и выдать услугу. |
| 9415–9425 | `process_successful_payment._provider_ids_for_log` | nested | есть: Извлекает ID транзакции/инвойса на стороне платёжного провайдера из исходных |

## `src/shop_bot/bot/admin_handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 99–100 | `_is_true` | function | **нет** |
| 103–109 | `_mask_secret` | function | **нет** |
| 111–114 | `AdminSettings` | class | **нет** |
| 116–117 | `AdminModules` | class | **нет** |
| 119–127 | `Broadcast` | class | **нет** |
| 130–147 | `IsAdminFilter` | class | есть: Router-level gate for admin_router (aiogram 3.x BaseFilter). |
| 136–147 | `IsAdminFilter.__call__` | method | **нет** |
| 150–175 | `AdminAccessMiddleware` | class | есть: When a non-admin hits admin_router, answer the callback the same way |
| 156–175 | `AdminAccessMiddleware.__call__` | method | **нет** |
| 178–8996 | `get_admin_router` | function | **нет** |
| 186–200 | `get_admin_router._format_user_mention` | nested | **нет** |
| 203–220 | `get_admin_router._resolve_target_from_hash` | nested | **нет** |
| 222–258 | `get_admin_router.show_admin_menu` | nested | **нет** |
| 260–272 | `get_admin_router.show_admin_promo_menu` | nested | **нет** |
| 274–283 | `get_admin_router._parse_datetime_input` | nested | **нет** |
| 285–335 | `get_admin_router._format_promo_line` | nested | **нет** |
| 337–363 | `get_admin_router._build_promo_list_keyboard` | nested | **нет** |
| 365–378 | `get_admin_router.show_admin_system_menu` | nested | **нет** |
| 381–394 | `get_admin_router.show_admin_settings_menu` | nested | **нет** |
| 397–413 | `get_admin_router._build_modules_keyboard` | nested | **нет** |
| 415–450 | `get_admin_router.show_admin_modules_menu` | nested | **нет** |
| 454–459 | `get_admin_router.open_admin_menu_handler` | nested | **нет** |
| 461–466 | `get_admin_router.open_admin_system_menu_handler` | nested | **нет** |
| 470–475 | `get_admin_router.open_admin_settings_menu_handler` | nested | **нет** |
| 479–485 | `get_admin_router.open_admin_modules_menu_handler` | nested | **нет** |
| 488–493 | `get_admin_router.refresh_admin_modules_menu_handler` | nested | **нет** |
| 496–504 | `get_admin_router.admin_module_enable_handler` | nested | **нет** |
| 507–515 | `get_admin_router.admin_module_disable_handler` | nested | **нет** |
| 521–530 | `ButtonConstructor` | class | **нет** |
| 541–545 | `get_admin_router._btnc_menu_label` | nested | **нет** |
| 547–552 | `get_admin_router._btnc_cancel_kb` | nested | **нет** |
| 554–571 | `get_admin_router._btnc_show_menu_types` | nested | **нет** |
| 573–614 | `get_admin_router._btnc_build_list_kb` | nested | **нет** |
| 616–631 | `get_admin_router._btnc_show_list` | nested | **нет** |
| 633–645 | `get_admin_router._btnc_build_details_kb` | nested | **нет** |
| 647–687 | `get_admin_router._btnc_show_details` | nested | **нет** |
| 693–698 | `get_admin_router.admin_button_constructor_root` | nested | **нет** |
| 703–708 | `get_admin_router.btnc_select_menu_type` | nested | **нет** |
| 713–723 | `get_admin_router.btnc_open_list` | nested | **нет** |
| 728–740 | `get_admin_router.btnc_open_details` | nested | **нет** |
| 745–760 | `get_admin_router.btnc_toggle_active` | nested | **нет** |
| 765–784 | `get_admin_router.btnc_delete_confirm` | nested | **нет** |
| 789–802 | `get_admin_router.btnc_delete_do` | nested | **нет** |
| 807–809 | `get_admin_router.btnc_cancel_any` | nested | **нет** |
| 814–834 | `get_admin_router.btnc_action_menu` | nested | **нет** |
| 839–866 | `get_admin_router.btnc_edit_field_start` | nested | **нет** |
| 869–916 | `get_admin_router.btnc_edit_field_value` | nested | **нет** |
| 924–938 | `get_admin_router.btnc_add_start` | nested | **нет** |
| 941–954 | `get_admin_router.btnc_add_button_id` | nested | **нет** |
| 957–975 | `get_admin_router.btnc_add_text` | nested | **нет** |
| 980–992 | `get_admin_router.btnc_add_action_type` | nested | **нет** |
| 995–1026 | `get_admin_router.btnc_add_action_value` | nested | **нет** |
| 1029–1047 | `get_admin_router.btnc_add_row` | nested | **нет** |
| 1050–1071 | `get_admin_router.btnc_add_col` | nested | **нет** |
| 1076–1097 | `get_admin_router.btnc_add_width` | nested | **нет** |
| 1100–1123 | `get_admin_router.btnc_add_sort` | nested | **нет** |
| 1128–1160 | `get_admin_router.btnc_add_finish` | nested | **нет** |
| 1167–1168 | `AdminPayments` | class | **нет** |
| 1171–1212 | `get_admin_router._get_payments_status_for_admin` | nested | **нет** |
| 1215–1225 | `get_admin_router.show_admin_payments_menu` | nested | **нет** |
| 1228–1341 | `get_admin_router._payment_detail_text` | nested | **нет** |
| 1344–1353 | `get_admin_router.show_admin_payment_detail` | nested | **нет** |
| 1357–1363 | `get_admin_router.admin_payments_menu` | nested | **нет** |
| 1367–1375 | `get_admin_router.admin_payments_open` | nested | **нет** |
| 1379–1399 | `get_admin_router.admin_payments_toggle` | nested | **нет** |
| 1427–1468 | `get_admin_router._payment_prompt` | nested | **нет** |
| 1471–1475 | `get_admin_router._normalize_payment_input` | nested | **нет** |
| 1479–1501 | `get_admin_router.admin_payments_set` | nested | **нет** |
| 1505–1542 | `get_admin_router.admin_payments_set_value` | nested | **нет** |
| 1546–1583 | `get_admin_router.admin_payments_yoomoney_check` | nested | **нет** |
| 1593–1599 | `AdminReferral` | class | **нет** |
| 1602–1604 | `get_admin_router._get_bool_setting` | nested | **нет** |
| 1607–1613 | `get_admin_router._get_float_setting` | nested | **нет** |
| 1616–1627 | `get_admin_router._get_referral_settings_for_admin` | nested | **нет** |
| 1630–1637 | `get_admin_router._format_reward_type_human` | nested | **нет** |
| 1640–1669 | `get_admin_router.show_admin_referral_menu` | nested | **нет** |
| 1673–1679 | `get_admin_router.admin_referral_menu_entry` | nested | **нет** |
| 1683–1691 | `get_admin_router.admin_referral_toggle` | nested | **нет** |
| 1695–1703 | `get_admin_router.admin_referral_toggle_days_bonus` | nested | **нет** |
| 1707–1718 | `get_admin_router.admin_referral_set_type` | nested | **нет** |
| 1722–1739 | `get_admin_router.admin_referral_type_chosen` | nested | **нет** |
| 1743–1754 | `get_admin_router.admin_referral_set_percent` | nested | **нет** |
| 1758–1773 | `get_admin_router.admin_referral_percent_input` | nested | **нет** |
| 1777–1788 | `get_admin_router.admin_referral_set_fixed_amount` | nested | **нет** |
| 1792–1807 | `get_admin_router.admin_referral_fixed_amount_input` | nested | **нет** |
| 1811–1822 | `get_admin_router.admin_referral_set_start_bonus` | nested | **нет** |
| 1826–1843 | `get_admin_router.admin_referral_start_bonus_input` | nested | **нет** |
| 1847–1858 | `get_admin_router.admin_referral_set_min_withdrawal` | nested | **нет** |
| 1862–1877 | `get_admin_router.admin_referral_min_withdrawal_input` | nested | **нет** |
| 1881–1892 | `get_admin_router.admin_referral_set_discount` | nested | **нет** |
| 1896–1911 | `get_admin_router.admin_referral_discount_input` | nested | **нет** |
| 1916–1919 | `AdminFranchise` | class | **нет** |
| 1922–1929 | `get_admin_router._get_franchise_settings_for_admin` | nested | есть: Получает текущие настройки франшизы (только для админа) |
| 1932–1953 | `get_admin_router.show_admin_franchise_menu` | nested | есть: Отображает меню настроек франшизы (только для админа) |
| 1957–1965 | `get_admin_router.admin_franchise_menu_entry` | nested | есть: Точка входа в меню франшизы - ТОЛЬКО ДЛЯ АДМИНА |
| 1969–1993 | `get_admin_router.admin_franchise_toggle` | nested | есть: Переключает франшизу ВКЛ/ВЫКЛ - ТОЛЬКО ДЛЯ АДМИНА |
| 1996–2004 | `get_admin_router.admin_franchise_set_percent` | nested | есть: Установить процент комиссии франшизы |
| 2007–2025 | `get_admin_router.admin_franchise_percent_input` | nested | есть: Обработка ввода процента комиссии |
| 2028–2036 | `get_admin_router.admin_franchise_set_min_withdraw` | nested | есть: Установить минимум для вывода франшизников |
| 2039–2057 | `get_admin_router.admin_franchise_min_withdraw_input` | nested | есть: Обработка ввода минимума для вывода |
| 2064–2083 | `AdminHosts` | class | **нет** |
| 2086–2102 | `get_admin_router._resolve_host_from_digest` | nested | **нет** |
| 2105–2106 | `get_admin_router._safe` | nested | **нет** |
| 2109–2154 | `get_admin_router._format_host_card` | nested | **нет** |
| 2157–2167 | `get_admin_router.show_admin_hosts_menu` | nested | **нет** |
| 2170–2188 | `get_admin_router.show_admin_host_detail` | nested | **нет** |
| 2191–2208 | `get_admin_router.show_admin_host_squads` | nested | **нет** |
| 2212–2218 | `get_admin_router.admin_hosts_menu` | nested | **нет** |
| 2222–2233 | `get_admin_router.admin_hosts_add` | nested | **нет** |
| 2237–2250 | `get_admin_router.admin_hosts_add_name` | nested | **нет** |
| 2254–2267 | `get_admin_router.admin_hosts_add_base_url` | nested | **нет** |
| 2271–2284 | `get_admin_router.admin_hosts_add_api_token` | nested | **нет** |
| 2288–2335 | `get_admin_router.admin_hosts_add_squad_uuid` | nested | **нет** |
| 2342–2370 | `get_admin_router.admin_hosts_open` | nested | есть: Открыть карточку выбранного хоста. |
| 2376–2388 | `get_admin_router.admin_hosts_squads_open` | nested | **нет** |
| 2394–2420 | `get_admin_router.admin_hosts_squad_toggle` | nested | **нет** |
| 2426–2447 | `get_admin_router.admin_hosts_squad_delete` | nested | **нет** |
| 2451–2466 | `get_admin_router.admin_hosts_squad_add` | nested | **нет** |
| 2470–2490 | `get_admin_router.admin_hosts_squad_add_class` | nested | **нет** |
| 2494–2509 | `get_admin_router.admin_hosts_squad2_uuid` | nested | **нет** |
| 2513–2557 | `get_admin_router.admin_hosts_squad2_label` | nested | **нет** |
| 2561–2576 | `get_admin_router.admin_hosts_delete` | nested | **нет** |
| 2580–2597 | `get_admin_router.admin_hosts_delete_confirm` | nested | **нет** |
| 2601–2618 | `get_admin_router.admin_hosts_rename` | nested | **нет** |
| 2622–2659 | `get_admin_router.admin_hosts_toggle_class` | nested | есть: Переключение класса ноды: ♾ Unlimited <-> 💰 Premium (LTE). |
| 2663–2684 | `get_admin_router.admin_hosts_rename_input` | nested | **нет** |
| 2688–2704 | `get_admin_router.admin_hosts_set_url` | nested | **нет** |
| 2708–2728 | `get_admin_router.admin_hosts_set_url_input` | nested | **нет** |
| 2732–2749 | `get_admin_router.admin_hosts_set_sub` | nested | **нет** |
| 2753–2770 | `get_admin_router.admin_hosts_set_sub_input` | nested | **нет** |
| 2774–2790 | `get_admin_router.admin_hosts_set_rmw_url` | nested | **нет** |
| 2794–2814 | `get_admin_router.admin_hosts_set_rmw_url_input` | nested | **нет** |
| 2818–2835 | `get_admin_router.admin_hosts_set_rmw_token` | nested | **нет** |
| 2839–2856 | `get_admin_router.admin_hosts_set_rmw_token_input` | nested | **нет** |
| 2860–2876 | `get_admin_router.admin_hosts_set_squad` | nested | **нет** |
| 2880–2897 | `get_admin_router.admin_hosts_set_squad_input` | nested | **нет** |
| 2901–2921 | `get_admin_router.admin_hosts_set_ssh` | nested | **нет** |
| 2925–2982 | `get_admin_router.admin_hosts_set_ssh_input` | nested | **нет** |
| 2963–2965 | `get_admin_router.admin_hosts_set_ssh_input._n` | nested | **нет** |
| 2986–3006 | `get_admin_router.admin_hosts_to_plans` | nested | **нет** |
| 3011–3015 | `AdminTrial` | class | **нет** |
| 3018–3019 | `get_admin_router._get_trial_enabled` | nested | **нет** |
| 3022–3032 | `get_admin_router._format_trial_value_gb` | nested | **нет** |
| 3035–3041 | `get_admin_router._format_trial_value_int` | nested | **нет** |
| 3044–3054 | `get_admin_router._get_trial_days` | nested | **нет** |
| 3058–3095 | `get_admin_router.show_admin_trial_menu` | nested | **нет** |
| 3099–3106 | `get_admin_router.admin_trial_entry` | nested | **нет** |
| 3110–3118 | `get_admin_router.admin_trial_toggle` | nested | **нет** |
| 3122–3133 | `get_admin_router.admin_trial_set_days` | nested | **нет** |
| 3136–3148 | `get_admin_router.admin_trial_set_traffic` | nested | **нет** |
| 3151–3163 | `get_admin_router.admin_trial_set_devices` | nested | **нет** |
| 3166–3179 | `get_admin_router.admin_trial_set_host` | nested | **нет** |
| 3182–3191 | `get_admin_router.admin_trial_select_host` | nested | **нет** |
| 3194–3209 | `get_admin_router.admin_trial_days_input` | nested | **нет** |
| 3213–3232 | `get_admin_router.admin_trial_traffic_input` | nested | **нет** |
| 3236–3251 | `get_admin_router.admin_trial_devices_input` | nested | **нет** |
| 3256–3258 | `AdminLteSettings` | class | **нет** |
| 3261–3266 | `get_admin_router._get_dual_limit_interval` | nested | **нет** |
| 3269–3286 | `get_admin_router.show_admin_lte_settings_menu` | nested | **нет** |
| 3290–3297 | `get_admin_router.admin_lte_settings_entry` | nested | **нет** |
| 3301–3312 | `get_admin_router.admin_lte_set_interval_start` | nested | **нет** |
| 3316–3330 | `get_admin_router.admin_lte_set_interval_received` | nested | **нет** |
| 3337–3340 | `AdminNotifications` | class | **нет** |
| 3342–3343 | `get_admin_router._get_inactive_reminder_enabled` | nested | **нет** |
| 3345–3355 | `get_admin_router._get_inactive_reminder_interval_hours` | nested | **нет** |
| 3357–3359 | `get_admin_router._get_inactive_reminder_support_url` | nested | **нет** |
| 3361–3390 | `get_admin_router.show_admin_notifications_menu` | nested | **нет** |
| 3394–3401 | `get_admin_router.admin_notifications_entry` | nested | **нет** |
| 3405–3413 | `get_admin_router.admin_inactive_reminder_toggle` | nested | **нет** |
| 3417–3430 | `get_admin_router.admin_inactive_reminder_set_interval` | nested | **нет** |
| 3434–3451 | `get_admin_router.admin_inactive_reminder_interval_input` | nested | **нет** |
| 3455–3469 | `get_admin_router.admin_inactive_reminder_set_support_url` | nested | **нет** |
| 3473–3494 | `get_admin_router.admin_inactive_reminder_support_url_input` | nested | **нет** |
| 3499–3530 | `AdminPlans` | class | **нет** |
| 3536–3548 | `get_admin_router._format_plan_duration` | nested | есть: Человекочитаемый срок тарифа. |
| 3550–3564 | `get_admin_router._format_traffic_gb` | nested | **нет** |
| 3566–3576 | `get_admin_router._format_devices` | nested | **нет** |
| 3578–3584 | `get_admin_router._plan_show_name_enabled` | nested | **нет** |
| 3586–3607 | `get_admin_router._format_plans_for_host` | nested | **нет** |
| 3611–3623 | `get_admin_router.admin_plans_entry` | nested | **нет** |
| 3627–3633 | `get_admin_router.admin_plans_back_to_admin` | nested | **нет** |
| 3637–3649 | `get_admin_router.admin_plans_pick_host` | nested | **нет** |
| 3652–3682 | `get_admin_router._format_plan_detail` | nested | **нет** |
| 3688–3719 | `get_admin_router.admin_plans_open_plan` | nested | есть: Открыть конкретный тариф из списка тарифов хоста. |
| 3722–3742 | `get_admin_router._format_traffic_package_detail` | nested | **нет** |
| 3746–3775 | `get_admin_router.admin_plan_packages_menu` | nested | **нет** |
| 3779–3810 | `get_admin_router.admin_lte_packages_menu` | nested | **нет** |
| 3814–3823 | `get_admin_router.admin_plan_edit_lte_limit_start` | nested | **нет** |
| 3827–3869 | `get_admin_router.admin_plan_edit_lte_limit_received` | nested | **нет** |
| 3873–3883 | `get_admin_router.admin_plan_edit_main_reset_price_start` | nested | **нет** |
| 3887–3928 | `get_admin_router.admin_plan_edit_main_reset_price_received` | nested | **нет** |
| 3932–3956 | `get_admin_router.admin_pkg_add_start` | nested | **нет** |
| 3960–3973 | `get_admin_router.admin_pkg_size_received` | nested | **нет** |
| 3977–4002 | `get_admin_router.admin_pkg_price_received` | nested | **нет** |
| 4006–4027 | `get_admin_router.admin_pkg_open` | nested | **нет** |
| 4031–4040 | `get_admin_router.admin_pkg_edit_size_start` | nested | **нет** |
| 4044–4066 | `get_admin_router.admin_pkg_edit_size_received` | nested | **нет** |
| 4070–4079 | `get_admin_router.admin_pkg_edit_price_start` | nested | **нет** |
| 4083–4105 | `get_admin_router.admin_pkg_edit_price_received` | nested | **нет** |
| 4109–4131 | `get_admin_router.admin_pkg_toggle` | nested | **нет** |
| 4135–4153 | `get_admin_router.admin_pkg_delete` | nested | **нет** |
| 4158–4168 | `get_admin_router.admin_plan_edit_name` | nested | **нет** |
| 4172–4183 | `get_admin_router.admin_plan_edit_months` | nested | **нет** |
| 4187–4197 | `get_admin_router.admin_plan_edit_price` | nested | **нет** |
| 4202–4212 | `get_admin_router.admin_plan_edit_duration` | nested | **нет** |
| 4216–4223 | `get_admin_router.admin_plan_duration_months` | nested | **нет** |
| 4227–4234 | `get_admin_router.admin_plan_duration_days` | nested | **нет** |
| 4238–4248 | `get_admin_router.admin_plan_edit_traffic` | nested | **нет** |
| 4252–4262 | `get_admin_router.admin_plan_edit_devices` | nested | **нет** |
| 4266–4291 | `get_admin_router.admin_plan_toggle_active` | nested | **нет** |
| 4295–4327 | `get_admin_router.admin_plan_toggle_show_name` | nested | **нет** |
| 4331–4341 | `get_admin_router.admin_plan_delete_start` | nested | **нет** |
| 4345–4347 | `get_admin_router.admin_plan_delete_cancel` | nested | **нет** |
| 4351–4380 | `get_admin_router.admin_plan_delete_confirm` | nested | **нет** |
| 4384–4408 | `get_admin_router.admin_plan_edit_name_received` | nested | **нет** |
| 4412–4441 | `get_admin_router.admin_plan_edit_months_received` | nested | **нет** |
| 4445–4474 | `get_admin_router.admin_plan_edit_price_received` | nested | **нет** |
| 4479–4515 | `get_admin_router.admin_plan_edit_days_received` | nested | **нет** |
| 4519–4560 | `get_admin_router.admin_plan_edit_traffic_received` | nested | **нет** |
| 4564–4603 | `get_admin_router.admin_plan_edit_devices_received` | nested | **нет** |
| 4607–4618 | `get_admin_router.admin_plans_back_to_hosts` | nested | **нет** |
| 4622–4641 | `get_admin_router.admin_plans_add_start` | nested | **нет** |
| 4646–4657 | `get_admin_router.admin_plans_new_duration_months` | nested | **нет** |
| 4661–4672 | `get_admin_router.admin_plans_new_duration_days` | nested | **нет** |
| 4675–4697 | `get_admin_router.admin_plans_back_to_host_menu` | nested | **нет** |
| 4701–4723 | `get_admin_router.admin_plans_plan_name_received` | nested | **нет** |
| 4727–4752 | `get_admin_router.admin_plans_months_received` | nested | **нет** |
| 4757–4776 | `get_admin_router.admin_plan_add_days_received` | nested | **нет** |
| 4780–4803 | `get_admin_router.admin_plan_add_traffic_received` | nested | **нет** |
| 4807–4827 | `get_admin_router.admin_plan_add_devices_received` | nested | **нет** |
| 4830–4888 | `get_admin_router.admin_plans_price_received` | nested | **нет** |
| 4891–4903 | `AdminPromoCreate` | class | **нет** |
| 4906–4912 | `get_admin_router.admin_promo_menu_handler` | nested | **нет** |
| 4915–4925 | `get_admin_router.admin_promo_create_start` | nested | **нет** |
| 4931–4950 | `get_admin_router.admin_promo_code_auto` | nested | **нет** |
| 4956–4965 | `get_admin_router.admin_promo_code_custom` | nested | **нет** |
| 4968–4984 | `get_admin_router.admin_promo_create_code` | nested | **нет** |
| 4990–4999 | `get_admin_router.admin_promo_set_discount_type` | nested | **нет** |
| 5002–5024 | `get_admin_router.admin_promo_set_discount_value` | nested | **нет** |
| 5027–5047 | `get_admin_router.admin_promo_set_total_limit` | nested | **нет** |
| 5053–5071 | `get_admin_router.admin_promo_total_limit_buttons` | nested | **нет** |
| 5077–5095 | `get_admin_router.admin_promo_user_limit_buttons` | nested | **нет** |
| 5098–5118 | `get_admin_router.admin_promo_set_per_user_limit` | nested | **нет** |
| 5121–5135 | `get_admin_router.admin_promo_set_valid_from` | nested | **нет** |
| 5147–5172 | `get_admin_router.admin_promo_valid_from_buttons` | nested | **нет** |
| 5175–5194 | `get_admin_router.admin_promo_set_valid_until` | nested | **нет** |
| 5206–5233 | `get_admin_router.admin_promo_valid_until_buttons` | nested | **нет** |
| 5236–5246 | `get_admin_router.admin_promo_description` | nested | **нет** |
| 5252–5269 | `get_admin_router.admin_promo_desc_buttons` | nested | **нет** |
| 5271–5317 | `get_admin_router._show_promo_confirm` | nested | **нет** |
| 5327–5353 | `get_admin_router.admin_promo_set_segment` | nested | **нет** |
| 5356–5373 | `get_admin_router.admin_promo_set_segment_value` | nested | **нет** |
| 5379–5391 | `get_admin_router.admin_promo_set_plans` | nested | **нет** |
| 5394–5409 | `get_admin_router.admin_promo_set_plans_custom` | nested | **нет** |
| 5412–5458 | `get_admin_router.admin_promo_confirm` | nested | **нет** |
| 5461–5478 | `get_admin_router.admin_promo_list` | nested | **нет** |
| 5481–5503 | `get_admin_router.admin_promo_change_page` | nested | **нет** |
| 5506–5532 | `get_admin_router.admin_promo_toggle` | nested | **нет** |
| 5536–5552 | `get_admin_router.admin_speedtest_entry` | nested | **нет** |
| 5556–5571 | `get_admin_router.admin_speedtest_ssh_targets` | nested | **нет** |
| 5575–5659 | `get_admin_router.admin_speedtest_run` | nested | **нет** |
| 5609–5622 | `get_admin_router.admin_speedtest_run.fmt_part` | nested | **нет** |
| 5663–5730 | `get_admin_router.admin_speedtest_run_target_hashed` | nested | **нет** |
| 5734–5801 | `get_admin_router.admin_speedtest_run_target` | nested | **нет** |
| 5805–5810 | `get_admin_router.admin_speedtest_back` | nested | **нет** |
| 5814–5855 | `get_admin_router.admin_speedtest_run_all` | nested | **нет** |
| 5859–5905 | `get_admin_router.admin_speedtest_run_all_targets` | nested | **нет** |
| 5909–5937 | `get_admin_router.admin_backup_db` | nested | **нет** |
| 5940–5941 | `AdminRestoreDB` | class | **нет** |
| 5944–5961 | `get_admin_router.admin_restore_db_prompt` | nested | **нет** |
| 5964–5988 | `get_admin_router.admin_restore_db_receive` | nested | **нет** |
| 5992–6013 | `get_admin_router.admin_speedtest_autoinstall` | nested | **нет** |
| 6017–6045 | `get_admin_router.admin_speedtest_autoinstall_target` | nested | **нет** |
| 6049–6075 | `get_admin_router.admin_speedtest_autoinstall_target_hashed` | nested | **нет** |
| 6081–6082 | `AdminUserSearch` | class | **нет** |
| 6085–6113 | `get_admin_router.admin_users_handler` | nested | **нет** |
| 6117–6202 | `get_admin_router.admin_users_search_process` | nested | **нет** |
| 6205–6247 | `get_admin_router.admin_view_user_handler` | nested | **нет** |
| 6251–6328 | `get_admin_router.admin_ban_user` | nested | **нет** |
| 6332–6340 | `get_admin_router.admin_admins_menu_entry` | nested | **нет** |
| 6343–6378 | `get_admin_router.admin_view_admins` | nested | **нет** |
| 6381–6439 | `get_admin_router.admin_unban_user` | nested | **нет** |
| 6444–6464 | `get_admin_router.admin_delete_user` | nested | **нет** |
| 6467–6491 | `get_admin_router.admin_user_keys` | nested | **нет** |
| 6494–6539 | `get_admin_router.admin_user_referrals` | nested | **нет** |
| 6542–6562 | `get_admin_router.admin_search_user_keys_handler` | nested | **нет** |
| 6565–6603 | `get_admin_router.admin_search_user_keys_input_handler` | nested | **нет** |
| 6606–6631 | `get_admin_router.admin_search_keys_page_handler` | nested | **нет** |
| 6634–6647 | `get_admin_router.admin_search_all_keys_handler` | nested | **нет** |
| 6650–6679 | `get_admin_router.admin_search_all_keys_input_handler` | nested | **нет** |
| 6682–6693 | `get_admin_router.admin_cancel_search_keys_handler` | nested | **нет** |
| 6696–6728 | `get_admin_router.admin_edit_key` | nested | **нет** |
| 6733–6760 | `get_admin_router.admin_key_delete_prompt` | nested | **нет** |
| 6763–6764 | `AdminExtendSingleKey` | class | **нет** |
| 6767–6783 | `get_admin_router.admin_key_extend_prompt` | nested | **нет** |
| 6786–6843 | `get_admin_router.admin_key_extend_process` | nested | **нет** |
| 6846–6847 | `AdminAddAdmin` | class | **нет** |
| 6850–6860 | `get_admin_router.admin_add_admin_entry` | nested | **нет** |
| 6863–6921 | `get_admin_router.admin_add_admin_process` | nested | **нет** |
| 6924–6925 | `AdminRemoveAdmin` | class | **нет** |
| 6928–6938 | `get_admin_router.admin_remove_admin_entry` | nested | **нет** |
| 6941–7009 | `get_admin_router.admin_remove_admin_process` | nested | **нет** |
| 7013–7047 | `get_admin_router.admin_key_delete_cancel` | nested | **нет** |
| 7051–7118 | `get_admin_router.admin_key_delete_confirm` | nested | **нет** |
| 7120–7121 | `AdminEditKeyEmail` | class | **нет** |
| 7124–7139 | `get_admin_router.admin_key_edit_email_start` | nested | **нет** |
| 7142–7156 | `get_admin_router.admin_key_edit_email_commit` | nested | **нет** |
| 7161–7164 | `AdminGiftKey` | class | **нет** |
| 7167–7178 | `get_admin_router.admin_gift_key_entry` | nested | **нет** |
| 7182–7199 | `get_admin_router.admin_gift_key_for_user` | nested | **нет** |
| 7202–7215 | `get_admin_router.admin_gift_pick_user_page` | nested | **нет** |
| 7218–7234 | `get_admin_router.admin_gift_pick_user` | nested | **нет** |
| 7237–7247 | `get_admin_router.admin_gift_back_to_users` | nested | **нет** |
| 7250–7261 | `get_admin_router.admin_gift_pick_host` | nested | **нет** |
| 7264–7276 | `get_admin_router.admin_gift_back_to_hosts` | nested | **нет** |
| 7278–7344 | `get_admin_router.admin_gift_pick_days` | nested | **нет** |
| 7349–7351 | `AdminMainRefill` | class | **нет** |
| 7354–7363 | `get_admin_router.admin_add_balance_entry` | nested | **нет** |
| 7366–7381 | `get_admin_router.admin_add_balance_user` | nested | **нет** |
| 7385–7398 | `get_admin_router.admin_add_balance_pick_user_page` | nested | **нет** |
| 7402–7417 | `get_admin_router.admin_add_balance_pick_user` | nested | **нет** |
| 7420–7446 | `get_admin_router.handle_main_amount` | nested | **нет** |
| 7450–7485 | `get_admin_router.admin_key_back` | nested | **нет** |
| 7489–7490 | `get_admin_router.admin_noop` | nested | **нет** |
| 7493–7496 | `get_admin_router.admin_cancel_handler` | nested | **нет** |
| 7499–7500 | `AdminMainDeduct` | class | **нет** |
| 7504–7513 | `get_admin_router.admin_deduct_balance_entry` | nested | **нет** |
| 7517–7532 | `get_admin_router.admin_deduct_balance_user` | nested | **нет** |
| 7536–7549 | `get_admin_router.admin_deduct_balance_pick_user_page` | nested | **нет** |
| 7553–7568 | `get_admin_router.admin_deduct_balance_pick_user` | nested | **нет** |
| 7571–7601 | `get_admin_router.handle_deduct_amount` | nested | **нет** |
| 7604–7605 | `AdminHostKeys` | class | **нет** |
| 7608–7619 | `get_admin_router.admin_host_keys_entry` | nested | **нет** |
| 7622–7637 | `get_admin_router.admin_host_keys_pick_host` | nested | **нет** |
| 7640–7663 | `get_admin_router.admin_hostkeys_page` | nested | **нет** |
| 7666–7680 | `get_admin_router.admin_hostkeys_back_to_hosts` | nested | **нет** |
| 7683–7688 | `get_admin_router.admin_hostkeys_back_to_users` | nested | **нет** |
| 7691–7692 | `AdminQuickDeleteKey` | class | **нет** |
| 7695–7704 | `get_admin_router.admin_delete_key_entry` | nested | **нет** |
| 7707–7729 | `get_admin_router.admin_delete_key_process` | nested | **нет** |
| 7732–7733 | `AdminExtendKey` | class | **нет** |
| 7736–7745 | `get_admin_router.admin_extend_key_entry` | nested | **нет** |
| 7748–7796 | `get_admin_router.admin_extend_key_process` | nested | **нет** |
| 7799–7810 | `get_admin_router.start_broadcast_handler` | nested | **нет** |
| 7813–7864 | `get_admin_router.broadcast_message_received_handler` | nested | **нет** |
| 7817–7822 | `get_admin_router.broadcast_message_received_handler._msg_json_default` | nested | **нет** |
| 7826–7832 | `get_admin_router.broadcast_message_received_handler._detect_parse_mode` | nested | есть: Auto-detect parse mode: HTML tags → HTML, Markdown links/bold/etc → MarkdownV2. |
| 7870–7879 | `get_admin_router.broadcast_parse_mode_handler` | nested | **нет** |
| 7883–7889 | `get_admin_router.add_button_choose_type` | nested | **нет** |
| 7892–7898 | `get_admin_router.add_button_prompt_handler` | nested | **нет** |
| 7901–7907 | `get_admin_router.add_functional_button_start` | nested | **нет** |
| 7910–7915 | `get_admin_router.functional_button_selected` | nested | **нет** |
| 7919–7925 | `get_admin_router.button_text_received_handler` | nested | **нет** |
| 7928–7936 | `get_admin_router.button_url_received_handler` | nested | **нет** |
| 7939–7942 | `get_admin_router.skip_button_handler` | nested | **нет** |
| 7944–7967 | `get_admin_router._escape_md2` | nested | есть: Escape MarkdownV2 special chars in plain-text parts, leaving inline entities intact. |
| 7958–7959 | `get_admin_router._escape_md2._esc` | nested | **нет** |
| 7969–8004 | `get_admin_router._send_broadcast_to` | nested | есть: Send broadcast, using specific send methods for media so reply_markup is applied correctly. |
| 8006–8036 | `get_admin_router.show_broadcast_preview` | nested | **нет** |
| 8039–8106 | `get_admin_router.confirm_broadcast_handler` | nested | **нет** |
| 8109–8112 | `get_admin_router.cancel_broadcast_handler` | nested | **нет** |
| 8116–8134 | `get_admin_router.approve_withdraw_handler` | nested | **нет** |
| 8137–8148 | `get_admin_router.decline_withdraw_handler` | nested | **нет** |
| 8152–8183 | `get_admin_router.admin_monitor_menu` | nested | **нет** |
| 8186–8354 | `get_admin_router.admin_monitor_local` | nested | **нет** |
| 8357–8462 | `get_admin_router.admin_monitor_host` | nested | **нет** |
| 8465–8592 | `get_admin_router.admin_monitor_target` | nested | **нет** |
| 8595–8723 | `get_admin_router.admin_monitor_detailed` | nested | **нет** |
| 8730–8764 | `get_admin_router.admin_captcha_settings_handler` | nested | есть: Показать страницу настроек капчи. |
| 8767–8778 | `get_admin_router.admin_captcha_toggle_handler` | nested | есть: Включить/отключить капчу. |
| 8781–8803 | `get_admin_router.admin_captcha_type_handler` | nested | есть: Выбрать тип капчи. |
| 8806–8817 | `get_admin_router.admin_captcha_type_set_handler` | nested | есть: Установить тип капчи. |
| 8820–8831 | `get_admin_router.admin_captcha_attempts_handler` | nested | есть: Установить максимальное количество попыток. |
| 8834–8850 | `get_admin_router.admin_captcha_attempts_input_handler` | nested | есть: Обработать ввод количества попыток. |
| 8853–8864 | `get_admin_router.admin_captcha_timeout_handler` | nested | есть: Установить timeout капчи. |
| 8867–8883 | `get_admin_router.admin_captcha_timeout_input_handler` | nested | есть: Обработать ввод timeout. |
| 8886–8897 | `get_admin_router.admin_captcha_message_handler` | nested | есть: Установить кастомное сообщение к капче. |
| 8900–8913 | `get_admin_router.admin_captcha_message_input_handler` | nested | есть: Обработать ввод сообщения. |
| 8919–8920 | `AdminAutoRenew` | class | **нет** |
| 8922–8944 | `get_admin_router.show_admin_auto_renew_menu` | nested | **нет** |
| 8947–8954 | `get_admin_router.admin_auto_renew_entry` | nested | **нет** |
| 8957–8966 | `get_admin_router.admin_auto_renew_toggle` | nested | **нет** |
| 8969–8977 | `get_admin_router.admin_auto_renew_set_hours` | nested | **нет** |
| 8980–8994 | `get_admin_router.admin_auto_renew_hours_input` | nested | **нет** |

## `src/shop_bot/data_manager/database.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 35–36 | `_now_str` | function | **нет** |
| 39–47 | `add_calendar_months` | function | есть: Добавляет календарные месяцы к дате, корректно обрабатывая переполнение дней |
| 50–53 | `compute_next_traffic_reset_str` | function | есть: Возвращает строку даты/времени следующего ежемесячного сброса трафика (сейчас + 1 месяц). |
| 56–68 | `add_months` | function | есть: Прибавляет к дате календарные месяцы (без внешних зависимостей вроде dateutil). |
| 71–74 | `compute_next_traffic_reset` | function | есть: Возвращает строку даты следующего ежемесячного сброса трафика (текущий момент + 1 месяц). |
| 77–82 | `_as_limit_bytes` | function | **нет** |
| 85–86 | `plan_main_limit_bytes` | function | **нет** |
| 89–90 | `plan_lte_limit_bytes` | function | **нет** |
| 93–114 | `should_account_lte_traffic` | function | есть: LTE-учёт (снапшоты, baseline, энфорс) только при лимите и живом скваде. |
| 117–119 | `plan_has_monthly_traffic_reset` | function | есть: Ежемесячный сброс нужен, если ограничен основной пул и/или LTE. |
| 122–128 | `remnawave_traffic_limit_strategy_for_plan` | function | есть: Стратегия Remnawave относится только к ОСНОВНОМУ пулу. |
| 131–140 | `parse_plan_id_from_key` | function | **нет** |
| 143–158 | `key_is_unbilled_trial_or_gift` | function | **нет** |
| 161–182 | `resolve_plan_for_key` | function | есть: Тариф ключа: plan_id из description, иначе первый активный тариф хоста. |
| 185–193 | `format_next_traffic_reset_display` | function | есть: Дата ближайшего сброса для карточки ключа (`ДД.ММ.ГГГГ`) либо None. |
| 196–224 | `compute_aligned_next_traffic_reset` | function | есть: Следующий сброс, согласованный с текущим rolling-окном ключа. |
| 227–234 | `_to_datetime_str` | function | **нет** |
| 237–241 | `_normalize_email` | function | **нет** |
| 244–270 | `_normalize_key_row` | function | **нет** |
| 273–275 | `_get_table_columns` | function | **нет** |
| 278–281 | `_ensure_table_column` | function | **нет** |
| 284–285 | `_ensure_unique_index` | function | **нет** |
| 288–289 | `_ensure_index` | function | **нет** |
| 292–297 | `normalize_host_name` | function | есть: Normalize host name by trimming and removing invisible/unicode spaces. |
| 300–891 | `initialize_db` | function | **нет** |
| 894–916 | `_ensure_users_columns` | function | **нет** |
| 919–943 | `_ensure_email_verification_columns` | function | есть: Добавляет поля для активации email (подтверждение владения адресом при веб-регистрации). |
| 946–973 | `_ensure_hosts_columns` | function | **нет** |
| 976–990 | `_ensure_plans_columns` | function | **нет** |
| 993–1014 | `_ensure_traffic_packages_table` | function | **нет** |
| 1017–1043 | `_ensure_key_node_usage_snapshots_table` | function | есть: Расход ключа по КОНКРЕТНЫМ нодам за расчётный период. |
| 1046–1076 | `resolve_key_period_start` | function | есть: Начало текущего расчётного периода ключа в формате '%Y-%m-%d %H:%M:%S'. |
| 1079–1121 | `upsert_key_node_usage_snapshot` | function | есть: Записать/обновить расход ключа по одной ноде за период (идемпотентно по |
| 1124–1150 | `get_node_usage_for_key` | function | есть: Разбивка расхода ключа по нодам за период (по убыванию расхода). |
| 1153–1163 | `delete_node_usage_for_key` | function | есть: Удалить все снапшоты ключа (используется при удалении ключа). |
| 1166–1194 | `_ensure_subscription_lte_table` | function | есть: Отдельный (независимый от основного) пул трафика LTE для «премиум»-нод. |
| 1197–1221 | `_ensure_key_lte_state_table` | function | есть: Состояние LTE-пула НА КЛЮЧ (пришло на смену пользовательскому `subscription_lte`). |
| 1224–1326 | `_migrate_subscription_lte_to_keys` | function | есть: Перенести пользовательское состояние LTE на ключи (однократно для каждой строки). |
| 1329–1409 | `_ensure_host_squads_table` | function | есть: Классифицированные сквады хоста: 'base' (∞), 'lte' (💰) или 'other'. |
| 1412–1449 | `add_host_squad` | function | есть: Добавить сквад к хосту с классификацией ('base' \| 'lte' \| 'other'). |
| 1452–1467 | `get_host_squads` | function | **нет** |
| 1470–1493 | `get_squad_by_class` | function | есть: Быстрый доступ к активному сквада заданного класса ('base'/'lte'/'other') хоста. |
| 1500–1517 | `squad_display_label` | function | есть: Публичная метка сквада: поле `label`, если заполнено, иначе fallback. |
| 1520–1528 | `get_lte_squad_display_label` | function | есть: Метка активного LTE-сквада хоста — то, что видит пользователь вместо «LTE». |
| 1531–1543 | `set_host_squad_active` | function | **нет** |
| 1546–1555 | `delete_host_squad` | function | **нет** |
| 1558–1625 | `_ensure_remnawave_squads_catalog` | function | есть: Глобальный каталог сквадов Remnawave (выбираются галочками на хостах). |
| 1628–1641 | `get_remnawave_squads` | function | **нет** |
| 1644–1668 | `add_remnawave_squad` | function | **нет** |
| 1671–1692 | `delete_remnawave_squad` | function | **нет** |
| 1695–1732 | `seed_global_remnawave_from_hosts` | function | есть: Если глобальные Remnawave-настройки пусты — взять из первого хоста. |
| 1735–1764 | `apply_global_remnawave_to_hosts` | function | есть: Синхронизировать глобальные Remnawave URL/token/subscription на все хосты. |
| 1767–1851 | `set_host_squads_from_catalog` | function | есть: Выставить привязку хоста к сквадам каталога (галочки). Синхронизирует host_squads и squad_uuid. |
| 1854–1873 | `get_host_selected_squad_catalog_ids` | function | есть: ID записей каталога, привязанных к хосту через host_squads.uuid. |
| 1876–1882 | `_ensure_support_tickets_columns` | function | **нет** |
| 1885–1891 | `_ensure_key_usage_monitor_columns` | function | **нет** |
| 1894–1899 | `_finalize_vpn_key_indexes` | function | **нет** |
| 1902–2002 | `_rebuild_vpn_keys_table` | function | **нет** |
| 1936–1937 | `_rebuild_vpn_keys_table.has` | nested | **нет** |
| 1939–1940 | `_rebuild_vpn_keys_table.col` | nested | **нет** |
| 2005–2034 | `_ensure_vpn_keys_schema` | function | **нет** |
| 2037–2049 | `_migrate_gift_tags` | function | есть: Обновить старые теги 'gift' и 'GIFT' на новый стандарт 'user_gift'. |
| 2053–2129 | `run_migration` | function | **нет** |
| 2132–2165 | `insert_resource_metric` | function | **нет** |
| 2168–2186 | `get_latest_resource_metric` | function | **нет** |
| 2189–2227 | `get_metrics_series` | function | **нет** |
| 2230–2257 | `create_host` | function | **нет** |
| 2259–2278 | `update_host_subscription_url` | function | **нет** |
| 2280–2306 | `claim_referral_start_bonus` | function | есть: Атомарно пометить, что приглашённый получил стартовый реферальный бонус. |
| 2309–2315 | `set_referral_start_bonus_received` | function | есть: Пометить, что пользователь получил стартовый бонус за реферальную регистрацию. |
| 2318–2333 | `set_referral_trial_day_bonus_received` | function | есть: Пометить, что за данного пользователя уже начислялся +1 день рефереру за активацию триала. |
| 2335–2355 | `update_host_url` | function | есть: Обновить URL панели XUI для указанного хоста. |
| 2357–2401 | `update_host_remnawave_settings` | function | есть: Обновить Remnawave-настройки на уровне конкретного хоста. |
| 2404–2418 | `get_host_class` | function | есть: Класс ноды: 'premium' (💰) или 'unlim' (∞, по умолчанию). |
| 2421–2438 | `set_host_class` | function | есть: Устанавливает класс ноды ('premium'/'unlim') и её значок (по умолчанию 💰/∞). |
| 2441–2467 | `set_host_squad_overlap` | function | есть: Сохранить результат проверки пересечения нод LTE- и base-сквадов хоста. |
| 2470–2488 | `get_host_squad_overlap` | function | есть: Ноды, доступные и через LTE-, и через base-сквад хоста (по последней проверке). |
| 2491–2504 | `list_hosts_by_class` | function | **нет** |
| 2507–2549 | `update_host_name` | function | есть: Переименовать хост во всех связанных таблицах (xui_hosts, plans, vpn_keys, host_squads). |
| 2551–2567 | `delete_host` | function | **нет** |
| 2569–2577 | `_decrypt_row_secrets` | function | есть: Расшифровать at-rest поля (enc1$ / legacy plaintext) в копии строки. |
| 2580–2591 | `get_host` | function | **нет** |
| 2593–2632 | `update_host_ssh_settings` | function | есть: Обновить SSH-параметры для speedtest/maintenance по хосту. |
| 2634–2650 | `delete_key_by_id` | function | **нет** |
| 2652–2661 | `update_key_comment` | function | **нет** |
| 2664–2697 | `update_key_name` | function | есть: Обновить пользовательское название ключа. |
| 2700–2716 | `get_all_hosts` | function | **нет** |
| 2718–2744 | `get_speedtests` | function | есть: Получить последние результаты спидтестов по хосту (ssh/net), новые сверху. |
| 2746–2768 | `get_latest_speedtest` | function | есть: Получить последний по времени спидтест для хоста. |
| 2770–2813 | `insert_host_speedtest` | function | есть: Сохранить результат спидтеста в таблицу host_speedtests. |
| 2817–2846 | `_ensure_ssh_targets_table` | function | есть: Миграция: создать таблицу speedtest_ssh_targets при необходимости и добавить недостающие столбцы. |
| 2849–2860 | `_ensure_ssh_known_hosts_table` | function | **нет** |
| 2863–2878 | `get_ssh_known_host_key` | function | **нет** |
| 2881–2902 | `save_ssh_known_host_key` | function | **нет** |
| 2905–2938 | `_ensure_gift_tokens_table` | function | есть: Миграция для таблиц подарочных токенов. |
| 2941–2962 | `_ensure_user_gifts_table` | function | есть: Миграция для таблицы неактивированных пользовательских подарков. |
| 2965–2991 | `_ensure_auth_pending_actions_table` | function | есть: Миграция для таблицы pending action — единого механизма "открыл ссылку |
| 2997–3028 | `create_pending_action` | function | есть: Создать pending action и вернуть одноразовый случайный токен. |
| 3031–3046 | `get_pending_action` | function | есть: Вернуть запись pending action по токену как есть (включая уже |
| 3049–3074 | `claim_pending_action` | function | есть: Атомарно "забрать" pending action для указанного пользователя. |
| 3077–3093 | `set_pending_action_result` | function | есть: Сохранить итоговый статус применения действия — чтобы повторный вызов |
| 3096–3111 | `cleanup_expired_pending_actions` | function | есть: Удалить давно истёкшие pending actions (профилактическая очистка, |
| 3114–3175 | `_ensure_promo_tables` | function | есть: Создание таблиц промокодов и истории их использования. |
| 3178–3284 | `_ensure_analytics_tables` | function | есть: Таблицы для раздела админки «Продажи и аналитика». |
| 3287–3298 | `get_all_ssh_targets` | function | есть: Вернуть все SSH-цели для спидтестов (включая неактивные), сортировка по sort_order, затем по имени. |
| 3301–3312 | `get_ssh_target` | function | **нет** |
| 3315–3353 | `create_ssh_target` | function | **нет** |
| 3356–3420 | `update_ssh_target_fields` | function | **нет** |
| 3423–3434 | `delete_ssh_target` | function | **нет** |
| 3436–3513 | `get_admin_stats` | function | есть: Return aggregated statistics for the admin dashboard. |
| 3528–3648 | `get_sales_overview` | function | есть: Главный дашборд продаж (Этап 4.1 плана): выручка/транзакции/чек/плательщики |
| 3651–3674 | `get_revenue_series` | function | есть: Ряд выручки/транзакций по дням для графика раздела «Продажи и аналитика». |
| 3677–3726 | `get_plans_analytics` | function | есть: Аналитика по тарифам (Этап 4.4): выручка, продажи, средний чек, доля повторных покупок. |
| 3729–3759 | `get_payment_methods_analytics` | function | есть: Аналитика по методам оплаты (Этап 4.5): число транзакций, выручка, успешность, динамика. |
| 3762–3791 | `get_users_without_real_payment_with_keys` | function | есть: Пользователи с хотя бы одним VPN-ключом, у которых нет ни одной успешной |
| 3794–3875 | `get_trial_key_stats` | function | есть: Метрики по триальным ключам и их продлениям. |
| 3878–3938 | `get_referrals_analytics` | function | есть: Аналитика реферальной программы (Этап 6.1) поверх существующих полей/функций, |
| 3941–3979 | `get_top_referrers` | function | есть: Топ пользователей по рефералам: число приглашённых и число платящих рефералов. |
| 3982–4013 | `get_top_buyers` | function | есть: Топ пользователей по покупкам (Этап 6.4): сумма, число успешных транзакций, средний чек. |
| 4016–4027 | `_promo_plans_label` | function | есть: Человекочитаемое ограничение тарифов для карточки купона в админке. |
| 4030–4043 | `_promo_segment_label` | function | есть: Человекочитаемое ограничение сегмента для карточки купона в админке. |
| 4046–4122 | `get_coupons_analytics` | function | есть: Аналитика купонов/промокодов (Этап 6.3) поверх существующих таблиц |
| 4125–4138 | `get_server_cost_entries` | function | **нет** |
| 4141–4180 | `create_server_cost_entry` | function | **нет** |
| 4183–4205 | `update_server_cost_entry` | function | **нет** |
| 4208–4217 | `delete_server_cost_entry` | function | **нет** |
| 4220–4256 | `get_economics_summary` | function | есть: Приблизительная экономика (Этап 7.3): расходы по провайдеру/локации, |
| 4259–4308 | `get_revenue_forecast` | function | есть: Прозрачный прогноз (Этап 4.6/9): скользящее среднее за 7 дней + линейная |
| 4311–4324 | `get_utm_links` | function | **нет** |
| 4327–4360 | `create_utm_link` | function | **нет** |
| 4363–4377 | `delete_utm_link` | function | есть: Удаляет UTM-метку вместе с накопленной статистикой посещений (utm_visits). |
| 4380–4391 | `log_utm_visit` | function | есть: Best-effort запись события UTM (клик/старт/регистрация/оплата). Никогда не бросает исключение наружу |
| 4394–4407 | `set_user_utm_slug_if_absent` | function | есть: First-touch атрибуция: записать utm_slug пользователю только если он ещё не задан. |
| 4410–4452 | `get_utm_analytics` | function | есть: Эффективность UTM-меток (Этап 5.4): клики, регистрации, оплаты, выручка, ROI (если задан budget). |
| 4459–4471 | `create_broadcast_campaign` | function | **нет** |
| 4474–4483 | `get_broadcast_campaigns` | function | **нет** |
| 4486–4496 | `get_broadcast_campaign` | function | **нет** |
| 4499–4511 | `update_broadcast_campaign` | function | **нет** |
| 4514–4532 | `toggle_broadcast_campaign` | function | есть: Flip is_active. Returns new is_active state. |
| 4535–4545 | `delete_broadcast_campaign` | function | **нет** |
| 4554–4561 | `is_email_only_user` | function | есть: True, если пользователь зарегистрирован по email и ещё не авторизовался |
| 4564–4588 | `get_inactive_subscribers` | function | есть: User IDs with no active keys (expire_at in the past or no keys at all), |
| 4591–4611 | `get_pending_broadcast_recipients` | function | есть: Inactive users who haven't been sent this campaign in the last `interval_hours`. |
| 4614–4633 | `record_broadcast_sends` | function | есть: Insert send records and bump campaign send_count. Returns count inserted. |
| 4636–4647 | `mark_broadcast_run` | function | есть: Update last_run_at even when there are no recipients (avoids tight retry loops). |
| 4650–4659 | `get_broadcast_stats` | function | **нет** |
| 4662–4671 | `get_all_keys` | function | **нет** |
| 4674–4683 | `get_all_key_ids` | function | есть: Все key_id из vpn_keys (без фильтров/пагинации) — для bulk-действий «всем». |
| 4686–4693 | `extend_key` | function | есть: Продлить/сократить срок ключа на N дней (с синхронизацией Remnawave). |
| 4696–4700 | `set_key_expiry` | function | есть: Установить точную дату истечения ключа (с синхронизацией Remnawave). |
| 4703–4760 | `get_keys_paginated` | function | **нет** |
| 4763–4764 | `get_keys_for_user` | function | **нет** |
| 4766–4768 | `update_key_email` | function | **нет** |
| 4770–4771 | `update_key_host` | function | **нет** |
| 4773–4794 | `create_gift_key` | function | есть: Создать подарочный ключ: expiry = now + months. |
| 4809–4821 | `get_setting` | function | **нет** |
| 4823–4860 | `get_admin_ids` | function | есть: Возвращает множество ID администраторов из настроек. |
| 4862–4867 | `is_admin` | function | есть: Проверка прав администратора по списку ID из настроек. |
| 4869–4880 | `_connect_pending_db` | function | есть: Connection helper for high-contention tables (webhooks/bot). |
| 4883–4891 | `_retry_sqlite` | function | **нет** |
| 4894–4907 | `_ensure_pending_tables` | function | **нет** |
| 4910–4918 | `_ensure_processed_payments_table` | function | **нет** |
| 4934–4941 | `_tx_meta_dict` | function | **нет** |
| 4944–4951 | `_provider_transaction_id_from_meta` | function | **нет** |
| 4954–5014 | `_mirror_pending_to_ledger` | function | есть: Дублирует неоплаченный счёт в ``transactions``, чтобы он был виден в истории. |
| 5017–5064 | `create_payload_pending` | function | есть: Create/update pending payload metadata. |
| 5027–5058 | `create_payload_pending._work` | nested | **нет** |
| 5067–5103 | `patch_pending_metadata` | function | есть: Дописывает поля (id провайдера) в pending и в зеркало ``transactions``. |
| 5073–5097 | `patch_pending_metadata._work` | nested | **нет** |
| 5106–5134 | `_get_pending_metadata` | function | **нет** |
| 5111–5128 | `_get_pending_metadata._work` | nested | **нет** |
| 5137–5139 | `get_pending_metadata` | function | есть: Public wrapper to fetch pending metadata by payment_id WITHOUT marking it paid. |
| 5142–5179 | `get_pending_record` | function | есть: Строка pending_transactions с любым статусом (pending/cancelled/paid). |
| 5148–5173 | `get_pending_record._work` | nested | **нет** |
| 5182–5218 | `revive_cancelled_invoice` | function | есть: Вернуть отменённый счёт в pending, если позже пришла реальная оплата. |
| 5188–5212 | `revive_cancelled_invoice._work` | nested | **нет** |
| 5221–5231 | `prepare_pending_for_fulfillment` | function | есть: Metadata для выдачи: отменённый счёт поднимаем, paid не трогаем. |
| 5234–5254 | `get_pending_status` | function | есть: Return status of pending transaction: 'pending', 'paid', or None if not found. |
| 5240–5248 | `get_pending_status._work` | nested | **нет** |
| 5257–5276 | `_complete_pending` | function | **нет** |
| 5262–5270 | `_complete_pending._work` | nested | **нет** |
| 5279–5331 | `find_and_complete_pending_transaction` | function | есть: Atomically mark pending transaction as paid and return its metadata. |
| 5288–5325 | `find_and_complete_pending_transaction._work` | nested | **нет** |
| 5334–5363 | `get_latest_pending_for_user` | function | есть: Return metadata of the most recent PENDING transaction for the user (without completing it). |
| 5366–5386 | `claim_processed_payment` | function | есть: Idempotency guard: returns True only once per payment_id. |
| 5372–5380 | `claim_processed_payment._work` | nested | **нет** |
| 5389–5406 | `unclaim_processed_payment` | function | есть: Remove idempotency record so a failed payment can be retried. |
| 5395–5400 | `unclaim_processed_payment._work` | nested | **нет** |
| 5409–5471 | `refund_payment_once` | function | есть: Вернуть средства за невыданную услугу не более одного раза на payment_id. |
| 5474–5539 | `cancel_pending_transaction` | function | есть: Пометить неоплаченный pending как cancelled, чтобы Stars/вебхук его не закрыли. |
| 5484–5533 | `cancel_pending_transaction._work` | nested | **нет** |
| 5542–5562 | `reset_pending_transaction` | function | есть: Reset a completed pending transaction back to 'pending' to allow webhook retry. |
| 5548–5556 | `reset_pending_transaction._work` | nested | **нет** |
| 5565–5586 | `get_referrals_for_user` | function | есть: Возвращает список пользователей, которых пригласил данный user_id. |
| 5589–5618 | `get_referral_top_rich` | function | есть: Возвращает топ пользователей по количеству рефералов, |
| 5621–5672 | `get_referral_rank_and_count` | function | есть: Возвращает кортеж (rank, count), где: |
| 5674–5689 | `get_all_settings` | function | **нет** |
| 5691–5702 | `update_setting` | function | **нет** |
| 5705–5725 | `get_button_configs` | function | есть: Get *active* button configurations for a specific menu type. |
| 5728–5759 | `get_button_configs_admin` | function | есть: Get button configurations for admin/editor UIs. |
| 5762–5773 | `get_button_config_by_db_id` | function | есть: Get a button configuration by its numeric DB id. |
| 5775–5791 | `get_button_config` | function | есть: Get a specific button configuration by menu_type and button_id |
| 5793–5836 | `create_button_config` | function | есть: Create a new button configuration |
| 5838–5899 | `update_button_config` | function | есть: Update an existing button configuration |
| 5901–5912 | `delete_button_config` | function | есть: Delete a button configuration |
| 5914–5946 | `update_existing_my_keys_button` | function | есть: Update existing my_keys button to include key count template and set proper button widths |
| 5949–5983 | `ensure_main_menu_gift_button` | function | есть: Ensure that the main menu has the gift button in button configs. |
| 5986–6036 | `ensure_main_menu_referral_button` | function | есть: Ensure that the main menu has the referral program button in button configs, |
| 6039–6109 | `ensure_admin_plans_button` | function | есть: Ensure that the Admin menu has a button for managing тарифы (plans). |
| 6114–6153 | `ensure_admin_trial_button` | function | есть: Ensure that the Admin menu has a button for managing Trial settings. |
| 6156–6199 | `ensure_admin_auto_renew_button` | function | есть: Ensure that the Admin settings submenu has a button for Автопродление (auto-renew). |
| 6202–6248 | `reorder_button_configs` | function | есть: Reorder button configurations for a menu type |
| 6250–6385 | `initialize_default_button_configs` | function | есть: Initialize default button configurations for all menu types |
| 6387–6408 | `create_plan` | function | **нет** |
| 6411–6422 | `get_plans_for_host` | function | **нет** |
| 6426–6441 | `get_active_plans_for_host` | function | есть: Возвращает только активные тарифы (is_active = 1) для указанного хоста. |
| 6444–6457 | `set_plan_active` | function | есть: Включить/выключить тариф (скрыть/показать пользователям). |
| 6459–6469 | `get_plan_by_id` | function | **нет** |
| 6472–6488 | `get_all_plans` | function | есть: Все тарифы (для админки промокодов и валидации applicable_plan_ids). |
| 6491–6497 | `_parse_json_metadata` | function | **нет** |
| 6499–6515 | `update_plan_metadata` | function | есть: Update plan.metadata JSON blob. |
| 6518–6546 | `create_traffic_package` | function | есть: Пакет докупки ГБ для тарифа. `pool`: 'main' (основной трафик) или 'lte' (premium-ноды). |
| 6549–6563 | `get_traffic_packages_for_plan` | function | **нет** |
| 6566–6576 | `get_traffic_package_by_id` | function | **нет** |
| 6579–6599 | `update_traffic_package` | function | **нет** |
| 6602–6611 | `delete_traffic_package` | function | **нет** |
| 6614–6626 | `set_key_traffic_boost` | function | **нет** |
| 6629–6638 | `get_plan_lte_limit` | function | **нет** |
| 6641–6690 | `get_lte_state` | function | есть: УСТАРЕЛО: пользовательская модель LTE-пула. |
| 6705–6729 | `get_key_lte_state` | function | есть: Состояние LTE-пула конкретного ключа (создаёт строку при отсутствии). |
| 6732–6774 | `update_key_lte_state` | function | **нет** |
| 6777–6806 | `add_key_lte_boost_bytes` | function | есть: Атомарно увеличить докупленный LTE-буст КЛЮЧА. Возвращает новое значение. |
| 6809–6837 | `commit_key_lte_baseline` | function | есть: Зафиксировать точку отсчёта LTE-расхода ключа одной транзакцией. |
| 6840–6854 | `request_key_lte_baseline_reset` | function | есть: Пометить начало нового расчётного периода LTE у ключа (буст сгорит вместе с baseline). |
| 6857–6876 | `resolve_lte_limit_bytes` | function | есть: Единая формула эффективного LTE-лимита: лимит тарифа + докупленный буст. |
| 6879–6914 | `add_lte_boost_bytes` | function | есть: Атомарно увеличить докупленный LTE-буст пользователя на `add_bytes`. |
| 6917–6953 | `commit_lte_baseline` | function | есть: Зафиксировать точку отсчёта (baseline) LTE-расхода одной транзакцией. |
| 6956–6979 | `request_lte_baseline_reset` | function | есть: Помечает начало нового расчётного периода LTE-пула. |
| 6982–7022 | `update_lte_state` | function | **нет** |
| 7025–7034 | `delete_plan` | function | **нет** |
| 7036–7072 | `update_plan` | function | **нет** |
| 7075–7098 | `register_user_if_not_exists` | function | есть: Зарегистрировать пользователя, если его ещё нет. |
| 7100–7109 | `add_to_referral_balance` | function | **нет** |
| 7111–7118 | `set_referral_balance` | function | **нет** |
| 7120–7127 | `set_referral_balance_all` | function | **нет** |
| 7129–7139 | `add_to_referral_balance_all` | function | **нет** |
| 7141–7150 | `get_referral_balance_all` | function | **нет** |
| 7152–7161 | `get_referral_balance` | function | **нет** |
| 7163–7172 | `get_balance` | function | **нет** |
| 7174–7184 | `adjust_user_balance` | function | есть: Скорректировать баланс пользователя на указанную дельту (может быть отрицательной). |
| 7186–7196 | `adjust_user_referral_balance` | function | есть: Скорректировать реферальный баланс пользователя на указанную дельту (может быть отрицательной). |
| 7198–7207 | `set_balance` | function | **нет** |
| 7209–7236 | `add_to_balance` | function | **нет** |
| 7238–7260 | `deduct_from_balance` | function | есть: Атомарное списание с основного баланса при достаточности средств. |
| 7262–7281 | `deduct_from_referral_balance` | function | есть: Атомарное списание с реферального баланса при достаточности средств. |
| 7300–7302 | `_referral_setting_is_true` | function | **нет** |
| 7305–7309 | `is_referral_withdraw_method_type_enabled` | function | **нет** |
| 7312–7336 | `validate_referral_payout_requisite` | function | есть: Проверить реквизиты метода получения перед сохранением. |
| 7339–7363 | `format_referral_withdrawal_admin_notice` | function | есть: Текст уведомления админам о новой заявке на вывод. |
| 7366–7378 | `list_referral_payout_methods` | function | **нет** |
| 7381–7400 | `add_referral_payout_method` | function | **нет** |
| 7403–7417 | `delete_referral_payout_method` | function | **нет** |
| 7420–7436 | `get_referral_payout_method` | function | **нет** |
| 7439–7452 | `create_webapp_auth_request` | function | есть: Создаёт запись ожидания подтверждения входа через deep-link бота (user_id пока NULL). |
| 7455–7471 | `confirm_webapp_auth_request` | function | есть: Подтверждает вход: бот вызывает эту функцию после получения deep-link auth_{token}. |
| 7474–7493 | `get_webapp_auth_request` | function | есть: Возвращает user_id, если запрос уже подтверждён ботом, иначе None. |
| 7496–7506 | `cleanup_old_webapp_auth_requests` | function | **нет** |
| 7509–7569 | `create_referral_withdrawal_request` | function | есть: Атомарно списывает сумму с referral_balance пользователя и создаёт заявку на вывод. |
| 7572–7588 | `has_open_referral_withdrawal_request` | function | есть: Есть ли у пользователя незакрытая заявка (new/processing). |
| 7591–7616 | `list_referral_withdrawal_requests` | function | **нет** |
| 7619–7637 | `get_referral_withdrawal_request` | function | **нет** |
| 7640–7717 | `update_referral_withdrawal_request_status` | function | есть: Меняет статус заявки на вывод. |
| 7720–7733 | `get_referral_withdrawable_stats` | function | есть: Сводка по заявкам на вывод (для админ-панели): счётчики по статусам и суммы. |
| 7736–7744 | `get_referral_count` | function | **нет** |
| 7746–7756 | `get_user` | function | **нет** |
| 7759–7773 | `get_user_by_username` | function | есть: Возвращает пользователя по username (без @), регистр не важен. |
| 7775–7783 | `set_terms_agreed` | function | **нет** |
| 7785–7800 | `is_subscription_expiry_notifications_enabled` | function | есть: Проверить, включены ли уведомления об истечении срока ключа. |
| 7802–7826 | `toggle_subscription_expiry_notifications` | function | есть: Переключить статус уведомлений об истечении срока. Возвращает новое состояние. |
| 7828–7835 | `update_user_stats` | function | **нет** |
| 7837–7845 | `get_user_count` | function | **нет** |
| 7847–7855 | `get_total_keys_count` | function | **нет** |
| 7857–7874 | `get_total_spent_sum` | function | **нет** |
| 7876–7901 | `create_pending_transaction` | function | есть: Create a pending transaction row in `transactions`. |
| 7904–7995 | `find_and_complete_ton_transaction` | function | есть: Atomically completes a TON transaction. |
| 8006–8023 | `_describe_transaction_action` | function | есть: Формирует человекочитаемое описание действия транзакции по её metadata. |
| 8025–8060 | `_find_nearest_key_id` | function | есть: Best-effort подбор ключа для старых транзакций, в metadata которых ещё не сохранялся key_id. |
| 8062–8128 | `log_transaction` | function | есть: Записывает транзакцию в таблицу `transactions`. |
| 8076–8122 | `log_transaction._work` | nested | **нет** |
| 8130–8179 | `get_paginated_transactions` | function | **нет** |
| 8181–8278 | `get_transactions_paginated` | function | есть: Универсальная выборка транзакций с фильтром по пользователю, поиском и сортировкой. |
| 8280–8288 | `set_trial_used` | function | **нет** |
| 8290–8362 | `add_new_key` | function | **нет** |
| 8365–8384 | `_apply_key_updates` | function | **нет** |
| 8387–8443 | `update_key_fields` | function | **нет** |
| 8446–8488 | `apply_key_monthly_reset_fields` | function | есть: Записать `traffic_limit_strategy` и `next_traffic_reset_at` по тарифу ключа. |
| 8491–8530 | `backfill_monthly_traffic_reset_for_existing_keys` | function | есть: Проставить MONTH_ROLLING и дату сброса уже выданным лимитным/LTE-ключам. |
| 8533–8568 | `delete_key_by_email` | function | **нет** |
| 8571–8584 | `get_user_keys` | function | **нет** |
| 8587–8597 | `get_key_by_id` | function | **нет** |
| 8600–8614 | `get_key_by_email` | function | **нет** |
| 8617–8633 | `get_key_by_remnawave_uuid` | function | **нет** |
| 8636–8642 | `update_key_info` | function | **нет** |
| 8645–8658 | `update_key_host_and_info` | function | **нет** |
| 8661–8662 | `get_next_key_number` | function | **нет** |
| 8665–8679 | `get_keys_for_host` | function | **нет** |
| 8682–8691 | `set_key_auto_renew` | function | **нет** |
| 8694–8704 | `set_all_keys_auto_renew_for_user` | function | есть: Mass-update auto_renew for all keys of a user. Returns count of updated rows. |
| 8707–8730 | `get_keys_for_auto_renew` | function | есть: Return keys with auto_renew=1 expiring within the next `hours_before` hours. |
| 8733–8741 | `_key_matches_search` | function | есть: Регистронезависимая (в т.ч. кириллица) проверка вхождения подстроки |
| 8744–8763 | `search_user_keys_by_email` | function | есть: Поиск ключей пользователя по key_email, email или user_key_name. |
| 8766–8784 | `search_all_keys_by_email` | function | есть: Поиск всех ключей (администраторам) по key_email, email или user_key_name. |
| 8787–8797 | `get_all_vpn_users` | function | **нет** |
| 8800–8840 | `update_key_status_from_server` | function | **нет** |
| 8843–8875 | `get_daily_stats_for_charts` | function | **нет** |
| 8878–8911 | `get_recent_transactions` | function | **нет** |
| 8914–8923 | `get_all_users` | function | **нет** |
| 8925–9041 | `get_users_paginated` | function | есть: Вернуть пользователей постранично и общее количество (с учётом фильтра). |
| 9043–9061 | `get_keys_counts_for_users` | function | есть: Вернуть словарь {user_id: keys_count} по списку пользователей. |
| 9063–9070 | `ban_user` | function | **нет** |
| 9072–9079 | `unban_user` | function | **нет** |
| 9091–9115 | `mark_user_unreachable` | function | есть: Отметить пользователя как недоступного в Telegram. |
| 9117–9135 | `mark_user_reachable` | function | есть: Снять отметку недоступности — пользователь снова взаимодействовал с ботом |
| 9137–9166 | `get_reachability_stats` | function | есть: Статистика по доступности пользователей в Telegram: сколько всего |
| 9168–9182 | `delete_user_keys` | function | **нет** |
| 9185–9304 | `delete_user_completely` | function | есть: Полностью удалить пользователя и все связанные с ним данные. |
| 9306–9330 | `create_support_ticket` | function | **нет** |
| 9332–9356 | `get_or_create_open_ticket` | function | есть: Возвращает ID открытого тикета пользователя и флаг, создан ли новый. |
| 9358–9374 | `add_support_message` | function | **нет** |
| 9376–9388 | `update_ticket_thread_info` | function | **нет** |
| 9390–9400 | `get_ticket` | function | **нет** |
| 9402–9415 | `get_ticket_by_thread` | function | **нет** |
| 9417–9435 | `get_user_tickets` | function | **нет** |
| 9437–9451 | `get_support_message` | function | есть: Одно сообщение тикета. Нужно для отдачи вложений в панели. |
| 9454–9470 | `resolve_db_file_path` | function | есть: Абсолютный путь к users.db без зависимости от cwd процесса. |
| 9473–9478 | `get_ticket_media_root` | function | есть: Каталог вложений рядом с users.db, не в webhook_server/. |
| 9481–9500 | `list_closed_ticket_ids_older_than` | function | есть: Закрытые тикеты с updated_at не новее cutoff (наивный ISO-текст SQLite). |
| 9503–9516 | `clear_support_message_media` | function | есть: Обнуляет media у сообщений тикета после TTL/удаления файлов. |
| 9519–9531 | `get_ticket_messages` | function | **нет** |
| 9533–9545 | `set_ticket_status` | function | **нет** |
| 9547–9559 | `update_ticket_subject` | function | **нет** |
| 9561–9568 | `_cleanup_ticket_media` | function | есть: Файлы вложений живут вне SQLite — удаляем каталог вместе с тикетом. |
| 9571–9590 | `delete_ticket` | function | **нет** |
| 9593–9606 | `_ticket_forum_target` | function | **нет** |
| 9617–9636 | `validate_ticket_auto_close_days` | function | есть: Для формы настроек: только целое 0–365. |
| 9639–9650 | `parse_ticket_auto_close_days` | function | есть: 0 — выключено. Нецелое и мусор → 0. Целое больше 365 режем потолком. |
| 9653–9654 | `get_ticket_auto_close_days` | function | **нет** |
| 9657–9709 | `find_open_tickets_idle_after_admin` | function | есть: Открытые тикеты, где последнее сообщение — ответ админа старше ``days`` суток. |
| 9712–9776 | `auto_close_idle_admin_tickets` | function | есть: Закрывает найденные простаивающие тикеты. Форум — снаружи. |
| 9779–9804 | `bulk_close_open_tickets` | function | есть: Один UPDATE всех открытых тикетов. Форум/уведомления — на стороне вызывающего. |
| 9807–9836 | `bulk_delete_all_tickets` | function | есть: Один DELETE всех тикетов и сообщений. Вложения на диске не трогает. |
| 9839–9852 | `cleanup_ticket_media_ids` | function | есть: Удаляет каталоги вложений пачкой. Ошибки по одному id не рвут остальные. |
| 9854–9877 | `get_tickets_paginated` | function | **нет** |
| 9879–9887 | `get_open_tickets_count` | function | **нет** |
| 9889–9897 | `get_closed_tickets_count` | function | **нет** |
| 9899–9907 | `get_all_tickets_count` | function | **нет** |
| 9915–9925 | `get_key_usage_monitor` | function | **нет** |
| 9928–9938 | `ensure_key_usage_monitor_row` | function | **нет** |
| 9941–9990 | `update_key_usage_monitor` | function | **нет** |
| 10000–10006 | `get_franchise_percent_default` | function | есть: Получить процент комиссии франшизы из настроек. |
| 10009–10015 | `get_franchise_min_withdraw` | function | есть: Получить минимум для вывода франшизников из настроек. |
| 10018–10036 | `resolve_factory_bot_id` | function | есть: Return internal managed bot id for a Telegram bot user id. |
| 10042–10051 | `_managed_bot_token_secret` | function | есть: Ключ шифрования токенов клонов: SHOPBOT_SECRET_KEY или стабильная запись в settings. |
| 10054–10060 | `_managed_bot_token_pad` | function | **нет** |
| 10063–10115 | `_backfill_encrypt_secrets_at_rest` | function | есть: Зашифровать уже сохранённые plaintext-секреты (settings / hosts / SSH-цели). |
| 10118–10131 | `encrypt_managed_bot_token` | function | есть: Зашифровать токен клона для хранения. Уже enc1$ не трогаем. |
| 10134–10154 | `decrypt_managed_bot_token` | function | есть: Расшифровать токен. Legacy plaintext (без enc1$) возвращается как есть. |
| 10157–10163 | `_row_with_decrypted_token` | function | **нет** |
| 10166–10176 | `get_managed_bot` | function | **нет** |
| 10179–10189 | `get_managed_bot_by_telegram_id` | function | **нет** |
| 10192–10201 | `list_active_managed_bots` | function | **нет** |
| 10204–10219 | `update_managed_bot_active` | function | есть: Параметризованно выставить is_active (0/1). Схему таблицы не меняет. |
| 10222–10245 | `get_managed_bots_by_owner` | function | есть: Список клонов владельца без токена (токен не отдаём в UI). |
| 10248–10260 | `purge_managed_bot_stats` | function | есть: Удалить активность и комиссии клона. Идемпотентно, ошибки не пробрасывает. |
| 10263–10265 | `_purge_managed_bot_stats_on_cursor` | function | **нет** |
| 10268–10316 | `delete_managed_bot` | function | есть: Удалить строку managed_bots и статистику клона. |
| 10319–10352 | `get_factory_cabinet` | function | есть: Статистика кабинета клона (пользователи/сообщения/прямые клоны/баланс). |
| 10355–10419 | `create_managed_bot` | function | есть: Register a managed bot. |
| 10422–10449 | `record_factory_activity` | function | есть: Upsert activity row (unique users + messages count). |
| 10452–10459 | `_is_card_payment_method` | function | **нет** |
| 10462–10571 | `accrue_partner_commission` | function | есть: Accrue partner commission for a managed bot. |
| 10574–10617 | `get_partner_cabinet` | function | есть: Return partner cabinet stats for managed bot. |
| 10622–10644 | `list_partner_requisites` | function | есть: Return all payout requisites for a partner (owner) within a managed bot. |
| 10647–10656 | `get_default_partner_requisite` | function | есть: Return the default payout requisite for a partner, if any. |
| 10659–10726 | `add_partner_requisite` | function | есть: Add a payout requisite for a partner. |
| 10729–10763 | `set_default_partner_requisite` | function | есть: Set given requisite as default for this bot/owner. |
| 10766–10811 | `delete_partner_requisite` | function | есть: Delete a payout requisite. |
| 10814–10862 | `create_withdraw_request` | function | есть: Create a partner withdraw request. |
| 10869–10917 | `create_user_gift` | function | есть: Создать неактивированный подарок от одного пользователя. |
| 10920–10931 | `get_user_gift` | function | есть: Получить информацию о подарке по ID. |
| 10934–10945 | `get_gift_by_code` | function | есть: Получить информацию о подарке по коду. |
| 10948–10979 | `get_user_inactive_gifts` | function | есть: Получить список неактивированных подарков пользователя. |
| 10982–11036 | `activate_user_gift` | function | есть: Активировать подарок для пользователя. |
| 11039–11049 | `_registration_age_seconds` | function | есть: Возраст аккаунта в секундах, либо None если даты нет / она не парсится. |
| 11052–11089 | `set_referred_by_from_gift` | function | есть: Set referred_by to the gift sender when a new user activates a gift. |
| 11101–11170 | `link_referrer_if_eligible` | function | есть: Привязать пользователя к рефереру (users.referred_by), если это допустимо. |
| 11179–11214 | `unlink_referral` | function | есть: Снять привязку реферала: обнулить users.referred_by у invitee, если он |
| 11217–11241 | `unlink_all_referrals` | function | есть: Снять привязку у всех рефералов указанного реферера. |
| 11244–11254 | `delete_user_gift` | function | есть: Удалить подарок. |
| 11257–11270 | `link_key_to_gift` | function | есть: Связать созданный ключ с подарком. |
| 11273–11284 | `get_gift_code_by_key_id` | function | есть: Получить код подарка по ID ключа. |
| 11286–11297 | `get_gift_code_by_key_id` | function | есть: Получить код подарка по ID ключа. |
| 11299–11312 | `get_gift_info_by_key_id` | function | есть: Получить ID и код подарка по ID ключа. Возвращает (gift_id, gift_code) или (None, None). |
| 11319–11322 | `get_msk_time` | function | есть: Текущее время в московской зоне (UTC+3), используется для расчётов сроков в webapp. |
| 11325–11350 | `check_transaction_exists` | function | есть: Проверить, существует ли уже завершённая транзакция с данным payment_id. |
| 11353–11387 | `payment_owned_by_user` | function | есть: True, если payment_id есть в pending_transactions или transactions у этого user_id. |
| 11367–11381 | `payment_owned_by_user._work` | nested | **нет** |
| 11390–11404 | `get_seller_user` | function | есть: Вернуть данные продавца (франшиза/партнёрская скидка) для пользователя. |
| 11407–11420 | `get_device_tiers` | function | есть: Вернуть тарифные планы, сгруппированные по лимиту устройств, для указанного хоста. |
| 11423–11436 | `get_user_by_auth_token` | function | есть: Найти пользователя по постоянному auth-токену (webapp). |
| 11439–11449 | `get_auth_token_by_user_id` | function | есть: Получить уже выданный постоянный auth-токен пользователя, если есть. |
| 11452–11462 | `update_user_auth_token` | function | есть: Сохранить постоянный auth-токен для пользователя (webapp). |
| 11465–11491 | `invalidate_all_user_auth_tokens` | function | есть: Перевыпустить все persistent auth_token пользователей (UUID4). |
| 11494–11498 | `hash_password` | function | есть: Хэшировать пароль пользователя (PBKDF2-HMAC-SHA256 со случайной солью). |
| 11501–11517 | `verify_password` | function | есть: Проверить пароль против сохранённого хэша. |
| 11520–11534 | `get_user_by_email` | function | есть: Найти локального пользователя webapp по email (для входа по email+паролю). |
| 11537–11569 | `create_user_by_email` | function | есть: Создать "виртуального" (не привязанного к Telegram) пользователя webapp по email+паролю. |
| 11572–11586 | `update_user_password` | function | есть: Обновить (хэшированный) пароль локального webapp-аккаунта по email. |
| 11589–11590 | `_hash_verification_code` | function | **нет** |
| 11593–11612 | `set_email_verification_code` | function | есть: Сохранить хэш одноразового кода подтверждения email и время его истечения. |
| 11615–11632 | `get_email_verification` | function | есть: Вернуть данные о статусе подтверждения email и последнем отправленном коде. |
| 11635–11647 | `check_email_verification_code` | function | есть: Проверить введённый код подтверждения против сохранённого хэша (с учётом срока действия). |
| 11650–11667 | `mark_email_verified` | function | есть: Отметить email пользователя как подтверждённый и очистить код. |
| 11670–11683 | `update_email_code_last_sent` | function | есть: Обновить время последней отправки кода (для rate-limit повторной отправки). |
| 11686–11698 | `update_user_password_by_id` | function | есть: Обновить (хэшированный) пароль webapp-аккаунта по telegram_id (смена пароля из профиля, |
| 11701–11715 | `set_pending_email` | function | есть: Сохранить новый email, ожидающий подтверждения кодом (смена почты из профиля). |
| 11718–11732 | `clear_pending_email` | function | есть: Отменить ожидающую смену email (например, пользователь передумал или запросил другой адрес). |
| 11735–11780 | `finalize_pending_email_change` | function | есть: Подтвердить смену email кодом: перенести `pending_email` в `auth_email`. |
| 11783–11806 | `get_webapp_settings` | function | есть: Вернуть настройки Telegram Mini App (webapp) из общей таблицы bot_settings. |

## `src/shop_bot/data_manager/remnawave_repository.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 16–32 | `__getattr__` | function | есть: Модуль-level fallback (PEP 562) для `DB_FILE`. |
| 41–49 | `set_current_factory_bot_id` | function | есть: Set current factory bot id for the running handler via contextvars. |
| 52–56 | `reset_current_factory_bot_id` | function | **нет** |
| 59–63 | `get_current_factory_bot_id` | function | **нет** |
| 66–71 | `PromoUnavailableError` | class | есть: Промокод нельзя зарезервировать (лимит / недействителен). |
| 69–71 | `PromoUnavailableError.__init__` | method | **нет** |
| 74–118 | `create_payload_pending` | function | есть: Create/update pending payload metadata. |
| 121–129 | `cancel_pending_transaction` | function | есть: Отменить неоплаченный pending и освободить слот промокода, если он был зарезервирован. |
| 132–135 | `_connect` | function | **нет** |
| 138–139 | `_normalize_email` | function | **нет** |
| 142–143 | `_default_expire_at_ms` | function | **нет** |
| 146–150 | `_decrypt_host_secrets` | function | есть: get_squad/list_squads читают xui_hosts напрямую — расшифровать как get_host. |
| 153–162 | `list_squads` | function | **нет** |
| 165–187 | `get_squad` | function | **нет** |
| 190–191 | `get_key_by_id` | function | **нет** |
| 194–195 | `get_key_by_email` | function | **нет** |
| 198–199 | `get_key_by_remnawave_uuid` | function | **нет** |
| 202–262 | `record_key` | function | **нет** |
| 265–301 | `record_key_from_payload` | function | **нет** |
| 304–340 | `update_key` | function | **нет** |
| 343–363 | `_parse_key_expiry_dt` | function | есть: Parse key expiry from normalized row (expiry_date / expire_at). |
| 366–400 | `_sync_key_expiry_ms` | function | есть: Push expiry to Remnawave, then update local DB. Returns (ok, error, final_ms). |
| 403–423 | `extend_key` | function | есть: Продлить/сократить срок ключа на N дней (N может быть отрицательным). |
| 426–460 | `set_key_expiry` | function | есть: Установить точную дату истечения ключа; синхронизирует Remnawave + БД. |
| 463–464 | `delete_key_by_email` | function | **нет** |
| 467–489 | `generate_key_email_for_user` | function | есть: Generate a unique key email based on Telegram ID + key number. |
| 759–799 | `create_gift_token` | function | **нет** |
| 802–810 | `get_gift_token` | function | **нет** |
| 813–823 | `list_gift_tokens` | function | **нет** |
| 826–834 | `delete_gift_token` | function | **нет** |
| 837–895 | `claim_gift_token` | function | **нет** |
| 900–977 | `create_promo_code` | function | **нет** |
| 980–988 | `get_promo_code` | function | **нет** |
| 991–999 | `list_promo_codes` | function | **нет** |
| 1032–1035 | `promo_error_message` | function | **нет** |
| 1038–1071 | `_serialize_applicable_plan_ids` | function | есть: Validate and store plan scope as a JSON array of ints, or NULL = all plans. |
| 1074–1092 | `_normalize_promo_segment` | function | **нет** |
| 1095–1117 | `_parse_applicable_plan_ids` | function | есть: NULL/empty → unrestricted. Invalid JSON → empty list (fail closed). |
| 1120–1126 | `_coerce_plan_id` | function | **нет** |
| 1129–1140 | `_user_has_active_subscription` | function | есть: True if the user has at least one vpn_keys row with expire_at > now(). |
| 1143–1186 | `_user_paid_total` | function | есть: Sum of completed purchases for the user. |
| 1173–1181 | `_user_paid_total._sum` | nested | **нет** |
| 1189–1211 | `_user_matches_promo_segment` | function | есть: Whether the user satisfies an optional promo segment restriction. |
| 1214–1238 | `_promo_targeting_error` | function | есть: plan_not_eligible / segment_not_eligible, or None if targeting passes. |
| 1241–1244 | `_PromoTxnAbort` | class | **нет** |
| 1242–1244 | `_PromoTxnAbort.__init__` | method | **нет** |
| 1247–1257 | `_connect_promo_write` | function | есть: Write connection with BEGIN IMMEDIATE so promo limit updates serialize. |
| 1260–1295 | `_with_promo_write` | function | **нет** |
| 1298–1316 | `_promo_validity_error` | function | **нет** |
| 1319–1336 | `_per_user_occupied` | function | **нет** |
| 1339–1352 | `_fetch_promo_row` | function | **нет** |
| 1355–1369 | `_atomic_increment_used_total` | function | есть: Increment used_total only if the total limit still has a free slot. |
| 1372–1383 | `_decrement_used_total` | function | **нет** |
| 1386–1442 | `check_promo_code_available` | function | есть: Проверить возможность использования промокода, не изменяя лимиты. |
| 1412–1432 | `check_promo_code_available._work` | nested | **нет** |
| 1445–1538 | `reserve_promo_code` | function | есть: Atomically reserve one promo usage slot for a pending payment. |
| 1472–1533 | `reserve_promo_code._work` | nested | **нет** |
| 1541–1579 | `release_promo_reservation` | function | есть: Free a reserved slot (pending expired/cancelled). Never lets used_total go below 0. |
| 1547–1574 | `release_promo_reservation._work` | nested | **нет** |
| 1582–1608 | `release_stale_promo_reservations` | function | есть: Release reservations older than TTL so abandoned invoices do not hold the limit forever. |
| 1611–1627 | `update_promo_code_status` | function | **нет** |
| 1630–1638 | `delete_promo_code` | function | **нет** |
| 1641–1760 | `redeem_promo_code` | function | есть: Confirm a reserved slot (or atomically take one) and record the usage. |
| 1656–1755 | `redeem_promo_code._work` | nested | **нет** |
| 1764–1766 | `search_user_keys_by_email` | function | есть: Поиск ключей пользователя по key_email. |
| 1769–1771 | `search_all_keys_by_email` | function | есть: Поиск всех ключей (администраторам) по key_email. |

## `src/shop_bot/data_manager/scheduler.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 45–60 | `format_time_left` | function | **нет** |
| 62–84 | `send_subscription_notification` | function | **нет** |
| 86–111 | `_cleanup_notified_users` | function | **нет** |
| 113–151 | `check_expiring_subscriptions` | function | **нет** |
| 154–175 | `_parse_dt_safe` | function | **нет** |
| 178–205 | `_extract_used_bytes` | function | есть: Пытаемся извлечь использованный трафик из payload пользователя Remnawave (если поле есть). |
| 208–209 | `_is_true` | function | **нет** |
| 212–217 | `_get_inactive_usage_reminder_enabled` | function | есть: Глобальный переключатель напоминаний о нулевом использовании трафика. |
| 220–232 | `_get_inactive_usage_reminder_interval_hours` | function | есть: Интервал напоминаний в часах (также используется как задержка перед первым напоминанием). |
| 235–236 | `_get_inactive_usage_reminder_interval_seconds` | function | **нет** |
| 239–249 | `_parse_origin_meta_from_description` | function | **нет** |
| 252–267 | `_try_int` | function | **нет** |
| 270–314 | `_resolve_hwid_device_limit_for_key` | function | есть: Определить допустимый лимит устройств для ключа. |
| 317–347 | `_extract_device_ids` | function | **нет** |
| 350–476 | `check_device_limit_violations` | function | есть: Проверяет превышение лимитов привязанных HWID устройств и уведомляет админов. |
| 479–589 | `check_traffic_boost_resets` | function | есть: Ежемесячный сброс трафика ключа до базовых значений тарифа. |
| 592–917 | `enforce_dual_traffic_limits` | function | есть: Двухуровневый учёт трафика (основной пул + независимый LTE-пул на premium-нодах). |
| 920–1004 | `_legacy_check_traffic_boost_resets` | function | есть: Откатывает докупленный буст трафика после ежемесячного сброса лимита на сервере (устаревшая эвристик |
| 1007–1100 | `check_inactive_usage_reminders` | function | есть: Если после выдачи ключа у пользователя не было подключенных устройств/трафика — напоминать с заданны |
| 1103–1265 | `sync_keys_with_panels` | function | **нет** |
| 1268–1281 | `_maybe_sync_keys_with_panels` | function | есть: sync_keys_with_panels is expensive (list all users on each host). |
| 1284–1300 | `_maybe_enforce_dual_traffic_limits` | function | есть: Учёт двух пулов трафика (основной + LTE) — интервал настраивается через bot_settings.dual_limit_inte |
| 1303–1321 | `_notify_auto_renew_success` | function | **нет** |
| 1324–1343 | `_notify_auto_renew_no_balance` | function | **нет** |
| 1346–1440 | `check_auto_renewals` | function | **нет** |
| 1443–1482 | `check_broadcast_campaigns` | function | есть: Send queued broadcast campaigns to inactive subscribers. |
| 1489–1498 | `_ticket_files_present` | function | есть: Дешёвая проверка: нет каталога или он пуст — TTL не запускаем. |
| 1501–1518 | `_maybe_purge_closed_ticket_media` | function | есть: TTL вложений. Отдельный task не создаём; если файлов нет — сразу выход. |
| 1521–1528 | `_maybe_auto_close_idle_tickets` | function | есть: После ответа админа пользователь молчит N дней — закрываем тикет. SQL сразу, Telegram в фоне. |
| 1531–1573 | `periodic_subscription_check` | function | **нет** |
| 1576–1586 | `_maybe_sync_keys_with_panels` | function | есть: Sync with Remnawave panels is expensive; throttle to reduce bot latency. |
| 1588–1597 | `_maybe_run_periodic_speedtests` | function | **нет** |
| 1599–1627 | `_run_speedtests_for_all_hosts` | function | **нет** |
| 1629–1655 | `_run_speedtests_for_all_ssh_targets` | function | **нет** |
| 1659–1739 | `_maybe_collect_resource_metrics` | function | есть: Периодический сбор метрик (локально + SSH на хостах) и отправка алертов при превышении порогов. |
| 1742–1770 | `_maybe_run_daily_backup` | function | есть: Ежедневный автобэкап базы и отправка админам. Интервал задаётся в настройках backup_interval_days. |
| 1773–1870 | `_maybe_alert` | function | **нет** |
| 1873–1933 | `_send_alert` | function | есть: Отправка алерта админам |

## `src/shop_bot/data_manager/backup_manager.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 25–26 | `_timestamp` | function | **нет** |
| 29–61 | `create_backup_file` | function | есть: Создаёт zip-архив с консистентной копией SQLite-БД. |
| 64–74 | `cleanup_old_backups` | function | есть: Хранить только N последних архивов, остальные удалять. |
| 77–135 | `send_backup_to_admins` | function | есть: Отправляет архив всем администраторам. Возвращает число успешных отправок. |
| 139–159 | `validate_db_file` | function | есть: Простая валидация файла БД: доступность основных таблиц. |
| 162–225 | `restore_from_file` | function | есть: Восстанавливает основную БД из переданного файла .db или .zip (внутри .db). |

## `src/shop_bot/data_manager/captcha_utils.py`

Модульный docstring: Утилиты для работы с системой капчи.

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 21–22 | `_now_str` | function | **нет** |
| 25–28 | `_expire_time_str` | function | есть: Возвращает время истечения капчи (через N минут). |
| 31–52 | `generate_math_captcha` | function | есть: Генерирует математическую задачу и правильный ответ. |
| 55–72 | `generate_button_captcha` | function | есть: Генерирует капчу с нажатием на кнопку. |
| 75–115 | `create_captcha_challenge` | function | есть: Создаёт новый капча-вызов для пользователя. |
| 118–181 | `check_captcha_answer` | function | есть: Проверяет ответ на капчу. |
| 184–230 | `get_active_captcha_challenge` | function | есть: Получает активный капча-вызов для пользователя. |
| 233–248 | `has_passed_captcha` | function | есть: Проверяет, прошла ли капчу пользователь при регистрации. |
| 251–267 | `mark_user_passed_captcha` | function | есть: Помечает пользователя как прошедшего капчу. |

## `src/shop_bot/data_manager/resource_monitor.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 19–26 | `_safe_percent` | function | **нет** |
| 29–212 | `get_local_metrics` | function | есть: Собрать базовые метрики локальной системы (панели). |
| 215–242 | `_parse_free_m` | function | **нет** |
| 245–250 | `_parse_loadavg` | function | **нет** |
| 253–278 | `_parse_df_h` | function | **нет** |
| 281–291 | `_compute_cpu_percent` | function | **нет** |
| 294–416 | `get_remote_metrics_for_host` | function | есть: Собрать базовые метрики по SSH для хоста из xui_hosts. |
| 419–531 | `get_remote_metrics_for_target` | function | **нет** |

## `src/shop_bot/data_manager/speedtest_runner.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 18–46 | `StoredHostKeyPolicy` | class | есть: Принимает host key только если он совпадает с сохранённым, либо |
| 24–33 | `StoredHostKeyPolicy.__init__` | method | **нет** |
| 35–46 | `StoredHostKeyPolicy.missing_host_key` | method | **нет** |
| 49–64 | `_apply_ssh_host_key_policy` | function | **нет** |
| 59–60 | `_apply_ssh_host_key_policy._save` | nested | **нет** |
| 67–77 | `_parse_host_port_from_url` | function | **нет** |
| 83–93 | `_parse_host_port_from_url` | function | **нет** |
| 96–104 | `_is_blocked_probe_ip` | function | **нет** |
| 107–132 | `_probe_target_error` | function | есть: Return an error string if the probe URL must not be contacted. |
| 135–200 | `net_probe_for_host` | function | есть: Lightweight network probe from panel to host_url: TCP connect + HTTP GET / (HEAD). |
| 203–226 | `_ssh_exec_json` | function | есть: Try commands sequentially; expect JSON on stdout. Returns (json_obj, error). |
| 229–246 | `_parse_ookla_json` | function | **нет** |
| 249–266 | `_parse_speedtest_cli_json` | function | **нет** |
| 269–342 | `ssh_speedtest_for_host` | function | есть: Run speedtest on remote host via SSH. Tries Ookla CLI first, then speedtest-cli. |
| 294–333 | `ssh_speedtest_for_host._run_ssh` | nested | **нет** |
| 345–362 | `run_and_store_net_probe` | function | **нет** |
| 365–382 | `run_and_store_ssh_speedtest` | function | **нет** |
| 385–407 | `run_both_for_host` | function | **нет** |
| 410–435 | `_ssh_connect` | function | **нет** |
| 438–443 | `_ssh_exec` | function | **нет** |
| 446–588 | `auto_install_speedtest_on_host` | function | есть: Attempt to auto-install Ookla speedtest or speedtest-cli on remote host via SSH. |
| 454–585 | `auto_install_speedtest_on_host._install` | nested | **нет** |
| 593–600 | `_target_to_host_row` | function | **нет** |
| 603–622 | `run_and_store_ssh_speedtest_for_target` | function | есть: Выполнить SSH-спидтест для отдельной цели (speedtest_ssh_targets) и сохранить результат как host_spe |
| 625–750 | `auto_install_speedtest_on_target` | function | есть: Автоустановка speedtest на отдельной SSH-цели. |
| 631–747 | `auto_install_speedtest_on_target._install` | nested | **нет** |

## `src/shop_bot/modules/remnawave_api.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 24–25 | `RemnawaveAPIError` | class | есть: Base error for Remnawave API interactions. |
| 34–44 | `_detail_is_already_in_desired_state` | function | есть: True, если панель ответила, что пользователь уже enable/disable — это успех. |
| 47–48 | `_is_already_in_desired_state` | function | **нет** |
| 76–83 | `_inflight_semaphore` | function | **нет** |
| 86–100 | `_client_request` | function | есть: Один HTTP-запрос к панели с лимитом параллелизма. |
| 103–115 | `gather_limited` | function | есть: asyncio.gather с потолком параллелизма — для списка ключей в WebApp. |
| 111–113 | `gather_limited._run` | nested | **нет** |
| 118–144 | `_get_shared_client` | function | **нет** |
| 147–178 | `_normalize_email_for_remnawave` | function | есть: Normalize and validate email for Remnawave API. |
| 181–206 | `_normalize_username_for_remnawave` | function | есть: Normalize username to only letters, numbers, underscores and dashes. |
| 208–216 | `_load_config` | function | есть: Backward-compatible global config loader (deprecated). |
| 219–234 | `_load_config_for_host` | function | есть: Load Remnawave API config for a specific host from xui_hosts. |
| 237–245 | `_build_headers` | function | **нет** |
| 248–293 | `_request` | function | **нет** |
| 296–341 | `_request_for_host` | function | **нет** |
| 344–348 | `_to_iso` | function | **нет** |
| 351–363 | `_extract_user_from_api_payload` | function | есть: Normalize Remnawave user lookup payloads (wrapped, list, or bare dict). |
| 366–376 | `get_user_by_email` | function | **нет** |
| 379–389 | `get_user_by_username` | function | **нет** |
| 398–407 | `_classify_panel_user_ref` | function | есть: id — числовой userId 3.x; uuid — старый идентификатор 2.x; short — shortUuid. |
| 410–416 | `_username_from_email` | function | есть: Локальная часть email → username, как при создании пользователя в панели. |
| 419–429 | `_panel_numeric_user_id` | function | есть: Числовой userId 3.x из payload пользователя, если он есть. |
| 432–441 | `panel_user_ref_from_payload` | function | есть: Идентификатор для путей `{userId}`: на 3.x это числовой id, на 2.x — uuid. |
| 444–454 | `_panel_user_get_path` | function | есть: Путь GET пользователя и допустимые статусы (3.x ждёт число, UUID даёт 400 NaN). |
| 457–466 | `_panel_hwid_devices_path` | function | есть: GET /api/hwid/devices/{userId}: 3.x ждёт число, UUID даёт 400 NaN. |
| 469–480 | `get_user_by_uuid` | function | **нет** |
| 483–509 | `lookup_panel_user` | function | есть: Найти пользователя панели: id / uuid / shortUuid, затем email, затем username. |
| 512–542 | `panel_user_exists` | function | есть: Есть ли пользователь на панели. |
| 545–553 | `_extract_hwid_devices_payload` | function | **нет** |
| 556–566 | `_get_hwid_devices_by_ref` | function | **нет** |
| 569–613 | `get_hwid_devices_for_user` | function | есть: Получить информацию об HWID-устройствах пользователя. |
| 616–637 | `_resolve_hwid_owner` | function | есть: Числовой userId 3.x и/или uuid 2.x для HWID API. |
| 640–702 | `delete_hwid_device` | function | есть: Удалить одно HWID-устройство пользователя через API. |
| 705–724 | `get_connected_devices_count` | function | есть: Обёртка над get_hwid_devices_for_user для webapp: всегда возвращает |
| 727–738 | `delete_user_device` | function | есть: Алиас delete_hwid_device с именем, ожидаемым webapp/handlers.py. |
| 741–919 | `ensure_user` | function | **нет** |
| 924–1110 | `list_users` | function | есть: List users from Remnawave. |
| 949–956 | `list_users._extract_users_from_payload` | nested | **нет** |
| 958–975 | `list_users._filter_by_squad` | nested | **нет** |
| 977–981 | `list_users._fetch` | nested | **нет** |
| 1004–1005 | `list_users._uid` | nested | **нет** |
| 1007–1021 | `list_users._append_new` | nested | **нет** |
| 1042–1065 | `list_users._try_paged` | nested | есть: Return True if paging seems to work (we got new users). |
| 1111–1123 | `delete_user` | function | есть: Глобальный вариант (устарел): удаление без привязки к хосту. |
| 1126–1136 | `delete_user_on_host` | function | есть: Удаление пользователя на конкретном хосте, используя конфиг хоста. |
| 1139–1144 | `reset_user_traffic` | function | **нет** |
| 1147–1157 | `update_user_traffic_limit` | function | есть: Обновляет лимит трафика (trafficLimitBytes) пользователя в Remnawave. |
| 1160–1184 | `set_user_status` | function | **нет** |
| 1187–1196 | `_extract_used_traffic_bytes` | function | **нет** |
| 1199–1227 | `disable_user` | function | есть: POST /api/users/{uuid}/actions/disable — скрыть ноду (используется для 💰-premium нод при исчерпании  |
| 1230–1257 | `enable_user` | function | есть: POST /api/users/{uuid}/actions/enable — вернуть доступ пользователю на конкретном хосте. |
| 1260–1287 | `set_user_active_squads` | function | есть: PATCH /api/users — установить полный список activeInternalSquads пользователя. |
| 1290–1311 | `extract_active_squad_uuids` | function | есть: UUID активных internal-сквадов пользователя из ответа панели. |
| 1314–1334 | `remove_squad_from_user` | function | есть: Убрать конкретный сквад из activeInternalSquads пользователя, не трогая остальные сквады. |
| 1337–1353 | `add_squad_to_user` | function | есть: Добавить конкретный сквад в activeInternalSquads пользователя, не трогая остальные сквады. |
| 1356–1374 | `get_user_used_traffic` | function | есть: Использованный трафик (в байтах) пользователя на конкретном инстансе Remnawave. 0, если данных нет. |
| 1377–1387 | `reset_user_traffic_on_host` | function | есть: POST /api/users/{uuid}/actions/reset-traffic на конкретном инстансе (host-aware вариант reset_user_t |
| 1390–1405 | `_extract_usage_rows` | function | есть: Достаёт список записей UserUsageDto из ответа Remnawave независимо от обёртки ({"response": [...]},  |
| 1408–1436 | `get_node_usage_range` | function | есть: Legacy per-node usage endpoint: GET /api/nodes/{node_uuid}/usage/range. |
| 1439–1469 | `get_bandwidth_stats_nodes_users` | function | есть: v2.8.0+ endpoint: POST /api/bandwidth-stats/nodes/users. |
| 1472–1521 | `get_user_lte_usage_bytes` | function | есть: Суммарный расход конкретного пользователя по нодам LTE-сквада за период. |
| 1492–1503 | `get_user_lte_usage_bytes._sum_for_user` | nested | **нет** |
| 1539–1545 | `RemnawavePathUnsupportedError` | class | есть: Путь не поддерживается этой версией панели (404 / 400 / 422 на валидации параметра). |
| 1557–1566 | `invalidate_squad_nodes_cache` | function | есть: Сбросить кэш нод сквада (целиком или по одному squad_uuid), включая негативный. |
| 1569–1597 | `_request_optional_path` | function | есть: Запрос к пути, которого может не быть в этой версии панели. |
| 1600–1699 | `get_squad_accessible_nodes` | function | есть: Ноды, доступные через internal squad: `GET /api/internal-squads/{uuid}/accessible-nodes`. |
| 1638–1642 | `get_squad_accessible_nodes._remember_failure` | nested | **нет** |
| 1702–1725 | `get_squad_nodes_for_class` | function | есть: Ноды активного сквада заданного класса ('lte'/'base') у хоста. |
| 1728–1730 | `get_lte_nodes_for_host` | function | есть: Ноды активного LTE-сквада хоста (с именами — для карточки ключа и снапшотов). |
| 1733–1738 | `get_lte_node_uuids_for_host` | function | есть: UUID нод активного LTE-сквада хоста. |
| 1741–1745 | `NodeUsage` | class | есть: Расход пользователя по нодам за период + идентификатор сработавшего пути API. |
| 1763–1768 | `_panel_instance_key` | function | есть: Идентификатор инстанса панели (base_url) для кэша поддержки путей. |
| 1771–1774 | `reset_usage_path_cache` | function | есть: Сбросить кэш решений о поддерживаемых путях (используется в тестах). |
| 1777–1787 | `_usage_path_unsupported` | function | **нет** |
| 1790–1798 | `_mark_usage_path_unsupported` | function | **нет** |
| 1801–1805 | `_as_api_date` | function | есть: Оба семейства эндпоинтов ждут дату в формате YYYY-MM-DD. |
| 1808–1818 | `_to_int_bytes` | function | **нет** |
| 1821–1852 | `resolve_panel_user_id` | function | есть: Числовой `id` пользователя панели (нужен путям 3.3.2). |
| 1855–1866 | `_sum_squad_scoped_days` | function | есть: 3.3.2: `{response: {days: [{date, nodes: [{uuid, totalBytes}]}]}}` -> сумма по нодам. |
| 1869–1888 | `_sum_user_series` | function | есть: 2.8.1/3.3.2: `{response: {series\|topNodes: [{uuid, total}]}}` -> расход по нодам. |
| 1891–1907 | `_sum_legacy_rows` | function | есть: 2.8.1 legacy: плоский список `{userUuid, nodeUuid, total, date}` -> расход по нодам. |
| 1910–2090 | `get_user_node_usage_for_squad` | function | есть: Расход пользователя по нодам LTE-сквада за период — с разбивкой по нодам. |
| 1970–1979 | `get_user_node_usage_for_squad._numeric_id` | nested | **нет** |
| 2093–2105 | `get_squad_node_overlap` | function | есть: Ноды, доступные одновременно через LTE- и base-сквад хоста. |
| 2108–2127 | `refresh_host_squad_overlap` | function | есть: Перепроверить пересечение сквадов хоста и сохранить результат для карточек. |
| 2130–2133 | `extract_subscription_url` | function | **нет** |
| 2138–2271 | `create_or_update_key_on_host` | function | есть: Legacy совместимость: создаёт/обновляет пользователя Remnawave и возвращает данные по ключу. |
| 2274–2299 | `get_key_details_from_host` | function | **нет** |
| 2302–2324 | `delete_client_on_host` | function | **нет** |

## `src/shop_bot/modules/platega_api.py`

Модульный docstring: Клиент для платёжного провайдера Platega.

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 26–58 | `get_transaction_sync` | function | есть: Синхронный GET /transaction/{id} для Flask-вебхука. Телу колбэка не доверяем. |
| 61–137 | `PlategaAPI` | class | есть: Простой асинхронный клиент Platega API. |
| 71–74 | `PlategaAPI.__init__` | method | **нет** |
| 76–99 | `PlategaAPI._request` | method | **нет** |
| 101–128 | `PlategaAPI.create_payment` | method | есть: Создать платёж в Platega. |
| 131–137 | `PlategaAPI.get_transaction` | method | есть: GET /transaction/{id} — сверка статуса по provider transaction ID. |

## `src/shop_bot/modules/platega_fulfillment.py`

Модульный docstring: Общая идемпотентная финализация Platega-платежа (webhook и WebApp verify).

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 18–22 | `is_platega_payment_method` | function | **нет** |
| 25–30 | `provider_transaction_id_from_meta` | function | **нет** |
| 33–39 | `normalize_platega_status` | function | **нет** |
| 42–50 | `extract_platega_amount` | function | **нет** |
| 53–63 | `remote_is_canceled` | function | есть: True только если API провайдера подтвердил отмену этого счёта. |
| 66–87 | `mark_pending_canceled` | function | есть: Пометить счёт отменённым в pending и в истории транзакций. |
| 90–111 | `complete_pending_platega_payment` | function | есть: Атомарно закрыть pending и вернуть metadata. |

## `src/shop_bot/modules/rollypay_api.py`

Модульный docstring: Клиент RollyPay: создание платежа, сверка статуса, проверка HMAC вебхука.

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 27–31 | `_safe_id` | function | **нет** |
| 34–58 | `verify_webhook_signature` | function | есть: HMAC-SHA256(`{unix_ts}.{raw_body}`) в заголовке X-Signature, как в SDK RollyPay. |
| 61–82 | `get_payment_sync` | function | есть: Синхронный GET /payments/{id} для Flask-вебхука. Не доверяем телу колбэка. |
| 85–180 | `RollyPayAPI` | class | **нет** |
| 86–88 | `RollyPayAPI.__init__` | method | **нет** |
| 90–96 | `RollyPayAPI._headers` | method | **нет** |
| 98–159 | `RollyPayAPI.create_payment` | method | есть: Возвращает (pay_url, provider_payment_id) или (None, None). |
| 161–180 | `RollyPayAPI.get_payment` | method | **нет** |

## `src/shop_bot/modules/heleket_api.py`

Модульный docstring: Клиент для платёжного провайдера Heleket (крипто-эквайринг).

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 26–109 | `create_heleket_payment_request` | function | есть: Создать инвойс в Heleket. |

## `src/shop_bot/modules/cryptobot_api.py`

Модульный docstring: Клиент для платёжного провайдера Crypto Pay (CryptoBot).

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 23–69 | `create_cryptobot_api_invoice` | function | есть: Создать инвойс в Crypto Pay (CryptoBot) в фиате RUB. |

## `src/shop_bot/modules/email_sender.py`

Модульный docstring: Отправка писем с кодом активации email (подтверждение адреса при веб-регистрации).

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 36–42 | `_get_service_name` | function | есть: Название сервиса для From/Subject писем (не хардкод репозитория). |
| 45–64 | `_get_smtp_settings` | function | **нет** |
| 67–72 | `_auth_hint_for_host` | function | **нет** |
| 75–78 | `is_smtp_configured` | function | есть: Проверить, заполнены ли минимально необходимые настройки SMTP. |
| 81–96 | `_send_once` | function | **нет** |
| 99–165 | `send_activation_code` | function | есть: Отправить письмо с одноразовым кодом активации email. |

## `src/shop_bot/modules/telegram_reachability.py`

Модульный docstring: Классификация и обработка ошибок недоступности пользователя в Telegram

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 30–46 | `classify_unreachable_error` | function | есть: Определить, означает ли ошибка отправки недоступность пользователя в Telegram. |
| 49–66 | `handle_send_exception` | function | есть: Проверить ошибку отправки сообщения пользователю и, если она означает |

## `src/shop_bot/core/module_types.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 8–14 | `ModuleStatus` | class | есть: Runtime status for a plugin module. |
| 18–65 | `ModuleMeta` | class | есть: Module manifest metadata. |
| 35–49 | `ModuleMeta.from_dict` | method | **нет** |
| 51–65 | `ModuleMeta.to_dict` | method | **нет** |
| 69–93 | `ModuleInfo` | class | есть: Public-facing module information for UIs. |
| 79–93 | `ModuleInfo.to_dict` | method | **нет** |

## `src/shop_bot/core/module_middleware.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 14–74 | `ModuleSafeMiddleware` | class | есть: Catches module handler errors and marks the module as failed. |
| 17–19 | `ModuleSafeMiddleware.__init__` | method | **нет** |
| 21–44 | `ModuleSafeMiddleware.__call__` | method | **нет** |
| 46–54 | `ModuleSafeMiddleware._is_allowed_callback` | method | **нет** |
| 56–74 | `ModuleSafeMiddleware._notify_admins` | method | **нет** |

## `src/shop_bot/core/module_loader.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 68–77 | `_LoadedModule` | class | **нет** |
| 80–904 | `ModuleLoader` | class | есть: Discovers, loads, and manages plugin modules. |
| 83–92 | `ModuleLoader.__init__` | method | **нет** |
| 94–97 | `ModuleLoader.set_dispatcher` | method | есть: Attach aiogram dispatcher for module router registration. |
| 99–102 | `ModuleLoader.set_flask_app` | method | есть: Attach Flask app for module blueprint registration. |
| 104–131 | `ModuleLoader.discover_modules` | method | есть: Discover module manifests under the modules directory. |
| 133–177 | `ModuleLoader.list_modules` | method | есть: Return a list of modules with status for UI usage. |
| 179–188 | `ModuleLoader.get_module_status` | method | есть: Return current status for a module. |
| 190–226 | `ModuleLoader.load_module` | method | есть: Import module code and prepare its hooks. |
| 228–241 | `ModuleLoader.unload_module` | method | есть: Unload module hooks and imported code. |
| 243–271 | `ModuleLoader.enable_module` | method | есть: Enable a module and register its hooks. |
| 273–284 | `ModuleLoader.disable_module` | method | есть: Disable a module without deleting its data. |
| 286–305 | `ModuleLoader.delete_module` | method | есть: Delete a module and remove its data. |
| 307–317 | `ModuleLoader.get_menu_items` | method | есть: Collect panel menu items from enabled modules. |
| 319–328 | `ModuleLoader.get_settings_schema` | method | есть: Return module settings schema if available. |
| 330–345 | `ModuleLoader.get_settings_values` | method | есть: Return current values for module settings. |
| 347–349 | `ModuleLoader.set_module_error` | method | есть: Mark module as failed with error message. |
| 351–364 | `ModuleLoader._activate_enabled_modules` | method | **нет** |
| 366–373 | `ModuleLoader._load_manifest` | method | **нет** |
| 375–385 | `ModuleLoader._validate_module_meta` | method | **нет** |
| 387–394 | `ModuleLoader._import_from_path` | method | **нет** |
| 396–409 | `ModuleLoader._load_router` | method | **нет** |
| 411–422 | `ModuleLoader._load_blueprint` | method | **нет** |
| 424–444 | `ModuleLoader._load_schema_sql` | method | **нет** |
| 446–457 | `ModuleLoader._load_cleanup` | method | **нет** |
| 459–470 | `ModuleLoader._load_settings_schema` | method | **нет** |
| 472–478 | `ModuleLoader._validate_schema` | method | **нет** |
| 480–489 | `ModuleLoader._apply_schema` | method | **нет** |
| 491–512 | `ModuleLoader._ensure_settings_defaults` | method | **нет** |
| 514–517 | `ModuleLoader._delete_settings_prefix` | method | **нет** |
| 519–538 | `ModuleLoader._attach_router` | method | **нет** |
| 540–552 | `ModuleLoader._detach_router` | method | есть: Detach router from dispatcher. |
| 554–598 | `ModuleLoader._register_blueprint` | method | есть: Store blueprint routes in a registry for dynamic dispatch. |
| 600–606 | `ModuleLoader._unregister_blueprint` | method | есть: Remove registered blueprint routes from the registry. |
| 608–613 | `ModuleLoader._get_dependents` | method | **нет** |
| 615–622 | `ModuleLoader._delete_module_files` | method | **нет** |
| 625–641 | `ModuleLoader._normalize_zip_member_name` | method | есть: Normalize a ZIP member path; return None if the name is unsafe. |
| 644–657 | `ModuleLoader._is_allowed_module_member` | method | есть: Allow only module source/manifest/assets; reject scripts and binaries. |
| 659–675 | `ModuleLoader._resolve_extract_path` | method | есть: Resolve extract destination and ensure it stays under target_root (zip-slip). |
| 677–824 | `ModuleLoader.import_module_from_zip` | method | есть: Import a module from a ZIP file. |
| 826–841 | `ModuleLoader._upsert_registry` | method | **нет** |
| 843–854 | `ModuleLoader._insert_registry` | method | **нет** |
| 856–859 | `ModuleLoader._delete_registry` | method | **нет** |
| 861–872 | `ModuleLoader._set_status` | method | **нет** |
| 874–886 | `ModuleLoader._set_module_buttons_active` | method | есть: Enable or disable buttons associated with a module. |
| 888–894 | `ModuleLoader._get_registry_row` | method | **нет** |
| 896–904 | `ModuleLoader._fetch_registry_rows` | method | **нет** |
| 910–914 | `get_global_module_loader` | function | **нет** |

## `src/shop_bot/webhook_server/app.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 144–157 | `_parse_decimal_amount` | function | **нет** |
| 160–161 | `_setting_flag_enabled` | function | **нет** |
| 164–169 | `_pending_method_allowed` | function | есть: True if pending metadata.payment_method matches one of the allowed provider names. |
| 172–178 | `_pending_expected_amount` | function | **нет** |
| 181–187 | `_platega_amount_covers_order` | function | есть: Platega callback amount is what the customer paid. |
| 190–199 | `_extract_platega_webhook_amount` | function | есть: Platega callback: top-level `amount`, with paymentDetails.amount as fallback. |
| 202–247 | `_dispatch_payment_processing` | function | есть: Fulfill paid orders even when the polling bot loop isn't running. |
| 231–245 | `_dispatch_payment_processing._worker` | nested | **нет** |
| 232–240 | `_dispatch_payment_processing._worker._run` | nested | **нет** |
| 250–297 | `_dispatch_bot_notification` | function | есть: Отправляет произвольное текстовое уведомление пользователю бота из админ-панели |
| 267–272 | `_dispatch_bot_notification._send` | nested | **нет** |
| 282–295 | `_dispatch_bot_notification._worker` | nested | **нет** |
| 283–291 | `_dispatch_bot_notification._worker._run` | nested | **нет** |
| 438–447 | `franchise_settings` | function | есть: Возвращает текущее состояние франшизы. |
| 450–456 | `franchise_menu_button_visible` | function | есть: Видимость пункта «Франшиза» в меню веб-админки (независимо от franchise_enabled). |
| 459–490 | `_run_on_root_bot_loop` | function | есть: Запустить coroutine action(service) на loop root-бота из Flask-потока. |
| 493–503 | `_apply_franchise_runtime` | function | есть: Включить/выключить все клоны на уже работающем event loop. |
| 506–521 | `toggle_franchise_settings` | function | есть: Переключает состояние франшизы (ВКЛ/ВЫКЛ). |
| 531–533 | `_forum_coro_wait` | function | **нет** |
| 536–612 | `run_bulk_ticket_followup` | function | есть: Форум и файлы после массового SQL. Не вызывать из HTTP-потока в проде. |
| 615–7521 | `create_webhook_app` | function | **нет** |
| 665–757 | `create_webhook_app._handle_promo_after_payment` | nested | **нет** |
| 760–797 | `create_webhook_app.inject_current_year` | nested | есть: Inject common variables into all templates |
| 799–805 | `create_webhook_app.login_required` | nested | **нет** |
| 801–804 | `create_webhook_app.login_required.decorated_function` | nested | **нет** |
| 811–820 | `create_webhook_app._rate_limit_login` | nested | **нет** |
| 824–831 | `create_webhook_app._login_client_ip` | nested | есть: IP for login rate-limit. Honor X-Forwarded-For only behind a local proxy. |
| 833–843 | `create_webhook_app._verify_panel_password` | nested | есть: Verify panel password. Prefers bcrypt hashes; legacy plaintext uses compare_digest. |
| 846–886 | `create_webhook_app.login_page` | nested | **нет** |
| 890–893 | `create_webhook_app.logout_page` | nested | **нет** |
| 895–939 | `create_webhook_app.get_common_template_data` | nested | **нет** |
| 943–951 | `create_webhook_app.update_brand_title_route` | nested | **нет** |
| 955–956 | `create_webhook_app.index` | nested | **нет** |
| 960–1000 | `create_webhook_app.dashboard_page` | nested | **нет** |
| 1004–1009 | `create_webhook_app.run_speedtests_route` | nested | **нет** |
| 1014–1022 | `create_webhook_app.dashboard_stats_partial` | nested | **нет** |
| 1026–1030 | `create_webhook_app.dashboard_transactions_partial` | nested | **нет** |
| 1034–1036 | `create_webhook_app.dashboard_charts_json` | nested | **нет** |
| 1041–1279 | `create_webhook_app.statistics_page` | nested | есть: Страница статистики (обзор). |
| 1197–1199 | `create_webhook_app.statistics_page._labels` | nested | **нет** |
| 1285–1299 | `create_webhook_app.analytics_overview_page` | nested | **нет** |
| 1303–1306 | `create_webhook_app.analytics_overview_charts_json` | nested | **нет** |
| 1310–1331 | `create_webhook_app.analytics_transactions_page` | nested | **нет** |
| 1335–1364 | `create_webhook_app.analytics_transactions_csv` | nested | **нет** |
| 1368–1371 | `create_webhook_app.analytics_plans_page` | nested | **нет** |
| 1375–1378 | `create_webhook_app.analytics_payment_methods_page` | nested | **нет** |
| 1382–1394 | `create_webhook_app.analytics_referrals_page` | nested | **нет** |
| 1398–1402 | `create_webhook_app.analytics_coupons_page` | nested | **нет** |
| 1406–1454 | `create_webhook_app.analytics_coupons_create_route` | nested | **нет** |
| 1458–1465 | `create_webhook_app.analytics_coupons_toggle_route` | nested | **нет** |
| 1469–1475 | `create_webhook_app.analytics_coupons_delete_route` | nested | **нет** |
| 1479–1489 | `create_webhook_app.analytics_utm_page` | nested | **нет** |
| 1493–1510 | `create_webhook_app.analytics_utm_create_route` | nested | **нет** |
| 1514–1520 | `create_webhook_app.analytics_utm_delete_route` | nested | **нет** |
| 1527–1533 | `create_webhook_app._referral_program_common` | nested | **нет** |
| 1537–1538 | `create_webhook_app.referral_program_page` | nested | **нет** |
| 1542–1553 | `create_webhook_app.referral_program_settings_page` | nested | **нет** |
| 1557–1576 | `create_webhook_app.referral_program_settings_route` | nested | **нет** |
| 1580–1589 | `create_webhook_app.referral_program_top_page` | nested | **нет** |
| 1593–1604 | `create_webhook_app.referral_program_requests_page` | nested | **нет** |
| 1608–1643 | `create_webhook_app.referral_program_request_status_route` | nested | **нет** |
| 1647–1657 | `create_webhook_app.analytics_economics_page` | nested | **нет** |
| 1661–1673 | `create_webhook_app.analytics_economics_create_route` | nested | **нет** |
| 1677–1680 | `create_webhook_app.analytics_economics_delete_route` | nested | **нет** |
| 1684–1694 | `create_webhook_app.analytics_forecast_page` | nested | **нет** |
| 1700–1710 | `create_webhook_app.analytics_broadcasts_page` | nested | **нет** |
| 1714–1731 | `create_webhook_app.analytics_broadcasts_create` | nested | **нет** |
| 1735–1748 | `create_webhook_app.analytics_broadcasts_update` | nested | **нет** |
| 1752–1755 | `create_webhook_app.analytics_broadcasts_toggle` | nested | **нет** |
| 1759–1764 | `create_webhook_app.analytics_broadcasts_delete` | nested | **нет** |
| 1768–1791 | `create_webhook_app.analytics_broadcasts_send_now` | nested | **нет** |
| 1800–1823 | `create_webhook_app._build_nginx_config` | nested | есть: HTTP-only config; serves ACME webroot so certbot --webroot works. |
| 1825–1863 | `create_webhook_app._build_nginx_ssl_config` | nested | есть: Full SSL config: HTTP → HTTPS redirect + HTTPS reverse proxy. |
| 1867–1878 | `create_webhook_app.webapp_nginx_config_route` | nested | **нет** |
| 1882–2243 | `create_webhook_app.webapp_setup_route` | nested | **нет** |
| 1889–1890 | `create_webhook_app.webapp_setup_route._step` | nested | **нет** |
| 1892–1907 | `create_webhook_app.webapp_setup_route._run` | nested | **нет** |
| 1934–1947 | `create_webhook_app.webapp_setup_route._nginx_reload` | nested | есть: Try nginx -s reload first (works in Docker), fall back to service/systemctl. |
| 1949–1962 | `create_webhook_app.webapp_setup_route._nginx_start` | nested | есть: Start nginx after fresh install (Docker-compatible). |
| 2033–2131 | `create_webhook_app.webapp_setup_route._find_traefik_dynamic_dir` | nested | есть: Return (dynamic_dir, cert_resolver) scanning filesystem then docker. |
| 2133–2176 | `create_webhook_app.webapp_setup_route._write_traefik_config` | nested | **нет** |
| 2247–2263 | `create_webhook_app.webapp_check_route` | nested | **нет** |
| 2267–2278 | `create_webhook_app.monitor_page` | nested | **нет** |
| 2282–2287 | `create_webhook_app.monitor_local_json` | nested | **нет** |
| 2291–2296 | `create_webhook_app.monitor_host_json` | nested | **нет** |
| 2300–2305 | `create_webhook_app.monitor_target_json` | nested | **нет** |
| 2310–2320 | `create_webhook_app.monitor_series_json` | nested | **нет** |
| 2325–2330 | `create_webhook_app.support_table_partial` | nested | **нет** |
| 2334–2346 | `create_webhook_app.support_open_count_partial` | nested | **нет** |
| 2350–2390 | `create_webhook_app.users_page` | nested | **нет** |
| 2395–2422 | `create_webhook_app.users_table_partial` | nested | **нет** |
| 2427–2437 | `create_webhook_app.user_keys_partial` | nested | **нет** |
| 2442–2460 | `create_webhook_app.user_transactions_partial` | nested | **нет** |
| 2465–2470 | `create_webhook_app.user_referrals_json` | nested | **нет** |
| 2474–2499 | `create_webhook_app.users_search_json` | nested | есть: Живой поиск пользователей по ID/username — для модалки "Назначить реферала" |
| 2503–2545 | `create_webhook_app.admin_global_search_json` | nested | есть: Живой поиск по пользователям и ключам для топбара админки. |
| 2549–2579 | `create_webhook_app.assign_referral_route` | nested | есть: Вручную назначить реферала: пользователь `user_id` (из формы) становится |
| 2583–2597 | `create_webhook_app.remove_referral_route` | nested | есть: Снять одного реферала с карточки реферера (обнулить users.referred_by). |
| 2601–2615 | `create_webhook_app.remove_all_referrals_route` | nested | есть: Снять всех рефералов у указанного реферера. |
| 2620–2628 | `create_webhook_app.users_pagination_partial` | nested | **нет** |
| 2632–2682 | `create_webhook_app.user_details_json` | nested | **нет** |
| 2686–2723 | `create_webhook_app.adjust_balance_route` | nested | **нет** |
| 2727–2762 | `create_webhook_app.adjust_referral_balance_route` | nested | **нет** |
| 2766–2803 | `create_webhook_app.admin_keys_page` | nested | **нет** |
| 2808–2819 | `create_webhook_app.admin_keys_table_partial` | nested | **нет** |
| 2823–2839 | `create_webhook_app.admin_keys_pagination_partial` | nested | **нет** |
| 2841–2851 | `create_webhook_app._resolve_key_plan` | nested | есть: Определяет актуальный тариф ключа по plan_id, сохранённому в его description. |
| 2855–2997 | `create_webhook_app.admin_key_details_json` | nested | **нет** |
| 3001–3085 | `create_webhook_app.admin_key_change_plan_route` | nested | **нет** |
| 3089–3146 | `create_webhook_app.admin_key_add_traffic_route` | nested | **нет** |
| 3150–3209 | `create_webhook_app.admin_key_add_lte_traffic_route` | nested | **нет** |
| 3213–3239 | `create_webhook_app.admin_key_delete_device_route` | nested | **нет** |
| 3243–3292 | `create_webhook_app.admin_key_delete_all_devices_route` | nested | **нет** |
| 3296–3310 | `create_webhook_app.admin_get_plans_for_host_json` | nested | **нет** |
| 3314–3398 | `create_webhook_app.create_key_route` | nested | **нет** |
| 3402–3651 | `create_webhook_app.create_key_ajax_route` | nested | есть: Создание ключа через панель: персонального либо универсального подарочного токена. |
| 3655–3664 | `create_webhook_app.generate_key_email_route` | nested | **нет** |
| 3668–3681 | `create_webhook_app.delete_key_route` | nested | **нет** |
| 3685–3755 | `create_webhook_app.adjust_key_expiry_route` | nested | **нет** |
| 3759–3833 | `create_webhook_app.sweep_expired_keys_route` | nested | **нет** |
| 3835–3853 | `create_webhook_app._parse_bulk_expiry_params` | nested | есть: Общие параметры модалки bulk-extend: mode=days\|date + days / expire_at. |
| 3855–3875 | `create_webhook_app._apply_bulk_expiry_to_ids` | nested | **нет** |
| 3877–3883 | `create_webhook_app._flash_bulk_expiry_result` | nested | **нет** |
| 3891–3974 | `create_webhook_app._dispatch_bulk_expiry` | nested | **нет** |
| 3905–3931 | `create_webhook_app._dispatch_bulk_expiry._run` | nested | **нет** |
| 3947–3957 | `create_webhook_app._dispatch_bulk_expiry._job` | nested | **нет** |
| 3978–4006 | `create_webhook_app.bulk_extend_keys_route` | nested | есть: Режим 1: изменить срок у выбранных key_ids (чекбоксы на странице). |
| 4010–4030 | `create_webhook_app.bulk_extend_all_keys_route` | nested | есть: Режим 2: изменить срок у ВСЕХ ключей в vpn_keys (игнорирует фильтры/выбор). |
| 4034–4066 | `create_webhook_app.bulk_extend_user_keys_route` | nested | есть: Изменить срок у всех ключей одного пользователя (карточка пользователя). |
| 4070–4074 | `create_webhook_app.update_key_comment_route` | nested | **нет** |
| 4079–4097 | `create_webhook_app.update_host_ssh_route` | nested | **нет** |
| 4102–4123 | `create_webhook_app.run_ssh_target_speedtest_route` | nested | **нет** |
| 4128–4158 | `create_webhook_app.run_all_ssh_target_speedtests_route` | nested | **нет** |
| 4163–4191 | `create_webhook_app.run_host_speedtest_route` | nested | **нет** |
| 4195–4207 | `create_webhook_app.host_speedtests_json` | nested | **нет** |
| 4211–4241 | `create_webhook_app.run_all_speedtests_route` | nested | **нет** |
| 4246–4270 | `create_webhook_app.auto_install_speedtest_route` | nested | **нет** |
| 4274–4290 | `create_webhook_app.admin_balance_page` | nested | **нет** |
| 4294–4314 | `create_webhook_app.support_list_page` | nested | **нет** |
| 4316–4343 | `create_webhook_app._schedule_bulk_ticket_followup` | nested | **нет** |
| 4335–4339 | `create_webhook_app._schedule_bulk_ticket_followup._job` | nested | **нет** |
| 4347–4363 | `create_webhook_app.support_bulk_close_route` | nested | **нет** |
| 4367–4384 | `create_webhook_app.support_bulk_delete_route` | nested | **нет** |
| 4388–4488 | `create_webhook_app.support_ticket_page` | nested | **нет** |
| 4492–4503 | `create_webhook_app.support_ticket_messages_api` | nested | **нет** |
| 4507–4508 | `create_webhook_app.block_ticket_files_dir` | nested | **нет** |
| 4511–4563 | `create_webhook_app.support_ticket_file` | nested | есть: Отдаёт вложение тикета. |
| 4567–4603 | `create_webhook_app.delete_support_ticket_route` | nested | **нет** |
| 4607–4839 | `create_webhook_app.settings_page` | nested | **нет** |
| 4842–4843 | `create_webhook_app._as_bool` | nested | **нет** |
| 4845–4849 | `create_webhook_app._get_module_info` | nested | **нет** |
| 4851–4877 | `create_webhook_app._build_module_settings_form` | nested | **нет** |
| 4881–4884 | `create_webhook_app.modules_page` | nested | **нет** |
| 4888–4891 | `create_webhook_app.module_enable_route` | nested | **нет** |
| 4895–4898 | `create_webhook_app.module_disable_route` | nested | **нет** |
| 4902–4905 | `create_webhook_app.module_delete_route` | nested | **нет** |
| 4909–4941 | `create_webhook_app.module_settings_page` | nested | **нет** |
| 4946–5021 | `create_webhook_app.module_page_proxy` | nested | есть: Proxy request to module's panel routes if they exist. |
| 5025–5073 | `create_webhook_app.module_upload_route` | nested | есть: Upload and install a module from ZIP file. |
| 5077–5102 | `create_webhook_app.create_ssh_target_route` | nested | **нет** |
| 5106–5128 | `create_webhook_app.update_ssh_target_route` | nested | **нет** |
| 5132–5135 | `create_webhook_app.delete_ssh_target_route` | nested | **нет** |
| 5141–5164 | `create_webhook_app.auto_install_speedtest_on_target_route` | nested | **нет** |
| 5169–5203 | `create_webhook_app.smtp_test_route` | nested | **нет** |
| 5207–5218 | `create_webhook_app.backup_db_route` | nested | **нет** |
| 5222–5263 | `create_webhook_app.restore_db_route` | nested | **нет** |
| 5267–5286 | `create_webhook_app.update_remnawave_settings_route` | nested | **нет** |
| 5290–5299 | `create_webhook_app.add_remnawave_squad_route` | nested | **нет** |
| 5303–5306 | `create_webhook_app.delete_remnawave_squad_route` | nested | **нет** |
| 5310–5340 | `create_webhook_app.update_host_squad_selection_route` | nested | **нет** |
| 5344–5355 | `create_webhook_app.update_host_subscription_route` | nested | **нет** |
| 5359–5367 | `create_webhook_app.update_host_url_route` | nested | **нет** |
| 5371–5386 | `create_webhook_app.update_host_remnawave_route` | nested | **нет** |
| 5390–5400 | `create_webhook_app.add_host_squad_route` | nested | **нет** |
| 5404–5408 | `create_webhook_app.toggle_host_squad_route` | nested | **нет** |
| 5412–5415 | `create_webhook_app.delete_host_squad_route` | nested | **нет** |
| 5419–5427 | `create_webhook_app.rename_host_route` | nested | **нет** |
| 5431–5434 | `create_webhook_app.start_support_bot_route` | nested | **нет** |
| 5436–5443 | `create_webhook_app._wait_for_stop` | nested | **нет** |
| 5447–5451 | `create_webhook_app.stop_support_bot_route` | nested | **нет** |
| 5455–5458 | `create_webhook_app.start_bot_route` | nested | **нет** |
| 5462–5466 | `create_webhook_app.stop_bot_route` | nested | **нет** |
| 5470–5487 | `create_webhook_app.stop_both_bots_route` | nested | **нет** |
| 5489–5494 | `create_webhook_app._soft_stop_controller` | nested | есть: Остановить контроллер; если уже остановлен — считать успехом (для перезапуска). |
| 5498–5521 | `create_webhook_app.restart_both_bots_route` | nested | есть: Остановить оба бота, дождаться остановки и сразу запустить снова — без ручного stop→start. |
| 5525–5540 | `create_webhook_app.start_both_bots_route` | nested | **нет** |
| 5544–5587 | `create_webhook_app.ban_user_route` | nested | **нет** |
| 5591–5611 | `create_webhook_app.unban_user_route` | nested | **нет** |
| 5615–5664 | `create_webhook_app.delete_user_route` | nested | есть: Полное удаление пользователя (как admin_delete_user в боте). |
| 5668–5710 | `create_webhook_app.revoke_keys_route` | nested | **нет** |
| 5714–5765 | `create_webhook_app.add_host_route` | nested | **нет** |
| 5769–5772 | `create_webhook_app.delete_host_route` | nested | **нет** |
| 5776–5823 | `create_webhook_app.add_plan_route` | nested | **нет** |
| 5827–5830 | `create_webhook_app.delete_plan_route` | nested | **нет** |
| 5834–5847 | `create_webhook_app.toggle_plan_route` | nested | **нет** |
| 5851–5907 | `create_webhook_app.update_plan_route` | nested | **нет** |
| 5909–5911 | `create_webhook_app._normalize_package_pool` | nested | есть: Пул пакета докупки: 'lte' (💰 premium-ноды) или 'main' (основной трафик). |
| 5915–5930 | `create_webhook_app.admin_get_traffic_packages_for_plan_json` | nested | **нет** |
| 5934–5954 | `create_webhook_app.add_traffic_package_route` | nested | **нет** |
| 5958–5981 | `create_webhook_app.update_traffic_package_route` | nested | **нет** |
| 5985–5993 | `create_webhook_app.toggle_traffic_package_route` | nested | **нет** |
| 5997–6000 | `create_webhook_app.delete_traffic_package_route` | nested | **нет** |
| 6004–6012 | `create_webhook_app._get_client_ip` | nested | есть: Best-effort client IP (supports reverse proxy via X-Forwarded-For). |
| 6014–6018 | `create_webhook_app._is_ip_allowed` | nested | **нет** |
| 6020–6024 | `create_webhook_app._debug_endpoints_allowed` | nested | **нет** |
| 6026–6036 | `create_webhook_app._http_json` | nested | есть: Minimal JSON HTTP client via urllib (avoids extra deps). |
| 6038–6051 | `create_webhook_app._yookassa_get_payment` | nested | **нет** |
| 6053–6066 | `create_webhook_app._cryptobot_verify_signature` | nested | **нет** |
| 6068–6088 | `create_webhook_app._cryptobot_get_invoice` | nested | **нет** |
| 6090–6102 | `create_webhook_app._require_ton_webhook_secret` | nested | **нет** |
| 6106–6213 | `create_webhook_app.yookassa_webhook_handler` | nested | есть: YooKassa webhook (secure). |
| 6217–6223 | `create_webhook_app.test_webhook` | nested | есть: Тестовый endpoint. В продакшне отключен по умолчанию. |
| 6227–6248 | `create_webhook_app.debug_all_requests` | nested | есть: Опасный debug endpoint: возвращает заголовки/куки/данные. В продакшне отключен по умолчанию. |
| 6252–6355 | `create_webhook_app.yoomoney_webhook_handler` | nested | есть: ЮMoney HTTP уведомление (кнопка/ссылка p2p). Подпись: sha1(notification_type&operation_id&amount&cur |
| 6360–6474 | `create_webhook_app.platega_webhook_handler` | nested | есть: Platega webhook. Авторизация: заголовки X-MerchantId / X-Secret. Payload содержит статус и поле payl |
| 6478–6625 | `create_webhook_app.rollypay_webhook_handler` | nested | есть: RollyPay webhook. |
| 6629–6774 | `create_webhook_app.cryptobot_webhook_handler` | nested | есть: Crypto Pay API webhook (secure). |
| 6778–6862 | `create_webhook_app.heleket_webhook_handler` | nested | **нет** |
| 6866–6920 | `create_webhook_app.ton_webhook_handler` | nested | есть: TonAPI webhook (hardened): |
| 6926–6934 | `create_webhook_app._ym_get_redirect_uri` | nested | **нет** |
| 6938–6955 | `create_webhook_app.yoomoney_connect_route` | nested | **нет** |
| 6960–7003 | `create_webhook_app.yoomoney_callback_route` | nested | **нет** |
| 7007–7047 | `create_webhook_app.yoomoney_check_route` | nested | **нет** |
| 7053–7061 | `create_webhook_app.get_button_configs_api` | nested | есть: Get button configurations for a specific menu type (including inactive for admin) |
| 7066–7093 | `create_webhook_app.create_button_config_api` | nested | есть: Create a new button configuration |
| 7098–7125 | `create_webhook_app.update_button_config_api` | nested | есть: Update an existing button configuration |
| 7130–7140 | `create_webhook_app.delete_button_config_api` | nested | есть: Delete a button configuration |
| 7145–7163 | `create_webhook_app.reorder_button_configs_api` | nested | есть: Reorder button configurations for a menu type |
| 7169–7172 | `create_webhook_app._franchise_db_connect` | nested | **нет** |
| 7174–7232 | `create_webhook_app._franchise_totals` | nested | **нет** |
| 7234–7291 | `create_webhook_app._franchise_list_bots` | nested | **нет** |
| 7293–7307 | `create_webhook_app._franchise_get_bot` | nested | **нет** |
| 7309–7358 | `create_webhook_app._franchise_bot_stats` | nested | **нет** |
| 7362–7367 | `create_webhook_app.franchise_page` | nested | **нет** |
| 7371–7433 | `create_webhook_app.franchise_bot_page` | nested | **нет** |
| 7437–7462 | `create_webhook_app.franchise_toggle_bot_route` | nested | **нет** |
| 7466–7489 | `create_webhook_app.franchise_delete_bot_route` | nested | **нет** |
| 7493–7512 | `create_webhook_app.franchise_withdraw_status_route` | nested | **нет** |
| 7516–7519 | `create_webhook_app.button_constructor_page` | nested | есть: Button constructor page |
| 7526–7528 | `_coerce_checkbox` | function | **нет** |

## `src/shop_bot/webhook_server/apply_app_fix.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 13–23 | `normalize_list` | function | **нет** |

## `src/shop_bot/webapp/handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 68–76 | `_create_payload_pending_or_error` | function | есть: Создать pending; если слот промокода уже занят — вернуть ошибку для API. |
| 110–117 | `_email_auth_rate_limit_response` | function | **нет** |
| 120–135 | `_email_auth_rate_limited` | function | есть: True, если по этому email уже исчерпан EMAIL_AUTH_PER_EMAIL_LIMIT за окно. |
| 138–141 | `_reject_if_email_auth_rate_limited` | function | **нет** |
| 144–164 | `_resolve_user_from_request_token` | function | **нет** |
| 167–188 | `_resolve_authenticated_user` | function | есть: Определить текущего пользователя ИСКЛЮЧИТЕЛЬНО по доверенным источникам: |
| 191–192 | `_unauthorized` | function | **нет** |
| 195–215 | `_require_authenticated_user` | function | есть: Resolve caller from auth_token / Bearer / signed init_data only (CWE-862/639). |
| 218–220 | `_ref_setting_is_true` | function | **нет** |
| 223–231 | `_ref_method_type_enabled` | function | **нет** |
| 235–262 | `get_transaction_comment` | function | есть: Короткое человекочитаемое описание платежа — для поля description в |
| 264–289 | `calculate_webapp_price` | function | **нет** |
| 292–294 | `notify_admin_of_purchase` | function | **нет** |
| 296–298 | `process_successful_payment` | function | **нет** |
| 300–314 | `_send_telegram_message` | function | **нет** |
| 316–335 | `_send_invoice_stars` | function | **нет** |
| 357–362 | `_platega_api` | function | **нет** |
| 365–373 | `_store_platega_transaction_id` | function | **нет** |
| 376–380 | `_rollypay_is_enabled` | function | **нет** |
| 383–387 | `_rollypay_api` | function | **нет** |
| 390–398 | `_store_rollypay_payment_id` | function | **нет** |
| 401–416 | `_fulfill_webapp_paid_order` | function | **нет** |
| 423–435 | `_build_yoomoney_link` | function | **нет** |
| 442–449 | `_webapp_no_cache_middleware` | function | **нет** |
| 460–462 | `_hidden_not_found` | function | есть: Как несуществующий URL: стандартный FastAPI 404, без Unauthorized. |
| 467–469 | `_block_ticket_files_dir` | function | есть: Каталог ticket_files не является static и не должен открываться по URL. |
| 474–494 | `api_referral_payout_methods_list` | function | **нет** |
| 499–523 | `api_referral_payout_methods_add` | function | **нет** |
| 527–553 | `api_referral_available_method_types` | function | **нет** |
| 557–575 | `api_referral_payout_methods_delete` | function | **нет** |
| 579–599 | `api_key_auto_renew` | function | **нет** |
| 604–648 | `api_referral_request_withdraw` | function | **нет** |
| 653–684 | `api_referral_list_withdrawals` | function | **нет** |
| 687–709 | `_format_remaining_details` | function | **нет** |
| 711–726 | `_format_bytes` | function | **нет** |
| 728–776 | `_process_template_placeholders` | function | **нет** |
| 778–785 | `_format_bytes_gb` | function | есть: Тот же формат ГБ, что в карточке ключа бота. |
| 788–793 | `_format_gb_amount` | function | **нет** |
| 796–815 | `_is_key_without_billing_plan` | function | есть: Триал/подарок: биллингового тарифа нет — докупка LTE недоступна (как в боте). |
| 818–842 | `_resolve_plan_id_for_key` | function | есть: plan_id из description JSON, иначе первый активный тариф хоста (как в боте). |
| 845–895 | `_lte_card_state` | function | есть: Условия и цифры LTE-пула — те же, что в карточке ключа бота. |
| 898–909 | `_owned_lte_key_and_plan` | function | есть: Ключ принадлежит user_id и доступен для LTE-докупки. Иначе (None, None). |
| 912–1042 | `_process_key_data` | function | **нет** |
| 1044–1089 | `_get_key_html` | function | **нет** |
| 1091–1220 | `_get_profile_card_html` | function | **нет** |
| 1222–1351 | `_get_key_card_html` | function | есть: Render the full key-card block (used for regular keys and, with an extra |
| 1353–1364 | `_key_created_sort_tuple` | function | есть: Sort key for newest-purchased-first: created_at desc, then key_id desc. |
| 1367–1368 | `_sort_keys_newest_first` | function | **нет** |
| 1371–1378 | `_get_profile_keys_html` | function | **нет** |
| 1380–1464 | `_get_setup_keys_html` | function | **нет** |
| 1466–1512 | `_get_renew_keys_html` | function | **нет** |
| 1514–1525 | `_get_no_key_html` | function | **нет** |
| 1529–1548 | `_duration_label` | function | **нет** |
| 1551–1562 | `_days_from_plan` | function | **нет** |
| 1565–1566 | `_billing_months_for_plan` | function | **нет** |
| 1569–1637 | `_build_plans_grid_html` | function | **нет** |
| 1640–1683 | `_get_servers_and_plans_html` | function | **нет** |
| 1686–1765 | `_render_banned_page` | function | **нет** |
| 1768–1966 | `_render_main_page` | function | **нет** |
| 1970–2010 | `index` | function | **нет** |
| 2014–2017 | `SupportStatusRequest` | class | **нет** |
| 2019–2023 | `SupportTicketCreateRequest` | class | **нет** |
| 2025–2030 | `SupportMessageSendRequest` | class | **нет** |
| 2032–2036 | `SupportTicketRequest` | class | **нет** |
| 2038–2041 | `PaymentMethodsRequest` | class | **нет** |
| 2043–2044 | `TokenRequest` | class | **нет** |
| 2046–2048 | `TelegramDirectAuthRequest` | class | есть: Must carry signed Telegram WebApp initData — never a bare user_id. |
| 2050–2052 | `EmailAuthRequest` | class | **нет** |
| 2054–2056 | `EmailVerifyRequest` | class | **нет** |
| 2058–2059 | `EmailResendRequest` | class | **нет** |
| 2061–2062 | `PasswordResetRequest` | class | **нет** |
| 2064–2066 | `PasswordResetCheckRequest` | class | **нет** |
| 2068–2071 | `PasswordResetVerifyRequest` | class | **нет** |
| 2079–2080 | `_hash_password_reset_code` | function | **нет** |
| 2083–2090 | `_password_reset_code_matches` | function | **нет** |
| 2092–2094 | `SyncTgRequest` | class | **нет** |
| 2097–2098 | `DeviceTiersRequest` | class | **нет** |
| 2100–2111 | `CreatePaymentRequest` | class | **нет** |
| 2113–2118 | `CreateTopUpPaymentRequest` | class | **нет** |
| 2120–2126 | `CreateLteTopUpPaymentRequest` | class | **нет** |
| 2128–2134 | `ApplyPromoRequest` | class | **нет** |
| 2136–2140 | `RenameKeyRequest` | class | **нет** |
| 2142–2146 | `DeleteAllDevicesRequest` | class | **нет** |
| 2148–2151 | `SearchKeysRequest` | class | **нет** |
| 2156–2222 | `validate_telegram_data` | function | есть: Verify Telegram WebApp initData HMAC and freshness (auth_date). |
| 2225–2239 | `_issue_persistent_token_for_telegram_user` | function | есть: Shared token issue/lookup used by /api/auth/token and /api/auth/telegram-direct. |
| 2244–2255 | `api_request_auth_token` | function | **нет** |
| 2259–2297 | `api_check_auth_token` | function | **нет** |
| 2301–2316 | `api_create_token` | function | есть: Generate or retrieve a persistent login token using verified Telegram data. |
| 2321–2354 | `api_telegram_direct_auth` | function | есть: Authenticate inside Telegram WebApp using signed initData only. |
| 2356–2375 | `_validate_password` | function | есть: Проверка пароля при регистрации / сбросе / смене. |
| 2381–2410 | `_issue_email_verification_code` | function | есть: Сгенерировать, сохранить и отправить новый код подтверждения email. |
| 2415–2440 | `api_email_register` | function | **нет** |
| 2444–2461 | `api_email_verify` | function | **нет** |
| 2465–2488 | `api_email_resend` | function | **нет** |
| 2492–2509 | `api_email_login` | function | **нет** |
| 2513–2546 | `api_email_reset_request` | function | **нет** |
| 2550–2566 | `api_email_reset_check` | function | **нет** |
| 2570–2595 | `api_email_reset_verify` | function | **нет** |
| 2607–2623 | `api_user_profile_info` | function | **нет** |
| 2627–2651 | `api_user_profile_change_password` | function | **нет** |
| 2655–2689 | `api_user_profile_change_email_request` | function | **нет** |
| 2693–2725 | `api_user_profile_change_email_resend` | function | **нет** |
| 2729–2749 | `api_user_profile_change_email_verify` | function | **нет** |
| 2753–2764 | `api_user_profile_change_email_cancel` | function | **нет** |
| 2769–2793 | `api_sync_tg` | function | **нет** |
| 2797–2813 | `api_device_tiers` | function | **нет** |
| 2816–2872 | `api_get_payment_methods` | function | **нет** |
| 2876–3332 | `api_create_payment` | function | **нет** |
| 3335–3371 | `_rollback_internal_payment` | function | есть: Идемпотентный откат списания Balance/ReferralBalance + лог PAYMENT_ROLLBACK. |
| 3374–3386 | `_platega_method_code_from_settings` | function | **нет** |
| 3390–3694 | `api_create_topup_payment` | function | есть: Create a balance top-up payment (action=top_up), mirroring the bot TopUpProcess flow. |
| 3697–3710 | `_lte_topup_metadata` | function | есть: Метаданные те же, что бот кладёт в pending для process_successful_payment. |
| 3714–3745 | `api_lte_packages` | function | есть: Пакеты докупки LTE для ключа владельца. Цена/размер только с сервера. |
| 3749–4035 | `api_create_lte_topup_payment` | function | есть: Оплата докупки LTE: те же методы, что в боте; цена берётся из пакета в БД. |
| 4038–4083 | `api_apply_promo` | function | есть: Проверить промокод и посчитать цену со скидкой. |
| 4085–4088 | `CheckPaymentRequest` | class | **нет** |
| 4091–4097 | `_check_payment_unpaid` | function | есть: Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена. |
| 4101–4140 | `api_check_payment` | function | **нет** |
| 4143–4145 | `VerifyPlategaPaymentRequest` | class | **нет** |
| 4148–4149 | `_platega_verify_error` | function | **нет** |
| 4153–4365 | `api_verify_platega_payment` | function | есть: Сверить pending Platega-заказ с GET /transaction/{id} и выдать ключ тем же путём, что webhook. |
| 4367–4372 | `KeyActionRequest` | class | **нет** |
| 4374–4380 | `DeleteDeviceRequest` | class | **нет** |
| 4382–4387 | `CommentRequest` | class | **нет** |
| 4389–4393 | `GiftActivateRequest` | class | **нет** |
| 4397–4429 | `api_user_referral_info` | function | **нет** |
| 4432–4448 | `_gift_link_row_html` | function | есть: Одна строка со ссылкой активации подарка: текст ссылки + копировать + поделиться. |
| 4451–4478 | `_get_gift_action_block_html` | function | есть: Общий блок для неактивированного подарка: обе ссылки активации |
| 4481–4502 | `_get_gift_fallback_card_html` | function | есть: Карточка подарка на случай, если связанный VPN-ключ не найден (например, |
| 4506–4559 | `api_user_gifts` | function | **нет** |
| 4568–4636 | `_activate_gift_for_user` | function | есть: Активировать подарок `gift_code` для пользователя `user_id`. |
| 4641–4656 | `api_gift_activate` | function | **нет** |
| 4673–4709 | `_apply_pending_referral` | function | есть: Привязать пользователя к рефереру и, если применимо, выплатить |
| 4713–4716 | `PendingActionCompleteRequest` | class | **нет** |
| 4719–4759 | `_pending_action_public_info` | function | есть: Собрать безопасный (без лишних деталей) ответ для UI по pending action — |
| 4763–4768 | `api_pending_action_info` | function | **нет** |
| 4772–4862 | `api_pending_action_complete` | function | есть: Единая точка завершения pending action ПОСЛЕ успешной авторизации. |
| 4865–4893 | `api_key_devices` | function | **нет** |
| 4896–4925 | `api_key_device_delete` | function | **нет** |
| 4928–4947 | `api_key_comment` | function | **нет** |
| 4949–4953 | `_support_rate_response` | function | **нет** |
| 4956–4966 | `_support_user_rate_limited` | function | **нет** |
| 4969–4979 | `_support_too_fast` | function | **нет** |
| 4982–4983 | `_clip_support_text` | function | **нет** |
| 4986–4993 | `_tickets_created_today_count` | function | **нет** |
| 4996–5002 | `_public_ticket_row` | function | **нет** |
| 5005–5013 | `_public_ticket_messages` | function | **нет** |
| 5016–5022 | `_ticket_owned_by` | function | **нет** |
| 5025–5077 | `_notify_webapp_support` | function | **нет** |
| 5081–5113 | `api_support_status` | function | **нет** |
| 5117–5161 | `api_support_create` | function | **нет** |
| 5165–5206 | `api_support_send` | function | **нет** |
| 5210–5234 | `api_support_ticket` | function | **нет** |
| 5239–5268 | `api_support_close` | function | **нет** |
| 5272–5311 | `api_support_ticket_file` | function | есть: Вложение только владельцу. Без сессии и при чужом id — тот же 404, что у несуществующего URL. |
| 5316–5372 | `api_support_upload` | function | **нет** |
| 5375–5392 | `api_user_status` | function | **нет** |
| 5395–5417 | `api_key_rename` | function | **нет** |
| 5420–5461 | `api_key_devices_delete_all` | function | **нет** |
| 5464–5515 | `api_user_transactions` | function | **нет** |
| 5518–5542 | `api_keys_search` | function | **нет** |
| 5544–5546 | `_html_esc` | function | есть: Экранировать значение для вставки в HTML-текст или атрибут (CWE-79). |
| 5560–5565 | `_public_fallback_response` | function | **нет** |
| 5568–5576 | `_parse_public_referrer_id` | function | есть: Только положительный int. Невалидный path не должен попадать в HTML/URL. |
| 5579–5583 | `_safe_public_gift_code` | function | **нет** |
| 5586–5592 | `_telegram_bot_deeplink` | function | **нет** |
| 5595–5598 | `_html_telegram_btn` | function | **нет** |
| 5601–5630 | `_referral_fallback_html` | function | есть: Резервная страница рефссылки (реферер не найден/бот не настроен) — |
| 5634–5677 | `web_referral_page` | function | есть: Публичная реферальная ссылка. |
| 5679–5702 | `_gift_fallback_html` | function | есть: Резервная страница подарка (не найден/уже активирован) — как и раньше, |
| 5706–5770 | `web_gift_page` | function | есть: Публичная ссылка активации подарка. |
| 5773–5805 | `dynamic_route` | function | **нет** |

## `src/shop_bot/support_bot/handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 32–35 | `SupportDialog` | class | **нет** |
| 38–39 | `AdminDialog` | class | **нет** |
| 42–1143 | `get_support_router` | function | **нет** |
| 45–52 | `get_support_router._user_main_reply_kb` | nested | **нет** |
| 54–61 | `get_support_router._is_user_banned` | nested | **нет** |
| 63–71 | `get_support_router._get_latest_open_ticket` | nested | **нет** |
| 73–114 | `get_support_router._admin_actions_kb` | nested | **нет** |
| 116–124 | `get_support_router._is_admin` | nested | **нет** |
| 127–162 | `get_support_router.start_handler` | nested | **нет** |
| 165–187 | `get_support_router.support_new_ticket_handler` | nested | **нет** |
| 190–203 | `get_support_router.support_subject_received` | nested | **нет** |
| 205–209 | `get_support_router._save_ticket_media` | nested | **нет** |
| 212–319 | `get_support_router.support_message_received` | nested | **нет** |
| 322–336 | `get_support_router.support_my_tickets_handler` | nested | **нет** |
| 339–369 | `get_support_router.support_view_ticket_handler` | nested | **нет** |
| 372–394 | `get_support_router.support_reply_prompt_handler` | nested | **нет** |
| 397–494 | `get_support_router.support_reply_received` | nested | **нет** |
| 497–564 | `get_support_router.forum_thread_message_handler` | nested | **нет** |
| 567–610 | `get_support_router.support_close_ticket_handler` | nested | **нет** |
| 613–649 | `get_support_router.admin_close_ticket` | nested | **нет** |
| 652–688 | `get_support_router.admin_reopen_ticket` | nested | **нет** |
| 691–743 | `get_support_router.admin_delete_ticket` | nested | **нет** |
| 746–815 | `get_support_router.admin_toggle_star` | nested | **нет** |
| 818–843 | `get_support_router.admin_show_user` | nested | **нет** |
| 845–867 | `get_support_router._support_contact_markup` | nested | **нет** |
| 869–877 | `get_support_router._notify_user_about_ban` | nested | **нет** |
| 880–908 | `get_support_router.admin_ban_user` | nested | **нет** |
| 911–942 | `get_support_router.admin_unban_user` | nested | **нет** |
| 945–959 | `get_support_router.admin_note_prompt` | nested | **нет** |
| 962–984 | `get_support_router.admin_list_notes` | nested | **нет** |
| 987–1005 | `get_support_router.admin_note_receive` | nested | **нет** |
| 1008–1016 | `get_support_router.start_text_button` | nested | **нет** |
| 1019–1027 | `get_support_router.new_ticket_text_button` | nested | **нет** |
| 1030–1041 | `get_support_router.my_tickets_text_button` | nested | **нет** |
| 1044–1141 | `get_support_router.relay_user_message_to_forum` | nested | **нет** |

## `src/shop_bot/support_bot/idle_close.py`

Модульный docstring: Автозакрытие открытых тикетов, если после ответа админа пользователь молчит N дней.

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 18–27 | `_ru_days_word` | function | **нет** |
| 30–32 | `_forum_wait` | function | **нет** |
| 35–120 | `run_idle_close_followup` | function | есть: Темы форума и короткое уведомление пользователю. Не из HTTP-потока. |
| 123–151 | `maybe_auto_close_idle_tickets` | function | есть: Закрывает пачку простаивающих тикетов. Telegram — в фоне, SQL сразу. |
| 154–158 | `_run_followup_safe` | function | **нет** |

## `src/shop_bot/support_bot/ticket_media.py`

Модульный docstring: Локальные вложения тикетов поддержки.

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 41–53 | `detect_image_kind_bytes` | function | есть: Расширение и MIME по сигнатуре. None — не jpeg/png/webp/pdf. |
| 56–62 | `detect_image_kind` | function | **нет** |
| 65–76 | `media_kind_from_stored` | function | есть: image \| pdf \| file по имени на диске. Сырой путь наружу не отдаём. |
| 79–90 | `public_support_message` | function | есть: Поля сообщения для панели/JSON без пути ticket_files. |
| 93–103 | `positive_file_size` | function | есть: Положительный размер в байтах или None, если Telegram его не дал. |
| 106–131 | `resolve_telegram_file_size` | function | есть: Размер до download. Всегда getFile, если бот его умеет. |
| 134–151 | `_CappedSeekBuffer` | class | есть: BytesIO с seek (его зовёт aiogram) и потолком, чтобы не держать 20 МБ в RAM. |
| 137–140 | `_CappedSeekBuffer.__init__` | method | **нет** |
| 142–151 | `_CappedSeekBuffer.write` | method | **нет** |
| 154–193 | `download_ticket_media_capped` | function | есть: Качаем в буфер с seek и потолком 10 МБ, затем на диск. |
| 196–210 | `declared_size_over_limit` | function | есть: True, если Telegram уже сообщил размер больше лимита. |
| 213–234 | `ticket_folder_usage` | function | есть: Число финальных файлов и их суммарный размер. ``*.part`` не считаем. |
| 237–261 | `quota_blocks_new_file` | function | есть: True, если ещё одно вложение превысит квоту тикета (10 файлов / 30 МБ). |
| 264–280 | `jailed_ticket_folder` | function | есть: Каталог вложений тикета строго внутри media root, иначе None. |
| 283–289 | `closed_ttl_days` | function | **нет** |
| 292–305 | `parse_ticket_updated_at` | function | **нет** |
| 308–322 | `closed_ticket_media_expired` | function | есть: True, если тикет закрыт дольше TTL — файлы пора снять. |
| 325–337 | `ticket_media_on_disk` | function | есть: True, если в ticket_files есть хоть одна запись. Без SQL и без полного обхода. |
| 340–349 | `expire_ticket_media_if_closed_ttl` | function | есть: Если тикет закрыт дольше TTL — удаляет файлы и обнуляет media. True = истекло. |
| 352–418 | `purge_expired_closed_ticket_media` | function | есть: Снимает каталоги закрытых тикетов старше TTL и осиротевшие папки. |
| 421–434 | `maybe_purge_expired_closed_ticket_media` | function | есть: Не чаще раза в час. Нет файлов — сразу выход, таймер не заводим. |
| 437–447 | `delete_ticket_media_dir` | function | есть: Удаляет ``ticket_files/<ticket_id>/``. Не трогает соседние тикеты и корень. |
| 450–484 | `commit_ticket_image` | function | есть: Размер + magic. Возвращает ``stem.ext`` или None; ``*.part`` удаляется при отказе. |
| 487–493 | `remove_empty_ticket_folder` | function | есть: Снимает пустой ``ticket_files/<id>/`` после неудачного save. |
| 496–502 | `_unlink_quiet` | function | **нет** |
| 505–513 | `document_may_be_ticket_media` | function | есть: Документ можно скачать: картинка или PDF. Тип всё равно подтвердит magic. |
| 516–563 | `save_ticket_media_bytes` | function | есть: Сохраняет вложение из WebApp (байты), те же jail/квота/magic, что у бота. |
| 566–641 | `save_ticket_media` | function | есть: Сохраняет изображение из сообщения. Контракт как у прежнего хелпера. |

## `src/shop_bot/factory_bot/runtime.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 7–9 | `set_service` | function | **нет** |
| 11–12 | `get_service` | function | **нет** |

## `src/shop_bot/factory_bot/middleware.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 13–15 | `invalidate_franchise_enabled_cache` | function | **нет** |
| 18–32 | `franchise_enabled_cached` | function | есть: Лёгкий кэш флага франшизы, чтобы middleware не ходила в SQL на каждое сообщение. |
| 35–65 | `FactoryStatsMiddleware` | class | есть: Tracks basic stats (messages + unique users) per factory bot instance. |
| 37–65 | `FactoryStatsMiddleware.__call__` | method | **нет** |

## `src/shop_bot/factory_bot/keyboards.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 4–10 | `cabinet_menu` | function | **нет** |
| 12–17 | `delete_bot_confirm` | function | **нет** |

## `src/shop_bot/factory_bot/handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 19–28 | `_parse_bot_id_from_callback` | function | **нет** |
| 31–105 | `get_owner_cabinet_router` | function | есть: Кабинет владельца текущего клона: просмотр и удаление ЭТОГО бота. |
| 36–57 | `get_owner_cabinet_router.cabinet` | nested | **нет** |
| 60–75 | `get_owner_cabinet_router.delete_self_ask` | nested | **нет** |
| 78–103 | `get_owner_cabinet_router.delete_bot_confirm` | nested | **нет** |

## `src/shop_bot/factory_bot/service.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 20–148 | `ManagedBotsService` | class | **нет** |
| 21–26 | `ManagedBotsService.__init__` | method | **нет** |
| 28–30 | `ManagedBotsService.get_bot` | method | есть: Возвращает экземпляр Bot для bot_id, если он запущен. |
| 32–35 | `ManagedBotsService._drop_bot_refs` | method | **нет** |
| 37–39 | `ManagedBotsService._has_running_task` | method | **нет** |
| 41–50 | `ManagedBotsService.start_all` | method | **нет** |
| 52–111 | `ManagedBotsService.start_bot` | method | **нет** |
| 113–132 | `ManagedBotsService.stop_bot` | method | есть: Остановить один клон. Идемпотентно: повторный вызов безопасен. |
| 134–137 | `ManagedBotsService.restart_bot` | method | есть: Перезапуск клона (смена токена владельцем). |
| 139–148 | `ManagedBotsService.stop_all` | method | **нет** |

## `modules/example_module/bot_handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 7–9 | `example_ping` | function | **нет** |

## `modules/example_module/db_cleanup.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 1–5 | `cleanup` | function | **нет** |

## `modules/example_module/panel_routes.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 12–13 | `index` | function | **нет** |

## `modules/ramadan_tracker/bot_handlers.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 27–28 | `WithdrawalStates` | class | **нет** |
| 33–37 | `open_ramadan_tracker` | function | **нет** |
| 41–45 | `open_ramadan_tracker_callback` | function | **нет** |
| 49–52 | `show_adhkar_menu` | function | **нет** |
| 56–59 | `show_adhkar_morning` | function | **нет** |
| 63–66 | `show_adhkar_evening` | function | **нет** |
| 70–75 | `mark_morning_read` | function | **нет** |
| 79–84 | `mark_morning_missed` | function | **нет** |
| 88–93 | `mark_evening_read` | function | **нет** |
| 97–102 | `mark_evening_missed` | function | **нет** |
| 106–109 | `show_salawat_menu` | function | **нет** |
| 113–118 | `add_salawat_one` | function | **нет** |
| 122–125 | `show_taraweeh_menu` | function | **нет** |
| 129–134 | `mark_taraweeh_mosque` | function | **нет** |
| 138–143 | `mark_taraweeh_home` | function | **нет** |
| 147–152 | `mark_taraweeh_missed` | function | **нет** |
| 156–159 | `show_today_stats` | function | **нет** |
| 163–166 | `show_total_stats` | function | **нет** |
| 170–174 | `show_top` | function | **нет** |
| 178–187 | `reward_top_user` | function | **нет** |
| 191–225 | `request_withdraw` | function | **нет** |
| 229–235 | `show_admin_menu` | function | **нет** |
| 239–245 | `show_admin_stats` | function | **нет** |
| 249–255 | `show_admin_top` | function | **нет** |
| 259–265 | `show_admin_withdrawals` | function | **нет** |
| 269–288 | `delete_withdrawal_request` | function | **нет** |
| 292–317 | `complete_withdrawal_request` | function | **нет** |
| 321–337 | `complete_without_proof` | function | **нет** |
| 341–367 | `handle_proof_photo` | function | **нет** |
| 370–390 | `_build_menu_text` | function | **нет** |
| 393–404 | `_build_today_stats_text` | function | **нет** |
| 407–416 | `_build_total_stats_text` | function | **нет** |
| 419–427 | `_build_adhkar_menu_text` | function | **нет** |
| 430–435 | `_build_adhkar_detail_text` | function | **нет** |
| 438–447 | `_build_salawat_menu_text` | function | **нет** |
| 450–458 | `_build_taraweeh_menu_text` | function | **нет** |
| 461–484 | `_build_top_text` | function | **нет** |
| 487–488 | `_build_admin_menu_text` | function | **нет** |
| 491–501 | `_build_admin_stats_text` | function | **нет** |
| 504–513 | `_build_admin_top_text` | function | **нет** |
| 516–531 | `_build_admin_withdrawals_text` | function | **нет** |
| 534–559 | `_build_admin_withdrawals_keyboard` | function | **нет** |
| 562–574 | `_build_menu_keyboard` | function | **нет** |
| 577–583 | `_build_back_keyboard` | function | **нет** |
| 586–594 | `_build_top_keyboard` | function | **нет** |
| 597–603 | `_build_adhkar_menu_keyboard` | function | **нет** |
| 606–612 | `_build_adhkar_detail_keyboard` | function | **нет** |
| 615–620 | `_build_salawat_menu_keyboard` | function | **нет** |
| 623–630 | `_build_taraweeh_menu_keyboard` | function | **нет** |
| 633–640 | `_build_admin_menu_keyboard` | function | **нет** |
| 643–647 | `_build_admin_back_keyboard` | function | **нет** |
| 650–662 | `_safe_edit` | function | **нет** |
| 665–666 | `_today_str` | function | **нет** |
| 669–670 | `_is_admin` | function | **нет** |
| 673–687 | `_get_settings` | function | **нет** |
| 677–678 | `_get_settings._get` | nested | **нет** |
| 690–695 | `_to_bool` | function | **нет** |
| 698–702 | `_to_int` | function | **нет** |
| 705–709 | `_to_float` | function | **нет** |
| 712–731 | `_get_daily_row` | function | **нет** |
| 734–741 | `_ensure_daily_row` | function | **нет** |
| 744–762 | `_set_adhkar_status` | function | **нет** |
| 765–778 | `_add_salawat` | function | **нет** |
| 783–809 | `_set_taraweeh` | function | **нет** |
| 812–834 | `_get_total_stats` | function | **нет** |
| 837–859 | `_get_global_stats` | function | **нет** |
| 862–885 | `_get_top_rows` | function | **нет** |
| 888–903 | `_ensure_auto_payout` | function | **нет** |
| 906–941 | `_generate_rewards` | function | **нет** |
| 944–951 | `_reward_already_given` | function | **нет** |
| 954–964 | `_save_reward` | function | **нет** |
| 967–974 | `_period_generated` | function | **нет** |
| 977–988 | `_save_reward_period` | function | **нет** |
| 991–1003 | `_save_reward_users` | function | **нет** |
| 1006–1032 | `_notify_winners` | function | **нет** |
| 1035–1052 | `_get_reward_for_user` | function | **нет** |
| 1055–1071 | `_get_withdrawal_requests` | function | **нет** |
| 1074–1086 | `_delete_withdrawal_request` | function | есть: Удаляет запрос на вывод по ID. |
| 1089–1101 | `_mark_withdrawal_completed` | function | есть: Отмечает запрос на вывод как выполненный с опциональным скриншотом. |
| 1104–1115 | `_mark_withdraw_requested` | function | **нет** |
| 1118–1125 | `_format_taraweeh_place` | function | **нет** |
| 1128–1133 | `_format_adhkar_status` | function | **нет** |
| 1136–1154 | `_parse_prize_shares` | function | **нет** |
| 1157–1167 | `_allocate_prize_fund` | function | **нет** |
| 1170–1178 | `_build_support_url` | function | **нет** |
| 1181–1288 | `_create_withdrawal_ticket` | function | есть: Создает тикет в support-боте для запроса на вывод выигрыша. |
| 1291–1295 | `_mask_user_id` | function | **нет** |

## `modules/ramadan_tracker/db_cleanup.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 1–10 | `cleanup` | function | **нет** |

## `modules/ramadan_tracker/db_schema.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 5–117 | `SCHEMA_SQL` | function | есть: Генерирует SQL схему и автоматически выполняет миграции. |

## `modules/ramadan_tracker/panel_routes.py`

Модульный docstring: —

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 15–37 | `_get_global_stats` | function | **нет** |
| 40–63 | `_get_top_rows` | function | **нет** |
| 66–109 | `_get_withdrawal_requests` | function | **нет** |
| 113–120 | `index` | function | **нет** |
| 124–129 | `payouts` | function | **нет** |
| 133–143 | `payouts_delete` | function | **нет** |
| 147–162 | `payouts_complete` | function | **нет** |

## `simple_collect.py`

Модульный docstring: Упрощенный скрипт для принудительного сбора метрик

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 13–91 | `collect_metrics_simple` | function | есть: Простой сбор метрик |
| 93–108 | `main` | function | есть: Основная функция |

## `simple_monitor_test.py`

Модульный docstring: Упрощенный скрипт для тестирования мониторинга без дополнительных зависимостей

| Строки | Имя | Вид | Docstring в коде |
|------:|-----|-----|------------------|
| 14–88 | `test_database` | function | есть: Проверяем базу данных |
| 90–115 | `test_settings` | function | есть: Проверяем настройки |
| 117–143 | `test_metrics_collection` | function | есть: Тестируем сбор метрик без psutil |
| 145–185 | `insert_test_metric` | function | есть: Вставляем тестовую метрику |
| 187–230 | `main` | function | есть: Основная функция |
