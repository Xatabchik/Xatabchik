# Комментарии: `src/shop_bot/support_bot/idle_close.py`

Модульный docstring в коде:

```
Автозакрытие открытых тикетов, если после ответа админа пользователь молчит N дней.
```

Выбор *кого* закрывать живёт не здесь, а в `database.find_open_tickets_idle_after_admin` / `database.auto_close_idle_admin_tickets`. Этот файл: прочитать N, вызвать SQL, затем (фоном) написать в тему и пользователю.

Константы: `_IDLE_CLOSE_GAP_SEC = 0.12` (пауза между тикетами), `_IDLE_CLOSE_CALL_TIMEOUT_SEC = 3.0` (таймаут одного Telegram-вызова). `_idle_close_followup_lock` сериализует follow-up.

Планировщик зовёт `maybe_auto_close_idle_tickets()` каждый цикл (`scheduler._maybe_auto_close_idle_tickets`).

## `_ru_days_word` (18–27)

**Docstring в коде:** нет

```
"""Русская форма «N день/дня/дней» для уведомлений; мусор → 0 дней."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 19–22 | abs(int(n)) | TypeError/ValueError → 0 |
| 23–26 | остатки 10/100 | 1 день; 2–4 дня (кроме 12–14); иначе дней |

## `_forum_wait` (30–32)

**Docstring в коде:** нет

```
"""Выполнить coro на loop из другого потока и ждать result(timeout)."""
```

`asyncio.run_coroutine_threadsafe` + `fut.result`. Исключения Telegram пробрасываются вызывающему.

## `run_idle_close_followup` (35–120)

**Docstring в коде:** есть

```
Темы форума и короткое уведомление пользователю. Не из HTTP-потока.
```

Пустой `tickets` → сразу return. Берёт `_support_bot_controller` из `webhook_server.app`. Нет bot/loop или loop не running — warning и выход (SQL уже закрыл; форум не трогаем).

Под lock: для каждой строки — сообщение в тему, `close_forum_topic`, ЛС пользователю. Ошибки по одному тикету не рвут пачку. Между тикетами `time.sleep(0.12)`, кроме последнего.

| Строки | Блок | Зачем |
|--------|------|--------|
| 37–38 | нет tickets | return |
| 40–52 | нет support-бота | warning, return |
| 55–120 | lock + цикл | сериализация с другими follow-up |
| 62–96 | forum_chat_id и thread_id | текст «закрыт автоматически… нет ответа N», затем close topic |
| 97–116 | user_id | ЛС: закрыт, можно создать новое |
| 117–118 | прочий Exception | exception-лог по ticket_id |
| 119–120 | gap | не после последнего |

Не решает, закрывать ли тикет: работает только с уже закрытыми строками из SQL.

## `maybe_auto_close_idle_tickets` (123–151)

**Docstring в коде:** есть

```
Закрывает пачку простаивающих тикетов. Telegram — в фоне, SQL сразу.

SQL не ждёт Telegram: следующий цикл планировщика может закрыть ещё пачку,
пока фоновые уведомления догоняют. Вызовы Telegram сериализует
``_idle_close_followup_lock``. ``sync_followup=True`` только для тестов.
```

`days = database.get_ticket_auto_close_days()`. По коду: `if days <= 0: return 0` — автозакрытие выключено (0 / нецелое / мусор в настройке, см. `parse_ticket_auto_close_days`).

Дальше только `database.auto_close_idle_admin_tickets(days, now=now)`. Этот модуль **не** дублирует SQL-условия. Инварианты закрытия — в `database.py` (цитата docstring и WHERE):

- открытый тикет, последнее сообщение `sender = 'admin'` старше `days` суток;
- `updated_at` тоже старше порога: переоткрытие без нового ответа админа обновляет `updated_at` и **сразу снова не закрывает**;
- ответ пользователя (или `sender=note`) делает last ≠ admin — не закрываем;
- UPDATE ещё раз проверяет last=admin, даты и `updated_at`, иначе ответ в окне между SELECT и UPDATE закрыл бы живой тикет.

`count == 0` → 0. Иначе info-лог и follow-up: синхронно при `sync_followup`, иначе daemon-поток `shopbot-idle-ticket-close`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 130–132 | days <= 0 | ничего не трогать |
| 134–138 | SQL | закрытие в БД; пусто → 0 |
| 141–143 | sync_followup | тесты: ждать Telegram |
| 145–150 | Thread daemon | продовый путь |

## `_run_followup_safe` (154–158)

**Docstring в коде:** нет

```
"""Обёртка потока: run_idle_close_followup, любой Exception — exception-лог."""
```
