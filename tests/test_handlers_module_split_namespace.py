"""Инварианты разделения bot/handlers.py на пакет bot/user_router/.

До разделения handlers.py был одним пространством имён, и на этом держались две
вещи, которые легко потерять при переносе кода:

  1. Запись атрибута извне. `bot_controller.py` после старта пишет
     `handlers.PAYMENT_METHODS`, `handlers.TELEGRAM_BOT_USERNAME` и
     `handlers.ADMIN_ID`, а тесты подменяют `handlers.process_successful_payment`
     и `handlers.deduct_from_balance`. В едином файле это видели все функции;
     после разделения значение обязано дойти до каждого доменного модуля, иначе
     бот молча берёт устаревшее (например, None вместо способов оплаты).

  2. Порядок регистрации хендлеров. aiogram проверяет хендлеры одного типа
     события в порядке регистрации, поэтому перестановка блоков меняет то, какой
     хендлер поймает апдейт первым. Особенно это важно для хендлеров-ловушек,
     принимающих любой ввод.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from conftest import temp_db  # noqa: F401

PKG_DIR = Path("src/shop_bot/bot/user_router")

# Имена, которые записывает извне bot_controller.py, и модули, читающие их.
BROADCAST_READERS = {
    "PAYMENT_METHODS": ("traffic_topup", "lte_topup", "main_reset", "balance_topup"),
    "TELEGRAM_BOT_USERNAME": (
        "share_links", "traffic_topup", "lte_topup", "main_reset", "balance_topup",
        "providers", "payment_create", "fulfillment",
    ),
    # Читателей внутри пакета нет, но запись обязана приниматься без ошибки.
    "ADMIN_ID": (),
}

# Имена, подменяемые в тестах, и модули, откуда их вызывают.
PATCH_READERS = {
    "process_successful_payment": (
        "traffic_topup", "lte_topup", "main_reset", "balance_topup",
        "payment_checks", "payment_create",
    ),
    "deduct_from_balance": ("traffic_topup", "lte_topup", "main_reset", "payment_create"),
}

MUTABLE_GLOBALS = ("PAYMENT_METHODS", "TELEGRAM_BOT_USERNAME", "ADMIN_ID", "PENDING_GIFTS")


def _handlers():
    from shop_bot.bot import handlers

    return handlers


def _module(name: str):
    from shop_bot.bot import user_router

    return getattr(user_router, name)


def test_facade_reexports_every_public_name():
    """`handlers.<имя>` должен работать для всего, что было в файле до разделения."""
    from shop_bot.bot import user_router

    handlers = _handlers()
    missing = []
    for mod in user_router.MODULES:
        for name in getattr(mod, "__all__", ()):
            if not hasattr(handlers, name):
                missing.append(f"{mod.__name__}.{name}")
            elif getattr(handlers, name) is not getattr(mod, name):
                missing.append(f"{mod.__name__}.{name} (другой объект)")
    assert missing == [], "фасад не переэкспортирует: " + ", ".join(missing)


def test_get_user_router_is_importable_from_facade():
    """`from shop_bot.bot.handlers import get_user_router` — публичный вход бота."""
    from shop_bot.bot.handlers import get_user_router
    from shop_bot.bot.user_router.router import get_user_router as packaged

    assert get_user_router is packaged


@pytest.mark.parametrize("name, readers", sorted(BROADCAST_READERS.items()))
def test_external_write_reaches_every_reader(name, readers):
    """Так значение проставляет bot_controller.py при запуске бота."""
    handlers = _handlers()
    sentinel = object()
    previous = getattr(handlers, name)
    try:
        setattr(handlers, name, sentinel)
        for reader in readers:
            assert getattr(_module(reader), name) is sentinel, (
                f"{reader} не увидел новое значение {name}"
            )
    finally:
        setattr(handlers, name, previous)
    for reader in readers:
        assert getattr(_module(reader), name) is previous


@pytest.mark.parametrize("name, readers", sorted(PATCH_READERS.items()))
def test_monkeypatch_reaches_internal_callers(name, readers):
    """Подмена через monkeypatch.setattr(handlers, ...) и откат после теста."""
    handlers = _handlers()
    original = getattr(handlers, name)
    stub = object()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(handlers, name, stub)
        for reader in readers:
            assert getattr(_module(reader), name) is stub, f"{reader} вызовет не подменённое {name}"
    assert getattr(handlers, name) is original
    for reader in readers:
        assert getattr(_module(reader), name) is original, f"{reader} остался с подменой {name}"


def test_pending_gifts_is_one_shared_dict():
    """Словарь меняют по месту, поэтому объект обязан быть один на весь пакет."""
    handlers = _handlers()
    catcher = _module("gift_catcher")
    assert handlers.PENDING_GIFTS is catcher.PENDING_GIFTS
    handlers.PENDING_GIFTS[-1] = {"probe": True}
    try:
        assert catcher.PENDING_GIFTS[-1] == {"probe": True}
    finally:
        handlers.PENDING_GIFTS.pop(-1, None)


def test_logger_name_unchanged():
    """Записи в логах должны остаться от 'shop_bot.bot.handlers', как до разделения."""
    assert _handlers().logger.name == "shop_bot.bot.handlers"


@pytest.mark.parametrize("path", sorted(PKG_DIR.glob("*.py")), ids=lambda p: p.name)
def test_no_module_imports_mutable_global_as_value(path):
    """Изменяемые глобальные нельзя импортировать значением: копия не обновится.

    `from ._core import PAYMENT_METHODS` сохранил бы None на момент импорта, и
    запись `handlers.PAYMENT_METHODS = ...` из bot_controller до этого модуля уже
    не дошла бы — клавиатура способов оплаты собиралась бы из пустого значения.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = [
        f"{path.name}:{node.lineno} from {'.' * node.level}{node.module or ''} import {alias.name}"
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in MUTABLE_GLOBALS
    ]
    assert bad == [], "импорт изменяемой глобальной значением:\n" + "\n".join(bad)


def _router_handlers(observer: str):
    from shop_bot.bot.handlers import get_user_router

    router = get_user_router()
    return [
        getattr(h.callback, "__name__", repr(h.callback))
        for h in router.observers[observer].handlers
    ]


def test_registered_handler_counts(temp_db):
    """Число зарегистрированных хендлеров на каждый тип события."""
    assert len(_router_handlers("message")) == 22
    assert len(_router_handlers("callback_query")) == 135
    assert len(_router_handlers("pre_checkout_query")) == 1


def test_gift_username_catcher_registered_after_overlapping_handlers(temp_db):
    """Ловушка текста без состояния FSM обязана стоять после пересекающихся с ней.

    Фильтр `_gift_username_catcher` — `StateFilter(None), F.text`, поэтому в
    состоянии None он пересекается с теми message-хендлерами, у которых фильтра
    по состоянию нет вовсе: кнопкой «Главное меню» и сообщениями в теме форума.
    Зарегистрируй ловушку раньше них — и она начнёт съедать их апдейты.

    С хендлерами, у которых задано конкретное состояние, пересечения нет, и их
    взаимный порядок с ловушкой на поведение не влияет — поэтому тест проверяет
    не всю последовательность, а именно пересекающиеся пары.
    """
    messages = _router_handlers("message")
    catcher = messages.index("_gift_username_catcher")
    for name in ("main_menu_handler", "forum_thread_message_handler"):
        assert messages.index(name) < catcher, f"{name} зарегистрирован позже ловушки текста"


def test_stale_payment_callback_registered_after_real_ones(temp_db):
    """Заглушка устаревших pay_*-кнопок стоит после настоящих обработчиков оплаты.

    Её фильтр перечисляет те же callback_data, что и рабочие хендлеры, так что
    при регистрации раньше них оплата перестала бы работать совсем.
    """
    callbacks = _router_handlers("callback_query")
    stale = callbacks.index("stale_payment_method_callback")
    for name in ("pay_with_main_balance_handler", "create_yookassa_payment_handler",
                 "pay_platega_handler", "pay_rollypay_handler"):
        assert callbacks.index(name) < stale, f"{name} зарегистрирован позже заглушки"
