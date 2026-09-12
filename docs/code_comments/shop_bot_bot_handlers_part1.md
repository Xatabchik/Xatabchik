# Комментарии: `src/shop_bot/bot/handlers.py` (часть 1)

Модульного docstring нет. Пользовательский Telegram-магазин: онбординг, капча, профиль, подарки, докупка ГБ/LTE, сброс пула, пополнение баланса и создание счетов. Выдача услуги — `process_successful_payment` (часть 2, в этот файл не входит); из этой половины она только **вызывается** (баланс, Stars `successful_payment`, кнопки «Проверить»).

Инвентарь: `_is_true` … `get_user_router.topup_pay_tonconnect` (до `referral_program_handler`). Клавиатуры докупки/LTE/reset/top-up смотрят в модульный кэш `PAYMENT_METHODS` (пишет `BotController.start`, **без platega**), а не в `_get_payment_methods()`.

---

## `_is_true` (122–123)

**Docstring в коде:** нет

```
"""True, если строка value в true/1/on/yes/y (регистр не важен)."""
```

Вызывается из `_get_payment_methods` (yoomoney / stars).

## `_get_payment_methods` (125–175)

**Docstring в коде:** есть (дословно):

```
Собирает доступные способы оплаты из актуальных настроек (без перезапуска бота).
```

Читает `get_setting` (БД). **Не** вызывается хендлерами этой части — те берут `PAYMENT_METHODS`.

| Ключ | Вкл., если |
|------|------------|
| `yookassa` | shop_id и secret_key |
| `heleket` | merchant_id и api_key |
| `platega` | merchant_id и secret |
| `rollypay` | api_key и signing_secret (оба strip) |
| `cryptobot` | token |
| `tonconnect` | ton_wallet_address и tonapi_key |
| `yoomoney` | флаг `None` → wallet+secret; иначе `_is_true(флаг)` (кошелёк не проверяется) |
| `stars` | `_is_true(stars_enabled)` и `stars_per_rub > 0` (ошибка float → 0) |

`balance` / `referral_balance` в dict нет.

## `_classify_key_creation_error` (190–213)

**Docstring в коде:** нет

```
"""Разобрать исключение панели: код (A019/400/404/status), описание из `errors`, detail ≤200 симв."""
```

Из `str(exc)` ищет `request failed: <digits> ...`. A019 — username already/exists/occupied/taken/занят. Иначе код = HTTP status из regex или `"400"`.

## `_format_key_action_label` (216–228)

**Docstring в коде:** нет

```
"""Человеческая метка действия ключа: new/extend/trial/gift или сырой action."""
```

`new`/`gift` — опционально `price` RUB; `extend` — `#key_id` и цена; `trial` — «пробный ключ»; иначе `action` или «операция».

## `_log_key_creation_error` (231–240)

**Docstring в коде:** нет

```
"""logger.error Key creation error: utcnow, user_id, action, code, detail."""
```

Только лог, без БД/Telegram.

## `_notify_admins_key_creation_error` (243–268)

**Docstring в коде:** нет

```
"""Разослать админам (rw_repo.get_admin_ids) текст ошибки создания ключа; сбой send_message глотается."""
```

Пустой список / ошибка get_admin_ids → return. **Telegram.**

## `_notify_user_key_creation_error` (271–308)

**Docstring в коде:** нет. В коде `#`: у франшизы сначала пробуем токен клона.

```
"""Написать пользователю «не удалось создать ключ» (+«средства возвращены» при refund) и клавиатуру поддержки."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 287–304 | factory_bot_id > 0 | `get_managed_bot` → временный `Bot(token)`, send, close |
| 305–308 | иначе / fallback | `bot.send_message` основному боту |

**БД:** get_managed_bot. **Telegram.** Ошибки send игнор.

## `_handle_key_creation_failure` (311–329)

**Docstring в коде:** нет

```
"""classify → лог → уведомить пользователя и админов. Сам refund не делает (флаг только для текста)."""
```

## `_abort_topup_fulfillment` (332–413)

**Docstring в коде:** есть (дословно):

```
Компенсирующая транзакция при сбое применения оплаченной докупки трафика.

    Аналог `_abort_key_fulfillment` для докупки ГБ/LTE (там сообщения про создание ключа
    неуместны). Раньше эти ветви просто писали пользователю «не удалось применить» и
    выходили: платёж оставался помеченным в `processed_payments`, повторная доставка
    вебхука отбрасывалась, автовозврата не было — деньги списаны, услуга не оказана.

    1) снимает idempotency-lock (чтобы ретрай вебхука мог применить докупку заново),
    2) один раз возвращает средства (Balance / ReferralBalance / внешние → баланс),
    3) уведомляет пользователя и админов.

    Возвращает True, если refund реально зачислен (первичный вызов).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 355–359 | unclaim + reset_pending | снять lock; Exception → pass |
| 361–368 | price > 0 | `refund_payment_once`; ошибка → did_refund=False |
| 387–393 | Telegram user | «оплата получена, применить не удалось» + support kb |
| 395–412 | Telegram admins | get_admin_ids, текст с payment_id/reason/refund |

## `_notify_admins_topup_desync` (416–453)

**Docstring в коде:** есть (дословно):

```
Докупка применена на VPN-сервере, но не сохранилась в БД бота.

    Возврат средств здесь недопустим (услуга фактически оказана), но расхождение нужно
    починить вручную: локальный `traffic_boost_bytes` используется при ежемесячном сбросе
    лимита, и без него бот вернёт ключ к базовому лимиту тарифа.
```

Лог `TOPUP_DB_DESYNC` + Telegram админам. **Refund нет.**

## `_abort_key_fulfillment` (456–514)

**Docstring в коде:** есть (дословно):

```
Компенсирующая транзакция при сбое выдачи ключа после оплаты.

    1) снимает idempotency-lock (webhook может ретраить),
    2) один раз возвращает средства (Balance / ReferralBalance / внешние → баланс),
    3) уведомляет пользователя и админов.

    Возвращает True, если refund реально зачислен (первичный вызов).
```

Как topup-abort: unclaim + reset + `refund_payment_once` (при успехе лог `PAYMENT_ROLLBACK`) → `_handle_key_creation_failure` с `refund=did_refund`. Если передан `processing_message` — `edit_text(fail_text)`.

## `_safe_edit_or_answer` (516–529)

**Docstring в коде:** есть (дословно):

```
Заменить `message.edit_text(...)` там, где предыдущее сообщение может
    оказаться нетекстовым (счёт на оплату Stars/ЮKassa, фото рассылки и т.п.) —
    у таких сообщений нет текста для редактирования, и Telegram отвечает
    `Bad Request: there is no text in the message to edit`. В этом случае
    вместо падения хендлера отправляем новое сообщение с тем же контентом.
```

`TelegramBadRequest` на edit → `answer`; второй BadRequest → pass.

## `_format_duration_label` (532–543)

**Docstring в коде:** нет

```
"""«N дн.», если duration_days > 0; иначе «N мес.» или «—»."""
```

Нечисло → 0.

## `_compute_days_to_add` (546–557)

**Docstring в коде:** нет

```
"""Дни к сроку: duration_days если > 0, иначе months * 30."""
```

## `_tariff_label_from_origin` (560–570)

**Docstring в коде:** есть (дословно):

```
Human label for subscription page tariff line.

    Requirement: show "30 дней" depending on how the key was obtained.
```

`is_trial` → «триал»; иначе `f"{days} дней"` или «—».

## `_build_key_origin_meta` (573–600)

**Docstring в коде:** есть (дословно):

```
Store key origin info inside vpn_keys.description as JSON.

    We use this later to correctly render "🕒 Тариф:" even if host plans change.
```

JSON `v=1`, source, is_trial, plan_id/name, months, duration_days, tariff_label; опционально `note`. `ensure_ascii=False`, separators без пробелов.

## `grant_referrer_day_bonus_for_trial` (603–742)

**Docstring в коде:** есть (дословно):

```
Начислить рефереру +1 день только в момент активации триала рефералом.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 606–610 | user_id невалиден | return |
| 612–623 | нет referred_by / флаг уже получен | return (идемпотентность) |
| 626–631 | enable_referral_days_bonus ≠ `"true"` | return (строго `== "true"`, не `_is_true`) |
| 637–638 | referrer ≤ 0 или self | return |
| 685–690 | ключи реферера | активный с max expiry, иначе самый дальний |
| 693–703 | host | ключ → setting `referral_days_bonus_host` → первый get_all_hosts |
| 711–722 | HTTP Remnawave | `create_or_update_key_on_host(..., days_to_add=1)`; нет result → return |
| 724–732 | БД | `record_key_from_payload` (ошибка игнор) |
| 734–737 | БД | `set_referral_trial_day_bonus_received` |
| 739–742 | Telegram | «+1 день…» рефереру |

Без ключа email = `tg{id}+trialref{ts}@ref.local`.

### `grant_referrer_day_bonus_for_trial._parse_exp_dt` (649–677)

**Docstring в коде:** нет. В коде `#`: нормализуем ISO / запасной парсер.

```
"""Разобрать expiry в aware UTC datetime или None (isoformat, затем strptime)."""
```

`Z` → `+00:00`; пробел → `T`; naive → UTC. Fallback: `%Y-%m-%d %H:%M:%S` / `%H:%M` / дата.

## `_webapp_public_base` (745–759)

**Docstring в коде:** есть (дословно):

```
Публичный базовый URL Mini App, если webapp включён и задан домен.

    В настройках домен хранится без схемы (app.example.com) — для ссылок,
    которыми делятся из бота, добавляем https://.
```

`database.get_webapp_settings()`: нет `webapp_enabled` или пустой domain → None. Схема не `http(s)` → префикс `https://`.

## `_build_gift_links` (762–771)

**Docstring в коде:** есть (дословно):

```
Построить обе ссылки активации подарка: в мини-приложении (webapp) и в Telegram.

    Возвращает (webapp_link, telegram_link) — то же самое, что показывает
    веб-приложение на своей странице подарков.
```

Web: `get_setting("webapp_domain")` + `/gift/{code}` **без** `_webapp_public_base` (схему не добавляет). TG: `t.me/{TELEGRAM_BOT_USERNAME}?start=gift_{code}` или None.

## `_build_referral_links` (774–784)

**Docstring в коде:** есть (дословно):

```
Построить реферальные ссылки: (webapp_link, telegram_link).

    Веб-ссылка возвращается только если Mini App включён в настройках
    и задан webapp_domain — иначе None.
```

TG username: аргумент → `TELEGRAM_BOT_USERNAME` → `telegram_bot_username`. Web: `{_webapp_public_base()}/ref/{id}`.

## `_referral_share_text` (791–794)

**Docstring в коде:** есть (дословно):

```
Текст для t.me/share из настроек (Контент → referral_share_text).
```

Пусто → `DEFAULT_REFERRAL_SHARE_TEXT`.

## `_gift_share_text` (797–800)

**Docstring в коде:** есть (дословно):

```
Текст для t.me/share при шаринге подарка (Контент → gift_share_text).
```

Пусто → `DEFAULT_GIFT_SHARE_TEXT`.

## `_telegram_share_url` (803–812)

**Docstring в коде:** есть (дословно):

```
Собрать https://t.me/share/url?... с пробелами как %20 (не +).

    Telegram подставляет text в поле ввода как есть; quote_plus даёт «+»
    вместо пробелов, и они остаются плюсами в черновике сообщения.
```

`urlencode(..., quote_via=quote)`.

## `_activate_gift_directly` (815–903)

**Docstring в коде:** есть (дословно):

```
Активировать подарок для пользователя.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 822–827 | нет gift | «не найден» + main_reply_keyboard |
| 829–834 | is_activated | «уже активирован» |
| 837–843 | activate_user_gift False | «не удалось» |
| 846–852 | is_new_user | `set_referred_by_from_gift(user, from_user_id)` |
| 856–886 | есть key_id | generate_key_email + `update_key` (user_id, email, tag="") + меню; ошибка — «активирован, но привязка» |
| 887–896 | нет key / нет key_id | предупреждение, подарок уже activated |
| 898–903 | except | лог + «ошибка при активации» |

**БД:** get_gift_by_code, activate_user_gift, set_referred_by_from_gift, get_key_by_id, generate_key_email_for_user, update_key. **Панель не вызывается.** **Telegram.**

## `_create_heleket_payment_request` (906–1016)

**Docstring в коде:** есть (дословно):

```
    Создание инвойса в Heleket и возврат payment URL.

    Требования API:
      - POST https://api.heleket.com/v1/payment
      - Заголовки: merchant, sign (md5(base64(json_body)+API_KEY))
      - Тело (минимум): { amount, currency, order_id }
      - Дополнительно: url_callback (наш вебхук), description (положим JSON метаданных)
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 923–927 | нет merchant/api_key | None |
| 950–956 | create_payload_pending | PromoUnavailableError → None; прочий Exception — warning, идём дальше |
| 968–976 | domain | `url_callback` = `{domain}/heleket-webhook` |
| 991–1016 | HTTP POST | state==0 и url → return url; uuid → `patch_pending_metadata(heleket_uuid)` |

Метаданные: action/key_id/host/plan/package/email/promo из `state_data`, `payment_method=Heleket`. Сбой HTTP pending **не** откатывает.

## `create_cryptobot_api_invoice` (1018–1065)

**Docstring в коде:** есть (дословно):

```
    Упрощённая обёртка для создания инвойса в Crypto Pay (CryptoBot), используемая
    из webapp (shop_bot/webapp/handlers.py). В отличие от _create_cryptobot_invoice,
    не создаёт pending-транзакцию (это уже делает вызывающий код) и принимает
    готовый payload (обычно payment_id).

    Возвращает (bot_invoice_url, invoice_id) либо None при ошибке.
```

POST `https://pay.crypt.bot/api/createInvoice`, fiat RUB. Успех: `patch_pending_metadata(payload_str, cryptobot_invoice_id)`. **Pending не создаёт.**

## `_create_cryptobot_invoice` (1068–1261)

**Docstring в коде:** есть (дословно):

```
    Создание инвойса в Crypto Pay (CryptoBot) и возврат bot_invoice_url.

    Эндпоинт: POST https://pay.crypt.bot/api/createInvoice
    Заголовки: { 'Crypto-Pay-API-Token': <token>, 'Content-Type': 'application/json' }

    Мы создаём инвойс в фиате RUB, чтобы не конвертировать курсы вручную.
    В payload записываем строку, которую ожидает наш вебхук '/cryptobot-webhook'.
```

`create_payload_pending` (PromoUnavailable → None). Тело: amount fiat RUB, `payload=payment_id`. Список `parts` собирается и **не используется**. Успех: patch `cryptobot_invoice_id`, `(url, invoice_id)`.

По коду: строки 1185–1261 после всех `return` — мёртвый хвост (похоже на Heleket: `price`/`api_key`/`merchant_id` в этой функции не определены). Живой путь заканчивается на 1182.

---

## FSM-классы

### `KeyPurchase` (1263–1265)

**Docstring в коде:** нет

```
"""FSM покупки ключа: хост, затем тариф."""
```

`waiting_for_host_selection`, `waiting_for_plan_selection`.

### `Captcha` (1267–1268)

**Docstring в коде:** нет

```
"""FSM капчи: ждём текстовый или кнопочный ответ."""
```

`waiting_for_answer`.

### `Onboarding` (1270–1271)

**Docstring в коде:** нет

```
"""FSM онбординга: подписка на канал и/или согласие с офертой."""
```

`waiting_for_subscription_and_agreement`.

### `PaymentProcess` (1273–1277)

**Docstring в коде:** нет

```
"""FSM оплаты ключа: email, способ, промо, счёт Stars."""
```

`waiting_for_email`, `waiting_for_payment_method`, `waiting_for_promo_code`, `waiting_for_stars_invoice`.

### `TopUpProcess` (1280–1282)

**Docstring в коде:** нет

```
"""FSM пополнения баланса: сумма, затем способ оплаты."""
```

`waiting_for_amount`, `waiting_for_topup_method`.

### `TrafficGbTopUp` (1285–1287)

**Docstring в коде:** нет

```
"""FSM докупки основного трафика: пакет, способ оплаты."""
```

`waiting_for_package`, `waiting_for_method`.

### `LteGbTopUp` (1290–1292)

**Docstring в коде:** нет

```
"""FSM докупки LTE-трафика: пакет, способ оплаты."""
```

`waiting_for_package`, `waiting_for_method`.

### `MainPoolReset` (1295–1296)

**Docstring в коде:** нет

```
"""FSM платного сброса основного пула: только выбор способа."""
```

`waiting_for_method`.

### `SupportDialog` (1299–1302)

**Docstring в коде:** нет

```
"""FSM тикета в основном боте: тема, текст, ответ."""
```

`waiting_for_subject`, `waiting_for_message`, `waiting_for_reply`. Хендлеры — часть 2.

### `FranchiseStates` (1312–1316)

**Docstring в коде:** нет

```
"""FSM франшизы: токен клона, сумма вывода, банк и значение реквизита."""
```

`waiting_bot_token`, `waiting_withdraw_amount`, `waiting_requisites_bank`, `waiting_requisites_value`. Хендлеры — часть 2.

### `KeyManagement` (1319–1320)

**Docstring в коде:** нет

```
"""FSM переименования ключа."""
```

`waiting_for_rename`. Хендлеры — часть 2.

### `ReferralWithdraw` (1323–1329)

**Docstring в коде:** нет

```
"""FSM реферального вывода/реквизитов/перевода на основной баланс."""
```

`waiting_method_type/bank/value`, `waiting_withdraw_choose_method`, `waiting_withdraw_amount`, `waiting_transfer_amount`. Хендлеры — часть 2.

---

## `is_valid_email` (1332–1333)

**Docstring в коде:** нет

```
"""True, если email совпал с простым regex local@domain.tld."""
```

## `show_captcha` (1336–1375)

**Docstring в коде:** есть (дословно):

```
Показывает капчу пользователю.
```

`create_captcha_challenge` (БД). Нет challenge → «ошибка». FSM `Captcha.waiting_for_answer` + challenge_id/type. `button`: 4 случайных эмодзи, правильный всегда в наборе. `math` (иначе): «введите ответ цифрой» + math kb.

## `show_main_menu` (1378–1506)

**Docstring в коде:** нет. В коде `#`: имя не брать у бота при edit inline; franchise owner.

```
"""Собрать текст профиля/балансов/промо и клавиатуру главного меню; edit или новое сообщение."""
```

**БД:** get_user, get_user_keys, get_user_inactive_gifts, is_admin, get_balance, get_referral_balance, get_setting (channel/chat/promo), resolve_factory_bot_id, get_managed_bot.

| Строки | Блок | Зачем |
|--------|------|--------|
| 1465–1481 | factory_bot_id > 0 | show_partner_cabinet только owner клона |
| 1481 | иначе | show_create_bot = True (root) |
| 1483–1501 | клавиатура | dynamic → fallback static |
| 1503–1506 | edit_message | `_safe_edit_or_answer` / `answer` |

По коду: `(get_setting("channel_link")).strip()` и то же для `chat_link` — без защиты от None.

## `process_successful_onboarding` (1508–1529)

**Docstring в коде:** есть (дословно):

```
Завершает онбординг: ставит флаг согласия и открывает главное меню.
```

`set_terms_agreed` → callback.answer → `show_main_menu(..., edit=True)` (fallback answer) → `state.clear`. Ошибки по шагам глотаются.

## `registration_required` (1531–1544)

**Docstring в коде:** нет

```
"""Декоратор: нет строки пользователя → просьба /start (alert на callback, иначе answer)."""
```

`get_user` есть → вызвать `f`. Иначе не вызывает исходный хендлер.

### `registration_required.decorated_function` (1533–1543)

**Docstring в коде:** нет

```
"""Обёртка: user_id из event.from_user; зарегистрирован — f, иначе текст про /start."""
```

## `_maybe_pay_referral_start_bonus` (1546–1617)

**Docstring в коде:** есть (дословно):

```
Выплатить рефереру фиксированный бонус за регистрацию приглашённого пользователя
    (настройка "Фиксированный бонус при старте по ссылке", referral_reward_type ==
    'fixed_start_referrer'), если это применимо и ещё не выплачено.

    Вынесено в отдельную функцию и вызывается из ВСЕХ путей завершения регистрации
    (обычный /start, капча текстом, капча кнопкой) — раньше эта логика была только в
    прямом /start-хендлере, и если у бота включена капча (а по умолчанию она включена,
    см. initialize_default_button_configs: "captcha_enabled": "true"), приглашённые
    пользователи регистрировались через отдельные капча-хендлеры, где этот бонус вообще
    не начислялся — реферер мог быть корректно привязан (`users.referred_by`), но так и
    не получал вознаграждение при этом типе награды.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1559–1570 | нет/битый referrer / нет user | return |
| 1573–1577 | reward_type ≠ `fixed_start_referrer` | return |
| 1579–1585 | сумма ≤ 0 | return (дефолт 20) |
| 1587–1594 | claim_referral_start_bonus | **до** кредита; False → return |
| 1596–1604 | БД | add_to_referral_balance + add_to_referral_balance_all |
| 1606–1617 | Telegram рефереру | «Начисление за приглашение» |

---

## `get_user_router` (1620–9295)

**Docstring в коде:** нет

```
"""Собрать пользовательский Router (хендлеры ниже) и вернуть его. Вызывают BotController и клоны франшизы."""
```

Часть 1 — вложенные сущности до `topup_pay_tonconnect`. `process_successful_payment` здесь не объявлен.

### `get_user_router.start_handler` (1624–1778)

**Docstring в коде:** нет. `/start`. В коде `#` про auth_/gift_/ref_/utm_ и «не затирать referred_by».

```
"""/start: deep-link auth/gift/ref/utm, капча новым, регистрация, стартовый рефбонус, меню или онбординг."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1630–1642 | `auth_` | register + `confirm_webapp_auth_request`; return (без меню) |
| 1645–1665 | `gift_` | new? → captcha+FSM gift_code или `_activate_gift_directly`; return |
| 1668–1675 | `ref_` | referrer_id если ≠ self |
| 1678–1685 | `utm_` | `log_utm_visit` + `set_user_utm_slug_if_absent` (best-effort) |
| 1692–1716 | captcha_enabled и новый | **не** register до капчи; referred_by в FSM только если пришёл ref; уже passed → register |
| 1717–1719 | иначе | `register_user_if_not_exists` |
| 1727 | бонус | `_maybe_pay_referral_start_bonus` |
| 1729–1735 | agreed_to_terms | приветствие + меню |
| 1741–1753 | нет channel и нет пары terms/privacy; или !show_welcome | `set_terms_agreed` + меню |
| 1755–1778 | welcome | канал и/или оферта + `Onboarding.waiting_for_subscription_and_agreement` |

### `get_user_router.check_subscription_handler` (1781–1806)

**Docstring в коде:** нет. Callback `check_subscription_and_agree` в Onboarding.

```
"""Проверить подписку на канал (если force) и завершить онбординг."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1786–1788 | force выкл или нет URL | `process_successful_onboarding` |
| 1791–1794 | URL без @ и t.me/ | лог, пропуск проверки, onboarding |
| 1796–1802 | get_chat_member | MEMBER/ADMIN/CREATOR → onboarding; иначе alert «не подписались» |
| 1804–1806 | except | alert про админа бота в канале |

**Telegram API** get_chat_member. **БД** в onboarding: set_terms_agreed.

### `get_user_router.onboarding_fallback_handler` (1809–1810)

**Docstring в коде:** нет. Любое сообщение в Onboarding.

```
"""Напомнить нажать кнопку в сообщении выше."""
```

### `get_user_router.captcha_answer_handler` (1817–1900)

**Docstring в коде:** есть (дословно):

```
Обработчик текстового ответа на математическую капчу.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1827–1830 | нет challenge_id | «сессия истекла», state.clear |
| 1835–1855 | success | mark_passed + register + start-бонус; gift_code → activate и return |
| 1857–1893 | success без gift | clear; нет оферты/welcome → set_terms + меню; иначе welcome + Onboarding |
| 1894–1896 | fail | текст ошибки проверки |
| 1898–1900 | except | «ошибка при проверке» |

### `get_user_router.captcha_button_answer_handler` (1903–1998)

**Docstring в коде:** есть (дословно):

```
Обработчик ответа на капчу с выбором кнопки.
```

Callback `captcha_answer:`. Та же регистрация/бонус/gift/онбординг, ответы через `callback.answer(show_alert)` и edit/answer welcome.

### `get_user_router.cancel_captcha_handler` (2001–2005)

**Docstring в коде:** есть (дословно):

```
Отмена капчи.
```

`cancel_captcha`: alert, `state.clear`, `message.delete`.

### `get_user_router.main_menu_handler` (2009–2010)

**Docstring в коде:** нет. Текст «🏠 Главное меню». `@registration_required`.

```
"""Reply-кнопка главного меню → show_main_menu (новое сообщение)."""
```

### `get_user_router.back_to_main_menu_handler` (2014–2016)

**Docstring в коде:** нет. Callback `back_to_main_menu`.

```
"""ACK и show_main_menu с edit_message=True."""
```

### `get_user_router.open_main_menu_handler` (2020–2022)

**Docstring в коде:** нет. Callback `open_main_menu`.

```
"""ACK и show_main_menu с edit_message=False (новое сообщение)."""
```

### `get_user_router.show_main_menu_cb` (2026–2028)

**Docstring в коде:** нет. Callback `show_main_menu`.

```
"""ACK и show_main_menu с edit=True (как back_to_main_menu)."""
```

### `get_user_router.profile_handler_callback` (2032–2102)

**Docstring в коде:** нет. Callback `show_profile`.

```
"""Карточка профиля: траты, VPN-статус, балансы, рефералы; клавиатура тумблеров."""
```

**БД:** get_user, get_user_keys, get_balance, get_referral_count, get_referral_balance_all, get_user_inactive_gifts, is_subscription_expiry_notifications_enabled.

| Строки | Блок | Зачем |
|--------|------|--------|
| 2037–2039 | нет user | alert |
| 2043–2050 | ключи | max expiry активных → get_vpn_active_text; иначе INACTIVE / NO_DATA |
| 2072–2085 | >10 ключей | показать тумблер уведомлений |
| 2088–2090 | non-gift ключи | тумблер автопродления (any auto_renew) |

Текст: `get_profile_text` + баланс + рефстата. `_safe_edit_or_answer` + `create_profile_keyboard`.

### `get_user_router.toggle_expiry_notifications_handler` (2106–2117)

**Docstring в коде:** нет. Callback `toggle_expiry_notifications`.

```
"""Переключить уведомления об истечении и перерисовать профиль."""
```

`toggle_subscription_expiry_notifications` + alert + повторный `profile_handler_callback`. Ошибка → alert.

### `get_user_router.show_inactive_gifts_handler` (2121–2142)

**Docstring в коде:** нет. Callback `show_inactive_gifts`.

```
"""Список неактивированных подарков пользователя (страница 0) или пустой текст."""
```

`get_user_inactive_gifts`. Пусто → «нет подарков». Иначе `create_gifts_management_keyboard(page=0)`.

### `get_user_router.gifts_page_handler` (2146–2173)

**Docstring в коде:** нет. Callback `gifts_page_*`.

```
"""Пагинация списка подарков: сменить reply_markup, текст не трогать."""
```

Битый page → alert. Пустой список → edit «нет подарков».

### `get_user_router.show_gift_handler` (2177–2263)

**Docstring в коде:** нет. Callback `show_gift_*`.

```
"""Карточка подарка: детали ключа с панели, ссылки активации, gift-клавиатура."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2191–2199 | нет gift / from_user_id ≠ user | не найден / «не ваш» |
| 2206–2213 | нет key_id / key | ошибка |
| 2216–2224 | HTTP | `get_key_details_from_host`; нет connection_string → ошибка сервера |
| 2234–2237 | код и не activated | `_build_gift_links` |
| 2240–2258 | UI | `get_key_info_text` + `create_gift_info_keyboard` |

`_get_connected_devices_count` / `_get_devices_list` / `_get_tariff_info_for_key` объявлены во второй половине файла (замыкание роутера).

### `get_user_router.send_gift_link_handler` (2267–2329)

**Docstring в коде:** есть (дословно):

```
Отправка ссылки подарка пользователю.
```

Владелец + gift_code; `_build_gift_links`; обе ссылки + t.me/share (`_gift_share_text`). Нет ни одной ссылки → alert.

### `get_user_router.activate_own_gift_handler` (2333–2366)

**Docstring в коде:** есть (дословно):

```
Активировать собственный неактивированный подарок себе (аналог webapp-кнопки 'Активировать себе').
```

Проверки владельца/activated/кода → `_activate_gift_directly(..., is_new_user=False)`.

---

### `get_user_router._resolve_plan_for_traffic_topup` (2368–2378)

**Docstring в коде:** нет

```
"""Ключ пользователя + план с traffic_limit_bytes > 0; иначе (None, None)."""
```

`get_key_by_id`, `_resolve_plan_id_for_key`, `get_plan_by_id`.

### `get_user_router.traffic_gb_start_handler` (2382–2411)

**Docstring в коде:** нет. Callback `traffic_gb_start_*`.

```
"""Старт докупки ГБ: пакеты плана или отказ; FSM traffic_key_id."""
```

Нет плана/пакетов → текст + back. Иначе `create_traffic_packages_keyboard`. **БД:** get_traffic_packages_for_plan(only_active).

### `get_user_router.traffic_gb_pick_handler` (2415–2458)

**Docstring в коде:** нет. Callback `traffic_gb_pick_{key}_{pkg}`.

```
"""Выбран пакет: цена/ГБ в FSM, экран способов (PAYMENT_METHODS), TrafficGbTopUp.waiting_for_method."""
```

Пакет должен совпасть с plan_id. **БД:** get_traffic_package_by_id, get_balance.

### `get_user_router._traffic_gb_metadata` (2460–2471)

**Docstring в коде:** нет

```
"""metadata докупки ГБ: action=traffic_gb_topup, key/package/size_gb, method, payment_id."""
```

### `get_user_router.trafficgb_pay_balance_handler` (2474–2491)

**Docstring в коде:** нет. Callback `trafficgb_pay_balance` в waiting_for_method.

```
"""Списать основной баланс и сразу process_successful_payment (без провайдера)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2479–2482 | price ≤ 0 | текст, state.clear |
| 2483–2485 | deduct_from_balance False | alert, FSM **не** clear |
| 2486–2491 | ок | payment_id `balance:{uid}:{uuid}`, chat/message_id, clear, fulfillment |

### `get_user_router.trafficgb_pay_referral_balance_handler` (2494–2511)

**Docstring в коде:** нет. `trafficgb_pay_referral_balance`.

```
"""То же с deduct_from_referral_balance и payment_method=ReferralBalance."""
```

Недостаток рефбаланса → alert, FSM жив.

### `get_user_router.trafficgb_pay_yookassa_handler` (2514–2566)

**Docstring в коде:** нет. `trafficgb_pay_yookassa`.

```
"""Создать pending + платёж YooKassa (redirect) на докупку ГБ; кнопка оплаты."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2516–2521 | нет shop/secret | answer, clear |
| 2528–2531 | price ≤ 0 | edit, clear |
| 2537–2540 | create_payload_pending | warning, платёж всё равно |
| 2549–2562 | Payment.create | повтор pending с yookassa_payment_id; клавиатура check |
| 2563–2566 | except | «не удалось», clear |

**HTTP** YooKassa SDK. **БД** pending. **Telegram** edit.

### `get_user_router.trafficgb_pay_platega_handler` (2569–2601)

**Docstring в коде:** нет. `trafficgb_pay_platega`.

```
"""Pending + ссылка Platega на докупку ГБ; сохранить platega_transaction_id."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2572–2575 | !_platega_is_enabled | недоступен, clear |
| 2578–2581 | price ≤ 0 | clear |
| 2585–2590 | create + HTTP | нет url → clear |
| 2591–2601 | ок | повтор pending с txid, kb, clear |

### `get_user_router.trafficgb_pay_rollypay_handler` (2604–2639)

**Docstring в коде:** нет. `trafficgb_pay_rollypay`.

```
"""Pending + ссылка RollyPay (СБП) на докупку ГБ; rollypay_payment_id в metadata."""
```

Ветви как Platega: disabled / price / нет url / успех + повтор pending.

### `get_user_router.trafficgb_pay_heleket_handler` (2642–2678)

**Docstring в коде:** нет. `trafficgb_pay_heleket`.

```
"""Инвойс Heleket через _create_heleket_payment_request (action=traffic_gb_topup)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2647–2650 | price ≤ 0 | clear |
| 2667–2672 | pay_url | generic payment kb, clear |
| 2673–2674 | нет url | «попробуйте другой»; **FSM не clear** |
| 2675–2678 | except | текст, clear |

Pending создаёт хелпер.

### `get_user_router.trafficgb_pay_cryptobot_handler` (2681–2718)

**Docstring в коде:** нет. `trafficgb_pay_cryptobot`.

```
"""Инвойс CryptoBot на докупку ГБ; клавиатура с invoice_id."""
```

Нет result → текст, FSM не clear (кроме except → clear).

### `get_user_router.trafficgb_pay_yoomoney_handler` (2721–2749)

**Docstring в коде:** нет. `trafficgb_pay_yoomoney`.

```
"""Pending + quickpay-ссылка YooMoney на докупку ГБ."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2728–2731 | нет wallet/secret или price≤0 | недоступен, clear |
| 2733–2736 | кошелёк не ≥11 цифр | clear |
| 2737–2740 | price < 1 | минимум 1 RUB, clear |
| 2741–2749 | ок | pending + `_build_yoomoney_link`, kb, clear |

### `get_user_router.trafficgb_pay_stars_handler` (2752–2789)

**Docstring в коде:** нет. `trafficgb_pay_stars`.

```
"""Pending + Telegram invoice XTR на докупку ГБ (курс stars_per_rub)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2757–2760 | price ≤ 0 | clear |
| 2765–2768 | ratio ≤ 0 | Stars недоступны, clear |
| 2769–2785 | ок | stars = max(1, round half-up); answer_invoice payload=payment_id; pending-ошибка только лог |
| 2786–2789 | except invoice | «не удалось», clear |

---

### `get_user_router._resolve_plan_for_lte_topup` (2791–2801)

**Docstring в коде:** нет

```
"""Ключ пользователя + план, для которого should_account_lte_traffic; иначе (None, None)."""
```

### `get_user_router.lte_gb_start_handler` (2805–2836)

**Docstring в коде:** нет. Callback `lte_gb_start_*`.

```
"""Старт докупки LTE: пакеты pool=lte и подпись сквада; FSM lte_key_id."""
```

Нет плана → «не настроена докупка LTE». Нет пакетов → текст с `get_lte_squad_display_label`. Иначе `create_lte_packages_keyboard`.

### `get_user_router.lte_gb_pick_handler` (2840–2884)

**Docstring в коде:** нет. `lte_gb_pick_{key}_{pkg}`.

```
"""Пакет LTE в FSM, способы create_lte_gb_payment_method_keyboard(PAYMENT_METHODS)."""
```

`LteGbTopUp.waiting_for_method`.

### `get_user_router._lte_gb_metadata` (2886–2897)

**Docstring в коде:** нет

```
"""metadata LTE-докупки: action=lte_gb_topup, key/package/size_gb, method, payment_id."""
```

### `get_user_router.ltegb_pay_balance_handler` (2900–2917)

**Docstring в коде:** нет. `ltegb_pay_balance`.

```
"""Списать основной баланс и process_successful_payment для lte_gb_topup."""
```

Ветви как trafficgb balance (`balance:{uid}:{uuid}`).

### `get_user_router.ltegb_pay_referral_balance_handler` (2920–2937)

**Docstring в коде:** нет. `ltegb_pay_referral_balance`.

```
"""Списать рефбаланс и сразу выдать LTE-докупку."""
```

### `get_user_router.ltegb_pay_yookassa_handler` (2940–2992)

**Docstring в коде:** нет. `ltegb_pay_yookassa`.

```
"""Pending + YooKassa redirect на докупку LTE; description «…ГБ LTE-трафика»."""
```

Те же ветви, что trafficgb YooKassa (конфиг / цена / pending warning / Payment.create / ошибка).

### `get_user_router.ltegb_pay_platega_handler` (2995–3027)

**Docstring в коде:** нет. `ltegb_pay_platega`.

```
"""Pending + Platega на LTE; description «Докупка N ГБ LTE»."""
```

### `get_user_router.ltegb_pay_rollypay_handler` (3030–3065)

**Docstring в коде:** нет. `ltegb_pay_rollypay`.

```
"""Pending + RollyPay на LTE."""
```

### `get_user_router.ltegb_pay_heleket_handler` (3068–3104)

**Docstring в коде:** нет. `ltegb_pay_heleket`.

```
"""Heleket-инвойс LTE (action=lte_gb_topup); нет url — FSM не clear."""
```

### `get_user_router.ltegb_pay_cryptobot_handler` (3107–3144)

**Docstring в коде:** нет. `ltegb_pay_cryptobot`.

```
"""CryptoBot-инвойс LTE; нет result — FSM не clear (кроме except)."""
```

### `get_user_router.ltegb_pay_yoomoney_handler` (3147–3175)

**Docstring в коде:** нет. `ltegb_pay_yoomoney`.

```
"""Pending + YooMoney quickpay на LTE (те же проверки кошелька/минимума 1 RUB)."""
```

### `get_user_router.ltegb_pay_stars_handler` (3178–3215)

**Docstring в коде:** нет. `ltegb_pay_stars`.

```
"""Pending + XTR invoice «Докупка LTE»; pending-сбой только лог."""
```

---

### `get_user_router._resolve_key_for_main_reset` (3217–3221)

**Docstring в коде:** нет

```
"""Вернуть ключ, если он есть и user_id совпал; иначе None."""
```

### `get_user_router.main_reset_start_handler` (3225–3292)

**Docstring в коде:** нет. Callback `main_reset_start_*`.

```
"""Экран платного сброса основного пула: цена плана, дата бесплатного сброса, способы."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3235–3237 | нет ключа | «не найден» |
| 3248–3253 | нет плана или traffic_limit ≤ 0 | «безлимитный» |
| 3259–3264 | main_reset_price_rub ≤ 0 | «не настроен» |
| 3267–3292 | ок | next_traffic_reset_at → дата; FSM key+price; `create_main_reset_payment_method_keyboard(PAYMENT_METHODS)` |

В этой части для reset есть только balance / referral / yookassa (нет platega/stars/…).

### `get_user_router._main_reset_metadata` (3294–3303)

**Docstring в коде:** нет

```
"""metadata сброса: action=main_traffic_reset, key_id, method, payment_id."""
```

### `get_user_router.mainreset_pay_balance_handler` (3306–3323)

**Docstring в коде:** нет. `mainreset_pay_balance`.

```
"""Списать баланс и process_successful_payment для main_traffic_reset."""
```

price ≤ 0 → clear; deduct fail → alert.

### `get_user_router.mainreset_pay_referral_balance_handler` (3326–3343)

**Docstring в коде:** нет. `mainreset_pay_referral_balance`.

```
"""Списать рефбаланс и сразу применить сброс пула."""
```

### `get_user_router.mainreset_pay_yookassa_handler` (3346–3397)

**Docstring в коде:** нет. `mainreset_pay_yookassa`.

```
"""Pending + YooKassa «Досрочный сброс основного пула трафика»."""
```

Ветви как другие YooKassa-create (конфиг / цена / pending warning / create / ошибка).

---

### `get_user_router.topup_start_handler` (3401–3407)

**Docstring в коде:** нет. Callback `top_up_start`.

```
"""Спросить сумму пополнения (10…100000 RUB), FSM TopUpProcess.waiting_for_amount."""
```

### `get_user_router.topup_amount_input` (3410–3432)

**Docstring в коде:** нет. Сообщение в waiting_for_amount.

```
"""Разобрать сумму (запятая→точка), проверить пределы, показать способы top-up."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3412–3416 | не Decimal | «корректную сумму» |
| 3417–3419 | ≤ 0 | «положительной» |
| 3420–3422 | < 10 | минимум |
| 3423–3425 | > 100000 | максимум |
| 3426–3432 | ок | quantize 0.01, FSM topup_amount, `create_topup_payment_method_keyboard(PAYMENT_METHODS)` |

FSM **не** clear на ошибке ввода.

### `get_user_router.topup_pay_yookassa` (3435–3516)

**Docstring в коде:** нет. `topup_pay_yookassa` в waiting_for_topup_method.

```
"""Pending action=top_up + YooKassa (опциональный receipt из receipt_email); кнопка оплаты."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3442–3445 | нет shop/secret | clear |
| 3452–3455 | amount ≤ 0 | clear |
| 3462–3475 | receipt_email валиден | receipt в payload |
| 3485–3488 | pending | warning, идём дальше |
| 3499–3512 | Payment.create | pending с yookassa_payment_id, kb |
| 3513–3516 | except | «не удалось», clear |

### `get_user_router.create_stars_invoice_handler` (3520–3610)

**Docstring в коде:** нет. `pay_stars` в PaymentProcess.waiting_for_payment_method (покупка ключа, не top-up).

```
"""Счёт Stars на тариф: pending обязателен; invoice XTR и FSM waiting_for_stars_invoice."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3524–3527 | нет plan | clear |
| 3536–3539 | stars_per_rub ≤ 0 | clear |
| 3563–3571 | create_payload_pending не ok | «не удалось подготовить», **invoice нет**, FSM жив |
| 3576–3581 | UI | delete сообщения или снять markup |
| 3584–3599 | answer_invoice | payload=payment_id; сохранить chat/message id; state stars invoice |
| 3600–3609 | except | `cancel_pending_transaction`, сообщение об ошибке |

Метаданные: action/key/host/plan/email из FSM покупки, method «Telegram Stars».

### `get_user_router.payment_stars_back_handler` (3612–3669)

**Docstring в коде:** нет. Callback `payment_stars_back`.

```
"""Отменить pending Stars (если свой и pending), удалить invoice, вернуть экран способов."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3618–3620 | status == paid | alert, выход |
| 3622–3631 | pending | чужой user_id → «недействителен»; свой → `cancel_pending_transaction` |
| 3633–3638 | нет plan_id | «сессия устарела» |
| 3646–3657 | invoice msg | delete или снять markup |
| 3659–3668 | ок | обнулить stars_* в FSM, waiting_for_payment_method, `show_payment_options` |

`show_payment_options` объявлен во второй половине роутера.

### `get_user_router.topup_stars_handler` (3672–3718)

**Docstring в коде:** нет. `topup_pay_stars`.

```
"""Pending top_up + XTR invoice на сумму пополнения; сбой pending только лог."""
```

amount≤0 / ratio≤0 → clear. Invoice payload=payment_id, затем clear. Ошибка invoice → edit, clear. **В отличие от create_stars_invoice_handler, отсутствие pending не блокирует invoice.**

### `get_user_router.pre_checkout_handler` (3722–3741)

**Docstring в коде:** нет. Любой `pre_checkout_query`.

```
"""ACK Stars pre-checkout: отклонить, если pending cancelled/canceled/paid; иначе ok=True."""
```

`invoice_payload` → `get_pending_status`. Ошибки answer глотаются.

### `get_user_router.stars_success_handler` (3745–3804)

**Docstring в коде:** нет. `successful_payment`.

```
"""Закрыть pending Stars и вызвать process_successful_payment; fallback top_up из суммы Stars."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3750–3751 | нет payload | return |
| 3753–3755 | cancelled/canceled | игнор |
| 3756–3758 | find_and_complete_pending_transaction | основной путь |
| 3760–3768 | нет meta | latest pending пользователя, если method Telegram Stars → complete по его pid |
| 3769–3793 | всё ещё нет | total_amount Stars / stars_per_rub → синтетический top_up; иначе return |
| 3795–3804 | ок | tg_username в meta, fulfillment, state.clear |

---

### `get_user_router._rollypay_is_enabled` (3808–3812)

**Docstring в коде:** нет

```
"""True, если заданы rollypay_api_key и rollypay_signing_secret."""
```

### `get_user_router._create_rollypay_payment_link` (3814–3829)

**Docstring в коде:** нет

```
"""HTTP RollyPayAPI.create_payment: сумма, description, payment_id, return t.me/bot, method из настроек."""
```

Возвращает то, что вернул клиент (pay_url, provider_id). **HTTP.**

### `get_user_router._platega_is_enabled` (3831–3832)

**Docstring в коде:** нет

```
"""True, если заданы platega_merchant_id и platega_secret."""
```

### `get_user_router._platega_get_base_url` (3834–3835)

**Docstring в коде:** нет

```
"""База Platega: setting platega_base_url или https://app.platega.io, без хвостового /."""
```

### `get_user_router._platega_get_method_code` (3837–3849)

**Docstring в коде:** нет

```
"""Первый положительный int из platega_active_methods (CSV); иначе 2."""
```

### `get_user_router._platega_request` (3851–3875)

**Docstring в коде:** нет

```
"""aiohttp к Platega: заголовки X-MerchantId/X-Secret; HTTP≥400 или пустое тело → None."""
```

timeout 25/10/20. JSON parse fail → None. **HTTP.**

### `get_user_router._create_platega_payment_link` (3877–3891)

**Docstring в коде:** нет

```
"""POST /transaction/process: вернуть (redirect, transactionId|id) или (None, None)."""
```

description обрезается до 64. return/failedUrl = t.me/bot. payload = payment_id.

### `get_user_router._get_platega_transaction` (3893–3896)

**Docstring в коде:** нет

```
"""GET /transaction/{id}; пустой id → None."""
```

### `get_user_router._build_yoomoney_link` (3898–3912)

**Docstring в коде:** нет

```
"""Собрать https://yoomoney.ru/quickpay/confirm.xml (donate) с label=payment_id."""
```

Нет HTTP. successURL = t.me/bot.

### `get_user_router.pay_yoomoney_handler` (3915–3972)

**Docstring в коде:** нет. `pay_yoomoney` в waiting_for_payment_method (покупка ключа).

```
"""Pending покупки + YooMoney-ссылка; PromoUnavailableError — текст, FSM не clear."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 3918–3922 | нет plan | clear |
| 3925–3928 | нет wallet/secret | clear |
| 3931–3934 | кошелёк | ≥11 цифр |
| 3936–3939 | price < 1 | минимум |
| 3962–3966 | pending | PromoUnavailable → «промокод недоступен», **return без clear** |
| 3967–3972 | ок | kb, **state.clear** |

Метаданные: months/duration/action/key/host/plan/email/promo.

### `get_user_router.topup_yoomoney_handler` (3975–4022)

**Docstring в коде:** нет. `topup_pay_yoomoney`.

```
"""Pending top_up + YooMoney-ссылка на сумму пополнения."""
```

Те же проверки кошелька/минимума. `create_payload_pending` без Promo-ветки. Логи 💜/💰.

---

### `get_user_router.check_platega_payment_handler` (4026–4079)

**Docstring в коде:** нет. Callback `check_platega:{pid}`.

```
"""Кнопка «Проверить»: сверка Platega API и выдача или отмена pending."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4028–4031 | нет pid | alert |
| 4038–4040 | локально paid | «уже обработана» |
| 4051–4053 | нет txid в meta | «ещё не подтверждён» |
| 4055–4058 | HTTP fail | «не удалось проверить» |
| 4061–4072 | CONFIRMED | find_and_complete → process_successful_payment; нет meta — «уже обработана»; ошибка fulfillment — поддержка |
| 4074–4077 | FAILED/CANCELED/CANCELLED/EXPIRED/CHARGEBACKED | `cancel_pending_transaction(pid)` (без user_id) |
| 4079 | иначе | ещё не подтверждён |

**HTTP** `_get_platega_transaction`. **БД** pending. **Fulfillment** process_successful_payment.

### `get_user_router.check_rollypay_payment_handler` (4082–4157)

**Docstring в коде:** нет. `check_rollypay:{pid}`.

```
"""Сверить RollyPay: method, status paid, order_id=pid, сумма; затем fulfillment."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4093–4095 | paid локально | выход |
| 4102–4104 | meta не RollyPay | ещё не подтверждён |
| 4107–4109 | нет rollypay_payment_id | то же |
| 4114–4116 | нет api_key | не удалось |
| 4117–4120 | get_payment пусто | не удалось |
| 4123–4128 | expired/canceled/cancelled/chargeback | cancel_pending |
| 4128 | иной не-paid | ещё не подтверждён |
| 4131–4133 | order_id ≠ pid | ещё не подтверждён |
| 4141–4144 | amount ≠ expected (0.01) | warning, ещё не подтверждён |
| 4146–4157 | ок | complete + process; setdefault method, txid в meta |

Сумму **не** берёт из тела на веру без сверки с pending.

### `get_user_router.check_yookassa_payment_handler` (4160–4250)

**Docstring в коде:** нет. `check_yookassa:{pid}`.

```
"""Сверить YooKassa Payment.find_one: succeeded, RUB, сумма = pending; затем fulfillment."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4172–4174 | paid локально | «скоро обновится» |
| 4182–4184 | нет pending_meta | «не найден» |
| 4187–4189 | нет yookassa_payment_id | «попробуйте позже» |
| 4193–4195 | нет shop/secret | не настроен |
| 4200–4205 | find_one fail | позже |
| 4208–4214 | canceled | cancel_pending; иначе ещё pending |
| 4232–4235 | currency и ≠ RUB | поддержка |
| 4236–4239 | сумма ≠ | поддержка |
| 4241–4250 | ок | complete + process |

### `get_user_router.check_pending_payment_handler` (4253–4337)

**Docstring в коде:** нет. `check_pending:{pid}` (YooMoney).

```
"""Проверить label в YooMoney operation-history; при success/done — complete + fulfillment."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4268–4271 | локально paid | «скоро обновится» |
| 4274–4281 | нет yoomoney_api_token | нет status → «не найден»; иначе «ещё не поступила» |
| 4285–4301 | HTTP | POST operation-history Bearer; ≠200 / сеть → warning |
| 4321–4334 | нашлась success/done | find_and_complete + process (ошибки лог); **answer успеха даже если metadata None** |
| 4337 | иначе | ещё не поступила |

---

### `get_user_router.topup_pay_platega` (4340–4382)

**Docstring в коде:** нет. `topup_pay_platega`.

```
"""Pending top_up + ссылка Platega «Пополнение баланса»; txid в повторном pending."""
```

disabled / amount≤0 / нет url → clear. **HTTP** `_create_platega_payment_link`.

### `get_user_router.topup_pay_rollypay` (4385–4430)

**Docstring в коде:** нет. `topup_pay_rollypay`.

```
"""Pending top_up + RollyPay на пополнение; rollypay_payment_id в metadata."""
```

### `get_user_router.topup_pay_heleket_like` (4433–4469)

**Docstring в коде:** нет. `topup_pay_heleket`.

```
"""Heleket-инвойс пополнения (action=top_up, months=0); нет url — FSM не clear."""
```

amount≤0 → clear. except → clear.

### `get_user_router.topup_pay_cryptobot` (4472–4508)

**Docstring в коде:** нет. `topup_pay_cryptobot`.

```
"""CryptoBot-инвойс пополнения; нет result — FSM не clear (кроме except)."""
```

### `get_user_router.topup_pay_tonconnect` (4511–4573)

**Docstring в коде:** нет. `topup_pay_tonconnect`.

```
"""Пополнение через TON Connect: курс → nanoton, pending, QR и deep-link кошелька."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 4516–4519 | amount ≤ 0 | clear |
| 4521–4525 | нет ton_wallet_address | недоступен, clear |
| 4527–4532 | нет курсов | «не удалось получить курс», clear |
| 4534–4545 | расчёт | RUB / usdt_rub / ton_usdt → TON (0.001); metadata **без** поля payment_id |
| 4545 | БД | `create_pending_transaction` (не `create_payload_pending`) |
| 4547–4568 | UI | payload TON = payment_id, valid_until +600 с; QR PNG + `create_ton_connect_keyboard` |
| 4570–4573 | except | «не удалось подготовить», clear |

По коду: `get_usdt_rub_rate`, `get_ton_usdt_rate`, `_start_ton_connect_process` в этом файле **не объявлены**; `create_pending_transaction` в модуле **не импортирован** (в `database.py` это строка `transactions` для TON). Сумма в nanoTON: `int(price_ton * 1_000_000_000)`.
