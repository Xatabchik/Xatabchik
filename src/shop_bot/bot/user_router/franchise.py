"""Кабинет партнёра-франчайзи: реквизиты, создание бота и вывод средств.
"""

from html import escape as html_escape
from ..callback_safety import (
    fast_callback_answer,
    catch_callback_errors,
)
from aiogram import (
    Router,
    F,
    Bot,
    types,
)
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties
from shop_bot.data_manager.remnawave_repository import get_setting
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.factory_bot.runtime import get_service
from shop_bot.data_manager.database import (
    get_franchise_min_withdraw,
    get_franchise_percent_default,
)

__all__: list[str] = []


def register_franchise(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""


    # =============================
    # Franchise (clone bots)
    # =============================

    def _kb_cancel_factory() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="factory_cancel")
        b.adjust(1)
        return b.as_markup()

    def _kb_partner_cabinet() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="💳 Реквизиты", callback_data="partner_requisites")
        b.button(text="💸 Вывод средств", callback_data="partner_withdraw")
        b.button(text="🗑 Удалить моего бота", callback_data="factory_del_self")
        b.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
        b.adjust(1, 1, 1, 1)
        return b.as_markup()

    def _kb_partner_withdraw() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="partner_withdraw_cancel")
        b.adjust(1)
        return b.as_markup()


    def _kb_partner_requisites(items: list[dict] | None = None) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="➕ Добавить карту", callback_data="partner_requisite_add")
        items = items or []
        # One row per action to keep callback_data short and stable
        for r in items[:20]:
            rid = int(r.get("id") or 0)
            if rid <= 0:
                continue
            is_def = int(r.get("is_default") or 0) == 1
            if not is_def:
                b.button(text=f"✅ Сделать основной #{rid}", callback_data=f"req_set_default:{rid}")
            b.button(text=f"🗑 Удалить #{rid}", callback_data=f"req_delete:{rid}")
        b.button(text="⬅️ Назад", callback_data="partner_cabinet")
        b.adjust(1)
        return b.as_markup()

    def _kb_partner_requisite_input() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="partner_requisite_cancel")
        b.adjust(1)
        return b.as_markup()

    def _mask_requisite(value: str, rtype: str) -> str:
        s = (value or '').strip()
        digits = ''.join(ch for ch in s if ch.isdigit())
        if not digits:
            return s
        last4 = digits[-4:]
        masked = '*' * max(0, len(digits) - 4) + last4
        # group in 4s for cards
        if (rtype or '').lower() == 'card' and len(digits) >= 12:
            parts = [masked[max(0, i-4):i] for i in range(len(masked), 0, -4)]
            masked = ' '.join(reversed(parts))
        return masked

    def _infer_requisite_type(value: str) -> str:
        digits = ''.join(ch for ch in (value or '') if ch.isdigit())
        # heuristic: 10-12 digits - чаще телефон, 13-19 - чаще карта
        if 10 <= len(digits) <= 12:
            return 'phone'
        if 13 <= len(digits) <= 19:
            return 'card'
        # fallback
        return 'card'

    @user_router.callback_query(F.data == "partner_requisites")
    @catch_callback_errors
    async def partner_requisites(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        try:
            await state.clear()
        except Exception:
            pass
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Реквизиты доступны только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Доступно только владельцу.", show_alert=True)
            return

        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        lines = ["💳 <b>Реквизиты</b>", ""]
        if not items:
            lines.append("Пока нет привязанных реквизитов.")
            lines.append("Нажмите <b>«Добавить карту»</b> и укажите банк и номер карты или телефона.")
        else:
            for i, r in enumerate(items, 1):
                bank = html_escape(str(r.get('bank') or ''))
                rtype = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rtype == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rtype)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank} — {label}: <code>{masked}</code> (id={r.get('id')})")
        text = "\n".join(lines)
        await cb.message.edit_text(text, reply_markup=_kb_partner_requisites(items), disable_web_page_preview=True)
        await fast_callback_answer(cb)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_requisite_add")
    @catch_callback_errors
    async def partner_requisite_add(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Доступно только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Только владелец.", show_alert=True)
            return

        await state.set_state(FranchiseStates.waiting_requisites_bank)
        await cb.message.edit_text(
            "🏦 <b>Добавление реквизитов</b>\n\nВведите название банка (например: <code>Тинькофф</code>):",
            reply_markup=_kb_partner_requisite_input(),
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_requisite_cancel")
    @catch_callback_errors
    async def partner_requisite_cancel(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        try:
            await state.clear()
        except Exception:
            pass
        try:
            await partner_requisites(cb, state, bot)
        except Exception:
            try:
                await partner_cabinet(cb, bot)
            except Exception:
                pass
        await fast_callback_answer(cb)

    @user_router.message(FranchiseStates.waiting_requisites_bank)
    @registration_required
    async def partner_requisite_bank(message: types.Message, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(message.from_user.id) != owner_id:
            await message.answer("Только владелец.")
            try:
                await state.clear()
            except Exception:
                pass
            return

        bank = (message.text or '').strip()
        if not bank:
            await message.answer("Укажите банк текстом.")
            return
        await state.update_data(req_bank=bank)
        await state.set_state(FranchiseStates.waiting_requisites_value)
        await message.answer(
            "💳 Теперь пришлите <b>номер карты</b> или <b>номер телефона</b> (как удобно):",
            reply_markup=_kb_partner_requisite_input(),
        )

    @user_router.message(FranchiseStates.waiting_requisites_value)
    @registration_required
    async def partner_requisite_value(message: types.Message, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(message.from_user.id) != owner_id:
            await message.answer("Только владелец.")
            try:
                await state.clear()
            except Exception:
                pass
            return

        data = await state.get_data()
        bank = (data.get('req_bank') or '').strip()
        value = (message.text or '').strip()
        if not bank:
            await message.answer("Не вижу банк. Попробуйте ещё раз.")
            await state.set_state(FranchiseStates.waiting_requisites_bank)
            return
        if not value:
            await message.answer("Укажите номер карты или телефона.")
            return

        rtype = _infer_requisite_type(value)
        ok, msg, _new_id = rw_repo.add_partner_requisite(bot_id, owner_id, bank, value, rtype)
        await message.answer(("✅ " if ok else "❌ ") + msg)
        try:
            await state.clear()
        except Exception:
            pass

        # show list
        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        lines = ["💳 <b>Реквизиты</b>", ""]
        if not items:
            lines.append("Пока нет привязанных реквизитов.")
        else:
            for i, r in enumerate(items, 1):
                bank_e = html_escape(str(r.get('bank') or ''))
                rt = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rt == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rt)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank_e} — {label}: <code>{masked}</code> (id={r.get('id')})")
        await message.answer("\n".join(lines), reply_markup=_kb_partner_requisites(items))

    @user_router.callback_query(F.data.startswith("req_set_default:"))
    @catch_callback_errors
    async def partner_requisite_set_default(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if bot_id <= 0 or int(cb.from_user.id) != owner_id:
            await cb.answer("Недостаточно прав.", show_alert=True)
            return
        try:
            rid = int((cb.data or '').split(':', 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        ok, msg = rw_repo.set_default_partner_requisite(rid, bot_id, owner_id)
        await cb.answer(("✅ " if ok else "❌ ") + msg, show_alert=not ok)
        # refresh
        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        try:
            await partner_requisites(cb, state, bot)
        except Exception:
            # rebuild text quickly
            lines = ["💳 <b>Реквизиты</b>", ""]
            for i, r in enumerate(items, 1):
                bank_e = html_escape(str(r.get('bank') or ''))
                rt = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rt == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rt)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank_e} — {label}: <code>{masked}</code> (id={r.get('id')})")
            await cb.message.edit_text("\n".join(lines), reply_markup=_kb_partner_requisites(items), disable_web_page_preview=True)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data.startswith("req_delete:"))
    @catch_callback_errors
    async def partner_requisite_delete(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if bot_id <= 0 or int(cb.from_user.id) != owner_id:
            await cb.answer("Недостаточно прав.", show_alert=True)
            return
        try:
            rid = int((cb.data or '').split(':', 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        ok, msg = rw_repo.delete_partner_requisite(rid, bot_id, owner_id)
        await cb.answer(("✅ " if ok else "❌ ") + msg, show_alert=not ok)
        # refresh list
        items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
        lines = ["💳 <b>Реквизиты</b>", ""]
        if not items:
            lines.append("Пока нет привязанных реквизитов.")
        else:
            for i, r in enumerate(items, 1):
                bank_e = html_escape(str(r.get('bank') or ''))
                rt = (r.get('requisite_type') or 'card')
                label = 'Номер карты' if rt == 'card' else 'Телефон'
                masked = html_escape(_mask_requisite(str(r.get('requisite_value') or ''), str(rt)))
                star = '⭐ ' if int(r.get('is_default') or 0) == 1 else ''
                lines.append(f"{star}<b>{i}.</b> {bank_e} — {label}: <code>{masked}</code> (id={r.get('id')})")
        await cb.message.edit_text("\n".join(lines), reply_markup=_kb_partner_requisites(items), disable_web_page_preview=True)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "factory_create_bot")
    @catch_callback_errors
    async def franchise_create_bot(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        # Creation is allowed only from the root bot UI
        try:
            current_bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        except Exception:
            current_bot_id = 0
        if current_bot_id > 0:
            await cb.answer("Создание бота доступно только в основном боте.", show_alert=True)
            return

        text = (
            "🤖 <b>Отправьте Token вашего бота</b>\n\n"
            "1. Перейдите в @BotFather\n"
            "2. Создайте нового бота (/newbot)\n"
            "3. Скопируйте API TOKEN\n"
            "4. Пришлите его в этот чат сообщением 👇"
        )
        await state.set_state(FranchiseStates.waiting_bot_token)
        try:
            await cb.message.edit_text(text, reply_markup=_kb_cancel_factory())
        except Exception:
            await cb.message.answer(text, reply_markup=_kb_cancel_factory())
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "factory_cancel")
    @catch_callback_errors
    async def franchise_cancel(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        try:
            await show_main_menu(cb.message, edit_message=True)
        except Exception:
            pass
        await fast_callback_answer(cb)

    @user_router.message(FranchiseStates.waiting_bot_token)
    @registration_required
    async def franchise_receive_token(message: types.Message, state: FSMContext, bot: Bot):
        token = (message.text or "").strip()
        if not TOKEN_RE.match(token):
            await message.answer("Похоже, это не токен. Пришлите токен в формате <code>123456:ABC...</code>.")
            return

        # Validate token
        try:
            tmp_bot = Bot(token=token)
            me = await tmp_bot.get_me()
            try:
                await tmp_bot.close()
            except Exception:
                try:
                    await tmp_bot.session.close()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            await message.answer("Не получилось проверить токен. Убедитесь, что он правильный и бот не заблокирован.")
            return

        ok, msg, new_bot_id = rw_repo.create_managed_bot(
            token=token,
            telegram_bot_user_id=me.id,
            username=getattr(me, "username", None),
            owner_telegram_id=message.from_user.id,
            referrer_bot_id=0,
        )
        if not ok or not new_bot_id:
            await message.answer(f"❌ {msg}")
            try:
                await state.clear()
            except Exception:
                pass
            return

        # Start the new bot immediately (if service is running)
        service = get_service()
        if service:
            try:
                await service.start_bot(new_bot_id)
            except Exception as e:
                logger.warning(f"Failed to start managed bot {new_bot_id}: {e}")

        uname = f"@{me.username}" if getattr(me, "username", None) else f"(id {me.id})"
        await message.answer(
            f"✅ Бот {uname} подключён.\n\n"
            "Откройте его и нажмите /start — у владельца появится кнопка «Личный кабинет»."
        )
        try:
            await state.clear()
        except Exception:
            pass

        # Return user to main menu
        try:
            await show_main_menu(message)
        except Exception:
            pass

    @user_router.callback_query(F.data == "partner_cabinet")
    @catch_callback_errors
    async def partner_cabinet(cb: types.CallbackQuery, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Кабинет доступен только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Кабинет доступен только владельцу.", show_alert=True)
            return

        st = rw_repo.get_partner_cabinet(bot_id) or {}
        gross = float(st.get("gross_paid_card", 0.0) or 0.0)
        com_total = float(st.get("commission_total", 0.0) or 0.0)
        avail = float(st.get("available", 0.0) or 0.0)
        users = int(st.get("total_users", 0) or 0)

        text = (
            "👤 <b>Личный кабинет</b>\n\n"
            f"Бот: @{info.get('username') or 'без_username'}\n"
            f"Пользователей: <b>{users}</b>\n\n"
            f"Оплачено картой: <b>{gross:.2f} ₽</b>\n"
            f"Ваш процент: <b>{get_franchise_percent_default():.1f}%</b>\n"
            f"Ваш доход: <b>{com_total:.2f} ₽</b>\n"
            f"Доступно к выводу: <b>{avail:.2f} ₽</b>\n\n"
            f"ℹ️ Минимальная сумма вывода: <b>{get_franchise_min_withdraw():.0f} ₽</b>\n"
        )
        await cb.message.edit_text(text, reply_markup=_kb_partner_cabinet(), disable_web_page_preview=True)
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_withdraw")
    @catch_callback_errors
    async def partner_withdraw(cb: types.CallbackQuery, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        if bot_id <= 0:
            await cb.answer("Вывод доступен только в клонах.", show_alert=True)
            return
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(cb.from_user.id) != owner_id:
            await cb.answer("Только владелец.", show_alert=True)
            return

        st = rw_repo.get_partner_cabinet(bot_id) or {}
        avail = float(st.get("available", 0.0) or 0.0)

        # Require payout requisites
        default_req = rw_repo.get_default_partner_requisite(bot_id, owner_id)
        if not default_req:
            items = rw_repo.list_partner_requisites(bot_id, owner_id) or []
            await cb.message.edit_text(
                "💳 <b>Реквизиты не указаны</b>\n\n"
                "Сначала добавьте реквизиты для вывода (банк + номер карты или телефона).",
                reply_markup=_kb_partner_requisites(items),
            )
            await fast_callback_answer(cb)
            return

        await state.set_state(FranchiseStates.waiting_withdraw_amount)
        await cb.message.edit_text(
            "💸 <b>Вывод средств</b>\n\n"
            f"Доступно: <b>{avail:.2f} ₽</b>\n"
            f"Минимум: <b>{get_franchise_min_withdraw():.0f} ₽</b>\n\n"
            f"Введите сумму для вывода числом (например: <code>{get_franchise_min_withdraw():.0f}</code>):",
            reply_markup=_kb_partner_withdraw(),
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "partner_withdraw_cancel")
    @catch_callback_errors
    async def partner_withdraw_cancel(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        # show cabinet again
        try:
            await partner_cabinet(cb, cb.bot)
        except Exception:
            try:
                await show_main_menu(cb.message, edit_message=True)
            except Exception:
                pass
        await fast_callback_answer(cb)

    @user_router.message(FranchiseStates.waiting_withdraw_amount)
    @registration_required
    async def partner_withdraw_amount(message: types.Message, state: FSMContext, bot: Bot):
        bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
        info = rw_repo.get_managed_bot(bot_id) or {}
        owner_id = int(info.get("owner_telegram_id") or 0)
        if int(message.from_user.id) != owner_id:
            await message.answer("Только владелец.")
            try:
                await state.clear()
            except Exception:
                pass
            return

        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer(f"Не понял сумму. Пришлите число, например <code>{get_franchise_min_withdraw():.0f}</code>.")
            return

        # Attach payout requisites snapshot to the withdraw request
        default_req = rw_repo.get_default_partner_requisite(bot_id, owner_id)
        if not default_req:
            await message.answer(
                "💳 Реквизиты не указаны. Сначала добавьте банк и номер карты/телефона, затем повторите вывод.",
                reply_markup=_kb_partner_requisites(rw_repo.list_partner_requisites(bot_id, owner_id) or []),
            )
            try:
                await state.clear()
            except Exception:
                pass
            return

        bank = str(default_req.get('bank') or '')
        rtype = str(default_req.get('requisite_type') or 'card')
        rvalue = str(default_req.get('requisite_value') or '')
        rid = int(default_req.get('id') or 0) or None

        ok, msg = rw_repo.create_withdraw_request(
            bot_id,
            owner_id,
            amount,
            bank=bank,
            requisite_type=rtype,
            requisite_value=rvalue,
            requisite_id=rid,
        )
        await message.answer(("✅ " if ok else "❌ ") + msg)

        # Notify admin from the ROOT bot token so the admin always receives it
        if ok:
            try:
                admin_id_raw = get_setting("admin_telegram_id")
                admin_id = int(str(admin_id_raw).strip()) if admin_id_raw else None
            except Exception:
                admin_id = None

            if admin_id:
                try:
                    root_token = (get_setting("telegram_bot_token") or "").strip()
                    if root_token:
                        tmp = Bot(token=root_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
                        try:
                            await tmp.send_message(
                                admin_id,
                                (
                                    "💸 <b>Заявка на вывод</b>\n"
                                    f"Бот: @{info.get('username') or 'без_username'} (bot_id={bot_id})\n"
                                    f"Владелец: <code>{owner_id}</code>\n"
                                    f"Сумма: <b>{amount:.2f} ₽</b>\n"
                                    f"Реквизиты: <b>{html_escape(str(default_req.get('bank') or ''))}</b> — <code>{html_escape(str(default_req.get('requisite_value') or ''))}</code>"
                                ),
                            )
                        finally:
                            try:
                                await tmp.close()
                            except Exception:
                                try:
                                    await tmp.session.close()
                                except Exception:
                                    pass
                except Exception:
                    pass

        try:
            await state.clear()
        except Exception:
            pass

        # Show cabinet again
        try:
            st = rw_repo.get_partner_cabinet(bot_id) or {}
            await message.answer(
                "📊 Обновляю кабинет...",
            )
            # reuse cabinet view
            fake_cb = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message)
            # Can't construct reliably; instead just show main menu which contains cabinet button
        except Exception:
            pass
        try:
            await show_main_menu(message)
        except Exception:
            pass

