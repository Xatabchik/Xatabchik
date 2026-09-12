# Карта разделения `bot/handlers.py`

Файл разделён на доменные модули пакета `src/shop_bot/bot/user_router/`.
Тела функций перенесены дословно; `handlers.py` остался фасадом и
ре-экспортирует прежний публичный API целиком, поэтому вызывающие
(`bot_controller.py`, `admin_handlers.py`, `factory_bot/service.py`, тесты)
не изменились.

Столбец «строки» — расположение в исходном `handlers.py` до разделения
(10 674 строки), чтобы перенос можно было сверить с `INVENTORY.md` и
документацией в `shop_bot_bot_handlers_part*.md`.

## Сводка

| Модуль | Назначение | Блоков кода | Строк | Регистрирует хендлеров |
| --- | --- | ---: | ---: | ---: |
| `user_router/referral.py` | Реферальная программа, реквизиты и заявки на вывод | 27 | 686 | 15 |
| `user_router/support.py` | «О сервисе», «Помощь», тикеты поддержки | 14 | 312 | 14 |
| `user_router/franchise.py` | Кабинет партнёра-франчайзи | 21 | 609 | 14 |
| `user_router/purchase.py` | Покупка и продление: хост, тариф, почта, промокод, выбор способа оплаты | 14 | 428 | 14 |
| `user_router/traffic_topup.py` | Докупка ГБ основного трафика и её оплата | 13 | 460 | 11 |
| `user_router/lte_topup.py` | Докупка LTE-трафика и её оплата | 13 | 464 | 11 |
| `user_router/onboarding.py` | `/start` с deep-link, онбординг, капча, главное меню | 10 | 453 | 10 |
| `user_router/key_manage.py` | Список ключей, поиск, переименование | 10 | 421 | 10 |
| `user_router/howto.py` | Инструкции по подключению | 10 | 308 | 10 |
| `user_router/key_view.py` | Пробный период, карточка ключа, автопродление, смена сервера, устройства | 10 | 672 | 9 |
| `user_router/payment_create.py` | Создание платежа выбранным способом | 10 | 744 | 9 |
| `user_router/balance_topup.py` | Пополнение баланса, оплата звёздами Telegram | 8 | 448 | 8 |
| `user_router/profile_gifts.py` | Профиль и полученные подарки | 7 | 380 | 7 |
| `user_router/topup_methods.py` | Выбор способа пополнения баланса | 5 | 266 | 5 |
| `user_router/main_reset.py` | Досрочный сброс основного пула и его оплата | 6 | 215 | 4 |
| `user_router/payment_checks.py` | Кнопки «Проверить оплату» | 4 | 345 | 4 |
| `user_router/providers.py` | Rollypay, Platega, ЮMoney: ссылки на оплату | 11 | 253 | 2 |
| `user_router/gift_catcher.py` | Приём username получателя подарка текстом | 1 | 156 | 1 |
| `user_router/_core.py` | Состояние уровня модуля, записываемое `bot_controller.py`, и сбор способов оплаты | 9 | 93 | — |
| `user_router/key_errors.py` | Классификация ошибок выдачи ключа, уведомления, откат неоплаченной выдачи | 10 | 370 | — |
| `user_router/formatting.py` | Подписи тарифов и сроков, расчёт дней, валидация почты | 5 | 89 | — |
| `user_router/share_links.py` | Ссылки-приглашения и подарочные ссылки, тексты «Поделиться» | 8 | 89 | — |
| `user_router/referral_bonus.py` | День за пробный период приглашённого | 1 | 163 | — |
| `user_router/gift_activation.py` | Активация подарочного кода | 1 | 103 | — |
| `user_router/payment_providers.py` | Запросы к Heleket и CryptoBot | 3 | 377 | — |
| `user_router/states.py` | Группы состояний FSM | 13 | 92 | — |
| `user_router/menu.py` | Главное меню, капча, онбординг, декоратор `registration_required` | 5 | 320 | — |
| `user_router/fulfillment.py` | Единая обработка успешного платежа и уведомление администраторов | 2 | 1419 | — |
| `user_router/key_info.py` | Сведения о ключе из панели: устройства, трафик, тариф, синхронизация | 10 | 702 | — |
| **итого** | | **261** | | **158** |

## Порядок сборки роутера

`router.py` вызывает `register_*` строго в порядке блоков исходного файла.
Порядок значим: aiogram проверяет хендлеры одного типа события в порядке
регистрации, поэтому перестановка блоков изменила бы, какой хендлер поймает
апдейт первым.

1. `register_onboarding`
2. `register_profile_gifts`
3. `register_traffic_topup`
4. `register_lte_topup`
5. `register_main_reset`
6. `register_balance_topup`
7. `register_providers`
8. `register_payment_checks`
9. `register_topup_methods`
10. `register_referral`
11. `register_support`
12. `register_key_manage`
13. `register_key_view`
14. `register_howto`
15. `register_purchase`
16. `register_payment_create`
17. `register_gift_catcher`
18. `register_franchise`

## Полная карта: определение → файл

`внутри register_*` — код перенесён дословно, включая отступ, и остался
вложенной функцией. `поднят на уровень модуля` — функция вызывается из
другого блока, поэтому вынесена на уровень модуля со сдвигом отступа на 4
пробела; тело не тронуто.

### `_core.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `TELEGRAM_BOT_USERNAME` | 118-119 | уровень модуля |
| `PAYMENT_METHODS` | 120-120 | уровень модуля |
| `_is_true` | 121-123 | уровень модуля |
| `_get_payment_methods` | 124-175 | уровень модуля |
| `ADMIN_ID` | 176-177 | уровень модуля |
| `CRYPTO_BOT_TOKEN` | 178-178 | уровень модуля |
| `PENDING_GIFTS` | 179-180 | уровень модуля |
| `logger` | 181-181 | уровень модуля |
| `errors` | 182-187 | уровень модуля |

### `balance_topup.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `topup_start_handler` | 3398-3407 | внутри register_balance_topup |
| `topup_amount_input` | 3408-3432 | внутри register_balance_topup |
| `topup_pay_yookassa` | 3433-3516 | внутри register_balance_topup |
| `create_stars_invoice_handler` | 3517-3609 | внутри register_balance_topup |
| `payment_stars_back_handler` | 3610-3669 | внутри register_balance_topup |
| `topup_stars_handler` | 3670-3718 | внутри register_balance_topup |
| `pre_checkout_handler` | 3719-3741 | внутри register_balance_topup |
| `stars_success_handler` | 3742-3804 | внутри register_balance_topup |

### `formatting.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_format_duration_label` | 530-543 | уровень модуля |
| `_compute_days_to_add` | 544-557 | уровень модуля |
| `_tariff_label_from_origin` | 558-570 | уровень модуля |
| `_build_key_origin_meta` | 571-600 | уровень модуля |
| `is_valid_email` | 1330-1334 | уровень модуля |

### `franchise.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_kb_cancel_factory` | 8717-8727 | внутри register_franchise |
| `_kb_partner_cabinet` | 8728-8736 | внутри register_franchise |
| `_kb_partner_withdraw` | 8737-8742 | внутри register_franchise |
| `_kb_partner_requisites` | 8743-8760 | внутри register_franchise |
| `_kb_partner_requisite_input` | 8761-8766 | внутри register_franchise |
| `_mask_requisite` | 8767-8779 | внутри register_franchise |
| `_infer_requisite_type` | 8780-8789 | внутри register_franchise |
| `partner_requisites` | 8790-8824 | внутри register_franchise |
| `partner_requisite_add` | 8825-8844 | внутри register_franchise |
| `partner_requisite_cancel` | 8845-8860 | внутри register_franchise |
| `partner_requisite_bank` | 8861-8885 | внутри register_franchise |
| `partner_requisite_value` | 8886-8933 | внутри register_franchise |
| `partner_requisite_set_default` | 8934-8966 | внутри register_franchise |
| `partner_requisite_delete` | 8967-8998 | внутри register_franchise |
| `franchise_create_bot` | 8999-9024 | внутри register_franchise |
| `franchise_cancel` | 9025-9037 | внутри register_franchise |
| `franchise_receive_token` | 9038-9100 | внутри register_franchise |
| `partner_cabinet` | 9101-9132 | внутри register_franchise |
| `partner_withdraw` | 9133-9170 | внутри register_franchise |
| `partner_withdraw_cancel` | 9171-9187 | внутри register_franchise |
| `partner_withdraw_amount` | 9188-9294 | внутри register_franchise |

### `fulfillment.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `notify_admin_of_purchase` | 9296-9402 | уровень модуля |
| `process_successful_payment` | 9403-10666 | уровень модуля |

### `gift_activation.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_activate_gift_directly` | 813-903 | уровень модуля |

### `gift_catcher.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_gift_username_catcher` | 8588-8716 | внутри register_gift_catcher |

### `howto.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `show_instruction_handler` | 7200-7212 | внутри register_howto |
| `show_instruction_handler` | 7213-7224 | внутри register_howto |
| `howto_android_handler` | 7225-7272 | внутри register_howto |
| `howto_android_key_handler` | 7273-7300 | внутри register_howto |
| `howto_ios_handler` | 7301-7322 | внутри register_howto |
| `howto_ios_key_handler` | 7323-7350 | внутри register_howto |
| `howto_windows_handler` | 7351-7402 | внутри register_howto |
| `howto_windows_key_handler` | 7403-7434 | внутри register_howto |
| `howto_linux_handler` | 7435-7459 | внутри register_howto |
| `howto_linux_key_handler` | 7460-7490 | внутри register_howto |

### `key_errors.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_classify_key_creation_error` | 188-213 | уровень модуля |
| `_format_key_action_label` | 214-228 | уровень модуля |
| `_log_key_creation_error` | 229-240 | уровень модуля |
| `_notify_admins_key_creation_error` | 241-268 | уровень модуля |
| `_notify_user_key_creation_error` | 269-308 | уровень модуля |
| `_handle_key_creation_failure` | 309-329 | уровень модуля |
| `_abort_topup_fulfillment` | 330-413 | уровень модуля |
| `_notify_admins_topup_desync` | 414-453 | уровень модуля |
| `_abort_key_fulfillment` | 454-514 | уровень модуля |
| `_safe_edit_or_answer` | 515-529 | уровень модуля |

### `key_info.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_remnawave_key_exists` | 5503-5526 | поднят на уровень модуля |
| `_extract_connected_devices` | 5527-5654 | поднят на уровень модуля |
| `_get_connected_devices_count` | 5655-5732 | поднят на уровень модуля |
| `_get_devices_list` | 5733-5786 | поднят на уровень модуля |
| `_is_key_without_billing_plan` | 5787-5818 | поднят на уровень модуля |
| `_resolve_plan_id_for_key` | 5819-5855 | поднят на уровень модуля |
| `_extract_traffic_used_bytes` | 5856-5877 | поднят на уровень модуля |
| `_format_bytes_gb` | 5878-5884 | поднят на уровень модуля |
| `_get_tariff_info_for_key` | 5885-6088 | поднят на уровень модуля |
| `sync_user_keys_with_remnawave` | 6089-6170 | поднят на уровень модуля |

### `key_manage.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `manage_keys_handler` | 6171-6194 | внутри register_key_manage |
| `sent_gifts_handler` | 6195-6211 | внутри register_key_manage |
| `search_my_keys_handler` | 6212-6221 | внутри register_key_manage |
| `search_keys_input_handler` | 6222-6251 | внутри register_key_manage |
| `search_keys_page_handler` | 6252-6275 | внутри register_key_manage |
| `cancel_search_keys_handler` | 6276-6289 | внутри register_key_manage |
| `rename_key_start` | 6290-6337 | внутри register_key_manage |
| `rename_key_process` | 6338-6430 | внутри register_key_manage |
| `remove_key_name` | 6431-6505 | внутри register_key_manage |
| `cancel_rename_key` | 6506-6568 | внутри register_key_manage |

### `key_view.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `trial_period_handler` | 6569-6603 | внутри register_key_view |
| `trial_host_selection_handler` | 6604-6610 | внутри register_key_view |
| `process_trial_key_creation` | 6611-6720 | внутри register_key_view |
| `show_key_handler` | 6721-6872 | внутри register_key_view |
| `auto_renew_key_toggle` | 6873-6894 | внутри register_key_view |
| `toggle_auto_renew_profile` | 6895-6908 | внутри register_key_view |
| `switch_server_start` | 6909-6939 | внутри register_key_view |
| `select_host_for_switch` | 6940-7075 | внутри register_key_view |
| `show_qr_handler` | 7076-7097 | внутри register_key_view |
| `delete_device_handler` | 7098-7199 | внутри register_key_view |

### `lte_topup.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_resolve_plan_for_lte_topup` | 2790-2801 | внутри register_lte_topup |
| `lte_gb_start_handler` | 2802-2836 | внутри register_lte_topup |
| `lte_gb_pick_handler` | 2837-2884 | внутри register_lte_topup |
| `_lte_gb_metadata` | 2885-2897 | внутри register_lte_topup |
| `ltegb_pay_balance_handler` | 2898-2917 | внутри register_lte_topup |
| `ltegb_pay_referral_balance_handler` | 2918-2937 | внутри register_lte_topup |
| `ltegb_pay_yookassa_handler` | 2938-2992 | внутри register_lte_topup |
| `ltegb_pay_platega_handler` | 2993-3027 | внутри register_lte_topup |
| `ltegb_pay_rollypay_handler` | 3028-3065 | внутри register_lte_topup |
| `ltegb_pay_heleket_handler` | 3066-3104 | внутри register_lte_topup |
| `ltegb_pay_cryptobot_handler` | 3105-3144 | внутри register_lte_topup |
| `ltegb_pay_yoomoney_handler` | 3145-3175 | внутри register_lte_topup |
| `ltegb_pay_stars_handler` | 3176-3215 | внутри register_lte_topup |

### `main_reset.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_resolve_key_for_main_reset` | 3216-3221 | внутри register_main_reset |
| `main_reset_start_handler` | 3222-3292 | внутри register_main_reset |
| `_main_reset_metadata` | 3293-3303 | внутри register_main_reset |
| `mainreset_pay_balance_handler` | 3304-3323 | внутри register_main_reset |
| `mainreset_pay_referral_balance_handler` | 3324-3343 | внутри register_main_reset |
| `mainreset_pay_yookassa_handler` | 3344-3397 | внутри register_main_reset |

### `menu.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `show_captcha` | 1335-1375 | уровень модуля |
| `show_main_menu` | 1376-1506 | уровень модуля |
| `process_successful_onboarding` | 1507-1529 | уровень модуля |
| `registration_required` | 1530-1544 | уровень модуля |
| `_maybe_pay_referral_start_bonus` | 1545-1619 | уровень модуля |

### `onboarding.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `start_handler` | 1622-1778 | внутри register_onboarding |
| `check_subscription_handler` | 1779-1806 | внутри register_onboarding |
| `onboarding_fallback_handler` | 1807-1810 | внутри register_onboarding |
| `captcha_answer_handler` | 1811-1900 | внутри register_onboarding |
| `captcha_button_answer_handler` | 1901-1998 | внутри register_onboarding |
| `cancel_captcha_handler` | 1999-2005 | внутри register_onboarding |
| `main_menu_handler` | 2006-2010 | внутри register_onboarding |
| `back_to_main_menu_handler` | 2011-2016 | поднят на уровень модуля |
| `open_main_menu_handler` | 2017-2022 | внутри register_onboarding |
| `show_main_menu_cb` | 2023-2028 | внутри register_onboarding |

### `payment_checks.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `check_platega_payment_handler` | 4023-4079 | внутри register_payment_checks |
| `check_rollypay_payment_handler` | 4080-4157 | внутри register_payment_checks |
| `check_yookassa_payment_handler` | 4158-4250 | внутри register_payment_checks |
| `check_pending_payment_handler` | 4251-4337 | внутри register_payment_checks |

### `payment_create.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `create_yookassa_payment_handler` | 7886-8022 | внутри register_payment_create |
| `pay_platega_handler` | 8023-8111 | внутри register_payment_create |
| `pay_rollypay_handler` | 8112-8199 | внутри register_payment_create |
| `create_cryptobot_invoice_handler` | 8200-8276 | внутри register_payment_create |
| `check_crypto_invoice_handler` | 8277-8404 | внутри register_payment_create |
| `create_ton_invoice_handler` | 8405-8474 | внутри register_payment_create |
| `pay_with_main_balance_handler` | 8475-8520 | внутри register_payment_create |
| `pay_with_referral_balance_handler` | 8521-8562 | внутри register_payment_create |
| `_STALE_PAY_CALLBACKS` | 8563-8575 | внутри register_payment_create |
| `stale_payment_method_callback` | 8576-8587 | внутри register_payment_create |

### `payment_providers.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_create_heleket_payment_request` | 904-1016 | уровень модуля |
| `create_cryptobot_api_invoice` | 1017-1065 | уровень модуля |
| `_create_cryptobot_invoice` | 1066-1261 | уровень модуля |

### `profile_gifts.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `profile_handler_callback` | 2029-2102 | поднят на уровень модуля |
| `toggle_expiry_notifications_handler` | 2103-2117 | внутри register_profile_gifts |
| `show_inactive_gifts_handler` | 2118-2142 | внутри register_profile_gifts |
| `gifts_page_handler` | 2143-2173 | внутри register_profile_gifts |
| `show_gift_handler` | 2174-2263 | внутри register_profile_gifts |
| `send_gift_link_handler` | 2264-2329 | внутри register_profile_gifts |
| `activate_own_gift_handler` | 2330-2366 | внутри register_profile_gifts |

### `providers.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_rollypay_is_enabled` | 3805-3812 | поднят на уровень модуля |
| `_create_rollypay_payment_link` | 3813-3829 | поднят на уровень модуля |
| `_platega_is_enabled` | 3830-3832 | поднят на уровень модуля |
| `_platega_get_base_url` | 3833-3835 | поднят на уровень модуля |
| `_platega_get_method_code` | 3836-3849 | поднят на уровень модуля |
| `_platega_request` | 3850-3875 | поднят на уровень модуля |
| `_create_platega_payment_link` | 3876-3891 | поднят на уровень модуля |
| `_get_platega_transaction` | 3892-3896 | поднят на уровень модуля |
| `_build_yoomoney_link` | 3897-3912 | поднят на уровень модуля |
| `pay_yoomoney_handler` | 3913-3972 | внутри register_providers |
| `topup_yoomoney_handler` | 3973-4022 | внутри register_providers |

### `purchase.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `gift_new_key_handler` | 7491-7504 | внутри register_purchase |
| `buy_new_key_handler` | 7505-7518 | внутри register_purchase |
| `select_host_for_purchase_handler` | 7519-7532 | внутри register_purchase |
| `select_host_for_gift_handler` | 7533-7545 | внутри register_purchase |
| `extend_key_handler` | 7546-7586 | внутри register_purchase |
| `plan_selection_handler` | 7587-7612 | внутри register_purchase |
| `back_to_plans_handler` | 7613-7677 | внутри register_purchase |
| `process_email_handler` | 7678-7686 | внутри register_purchase |
| `skip_email_handler` | 7687-7692 | внутри register_purchase |
| `show_payment_options` | 7693-7818 | поднят на уровень модуля |
| `back_to_email_prompt_handler` | 7819-7832 | внутри register_purchase |
| `prompt_promo_code` | 7833-7841 | внутри register_purchase |
| `cancel_promo_entry` | 7842-7846 | внутри register_purchase |
| `handle_promo_code_input` | 7847-7885 | внутри register_purchase |

### `referral.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `referral_program_handler` | 4574-4682 | внутри register_referral |
| `referral_top_handler` | 4683-4732 | внутри register_referral |
| `_ref_is_true` | 4733-4741 | внутри register_referral |
| `_ref_float_setting` | 4742-4748 | внутри register_referral |
| `_ref_withdraw_enabled` | 4749-4751 | внутри register_referral |
| `_ref_method_enabled` | 4752-4758 | внутри register_referral |
| `_ref_sbp_banks` | 4759-4762 | внутри register_referral |
| `_REF_METHOD_LABELS` | 4763-4764 | внутри register_referral |
| `_ref_mask` | 4765-4772 | внутри register_referral |
| `_kb_my_balance` | 4773-4784 | внутри register_referral |
| `referral_my_balance` | 4785-4796 | внутри register_referral |
| `_REF_STATUS_LABELS` | 4797-4803 | внутри register_referral |
| `referral_withdraw_requests` | 4804-4836 | внутри register_referral |
| `referral_transfer_start` | 4837-4861 | внутри register_referral |
| `referral_transfer_amount` | 4862-4921 | внутри register_referral |
| `_kb_payout_methods` | 4922-4937 | внутри register_referral |
| `referral_payout_methods` | 4938-4964 | внутри register_referral |
| `_kb_method_types` | 4965-4976 | внутри register_referral |
| `referral_payout_method_add` | 4977-4990 | внутри register_referral |
| `_kb_bank_choice` | 4991-4998 | внутри register_referral |
| `referral_payout_method_add_type` | 4999-5020 | внутри register_referral |
| `referral_payout_method_bank_choice` | 5021-5038 | внутри register_referral |
| `referral_payout_method_value` | 5039-5064 | внутри register_referral |
| `referral_payout_method_delete` | 5065-5090 | внутри register_referral |
| `referral_withdraw_start` | 5091-5135 | внутри register_referral |
| `referral_withdraw_choose_method` | 5136-5161 | внутри register_referral |
| `referral_withdraw_amount` | 5162-5215 | внутри register_referral |

### `referral_bonus.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `grant_referrer_day_bonus_for_trial` | 601-742 | уровень модуля |

### `share_links.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_webapp_public_base` | 743-759 | уровень модуля |
| `_build_gift_links` | 760-771 | уровень модуля |
| `_build_referral_links` | 772-784 | уровень модуля |
| `DEFAULT_REFERRAL_SHARE_TEXT` | 785-787 | уровень модуля |
| `DEFAULT_GIFT_SHARE_TEXT` | 788-788 | уровень модуля |
| `_referral_share_text` | 789-794 | уровень модуля |
| `_gift_share_text` | 795-800 | уровень модуля |
| `_telegram_share_url` | 801-812 | уровень модуля |

### `states.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `KeyPurchase` | 1262-1265 | уровень модуля |
| `Captcha` | 1266-1268 | уровень модуля |
| `Onboarding` | 1269-1271 | уровень модуля |
| `PaymentProcess` | 1272-1277 | уровень модуля |
| `TopUpProcess` | 1278-1282 | уровень модуля |
| `TrafficGbTopUp` | 1283-1287 | уровень модуля |
| `LteGbTopUp` | 1288-1292 | уровень модуля |
| `MainPoolReset` | 1293-1296 | уровень модуля |
| `SupportDialog` | 1297-1302 | уровень модуля |
| `TOKEN_RE` | 1303-1309 | уровень модуля |
| `FranchiseStates` | 1310-1316 | уровень модуля |
| `KeyManagement` | 1317-1320 | уровень модуля |
| `ReferralWithdraw` | 1321-1329 | уровень модуля |

### `support.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `about_handler` | 5216-5236 | внутри register_support |
| `user_speedtest_last_handler` | 5237-5288 | внутри register_support |
| `about_handler` | 5289-5309 | внутри register_support |
| `support_menu_handler` | 5310-5330 | внутри register_support |
| `support_external_handler` | 5331-5350 | внутри register_support |
| `support_new_ticket_handler` | 5351-5363 | внутри register_support |
| `support_subject_received` | 5364-5376 | внутри register_support |
| `support_message_received` | 5377-5389 | внутри register_support |
| `support_my_tickets_handler` | 5390-5402 | внутри register_support |
| `support_view_ticket_handler` | 5403-5415 | внутри register_support |
| `support_reply_prompt_handler` | 5416-5429 | внутри register_support |
| `support_reply_received` | 5430-5442 | внутри register_support |
| `forum_thread_message_handler` | 5443-5489 | внутри register_support |
| `support_close_ticket_handler` | 5490-5502 | внутри register_support |

### `topup_methods.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `topup_pay_platega` | 4338-4382 | внутри register_topup_methods |
| `topup_pay_rollypay` | 4383-4430 | внутри register_topup_methods |
| `topup_pay_heleket_like` | 4431-4469 | внутри register_topup_methods |
| `topup_pay_cryptobot` | 4470-4508 | внутри register_topup_methods |
| `topup_pay_tonconnect` | 4509-4573 | внутри register_topup_methods |

### `traffic_topup.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `_resolve_plan_for_traffic_topup` | 2367-2378 | внутри register_traffic_topup |
| `traffic_gb_start_handler` | 2379-2411 | внутри register_traffic_topup |
| `traffic_gb_pick_handler` | 2412-2458 | внутри register_traffic_topup |
| `_traffic_gb_metadata` | 2459-2471 | внутри register_traffic_topup |
| `trafficgb_pay_balance_handler` | 2472-2491 | внутри register_traffic_topup |
| `trafficgb_pay_referral_balance_handler` | 2492-2511 | внутри register_traffic_topup |
| `trafficgb_pay_yookassa_handler` | 2512-2566 | внутри register_traffic_topup |
| `trafficgb_pay_platega_handler` | 2567-2601 | внутри register_traffic_topup |
| `trafficgb_pay_rollypay_handler` | 2602-2639 | внутри register_traffic_topup |
| `trafficgb_pay_heleket_handler` | 2640-2678 | внутри register_traffic_topup |
| `trafficgb_pay_cryptobot_handler` | 2679-2718 | внутри register_traffic_topup |
| `trafficgb_pay_yoomoney_handler` | 2719-2749 | внутри register_traffic_topup |
| `trafficgb_pay_stars_handler` | 2750-2789 | внутри register_traffic_topup |

### `handlers.py`

| Определение | Строки в исходнике | Как перенесено |
| --- | --- | --- |
| `<unknown-callback-fallback>` | 10667-10674 | остаётся в фасаде |


## Заметки о переносе

### Что изменилось, кроме расположения кода

`get_user_router` была одной функцией на 7676 строк с 201 вложенным
определением. Вложенные функции нельзя просто разложить по файлам: 53 имени из
области видимости фабрики использовались другими вложенными функциями, то есть
это были замыкания, а не независимые обработчики.

Поэтому каждый блок обработчиков перенесён целиком в функцию
`register_<блок>(user_router)` — отступ там тот же, что был внутри фабрики,
и код (включая строки `@user_router.…`) перенесён дословно. Замыкания внутри
блока сохранились как замыкания.

Из 203 определений фабрики на уровень модуля поднято 22 — те, что вызываются
из другого блока, плюс их собственные зависимости:

* 20 хелперов (`providers.py`, `key_info.py`, `show_payment_options`) —
  сдвинуты на 4 пробела, тела не тронуты;
* 2 обработчика (`back_to_main_menu_handler`, `profile_handler_callback`) —
  дополнительно у них снят декоратор `@user_router.callback_query(...)`, а
  регистрация стала явным вызовом `user_router.callback_query(...)(handler)` на
  том же месте блока. Это в точности то, что делает декоратор aiogram, и
  позиция регистрации сохранена.

Остальные 180 определений перенесены дословно внутрь `register_*`.

### Что осталось без изменений

* Публичный API: из 196 имён `handlers.*` не пропало ни одно. Добавились 22
  поднятых имени (раньше были вложенными и снаружи не существовали) и 4
  служебных с подчёркиванием (`_sys`, `_types`, `_pkg`, `_HandlersFacade`).
* Логгер: имя задано строкой `"shop_bot.bot.handlers"`, а не через `__name__`,
  чтобы записи в логах не поменяли источник.
* Порядок регистрации: 158 хендлеров в тех же позициях. Сверено снимком
  роутера до и после разделения — совпали позиции, фильтры, флаги и хеши тел.
* Тела определений: у 240 из 248 AST совпадает побайтово. Отличаются 8
  поднятых хелперов из `key_info.py` — у них сдвинут отступ в продолжении
  докстринга, что для функции уровня модуля и правильно; тела идентичны.

### Найденное при переносе, но не исправленное

В конце `handlers.py` был блок:

```python
# fallback for unknown callbacks
try:
    router.callback_query.register(handle_unknown_callback)
except Exception:
    pass
```

Имени `router` на уровне модуля нет и не было, поэтому блок всегда падал с
`NameError` и сразу гасил его в `except` — обработчик неизвестных коллбэков не
регистрировался никогда. Блок перенесён в фасад дословно: это существующий
дефект, а не следствие разделения, и правка логики в задачу не входила.

### Почему модули пакета не импортируют имена друг у друга

`handlers.py` был одним пространством имён, и код внутри функций обращается к
соседям просто по имени. Вместо правки тел пространства имён связываются в
`user_router/__init__.py` после импорта всех модулей, а записи атрибутов фасада
рассылаются по модулям через `broadcast`. Это нужно для трёх имён, которые
`bot_controller.py` проставляет уже после старта (`PAYMENT_METHODS`,
`TELEGRAM_BOT_USERNAME`, `ADMIN_ID`), и для подмен в тестах
(`process_successful_payment`, `deduct_from_balance`). Инварианты закреплены в
`tests/test_handlers_module_split_namespace.py`.

Единственное исключение — `from .menu import registration_required` в
`onboarding.py` и `profile_gifts.py`: этот декоратор применяется в момент
импорта модуля, то есть до связывания пространств имён. Имя неизменяемое и
нигде не подменяется.
