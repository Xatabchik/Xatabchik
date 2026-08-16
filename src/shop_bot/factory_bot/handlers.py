
import logging

from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery

from shop_bot.data_manager import remnawave_repository as rw_repo
from . import keyboards
from .runtime import get_service

logger = logging.getLogger(__name__)

DELETE_CONFIRM_TEXT = (
    "Клон будет остановлен. Активность пользователей клона будет удалена. "
    "Одобренные/выплаченные заявки на вывод сохранятся для финансового аудита."
)


def _parse_bot_id_from_callback(data: str, prefix: str) -> int | None:
    raw = (data or "")
    if not raw.startswith(prefix):
        return None
    suffix = raw[len(prefix):]
    try:
        bot_id = int(suffix)
    except Exception:
        return None
    return bot_id if bot_id > 0 else None


def get_owner_cabinet_router() -> Router:
    """Кабинет владельца текущего клона: просмотр и удаление ЭТОГО бота."""
    r = Router()

    @r.callback_query(F.data == "factory_cabinet")
    async def cabinet(cb: CallbackQuery, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id == 0:
            await cb.answer("Кабинет доступен только во клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if cb.from_user.id != owner_id:
            await cb.answer("Кабинет доступен только владельцу.", show_alert=True)
            return

        stats = rw_repo.get_factory_cabinet(bot_id)
        text = (
            "📊 *Кабинет*\n\n"
            f"Бот: @{info.get('username') or 'без_username'}\n"
            f"Пользователи: *{stats.get('total_users', 0)}*\n"
            f"Сообщения: *{stats.get('total_messages', 0)}*\n"
            f"Создано ботов (прямые): *{stats.get('direct_bots', 0)}*\n"
            f"Баланс: *{stats.get('balance', 0):.2f}*\n"
        )
        await cb.message.edit_text(text, reply_markup=keyboards.cabinet_menu(), parse_mode="Markdown")
        await cb.answer()

    @r.callback_query(F.data == "factory_del_self")
    async def delete_self_ask(cb: CallbackQuery, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if int(bot_id or 0) <= 0:
            await cb.answer("Удаление доступно только в клоне.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if not info or cb.from_user.id != owner_id:
            await cb.answer("Можно удалять только своего бота.", show_alert=True)
            return
        username = info.get("username") or "без_username"
        await cb.message.edit_text(
            f"Удалить бота @{username} (id={bot_id})?\n\n{DELETE_CONFIRM_TEXT}",
            reply_markup=keyboards.delete_bot_confirm(bot_id),
        )
        await cb.answer()

    @r.callback_query(F.data.startswith("factory_del_yes:"))
    async def delete_bot_confirm(cb: CallbackQuery):
        bot_id = _parse_bot_id_from_callback(cb.data or "", "factory_del_yes:")
        if not bot_id:
            await cb.answer("Некорректный бот.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if not info or cb.from_user.id != owner_id:
            await cb.answer("Можно удалять только свои боты.", show_alert=True)
            return

        service = get_service()
        if service:
            try:
                await service.stop_bot(bot_id)
            except Exception as e:
                logger.error(f"Failed to stop managed bot {bot_id} before delete: {e}", exc_info=True)

        deleted = rw_repo.delete_managed_bot(bot_id, owner_telegram_id=cb.from_user.id)
        try:
            if not deleted:
                await cb.answer("Не удалось удалить бота.", show_alert=True)
                return
            await cb.answer("Бот удалён.")
        except Exception:
            pass

    return r
