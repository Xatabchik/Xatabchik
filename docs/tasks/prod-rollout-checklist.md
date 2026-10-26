# Чек-листы выката на прод

Выполняются владельцем: у агента нет доступа к проду. Каждый шаг начинается с резервной
копии. `$APP` каталог проекта на проде (на стенде `/root/xatabchik`).

## PR-0: проверка владельца, хоста и тарифа в /api/create-payment (PR #174)

Порядок:

1. Резервная копия БД (не `cp` при работающей записи):
   `sqlite3 $APP/users.db ".backup /root/backups/users.db.pre-pr0-$(date +%Y%m%d-%H%M%S)"`
   и `sqlite3 <копия> "PRAGMA integrity_check;"` должен вернуть `ok`.
2. Запомнить текущий коммит: `cd $APP && git rev-parse HEAD > /root/backups/pr0-prev-commit`.
3. Аудит до выката (только чтение): список хостов с `is_active = 0`
   `SELECT host_name, is_active FROM xui_hosts WHERE COALESCE(is_active,1)=0;`
   PR-0 флаг `is_active` не проверяет, результат нужен только для сведения.
4. Получить код: `git fetch origin && git checkout <ветка/тег с PR #174>` (или merge в main и `git pull`).
5. Применить: `docker compose up -d --no-build xatabchik-webapp && docker restart xatabchik`
   (код подключён bind-mount `.:/app/project`, пересборка образа не нужна).
6. Подождать 10-15 секунд, `docker ps` оба контейнера `Up`.

Проверки после выката:

- `docker logs --since 5m xatabchik-webapp | grep -i traceback` пусто, то же для `xatabchik`.
- Mini App открывается, список ключей и тарифов виден.
- Покупка нового ключа и продление своего ключа на небольшом тарифе проходят (или
  оплата с баланса тестового пользователя).
- Продление чужого `key_id` возвращает `Ключ не найден` (вызов `/api/create-payment` с
  токеном обычного пользователя и `action=extend` для ключа другого пользователя).
- В логах бота после оплат нет новых строк `extend: host_name в metadata не совпадает`
  (такие предупреждения означают платежи, созданные до выката).
- Число пользователей, ключей и транзакций в БД совпадает с ожидаемым (`SELECT COUNT(*)`).

Откат:

```
cd $APP && git checkout $(cat /root/backups/pr0-prev-commit) \
  && docker compose up -d --no-build xatabchik-webapp && docker restart xatabchik
```

БД PR-0 не меняет, восстановление из копии не требуется.

## PR-IP: адрес клиента за nginx и docker-прокси (PR #176)

Порядок (nginx строго до приложения, иначе заголовок остаётся подделываемым):

1. Копия БД как выше и копии конфигов nginx:
   `cp -a /etc/nginx/sites-available/<файл> /root/backups/<файл>.pre-prip-$(date +%Y%m%d-%H%M%S)`.
2. В `location`, проксирующих в приложение (webapp на 127.0.0.1:8001, панель на 127.0.0.1:1488):
   `proxy_set_header X-Real-IP $remote_addr;` и `proxy_set_header X-Forwarded-For $remote_addr;`
   (вместо `$proxy_add_x_forwarded_for`). Проверить: `nginx -t && systemctl reload nginx`.
3. На проде перед nginx стоит CDN (Cloudflare), поэтому этот шаг обязателен и выполняется ДО п. 2
   или вместе с ним. Без него `$remote_addr` будет адресом узла Cloudflare, и все клиенты снова
   сольются в один адрес (лимиты slowapi, лимит входа в панель):
   ```
   # /etc/nginx/conf.d/cloudflare-realip.conf (список взять с https://www.cloudflare.com/ips-v4 и /ips-v6)
   set_real_ip_from 173.245.48.0/20;
   # ... остальные диапазоны Cloudflare ...
   real_ip_header CF-Connecting-IP;
   real_ip_recursive off;
   ```
   `set_real_ip_from` должен содержать только диапазоны CDN: заголовку `CF-Connecting-IP` от остальных
   адресов nginx не верит. После `nginx -t && systemctl reload nginx` проверить по access-логу, что в
   поле адреса стоят реальные адреса клиентов, а не диапазоны Cloudflare. Если используется другой
   CDN или балансировщик, нужны его диапазоны и его заголовок (`X-Forwarded-For` с
   `real_ip_recursive on`). Периодически обновлять список диапазонов.
4. Получить код PR #176 и применить: `docker compose up -d --no-build xatabchik-webapp && docker restart xatabchik`
   (команда запуска webapp изменена, поэтому контейнер именно пересоздаётся).
5. Порты 8000/8001/1488 должны быть опубликованы только на 127.0.0.1
   (`ss -ltn | grep -E ':(8000|8001|1488) '`), снаружи недоступны. Не использовать `*`.
6. Сузить доверенные прокси webapp до подсети compose-сети проекта. Узнать подсеть:
   `docker network inspect <проект>_default --format '{{(index .IPAM.Config 0).Subnet}}'`
   (например `172.19.0.0/16`; peer, который видит uvicorn, это шлюз этой сети). Записать в `.env`
   рядом с `docker-compose.yml`:
   `WEBAPP_FORWARDED_ALLOW_IPS=127.0.0.1,::1,172.19.0.0/16`
   и пересоздать webapp (`docker compose up -d --no-build xatabchik-webapp`). Значение по умолчанию
   (все частные диапазоны) допустимо, но уже это сужение уменьшает число адресов, которым верит uvicorn.
   Если подсеть пересоздаётся при `docker compose down`, перепроверить значение после пересоздания сети.
   Для панели (Flask) то же через `SHOPBOT_TRUSTED_PROXIES` в окружении контейнера `xatabchik`.

Проверки после выката:

- С двух разных внешних адресов 31 запрос к одному и тому же пути с лимитом
  (например `/api/auth/check-token/x`): первый адрес получает 429 после 30-го,
  второй адрес в это время получает 200. Для роутов с параметром пути (`/api/auth/check-token/{token}`) корзина общая на IP только после PR #178: до него разные значения параметра обходили лимит.
- Запрос с `-H "X-Forwarded-For: 1.2.3.4"` не даёт нового лимита: ограничение остаётся
  по реальному адресу.
- Вход в панель: 5 неудачных попыток подряд с одного адреса дают 429, с другого адреса вход доступен.
- Если используется allowlist TON-вебхука (переменная окружения `SHOPBOT_TON_WEBHOOK_IP_ALLOWLIST`), он сверяется с реальным
  адресом отправителя; убедиться, что он совпадает с адресом, указанным в списке.

Откат:

```
cp -a /root/backups/<файл>.pre-prip-<метка> /etc/nginx/sites-available/<файл> && nginx -t && systemctl reload nginx
cd $APP && git checkout $(cat /root/backups/pr0-prev-commit)   # или коммит до PR-IP
docker compose up -d --no-build xatabchik-webapp && docker restart xatabchik
```

БД PR-IP не меняет. Переменные окружения: `WEBAPP_FORWARDED_ALLOW_IPS` (webapp, через compose)
и `SHOPBOT_TRUSTED_PROXIES` (панель Flask) позволяют сузить список доверенных прокси.

## PR-A: замок записи ключа, идемпотентное продление, журнал автопродления, сверка (PR #180)

Только после того, как PR-0 и PR-IP стоят на проде. PR-B не начинается без отдельного подтверждения владельца.

Новые режимы выключены по умолчанию, поэтому сам выкат кода поведение не меняет. Таблицы
`key_write_locks`, `key_extension_applied`, `ops_alerts`, `auto_renew_charges`, `auto_renew_attempts`
создаются при старте.

Порядок:

1. Копия БД как выше (`.backup` и `integrity_check`) и `git rev-parse HEAD > /root/backups/pra-prev-commit`.
2. Получить код PR #180 и пересоздать оба контейнера: `docker compose up -d --no-build`
   (в `docker-compose.yml` добавлен `stop_grace_period: 40s`, он применяется только при пересоздании,
   а не при `docker restart`). Проверить: `docker inspect -f '{{.Config.StopTimeout}}' xatabchik xatabchik-webapp` даёт `40`.
3. Подождать 30 секунд, оба контейнера `Up`, в логах нет `Traceback`. В логе бота при старте нет
   предупреждения о режиме журнала SQLite (нужен `wal`: `sqlite3 $APP/users.db "PRAGMA journal_mode;"`).
4. Проверить остановку: `docker stop xatabchik` завершается с кодом 0 (`docker inspect -f '{{.State.ExitCode}}' xatabchik`), затем `docker start xatabchik`.

Включение режимов (значения читаются при каждом вызове, перезапуск не нужен). Меняются в `bot_settings`:

```
sqlite3 $APP/users.db "UPDATE bot_settings SET value='payments' WHERE key IN ('key_write_lock_scope','key_extension_delta_scope');"
```

- `key_write_lock_scope=payments` и `key_extension_delta_scope=payments` включаются ВМЕСТЕ одной командой.
  На стенде один замок без дельты не помогает: два параллельных продления по 30 дней дают +30 вместо +60
  (оба платежа пишут одну и ту же абсолютную дату). Только замок и дельта вместе дают +60, а повторная доставка
  того же `payment_id` ничего не добавляет. Не включать замок отдельно.
- `key_write_lock_scope=all` (замок также для админских операций «добавить дни» и вызовов без `payment_id`)
  включать позже, отдельным шагом, после наблюдения за режимом `payments`.
- `payment_reconciler_mode` остаётся `alert` (только оповещения админам). Режим `retry` включать ТОЛЬКО после
  п. 3 списка вопросов к владельцу в отчёте этапа 2: сверка платежей с баланса (см. `balance-payments-reconciliation.md`).
  Сейчас сверка не видит такие платежи, а автоповтор `new` без этого пункта оставляет их без защиты.
- Автопродление (`auto_renew_globally_enabled`) работает через новый журнал сразу после выката: после выката проверить, что
  первая попытка прошла (`SELECT state, COUNT(*) FROM auto_renew_charges GROUP BY state;`, записи `charged` старше 15 минут
  означают неоконченное продление, их закроет сверка).

Проверки после включения:

- `SELECT state, COUNT(*) FROM key_extension_applied GROUP BY state;` записи `started` старше 10 минут единичны (неоднозначные
  таймауты панели, их закрывает следующее продление или сверка); `done` растёт с каждым продлением.
- `SELECT COUNT(*) FROM key_write_locks;` стремится к 0 между платежами.
- `docker logs --since 1h xatabchik | grep KEY_WRITE_LOCK_TIMEOUT` пусто. Каждое такое событие значит, что запись шла без замка
  дольше 360 секунд, и дублируется в `ops_alerts` и админу.
- Два одновременных продления одного ключа дают ровно два периода (на тестовом ключе).

Откат без перезапуска: `UPDATE bot_settings SET value='off' WHERE key IN ('key_write_lock_scope','key_extension_delta_scope');`
и при необходимости `payment_reconciler_mode='off'`. Таблицы остаются и ничему не мешают.
Откат кода: `git checkout $(cat /root/backups/pra-prev-commit) && docker compose up -d --no-build`.
