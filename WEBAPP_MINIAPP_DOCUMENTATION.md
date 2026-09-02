# Документация: Telegram Mini App (Webapp)

Этот документ описывает устройство перенесённого в проект каталога `src/shop_bot/webapp/` —
самостоятельного Telegram Mini App (веб-кабинета пользователя), который будет интегрирован
в основной проект Xatabchik.

## 1. Общая архитектура

- **Технология**: FastAPI (ASGI-приложение), запускается через `uvicorn`.
- **Точка входа**: `shop_bot.webapp.handlers:app` (объект `app = FastAPI()` в `handlers.py`).
- **Способ запуска в проде** (из предоставленного `docker-compose.yml`):
  ```
  /app/.venv/bin/uvicorn shop_bot.webapp.handlers:app --host 0.0.0.0 --port 8000 --proxy-headers
  ```
  Отдельный контейнер `remnawave-webapp`, тот же образ, что и у основного бота, тот же volume
  (`.:/app/project`), то есть тот же код и та же SQLite БД (`users.db`), что и у бота/админки.
- **Порт**: внутри контейнера 8000, наружу публикуется на хосте как `127.0.0.1:8001`, наружу
  отдаётся через Nginx + Let's Encrypt (см. `install.sh`) по HTTPS на пользовательском домене.
- **Хранилище**: не имеет собственной БД — использует общий `shop_bot.data_manager.database`
  и `shop_bot.data_manager.remnawave_repository`.

## 2. Файловая структура (`src/shop_bot/webapp/`)

```
__init__.py        - пустой, маркер пакета
handlers.py         - вся backend-логика (~5800 строк): роуты FastAPI, HTML-рендеринг, auth, оплата, тикеты
app.html            - главная SPA-страница (шаблон с плейсхолдерами {{ ... }}, рендерится строковой заменой)
login.html          - страница логина/загрузки (для неавторизованных пользователей)
install.sh          - bash-скрипт первичной настройки Nginx + Certbot (SSL) для домена miniapp
module/
    load.html        - экран загрузки/заставка
    theme/
        default.json - пустой `{}` — задел под тему оформления, пока не используется
    ico/
        balance.png          - иконка "Баланс"
        crypto.png           - иконка криптоплатежей
        sbp-kards.png        - иконка СБП/банковских карт
        telegram-sters.png   - иконка Telegram Stars
        xatabvpn-logo.jpg    - ЗАХАРДКОЖЕННЫЙ логотип (нужно заменить на логотип проекта)
```

Раздача статики: `/module/ico` смонтирован через `StaticFiles` прямо на директорию `module/ico`.

## 3. Рендеринг HTML (шаблонизация через строковую замену)

Функция `_process_template_placeholders()` заменяет плейсхолдеры вида `{{ xxx }}` в `app.html`/
`login.html` обычным `str.replace` (никакого Jinja2). Ключевые плейсхолдеры:

- `{{ panel_brand_title }}` — берётся из `webapp_settings["webapp_title"]`, а если пусто —
  из общей настройки бота `get_setting("panel_brand_title")`, иначе `"Xatab VPN"`.
- `{{ webapp_logo }}` — URL/путь логотипа, берётся из `webapp_settings["webapp_logo"]`.
  Если пусто — рисуется `logo_hidden="hidden"` (логотип скрывается, показывается плашка-заглушка).
- `{{ webapp_icon }}` — favicon/apple-touch-icon, из `webapp_settings["webapp_icon"]`.
- `{{ support_bot_username }}` — из `get_setting("support_contact_username")` либо
  `get_setting("support_bot_username")`.
- `{{ tg_fullscreen_css }}` — условный CSS-блок, добавляется только если
  `webapp_settings["tg_fullscreen"]` включён (полноэкранный режим Mini App в Telegram).
- Плюс множество секций-«кусков HTML», которые генерируются backend-функциями и подставляются
  как целые HTML-блоки: `{{ user_profile_card }}`, `{{ key_info_section }}`,
  `{{ profile_keys_list }}`, `{{ setup_keys_list }}`, `{{ renew_keys_dropdown_options }}`,
  `{{ renew_plans_grid }}`, `{{ server_dropdown_options }}`, `{{ server_plans_grid }}`,
  `{{ min_price }}`, `{{ renew_selected_key_display }}`, `{{ user_id }}`.

## 4. Настройки Mini App: `get_webapp_settings`

Функция **есть** в `database.py` (проксируется через `remnawave_repository`). Читает ключи из `bot_settings`:

| Ключ | Тип | Назначение |
|------|-----|------------|
| `webapp_enabled` | bool | Включён ли Mini App |
| `webapp_domain` | str | Домен, на котором развёрнут кабинет |
| `webapp_title` | str | Заголовок (fallback: `panel_brand_title` → `"Xatab VPN"`) |
| `webapp_logo` | str | URL логотипа |
| `webapp_icon` | str | favicon / apple-touch-icon |
| `tg_fullscreen` | bool | Полноэкранный режим в Telegram |

Редактируются в Flask-панели (`GET/POST /settings`) и прогоне nginx (`/settings/webapp/*`).  
Карта роутов Mini App и связь с ботом: [ADMIN_PANEL_DOCUMENTATION.md](ADMIN_PANEL_DOCUMENTATION.md), [BOT_HANDLERS_DOCUMENTATION.md](BOT_HANDLERS_DOCUMENTATION.md), [PAYMENTS_DOCUMENTATION.md](PAYMENTS_DOCUMENTATION.md).

## 5. Аутентификация (Telegram initData + альтернативные способы)

Функция `validate_telegram_data(init_data, bot_token)`:
- Стандартная проверка подписи Telegram WebApp initData (HMAC-SHA256 с секретом
  `HMAC(key="WebAppData", msg=bot_token)`, затем `HMAC(secret, data_check_string)`), сверяется
  с полем `hash` из initData. Стандартный, безопасный подход.

Поддерживаемые способы входа (все реализованы как FastAPI-роуты):
- `GET /` — если передан `token` (query param) — вход по постоянному токену
  (`database.get_user_by_auth_token`). Если нет `user_id`/токена — отдаётся `login.html`.
- `GET /api/auth/request-token` — генерирует временный токен (`database.create_webapp_auth_request`)
  и deep-link `tg://resolve?domain=<bot_username>&start=auth_<token>`. Бот подтверждает через
  `confirm_webapp_auth_request` в `start_handler`.
- `GET /api/auth/check-token/{token}` — поллинг: проверяет, подтверждён ли токен (или уже есть
  постоянный токен в БД).
- `POST /api/auth/token` — вход через `init_data` (проверка через `validate_telegram_data`),
  выдаёт постоянный токен.
- `POST /api/auth/telegram-direct` — вход по данным Telegram с проверкой (см. `tests/test_telegram_direct_auth.py`).
  Клиентский `user_id` сам по себе для выдачи услуги не принимается (`_require_authenticated_user`).
- `POST /api/auth/email/register` / `/login` — альтернативная регистрация по email+паролю
  (создаёт "виртуального" пользователя с telegram_id, начинающимся на `"999"` — это специальный
  префикс для "не привязанных к Telegram" аккаунтов, что подтверждается также в
  `_get_profile_card_html`, где кнопка "Синхронизировать с Telegram" показывается только если
  `str(user_id).startswith("999")`).
- `POST /api/auth/email/reset/request|check|verify` — сброс пароля: код уходит на почту
  (`modules/email_sender.send_activation_code`), если SMTP настроен.
- `POST /api/auth/sync-tg` — привязка ранее созданного email-аккаунта к реальному Telegram.

Постоянные токены — UUID, таблица пользователей (`update_user_auth_token`, `get_user_by_auth_token`).
Email-аккаунты: `create_user_by_email`, `hash_password` / `verify_password`, коды в
`set_email_verification_code` (хеш, не plaintext — `tests/test_password_reset_code_hash.py`).

## 5.1. Единый сценарий подарочных и реферальных ссылок (pending action)

Раньше `/gift/<gift_code>` и `/ref/<referrer_id>` вели пользователя ТОЛЬКО в Telegram
(deep link `?start=gift_<code>` / `?start=ref_<id>`), независимо от того, авторизован ли он
уже, и не давая выбрать вход по email. Теперь обе ссылки используют единый серверный
механизм "pending action":

- **Таблица** `auth_pending_actions` (`database.py`): `token` (криптографически случайный,
  `secrets.token_urlsafe(32)`), `action_type` (`gift`/`referral`), `gift_code`/`referrer_id`,
  `expires_at` (по умолчанию 24 часа), `consumed_at`/`consumed_by_user_id`/`result_status`
  (для идемпотентности повторных вызовов).
- **`GET /gift/{gift_code}`** и **`GET /ref/{referrer_id}`**: если подарок/реферер валидны —
  создают pending action и делают `302` на `/?pending_token=<token>`. Клиенту уходит только
  токен — сам `gift_code`/`referrer_id` остаются на сервере и не могут быть подменены.
  Невалидные случаи (подарок не найден/уже активирован, реферер не существует) — как раньше,
  простая HTML-страница со ссылкой в Telegram, без pending action.
- **`GET /api/webapp/pending-actions/info?pending_token=...`** — безопасная информация для
  UI (`login.html` показывает баннер "Вам доступен подарок" / "Вы переходите по приглашению")
  без раскрытия деталей, позволяющих обойти проверки.
- **`POST /api/webapp/pending-actions/complete`** — вызывается автоматически после входа
  (и `login.html`, и `app.html`). Тело: `{pending_token, token?, init_data?}` — **`user_id` не
  принимается и не может быть передан клиентом**: пользователь определяется только через
  `_resolve_authenticated_user` (существующий persistent auth-токен ИЛИ подписанные Telegram
  `init_data`, та же проверка, что и в `/api/auth/token`). Атомарно "забирает" токен
  (`claim_pending_action`, условный `UPDATE ... WHERE consumed_at IS NULL`) и применяет
  действие ровно один раз — повторные/параллельные вызовы идемпотентны (`already_completed`).
- Бизнес-логика не дублируется: активация подарка идёт через общую `_activate_gift_for_user`
  (используется и здесь, и в уже существующем `POST /api/gift/activate`), привязка реферала —
  через `database.link_referrer_if_eligible` (атомарный `UPDATE ... WHERE referred_by IS NULL`).
  Классический Telegram-флоу (`bot/handlers.py`: `/start gift_<code>`, `/start ref_<id>`) не
  изменён и продолжает работать как раньше.
- `login.html`: если в URL есть `pending_token`, показывает баннер с контекстом ссылки над
  выбором способа входа (Telegram/email — оба равноправны) и передаёт `pending_token` через
  все переходы (включая обратный переход из Telegram) в финальный редирект `/?token=...`.
- `app.html`: снимает `pending_token` из URL при загрузке и, если пользователь уже авторизован
  (что для этой страницы всегда так — она рендерится только для авторизованных), сразу
  вызывает `complete` и показывает тост с результатом — экран входа при этом не показывается.

## 6. Основные разделы интерфейса (SPA, одна страница `app.html`)

На основе сгенерированных HTML-секций и id (`#main-page`, `#purchase-page`, `#renew-page`,
`#setup-page`, `#profile-page`, `#support-page`):

1. **Главная (main-page)** — карточка активного ключа (ближайший по сроку истечения),
   мониторинг остатка трафика/устройств/времени.
2. **Покупка (purchase-page)** — выбор сервера (`server_dropdown_options`) и плана
   (`server_plans_grid`), расчёт цены с учётом скидок.
3. **Продление (renew-page)** — выбор существующего ключа для продления + сетка тарифов.
4. **Инструкция/подключение (setup-page)** — список активных ключей с кнопкой
   "Открыть инструкцию" (используется deep-link на `sub_url`).
5. **Профиль (profile-page)** — карточка пользователя: баланс, кол-во рефералов, реферальный
   доход, кол-во ключей, дата регистрации, список всех ключей.
6. **Поддержка (support-page)** — тикет-система (`/api/support/status`, `/api/support/create`),
   независимая от основного `support_bot`, судя по отдельным моделям `SupportStatusRequest`,
   `SupportTicketCreateRequest`, `SupportMessageSendRequest`.

## 7. Расчёт цены и скидки (`calculate_webapp_price`)

- Скидка продавца (`seller_active` + `seller_sale` из `get_seller_user`) — франшиза/партнёрка.
- Реферальная скидка на первую покупку (`referred_by` + `total_spent == 0` +
  настройка `referral_discount`).
- Использует общие функции проекта (`get_seller_user`, `get_device_tiers`, `get_host` из
  `database.py`), значит логика полностью завязана на существующие таблицы бота.

## 8. Оплата — переиспользует существующие модули бота

`handlers.py` импортирует напрямую из основного бота:
- `shop_bot.bot.keyboards`: `create_payment_keyboard`, `create_yoomoney_payment_keyboard`,
  `create_cryptobot_payment_keyboard`.
- `shop_bot.bot.handlers`: `create_cryptobot_api_invoice`, `process_successful_payment`,
  `notify_admin_of_purchase`.
- `get_transaction_comment` — короткое описание платежа (для ЮKassa/ЮMoney/Stars) реализовано
  локально в `webapp/handlers.py`, без зависимости от модуля бота (там такой функции никогда
  не было — старая попытка импортировать её из `shop_bot.bot.handlers` ломала любую оплату
  из webapp `ImportError`'ом).
- `shop_bot.modules.platega_api.PlategaAPI`, `shop_bot.modules.heleket_api.create_heleket_payment_request`.
- `yookassa` SDK напрямую (`Configuration`, `Payment`).
- Собственная генерация ссылки ЮMoney (`_build_yoomoney_link`).
- Оплата звёздами Telegram (`_send_invoice_stars`, валюта `"XTR"`).
- Роуты: `POST /api/payment-methods`, `POST /api/create-payment`, `POST /api/apply-promo`,
  `POST /api/check-payment`.

Значит: **это не отдельный магазин, а альтернативный UI поверх той же бизнес-логики бота.**

## 9. Управление ключами из mini app

- `POST /api/key/devices` — просмотр/лимит устройств по ключу.
- `POST /api/key/device/delete` — отвязка устройства (HWID) от ключа.
- `POST /api/key/comment` — редактирование пользовательского комментария к ключу
  (`comment_key`, отображается на карточке ключа).
- `POST /api/device-tiers` — получение тарифных планов по лимиту устройств для хоста
  (`get_device_tiers` из `database.py`).

## 10. Различия по сравнению с ботом

- Форматирование сумм — `"1 240,50 ₽"` (пробел как разделитель тысяч, запятая как разделитель
  дробной части — русская локаль).
- Собственное форматирование "осталось времени" (`_format_remaining_details`) и трафика
  (`_format_bytes`) — по сути дублирует аналогичную логику из `bot/handlers.py`, но не
  переиспользует её напрямую (риск рассинхронизации форматов при доработках).
- Отдельная HTML-генерация карточек ключей (три почти идентичных генератора:
  `_get_key_html`, `_get_profile_keys_html`, `_get_setup_keys_html`) — потенциальный кандидат
  на рефакторинг/унификацию, но пока не трогаем, чтобы не сломать функциональность.

## 11. `install.sh` — требования к деплою домена

Скрипт (bash, запускается на сервере, требует root/sudo):
- Устанавливает пакеты `nginx`, `certbot`, `python3-certbot-nginx` (если их нет).
- Запрашивает у администратора интерактивно (через `/dev/tty`): домен и email для SSL.
- Генерирует конфиг Nginx (`/etc/nginx/sites-available/remnawave-webapp.conf`) —
  простой reverse-proxy на `127.0.0.1:8000` (порт uvicorn внутри контейнера/хоста).
- Получает SSL-сертификат через `certbot --nginx`.
- В конце выводит: **"Убедитесь, что в админ-панели включен Webapp."** — прямое текстовое
  подтверждение, что в существующей (более ранней) версии проекта уже предполагался тумблер
  включения/выключения Webapp в админ-панели — то есть наша будущая настройка
  "включение/выключение" полностью соответствует изначальному замыслу авторов miniapp.

## 12. Статус интеграции (актуально)

Пункты ниже **уже сделаны** в текущем репозитории:

1. `get_webapp_settings()` живёт в `database.py` и доступна через `remnawave_repository`.
2. Ключи `webapp_*` сохраняются из панели (`/settings`, `/settings/webapp/*`).
3. Сервис `xatabchik-webapp` есть в `docker-compose.yml` (`uvicorn` на порту 8000 → хост 8001).
4. Зависимости `fastapi`, `uvicorn`, `qrcode` есть в `pyproject.toml`.
5. Fulfillment оплаты делегируется в `bot.handlers.process_successful_payment`.
6. Тикеты Mini App пишут в те же `support_*` таблицы, что бот и панель.

Имеет смысл держать в голове при доработках (это не дыры интеграции, а особенности кода):

- HTML собирается строковой заменой, не Jinja.
- Форматирование дат/трафика дублирует бот и может разъехаться.
- `modules/cryptobot_api.py` Mini App не импортирует — берёт функцию из `bot/handlers.py`.

Полный список HTTP-роутов: [ADMIN_PANEL_DOCUMENTATION.md](ADMIN_PANEL_DOCUMENTATION.md) не покрывает Mini App; актуальные FastAPI-пути:

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/` | Кабинет или login |
| GET/POST | `/api/auth/*` | Токен, Telegram, email, reset, sync-tg |
| POST | `/api/create-payment`, `/create-topup-payment`, `/create-lte-topup-payment` | Инвойсы |
| POST | `/api/check-payment`, `/api/webapp/payments/{id}/verify` | Сверка статуса |
| POST | `/api/key/*`, `/api/keys/search` | Устройства, имя, комментарий, автопродление |
| POST | `/api/support/*` | Тикеты |
| GET | `/api/user/transactions`, `/api/lte-packages` | История и пакеты LTE |
| GET | `/ref/{id}`, `/gift/{code}` | Публичные лендинги + pending action |

---

Связанные документы: [ARCHITECTURE.md](ARCHITECTURE.md), [PAYMENTS_DOCUMENTATION.md](PAYMENTS_DOCUMENTATION.md), [SUPPORT_BOT_DOCUMENTATION.md](SUPPORT_BOT_DOCUMENTATION.md).

