"""Разбор и последствия ошибок выдачи ключа: классификация, логи,
уведомления администраторов и пользователя, откат неоплаченной выдачи.
"""

import re
from datetime import datetime
from aiogram import (
    Bot,
    types,
)
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import refund_payment_once
from shop_bot.data_manager import remnawave_repository as rw_repo

__all__ = [
    "_classify_key_creation_error",
    "_format_key_action_label",
    "_log_key_creation_error",
    "_notify_admins_key_creation_error",
    "_notify_user_key_creation_error",
    "_handle_key_creation_failure",
    "_abort_topup_fulfillment",
    "_notify_admins_topup_desync",
    "_abort_key_fulfillment",
    "_safe_edit_or_answer",
]

def _classify_key_creation_error(exc: Exception | None) -> tuple[str, str, str]:
    raw = str(exc) if exc else ""
    status = None
    detail = raw
    try:
        m = re.search(r"request failed:\s*(\d+)\s*(.*)", raw, flags=re.IGNORECASE)
        if m:
            status = m.group(1)
            detail = (m.group(2) or "").strip() or raw
    except Exception:
        pass

    detail_l = (detail or "").lower()
    if "username" in detail_l and any(word in detail_l for word in ("already", "exists", "occupied", "taken", "занят")):
        code = "A019"
    elif status in errors:
        code = status
    else:
        code = status or "400"
    description = errors.get(code, "неизвестная ошибка")
    short_detail = (detail or "").strip()
    if len(short_detail) > 200:
        short_detail = short_detail[:200] + "..."
    return code, description, short_detail


def _format_key_action_label(action: str | None, *, price: float | None = None, key_id: int | None = None) -> str:
    action_s = (action or "").strip().lower()
    if action_s == "new":
        return f"покупка тарифа {price:.0f} RUB" if price is not None else "покупка тарифа"
    if action_s == "extend":
        if price is not None:
            return f"продление ключа #{key_id or '—'} ({price:.0f} RUB)"
        return f"продление ключа #{key_id or '—'}"
    if action_s == "trial":
        return "пробный ключ"
    if action_s == "gift":
        return f"подарочный ключ {price:.0f} RUB" if price is not None else "подарочный ключ"
    return action or "операция"


def _log_key_creation_error(user_id: int, action_label: str, code: str, detail: str) -> None:
    ts = datetime.utcnow().isoformat()
    logger.error(
        "Key creation error: time=%s user_id=%s action=%s code=%s detail=%s",
        ts,
        user_id,
        action_label,
        code,
        detail,
    )


async def _notify_admins_key_creation_error(
    bot: Bot,
    *,
    user_id: int,
    code: str,
    description: str,
    action_label: str,
) -> None:
    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    if not admin_ids:
        return
    text = (
        "🚨 Ошибка создания ключа\n"
        f"👤 ID: {user_id}\n"
        f"🔢 Код: {code}\n"
        f"📝 Описание: {description}\n"
        f"📋 Действие: {action_label}"
    )
    for aid in admin_ids:
        try:
            await bot.send_message(int(aid), text)
        except Exception:
            continue


async def _notify_user_key_creation_error(
    bot: Bot,
    *,
    user_id: int,
    code: str,
    refund: bool = True,
    factory_bot_id: int = 0,
) -> None:
    lines = ["❌ Не удалось создать ключ."]
    if refund:
        lines.append("Средства возвращены на ваш баланс в боте.")
    lines.append(f"Код ошибки: {code}")
    lines.append("Попробуй позже или напиши в поддержку.")
    text = "\n".join(lines)
    markup = keyboards.create_support_keyboard()
    # Franchise users may only have started the clone bot — try it first.
    if factory_bot_id > 0:
        try:
            info = rw_repo.get_managed_bot(factory_bot_id)
            token = (info or {}).get("token")
            if token:
                tmp = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
                try:
                    await tmp.send_message(chat_id=user_id, text=text, reply_markup=markup)
                    return
                except Exception:
                    pass
                finally:
                    try:
                        await tmp.close()
                    except Exception:
                        pass
        except Exception:
            pass
    try:
        await bot.send_message(chat_id=user_id, text=text, reply_markup=markup)
    except Exception:
        pass


async def _handle_key_creation_failure(
    bot: Bot,
    *,
    user_id: int,
    action_label: str,
    exc: Exception | None,
    refund: bool = True,
    factory_bot_id: int = 0,
) -> None:
    code, description, detail = _classify_key_creation_error(exc)
    _log_key_creation_error(user_id, action_label, code, detail)
    await _notify_user_key_creation_error(bot, user_id=user_id, code=code, refund=refund, factory_bot_id=factory_bot_id)
    await _notify_admins_key_creation_error(
        bot,
        user_id=user_id,
        code=code,
        description=description,
        action_label=action_label,
    )


async def _abort_topup_fulfillment(
    bot: Bot,
    *,
    payment_id: str,
    user_id: int,
    price: float,
    payment_method: str | None,
    action_label: str,
    reason: str,
) -> bool:
    """Компенсирующая транзакция при сбое применения оплаченной докупки трафика.

    Аналог `_abort_key_fulfillment` для докупки ГБ/LTE (там сообщения про создание ключа
    неуместны). Раньше эти ветви просто писали пользователю «не удалось применить» и
    выходили: платёж оставался помеченным в `processed_payments`, повторная доставка
    вебхука отбрасывалась, автовозврата не было — деньги списаны, услуга не оказана.

    1) снимает idempotency-lock (чтобы ретрай вебхука мог применить докупку заново),
    2) один раз возвращает средства (Balance / ReferralBalance / внешние → баланс),
    3) уведомляет пользователя и админов.

    Возвращает True, если refund реально зачислен (первичный вызов).
    """
    try:
        rw_repo.unclaim_processed_payment(payment_id)
        rw_repo.reset_pending_transaction(payment_id)
    except Exception:
        pass

    did_refund = False
    if price and float(price) > 0:
        try:
            did_refund = bool(
                refund_payment_once(payment_id, int(user_id), float(price), payment_method)
            )
        except Exception:
            did_refund = False

    logger.error(
        "TOPUP_ROLLBACK payment_id=%s user_id=%s amount=%s method=%s action=%s reason=%s refunded=%s",
        payment_id,
        user_id,
        price,
        payment_method,
        action_label,
        reason,
        did_refund,
    )

    lines = ["⚠️ Оплата получена, но применить докупку не удалось."]
    if did_refund:
        lines.append("Средства возвращены на ваш баланс в боте — попробуйте ещё раз.")
    else:
        lines.append("Платёж не потерян: обратитесь в поддержку, мы применим докупку вручную.")
    try:
        await bot.send_message(
            chat_id=user_id,
            text="\n".join(lines),
            reply_markup=keyboards.create_support_keyboard(),
        )
    except Exception:
        pass

    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    admin_text = (
        "🚨 Не удалось применить оплаченную докупку\n"
        f"👤 ID: {user_id}\n"
        f"📋 Действие: {action_label}\n"
        f"🧾 payment_id: {payment_id}\n"
        f"💰 Сумма: {price}\n"
        f"🔢 Причина: {reason}\n"
        f"↩️ Возврат: {'да' if did_refund else 'нет'}"
    )
    for aid in admin_ids:
        try:
            await bot.send_message(int(aid), admin_text)
        except Exception:
            continue
    return did_refund


async def _notify_admins_topup_desync(
    bot: Bot,
    *,
    user_id: int,
    action_label: str,
    payment_id: str,
    detail: str,
) -> None:
    """Докупка применена на VPN-сервере, но не сохранилась в БД бота.

    Возврат средств здесь недопустим (услуга фактически оказана), но расхождение нужно
    починить вручную: локальный `traffic_boost_bytes` используется при ежемесячном сбросе
    лимита, и без него бот вернёт ключ к базовому лимиту тарифа.
    """
    logger.error(
        "TOPUP_DB_DESYNC user_id=%s action=%s payment_id=%s detail=%s",
        user_id,
        action_label,
        payment_id,
        detail,
    )
    try:
        admin_ids = list(rw_repo.get_admin_ids() or [])
    except Exception:
        admin_ids = []
    text = (
        "🚨 Докупка применена на сервере, но не записана в БД бота\n"
        f"👤 ID: {user_id}\n"
        f"📋 Действие: {action_label}\n"
        f"🧾 payment_id: {payment_id}\n"
        f"📝 Детали: {detail}\n"
        "Требуется ручная сверка лимита ключа."
    )
    for aid in admin_ids:
        try:
            await bot.send_message(int(aid), text)
        except Exception:
            continue


async def _abort_key_fulfillment(
    bot: Bot,
    *,
    payment_id: str,
    user_id: int,
    price: float,
    payment_method: str | None,
    action_label: str,
    exc: Exception | None,
    factory_bot_id: int = 0,
    processing_message=None,
    fail_text: str = "❌ Не удалось создать ключ.",
) -> bool:
    """Компенсирующая транзакция при сбое выдачи ключа после оплаты.

    1) снимает idempotency-lock (webhook может ретраить),
    2) один раз возвращает средства (Balance / ReferralBalance / внешние → баланс),
    3) уведомляет пользователя и админов.

    Возвращает True, если refund реально зачислен (первичный вызов).
    """
    try:
        rw_repo.unclaim_processed_payment(payment_id)
        rw_repo.reset_pending_transaction(payment_id)
    except Exception:
        pass

    did_refund = False
    if price and float(price) > 0:
        try:
            did_refund = bool(
                refund_payment_once(payment_id, int(user_id), float(price), payment_method)
            )
        except Exception:
            did_refund = False
        if did_refund:
            logger.error(
                "PAYMENT_ROLLBACK payment_id=%s user_id=%s amount=%.2f method=%s error=%s",
                payment_id,
                user_id,
                float(price),
                payment_method,
                exc,
            )

    await _handle_key_creation_failure(
        bot,
        user_id=user_id,
        action_label=action_label,
        exc=exc,
        refund=did_refund,
        factory_bot_id=factory_bot_id,
    )
    if processing_message is not None:
        try:
            await processing_message.edit_text(fail_text)
        except Exception:
            pass
    return did_refund

async def _safe_edit_or_answer(message: types.Message, text: str, **kwargs) -> None:
    """Заменить `message.edit_text(...)` там, где предыдущее сообщение может
    оказаться нетекстовым (счёт на оплату Stars/ЮKassa, фото рассылки и т.п.) —
    у таких сообщений нет текста для редактирования, и Telegram отвечает
    `Bad Request: there is no text in the message to edit`. В этом случае
    вместо падения хендлера отправляем новое сообщение с тем же контентом.
    """
    try:
        await message.edit_text(text, **kwargs)
    except TelegramBadRequest:
        try:
            await message.answer(text, **kwargs)
        except TelegramBadRequest:
            pass
