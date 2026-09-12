"""Административная часть бота, разделённая из bot/admin_handlers.py.

Все 288 хендлеров были вложенными функциями одной фабрики
`get_admin_router()` и обращались к соседям просто по имени. Чтобы не
править тела функций, они переехали в register_*-сегменты как есть, а
общее пространство имён воссоздаётся здесь: `_link_namespace()` после
импорта всех модулей раскладывает по ним имена, поднятые на уровень
модуля, — обращение по имени снова разрешается в момент вызова.

Отдельная причина так делать — подмена атрибутов извне. Тест
`test_admin_router_authorization.py` пишет
`monkeypatch.setattr(admin_handlers, "get_admin_stats", ...)`, и до
разделения это видели все функции файла. Такие записи фасад рассылает
через `broadcast()`.

PEP 562 (`__getattr__` модуля) здесь не помогает: обращение к глобальному
имени внутри функции компилируется в LOAD_GLOBAL и до `__getattr__` не
доходит.
"""

from shop_bot.bot.admin_router import core  # noqa: F401
from shop_bot.bot.admin_router import menu  # noqa: F401
from shop_bot.bot.admin_router import promo  # noqa: F401
from shop_bot.bot.admin_router import modules  # noqa: F401
from shop_bot.bot.admin_router import button_constructor  # noqa: F401
from shop_bot.bot.admin_router import payments  # noqa: F401
from shop_bot.bot.admin_router import referral  # noqa: F401
from shop_bot.bot.admin_router import franchise  # noqa: F401
from shop_bot.bot.admin_router import hosts  # noqa: F401
from shop_bot.bot.admin_router import trial  # noqa: F401
from shop_bot.bot.admin_router import lte_settings  # noqa: F401
from shop_bot.bot.admin_router import notifications  # noqa: F401
from shop_bot.bot.admin_router import plans  # noqa: F401
from shop_bot.bot.admin_router import speedtest  # noqa: F401
from shop_bot.bot.admin_router import backup  # noqa: F401
from shop_bot.bot.admin_router import users  # noqa: F401
from shop_bot.bot.admin_router import admins  # noqa: F401
from shop_bot.bot.admin_router import keys  # noqa: F401
from shop_bot.bot.admin_router import gifts  # noqa: F401
from shop_bot.bot.admin_router import balance  # noqa: F401
from shop_bot.bot.admin_router import host_keys  # noqa: F401
from shop_bot.bot.admin_router import key_quick_ops  # noqa: F401
from shop_bot.bot.admin_router import mailing  # noqa: F401
from shop_bot.bot.admin_router import withdrawals  # noqa: F401
from shop_bot.bot.admin_router import monitor  # noqa: F401
from shop_bot.bot.admin_router import captcha  # noqa: F401
from shop_bot.bot.admin_router import auto_renew  # noqa: F401
from shop_bot.bot.admin_router import router  # noqa: F401

MODULES = (
    core,
    menu,
    promo,
    modules,
    button_constructor,
    payments,
    referral,
    franchise,
    hosts,
    trial,
    lte_settings,
    notifications,
    plans,
    speedtest,
    backup,
    users,
    admins,
    keys,
    gifts,
    balance,
    host_keys,
    key_quick_ops,
    mailing,
    withdrawals,
    monitor,
    captcha,
    auto_renew,
    router,
)


def _link_namespace() -> None:
    """Раскладывает экспортируемые имена каждого модуля по остальным.

    После этого вложенные функции видят соседей через LOAD_GLOBAL ровно
    так, как видели их локальными переменными одной фабрики.
    """
    for owner in MODULES:
        for name in getattr(owner, "__all__", ()):
            value = getattr(owner, name)
            for target in MODULES:
                if target is owner:
                    continue
                if name not in target.__dict__:
                    setattr(target, name, value)


def broadcast(name: str, value: object) -> None:
    """Разносит запись атрибута фасада по модулям, где это имя есть."""
    for target in MODULES:
        if name in target.__dict__:
            setattr(target, name, value)


_link_namespace()
