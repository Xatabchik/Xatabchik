"""Пользовательская часть бота, разделённая из bot/handlers.py.

Модули пакета сознательно не импортируют имена друг у друга: `handlers.py` был
одним пространством имён, и код внутри функций обращается к соседям просто по
имени. Вместо правки тел функций пространства имён связываются здесь, после
импорта всех модулей — тогда обращение по имени разрешается в момент вызова,
как и до разделения.

Отдельная причина так делать — подмена атрибутов извне. `bot_controller.py`
пишет `handlers.PAYMENT_METHODS`, `handlers.TELEGRAM_BOT_USERNAME` и
`handlers.ADMIN_ID` уже после старта, а тесты подменяют
`handlers.process_successful_payment` и `handlers.deduct_from_balance`. Все
такие записи фасад рассылает через `broadcast`, поэтому доменные модули видят
новое значение так же, как видели его в едином файле.

PEP 562 (`__getattr__` модуля) здесь не помогает: обращение к глобальному имени
внутри функции компилируется в LOAD_GLOBAL и до `__getattr__` не доходит.
"""

from . import _core  # noqa: F401
from . import key_errors  # noqa: F401
from . import formatting  # noqa: F401
from . import share_links  # noqa: F401
from . import referral_bonus  # noqa: F401
from . import gift_activation  # noqa: F401
from . import payment_providers  # noqa: F401
from . import states  # noqa: F401
from . import menu  # noqa: F401
from . import fulfillment  # noqa: F401
from . import onboarding  # noqa: F401
from . import profile_gifts  # noqa: F401
from . import traffic_topup  # noqa: F401
from . import lte_topup  # noqa: F401
from . import main_reset  # noqa: F401
from . import balance_topup  # noqa: F401
from . import providers  # noqa: F401
from . import payment_checks  # noqa: F401
from . import topup_methods  # noqa: F401
from . import referral  # noqa: F401
from . import support  # noqa: F401
from . import key_info  # noqa: F401
from . import key_manage  # noqa: F401
from . import key_view  # noqa: F401
from . import howto  # noqa: F401
from . import purchase  # noqa: F401
from . import payment_create  # noqa: F401
from . import gift_catcher  # noqa: F401
from . import franchise  # noqa: F401
from . import router  # noqa: F401

MODULES = (
    _core,
    key_errors,
    formatting,
    share_links,
    referral_bonus,
    gift_activation,
    payment_providers,
    states,
    menu,
    fulfillment,
    onboarding,
    profile_gifts,
    traffic_topup,
    lte_topup,
    main_reset,
    balance_topup,
    providers,
    payment_checks,
    topup_methods,
    referral,
    support,
    key_info,
    key_manage,
    key_view,
    howto,
    purchase,
    payment_create,
    gift_catcher,
    franchise,
)


def _link_namespace() -> None:
    """Копирует имена каждого модуля в соседние, где их нет."""
    for source in MODULES:
        for name in getattr(source, "__all__", ()):
            value = getattr(source, name)
            for target in MODULES:
                if target is source:
                    continue
                if name not in target.__dict__:
                    setattr(target, name, value)


def broadcast(name: str, value: object) -> None:
    """Разносит запись атрибута фасада по модулям, где это имя есть."""
    for target in MODULES:
        if name in target.__dict__:
            setattr(target, name, value)


_link_namespace()
