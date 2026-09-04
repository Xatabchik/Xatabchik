# Карта разделения `data_manager/database.py`

Файл разделён на доменные модули подпакета `src/shop_bot/data_manager/db/`.
Код функций перенесён 1:1, без правок тел. `database.py` остался фасадом и
ре-экспортирует прежний публичный API целиком, поэтому все вызывающие
(`from shop_bot.data_manager.database import ...`, `database.DB_FILE`,
`getattr(database, name)`) не изменились.


Столбец «строки» — расположение в исходном `database.py` до разделения
(11 806 строк), чтобы можно было сверить перенос с `INVENTORY.md` и
документацией в `shop_bot_data_manager_database_part*.md`.


## Сводка

| Модуль | Назначение | Функций | Констант |
| --- | --- | --- | --- |
| `db/payments.py` | Платежи, транзакции, инвойсы, pending actions | 45 | 5 |
| `db/keys.py` | VPN-ключи, срок действия, трафик | 44 | 0 |
| `db/referral.py` | Реферальная программа | 26 | 11 |
| `db/franchise.py` | Франшиза, клоны бота, кабинет партнёра, выводы | 33 | 4 |
| `db/tickets.py` | Поддержка: тикеты, сообщения, вложения | 29 | 4 |
| `db/lte.py` | LTE-хосты и squad'ы | 29 | 3 |
| `db/_core.py` | Инфраструктура: DB_FILE, логгер, retry, помощники дат/JSON, settings, шифрование токена | 19 | 12 |
| `db/hosts.py` | Хосты и панели (3x-ui, Remnawave) | 28 | 0 |
| `db/schema.py` | Создание и миграции схемы | 28 | 0 |
| `db/users.py` | Пользователи, баланс, бан, UTM, настройки уведомлений | 28 | 0 |
| `db/analytics.py` | Метрики, выручка, экономика, затраты | 24 | 0 |
| `db/plans.py` | Тарифы, пакеты трафика, уровни устройств | 18 | 0 |
| `db/captcha_auth.py` | Captcha, коды email, auth-токены, webapp-авторизация | 18 | 0 |
| `db/buttons.py` | Кнопки интерфейса | 14 | 0 |
| `db/gifts.py` | Подарочные подписки | 13 | 0 |
| `db/broadcasts.py` | Рассылки | 9 | 0 |
| `db/ssh_targets.py` | SSH-цели | 6 | 0 |
| `db/promo.py` | Промокоды (форматирование подписей) | 2 | 0 |
| **итого** | | **413** | **39** |

## Заметки о переносе

### Отклонение от согласованного списка файлов

В плане было 17 модулей. Добавлен 18-й — `db/broadcasts.py`: девять функций
рассылок (`create_broadcast_campaign`, `get_inactive_subscribers`,
`record_broadcast_sends` и др.) образуют самостоятельную ответственность и в
`users.py` попали бы только по остаточному принципу.

### Найденное при переносе, но не исправленное

`get_gift_code_by_key_id` объявлена в старом `database.py` дважды подряд
(строки 11273–11284 и 11286–11297) с разными запросами: во второй версии
добавлено условие `AND is_activated = 0`. Побеждает вторая — она затирает
первую. Оба определения перенесены в `db/gifts.py` в исходном порядке, чтобы
победитель не поменялся. Первое определение остаётся мёртвым кодом; это
существующий дефект, а не следствие разделения, и он сознательно не тронут.

### Почему доменные модули не импортируют имена друг у друга

Граф вызовов между доменами циклический (`keys` ↔ `hosts`, `hosts` ↔ `plans`,
`keys` ↔ `schema`, `_core` ↔ `franchise` и ещё 11 циклов), поэтому обычные
`from .keys import add_new_key` на уровне модуля привели бы к циклическому
импорту. Пути
обхода — отложенные импорты внутри функций — потребовали бы правки тел, что
этим шагом запрещено. Вместо этого `db/__init__.py` собирает единое
пространство имён обратно (`_link_namespace`), а `broadcast` разносит внешний
`setattr` на фасаде по доменным модулям. Единственное исключение —
`from ._core import _UNSET` в `keys.py`, `lte.py` и `plans.py`: этот sentinel
нужен уже при выполнении `def` (значение по умолчанию), поэтому раздать его
после импорта нельзя. Объект неизменяемый, сравнивается через `is`, нигде не
подменяется — идентичность сохраняется.

## Полная привязка


### `db/_core.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `DB_FILE` | константа | 21–32 |
| `logger` | константа | 14 |
| `_UNSET` | константа | 17 |
| `_now_str` | функция | 35–36 |
| `add_calendar_months` | функция | 39–47 |
| `add_months` | функция | 56–68 |
| `_to_datetime_str` | функция | 227–234 |
| `_normalize_email` | функция | 237–241 |
| `_get_table_columns` | функция | 273–275 |
| `_ensure_unique_index` | функция | 284–285 |
| `_decrypt_row_secrets` | функция | 2569–2577 |
| `_SUCCESS_TX_SQL` | константа | 3519 |
| `_NON_BALANCE_SQL` | константа | 3520 |
| `_REAL_MONEY_SQL` | константа | 3523–3525 |
| `EMAIL_ONLY_TELEGRAM_ID_MIN` | константа | 4550 |
| `EMAIL_ONLY_TELEGRAM_ID_MAX` | константа | 4551 |
| `SECRET_SETTING_KEYS` | константа | 4798–4806 |
| `get_setting` | функция | 4809–4821 |
| `_retry_sqlite` | функция | 4883–4891 |
| `get_all_settings` | функция | 5674–5689 |
| `update_setting` | функция | 5691–5702 |
| `_parse_json_metadata` | функция | 6491–6497 |
| `UNREACHABLE_REASON_BLOCKED` | константа | 9088 |
| `UNREACHABLE_REASON_DEACTIVATED` | константа | 9089 |
| `resolve_db_file_path` | функция | 9454–9470 |
| `MANAGED_BOT_TOKEN_PREFIX` | константа | 10039 |
| `_managed_bot_token_secret` | функция | 10042–10051 |
| `encrypt_managed_bot_token` | функция | 10118–10131 |
| `decrypt_managed_bot_token` | функция | 10134–10154 |
| `get_msk_time` | функция | 11319–11322 |
| `get_webapp_settings` | функция | 11783–11806 |

### `db/analytics.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `insert_resource_metric` | функция | 2132–2165 |
| `get_latest_resource_metric` | функция | 2168–2186 |
| `get_metrics_series` | функция | 2189–2227 |
| `get_speedtests` | функция | 2718–2744 |
| `get_latest_speedtest` | функция | 2746–2768 |
| `get_admin_stats` | функция | 3436–3513 |
| `get_sales_overview` | функция | 3528–3648 |
| `get_revenue_series` | функция | 3651–3674 |
| `get_trial_key_stats` | функция | 3794–3875 |
| `get_top_buyers` | функция | 3982–4013 |
| `get_coupons_analytics` | функция | 4046–4122 |
| `get_server_cost_entries` | функция | 4125–4138 |
| `create_server_cost_entry` | функция | 4141–4180 |
| `update_server_cost_entry` | функция | 4183–4205 |
| `delete_server_cost_entry` | функция | 4208–4217 |
| `get_economics_summary` | функция | 4220–4256 |
| `get_revenue_forecast` | функция | 4259–4308 |
| `get_broadcast_stats` | функция | 4650–4659 |
| `get_pending_status` | функция | 5234–5254 |
| `update_user_stats` | функция | 7828–7835 |
| `get_total_spent_sum` | функция | 7857–7874 |
| `update_key_status_from_server` | функция | 8800–8840 |
| `get_daily_stats_for_charts` | функция | 8843–8875 |
| `get_reachability_stats` | функция | 9137–9166 |

### `db/broadcasts.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `create_broadcast_campaign` | функция | 4459–4471 |
| `get_broadcast_campaigns` | функция | 4474–4483 |
| `get_broadcast_campaign` | функция | 4486–4496 |
| `update_broadcast_campaign` | функция | 4499–4511 |
| `toggle_broadcast_campaign` | функция | 4514–4532 |
| `delete_broadcast_campaign` | функция | 4535–4545 |
| `get_inactive_subscribers` | функция | 4564–4588 |
| `record_broadcast_sends` | функция | 4614–4633 |
| `mark_broadcast_run` | функция | 4636–4647 |

### `db/buttons.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `get_button_configs` | функция | 5705–5725 |
| `get_button_configs_admin` | функция | 5728–5759 |
| `get_button_config_by_db_id` | функция | 5762–5773 |
| `get_button_config` | функция | 5775–5791 |
| `create_button_config` | функция | 5793–5836 |
| `update_button_config` | функция | 5838–5899 |
| `delete_button_config` | функция | 5901–5912 |
| `update_existing_my_keys_button` | функция | 5914–5946 |
| `ensure_main_menu_referral_button` | функция | 5986–6036 |
| `ensure_admin_plans_button` | функция | 6039–6109 |
| `ensure_admin_trial_button` | функция | 6114–6153 |
| `ensure_admin_auto_renew_button` | функция | 6156–6199 |
| `reorder_button_configs` | функция | 6202–6248 |
| `initialize_default_button_configs` | функция | 6250–6385 |

### `db/captcha_auth.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `create_webapp_auth_request` | функция | 7439–7452 |
| `confirm_webapp_auth_request` | функция | 7455–7471 |
| `get_webapp_auth_request` | функция | 7474–7493 |
| `cleanup_old_webapp_auth_requests` | функция | 7496–7506 |
| `get_user_by_auth_token` | функция | 11423–11436 |
| `get_auth_token_by_user_id` | функция | 11439–11449 |
| `update_user_auth_token` | функция | 11452–11462 |
| `invalidate_all_user_auth_tokens` | функция | 11465–11491 |
| `hash_password` | функция | 11494–11498 |
| `verify_password` | функция | 11501–11517 |
| `update_user_password` | функция | 11572–11586 |
| `_hash_verification_code` | функция | 11589–11590 |
| `set_email_verification_code` | функция | 11593–11612 |
| `get_email_verification` | функция | 11615–11632 |
| `check_email_verification_code` | функция | 11635–11647 |
| `mark_email_verified` | функция | 11650–11667 |
| `update_email_code_last_sent` | функция | 11670–11683 |
| `update_user_password_by_id` | функция | 11686–11698 |

### `db/franchise.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `REFERRAL_WITHDRAWAL_STATUSES` | константа | 7289 |
| `REFERRAL_PAYOUT_METHOD_LABELS` | константа | 7290 |
| `REFERRAL_WITHDRAW_METHOD_SETTINGS` | константа | 7291–7295 |
| `MAX_OPEN_REFERRAL_WITHDRAWAL_REQUESTS` | константа | 7296 |
| `is_referral_withdraw_method_type_enabled` | функция | 7305–7309 |
| `format_referral_withdrawal_admin_notice` | функция | 7339–7363 |
| `create_referral_withdrawal_request` | функция | 7509–7569 |
| `has_open_referral_withdrawal_request` | функция | 7572–7588 |
| `list_referral_withdrawal_requests` | функция | 7591–7616 |
| `get_referral_withdrawal_request` | функция | 7619–7637 |
| `update_referral_withdrawal_request_status` | функция | 7640–7717 |
| `get_referral_withdrawable_stats` | функция | 7720–7733 |
| `get_franchise_percent_default` | функция | 10000–10006 |
| `get_franchise_min_withdraw` | функция | 10009–10015 |
| `resolve_factory_bot_id` | функция | 10018–10036 |
| `_managed_bot_token_pad` | функция | 10054–10060 |
| `_row_with_decrypted_token` | функция | 10157–10163 |
| `get_managed_bot` | функция | 10166–10176 |
| `get_managed_bot_by_telegram_id` | функция | 10179–10189 |
| `list_active_managed_bots` | функция | 10192–10201 |
| `update_managed_bot_active` | функция | 10204–10219 |
| `get_managed_bots_by_owner` | функция | 10222–10245 |
| `purge_managed_bot_stats` | функция | 10248–10260 |
| `_purge_managed_bot_stats_on_cursor` | функция | 10263–10265 |
| `delete_managed_bot` | функция | 10268–10316 |
| `get_factory_cabinet` | функция | 10319–10352 |
| `create_managed_bot` | функция | 10355–10419 |
| `record_factory_activity` | функция | 10422–10449 |
| `_is_card_payment_method` | функция | 10452–10459 |
| `accrue_partner_commission` | функция | 10462–10571 |
| `get_partner_cabinet` | функция | 10574–10617 |
| `list_partner_requisites` | функция | 10622–10644 |
| `get_default_partner_requisite` | функция | 10647–10656 |
| `add_partner_requisite` | функция | 10659–10726 |
| `set_default_partner_requisite` | функция | 10729–10763 |
| `delete_partner_requisite` | функция | 10766–10811 |
| `create_withdraw_request` | функция | 10814–10862 |

### `db/gifts.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `create_gift_key` | функция | 4773–4794 |
| `ensure_main_menu_gift_button` | функция | 5949–5983 |
| `create_user_gift` | функция | 10869–10917 |
| `get_user_gift` | функция | 10920–10931 |
| `get_gift_by_code` | функция | 10934–10945 |
| `get_user_inactive_gifts` | функция | 10948–10979 |
| `activate_user_gift` | функция | 10982–11036 |
| `set_referred_by_from_gift` | функция | 11052–11089 |
| `delete_user_gift` | функция | 11244–11254 |
| `link_key_to_gift` | функция | 11257–11270 |
| `get_gift_code_by_key_id` | функция | 11273–11284 |
| `get_gift_code_by_key_id` | функция | 11286–11297 |
| `get_gift_info_by_key_id` | функция | 11299–11312 |

### `db/hosts.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `remnawave_traffic_limit_strategy_for_plan` | функция | 122–128 |
| `normalize_host_name` | функция | 292–297 |
| `upsert_key_node_usage_snapshot` | функция | 1079–1121 |
| `get_node_usage_for_key` | функция | 1124–1150 |
| `delete_node_usage_for_key` | функция | 1153–1163 |
| `seed_global_remnawave_from_hosts` | функция | 1695–1732 |
| `apply_global_remnawave_to_hosts` | функция | 1735–1764 |
| `create_host` | функция | 2230–2257 |
| `update_host_subscription_url` | функция | 2259–2278 |
| `update_host_url` | функция | 2335–2355 |
| `update_host_remnawave_settings` | функция | 2357–2401 |
| `get_host_class` | функция | 2404–2418 |
| `set_host_class` | функция | 2421–2438 |
| `list_hosts_by_class` | функция | 2491–2504 |
| `update_host_name` | функция | 2507–2549 |
| `delete_host` | функция | 2551–2567 |
| `get_host` | функция | 2580–2591 |
| `update_host_ssh_settings` | функция | 2593–2632 |
| `get_all_hosts` | функция | 2700–2716 |
| `insert_host_speedtest` | функция | 2770–2813 |
| `get_ssh_known_host_key` | функция | 2863–2878 |
| `save_ssh_known_host_key` | функция | 2881–2902 |
| `update_key_host` | функция | 4770–4771 |
| `get_plans_for_host` | функция | 6411–6422 |
| `get_active_plans_for_host` | функция | 6426–6441 |
| `get_key_by_remnawave_uuid` | функция | 8617–8633 |
| `update_key_host_and_info` | функция | 8645–8658 |
| `get_keys_for_host` | функция | 8665–8679 |

### `db/keys.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `compute_next_traffic_reset_str` | функция | 50–53 |
| `compute_next_traffic_reset` | функция | 71–74 |
| `_as_limit_bytes` | функция | 77–82 |
| `key_is_unbilled_trial_or_gift` | функция | 143–158 |
| `format_next_traffic_reset_display` | функция | 185–193 |
| `compute_aligned_next_traffic_reset` | функция | 196–224 |
| `_normalize_key_row` | функция | 244–270 |
| `resolve_key_period_start` | функция | 1046–1076 |
| `_finalize_vpn_key_indexes` | функция | 1894–1899 |
| `delete_key_by_id` | функция | 2634–2650 |
| `update_key_comment` | функция | 2652–2661 |
| `update_key_name` | функция | 2664–2697 |
| `get_all_keys` | функция | 4662–4671 |
| `get_all_key_ids` | функция | 4674–4683 |
| `extend_key` | функция | 4686–4693 |
| `set_key_expiry` | функция | 4696–4700 |
| `get_keys_paginated` | функция | 4703–4760 |
| `get_keys_for_user` | функция | 4763–4764 |
| `update_key_email` | функция | 4766–4768 |
| `set_key_traffic_boost` | функция | 6614–6626 |
| `get_total_keys_count` | функция | 7847–7855 |
| `add_new_key` | функция | 8290–8362 |
| `_apply_key_updates` | функция | 8365–8384 |
| `update_key_fields` | функция | 8387–8443 |
| `apply_key_monthly_reset_fields` | функция | 8446–8488 |
| `backfill_monthly_traffic_reset_for_existing_keys` | функция | 8491–8530 |
| `delete_key_by_email` | функция | 8533–8568 |
| `get_user_keys` | функция | 8571–8584 |
| `get_key_by_id` | функция | 8587–8597 |
| `get_key_by_email` | функция | 8600–8614 |
| `update_key_info` | функция | 8636–8642 |
| `get_next_key_number` | функция | 8661–8662 |
| `set_key_auto_renew` | функция | 8682–8691 |
| `set_all_keys_auto_renew_for_user` | функция | 8694–8704 |
| `get_keys_for_auto_renew` | функция | 8707–8730 |
| `_key_matches_search` | функция | 8733–8741 |
| `search_user_keys_by_email` | функция | 8744–8763 |
| `search_all_keys_by_email` | функция | 8766–8784 |
| `get_all_vpn_users` | функция | 8787–8797 |
| `get_keys_counts_for_users` | функция | 9043–9061 |
| `delete_user_keys` | функция | 9168–9182 |
| `get_key_usage_monitor` | функция | 9915–9925 |
| `ensure_key_usage_monitor_row` | функция | 9928–9938 |
| `update_key_usage_monitor` | функция | 9941–9990 |

### `db/lte.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `plan_lte_limit_bytes` | функция | 89–90 |
| `should_account_lte_traffic` | функция | 93–114 |
| `add_host_squad` | функция | 1412–1449 |
| `get_host_squads` | функция | 1452–1467 |
| `get_squad_by_class` | функция | 1470–1493 |
| `DEFAULT_LTE_SQUAD_LABEL` | константа | 1496 |
| `_SQUAD_LABEL_MAX_LEN` | константа | 1497 |
| `squad_display_label` | функция | 1500–1517 |
| `get_lte_squad_display_label` | функция | 1520–1528 |
| `set_host_squad_active` | функция | 1531–1543 |
| `delete_host_squad` | функция | 1546–1555 |
| `_ensure_remnawave_squads_catalog` | функция | 1558–1625 |
| `get_remnawave_squads` | функция | 1628–1641 |
| `add_remnawave_squad` | функция | 1644–1668 |
| `delete_remnawave_squad` | функция | 1671–1692 |
| `set_host_squads_from_catalog` | функция | 1767–1851 |
| `get_host_selected_squad_catalog_ids` | функция | 1854–1873 |
| `set_host_squad_overlap` | функция | 2441–2467 |
| `get_host_squad_overlap` | функция | 2470–2488 |
| `get_plan_lte_limit` | функция | 6629–6638 |
| `get_lte_state` | функция | 6641–6690 |
| `_KEY_LTE_DEFAULT_STATE` | константа | 6693–6702 |
| `get_key_lte_state` | функция | 6705–6729 |
| `update_key_lte_state` | функция | 6732–6774 |
| `add_key_lte_boost_bytes` | функция | 6777–6806 |
| `commit_key_lte_baseline` | функция | 6809–6837 |
| `request_key_lte_baseline_reset` | функция | 6840–6854 |
| `resolve_lte_limit_bytes` | функция | 6857–6876 |
| `add_lte_boost_bytes` | функция | 6879–6914 |
| `commit_lte_baseline` | функция | 6917–6953 |
| `request_lte_baseline_reset` | функция | 6956–6979 |
| `update_lte_state` | функция | 6982–7022 |

### `db/payments.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `PENDING_ACTION_DEFAULT_TTL_HOURS` | константа | 2994 |
| `create_pending_action` | функция | 2997–3028 |
| `get_pending_action` | функция | 3031–3046 |
| `claim_pending_action` | функция | 3049–3074 |
| `set_pending_action_result` | функция | 3077–3093 |
| `cleanup_expired_pending_actions` | функция | 3096–3111 |
| `get_payment_methods_analytics` | функция | 3729–3759 |
| `get_users_without_real_payment_with_keys` | функция | 3762–3791 |
| `get_pending_broadcast_recipients` | функция | 4591–4611 |
| `_connect_pending_db` | функция | 4869–4880 |
| `_PAID_TX_STATUSES` | константа | 4921 |
| `_TERMINAL_TX_STATUSES` | константа | 4922–4924 |
| `_PROVIDER_TX_KEYS` | константа | 4925–4931 |
| `_tx_meta_dict` | функция | 4934–4941 |
| `_provider_transaction_id_from_meta` | функция | 4944–4951 |
| `_mirror_pending_to_ledger` | функция | 4954–5014 |
| `create_payload_pending` | функция | 5017–5064 |
| `patch_pending_metadata` | функция | 5067–5103 |
| `_get_pending_metadata` | функция | 5106–5134 |
| `get_pending_metadata` | функция | 5137–5139 |
| `get_pending_record` | функция | 5142–5179 |
| `revive_cancelled_invoice` | функция | 5182–5218 |
| `prepare_pending_for_fulfillment` | функция | 5221–5231 |
| `_complete_pending` | функция | 5257–5276 |
| `find_and_complete_pending_transaction` | функция | 5279–5331 |
| `get_latest_pending_for_user` | функция | 5334–5363 |
| `claim_processed_payment` | функция | 5366–5386 |
| `unclaim_processed_payment` | функция | 5389–5406 |
| `refund_payment_once` | функция | 5409–5471 |
| `cancel_pending_transaction` | функция | 5474–5539 |
| `reset_pending_transaction` | функция | 5542–5562 |
| `get_balance` | функция | 7163–7172 |
| `adjust_user_balance` | функция | 7174–7184 |
| `set_balance` | функция | 7198–7207 |
| `add_to_balance` | функция | 7209–7236 |
| `deduct_from_balance` | функция | 7238–7260 |
| `create_pending_transaction` | функция | 7876–7901 |
| `find_and_complete_ton_transaction` | функция | 7904–7995 |
| `_TX_ACTION_LABELS` | константа | 7996–8004 |
| `_describe_transaction_action` | функция | 8006–8023 |
| `_find_nearest_key_id` | функция | 8025–8060 |
| `log_transaction` | функция | 8062–8128 |
| `get_paginated_transactions` | функция | 8130–8179 |
| `get_transactions_paginated` | функция | 8181–8278 |
| `get_recent_transactions` | функция | 8878–8911 |
| `check_transaction_exists` | функция | 11325–11350 |
| `payment_owned_by_user` | функция | 11353–11387 |
| `set_pending_email` | функция | 11701–11715 |
| `clear_pending_email` | функция | 11718–11732 |
| `finalize_pending_email_change` | функция | 11735–11780 |

### `db/plans.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `plan_main_limit_bytes` | функция | 85–86 |
| `plan_has_monthly_traffic_reset` | функция | 117–119 |
| `parse_plan_id_from_key` | функция | 131–140 |
| `resolve_plan_for_key` | функция | 161–182 |
| `get_plans_analytics` | функция | 3677–3726 |
| `create_plan` | функция | 6387–6408 |
| `set_plan_active` | функция | 6444–6457 |
| `get_plan_by_id` | функция | 6459–6469 |
| `get_all_plans` | функция | 6472–6488 |
| `update_plan_metadata` | функция | 6499–6515 |
| `create_traffic_package` | функция | 6518–6546 |
| `get_traffic_packages_for_plan` | функция | 6549–6563 |
| `get_traffic_package_by_id` | функция | 6566–6576 |
| `update_traffic_package` | функция | 6579–6599 |
| `delete_traffic_package` | функция | 6602–6611 |
| `delete_plan` | функция | 7025–7034 |
| `update_plan` | функция | 7036–7072 |
| `get_device_tiers` | функция | 11407–11420 |

### `db/promo.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `_promo_plans_label` | функция | 4016–4027 |
| `_promo_segment_label` | функция | 4030–4043 |

### `db/referral.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `claim_referral_start_bonus` | функция | 2280–2306 |
| `set_referral_start_bonus_received` | функция | 2309–2315 |
| `set_referral_trial_day_bonus_received` | функция | 2318–2333 |
| `get_referrals_analytics` | функция | 3878–3938 |
| `get_top_referrers` | функция | 3941–3979 |
| `get_referrals_for_user` | функция | 5565–5586 |
| `get_referral_top_rich` | функция | 5589–5618 |
| `get_referral_rank_and_count` | функция | 5621–5672 |
| `add_to_referral_balance` | функция | 7100–7109 |
| `set_referral_balance` | функция | 7111–7118 |
| `set_referral_balance_all` | функция | 7120–7127 |
| `add_to_referral_balance_all` | функция | 7129–7139 |
| `get_referral_balance_all` | функция | 7141–7150 |
| `get_referral_balance` | функция | 7152–7161 |
| `adjust_user_referral_balance` | функция | 7186–7196 |
| `deduct_from_referral_balance` | функция | 7262–7281 |
| `REFERRAL_PAYOUT_METHOD_TYPES` | константа | 7288 |
| `_REFERRAL_TRC20_RE` | константа | 7297 |
| `_referral_setting_is_true` | функция | 7300–7302 |
| `validate_referral_payout_requisite` | функция | 7312–7336 |
| `list_referral_payout_methods` | функция | 7366–7378 |
| `add_referral_payout_method` | функция | 7381–7400 |
| `delete_referral_payout_method` | функция | 7403–7417 |
| `get_referral_payout_method` | функция | 7420–7436 |
| `get_referral_count` | функция | 7736–7744 |
| `REFERRAL_LINK_LINKED` | константа | 11094 |
| `REFERRAL_LINK_ALREADY_LINKED` | константа | 11095 |
| `REFERRAL_LINK_SELF_FORBIDDEN` | константа | 11096 |
| `REFERRAL_LINK_INVALID_REFERRER` | константа | 11097 |
| `REFERRAL_LINK_NOT_ELIGIBLE` | константа | 11098 |
| `link_referrer_if_eligible` | функция | 11101–11170 |
| `REFERRAL_UNLINK_UNLINKED` | константа | 11173 |
| `REFERRAL_UNLINK_NOT_LINKED` | константа | 11174 |
| `REFERRAL_UNLINK_NOT_FOUND` | константа | 11175 |
| `REFERRAL_UNLINK_INVALID` | константа | 11176 |
| `unlink_referral` | функция | 11179–11214 |
| `unlink_all_referrals` | функция | 11217–11241 |

### `db/schema.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `_ensure_table_column` | функция | 278–281 |
| `_ensure_index` | функция | 288–289 |
| `initialize_db` | функция | 300–891 |
| `_ensure_users_columns` | функция | 894–916 |
| `_ensure_email_verification_columns` | функция | 919–943 |
| `_ensure_hosts_columns` | функция | 946–973 |
| `_ensure_plans_columns` | функция | 976–990 |
| `_ensure_traffic_packages_table` | функция | 993–1014 |
| `_ensure_key_node_usage_snapshots_table` | функция | 1017–1043 |
| `_ensure_subscription_lte_table` | функция | 1166–1194 |
| `_ensure_key_lte_state_table` | функция | 1197–1221 |
| `_migrate_subscription_lte_to_keys` | функция | 1224–1326 |
| `_ensure_host_squads_table` | функция | 1329–1409 |
| `_ensure_support_tickets_columns` | функция | 1876–1882 |
| `_ensure_key_usage_monitor_columns` | функция | 1885–1891 |
| `_rebuild_vpn_keys_table` | функция | 1902–2002 |
| `_ensure_vpn_keys_schema` | функция | 2005–2034 |
| `_migrate_gift_tags` | функция | 2037–2049 |
| `run_migration` | функция | 2053–2129 |
| `_ensure_ssh_known_hosts_table` | функция | 2849–2860 |
| `_ensure_gift_tokens_table` | функция | 2905–2938 |
| `_ensure_user_gifts_table` | функция | 2941–2962 |
| `_ensure_auth_pending_actions_table` | функция | 2965–2991 |
| `_ensure_promo_tables` | функция | 3114–3175 |
| `_ensure_analytics_tables` | функция | 3178–3284 |
| `_ensure_pending_tables` | функция | 4894–4907 |
| `_ensure_processed_payments_table` | функция | 4910–4918 |
| `_backfill_encrypt_secrets_at_rest` | функция | 10063–10115 |

### `db/ssh_targets.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `_ensure_ssh_targets_table` | функция | 2817–2846 |
| `get_all_ssh_targets` | функция | 3287–3298 |
| `get_ssh_target` | функция | 3301–3312 |
| `create_ssh_target` | функция | 3315–3353 |
| `update_ssh_target_fields` | функция | 3356–3420 |
| `delete_ssh_target` | функция | 3423–3434 |

### `db/tickets.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `create_support_ticket` | функция | 9306–9330 |
| `get_or_create_open_ticket` | функция | 9332–9356 |
| `add_support_message` | функция | 9358–9374 |
| `update_ticket_thread_info` | функция | 9376–9388 |
| `get_ticket` | функция | 9390–9400 |
| `get_ticket_by_thread` | функция | 9402–9415 |
| `get_user_tickets` | функция | 9417–9435 |
| `get_support_message` | функция | 9437–9451 |
| `get_ticket_media_root` | функция | 9473–9478 |
| `list_closed_ticket_ids_older_than` | функция | 9481–9500 |
| `clear_support_message_media` | функция | 9503–9516 |
| `get_ticket_messages` | функция | 9519–9531 |
| `set_ticket_status` | функция | 9533–9545 |
| `update_ticket_subject` | функция | 9547–9559 |
| `_cleanup_ticket_media` | функция | 9561–9568 |
| `delete_ticket` | функция | 9571–9590 |
| `_ticket_forum_target` | функция | 9593–9606 |
| `TICKET_AUTO_CLOSE_DAYS_MAX` | константа | 9609 |
| `TICKET_AUTO_CLOSE_BATCH` | константа | 9610 |
| `TICKET_AUTO_CLOSE_DAYS_NOT_INTEGER` | константа | 9611–9613 |
| `_TICKET_AUTO_CLOSE_WHOLE_RE` | константа | 9614 |
| `validate_ticket_auto_close_days` | функция | 9617–9636 |
| `parse_ticket_auto_close_days` | функция | 9639–9650 |
| `get_ticket_auto_close_days` | функция | 9653–9654 |
| `find_open_tickets_idle_after_admin` | функция | 9657–9709 |
| `auto_close_idle_admin_tickets` | функция | 9712–9776 |
| `bulk_close_open_tickets` | функция | 9779–9804 |
| `bulk_delete_all_tickets` | функция | 9807–9836 |
| `cleanup_ticket_media_ids` | функция | 9839–9852 |
| `get_tickets_paginated` | функция | 9854–9877 |
| `get_open_tickets_count` | функция | 9879–9887 |
| `get_closed_tickets_count` | функция | 9889–9897 |
| `get_all_tickets_count` | функция | 9899–9907 |

### `db/users.py`

| Имя | Вид | Строки в старом `database.py` |
| --- | --- | --- |
| `get_utm_links` | функция | 4311–4324 |
| `create_utm_link` | функция | 4327–4360 |
| `delete_utm_link` | функция | 4363–4377 |
| `log_utm_visit` | функция | 4380–4391 |
| `set_user_utm_slug_if_absent` | функция | 4394–4407 |
| `get_utm_analytics` | функция | 4410–4452 |
| `is_email_only_user` | функция | 4554–4561 |
| `get_admin_ids` | функция | 4823–4860 |
| `is_admin` | функция | 4862–4867 |
| `register_user_if_not_exists` | функция | 7075–7098 |
| `get_user` | функция | 7746–7756 |
| `get_user_by_username` | функция | 7759–7773 |
| `set_terms_agreed` | функция | 7775–7783 |
| `is_subscription_expiry_notifications_enabled` | функция | 7785–7800 |
| `toggle_subscription_expiry_notifications` | функция | 7802–7826 |
| `get_user_count` | функция | 7837–7845 |
| `set_trial_used` | функция | 8280–8288 |
| `get_all_users` | функция | 8914–8923 |
| `get_users_paginated` | функция | 8925–9041 |
| `ban_user` | функция | 9063–9070 |
| `unban_user` | функция | 9072–9079 |
| `mark_user_unreachable` | функция | 9091–9115 |
| `mark_user_reachable` | функция | 9117–9135 |
| `delete_user_completely` | функция | 9185–9304 |
| `_registration_age_seconds` | функция | 11039–11049 |
| `get_seller_user` | функция | 11390–11404 |
| `get_user_by_email` | функция | 11520–11534 |
| `create_user_by_email` | функция | 11537–11569 |
