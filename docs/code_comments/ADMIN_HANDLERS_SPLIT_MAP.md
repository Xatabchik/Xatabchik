# Карта разделения `bot/admin_handlers.py`

Файл разделён на доменные модули пакета `src/shop_bot/bot/admin_router/`.
Тела функций перенесены дословно; `admin_handlers.py` остался фасадом и
ре-экспортирует прежний публичный API целиком, поэтому вызывающие
(`bot_controller.py`, `tests/test_admin_router_authorization.py`) не изменились.

Особенность этого файла: все 288 хендлеров были **вложенными функциями** одной
фабрики `get_admin_router()` на 8996 строк и обращались к соседям просто по
имени, то есть замыканием по локальным переменным фабрики. Разложить такие
определения по файлам «как есть» нельзя, поэтому каждый блок переехал целиком
в `register_<группа>[_<n>](admin_router)` с тем же отступом 4 — включая строки
`@admin_router.…`.

Столбец «строки» — расположение в исходном `admin_handlers.py` до разделения,
чтобы перенос можно было сверить с `INVENTORY.md` и документацией в
`shop_bot_bot_admin_handlers_part*.md`.

## Сводка

| Модуль | Назначение | Перенесено определений | Строк | Регистрирует хендлеров |
| --- | --- | ---: | ---: | ---: |
| `admin_router/plans.py` | Тарифы и пакеты трафика: создание, правка, удаление, лимиты LTE | 58 | 1442 | 52 |
| `admin_router/hosts.py` | Хосты: добавление, правка, сквады, SSH-доступ, переход к тарифам | 39 | 992 | 32 |
| `admin_router/promo.py` | Промокоды: пошаговое создание, список, включение и отключение | 31 | 788 | 25 |
| `admin_router/button_constructor.py` | Конструктор кнопок: меню, список, карточка, добавление и правка | 30 | 678 | 21 |
| `admin_router/keys.py` | Ключи: поиск, карточка, правка email, продление, удаление | 17 | 530 | 15 |
| `admin_router/referral.py` | Реферальная программа: тип награды, проценты, минимальные суммы | 21 | 353 | 15 |
| `admin_router/mailing.py` | Рассылка: текст, режим разбора, кнопка, предпросмотр, отправка | 15 | 349 | 12 |
| `admin_router/speedtest.py` | Speedtest: запуск по хостам и SSH-целям, автоустановка утилиты | 11 | 488 | 11 |
| `admin_router/balance.py` | Баланс пользователя: пополнение и списание вручную | 12 | 237 | 10 |
| `admin_router/captcha.py` | Капча: включение, тип, число попыток, таймаут, текст | 10 | 214 | 10 |
| `admin_router/trial.py` | Пробный период: включение, длительность, трафик, устройства, хост | 16 | 271 | 10 |
| `admin_router/gifts.py` | Выдача ключа в подарок: выбор пользователя, хоста и срока | 9 | 221 | 8 |
| `admin_router/users.py` | Пользователи: поиск, карточка, бан, разбан, удаление, рефералы | 9 | 450 | 8 |
| `admin_router/admins.py` | Администраторы: список, добавление, удаление | 8 | 246 | 6 |
| `admin_router/franchise.py` | Франшиза: включение, процент партнёра, минимум вывода | 9 | 170 | 6 |
| `admin_router/notifications.py` | Уведомления: напоминание неактивным, интервал, ссылка на поддержку | 11 | 191 | 6 |
| `admin_router/payments.py` | Платёжные провайдеры: статус, карточка провайдера, правка полей | 14 | 452 | 6 |
| `admin_router/host_keys.py` | Ключи в разрезе хостов: выбор хоста и постраничный список | 6 | 112 | 5 |
| `admin_router/menu.py` | Корневые меню админки: главное, системное и меню настроек | 8 | 137 | 5 |
| `admin_router/monitor.py` | Мониторинг ресурсов: локально, по хостам и по SSH-целям | 5 | 603 | 5 |
| `admin_router/auto_renew.py` | Автопродление: включение и интервал проверки | 6 | 103 | 4 |
| `admin_router/key_quick_ops.py` | Быстрые операции с ключом по идентификатору: удаление, продление | 6 | 132 | 4 |
| `admin_router/modules.py` | Раздел «Модули»: список плагинов, включение и отключение | 6 | 123 | 4 |
| `admin_router/backup.py` | Бэкап и восстановление базы данных | 4 | 108 | 3 |
| `admin_router/lte_settings.py` | Настройки LTE: интервал двойного лимита | 6 | 104 | 3 |
| `admin_router/withdrawals.py` | Заявки на вывод: подтверждение и отклонение командой | 2 | 62 | 2 |
| `admin_router/core.py` | Общие определения админки: состояния FSM, фильтр доступа, middleware, хелперы | 10 | 158 | — |
| **итого** | | **379** | | **288** |

## Что поднято на уровень модуля

Определение остаётся вложенным в `register_*`, пока его читают только соседи
из того же сегмента: это по-прежнему замыкание, и код не меняется вообще.
Если же на него ссылаются из другого сегмента, замыкания больше нет —
определение выносится на уровень модуля со сдвигом отступа на 4 пробела, а
тело остаётся тем же. Транзитивно выносится и всё, что нужно самому
вынесенному определению.

Из 86 захваченных фабрикой имён так поднято 16, остальные 70 остались
локальными.

| Определение | Файл | Кто читает из другого сегмента |
| --- | --- | --- |
| `_format_user_mention` | `core.py` | speedtest |
| `_resolve_target_from_hash` | `core.py` | speedtest |
| `show_admin_menu` | `menu.py` | admins, balance, mailing, gifts, host_keys, plans, speedtest |
| `show_admin_system_menu` | `menu.py` | другой сегмент menu |
| `show_admin_settings_menu` | `menu.py` | button_constructor |
| `_build_modules_keyboard` | `modules.py` | нужен `show_admin_modules_menu` |
| `show_admin_modules_menu` | `modules.py` | другой сегмент modules |
| `AdminPlans` | `plans.py` | hosts |
| `_format_plan_duration` | `plans.py` | нужен `_format_plans_for_host` |
| `_format_traffic_gb` | `plans.py` | нужен `_format_plans_for_host` |
| `_format_devices` | `plans.py` | нужен `_format_plans_for_host` |
| `_format_plans_for_host` | `plans.py` | hosts |
| `show_admin_promo_menu` | `promo.py` | другой сегмент promo |
| `_parse_datetime_input` | `promo.py` | другой сегмент promo |
| `_format_promo_line` | `promo.py` | другой сегмент promo |
| `_build_promo_list_keyboard` | `promo.py` | другой сегмент promo |

## Порядок сборки роутера

`router.py` вызывает `register_*` строго в порядке блоков исходного файла.
Порядок значим: aiogram проверяет хендлеры одного типа события в порядке
регистрации, поэтому перестановка блоков изменила бы, какой хендлер поймает
апдейт первым.

Восемь групп в исходном файле шли чересполосно: `menu`, `modules`, `promo`,
`speedtest`, `users`, `admins`, `keys`, `balance`. У шести из них осталось по
нескольку сегментов, и номер в имени отражает исходный порядок, а не
приоритет. У `modules` и `promo` второй сегмент состоял только из
определений, поднятых на уровень модуля, поэтому register-функция у них одна.

1. `register_menu_1`
2. `register_modules`
3. `register_button_constructor`
4. `register_payments`
5. `register_referral`
6. `register_franchise`
7. `register_hosts`
8. `register_trial`
9. `register_lte_settings`
10. `register_notifications`
11. `register_plans`
12. `register_promo`
13. `register_speedtest_1`
14. `register_backup`
15. `register_speedtest_2`
16. `register_users_1`
17. `register_admins_1`
18. `register_users_2`
19. `register_keys_1`
20. `register_admins_2`
21. `register_keys_2`
22. `register_gifts`
23. `register_balance_1`
24. `register_keys_3`
25. `register_menu_2`
26. `register_balance_2`
27. `register_host_keys`
28. `register_key_quick_ops`
29. `register_mailing`
30. `register_withdrawals`
31. `register_monitor`
32. `register_captcha`
33. `register_auto_renew`

## Полная карта: определение → файл

`внутри register_*` — код перенесён дословно, включая отступ, и остался
вложенной функцией. `поднят на уровень модуля` — на определение ссылаются из
другого сегмента, поэтому оно вынесено на уровень модуля со сдвигом отступа
на 4 пробела; тело не тронуто. `уровень модуля` — определение и до разделения
было на уровне модуля.

### `admins.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `admin_admins_menu_entry` | 6332-6340 | внутри register_admins_1 |
| `admin_view_admins` | 6343-6378 | внутри register_admins_1 |
| `AdminAddAdmin` | 6846-6847 | внутри register_admins_2 |
| `admin_add_admin_entry` | 6850-6860 | внутри register_admins_2 |
| `admin_add_admin_process` | 6863-6921 | внутри register_admins_2 |
| `AdminRemoveAdmin` | 6924-6925 | внутри register_admins_2 |
| `admin_remove_admin_entry` | 6928-6938 | внутри register_admins_2 |
| `admin_remove_admin_process` | 6941-7009 | внутри register_admins_2 |

### `auto_renew.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminAutoRenew` | 8919-8920 | внутри register_auto_renew |
| `show_admin_auto_renew_menu` | 8922-8944 | внутри register_auto_renew |
| `admin_auto_renew_entry` | 8947-8954 | внутри register_auto_renew |
| `admin_auto_renew_toggle` | 8957-8966 | внутри register_auto_renew |
| `admin_auto_renew_set_hours` | 8969-8977 | внутри register_auto_renew |
| `admin_auto_renew_hours_input` | 8980-8994 | внутри register_auto_renew |

### `backup.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `admin_backup_db` | 5909-5937 | внутри register_backup |
| `AdminRestoreDB` | 5940-5941 | внутри register_backup |
| `admin_restore_db_prompt` | 5944-5961 | внутри register_backup |
| `admin_restore_db_receive` | 5964-5988 | внутри register_backup |

### `balance.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminMainRefill` | 7349-7351 | внутри register_balance_1 |
| `admin_add_balance_entry` | 7354-7363 | внутри register_balance_1 |
| `admin_add_balance_user` | 7366-7381 | внутри register_balance_1 |
| `admin_add_balance_pick_user_page` | 7385-7398 | внутри register_balance_1 |
| `admin_add_balance_pick_user` | 7402-7417 | внутри register_balance_1 |
| `handle_main_amount` | 7420-7446 | внутри register_balance_1 |
| `AdminMainDeduct` | 7499-7500 | внутри register_balance_2 |
| `admin_deduct_balance_entry` | 7504-7513 | внутри register_balance_2 |
| `admin_deduct_balance_user` | 7517-7532 | внутри register_balance_2 |
| `admin_deduct_balance_pick_user_page` | 7536-7549 | внутри register_balance_2 |
| `admin_deduct_balance_pick_user` | 7553-7568 | внутри register_balance_2 |
| `handle_deduct_amount` | 7571-7601 | внутри register_balance_2 |

### `button_constructor.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `ButtonConstructor` | 521-530 | внутри register_button_constructor |
| `_BTN_MENUS` | 532-539 | внутри register_button_constructor |
| `_btnc_menu_label` | 541-545 | внутри register_button_constructor |
| `_btnc_cancel_kb` | 547-552 | внутри register_button_constructor |
| `_btnc_show_menu_types` | 554-571 | внутри register_button_constructor |
| `_btnc_build_list_kb` | 573-614 | внутри register_button_constructor |
| `_btnc_show_list` | 616-631 | внутри register_button_constructor |
| `_btnc_build_details_kb` | 633-645 | внутри register_button_constructor |
| `_btnc_show_details` | 647-687 | внутри register_button_constructor |
| `admin_button_constructor_root` | 693-698 | внутри register_button_constructor |
| `btnc_select_menu_type` | 703-708 | внутри register_button_constructor |
| `btnc_open_list` | 713-723 | внутри register_button_constructor |
| `btnc_open_details` | 728-740 | внутри register_button_constructor |
| `btnc_toggle_active` | 745-760 | внутри register_button_constructor |
| `btnc_delete_confirm` | 765-784 | внутри register_button_constructor |
| `btnc_delete_do` | 789-802 | внутри register_button_constructor |
| `btnc_cancel_any` | 807-809 | внутри register_button_constructor |
| `btnc_action_menu` | 814-834 | внутри register_button_constructor |
| `btnc_edit_field_start` | 839-866 | внутри register_button_constructor |
| `btnc_edit_field_value` | 869-916 | внутри register_button_constructor |
| `btnc_add_start` | 924-938 | внутри register_button_constructor |
| `btnc_add_button_id` | 941-954 | внутри register_button_constructor |
| `btnc_add_text` | 957-975 | внутри register_button_constructor |
| `btnc_add_action_type` | 980-992 | внутри register_button_constructor |
| `btnc_add_action_value` | 995-1026 | внутри register_button_constructor |
| `btnc_add_row` | 1029-1047 | внутри register_button_constructor |
| `btnc_add_col` | 1050-1071 | внутри register_button_constructor |
| `btnc_add_width` | 1076-1097 | внутри register_button_constructor |
| `btnc_add_sort` | 1100-1123 | внутри register_button_constructor |
| `btnc_add_finish` | 1128-1160 | внутри register_button_constructor |

### `captcha.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `admin_captcha_settings_handler` | 8730-8764 | внутри register_captcha |
| `admin_captcha_toggle_handler` | 8767-8778 | внутри register_captcha |
| `admin_captcha_type_handler` | 8781-8803 | внутри register_captcha |
| `admin_captcha_type_set_handler` | 8806-8817 | внутри register_captcha |
| `admin_captcha_attempts_handler` | 8820-8831 | внутри register_captcha |
| `admin_captcha_attempts_input_handler` | 8834-8850 | внутри register_captcha |
| `admin_captcha_timeout_handler` | 8853-8864 | внутри register_captcha |
| `admin_captcha_timeout_input_handler` | 8867-8883 | внутри register_captcha |
| `admin_captcha_message_handler` | 8886-8897 | внутри register_captcha |
| `admin_captcha_message_input_handler` | 8900-8913 | внутри register_captcha |

### `core.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `logger` | ?-? | уровень модуля |
| `_is_true` | 99-100 | уровень модуля |
| `_mask_secret` | 103-109 | уровень модуля |
| `AdminSettings` | 111-114 | уровень модуля |
| `AdminModules` | 116-117 | уровень модуля |
| `Broadcast` | 119-127 | уровень модуля |
| `IsAdminFilter` | 130-147 | уровень модуля |
| `AdminAccessMiddleware` | 150-175 | уровень модуля |
| `_format_user_mention` | 186-200 | поднят на уровень модуля |
| `_resolve_target_from_hash` | 203-220 | поднят на уровень модуля |

### `franchise.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminFranchise` | 1916-1919 | внутри register_franchise |
| `_get_franchise_settings_for_admin` | 1922-1929 | внутри register_franchise |
| `show_admin_franchise_menu` | 1932-1953 | внутри register_franchise |
| `admin_franchise_menu_entry` | 1957-1965 | внутри register_franchise |
| `admin_franchise_toggle` | 1969-1993 | внутри register_franchise |
| `admin_franchise_set_percent` | 1996-2004 | внутри register_franchise |
| `admin_franchise_percent_input` | 2007-2025 | внутри register_franchise |
| `admin_franchise_set_min_withdraw` | 2028-2036 | внутри register_franchise |
| `admin_franchise_min_withdraw_input` | 2039-2057 | внутри register_franchise |

### `gifts.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminGiftKey` | 7161-7164 | внутри register_gifts |
| `admin_gift_key_entry` | 7167-7178 | внутри register_gifts |
| `admin_gift_key_for_user` | 7182-7199 | внутри register_gifts |
| `admin_gift_pick_user_page` | 7202-7215 | внутри register_gifts |
| `admin_gift_pick_user` | 7218-7234 | внутри register_gifts |
| `admin_gift_back_to_users` | 7237-7247 | внутри register_gifts |
| `admin_gift_pick_host` | 7250-7261 | внутри register_gifts |
| `admin_gift_back_to_hosts` | 7264-7276 | внутри register_gifts |
| `admin_gift_pick_days` | 7278-7344 | внутри register_gifts |

### `host_keys.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminHostKeys` | 7604-7605 | внутри register_host_keys |
| `admin_host_keys_entry` | 7608-7619 | внутри register_host_keys |
| `admin_host_keys_pick_host` | 7622-7637 | внутри register_host_keys |
| `admin_hostkeys_page` | 7640-7663 | внутри register_host_keys |
| `admin_hostkeys_back_to_hosts` | 7666-7680 | внутри register_host_keys |
| `admin_hostkeys_back_to_users` | 7683-7688 | внутри register_host_keys |

### `hosts.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminHosts` | 2064-2083 | внутри register_hosts |
| `_resolve_host_from_digest` | 2086-2102 | внутри register_hosts |
| `_safe` | 2105-2106 | внутри register_hosts |
| `_format_host_card` | 2109-2154 | внутри register_hosts |
| `show_admin_hosts_menu` | 2157-2167 | внутри register_hosts |
| `show_admin_host_detail` | 2170-2188 | внутри register_hosts |
| `show_admin_host_squads` | 2191-2208 | внутри register_hosts |
| `admin_hosts_menu` | 2212-2218 | внутри register_hosts |
| `admin_hosts_add` | 2222-2233 | внутри register_hosts |
| `admin_hosts_add_name` | 2237-2250 | внутри register_hosts |
| `admin_hosts_add_base_url` | 2254-2267 | внутри register_hosts |
| `admin_hosts_add_api_token` | 2271-2284 | внутри register_hosts |
| `admin_hosts_add_squad_uuid` | 2288-2335 | внутри register_hosts |
| `admin_hosts_open` | 2342-2370 | внутри register_hosts |
| `admin_hosts_squads_open` | 2376-2388 | внутри register_hosts |
| `admin_hosts_squad_toggle` | 2394-2420 | внутри register_hosts |
| `admin_hosts_squad_delete` | 2426-2447 | внутри register_hosts |
| `admin_hosts_squad_add` | 2451-2466 | внутри register_hosts |
| `admin_hosts_squad_add_class` | 2470-2490 | внутри register_hosts |
| `admin_hosts_squad2_uuid` | 2494-2509 | внутри register_hosts |
| `admin_hosts_squad2_label` | 2513-2557 | внутри register_hosts |
| `admin_hosts_delete` | 2561-2576 | внутри register_hosts |
| `admin_hosts_delete_confirm` | 2580-2597 | внутри register_hosts |
| `admin_hosts_rename` | 2601-2618 | внутри register_hosts |
| `admin_hosts_toggle_class` | 2622-2659 | внутри register_hosts |
| `admin_hosts_rename_input` | 2663-2684 | внутри register_hosts |
| `admin_hosts_set_url` | 2688-2704 | внутри register_hosts |
| `admin_hosts_set_url_input` | 2708-2728 | внутри register_hosts |
| `admin_hosts_set_sub` | 2732-2749 | внутри register_hosts |
| `admin_hosts_set_sub_input` | 2753-2770 | внутри register_hosts |
| `admin_hosts_set_rmw_url` | 2774-2790 | внутри register_hosts |
| `admin_hosts_set_rmw_url_input` | 2794-2814 | внутри register_hosts |
| `admin_hosts_set_rmw_token` | 2818-2835 | внутри register_hosts |
| `admin_hosts_set_rmw_token_input` | 2839-2856 | внутри register_hosts |
| `admin_hosts_set_squad` | 2860-2876 | внутри register_hosts |
| `admin_hosts_set_squad_input` | 2880-2897 | внутри register_hosts |
| `admin_hosts_set_ssh` | 2901-2921 | внутри register_hosts |
| `admin_hosts_set_ssh_input` | 2925-2982 | внутри register_hosts |
| `admin_hosts_to_plans` | 2986-3006 | внутри register_hosts |

### `key_quick_ops.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminQuickDeleteKey` | 7691-7692 | внутри register_key_quick_ops |
| `admin_delete_key_entry` | 7695-7704 | внутри register_key_quick_ops |
| `admin_delete_key_process` | 7707-7729 | внутри register_key_quick_ops |
| `AdminExtendKey` | 7732-7733 | внутри register_key_quick_ops |
| `admin_extend_key_entry` | 7736-7745 | внутри register_key_quick_ops |
| `admin_extend_key_process` | 7748-7796 | внутри register_key_quick_ops |

### `keys.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `admin_search_user_keys_handler` | 6542-6562 | внутри register_keys_1 |
| `admin_search_user_keys_input_handler` | 6565-6603 | внутри register_keys_1 |
| `admin_search_keys_page_handler` | 6606-6631 | внутри register_keys_1 |
| `admin_search_all_keys_handler` | 6634-6647 | внутри register_keys_1 |
| `admin_search_all_keys_input_handler` | 6650-6679 | внутри register_keys_1 |
| `admin_cancel_search_keys_handler` | 6682-6693 | внутри register_keys_1 |
| `admin_edit_key` | 6696-6728 | внутри register_keys_1 |
| `admin_key_delete_prompt` | 6733-6760 | внутри register_keys_1 |
| `AdminExtendSingleKey` | 6763-6764 | внутри register_keys_1 |
| `admin_key_extend_prompt` | 6767-6783 | внутри register_keys_1 |
| `admin_key_extend_process` | 6786-6843 | внутри register_keys_1 |
| `admin_key_delete_cancel` | 7013-7047 | внутри register_keys_2 |
| `admin_key_delete_confirm` | 7051-7118 | внутри register_keys_2 |
| `AdminEditKeyEmail` | 7120-7121 | внутри register_keys_2 |
| `admin_key_edit_email_start` | 7124-7139 | внутри register_keys_2 |
| `admin_key_edit_email_commit` | 7142-7156 | внутри register_keys_2 |
| `admin_key_back` | 7450-7485 | внутри register_keys_3 |

### `lte_settings.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminLteSettings` | 3256-3258 | внутри register_lte_settings |
| `_get_dual_limit_interval` | 3261-3266 | внутри register_lte_settings |
| `show_admin_lte_settings_menu` | 3269-3286 | внутри register_lte_settings |
| `admin_lte_settings_entry` | 3290-3297 | внутри register_lte_settings |
| `admin_lte_set_interval_start` | 3301-3312 | внутри register_lte_settings |
| `admin_lte_set_interval_received` | 3316-3330 | внутри register_lte_settings |

### `mailing.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `start_broadcast_handler` | 7799-7810 | внутри register_mailing |
| `broadcast_message_received_handler` | 7813-7864 | внутри register_mailing |
| `broadcast_parse_mode_handler` | 7870-7879 | внутри register_mailing |
| `add_button_choose_type` | 7883-7889 | внутри register_mailing |
| `add_button_prompt_handler` | 7892-7898 | внутри register_mailing |
| `add_functional_button_start` | 7901-7907 | внутри register_mailing |
| `functional_button_selected` | 7910-7915 | внутри register_mailing |
| `button_text_received_handler` | 7919-7925 | внутри register_mailing |
| `button_url_received_handler` | 7928-7936 | внутри register_mailing |
| `skip_button_handler` | 7939-7942 | внутри register_mailing |
| `_escape_md2` | 7944-7967 | внутри register_mailing |
| `_send_broadcast_to` | 7969-8004 | внутри register_mailing |
| `show_broadcast_preview` | 8006-8036 | внутри register_mailing |
| `confirm_broadcast_handler` | 8039-8106 | внутри register_mailing |
| `cancel_broadcast_handler` | 8109-8112 | внутри register_mailing |

### `menu.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `show_admin_menu` | 222-258 | поднят на уровень модуля |
| `show_admin_system_menu` | 365-378 | поднят на уровень модуля |
| `show_admin_settings_menu` | 381-394 | поднят на уровень модуля |
| `open_admin_menu_handler` | 454-459 | внутри register_menu_1 |
| `open_admin_system_menu_handler` | 461-466 | внутри register_menu_1 |
| `open_admin_settings_menu_handler` | 470-475 | внутри register_menu_1 |
| `admin_noop` | 7489-7490 | внутри register_menu_2 |
| `admin_cancel_handler` | 7493-7496 | внутри register_menu_2 |

### `modules.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_build_modules_keyboard` | 397-413 | поднят на уровень модуля |
| `show_admin_modules_menu` | 415-450 | поднят на уровень модуля |
| `open_admin_modules_menu_handler` | 479-485 | внутри register_modules |
| `refresh_admin_modules_menu_handler` | 488-493 | внутри register_modules |
| `admin_module_enable_handler` | 496-504 | внутри register_modules |
| `admin_module_disable_handler` | 507-515 | внутри register_modules |

### `monitor.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `admin_monitor_menu` | 8152-8183 | внутри register_monitor |
| `admin_monitor_local` | 8186-8354 | внутри register_monitor |
| `admin_monitor_host` | 8357-8462 | внутри register_monitor |
| `admin_monitor_target` | 8465-8592 | внутри register_monitor |
| `admin_monitor_detailed` | 8595-8723 | внутри register_monitor |

### `notifications.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminNotifications` | 3337-3340 | внутри register_notifications |
| `_get_inactive_reminder_enabled` | 3342-3343 | внутри register_notifications |
| `_get_inactive_reminder_interval_hours` | 3345-3355 | внутри register_notifications |
| `_get_inactive_reminder_support_url` | 3357-3359 | внутри register_notifications |
| `show_admin_notifications_menu` | 3361-3390 | внутри register_notifications |
| `admin_notifications_entry` | 3394-3401 | внутри register_notifications |
| `admin_inactive_reminder_toggle` | 3405-3413 | внутри register_notifications |
| `admin_inactive_reminder_set_interval` | 3417-3430 | внутри register_notifications |
| `admin_inactive_reminder_interval_input` | 3434-3451 | внутри register_notifications |
| `admin_inactive_reminder_set_support_url` | 3455-3469 | внутри register_notifications |
| `admin_inactive_reminder_support_url_input` | 3473-3494 | внутри register_notifications |

### `payments.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminPayments` | 1167-1168 | внутри register_payments |
| `_get_payments_status_for_admin` | 1171-1212 | внутри register_payments |
| `show_admin_payments_menu` | 1215-1225 | внутри register_payments |
| `_payment_detail_text` | 1228-1341 | внутри register_payments |
| `show_admin_payment_detail` | 1344-1353 | внутри register_payments |
| `admin_payments_menu` | 1357-1363 | внутри register_payments |
| `admin_payments_open` | 1367-1375 | внутри register_payments |
| `admin_payments_toggle` | 1379-1399 | внутри register_payments |
| `_PAYMENT_FIELD_MAP` | 1402-1424 | внутри register_payments |
| `_payment_prompt` | 1427-1468 | внутри register_payments |
| `_normalize_payment_input` | 1471-1475 | внутри register_payments |
| `admin_payments_set` | 1479-1501 | внутри register_payments |
| `admin_payments_set_value` | 1505-1542 | внутри register_payments |
| `admin_payments_yoomoney_check` | 1546-1583 | внутри register_payments |

### `plans.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminPlans` | 3499-3530 | поднят на уровень модуля |
| `_format_plan_duration` | 3536-3548 | поднят на уровень модуля |
| `_format_traffic_gb` | 3550-3564 | поднят на уровень модуля |
| `_format_devices` | 3566-3576 | поднят на уровень модуля |
| `_format_plans_for_host` | 3586-3607 | поднят на уровень модуля |
| `_plan_show_name_enabled` | 3578-3584 | внутри register_plans |
| `admin_plans_entry` | 3611-3623 | внутри register_plans |
| `admin_plans_back_to_admin` | 3627-3633 | внутри register_plans |
| `admin_plans_pick_host` | 3637-3649 | внутри register_plans |
| `_format_plan_detail` | 3652-3682 | внутри register_plans |
| `admin_plans_open_plan` | 3688-3719 | внутри register_plans |
| `_format_traffic_package_detail` | 3722-3742 | внутри register_plans |
| `admin_plan_packages_menu` | 3746-3775 | внутри register_plans |
| `admin_lte_packages_menu` | 3779-3810 | внутри register_plans |
| `admin_plan_edit_lte_limit_start` | 3814-3823 | внутри register_plans |
| `admin_plan_edit_lte_limit_received` | 3827-3869 | внутри register_plans |
| `admin_plan_edit_main_reset_price_start` | 3873-3883 | внутри register_plans |
| `admin_plan_edit_main_reset_price_received` | 3887-3928 | внутри register_plans |
| `admin_pkg_add_start` | 3932-3956 | внутри register_plans |
| `admin_pkg_size_received` | 3960-3973 | внутри register_plans |
| `admin_pkg_price_received` | 3977-4002 | внутри register_plans |
| `admin_pkg_open` | 4006-4027 | внутри register_plans |
| `admin_pkg_edit_size_start` | 4031-4040 | внутри register_plans |
| `admin_pkg_edit_size_received` | 4044-4066 | внутри register_plans |
| `admin_pkg_edit_price_start` | 4070-4079 | внутри register_plans |
| `admin_pkg_edit_price_received` | 4083-4105 | внутри register_plans |
| `admin_pkg_toggle` | 4109-4131 | внутри register_plans |
| `admin_pkg_delete` | 4135-4153 | внутри register_plans |
| `admin_plan_edit_name` | 4158-4168 | внутри register_plans |
| `admin_plan_edit_months` | 4172-4183 | внутри register_plans |
| `admin_plan_edit_price` | 4187-4197 | внутри register_plans |
| `admin_plan_edit_duration` | 4202-4212 | внутри register_plans |
| `admin_plan_duration_months` | 4216-4223 | внутри register_plans |
| `admin_plan_duration_days` | 4227-4234 | внутри register_plans |
| `admin_plan_edit_traffic` | 4238-4248 | внутри register_plans |
| `admin_plan_edit_devices` | 4252-4262 | внутри register_plans |
| `admin_plan_toggle_active` | 4266-4291 | внутри register_plans |
| `admin_plan_toggle_show_name` | 4295-4327 | внутри register_plans |
| `admin_plan_delete_start` | 4331-4341 | внутри register_plans |
| `admin_plan_delete_cancel` | 4345-4347 | внутри register_plans |
| `admin_plan_delete_confirm` | 4351-4380 | внутри register_plans |
| `admin_plan_edit_name_received` | 4384-4408 | внутри register_plans |
| `admin_plan_edit_months_received` | 4412-4441 | внутри register_plans |
| `admin_plan_edit_price_received` | 4445-4474 | внутри register_plans |
| `admin_plan_edit_days_received` | 4479-4515 | внутри register_plans |
| `admin_plan_edit_traffic_received` | 4519-4560 | внутри register_plans |
| `admin_plan_edit_devices_received` | 4564-4603 | внутри register_plans |
| `admin_plans_back_to_hosts` | 4607-4618 | внутри register_plans |
| `admin_plans_add_start` | 4622-4641 | внутри register_plans |
| `admin_plans_new_duration_months` | 4646-4657 | внутри register_plans |
| `admin_plans_new_duration_days` | 4661-4672 | внутри register_plans |
| `admin_plans_back_to_host_menu` | 4675-4697 | внутри register_plans |
| `admin_plans_plan_name_received` | 4701-4723 | внутри register_plans |
| `admin_plans_months_received` | 4727-4752 | внутри register_plans |
| `admin_plan_add_days_received` | 4757-4776 | внутри register_plans |
| `admin_plan_add_traffic_received` | 4780-4803 | внутри register_plans |
| `admin_plan_add_devices_received` | 4807-4827 | внутри register_plans |
| `admin_plans_price_received` | 4830-4888 | внутри register_plans |

### `promo.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `show_admin_promo_menu` | 260-272 | поднят на уровень модуля |
| `_parse_datetime_input` | 274-283 | поднят на уровень модуля |
| `_format_promo_line` | 285-335 | поднят на уровень модуля |
| `_build_promo_list_keyboard` | 337-363 | поднят на уровень модуля |
| `AdminPromoCreate` | 4891-4903 | внутри register_promo |
| `admin_promo_menu_handler` | 4906-4912 | внутри register_promo |
| `admin_promo_create_start` | 4915-4925 | внутри register_promo |
| `admin_promo_code_auto` | 4931-4950 | внутри register_promo |
| `admin_promo_code_custom` | 4956-4965 | внутри register_promo |
| `admin_promo_create_code` | 4968-4984 | внутри register_promo |
| `admin_promo_set_discount_type` | 4990-4999 | внутри register_promo |
| `admin_promo_set_discount_value` | 5002-5024 | внутри register_promo |
| `admin_promo_set_total_limit` | 5027-5047 | внутри register_promo |
| `admin_promo_total_limit_buttons` | 5053-5071 | внутри register_promo |
| `admin_promo_user_limit_buttons` | 5077-5095 | внутри register_promo |
| `admin_promo_set_per_user_limit` | 5098-5118 | внутри register_promo |
| `admin_promo_set_valid_from` | 5121-5135 | внутри register_promo |
| `admin_promo_valid_from_buttons` | 5147-5172 | внутри register_promo |
| `admin_promo_set_valid_until` | 5175-5194 | внутри register_promo |
| `admin_promo_valid_until_buttons` | 5206-5233 | внутри register_promo |
| `admin_promo_description` | 5236-5246 | внутри register_promo |
| `admin_promo_desc_buttons` | 5252-5269 | внутри register_promo |
| `_show_promo_confirm` | 5271-5317 | внутри register_promo |
| `admin_promo_set_segment` | 5327-5353 | внутри register_promo |
| `admin_promo_set_segment_value` | 5356-5373 | внутри register_promo |
| `admin_promo_set_plans` | 5379-5391 | внутри register_promo |
| `admin_promo_set_plans_custom` | 5394-5409 | внутри register_promo |
| `admin_promo_confirm` | 5412-5458 | внутри register_promo |
| `admin_promo_list` | 5461-5478 | внутри register_promo |
| `admin_promo_change_page` | 5481-5503 | внутри register_promo |
| `admin_promo_toggle` | 5506-5532 | внутри register_promo |

### `referral.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminReferral` | 1593-1599 | внутри register_referral |
| `_get_bool_setting` | 1602-1604 | внутри register_referral |
| `_get_float_setting` | 1607-1613 | внутри register_referral |
| `_get_referral_settings_for_admin` | 1616-1627 | внутри register_referral |
| `_format_reward_type_human` | 1630-1637 | внутри register_referral |
| `show_admin_referral_menu` | 1640-1669 | внутри register_referral |
| `admin_referral_menu_entry` | 1673-1679 | внутри register_referral |
| `admin_referral_toggle` | 1683-1691 | внутри register_referral |
| `admin_referral_toggle_days_bonus` | 1695-1703 | внутри register_referral |
| `admin_referral_set_type` | 1707-1718 | внутри register_referral |
| `admin_referral_type_chosen` | 1722-1739 | внутри register_referral |
| `admin_referral_set_percent` | 1743-1754 | внутри register_referral |
| `admin_referral_percent_input` | 1758-1773 | внутри register_referral |
| `admin_referral_set_fixed_amount` | 1777-1788 | внутри register_referral |
| `admin_referral_fixed_amount_input` | 1792-1807 | внутри register_referral |
| `admin_referral_set_start_bonus` | 1811-1822 | внутри register_referral |
| `admin_referral_start_bonus_input` | 1826-1843 | внутри register_referral |
| `admin_referral_set_min_withdrawal` | 1847-1858 | внутри register_referral |
| `admin_referral_min_withdrawal_input` | 1862-1877 | внутри register_referral |
| `admin_referral_set_discount` | 1881-1892 | внутри register_referral |
| `admin_referral_discount_input` | 1896-1911 | внутри register_referral |

### `speedtest.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `admin_speedtest_entry` | 5536-5552 | внутри register_speedtest_1 |
| `admin_speedtest_ssh_targets` | 5556-5571 | внутри register_speedtest_1 |
| `admin_speedtest_run` | 5575-5659 | внутри register_speedtest_1 |
| `admin_speedtest_run_target_hashed` | 5663-5730 | внутри register_speedtest_1 |
| `admin_speedtest_run_target` | 5734-5801 | внутри register_speedtest_1 |
| `admin_speedtest_back` | 5805-5810 | внутри register_speedtest_1 |
| `admin_speedtest_run_all` | 5814-5855 | внутри register_speedtest_1 |
| `admin_speedtest_run_all_targets` | 5859-5905 | внутри register_speedtest_1 |
| `admin_speedtest_autoinstall` | 5992-6013 | внутри register_speedtest_2 |
| `admin_speedtest_autoinstall_target` | 6017-6045 | внутри register_speedtest_2 |
| `admin_speedtest_autoinstall_target_hashed` | 6049-6075 | внутри register_speedtest_2 |

### `trial.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminTrial` | 3011-3015 | внутри register_trial |
| `_get_trial_enabled` | 3018-3019 | внутри register_trial |
| `_format_trial_value_gb` | 3022-3032 | внутри register_trial |
| `_format_trial_value_int` | 3035-3041 | внутри register_trial |
| `_get_trial_days` | 3044-3054 | внутри register_trial |
| `show_admin_trial_menu` | 3058-3095 | внутри register_trial |
| `admin_trial_entry` | 3099-3106 | внутри register_trial |
| `admin_trial_toggle` | 3110-3118 | внутри register_trial |
| `admin_trial_set_days` | 3122-3133 | внутри register_trial |
| `admin_trial_set_traffic` | 3136-3148 | внутри register_trial |
| `admin_trial_set_devices` | 3151-3163 | внутри register_trial |
| `admin_trial_set_host` | 3166-3179 | внутри register_trial |
| `admin_trial_select_host` | 3182-3191 | внутри register_trial |
| `admin_trial_days_input` | 3194-3209 | внутри register_trial |
| `admin_trial_traffic_input` | 3213-3232 | внутри register_trial |
| `admin_trial_devices_input` | 3236-3251 | внутри register_trial |

### `users.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `AdminUserSearch` | 6081-6082 | внутри register_users_1 |
| `admin_users_handler` | 6085-6113 | внутри register_users_1 |
| `admin_users_search_process` | 6117-6202 | внутри register_users_1 |
| `admin_view_user_handler` | 6205-6247 | внутри register_users_1 |
| `admin_ban_user` | 6251-6328 | внутри register_users_1 |
| `admin_unban_user` | 6381-6439 | внутри register_users_2 |
| `admin_delete_user` | 6444-6464 | внутри register_users_2 |
| `admin_user_keys` | 6467-6491 | внутри register_users_2 |
| `admin_user_referrals` | 6494-6539 | внутри register_users_2 |

### `withdrawals.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `approve_withdraw_handler` | 8116-8134 | внутри register_withdrawals |
| `decline_withdraw_handler` | 8137-8148 | внутри register_withdrawals |

## Совместимость и проверки

`admin_handlers.py` повторяет исходную прелюдию импортов дословно и
реэкспортирует все имена уровня модуля, которые в нём были. Внешняя запись
атрибута фасада (`monkeypatch.setattr(admin_handlers, "get_admin_stats", ...)`)
рассылается по доменным модулям через `_AdminHandlersFacade.__setattr__` →
`broadcast()`: до разделения такая запись была видна всем функциям файла.

PEP 562 (`__getattr__` модуля) для этого не подходит — обращение к глобальному
имени внутри функции компилируется в `LOAD_GLOBAL` и до `__getattr__` не
доходит. Поэтому единый namespace воссоздаётся явно: `_link_namespace()` после
импорта всех модулей раскладывает по ним поднятые имена.

Инварианты закреплены тестами в `tests/test_admin_router_split.py`: состав
публичного API фасада, рассылка подменённых атрибутов до конечного вызывающего,
отсутствие значениевых импортов рассылаемых имён внутри пакета, разрешимость
всех глобальных имён пакета, число хендлеров по обсерверам и состав с порядком
вызовов `register_*`.

## Известная особенность, перенесённая как есть

`admin_plan_back` вызывается в `admin_plan_delete_cancel`, но не определён
нигде в исходном файле — это был `LOAD_GLOBAL` → `NameError` и до разделения.
Разделение поведение не меняет; `test_every_global_name_in_the_package_resolves`
держит это имя в списке ожидаемых, чтобы новое неразрешимое имя не спряталось.
