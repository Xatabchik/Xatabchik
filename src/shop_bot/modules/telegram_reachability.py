"""
Классификация и обработка ошибок недоступности пользователя в Telegram
(пользователь заблокировал бота, либо его аккаунт удалён/деактивирован).

Используется во всех местах массовой отправки сообщений (рассылки — как
плановые кампании из scheduler.py, так и разовая рассылка из админ-панели/бота),
чтобы автоматически:
  1. помечать таких пользователей в БД (users.is_unreachable/unreachable_reason);
  2. больше не пытаться писать им в последующих рассылках
     (см. database.get_inactive_subscribers — уже фильтрует таких пользователей);
  3. вести статистику реального количества доступных подписчиков
     (см. database.get_reachability_stats).

Отметка снимается автоматически, как только пользователь снова напишет боту
или нажмёт любую кнопку — см. shop_bot.bot.middlewares.BanMiddleware.
"""

from __future__ import annotations

import logging

from aiogram.exceptions import TelegramForbiddenError

logger = logging.getLogger(__name__)

REASON_BLOCKED = "blocked"
REASON_DEACTIVATED = "deactivated"


def classify_unreachable_error(exc: Exception) -> str | None:
    """Определить, означает ли ошибка отправки недоступность пользователя в Telegram.

    Возвращает REASON_BLOCKED / REASON_DEACTIVATED, либо None, если это другая
    ошибка (временная сетевая проблема, rate limit, невалидный контент и т.п.),
    не связанная с недоступностью получателя.
    """
    if not isinstance(exc, TelegramForbiddenError):
        return None
    message = (getattr(exc, "message", "") or str(exc)).lower()
    if "deactivated" in message:
        return REASON_DEACTIVATED
    if "blocked" in message:
        return REASON_BLOCKED
    # Прочие 403-ошибки (например, "bot can't initiate conversation with a user")
    # тоже означают, что боту недоступен этот пользователь — считаем блокировкой.
    return REASON_BLOCKED


def handle_send_exception(user_id: int, exc: Exception) -> bool:
    """Проверить ошибку отправки сообщения пользователю и, если она означает
    недоступность (блокировка бота / деактивация аккаунта), пометить это в БД.

    Возвращает True, если пользователь был помечен как недоступный.
    Ничего не поднимает наружу — вызывающий код должен продолжать рассылку.
    """
    reason = classify_unreachable_error(exc)
    if not reason:
        return False
    try:
        from shop_bot.data_manager import database

        if database.mark_user_unreachable(user_id, reason):
            logger.info("Пользователь %s отмечен как недоступный (%s): %s", user_id, reason, exc)
    except Exception as e:
        logger.error("Не удалось отметить пользователя %s как недоступного: %s", user_id, e)
    return True
