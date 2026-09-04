"""Доменные модули слоя доступа к БД, выделенные из `database.py`.

До разделения все функции лежали в одном модуле и обращались друг к другу и к
модульным глобалам (`DB_FILE`, `logger`) по голому имени, то есть через словарь
одного пространства имён в момент вызова. На этом основаны два рабочих
механизма проекта:

* тесты подменяют путь к БД одной строкой — `monkeypatch.setattr(database,
  "DB_FILE", tmp_path / "test.db")` (см. фикстуру `temp_db` в `tests/conftest.py`),
  и это должны увидеть все функции;
* тесты подменяют отдельные функции — например
  `monkeypatch.setattr(database, "find_open_tickets_idle_after_admin", ...)`, —
  и подмену должны увидеть внутренние вызывающие (`auto_close_idle_admin_tickets`).

PEP 562 `__getattr__` здесь не помогает: он вызывается только при обращении к
атрибуту модуля, а `LOAD_GLOBAL` (голое имя в теле функции) его не задействует
и падает с `NameError`. Поэтому пакет собирает единое пространство имён обратно:
`_link_namespace` раздаёт каждому модулю имена соседей, а `broadcast` разносит
запись в атрибут фасада по всем модулям, где это имя присутствует. Из-за этого
ни один доменный модуль не импортирует значения соседей на уровне модуля —
такой импорт скопировал бы значение один раз и не увидел подмену.
"""
import types as _types

from . import _core
from . import analytics
from . import broadcasts
from . import buttons
from . import captcha_auth
from . import franchise
from . import gifts
from . import hosts
from . import keys
from . import lte
from . import payments
from . import plans
from . import promo
from . import referral
from . import schema
from . import ssh_targets
from . import tickets
from . import users

MODULES = (
    _core,
    analytics,
    broadcasts,
    buttons,
    captcha_auth,
    franchise,
    gifts,
    hosts,
    keys,
    lte,
    payments,
    plans,
    promo,
    referral,
    schema,
    ssh_targets,
    tickets,
    users,
)


def _link_namespace() -> None:
    """Раздать каждому доменному модулю имена, объявленные в соседних модулях."""
    shared: dict[str, object] = {}
    for module in MODULES:
        for name in module.__all__:
            shared[name] = getattr(module, name)
    for module in MODULES:
        for name, value in shared.items():
            if name not in module.__dict__:
                _types.ModuleType.__setattr__(module, name, value)


def broadcast(name: str, value: object) -> None:
    """Записать значение во все доменные модули, где имя уже присутствует."""
    for module in MODULES:
        if name in module.__dict__:
            _types.ModuleType.__setattr__(module, name, value)


_link_namespace()
