# 📋 Руководство по настройке тарифов

## Содержание
- [Обзор](#обзор)
- [Структура тарифа](#структура-тарифа)
- [Способы настройки](#способы-настройки)
  - [Веб-интерфейс](#веб-интерфейс)
  - [Telegram бот (админ-панель)](#telegram-бот-админ-панель)
  - [Прямое редактирование БД](#прямое-редактирование-бд)
- [API для работы с тарифами](#api-для-работы-с-тарифами)
- [Архитектура](#архитектура)

---

## Обзор

Система тарифов позволяет настраивать различныеplanы подписки для каждого VPN-хоста. Тарифы включают:
- Название и описание
- Срок действия (месяцы или дни)
- Цену
- Лимиты трафика
- Лимиты устройств

Каждый тариф привязан к конкретному хосту (`host_name`) и может быть активирован/деактивирован.

---

## Структура тарифа

### База данных (таблица `plans`)

```sql
CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_name TEXT,                          -- Привязка к хосту
    squad_uuid TEXT,                         -- UUID сквада Remnawave
    plan_name TEXT NOT NULL,                 -- Название тарифа
    months INTEGER,                          -- Срок в месяцах
    duration_days INTEGER,                   -- Срок в днях (альтернатива)
    price REAL NOT NULL,                     -- Цена в RUB
    traffic_limit_bytes INTEGER,             -- Лимит трафика в байтах
    traffic_limit_strategy TEXT DEFAULT 'NO_RESET',  -- Стратегия лимита
    hwid_device_limit INTEGER,               -- Лимит устройств
    is_active INTEGER DEFAULT 1,             -- Видимость (1=активен, 0=скрыт)
    sort_order INTEGER DEFAULT 0,            -- Порядок сортировки
    metadata TEXT,                           -- JSON с доп. настройками
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Поля metadata (JSON)

```json
{
    "show_name_in_tariffs": true,  // Показывать название при покупке
    "description": "Описание тарифа",
    "features": ["Без рекламы", "HD качество"]
}
```

---

## Способы настройки

### Веб-интерфейс

Самый простой способ управления тарифами.

**Путь:** `/settings` → вкладка "Хосты"

#### Добавление тарифа:
1. Раскройте секцию нужного хоста
2. Найдите раздел "Тарифы"
3. Заполните форму:
   - **Название** — отображаемое имя тарифа
   - **Мес.** — количество месяцев
   - **Цена** — стоимость в RUB
4. Нажмите кнопку "+" для добавления

#### Редактирование тарифа:
1. Нажмите кнопку "Редактировать" рядом с тарифом
2. Измените нужные поля
3. Нажмите "Сохранить"

#### Удаление тарифа:
- Нажмите кнопку "×" рядом с тарифом
- Подтвердите удаление

**Файл:** `src/shop_bot/webhook_server/templates/settings.html` (строки 254-299)

**API endpoints:**
- `POST /add-plan` — добавить тариф
- `POST /update-plan/<plan_id>` — обновить тариф
- `POST /delete-plan/<plan_id>` — удалить тариф

---

### Telegram бот (админ-панель)

Полнофункциональная админ-панель прямо в Telegram.

#### Доступ:
1. Откройте бота
2. Нажмите "⚙️ Админ-панель"
3. Выберите "🧾 Тарифы"

#### Создание тарифа:

```
🧾 Тарифы
  └─ Выбор хоста
      └─ [Хост]
          └─ ➕ Добавить тариф
              ├─ Название тарифа
              ├─ Срок (месяцы или дни)
              ├─ Трафик (ГБ)
              ├─ Устройства (количество)
              └─ Цена
```

**Этапы:**
1. **Выбор хоста** — выберите VPN-хост для тарифа
2. **Название** — введите название (например: "Стандарт")
3. **Срок действия** — выберите:
   - Месяцы (1, 3, 6, 12)
   - Дни (для кастомных периодов)
4. **Трафик** — лимит в ГБ (или 0 для безлимита)
5. **Устройства** — максимум подключений (или 0 для безлимита)
6. **Цена** — стоимость в рублях

#### Редактирование тарифа:

После выбора тарифа доступны кнопки:
- ✏️ **Название** — изменить имя
- ⏳ **Срок** — изменить длительность
- 💰 **Цена** — изменить стоимость
- 📶 **Трафик (ГБ)** — изменить лимит трафика
- 📱 **Устройства** — изменить лимит подключений
- 👁️ **Показывать название** — отображать имя при покупке
- 🚫 **Скрыть** / ✅ **Активировать** — видимость
- 🗑️ **Удалить** — удалить тариф

**Файл:** `src/shop_bot/bot/admin_handlers.py` (строки 2921-3870)

---

### Прямое редактирование БД

Для advanced-пользователей и автоматизации.

```python
from src.shop_bot.data_manager.database import (
    create_plan,
    update_plan,
    delete_plan,
    get_plans_for_host,
    get_plan_by_id
)

# Создание тарифа
create_plan(
    host_name="main_server",
    plan_name="Premium",
    months=3,
    price=599.0,
    duration_days=None,              # Опционально (если не используем months)
    traffic_limit_bytes=107374182400,  # 100 ГБ в байтах
    hwid_device_limit=5               # До 5 устройств
)

# Обновление тарифа
update_plan(
    plan_id=1,
    plan_name="Premium Plus",
    months=3,
    price=699.0,
    traffic_limit_bytes=214748364800  # 200 ГБ
)

# Получение тарифов хоста
plans = get_plans_for_host("main_server")
for plan in plans:
    print(f"{plan['plan_name']}: {plan['price']} RUB")

# Удаление тарифа
delete_plan(plan_id=1)
```

**Файл:** `src/shop_bot/data_manager/database.py` (строки 2999+)

---

## API для работы с тарифами

### Основные функции

#### `create_plan()`
```python
def create_plan(
    host_name: str,
    plan_name: str,
    months: int | None,
    price: float,
    duration_days: int | None = None,
    traffic_limit_bytes: int | None = None,
    hwid_device_limit: int | None = None
) -> None
```

**Параметры:**
- `host_name` — имя хоста из таблицы `xui_hosts`
- `plan_name` — отображаемое название
- `months` — срок в месяцах (или None)
- `duration_days` — срок в днях (альтернатива months)
- `price` — цена в RUB
- `traffic_limit_bytes` — лимит трафика (bytes), None = безлимит
- `hwid_device_limit` — лимит устройств, None = безлимит

**Пример:**
```python
# Тариф "Стандарт" на 30 дней
create_plan(
    host_name="vpn1",
    plan_name="Стандарт",
    months=1,
    price=199.0,
    traffic_limit_bytes=53687091200  # 50 ГБ
)
```

---

#### `update_plan()`
```python
def update_plan(
    plan_id: int,
    plan_name: str,
    months: int,
    price: float,
    duration_days: int | None = None,
    traffic_limit_bytes: int | None = None,
    hwid_device_limit: int | None = None
) -> bool
```

**Возвращает:** `True` при успехе, `False` при ошибке

---

#### `get_plans_for_host()`
```python
def get_plans_for_host(host_name: str) -> list[dict] | None
```

**Возвращает:** список тарифов хоста или `None`

---

#### `get_plan_by_id()`
```python
def get_plan_by_id(plan_id: int) -> dict | None
```

**Возвращает:** словарь с данными тарифа или `None`

---

#### `delete_plan()`
```python
def delete_plan(plan_id: int) -> None
```

---

## Архитектура

### Слои системы

```
┌─────────────────────────────────────┐
│   Пользовательский интерфейс        │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ Web UI       │  │ Telegram Bot │ │
│  │ (Flask)      │  │ (aiogram)    │ │
│  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│         API Routes / Handlers       │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ webhook_app  │  │ admin_       │ │
│  │ .py          │  │ handlers.py  │ │
│  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│         Business Logic              │
│  ┌────────────────────────────────┐ │
│  │ database.py                    │ │
│  │  - create_plan()               │ │
│  │  - update_plan()               │ │
│  │  - get_plans_for_host()        │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│         Data Layer                  │
│  ┌────────────────────────────────┐ │
│  │ SQLite Database                │ │
│  │  - plans table                 │ │
│  │  - xui_hosts table             │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Взаимодействие компонентов

1. **Web UI** (`templates/settings.html`)
   - Формы для CRUD операций
   - AJAX для загрузки тарифов по хосту
   
2. **Flask Routes** (`webhook_server/app.py`)
   - `/add-plan` — создание
   - `/update-plan/<id>` — обновление
   - `/delete-plan/<id>` — удаление

3. **Telegram Admin** (`bot/admin_handlers.py`)
   - Класс `AdminPlans` с FSM
   - Интерактивные меню и формы
   - Валидация ввода

4. **Database Layer** (`data_manager/database.py`)
   - CRUD функции
   - Нормализация данных
   - Транзакции SQLite

### Клавиатуры Telegram

**Файл:** `src/shop_bot/bot/keyboards.py`

- `create_admin_plans_host_menu_keyboard()` — список тарифов хоста
- `create_admin_plan_manage_keyboard()` — управление тарифом
- `create_plans_keyboard()` — выбор тарифа при покупке

---

## Примеры использования

### Пример 1: Создание базовых тарифов

```python
from src.shop_bot.data_manager.database import create_plan

# Базовый тариф
create_plan(
    host_name="vpn_main",
    plan_name="Базовый",
    months=1,
    price=149.0
)

# Стандарт с лимитом трафика
create_plan(
    host_name="vpn_main",
    plan_name="Стандарт",
    months=1,
    price=249.0,
    traffic_limit_bytes=107374182400  # 100 ГБ
)

# Премиум безлимитный
create_plan(
    host_name="vpn_main",
    plan_name="Премиум",
    months=3,
    price=649.0,
    hwid_device_limit=10
)
```

### Пример 2: Получение и отображение тарифов

```python
from src.shop_bot.data_manager.database import get_plans_for_host

plans = get_plans_for_host("vpn_main")

if plans:
    for plan in plans:
        duration = f"{plan['months']} мес." if plan['months'] else f"{plan['duration_days']} дн."
        traffic = f"{plan['traffic_limit_bytes'] / 1024**3:.0f} ГБ" if plan['traffic_limit_bytes'] else "∞"
        devices = plan['hwid_device_limit'] or "∞"
        
        print(f"""
        {plan['plan_name']}
        ├─ Срок: {duration}
        ├─ Цена: {plan['price']:.0f} ₽
        ├─ Трафик: {traffic}
        └─ Устройства: {devices}
        """)
```

### Пример 3: Массовое создание тарифов

```python
from src.shop_bot.data_manager.database import create_plan

tariffs = [
    {"name": "1 месяц", "months": 1, "price": 199},
    {"name": "3 месяца", "months": 3, "price": 549},
    {"name": "6 месяцев", "months": 6, "price": 999},
    {"name": "12 месяцев", "months": 12, "price": 1799},
]

for t in tariffs:
    create_plan(
        host_name="vpn_server",
        plan_name=t["name"],
        months=t["months"],
        price=t["price"]
    )
    print(f"✅ Создан тариф: {t['name']}")
```

---

## Дополнительные возможности

### Скрытие/Активация тарифов

Вместо удаления можно скрывать тарифы через поле `is_active`:

```python
import sqlite3

DB_FILE = "shop_bot.db"

def toggle_plan_visibility(plan_id: int, is_active: bool):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "UPDATE plans SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE plan_id = ?",
            (1 if is_active else 0, plan_id)
        )
        conn.commit()

# Скрыть тариф
toggle_plan_visibility(plan_id=1, is_active=False)

# Активировать обратно
toggle_plan_visibility(plan_id=1, is_active=True)
```

### Настройка отображения названия

Через metadata можно управлять показом имени тарифа при покупке:

```python
import json
import sqlite3

def set_show_name_flag(plan_id: int, show: bool):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT metadata FROM plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        
        meta = json.loads(row[0]) if row and row[0] else {}
        meta["show_name_in_tariffs"] = show
        
        cursor.execute(
            "UPDATE plans SET metadata = ? WHERE plan_id = ?",
            (json.dumps(meta), plan_id)
        )
        conn.commit()

# Показывать название "Премиум" при покупке
set_show_name_flag(plan_id=3, show=True)
```

---

## Troubleshooting

### Проблема: Тарифы не отображаются в боте

**Решение:**
1. Проверьте `is_active = 1`
2. Убедитесь, что `host_name` совпадает с хостом
3. Проверьте, что цена и срок > 0

### Проблема: Не создается тариф через веб-интерфейс

**Решение:**
1. Проверьте CSRF токен
2. Убедитесь, что вы залогинены как админ
3. Проверьте логи Flask:
   ```python
   logger.error(f"Failed to create plan: {e}")
   ```

### Проблема: Ошибка "Тариф не найден"

**Решение:**
```python
# Проверьте существование
from src.shop_bot.data_manager.database import get_plan_by_id

plan = get_plan_by_id(plan_id)
if not plan:
    print("План не существует или удален")
```

---

## См. также

- [README.md](README.md) — общее описание проекта
- [FRANCHISE_IMPLEMENTATION.md](FRANCHISE_IMPLEMENTATION.md) — франшиза и тарифы
- Файлы:
  - `src/shop_bot/data_manager/database.py` — функции БД
  - `src/shop_bot/bot/admin_handlers.py` — админ-панель
  - `src/shop_bot/webhook_server/app.py` — веб-роуты
  - `src/shop_bot/webhook_server/templates/settings.html` — веб-интерфейс

---

**Дата создания:** 13 февраля 2026  
**Версия:** 1.0
