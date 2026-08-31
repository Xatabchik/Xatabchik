"""Автозакрытие открытых тикетов, если после ответа админа пользователь молчит N дней."""
from __future__ import annotations

import asyncio
import logging
import threading
import time

from shop_bot.data_manager import database

logger = logging.getLogger(__name__)

_IDLE_CLOSE_GAP_SEC = 0.12
_IDLE_CLOSE_CALL_TIMEOUT_SEC = 3.0
_idle_close_followup_lock = threading.Lock()


def _ru_days_word(n: int) -> str:
    try:
        n = abs(int(n))
    except (TypeError, ValueError):
        n = 0
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} день"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} дня"
    return f"{n} дней"


def _forum_wait(loop, coro, timeout: float) -> None:
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    fut.result(timeout=timeout)


def run_idle_close_followup(tickets: list[dict], days: int) -> None:
    """Темы форума и короткое уведомление пользователю. Не из HTTP-потока."""
    if not tickets:
        return
    try:
        from shop_bot.webhook_server import app as wh_mod

        ctrl = getattr(wh_mod, "_support_bot_controller", None)
    except Exception:
        ctrl = None
    bot = ctrl.get_bot_instance() if ctrl else None
    loop = ctrl.get_loop() if ctrl else None
    if not bot or not loop or not loop.is_running():
        logger.warning(
            "Автозакрытие тикетов: support-бот недоступен, форум и уведомления пропущены (%s шт.)",
            len(tickets),
        )
        return

    days_text = _ru_days_word(days)
    with _idle_close_followup_lock:
        for i, row in enumerate(tickets):
            ticket_id = row.get("ticket_id")
            forum_chat_id = row.get("forum_chat_id")
            thread_id = row.get("message_thread_id")
            user_id = row.get("user_id")
            try:
                if forum_chat_id and thread_id not in (None, ""):
                    try:
                        _forum_wait(
                            loop,
                            bot.send_message(
                                chat_id=int(forum_chat_id),
                                text=(
                                    f"⏱ Тикет #{ticket_id} закрыт автоматически: "
                                    f"нет ответа пользователя {days_text}."
                                ),
                                message_thread_id=int(thread_id),
                            ),
                            _IDLE_CLOSE_CALL_TIMEOUT_SEC,
                        )
                    except Exception as e:
                        logger.warning(
                            "Автозакрытие: не удалось написать в тему тикета %s: %s",
                            ticket_id,
                            e,
                        )
                    try:
                        _forum_wait(
                            loop,
                            bot.close_forum_topic(
                                chat_id=int(forum_chat_id),
                                message_thread_id=int(thread_id),
                            ),
                            _IDLE_CLOSE_CALL_TIMEOUT_SEC,
                        )
                    except Exception as e:
                        logger.warning(
                            "Автозакрытие: не удалось закрыть тему тикета %s: %s",
                            ticket_id,
                            e,
                        )
                if user_id:
                    try:
                        _forum_wait(
                            loop,
                            bot.send_message(
                                chat_id=int(user_id),
                                text=(
                                    f"✅ Ваш тикет #{ticket_id} закрыт автоматически: "
                                    f"нет ответа {days_text}. "
                                    "Вы можете создать новое обращение."
                                ),
                            ),
                            _IDLE_CLOSE_CALL_TIMEOUT_SEC,
                        )
                    except Exception as e:
                        logger.warning(
                            "Автозакрытие: не удалось уведомить пользователя тикета %s: %s",
                            ticket_id,
                            e,
                        )
            except Exception:
                logger.exception("Автозакрытие: сбой по тикету %s", ticket_id)
            if _IDLE_CLOSE_GAP_SEC and i + 1 < len(tickets):
                time.sleep(_IDLE_CLOSE_GAP_SEC)


def maybe_auto_close_idle_tickets(*, now=None, sync_followup: bool = False) -> int:
    """Закрывает пачку простаивающих тикетов. Telegram — в фоне, SQL сразу.

    SQL не ждёт Telegram: следующий цикл планировщика может закрыть ещё пачку,
    пока фоновые уведомления догоняют. Вызовы Telegram сериализует
    ``_idle_close_followup_lock``. ``sync_followup=True`` только для тестов.
    """
    days = database.get_ticket_auto_close_days()
    if days <= 0:
        return 0

    result = database.auto_close_idle_admin_tickets(days, now=now)
    count = int(result.get("count") or 0)
    tickets = list(result.get("tickets") or [])
    if count == 0:
        return 0
    logger.info("Автозакрытие тикетов: закрыто %s (порог %s).", count, _ru_days_word(days))

    if sync_followup:
        run_idle_close_followup(tickets, days)
        return count

    threading.Thread(
        target=_run_followup_safe,
        args=(tickets, days),
        name="shopbot-idle-ticket-close",
        daemon=True,
    ).start()
    return count


def _run_followup_safe(tickets: list[dict], days: int) -> None:
    try:
        run_idle_close_followup(tickets, days)
    except Exception:
        logger.exception("Автозакрытие тикетов: фоновая задача упала")
