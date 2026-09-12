"""Рассылка: текст, режим разбора, кнопка, предпросмотр, отправка.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import asyncio
import re
import json
from datetime import datetime

from aiogram import Bot, Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.modules import telegram_reachability
from shop_bot.data_manager import database
from shop_bot.data_manager.remnawave_repository import (
    get_all_users,
    get_setting,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_mailing(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""

    @admin_router.callback_query(F.data == "start_broadcast")
    async def start_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            "Пришлите сообщение, которое вы хотите разослать всем пользователям.\n"
            "Вы можете использовать форматирование (<b>жирный</b>, <i>курсив</i>).\n"
            "Также поддерживаются фото, видео и документы.\n",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_message)

    @admin_router.message(Broadcast.waiting_for_message)
    async def broadcast_message_received_handler(message: types.Message, state: FSMContext):
        import datetime
        from enum import Enum

        def _msg_json_default(o):
            if isinstance(o, Enum):
                return o.value
            if isinstance(o, (datetime.datetime, datetime.date)):
                return o.isoformat()
            return None  # aiogram Default sentinel and other unknown types

        import re

        def _detect_parse_mode(text: str) -> str | None:
            """Auto-detect parse mode: HTML tags → HTML, Markdown links/bold/etc → MarkdownV2."""
            if re.search(r'<(?:a|b|i|s|u|code|pre|tg-spoiler)\b', text, re.IGNORECASE):
                return 'HTML'
            if re.search(r'\[.+?\]\(https?://', text) or re.search(r'\*\*.+?\*\*|__.+?__|~~.+?~~|`[^`\n]+`|\|\|.+?\|\|', text):
                return 'MarkdownV2'
            return None

        msg_json = json.dumps(message.model_dump(), default=_msg_json_default)
        await state.update_data(message_to_send=msg_json)
        if message.text:
            auto_pm = _detect_parse_mode(message.text)
            if auto_pm:
                await state.update_data(parse_mode=auto_pm)
                await message.answer(
                    f"Сообщение получено. Обнаружена разметка — формат <b>{auto_pm}</b> применён автоматически.\n"
                    "Хотите добавить к нему кнопку со ссылкой?",
                    reply_markup=keyboards.create_broadcast_options_keyboard(),
                    parse_mode="HTML",
                )
                await state.set_state(Broadcast.waiting_for_button_option)
            else:
                await message.answer(
                    "Сообщение получено.\n\n"
                    "<b>Выберите формат</b> (нужен если в тексте есть ссылки или разметка):\n"
                    "• <b>Без форматирования</b> — текст как есть\n"
                    "• <b>HTML</b> — <code>&lt;b&gt;жирный&lt;/b&gt;</code>, <code>&lt;a href='url'&gt;текст&lt;/a&gt;</code>\n"
                    "• <b>MarkdownV2</b> — <code>[текст](url)</code> → кликабельная ссылка",
                    reply_markup=keyboards.create_broadcast_parse_mode_keyboard(),
                    parse_mode="HTML",
                )
                await state.set_state(Broadcast.waiting_for_parse_mode)
        else:
            await state.update_data(parse_mode=None)
            await message.answer(
                "Сообщение получено. Хотите добавить к нему кнопку со ссылкой?",
                reply_markup=keyboards.create_broadcast_options_keyboard()
            )
            await state.set_state(Broadcast.waiting_for_button_option)

    @admin_router.callback_query(
        Broadcast.waiting_for_parse_mode,
        F.data.in_({"broadcast_pm_none", "broadcast_pm_html", "broadcast_pm_md2"}),
    )
    async def broadcast_parse_mode_handler(callback: types.CallbackQuery, state: FSMContext):
        pm_map = {"broadcast_pm_none": None, "broadcast_pm_html": "HTML", "broadcast_pm_md2": "MarkdownV2"}
        parse_mode = pm_map[callback.data]
        await state.update_data(parse_mode=parse_mode)
        await callback.answer()
        await callback.message.edit_text(
            "Хотите добавить к нему кнопку со ссылкой?",
            reply_markup=keyboards.create_broadcast_options_keyboard(),
        )
        await state.set_state(Broadcast.waiting_for_button_option)

    
    @admin_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_add_button")
    async def add_button_choose_type(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Выберите тип кнопки для рассылки:",
            reply_markup=keyboards.create_broadcast_button_type_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_type)

    @admin_router.callback_query(Broadcast.waiting_for_button_type, F.data == "broadcast_btn_type_url")
    async def add_button_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Хорошо. Теперь отправьте мне текст для кнопки.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_text)

    @admin_router.callback_query(Broadcast.waiting_for_button_type, F.data == "broadcast_btn_type_action")
    async def add_functional_button_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Выберите действие из функционала бота, к которому привяжем кнопку:",
            reply_markup=keyboards.create_broadcast_actions_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_action_select)

    @admin_router.callback_query(Broadcast.waiting_for_action_select, F.data.startswith("broadcast_action:"))
    async def functional_button_selected(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        data_key = callback.data.split(":",1)[1]
        label = keyboards.BROADCAST_ACTIONS_MAP.get(data_key, data_key)
        await state.update_data(button_text=label, button_callback=data_key, button_url=None)
        await show_broadcast_preview(callback.message, state, callback.bot)


    @admin_router.message(Broadcast.waiting_for_button_text)
    async def button_text_received_handler(message: types.Message, state: FSMContext):
        await state.update_data(button_text=message.text)
        await message.answer(
            "Текст кнопки получен. Теперь отправьте ссылку (URL), куда она будет вести.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_url)

    @admin_router.message(Broadcast.waiting_for_button_url)
    async def button_url_received_handler(message: types.Message, state: FSMContext, bot: Bot):
        url_to_check = message.text

        if not (url_to_check.startswith("http://") or url_to_check.startswith("https://")):
            await message.answer(
                "❌ Ссылка должна начинаться с http:// или https://. Попробуйте еще раз.")
            return
        await state.update_data(button_url=url_to_check)
        await show_broadcast_preview(message, state, bot)

    @admin_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_skip_button")
    async def skip_button_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        await state.update_data(button_text=None, button_url=None)
        await show_broadcast_preview(callback.message, state, bot)

    def _escape_md2(text: str) -> str:
        """Escape MarkdownV2 special chars in plain-text parts, leaving inline entities intact."""
        import re as _re

        # Match valid MarkdownV2 entities to keep as-is
        ENTITY_RE = _re.compile(
            r'(\[(?:[^\[\]\\]|\\.)*\]\((?:[^()\\]|\\.)*\))'  # [text](url)
            r'|(\*\*(?:[^*\\]|\\.|\*(?!\*))*\*\*)'  # **bold**
            r'|(__(?:[^_\\]|\\.)*__)'  # __italic__
            r'|(~~(?:[^~\\]|\\.)*~~)'  # ~~strike~~
            r'|(`[^`\n]+`)'  # `code`
            r'|(\|\|(?:[^|\\]|\\.)*\|\|)',  # ||spoiler||
        )

        def _esc(s: str) -> str:
            return _re.sub(r'([_*\[\]()~`>#+=|{}.!\-\\])', r'\\\1', s)

        parts, last = [], 0
        for m in ENTITY_RE.finditer(text):
            parts.append(_esc(text[last:m.start()]))
            parts.append(m.group(0))
            last = m.end()
        parts.append(_esc(text[last:]))
        return ''.join(parts)

    async def _send_broadcast_to(bot: Bot, chat_id: int, msg: types.Message, keyboard, parse_mode: str | None = None) -> None:
        """Send broadcast, using specific send methods for media so reply_markup is applied correctly."""
        kw = dict(reply_markup=keyboard)
        # When parse_mode is set, use it instead of entities (they are mutually exclusive)
        if parse_mode:
            ckw = dict(caption=msg.caption, parse_mode=parse_mode, **kw)
        else:
            ckw = dict(caption=msg.caption, caption_entities=msg.caption_entities, **kw)
        if msg.photo:
            await bot.send_photo(chat_id=chat_id, photo=msg.photo[-1].file_id, **ckw)
        elif msg.video:
            await bot.send_video(chat_id=chat_id, video=msg.video.file_id, **ckw)
        elif msg.animation:
            await bot.send_animation(chat_id=chat_id, animation=msg.animation.file_id, **ckw)
        elif msg.document:
            await bot.send_document(chat_id=chat_id, document=msg.document.file_id, **ckw)
        elif msg.audio:
            await bot.send_audio(chat_id=chat_id, audio=msg.audio.file_id, **ckw)
        elif msg.voice:
            await bot.send_voice(chat_id=chat_id, voice=msg.voice.file_id, **kw)
        elif msg.sticker:
            await bot.send_sticker(chat_id=chat_id, sticker=msg.sticker.file_id, **kw)
        elif msg.text:
            no_preview = types.LinkPreviewOptions(is_disabled=True)
            if parse_mode:
                text = _escape_md2(msg.text) if parse_mode == 'MarkdownV2' else msg.text
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, link_preview_options=no_preview, **kw)
            else:
                await bot.send_message(chat_id=chat_id, text=msg.text, entities=msg.entities, link_preview_options=no_preview, **kw)
        else:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=msg.chat.id,
                message_id=msg.message_id,
                **kw,
            )

    async def show_broadcast_preview(message: types.Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        message_json = data.get('message_to_send')
        original_message = types.Message.model_validate_json(message_json)
        parse_mode = data.get('parse_mode')

        button_text = data.get('button_text')
        button_url = data.get('button_url')
        button_callback = data.get('button_callback')

        preview_builder = InlineKeyboardBuilder()
        if button_text and (button_url or button_callback):
            if button_url:
                preview_builder.button(text=button_text, url=button_url)
            else:
                preview_builder.button(text=button_text, callback_data=button_callback)
        preview_builder.button(
            text=(get_setting("btn_back_to_menu_text") or "⬅️ Главное меню"),
            callback_data="open_main_menu",
        )
        preview_builder.adjust(1)
        preview_keyboard = preview_builder.as_markup()

        await message.answer(
            "Вот так будет выглядеть ваше сообщение. Отправляем?",
            reply_markup=keyboards.create_broadcast_confirmation_keyboard()
        )

        await _send_broadcast_to(bot, message.chat.id, original_message, preview_keyboard, parse_mode=parse_mode)

        await state.set_state(Broadcast.waiting_for_confirmation)

    @admin_router.callback_query(Broadcast.waiting_for_confirmation, F.data == "confirm_broadcast")
    async def confirm_broadcast_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.message.edit_text("⏳ Начинаю рассылку... Это может занять некоторое время.")

        data = await state.get_data()
        message_json = data.get('message_to_send')
        original_message = types.Message.model_validate_json(message_json)
        parse_mode = data.get('parse_mode')

        button_text = data.get('button_text')
        button_url = data.get('button_url')
        button_callback = data.get('button_callback')

        final_builder = InlineKeyboardBuilder()
        if button_text and (button_url or button_callback):
            if button_url:
                final_builder.button(text=button_text, url=button_url)
            else:
                final_builder.button(text=button_text, callback_data=button_callback)
        final_builder.button(
            text=(get_setting("btn_back_to_menu_text") or "⬅️ Главное меню"),
            callback_data="open_main_menu",
        )
        final_builder.adjust(1)
        final_keyboard = final_builder.as_markup()

        await state.clear()

        users = get_all_users()
        logger.info(f"Рассылка: Начинаем итерацию по {len(users)} пользователями.")

        sent_count = 0
        failed_count = 0
        banned_count = 0
        unreachable_count = 0
        email_only_count = 0

        for user in users:
            user_id = user['telegram_id']
            if user.get('is_banned'):
                banned_count += 1
                continue
            if user.get('is_unreachable'):
                unreachable_count += 1
                continue
            # Email-регистрация без авторизации через Telegram — боту некуда писать.
            if database.is_email_only_user(user_id):
                email_only_count += 1
                continue
            try:
                await _send_broadcast_to(bot, user_id, original_message, final_keyboard, parse_mode=parse_mode)
                sent_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed_count += 1
                if telegram_reachability.handle_send_exception(user_id, e):
                    unreachable_count += 1
                else:
                    logger.warning(f"Не удалось отправить сообщение рассылки пользователю {user_id}: {e}")

        await callback.message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"👍 Отправлено: {sent_count}\n"
            f"👎 Не удалось отправить: {failed_count}\n"
            f"🚫 Пропущено (забанены): {banned_count}\n"
            f"📵 Недоступны (блок/деактивация): {unreachable_count}\n"
            f"📧 Пропущено (email без Telegram): {email_only_count}"
        )
        await show_admin_menu(callback.message)

    @admin_router.callback_query(StateFilter(Broadcast), F.data == "cancel_broadcast")
    async def cancel_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Рассылка отменена.")
        await state.clear()
        await show_admin_menu(callback.message, edit_message=True)
