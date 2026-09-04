"""Фасад слоя доступа к БД: единая точка входа с прежним публичным API.

Код разъехался по доменным модулям подпакета `db/` (см. `db/__init__.py`), но
для всего остального проекта ничего не изменилось: и `from
shop_bot.data_manager.database import get_setting`, и `database.DB_FILE`, и
`getattr(database, name)` (как в `_LEGACY_FORWARDERS` в
`remnawave_repository.py`) работают как раньше.

Модуль остаётся целью для подмены атрибутов: тесты пишут
`monkeypatch.setattr(database, "DB_FILE", ...)` или подменяют отдельные функции.
Пока весь код лежал в одном модуле, такая запись автоматически меняла то, что
видят внутренние вызывающие, — они читали тот же словарь. После разделения
пространство имён распалось на 18 частей, поэтому `__setattr__` ниже разносит
запись по доменным модулям через `db.broadcast`, сохраняя прежнюю семантику.
"""
import sys as _sys
import types as _types

import sqlite3
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
import hashlib
import hmac
import json
import secrets
import time
import re
import uuid
from typing import Any
import os

from . import db as _db

from .db._core import *  # noqa: F401,F403
from .db.analytics import *  # noqa: F401,F403
from .db.broadcasts import *  # noqa: F401,F403
from .db.buttons import *  # noqa: F401,F403
from .db.captcha_auth import *  # noqa: F401,F403
from .db.franchise import *  # noqa: F401,F403
from .db.gifts import *  # noqa: F401,F403
from .db.hosts import *  # noqa: F401,F403
from .db.keys import *  # noqa: F401,F403
from .db.lte import *  # noqa: F401,F403
from .db.payments import *  # noqa: F401,F403
from .db.plans import *  # noqa: F401,F403
from .db.promo import *  # noqa: F401,F403
from .db.referral import *  # noqa: F401,F403
from .db.schema import *  # noqa: F401,F403
from .db.ssh_targets import *  # noqa: F401,F403
from .db.tickets import *  # noqa: F401,F403
from .db.users import *  # noqa: F401,F403


class _DatabaseFacade(_types.ModuleType):
    """Тип модуля-фасада, разносящий запись атрибута по доменным модулям.

    Присваивания в теле самого модуля сюда не попадают (`STORE_NAME` пишет в
    `__dict__` напрямую) — перехватывается только внешний `setattr`, то есть
    ровно то, чем пользуются `monkeypatch` и рантайм-переключение настроек.
    """

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        _db.broadcast(name, value)


_sys.modules[__name__].__class__ = _DatabaseFacade
