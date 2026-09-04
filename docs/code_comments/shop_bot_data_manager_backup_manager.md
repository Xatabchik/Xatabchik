# Комментарии: `src/shop_bot/data_manager/backup_manager.py`

Создание ZIP-бэкапа SQLite, рассылка админам, валидация и восстановление. Модульного docstring нет. Вызовы: планировщик (`_maybe_run_daily_backup`), админ-бот, панель `/admin/db/backup` и `/admin/db/restore`.

| Имя | Значение | Зачем |
|-----|----------|--------|
| `BACKUPS_DIR` | `Path("/app/project/backups")` | каталог архивов; `mkdir` при импорте |
| `DB_FILE` | `rw_repo.DB_FILE` | актуальный путь к БД через PEP 562 |

## `_timestamp` (25–26)

**Docstring в коде:** нет

```
"""Вернуть метку локального now() в формате YYYYMMDD-HHMMSS."""
```

## `create_backup_file` (29–61)

**Docstring в коде:** есть

```
Создаёт zip-архив с консистентной копией SQLite-БД.
Возвращает путь к архиву или None при ошибке.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 35–37 | нет DB_FILE | error, None |
| 43–45 | sqlite3.backup | консистентная копия в `users-{ts}.db` |
| 48–49 | ZipFile DEFLATED | архив `db-backup-{ts}.zip` |
| 52–55 | unlink tmp | ошибка удаления игнорируется |
| 59–61 | except | None |

## `cleanup_old_backups` (64–74)

**Docstring в коде:** есть

```
Хранить только N последних архивов, остальные удалять.
```

Сортировка `db-backup-*.zip` по `st_mtime` убыв.; удаляет хвост после `keep` (по умолчанию 7). Ошибка unlink одного файла глотается; ошибка glob — warning.

## `send_backup_to_admins` (77–135)

**Docstring в коде:** есть

```
Отправляет архив всем администраторам. Возвращает число успешных отправок.

Загрузка большого файла может занимать больше времени, чем стандартный
таймаут HTTP-клиента aiogram, поэтому здесь используется увеличенный
request_timeout и несколько попыток с задержкой при сетевых сбоях.
```

Побочный эффект: Telegram `send_document`. `get_admin_ids()` падает → пустой список → 0.

| Строки | Блок | Зачем |
|--------|------|--------|
| 97–107 | успех | cnt+=1, break |
| 109–115 | TelegramRetryAfter | sleep `retry_after` или 5 |
| 116–123 | сеть/Timeout | sleep `3 * attempt`, повтор |
| 124–127 | прочий Exception | лог, без повтора |
| 128–131 | last_error после цикла | лог исчерпания попыток |

## `validate_db_file` (139–159)

**Docstring в коде:** есть

```
Простая валидация файла БД: доступность основных таблиц.
```

True только если в `sqlite_master` есть и `users`, и `bot_settings`. Отсутствие `vpn_keys` / `transactions` / `xui_hosts` пишется в warning, но не валит результат.

## `restore_from_file` (162–225)

**Docstring в коде:** есть

```
Восстанавливает основную БД из переданного файла .db или .zip (внутри .db).
Делает резервную копию текущей БД на случай отката.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 168–170 | нет файла | False |
| 177–187 | suffix `.zip` | первый `*.db` из архива; ошибка unpack → False |
| 188–190 | иначе | сам uploaded_path как кандидат |
| 197–199 | validate_db_file | False без замены |
| 202–208 | create_backup_file + copy | `before-restore-{ts}.zip`; ошибка copy игнорируется |
| 211–213 | sqlite3.backup | candidate → `DB_FILE` |
| 216–219 | run_migration | ошибка игнорируется |
