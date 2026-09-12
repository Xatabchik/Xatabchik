# Комментарии: `src/shop_bot/bot/keyboards.py`

Inline- и reply-клавиатуры пользовательского и админского бота. Модульного docstring нет.

Именование: `create_<экран>_keyboard`. Обёртки `create_dynamic_*` читают `get_button_configs` и падают на статику, если конструктор пуст.

Повторяющиеся префиксы `callback_data` (неочевидные):

| Префикс / шаблон | Где |
|------------------|-----|
| `admin_payments_open:`, `admin_payments_set:`, `admin_payments_toggle:` | карточка платежки |
| `admin_hosts_open:{sha1[:12]}` | хост по дайджесту, не по имени |
| `stt:{sha1}`, `stti:{sha1}` | SSH-цели speedtest (полный sha1, не `[:12]`) |
| `pay_*` / `topup_pay_*` / `trafficgb_pay_*` / `ltegb_pay_*` / `mainreset_pay_*` | выбор способа оплаты |
| `check_pending:`, `check_yookassa:`, `check_platega:`, `check_rollypay:`, `check_crypto_invoice:` | «Проверить оплату» |
| `buy_{host}_{plan_id}_{action}_{key_id}` | выбор тарифа |
| `select_host_{action}_{host_name}` | выбор хоста при покупке |
| `admin_promo_limit_total_*` / `admin_promo_limit_user_*` | лимиты промокода |
| `captcha_answer:{emoji}` | кнопочная капча |
| `broadcast_action:{cb}` | действие кнопки рассылки |

Витрина оплаты (`create_payment_method_keyboard` и аналоги) **сама** читает `get_setting` и почти игнорирует переданный `payment_methods`. Cryptobot перекрывает Heleket (`elif`). YooKassa+СБП — тот же callback, другой текст.

После `create_main_reset_payment_method_keyboard` (1654–1657) висит мёртвый блок с docstring «Клавиатура для отмены поиска ключей пользователя» и кнопкой `cancel_search_keys` — без `def`, не вызывается.

---

## Константы модуля

### `SUPPORT_URL` (17–25)

Считается **на импорте**. Сырое значение: `support_bot_username` или `support_user`. Если не пусто и не начинается с `http`/`tg:` — оборачивается в `https://t.me/{без @}`. Иначе берётся как есть (может быть пустой строкой).

### `main_reply_keyboard` (58–61)

Единственная Reply-клавиатура файла: одна кнопка «🏠 Главное меню», `resize_keyboard=True`. Текстовый хендлер ловит этот лейбл.

### `BROADCAST_ACTIONS_MAP` (2485–2495)

Словарь callback → подпись для кнопки «из функционала» в рассылке: `show_profile`, `manage_keys`, `buy_new_key`, `gift_new_key`, `top_up_start`, `show_referral_program`, `show_help`, `show_about`, `admin_menu`.

---

## `_normalize_url` (28–37)

**Docstring в коде:** нет

```
"""Нормализовать URL: пустое → ''; http/https/tg:// оставить; @user → t.me; иначе приписать https://."""
```

`t.me/xxx` без схемы получит `https://` спереди (`https://t.me/xxx`).

## `_get_notifications_support_url` (40–43)

**Docstring в коде:** есть

```
Support URL for inactive usage reminder notifications (admin-configurable).
```

`inactive_usage_reminder_support_url` через `_normalize_url`, иначе `SUPPORT_URL`.

## `_ru_days` (46–56)

**Docstring в коде:** есть

```
Русское склонение слова "день".

1 день, 2/3/4 дня, 5-20 дней, 21 день, 22 дня, 25 дней, ...
```

## `create_main_menu_keyboard` (63–169)

**Docstring в коде:** нет

```
"""Главное меню: триал, кабинет партнёра, профиль, ключи/покупка, подарки, подарить, пополнение, баланс, рефералка, клон, поддержка, о проекте, скорость, howto, админка.

Тексты кнопок — get_setting(btn_*_text) с фолбэками. Обычные ключи (tag не user_gift/gift) vs подарки считаются отдельно.
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 74–75 | trial_available | `get_trial` отдельной строкой |
| 78–79 | show_partner_cabinet | `partner_cabinet` (клоны франшизы) |
| 103–111 | keys_count > 0 | `manage_keys` + отдельная `buy_new_key`; иначе одна `buy_new_key` вместо «Мои ключи» |
| 114–115 | gifts_count > 0 | `show_inactive_gifts` со счётчиком |
| 125–129 | show_create_bot и franchise_settings() | `factory_create_bot`; ленивый импорт webhook_server |
| 140–141 | is_admin | `admin_menu` |
| 145–167 | layout | триал / кабинет / админ — по 1 в ряд; остальные сетка 2 |

Остальные всегда: `show_profile`, `gift_new_key`, `top_up_start`, `referral_my_balance`, `show_referral_program`, `show_help`, `show_about`, `user_speedtest_last`, `howto_vless`.

## `create_admin_menu_keyboard` (171–186)

**Docstring в коде:** нет

```
"""Корневое админ-меню: admin_users, admin_gift_key, admin_host_keys, admin_promo_menu, admin_system_menu, admin_settings_menu, start_broadcast, back_to_main_menu."""
```

`adjust(2, 2, 2, 1, 1, 1)`.

## `create_admin_system_menu_keyboard` (189–197)

**Docstring в коде:** нет

```
"""Подменю «Система»: admin_speedtest, admin_monitor, admin_backup_db, admin_restore_db, admin_menu."""
```

## `create_admin_settings_menu_keyboard` (201–218)

**Docstring в коде:** нет

```
"""Подменю «Настройки»: админы, тарифы, хосты, платежки, рефералка, франшиза, модули, триал, уведомления, капча, LTE, конструктор кнопок, автопродление, назад в admin_menu."""
```

Callbacks: `admin_admins_menu`, `admin_plans`, `admin_hosts_menu`, `admin_payments_menu`, `admin_referral`, `admin_franchise`, `admin_modules`, `admin_trial`, `admin_notifications_menu`, `admin_captcha_settings`, `admin_lte_settings_menu`, `admin_btn_constructor`, `admin_auto_renew`, `admin_menu`.

## `create_admin_lte_settings_keyboard` (221–227)

**Docstring в коде:** нет

```
"""Одна кнопка интервала dual-limit (admin_lte_set_interval) и назад в admin_settings_menu."""
```

Текст кнопки включает `dual_limit_interval_sec`.

## `create_admin_payments_menu_keyboard` (230–245)

**Docstring в коде:** есть

```
Меню выбора платежной системы.
```

Кнопки `admin_payments_open:{provider}` для yookassa/heleket/platega/cryptobot/tonconnect/stars/yoomoney; назад `admin_settings_menu`. Индикатор 🟢/🔴 из `status[key]`.

### `create_admin_payments_menu_keyboard._mark` (232–233)

**Docstring в коде:** нет

```
"""🟢 если status[key] истинно, иначе 🔴."""
```

## `create_admin_payment_detail_keyboard` (248–296)

**Docstring в коде:** есть

```
Клавиатура управления конкретной платежкой.
```

Набор полей и `adjust` зависят от `provider`. Общая кнопка «Назад» — `admin_payments_menu`. Неизвестный provider → только «Назад».

| Строки | Блок | Зачем |
|--------|------|--------|
| 253–259 | yookassa | set receipt_email/shop_id/secret_key; toggle СБП по `flags.sbp_enabled` |
| 260–262 | cryptobot | token |
| 263–267 | heleket | merchant_id, api_key, domain |
| 268–273 | platega | base_url, merchant_id, secret, active_methods |
| 274–277 | tonconnect | wallet, tonapi |
| 278–282 | stars | toggle `flags.stars_enabled`; set ratio |
| 283–293 | yoomoney | toggle + wallet/secret/api_token/client_id/client_secret/redirect_uri + `admin_payments_yoomoney_check` |

Префиксы: `admin_payments_set:{provider}:{field}`, `admin_payments_toggle:{sbp|stars|yoomoney}`.

## `create_admin_payments_cancel_keyboard` (299–302)

**Docstring в коде:** нет

```
"""Одна кнопка «Отмена» с переданным back_callback."""
```

## `create_admin_referral_settings_keyboard` (305–338)

**Docstring в коде:** нет

```
"""Настройки рефералки: toggle вкл/выкл и бонуса +1 день, тип начисления, % / фикс / старт / скидка / мин. вывод, назад в admin_settings_menu."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 313–314 | enabled | текст «Выключить» / «Включить»; callback `admin_referral_toggle` |
| 316–317 | days_bonus_enabled | `admin_referral_toggle_days_bonus` |
| 319–327 | reward_type | подпись из percent_purchase / fixed_purchase / fixed_start_referrer; иначе «Тип начисления» |

Остальные: `admin_referral_set_type`, `…_percent`, `…_fixed_amount`, `…_start_bonus`, `…_discount`, `…_min_withdrawal`.

## `create_admin_franchise_settings_keyboard` (341–357)

**Docstring в коде:** есть

```
Создаёт клавиатуру настроек франшизы
```

Toggle `admin_franchise_toggle` (текст «Выключить» если enabled); `admin_franchise_set_percent`, `admin_franchise_set_min_withdraw`, `admin_settings_menu`.

## `create_admin_auto_renew_keyboard` (360–367)

**Docstring в коде:** нет

```
"""Автопродление: toggle (admin_auto_renew_toggle), окно часов (admin_auto_renew_set_hours), назад в admin_settings_menu."""
```

Строки в исходнике — unicode-escape («Выключить/Включить автопродление»).

## `create_admin_referral_type_keyboard` (370–385)

**Docstring в коде:** нет

```
"""Выбор типа реферального начисления: admin_referral_type:{percent_purchase|fixed_purchase|fixed_start_referrer}, назад admin_referral.

Текущий тип помечается префиксом «✅ ».
"""
```

## `_host_digest` (390–397)

**Docstring в коде:** есть

```
Safe stable digest for callback_data.
```

`sha1(host_name)[:12]`. В коде `#` про лимит Telegram 64 байта. `except` — тот же sha1 от `str(host_name)`.

## `create_admin_hosts_menu_keyboard` (400–418)

**Docstring в коде:** есть

```
Hosts list + add button.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 404–408 | hosts непустой | по хосту `admin_hosts_open:{digest}` |
| 409–410 | иначе | «Хостов нет» / `noop` |
| 412–413 | всегда | `admin_hosts_add`, `admin_settings_menu` |

## `create_admin_host_manage_keyboard` (421–442)

**Docstring в коде:** нет

```
"""Карточка хоста: rename/url/sub/rmw_url/rmw_token/squad/squads/ssh/plans, toggle класса (premium vs unlim), удаление, список хостов.

Все действия несут host_digest: admin_hosts_{action}:{digest}.
"""
```

`admin_hosts_toggle_class` — подпись «Premium (LTE)» если `node_class == 'premium'`, иначе «Unlimited».

## `create_admin_hosts_cancel_keyboard` (445–449)

**Docstring в коде:** нет

```
"""Отмена с callback back_cb (по умолчанию admin_hosts_menu)."""
```

## `create_admin_hosts_delete_confirm_keyboard` (452–457)

**Docstring в коде:** нет

```
"""Подтверждение удаления хоста: admin_hosts_delete_confirm:{digest} / admin_hosts_open:{digest}."""
```

## `create_admin_host_squads_keyboard` (460–488)

**Docstring в коде:** есть

```
Список сквадов хоста с переключением активности и удалением.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 465–478 | squads есть | ряд: toggle `admin_hosts_squad_toggle:{sid}:{digest}` + 🗑 `admin_hosts_squad_delete:{sid}:{digest}` |
| 479–481 | пусто | «Сквады не добавлены» / `noop` |
| 483–484 | всегда | add `admin_hosts_squad_add:{digest}`, назад `admin_hosts_open:{digest}` |

Иконки класса: base ♾, lte 💰, other 🧩. Активность ✅/🚫.

## `create_admin_squad_class_keyboard` (491–498)

**Docstring в коде:** нет

```
"""Выбор класса нового сквада: admin_hosts_squad_add_class:{digest}:{base|lte|other}, отмена admin_hosts_squads:{digest}."""
```

## `create_admin_trial_settings_keyboard` (502–528)

**Docstring в коде:** нет

```
"""Настройки триала: toggle, дни, трафик, устройства, группа тарифов (хост), назад в admin_menu.

Подписи кнопок подставляют текущие days/traffic_text/devices_text/default_host (хост >16 символов обрезается).
"""
```

Callbacks: `admin_trial_toggle`, `admin_trial_set_days`, `…_traffic`, `…_devices`, `…_host`.

## `create_admin_trial_host_keyboard` (531–540)

**Docstring в коде:** нет

```
"""Выбор хоста для триала: admin_trial_select_host_ (авто), admin_trial_select_host_{name} по списку, отмена admin_trial."""
```

Имя хоста в callback целиком (не digest). Подпись обрезается до 32.

## `create_admin_notifications_settings_keyboard` (542–567)

**Docstring в коде:** есть

```
Настройки уведомлений о неиспользовании трафика.
```

Toggle `admin_inactive_reminder_toggle`; интервал `…_set_interval` (подпись с `interval_hours`); URL поддержки `…_set_support_url` (обрезан до 24); назад `admin_settings_menu`.

## `create_admin_plans_host_menu_keyboard` (571–619)

**Docstring в коде:** есть

```
Меню тарифов для выбранного хоста (админка).

Если переданы планы — отображает их как inline-кнопки.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 578–613 | plans | по тарифу `admin_plans_open_{pid}`; ✅/🚫; срок дни или месяцы; цена ₽; битый plan_id — skip |
| 615–617 | всегда | `admin_plans_add`, `admin_plans_back_to_hosts`, `admin_menu` |

## `create_admin_plan_manage_keyboard` (622–674)

**Docstring в коде:** нет

```
"""Карточка тарифа: имя/срок/цена/трафик/устройства, toggle названия в витрине, пакеты ГБ, цена сброса (если есть лимит), LTE-лимит и LTE-пакеты, скрыть/активировать, удалить, назад."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 635–643 | metadata.show_name_in_tariffs | подпись «Название в тарифах: ✅/❌»; `admin_plan_toggle_show_name` |
| 652–658 | traffic_limit_bytes > 0 | `admin_plan_edit_main_reset_price` |
| 669 | is_active | «Скрыть» / «Активировать»; `admin_plan_toggle_active` |

Пакеты: `admin_plan_packages_{plan_id}`, `admin_lte_packages_{plan_id}`. Остальные edit без id в callback (FSM).

## `create_admin_traffic_packages_keyboard` (677–700)

**Docstring в коде:** нет

```
"""Список пакетов докупки тарифа: admin_pkg_open_{package_id}; добавить admin_pkg_add_{plan_id}_{pool}; назад admin_plans_open_{plan_id}."""
```

`pool` по умолчанию `'main'`. ✅/🚫 по `is_active`.

## `create_admin_traffic_package_manage_keyboard` (703–712)

**Docstring в коде:** нет

```
"""Карточка пакета: размер, цена, toggle, удалить, назад к admin_plan_packages_{plan_id}."""
```

`admin_pkg_edit_size_{id}`, `admin_pkg_edit_price_{id}`, `admin_pkg_toggle_{id}`, `admin_pkg_delete_{id}`.

## `create_admin_plans_duration_type_keyboard` (716–724)

**Docstring в коде:** есть

```
Выбор единиц срока тарифа при создании.
```

`admin_plans_duration_months` / `admin_plans_duration_days`, назад `admin_plans_back_to_host_menu`, `admin_cancel`.

## `create_admin_plan_duration_type_keyboard` (727–735)

**Docstring в коде:** есть

```
Выбор единиц срока тарифа при редактировании.
```

`admin_plan_duration_months` / `admin_plan_duration_days`, `admin_plan_back`, `admin_cancel`.

## `create_admin_plan_delete_confirm_keyboard` (737–742)

**Docstring в коде:** нет

```
"""Подтверждение удаления тарифа: admin_plan_delete_confirm / admin_plan_delete_cancel."""
```

## `create_admin_plan_edit_flow_keyboard` (746–751)

**Docstring в коде:** нет

```
"""Назад/отмена шага редактирования тарифа: admin_plan_back, admin_cancel."""
```

## `create_admin_plans_flow_keyboard` (754–759)

**Docstring в коде:** нет

```
"""Назад/отмена шага создания тарифа: admin_plans_back_to_host_menu, admin_cancel."""
```

## `create_admins_menu_keyboard` (761–768)

**Docstring в коде:** нет

```
"""Управление админами: admin_add_admin, admin_remove_admin, admin_view_admins, admin_menu."""
```

## `create_admin_users_keyboard` (770–796)

**Docstring в коде:** нет

```
"""Страница пользователей: admin_view_user_{id}, пагинация admin_users_page_{n}, поиск admin_users_search, admin_menu."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 774–778 | срез page*page_size | кнопка на пользователя |
| 783–786 | page>0 / end<total | назад / вперёд |
| 790–795 | adjust | ряды по 1 на юзера; хвост пагинации 2 или 1 + ряд «Поиск/меню» |

## `create_admin_user_actions_keyboard` (798–814)

**Docstring в коде:** нет

```
"""Карточка пользователя: баланс +/−, выдать ключ, рефералы, бан/разбан, ключи, удалить, к списку, в админ-меню."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 804–807 | is_banned is True | `admin_unban_user_{id}`; иначе `admin_ban_user_{id}` (None и False — «Забанить») |

Callbacks: `admin_add_balance_{id}`, `admin_deduct_balance_{id}`, `admin_gift_key_{id}`, `admin_user_referrals_{id}`, `admin_user_keys_{id}`, `admin_delete_user_{id}`, `admin_users`, `admin_menu`.

## `create_keys_management_keyboard` (816–863)

**Docstring в коде:** есть

```
Клавиатура списка ключей пользователя (раздел 'Мои ключи') с пагинацией.
```

Страница по 5. Callback ключа `show_key_{kid}`. Нумерация: старый = #1 (`len(keys) - idx`).

| Строки | Блок | Зачем |
|--------|------|--------|
| 826–840 | current_keys | имя или «Ключ #N (host) (до дд.мм.гггг)»; ✅/❌ по expiry |
| 841–842 | пусто | «Ключей нет» / `noop` |
| 847–852 | page / остаток | `keys_page_{n}` |
| 854–855 | len(keys) > 10 | `search_my_keys` |
| 857–859 | gift_keys непустой | `sent_gifts` со счётчиком |
| 861 | всегда | `back_to_main_menu` |

## `create_sent_gifts_keyboard` (866–902)

**Docstring в коде:** есть

```
Клавиатура раздела «Отправленные подарки».
```

Страница по 5; `show_key_{kid}`; пагинация `gift_keys_page_{n}`; назад `manage_keys`. Пусто — `noop`.

## `create_admin_user_keys_keyboard` (905–952)

**Docstring в коде:** нет

```
"""Ключи пользователя в админке (по 8): admin_edit_key_{kid}, страницы admin_user_keys_{user_id}_{page}, поиск если >10, назад admin_view_user_{id}."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 913–928 | current_keys / пусто | карточка или `noop` |
| 936–943 | page | `admin_user_keys_{user_id}_{page±1}` |
| 946–947 | len(keys) > 10 | `admin_search_user_keys_{user_id}` |

## `create_admin_key_actions_keyboard` (954–964)

**Docstring в коде:** нет

```
"""Действия по ключу: продлить, удалить, назад к ключам; опционально переход к пользователю."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 959–963 | user_id is not None | `admin_view_user_{user_id}`, adjust(2,2); иначе adjust(2,1) |

`admin_key_extend_{id}`, `admin_key_delete_{id}`, `admin_key_back_{id}`.

## `create_admin_delete_key_confirm_keyboard` (966–971)

**Docstring в коде:** нет

```
"""Подтверждение удаления ключа: admin_key_delete_confirm_{id} / admin_key_delete_cancel_{id}."""
```

## `create_cancel_keyboard` (973–976)

**Docstring в коде:** нет

```
"""Одна «Отмена» с произвольным callback (по умолчанию admin_cancel)."""
```

## `create_admin_cancel_keyboard` (979–980)

**Docstring в коде:** нет

```
"""Обёртка create_cancel_keyboard('admin_cancel')."""
```

## `create_admin_promo_menu_keyboard` (983–989)

**Docstring в коде:** нет

```
"""Меню промокодов: admin_promo_create, admin_promo_list, admin_menu."""
```

## `create_admin_promo_discount_keyboard` (992–998)

**Docstring в коде:** нет

```
"""Тип скидки: admin_promo_discount_percent / admin_promo_discount_amount, admin_cancel."""
```

## `create_admin_promo_code_keyboard` (1000–1006)

**Docstring в коде:** нет

```
"""Код промо: admin_promo_code_auto / admin_promo_code_custom, admin_cancel."""
```

## `create_admin_promo_limit_keyboard` (1008–1018)

**Docstring в коде:** нет

```
"""Лимит использований: inf / 1 / 5 / 10 / 50 / 100 / custom + admin_cancel.

Префикс admin_promo_limit_total_ если kind=='total', иначе admin_promo_limit_user_.
"""
```

## `create_admin_promo_valid_from_keyboard` (1020–1029)

**Docstring в коде:** нет

```
"""Старт действия промо: now / today / tomorrow / skip / custom, admin_cancel (префикс admin_promo_valid_from_)."""
```

## `create_admin_promo_valid_until_keyboard` (1031–1040)

**Docstring в коде:** нет

```
"""Конец действия промо: plus1d / plus7d / plus30d / skip / custom, admin_cancel (префикс admin_promo_valid_until_)."""
```

## `create_admin_promo_description_keyboard` (1042–1048)

**Docstring в коде:** нет

```
"""Описание промо: admin_promo_desc_skip / admin_promo_desc_custom, admin_cancel."""
```

## `create_admin_promo_segment_keyboard` (1051–1058)

**Docstring в коде:** нет

```
"""Сегмент промо: none / no_sub / min_spent, admin_cancel (префикс admin_promo_segment_)."""
```

## `create_admin_promo_plans_keyboard` (1061–1067)

**Docstring в коде:** нет

```
"""Привязка тарифов: admin_promo_plans_all / admin_promo_plans_custom, admin_cancel."""
```

## `create_broadcast_parse_mode_keyboard` (1069–1076)

**Docstring в коде:** нет

```
"""Parse mode рассылки: broadcast_pm_none / html / md2, cancel_broadcast."""
```

## `create_broadcast_options_keyboard` (1079–1085)

**Docstring в коде:** нет

```
"""Опции кнопки рассылки: broadcast_add_button / broadcast_skip_button, cancel_broadcast."""
```

## `create_broadcast_confirmation_keyboard` (1087–1092)

**Docstring в коде:** нет

```
"""Подтверждение рассылки: confirm_broadcast / cancel_broadcast."""
```

## `create_broadcast_cancel_keyboard` (1094–1097)

**Docstring в коде:** нет

```
"""Одна «Отмена» cancel_broadcast."""
```

## `create_about_keyboard` (1099–1112)

**Docstring в коде:** нет

```
"""О проекте: url-кнопки канала / оферты / privacy (если _normalize_url непустой) и back_to_main_menu."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1104–1105 | channel | url «Наш канал» |
| 1106–1107 | terms | url «Условия использования» |
| 1108–1109 | privacy | url «Политика конфиденциальности» |

## `create_support_keyboard` (1114–1123)

**Docstring в коде:** есть

```
Кнопка техподдержки (всегда ведёт на фиксированный URL).
```

По коду: аргумент `support_user` не читается. Если `SUPPORT_URL` — url-кнопка, иначе `support_menu`. Плюс `back_to_main_menu`.

## `create_support_bot_link_keyboard` (1125–1133)

**Docstring в коде:** нет

```
"""Ссылка на бота поддержки: url SUPPORT_URL или callback support_menu; назад back_to_main_menu.

По коду: аргумент support_bot_username не используется.
"""
```

## `create_inactive_usage_reminder_keyboard` (1135–1162)

**Docstring в коде:** есть

```
Клавиатура для напоминания, если пользователь не подключил устройство.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1142–1147 | key_info_show_connect_device == true | url connection_string или fallback `manage_keys` |
| 1149–1150 | key_info_show_howto == true | `howto_vless` |
| 1153–1158 | support_url из _get_notifications_support_url | url или `support_menu` (чтобы Telegram не отверг кнопку без url/callback) |
| 1159 | всегда | `back_to_main_menu` («Личный кабинет») |

## `create_support_menu_keyboard` (1164–1172)

**Docstring в коде:** нет

```
"""Меню поддержки: support_new_ticket, support_my_tickets, опционально support_external, back_to_main_menu."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1168–1169 | has_external | «Внешняя поддержка» / `support_external` |

## `create_tickets_list_keyboard` (1174–1184)

**Docstring в коде:** нет

```
"""Список тикетов: support_view_{ticket_id} (если tickets непустой) и назад support_menu."""
```

Подпись: `#{id} • {status} • {subject[:20]}`.

## `create_ticket_actions_keyboard` (1186–1193)

**Docstring в коде:** нет

```
"""Карточка тикета: при is_open — support_reply_{id} и support_close_{id}; всегда support_my_tickets."""
```

## `create_host_selection_keyboard` (1195–1202)

**Docstring в коде:** нет

```
"""Выбор хоста: select_host_{action}_{host_name}; назад manage_keys если action=='new', иначе back_to_main_menu."""
```

## `create_plans_keyboard` (1204–1254)

**Docstring в коде:** нет

```
"""Витрина тарифов: buy_{host_name}_{plan_id}_{action}_{key_id}; назад manage_keys при extend, иначе buy_new_key.

Срок — duration_days или months*30 через _ru_days. Имя тарифа в тексте только если metadata.show_name_in_tariffs.
"""
```

## `create_payment_method_keyboard` (1257–1343)

**Docstring в коде:** нет

```
"""Способы оплаты покупки ключа. Источник истины — get_setting, не аргумент payment_methods.

pay_balance / pay_referral_balance / pay_yookassa / pay_platega / pay_rollypay / pay_cryptobot|pay_heleket / pay_tonconnect / pay_stars / pay_yoomoney; промо enter_promo_code; назад back_to_email_prompt или back_to_plans.
"""
```

По коду: `payment_methods`, `action`, `key_id`, `price` в теле не читаются.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1289–1296 | show_balance | баланс, опционально сумма в скобках |
| 1298–1304 | referral_balance > 0 | реферальный баланс |
| 1307–1311 | yookassa | СБП-лейбл если sbp_enabled in true/1/on/yes/y |
| 1320–1323 | cryptobot иначе heleket | одна кнопка «Криптовалюта» |
| 1334–1335 | not promo_applied | ввод промокода |
| 1337–1341 | payment_email_prompt_enabled | другой callback «Назад» |

### `create_payment_method_keyboard._label` (1269–1274)

**Docstring в коде:** нет

```
"""Текст кнопки из get_setting(setting_key) или fallback; ошибка настроек → fallback."""
```

Тот же `_label` повторён в topup / trafficgb / ltegb / mainreset.

## `create_skip_email_keyboard` (1346–1351)

**Docstring в коде:** нет

```
"""Пропуск почты: skip_email и back_to_plans."""
```

## `create_stars_invoice_keyboard` (1353–1359)

**Docstring в коде:** есть

```
Кнопки под системной Pay ⭐: сначала Pay (требование Telegram), затем Назад.
```

`pay=True` («Оплатить ⭐»), затем `payment_stars_back`.

## `create_ton_connect_keyboard` (1362–1367)

**Docstring в коде:** нет

```
"""TON Connect: url «Открыть кошелек» и back_to_main_menu."""
```

## `create_payment_keyboard` (1369–1374)

**Docstring в коде:** нет

```
"""Универсальная ссылка оплаты: url «Перейти к оплате» и back_to_main_menu."""
```

## `create_yoomoney_payment_keyboard` (1376–1382)

**Docstring в коде:** нет

```
"""Оплата YooMoney: url + check_pending:{payment_id} + back_to_main_menu."""
```

## `create_yookassa_payment_keyboard` (1384–1390)

**Docstring в коде:** нет

```
"""Оплата YooKassa: url + check_yookassa:{payment_id} + back_to_main_menu."""
```

## `create_platega_payment_keyboard` (1392–1398)

**Docstring в коде:** нет

```
"""Оплата Platega: url + check_platega:{payment_id} + back_to_main_menu."""
```

## `create_rollypay_payment_keyboard` (1401–1407)

**Docstring в коде:** нет

```
"""Оплата RollyPay: url + check_rollypay:{payment_id} + back_to_main_menu."""
```

## `create_cryptobot_payment_keyboard` (1410–1416)

**Docstring в коде:** нет

```
"""Оплата CryptoBot: url + check_crypto_invoice:{invoice_id} + back_to_main_menu."""
```

## `create_topup_payment_method_keyboard` (1418–1463)

**Docstring в коде:** нет

```
"""Способы пополнения баланса (префикс topup_pay_*). Те же флаги get_setting, что у витрины покупки; без баланса/промо. Назад show_profile."""
```

По коду: `payment_methods` не читается. Нет кнопки баланса (это и есть пополнение).

### `create_topup_payment_method_keyboard._label` (1421–1426)

**Docstring в коде:** нет

```
"""Текст кнопки из get_setting или fallback."""
```

## `create_traffic_packages_keyboard` (1466–1485)

**Docstring в коде:** нет

```
"""Пакеты докупки основного пула: traffic_gb_pick_{key_id}_{pkg_id}; назад show_key_{key_id}."""
```

## `create_traffic_gb_payment_method_keyboard` (1488–1533)

**Docstring в коде:** нет

```
"""Оплата докупки ГБ (префикс trafficgb_pay_*). Провайдеры из get_setting + всегда trafficgb_pay_balance и trafficgb_pay_referral_balance; отмена back_to_main_menu."""
```

По коду: `payment_methods` не читается.

### `create_traffic_gb_payment_method_keyboard._label` (1491–1496)

**Docstring в коде:** нет

```
"""Текст кнопки из get_setting или fallback."""
```

## `create_lte_packages_keyboard` (1536–1557)

**Docstring в коде:** есть

```
Пакеты докупки независимого LTE-пула (premium-ноды 💰).
```

`lte_gb_pick_{key_id}_{pkg_id}`; подпись пула из `lte_label` (пустое → «LTE»); назад `show_key_{key_id}`.

## `create_lte_gb_payment_method_keyboard` (1560–1607)

**Docstring в коде:** есть

```
Выбор способа оплаты докупки LTE-пула (полный аналог create_traffic_gb_payment_method_keyboard,
но с callback-префиксом ltegb_pay_*).
```

По коду: `payment_methods` не читается. Плюс `ltegb_pay_balance`, `ltegb_pay_referral_balance`, `back_to_main_menu`.

### `create_lte_gb_payment_method_keyboard._label` (1565–1570)

**Docstring в коде:** нет

```
"""Текст кнопки из get_setting или fallback."""
```

## `create_main_reset_payment_method_keyboard` (1610–1651)

**Docstring в коде:** есть

```
Выбор способа оплаты разовой платной перезагрузки основного пула трафика.
```

Префикс `mainreset_pay_*`. По коду: нет rollypay и нет SBP-варианта YooKassa (сразу card-лейбл). `payment_methods` не читается. Баланс / реф. баланс / `back_to_main_menu` всегда.

### `create_main_reset_payment_method_keyboard._label` (1614–1619)

**Docstring в коде:** нет

```
"""Текст кнопки из get_setting или fallback."""
```

## `create_rename_key_keyboard` (1660–1667)

**Docstring в коде:** есть

```
Клавиатура для переименования ключа.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1663–1664 | has_name | `remove_key_name_{key_id}` |

Всегда `cancel_rename_key_{key_id}`.

## `create_search_keys_results_keyboard` (1670–1710)

**Docstring в коде:** есть

```
Клавиатура с результатами поиска ключей.
```

По 5 на страницу; `show_key_{id}`; пагинация `search_keys_page_{n}`; отмена `cancel_search_keys`. Нумерация `start_idx+i+1` (не «старый=#1»).

## `create_admin_search_keys_cancel_keyboard` (1712–1716)

**Docstring в коде:** есть

```
Клавиатура для отмены поиска ключей администратором.
```

Одна кнопка `admin_cancel_search_keys`.

## `create_admin_search_keys_results_keyboard` (1718–1761)

**Docstring в коде:** есть

```
Клавиатура с результатами поиска ключей (для админа).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1727–1741 | current_keys | `admin_edit_key_{id}` |
| 1747–1753 | страницы | `admin_search_keys_page_{n}` |
| 1756–1759 | user_id is not None | «К пользователю» `admin_view_user_{id}`; иначе `admin_cancel_search_keys` |

`expiry_str` считается, но в текст кнопки не попадает.

## `create_gifts_management_keyboard` (1763–1798)

**Docstring в коде:** есть

```
Клавиатура для управления неактивными подарками.
```

По 5; `show_gift_{gift_id}`; пагинация `gifts_page_{n}`; назад `back_to_main_menu`. ✅ если `is_activated`, иначе ⏳.

## `create_gift_info_keyboard` (1800–1848)

**Docstring в коде:** есть

```
Клавиатура для информации о подарке (как обычный ключ, но без продления).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1805–1806 | not is_activated and gift_link | `send_gift_link_{gift_id}` |
| 1811–1812 | show_connect и connection_string | url «Подключить устройство» |
| 1813–1814 | show_howto | `howto_vless_{key_id}` |
| 1818–1834 | devices_list | `delete_device_{key_id}_{hwid}`; текст >64 обрезается |
| 1838–1840 | not is_activated | разделитель `noop` + `activate_own_gift_{gift_id}` |
| 1843–1844 | not is_activated | `delete_gift_{gift_id}` |
| 1846 | всегда | `show_inactive_gifts` |

Всегда есть `show_qr_{key_id}`.

## `create_key_info_keyboard` (1850–1905)

**Docstring в коде:** нет

```
"""Карточка ключа: продление, опционально докупка ГБ/LTE/сброс, connect/howto, QR, удаление HWID, ссылка подарка, автопродление, переименование, назад к manage_keys."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1855–1856 | show_traffic_topup | `traffic_gb_start_{id}` |
| 1858–1860 | show_lte_topup | `lte_gb_start_{id}` (лейбл из lte_label) |
| 1862–1863 | show_main_reset | `main_reset_start_{id}` |
| 1868–1869 | show_connect и connection_string | url |
| 1870–1871 | show_howto | `howto_vless_{id}` |
| 1875–1891 | devices_list | `delete_device_{id}_{hwid}` |
| 1894–1895 | gift_code and gift_id | `send_gift_link_{gift_id}` |
| 1897–1898 | auto_renew | текст ВКЛ/ВЫКЛ; `auto_renew_key_{id}` |

Всегда: `extend_key_{id}`, `show_qr_{id}`, `rename_key_{id}`, `manage_keys`.

## `create_howto_vless_keyboard` (1906–1914)

**Docstring в коде:** нет

```
"""Инструкции VLESS с главного меню: howto_android/ios/windows/linux, back_to_main_menu."""
```

## `create_howto_vless_keyboard_key` (1916–1924)

**Docstring в коде:** нет

```
"""Инструкции VLESS с карточки ключа: howto_{os}_{key_id}, назад show_key_{key_id}."""
```

## `create_back_to_menu_keyboard` (1926–1929)

**Docstring в коде:** нет

```
"""Одна кнопка back_to_main_menu (текст из btn_back_to_menu_text)."""
```

## `create_profile_keyboard` (1931–1953)

**Docstring в коде:** нет

```
"""Профиль: top_up_start; опционально toggle автопродления всех ключей и уведомлений об истечении; back_to_main_menu.

По коду: gifts_count не используется.
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1942–1944 | show_auto_renew_toggle | `toggle_auto_renew_profile` (текст «ВЫКЛ всё» если auto_renew_any_enabled) |
| 1947–1949 | show_notification_toggle | `toggle_expiry_notifications` |

## `create_welcome_keyboard` (1955–1968)

**Docstring в коде:** нет

```
"""Онбординг: канал и/или «Принимаю условия» (check_subscription_and_agree)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1958–1960 | channel_url и is_subscription_forced | url канала + «Я подписался» |
| 1961–1963 | только channel_url | url «не обязательно» + «Принимаю условия» |
| 1964–1965 | иначе | только «Принимаю условия» |

## `get_main_menu_button` (1970–1971)

**Docstring в коде:** нет

```
"""Одна InlineKeyboardButton «В главное меню» / show_main_menu (не Markup)."""
```

## `get_buy_button` (1973–1974)

**Docstring в коде:** нет

```
"""Одна InlineKeyboardButton «Купить подписку» / buy_vpn (не Markup)."""
```

## `create_admin_users_pick_keyboard` (1977–2000)

**Docstring в коде:** нет

```
"""Пикер пользователя для admin-действия: admin_{action}_pick_user_{id}, страницы admin_{action}_pick_user_page_{n}, admin_menu.

action по умолчанию 'gift'.
"""
```

Пагинация как у `create_admin_users_keyboard`.

## `create_admin_hosts_pick_keyboard` (2002–2029)

**Docstring в коде:** нет

```
"""Пикер хоста: admin_{action}_pick_host_{name}; для speedtest — пара кнопок + run_all + SSH-цели; назад admin_{action}_back_to_users."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2004–2012 | hosts | обычный pick; speedtest — ещё `admin_speedtest_autoinstall_{name}` |
| 2013–2014 | пусто | `noop` |
| 2016–2018 | action == speedtest | `admin_speedtest_run_all`, `admin_speedtest_ssh_targets` |
| 2021–2027 | layout | speedtest ряды по 2 + хвост [2,1]; иначе по 1 + [1] |

## `create_admin_ssh_targets_keyboard` (2032–2054)

**Docstring в коде:** нет

```
"""SSH-цели speedtest: stt:{sha1} и stti:{sha1} на цель; run_all_targets; admin_menu.

Дайджест — полный sha1, не _host_digest[:12].
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2034–2044 | ssh_targets | имя + автоустановка |
| 2045–2046 | пусто | `noop` |
| 2048–2049 | всегда | `admin_speedtest_run_all_targets`, `admin_menu` |

## `create_admin_keys_for_host_keyboard` (2056–2111)

**Docstring в коде:** нет

```
"""Ключи на хосте (админ): admin_edit_key_{kid}, страницы admin_hostkeys_page_{n}, поиск если >10, назад к хостам / в меню."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2064–2069 | keys пустой | `noop` + `admin_hostkeys_back_to_hosts` + `admin_menu`, ранний return |
| 2089–2094 | page | назад/вперёд |
| 2097–2098 | total > 10 | `admin_search_all_keys` |

`host_name` в сигнатуре в кнопки не попадает (хост уже выбран в FSM).

## `create_admin_months_pick_keyboard` (2113–2119)

**Docstring в коде:** нет

```
"""Срок выдачи ключа админом: admin_{action}_pick_months_{1|3|6|12}, назад admin_{action}_back_to_hosts."""
```

## `create_dynamic_keyboard` (2122–2440)

**Docstring в коде:** есть

```
Create a keyboard based on database configuration
```

Читает `get_button_configs(menu_type)`, при необходимости дописывает франшизу / группировку админки / недостающие пункты настроек, иначе fallback на статику.

| Строки | Блок | Зачем |
|--------|------|--------|
| 2137–2192 | main_menu + конфиг | вставить `partner_cabinet` и `factory_create_bot` (если франшиза), не дублируя callback |
| 2197–2232 | admin_menu | выкинуть speedtest/monitor/backup/restore/admins/plans/trial; добавить `admin_system_menu` и `admin_settings_menu` |
| 2236–2299 | admin_settings_menu | гарантировать notifications / btn_constructor / lte_settings, если их нет в БД |
| 2302–2325 | нет конфигов | fallback: main/admin/profile/support/system/settings → статика; иначе `create_back_to_menu_keyboard` |
| 2369–2376 | main_menu | скрыть trial без trial_available, admin без is_admin |
| 2381–2393 | 0 обычных ключей | «Мои ключи» → `buy_new_key`; отдельную buy скрыть |
| 2396–2402 | плейсхолдеры | `({len(user_keys)})` → keys_count; `{gifts_count}` |
| 2404–2409 | url vs callback | url-кнопка или callback; без обоих — пропуск |
| 2415–2427 | button_width > 1 | одна кнопка в ряд |
| 2434–2440 | except | main_menu → статика **без** show_create_bot/partner/gifts_count; иначе back_to_menu |

## `create_dynamic_main_menu_keyboard` (2442–2460)

**Docstring в коде:** есть

```
Create main menu keyboard using dynamic configuration
```

Прокси в `create_dynamic_keyboard("main_menu", …)` со всеми флагами.

## `create_dynamic_admin_menu_keyboard` (2462–2464)

**Docstring в коде:** есть

```
Create admin menu keyboard using dynamic configuration
```

`create_dynamic_keyboard("admin_menu")`.

## `create_dynamic_admin_system_menu_keyboard` (2465–2467)

**Docstring в коде:** есть

```
Create admin system submenu keyboard using dynamic configuration
```

`create_dynamic_keyboard("admin_system_menu")`.

## `create_dynamic_admin_settings_menu_keyboard` (2470–2472)

**Docstring в коде:** есть

```
Create admin settings submenu keyboard using dynamic configuration
```

`create_dynamic_keyboard("admin_settings_menu")`.

## `create_dynamic_profile_keyboard` (2475–2477)

**Docstring в коде:** есть

```
Create profile keyboard using dynamic configuration
```

`create_dynamic_keyboard("profile_menu")` — без флагов уведомлений/автопродления статического профиля.

## `create_dynamic_support_menu_keyboard` (2479–2481)

**Docstring в коде:** есть

```
Create support menu keyboard using dynamic configuration
```

`create_dynamic_keyboard("support_menu")`.

## `create_broadcast_button_type_keyboard` (2497–2503)

**Docstring в коде:** нет

```
"""Тип кнопки рассылки: broadcast_btn_type_url / broadcast_btn_type_action, cancel_broadcast."""
```

## `create_broadcast_actions_keyboard` (2505–2512)

**Docstring в коде:** нет

```
"""Действия из BROADCAST_ACTIONS_MAP как broadcast_action:{cb}; назад broadcast_btn_type_url; cancel_broadcast."""
```

## `create_math_captcha_keyboard` (2518–2522)

**Docstring в коде:** есть

```
Клавиатура для математической капчи с текстовым полем.
```

Одна «Отмена» `cancel_captcha` (ответ вводится текстом, не кнопкой).

## `create_button_captcha_keyboard` (2525–2541)

**Docstring в коде:** есть

```
Клавиатура для капчи с выбором кнопки (смайлик или текст).
    
    Args:
        emoji_options: список опций для выбора (если None, используются случайные)
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2531–2534 | not emoji_options | `random.sample` из 12 эмодзи, до 4 штук |

Каждая опция — `captcha_answer:{emoji}`; отмена `cancel_captcha`; `adjust(4)`.

---

Функций: **118** (инвентарь `_normalize_url` … `create_button_captcha_keyboard`, включая 6 вложенных `_mark` / `_label`).
