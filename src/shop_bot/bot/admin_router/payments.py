"""Платёжные провайдеры: статус, карточка провайдера, правка полей.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import html as html_escape
import json

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.bot.callback_safety import fast_callback_answer
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_payments(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""




    # === Payments settings management ===

    class AdminPayments(StatesGroup):
        waiting_for_value = State()


    def _get_payments_status_for_admin() -> dict:
        yookassa_shop_id = (get_setting('yookassa_shop_id') or '').strip()
        yookassa_secret_key = (get_setting('yookassa_secret_key') or '').strip()
        yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)

        cryptobot_token = (get_setting('cryptobot_token') or '').strip()
        cryptobot_enabled = bool(cryptobot_token)

        heleket_merchant_id = (get_setting('heleket_merchant_id') or '').strip()
        heleket_api_key = (get_setting('heleket_api_key') or '').strip()
        heleket_enabled = bool(heleket_merchant_id and heleket_api_key)

        platega_merchant_id = (get_setting('platega_merchant_id') or '').strip()
        platega_secret = (get_setting('platega_secret') or '').strip()
        platega_enabled = bool(platega_merchant_id and platega_secret)

        ton_wallet_address = (get_setting('ton_wallet_address') or '').strip()
        tonapi_key = (get_setting('tonapi_key') or '').strip()
        tonconnect_enabled = bool(ton_wallet_address and tonapi_key)

        yoomoney_enabled = _is_true(get_setting('yoomoney_enabled') or 'false')
        yoomoney_wallet = (get_setting('yoomoney_wallet') or '').strip()
        yoomoney_secret = (get_setting('yoomoney_secret') or '').strip()
        yoomoney_ready = bool(yoomoney_wallet and yoomoney_secret)
        yoomoney_active = bool(yoomoney_enabled and yoomoney_ready)

        stars_enabled = _is_true(get_setting('stars_enabled') or 'false')
        try:
            stars_ratio = float(str(get_setting('stars_per_rub') or '0').replace(',', '.'))
        except Exception:
            stars_ratio = 0.0
        stars_active = bool(stars_enabled and stars_ratio > 0)

        return {
            'yookassa': yookassa_enabled,
            'cryptobot': cryptobot_enabled,
            'heleket': heleket_enabled,
            'platega': platega_enabled,
            'tonconnect': tonconnect_enabled,
            'yoomoney': yoomoney_active,
            'stars': stars_active,
        }


    async def show_admin_payments_menu(message: types.Message, *, edit_message: bool = False):
        status = _get_payments_status_for_admin()
        text = "💳 <b>Платежки</b>\n\nВыберите платежную систему для настройки:" 
        kb = keyboards.create_admin_payments_menu_keyboard(status)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    def _payment_detail_text(provider: str) -> tuple[str, dict]:
        provider = (provider or '').strip().lower()
        flags: dict = {}
        if provider == 'yookassa':
            receipt_email = (get_setting('receipt_email') or '').strip()
            shop_id = (get_setting('yookassa_shop_id') or '').strip()
            secret_key = (get_setting('yookassa_secret_key') or '').strip()
            sbp_enabled = _is_true(get_setting('sbp_enabled') or 'false')
            flags['sbp_enabled'] = sbp_enabled
            active = bool(shop_id and secret_key)
            text = (
                "💳 <b>YooKassa</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Почта для чеков: <code>{html_escape.escape(receipt_email) if receipt_email else '—'}</code>\n"
                f"Shop ID: <code>{html_escape.escape(shop_id) if shop_id else '—'}</code>\n"
                f"Secret Key: <code>{_mask_secret(secret_key)}</code>\n"
                f"СБП: <b>{'включено' if sbp_enabled else 'выключено'}</b>"
            )
            return text, flags

        if provider == 'cryptobot':
            token = (get_setting('cryptobot_token') or '').strip()
            active = bool(token)
            text = (
                "💳 <b>CryptoBot</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Token: <code>{_mask_secret(token)}</code>"
            )
            return text, flags

        if provider == 'heleket':
            merchant_id = (get_setting('heleket_merchant_id') or '').strip()
            api_key = (get_setting('heleket_api_key') or '').strip()
            domain = (get_setting('domain') or '').strip()
            active = bool(merchant_id and api_key)
            text = (
                "💳 <b>Heleket</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Merchant ID: <code>{html_escape.escape(merchant_id) if merchant_id else '—'}</code>\n"
                f"API Key: <code>{_mask_secret(api_key)}</code>\n"
                f"Домен: <code>{html_escape.escape(domain) if domain else '—'}</code>"
            )
            return text, flags


        if provider == 'platega':
            base_url = (get_setting('platega_base_url') or 'https://app.platega.io').strip()
            merchant_id = (get_setting('platega_merchant_id') or '').strip()
            secret = (get_setting('platega_secret') or '').strip()
            methods = (get_setting('platega_active_methods') or '').strip()
            active = bool(merchant_id and secret)
            text = (
                "💳 <b>Platega</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Base URL: <code>{html_escape.escape(base_url) if base_url else '—'}</code>\n"
                f"Merchant ID: <code>{html_escape.escape(merchant_id) if merchant_id else '—'}</code>\n"
                f"Secret: <code>{_mask_secret(secret)}</code>\n"
                f"Методы: <code>{html_escape.escape(methods) if methods else '—'}</code>"
            )
            return text, flags

        if provider == 'tonconnect':
            wallet = (get_setting('ton_wallet_address') or '').strip()
            tonapi_key = (get_setting('tonapi_key') or '').strip()
            active = bool(wallet and tonapi_key)
            text = (
                "💳 <b>TonConnect</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Ton Wallet: <code>{html_escape.escape(wallet) if wallet else '—'}</code>\n"
                f"TonAPI Key: <code>{_mask_secret(tonapi_key)}</code>"
            )
            return text, flags

        if provider == 'stars':
            enabled = _is_true(get_setting('stars_enabled') or 'false')
            flags['stars_enabled'] = enabled
            try:
                ratio = float(str(get_setting('stars_per_rub') or '0').replace(',', '.'))
            except Exception:
                ratio = 0.0
            active = bool(enabled and ratio > 0)
            text = (
                "💳 <b>Telegram Stars</b>\n\n"
                f"Включено: <b>{'да' if enabled else 'нет'}</b>\n"
                f"Коэффициент: <code>{ratio:g}</code> (⭐ за 1 RUB)\n"
                f"Статус: {'🟢 Активно' if active else '🔴 Не активно'}"
            )
            return text, flags

        if provider == 'yoomoney':
            enabled = _is_true(get_setting('yoomoney_enabled') or 'false')
            flags['yoomoney_enabled'] = enabled
            wallet = (get_setting('yoomoney_wallet') or '').strip()
            secret = (get_setting('yoomoney_secret') or '').strip()
            api_token = (get_setting('yoomoney_api_token') or '').strip()
            client_id = (get_setting('yoomoney_client_id') or '').strip()
            client_secret = (get_setting('yoomoney_client_secret') or '').strip()
            redirect_uri = (get_setting('yoomoney_redirect_uri') or '').strip()
            ready = bool(wallet and secret)
            active = bool(enabled and ready)
            text = (
                "💳 <b>YooMoney</b>\n\n"
                f"Включено: <b>{'да' if enabled else 'нет'}</b>\n"
                f"Статус: {'🟢 Активно' if active else '🔴 Не активно'}\n\n"
                f"Кошелёк: <code>{html_escape.escape(wallet) if wallet else '—'}</code>\n"
                f"Секрет уведомлений: <code>{_mask_secret(secret)}</code>\n"
                f"API Token: <code>{_mask_secret(api_token)}</code>\n"
                f"client_id: <code>{html_escape.escape(client_id) if client_id else '—'}</code>\n"
                f"client_secret: <code>{_mask_secret(client_secret)}</code>\n"
                f"redirect_uri: <code>{html_escape.escape(redirect_uri) if redirect_uri else '—'}</code>"
            )
            return text, flags

        return "💳 <b>Платежки</b>\n\nНеизвестная платежная система.", flags


    async def show_admin_payment_detail(message: types.Message, provider: str, *, edit_message: bool = False):
        text, flags = _payment_detail_text(provider)
        kb = keyboards.create_admin_payment_detail_keyboard(provider, flags=flags)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_payments_menu")
    async def admin_payments_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        await state.clear()
        await show_admin_payments_menu(callback.message, edit_message=True)


    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_payments_open:"))
    async def admin_payments_open(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        provider = callback.data.split("admin_payments_open:", 1)[-1].strip()
        await state.clear()
        await state.update_data(payments_provider=provider)
        await show_admin_payment_detail(callback.message, provider, edit_message=True)


    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_payments_toggle:"))
    async def admin_payments_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        what = callback.data.split("admin_payments_toggle:", 1)[-1].strip()
        if what == 'sbp':
            cur = _is_true(get_setting('sbp_enabled') or 'false')
            rw_repo.update_setting('sbp_enabled', 'false' if cur else 'true')
            provider = 'yookassa'
        elif what == 'stars':
            cur = _is_true(get_setting('stars_enabled') or 'false')
            rw_repo.update_setting('stars_enabled', 'false' if cur else 'true')
            provider = 'stars'
        elif what == 'yoomoney':
            cur = _is_true(get_setting('yoomoney_enabled') or 'false')
            rw_repo.update_setting('yoomoney_enabled', 'false' if cur else 'true')
            provider = 'yoomoney'
        else:
            provider = (await state.get_data()).get('payments_provider') or 'yookassa'
        await show_admin_payment_detail(callback.message, provider, edit_message=True)


    _PAYMENT_FIELD_MAP = {
        # provider -> field -> setting key
        ('yookassa', 'receipt_email'): 'receipt_email',
        ('yookassa', 'shop_id'): 'yookassa_shop_id',
        ('yookassa', 'secret_key'): 'yookassa_secret_key',
        ('cryptobot', 'token'): 'cryptobot_token',
        ('heleket', 'merchant_id'): 'heleket_merchant_id',
        ('heleket', 'api_key'): 'heleket_api_key',
        ('heleket', 'domain'): 'domain',
        ('platega', 'base_url'): 'platega_base_url',
        ('platega', 'merchant_id'): 'platega_merchant_id',
        ('platega', 'secret'): 'platega_secret',
        ('platega', 'active_methods'): 'platega_active_methods',
        ('tonconnect', 'wallet'): 'ton_wallet_address',
        ('tonconnect', 'tonapi'): 'tonapi_key',
        ('stars', 'ratio'): 'stars_per_rub',
        ('yoomoney', 'wallet'): 'yoomoney_wallet',
        ('yoomoney', 'secret'): 'yoomoney_secret',
        ('yoomoney', 'api_token'): 'yoomoney_api_token',
        ('yoomoney', 'client_id'): 'yoomoney_client_id',
        ('yoomoney', 'client_secret'): 'yoomoney_client_secret',
        ('yoomoney', 'redirect_uri'): 'yoomoney_redirect_uri',
    }


    def _payment_prompt(provider: str, field: str) -> str:
        if provider == 'yookassa' and field == 'receipt_email':
            return "Введите почту для чеков (receipt_email) или '-' чтобы очистить:"
        if provider == 'yookassa' and field == 'shop_id':
            return "Введите YooKassa Shop ID или '-' чтобы очистить:"
        if provider == 'yookassa' and field == 'secret_key':
            return "Введите YooKassa Secret Key или '-' чтобы очистить:"
        if provider == 'cryptobot':
            return "Введите CryptoBot Token или '-' чтобы очистить:"
        if provider == 'heleket' and field == 'merchant_id':
            return "Введите Heleket Merchant ID или '-' чтобы очистить:"
        if provider == 'heleket' and field == 'api_key':
            return "Введите Heleket API Key или '-' чтобы очистить:"
        if provider == 'heleket' and field == 'domain':
            return "Введите домен (например my-shop.com) или '-' чтобы очистить:"
        if provider == 'platega' and field == 'base_url':
            return "Введите Platega Base URL (например https://app.platega.io) или '-' чтобы очистить:"
        if provider == 'platega' and field == 'merchant_id':
            return "Введите Platega Merchant ID или '-' чтобы очистить:"
        if provider == 'platega' and field == 'secret':
            return "Введите Platega Secret или '-' чтобы очистить:"
        if provider == 'platega' and field == 'active_methods':
            return "Введите коды методов Platega через запятую (например 2,10,11,12,13) или '-' чтобы очистить:"
        if provider == 'tonconnect' and field == 'wallet':
            return "Введите Ton Wallet address или '-' чтобы очистить:"
        if provider == 'tonconnect' and field == 'tonapi':
            return "Введите TonAPI Key или '-' чтобы очистить:"
        if provider == 'stars' and field == 'ratio':
            return "Введите коэффициент ⭐ за 1 RUB (например 1.0). 0 — отключит оплату звездами:"
        if provider == 'yoomoney' and field == 'wallet':
            return "Введите номер кошелька YooMoney или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'secret':
            return "Введите секрет HTTP-уведомлений YooMoney или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'api_token':
            return "Введите YooMoney API Token (OAuth access_token) или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'client_id':
            return "Введите YooMoney client_id или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'client_secret':
            return "Введите YooMoney client_secret или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'redirect_uri':
            return "Введите redirect_uri для OAuth или '-' чтобы очистить:"
        return "Введите значение или '-' чтобы очистить:"


    def _normalize_payment_input(value: str) -> str:
        raw = (value or '').strip()
        if raw in {'-', '—', 'clear', 'clr', 'нет'}:
            return ''
        return raw


    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_payments_set:"))
    async def admin_payments_set(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        try:
            _, provider, field = callback.data.split(":", 2)
        except Exception:
            await callback.answer("Некорректная команда", show_alert=True)
            return
        provider = provider.strip()
        field = field.strip()
        setting_key = _PAYMENT_FIELD_MAP.get((provider, field))
        if not setting_key:
            await callback.answer("Неизвестный параметр", show_alert=True)
            return
        await state.set_state(AdminPayments.waiting_for_value)
        await state.update_data(payments_provider=provider, payments_field=field, payments_key=setting_key)
        await callback.message.answer(
            "✏️ <b>Платежки</b>\n\n" + _payment_prompt(provider, field),
            parse_mode="HTML",
            reply_markup=keyboards.create_admin_payments_cancel_keyboard(f"admin_payments_open:{provider}"),
        )


    @admin_router.message(AdminPayments.waiting_for_value)
    async def admin_payments_set_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        provider = (data.get('payments_provider') or '').strip().lower()
        field = (data.get('payments_field') or '').strip().lower()
        setting_key = (data.get('payments_key') or '').strip()
        if not provider or not field or not setting_key:
            await state.clear()
            await show_admin_payments_menu(message, edit_message=False)
            return

        raw = message.text or ''
        value = _normalize_payment_input(raw)

        # validators
        if (provider, field) == ('stars', 'ratio'):
            try:
                rr = float(value.replace(',', '.')) if value else 0.0
            except Exception:
                await message.answer("❌ Введите число, например 1.0")
                return
            if rr < 0 or rr > 1000:
                await message.answer("❌ Некорректное значение. Допустимо 0..1000")
                return
            value = str(rr)

        # save
        try:
            rw_repo.update_setting(setting_key, value)
        except Exception as e:
            logger.error(f"Не удалось обновить настройку {setting_key}: {e}", exc_info=True)
            await message.answer("❌ Не удалось сохранить настройку")
            return

        await state.clear()
        await message.answer("✅ Сохранено.")
        await show_admin_payment_detail(message, provider, edit_message=False)


    @admin_router.callback_query(F.data == "admin_payments_yoomoney_check")
    async def admin_payments_yoomoney_check(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        token = (get_setting('yoomoney_api_token') or '').strip()
        if not token:
            await callback.message.answer("YooMoney: токен не задан.")
            await show_admin_payment_detail(callback.message, 'yoomoney', edit_message=False)
            return

        import aiohttp
        ok = False
        account = None
        err = None
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post('https://yoomoney.ru/api/account-info', headers={'Authorization': f'Bearer {token}'}) as resp:
                    text = await resp.text()
                    status = resp.status
                if status != 200:
                    err = f"account-info HTTP {status}."
                else:
                    try:
                        data = json.loads(text)
                    except Exception:
                        data = {}
                    account = data.get('account') or data.get('account_number')
                    ok = True
        except Exception as e:
            err = str(e)

        if ok:
            await callback.message.answer(f"✅ YooMoney: токен валиден. Кошелёк: {account or '—'}")
        else:
            await callback.message.answer(f"❌ YooMoney: ошибка проверки токена: {err}")

        await show_admin_payment_detail(callback.message, 'yoomoney', edit_message=False)
