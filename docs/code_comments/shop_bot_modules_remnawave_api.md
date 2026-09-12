# Комментарии: `src/shop_bot/modules/remnawave_api.py`

Единственный HTTP-клиент панели Remnawave в проекте: выдача VPN-ключей (`create_or_update_key_on_host` → `ensure_user`), HWID, сквады, LTE-статистика. Других panel-клиентов нет. Модульного docstring нет.

В коде `#` про общий httpx-пул: каждый Flask-handler делает `asyncio.run` (новый loop), клиент привязан к loop, поэтому `_CLIENTS` + `_CLIENTS_LOOP` + `threading.Lock`; протухший клиент не `aclose()`, а отбрасывается. `_MAX_INFLIGHT = 16` ниже `max_connections=100`, иначе WebApp `gather` ловит PoolTimeout.

Enable/disable: HTTP 400 с A030 «already enabled» / A029 «already disabled» — успех. Usage-пути кэшируются по `base_url` панели (TTL 3600 с), ноды сквада — по `squad_uuid` (TTL 600 с, негативный 120 с).

## `RemnawaveAPIError` (24–25)

**Docstring в коде:** есть

```
Base error for Remnawave API interactions.
```

## `_detail_is_already_in_desired_state` (34–44)

**Docstring в коде:** есть

```
True, если панель ответила, что пользователь уже enable/disable — это успех.
```

## `_is_already_in_desired_state` (47–48)

**Docstring в коде:** нет. По коду: в `_detail_is_already_in_desired_state` уходит только `str(exc)`, не JSON-dict.

```
"""True, если str(exc) содержит A030/A029 или «already enabled/disabled»."""
```

## `_inflight_semaphore` (76–83)

**Docstring в коде:** нет. В коде `#`: WebApp gather без лимита исчерпывает пул httpx (PoolTimeout).

```
"""Семафор текущего event loop с потолком _MAX_INFLIGHT (16)."""
```

## `_client_request` (86–100)

**Docstring в коде:** есть

```
Один HTTP-запрос к панели с лимитом параллелизма.

PoolTimeout = в пуле не осталось свободных соединений. Семафор не даёт
набрать больше запросов, чем пул может обслужить; таймаут всё равно
превращаем в RemnawaveAPIError без сырого traceback httpx.
```

## `gather_limited` (103–115)

**Docstring в коде:** есть

```
asyncio.gather с потолком параллелизма — для списка ключей в WebApp.
```

## `gather_limited._run` (111–113)

**Docstring в коде:** нет

```
"""Выполнить одну корутину под семафором gather_limited."""
```

## `_get_shared_client` (118–144)

**Docstring в коде:** нет. В коде `#` про Flask `asyncio.run` (новый loop) и запрет `aclose()` чужого клиента.

```
"""Вернуть общий httpx.AsyncClient для (base_url, token, is_local); пересоздать, если loop другой или клиент закрыт."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 124–129 | тот же loop, клиент жив | вернуть кэш |
| 130–136 | is_stale | pop ссылок, не aclose() — loop мог быть уже закрыт |
| 137–144 | иначе | новый AsyncClient в текущем loop |

## `_normalize_email_for_remnawave` (147–178)

**Docstring в коде:** есть

```
Normalize and validate email for Remnawave API.

- Lowercases the email
- If domain is missing or email invalid, tries to sanitize local-part by replacing
  any characters outside [a-z0-9._+-] with '_'
- Validates with a conservative regex that excludes '/'
- Raises RemnawaveAPIError if validation still fails
```

## `_normalize_username_for_remnawave` (181–206)

**Docstring в коде:** есть

```
Normalize username to only letters, numbers, underscores and dashes.

- Lowercase
- Replace invalid characters with '_'
- Trim leading/trailing '_' and '-'
- Ensure starts with alnum; if not, prefix with 'u'
- Limit length to 32 characters
- Fallback to 'user<timestamp>' if empty
```

## `_load_config` (208–216)

**Docstring в коде:** есть

```
Backward-compatible global config loader (deprecated).
```

## `_load_config_for_host` (219–234)

**Docstring в коде:** есть. По коду: пустые url/token хоста → `_load_config()`; если и глобальные пусты — ошибка про этот host.

```
Load Remnawave API config for a specific host from xui_hosts.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 226–227 | нет url/token у хоста | fallback `_load_config()` (глобальные settings) |
| 232–233 | и глобальные пусты | RemnawaveAPIError про этот host |

## `_build_headers` (237–245)

**Docstring в коде:** нет

```
"""Authorization Bearer и Content-Type JSON; при is_local добавить X-Forwarded-Proto/For."""
```

## `_request` (248–293)

**Docstring в коде:** нет

```
"""HTTP к глобальной панели (_load_config): лог, _client_request, RemnawaveAPIError если статус не expected."""
```

## `_request_for_host` (296–341)

**Docstring в коде:** нет

```
"""То же, что _request, но URL/токен из _load_config_for_host(host_name)."""
```

## `_to_iso` (344–348)

**Docstring в коде:** нет

```
"""datetime в ISO-8601 UTC с суффиксом Z (naive считается UTC)."""
```

## `_extract_user_from_api_payload` (351–363)

**Docstring в коде:** есть

```
Normalize Remnawave user lookup payloads (wrapped, list, or bare dict).
```

## `get_user_by_email` (366–376)

**Docstring в коде:** нет

```
"""GET /api/users/by-email/{email} на хосте или глобально; 404 → None."""
```

## `get_user_by_username` (379–389)

**Docstring в коде:** нет

```
"""GET /api/users/by-username/{username} на хосте или глобально; 404 → None."""
```

## `_classify_panel_user_ref` (398–407)

**Docstring в коде:** есть

```
id — числовой userId 3.x; uuid — старый идентификатор 2.x; short — shortUuid.
```

## `_username_from_email` (410–416)

**Docstring в коде:** есть

```
Локальная часть email → username, как при создании пользователя в панели.
```

## `_panel_numeric_user_id` (419–429)

**Docstring в коде:** есть

```
Числовой userId 3.x из payload пользователя, если он есть.
```

## `panel_user_ref_from_payload` (432–441)

**Docstring в коде:** есть

```
Идентификатор для путей `{userId}`: на 3.x это числовой id, на 2.x — uuid.
```

## `_panel_user_get_path` (444–454)

**Docstring в коде:** есть

```
Путь GET пользователя и допустимые статусы (3.x ждёт число, UUID даёт 400 NaN).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 449–450 | kind id | `/api/users/{число}` — 200/404 (3.x) |
| 451–453 | kind uuid | тот же путь, expected 200/400/404: 3.x даёт 400 NaN |
| 454 | short | `/api/users/by-short-uuid/{ref}` |

## `_panel_hwid_devices_path` (457–466)

**Docstring в коде:** есть

```
GET /api/hwid/devices/{userId}: 3.x ждёт число, UUID даёт 400 NaN.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 462–463 | kind id | `/api/hwid/devices/{число}` |
| 464–465 | kind uuid | тот же путь, 400 NaN на 3.x допустим |
| 466 | short | `("", ())` — HWID по shortUuid не зовут |

## `get_user_by_uuid` (469–480)

**Docstring в коде:** нет

```
"""GET пользователя по id/uuid/shortUuid через _panel_user_get_path; статус ≠ 200 → None."""
```

## `lookup_panel_user` (483–509)

**Docstring в коде:** есть

```
Найти пользователя панели: id / uuid / shortUuid, затем email, затем username.

На Remnawave 3.x GET /api/users/by-email/{email} снят, а GET /api/users/{uuid}
отвечает 400 NaN. Рабочие lookup: числовой id, by-username, by-short-uuid.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 495–498 | есть user_ref | `get_user_by_uuid` (id / uuid / short) |
| 500–503 | email | `get_user_by_email` (на 3.x путь снят — может быть 404) |
| 504–508 | не найден | `get_user_by_username` из local-part — рабочий lookup 3.x |

## `panel_user_exists` (512–542)

**Docstring в коде:** есть

```
Есть ли пользователь на панели.

True — найден; False — подтверждённо отсутствует; None — нельзя решить
(UUID на 3.x даёт 400, by-email может быть снят, сеть/API ошибка).
False только после 404 на поддерживаемом lookup (id / shortUuid / username)
либо 404 UUID на 2.x — никогда из одного 404 by-email.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 527–528 | lookup нашёл | True |
| 531–533 | есть username из email | False: by-username уже дал 404 (3.x) |
| 534–535 | kind id/short | False: поддерживаемый lookup пуст |
| 536–538 | UUID без email | None: 400 на 3.x ≠ удаление |
| 539–542 | API/прочее | None |

## `_extract_hwid_devices_payload` (545–553)

**Docstring в коде:** нет

```
"""Достать тело HWID из response/data/list или вернуть payload как есть."""
```

## `_get_hwid_devices_by_ref` (556–566)

**Docstring в коде:** нет

```
"""GET /api/hwid/devices/{userId} по ref; вернуть (status, payload|None)."""
```

## `get_hwid_devices_for_user` (569–613)

**Docstring в коде:** есть

```
Получить информацию об HWID-устройствах пользователя.

В Remnawave HWID устройства живут отдельным endpoint'ом и не всегда
возвращаются внутри /api/users. Поэтому для корректного подсчёта
подключённых устройств используем этот запрос как источник истины.

3.x: путь ждёт числовой userId. UUID в сегменте даёт 400 NaN — тогда
резолвим id через lookup (email/username) и повторяем запрос.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 587–592 | kind id/uuid | прямой GET; 200 → payload; id или 404 → None |
| 594–600 | иначе / 400 на uuid | lookup → числовой id 3.x, повтор GET |
| 601–608 | нет numeric | fallback uuid из payload (2.x) |
| 609–613 | API/прочее | None |

## `_resolve_hwid_owner` (616–637)

**Docstring в коде:** есть

```
Числовой userId 3.x и/или uuid 2.x для HWID API.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 626–629 | user_id / kind id | числовой id сразу |
| 627 | kind uuid | uuid_val = stored |
| 630–636 | numeric ещё None | lookup: id из payload и/или uuid |

## `delete_hwid_device` (640–702)

**Docstring в коде:** есть

```
Удалить одно HWID-устройство пользователя через API.

Remnawave 3.x требует числовой `userId`; `userUuid` игнорируется → 400
`expected number, received undefined`. Резолвим id из хранимого ref / lookup.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 662–665 | payload | 3.x: `userId` int; 2.x: `userUuid`; шлём оба, если есть |
| 666–668 | нет ни того ни другого | False |
| 686–688 | HTTP 404 | True (уже нет) |
| 690–692 | 200/204 | True |

## `get_connected_devices_count` (705–724)

**Docstring в коде:** есть

```
Обёртка над get_hwid_devices_for_user для webapp: всегда возвращает
dict с ключом "devices" (список), даже если исходный ответ Remnawave —
просто список или пуст.
```

## `delete_user_device` (727–738)

**Docstring в коде:** есть

```
Алиас delete_hwid_device с именем, ожидаемым webapp/handlers.py.
```

## `ensure_user` (741–919)

**Docstring в коде:** нет. В коде `#`: lookup по username, если email пустой/другой (A019); hwid из SQLite может быть TEXT; PATCH шлёт uuid и id (2.x / 3.x).

```
"""Создать (POST) или обновить (PATCH) пользователя панели на хосте: срок, сквады, лимиты."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 764–775 | нет по email | lookup по username (A019) |
| 790–836 | current есть | PATCH `/api/users`, uuid+id, expire не короче текущего |
| 837–864 | нет | POST `/api/users` |
| 869–902 | POST + A019 | найти по username и PATCH |
| 905–908 | нет response | RemnawaveAPIError |

## `list_users` (924–1110)

**Docstring в коде:** есть. По коду: сначала страница без page; если size задан и first_len < page_size — одна страница. Дальше `_try_paged(1)` (0-based), иначе `_try_paged(2)` (1-based), иначе offset/skip/from. Если пагинация не дала новых — warning и первая страница.

```
List users from Remnawave.

IMPORTANT:
- Some Remnawave deployments paginate /api/users and may return only the first N records.
- Historically the bot used size=500 and then удалял локальные ключи, если они не попадали в первую страницу.
- Этот helper пытается забрать *все* страницы (фактически «без лимита»), но с защитой от бесконечных циклов
  (детект дубликатов + max_pages).

Args:
    host_name: Remnawave host name.
    squad_uuid: If provided, request users for this squad (server-side) and also apply a defensive filter.
    size: Подсказка размера страницы. Если None — параметр size не отправляется, используется дефолт панели.
    max_pages: Страховочный лимит числа запросов/страниц (на случай, если API отдаёт бесконечную ленту).

Returns:
    A list of user dicts.
```

## `list_users._extract_users_from_payload` (949–956)

**Docstring в коде:** нет

```
"""Достать список dict-пользователей из users/data/items/list ответа."""
```

## `list_users._filter_by_squad` (958–975)

**Docstring в коде:** нет

```
"""Оставить пользователей, у которых squad_uuid есть в activeInternalSquads (dict или str)."""
```

## `list_users._fetch` (977–981)

**Docstring в коде:** нет

```
"""GET /api/users с params; вернуть (список пользователей, длина)."""
```

## `list_users._uid` (1004–1005)

**Docstring в коде:** нет

```
"""Идентификатор записи: uuid, иначе id, иначе email/accountEmail."""
```

## `list_users._append_new` (1007–1021)

**Docstring в коде:** нет

```
"""Добавить в all_users ещё не виденных по _uid; без ident — всегда append."""
```

## `list_users._try_paged` (1042–1065)

**Docstring в коде:** есть

```
Return True if paging seems to work (we got new users).
```

## `delete_user` (1111–1123)

**Docstring в коде:** есть

```
Глобальный вариант (устарел): удаление без привязки к хосту.
Сохраняется для обратной совместимости, но предпочтительно использовать host-specific путь ниже.
```

## `delete_user_on_host` (1126–1136)

**Docstring в коде:** есть

```
Удаление пользователя на конкретном хосте, используя конфиг хоста.
```

## `reset_user_traffic` (1139–1144)

**Docstring в коде:** нет

```
"""POST /api/users/{uuid}/actions/reset-traffic на глобальной панели."""
```

## `update_user_traffic_limit` (1147–1157)

**Docstring в коде:** есть

```
Обновляет лимит трафика (trafficLimitBytes) пользователя в Remnawave.
```

## `set_user_status` (1160–1184)

**Docstring в коде:** нет

```
"""POST enable или disable на глобальной панели; «уже в нужном состоянии» — успех."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1170–1177 | HTTP 400 + already desired | True |
| 1178 | 400 иное | RemnawaveAPIError |
| 1181–1183 | RemnawaveAPIError already desired | True |

## `_extract_used_traffic_bytes` (1187–1196)

**Docstring в коде:** нет

```
"""Первое положительное usedTrafficBytes / trafficUsedBytes / traffic_used_bytes / usedBytes."""
```

## `disable_user` (1199–1227)

**Docstring в коде:** есть

```
POST /api/users/{uuid}/actions/disable — скрыть ноду (используется для 💰-premium нод при исчерпании LTE
или для всех нод при исчерпании основного пула трафика).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1210–1217 | HTTP 400 + already disabled | True |
| 1218–1219 | 400 иное | False |
| 1223–1225 | Exception already disabled | True |

## `enable_user` (1230–1257)

**Docstring в коде:** есть

```
POST /api/users/{uuid}/actions/enable — вернуть доступ пользователю на конкретном хосте.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1240–1247 | HTTP 400 + already enabled | True |
| 1248–1249 | 400 иное | False |
| 1253–1255 | Exception already enabled | True |

## `set_user_active_squads` (1260–1287)

**Docstring в коде:** есть. В коде `#`: PATCH идентифицирует по числовому `id` (3.3.2) или `uuid` (2.8.1).

```
PATCH /api/users — установить полный список activeInternalSquads пользователя.

В отличие от enable_user/disable_user (которые полностью открывают/закрывают доступ на хосте),
это позволяет точечно управлять членством в конкретном сквада (например, отключить только
LTE-сквад, оставив Base-сквад активным — двухпуловая схема).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1273–1275 | stored.isdigit() | payload `id` int (3.x); иначе `uuid` (2.x) |

## `extract_active_squad_uuids` (1290–1311)

**Docstring в коде:** есть

```
UUID активных internal-сквадов пользователя из ответа панели.

ВАЖНО: `activeInternalSquads` в ответе — массив ОБЪЕКТОВ (`{uuid, name, ...}`), и в
2.8.1, и в 3.3.2, тогда как `PATCH /api/users` принимает массив строк-UUID. Сравнение
строки с объектами всегда давало «сквада нет», из-за чего remove_squad_from_user
возвращал ложный успех и LTE-сквад не снимался при исчерпании лимита.
```

## `remove_squad_from_user` (1314–1334)

**Docstring в коде:** есть

```
Убрать конкретный сквад из activeInternalSquads пользователя, не трогая остальные сквады.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1321–1326 | сквада уже нет | True (идемпотентно) |

## `add_squad_to_user` (1337–1353)

**Docstring в коде:** есть

```
Добавить конкретный сквад в activeInternalSquads пользователя, не трогая остальные сквады.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1344–1345 | сквад уже есть | True (идемпотентно) |

## `get_user_used_traffic` (1356–1374)

**Docstring в коде:** есть

```
Использованный трафик (в байтах) пользователя на конкретном инстансе Remnawave. 0, если данных нет.
```

## `reset_user_traffic_on_host` (1377–1387)

**Docstring в коде:** есть

```
POST /api/users/{uuid}/actions/reset-traffic на конкретном инстансе (host-aware вариант reset_user_traffic).
```

## `_extract_usage_rows` (1390–1405)

**Docstring в коде:** есть

```
Достаёт список записей UserUsageDto из ответа Remnawave независимо от обёртки ({"response": [...]}, просто [...]).
```

## `get_node_usage_range` (1408–1436)

**Docstring в коде:** есть

```
Legacy per-node usage endpoint: GET /api/nodes/{node_uuid}/usage/range.

Возвращает расход ВСЕХ пользователей на конкретной ноде за период
(UserUsageDto: userUuid/user_uuid, nodeUuid/node_uuid, total, date).
Используется как fallback, если v2.8.0+ bandwidth-stats эндпоинт недоступен.
```

## `get_bandwidth_stats_nodes_users` (1439–1469)

**Docstring в коде:** есть

```
v2.8.0+ endpoint: POST /api/bandwidth-stats/nodes/users.

Пер-пользовательская статистика сразу по списку нод за период — один запрос вместо N (по ноде),
предпочтительный путь при доступности панели версии 2.8.0+.
```

## `get_user_lte_usage_bytes` (1472–1521)

**Docstring в коде:** есть

```
Суммарный расход конкретного пользователя по нодам LTE-сквада за период.

Порядок попыток:
  1. v2.8.0+ `POST /api/bandwidth-stats/nodes/users` — один запрос сразу по всем нодам.
  2. Fallback: legacy `GET /api/nodes/{uuid}/usage/range` по каждой ноде отдельно (для старых панелей
     или если основной эндпоинт вернул 404/пусто).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1506–1510 | bandwidth-stats > 0 | вернуть сумму (v2.8.0+) |
| 1511–1512 | исключение / пусто | warning, fallback |
| 1514–1521 | per-node usage/range | сложить по каждой LTE-ноде |

## `get_user_lte_usage_bytes._sum_for_user` (1492–1503)

**Docstring в коде:** нет

```
"""Сумма total/totalBytes/bytes в строках, где userUuid/user_uuid совпал."""
```

## `RemnawavePathUnsupportedError` (1539–1545)

**Docstring в коде:** есть

```
Путь не поддерживается этой версией панели (404 / 400 / 422 на валидации параметра).

Отделено от сетевых и 5xx-ошибок намеренно: «версия не умеет этот путь» — повод
попробовать следующего кандидата в цепочке, а «панель недоступна» — повод пропустить
ключ на этом проходе и НЕ записывать нулевой расход.
```

## `invalidate_squad_nodes_cache` (1557–1566)

**Docstring в коде:** есть

```
Сбросить кэш нод сквада (целиком или по одному squad_uuid), включая негативный.
```

## `_request_optional_path` (1569–1597)

**Docstring в коде:** есть

```
Запрос к пути, которого может не быть в этой версии панели.

Возвращает None, если панель ответила 404 (маршрута нет) либо 400/422 (маршрут есть,
но параметр другого типа — например, числовой userId вместо UUID в 3.3.2 против 2.8.1).
Сетевые ошибки и 5xx пробрасываются как RemnawaveAPIError/httpx-исключения.
```

## `get_squad_accessible_nodes` (1600–1699)

**Docstring в коде:** есть. В коде `#`: 401/403 vs 404 разбираются отдельно (токен vs нет сквада).

```
Ноды, доступные через internal squad: `GET /api/internal-squads/{uuid}/accessible-nodes`.

Возвращает список словарей нод (`uuid`, `nodeName`, `countryCode`, `configProfileUuid`,
`configProfileName`, `activeInbounds`) — схема подтверждена для 2.8.1 и 3.3.2.

Пустой список означает «у сквада действительно нет доступных нод». Любой сбой запроса —
исключение, а не пустой список: иначе «не удалось узнать» было бы неотличимо от «нод нет»
и привело бы к нулевому расходу и ложному «лимит не исчерпан».

Кэш TTL 10 минут с ключом `squad_uuid` (не `host_name`: два разных host_name, смотрящих
в одну панель, обязаны переиспользовать один и тот же список нод).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1622–1626 | кэш hit, TTL 600 с | вернуть копию списка |
| 1627–1633 | негативный кэш, TTL 120 с | пробросить ту же RemnawaveAPIError |
| 1655–1662 | 401/403 | авторизация, не «сквада нет» |
| 1663–1668 | 404 | сквад не найден |
| 1697–1698 | успех | записать позитивный кэш |

## `get_squad_accessible_nodes._remember_failure` (1638–1642)

**Docstring в коде:** нет

```
"""Записать ошибку сквада в негативный кэш (TTL 120 с) и вернуть RemnawaveAPIError."""
```

## `get_squad_nodes_for_class` (1702–1725)

**Docstring в коде:** есть

```
Ноды активного сквада заданного класса ('lte'/'base') у хоста.

Пустой список, если сквад такого класса не настроен — это легитимная конфигурация
(лог info, не ошибка). Сбой обращения к панели пробрасывается наверх.
```

## `get_lte_nodes_for_host` (1728–1730)

**Docstring в коде:** есть

```
Ноды активного LTE-сквада хоста (с именами — для карточки ключа и снапшотов).
```

## `get_lte_node_uuids_for_host` (1733–1738)

**Docstring в коде:** есть

```
UUID нод активного LTE-сквада хоста.

`[]` — LTE-сквад не настроен (легитимно). Сбой обращения к панели — исключение.
```

## `NodeUsage` (1741–1745)

**Docstring в коде:** есть

```
Расход пользователя по нодам за период + идентификатор сработавшего пути API.
```

## `_panel_instance_key` (1763–1768)

**Docstring в коде:** есть

```
Идентификатор инстанса панели (base_url) для кэша поддержки путей.
```

## `reset_usage_path_cache` (1771–1774)

**Docstring в коде:** есть

```
Сбросить кэш решений о поддерживаемых путях (используется в тестах).
```

## `_usage_path_unsupported` (1777–1787)

**Docstring в коде:** нет

```
"""True, если путь помечен неподдерживаемым для инстанса и TTL 3600 с не истёк."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1778–1779 | пустой instance_key | False (не кэшируем) |
| 1784–1786 | TTL 3600 истёк | pop state, False |
| 1787 | path в unsupported | True |

## `_mark_usage_path_unsupported` (1790–1798)

**Docstring в коде:** нет

```
"""Пометить путь неподдерживаемым для инстанса панели (TTL 3600 с)."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1791–1792 | пустой instance_key | no-op |
| 1795–1797 | TTL истёк | сбросить set и ts |

## `_as_api_date` (1801–1805)

**Docstring в коде:** есть

```
Оба семейства эндпоинтов ждут дату в формате YYYY-MM-DD.
```

## `_to_int_bytes` (1808–1818)

**Docstring в коде:** нет

```
"""Привести значение к int байт; bool и нечисло — 0."""
```

## `resolve_panel_user_id` (1821–1852)

**Docstring в коде:** есть

```
Числовой `id` пользователя панели (нужен путям 3.3.2).

В 3.3.2 у пользователя вообще нет поля `uuid` (только `id` и `shortUuid`), поэтому
`vpn_keys.remnawave_user_uuid` там хранит уже числовой id — в этом случае берём его
напрямую, без лишнего запроса к панели (который к тому же может не отвечать).
В 2.8.1 хранится UUID, и числовой id приходится доставать из payload.

На 3.x `GET /api/users/{uuid}` отвечает 400 NaN. Тогда нужен `email` (или готовый
`user_payload` с полем `id`): lookup падает на by-username, как в остальных
3.x-путях. Без email числовой id не резолвится — это ошибка ЭТОГО ключа, а не
«панель не умеет squad-scoped».
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1841–1842 | stored.isdigit() | int сразу (3.x ключ уже хранит id) |
| 1844–1845 | нет payload | lookup (на 3.x нужен email) |
| 1847–1852 | поле id | int или None |

## `_sum_squad_scoped_days` (1855–1866)

**Docstring в коде:** есть

```
3.3.2: `{response: {days: [{date, nodes: [{uuid, totalBytes}]}]}}` -> сумма по нодам.
```

## `_sum_user_series` (1869–1888)

**Docstring в коде:** есть

```
2.8.1/3.3.2: `{response: {series|topNodes: [{uuid, total}]}}` -> расход по нодам.

`uuid` в series/topNodes — это UUID ноды; фильтруем по нодам LTE-сквада, т.к. эндпоинт
отдаёт расход пользователя по ВСЕМ нодам.
```

## `_sum_legacy_rows` (1891–1907)

**Docstring в коде:** есть

```
2.8.1 legacy: плоский список `{userUuid, nodeUuid, total, date}` -> расход по нодам.
```

## `get_user_node_usage_for_squad` (1910–2090)

**Docstring в коде:** есть

```
Расход пользователя по нодам LTE-сквада за период — с разбивкой по нодам.

Версионно-толерантная цепочка (подтверждена по контракту 2.8.1 и 3.3.2 / 3.4):

  1. `GET /api/bandwidth-stats/internal-squads/{squadUuid}/users/{userId}/usage`
     — 3.3.2+, числовой userId, ответ `days[].nodes[]{uuid,totalBytes}`, уже
     заскоупленный нодами сквада. В 2.8.1 секции INTERNAL_SQUADS нет -> 404.
  2. `GET /api/bandwidth-stats/users/{userId}` — 3.3.2+ (числовой id). 200,
     даже с пустым series, значит панель приняла числовой userId — это 3.x,
     UUID в этот путь не подставляем (400 NaN).
  3. `GET /api/bandwidth-stats/users/{userUuid}` — 2.8.1 (UUID): тот же
     маршрут, ответ `series[]/topNodes[]{uuid,total}` по всем нодам.
  4. `GET /api/bandwidth-stats/users/{userUuid}/legacy` — 2.8.1, плоские строки
     `{userUuid,nodeUuid,total,date}`. В 3.3.2 секции LEGACY нет -> 404.
  5. Исторический `get_user_lte_usage_bytes` — оставлен как последний кандидат без
     изменения его логики выбора пути. Разбивку он дать не может (только сумму), а
     оба его эндпоинта на 2.8.1/3.3.2 неприменимы (`/api/nodes/{uuid}/usage/range`
     отсутствует в обеих версиях, а у `POST /bandwidth-stats/nodes/users` другое тело
     и график вместо строк), поэтому его нулевой результат трактуется как «данных
     нет», а не как «расход нулевой».

`email` нужен, когда в ключе лежит UUID, а панель 3.x: без него числовой id
не резолвится. Нерезолвленный id — пропуск 3.x-путей для ЭТОГО ключа, кэш
«путь не поддерживается» при этом не трогаем (иначе один старый ключ глушит
squad-scoped на час для всей панели).

Ошибки: 404/400/422 -> путь/тип параметра не поддерживается версией, пробуем
следующего кандидата и запоминаем решение по инстансу панели. Сетевая ошибка или 5xx
-> строгий fail-safe: пробрасываем RemnawaveAPIError, чтобы вызывающий пропустил ключ
и НЕ записал нулевой расход. Если ни один путь не дал данных -> RemnawavePathUnsupportedError.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 1982–2008 | squad_scoped 3.3.2 | 200 → сумма days[].nodes; 404/400/422 → mark unsupported; нет numeric id — не травить кэш инстанса |
| 2012–2042 | users/{id} затем users/{uuid} | 3.x: 200 на числе, даже пустой series — стоп (UUID даст 400 NaN); 2.8.1 — series/topNodes |
| 2045–2058 | users/{uuid}/legacy | 2.8.1 плоские строки; 3.3.2 → 404 |
| 2063–2075 | get_user_lte_usage_bytes | если сумма > 0 — кладём на первую ноду; 0 — mark unsupported |
| 2077–2085 | answered_path и нуль | значимый нуль, не сбой |
| 2087–2090 | никто не ответил | RemnawavePathUnsupportedError |

## `get_user_node_usage_for_squad._numeric_id` (1970–1979)

**Docstring в коде:** нет

```
"""Лениво резолвить числовой panel_user_id через resolve_panel_user_id и запомнить в замыкании."""
```

## `get_squad_node_overlap` (2093–2105)

**Docstring в коде:** есть

```
Ноды, доступные одновременно через LTE- и base-сквад хоста.

Такое пересечение означает, что расход на этих нодах будет считаться в LTE-пул, хотя
они же отдаются базовым (безлимитным) сквадом. Исправить это можно только настройкой
inbound'ов сквадов на стороне Remnawave — код лишь обнаруживает и предупреждает.
```

## `refresh_host_squad_overlap` (2108–2127)

**Docstring в коде:** есть

```
Перепроверить пересечение сквадов хоста и сохранить результат для карточек.

Вызывается при сохранении сквадов хоста. Пересечение НЕ блокирует сохранение — это
предупреждение: устранить его можно только правкой inbound'ов сквадов в Remnawave.
```

## `extract_subscription_url` (2130–2133)

**Docstring в коде:** нет

```
"""Вернуть user_payload['subscriptionUrl'] или None."""
```

## `create_or_update_key_on_host` (2138–2271)

**Docstring в коде:** есть. Единственная точка выдачи ключа на панель (бот, WebApp, webhook, scheduler). По коду: `days==0` становится 1; продление от текущего expireAt, если оно в будущем.

```
Legacy совместимость: создаёт/обновляет пользователя Remnawave и возвращает данные по ключу.

Двухпуловая схема (host_squads): помимо базового `squad_uuid` хоста (legacy-поле на xui_hosts),
пользователь также добавляется в активный сквад класса 'lte' этого хоста (если он настроен),
когда это уместно — то есть когда `include_lte_squad=True` ЛИБО у переданного `plan_id` задан
`lte_limit_bytes > 0`. Если явной информации нет (plan_id не передан и include_lte_squad не задан),
поведение как раньше — только базовый сквад (без регрессии для старых вызовов).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 2178–2186 | include_lte_squad is None | False, либо True если plan.lte_limit_bytes > 0 |
| 2189–2197 | want_lte | extra_squad_uuids из активного LTE-сквада хоста |
| 2199–2225 | нет expiry_timestamp_ms | дни от expireAt панели, если оно в будущем, иначе now |
| 2263–2270 | ошибка | None, если не raise_on_error |

## `get_key_details_from_host` (2274–2299)

**Docstring в коде:** нет

```
"""Найти пользователя ключа на панели и вернуть connection_string, subscription_url, user."""
```

## `delete_client_on_host` (2302–2324)

**Docstring в коде:** нет

```
"""Найти пользователя по email на хосте и удалить через delete_user_on_host; нет на панели — True."""
```

---

Документировано: **86** функций/методов/вложенных (плюс 3 класса). Исходник `.py` не менялся.
