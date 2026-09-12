"""Общая платёжная обвязка: чек, цена, отправка сообщений и инвойсов, провайдеры.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


from shop_bot.data_manager.remnawave_repository import get_setting, get_user
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import LabeledPrice
from shop_bot.data_manager.remnawave_repository import create_payload_pending
import shop_bot.data_manager.remnawave_repository as rw_repo
from shop_bot.data_manager.database import get_seller_user
from decimal import Decimal


def _create_payload_pending_or_error(payment_id, user_id, amount, meta):
    """Создать pending; если слот промокода уже занят — вернуть ошибку для API."""
    try:
        ok = create_payload_pending(payment_id, user_id, amount, meta)
    except rw_repo.PromoUnavailableError as e:
        return {"ok": False, "error": rw_repo.promo_error_message(e.reason)}
    if not ok:
        return {"ok": False, "error": "Не удалось создать платёж"}
    return None


def _yookassa_receipt(item_description: str, price_str: str) -> dict | None:
    """Чек для платежа YooKassa или None, если почта для чеков не настроена.

    Магазину с включённой фискализацией (54-ФЗ) чек обязателен: без него
    создание платежа падает с `Receipt is missing or illegal`. Почта берётся
    из настройки `receipt_email` — той же, что использует бот. Если она не
    заполнена, чек не формируется: магазинам без фискализации он не нужен.

    `price_str` должен совпадать с `amount.value` самого платежа, иначе
    YooKassa отклонит чек как несогласованный с суммой.
    """
    customer_email = get_setting("receipt_email")
    if not customer_email or "@" not in str(customer_email):
        return None
    return {
        "customer": {"email": customer_email},
        "items": [{
            "description": item_description,
            "quantity": "1.00",
            "amount": {"value": price_str, "currency": "RUB"},
            "vat_code": "1",
            "payment_subject": "service",
            "payment_mode": "full_payment",
        }],
    }


def get_transaction_comment(user_data: dict, action_type: str, value: any, host_name: str | None = None) -> str:
    """Короткое человекочитаемое описание платежа — для поля description в
    ЮKassa/ЮMoney и подписи Stars-инвойса.

    Раньше здесь была попытка импортировать одноимённую функцию из
    `shop_bot.bot.handlers`, которой там никогда не было — это ломало ЛЮБУЮ
    оплату из webapp (ЮKassa/ЮMoney/Stars) с `ImportError`, тихо проглоченным
    общим `except Exception` в /api/create-payment. Теперь строка собирается
    здесь же, без зависимости от модуля бота.
    """
    try:
        months = int(value or 0)
    except (TypeError, ValueError):
        months = 0

    action_label = "Продление подписки" if action_type == "extend" else "Оплата подписки"
    duration = f"на {months} мес." if months else ""

    user_id = (user_data or {}).get("id")
    username = (user_data or {}).get("username")
    who = f"@{username}" if username else (f"#{user_id}" if user_id else "")

    parts = [action_label, duration]
    if host_name:
        parts.append(f"({host_name})")
    if who:
        parts.append(f"— {who}")
    return " ".join(p for p in parts if p)


def calculate_webapp_price(price: float, user_id: int) -> float:
    try:
        user = get_user(user_id)
        if not user: return price
        
        # 1. Seller Discount
        if user.get('seller_active'):
            seller = get_seller_user(user_id)
            if seller and seller.get('seller_sale'):
                discount_percent = float(seller['seller_sale'])
                price -= price * (discount_percent / 100)
        
        # 2. Referral Discount (First purchase)
        if user.get('referred_by') and user.get('total_spent', 0) == 0:
            ref_discount = get_setting("referral_discount")
            if ref_discount:
                try:
                    d_val = float(ref_discount)
                    if d_val > 0:
                        price -= price * (d_val / 100)
                except: pass
                
    except Exception as e:
        logger.error(f"Error calculating price: {e}")
        
    return round(price, 2)


async def notify_admin_of_purchase(bot: Bot, metadata: dict):
    from shop_bot.bot.handlers import notify_admin_of_purchase as bot_notify
    await bot_notify(bot, metadata)


async def process_successful_payment(bot: Bot, metadata: dict):
    from shop_bot.bot.handlers import process_successful_payment as bot_process
    return await bot_process(bot, metadata)


def _telegram_chat_exists(user_id: int) -> bool:
    """False, если чата с таким id в Telegram заведомо нет.

    Аккаунт, зарегистрированный по email, получает синтетический telegram_id
    (см. `is_email_only_user`) — бот в него писать не может, Telegram на любой
    запрос отвечает «chat not found». Так же поступает рассылка бота: она
    пропускает такие аккаунты до обращения к API (см. admin_router/mailing.py).
    """
    try:
        return not rw_repo.is_email_only_user(user_id)
    except Exception:
        return True


async def _send_telegram_message(user_id: int, text: str, reply_markup=None, photo=None):
    if not _telegram_chat_exists(user_id):
        return False
    token = get_setting("telegram_bot_token")
    if not token: return False
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        if photo:
            await bot.send_photo(chat_id=user_id, photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode="HTML")
        return True
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")
        return False
    finally:
        await bot.session.close()


async def _send_invoice_stars(user_id: int, title: str, description: str, payload: str, amount: int):
    token = get_setting("telegram_bot_token")
    if not token: return False
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="", 
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=amount)]
        )
        return True
    except Exception as e:
        logger.error(f"Error sending Stars invoice: {e}")
        return False
    finally:
        await bot.session.close()


from shop_bot.modules.platega_api import PlategaAPI
from shop_bot.modules.rollypay_api import RollyPayAPI
from shop_bot.bot.handlers import process_successful_payment


def _platega_api() -> PlategaAPI | None:
    mid = (get_setting("platega_merchant_id") or "").strip()
    secret = (get_setting("platega_secret") or "").strip()
    if not mid or not secret:
        return None
    return PlategaAPI(mid, secret, get_setting("platega_base_url"))


def _store_platega_transaction_id(payment_id, user_id, amount, meta, txid) -> None:
    if not txid:
        return
    meta2 = dict(meta or {})
    meta2["platega_transaction_id"] = str(txid)
    try:
        create_payload_pending(payment_id, user_id, amount, meta2)
    except Exception:
        logger.warning("Platega: не удалось сохранить provider_transaction_id для payment_id=%s", payment_id)


def _rollypay_is_enabled() -> bool:
    return bool(
        (get_setting("rollypay_api_key") or "").strip()
        and (get_setting("rollypay_signing_secret") or "").strip()
    )


def _rollypay_api() -> RollyPayAPI | None:
    key = (get_setting("rollypay_api_key") or "").strip()
    if not key:
        return None
    return RollyPayAPI(key, get_setting("rollypay_terminal_id") or "")


def _store_rollypay_payment_id(payment_id, user_id, amount, meta, provider_id) -> None:
    if not provider_id:
        return
    meta2 = dict(meta or {})
    meta2["rollypay_payment_id"] = str(provider_id)
    try:
        create_payload_pending(payment_id, user_id, amount, meta2)
    except Exception:
        logger.warning("RollyPay: не удалось сохранить provider payment_id для payment_id=%s", payment_id)


async def _fulfill_webapp_paid_order(metadata: dict) -> bool:
    token = (get_setting("telegram_bot_token") or "").strip()
    bot = None
    if token:
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    else:
        bot = object()
    try:
        return bool(await process_successful_payment(bot, metadata))
    finally:
        session = getattr(bot, "session", None)
        if session is not None:
            try:
                await session.close()
            except Exception:
                pass


from urllib.parse import urlencode


def _build_yoomoney_link(receiver: str, amount_rub: Decimal, label: str, description: str) -> str:
    base = "https://yoomoney.ru/quickpay/confirm.xml"
    params = {
        "receiver": (receiver or "").strip(),
        "quickpay-form": "donate",
        "targets": description[:50],
        "formcomment": description,
        "short-dest": description,
        "sum": f"{amount_rub:.2f}",
        "label": label,
        "successURL": f"https://t.me/{get_setting('telegram_bot_username')}",
    }
    return base + "?" + urlencode(params)


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_create_payload_pending_or_error",
    "_yookassa_receipt",
    "get_transaction_comment",
    "calculate_webapp_price",
    "notify_admin_of_purchase",
    "process_successful_payment",
    "_telegram_chat_exists",
    "_send_telegram_message",
    "_send_invoice_stars",
    "_platega_api",
    "_store_platega_transaction_id",
    "_rollypay_is_enabled",
    "_rollypay_api",
    "_store_rollypay_payment_id",
    "_fulfill_webapp_paid_order",
    "_build_yoomoney_link",
]
