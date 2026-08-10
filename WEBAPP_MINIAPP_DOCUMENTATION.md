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
handlers.py         - вся backend-логика (2406 строк): роуты FastAPI, HTML-рендеринг, auth, оплата
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

## 4. КРИТИЧЕСКИ ВАЖНО: отсутствующая функция `get_webapp_settings`

`handlers.py` импортирует:
```python
from shop_bot.data_manager.remnawave_repository import (..., get_webapp_settings, ...)
```
Но такой функции **не существует** ни в `remnawave_repository.py`, ни в `database.py` текущего
проекта (проверено через поиск по всему репозиторию). Значит:
- Это функция, которую нужно **создать с нуля** при интеграции.
- Ожидаемо, что она должна возвращать dict с как минимум ключами:
  `webapp_title`, `webapp_logo`, `webapp_icon`, `tg_fullscreen`, а также (по требованию
  пользователя) флаг включения и домен — вероятно `webapp_enabled`, `webapp_domain`.
- В существующем `ALL_SETTINGS_KEYS` (в `webhook_server/app.py`) таких ключей тоже нет —
  их нужно туда добавить, а также добавить чтение/запись через `get_setting`/`update_setting`
  (общий key-value механизм настроек бота, таблица `bot_settings` в SQLite).
- В проекте уже есть похожий текстовый бренд `panel_brand_title` (используется в шапке админки
  и как fallback для заголовка miniapp) и логотип бота по умолчанию — `src/shop_bot/img/obla.png`
  (используется в `bot/photo_helper.py::get_default_photo_path()` для отправки картинок ботом).
  Отдельной настройки "логотип проекта" (URL/путь) в БД пока не существует — её тоже нужно будет
  завести (или переиспользовать существующий файл `img/obla.png` как источник, что соответствует
  пожеланию пользователя "логотип он должен брать из логотипа проекта").

## 5. Аутентификация (Telegram initData + альтернативные способы)

Функция `validate_telegram_data(init_data, bot_token)`:
- Стандартная проверка подписи Telegram WebApp initData (HMAC-SHA256 с секретом
  `HMAC(key="WebAppData", msg=bot_token)`, затем `HMAC(secret, data_check_string)`), сверяется
  с полем `hash` из initData. Стандартный, безопасный подход.

Поддерживаемые способы входа (все реализованы как FastAPI-роуты):
- `GET /` — если передан `token` (query param) — вход по постоянному токену
  (`database.get_user_by_auth_token`). Если нет `user_id`/токена — отдаётся `login.html`.
- `GET /api/auth/request-token` — генерирует временный токен и deep-link
  `tg://resolve?domain=<bot_username>&start=auth_<token>` (пользователь переходит в бота,
  бот подтверждает — см. `TEMP_AUTH_TOKENS` in-memory dict).
- `GET /api/auth/check-token/{token}` — поллинг: проверяет, подтверждён ли токен (или уже есть
  постоянный токен в БД).
- `POST /api/auth/token` — вход через `init_data` (проверка через `validate_telegram_data`),
  выдаёт постоянный токен.
- `POST /api/auth/telegram-direct` — прямой вход по `user_id` (без проверки initData —
  используется, видимо, когда открыто изнутри Telegram и user уже известен).
- `POST /api/auth/email/register` / `/login` — альтернативная регистрация по email+паролю
  (создаёт "виртуального" пользователя с telegram_id, начинающимся на `"999"` — это специальный
  префикс для "не привязанных к Telegram" аккаунтов, что подтверждается также в
  `_get_profile_card_html`, где кнопка "Синхронизировать с Telegram" показывается только если
  `str(user_id).startswith("999")`).
- `POST /api/auth/email/reset/request|check|verify` — сброс пароля по email через код,
  отправляемый... в Telegram-сообщение (не на почту!) — см. `_send_telegram_message`.
- `POST /api/auth/sync-tg` — привязка ранее созданного email-аккаунта к реальному Telegram.

Все токены — постоянные UUID4, хранятся в БД через `database.update_user_auth_token` /
`get_auth_token_by_user_id` / `get_user_by_email` / `create_user_by_email` (эти функции уже
должны существовать в проектном `database.py` — требуется проверить/добавить при интеграции).

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

## 12. Что нужно сделать при интеграции (план, ещё не реализовано)

1. Создать `get_webapp_settings()` в `remnawave_repository.py` (или `database.py`) — должна
   отдавать dict как минимум с: `webapp_enabled`, `webapp_domain`, `webapp_title`,
   `webapp_logo`, `webapp_icon`, `tg_fullscreen`.
2. Добавить новые ключи в `ALL_SETTINGS_KEYS` (`webhook_server/app.py`):
   `webapp_enabled`, `webapp_domain` (логотип — не отдельная настройка, а автоматически
   берётся из существующего логотипа проекта, как и просил пользователь).
3. Логотип: определить единый источник "логотипа проекта" — либо использовать
   `src/shop_bot/img/obla.png` как файл (раздать его в вебе через `StaticFiles`/новый роут),
   либо (если в будущем появится настройка загрузки логотипа в админке) использовать её.
   Значение `webapp_logo` в шаблоне должно указывать на публичный URL этого файла.
4. Добавить секцию в шаблон `webhook_server/templates/settings.html` (или отдельную вкладку) с
   полями: домен (`webapp_domain`), чекбокс включения (`webapp_enabled`). Обработчик в `app.py`
   должен сохранять эти значения через `update_setting`.
5. Исправить импорты в `handlers.py`, если потребуется (пока похоже, что они уже соответствуют
   структуре проекта — `shop_bot.data_manager.database`, `shop_bot.bot.keyboards`,
   `shop_bot.bot.handlers`, `shop_bot.modules.*` — все такие модули существуют в проекте).
6. Добавить сервис `remnawave-webapp` в реальный `docker-compose.yml` проекта (по образцу
   предоставленного пользователем), а также зависимость `fastapi`/`uvicorn`/`qrcode` и др.
   в `pyproject.toml`, если их там ещё нет.
7. Проверить, что `webapp_enabled=False` действительно отключает выдачу Mini App (например,
   через middleware/проверку в начале `index()`, отдающую 503 или страницу "отключено"), так
   как в текущем коде такой проверки пока не найдено.

