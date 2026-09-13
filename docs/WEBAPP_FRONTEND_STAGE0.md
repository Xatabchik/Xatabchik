# Этап 0. Аудит и план: нативный модульный WebApp

Документ фиксирует состояние Mini App **на момент Этапа 0**. Исходный аудит кода не менял. План ниже — предложение; к Этапу 1 не приступать, пока этот документ не одобрен.

Исходники: `src/shop_bot/webapp/app.html`, `src/shop_bot/webapp/login.html`, пакет `src/shop_bot/webapp/web_router/`. Замеры внешних ресурсов — 13 сентября 2026, живые ответы CDN. Тестовая база — `main` на коммите `e1ae3c7`, `python3 -m pytest -q` → **735 passed**.

**Addendum 13 сентября 2026.** Stored XSS в заметке/имени ключа закрыт отдельным security PR [#145](https://github.com/Xatabchik/Xatabchik/pull/145) (`cursor/fix-key-comment-stored-xss-35c7`, `1038689`), **не** смешан с этим документом и **не** смешан с рефакторингом `app.html`. После мержа #145 baseline тестов станет **741 passed**. Повторный обход оставшихся цепочек — §2.1a. Этап 0 по-прежнему не содержит правок продукта.

---

## 1. Карта frontend

### 1.1 Файлы и размеры

| Файл | Строк | Байт | Inline JS | Inline CSS |
|------|------:|-----:|----------:|-----------:|
| `app.html` | 5703 | 333 368 | 4 блока, ~4534 строк / 254 672 байт | 2 блока, ~238 строк / 6797 байт |
| `login.html` | 947 | 55 111 | 3 блока, 35 190 байт | 2 блока, 832 байт |
| Итого | 6650 | 388 479 | ~290 КБ JS в HTML | ~7.6 КБ CSS в HTML |

В `app.html` четыре `<script>` без `src`:

| Строки | Назначение |
|--------|------------|
| 15–74 | Auth helpers + снятие `token`/`pending_token` из URL |
| 80–104 | `tailwind.config` (runtime-конфиг CDN) |
| 922–1909 | Навигация, поддержка, дропдауны, `initApp` |
| 2237–5701 | Платежи, ключи, рефералка, профиль, подарки, polling |

Отдельного каталога `js/` или `static/css/` нет. Статика webapp: `StaticFiles` на `/uploads` и `/module/ico` (`web_router/_app.py:42–48`).

### 1.2 Экраны и точки входа

Роутер — hash, без перезагрузки страницы. `handleHashChange` (`app.html:1549`) + `showPage` (`app.html:1500`).

| Экран | DOM id | Hash | Точка входа | Данные при открытии |
|-------|--------|------|-------------|---------------------|
| Главная | `#home-page` | `''` | нижняя навигация, `navigateTo('home')` | SSR карточка профиля; `_loadHomeStats` → `/api/user-status`, `/api/user/referral-info` |
| Ключи | `#keys-page` | `#keys` | нижняя навигация | SSR `#profile-keys-list-container`; `_loadKeysPage` → пагинация + `/api/user/gifts` |
| Покупка | `#purchase-page` | `#bay` | кнопки «Купить» / gift | SSR `#server-dropdown-options`, `#server-plans-grid`; `/api/device-tiers` |
| Продление | `#renew-page` | `#rebay` | «Продлить», `goToRenewKey` | SSR renew dropdown + plans; `/api/device-tiers` |
| Установка | `#setup-page` | `#setup` | из карточки ключа | SSR `#setup-keys-list-container` |
| Финансы | `#finance-page` | `#finance` | нижняя навигация | `_loadFinancePage` → `/api/user-status`, `/api/user/transactions` |
| Рефералка | `#referral-page` | `#referral` | нижняя навигация | `_loadReferralPage` → referral-info, withdrawals |
| Поддержка | `#support-page` | `#support` | нижняя навигация | `/api/support/status` + polling 5 с |
| Логин: загрузка | `#loader` | — | `GET /` без токена | — |
| Логин: методы | `#auth-methods` | — | после инициализации TG | `/api/auth/request-token`, `/api/auth/telegram-direct` |
| Логин: email | `#email-auth-form` | — | «Войти по Email» | `/api/auth/email/login`, register |
| Логин: код | `#email-verify-form` | — | после register | `/api/auth/email/verify`, resend |
| Логин: сброс | `#reset-password-form` | — | «Забыли пароль?» | reset/request, check, verify |

Модальные окна (не отдельные hash): `#payment-modal` (покупка), `#action-modal` (пополнение, устройства, переименование, заметка, профиль, реквизиты), toast `#notification-container`.

`login.html` обработчики вешает через `addEventListener` (кроме одного `onerror` на логотипе, `login.html:103`). `app.html` — 98 `onclick` + 2 `oninput`.

### 1.3 Глобальное состояние

**`localStorage` / cookie**

| Ключ | Файл:строки | Что лежит | Срок |
|------|-------------|-----------|------|
| `auth_token` | `app.html:16–37`, `login.html:757–777` | Persistent UUID сессии | cookie `max-age=31536000`, `path=/`, `SameSite=Lax`; **без `HttpOnly`, без `Secure`** |
| `pendingPayment` | `app.html:2909–3360` | `{paymentId, paymentUrl, planName, methodName, timestamp}` | клиентский TTL проверяется при restore |
| `pendingTopUp` (`TOPUP_PENDING_KEY`) | `app.html:4952–4962` | `{paymentId, paymentUrl, amount, methodName, timestamp}` | клиентский TTL |

Токен также читается из query `?token=` и сразу убирается через `history.replaceState` (`app.html:54–72`). Дублируется в cookie «для запросов без JS» — но `GET /` читает только query token (`render_page.py:329`), не cookie.

**`window.*` состояние (38 присваиваний)**

Auth: `setAuthToken`, `getAuthToken`, `removeAuthToken`, `getTgInitData`. Навигация/UI: `toggleKeyCard`, `selectPlan`, `selectServer`, `selectRenewKey`, `selectTierDot`, `openLinkSafe`, `toggleInfoBlock`, `toggleRenewInfoBlock`. Данные: `_currentUserId`, `_purchaseMode`, `_profileKeysCards`, `_giftsState`, `_deviceModalState`, `_payoutMethodState`, `_profileInfo`. Платежи: `_topUpAmount`, `_topUpPaymentId`, `_topUpPaymentUrl`, `_topUpPollingInterval`, `_plategaAutoVerifyFor`. Рефералка: `_referralMinWithdraw`, `_referralAvailableBalance`, `_referralHasOpenWithdraw`, `_referralWithdrawEnabled`, `_withdrawSelectedId`. Pending: `_pendingActionToken`. Загрузчики: `_loadHomeStats`, `_loadKeysPage`, `_loadFinancePage`, `_loadReferralPage`.

**Локальные `let` в главном скрипте (74)** — отдельно: `currentTicketId`, `supportPollInterval`, `_paymentPoll*`, `currentPaymentData`, `selectedMethod`, `activePaymentUrl`, `activePaymentId`, `activeTierData`, `tierCache`, `methodsCache`, `_txPage`, `_activeKeysTab`, `_keysSearchDebounceTimer`. Единого store нет: баланс читается заново на home и finance двумя независимыми `fetch`.

### 1.4 API-вызовы frontend → backend

Клиент шлёт `user_id` в JSON почти во всех POST. Сервер его **игнорирует** (`models.py`: комментарий `ignored; identity from token only`). Идентичность — `_require_authenticated_user` / `_resolve_user_from_request_token` (`auth_session.py:14–85`): token из body / Bearer / cookie, либо HMAC `init_data`.

| Экран | Запросы | Когда |
|-------|---------|-------|
| Первое открытие `GET /` | SSR HTML, никаких `/api/*` до JS | сервер |
| Home | `GET /api/user-status`, `POST /api/user/referral-info` | `showPage(home)` |
| Keys | `POST /api/user/gifts`; поиск `POST /api/keys/search`; rename/comment/devices/auto-renew | открытие + действия |
| Purchase / Renew | `POST /api/device-tiers`, `POST /api/payment-methods`, `POST /api/create-payment`, `POST /api/apply-promo` | выбор тарифа / оплата |
| LTE | `GET /api/lte-packages`, `POST /api/create-lte-topup-payment` | докупка LTE |
| Finance | `GET /api/user-status`, `GET /api/user/transactions` | открытие + «ещё» |
| Top-up | `POST /api/payment-methods`, `POST /api/create-topup-payment`, `POST /api/check-payment`, `POST /api/webapp/payments/{id}/verify` | модалка |
| Referral | `POST /api/user/referral-info`, withdrawals, payout-methods/* | открытие + действия |
| Support | status / create / send / ticket / close / upload / `GET /api/support/ticket-file/{id}` | открытие + polling 5 с |
| Profile | `POST /api/user/profile-info`, change-password, change-email/* | модалка |
| Gift / pending | `POST /api/gift/activate`, `POST /api/webapp/pending-actions/complete` | deep-link |
| Login | `GET /api/auth/request-token`, `GET /api/auth/check-token/{t}`, `POST /api/auth/token`, `POST /api/auth/telegram-direct`, email/* | вход |
| После успеха оплаты | `GET /?token=…` целиком (`refreshAppData`, `app.html:3129`) + `GET /api/user-status` | `showSuccessScreen` |

Полный список путей, которые дергает `app.html`:  
`/api/support/{ticket,status,create,send,upload,close,ticket-file/}`, `/api/device-tiers`, `/api/lte-packages`, `/api/payment-methods`, `/api/create-payment`, `/api/create-lte-topup-payment`, `/api/create-topup-payment`, `/api/check-payment`, `/api/webapp/payments/{id}/verify`, `/api/user-status`, `/api/key/{devices,device/delete,comment,rename,devices/delete-all,auto-renew}`, `/api/apply-promo`, `/api/user/transactions`, `/api/keys/search`, `/api/referral/{payout-methods/list,add,delete,available-method-types,request-withdrawal,withdrawals}`, `/api/user/{referral-info,gifts,profile-info}`, `/api/gift/activate`, `/api/webapp/pending-actions/complete`, `/api/user/profile/{change-password,change-email/request,verify,resend,cancel}`.

`login.html`: `/api/webapp/pending-actions/info`, `/api/auth/email/{verify,resend,reset/check,reset/request,reset/verify}`, `/api/auth/check-token/{token}`, `/api/auth/request-token`, `/api/auth/token`.

### 1.5 Polling и интервалы

| Механизм | Файл:строки | Интервал | Стоп | Риск |
|----------|-------------|----------|------|------|
| Поддержка `startSupportPolling` | `app.html:1084–1092` | `setInterval` **5 с** на `/api/support/status` | `stopSupportPolling` при уходе со страницы | Один запрос на вкладку; без AbortController; тикеты всех пользователей с открытой вкладкой бьют API |
| Оплата `startStatusPolling` / `_tickPaymentPoll` | `app.html:2296–3127` | backoff 8→20 с, потолок 40 мин, пауза при `document.hidden`, один in-flight | `_stopStatusPolling` | Один активный `payment_id`. Старый `window._topUpPollingInterval` ещё чистится, но больше не ставится |
| Platega verify | `app.html:3002, 5107` | по кнопке / авто при возврате | — | Отдельный POST, не цикл |
| `themeColorTimer` | `app.html:1054–1060` | 100 мс debounce скролла | — | локально |
| `_keysSearchDebounceTimer` | `app.html:3951` | debounce поиска | — | локально |
| Login: опрос `check-token` | `login.html:798` | цикл до подтверждения ботом | переход на `/?token=` | нормальный pairing |

Общего polling баланса/ключей нет. После успеха покупки вызывается `refreshAppData()` — полный повторный `GET /` и замена innerHTML шести контейнеров (`app.html:3129–3198`). Это не reload вкладки, но по стоимости — повторный SSR всей страницы.

### 1.6 `location.reload` / навигация / `window.open`

| Строка | Что | Зачем сейчас | Что инвалидировать вместо reload |
|--------|-----|--------------|----------------------------------|
| `app.html:294` | `onclick="location.reload()"` | кнопка «Обновить» на home | `refresh.refresh(['user','keys','finance'])` на текущем экране |
| `app.html:3530` | `reload()` через 500 мс | заметка ключа: DOM-узлов комментария нет | точечно карточку ключа; fallback — `keys` |
| `app.html:3762` | `reload()` через 700 мс | после rename | только карточку ключа (`keys`, home badge) |
| `app.html:4585` | `reload()` через 1200 мс | активация своего подарка | `keys`, `gifts`, home |
| `app.html:5443` | `location.reload()` через 1800 мс | gift из URL | то же |
| `app.html:5470` | `location.reload()` через 1800 мс | pending-action gift activated | то же |
| `app.html:1072, 3352` | `location.href = "/"` | logout / cancel session | остаётся полная навигация (смена документа) |
| `app.html:2945, 4916` | `location.href = payment_url` | уход на оплату YooKassa и др. | остаётся: это внешний провайдер |
| `app.html:1042–1050, 2936, 3047, 4099, 4928, 5154` | `openLinkSafe` / `window.open` | оплата, t.me share, sync TG | не reload |
| `app.html:341–351, 1527–1559` | `hash = …` | смена экрана | уже без reload |
| `login.html:791, 824` | `location.href = /?token=` | после входа | смена документа login→app, допустимо |

Итого **6 reload для данных** + 1 явная кнопка «Обновить» + 2 logout/cancel на `/`.

### 1.7 Inline-обработчики

`app.html`: **98 `onclick`**, **2 `oninput`** (поиск ключей). `login.html`: **1 `onerror`** на логотипе.

60 уникальных функций в `onclick="…("` — полный список в §6 (compatibility bridge). Не удалять одним махом: пока разметка вызывает функцию, нужен `window.<name>`.

### 1.8 `innerHTML` и вставка данных в HTML

| Метрика | `app.html` | `login.html` |
|---------|-----------:|-------------:|
| `innerHTML` (любое) | 149 | 0 |
| присваивания `innerHTML =` | 141 | 0 |
| из них очистка `''` | 7 | 0 |
| шаблонные строки в `innerHTML` | 22 | 0 |
| `createElement` | 21 | 3 |
| `textContent` | 67 | 34 |
| `addEventListener` | 46 | 20 |
| `escapeHtml` общий | **нет** | нет |
| локальный `esc` / `escTx` | 2 места (транзакции) | — |
| `eval` / `new Function` / строковый `setTimeout` | **нет** | нет |

Доверенные HTML-поля с сервера (намеренно HTML):

| Источник | Поле | Sink |
|----------|------|------|
| `POST /api/keys/search` | `data.html` | `app.html:4009` `resultsEl.innerHTML` |
| `POST /api/user/gifts` | `g.card_html` | `app.html:4466–4506` |
| SSR `GET /` | `{{ profile_keys_list }}`, `{{ setup_keys_list }}`, `{{ user_profile_card }}`, plans/hosts | первичная загрузка |
| `refreshAppData` | повторный SSR тех же контейнеров | `app.html:3145` |
| admin `hosts.description` | `#desc-content-*` | копируется `infoBlock.innerHTML = descContent.innerHTML` (`app.html:1664, 1777, 1878, 1885`) |

Поддержка рендерит сообщения через `createElement` + `textContent` (`app.html:1176–1178`) — образец безопасного пути.

Пользовательские поля в HTML без экранирования: снимок аудита — §2.1; актуальный статус после #145 — §2.1a.

### 1.9 Клиент считает цену / права

| Место | Что считает | Источник истины на сервере? |
|-------|-------------|-----------------------------|
| `app.html:2453, 2528–2562` | доплата за tier: `(device_count - base) * price * billing_units` | **Частично нет.** `/api/create-payment` принимает `req.tier_price` и **прибавляет его как есть** (`payments_create.py:185–216`), не сверяя с `get_device_tiers`. Нулевой `tier_price` обнуляет `tier_device_count`. |
| `app.html:2817, 2695` | цена в модалке из `data-price` кнопки тарифа | База тарифа пересчитывается: `calculate_webapp_price(plan['price'], user_id)` (`payments_create.py:179`) |
| `app.html:3568` | отображение скидки промокода | `/api/apply-promo` считает `new_price` от **`req.price` клиента** (`payments_promo.py:49–63`) — только preview. При создании платежа скидка считается заново от серверной цены |
| `app.html:4883, 5123` | сумма пополнения `window._topUpAmount` | сервер берёт `req.amount`, границы 10–100000 (`payments_topup.py:55–62`) |
| `{{ min_price }}` | «от N ₽» на кнопке покупки | SSR из админских тарифов |
| `RENDERED_USER_ID` / `initDataUnsafe.user.id` | клиент кладёт в JSON как `user_id` | сервер не использует для идентичности |

Права (чей ключ, чей тикет, чей платёж) клиент не решает — кроме того, что шлёт id ресурса. Проверка владельца обязана остаться на сервере (см. §2.2).

---

## 2. Security-аудит

Угрозы — конкретные пути этого репозитория. «Защита есть» не значит «можно не трогать при миграции»: Этапы 1–7 не должны ослабить ни один из этих контролей.

### 2.1 XSS

| # | Путь | Файл:строки | Данные | Доверие | Риск сейчас | План миграции |
|---|------|-------------|--------|---------|-------------|---------------|
| X1 | `comment_key` в `onclick="openActionModal('comment', id, '{comment}')"` и в `<span>` | `render_keys.py:639, 670, 771, 802` | `POST /api/key/comment` → `update_key_comment` без фильтра (`key_devices.py:105`, `db/keys.py:229`) | пользователь, свой ключ | **Stored XSS в своей сессии** (`'` ломает JS-строку). После reload/search/gifts HTML пересобирается с тем же текстом. Live-update после сохранения идёт через `textContent` (`app.html:3519`) — безопасно, пока нет SSR | Не расширять onclick-модель. В Этапе 3: `data-key-id` + `textContent`. На сервере — `_html_esc` / JSON-модель карточки. Отдельный маленький PR на escape **до** большого выноса JS, если одобрите вне плана UI |
| X2 | `user_key_name` в onclick rename и в тексте карточки | `render_keys.py:584, 665, 750, 797, 838` | `POST /api/key/rename`, max 30 символов, HTML не фильтруется | пользователь | То же, лимит 30 сужает payload, но `'`/`"` достаточно для breakout | как X1 |
| X3 | `sub_url` в `copyKey(this, '{url}')` / `openLinkSafe('{url}')` | `render_keys.py:647, 653, 779, 785` | URL подписки с VPN-панели / БД | панель (полуtrusted) | `'` в URL ломает обработчик | `data-url` + listener |
| X4 | `host_name` в onclick devices | `render_keys.py:660` | админский host | админ | XSS при враждебном имени хоста | escape / data-* |
| X5 | `hosts.description` → hidden div → `innerHTML` копия | `render_plans.py:160` → `app.html:1777` | админ | админ XSS в Mini App | не расширять; в Этапе 3 — `textContent` или санитайз на сервере | |
| X6 | `panel_brand_title`, `webapp_logo`, `webapp_icon` в `<title>`, `<img src>`, `<link href>` | `render_keys.py:77, 86–87`; `app.html:11–13, 284` | админ, **plain `str.replace`, без escape** (`render_keys.py:111`) | админ | инъекция в shell, если настройки скомпрометированы | escape при подстановке; logo/icon — только `/uploads/…` или относительный путь |
| X7 | `gift_code` в `onclick="activateOwnGift('{code}')"` | `gifts.py:63` | UUID-фрагмент | низкий | формат ограничен на публичном маршруте | data-* |
| X8 | `data.error` в `innerHTML` поиска | `app.html:4000` | серверная строка ошибки | низкий | если error когда-нибудь станет пользовательским | `textContent` |
| X9 | методы оплаты `m.name` в innerHTML | `app.html:2825–2831, 4867` | серверный список методов | низкий | фиксированные имена | textContent / escape |
| X10 | `pending_email` в onclick профиля | `app.html:5536` | email пользователя | средний | `'` в email ломает JS | data-email + listener |
| X11 | чат поддержки | `app.html:1176–1178` | `msg.content` | пользователь / агент | **уже `textContent`** | сохранить |
| X12 | транзакции | `app.html:3823, 4657` | labels / provider id | БД | локальный `esc`/`escTx` | вынести в общий `escapeHtml` |
| X13 | баннер pending на login | `login.html:255+` | `data.message` с сервера | сервер | проверить, что пишется в `textContent` (сейчас так) | не менять на innerHTML |

Админка показывает заметку через `textContent` (`admin_keys.html:1286–1293`, `setKdNote`) — stored XSS из Mini App **не бьёт админа** этим полем. Риск X1/X2 — в первую очередь сессия самого пользователя и любой, кто откроет его Mini App (общий телефон, XSS + кража token). **X1–X4 закрыты в #145** — актуальная таблица в §2.1a; строки выше — снимок аудита до фикса.

`eval` / `new Function` / загрузка JS из API — нет. Строковых `setTimeout('…')` нет.

### 2.1a Addendum: после #145 — что закрыто и что осталось

PR [#145](https://github.com/Xatabchik/Xatabchik/pull/145) чинит **только** цепочку карточки ключа: ввод → хранение → SSR → inline handler. Рефакторинг `app.html` и Этапы 1–7 сюда не входят. Старые вредоносные строки в БД после фикса не исполняются: фронт не вставляет их в `innerHTML` как сырой текст и не кладёт в `onclick`.

| Было | Статус после #145 | Как закрыто |
|------|-------------------|-------------|
| X1 `comment_key` | **закрыто** | `normalize_key_comment()` + лимит 200; пустое → `NULL` (очистка, не мусор); SSR `_esc_text` = `html.escape(..., quote=True)`; кнопка `data-key-action="comment"` + `data-key-id`; модалка читает `#comment-text-<id>.textContent` |
| X2 `user_key_name` | **закрыто** | тот же `_esc_text` в карточке/setup/renew; rename читает `data-key-name` с карточки и пишет в `input.value` |
| X3 `sub_url` в `copyKey` / `openLinkSafe` | **закрыто** | `data-url` + делегированный `click` на `[data-key-action]` |
| X4 `host_name` на кнопке devices | **закрыто** на карточке ключа | `data-host` + escape текста. Имя хоста в **других** местах — ниже |

Regression: `tests/test_key_comment_stored_xss.py`. Payload (`<img…onerror>`, `</span><script>`, `');alert(1);//`, кавычки, `\`, переносы, backticks) остаётся текстом, не создаёт тегов/атрибутов и не попадает в исполняемый inline JS. Auth token в HTML/`GET /` и в assert-сообщениях тестов не печатается.

Ниже — повторная проверка полей из задания. **В #145 их нет**: либо нет доказанного user-writable XSS в том же классе sink, либо это другой экран и отдельный PR.

#### Уже безопасно (не трогать в срочном PR)

| Поле | Пишет | Sink | Вердикт |
|------|-------|------|---------|
| Текст тикета `msg.content` | пользователь / агент | `createElement` + `textContent` (`app.html:1176–1178`) | безопасно |
| Тема тикета `t.subject` | пользователь, clip 64 | `name.textContent` / `header.textContent` (`app.html:1219, 1263`) | безопасно |
| Промокод | пользователь | `input.value` / поле платежа, не HTML (`app.html:3545–3581`) | безопасно как текст |
| Название тарифа в модалке оплаты | админ | `elName.textContent` (`app.html:2740`) | отображение безопасно |
| Транзакции `action_label` / `status` / provider id | сервер | локальный `escTx` (`app.html:3823`) | экранировано (без `'` в onclick) |
| Подписи кнопок Mini App | константы в HTML | — | не user-data |
| `card_html` подарка после #145 | SSR той же `_get_key_card_html` | `g.card_html` → `innerHTML` (`app.html:4466`) | наследует escape карточки; fallback без user-comment |

#### Оставшиеся цепочки (потенциал / доказанный риск вне #145)

Доверие: **пользователь** = любой авторизованный; **админ** = компрометация панели/настроек; **панель** = Remnawave / чужой UA.

| # | Путь | Файл:строки (на `e1ae3c7`, если не указано) | Кто пишет | Sink | Доказанный XSS сейчас? | Следующий шаг |
|---|------|---------------------------------------------|-----------|------|------------------------|---------------|
| X5 | `hosts.description` → hidden `#desc-content-*` → копия `innerHTML` | `render_plans.py:61, 160` → `app.html:1664, 1777, 1878, 1885` | админ | HTML как HTML | да, если админ враждебен | Этап 3: `textContent` или санитайз на сервере. Не в #145 |
| X6 | `panel_brand_title`, `webapp_logo`, `webapp_icon` | `render_keys.py:77, 86–88, 111`; `app.html:11–13, 284` | админ | `str.replace` без escape в `<title>`, `<img src>`, текст | да при враждебных настройках | escape + ограничить logo/icon путём `/uploads/…`. Не в #145 |
| X7 | `gift_code` в `onclick="activateOwnGift('…')"` | `gifts.py:63`; клиентский fallback `app.html:4488` | система (UUID) | JS-строка, экранируется только `'` | нет (формат кода) | data-* в Этапе 5 |
| X8 | `data.error` в `innerHTML` | `app.html:2659, 3430, 3812, 4000, 5201` | серверные строки | HTML | нет, пока error не станет user-text | `textContent` |
| X9 | `m.name` методов оплаты | `app.html:2825–2831, 4861–4867` | конфиг методов | `innerHTML` + `onclick` (top-up экранирует только `'`) | нет при фиксированных именах | textContent / data-* |
| X10 | `pending_email` / `auth_email` | `app.html:5528–5536` | пользователь | `innerHTML` + `onclick="…('${email}')"` | **да, формат слабый.** `_EMAIL_FORMAT_RE` = `[^@\s]+@…` (`_core.py:49`) пропускает `<`, `>`, `'`, `"`. Payload вида `<img src=x onerror=alert(1)>@evil.com` или `');alert(1);//@x.com` проходит валидатор и попадает в HTML/JS | отдельный маленький security PR: ужесточить regex + `textContent` / `data-email`. **Не смешивать с #145 и Этапом 0** |
| X11 | чат поддержки | см. выше | — | `textContent` | нет | сохранить |
| X12 | транзакции | см. выше | — | `escTx` | нет | общий `escapeHtml` в Этапе 2 |
| X13 | баннер pending login | `login.html:255+` | сервер | `textContent` | нет | не менять на innerHTML |
| **X14** | реквизиты `requisite_value` | запись: `referral_payouts.py:56–68` (только `strip`); показ: `_maskRequisite` → `innerHTML` (`app.html:4105–4110, 4274, 5217`) | **пользователь** | HTML | **да, если в значении нет цифр.** `_maskRequisite` тогда возвращает сырую строку. `<img src=x onerror=alert(1)>` как USDT/произвольный реквизит исполняется в своей сессии | отдельный security PR: валидация формата на backend + escape/`textContent`. Не в #145 |
| **X15** | `bank_name` реквизита | API принимает любой `bank_name` (`referral_payouts.py:57`); UI подставляет из админского списка, но клиент не обязателен | **пользователь через API** | `${label}` в `innerHTML` (`app.html:4266–4273, 5210–5216`) | **да** — `bank_name=<img src=x onerror=alert(1)>` | тот же PR, что X14 |
| X16 | user-agent / hwid устройств | `app.html:3694–3707` | VPN-клиент / панель | `innerHTML` без HTML-escape; в `onclick` только `.replace(/'/g, "\\'")` | потенциально: UA с `<` создаёт теги; `` ` `` / перевод строки / `</button>` ломают разметку. `'` в onclick экранирован, обратный слеш и newline — нет | data-* + textContent в пакете keys Этапа 5. Не доказано как user-API write в этом репо |
| X17 | `host_name` / `plan_name` в покупке | `render_plans.py:106, 146–150, 160` | админ | атрибуты `data-host`, `data-plan-name`, `data-server` и текст без escape | да при враждебном имени (`"`, `<`) | escape атрибутов вместе с X5/X6 |
| X18 | fallback-карточка подарка `{host_name}` | `gifts.py:77–86` | админский host | HTML без escape | как X17 | escape в `_get_gift_fallback_card_html` |
| X19 | `gift_code` / ссылки подарка / `gift_share_text` | `gifts.py:25–34, 47–63` | UUID + админский текст + собранный URL | HTML + `onclick` (только `'` → `\'`) | нет для UUID; да если admin `gift_share_text` / domain враждебны | data-url; escape share text |
| X20 | реферальные `bot_link` / `webapp_link` / `share_text` | `app.html:4376–4418` | сервер (username, domain, админский текст) | `innerHTML` + `onclick="copyToClipboard('${link}')"` без escape | да при `'` в username/domain/share_text | encodeURI / data-* |
| X21 | `syncTelegram('{bot_username}')` | `render_keys.py:490` (после #145: ~501) | админская настройка | inline JS | да при `'` в username | data-username |
| X22 | LTE `pickLtePackage(${JSON.stringify(p)})` в `onclick='…'` | `app.html:2668–2669` | админские пакеты | JSON внутри single-quoted onclick: `JSON.stringify` не экранирует `'` | да, если в пакете есть `'` | data-* + listener |
| X23 | `methodName` в success-описании | `app.html:3320` | имя метода | `innerHTML` | как X9 | textContent |
| X24 | иконка метода `iconData.html` | `app.html:2850, 4864` | локальный словарь SVG | `innerHTML` | нет, если словарь константный | не расширять |

`card_html` (`POST /api/user/gifts`, `POST /api/keys/search`, `refreshAppData`) остаётся **доверенным HTML с сервера**. После #145 карточка ключа в этом HTML уже с escape. Новый user-текст в `card_html` без `_esc_text` снова станет XSS — при Этапах 3/6 не возвращать сырые поля в разметку.

Админка по-прежнему показывает заметку ключа через `textContent` (`admin_keys.html:1286–1293`) — Mini App XSS **не бьёт админа** этим полем.

Итог для порядка работ: #145 не расширять. Следующий **доказанный** user-stored XSS вне карточки ключа — **X14+X15 (реквизиты)** и **X10 (email в профиле)**. Их имеет смысл закрыть отдельными минимальными security PR, не Этапами 1–7. Остальное — админ/конфиг или Этап 5 (`onclick` → listener).

### 2.2 IDOR

Идентичность: `_require_authenticated_user` (`auth_session.py:65`) — token или HMAC `init_data`, **никогда** client `user_id`. `GET /` больше не принимает `?user_id=` (`render_page.py:325–334`).

| Ресурс | Endpoint | Проверка владельца | Дыра / замечание |
|--------|----------|-------------------|------------------|
| Платёж | `POST /api/check-payment` | `payment_owned_by_user` (`payments_check.py:103`) | чужой/несуществующий id → нейтральный `{ok:true, paid:false}` |
| Платёж Platega | `POST /api/webapp/payments/{id}/verify` | `payment_owned_by_user` + match metadata (`payments_platega.py:54, 92`) | ок |
| Ключ rename/comment/devices/delete/auto-renew/LTE | соответствующие `/api/key/*`, `/api/lte-packages`, `/api/create-lte-topup-payment` | `key.get("user_id") != user_id` или `_owned_lte_key_and_plan` | ок |
| **Продление ключа** | `POST /api/create-payment` action=`extend` | **проверки владельца `key_id` нет** (`payments_create.py:191–196` читает ключ только для tier). Можно создать счёт на продление чужого `key_id` | **не чинить в UI-PR.** Отдельное согласование backend |
| Тикет / вложение | `/api/support/*`, `GET /api/support/ticket-file/{id}` | `_ticket_owned_by`; чужой file → тот же 404 (`support.py:361–386`) | ок |
| Реквизиты | payout-methods delete/add/withdraw | `get_referral_payout_method(method_id, user_id)` | ок |
| Подарки | `/api/user/gifts` | свои inactive | ок |
| `/ticket_files/**` | `ticket_files_guard.py:16–20` | всегда 404 | **не монтировать как static** |
| `GET /uploads/**` | `_app.py:46–48` | **без auth** | каталог логотипов админки; не класть туда ticket media |
| `POST /api/device-tiers` | `account_sync.py:55` | **без auth** | публичный список тарифов устройств по `host_name` — не секрет, но без лимита |
| `GET /api/webapp/pending-actions/info` | `pending_actions.py:105` | знание `pending_token` | токен одноразовый/TTL 24 ч; не светить в логах |

### 2.3 Token / initData / CSRF

| Угроза | Как сейчас | Риск | План |
|--------|------------|------|------|
| Кража `auth_token` из `localStorage` | любой XSS читает token | высокий при X1 | схема хранения **не менять** до отдельного PR (HttpOnly cookie + CSRF). В Этапе 0 зафиксировано |
| Cookie без `HttpOnly`/`Secure` | `app.html:18` | XSS читает cookie так же, как LS; на HTTP утечёт | тот же отдельный PR |
| Token в query | снимается при load (`app.html:54–72`); `GET /?token=` всё ещё валидный вход (`render_page.py:329`); `refreshAppData` снова запрашивает `/?token=` (`app.html:3133`) | token в Referer/логах прокси при refresh | Этап 3: не тянуть HTML через query token; Authorization / cookie |
| Persistent token ≠ Telegram-контекст | `_is_telegram_webapp_context` + `_telegram_only_method_error` для Stars/TON (`payments_create.py:74`) | уже закрыто в #141 | не подменять `init_data` флагом с клиента |
| `init_data` HMAC + freshness | `validate_telegram_data` (`auth_telegram.py:29`): HMAC-SHA256(`WebAppData`, bot_token), `auth_date` окно **600 с**, дрейф в будущее 60 с (`_core.py:21`) | ок | не трогать |
| `initDataUnsafe.user.id` на клиенте | используется только как fallback `user_id` в JSON | сервер игнорирует | в новых модулях **не слать** `user_id` |
| CSRF state-changing | нет CSRF-токена; cookie `SameSite=Lax` | cross-site POST из другой HTTPS-страницы с cookie — возможен | не менять схему в UI-PR; учесть в PR про HttpOnly |
| Token в HTML/JS исходниках | `{{ user_id }}` — число, не token. Токена бота в HTML нет | ок | source maps не публиковать |

Lifetime persistent token: **бессрочный на сервере**, пока не перевыпущен (`captcha_auth.py:136`).

### 2.4 Файлы

| Путь | Защита | Риск |
|------|--------|------|
| `GET /api/support/ticket-file/{message_id}` | auth + owner + `realpath` prefix + MIME whitelist (`detect_image_kind`) + TTL закрытого тикета + `nosniff` / `no-store` (`support.py:361–401`) | ок |
| `POST /api/support/upload` | owner + open ticket + 10 МБ + jpeg/png/webp/pdf + rate (`TICKET_MEDIA_MAX_BYTES`) | ок |
| `/ticket_files` и `/ticket_files/{rest}` | всегда 404 (`ticket_files_guard.py:16–20`) | **не открывать** при раздаче `static/` |
| `/uploads` | публичный StaticFiles | только брендинг; не media тикетов |
| `/module/ico` | публичный, если каталог есть | иконки |

### 2.5 CDN / supply-chain / CSP

Сейчас **CSP на `GET /` и login нет**. Есть только `_PUBLIC_FALLBACK_CSP` на HTML-заглушках `/ref/` и `/gift/` (`public_pages.py:37`, `_core.py:59`).

Каждый визит Mini App грузит с чужих origin:

| URL | Кто | Размер (uncompressed / compressed) | Риск |
|-----|-----|-------------------------------------|------|
| `https://cdn.tailwindcss.com?plugins=forms,typography` → `cdn.tailwindcss.com/3.4.17?plugins=forms@0.5.10,typography@0.5.16` | `app.html:76` | **510 091 / 145 346** | JIT-компилятор в браузере, `unsafe-eval` по сути, supply-chain на каждый запрос, `?plugins=` без pin в HTML |
| `https://cdn.tailwindcss.com` (без pin) | `login.html:31` | тот же CDN, другой URL | «latest»-поведение |
| `https://telegram.org/js/telegram-web-app.js` | оба HTML `:75` / `:14` | 116 510 / 23 731 | **осознанно оставляем**; без него нет `initData` |
| Google Fonts Inter CSS | `app.html:77` | 916 б + **7 woff2 × 4 начертания** ≈ 219 КБ | 4 лишних subset (greek, greek-ext, vietnamese, часть latin-ext) |
| Google Material Symbols Rounded | оба HTML | CSS 650 б + **один woff2 5 373 872 байт** | полный variable font ради **64** глифов |
| `fonts.gstatic.com` | косвенно | см. выше | третья сторона видит каждый запуск Mini App |

500-страница `GET /` отдаёт traceback в HTML (`render_page.py:363`) — утечка путей. Не в scope frontend-модулей, но зафиксировано.

### 2.6 DoS / polling / payload

| Место | Лимит | Зазор |
|-------|-------|-------|
| Auth IP | slowapi `30/minute` (`_core.py:24`) | ок |
| Email per-address | 30 / 60 с | ок |
| Support create/send/upload | 5/ч, 8/сутки, 20/мин, 8 upload/мин, 1.5 с gap, 200 сообщений/тикет | ок |
| Support polling 5 с | **нет** серверного лимита на `/api/support/status` | при открытой вкладке вечный GET-эквивалент POST каждые 5 с |
| `/api/check-payment` | клиентский backoff; серверного лимита нет | один pid, 40 мин |
| `/api/device-tiers` | нет auth, нет лимита | дешёвый JSON |
| `refreshAppData` | полный SSR | после каждой успешной покупки |
| Comment payload | нет max length | раздувание карточки / XSS |
| `GET /` без cache (`_app.py:31–38`) | каждый заход — полный HTML 333 КБ + CDN | Этап 1 режет CDN |

### 2.7 Утечки через ответы API

| Endpoint | Контракт, который нельзя сломать |
|----------|----------------------------------|
| `/api/check-payment` | чужой/нет id → `{ok:true, paid:false}` без `processing`/`balance`/`message` об успехе |
| ticket-file | 404 одинаковый для «нет», «чужой», «нет файла» |
| `/ticket_files` | 404, не 401/403 |
| payment create ошибки | не раскрывать чужие payment_id |

---

## 3. Внешние ресурсы и план локализации

### 3.1 Матрица origins (факт)

| Директива | Сейчас нужно | После Этапа 1 | После Этапа 7 |
|-----------|--------------|---------------|---------------|
| `default-src` | не задано | `'self'` | `'self'` |
| `script-src` | любой (нет CSP) + Tailwind eval | `'self' https://telegram.org` + временный `'unsafe-inline'` (inline JS ещё жив) | `'self' https://telegram.org` (без inline) |
| `style-src` | Google Fonts + Tailwind inject + inline `<style>` | `'self'` + временный `'unsafe-inline'` | `'self'` (+ hash critical, если останется) |
| `font-src` | `fonts.gstatic.com` | `'self'` | `'self'` |
| `img-src` | `'self'` + `https:` (лого админа может быть внешним URL) + `data:` (QR нет в Mini App, но logo fallback) | `'self' https: data:` | сузить logo до `'self'` |
| `connect-src` | `'self'` + telegram.org (SDK XHR?) | `'self'` (+ `https://telegram.org` если SDK стучится) | то же |
| `frame-ancestors` | нет | `'none'` | `'none'` |
| `base-uri` / `form-action` | нет | `'self'` | `'self'` |

Telegram SDK **не вендорить** в Этапе 1. Если `Telegram.WebApp` нет — UI на русском: «Откройте приложение через Telegram» / ограниченный email-режим. Сейчас при отсутствии SDK `getTgInitData()` → `''`, Stars/TON сервер отвергнет; иконки Google Fonts просто не рисуются (пустые квадраты) — это и надо заменить локальным шрифтом/SVG.

### 3.2 Что скачать и как собрать

**Inter (только используемые начертания 400/500/600/700, subset `cyrillic` + `latin`):**

Источник: [github.com/rsms/inter](https://github.com/rsms/inter) release, файлы `Inter-Regular.woff2` … `Inter-Bold.woff2`, либо google-webfonts-helper с теми же subset. Не тянуть greek / vietnamese. Ожидаемый размер: **~70–90 КБ** вместо ~219 КБ × неявного кэша Google.

Зафиксировать: URL релиза, git tag, sha256 каждого `.woff2` в `src/shop_bot/webapp/static/vendor/SOURCES.md`.

**Иконки:** 64 уникальных имени:

`account_balance add add_card alternate_email arrow_back arrow_forward attach_file autorenew block bolt calendar_today card_giftcard chat check check_circle chevron_left chevron_right close confirmation_number content_copy delete delete_sweep devices download edit edit_note expand_more group groups history home hourglass_top info key key_off lightbulb local_offer lock_person lock_reset logout mail manage_accounts more_horiz open_in_new payment payments person pin progress_activity public receipt receipt_long redeem refresh save schedule search send settings shopping_bag support_agent sync update wallet` (+ `sticky_note_2` из server HTML).

Вариант A (рекомендую): subset Material Symbols Rounded через [google/material-design-icons](https://github.com/google/material-design-icons) + `fonttools subset` только этих ligature — один woff2 **≪ 100 КБ**.  
Вариант B: 64 локальных SVG в `static/icons/` и замена `<span class="material-symbols-rounded">name</span>` на `<img>`/`<svg>` — больше правок разметки, зато нет шрифта.

Не класть полный 5.3 МБ font.

**Tailwind:**

- `package.json` с **точными** версиями: `tailwindcss@3.4.17`, `@tailwindcss/forms@0.5.10`, `@tailwindcss/typography@0.5.16` (те, что сейчас отдаёт CDN). Никакого `latest`.
- `tailwind.config.js` = текущий `tailwind.config` из `app.html:81–103` + `content: ['./app.html','./login.html','./js/**/*.js','./web_router/**/*.py']` (server HTML тоже содержит классы).
- Сборка: `npx tailwindcss -i ./static/css/input.css -o ./static/css/app.css --minify`.
- Артефакт `app.css` коммитить (воспроизводимо) **или** собирать в CI одним шагом — выбрать в Этапе 1 и описать в README webapp. Предпочтение: коммитить min.css, чтобы деплой без Node работал как сейчас.
- Ожидаемый размер purged CSS: **30–80 КБ** вместо 510 КБ runtime.

**Не локализовать:** `https://telegram.org/js/telegram-web-app.js`.

### 3.3 Временные CSP-исключения (Этап 1)

| Исключение | Почему | Снятие |
|------------|--------|--------|
| `script-src 'unsafe-inline'` | 4 inline-блока JS + `tailwind.config` + login IIFE | Этап 2 (вынос JS) + Этап 7 |
| `style-src 'unsafe-inline'` | `<style>` в `app.html:106–274, 1911–1981`, `{{ tg_fullscreen_css }}`, style= на страницах | Этап 1b вынос CSS; `tg_fullscreen` → класс + `app.css` |
| `script-src https://telegram.org` | SDK | остаётся |

Не включать `unsafe-eval`, `*`, `cdn.tailwindcss.com`, `fonts.googleapis.com`.

---

## 4. Целевая структура модулей

Предложение совпадает с заданием, с тремя уточнениями.

```
src/shop_bot/webapp/
├── app.html                 # shell: контейнеры экранов, локальные CSS, один <script type="module" src="/static/js/app.js">
├── login.html               # shell логина + /static/js/login.js
├── static/
│   ├── css/app.css          # purged Tailwind + critical
│   ├── css/fonts.css        # @font-face Inter + icons
│   ├── fonts/*.woff2
│   ├── icons/               # если вариант SVG
│   └── vendor/SOURCES.md    # url, версия, sha256
└── js/
    ├── app.js               # единственный entry Mini App
    ├── login.js             # единственный entry логина
    ├── core/
    │   ├── api.js           # fetch + token + init_data + AbortController
    │   ├── store.js         # user, balance, keys, activePage, pending*
    │   ├── refresh.js       # invalidate / TTL / inflight de-dupe
    │   ├── router.js        # hash, без reload
    │   ├── dom.js           # escapeHtml, textContent helpers
    │   └── telegram.js      # WebApp, theme, haptic, initData; fallback без SDK
    ├── views/{home,keys,finance,referral,support,profile,auth}.js
    └── components/{modal,toast,key-card,payment-status}.js
```

Уточнения:

1. `login.js` отдельно — иначе entry app потянет платежный код на экран входа.
2. `core/dom.js` обязателен с первого выноса JS: общий `escapeHtml`, запрет новых `innerHTML` без него.
3. Карточки ключей: Этапы 2–3 оставляют server `card_html` как доверенную зону (после #145 — уже с `_esc_text`). Перевод на JSON+`key-card.js` — отдельный PR после Этапа 3, не смешивать с выносом скрипта.
4. Раздача: `StaticFiles` на `/static` (новый mount). **Не** ставить root webapp. `/ticket_files` guard оставить. `app.js` не должен попасть под `no-store` всего HTML — для JS/CSS нужен cache + content hash или `?v=`.

Store (не содержит секретов, цен как истины, прав):

```js
{
  user: null,            // id, email mask — с /api/user-status
  balance: null,
  referralBalance: null,
  keys: [],              // JSON, не HTML
  gifts: [],
  activePage: 'home',
  pendingPayment: null,  // id/url/ts — как сейчас в LS
  pendingTopUp: null,
  loading: new Set(),
  updatedAt: {}
}
```

---

## 5. Порядок PR и риски

Каждый PR: `compileall` затронутого Python, полный `pytest -q` = 735 (или зафиксированный новый счёт), статические проверки из задания.

| PR | Содержание | Нельзя | Риск | Откат |
|----|------------|--------|------|-------|
| **0** (этот) | Только документ | любой код | — | — |
| **1. Локальные ресурсы + CSP groundwork** | woff2 + fonts.css; purged `app.css`; убрать 4 CDN-ссылки; mount `/static`; `SOURCES.md`; CSP с `unsafe-inline`; fallback без Telegram SDK (русский текст, не пустые иконки) | менять JS-логику, API, auth | сломанная вёрстка (не все классы в content), FOUC, SDK timeout | вернуть CDN-теги |
| **2. Вынос JS + compatibility bridge** | разрезать 4 скрипта в модули **без смены порядка init**; каждый живой onclick → `window.fn = fn`; тесты: нет CDN JS кроме telegram.org, нет eval/new Function | менять UX, удалять onclick, дублировать fetch | гонка инициализации (token снимается в head **до** SDK — сохранить этот порядок), сломанный `tailwind.config` (его уже не будет) | один HTML-файл как сейчас |
| **3. Store + без reload** | `refreshAppData` и 6 `location.reload` → invalidate+patch; кнопка «Обновить» не сбрасывает hash/modal; success top-up/purchase обновляет сущности из таблицы §1.6 | бессистемный fetch всего; innerHTML без escape; менять API | пропущенный ребиндинг `.key-toggle`; устаревший ответ перерисует новый экран (нужен AbortController + generation) | вернуть reload |
| **4. API/TTL/Abort/polling** | de-dupe `/api/user-status`; TTL на device-tiers / payment-methods / hosts; support poll только видимой вкладке + backoff; не дергать `GET /` | общий бесконечный poll баланса | stale methods после смены настроек админом | увеличить TTL=0 |
| **5. onclick → addEventListener** | пакетами по экранам: support, finance, keys, payment. После каждого пакета удалять соответствующий bridge | один большой bang | пропущенная server-rendered кнопка | bridge остаётся |
| **6. JSON-карточки ключей** (отдельное согласование) | `/api/keys/search` и gifts отдают модель, не HTML; `key-card.js` | менять расчёт цен/выдачу | регресс кнопок LTE/renew | поле `html` оставить на переходный период |
| **7. CSP ужесточение** | снять `'unsafe-inline'`; удалить оставшиеся bridge; запрет новых inline в тесте | ослаблять CSP «чтобы заработало» | что-то ещё inline (tg_fullscreen, style=) | временно hash-csp |

**Не в этих PR (нужно отдельное «да»):**

- проверка владельца `key_id` в `/api/create-payment` extend;
- отказ принимать `req.tier_price` (считать только с `get_device_tiers`);
- HttpOnly cookie + CSRF;
- экранирование `comment_key`/`user_key_name` на сервере — **сделано отдельно:** PR [#145](https://github.com/Xatabchik/Xatabchik/pull/145), не в этом документе и не в Этапах 1–7. См. §2.1a;
- доказанные остатки user-stored XSS (X10 email, X14/X15 реквизиты) — тоже отдельные security PR, не Этап 1;
- traceback 500 на `GET /`.

---

## 6. Compatibility bridge (Этап 2)

Пока в HTML есть `onclick="name("` или `window.name =`, имя остаётся на `window`.

**Вызываются из разметки (60):**  
`_addReferralPayoutMethod`, `_cancelProfileEmailChange`, `_deletePayoutMethod`, `_loadProfileMain`, `_loadReferralPayoutMethods`, `_renderPayoutTypeStep`, `_renderProfileChangeEmailRequest`, `_renderProfileChangePassword`, `_renderProfileVerifyEmailCode`, `_renderTopUpAmountStep`, `_reopenTopUpPaymentLink`, `_resendProfileEmailChangeCode`, `_selectPayoutBankByIndex`, `_selectPayoutType`, `_selectWithdrawMethod`, `_stopTrackingTopUp`, `_submitPayoutMethod`, `_submitProfileChangeEmailRequest`, `_submitProfileChangePassword`, `_submitProfileVerifyEmailCode`, `_submitTopUpPayment`, `_submitWithdrawRequest`, `_topUpContinueToMethods`, `activateOwnGift`, `applyDiscountPromo`, `cancelPayment`, `changeGiftsPage`, `changePaymentStep`, `changeProfileKeysPage`, `clearKeysSearch`, `closeActionModal`, `closePaymentModal`, `closeSupportTicket`, `confirmMethod`, `copySuccessKey`, `copyToClipboard`, `createSupportTicket`, `deleteAllDevices`, `deleteDevice`, `goToPaymentLink`, `loadTransactions`, `navigateTo`, `openActionModal`, `openLinkSafe`, `openMethodsList`, `openReferralMethodsModal`, `openTopUpModal`, `processPayment`, `renameKey`, `requestReferralWithdraw`, `resetSupportChat`, `saveComment`, `sendSupportMessage`, `setPurchaseMode`, `switchKeysTab`, `toggleInfoBlock`, `toggleRenewInfoBlock`, `toggleSettingsMenu`, `verifyPlategaPayment`, `verifyPlategaTopUp`.

**Плюс из server HTML:** `copyKey`, `openLinkSafe`, `openActionModal`, `goToRenewKey`, `toggleKeyAutoRenew`, `openLteTopup`, `selectPlan`, `selectServer`, `syncTelegram`, `activateOwnGift`, `toggleKeyCard`.

Документировать фактический список в `js/bridges.js` комментарием; тест Этапа 2 читает его и сверяет с `onclick=` в HTML/py.

---

## 7. Baseline

### 7.1 Тесты

Команда: `python3 -m pytest -q`  
Результат на `main` (`e1ae3c7`): **735 passed** (collect-only: 735).  
`python3 -m compileall -q src/shop_bot` — чисто.

Существующие тесты, которые нельзя сломать (платежи / auth / IDOR / support / frontend-структура):

- `tests/test_webapp_idor_authorization.py`
- `tests/test_webapp_telegram_only_methods.py`
- `tests/test_check_payment_fulfilled.py`
- `tests/test_check_payment_authorization.py`
- `tests/test_webapp_payment_poll.py`
- `tests/test_webapp_topup_modal.py`
- `tests/test_platega_webapp_verify.py`
- `tests/test_webapp_lte_topup.py`
- `tests/test_webapp_support_tickets.py`
- `tests/test_webapp_referral_balance_payment.py`
- `tests/test_no_send_without_telegram_chat.py`
- `tests/test_create_payment*.py` (несколько файлов)
- `tests/test_webapp_router_split.py`

После каждого этапа: то же число **735** (или **741** после мержа #145), плюс новые статические тесты (CDN/eval/CSP) — тогда новое baseline фиксируется в отчёте PR.

### 7.2 Размер и сеть при первом открытии (сейчас)

Минимум запросов **до** действий пользователя (авторизованный `GET /`):

| # | Ресурс | Куда | Байт ≈ |
|---|--------|------|--------|
| 1 | документ | `'self'` | 333 КБ HTML |
| 2 | Telegram SDK | telegram.org | 117 КБ (24 КБ br) |
| 3 | Tailwind runtime | cdn.tailwindcss.com | 510 КБ (145 КБ br) |
| 4 | Inter CSS | fonts.googleapis.com | 1 КБ |
| 5–11 | Inter woff2 × subset × вес | fonts.gstatic.com | до ~219 КБ (браузер берёт нужные unicode-range) |
| 12 | Material Symbols CSS | fonts.googleapis.com | 1 КБ |
| 13 | Material Symbols woff2 | fonts.gstatic.com | **5.4 МБ** |

Порядок величины первого экрана: **~6 МБ** неупакованных шрифтов+CDN, из них 5.4 МБ — иконки. После Этапа 1 цель: документ + `app.css` (~50 КБ) + 2–4 woff2 Inter (~80 КБ) + icon subset (<100 КБ) + Telegram SDK. Внешние origin: только `telegram.org`.

`login.html` — тот же Tailwind + Material Symbols, без Inter.

### 7.3 Сценарии, которые нельзя сломать

1. Вход Telegram (`init_data` / pairing token) и вход email + verify + reset.
2. Список ключей, rename, заметка, устройства, delete-all, auto-renew, LTE.
3. Покупка / продление: выбор сервера и тарифа, промокод, методы, создание счёта, `processing`, успех, ссылка ключа.
4. Пополнение: сумма → метод → ожидание (restore из LS) → processing → успех с балансом; кнопка «Вернуться к вводу суммы» не отменяет внешний счёт.
5. Stars/TON только с живым `init_data`.
6. Рефералка, реквизиты, вывод, подарки, активация.
7. Поддержка: список, чат, upload, файл только владельцу, 404 чужому.
8. Профиль: пароль, смена email.
9. Refresh/данные не сбрасывают hash и открытую payment-модалку.
10. Чужой `payment_id` — нейтральный ответ. `/ticket_files` — 404. Токена бота нет в HTML/JS.

### 7.4 Замеры, которые повторить после Этапа 1 и 3

- вес `app.html` (цель Этапа 2: ≪ 1000 строк, без бизнес-JS);
- число запросов DevTools при cold open;
- число `/api/user-status` при переключении home↔finance (сейчас 2 независимых);
- число `location.reload` в исходниках (цель Этапа 3: 0 для действий пользователя).

---

## 8. Решение, которое нужно от вас

Код не меняю, пока не будет «да» по Этапу 0. Конкретно прошу согласовать:

1. Порядок PR 1→2→3→4→5→7, а **PR 6 (JSON-карточки)** — после 3 и отдельно.
2. ~~Между 0 и 1: маленький PR на escape карточки ключа~~ — **сделано** [#145](https://github.com/Xatabchik/Xatabchik/pull/145). Осталось согласовать отдельные PR на X10 (email) и X14/X15 (реквизиты) — да / нет / не сейчас.
3. Иконки: subset Material Symbols (A) или SVG (B).
4. `app.css` коммитить в репозиторий (деплой без Node) — да / собирать в Docker.
5. Telegram SDK оставляем на `telegram.org` — да (рекомендация).

После «да» — Этап 1 отдельной веткой `cursor/webapp-local-assets-csp-35c7`.
