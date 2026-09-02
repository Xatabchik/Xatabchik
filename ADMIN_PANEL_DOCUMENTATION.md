# Админ-панель (Flask)

Приложение: `src/shop_bot/webhook_server/app.py`.  
Фабрика: `create_webhook_app(bot_controller_instance)`.

Запускается потоком из `__main__.py` (`SHOPBOT_FLASK_HOST` / `SHOPBOT_FLASK_PORT`, по умолчанию `127.0.0.1:1488`). Снаружи обычно Nginx + TLS на 443/8443.

Шаблоны: `webhook_server/templates/`. Тема Tabler: `static/vendor/tabler/`.

---

## Обвязка приложения

При создании app:

- CSRF (`flask-wtf`), cookie-сессия;
- rate-limit логина (`_rate_limit_login`);
- `login_required` на операционных роутах;
- `module_loader.set_flask_app` — плагины;
- context processor: статус ботов, число открытых тикетов, флаги франшизы;
- синглтон `_support_bot_controller`.

Хелперы, которые связывают панель с ботом:

| Функция | Зачем |
|---------|--------|
| `_dispatch_payment_processing` | Выполнить `process_successful_payment` на loop основного бота |
| `_dispatch_bot_notification` | Пуш пользователю из панели |
| `_handle_promo_after_payment` | Redeem / деактивация промо после оплаты |
| `_apply_franchise_runtime` | `start_all` / `stop_all` клонов без рестарта контейнера |
| `run_bulk_ticket_followup` | Массовое закрытие тикетов с уведомлениями |

`apply_app_fix.py` — ручной regex-патч списков настроек, **не** часть runtime.

---

## Маршруты по доменам

### Сессия

| URL | Методы | Назначение |
|-----|--------|------------|
| `/login` | GET, POST | Логин + опционально TOTP |
| `/logout` | POST | Выход |
| `/brand-title` | POST | Смена бренда шапки |

### Дашборд и аналитика

`/`, `/dashboard`, partials статистики и транзакций, `/dashboard/charts.json`, `/dashboard/run-speedtests`.

`/analytics/*` — транзакции (+ CSV), тарифы, методы оплаты, рефералы, купоны CRUD, UTM, экономика серверов, прогноз, плановые рассылки.

`/referral-program/*` — настройки рефералки, топ, заявки на вывод (`.../requests/<id>/status`).

`/statistics` — сводная страница.

### Пользователи и ключи

`/users` и partials (таблица, ключи, транзакции).  
`/users/search.json`, `/admin/search.json` — глобальный поиск.  
Бан / разбан / удаление / revoke ключей на панели.  
Назначение реферала: `POST /users/<referrer_id>/referrals/assign`.

`/admin/keys/*` — список всех ключей, создание, продление, bulk-extend, устройства, комментарий, sweep просроченных.

### Хосты, сквады, тарифы

`POST /add-host`, `/delete-host/<name>`, `/rename-host`, `/update-host-url`, `/update-host-remnawave`, `/update-host-subscription`, `/update-host-squad-selection`.

Сквады: `/add-host-squad`, `/toggle-host-squad/<id>`, `/delete-host-squad/<id>`, `/add-remnawave-squad`, `/delete-remnawave-squad/<id>`, `POST /settings/remnawave`.

Планы: `/add-plan`, `/update-plan/<id>`, `/toggle-plan/<id>`, `/delete-plan/<id>`, пакеты трафика `/add-traffic-package` и CRUD `/...-traffic-package/<id>`.

### Support

`/support`, `/support/<id>`, messages JSON, delete, bulk-close/delete, `/ticket_files`, `/support/ticket-file/<message_id>`.

### Настройки и сервисы

`GET/POST /settings` — вся `bot_settings`.  
SMTP test, webapp nginx (`/settings/webapp/*`).  
Мониторинг `/monitor` + JSON series.  
SSH-цели и speedtest `/admin/ssh-targets/*`, `/admin/hosts/<name>/speedtest/*`.  
Бэкап `/admin/db/backup`, `/admin/db/restore`.  
Конструктор кнопок `/button-constructor` + `/api/button-configs*`.

### Боты

`/start-bot`, `/stop-bot`, `/start-support-bot`, `/stop-support-bot`, `/start-both-bots`, `/stop-both-bots`, `/restart-both-bots`.

### Модули

`/modules/`, enable/disable/delete, settings, upload ZIP, proxy `/modules/<id>/` и `/<id>/<subpath>` на view плагина.

### Франшиза

`/franchise`, карточка бота, toggle, delete, статус заявки на вывод.

### Вебхуки (без login_required)

`/yookassa-webhook`, `/yoomoney-webhook`, `/platega-webhook`, `/rollypay-webhook`, `/cryptobot-webhook`, `/heleket-webhook`, `/ton-webhook`, `/yoomoney/connect|callback|check`.

См. [PAYMENTS_DOCUMENTATION.md](PAYMENTS_DOCUMENTATION.md).

Отладочные `/test-webhook`, `/debug-all` — не для продакшена без ограничения доступа на уровне Nginx.

---

## Связь с остальным кодом

Панель не выдаёт VPN-ключи сама: после оплаты вызывает тот же `process_successful_payment`, что бот и Mini App. CRUD пользователей/ключей идёт через `remnawave_repository` + при необходимости `remnawave_api` (revoke, устройства, создание с панели).
