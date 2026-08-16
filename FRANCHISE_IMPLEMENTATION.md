# Реализация модуля «Франшиза» (управляемые клоны ботов)

## Что изменилось в этом цикле

Точечные правки runtime-управления клонами: включение/выключение франшизы и отдельных ботов больше не требует `docker-compose restart`. Добавлены остановка одного клона, автоотключение по невалидному токену, кабинет «Мои боты», удаление в веб-админке и отдельный флаг видимости пункта меню.

### Изменённые файлы и закрытые задачи

1. **`src/shop_bot/factory_bot/service.py`** — задачи 1, 4, 5
   - `stop_bot(bot_id)` — идемпотентная остановка одного клона (cancel task, await, без повторного закрытия `bot.session`).
   - `restart_bot(bot_id)` = `stop_bot` + `start_bot` (ротация токена).
   - `runner()` перехватывает `TelegramUnauthorizedError` / `TelegramForbiddenError`, ставит `is_active=0`, логирует **без токена**, корректно завершает task.
   - В dispatcher клона подключается `get_factory_router()` (список/удаление ботов владельца).

2. **`src/shop_bot/webhook_server/app.py`** — задачи 2, 6, 7
   - `toggle_franchise_settings()` после записи флага вызывает `start_all()` / `stop_all()` через `asyncio.run_coroutine_threadsafe` на loop root-бота (`future.result(timeout=5)`).
   - `franchise_toggle_bot_route` после смены `is_active` вызывает `start_bot` / `stop_bot`.
   - POST `/franchise/bot/<int:bot_id>/delete` — `@login_required` + CSRF, `stop_bot`, параметризованный `delete_managed_bot`.
   - Ключ `franchise_menu_button_visible` в сохраняемых настройках (дефолт `false`).
   - В контекст шаблонов передаются и `franchise_enabled`, и `franchise_menu_button_visible`.
   - Роуты `/franchise*` **не** проверяют `franchise_enabled`.

3. **`src/shop_bot/bot/admin_handlers.py`** — задача 2
   - `admin_franchise_toggle()` по-прежнему требует `is_admin()`; после переключения сразу `start_all()` / `stop_all()` на уже работающем loop.

4. **`src/shop_bot/factory_bot/middleware.py`** — задача 3
   - `FactoryStatsMiddleware` при выключенной франшизе сразу отдаёт управление handler без SQL статистики (лёгкий TTL-кэш `franchise_enabled`).
   - `OwnerCabinetEnhanceMiddleware` добавляет кнопку «🤖 Мои боты» в живой `partner_cabinet` клона.

5. **`src/shop_bot/factory_bot/handlers.py` + `keyboards.py`** — задача 5
   - В `cabinet_menu()` кнопки «🤖 Мои боты» и удаление каждого бота.
   - Список через `get_managed_bots_by_owner`; удаление заново проверяет `owner_telegram_id == from_user.id`.
   - После смены токена вызывается `restart_bot`.

6. **`src/shop_bot/data_manager/database.py` + `remnawave_repository.py`** — задачи 4–6
   - Новые функции: `update_managed_bot_active`, `get_managed_bots_by_owner`, `delete_managed_bot`, `get_factory_cabinet`.
   - Схема `managed_bots` не менялась (`is_active` переиспользуется). Связанные `factory_user_activity` / `partner_commissions` при удалении **не** стираются.

7. **Шаблоны** — задачи 6–7
   - `franchise.html` / `franchise_bot.html` — кнопка удаления с `confirm()`.
   - `settings.html` — чекбокс `franchise_menu_button_visible`.
   - `base.html` — пункт «Франшиза» виден при `franchise_enabled or franchise_menu_button_visible`.

## Как это работает сейчас

### Включение / выключение франшизы
- Telegram: Админка → Настройки → Франшиза → переключатель. Клоны стартуют/останавливаются сразу.
- Веб: Настройки → секция «Франшиза». Сохранение чекбокса тоже вызывает `start_all` / `stop_all`.
- Если root-бот ещё не запущен, сохраняется только флаг; клоны поднимутся при старте root-бота.

### Один клон
- Веб: «Включить» / «Отключить» на `/franchise` реально стартует/останавливает aiogram-процесс.
- Невалидный токен: polling **не** ретраится; `is_active=0`; запись и комиссии остаются. После нового токена — «Включить» или повторная регистрация токена владельцем (`restart_bot`).

### Кабинет владельца
- В клоне у владельца в кабинете есть «🤖 Мои боты».
- Удаление проверяет владение на сервере на каждое нажатие.

### Меню веб-админки
- `franchise_enabled` — включает клонирование и runtime клонов.
- `franchise_menu_button_visible` — только видимость ссылки «Франшиза» в меню (чтобы зайти в заявки/удаление при выключенной франшизе).
- Для существующих инсталляций новый флаг по умолчанию `false` (поведение меню не меняется, пока админ явно не включит чекбокс).

## Безопасность

- Токены клонов по-прежнему хранятся в `enc1$...`; в UI и логах полный токен не выводится.
- Новые HTTP-роуты: `@login_required`, CSRF, `bot_id` как `int`, только параметризованный SQL.
- Деструктивные Telegram-действия заново проверяют `is_admin()` / `owner_telegram_id`.
- Падение одного клона ловится внутри `runner()` и не роняет loop root-бота.

## Тесты

- Существующие: `tests/test_managed_bot_ownership.py`, `tests/test_managed_bot_token_encrypt.py`.
- Новые: `tests/test_franchise_runtime.py` — идемпотентность `stop_bot`/`start_bot`, автоотключение по `TelegramUnauthorizedError`, владение при удалении, видимость пункта меню.

## Развёртывание

Пересборка контейнера нужна только чтобы подтянуть новый код. После деплоя **повторно переключать франшизу уже не требуется ради применения флага** — runtime подхватывает изменения на живом loop.
