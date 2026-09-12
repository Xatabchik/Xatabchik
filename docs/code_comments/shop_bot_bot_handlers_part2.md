# Комментарии: `src/shop_bot/bot/handlers.py` (часть 2)

Вторая половина пользовательского роутера `get_user_router` (с `referral_program_handler`) и модульные `notify_admin_of_purchase` / `process_successful_payment`. Часть 1 — до top-up/TON. Модульного docstring нет.

Имена — как в `INVENTORY.md`. Вложенные хелперы и дубли имён (`about_handler`, `show_instruction_handler`) идут отдельными секциями по строкам.

`process_successful_payment` — единственный fulfillment платной выдачи. Ветки в теле: `traffic_gb_topup`, `lte_gb_topup`, `main_traffic_reset`, `top_up`, затем ключ `new` / `gift` / `extend`. **Ветки `trial` в этой функции нет** — триал выдаёт `process_trial_key_creation` без оплаты и без `claim_processed_payment`.

---

## `get_user_router.referral_program_handler` (4577–4682)

**Docstring в коде:** нет. Callback `show_referral_program`.

```
"""Показать экран рефералки: ссылки, бонусы из настроек, статистика, кнопки перевода/вывода/топ."""
```

`registration_required`. Ссылки — `_build_referral_links`. Счётчики: `get_referral_count`, `get_referral_balance_all` (всего), `get_referral_balance` (доступно); ошибка float → 0.0.

| Строки | Блок | Зачем |
|--------|------|--------|
| 4607–4628 | reward_type | `fixed_purchase` / `fixed_start_referrer` / иначе %; `+1 день` если `enable_referral_days_bonus` |
| 4630–4632 | вывод | кнопка «Вывести» только если withdraw включён и баланс ≥ `minimum_withdrawal` (default 100) |
| 4661–4678 | клавиатура | share TG/сайт, перевод, вывод, способы, заявки, топ-5, назад |

### `get_user_router.referral_program_handler._to_float_setting` (4595–4601)

**Docstring в коде:** нет

```
"""Прочитать настройку как float: запятая→точка; ошибка → default."""
```

### `get_user_router.referral_program_handler._is_true_setting` (4603–4605)

**Docstring в коде:** нет

```
"""True, если настройка в {1,true,yes,on,y}; пусто → default (строка true/false)."""
```

### `get_user_router.referral_program_handler._fmt_num` (4613–4618)

**Docstring в коде:** нет

```
"""Формат числа с отрезанием хвостовых нулей и точки; ошибка → str(x)."""
```

---

## `get_user_router.referral_top_handler` (4688–4732)

**Docstring в коде:** нет. Callback `show_referral_top`.

```
"""Топ-5 «богатых» рефереров (`get_referral_top_rich(5)`) и место текущего пользователя."""
```

`get_referral_rank_and_count`: в рейтинге только если `rank is not None` и `personal_count > 0`. В топе telegram_id маскируется: первые 5 символов + `*****` (короткий id — целиком + `*****`). Назад — `show_referral_program`.

---

## `get_user_router._ref_is_true` (4739–4741)

**Docstring в коде:** нет

```
"""То же, что `_is_true_setting`: настройка в {1,true,yes,on,y}."""
```

## `get_user_router._ref_float_setting` (4743–4748)

**Docstring в коде:** нет

```
"""float настройки с заменой запятой; ошибка → default."""
```

## `get_user_router._ref_withdraw_enabled` (4750–4751)

**Docstring в коде:** нет

```
"""True, если `referral_withdraw_enabled` истинна (default False)."""
```

## `get_user_router._ref_method_enabled` (4753–4758)

**Docstring в коде:** нет. Аннотация `-> dict`, по коду возвращает **bool**.

```
"""Включён ли тип вывода: sbp / card / usdt_trc20; неизвестный тип → False."""
```

Флаги: `referral_withdraw_sbp_enabled`, `referral_withdraw_card_enabled`, `referral_withdraw_usdt_enabled`.

## `get_user_router._ref_sbp_banks` (4760–4762)

**Docstring в коде:** нет

```
"""Список банков СБП из `referral_withdraw_sbp_banks` (через запятую, пустые отброшены)."""
```

## `get_user_router._ref_mask` (4766–4772)

**Docstring в коде:** нет

```
"""Маска реквизита: цифры → `*` + последние 4; без цифр — html_escape исходной строки."""
```

## `get_user_router._kb_my_balance` (4774–4784)

**Docstring в коде:** нет

```
"""Клавиатура баланса: перевод; вывод если can_withdraw_now; способы/заявки если withdraw_enabled; назад."""
```

---

## `get_user_router.referral_my_balance` (4788–4796)

**Docstring в коде:** нет. Callback `referral_my_balance`. В коде `#`: совместимость со старыми кнопками.

```
"""Очистить FSM и показать `referral_program_handler` — отдельного экрана баланса больше нет."""
```

---

## `get_user_router.referral_withdraw_requests` (4807–4836)

**Docstring в коде:** нет. Callback `referral_withdraw_requests`. `@catch_callback_errors`.

```
"""Список до 20 заявок `list_referral_withdrawal_requests`: сумма, способ, маска, статус, причина reject."""
```

Статусы `_REF_STATUS_LABELS`: new / processing / paid / rejected.

---

## `get_user_router.referral_transfer_start` (4841–4861)

**Docstring в коде:** нет. Callback `referral_transfer_start`.

```
"""Начать перевод с реферального на основной: FSM `waiting_transfer_amount`, если баланс > 0."""
```

Баланс ≤ 0 → alert, без смены сообщения.

---

## `get_user_router.referral_transfer_amount` (4865–4921)

**Docstring в коде:** нет. Message, `ReferralWithdraw.waiting_transfer_amount`.

```
"""Списать реф. баланс и зачислить на основной; при сбое add_to_balance — откат `add_to_referral_balance`."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4868–4879 | валидация | число > 0 и ≤ текущего реф. баланса |
| 4880–4891 | deduct + add | deduct fail / add fail → сообщение, при add fail — откат |
| 4892–4907 | log_transaction | method `ReferralTransfer`, metadata `referral_transfer`; ошибка — warning |
| 4912–4920 | ответ | новые балансы + `_kb_my_balance` |

---

## `get_user_router._kb_payout_methods` (4923–4937)

**Docstring в коде:** нет

```
"""Клавиатура способов: «Добавить» если вывод включён; до 20 кнопок удаления `rpm_delete:{id}`; назад на referral_my_balance."""
```

## `get_user_router.referral_payout_methods` (4941–4964)

**Docstring в коде:** нет. Callback `referral_payout_methods`.

```
"""Список сохранённых способов; если вывод выключен — alert и выход."""
```

## `get_user_router._kb_method_types` (4966–4976)

**Docstring в коде:** нет

```
"""Кнопки типов СБП/карта/USDT только если соответствующий `_ref_method_enabled`; отмена на список."""
```

## `get_user_router.referral_payout_method_add` (4980–4990)

**Docstring в коде:** нет. Callback `referral_payout_method_add`.

```
"""Экран выбора типа способа; недоступно, если вывод выключен или ни один тип не включён."""
```

## `get_user_router._kb_bank_choice` (4992–4998)

**Docstring в коде:** нет

```
"""Кнопки банков `rpm_bank:{index}` (до 30), 2 в ряд; отмена на список способов."""
```

## `get_user_router.referral_payout_method_add_type` (5002–5020)

**Docstring в коде:** нет. Callback `rpm_add_type:`.

```
"""Сохранить тип в FSM: СБП → выбор банка; карта/USDT → ввод значения."""
```

СБП без списка банков → alert. Иначе `waiting_method_bank` / `waiting_method_value`.

## `get_user_router.referral_payout_method_bank_choice` (5024–5038)

**Docstring в коде:** нет. `rpm_bank:` + `waiting_method_bank`.

```
"""Записать выбранный банк в FSM и спросить телефон СБП."""
```

Индекс вне списка / не-число → alert.

## `get_user_router.referral_payout_method_value` (5042–5064)

**Docstring в коде:** нет. Message, `waiting_method_value`.

```
"""`add_referral_payout_method` и показать обновлённый список способов."""
```

Пустое значение — повтор без clear FSM.

## `get_user_router.referral_payout_method_delete` (5068–5090)

**Docstring в коде:** нет. Callback `rpm_delete:`.

```
"""Удалить способ `delete_referral_payout_method(id, user_id)` и перерисовать список."""
```

---

## `get_user_router.referral_withdraw_start` (5094–5135)

**Docstring в коде:** нет. Callback `referral_withdraw_start`.

```
"""Старт вывода: проверка флага, минимума и наличия включённых способов; FSM выбора метода."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5099–5101 | вывод выкл | alert |
| 5105–5109 | баланс < min | alert с суммами |
| 5110–5120 | нет способов | текст «добавьте способ» + `_kb_payout_methods([], True)` |
| 5121–5134 | иначе | кнопки `rwd_method:{id}`, `waiting_withdraw_choose_method` |

## `get_user_router.referral_withdraw_choose_method` (5139–5161)

**Docstring в коде:** нет. `rwd_method:` + `waiting_withdraw_choose_method`.

```
"""Проверить, что способ принадлежит пользователю; спросить сумму (`waiting_withdraw_amount`)."""
```

## `get_user_router.referral_withdraw_amount` (5165–5215)

**Docstring в коде:** нет. Message, `waiting_withdraw_amount`.

```
"""Создать заявку `create_referral_withdrawal_request` и уведомить всех `get_admin_ids`."""
```

Вывод выключен → clear state. Сумма < min → повтор ввода. Успех + `new_id` → `format_referral_withdrawal_admin_notice` каждому админу; ошибка send — warning. Затем экран «Мой баланс».

---

## `get_user_router.about_handler` (5220–5236)

**Docstring в коде:** нет. Callback `show_about`. Первое объявление имени.

```
"""Экран «О проекте»: `about_text` (или заглушка) и `create_about_keyboard` (канал/оферта/privacy)."""
```

Имя перекрывается вторым `about_handler` (5292); оба хендлера уже зарегистрированы декоратором.

---

## `get_user_router.user_speedtest_last_handler` (5241–5288)

**Docstring в коде:** нет. Callback `user_speedtest_last`.

```
"""Последний SSH-speedtest по каждой цели `get_all_ssh_targets` + `get_latest_speedtest`."""
```

Нет имени цели — пропуск. Нет замера — «данных нет». edit_text fail → answer. Пустой список целей — «(цели не настроены)».

---

## `get_user_router.about_handler` (5292–5309)

**Docstring в коде:** нет. Callback `show_help`. Второе объявление того же имени.

```
"""Экран помощи: ссылка на support-бота, иначе `support_user`, иначе «контакты не настроены»."""
```

Логика совпадает с `support_menu_handler`.

---

## `get_user_router.support_menu_handler` (5313–5330)

**Docstring в коде:** нет. Callback `support_menu`.

```
"""То же ветвление, что `show_help`: support-бот / внешний контакт / заглушка."""
```

## `get_user_router.support_external_handler` (5334–5350)

**Docstring в коде:** нет. Callback `support_external`.

```
"""Внешний контакт: если задан support-бот — его ссылка; иначе `support_user` или «не настроен»."""
```

## `get_user_router.support_new_ticket_handler` (5354–5363)

**Docstring в коде:** нет. Callback `support_new_ticket`.

```
"""Заглушка: тикеты только в support-боте; иначе «контакты не настроены». Тикет в основном боте не создаётся."""
```

## `get_user_router.support_subject_received` (5367–5376)

**Docstring в коде:** нет. Message, `SupportDialog.waiting_for_subject`.

```
"""Сбросить FSM и отправить в support-бота (или «не настроено»). Тему не сохраняет."""
```

## `get_user_router.support_message_received` (5380–5389)

**Docstring в коде:** нет. `waiting_for_message`.

```
"""Сбросить FSM; тело обращения не пишется — только редирект в support-бота."""
```

## `get_user_router.support_my_tickets_handler` (5393–5402)

**Docstring в коде:** нет. Callback `support_my_tickets`.

```
"""Список тикетов в основном боте не строится — редирект в support-бота."""
```

## `get_user_router.support_view_ticket_handler` (5406–5415)

**Docstring в коде:** нет. Callback `support_view_`.

```
"""Просмотр тикета в основном боте отключён — редирект в support-бота."""
```

## `get_user_router.support_reply_prompt_handler` (5419–5429)

**Docstring в коде:** нет. Callback `support_reply_`.

```
"""Очистить FSM; ответ пишется только в support-боте."""
```

## `get_user_router.support_reply_received` (5433–5442)

**Docstring в коде:** нет. `waiting_for_reply`.

```
"""Сбросить FSM; текст ответа в БД/форум не уходит."""
```

## `get_user_router.forum_thread_message_handler` (5445–5489)

**Docstring в коде:** нет. Message, `F.is_topic_message == True`. Без `registration_required`.

```
"""Релей ответа админа из форум-топика пользователю тикета; свой бот и не-админы игнорируются."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5447–5450 | support_bot_username и me ≠ support | выход: релей только если этот бот и есть support (или username пуст) |
| 5451–5457 | нет thread / нет тикета | выход |
| 5459–5460 | from_user == me | не релеить свои сообщения |
| 5462–5470 | админ | `is_admin` или статус ADMINISTRATOR/CREATOR в чате |
| 5471–5487 | контент | `add_support_message(sender='admin')` если есть текст/caption; header + copy_message, fallback send текста |

Ошибка всего хендлера — warning, без ответа пользователю.

## `get_user_router.support_close_ticket_handler` (5493–5502)

**Docstring в коде:** нет. Callback `support_close_`.

```
"""Закрытие тикета в основном боте не выполняется — редирект или «не настроено»."""
```

---

## `get_user_router._remnawave_key_exists` (5506–5526)

**Docstring в коде:** есть

```
Проверяет, существует ли ключ (пользователь) в Remnawave.

        Возвращает:
        - True  — ключ найден
        - False — ключ точно удалён (404 на поддерживаемом lookup)
        - None  — не удалось проверить (ошибка API/сети или UUID на 3.x без username)
```

`panel_user_exists(user_ref=uuid, email, host_name)`. `RemnawaveAPIError` и любой Exception → None.

---

## `get_user_router._extract_connected_devices` (5531–5654)

**Docstring в коде:** есть

```
Возвращает количество подключённых устройств (HWID/Devices) по данным Remnawave.

        В Remnawave это поле встречается в разных форматах:
        - списком (list)
        - объектом-пейджером (dict) с полями data/items/list и т.п.
        - уже готовым числом count/total
        Поэтому парсер старается быть максимально терпимым к схеме.
```

Не-dict → 0. Порядок: list-like ключи → count-ключи → вложенный hwid/hwidInfo/deviceInfo/devicesInfo → скан всех ключей с hwid/device, **исключая** limit/max/quota (в коде `#`: не путать с лимитом устройств).

### `get_user_router._extract_connected_devices._count_from_value` (5543–5572)

**Docstring в коде:** нет

```
"""Посчитать устройства из list/int/digit-str/пейджера (data/items/… или total/count). Иначе None."""
```

---

## `get_user_router._get_connected_devices_count` (5657–5732)

**Docstring в коде:** есть

```
Надёжно получить количество подключённых HWID-устройств.

        Remnawave не всегда возвращает HWID-устройства внутри /api/users,
        поэтому если в user_payload получается 0 — делаем отдельный запрос
        /api/hwid/devices/{userUuid}.
```

`base_cnt > 0` → сразу вернуть. Не-dict payload или нет uuid → 0. Запрос `get_hwid_devices_for_user`; ошибка → payload None → `_count_any` даст 0.

### `get_user_router._get_connected_devices_count._count_any` (5686–5730)

**Docstring в коде:** нет

```
"""Рекурсивно посчитать HWID из list/int/str/dict (total/items/…); ключи limit/max/quota пропускает."""
```

None → 0. В dict сначала готовые count, затем контейнеры, затем скан ключей.

---

## `get_user_router._get_devices_list` (5735–5786)

**Docstring в коде:** есть

```
Получить полный список подключённых HWID-устройств с информацией о каждом.
        
        Возвращает список словарей вида:
        {
            'hwid': 'device_id',
            'platform': 'iOS' или None,
            'osVersion': '16.0' или None,
            'deviceModel': 'iPhone 12' или None,
            'userAgent': '...' или None,
        }
```

Не-dict / нет uuid / ошибка API / пустой ответ → `[]`. Контейнеры: сам list, либо devices/list/response/data/items. Берёт первый непустой список dict. Поля из docstring — контракт ожидаемой схемы; разбор полей элементов здесь не делается.

---

## `get_user_router._is_key_without_billing_plan` (5789–5818)

**Docstring в коде:** есть

```
Триальный или подарочный ключ: биллингового тарифа у него нет.

        Для таких ключей `plan_id` в description намеренно None (см. вызовы
        `_build_key_origin_meta(source="trial"/"gift", plan_id=None)`), поэтому подставлять
        им «первый активный тариф хоста» нельзя: это исказило бы и лимиты в карточке
        ключа, и набор пакетов докупки.

        TODO: для подарочных ключей точный тариф известен в `user_gifts.plan_id`
        (rw_repo.get_gift_info_by_key_id) — при необходимости докупку для подарков можно
        включить, резолвя тариф оттуда, а не эвристикой по хосту.
```

True если tag ∈ {trial, триал} или `"gift" in tag`, либо JSON description: `is_trial` или source ∈ {trial, gift}.

---

## `get_user_router._resolve_plan_id_for_key` (5820–5855)

**Docstring в коде:** есть

```
Определяет plan_id, привязанный к ключу.

        Приоритеты:
          1) plan_id из vpn_keys.description (JSON, пишется при покупке/продлении);
          2) fallback на первый активный тариф хоста — как в `_get_tariff_info_for_key`.

        Без п.2 у ключей, выданных до появления этого поля (или с не-JSON description),
        докупка ГБ/LTE была недоступна, хотя тариф хоста существует и карточка ключа
        показывала его название через fallback в `_get_tariff_info_for_key`.
```

После п.1: `_is_key_without_billing_plan` → None (fallback хоста не применяется). Нет host_name / нет планов / не-int plan_id → None.

---

## `get_user_router._extract_traffic_used_bytes` (5858–5877)

**Docstring в коде:** есть

```
Извлекает использованный трафик из payload пользователя Remnawave (если поле есть).
```

Не-dict → 0. Первое положительное из `trafficUsedBytes` / `traffic_used_bytes` / `usedTrafficBytes` / `trafficUsed` / `traffic_used` / `usedBytes` / `bytesUsed`. Рекурсии вложенных объектов нет.

## `get_user_router._format_bytes_gb` (5879–5884)

**Docstring в коде:** нет

```
"""Байты → строка ГиБ с отрезанием хвостовых нулей; ошибка → «0»."""
```

---

## `get_user_router._get_tariff_info_for_key` (5886–6088)

**Docstring в коде:** есть

```
Подбирает данные тарифа для отображения в 'Мои ключи'.

        Приоритеты:
          1) точные данные из Remnawave (user_payload.hwidDeviceLimit)
          2) тариф, выбранный при покупке/продлении (vpn_keys.description JSON -> plan_id)
          3) fallback на первый активный тариф хоста
```

Возвращает `(group, plan_name, device_limit)`, где `group` = `f"{device_limit} устройств📡"`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 5901–5915 | trial эвристика | tag trial/триал; email `trial_*` или `@bot.local`+trial |
| 5917–5961 | description | tariff_label / is_trial / plan_id / device limit / duration |
| 5965–5977 | payload | первое hwidDeviceLimit/deviceLimit/… > 0 |
| 5979–5992 | план | get_plan_by_id, иначе первый активный/любой план хоста |
| 5997–6045 | из плана | имя, лимит устройств, duration_days или months*30; origin_locked не перезаписывает имя цифрами |
| 6047–6066 | fallback лимита | meta ключа, затем `trial_device_limit` |
| 6068–6086 | финал | окно created→expiry в днях; имя «—»; device_limit default **5** |

---

## `get_user_router.sync_user_keys_with_remnawave` (6090–6170)

**Docstring в коде:** есть

```
Синхронизирует ключи пользователя в БД с фактическими ключами в Remnawave.

        Раньше бот *сразу* удалял ключ из локальной БД, если Remnawave отвечал 404.
        При большом количестве пользователей (>500) и/или проблемах пагинации/поиска на панели
        это могло приводить к ложным 404 и массовым удалениям активных ключей.

        Новая логика безопаснее:
        - если ключ не найден, сначала помечаем его как "missing_from_server_at"
        - удаляем из БД только если ключ отсутствует повторно и "missing_from_server_at" старше 24 часов
        - если ключ снова найден — снимаем пометку missing_from_server_at

        Возвращает количество удалённых из БД ключей.
```

Нет ключей → 0. Проверки параллельно `asyncio.gather(..., return_exceptions=True)`. Exception в результате — пропуск. `exists is None` (ошибка API) — ничего. `exists is False` и метка старше 24 ч → `delete_key_by_id`; иначе пишем `missing_from_server_at`. `exists is True` и была метка → сброс в None.

### `get_user_router.sync_user_keys_with_remnawave._parse_missing_dt` (6111–6126)

**Docstring в коде:** нет

```
"""Разобрать missing_from_server_at в naive-UTC; пусто/ошибка → None."""
```

### `get_user_router.sync_user_keys_with_remnawave._check` (6128–6130)

**Docstring в коде:** нет

```
"""Вернуть (key, exists) из `_remnawave_key_exists`."""
```

---

## `get_user_router.manage_keys_handler` (6173–6194)

**Docstring в коде:** нет. `manage_keys` или `keys_page_*`.

```
"""Список ключей (без tag user_gift/gift) + пагинация; на page 0 — sync с панелью."""
```

Подарки передаются в клавиатуру отдельно (`gift_keys`).

## `get_user_router.sent_gifts_handler` (6198–6211)

**Docstring в коде:** нет. `sent_gifts` или `gift_keys_page_*`.

```
"""Пагинированный список отправленных подарков (tag user_gift/gift)."""
```

## `get_user_router.search_my_keys_handler` (6215–6221)

**Docstring в коде:** нет. Callback `search_my_keys`.

```
"""Поставить FSM `search_keys_state` и спросить название/email."""
```

## `get_user_router.search_keys_input_handler` (6225–6251)

**Docstring в коде:** нет. Message, `search_keys_state`.

```
"""`search_user_keys_by_email`; пустой ввод / не найдено — повтор; иначе сохранить results в state."""
```

Сообщение просит «название или email», поиск идёт по email-функции.

## `get_user_router.search_keys_page_handler` (6255–6275)

**Docstring в коде:** нет. Callback `search_keys_page_`.

```
"""Переключить страницу результатов из `state.search_results`; пустые results — alert."""
```

## `get_user_router.cancel_search_keys_handler` (6279–6289)

**Docstring в коде:** нет. Callback `cancel_search_keys`.

```
"""Сбросить FSM и вернуть `create_keys_management_keyboard` всех ключей (без фильтра подарков)."""
```

---

## `get_user_router.rename_key_start` (6297–6337)

**Docstring в коде:** есть

```
Начало процесса переименования ключа.
```

`rename_key_{id}`. Чужой/нет ключа — alert. FSM `KeyManagement.waiting_for_rename`, в state `key_id`. Клавиатура зависит от `has_name`.

## `get_user_router.rename_key_process` (6341–6430)

**Docstring в коде:** есть

```
Обработка ввода нового названия ключа.
```

Нет key_id / чужой ключ — clear. Длина > 30 или пусто — повтор без clear. `update_key_name`; успех — карточка через `get_key_details_from_host` + HWID/тариф/gift; иначе список ключей.

## `get_user_router.remove_key_name` (6434–6505)

**Docstring в коде:** есть

```
Удаление названия ключа.
```

`remove_key_name_{id}`. `update_key_name(key_id, None)`, clear state, затем та же перерисовка карточки.

## `get_user_router.cancel_rename_key` (6509–6568)

**Docstring в коде:** есть

```
Отмена переименования ключа.
```

`cancel_rename_key_{id}`. Clear + карточка; нет connection_string — «не удалось загрузить»; Exception — «Отменено» + список ключей.

---

## `get_user_router.trial_period_handler` (6576–6603)

**Docstring в коде:** нет. Callback `get_trial`.

```
"""Выдать триал или показать выбор хоста; повторный триал (`trial_used`) — alert."""
```

Нет хостов — текст ошибки. Если `trial_default_host` есть среди хостов — сразу `process_trial_key_creation`. Один хост — без выбора. Иначе клавиатура `action="trial"`.

## `get_user_router.trial_host_selection_handler` (6607–6610)

**Docstring в коде:** нет. Callback `select_host_trial_`.

```
"""Создать триал на хосте из хвоста callback.data."""
```

## `get_user_router.process_trial_key_creation` (6612–6720)

**Docstring в коде:** нет. Не хендлер роутера — вызывается из trial-хендлеров.

```
"""Создать бесплатный ключ на хосте, пометить trial_used, бонус рефереру, записать ключ с origin trial."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 6613–6616 | прогресс | `trial_duration_days` и имя хоста |
| 6621–6645 | email + лимиты | `generate_key_email_for_user` или `{uid}-{ts}@bot.local`; опционально GB и device из настроек |
| 6647–6682 | панель | `create_or_update_key_on_host(..., raise_on_error=True)`; fail → `_handle_key_creation_failure(..., refund=False)` |
| 6684–6690 | после успеха | `set_trial_used`; `grant_referrer_day_bonus_for_trial` |
| 6692–6716 | БД + UI | `_build_key_origin_meta(source="trial", plan_id=None, is_trial=True)`, tag=`trial`; delete прогресса + `get_purchase_success_text("new", ...)` |
| 6718–6720 | except | лог + «ошибка при создании пробного ключа» |

В `process_successful_payment` эта ветка не заходит.

---

## `get_user_router.show_key_handler` (6724–6872)

**Docstring в коде:** нет. Callback `show_key_`.

```
"""Карточка ключа: connection string, HWID, тариф, трафик/LTE/сброс, автопродление, gift-ссылка."""
```

Чужой ключ — ошибка. Нет details: если `_remnawave_key_exists is False` — `delete_key_by_id` и «удалён на сервере»; иначе «ошибка на сервере».

| Строки | Блок | Зачем |
|--------|------|--------|
| 6777–6794 | plan | `_resolve_plan_id_for_key`; `show_traffic_topup` если `traffic_limit_bytes > 0` |
| 6796–6813 | основной пул | used + boost / лимит; дата `format_next_traffic_reset_display` |
| 6819 | main reset | `show_traffic_topup and main_reset_price_rub > 0` |
| 6821–6844 | LTE | только `should_account_lte_traffic`; лейбл сквада; used/total через `resolve_lte_limit_bytes` |
| 6858–6868 | клавиатура | флаги topup/lte/reset + `auto_renew` + `lte_label` |

---

## `get_user_router.auto_renew_key_toggle` (6876–6894)

**Docstring в коде:** нет. Callback `auto_renew_key_`.

```
"""Инвертировать `auto_renew` одного ключа и перерисовать карточку через `show_key_handler`."""
```

Чужой ключ / не-int id — alert. После записи — `callback.model_copy(update={"data": f"show_key_{key_id}"})`.

## `get_user_router.toggle_auto_renew_profile` (6898–6908)

**Docstring в коде:** нет. Callback `toggle_auto_renew_profile`.

```
"""Если хоть один ключ с auto_renew — выключить все; иначе включить все. Затем профиль."""
```

---

## `get_user_router.switch_server_start` (6912–6939)

**Docstring в коде:** нет. Callback `switch_server_`.

```
"""Список хостов кроме текущего для переноса ключа (`action=switch_{key_id}`)."""
```

Нет других хостов / нет ключа — alert.

## `get_user_router.select_host_for_switch` (6943–7075)

**Docstring в коде:** нет. Callback `select_host_switch_{keyId}_{host}`.

```
"""Создать ключ на новом хосте с тем же expiry, удалить клиента на старом, обновить БД и карточку."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 6972–6978 | expiry | из `expiry_date`; ошибка → now+1 день |
| 6986–7010 | create | лимит/стратегия из плана ключа или полей ключа; пустой result → ошибка |
| 7013–7016 | delete old | ошибка глотается |
| 7019–7024 | БД | `update_key_host_and_info` (новый uuid + expiry) |
| 7027–7070 | UI | карточка или «Готово, обновите подписку» |
| 7071–7075 | except | лог + «ошибка при переносе» |

---

## `get_user_router.show_qr_handler` (7079–7097)

**Docstring в коде:** нет. Callback `show_qr_`.

```
"""PNG QR connection_string; чужой ключ — молчаливый return."""
```

Нет строки — alert. Ошибка — только лог, без сообщения.

---

## `get_user_router.delete_device_handler` (7101–7199)

**Docstring в коде:** есть

```
Обработчик удаления HWID-устройства с ключа.
```

`delete_device_{key_id}_{hwid}`. Нужен uuid и/или integer `user.id` из панели. `delete_hwid_device`; успех — перерисовать карточку (warning если refresh упал). Fail API — alert «не удалось».

---

## `get_user_router.show_instruction_handler` (7203–7212)

**Docstring в коде:** нет. Callback `howto_vless_{key_id}`. Первое объявление.

```
"""How-to с привязкой к ключу: `create_howto_vless_keyboard_key(key_id)`."""
```

## `get_user_router.show_instruction_handler` (7216–7224)

**Docstring в коде:** нет. Callback `startswith("howto_vless")` (общее меню без key_id).

```
"""How-to без ключа: `create_howto_vless_keyboard()`."""
```

Второе объявление перекрывает имя; оба зарегистрированы. Более специфичный `howto_vless_` зарегистрирован первым.

## `get_user_router.howto_android_handler` (7228–7272)

**Docstring в коде:** нет. Callback `howto_android`.

```
"""Текст Android из настройки или дефолт; skip edit, если текст+клавиатура не изменились."""
```

`TelegramBadRequest` «message is not modified» глотается.

## `get_user_router.howto_android_key_handler` (7276–7300)

**Docstring в коде:** нет. Callback `howto_android_`.

```
"""Тот же текст Android с клавиатурой ключа (`key_id` из 3-го сегмента; 0 → общее меню)."""
```

## `get_user_router.howto_ios_handler` (7304–7322)

**Docstring в коде:** нет. Callback `howto_ios`.

```
"""Инструкция iOS: настройка или дефолт + общее how-to меню."""
```

## `get_user_router.howto_ios_key_handler` (7326–7350)

**Docstring в коде:** нет. Callback `howto_ios_`.

```
"""iOS-текст с клавиатурой конкретного ключа."""
```

## `get_user_router.howto_windows_handler` (7354–7402)

**Docstring в коде:** нет. Callback `howto_windows`.

```
"""Инструкция Windows (Nekoray); skip, если сообщение не изменилось."""
```

## `get_user_router.howto_windows_key_handler` (7406–7434)

**Docstring в коде:** нет. Callback `howto_windows_`.

```
"""Windows-текст с клавиатурой ключа."""
```

## `get_user_router.howto_linux_handler` (7438–7459)

**Docstring в коде:** нет. Callback `howto_linux`.

```
"""Инструкция Linux (Nekoray) + общее how-to меню."""
```

## `get_user_router.howto_linux_key_handler` (7463–7490)

**Docstring в коде:** нет. Callback `howto_linux_`.

```
"""Linux-текст с клавиатурой ключа."""
```

---

## `get_user_router.gift_new_key_handler` (7494–7504)

**Docstring в коде:** нет. Callback `gift_new_key`.

```
"""Выбор хоста для подарка (`action="gift"`); нет хостов — ошибка."""
```

## `get_user_router.buy_new_key_handler` (7508–7518)

**Docstring в коде:** нет. Callback `buy_new_key`.

```
"""Выбор хоста для нового ключа (`action="new"`)."""
```

## `get_user_router.select_host_for_purchase_handler` (7522–7532)

**Docstring в коде:** нет. Callback `select_host_new_`.

```
"""Активные тарифы хоста для покупки нового ключа."""
```

## `get_user_router.select_host_for_gift_handler` (7535–7545)

**Docstring в коде:** нет. Callback `select_host_gift_`.

```
"""Активные тарифы хоста для подарочного ключа."""
```

## `get_user_router.extend_key_handler` (7550–7586)

**Docstring в коде:** нет. Callback `extend_key_`.

```
"""Тарифы хоста этого ключа для продления; чужой ключ / нет host / нет планов — ошибка."""
```

## `get_user_router.plan_selection_handler` (7590–7612)

**Docstring в коде:** нет. Callback `buy_*` (разбор: host / plan_id / action / key_id).

```
"""Записать action/key_id/plan_id/host_name в FSM; email-промпт или сразу `show_payment_options`."""
```

Email-шаг только если `payment_email_prompt_enabled`. Формат callback: `buy_{host}_{plan_id}_{action}_{key_id}` (`host` может содержать `_`).

## `get_user_router.back_to_plans_handler` (7616–7677)

**Docstring в коде:** нет. `back_to_plans` в waiting_for_email / waiting_for_payment_method.

```
"""Очистить FSM и вернуть список тарифов для `new`/`extend`; иной action — главное меню."""
```

`gift` в этом хендлере **не** обрабатывается — уходит в `back_to_main_menu_handler`.

## `get_user_router.process_email_handler` (7680–7686)

**Docstring в коде:** нет. Message, `waiting_for_email`.

```
"""Валидный email → `customer_email` + `show_payment_options`; иначе повтор."""
```

## `get_user_router.skip_email_handler` (7689–7692)

**Docstring в коде:** нет. Callback `skip_email`.

```
"""`customer_email=None` и перейти к способам оплаты."""
```

---

## `get_user_router.show_payment_options` (7694–7818)

**Docstring в коде:** нет

```
"""Показать способы оплаты с ценой: реф. скидка на первую покупку, промо, кнопки баланса."""
```

Нет плана — clear FSM. Реф. скидка: `referred_by` и `total_spent == 0` и `referral_discount` > 0. Промо: повторный `check_promo_code_available`; невалиден — снять из state. Скидка не опускает цену ниже 0.01. Кнопка основного/реф. баланса — если баланс ≥ final_price. State → `waiting_for_payment_method`. В except `TelegramBadRequest` повторный answer **без** `promo_applied`.

## `get_user_router.back_to_email_prompt_handler` (7821–7832)

**Docstring в коде:** нет. Callback `back_to_email_prompt`.

```
"""Вернуть email-промпт; если промпт выключен — `back_to_plans_handler`."""
```

## `get_user_router.prompt_promo_code` (7835–7841)

**Docstring в коде:** нет. Callback `enter_promo_code`.

```
"""Спросить промокод, FSM `waiting_for_promo_code`."""
```

## `get_user_router.cancel_promo_entry` (7844–7846)

**Docstring в коде:** нет. Callback `cancel_promo`.

```
"""Вернуться к `show_payment_options` без смены промо в state."""
```

## `get_user_router.handle_promo_code_input` (7849–7885)

**Docstring в коде:** нет. Message, `waiting_for_promo_code`.

```
"""Проверить промо на план; записать скидку (percent от цены плана или amount) и открыть оплату."""
```

`отмена`/`cancel`/`назад`/`stop`/`стоп` → назад без ошибки. Скидка ≤ 0 — «не даёт скидку».

---

## `get_user_router.create_yookassa_payment_handler` (7888–8022)

**Docstring в коде:** нет. Callback `pay_yookassa` в waiting_for_payment_method.

```
"""Создать pending + платёж YooKassa (receipt при валидном email) и показать confirmation_url."""
```

Нет shop_id/secret — clear. Цена: план − реф. скидка первой покупки − promo (min 0.01). Email чека: из FSM или `receipt_email`. `create_payload_pending`; `PromoUnavailableError` — без clear в этом except (только сообщение). Повторный pending с `yookassa_payment_id`. Metadata провайдеру — только `{payment_id}`.

## `get_user_router.pay_platega_handler` (8026–8111)

**Docstring в коде:** нет. Callback `pay_platega`.

```
"""Pending + ссылка Platega; сохранить `platega_transaction_id`; клавиатура оплаты."""
```

`_platega_is_enabled` false / нет плана / нет URL — clear. Та же схема скидок. `PromoUnavailableError` — clear.

## `get_user_router.pay_rollypay_handler` (8114–8199)

**Docstring в коде:** нет. Callback `pay_rollypay`.

```
"""Pending + ссылка RollyPay (`rollypay_payment_id`); текст кнопки — «оплата по СБП»."""
```

`_rollypay_is_enabled` false → «СБП не настроена».

## `get_user_router.create_cryptobot_invoice_handler` (8202–8276)

**Docstring в коде:** нет. Callback `pay_cryptobot`.

```
"""Инвойс Crypto Pay через `_create_cryptobot_invoice`; нет токена/плана/result — ошибка."""
```

Цена с теми же скидками. `state_data=data` целиком. Успех — clear; неуспех — текст без обязательного clear.

## `get_user_router.check_crypto_invoice_handler` (8279–8404)

**Docstring в коде:** нет. Callback `check_crypto_invoice:`.

```
"""Ручная сверка CryptoBot getInvoices; при paid — `process_successful_payment` (новый или legacy payload)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 8282–8292 | id / токен | некорректный id / нет токена |
| 8294–8332 | HTTP | не 200 / не paid / нет invoices → «ещё не поступила» |
| 8339–8367 | payload без `:` | internal payment_id; сверка суммы с pending; `find_and_complete_pending_transaction`; нет pending — «уже обработан» |
| 8369–8404 | legacy `a:b:...` | ≥9 полей; сверка суммы с `p[2]`; metadata собирается из payload, **без** `find_and_complete` |

## `get_user_router.create_ton_invoice_handler` (8406–8474)

**Docstring в коде:** нет. Callback `pay_tonconnect`.

```
"""Pending TON Connect: курс USDT/TON, QR + deep-link на `valid_until` now+600 с."""
```

Нет кошелька/плана/курса — clear. Цена из `final_price` или плана. `create_pending_transaction` (не `create_payload_pending`). Payload сообщения = `payment_id`. `_start_ton_connect_process`.

## `get_user_router.pay_with_main_balance_handler` (8477–8520)

**Docstring в коде:** нет. Callback `pay_balance`.

```
"""Списать основной баланс и сразу `process_successful_payment` (payment_id `balance:{uid}:{uuid}`)."""
```

`deduct_from_balance` false → alert, FSM не чистится. В коде `#`: нет внешнего id, нужен уникальный payment_id для идемпотентности.

## `get_user_router.pay_with_referral_balance_handler` (8523–8562)

**Docstring в коде:** нет. Callback `pay_referral_balance`.

```
"""Списать реф. баланс и `process_successful_payment` (payment_id `referral_balance:{uid}:{uuid}`)."""
```

---

## `get_user_router.stale_payment_method_callback` (8578–8587)

**Docstring в коде:** есть

```
Устаревшие pay_* после смены FSM (например, после Stars invoice).

        Регистрируется после штатных обработчиков waiting_for_payment_method,
        чтобы не перехватывать живой сценарий выбора метода.
```

Набор `_STALE_PAY_CALLBACKS`: balance, referral_balance, stars, yookassa, platega, rollypay, cryptobot, heleket, yoomoney, tonconnect.

---

## `get_user_router._gift_username_catcher` (8594–8716)

**Docstring в коде:** нет. Message, `StateFilter(None)`, любой текст. `@registration_required`.

```
"""Если есть pending gift — создать ключ на username получателя (не через process_successful_payment)."""
```

Текст должен матчить `^[A-Za-z0-9_]{5,}$` (опциональный `@` снимается). Pending: `get_latest_pending_for_user` или кэш `PENDING_GIFTS`; `type != "gift"` — выход.

| Строки | Блок | Зачем |
|--------|------|--------|
| 8627–8644 | email | если получатель уже в БД — email по его telegram_id; иначе `gift-{hex}@bot.local` |
| 8646–8680 | панель | `create_or_update_key_on_host`; fail → `_handle_key_creation_failure(..., refund=True)` |
| 8682–8703 | запись | `record_key_from_payload` на получателя, tag=`paid`, source gift; ошибка — warning |
| 8705–8716 | закрытие | `find_and_complete_pending_transaction`; pop PENDING_GIFTS; reply «ключ создан» |

Это **второй** путь выдачи подарка (после оплаты, по username). Основной платный gift — ветка `action=="gift"` в `process_successful_payment`.

---

## `get_user_router._kb_cancel_factory` (8723–8727)

**Docstring в коде:** нет

```
"""Кнопка отмены `factory_cancel`."""
```

## `get_user_router._kb_partner_cabinet` (8729–8736)

**Docstring в коде:** нет

```
"""Кабинет клона: реквизиты, вывод, удалить бота, назад в меню."""
```

## `get_user_router._kb_partner_withdraw` (8738–8742)

**Docstring в коде:** нет

```
"""Отмена вывода партнёра `partner_withdraw_cancel`."""
```

## `get_user_router._kb_partner_requisites` (8745–8760)

**Docstring в коде:** нет

```
"""Список реквизитов: добавить; для не-default — «сделать основной»; удалить; назад в кабинет."""
```

До 20 записей. В коде `#`: одна строка на действие, короткий callback.

## `get_user_router._kb_partner_requisite_input` (8762–8766)

**Docstring в коде:** нет

```
"""Отмена ввода реквизита `partner_requisite_cancel`."""
```

## `get_user_router._mask_requisite` (8768–8779)

**Docstring в коде:** нет

```
"""Маска цифр (* + last4); для card ≥12 цифр — группы по 4."""
```

Без цифр возвращает исходную строку **без** html_escape.

## `get_user_router._infer_requisite_type` (8781–8789)

**Docstring в коде:** нет. В коде `#`: 10–12 цифр — телефон, 13–19 — карта.

```
"""Эвристика типа реквизита: 10–12 цифр → phone, иначе card (в т.ч. fallback)."""
```

---

## `get_user_router.partner_requisites` (8793–8824)

**Docstring в коде:** нет. Callback `partner_requisites`.

```
"""Список реквизитов владельца текущего клона; root-бот и не-владелец — alert."""
```

`bot_id <= 0` — «только в клонах». `fast_callback_answer` вызывается **дважды**.

## `get_user_router.partner_requisite_add` (8828–8844)

**Docstring в коде:** нет. Callback `partner_requisite_add`.

```
"""FSM `waiting_requisites_bank`: спросить название банка."""
```

## `get_user_router.partner_requisite_cancel` (8848–8860)

**Docstring в коде:** нет. Callback `partner_requisite_cancel`.

```
"""Сбросить FSM и открыть список реквизитов; fallback — `partner_cabinet`."""
```

## `get_user_router.partner_requisite_bank` (8864–8885)

**Docstring в коде:** нет. Message, `waiting_requisites_bank`.

```
"""Сохранить банк и спросить номер карты/телефона (`waiting_requisites_value`)."""
```

Не владелец — clear. Пустой банк — повтор.

## `get_user_router.partner_requisite_value` (8889–8933)

**Docstring в коде:** нет. `waiting_requisites_value`.

```
"""`add_partner_requisite` с типом из `_infer_requisite_type` и показать список."""
```

Нет банка в state → назад на ввод банка.

## `get_user_router.partner_requisite_set_default` (8937–8966)

**Docstring в коде:** нет. Callback `req_set_default:`.

```
"""`set_default_partner_requisite` и обновить экран (`partner_requisites` или ручная перерисовка)."""
```

## `get_user_router.partner_requisite_delete` (8970–8998)

**Docstring в коде:** нет. Callback `req_delete:`.

```
"""Удалить реквизит владельца клона и перерисовать список."""
```

---

## `get_user_router.franchise_create_bot` (9002–9024)

**Docstring в коде:** нет. Callback `factory_create_bot`.

```
"""Только из root-бота: FSM токена нового клона. В клоне — alert."""
```

`resolve_factory_bot_id > 0` → отказ. В коде `#`: creation only from root.

## `get_user_router.franchise_cancel` (9028–9037)

**Docstring в коде:** нет. Callback `factory_cancel`.

```
"""Сбросить FSM и `show_main_menu` (edit)."""
```

## `get_user_router.franchise_receive_token` (9041–9100)

**Docstring в коде:** нет. Message, `FranchiseStates.waiting_bot_token`.

```
"""Проверить токен через Bot.get_me, `create_managed_bot`, `service.start_bot`, вернуть в меню."""
```

Не `TOKEN_RE` — повтор. get_me fail — «не получилось проверить». `create_managed_bot(..., referrer_bot_id=0)`. Старт клона — warning при ошибке, запись в БД уже есть. Затем `show_main_menu`.

## `get_user_router.partner_cabinet` (9104–9132)

**Docstring в коде:** нет. Callback `partner_cabinet`.

```
"""Кабинет владельца клона: пользователи, оборот картой, % франшизы, доход, доступно к выводу."""
```

Root / не владелец — alert. Цифры из `get_partner_cabinet`; процент — `get_franchise_percent_default()`, минимум — `get_franchise_min_withdraw()`.

## `get_user_router.partner_withdraw` (9136–9170)

**Docstring в коде:** нет. Callback `partner_withdraw`.

```
"""Старт вывода: нужен default-реквизит; иначе список реквизитов. FSM суммы."""
```

## `get_user_router.partner_withdraw_cancel` (9174–9187)

**Docstring в коде:** нет. Callback `partner_withdraw_cancel`.

```
"""Сбросить FSM и открыть кабинет (fallback — главное меню)."""
```

## `get_user_router.partner_withdraw_amount` (9191–9293)

**Docstring в коде:** нет. Message, `waiting_withdraw_amount`.

```
"""`create_withdraw_request` со снимком default-реквизита; админу — сообщение с root-токена."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 9203–9221 | сумма / реквизит | не-число — повтор; нет default — список реквизитов + clear |
| 9228–9237 | заявка | bank/type/value/id из default |
| 9239–9272 | админ | `admin_telegram_id` + временный `Bot(telegram_bot_token)`; HTML с суммой и реквизитом (без маски) |
| 9279–9293 | UI | попытка «обновить кабинет» через неполный CallbackQuery не используется; в конце `show_main_menu` |

После этих хендлеров `get_user_router` делает `return user_router`.

---

## `notify_admin_of_purchase` (9297–9402)

**Docstring в коде:** нет

```
"""Одному `admin_telegram_id` — карточка оплаты: хост, тариф, метод, сумма, new/gift/extend, промо-лимиты."""
```

Нет `admin_telegram_id` — тихий return. Методы Balance/ReferralBalance/Card/Crypto/USDT/TON переводятся; остальные как есть. Action в тексте: `new` → «Новый ключ», `gift` → «Подарок», **всё остальное** → «Продление» (включая top-up/LTE — по коду так). Промо-блок: applied amount, лимиты usage, disabled/expired/redeem_failed. Ошибка send — warning.

---

## `process_successful_payment` (9404–10666)

**Docstring в коде:** есть

```
Обработать успешную оплату и выдать услугу.

    Returns:
        True — услуга выдана (или платёж уже был обработан ранее).
        False — выдача не удалась; для Balance/ReferralBalance/внешних методов
        средства возвращены через ``refund_payment_once`` (идемпотентно).
```

Единственная точка платной выдачи (вебхук / Stars / «проверить» / баланс). Вызывающие: Flask/Mini App, `check_*`, `stars_success_handler`, `pay_with_*_balance`, CryptoBot check.

**Ветки `action` в теле (по коду, без выдуманных путей):**

| `metadata.action` | Что делает | return |
|-------------------|------------|--------|
| *(нет / нераспознанный до key-path)* | после early-action идёт key-path | см. new/gift/extend |
| `traffic_gb_topup` | докупка основного трафика | голый `return` → **None** |
| `lte_gb_topup` | докупка LTE-буста ключа | **None** |
| `main_traffic_reset` | сброс трафика **всех** ключей пользователя | **None** |
| `top_up` | пополнение основного баланса | **None** |
| `new` | новый ключ на хосте | True / False |
| `gift` | ключ + `user_gifts` + ссылка | True / False |
| `extend` (и любой иной action на key-path) | продление существующего ключа | True / False |
| `trial` | **нет** — триал не проходит эту функцию | — |

### Общая прелюдия (9427–9519)

| Строки | Блок | Зачем |
|--------|------|--------|
| 9428–9448 | разбор | action, user_id, price, months, key_id, host, plan_id, duration_days, email, method |
| 9450–9460 | идемпотентность | нет `payment_id`/`transaction_id` → False; `claim_processed_payment` false → **True** (дубль); ошибка claim → False |
| 9462–9490 | промо reserve | если есть promo_code: `reserve_promo_code`; fail → `unclaim_processed_payment` + False |
| 9493–9506 | франшиза | `factory_bot_id` из metadata или `resolve_factory_bot_id(bot.id)`; >0 → `accrue_partner_commission(..., 35.0)` (ошибка глотается) |
| 9508–9513 | parse fail | ValueError/TypeError metadata → False |
| 9515–9519 | UI | delete сообщения оплаты по chat_id/message_id |

Локальный `_to_int` (9434–9440): None/`''`/`None`/`null` → default.

Комментарий «Franchise…» на 9492 стоит **после** `return False` внутри promo-fail — не исполняется; живой код франшизы — 9493–9506.

### `traffic_gb_topup` (9521–9658)

Нет ключа/пакета → `_abort_topup_fulfillment` + `return`. `add_bytes = size_gb * 1024³`. Текущий лимит: payload `trafficLimitBytes` или поле ключа. Панель: `update_user_traffic_limit`. Нет uuid / update fail → abort (в коде `#`: состояние консистентно, можно вернуть деньги). Успех панели: до 3 попыток `update_key(traffic_limit_bytes, traffic_boost_bytes)`; устойчивый сбой БД → `_notify_admins_topup_desync`, **без** refund (услуга уже на панели). Затем `log_transaction`, `update_user_stats(price, 0)`, сообщение про ГБ до месячного сброса. Внешний except — лог, всё равно `return`.

### `lte_gb_topup` (9660–9777)

Нет ключа/пакета → abort. `add_key_lte_boost_bytes` атомарно (в коде `#`: не read-modify-write; baseline не сдвигается). `new_boost is None` → abort. Если ключ `disabled_premium` / `disabled_premium_squad` и есть uuid — `add_squad_to_user` или `enable_user`; успех → `remote_access_state='enabled'`. Лог + stats + сообщение «пул {lte_label} … доступ восстановлен» (текст фиксированный, даже если enable не вызывался).

### `main_traffic_reset` (9779–9854)

Ключ не найден → сообщение «обратитесь в поддержку», **без** `_abort_topup_fulfillment`. Дальше цикл по **всем** `get_user_keys(user_id)` (fallback — один key_data): `reset_user_traffic_on_host`, `enable_user`, `traffic_boost_bytes=0` + `remote_access_state='enabled'`. Счётчик `reset_errors`. Лог + stats. 0 ошибок — «сброшен, доступ на всех нодах»; иначе «часть узлов не удалось».

### `top_up` (9856–10018)

`add_to_balance`. Всегда пытается `update_user_stats(price, 0)` (в коде `#`: инвестиция в сервис). `log_transaction` action `top_up`; fail лога — error про аналитику. Рефералка: **пропуск**, если method ∈ {balance, referralbalance}; иначе как при покупке (`fixed_start_referrer` → 0, `fixed_purchase` → фикс, иначе %). Уведомление пользователю с текущим балансом + `create_profile_keyboard`; fail баланса — support keyboard. Затем **всем** `is_admin` из `get_all_users` — «Пополнение: …» (не `notify_admin_of_purchase`).

### Key-path: new / gift / extend (10020–10666)

Сообщение «Оплата получена! Обрабатываю…». `key_issued = False`.

**Email кандидата:**

- `new` — `generate_key_email_for_user` или `{uid}-{ts}@bot.local`
- `gift` — `gift-{uuid[:12]}@bot.local` (это **не** код активации; уникальный код позже)
- иначе (`extend` и любой другой) — email существующего ключа; нет ключа → `_abort_key_fulfillment` + False

План: months/days, `traffic_limit_bytes`/`strategy`/`hwid_device_limit`. None лимитов → 0 (в коде `#`: 0 = unlimited / снять кап). Стратегия **перезаписывается** `remnawave_traffic_limit_strategy_for_plan(plan)`. `days_to_add`: план → metadata → `months*30` или **30**.

`origin_desc` = `_build_key_origin_meta(source="extend" if extend else "purchase", …)`; tag `paid`.

Для `extend`: `expiry_timestamp_ms = max(текущий expiry, now) + days_to_add * 86400000` (не потерять остаток).

`create_or_update_key_on_host(..., raise_on_error=True)`. Exception / (не-gift и пустой result) → `_abort_key_fulfillment` + False. Для gift пустой result проверяется позже в своей ветке.

#### `new` (10207–10233)

`record_key_from_payload`; нет key_id → abort. `apply_key_monthly_reset_fields(..., restart_cycle=True)`. `key_issued = True`.

#### `gift` (10235–10357)

Новый `gift_code_unique = uuid[:16]`. `record_key_from_payload` tag=`user_gift`. `create_user_gift` + `link_key_to_gift` + monthly reset. Ссылка: `{domain}/start?start=gift_{code}` или `t.me/{bot}?start=gift_{code}`. Сообщение с «использовать сами / поделиться»; `key_issued = True`. Fail записи подарка/ключа/пустой result → abort + False. В коде `#` про локальный `import uuid` — его нет, uuid модульный.

#### `extend` (10359–10390)

`update_key` uuid/expiry/лимиты/tag/description. Fail → abort. `apply_key_monthly_reset_fields(..., restart_cycle=False)` (в коде `#`: срок, не сброс трафика). `key_issued = True`.

Иной action на этом уровне (не new/gift/extend) **не** ставит `key_issued` и не abort — идёт в пост-обработку с возможно пустым result.

### Пост-обработка ключа (10393–10631)

Рефералка: skip для balance/referralbalance; иначе та же формула, что top_up. `update_user_stats`: spent=0 для внутренних методов; месяцы — `ceil(days/30)` если months≤0. `log_transaction` с планом/хостом/email + provider ids.

Промо: `redeem_promo_code`; лимиты в metadata; при total_limit/expired — `update_promo_code_status(is_active=False)`. Затем delete processing_message.

Текст успеха: `get_purchase_success_text("extend" if extend else "new", …)` — gift уходит как `"new"`. Для gift в текст вставляется ссылка активации перед connection_string. Клавиатура карточки ключа. `notify_admin_of_purchase`. **return True**.

### except key-path (10633–10666)

Если `not key_issued` — `_abort_key_fulfillment` + False (fallback edit/send «ошибка при выдаче»). Если ключ уже выдан — сообщение об ошибке, но **return True** (в коде `#`: оплата успешна, несмотря на ошибку нотификации).

---

## `process_successful_payment._provider_ids_for_log` (9415–9425)

**Docstring в коде:** есть

```
Извлекает ID транзакции/инвойса на стороне платёжного провайдера из исходных
        metadata, чтобы не потерять их при пересборке metadata для log_transaction.
```

Ключи: `platega_transaction_id`, `cryptobot_invoice_id`, `heleket_uuid`, `yookassa_payment_id`, `rollypay_payment_id`. Не-dict → `{}`. Пустые значения пропускаются.
