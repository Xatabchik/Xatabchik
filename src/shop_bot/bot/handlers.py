"""Фасад пользовательской части бота: код разнесён по пакету `user_router`.

Модуль сохранён как единая точка входа, потому что на него ссылаются
`bot_controller.py`, `admin_handlers.py`, `factory_bot/service.py` и тесты.
Импорты ниже повторяют исходные, чтобы `handlers.<имя>` продолжал работать для
всего, что здесь было раньше.

Присваивание атрибута этому модулю извне (`handlers.PAYMENT_METHODS = ...`,
`monkeypatch.setattr(handlers, "process_successful_payment", ...)`) рассылается
по доменным модулям через `_HandlersFacade.__setattr__` ниже: до разделения
такая запись была видна всем функциям файла, и это поведение сохранено.
"""
import sys as _sys
import types as _types

import logging
import os
import uuid
import math
import qrcode
import aiohttp
import re
import hashlib
import json
import base64
import asyncio
import time

from html import escape as html_escape

from urllib.parse import urlencode, quote
from hmac import compare_digest
from functools import wraps
from io import BytesIO
from yookassa import Payment, Configuration
from datetime import datetime, timedelta, timezone
from aiosend import CryptoPay, TESTNET
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from pytonconnect import TonConnect
from .callback_safety import fast_callback_answer, catch_callback_errors, handle_unknown_callback
from aiogram import Router, F, Bot, types, html
from aiogram.types import BufferedInputFile, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    add_to_balance,
    deduct_from_balance,
    get_setting,
    get_user,
    register_user_if_not_exists,
    get_next_key_number,
    create_payload_pending,
    cancel_pending_transaction,
    claim_processed_payment,
    unclaim_processed_payment,
    refund_payment_once,
    reset_pending_transaction,
    get_pending_status,
    get_pending_metadata,
    find_and_complete_pending_transaction,
    get_user_keys,
    get_balance,
    get_referral_count,
    get_plan_by_id,
    get_all_hosts,
    get_plans_for_host,
    get_active_plans_for_host,
    redeem_promo_code,
    reserve_promo_code,
    PromoUnavailableError,
    check_promo_code_available,
    promo_error_message,
    update_promo_code_status,
    record_key_from_payload,
    add_to_referral_balance_all,
    add_to_referral_balance,
    deduct_from_referral_balance,
    get_referral_balance_all,
    get_referral_balance,
    list_referral_payout_methods,
    add_referral_payout_method,
    delete_referral_payout_method,
    get_referral_payout_method,
    create_referral_withdrawal_request,
    list_referral_withdrawal_requests,
    get_referral_top_rich,
    get_referral_rank_and_count,
    get_all_users,
    set_terms_agreed,
    claim_referral_start_bonus,
    set_referral_trial_day_bonus_received,
    set_trial_used,
    set_key_auto_renew,
    set_all_keys_auto_renew_for_user,
    update_user_stats,
    log_transaction,
    is_admin,
)

from shop_bot.config import (
    get_profile_text,
    get_vpn_active_text,
    VPN_INACTIVE_TEXT,
    VPN_NO_DATA_TEXT,
    get_key_info_text,
    CHOOSE_PAYMENT_METHOD_MESSAGE,
    get_purchase_success_text
)
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.data_manager.captcha_utils import (
    create_captcha_challenge,
    check_captcha_answer,
    get_active_captcha_challenge,
    has_passed_captcha,
    mark_user_passed_captcha,
)
from shop_bot.factory_bot.runtime import get_service
from shop_bot.modules import remnawave_api
from shop_bot.data_manager.database import get_latest_pending_for_user, get_user_by_username
from shop_bot.data_manager.database import delete_key_by_id
from shop_bot.data_manager.database import _get_pending_metadata
from shop_bot.data_manager.database import get_franchise_min_withdraw, get_franchise_percent_default
from shop_bot.data_manager.database import log_utm_visit, set_user_utm_slug_if_absent

from shop_bot.bot import user_router as _pkg
from shop_bot.bot.user_router.router import get_user_router  # noqa: F401

from shop_bot.bot.user_router._core import *  # noqa: F401,F403
from shop_bot.bot.user_router.key_errors import *  # noqa: F401,F403
from shop_bot.bot.user_router.formatting import *  # noqa: F401,F403
from shop_bot.bot.user_router.share_links import *  # noqa: F401,F403
from shop_bot.bot.user_router.referral_bonus import *  # noqa: F401,F403
from shop_bot.bot.user_router.gift_activation import *  # noqa: F401,F403
from shop_bot.bot.user_router.payment_providers import *  # noqa: F401,F403
from shop_bot.bot.user_router.states import *  # noqa: F401,F403
from shop_bot.bot.user_router.menu import *  # noqa: F401,F403
from shop_bot.bot.user_router.fulfillment import *  # noqa: F401,F403
from shop_bot.bot.user_router.onboarding import *  # noqa: F401,F403
from shop_bot.bot.user_router.profile_gifts import *  # noqa: F401,F403
from shop_bot.bot.user_router.traffic_topup import *  # noqa: F401,F403
from shop_bot.bot.user_router.lte_topup import *  # noqa: F401,F403
from shop_bot.bot.user_router.main_reset import *  # noqa: F401,F403
from shop_bot.bot.user_router.balance_topup import *  # noqa: F401,F403
from shop_bot.bot.user_router.providers import *  # noqa: F401,F403
from shop_bot.bot.user_router.payment_checks import *  # noqa: F401,F403
from shop_bot.bot.user_router.topup_methods import *  # noqa: F401,F403
from shop_bot.bot.user_router.referral import *  # noqa: F401,F403
from shop_bot.bot.user_router.support import *  # noqa: F401,F403
from shop_bot.bot.user_router.key_info import *  # noqa: F401,F403
from shop_bot.bot.user_router.key_manage import *  # noqa: F401,F403
from shop_bot.bot.user_router.key_view import *  # noqa: F401,F403
from shop_bot.bot.user_router.howto import *  # noqa: F401,F403
from shop_bot.bot.user_router.purchase import *  # noqa: F401,F403
from shop_bot.bot.user_router.payment_create import *  # noqa: F401,F403
from shop_bot.bot.user_router.gift_catcher import *  # noqa: F401,F403
from shop_bot.bot.user_router.franchise import *  # noqa: F401,F403


class _HandlersFacade(_types.ModuleType):
    """Тип модуля-фасада, разносящий запись атрибута по доменным модулям.

    Присваивания в теле самого модуля сюда не попадают (они пишут в `__dict__`
    напрямую) — перехватывается только внешний `setattr`, то есть ровно то, чем
    пользуются `bot_controller` при старте и `monkeypatch` в тестах.
    """

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        _pkg.broadcast(name, value)


_sys.modules[__name__].__class__ = _HandlersFacade

# fallback for unknown callbacks
try:
    router.callback_query.register(handle_unknown_callback)
except Exception:
    pass
