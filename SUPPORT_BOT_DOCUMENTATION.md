# Support-бот и тикеты

Три входа в одну модель тикетов (`support_tickets` / `support_messages`):

1. Отдельный Telegram support-бот (`support_bot/`).
2. Раздел «Помощь» в основном боте (`bot/handlers.py`, FSM `SupportDialog`).
3. Mini App (`/api/support/*`) и админ-панель (`/support*`).

Внешние режимы из README (ссылка на другого бота или `@username`) остаются: если токен support-бота не задан, кнопка ведёт наружу.

---

## Контроллер

`SupportBotController` — свой thread + event loop, как у основного бота.

| Метод | Кто вызывает | Зачем |
|-------|--------------|--------|
| `start` / `stop` / `get_status` | Flask `/start-support-bot`, `/stop-support-bot`; `__main__` при `auto_start_support_bot` | Polling |
| `get_bot_instance` / `get_loop` | `idle_close.run_idle_close_followup` | Сообщение в форум и пользователю после автозакрытия |

Старт требует `support_bot_token`, `support_bot_username` и непустой `get_admin_ids()`. Для топиков нужен `support_forum_chat_id` (супергруппа с Topics, бот — админ с правом создавать топики).

---

## Хендлеры — `get_support_router()`

| Хендлер | Зачем |
|---------|--------|
| `start_handler` | `/start`, deep-link `?new`, бан |
| `support_new_ticket_handler` + FSM subject/message | Создать тикет, сохранить медиа, создать топик, зеркалировать админам |
| `support_my_tickets_handler` / `support_view_ticket_handler` | Список и карточка |
| `support_reply_*` | Ответ пользователя |
| `forum_thread_message_handler` | Ответ админа в топике → пользователю; внутренние заметки |
| `support_close_ticket_handler` | Пользователь закрыл + close topic |
| `admin_close_ticket` / `admin_reopen_ticket` / `admin_delete_ticket` | Модерация |
| `admin_toggle_star` | Важное + pin топика |
| `admin_ban_user` / `admin_unban_user` | Бан из контекста тикета |
| `admin_note_*` | Внутренние заметки |
| `relay_user_message_to_forum` | Сообщение вне FSM дописывается в открытый тикет |

Данные: `rw_repo` / `database` (`create_support_ticket`, `add_support_message`, `set_ticket_status`, `update_ticket_thread_info`). Медиа: `ticket_media.save_ticket_media`.

---

## Автозакрытие — `idle_close.py`

| Функция | Кто вызывает | Зачем |
|---------|--------------|--------|
| `maybe_auto_close_idle_tickets` | `scheduler` каждый цикл (5 мин) | Найти тикеты, где после ответа админа пользователь молчит N дней |
| `run_idle_close_followup` | после SQL-закрытия | Сообщение в топик, close topic, уведомить пользователя |

N берётся из настройки (`get_ticket_auto_close_days` / `validate_ticket_auto_close_days`). Нецелое значение отвергается с warning. Только что reopen'утый тикет сразу не закрывается (`tests/test_ticket_auto_close.py`).

SQL-часть: `database.find_open_tickets_idle_after_admin`, `auto_close_idle_admin_tickets`.

---

## Вложения — `ticket_media.py`

Каталог рядом с `users.db` (`get_ticket_media_root`), не в `webhook_server/static`. Env: `TICKET_FILES_DIR`.

| Функция | Где | Зачем |
|---------|-----|--------|
| `save_ticket_media` | support-бот, основной бот | Скачать из Telegram |
| `save_ticket_media_bytes` | Mini App upload | Загрузка из браузера |
| `public_support_message` | панель JSON | Отдать сообщение без внутренних путей |
| `jailed_ticket_folder` | все записи/чтения | Path jail |
| `purge_expired_closed_ticket_media` | scheduler раз в час | TTL 7 дней после закрытия |
| `delete_ticket_media_dir` | `database.delete_ticket` | Удалить папку вместе с тикетом |

Квоты: 10 МБ/файл, 10 файлов / 30 МБ на тикет, проверка magic-bytes. Тесты: `test_ticket_media_*`.

Скачивание: Flask `/support/ticket-file/<message_id>`, `/ticket_files/...`; Mini App `GET /api/support/ticket-file/{message_id}`.

---

## Панель и Mini App

Панель: `/support`, partial-таблица, карточка тикета, bulk close/delete (`bulk_close_open_tickets`, `bulk_delete_all_tickets`), удаление одного тикета.

Mini App: `POST /api/support/{status,create,send,ticket,close,upload}`.

Оба пишут в те же таблицы — пользователь видит одну переписку во всех каналах.

---

## Связь с модулями

`modules/ramadan_tracker` при запросе выплаты создаёт тикет в `support_tickets` и топик через временный инстанс support-бота. Support-бот должен быть настроен и добавлен в форум-группу.
