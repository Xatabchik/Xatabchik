from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModuleStatus(str, Enum):
    """Runtime status for a plugin module."""

    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    MISSING = "missing"


@dataclass(frozen=True)
class ModuleMeta:
    """Module manifest metadata."""

    id: str
    name: str
    version: str
    description: str
    author: str
    requires: list[str] = field(default_factory=list)
    bot_entry: str | None = None
    panel_entry: str | None = None
    db_schema: str | None = None
    db_cleanup: str | None = None
    settings_schema: str | None = None
    menu_items: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleMeta":
        return cls(
            id=str(data.get("id") or "").strip(),
            name=str(data.get("name") or "").strip(),
            version=str(data.get("version") or "").strip(),
            description=str(data.get("description") or "").strip(),
            author=str(data.get("author") or "").strip(),
            requires=list(data.get("requires") or []),
            bot_entry=data.get("bot_entry") or None,
            panel_entry=data.get("panel_entry") or None,
            db_schema=data.get("db_schema") or None,
            db_cleanup=data.get("db_cleanup") or None,
            settings_schema=data.get("settings_schema") or None,
            menu_items=list(data.get("menu_items") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "requires": list(self.requires),
            "bot_entry": self.bot_entry,
            "panel_entry": self.panel_entry,
            "db_schema": self.db_schema,
            "db_cleanup": self.db_cleanup,
            "settings_schema": self.settings_schema,
            "menu_items": list(self.menu_items),
        }


@dataclass
class ModuleInfo:
    """Public-facing module information for UIs."""

    meta: ModuleMeta
    status: ModuleStatus
    enabled_at: str | None = None
    error_message: str | None = None
    has_settings: bool = False
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.meta.id,
            "name": self.meta.name,
            "version": self.meta.version,
            "description": self.meta.description,
            "author": self.meta.author,
            "requires": list(self.meta.requires),
            "status": self.status.value,
            "enabled_at": self.enabled_at,
            "error_message": self.error_message,
            "has_settings": self.has_settings,
            "menu_items": list(self.meta.menu_items),
            "path": self.path,
        }
