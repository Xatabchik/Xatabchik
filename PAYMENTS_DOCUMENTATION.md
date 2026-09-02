# Платежи

Все способы оплаты, создание инвойса, вебхуки и выдача услуги. Настройки полей — [BOT_SETTINGS_GUIDE.md](BOT_SETTINGS_GUIDE.md). Функции по файлам — [docs/FUNCTIONS_CATALOG.md](docs/FUNCTIONS_CATALOG.md).

---

## Общая модель

1. Создаётся запись `pending_transactions` (`rw_repo.create_payload_pending`).
2. В `metadata` JSON: тип операции (`new` / `extend` / `gift` / `topup` / `traffic` / `lte` / `reset`), `plan_id`, `host_name`, `key_id`, промо, `factory_bot_id`.
3. Провайдер возвращает URL (или invoice id для Stars).
4. Подтверждение приходит вебхуком **или** кнопкой «Проверить» **или** `successful_payment`.
5. Идемпотентность: `processed_payments` + `claim_processed_payment` / `find_and_complete_pending_transaction`.
6. Выдача услуги только в `bot/handlers.py::process_successful_payment`.

Оплата с **баланса** и **реферального баланса** минует провайдера: сразу deduct + `process_successful_payment`.

---

## Провайдеры

| Код в metadata | Модуль / SDK | Вебхук Flask | Создание инвойса |
|----------------|--------------|--------------|------------------|
| `yookassa` | `yookassa` SDK | `POST /yookassa-webhook` | бот `pay_yookassa`, Mini App `api_create_payment` |
| `platega` | `modules/platega_api.py` | `GET/POST /platega-webhook` | бот (inline), Mini App `PlategaAPI` |
| `rollypay` | `modules/rollypay_api.py` | `POST /rollypay-webhook` | бот, Mini App, Flask |
| `cryptobot` | Crypto Pay API | `POST /cryptobot-webhook` | `handlers.create_cryptobot_api_invoice` (модуль `cryptobot_api.py` не импортируется) |
| `heleket` | `modules/heleket_api.py` | `POST /heleket-webhook` | Mini App — модуль; бот — `_create_heleket_payment_request` |
| `yoomoney` | HTTP + secret | `POST /yoomoney-webhook` | ссылка на кошелёк; OAuth: `/yoomoney/connect`, `/callback`, `/check` |
| `tonconnect` | TON API | `POST /ton-webhook` | бот `pay_tonconnect` |
| `stars` | Telegram Payments | нет (бот) | `successful_payment_handler` |
| `balance` / `referral_balance` | БД | нет | `deduct_from_*` |

Включение метода: заполненные секреты в `bot_settings` + для части провайдеров явный флаг (`stars_enabled`, `yoomoney_enabled`). Live-список собирает `handlers._get_payment_methods()` и `keyboards.create_payment_method_keyboard`.

`BotController.start` пишет кэш `handlers.PAYMENT_METHODS` **без platega**. Клавиатуры top-up / LTE / reset на стартовом кэше могут не показать Platega до перезапуска бота, если смотрят в этот dict. Экран покупки ключа перечитывает настройки.

---

## Модули и функции

### Platega — `platega_api.py`

| Функция | Где | Зачем |
|---------|-----|--------|
| `PlategaAPI.create_payment` | Mini App | Редирект + `transaction_id` |
| `PlategaAPI.get_transaction` | Mini App verify | Асинхронная сверка |
| `get_transaction_sync` | Flask webhook | Сверка в синхронном потоке Flask (телу вебхука не доверяем) |

### Platega — `platega_fulfillment.py`

Общий финал для вебхука и Mini App:

- `is_platega_payment_method` — метод Platega / Platega Crypto;
- `normalize_platega_status` → `confirmed` / `canceled` / `pending`;
- `extract_platega_amount` — сумма из разных форм payload;
- `complete_pending_platega_payment` — атомарно закрыть pending;
- `mark_pending_canceled` — отмена, если провайдер подтвердил cancel.

### RollyPay — `rollypay_api.py`

Базовый URL зафиксирован: `https://api.rollypay.io/api/v1` (нельзя подменить из админки).

| Функция | Зачем |
|---------|--------|
| `RollyPayAPI.create_payment` | `(pay_url, provider_payment_id)` |
| `RollyPayAPI.get_payment` / `get_payment_sync` | Сверка статуса |
| `verify_webhook_signature` | HMAC-SHA256 `{unix_ts}.{body}`, заголовок `X-Signature`, окно 300 с |

Настройки: `rollypay_api_key`, `rollypay_signing_secret`, `rollypay_terminal_id`, `rollypay_payment_method`.

### Heleket / CryptoBot

- Heleket: подпись запроса, `url_callback` = `{domain}/heleket-webhook`, `order_id` = внутренний `payment_id`.
- CryptoBot: `cryptobot_token`, вебхук `{domain}/cryptobot-webhook`. Mini App импортирует функцию из `bot/handlers.py`, не из `modules/cryptobot_api.py`.

### YooKassa

`yookassa.Configuration` выставляется в `BotController.start`. Вебхук проверяет платёж через API магазина, затем `_dispatch_payment_processing`.

### Telegram Stars

Флаг `stars_enabled` и курс `stars_per_rub > 0`. Инвойс шлётся ботом; подтверждение — апдейт `successful_payment`, не Flask.

---

## Fulfillment: `process_successful_payment`

Разбирает `metadata.action` и:

- создаёт или продлевает ключ на хосте (`remnawave_api.create_or_update_key_on_host`);
- гасит pending, пишет `transactions`;
- обновляет `total_spent` / месяцы;
- начисляет рефералку и `accrue_partner_commission`;
- применяет промо (`redeem_promo_code`);
- для top-up / LTE / reset меняет баланс или `key_lte_state` / `traffic_boost_bytes`;
- уведомляет админов (`notify_admin_of_purchase`) и пользователя.

При ошибке выдачи ключа: `_handle_key_creation_failure` / `_abort_key_fulfillment` — откат, чтобы деньги не «исчезли» без услуги (см. также `refund_payment_once`).

---

## Безопасность вебхуков

- Секреты и HMAC / shop API — не доверять сумме и статусу из тела, сверять у провайдера.
- `claim_processed_payment` защищает от повторной выдачи.
- Platega: сумма должна покрывать заказ (`_platega_amount_covers_order` в Flask).
- RollyPay: невалидный `X-Signature` → отказ.
- YooMoney OAuth: `state` проверяется (см. `tests/test_yoomoney_oauth_state.py`).

Тесты: `tests/test_payment_webhooks_security.py`, `test_platega_webapp_verify.py`, `test_rollypay.py`, `test_create_payment.py`, `test_check_payment_authorization.py`, `test_payment_balance_rollback.py`.
