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
3. Если перед nginx стоит CDN/балансировщик (Cloudflare и т. п.), сначала настроить
   `set_real_ip_from <диапазоны CDN>;` и `real_ip_header CF-Connecting-IP;` (или `X-Forwarded-For`),
   иначе `$remote_addr` будет адресом CDN и все клиенты снова сольются в один.
4. Получить код PR #176 и применить: `docker compose up -d --no-build xatabchik-webapp && docker restart xatabchik`
   (команда запуска webapp изменена, поэтому контейнер именно пересоздаётся).
5. Порты 8000/8001/1488 должны быть опубликованы только на 127.0.0.1
   (`ss -ltn | grep -E ':(8000|8001|1488) '`), снаружи недоступны. Если порт когда-либо
   открывается наружу, не оставлять `--forwarded-allow-ips` с диапазонами, которым
   доступен посторонний клиент, и не использовать `*`.

Проверки после выката:

- С двух разных внешних адресов 31 запрос к одному и тому же пути с лимитом
  (например `/api/auth/check-token/x`): первый адрес получает 429 после 30-го,
  второй адрес в это время получает 200. (Лимит slowapi считается по пути вместе с параметрами.)
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
