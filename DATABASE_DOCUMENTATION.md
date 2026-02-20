# Документация базы данных Xatabchik VPN Bot

## Общая информация

**СУБД:** SQLite  
**Файл базы данных:** `users.db` (или `/app/project/users.db` в Docker)  
**Модуль базы данных:** [src/shop_bot/data_manager/database.py](src/shop_bot/data_manager/database.py)

База данных используется для хранения информации о пользователях, VPN-ключах, транзакциях, тикетах поддержки, франшизах и других данных бота.

---

## Таблицы базы данных

### 1. `users` - Пользователи

Основная таблица с информацией о пользователях бота.

| Поле | Тип | Описание |
|------|-----|----------|
| `telegram_id` | INTEGER PRIMARY KEY | Уникальный ID пользователя в Telegram |
| `username` | TEXT | Имя пользователя в Telegram |
| `total_spent` | REAL | Общая сумма потраченных средств (по умолчанию 0) |
| `total_months` | INTEGER | Общее количество купленных месяцев (по умолчанию 0) |
| `trial_used` | BOOLEAN | Использован ли пробный период (по умолчанию 0) |
| `agreed_to_terms` | BOOLEAN | Согласие с условиями использования (по умолчанию 0) |
| `registration_date` | TIMESTAMP | Дата регистрации (по умолчанию текущее время) |
| `is_banned` | BOOLEAN | Забанен ли пользователь (по умолчанию 0) |
| `balance` | REAL | Баланс пользователя в рублях (по умолчанию 0) |
| `referred_by` | INTEGER | ID пригласившего пользователя |
| `referral_balance` | REAL | Доступный реферальный баланс (по умолчанию 0) |
| `referral_balance_all` | REAL | Общий заработанный реферальный баланс (по умолчанию 0) |
| `referral_start_bonus_received` | BOOLEAN | Получен ли бонус за первого реферала (по умолчанию 0) |
| `referral_trial_day_bonus_received` | BOOLEAN | Получен ли бонус за пробный день реферала (по умолчанию 0) |
| `subscription_expiry_notifications_enabled` | BOOLEAN | Включены ли уведомления об истечении подписки (по умолчанию 1) |

**Функции для работы:**
- `register_user_if_not_exists()` - регистрация нового пользователя
- `get_user()` - получение информации о пользователе
- `get_all_users()` - получение всех пользователей
- `get_users_paginated()` - постраничное получение пользователей
- `ban_user()` / `unban_user()` - блокировка/разблокировка пользователя
- `set_terms_agreed()` - отметка согласия с условиями
- `update_user_stats()` - обновление статистики пользователя
- `get_balance()` / `set_balance()` / `add_to_balance()` - работа с балансом

---

### 2. `vpn_keys` - VPN-ключи

Таблица для хранения VPN-ключей пользователей.

| Поле | Тип | Описание |
|------|-----|----------|
| `key_id` | INTEGER PRIMARY KEY | Уникальный идентификатор ключа (автоинкремент) |
| `user_id` | INTEGER | ID пользователя (владельца ключа) |
| `host_name` | TEXT | Имя хоста/сервера |
| `squad_uuid` | TEXT | UUID группы серверов |
| `remnawave_user_uuid` | TEXT | UUID пользователя в системе Remnawave |
| `short_uuid` | TEXT | Короткий UUID для отображения |
| `email` | TEXT UNIQUE | Email ключа (уникальный) |
| `key_email` | TEXT UNIQUE | Email ключа (альтернативное поле, уникальное) |
| `subscription_url` | TEXT | URL подписки для подключения |
| `expire_at` | TIMESTAMP | Дата истечения срока действия |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `updated_at` | TIMESTAMP | Дата последнего обновления (по умолчанию текущее время) |
| `traffic_limit_bytes` | INTEGER | Лимит трафика в байтах |
| `traffic_limit_strategy` | TEXT | Стратегия лимита трафика ('NO_RESET' по умолчанию) |
| `tag` | TEXT | Тег ключа (например, 'trial', 'user_gift') |
| `description` | TEXT | Описание ключа |
| `missing_from_server_at` | TIMESTAMP | Время, когда ключ исчез с сервера |

**Индексы:**
- `uq_vpn_keys_email` - уникальный индекс на email
- `uq_vpn_keys_key_email` - уникальный индекс на key_email
- `idx_vpn_keys_user_id` - индекс на user_id
- `idx_vpn_keys_rem_uuid` - индекс на remnawave_user_uuid
- `idx_vpn_keys_expire_at` - индекс на expire_at

**Функции для работы:**
- `add_new_key()` - создание нового ключа
- `get_user_keys()` - получение всех ключей пользователя
- `get_key_by_id()` - получение ключа по ID
- `get_key_by_email()` - получение ключа по email
- `get_all_keys()` - получение всех ключей
- `update_key_fields()` - обновление полей ключа
- `delete_key_by_id()` - удаление ключа по ID
- `delete_key_by_email()` - удаление ключа по email

---

### 3. `transactions` - Транзакции

Таблица для хранения завершенных транзакций (платежей).

| Поле | Тип | Описание |
|------|-----|----------|
| `transaction_id` | INTEGER PRIMARY KEY | Уникальный ID транзакции (автоинкремент) |
| `payment_id` | TEXT UNIQUE | Уникальный ID платежа |
| `user_id` | INTEGER | ID пользователя |
| `username` | TEXT | Имя пользователя |
| `status` | TEXT | Статус транзакции |
| `amount_rub` | REAL | Сумма в рублях |
| `amount_currency` | REAL | Сумма в другой валюте |
| `currency_name` | TEXT | Название валюты |
| `payment_method` | TEXT | Метод оплаты |
| `metadata` | TEXT | Дополнительная информация (JSON) |
| `created_date` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Функции для работы:**
- `create_transaction()` - создание новой транзакции
- `get_recent_transactions()` - получение последних транзакций
- `get_paginated_transactions()` - постраничное получение транзакций

---

### 4. `pending_transactions` - Ожидающие транзакции

Таблица для хранения транзакций, ожидающих подтверждения оплаты.

| Поле | Тип | Описание |
|------|-----|----------|
| `payment_id` | TEXT PRIMARY KEY | Уникальный ID платежа |
| `user_id` | INTEGER | ID пользователя |
| `amount_rub` | REAL | Сумма в рублях |
| `metadata` | TEXT | Дополнительная информация (JSON) |
| `status` | TEXT | Статус ('pending' или 'paid', по умолчанию 'pending') |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `updated_at` | TIMESTAMP | Дата обновления (по умолчанию текущее время) |

**Функции для работы:**
- `create_payload_pending()` - создание ожидающей транзакции
- `get_pending_metadata()` - получение метаданных ожидающей транзакции
- `get_pending_status()` - получение статуса транзакции
- `find_and_complete_pending_transaction()` - завершение ожидающей транзакции

---

### 5. `processed_payments` - Обработанные платежи

Таблица для отслеживания уже обработанных платежей (защита от дублирования).

| Поле | Тип | Описание |
|------|-----|----------|
| `payment_id` | TEXT PRIMARY KEY | Уникальный ID платежа |
| `processed_at` | TIMESTAMP | Время обработки (по умолчанию текущее время) |

---

### 6. `xui_hosts` - Хосты/Серверы VPN

Таблица с настройками серверов VPN.

| Поле | Тип | Описание |
|------|-----|----------|
| `host_name` | TEXT PRIMARY KEY | Имя хоста (уникальное) |
| `squad_uuid` | TEXT UNIQUE | UUID группы |
| `description` | TEXT | Описание хоста |
| `default_traffic_limit_bytes` | INTEGER | Лимит трафика по умолчанию в байтах |
| `default_traffic_strategy` | TEXT | Стратегия лимита трафика ('NO_RESET' по умолчанию) |
| `host_url` | TEXT | URL панели управления |
| `host_username` | TEXT | Имя пользователя для API |
| `host_pass` | TEXT | Пароль для API |
| `host_inbound_id` | INTEGER | ID inbound'а в панели |
| `subscription_url` | TEXT | URL для подписок |
| `ssh_host` | TEXT | SSH хост для подключения |
| `ssh_port` | INTEGER | SSH порт |
| `ssh_user` | TEXT | SSH пользователь |
| `ssh_password` | TEXT | SSH пароль |
| `ssh_key_path` | TEXT | Путь к SSH ключу |
| `is_active` | INTEGER | Активен ли хост (по умолчанию 1) |
| `sort_order` | INTEGER | Порядок сортировки (по умолчанию 0) |
| `metadata` | TEXT | Дополнительная информация (JSON) |
| `remnawave_base_url` | TEXT | URL базы Remnawave API |
| `remnawave_api_token` | TEXT | API токен Remnawave |

**Функции для работы:**
- `create_host()` - создание нового хоста
- `get_host()` - получение информации о хосте
- `get_all_hosts()` - получение всех хостов
- `update_host_url()` - обновление URL хоста
- `update_host_ssh_settings()` - обновление SSH настроек
- `delete_host()` - удаление хоста

---

### 7. `plans` - Тарифные планы

Таблица с тарифными планами для покупки VPN.

| Поле | Тип | Описание |
|------|-----|----------|
| `plan_id` | INTEGER PRIMARY KEY | Уникальный ID плана (автоинкремент) |
| `host_name` | TEXT | Имя хоста (внешний ключ) |
| `squad_uuid` | TEXT | UUID группы серверов |
| `plan_name` | TEXT | Название плана |
| `months` | INTEGER | Количество месяцев |
| `duration_days` | INTEGER | Длительность в днях |
| `price` | REAL | Цена в рублях |
| `traffic_limit_bytes` | INTEGER | Лимит трафика в байтах |
| `traffic_limit_strategy` | TEXT | Стратегия лимита трафика ('NO_RESET' по умолчанию) |
| `hwid_device_limit` | INTEGER | Лимит устройств |
| `is_active` | INTEGER | Активен ли план (по умолчанию 1) |
| `sort_order` | INTEGER | Порядок сортировки (по умолчанию 0) |
| `metadata` | TEXT | Дополнительная информация (JSON) |

**Функции для работы:**
- `create_plan()` - создание нового плана
- `get_plan_by_id()` - получение плана по ID
- `get_plans_for_host()` - получение всех планов для хоста
- `get_active_plans_for_host()` - получение активных планов для хоста
- `update_plan()` - обновление плана
- `delete_plan()` - удаление плана

---

### 8. `support_tickets` - Тикеты поддержки

Таблица для хранения тикетов поддержки пользователей.

| Поле | Тип | Описание |
|------|-----|----------|
| `ticket_id` | INTEGER PRIMARY KEY | Уникальный ID тикета (автоинкремент) |
| `user_id` | INTEGER | ID пользователя |
| `status` | TEXT | Статус тикета ('open', 'closed' и т.д., по умолчанию 'open') |
| `subject` | TEXT | Тема тикета |
| `forum_chat_id` | TEXT | ID чата форума в Telegram |
| `message_thread_id` | INTEGER | ID треда сообщения в форуме |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `updated_at` | TIMESTAMP | Дата обновления (по умолчанию текущее время) |

**Индексы:**
- `idx_support_tickets_thread` - индекс на (forum_chat_id, message_thread_id)

**Функции для работы:**
- `create_support_ticket()` - создание нового тикета
- `get_ticket()` - получение тикета по ID
- `get_user_tickets()` - получение всех тикетов пользователя
- `set_ticket_status()` - изменение статуса тикета
- `delete_ticket()` - удаление тикета

---

### 9. `support_messages` - Сообщения в тикетах поддержки

Таблица для хранения сообщений в тикетах поддержки.

| Поле | Тип | Описание |
|------|-----|----------|
| `message_id` | INTEGER PRIMARY KEY | Уникальный ID сообщения (автоинкремент) |
| `ticket_id` | INTEGER | ID тикета (внешний ключ) |
| `sender` | TEXT | Отправитель ('user' или 'support') |
| `content` | TEXT | Содержимое сообщения |
| `media` | TEXT | Медиа-контент (JSON) |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Функции для работы:**
- `add_support_message()` - добавление сообщения в тикет
- `get_ticket_messages()` - получение всех сообщений тикета

---

### 10. `bot_settings` - Настройки бота

Таблица для хранения настроек бота в формате ключ-значение.

| Поле | Тип | Описание |
|------|-----|----------|
| `key` | TEXT PRIMARY KEY | Ключ настройки (уникальный) |
| `value` | TEXT | Значение настройки |

**Основные настройки:**
- `panel_login` / `panel_password` - логин/пароль панели управления
- `telegram_bot_token` - токен бота
- `admin_telegram_id` / `admin_telegram_ids` - ID администраторов
- `trial_enabled` / `trial_duration_days` - настройки пробного периода
- `enable_referrals` / `referral_percentage` - реферальная система
- `yookassa_shop_id` / `yookassa_secret_key` - настройки ЮKassa
- `cryptobot_token` - токен CryptoBot
- `franchise_enabled` / `franchise_commission_percent` - франшиза
- `captcha_enabled` / `captcha_type` - настройки капчи
- И многое другое...

**Функции для работы:**
- `get_setting()` - получение значения настройки
- `get_all_settings()` - получение всех настроек
- `update_setting()` - обновление настройки

---

### 11. `button_configs` - Конфигурация кнопок

Таблица для хранения кастомных кнопок меню бота.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID кнопки (автоинкремент) |
| `menu_type` | TEXT | Тип меню ('main', 'admin' и т.д.) |
| `button_id` | TEXT | Идентификатор кнопки |
| `text` | TEXT | Текст кнопки |
| `callback_data` | TEXT | Callback данные |
| `url` | TEXT | URL (для inline кнопок) |
| `row_position` | INTEGER | Позиция ряда (по умолчанию 0) |
| `column_position` | INTEGER | Позиция колонки (по умолчанию 0) |
| `button_width` | INTEGER | Ширина кнопки (по умолчанию 1) |
| `is_active` | INTEGER | Активна ли кнопка (по умолчанию 1) |
| `sort_order` | INTEGER | Порядок сортировки (по умолчанию 0) |
| `metadata` | TEXT | Дополнительная информация (JSON) |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `updated_at` | TIMESTAMP | Дата обновления (по умолчанию текущее время) |

**Уникальный ключ:** (menu_type, button_id)

**Функции для работы:**
- `get_button_configs()` - получение конфигурации кнопок для меню
- `create_button_config()` - создание новой кнопки
- `update_button_config()` - обновление кнопки
- `delete_button_config()` - удаление кнопки

---

### 12. `key_usage_monitor` - Мониторинг использования ключей

Таблица для отслеживания использования VPN-ключей пользователями.

| Поле | Тип | Описание |
|------|-----|----------|
| `key_id` | INTEGER PRIMARY KEY | ID ключа |
| `user_id` | INTEGER | ID пользователя |
| `first_seen_usage_at` | TIMESTAMP | Время первого использования |
| `last_reminder_at` | TIMESTAMP | Время последнего напоминания |
| `last_checked_at` | TIMESTAMP | Время последней проверки |
| `last_devices_count` | INTEGER | Количество устройств (по умолчанию 0) |
| `last_traffic_bytes` | INTEGER | Последний объем трафика (по умолчанию 0) |
| `overlimit_notified_count` | INTEGER | Количество уведомлений о превышении (по умолчанию 0) |
| `overlimit_notified_at` | TIMESTAMP | Время уведомления о превышении |

**Индексы:**
- `idx_key_usage_monitor_first_seen` - индекс на first_seen_usage_at

**Функции для работы:**
- `get_key_usage_monitor()` - получение информации о мониторинге ключа
- `update_key_usage_monitor()` - обновление информации о мониторинге

---

### 13. `host_speedtests` - Тесты скорости хостов

Таблица для хранения результатов тестов скорости серверов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID записи (автоинкремент) |
| `host_name` | TEXT | Имя хоста |
| `method` | TEXT | Метод тестирования |
| `ping_ms` | REAL | Пинг в миллисекундах |
| `jitter_ms` | REAL | Джиттер в миллисекундах |
| `download_mbps` | REAL | Скорость скачивания в Мбит/с |
| `upload_mbps` | REAL | Скорость загрузки в Мбит/с |
| `server_name` | TEXT | Название сервера |
| `server_id` | TEXT | ID сервера |
| `ok` | INTEGER | Успешность теста (по умолчанию 1) |
| `error` | TEXT | Сообщение об ошибке |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Индексы:**
- `idx_host_speedtests_host_time` - индекс на (host_name, created_at DESC)

**Функции для работы:**
- `insert_host_speedtest()` - добавление результата теста
- `get_speedtests()` - получение результатов тестов для хоста
- `get_latest_speedtest()` - получение последнего теста для хоста

---

### 14. `resource_metrics` - Метрики ресурсов

Таблица для хранения метрик использования ресурсов серверов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID записи (автоинкремент) |
| `scope` | TEXT | Область ('local', 'host', 'target') |
| `object_name` | TEXT | Имя объекта ('panel', имя хоста, имя цели) |
| `cpu_percent` | REAL | Загрузка CPU в процентах |
| `mem_percent` | REAL | Использование памяти в процентах |
| `disk_percent` | REAL | Использование диска в процентах |
| `load1` | REAL | Средняя нагрузка за 1 минуту |
| `net_bytes_sent` | INTEGER | Отправлено байт по сети |
| `net_bytes_recv` | INTEGER | Получено байт по сети |
| `raw_json` | TEXT | Сырые данные в JSON |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Индексы:**
- `idx_resource_metrics_scope_time` - индекс на (scope, object_name, created_at DESC)

**Функции для работы:**
- `insert_resource_metric()` - добавление метрики
- `get_latest_resource_metric()` - получение последней метрики
- `get_metrics_series()` - получение серии метрик

---

### 15. `speedtest_ssh_targets` - SSH цели для тестирования скорости

Таблица для хранения SSH целей, с которых выполняются тесты скорости.

| Поле | Тип | Описание |
|------|-----|----------|
| `target_name` | TEXT PRIMARY KEY | Имя цели (уникальное) |
| `ssh_host` | TEXT | SSH хост |
| `ssh_port` | INTEGER | SSH порт (по умолчанию 22) |
| `ssh_user` | TEXT | SSH пользователь |
| `ssh_password` | TEXT | SSH пароль |
| `ssh_key_path` | TEXT | Путь к SSH ключу |
| `description` | TEXT | Описание |
| `is_active` | INTEGER | Активна ли цель (по умолчанию 1) |
| `sort_order` | INTEGER | Порядок сортировки (по умолчанию 0) |
| `metadata` | TEXT | Дополнительная информация (JSON) |

**Функции для работы:**
- `get_all_ssh_targets()` - получение всех SSH целей
- `get_ssh_target()` - получение цели по имени
- `create_ssh_target()` - создание новой цели
- `update_ssh_target_fields()` - обновление полей цели
- `delete_ssh_target()` - удаление цели

---

### 16. `managed_bots` - Франшизные боты

Таблица для хранения франшизных (клонированных) ботов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID бота (автоинкремент) |
| `telegram_bot_user_id` | INTEGER UNIQUE | Telegram ID бота |
| `username` | TEXT | Имя пользователя бота |
| `token` | TEXT | Токен бота |
| `owner_telegram_id` | INTEGER | Telegram ID владельца |
| `referrer_bot_id` | INTEGER | ID пригласившего бота (по умолчанию 0) |
| `is_active` | INTEGER | Активен ли бот (по умолчанию 1) |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Функции для работы:**
- `create_managed_bot()` - создание франшизного бота
- `get_managed_bot()` - получение бота по ID
- `get_managed_bot_by_telegram_id()` - получение бота по Telegram ID

---

### 17. `factory_user_activity` - Активность пользователей в франшизных ботах

Таблица для отслеживания активности пользователей в франшизных ботах.

| Поле | Тип | Описание |
|------|-----|----------|
| `bot_id` | INTEGER | ID бота |
| `user_id` | INTEGER | ID пользователя |
| `first_seen` | TIMESTAMP | Первое появление (по умолчанию текущее время) |
| `last_seen` | TIMESTAMP | Последнее появление (по умолчанию текущее время) |
| `messages_count` | INTEGER | Количество сообщений (по умолчанию 0) |

**Первичный ключ:** (bot_id, user_id)

**Индексы:**
- `idx_factory_activity_bot` - индекс на bot_id

---

### 18. `partner_commissions` - Комиссии партнеров

Таблица для хранения комиссий партнеров от продаж в их франшизных ботах.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID записи (автоинкремент) |
| `bot_id` | INTEGER | ID бота |
| `payment_id` | TEXT | ID платежа |
| `user_id` | INTEGER | ID пользователя |
| `amount_rub` | REAL | Сумма платежа в рублях |
| `commission_percent` | REAL | Процент комиссии |
| `commission_rub` | REAL | Размер комиссии в рублях |
| `payment_method` | TEXT | Метод оплаты |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Уникальный ключ:** (bot_id, payment_id)

**Индексы:**
- `idx_partner_commissions_bot` - индекс на (bot_id, created_at DESC)

---

### 19. `partner_withdraw_requests` - Заявки на вывод средств партнеров

Таблица для хранения заявок партнеров на вывод заработанных средств.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID заявки (автоинкремент) |
| `bot_id` | INTEGER | ID бота |
| `owner_telegram_id` | INTEGER | Telegram ID владельца |
| `amount_rub` | REAL | Сумма к выводу в рублях |
| `status` | TEXT | Статус заявки (по умолчанию 'pending') |
| `comment` | TEXT | Комментарий |
| `bank` | TEXT | Название банка |
| `requisite_type` | TEXT | Тип реквизита ('card', 'phone' и т.д.) |
| `requisite_value` | TEXT | Значение реквизита |
| `requisite_id` | INTEGER | ID реквизита |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Индексы:**
- `idx_partner_withdraw_bot` - индекс на (bot_id, created_at DESC)

---

### 20. `partner_payout_requisites` - Реквизиты партнеров для выплат

Таблица для хранения платежных реквизитов партнеров.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID реквизита (автоинкремент) |
| `bot_id` | INTEGER | ID бота |
| `owner_telegram_id` | INTEGER | Telegram ID владельца |
| `bank` | TEXT | Название банка |
| `requisite_type` | TEXT | Тип реквизита ('card', 'phone' и т.д.) |
| `requisite_value` | TEXT | Значение реквизита (номер карты, телефон) |
| `is_default` | INTEGER | Используется ли по умолчанию (по умолчанию 0) |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |

**Индексы:**
- `idx_partner_requisites_owner` - индекс на (bot_id, owner_telegram_id, created_at DESC)

**Функции для работы:**
- `add_partner_requisite()` - добавление реквизита
- `get_default_partner_requisite()` - получение реквизита по умолчанию
- `set_default_partner_requisite()` - установка реквизита по умолчанию
- `delete_partner_requisite()` - удаление реквизита

---

### 21. `captcha_challenges` - Капча вызовы

Таблица для хранения капча-вызовов для пользователей.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | INTEGER PRIMARY KEY | ID вызова (автоинкремент) |
| `user_id` | INTEGER | ID пользователя |
| `challenge_type` | TEXT | Тип капчи ('math', 'button' и т.д.) |
| `question` | TEXT | Вопрос капчи |
| `correct_answer` | TEXT | Правильный ответ |
| `attempts` | INTEGER | Количество попыток (по умолчанию 0) |
| `max_attempts` | INTEGER | Максимум попыток (по умолчанию 3) |
| `passed` | INTEGER | Пройдена ли капча (по умолчанию 0) |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `expired_at` | TIMESTAMP | Время истечения |

**Индексы:**
- `idx_captcha_challenges_user_time` - индекс на (user_id, created_at DESC)

---

### 22. `user_captcha_status` - Статус капчи пользователей

Таблица для хранения статуса прохождения капчи пользователями.

| Поле | Тип | Описание |
|------|-----|----------|
| `user_id` | INTEGER PRIMARY KEY | ID пользователя |
| `passed_at` | TIMESTAMP | Время прохождения капчи |
| `challenge_id` | INTEGER | ID вызова капчи (внешний ключ) |

---

### 23. `gift_tokens` - Подарочные токены

Таблица для хранения подарочных токенов (промокодов на подарки).

| Поле | Тип | Описание |
|------|-----|----------|
| `token` | TEXT PRIMARY KEY | Токен (уникальный) |
| `host_name` | TEXT | Имя хоста |
| `days` | INTEGER | Количество дней |
| `activation_limit` | INTEGER | Лимит активаций (по умолчанию 1) |
| `activations_used` | INTEGER | Использовано активаций (по умолчанию 0) |
| `expires_at` | TIMESTAMP | Дата истечения |
| `created_by` | INTEGER | ID создателя |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `last_claimed_at` | TIMESTAMP | Дата последней активации |
| `comment` | TEXT | Комментарий |

**Индексы:**
- `idx_gift_tokens_host` - индекс на host_name
- `idx_gift_tokens_expires` - индекс на expires_at

---

### 24. `gift_token_claims` - Активации подарочных токенов

Таблица для отслеживания активаций подарочных токенов.

| Поле | Тип | Описание |
|------|-----|----------|
| `claim_id` | INTEGER PRIMARY KEY | ID активации (автоинкремент) |
| `token` | TEXT | Токен (внешний ключ) |
| `user_id` | INTEGER | ID пользователя |
| `key_id` | INTEGER | ID созданного ключа |
| `claimed_at` | TIMESTAMP | Дата активации (по умолчанию текущее время) |

**Индексы:**
- `idx_gift_token_claims_token` - индекс на token
- `idx_gift_token_claims_user` - индекс на user_id

---

### 25. `user_gifts` - Пользовательские подарки

Таблица для хранения подарков от пользователей другим пользователям.

| Поле | Тип | Описание |
|------|-----|----------|
| `gift_id` | INTEGER PRIMARY KEY | ID подарка (автоинкремент) |
| `from_user_id` | INTEGER | ID дарителя |
| `key_id` | INTEGER | ID ключа |
| `host_name` | TEXT | Имя хоста |
| `plan_id` | INTEGER | ID плана |
| `gift_code` | TEXT UNIQUE | Код подарка (уникальный) |
| `is_activated` | BOOLEAN | Активирован ли подарок (по умолчанию 0) |
| `activated_by_user_id` | INTEGER | ID активировавшего пользователя |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `activated_at` | TIMESTAMP | Дата активации |
| `expires_at` | TIMESTAMP | Дата истечения |

**Индексы:**
- `idx_user_gifts_from_user` - индекс на from_user_id
- `idx_user_gifts_gift_code` - индекс на gift_code
- `idx_user_gifts_is_activated` - индекс на is_activated

**Функции для работы:**
- `create_user_gift()` - создание подарка
- `get_user_gift()` - получение подарка по ID
- `get_gift_by_code()` - получение подарка по коду
- `activate_user_gift()` - активация подарка

---

### 26. `promo_codes` - Промокоды

Таблица для хранения промокодов на скидки.

| Поле | Тип | Описание |
|------|-----|----------|
| `code` | TEXT PRIMARY KEY | Код промокода (уникальный) |
| `discount_percent` | REAL | Процент скидки |
| `discount_amount` | REAL | Фиксированная сумма скидки |
| `usage_limit_total` | INTEGER | Общий лимит использований |
| `usage_limit_per_user` | INTEGER | Лимит использований на пользователя |
| `used_total` | INTEGER | Общее количество использований (по умолчанию 0) |
| `valid_from` | TIMESTAMP | Дата начала действия |
| `valid_until` | TIMESTAMP | Дата окончания действия |
| `is_active` | INTEGER | Активен ли промокод (по умолчанию 1) |
| `created_by` | INTEGER | ID создателя |
| `created_at` | TIMESTAMP | Дата создания (по умолчанию текущее время) |
| `description` | TEXT | Описание промокода |

**Индексы:**
- `idx_promo_codes_valid` - индекс на valid_until

---

### 27. `promo_code_usages` - Использования промокодов

Таблица для отслеживания использований промокодов пользователями.

| Поле | Тип | Описание |
|------|-----|----------|
| `usage_id` | INTEGER PRIMARY KEY | ID использования (автоинкремент) |
| `code` | TEXT | Код промокода (внешний ключ) |
| `user_id` | INTEGER | ID пользователя |
| `applied_amount` | REAL | Примененная сумма скидки |
| `order_id` | TEXT | ID заказа |
| `used_at` | TIMESTAMP | Дата использования (по умолчанию текущее время) |

**Индексы:**
- `idx_promo_code_usages_code` - индекс на code
- `idx_promo_code_usages_user` - индекс на user_id

---

## Особенности работы с базой данных

### Подключение к базе данных

База данных использует SQLite и подключается через модуль `sqlite3`. Путь к файлу БД определяется автоматически в следующем порядке:
1. `/app/project/users.db` (для Docker)
2. `users-20251005-173430.db` (бэкап)
3. `users.db` (локальная БД)

### Миграции

Миграции выполняются автоматически при инициализации базы данных через функцию `run_migration()`. Система поддерживает:
- Добавление новых колонок в существующие таблицы
- Создание недостающих таблиц
- Перестройку таблиц при изменении схемы
- Обновление индексов

### Нормализация данных

Система автоматически нормализует некоторые данные:
- Email адреса приводятся к нижнему регистру
- Имена хостов очищаются от невидимых символов
- Даты конвертируются в единый формат

### Транзакции

Все операции с базой данных используют транзакции для обеспечения целостности данных. При ошибках выполняется автоматический откат (rollback).

### Индексы

База данных использует индексы для оптимизации запросов:
- Уникальные индексы на email, key_email в таблице vpn_keys
- Индексы на внешние ключи
- Индексы на поля, используемые в WHERE и JOIN

---

## API функции для работы с базой данных

Основные группы функций:

### Пользователи
- `register_user_if_not_exists()`, `get_user()`, `get_all_users()`
- `ban_user()`, `unban_user()`, `set_terms_agreed()`
- `get_balance()`, `set_balance()`, `add_to_balance()`

### VPN Ключи
- `add_new_key()`, `get_user_keys()`, `get_key_by_id()`
- `update_key_fields()`, `delete_key_by_id()`

### Транзакции
- `create_transaction()`, `create_pending_transaction()`
- `find_and_complete_pending_transaction()`

### Хосты и планы
- `create_host()`, `get_all_hosts()`, `update_host_url()`
- `create_plan()`, `get_active_plans_for_host()`

### Поддержка
- `create_support_ticket()`, `get_user_tickets()`
- `add_support_message()`, `set_ticket_status()`

### Реферальная система
- `get_referrals_for_user()`, `add_to_referral_balance()`
- `get_referral_top_rich()`, `get_referral_rank_and_count()`

### Франшиза
- `create_managed_bot()`, `get_partner_cabinet()`
- `create_withdraw_request()`

### Подарки и промокоды
- `create_user_gift()`, `activate_user_gift()`
- `create_promo_code()`, `validate_promo_code()`

---

## Резервное копирование

Система поддерживает автоматическое резервное копирование базы данных через модуль `backup_manager.py`. Настройки резервного копирования хранятся в таблице bot_settings:
- `backup_interval_days` - интервал резервного копирования

---

## Безопасность

1. **SQL-инъекции** предотвращаются использованием параметризованных запросов во всех операциях с базой данных.
2. **Транзакции** обеспечивают целостность данных при одновременном доступе и параллельных операциях.
3. **Контроль доступа** осуществляется на уровне бота - каждый пользователь имеет доступ только к своим данным через Telegram API.

---

## Мониторинг и статистика

База данных содержит таблицы для мониторинга:
- `resource_metrics` - метрики использования ресурсов серверов
- `host_speedtests` - результаты тестов скорости
- `key_usage_monitor` - мониторинг использования ключей

Статистические функции:
- `get_admin_stats()` - общая статистика для админ-панели
- `get_daily_stats_for_charts()` - статистика по дням для графиков
- `get_recent_transactions()` - последние транзакции

---

## Дополнительная информация

Более подробную информацию о работе с базой данных можно найти в следующих файлах:
- [database.py](src/shop_bot/data_manager/database.py) - основной модуль работы с БД
- [backup_manager.py](src/shop_bot/data_manager/backup_manager.py) - резервное копирование
- [scheduler.py](src/shop_bot/data_manager/scheduler.py) - планировщик задач

---

*Документация актуальна на 14.02.2026*
