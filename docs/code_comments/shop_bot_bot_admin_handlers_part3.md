# Комментарии: `src/shop_bot/bot/admin_handlers.py` (часть 3)

Продолжение вложенных хендлеров `get_admin_router`: промо-список, speedtest/бэкап, пользователи и ключи, рассылка, мониторинг, капча, автопродление. Модульный docstring файла — в части 1.

## `get_admin_router.admin_promo_list` (5461–5478)

**Docstring в коде:** нет. Callback `admin_promo_list`.

```
"""Показать первую страницу всех промокодов (включая неактивные); promo_page=0."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5462–5464 | не админ | alert, return |
| 5466–5473 | list_promo_codes | заголовок; пусто или первые 10 строк `_format_promo_line` |
| 5474–5478 | edit_text | клавиатура `_build_promo_list_keyboard(codes, page=0)` |

## `get_admin_router.admin_promo_change_page` (5481–5503)

**Docstring в коде:** нет. Callback `admin_promo_page_*`.

```
"""Переключить страницу списка промокодов; номер — последний `_`-сегмент (ошибка → 0)."""
```

Срез `codes[page*10 : page*10+10]`. Пишет `promo_page` в FSM.

## `get_admin_router.admin_promo_toggle` (5506–5532)

**Docstring в коде:** нет. Callback `admin_promo_toggle_*`.

```
"""Инвертировать is_active промокода (поиск без учёта регистра) и перерисовать текущую страницу."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5510–5515 | code из data, next(...) | нет совпадения → alert «не найден» |
| 5516–5518 | update_promo_code_status | new_status = not is_active |
| 5519–5532 | promo_page из state | тот же текст/клавиатура, что у списка |

## `get_admin_router.admin_speedtest_entry` (5536–5552)

**Docstring в коде:** нет. Callback `admin_speedtest`.

```
"""Показать SSH-цели speedtest (`get_all_ssh_targets`); edit_text, при сбое — answer."""
```

## `get_admin_router.admin_speedtest_ssh_targets` (5556–5571)

**Docstring в коде:** нет. Callback `admin_speedtest_ssh_targets`.

```
"""Тот же экран SSH-целей, что `admin_speedtest_entry`."""
```

## `get_admin_router.admin_speedtest_run` (5575–5659)

**Docstring в коде:** нет. Callback `admin_speedtest_pick_host_*`.

```
"""Запустить SSH+NET speedtest хоста (`run_both_for_host`); оповестить всех админов о старте и результате."""
```

Имя хоста — хвост callback после префикса. `admin_ids` = `get_admin_ids()` ∪ инициатор; ошибка импорта → только инициатор.

| Строки | Блок | Зачем |
|--------|------|--------|
| 5588–5594 | start_text всем aid | «Запущен тест…» |
| 5597–5600 | wait_msg | «Выполняю…»; сбой → None |
| 5603–5606 | run_both_for_host | исключение → `{ok: False, error, details: {}}` |
| 5633–5642 | два одинаковых if ok | info/warning и повтор с пометкой `(legacy)` |
| 5644–5659 | результат | edit wait_msg или answer; остальным админам send (инициатора с wait_msg пропускает) |

### `get_admin_router.admin_speedtest_run.fmt_part` (5609–5622)

**Docstring в коде:** нет

```
"""Строка блока SSH/NET: «—» если нет dict, ❌+error если не ok, иначе ping/↓/↑/сервер."""
```

## `get_admin_router.admin_speedtest_run_target_hashed` (5663–5730)

**Docstring в коде:** нет. Callback `stt:`.

```
"""Speedtest SSH-цели по sha1-хэшу (`_resolve_target_from_hash`); иначе «Цель не найдена»."""
```

`run_and_store_ssh_speedtest_for_target`. Рассылка старта/результата как у `admin_speedtest_run`.

## `get_admin_router.admin_speedtest_run_target` (5734–5801)

**Docstring в коде:** нет. Callback `admin_speedtest_pick_target_*`.

```
"""То же, что hashed-вариант, но имя цели из хвоста callback (legacy-префикс)."""
```

Лог: «запуск спидтеста (legacy)».

## `get_admin_router.admin_speedtest_back` (5805–5810)

**Docstring в коде:** нет. Callback `admin_speedtest_back_to_users`.

```
"""Вернуть админ-меню (`show_admin_menu`, edit_message=True)."""
```

## `get_admin_router.admin_speedtest_run_all` (5814–5855)

**Docstring в коде:** нет. Callback `admin_speedtest_run_all`.

```
"""Пройти все хосты `run_both_for_host`; сводка ↓/↑ (ssh, иначе net) всем админам кроме инициатора/чата."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5833–5846 | for hosts | ok + download/upload; except → строка с e |
| 5848–5855 | send остальным | skip если aid == from_user или chat.id |

## `get_admin_router.admin_speedtest_run_all_targets` (5859–5905)

**Docstring в коде:** нет. Callback `admin_speedtest_run_all_targets`.

```
"""Пройти все SSH-цели `run_and_store_ssh_speedtest_for_target`; пустые target_name пропускает."""
```

Лог старта и `ок={ok_total}, всего={len(targets)}`. Нет целей → «(нет целей)».

## `get_admin_router.admin_backup_db` (5909–5937)

**Docstring в коде:** нет. Callback `admin_backup_db`.

```
"""Создать zip бэкапа (`create_backup_file`) и разослать админам (`send_backup_to_admins`)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5918–5924 | zip_path falsy | «Не удалось создать» |
| 5926–5937 | send | txt с именем файла и числом sent (ошибка send → 0) |

## `AdminRestoreDB` (5940–5941)

**Docstring в коде:** нет

```
"""FSM восстановления БД: одно состояние — ожидание файла."""
```

`waiting_file`.

## `get_admin_router.admin_restore_db_prompt` (5944–5961)

**Docstring в коде:** нет. Callback `admin_restore_db`.

```
"""Перейти в AdminRestoreDB.waiting_file и попросить .zip/.db; кнопка admin_cancel."""
```

Текст: текущая БД предварительно будет сохранена. edit_text, иначе answer.

## `get_admin_router.admin_restore_db_receive` (5964–5988)

**Docstring в коде:** нет. Message, `AdminRestoreDB.waiting_file`.

```
"""Скачать документ в BACKUPS_DIR как uploaded-{ts}-{filename} и вызвать restore_from_file."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 5965–5966 | не админ | молча return |
| 5967–5974 | нет document / не .zip/.db | отказ |
| 5975–5982 | download | сбой → «Не удалось скачать» |
| 5983–5988 | restore + state.clear | успех/провал текстом |

## `get_admin_router.admin_speedtest_autoinstall` (5992–6013)

**Docstring в коде:** нет. Callback `admin_speedtest_autoinstall_*`.

```
"""Автоустановка speedtest на хосте (`auto_install_speedtest_on_host`); лог в <pre> до 3500 символов."""
```

По коду: если `wait` is None, результат никуда не отправляется (в отличие от target-вариантов).

## `get_admin_router.admin_speedtest_autoinstall_target` (6017–6045)

**Docstring в коде:** нет. Callback `admin_speedtest_autoinstall_target_*`.

```
"""Автоустановка на SSH-цели по имени (`auto_install_speedtest_on_target`); лог старта/исхода."""
```

Если wait нет или edit не удался — `answer`.

## `get_admin_router.admin_speedtest_autoinstall_target_hashed` (6049–6075)

**Docstring в коде:** нет. Callback `stti:`.

```
"""То же, что autoinstall_target, но имя через `_resolve_target_from_hash`; пусто → «Цель не найдена»."""
```

## `AdminUserSearch` (6081–6082)

**Docstring в коде:** нет

```
"""FSM поиска пользователя: ожидание ID или @username."""
```

`waiting_for_query`.

## `get_admin_router.admin_users_handler` (6085–6113)

**Docstring в коде:** нет. Callback startswith `admin_users`. В коде `#` про поиск и список/страницы.

```
"""admin_users_search → FSM ввода; иначе список get_all_users, страница из admin_users_page_*."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 6092–6099 | data == admin_users_search | waiting_for_query, примеры ID/@username |
| 6102–6113 | иначе | state.clear; page из хвоста или 0 |

## `get_admin_router.admin_users_search_process` (6117–6202)

**Docstring в коде:** нет. Message, `AdminUserSearch.waiting_for_query`. В коде `#` про ID / username / часть ID / один vs несколько.

```
"""Найти пользователя: точный ID, затем username (равенство или вхождение), затем подстрока telegram_id."""
```

Пустой ввод — повтор. Нет совпадений — остаёмся в состоянии. Один матч — карточка + `create_admin_user_actions_keyboard`. Несколько — список кнопок page=0.

## `get_admin_router.admin_view_user_handler` (6205–6247)

**Docstring в коде:** нет. Callback `admin_view_user_*`.

```
"""Карточка пользователя: ссылка t.me/@ / tg://user, spent/balance/реф, бан, пригласивший, число ключей."""
```

Не-int хвост / нет user → answer с ошибкой. edit_text карточки.

## `get_admin_router.admin_ban_user` (6251–6328)

**Docstring в коде:** нет. Callback `admin_ban_user_*`.

```
"""ban_user(user_id), уведомить жертву (кнопка support_bot_username / show_help) и обновить карточку is_banned=да."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 6261–6263 | ban_user | «забанен»; ошибка → текст e, return |
| 6265–6294 | send жертве | URL из support_bot_username / support_user (@, tg://, http→domain, иначе domain); сбой глотается |
| 6299–6328 | карточка | edit_text; сбой глотается |

## `get_admin_router.admin_admins_menu_entry` (6332–6340)

**Docstring в коде:** нет. Callback `admin_admins_menu`.

```
"""Экран «Управление администраторами» + create_admins_menu_keyboard."""
```

## `get_admin_router.admin_view_admins` (6343–6378)

**Docstring в коде:** нет. Callback `admin_view_admins`.

```
"""Список get_admin_ids() со ссылками @/профиля; кнопки назад в меню админов и admin_menu."""
```

Пустой ids → «список пуст». Ошибка get_admin_ids → [].

## `get_admin_router.admin_unban_user` (6381–6439)

**Docstring в коде:** нет. Callback `admin_unban_user_*`.

```
"""unban_user, уведомить жертву (кнопка главного меню) и обновить карточку «Забанен: нет»."""
```

Симметрично бану: ошибка unban → текст e и return; edit карточки глотается.

## `get_admin_router.admin_delete_user` (6444–6464)

**Docstring в коде:** нет. Callback `admin_delete_user_*`.

```
"""delete_user_completely(user_id); exception → success=False и exception-лог."""
```

Не перерисовывает карточку — только answer об удалении или провале.

## `get_admin_router.admin_user_keys` (6467–6491)

**Docstring в коде:** нет. Callback `admin_user_keys_*`. В коде `#`: формат `admin_user_keys_{id}` или `admin_user_keys_{id}_{page}`.

```
"""Список ключей пользователя: parts[3]=user_id, parts[4]=page (нет → 0)."""
```

IndexError/ValueError → «Ошибка в данных запроса».

## `get_admin_router.admin_user_referrals` (6494–6539)

**Docstring в коде:** нет. Callback `admin_user_referrals_*`.

```
"""Рефералы пользователя: до 30 строк (@, id, дата, spent) и get_referral_balance_all; хвост «и ещё N»."""
```

Нет inviter → «не найден». Кнопки к карточке и admin_menu.

## `get_admin_router.admin_search_user_keys_handler` (6542–6562)

**Docstring в коде:** нет. Callback `admin_search_user_keys_*`. В коде `#`: user_id в state.

```
"""Запросить название/email ключа; search_user_id в FSM, состояние admin_search_user_keys_state."""
```

## `get_admin_router.admin_search_user_keys_input_handler` (6565–6603)

**Docstring в коде:** нет. Message, `StateFilter("admin_search_user_keys_state")`.

```
"""search_user_keys_by_email(user_id, query); пустой query / нет user_id / пустой результат — отказ."""
```

Успех: `search_results` в state, клавиатура результатов page=0. Состояние не clear.

## `get_admin_router.admin_search_keys_page_handler` (6606–6631)

**Docstring в коде:** нет. Callback `admin_search_keys_page_*`.

```
"""Листать search_results из FSM; пустые результаты → alert «потеряны»."""
```

Только `edit_reply_markup`.

## `get_admin_router.admin_search_all_keys_handler` (6634–6647)

**Docstring в коде:** нет. Callback `admin_search_all_keys`. В коде `#`: user_id не сохраняем.

```
"""Общий поиск ключей: состояние admin_search_all_keys_state, без search_user_id."""
```

## `get_admin_router.admin_search_all_keys_input_handler` (6650–6679)

**Docstring в коде:** нет. Message, `admin_search_all_keys_state`.

```
"""search_all_keys_by_email(query); клавиатура с user_id=None."""
```

Пустой query → «введите email». Нет ключей — остаёмся в поиске.

## `get_admin_router.admin_cancel_search_keys_handler` (6682–6693)

**Docstring в коде:** нет. Callback `admin_cancel_search_keys`.

```
"""state.clear и «Поиск отменён» + create_admin_cancel_keyboard (не админ-меню)."""
```

## `get_admin_router.admin_edit_key` (6696–6728)

**Docstring в коде:** нет. Callback `admin_edit_key_*`.

```
"""Карточка ключа: хост, email, expiry, connection/subscription в <code>; клавиатура действий."""
```

Нет ключа / не-int → answer. edit_text, иначе answer (debug-лог «отмене удаления» — формулировка та же, что у cancel).

## `get_admin_router.admin_key_delete_prompt` (6733–6760)

**Docstring в коде:** нет. Callback regexp `^admin_key_delete_\d+$`.

```
"""Подтверждение удаления ключа (email, хост) + create_admin_delete_key_confirm_keyboard."""
```

Лог входящего callback. edit_text, иначе answer.

## `AdminExtendSingleKey` (6763–6764)

**Docstring в коде:** нет

```
"""FSM сдвига срока одного ключа: ожидание целого числа дней."""
```

`waiting_days`.

## `get_admin_router.admin_key_extend_prompt` (6767–6783)

**Docstring в коде:** нет. Callback `admin_key_extend_*`.

```
"""Сохранить extend_key_id и попросить дни (плюс — продление, минус — уменьшение)."""
```

## `get_admin_router.admin_key_extend_process` (6786–6843)

**Docstring в коде:** нет. Message, `AdminExtendSingleKey.waiting_days`.

```
"""create_or_update_key_on_host(days_to_add) и rw_repo.update_key (uuid + expire_at_ms); 0 дней запрещён."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 6791–6794 | нет extend_key_id | clear, «не удалось определить» |
| 6795–6802 | int / == 0 | повтор ввода, состояние живое |
| 6803–6813 | нет ключа / host / email | clear |
| 6815–6822 | панель | нет client_uuid/expiry → «на сервере»; state не clear |
| 6824–6830 | update_key False | «не удалось обновить»; state не clear |
| 6831–6843 | успех | clear, «продлён на N», карточка |

## `AdminAddAdmin` (6846–6847)

**Docstring в коде:** нет

```
"""FSM добавления админа: ожидание ID или @username."""
```

`waiting_for_input`.

## `get_admin_router.admin_add_admin_entry` (6850–6860)

**Docstring в коде:** нет. Callback `admin_add_admin`.

```
"""Запросить ID/@username нового администратора."""
```

## `get_admin_router.admin_add_admin_process` (6863–6921)

**Docstring в коде:** нет. Message, `AdminAddAdmin.waiting_for_input`.

```
"""Разрешить target_id (цифра / get_chat @ / get_chat без @ / обход users) и дописать в admin_telegram_ids."""
```

По коду: ветка `@` только если `raw.startswith('@')`. Не распознан — состояние живое. `ids.add` + `update_setting`; затем всегда `state.clear` и `show_admin_menu`.

## `AdminRemoveAdmin` (6924–6925)

**Docstring в коде:** нет

```
"""FSM снятия админа: ожидание ID или @username."""
```

`waiting_for_input`.

## `get_admin_router.admin_remove_admin_entry` (6928–6938)

**Docstring в коде:** нет. Callback `admin_remove_admin`.

```
"""Запросить ID/@username снимаемого администратора."""
```

## `get_admin_router.admin_remove_admin_process` (6941–7009)

**Docstring в коде:** нет. Message, `AdminRemoveAdmin.waiting_for_input`.

```
"""Снять id из admin_telegram_ids; нельзя снять последнего; не-админ — info без изменения списка."""
```

Резолв шире add: get_chat пробуется и без ведущего `@`. `len(ids) <= 1` → отказ, state не clear. Иначе discard + update_setting, clear, меню.

## `get_admin_router.admin_key_delete_cancel` (7013–7047)

**Docstring в коде:** нет. Callback `admin_key_delete_cancel_*`.

```
"""Вернуть карточку ключа после отмены удаления; не-int / нет ключа — тихий return."""
```

`callback.answer("Отменено")` в try. edit_text, иначе answer.

## `get_admin_router.admin_key_delete_confirm` (7051–7118)

**Docstring в коде:** нет. Callback `admin_key_delete_confirm_*`.

```
"""Удалить клиента на хосте (если host+email) и delete_key_by_email; обновить список ключей и уведомить user_id."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 7073–7078 | user_id ключа | не int → отказ |
| 7081–7087 | delete_client_on_host | нет host/email → ok_host остаётся True |
| 7088–7092 | delete_key_by_email | ok_db |
| 7093–7116 | ok_db | текст с оговоркой про хост; список ключей; send user_id (сбой глотается) |
| 7117–7118 | не ok_db | «не удалось удалить из БД» |

## `AdminEditKeyEmail` (7120–7121)

**Docstring в коде:** нет

```
"""FSM смены email ключа: ожидание новой строки."""
```

`waiting_for_email`.

## `get_admin_router.admin_key_edit_email_start` (7124–7139)

**Docstring в коде:** нет. Callback `admin_key_edit_email_*`.

```
"""Сохранить edit_key_id и попросить новый email."""
```

## `get_admin_router.admin_key_edit_email_commit` (7142–7156)

**Docstring в коде:** нет. Message, `AdminEditKeyEmail.waiting_for_email`.

```
"""update_key_email(key_id, new_email); пустая строка — повтор; затем state.clear."""
```

Провал → «возможно, уже занят». Карточку не перерисовывает.

## `AdminGiftKey` (7161–7164)

**Docstring в коде:** нет

```
"""FSM подарка ключа: пользователь → хост → дни."""
```

`picking_user`, `picking_host`, `picking_days`.

## `get_admin_router.admin_gift_key_entry` (7167–7178)

**Docstring в коде:** нет. Callback `admin_gift_key`.

```
"""state.clear, picking_user, список пользователей action=gift page=0."""
```

## `get_admin_router.admin_gift_key_for_user` (7182–7199)

**Docstring в коде:** нет. Callback `admin_gift_key_*` (вход с карточки пользователя).

```
"""target_user_id из хвоста, picking_host, список хостов action=gift."""
```

`state.clear` перед update_data.

## `get_admin_router.admin_gift_pick_user_page` (7202–7215)

**Docstring в коде:** нет. Callback `admin_gift_pick_user_page_*` в `picking_user`.

```
"""Страница выбора пользователя для подарка; битый номер → 0."""
```

## `get_admin_router.admin_gift_pick_user` (7218–7234)

**Docstring в коде:** нет. Callback `admin_gift_pick_user_*` в `picking_user`.

```
"""Запомнить target_user_id и показать хосты (без clear)."""
```

## `get_admin_router.admin_gift_back_to_users` (7237–7247)

**Docstring в коде:** нет. Callback `admin_gift_back_to_users` в `picking_host`.

```
"""Вернуться к picking_user, страница 0."""
```

## `get_admin_router.admin_gift_pick_host` (7250–7261)

**Docstring в коде:** нет. Callback `admin_gift_pick_host_*` в `picking_host`.

```
"""Запомнить host_name и попросить целое число дней."""
```

## `get_admin_router.admin_gift_back_to_hosts` (7264–7276)

**Docstring в коде:** нет. Callback `admin_gift_back_to_hosts` в `picking_days`.

```
"""Вернуться к выбору хоста для target_user_id из FSM."""
```

## `get_admin_router.admin_gift_pick_days` (7278–7344)

**Docstring в коде:** нет. Message, `AdminGiftKey.picking_days`.

```
"""Создать ключ на хосте (generate_key_email_for_user), record_key_from_payload и уведомить пользователя."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 7284–7291 | days | не int / ≤0 → повтор |
| 7294–7297 | email | сбой generate → `{user_id}-{time}@bot.local` |
| 7300–7310 | create_or_update_key_on_host | нет uuid/expiry → отказ, clear, меню |
| 7316–7340 | record_key_from_payload | key_id: ответ админу + HTML-уведомление с подпиской; нет id → «не сохранить в БД» |
| 7343–7344 | всегда | clear + show_admin_menu |

## `AdminMainRefill` (7349–7351)

**Docstring в коде:** нет

```
"""FSM начисления баланса: пара (не используется ниже) и сумма."""
```

`waiting_for_pair`, `waiting_for_amount`. Хендлеры ставят только `waiting_for_amount`.

## `get_admin_router.admin_add_balance_entry` (7354–7363)

**Docstring в коде:** нет. Callback `admin_add_balance`.

```
"""Список пользователей для начисления, action=add_balance page=0."""
```

## `get_admin_router.admin_add_balance_user` (7366–7381)

**Docstring в коде:** нет. Callback startswith `admin_add_balance_`.

```
"""target_user_id из хвоста, waiting_for_amount, запрос суммы в рублях."""
```

По коду: тот же startswith ловит и `admin_add_balance_pick_user_*` (этот хендлер зарегистрирован раньше page/pick).

## `get_admin_router.admin_add_balance_pick_user_page` (7385–7398)

**Docstring в коде:** нет. Callback `admin_add_balance_pick_user_page_*`.

```
"""Страница выбора пользователя для начисления."""
```

## `get_admin_router.admin_add_balance_pick_user` (7402–7417)

**Docstring в коде:** нет. Callback `admin_add_balance_pick_user_*`.

```
"""То же, что admin_add_balance_user: сумма в waiting_for_amount."""
```

## `get_admin_router.handle_main_amount` (7420–7446)

**Docstring в коде:** нет. Message, `AdminMainRefill.waiting_for_amount`.

```
"""add_to_balance(user_id, amount); запятая→точка; amount≤0 запрещён; уведомить пользователя."""
```

Всегда `state.clear` + меню (даже при ошибке числа — нет: return до clear; после попытки БД — да).

| Строки | Блок | Зачем |
|--------|------|--------|
| 7425–7432 | parse / ≤0 | повтор, state живой |
| 7433–7444 | add_to_balance | ok → админ+user; иначе «не найден или БД» |
| 7445–7446 | finally-по-коду | clear + меню |

## `get_admin_router.admin_key_back` (7450–7485)

**Docstring в коде:** нет. Callback `admin_key_back_*`.

```
"""Назад из карточки ключа: если в FSM hostkeys_host — список хоста, иначе ключи владельца."""
```

## `get_admin_router.admin_noop` (7489–7490)

**Docstring в коде:** нет. Callback `noop`.

```
"""Пустой ACK callback (без проверки is_admin)."""
```

## `get_admin_router.admin_cancel_handler` (7493–7496)

**Docstring в коде:** нет. Callback `admin_cancel`.

```
"""«Отменено», state.clear, админ-меню (без проверки is_admin)."""
```

## `AdminMainDeduct` (7499–7500)

**Docstring в коде:** нет

```
"""FSM списания баланса: ожидание суммы."""
```

`waiting_for_amount`.

## `get_admin_router.admin_deduct_balance_entry` (7504–7513)

**Docstring в коде:** нет. Callback `admin_deduct_balance`.

```
"""Список пользователей для списания, action=deduct_balance."""
```

## `get_admin_router.admin_deduct_balance_user` (7517–7532)

**Docstring в коде:** нет. Callback startswith `admin_deduct_balance_`.

```
"""target_user_id, waiting_for_amount, запрос суммы списания."""
```

По коду: тот же startswith перекрывает последующие pick_user/page (как у начисления).

## `get_admin_router.admin_deduct_balance_pick_user_page` (7536–7549)

**Docstring в коде:** нет. Callback `admin_deduct_balance_pick_user_page_*`.

```
"""Страница выбора пользователя для списания."""
```

## `get_admin_router.admin_deduct_balance_pick_user` (7553–7568)

**Docstring в коде:** нет. Callback `admin_deduct_balance_pick_user_*`.

```
"""То же, что admin_deduct_balance_user: запрос суммы списания."""
```

## `get_admin_router.handle_deduct_amount` (7571–7601)

**Docstring в коде:** нет. Message, `AdminMainDeduct.waiting_for_amount`.

```
"""deduct_from_balance; провал → «не найден или недостаточно средств»; user получает support-клавиатуру."""
```

Парсинг как у начисления. Затем clear + меню.

## `AdminHostKeys` (7604–7605)

**Docstring в коде:** нет

```
"""FSM просмотра ключей хоста: выбор хоста."""
```

`picking_host`.

## `get_admin_router.admin_host_keys_entry` (7608–7619)

**Docstring в коде:** нет. Callback `admin_host_keys`.

```
"""state.clear, picking_host, список хостов action=hostkeys."""
```

## `get_admin_router.admin_host_keys_pick_host` (7622–7637)

**Docstring в коде:** нет. Callback `admin_hostkeys_pick_host_*` в `picking_host`.

```
"""hostkeys_host в FSM и список get_keys_for_host."""
```

update_data в try (сбой игнор).

## `get_admin_router.admin_hostkeys_page` (7640–7663)

**Docstring в коде:** нет. Callback `admin_hostkeys_page_*` в `picking_host`.

```
"""Страница ключей текущего hostkeys_host; нет хоста в FSM → снова выбор хоста."""
```

## `get_admin_router.admin_hostkeys_back_to_hosts` (7666–7680)

**Docstring в коде:** нет. Callback `admin_hostkeys_back_to_hosts` в `picking_host`.

```
"""Сбросить hostkeys_host и показать список хостов."""
```

## `get_admin_router.admin_hostkeys_back_to_users` (7683–7688)

**Docstring в коде:** нет. Callback `admin_hostkeys_back_to_users`.

```
"""Админ-меню (edit). Имя — «к пользователям», тело зовёт show_admin_menu."""
```

## `AdminQuickDeleteKey` (7691–7692)

**Docstring в коде:** нет

```
"""FSM быстрого удаления: ожидание key_id или email."""
```

`waiting_for_identifier`.

## `get_admin_router.admin_delete_key_entry` (7695–7704)

**Docstring в коде:** нет. Callback `admin_delete_key`.

```
"""Попросить key_id или email ключа для удаления."""
```

## `get_admin_router.admin_delete_key_process` (7707–7729)

**Docstring в коде:** нет. Message, `AdminQuickDeleteKey.waiting_for_identifier`.

```
"""Найти ключ по int id, иначе по email; показать то же подтверждение, что admin_key_delete_prompt."""
```

Не найден — состояние живое. Найден — clear и confirm-клавиатура.

## `AdminExtendKey` (7732–7733)

**Docstring в коде:** нет

```
"""FSM быстрого продления: одна строка «key_id дни»."""
```

`waiting_for_pair`.

## `get_admin_router.admin_extend_key_entry` (7736–7745)

**Docstring в коде:** нет. Callback `admin_extend_key`.

```
"""Попросить пару `key_id дни`."""
```

## `get_admin_router.admin_extend_key_process` (7748–7796)

**Docstring в коде:** нет. Message, `AdminExtendKey.waiting_for_pair`.

```
"""Продлить ключ на хосте (days>0) и update_key; уведомить владельца."""
```

Не 2 токена / не числа / days≤0 / нет ключа / нет host|email — return без clear. Нет ответа панели / update_key False — без clear. Успех: clear, текст админу, send user_id (сбой глотается). Меню не открывает.

## `get_admin_router.start_broadcast_handler` (7799–7810)

**Docstring в коде:** нет. Callback `start_broadcast`.

```
"""Запросить текст/медиа рассылки; Broadcast.waiting_for_message."""
```

## `get_admin_router.broadcast_message_received_handler` (7813–7864)

**Docstring в коде:** нет. Message, `Broadcast.waiting_for_message`.

```
"""Сериализовать сообщение в JSON FSM; для текста — авто-parse_mode или выбор формата; иначе сразу кнопки."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 7834–7835 | model_dump + default | message_to_send |
| 7836–7846 | text + auto_pm | HTML/MD2, waiting_for_button_option |
| 7847–7857 | text без разметки | waiting_for_parse_mode |
| 7858–7864 | не text | parse_mode=None, кнопки |

### `get_admin_router.broadcast_message_received_handler._msg_json_default` (7817–7822)

**Docstring в коде:** нет. В коде `#`: aiogram Default sentinel и неизвестные типы.

```
"""JSON-default: Enum.value, date/datetime.isoformat, иначе None."""
```

### `get_admin_router.broadcast_message_received_handler._detect_parse_mode` (7826–7832)

**Docstring в коде:** есть

```
"""Auto-detect parse mode: HTML tags → HTML, Markdown links/bold/etc → MarkdownV2."""
```

HTML: теги a/b/i/s/u/code/pre/tg-spoiler. Иначе MD-ссылка или `**`/`__`/`~~`/`` ` ``/`||`. Нет совпадений → None.

## `get_admin_router.broadcast_parse_mode_handler` (7870–7879)

**Docstring в коде:** нет. Callback `broadcast_pm_none|html|md2` в `waiting_for_parse_mode`.

```
"""Записать parse_mode (None/HTML/MarkdownV2) и спросить про кнопку."""
```

## `get_admin_router.add_button_choose_type` (7883–7889)

**Docstring в коде:** нет. Callback `broadcast_add_button`.

```
"""Выбор типа кнопки: URL или действие бота."""
```

`waiting_for_button_type`.

## `get_admin_router.add_button_prompt_handler` (7892–7898)

**Docstring в коде:** нет. Callback `broadcast_btn_type_url`.

```
"""Попросить текст URL-кнопки."""
```

`waiting_for_button_text`.

## `get_admin_router.add_functional_button_start` (7901–7907)

**Docstring в коде:** нет. Callback `broadcast_btn_type_action`.

```
"""Показать BROADCAST_ACTIONS клавиатуру."""
```

`waiting_for_action_select`.

## `get_admin_router.functional_button_selected` (7910–7915)

**Docstring в коде:** нет. Callback `broadcast_action:`.

```
"""button_text из BROADCAST_ACTIONS_MAP, button_callback=ключ, button_url=None; превью."""
```

## `get_admin_router.button_text_received_handler` (7919–7925)

**Docstring в коде:** нет. Message, `waiting_for_button_text`.

```
"""Сохранить button_text и попросить URL."""
```

## `get_admin_router.button_url_received_handler` (7928–7936)

**Docstring в коде:** нет. Message, `waiting_for_button_url`.

```
"""Принять http(s) URL в button_url и показать превью; иначе повтор."""
```

## `get_admin_router.skip_button_handler` (7939–7942)

**Docstring в коде:** нет. Callback `broadcast_skip_button`.

```
"""Обнулить button_text/url и показать превью."""
```

## `get_admin_router._escape_md2` (7944–7967)

**Docstring в коде:** есть. В коде `#`: Match valid MarkdownV2 entities to keep as-is.

```
"""Escape MarkdownV2 special chars in plain-text parts, leaving inline entities intact."""
```

Сущности: `[text](url)`, `**bold**`, `__italic__`, `~~strike~~`, `` `code` ``, `||spoiler||`. Между ними — `_esc`.

### `get_admin_router._escape_md2._esc` (7958–7959)

**Docstring в коде:** нет

```
"""Экранировать MarkdownV2 спецсимволы `_*[]()~`>#+=|{}.!-\` обратным слешем."""
```

## `get_admin_router._send_broadcast_to` (7969–8004)

**Docstring в коде:** есть. В коде `#`: parse_mode и entities взаимоисключают.

```
"""Send broadcast, using specific send methods for media so reply_markup is applied correctly."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 7973–7976 | parse_mode | caption+parse_mode vs caption_entities |
| 7977–7990 | photo/video/animation/document/audio | ckw; voice/sticker — без caption |
| 7991–7997 | text | MD2 → `_escape_md2`; иначе entities; preview off |
| 7998–8004 | иначе | copy_message |

## `get_admin_router.show_broadcast_preview` (8006–8036)

**Docstring в коде:** нет

```
"""Собрать клавиатуру (url или callback + open_main_menu), спросить «Отправляем?» и разослать превью себе."""
```

`waiting_for_confirmation`. Текст кнопки меню — `btn_back_to_menu_text` или «⬅️ Главное меню».

## `get_admin_router.confirm_broadcast_handler` (8039–8106)

**Docstring в коде:** нет. Callback `confirm_broadcast`. В коде `#`: email-only без Telegram.

```
"""Разослать сохранённое сообщение всем get_all_users, пропуская бан / unreachable / email-only; sleep 0.1."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 8064 | state.clear | до цикла |
| 8077–8086 | skip | banned / unreachable / is_email_only_user |
| 8087–8096 | send | успех +0.1с; except: failed++; handle_send_exception → ещё unreachable |
| 8098–8106 | итог | счётчики + админ-меню |

## `get_admin_router.cancel_broadcast_handler` (8109–8112)

**Docstring в коде:** нет. Callback `cancel_broadcast` при любом Broadcast-состоянии.

```
"""Отменить рассылку, clear, админ-меню."""
```

## `get_admin_router.approve_withdraw_handler` (8116–8134)

**Docstring в коде:** нет. Command `approve_withdraw`.

```
"""Одобрить вывод: user_id = int(text.rsplit по `_`); referral_balance < 100 — отказ; оба реф-баланса в 0."""
```

Уведомляет пользователя. Любой Exception → «Ошибка: e».

## `get_admin_router.decline_withdraw_handler` (8137–8148)

**Docstring в коде:** нет. Command `decline_withdraw`.

```
"""Отклонить вывод (тот же разбор user_id); балансы не трогает, шлёт отказ пользователю."""
```

## `get_admin_router.admin_monitor_menu` (8152–8183)

**Docstring в коде:** нет. Callback `admin_monitor`.

```
"""Меню мониторинга: локальная панель, rmh:{host}, rmt:{sha1(target)}, назад в admin_menu."""
```

Кнопки хостов/целей по 2 в ряд. sha1 utf-8 ignore.

## `get_admin_router.admin_monitor_local` (8186–8354)

**Docstring в коде:** нет. Callback `admin_monitor_local`.

```
"""Метрики «панели»: при наличии хостов — remote первого, иначе local; снимок в insert_resource_metric."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 8194–8208 | источник | hosts[0] remote; except/пусто → local |
| 8210–8242 | insert | scope host/local, поля cpu/mem/disk/load/net + raw_json; сбой игнор |
| 8244–8250 | not ok | ошибка |
| 8251–8345 | ok | нормализация remote vs local; emoji 70/90; диски до 3 |
| 8348–8354 | kb | обновить / detailed / назад |

Локальные `get_status_emoji` / `format_bytes` / `format_uptime` в инвентарь не входят.

## `get_admin_router.admin_monitor_host` (8357–8462)

**Docstring в коде:** нет. Callback `rmh:`.

```
"""Remote-метрики хоста (`get_remote_metrics_for_host`); CPU ≈ min(load1/ncpu*100, 100)."""
```

Пишет metric scope=`host` (mem/disk/load1). Ошибка подключения — отдельный текст. Диски до 3. Обновить = тот же callback.data.

## `get_admin_router.admin_monitor_target` (8465–8592)

**Docstring в коде:** нет. Callback `rmt:`.

```
"""То же, что host, но цель ищется перебором sha1(target_name)==digest; метрики get_remote_metrics_for_target."""
```

Нет совпадения → alert «Цель не найдена». scope=`target`.

## `get_admin_router.admin_monitor_detailed` (8595–8723)

**Docstring в коде:** нет. Callback `admin_monitor_detailed`.

```
"""Локальные get_local_metrics: CPU/RAM/swap/сеть/температуры/топ-5 процессов/все диски."""
```

Только local, без записи metric. Температура: 🔴 если ≥ critical, 🟡 ≥ high. Диски: 95/80.

## `get_admin_router.admin_captcha_settings_handler` (8730–8764)

**Docstring в коде:** есть

```
"""Показать страницу настроек капчи."""
```

Читает captcha_enabled/type/max_attempts/timeout_minutes. Кнопки toggle/type/attempts/timeout/message/назад в admin_settings_menu.

## `get_admin_router.admin_captcha_toggle_handler` (8767–8778)

**Docstring в коде:** есть

```
"""Включить/отключить капчу."""
```

Инверсия `captcha_enabled` true↔false через `rw_repo.update_setting`, затем повтор `admin_captcha_settings_handler`.

## `get_admin_router.admin_captcha_type_handler` (8781–8803)

**Docstring в коде:** есть

```
"""Выбрать тип капчи."""
```

math / button; текущий помечен ✅.

## `get_admin_router.admin_captcha_type_set_handler` (8806–8817)

**Docstring в коде:** есть

```
"""Установить тип капчи."""
```

Хвост после `:`, update_setting, возврат на страницу настроек.

## `get_admin_router.admin_captcha_attempts_handler` (8820–8831)

**Docstring в коде:** есть

```
"""Установить максимальное количество попыток."""
```

`AdminSettings.waiting_for_captcha_attempts`. Текущее из settings или «3».

## `get_admin_router.admin_captcha_attempts_input_handler` (8834–8850)

**Docstring в коде:** есть

```
"""Обработать ввод количества попыток."""
```

Целое 1…10 → `captcha_max_attempts`, clear. Иначе повтор без clear.

## `get_admin_router.admin_captcha_timeout_handler` (8853–8864)

**Docstring в коде:** есть

```
"""Установить timeout капчи."""
```

`waiting_for_captcha_timeout`. Текущее или «15».

## `get_admin_router.admin_captcha_timeout_input_handler` (8867–8883)

**Docstring в коде:** есть

```
"""Обработать ввод timeout."""
```

Целое 5…120 → `captcha_timeout_minutes`.

## `get_admin_router.admin_captcha_message_handler` (8886–8897)

**Docstring в коде:** есть

```
"""Установить кастомное сообщение к капче."""
```

Дефолт показа: «👤 Привет! Ты выглядишь как бот. Пройди простую капчу...». `waiting_for_captcha_message`.

## `get_admin_router.admin_captcha_message_input_handler` (8900–8913)

**Docstring в коде:** есть

```
"""Обработать ввод сообщения."""
```

Длина > 200 — отказ без clear. Иначе `captcha_message` и clear.

## `AdminAutoRenew` (8919–8920)

**Docstring в коде:** нет

```
"""FSM окна автопродления: ожидание часов."""
```

`waiting_for_hours`.

## `get_admin_router.show_admin_auto_renew_menu` (8922–8944)

**Docstring в коде:** нет

```
"""Экран глобального автопродления: auto_renew_globally_enabled и auto_renew_hours_before (fallback 24)."""
```

`edit_message=True` → edit_text, иначе answer. Текст поясняет списание с баланса только для ключей с автопродлением на карточке.

## `get_admin_router.admin_auto_renew_entry` (8947–8954)

**Docstring в коде:** нет. Callback `admin_auto_renew`.

```
"""Показать меню автопродления. По коду: set_state(waiting_for_hours) сразу сбрасывается state.clear()."""
```

## `get_admin_router.admin_auto_renew_toggle` (8957–8966)

**Docstring в коде:** нет. Callback `admin_auto_renew_toggle`.

```
"""Инвертировать auto_renew_globally_enabled и перерисовать меню."""
```

## `get_admin_router.admin_auto_renew_set_hours` (8969–8977)

**Docstring в коде:** нет. Callback `admin_auto_renew_set_hours`.

```
"""Попросить число часов до конца срока; waiting_for_hours."""
```

Ответ новым сообщением, не edit.

## `get_admin_router.admin_auto_renew_hours_input` (8980–8994)

**Docstring в коде:** нет. Message, `AdminAutoRenew.waiting_for_hours`.

```
"""Записать auto_renew_hours_before (1…168) и показать меню новым сообщением."""
```

Не-int / вне диапазона — повтор, state живой. После `return admin_router` файл заканчивается.

Документировано записей: **129**.
