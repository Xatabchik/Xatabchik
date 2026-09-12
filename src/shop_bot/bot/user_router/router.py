"""Сборка роутера пользовательской части бота.

Порядок вызовов register_* повторяет порядок определений в исходном
handlers.py и значим: aiogram проверяет хендлеры одного типа события в
порядке регистрации, поэтому перестановка блоков меняла бы, какой хендлер
поймает апдейт первым.
"""

from aiogram import Router

from .onboarding import register_onboarding
from .profile_gifts import register_profile_gifts
from .traffic_topup import register_traffic_topup
from .lte_topup import register_lte_topup
from .main_reset import register_main_reset
from .balance_topup import register_balance_topup
from .providers import register_providers
from .payment_checks import register_payment_checks
from .topup_methods import register_topup_methods
from .referral import register_referral
from .support import register_support
from .key_manage import register_key_manage
from .key_view import register_key_view
from .howto import register_howto
from .purchase import register_purchase
from .payment_create import register_payment_create
from .gift_catcher import register_gift_catcher
from .franchise import register_franchise

__all__ = ["get_user_router"]


def get_user_router() -> Router:
    user_router = Router()
    register_onboarding(user_router)
    register_profile_gifts(user_router)
    register_traffic_topup(user_router)
    register_lte_topup(user_router)
    register_main_reset(user_router)
    register_balance_topup(user_router)
    register_providers(user_router)
    register_payment_checks(user_router)
    register_topup_methods(user_router)
    register_referral(user_router)
    register_support(user_router)
    register_key_manage(user_router)
    register_key_view(user_router)
    register_howto(user_router)
    register_purchase(user_router)
    register_payment_create(user_router)
    register_gift_catcher(user_router)
    register_franchise(user_router)
    return user_router
