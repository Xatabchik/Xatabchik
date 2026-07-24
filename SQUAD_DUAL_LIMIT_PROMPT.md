# Промт: Двухсквадовая архитектура (SQUAD_BASE + SQUAD_LTE) с раздельными лимитами

> Это техническое задание/промт для реализации изменения модели сквадов Remnawave.
> Использовать как контекст при следующей итерации доработки LTE-модуля.

## 1. Цель

Один пользователь Remnawave (одна подписка, один `subscription_url`) должен одновременно
состоять в **двух и более internal squad'ах**:

- **SQUAD_BASE** (∞) — inbound'ы базовых нод. Лимит по нему видит и энфорсит **сама панель**
  Remnawave через штатный `trafficLimitBytes` пользователя.
- **SQUAD_LTE** (💰) — inbound'ы премиум/LTE нод. Лимит по нему считает и энфорсит **бот**
  (панель ничего не знает про "LTE-лимит" как отдельную сущность).

При исчерпании основного лимита (`trafficLimitBytes`) панель переводит пользователя в
`LIMITED` — гаснут **оба** сквада (весь доступ). Это штатное поведение, менять не нужно.

При исчерпании LTE-лимита бот **не трогает** `trafficLimitBytes` и не переводит пользователя
в `LIMITED` — он просто убирает `SQUAD_LTE` из `activeInternalSquads` через
`PATCH /api/users`. Премиум-ноды пропадают из подписки, базовые продолжают работать.
При докупке/сбросе LTE бот возвращает `SQUAD_LTE` обратно в список.

## 2. Классификация сквадов при добавлении (административная часть)

Сейчас в проекте сквад/хост привязывается по одному `squad_uuid` на хост (см. `plans.squad_uuid`,
`xui_hosts.squad_uuid` в `src/shop_bot/data_manager/database.py`,
`src/shop_bot/webhook_server/templates/settings.html` — поле `squad_uuid` в форме хоста).

Нужно расширить модель так, чтобы **при добавлении/редактировании сквада** (в веб-панели и/или
в Telegram-админке) явно указывался **класс сквада**:

```
squad_class = 'base' | 'lte' | 'other'
```

- `base` — обычный, безлимитный по умолчанию сквад (учитывается в основном `trafficLimitBytes`).
- `lte` — премиум/LTE сквад, по нему ведётся отдельный учёт ботом.
- `other` — резерв на будущее (доп. пулы, спец-ноды и т.п.), не участвует в LTE-логике,
  не удаляется автоматически.

### Изменения в БД

Новая таблица (или расширение существующей, если сквады уже хранятся отдельно от хостов):

```sql
CREATE TABLE IF NOT EXISTS host_squads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_name TEXT NOT NULL,
    squad_uuid TEXT NOT NULL,
    squad_class TEXT NOT NULL DEFAULT 'base', -- 'base' | 'lte' | 'other'
    label TEXT,                                -- человекочитаемое имя (для админки)
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(host_name, squad_uuid)
);
```

Если сейчас `squad_uuid` хранится по одному полю в `xui_hosts`/`plans` — нужна миграция:
существующее значение переносится как запись с `squad_class='base'`, плюс добавляется
интерфейс для привязки второго (LTE) сквада к тому же хосту.

Функции в `database.py` (или `remnawave_repository.py`):

- `add_host_squad(host_name, squad_uuid, squad_class, label=None) -> int`
- `get_host_squads(host_name) -> list[dict]`
- `get_squad_by_class(host_name, squad_class) -> dict | None` — быстрый доступ к
  "базовому" и "LTE" сквадам хоста.
- `set_host_squad_active(squad_id, is_active)`
- `delete_host_squad(squad_id)`

### UI (веб-панель, `settings.html`)

В блоке добавления/редактирования хоста вместо одного поля `squad_uuid` — список сквадов
хоста с возможностью добавить ещё один и обязательным выбором класса:

```
Сквады хоста:
  [🌐 Base]  <squad_uuid_1>   [класс: Базовый ▾]   [Удалить]
  [💰 LTE ]  <squad_uuid_2>   [класс: LTE     ▾]   [Удалить]
  + Добавить сквад: [squad_uuid ____] [класс ▾: Базовый/LTE/Другое] [Добавить]
```

Правила валидации:
- На хост допускается **не более одного** активного сквада класса `base` и **не более одного**
  активного сквада класса `lte` (иначе неоднозначно, что энфорсить). Класс `other` — без
  ограничения по количеству.
- Если у хоста ещё нет `lte`-сквада — LTE-функции (топап, лимит, кнопки в боте) для тарифов
  этого хоста должны быть скрыты/недоступны (уже частично реализовано через
  `has_traffic_limit`/`plan.lte_limit_bytes` — здесь добавляется ещё проверка на уровне хоста).

## 3. Учёт LTE-трафика: путь получения данных

Два варианта API Remnawave, выбор в зависимости от версии панели:

1. **v2.8.0+** (предпочтительно): `POST /api/bandwidth-stats/nodes/users` — пер-пользовательская
   статистика сразу по нодам. (Уже частично заложено в `resource_monitor.py`/scheduler-воркере —
   проверить и оставить как основной путь.)
2. **Универсальный (legacy, для старых версий панели)**:
   `GET /api/nodes/{node_uuid}/usage/range` (в SDK — `getNodeUserUsageByRange(node_uuid, startDate, endDate)`).
   Возвращает расход **всех** пользователей на конкретной ноде за период — из ответа
   (`UserUsageDto`: `user_uuid`, `node_uuid`, `total`, `date`) фильтруется свой `user_uuid`.
   Этот путь используется как fallback, если основной v2.8.0+ эндпоинт недоступен/возвращает 404,
   и вообще как основной способ во избежание 429, если по опыту других ботов основной эндпоинт
   слишком тяжёлый при большом числе пользователей.

Функции в `remnawave_api.py`:

- `get_node_usage_range(node_uuid, start_date, end_date) -> list[UserUsageDto]` (legacy per-node).
- `get_bandwidth_stats_nodes_users(...) -> ...` (v2.8.0+, если ещё не реализовано — проверить).
- Обёртка `get_user_lte_usage_bytes(user_uuid, lte_node_uuids, start_date, end_date) -> int`,
  которая сама выбирает путь (v2.8.0+ → fallback legacy) и суммирует `total` только по нодам,
  входящим в `SQUAD_LTE` (нужен маппинг squad → список node_uuid, если Remnawave отдаёт ноды
  сквада отдельным эндпоинтом, либо фильтрация на основе конфигурации сквада).

## 4. КРИТИЧЕСКИ ВАЖНО: точка отсчёта (baseline) LTE-периода

Панель Remnawave хранит расход по нодам **накопительно** (за всю историю или с начала месяца
по своим настройкам), а не "с момента сброса LTE у конкретного пользователя". Поэтому бот
**не может** просто спросить "сколько сейчас израсходовано на LTE-нодах" и сравнить с лимитом —
после любого сброса/докупки LTE счётчик мгновенно снова покажет полное историческое значение.

### Решение: хранить baseline на ключе/подписке

В таблице ключей (`vpn_keys` или аналог) добавить поле:

```sql
ALTER TABLE vpn_keys ADD COLUMN lte_used_baseline_bytes INTEGER DEFAULT 0;
```

Логика:

```
lte_usage_now_raw = SUM(total по LTE-нодам за текущий период, из API)
lte_usage_effective = max(0, lte_usage_now_raw - lte_used_baseline_bytes)

if lte_usage_effective >= plan.lte_limit_bytes:
    # убрать SQUAD_LTE из activeInternalSquads пользователя
    remove_lte_squad(user_uuid)
```

`lte_used_baseline_bytes` обновляется на **текущее значение `lte_usage_now_raw`** в двух
случаях:
1. При **докупке LTE-пакета** (пользователь купил доп. ГБ LTE) — новый лимит = старый остаток
   + купленный пакет, точка отсчёта сдвигается на "сейчас", чтобы не пересчитывать задним числом.
2. При **сбросе/новом периоде тарифа** (ежемесячный ролловер, платный/бесплатный сброс основного
   пула — если по бизнес-логике сброс основного пула также обнуляет LTE-счётчик, см. п.5) —
   baseline = текущее `lte_usage_now_raw` на момент сброса.
3. При **добавлении SQUAD_LTE обратно** после того, как он был снят (искусственный "новый старт
   периода") — тоже обновляем baseline.

Важно: baseline обновляется **до** того, как воркер в следующий раз проверит лимит, иначе
возможна гонка (успеет сработать сравнение со старым baseline).

### Проверить в текущей реализации

В отчёте предыдущей итерации фигурирует `lte_boost_bytes`, но нет явного упоминания
baseline/точки отсчёта расхода по нодам. Нужно:
1. Найти воркер, который считает LTE-расход (scheduler/resource_monitor), и проверить, с чем
   он сравнивает: с накопительным API-значением напрямую (баг) или с разницей от baseline (ок).
2. Если baseline отсутствует — добавить колонку `lte_used_baseline_bytes`, прокинуть её
   инициализацию при выдаче ключа (baseline = текущий расход на момент выдачи, обычно 0,
   но на случай если сквад уже использовался — берём фактическое значение API), и обновлять
   в местах, описанных выше.

## 5. Энфорсинг (воркер)

Периодическая задача (уже существующий scheduler-воркер для dual-limit, интервал настраивается
через `dual_limit_interval_sec` в админке):

```
for each active key with plan.lte_limit_bytes > 0:
    lte_node_uuids = get_lte_node_uuids_for_host(key.host_name)  # по squad_class='lte'
    lte_usage_now_raw = get_user_lte_usage_bytes(user_uuid, lte_node_uuids, period_start, now)
    lte_usage_effective = max(0, lte_usage_now_raw - key.lte_used_baseline_bytes)

    lte_squad_currently_active = SQUAD_LTE in user.activeInternalSquads (текущее состояние в Remnawave)

    if lte_usage_effective >= plan.lte_limit_bytes and lte_squad_currently_active:
        remove_squad_from_user(user_uuid, lte_squad_uuid)   # PATCH /api/users
        # уведомить пользователя в боте: "LTE-лимит исчерпан, премиум-ноды отключены"

    elif lte_usage_effective < plan.lte_limit_bytes and not lte_squad_currently_active:
        # например, после докупки/сброса — вернуть сквад, если баланс позволяет
        add_squad_to_user(user_uuid, lte_squad_uuid)
```

`remove_squad_from_user`/`add_squad_to_user` — обёртки над `PATCH /api/users`, формирующие
новый список `activeInternalSquads` (базовый сквад остаётся всегда, LTE — добавляется/убирается).

## 6. Что нужно проверить/доделать по итогам предыдущей реализации

1. ✅/❓ Убедиться, что таблица `plans` действительно хранит `lte_limit_bytes` и
   `main_reset_price_rub` (уже сделано в этой сессии).
2. ❓ Найти, где сейчас в проекте задаётся `squad_uuid` для LTE-нод — судя по коду, сейчас
   на хост приходится **один** `squad_uuid` (в `xui_hosts`/`plans`). Нужно расширение до
   двух сквадов на хост (см. п.2) — это структурное изменение, требует миграции.
3. ❓ Проверить актуальный воркер (`resource_monitor.py`/`scheduler.py`) на предмет:
   - использует ли он baseline (`lte_used_baseline_bytes`) или сравнивает с сырым значением API;
   - какой путь получения статистики использует (v2.8.0+ или legacy per-node) и есть ли fallback;
   - обновляется ли baseline при докупке LTE и при сбросе основного пула.
4. ❓ Добавить в веб-панель и/или Telegram-админку явный выбор `squad_class` при добавлении
   сквада к хосту (сейчас, судя по `settings.html`, поле одно — `squad_uuid` без классификации).

## 7. Итоговый чек-лист для реализации

- [ ] Миграция БД: таблица `host_squads` (или аналог) с полем `squad_class`.
- [ ] Перенос существующих `squad_uuid` хостов в `host_squads` с классом `base`.
- [ ] UI веб-панели: список сквадов хоста + добавление нового с выбором класса.
- [ ] UI Telegram-админки: аналогичное управление сквадами хоста (класс base/lte/other).
- [ ] Колонка `lte_used_baseline_bytes` в таблице ключей.
- [ ] Функция расчёта `lte_usage_effective = raw - baseline` во воркере.
- [ ] Обновление baseline при: выдаче ключа, докупке LTE, сбросе основного пула (если применимо),
      возврате SQUAD_LTE пользователю.
- [ ] Функции `remove_squad_from_user` / `add_squad_to_user` (PATCH `/api/users`,
      манипуляция `activeInternalSquads` с сохранением базового сквада).
- [ ] Fallback между `POST /api/bandwidth-stats/nodes/users` (v2.8.0+) и
      `GET /api/nodes/{node_uuid}/usage/range` (legacy) с фильтрацией по `user_uuid`.
- [ ] Уведомление пользователя в боте при отключении/включении LTE-сквада.
