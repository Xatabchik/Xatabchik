"""Mini App, разделённое из webapp/handlers.py.

Порядок импорта модулей ниже значим и повторяет порядок определений в
исходном файле: маршруты регистрируются декоратором `@app.…` в момент
импорта, а FastAPI выбирает первый совпавший маршрут в порядке регистрации.
`@app.get('/{path_param}')` в `public_pages` — catch-all, он обязан
остаться последним.

Порядок задаётся именно здесь и только здесь: Python исполняет `__init__`
родительского пакета раньше любого его подмодуля, поэтому прямой импорт
`web_router.support` сначала пройдёт по всему списку и получит тот же
порядок, что и запуск через фасад или uvicorn.

Модули пакета не импортируют имена друг у друга значением, кроме тех, что
нужны уже на этапе импорта (`app`, `limiter`, константы лимитов, модели
запросов) — их владельцы маршрутов не регистрируют. Всё остальное
раскладывает `_link_namespace()` после импорта всех модулей, а внешнюю
запись атрибута фасада разносит `broadcast()`.

PEP 562 (`__getattr__` модуля) здесь не помогает: обращение к глобальному
имени внутри функции компилируется в LOAD_GLOBAL и до `__getattr__` не
доходит.
"""

from shop_bot.webapp.web_router import _core  # noqa: F401
from shop_bot.webapp.web_router import payments_common  # noqa: F401
from shop_bot.webapp.web_router import auth_limits  # noqa: F401
from shop_bot.webapp.web_router import auth_session  # noqa: F401
from shop_bot.webapp.web_router import referral_settings  # noqa: F401
from shop_bot.webapp.web_router import _app  # noqa: F401
from shop_bot.webapp.web_router import ticket_files_guard  # noqa: F401
from shop_bot.webapp.web_router import referral_payouts  # noqa: F401
from shop_bot.webapp.web_router import key_auto_renew  # noqa: F401
from shop_bot.webapp.web_router import referral_withdrawals  # noqa: F401
from shop_bot.webapp.web_router import render_keys  # noqa: F401
from shop_bot.webapp.web_router import render_plans  # noqa: F401
from shop_bot.webapp.web_router import render_page  # noqa: F401
from shop_bot.webapp.web_router import models  # noqa: F401
from shop_bot.webapp.web_router import auth_password  # noqa: F401
from shop_bot.webapp.web_router import auth_telegram  # noqa: F401
from shop_bot.webapp.web_router import auth_email  # noqa: F401
from shop_bot.webapp.web_router import profile  # noqa: F401
from shop_bot.webapp.web_router import account_sync  # noqa: F401
from shop_bot.webapp.web_router import payments_create  # noqa: F401
from shop_bot.webapp.web_router import payments_topup  # noqa: F401
from shop_bot.webapp.web_router import payments_lte  # noqa: F401
from shop_bot.webapp.web_router import payments_promo  # noqa: F401
from shop_bot.webapp.web_router import payments_check  # noqa: F401
from shop_bot.webapp.web_router import payments_platega  # noqa: F401
from shop_bot.webapp.web_router import referral_info  # noqa: F401
from shop_bot.webapp.web_router import gifts  # noqa: F401
from shop_bot.webapp.web_router import pending_actions  # noqa: F401
from shop_bot.webapp.web_router import key_devices  # noqa: F401
from shop_bot.webapp.web_router import support  # noqa: F401
from shop_bot.webapp.web_router import key_actions  # noqa: F401
from shop_bot.webapp.web_router import public_pages  # noqa: F401

MODULES = (
    _core,
    payments_common,
    auth_limits,
    auth_session,
    referral_settings,
    _app,
    ticket_files_guard,
    referral_payouts,
    key_auto_renew,
    referral_withdrawals,
    render_keys,
    render_plans,
    render_page,
    models,
    auth_password,
    auth_telegram,
    auth_email,
    profile,
    account_sync,
    payments_create,
    payments_topup,
    payments_lte,
    payments_promo,
    payments_check,
    payments_platega,
    referral_info,
    gifts,
    pending_actions,
    key_devices,
    support,
    key_actions,
    public_pages,
)


def _link_namespace() -> None:
    """Раскладывает экспортируемые имена каждого модуля по остальным."""
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
