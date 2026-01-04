
import logging
import functools
from typing import Any, Callable, Coroutine, Optional, TypeVar, Union

from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def fast_callback_answer(arg: Union[CallbackQuery, F]) -> Union[Coroutine[Any, Any, None], F]:
    """Fast ACK for callback queries.

    This helper is intentionally *dual-mode* for backward compatibility:
    - As a decorator:  @fast_callback_answer
    - As an awaitable: await fast_callback_answer(callback)
    """

    # Mode 1: called as an awaitable helper: `await fast_callback_answer(callback)`
    if isinstance(arg, CallbackQuery):
        callback = arg

        async def _ack() -> None:
            try:
                await callback.answer(cache_time=1)
            except TelegramBadRequest:
                pass
            except Exception as e:
                logger.debug("fast_callback_answer ignore: %r", e)

        return _ack()

    # Mode 2: used as a decorator: `@fast_callback_answer`
    func = arg

    @functools.wraps(func)
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        try:
            await callback.answer(cache_time=1)
        except TelegramBadRequest:
            pass
        except Exception as e:
            logger.debug("fast_callback_answer ignore: %r", e)
        return await func(callback, *args, **kwargs)

    return wrapper  # type: ignore[return-value]

def catch_callback_errors(func):
    @functools.wraps(func)
    async def wrapper(callback: CallbackQuery, *args, **kwargs):
        try:
            return await func(callback, *args, **kwargs)
        except Exception as e:
            try:
                await callback.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)
            except Exception:
                pass
            logger.exception("Callback handler error for data=%r: %s", getattr(callback, "data", None), e)
            return None
    return wrapper

@catch_callback_errors
@fast_callback_answer
async def handle_unknown_callback(callback: CallbackQuery):
    data = getattr(callback, "data", None)
    logger.warning("Unknown callback_data received: %r", data)
    try:
        await callback.message.answer("Эта кнопка пока недоступна. Мы уже разбираемся.")
    except Exception:
        pass
