# Комментарии: `src/shop_bot/bot/admin_handlers.py` (часть 2)

Продолжение вложенных хендлеров `get_admin_router`: редактирование полей хоста (после `admin_hosts_toggle_class`), trial / LTE-интервал / уведомления, тарифы и пакеты, мастер создания промокода до `admin_promo_confirm`. Модульного docstring нет.

Все имена ниже — вложенные в `get_admin_router` (кроме заголовков классов FSM). Проверка `is_admin` у большинства callback даёт alert «У вас нет прав.»; у message-хендлеров — тихий `return`.

## `get_admin_router.admin_hosts_rename_input` (2663–2684)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_rename`.

```
"""Принять новое имя хоста из FSM и вызвать update_host_name; пустое имя не пишется."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2666–2669 | strip пустой | «Имя не может быть пустым», state не чистится |
| 2674–2677 | update_host_name | любой Exception → ok=False |
| 2678–2684 | state.clear | не ok → «имя занято»; затем `show_admin_hosts_menu` (не карточка) |

## `get_admin_router.admin_hosts_set_url` (2688–2704)

**Docstring в коде:** нет. Callback `admin_hosts_set_url:`.

```
"""Поставить waiting_set_url и спросить новый URL панели (http/https) для хоста по digest."""
```

Digest не резолвится → alert «Хост не найден.» Cancel → `admin_hosts_open:{digest}`.

## `get_admin_router.admin_hosts_set_url_input` (2708–2728)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_set_url`.

```
"""Записать URL панели через update_host_url; без префикса http(s) — ошибка, FSM не сбрасывается."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2712–2714 | не http/https | ответ, return |
| 2719–2722 | update_host_url | Exception → ok=False |
| 2723–2728 | clear + ответ | есть host_name → detail, иначе список хостов |

## `get_admin_router.admin_hosts_set_sub` (2732–2749)

**Docstring в коде:** нет. Callback `admin_hosts_set_sub:`.

```
"""Поставить waiting_set_subscription и спросить ссылку подписки или `-` для очистки."""
```

## `get_admin_router.admin_hosts_set_sub_input` (2753–2770)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_set_subscription`.

```
"""update_host_subscription_url: `-` или пусто → None, иначе сырой текст."""
```

После clear — detail или список хостов.

## `get_admin_router.admin_hosts_set_rmw_url` (2774–2790)

**Docstring в коде:** нет. Callback `admin_hosts_set_rmw_url:`.

```
"""Поставить waiting_set_rmw_url и спросить Remnawave URL или `-` для очистки."""
```

## `get_admin_router.admin_hosts_set_rmw_url_input` (2794–2814)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_set_rmw_url`.

```
"""update_host_remnawave_settings(remnawave_base_url=…); `-`/пусто → None; непустой без http(s) — ошибка."""
```

Невалидный URL не чистит state.

## `get_admin_router.admin_hosts_set_rmw_token` (2818–2835)

**Docstring в коде:** нет. Callback `admin_hosts_set_rmw_token:`.

```
"""Поставить waiting_set_rmw_token и спросить Remnawave API token или `-` для очистки."""
```

## `get_admin_router.admin_hosts_set_rmw_token_input` (2839–2856)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_set_rmw_token`.

```
"""update_host_remnawave_settings(remnawave_api_token=…); `-`/пусто → None."""
```

Проверки формата токена нет.

## `get_admin_router.admin_hosts_set_squad` (2860–2876)

**Docstring в коде:** нет. Callback `admin_hosts_set_squad:`.

```
"""Поставить waiting_set_squad и спросить Squad UUID или `-` для очистки."""
```

## `get_admin_router.admin_hosts_set_squad_input` (2880–2897)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_set_squad`.

```
"""update_host_remnawave_settings(squad_uuid=…); `-`/пусто → None."""
```

Формат UUID не проверяется.

## `get_admin_router.admin_hosts_set_ssh` (2901–2921)

**Docstring в коде:** нет. Callback `admin_hosts_set_ssh:`.

```
"""Поставить waiting_set_ssh и показать формат пяти строк SSH (host/port/user/password/key_path) или `clear`."""
```

Текст: пароль или key_path можно `-`; `clear` очищает всё.

## `get_admin_router.admin_hosts_set_ssh_input` (2925–2982)

**Docstring в коде:** нет. Message, `AdminHosts.waiting_set_ssh`.

```
"""Разобрать многострочный SSH (или `clear`) и вызвать update_host_ssh_settings."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2931–2934 | нет host_name | clear + список хостов |
| 2936–2945 | raw.lower()=='clear' | все поля None |
| 2947–2950 | частей < 3 | «минимум 3 строки», state жив |
| 2957–2961 | port не int | ошибка, state жив |
| 2967–2982 | update_host_ssh_settings | password `-` явно None; затем detail |

## `get_admin_router.admin_hosts_set_ssh_input._n` (2963–2965)

**Docstring в коде:** нет

```
"""None, если строка пустая или `-`, иначе strip."""
```

## `get_admin_router.admin_hosts_to_plans` (2986–3006)

**Docstring в коде:** нет. Callback `admin_hosts_to_plans:`. В коде `#`: Reuse plans UI but jump straight into host menu.

```
"""Открыть меню тарифов выбранного хоста: plans_host + AdminPlans.host_menu, без пикера хостов."""
```

`set_state(AdminPlans.host_menu)` в try/except — сбой игнорируется. Текст — `_format_plans_for_host`.

## `AdminTrial` (3011–3015)

**Docstring в коде:** нет

```
"""FSM настроек пробного периода: меню и ввод дней / трафика / устройств."""
```

Состояния: `menu`, `waiting_for_days`, `waiting_for_traffic`, `waiting_for_devices`. Отдельного waiting для хоста нет (выбор кнопками).

## `get_admin_router._get_trial_enabled` (3018–3019)

**Docstring в коде:** нет

```
"""True, если setting trial_enabled после strip.lower() равен `true` (пусто → false)."""
```

## `get_admin_router._format_trial_value_gb` (3022–3032)

**Docstring в коде:** нет

```
"""Показать лимит ГБ: ≤0 → «без лимита»; целое без дроби, иначе как float + « ГБ»."""
```

Непарсибельное / None → 0.0. Запятая → точка.

## `get_admin_router._format_trial_value_int` (3035–3041)

**Docstring в коде:** нет

```
"""Целое из строки (через float): ≤0 → «без лимита», иначе str(val)."""
```

## `get_admin_router._get_trial_days` (3044–3054)

**Docstring в коде:** нет

```
"""trial_duration_days как int; дефолт 3; зажать в [1, 365]."""
```

## `get_admin_router.show_admin_trial_menu` (3058–3095)

**Docstring в коде:** нет

```
"""Показать карточку Trial: статус, дни, трафик, устройства, группа тарифов и клавиатуру настроек."""
```

Пустой `trial_default_host` → «авто (все доступные)». `edit_message` + ошибка edit → answer.

## `get_admin_router.admin_trial_entry` (3099–3106)

**Docstring в коде:** нет. Callback `admin_trial`.

```
"""Войти в Trial: clear FSM, AdminTrial.menu, show_admin_trial_menu(edit)."""
```

## `get_admin_router.admin_trial_toggle` (3110–3118)

**Docstring в коде:** нет. Callback `admin_trial_toggle`.

```
"""Инвертировать trial_enabled (true↔false) через rw_repo.update_setting и перерисовать меню."""
```

## `get_admin_router.admin_trial_set_days` (3122–3133)

**Docstring в коде:** нет. Callback `admin_trial_set_days`.

```
"""Поставить waiting_for_days и спросить длительность 1–365."""
```

Cancel → `admin_trial`.

## `get_admin_router.admin_trial_set_traffic` (3136–3148)

**Docstring в коде:** нет. Callback `admin_trial_set_traffic`.

```
"""Поставить waiting_for_traffic и спросить лимит ГБ (0 — без лимита)."""
```

## `get_admin_router.admin_trial_set_devices` (3151–3163)

**Docstring в коде:** нет. Callback `admin_trial_set_devices`.

```
"""Поставить waiting_for_devices и спросить HWID-лимит (0 — без лимита)."""
```

## `get_admin_router.admin_trial_set_host` (3166–3179)

**Docstring в коде:** нет. Callback `admin_trial_set_host`.

```
"""Оставить AdminTrial.menu и показать пикер хостов для trial_default_host."""
```

Текст: «Авто» — пользователь выбирает сам (или единственная группа).

## `get_admin_router.admin_trial_select_host` (3182–3191)

**Docstring в коде:** нет. Callback `admin_trial_select_host_`.

```
"""Записать trial_default_host хвостом callback (пустая строка = авто) и вернуть меню Trial."""
```

Alert с «группой тарифов».

## `get_admin_router.admin_trial_days_input` (3194–3209)

**Docstring в коде:** нет. Message, `AdminTrial.waiting_for_days`.

```
"""Сохранить trial_duration_days (1–365) и показать меню Trial новым сообщением."""
```

Нечисло / вне диапазона — state жив.

## `get_admin_router.admin_trial_traffic_input` (3213–3232)

**Docstring в коде:** нет. Message, `AdminTrial.waiting_for_traffic`.

```
"""Сохранить trial_traffic_limit_gb: 0 как `0`, иначе компактный float; диапазон 0–10000."""
```

`val_str` для ненуля: `("%s" % gb).rstrip("0").rstrip(".")`.

## `get_admin_router.admin_trial_devices_input` (3236–3251)

**Docstring в коде:** нет. Message, `AdminTrial.waiting_for_devices`.

```
"""Сохранить trial_device_limit (0–1000) и показать меню Trial."""
```

## `AdminLteSettings` (3256–3258)

**Docstring в коде:** нет

```
"""FSM глобальных LTE-настроек: меню и ввод интервала проверки dual-лимитов."""
```

`menu`, `waiting_for_interval`. Класс ноды / LTE-лимит тарифа здесь не правятся (текст меню отсылает в хосты и тарифы).

## `get_admin_router._get_dual_limit_interval` (3261–3266)

**Docstring в коде:** нет

```
"""int dual_limit_interval_sec; дефолт/провал/≤0 → 120."""
```

## `get_admin_router.show_admin_lte_settings_menu` (3269–3286)

**Docstring в коде:** нет

```
"""Показать интервал dual_limit_interval_sec и пояснение, где настраиваются класс ноды и LTE-пакеты."""
```

## `get_admin_router.admin_lte_settings_entry` (3290–3297)

**Docstring в коде:** нет. Callback `admin_lte_settings_menu`.

```
"""Войти в LTE-меню: clear, AdminLteSettings.menu, show_admin_lte_settings_menu(edit)."""
```

## `get_admin_router.admin_lte_set_interval_start` (3301–3312)

**Docstring в коде:** нет. Callback `admin_lte_set_interval`.

```
"""Поставить waiting_for_interval и спросить секунды интервала проверки."""
```

Cancel → `admin_lte_settings_menu`.

## `get_admin_router.admin_lte_set_interval_received` (3316–3330)

**Docstring в коде:** нет. Message, `AdminLteSettings.waiting_for_interval`.

```
"""Записать dual_limit_interval_sec (целое > 0) и вернуть LTE-меню."""
```

≤0 трактуется как ошибка (raise ValueError в том же try). State → `menu`, не clear.

## `AdminNotifications` (3337–3340)

**Docstring в коде:** нет

```
"""FSM уведомлений о неиспользованном ключе: меню, интервал часов, URL поддержки."""
```

`menu`, `waiting_for_interval`, `waiting_for_support_url`.

## `get_admin_router._get_inactive_reminder_enabled` (3342–3343)

**Docstring в коде:** нет

```
"""_is_true(inactive_usage_reminder_enabled), пусто → `true`."""
```

## `get_admin_router._get_inactive_reminder_interval_hours` (3345–3355)

**Docstring в коде:** нет

```
"""float inactive_usage_reminder_interval_hours; дефолт 8; зажать в [1, 168]."""
```

## `get_admin_router._get_inactive_reminder_support_url` (3357–3359)

**Docstring в коде:** нет

```
"""Вернуть strip inactive_usage_reminder_support_url или пустую строку."""
```

## `get_admin_router.show_admin_notifications_menu` (3361–3390)

**Docstring в коде:** нет

```
"""Показать статус напоминаний, интервал часов и ссылку поддержки (пусто → «по умолчанию»)."""
```

URL в тексте экранируется `html_escape.escape`. Текст: интервал = и задержка до первого уведомления.

## `get_admin_router.admin_notifications_entry` (3394–3401)

**Docstring в коде:** нет. Callback `admin_notifications_menu`.

```
"""Войти в уведомления: clear, AdminNotifications.menu, перерисовать меню."""
```

## `get_admin_router.admin_inactive_reminder_toggle` (3405–3413)

**Docstring в коде:** нет. Callback `admin_inactive_reminder_toggle`.

```
"""Инвертировать inactive_usage_reminder_enabled и перерисовать меню."""
```

## `get_admin_router.admin_inactive_reminder_set_interval` (3417–3430)

**Docstring в коде:** нет. Callback `admin_inactive_reminder_set_interval`.

```
"""Поставить waiting_for_interval и спросить часы 1–168."""
```

## `get_admin_router.admin_inactive_reminder_interval_input` (3434–3451)

**Docstring в коде:** нет. Message, `AdminNotifications.waiting_for_interval`. В коде `#`: store compact.

```
"""Сохранить интервал часов (1–168) компактной строкой без хвостовых нулей."""
```

## `get_admin_router.admin_inactive_reminder_set_support_url` (3455–3469)

**Docstring в коде:** нет. Callback `admin_inactive_reminder_set_support_url`.

```
"""Поставить waiting_for_support_url; показать текущее значение, если непустое; 0 в подсказке = дефолт."""
```

## `get_admin_router.admin_inactive_reminder_support_url_input` (3473–3494)

**Docstring в коде:** нет. Message, `AdminNotifications.waiting_for_support_url`. В коде `#`: minimal normalization: allow t.me/... or @user.

```
"""Записать URL поддержки: 0/-/нет/off → пусто; `@name` → https://t.me/; иначе при отсутствии схемы добавить https://."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3477–3482 | 0, `-`, нет, off | сброс в `""` |
| 3486–3489 | @ | t.me без @ |
| 3488–3489 | не http/https/tg:// | `https://` + lstrip `/` |

## `AdminPlans` (3499–3530)

**Docstring в коде:** нет. В коде `#`: создание нового тарифа; управление пакетами докупки трафика (ГБ).

```
"""FSM тарифов: пикер хоста, карточка плана, правки полей, подтверждение удаления, мастер создания, пакеты ГБ."""
```

Состояния: `picking_host`, `host_menu`, `plan_menu`, `edit_name`, `edit_duration_type`, `edit_months`, `edit_days`, `edit_price`, `edit_traffic`, `edit_devices`, `edit_lte_limit`, `edit_main_reset_price`, `confirm_delete`, `waiting_for_plan_name`, `waiting_for_duration_type`, `waiting_for_months`, `waiting_for_days`, `waiting_for_traffic`, `waiting_for_devices`, `waiting_for_price`, `packages_menu`, `package_menu`, `waiting_for_package_size`, `waiting_for_package_price`, `edit_package_size`, `edit_package_price`.

## `get_admin_router._format_plan_duration` (3536–3548)

**Docstring в коде:** есть

```
Человекочитаемый срок тарифа.
```

По коду: `duration_days` > 0 → «N дн.»; иначе months или «—».

## `get_admin_router._format_traffic_gb` (3550–3564)

**Docstring в коде:** нет. В коде `#`: красивое округление.

```
"""traffic_limit_bytes → «без лимита» (None/≤0), иначе ГБ: целое или до 2 знаков без хвостовых нулей; ошибка → «—»."""
```

Делитель `1024*1024*1024`.

## `get_admin_router._format_devices` (3566–3576)

**Docstring в коде:** нет

```
"""hwid_device_limit: None/≤0 → «без лимита», иначе str; ошибка → «—»."""
```

## `get_admin_router._plan_show_name_enabled` (3578–3584)

**Docstring в коде:** нет

```
"""True, если JSON metadata.show_name_in_tariffs истинен; битый JSON → False."""
```

## `get_admin_router._format_plans_for_host` (3586–3607)

**Docstring в коде:** нет

```
"""HTML-список тарифов хоста: статус, id, имя, срок, цена RUB, трафик, устройства; пусто → «не настроены»."""
```

`is_active==1` → ✅ иначе 🚫. Имя хоста экранируется.

## `get_admin_router.admin_plans_entry` (3611–3623)

**Docstring в коде:** нет. Callback `admin_plans`.

```
"""Войти в тарифы: clear, picking_host, пикер хостов action=plans."""
```

## `get_admin_router.admin_plans_back_to_admin` (3627–3633)

**Docstring в коде:** нет. Callback `admin_plans_back_to_users` только в `picking_host`.

```
"""Сбросить FSM и показать главное админ-меню (edit)."""
```

Имя callback `…_to_users`, тело зовёт `show_admin_menu`.

## `get_admin_router.admin_plans_pick_host` (3637–3649)

**Docstring в коде:** нет. Callback `admin_plans_pick_host_` в `picking_host`.

```
"""Запомнить plans_host, перейти в host_menu и показать список тарифов хоста."""
```

Хвост callback — имя хоста как есть (без digest).

## `get_admin_router._format_plan_detail` (3652–3682)

**Docstring в коде:** нет

```
"""HTML-карточка тарифа: id, хост, имя, срок, цена, трафик, устройства, активен/скрыт, флаг названия при покупке."""
```

## `get_admin_router.admin_plans_open_plan` (3688–3719)

**Docstring в коде:** есть. Callback `admin_plans_open_` в `host_menu` / `packages_menu` / `package_menu`. В коде `#`: safety: if host was changed or stale.

```
Открыть конкретный тариф из списка тарифов хоста.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3694–3698 | plan_id не int | alert |
| 3700–3703 | нет плана | alert |
| 3707–3710 | plans_host задан и ≠ plan.host_name | «другому хосту» |
| 3712–3718 | иначе | current_plan_id, plan_menu, карточка |

## `get_admin_router._format_traffic_package_detail` (3722–3742)

**Docstring в коде:** нет

```
"""HTML-карточка пакета: id, объём ГБ, цена RUB, активен/скрыт."""
```

Целое ГБ без дроби, иначе `:g`.

## `get_admin_router.admin_plan_packages_menu` (3746–3775)

**Docstring в коде:** нет. Callback `admin_plan_packages_` в `plan_menu`.

```
"""Открыть пакеты докупки основного пула (pool=main) для тарифа."""
```

`current_pkg_pool='main'`. Пустой список — доп. строка «не настроены». Текст: до ближайшего ежемесячного сброса.

## `get_admin_router.admin_lte_packages_menu` (3779–3810)

**Docstring в коде:** нет. Callback `admin_lte_packages_` в `plan_menu`.

```
"""Открыть LTE-пакеты (pool=lte); без lte_limit_bytes > 0 — alert «Сначала задайте LTE-лимит»."""
```

Список через `database.get_traffic_packages_for_plan` (не импорт верхнего уровня).

## `get_admin_router.admin_plan_edit_lte_limit_start` (3814–3823)

**Docstring в коде:** нет. Callback `admin_plan_edit_lte_limit` в `plan_menu`.

```
"""Поставить edit_lte_limit и спросить ГБ независимого LTE-пула (0 — выключить)."""
```

## `get_admin_router.admin_plan_edit_lte_limit_received` (3827–3869)

**Docstring в коде:** нет. Message, `AdminPlans.edit_lte_limit`.

```
"""update_plan(lte_limit_bytes=ГБ×2³⁰), сохранив имя/months/price; вернуть карточку тарифа."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3831–3837 | не float / < 0 | ошибка, state жив |
| 3840–3843 | нет current_plan_id | clear |
| 3846–3848 | нет плана | return без clear |
| 3849–3860 | update_plan except | лог, «не удалось», state жив |
| 3861–3869 | успех | plan_menu + карточка новым сообщением |

## `get_admin_router.admin_plan_edit_main_reset_price_start` (3873–3883)

**Docstring в коде:** нет. Callback `admin_plan_edit_main_reset_price`.

```
"""Поставить edit_main_reset_price и спросить цену досрочного сброса основного трафика (0 — выключить)."""
```

## `get_admin_router.admin_plan_edit_main_reset_price_received` (3887–3928)

**Docstring в коде:** нет. Message, `AdminPlans.edit_main_reset_price`.

```
"""update_plan(main_reset_price_rub=price ≥ 0) с теми же имя/months/price; вернуть карточку."""
```

Ветки как у LTE-лимита (нет id → clear; нет плана / ошибка update → return).

## `get_admin_router.admin_pkg_add_start` (3932–3956)

**Docstring в коде:** нет. Callback `admin_pkg_add_` в `packages_menu`.

```
"""Начать добавление пакета: хвост `_lte`/`_main` задаёт pool, иначе main; спросить размер ГБ."""
```

`waiting_for_package_size`. Суффикс срезается до `int(plan_id)`.

## `get_admin_router.admin_pkg_size_received` (3960–3973)

**Docstring в коде:** нет. Message, `waiting_for_package_size`.

```
"""Принять size_gb > 0 в new_package_size и спросить цену."""
```

## `get_admin_router.admin_pkg_price_received` (3977–4002)

**Docstring в коде:** нет. Message, `waiting_for_package_price`.

```
"""create_traffic_package(plan_id, size_gb, price, pool) и вернуться в список пакетов."""
```

Нет plan_id или size_gb → clear. `price` и `size_gb` должны быть > 0.

## `get_admin_router.admin_pkg_open` (4006–4027)

**Docstring в коде:** нет. Callback `admin_pkg_open_` в `packages_menu`.

```
"""Открыть карточку пакета: current_package_id / current_plan_id, package_menu."""
```

## `get_admin_router.admin_pkg_edit_size_start` (4031–4040)

**Docstring в коде:** нет. Callback `admin_pkg_edit_size_` в `package_menu`.

```
"""Поставить edit_package_size и спросить новый объём ГБ (id пакета из FSM, не из callback)."""
```

Хвост callback не парсится.

## `get_admin_router.admin_pkg_edit_size_received` (4044–4066)

**Docstring в коде:** нет. Message, `edit_package_size`.

```
"""update_traffic_package(size_gb>0) и перерисовать карточку пакета."""
```

`int(pkg_id)` без проверки на None.

## `get_admin_router.admin_pkg_edit_price_start` (4070–4079)

**Docstring в коде:** нет. Callback `admin_pkg_edit_price_`.

```
"""Поставить edit_package_price и спросить новую цену; id снова из FSM."""
```

## `get_admin_router.admin_pkg_edit_price_received` (4083–4105)

**Docstring в коде:** нет. Message, `edit_package_price`.

```
"""update_traffic_package(price>0) и перерисовать карточку пакета."""
```

## `get_admin_router.admin_pkg_toggle` (4109–4131)

**Docstring в коде:** нет. Callback `admin_pkg_toggle_`.

```
"""Инвертировать is_active пакета и обновить карточку на месте."""
```

State не меняется.

## `get_admin_router.admin_pkg_delete` (4135–4153)

**Docstring в коде:** нет. Callback `admin_pkg_delete_`.

```
"""delete_traffic_package и показать список пакетов; get_traffic_packages_for_plan без pool (в БД default main)."""
```

Нет отдельного confirm. `plan_id` с удалённого пакета; если pkg не найден — пустой список.

## `get_admin_router.admin_plan_edit_name` (4158–4168)

**Docstring в коде:** нет. Callback `admin_plan_edit_name`.

```
"""Поставить edit_name и спросить новое название тарифа."""
```

## `get_admin_router.admin_plan_edit_months` (4172–4183)

**Docstring в коде:** нет. Callback `admin_plan_edit_months`. В коде `#`: backward compatibility: open duration selector.

```
"""Открыть выбор единиц срока (месяцы/дни), не сразу ввод месяцев."""
```

То же тело, что у `admin_plan_edit_duration`.

## `get_admin_router.admin_plan_edit_price` (4187–4197)

**Docstring в коде:** нет. Callback `admin_plan_edit_price`.

```
"""Поставить edit_price и спросить новую цену."""
```

## `get_admin_router.admin_plan_edit_duration` (4202–4212)

**Docstring в коде:** нет. Callback `admin_plan_edit_duration`.

```
"""Поставить edit_duration_type и показать клавиатуру месяцев/дней."""
```

## `get_admin_router.admin_plan_duration_months` (4216–4223)

**Docstring в коде:** нет. Callback `admin_plan_duration_months` в `edit_duration_type`.

```
"""Перейти в edit_months и спросить срок 1–120 месяцев."""
```

`is_admin` здесь нет.

## `get_admin_router.admin_plan_duration_days` (4227–4234)

**Docstring в коде:** нет. Callback `admin_plan_duration_days` в `edit_duration_type`.

```
"""Перейти в edit_days и спросить срок 1–3650 дней."""
```

`is_admin` нет.

## `get_admin_router.admin_plan_edit_traffic` (4238–4248)

**Docstring в коде:** нет. Callback `admin_plan_edit_traffic`.

```
"""Поставить edit_traffic и спросить лимит ГБ (0 — без лимита)."""
```

## `get_admin_router.admin_plan_edit_devices` (4252–4262)

**Docstring в коде:** нет. Callback `admin_plan_edit_devices`.

```
"""Поставить edit_devices и спросить целое HWID (0 — без лимита)."""
```

## `get_admin_router.admin_plan_toggle_active` (4266–4291)

**Docstring в коде:** нет. Callback `admin_plan_toggle_active`.

```
"""Инвертировать is_active через set_plan_active и перерисовать карточку тарифа."""
```

Нет current_plan_id / нет плана / set_plan_active ложь → alert.

## `get_admin_router.admin_plan_toggle_show_name` (4295–4327)

**Docstring в коде:** нет. Callback `admin_plan_toggle_show_name`. В коде `#`: Toggle metadata flag.

```
"""Инвертировать metadata.show_name_in_tariffs через update_plan_metadata и перерисовать карточку."""
```

Битый JSON metadata → `{}`.

## `get_admin_router.admin_plan_delete_start` (4331–4341)

**Docstring в коде:** нет. Callback `admin_plan_delete`.

```
"""Поставить confirm_delete и спросить необратимое удаление."""
```

## `get_admin_router.admin_plan_delete_cancel` (4345–4347)

**Docstring в коде:** нет. Callback `admin_plan_delete_cancel` в `confirm_delete`. В коде `#`: возвращаемся в меню тарифа.

```
"""По коду: await admin_plan_back(callback, state) — def admin_plan_back в этом файле нет."""
```

В `keyboards.py` есть кнопка `callback_data="admin_plan_back"`, хендлера с таким именем в `admin_handlers.py` нет.

## `get_admin_router.admin_plan_delete_confirm` (4351–4380)

**Docstring в коде:** нет. Callback `admin_plan_delete_confirm`.

```
"""delete_plan(current_plan_id) и вернуться в список тарифов хоста."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4359–4361 | нет plan_id | alert |
| 4362–4367 | except delete_plan | exception-лог, alert |
| 4369–4380 | успех | host_menu; без host_name — «удален» + cancel kb |

## `get_admin_router.admin_plan_edit_name_received` (4384–4408)

**Docstring в коде:** нет. Message, `edit_name`.

```
"""update_plan с новым именем (длина 2–64), старыми months/price; вернуть карточку."""
```

## `get_admin_router.admin_plan_edit_months_received` (4412–4441)

**Docstring в коде:** нет. Message, `edit_months`.

```
"""update_plan(months 1–120, duration_days=None) и вернуть карточку."""
```

## `get_admin_router.admin_plan_edit_price_received` (4445–4474)

**Docstring в коде:** нет. Message, `edit_price`.

```
"""update_plan с новой ценой (0 < price ≤ 1_000_000) и вернуть карточку."""
```

## `get_admin_router.admin_plan_edit_days_received` (4479–4515)

**Docstring в коде:** нет. Message, `edit_days`. В коде `#`: months -> NULL, т.к. теперь срок в днях.

```
"""update_plan(months=None, duration_days 1–3650) и вернуть карточку."""
```

## `get_admin_router.admin_plan_edit_traffic_received` (4519–4560)

**Docstring в коде:** нет. Message, `edit_traffic`.

```
"""update_plan(traffic_limit_bytes): 0 ГБ → 0 байт, иначе ГБ×2³⁰; диапазон 0–100000."""
```

`months` передаётся как `plan.get('months')` (может быть NULL после дней).

## `get_admin_router.admin_plan_edit_devices_received` (4564–4603)

**Docstring в коде:** нет. Message, `edit_devices`.

```
"""update_plan(hwid_device_limit): ≤0 → None (без лимита), иначе 1–1000."""
```

## `get_admin_router.admin_plans_back_to_hosts` (4607–4618)

**Docstring в коде:** нет. Callback `admin_plans_back_to_hosts` в `host_menu`.

```
"""Вернуться к пикеру хостов тарифов (picking_host), без clear всего FSM."""
```

## `get_admin_router.admin_plans_add_start` (4622–4641)

**Docstring в коде:** нет. Callback `admin_plans_add` в `host_menu`.

```
"""Начать создание тарифа: waiting_for_plan_name; без plans_host — ошибка и picking_host."""
```

## `get_admin_router.admin_plans_new_duration_months` (4646–4657)

**Docstring в коде:** нет. Callback `admin_plans_duration_months` в `waiting_for_duration_type`.

```
"""new_plan_duration_unit=months, waiting_for_months, спросить 1–120."""
```

## `get_admin_router.admin_plans_new_duration_days` (4661–4672)

**Docstring в коде:** нет. Callback `admin_plans_duration_days` в `waiting_for_duration_type`.

```
"""new_plan_duration_unit=days, waiting_for_days, спросить 1–3650."""
```

## `get_admin_router.admin_plans_back_to_host_menu` (4675–4697)

**Docstring в коде:** нет. Callback `admin_plans_back_to_host_menu` при любом `StateFilter(AdminPlans)`.

```
"""Вернуться к списку тарифов хоста; нет plans_host — снова пикер хостов."""
```

## `get_admin_router.admin_plans_plan_name_received` (4701–4723)

**Docstring в коде:** нет. Message, `waiting_for_plan_name`.

```
"""Принять имя (непусто, ≤64) в new_plan_name и показать выбор единиц срока."""
```

Минимум 2 символа здесь не требуется (в отличие от edit_name).

## `get_admin_router.admin_plans_months_received` (4727–4752)

**Docstring в коде:** нет. Message, `waiting_for_months`. В коде `#`: Для тарифов в месяцах тоже собираем лимиты (ГБ/устройства) как и для тарифов в днях.

```
"""new_plan_months (1–120), new_plan_days=None, затем спросить лимит трафика."""
```

## `get_admin_router.admin_plan_add_days_received` (4757–4776)

**Docstring в коде:** нет. Message, `waiting_for_days`.

```
"""new_plan_days (1–3650), new_plan_months=None, затем спросить лимит трафика."""
```

## `get_admin_router.admin_plan_add_traffic_received` (4780–4803)

**Docstring в коде:** нет. Message, `waiting_for_traffic`.

```
"""new_plan_traffic_limit_bytes (0 или ГБ×2³⁰, 0–100000 ГБ) и спросить лимит устройств."""
```

## `get_admin_router.admin_plan_add_devices_received` (4807–4827)

**Docstring в коде:** нет. Message, `waiting_for_devices`.

```
"""new_plan_hwid_device_limit (≤0 → None) и спросить цену."""
```

## `get_admin_router.admin_plans_price_received` (4830–4888)

**Docstring в коде:** нет. Message, `waiting_for_price`. В коде `#`: Return to host menu with refreshed list.

```
"""create_plan из FSM (хост, имя, months xor days, цена 0<…≤1e6, трафик, HWID) и показать список хоста."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4839–4841 | цена вне (0, 1e6] | ошибка |
| 4851–4857 | нет хоста/имени/срока | clear |
| 4859–4872 | create_plan except | лог + текст исключения |
| 4875–4888 | успех | обнулить new_plan_*, host_menu |

## `AdminPromoCreate` (4891–4903)

**Docstring в коде:** нет

```
"""FSM мастера нового промокода: код, скидка, лимиты, даты, описание, сегмент, тарифы, confirming."""
```

Состояния: `waiting_for_code`, `waiting_for_discount_type`, `waiting_for_discount_value`, `waiting_for_total_limit`, `waiting_for_per_user_limit`, `waiting_for_valid_from`, `waiting_for_valid_until`, `waiting_for_description`, `waiting_for_segment`, `waiting_for_segment_value`, `waiting_for_plans`, `confirming`.

## `get_admin_router.admin_promo_menu_handler` (4906–4912)

**Docstring в коде:** нет. Callback `admin_promo_menu`.

```
"""Сбросить FSM и показать меню промокодов (show_admin_promo_menu, edit)."""
```

## `get_admin_router.admin_promo_create_start` (4915–4925)

**Docstring в коде:** нет. Callback `admin_promo_create`.

```
"""Начать создание: clear, waiting_for_code, кнопки авто/свой код."""
```

## `get_admin_router.admin_promo_code_auto` (4931–4950)

**Docstring в коде:** нет. Callback `admin_promo_code_auto` в `waiting_for_code`.

```
"""Сгенерировать uuid4.hex[:8].upper(), записать promo_code, перейти к типу скидки."""
```

edit_text падает → answer тем же текстом.

## `get_admin_router.admin_promo_code_custom` (4956–4965)

**Docstring в коде:** нет. Callback `admin_promo_code_custom`. Без `state` в сигнатуре.

```
"""Попросить ввести код вручную (латиница/цифры) или слово «авто»; state не меняет."""
```

Остаётся `waiting_for_code` — дальше ловит `admin_promo_create_code`.

## `get_admin_router.admin_promo_create_code` (4968–4984)

**Docstring в коде:** нет. Message, `waiting_for_code`.

```
"""Принять код: «авто»/auto → hex8; иначе UPPER; regex [A-Z0-9_-]{3,32}; затем тип скидки."""
```

## `get_admin_router.admin_promo_set_discount_type` (4990–4999)

**Docstring в коде:** нет. Callback `admin_promo_discount_percent` / `_amount`.

```
"""discount_type percent|amount по суффиксу callback и спросить значение."""
```

`endswith('percent')` иначе `amount`.

## `get_admin_router.admin_promo_set_discount_value` (5002–5024)

**Docstring в коде:** нет. Message, `waiting_for_discount_value`.

```
"""Принять discount_value > 0; для percent ещё < 100; затем общий лимит (кнопки total)."""
```

## `get_admin_router.admin_promo_set_total_limit` (5027–5047)

**Docstring в коде:** нет. Message, `waiting_for_total_limit`.

```
"""usage_limit_total: 0/∞/inf/безлимит/нет/пусто или ≤0 → None; иначе int; затем лимит на пользователя."""
```

## `get_admin_router.admin_promo_total_limit_buttons` (5053–5071)

**Docstring в коде:** нет. Callback `admin_promo_limit_total_` в `waiting_for_total_limit`.

```
"""Кнопки общего лимита: custom → промпт текстом; inf → None; иначе int(хвост)."""
```

Alert без `show_alert`. `custom` state не меняет.

## `get_admin_router.admin_promo_user_limit_buttons` (5077–5095)

**Docstring в коде:** нет. Callback `admin_promo_limit_user_`.

```
"""Кнопки per-user лимита: custom → промпт; inf → None; иначе int; затем дата начала (кнопки)."""
```

## `get_admin_router.admin_promo_set_per_user_limit` (5098–5118)

**Docstring в коде:** нет. Message, `waiting_for_per_user_limit`.

```
"""usage_limit_per_user теми же правилами безлимита; затем текстовый промпт даты начала (skip)."""
```

Текстовый путь не ставит клавиатуру дат — только cancel.

## `get_admin_router.admin_promo_set_valid_from` (5121–5135)

**Docstring в коде:** нет. Message, `waiting_for_valid_from`.

```
"""valid_from через _parse_datetime_input (skip/нет/пусто → None); затем кнопки даты окончания."""
```

ValueError из парсера показывается как `❌ {e}`.

## `get_admin_router.admin_promo_valid_from_buttons` (5147–5172)

**Docstring в коде:** нет. Callback now/today/tomorrow/skip/custom.

```
"""Кнопки начала: custom → текстовый ввод; skip → None; today — 00:00 сегодня; tomorrow +1д; иначе now."""
```

`endswith` на полном callback_data.

## `get_admin_router.admin_promo_set_valid_until` (5175–5194)

**Docstring в коде:** нет. Message, `waiting_for_valid_until`.

```
"""valid_until через _parse_datetime_input; если оба конца заданы и until ≤ from — ошибка; затем описание."""
```

## `get_admin_router.admin_promo_valid_until_buttons` (5206–5233)

**Docstring в коде:** нет. Callback plus1d/plus7d/plus30d/skip/custom.

```
"""Кнопки конца: custom → текст; skip → None; иначе base=valid_from или now плюс 1/7/30 дней."""
```

Иначе (не plus1d/plus7d) → +30д.

## `get_admin_router.admin_promo_description` (5236–5246)

**Docstring в коде:** нет. Message, `waiting_for_description`.

```
"""description=None при пусто/skip/пропустить/нет; иначе текст; затем выбор сегмента."""
```

## `get_admin_router.admin_promo_desc_buttons` (5252–5269)

**Docstring в коде:** нет. Callback `admin_promo_desc_skip` / `_custom`.

```
"""custom → промпт текста; skip → description=None и вопрос про сегмент."""
```

## `get_admin_router._show_promo_confirm` (5271–5317)

**Docstring в коде:** нет

```
"""Собрать HTML-сводку FSM промокода, кнопки Создать/Отмена, state=confirming; edit если это callback."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5284–5291 | сегмент | нет / no_active_subscription / min_total_spent / иначе raw |
| 5292 | тарифы | нет plan_ids → «все тарифы» |
| 5312–5317 | target | есть `.message` и `.data` → callback: edit_text, иначе answer |

`discount_value:.2f` без проверки на None.

## `get_admin_router.admin_promo_set_segment` (5327–5353)

**Docstring в коде:** нет. Callback none / no_sub / min_spent.

```
"""Сегмент: none→оба None; no_sub→no_active_subscription; min_spent→ввод суммы; иначе сразу вопрос про тарифы."""
```

## `get_admin_router.admin_promo_set_segment_value` (5356–5373)

**Docstring в коде:** нет. Message, `waiting_for_segment_value`.

```
"""segment_value = float > 0 (мин. сумма покупок) и вопрос про ограничение тарифами."""
```

## `get_admin_router.admin_promo_set_plans` (5379–5391)

**Docstring в коде:** нет. Callback `admin_promo_plans_all` / `_custom`.

```
"""all → applicable_plan_ids=None и _show_promo_confirm; custom → промпт списка id."""
```

## `get_admin_router.admin_promo_set_plans_custom` (5394–5409)

**Docstring в коде:** нет. Message, `waiting_for_plans`.

```
"""Разобрать plan_id через запятую/точку с запятой в list[int] и показать подтверждение."""
```

Пустой ввод / не-число — ошибка, confirm не зовётся.

## `get_admin_router.admin_promo_confirm` (5412–5458)

**Docstring в коде:** нет. Callback `admin_promo_confirm` в `confirming`.

```
"""create_promo_code из FSM: percent→discount_percent, amount→discount_amount; успех → меню промо."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5426–5439 | kwargs | created_by=from_user.id; сегмент и plan_ids из data |
| 5441–5445 | ValueError | текст исключения, clear |
| 5446–5452 | not ok | «возможно, код уже существует», clear |
| 5453–5458 | успех | clear, код в `<code>` |

---

Покрыто записей инвентаря: **130** (`admin_hosts_rename_input` … `admin_promo_confirm` включительно).
