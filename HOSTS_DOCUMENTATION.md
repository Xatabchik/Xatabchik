# 🖥️ Документация: Система управления хостами (VPN-серверами)

## 📋 Оглавление
1. [Введение](#введение)
2. [Архитектура системы](#архитектура-системы)
3. [Структура базы данных](#структура-базы-данных)
4. [Интеграция с Remnawave](#интеграция-с-remnawave)
5. [CRUD операции](#crud-операции)
6. [SSH и мониторинг](#ssh-и-мониторинг)
7. [Интерфейсы управления](#интерфейсы-управления)
8. [API Reference](#api-reference)
9. [Примеры](#примеры)
10. [Связь с тарифами и ключами](#связь-с-тарифами-и-ключами)

---

## 🎯 Введение

**Хост** — это VPN-сервер, на котором работает панель Remnawave для управления VPN-ключами. Каждый хост содержит:
- Настройки подключения к Remnawave API
- SSH-конфигурацию для мониторинга
- URL для подписок пользователей
- Метаданные и настройки активности

### Основные возможности
- ✅ Управление несколькими VPN-серверами
- ✅ Интеграция с Remnawave API (мультитенантность через Squad UUID)
- ✅ SSH-мониторинг (speedtest и ресурсы)
- ✅ Привязка тарифов к конкретным серверам
- ✅ Автоматическое создание ключей на выбранном сервере

---

## 🏗️ Архитектура системы

```
┌─────────────────────────────────────────────────────────┐
│                     VPN Bot System                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐     │
│  │  План 1  │──────│  План 2  │──────│  План 3  │     │
│  └────┬─────┘      └────┬─────┘      └────┬─────┘     │
│       │                 │                  │            │
│       └─────────────────┴──────────────────┘            │
│                         │                               │
│                    host_name (FK)                       │
│                         │                               │
│  ┌──────────────────────▼───────────────────────────┐  │
│  │           Таблица xui_hosts (Хосты)             │  │
│  │  ┌────────────────────────────────────────┐     │  │
│  │  │ host_name (PK) + squad_uuid (UNIQUE)   │     │  │
│  │  │ remnawave_base_url + remnawave_api_token│    │  │
│  │  │ host_url + subscription_url             │     │  │
│  │  │ SSH: host/port/user/password/key        │     │  │
│  │  └────────────────────────────────────────┘     │  │
│  └───────────┬──────────────────────────────────────┘  │
│              │                                          │
│         host_name (FK)                                  │
│              │                                          │
│  ┌───────────▼──────────────────────────────────────┐  │
│  │          Таблица vpn_keys (Ключи)               │  │
│  │  ┌────────────────────────────────────────┐     │  │
│  │  │ key_id + email + remnawave_user_uuid   │     │  │
│  │  │ plan_id + host_name + metadata         │     │  │
│  │  └────────────────────────────────────────┘     │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Внешний Remnawave Server               │  │
│  │  API: https://panel.example.com/api/v1/        │  │
│  │  Squad UUID: организует мультитенантность      │  │
│  │  SSH: speedtest и мониторинг ресурсов          │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🗄️ Структура базы данных

### Таблица `xui_hosts`

**Файл:** `src/shop_bot/data_manager/database.py` (строки 220-250)

```sql
CREATE TABLE IF NOT EXISTS xui_hosts (
    host_name TEXT PRIMARY KEY,
    squad_uuid TEXT UNIQUE,
    remnawave_base_url TEXT,
    remnawave_api_token TEXT,
    host_url TEXT,
    subscription_url TEXT,
    ssh_host TEXT,
    ssh_port INTEGER DEFAULT 22,
    ssh_user TEXT,
    ssh_password TEXT,
    ssh_key_path TEXT,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TEXT,
    updated_at TEXT,
    speedtest_last_run TEXT
)
```

### Описание полей

| Поле | Тип | Описание |
|------|-----|----------|
| `host_name` | TEXT (PK) | Уникальное имя хоста (нормализуется) |
| `squad_uuid` | TEXT (UNIQUE) | UUID Squad в Remnawave для мультитенантности |
| `remnawave_base_url` | TEXT | URL панели Remnawave (например, `https://panel.example.com`) |
| `remnawave_api_token` | TEXT | API токен для доступа к Remnawave |
| `host_url` | TEXT | Публичный URL панели (для админов) |
| `subscription_url` | TEXT | URL подписки для пользователей |
| `ssh_host` | TEXT | SSH адрес сервера |
| `ssh_port` | INTEGER | SSH порт (по умолчанию 22) |
| `ssh_user` | TEXT | SSH пользователь |
| `ssh_password` | TEXT | SSH пароль |
| `ssh_key_path` | TEXT | Путь к SSH приватному ключу |
| `description` | TEXT | Описание хоста (может содержать JSON-метаданные) |
| `is_active` | INTEGER | Активен ли хост (1 = да, 0 = нет) |
| `sort_order` | INTEGER | Порядок сортировки при отображении |
| `metadata` | TEXT | Дополнительные метаданные (JSON) |
| `created_at` | TEXT | Дата создания (ISO 8601) |
| `updated_at` | TEXT | Дата последнего обновления |
| `speedtest_last_run` | TEXT | Дата последнего speedtest |

### Нормализация имен

**Функция:** `normalize_host_name(name: str) -> str`

```python
def normalize_host_name(name: str) -> str:
    """Нормализует имя хоста: убирает пробелы и приводит к lowercase."""
    if name is None:
        return ""
    return name.strip().lower()
```

Используется для обеспечения единообразия при поиске и сравнении имен хостов.

---

## 🔗 Интеграция с Remnawave

### Что такое Remnawave?

**Remnawave** — это панель управления VPN (аналог 3x-ui), которая предоставляет REST API для:
- Создания/удаления пользователей (VPN-ключей)
- Управления subscription URL
- Получения статистики трафика
- Управления Squad (мультитенантность)

### Squad UUID и мультитенантность

**Squad** — это концепция Remnawave для изоляции пользователей и настроек между разными "командами" или клиентами на одном сервере.

```
┌────────────────────────────────────────┐
│      Remnawave Server (физический)     │
├────────────────────────────────────────┤
│                                        │
│  └─ Squad 1 (aaaa-bbbb-cccc-dddd)      │
│      ├─ User 1 (email: user1@bot)      │
│      ├─ User 2 (email: user2@bot)      │
│      └─ Inbound Config #1              │
│                                        │
│  └─ Squad 2 (eeee-ffff-gggg-hhhh)      │
│      ├─ User 3 (email: user3@bot)      │
│      └─ Inbound Config #2              │
│                                        │
└────────────────────────────────────────┘
```

Каждый хост в боте может иметь свой `squad_uuid`, что позволяет:
- Использовать один физический сервер для нескольких ботов/франшиз
- Изолировать пользователей друг от друга
- Управлять разными inbound конфигурациями

### Загрузка конфигурации для API

**Файл:** `src/shop_bot/modules/remnawave_api.py` (строки 127-142)

```python
def _load_config_for_host(host_name: str) -> dict[str, Any]:
    """Load Remnawave API config for a specific host from xui_hosts."""
    if not host_name:
        raise RemnawaveAPIError("host_name is required")
    squad = rw_repo.get_squad(host_name)
    if not squad:
        raise RemnawaveAPIError(f"Host '{host_name}' not found")
    base_url = (squad.get("remnawave_base_url") or "").strip().rstrip("/")
    token = (squad.get("remnawave_api_token") or "").strip()
    if not base_url or not token:
        # Fallback to global config
        try:
            return _load_config()
        except RemnawaveAPIError:
            raise RemnawaveAPIError(f"Remnawave API settings are not configured for host '{host_name}'")
    return {"base_url": base_url, "token": token, "cookies": {}, "is_local": False}
```

### Поиск хоста (get_squad)

**Файл:** `src/shop_bot/data_manager/remnawave_repository.py` (строки 87-107)

```python
def get_squad(identifier: str) -> dict[str, Any] | None:
    """Найти хост по имени или squad_uuid."""
    if not identifier:
        return None
    ident = identifier.strip()
    if not ident:
        return None
    normalized = normalize_host_name(ident)
    with _connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM xui_hosts
            WHERE TRIM(host_name) = TRIM(?)
               OR TRIM(host_name) = TRIM(?)
               OR TRIM(squad_uuid) = TRIM(?)
               OR TRIM(squad_uuid) = TRIM(?)
            LIMIT 1
            """,
            (ident, normalized, ident, normalized),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
```

**Особенности:**
- Поиск по `host_name` (с нормализацией и без)
- Поиск по `squad_uuid` (с нормализацией и без)
- Возвращает первое совпадение

---

## ⚙️ CRUD операции

### 1. Создание хоста (`create_host`)

**Файл:** `src/shop_bot/data_manager/database.py` (строки 983-1037)

```python
def create_host(
    name: str,
    url: str = "",
    user: str = "",
    passwd: str = "",
    inbound: str = "",
    subscription_url: str = "",
) -> None:
    """
    Создать новый хост.
    
    Args:
        name: Имя хоста (нормализуется)
        url: URL панели Remnawave
        user: (устарело)
        passwd: (устарело)
        inbound: (устарело)
        subscription_url: URL для подписок
    """
    name_n = normalize_host_name(name)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO xui_hosts(
                    host_name, host_url, subscription_url,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (name_n, url or "", subscription_url or "", now_iso, now_iso),
            )
            conn.commit()
            logging.info(f"✅ Хост '{name_n}' создан")
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: xui_hosts.host_name" in str(e):
            logging.error(f"❌ Хост с именем '{name_n}' уже существует")
            raise ValueError(f"Хост с именем '{name_n}' уже существует") from e
        else:
            logging.error(f"Ошибка создания хоста: {e}")
            raise
    except sqlite3.Error as e:
        logging.error(f"Ошибка создания хоста: {e}")
        raise
```

### 2. Обновление Remnawave настроек

**Файл:** `src/shop_bot/data_manager/database.py` (строки 1096-1134)

```python
def update_host_remnawave_settings(
    host_name: str,
    remnawave_base_url: str = None,
    remnawave_api_token: str = None,
    squad_uuid: str = None,
) -> None:
    """
    Обновить настройки Remnawave для хоста.
    
    Args:
        host_name: Имя хоста
        remnawave_base_url: Новый базовый URL
        remnawave_api_token: Новый API токен
        squad_uuid: Новый Squad UUID
    """
    host_name_n = normalize_host_name(host_name)
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = []
    values = []
    if remnawave_base_url is not None:
        updates.append("remnawave_base_url = ?")
        values.append(remnawave_base_url.strip())
    if remnawave_api_token is not None:
        updates.append("remnawave_api_token = ?")
        values.append(remnawave_api_token.strip())
    if squad_uuid is not None:
        updates.append("squad_uuid = ?")
        values.append(squad_uuid.strip() if squad_uuid else "")
    if not updates:
        return
    updates.append("updated_at = ?")
    values.append(now_iso)
    values.append(host_name_n)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE xui_hosts SET {', '.join(updates)} WHERE host_name=?",
                values,
            )
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"✅ Remnawave настройки обновлены для хоста '{host_name_n}'")
            else:
                logging.warning(f"⚠️ Хост '{host_name_n}' не найден")
    except sqlite3.Error as e:
        logging.error(f"Ошибка обновления Remnawave настроек: {e}")
        raise
```

### 3. Обновление SSH настроек

**Файл:** `src/shop_bot/data_manager/database.py` (строки 1136-1194)

```python
def update_host_ssh_settings(
    host_name: str,
    ssh_host: str = None,
    ssh_port: int = None,
    ssh_user: str = None,
    ssh_password: str = None,
    ssh_key_path: str = None,
) -> None:
    """
    Обновить SSH настройки для хоста (для speedtest и мониторинга).
    
    Args:
        host_name: Имя хоста
        ssh_host: SSH адрес
        ssh_port: SSH порт
        ssh_user: SSH пользователь
        ssh_password: SSH пароль
        ssh_key_path: Путь к приватному ключу
    """
    host_name_n = normalize_host_name(host_name)
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = []
    values = []
    if ssh_host is not None:
        updates.append("ssh_host = ?")
        values.append(ssh_host.strip())
    if ssh_port is not None:
        updates.append("ssh_port = ?")
        values.append(ssh_port)
    if ssh_user is not None:
        updates.append("ssh_user = ?")
        values.append(ssh_user.strip())
    if ssh_password is not None:
        updates.append("ssh_password = ?")
        values.append(ssh_password)
    if ssh_key_path is not None:
        updates.append("ssh_key_path = ?")
        values.append(ssh_key_path.strip())
    if not updates:
        return
    updates.append("updated_at = ?")
    values.append(now_iso)
    values.append(host_name_n)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE xui_hosts SET {', '.join(updates)} WHERE host_name=?",
                values,
            )
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"✅ SSH настройки обновлены для хоста '{host_name_n}'")
            else:
                logging.warning(f"⚠️ Хост '{host_name_n}' не найден")
    except sqlite3.Error as e:
        logging.error(f"Ошибка обновления SSH настроек: {e}")
        raise
```

### 4. Переименование хоста

**Файл:** `src/shop_bot/data_manager/database.py` (строки 1076-1094)

```python
def update_host_name(old_name: str, new_name: str) -> None:
    """
    Переименовать хост (обновляет host_name + все FK в plans и vpn_keys).
    
    Args:
        old_name: Старое имя хоста
        new_name: Новое имя хоста
    """
    old_n = normalize_host_name(old_name)
    new_n = normalize_host_name(new_name)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Обновить имя хоста
            cursor.execute("UPDATE xui_hosts SET host_name=?, updated_at=? WHERE host_name=?", (new_n, now_iso, old_n))
            # Обновить FK в тарифах
            cursor.execute("UPDATE plans SET host_name=? WHERE host_name=?", (new_n, old_n))
            # Обновить FK в ключах
            cursor.execute("UPDATE vpn_keys SET host_name=? WHERE host_name=?", (new_n, old_n))
            conn.commit()
            logging.info(f"✅ Хост '{old_n}' переименован в '{new_n}'")
    except sqlite3.Error as e:
        logging.error(f"Ошибка переименования хоста: {e}")
        raise
```

### 5. Удаление хоста

**Файл:** `src/shop_bot/data_manager/database.py` (строки 1196-1225)

```python
def delete_host(host_name: str) -> None:
    """
    Удалить хост (проверяет отсутствие связанных тарифов перед удалением).
    
    Args:
        host_name: Имя хоста
        
    Raises:
        ValueError: Если есть тарифы, привязанные к хосту
    """
    host_name_n = normalize_host_name(host_name)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Проверить наличие связанных тарифов
            cursor.execute("SELECT COUNT(*) FROM plans WHERE host_name = ?", (host_name_n,))
            count = cursor.fetchone()[0]
            if count > 0:
                raise ValueError(f"Невозможно удалить хост '{host_name_n}': существует {count} тарифов, привязанных к нему")
            # Удалить хост
            cursor.execute("DELETE FROM xui_hosts WHERE host_name=?", (host_name_n,))
            conn.commit()
            if cursor.rowcount > 0:
                logging.info(f"✅ Хост '{host_name_n}' удален")
            else:
                logging.warning(f"⚠️ Хост '{host_name_n}' не найден")
    except sqlite3.Error as e:
        logging.error(f"Ошибка удаления хоста: {e}")
        raise
```

### 6. Получение хоста

**Файл:** `src/shop_bot/data_manager/database.py` (строки 1227-1244)

```python
def get_host(host_name: str) -> dict | None:
    """
    Получить информацию о хосте по имени.
    
    Returns:
        dict или None если не найден
    """
    host_name_n = normalize_host_name(host_name)
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts WHERE host_name=?", (host_name_n,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения хоста: {e}")
        return None
```

### 7. Получение всех хостов

**Файл:** `src/shop_bot/data_manager/database.py` (строки 1259-1276)

```python
def get_all_hosts() -> list[dict]:
    """
    Получить список всех хостов.
    
    Returns:
        Список словарей с данными хостов
    """
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM xui_hosts")
            hosts = cursor.fetchall()
            result = []
            for row in hosts:
                d = dict(row)
                d['host_name'] = normalize_host_name(d.get('host_name'))
                result.append(d)
            return result
    except sqlite3.Error as e:
        logging.error(f"Ошибка получения списка всех хостов: {e}")
        return []
```

---

## 🖥️ SSH и мониторинг

### Speedtest через SSH

Бот может запускать speedtest на удаленном сервере через SSH и сохранять результаты.

**Таблица `speedtest_results`:**

```sql
CREATE TABLE IF NOT EXISTS speedtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    download_speed REAL,
    upload_speed REAL,
    ping REAL,
    metadata TEXT
)
```

**Файл:** `src/shop_bot/data_manager/speedtest_runner.py`

### Мониторинг ресурсов

**Файл:** `src/shop_bot/data_manager/resource_monitor.py`

Мониторит:
- CPU использование
- RAM использование
- Disk использование
- Network трафик

через SSH подключение к серверу.

---

## 🎛️ Интерфейсы управления

### 1. Telegram Bot (Admin Panel)

**Файл:** `src/shop_bot/bot/admin_handlers.py` (строки 1914-2120)

#### Меню управления хостами

```python
async def show_admin_hosts_menu(message: Message, *, edit: bool = False):
    """Показать главное меню управления хостами."""
    hosts = get_all_hosts()
    text = "🖥 <b>Управление хостами</b>\n\n"
    if hosts:
        text += "📋 <b>Список хостов:</b>\n"
        for h in hosts:
            name = h.get("host_name", "")
            url = h.get("host_url", "")
            active = "✅" if h.get("is_active", 1) else "❌"
            text += f"{active} <code>{name}</code> — {url}\n"
    else:
        text += "⚠️ Хостов пока нет.\n"
    text += "\n💡 Выберите действие:"
    kb = keyboards.get_admin_hosts_keyboard()
    if edit:
        await message.edit_text(text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)
```

#### Состояния для добавления хоста

```python
class AdminHosts(StatesGroup):
    menu = State()
    waiting_add_name = State()
    waiting_add_base_url = State()
    waiting_add_api_token = State()
    waiting_add_squad_uuid = State()
    waiting_edit_host_select = State()
    # ... другие состояния
```

#### Процесс добавления хоста

```python
@router.message(AdminHosts.waiting_add_name)
async def admin_hosts_add_step2(message: Message, state: FSMContext):
    """Получить имя нового хоста."""
    name = message.text.strip()
    if not name:
        await message.answer("❌ Имя не может быть пустым.")
        return
    await state.update_data(new_host_name=name)
    await message.answer("📝 Введите базовый URL Remnawave\n(например: https://panel.example.com):")
    await state.set_state(AdminHosts.waiting_add_base_url)

@router.message(AdminHosts.waiting_add_base_url)
async def admin_hosts_add_step3(message: Message, state: FSMContext):
    """Получить базовый URL."""
    base_url = message.text.strip()
    await state.update_data(remnawave_base_url=base_url)
    await message.answer("🔑 Введите API Token для Remnawave:")
    await state.set_state(AdminHosts.waiting_add_api_token)

@router.message(AdminHosts.waiting_add_api_token)
async def admin_hosts_add_step4(message: Message, state: FSMContext):
    """Получить API токен."""
    api_token = message.text.strip()
    await state.update_data(remnawave_api_token=api_token)
    await message.answer("🆔 Введите Squad UUID (или отправьте '-' чтобы пропустить):")
    await state.set_state(AdminHosts.waiting_add_squad_uuid)

@router.message(AdminHosts.waiting_add_squad_uuid)
async def admin_hosts_add_complete(message: Message, state: FSMContext):
    """Завершить создание хоста."""
    squad_uuid = message.text.strip()
    if squad_uuid == "-":
        squad_uuid = ""
    data = await state.get_data()
    try:
        create_host(
            name=data["new_host_name"],
            url="",
            subscription_url=""
        )
        update_host_remnawave_settings(
            host_name=data["new_host_name"],
            remnawave_base_url=data["remnawave_base_url"],
            remnawave_api_token=data["remnawave_api_token"],
            squad_uuid=squad_uuid
        )
        await message.answer(f"✅ Хост '{data['new_host_name']}' успешно создан!")
        await state.clear()
        await show_admin_hosts_menu(message)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
```

### 2. Web Interface (Flask)

**Файл:** `src/shop_bot/webhook_server/app.py`

#### Маршруты для хостов

```python
@app.route("/add-host", methods=["POST"])
@requires_auth
def add_host_route():
    """Добавить новый хост через веб-интерфейс."""
    host_name = request.form.get("host_name", "").strip()
    remnawave_base_url = request.form.get("remnawave_base_url", "").strip()
    remnawave_api_token = request.form.get("remnawave_api_token", "").strip()
    squad_uuid = request.form.get("squad_uuid", "").strip()
    try:
        database.create_host(host_name, subscription_url="")
        database.update_host_remnawave_settings(
            host_name,
            remnawave_base_url=remnawave_base_url,
            remnawave_api_token=remnawave_api_token,
            squad_uuid=squad_uuid
        )
        flash(f"Хост '{host_name}' успешно добавлен", "success")
    except Exception as e:
        flash(f"Ошибка: {e}", "danger")
    return redirect(url_for("settings_page"))

@app.route("/delete-host/<host_name>", methods=["POST"])
@requires_auth
def delete_host_route(host_name):
    """Удалить хост."""
    try:
        database.delete_host(host_name)
        flash(f"Хост '{host_name}' удален", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Ошибка: {e}", "danger")
    return redirect(url_for("settings_page"))

@app.route("/update-host-remnawave", methods=["POST"])
@requires_auth
def update_host_remnawave_route():
    """Обновить Remnawave настройки хоста."""
    host_name = request.form.get("host_name")
    remnawave_base_url = request.form.get("remnawave_base_url")
    remnawave_api_token = request.form.get("remnawave_api_token")
    squad_uuid = request.form.get("squad_uuid")
    try:
        database.update_host_remnawave_settings(
            host_name,
            remnawave_base_url=remnawave_base_url,
            remnawave_api_token=remnawave_api_token,
            squad_uuid=squad_uuid
        )
        flash(f"Remnawave настройки обновлены для хоста '{host_name}'", "success")
    except Exception as e:
        flash(f"Ошибка: {e}", "danger")
    return redirect(url_for("settings_page"))

@app.route("/update-host-ssh", methods=["POST"])
@requires_auth
def update_host_ssh_route():
    """Обновить SSH настройки хоста."""
    host_name = request.form.get("host_name")
    ssh_host = request.form.get("ssh_host")
    ssh_port = request.form.get("ssh_port", type=int)
    ssh_user = request.form.get("ssh_user")
    ssh_password = request.form.get("ssh_password")
    ssh_key_path = request.form.get("ssh_key_path")
    try:
        database.update_host_ssh_settings(
            host_name,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            ssh_key_path=ssh_key_path
        )
        flash(f"SSH настройки обновлены для хоста '{host_name}'", "success")
    except Exception as e:
        flash(f"Ошибка: {e}", "danger")
    return redirect(url_for("settings_page"))
```

#### UI форма (HTML)

**Файл:** `src/shop_bot/webhook_server/templates/settings.html` (строки 144-200)

```html
<h2>
    <i class="ti ti-server me-2"></i>
    Управление Хостами (Серверами)
</h2>

<!-- Форма добавления хоста -->
<div class="host-card">
    <h4>
        <i class="ti ti-plus me-2"></i>
        Добавить новый хост
    </h4>
    <form action="{{ url_for('add_host_route') }}" method="post">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
        <div class="form-group">
            <label for="host_name">Название хоста:</label>
            <input type="text" id="host_name" name="host_name" required />
        </div>
        <div class="form-group">
            <label for="remnawave_base_url">Базовый URL Remnawave:</label>
            <input type="url" id="remnawave_base_url" name="remnawave_base_url" placeholder="https://panel.example.com" required />
        </div>
        <div class="form-group password-wrapper">
            <label for="remnawave_api_token">API Token:</label>
            <input type="password" id="remnawave_api_token" name="remnawave_api_token" required />
            <button type="button" class="toggle-password">👁️</button>
        </div>
        <div class="form-group">
            <label for="squad_uuid">Squad UUID:</label>
            <input type="text" id="squad_uuid" name="squad_uuid" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" />
        </div>
        <button type="submit" class="btn btn-primary">
            <i class="ti ti-plus me-1"></i>
            Добавить хост
        </button>
    </form>
</div>

<!-- Список существующих хостов -->
{% if hosts %}
    {% for host in hosts %}
    <details class="host-card rw-drawer rw-drawer-host">
        <summary class="host-header rw-drawer-summary">
            <h3>{{ host.host_name }}</h3>
            <span class="rw-drawer-caret" aria-hidden="true"></span>
            <form action="{{ url_for('delete_host_route', host_name=host.host_name) }}" method="post" data-confirm="Вы уверены, что хотите удалить этот хост и все его тарифы?">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
                <button type="submit" class="btn btn-danger btn-sm">Удалить</button>
            </form>
        </summary>
        <div class="rw-drawer-body">
            <!-- Формы редактирования -->
        </div>
    </details>
    {% endfor %}
{% endif %}
```

---

## 📚 API Reference

### Основные функции

#### `create_host(name, url, user, passwd, inbound, subscription_url)`
- **Описание:** Создает новый хост
- **Параметры:**
  - `name` (str): Имя хоста (обязательно)
  - `url` (str): URL панели
  - `user` (str): (устарело)
  - `passwd` (str): (устарело)
  - `inbound` (str): (устарело)
  - `subscription_url` (str): URL подписки
- **Возвращает:** None
- **Исключения:** 
  - `ValueError` — если хост с таким именем уже существует
  - `sqlite3.Error` — при ошибках БД

#### `update_host_remnawave_settings(host_name, remnawave_base_url, remnawave_api_token, squad_uuid)`
- **Описание:** Обновляет настройки Remnawave для хоста
- **Параметры:**
  - `host_name` (str): Имя хоста
  - `remnawave_base_url` (str, optional): Новый URL
  - `remnawave_api_token` (str, optional): Новый токен
  - `squad_uuid` (str, optional): Новый Squad UUID
- **Возвращает:** None

#### `update_host_ssh_settings(host_name, ssh_host, ssh_port, ssh_user, ssh_password, ssh_key_path)`
- **Описание:** Обновляет SSH настройки для хоста
- **Параметры:**
  - `host_name` (str): Имя хоста
  - `ssh_host` (str, optional): SSH адрес
  - `ssh_port` (int, optional): SSH порт
  - `ssh_user` (str, optional): SSH пользователь
  - `ssh_password` (str, optional): SSH пароль
  - `ssh_key_path` (str, optional): Путь к ключу
- **Возвращает:** None

#### `update_host_name(old_name, new_name)`
- **Описание:** Переименовывает хост и обновляет все FK
- **Параметры:**
  - `old_name` (str): Старое имя
  - `new_name` (str): Новое имя
- **Возвращает:** None

#### `update_host_url(host_name, new_url)`
- **Описание:** Обновляет URL панели хоста
- **Параметры:**
  - `host_name` (str): Имя хоста
  - `new_url` (str): Новый URL
- **Возвращает:** None

#### `update_host_subscription_url(host_name, new_subscription_url)`
- **Описание:** Обновляет URL подписки хоста
- **Параметры:**
  - `host_name` (str): Имя хоста
  - `new_subscription_url` (str): Новый URL подписки
- **Возвращает:** None

#### `delete_host(host_name)`
- **Описание:** Удаляет хост (проверяет отсутствие связанных тарифов)
- **Параметры:**
  - `host_name` (str): Имя хоста
- **Возвращает:** None
- **Исключения:**
  - `ValueError` — если есть тарифы на этом хосте

#### `get_host(host_name)`
- **Описание:** Получает информацию о хосте
- **Параметры:**
  - `host_name` (str): Имя хоста
- **Возвращает:** dict | None

#### `get_all_hosts()`
- **Описание:** Получает список всех хостов
- **Параметры:** Нет
- **Возвращает:** list[dict]

#### `get_squad(identifier)`
- **Описание:** Находит хост по имени или squad_uuid
- **Параметры:**
  - `identifier` (str): Имя хоста или Squad UUID
- **Возвращает:** dict | None

#### `normalize_host_name(name)`
- **Описание:** Нормализует имя хоста (lowercase + strip)
- **Параметры:**
  - `name` (str): Имя хоста
- **Возвращает:** str

---

## 💡 Примеры

### Пример 1: Создание нового хоста

```python
from src.shop_bot.data_manager import database

# 1. Создать хост
database.create_host(
    name="Server-EU-1",
    url="",
    subscription_url=""
)

# 2. Настроить Remnawave
database.update_host_remnawave_settings(
    host_name="server-eu-1",  # нормализуется автоматически
    remnawave_base_url="https://panel-eu.example.com",
    remnawave_api_token="your-api-token-here",
    squad_uuid="aaaa-bbbb-cccc-dddd"
)

# 3. Настроить SSH
database.update_host_ssh_settings(
    host_name="server-eu-1",
    ssh_host="185.123.45.67",
    ssh_port=22,
    ssh_user="root",
    ssh_password="your-password",
    ssh_key_path="/root/.ssh/id_rsa"
)

print("✅ Хост создан и настроен!")
```

### Пример 2: Получение всех хостов

```python
hosts = database.get_all_hosts()
for host in hosts:
    print(f"🖥 {host['host_name']}")
    print(f"   URL: {host['host_url']}")
    print(f"   Squad UUID: {host['squad_uuid']}")
    print(f"   Активен: {'Да' if host['is_active'] else 'Нет'}")
    print()
```

### Пример 3: Поиск хоста для создания ключа

```python
from src.shop_bot.data_manager import remnawave_repository as rw_repo

# Найти хост по имени
host = rw_repo.get_squad("server-eu-1")
if host:
    print(f"Найден хост: {host['host_name']}")
    print(f"Remnawave URL: {host['remnawave_base_url']}")
    print(f"Squad UUID: {host['squad_uuid']}")
else:
    print("Хост не найден")

# Найти хост по Squad UUID
host_by_uuid = rw_repo.get_squad("aaaa-bbbb-cccc-dddd")
if host_by_uuid:
    print(f"Найден хост: {host_by_uuid['host_name']}")
```

### Пример 4: Обновление URL подписки

```python
database.update_host_subscription_url(
    host_name="server-eu-1",
    new_subscription_url="https://sub.example.com/api/v1/client/subscribe?token={KEY}"
)
print("✅ URL подписки обновлен")
```

### Пример 5: Удаление хоста

```python
try:
    database.delete_host("server-eu-1")
    print("✅ Хост удален")
except ValueError as e:
    print(f"❌ Ошибка: {e}")
    # Например: "Невозможно удалить хост 'server-eu-1': существует 5 тарифов, привязанных к нему"
```

---

## 🔗 Связь с тарифами и ключами

### Взаимосвязи в базе данных

```
┌─────────────────────────────────────────────────────────┐
│                    Таблица: xui_hosts                   │
│  ┌────────────────────────────────────────────────┐    │
│  │ host_name (PK)                                 │    │
│  │ squad_uuid (UNIQUE)                            │    │
│  │ remnawave_base_url + remnawave_api_token       │    │
│  └────────────────────────────────────────────────┘    │
└─────────────┬───────────────────┬───────────────────────┘
              │                   │
         host_name (FK)      host_name (FK)
              │                   │
     ┌────────▼────────┐   ┌──────▼──────────┐
     │  Таблица: plans │   │ Таблица: vpn_keys│
     ├─────────────────┤   ├──────────────────┤
     │ plan_id (PK)    │   │ key_id (PK)      │
     │ host_name       │   │ host_name        │
     │ name            │   │ plan_id (FK)     │
     │ price           │   │ email            │
     │ duration_days   │   │ remnawave_uuid   │
     │ traffic_limit   │   │ description      │
     │ description     │   │ (JSON metadata)  │
     │ (JSON metadata) │   └──────────────────┘
     └─────────────────┘
```

### Как это работает:

1. **Создание тарифа:**
   ```python
   database.create_plan(
       name="Premium 1 месяц",
       price=500,
       duration_days=30,
       traffic_limit_gb=100,
       host_name="server-eu-1"  # Привязка к хосту
   )
   ```

2. **Покупка ключа:**
   - Пользователь выбирает тариф
   - Бот получает `host_name` из тарифа
   - Бот открывает squad конфигурацию через `get_squad(host_name)`
   - Бот создает ключ на Remnawave API используя настройки из хоста
   - Бот сохраняет ключ в `vpn_keys` с `host_name`

3. **Обновление ключа:**
   ```python
   # Получить хост ключа
   key = database.get_key_by_id(123)
   host_name = key['host_name']
   
   # Загрузить конфигурацию для API
   config = remnawave_api._load_config_for_host(host_name)
   
   # Обновить ключ через API
   await remnawave_api.update_user(
       user_uuid=key['remnawave_user_uuid'],
       data={...}
   )
   ```

### Денормализация для истории

При покупке ключа в поле `description` сохраняется JSON с данными тарифа и хоста:

```json
{
  "plan_name": "Premium 1 месяц",
  "plan_price": 500,
  "plan_duration_days": 30,
  "plan_traffic_limit_gb": 100,
  "host_name": "server-eu-1",
  "host_url": "https://panel-eu.example.com",
  "subscription_url": "https://sub.example.com/...",
  "purchase_date": "2025-02-01T12:00:00Z"
}
```

Это позволяет:
- ✅ Сохранить историю покупки даже если тариф/хост изменится
- ✅ Показать пользователю какие условия были на момент покупки
- ✅ Не терять данные при удалении тарифов

---

## ⚠️ Важные особенности

### 1. Нормализация имен
Все имена хостов автоматически приводятся к `lowercase` и обрезаются от пробелов. Это означает:
- `"Server-EU-1"` → `"server-eu-1"`
- `" My Host "` → `"my host"`

### 2. Защита от удаления
Нельзя удалить хост, если к нему привязаны тарифы. Сначала нужно удалить или перепривязать все тарифы.

### 3. Каскадное обновление при переименовании
При переименовании хоста автоматически обновляются:
- Все тарифы (`plans.host_name`)
- Все ключи (`vpn_keys.host_name`)

### 4. Fallback на глобальную конфигурацию
Если для хоста не указаны Remnawave настройки, используется глобальная конфигурация из `.env`:
- `REMNAWAVE_BASE_URL`
- `REMNAWAVE_API_TOKEN`

### 5. Squad UUID опционален
Если `squad_uuid` не указан, API будет работать с дефолтным Squad в Remnawave.

---

## 🔍 Troubleshooting

### Проблема: "Host not found"

**Причина:** Хост с указанным именем не существует в БД.

**Решение:**
```python
# Проверить существование
host = database.get_host("server-eu-1")
if not host:
    print("Хост не найден, создаем...")
    database.create_host("server-eu-1", subscription_url="")
```

### Проблема: "Remnawave API settings are not configured"

**Причина:** Для хоста не указаны `remnawave_base_url` или `remnawave_api_token`.

**Решение:**
```python
database.update_host_remnawave_settings(
    host_name="server-eu-1",
    remnawave_base_url="https://panel.example.com",
    remnawave_api_token="your-token"
)
```

### Проблема: "Невозможно удалить хост: существует N тарифов"

**Причина:** К хосту привязаны тарифы.

**Решение:**
```python
# 1. Получить тарифы хоста
plans = database.get_plans_by_host("server-eu-1")

# 2. Удалить все тарифы
for plan in plans:
    database.delete_plan(plan['plan_id'])

# 3. Теперь можно удалить хост
database.delete_host("server-eu-1")
```

### Проблема: SSH мониторинг не работает

**Причина:** Не настроены SSH параметры или неверный пароль/ключ.

**Решение:**
```python
database.update_host_ssh_settings(
    host_name="server-eu-1",
    ssh_host="185.123.45.67",
    ssh_port=22,
    ssh_user="root",
    ssh_password="correct-password"
)
```

---

## 📊 Статистика и мониторинг

### Получение статистики по хостам

```python
def get_host_statistics():
    """Получить статистику по всем хостам."""
    hosts = database.get_all_hosts()
    stats = []
    for host in hosts:
        host_name = host['host_name']
        # Количество тарифов
        plans = database.get_plans_by_host(host_name)
        # Количество активных ключей
        keys = database.get_keys_by_host(host_name)
        active_keys = [k for k in keys if k.get('status') == 'active']
        stats.append({
            'host': host_name,
            'plans_count': len(plans),
            'keys_total': len(keys),
            'keys_active': len(active_keys)
        })
    return stats
```

### Мониторинг доступности хостов

```python
from src.shop_bot.data_manager import resource_monitor

async def check_all_hosts_health():
    """Проверить состояние всех хостов."""
    hosts = database.get_all_hosts()
    for host in hosts:
        if not host.get('ssh_host'):
            continue
        try:
            stats = await resource_monitor.get_system_stats(
                ssh_host=host['ssh_host'],
                ssh_port=host['ssh_port'],
                ssh_user=host['ssh_user'],
                ssh_password=host['ssh_password']
            )
            print(f"✅ {host['host_name']}: CPU {stats['cpu']}%, RAM {stats['ram']}%")
        except Exception as e:
            print(f"❌ {host['host_name']}: {e}")
```

---

## 🎓 Заключение

Система управления хостами обеспечивает:
- ✅ Гибкую конфигурацию множества VPN-серверов
- ✅ Интеграцию с Remnawave API (включая мультитенантность)
- ✅ SSH мониторинг и speedtest
- ✅ Привязку тарифов и ключей к конкретным серверам
- ✅ Удобные интерфейсы управления (Telegram бот + web панель)

**Ключевые файлы:**
- [src/shop_bot/data_manager/database.py](src/shop_bot/data_manager/database.py) — CRUD операции
- [src/shop_bot/bot/admin_handlers.py](src/shop_bot/bot/admin_handlers.py) — Telegram админ-панель
- [src/shop_bot/webhook_server/app.py](src/shop_bot/webhook_server/app.py) — Web маршруты
- [src/shop_bot/modules/remnawave_api.py](src/shop_bot/modules/remnawave_api.py) — API интеграция
- [src/shop_bot/data_manager/remnawave_repository.py](src/shop_bot/data_manager/remnawave_repository.py) — Репозиторий хостов

**Связанные документы:**
- [TARIFFS_GUIDE.md](TARIFFS_GUIDE.md) — Документация по тарифам
- [VPN_KEYS_DOCUMENTATION.md](VPN_KEYS_DOCUMENTATION.md) — Документация по ключам

---

*Документация актуальна на 2025 год. При изменении структуры БД или API необходимо обновление.*
