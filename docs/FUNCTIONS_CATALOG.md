# Каталог функций Xatabchik

Автоматически собранный индекс функций и методов исходного кода (без тестов и vendor).
Связи «кто вызывает» — эвристика по имени вызываемой функции (последний атрибут `foo.bar()` → `bar`).
Полные взаимосвязи подсистем см. [ARCHITECTURE.md](../ARCHITECTURE.md) и [FUNCTIONS_AND_RELATIONS.md](../FUNCTIONS_AND_RELATIONS.md).

**Всего функций/методов:** 2109  
**Классов:** 95  
**Файлов:** 50

## Оглавление по файлам

1. [`src/shop_bot/data_manager/database.py`](#srcshopbotdatamanagerdatabasepy) — 429
2. [`src/shop_bot/bot/admin_handlers.py`](#srcshopbotbotadminhandlerspy) — 367
3. [`src/shop_bot/bot/handlers.py`](#srcshopbotbothandlerspy) — 249
4. [`src/shop_bot/webhook_server/app.py`](#srcshopbotwebhookserverapppy) — 241
5. [`src/shop_bot/webapp/handlers.py`](#srcshopbotwebapphandlerspy) — 144
6. [`src/shop_bot/bot/keyboards.py`](#srcshopbotbotkeyboardspy) — 118
7. [`modules/ramadan_tracker/bot_handlers.py`](#modulesramadantrackerbothandlerspy) — 86
8. [`src/shop_bot/modules/remnawave_api.py`](#srcshopbotmodulesremnawaveapipy) — 86
9. [`src/shop_bot/data_manager/remnawave_repository.py`](#srcshopbotdatamanagerremnawaverepositorypy) — 64
10. [`src/shop_bot/core/module_loader.py`](#srcshopbotcoremoduleloaderpy) — 46
11. [`src/shop_bot/data_manager/scheduler.py`](#srcshopbotdatamanagerschedulerpy) — 39
12. [`src/shop_bot/support_bot/handlers.py`](#srcshopbotsupportbothandlerspy) — 33
13. [`src/shop_bot/support_bot/ticket_media.py`](#srcshopbotsupportbotticketmediapy) — 27
14. [`src/shop_bot/data_manager/speedtest_runner.py`](#srcshopbotdatamanagerspeedtestrunnerpy) — 25
15. [`src/shop_bot/bot_controller.py`](#srcshopbotbotcontrollerpy) — 11
16. [`src/shop_bot/factory_bot/service.py`](#srcshopbotfactorybotservicepy) — 10
17. [`src/shop_bot/support_bot_controller.py`](#srcshopbotsupportbotcontrollerpy) — 10
18. [`src/shop_bot/data_manager/captcha_utils.py`](#srcshopbotdatamanagercaptchautilspy) — 9
19. [`src/shop_bot/data_manager/resource_monitor.py`](#srcshopbotdatamanagerresourcemonitorpy) — 8
20. [`modules/ramadan_tracker/panel_routes.py`](#modulesramadantrackerpanelroutespy) — 7
21. [`src/shop_bot/__main__.py`](#srcshopbotmainpy) — 7
22. [`src/shop_bot/modules/platega_fulfillment.py`](#srcshopbotmodulesplategafulfillmentpy) — 7
23. [`src/shop_bot/modules/rollypay_api.py`](#srcshopbotmodulesrollypayapipy) — 7
24. [`src/shop_bot/bot/callback_safety.py`](#srcshopbotbotcallbacksafetypy) — 6
25. [`src/shop_bot/data_manager/backup_manager.py`](#srcshopbotdatamanagerbackupmanagerpy) — 6
26. [`src/shop_bot/modules/email_sender.py`](#srcshopbotmodulesemailsenderpy) — 6
27. [`simple_monitor_test.py`](#simplemonitortestpy) — 5
28. [`src/shop_bot/bot/photo_helper.py`](#srcshopbotbotphotohelperpy) — 5
29. [`src/shop_bot/factory_bot/handlers.py`](#srcshopbotfactorybothandlerspy) — 5
30. [`src/shop_bot/modules/platega_api.py`](#srcshopbotmodulesplategaapipy) — 5
31. [`src/shop_bot/support_bot/idle_close.py`](#srcshopbotsupportbotidleclosepy) — 5
32. [`src/shop_bot/config.py`](#srcshopbotconfigpy) — 4
33. [`src/shop_bot/core/module_middleware.py`](#srcshopbotcoremodulemiddlewarepy) — 4
34. [`src/shop_bot/bot/image_bot.py`](#srcshopbotbotimagebotpy) — 3
35. [`src/shop_bot/core/module_types.py`](#srcshopbotcoremoduletypespy) — 3
36. [`src/shop_bot/factory_bot/middleware.py`](#srcshopbotfactorybotmiddlewarepy) — 3
37. [`simple_collect.py`](#simplecollectpy) — 2
38. [`src/shop_bot/app.py`](#srcshopbotapppy) — 2
39. [`src/shop_bot/factory_bot/keyboards.py`](#srcshopbotfactorybotkeyboardspy) — 2
40. [`src/shop_bot/factory_bot/runtime.py`](#srcshopbotfactorybotruntimepy) — 2
41. [`src/shop_bot/modules/telegram_reachability.py`](#srcshopbotmodulestelegramreachabilitypy) — 2
42. [`modules/example_module/bot_handlers.py`](#modulesexamplemodulebothandlerspy) — 1
43. [`modules/example_module/db_cleanup.py`](#modulesexamplemoduledbcleanuppy) — 1
44. [`modules/example_module/panel_routes.py`](#modulesexamplemodulepanelroutespy) — 1
45. [`modules/ramadan_tracker/db_cleanup.py`](#modulesramadantrackerdbcleanuppy) — 1
46. [`modules/ramadan_tracker/db_schema.py`](#modulesramadantrackerdbschemapy) — 1
47. [`src/shop_bot/bot/middlewares.py`](#srcshopbotbotmiddlewarespy) — 1
48. [`src/shop_bot/modules/cryptobot_api.py`](#srcshopbotmodulescryptobotapipy) — 1
49. [`src/shop_bot/modules/heleket_api.py`](#srcshopbotmodulesheleketapipy) — 1
50. [`src/shop_bot/webhook_server/apply_app_fix.py`](#srcshopbotwebhookserverapplyappfixpy) — 1

## src/shop_bot/data_manager/database.py

SQLite-схема, миграции и CRUD всех сущностей проекта.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 35 | `_now_str()` | — | `src/shop_bot/data_manager/captcha_utils.py::mark_user_passed_captcha`<br>`src/shop_bot/data_manager/database.py::_apply_key_updates`<br>`src/shop_bot/data_manager/database.py::_migrate_subscription_lte_to_keys`<br>`src/shop_bot/data_manager/database.py::activate_user_gift`<br>`src/shop_bot/data_manager/database.py::add_key_lte_boost_bytes`<br>`src/shop_bot/data_manager/database.py::add_lte_boost_bytes` |
| 39 | `add_calendar_months(dt, months)` | Добавляет календарные месяцы к дате, корректно обрабатывая переполнение дней | `src/shop_bot/data_manager/database.py::compute_aligned_next_traffic_reset`<br>`src/shop_bot/data_manager/database.py::compute_next_traffic_reset_str`<br>`src/shop_bot/data_manager/database.py::resolve_key_period_start` |
| 50 | `compute_next_traffic_reset_str(from_dt)` | Возвращает строку даты/времени следующего ежемесячного сброса трафика (сейчас + 1 месяц). | `src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 56 | `add_months(dt, months)` | Прибавляет к дате календарные месяцы (без внешних зависимостей вроде dateutil). | `src/shop_bot/data_manager/database.py::compute_next_traffic_reset` |
| 71 | `compute_next_traffic_reset(from_dt)` | Возвращает строку даты следующего ежемесячного сброса трафика (текущий момент + 1 месяц). | — |
| 77 | `_as_limit_bytes(value)` | — | `src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields`<br>`src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/database.py::plan_lte_limit_bytes`<br>`src/shop_bot/data_manager/database.py::plan_main_limit_bytes`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 85 | `plan_main_limit_bytes(plan)` | — | `src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields`<br>`src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/database.py::plan_has_monthly_traffic_reset`<br>`src/shop_bot/data_manager/database.py::remnawave_traffic_limit_strategy_for_plan`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 89 | `plan_lte_limit_bytes(plan)` | — | `src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/database.py::plan_has_monthly_traffic_reset`<br>`src/shop_bot/data_manager/database.py::should_account_lte_traffic` |
| 93 | `should_account_lte_traffic(plan, host_name, lte_squad)` | LTE-учёт (снапшоты, baseline, энфорс) только при лимите и живом скваде. | `src/shop_bot/bot/handlers.py::_resolve_plan_for_lte_topup`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/webapp/handlers.py::_lte_card_state` |
| 117 | `plan_has_monthly_traffic_reset(plan)` | Ежемесячный сброс нужен, если ограничен основной пул и/или LTE. | `src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields` |
| 122 | `remnawave_traffic_limit_strategy_for_plan(plan)` | Стратегия Remnawave относится только к ОСНОВНОМУ пулу. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch`<br>`src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields`<br>`src/shop_bot/data_manager/scheduler.py::check_auto_renewals`<br>`src/shop_bot/webhook_server/app.py::admin_key_change_plan_route` |
| 131 | `parse_plan_id_from_key(key)` | — | `src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/database.py::resolve_plan_for_key` |
| 143 | `key_is_unbilled_trial_or_gift(key)` | — | `src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/database.py::resolve_plan_for_key` |
| 161 | `resolve_plan_for_key(key, allow_host_fallback)` | Тариф ключа: plan_id из description, иначе первый активный тариф хоста. | `src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields`<br>`src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 185 | `format_next_traffic_reset_display(raw)` | Дата ближайшего сброса для карточки ключа (`ДД.ММ.ГГГГ`) либо None. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/webapp/handlers.py::_lte_card_state`<br>`src/shop_bot/webapp/handlers.py::_process_key_data`<br>`src/shop_bot/webhook_server/app.py::admin_key_details_json`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 196 | `compute_aligned_next_traffic_reset(key, now)` | Следующий сброс, согласованный с текущим rolling-окном ключа. | `src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields` |
| 227 | `_to_datetime_str(ts_ms)` | — | `src/shop_bot/data_manager/database.py::add_new_key`<br>`src/shop_bot/data_manager/database.py::update_key_fields` |
| 237 | `_normalize_email(value)` | — | `src/shop_bot/data_manager/database.py::_normalize_key_row`<br>`src/shop_bot/data_manager/database.py::add_new_key`<br>`src/shop_bot/data_manager/database.py::create_user_by_email`<br>`src/shop_bot/data_manager/database.py::delete_key_by_email`<br>`src/shop_bot/data_manager/database.py::get_key_by_email`<br>`src/shop_bot/data_manager/database.py::get_user_by_email` |
| 244 | `_normalize_key_row(row)` | — | `src/shop_bot/data_manager/database.py::get_all_keys`<br>`src/shop_bot/data_manager/database.py::get_key_by_email`<br>`src/shop_bot/data_manager/database.py::get_key_by_id`<br>`src/shop_bot/data_manager/database.py::get_key_by_remnawave_uuid`<br>`src/shop_bot/data_manager/database.py::get_keys_for_auto_renew`<br>`src/shop_bot/data_manager/database.py::get_keys_for_host` |
| 273 | `_get_table_columns(cursor, table)` | — | `src/shop_bot/data_manager/database.py::_ensure_email_verification_columns`<br>`src/shop_bot/data_manager/database.py::_ensure_table_column`<br>`src/shop_bot/data_manager/database.py::_rebuild_vpn_keys_table` |
| 278 | `_ensure_table_column(cursor, table, column, definition)` | — | `src/shop_bot/data_manager/database.py::_ensure_analytics_tables`<br>`src/shop_bot/data_manager/database.py::_ensure_email_verification_columns`<br>`src/shop_bot/data_manager/database.py::_ensure_hosts_columns`<br>`src/shop_bot/data_manager/database.py::_ensure_key_usage_monitor_columns`<br>`src/shop_bot/data_manager/database.py::_ensure_plans_columns`<br>`src/shop_bot/data_manager/database.py::_ensure_promo_tables` |
| 284 | `_ensure_unique_index(cursor, name, table, column)` | — | `src/shop_bot/data_manager/database.py::_ensure_auth_pending_actions_table`<br>`src/shop_bot/data_manager/database.py::_ensure_users_columns`<br>`src/shop_bot/data_manager/database.py::_finalize_vpn_key_indexes` |
| 288 | `_ensure_index(cursor, name, table, column)` | — | `src/shop_bot/data_manager/database.py::_ensure_analytics_tables`<br>`src/shop_bot/data_manager/database.py::_ensure_auth_pending_actions_table`<br>`src/shop_bot/data_manager/database.py::_ensure_gift_tokens_table`<br>`src/shop_bot/data_manager/database.py::_ensure_promo_tables`<br>`src/shop_bot/data_manager/database.py::_ensure_user_gifts_table`<br>`src/shop_bot/data_manager/database.py::_ensure_users_columns` |
| 292 | `normalize_host_name(name)` | Normalize host name by trimming and removing invisible/unicode spaces. | `src/shop_bot/data_manager/database.py::_ensure_host_squads_table`<br>`src/shop_bot/data_manager/database.py::add_host_squad`<br>`src/shop_bot/data_manager/database.py::add_new_key`<br>`src/shop_bot/data_manager/database.py::create_host`<br>`src/shop_bot/data_manager/database.py::create_plan`<br>`src/shop_bot/data_manager/database.py::create_ssh_target` |
| 300 | `initialize_db()` | — | `src/shop_bot/__main__.py::main` |
| 894 | `_ensure_users_columns(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 919 | `_ensure_email_verification_columns(cursor)` | Добавляет поля для активации email (подтверждение владения адресом при веб-регистрации). | `src/shop_bot/data_manager/database.py::run_migration` |
| 946 | `_ensure_hosts_columns(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 976 | `_ensure_plans_columns(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 993 | `_ensure_traffic_packages_table(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 1017 | `_ensure_key_node_usage_snapshots_table(cursor)` | Расход ключа по КОНКРЕТНЫМ нодам за расчётный период. | `src/shop_bot/data_manager/database.py::run_migration` |
| 1046 | `resolve_key_period_start(key)` | Начало текущего расчётного периода ключа в формате '%Y-%m-%d %H:%M:%S'. | `src/shop_bot/data_manager/database.py::compute_aligned_next_traffic_reset`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/webhook_server/app.py::admin_key_details_json`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1079 | `upsert_key_node_usage_snapshot(key_id, node_uuid, host_name, used_bytes, period_start, node_name)` | Записать/обновить расход ключа по одной ноде за период (идемпотентно по | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1124 | `get_node_usage_for_key(key_id, period_start)` | Разбивка расхода ключа по нодам за период (по убыванию расхода). | `src/shop_bot/webhook_server/app.py::admin_key_details_json`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1153 | `delete_node_usage_for_key(key_id)` | Удалить все снапшоты ключа (используется при удалении ключа). | — |
| 1166 | `_ensure_subscription_lte_table(cursor)` | Отдельный (независимый от основного) пул трафика LTE для «премиум»-нод. | `src/shop_bot/data_manager/database.py::run_migration` |
| 1197 | `_ensure_key_lte_state_table(cursor)` | Состояние LTE-пула НА КЛЮЧ (пришло на смену пользовательскому `subscription_lte`). | `src/shop_bot/data_manager/database.py::run_migration` |
| 1224 | `_migrate_subscription_lte_to_keys(cursor)` | Перенести пользовательское состояние LTE на ключи (однократно для каждой строки). | `src/shop_bot/data_manager/database.py::_ensure_key_lte_state_table` |
| 1329 | `_ensure_host_squads_table(cursor)` | Классифицированные сквады хоста: 'base' (∞), 'lte' (💰) или 'other'. | `src/shop_bot/data_manager/database.py::run_migration` |
| 1412 | `add_host_squad(host_name, squad_uuid, squad_class, label)` | Добавить сквад к хосту с классификацией ('base' \| 'lte' \| 'other'). | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad2_label`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::add_host_squad_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1452 | `get_host_squads(host_name, only_active)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_squads`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 1470 | `get_squad_by_class(host_name, squad_class)` | Быстрый доступ к активному сквада заданного класса ('base'/'lte'/'other') хоста. | `src/shop_bot/bot/admin_handlers.py::_format_host_card`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_toggle_class`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::show_key_handler` |
| 1500 | `squad_display_label(squad, fallback)` | Публичная метка сквада: поле `label`, если заполнено, иначе fallback. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/data_manager/database.py::get_lte_squad_display_label`<br>`src/shop_bot/webapp/handlers.py::_lte_card_state`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 1520 | `get_lte_squad_display_label(host_name, fallback)` | Метка активного LTE-сквада хоста — то, что видит пользователь вместо «LTE». | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::lte_gb_pick_handler`<br>`src/shop_bot/bot/handlers.py::lte_gb_start_handler`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 1531 | `set_host_squad_active(squad_id, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::toggle_host_squad_route` |
| 1546 | `delete_host_squad(squad_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad_delete`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_host_squad_route` |
| 1558 | `_ensure_remnawave_squads_catalog(cursor)` | Глобальный каталог сквадов Remnawave (выбираются галочками на хостах). | `src/shop_bot/data_manager/database.py::run_migration` |
| 1628 | `get_remnawave_squads(only_active)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 1644 | `add_remnawave_squad(squad_uuid, squad_class, label)` | — | `src/shop_bot/webhook_server/app.py::add_remnawave_squad_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1671 | `delete_remnawave_squad(squad_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_remnawave_squad_route` |
| 1695 | `seed_global_remnawave_from_hosts()` | Если глобальные Remnawave-настройки пусты — взять из первого хоста. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 1735 | `apply_global_remnawave_to_hosts()` | Синхронизировать глобальные Remnawave URL/token/subscription на все хосты. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_remnawave_settings_route` |
| 1767 | `set_host_squads_from_catalog(host_name, catalog_ids)` | Выставить привязку хоста к сквадам каталога (галочки). Синхронизирует host_squads и squad_uuid. | `src/shop_bot/webhook_server/app.py::add_host_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_host_squad_selection_route` |
| 1854 | `get_host_selected_squad_catalog_ids(host_name)` | ID записей каталога, привязанных к хосту через host_squads.uuid. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 1876 | `_ensure_support_tickets_columns(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 1885 | `_ensure_key_usage_monitor_columns(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 1894 | `_finalize_vpn_key_indexes(cursor)` | — | `src/shop_bot/data_manager/database.py::_ensure_vpn_keys_schema`<br>`src/shop_bot/data_manager/database.py::_rebuild_vpn_keys_table` |
| 1902 | `_rebuild_vpn_keys_table(cursor)` | — | `src/shop_bot/data_manager/database.py::_ensure_vpn_keys_schema` |
| 1936 | `has(column)` | — | `src/shop_bot/data_manager/database.py::_rebuild_vpn_keys_table`<br>`src/shop_bot/data_manager/database.py::col` |
| 1939 | `col(column, default)` | — | `src/shop_bot/data_manager/database.py::_rebuild_vpn_keys_table` |
| 2005 | `_ensure_vpn_keys_schema(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 2037 | `_migrate_gift_tags(cursor)` | Обновить старые теги 'gift' и 'GIFT' на новый стандарт 'user_gift'. | `src/shop_bot/data_manager/database.py::run_migration` |
| 2053 | `run_migration()` | — | `src/shop_bot/data_manager/backup_manager.py::restore_from_file`<br>`src/shop_bot/data_manager/database.py::initialize_db` |
| 2132 | `insert_resource_metric(scope, object_name, cpu_percent, mem_percent, disk_percent, load1, net_bytes_sent, net_bytes_recv, raw_json)` | — | `simple_collect.py::collect_metrics_simple`<br>`simple_monitor_test.py::insert_test_metric`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2168 | `get_latest_resource_metric(scope, object_name)` | — | `simple_collect.py::collect_metrics_simple` |
| 2189 | `get_metrics_series(scope, object_name, since_hours, limit)` | — | `simple_collect.py::collect_metrics_simple`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::monitor_series_json` |
| 2230 | `create_host(name, url, user, passwd, inbound, subscription_url)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_add_squad_uuid`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::add_host_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 2259 | `update_host_subscription_url(host_name, subscription_url)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_set_sub_input`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/database.py::apply_global_remnawave_to_hosts`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_host_subscription_route` |
| 2280 | `claim_referral_start_bonus(user_id)` | Атомарно пометить, что приглашённый получил стартовый реферальный бонус. | `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`<br>`src/shop_bot/data_manager/database.py::set_referral_start_bonus_received`<br>`src/shop_bot/webapp/handlers.py::_apply_pending_referral` |
| 2309 | `set_referral_start_bonus_received(user_id)` | Пометить, что пользователь получил стартовый бонус за реферальную регистрацию. | — |
| 2318 | `set_referral_trial_day_bonus_received(user_id)` | Пометить, что за данного пользователя уже начислялся +1 день рефереру за активацию триала. | `src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial` |
| 2335 | `update_host_url(host_name, new_url)` | Обновить URL панели XUI для указанного хоста. | `src/shop_bot/bot/admin_handlers.py::admin_hosts_set_url_input`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/database.py::apply_global_remnawave_to_hosts`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_host_url_route` |
| 2357 | `update_host_remnawave_settings(host_name, remnawave_base_url, remnawave_api_token, squad_uuid)` | Обновить Remnawave-настройки на уровне конкретного хоста. | `src/shop_bot/bot/admin_handlers.py::admin_hosts_add_squad_uuid`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_token_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_url_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_squad_input`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/database.py::apply_global_remnawave_to_hosts` |
| 2404 | `get_host_class(host_name)` | Класс ноды: 'premium' (💰) или 'unlim' (∞, по умолчанию). | `src/shop_bot/bot/admin_handlers.py::admin_hosts_toggle_class`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_detail`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/webhook_server/app.py::admin_key_add_lte_traffic_route` |
| 2421 | `set_host_class(host_name, node_class, badge)` | Устанавливает класс ноды ('premium'/'unlim') и её значок (по умолчанию 💰/∞). | `src/shop_bot/bot/admin_handlers.py::admin_hosts_toggle_class`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2441 | `set_host_squad_overlap(host_name, overlap_nodes)` | Сохранить результат проверки пересечения нод LTE- и base-сквадов хоста. | `src/shop_bot/modules/remnawave_api.py::refresh_host_squad_overlap` |
| 2470 | `get_host_squad_overlap(host_name)` | Ноды, доступные и через LTE-, и через base-сквад хоста (по последней проверке). | `src/shop_bot/bot/admin_handlers.py::_format_host_card`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 2491 | `list_hosts_by_class(node_class)` | — | — |
| 2507 | `update_host_name(old_name, new_name)` | Переименовать хост во всех связанных таблицах (xui_hosts, plans, vpn_keys, host_squads). | `src/shop_bot/bot/admin_handlers.py::admin_hosts_rename_input`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::rename_host_route` |
| 2551 | `delete_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_host_route` |
| 2569 | `_decrypt_row_secrets(row, *fields)` | Расшифровать at-rest поля (enc1$ / legacy plaintext) в копии строки. | `src/shop_bot/data_manager/database.py::get_all_hosts`<br>`src/shop_bot/data_manager/database.py::get_all_ssh_targets`<br>`src/shop_bot/data_manager/database.py::get_host`<br>`src/shop_bot/data_manager/database.py::get_ssh_target`<br>`src/shop_bot/data_manager/database.py::list_hosts_by_class`<br>`src/shop_bot/data_manager/remnawave_repository.py::_decrypt_host_secrets` |
| 2580 | `get_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_add_squad_uuid`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_detail`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_host`<br>`src/shop_bot/data_manager/speedtest_runner.py::run_and_store_net_probe` |
| 2593 | `update_host_ssh_settings(host_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path)` | Обновить SSH-параметры для speedtest/maintenance по хосту. | `src/shop_bot/bot/admin_handlers.py::admin_hosts_set_ssh_input`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_host_ssh_route` |
| 2634 | `delete_key_by_id(key_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/bot/handlers.py::sync_user_keys_with_remnawave`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_key_route`<br>`src/shop_bot/webhook_server/app.py::sweep_expired_keys_route` |
| 2652 | `update_key_comment(key_id, comment)` | — | `src/shop_bot/webapp/handlers.py::api_key_comment`<br>`src/shop_bot/webhook_server/app.py::create_key_ajax_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_key_comment_route` |
| 2664 | `update_key_name(key_id, new_name)` | Обновить пользовательское название ключа. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process`<br>`src/shop_bot/webapp/handlers.py::api_key_rename` |
| 2700 | `get_all_hosts()` | — | `src/shop_bot/bot/admin_handlers.py::_resolve_host_from_digest`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_back_to_hosts`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_key_for_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_host_keys_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_back_to_hosts` |
| 2718 | `get_speedtests(host_name, limit)` | Получить последние результаты спидтестов по хосту (ssh/net), новые сверху. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::host_speedtests_json` |
| 2746 | `get_latest_speedtest(host_name)` | Получить последний по времени спидтест для хоста. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::user_speedtest_last_handler`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::dashboard_page`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 2770 | `insert_host_speedtest(host_name, method, ping_ms, jitter_ms, download_mbps, upload_mbps, server_name, server_id, ok, error)` | Сохранить результат спидтеста в таблицу host_speedtests. | `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_net_probe`<br>`src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest`<br>`src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest_for_target` |
| 2817 | `_ensure_ssh_targets_table(cursor)` | Миграция: создать таблицу speedtest_ssh_targets при необходимости и добавить недостающие столбцы. | `src/shop_bot/data_manager/database.py::run_migration` |
| 2849 | `_ensure_ssh_known_hosts_table(cursor)` | — | `src/shop_bot/data_manager/database.py::run_migration` |
| 2863 | `get_ssh_known_host_key(host, port)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_apply_ssh_host_key_policy` |
| 2881 | `save_ssh_known_host_key(host, port, key_type, key_base64)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_apply_ssh_host_key_policy`<br>`src/shop_bot/data_manager/speedtest_runner.py::_save` |
| 2905 | `_ensure_gift_tokens_table(cursor)` | Миграция для таблиц подарочных токенов. | `src/shop_bot/data_manager/database.py::run_migration` |
| 2941 | `_ensure_user_gifts_table(cursor)` | Миграция для таблицы неактивированных пользовательских подарков. | `src/shop_bot/data_manager/database.py::run_migration` |
| 2965 | `_ensure_auth_pending_actions_table(cursor)` | Миграция для таблицы pending action — единого механизма "открыл ссылку | `src/shop_bot/data_manager/database.py::run_migration` |
| 2997 | `create_pending_action(action_type, gift_code, referrer_id, ttl_hours)` | Создать pending action и вернуть одноразовый случайный токен. | `src/shop_bot/webapp/handlers.py::web_gift_page`<br>`src/shop_bot/webapp/handlers.py::web_referral_page` |
| 3031 | `get_pending_action(token)` | Вернуть запись pending action по токену как есть (включая уже | `src/shop_bot/webapp/handlers.py::api_pending_action_complete`<br>`src/shop_bot/webapp/handlers.py::api_pending_action_info` |
| 3049 | `claim_pending_action(token, user_id)` | Атомарно "забрать" pending action для указанного пользователя. | `src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 3077 | `set_pending_action_result(token, result_status)` | Сохранить итоговый статус применения действия — чтобы повторный вызов | `src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 3096 | `cleanup_expired_pending_actions(max_age_hours)` | Удалить давно истёкшие pending actions (профилактическая очистка, | — |
| 3114 | `_ensure_promo_tables(cursor)` | Создание таблиц промокодов и истории их использования. | `src/shop_bot/data_manager/database.py::run_migration` |
| 3178 | `_ensure_analytics_tables(cursor)` | Таблицы для раздела админки «Продажи и аналитика». | `src/shop_bot/data_manager/database.py::run_migration` |
| 3287 | `get_all_ssh_targets()` | Вернуть все SSH-цели для спидтестов (включая неактивные), сортировка по sort_order, затем по имени. | `src/shop_bot/bot/admin_handlers.py::_resolve_target_from_hash`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_all_targets`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_ssh_targets` |
| 3301 | `get_ssh_target(target_name)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_target`<br>`src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest_for_target` |
| 3315 | `create_ssh_target(target_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path, description, sort_order, is_active)` | — | `src/shop_bot/webhook_server/app.py::create_ssh_target_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3356 | `update_ssh_target_fields(target_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path, description, sort_order, is_active)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_ssh_target_route` |
| 3423 | `delete_ssh_target(target_name)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_ssh_target_route` |
| 3436 | `get_admin_stats()` | Return aggregated statistics for the admin dashboard. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_menu`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::statistics_page` |
| 3528 | `get_sales_overview()` | Главный дашборд продаж (Этап 4.1 плана): выручка/транзакции/чек/плательщики | `src/shop_bot/data_manager/database.py::get_economics_summary`<br>`src/shop_bot/webhook_server/app.py::analytics_overview_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3651 | `get_revenue_series(days)` | Ряд выручки/транзакций по дням для графика раздела «Продажи и аналитика». | `src/shop_bot/webhook_server/app.py::analytics_overview_charts_json`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3677 | `get_plans_analytics(limit)` | Аналитика по тарифам (Этап 4.4): выручка, продажи, средний чек, доля повторных покупок. | `src/shop_bot/webhook_server/app.py::analytics_forecast_page`<br>`src/shop_bot/webhook_server/app.py::analytics_plans_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3729 | `get_payment_methods_analytics()` | Аналитика по методам оплаты (Этап 4.5): число транзакций, выручка, успешность, динамика. | `src/shop_bot/webhook_server/app.py::analytics_payment_methods_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3762 | `get_users_without_real_payment_with_keys()` | Пользователи с хотя бы одним VPN-ключом, у которых нет ни одной успешной | `src/shop_bot/webhook_server/app.py::analytics_overview_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3794 | `get_trial_key_stats()` | Метрики по триальным ключам и их продлениям. | `src/shop_bot/webhook_server/app.py::analytics_overview_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3878 | `get_referrals_analytics()` | Аналитика реферальной программы (Этап 6.1) поверх существующих полей/функций, | `src/shop_bot/webhook_server/app.py::analytics_referrals_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3941 | `get_top_referrers(limit)` | Топ пользователей по рефералам: число приглашённых и число платящих рефералов. | `src/shop_bot/webhook_server/app.py::analytics_referrals_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::referral_program_top_page` |
| 3982 | `get_top_buyers(limit)` | Топ пользователей по покупкам (Этап 6.4): сумма, число успешных транзакций, средний чек. | `src/shop_bot/webhook_server/app.py::analytics_referrals_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4016 | `_promo_plans_label(raw_ids)` | Человекочитаемое ограничение тарифов для карточки купона в админке. | `src/shop_bot/data_manager/database.py::get_coupons_analytics` |
| 4030 | `_promo_segment_label(segment_type, segment_value)` | Человекочитаемое ограничение сегмента для карточки купона в админке. | `src/shop_bot/data_manager/database.py::get_coupons_analytics` |
| 4046 | `get_coupons_analytics()` | Аналитика купонов/промокодов (Этап 6.3) поверх существующих таблиц | `src/shop_bot/webhook_server/app.py::analytics_coupons_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4125 | `get_server_cost_entries(only_active)` | — | `src/shop_bot/data_manager/database.py::get_economics_summary`<br>`src/shop_bot/webhook_server/app.py::analytics_economics_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4141 | `create_server_cost_entry(server_label, linked_host_name, provider, location, monthly_cost, currency, status, started_at, ended_at, comment)` | — | `src/shop_bot/webhook_server/app.py::analytics_economics_create_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4183 | `update_server_cost_entry(entry_id, **fields)` | — | — |
| 4208 | `delete_server_cost_entry(entry_id)` | — | `src/shop_bot/webhook_server/app.py::analytics_economics_delete_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4220 | `get_economics_summary()` | Приблизительная экономика (Этап 7.3): расходы по провайдеру/локации, | `src/shop_bot/webhook_server/app.py::analytics_economics_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4259 | `get_revenue_forecast()` | Прозрачный прогноз (Этап 4.6/9): скользящее среднее за 7 дней + линейная | `src/shop_bot/webhook_server/app.py::analytics_forecast_page`<br>`src/shop_bot/webhook_server/app.py::analytics_overview_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4311 | `get_utm_links(only_active)` | — | — |
| 4327 | `create_utm_link(slug, source, medium, campaign, content, term, label, comment, budget, created_by)` | — | `src/shop_bot/webhook_server/app.py::analytics_utm_create_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4363 | `delete_utm_link(slug)` | Удаляет UTM-метку вместе с накопленной статистикой посещений (utm_visits). | `src/shop_bot/webhook_server/app.py::analytics_utm_delete_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4380 | `log_utm_visit(slug, user_id, event_type)` | Best-effort запись события UTM (клик/старт/регистрация/оплата). Никогда не бросает исключение наружу. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 4394 | `set_user_utm_slug_if_absent(user_id, slug)` | First-touch атрибуция: записать utm_slug пользователю только если он ещё не задан. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 4410 | `get_utm_analytics()` | Эффективность UTM-меток (Этап 5.4): клики, регистрации, оплаты, выручка, ROI (если задан budget). | `src/shop_bot/webhook_server/app.py::analytics_utm_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4459 | `create_broadcast_campaign(name, text_html, interval_hours, target_segment)` | — | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_create`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4474 | `get_broadcast_campaigns()` | — | `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`<br>`src/shop_bot/webhook_server/app.py::analytics_broadcasts_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4486 | `get_broadcast_campaign(campaign_id)` | — | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_delete`<br>`src/shop_bot/webhook_server/app.py::analytics_broadcasts_send_now`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4499 | `update_broadcast_campaign(campaign_id, name, text_html, interval_hours)` | — | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_update`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4514 | `toggle_broadcast_campaign(campaign_id)` | Flip is_active. Returns new is_active state. | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_toggle`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4535 | `delete_broadcast_campaign(campaign_id)` | — | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_delete`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4554 | `is_email_only_user(telegram_id)` | True, если пользователь зарегистрирован по email и ещё не авторизовался | `src/shop_bot/bot/admin_handlers.py::confirm_broadcast_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_request` |
| 4564 | `get_inactive_subscribers()` | User IDs with no active keys (expire_at in the past or no keys at all), | `src/shop_bot/data_manager/database.py::get_pending_broadcast_recipients` |
| 4591 | `get_pending_broadcast_recipients(campaign_id, interval_hours)` | Inactive users who haven't been sent this campaign in the last `interval_hours`. | `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`<br>`src/shop_bot/webhook_server/app.py::analytics_broadcasts_send_now`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4614 | `record_broadcast_sends(campaign_id, user_ids)` | Insert send records and bump campaign send_count. Returns count inserted. | `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`<br>`src/shop_bot/webhook_server/app.py::analytics_broadcasts_send_now`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4636 | `mark_broadcast_run(campaign_id)` | Update last_run_at even when there are no recipients (avoids tight retry loops). | `src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`<br>`src/shop_bot/webhook_server/app.py::analytics_broadcasts_send_now`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4650 | `get_broadcast_stats(campaign_id)` | — | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4662 | `get_all_keys()` | — | `src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_expiring_subscriptions`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 4674 | `get_all_key_ids()` | Все key_id из vpn_keys (без фильтров/пагинации) — для bulk-действий «всем». | `src/shop_bot/webhook_server/app.py::bulk_extend_all_keys_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4686 | `extend_key(key_id, days)` | Продлить/сократить срок ключа на N дней (с синхронизацией Remnawave). | `src/shop_bot/webhook_server/app.py::_apply_bulk_expiry_to_ids`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4696 | `set_key_expiry(key_id, new_expire_at)` | Установить точную дату истечения ключа (с синхронизацией Remnawave). | `src/shop_bot/webhook_server/app.py::_apply_bulk_expiry_to_ids`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 4703 | `get_keys_paginated(page, per_page, search, sort_by, sort_dir, user_id)` | — | `src/shop_bot/webhook_server/app.py::admin_global_search_json`<br>`src/shop_bot/webhook_server/app.py::admin_keys_page`<br>`src/shop_bot/webhook_server/app.py::admin_keys_pagination_partial`<br>`src/shop_bot/webhook_server/app.py::admin_keys_table_partial`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::user_keys_partial` |
| 4763 | `get_keys_for_user(user_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_ban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_back`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_unban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_user_keys`<br>`src/shop_bot/bot/admin_handlers.py::admin_users_search_process` |
| 4766 | `update_key_email(key_id, new_email)` | — | `src/shop_bot/bot/admin_handlers.py::admin_key_edit_email_commit`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 4770 | `update_key_host(key_id, new_host_name)` | — | — |
| 4773 | `create_gift_key(user_id, host_name, key_email, months, remnawave_user_uuid)` | Создать подарочный ключ: expiry = now + months. | — |
| 4809 | `get_setting(key)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_support_url`<br>`modules/ramadan_tracker/bot_handlers.py::_create_withdrawal_ticket`<br>`simple_monitor_test.py::test_settings`<br>`src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_get_bool_setting` |
| 4823 | `get_admin_ids()` | Возвращает множество ID администраторов из настроек. | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_remove_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_all` |
| 4862 | `is_admin(user_id)` | Проверка прав администратора по списку ID из настроек. | `modules/ramadan_tracker/bot_handlers.py::_is_admin`<br>`src/shop_bot/bot/admin_handlers.py::AdminAccessMiddleware.__call__`<br>`src/shop_bot/bot/admin_handlers.py::IsAdminFilter.__call__`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_admin_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_balance_entry` |
| 4869 | `_connect_pending_db()` | Connection helper for high-contention tables (webhooks/bot). | `src/shop_bot/data_manager/database.py::_complete_pending`<br>`src/shop_bot/data_manager/database.py::_get_pending_metadata`<br>`src/shop_bot/data_manager/database.py::_work`<br>`src/shop_bot/data_manager/database.py::cancel_pending_transaction`<br>`src/shop_bot/data_manager/database.py::claim_processed_payment`<br>`src/shop_bot/data_manager/database.py::create_payload_pending` |
| 4883 | `_retry_sqlite(work, attempts, base_sleep)` | — | `src/shop_bot/data_manager/database.py::_complete_pending`<br>`src/shop_bot/data_manager/database.py::_get_pending_metadata`<br>`src/shop_bot/data_manager/database.py::cancel_pending_transaction`<br>`src/shop_bot/data_manager/database.py::claim_processed_payment`<br>`src/shop_bot/data_manager/database.py::create_payload_pending`<br>`src/shop_bot/data_manager/database.py::find_and_complete_pending_transaction` |
| 4894 | `_ensure_pending_tables(cursor)` | — | `src/shop_bot/data_manager/database.py::_complete_pending`<br>`src/shop_bot/data_manager/database.py::_get_pending_metadata`<br>`src/shop_bot/data_manager/database.py::_work`<br>`src/shop_bot/data_manager/database.py::cancel_pending_transaction`<br>`src/shop_bot/data_manager/database.py::create_payload_pending`<br>`src/shop_bot/data_manager/database.py::find_and_complete_pending_transaction` |
| 4910 | `_ensure_processed_payments_table(cursor)` | — | `src/shop_bot/data_manager/database.py::_work`<br>`src/shop_bot/data_manager/database.py::claim_processed_payment`<br>`src/shop_bot/data_manager/database.py::unclaim_processed_payment` |
| 4934 | `_tx_meta_dict(raw)` | — | `src/shop_bot/data_manager/database.py::_mirror_pending_to_ledger`<br>`src/shop_bot/data_manager/database.py::_work`<br>`src/shop_bot/data_manager/database.py::log_transaction`<br>`src/shop_bot/data_manager/database.py::patch_pending_metadata` |
| 4944 | `_provider_transaction_id_from_meta(metadata)` | — | `src/shop_bot/data_manager/database.py::_describe_transaction_action` |
| 4954 | `_mirror_pending_to_ledger(cursor, payment_id, user_id, amount_rub, metadata, status)` | Дублирует неоплаченный счёт в ``transactions``, чтобы он был виден в истории. | `src/shop_bot/data_manager/database.py::_work`<br>`src/shop_bot/data_manager/database.py::create_payload_pending`<br>`src/shop_bot/data_manager/database.py::create_pending_transaction`<br>`src/shop_bot/data_manager/database.py::patch_pending_metadata` |
| 5017 | `create_payload_pending(payment_id, user_id, amount_rub, metadata)` | Create/update pending payload metadata. | `src/shop_bot/bot/handlers.py::_create_cryptobot_invoice`<br>`src/shop_bot/bot/handlers.py::_create_heleket_payment_request`<br>`src/shop_bot/bot/handlers.py::create_stars_invoice_handler`<br>`src/shop_bot/bot/handlers.py::create_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_platega_handler` |
| 5027 | `_work()` | — | — |
| 5067 | `patch_pending_metadata(payment_id, extra)` | Дописывает поля (id провайдера) в pending и в зеркало ``transactions``. | `src/shop_bot/bot/handlers.py::_create_cryptobot_invoice`<br>`src/shop_bot/bot/handlers.py::_create_heleket_payment_request`<br>`src/shop_bot/bot/handlers.py::create_cryptobot_api_invoice`<br>`src/shop_bot/modules/heleket_api.py::create_heleket_payment_request`<br>`src/shop_bot/modules/platega_fulfillment.py::mark_pending_canceled` |
| 5073 | `_work()` | — | — |
| 5106 | `_get_pending_metadata(payment_id)` | — | `src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/data_manager/database.py::get_pending_metadata`<br>`src/shop_bot/data_manager/database.py::prepare_pending_for_fulfillment` |
| 5111 | `_work()` | — | — |
| 5137 | `get_pending_metadata(payment_id)` | Public wrapper to fetch pending metadata by payment_id WITHOUT marking it paid. | `src/shop_bot/bot/handlers.py::check_crypto_invoice_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::payment_stars_back_handler`<br>`src/shop_bot/webapp/handlers.py::api_verify_platega_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 5142 | `get_pending_record(payment_id)` | Строка pending_transactions с любым статусом (pending/cancelled/paid). | `src/shop_bot/data_manager/database.py::prepare_pending_for_fulfillment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler` |
| 5148 | `_work()` | — | — |
| 5182 | `revive_cancelled_invoice(payment_id)` | Вернуть отменённый счёт в pending, если позже пришла реальная оплата. | `src/shop_bot/data_manager/database.py::prepare_pending_for_fulfillment` |
| 5188 | `_work()` | — | — |
| 5221 | `prepare_pending_for_fulfillment(payment_id)` | Metadata для выдачи: отменённый счёт поднимаем, paid не трогаем. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::yookassa_webhook_handler` |
| 5234 | `get_pending_status(payment_id)` | Return status of pending transaction: 'pending', 'paid', or None if not found. | `src/shop_bot/bot/handlers.py::check_pending_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::payment_stars_back_handler` |
| 5240 | `_work()` | — | — |
| 5257 | `_complete_pending(payment_id)` | — | — |
| 5262 | `_work()` | — | — |
| 5279 | `find_and_complete_pending_transaction(payment_id)` | Atomically mark pending transaction as paid and return its metadata. | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::check_crypto_invoice_handler`<br>`src/shop_bot/bot/handlers.py::check_pending_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler` |
| 5288 | `_work()` | — | — |
| 5334 | `get_latest_pending_for_user(user_id)` | Return metadata of the most recent PENDING transaction for the user (without completing it). | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::stars_success_handler` |
| 5366 | `claim_processed_payment(payment_id)` | Idempotency guard: returns True only once per payment_id. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/database.py::refund_payment_once` |
| 5372 | `_work()` | — | — |
| 5389 | `unclaim_processed_payment(payment_id)` | Remove idempotency record so a failed payment can be retried. | `src/shop_bot/bot/handlers.py::_abort_key_fulfillment`<br>`src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/database.py::refund_payment_once` |
| 5395 | `_work()` | — | — |
| 5409 | `refund_payment_once(payment_id, user_id, amount, payment_method)` | Вернуть средства за невыданную услугу не более одного раза на payment_id. | `src/shop_bot/bot/handlers.py::_abort_key_fulfillment`<br>`src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`<br>`src/shop_bot/webapp/handlers.py::_rollback_internal_payment` |
| 5474 | `cancel_pending_transaction(payment_id, user_id)` | Пометить неоплаченный pending как cancelled, чтобы Stars/вебхук его не закрыли. | `src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::create_stars_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::payment_stars_back_handler` |
| 5484 | `_work()` | — | — |
| 5542 | `reset_pending_transaction(payment_id)` | Reset a completed pending transaction back to 'pending' to allow webhook retry. | `src/shop_bot/bot/handlers.py::_abort_key_fulfillment`<br>`src/shop_bot/bot/handlers.py::_abort_topup_fulfillment` |
| 5548 | `_work()` | — | — |
| 5565 | `get_referrals_for_user(user_id)` | Возвращает список пользователей, которых пригласил данный user_id. | `src/shop_bot/bot/admin_handlers.py::admin_user_referrals`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::admin_balance_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::user_details_json`<br>`src/shop_bot/webhook_server/app.py::user_referrals_json` |
| 5589 | `get_referral_top_rich(limit)` | Возвращает топ пользователей по количеству рефералов, | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_top_handler` |
| 5621 | `get_referral_rank_and_count(user_id)` | Возвращает кортеж (rank, count), где: | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_top_handler` |
| 5674 | `get_all_settings()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year`<br>`src/shop_bot/webhook_server/app.py::login_page`<br>`src/shop_bot/webhook_server/app.py::referral_program_settings_page`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 5691 | `update_setting(key, value)` | — | `simple_monitor_test.py::test_settings`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_hours_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_captcha_attempts_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_captcha_message_input_handler` |
| 5705 | `get_button_configs(menu_type)` | Get *active* button configurations for a specific menu type. | `src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 5728 | `get_button_configs_admin(menu_type, include_inactive)` | Get button configurations for admin/editor UIs. | `src/shop_bot/bot/admin_handlers.py::_btnc_show_list`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_action_value`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_width`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_button_configs_api` |
| 5762 | `get_button_config_by_db_id(button_db_id)` | Get a button configuration by its numeric DB id. | `src/shop_bot/bot/admin_handlers.py::_btnc_show_details`<br>`src/shop_bot/bot/admin_handlers.py::btnc_toggle_active`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 5775 | `get_button_config(menu_type, button_id)` | Get a specific button configuration by menu_type and button_id | — |
| 5793 | `create_button_config(menu_type, button_id, text, callback_data, url, row_position, column_position, button_width, is_active, sort_order, …)` | Create a new button configuration | `src/shop_bot/bot/admin_handlers.py::btnc_add_finish`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_button_config_api`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 5838 | `update_button_config(button_id, text, callback_data, url, row_position, column_position, button_width, is_active, sort_order, metadata)` | Update an existing button configuration | `src/shop_bot/bot/admin_handlers.py::btnc_edit_field_value`<br>`src/shop_bot/bot/admin_handlers.py::btnc_toggle_active`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_button_config_api` |
| 5901 | `delete_button_config(button_id)` | Delete a button configuration | `src/shop_bot/bot/admin_handlers.py::btnc_delete_do`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_button_config_api` |
| 5914 | `update_existing_my_keys_button()` | Update existing my_keys button to include key count template and set proper button widths | `src/shop_bot/data_manager/database.py::initialize_db` |
| 5949 | `ensure_main_menu_gift_button()` | Ensure that the main menu has the gift button in button configs. | `src/shop_bot/data_manager/database.py::initialize_db` |
| 5986 | `ensure_main_menu_referral_button()` | Ensure that the main menu has the referral program button in button configs, | `src/shop_bot/data_manager/database.py::initialize_db` |
| 6039 | `ensure_admin_plans_button()` | Ensure that the Admin menu has a button for managing тарифы (plans). | `src/shop_bot/data_manager/database.py::initialize_db` |
| 6114 | `ensure_admin_trial_button()` | Ensure that the Admin menu has a button for managing Trial settings. | `src/shop_bot/data_manager/database.py::initialize_db` |
| 6156 | `ensure_admin_auto_renew_button()` | Ensure that the Admin settings submenu has a button for Автопродление (auto-renew). | `src/shop_bot/data_manager/database.py::initialize_db` |
| 6202 | `reorder_button_configs(menu_type, button_orders)` | Reorder button configurations for a menu type | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::reorder_button_configs_api` |
| 6250 | `initialize_default_button_configs()` | Initialize default button configurations for all menu types | `src/shop_bot/data_manager/database.py::initialize_db` |
| 6387 | `create_plan(host_name, plan_name, months, price, duration_days, traffic_limit_bytes, hwid_device_limit, lte_limit_bytes, main_reset_price_rub)` | — | `src/shop_bot/bot/admin_handlers.py::admin_plans_price_received`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::add_plan_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 6411 | `get_plans_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::_format_plans_for_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_to_plans`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_back_to_host_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_pick_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_price_received` |
| 6426 | `get_active_plans_for_host(host_name)` | Возвращает только активные тарифы (is_active = 1) для указанного хоста. | `src/shop_bot/bot/handlers.py::_get_tariff_info_for_key`<br>`src/shop_bot/bot/handlers.py::_resolve_plan_id_for_key`<br>`src/shop_bot/bot/handlers.py::back_to_plans_handler`<br>`src/shop_bot/bot/handlers.py::extend_key_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::select_host_for_gift_handler` |
| 6444 | `set_plan_active(plan_id, is_active)` | Включить/выключить тариф (скрыть/показать пользователям). | `src/shop_bot/bot/admin_handlers.py::admin_plan_toggle_active`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::toggle_plan_route` |
| 6459 | `get_plan_by_id(plan_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_lte_packages_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_days_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_devices_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_lte_limit_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_main_reset_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_months_received` |
| 6472 | `get_all_plans()` | Все тарифы (для админки промокодов и валидации applicable_plan_ids). | `src/shop_bot/webhook_server/app.py::analytics_coupons_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 6491 | `_parse_json_metadata(raw)` | — | — |
| 6499 | `update_plan_metadata(plan_id, metadata)` | Update plan.metadata JSON blob. | `src/shop_bot/bot/admin_handlers.py::admin_plan_toggle_show_name`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 6518 | `create_traffic_package(plan_id, size_gb, price, pool)` | Пакет докупки ГБ для тарифа. `pool`: 'main' (основной трафик) или 'lte' (premium-ноды). | `src/shop_bot/bot/admin_handlers.py::admin_pkg_price_received`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::add_traffic_package_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 6549 | `get_traffic_packages_for_plan(plan_id, only_active, pool)` | — | `src/shop_bot/bot/admin_handlers.py::admin_lte_packages_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_delete`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_packages_menu`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 6566 | `get_traffic_package_by_id(package_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_pkg_delete`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_size_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 6579 | `update_traffic_package(package_id, size_gb, price, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_size_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::toggle_traffic_package_route` |
| 6602 | `delete_traffic_package(package_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_pkg_delete`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_traffic_package_route` |
| 6614 | `set_key_traffic_boost(key_id, boost_bytes)` | — | — |
| 6629 | `get_plan_lte_limit(plan_id)` | — | — |
| 6641 | `get_lte_state(user_id)` | УСТАРЕЛО: пользовательская модель LTE-пула. | `src/shop_bot/data_manager/database.py::add_lte_boost_bytes`<br>`src/shop_bot/data_manager/database.py::commit_lte_baseline`<br>`src/shop_bot/data_manager/database.py::request_lte_baseline_reset`<br>`src/shop_bot/data_manager/database.py::update_lte_state` |
| 6705 | `get_key_lte_state(key_id)` | Состояние LTE-пула конкретного ключа (создаёт строку при отсутствии). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/data_manager/database.py::add_key_lte_boost_bytes`<br>`src/shop_bot/data_manager/database.py::commit_key_lte_baseline`<br>`src/shop_bot/data_manager/database.py::request_key_lte_baseline_reset`<br>`src/shop_bot/data_manager/database.py::update_key_lte_state` |
| 6732 | `update_key_lte_state(key_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, lte_used_baseline_bytes, lte_baseline_reset_requested, lte_reset_at, premium_state)` | — | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 6777 | `add_key_lte_boost_bytes(key_id, add_bytes)` | Атомарно увеличить докупленный LTE-буст КЛЮЧА. Возвращает новое значение. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/webhook_server/app.py::admin_key_add_lte_traffic_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 6809 | `commit_key_lte_baseline(key_id, baseline_bytes, expire_boost)` | Зафиксировать точку отсчёта LTE-расхода ключа одной транзакцией. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 6840 | `request_key_lte_baseline_reset(key_id)` | Пометить начало нового расчётного периода LTE у ключа (буст сгорит вместе с baseline). | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 6857 | `resolve_lte_limit_bytes(lte_state, plan_lte_limit_bytes)` | Единая формула эффективного LTE-лимита: лимит тарифа + докупленный буст. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/webapp/handlers.py::_lte_card_state` |
| 6879 | `add_lte_boost_bytes(user_id, add_bytes)` | Атомарно увеличить докупленный LTE-буст пользователя на `add_bytes`. | — |
| 6917 | `commit_lte_baseline(user_id, baseline_bytes, expire_boost)` | Зафиксировать точку отсчёта (baseline) LTE-расхода одной транзакцией. | — |
| 6956 | `request_lte_baseline_reset(user_id)` | Помечает начало нового расчётного периода LTE-пула. | — |
| 6982 | `update_lte_state(user_id, lte_limit_bytes, lte_used_bytes, lte_boost_bytes, lte_used_baseline_bytes, lte_baseline_reset_requested, lte_reset_at, premium_state)` | — | — |
| 7025 | `delete_plan(plan_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_plan_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_plan_route` |
| 7036 | `update_plan(plan_id, plan_name, months, price, duration_days, traffic_limit_bytes, hwid_device_limit, lte_limit_bytes, main_reset_price_rub)` | — | `src/shop_bot/bot/admin_handlers.py::admin_plan_edit_days_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_devices_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_lte_limit_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_main_reset_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_months_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_name_received` |
| 7075 | `register_user_if_not_exists(telegram_id, username, referrer_id)` | Зарегистрировать пользователя, если его ещё нет. | `src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 7100 | `add_to_referral_balance(user_id, amount)` | — | `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount`<br>`src/shop_bot/data_manager/database.py::refund_payment_once`<br>`src/shop_bot/webapp/handlers.py::_apply_pending_referral` |
| 7111 | `set_referral_balance(user_id, value)` | — | `src/shop_bot/bot/admin_handlers.py::approve_withdraw_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 7120 | `set_referral_balance_all(user_id, value)` | — | `src/shop_bot/bot/admin_handlers.py::approve_withdraw_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 7129 | `add_to_referral_balance_all(user_id, amount)` | — | `src/shop_bot/bot/handlers.py::_maybe_pay_referral_start_bonus`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/webapp/handlers.py::_apply_pending_referral` |
| 7141 | `get_referral_balance_all(user_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_user_referrals`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 7152 | `get_referral_balance(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount`<br>`src/shop_bot/bot/handlers.py::referral_transfer_start`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_amount`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_choose_method` |
| 7163 | `get_balance(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::lte_gb_pick_handler`<br>`src/shop_bot/bot/handlers.py::main_reset_start_handler`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount` |
| 7174 | `adjust_user_balance(user_id, delta)` | Скорректировать баланс пользователя на указанную дельту (может быть отрицательной). | `src/shop_bot/webhook_server/app.py::adjust_balance_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 7186 | `adjust_user_referral_balance(user_id, delta)` | Скорректировать реферальный баланс пользователя на указанную дельту (может быть отрицательной). | `src/shop_bot/webhook_server/app.py::adjust_referral_balance_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 7198 | `set_balance(user_id, value)` | — | — |
| 7209 | `add_to_balance(user_id, amount)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::handle_main_amount`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount`<br>`src/shop_bot/data_manager/database.py::refund_payment_once` |
| 7238 | `deduct_from_balance(user_id, amount)` | Атомарное списание с основного баланса при достаточности средств. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::handle_deduct_amount`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_balance_handler`<br>`src/shop_bot/bot/handlers.py::mainreset_pay_balance_handler`<br>`src/shop_bot/bot/handlers.py::pay_with_main_balance_handler` |
| 7262 | `deduct_from_referral_balance(user_id, amount)` | Атомарное списание с реферального баланса при достаточности средств. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_referral_balance_handler`<br>`src/shop_bot/bot/handlers.py::mainreset_pay_referral_balance_handler`<br>`src/shop_bot/bot/handlers.py::pay_with_referral_balance_handler`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_referral_balance_handler` |
| 7300 | `_referral_setting_is_true(key, default)` | — | `src/shop_bot/data_manager/database.py::is_referral_withdraw_method_type_enabled` |
| 7305 | `is_referral_withdraw_method_type_enabled(method_type)` | — | `src/shop_bot/data_manager/database.py::create_referral_withdrawal_request` |
| 7312 | `validate_referral_payout_requisite(method_type, requisite_value, bank_name)` | Проверить реквизиты метода получения перед сохранением. | `src/shop_bot/data_manager/database.py::add_referral_payout_method` |
| 7339 | `format_referral_withdrawal_admin_notice(request_id, user_id, username, amount, method_type, bank_name, requisite_value)` | Текст уведомления админам о новой заявке на вывод. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_amount`<br>`src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 7366 | `list_referral_payout_methods(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_delete`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_value`<br>`src/shop_bot/bot/handlers.py::referral_payout_methods`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_start`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_list` |
| 7381 | `add_referral_payout_method(user_id, method_type, requisite_value, bank_name)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_value`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_add` |
| 7403 | `delete_referral_payout_method(method_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_delete`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_delete` |
| 7420 | `get_referral_payout_method(method_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_amount`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_choose_method`<br>`src/shop_bot/data_manager/database.py::create_referral_withdrawal_request`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_delete`<br>`src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 7439 | `create_webapp_auth_request(token)` | Создаёт запись ожидания подтверждения входа через deep-link бота (user_id пока NULL). | `src/shop_bot/webapp/handlers.py::api_request_auth_token` |
| 7455 | `confirm_webapp_auth_request(token, user_id)` | Подтверждает вход: бот вызывает эту функцию после получения deep-link auth_{token}. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 7474 | `get_webapp_auth_request(token, consume)` | Возвращает user_id, если запрос уже подтверждён ботом, иначе None. | `src/shop_bot/webapp/handlers.py::api_check_auth_token` |
| 7496 | `cleanup_old_webapp_auth_requests(max_age_minutes)` | — | `src/shop_bot/webapp/handlers.py::api_request_auth_token` |
| 7509 | `create_referral_withdrawal_request(user_id, amount, method_id)` | Атомарно списывает сумму с referral_balance пользователя и создаёт заявку на вывод. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_amount`<br>`src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 7572 | `has_open_referral_withdrawal_request(user_id)` | Есть ли у пользователя незакрытая заявка (new/processing). | `src/shop_bot/webapp/handlers.py::api_referral_request_withdraw`<br>`src/shop_bot/webapp/handlers.py::api_user_referral_info` |
| 7591 | `list_referral_withdrawal_requests(status, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_requests`<br>`src/shop_bot/webapp/handlers.py::api_referral_list_withdrawals`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::referral_program_requests_page` |
| 7619 | `get_referral_withdrawal_request(request_id)` | — | `src/shop_bot/data_manager/database.py::update_referral_withdrawal_request_status` |
| 7640 | `update_referral_withdrawal_request_status(request_id, new_status, reject_reason)` | Меняет статус заявки на вывод. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::referral_program_request_status_route` |
| 7720 | `get_referral_withdrawable_stats()` | Сводка по заявкам на вывод (для админ-панели): счётчики по статусам и суммы. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data` |
| 7736 | `get_referral_count(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/bot/handlers.py::referral_program_handler`<br>`src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::api_user_referral_info` |
| 7746 | `get_user(telegram_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_ban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days`<br>`src/shop_bot/bot/admin_handlers.py::admin_unban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_user_referrals`<br>`src/shop_bot/bot/admin_handlers.py::admin_users_search_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_view_admins` |
| 7759 | `get_user_by_username(username)` | Возвращает пользователя по username (без @), регистр не важен. | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/modules/remnawave_api.py::ensure_user`<br>`src/shop_bot/modules/remnawave_api.py::lookup_panel_user` |
| 7775 | `set_terms_agreed(telegram_id)` | — | `src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_onboarding`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 7785 | `is_subscription_expiry_notifications_enabled(telegram_id)` | Проверить, включены ли уведомления об истечении срока ключа. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/data_manager/scheduler.py::check_expiring_subscriptions` |
| 7802 | `toggle_subscription_expiry_notifications(telegram_id)` | Переключить статус уведомлений об истечении срока. Возвращает новое состояние. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::toggle_expiry_notifications_handler` |
| 7828 | `update_user_stats(telegram_id, amount_spent, months_purchased)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 7837 | `get_user_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::dashboard_page`<br>`src/shop_bot/webhook_server/app.py::dashboard_stats_partial` |
| 7847 | `get_total_keys_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::dashboard_page`<br>`src/shop_bot/webhook_server/app.py::dashboard_stats_partial` |
| 7857 | `get_total_spent_sum()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::dashboard_page`<br>`src/shop_bot/webhook_server/app.py::dashboard_stats_partial` |
| 7876 | `create_pending_transaction(payment_id, user_id, amount_rub, metadata)` | Create a pending transaction row in `transactions`. | `src/shop_bot/bot/handlers.py::create_ton_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::topup_pay_tonconnect` |
| 7904 | `find_and_complete_ton_transaction(payment_id, amount_ton)` | Atomically completes a TON transaction. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::ton_webhook_handler` |
| 8006 | `_describe_transaction_action(metadata)` | Формирует человекочитаемое описание действия транзакции по её metadata. | `src/shop_bot/data_manager/database.py::get_paginated_transactions`<br>`src/shop_bot/data_manager/database.py::get_transactions_paginated` |
| 8025 | `_find_nearest_key_id(cursor, user_id, host_name, created_date, window_minutes)` | Best-effort подбор ключа для старых транзакций, в metadata которых ещё не сохранялся key_id. | `src/shop_bot/data_manager/database.py::get_paginated_transactions`<br>`src/shop_bot/data_manager/database.py::get_transactions_paginated` |
| 8062 | `log_transaction(username, transaction_id, payment_id, user_id, status, amount_rub, amount_currency, currency_name, payment_method, metadata)` | Записывает транзакцию в таблицу `transactions`. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount` |
| 8076 | `_work()` | — | — |
| 8130 | `get_paginated_transactions(page, per_page)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::dashboard_page`<br>`src/shop_bot/webhook_server/app.py::dashboard_transactions_partial` |
| 8181 | `get_transactions_paginated(page, per_page, user_id, search, sort_by, sort_dir)` | Универсальная выборка транзакций с фильтром по пользователю, поиском и сортировкой. | `src/shop_bot/webapp/handlers.py::api_user_transactions`<br>`src/shop_bot/webhook_server/app.py::analytics_transactions_csv`<br>`src/shop_bot/webhook_server/app.py::analytics_transactions_page`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::user_details_json`<br>`src/shop_bot/webhook_server/app.py::user_transactions_partial` |
| 8280 | `set_trial_used(telegram_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation` |
| 8290 | `add_new_key(user_id, host_name, remnawave_user_uuid, key_email, expiry_timestamp_ms, squad_uuid, short_uuid, subscription_url, traffic_limit_bytes, traffic_limit_strategy, …)` | — | `src/shop_bot/data_manager/database.py::create_gift_key`<br>`src/shop_bot/data_manager/remnawave_repository.py::record_key` |
| 8365 | `_apply_key_updates(key_id, updates)` | — | `src/shop_bot/data_manager/database.py::update_key_fields` |
| 8387 | `update_key_fields(key_id, user_id, host_name, squad_uuid, remnawave_user_uuid, short_uuid, email, subscription_url, expire_at_ms, traffic_limit_bytes, …)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::sync_user_keys_with_remnawave`<br>`src/shop_bot/data_manager/database.py::apply_key_monthly_reset_fields`<br>`src/shop_bot/data_manager/database.py::update_key_email`<br>`src/shop_bot/data_manager/database.py::update_key_host` |
| 8446 | `apply_key_monthly_reset_fields(key_id, plan, restart_cycle, key, expire_main_boost)` | Записать `traffic_limit_strategy` и `next_traffic_reset_at` по тарифу ключа. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/database.py::backfill_monthly_traffic_reset_for_existing_keys`<br>`src/shop_bot/data_manager/scheduler.py::check_auto_renewals`<br>`src/shop_bot/webhook_server/app.py::admin_key_change_plan_route`<br>`src/shop_bot/webhook_server/app.py::create_key_ajax_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 8491 | `backfill_monthly_traffic_reset_for_existing_keys()` | Проставить MONTH_ROLLING и дату сброса уже выданным лимитным/LTE-ключам. | `src/shop_bot/data_manager/database.py::run_migration` |
| 8533 | `delete_key_by_email(email)` | — | `src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8571 | `get_user_keys(user_id)` | — | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::cancel_search_keys_handler`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial`<br>`src/shop_bot/bot/handlers.py::manage_keys_handler` |
| 8587 | `get_key_by_id(key_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_delete_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_edit_key`<br>`src/shop_bot/bot/admin_handlers.py::admin_extend_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_back`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_cancel`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm` |
| 8600 | `get_key_by_email(key_email)` | — | `src/shop_bot/bot/admin_handlers.py::admin_delete_key_process`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/database.py::update_key_status_from_server`<br>`src/shop_bot/data_manager/remnawave_repository.py::generate_key_email_for_user`<br>`src/shop_bot/data_manager/remnawave_repository.py::record_key`<br>`src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8617 | `get_key_by_remnawave_uuid(remnawave_uuid)` | — | `src/shop_bot/data_manager/remnawave_repository.py::record_key` |
| 8636 | `update_key_info(key_id, new_remnawave_uuid, new_expiry_ms, **kwargs)` | — | — |
| 8645 | `update_key_host_and_info(key_id, new_host_name, new_remnawave_uuid, new_expiry_ms, **kwargs)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch` |
| 8661 | `get_next_key_number(user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation`<br>`src/shop_bot/data_manager/remnawave_repository.py::generate_key_email_for_user` |
| 8665 | `get_keys_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_host_keys_pick_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_back`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8682 | `set_key_auto_renew(key_id, enabled)` | — | `src/shop_bot/bot/handlers.py::auto_renew_key_toggle`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/webapp/handlers.py::api_key_auto_renew` |
| 8694 | `set_all_keys_auto_renew_for_user(user_id, enabled)` | Mass-update auto_renew for all keys of a user. Returns count of updated rows. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::toggle_auto_renew_profile` |
| 8707 | `get_keys_for_auto_renew(hours_before)` | Return keys with auto_renew=1 expiring within the next `hours_before` hours. | `src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 8733 | `_key_matches_search(data, needle_lower)` | Регистронезависимая (в т.ч. кириллица) проверка вхождения подстроки | `src/shop_bot/data_manager/database.py::search_all_keys_by_email`<br>`src/shop_bot/data_manager/database.py::search_user_keys_by_email` |
| 8744 | `search_user_keys_by_email(user_id, search_query)` | Поиск ключей пользователя по key_email, email или user_key_name. | `src/shop_bot/bot/admin_handlers.py::admin_search_user_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::search_keys_input_handler`<br>`src/shop_bot/webapp/handlers.py::api_keys_search` |
| 8766 | `search_all_keys_by_email(search_query)` | Поиск всех ключей (администраторам) по key_email, email или user_key_name. | `src/shop_bot/bot/admin_handlers.py::admin_search_all_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8787 | `get_all_vpn_users()` | — | — |
| 8800 | `update_key_status_from_server(key_email, client_data)` | — | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 8843 | `get_daily_stats_for_charts(days)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::dashboard_charts_json`<br>`src/shop_bot/webhook_server/app.py::dashboard_page`<br>`src/shop_bot/webhook_server/app.py::statistics_page` |
| 8878 | `get_recent_transactions(limit)` | — | — |
| 8914 | `get_all_users()` | — | `src/shop_bot/bot/admin_handlers.py::admin_add_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_balance_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_balance_pick_user_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_deduct_balance_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_deduct_balance_pick_user_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_back_to_users` |
| 8925 | `get_users_paginated(page, per_page, q, sort)` | Вернуть пользователей постранично и общее количество (с учётом фильтра). | `src/shop_bot/webhook_server/app.py::admin_global_search_json`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::users_page`<br>`src/shop_bot/webhook_server/app.py::users_pagination_partial`<br>`src/shop_bot/webhook_server/app.py::users_search_json`<br>`src/shop_bot/webhook_server/app.py::users_table_partial` |
| 9043 | `get_keys_counts_for_users(user_ids)` | Вернуть словарь {user_id: keys_count} по списку пользователей. | — |
| 9063 | `ban_user(telegram_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_ban_user`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/support_bot/handlers.py::admin_ban_user`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/webhook_server/app.py::ban_user_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 9072 | `unban_user(telegram_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_unban_user`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/support_bot/handlers.py::admin_unban_user`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::unban_user_route` |
| 9091 | `mark_user_unreachable(telegram_id, reason)` | Отметить пользователя как недоступного в Telegram. | `src/shop_bot/modules/telegram_reachability.py::handle_send_exception` |
| 9117 | `mark_user_reachable(telegram_id)` | Снять отметку недоступности — пользователь снова взаимодействовал с ботом | `src/shop_bot/bot/middlewares.py::BanMiddleware.__call__` |
| 9137 | `get_reachability_stats()` | Статистика по доступности пользователей в Telegram: сколько всего | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::statistics_page` |
| 9168 | `delete_user_keys(user_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::revoke_keys_route` |
| 9185 | `delete_user_completely(user_id)` | Полностью удалить пользователя и все связанные с ним данные. | `src/shop_bot/bot/admin_handlers.py::admin_delete_user`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_user_route` |
| 9306 | `create_support_ticket(user_id, subject)` | — | — |
| 9332 | `get_or_create_open_ticket(user_id, subject)` | Возвращает ID открытого тикета пользователя и флаг, создан ли новый. | `src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum`<br>`src/shop_bot/support_bot/handlers.py::support_message_received`<br>`src/shop_bot/webapp/handlers.py::api_support_create` |
| 9358 | `add_support_message(ticket_id, sender, content, media)` | — | `src/shop_bot/bot/handlers.py::forum_thread_message_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/support_bot/handlers.py::admin_note_receive`<br>`src/shop_bot/support_bot/handlers.py::forum_thread_message_handler`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum` |
| 9376 | `update_ticket_thread_info(ticket_id, forum_chat_id, message_thread_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum`<br>`src/shop_bot/support_bot/handlers.py::support_message_received`<br>`src/shop_bot/support_bot/handlers.py::support_reply_received` |
| 9390 | `get_ticket(ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::_admin_actions_kb`<br>`src/shop_bot/support_bot/handlers.py::admin_ban_user`<br>`src/shop_bot/support_bot/handlers.py::admin_close_ticket`<br>`src/shop_bot/support_bot/handlers.py::admin_delete_ticket`<br>`src/shop_bot/support_bot/handlers.py::admin_list_notes`<br>`src/shop_bot/support_bot/handlers.py::admin_note_prompt` |
| 9402 | `get_ticket_by_thread(forum_chat_id, message_thread_id)` | — | `src/shop_bot/bot/handlers.py::forum_thread_message_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/support_bot/handlers.py::forum_thread_message_handler`<br>`src/shop_bot/support_bot/handlers.py::get_support_router` |
| 9417 | `get_user_tickets(user_id, status)` | — | `src/shop_bot/support_bot/handlers.py::_get_latest_open_ticket`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::my_tickets_text_button`<br>`src/shop_bot/support_bot/handlers.py::support_my_tickets_handler`<br>`src/shop_bot/webapp/handlers.py::api_support_create`<br>`src/shop_bot/webapp/handlers.py::api_support_status` |
| 9437 | `get_support_message(message_id)` | Одно сообщение тикета. Нужно для отдачи вложений в панели. | `src/shop_bot/webapp/handlers.py::api_support_ticket_file`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_ticket_file` |
| 9454 | `resolve_db_file_path(db_file)` | Абсолютный путь к users.db без зависимости от cwd процесса. | `src/shop_bot/data_manager/database.py::get_ticket_media_root` |
| 9473 | `get_ticket_media_root()` | Каталог вложений рядом с users.db, не в webhook_server/. | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/data_manager/scheduler.py::_ticket_files_present`<br>`src/shop_bot/support_bot/ticket_media.py::jailed_ticket_folder`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::ticket_media_on_disk`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket_file` |
| 9481 | `list_closed_ticket_ids_older_than(cutoff)` | Закрытые тикеты с updated_at не новее cutoff (наивный ISO-текст SQLite). | `src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 9503 | `clear_support_message_media(ticket_id)` | Обнуляет media у сообщений тикета после TTL/удаления файлов. | `src/shop_bot/support_bot/ticket_media.py::expire_ticket_media_if_closed_ttl`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 9519 | `get_ticket_messages(ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::admin_list_notes`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::support_view_ticket_handler`<br>`src/shop_bot/webapp/handlers.py::api_support_send`<br>`src/shop_bot/webapp/handlers.py::api_support_status`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket` |
| 9533 | `set_ticket_status(ticket_id, status)` | — | `src/shop_bot/support_bot/handlers.py::admin_close_ticket`<br>`src/shop_bot/support_bot/handlers.py::admin_reopen_ticket`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::support_close_ticket_handler`<br>`src/shop_bot/webapp/handlers.py::api_support_close`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 9547 | `update_ticket_subject(ticket_id, subject)` | — | `src/shop_bot/support_bot/handlers.py::admin_toggle_star`<br>`src/shop_bot/support_bot/handlers.py::get_support_router` |
| 9561 | `_cleanup_ticket_media(ticket_id)` | Файлы вложений живут вне SQLite — удаляем каталог вместе с тикетом. | `src/shop_bot/data_manager/database.py::cleanup_ticket_media_ids`<br>`src/shop_bot/data_manager/database.py::delete_ticket`<br>`src/shop_bot/data_manager/database.py::delete_user_completely` |
| 9571 | `delete_ticket(ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::admin_delete_ticket`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::delete_support_ticket_route` |
| 9593 | `_ticket_forum_target(row)` | — | `src/shop_bot/data_manager/database.py::auto_close_idle_admin_tickets`<br>`src/shop_bot/data_manager/database.py::bulk_close_open_tickets`<br>`src/shop_bot/data_manager/database.py::bulk_delete_all_tickets` |
| 9617 | `validate_ticket_auto_close_days(raw)` | Для формы настроек: только целое 0–365. | `src/shop_bot/data_manager/database.py::parse_ticket_auto_close_days`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page` |
| 9639 | `parse_ticket_auto_close_days(raw)` | 0 — выключено. Нецелое и мусор → 0. Целое больше 365 режем потолком. | `src/shop_bot/data_manager/database.py::auto_close_idle_admin_tickets`<br>`src/shop_bot/data_manager/database.py::find_open_tickets_idle_after_admin`<br>`src/shop_bot/data_manager/database.py::get_ticket_auto_close_days` |
| 9653 | `get_ticket_auto_close_days()` | — | `src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets` |
| 9657 | `find_open_tickets_idle_after_admin(days, now, limit)` | Открытые тикеты, где последнее сообщение — ответ админа старше ``days`` суток. | `src/shop_bot/data_manager/database.py::auto_close_idle_admin_tickets` |
| 9712 | `auto_close_idle_admin_tickets(days, now, limit)` | Закрывает найденные простаивающие тикеты. Форум — снаружи. | `src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets` |
| 9779 | `bulk_close_open_tickets()` | Один UPDATE всех открытых тикетов. Форум/уведомления — на стороне вызывающего. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_bulk_close_route` |
| 9807 | `bulk_delete_all_tickets()` | Один DELETE всех тикетов и сообщений. Вложения на диске не трогает. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_bulk_delete_route` |
| 9839 | `cleanup_ticket_media_ids(ticket_ids)` | Удаляет каталоги вложений пачкой. Ошибки по одному id не рвут остальные. | `src/shop_bot/webhook_server/app.py::run_bulk_ticket_followup` |
| 9854 | `get_tickets_paginated(page, per_page, status)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_list_page`<br>`src/shop_bot/webhook_server/app.py::support_table_partial` |
| 9879 | `get_open_tickets_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year`<br>`src/shop_bot/webhook_server/app.py::support_list_page`<br>`src/shop_bot/webhook_server/app.py::support_open_count_partial` |
| 9889 | `get_closed_tickets_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year`<br>`src/shop_bot/webhook_server/app.py::support_list_page` |
| 9899 | `get_all_tickets_count()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year`<br>`src/shop_bot/webhook_server/app.py::support_list_page` |
| 9915 | `get_key_usage_monitor(key_id)` | — | `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 9928 | `ensure_key_usage_monitor_row(key_id, user_id)` | — | `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 9941 | `update_key_usage_monitor(key_id, first_seen_usage_at, last_reminder_at, last_checked_at, last_devices_count, last_traffic_bytes, overlimit_notified_count, overlimit_notified_at)` | — | `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 10000 | `get_franchise_percent_default()` | Получить процент комиссии франшизы из настроек. | `src/shop_bot/bot/admin_handlers.py::_get_franchise_settings_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_cabinet`<br>`src/shop_bot/data_manager/database.py::accrue_partner_commission`<br>`src/shop_bot/data_manager/database.py::get_partner_cabinet` |
| 10009 | `get_franchise_min_withdraw()` | Получить минимум для вывода франшизников из настроек. | `src/shop_bot/bot/admin_handlers.py::_get_franchise_settings_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_cabinet`<br>`src/shop_bot/bot/handlers.py::partner_withdraw`<br>`src/shop_bot/bot/handlers.py::partner_withdraw_amount` |
| 10018 | `resolve_factory_bot_id(telegram_bot_user_id)` | Return internal managed bot id for a Telegram bot user id. | `src/shop_bot/bot/handlers.py::franchise_create_bot`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_cabinet`<br>`src/shop_bot/bot/handlers.py::partner_requisite_add`<br>`src/shop_bot/bot/handlers.py::partner_requisite_bank`<br>`src/shop_bot/bot/handlers.py::partner_requisite_delete` |
| 10042 | `_managed_bot_token_secret()` | Ключ шифрования токенов клонов: SHOPBOT_SECRET_KEY или стабильная запись в settings. | `src/shop_bot/data_manager/database.py::decrypt_managed_bot_token`<br>`src/shop_bot/data_manager/database.py::encrypt_managed_bot_token` |
| 10054 | `_managed_bot_token_pad(secret, nonce, n)` | — | `src/shop_bot/data_manager/database.py::decrypt_managed_bot_token`<br>`src/shop_bot/data_manager/database.py::encrypt_managed_bot_token` |
| 10063 | `_backfill_encrypt_secrets_at_rest()` | Зашифровать уже сохранённые plaintext-секреты (settings / hosts / SSH-цели). | `src/shop_bot/data_manager/database.py::initialize_db`<br>`src/shop_bot/data_manager/database.py::run_migration` |
| 10118 | `encrypt_managed_bot_token(token)` | Зашифровать токен клона для хранения. Уже enc1$ не трогаем. | `src/shop_bot/data_manager/database.py::_backfill_encrypt_secrets_at_rest`<br>`src/shop_bot/data_manager/database.py::create_managed_bot`<br>`src/shop_bot/data_manager/database.py::create_ssh_target`<br>`src/shop_bot/data_manager/database.py::update_host_remnawave_settings`<br>`src/shop_bot/data_manager/database.py::update_host_ssh_settings`<br>`src/shop_bot/data_manager/database.py::update_setting` |
| 10134 | `decrypt_managed_bot_token(stored)` | Расшифровать токен. Legacy plaintext (без enc1$) возвращается как есть. | `src/shop_bot/data_manager/database.py::_decrypt_row_secrets`<br>`src/shop_bot/data_manager/database.py::_row_with_decrypted_token`<br>`src/shop_bot/data_manager/database.py::get_all_settings`<br>`src/shop_bot/data_manager/database.py::get_setting`<br>`src/shop_bot/data_manager/database.py::seed_global_remnawave_from_hosts`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 10157 | `_row_with_decrypted_token(row)` | — | `src/shop_bot/data_manager/database.py::get_managed_bot`<br>`src/shop_bot/data_manager/database.py::get_managed_bot_by_telegram_id`<br>`src/shop_bot/data_manager/database.py::list_active_managed_bots` |
| 10166 | `get_managed_bot(bot_id)` | — | `src/shop_bot/bot/handlers.py::_notify_user_key_creation_error`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_cabinet`<br>`src/shop_bot/bot/handlers.py::partner_requisite_add`<br>`src/shop_bot/bot/handlers.py::partner_requisite_bank`<br>`src/shop_bot/bot/handlers.py::partner_requisite_delete` |
| 10179 | `get_managed_bot_by_telegram_id(telegram_bot_user_id)` | — | — |
| 10192 | `list_active_managed_bots()` | — | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_all` |
| 10204 | `update_managed_bot_active(bot_id, is_active)` | Параметризованно выставить is_active (0/1). Схему таблицы не меняет. | `src/shop_bot/factory_bot/service.py::ManagedBotsService.runner`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot` |
| 10222 | `get_managed_bots_by_owner(owner_telegram_id)` | Список клонов владельца без токена (токен не отдаём в UI). | — |
| 10248 | `purge_managed_bot_stats(bot_id)` | Удалить активность и комиссии клона. Идемпотентно, ошибки не пробрасывает. | — |
| 10263 | `_purge_managed_bot_stats_on_cursor(cur, bot_id)` | — | `src/shop_bot/data_manager/database.py::delete_managed_bot`<br>`src/shop_bot/data_manager/database.py::purge_managed_bot_stats` |
| 10268 | `delete_managed_bot(bot_id, owner_telegram_id)` | Удалить строку managed_bots и статистику клона. | `src/shop_bot/factory_bot/handlers.py::delete_bot_confirm`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_delete_bot_route` |
| 10319 | `get_factory_cabinet(bot_id)` | Статистика кабинета клона (пользователи/сообщения/прямые клоны/баланс). | `src/shop_bot/factory_bot/handlers.py::cabinet`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router` |
| 10355 | `create_managed_bot(token, telegram_bot_user_id, username, owner_telegram_id, referrer_bot_id)` | Register a managed bot. | `src/shop_bot/bot/handlers.py::franchise_receive_token`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 10422 | `record_factory_activity(bot_id, user_id)` | Upsert activity row (unique users + messages count). | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__` |
| 10452 | `_is_card_payment_method(method)` | — | `src/shop_bot/data_manager/database.py::accrue_partner_commission` |
| 10462 | `accrue_partner_commission(bot_id, payment_id, user_id, amount_rub, payment_method, percent)` | Accrue partner commission for a managed bot. | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 10574 | `get_partner_cabinet(bot_id)` | Return partner cabinet stats for managed bot. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_cabinet`<br>`src/shop_bot/bot/handlers.py::partner_withdraw`<br>`src/shop_bot/bot/handlers.py::partner_withdraw_amount`<br>`src/shop_bot/data_manager/database.py::create_withdraw_request`<br>`src/shop_bot/data_manager/database.py::get_factory_cabinet` |
| 10622 | `list_partner_requisites(bot_id, owner_telegram_id)` | Return all payout requisites for a partner (owner) within a managed bot. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_delete`<br>`src/shop_bot/bot/handlers.py::partner_requisite_set_default`<br>`src/shop_bot/bot/handlers.py::partner_requisite_value`<br>`src/shop_bot/bot/handlers.py::partner_requisites`<br>`src/shop_bot/bot/handlers.py::partner_withdraw` |
| 10647 | `get_default_partner_requisite(bot_id, owner_telegram_id)` | Return the default payout requisite for a partner, if any. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_withdraw`<br>`src/shop_bot/bot/handlers.py::partner_withdraw_amount` |
| 10659 | `add_partner_requisite(bot_id, owner_telegram_id, bank, requisite_value, requisite_type, make_default)` | Add a payout requisite for a partner. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_value` |
| 10729 | `set_default_partner_requisite(req_id, bot_id, owner_telegram_id)` | Set given requisite as default for this bot/owner. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_set_default` |
| 10766 | `delete_partner_requisite(req_id, bot_id, owner_telegram_id)` | Delete a payout requisite. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_delete` |
| 10814 | `create_withdraw_request(bot_id, owner_telegram_id, amount_rub, comment, bank, requisite_type, requisite_value, requisite_id)` | Create a partner withdraw request. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_withdraw_amount` |
| 10869 | `create_user_gift(from_user_id, host_name, plan_id, gift_code, expires_in_days)` | Создать неактивированный подарок от одного пользователя. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/webhook_server/app.py::create_key_ajax_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 10920 | `get_user_gift(gift_id)` | Получить информацию о подарке по ID. | `src/shop_bot/bot/handlers.py::activate_own_gift_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::send_gift_link_handler`<br>`src/shop_bot/bot/handlers.py::show_gift_handler` |
| 10934 | `get_gift_by_code(gift_code)` | Получить информацию о подарке по коду. | `src/shop_bot/bot/handlers.py::_activate_gift_directly`<br>`src/shop_bot/data_manager/database.py::activate_user_gift`<br>`src/shop_bot/webapp/handlers.py::_activate_gift_for_user`<br>`src/shop_bot/webapp/handlers.py::_pending_action_public_info`<br>`src/shop_bot/webapp/handlers.py::web_gift_page` |
| 10948 | `get_user_inactive_gifts(from_user_id)` | Получить список неактивированных подарков пользователя. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::gifts_page_handler`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/bot/handlers.py::show_inactive_gifts_handler`<br>`src/shop_bot/bot/handlers.py::show_main_menu` |
| 10982 | `activate_user_gift(gift_code, activated_by_user_id)` | Активировать подарок для пользователя. | `src/shop_bot/bot/handlers.py::_activate_gift_directly`<br>`src/shop_bot/webapp/handlers.py::_activate_gift_for_user` |
| 11039 | `_registration_age_seconds(reg_date_raw)` | Возраст аккаунта в секундах, либо None если даты нет / она не парсится. | `src/shop_bot/data_manager/database.py::link_referrer_if_eligible`<br>`src/shop_bot/data_manager/database.py::set_referred_by_from_gift` |
| 11052 | `set_referred_by_from_gift(user_id, from_user_id, max_age_seconds)` | Set referred_by to the gift sender when a new user activates a gift. | `src/shop_bot/bot/handlers.py::_activate_gift_directly`<br>`src/shop_bot/webapp/handlers.py::_activate_gift_for_user` |
| 11101 | `link_referrer_if_eligible(user_id, referrer_id, max_age_seconds)` | Привязать пользователя к рефереру (users.referred_by), если это допустимо. | `src/shop_bot/webapp/handlers.py::_apply_pending_referral`<br>`src/shop_bot/webhook_server/app.py::assign_referral_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 11179 | `unlink_referral(invitee_id, referrer_id)` | Снять привязку реферала: обнулить users.referred_by у invitee, если он | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::remove_referral_route` |
| 11217 | `unlink_all_referrals(referrer_id)` | Снять привязку у всех рефералов указанного реферера. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::remove_all_referrals_route` |
| 11244 | `delete_user_gift(gift_id)` | Удалить подарок. | — |
| 11257 | `link_key_to_gift(gift_id, key_id)` | Связать созданный ключ с подарком. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/webhook_server/app.py::create_key_ajax_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 11273 | `get_gift_code_by_key_id(key_id)` | Получить код подарка по ID ключа. | — |
| 11286 | `get_gift_code_by_key_id(key_id)` | Получить код подарка по ID ключа. | — |
| 11299 | `get_gift_info_by_key_id(key_id)` | Получить ID и код подарка по ID ключа. Возвращает (gift_id, gift_code) или (None, None). | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process` |
| 11319 | `get_msk_time()` | Текущее время в московской зоне (UTC+3), используется для расчётов сроков в webapp. | `src/shop_bot/webapp/handlers.py::_get_profile_card_html`<br>`src/shop_bot/webapp/handlers.py::_process_key_data`<br>`src/shop_bot/webapp/handlers.py::_render_main_page` |
| 11325 | `check_transaction_exists(payment_id)` | Проверить, существует ли уже завершённая транзакция с данным payment_id. | `src/shop_bot/webapp/handlers.py::api_check_payment`<br>`src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 11353 | `payment_owned_by_user(payment_id, user_id)` | True, если payment_id есть в pending_transactions или transactions у этого user_id. | `src/shop_bot/webapp/handlers.py::api_check_payment`<br>`src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 11367 | `_work()` | — | — |
| 11390 | `get_seller_user(user_id)` | Вернуть данные продавца (франшиза/партнёрская скидка) для пользователя. | `src/shop_bot/webapp/handlers.py::calculate_webapp_price` |
| 11407 | `get_device_tiers(host_name)` | Вернуть тарифные планы, сгруппированные по лимиту устройств, для указанного хоста. | `src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_device_tiers` |
| 11423 | `get_user_by_auth_token(token)` | Найти пользователя по постоянному auth-токену (webapp). | `src/shop_bot/webapp/handlers.py::_resolve_user_from_request_token`<br>`src/shop_bot/webapp/handlers.py::api_check_auth_token`<br>`src/shop_bot/webapp/handlers.py::api_sync_tg`<br>`src/shop_bot/webapp/handlers.py::dynamic_route`<br>`src/shop_bot/webapp/handlers.py::index` |
| 11439 | `get_auth_token_by_user_id(user_id)` | Получить уже выданный постоянный auth-токен пользователя, если есть. | `src/shop_bot/webapp/handlers.py::_issue_persistent_token_for_telegram_user`<br>`src/shop_bot/webapp/handlers.py::api_check_auth_token`<br>`src/shop_bot/webapp/handlers.py::api_telegram_direct_auth` |
| 11452 | `update_user_auth_token(user_id, token)` | Сохранить постоянный auth-токен для пользователя (webapp). | `src/shop_bot/webapp/handlers.py::_issue_persistent_token_for_telegram_user`<br>`src/shop_bot/webapp/handlers.py::api_check_auth_token`<br>`src/shop_bot/webapp/handlers.py::api_email_login`<br>`src/shop_bot/webapp/handlers.py::api_email_verify`<br>`src/shop_bot/webapp/handlers.py::api_telegram_direct_auth` |
| 11465 | `invalidate_all_user_auth_tokens()` | Перевыпустить все persistent auth_token пользователей (UUID4). | — |
| 11494 | `hash_password(password)` | Хэшировать пароль пользователя (PBKDF2-HMAC-SHA256 со случайной солью). | `src/shop_bot/data_manager/database.py::create_user_by_email`<br>`src/shop_bot/data_manager/database.py::update_user_password`<br>`src/shop_bot/data_manager/database.py::update_user_password_by_id` |
| 11501 | `verify_password(password, stored)` | Проверить пароль против сохранённого хэша. | `src/shop_bot/webapp/handlers.py::api_email_login`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_password` |
| 11520 | `get_user_by_email(email)` | Найти локального пользователя webapp по email (для входа по email+паролю). | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host`<br>`src/shop_bot/modules/remnawave_api.py::ensure_user`<br>`src/shop_bot/modules/remnawave_api.py::lookup_panel_user`<br>`src/shop_bot/webapp/handlers.py::api_email_login`<br>`src/shop_bot/webapp/handlers.py::api_email_register` |
| 11537 | `create_user_by_email(email, password)` | Создать "виртуального" (не привязанного к Telegram) пользователя webapp по email+паролю. | `src/shop_bot/webapp/handlers.py::api_email_register` |
| 11572 | `update_user_password(email, new_password)` | Обновить (хэшированный) пароль локального webapp-аккаунта по email. | `src/shop_bot/webapp/handlers.py::api_email_reset_verify` |
| 11589 | `_hash_verification_code(user_id, code)` | — | `src/shop_bot/data_manager/database.py::check_email_verification_code`<br>`src/shop_bot/data_manager/database.py::set_email_verification_code` |
| 11593 | `set_email_verification_code(user_id, code, ttl_seconds)` | Сохранить хэш одноразового кода подтверждения email и время его истечения. | `src/shop_bot/webapp/handlers.py::_issue_email_verification_code` |
| 11615 | `get_email_verification(user_id)` | Вернуть данные о статусе подтверждения email и последнем отправленном коде. | `src/shop_bot/data_manager/database.py::check_email_verification_code`<br>`src/shop_bot/webapp/handlers.py::api_email_resend`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_email_resend` |
| 11635 | `check_email_verification_code(user_id, code)` | Проверить введённый код подтверждения против сохранённого хэша (с учётом срока действия). | `src/shop_bot/webapp/handlers.py::api_email_verify`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_email_verify` |
| 11650 | `mark_email_verified(user_id)` | Отметить email пользователя как подтверждённый и очистить код. | `src/shop_bot/webapp/handlers.py::api_email_verify` |
| 11670 | `update_email_code_last_sent(user_id)` | Обновить время последней отправки кода (для rate-limit повторной отправки). | — |
| 11686 | `update_user_password_by_id(user_id, new_password)` | Обновить (хэшированный) пароль webapp-аккаунта по telegram_id (смена пароля из профиля, | `src/shop_bot/webapp/handlers.py::api_user_profile_change_password` |
| 11701 | `set_pending_email(user_id, new_email)` | Сохранить новый email, ожидающий подтверждения кодом (смена почты из профиля). | `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request` |
| 11718 | `clear_pending_email(user_id)` | Отменить ожидающую смену email (например, пользователь передумал или запросил другой адрес). | `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_cancel`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request` |
| 11735 | `finalize_pending_email_change(user_id)` | Подтвердить смену email кодом: перенести `pending_email` в `auth_email`. | `src/shop_bot/webapp/handlers.py::api_user_profile_change_email_verify` |
| 11783 | `get_webapp_settings()` | Вернуть настройки Telegram Mini App (webapp) из общей таблицы bot_settings. | `src/shop_bot/bot/handlers.py::_webapp_public_base`<br>`src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::dynamic_route`<br>`src/shop_bot/webapp/handlers.py::index`<br>`src/shop_bot/webapp/handlers.py::web_gift_page`<br>`src/shop_bot/webapp/handlers.py::web_referral_page` |

## src/shop_bot/bot/admin_handlers.py

Админ-меню Telegram: хосты, тарифы, пользователи, рассылка, speedtest, модули, бэкап.

**Классы:** `AdminSettings`, `AdminModules`, `Broadcast`, `IsAdminFilter`, `AdminAccessMiddleware`, `ButtonConstructor`, `AdminPayments`, `AdminReferral`, `AdminFranchise`, `AdminHosts`, `AdminTrial`, `AdminLteSettings`, `AdminNotifications`, `AdminPlans`, `AdminPromoCreate`, `AdminRestoreDB`, `AdminUserSearch`, `AdminExtendSingleKey`, `AdminAddAdmin`, `AdminRemoveAdmin`, `AdminEditKeyEmail`, `AdminGiftKey`, `AdminMainRefill`, `AdminMainDeduct`, `AdminHostKeys`, `AdminQuickDeleteKey`, `AdminExtendKey`, `AdminAutoRenew`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 99 | `_is_true(value)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_get_inactive_reminder_enabled`<br>`src/shop_bot/bot/admin_handlers.py::_get_payments_status_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::_payment_detail_text`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle` |
| 103 | `_mask_secret(value)` | — | `src/shop_bot/bot/admin_handlers.py::_payment_detail_text`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 136 | `async IsAdminFilter.__call__(self, event, event_from_user)` | — | — |
| 156 | `async AdminAccessMiddleware.__call__(self, handler, event, data)` | — | — |
| 178 | `get_admin_router()` | — | `src/shop_bot/bot_controller.py::BotController.start` |
| 186 | `_format_user_mention(u)` | — | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_run`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_all`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_all_targets`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_target`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_target_hashed`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 203 | `_resolve_target_from_hash(cb_data)` | — | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_autoinstall_target_hashed`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_target_hashed`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 222 | `async show_admin_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_add_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_cancel_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_back_to_users`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_back_to_admin`<br>`src/shop_bot/bot/admin_handlers.py::admin_remove_admin_process` |
| 260 | `async show_admin_promo_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_menu_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 274 | `_parse_datetime_input(raw)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_set_valid_from`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_set_valid_until`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 285 | `_format_promo_line(promo)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_change_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_list`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 337 | `_build_promo_list_keyboard(codes, page, page_size)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_change_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_list`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 365 | `async show_admin_system_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::open_admin_system_menu_handler` |
| 381 | `async show_admin_settings_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::btnc_cancel_any`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::open_admin_settings_menu_handler` |
| 397 | `_build_modules_keyboard(modules)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_modules_menu` |
| 415 | `async show_admin_modules_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_module_disable_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_module_enable_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::open_admin_modules_menu_handler`<br>`src/shop_bot/bot/admin_handlers.py::refresh_admin_modules_menu_handler` |
| 454 | `async open_admin_menu_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_menu')` | — |
| 461 | `async open_admin_system_menu_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_system_menu')` | — |
| 470 | `async open_admin_settings_menu_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_settings_menu')` | — |
| 479 | `async open_admin_modules_menu_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_modules')` | — |
| 488 | `async refresh_admin_modules_menu_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_modules_refresh')` | — |
| 496 | `async admin_module_enable_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_module_enable:'))` | — |
| 507 | `async admin_module_disable_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_module_disable:'))` | — |
| 541 | `_btnc_menu_label(menu_type)` | — | `src/shop_bot/bot/admin_handlers.py::_btnc_show_details`<br>`src/shop_bot/bot/admin_handlers.py::_btnc_show_list`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_start`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 547 | `_btnc_cancel_kb(back_cb)` | — | `src/shop_bot/bot/admin_handlers.py::btnc_add_action_type`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_action_value`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_button_id`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_row`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_start`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_width` |
| 554 | `async _btnc_show_menu_types(message, edit)` | — | `src/shop_bot/bot/admin_handlers.py::admin_button_constructor_root`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 573 | `_btnc_build_list_kb(menu_type, configs, page, page_size)` | — | `src/shop_bot/bot/admin_handlers.py::_btnc_show_list`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 616 | `async _btnc_show_list(message, menu_type, page, edit)` | — | `src/shop_bot/bot/admin_handlers.py::_btnc_show_details`<br>`src/shop_bot/bot/admin_handlers.py::btnc_add_finish`<br>`src/shop_bot/bot/admin_handlers.py::btnc_delete_do`<br>`src/shop_bot/bot/admin_handlers.py::btnc_open_list`<br>`src/shop_bot/bot/admin_handlers.py::btnc_select_menu_type`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 633 | `_btnc_build_details_kb(menu_type, db_id, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::_btnc_show_details`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 647 | `async _btnc_show_details(message, menu_type, db_id, edit)` | — | `src/shop_bot/bot/admin_handlers.py::btnc_edit_field_value`<br>`src/shop_bot/bot/admin_handlers.py::btnc_open_details`<br>`src/shop_bot/bot/admin_handlers.py::btnc_toggle_active`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 693 | `async admin_button_constructor_root(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_btn_constructor')` | — |
| 703 | `async btnc_select_menu_type(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_mt:'))` | — |
| 713 | `async btnc_open_list(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_list:'))` | — |
| 728 | `async btnc_open_details(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_edit:'))` | — |
| 745 | `async btnc_toggle_active(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_toggle:'))` | — |
| 765 | `async btnc_delete_confirm(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_del:'))` | — |
| 789 | `async btnc_delete_do(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_del_ok:'))` | — |
| 807 | `async btnc_cancel_any(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'btnc_cancel')` | — |
| 814 | `async btnc_action_menu(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_action_menu:'))` | — |
| 839 | `async btnc_edit_field_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_setfield:'))` | — |
| 869 | `async btnc_edit_field_value(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.editing_value))` | — |
| 924 | `async btnc_add_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('btnc_add:'))` | — |
| 941 | `async btnc_add_button_id(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.adding_button_id))` | — |
| 957 | `async btnc_add_text(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.adding_text))` | — |
| 980 | `async btnc_add_action_type(callback, state)` | HTTP-маршрут: `admin_router.callback_query(StateFilter(ButtonConstructor.adding_text), F.data.startswith('btnc_add_action:'))` | — |
| 995 | `async btnc_add_action_value(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.adding_action_value))` | — |
| 1029 | `async btnc_add_row(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.adding_row))` | — |
| 1050 | `async btnc_add_col(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.adding_col))` | — |
| 1076 | `async btnc_add_width(callback, state)` | HTTP-маршрут: `admin_router.callback_query(StateFilter(ButtonConstructor.adding_width), F.data.startswith('btnc_add_width:'))` | — |
| 1100 | `async btnc_add_sort(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter(ButtonConstructor.adding_sort))` | — |
| 1128 | `async btnc_add_finish(callback, state)` | HTTP-маршрут: `admin_router.callback_query(StateFilter(ButtonConstructor.adding_active), F.data.startswith('btnc_add_active:'))` | — |
| 1171 | `_get_payments_status_for_admin()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_payments_menu` |
| 1215 | `async show_admin_payments_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_payments_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_set_value`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1228 | `_payment_detail_text(provider)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_payment_detail` |
| 1344 | `async show_admin_payment_detail(message, provider, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_payments_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_set_value`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_yoomoney_check`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1357 | `async admin_payments_menu(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_payments_menu')` | — |
| 1367 | `async admin_payments_open(callback, state)` | HTTP-маршрут: `admin_router.callback_query(lambda c: isinstance(getattr(c, 'data', None), str) and c.data.startswith('admin_payments_open:'))` | — |
| 1379 | `async admin_payments_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(lambda c: isinstance(getattr(c, 'data', None), str) and c.data.startswith('admin_payments_toggle:'))` | — |
| 1427 | `_payment_prompt(provider, field)` | — | `src/shop_bot/bot/admin_handlers.py::admin_payments_set`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1471 | `_normalize_payment_input(value)` | — | `src/shop_bot/bot/admin_handlers.py::admin_payments_set_value`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1479 | `async admin_payments_set(callback, state)` | HTTP-маршрут: `admin_router.callback_query(lambda c: isinstance(getattr(c, 'data', None), str) and c.data.startswith('admin_payments_set:'))` | — |
| 1505 | `async admin_payments_set_value(message, state)` | HTTP-маршрут: `admin_router.message(AdminPayments.waiting_for_value)` | — |
| 1546 | `async admin_payments_yoomoney_check(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_payments_yoomoney_check')` | — |
| 1602 | `_get_bool_setting(key, default)` | — | `src/shop_bot/bot/admin_handlers.py::_get_referral_settings_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1607 | `_get_float_setting(key, default)` | — | `src/shop_bot/bot/admin_handlers.py::_get_referral_settings_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1616 | `_get_referral_settings_for_admin()` | — | `src/shop_bot/bot/admin_handlers.py::admin_referral_set_type`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_toggle_days_bonus`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_referral_menu` |
| 1630 | `_format_reward_type_human(reward_type)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_referral_menu` |
| 1640 | `async show_admin_referral_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_referral_discount_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_fixed_amount_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_menu_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_min_withdrawal_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_percent_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_start_bonus_input` |
| 1673 | `async admin_referral_menu_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral')` | — |
| 1683 | `async admin_referral_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_toggle')` | — |
| 1695 | `async admin_referral_toggle_days_bonus(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_toggle_days_bonus')` | — |
| 1707 | `async admin_referral_set_type(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_set_type')` | — |
| 1722 | `async admin_referral_type_chosen(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_referral_type:'))` | — |
| 1743 | `async admin_referral_set_percent(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_set_percent')` | — |
| 1758 | `async admin_referral_percent_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminReferral.waiting_for_percent)` | — |
| 1777 | `async admin_referral_set_fixed_amount(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_set_fixed_amount')` | — |
| 1792 | `async admin_referral_fixed_amount_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminReferral.waiting_for_fixed_amount)` | — |
| 1811 | `async admin_referral_set_start_bonus(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_set_start_bonus')` | — |
| 1826 | `async admin_referral_start_bonus_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminReferral.waiting_for_start_bonus)` | — |
| 1847 | `async admin_referral_set_min_withdrawal(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_set_min_withdrawal')` | — |
| 1862 | `async admin_referral_min_withdrawal_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminReferral.waiting_for_min_withdrawal)` | — |
| 1881 | `async admin_referral_set_discount(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_referral_set_discount')` | — |
| 1896 | `async admin_referral_discount_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminReferral.waiting_for_discount)` | — |
| 1922 | `_get_franchise_settings_for_admin()` | Получает текущие настройки франшизы (только для админа) | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_franchise_menu` |
| 1932 | `async show_admin_franchise_menu(message, edit_message)` | Отображает меню настроек франшизы (только для админа) | `src/shop_bot/bot/admin_handlers.py::admin_franchise_menu_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_franchise_min_withdraw_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_franchise_percent_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_franchise_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1957 | `async admin_franchise_menu_entry(callback, state)` | Точка входа в меню франшизы - ТОЛЬКО ДЛЯ АДМИНА | — |
| 1969 | `async admin_franchise_toggle(callback, state)` | Переключает франшизу ВКЛ/ВЫКЛ - ТОЛЬКО ДЛЯ АДМИНА | — |
| 1996 | `async admin_franchise_set_percent(callback, state)` | Установить процент комиссии франшизы | — |
| 2007 | `async admin_franchise_percent_input(message, state)` | Обработка ввода процента комиссии | — |
| 2028 | `async admin_franchise_set_min_withdraw(callback, state)` | Установить минимум для вывода франшизников | — |
| 2039 | `async admin_franchise_min_withdraw_input(message, state)` | Обработка ввода минимума для вывода | — |
| 2086 | `_resolve_host_from_digest(digest)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_delete`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_rename`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_token`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_url` |
| 2105 | `_safe(s)` | — | `src/shop_bot/bot/admin_handlers.py::_format_host_card`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_delete`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_rename`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_squad2_label`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_squads` |
| 2109 | `_format_host_card(host)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_detail` |
| 2157 | `async show_admin_hosts_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_add_squad_uuid`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_rename_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_token_input` |
| 2170 | `async show_admin_host_detail(message, host_name, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_token_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_url_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_squad_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_ssh_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_sub_input` |
| 2191 | `async show_admin_host_squads(message, host_name, host_digest, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad2_label`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_squad_delete`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_squad_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_squads_open`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2212 | `async admin_hosts_menu(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_hosts_menu')` | — |
| 2222 | `async admin_hosts_add(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_hosts_add')` | — |
| 2237 | `async admin_hosts_add_name(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_add_name)` | — |
| 2254 | `async admin_hosts_add_base_url(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_add_base_url)` | — |
| 2271 | `async admin_hosts_add_api_token(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_add_api_token)` | — |
| 2288 | `async admin_hosts_add_squad_uuid(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_add_squad_uuid)` | — |
| 2342 | `async admin_hosts_open(callback, state)` | Открыть карточку выбранного хоста. | — |
| 2376 | `async admin_hosts_squads_open(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_squads:'))` | — |
| 2394 | `async admin_hosts_squad_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_squad_toggle:'))` | — |
| 2426 | `async admin_hosts_squad_delete(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_squad_delete:'))` | — |
| 2451 | `async admin_hosts_squad_add(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_squad_add:'))` | — |
| 2470 | `async admin_hosts_squad_add_class(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_squad_add_class:'))` | — |
| 2494 | `async admin_hosts_squad2_uuid(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_add_squad2_uuid)` | — |
| 2513 | `async admin_hosts_squad2_label(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_add_squad2_label)` | — |
| 2561 | `async admin_hosts_delete(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_delete:'))` | — |
| 2580 | `async admin_hosts_delete_confirm(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_delete_confirm:'))` | — |
| 2601 | `async admin_hosts_rename(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_rename:'))` | — |
| 2622 | `async admin_hosts_toggle_class(callback, state)` | Переключение класса ноды: ♾ Unlimited <-> 💰 Premium (LTE). | — |
| 2663 | `async admin_hosts_rename_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_rename)` | — |
| 2688 | `async admin_hosts_set_url(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_set_url:'))` | — |
| 2708 | `async admin_hosts_set_url_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_set_url)` | — |
| 2732 | `async admin_hosts_set_sub(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_set_sub:'))` | — |
| 2753 | `async admin_hosts_set_sub_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_set_subscription)` | — |
| 2774 | `async admin_hosts_set_rmw_url(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_set_rmw_url:'))` | — |
| 2794 | `async admin_hosts_set_rmw_url_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_set_rmw_url)` | — |
| 2818 | `async admin_hosts_set_rmw_token(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_set_rmw_token:'))` | — |
| 2839 | `async admin_hosts_set_rmw_token_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_set_rmw_token)` | — |
| 2860 | `async admin_hosts_set_squad(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_set_squad:'))` | — |
| 2880 | `async admin_hosts_set_squad_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_set_squad)` | — |
| 2901 | `async admin_hosts_set_ssh(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_set_ssh:'))` | — |
| 2925 | `async admin_hosts_set_ssh_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminHosts.waiting_set_ssh)` | — |
| 2963 | `_n(v)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_set_ssh_input`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2986 | `async admin_hosts_to_plans(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_hosts_to_plans:'))` | — |
| 3018 | `_get_trial_enabled()` | — | `src/shop_bot/bot/admin_handlers.py::admin_trial_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_trial_menu` |
| 3022 | `_format_trial_value_gb(raw)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_trial_menu` |
| 3035 | `_format_trial_value_int(raw)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_trial_menu` |
| 3044 | `_get_trial_days()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_trial_menu` |
| 3058 | `async show_admin_trial_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_trial_days_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_trial_devices_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_trial_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_trial_select_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_trial_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_trial_traffic_input` |
| 3099 | `async admin_trial_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_trial')` | — |
| 3110 | `async admin_trial_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_trial_toggle')` | — |
| 3122 | `async admin_trial_set_days(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_trial_set_days')` | — |
| 3136 | `async admin_trial_set_traffic(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_trial_set_traffic')` | — |
| 3151 | `async admin_trial_set_devices(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_trial_set_devices')` | — |
| 3166 | `async admin_trial_set_host(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_trial_set_host')` | — |
| 3182 | `async admin_trial_select_host(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_trial_select_host_'))` | — |
| 3194 | `async admin_trial_days_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminTrial.waiting_for_days)` | — |
| 3213 | `async admin_trial_traffic_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminTrial.waiting_for_traffic)` | — |
| 3236 | `async admin_trial_devices_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminTrial.waiting_for_devices)` | — |
| 3261 | `_get_dual_limit_interval()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_lte_settings_menu` |
| 3269 | `async show_admin_lte_settings_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_lte_set_interval_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_lte_settings_entry`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3290 | `async admin_lte_settings_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_lte_settings_menu')` | — |
| 3301 | `async admin_lte_set_interval_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_lte_set_interval')` | — |
| 3316 | `async admin_lte_set_interval_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminLteSettings.waiting_for_interval)` | — |
| 3342 | `_get_inactive_reminder_enabled()` | — | `src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_notifications_menu` |
| 3345 | `_get_inactive_reminder_interval_hours()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_notifications_menu` |
| 3357 | `_get_inactive_reminder_support_url()` | — | `src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_set_support_url`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_notifications_menu` |
| 3361 | `async show_admin_notifications_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_interval_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_support_url_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_notifications_entry`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3394 | `async admin_notifications_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_notifications_menu')` | — |
| 3405 | `async admin_inactive_reminder_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_inactive_reminder_toggle')` | — |
| 3417 | `async admin_inactive_reminder_set_interval(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_inactive_reminder_set_interval')` | — |
| 3434 | `async admin_inactive_reminder_interval_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminNotifications.waiting_for_interval)` | — |
| 3455 | `async admin_inactive_reminder_set_support_url(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_inactive_reminder_set_support_url')` | — |
| 3473 | `async admin_inactive_reminder_support_url_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminNotifications.waiting_for_support_url)` | — |
| 3536 | `_format_plan_duration(plan)` | Человекочитаемый срок тарифа. | `src/shop_bot/bot/admin_handlers.py::_format_plan_detail`<br>`src/shop_bot/bot/admin_handlers.py::_format_plans_for_host`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3550 | `_format_traffic_gb(plan)` | — | `src/shop_bot/bot/admin_handlers.py::_format_plan_detail`<br>`src/shop_bot/bot/admin_handlers.py::_format_plans_for_host`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3566 | `_format_devices(plan)` | — | `src/shop_bot/bot/admin_handlers.py::_format_plan_detail`<br>`src/shop_bot/bot/admin_handlers.py::_format_plans_for_host`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3578 | `_plan_show_name_enabled(plan)` | — | `src/shop_bot/bot/admin_handlers.py::_format_plan_detail`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3586 | `_format_plans_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_to_plans`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_back_to_host_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_pick_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_price_received`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3611 | `async admin_plans_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_plans')` | — |
| 3627 | `async admin_plans_back_to_admin(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.picking_host, F.data == 'admin_plans_back_to_users')` | — |
| 3637 | `async admin_plans_pick_host(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.picking_host, F.data.startswith('admin_plans_pick_host_'))` | — |
| 3652 | `_format_plan_detail(plan, host_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_plan_edit_days_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_devices_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_lte_limit_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_main_reset_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_months_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_name_received` |
| 3688 | `async admin_plans_open_plan(callback, state)` | Открыть конкретный тариф из списка тарифов хоста. | — |
| 3722 | `_format_traffic_package_detail(pkg)` | — | `src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_size_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 3746 | `async admin_plan_packages_menu(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data.startswith('admin_plan_packages_'))` | — |
| 3779 | `async admin_lte_packages_menu(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data.startswith('admin_lte_packages_'))` | — |
| 3814 | `async admin_plan_edit_lte_limit_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_lte_limit')` | — |
| 3827 | `async admin_plan_edit_lte_limit_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_lte_limit)` | — |
| 3873 | `async admin_plan_edit_main_reset_price_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_main_reset_price')` | — |
| 3887 | `async admin_plan_edit_main_reset_price_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_main_reset_price)` | — |
| 3932 | `async admin_pkg_add_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.packages_menu, F.data.startswith('admin_pkg_add_'))` | — |
| 3960 | `async admin_pkg_size_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_package_size)` | — |
| 3977 | `async admin_pkg_price_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_package_price)` | — |
| 4006 | `async admin_pkg_open(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.packages_menu, F.data.startswith('admin_pkg_open_'))` | — |
| 4031 | `async admin_pkg_edit_size_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.package_menu, F.data.startswith('admin_pkg_edit_size_'))` | — |
| 4044 | `async admin_pkg_edit_size_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_package_size)` | — |
| 4070 | `async admin_pkg_edit_price_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.package_menu, F.data.startswith('admin_pkg_edit_price_'))` | — |
| 4083 | `async admin_pkg_edit_price_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_package_price)` | — |
| 4109 | `async admin_pkg_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.package_menu, F.data.startswith('admin_pkg_toggle_'))` | — |
| 4135 | `async admin_pkg_delete(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.package_menu, F.data.startswith('admin_pkg_delete_'))` | — |
| 4158 | `async admin_plan_edit_name(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_name')` | — |
| 4172 | `async admin_plan_edit_months(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_months')` | — |
| 4187 | `async admin_plan_edit_price(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_price')` | — |
| 4202 | `async admin_plan_edit_duration(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_duration')` | — |
| 4216 | `async admin_plan_duration_months(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.edit_duration_type, F.data == 'admin_plan_duration_months')` | — |
| 4227 | `async admin_plan_duration_days(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.edit_duration_type, F.data == 'admin_plan_duration_days')` | — |
| 4238 | `async admin_plan_edit_traffic(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_traffic')` | — |
| 4252 | `async admin_plan_edit_devices(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_edit_devices')` | — |
| 4266 | `async admin_plan_toggle_active(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_toggle_active')` | — |
| 4295 | `async admin_plan_toggle_show_name(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_toggle_show_name')` | — |
| 4331 | `async admin_plan_delete_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.plan_menu, F.data == 'admin_plan_delete')` | — |
| 4345 | `async admin_plan_delete_cancel(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.confirm_delete, F.data == 'admin_plan_delete_cancel')` | — |
| 4351 | `async admin_plan_delete_confirm(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.confirm_delete, F.data == 'admin_plan_delete_confirm')` | — |
| 4384 | `async admin_plan_edit_name_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_name)` | — |
| 4412 | `async admin_plan_edit_months_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_months)` | — |
| 4445 | `async admin_plan_edit_price_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_price)` | — |
| 4479 | `async admin_plan_edit_days_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_days)` | — |
| 4519 | `async admin_plan_edit_traffic_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_traffic)` | — |
| 4564 | `async admin_plan_edit_devices_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.edit_devices)` | — |
| 4607 | `async admin_plans_back_to_hosts(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.host_menu, F.data == 'admin_plans_back_to_hosts')` | — |
| 4622 | `async admin_plans_add_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.host_menu, F.data == 'admin_plans_add')` | — |
| 4646 | `async admin_plans_new_duration_months(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.waiting_for_duration_type, F.data == 'admin_plans_duration_months')` | — |
| 4661 | `async admin_plans_new_duration_days(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPlans.waiting_for_duration_type, F.data == 'admin_plans_duration_days')` | — |
| 4675 | `async admin_plans_back_to_host_menu(callback, state)` | HTTP-маршрут: `admin_router.callback_query(StateFilter(AdminPlans), F.data == 'admin_plans_back_to_host_menu')` | — |
| 4701 | `async admin_plans_plan_name_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_plan_name)` | — |
| 4727 | `async admin_plans_months_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_months)` | — |
| 4757 | `async admin_plan_add_days_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_days)` | — |
| 4780 | `async admin_plan_add_traffic_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_traffic)` | — |
| 4807 | `async admin_plan_add_devices_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_devices)` | — |
| 4830 | `async admin_plans_price_received(message, state)` | HTTP-маршрут: `admin_router.message(AdminPlans.waiting_for_price)` | — |
| 4906 | `async admin_promo_menu_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_promo_menu')` | — |
| 4915 | `async admin_promo_create_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_promo_create')` | — |
| 4931 | `async admin_promo_code_auto(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_code, F.data == 'admin_promo_code_auto')` | — |
| 4956 | `async admin_promo_code_custom(callback)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_code, F.data == 'admin_promo_code_custom')` | — |
| 4968 | `async admin_promo_create_code(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_code)` | — |
| 4990 | `async admin_promo_set_discount_type(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_discount_type, F.data.in_({'admin_promo_discount_percent', 'admin_promo_discount_amount'}))` | — |
| 5002 | `async admin_promo_set_discount_value(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_discount_value)` | — |
| 5027 | `async admin_promo_set_total_limit(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_total_limit)` | — |
| 5053 | `async admin_promo_total_limit_buttons(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_total_limit, F.data.startswith('admin_promo_limit_total_'))` | — |
| 5077 | `async admin_promo_user_limit_buttons(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_per_user_limit, F.data.startswith('admin_promo_limit_user_'))` | — |
| 5098 | `async admin_promo_set_per_user_limit(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_per_user_limit)` | — |
| 5121 | `async admin_promo_set_valid_from(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_valid_from)` | — |
| 5147 | `async admin_promo_valid_from_buttons(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_valid_from, F.data.in_({'admin_promo_valid_from_now', 'admin_promo_valid_from_today', 'admin_promo_valid_from_tomorrow', 'admin_promo_valid_from_skip', 'admin_promo_valid_from_custom'}))` | — |
| 5175 | `async admin_promo_set_valid_until(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_valid_until)` | — |
| 5206 | `async admin_promo_valid_until_buttons(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_valid_until, F.data.in_({'admin_promo_valid_until_plus1d', 'admin_promo_valid_until_plus7d', 'admin_promo_valid_until_plus30d', 'admin_promo_valid_until_skip', 'admin_promo_valid_until_custom'}))` | — |
| 5236 | `async admin_promo_description(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_description)` | — |
| 5252 | `async admin_promo_desc_buttons(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_description, F.data.in_({'admin_promo_desc_skip', 'admin_promo_desc_custom'}))` | — |
| 5271 | `async _show_promo_confirm(message_or_callback, state)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_set_plans`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_set_plans_custom`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 5327 | `async admin_promo_set_segment(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_segment, F.data.in_({'admin_promo_segment_none', 'admin_promo_segment_no_sub', 'admin_promo_segment_min_spent'}))` | — |
| 5356 | `async admin_promo_set_segment_value(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_segment_value)` | — |
| 5379 | `async admin_promo_set_plans(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.waiting_for_plans, F.data.in_({'admin_promo_plans_all', 'admin_promo_plans_custom'}))` | — |
| 5394 | `async admin_promo_set_plans_custom(message, state)` | HTTP-маршрут: `admin_router.message(AdminPromoCreate.waiting_for_plans)` | — |
| 5412 | `async admin_promo_confirm(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminPromoCreate.confirming, F.data == 'admin_promo_confirm')` | — |
| 5461 | `async admin_promo_list(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_promo_list')` | — |
| 5481 | `async admin_promo_change_page(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_promo_page_'))` | — |
| 5506 | `async admin_promo_toggle(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_promo_toggle_'))` | — |
| 5536 | `async admin_speedtest_entry(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_speedtest')` | — |
| 5556 | `async admin_speedtest_ssh_targets(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_speedtest_ssh_targets')` | — |
| 5575 | `async admin_speedtest_run(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_speedtest_pick_host_'))` | — |
| 5609 | `fmt_part(title, d)` | — | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_run`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 5663 | `async admin_speedtest_run_target_hashed(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('stt:'))` | — |
| 5734 | `async admin_speedtest_run_target(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_speedtest_pick_target_'))` | — |
| 5805 | `async admin_speedtest_back(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_speedtest_back_to_users')` | — |
| 5814 | `async admin_speedtest_run_all(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_speedtest_run_all')` | — |
| 5859 | `async admin_speedtest_run_all_targets(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_speedtest_run_all_targets')` | — |
| 5909 | `async admin_backup_db(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_backup_db')` | — |
| 5944 | `async admin_restore_db_prompt(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_restore_db')` | — |
| 5964 | `async admin_restore_db_receive(message, state)` | HTTP-маршрут: `admin_router.message(AdminRestoreDB.waiting_file)` | — |
| 5992 | `async admin_speedtest_autoinstall(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_speedtest_autoinstall_'))` | — |
| 6017 | `async admin_speedtest_autoinstall_target(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_speedtest_autoinstall_target_'))` | — |
| 6049 | `async admin_speedtest_autoinstall_target_hashed(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('stti:'))` | — |
| 6085 | `async admin_users_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_users'))` | — |
| 6117 | `async admin_users_search_process(message, state)` | HTTP-маршрут: `admin_router.message(AdminUserSearch.waiting_for_query)` | — |
| 6205 | `async admin_view_user_handler(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_view_user_'))` | — |
| 6251 | `async admin_ban_user(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_ban_user_'))` | — |
| 6332 | `async admin_admins_menu_entry(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_admins_menu')` | — |
| 6343 | `async admin_view_admins(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_view_admins')` | — |
| 6381 | `async admin_unban_user(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_unban_user_'))` | — |
| 6444 | `async admin_delete_user(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_delete_user_'))` | — |
| 6467 | `async admin_user_keys(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_user_keys_'))` | — |
| 6494 | `async admin_user_referrals(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_user_referrals_'))` | — |
| 6542 | `async admin_search_user_keys_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_search_user_keys_'))` | — |
| 6565 | `async admin_search_user_keys_input_handler(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter('admin_search_user_keys_state'))` | — |
| 6606 | `async admin_search_keys_page_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_search_keys_page_'))` | — |
| 6634 | `async admin_search_all_keys_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_search_all_keys')` | — |
| 6650 | `async admin_search_all_keys_input_handler(message, state)` | HTTP-маршрут: `admin_router.message(StateFilter('admin_search_all_keys_state'))` | — |
| 6682 | `async admin_cancel_search_keys_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_cancel_search_keys')` | — |
| 6696 | `async admin_edit_key(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_edit_key_'))` | — |
| 6733 | `async admin_key_delete_prompt(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.regexp('^admin_key_delete_\\d+$'))` | — |
| 6767 | `async admin_key_extend_prompt(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_key_extend_'))` | — |
| 6786 | `async admin_key_extend_process(message, state)` | HTTP-маршрут: `admin_router.message(AdminExtendSingleKey.waiting_days)` | — |
| 6850 | `async admin_add_admin_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_add_admin')` | — |
| 6863 | `async admin_add_admin_process(message, state)` | HTTP-маршрут: `admin_router.message(AdminAddAdmin.waiting_for_input)` | — |
| 6928 | `async admin_remove_admin_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_remove_admin')` | — |
| 6941 | `async admin_remove_admin_process(message, state)` | HTTP-маршрут: `admin_router.message(AdminRemoveAdmin.waiting_for_input)` | — |
| 7013 | `async admin_key_delete_cancel(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_key_delete_cancel_'))` | — |
| 7051 | `async admin_key_delete_confirm(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_key_delete_confirm_'))` | — |
| 7124 | `async admin_key_edit_email_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_key_edit_email_'))` | — |
| 7142 | `async admin_key_edit_email_commit(message, state)` | HTTP-маршрут: `admin_router.message(AdminEditKeyEmail.waiting_for_email)` | — |
| 7167 | `async admin_gift_key_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_gift_key')` | — |
| 7182 | `async admin_gift_key_for_user(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_gift_key_'))` | — |
| 7202 | `async admin_gift_pick_user_page(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminGiftKey.picking_user, F.data.startswith('admin_gift_pick_user_page_'))` | — |
| 7218 | `async admin_gift_pick_user(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminGiftKey.picking_user, F.data.startswith('admin_gift_pick_user_'))` | — |
| 7237 | `async admin_gift_back_to_users(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminGiftKey.picking_host, F.data == 'admin_gift_back_to_users')` | — |
| 7250 | `async admin_gift_pick_host(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminGiftKey.picking_host, F.data.startswith('admin_gift_pick_host_'))` | — |
| 7264 | `async admin_gift_back_to_hosts(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminGiftKey.picking_days, F.data == 'admin_gift_back_to_hosts')` | — |
| 7278 | `async admin_gift_pick_days(message, state)` | HTTP-маршрут: `admin_router.message(AdminGiftKey.picking_days)` | — |
| 7354 | `async admin_add_balance_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_add_balance')` | — |
| 7366 | `async admin_add_balance_user(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_add_balance_'))` | — |
| 7385 | `async admin_add_balance_pick_user_page(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_add_balance_pick_user_page_'))` | — |
| 7402 | `async admin_add_balance_pick_user(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_add_balance_pick_user_'))` | — |
| 7420 | `async handle_main_amount(message, state)` | HTTP-маршрут: `admin_router.message(AdminMainRefill.waiting_for_amount)` | — |
| 7450 | `async admin_key_back(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_key_back_'))` | — |
| 7489 | `async admin_noop(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'noop')` | — |
| 7493 | `async admin_cancel_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_cancel')` | — |
| 7504 | `async admin_deduct_balance_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_deduct_balance')` | — |
| 7517 | `async admin_deduct_balance_user(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_deduct_balance_'))` | — |
| 7536 | `async admin_deduct_balance_pick_user_page(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_deduct_balance_pick_user_page_'))` | — |
| 7553 | `async admin_deduct_balance_pick_user(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('admin_deduct_balance_pick_user_'))` | — |
| 7571 | `async handle_deduct_amount(message, state)` | HTTP-маршрут: `admin_router.message(AdminMainDeduct.waiting_for_amount)` | — |
| 7608 | `async admin_host_keys_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_host_keys')` | — |
| 7622 | `async admin_host_keys_pick_host(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminHostKeys.picking_host, F.data.startswith('admin_hostkeys_pick_host_'))` | — |
| 7640 | `async admin_hostkeys_page(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminHostKeys.picking_host, F.data.startswith('admin_hostkeys_page_'))` | — |
| 7666 | `async admin_hostkeys_back_to_hosts(callback, state)` | HTTP-маршрут: `admin_router.callback_query(AdminHostKeys.picking_host, F.data == 'admin_hostkeys_back_to_hosts')` | — |
| 7683 | `async admin_hostkeys_back_to_users(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_hostkeys_back_to_users')` | — |
| 7695 | `async admin_delete_key_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_delete_key')` | — |
| 7707 | `async admin_delete_key_process(message, state)` | HTTP-маршрут: `admin_router.message(AdminQuickDeleteKey.waiting_for_identifier)` | — |
| 7736 | `async admin_extend_key_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_extend_key')` | — |
| 7748 | `async admin_extend_key_process(message, state)` | HTTP-маршрут: `admin_router.message(AdminExtendKey.waiting_for_pair)` | — |
| 7799 | `async start_broadcast_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'start_broadcast')` | — |
| 7813 | `async broadcast_message_received_handler(message, state)` | HTTP-маршрут: `admin_router.message(Broadcast.waiting_for_message)` | — |
| 7817 | `_msg_json_default(o)` | — | — |
| 7826 | `_detect_parse_mode(text)` | Auto-detect parse mode: HTML tags → HTML, Markdown links/bold/etc → MarkdownV2. | `src/shop_bot/bot/admin_handlers.py::broadcast_message_received_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 7870 | `async broadcast_parse_mode_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_parse_mode, F.data.in_({'broadcast_pm_none', 'broadcast_pm_html', 'broadcast_pm_md2'}))` | — |
| 7883 | `async add_button_choose_type(callback, state)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_button_option, F.data == 'broadcast_add_button')` | — |
| 7892 | `async add_button_prompt_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_button_type, F.data == 'broadcast_btn_type_url')` | — |
| 7901 | `async add_functional_button_start(callback, state)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_button_type, F.data == 'broadcast_btn_type_action')` | — |
| 7910 | `async functional_button_selected(callback, state)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_action_select, F.data.startswith('broadcast_action:'))` | — |
| 7919 | `async button_text_received_handler(message, state)` | HTTP-маршрут: `admin_router.message(Broadcast.waiting_for_button_text)` | — |
| 7928 | `async button_url_received_handler(message, state, bot)` | HTTP-маршрут: `admin_router.message(Broadcast.waiting_for_button_url)` | — |
| 7939 | `async skip_button_handler(callback, state, bot)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_button_option, F.data == 'broadcast_skip_button')` | — |
| 7944 | `_escape_md2(text)` | Escape MarkdownV2 special chars in plain-text parts, leaving inline entities intact. | `src/shop_bot/bot/admin_handlers.py::_send_broadcast_to`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 7958 | `_esc(s)` | — | `src/shop_bot/bot/admin_handlers.py::_escape_md2`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 7969 | `async _send_broadcast_to(bot, chat_id, msg, keyboard, parse_mode)` | Send broadcast, using specific send methods for media so reply_markup is applied correctly. | `src/shop_bot/bot/admin_handlers.py::confirm_broadcast_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_broadcast_preview` |
| 8006 | `async show_broadcast_preview(message, state, bot)` | — | `src/shop_bot/bot/admin_handlers.py::button_url_received_handler`<br>`src/shop_bot/bot/admin_handlers.py::functional_button_selected`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::skip_button_handler` |
| 8039 | `async confirm_broadcast_handler(callback, state, bot)` | HTTP-маршрут: `admin_router.callback_query(Broadcast.waiting_for_confirmation, F.data == 'confirm_broadcast')` | — |
| 8109 | `async cancel_broadcast_handler(callback, state)` | HTTP-маршрут: `admin_router.callback_query(StateFilter(Broadcast), F.data == 'cancel_broadcast')` | — |
| 8116 | `async approve_withdraw_handler(message)` | HTTP-маршрут: `admin_router.message(Command(commands=['approve_withdraw']))` | — |
| 8137 | `async decline_withdraw_handler(message)` | HTTP-маршрут: `admin_router.message(Command(commands=['decline_withdraw']))` | — |
| 8152 | `async admin_monitor_menu(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_monitor')` | — |
| 8186 | `async admin_monitor_local(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_monitor_local')` | — |
| 8285 | `get_status_emoji(value, warning, critical)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8293 | `format_bytes(bytes_val)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8302 | `format_uptime(seconds)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8357 | `async admin_monitor_host(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('rmh:'))` | — |
| 8400 | `get_status_emoji(value, warning, critical)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8410 | `format_uptime(seconds)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8423 | `format_loadavg(loads)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8465 | `async admin_monitor_target(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data.startswith('rmt:'))` | — |
| 8530 | `get_status_emoji(value, warning, critical)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8540 | `format_uptime(seconds)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8553 | `format_loadavg(loads)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8595 | `async admin_monitor_detailed(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_monitor_detailed')` | — |
| 8616 | `format_bytes(bytes_val)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8625 | `format_uptime(seconds)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8730 | `async admin_captcha_settings_handler(callback)` | Показать страницу настроек капчи. | `src/shop_bot/bot/admin_handlers.py::admin_captcha_toggle_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_captcha_type_set_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8767 | `async admin_captcha_toggle_handler(callback)` | Включить/отключить капчу. | — |
| 8781 | `async admin_captcha_type_handler(callback)` | Выбрать тип капчи. | — |
| 8806 | `async admin_captcha_type_set_handler(callback)` | Установить тип капчи. | — |
| 8820 | `async admin_captcha_attempts_handler(callback, state)` | Установить максимальное количество попыток. | — |
| 8834 | `async admin_captcha_attempts_input_handler(message, state)` | Обработать ввод количества попыток. | — |
| 8853 | `async admin_captcha_timeout_handler(callback, state)` | Установить timeout капчи. | — |
| 8867 | `async admin_captcha_timeout_input_handler(message, state)` | Обработать ввод timeout. | — |
| 8886 | `async admin_captcha_message_handler(callback, state)` | Установить кастомное сообщение к капче. | — |
| 8900 | `async admin_captcha_message_input_handler(message, state)` | Обработать ввод сообщения. | — |
| 8922 | `async show_admin_auto_renew_menu(message, edit_message)` | — | `src/shop_bot/bot/admin_handlers.py::admin_auto_renew_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_hours_input`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 8947 | `async admin_auto_renew_entry(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_auto_renew')` | — |
| 8957 | `async admin_auto_renew_toggle(callback)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_auto_renew_toggle')` | — |
| 8969 | `async admin_auto_renew_set_hours(callback, state)` | HTTP-маршрут: `admin_router.callback_query(F.data == 'admin_auto_renew_set_hours')` | — |
| 8980 | `async admin_auto_renew_hours_input(message, state)` | HTTP-маршрут: `admin_router.message(AdminAutoRenew.waiting_for_hours)` | — |

## src/shop_bot/bot/handlers.py

Пользовательские хендлеры магазина: онбординг, покупка, ключи, платежи, рефералка, подарки, франшиза.

**Классы:** `KeyPurchase`, `Captcha`, `Onboarding`, `PaymentProcess`, `TopUpProcess`, `TrafficGbTopUp`, `LteGbTopUp`, `MainPoolReset`, `SupportDialog`, `FranchiseStates`, `KeyManagement`, `ReferralWithdraw`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 122 | `_is_true(value)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_get_inactive_reminder_enabled`<br>`src/shop_bot/bot/admin_handlers.py::_get_payments_status_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::_payment_detail_text`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle` |
| 125 | `_get_payment_methods()` | Собирает доступные способы оплаты из актуальных настроек (без перезапуска бота). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_payment_options` |
| 190 | `_classify_key_creation_error(exc)` | — | `src/shop_bot/bot/handlers.py::_handle_key_creation_failure` |
| 216 | `_format_key_action_label(action, price, key_id)` | — | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation` |
| 231 | `_log_key_creation_error(user_id, action_label, code, detail)` | — | `src/shop_bot/bot/handlers.py::_handle_key_creation_failure` |
| 243 | `async _notify_admins_key_creation_error(bot, user_id, code, description, action_label)` | — | `src/shop_bot/bot/handlers.py::_handle_key_creation_failure` |
| 271 | `async _notify_user_key_creation_error(bot, user_id, code, refund, factory_bot_id)` | — | `src/shop_bot/bot/handlers.py::_handle_key_creation_failure` |
| 311 | `async _handle_key_creation_failure(bot, user_id, action_label, exc, refund, factory_bot_id)` | — | `src/shop_bot/bot/handlers.py::_abort_key_fulfillment`<br>`src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation` |
| 332 | `async _abort_topup_fulfillment(bot, payment_id, user_id, price, payment_method, action_label, reason)` | Компенсирующая транзакция при сбое применения оплаченной докупки трафика. | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 416 | `async _notify_admins_topup_desync(bot, user_id, action_label, payment_id, detail)` | Докупка применена на VPN-сервере, но не сохранилась в БД бота. | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 456 | `async _abort_key_fulfillment(bot, payment_id, user_id, price, payment_method, action_label, exc, factory_bot_id, processing_message, fail_text)` | Компенсирующая транзакция при сбое выдачи ключа после оплаты. | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 516 | `async _safe_edit_or_answer(message, text, **kwargs)` | Заменить `message.edit_text(...)` там, где предыдущее сообщение может | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/bot/handlers.py::show_main_menu` |
| 532 | `_format_duration_label(months, duration_days)` | — | `src/shop_bot/bot/handlers.py::create_cryptobot_invoice_handler`<br>`src/shop_bot/bot/handlers.py::create_stars_invoice_handler`<br>`src/shop_bot/bot/handlers.py::create_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::notify_admin_of_purchase`<br>`src/shop_bot/bot/handlers.py::pay_yoomoney_handler` |
| 546 | `_compute_days_to_add(months, duration_days)` | — | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::_tariff_label_from_origin`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment` |
| 560 | `_tariff_label_from_origin(is_trial, months, duration_days)` | Human label for subscription page tariff line. | `src/shop_bot/bot/handlers.py::_build_key_origin_meta` |
| 573 | `_build_key_origin_meta(source, plan_id, plan_name, months, duration_days, is_trial, note)` | Store key origin info inside vpn_keys.description as JSON. | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation` |
| 603 | `async grant_referrer_day_bonus_for_trial(referred_user_id, bot)` | Начислить рефереру +1 день только в момент активации триала рефералом. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation` |
| 649 | `_parse_exp_dt(v)` | — | `src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial` |
| 745 | `_webapp_public_base()` | Публичный базовый URL Mini App, если webapp включён и задан домен. | `src/shop_bot/bot/handlers.py::_build_referral_links` |
| 762 | `_build_gift_links(gift_code)` | Построить обе ссылки активации подарка: в мини-приложении (webapp) и в Telegram. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::send_gift_link_handler`<br>`src/shop_bot/bot/handlers.py::show_gift_handler` |
| 774 | `_build_referral_links(user_id, bot_username)` | Построить реферальные ссылки: (webapp_link, telegram_link). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 791 | `_referral_share_text()` | Текст для t.me/share из настроек (Контент → referral_share_text). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 797 | `_gift_share_text()` | Текст для t.me/share при шаринге подарка (Контент → gift_share_text). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::send_gift_link_handler` |
| 803 | `_telegram_share_url(url, text)` | Собрать https://t.me/share/url?... с пробелами как %20 (не +). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::referral_program_handler`<br>`src/shop_bot/bot/handlers.py::send_gift_link_handler` |
| 815 | `async _activate_gift_directly(message, bot, user_id, gift_code, is_new_user)` | Активировать подарок для пользователя. | `src/shop_bot/bot/handlers.py::activate_own_gift_handler`<br>`src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 906 | `async _create_heleket_payment_request(user_id, price, months, host_name, state_data)` | Создание инвойса в Heleket и возврат payment URL. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_heleket_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_heleket_like`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_heleket_handler` |
| 1018 | `async create_cryptobot_api_invoice(amount, payload_str)` | Упрощённая обёртка для создания инвойса в Crypto Pay (CryptoBot), используемая | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 1068 | `async _create_cryptobot_invoice(user_id, price_rub, months, host_name, state_data)` | Создание инвойса в Crypto Pay (CryptoBot) и возврат bot_invoice_url. | `src/shop_bot/bot/handlers.py::create_cryptobot_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_cryptobot_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_cryptobot`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_cryptobot_handler` |
| 1332 | `is_valid_email(email)` | — | `src/shop_bot/bot/handlers.py::create_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_email_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_yookassa` |
| 1336 | `async show_captcha(message, state, user_id)` | Показывает капчу пользователю. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 1378 | `async show_main_menu(message, edit_message)` | — | `src/shop_bot/bot/handlers.py::_activate_gift_directly`<br>`src/shop_bot/bot/handlers.py::back_to_main_menu_handler`<br>`src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::franchise_cancel`<br>`src/shop_bot/bot/handlers.py::franchise_receive_token` |
| 1508 | `async process_successful_onboarding(callback, state)` | Завершает онбординг: ставит флаг согласия и открывает главное меню. | `src/shop_bot/bot/handlers.py::check_subscription_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 1531 | `registration_required(f)` | — | — |
| 1533 | `async decorated_function(event, *args, **kwargs)` | — | — |
| 1546 | `async _maybe_pay_referral_start_bonus(bot, user_id, referrer_id)` | Выплатить рефереру фиксированный бонус за регистрацию приглашённого пользователя | `src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 1620 | `get_user_router()` | — | `src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot` |
| 1624 | `async start_handler(message, state, bot, command)` | HTTP-маршрут: `user_router.message(CommandStart())` | — |
| 1781 | `async check_subscription_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(Onboarding.waiting_for_subscription_and_agreement, F.data == 'check_subscription_and_agree')` | — |
| 1809 | `async onboarding_fallback_handler(message)` | HTTP-маршрут: `user_router.message(Onboarding.waiting_for_subscription_and_agreement)` | — |
| 1817 | `async captcha_answer_handler(message, state)` | Обработчик текстового ответа на математическую капчу. | — |
| 1903 | `async captcha_button_answer_handler(callback, state)` | Обработчик ответа на капчу с выбором кнопки. | — |
| 2001 | `async cancel_captcha_handler(callback, state)` | Отмена капчи. | — |
| 2009 | `async main_menu_handler(message)` | HTTP-маршрут: `user_router.message(F.text == '🏠 Главное меню')` | — |
| 2014 | `async back_to_main_menu_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'back_to_main_menu')` | `src/shop_bot/bot/handlers.py::back_to_plans_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 2020 | `async open_main_menu_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'open_main_menu')` | — |
| 2026 | `async show_main_menu_cb(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_main_menu')` | — |
| 2032 | `async profile_handler_callback(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_profile')` | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::toggle_auto_renew_profile`<br>`src/shop_bot/bot/handlers.py::toggle_expiry_notifications_handler` |
| 2106 | `async toggle_expiry_notifications_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'toggle_expiry_notifications')` | — |
| 2121 | `async show_inactive_gifts_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_inactive_gifts')` | — |
| 2146 | `async gifts_page_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('gifts_page_'))` | — |
| 2177 | `async show_gift_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('show_gift_'))` | — |
| 2267 | `async send_gift_link_handler(callback)` | Отправка ссылки подарка пользователю. | — |
| 2333 | `async activate_own_gift_handler(callback)` | Активировать собственный неактивированный подарок себе (аналог webapp-кнопки 'Активировать себе'). | — |
| 2368 | `_resolve_plan_for_traffic_topup(key_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::traffic_gb_pick_handler`<br>`src/shop_bot/bot/handlers.py::traffic_gb_start_handler` |
| 2382 | `async traffic_gb_start_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('traffic_gb_start_'))` | — |
| 2415 | `async traffic_gb_pick_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('traffic_gb_pick_'))` | — |
| 2460 | `_traffic_gb_metadata(data, user_id, payment_method, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_balance_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_referral_balance_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_stars_handler` |
| 2474 | `async trafficgb_pay_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_balance')` | — |
| 2494 | `async trafficgb_pay_referral_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_referral_balance')` | — |
| 2514 | `async trafficgb_pay_yookassa_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_yookassa')` | — |
| 2569 | `async trafficgb_pay_platega_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_platega')` | — |
| 2604 | `async trafficgb_pay_rollypay_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_rollypay')` | — |
| 2642 | `async trafficgb_pay_heleket_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_heleket')` | — |
| 2681 | `async trafficgb_pay_cryptobot_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_cryptobot')` | — |
| 2721 | `async trafficgb_pay_yoomoney_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_yoomoney')` | — |
| 2752 | `async trafficgb_pay_stars_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TrafficGbTopUp.waiting_for_method, F.data == 'trafficgb_pay_stars')` | — |
| 2791 | `_resolve_plan_for_lte_topup(key_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::lte_gb_pick_handler`<br>`src/shop_bot/bot/handlers.py::lte_gb_start_handler` |
| 2805 | `async lte_gb_start_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('lte_gb_start_'))` | — |
| 2840 | `async lte_gb_pick_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('lte_gb_pick_'))` | — |
| 2886 | `_lte_gb_metadata(data, user_id, payment_method, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_balance_handler`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_referral_balance_handler`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_stars_handler` |
| 2900 | `async ltegb_pay_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_balance')` | — |
| 2920 | `async ltegb_pay_referral_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_referral_balance')` | — |
| 2940 | `async ltegb_pay_yookassa_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_yookassa')` | — |
| 2995 | `async ltegb_pay_platega_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_platega')` | — |
| 3030 | `async ltegb_pay_rollypay_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_rollypay')` | — |
| 3068 | `async ltegb_pay_heleket_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_heleket')` | — |
| 3107 | `async ltegb_pay_cryptobot_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_cryptobot')` | — |
| 3147 | `async ltegb_pay_yoomoney_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_yoomoney')` | — |
| 3178 | `async ltegb_pay_stars_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(LteGbTopUp.waiting_for_method, F.data == 'ltegb_pay_stars')` | — |
| 3217 | `_resolve_key_for_main_reset(key_id, user_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::main_reset_start_handler` |
| 3225 | `async main_reset_start_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('main_reset_start_'))` | — |
| 3294 | `_main_reset_metadata(data, user_id, payment_method, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::mainreset_pay_balance_handler`<br>`src/shop_bot/bot/handlers.py::mainreset_pay_referral_balance_handler`<br>`src/shop_bot/bot/handlers.py::mainreset_pay_yookassa_handler` |
| 3306 | `async mainreset_pay_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(MainPoolReset.waiting_for_method, F.data == 'mainreset_pay_balance')` | — |
| 3326 | `async mainreset_pay_referral_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(MainPoolReset.waiting_for_method, F.data == 'mainreset_pay_referral_balance')` | — |
| 3346 | `async mainreset_pay_yookassa_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(MainPoolReset.waiting_for_method, F.data == 'mainreset_pay_yookassa')` | — |
| 3401 | `async topup_start_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'top_up_start')` | — |
| 3410 | `async topup_amount_input(message, state)` | HTTP-маршрут: `user_router.message(TopUpProcess.waiting_for_amount)` | — |
| 3435 | `async topup_pay_yookassa(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_yookassa')` | — |
| 3520 | `async create_stars_invoice_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_stars')` | — |
| 3612 | `async payment_stars_back_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'payment_stars_back')` | — |
| 3672 | `async topup_stars_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_stars')` | — |
| 3722 | `async pre_checkout_handler(pre_checkout_q)` | HTTP-маршрут: `user_router.pre_checkout_query()` | — |
| 3745 | `async stars_success_handler(message, bot, state)` | HTTP-маршрут: `user_router.message(F.successful_payment)` | — |
| 3808 | `_rollypay_is_enabled()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_rollypay`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_rollypay_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 3814 | `async _create_rollypay_payment_link(amount_rub, payment_id, description, customer_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_rollypay`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_rollypay_handler` |
| 3831 | `_platega_is_enabled()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_platega`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_platega_handler` |
| 3834 | `_platega_get_base_url()` | — | `src/shop_bot/bot/handlers.py::_platega_request`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 3837 | `_platega_get_method_code()` | — | `src/shop_bot/bot/handlers.py::_create_platega_payment_link`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 3851 | `async _platega_request(method, endpoint, json_data)` | — | `src/shop_bot/bot/handlers.py::_create_platega_payment_link`<br>`src/shop_bot/bot/handlers.py::_get_platega_transaction`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 3877 | `async _create_platega_payment_link(amount_rub, payment_id, description)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_platega`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_platega_handler` |
| 3893 | `async _get_platega_transaction(transaction_id)` | — | `src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 3898 | `_build_yoomoney_link(receiver, amount_rub, label)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::pay_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::topup_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_yoomoney_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 3915 | `async pay_yoomoney_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_yoomoney')` | — |
| 3975 | `async topup_yoomoney_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_yoomoney')` | — |
| 4026 | `async check_platega_payment_handler(callback, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('check_platega:'))` | — |
| 4082 | `async check_rollypay_payment_handler(callback, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('check_rollypay:'))` | — |
| 4160 | `async check_yookassa_payment_handler(callback, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('check_yookassa:'))` | — |
| 4253 | `async check_pending_payment_handler(callback, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('check_pending:'))` | — |
| 4340 | `async topup_pay_platega(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_platega')` | — |
| 4385 | `async topup_pay_rollypay(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_rollypay')` | — |
| 4433 | `async topup_pay_heleket_like(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_heleket')` | — |
| 4472 | `async topup_pay_cryptobot(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_cryptobot')` | — |
| 4511 | `async topup_pay_tonconnect(callback, state)` | HTTP-маршрут: `user_router.callback_query(TopUpProcess.waiting_for_topup_method, F.data == 'topup_pay_tonconnect')` | — |
| 4577 | `async referral_program_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_referral_program')` | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_my_balance` |
| 4595 | `_to_float_setting(key, default)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 4603 | `_is_true_setting(key, default)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 4613 | `_fmt_num(x, decimals)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 4688 | `async referral_top_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_referral_top')` | — |
| 4739 | `_ref_is_true(key, default)` | — | `src/shop_bot/bot/handlers.py::_ref_method_enabled`<br>`src/shop_bot/bot/handlers.py::_ref_withdraw_enabled`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 4743 | `_ref_float_setting(key, default)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_program_handler`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_amount`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_choose_method`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_start` |
| 4750 | `_ref_withdraw_enabled()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_delete`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_value`<br>`src/shop_bot/bot/handlers.py::referral_payout_methods`<br>`src/shop_bot/bot/handlers.py::referral_program_handler` |
| 4753 | `_ref_method_enabled(method_type)` | — | `src/shop_bot/bot/handlers.py::_kb_method_types`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add_type`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_start` |
| 4760 | `_ref_sbp_banks()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add_type` |
| 4766 | `_ref_mask(value)` | — | `src/shop_bot/bot/handlers.py::_kb_payout_methods`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_delete`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_value`<br>`src/shop_bot/bot/handlers.py::referral_payout_methods`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_requests` |
| 4774 | `_kb_my_balance(withdraw_enabled, can_withdraw_now)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_transfer_amount`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_amount` |
| 4788 | `async referral_my_balance(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'referral_my_balance')` | — |
| 4807 | `async referral_withdraw_requests(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'referral_withdraw_requests')` | — |
| 4841 | `async referral_transfer_start(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'referral_transfer_start')` | — |
| 4865 | `async referral_transfer_amount(message, state)` | HTTP-маршрут: `user_router.message(ReferralWithdraw.waiting_transfer_amount)` | — |
| 4923 | `_kb_payout_methods(items, withdraw_enabled)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add_type`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_delete`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_value`<br>`src/shop_bot/bot/handlers.py::referral_payout_methods`<br>`src/shop_bot/bot/handlers.py::referral_withdraw_start` |
| 4941 | `async referral_payout_methods(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'referral_payout_methods')` | — |
| 4966 | `_kb_method_types()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add` |
| 4980 | `async referral_payout_method_add(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'referral_payout_method_add')` | — |
| 4992 | `_kb_bank_choice(banks)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::referral_payout_method_add_type` |
| 5002 | `async referral_payout_method_add_type(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('rpm_add_type:'))` | — |
| 5024 | `async referral_payout_method_bank_choice(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('rpm_bank:'), ReferralWithdraw.waiting_method_bank)` | — |
| 5042 | `async referral_payout_method_value(message, state)` | HTTP-маршрут: `user_router.message(ReferralWithdraw.waiting_method_value)` | — |
| 5068 | `async referral_payout_method_delete(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('rpm_delete:'))` | — |
| 5094 | `async referral_withdraw_start(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'referral_withdraw_start')` | — |
| 5139 | `async referral_withdraw_choose_method(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('rwd_method:'), ReferralWithdraw.waiting_withdraw_choose_method)` | — |
| 5165 | `async referral_withdraw_amount(message, state)` | HTTP-маршрут: `user_router.message(ReferralWithdraw.waiting_withdraw_amount)` | — |
| 5220 | `async about_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_about')` | — |
| 5241 | `async user_speedtest_last_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'user_speedtest_last')` | — |
| 5292 | `async about_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'show_help')` | — |
| 5313 | `async support_menu_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'support_menu')` | — |
| 5334 | `async support_external_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'support_external')` | — |
| 5354 | `async support_new_ticket_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'support_new_ticket')` | — |
| 5367 | `async support_subject_received(message, state)` | HTTP-маршрут: `user_router.message(SupportDialog.waiting_for_subject)` | — |
| 5380 | `async support_message_received(message, state, bot)` | HTTP-маршрут: `user_router.message(SupportDialog.waiting_for_message)` | — |
| 5393 | `async support_my_tickets_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'support_my_tickets')` | — |
| 5406 | `async support_view_ticket_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('support_view_'))` | — |
| 5419 | `async support_reply_prompt_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('support_reply_'))` | — |
| 5433 | `async support_reply_received(message, state, bot)` | HTTP-маршрут: `user_router.message(SupportDialog.waiting_for_reply)` | — |
| 5445 | `async forum_thread_message_handler(message, bot)` | HTTP-маршрут: `user_router.message(F.is_topic_message == True)` | — |
| 5493 | `async support_close_ticket_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('support_close_'))` | — |
| 5506 | `async _remnawave_key_exists(key_data)` | Проверяет, существует ли ключ (пользователь) в Remnawave. | `src/shop_bot/bot/handlers.py::_check`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/bot/handlers.py::sync_user_keys_with_remnawave` |
| 5531 | `_extract_connected_devices(user_payload)` | Возвращает количество подключённых устройств (HWID/Devices) по данным Remnawave. | `src/shop_bot/bot/handlers.py::_get_connected_devices_count`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 5543 | `_count_from_value(val)` | — | `src/shop_bot/bot/handlers.py::_extract_connected_devices`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 5657 | `async _get_connected_devices_count(key_data, user_payload)` | Надёжно получить количество подключённых HWID-устройств. | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch` |
| 5686 | `_count_any(val)` | — | `src/shop_bot/bot/handlers.py::_get_connected_devices_count`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 5735 | `async _get_devices_list(key_data, user_payload)` | Получить полный список подключённых HWID-устройств с информацией о каждом. | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process`<br>`src/shop_bot/bot/handlers.py::show_gift_handler` |
| 5789 | `_is_key_without_billing_plan(key_data)` | Триальный или подарочный ключ: биллингового тарифа у него нет. | `src/shop_bot/bot/handlers.py::_resolve_plan_id_for_key`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/webapp/handlers.py::_resolve_plan_id_for_key` |
| 5820 | `_resolve_plan_id_for_key(key_data)` | Определяет plan_id, привязанный к ключу. | `src/shop_bot/bot/handlers.py::_resolve_plan_for_lte_topup`<br>`src/shop_bot/bot/handlers.py::_resolve_plan_for_traffic_topup`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::main_reset_start_handler`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch`<br>`src/shop_bot/bot/handlers.py::show_key_handler` |
| 5858 | `_extract_traffic_used_bytes(payload)` | Извлекает использованный трафик из payload пользователя Remnawave (если поле есть). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler` |
| 5879 | `_format_bytes_gb(num_bytes)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/webapp/handlers.py::_lte_card_state` |
| 5886 | `_get_tariff_info_for_key(key_data, user_payload)` | Подбирает данные тарифа для отображения в 'Мои ключи'. | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch` |
| 6090 | `async sync_user_keys_with_remnawave(user_id)` | Синхронизирует ключи пользователя в БД с фактическими ключами в Remnawave. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::manage_keys_handler` |
| 6111 | `_parse_missing_dt(value)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::sync_user_keys_with_remnawave` |
| 6128 | `async _check(key)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::sync_user_keys_with_remnawave` |
| 6173 | `async manage_keys_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.in_({'manage_keys'}) | F.data.startswith('keys_page_'))` | — |
| 6198 | `async sent_gifts_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.in_({'sent_gifts'}) | F.data.startswith('gift_keys_page_'))` | — |
| 6215 | `async search_my_keys_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'search_my_keys')` | — |
| 6225 | `async search_keys_input_handler(message, state)` | HTTP-маршрут: `user_router.message(StateFilter('search_keys_state'))` | — |
| 6255 | `async search_keys_page_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('search_keys_page_'))` | — |
| 6279 | `async cancel_search_keys_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'cancel_search_keys')` | — |
| 6297 | `async rename_key_start(callback, state)` | Начало процесса переименования ключа. | — |
| 6341 | `async rename_key_process(message, state)` | Обработка ввода нового названия ключа. | — |
| 6434 | `async remove_key_name(callback, state)` | Удаление названия ключа. | — |
| 6509 | `async cancel_rename_key(callback, state)` | Отмена переименования ключа. | — |
| 6576 | `async trial_period_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'get_trial')` | — |
| 6607 | `async trial_host_selection_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('select_host_trial_'))` | — |
| 6612 | `async process_trial_key_creation(message, host_name)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::trial_host_selection_handler`<br>`src/shop_bot/bot/handlers.py::trial_period_handler` |
| 6724 | `async show_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('show_key_'))` | `src/shop_bot/bot/handlers.py::auto_renew_key_toggle`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 6876 | `async auto_renew_key_toggle(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('auto_renew_key_'))` | — |
| 6898 | `async toggle_auto_renew_profile(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'toggle_auto_renew_profile')` | — |
| 6912 | `async switch_server_start(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('switch_server_'))` | — |
| 6943 | `async select_host_for_switch(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('select_host_switch_'))` | — |
| 7079 | `async show_qr_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('show_qr_'))` | — |
| 7101 | `async delete_device_handler(callback)` | Обработчик удаления HWID-устройства с ключа. | — |
| 7203 | `async show_instruction_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('howto_vless_'))` | — |
| 7216 | `async show_instruction_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('howto_vless'))` | — |
| 7228 | `async howto_android_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'howto_android')` | — |
| 7276 | `async howto_android_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('howto_android_'))` | — |
| 7304 | `async howto_ios_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'howto_ios')` | — |
| 7326 | `async howto_ios_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('howto_ios_'))` | — |
| 7354 | `async howto_windows_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'howto_windows')` | — |
| 7406 | `async howto_windows_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('howto_windows_'))` | — |
| 7438 | `async howto_linux_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'howto_linux')` | — |
| 7463 | `async howto_linux_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('howto_linux_'))` | — |
| 7494 | `async gift_new_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'gift_new_key')` | — |
| 7508 | `async buy_new_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data == 'buy_new_key')` | — |
| 7522 | `async select_host_for_purchase_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('select_host_new_'))` | — |
| 7535 | `async select_host_for_gift_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('select_host_gift_'))` | — |
| 7550 | `async extend_key_handler(callback)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('extend_key_'))` | — |
| 7590 | `async plan_selection_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('buy_'))` | — |
| 7616 | `async back_to_plans_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_email, F.data == 'back_to_plans')` | `src/shop_bot/bot/handlers.py::back_to_email_prompt_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 7680 | `async process_email_handler(message, state)` | HTTP-маршрут: `user_router.message(PaymentProcess.waiting_for_email)` | — |
| 7689 | `async skip_email_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_email, F.data == 'skip_email')` | — |
| 7694 | `async show_payment_options(message, state)` | — | `src/shop_bot/bot/handlers.py::cancel_promo_entry`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::handle_promo_code_input`<br>`src/shop_bot/bot/handlers.py::payment_stars_back_handler`<br>`src/shop_bot/bot/handlers.py::plan_selection_handler`<br>`src/shop_bot/bot/handlers.py::process_email_handler` |
| 7821 | `async back_to_email_prompt_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'back_to_email_prompt')` | — |
| 7835 | `async prompt_promo_code(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'enter_promo_code')` | — |
| 7844 | `async cancel_promo_entry(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_promo_code, F.data == 'cancel_promo')` | — |
| 7849 | `async handle_promo_code_input(message, state)` | HTTP-маршрут: `user_router.message(PaymentProcess.waiting_for_promo_code)` | — |
| 7888 | `async create_yookassa_payment_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_yookassa')` | — |
| 8026 | `async pay_platega_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_platega')` | — |
| 8114 | `async pay_rollypay_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_rollypay')` | — |
| 8202 | `async create_cryptobot_invoice_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_cryptobot')` | — |
| 8279 | `async check_crypto_invoice_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('check_crypto_invoice:'))` | — |
| 8406 | `async create_ton_invoice_handler(callback, state)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_tonconnect')` | — |
| 8477 | `async pay_with_main_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_balance')` | — |
| 8523 | `async pay_with_referral_balance_handler(callback, state, bot)` | HTTP-маршрут: `user_router.callback_query(PaymentProcess.waiting_for_payment_method, F.data == 'pay_referral_balance')` | — |
| 8578 | `async stale_payment_method_callback(callback)` | Устаревшие pay_* после смены FSM (например, после Stars invoice). | — |
| 8594 | `async _gift_username_catcher(message)` | HTTP-маршрут: `user_router.message(StateFilter(None), F.text)` | — |
| 8723 | `_kb_cancel_factory()` | — | `src/shop_bot/bot/handlers.py::franchise_create_bot`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 8729 | `_kb_partner_cabinet()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_cabinet` |
| 8738 | `_kb_partner_withdraw()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_withdraw` |
| 8745 | `_kb_partner_requisites(items)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_delete`<br>`src/shop_bot/bot/handlers.py::partner_requisite_set_default`<br>`src/shop_bot/bot/handlers.py::partner_requisite_value`<br>`src/shop_bot/bot/handlers.py::partner_requisites`<br>`src/shop_bot/bot/handlers.py::partner_withdraw` |
| 8762 | `_kb_partner_requisite_input()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_add`<br>`src/shop_bot/bot/handlers.py::partner_requisite_bank` |
| 8768 | `_mask_requisite(value, rtype)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_delete`<br>`src/shop_bot/bot/handlers.py::partner_requisite_set_default`<br>`src/shop_bot/bot/handlers.py::partner_requisite_value`<br>`src/shop_bot/bot/handlers.py::partner_requisites` |
| 8781 | `_infer_requisite_type(value)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_value` |
| 8793 | `async partner_requisites(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'partner_requisites')` | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_cancel`<br>`src/shop_bot/bot/handlers.py::partner_requisite_set_default` |
| 8828 | `async partner_requisite_add(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'partner_requisite_add')` | — |
| 8848 | `async partner_requisite_cancel(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'partner_requisite_cancel')` | — |
| 8864 | `async partner_requisite_bank(message, state, bot)` | HTTP-маршрут: `user_router.message(FranchiseStates.waiting_requisites_bank)` | — |
| 8889 | `async partner_requisite_value(message, state, bot)` | HTTP-маршрут: `user_router.message(FranchiseStates.waiting_requisites_value)` | — |
| 8937 | `async partner_requisite_set_default(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('req_set_default:'))` | — |
| 8970 | `async partner_requisite_delete(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data.startswith('req_delete:'))` | — |
| 9002 | `async franchise_create_bot(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'factory_create_bot')` | — |
| 9028 | `async franchise_cancel(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'factory_cancel')` | — |
| 9041 | `async franchise_receive_token(message, state, bot)` | HTTP-маршрут: `user_router.message(FranchiseStates.waiting_bot_token)` | — |
| 9104 | `async partner_cabinet(cb, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'partner_cabinet')` | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::partner_requisite_cancel`<br>`src/shop_bot/bot/handlers.py::partner_withdraw_cancel` |
| 9136 | `async partner_withdraw(cb, state, bot)` | HTTP-маршрут: `user_router.callback_query(F.data == 'partner_withdraw')` | — |
| 9174 | `async partner_withdraw_cancel(cb, state)` | HTTP-маршрут: `user_router.callback_query(F.data == 'partner_withdraw_cancel')` | — |
| 9191 | `async partner_withdraw_amount(message, state, bot)` | HTTP-маршрут: `user_router.message(FranchiseStates.waiting_withdraw_amount)` | — |
| 9297 | `async notify_admin_of_purchase(bot, metadata)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 9351 | `_to_int(val)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings`<br>`src/shop_bot/bot/handlers.py::notify_admin_of_purchase`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics` |
| 9404 | `async process_successful_payment(bot, metadata)` | Обработать успешную оплату и выдать услугу. | `src/shop_bot/bot/handlers.py::check_crypto_invoice_handler`<br>`src/shop_bot/bot/handlers.py::check_pending_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 9415 | `_provider_ids_for_log(meta)` | Извлекает ID транзакции/инвойса на стороне платёжного провайдера из исходных | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 9434 | `_to_int(val, default)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings`<br>`src/shop_bot/bot/handlers.py::notify_admin_of_purchase`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics` |

## src/shop_bot/webhook_server/app.py

Flask-админка, вебхуки платежей, CRUD сущностей, модули, франшиза.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 144 | `_parse_decimal_amount(value, log_prefix)` | — | `src/shop_bot/webhook_server/app.py::_pending_expected_amount`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::heleket_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::yookassa_webhook_handler` |
| 160 | `_setting_flag_enabled(raw)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::yoomoney_webhook_handler` |
| 164 | `_pending_method_allowed(pending_meta, *allowed)` | True if pending metadata.payment_method matches one of the allowed provider names. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::heleket_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::yoomoney_webhook_handler` |
| 172 | `_pending_expected_amount(pending_meta)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::heleket_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::yoomoney_webhook_handler` |
| 181 | `_platega_amount_covers_order(got_amount, expected_amount)` | Platega callback amount is what the customer paid. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 190 | `_extract_platega_webhook_amount(payload)` | Platega callback: top-level `amount`, with paymentDetails.amount as fallback. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 202 | `_dispatch_payment_processing(metadata)` | Fulfill paid orders even when the polling bot loop isn't running. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::cryptobot_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::heleket_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::ton_webhook_handler` |
| 231 | `_worker()` | — | — |
| 232 | `async _run()` | — | `src/shop_bot/modules/remnawave_api.py::gather_limited`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_job`<br>`src/shop_bot/webhook_server/app.py::_worker` |
| 250 | `_dispatch_bot_notification(user_id, text)` | Отправляет произвольное текстовое уведомление пользователю бота из админ-панели | `src/shop_bot/webhook_server/app.py::analytics_broadcasts_send_now`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::referral_program_request_status_route` |
| 267 | `async _send(bot_instance)` | — | `src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_run`<br>`src/shop_bot/webhook_server/app.py::_worker` |
| 282 | `_worker()` | — | — |
| 283 | `async _run()` | — | `src/shop_bot/modules/remnawave_api.py::gather_limited`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_job`<br>`src/shop_bot/webhook_server/app.py::_worker` |
| 438 | `franchise_settings()` | Возвращает текущее состояние франшизы. | `src/shop_bot/bot/admin_handlers.py::_get_franchise_settings_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/keyboards.py::create_main_menu_keyboard`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year` |
| 450 | `franchise_menu_button_visible()` | Видимость пункта «Франшиза» в меню веб-админки (независимо от franchise_enabled). | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year` |
| 459 | `_run_on_root_bot_loop(action, wait, timeout)` | Запустить coroutine action(service) на loop root-бота из Flask-потока. | `src/shop_bot/webhook_server/app.py::_apply_franchise_runtime`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_delete_bot_route`<br>`src/shop_bot/webhook_server/app.py::franchise_toggle_bot_route` |
| 493 | `_apply_franchise_runtime(enabled)` | Включить/выключить все клоны на уже работающем event loop. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::settings_page`<br>`src/shop_bot/webhook_server/app.py::toggle_franchise_settings` |
| 506 | `toggle_franchise_settings()` | Переключает состояние франшизы (ВКЛ/ВЫКЛ). | `src/shop_bot/bot/admin_handlers.py::admin_franchise_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 531 | `_forum_coro_wait(loop, coro, timeout)` | — | `src/shop_bot/webhook_server/app.py::run_bulk_ticket_followup` |
| 536 | `run_bulk_ticket_followup(action, forum_targets, media_ticket_ids, bot, loop, gap_sec, call_timeout)` | Форум и файлы после массового SQL. Не вызывать из HTTP-потока в проде. | `src/shop_bot/webhook_server/app.py::_job`<br>`src/shop_bot/webhook_server/app.py::_schedule_bulk_ticket_followup`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 615 | `create_webhook_app(bot_controller_instance)` | — | `src/shop_bot/__main__.py::main` |
| 665 | `_handle_promo_after_payment(metadata)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::heleket_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler` |
| 760 | `inject_current_year()` | Inject common variables into all templates | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_page_proxy`<br>`src/shop_bot/webhook_server/app.py::wrapped_render_template` |
| 799 | `login_required(f)` | — | — |
| 801 | `decorated_function(*args, **kwargs)` | — | — |
| 811 | `_rate_limit_login(ip, limit, window_sec)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::login_page` |
| 824 | `_login_client_ip()` | IP for login rate-limit. Honor X-Forwarded-For only behind a local proxy. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::login_page` |
| 833 | `_verify_panel_password(stored, provided)` | Verify panel password. Prefers bcrypt hashes; legacy plaintext uses compare_digest. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::login_page` |
| 846 | `login_page()` | HTTP-маршрут: `flask_app.route('/login', methods=['GET', 'POST'])` | — |
| 890 | `logout_page()` | HTTP-маршрут: `flask_app.route('/logout', methods=['POST'])` | — |
| 895 | `get_common_template_data()` | — | `src/shop_bot/webhook_server/app.py::admin_balance_page`<br>`src/shop_bot/webhook_server/app.py::admin_keys_page`<br>`src/shop_bot/webhook_server/app.py::analytics_broadcasts_page`<br>`src/shop_bot/webhook_server/app.py::analytics_coupons_page`<br>`src/shop_bot/webhook_server/app.py::analytics_economics_page`<br>`src/shop_bot/webhook_server/app.py::analytics_forecast_page` |
| 943 | `update_brand_title_route()` | HTTP-маршрут: `flask_app.route('/brand-title', methods=['POST'])` | — |
| 955 | `index()` | HTTP-маршрут: `flask_app.route('/')` | — |
| 960 | `dashboard_page()` | HTTP-маршрут: `flask_app.route('/dashboard')` | — |
| 1004 | `run_speedtests_route()` | HTTP-маршрут: `flask_app.route('/dashboard/run-speedtests', methods=['POST'])` | — |
| 1014 | `dashboard_stats_partial()` | HTTP-маршрут: `flask_app.route('/dashboard/stats.partial')` | — |
| 1026 | `dashboard_transactions_partial()` | HTTP-маршрут: `flask_app.route('/dashboard/transactions.partial')` | — |
| 1034 | `dashboard_charts_json()` | HTTP-маршрут: `flask_app.route('/dashboard/charts.json')` | — |
| 1041 | `statistics_page()` | Страница статистики (обзор). | — |
| 1197 | `_labels(days)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::statistics_page` |
| 1285 | `analytics_overview_page()` | HTTP-маршрут: `flask_app.route('/analytics')` | — |
| 1303 | `analytics_overview_charts_json()` | HTTP-маршрут: `flask_app.route('/analytics/overview_charts.json')` | — |
| 1310 | `analytics_transactions_page()` | HTTP-маршрут: `flask_app.route('/analytics/transactions')` | — |
| 1335 | `analytics_transactions_csv()` | HTTP-маршрут: `flask_app.route('/analytics/transactions.csv')` | — |
| 1368 | `analytics_plans_page()` | HTTP-маршрут: `flask_app.route('/analytics/plans')` | — |
| 1375 | `analytics_payment_methods_page()` | HTTP-маршрут: `flask_app.route('/analytics/payment-methods')` | — |
| 1382 | `analytics_referrals_page()` | HTTP-маршрут: `flask_app.route('/analytics/referrals')` | — |
| 1398 | `analytics_coupons_page()` | HTTP-маршрут: `flask_app.route('/analytics/coupons')` | — |
| 1406 | `analytics_coupons_create_route()` | HTTP-маршрут: `flask_app.route('/analytics/coupons/create', methods=['POST'])` | — |
| 1458 | `analytics_coupons_toggle_route(code)` | HTTP-маршрут: `flask_app.route('/analytics/coupons/<path:code>/toggle', methods=['POST'])` | — |
| 1469 | `analytics_coupons_delete_route(code)` | HTTP-маршрут: `flask_app.route('/analytics/coupons/<path:code>/delete', methods=['POST'])` | — |
| 1479 | `analytics_utm_page()` | HTTP-маршрут: `flask_app.route('/analytics/utm')` | — |
| 1493 | `analytics_utm_create_route()` | HTTP-маршрут: `flask_app.route('/analytics/utm/create', methods=['POST'])` | — |
| 1514 | `analytics_utm_delete_route(slug)` | HTTP-маршрут: `flask_app.route('/analytics/utm/<path:slug>/delete', methods=['POST'])` | — |
| 1527 | `_referral_program_common()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::referral_program_requests_page`<br>`src/shop_bot/webhook_server/app.py::referral_program_settings_page`<br>`src/shop_bot/webhook_server/app.py::referral_program_top_page` |
| 1537 | `referral_program_page()` | HTTP-маршрут: `flask_app.route('/referral-program')` | — |
| 1542 | `referral_program_settings_page()` | HTTP-маршрут: `flask_app.route('/referral-program/settings', methods=['GET'])` | — |
| 1557 | `referral_program_settings_route()` | HTTP-маршрут: `flask_app.route('/referral-program/settings', methods=['POST'])` | — |
| 1580 | `referral_program_top_page()` | HTTP-маршрут: `flask_app.route('/referral-program/top')` | — |
| 1593 | `referral_program_requests_page()` | HTTP-маршрут: `flask_app.route('/referral-program/requests')` | — |
| 1608 | `referral_program_request_status_route(request_id)` | HTTP-маршрут: `flask_app.route('/referral-program/requests/<int:request_id>/status', methods=['POST'])` | — |
| 1647 | `analytics_economics_page()` | HTTP-маршрут: `flask_app.route('/analytics/economics')` | — |
| 1661 | `analytics_economics_create_route()` | HTTP-маршрут: `flask_app.route('/analytics/economics/create', methods=['POST'])` | — |
| 1677 | `analytics_economics_delete_route(entry_id)` | HTTP-маршрут: `flask_app.route('/analytics/economics/<int:entry_id>/delete', methods=['POST'])` | — |
| 1684 | `analytics_forecast_page()` | HTTP-маршрут: `flask_app.route('/analytics/forecast')` | — |
| 1700 | `analytics_broadcasts_page()` | HTTP-маршрут: `flask_app.route('/analytics/broadcasts')` | — |
| 1714 | `analytics_broadcasts_create()` | HTTP-маршрут: `flask_app.route('/analytics/broadcasts/create', methods=['POST'])` | — |
| 1735 | `analytics_broadcasts_update(campaign_id)` | HTTP-маршрут: `flask_app.route('/analytics/broadcasts/<int:campaign_id>/update', methods=['POST'])` | — |
| 1752 | `analytics_broadcasts_toggle(campaign_id)` | HTTP-маршрут: `flask_app.route('/analytics/broadcasts/<int:campaign_id>/toggle', methods=['POST'])` | — |
| 1759 | `analytics_broadcasts_delete(campaign_id)` | HTTP-маршрут: `flask_app.route('/analytics/broadcasts/<int:campaign_id>/delete', methods=['POST'])` | — |
| 1768 | `analytics_broadcasts_send_now(campaign_id)` | HTTP-маршрут: `flask_app.route('/analytics/broadcasts/<int:campaign_id>/send-now', methods=['POST'])` | — |
| 1800 | `_build_nginx_config(domain, port)` | HTTP-only config; serves ACME webroot so certbot --webroot works. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_nginx_config_route`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 1825 | `_build_nginx_ssl_config(domain, port)` | Full SSL config: HTTP → HTTPS redirect + HTTPS reverse proxy. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 1867 | `webapp_nginx_config_route()` | HTTP-маршрут: `flask_app.route('/settings/webapp/nginx-config')` | — |
| 1882 | `webapp_setup_route()` | HTTP-маршрут: `flask_app.route('/settings/webapp/setup', methods=['POST'])` | — |
| 1889 | `_step(name, status, message)` | — | `src/shop_bot/webhook_server/app.py::_nginx_reload`<br>`src/shop_bot/webhook_server/app.py::_nginx_start`<br>`src/shop_bot/webhook_server/app.py::_run`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 1892 | `_run(name, cmd, timeout, extra_env)` | — | `src/shop_bot/modules/remnawave_api.py::gather_limited`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_job`<br>`src/shop_bot/webhook_server/app.py::_worker` |
| 1934 | `_nginx_reload(step_name)` | Try nginx -s reload first (works in Docker), fall back to service/systemctl. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 1949 | `_nginx_start()` | Start nginx after fresh install (Docker-compatible). | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 2033 | `_find_traefik_dynamic_dir()` | Return (dynamic_dir, cert_resolver) scanning filesystem then docker. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 2133 | `_write_traefik_config(dynamic_dir, cert_resolver)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::webapp_setup_route` |
| 2247 | `webapp_check_route()` | HTTP-маршрут: `flask_app.route('/settings/webapp/check', methods=['POST'])` | — |
| 2267 | `monitor_page()` | HTTP-маршрут: `flask_app.route('/monitor')` | — |
| 2282 | `monitor_local_json()` | HTTP-маршрут: `flask_app.route('/monitor/local.json')` | — |
| 2291 | `monitor_host_json(host_name)` | HTTP-маршрут: `flask_app.route('/monitor/host/<host_name>.json')` | — |
| 2300 | `monitor_target_json(target_name)` | HTTP-маршрут: `flask_app.route('/monitor/target/<target_name>.json')` | — |
| 2310 | `monitor_series_json(scope, name)` | HTTP-маршрут: `flask_app.route('/monitor/series/<scope>/<name>.json')` | — |
| 2325 | `support_table_partial()` | HTTP-маршрут: `flask_app.route('/support/table.partial')` | — |
| 2334 | `support_open_count_partial()` | HTTP-маршрут: `flask_app.route('/support/open-count.partial')` | — |
| 2350 | `users_page()` | HTTP-маршрут: `flask_app.route('/users')` | — |
| 2395 | `users_table_partial()` | HTTP-маршрут: `flask_app.route('/users/table.partial')` | — |
| 2427 | `user_keys_partial(user_id)` | HTTP-маршрут: `flask_app.route('/users/<int:user_id>/keys.partial')` | — |
| 2442 | `user_transactions_partial(user_id)` | HTTP-маршрут: `flask_app.route('/users/<int:user_id>/transactions.partial')` | — |
| 2465 | `user_referrals_json(user_id)` | HTTP-маршрут: `flask_app.route('/users/<int:user_id>/referrals.json')` | — |
| 2474 | `users_search_json()` | Живой поиск пользователей по ID/username — для модалки "Назначить реферала" | — |
| 2503 | `admin_global_search_json()` | Живой поиск по пользователям и ключам для топбара админки. | — |
| 2549 | `assign_referral_route(referrer_id)` | Вручную назначить реферала: пользователь `user_id` (из формы) становится | — |
| 2583 | `remove_referral_route(referrer_id, invitee_id)` | Снять одного реферала с карточки реферера (обнулить users.referred_by). | — |
| 2601 | `remove_all_referrals_route(referrer_id)` | Снять всех рефералов у указанного реферера. | — |
| 2620 | `users_pagination_partial()` | HTTP-маршрут: `flask_app.route('/users/pagination.partial')` | — |
| 2632 | `user_details_json(user_id)` | HTTP-маршрут: `flask_app.route('/users/<int:user_id>/details.json')` | — |
| 2686 | `adjust_balance_route(user_id)` | HTTP-маршрут: `flask_app.route('/users/<int:user_id>/balance/adjust', methods=['POST'])` | — |
| 2727 | `adjust_referral_balance_route(user_id)` | HTTP-маршрут: `flask_app.route('/users/<int:user_id>/referral-balance/adjust', methods=['POST'])` | — |
| 2766 | `admin_keys_page()` | HTTP-маршрут: `flask_app.route('/admin/keys')` | — |
| 2808 | `admin_keys_table_partial()` | HTTP-маршрут: `flask_app.route('/admin/keys/table.partial')` | — |
| 2823 | `admin_keys_pagination_partial()` | HTTP-маршрут: `flask_app.route('/admin/keys/pagination.partial')` | — |
| 2841 | `_resolve_key_plan(key)` | Определяет актуальный тариф ключа по plan_id, сохранённому в его description. | `src/shop_bot/webhook_server/app.py::admin_key_add_lte_traffic_route`<br>`src/shop_bot/webhook_server/app.py::admin_key_add_traffic_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 2855 | `admin_key_details_json(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/details')` | — |
| 3001 | `admin_key_change_plan_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/change-plan', methods=['POST'])` | — |
| 3089 | `admin_key_add_traffic_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/add-traffic', methods=['POST'])` | — |
| 3150 | `admin_key_add_lte_traffic_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/add-lte-traffic', methods=['POST'])` | — |
| 3213 | `admin_key_delete_device_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/devices/delete', methods=['POST'])` | — |
| 3243 | `admin_key_delete_all_devices_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/devices/delete-all', methods=['POST'])` | — |
| 3296 | `admin_get_plans_for_host_json(host_name)` | HTTP-маршрут: `flask_app.route('/admin/hosts/<host_name>/plans')` | — |
| 3314 | `create_key_route()` | HTTP-маршрут: `flask_app.route('/admin/keys/create', methods=['POST'])` | — |
| 3402 | `create_key_ajax_route()` | Создание ключа через панель: персонального либо универсального подарочного токена. | — |
| 3655 | `generate_key_email_route()` | HTTP-маршрут: `flask_app.route('/admin/keys/generate-email')` | — |
| 3668 | `delete_key_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/delete', methods=['POST'])` | — |
| 3685 | `adjust_key_expiry_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/adjust-expiry', methods=['POST'])` | — |
| 3759 | `sweep_expired_keys_route()` | HTTP-маршрут: `flask_app.route('/admin/keys/sweep-expired', methods=['POST'])` | — |
| 3835 | `_parse_bulk_expiry_params()` | Общие параметры модалки bulk-extend: mode=days\|date + days / expire_at. | `src/shop_bot/webhook_server/app.py::bulk_extend_all_keys_route`<br>`src/shop_bot/webhook_server/app.py::bulk_extend_keys_route`<br>`src/shop_bot/webhook_server/app.py::bulk_extend_user_keys_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3855 | `_apply_bulk_expiry_to_ids(key_ids, params)` | — | `src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::_run`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3877 | `_flash_bulk_expiry_result(ok_n, fail_n, failed_ids)` | — | `src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3891 | `_dispatch_bulk_expiry(key_ids, params, admin_who, label, log_extra, fallback_endpoint)` | — | `src/shop_bot/webhook_server/app.py::bulk_extend_all_keys_route`<br>`src/shop_bot/webhook_server/app.py::bulk_extend_keys_route`<br>`src/shop_bot/webhook_server/app.py::bulk_extend_user_keys_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 3905 | `_run()` | — | `src/shop_bot/modules/remnawave_api.py::gather_limited`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_job`<br>`src/shop_bot/webhook_server/app.py::_worker` |
| 3947 | `_job()` | — | — |
| 3978 | `bulk_extend_keys_route()` | Режим 1: изменить срок у выбранных key_ids (чекбоксы на странице). | — |
| 4010 | `bulk_extend_all_keys_route()` | Режим 2: изменить срок у ВСЕХ ключей в vpn_keys (игнорирует фильтры/выбор). | — |
| 4034 | `bulk_extend_user_keys_route()` | Изменить срок у всех ключей одного пользователя (карточка пользователя). | — |
| 4070 | `update_key_comment_route(key_id)` | HTTP-маршрут: `flask_app.route('/admin/keys/<int:key_id>/comment', methods=['POST'])` | — |
| 4079 | `update_host_ssh_route()` | HTTP-маршрут: `flask_app.route('/admin/hosts/ssh/update', methods=['POST'])` | — |
| 4102 | `run_ssh_target_speedtest_route(target_name)` | HTTP-маршрут: `flask_app.route('/admin/ssh-targets/<target_name>/speedtest/run', methods=['POST'])` | — |
| 4128 | `run_all_ssh_target_speedtests_route()` | HTTP-маршрут: `flask_app.route('/admin/ssh-targets/speedtests/run-all', methods=['POST'])` | — |
| 4163 | `run_host_speedtest_route(host_name)` | HTTP-маршрут: `flask_app.route('/admin/hosts/<host_name>/speedtest/run', methods=['POST'])` | — |
| 4195 | `host_speedtests_json(host_name)` | HTTP-маршрут: `flask_app.route('/admin/hosts/<host_name>/speedtests.json')` | — |
| 4211 | `run_all_speedtests_route()` | HTTP-маршрут: `flask_app.route('/admin/speedtests/run-all', methods=['POST'])` | — |
| 4246 | `auto_install_speedtest_route(host_name)` | HTTP-маршрут: `flask_app.route('/admin/hosts/<host_name>/speedtest/install', methods=['POST'])` | — |
| 4274 | `admin_balance_page()` | HTTP-маршрут: `flask_app.route('/admin/balance')` | — |
| 4294 | `support_list_page()` | HTTP-маршрут: `flask_app.route('/support')` | — |
| 4316 | `_schedule_bulk_ticket_followup(action, forum_targets, media_ticket_ids)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_bulk_close_route`<br>`src/shop_bot/webhook_server/app.py::support_bulk_delete_route` |
| 4335 | `_job()` | — | — |
| 4347 | `support_bulk_close_route()` | HTTP-маршрут: `flask_app.route('/support/bulk-close', methods=['POST'])` | — |
| 4367 | `support_bulk_delete_route()` | HTTP-маршрут: `flask_app.route('/support/bulk-delete', methods=['POST'])` | — |
| 4388 | `support_ticket_page(ticket_id)` | HTTP-маршрут: `flask_app.route('/support/<int:ticket_id>', methods=['GET', 'POST'])` | — |
| 4492 | `support_ticket_messages_api(ticket_id)` | HTTP-маршрут: `flask_app.route('/support/<int:ticket_id>/messages.json')` | — |
| 4507 | `block_ticket_files_dir(rest)` | HTTP-маршрут: `flask_app.route('/ticket_files', defaults={'rest': ''}, methods=['GET', 'HEAD', 'POST'])` | — |
| 4511 | `support_ticket_file(message_id)` | Отдаёт вложение тикета. | — |
| 4567 | `delete_support_ticket_route(ticket_id)` | HTTP-маршрут: `flask_app.route('/support/<int:ticket_id>/delete', methods=['POST'])` | — |
| 4607 | `settings_page()` | HTTP-маршрут: `flask_app.route('/settings', methods=['GET', 'POST'])` | — |
| 4842 | `_as_bool(value)` | — | `src/shop_bot/webhook_server/app.py::_build_module_settings_form`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_settings_page` |
| 4845 | `_get_module_info(module_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_settings_page` |
| 4851 | `_build_module_settings_form(module_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_settings_page` |
| 4881 | `modules_page()` | HTTP-маршрут: `flask_app.route('/modules/', methods=['GET'])` | — |
| 4888 | `module_enable_route(module_id)` | HTTP-маршрут: `flask_app.route('/modules/<module_id>/enable', methods=['POST'])` | — |
| 4895 | `module_disable_route(module_id)` | HTTP-маршрут: `flask_app.route('/modules/<module_id>/disable', methods=['POST'])` | — |
| 4902 | `module_delete_route(module_id)` | HTTP-маршрут: `flask_app.route('/modules/<module_id>/delete', methods=['POST'])` | — |
| 4909 | `module_settings_page(module_id)` | HTTP-маршрут: `flask_app.route('/modules/<module_id>/settings', methods=['GET', 'POST'])` | — |
| 4946 | `module_page_proxy(module_id, subpath)` | Proxy request to module's panel routes if they exist. | — |
| 4995 | `wrapped_render_template(template_name_or_list, **kwargs)` | — | — |
| 5025 | `module_upload_route()` | Upload and install a module from ZIP file. | — |
| 5077 | `create_ssh_target_route()` | HTTP-маршрут: `flask_app.route('/admin/ssh-targets/create', methods=['POST'])` | — |
| 5106 | `update_ssh_target_route(target_name)` | HTTP-маршрут: `flask_app.route('/admin/ssh-targets/<target_name>/update', methods=['POST'])` | — |
| 5132 | `delete_ssh_target_route(target_name)` | HTTP-маршрут: `flask_app.route('/admin/ssh-targets/<target_name>/delete', methods=['POST'])` | — |
| 5141 | `auto_install_speedtest_on_target_route(target_name)` | HTTP-маршрут: `flask_app.route('/admin/ssh-targets/<target_name>/speedtest/install', methods=['POST'])` | — |
| 5169 | `smtp_test_route()` | HTTP-маршрут: `flask_app.route('/settings/smtp/test', methods=['POST'])` | — |
| 5207 | `backup_db_route()` | HTTP-маршрут: `flask_app.route('/admin/db/backup', methods=['POST'])` | — |
| 5222 | `restore_db_route()` | HTTP-маршрут: `flask_app.route('/admin/db/restore', methods=['POST'])` | — |
| 5267 | `update_remnawave_settings_route()` | HTTP-маршрут: `flask_app.route('/settings/remnawave', methods=['POST'])` | — |
| 5290 | `add_remnawave_squad_route()` | HTTP-маршрут: `flask_app.route('/add-remnawave-squad', methods=['POST'])` | — |
| 5303 | `delete_remnawave_squad_route(squad_id)` | HTTP-маршрут: `flask_app.route('/delete-remnawave-squad/<int:squad_id>', methods=['POST'])` | — |
| 5310 | `update_host_squad_selection_route()` | HTTP-маршрут: `flask_app.route('/update-host-squad-selection', methods=['POST'])` | — |
| 5344 | `update_host_subscription_route()` | HTTP-маршрут: `flask_app.route('/update-host-subscription', methods=['POST'])` | — |
| 5359 | `update_host_url_route()` | HTTP-маршрут: `flask_app.route('/update-host-url', methods=['POST'])` | — |
| 5371 | `update_host_remnawave_route()` | HTTP-маршрут: `flask_app.route('/update-host-remnawave', methods=['POST'])` | — |
| 5390 | `add_host_squad_route()` | HTTP-маршрут: `flask_app.route('/add-host-squad', methods=['POST'])` | — |
| 5404 | `toggle_host_squad_route(squad_id)` | HTTP-маршрут: `flask_app.route('/toggle-host-squad/<int:squad_id>', methods=['POST'])` | — |
| 5412 | `delete_host_squad_route(squad_id)` | HTTP-маршрут: `flask_app.route('/delete-host-squad/<int:squad_id>', methods=['POST'])` | — |
| 5419 | `rename_host_route()` | HTTP-маршрут: `flask_app.route('/rename-host', methods=['POST'])` | — |
| 5431 | `start_support_bot_route()` | HTTP-маршрут: `flask_app.route('/start-support-bot', methods=['POST'])` | — |
| 5436 | `_wait_for_stop(controller, timeout)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::restart_both_bots_route`<br>`src/shop_bot/webhook_server/app.py::stop_bot_route`<br>`src/shop_bot/webhook_server/app.py::stop_both_bots_route`<br>`src/shop_bot/webhook_server/app.py::stop_support_bot_route` |
| 5447 | `stop_support_bot_route()` | HTTP-маршрут: `flask_app.route('/stop-support-bot', methods=['POST'])` | — |
| 5455 | `start_bot_route()` | HTTP-маршрут: `flask_app.route('/start-bot', methods=['POST'])` | — |
| 5462 | `stop_bot_route()` | HTTP-маршрут: `flask_app.route('/stop-bot', methods=['POST'])` | — |
| 5470 | `stop_both_bots_route()` | HTTP-маршрут: `flask_app.route('/stop-both-bots', methods=['POST'])` | — |
| 5489 | `_soft_stop_controller(controller)` | Остановить контроллер; если уже остановлен — считать успехом (для перезапуска). | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::restart_both_bots_route` |
| 5498 | `restart_both_bots_route()` | Остановить оба бота, дождаться остановки и сразу запустить снова — без ручного stop→start. | — |
| 5525 | `start_both_bots_route()` | HTTP-маршрут: `flask_app.route('/start-both-bots', methods=['POST'])` | — |
| 5544 | `ban_user_route(user_id)` | HTTP-маршрут: `flask_app.route('/users/ban/<int:user_id>', methods=['POST'])` | — |
| 5591 | `unban_user_route(user_id)` | HTTP-маршрут: `flask_app.route('/users/unban/<int:user_id>', methods=['POST'])` | — |
| 5615 | `delete_user_route(user_id)` | Полное удаление пользователя (как admin_delete_user в боте). | — |
| 5668 | `revoke_keys_route(user_id)` | HTTP-маршрут: `flask_app.route('/users/revoke/<int:user_id>', methods=['POST'])` | — |
| 5714 | `add_host_route()` | HTTP-маршрут: `flask_app.route('/add-host', methods=['POST'])` | — |
| 5769 | `delete_host_route(host_name)` | HTTP-маршрут: `flask_app.route('/delete-host/<host_name>', methods=['POST'])` | — |
| 5776 | `add_plan_route()` | HTTP-маршрут: `flask_app.route('/add-plan', methods=['POST'])` | — |
| 5827 | `delete_plan_route(plan_id)` | HTTP-маршрут: `flask_app.route('/delete-plan/<int:plan_id>', methods=['POST'])` | — |
| 5834 | `toggle_plan_route(plan_id)` | HTTP-маршрут: `flask_app.route('/toggle-plan/<int:plan_id>', methods=['POST'])` | — |
| 5851 | `update_plan_route(plan_id)` | HTTP-маршрут: `flask_app.route('/update-plan/<int:plan_id>', methods=['POST'])` | — |
| 5909 | `_normalize_package_pool(raw)` | Пул пакета докупки: 'lte' (💰 premium-ноды) или 'main' (основной трафик). | `src/shop_bot/webhook_server/app.py::add_traffic_package_route`<br>`src/shop_bot/webhook_server/app.py::admin_get_traffic_packages_for_plan_json`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 5915 | `admin_get_traffic_packages_for_plan_json(plan_id)` | HTTP-маршрут: `flask_app.route('/admin/plans/<int:plan_id>/packages')` | — |
| 5934 | `add_traffic_package_route()` | HTTP-маршрут: `flask_app.route('/add-traffic-package', methods=['POST'])` | — |
| 5958 | `update_traffic_package_route(package_id)` | HTTP-маршрут: `flask_app.route('/update-traffic-package/<int:package_id>', methods=['POST'])` | — |
| 5985 | `toggle_traffic_package_route(package_id)` | HTTP-маршрут: `flask_app.route('/toggle-traffic-package/<int:package_id>', methods=['POST'])` | — |
| 5997 | `delete_traffic_package_route(package_id)` | HTTP-маршрут: `flask_app.route('/delete-traffic-package/<int:package_id>', methods=['POST'])` | — |
| 6004 | `_get_client_ip()` | Best-effort client IP (supports reverse proxy via X-Forwarded-For). | `src/shop_bot/webhook_server/app.py::_is_ip_allowed`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::ton_webhook_handler` |
| 6014 | `_is_ip_allowed(allowlist)` | — | `src/shop_bot/webhook_server/app.py::_debug_endpoints_allowed`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 6020 | `_debug_endpoints_allowed()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::debug_all_requests`<br>`src/shop_bot/webhook_server/app.py::test_webhook` |
| 6026 | `_http_json(url, method, headers, body, timeout)` | Minimal JSON HTTP client via urllib (avoids extra deps). | `src/shop_bot/webhook_server/app.py::_cryptobot_get_invoice`<br>`src/shop_bot/webhook_server/app.py::_yookassa_get_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::yookassa_webhook_handler` |
| 6038 | `_yookassa_get_payment(payment_id)` | — | — |
| 6053 | `_cryptobot_verify_signature(raw_body)` | — | — |
| 6068 | `_cryptobot_get_invoice(invoice_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::cryptobot_webhook_handler` |
| 6090 | `_require_ton_webhook_secret()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::ton_webhook_handler` |
| 6106 | `yookassa_webhook_handler()` | YooKassa webhook (secure). | — |
| 6217 | `test_webhook()` | Тестовый endpoint. В продакшне отключен по умолчанию. | — |
| 6227 | `debug_all_requests()` | Опасный debug endpoint: возвращает заголовки/куки/данные. В продакшне отключен по умолчанию. | — |
| 6252 | `yoomoney_webhook_handler()` | ЮMoney HTTP уведомление (кнопка/ссылка p2p). Подпись: sha1(notification_type&operation_id&amount&currency&datetime&sender&codepro&notification_secret&label). | — |
| 6360 | `platega_webhook_handler()` | Platega webhook. Авторизация: заголовки X-MerchantId / X-Secret. Payload содержит статус и поле payload (наш payment_id). | — |
| 6478 | `rollypay_webhook_handler()` | RollyPay webhook. | — |
| 6629 | `cryptobot_webhook_handler()` | Crypto Pay API webhook (secure). | — |
| 6778 | `heleket_webhook_handler()` | — | — |
| 6866 | `ton_webhook_handler()` | TonAPI webhook (hardened): | — |
| 6926 | `_ym_get_redirect_uri()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::yoomoney_callback_route`<br>`src/shop_bot/webhook_server/app.py::yoomoney_connect_route` |
| 6938 | `yoomoney_connect_route()` | HTTP-маршрут: `flask_app.route('/yoomoney/connect')` | — |
| 6960 | `yoomoney_callback_route()` | — | — |
| 7007 | `yoomoney_check_route()` | HTTP-маршрут: `flask_app.route('/yoomoney/check', methods=['GET', 'POST'])` | — |
| 7053 | `get_button_configs_api(menu_type)` | Get button configurations for a specific menu type (including inactive for admin) | — |
| 7066 | `create_button_config_api()` | Create a new button configuration | — |
| 7098 | `update_button_config_api(button_id)` | Update an existing button configuration | — |
| 7130 | `delete_button_config_api(button_id)` | Delete a button configuration | — |
| 7145 | `reorder_button_configs_api(menu_type)` | Reorder button configurations for a menu type | — |
| 7169 | `_franchise_db_connect()` | — | `src/shop_bot/webhook_server/app.py::_franchise_bot_stats`<br>`src/shop_bot/webhook_server/app.py::_franchise_get_bot`<br>`src/shop_bot/webhook_server/app.py::_franchise_list_bots`<br>`src/shop_bot/webhook_server/app.py::_franchise_totals`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_bot_page` |
| 7174 | `_franchise_totals()` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_page` |
| 7234 | `_franchise_list_bots(q)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_page` |
| 7293 | `_franchise_get_bot(bot_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_bot_page`<br>`src/shop_bot/webhook_server/app.py::franchise_delete_bot_route` |
| 7309 | `_franchise_bot_stats(bot_id)` | — | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_bot_page` |
| 7362 | `franchise_page()` | HTTP-маршрут: `flask_app.route('/franchise')` | — |
| 7371 | `franchise_bot_page(bot_id)` | HTTP-маршрут: `flask_app.route('/franchise/bot/<int:bot_id>')` | — |
| 7437 | `franchise_toggle_bot_route(bot_id)` | HTTP-маршрут: `flask_app.route('/franchise/bot/<int:bot_id>/toggle', methods=['POST'])` | — |
| 7466 | `franchise_delete_bot_route(bot_id)` | HTTP-маршрут: `flask_app.route('/franchise/bot/<int:bot_id>/delete', methods=['POST'])` | — |
| 7493 | `franchise_withdraw_status_route(req_id)` | HTTP-маршрут: `flask_app.route('/franchise/withdraw/<int:req_id>/status', methods=['POST'])` | — |
| 7516 | `button_constructor_page()` | Button constructor page | — |
| 7526 | `_coerce_checkbox(value)` | — | — |

## src/shop_bot/webapp/handlers.py

FastAPI Mini App: кабинет пользователя, оплата, тикеты, auth.

**Классы:** `SupportStatusRequest`, `SupportTicketCreateRequest`, `SupportMessageSendRequest`, `SupportTicketRequest`, `PaymentMethodsRequest`, `TokenRequest`, `TelegramDirectAuthRequest`, `EmailAuthRequest`, `EmailVerifyRequest`, `EmailResendRequest`, `PasswordResetRequest`, `PasswordResetCheckRequest`, `PasswordResetVerifyRequest`, `SyncTgRequest`, `DeviceTiersRequest`, `CreatePaymentRequest`, `CreateTopUpPaymentRequest`, `CreateLteTopUpPaymentRequest`, `ApplyPromoRequest`, `RenameKeyRequest`, `DeleteAllDevicesRequest`, `SearchKeysRequest`, `CheckPaymentRequest`, `VerifyPlategaPaymentRequest`, `KeyActionRequest`, `DeleteDeviceRequest`, `CommentRequest`, `GiftActivateRequest`, `PendingActionCompleteRequest`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 68 | `_create_payload_pending_or_error(payment_id, user_id, amount, meta)` | Создать pending; если слот промокода уже занят — вернуть ошибку для API. | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 110 | `_email_auth_rate_limit_response()` | — | `src/shop_bot/webapp/handlers.py::_reject_if_email_auth_rate_limited` |
| 120 | `_email_auth_rate_limited(email)` | True, если по этому email уже исчерпан EMAIL_AUTH_PER_EMAIL_LIMIT за окно. | `src/shop_bot/webapp/handlers.py::_reject_if_email_auth_rate_limited` |
| 138 | `_reject_if_email_auth_rate_limited(email)` | — | `src/shop_bot/webapp/handlers.py::api_email_login`<br>`src/shop_bot/webapp/handlers.py::api_email_register`<br>`src/shop_bot/webapp/handlers.py::api_email_resend`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_check`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_request`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_verify` |
| 144 | `_resolve_user_from_request_token(data, request)` | — | `src/shop_bot/webapp/handlers.py::_resolve_authenticated_user`<br>`src/shop_bot/webapp/handlers.py::api_key_auto_renew`<br>`src/shop_bot/webapp/handlers.py::api_key_devices_delete_all`<br>`src/shop_bot/webapp/handlers.py::api_key_rename`<br>`src/shop_bot/webapp/handlers.py::api_keys_search`<br>`src/shop_bot/webapp/handlers.py::api_referral_available_method_types` |
| 167 | `_resolve_authenticated_user(data, request)` | Определить текущего пользователя ИСКЛЮЧИТЕЛЬНО по доверенным источникам: | `src/shop_bot/webapp/handlers.py::_require_authenticated_user`<br>`src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 191 | `_unauthorized(detail)` | — | `src/shop_bot/webapp/handlers.py::api_apply_promo`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_get_payment_methods`<br>`src/shop_bot/webapp/handlers.py::api_gift_activate` |
| 195 | `_require_authenticated_user(request, data, token, init_data)` | Resolve caller from auth_token / Bearer / signed init_data only (CWE-862/639). | `src/shop_bot/webapp/handlers.py::api_apply_promo`<br>`src/shop_bot/webapp/handlers.py::api_check_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_get_payment_methods` |
| 218 | `_ref_setting_is_true(key, default)` | — | `src/shop_bot/webapp/handlers.py::_ref_method_type_enabled`<br>`src/shop_bot/webapp/handlers.py::api_referral_available_method_types`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_add`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_delete`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_list`<br>`src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 223 | `_ref_method_type_enabled(method_type)` | — | `src/shop_bot/webapp/handlers.py::api_referral_payout_methods_add`<br>`src/shop_bot/webapp/handlers.py::api_referral_payout_methods_list` |
| 235 | `get_transaction_comment(user_data, action_type, value, host_name)` | Короткое человекочитаемое описание платежа — для поля description в | `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 264 | `calculate_webapp_price(price, user_id)` | — | `src/shop_bot/webapp/handlers.py::_build_plans_grid_html`<br>`src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 292 | `async notify_admin_of_purchase(bot, metadata)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 296 | `async process_successful_payment(bot, metadata)` | — | `src/shop_bot/bot/handlers.py::check_crypto_invoice_handler`<br>`src/shop_bot/bot/handlers.py::check_pending_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 300 | `async _send_telegram_message(user_id, text, reply_markup, photo)` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_request`<br>`src/shop_bot/webapp/handlers.py::api_referral_request_withdraw` |
| 316 | `async _send_invoice_stars(user_id, title, description, payload, amount)` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 357 | `_platega_api()` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 365 | `_store_platega_transaction_id(payment_id, user_id, amount, meta, txid)` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 376 | `_rollypay_is_enabled()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_rollypay`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_rollypay_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 383 | `_rollypay_api()` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 390 | `_store_rollypay_payment_id(payment_id, user_id, amount, meta, provider_id)` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 401 | `async _fulfill_webapp_paid_order(metadata)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 423 | `_build_yoomoney_link(receiver, amount_rub, label, description)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::pay_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::topup_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_yoomoney_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 442 | `async _webapp_no_cache_middleware(request, call_next)` | — | — |
| 460 | `_hidden_not_found()` | Как несуществующий URL: стандартный FastAPI 404, без Unauthorized. | `src/shop_bot/webapp/handlers.py::_block_ticket_files_dir`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket_file` |
| 467 | `async _block_ticket_files_dir(rest)` | Каталог ticket_files не является static и не должен открываться по URL. | — |
| 474 | `async api_referral_payout_methods_list(request)` | HTTP-маршрут: `app.post('/api/referral/payout-methods/list')` | — |
| 499 | `async api_referral_payout_methods_add(request)` | HTTP-маршрут: `app.post('/api/referral/payout-methods/add')` | — |
| 527 | `async api_referral_available_method_types(request)` | HTTP-маршрут: `app.post('/api/referral/available-method-types')` | — |
| 557 | `async api_referral_payout_methods_delete(request)` | HTTP-маршрут: `app.post('/api/referral/payout-methods/delete')` | — |
| 579 | `async api_key_auto_renew(request)` | HTTP-маршрут: `app.post('/api/key/auto-renew')` | — |
| 604 | `async api_referral_request_withdraw(request)` | HTTP-маршрут: `app.post('/api/referral/request-withdrawal')` | — |
| 653 | `async api_referral_list_withdrawals(request)` | HTTP-маршрут: `app.post('/api/referral/withdrawals')` | — |
| 687 | `_format_remaining_details(remaining)` | — | `src/shop_bot/webapp/handlers.py::_process_key_data` |
| 711 | `_format_bytes(size)` | — | `src/shop_bot/webapp/handlers.py::_process_key_data` |
| 728 | `_process_template_placeholders(html, user_id, webapp_settings, context_data)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::dynamic_route`<br>`src/shop_bot/webapp/handlers.py::index` |
| 778 | `_format_bytes_gb(num_bytes)` | Тот же формат ГБ, что в карточке ключа бота. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_key_handler`<br>`src/shop_bot/webapp/handlers.py::_lte_card_state` |
| 788 | `_format_gb_amount(size_gb)` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_lte_packages` |
| 796 | `_is_key_without_billing_plan(key_data)` | Триал/подарок: биллингового тарифа нет — докупка LTE недоступна (как в боте). | `src/shop_bot/bot/handlers.py::_resolve_plan_id_for_key`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/webapp/handlers.py::_resolve_plan_id_for_key` |
| 818 | `_resolve_plan_id_for_key(key_data)` | plan_id из description JSON, иначе первый активный тариф хоста (как в боте). | `src/shop_bot/bot/handlers.py::_resolve_plan_for_lte_topup`<br>`src/shop_bot/bot/handlers.py::_resolve_plan_for_traffic_topup`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::main_reset_start_handler`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch`<br>`src/shop_bot/bot/handlers.py::show_key_handler` |
| 845 | `_lte_card_state(key)` | Условия и цифры LTE-пула — те же, что в карточке ключа бота. | `src/shop_bot/webapp/handlers.py::_owned_lte_key_and_plan`<br>`src/shop_bot/webapp/handlers.py::_process_key_data`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_lte_packages` |
| 898 | `_owned_lte_key_and_plan(user_id, key_id)` | Ключ принадлежит user_id и доступен для LTE-докупки. Иначе (None, None). | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_lte_packages` |
| 912 | `_process_key_data(key)` | — | `src/shop_bot/webapp/handlers.py::_get_key_card_html`<br>`src/shop_bot/webapp/handlers.py::_get_key_html`<br>`src/shop_bot/webapp/handlers.py::_get_renew_keys_html`<br>`src/shop_bot/webapp/handlers.py::_get_setup_keys_html`<br>`src/shop_bot/webapp/handlers.py::api_user_status` |
| 1044 | `_get_key_html(key)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 1091 | `_get_profile_card_html(user, referral_count, keys_count, referral_earned)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 1222 | `_get_key_card_html(key, badge_html, extra_content_html)` | Render the full key-card block (used for regular keys and, with an extra | `src/shop_bot/webapp/handlers.py::_get_profile_keys_html`<br>`src/shop_bot/webapp/handlers.py::api_user_gifts` |
| 1353 | `_key_created_sort_tuple(key)` | Sort key for newest-purchased-first: created_at desc, then key_id desc. | — |
| 1367 | `_sort_keys_newest_first(keys)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::api_user_status` |
| 1371 | `_get_profile_keys_html(keys)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::api_keys_search` |
| 1380 | `_get_setup_keys_html(keys)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 1466 | `_get_renew_keys_html(keys, user_id)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 1514 | `_get_no_key_html()` | — | `src/shop_bot/webapp/handlers.py::_get_profile_keys_html`<br>`src/shop_bot/webapp/handlers.py::_get_renew_keys_html`<br>`src/shop_bot/webapp/handlers.py::_get_setup_keys_html`<br>`src/shop_bot/webapp/handlers.py::_render_main_page` |
| 1529 | `_duration_label(months, duration_days)` | — | `src/shop_bot/webapp/handlers.py::_build_plans_grid_html` |
| 1551 | `_days_from_plan(plan)` | — | `src/shop_bot/webapp/handlers.py::_billing_months_for_plan` |
| 1565 | `_billing_months_for_plan(plan)` | — | `src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1569 | `_build_plans_grid_html(host_name, user_id, container_id, display_style)` | — | `src/shop_bot/webapp/handlers.py::_get_renew_keys_html`<br>`src/shop_bot/webapp/handlers.py::_get_servers_and_plans_html` |
| 1640 | `_get_servers_and_plans_html(user_id)` | — | `src/shop_bot/webapp/handlers.py::_process_template_placeholders` |
| 1686 | `_render_banned_page(webapp_settings)` | — | `src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::dynamic_route`<br>`src/shop_bot/webapp/handlers.py::index` |
| 1768 | `async _render_main_page(user_id)` | — | `src/shop_bot/webapp/handlers.py::dynamic_route`<br>`src/shop_bot/webapp/handlers.py::index` |
| 1970 | `async index(request, user_id, token)` | HTTP-маршрут: `app.get('/', response_class=HTMLResponse)` | — |
| 2079 | `_hash_password_reset_code(email, code)` | — | `src/shop_bot/webapp/handlers.py::_password_reset_code_matches`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_request` |
| 2083 | `_password_reset_code_matches(email, code, stored_hash)` | — | `src/shop_bot/webapp/handlers.py::api_email_reset_check`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_verify` |
| 2156 | `validate_telegram_data(init_data, bot_token, max_age_seconds)` | Verify Telegram WebApp initData HMAC and freshness (auth_date). | `src/shop_bot/webapp/handlers.py::_resolve_authenticated_user`<br>`src/shop_bot/webapp/handlers.py::api_create_token`<br>`src/shop_bot/webapp/handlers.py::api_sync_tg`<br>`src/shop_bot/webapp/handlers.py::api_telegram_direct_auth` |
| 2225 | `_issue_persistent_token_for_telegram_user(user_id)` | Shared token issue/lookup used by /api/auth/token and /api/auth/telegram-direct. | `src/shop_bot/webapp/handlers.py::api_create_token` |
| 2244 | `async api_request_auth_token(request)` | HTTP-маршрут: `app.get('/api/auth/request-token')` | — |
| 2259 | `async api_check_auth_token(token, request)` | HTTP-маршрут: `app.get('/api/auth/check-token/{token}')` | — |
| 2301 | `async api_create_token(request, req)` | Generate or retrieve a persistent login token using verified Telegram data. | — |
| 2321 | `async api_telegram_direct_auth(request, req)` | Authenticate inside Telegram WebApp using signed initData only. | — |
| 2356 | `_validate_password(password)` | Проверка пароля при регистрации / сбросе / смене. | `src/shop_bot/webapp/handlers.py::api_email_register`<br>`src/shop_bot/webapp/handlers.py::api_email_reset_verify`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_password` |
| 2381 | `async _issue_email_verification_code(user_id, email)` | Сгенерировать, сохранить и отправить новый код подтверждения email. | `src/shop_bot/webapp/handlers.py::api_email_register`<br>`src/shop_bot/webapp/handlers.py::api_email_resend`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_email_request`<br>`src/shop_bot/webapp/handlers.py::api_user_profile_change_email_resend` |
| 2415 | `async api_email_register(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/register')` | — |
| 2444 | `async api_email_verify(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/verify')` | — |
| 2465 | `async api_email_resend(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/resend')` | — |
| 2492 | `async api_email_login(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/login')` | — |
| 2513 | `async api_email_reset_request(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/reset/request')` | — |
| 2550 | `async api_email_reset_check(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/reset/check')` | — |
| 2570 | `async api_email_reset_verify(request, req)` | HTTP-маршрут: `app.post('/api/auth/email/reset/verify')` | — |
| 2607 | `async api_user_profile_info(request)` | HTTP-маршрут: `app.post('/api/user/profile-info')` | — |
| 2627 | `async api_user_profile_change_password(request)` | HTTP-маршрут: `app.post('/api/user/profile/change-password')` | — |
| 2655 | `async api_user_profile_change_email_request(request)` | HTTP-маршрут: `app.post('/api/user/profile/change-email/request')` | — |
| 2693 | `async api_user_profile_change_email_resend(request)` | HTTP-маршрут: `app.post('/api/user/profile/change-email/resend')` | — |
| 2729 | `async api_user_profile_change_email_verify(request)` | HTTP-маршрут: `app.post('/api/user/profile/change-email/verify')` | — |
| 2753 | `async api_user_profile_change_email_cancel(request)` | HTTP-маршрут: `app.post('/api/user/profile/change-email/cancel')` | — |
| 2769 | `async api_sync_tg(request, req)` | HTTP-маршрут: `app.post('/api/auth/sync-tg')` | — |
| 2797 | `async api_device_tiers(req)` | HTTP-маршрут: `app.post('/api/device-tiers')` | — |
| 2816 | `async api_get_payment_methods(req, request)` | HTTP-маршрут: `app.post('/api/payment-methods')` | — |
| 2876 | `async api_create_payment(req, request)` | HTTP-маршрут: `app.post('/api/create-payment')` | — |
| 3335 | `_rollback_internal_payment(payment_id, user_id, amount, payment_method, plan_id, reason)` | Идемпотентный откат списания Balance/ReferralBalance + лог PAYMENT_ROLLBACK. | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 3374 | `_platega_method_code_from_settings()` | — | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 3390 | `async api_create_topup_payment(req, request)` | Create a balance top-up payment (action=top_up), mirroring the bot TopUpProcess flow. | — |
| 3697 | `_lte_topup_metadata(user_id, key_id, package, payment_method, payment_id, host_name)` | Метаданные те же, что бот кладёт в pending для process_successful_payment. | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 3714 | `async api_lte_packages(request, key_id, token)` | Пакеты докупки LTE для ключа владельца. Цена/размер только с сервера. | — |
| 3749 | `async api_create_lte_topup_payment(req, request)` | Оплата докупки LTE: те же методы, что в боте; цена берётся из пакета в БД. | — |
| 4038 | `async api_apply_promo(req, request)` | Проверить промокод и посчитать цену со скидкой. | — |
| 4091 | `_check_payment_unpaid()` | Нейтральный ответ: неизвестный / чужой / ещё не оплаченный / без токена. | `src/shop_bot/webapp/handlers.py::api_check_payment` |
| 4101 | `async api_check_payment(req, request)` | HTTP-маршрут: `app.post('/api/check-payment')` | — |
| 4148 | `_platega_verify_error(message, status_code)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 4153 | `async api_verify_platega_payment(payment_id, req, request)` | Сверить pending Platega-заказ с GET /transaction/{id} и выдать ключ тем же путём, что webhook. | — |
| 4397 | `async api_user_referral_info(request)` | HTTP-маршрут: `app.post('/api/user/referral-info')` | — |
| 4432 | `_gift_link_row_html(label, link, share_text)` | Одна строка со ссылкой активации подарка: текст ссылки + копировать + поделиться. | `src/shop_bot/webapp/handlers.py::_get_gift_action_block_html` |
| 4451 | `_get_gift_action_block_html(gift_code, webapp_link, telegram_link)` | Общий блок для неактивированного подарка: обе ссылки активации | `src/shop_bot/webapp/handlers.py::api_user_gifts` |
| 4481 | `_get_gift_fallback_card_html(g, badge_html, action_block_html)` | Карточка подарка на случай, если связанный VPN-ключ не найден (например, | `src/shop_bot/webapp/handlers.py::api_user_gifts` |
| 4506 | `async api_user_gifts(request)` | HTTP-маршрут: `app.post('/api/user/gifts')` | — |
| 4568 | `_activate_gift_for_user(user_id, gift_code)` | Активировать подарок `gift_code` для пользователя `user_id`. | `src/shop_bot/webapp/handlers.py::api_gift_activate`<br>`src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 4641 | `async api_gift_activate(req, request)` | HTTP-маршрут: `app.post('/api/gift/activate')` | — |
| 4673 | `_apply_pending_referral(user_id, referrer_id)` | Привязать пользователя к рефереру и, если применимо, выплатить | `src/shop_bot/webapp/handlers.py::api_pending_action_complete` |
| 4719 | `_pending_action_public_info(pending)` | Собрать безопасный (без лишних деталей) ответ для UI по pending action — | `src/shop_bot/webapp/handlers.py::api_pending_action_info` |
| 4763 | `async api_pending_action_info(pending_token)` | HTTP-маршрут: `app.get('/api/webapp/pending-actions/info')` | — |
| 4772 | `async api_pending_action_complete(req, request)` | Единая точка завершения pending action ПОСЛЕ успешной авторизации. | — |
| 4865 | `async api_key_devices(req, request)` | HTTP-маршрут: `app.post('/api/key/devices')` | — |
| 4896 | `async api_key_device_delete(req, request)` | HTTP-маршрут: `app.post('/api/key/device/delete')` | — |
| 4928 | `async api_key_comment(req, request)` | HTTP-маршрут: `app.post('/api/key/comment')` | — |
| 4949 | `_support_rate_response()` | — | `src/shop_bot/webapp/handlers.py::api_support_create`<br>`src/shop_bot/webapp/handlers.py::api_support_send`<br>`src/shop_bot/webapp/handlers.py::api_support_upload` |
| 4956 | `_support_user_rate_limited(user_id, action, limit, window)` | — | `src/shop_bot/webapp/handlers.py::api_support_create`<br>`src/shop_bot/webapp/handlers.py::api_support_send`<br>`src/shop_bot/webapp/handlers.py::api_support_upload` |
| 4969 | `_support_too_fast(user_id, min_interval)` | — | `src/shop_bot/webapp/handlers.py::api_support_send`<br>`src/shop_bot/webapp/handlers.py::api_support_upload` |
| 4982 | `_clip_support_text(value, max_len)` | — | `src/shop_bot/webapp/handlers.py::_notify_webapp_support`<br>`src/shop_bot/webapp/handlers.py::api_support_create`<br>`src/shop_bot/webapp/handlers.py::api_support_send`<br>`src/shop_bot/webapp/handlers.py::api_support_upload` |
| 4986 | `_tickets_created_today_count(tickets)` | — | `src/shop_bot/webapp/handlers.py::api_support_create` |
| 4996 | `_public_ticket_row(ticket)` | — | `src/shop_bot/webapp/handlers.py::api_support_status`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket` |
| 5005 | `_public_ticket_messages(messages)` | — | `src/shop_bot/webapp/handlers.py::api_support_status`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket` |
| 5016 | `_ticket_owned_by(ticket, user_id)` | — | `src/shop_bot/webapp/handlers.py::api_support_close`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket_file`<br>`src/shop_bot/webapp/handlers.py::api_support_upload` |
| 5025 | `async _notify_webapp_support(user_id, ticket, title, body)` | — | `src/shop_bot/webapp/handlers.py::api_support_close`<br>`src/shop_bot/webapp/handlers.py::api_support_create`<br>`src/shop_bot/webapp/handlers.py::api_support_send`<br>`src/shop_bot/webapp/handlers.py::api_support_upload` |
| 5081 | `async api_support_status(req, request)` | HTTP-маршрут: `app.post('/api/support/status')` | — |
| 5117 | `async api_support_create(req, request)` | HTTP-маршрут: `app.post('/api/support/create')` | — |
| 5165 | `async api_support_send(req, request)` | HTTP-маршрут: `app.post('/api/support/send')` | — |
| 5210 | `async api_support_ticket(req, request)` | HTTP-маршрут: `app.post('/api/support/ticket')` | — |
| 5239 | `async api_support_close(req, request)` | HTTP-маршрут: `app.post('/api/support/close')` | — |
| 5272 | `async api_support_ticket_file(message_id, request, token)` | Вложение только владельцу. Без сессии и при чужом id — тот же 404, что у несуществующего URL. | — |
| 5316 | `async api_support_upload(request, file, ticket_id, token, caption, init_data)` | HTTP-маршрут: `app.post('/api/support/upload')` | — |
| 5375 | `async api_user_status(request, token)` | HTTP-маршрут: `app.get('/api/user-status')` | — |
| 5395 | `async api_key_rename(req, request)` | HTTP-маршрут: `app.post('/api/key/rename')` | — |
| 5420 | `async api_key_devices_delete_all(req, request)` | HTTP-маршрут: `app.post('/api/key/devices/delete-all')` | — |
| 5464 | `async api_user_transactions(request, page, per_page, token)` | HTTP-маршрут: `app.get('/api/user/transactions')` | — |
| 5518 | `async api_keys_search(req, request)` | HTTP-маршрут: `app.post('/api/keys/search')` | — |
| 5544 | `_html_esc(value)` | Экранировать значение для вставки в HTML-текст или атрибут (CWE-79). | `src/shop_bot/webapp/handlers.py::_get_key_card_html`<br>`src/shop_bot/webapp/handlers.py::_gift_fallback_html`<br>`src/shop_bot/webapp/handlers.py::_html_telegram_btn`<br>`src/shop_bot/webapp/handlers.py::_referral_fallback_html` |
| 5560 | `_public_fallback_response(content, status_code)` | — | `src/shop_bot/webapp/handlers.py::web_gift_page`<br>`src/shop_bot/webapp/handlers.py::web_referral_page` |
| 5568 | `_parse_public_referrer_id(referrer_id)` | Только положительный int. Невалидный path не должен попадать в HTML/URL. | `src/shop_bot/webapp/handlers.py::web_referral_page` |
| 5579 | `_safe_public_gift_code(gift_code)` | — | `src/shop_bot/webapp/handlers.py::web_gift_page` |
| 5586 | `_telegram_bot_deeplink(bot_username, start_payload)` | — | `src/shop_bot/webapp/handlers.py::web_gift_page`<br>`src/shop_bot/webapp/handlers.py::web_referral_page` |
| 5595 | `_html_telegram_btn(deeplink, label)` | — | `src/shop_bot/webapp/handlers.py::_referral_fallback_html`<br>`src/shop_bot/webapp/handlers.py::web_gift_page` |
| 5601 | `_referral_fallback_html(project_name, logo_url, deeplink, error_note)` | Резервная страница рефссылки (реферер не найден/бот не настроен) — | `src/shop_bot/webapp/handlers.py::web_referral_page` |
| 5634 | `async web_referral_page(referrer_id, request)` | Публичная реферальная ссылка. | — |
| 5679 | `_gift_fallback_html(project_name, logo_url, title, desc, action_html)` | Резервная страница подарка (не найден/уже активирован) — как и раньше, | `src/shop_bot/webapp/handlers.py::web_gift_page` |
| 5706 | `async web_gift_page(gift_code, request)` | Публичная ссылка активации подарка. | — |
| 5773 | `async dynamic_route(request, path_param)` | HTTP-маршрут: `app.get('/{path_param}')` | — |

## src/shop_bot/bot/keyboards.py

Сборщики inline-клавиатур пользователя и админа.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 28 | `_normalize_url(url)` | — | `src/shop_bot/bot/keyboards.py::_get_notifications_support_url`<br>`src/shop_bot/bot/keyboards.py::create_about_keyboard` |
| 40 | `_get_notifications_support_url()` | Support URL for inactive usage reminder notifications (admin-configurable). | `src/shop_bot/bot/keyboards.py::create_inactive_usage_reminder_keyboard` |
| 46 | `_ru_days(n)` | Русское склонение слова "день". | `src/shop_bot/bot/keyboards.py::create_plans_keyboard` |
| 63 | `create_main_menu_keyboard(user_keys, trial_available, is_admin, show_create_bot, show_partner_cabinet, gifts_count)` | — | `src/shop_bot/bot/handlers.py::show_main_menu`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 171 | `create_admin_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_menu`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 189 | `create_admin_system_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_system_menu`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 201 | `create_admin_settings_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_settings_menu`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 221 | `create_admin_lte_settings_keyboard(dual_limit_interval_sec)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_lte_settings_menu` |
| 230 | `create_admin_payments_menu_keyboard(status)` | Меню выбора платежной системы. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_payments_menu` |
| 232 | `_mark(key)` | — | `src/shop_bot/bot/keyboards.py::create_admin_payments_menu_keyboard` |
| 248 | `create_admin_payment_detail_keyboard(provider, flags)` | Клавиатура управления конкретной платежкой. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_payment_detail` |
| 299 | `create_admin_payments_cancel_keyboard(back_callback)` | — | `src/shop_bot/bot/admin_handlers.py::admin_payments_set`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 305 | `create_admin_referral_settings_keyboard(enabled, days_bonus_enabled, reward_type)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_referral_menu` |
| 341 | `create_admin_franchise_settings_keyboard(enabled)` | Создаёт клавиатуру настроек франшизы | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_franchise_menu` |
| 360 | `create_admin_auto_renew_keyboard(enabled)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_auto_renew_menu` |
| 370 | `create_admin_referral_type_keyboard(current_type)` | — | `src/shop_bot/bot/admin_handlers.py::admin_referral_set_type`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 390 | `_host_digest(host_name)` | Safe stable digest for callback_data. | `src/shop_bot/bot/keyboards.py::create_admin_hosts_menu_keyboard` |
| 400 | `create_admin_hosts_menu_keyboard(hosts)` | Hosts list + add button. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_hosts_menu` |
| 421 | `create_admin_host_manage_keyboard(host_digest, node_class)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_detail` |
| 445 | `create_admin_hosts_cancel_keyboard(back_cb)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_add`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_add_api_token`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_add_base_url`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_add_name`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_rename`<br>`src/shop_bot/bot/admin_handlers.py::admin_hosts_set_rmw_token` |
| 452 | `create_admin_hosts_delete_confirm_keyboard(host_digest)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_delete`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 460 | `create_admin_host_squads_keyboard(host_digest, squads)` | Список сквадов хоста с переключением активности и удалением. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_host_squads` |
| 491 | `create_admin_squad_class_keyboard(host_digest)` | — | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad_add`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 502 | `create_admin_trial_settings_keyboard(trial_enabled, days, traffic_text, devices_text, default_host)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_trial_menu` |
| 531 | `create_admin_trial_host_keyboard(hosts)` | — | `src/shop_bot/bot/admin_handlers.py::admin_trial_set_host`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 542 | `create_admin_notifications_settings_keyboard(enabled, interval_hours, support_url)` | Настройки уведомлений о неиспользовании трафика. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_notifications_menu` |
| 571 | `create_admin_plans_host_menu_keyboard(plans)` | Меню тарифов для выбранного хоста (админка). | `src/shop_bot/bot/admin_handlers.py::admin_hosts_to_plans`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_back_to_host_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_pick_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_price_received`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 622 | `create_admin_plan_manage_keyboard(plan)` | — | `src/shop_bot/bot/admin_handlers.py::admin_plan_edit_days_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_devices_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_lte_limit_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_main_reset_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_months_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_name_received` |
| 677 | `create_admin_traffic_packages_keyboard(plan_id, packages, pool)` | — | `src/shop_bot/bot/admin_handlers.py::admin_lte_packages_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_delete`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_packages_menu`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 703 | `create_admin_traffic_package_manage_keyboard(package_id, plan_id, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_price_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_size_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 716 | `create_admin_plans_duration_type_keyboard()` | Выбор единиц срока тарифа при создании. | `src/shop_bot/bot/admin_handlers.py::admin_plans_plan_name_received`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 727 | `create_admin_plan_duration_type_keyboard()` | Выбор единиц срока тарифа при редактировании. | `src/shop_bot/bot/admin_handlers.py::admin_plan_edit_duration`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_months`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 737 | `create_admin_plan_delete_confirm_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_plan_delete_start`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 746 | `create_admin_plan_edit_flow_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_pkg_add_start`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_price_start`<br>`src/shop_bot/bot/admin_handlers.py::admin_pkg_edit_size_start`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_duration_days`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_duration_months`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_edit_days_received` |
| 754 | `create_admin_plans_flow_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_plan_add_days_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_add_devices_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plan_add_traffic_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_add_start`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_months_received`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_new_duration_days` |
| 761 | `create_admins_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_admins_menu_entry`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 770 | `create_admin_users_keyboard(users, page, page_size)` | — | `src/shop_bot/bot/admin_handlers.py::admin_users_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_users_search_process`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 798 | `create_admin_user_actions_keyboard(user_id, is_banned)` | — | `src/shop_bot/bot/admin_handlers.py::admin_ban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_unban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_users_search_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_view_user_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 816 | `create_keys_management_keyboard(keys, page, gift_keys)` | Клавиатура списка ключей пользователя (раздел 'Мои ключи') с пагинацией. | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::cancel_search_keys_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::manage_keys_handler`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process` |
| 866 | `create_sent_gifts_keyboard(gift_keys, page)` | Клавиатура раздела «Отправленные подарки». | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::sent_gifts_handler` |
| 905 | `create_admin_user_keys_keyboard(user_id, keys, page)` | — | `src/shop_bot/bot/admin_handlers.py::admin_key_back`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::admin_user_keys`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 954 | `create_admin_key_actions_keyboard(key_id, user_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_edit_key`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_cancel`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_extend_process`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 966 | `create_admin_delete_key_confirm_keyboard(key_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_delete_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_prompt`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 973 | `create_cancel_keyboard(callback)` | — | `src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_set_interval`<br>`src/shop_bot/bot/admin_handlers.py::admin_inactive_reminder_set_support_url`<br>`src/shop_bot/bot/admin_handlers.py::admin_lte_set_interval_start`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_set_discount`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_set_fixed_amount`<br>`src/shop_bot/bot/admin_handlers.py::admin_referral_set_min_withdrawal` |
| 979 | `create_admin_cancel_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_add_admin_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_balance_pick_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_balance_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_cancel_search_keys_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_deduct_balance_pick_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_deduct_balance_user` |
| 983 | `create_admin_promo_menu_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_promo_menu` |
| 992 | `create_admin_promo_discount_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_code_auto`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_create_code`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1000 | `create_admin_promo_code_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_create_start`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1008 | `create_admin_promo_limit_keyboard(kind)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_set_discount_value`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_set_total_limit`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_total_limit_buttons`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1020 | `create_admin_promo_valid_from_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_user_limit_buttons`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1031 | `create_admin_promo_valid_until_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_set_valid_from`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_valid_from_buttons`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1042 | `create_admin_promo_description_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_set_valid_until`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_valid_until_buttons`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1051 | `create_admin_promo_segment_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_desc_buttons`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_description`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1061 | `create_admin_promo_plans_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_set_segment`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_set_segment_value`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1069 | `create_broadcast_parse_mode_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::broadcast_message_received_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1079 | `create_broadcast_options_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::broadcast_message_received_handler`<br>`src/shop_bot/bot/admin_handlers.py::broadcast_parse_mode_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1087 | `create_broadcast_confirmation_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_broadcast_preview` |
| 1094 | `create_broadcast_cancel_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::add_button_prompt_handler`<br>`src/shop_bot/bot/admin_handlers.py::button_text_received_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::start_broadcast_handler` |
| 1099 | `create_about_keyboard(channel_url, terms_url, privacy_url)` | — | `src/shop_bot/bot/handlers.py::about_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 1114 | `create_support_keyboard(support_user)` | Кнопка техподдержки (всегда ведёт на фиксированный URL). | `src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::handle_deduct_amount`<br>`src/shop_bot/bot/handlers.py::_abort_topup_fulfillment`<br>`src/shop_bot/bot/handlers.py::_notify_user_key_creation_error`<br>`src/shop_bot/bot/handlers.py::about_handler` |
| 1125 | `create_support_bot_link_keyboard(support_bot_username)` | — | `src/shop_bot/bot/handlers.py::about_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::support_close_ticket_handler`<br>`src/shop_bot/bot/handlers.py::support_external_handler`<br>`src/shop_bot/bot/handlers.py::support_menu_handler`<br>`src/shop_bot/bot/handlers.py::support_message_received` |
| 1135 | `create_inactive_usage_reminder_keyboard(connection_string)` | Клавиатура для напоминания, если пользователь не подключил устройство. | `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 1164 | `create_support_menu_keyboard(has_external)` | — | `src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 1174 | `create_tickets_list_keyboard(tickets)` | — | — |
| 1186 | `create_ticket_actions_keyboard(ticket_id, is_open)` | — | — |
| 1195 | `create_host_selection_keyboard(hosts, action)` | — | `src/shop_bot/bot/handlers.py::buy_new_key_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::gift_new_key_handler`<br>`src/shop_bot/bot/handlers.py::switch_server_start`<br>`src/shop_bot/bot/handlers.py::trial_period_handler` |
| 1204 | `create_plans_keyboard(plans, action, host_name, key_id)` | — | `src/shop_bot/bot/handlers.py::back_to_plans_handler`<br>`src/shop_bot/bot/handlers.py::extend_key_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::select_host_for_gift_handler`<br>`src/shop_bot/bot/handlers.py::select_host_for_purchase_handler` |
| 1257 | `create_payment_method_keyboard(payment_methods, action, key_id, show_balance, main_balance, referral_balance, price, promo_applied)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_payment_options` |
| 1269 | `_label(setting_key, fallback)` | — | `src/shop_bot/bot/keyboards.py::create_lte_gb_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_main_reset_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_topup_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_traffic_gb_payment_method_keyboard` |
| 1346 | `create_skip_email_keyboard()` | — | `src/shop_bot/bot/handlers.py::back_to_email_prompt_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::plan_selection_handler` |
| 1353 | `create_stars_invoice_keyboard()` | Кнопки под системной Pay ⭐: сначала Pay (требование Telegram), затем Назад. | `src/shop_bot/bot/handlers.py::create_stars_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 1362 | `create_ton_connect_keyboard(connect_url)` | — | `src/shop_bot/bot/handlers.py::create_ton_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::topup_pay_tonconnect` |
| 1369 | `create_payment_keyboard(payment_url)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_heleket_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_heleket_like`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_heleket_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1376 | `create_yoomoney_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::pay_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::topup_yoomoney_handler`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_yoomoney_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 1384 | `create_yookassa_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::create_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_yookassa_handler`<br>`src/shop_bot/bot/handlers.py::mainreset_pay_yookassa_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_yookassa`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_yookassa_handler` |
| 1392 | `create_platega_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::pay_platega_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_platega`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_platega_handler` |
| 1401 | `create_rollypay_payment_keyboard(payment_url, payment_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::pay_rollypay_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_rollypay`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_rollypay_handler` |
| 1410 | `create_cryptobot_payment_keyboard(payment_url, invoice_id)` | — | `src/shop_bot/bot/handlers.py::create_cryptobot_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_cryptobot_handler`<br>`src/shop_bot/bot/handlers.py::topup_pay_cryptobot`<br>`src/shop_bot/bot/handlers.py::trafficgb_pay_cryptobot_handler`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment` |
| 1418 | `create_topup_payment_method_keyboard(payment_methods)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::topup_amount_input` |
| 1421 | `_label(setting_key, fallback)` | — | `src/shop_bot/bot/keyboards.py::create_lte_gb_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_main_reset_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_topup_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_traffic_gb_payment_method_keyboard` |
| 1466 | `create_traffic_packages_keyboard(key_id, packages)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::traffic_gb_start_handler` |
| 1488 | `create_traffic_gb_payment_method_keyboard(payment_methods)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::traffic_gb_pick_handler` |
| 1491 | `_label(setting_key, fallback)` | — | `src/shop_bot/bot/keyboards.py::create_lte_gb_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_main_reset_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_topup_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_traffic_gb_payment_method_keyboard` |
| 1536 | `create_lte_packages_keyboard(key_id, packages, lte_label)` | Пакеты докупки независимого LTE-пула (premium-ноды 💰). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::lte_gb_start_handler` |
| 1560 | `create_lte_gb_payment_method_keyboard(payment_methods)` | Выбор способа оплаты докупки LTE-пула (полный аналог create_traffic_gb_payment_method_keyboard, | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::lte_gb_pick_handler` |
| 1565 | `_label(setting_key, fallback)` | — | `src/shop_bot/bot/keyboards.py::create_lte_gb_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_main_reset_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_topup_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_traffic_gb_payment_method_keyboard` |
| 1610 | `create_main_reset_payment_method_keyboard(payment_methods)` | Выбор способа оплаты разовой платной перезагрузки основного пула трафика. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::main_reset_start_handler` |
| 1614 | `_label(setting_key, fallback)` | — | `src/shop_bot/bot/keyboards.py::create_lte_gb_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_main_reset_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_topup_payment_method_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_traffic_gb_payment_method_keyboard` |
| 1660 | `create_rename_key_keyboard(key_id, has_name)` | Клавиатура для переименования ключа. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::rename_key_start` |
| 1670 | `create_search_keys_results_keyboard(keys, page)` | Клавиатура с результатами поиска ключей. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::search_keys_input_handler`<br>`src/shop_bot/bot/handlers.py::search_keys_page_handler` |
| 1712 | `create_admin_search_keys_cancel_keyboard()` | Клавиатура для отмены поиска ключей администратором. | `src/shop_bot/bot/admin_handlers.py::admin_search_all_keys_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_search_all_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_search_user_keys_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_search_user_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1718 | `create_admin_search_keys_results_keyboard(keys, page, user_id)` | Клавиатура с результатами поиска ключей (для админа). | `src/shop_bot/bot/admin_handlers.py::admin_search_all_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_search_keys_page_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_search_user_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1763 | `create_gifts_management_keyboard(gifts, page)` | Клавиатура для управления неактивными подарками. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::gifts_page_handler`<br>`src/shop_bot/bot/handlers.py::show_inactive_gifts_handler` |
| 1800 | `create_gift_info_keyboard(gift_id, key_id, is_activated, connection_string, devices_list, gift_link)` | Клавиатура для информации о подарке (как обычный ключ, но без продления). | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::show_gift_handler` |
| 1850 | `create_key_info_keyboard(key_id, connection_string, devices_list, gift_code, gift_id, show_traffic_topup, show_lte_topup, show_main_reset, auto_renew, lte_label)` | — | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation`<br>`src/shop_bot/bot/handlers.py::remove_key_name` |
| 1906 | `create_howto_vless_keyboard()` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::howto_android_handler`<br>`src/shop_bot/bot/handlers.py::howto_android_key_handler`<br>`src/shop_bot/bot/handlers.py::howto_ios_handler`<br>`src/shop_bot/bot/handlers.py::howto_ios_key_handler`<br>`src/shop_bot/bot/handlers.py::howto_linux_handler` |
| 1916 | `create_howto_vless_keyboard_key(key_id)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::howto_android_key_handler`<br>`src/shop_bot/bot/handlers.py::howto_ios_key_handler`<br>`src/shop_bot/bot/handlers.py::howto_linux_key_handler`<br>`src/shop_bot/bot/handlers.py::howto_windows_key_handler`<br>`src/shop_bot/bot/handlers.py::show_instruction_handler` |
| 1926 | `create_back_to_menu_keyboard()` | — | `src/shop_bot/bot/handlers.py::about_handler`<br>`src/shop_bot/bot/handlers.py::back_to_plans_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::gifts_page_handler`<br>`src/shop_bot/bot/handlers.py::lte_gb_start_handler`<br>`src/shop_bot/bot/handlers.py::main_reset_start_handler` |
| 1931 | `create_profile_keyboard(show_notification_toggle, notifications_enabled, gifts_count, auto_renew_any_enabled, show_auto_renew_toggle)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_keyboard` |
| 1955 | `create_welcome_keyboard(channel_url, is_subscription_forced)` | — | `src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 1970 | `get_main_menu_button()` | — | `src/shop_bot/bot/admin_handlers.py::admin_unban_user`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::unban_user_route` |
| 1973 | `get_buy_button()` | — | — |
| 1977 | `create_admin_users_pick_keyboard(users, page, page_size, action)` | — | `src/shop_bot/bot/admin_handlers.py::admin_add_balance_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_add_balance_pick_user_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_deduct_balance_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_deduct_balance_pick_user_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_back_to_users`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_key_entry` |
| 2002 | `create_admin_hosts_pick_keyboard(hosts, action)` | — | `src/shop_bot/bot/admin_handlers.py::admin_gift_back_to_hosts`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_key_for_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_host_keys_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_back_to_hosts`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_page` |
| 2032 | `create_admin_ssh_targets_keyboard(ssh_targets)` | — | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_entry`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_ssh_targets`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2056 | `create_admin_keys_for_host_keyboard(host_name, keys, page, page_size)` | — | `src/shop_bot/bot/admin_handlers.py::admin_host_keys_pick_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_back`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2113 | `create_admin_months_pick_keyboard(action)` | — | — |
| 2122 | `create_dynamic_keyboard(menu_type, user_keys, trial_available, is_admin, show_create_bot, show_partner_cabinet, gifts_count)` | Create a keyboard based on database configuration | `src/shop_bot/bot/keyboards.py::create_dynamic_admin_menu_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_admin_settings_menu_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_admin_system_menu_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_main_menu_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_profile_keyboard`<br>`src/shop_bot/bot/keyboards.py::create_dynamic_support_menu_keyboard` |
| 2442 | `create_dynamic_main_menu_keyboard(user_keys, trial_available, is_admin, show_create_bot, show_partner_cabinet, gifts_count)` | Create main menu keyboard using dynamic configuration | `src/shop_bot/bot/handlers.py::show_main_menu` |
| 2462 | `create_dynamic_admin_menu_keyboard()` | Create admin menu keyboard using dynamic configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_menu` |
| 2465 | `create_dynamic_admin_system_menu_keyboard()` | Create admin system submenu keyboard using dynamic configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_system_menu` |
| 2470 | `create_dynamic_admin_settings_menu_keyboard()` | Create admin settings submenu keyboard using dynamic configuration | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_settings_menu` |
| 2475 | `create_dynamic_profile_keyboard()` | Create profile keyboard using dynamic configuration | — |
| 2479 | `create_dynamic_support_menu_keyboard()` | Create support menu keyboard using dynamic configuration | — |
| 2497 | `create_broadcast_button_type_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::add_button_choose_type`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2505 | `create_broadcast_actions_keyboard()` | — | `src/shop_bot/bot/admin_handlers.py::add_functional_button_start`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 2518 | `create_math_captcha_keyboard()` | Клавиатура для математической капчи с текстовым полем. | `src/shop_bot/bot/handlers.py::show_captcha` |
| 2525 | `create_button_captcha_keyboard(emoji_options)` | Клавиатура для капчи с выбором кнопки (смайлик или текст). | `src/shop_bot/bot/handlers.py::show_captcha` |

## modules/ramadan_tracker/bot_handlers.py

Трекинг практик, баллы, призовой фонд, выплаты.

**Классы:** `WithdrawalStates`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 33 | `async open_ramadan_tracker(message)` | HTTP-маршрут: `router.message(Command('ramadan'))` | — |
| 41 | `async open_ramadan_tracker_callback(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}menu')` | — |
| 49 | `async show_adhkar_menu(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_menu')` | — |
| 56 | `async show_adhkar_morning(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_morning')` | — |
| 63 | `async show_adhkar_evening(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_evening')` | — |
| 70 | `async mark_morning_read(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_morning_read')` | — |
| 79 | `async mark_morning_missed(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_morning_missed')` | — |
| 88 | `async mark_evening_read(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_evening_read')` | — |
| 97 | `async mark_evening_missed(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}adhkar_evening_missed')` | — |
| 106 | `async show_salawat_menu(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}salawat_menu')` | — |
| 113 | `async add_salawat_one(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}salawat_add')` | — |
| 122 | `async show_taraweeh_menu(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}taraweeh_menu')` | — |
| 129 | `async mark_taraweeh_mosque(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}taraweeh_mosque')` | — |
| 138 | `async mark_taraweeh_home(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}taraweeh_home')` | — |
| 147 | `async mark_taraweeh_missed(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}taraweeh_missed')` | — |
| 156 | `async show_today_stats(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}stats_today')` | — |
| 163 | `async show_total_stats(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}stats_total')` | — |
| 170 | `async show_top(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}top')` | — |
| 178 | `async reward_top_user(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}reward')` | — |
| 191 | `async request_withdraw(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}withdraw')` | — |
| 229 | `async show_admin_menu(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}admin_menu')` | `src/shop_bot/bot/admin_handlers.py::admin_add_admin_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_cancel_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days`<br>`src/shop_bot/bot/admin_handlers.py::admin_hostkeys_back_to_users`<br>`src/shop_bot/bot/admin_handlers.py::admin_plans_back_to_admin`<br>`src/shop_bot/bot/admin_handlers.py::admin_remove_admin_process` |
| 239 | `async show_admin_stats(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}admin_stats')` | — |
| 249 | `async show_admin_top(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}admin_top')` | — |
| 259 | `async show_admin_withdrawals(callback)` | HTTP-маршрут: `router.callback_query(F.data == f'{CALLBACK_PREFIX}admin_withdrawals')` | — |
| 269 | `async delete_withdrawal_request(callback)` | HTTP-маршрут: `router.callback_query(F.data.startswith(f'{CALLBACK_PREFIX}delete_withdrawal:'))` | — |
| 292 | `async complete_withdrawal_request(callback, state)` | HTTP-маршрут: `router.callback_query(F.data.startswith(f'{CALLBACK_PREFIX}complete_withdrawal:'))` | — |
| 321 | `async complete_without_proof(callback, state)` | HTTP-маршрут: `router.callback_query(F.data.startswith(f'{CALLBACK_PREFIX}complete_no_proof:'))` | — |
| 341 | `async handle_proof_photo(message, state)` | HTTP-маршрут: `router.message(WithdrawalStates.waiting_proof, F.photo)` | — |
| 370 | `_build_menu_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker_callback`<br>`modules/ramadan_tracker/bot_handlers.py::reward_top_user` |
| 393 | `_build_today_stats_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::show_today_stats` |
| 407 | `_build_total_stats_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::show_total_stats` |
| 419 | `_build_adhkar_menu_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::show_adhkar_menu` |
| 430 | `_build_adhkar_detail_text(user_id, field)` | — | `modules/ramadan_tracker/bot_handlers.py::mark_evening_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_evening_read`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_read`<br>`modules/ramadan_tracker/bot_handlers.py::show_adhkar_evening`<br>`modules/ramadan_tracker/bot_handlers.py::show_adhkar_morning` |
| 438 | `_build_salawat_menu_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::add_salawat_one`<br>`modules/ramadan_tracker/bot_handlers.py::show_salawat_menu` |
| 450 | `_build_taraweeh_menu_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_home`<br>`modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_mosque`<br>`modules/ramadan_tracker/bot_handlers.py::show_taraweeh_menu` |
| 461 | `_build_top_text(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::show_top` |
| 487 | `_build_admin_menu_text()` | — | `modules/ramadan_tracker/bot_handlers.py::show_admin_menu` |
| 491 | `_build_admin_stats_text()` | — | `modules/ramadan_tracker/bot_handlers.py::show_admin_stats` |
| 504 | `_build_admin_top_text()` | — | `modules/ramadan_tracker/bot_handlers.py::show_admin_top` |
| 516 | `_build_admin_withdrawals_text()` | — | `modules/ramadan_tracker/bot_handlers.py::complete_without_proof`<br>`modules/ramadan_tracker/bot_handlers.py::delete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::handle_proof_photo`<br>`modules/ramadan_tracker/bot_handlers.py::show_admin_withdrawals` |
| 534 | `_build_admin_withdrawals_keyboard()` | — | `modules/ramadan_tracker/bot_handlers.py::complete_without_proof`<br>`modules/ramadan_tracker/bot_handlers.py::delete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::handle_proof_photo`<br>`modules/ramadan_tracker/bot_handlers.py::show_admin_withdrawals` |
| 562 | `_build_menu_keyboard(is_admin)` | — | `modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker_callback`<br>`modules/ramadan_tracker/bot_handlers.py::reward_top_user` |
| 577 | `_build_back_keyboard(is_admin)` | — | `modules/ramadan_tracker/bot_handlers.py::show_today_stats`<br>`modules/ramadan_tracker/bot_handlers.py::show_total_stats` |
| 586 | `_build_top_keyboard(is_admin, can_withdraw)` | — | `modules/ramadan_tracker/bot_handlers.py::show_top` |
| 597 | `_build_adhkar_menu_keyboard()` | — | `modules/ramadan_tracker/bot_handlers.py::show_adhkar_menu` |
| 606 | `_build_adhkar_detail_keyboard(period)` | — | `modules/ramadan_tracker/bot_handlers.py::mark_evening_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_evening_read`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_read`<br>`modules/ramadan_tracker/bot_handlers.py::show_adhkar_evening`<br>`modules/ramadan_tracker/bot_handlers.py::show_adhkar_morning` |
| 615 | `_build_salawat_menu_keyboard()` | — | `modules/ramadan_tracker/bot_handlers.py::add_salawat_one`<br>`modules/ramadan_tracker/bot_handlers.py::show_salawat_menu` |
| 623 | `_build_taraweeh_menu_keyboard()` | — | `modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_home`<br>`modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_mosque`<br>`modules/ramadan_tracker/bot_handlers.py::show_taraweeh_menu` |
| 633 | `_build_admin_menu_keyboard()` | — | `modules/ramadan_tracker/bot_handlers.py::show_admin_menu` |
| 643 | `_build_admin_back_keyboard()` | — | `modules/ramadan_tracker/bot_handlers.py::show_admin_stats`<br>`modules/ramadan_tracker/bot_handlers.py::show_admin_top` |
| 650 | `_safe_edit(callback, text, keyboard)` | — | `modules/ramadan_tracker/bot_handlers.py::add_salawat_one`<br>`modules/ramadan_tracker/bot_handlers.py::delete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::mark_evening_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_evening_read`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_read` |
| 665 | `_today_str()` | — | `modules/ramadan_tracker/bot_handlers.py::_add_salawat`<br>`modules/ramadan_tracker/bot_handlers.py::_build_adhkar_detail_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_adhkar_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_salawat_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_taraweeh_menu_text` |
| 669 | `_is_admin(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::complete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::complete_without_proof`<br>`modules/ramadan_tracker/bot_handlers.py::delete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::handle_proof_photo`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker_callback` |
| 673 | `_get_settings()` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::_ensure_auto_payout`<br>`modules/ramadan_tracker/bot_handlers.py::_generate_rewards`<br>`modules/ramadan_tracker/bot_handlers.py::_get_reward_for_user` |
| 677 | `_get(key, default)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings` |
| 690 | `_to_bool(value)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings` |
| 698 | `_to_int(value, default)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings`<br>`src/shop_bot/bot/handlers.py::notify_admin_of_purchase`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics` |
| 705 | `_to_float(value)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings` |
| 712 | `_get_daily_row(user_id, day)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_adhkar_detail_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_adhkar_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_salawat_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_taraweeh_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_today_stats_text` |
| 734 | `_ensure_daily_row(user_id, day)` | — | `modules/ramadan_tracker/bot_handlers.py::_add_salawat`<br>`modules/ramadan_tracker/bot_handlers.py::_get_daily_row`<br>`modules/ramadan_tracker/bot_handlers.py::_set_adhkar_status`<br>`modules/ramadan_tracker/bot_handlers.py::_set_taraweeh` |
| 744 | `_set_adhkar_status(user_id, field, status)` | — | `modules/ramadan_tracker/bot_handlers.py::mark_evening_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_evening_read`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_morning_read` |
| 765 | `_add_salawat(user_id, amount)` | — | `modules/ramadan_tracker/bot_handlers.py::add_salawat_one` |
| 783 | `_set_taraweeh(user_id, place)` | — | `modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_home`<br>`modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_missed`<br>`modules/ramadan_tracker/bot_handlers.py::mark_taraweeh_mosque` |
| 812 | `_get_total_stats(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_salawat_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_total_stats_text` |
| 837 | `_get_global_stats()` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_stats_text`<br>`modules/ramadan_tracker/panel_routes.py::index` |
| 862 | `_get_top_rows(limit)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::_generate_rewards`<br>`modules/ramadan_tracker/panel_routes.py::index` |
| 888 | `_ensure_auto_payout(bot)` | — | `modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker_callback`<br>`modules/ramadan_tracker/bot_handlers.py::request_withdraw`<br>`modules/ramadan_tracker/bot_handlers.py::show_top` |
| 906 | `_generate_rewards(manual, bot)` | — | `modules/ramadan_tracker/bot_handlers.py::_ensure_auto_payout`<br>`modules/ramadan_tracker/bot_handlers.py::reward_top_user` |
| 944 | `_reward_already_given(period_end)` | — | — |
| 954 | `_save_reward(period_end, user_id, amount)` | — | — |
| 967 | `_period_generated(period_end)` | — | `modules/ramadan_tracker/bot_handlers.py::_ensure_auto_payout`<br>`modules/ramadan_tracker/bot_handlers.py::_generate_rewards` |
| 977 | `_save_reward_period(period_end, prize_fund, winners_count)` | — | `modules/ramadan_tracker/bot_handlers.py::_generate_rewards` |
| 991 | `_save_reward_users(period_end, rows, shares, amounts)` | — | `modules/ramadan_tracker/bot_handlers.py::_generate_rewards` |
| 1006 | `_notify_winners(bot, period_end, winners, amounts)` | — | `modules/ramadan_tracker/bot_handlers.py::_generate_rewards` |
| 1035 | `_get_reward_for_user(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::request_withdraw` |
| 1055 | `_get_withdrawal_requests(limit)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_withdrawals_keyboard`<br>`modules/ramadan_tracker/bot_handlers.py::_build_admin_withdrawals_text`<br>`modules/ramadan_tracker/panel_routes.py::payouts` |
| 1074 | `_delete_withdrawal_request(withdrawal_id)` | Удаляет запрос на вывод по ID. | `modules/ramadan_tracker/bot_handlers.py::delete_withdrawal_request` |
| 1089 | `_mark_withdrawal_completed(withdrawal_id, proof_file_id)` | Отмечает запрос на вывод как выполненный с опциональным скриншотом. | `modules/ramadan_tracker/bot_handlers.py::complete_without_proof`<br>`modules/ramadan_tracker/bot_handlers.py::handle_proof_photo` |
| 1104 | `_mark_withdraw_requested(user_id, period_end)` | — | `modules/ramadan_tracker/bot_handlers.py::request_withdraw` |
| 1118 | `_format_taraweeh_place(place)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_taraweeh_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_today_stats_text` |
| 1128 | `_format_adhkar_status(value)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_adhkar_detail_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_adhkar_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_menu_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_today_stats_text` |
| 1136 | `_parse_prize_shares(raw, winners_count)` | — | `modules/ramadan_tracker/bot_handlers.py::_generate_rewards` |
| 1157 | `_allocate_prize_fund(prize_fund, shares)` | — | `modules/ramadan_tracker/bot_handlers.py::_generate_rewards` |
| 1170 | `_build_support_url()` | — | `modules/ramadan_tracker/bot_handlers.py::_notify_winners`<br>`modules/ramadan_tracker/bot_handlers.py::request_withdraw` |
| 1181 | `async _create_withdrawal_ticket(user_id, username, full_name, amount, period_end, bot)` | Создает тикет в support-боте для запроса на вывод выигрыша. | `modules/ramadan_tracker/bot_handlers.py::request_withdraw` |
| 1291 | `_mask_user_id(user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_withdrawals_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_top_text` |

## src/shop_bot/modules/remnawave_api.py

HTTP-клиент Remnawave: ключи, сквады, HWID, LTE-статистика.

**Классы:** `RemnawaveAPIError`, `RemnawavePathUnsupportedError`, `NodeUsage`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 34 | `_detail_is_already_in_desired_state(detail, want_enabled)` | True, если панель ответила, что пользователь уже enable/disable — это успех. | `src/shop_bot/modules/remnawave_api.py::_is_already_in_desired_state`<br>`src/shop_bot/modules/remnawave_api.py::disable_user`<br>`src/shop_bot/modules/remnawave_api.py::enable_user`<br>`src/shop_bot/modules/remnawave_api.py::set_user_status` |
| 47 | `_is_already_in_desired_state(exc, want_enabled)` | — | `src/shop_bot/modules/remnawave_api.py::disable_user`<br>`src/shop_bot/modules/remnawave_api.py::enable_user`<br>`src/shop_bot/modules/remnawave_api.py::set_user_status` |
| 76 | `_inflight_semaphore()` | — | `src/shop_bot/modules/remnawave_api.py::_client_request` |
| 86 | `async _client_request(client, **kwargs)` | Один HTTP-запрос к панели с лимитом параллелизма. | `src/shop_bot/modules/remnawave_api.py::_request`<br>`src/shop_bot/modules/remnawave_api.py::_request_for_host` |
| 103 | `async gather_limited(coros, limit, return_exceptions)` | asyncio.gather с потолком параллелизма — для списка ключей в WebApp. | `src/shop_bot/webapp/handlers.py::_render_main_page` |
| 111 | `async _run(coro)` | — | `src/shop_bot/modules/remnawave_api.py::gather_limited`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bulk_expiry`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_job`<br>`src/shop_bot/webhook_server/app.py::_worker` |
| 118 | `async _get_shared_client(config)` | — | `src/shop_bot/modules/remnawave_api.py::_request`<br>`src/shop_bot/modules/remnawave_api.py::_request_for_host` |
| 147 | `_normalize_email_for_remnawave(email)` | Normalize and validate email for Remnawave API. | `src/shop_bot/modules/remnawave_api.py::ensure_user` |
| 181 | `_normalize_username_for_remnawave(name)` | Normalize username to only letters, numbers, underscores and dashes. | `src/shop_bot/modules/remnawave_api.py::_username_from_email`<br>`src/shop_bot/modules/remnawave_api.py::ensure_user` |
| 208 | `_load_config()` | Backward-compatible global config loader (deprecated). | `src/shop_bot/modules/remnawave_api.py::_load_config_for_host`<br>`src/shop_bot/modules/remnawave_api.py::_request` |
| 219 | `_load_config_for_host(host_name)` | Load Remnawave API config for a specific host from xui_hosts. | `src/shop_bot/modules/remnawave_api.py::_panel_instance_key`<br>`src/shop_bot/modules/remnawave_api.py::_request_for_host` |
| 237 | `_build_headers(config)` | — | `src/shop_bot/modules/remnawave_api.py::_request`<br>`src/shop_bot/modules/remnawave_api.py::_request_for_host` |
| 248 | `async _request(method, path, json_payload, params, expected_status)` | — | `src/shop_bot/modules/platega_api.py::PlategaAPI.create_payment`<br>`src/shop_bot/modules/platega_api.py::PlategaAPI.get_transaction`<br>`src/shop_bot/modules/remnawave_api.py::_get_hwid_devices_by_ref`<br>`src/shop_bot/modules/remnawave_api.py::delete_hwid_device`<br>`src/shop_bot/modules/remnawave_api.py::delete_user`<br>`src/shop_bot/modules/remnawave_api.py::get_bandwidth_stats_nodes_users` |
| 296 | `async _request_for_host(host_name, method, path, json_payload, params, expected_status)` | — | `src/shop_bot/modules/remnawave_api.py::_fetch`<br>`src/shop_bot/modules/remnawave_api.py::_get_hwid_devices_by_ref`<br>`src/shop_bot/modules/remnawave_api.py::_request_optional_path`<br>`src/shop_bot/modules/remnawave_api.py::delete_hwid_device`<br>`src/shop_bot/modules/remnawave_api.py::delete_user_on_host`<br>`src/shop_bot/modules/remnawave_api.py::disable_user` |
| 344 | `_to_iso(dt)` | — | `src/shop_bot/modules/remnawave_api.py::ensure_user`<br>`src/shop_bot/modules/remnawave_api.py::get_bandwidth_stats_nodes_users`<br>`src/shop_bot/modules/remnawave_api.py::get_node_usage_range` |
| 351 | `_extract_user_from_api_payload(payload)` | Normalize Remnawave user lookup payloads (wrapped, list, or bare dict). | `src/shop_bot/modules/remnawave_api.py::get_user_by_email`<br>`src/shop_bot/modules/remnawave_api.py::get_user_by_username`<br>`src/shop_bot/modules/remnawave_api.py::get_user_by_uuid` |
| 366 | `async get_user_by_email(email, host_name)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host`<br>`src/shop_bot/modules/remnawave_api.py::ensure_user`<br>`src/shop_bot/modules/remnawave_api.py::lookup_panel_user`<br>`src/shop_bot/webapp/handlers.py::api_email_login`<br>`src/shop_bot/webapp/handlers.py::api_email_register` |
| 379 | `async get_user_by_username(username, host_name)` | — | `src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/modules/remnawave_api.py::ensure_user`<br>`src/shop_bot/modules/remnawave_api.py::lookup_panel_user` |
| 398 | `_classify_panel_user_ref(user_ref)` | id — числовой userId 3.x; uuid — старый идентификатор 2.x; short — shortUuid. | `src/shop_bot/modules/remnawave_api.py::_panel_hwid_devices_path`<br>`src/shop_bot/modules/remnawave_api.py::_panel_user_get_path`<br>`src/shop_bot/modules/remnawave_api.py::_resolve_hwid_owner`<br>`src/shop_bot/modules/remnawave_api.py::get_hwid_devices_for_user`<br>`src/shop_bot/modules/remnawave_api.py::panel_user_exists` |
| 410 | `_username_from_email(email)` | Локальная часть email → username, как при создании пользователя в панели. | `src/shop_bot/modules/remnawave_api.py::lookup_panel_user`<br>`src/shop_bot/modules/remnawave_api.py::panel_user_exists` |
| 419 | `_panel_numeric_user_id(user)` | Числовой userId 3.x из payload пользователя, если он есть. | `src/shop_bot/modules/remnawave_api.py::_resolve_hwid_owner`<br>`src/shop_bot/modules/remnawave_api.py::get_hwid_devices_for_user`<br>`src/shop_bot/modules/remnawave_api.py::panel_user_ref_from_payload` |
| 432 | `panel_user_ref_from_payload(user)` | Идентификатор для путей `{userId}`: на 3.x это числовой id, на 2.x — uuid. | `src/shop_bot/bot/handlers.py::_get_connected_devices_count`<br>`src/shop_bot/bot/handlers.py::_get_devices_list`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 444 | `_panel_user_get_path(user_ref)` | Путь GET пользователя и допустимые статусы (3.x ждёт число, UUID даёт 400 NaN). | `src/shop_bot/modules/remnawave_api.py::get_user_by_uuid` |
| 457 | `_panel_hwid_devices_path(user_ref)` | GET /api/hwid/devices/{userId}: 3.x ждёт число, UUID даёт 400 NaN. | `src/shop_bot/modules/remnawave_api.py::_get_hwid_devices_by_ref` |
| 469 | `async get_user_by_uuid(user_uuid, host_name)` | — | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/modules/remnawave_api.py::add_squad_to_user`<br>`src/shop_bot/modules/remnawave_api.py::lookup_panel_user`<br>`src/shop_bot/modules/remnawave_api.py::remove_squad_from_user`<br>`src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 483 | `async lookup_panel_user(user_ref, email, host_name)` | Найти пользователя панели: id / uuid / shortUuid, затем email, затем username. | `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`<br>`src/shop_bot/modules/remnawave_api.py::_resolve_hwid_owner`<br>`src/shop_bot/modules/remnawave_api.py::delete_client_on_host` |
| 512 | `async panel_user_exists(user_ref, email, host_name)` | Есть ли пользователь на панели. | `src/shop_bot/bot/handlers.py::_remnawave_key_exists`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 545 | `_extract_hwid_devices_payload(payload)` | — | `src/shop_bot/modules/remnawave_api.py::_get_hwid_devices_by_ref` |
| 556 | `async _get_hwid_devices_by_ref(user_ref, host_name)` | — | `src/shop_bot/modules/remnawave_api.py::get_hwid_devices_for_user` |
| 569 | `async get_hwid_devices_for_user(user_uuid, host_name, email)` | Получить информацию об HWID-устройствах пользователя. | `src/shop_bot/bot/handlers.py::_get_connected_devices_count`<br>`src/shop_bot/bot/handlers.py::_get_devices_list`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`<br>`src/shop_bot/modules/remnawave_api.py::get_connected_devices_count` |
| 616 | `async _resolve_hwid_owner(user_uuid, host_name, user_id, email)` | Числовой userId 3.x и/или uuid 2.x для HWID API. | `src/shop_bot/modules/remnawave_api.py::delete_hwid_device` |
| 640 | `async delete_hwid_device(user_uuid, hwid, host_name, user_id, email)` | Удалить одно HWID-устройство пользователя через API. | `src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/modules/remnawave_api.py::delete_user_device`<br>`src/shop_bot/webhook_server/app.py::admin_key_delete_all_devices_route`<br>`src/shop_bot/webhook_server/app.py::admin_key_delete_device_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 705 | `async get_connected_devices_count(user_uuid, host_name, email)` | Обёртка над get_hwid_devices_for_user для webapp: всегда возвращает | `src/shop_bot/webapp/handlers.py::_render_main_page`<br>`src/shop_bot/webapp/handlers.py::api_key_devices`<br>`src/shop_bot/webapp/handlers.py::api_key_devices_delete_all` |
| 727 | `async delete_user_device(user_uuid, device_id, host_name, email, user_id)` | Алиас delete_hwid_device с именем, ожидаемым webapp/handlers.py. | `src/shop_bot/webapp/handlers.py::api_key_device_delete`<br>`src/shop_bot/webapp/handlers.py::api_key_devices_delete_all` |
| 741 | `async ensure_user(host_name, email, squad_uuid, expire_at, traffic_limit_bytes, traffic_limit_strategy, description, tag, username, hwid_device_limit, …)` | — | `src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host` |
| 924 | `async list_users(host_name, squad_uuid, size, max_pages)` | List users from Remnawave. | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 949 | `_extract_users_from_payload(payload)` | — | `src/shop_bot/modules/remnawave_api.py::_fetch`<br>`src/shop_bot/modules/remnawave_api.py::list_users` |
| 958 | `_filter_by_squad(users)` | — | `src/shop_bot/modules/remnawave_api.py::_append_new`<br>`src/shop_bot/modules/remnawave_api.py::list_users` |
| 977 | `async _fetch(params)` | — | `src/shop_bot/modules/remnawave_api.py::_try_paged`<br>`src/shop_bot/modules/remnawave_api.py::list_users` |
| 1004 | `_uid(u)` | — | `src/shop_bot/modules/remnawave_api.py::_append_new`<br>`src/shop_bot/modules/remnawave_api.py::list_users` |
| 1007 | `_append_new(page_users)` | — | `src/shop_bot/modules/remnawave_api.py::_try_paged`<br>`src/shop_bot/modules/remnawave_api.py::list_users` |
| 1042 | `async _try_paged(start_page)` | Return True if paging seems to work (we got new users). | `src/shop_bot/modules/remnawave_api.py::list_users` |
| 1111 | `async delete_user(user_uuid)` | Глобальный вариант (устарел): удаление без привязки к хосту. | — |
| 1126 | `async delete_user_on_host(host_name, user_uuid)` | Удаление пользователя на конкретном хосте, используя конфиг хоста. | `src/shop_bot/modules/remnawave_api.py::delete_client_on_host` |
| 1139 | `async reset_user_traffic(user_uuid)` | — | `src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 1147 | `async update_user_traffic_limit(user_uuid, new_traffic_limit_bytes, host_name)` | Обновляет лимит трафика (trafficLimitBytes) пользователя в Remnawave. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets`<br>`src/shop_bot/webhook_server/app.py::admin_key_add_traffic_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1160 | `async set_user_status(user_uuid, active)` | — | — |
| 1187 | `_extract_used_traffic_bytes(payload)` | — | `src/shop_bot/modules/remnawave_api.py::get_user_used_traffic` |
| 1199 | `async disable_user(user_uuid, host_name)` | POST /api/users/{uuid}/actions/disable — скрыть ноду (используется для 💰-premium нод при исчерпании LTE | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1230 | `async enable_user(user_uuid, host_name)` | POST /api/users/{uuid}/actions/enable — вернуть доступ пользователю на конкретном хосте. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/webhook_server/app.py::admin_key_add_lte_traffic_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1260 | `async set_user_active_squads(user_uuid, squad_uuids, host_name)` | PATCH /api/users — установить полный список activeInternalSquads пользователя. | `src/shop_bot/modules/remnawave_api.py::add_squad_to_user`<br>`src/shop_bot/modules/remnawave_api.py::remove_squad_from_user` |
| 1290 | `extract_active_squad_uuids(user_payload)` | UUID активных internal-сквадов пользователя из ответа панели. | `src/shop_bot/modules/remnawave_api.py::add_squad_to_user`<br>`src/shop_bot/modules/remnawave_api.py::remove_squad_from_user` |
| 1314 | `async remove_squad_from_user(user_uuid, squad_uuid, host_name)` | Убрать конкретный сквад из activeInternalSquads пользователя, не трогая остальные сквады. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1337 | `async add_squad_to_user(user_uuid, squad_uuid, host_name)` | Добавить конкретный сквад в activeInternalSquads пользователя, не трогая остальные сквады. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/webhook_server/app.py::admin_key_add_lte_traffic_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1356 | `async get_user_used_traffic(user_uuid, host_name, email)` | Использованный трафик (в байтах) пользователя на конкретном инстансе Remnawave. 0, если данных нет. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1377 | `async reset_user_traffic_on_host(user_uuid, host_name)` | POST /api/users/{uuid}/actions/reset-traffic на конкретном инстансе (host-aware вариант reset_user_traffic). | `src/shop_bot/bot/handlers.py::process_successful_payment` |
| 1390 | `_extract_usage_rows(response)` | Достаёт список записей UserUsageDto из ответа Remnawave независимо от обёртки ({"response": [...]}, просто [...]). | `src/shop_bot/modules/remnawave_api.py::get_bandwidth_stats_nodes_users`<br>`src/shop_bot/modules/remnawave_api.py::get_node_usage_range` |
| 1408 | `async get_node_usage_range(node_uuid, start_date, end_date, host_name)` | Legacy per-node usage endpoint: GET /api/nodes/{node_uuid}/usage/range. | `src/shop_bot/modules/remnawave_api.py::get_user_lte_usage_bytes` |
| 1439 | `async get_bandwidth_stats_nodes_users(node_uuids, start_date, end_date, host_name)` | v2.8.0+ endpoint: POST /api/bandwidth-stats/nodes/users. | `src/shop_bot/modules/remnawave_api.py::get_user_lte_usage_bytes` |
| 1472 | `async get_user_lte_usage_bytes(user_uuid, lte_node_uuids, start_date, end_date, host_name)` | Суммарный расход конкретного пользователя по нодам LTE-сквада за период. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1492 | `_sum_for_user(rows)` | — | `src/shop_bot/modules/remnawave_api.py::get_user_lte_usage_bytes` |
| 1557 | `invalidate_squad_nodes_cache(squad_uuid)` | Сбросить кэш нод сквада (целиком или по одному squad_uuid), включая негативный. | `src/shop_bot/modules/remnawave_api.py::refresh_host_squad_overlap` |
| 1569 | `async _request_optional_path(host_name, method, path, params, json_payload)` | Запрос к пути, которого может не быть в этой версии панели. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1600 | `async get_squad_accessible_nodes(squad_uuid, host_name, use_cache)` | Ноды, доступные через internal squad: `GET /api/internal-squads/{uuid}/accessible-nodes`. | `src/shop_bot/modules/remnawave_api.py::get_squad_nodes_for_class` |
| 1638 | `_remember_failure(message)` | — | `src/shop_bot/modules/remnawave_api.py::get_squad_accessible_nodes` |
| 1702 | `async get_squad_nodes_for_class(host_name, squad_class)` | Ноды активного сквада заданного класса ('lte'/'base') у хоста. | `src/shop_bot/modules/remnawave_api.py::get_lte_nodes_for_host`<br>`src/shop_bot/modules/remnawave_api.py::get_squad_node_overlap` |
| 1728 | `async get_lte_nodes_for_host(host_name)` | Ноды активного LTE-сквада хоста (с именами — для карточки ключа и снапшотов). | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/modules/remnawave_api.py::get_lte_node_uuids_for_host`<br>`src/shop_bot/modules/remnawave_api.py::get_squad_node_overlap` |
| 1733 | `async get_lte_node_uuids_for_host(host_name)` | UUID нод активного LTE-сквада хоста. | — |
| 1763 | `_panel_instance_key(host_name)` | Идентификатор инстанса панели (base_url) для кэша поддержки путей. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1771 | `reset_usage_path_cache()` | Сбросить кэш решений о поддерживаемых путях (используется в тестах). | — |
| 1777 | `_usage_path_unsupported(instance_key, path)` | — | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1790 | `_mark_usage_path_unsupported(instance_key, path)` | — | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1801 | `_as_api_date(dt)` | Оба семейства эндпоинтов ждут дату в формате YYYY-MM-DD. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1808 | `_to_int_bytes(value)` | — | `src/shop_bot/modules/remnawave_api.py::_sum_legacy_rows`<br>`src/shop_bot/modules/remnawave_api.py::_sum_squad_scoped_days`<br>`src/shop_bot/modules/remnawave_api.py::_sum_user_series` |
| 1821 | `async resolve_panel_user_id(user_uuid, host_name, user_payload, email)` | Числовой `id` пользователя панели (нужен путям 3.3.2). | `src/shop_bot/modules/remnawave_api.py::_numeric_id`<br>`src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1855 | `_sum_squad_scoped_days(payload, allowed_nodes)` | 3.3.2: `{response: {days: [{date, nodes: [{uuid, totalBytes}]}]}}` -> сумма по нодам. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1869 | `_sum_user_series(payload, allowed_nodes)` | 2.8.1/3.3.2: `{response: {series\|topNodes: [{uuid, total}]}}` -> расход по нодам. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1891 | `_sum_legacy_rows(payload, user_uuid, allowed_nodes)` | 2.8.1 legacy: плоский список `{userUuid, nodeUuid, total, date}` -> расход по нодам. | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 1910 | `async get_user_node_usage_for_squad(user_uuid, host_name, squad_uuid, node_uuids, start_date, end_date, panel_user_id, user_payload, email)` | Расход пользователя по нодам LTE-сквада за период — с разбивкой по нодам. | `src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits` |
| 1970 | `async _numeric_id()` | — | `src/shop_bot/modules/remnawave_api.py::get_user_node_usage_for_squad` |
| 2093 | `async get_squad_node_overlap(host_name)` | Ноды, доступные одновременно через LTE- и base-сквад хоста. | `src/shop_bot/modules/remnawave_api.py::refresh_host_squad_overlap` |
| 2108 | `async refresh_host_squad_overlap(host_name)` | Перепроверить пересечение сквадов хоста и сохранить результат для карточек. | `src/shop_bot/bot/admin_handlers.py::admin_hosts_squad2_label`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::update_host_squad_selection_route` |
| 2130 | `extract_subscription_url(user_payload)` | — | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`<br>`src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host`<br>`src/shop_bot/modules/remnawave_api.py::get_key_details_from_host` |
| 2138 | `async create_or_update_key_on_host(host_name, email, days_to_add, expiry_timestamp_ms, description, tag, traffic_limit_bytes, traffic_limit_strategy, hwid_device_limit, plan_id, …)` | Legacy совместимость: создаёт/обновляет пользователя Remnawave и возвращает данные по ключу. | `src/shop_bot/bot/admin_handlers.py::admin_extend_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_extend_process`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 2274 | `async get_key_details_from_host(key_data)` | — | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch` |
| 2302 | `async delete_client_on_host(host_name, client_email)` | — | `src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch`<br>`src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |

## src/shop_bot/data_manager/remnawave_repository.py

Фасад над database.py + промокоды, ключи, франшизный контекст.

**Классы:** `PromoUnavailableError`, `_PromoTxnAbort`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 16 | `__getattr__(name)` | Модуль-level fallback (PEP 562) для `DB_FILE`. | — |
| 41 | `set_current_factory_bot_id(bot_id)` | Set current factory bot id for the running handler via contextvars. | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__` |
| 52 | `reset_current_factory_bot_id(token)` | — | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__` |
| 59 | `get_current_factory_bot_id()` | — | `src/shop_bot/data_manager/remnawave_repository.py::create_payload_pending` |
| 69 | `PromoUnavailableError.__init__(self, reason)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 74 | `create_payload_pending(payment_id, user_id, amount_rub, metadata)` | Create/update pending payload metadata. | `src/shop_bot/bot/handlers.py::_create_cryptobot_invoice`<br>`src/shop_bot/bot/handlers.py::_create_heleket_payment_request`<br>`src/shop_bot/bot/handlers.py::create_stars_invoice_handler`<br>`src/shop_bot/bot/handlers.py::create_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::ltegb_pay_platega_handler` |
| 121 | `cancel_pending_transaction(payment_id, user_id)` | Отменить неоплаченный pending и освободить слот промокода, если он был зарезервирован. | `src/shop_bot/bot/handlers.py::check_platega_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::check_yookassa_payment_handler`<br>`src/shop_bot/bot/handlers.py::create_stars_invoice_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::payment_stars_back_handler` |
| 132 | `_connect()` | — | `src/shop_bot/data_manager/remnawave_repository.py::_user_paid_total`<br>`src/shop_bot/data_manager/remnawave_repository.py::claim_gift_token`<br>`src/shop_bot/data_manager/remnawave_repository.py::create_gift_token`<br>`src/shop_bot/data_manager/remnawave_repository.py::create_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::delete_gift_token`<br>`src/shop_bot/data_manager/remnawave_repository.py::delete_promo_code` |
| 138 | `_normalize_email(value)` | — | `src/shop_bot/data_manager/database.py::_normalize_key_row`<br>`src/shop_bot/data_manager/database.py::add_new_key`<br>`src/shop_bot/data_manager/database.py::create_user_by_email`<br>`src/shop_bot/data_manager/database.py::delete_key_by_email`<br>`src/shop_bot/data_manager/database.py::get_key_by_email`<br>`src/shop_bot/data_manager/database.py::get_user_by_email` |
| 142 | `_default_expire_at_ms()` | — | `src/shop_bot/data_manager/remnawave_repository.py::record_key` |
| 146 | `_decrypt_host_secrets(row)` | get_squad/list_squads читают xui_hosts напрямую — расшифровать как get_host. | `src/shop_bot/data_manager/remnawave_repository.py::get_squad`<br>`src/shop_bot/data_manager/remnawave_repository.py::list_squads` |
| 153 | `list_squads(active_only)` | — | `src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 165 | `get_squad(identifier)` | — | `src/shop_bot/modules/remnawave_api.py::_load_config_for_host`<br>`src/shop_bot/modules/remnawave_api.py::create_or_update_key_on_host`<br>`src/shop_bot/modules/remnawave_api.py::get_key_details_from_host`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::sweep_expired_keys_route` |
| 190 | `get_key_by_id(key_id)` | — | `src/shop_bot/bot/admin_handlers.py::admin_delete_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_edit_key`<br>`src/shop_bot/bot/admin_handlers.py::admin_extend_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_back`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_cancel`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm` |
| 194 | `get_key_by_email(email)` | — | `src/shop_bot/bot/admin_handlers.py::admin_delete_key_process`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/database.py::update_key_status_from_server`<br>`src/shop_bot/data_manager/remnawave_repository.py::generate_key_email_for_user`<br>`src/shop_bot/data_manager/remnawave_repository.py::record_key`<br>`src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 198 | `get_key_by_remnawave_uuid(remnawave_uuid)` | — | `src/shop_bot/data_manager/remnawave_repository.py::record_key` |
| 202 | `record_key(user_id, squad_uuid, remnawave_user_uuid, email, host_name, expire_at_ms, short_uuid, subscription_url, traffic_limit_bytes, traffic_limit_strategy, …)` | — | `src/shop_bot/data_manager/remnawave_repository.py::record_key_from_payload` |
| 265 | `record_key_from_payload(user_id, payload, host_name, description, tag)` | — | `src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::grant_referrer_day_bonus_for_trial`<br>`src/shop_bot/bot/handlers.py::process_successful_payment` |
| 304 | `update_key(key_id, user_id, host_name, squad_uuid, remnawave_user_uuid, short_uuid, email, subscription_url, expire_at_ms, traffic_limit_bytes, …)` | — | `src/shop_bot/bot/admin_handlers.py::admin_extend_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_key_extend_process`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::_activate_gift_directly`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/remnawave_repository.py::_sync_key_expiry_ms` |
| 343 | `_parse_key_expiry_dt(key)` | Parse key expiry from normalized row (expiry_date / expire_at). | `src/shop_bot/data_manager/remnawave_repository.py::_user_has_active_subscription`<br>`src/shop_bot/data_manager/remnawave_repository.py::extend_key` |
| 366 | `_sync_key_expiry_ms(key_id, new_ms)` | Push expiry to Remnawave, then update local DB. Returns (ok, error, final_ms). | `src/shop_bot/data_manager/remnawave_repository.py::extend_key`<br>`src/shop_bot/data_manager/remnawave_repository.py::set_key_expiry` |
| 403 | `extend_key(key_id, days)` | Продлить/сократить срок ключа на N дней (N может быть отрицательным). | `src/shop_bot/webhook_server/app.py::_apply_bulk_expiry_to_ids`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 426 | `set_key_expiry(key_id, new_expire_at)` | Установить точную дату истечения ключа; синхронизирует Remnawave + БД. | `src/shop_bot/webhook_server/app.py::_apply_bulk_expiry_to_ids`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 463 | `delete_key_by_email(email)` | — | `src/shop_bot/bot/admin_handlers.py::admin_key_delete_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::sync_keys_with_panels` |
| 467 | `generate_key_email_for_user(user_id, domain)` | Generate a unique key email based on Telegram ID + key number. | `src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::_activate_gift_directly`<br>`src/shop_bot/bot/handlers.py::_gift_username_catcher`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment` |
| 759 | `create_gift_token(token, host_name, days, activation_limit, expires_at, created_by, comment)` | — | — |
| 802 | `get_gift_token(token)` | — | — |
| 813 | `list_gift_tokens(active_only)` | — | — |
| 826 | `delete_gift_token(token)` | — | — |
| 837 | `claim_gift_token(token, user_id, key_id)` | — | — |
| 900 | `create_promo_code(code, discount_percent, discount_amount, usage_limit_total, usage_limit_per_user, valid_from, valid_until, created_by, description, applicable_plan_ids, …)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_confirm`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::analytics_coupons_create_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 980 | `get_promo_code(code)` | — | — |
| 991 | `list_promo_codes(include_inactive)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_change_page`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_list`<br>`src/shop_bot/bot/admin_handlers.py::admin_promo_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 1032 | `promo_error_message(reason)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::handle_promo_code_input`<br>`src/shop_bot/webapp/handlers.py::_create_payload_pending_or_error`<br>`src/shop_bot/webapp/handlers.py::api_apply_promo`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1038 | `_serialize_applicable_plan_ids(raw)` | Validate and store plan scope as a JSON array of ints, or NULL = all plans. | `src/shop_bot/data_manager/remnawave_repository.py::create_promo_code` |
| 1074 | `_normalize_promo_segment(segment_type, segment_value)` | — | `src/shop_bot/data_manager/remnawave_repository.py::create_promo_code` |
| 1095 | `_parse_applicable_plan_ids(raw)` | NULL/empty → unrestricted. Invalid JSON → empty list (fail closed). | `src/shop_bot/data_manager/remnawave_repository.py::_promo_targeting_error` |
| 1120 | `_coerce_plan_id(plan_id)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_promo_targeting_error`<br>`src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1129 | `_user_has_active_subscription(user_id)` | True if the user has at least one vpn_keys row with expire_at > now(). | `src/shop_bot/data_manager/remnawave_repository.py::_user_matches_promo_segment` |
| 1143 | `_user_paid_total(user_id, cursor)` | Sum of completed purchases for the user. | `src/shop_bot/data_manager/remnawave_repository.py::_user_matches_promo_segment` |
| 1173 | `_sum(cur)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_user_paid_total` |
| 1189 | `_user_matches_promo_segment(user_id, segment_type, segment_value, cursor)` | Whether the user satisfies an optional promo segment restriction. | `src/shop_bot/data_manager/remnawave_repository.py::_promo_targeting_error` |
| 1214 | `_promo_targeting_error(promo, user_id, plan_id, cursor)` | plan_not_eligible / segment_not_eligible, or None if targeting passes. | `src/shop_bot/data_manager/remnawave_repository.py::_work`<br>`src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1242 | `_PromoTxnAbort.__init__(self, reason)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 1247 | `_connect_promo_write()` | Write connection with BEGIN IMMEDIATE so promo limit updates serialize. | `src/shop_bot/data_manager/remnawave_repository.py::_with_promo_write` |
| 1260 | `_with_promo_write(work, attempts)` | — | `src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::redeem_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::release_promo_reservation`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1298 | `_promo_validity_error(promo, now_dt)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_work`<br>`src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::redeem_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1319 | `_per_user_occupied(cursor, code, user_id)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_work`<br>`src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::redeem_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1339 | `_fetch_promo_row(cursor, code)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_work`<br>`src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::redeem_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1355 | `_atomic_increment_used_total(cursor, code)` | Increment used_total only if the total limit still has a free slot. | `src/shop_bot/data_manager/remnawave_repository.py::_work`<br>`src/shop_bot/data_manager/remnawave_repository.py::redeem_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1372 | `_decrement_used_total(cursor, code)` | — | `src/shop_bot/data_manager/remnawave_repository.py::_work`<br>`src/shop_bot/data_manager/remnawave_repository.py::redeem_promo_code`<br>`src/shop_bot/data_manager/remnawave_repository.py::release_promo_reservation`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1386 | `check_promo_code_available(code, user_id, plan_id)` | Проверить возможность использования промокода, не изменяя лимиты. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::handle_promo_code_input`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::show_payment_options`<br>`src/shop_bot/webapp/handlers.py::api_apply_promo`<br>`src/shop_bot/webapp/handlers.py::api_create_payment` |
| 1412 | `_work(conn)` | — | — |
| 1445 | `reserve_promo_code(code, user_id, payment_id, applied_amount, plan_id)` | Atomically reserve one promo usage slot for a pending payment. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/remnawave_repository.py::create_payload_pending` |
| 1472 | `_work(conn)` | — | — |
| 1541 | `release_promo_reservation(payment_id)` | Free a reserved slot (pending expired/cancelled). Never lets used_total go below 0. | `src/shop_bot/data_manager/remnawave_repository.py::cancel_pending_transaction`<br>`src/shop_bot/data_manager/remnawave_repository.py::create_payload_pending`<br>`src/shop_bot/data_manager/remnawave_repository.py::release_stale_promo_reservations` |
| 1547 | `_work(conn)` | — | — |
| 1582 | `release_stale_promo_reservations(max_age_hours)` | Release reservations older than TTL so abandoned invoices do not hold the limit forever. | `src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/data_manager/remnawave_repository.py::reserve_promo_code` |
| 1611 | `update_promo_code_status(code, is_active)` | — | `src/shop_bot/bot/admin_handlers.py::admin_promo_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/remnawave_repository.py::check_promo_code_available`<br>`src/shop_bot/webhook_server/app.py::_handle_promo_after_payment`<br>`src/shop_bot/webhook_server/app.py::analytics_coupons_toggle_route` |
| 1630 | `delete_promo_code(code)` | — | `src/shop_bot/webhook_server/app.py::analytics_coupons_delete_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1641 | `redeem_promo_code(code, user_id, applied_amount, order_id)` | Confirm a reserved slot (or atomically take one) and record the usage. | `src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/webhook_server/app.py::_handle_promo_after_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 1656 | `_work(conn)` | — | — |
| 1764 | `search_user_keys_by_email(user_id, search_query)` | Поиск ключей пользователя по key_email. | `src/shop_bot/bot/admin_handlers.py::admin_search_user_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::search_keys_input_handler`<br>`src/shop_bot/webapp/handlers.py::api_keys_search` |
| 1769 | `search_all_keys_by_email(search_query)` | Поиск всех ключей (администраторам) по key_email. | `src/shop_bot/bot/admin_handlers.py::admin_search_all_keys_input_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |

## src/shop_bot/core/module_loader.py

Discover/enable/disable/ZIP-импорт плагинов из modules/.

**Классы:** `_LoadedModule`, `ModuleLoader`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 83 | `ModuleLoader.__init__(self, modules_path, db_file)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 94 | `ModuleLoader.set_dispatcher(self, dispatcher)` | Attach aiogram dispatcher for module router registration. | `src/shop_bot/bot_controller.py::BotController.start` |
| 99 | `ModuleLoader.set_flask_app(self, app)` | Attach Flask app for module blueprint registration. | `src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 104 | `ModuleLoader.discover_modules(self)` | Discover module manifests under the modules directory. | `src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.enable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.get_menu_items`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.get_settings_schema`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.import_module_from_zip`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.list_modules` |
| 133 | `ModuleLoader.list_modules(self)` | Return a list of modules with status for UI usage. | `src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_modules_menu`<br>`src/shop_bot/webhook_server/app.py::_get_module_info`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::modules_page` |
| 179 | `ModuleLoader.get_module_status(self, module_id)` | Return current status for a module. | `src/shop_bot/core/module_loader.py::ModuleLoader.enable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.get_menu_items` |
| 190 | `ModuleLoader.load_module(self, module_id)` | Import module code and prepare its hooks. | `src/shop_bot/core/module_loader.py::ModuleLoader.enable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.get_settings_schema` |
| 228 | `ModuleLoader.unload_module(self, module_id)` | Unload module hooks and imported code. | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |
| 243 | `ModuleLoader.enable_module(self, module_id, from_startup)` | Enable a module and register its hooks. | `src/shop_bot/bot/admin_handlers.py::admin_module_enable_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._activate_enabled_modules`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.import_module_from_zip`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_enable_route` |
| 273 | `ModuleLoader.disable_module(self, module_id)` | Disable a module without deleting its data. | `src/shop_bot/bot/admin_handlers.py::admin_module_disable_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.delete_module`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_disable_route` |
| 286 | `ModuleLoader.delete_module(self, module_id)` | Delete a module and remove its data. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_delete_route` |
| 307 | `ModuleLoader.get_menu_items(self)` | Collect panel menu items from enabled modules. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::get_common_template_data`<br>`src/shop_bot/webhook_server/app.py::inject_current_year` |
| 319 | `ModuleLoader.get_settings_schema(self, module_id)` | Return module settings schema if available. | `src/shop_bot/core/module_loader.py::ModuleLoader.get_settings_values`<br>`src/shop_bot/webhook_server/app.py::_build_module_settings_form`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_settings_page` |
| 330 | `ModuleLoader.get_settings_values(self, module_id)` | Return current values for module settings. | `modules/ramadan_tracker/bot_handlers.py::_get_settings`<br>`src/shop_bot/webhook_server/app.py::_build_module_settings_form`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 347 | `ModuleLoader.set_module_error(self, module_id, message)` | Mark module as failed with error message. | `src/shop_bot/core/module_loader.py::ModuleLoader._apply_schema`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.delete_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.load_module`<br>`src/shop_bot/core/module_middleware.py::ModuleSafeMiddleware.__call__` |
| 351 | `ModuleLoader._activate_enabled_modules(self)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.set_dispatcher`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.set_flask_app` |
| 366 | `ModuleLoader._load_manifest(self, module_path)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.discover_modules` |
| 375 | `ModuleLoader._validate_module_meta(self, meta, folder_name)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.discover_modules` |
| 387 | `ModuleLoader._import_from_path(self, file_path, module_name)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._load_blueprint`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._load_cleanup`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._load_manifest`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._load_router`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._load_schema_sql`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._load_settings_schema` |
| 396 | `ModuleLoader._load_router(self, module_id, meta, module_path, names)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.load_module` |
| 411 | `ModuleLoader._load_blueprint(self, module_id, meta, module_path, names)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.load_module` |
| 424 | `ModuleLoader._load_schema_sql(self, meta, module_path, names)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.load_module` |
| 446 | `ModuleLoader._load_cleanup(self, meta, module_path, names)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.load_module` |
| 459 | `ModuleLoader._load_settings_schema(self, meta, module_path, names)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.load_module` |
| 472 | `ModuleLoader._validate_schema(self, module_id, statements)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._load_schema_sql` |
| 480 | `ModuleLoader._apply_schema(self, module_id, statements)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.enable_module` |
| 491 | `ModuleLoader._ensure_settings_defaults(self, module_id, settings)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.enable_module` |
| 514 | `ModuleLoader._delete_settings_prefix(self, module_id)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |
| 519 | `ModuleLoader._attach_router(self, module_id, router)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.enable_module` |
| 540 | `ModuleLoader._detach_router(self, dispatcher, router)` | Detach router from dispatcher. | `src/shop_bot/core/module_loader.py::ModuleLoader.disable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.unload_module` |
| 554 | `ModuleLoader._register_blueprint(self, module_id, blueprint)` | Store blueprint routes in a registry for dynamic dispatch. | `src/shop_bot/core/module_loader.py::ModuleLoader.enable_module` |
| 600 | `ModuleLoader._unregister_blueprint(self, module_id)` | Remove registered blueprint routes from the registry. | `src/shop_bot/core/module_loader.py::ModuleLoader.disable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.unload_module` |
| 608 | `ModuleLoader._get_dependents(self, module_id)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |
| 615 | `ModuleLoader._delete_module_files(self, module_id)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |
| 625 | `ModuleLoader._normalize_zip_member_name(name)` | Normalize a ZIP member path; return None if the name is unsafe. | `src/shop_bot/core/module_loader.py::ModuleLoader.import_module_from_zip` |
| 644 | `ModuleLoader._is_allowed_module_member(cls, relative_path)` | Allow only module source/manifest/assets; reject scripts and binaries. | `src/shop_bot/core/module_loader.py::ModuleLoader.import_module_from_zip` |
| 659 | `ModuleLoader._resolve_extract_path(self, target_root, relative_path)` | Resolve extract destination and ensure it stays under target_root (zip-slip). | `src/shop_bot/core/module_loader.py::ModuleLoader.import_module_from_zip` |
| 677 | `ModuleLoader.import_module_from_zip(self, zip_file_path, auto_enable)` | Import a module from a ZIP file. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::module_upload_route` |
| 826 | `ModuleLoader._upsert_registry(self, meta)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.discover_modules` |
| 843 | `ModuleLoader._insert_registry(self, meta)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._upsert_registry` |
| 856 | `ModuleLoader._delete_registry(self, module_id)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |
| 861 | `ModuleLoader._set_status(self, module_id, status, error_message)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.disable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.discover_modules`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.enable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.set_module_error` |
| 874 | `ModuleLoader._set_module_buttons_active(self, module_id, active)` | Enable or disable buttons associated with a module. | `src/shop_bot/core/module_loader.py::ModuleLoader._activate_enabled_modules`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.disable_module`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.enable_module` |
| 888 | `ModuleLoader._get_registry_row(self, module_id)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._upsert_registry`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.get_module_status` |
| 896 | `ModuleLoader._fetch_registry_rows(self)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._activate_enabled_modules`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.list_modules` |
| 910 | `get_global_module_loader()` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings`<br>`src/shop_bot/bot/admin_handlers.py::admin_module_disable_handler`<br>`src/shop_bot/bot/admin_handlers.py::admin_module_enable_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/admin_handlers.py::show_admin_modules_menu`<br>`src/shop_bot/bot_controller.py::BotController.start` |

## src/shop_bot/data_manager/scheduler.py

Фоновый цикл каждые 5 минут: уведомления, LTE, бэкапы, рассылки, тикеты.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 45 | `format_time_left(hours)` | — | `src/shop_bot/data_manager/scheduler.py::send_subscription_notification` |
| 62 | `async send_subscription_notification(bot, user_id, key_id, time_left_hours, expiry_date)` | — | `src/shop_bot/data_manager/scheduler.py::check_expiring_subscriptions` |
| 86 | `_cleanup_notified_users(all_db_keys)` | — | `src/shop_bot/data_manager/scheduler.py::check_expiring_subscriptions` |
| 113 | `async check_expiring_subscriptions(bot)` | — | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 154 | `_parse_dt_safe(value)` | — | `src/shop_bot/data_manager/scheduler.py::check_auto_renewals`<br>`src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders`<br>`src/shop_bot/data_manager/scheduler.py::check_traffic_boost_resets` |
| 178 | `_extract_used_bytes(payload)` | Пытаемся извлечь использованный трафик из payload пользователя Remnawave (если поле есть). | `src/shop_bot/data_manager/scheduler.py::_legacy_check_traffic_boost_resets`<br>`src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 208 | `_is_true(value)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_get_inactive_reminder_enabled`<br>`src/shop_bot/bot/admin_handlers.py::_get_payments_status_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::_payment_detail_text`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle` |
| 212 | `_get_inactive_usage_reminder_enabled()` | Глобальный переключатель напоминаний о нулевом использовании трафика. | `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 220 | `_get_inactive_usage_reminder_interval_hours()` | Интервал напоминаний в часах (также используется как задержка перед первым напоминанием). | `src/shop_bot/data_manager/scheduler.py::_get_inactive_usage_reminder_interval_seconds` |
| 235 | `_get_inactive_usage_reminder_interval_seconds()` | — | `src/shop_bot/data_manager/scheduler.py::check_inactive_usage_reminders` |
| 239 | `_parse_origin_meta_from_description(description)` | — | `src/shop_bot/data_manager/scheduler.py::_resolve_hwid_device_limit_for_key`<br>`src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 252 | `_try_int(v)` | — | `src/shop_bot/data_manager/scheduler.py::_resolve_hwid_device_limit_for_key`<br>`src/shop_bot/data_manager/scheduler.py::check_auto_renewals`<br>`src/shop_bot/data_manager/scheduler.py::check_device_limit_violations` |
| 270 | `_resolve_hwid_device_limit_for_key(key, remote_user)` | Определить допустимый лимит устройств для ключа. | `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations` |
| 317 | `_extract_device_ids(devices_payload)` | — | `src/shop_bot/data_manager/scheduler.py::check_device_limit_violations` |
| 350 | `async check_device_limit_violations(bot)` | Проверяет превышение лимитов привязанных HWID устройств и уведомляет админов. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 479 | `async check_traffic_boost_resets(bot)` | Ежемесячный сброс трафика ключа до базовых значений тарифа. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 592 | `async enforce_dual_traffic_limits(bot)` | Двухуровневый учёт трафика (основной пул + независимый LTE-пул на premium-нодах). | `src/shop_bot/data_manager/scheduler.py::_maybe_enforce_dual_traffic_limits` |
| 920 | `async _legacy_check_traffic_boost_resets(bot)` | Откатывает докупленный буст трафика после ежемесячного сброса лимита на сервере (устаревшая эвристика, | — |
| 1007 | `async check_inactive_usage_reminders(bot)` | Если после выдачи ключа у пользователя не было подключенных устройств/трафика — напоминать с заданным интервалом. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1103 | `async sync_keys_with_panels()` | — | `src/shop_bot/data_manager/scheduler.py::_maybe_sync_keys_with_panels` |
| 1268 | `async _maybe_sync_keys_with_panels()` | sync_keys_with_panels is expensive (list all users on each host). | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1284 | `async _maybe_enforce_dual_traffic_limits(bot)` | Учёт двух пулов трафика (основной + LTE) — интервал настраивается через bot_settings.dual_limit_interval_sec. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1303 | `async _notify_auto_renew_success(bot, user_id, key_id, price, days_added, key_name)` | — | `src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 1324 | `async _notify_auto_renew_no_balance(bot, user_id, key_id, price, key_name)` | — | `src/shop_bot/data_manager/scheduler.py::check_auto_renewals` |
| 1346 | `async check_auto_renewals(bot)` | — | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1443 | `async check_broadcast_campaigns(bot)` | Send queued broadcast campaigns to inactive subscribers. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1489 | `_ticket_files_present()` | Дешёвая проверка: нет каталога или он пуст — TTL не запускаем. | `src/shop_bot/data_manager/scheduler.py::_maybe_purge_closed_ticket_media` |
| 1501 | `_maybe_purge_closed_ticket_media()` | TTL вложений. Отдельный task не создаём; если файлов нет — сразу выход. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1521 | `_maybe_auto_close_idle_tickets()` | После ответа админа пользователь молчит N дней — закрываем тикет. SQL сразу, Telegram в фоне. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1531 | `async periodic_subscription_check(bot_controller)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services` |
| 1576 | `async _maybe_sync_keys_with_panels()` | Sync with Remnawave panels is expensive; throttle to reduce bot latency. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1588 | `async _maybe_run_periodic_speedtests()` | — | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1599 | `async _run_speedtests_for_all_hosts()` | — | — |
| 1629 | `async _run_speedtests_for_all_ssh_targets()` | — | `src/shop_bot/data_manager/scheduler.py::_maybe_run_periodic_speedtests` |
| 1659 | `async _maybe_collect_resource_metrics(bot)` | Периодический сбор метрик (локально + SSH на хостах) и отправка алертов при превышении порогов. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1681 | `_to_int(s, default)` | — | `modules/ramadan_tracker/bot_handlers.py::_get_settings`<br>`src/shop_bot/bot/handlers.py::notify_admin_of_purchase`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics` |
| 1742 | `async _maybe_run_daily_backup(bot)` | Ежедневный автобэкап базы и отправка админам. Интервал задаётся в настройках backup_interval_days. | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check` |
| 1773 | `async _maybe_alert(bot, scope, name, cpu, mem, disk, cpu_thr, mem_thr, disk_thr, cooldown_sec)` | — | `src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics` |
| 1873 | `async _send_alert(bot, scope, name, issues, level)` | Отправка алерта админам | `src/shop_bot/data_manager/scheduler.py::_maybe_alert` |

## src/shop_bot/support_bot/handlers.py

Тикеты support-бота: DM пользователя ↔ форум админов.

**Классы:** `SupportDialog`, `AdminDialog`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 42 | `get_support_router()` | — | `src/shop_bot/support_bot_controller.py::SupportBotController.start` |
| 45 | `_user_main_reply_kb()` | — | `src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::support_close_ticket_handler`<br>`src/shop_bot/support_bot/handlers.py::support_message_received` |
| 54 | `_is_user_banned(user_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum`<br>`src/shop_bot/support_bot/handlers.py::start_handler`<br>`src/shop_bot/support_bot/handlers.py::support_message_received`<br>`src/shop_bot/support_bot/handlers.py::support_new_ticket_handler`<br>`src/shop_bot/support_bot/handlers.py::support_reply_prompt_handler` |
| 63 | `_get_latest_open_ticket(user_id)` | — | `src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::new_ticket_text_button`<br>`src/shop_bot/support_bot/handlers.py::start_handler`<br>`src/shop_bot/support_bot/handlers.py::start_text_button`<br>`src/shop_bot/support_bot/handlers.py::support_new_ticket_handler` |
| 73 | `_admin_actions_kb(ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::admin_ban_user`<br>`src/shop_bot/support_bot/handlers.py::admin_close_ticket`<br>`src/shop_bot/support_bot/handlers.py::admin_reopen_ticket`<br>`src/shop_bot/support_bot/handlers.py::admin_unban_user`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum` |
| 116 | `async _is_admin(bot, chat_id, user_id)` | — | `modules/ramadan_tracker/bot_handlers.py::complete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::complete_without_proof`<br>`modules/ramadan_tracker/bot_handlers.py::delete_withdrawal_request`<br>`modules/ramadan_tracker/bot_handlers.py::handle_proof_photo`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker`<br>`modules/ramadan_tracker/bot_handlers.py::open_ramadan_tracker_callback` |
| 127 | `async start_handler(message, state, bot)` | HTTP-маршрут: `router.message(CommandStart(), F.chat.type == 'private')` | — |
| 165 | `async support_new_ticket_handler(callback, state)` | HTTP-маршрут: `router.callback_query(F.data == 'support_new_ticket')` | — |
| 190 | `async support_subject_received(message, state)` | HTTP-маршрут: `router.message(SupportDialog.waiting_for_subject, F.chat.type == 'private')` | — |
| 205 | `async _save_ticket_media(bot, message, ticket_id)` | — | `src/shop_bot/support_bot/handlers.py::forum_thread_message_handler`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum`<br>`src/shop_bot/support_bot/handlers.py::support_message_received`<br>`src/shop_bot/support_bot/handlers.py::support_reply_received` |
| 212 | `async support_message_received(message, state, bot)` | HTTP-маршрут: `router.message(SupportDialog.waiting_for_message, F.chat.type == 'private')` | — |
| 322 | `async support_my_tickets_handler(callback)` | HTTP-маршрут: `router.callback_query(F.data == 'support_my_tickets')` | — |
| 339 | `async support_view_ticket_handler(callback)` | HTTP-маршрут: `router.callback_query(F.data.startswith('support_view_'))` | — |
| 372 | `async support_reply_prompt_handler(callback, state)` | HTTP-маршрут: `router.callback_query(F.data.startswith('support_reply_'))` | — |
| 397 | `async support_reply_received(message, state, bot)` | HTTP-маршрут: `router.message(SupportDialog.waiting_for_reply, F.chat.type == 'private')` | — |
| 497 | `async forum_thread_message_handler(message, bot, state)` | HTTP-маршрут: `router.message(F.is_topic_message == True)` | — |
| 567 | `async support_close_ticket_handler(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('support_close_'))` | — |
| 613 | `async admin_close_ticket(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_close_'))` | — |
| 652 | `async admin_reopen_ticket(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_reopen_'))` | — |
| 691 | `async admin_delete_ticket(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_delete_'))` | — |
| 746 | `async admin_toggle_star(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_star_'))` | — |
| 818 | `async admin_show_user(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_user_'))` | — |
| 845 | `_support_contact_markup()` | — | `src/shop_bot/support_bot/handlers.py::_notify_user_about_ban`<br>`src/shop_bot/support_bot/handlers.py::get_support_router`<br>`src/shop_bot/support_bot/handlers.py::relay_user_message_to_forum`<br>`src/shop_bot/support_bot/handlers.py::start_handler`<br>`src/shop_bot/support_bot/handlers.py::support_message_received`<br>`src/shop_bot/support_bot/handlers.py::support_new_ticket_handler` |
| 869 | `async _notify_user_about_ban(bot, user_id, text)` | — | `src/shop_bot/support_bot/handlers.py::admin_ban_user`<br>`src/shop_bot/support_bot/handlers.py::get_support_router` |
| 880 | `async admin_ban_user(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_ban_user_'))` | — |
| 911 | `async admin_unban_user(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_unban_user_'))` | — |
| 945 | `async admin_note_prompt(callback, state, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_note_'))` | — |
| 962 | `async admin_list_notes(callback, bot)` | HTTP-маршрут: `router.callback_query(F.data.startswith('admin_notes_'))` | — |
| 987 | `async admin_note_receive(message, state)` | HTTP-маршрут: `router.message(AdminDialog.waiting_for_note, F.is_topic_message == True)` | — |
| 1008 | `async start_text_button(message, state)` | HTTP-маршрут: `router.message(F.text == '▶️ Начать', F.chat.type == 'private')` | — |
| 1019 | `async new_ticket_text_button(message, state)` | HTTP-маршрут: `router.message(F.text == '✍️ Новое обращение', F.chat.type == 'private')` | — |
| 1030 | `async my_tickets_text_button(message)` | HTTP-маршрут: `router.message(F.text == '📨 Мои обращения', F.chat.type == 'private')` | — |
| 1044 | `async relay_user_message_to_forum(message, bot, state)` | HTTP-маршрут: `router.message(F.chat.type == 'private')` | — |

## src/shop_bot/support_bot/ticket_media.py

Хранение вложений тикетов с квотами и TTL.

**Классы:** `_CappedSeekBuffer`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 41 | `detect_image_kind_bytes(head)` | Расширение и MIME по сигнатуре. None — не jpeg/png/webp/pdf. | `src/shop_bot/support_bot/ticket_media.py::detect_image_kind`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 56 | `detect_image_kind(path)` | — | `src/shop_bot/support_bot/ticket_media.py::commit_ticket_image`<br>`src/shop_bot/webapp/handlers.py::api_support_ticket_file`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_ticket_file` |
| 65 | `media_kind_from_stored(media)` | image \| pdf \| file по имени на диске. Сырой путь наружу не отдаём. | `src/shop_bot/support_bot/ticket_media.py::public_support_message` |
| 79 | `public_support_message(m)` | Поля сообщения для панели/JSON без пути ticket_files. | `src/shop_bot/webapp/handlers.py::_public_ticket_messages`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_ticket_messages_api`<br>`src/shop_bot/webhook_server/app.py::support_ticket_page` |
| 93 | `positive_file_size(file_size)` | Положительный размер в байтах или None, если Telegram его не дал. | `src/shop_bot/support_bot/ticket_media.py::resolve_telegram_file_size` |
| 106 | `async resolve_telegram_file_size(bot, file_id, declared_size)` | Размер до download. Всегда getFile, если бот его умеет. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media` |
| 137 | `_CappedSeekBuffer.__init__(self, max_bytes)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__` |
| 142 | `_CappedSeekBuffer.write(self, b)` | — | `src/shop_bot/app.py::patch_file`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.import_module_from_zip`<br>`src/shop_bot/data_manager/backup_manager.py::create_backup_file`<br>`src/shop_bot/support_bot/ticket_media.py::download_ticket_media_capped`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes`<br>`src/shop_bot/webhook_server/app.py::_find_traefik_dynamic_dir` |
| 154 | `async download_ticket_media_capped(bot, source, part_path, max_bytes)` | Качаем в буфер с seek и потолком 10 МБ, затем на диск. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media` |
| 196 | `declared_size_over_limit(file_size, max_bytes)` | True, если Telegram уже сообщил размер больше лимита. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media` |
| 213 | `ticket_folder_usage(folder)` | Число финальных файлов и их суммарный размер. ``*.part`` не считаем. | `src/shop_bot/support_bot/ticket_media.py::quota_blocks_new_file`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 237 | `quota_blocks_new_file(folder, incoming_bytes, max_files, max_total_bytes)` | True, если ещё одно вложение превысит квоту тикета (10 файлов / 30 МБ). | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 264 | `jailed_ticket_folder(ticket_id, root)` | Каталог вложений тикета строго внутри media root, иначе None. | `src/shop_bot/support_bot/ticket_media.py::delete_ticket_media_dir`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 283 | `closed_ttl_days()` | — | `src/shop_bot/support_bot/ticket_media.py::closed_ticket_media_expired`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 292 | `parse_ticket_updated_at(value)` | — | `src/shop_bot/support_bot/ticket_media.py::closed_ticket_media_expired` |
| 308 | `closed_ticket_media_expired(ticket, now, ttl_days)` | True, если тикет закрыт дольше TTL — файлы пора снять. | `src/shop_bot/support_bot/ticket_media.py::expire_ticket_media_if_closed_ttl`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 325 | `ticket_media_on_disk(root)` | True, если в ticket_files есть хоть одна запись. Без SQL и без полного обхода. | `src/shop_bot/support_bot/ticket_media.py::maybe_purge_expired_closed_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 340 | `expire_ticket_media_if_closed_ttl(ticket_id, now)` | Если тикет закрыт дольше TTL — удаляет файлы и обнуляет media. True = истекло. | `src/shop_bot/webapp/handlers.py::api_support_ticket_file`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::support_ticket_file` |
| 352 | `purge_expired_closed_ticket_media(now, ttl_days)` | Снимает каталоги закрытых тикетов старше TTL и осиротевшие папки. | `src/shop_bot/data_manager/scheduler.py::_maybe_purge_closed_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::maybe_purge_expired_closed_ticket_media` |
| 421 | `maybe_purge_expired_closed_ticket_media()` | Не чаще раза в час. Нет файлов — сразу выход, таймер не заводим. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 437 | `delete_ticket_media_dir(ticket_id)` | Удаляет ``ticket_files/<ticket_id>/``. Не трогает соседние тикеты и корень. | `src/shop_bot/data_manager/database.py::_cleanup_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::expire_ticket_media_if_closed_ttl`<br>`src/shop_bot/support_bot/ticket_media.py::purge_expired_closed_ticket_media` |
| 450 | `commit_ticket_image(part_path, dest_dir, stem)` | Размер + magic. Возвращает ``stem.ext`` или None; ``*.part`` удаляется при отказе. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 487 | `remove_empty_ticket_folder(folder)` | Снимает пустой ``ticket_files/<id>/`` после неудачного save. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 496 | `_unlink_quiet(*paths)` | — | `src/shop_bot/support_bot/ticket_media.py::commit_ticket_image`<br>`src/shop_bot/support_bot/ticket_media.py::download_ticket_media_capped`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media`<br>`src/shop_bot/support_bot/ticket_media.py::save_ticket_media_bytes` |
| 505 | `document_may_be_ticket_media(doc)` | Документ можно скачать: картинка или PDF. Тип всё равно подтвердит magic. | `src/shop_bot/support_bot/ticket_media.py::save_ticket_media` |
| 516 | `save_ticket_media_bytes(payload, ticket_id)` | Сохраняет вложение из WebApp (байты), те же jail/квота/magic, что у бота. | `src/shop_bot/webapp/handlers.py::api_support_upload` |
| 566 | `async save_ticket_media(bot, message, ticket_id)` | Сохраняет изображение из сообщения. Контракт как у прежнего хелпера. | `src/shop_bot/support_bot/handlers.py::_save_ticket_media`<br>`src/shop_bot/support_bot/handlers.py::get_support_router` |

## src/shop_bot/data_manager/speedtest_runner.py

SSH-speedtest и HTTP net-probe хостов.

**Классы:** `StoredHostKeyPolicy`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 24 | `StoredHostKeyPolicy.__init__(self, expected_b64, accept_new, on_save)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 35 | `StoredHostKeyPolicy.missing_host_key(self, client, hostname, key)` | — | — |
| 49 | `_apply_ssh_host_key_policy(ssh, ssh_host, ssh_port, accept_new_host_key)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_run_ssh`<br>`src/shop_bot/data_manager/speedtest_runner.py::_ssh_connect`<br>`src/shop_bot/data_manager/speedtest_runner.py::ssh_speedtest_for_host` |
| 59 | `_save(key_type, key_b64)` | — | — |
| 67 | `_parse_host_port_from_url(url)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_probe_target_error`<br>`src/shop_bot/data_manager/speedtest_runner.py::net_probe_for_host` |
| 83 | `_parse_host_port_from_url(url)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_probe_target_error`<br>`src/shop_bot/data_manager/speedtest_runner.py::net_probe_for_host` |
| 96 | `_is_blocked_probe_ip(ip_obj)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_probe_target_error` |
| 107 | `_probe_target_error(url)` | Return an error string if the probe URL must not be contacted. | `src/shop_bot/data_manager/speedtest_runner.py::net_probe_for_host` |
| 135 | `async net_probe_for_host(host_row)` | Lightweight network probe from panel to host_url: TCP connect + HTTP GET / (HEAD). | `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_net_probe` |
| 203 | `_ssh_exec_json(ssh, commands)` | Try commands sequentially; expect JSON on stdout. Returns (json_obj, error). | `src/shop_bot/data_manager/speedtest_runner.py::_run_ssh`<br>`src/shop_bot/data_manager/speedtest_runner.py::ssh_speedtest_for_host` |
| 229 | `_parse_ookla_json(data)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_run_ssh`<br>`src/shop_bot/data_manager/speedtest_runner.py::ssh_speedtest_for_host` |
| 249 | `_parse_speedtest_cli_json(data)` | — | `src/shop_bot/data_manager/speedtest_runner.py::_run_ssh`<br>`src/shop_bot/data_manager/speedtest_runner.py::ssh_speedtest_for_host` |
| 269 | `async ssh_speedtest_for_host(host_row, accept_new_host_key)` | Run speedtest on remote host via SSH. Tries Ookla CLI first, then speedtest-cli. | `src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest`<br>`src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest_for_target` |
| 294 | `_run_ssh()` | — | — |
| 345 | `async run_and_store_net_probe(host_name)` | — | `src/shop_bot/data_manager/speedtest_runner.py::run_both_for_host`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::run_host_speedtest_route` |
| 365 | `async run_and_store_ssh_speedtest(host_name, accept_new_host_key)` | — | `src/shop_bot/data_manager/speedtest_runner.py::run_both_for_host`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::run_host_speedtest_route` |
| 385 | `async run_both_for_host(host_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_run`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_all`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::_run_speedtests_for_all_hosts`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::run_all_speedtests_route` |
| 410 | `_ssh_connect(host_row, accept_new_host_key)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target`<br>`src/shop_bot/data_manager/speedtest_runner.py::_install`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_host`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_target` |
| 438 | `_ssh_exec(ssh, cmd, timeout)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target`<br>`src/shop_bot/data_manager/speedtest_runner.py::_install`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_host`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_target` |
| 446 | `async auto_install_speedtest_on_host(host_name, accept_new_host_key)` | Attempt to auto-install Ookla speedtest or speedtest-cli on remote host via SSH. | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_autoinstall`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::auto_install_speedtest_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 454 | `_install()` | — | — |
| 593 | `_target_to_host_row(target)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target`<br>`src/shop_bot/data_manager/speedtest_runner.py::_install`<br>`src/shop_bot/data_manager/speedtest_runner.py::auto_install_speedtest_on_target`<br>`src/shop_bot/data_manager/speedtest_runner.py::run_and_store_ssh_speedtest_for_target` |
| 603 | `async run_and_store_ssh_speedtest_for_target(target_name, accept_new_host_key)` | Выполнить SSH-спидтест для отдельной цели (speedtest_ssh_targets) и сохранить результат как host_speedtests с именем цели. | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_all_targets`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_target`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_run_target_hashed`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::_run_speedtests_for_all_ssh_targets`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 625 | `async auto_install_speedtest_on_target(target_name, accept_new_host_key)` | Автоустановка speedtest на отдельной SSH-цели. | `src/shop_bot/bot/admin_handlers.py::admin_speedtest_autoinstall_target`<br>`src/shop_bot/bot/admin_handlers.py::admin_speedtest_autoinstall_target_hashed`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::auto_install_speedtest_on_target_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 631 | `_install()` | — | — |

## src/shop_bot/bot_controller.py

Жизненный цикл основного Telegram-бота: свой event loop, polling, middleware, клоны франшизы.

**Классы:** `BotController`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 28 | `_is_true(value)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_get_inactive_reminder_enabled`<br>`src/shop_bot/bot/admin_handlers.py::_get_payments_status_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::_payment_detail_text`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle` |
| 33 | `BotController.__init__(self)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 47 | `BotController._start_own_loop(self)` | — | `src/shop_bot/bot_controller.py::BotController.__init__`<br>`src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/support_bot_controller.py::SupportBotController.__init__`<br>`src/shop_bot/support_bot_controller.py::SupportBotController.start` |
| 50 | `BotController._runner()` | — | — |
| 70 | `BotController.set_loop(self, loop)` | — | — |
| 76 | `BotController.get_loop(self)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/support_bot/idle_close.py::run_idle_close_followup`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_handle_promo_after_payment` |
| 79 | `BotController.get_bot_instance(self)` | — | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check`<br>`src/shop_bot/support_bot/idle_close.py::run_idle_close_followup`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_handle_promo_after_payment`<br>`src/shop_bot/webhook_server/app.py::_schedule_bulk_ticket_followup` |
| 82 | `async BotController._start_polling(self)` | — | `src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/support_bot_controller.py::SupportBotController.start` |
| 137 | `BotController.start(self)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_escape_md2`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot_controller.py::BotController._start_own_loop`<br>`src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets` |
| 271 | `BotController.stop(self)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::shutdown`<br>`src/shop_bot/webhook_server/app.py::_soft_stop_controller`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::stop_bot_route`<br>`src/shop_bot/webhook_server/app.py::stop_both_bots_route` |
| 284 | `BotController.get_status(self)` | — | `src/shop_bot/__main__.py::_log_bot_status_soon`<br>`src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::shutdown`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/data_manager/scheduler.py::periodic_subscription_check`<br>`src/shop_bot/webhook_server/app.py::_soft_stop_controller` |

## src/shop_bot/factory_bot/service.py

Запуск/остановка клонов франшизы на loop root-бота.

**Классы:** `ManagedBotsService`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 21 | `ManagedBotsService.__init__(self, loop)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 28 | `ManagedBotsService.get_bot(self, bot_id)` | Возвращает экземпляр Bot для bot_id, если он запущен. | — |
| 32 | `ManagedBotsService._drop_bot_refs(self, bot_id)` | — | `src/shop_bot/factory_bot/service.py::ManagedBotsService.runner`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.stop_bot` |
| 37 | `ManagedBotsService._has_running_task(self, bot_id)` | — | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_all`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot` |
| 41 | `async ManagedBotsService.start_all(self)` | — | `src/shop_bot/bot/admin_handlers.py::admin_franchise_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/webhook_server/app.py::_apply_franchise_runtime` |
| 52 | `async ManagedBotsService.start_bot(self, bot_id)` | — | `src/shop_bot/bot/handlers.py::franchise_receive_token`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.restart_bot`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.start_all`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_toggle_bot_route` |
| 83 | `async ManagedBotsService.runner()` | — | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot` |
| 113 | `async ManagedBotsService.stop_bot(self, bot_id)` | Остановить один клон. Идемпотентно: повторный вызов безопасен. | `src/shop_bot/factory_bot/handlers.py::delete_bot_confirm`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.restart_bot`<br>`src/shop_bot/factory_bot/service.py::ManagedBotsService.stop_all`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::franchise_delete_bot_route` |
| 134 | `async ManagedBotsService.restart_bot(self, bot_id)` | Перезапуск клона (смена токена владельцем). | — |
| 139 | `async ManagedBotsService.stop_all(self)` | — | `src/shop_bot/bot/admin_handlers.py::admin_franchise_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot_controller.py::BotController._start_polling`<br>`src/shop_bot/webhook_server/app.py::_apply_franchise_runtime` |

## src/shop_bot/support_bot_controller.py

Жизненный цикл support-бота в отдельном потоке и event loop.

**Классы:** `SupportBotController`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 16 | `SupportBotController.__init__(self)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 28 | `SupportBotController._start_own_loop(self)` | — | `src/shop_bot/bot_controller.py::BotController.__init__`<br>`src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/support_bot_controller.py::SupportBotController.__init__`<br>`src/shop_bot/support_bot_controller.py::SupportBotController.start` |
| 31 | `SupportBotController._runner()` | — | — |
| 49 | `SupportBotController.set_loop(self, loop)` | — | — |
| 54 | `SupportBotController.get_loop(self)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/support_bot/idle_close.py::run_idle_close_followup`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_handle_promo_after_payment` |
| 57 | `SupportBotController.get_bot_instance(self)` | — | `src/shop_bot/data_manager/scheduler.py::periodic_subscription_check`<br>`src/shop_bot/support_bot/idle_close.py::run_idle_close_followup`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_payment_processing`<br>`src/shop_bot/webhook_server/app.py::_handle_promo_after_payment`<br>`src/shop_bot/webhook_server/app.py::_schedule_bulk_ticket_followup` |
| 60 | `async SupportBotController._start_polling(self)` | — | `src/shop_bot/bot_controller.py::BotController.start`<br>`src/shop_bot/support_bot_controller.py::SupportBotController.start` |
| 78 | `SupportBotController.start(self)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_escape_md2`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot_controller.py::BotController._start_own_loop`<br>`src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets` |
| 120 | `SupportBotController.stop(self)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::shutdown`<br>`src/shop_bot/webhook_server/app.py::_soft_stop_controller`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::stop_bot_route`<br>`src/shop_bot/webhook_server/app.py::stop_both_bots_route` |
| 131 | `SupportBotController.get_status(self)` | — | `src/shop_bot/__main__.py::_log_bot_status_soon`<br>`src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::shutdown`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/data_manager/scheduler.py::periodic_subscription_check`<br>`src/shop_bot/webhook_server/app.py::_soft_stop_controller` |

## src/shop_bot/data_manager/captcha_utils.py

Генерация и проверка капчи при регистрации.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 21 | `_now_str()` | — | `src/shop_bot/data_manager/captcha_utils.py::mark_user_passed_captcha`<br>`src/shop_bot/data_manager/database.py::_apply_key_updates`<br>`src/shop_bot/data_manager/database.py::_migrate_subscription_lte_to_keys`<br>`src/shop_bot/data_manager/database.py::activate_user_gift`<br>`src/shop_bot/data_manager/database.py::add_key_lte_boost_bytes`<br>`src/shop_bot/data_manager/database.py::add_lte_boost_bytes` |
| 25 | `_expire_time_str(minutes)` | Возвращает время истечения капчи (через N минут). | `src/shop_bot/data_manager/captcha_utils.py::create_captcha_challenge` |
| 31 | `generate_math_captcha()` | Генерирует математическую задачу и правильный ответ. | `src/shop_bot/data_manager/captcha_utils.py::create_captcha_challenge` |
| 55 | `generate_button_captcha()` | Генерирует капчу с нажатием на кнопку. | `src/shop_bot/data_manager/captcha_utils.py::create_captcha_challenge` |
| 75 | `create_captcha_challenge(user_id, challenge_type, timeout_minutes)` | Создаёт новый капча-вызов для пользователя. | `src/shop_bot/bot/handlers.py::show_captcha` |
| 118 | `check_captcha_answer(challenge_id, user_answer, max_attempts)` | Проверяет ответ на капчу. | `src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |
| 184 | `get_active_captcha_challenge(user_id)` | Получает активный капча-вызов для пользователя. | — |
| 233 | `has_passed_captcha(user_id)` | Проверяет, прошла ли капчу пользователь при регистрации. | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::start_handler` |
| 251 | `mark_user_passed_captcha(user_id, challenge_id)` | Помечает пользователя как прошедшего капчу. | `src/shop_bot/bot/handlers.py::captcha_answer_handler`<br>`src/shop_bot/bot/handlers.py::captcha_button_answer_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |

## src/shop_bot/data_manager/resource_monitor.py

Метрики CPU/RAM/диск локально и по SSH.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 19 | `_safe_percent(numerator, denominator)` | — | `src/shop_bot/data_manager/resource_monitor.py::_parse_free_m` |
| 29 | `get_local_metrics()` | Собрать базовые метрики локальной системы (панели). | `src/shop_bot/bot/admin_handlers.py::admin_monitor_detailed`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::monitor_local_json` |
| 215 | `_parse_free_m(text)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 245 | `_parse_loadavg(text)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 253 | `_parse_df_h(text)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 281 | `_compute_cpu_percent(loadavg, cpu_count)` | — | `src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_host`<br>`src/shop_bot/data_manager/resource_monitor.py::get_remote_metrics_for_target` |
| 294 | `get_remote_metrics_for_host(host_name)` | Собрать базовые метрики по SSH для хоста из xui_hosts. | `src/shop_bot/bot/admin_handlers.py::admin_monitor_host`<br>`src/shop_bot/bot/admin_handlers.py::admin_monitor_local`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_collect_resource_metrics`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::monitor_host_json` |
| 419 | `get_remote_metrics_for_target(target_name)` | — | `src/shop_bot/bot/admin_handlers.py::admin_monitor_target`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::monitor_target_json` |

## modules/ramadan_tracker/panel_routes.py

Страницы статистики и выплат в админке.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 15 | `_get_global_stats()` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_stats_text`<br>`modules/ramadan_tracker/panel_routes.py::index` |
| 40 | `_get_top_rows(limit)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::_build_top_text`<br>`modules/ramadan_tracker/bot_handlers.py::_generate_rewards`<br>`modules/ramadan_tracker/panel_routes.py::index` |
| 66 | `_get_withdrawal_requests(limit)` | — | `modules/ramadan_tracker/bot_handlers.py::_build_admin_withdrawals_keyboard`<br>`modules/ramadan_tracker/bot_handlers.py::_build_admin_withdrawals_text`<br>`modules/ramadan_tracker/panel_routes.py::payouts` |
| 113 | `index()` | HTTP-маршрут: `bp.route('/')` | — |
| 124 | `payouts()` | HTTP-маршрут: `bp.route('/payouts')` | — |
| 133 | `payouts_delete()` | HTTP-маршрут: `bp.route('/payouts/delete', methods=['POST'])` | — |
| 147 | `payouts_complete()` | HTTP-маршрут: `bp.route('/payouts/complete', methods=['POST'])` | — |

## src/shop_bot/__main__.py

Точка входа процесса: логирование, инициализация БД, Flask-поток, автозапуск ботов, планировщик.

**Классы:** `ColoredFormatter`, `RussianizeAiogramFilter`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 20 | `main()` | — | — |
| 37 | `ColoredFormatter.format(self, record)` | — | — |
| 73 | `RussianizeAiogramFilter.filter(self, record)` | — | `src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 121 | `_is_true(value)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services`<br>`src/shop_bot/bot/admin_handlers.py::_get_inactive_reminder_enabled`<br>`src/shop_bot/bot/admin_handlers.py::_get_payments_status_for_admin`<br>`src/shop_bot/bot/admin_handlers.py::_payment_detail_text`<br>`src/shop_bot/bot/admin_handlers.py::admin_auto_renew_toggle` |
| 124 | `async shutdown(sig, loop)` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services` |
| 135 | `async start_services()` | — | `src/shop_bot/__main__.py::main` |
| 193 | `async _log_bot_status_soon()` | — | `src/shop_bot/__main__.py::main`<br>`src/shop_bot/__main__.py::start_services` |

## src/shop_bot/modules/platega_fulfillment.py

Идемпотентное завершение Platega-платежа (webhook + Mini App).

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 18 | `is_platega_payment_method(pending_meta)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 25 | `provider_transaction_id_from_meta(pending_meta)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 33 | `normalize_platega_status(raw)` | — | `src/shop_bot/modules/platega_fulfillment.py::remote_is_canceled`<br>`src/shop_bot/webapp/handlers.py::api_verify_platega_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 42 | `extract_platega_amount(payload)` | — | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |
| 53 | `remote_is_canceled(remote, payment_id)` | True только если API провайдера подтвердил отмену этого счёта. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 66 | `mark_pending_canceled(payment_id, provider_transaction_id)` | Пометить счёт отменённым в pending и в истории транзакций. | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 90 | `complete_pending_platega_payment(payment_id, provider_transaction_id)` | Атомарно закрыть pending и вернуть metadata. | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |

## src/shop_bot/modules/rollypay_api.py

Клиент RollyPay: инвойс, HMAC вебхука, сверка статуса.

**Классы:** `RollyPayAPI`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 27 | `_safe_id(value)` | — | `src/shop_bot/modules/rollypay_api.py::RollyPayAPI.create_payment`<br>`src/shop_bot/modules/rollypay_api.py::RollyPayAPI.get_payment`<br>`src/shop_bot/modules/rollypay_api.py::get_payment_sync` |
| 34 | `verify_webhook_signature(raw_body, timestamp, signature, signing_secret, tolerance, now)` | HMAC-SHA256(`{unix_ts}.{raw_body}`) в заголовке X-Signature, как в SDK RollyPay. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler` |
| 61 | `get_payment_sync(api_key, payment_id, timeout)` | Синхронный GET /payments/{id} для Flask-вебхука. Не доверяем телу колбэка. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::rollypay_webhook_handler` |
| 86 | `RollyPayAPI.__init__(self, api_key, terminal_id)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 90 | `RollyPayAPI._headers(self)` | — | `src/shop_bot/modules/rollypay_api.py::RollyPayAPI.create_payment`<br>`src/shop_bot/modules/rollypay_api.py::RollyPayAPI.get_payment` |
| 98 | `async RollyPayAPI.create_payment(self, amount, description, order_id, success_url, fail_url, payment_method, customer_id)` | Возвращает (pay_url, provider_payment_id) или (None, None). | `src/shop_bot/bot/handlers.py::_create_rollypay_payment_link`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 161 | `async RollyPayAPI.get_payment(self, payment_id)` | — | `src/shop_bot/bot/handlers.py::check_rollypay_payment_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router` |

## src/shop_bot/bot/callback_safety.py

Безопасные ACK/ошибки callback_query для админ-хендлеров.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 14 | `fast_callback_answer(arg)` | Fast ACK for callback queries. | `src/shop_bot/bot/admin_handlers.py::admin_payments_menu`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_open`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_set`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_toggle`<br>`src/shop_bot/bot/admin_handlers.py::admin_payments_yoomoney_check`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router` |
| 26 | `async _ack()` | — | `src/shop_bot/bot/callback_safety.py::fast_callback_answer` |
| 40 | `async wrapper(callback, *args, **kwargs)` | — | — |
| 51 | `catch_callback_errors(func)` | — | — |
| 53 | `async wrapper(callback, *args, **kwargs)` | — | — |
| 67 | `async handle_unknown_callback(callback)` | Telegram-хендлер: `catch_callback_errors` | — |

## src/shop_bot/data_manager/backup_manager.py

Создание, отправка и восстановление ZIP-бэкапа SQLite.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 25 | `_timestamp()` | — | `src/shop_bot/data_manager/backup_manager.py::create_backup_file`<br>`src/shop_bot/data_manager/backup_manager.py::restore_from_file` |
| 29 | `create_backup_file()` | Создаёт zip-архив с консистентной копией SQLite-БД. | `src/shop_bot/bot/admin_handlers.py::admin_backup_db`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/backup_manager.py::restore_from_file`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_run_daily_backup`<br>`src/shop_bot/webhook_server/app.py::backup_db_route`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app` |
| 64 | `cleanup_old_backups(keep)` | Хранить только N последних архивов, остальные удалять. | `src/shop_bot/data_manager/scheduler.py::_maybe_run_daily_backup` |
| 77 | `async send_backup_to_admins(bot, zip_path, request_timeout, max_attempts)` | Отправляет архив всем администраторам. Возвращает число успешных отправок. | `src/shop_bot/bot/admin_handlers.py::admin_backup_db`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::_maybe_run_daily_backup` |
| 139 | `validate_db_file(db_path)` | Простая валидация файла БД: доступность основных таблиц. | `src/shop_bot/data_manager/backup_manager.py::restore_from_file` |
| 162 | `restore_from_file(uploaded_path)` | Восстанавливает основную БД из переданного файла .db или .zip (внутри .db). | `src/shop_bot/bot/admin_handlers.py::admin_restore_db_receive`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::restore_db_route` |

## src/shop_bot/modules/email_sender.py

SMTP-отправка кодов активации для email-регистрации Mini App.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 36 | `_get_service_name()` | Название сервиса для From/Subject писем (не хардкод репозитория). | `src/shop_bot/modules/email_sender.py::send_activation_code` |
| 45 | `_get_smtp_settings()` | — | `src/shop_bot/modules/email_sender.py::is_smtp_configured`<br>`src/shop_bot/modules/email_sender.py::send_activation_code` |
| 67 | `_auth_hint_for_host(host)` | — | `src/shop_bot/modules/email_sender.py::send_activation_code` |
| 75 | `is_smtp_configured()` | Проверить, заполнены ли минимально необходимые настройки SMTP. | `src/shop_bot/webapp/handlers.py::_issue_email_verification_code`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::smtp_test_route` |
| 81 | `_send_once(host, port, settings, to_email, message, connect_timeout)` | — | `src/shop_bot/modules/email_sender.py::send_activation_code` |
| 99 | `send_activation_code(to_email, code, max_attempts, retry_delay_seconds)` | Отправить письмо с одноразовым кодом активации email. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::smtp_test_route` |

## simple_monitor_test.py

Ручной тест мониторинга (вне основного runtime).

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 14 | `test_database()` | Проверяем базу данных | `simple_monitor_test.py::main` |
| 90 | `test_settings()` | Проверяем настройки | `simple_monitor_test.py::main` |
| 117 | `test_metrics_collection()` | Тестируем сбор метрик без psutil | `simple_monitor_test.py::main` |
| 145 | `insert_test_metric()` | Вставляем тестовую метрику | `simple_monitor_test.py::main` |
| 187 | `main()` | Основная функция | — |

## src/shop_bot/bot/photo_helper.py

Утилиты отправки сообщений с картинкой (в runtime почти не подключены).

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 8 | `_default_image_path()` | Returns absolute path to default image (src/shop_bot/img/obla.png). | `src/shop_bot/bot/photo_helper.py::_get_default_photo` |
| 16 | `_get_default_photo()` | — | `src/shop_bot/bot/photo_helper.py::answer_with_image`<br>`src/shop_bot/bot/photo_helper.py::edit_with_image`<br>`src/shop_bot/bot/photo_helper.py::send_with_image` |
| 21 | `async answer_with_image(message, *args, **kwargs)` | Drop-in replacement for message.answer(...), but sends a photo with caption. | — |
| 40 | `async send_with_image(bot, *args, **kwargs)` | Drop-in replacement for bot.send_message(...), but sends a photo with caption. | — |
| 73 | `async edit_with_image(message, *args, **kwargs)` | Replacement for message.edit_text(...). | — |

## src/shop_bot/factory_bot/handlers.py

Кабинет владельца клона: статистика и удаление бота.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 19 | `_parse_bot_id_from_callback(data, prefix)` | — | `src/shop_bot/factory_bot/handlers.py::delete_bot_confirm`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router` |
| 31 | `get_owner_cabinet_router()` | Кабинет владельца текущего клона: просмотр и удаление ЭТОГО бота. | `src/shop_bot/factory_bot/service.py::ManagedBotsService.start_bot` |
| 36 | `async cabinet(cb, bot)` | Telegram-хендлер: `r.callback_query(F.data == 'factory_cabinet')` | — |
| 60 | `async delete_self_ask(cb, bot)` | Telegram-хендлер: `r.callback_query(F.data == 'factory_del_self')` | — |
| 78 | `async delete_bot_confirm(cb)` | Telegram-хендлер: `r.callback_query(F.data.startswith('factory_del_yes:'))` | `src/shop_bot/factory_bot/handlers.py::delete_self_ask`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router` |

## src/shop_bot/modules/platega_api.py

Клиент Platega: создание платежа и сверка статуса.

**Классы:** `PlategaAPI`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 26 | `get_transaction_sync(merchant_id, secret, transaction_id, base_url, timeout)` | Синхронный GET /transaction/{id} для Flask-вебхука. Телу колбэка не доверяем. | `src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::platega_webhook_handler` |
| 71 | `PlategaAPI.__init__(self, merchant_id, secret, base_url)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 76 | `async PlategaAPI._request(self, method, endpoint, json_data)` | — | `src/shop_bot/modules/platega_api.py::PlategaAPI.create_payment`<br>`src/shop_bot/modules/platega_api.py::PlategaAPI.get_transaction`<br>`src/shop_bot/modules/remnawave_api.py::_get_hwid_devices_by_ref`<br>`src/shop_bot/modules/remnawave_api.py::delete_hwid_device`<br>`src/shop_bot/modules/remnawave_api.py::delete_user`<br>`src/shop_bot/modules/remnawave_api.py::get_bandwidth_stats_nodes_users` |
| 101 | `async PlategaAPI.create_payment(self, amount, description, payment_id, return_url, failed_url, method_code)` | Создать платёж в Platega. | `src/shop_bot/bot/handlers.py::_create_rollypay_payment_link`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |
| 131 | `async PlategaAPI.get_transaction(self, transaction_id)` | GET /transaction/{id} — сверка статуса по provider transaction ID. | `src/shop_bot/webapp/handlers.py::api_verify_platega_payment` |

## src/shop_bot/support_bot/idle_close.py

Автозакрытие тикетов по простою после ответа админа.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 18 | `_ru_days_word(n)` | — | `src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets`<br>`src/shop_bot/support_bot/idle_close.py::run_idle_close_followup` |
| 30 | `_forum_wait(loop, coro, timeout)` | — | `src/shop_bot/support_bot/idle_close.py::run_idle_close_followup` |
| 35 | `run_idle_close_followup(tickets, days)` | Темы форума и короткое уведомление пользователю. Не из HTTP-потока. | `src/shop_bot/support_bot/idle_close.py::_run_followup_safe`<br>`src/shop_bot/support_bot/idle_close.py::maybe_auto_close_idle_tickets` |
| 123 | `maybe_auto_close_idle_tickets(now, sync_followup)` | Закрывает пачку простаивающих тикетов. Telegram — в фоне, SQL сразу. | `src/shop_bot/data_manager/scheduler.py::_maybe_auto_close_idle_tickets` |
| 154 | `_run_followup_safe(tickets, days)` | — | — |

## src/shop_bot/config.py

Текстовые шаблоны профиля, статуса VPN и карточки ключа для Telegram-бота.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 9 | `get_profile_text(username, total_spent, total_months, vpn_status_text)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback` |
| 17 | `get_vpn_active_text(days_left, hours_left)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::profile_handler_callback` |
| 23 | `get_key_info_text(key, key_number, devices_connected, plan_group, plan_name, device_limit, gift_code, domain, is_gift_activated, gift_link, …)` | — | `src/shop_bot/bot/handlers.py::cancel_rename_key`<br>`src/shop_bot/bot/handlers.py::delete_device_handler`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::remove_key_name`<br>`src/shop_bot/bot/handlers.py::rename_key_process`<br>`src/shop_bot/bot/handlers.py::select_host_for_switch` |
| 115 | `get_purchase_success_text(action, key_number, expiry_date, connection_string)` | — | `src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/bot/handlers.py::process_successful_payment`<br>`src/shop_bot/bot/handlers.py::process_trial_key_creation` |

## src/shop_bot/core/module_middleware.py

Изоляция ошибок плагинов и whitelist callback_data.

**Классы:** `ModuleSafeMiddleware`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 17 | `ModuleSafeMiddleware.__init__(self, module_id, module_loader)` | — | `src/shop_bot/data_manager/remnawave_repository.py::PromoUnavailableError.__init__`<br>`src/shop_bot/data_manager/remnawave_repository.py::_PromoTxnAbort.__init__`<br>`src/shop_bot/support_bot/ticket_media.py::_CappedSeekBuffer.__init__` |
| 21 | `async ModuleSafeMiddleware.__call__(self, handler, event, data)` | — | — |
| 46 | `ModuleSafeMiddleware._is_allowed_callback(self, event)` | — | `src/shop_bot/core/module_middleware.py::ModuleSafeMiddleware.__call__` |
| 56 | `async ModuleSafeMiddleware._notify_admins(self, event, exc)` | — | `src/shop_bot/core/module_middleware.py::ModuleSafeMiddleware.__call__` |

## src/shop_bot/bot/image_bot.py

Подкласс Bot с авто-вложением картинки (не подключён).

**Классы:** `ImageBot`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 11 | `_pick_image_path()` | Pick an image file from shop_bot/img. | `src/shop_bot/bot/image_bot.py::ImageBot.send_message` |
| 29 | `_filter_kwargs(func, kwargs)` | Keep only kwargs that func(...) accepts (defensive for aiogram version differences). | `src/shop_bot/bot/image_bot.py::ImageBot.send_message` |
| 45 | `async ImageBot.send_message(self, chat_id, text, *args, **kwargs)` | — | `modules/ramadan_tracker/bot_handlers.py::_create_withdrawal_ticket`<br>`modules/ramadan_tracker/bot_handlers.py::_notify_winners`<br>`src/shop_bot/bot/admin_handlers.py::_send_broadcast_to`<br>`src/shop_bot/bot/admin_handlers.py::admin_ban_user`<br>`src/shop_bot/bot/admin_handlers.py::admin_extend_key_process`<br>`src/shop_bot/bot/admin_handlers.py::admin_gift_pick_days` |

## src/shop_bot/core/module_types.py

Типы манифеста модуля (ModuleMeta, ModuleStatus).

**Классы:** `ModuleStatus`, `ModuleMeta`, `ModuleInfo`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 35 | `ModuleMeta.from_dict(cls, data)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._load_manifest` |
| 51 | `ModuleMeta.to_dict(self)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._insert_registry`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._upsert_registry`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.list_modules`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::debug_all_requests`<br>`src/shop_bot/webhook_server/app.py::test_webhook` |
| 79 | `ModuleInfo.to_dict(self)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader._insert_registry`<br>`src/shop_bot/core/module_loader.py::ModuleLoader._upsert_registry`<br>`src/shop_bot/core/module_loader.py::ModuleLoader.list_modules`<br>`src/shop_bot/webhook_server/app.py::create_webhook_app`<br>`src/shop_bot/webhook_server/app.py::debug_all_requests`<br>`src/shop_bot/webhook_server/app.py::test_webhook` |

## src/shop_bot/factory_bot/middleware.py

Статистика клонов и кэш franchise_enabled.

**Классы:** `FactoryStatsMiddleware`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 13 | `invalidate_franchise_enabled_cache()` | — | `src/shop_bot/webhook_server/app.py::_apply_franchise_runtime` |
| 18 | `franchise_enabled_cached()` | Лёгкий кэш флага франшизы, чтобы middleware не ходила в SQL на каждое сообщение. | `src/shop_bot/factory_bot/middleware.py::FactoryStatsMiddleware.__call__` |
| 37 | `async FactoryStatsMiddleware.__call__(self, handler, event, data)` | — | — |

## simple_collect.py

Вспомогательный сбор метрик (вне основного runtime).

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 13 | `collect_metrics_simple()` | Простой сбор метрик | `simple_collect.py::main` |
| 93 | `main()` | Основная функция | — |

## src/shop_bot/app.py

Одноразовый hotfix-скрипт для патча webhook_server/app.py (не часть runtime).

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 14 | `patch_file(path)` | — | — |
| 33 | `ensure_flag_in_list(src, list_name_pattern)` | — | `src/shop_bot/app.py::patch_file` |

## src/shop_bot/factory_bot/keyboards.py

Клавиатуры кабинета владельца клона.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 4 | `cabinet_menu()` | — | `src/shop_bot/factory_bot/handlers.py::cabinet`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router` |
| 12 | `delete_bot_confirm(bot_id)` | — | `src/shop_bot/factory_bot/handlers.py::delete_self_ask`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router` |

## src/shop_bot/factory_bot/runtime.py

Глобальный singleton ManagedBotsService.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 7 | `set_service(service)` | — | `src/shop_bot/bot_controller.py::BotController.start` |
| 11 | `get_service()` | — | `src/shop_bot/bot/admin_handlers.py::admin_franchise_toggle`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/bot/handlers.py::franchise_receive_token`<br>`src/shop_bot/bot/handlers.py::get_user_router`<br>`src/shop_bot/factory_bot/handlers.py::delete_bot_confirm`<br>`src/shop_bot/factory_bot/handlers.py::get_owner_cabinet_router` |

## src/shop_bot/modules/telegram_reachability.py

Классификация 403 Telegram и пометка пользователя unreachable.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 30 | `classify_unreachable_error(exc)` | Определить, означает ли ошибка отправки недоступность пользователя в Telegram. | `src/shop_bot/modules/telegram_reachability.py::handle_send_exception` |
| 49 | `handle_send_exception(user_id, exc)` | Проверить ошибку отправки сообщения пользователю и, если она означает | `src/shop_bot/bot/admin_handlers.py::confirm_broadcast_handler`<br>`src/shop_bot/bot/admin_handlers.py::get_admin_router`<br>`src/shop_bot/data_manager/scheduler.py::check_broadcast_campaigns`<br>`src/shop_bot/data_manager/scheduler.py::enforce_dual_traffic_limits`<br>`src/shop_bot/data_manager/scheduler.py::send_subscription_notification`<br>`src/shop_bot/webhook_server/app.py::_dispatch_bot_notification` |

## modules/example_module/bot_handlers.py

Пример Telegram-хендлеров модуля.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 7 | `async example_ping(callback)` | HTTP-маршрут: `router.callback_query(F.data == 'mod:example_module:ping')` | — |

## modules/example_module/db_cleanup.py

Пример cleanup модуля.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 1 | `cleanup(db_conn)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |

## modules/example_module/panel_routes.py

Пример Flask-blueprint модуля.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 12 | `index()` | HTTP-маршрут: `bp.route('/')` | — |

## modules/ramadan_tracker/db_cleanup.py

DROP таблиц модуля при удалении.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 1 | `cleanup(db_conn)` | — | `src/shop_bot/core/module_loader.py::ModuleLoader.delete_module` |

## modules/ramadan_tracker/db_schema.py

Таблицы ramadan_tracker_*.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 5 | `SCHEMA_SQL()` | Генерирует SQL схему и автоматически выполняет миграции. | — |

## src/shop_bot/bot/middlewares.py

BanMiddleware — блокировка забаненных и сброс флага unreachable.

**Классы:** `BanMiddleware`

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 8 | `async BanMiddleware.__call__(self, handler, event, data)` | — | — |

## src/shop_bot/modules/cryptobot_api.py

Клиент Crypto Pay; основной бот дублирует логику в handlers.py.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 23 | `async create_cryptobot_api_invoice(amount, payload_str)` | Создать инвойс в Crypto Pay (CryptoBot) в фиате RUB. | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |

## src/shop_bot/modules/heleket_api.py

Клиент Heleket: создание крипто-инвойса.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 26 | `async create_heleket_payment_request(amount, currency, description, return_url, user_id, email, order_id)` | Создать инвойс в Heleket. | `src/shop_bot/webapp/handlers.py::api_create_lte_topup_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_payment`<br>`src/shop_bot/webapp/handlers.py::api_create_topup_payment` |

## src/shop_bot/webhook_server/apply_app_fix.py

Утилита regex-патча настроек в app.py.

| Строка | Сигнатура | Назначение | Кто вызывает (по имени) |
|------:|-----------|------------|-------------------------|
| 13 | `normalize_list(block, must_have)` | — | — |
