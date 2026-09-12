"""Фасад административной части бота: код разнесён по пакету `admin_router`.

Модуль сохранён как единая точка входа, потому что на него ссылаются
`bot_controller.py` и тесты (`tests/test_admin_router_authorization.py`).
Импорты ниже повторяют исходные, чтобы `admin_handlers.<имя>` продолжал
работать для всего, что здесь было раньше.

Присваивание атрибута этому модулю извне
(`monkeypatch.setattr(admin_handlers, "get_admin_stats", ...)`) рассылается по
доменным модулям через `_AdminHandlersFacade.__setattr__` ниже: до разделения
такая запись была видна всем функциям файла, и это поведение сохранено.
"""
import sys as _sys
import types as _types

import logging
import asyncio
import time
import uuid
import re
import html as html_escape
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Router, F, types, BaseMiddleware
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.bot.callback_safety import fast_callback_answer, catch_callback_errors
from shop_bot.modules import telegram_reachability
from shop_bot.data_manager import speedtest_runner
from shop_bot.data_manager import resource_monitor
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.data_manager.remnawave_repository import (
    get_all_users,
    get_setting,
    get_user,
    get_keys_for_user,
    create_gift_key,
    get_all_hosts,
    get_all_ssh_targets,
    add_to_balance,
    deduct_from_balance,
    ban_user,
    unban_user,
    delete_key_by_email,
    get_admin_stats,
    get_keys_for_host,
    is_admin,
    get_referral_count,
    get_referral_balance_all,
    get_referrals_for_user,
    create_promo_code,
    list_promo_codes,
    update_promo_code_status,
    # hosts
    create_host,
    delete_host,
    get_host,
    update_host_url,
    update_host_name,
    update_host_subscription_url,
    update_host_remnawave_settings,
    update_host_ssh_settings,
    get_host_squads,
    add_host_squad,
    set_host_squad_active,
    delete_host_squad,
)
from shop_bot.data_manager.database import (
    update_key_email,
    set_balance,
    set_referral_balance,
    set_referral_balance_all,
    delete_user_completely,
    create_plan,
    get_plans_for_host,
    get_plan_by_id,
    update_plan,
    update_plan_metadata,
    delete_plan,
    set_plan_active,

    # traffic packages (докупка ГБ)
    create_traffic_package,
    get_traffic_packages_for_plan,
    get_traffic_package_by_id,
    update_traffic_package,
    delete_traffic_package,

    # Button constructor (dynamic keyboards)
    get_button_configs_admin,
    get_button_config_by_db_id,
    create_button_config,
    update_button_config,
    delete_button_config,
)
from shop_bot.data_manager import backup_manager
from shop_bot.bot.handlers import show_main_menu
from shop_bot.webhook_server.app import franchise_settings, toggle_franchise_settings
from shop_bot.modules import remnawave_api
from shop_bot.modules.remnawave_api import create_or_update_key_on_host, delete_client_on_host
from shop_bot.core.module_loader import get_global_module_loader

from shop_bot.bot import admin_router as _pkg
from shop_bot.bot.admin_router.core import (
    AdminAccessMiddleware,
    AdminModules,
    AdminSettings,
    Broadcast,
    IsAdminFilter,
    _is_true,
    _mask_secret,
    logger,
)
from shop_bot.bot.admin_router.router import get_admin_router  # noqa: F401


class _AdminHandlersFacade(_types.ModuleType):
    """Тип модуля-фасада, разносящий запись атрибута по доменным модулям.

    Присваивания в теле самого модуля сюда не попадают (они пишут в `__dict__`
    напрямую) — перехватывается только внешний `setattr`, то есть ровно то,
    чем пользуется `monkeypatch` в тестах.
    """

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        _pkg.broadcast(name, value)


_sys.modules[__name__].__class__ = _AdminHandlersFacade
