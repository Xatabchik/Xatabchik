# Telegram-хендлеры и клавиатуры

Пользовательский роутер: `bot/handlers.py::get_user_router()`.  
Админский: `bot/admin_handlers.py::get_admin_router()`.  
Клавиатуры: `bot/keyboards.py`.  
Тексты карточек: `config.py`.

Полный список функций — [docs/FUNCTIONS_CATALOG.md](docs/FUNCTIONS_CATALOG.md).

---

## Подключение

`BotController.start` (и каждый клон франшизы) делает:

```
Dispatcher
  ├─ BanMiddleware
  ├─ FactoryStatsMiddleware
  ├─ get_user_router()
  ├─ get_admin_router()          # только root-бот
  ├─ get_owner_cabinet_router()  # только клон
  └─ routers включённых модулей
```

Пользовательские хендлеры закрыты декоратором `registration_required` (кроме `/start` и капчи/онбординга).

---

## Пользовательский бот — домены

### Онбординг и капча

`start_handler` разбирает deep-link:

| Префикс | Действие |
|---------|----------|
| `auth_<token>` | `confirm_webapp_auth_request` — вход в Mini App |
| `gift_<code>` | Активация подарка |
| `ref_<id>` | Привязка реферера (`link_referrer_if_eligible`) |
| `utm_<slug>` | `log_utm_visit` / `set_user_utm_slug_if_absent` |

Дальше: капча (`captcha_utils`) → подписка на канал (`check_subscription_handler`) → согласие (`Onboarding`) → `process_successful_onboarding` → `show_main_menu`. Реферальный стартовый бонус: `_maybe_pay_referral_start_bonus`.

### Меню, профиль, ключи

`show_main_menu` / `create_dynamic_main_menu_keyboard` — кнопки из `button_configs` с fallback на статику.

Профиль: статистика, VPN-статус (`config.get_profile_text`), тумблеры уведомлений и автопродления.

Ключи: `manage_keys`, пагинация, поиск (`search_user_keys_by_email`), карточка (`get_key_info_text` + `create_key_info_keyboard`), QR, HWID-устройства, переименование, смена сервера, автопродление одного ключа.

How-to: `howto_vless_*` по платформам.

### Покупка, продление, триал, подарок

Выбор хоста → тариф → email (чеки) → промо → `show_payment_options` → `pay_*`.

Триал: `get_trial` / `select_host_trial_*`, бонус рефереру `grant_referrer_day_bonus_for_trial`.

Подарок: покупка как обычный ключ с `action=gift`, ссылки `_build_gift_links`, активация `_activate_gift_directly`. Лендинг Mini App `/gift/<code>` стыкуется через `auth_pending_actions`.

### Докупка трафика / LTE / сброс / top-up

Отдельные FSM (`TrafficGbTopUp`, `LteGbTopUp`, `MainPoolReset`, `TopUpProcess`) и свои `create_*_payment_method_keyboard`. После оплаты тот же `process_successful_payment` с другим `action` в metadata.

### Рефералка

`show_referral_program`, топ, перевод на основной баланс, вывод (`create_referral_withdrawal_request`), справочник реквизитов (`referral_payout_methods`). Ссылка: `https://t.me/<bot>?start=ref_<id>` и веб `/ref/<id>`.

### Поддержка в основном боте

Свой FSM тикетов (параллелен support-боту): создание, список, ответ, закрытие. Если настроен внешний контакт — `support_external`.

### Франшиза для партнёра

В **root-боте**: `factory_create_bot` (токен нового клона), `partner_cabinet`, реквизиты, вывод.  
В **клоне**: `factory_bot/handlers.py` — статистика и «удалить моего бота». Создание клонов из клона невозможно.

---

## Админ-бот — домены

Фильтр `IsAdminFilter` + `AdminAccessMiddleware`. Callback'и часто обёрнуты в `callback_safety.fast_callback_answer` / `catch_callback_errors`.

| Меню | Callback / FSM | Действия |
|------|----------------|----------|
| Главное / система / настройки | `admin_menu`, `admin_system_menu`, `admin_settings_menu` | Навигация |
| Модули | `admin_modules`, `admin_module_enable/disable` | `module_loader` |
| Конструктор кнопок | `btnc_*`, FSM `ButtonConstructor` | CRUD `button_configs` |
| Платежки | `admin_payments_*`, FSM `AdminPayments` | Флаги и секреты |
| Рефералка | `admin_referral_*` | % / фикс / min withdraw / days bonus |
| Франшиза | `admin_franchise_*` | Флаг + `start_all`/`stop_all` |
| Хосты | `admin_hosts_*` | CRUD, SSH, Remnawave, сквады |
| Тарифы и пакеты | `admin_plans_*`, `admin_pkg_*` | CRUD планов и GB/LTE пакетов |
| Триал / LTE / уведомления / капча / автопродление | отдельные меню | `update_setting` |
| Промо | `admin_promo_*` | CRUD через `rw_repo` |
| Пользователи | `admin_users`, поиск, ban, баланс, ключи пользователя | `database` + панель те же сущности |
| Ключи хоста | `admin_host_keys`, `admin_key_*` | extend / delete / email |
| Выдача ключа | FSM `AdminGiftKey` | `create_or_update_key_on_host` |
| Рассылка | FSM `Broadcast` | `_send_broadcast_to` + reachability |
| Speedtest | `admin_speedtest*` | `speedtest_runner` |
| Мониторинг | `admin_monitor` | `resource_monitor` |
| Бэкап | `admin_backup_db`, `admin_restore_db` | `backup_manager` |
| Админы | `admin_admins_menu` | список `admin_telegram_ids` |

---

## Клавиатуры (`keyboards.py`)

Именование: `create_<экран>_keyboard`. Динамические обёртки `create_dynamic_*` читают БД и падают на статику, если конструктор пуст.

Важные семейства:

- меню / профиль / about / support / тикеты;
- хост → тариф → способ оплаты (отдельные клавиатуры для purchase / topup / traffic / LTE / reset);
- ссылка «перейти к оплате» на каждого провайдера;
- карточка ключа, подарки, капча;
- все админ-меню из таблицы выше.

`create_payment_method_keyboard` **сам** читает `get_setting` и почти игнорирует переданный dict — источник истины для витрины покупки.

---

## Что не подключено

- `bot/photo_helper.py` и `bot/image_bot.py` в текущем runtime не импортируются хендлерами. Тексты уходят обычным `answer`/`edit`.
- `modules/cryptobot_api.py` не используется; бот и Mini App ходят в функции из `handlers.py`.
