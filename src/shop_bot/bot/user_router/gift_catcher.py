"""Приём username получателя подарка обычным текстовым сообщением.

Хендлер ловит любой текст без состояния FSM, поэтому регистрируется
последним среди message-хендлеров — порядок здесь значим.
"""

import uuid
import time
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.filters import StateFilter
from shop_bot.data_manager.remnawave_repository import find_and_complete_pending_transaction
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.modules import remnawave_api
from shop_bot.data_manager.database import (
    get_latest_pending_for_user,
    get_user_by_username,
)

__all__: list[str] = []


def register_gift_catcher(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""



    
    @user_router.message(StateFilter(None), F.text)
    @registration_required
    async def _gift_username_catcher(message: types.Message):
        logger.info(f"Gift catcher: incoming text from {message.from_user.id}: {message.text}")
        text = (message.text or "").strip()
        if not text:
            return
        if text.startswith("@"):
            text = text[1:]
        import re as _re
        if not _re.match(r"^[A-Za-z0-9_]{5,}$", text):
            return
        
        pending = None
        try:
            pending = get_latest_pending_for_user(message.from_user.id)
        except Exception as e:
            logger.info(f"Gift catcher: DB not available or error: {e}")
        if not pending:
            try:
                pending = PENDING_GIFTS.get(int(message.from_user.id))
                if pending:
                    logger.info(f"Gift catcher: fallback cache hit for {message.from_user.id}: {pending}")
            except Exception:
                pending = None
        if not pending or (pending.get("type") != "gift"):
            logger.info(f"Gift catcher: no pending gift for {message.from_user.id}")
            return
        
        host_name = pending.get("host_name")
        months = int(pending.get("months") or 0)
        duration_days = int(pending.get("duration_days") or 0)
        days_to_add = int(pending.get("days_to_add") or 0)
        if days_to_add <= 0:
            days_to_add = _compute_days_to_add(months, duration_days)
        recipient_user = None
        try:
            recipient_user = get_user_by_username(text)
        except Exception:
            recipient_user = None
        recipient_email = None
        if recipient_user and recipient_user.get("telegram_id"):
            try:
                recipient_id = int(recipient_user["telegram_id"])
            except Exception:
                recipient_id = None
            if recipient_id:
                try:
                    recipient_email = rw_repo.generate_key_email_for_user(recipient_id)
                except Exception:
                    recipient_email = f"{recipient_id}-{int(time.time())}@bot.local"
        if not recipient_email:
            recipient_email = f"gift-{uuid.uuid4().hex[:8]}@bot.local"
        
        try:
            result = await remnawave_api.create_or_update_key_on_host(
                host_name=host_name,
                email=recipient_email,
                days_to_add=int(days_to_add),
                description=f"Gift for @{text} from {message.from_user.id}",
                raise_on_error=True,
            )
        except Exception as exc:
            try:
                price = float(pending.get("price") or 0.0)
            except Exception:
                price = None
            await _handle_key_creation_failure(
                message.bot,
                user_id=message.from_user.id,
                action_label=_format_key_action_label("gift", price=price),
                exc=exc,
                refund=True,
            )
            return
        
        if not result:
            try:
                price = float(pending.get("price") or 0.0)
            except Exception:
                price = None
            await _handle_key_creation_failure(
                message.bot,
                user_id=message.from_user.id,
                action_label=_format_key_action_label("gift", price=price),
                exc=RuntimeError("gift key creation returned empty response"),
                refund=True,
            )
            return
        
        # Привязываем ключ к локальному аккаунту получателя, если он уже пользовался ботом
        try:
            ru = recipient_user or get_user_by_username(text)
            if ru and ru.get('telegram_id'):
                rw_repo.record_key_from_payload(
                    user_id=int(ru['telegram_id']),
                    payload=result,
                    host_name=host_name,
                    tag="paid",
                    description=_build_key_origin_meta(
                        source="gift",
                        plan_id=None,
                        plan_name=None,
                        months=months,
                        duration_days=duration_days,
                        is_trial=False,
                        note=f"Gift received from {message.from_user.id}",
                    )
                )
                logger.info(f"Gift: key attached to local user {ru['telegram_id']}")
        except Exception as e:
            logger.warning(f"Gift: failed to record gifted key for recipient: {e}")
        
        try:
            pid = pending.get("payment_id")
            if pid:
                find_and_complete_pending_transaction(str(pid))
        except Exception:
            pass
        try:
            PENDING_GIFTS.pop(int(message.from_user.id), None)
        except Exception:
            pass
        
        await message.reply("✅ Подарочный ключ создан для пользователя @{}\nКлюч уже активен в панели, пользователь сможет подключиться сразу.".format(text))
