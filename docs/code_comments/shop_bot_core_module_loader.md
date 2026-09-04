# Комментарии: `src/shop_bot/core/module_loader.py`

Загрузчик плагинов: discover / enable / ZIP. Модульного docstring нет. Существующие docstring — английские.

## Константы и `#` (CWE / zip)

В коде `#` (26): Limits for ZIP module imports (CWE-22 / zip-bomb / unexpected payloads).

| Строки | Имя | Зачем |
|--------|-----|--------|
| 27 | `MAX_MODULE_ZIP_BYTES` | 10 MiB compressed (`#` в коде) |
| 28 | `MAX_MODULE_ZIP_UNCOMPRESSED_BYTES` | 40 MiB total uncompressed (`#` в коде) |
| 29 | `MAX_MODULE_ZIP_FILES` | 200 записей |
| 30 | `_MODULE_ID_RE` | `^[a-z0-9_]+$` — имя корня ZIP и id модуля |
| 31–53 | `_ALLOWED_MODULE_EXTENSIONS` | исходники/манифест/ассеты; не скрипты/бинари |
| 54–64 | `_ALLOWED_EXTENSIONLESS_NAMES` | license, readme, changelog, notice, copying, authors, contributors |

## `_LoadedModule` (68–77)

**Docstring в коде:** нет

```
"""In-memory import: meta, path, module_obj, optional router/blueprint/cleanup, settings_schema, schema_sql, module_names."""
```

## `ModuleLoader` (80–904)

**Docstring в коде:** есть

```
Discovers, loads, and manages plugin modules.
```

### `ModuleLoader.__init__` (83–92)

**Docstring в коде:** нет

```
"""Set modules_path (default repo `modules/`) and db_file; empty discovery/load caches and `_enabled_cache`."""
```

`modules_path` default: `Path(__file__).resolve().parents[3] / "modules"`. `db_file` default: `database.DB_FILE`.

### `ModuleLoader.set_dispatcher` (94–97)

**Docstring в коде:** есть

```
Attach aiogram dispatcher for module router registration.
```

Затем `_activate_enabled_modules()`.

### `ModuleLoader.set_flask_app` (99–102)

**Docstring в коде:** есть

```
Attach Flask app for module blueprint registration.
```

Затем `_activate_enabled_modules()`.

### `ModuleLoader.discover_modules` (104–131)

**Docstring в коде:** есть

```
Discover module manifests under the modules directory.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 106–107 | уже `_discovered` | копия `_modules` без повторного скана |
| 109–111 | нет каталога | info, `{}` |
| 113–130 | sorted dirs с `__init__.py` | `_load_manifest`; ошибка / invalid meta → `_set_status` ERROR; иначе cache + `_upsert_registry` |

Возвращает `dict(self._modules)`.

### `ModuleLoader.list_modules` (133–177)

**Docstring в коде:** есть

```
Return a list of modules with status for UI usage.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 138–156 | известные id | ModuleInfo из registry; битый status → ERROR; `has_settings=bool(meta.settings_schema)` |
| 157–175 | строки registry без файлов | ModuleInfo ERROR, description «Module files not found» |
| 176–177 | sort по id | `[m.to_dict() for m in modules]` |

### `ModuleLoader.get_module_status` (179–188)

**Docstring в коде:** есть

```
Return current status for a module.
```

Нет строки registry → `MISSING`. Битый status → `ERROR`. Пустой status → `DISABLED`.

### `ModuleLoader.load_module` (190–226)

**Docstring в коде:** есть

```
Import module code and prepare its hooks.
```

Уже в `_loaded` → тот же объект. Нет meta/path → None. Импорт `__init__.py` как `xatabchik_module_{id}`, затем router/blueprint/schema/cleanup/settings. Исключение → лог, `set_module_error`, None.

### `ModuleLoader.unload_module` (228–241)

**Docstring в коде:** есть

```
Unload module hooks and imported code.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 230–232 | нет в `_loaded` | return |
| 234–235 | router | `_detach_router` |
| 236–237 | blueprint | по коду: `_unregister_blueprint(self._flask_app, loaded.blueprint.name)` при сигнатуре только `(module_id)` |
| 238–239 | except | warning |
| 240–241 | `sys.modules.pop` | все `module_names` |

### `ModuleLoader.enable_module` (243–271)

**Docstring в коде:** есть. В коде `#`: Enable module buttons.

```
Enable a module and register its hooks.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 246–248 | нет meta | `(False, "Module not found")` |
| 249–252 | requires не ENABLED | `(False, "Dependency not enabled: …")` |
| 253–255 | load failed | `(False, "Module load failed")` |
| 256–259 | schema_sql | `_apply_schema`; fail → тот error |
| 260–261 | settings_schema | `_ensure_settings_defaults` |
| 262–265 | dispatcher/flask | attach router / register blueprint |
| 267 | buttons | `_set_module_buttons_active(True)` |
| 268–269 | not from_startup | `_set_status(ENABLED)` |
| 270–271 | cache | add, `(True, "Module enabled")` |

`from_startup=True` не пишет status (уже enabled в БД).

### `ModuleLoader.disable_module` (273–284)

**Docstring в коде:** есть. В коде `#`: Disable module buttons.

```
Disable a module without deleting its data.
```

Detach router если loaded; `_unregister_blueprint(module_id)` если есть flask+blueprint; buttons False; discard cache; `_set_status(DISABLED)`. Всегда `(True, "Module disabled")`. Объект в `_loaded` остаётся.

### `ModuleLoader.delete_module` (286–305)

**Docstring в коде:** есть

```
Delete a module and remove its data.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 288–290 | dependents | `(False, "Dependent modules: …")` |
| 292–298 | `loaded.cleanup` | `cleanup(conn)`; fail → `set_module_error`, `(False, "Cleanup failed")` |
| 299–300 | иначе | `_delete_settings_prefix` (при cleanup prefix сам не чистится) |
| 301–305 | disable, unload, delete registry, rmtree | `(True, "Module deleted")` |

### `ModuleLoader.get_menu_items` (307–317)

**Docstring в коде:** есть

```
Collect panel menu items from enabled modules.
```

Только ENABLED; элемент — dict с непустыми `label` и `url`.

### `ModuleLoader.get_settings_schema` (319–328)

**Docstring в коде:** есть

```
Return module settings schema if available.
```

Нет meta/`settings_schema` или load failed → `[]`. Иначе `list(loaded.settings_schema)`.

### `ModuleLoader.get_settings_values` (330–345)

**Docstring в коде:** есть

```
Return current values for module settings.
```

Ключи `{module_id}_{item.key}`; нет строки bot_settings → value None.

### `ModuleLoader.set_module_error` (347–349)

**Docstring в коде:** есть

```
Mark module as failed with error message.
```

`_set_status(ERROR, message)`.

### `ModuleLoader._activate_enabled_modules` (351–364)

**Docstring в коде:** нет. В коде `#`: disabled → inactive buttons.

```
"""If dispatcher or Flask is attached, enable registry rows with status enabled that are not in `_enabled_cache`."""
```

Нет ни dispatcher, ни flask → return. Не-ENABLED: только buttons False. Успешный `enable_module(..., from_startup=True)` → add в cache.

### `ModuleLoader._load_manifest` (366–373)

**Docstring в коде:** нет

```
"""Import `__init__.py` as `xatabchik_manifest_{folder}` and return MODULE_META (ModuleMeta or dict). Missing → ValueError."""
```

### `ModuleLoader._validate_module_meta` (375–385)

**Docstring в коде:** нет

```
"""True if id matches `^[a-z0-9_]+$`, equals folder_name, and name/version are non-empty."""
```

### `ModuleLoader._import_from_path` (387–394)

**Docstring в коде:** нет

```
"""importlib spec_from_file_location + exec_module; register in sys.modules. No loader → ImportError."""
```

### `ModuleLoader._load_router` (396–409)

**Docstring в коде:** нет

```
"""Import `{bot_entry}.py`, require `router` is aiogram.Router, attach ModuleSafeMiddleware to message and callback_query. No bot_entry → None."""
```

Нет файла → FileNotFoundError. Не Router → TypeError.

### `ModuleLoader._load_blueprint` (411–422)

**Docstring в коде:** нет

```
"""Import `{panel_entry}.py` and require `bp` is flask.Blueprint. No panel_entry → None."""
```

Нет файла → FileNotFoundError. Не Blueprint → TypeError.

### `ModuleLoader._load_schema_sql` (424–444)

**Docstring в коде:** нет

```
"""Import `{db_schema}.py`, read SCHEMA_SQL or schema_sql (call if callable), normalize to statements, `_validate_schema`."""
```

str → один statement; list/tuple → непустые str; иначе ValueError. Нет `db_schema` → `[]`.

### `ModuleLoader._load_cleanup` (446–457)

**Docstring в коде:** нет

```
"""Import `{db_cleanup}.py` and return callable `cleanup`. No db_cleanup → None; not callable → TypeError."""
```

### `ModuleLoader._load_settings_schema` (459–470)

**Docstring в коде:** нет

```
"""Import `{settings_schema}.py` and return SETTINGS (must be a list). No settings_schema → []."""
```

### `ModuleLoader._validate_schema` (472–478)

**Docstring в коде:** нет

```
"""Raise ValueError if any CREATE TABLE name is not prefixed with `{module_id}_`."""
```

Regex: `CREATE TABLE [IF NOT EXISTS] name`. Имя без `` ` " [] ``.

### `ModuleLoader._apply_schema` (480–489)

**Docstring в коде:** нет

```
"""executescript each statement; on failure set_module_error and return (False, str(exc))."""
```

### `ModuleLoader._ensure_settings_defaults` (491–512)

**Docstring в коде:** нет

```
"""INSERT OR REPLACE missing bot_settings `{module_id}_{key}`: bool→true/false, dict/list→JSON, None→\"\"."""
```

Пропускает item без `key`. Существующая строка не перезаписывается.

### `ModuleLoader._delete_settings_prefix` (514–517)

**Docstring в коде:** нет

```
"""DELETE FROM bot_settings WHERE key LIKE `{module_id}_%`."""
```

### `ModuleLoader._attach_router` (519–538)

**Docstring в коде:** нет. В коде `#`: Check if router is already attached.

```
"""include_router unless router is already in dispatcher.sub_routers; swallow RuntimeError containing 'already attached'."""
```

Нет dispatcher → return. Ошибка чтения sub_routers — warning, попытка include всё равно.

### `ModuleLoader._detach_router` (540–552)

**Docstring в коде:** есть. В коде `#`: Reset parent_router using private attribute to avoid setter validation.

```
Detach router from dispatcher.
```

Нет в `sub_routers` → return. `remove`; если есть `_parent_router` — `None`. Исключение — warning.

### `ModuleLoader._register_blueprint` (554–598)

**Docstring в коде:** есть

```
Store blueprint routes in a registry for dynamic dispatch.

This allows module routes to be added after the app has started.
Routes are handled by a special proxy endpoint.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 560–561 | нет flask | return |
| 563–565 | `#` Store reference | `_module_route_registry` на app |
| 567–581 | `#` template folder | ChoiceLoader + FileSystemLoader модуля |
| 583–598 | `#` temp Flask | register_blueprint на temp_app; вытащить view_functions после `.`; записать в registry[module_id] |

На боевой app blueprint не регистрируется.

### `ModuleLoader._unregister_blueprint` (600–606)

**Docstring в коде:** есть. В коде `#`: Remove the blueprint for this module.

```
Remove registered blueprint routes from the registry.
```

`pop(module_id)` из `_module_route_registry`. Нет app/registry → return.

### `ModuleLoader._get_dependents` (608–613)

**Docstring в коде:** нет

```
"""Return ids of discovered modules that list module_id in requires."""
```

### `ModuleLoader._delete_module_files` (615–622)

**Docstring в коде:** нет

```
"""shutil.rmtree the module directory if it exists; log warning on failure."""
```

Нет path / не exists → return.

### `ModuleLoader._normalize_zip_member_name` (625–641)

**Docstring в коде:** есть

```
Normalize a ZIP member path; return None if the name is unsafe.
```

| Строки | Блок | `#` / зачем |
|--------|------|-------------|
| 627–628 | пустое имя или `\\x00` | None |
| 629–631 | `\\` или `C:` | `#` ZIP uses forward slashes; reject Windows separators / drive letters |
| 632–633 | начинается с `/` или `//` | None (абсолютный путь) |
| 634–638 | split, drop `""`/`.`; любой `..` | `#` Collapse duplicate slashes but keep trailing slash for directories |
| 639–641 | trailing `/` | directory form `a/b/`; пустые parts → None |

### `ModuleLoader._is_allowed_module_member` (644–657)

**Docstring в коде:** есть

```
Allow only module source/manifest/assets; reject scripts and binaries.
```

| Строки | Блок | `#` / зачем |
|--------|------|-------------|
| 646–647 | пусто или directory (`/`) | True |
| 649–650 | имя `.` / `..` | False |
| 651–653 | hidden кроме `.gitignore` | `#` Hidden / macOS junk often appears in archives; reject for safety |
| 655–657 | нет suffix | только `_ALLOWED_EXTENSIONLESS_NAMES`; иначе suffix ∈ `_ALLOWED_MODULE_EXTENSIONS` |

### `ModuleLoader._resolve_extract_path` (659–675)

**Docstring в коде:** есть

```
Resolve extract destination and ensure it stays under target_root (zip-slip).
```

| Строки | Блок | `#` / зачем |
|--------|------|-------------|
| 661–662 | пусто / directory | None (файлы пишет caller) |
| 663–665 | `/` или `..` в parts | `#` Refuse absolute / parent segments again at join time |
| 666–670 | `dest.resolve()` vs `root.resolve()` | `is_relative_to`; иначе None (zip-slip) |
| 671–674 | AttributeError | `#` Python < 3.9 fallback (not expected on 3.11, kept for safety) — `os.path.commonpath` |

### `ModuleLoader.import_module_from_zip` (677–824)

**Docstring в коде:** есть

```
Import a module from a ZIP file.

Expects ZIP with structure:
    module_name/
        __init__.py
        bot_handlers.py
        ...

Hardened against zip-slip (CWE-22), zip bombs, and unexpected payloads.
```

| Строки | Блок | `#` / зачем |
|--------|------|-------------|
| 690–703 | нет файла / не `.zip` / size≤0 / > MAX_MODULE_ZIP_BYTES | False + сообщение |
| 706–711 | empty / слишком много entries | False |
| 713–720 | сумма `file_size` | zip-bomb: > MAX_MODULE_ZIP_UNCOMPRESSED_BYTES; отрицательный size — reject |
| 721–728 | `#` Reject symlink / special entries | `info.is_symlink()` или `external_attr` mode `0o120000` |
| 729–735 | `#` Large highly-compressible members are a zip-bomb signal | file_size > 1_000_000 и ratio > 100× |
| 736–738 | normalize | unsafe path → False |
| 741–751 | `#` Determine module root from first non-empty normalized path | id по `_MODULE_ID_RE`; обязателен `{name}/__init__.py` |
| 753–759 | `#` All members must live under module_name/ | чужой корень / disallowed type |
| 761–763 | target exists | не перезаписывать |
| 768–796 | extract | dir: probe `_resolve_extract_path(.../__dir__)`; file: resolve + chunk 64KiB; remaining≠0 → truncated |
| 775–778 | `#` Validate directory stays under target via a child sentinel path | zip-slip на mkdir |
| 799–806 | BadZipFile / Exception | rmtree target, False |
| 808–815 | `#` Discover the new module | `_discovered=False`; нет в `_modules` → rmtree, validation fail |
| 817–824 | auto_enable | enable fail → False «extracted but enable failed»; иначе success |

### `ModuleLoader._upsert_registry` (826–841)

**Docstring в коде:** нет

```
"""Insert a DISABLED registry row if missing; else UPDATE name, version, metadata only."""
```

Status не меняется при повторном discover.

### `ModuleLoader._insert_registry` (843–854)

**Docstring в коде:** нет

```
"""INSERT OR IGNORE modules_registry as disabled with JSON metadata."""
```

### `ModuleLoader._delete_registry` (856–859)

**Docstring в коде:** нет

```
"""DELETE the modules_registry row for module_id."""
```

### `ModuleLoader._set_status` (861–872)

**Docstring в коде:** нет

```
"""UPDATE status and error_message; set enabled_at=CURRENT_TIMESTAMP only when status is enabled."""
```

Иначе `enabled_at` не трогается.

### `ModuleLoader._set_module_buttons_active` (874–886)

**Docstring в коде:** есть

```
Enable or disable buttons associated with a module.
```

`UPDATE button_configs SET is_active=? WHERE button_id=?` — `button_id` равен `module_id`. 1/0.

### `ModuleLoader._get_registry_row` (888–894)

**Docstring в коде:** нет

```
"""Return one modules_registry row as dict, or None."""
```

### `ModuleLoader._fetch_registry_rows` (896–904)

**Docstring в коде:** нет

```
"""Return all modules_registry rows keyed by module_id."""
```

## `get_global_module_loader` (910–914)

**Docstring в коде:** нет

```
"""Return the process-wide ModuleLoader singleton, creating it on first call."""
```
