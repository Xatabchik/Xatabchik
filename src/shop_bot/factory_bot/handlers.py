
import re
import logging

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.data_manager import remnawave_repository as rw_repo
from . import keyboards
from .runtime import get_service

logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")

class FactoryStates(StatesGroup):
    waiting_token = State()
    waiting_withdraw_amount = State()

def get_factory_router() -> Router:
    r = Router()

    @r.message(CommandStart())
    async def start(message: Message, bot: Bot):
        # Determine internal bot_id for this running bot (0 for root)
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        owner_id = None
        if bot_id != 0:
            info = rw_repo.get_managed_bot(bot_id)
            owner_id = info.get("owner_telegram_id") if info else None
        show_cabinet = owner_id is not None and message.from_user and message.from_user.id == int(owner_id)
        text = (
            "👋 Привет!\n\n"
            "Здесь ты можешь быстро *клонировать* бота: создай нового бота в @BotFather и отправь сюда его токен.\n\n"
            "Нажми «🤖 Создать бот» — я пришлю инструкцию."
        )
        await message.answer(text, reply_markup=keyboards.main_menu(show_cabinet=show_cabinet), parse_mode="Markdown")

    @r.callback_query(F.data == "factory_back")
    async def back(cb: CallbackQuery, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        owner_id = None
        if bot_id != 0:
            info = rw_repo.get_managed_bot(bot_id)
            owner_id = info.get("owner_telegram_id") if info else None
        show_cabinet = owner_id is not None and cb.from_user.id == int(owner_id)
        await cb.message.edit_text(
            "Главное меню:", reply_markup=keyboards.main_menu(show_cabinet=show_cabinet)
        )
        await cb.answer()

    @r.callback_query(F.data == "factory_help")
    async def help_cb(cb: CallbackQuery):
        text = (
            "📌 *Инструкция по созданию бота*\n\n"
            "1) Открой @BotFather\n"
            "2) Нажми /start\n"
            "3) Напиши /newbot\n"
            "4) Придумай имя\n"
            "5) Придумай username, который заканчивается на *Bot*\n"
            "6) Скопируй токен (вида `123456:ABC...`)\n\n"
            "После этого вернись сюда и отправь токен одним сообщением."
        )
        await cb.message.edit_text(text, reply_markup=keyboards.back_only(), parse_mode="Markdown")
        await cb.answer()

    @r.callback_query(F.data == "factory_create_bot")
    async def create_bot_start(cb: CallbackQuery, state: FSMContext):
        text = (
            "Пришли токен твоего бота одним сообщением.\n\n"
            "Пример: `123456789:ABC-DEF...`\n\n"
            "⚠️ Токен — секрет. Не публикуй его в чатах."
        )
        await state.set_state(FactoryStates.waiting_token)
        await cb.message.edit_text(text, reply_markup=keyboards.back_only(), parse_mode="Markdown")
        await cb.answer()

    @r.message(FactoryStates.waiting_token)
    async def receive_token(message: Message, state: FSMContext, bot: Bot):
        token = (message.text or "").strip()
        if not TOKEN_RE.match(token):
            await message.answer("Похоже, это не токен. Пришли токен в формате `123456:ABC...`.", parse_mode="Markdown")
            return

        # Validate token
        try:
            tmp_bot = Bot(token=token)
            me = await tmp_bot.get_me()
            await tmp_bot.session.close()
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            await message.answer("Не получилось проверить токен. Убедись, что он правильный и бот не заблокирован.")
            return

        referrer_bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        ok, msg, new_bot_id = rw_repo.create_managed_bot(
            token=token,
            telegram_bot_user_id=me.id,
            username=getattr(me, "username", None),
            owner_telegram_id=message.from_user.id,
            referrer_bot_id=referrer_bot_id,
        )
        if not ok or not new_bot_id:
            await message.answer(msg)
            await state.clear()
            return

        # Start the new bot immediately
        service = get_service()
        if service:
            try:
                await service.start_bot(new_bot_id)
            except Exception as e:
                logger.error(f"Failed to start managed bot {new_bot_id}: {e}", exc_info=True)

        uname = f"@{me.username}" if getattr(me, "username", None) else f"(id {me.id})"
        await message.answer(
            f"✅ Готово! Твой бот {uname} подключён.\n\n"
            "Открой его и нажми /start — у владельца появится кнопка «📊 Кабинет».",
            parse_mode="Markdown",
        )
        await state.clear()

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

    @r.callback_query(F.data == "factory_withdraw")
    async def withdraw_start(cb: CallbackQuery, bot: Bot, state: FSMContext):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if cb.from_user.id != owner_id:
            await cb.answer("Только владелец.", show_alert=True)
            return
        await state.set_state(FactoryStates.waiting_withdraw_amount)
        await cb.message.edit_text(
            "Введи сумму для вывода (числом).\n\nНапример: `150`",
            reply_markup=keyboards.back_only(),
            parse_mode="Markdown",
        )
        await cb.answer()

    @r.message(FactoryStates.waiting_withdraw_amount)
    async def withdraw_amount(message: Message, bot: Bot, state: FSMContext):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if message.from_user.id != owner_id:
            await message.answer("Только владелец.")
            await state.clear()
            return

        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer("Не понял сумму. Пришли число, например `150`.", parse_mode="Markdown")
            return

        ok, msg = rw_repo.create_withdraw_request(bot_id, owner_id, amount)
        await message.answer("✅ " + msg if ok else "❌ " + msg)

        # notify admin (root settings)
        try:
            admin_id_raw = rw_repo.get_setting("admin_telegram_id")
            admin_id = int(str(admin_id_raw).strip()) if admin_id_raw is not None else None
        except Exception:
            admin_id = None

        if ok and admin_id:
            try:
                await bot.send_message(
                    admin_id,
                    f"💸 Заявка на вывод\nБот: @{info.get('username') or 'без_username'} (bot_id={bot_id})\n"
                    f"Владелец: {owner_id}\nСумма: {amount}",
                )
            except Exception:
                pass

        await state.clear()

    return r
