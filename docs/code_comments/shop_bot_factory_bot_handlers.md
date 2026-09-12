# Комментарии: `src/shop_bot/factory_bot/handlers.py`

Кабинет владельца текущего клона (просмотр/удаление). Модульного docstring нет.

`DELETE_CONFIRM_TEXT`: клон останавливается, активность пользователей удаляется, одобренные/выплаченные заявки на вывод сохраняются.

## `_parse_bot_id_from_callback` (19–28)

**Docstring в коде:** нет

```
"""Вырезать int после prefix из callback.data; иначе None. Не-число или id ≤ 0 → None."""
```

`data` None → `""`. Prefix не совпал → None.

## `get_owner_cabinet_router` (31–105)

**Docstring в коде:** есть

```
Кабинет владельца текущего клона: просмотр и удаление ЭТОГО бота.
```

Собирает Router с тремя callback. Создания клонов здесь нет (только root-бот).

### `get_owner_cabinet_router.cabinet` (36–57)

**Docstring в коде:** нет. Callback `factory_cabinet`.

```
"""Показать статистику этого клона владельцу: пользователи, сообщения, прямые боты, баланс."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 37–40 | resolve_factory_bot_id == 0 | alert «только во клонах» |
| 41–45 | from_user ≠ owner_telegram_id | alert «только владельцу» |
| 47–57 | get_factory_cabinet | Markdown-текст + `cabinet_menu()` |

### `get_owner_cabinet_router.delete_self_ask` (60–75)

**Docstring в коде:** нет. Callback `factory_del_self`.

```
"""Спросить подтверждение удаления текущего клона; только владелец и только если bot_id > 0."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 61–64 | bot_id ≤ 0 | alert «только в клоне» |
| 65–69 | нет info или не владелец | alert «только своего бота» |
| 70–75 | иначе | текст + DELETE_CONFIRM_TEXT + `delete_bot_confirm(bot_id)` |

### `get_owner_cabinet_router.delete_bot_confirm` (78–103)

**Docstring в коде:** нет. Callback `factory_del_yes:`.

```
"""Остановить клон через ManagedBotsService и delete_managed_bot с проверкой owner_telegram_id."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 79–82 | не распарсился bot_id | alert «Некорректный бот» |
| 83–87 | нет info / не владелец | alert «только свои боты» |
| 89–94 | get_service() | `stop_bot`; ошибка — лог, удаление всё равно идёт |
| 96–103 | delete_managed_bot | не удалился → alert; успех → «Бот удалён»; сбой answer глотается |
