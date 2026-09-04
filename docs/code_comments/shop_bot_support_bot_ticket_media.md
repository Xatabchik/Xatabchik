# Комментарии: `src/shop_bot/support_bot/ticket_media.py`

Модульный docstring в коде:

```
Локальные вложения тикетов поддержки.

Файлы пишутся на диск рядом с БД и отдаются только панелью под login_required.
Наружу как static / Telegram file URL они не публикуются.

Лимит 10 МБ: заявленный file_size или getFile. Если размера нет — качаем
в память с потолком 10 МБ и проверяем после.

На тикет: не больше 10 файлов и 30 МБ суммарно. При удалении тикета
каталог ``ticket_files/<ticket_id>/`` снимается вместе со строками БД.

Тип файла определяется по magic bytes (jpeg/png/webp/pdf), не по имени
и не по MIME Telegram. GIF не принимаем. Панель отдаёт MIME и nosniff.

Вложения закрытого тикета хранятся ``TICKET_MEDIA_CLOSED_TTL_DAYS`` суток
(по ``updated_at`` закрытия), затем каталог удаляется. Строки тикета в БД
не трогаем.
```

Константы: `TICKET_MEDIA_MAX_BYTES` 10 МиБ, `MAX_FILES` 10, `MAX_TOTAL_BYTES` 30 МиБ, `EXTS` jpg/jpeg/png/webp/pdf, `CLOSED_TTL_DAYS` 7, `PURGE_INTERVAL_SECONDS` 3600. `_last_purge_monotonic` — троттлинг.

## `detect_image_kind_bytes` (41–53)

**Docstring в коде:** есть

```
Расширение и MIME по сигнатуре. None — не jpeg/png/webp/pdf.
```

Пустой head → None. jpeg `\xff\xd8\xff`, png 8 байт, webp RIFF+WEBP, pdf `%PDF-`.

## `detect_image_kind` (56–62)

**Docstring в коде:** нет

```
"""Прочитать 16 байт с path и отдать detect_image_kind_bytes; OSError → None."""
```

## `media_kind_from_stored` (65–76)

**Docstring в коде:** есть

```
image | pdf | file по имени на диске. Сырой путь наружу не отдаём.
```

Берёт basename (после `/` или `\`). Пусто или `..` в имени → None. `.pdf` → pdf; jpg/jpeg/png/webp → image; иначе file.

## `public_support_message` (79–90)

**Docstring в коде:** есть

```
Поля сообщения для панели/JSON без пути ticket_files.
```

`sender`, `content`, `message_id`, `created_at`, `has_media`, `media_kind`. Путь `media` не копируется.

## `positive_file_size` (93–103)

**Docstring в коде:** есть

```
Положительный размер в байтах или None, если Telegram его не дал.
```

None / не int / `<= 0` → None.

## `resolve_telegram_file_size` (106–131)

**Docstring в коде:** есть

```
Размер до download. Всегда getFile, если бот его умеет.

Возвращает (размер или None, объект для bot.download).
Download по File надёжнее, чем по голому file_id: локальный Bot API
отдаёт file_path, без него папка тикета создавалась пустой.
None — размер неизвестен; вызывающая сторона всё равно может качать
с потолком 10 МБ.
```

Нет `get_file` → `(declared, file_id)`. getFile упал → то же. Иначе размер из File, иначе declared; source = File или file_id.

## `_CappedSeekBuffer` (134–151)

**Docstring в коде:** есть

```
BytesIO с seek (его зовёт aiogram) и потолком, чтобы не держать 20 МБ в RAM.
```

### `_CappedSeekBuffer.__init__` (137–140)

**Docstring в коде:** нет

```
"""BytesIO + _max_bytes и overflow=False."""
```

### `_CappedSeekBuffer.write` (142–151)

**Docstring в коде:** нет

```
"""Писать чанк; при превышении потолка overflow=True и OverflowError. После overflow — только вернуть len, не писать."""
```

None → 0. Не bytes → `bytes(b)`.

## `download_ticket_media_capped` (154–193)

**Docstring в коде:** есть

```
Качаем в буфер с seek и потолком 10 МБ, затем на диск.

Путь + aiofiles раньше мог молча не создать файл; обычный BytesIO
держал бы весь ответ Telegram (~20 МБ) до проверки размера.
```

Есть `source.file_path` и `bot.download_file` — качает по path, иначе `bot.download`. overflow / пусто / OverflowError / Exception → False, `*.part` unlink. Успех: mkdir родителя, write part_path.

## `declared_size_over_limit` (196–210)

**Docstring в коде:** есть

```
True, если Telegram уже сообщил размер больше лимита.

None и 0 — размер неизвестен; тогда нужен getFile, не download.
```

None / не int → False. `size > max_bytes` → True. 0 не больше лимита.

## `ticket_folder_usage` (213–234)

**Docstring в коде:** есть

```
Число финальных файлов и их суммарный размер. ``*.part`` не считаем.
```

Нет dir / listdir OSError → (0, 0). Только файлы; getsize OSError — файл не считаем.

## `quota_blocks_new_file` (237–261)

**Docstring в коде:** есть

```
True, если ещё одно вложение превысит квоту тикета (10 файлов / 30 МБ).
```

`count >= max_files` или `total >= max_total`. Если `incoming_bytes` задан и `> 0` — ещё `total + incoming > max_total`. Не-int incoming → 0 (квоту по размеру не добавляет).

## `jailed_ticket_folder` (264–280)

**Docstring в коде:** есть

```
Каталог вложений тикета строго внутри media root, иначе None.
```

tid не int или `<= 0` → None. root default `get_ticket_media_root()`. `realpath(root/tid)` должен быть строго внутри `realpath(root)+sep`, не равен корню.

## `closed_ttl_days` (283–289)

**Docstring в коде:** нет

```
"""TTL суток из env TICKET_MEDIA_CLOSED_TTL_DAYS, clamp 1…3650; мусор → 7."""
```

## `parse_ticket_updated_at` (292–305)

**Docstring в коде:** нет

```
"""datetime без tzinfo или parse первых 19 символов `%Y-%m-%d %H:%M:%S` / `T`; иначе None."""
```

## `closed_ticket_media_expired` (308–322)

**Docstring в коде:** есть

```
True, если тикет закрыт дольше TTL — файлы пора снять.
```

Нет ticket / status ≠ `closed` / нет `updated_at` → False. Порог: `updated <= now - timedelta(days)`. now default `utcnow()`.

## `ticket_media_on_disk` (325–337)

**Docstring в коде:** есть

```
True, если в ticket_files есть хоть одна запись. Без SQL и без полного обхода.
```

`os.scandir` + `next(it, None)`: есть любой child (файл или папка).

## `expire_ticket_media_if_closed_ttl` (340–349)

**Docstring в коде:** есть

```
Если тикет закрыт дольше TTL — удаляет файлы и обнуляет media. True = истекло.
```

`get_ticket` → `closed_ticket_media_expired` → `delete_ticket_media_dir` + `clear_support_message_media`. Строки тикета не удаляет.

## `purge_expired_closed_ticket_media` (352–418)

**Docstring в коде:** есть

```
Снимает каталоги закрытых тикетов старше TTL и осиротевшие папки.
```

Нет файлов на диске → `{purged:0, orphans:0}`. Сначала `list_closed_ticket_ids_older_than(cutoff)`: delete dir + clear media. Потом listdir корня: только имена из цифр, не в seen; нет тикета и mtime папки старше TTL → orphan delete (без SQL media); тикет закрыт по TTL → purge. Лог если purged или orphans.

## `maybe_purge_expired_closed_ticket_media` (421–434)

**Docstring в коде:** есть

```
Не чаще раза в час. Нет файлов — сразу выход, таймер не заводим.
```

Нет диска → None, `_last_purge_monotonic` не двигаем. Интервал от monotonic. Exception purge → None.

## `delete_ticket_media_dir` (437–447)

**Docstring в коде:** есть

```
Удаляет ``ticket_files/<ticket_id>/``. Не трогает соседние тикеты и корень.
```

jail None → False. Нет dir → True. `rmtree(ignore_errors=True)`; True если папки больше нет.

## `commit_ticket_image` (450–484)

**Docstring в коде:** есть

```
Размер + magic. Возвращает ``stem.ext`` или None; ``*.part`` удаляется при отказе.
```

Нет файла / size 0 или > 10 МиБ / не jpeg/png/webp/pdf → unlink part, None. Иначе `os.replace` в `stem.ext`.

## `remove_empty_ticket_folder` (487–493)

**Docstring в коде:** есть

```
Снимает пустой ``ticket_files/<id>/`` после неудачного save.
```

`rmdir` только если listdir пуст. OSError глотает.

## `_unlink_quiet` (496–502)

**Docstring в коде:** нет

```
"""os.unlink каждого существующего файла; OSError и пустой path игнор."""
```

## `document_may_be_ticket_media` (505–513)

**Docstring в коде:** есть

```
Документ можно скачать: картинка или PDF. Тип всё равно подтвердит magic.
```

`image/*`, `application/pdf` / `x-pdf`, или имя на `.jpg/.jpeg/.png/.webp/.pdf`.

## `save_ticket_media_bytes` (516–563)

**Docstring в коде:** есть

```
Сохраняет вложение из WebApp (байты), те же jail/квота/magic, что у бота.

Возвращает ``<ticket_id>/<uuid>.ext`` или None.
```

Пусто / > 10 МиБ / плохой magic / плохой id / нет jail / квота → None. Пишет `.part`, `commit_ticket_image`, повторная проверка квоты (лишний файл снимает). Успех: `maybe_purge`, путь `tid/name`. finally: `remove_empty_ticket_folder`.

## `save_ticket_media` (566–641)

**Docstring в коде:** есть

```
Сохраняет изображение из сообщения. Контракт как у прежнего хелпера.

Возвращает относительный путь ``<ticket_id>/<uuid>.ext`` или None.
Текст сообщения вызывающая сторона сохраняет сама — отказ по размеру
не ломает обращение.
```

Фото: последнее size, отказ если declared over limit. Иначе document, если `document_may_be_ticket_media`. Нет file_id → None. getFile size, jail, квота, capped download, commit, квота после записи. `maybe_purge` при успехе. finally: пустую папку снимает только если `not saved`.
