# Комментарии: `src/shop_bot/webhook_server/app.py` (часть 1)

Flask-админка и вебхуки оплат. Модульного docstring нет. Фабрика: `create_webhook_app(bot_controller_instance)` — шаблоны `webhook_server/templates/`, поток из `__main__.py` (`SHOPBOT_FLASK_HOST` / `SHOPBOT_FLASK_PORT`, по умолчанию `127.0.0.1:1488`). См. [ADMIN_PANEL_DOCUMENTATION.md](../../ADMIN_PANEL_DOCUMENTATION.md).

Инвентарь этой части: `_parse_decimal_amount` … `create_webhook_app.admin_key_details_json` (хелперы модуля + обвязка фабрики + маршруты до карточки ключа). Дальше по файлу — смена тарифа, создание ключей, support, settings, вебхуки, франшиза.

Покрыто записей инвентаря: **108**.

---

## `_parse_decimal_amount` (144–157)

**Docstring в коде:** нет

```
"""Разобрать сумму в Decimal с квантованием до копеек; None при пустом/битом значении."""
```

Строка: strip, `,`→`.`, пробелы убрать. Не строка → `str(value)`. Исключение → `logger.warning` с `log_prefix`, `return None`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 146–148 | value is None | ValueError «amount is None» |
| 149–151 | str / иначе | нормализация |
| 152–154 | пусто / Decimal | quantize `0.01` |
| 155–157 | except | warning, None |

Побочных эффектов кроме лога нет.

## `_setting_flag_enabled` (160–161)

**Docstring в коде:** нет

```
"""True, если строка raw в true/1/on/yes/y (регистр не важен); None/пусто → False."""
```

## `_pending_method_allowed` (164–169)

**Docstring в коде:** есть (дословно):

```
True if pending metadata.payment_method matches one of the allowed provider names.
```

Не-dict → False. Сравнение `payment_method` и имён провайдера в lower/strip.

## `_pending_expected_amount` (172–178)

**Docstring в коде:** нет

```
"""Ожидаемая сумма заказа из pending: `price`, иначе `amount_rub`; иначе None."""
```

Не-dict → None. Парсинг через `_parse_decimal_amount(..., log_prefix="pending amount")`.

## `_platega_amount_covers_order` (181–187)

**Docstring в коде:** есть (дословно):

```
Platega callback amount is what the customer paid.

    The provider may add its own fee on top of the order we created
    (e.g. 107.00 charged vs 100.00 pending). Underpayment is still rejected.
```

По коду: `got_amount >= expected_amount`.

## `_extract_platega_webhook_amount` (190–199)

**Docstring в коде:** есть (дословно):

```
Platega callback: top-level `amount`, with paymentDetails.amount as fallback.
```

Не-dict → None. Сначала top-level `amount` (даже если 0). Иначе `paymentDetails` / `payment_details`.amount.

## `_dispatch_payment_processing` (202–247)

**Docstring в коде:** есть (дословно):

```
Fulfill paid orders even when the polling bot loop isn't running.

    If the main bot + EVENT_LOOP are available, schedule into that loop.
    Otherwise, run in a background thread using a temporary Bot instance.
```

Вызывает `handlers.process_successful_payment`. Живой bot + running loop → `run_coroutine_threadsafe`. Иначе токен из `telegram_bot_token`; без токена — error и выход.

**Побочные эффекты:** Telegram / fulfillment (через `process_successful_payment`: БД, панель, сообщения). Поток `shopbot-payment-fulfillment` (daemon).

| Строки | Блок | Зачем |
|--------|------|--------|
| 210–220 | loop / live_bot | get_loop / get_bot_instance; Exception → None |
| 222–224 | живой путь | schedule на loop бота |
| 226–229 | нет токена | не выдавать заказ |
| 231–247 | фон | временный Bot + asyncio.run |

### `_dispatch_payment_processing._worker` (231–245)

**Docstring в коде:** нет

```
"""Целевая функция потока: asyncio.run(_run); ошибка — error+exc_info."""
```

### `_dispatch_payment_processing._worker._run` (232–240)

**Docstring в коде:** нет

```
"""Создать временный Bot(HTML), await process_successful_payment, close в finally."""
```

`bot.close` глотает Exception.

## `_dispatch_bot_notification` (250–297)

**Docstring в коде:** есть (дословно):

```
Отправляет произвольное текстовое уведомление пользователю бота из админ-панели
    (используется, например, при смене статуса заявки на вывод реферальных средств).
    Использует ту же схему диспетчеризации, что и обработка платежей: живой Bot-инстанс
    из работающего event loop, либо временный Bot в отдельном потоке.
```

Без токена на запасном пути — тихий `return` (без лога). Поток `shopbot-user-notification`.

**Побочные эффекты:** Telegram `send_message`. Reachability: `telegram_reachability.handle_send_exception`.

### `_dispatch_bot_notification._send` (267–272)

**Docstring в коде:** нет

```
"""await send_message(user_id, text); сбой — handle_send_exception или warning."""
```

### `_dispatch_bot_notification._worker` (282–295)

**Docstring в коде:** нет

```
"""Фоновый поток: asyncio.run(_run); ошибка — Notification dispatch failed."""
```

### `_dispatch_bot_notification._worker._run` (283–291)

**Docstring в коде:** нет

```
"""Временный Bot(HTML), await _send, close в finally."""
```

## `franchise_settings` (438–447)

**Docstring в коде:** есть (дословно):

```
    Возвращает текущее состояние франшизы.
    True = включена, False = выключена
```

Читает `franchise_enabled`. True при `1`/`true`/`yes`/`on`. Exception → False. **БД** read.

## `franchise_menu_button_visible` (450–456)

**Docstring в коде:** есть (дословно):

```
Видимость пункта «Франшиза» в меню веб-админки (независимо от franchise_enabled).
```

Флаг `franchise_menu_button_visible`, те же true-строки. Exception → False. **БД** read.

## `_run_on_root_bot_loop` (459–490)

**Docstring в коде:** есть (дословно):

```
Запустить coroutine action(service) на loop root-бота из Flask-потока.

    Не падает, если сервис/loop ещё не созданы. Не блокирует HTTP дольше timeout.
```

`get_service()` None / loop не running → warning, выход (изменение уже в БД применится позже). Если текущий running loop == loop бота — `create_task`. Иначе `run_coroutine_threadsafe`; `wait=False` не ждёт. `fut.result(timeout)` ловит Exception.

**Побочные эффекты:** старт/стоп клонов (то, что передали в `action`).

## `_apply_franchise_runtime` (493–503)

**Docstring в коде:** есть (дословно):

```
Включить/выключить все клоны на уже работающем event loop.
```

`invalidate_franchise_enabled_cache()` (ошибка игнор). `enabled` → `svc.start_all()`, иначе `stop_all()`.

## `toggle_franchise_settings` (506–521)

**Docstring в коде:** есть (дословно):

```
    Переключает состояние франшизы (ВКЛ/ВЫКЛ).
    Возвращает новое состояние: True = включена, False = выключена
    Сразу запускает или останавливает клонов, если root-бот уже работает.
```

**БД:** `rw_repo.update_setting('franchise_enabled', ...)`. Затем `_apply_franchise_runtime`. Exception → False (по коду: не откатывает уже записанное, если упало после update).

## `_forum_coro_wait` (531–533)

**Docstring в коде:** нет

```
"""Поставить coro на loop и ждать fut.result(timeout) — синхронно из Flask/фонового потока."""
```

## `run_bulk_ticket_followup` (536–612)

**Docstring в коде:** есть (дословно):

```
Форум и файлы после массового SQL. Не вызывать из HTTP-потока в проде.

    Пауза между вызовами Telegram, чтобы не забить flood-limit. Ошибка одной
    темы не останавливает остальные. Пользователям в личку не пишем — это
    массовая админ-операция, не переписка по тикету.
```

**Побочные эффекты:** **БД** `cleanup_ticket_media_ids` при `media_ticket_ids`. **Telegram** forum: `delete` → delete_forum_topic, при сбое close_forum_topic; иначе close. Глобальный `_bulk_ticket_forum_lock`. Пауза `gap_sec` (0.12) между темами. Нет bot/loop → warning, темы не трогает.

| Строки | Блок | Зачем |
|--------|------|--------|
| 552–556 | media_ticket_ids | чистка вложений |
| 558–566 | нет целей / нет бота | выход |
| 568–612 | lock + цикл | форум + sleep |

---

## `create_webhook_app` (615–7521)

**Docstring в коде:** нет

```
"""Собрать Flask-приложение админки: CSRF, сессии, плагины, все маршруты панели и вебхуков.

Сохраняет bot_controller_instance в модульный _bot_controller. Сервер не поднимает
(это __main__). Возвращает готовый flask_app.
"""
```

Обвязка при создании (ADMIN_PANEL_DOCUMENTATION):

- CSRF (`flask-wtf`), cookie-сессия 30 дней;
- `SECRET_KEY` из `SHOPBOT_SECRET_KEY` или `token_hex(32)`;
- `MAX_CONTENT_LENGTH` = 12 MiB (ZIP модулей и формы);
- cookie: HTTPONLY, SAMESITE (`SHOPBOT_SESSION_SAMESITE`, default Lax), SECURE (`SHOPBOT_SESSION_SECURE`);
- `ENABLE_DEBUG_ENDPOINTS` / `DEBUG_IP_ALLOWLIST` / `TON_WEBHOOK_SECRET`;
- `module_loader.discover_modules()` + `set_flask_app`;
- context processor `inject_current_year`;
- `login_required` на операционных роутах (вебхуки оплат — без него, ниже по файлу);
- синглтон `_support_bot_controller` на уровне модуля (не создаётся здесь).

Диагностика путей шаблонов — `logger.debug`. Вложенные хендлеры этой части — до `admin_key_details_json`; остальное (ключи CRUD, support-страницы, settings, вебхуки, франшиза, button constructor) регистрируется тем же вызовом, но в инвентаре следующих частей.

**Побочные эффекты фабрики:** глобальный `_bot_controller`; привязка Flask к module_loader. Сами маршруты пишут БД/Telegram при запросах.

| Строки | Блок | Зачем |
|--------|------|--------|
| 616–617 | global | связать панель с контроллером бота |
| 619–632 | debug путей | login.html / templates |
| 634–638 | Flask | templates + static |
| 640–642 | module_loader | discover + set_flask_app |
| 645–657 | config | сессия, лимит тела, debug/TON |
| 661–662 | CSRF | на всё приложение |
| 7521 | return | готовый app |

### `create_webhook_app._handle_promo_after_payment` (665–757)

**Docstring в коде:** нет

```
"""После оплаты: redeem промокода, при лимите деактивировать, написать админам."""
```

Пустой `promo_code` → выход. `redeem_promo_code`; если None — `check_promo_code_available`. Деактивация при `usage_limit_total` исчерпан или `availability_error == "total_limit_reached"`. Лимит на пользователя только в тексте админам (код не гасится).

**Побочные эффекты:** **БД** redeem / update_promo_code_status. **Telegram** админам (`get_admin_ids`) через loop живого бота. Ошибки глотаются.

В этой части файла не вызывается (нужен вебхукам ниже).

### `create_webhook_app.inject_current_year` (760–797)

**Docstring в коде:** есть (дословно):

```
Inject common variables into all templates
```

Context processor (все шаблоны). Не маршрут.

Отдаёт: `current_year`, `csrf_token` (generate_csrf), статусы ботов, флаги готовности к старту (токен/username/admin; support + admin_ids), счётчики тикетов, `brand_title`, `panel_login`, франшиза, `module_menu_items`.

**БД** read (settings, tickets, admin_ids). Exception по тикетам → нули.

### `create_webhook_app.login_required` (799–805)

**Docstring в коде:** нет

```
"""Декоратор: нет session['logged_in'] → redirect на login_page."""
```

Не проверяет CSRF и не смотрит webapp `auth_token` (см. комментарий в `login_page`).

### `create_webhook_app.login_required.decorated_function` (801–804)

**Docstring в коде:** нет

```
"""Обёртка: редирект на логин или вызов исходной view."""
```

### `create_webhook_app._rate_limit_login` (811–820)

**Docstring в коде:** нет. В коде `#`: in-memory brute-force (CWE-307), 5 / 5 мин на IP.

```
"""True, если попытка логина с IP ещё в лимите; иначе False (окно window_sec)."""
```

Пишет `_login_attempts` в памяти процесса. Успешный логин счётчик не сбрасывает.

### `create_webhook_app._login_client_ip` (824–831)

**Docstring в коде:** есть (дословно):

```
IP for login rate-limit. Honor X-Forwarded-For only behind a local proxy.
```

XFF только если `remote_addr` в `{127.0.0.1, ::1}`. Иначе remote или `"unknown"`.

### `create_webhook_app._verify_panel_password` (833–843)

**Docstring в коде:** есть (дословно):

```
Verify panel password. Prefers bcrypt hashes; legacy plaintext uses compare_digest.
```

Пустой stored → False. `$2…` → `bcrypt.checkpw` (Exception → fallback). Иначе `compare_digest` (CWE-208 в `#`).

### `create_webhook_app.login_page` (846–886)

**Docstring в коде:** нет. Маршрут `GET, POST /login`. Без `login_required`. CSRF приложения действует.

```
"""Форма входа в панель: логин/пароль, опционально TOTP; при успехе session['logged_in']."""
```

GET: `login.html`, флаг `totp_enabled`. POST: rate-limit → 429 + flash. Username `compare_digest`. TOTP: `decrypt_managed_bot_token(panel_totp_secret)`, `pyotp.TOTP.verify(..., valid_window=1)` только если user+pass ок. Успех: plaintext-пароль мигрирует в bcrypt (`update_setting`); `session.permanent` при `remember_me`; redirect dashboard. Иначе flash «Неверный логин или пароль».

В коде `#`: сессия для CSRF; username без timing oracle; миграция CWE-916; `logged_in` изолирован от webapp-токена.

**Побочные эффекты:** **сессия**; **БД** hash-миграция; flash.

### `create_webhook_app.logout_page` (890–893)

**Docstring в коде:** нет. Маршрут `POST /logout`. `@login_required`.

```
"""Снять session['logged_in'], flash успеха, redirect на логин."""
```

**Побочные эффекты:** сессия, flash.

### `create_webhook_app.get_common_template_data` (895–939)

**Docstring в коде:** нет

```
"""Общий dict для страниц: статусы ботов, тикеты, бренд, хосты, бейдж заявок на вывод."""
```

Как context processor плюс `referral_requests_stats` и `hosts` (для модалки выдачи ключа). Не маршрут. **БД** read.

### `create_webhook_app.update_brand_title_route` (943–951)

**Docstring в коде:** нет. Маршрут `POST /brand-title`. `@login_required`.

```
"""Сохранить panel_brand_title; JSON ok/title или 400 empty / 500."""
```

**Побочные эффекты:** **БД** `update_setting`.

### `create_webhook_app.index` (955–956)

**Docstring в коде:** нет. Маршрут `GET /`. `@login_required`.

```
"""Редирект на dashboard_page."""
```

Без побочных эффектов кроме redirect.

### `create_webhook_app.dashboard_page` (960–1000)

**Docstring в коде:** нет. Маршрут `GET /dashboard`. `@login_required`.

```
"""Дашборд: KPI, график 30 дней, транзакции (page, 8/стр), speedtest хостов и SSH-цели."""
```

`hosts[].latest_speedtest` через `get_latest_speedtest`. Шаблон `dashboard.html`.

**Побочные эффекты:** нет записи; **БД** read.

### `create_webhook_app.run_speedtests_route` (1004–1009)

**Docstring в коде:** нет. Маршрут `POST /dashboard/run-speedtests`. `@login_required`.

```
"""Запустить speedtest_runner.run_speedtests_for_all_hosts; JSON ok или 500."""
```

**Побочные эффекты:** SSH/speedtest по хостам, запись результатов раннером.

### `create_webhook_app.dashboard_stats_partial` (1014–1022)

**Docstring в коде:** нет. Маршрут `GET /dashboard/stats.partial`. `@login_required`.

```
"""HTML-partial KPI дашборда (users/keys/spent/hosts)."""
```

### `create_webhook_app.dashboard_transactions_partial` (1026–1030)

**Docstring в коде:** нет. Маршрут `GET /dashboard/transactions.partial`. `@login_required`.

```
"""HTML-partial таблицы транзакций дашборда (page, 8/стр)."""
```

### `create_webhook_app.dashboard_charts_json` (1034–1036)

**Docstring в коде:** нет. Маршрут `GET /dashboard/charts.json`. `@login_required`.

```
"""JSON рядов get_daily_stats_for_charts(days=30)."""
```

### `create_webhook_app.statistics_page` (1041–1279)

**Docstring в коде:** есть (дословно):

```
Страница статистики (обзор).
```

Маршрут `GET /statistics`. `@login_required`. Шаблон `statistics.html`.

Сводка: хосты active/disabled; `get_admin_stats`; активные клиенты = DISTINCT user_id с неистёкшим ключом; платежи (status paid/success/succeeded, метод ≠ balance); рефералы; подарки `user_gifts`; reachability. Графики: users/keys 30д, платежи 7д, рефералы 30д, топ-8 `metadata.plan_name`.

**Побочные эффекты:** нет записи. **БД** read, в т.ч. сырой sqlite3 к `rw_repo.database.DB_FILE`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1044–1056 | hosts | total/active/disabled |
| 1058–1085 | clients | admin_stats + SQL active keys |
| 1087–1121 | payments | totals + today, без balance |
| 1123–1142 | referrals | users.referred_by |
| 1144–1163 | gifts | user_gifts |
| 1165–1191 | reachability + metrics | dict в шаблон |
| 1193–1276 | charts | daily + SQL series + plans |

### `create_webhook_app.statistics_page._labels` (1197–1199)

**Docstring в коде:** нет

```
"""Список ISO-дат за последние days дней, от старых к сегодня."""
```

### `create_webhook_app.analytics_overview_page` (1285–1299)

**Docstring в коде:** нет. Маршрут `GET /analytics`. `@login_required`.

```
"""Обзор продаж: get_sales_overview, прогноз, юзеры без реальной оплаты с ключами, trial-стата."""
```

Шаблон `analytics/overview.html`, `active_tab='overview'`. **БД** read.

### `create_webhook_app.analytics_overview_charts_json` (1303–1306)

**Docstring в коде:** нет. Маршрут `GET /analytics/overview_charts.json`. `@login_required`.

```
"""JSON get_revenue_series(days) — query `days`, default 30."""
```

### `create_webhook_app.analytics_transactions_page` (1310–1331)

**Docstring в коде:** нет. Маршрут `GET /analytics/transactions`. `@login_required`.

```
"""Таблица транзакций: q/sort_by/sort_dir, 20/стр, analytics/transactions.html."""
```

### `create_webhook_app.analytics_transactions_csv` (1335–1364)

**Docstring в коде:** нет. Маршрут `GET /analytics/transactions.csv`. `@login_required`.

```
"""Скачать CSV тех же фильтров: до 100000 строк, `;`, utf-8-sig, filename=transactions.csv."""
```

Колонки: ID, пользователь, сумма, статус, метод, ID провайдера, тариф, действие, дата. Без записи в БД.

### `create_webhook_app.analytics_plans_page` (1368–1371)

**Docstring в коде:** нет. Маршрут `GET /analytics/plans`. `@login_required`.

```
"""Аналитика тарифов get_plans_analytics(limit=50)."""
```

### `create_webhook_app.analytics_payment_methods_page` (1375–1378)

**Docstring в коде:** нет. Маршрут `GET /analytics/payment-methods`. `@login_required`.

```
"""Аналитика методов оплаты get_payment_methods_analytics."""
```

### `create_webhook_app.analytics_referrals_page` (1382–1394)

**Docstring в коде:** нет. Маршрут `GET /analytics/referrals`. `@login_required`.

```
"""Реферальная аналитика + топ-15 рефереров и покупателей."""
```

### `create_webhook_app.analytics_coupons_page` (1398–1402)

**Docstring в коде:** нет. Маршрут `GET /analytics/coupons`. `@login_required`.

```
"""Список купонов get_coupons_analytics и планы для формы создания."""
```

### `create_webhook_app.analytics_coupons_create_route` (1406–1454)

**Docstring в коде:** нет. Маршрут `POST /analytics/coupons/create`. `@login_required`.

```
"""Создать промокод из формы; flash и redirect на список купонов."""
```

Поля: code, скидка %/сумма, лимиты, даты ISO, description, segment, applicable_plan_ids. `created_by=session.get('admin_id')` (логин `admin_id` не ставит — по коду может быть None). ValueError / прочее → flash danger.

**Побочные эффекты:** **БД** `create_promo_code`. flash.

### `create_webhook_app.analytics_coupons_toggle_route` (1458–1465)

**Docstring в коде:** нет. Маршрут `POST /analytics/coupons/<path:code>/toggle`. `@login_required`.

```
"""Включить/выключить купон: form is_active=='1' → update_promo_code_status."""
```

**Побочные эффекты:** **БД**. flash. Redirect список.

### `create_webhook_app.analytics_coupons_delete_route` (1469–1475)

**Docstring в коде:** нет. Маршрут `POST /analytics/coupons/<path:code>/delete`. `@login_required`.

```
"""Удалить промокод delete_promo_code; flash; redirect список."""
```

**Побочные эффекты:** **БД** delete.

### `create_webhook_app.analytics_utm_page` (1479–1489)

**Docstring в коде:** нет. Маршрут `GET /analytics/utm`. `@login_required`.

```
"""UTM-аналитика и username бота для ссылок."""
```

### `create_webhook_app.analytics_utm_create_route` (1493–1510)

**Docstring в коде:** нет. Маршрут `POST /analytics/utm/create`. `@login_required`.

```
"""Создать UTM-ссылку create_utm_link (slug + source/medium/campaign/…)."""
```

Неуспех: пустой/занятый slug. **БД** insert. flash. Redirect `/analytics/utm`.

### `create_webhook_app.analytics_utm_delete_route` (1514–1520)

**Docstring в коде:** нет. Маршрут `POST /analytics/utm/<path:slug>/delete`. `@login_required`.

```
"""Удалить UTM-метку delete_utm_link."""
```

**Побочные эффекты:** **БД** delete.

### `create_webhook_app._referral_program_common` (1527–1533)

**Docstring в коде:** нет. В коде `#`: stats уже в get_common_template_data (бейдж сайдбара).

```
"""Подписи методов вывода и статусов заявок для шаблонов рефералки."""
```

`sbp`/`card`/`usdt_trc20`; `new`/`processing`/`paid`/`rejected`. Не маршрут.

### `create_webhook_app.referral_program_page` (1537–1538)

**Docstring в коде:** нет. Маршрут `GET /referral-program`. `@login_required`.

```
"""Редирект на список заявок на вывод."""
```

### `create_webhook_app.referral_program_settings_page` (1542–1553)

**Docstring в коде:** нет. Маршрут `GET /referral-program/settings`. `@login_required`.

```
"""Форма настроек рефералки: settings + список банков СБП (CSV)."""
```

### `create_webhook_app.referral_program_settings_route` (1557–1576)

**Docstring в коде:** нет. Маршрут `POST /referral-program/settings`. `@login_required`.

```
"""Сохранить флаги вывода и числовые/текстовые поля рефералки в bot_settings."""
```

Чекбоксы: последнее значение из getlist, on/true/1/yes → `'true'`. Поля: reward_type, minimum_withdrawal, percentage, fixed bonus, on_start amount, discount, sbp_banks — только если ключ есть в form.

**Побочные эффекты:** **БД** `update_setting` (несколько ключей). flash. Redirect GET settings.

### `create_webhook_app.referral_program_top_page` (1580–1589)

**Docstring в коде:** нет. Маршрут `GET /referral-program/top`. `@login_required`.

```
"""Топ-50 рефереров."""
```

### `create_webhook_app.referral_program_requests_page` (1593–1604)

**Docstring в коде:** нет. Маршрут `GET /referral-program/requests`. `@login_required`.

```
"""Заявки на вывод; фильтр query status."""
```

### `create_webhook_app.referral_program_request_status_route` (1608–1643)

**Docstring в коде:** нет. Маршрут `POST /referral-program/requests/<int:request_id>/status`. `@login_required`.

```
"""Сменить статус заявки; paid/processing/rejected — пуш пользователю в бота."""
```

`update_referral_withdrawal_request_status` (+ reject_reason). При ok+updated: тексты выплаты / «в обработке» / отказ (причина html.escape; в тексте отказ — «сумма возвращена на реферальный баланс» — возврат делает репозиторий, не этот хендлер).

**Побочные эффекты:** **БД** статус (и возврат баланса внутри repo при rejected). **Telegram** `_dispatch_bot_notification`. flash. Redirect referrer или список.

### `create_webhook_app.analytics_economics_page` (1647–1657)

**Docstring в коде:** нет. Маршрут `GET /analytics/economics`. `@login_required`.

```
"""Расходы на серверы: записи + get_economics_summary."""
```

### `create_webhook_app.analytics_economics_create_route` (1661–1673)

**Docstring в коде:** нет. Маршрут `POST /analytics/economics/create`. `@login_required`.

```
"""Добавить статью расходов create_server_cost_entry (label, host, cost, валюта…)."""
```

`monthly_cost` float, default 0; currency default RUB; status default active. Нет проверки ошибок create.

**Побочные эффекты:** **БД** insert. flash.

### `create_webhook_app.analytics_economics_delete_route` (1677–1680)

**Docstring в коде:** нет. Маршрут `POST /analytics/economics/<int:entry_id>/delete`. `@login_required`.

```
"""Удалить статью расходов delete_server_cost_entry."""
```

**Побочные эффекты:** **БД** delete.

### `create_webhook_app.analytics_forecast_page` (1684–1694)

**Docstring в коде:** нет. Маршрут `GET /analytics/forecast`. `@login_required`.

```
"""Прогноз выручки + топ-5 тарифов."""
```

### `create_webhook_app.analytics_broadcasts_page` (1700–1710)

**Docstring в коде:** нет. Маршрут `GET /analytics/broadcasts`. `@login_required`.

```
"""Список кампаний рассылки; к каждой get_broadcast_stats."""
```

### `create_webhook_app.analytics_broadcasts_create` (1714–1731)

**Docstring в коде:** нет. Маршрут `POST /analytics/broadcasts/create`. `@login_required`.

```
"""Создать кампанию: name, text_html, interval_hours≥1 (default 72), target_segment."""
```

Пустые name/text → flash, без записи. **БД** `create_broadcast_campaign`.

### `create_webhook_app.analytics_broadcasts_update` (1735–1748)

**Docstring в коде:** нет. Маршрут `POST /analytics/broadcasts/<int:campaign_id>/update`. `@login_required`.

```
"""Обновить name/text_html/interval_hours кампании."""
```

Пустые поля — без update. **БД** `update_broadcast_campaign`.

### `create_webhook_app.analytics_broadcasts_toggle` (1752–1755)

**Docstring в коде:** нет. Маршрут `POST /analytics/broadcasts/<int:campaign_id>/toggle`. `@login_required`.

```
"""Переключить активность кампании toggle_broadcast_campaign."""
```

**Побочные эффекты:** **БД**.

### `create_webhook_app.analytics_broadcasts_delete` (1759–1764)

**Docstring в коде:** нет. Маршрут `POST /analytics/broadcasts/<int:campaign_id>/delete`. `@login_required`.

```
"""Удалить кампанию; имя для flash берётся до delete."""
```

**Побочные эффекты:** **БД** delete.

### `create_webhook_app.analytics_broadcasts_send_now` (1768–1791)

**Docstring в коде:** нет. Маршрут `POST /analytics/broadcasts/<int:campaign_id>/send-now`. `@login_required`.

```
"""Разослать сейчас: pending recipients, mark run, _dispatch_bot_notification каждому, record sends."""
```

Нет кампании / нет получателей — flash, без Telegram. `failed` считает только Exception вокруг dispatch (сам dispatch ошибки send глушит). `record_broadcast_sends` только если sent>0 (пишет исходный список recipients, не только успешных).

**Побочные эффекты:** **БД** mark_broadcast_run / record_broadcast_sends. **Telegram** массово.

### `create_webhook_app._build_nginx_config` (1800–1823)

**Docstring в коде:** есть (дословно):

```
HTTP-only config; serves ACME webroot so certbot --webroot works.
```

Строка server: listen 80, ACME `/.well-known/acme-challenge/` → `/var/www/html`, `/` → proxy `127.0.0.1:{port}` + Upgrade. Не пишет диск.

### `create_webhook_app._build_nginx_ssl_config` (1825–1863)

**Docstring в коде:** есть (дословно):

```
Full SSL config: HTTP → HTTPS redirect + HTTPS reverse proxy.
```

Серты `/etc/letsencrypt/live/{domain}/fullchain.pem` + privkey. HTTP: ACME + `return 301 https://…`. HTTPS: TLSv1.2/1.3, тот же proxy.

### `create_webhook_app.webapp_nginx_config_route` (1867–1878)

**Docstring в коде:** нет. Маршрут `GET /settings/webapp/nginx-config`. `@login_required`.

```
"""Скачать HTTP-конфиг nginx для webapp (webapp_domain/port); без домена — комментарий text/plain."""
```

Порт clamp 1–65535, default 8001. `Content-Disposition: remnawave-webapp.conf`. Без записи на сервер.

### `create_webhook_app.webapp_setup_route` (1882–2243)

**Docstring в коде:** нет. Маршрут `POST /settings/webapp/setup`. `@login_required`.

```
"""Автонастройка Mini App: валидация домена/email/порта, nginx, Traefik или certbot, JSON steps."""
```

Форма: `webapp_domain`, `ssl_email`, `webapp_port`. Регэкспы `_DOMAIN_RE` / `_EMAIL_RE`. Успех шагов — `status in (ok, skip)`.

**Побочные эффекты (существенные):** **БД** update_setting domain/port/email; запись `/etc/nginx/sites-available/remnawave-webapp.conf` (+ sudo tee); symlink sites-enabled; `apt-get update/install nginx certbot`; `os.makedirs` ACME webroot; `nginx -t` / reload / start; docker inspect/SIGHUP traefik; запись `webapp.yml`; `chmod`+`bash install.sh`; `certbot certonly --webroot`. Процессы с timeout.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1909–1921 | validate | JSON error, без записи |
| 1923–1927 | settings | БД |
| 1964–1975 | nginx install | apt + start |
| 1977–2027 | conf + symlink + test + reload | ФС / subprocess |
| 2178–2240 | Traefik vs certbot | TLS |
| 2242–2243 | result | success = все ok/skip |

### `create_webhook_app.webapp_setup_route._step` (1889–1890)

**Docstring в коде:** нет

```
"""Добавить {name, status, message} в steps ответа."""
```

### `create_webhook_app.webapp_setup_route._run` (1892–1907)

**Docstring в коде:** нет

```
"""subprocess.run(cmd): ok/error/skip в steps; True при returncode 0."""
```

FileNotFoundError → skip. Timeout / прочее → error. stdout+stderr обрезаются до 800.

### `create_webhook_app.webapp_setup_route._nginx_reload` (1934–1947)

**Docstring в коде:** есть (дословно):

```
Try nginx -s reload first (works in Docker), fall back to service/systemctl.
```

**Побочные эффекты:** reload nginx.

### `create_webhook_app.webapp_setup_route._nginx_start` (1949–1962)

**Docstring в коде:** есть (дословно):

```
Start nginx after fresh install (Docker-compatible).
```

Пробует `service nginx start`, затем `nginx`.

### `create_webhook_app.webapp_setup_route._find_traefik_dynamic_dir` (2033–2131)

**Docstring в коде:** есть (дословно):

```
Return (dynamic_dir, cert_resolver) scanning filesystem then docker.
```

Пишет/удаляет `.wtest` для проверки writable. Кандидаты `/opt|/etc|/var|/usr/local/etc/traefik/dynamic`; затем directory: из traefik.yml (пропуск путей с `/remnawave`); затем docker ps/inspect mounts. Default resolver `letsencrypt`. Не найдено → `(None, cert_resolver)`.

**Побочные эффекты:** временный файл `.wtest`; docker CLI.

### `create_webhook_app.webapp_setup_route._write_traefik_config` (2133–2176)

**Docstring в коде:** нет

```
"""Записать dynamic/webapp.yml: Host(domain) → http://bridge_gw:port, tls certResolver."""
```

Gateway из `docker network inspect bridge`, fallback `172.17.0.1`. Возврат `(ok, message)`.

**Побочные эффекты:** запись YAML на диск.

### `create_webhook_app.webapp_check_route` (2247–2263)

**Docstring в коде:** нет. Маршрут `POST /settings/webapp/check`. `@login_required`.

```
"""Проверить доступность https://webapp_domain/, fallback http://; JSON ok/message."""
```

Нет домена → ok False. **HTTP** исходящий urllib (UA `XatabchikBot/1.0`). БД не пишет.

### `create_webhook_app.monitor_page` (2267–2278)

**Docstring в коде:** нет. Маршрут `GET /monitor`. `@login_required`.

```
"""Страница мониторинга: хосты и SSH-цели."""
```

Шаблон `monitor.html`.

### `create_webhook_app.monitor_local_json` (2282–2287)

**Docstring в коде:** нет. Маршрут `GET /monitor/local.json`. `@login_required`.

```
"""JSON resource_monitor.get_local_metrics; ошибка → {ok:False,error}."""
```

### `create_webhook_app.monitor_host_json` (2291–2296)

**Docstring в коде:** нет. Маршрут `GET /monitor/host/<host_name>.json`. `@login_required`.

```
"""JSON метрик удалённого хоста get_remote_metrics_for_host."""
```

Может ходить по SSH (внутри монитора).

### `create_webhook_app.monitor_target_json` (2300–2305)

**Docstring в коде:** нет. Маршрут `GET /monitor/target/<target_name>.json`. `@login_required`.

```
"""JSON метрик SSH-цели get_remote_metrics_for_target."""
```

### `create_webhook_app.monitor_series_json` (2310–2320)

**Docstring в коде:** нет. Маршрут `GET /monitor/series/<scope>/<name>.json`. `@login_required`.

```
"""История метрик get_metrics_series(scope, name, hours default 24, limit 1000)."""
```

hours битый → 24. Ошибка → 500 JSON.

### `create_webhook_app.support_table_partial` (2325–2330)

**Docstring в коде:** нет. Маршрут `GET /support/table.partial`. `@login_required`.

```
"""HTML-partial таблицы тикетов: status, page, 12/стр."""
```

Полная страница `/support` — в следующей части файла.

### `create_webhook_app.support_open_count_partial` (2334–2346)

**Docstring в коде:** нет. Маршрут `GET /support/open-count.partial`. `@login_required`.

```
"""Бейдж открытых тикетов для навбара; 0 → пустой HTML 200."""
```

### `create_webhook_app.users_page` (2350–2390)

**Docstring в коде:** нет. Маршрут `GET /users`. `@login_required`.

```
"""Список пользователей: q/sort/page/per_page (default 25), нормализация чисел, users.html."""
```

Приводит balance/referral_balance/keys_count/active_keys_count/total_spent. **БД** read.

### `create_webhook_app.users_table_partial` (2395–2422)

**Docstring в коде:** нет. Маршрут `GET /users/table.partial`. `@login_required`.

```
"""HTML-partial той же таблицы пользователей (те же query-параметры)."""
```

### `create_webhook_app.user_keys_partial` (2427–2437)

**Docstring в коде:** нет. Маршрут `GET /users/<int:user_id>/keys.partial`. `@login_required`.

```
"""JSON {html таблицы ключей, пагинация} для карточки пользователя."""
```

`get_keys_paginated(..., user_id=)`. Exception → пустой список. HTML — `partials/admin_keys_table.html`.

### `create_webhook_app.user_transactions_partial` (2442–2460)

**Docstring в коде:** нет. Маршрут `GET /users/<int:user_id>/transactions.partial`. `@login_required`.

```
"""JSON {html транзакций пользователя, пагинация, sort/dir}."""
```

### `create_webhook_app.user_referrals_json` (2465–2470)

**Docstring в коде:** нет. Маршрут `GET /users/<int:user_id>/referrals.json`. `@login_required`.

```
"""JSON список рефералов get_referrals_for_user; 500 при ошибке."""
```

### `create_webhook_app.users_search_json` (2474–2499)

**Docstring в коде:** есть (дословно):

```
Живой поиск пользователей по ID/username — для модалки "Назначить реферала"
        на карточке пользователя (и для любых будущих похожих подборов пользователя).
```

Маршрут `GET /users/search.json`. `@login_required`. Query `q`, `exclude` (вычесть telegram_id). Пустой q → `items: []`. До 8 строк. Поля: telegram_id, username, referred_by. Ошибка → 500 `search_failed`.

### `create_webhook_app.admin_global_search_json` (2503–2545)

**Docstring в коде:** есть (дословно):

```
Живой поиск по пользователям и ключам для топбара админки.
```

Маршрут `GET /admin/search.json`. `@login_required`. `q` без ведущего `@`; пусто → пустые массивы. `limit` 1–12, default 6. Ошибки users/keys логируются отдельно, ответ всё равно 200.

### `create_webhook_app.assign_referral_route` (2549–2579)

**Docstring в коде:** есть (дословно):

```
Вручную назначить реферала: пользователь `user_id` (из формы) становится
        приглашённым текущим пользователем `referrer_id` (users.referred_by).
```

Маршрут `POST /users/<int:referrer_id>/referrals/assign`. `@login_required`.

`link_referrer_if_eligible`. Статусы: linked / already_linked / self_referral_forbidden / invalid_referrer / not_eligible. JSON если Accept json или X-Requested-With XMLHttpRequest.

**Побочные эффекты:** **БД** referred_by. flash или JSON.

### `create_webhook_app.remove_referral_route` (2583–2597)

**Docstring в коде:** есть (дословно):

```
Снять одного реферала с карточки реферера (обнулить users.referred_by).
```

Маршрут `POST /users/<int:referrer_id>/referrals/<int:invitee_id>/remove`. `@login_required`.

`unlink_referral`: unlinked / not_linked / not_found / invalid.

**Побочные эффекты:** **БД**.

### `create_webhook_app.remove_all_referrals_route` (2601–2615)

**Docstring в коде:** есть (дословно):

```
Снять всех рефералов у указанного реферера.
```

Маршрут `POST /users/<int:referrer_id>/referrals/remove-all`. `@login_required`.

`unlink_all_referrals` → (ok, removed).

**Побочные эффекты:** **БД**.

### `create_webhook_app.users_pagination_partial` (2620–2628)

**Docstring в коде:** нет. Маршрут `GET /users/pagination.partial`. `@login_required`.

```
"""HTML пагинации списка пользователей (тот же q/sort/per_page)."""
```

### `create_webhook_app.user_details_json` (2632–2682)

**Docstring в коде:** нет. Маршрут `GET /users/<int:user_id>/details.json`. `@login_required`.

```
"""JSON карточки пользователя: профиль, счётчики ключей/транзакций, список рефералов."""
```

404 `not_found`. Активный ключ: expire > now и нет `missing_from_server_at`. Транзакции: только total через per_page=1.

### `create_webhook_app.adjust_balance_route` (2686–2723)

**Docstring в коде:** нет. Маршрут `POST /users/<int:user_id>/balance/adjust`. `@login_required`.

```
"""Изменить баланс на delta; JSON или flash; при form-успехе — Telegram о новом балансе."""
```

Битый delta → 400 / flash. `adjust_user_balance`. По коду: JSON `return` **до** блока уведомления — пуш только на обычном POST.

**Побочные эффекты:** **БД** баланс. **Telegram** send_message (loop или `asyncio.run`). flash.

### `create_webhook_app.adjust_referral_balance_route` (2727–2762)

**Docstring в коде:** нет. Маршрут `POST /users/<int:user_id>/referral-balance/adjust`. `@login_required`.

```
"""Изменить реферальный баланс на delta; та же схема ответа и Telegram, что у обычного баланса."""
```

`adjust_user_referral_balance` + `get_referral_balance` в тексте. JSON тоже возвращается до notify.

**Побочные эффекты:** **БД**. **Telegram**.

### `create_webhook_app.admin_keys_page` (2766–2803)

**Docstring в коде:** нет. Маршрут `GET /admin/keys`. `@login_required`.

```
"""Все ключи: search/sort/dir/page/per_page, хосты и users для фильтров, admin_keys.html."""
```

### `create_webhook_app.admin_keys_table_partial` (2808–2819)

**Docstring в коде:** нет. Маршрут `GET /admin/keys/table.partial`. `@login_required`.

```
"""HTML-partial таблицы ключей (те же фильтры)."""
```

### `create_webhook_app.admin_keys_pagination_partial` (2823–2839)

**Docstring в коде:** нет. Маршрут `GET /admin/keys/pagination.partial`. `@login_required`.

```
"""HTML пагинации списка ключей."""
```

### `create_webhook_app._resolve_key_plan` (2841–2851)

**Docstring в коде:** есть (дословно):

```
Определяет актуальный тариф ключа по plan_id, сохранённому в его description.
```

Не маршрут. description — JSON, начинается с `{`. Exception / нет plan_id → None. **БД** `get_plan_by_id`.

В `admin_key_details_json` тот же разбор plan_id продублирован, этот хелпер там не вызывается.

### `create_webhook_app.admin_key_details_json` (2855–2997)

**Docstring в коде:** нет. Маршрут `GET /admin/keys/<int:key_id>/details`. `@login_required`.

```
"""JSON карточки ключа: владелец, тариф, QR подписки, HWID-устройства, LTE-пул и расход по нодам."""
```

404 если ключа нет. QR: `qrcode.make(subscription_url)` → data PNG; сбой — warning, qr None. Устройства: `asyncio.run(remnawave_api.get_hwid_devices_for_user)` если есть `remnawave_user_uuid`; контейнеры devices/response/data/items. LTE только при `should_account_lte_traffic(plan, host_name)`: `get_key_lte_state`, `get_node_usage_for_key`. В коде `#`: LTE-пул у ключа, не у пользователя; в node_usage только node_uuid (без имени ноды).

**Побочные эффекты:** **HTTP** панель Remnawave (HWID). Генерация QR в памяти. **БД** read. Запись ключа/панели нет.
