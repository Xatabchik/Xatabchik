"""Фасад Telegram Mini App: код разнесён по пакету `web_router`.

Модуль сохранён как единая точка входа, потому что на него ссылаются
`docker-compose.yml` (`uvicorn shop_bot.webapp.handlers:app`), `conftest.py` и
около двадцати пяти файлов тестов. Импорты ниже повторяют исходные, чтобы
`handlers.<имя>` продолжал работать для всего, что здесь было раньше.

Присваивание атрибута этому модулю извне рассылается по доменным модулям через
`_WebappHandlersFacade.__setattr__`: тесты подменяют `Bot`, `YookassaPayment`,
`get_setting`, `process_successful_payment`, `_send_telegram_message`,
`_send_invoice_stars`, `_rollypay_api` и три константы лимитов, и до разделения
такая запись была видна всем функциям файла.

Порядок маршрутов задаёт `web_router/__init__.py`; звёздочные импорты ниже
нужны только для ре-экспорта имён и на порядок не влияют — к этому моменту
модули уже в `sys.modules`, и повторный импорт ничего не исполняет.
"""
import sys as _sys
import types as _types

from typing import Any
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
import aiohttp
from shop_bot.data_manager.remnawave_repository import get_setting, get_user_keys, get_msk_time, get_webapp_settings, get_user, get_referral_count, get_all_hosts, list_squads, get_plans_for_host
import os
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
import html
import uuid
import asyncio
import time
import threading
from collections import deque
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, FSInputFile, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder
import json
import traceback
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from shop_bot.bot.keyboards import (
    create_payment_keyboard, 
    create_yoomoney_payment_keyboard, 
    create_cryptobot_payment_keyboard
)
from shop_bot.data_manager.remnawave_repository import (
    create_payload_pending, get_plan_by_id, get_pending_metadata,
    deduct_from_balance, check_transaction_exists, payment_owned_by_user, add_to_balance, log_transaction,
    add_to_referral_balance_all, add_to_referral_balance, deduct_from_referral_balance,
    get_referral_balance, get_balance, get_all_users, is_admin, update_user_stats,
    redeem_promo_code, update_promo_code_status, record_key_from_payload, get_key_by_id,
    update_key, get_key_by_email,
    list_referral_payout_methods, add_referral_payout_method, delete_referral_payout_method,
    get_referral_payout_method, get_pending_status,
)
import shop_bot.data_manager.remnawave_repository as rw_repo
from shop_bot.data_manager.database import (
    get_seller_user,
    get_device_tiers,
    get_host,
    format_next_traffic_reset_display,
    get_squad_by_class,
    should_account_lte_traffic,
    get_key_lte_state,
    resolve_lte_limit_bytes,
    get_traffic_packages_for_plan,
    get_traffic_package_by_id,
    squad_display_label,
)
from shop_bot.modules import remnawave_api
from shop_bot.config import get_purchase_success_text
import re
from decimal import Decimal, ROUND_HALF_UP
import logging
from urllib.parse import urlencode, quote
import hashlib
import hmac
from shop_bot.modules.platega_api import PlategaAPI
from shop_bot.modules.rollypay_api import RollyPayAPI
from shop_bot.modules.platega_fulfillment import (
    complete_pending_platega_payment,
    extract_platega_amount,
    is_platega_payment_method,
    mark_pending_canceled,
    normalize_platega_status,
    provider_transaction_id_from_meta,
)
from shop_bot.modules.heleket_api import create_heleket_payment_request
from shop_bot.bot.keyboards import (
    create_payment_keyboard, create_cryptobot_payment_keyboard,
    create_yoomoney_payment_keyboard
)
from shop_bot.bot.handlers import create_cryptobot_api_invoice, process_successful_payment
from yookassa import Configuration as YookassaConfiguration, Payment as YookassaPayment
from aiogram.types import BufferedInputFile
import io
import qrcode
from urllib.parse import urlencode

from shop_bot.webapp import web_router as _pkg

from shop_bot.webapp.web_router._core import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_common import *  # noqa: F401,F403
from shop_bot.webapp.web_router.auth_limits import *  # noqa: F401,F403
from shop_bot.webapp.web_router.auth_session import *  # noqa: F401,F403
from shop_bot.webapp.web_router.referral_settings import *  # noqa: F401,F403
from shop_bot.webapp.web_router._app import *  # noqa: F401,F403
from shop_bot.webapp.web_router.ticket_files_guard import *  # noqa: F401,F403
from shop_bot.webapp.web_router.referral_payouts import *  # noqa: F401,F403
from shop_bot.webapp.web_router.key_auto_renew import *  # noqa: F401,F403
from shop_bot.webapp.web_router.referral_withdrawals import *  # noqa: F401,F403
from shop_bot.webapp.web_router.render_keys import *  # noqa: F401,F403
from shop_bot.webapp.web_router.render_plans import *  # noqa: F401,F403
from shop_bot.webapp.web_router.render_page import *  # noqa: F401,F403
from shop_bot.webapp.web_router.models import *  # noqa: F401,F403
from shop_bot.webapp.web_router.auth_password import *  # noqa: F401,F403
from shop_bot.webapp.web_router.auth_telegram import *  # noqa: F401,F403
from shop_bot.webapp.web_router.auth_email import *  # noqa: F401,F403
from shop_bot.webapp.web_router.profile import *  # noqa: F401,F403
from shop_bot.webapp.web_router.account_sync import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_create import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_topup import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_lte import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_promo import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_check import *  # noqa: F401,F403
from shop_bot.webapp.web_router.payments_platega import *  # noqa: F401,F403
from shop_bot.webapp.web_router.referral_info import *  # noqa: F401,F403
from shop_bot.webapp.web_router.gifts import *  # noqa: F401,F403
from shop_bot.webapp.web_router.pending_actions import *  # noqa: F401,F403
from shop_bot.webapp.web_router.key_devices import *  # noqa: F401,F403
from shop_bot.webapp.web_router.support import *  # noqa: F401,F403
from shop_bot.webapp.web_router.key_actions import *  # noqa: F401,F403
from shop_bot.webapp.web_router.public_pages import *  # noqa: F401,F403


class _WebappHandlersFacade(_types.ModuleType):
    """Тип модуля-фасада, разносящий запись атрибута по доменным модулям.

    Присваивания в теле самого модуля сюда не попадают (они пишут в `__dict__`
    напрямую) — перехватывается только внешний `setattr`, то есть ровно то,
    чем пользуется `monkeypatch` в тестах.
    """

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        _pkg.broadcast(name, value)


_sys.modules[__name__].__class__ = _WebappHandlersFacade
