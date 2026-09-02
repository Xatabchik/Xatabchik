# 🔑 Документация по системе VPN-ключей

Выдача после оплаты: `process_successful_payment` → `remnawave_api.create_or_update_key_on_host` → `rw_repo.record_key_from_payload`. LTE и месячный сброс крутит [SCHEDULER_DOCUMENTATION.md](SCHEDULER_DOCUMENTATION.md). Индекс: [DOCUMENTATION.md](DOCUMENTATION.md).

## Содержание
- [Обзор системы](#обзор-системы)
- [Структура хранения ключей](#структура-хранения-ключей)
- [Процесс приобретения ключа](#процесс-приобретения-ключа)
- [Связь ключей с тарифами](#связь-ключей-с-тарифами)
- [Жизненный цикл ключа](#жизненный-цикл-ключа)
- [API для работы с ключами](#api-для-работы-с-ключами)
- [Архитектура системы](#архитектура-системы)

---

## Обзор системы

Система VPN-ключей — это ядро бота, которое управляет созданием, хранением и продлением ключей доступа к VPN-серверам. Каждый ключ привязан к пользователю Telegram и хосту VPN.

### Основные компоненты:
- **База данных** — хранение ключей и метаданных
- **Remnawave API** — создание и управление ключами на VPN-хостах
- **Payment System** — обработка платежей и создание ключей
- **Bot Handlers** — взаимодействие с пользователями

---

## Структура хранения ключей

### Таблица `vpn_keys` в SQLite

```sql
CREATE TABLE IF NOT EXISTS vpn_keys (
    key_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Привязка к пользователю
    user_id INTEGER NOT NULL,
    
    -- Привязка к хосту и франшизе
    host_name TEXT,
    squad_uuid TEXT,
    
    -- Идентификаторы ключа
    remnawave_user_uuid TEXT,      -- UUID клиента в Remnawave
    short_uuid TEXT,                -- Короткий UUID
    email TEXT UNIQUE,              -- Email ключа (уникальный)
    key_email TEXT UNIQUE,          -- Дубликат email для совместимости
    
    -- Подключение
    subscription_url TEXT,          -- vless:// URL для подключения
    
    -- Сроки и лимиты
    expire_at TIMESTAMP,            -- Дата истечения ключа
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Лимиты трафика
    traffic_limit_bytes INTEGER,    -- Лимит трафика в байтах
    traffic_limit_strategy TEXT DEFAULT 'NO_RESET',  -- Стратегия сброса (NO_RESET/MONTHLY)
    
    -- Метаданные
    tag TEXT,                       -- Теги: trial, paid, user_gift
    description TEXT,               -- JSON с информацией о тарифе
    
    -- Мониторинг
    missing_from_server_at TIMESTAMP  -- Время когда ключ пропал с сервера
)
```

### Поля description (JSON)

В поле `description` хранится JSON с информацией о тарифе и происхождении ключа:

```json
{
    "v": 1,
    "source": "purchase",           // purchase | extend | trial | gift
    "is_trial": false,
    "plan_id": 3,                   // ID тарифа из таблицы plans
    "plan_name": "Стандарт",        // Название тарифа
    "months": 1,                    // Срок в месяцах
    "duration_days": 30,            // Срок в днях
    "tariff_label": "30 дней",     // Отображаемая метка
    "note": "Дополнительная информация"
}
```

Это позволяет:
- Отслеживать происхождение ключа
- Показывать корректную информацию о тарифе даже если план изменился
- Хранить историю покупок

---

## Процесс приобретения ключа

### 1. Выбор хоста

Пользователь выбирает VPN-хост из списка доступных:

```python
# Получение списка активных хостов
hosts = get_all_hosts()
active_hosts = [h for h in hosts if h.get('is_active')]
```

**Файл:** [src/shop_bot/bot/handlers.py](src/shop_bot/bot/handlers.py#L1066-L1089)

### 2. Выбор тарифа

Из списка тарифов для выбранного хоста:

```python
# Получение тарифов для хоста
plans = get_plans_for_host(host_name)
active_plans = [p for p in plans if p.get('is_active')]
```

**Файл:** [src/shop_bot/bot/handlers.py](src/shop_bot/bot/handlers.py#L1095-L1140)

**Клавиатура:** [src/shop_bot/bot/keyboards.py](src/shop_bot/bot/keyboards.py#L940-L970)

### 3. Ввод email (опционально)

Если включена настройка `payment_email_prompt_enabled`:

```python
email_prompt_enabled = (get_setting("payment_email_prompt_enabled") or "false").strip().lower() == "true"
```

**State:** `PaymentProcess.waiting_for_email`

### 4. Выбор способа оплаты

Доступные методы:
- 💼 **Баланс** — если достаточно средств
- 💳 **Банковская карта** (YooKassa/ЮMoney)
- 💎 **Криптовалюта** (CryptoBot/Heleket)
- 🪙 **TON Connect**
- ⭐ **Telegram Stars**
- 🏦 **СБП** через Platega

**State:** `PaymentProcess.waiting_for_payment_method`

**Файл:** [src/shop_bot/bot/keyboards.py](src/shop_bot/bot/keyboards.py#L977-L1045)

### 5. Создание платежа

Для каждого платежного метода создается инвойс:

```python
# Пример: YooKassa
payment_id = str(uuid.uuid4())
metadata = {
    "user_id": user_id,
    "months": months,
    "duration_days": duration_days,
    "price": float(price),
    "action": "new",  # new | extend | trial | gift
    "key_id": None,
    "host_name": host_name,
    "plan_id": plan_id,
    "customer_email": customer_email,
    "payment_method": "YooKassa",
    "payment_id": payment_id,
}

# Создание pending транзакции (для идемпотентности)
create_payload_pending(payment_id, user_id, float(price), metadata)
```

**Файл:** [src/shop_bot/bot/handlers.py](src/shop_bot/bot/handlers.py#L1785-L1850)

### 6. Webhook от платежной системы

При успешной оплате платежная система отправляет webhook:

```python
# Пример: YooKassa webhook
@flask_app.route('/yookassa-webhook', methods=['POST'])
def yookassa_webhook_handler():
    # 1. Проверка подписи и статуса
    # 2. Получение payment_id из payload
    # 3. Атомарная проверка и завершение pending транзакции
    metadata = find_and_complete_pending_transaction(payment_id)
    
    # 4. Запуск обработки платежа
    _dispatch_payment_processing(metadata)
```

**Файл:** [src/shop_bot/webhook_server/app.py](src/shop_bot/webhook_server/app.py#L2663-L2775)

### 7. Обработка успешного платежа

Функция `process_successful_payment()` выполняет:

```python
async def process_successful_payment(bot: Bot, metadata: dict):
    # 1. Идемпотентность - проверка что платеж не обработан
    if not claim_processed_payment(payment_id):
        return  # Дубликат, пропускаем
    
    # 2. Генерация уникального email для ключа
    if action == "new":
        email = generate_key_email_for_user(user_id)  # 12345-1@bot.local
    elif action == "extend":
        email = existing_key['key_email']
    elif action == "gift":
        email = f"gift-{uuid4().hex[:8]}@bot.local"
    
    # 3. Получение параметров тарифа
    plan = get_plan_by_id(plan_id)
    months = plan.get('months')
    duration_days = plan.get('duration_days')
    traffic_limit_bytes = plan.get('traffic_limit_bytes')
    hwid_device_limit = plan.get('hwid_device_limit')
    
    days_to_add = duration_days if duration_days else months * 30
    
    # 4. Создание ключа на VPN-хосте через Remnawave API
    result = await remnawave_api.create_or_update_key_on_host(
        host_name=host_name,
        email=email,
        days_to_add=days_to_add,
        traffic_limit_bytes=traffic_limit_bytes,
        hwid_device_limit=hwid_device_limit,
    )
    
    # 5. Сохранение ключа в БД
    origin_desc = _build_key_origin_meta(
        source="purchase",
        plan_id=plan_id,
        plan_name=plan.get('plan_name'),
        months=months,
        duration_days=duration_days,
    )
    
    key_id = record_key_from_payload(
        user_id=user_id,
        payload=result,
        host_name=host_name,
        tag="paid",
        description=origin_desc,
    )
    
    # 6. Начисление реферального бонуса
    # 7. Обновление статистики пользователя
    # 8. Отправка уведомления пользователю
}
```

**Файл:** [src/shop_bot/bot/handlers.py](src/shop_bot/bot/handlers.py#L6318-L6850)

### 8. Сохранение в БД

Функция `record_key_from_payload()` парсит ответ от Remnawave и сохраняет:

```python
def record_key_from_payload(
    user_id: int,
    payload: dict,
    *,
    host_name: str | None = None,
    description: str | None = None,
    tag: str | None = None,
) -> int | None:
    # Извлечение данных из payload
    squad_uuid = payload.get('squad_uuid')
    remnawave_user_uuid = payload.get('client_uuid')
    email = payload.get('email')
    expire_at_ms = payload.get('expiry_timestamp_ms')
    subscription_url = payload.get('connection_string')
    
    # Вызов record_key для сохранения
    return record_key(
        user_id=user_id,
        squad_uuid=squad_uuid,
        remnawave_user_uuid=remnawave_user_uuid,
        email=email,
        host_name=host_name,
        expire_at_ms=expire_at_ms,
        subscription_url=subscription_url,
        tag=tag,
        description=description,
    )
```

**Файл:** [src/shop_bot/data_manager/remnawave_repository.py](src/shop_bot/data_manager/remnawave_repository.py#L187-L225)

### 9. Уведомление пользователя

После успешного создания ключа:

```python
# Форматирование сообщения
new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000)
connection_string = result['connection_string']

text = get_purchase_success_text(
    action="new",
    key_number=get_next_key_number(user_id) - 1,
    expiry_date=new_expiry_date,
    connection_string=connection_string
)

# Отправка с клавиатурой
await bot.send_message(
    chat_id=user_id,
    text=text,
    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string)
)
```

---

## Связь ключей с тарифами

### Прямая связь

Ключи связаны с тарифами через:
1. **plan_id** в metadata платежа
2. **description** (JSON) в таблице vpn_keys
3. **Лимиты** — копируются из тарифа при создании ключа

### Схема связи

```
┌──────────────┐
│    users     │
│  telegram_id │
└──────┬───────┘
       │ 1
       │
       │ N
┌──────▼───────────────────┐        ┌─────────────┐
│      vpn_keys            │   N    │   plans     │
│                          ├────────┤             │
│  key_id                  │   1    │  plan_id    │
│  user_id (FK)            │        │  host_name  │
│  host_name (FK)          │        │  plan_name  │
│  email (UNIQUE)          │        │  months     │
│  subscription_url        │        │  price      │
│  expire_at               │        │  traffic_   │
│  traffic_limit_bytes     │        │  limit_bytes│
│  hwid_device_limit       │        │  hwid_      │
│  tag                     │        │  device_    │
│  description (JSON):     │        │  limit      │
│    {                     │        │  is_active  │
│      "plan_id": 3,       │        └─────────────┘
│      "plan_name": "..."  │
│      "months": 1         │        ┌─────────────┐
│    }                     │   N    │  xui_hosts  │
│                          ├────────┤             │
└──────────────────────────┘   1    │  host_name  │
                                     │  (PK)       │
                                     │  host_url   │
                                     │  squad_uuid │
                                     └─────────────┘
```

### Почему не прямая FK к plans?

Система использует **денормализацию** через JSON в `description`:

**Преимущества:**
1. **Историчность** — если тариф изменится, старые ключи сохранят информацию
2. **Гибкость** — можно хранить любые данные о происхождении ключа
3. **Независимость** — ключ не ломается при удалении тарифа

**При покупке:**
```python
# 1. Получаем тариф
plan = get_plan_by_id(plan_id)

# 2. Извлекаем параметры
months = plan.get('months')
price = plan.get('price')
traffic_limit = plan.get('traffic_limit_bytes')

# 3. Создаем ключ с этими параметрами
result = create_key(
    email=email,
    days_to_add=months * 30,
    traffic_limit_bytes=traffic_limit,
)

# 4. Сохраняем ссылку на тариф в description
description = json.dumps({
    "plan_id": plan_id,
    "plan_name": plan['plan_name'],
    "months": months,
    "price": price,
})
```

### Получение информации о тарифе ключа

```python
def _get_tariff_info_for_key(key_data: dict, user_payload: dict | None = None):
    """Извлекает информацию о тарифе из ключа."""
    
    # 1. Пытаемся получить из description
    description = key_data.get('description', '')
    if description and description.startswith('{'):
        try:
            meta = json.loads(description)
            if meta.get('tariff_label'):
                return (
                    meta.get('plan_name'),
                    meta.get('tariff_label'),
                    meta.get('device_limit')
                )
        except:
            pass
    
    # 2. Если нет — пытаемся получить из plan_id
    plan_id = key_data.get('plan_id')
    if plan_id:
        plan = get_plan_by_id(plan_id)
        if plan:
            return (
                plan.get('plan_name'),
                f"{plan.get('months')} мес.",
                plan.get('hwid_device_limit')
            )
    
    # 3. Fallback — базовая информация
    return ('Неизвестно', '—', None)
```

**Файл:** [src/shop_bot/bot/handlers.py](src/shop_bot/bot/handlers.py#L3440-L3530)

---

## Жизненный цикл ключа

### 1. Создание (New)

```python
action = "new"
# Генерируется новый email: {user_id}-{key_number}@bot.local
# Создается на хосте + сохраняется в БД
# tag = "paid" (или "trial" для триальных)
```

### 2. Активный период

Пользователь использует ключ:
- Подключается к VPN
- Расходует трафик (если есть лимит)
- Система мониторит `expire_at`

### 3. Напоминания

За N дней до истечения:
```python
# Настраивается в:
notification_days = get_setting("expiry_notification_days") or "3,1"

# Отправка напоминания
await bot.send_message(
    user_id,
    f"⏰ Ваш ключ #{key_number} истекает через {days_left} дн."
)
```

### 4. Продление (Extend)

```python
action = "extend"
key_id = existing_key['key_id']
# Продлевается существующий email
# Срок добавляется к текущему (если не истек)
# tag обновляется на "paid"
```

**Логика продления:**
```python
# Если срок еще не истек — продлеваем от текущего
exp_ms = existing_key['expire_at']
now_ms = int(time.time() * 1000)

if exp_ms > now_ms:
    # Продлеваем от текущей даты истечения
    new_expiry = exp_ms + (days_to_add * 86400000)
else:
    # Истек — продлеваем от текущего момента
    new_expiry = now_ms + (days_to_add * 86400000)
```

### 5. Истечение

```python
# Автоматическая проверка истекших ключей
expired_keys = get_expired_keys()

for key in expired_keys:
    # Опционально: удаление с хоста
    await remove_key_from_host(key)
    
    # Пометка в БД
    mark_key_as_missing(key['key_id'])
```

### 6. Удаление

Через админ-панель или автоматически:
```python
# Удаление с хоста
await remnawave_api.delete_key_from_host(host_name, email)

# Удаление из БД (или пометка)
delete_key_by_email(email)
```

---

## API для работы с ключами

### Основные функции

#### `generate_key_email_for_user()`
```python
def generate_key_email_for_user(user_id: int, *, domain: str = "bot.local") -> str:
    """Генерирует уникальный email для ключа пользователя.
    
    Формат: {user_id}-{key_number}@{domain}
    Например: 12345-1@bot.local, 12345-2@bot.local
    """
    next_number = get_next_key_number(user_id)
    
    # Проверка уникальности
    for attempt in range(1000):
        candidate = f"{user_id}-{next_number}@{domain}"
        if not get_key_by_email(candidate):
            return candidate
        next_number += 1
    
    # Fallback на timestamp
    return f"{user_id}-{int(time.time())}@{domain}"
```

**Файл:** [src/shop_bot/data_manager/remnawave_repository.py](src/shop_bot/data_manager/remnawave_repository.py#L268-L291)

---

#### `record_key_from_payload()`
```python
def record_key_from_payload(
    user_id: int,
    payload: dict[str, Any],
    *,
    host_name: str | None = None,
    description: str | None = None,
    tag: str | None = None,
) -> int | None:
    """Сохраняет ключ из ответа Remnawave API в БД.
    
    Args:
        user_id: ID пользователя Telegram
        payload: Ответ от Remnawave API с данными ключа
        host_name: Имя хоста
        description: JSON с метаданными тарифа
        tag: Тег ключа (paid, trial, user_gift)
    
    Returns:
        key_id или None при ошибке
    """
    # Парсинг payload
    squad_uuid = payload.get('squad_uuid')
    remnawave_user_uuid = payload.get('client_uuid')
    email = payload.get('email')
    expire_at_ms = payload.get('expiry_timestamp_ms')
    subscription_url = payload.get('connection_string')
    
    # Вызов record_key
    return record_key(
        user_id=user_id,
        squad_uuid=squad_uuid,
        remnawave_user_uuid=remnawave_user_uuid,
        email=email,
        host_name=host_name,
        expire_at_ms=expire_at_ms,
        subscription_url=subscription_url,
        tag=tag,
        description=description,
    )
```

---

#### `record_key()`
```python
def record_key(
    user_id: int,
    squad_uuid: str,
    remnawave_user_uuid: str,
    email: str,
    *,
    host_name: str | None = None,
    expire_at_ms: int | None = None,
    subscription_url: str | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    tag: str | None = None,
    description: str | None = None,
) -> int | None:
    """Создает или обновляет ключ в БД.
    
    Логика:
    1. Поиск существующего ключа по email или remnawave_user_uuid
    2. Если найден — обновление
    3. Если не найден — создание нового
    
    Returns:
        key_id существующего или нового ключа
    """
    email_normalized = _normalize_email(email)
    
    # Поиск существующего
    existing = None
    if email_normalized:
        existing = get_key_by_email(email_normalized)
    if not existing and remnawave_user_uuid:
        existing = get_key_by_remnawave_uuid(remnawave_user_uuid)
    
    if existing:
        # Обновление
        update_key_fields(
            existing['key_id'],
            expire_at_ms=expire_at_ms,
            subscription_url=subscription_url,
            traffic_limit_bytes=traffic_limit_bytes,
            tag=tag,
            description=description,
        )
        return existing['key_id']
    else:
        # Создание
        return add_new_key(
            user_id=user_id,
            host_name=host_name,
            remnawave_user_uuid=remnawave_user_uuid,
            key_email=email_normalized,
            expiry_timestamp_ms=expire_at_ms,
            subscription_url=subscription_url,
            traffic_limit_bytes=traffic_limit_bytes,
            description=description,
            tag=tag,
        )
```

**Файл:** [src/shop_bot/data_manager/remnawave_repository.py](src/shop_bot/data_manager/remnawave_repository.py#L124-L186)

---

#### `get_user_keys()`
```python
def get_user_keys(user_id: int) -> list[dict] | None:
    """Получает все ключи пользователя.
    
    Returns:
        Список словарей с данными ключей, сортированных по дате создания
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_keys WHERE user_id = ? "
                "ORDER BY datetime(created_at) DESC, key_id DESC",
                (user_id,)
            )
            rows = cursor.fetchall()
            return [_normalize_key_row(row) for row in rows]
    except Exception:
        return None
```

**Файл:** [src/shop_bot/data_manager/database.py](src/shop_bot/data_manager/database.py#L3832-L3844)

---

#### `get_key_by_id()`
```python
def get_key_by_id(key_id: int) -> dict | None:
    """Получает ключ по ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vpn_keys WHERE key_id = ?", (key_id,))
            row = cursor.fetchone()
            return _normalize_key_row(row)
    except Exception:
        return None
```

---

#### `update_key_fields()`
```python
def update_key_fields(
    key_id: int,
    *,
    user_id: int | None = None,
    host_name: str | None = None,
    remnawave_user_uuid: str | None = None,
    email: str | None = None,
    subscription_url: str | None = None,
    expire_at_ms: int | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    tag: str | None = None,
    description: str | None = None,
) -> bool:
    """Обновляет поля ключа.
    
    Только переданные параметры будут обновлены.
    
    Returns:
        True если обновление успешно
    """
    updates = {}
    if user_id is not None:
        updates["user_id"] = user_id
    if host_name is not None:
        updates["host_name"] = normalize_host_name(host_name)
    if email is not None:
        normalized = _normalize_email(email)
        updates["email"] = normalized
        updates["key_email"] = normalized
    if expire_at_ms is not None:
        updates["expire_at"] = _to_datetime_str(expire_at_ms)
    if traffic_limit_bytes is not None:
        updates["traffic_limit_bytes"] = traffic_limit_bytes
    if tag is not None:
        updates["tag"] = tag
    if description is not None:
        updates["description"] = description
    
    return _apply_key_updates(key_id, updates)
```

**Файл:** [src/shop_bot/data_manager/database.py](src/shop_bot/data_manager/database.py#L3757-L3825)

---

#### `delete_key_by_email()`
```python
def delete_key_by_email(email: str) -> bool:
    """Удаляет ключ из БД по email."""
    try:
        email_normalized = _normalize_email(email)
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM vpn_keys WHERE email = ? OR key_email = ?",
                (email_normalized, email_normalized)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False
```

---

### Интеграция с Remnawave API

#### `create_or_update_key_on_host()`
```python
async def create_or_update_key_on_host(
    host_name: str,
    email: str,
    *,
    days_to_add: int | None = None,
    expiry_timestamp_ms: int | None = None,
    traffic_limit_bytes: int | None = None,
    traffic_limit_strategy: str | None = None,
    hwid_device_limit: int | None = None,
    description: str | None = None,
    raise_on_error: bool = False,
) -> dict | None:
    """Создает или обновляет ключ на VPN-хосте через Remnawave API.
    
    Args:
        host_name: Имя хоста из таблицы xui_hosts
        email: Уникальный email ключа
        days_to_add: Сколько дней добавить (для продления)
        expiry_timestamp_ms: Абсолютная дата истечения
        traffic_limit_bytes: Лимит трафика (0 = безлимит)
        hwid_device_limit: Лимит устройств (0 = безлимит)
    
    Returns:
        dict с данными ключа:
        {
            "client_uuid": "...",
            "email": "...",
            "expiry_timestamp_ms": 1234567890,
            "connection_string": "vless://...",
            "traffic_limit_bytes": 0,
            "short_uuid": "..."
        }
    """
    # Получение настроек хоста
    host = get_host_by_name(host_name)
    if not host:
        raise ValueError(f"Host {host_name} not found")
    
    base_url = host.get('remnawave_base_url')
    api_token = host.get('remnawave_api_token')
    squad_uuid = host.get('squad_uuid')
    
    # Формирование запроса
    payload = {
        "email": email,
        "squadUuid": squad_uuid,
    }
    
    if days_to_add is not None:
        payload["daysToAdd"] = days_to_add
    if expiry_timestamp_ms is not None:
        payload["expiryTimestampMs"] = expiry_timestamp_ms
    if traffic_limit_bytes is not None:
        payload["trafficLimitBytes"] = traffic_limit_bytes
    if hwid_device_limit is not None:
        payload["hwidDeviceLimit"] = hwid_device_limit
    
    # Отправка запроса
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/api/users",
            json=payload,
            headers={"Authorization": f"Bearer {api_token}"}
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                if raise_on_error:
                    raise Exception(f"Remnawave API error: {error_text}")
                return None
            
            return await response.json()
```

**Файл:** [src/shop_bot/modules/remnawave_api.py](src/shop_bot/modules/remnawave_api.py#L760-L920)

---

## Архитектура системы

### Компоненты

```
┌──────────────────────────────────────────────┐
│           Telegram Bot (aiogram)             │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │       User Handlers                    │ │
│  │  - Выбор хоста                        │ │
│  │  - Выбор тарифа                       │ │
│  │  - Оплата                             │ │
│  │  - Управление ключами                 │ │
│  └────────────────┬───────────────────────┘ │
└───────────────────┼──────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│          Payment Processing                   │
│                                              │
│  ┌────────────────┐  ┌──────────────────┐  │
│  │   YooKassa     │  │   CryptoBot      │  │
│  │   ЮMoney       │  │   Heleket        │  │
│  │   Platega      │  │   TON Connect    │  │
│  │   Stars        │  │   Balance        │  │
│  └────────┬───────┘  └────────┬─────────┘  │
└───────────┼──────────────────┼──────────────┘
            │                  │
            │  Webhooks        │
            ▼                  ▼
┌──────────────────────────────────────────────┐
│           Webhook Handlers (Flask)            │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  _dispatch_payment_processing()        │ │
│  │  - Идемпотентность                     │ │
│  │  - Проверка статуса                    │ │
│  │  - Запуск обработки                    │ │
│  └───────────────┬────────────────────────┘ │
└──────────────────┼───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│     process_successful_payment()              │
│                                              │
│  1. Генерация email                         │
│  2. Получение параметров тарифа             │
│  3. Создание ключа на хосте                 │
│  4. Сохранение в БД                         │
│  5. Реферальная система                     │
│  6. Уведомление пользователя                │
└──────────────────┬───────────────────────────┘
                   │
         ┌─────────┼─────────┐
         ▼         ▼         ▼
┌────────────┐ ┌──────────┐ ┌───────────────┐
│ Remnawave  │ │   SQLite │ │   Telegram    │
│    API     │ │    DB    │ │  Notifications│
│            │ │          │ │               │
│ POST /api  │ │ vpn_keys │ │ send_message()│
│   /users   │ │  plans   │ │               │
└────────────┘ └──────────┘ └───────────────┘
```

### Поток данных при покупке

```
[Пользователь]
    │
    │ 1. Выбор хоста и тарифа
    ▼
[Bot Handlers]
    │
    │ 2. Создание metadata + payment_id
    ▼
[Payment Provider]
    │ create_invoice()
    │
    │ 3. Пользователь оплачивает
    ▼
[Webhook]
    │ payment_id + status=paid
    │
    │ 4. find_and_complete_pending_transaction()
    ▼
[_dispatch_payment_processing]
    │ asyncio task
    │
    │ 5. Запуск в event loop или thread
    ▼
[process_successful_payment]
    │
    ├─► 6a. Remnawave API
    │        create_or_update_key_on_host()
    │        ↓
    │        {client_uuid, email, expiry_ms, connection_string}
    │
    ├─► 6b. Database
    │        record_key_from_payload()
    │        ↓
    │        INSERT INTO vpn_keys (...)
    │        ↓
    │        key_id
    │
    ├─► 6c. Referral System
    │        add_to_balance(referrer_id, reward)
    │
    └─► 6d. Notification
         bot.send_message(user_id, success_text)
         ↓
    [Пользователь получает ключ]
```

### Идемпотентность

Система защищена от дублирующих webhooks:

```python
# 1. Pending транзакции
payment_id = str(uuid.uuid4())
metadata = {...}
create_payload_pending(payment_id, user_id, price, metadata)

# 2. Атомарное завершение (один раз)
def find_and_complete_pending_transaction(payment_id: str) -> dict | None:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Атомарная проверка + обновление статуса
        cursor.execute(
            "UPDATE pending_payments SET status = 'paid' "
            "WHERE payment_id = ? AND status = 'pending'",
            (payment_id,)
        )
        if cursor.rowcount == 0:
            return None  # Уже обработан
        
        # Получение метаданных
        cursor.execute(
            "SELECT metadata FROM pending_payments WHERE payment_id = ?",
            (payment_id,)
        )
        row = cursor.fetchone()
        return json.loads(row[0]) if row else None

# 3. Processed payments (вторая линия защиты)
def claim_processed_payment(payment_id: str) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO processed_payments (payment_id, processed_at) "
                "VALUES (?, CURRENT_TIMESTAMP)",
                (payment_id,)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Дубликат
```

**Файл:** [src/shop_bot/webhook_server/app.py](src/shop_bot/webhook_server/app.py#L87-L135)

### Многопоточность и асинхронность

```python
def _dispatch_payment_processing(metadata: dict) -> None:
    """Запускает обработку в правильном контексте."""
    
    # Пытаемся использовать основной event loop бота
    loop = current_app.config.get('EVENT_LOOP')
    bot = _bot_controller.get_bot_instance()
    
    if bot and loop and loop.is_running():
        # Запуск в основном event loop
        asyncio.run_coroutine_threadsafe(
            process_successful_payment(bot, metadata),
            loop
        )
        return
    
    # Fallback: создаем новый event loop в отдельном потоке
    def _worker():
        async def _run():
            bot = Bot(token=telegram_bot_token)
            try:
                await process_successful_payment(bot, metadata)
            finally:
                await bot.close()
        
        asyncio.run(_run())
    
    threading.Thread(
        target=_worker,
        name="payment-fulfillment",
        daemon=True
    ).start()
```

---

## Примеры использования

### Пример 1: Создание нового ключа (программно)

```python
import asyncio
from src.shop_bot.modules import remnawave_api
from src.shop_bot.data_manager import remnawave_repository as rw_repo

async def create_key_for_user(user_id: int, host_name: str, plan_id: int):
    # 1. Получаем тариф
    from src.shop_bot.data_manager.database import get_plan_by_id
    plan = get_plan_by_id(plan_id)
    
    # 2. Генерируем email
    email = rw_repo.generate_key_email_for_user(user_id)
    print(f"Generated email: {email}")
    
    # 3. Создаем ключ на хосте
    result = await remnawave_api.create_or_update_key_on_host(
        host_name=host_name,
        email=email,
        days_to_add=plan['months'] * 30,
        traffic_limit_bytes=plan.get('traffic_limit_bytes'),
        hwid_device_limit=plan.get('hwid_device_limit'),
    )
    
    # 4. Сохраняем в БД
    key_id = rw_repo.record_key_from_payload(
        user_id=user_id,
        payload=result,
        host_name=host_name,
        tag="paid",
        description=json.dumps({
            "plan_id": plan_id,
            "plan_name": plan['plan_name'],
            "months": plan['months'],
        })
    )
    
    print(f"Key created: {key_id}")
    print(f"Connection string: {result['connection_string']}")
    
    return key_id

# Запуск
asyncio.run(create_key_for_user(
    user_id=12345,
    host_name="vpn_main",
    plan_id=3
))
```

### Пример 2: Получение всех ключей пользователя

```python
from src.shop_bot.data_manager.database import get_user_keys

user_id = 12345
keys = get_user_keys(user_id)

for key in keys:
    print(f"""
    Ключ #{key['key_id']}
    ├─ Email: {key['key_email']}
    ├─ Хост: {key['host_name']}
    ├─ Истекает: {key['expire_at']}
    ├─ Трафик: {key.get('traffic_limit_bytes', 'Безлимит')}
    └─ Тег: {key.get('tag', '—')}
    """)
```

### Пример 3: Продление ключа

```python
async def extend_key(key_id: int, days: int):
    # 1. Получаем существующий ключ
    from src.shop_bot.data_manager.database import get_key_by_id
    key = get_key_by_id(key_id)
    
    # 2. Продлеваем на хосте
    result = await remnawave_api.create_or_update_key_on_host(
        host_name=key['host_name'],
        email=key['key_email'],
        days_to_add=days,
    )
    
    # 3. Обновляем в БД
    from src.shop_bot.data_manager import remnawave_repository as rw_repo
    rw_repo.update_key(
        key_id,
        expire_at_ms=result['expiry_timestamp_ms'],
        description=json.dumps({
            "source": "extend",
            "extended_days": days,
        })
    )
    
    print(f"Key {key_id} extended by {days} days")
    print(f"New expiry: {result['expiry_timestamp_ms']}")

asyncio.run(extend_key(key_id=42, days=30))
```

### Пример 4: Триальный ключ

```python
async def create_trial_key(user_id: int, host_name: str):
    from src.shop_bot.data_manager.database import get_setting
    
    # Получаем настройки триала
    trial_days = int(get_setting("trial_duration_days") or 3)
    trial_traffic_gb = int(get_setting("trial_traffic_limit_gb") or 10)
    traffic_bytes = trial_traffic_gb * 1024**3
    
    # Генерируем email
    email = rw_repo.generate_key_email_for_user(user_id)
    
    # Создаем
    result = await remnawave_api.create_or_update_key_on_host(
        host_name=host_name,
        email=email,
        days_to_add=trial_days,
        traffic_limit_bytes=traffic_bytes,
    )
    
    # Сохраняем с тегом trial
    key_id = rw_repo.record_key_from_payload(
        user_id=user_id,
        payload=result,
        host_name=host_name,
        tag="trial",
        description=json.dumps({
            "source": "trial",
            "is_trial": True,
            "duration_days": trial_days,
        })
    )
    
    return key_id, result['connection_string']
```

---

## Диаграмма данных: таблицы БД

```sql
-- Схема связей между таблицами

-- Пользователи
users (telegram_id, username, balance, referral_balance, referred_by)
  │
  ├─► vpn_keys (user_id FK → users.telegram_id)
  │     ├─ host_name FK → xui_hosts.host_name
  │     └─ description (JSON) → plan_id → plans.plan_id
  │
  ├─► transactions (user_id FK → users.telegram_id)
  │
  └─► user_gifts (from_user_id FK → users.telegram_id)
        └─ key_id FK → vpn_keys.key_id

-- Хосты и тарифы
xui_hosts (host_name PK, squad_uuid, host_url, remnawave_base_url)
  │
  └─► plans (host_name FK → xui_hosts.host_name)
        └─ plan_id PK
           ├─ plan_name, months, price
           ├─ traffic_limit_bytes
           └─ hwid_device_limit

-- Платежи
pending_payments (payment_id PK, user_id, status, metadata JSON)
processed_payments (payment_id PK, processed_at)
transactions (transaction_id PK, user_id FK, payment_id, status, amount_rub)
```

---

## Troubleshooting

### Проблема: Ключ не создается

**Симптомы:**
- Платеж прошел, но ключ не пришел
- Ошибка "Не удалось создать ключ"

**Решение:**

1. Проверьте логи:
```bash
grep "Key creation error" logs/bot.log
```

2. Проверьте доступность хоста:
```python
from src.shop_bot.modules.remnawave_api import check_host_connection
result = await check_host_connection("vpn_main")
```

3. Проверьте pending транзакцию:
```sql
SELECT * FROM pending_payments WHERE payment_id = '...';
```

4. Проверьте processed_payments (идемпотентность):
```sql
SELECT * FROM processed_payments WHERE payment_id = '...';
```

### Проблема: Дублирование ключей

**Симптомы:**
- Пользователь получил два одинаковых ключа
- Email collision error

**Решение:**

1. Проверьте уникальность email:
```sql
SELECT COUNT(*), key_email FROM vpn_keys GROUP BY key_email HAVING COUNT(*) > 1;
```

2. Проверьте pending транзакции:
```sql
SELECT COUNT(*), payment_id FROM pending_payments GROUP BY payment_id HAVING COUNT(*) > 1;
```

3. Очистите дубликаты (осторожно!):
```python
# Удалить дубликаты, оставив самый последний
duplicates = """
SELECT key_id FROM vpn_keys 
WHERE key_email IN (
    SELECT key_email FROM vpn_keys 
    GROUP BY key_email HAVING COUNT(*) > 1
)
AND key_id NOT IN (
    SELECT MAX(key_id) FROM vpn_keys 
    GROUP BY key_email
)
"""
```

### Проблема: Ключ не продлевается

**Симптомы:**
- Платеж прошел, но срок не изменился
- "Не удалось обновить информацию о ключе"

**Решение:**

1. Проверьте существующий ключ:
```python
key = get_key_by_id(key_id)
print(f"Current expiry: {key['expire_at']}")
print(f"Email: {key['key_email']}")
```

2. Проверьте ответ Remnawave:
```python
result = await remnawave_api.create_or_update_key_on_host(
    host_name=key['host_name'],
    email=key['key_email'],
    days_to_add=30
)
print(f"New expiry from API: {result['expiry_timestamp_ms']}")
```

3. Обновите вручную:
```python
from src.shop_bot.data_manager import remnawave_repository as rw_repo
rw_repo.update_key(
    key_id,
    expire_at_ms=result['expiry_timestamp_ms']
)
```

---

## См. также

- [TARIFFS_GUIDE.md](TARIFFS_GUIDE.md) — Руководство по настройке тарифов
- [FRANCHISE_IMPLEMENTATION.MD](FRANCHISE_IMPLEMENTATION.md) — Франшиза и управление клонами
- [README.md](README.md) — Общее описание проекта
- Файлы:
  - `src/shop_bot/data_manager/database.py` — Функции работы с БД
  - `src/shop_bot/data_manager/remnawave_repository.py` — Репозиторий ключей
  - `src/shop_bot/modules/remnawave_api.py` — Интеграция с Remnawave
  - `src/shop_bot/bot/handlers.py` — Обработчики бота
  - `src/shop_bot/webhook_server/app.py` — Webhook-сервер

---

**Дата создания:** 13 февраля 2026  
**Версия:** 1.0
