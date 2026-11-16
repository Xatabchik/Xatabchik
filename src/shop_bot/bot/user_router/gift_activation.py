"""Активация подарочного кода без участия дарителя.
"""

from html import escape as html_escape

from aiogram import (
    Bot,
    types,
)
from shop_bot.bot import keyboards
from shop_bot.data_manager import gift_claim
from shop_bot.data_manager import remnawave_repository as rw_repo

__all__ = [
    "_activate_gift_directly",
    "_remember_pending_gift",
    "_resume_pending_gift_claims",
]


def _remember_pending_gift(user_id: int, gift_code: str, *, is_new_user: bool) -> None:
    """Сохранить получение подарка до прохождения капчи/согласия/подписки."""
    try:
        token = rw_repo.remember_pending_gift_for_user(user_id, gift_code, is_new_user=is_new_user)
    except Exception:
        token = None
        logger.warning("gift_claim stage=remember channel=telegram user_id=%s result=error", user_id, exc_info=True)
    logger.info(
        "gift_claim stage=remember channel=telegram user_id=%s code_ref=%s is_new=%s result=%s",
        user_id, rw_repo.gift_code_ref(gift_code), bool(is_new_user), "ok" if token else "error",
    )


def _gift_result_text(result: dict) -> str:
    status = result.get("status")
    if status in ("activated", "recovered"):
        key = result.get("key") or {}
        return (
            "🎁 <b>Подарок успешно активирован!</b>\n\n"
            "✅ Ключ добавлен в ваш профиль\n"
            f"🖥️ Сервер: {html_escape(str(key.get('host_name') or 'Unknown'))}\n"
            f"📅 Истекает: {html_escape(str(key.get('expiry_date') or key.get('expire_at') or 'Unknown'))}"
        )
    if status == "already_activated":
        return "✅ " + gift_claim.MESSAGES["already_activated"]
    if status in ("error", "key_missing", "key_unavailable", "inconsistent"):
        return "⚠️ " + result.get("message", gift_claim.MESSAGES["error"])
    return "❌ " + result.get("message", gift_claim.MESSAGES["error"])


async def _claim_and_notify(
    message: types.Message,
    bot: Bot,
    user_id: int,
    gift_code: str,
    *,
    is_new_user: bool,
    pending_token: str | None = None,
) -> dict:
    """Передать подарок и сообщить результат.

    Pending action закрывается сразу после окончательного результата, до
    отправки сообщения: сбой Telegram после commit не отменяет выдачу и не
    приводит к повторной передаче.
    """
    try:
        result = gift_claim.claim_gift(user_id, gift_code, channel="telegram", bind_referral=is_new_user)
    except Exception:
        logger.error("gift_claim channel=telegram user_id=%s result=error", user_id, exc_info=True)
        result = {"ok": False, "status": "error", "final": False, "message": gift_claim.MESSAGES["error"]}

    if pending_token and result.get("final"):
        try:
            rw_repo.resolve_pending_action(pending_token, user_id, result.get("status") or "error")
        except Exception:
            logger.warning("gift_claim stage=resolve channel=telegram user_id=%s result=error", user_id, exc_info=True)

    try:
        await message.answer(_gift_result_text(result), reply_markup=keyboards.main_reply_keyboard)
    except Exception:
        logger.warning(
            "gift_claim stage=notify channel=telegram gift_id=%s user_id=%s result=error",
            result.get("gift_id"), user_id, exc_info=True,
        )
    return result


async def _resume_pending_gift_claims(message: types.Message, bot: Bot, user_id: int) -> bool:
    """Довести сохранённые получения подарков после всех этапов входа.

    Вызывается только когда пользователь зарегистрирован, прошёл капчу и
    принял условия/подписку. Возвращает True, если что-то было обработано.
    """
    try:
        pending = rw_repo.get_open_pending_gift_actions(user_id) or []
    except Exception:
        logger.warning("gift_claim stage=resume channel=telegram user_id=%s result=error", user_id, exc_info=True)
        return False
    for item in pending:
        await _claim_and_notify(
            message, bot, user_id, item.get("gift_code") or "",
            is_new_user=bool(item.get("owner_is_new")),
            pending_token=item.get("token"),
        )
    return bool(pending)


async def _activate_gift_directly(
    message: types.Message, bot: Bot, user_id: int, gift_code: str,
    *, is_new_user: bool = False
) -> dict:
    """Активировать подарок для пользователя и показать главное меню при успехе.

    `user_id` — проверенный отправитель апдейта (message/callback.from_user),
    а не `message.from_user`: для callback это сообщение бота.
    """
    result = await _claim_and_notify(message, bot, user_id, gift_code, is_new_user=is_new_user)
    if result.get("ok"):
        try:
            await show_main_menu(message)
        except Exception:
            logger.warning("gift_claim stage=menu channel=telegram user_id=%s result=error", user_id, exc_info=True)
    return result
