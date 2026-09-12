"""Группы состояний FSM для диалогов пользователя.
"""

import re
from aiogram.fsm.state import (
    State,
    StatesGroup,
)

__all__ = [
    "KeyPurchase",
    "Captcha",
    "Onboarding",
    "PaymentProcess",
    "TopUpProcess",
    "TrafficGbTopUp",
    "LteGbTopUp",
    "MainPoolReset",
    "SupportDialog",
    "TOKEN_RE",
    "FranchiseStates",
    "KeyManagement",
    "ReferralWithdraw",
]

class KeyPurchase(StatesGroup):
    waiting_for_host_selection = State()
    waiting_for_plan_selection = State()

class Captcha(StatesGroup):
    waiting_for_answer = State()

class Onboarding(StatesGroup):
    waiting_for_subscription_and_agreement = State()

class PaymentProcess(StatesGroup):
    waiting_for_email = State()
    waiting_for_payment_method = State()
    waiting_for_promo_code = State()
    waiting_for_stars_invoice = State()

 
class TopUpProcess(StatesGroup):
    waiting_for_amount = State()
    waiting_for_topup_method = State()


class TrafficGbTopUp(StatesGroup):
    waiting_for_package = State()
    waiting_for_method = State()


class LteGbTopUp(StatesGroup):
    waiting_for_package = State()
    waiting_for_method = State()


class MainPoolReset(StatesGroup):
    waiting_for_method = State()


class SupportDialog(StatesGroup):
    waiting_for_subject = State()
    waiting_for_message = State()
    waiting_for_reply = State()


# =============================
# Franchise (managed clone bots)
# =============================

TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")


class FranchiseStates(StatesGroup):
    waiting_bot_token = State()
    waiting_withdraw_amount = State()
    waiting_requisites_bank = State()
    waiting_requisites_value = State()


class KeyManagement(StatesGroup):
    waiting_for_rename = State()


class ReferralWithdraw(StatesGroup):
    waiting_method_type = State()
    waiting_method_bank = State()
    waiting_method_value = State()
    waiting_withdraw_choose_method = State()
    waiting_withdraw_amount = State()
    waiting_transfer_amount = State()
