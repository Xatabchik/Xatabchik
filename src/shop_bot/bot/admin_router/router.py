"""Сборка admin_router: создание роутера и регистрация блоков.

Порядок вызовов register_* повторяет порядок определений в бывшем
bot/admin_handlers.py: в aiogram хендлеры одного типа события проверяются
в порядке регистрации, поэтому переставлять их нельзя.

`IsAdminFilter` и `AdminAccessMiddleware` сюда не импортируются значением,
а приходят из пакета через _link_namespace(). До разделения фабрика читала
их из namespace модуля в момент вызова, и подмена атрибута на
`admin_handlers` была видна — это поведение сохранено.
"""

from aiogram import Router

from shop_bot.bot.admin_router.menu import register_menu_1
from shop_bot.bot.admin_router.modules import register_modules
from shop_bot.bot.admin_router.button_constructor import register_button_constructor
from shop_bot.bot.admin_router.payments import register_payments
from shop_bot.bot.admin_router.referral import register_referral
from shop_bot.bot.admin_router.franchise import register_franchise
from shop_bot.bot.admin_router.hosts import register_hosts
from shop_bot.bot.admin_router.trial import register_trial
from shop_bot.bot.admin_router.lte_settings import register_lte_settings
from shop_bot.bot.admin_router.notifications import register_notifications
from shop_bot.bot.admin_router.plans import register_plans
from shop_bot.bot.admin_router.promo import register_promo
from shop_bot.bot.admin_router.speedtest import register_speedtest_1
from shop_bot.bot.admin_router.backup import register_backup
from shop_bot.bot.admin_router.speedtest import register_speedtest_2
from shop_bot.bot.admin_router.users import register_users_1
from shop_bot.bot.admin_router.admins import register_admins_1
from shop_bot.bot.admin_router.users import register_users_2
from shop_bot.bot.admin_router.keys import register_keys_1
from shop_bot.bot.admin_router.admins import register_admins_2
from shop_bot.bot.admin_router.keys import register_keys_2
from shop_bot.bot.admin_router.gifts import register_gifts
from shop_bot.bot.admin_router.balance import register_balance_1
from shop_bot.bot.admin_router.keys import register_keys_3
from shop_bot.bot.admin_router.menu import register_menu_2
from shop_bot.bot.admin_router.balance import register_balance_2
from shop_bot.bot.admin_router.host_keys import register_host_keys
from shop_bot.bot.admin_router.key_quick_ops import register_key_quick_ops
from shop_bot.bot.admin_router.mailing import register_mailing
from shop_bot.bot.admin_router.withdrawals import register_withdrawals
from shop_bot.bot.admin_router.monitor import register_monitor
from shop_bot.bot.admin_router.captcha import register_captcha
from shop_bot.bot.admin_router.auto_renew import register_auto_renew

__all__ = ["get_admin_router"]


def get_admin_router() -> Router:
    admin_router = Router(name="admin_router")
    admin_router.message.filter(IsAdminFilter())
    admin_router.callback_query.filter(IsAdminFilter())
    admin_router.message.outer_middleware(AdminAccessMiddleware())
    admin_router.callback_query.outer_middleware(AdminAccessMiddleware())
    register_menu_1(admin_router)
    register_modules(admin_router)
    register_button_constructor(admin_router)
    register_payments(admin_router)
    register_referral(admin_router)
    register_franchise(admin_router)
    register_hosts(admin_router)
    register_trial(admin_router)
    register_lte_settings(admin_router)
    register_notifications(admin_router)
    register_plans(admin_router)
    register_promo(admin_router)
    register_speedtest_1(admin_router)
    register_backup(admin_router)
    register_speedtest_2(admin_router)
    register_users_1(admin_router)
    register_admins_1(admin_router)
    register_users_2(admin_router)
    register_keys_1(admin_router)
    register_admins_2(admin_router)
    register_keys_2(admin_router)
    register_gifts(admin_router)
    register_balance_1(admin_router)
    register_keys_3(admin_router)
    register_menu_2(admin_router)
    register_balance_2(admin_router)
    register_host_keys(admin_router)
    register_key_quick_ops(admin_router)
    register_mailing(admin_router)
    register_withdrawals(admin_router)
    register_monitor(admin_router)
    register_captcha(admin_router)
    register_auto_renew(admin_router)

    return admin_router
