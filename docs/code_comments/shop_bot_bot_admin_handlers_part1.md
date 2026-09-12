# Комментарии: `src/shop_bot/bot/admin_handlers.py` (часть 1)

Админский Telegram-роутер: `get_admin_router()`. Модульного docstring нет. Фильтр `IsAdminFilter` + `AdminAccessMiddleware`; часть callback обёрнута в `fast_callback_answer` / `catch_callback_errors`. Часть 1 — от `_is_true` до `admin_hosts_toggle_class` (инвентарь: меню, модули, конструктор кнопок, платежки, рефералка, франшиза, хосты/сквады). Хендлеры дальше по файлу — в следующих частях.

Покрыто записей инвентаря: **125**.

## `_is_true` (99–100)

**Docstring в коде:** нет

```
"""True, если строка value в true/1/on/yes/y (регистр не важен)."""
```

## `_mask_secret` (103–109)

**Docstring в коде:** нет

```
"""Маска секрета для админ-карточки: пусто → «—»; ≤6 символов — все «•»; иначе первые и последние 2 символа."""
```

## `AdminSettings` (111–114)

**Docstring в коде:** нет

```
"""FSM капчи в админке: попытки, таймаут, текст сообщения (хендлеры ниже по файлу)."""
```

Состояния: `waiting_for_captcha_attempts`, `waiting_for_captcha_timeout`, `waiting_for_captcha_message`.

## `AdminModules` (116–117)

**Docstring в коде:** нет

```
"""FSM просмотра списка модулей: одно состояние browsing."""
```

## `Broadcast` (119–127)

**Docstring в коде:** нет

```
"""FSM рассылки: текст, parse_mode, кнопки, подтверждение (хендлеры ниже по файлу)."""
```

Состояния: `waiting_for_message`, `waiting_for_parse_mode`, `waiting_for_button_option`, `waiting_for_button_type`, `waiting_for_button_text`, `waiting_for_button_url`, `waiting_for_action_select`, `waiting_for_confirmation`.

## `IsAdminFilter` (130–147)

**Docstring в коде:** есть

```
Router-level gate for admin_router (aiogram 3.x BaseFilter).

    Only telegram_ids from admin_telegram_id / admin_telegram_ids pass.
```

Навешивается на `admin_router.message` и `admin_router.callback_query`.

### `IsAdminFilter.__call__` (136–147)

**Docstring в коде:** нет

```
"""True, если is_admin(event_from_user.id); нет пользователя или исключение БД → False."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 141–143 | user is None | отказ (каналы и т.п.) |
| 144–145 | is_admin | пропуск админа |
| 146–147 | except | отказ, без проброса |

## `AdminAccessMiddleware` (150–175)

**Docstring в коде:** есть

```
When a non-admin hits admin_router, answer the callback the same way
    existing handlers do (`У вас нет прав.`) instead of leaving Telegram spinning.
    Messages are ignored silently (same as a failed router filter).
```

outer_middleware на message и callback_query того же роутера.

### `AdminAccessMiddleware.__call__` (156–175)

**Docstring в коде:** нет

```
"""Не-админу: CallbackQuery → alert «У вас нет прав.» и return None; Message — молча. Админу — вызвать handler."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 162–167 | uid / is_admin | исключение → allowed=False |
| 168–174 | not allowed | ACK callback; message без ответа |
| 175 | иначе | handler(event, data) |

## `get_admin_router` (178–8996)

**Docstring в коде:** нет

```
"""Собрать admin_router: IsAdminFilter + AdminAccessMiddleware, все вложенные хендлеры; вернуть Router.

В этой части — меню, модули, конструктор кнопок, платежки, рефералка, франшиза, хосты до toggle_class.
"""
```

Создаёт `Router(name="admin_router")`, вешает фильтр и middleware на message и callback_query. Вложенные функции — отдельные секции.

### `get_admin_router._format_user_mention` (186–200)

**Docstring в коде:** нет

```
"""HTML-упоминание админа: @username или <a href='tg://user?id='> с escape имени; сбой → id."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 188–190 | username | без ведущего @ |
| 192–198 | иначе | full_name / first_name / «Администратор» |
| 199–200 | except | str(id) или «—» |

### `get_admin_router._resolve_target_from_hash` (203–220)

**Docstring в коде:** нет

```
"""Имя SSH-цели из callback `…:<sha1>`: сравнить полный SHA1 target_name со вторым сегментом; нет → None."""
```

`get_all_ssh_targets()`. Хендлеры speedtest, которые это вызывают, — ниже по файлу.

### `get_admin_router.show_admin_menu` (222–258)

**Docstring в коде:** нет

```
"""Показать панель админа: статистика get_admin_stats и динамическая клавиатура (fallback на статику)."""
```

`edit_message=True` — `edit_text`, ошибка глотается; иначе `answer`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 224–231 | stats | today/total users/income/keys, active_keys |
| 247–251 | keyboard | create_dynamic_admin_menu_keyboard, иначе create_admin_menu_keyboard |

### `get_admin_router.show_admin_promo_menu` (260–272)

**Docstring в коде:** нет

```
"""Экран «Управление промокодами» и create_admin_promo_menu_keyboard (хендлеры промо — ниже по файлу)."""
```

edit не удался → `answer`.

### `get_admin_router._parse_datetime_input` (274–283)

**Docstring в коде:** нет

```
"""Разобрать дату админа: skip/нет/не/none/пусто → None; `%Y-%m-%d %H:%M` или `%Y-%m-%d`; иначе ValueError."""
```

### `get_admin_router._format_promo_line` (285–335)

**Docstring в коде:** нет

```
"""Одна HTML-строка промо: код, скидка % или RUB, активен/лимиты/срок/тарифы/сегмент."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 289–295 | скидка | percent, иначе amount |
| 301–309 | usage_limit_total | used/limit и «лимит исчерпан» |
| 315–316 | per_user | «пользователь ≤ N» |
| 322–332 | valid_until / plan_ids / segment | до, тарифы, нет подписки / сумма ≥ |

### `get_admin_router._build_promo_list_keyboard` (337–363)

**Docstring в коде:** нет

```
"""Инлайн-список промо: `admin_promo_toggle_{code}`, страницы `admin_promo_page_*`, назад `admin_promo_menu`."""
```

Пустая страница — кнопка `noop`. page_size по умолчанию 10.

### `get_admin_router.show_admin_system_menu` (365–378)

**Docstring в коде:** нет

```
"""Экран «Система»: динамическая клавиатура, fallback на create_admin_system_menu_keyboard."""
```

### `get_admin_router.show_admin_settings_menu` (381–394)

**Docstring в коде:** нет

```
"""Экран «Настройки»: динамическая клавиатура, fallback на create_admin_settings_menu_keyboard."""
```

### `get_admin_router._build_modules_keyboard` (397–413)

**Docstring в коде:** нет

```
"""Кнопки модулей: enabled → `admin_module_disable:{id}`, иначе `admin_module_enable:{id}`; refresh и назад в настройки."""
```

### `get_admin_router.show_admin_modules_menu` (415–450)

**Docstring в коде:** нет

```
"""Список module_loader.list_modules(): статус 🟢/🔴/🟡, error_message, клавиатура _build_modules_keyboard."""
```

Пустой список — «Модули не найдены.»

### `get_admin_router.open_admin_menu_handler` (454–459)

**Docstring в коде:** нет. Callback `admin_menu`.

```
"""Callback `admin_menu`: повторная проверка is_admin, затем show_admin_menu (edit)."""
```

Не-админ → alert «У вас нет прав.»

### `get_admin_router.open_admin_system_menu_handler` (461–466)

**Docstring в коде:** нет. Callback `admin_system_menu`.

```
"""Callback `admin_system_menu`: открыть системное меню (edit)."""
```

### `get_admin_router.open_admin_settings_menu_handler` (470–475)

**Docstring в коде:** нет. Callback `admin_settings_menu`.

```
"""Callback `admin_settings_menu`: открыть меню настроек (edit)."""
```

### `get_admin_router.open_admin_modules_menu_handler` (479–485)

**Docstring в коде:** нет. Callback `admin_modules`.

```
"""Callback `admin_modules`: FSM AdminModules.browsing и экран списка модулей."""
```

### `get_admin_router.refresh_admin_modules_menu_handler` (488–493)

**Docstring в коде:** нет. Callback `admin_modules_refresh`.

```
"""Callback `admin_modules_refresh`: перерисовать список модулей без смены FSM."""
```

### `get_admin_router.admin_module_enable_handler` (496–504)

**Docstring в коде:** нет. Callback `admin_module_enable:{module_id}`.

```
"""Callback `admin_module_enable:`: module_loader.enable_module; alert при неуспехе; обновить список."""
```

### `get_admin_router.admin_module_disable_handler` (507–515)

**Docstring в коде:** нет. Callback `admin_module_disable:{module_id}`.

```
"""Callback `admin_module_disable:`: module_loader.disable_module; alert при неуспехе; обновить список."""
```

## `ButtonConstructor` (521–530)

**Docstring в коде:** нет. Объявлен внутри `get_admin_router`.

```
"""FSM конструктора кнопок: добавление полей и editing_value для правки существующей."""
```

Состояния: `adding_button_id`, `adding_text`, `adding_action_value`, `adding_row`, `adding_col`, `adding_width`, `adding_sort`, `adding_active`, `editing_value`.

`_BTN_MENUS` (532–539, не в инвентаре): `main_menu`, `profile_menu`, `support_menu`, `admin_menu`, `admin_system_menu`, `admin_settings_menu`.

### `get_admin_router._btnc_menu_label` (541–545)

**Docstring в коде:** нет

```
"""Человекочитаемый заголовок menu_type из _BTN_MENUS; неизвестный тип вернуть как есть."""
```

### `get_admin_router._btnc_cancel_kb` (547–552)

**Docstring в коде:** нет

```
"""Клавиатура «Отмена» (`btnc_cancel`) и «Назад» (back_cb, по умолчанию `admin_settings_menu`)."""
```

### `get_admin_router._btnc_show_menu_types` (554–571)

**Docstring в коде:** нет

```
"""Корень конструктора: кнопки `btnc_mt:{menu_type}` и назад в настройки."""
```

### `get_admin_router._btnc_build_list_kb` (573–614)

**Docstring в коде:** нет

```
"""Список кнопок меню: `btnc_edit:{menu}:{id}`, страницы `btnc_list:`, добавить `btnc_add:`, другое меню, назад."""
```

Пусто — `(пусто)` / `noop`. Текст обрезается до 28 символов.

### `get_admin_router._btnc_show_list` (616–631)

**Docstring в коде:** нет

```
"""Показать список get_button_configs_admin(include_inactive=True) для menu_type."""
```

### `get_admin_router._btnc_build_details_kb` (633–645)

**Docstring в коде:** нет

```
"""Клавиатура карточки кнопки: поля, `btnc_toggle`, `btnc_del`, к списку, в настройки."""
```

### `get_admin_router._btnc_show_details` (647–687)

**Docstring в коде:** нет

```
"""Карточка кнопки get_button_config_by_db_id: текст, URL/callback, позиция, статус; чужой menu_type → список."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 649–652 | нет cfg / другой menu_type | «не найдена», _btnc_show_list |
| 664–665 | url_val | действие URL, иначе Callback |

### `get_admin_router.admin_button_constructor_root` (693–698)

**Docstring в коде:** нет. Callback `admin_btn_constructor`. `@catch_callback_errors` + `@fast_callback_answer`.

```
"""Callback `admin_btn_constructor`: очистить FSM и показать выбор типа меню."""
```

### `get_admin_router.btnc_select_menu_type` (703–708)

**Docstring в коде:** нет. Callback `btnc_mt:{menu_type}`.

```
"""Callback `btnc_mt:`: открыть список кнопок выбранного menu_type, страница 0."""
```

### `get_admin_router.btnc_open_list` (713–723)

**Docstring в коде:** нет. Callback `btnc_list:{menu_type}:{page}`.

```
"""Callback `btnc_list:`: список кнопок; нет page → 0, нет menu_type → main_menu."""
```

### `get_admin_router.btnc_open_details` (728–740)

**Docstring в коде:** нет. Callback `btnc_edit:{menu_type}:{db_id}`.

```
"""Callback `btnc_edit:`: карточка кнопки; короткий payload или не-int id — тихий выход."""
```

### `get_admin_router.btnc_toggle_active` (745–760)

**Docstring в коде:** нет. Callback `btnc_toggle:{menu_type}:{db_id}`.

```
"""Callback `btnc_toggle:`: инвертировать is_active через update_button_config и перерисовать карточку."""
```

### `get_admin_router.btnc_delete_confirm` (765–784)

**Docstring в коде:** нет. Callback `btnc_del:{menu_type}:{db_id}`.

```
"""Callback `btnc_del:`: спросить удаление; да → `btnc_del_ok:`, отмена → `btnc_edit:`."""
```

### `get_admin_router.btnc_delete_do` (789–802)

**Docstring в коде:** нет. Callback `btnc_del_ok:{menu_type}:{db_id}`.

```
"""Callback `btnc_del_ok:`: delete_button_config(db_id) и вернуться к списку меню."""
```

### `get_admin_router.btnc_cancel_any` (807–809)

**Docstring в коде:** нет. Callback `btnc_cancel`.

```
"""Callback `btnc_cancel`: state.clear и show_admin_settings_menu (edit). Проверки is_admin нет."""
```

### `get_admin_router.btnc_action_menu` (814–834)

**Docstring в коде:** нет. Callback `btnc_action_menu:{menu_type}:{db_id}`.

```
"""Callback `btnc_action_menu:`: выбрать тип действия — `btnc_setfield:callback` или `:url`."""
```

### `get_admin_router.btnc_edit_field_start` (839–866)

**Docstring в коде:** нет. Callback `btnc_setfield:{field}:{menu_type}:{db_id}`.

```
"""Callback `btnc_setfield:`: FSM editing_value, сохранить field/menu/id, показать промпт поля."""
```

Поля промптов: `text`, `callback`, `url`, `rowcol`, `width`, `sort`; иное — «Отправьте новое значение:».

### `get_admin_router.btnc_edit_field_value` (869–916)

**Docstring в коде:** нет. Message в `ButtonConstructor.editing_value`.

```
"""Принять текст правки кнопки: update_button_config по btnc_field; callback сбрасывает url и наоборот."""
```

В коде `#`: при callback очистить URL.

| Строки | Блок | Зачем |
|--------|------|--------|
| 882–884 | пустой raw | отказ, FSM не сбрасывается |
| 887–888 | text | update text |
| 889–891 | callback | callback_data, url=None |
| 892–893 | url | url, callback_data=None |
| 894–900 | rowcol | два int через пробел/запятую |
| 901–905 | width | по коду 1/2/3 (промпт писал «1 или 2») |
| 906–908 | sort | int sort_order |
| 909–910 | иначе | metadata=raw |
| 911–916 | except / успех | ошибка в чат; иначе clear и карточка |

### `get_admin_router.btnc_add_start` (924–938)

**Docstring в коде:** нет. Callback `btnc_add:{menu_type}`.

```
"""Callback `btnc_add:`: начать создание кнопки, спросить button_id (FSM adding_button_id)."""
```

### `get_admin_router.btnc_add_button_id` (941–954)

**Docstring в коде:** нет. Message в `adding_button_id`.

```
"""Проверить button_id `^[a-zA-Z0-9_\\-]{1,64}$`, сохранить в btnc_new, спросить текст."""
```

### `get_admin_router.btnc_add_text` (957–975)

**Docstring в коде:** нет. Message в `adding_text`.

```
"""Сохранить text в btnc_new и предложить тип: `btnc_add_action:callback` / `:url`."""
```

Состояние FSM не меняется — выбор типа ловит `btnc_add_action_type` в том же `adding_text`.

### `get_admin_router.btnc_add_action_type` (980–992)

**Docstring в коде:** нет. Callback `btnc_add_action:{callback|url}` при `adding_text`.

```
"""Callback `btnc_add_action:`: записать action_type и спросить URL или callback_data."""
```

### `get_admin_router.btnc_add_action_value` (995–1026)

**Docstring в коде:** нет. Message в `adding_action_value`.

```
"""Сохранить url или callback_data (взаимно exclusive) и спросить row; default_row = max существующих + 1."""
```

В коде `#`: дефолт ряда по уже существующим кнопкам.

### `get_admin_router.btnc_add_row` (1029–1047)

**Docstring в коде:** нет. Message в `adding_row`.

```
"""Принять row_position (skip/- /— → btnc_default_row) и спросить column_position."""
```

### `get_admin_router.btnc_add_col` (1050–1071)

**Docstring в коде:** нет. Message в `adding_col`.

```
"""Принять column_position (int) и предложить ширину `btnc_add_width:1|2|3`."""
```

### `get_admin_router.btnc_add_width` (1076–1097)

**Docstring в коде:** нет. Callback `btnc_add_width:{n}` при `adding_width`.

```
"""Callback `btnc_add_width:`: сохранить button_width (сбой разбора → 1) и спросить sort_order."""
```

default_sort = max существующих + 1.

### `get_admin_router.btnc_add_sort` (1100–1123)

**Docstring в коде:** нет. Message в `adding_sort`.

```
"""Принять sort_order (skip → default) и спросить статус `btnc_add_active:1|0`."""
```

### `get_admin_router.btnc_add_finish` (1128–1160)

**Docstring в коде:** нет. Callback `btnc_add_active:{0|1}` при `adding_active`.

```
"""Callback `btnc_add_active:`: create_button_config из btnc_new; clear FSM; список кнопок меню."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1131–1134 | active_val | не-int → 1 |
| 1138–1153 | create_button_config | исключение → ok=False, exception-лог |
| 1155–1160 | итог | «создана» / «не удалось», затем список (не edit) |

## `AdminPayments` (1167–1168)

**Docstring в коде:** нет. Внутри `get_admin_router`.

```
"""FSM ввода значения настройки платежки: waiting_for_value."""
```

### `get_admin_router._get_payments_status_for_admin` (1171–1212)

**Docstring в коде:** нет

```
"""Флаги «настроена/активна» для клавиатуры: креды есть (YooKassa/CryptoBot/Heleket/Platega/TonConnect) или флаг+готовность (YooMoney/Stars)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1172–1189 | yookassa…tonconnect | True если заполнены обязательные секреты |
| 1191–1195 | yoomoney | _is_true(yoomoney_enabled) и wallet+secret |
| 1197–1202 | stars | _is_true(stars_enabled) и stars_per_rub > 0 |

### `get_admin_router.show_admin_payments_menu` (1215–1225)

**Docstring в коде:** нет

```
"""Список платежек: create_admin_payments_menu_keyboard(status)."""
```

### `get_admin_router._payment_detail_text` (1228–1341)

**Docstring в коде:** нет

```
"""HTML-карточка провайдера и flags для тумблеров (sbp_enabled / stars_enabled / yoomoney_enabled). Секреты через _mask_secret."""
```

Неизвестный provider → «Неизвестная платежная система.» и пустые flags.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1231–1246 | yookassa | shop/secret, receipt_email, СБП |
| 1248–1256 | cryptobot | token |
| 1258–1270 | heleket | merchant, api_key, domain |
| 1273–1287 | platega | base_url, merchant, secret, methods |
| 1289–1299 | tonconnect | wallet, tonapi |
| 1301–1315 | stars | enabled + stars_per_rub |
| 1317–1339 | yoomoney | enabled, wallet, secret, OAuth-поля |

### `get_admin_router.show_admin_payment_detail` (1344–1353)

**Docstring в коде:** нет

```
"""Карточка провайдера + create_admin_payment_detail_keyboard(provider, flags)."""
```

### `get_admin_router.admin_payments_menu` (1357–1363)

**Docstring в коде:** нет. Callback `admin_payments_menu`.

```
"""Callback `admin_payments_menu`: clear FSM и список платежек."""
```

### `get_admin_router.admin_payments_open` (1367–1375)

**Docstring в коде:** нет. Callback `admin_payments_open:{provider}`.

```
"""Callback `admin_payments_open:`: запомнить payments_provider и открыть карточку провайдера."""
```

### `get_admin_router.admin_payments_toggle` (1379–1399)

**Docstring в коде:** нет. Callback `admin_payments_toggle:{sbp|stars|yoomoney|…}`.

```
"""Callback `admin_payments_toggle:`: инвертировать sbp_enabled / stars_enabled / yoomoney_enabled; иное — только перерисовать карточку из FSM."""
```

`_PAYMENT_FIELD_MAP` (1402–1424, не в инвентаре): пары (provider, field) → ключ `update_setting`.

### `get_admin_router._payment_prompt` (1427–1468)

**Docstring в коде:** нет

```
"""Текст приглашения ввода для пары provider+field; неизвестная пара — общее «Введите значение…»."""
```

Почти все поля: «или '-' чтобы очистить». Stars ratio: «0 — отключит оплату звездами».

### `get_admin_router._normalize_payment_input` (1471–1475)

**Docstring в коде:** нет

```
"""Нормализовать ввод настройки: `-` / `—` / clear / clr / нет → пустая строка; иначе strip."""
```

### `get_admin_router.admin_payments_set` (1479–1501)

**Docstring в коде:** нет. Callback `admin_payments_set:{provider}:{field}`.

```
"""Callback `admin_payments_set:`: FSM waiting_for_value, запомнить ключ из _PAYMENT_FIELD_MAP, спросить значение."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1484–1488 | split не на 3 части | alert «Некорректная команда» |
| 1491–1494 | нет в карте | alert «Неизвестный параметр» |

### `get_admin_router.admin_payments_set_value` (1505–1542)

**Docstring в коде:** нет. Message в `AdminPayments.waiting_for_value`.

```
"""Сохранить нормализованный ввод в rw_repo.update_setting; для stars/ratio — float 0..1000."""
```

В коде `#`: validators, save.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1512–1515 | нет provider/field/key | clear, меню платежек |
| 1521–1530 | stars ratio | не число / вне 0..1000 — отказ, FSM жив |
| 1533–1538 | update_setting | ошибка → «Не удалось сохранить» |
| 1540–1542 | успех | clear, «Сохранено», карточка |

### `get_admin_router.admin_payments_yoomoney_check` (1546–1583)

**Docstring в коде:** нет. Callback `admin_payments_yoomoney_check`.

```
"""Callback `admin_payments_yoomoney_check`: POST yoomoney.ru/api/account-info с Bearer-токеном; показать account или ошибку."""
```

Нет `yoomoney_api_token` → «токен не задан». HTTP ≠ 200 или сеть — ошибка. JSON: `account` или `account_number`.

## `AdminReferral` (1593–1599)

**Docstring в коде:** нет. Внутри `get_admin_router`.

```
"""FSM рефералки: menu и ввод percent / fixed / start_bonus / min_withdrawal / discount."""
```

### `get_admin_router._get_bool_setting` (1602–1604)

**Docstring в коде:** нет

```
"""Прочитать настройку как bool: 1/true/yes/on; пусто → default (без синонима y, в отличие от _is_true)."""
```

### `get_admin_router._get_float_setting` (1607–1613)

**Docstring в коде:** нет

```
"""float настройки: запятая → точка; провал разбора → default."""
```

### `get_admin_router._get_referral_settings_for_admin` (1616–1627)

**Docstring в коде:** нет

```
"""Срез реферальных настроек для меню: флаги, reward_type и числа с дефолтами."""
```

Дефолты: enable_referrals/days_bonus True; percent 10; fixed 50; start 20; min_withdrawal 100; discount 5. Тип пустой → `percent_purchase`.

### `get_admin_router._format_reward_type_human` (1630–1637)

**Docstring в коде:** нет

```
"""Русская подпись referral_reward_type: percent_purchase / fixed_purchase / fixed_start_referrer; иначе сырое значение."""
```

### `get_admin_router.show_admin_referral_menu` (1640–1669)

**Docstring в коде:** нет

```
"""Карточка рефералки и create_admin_referral_settings_keyboard(enabled, days_bonus, reward_type)."""
```

### `get_admin_router.admin_referral_menu_entry` (1673–1679)

**Docstring в коде:** нет. Callback `admin_referral`.

```
"""Callback `admin_referral`: FSM AdminReferral.menu и экран настроек."""
```

### `get_admin_router.admin_referral_toggle` (1683–1691)

**Docstring в коде:** нет. Callback `admin_referral_toggle`.

```
"""Callback `admin_referral_toggle`: инвертировать enable_referrals и перерисовать меню."""
```

### `get_admin_router.admin_referral_toggle_days_bonus` (1695–1703)

**Docstring в коде:** нет. Callback `admin_referral_toggle_days_bonus`.

```
"""Callback `admin_referral_toggle_days_bonus`: инвертировать enable_referral_days_bonus."""
```

### `get_admin_router.admin_referral_set_type` (1707–1718)

**Docstring в коде:** нет. Callback `admin_referral_set_type`.

```
"""Callback `admin_referral_set_type`: клавиатура выбора типа начисления (не пишет настройку)."""
```

### `get_admin_router.admin_referral_type_chosen` (1722–1739)

**Docstring в коде:** нет. Callback `admin_referral_type:{value}`.

```
"""Callback `admin_referral_type:`: записать referral_reward_type и enable_fixed_referral_bonus (true только для fixed_start_referrer)."""
```

Допустимы только `percent_purchase`, `fixed_purchase`, `fixed_start_referrer`.

### `get_admin_router.admin_referral_set_percent` (1743–1754)

**Docstring в коде:** нет. Callback `admin_referral_set_percent`.

```
"""Callback `admin_referral_set_percent`: спросить процент 0–100 (FSM waiting_for_percent)."""
```

### `get_admin_router.admin_referral_percent_input` (1758–1773)

**Docstring в коде:** нет. Message в `waiting_for_percent`.

```
"""Записать referral_percentage (0–100, два знака) и показать меню рефералки."""
```

### `get_admin_router.admin_referral_set_fixed_amount` (1777–1788)

**Docstring в коде:** нет. Callback `admin_referral_set_fixed_amount`.

```
"""Callback `admin_referral_set_fixed_amount`: спросить фикс за покупку 0–100000 ₽."""
```

### `get_admin_router.admin_referral_fixed_amount_input` (1792–1807)

**Docstring в коде:** нет. Message в `waiting_for_fixed_amount`.

```
"""Записать fixed_referral_bonus_amount (0–100000) и вернуться в меню."""
```

### `get_admin_router.admin_referral_set_start_bonus` (1811–1822)

**Docstring в коде:** нет. Callback `admin_referral_set_start_bonus`.

```
"""Callback `admin_referral_set_start_bonus`: спросить стартовый бонус пригласившему 0–100000 ₽."""
```

### `get_admin_router.admin_referral_start_bonus_input` (1826–1843)

**Docstring в коде:** нет. Message в `waiting_for_start_bonus`. В коде `#`: ненулевой бонус включает фиксированный флаг.

```
"""Записать referral_on_start_referrer_amount и enable_fixed_referral_bonus (true если сумма > 0)."""
```

### `get_admin_router.admin_referral_set_min_withdrawal` (1847–1858)

**Docstring в коде:** нет. Callback `admin_referral_set_min_withdrawal`.

```
"""Callback `admin_referral_set_min_withdrawal`: спросить minimum_withdrawal 0–100000 ₽."""
```

### `get_admin_router.admin_referral_min_withdrawal_input` (1862–1877)

**Docstring в коде:** нет. Message в `waiting_for_min_withdrawal`.

```
"""Записать minimum_withdrawal (0–100000) и показать меню."""
```

### `get_admin_router.admin_referral_set_discount` (1881–1892)

**Docstring в коде:** нет. Callback `admin_referral_set_discount`.

```
"""Callback `admin_referral_set_discount`: спросить скидку новому пользователю 0–100 %."""
```

### `get_admin_router.admin_referral_discount_input` (1896–1911)

**Docstring в коде:** нет. Message в `waiting_for_discount`.

```
"""Записать referral_discount (0–100) и показать меню."""
```

## `AdminFranchise` (1916–1919)

**Docstring в коде:** нет. Внутри `get_admin_router`.

```
"""FSM франшизы: menu, ввод процента комиссии и минимума вывода."""
```

### `get_admin_router._get_franchise_settings_for_admin` (1922–1929)

**Docstring в коде:** есть

```
Получает текущие настройки франшизы (только для админа)
```

Читает `franchise_settings()`, `get_franchise_percent_default()`, `get_franchise_min_withdraw()`.

### `get_admin_router.show_admin_franchise_menu` (1932–1953)

**Docstring в коде:** есть

```
Отображает меню настроек франшизы (только для админа)
```

Статус, комиссия, минимум вывода; `create_admin_franchise_settings_keyboard(enabled)`.

### `get_admin_router.admin_franchise_menu_entry` (1957–1965)

**Docstring в коде:** есть. Callback `admin_franchise`.

```
Точка входа в меню франшизы - ТОЛЬКО ДЛЯ АДМИНА
```

FSM `AdminFranchise.menu`, затем `show_admin_franchise_menu`.

### `get_admin_router.admin_franchise_toggle` (1969–1993)

**Docstring в коде:** есть. Callback `admin_franchise_toggle`. В коде `#`: переключить и применить клоны.

```
Переключает франшизу ВКЛ/ВЫКЛ - ТОЛЬКО ДЛЯ АДМИНА
```

`toggle_franchise_settings()`; при успехе сервиса — `start_all` / `stop_all`. Сбой клонов — warning, меню всё равно обновляется.

### `get_admin_router.admin_franchise_set_percent` (1996–2004)

**Docstring в коде:** есть. Callback `admin_franchise_set_percent`.

```
Установить процент комиссии франшизы
```

Спрашивает число в чат, FSM `waiting_for_percent` (клавиатуры отмены нет).

### `get_admin_router.admin_franchise_percent_input` (2007–2025)

**Docstring в коде:** есть. Message в `waiting_for_percent`.

```
Обработка ввода процента комиссии
```

0–100 → `franchise_commission_percent` с одним знаком. ValueError — «Некорректное значение», FSM не сбрасывается.

### `get_admin_router.admin_franchise_set_min_withdraw` (2028–2036)

**Docstring в коде:** есть. Callback `admin_franchise_set_min_withdraw`.

```
Установить минимум для вывода франшизников
```

### `get_admin_router.admin_franchise_min_withdraw_input` (2039–2057)

**Docstring в коде:** есть. Message в `waiting_for_min_withdraw`.

```
Обработка ввода минимума для вывода
```

`amount < 1` отвергается. Пишет `franchise_min_withdraw_rub` как целое.

## `AdminHosts` (2064–2083)

**Docstring в коде:** нет. Внутри `get_admin_router`.

```
"""FSM хостов: меню, добавление (имя/URL/token/squad), правки полей, сквады второго пула."""
```

Состояния: `menu`, `host_menu`, `waiting_add_*`, `waiting_rename` / `waiting_set_*`, `squads_menu`, `waiting_add_squad2_uuid`, `waiting_add_squad2_label`.

### `get_admin_router._resolve_host_from_digest` (2086–2102)

**Docstring в коде:** нет. В коде `#`: короткий digest из‑за лимита 64 байт callback_data; принимаются полный SHA1 и префикс.

```
"""Найти host_name по SHA1: полное совпадение (legacy) или startswith (текущие 12 hex). Нет → None."""
```

### `get_admin_router._safe` (2105–2106)

**Docstring в коде:** нет

```
"""html.escape строки для карточки хоста; None/пусто → «—»."""
```

### `get_admin_router._format_host_card` (2109–2154)

**Docstring в коде:** нет. В коде `#`: LTE-биллинг смотреть по host_squads, не по node_class.

```
"""HTML-карточка хоста: URL/sub/Remnawave/squad, статус LTE-сквада и overlap, SSH без пароля (только «задан»)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2125–2129 | get_squad_by_class(lte) | «настроен» / «не настроен» |
| 2131–2135 | get_host_squad_overlap | предупреждение о пересечении с base |

### `get_admin_router.show_admin_hosts_menu` (2157–2167)

**Docstring в коде:** нет

```
"""Список хостов: get_all_hosts + create_admin_hosts_menu_keyboard."""
```

### `get_admin_router.show_admin_host_detail` (2170–2188)

**Docstring в коде:** нет

```
"""Карточка хоста: _format_host_card и create_admin_host_manage_keyboard(digest[:12], node_class)."""
```

`get_host_class` сбой → `unlim`.

### `get_admin_router.show_admin_host_squads` (2191–2208)

**Docstring в коде:** нет

```
"""Экран сквадов хоста: get_host_squads и create_admin_host_squads_keyboard(digest, squads)."""
```

### `get_admin_router.admin_hosts_menu` (2212–2218)

**Docstring в коде:** нет. Callback `admin_hosts_menu`.

```
"""Callback `admin_hosts_menu`: FSM AdminHosts.menu и список хостов."""
```

### `get_admin_router.admin_hosts_add` (2222–2233)

**Docstring в коде:** нет. Callback `admin_hosts_add`.

```
"""Callback `admin_hosts_add`: clear FSM, спросить название хоста (waiting_add_name)."""
```

### `get_admin_router.admin_hosts_add_name` (2237–2250)

**Docstring в коде:** нет. Message в `waiting_add_name`.

```
"""Сохранить add_host_name (непустой) и спросить базовый URL Remnawave."""
```

### `get_admin_router.admin_hosts_add_base_url` (2254–2267)

**Docstring в коде:** нет. Message в `waiting_add_base_url`.

```
"""Проверить http(s)://, сохранить add_base_url, спросить API Token."""
```

### `get_admin_router.admin_hosts_add_api_token` (2271–2284)

**Docstring в коде:** нет. Message в `waiting_add_api_token`.

```
"""Сохранить непустой add_api_token и спросить Squad UUID (`-` = пропуск)."""
```

### `get_admin_router.admin_hosts_add_squad_uuid` (2288–2335)

**Docstring в коде:** нет. Message в `waiting_add_squad_uuid`. В коде `#`: создать хост как в веб-панели.

```
"""create_host + update_host_remnawave_settings; `-` обнуляет squad_uuid. Исключение create_host глотается."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2300–2310 | create_host | user/passwd пустые, inbound=0; except pass |
| 2312–2321 | update_host_remnawave_settings | URL, token, squad |
| 2323–2335 | get_host | нет строки → ошибка; иначе ок/частичный ок |

### `get_admin_router.admin_hosts_open` (2342–2370)

**Docstring в коде:** есть. Callback `admin_hosts_open:{digest}`. В коде `#`: lambda-фильтр из‑за совместимости aiogram.

```
Открыть карточку выбранного хоста.

        В некоторых окружениях фильтр startswith может не срабатывать стабильно,
        поэтому используем строгий regexp по SHA1-дайджесту.
        Также отвечаем на callback максимально быстро.
```

Не найден → alert и список хостов. Успех: FSM `host_menu`, `host_digest`/`host_name` в state.

### `get_admin_router.admin_hosts_squads_open` (2376–2388)

**Docstring в коде:** нет. Callback `admin_hosts_squads:{digest}`.

```
"""Callback `admin_hosts_squads:`: FSM squads_menu и экран сквадов хоста."""
```

### `get_admin_router.admin_hosts_squad_toggle` (2394–2420)

**Docstring в коде:** нет. Callback `admin_hosts_squad_toggle:{squad_id}:{digest}`.

```
"""Callback `admin_hosts_squad_toggle:`: инвертировать is_active через set_host_squad_active и перерисовать сквады."""
```

Не-int id / нет хоста — alert. Сбой set — «Не удалось изменить статус», список всё равно обновляется.

### `get_admin_router.admin_hosts_squad_delete` (2426–2447)

**Docstring в коде:** нет. Callback `admin_hosts_squad_delete:{squad_id}:{digest}`.

```
"""Callback `admin_hosts_squad_delete:`: delete_host_squad(squad_id) без отдельного confirm."""
```

### `get_admin_router.admin_hosts_squad_add` (2451–2466)

**Docstring в коде:** нет. Callback `admin_hosts_squad_add:{digest}`.

```
"""Callback `admin_hosts_squad_add:`: запомнить хост и показать выбор класса сквада."""
```

### `get_admin_router.admin_hosts_squad_add_class` (2470–2490)

**Docstring в коде:** нет. Callback `admin_hosts_squad_add_class:{digest}:{class}`.

```
"""Callback `admin_hosts_squad_add_class:`: class base/lte/other (иначе base), спросить Squad UUID."""
```

### `get_admin_router.admin_hosts_squad2_uuid` (2494–2509)

**Docstring в коде:** нет. Message в `waiting_add_squad2_uuid`.

```
"""Сохранить непустой add_squad_uuid и спросить метку (`-` = пропуск)."""
```

### `get_admin_router.admin_hosts_squad2_label` (2513–2557)

**Docstring в коде:** нет. Message в `waiting_add_squad2_label`. В коде `#`: overlap не блокирует сохранение, но трафик пересечений уйдёт в LTE-пул.

```
"""add_host_squad; при успехе refresh_host_squad_overlap и предупреждение о общих нодах base/LTE."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2526–2529 | add_host_squad | except → None |
| 2532–2552 | squad_id | «добавлен» + список overlap из панели |
| 2553–2556 | иначе | дубликат UUID / уже есть активный класс |
| 2557 | всегда | show_admin_host_squads |

### `get_admin_router.admin_hosts_delete` (2561–2576)

**Docstring в коде:** нет. Callback `admin_hosts_delete:{digest}`.

```
"""Callback `admin_hosts_delete:`: спросить подтверждение; предупредить, что тарифы хоста тоже удалятся."""
```

Ещё не вызывает `delete_host`.

### `get_admin_router.admin_hosts_delete_confirm` (2580–2597)

**Docstring в коде:** нет. Callback `admin_hosts_delete_confirm:{digest}`.

```
"""Callback `admin_hosts_delete_confirm:`: delete_host(host_name), исключение глотается; список хостов."""
```

### `get_admin_router.admin_hosts_rename` (2601–2618)

**Docstring в коде:** нет. Callback `admin_hosts_rename:{digest}`.

```
"""Callback `admin_hosts_rename:`: FSM waiting_rename, спросить новое имя (ввод — хендлер ниже по файлу)."""
```

### `get_admin_router.admin_hosts_toggle_class` (2622–2659)

**Docstring в коде:** есть. Callback `admin_hosts_toggle_class:{digest}`. В коде `#`: источник LTE — host_squads, node_class только значок; сквад сам не создаётся.

```
Переключение класса ноды: ♾ Unlimited <-> 💰 Premium (LTE).
```

`get_host_class` → `set_host_class`: `premium` ↔ `unlim` (сбой чтения → считать unlim). Alert с note, если premium без LTE-сквада или unlim при живом LTE-скваде; затем карточка хоста.
