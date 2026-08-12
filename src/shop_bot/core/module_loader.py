from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from aiogram import Router
from flask import Blueprint

from shop_bot.core.module_middleware import ModuleSafeMiddleware
from shop_bot.core.module_types import ModuleInfo, ModuleMeta, ModuleStatus
from shop_bot.data_manager import database

logger = logging.getLogger(__name__)

# Limits for ZIP module imports (CWE-22 / zip-bomb / unexpected payloads).
MAX_MODULE_ZIP_BYTES = 10 * 1024 * 1024  # 10 MiB compressed
MAX_MODULE_ZIP_UNCOMPRESSED_BYTES = 40 * 1024 * 1024  # 40 MiB total uncompressed
MAX_MODULE_ZIP_FILES = 200
_MODULE_ID_RE = re.compile(r"^[a-z0-9_]+$")
_ALLOWED_MODULE_EXTENSIONS = frozenset(
    {
        ".py",
        ".html",
        ".htm",
        ".css",
        ".js",
        ".json",
        ".md",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".cfg",
        ".ini",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".gif",
    }
)
_ALLOWED_EXTENSIONLESS_NAMES = frozenset(
    {
        "license",
        "readme",
        "changelog",
        "notice",
        "copying",
        "authors",
        "contributors",
    }
)


@dataclass
class _LoadedModule:
    meta: ModuleMeta
    path: Path
    module_obj: ModuleType
    router: Router | None = None
    blueprint: Blueprint | None = None
    settings_schema: list[dict[str, Any]] = field(default_factory=list)
    cleanup: Any | None = None
    schema_sql: list[str] = field(default_factory=list)
    module_names: list[str] = field(default_factory=list)


class ModuleLoader:
    """Discovers, loads, and manages plugin modules."""

    def __init__(self, modules_path: Path | None = None, db_file: Path | None = None) -> None:
        self._modules_path = modules_path or (Path(__file__).resolve().parents[3] / "modules")
        self._db_file = db_file or database.DB_FILE
        self._dispatcher = None
        self._flask_app = None
        self._discovered = False
        self._modules: dict[str, ModuleMeta] = {}
        self._module_paths: dict[str, Path] = {}
        self._loaded: dict[str, _LoadedModule] = {}
        self._enabled_cache: set[str] = set()

    def set_dispatcher(self, dispatcher: Any) -> None:
        """Attach aiogram dispatcher for module router registration."""
        self._dispatcher = dispatcher
        self._activate_enabled_modules()

    def set_flask_app(self, app: Any) -> None:
        """Attach Flask app for module blueprint registration."""
        self._flask_app = app
        self._activate_enabled_modules()

    def discover_modules(self) -> dict[str, ModuleMeta]:
        """Discover module manifests under the modules directory."""
        if self._discovered:
            return dict(self._modules)
        self._discovered = True
        if not self._modules_path.exists():
            logger.info("Modules directory not found: %s", self._modules_path)
            return {}

        for entry in sorted(self._modules_path.iterdir()):
            if not entry.is_dir():
                continue
            manifest_path = entry / "__init__.py"
            if not manifest_path.exists():
                continue
            try:
                meta = self._load_manifest(entry)
            except Exception as exc:
                logger.error("Module manifest load failed for %s: %s", entry.name, exc, exc_info=True)
                self._set_status(entry.name, ModuleStatus.ERROR, str(exc))
                continue
            if not self._validate_module_meta(meta, entry.name):
                self._set_status(entry.name, ModuleStatus.ERROR, "Invalid module manifest")
                continue
            self._modules[meta.id] = meta
            self._module_paths[meta.id] = entry
            self._upsert_registry(meta)
        return dict(self._modules)

    def list_modules(self) -> list[dict[str, Any]]:
        """Return a list of modules with status for UI usage."""
        self.discover_modules()
        rows = self._fetch_registry_rows()
        modules: list[ModuleInfo] = []
        for module_id, meta in self._modules.items():
            row = rows.get(module_id) or {}
            status_raw = row.get("status") or ModuleStatus.DISABLED.value
            try:
                status = ModuleStatus(status_raw)
            except Exception:
                status = ModuleStatus.ERROR
            error_message = row.get("error_message")
            enabled_at = row.get("enabled_at")
            modules.append(
                ModuleInfo(
                    meta=meta,
                    status=status,
                    enabled_at=enabled_at,
                    error_message=error_message,
                    has_settings=bool(meta.settings_schema),
                    path=str(self._module_paths.get(module_id) or ""),
                )
            )
        for module_id, row in rows.items():
            if module_id in self._modules:
                continue
            meta = ModuleMeta(
                id=module_id,
                name=row.get("name") or module_id,
                version=row.get("version") or "",
                description="Module files not found",
                author="",
            )
            modules.append(
                ModuleInfo(
                    meta=meta,
                    status=ModuleStatus.ERROR,
                    enabled_at=row.get("enabled_at"),
                    error_message=row.get("error_message") or "Module files missing",
                    has_settings=False,
                )
            )
        modules.sort(key=lambda item: item.meta.id)
        return [m.to_dict() for m in modules]

    def get_module_status(self, module_id: str) -> ModuleStatus:
        """Return current status for a module."""
        row = self._get_registry_row(module_id)
        if not row:
            return ModuleStatus.MISSING
        status_raw = row.get("status") or ModuleStatus.DISABLED.value
        try:
            return ModuleStatus(status_raw)
        except Exception:
            return ModuleStatus.ERROR

    def load_module(self, module_id: str) -> _LoadedModule | None:
        """Import module code and prepare its hooks."""
        self.discover_modules()
        if module_id in self._loaded:
            return self._loaded[module_id]
        meta = self._modules.get(module_id)
        if not meta:
            return None
        module_path = self._module_paths.get(module_id)
        if not module_path:
            return None
        try:
            module_names: list[str] = []
            module_obj = self._import_from_path(module_path / "__init__.py", f"xatabchik_module_{module_id}")
            module_names.append(module_obj.__name__)
            router = self._load_router(module_id, meta, module_path, module_names)
            blueprint = self._load_blueprint(module_id, meta, module_path, module_names)
            schema_sql = self._load_schema_sql(meta, module_path, module_names)
            cleanup = self._load_cleanup(meta, module_path, module_names)
            settings_schema = self._load_settings_schema(meta, module_path, module_names)
            loaded = _LoadedModule(
                meta=meta,
                path=module_path,
                module_obj=module_obj,
                router=router,
                blueprint=blueprint,
                settings_schema=settings_schema,
                cleanup=cleanup,
                schema_sql=schema_sql,
                module_names=module_names,
            )
            self._loaded[module_id] = loaded
            return loaded
        except Exception as exc:
            logger.error("Module load failed (%s): %s", module_id, exc, exc_info=True)
            self.set_module_error(module_id, str(exc))
            return None

    def unload_module(self, module_id: str) -> None:
        """Unload module hooks and imported code."""
        loaded = self._loaded.pop(module_id, None)
        if not loaded:
            return
        try:
            if loaded.router and self._dispatcher:
                self._detach_router(self._dispatcher, loaded.router)
            if loaded.blueprint and self._flask_app:
                self._unregister_blueprint(self._flask_app, loaded.blueprint.name)
        except Exception as exc:
            logger.warning("Module unload cleanup failed (%s): %s", module_id, exc)
        for name in loaded.module_names:
            sys.modules.pop(name, None)

    def enable_module(self, module_id: str, *, from_startup: bool = False) -> tuple[bool, str]:
        """Enable a module and register its hooks."""
        self.discover_modules()
        meta = self._modules.get(module_id)
        if not meta:
            return False, "Module not found"
        requires = [r for r in (meta.requires or []) if r]
        for req in requires:
            if self.get_module_status(req) != ModuleStatus.ENABLED:
                return False, f"Dependency not enabled: {req}"
        loaded = self.load_module(module_id)
        if not loaded:
            return False, "Module load failed"
        if loaded.schema_sql:
            ok, error = self._apply_schema(module_id, loaded.schema_sql)
            if not ok:
                return False, error or "Schema error"
        if loaded.settings_schema:
            self._ensure_settings_defaults(module_id, loaded.settings_schema)
        if self._dispatcher and loaded.router:
            self._attach_router(module_id, loaded.router)
        if self._flask_app and loaded.blueprint:
            self._register_blueprint(module_id, loaded.blueprint)
        # Enable module buttons
        self._set_module_buttons_active(module_id, True)
        if not from_startup:
            self._set_status(module_id, ModuleStatus.ENABLED)
        self._enabled_cache.add(module_id)
        return True, "Module enabled"

    def disable_module(self, module_id: str) -> tuple[bool, str]:
        """Disable a module without deleting its data."""
        loaded = self._loaded.get(module_id)
        if loaded and self._dispatcher and loaded.router:
            self._detach_router(self._dispatcher, loaded.router)
        if loaded and self._flask_app and loaded.blueprint:
            self._unregister_blueprint(module_id)
        # Disable module buttons
        self._set_module_buttons_active(module_id, False)
        self._enabled_cache.discard(module_id)
        self._set_status(module_id, ModuleStatus.DISABLED)
        return True, "Module disabled"

    def delete_module(self, module_id: str) -> tuple[bool, str]:
        """Delete a module and remove its data."""
        dependents = self._get_dependents(module_id)
        if dependents:
            return False, f"Dependent modules: {', '.join(dependents)}"
        loaded = self._loaded.get(module_id)
        if loaded and loaded.cleanup:
            try:
                with sqlite3.connect(self._db_file) as conn:
                    loaded.cleanup(conn)
            except Exception as exc:
                self.set_module_error(module_id, str(exc))
                return False, "Cleanup failed"
        else:
            self._delete_settings_prefix(module_id)
        self.disable_module(module_id)
        self.unload_module(module_id)
        self._delete_registry(module_id)
        self._delete_module_files(module_id)
        return True, "Module deleted"

    def get_menu_items(self) -> list[dict[str, str]]:
        """Collect panel menu items from enabled modules."""
        self.discover_modules()
        items: list[dict[str, str]] = []
        for module_id, meta in self._modules.items():
            if self.get_module_status(module_id) != ModuleStatus.ENABLED:
                continue
            for item in meta.menu_items or []:
                if isinstance(item, dict) and item.get("label") and item.get("url"):
                    items.append(item)
        return items

    def get_settings_schema(self, module_id: str) -> list[dict[str, Any]]:
        """Return module settings schema if available."""
        self.discover_modules()
        meta = self._modules.get(module_id)
        if not meta or not meta.settings_schema:
            return []
        loaded = self.load_module(module_id)
        if not loaded:
            return []
        return list(loaded.settings_schema)

    def get_settings_values(self, module_id: str) -> dict[str, Any]:
        """Return current values for module settings."""
        values: dict[str, Any] = {}
        schema = self.get_settings_schema(module_id)
        if not schema:
            return values
        keys = [f"{module_id}_{item.get('key')}" for item in schema if item.get("key")]
        if not keys:
            return values
        with sqlite3.connect(self._db_file) as conn:
            cursor = conn.cursor()
            for full_key in keys:
                cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (full_key,))
                row = cursor.fetchone()
                values[full_key] = row[0] if row else None
        return values

    def set_module_error(self, module_id: str, message: str) -> None:
        """Mark module as failed with error message."""
        self._set_status(module_id, ModuleStatus.ERROR, message)

    def _activate_enabled_modules(self) -> None:
        if not self._dispatcher and not self._flask_app:
            return
        rows = self._fetch_registry_rows()
        for module_id, row in rows.items():
            if row.get("status") != ModuleStatus.ENABLED.value:
                # Ensure disabled modules have inactive buttons
                self._set_module_buttons_active(module_id, False)
                continue
            if module_id in self._enabled_cache:
                continue
            ok, _ = self.enable_module(module_id, from_startup=True)
            if ok:
                self._enabled_cache.add(module_id)

    def _load_manifest(self, module_path: Path) -> ModuleMeta:
        module_obj = self._import_from_path(module_path / "__init__.py", f"xatabchik_manifest_{module_path.name}")
        meta = getattr(module_obj, "MODULE_META", None)
        if isinstance(meta, ModuleMeta):
            return meta
        if isinstance(meta, dict):
            return ModuleMeta.from_dict(meta)
        raise ValueError("MODULE_META not found")

    def _validate_module_meta(self, meta: ModuleMeta, folder_name: str) -> bool:
        if not meta.id or not re.match(r"^[a-z0-9_]+$", meta.id):
            logger.error("Module id invalid: %s", meta.id)
            return False
        if meta.id != folder_name:
            logger.error("Module id mismatch: %s vs folder %s", meta.id, folder_name)
            return False
        if not meta.name or not meta.version:
            logger.error("Module meta missing name/version: %s", meta.id)
            return False
        return True

    def _import_from_path(self, file_path: Path, module_name: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Unable to load {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _load_router(self, module_id: str, meta: ModuleMeta, module_path: Path, names: list[str]) -> Router | None:
        if not meta.bot_entry:
            return None
        entry = module_path / f"{meta.bot_entry}.py"
        if not entry.exists():
            raise FileNotFoundError(f"bot_entry missing: {entry}")
        module = self._import_from_path(entry, f"xatabchik_module_{module_id}_bot")
        names.append(module.__name__)
        router = getattr(module, "router", None)
        if not isinstance(router, Router):
            raise TypeError("bot_entry.router must be aiogram.Router")
        router.message.middleware(ModuleSafeMiddleware(module_id, self))
        router.callback_query.middleware(ModuleSafeMiddleware(module_id, self))
        return router

    def _load_blueprint(self, module_id: str, meta: ModuleMeta, module_path: Path, names: list[str]) -> Blueprint | None:
        if not meta.panel_entry:
            return None
        entry = module_path / f"{meta.panel_entry}.py"
        if not entry.exists():
            raise FileNotFoundError(f"panel_entry missing: {entry}")
        module = self._import_from_path(entry, f"xatabchik_module_{module_id}_panel")
        names.append(module.__name__)
        blueprint = getattr(module, "bp", None)
        if not isinstance(blueprint, Blueprint):
            raise TypeError("panel_entry.bp must be flask.Blueprint")
        return blueprint

    def _load_schema_sql(self, meta: ModuleMeta, module_path: Path, names: list[str]) -> list[str]:
        if not meta.db_schema:
            return []
        entry = module_path / f"{meta.db_schema}.py"
        if not entry.exists():
            raise FileNotFoundError(f"db_schema missing: {entry}")
        module = self._import_from_path(entry, f"xatabchik_module_{meta.id}_schema")
        names.append(module.__name__)
        schema_sql = getattr(module, "SCHEMA_SQL", None)
        if schema_sql is None:
            schema_sql = getattr(module, "schema_sql", None)
        if callable(schema_sql):
            schema_sql = schema_sql()
        if isinstance(schema_sql, str):
            statements = [schema_sql]
        elif isinstance(schema_sql, (list, tuple)):
            statements = [str(item) for item in schema_sql if str(item).strip()]
        else:
            raise ValueError("SCHEMA_SQL not found")
        self._validate_schema(meta.id, statements)
        return statements

    def _load_cleanup(self, meta: ModuleMeta, module_path: Path, names: list[str]) -> Any | None:
        if not meta.db_cleanup:
            return None
        entry = module_path / f"{meta.db_cleanup}.py"
        if not entry.exists():
            raise FileNotFoundError(f"db_cleanup missing: {entry}")
        module = self._import_from_path(entry, f"xatabchik_module_{meta.id}_cleanup")
        names.append(module.__name__)
        cleanup = getattr(module, "cleanup", None)
        if not callable(cleanup):
            raise TypeError("db_cleanup.cleanup must be callable")
        return cleanup

    def _load_settings_schema(self, meta: ModuleMeta, module_path: Path, names: list[str]) -> list[dict[str, Any]]:
        if not meta.settings_schema:
            return []
        entry = module_path / f"{meta.settings_schema}.py"
        if not entry.exists():
            raise FileNotFoundError(f"settings_schema missing: {entry}")
        module = self._import_from_path(entry, f"xatabchik_module_{meta.id}_settings")
        names.append(module.__name__)
        settings = getattr(module, "SETTINGS", None)
        if not isinstance(settings, list):
            raise TypeError("settings_schema.SETTINGS must be a list")
        return settings

    def _validate_schema(self, module_id: str, statements: list[str]) -> None:
        create_re = re.compile(r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?([\"`\[]?[^\s(\"`\]]+[\"`\]]?)", re.IGNORECASE)
        for stmt in statements:
            for match in create_re.finditer(stmt):
                table = match.group(2).strip("`\"[]")
                if not table.startswith(f"{module_id}_"):
                    raise ValueError(f"Table '{table}' must be prefixed with {module_id}_")

    def _apply_schema(self, module_id: str, statements: list[str]) -> tuple[bool, str | None]:
        try:
            with sqlite3.connect(self._db_file) as conn:
                cur = conn.cursor()
                for stmt in statements:
                    cur.executescript(stmt)
            return True, None
        except Exception as exc:
            self.set_module_error(module_id, str(exc))
            return False, str(exc)

    def _ensure_settings_defaults(self, module_id: str, settings: list[dict[str, Any]]) -> None:
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            for setting in settings:
                key = setting.get("key")
                if not key:
                    continue
                full_key = f"{module_id}_{key}"
                cur.execute("SELECT value FROM bot_settings WHERE key = ?", (full_key,))
                row = cur.fetchone()
                if row is None:
                    default = setting.get("default")
                    if isinstance(default, bool):
                        value = "true" if default else "false"
                    elif isinstance(default, (dict, list)):
                        value = json.dumps(default, ensure_ascii=True)
                    else:
                        value = "" if default is None else str(default)
                    cur.execute(
                        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
                        (full_key, value),
                    )

    def _delete_settings_prefix(self, module_id: str) -> None:
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM bot_settings WHERE key LIKE ?", (f"{module_id}_%",))

    def _attach_router(self, module_id: str, router: Router) -> None:
        if not self._dispatcher:
            return
        # Check if router is already attached
        try:
            sub_routers = getattr(self._dispatcher, "sub_routers", [])
            if router in sub_routers:
                logger.debug("Module router already attached: %s", module_id)
                return
        except Exception as e:
            logger.warning("Error checking sub_routers: %s", e)
        
        try:
            self._dispatcher.include_router(router)
            logger.info("Module router attached: %s", module_id)
        except RuntimeError as e:
            if "already attached" in str(e):
                logger.debug("Module router was already attached: %s", module_id)
            else:
                raise

    def _detach_router(self, dispatcher: Any, router: Router) -> None:
        """Detach router from dispatcher."""
        try:
            sub_routers = getattr(dispatcher, "sub_routers", [])
            if router not in sub_routers:
                return
            sub_routers.remove(router)
            # Reset parent_router using private attribute to avoid setter validation
            if hasattr(router, '_parent_router'):
                router._parent_router = None
            logger.debug("Router detached successfully")
        except Exception as e:
            logger.warning("Error detaching router: %s", e)

    def _register_blueprint(self, module_id: str, blueprint: Blueprint) -> None:
        """Store blueprint routes in a registry for dynamic dispatch.
        
        This allows module routes to be added after the app has started.
        Routes are handled by a special proxy endpoint.
        """
        if not self._flask_app:
            return
        
        # Store reference to blueprints and their routes
        if not hasattr(self._flask_app, '_module_route_registry'):
            self._flask_app._module_route_registry = {}
        
        # Add module's template folder to Jinja loader search path
        if blueprint.template_folder:
            from jinja2 import ChoiceLoader, FileSystemLoader
            module_path = self._module_paths.get(module_id)
            if module_path:
                template_path = module_path / blueprint.template_folder
                if template_path.exists():
                    # Get current loader
                    current_loader = self._flask_app.jinja_loader
                    # Create new loader that includes module templates
                    new_loader = ChoiceLoader([
                        current_loader,
                        FileSystemLoader(str(template_path))
                    ])
                    self._flask_app.jinja_loader = new_loader
        
        # To extract view_functions from blueprint, we need to register it to a temp app
        # because Blueprint only populates view_functions during registration
        from flask import Flask
        temp_app = Flask(__name__)
        temp_app.register_blueprint(blueprint)
        
        # Now extract the populated view_functions
        view_functions = {}
        for endpoint, func in temp_app.view_functions.items():
            # Endpoints are in format "blueprint_name.function_name"
            if '.' in endpoint:
                func_name = endpoint.split('.')[-1]
                view_functions[func_name] = func
        
        # Store the view functions in the registry
        self._flask_app._module_route_registry[module_id] = view_functions

    def _unregister_blueprint(self, module_id: str) -> None:
        """Remove registered blueprint routes from the registry."""
        if not self._flask_app or not hasattr(self._flask_app, '_module_route_registry'):
            return
        
        # Remove the blueprint for this module
        self._flask_app._module_route_registry.pop(module_id, None)

    def _get_dependents(self, module_id: str) -> list[str]:
        dependents: list[str] = []
        for meta in self._modules.values():
            if module_id in (meta.requires or []):
                dependents.append(meta.id)
        return dependents

    def _delete_module_files(self, module_id: str) -> None:
        path = self._module_paths.get(module_id)
        if not path or not path.exists():
            return
        try:
            shutil.rmtree(path)
        except Exception as exc:
            logger.warning("Failed to delete module files %s: %s", module_id, exc)

    @staticmethod
    def _normalize_zip_member_name(name: str) -> str | None:
        """Normalize a ZIP member path; return None if the name is unsafe."""
        if not name or "\x00" in name:
            return None
        # ZIP uses forward slashes; reject Windows separators / drive letters.
        if "\\" in name or (len(name) >= 2 and name[1] == ":"):
            return None
        if name.startswith("/") or name.startswith("//"):
            return None
        normalized = name.replace("\\", "/")
        # Collapse duplicate slashes but keep trailing slash for directories.
        parts = [p for p in normalized.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            return None
        if normalized.endswith("/"):
            return "/".join(parts) + "/" if parts else None
        return "/".join(parts) if parts else None

    @classmethod
    def _is_allowed_module_member(cls, relative_path: str) -> bool:
        """Allow only module source/manifest/assets; reject scripts and binaries."""
        if not relative_path or relative_path.endswith("/"):
            return True
        name = Path(relative_path).name
        if not name or name in (".", ".."):
            return False
        # Hidden / macOS junk often appears in archives; reject for safety.
        if name.startswith(".") and name not in (".gitignore",):
            return False
        suffix = Path(name).suffix.lower()
        if not suffix:
            return name.lower() in _ALLOWED_EXTENSIONLESS_NAMES
        return suffix in _ALLOWED_MODULE_EXTENSIONS

    def _resolve_extract_path(self, target_root: Path, relative_path: str) -> Path | None:
        """Resolve extract destination and ensure it stays under target_root (zip-slip)."""
        if not relative_path or relative_path.endswith("/"):
            return None
        # Refuse absolute / parent segments again at join time.
        if relative_path.startswith("/") or ".." in Path(relative_path).parts:
            return None
        dest = (target_root / relative_path).resolve()
        root = target_root.resolve()
        try:
            if not dest.is_relative_to(root):
                return None
        except AttributeError:
            # Python < 3.9 fallback (not expected on 3.11, kept for safety).
            if os.path.commonpath([str(root), str(dest)]) != str(root):
                return None
        return dest

    def import_module_from_zip(self, zip_file_path: str | Path, *, auto_enable: bool = True) -> tuple[bool, str]:
        """Import a module from a ZIP file.

        Expects ZIP with structure:
            module_name/
                __init__.py
                bot_handlers.py
                ...

        Hardened against zip-slip (CWE-22), zip bombs, and unexpected payloads.
        """
        zip_path = Path(zip_file_path)
        target_path: Path | None = None
        if not zip_path.exists():
            return False, "ZIP file not found"

        if zip_path.suffix.lower() != ".zip":
            return False, "File is not a ZIP archive"

        try:
            zip_size = zip_path.stat().st_size
        except OSError as exc:
            return False, f"Unable to read ZIP file: {exc}"
        if zip_size <= 0:
            return False, "ZIP archive is empty"
        if zip_size > MAX_MODULE_ZIP_BYTES:
            return False, f"ZIP file too large (max {MAX_MODULE_ZIP_BYTES // (1024 * 1024)} MB)"

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                infos = zf.infolist()
                if not infos:
                    return False, "ZIP archive is empty"
                if len(infos) > MAX_MODULE_ZIP_FILES:
                    return False, f"ZIP contains too many entries (max {MAX_MODULE_ZIP_FILES})"

                total_uncompressed = 0
                normalized_names: list[str] = []
                for info in infos:
                    if info.file_size < 0:
                        return False, "Invalid ZIP entry size"
                    total_uncompressed += info.file_size
                    if total_uncompressed > MAX_MODULE_ZIP_UNCOMPRESSED_BYTES:
                        return False, "ZIP uncompressed size exceeds limit"
                    # Reject symlink / special entries when metadata is present.
                    try:
                        if info.is_symlink():  # type: ignore[attr-defined]
                            return False, "Symlinks are not allowed in module ZIP"
                    except AttributeError:
                        mode = (info.external_attr >> 16) & 0o170000
                        if mode == 0o120000:
                            return False, "Symlinks are not allowed in module ZIP"
                    # Large highly-compressible members are a zip-bomb signal.
                    if (
                        info.file_size > 1_000_000
                        and info.compress_size > 0
                        and info.file_size > info.compress_size * 100
                    ):
                        return False, "Suspicious ZIP compression ratio"
                    normalized = self._normalize_zip_member_name(info.filename)
                    if normalized is None:
                        return False, f"Unsafe path in ZIP: {info.filename}"
                    normalized_names.append(normalized)

                # Determine module root from first non-empty normalized path.
                module_name = ""
                for name in normalized_names:
                    module_name = name.split("/", 1)[0]
                    if module_name:
                        break
                if not module_name or not _MODULE_ID_RE.match(module_name):
                    return False, "Invalid module directory name in ZIP"

                if f"{module_name}/__init__.py" not in normalized_names:
                    return False, "Module __init__.py not found"

                # All members must live under module_name/
                for name in normalized_names:
                    if name != module_name and not name.startswith(f"{module_name}/"):
                        return False, "ZIP contains files outside the module directory"
                    rel = "" if name.rstrip("/") == module_name else name[len(module_name) + 1 :]
                    if rel and not self._is_allowed_module_member(rel):
                        return False, f"Disallowed file type in ZIP: {rel}"

                target_path = self._modules_path / module_name
                if target_path.exists():
                    return False, f"Module '{module_name}' already exists"

                self._modules_path.mkdir(parents=True, exist_ok=True)
                target_path.mkdir(parents=True, exist_ok=False)

                for info, name in zip(infos, normalized_names):
                    is_dir = name.endswith("/") or getattr(info, "is_dir", lambda: False)()
                    if name.rstrip("/") == module_name or is_dir:
                        rel_dir = ""
                        if name.startswith(f"{module_name}/"):
                            rel_dir = name[len(module_name) + 1 :].rstrip("/")
                        if rel_dir:
                            # Validate directory stays under target via a child sentinel path.
                            probe = self._resolve_extract_path(target_path, f"{rel_dir}/__dir__")
                            if probe is None:
                                raise ValueError(f"Path traversal blocked: {info.filename}")
                            probe.parent.mkdir(parents=True, exist_ok=True)
                        continue

                    rel_path = name[len(module_name) + 1 :]
                    dest = self._resolve_extract_path(target_path, rel_path)
                    if dest is None:
                        raise ValueError(f"Path traversal blocked: {info.filename}")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as source, open(dest, "wb") as out:
                        remaining = info.file_size
                        while remaining > 0:
                            chunk = source.read(min(65536, remaining))
                            if not chunk:
                                break
                            out.write(chunk)
                            remaining -= len(chunk)
                        if remaining != 0:
                            raise ValueError(f"Truncated ZIP member: {info.filename}")

                logger.info("Module extracted: %s -> %s", module_name, target_path)
        except zipfile.BadZipFile:
            if target_path and target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            return False, "Invalid ZIP file"
        except Exception as exc:
            if target_path and target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            return False, f"Extraction error: {exc}"

        # Discover the new module
        self._discovered = False
        self.discover_modules()

        if module_name not in self._modules:
            if target_path and target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            return False, "Module was extracted but failed validation"

        if auto_enable:
            ok, msg = self.enable_module(module_name)
            if not ok:
                logger.warning("Auto-enable failed for %s: %s", module_name, msg)
                return False, f"Module extracted but enable failed: {msg}"
            return True, f"Module '{module_name}' imported and enabled successfully"

        return True, f"Module '{module_name}' imported successfully"

    def _upsert_registry(self, meta: ModuleMeta) -> None:
        row = self._get_registry_row(meta.id)
        if row is None:
            self._insert_registry(meta)
            return
        payload = json.dumps(meta.to_dict(), ensure_ascii=True)
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE modules_registry
                   SET name = ?, version = ?, metadata = ?
                 WHERE module_id = ?
                """,
                (meta.name, meta.version, payload, meta.id),
            )

    def _insert_registry(self, meta: ModuleMeta) -> None:
        payload = json.dumps(meta.to_dict(), ensure_ascii=True)
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO modules_registry
                    (module_id, name, version, status, enabled_at, error_message, metadata)
                VALUES (?, ?, ?, ?, NULL, NULL, ?)
                """,
                (meta.id, meta.name, meta.version, ModuleStatus.DISABLED.value, payload),
            )

    def _delete_registry(self, module_id: str) -> None:
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM modules_registry WHERE module_id = ?", (module_id,))

    def _set_status(self, module_id: str, status: ModuleStatus, error_message: str | None = None) -> None:
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE modules_registry
                   SET status = ?, enabled_at = CASE WHEN ? = 'enabled' THEN CURRENT_TIMESTAMP ELSE enabled_at END,
                       error_message = ?
                 WHERE module_id = ?
                """,
                (status.value, status.value, error_message, module_id),
            )

    def _set_module_buttons_active(self, module_id: str, active: bool) -> None:
        """Enable or disable buttons associated with a module."""
        with sqlite3.connect(self._db_file) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE button_configs
                   SET is_active = ?
                 WHERE button_id = ?
                """,
                (1 if active else 0, module_id),
            )
            conn.commit()

    def _get_registry_row(self, module_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self._db_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM modules_registry WHERE module_id = ?", (module_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def _fetch_registry_rows(self) -> dict[str, dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        with sqlite3.connect(self._db_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM modules_registry")
            for row in cur.fetchall():
                rows[row["module_id"]] = dict(row)
        return rows


_global_loader: ModuleLoader | None = None


def get_global_module_loader() -> ModuleLoader:
    global _global_loader
    if _global_loader is None:
        _global_loader = ModuleLoader()
    return _global_loader
