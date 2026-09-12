# Комментарии: `src/shop_bot/support_bot/handlers.py`

Модульного docstring нет. Роутер support-бота: FSM пользователя и админа, форум-топики, бан, заметки. Данные через `remnawave_repository`; медиа — `ticket_media.save_ticket_media`.

## `SupportDialog` (32–35)

**Docstring в коде:** нет

```
"""FSM пользователя: тема, текст обращения, ответ в открытый тикет."""
```

Состояния: `waiting_for_subject`, `waiting_for_message`, `waiting_for_reply`.

## `AdminDialog` (38–39)

**Docstring в коде:** нет

```
"""FSM админа: одно сообщение — внутренняя заметка (sender=note)."""
```

`waiting_for_note`.

## `get_support_router` (42–1143)

**Docstring в коде:** нет

```
"""Собрать Router support-бота: хелперы и все хендлеры ниже, вернуть router."""
```

Вложенные функции — отдельные секции.

### `get_support_router._user_main_reply_kb` (45–52)

**Docstring в коде:** нет

```
"""Reply-клавиатура: «Новое обращение» / «Мои обращения»."""
```

### `get_support_router._is_user_banned` (54–61)

**Docstring в коде:** нет

```
"""True, если get_user().is_banned; пустой user_id / ошибка → False."""
```

### `get_support_router._get_latest_open_ticket` (63–71)

**Docstring в коде:** нет

```
"""Открытый тикет пользователя с максимальным ticket_id или None."""
```

### `get_support_router._admin_actions_kb` (73–114)

**Docstring в коде:** нет

```
"""Инлайн-панель тикета: закрыть/переоткрыть, удалить, звезда, пользователь, заметка, список заметок, бан/разбан."""
```

Закрыть если `status=='open'`, иначе переоткрыть. Бан/разбан только при известном user_id.

### `get_support_router._is_admin` (116–124)

**Docstring в коде:** нет

```
"""True, если is_admin(user_id) или в чате ADMINISTRATOR/CREATOR (ошибка get_chat_member игнор)."""
```

### `get_support_router.start_handler` (127–162)

**Docstring в коде:** нет

```
"""/start в личке: deep-link `new` → тема или отказ при открытом тикете; иначе бан-текст или support_text + меню."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 132–141 | arg == "new" | **до** проверки бана: есть open → отказ; иначе FSM subject |
| 142–150 | banned | текст + optional contact markup, state.clear |
| 152–162 | обычный /start | `get_setting("support_text")` и ReplyKeyboard |

### `get_support_router.support_new_ticket_handler` (165–187)

**Docstring в коде:** нет

```
"""Callback `support_new_ticket`: бан → alert; open тикет → отказ; иначе FSM subject."""
```

Сначала `callback.answer()`, при бане ещё раз `answer(..., show_alert=True)`.

### `get_support_router.support_subject_received` (190–203)

**Docstring в коде:** нет

```
"""Личка в waiting_for_subject: бан → выход; иначе сохранить subject (может быть пустой) и спросить текст."""
```

### `get_support_router._save_ticket_media` (205–209)

**Docstring в коде:** нет. В коде `#`: лимит 10 МБ в `save_ticket_media`; отказ → None, текст всё равно пишут хендлеры.

```
"""Прокси на ticket_media.save_ticket_media(bot, message, ticket_id)."""
```

### `get_support_router.support_message_received` (212–319)

**Docstring в коде:** нет

```
"""Личка в waiting_for_message: создать/найти open тикет, сохранить текст+медиа, топик, зеркало, уведомить get_admin_ids()."""
```

Пустая тема → «Обращение без темы». `get_or_create_open_ticket`. Нет ticket_id → ошибка, clear. Медиа затем `add_support_message(sender=user)`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 241–268 | нет thread и задан support_forum_chat_id | create_forum_topic, header + admin kb |
| 269–290 | есть forum+thread | «Новое обращение» или «Новое сообщение» + copy_message (и после только что созданного топика тоже) |
| 292–301 | ответ пользователю | создан / дописан + reply kb |
| 303–319 | get_admin_ids | ЛС каждому админу; сбой одного — continue |

### `get_support_router.support_my_tickets_handler` (322–336)

**Docstring в коде:** нет

```
"""Callback `support_my_tickets`: список тикетов с ⭐/статусом/темой[:20], кнопки `support_view_{id}`."""
```

### `get_support_router.support_view_ticket_handler` (339–369)

**Docstring в коде:** нет

```
"""Callback `support_view_*`: карточка своего тикета; sender=note скрыт; open → Ответить/Закрыть."""
```

Чужой / нет тикета → «доступ запрещён».

### `get_support_router.support_reply_prompt_handler` (372–394)

**Docstring в коде:** нет

```
"""Callback `support_reply_*`: бан / не свой / не open → отказ; иначе FSM waiting_for_reply."""
```

### `get_support_router.support_reply_received` (397–494)

**Docstring в коде:** нет

```
"""Личка в waiting_for_reply: user-сообщение+медиа, при отсутствии топика создать, переименовать тему, copy в форум, ЛС admin_telegram_id."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 398–413 | бан / невалидный тикет | отказ, clear |
| 414–422 | БД + «Сообщение отправлено» | |
| 426–455 | нет thread | create_forum_topic + header «Тред создан автоматически» |
| 456–478 | есть thread | edit_forum_topic, префикс, copy |
| 481–494 | admin_telegram_id | одно ЛС (не get_admin_ids) |

### `get_support_router.forum_thread_message_handler` (497–564)

**Docstring в коде:** нет

```
"""Сообщение в топике: заметка если AdminDialog; иначе ответ админа → БД + copy пользователю."""
```

Нет thread / нет тикета по thread → return. Свои сообщения бота (`get_me`) игнор. Не админ по настройке и не админ чата → return. Пустой content без медиа — в БД не пишет, header пользователю всё равно шлёт. copy_message упал → fallback текстом.

### `get_support_router.support_close_ticket_handler` (567–610)

**Docstring в коде:** нет

```
"""Callback `support_close_*`: пользователь закрывает свой тикет, пишет в тему, close_forum_topic, меню."""
```

Уже closed / чужой — отказ. `set_ticket_status(..., 'closed')`.

### `get_support_router.admin_close_ticket` (613–649)

**Docstring в коде:** нет

```
"""Callback `admin_close_*`: админ закрывает, close topic, kb, ЛС пользователю."""
```

Не админ → тихий return. «message is not modified» → answer без алерта.

### `get_support_router.admin_reopen_ticket` (652–688)

**Docstring в коде:** нет

```
"""Callback `admin_reopen_*`: status=open, reopen_forum_topic, kb, ЛС «переоткрыт»."""
```

По коду: только `set_ticket_status(..., 'open')` — тем самым обновляется `updated_at` (SQL автозакрытия сразу снова не возьмёт). Сам хендлер idle-правил не знает.

### `get_support_router.admin_delete_ticket` (691–743)

**Docstring в коде:** нет

```
"""Callback `admin_delete_*`: delete_forum_topic (fallback close), затем delete_ticket."""
```

Нет тикета → «уже удалён». edit_text «Удаляю…»; итог через `callback.answer`.

### `get_support_router.admin_toggle_star` (746–815)

**Docstring в коде:** нет

```
"""Callback `admin_star_*`: префикс «⭐ » у subject вкл/выкл, переименовать топик, pin при включении / unpin_all при снятии."""
```

`is_starred = subject.startswith("⭐ ")`. update_ticket_subject. Pin — сообщение «Важность включена»; снятие — `unpin_all_forum_topic_messages`.

### `get_support_router.admin_show_user` (818–843)

**Docstring в коде:** нет

```
"""Callback `admin_user_*`: ID, @username если get_chat дал, ссылка tg://user?id=."""
```

parse_mode Markdown.

### `get_support_router._support_contact_markup` (845–867)

**Docstring в коде:** нет

```
"""Кнопка «Написать в поддержку» из support_bot_username или support_user; пусто → None."""
```

`@` → `tg://resolve`; `tg://` как есть; http(s) → последний path segment как domain; иначе как domain.

### `get_support_router._notify_user_about_ban` (869–877)

**Docstring в коде:** нет

```
"""ЛС user_id с текстом бана и optional contact markup; ошибки глотать."""
```

### `get_support_router.admin_ban_user` (880–908)

**Docstring в коде:** нет

```
"""Callback `admin_ban_user_*`: ban_user, ЛС о блоке, обновить admin kb."""
```

### `get_support_router.admin_unban_user` (911–942)

**Docstring в коде:** нет

```
"""Callback `admin_unban_user_*`: unban_user, ЛС «разблокирован», обновить kb."""
```

### `get_support_router.admin_note_prompt` (945–959)

**Docstring в коде:** нет

```
"""Callback startswith `admin_note_`: FSM waiting_for_note, попросить одно внутреннее сообщение."""
```

По коду: `admin_notes_{id}` тоже `startswith("admin_note_")` и зарегистрирован **позже**. `split("_")[-1]` у `admin_notes_123` = `123`, поэтому список заметок, скорее всего, открывает промпт заметки, а не `admin_list_notes`.

### `get_support_router.admin_list_notes` (962–984)

**Docstring в коде:** нет

```
"""Callback startswith `admin_notes_`: все sender=note тикета текстом в чат."""
```

См. коллизию префикса выше.

### `get_support_router.admin_note_receive` (987–1005)

**Docstring в коде:** нет

```
"""Сообщение в топике в waiting_for_note: add_support_message(sender=note) с автором, clear."""
```

Нет `note_ticket_id` в FSM → ошибка. Пользователю не шлёт. Параллельный путь — ветка в `forum_thread_message_handler` (тот же state).

### `get_support_router.start_text_button` (1008–1016)

**Docstring в коде:** нет

```
"""Текст «▶️ Начать» в личке: open тикет → отказ; иначе FSM subject. Бан не проверяет."""
```

### `get_support_router.new_ticket_text_button` (1019–1027)

**Docstring в коде:** нет

```
"""Текст «✍️ Новое обращение»: то же, что start_text_button. Бан не проверяет."""
```

### `get_support_router.my_tickets_text_button` (1030–1041)

**Docstring в коде:** нет

```
"""Текст «📨 Мои обращения»: список без ⭐-префикса в кнопке (в отличие от support_my_tickets_handler)."""
```

### `get_support_router.relay_user_message_to_forum` (1044–1141)

**Docstring в коде:** нет. В коде `#`: после создания тикета FSM сброшен; фото/PDF раньше не писались в media.

```
"""Любое private-сообщение без FSM: дописать/создать open тикет, медиа, топик, copy в форум."""
```

Есть state → return (не перехватывать FSM). Бан → текст и clear. `get_or_create_open_ticket(user_id, None)`. Нет ticket_id → тихий return. Создаёт топик, если нет; переименовывает; copy. Ответ: создано / добавлено.
