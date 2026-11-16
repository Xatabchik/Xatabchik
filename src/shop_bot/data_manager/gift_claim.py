"""Получение пользовательского подарка — общий сервис для бота и Mini App.

Передача ключа и запись активации выполняются одной транзакцией
(`database.transfer_user_gift`); здесь — то, что идёт после подтверждённой
передачи (привязка реферала к дарителю), единые тексты для пользователя и
диагностические события `gift_claim` без кода подарка и ссылок подписки.
"""
from __future__ import annotations

import logging

from shop_bot.data_manager import database

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = frozenset({"activated", "recovered", "already_activated"})

# Повтор не изменит исход: pending action закрывается, пользователь получает ответ.
# Не входит только "error" — временный сбой, действие остаётся открытым.
FINAL_STATUSES = SUCCESS_STATUSES | frozenset({
    "not_found",
    "expired",
    "already_activated_by_other",
    "key_missing",
    "key_unavailable",
    "inconsistent",
})

MESSAGES = {
    "activated": "Подарок успешно активирован! Ключ добавлен в ваш профиль.",
    "recovered": "Подарок успешно активирован! Ключ добавлен в ваш профиль.",
    "already_activated": "Подарок уже активирован на ваш аккаунт.",
    "already_activated_by_other": "Этот подарок уже был активирован другим пользователем.",
    "not_found": "Подарок не найден или код неверный.",
    "expired": "Срок действия подарка истёк.",
    "key_missing": "Ключ этого подарка не найден, поэтому подарок не активирован. Свяжитесь с поддержкой.",
    "key_unavailable": "Ключ этого подарка сейчас недоступен для передачи. Свяжитесь с поддержкой.",
    "inconsistent": (
        "Подарок записан на ваш аккаунт, но ключ не был передан. "
        "Свяжитесь с поддержкой — подарок не потерян."
    ),
    "error": "Не удалось активировать подарок из-за временной ошибки. Попробуйте ещё раз чуть позже.",
}


def claim_gift(user_id: int, gift_code: str, *, channel: str, bind_referral: bool) -> dict:
    """Передать подарок `gift_code` пользователю `user_id`.

    `bind_referral` — сделать дарителя реферером получателя; выполняется только
    после новой подтверждённой передачи и с прежними ограничениями
    `set_referred_by_from_gift` (без существующего реферера, свежая регистрация).

    Returns: результат `transfer_user_gift` + {"message", "final", "channel",
    "referral_bound"}.
    """
    logger.info(
        "gift_claim stage=start channel=%s user_id=%s code_ref=%s",
        channel, user_id, database.gift_code_ref(gift_code),
    )
    result = database.transfer_user_gift(gift_code, user_id)
    status = result.get("status") or "error"
    result["channel"] = channel
    result["final"] = status in FINAL_STATUSES
    result["message"] = MESSAGES.get(status, MESSAGES["error"])
    result["referral_bound"] = False

    if status == "activated" and bind_referral:
        from_user_id = int(result.get("from_user_id") or 0)
        if from_user_id > 0:
            try:
                result["referral_bound"] = bool(database.set_referred_by_from_gift(int(user_id), from_user_id))
            except Exception:
                logger.warning(
                    "gift_claim stage=referral channel=%s gift_id=%s user_id=%s result=error",
                    channel, result.get("gift_id"), user_id, exc_info=True,
                )

    log = logger.warning if status in ("error", "inconsistent", "key_unavailable") else logger.info
    log(
        "gift_claim stage=done channel=%s gift_id=%s user_id=%s key_id=%s result=%s referral_bound=%s",
        channel, result.get("gift_id"), user_id, result.get("key_id"), status, result["referral_bound"],
    )
    return result
