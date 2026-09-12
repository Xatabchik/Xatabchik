# Комментарии: `modules/ramadan_tracker/bot_handlers.py`

Модульного docstring нет. Плагин: модульный `Router`, prefix callback `mod:ramadan_tracker:`. Команды `/ramadan`, `/ramadan_tracker`.

По коду (не README): score топа = Σ(`morning_adhkar=1` → 1 + `evening_adhkar=1` → 1 + сырой `salawat_count`). Таравих в score не входит. Салават — `+1` за нажатие, лимита 100–10000 в этом файле нет. Фонд — настройка `reward_amount` (не `prize_fund`). `_reward_already_given` / `_save_reward` в `_generate_rewards` не вызываются.

## `WithdrawalStates` (27–28)

**Docstring в коде:** нет

```
"""FSM админа: ждём фото доказательства выплаты (`waiting_proof`)."""
```

## `open_ramadan_tracker` (33–37)

**Docstring в коде:** нет

```
"""Команды /ramadan и /ramadan_tracker: автовыплата если пора, главное меню."""
```

## `open_ramadan_tracker_callback` (41–45)

**Docstring в коде:** нет

```
"""Callback `mod:ramadan_tracker:menu`: то же меню через _safe_edit."""
```

## `show_adhkar_menu` (49–52)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_menu`: статусы утра/вечера за сегодня."""
```

## `show_adhkar_morning` (56–59)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_morning`: деталь morning_adhkar + кнопки читал/пропустил."""
```

## `show_adhkar_evening` (63–66)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_evening`: то же для evening_adhkar."""
```

## `mark_morning_read` (70–75)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_morning_read`: _set_adhkar_status(..., 1), toast, перерисовать деталь."""
```

## `mark_morning_missed` (79–84)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_morning_missed`: status=-1, перерисовать."""
```

## `mark_evening_read` (88–93)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_evening_read`: evening_adhkar=1."""
```

## `mark_evening_missed` (97–102)

**Docstring в коде:** нет

```
"""Callback `…:adhkar_evening_missed`: evening_adhkar=-1."""
```

## `show_salawat_menu` (106–109)

**Docstring в коде:** нет

```
"""Callback `…:salawat_menu`: сегодня / месяц + кнопка +1."""
```

## `add_salawat_one` (113–118)

**Docstring в коде:** нет

```
"""Callback `…:salawat_add`: _add_salawat(amount=1), toast «+1 салават»."""
```

## `show_taraweeh_menu` (122–125)

**Docstring в коде:** нет

```
"""Callback `…:taraweeh_menu`: статус таравиха за сегодня."""
```

## `mark_taraweeh_mosque` (129–134)

**Docstring в коде:** нет

```
"""Callback `…:taraweeh_mosque`: place=mosque."""
```

## `mark_taraweeh_home` (138–143)

**Docstring в коде:** нет

```
"""Callback `…:taraweeh_home`: place=home."""
```

## `mark_taraweeh_missed` (147–152)

**Docstring в коде:** нет

```
"""Callback `…:taraweeh_missed`: place=missed."""
```

## `show_today_stats` (156–159)

**Docstring в коде:** нет

```
"""Callback `…:stats_today`: статистика дня + назад (админу ещё «Начислить награду»)."""
```

## `show_total_stats` (163–166)

**Docstring в коде:** нет

```
"""Callback `…:stats_total`: суммы за все дни пользователя."""
```

## `show_top` (170–174)

**Docstring в коде:** нет

```
"""Callback `…:top`: _ensure_auto_payout, топ и кнопка вывода если can_withdraw."""
```

## `reward_top_user` (178–187)

**Docstring в коде:** нет

```
"""Callback `…:reward`: только админ; _generate_rewards(manual=True), потом главное меню."""
```

Не-админ — alert «Недостаточно прав». Toast: `show_alert=not ok`.

## `request_withdraw` (191–225)

**Docstring в коде:** нет. В коде `#`: создаём тикет в support-боте.

```
"""Callback `…:withdraw`: победителю — тикет support + mark requested_at; нет тикета — кнопка URL."""
```

Нет строки в reward_users за текущий `end_date` → «не в списке». Нет `support_bot_username` → «не настроен». `_mark_withdraw_requested` зовётся **всегда** после попытки тикета (и при False). Успех тикета — текст в чат; иначе URL из `_build_support_url`.

## `show_admin_menu` (229–235)

**Docstring в коде:** нет

```
"""Callback `…:admin_menu`: админ-меню модуля."""
```

## `show_admin_stats` (239–245)

**Docstring в коде:** нет

```
"""Callback `…:admin_stats`: глобальные счётчики daily."""
```

## `show_admin_top` (249–255)

**Docstring в коде:** нет

```
"""Callback `…:admin_top`: топ с полными user_id."""
```

## `show_admin_withdrawals` (259–265)

**Docstring в коде:** нет

```
"""Callback `…:admin_withdrawals`: список запросов + кнопки ✅/❌."""
```

## `delete_withdrawal_request` (269–288)

**Docstring в коде:** нет. В коде `#`: format `delete_withdrawal:ID`, обновить список.

```
"""Callback `…:delete_withdrawal:{id}`: админ, _delete_withdrawal_request (NULL requested_at), перерисовать."""
```

`parts[-1]` — id. Меньше 4 частей → «Неверный формат».

## `complete_withdrawal_request` (292–317)

**Docstring в коде:** нет

```
"""Callback `…:complete_withdrawal:{id}`: FSM waiting_proof, кнопки «Без скриншота» / «Отмена»."""
```

По коду кнопки: `complete_no_proof:{id}` и `admin_withdrawals`, не «с доказательством» отдельным callback — доказательство это следующее фото.

## `complete_without_proof` (321–337)

**Docstring в коде:** нет

```
"""Callback `…:complete_no_proof:{id}`: completed без proof, clear FSM, список."""
```

`edit_text` списка (не `_safe_edit`).

## `handle_proof_photo` (341–367)

**Docstring в коде:** нет. В коде `#`: самое большое фото.

```
"""Фото в waiting_proof: file_id последнего photo → _mark_withdrawal_completed, список новым сообщением."""
```

Не админ / нет withdrawal_id в FSM → clear. Документы не принимает (`F.photo`).

## `_build_menu_text` (370–390)

**Docstring в коде:** нет

```
"""Текст главного меню: сегодняшние практики + итог за месяц (счётчики, не score топа)."""
```

## `_build_today_stats_text` (393–404)

**Docstring в коде:** нет

```
"""Блок «Статистика за сегодня» по daily-строке."""
```

## `_build_total_stats_text` (407–416)

**Docstring в коде:** нет

```
"""«Статистика за весь месяц» из _get_total_stats."""
```

## `_build_adhkar_menu_text` (419–427)

**Docstring в коде:** нет

```
"""Меню азкаров: утро/вечер на сегодня."""
```

## `_build_adhkar_detail_text` (430–435)

**Docstring в коде:** нет

```
"""Заголовок утра или вечера + статус (читал/пропустил/—)."""
```

field ≠ `morning_adhkar` → подпись «Вечерние азкары».

## `_build_salawat_menu_text` (438–447)

**Docstring в коде:** нет

```
"""Салаваты сегодня и сумма за месяц."""
```

## `_build_taraweeh_menu_text` (450–458)

**Docstring в коде:** нет

```
"""Таравих сегодня: в мечети / дома / пропущен / —."""
```

## `_build_top_text` (461–484)

**Docstring в коде:** нет

```
"""Топ (маскированные id) + блок приза; can_withdraw только если есть reward и requested_at пуст."""
```

Пустой топ → текст «пуст», False. `top_limit` из настроек (default 10).

## `_build_admin_menu_text` (487–488)

**Docstring в коде:** нет

```
"""Короткий заголовок админки."""
```

## `_build_admin_stats_text` (491–501)

**Docstring в коде:** нет

```
"""Глобальные счётчики для админа."""
```

## `_build_admin_top_text` (504–513)

**Docstring в коде:** нет

```
"""Топ с полными user_id, без маски."""
```

## `_build_admin_withdrawals_text` (516–531)

**Docstring в коде:** нет

```
"""История выводов: маска id, сумма, ⏳/✅, 📎 если proof, даты."""
```

## `_build_admin_withdrawals_keyboard` (534–559)

**Docstring в коде:** нет

```
"""✅ по pending (id из БД), ❌ по всем строкам списка, назад в admin_menu; adjust(5)."""
```

Номер на кнопке — индекс в **своём** списке (pending vs все), не id.

## `_build_menu_keyboard` (562–574)

**Docstring в коде:** нет

```
"""Главные кнопки практик/статы/топ; админу — админка и «Начислить награду»."""
```

## `_build_back_keyboard` (577–583)

**Docstring в коде:** нет

```
"""Назад в menu; админу — reward."""
```

## `_build_top_keyboard` (586–594)

**Docstring в коде:** нет

```
"""«Запросить вывод» если can_withdraw; назад; админу reward."""
```

## `_build_adhkar_menu_keyboard` (597–603)

**Docstring в коде:** нет

```
"""Утренние / Вечерние / назад."""
```

## `_build_adhkar_detail_keyboard` (606–612)

**Docstring в коде:** нет

```
"""Читал / Пропустил для period morning|evening, назад в adhkar_menu."""
```

## `_build_salawat_menu_keyboard` (615–620)

**Docstring в коде:** нет

```
"""➕ salawat_add и назад."""
```

## `_build_taraweeh_menu_keyboard` (623–630)

**Docstring в коде:** нет

```
"""Дома / мечеть / пропустил / назад."""
```

## `_build_admin_menu_keyboard` (633–640)

**Docstring в коде:** нет

```
"""Статистика, топ, запросы на вывод, назад в user-menu."""
```

## `_build_admin_back_keyboard` (643–647)

**Docstring в коде:** нет

```
"""Одна кнопка назад в admin_menu."""
```

## `_safe_edit` (650–662)

**Docstring в коде:** нет

```
"""edit_text; «message is not modified» → None; иначе answer тем же текстом."""
```

## `_today_str` (665–666)

**Docstring в коде:** нет

```
"""date.today().isoformat() (YYYY-MM-DD)."""
```

## `_is_admin` (669–670)

**Docstring в коде:** нет

```
"""database.is_admin(int(user_id))."""
```

## `_get_settings` (673–687)

**Docstring в коде:** нет

```
"""Настройки модуля из loader: ключи MODULE_ID_{end_date,reward_amount,reward_enabled,top_limit,winners_count,prize_shares}."""
```

### `_get_settings._get` (677–678)

**Docstring в коде:** нет

```
"""raw.get(f'{MODULE_ID}_{key}', default)."""
```

Возврат: end_date str, reward_amount float, reward_enabled bool, top_limit int (def 10), winners_count int (def 3), prize_shares str.

## `_to_bool` (690–695)

**Docstring в коде:** нет

```
"""bool как есть; None→False; строка 1/true/yes/y/on без регистра."""
```

## `_to_int` (698–702)

**Docstring в коде:** нет

```
"""int(float(value)) или default."""
```

## `_to_float` (705–709)

**Docstring в коде:** нет

```
"""float(value) или 0.0."""
```

## `_get_daily_row` (712–731)

**Docstring в коде:** нет

```
"""Гарантировать строку дня и вернуть morning/evening/salawat/taraweeh; нет row → нули."""
```

## `_ensure_daily_row` (734–741)

**Docstring в коде:** нет

```
"""INSERT OR IGNORE ramadan_tracker_daily(user_id, date)."""
```

## `_set_adhkar_status` (744–762)

**Docstring в коде:** нет

```
"""Проставить morning_adhkar|evening_adhkar = 1|-1 на сегодня; иначе текст ошибки; успех «Отмечено»."""
```

field не из множества / status не 1|-1 → без UPDATE.

## `_add_salawat` (765–778)

**Docstring в коде:** нет

```
"""salawat_count += amount на сегодня. Потолка в этой функции нет."""
```

## `_set_taraweeh` (783–809)

**Docstring в коде:** нет

```
"""taraweeh_place = mosque|home|missed на сегодня; то же значение → «Уже отмечено»."""
```

Иное place → «Неверный вариант».

## `_get_total_stats` (812–834)

**Docstring в коде:** нет

```
"""Суммы пользователя: дни с adhkar=1, сумма salawat, дни mosque/home; adhkar_total=утро+вечер."""
```

## `_get_global_stats` (837–859)

**Docstring в коде:** нет

```
"""Те же агрегаты по всей daily + COUNT DISTINCT user_id."""
```

## `_get_top_rows` (862–885)

**Docstring в коде:** нет

```
"""Топ LIMIT: score = Σ(утром=1 + вечером=1 + salawat_count). Таравих не суммируется."""
```

## `_ensure_auto_payout` (888–903)

**Docstring в коде:** нет

```
"""Если reward_enabled, end_date YYYY-MM-DD, сегодня ≥ end_date и периода ещё нет — _generate_rewards(manual=False)."""
```

Выключено / пустая дата / плохой parse / рано / уже есть period → тихий return.

## `_generate_rewards` (906–941)

**Docstring в коде:** нет

```
"""Распределить фонд: проверки настроек, топ winners_count, доли, period+users, уведомить. (ok, сообщение)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 908–909 | не reward_enabled | False |
| 911–918 | нет/битая end_date | False |
| 920–921 | today < end_date **и** manual | «Рано» (авто путь сюда не доходит) |
| 923–924 | _period_generated | уже распределено |
| 926–928 | reward_amount ≤ 0 | отказ |
| 930–933 | топ пуст | отказ |
| 935–941 | shares/amounts/save/notify | True, «Награда распределена» |

Идемпотентность — строка в `ramadan_tracker_reward_periods`, не таблица `_rewards`.

## `_reward_already_given` (944–951)

**Docstring в коде:** нет

```
"""True, если в ramadan_tracker_rewards есть period_end. Из _generate_rewards не вызывается."""
```

## `_save_reward` (954–964)

**Docstring в коде:** нет

```
"""INSERT OR IGNORE в ramadan_tracker_rewards (один period_end на таблицу). Из _generate_rewards не вызывается."""
```

## `_period_generated` (967–974)

**Docstring в коде:** нет

```
"""True, если есть ramadan_tracker_reward_periods.period_end."""
```

## `_save_reward_period` (977–988)

**Docstring в коде:** нет

```
"""INSERT OR IGNORE period_end, prize_fund, winners_count."""
```

## `_save_reward_users` (991–1003)

**Docstring в коде:** нет

```
"""INSERT OR REPLACE reward_users (period, user, score, share, amount); zip(..., strict=False)."""
```

`requested_at`/`completed_at` этим INSERT не задаёт (REPLACE перезапишет строку целиком — колонки без default в INSERT станут NULL).

## `_notify_winners` (1006–1032)

**Docstring в коде:** нет

```
"""Каждому победителю create_task send_message, если есть running loop; иначе ничего не шлёт."""
```

Нет bot → return. Нет loop (`RuntimeError`) — рассылка пропущена. Кнопка — URL `_build_support_url`, не callback withdraw.

## `_get_reward_for_user` (1035–1052)

**Docstring в коде:** нет

```
"""Строка reward_users для settings.end_date и user_id (period_end, amount, requested_at) или None."""
```

Пустой end_date → None.

## `_get_withdrawal_requests` (1055–1071)

**Docstring в коде:** нет

```
"""До 50 запросов с requested_at; pending сверху, затем requested_at DESC."""
```

Колонки включая completed_at, proof_file_id (без PRAGMA-fallback панели).

## `_delete_withdrawal_request` (1074–1086)

**Docstring в коде:** есть

```
Удаляет запрос на вывод по ID.
```

По телу: `UPDATE … SET requested_at = NULL WHERE id = ?` — строку победителя не DROP.

## `_mark_withdrawal_completed` (1089–1101)

**Docstring в коде:** есть

```
Отмечает запрос на вывод как выполненный с опциональным скриншотом.
```

`completed_at = CURRENT_TIMESTAMP`, `proof_file_id` как передали (может быть None).

## `_mark_withdraw_requested` (1104–1115)

**Docstring в коде:** нет

```
"""Проставить requested_at, только если ещё NULL, по period_end+user_id."""
```

## `_format_taraweeh_place` (1118–1125)

**Docstring в коде:** нет

```
"""mosque/home/missed → «в мечети»/«дома»/«пропущен»; иначе —."""
```

## `_format_adhkar_status` (1128–1133)

**Docstring в коде:** нет

```
"""1 → «читал»; -1 → «пропустил»; иначе —."""
```

## `_parse_prize_shares` (1136–1154)

**Docstring в коде:** нет

```
"""Разобрать доли через запятую или `/`, обрезать/добить нулями до winners_count, нормализовать суммой; пусто → веса N..1."""
```

Не-float куски пропускает. total==0 после парса падает в веса.

## `_allocate_prize_fund` (1157–1167)

**Docstring в коде:** нет

```
"""Суммы: все кроме последнего round(fund*share, 2); последний — остаток, чтобы сойтись."""
```

## `_build_support_url` (1170–1178)

**Docstring в коде:** нет

```
"""https://t.me/{username}?text=Запрос%20вывода%20выигрыша из support_bot_username; пусто → None."""
```

Срезает ведущий `@`.

## `_create_withdrawal_ticket` (1181–1288)

**Docstring в коде:** есть

```
Создает тикет в support-боте для запроса на вывод выигрыша.
```

Пишет в `support_tickets` / `support_messages` напрямую (не repository). Есть open тикет → его id, `created_new=False` (новый INSERT не делается). Нет — INSERT subject `⭐ Запрос на вывод выигрыша {amount} ₽`. Всегда INSERT user-сообщения с суммой/периодом. Топик: только если `created_new` и заданы `support_forum_chat_id` + `support_bot_token` — временный `Bot(token=…)`, `create_forum_topic`, UPDATE thread, header в тему, `session.close()`. Ошибка топика — warning, функция всё равно True если тикет в БД есть. Exception снаружи → False.

## `_mask_user_id` (1291–1295)

**Docstring в коде:** нет

```
"""Первые 4 цифры + `***`; длина ≤ 4 → `***`."""
```
