"""Реферальная программа: статистика, реквизиты выплат и заявки на вывод.
"""

import uuid
import json
from html import escape as html_escape
from ..callback_safety import (
    fast_callback_answer,
    catch_callback_errors,
)
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from shop_bot.data_manager.remnawave_repository import (
    add_to_balance,
    get_setting,
    get_user,
    get_balance,
    get_referral_count,
    add_to_referral_balance,
    deduct_from_referral_balance,
    get_referral_balance_all,
    get_referral_balance,
    list_referral_payout_methods,
    add_referral_payout_method,
    delete_referral_payout_method,
    get_referral_payout_method,
    create_referral_withdrawal_request,
    list_referral_withdrawal_requests,
    get_referral_top_rich,
    get_referral_rank_and_count,
    log_transaction,
)
from shop_bot.data_manager import remnawave_repository as rw_repo

__all__: list[str] = []


def register_referral(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(F.data == "show_referral_program")
    @registration_required
    async def referral_program_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        user_data = get_user(user_id)
        bot_username = (await callback.bot.get_me()).username

        webapp_link, referral_link = _build_referral_links(user_id, bot_username)
        referral_count = get_referral_count(user_id)
        try:
            total_ref_earned = float(get_referral_balance_all(user_id))
        except Exception:
            total_ref_earned = 0.0
        try:
            available_ref_balance = float(get_referral_balance(user_id))
        except Exception:
            available_ref_balance = 0.0

        # Referral bonuses text is driven by admin settings
        def _to_float_setting(key: str, default: float) -> float:
            raw = str(get_setting(key) or str(default)).strip()
            try:
                raw = raw.replace(",", ".")
                return float(raw)
            except Exception:
                return float(default)

        def _is_true_setting(key: str, default: bool = False) -> bool:
            raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
            return raw in {"1", "true", "yes", "on", "y"}

        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip() or "percent_purchase"
        percent = _to_float_setting("referral_percentage", 10.0)
        fixed_amount = _to_float_setting("fixed_referral_bonus_amount", 50.0)
        start_bonus = _to_float_setting("referral_on_start_referrer_amount", 20.0)
        days_bonus_enabled = _is_true_setting("enable_referral_days_bonus", default=True)

        def _fmt_num(x: float, decimals: int = 2) -> str:
            try:
                s = f"{x:.{decimals}f}"
                return s.rstrip("0").rstrip(".")
            except Exception:
                return str(x)

        if reward_type == "fixed_purchase":
            main_bonus = f"{_fmt_num(fixed_amount, 2)} ₽ бонуса"
        elif reward_type == "fixed_start_referrer":
            main_bonus = f"{_fmt_num(start_bonus, 2)} ₽ бонуса при старте"
        else:
            main_bonus = f"{_fmt_num(percent, 2)}% бонуса"

        extra_bonus = " +1 день подписки" if days_bonus_enabled else ""
        bonuses_line = f"<b>🏆 Бонусы за приглашения:</b>🌟 {main_bonus}{extra_bonus}"

        withdraw_enabled = _ref_withdraw_enabled()
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        can_withdraw_now = withdraw_enabled and available_ref_balance >= min_withdraw

        text_lines = [
            "👥 <b>Реферальная программа</b>",
            "",
        ]
        if referral_link:
            text_lines.append(f"<b>Ссылка в Telegram:</b>\n<code>{html_escape(referral_link)}</code>")
            text_lines.append("")
        if webapp_link:
            text_lines.append(f"<b>Ссылка на сайт:</b>\n<code>{html_escape(webapp_link)}</code>")
            text_lines.append("")
        text_lines.extend([
            "<b>🤝 Приглашайте друзей и получайте бонусы на каждом уровне! 💰</b>",
            "",
            bonuses_line,
            "",
            "<b>📊 Статистика приглашений:</b>",
            f"<b>👥 Приглашено пользователей:</b> {referral_count}",
            "",
            f"<b>💰 Заработано по рефералке (всего):</b> {total_ref_earned:.2f} ₽",
            f"<b>💼 Доступно к выводу:</b> {available_ref_balance:.2f} ₽",
        ])
        if withdraw_enabled:
            text_lines.append(f"<b>ℹ️ Минимальная сумма для вывода:</b> {min_withdraw:.0f} ₽")
        text = "\n".join(text_lines)

        share_text = _referral_share_text()

        builder = InlineKeyboardBuilder()
        if referral_link:
            share_tg = _telegram_share_url(referral_link, share_text)
            builder.button(
                text="📩 Поделиться (Telegram)" if webapp_link else "📩 Поделиться",
                url=share_tg,
            )
        if webapp_link:
            share_web = _telegram_share_url(webapp_link, share_text)
            builder.button(text="🌐 Поделиться (сайт)", url=share_web)
        builder.button(text="🔄 Перевести на баланс", callback_data="referral_transfer_start")
        if can_withdraw_now:
            builder.button(text="💸 Вывести", callback_data="referral_withdraw_start")
        if withdraw_enabled:
            builder.button(text="🧾 Способы получения", callback_data="referral_payout_methods")
            builder.button(text="📋 Запросы на вывод", callback_data="referral_withdraw_requests")
        builder.button(text="🏆 Топ-5", callback_data="show_referral_top")
        builder.button(text="⬅️ Назад", callback_data="back_to_main_menu")
        builder.adjust(1)
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup(), disable_web_page_preview=True
        )


    
    @user_router.callback_query(F.data == "show_referral_top")
    @registration_required
    async def referral_top_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id

        rank, personal_count = get_referral_rank_and_count(user_id)
        top_users = get_referral_top_rich(5)

        lines: list[str] = []
        lines.append(
            "Здесь можно увидеть топ людей, которые пригласили "
            "наибольшее количество рефералов в сервис.\n"
            "Учитываются те богачи, которые пополнили баланс хотя бы раз.\n"
        )

        lines.append("\n<b>Твоё место в рейтинге:</b>")
        if rank is not None and personal_count > 0:
            lines.append(f"\n{rank}. <code>{user_id}</code> - {personal_count} чел.")
        else:
            lines.append(
                "\nПока ты не участвуешь в рейтинге. "
                "Пригласи пользователей, которые пополнят баланс, "
                "и появишься здесь."
            )

        lines.append("\n\n<b>🏆 Топ-5 пригласивших:</b>\n")
        if top_users:
            for index, row in enumerate(top_users, start=1):
                uid = row.get("telegram_id") or row.get("referred_by")
                count = int(row.get("rich_referrals") or row.get("ref_count") or 0)
                uid_str = str(uid)
                if len(uid_str) > 5:
                    masked = uid_str[:5] + "*****"
                else:
                    masked = uid_str + "*****"
                lines.append(f"<blockquote>{index}. {masked} - {count} чел.</blockquote>")
        else:
            lines.append("\n\nПока ещё нет пользователей, которые попали бы в рейтинг.")

        text = "\n".join(lines)

        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ Назад", callback_data="show_referral_program")
        builder.button(text="🏠 Главное меню", callback_data="back_to_main_menu")
        builder.adjust(1, 1)
        await callback.message.edit_text(text, reply_markup=builder.as_markup())


    # =============================
    # Referral balance / withdrawal
    # =============================

    def _ref_is_true(key: str, default: bool = False) -> bool:
        raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
        return raw in {"1", "true", "yes", "on", "y"}

    def _ref_float_setting(key: str, default: float) -> float:
        raw = str(get_setting(key) or str(default)).strip().replace(",", ".")
        try:
            return float(raw)
        except Exception:
            return float(default)

    def _ref_withdraw_enabled() -> bool:
        return _ref_is_true("referral_withdraw_enabled", False)

    def _ref_method_enabled(method_type: str) -> dict:
        return {
            "sbp": _ref_is_true("referral_withdraw_sbp_enabled", False),
            "card": _ref_is_true("referral_withdraw_card_enabled", False),
            "usdt_trc20": _ref_is_true("referral_withdraw_usdt_enabled", False),
        }.get(method_type, False)

    def _ref_sbp_banks() -> list[str]:
        raw = get_setting("referral_withdraw_sbp_banks") or ""
        return [b.strip() for b in raw.split(",") if b.strip()]

    _REF_METHOD_LABELS = {"sbp": "СБП", "card": "Номер карты", "usdt_trc20": "USDT TRC20"}

    def _ref_mask(value: str) -> str:
        s = (value or "").strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return html_escape(s)
        last4 = digits[-4:]
        return "*" * max(0, len(digits) - 4) + last4

    def _kb_my_balance(withdraw_enabled: bool, can_withdraw_now: bool = False) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="🔄 Перевести на баланс", callback_data="referral_transfer_start")
        if can_withdraw_now:
            b.button(text="💸 Вывести", callback_data="referral_withdraw_start")
        if withdraw_enabled:
            b.button(text="🧾 Способы получения", callback_data="referral_payout_methods")
            b.button(text="📋 Запросы на вывод", callback_data="referral_withdraw_requests")
        b.button(text="⬅️ Назад", callback_data="show_referral_program")
        b.adjust(1)
        return b.as_markup()

    @user_router.callback_query(F.data == "referral_my_balance")
    @registration_required
    async def referral_my_balance(callback: types.CallbackQuery, state: FSMContext):
        # Оставлено для обратной совместимости со старыми сообщениями/кнопками —
        # теперь баланс отображается прямо на экране "Реферальная программа".
        await callback.answer()
        try:
            await state.clear()
        except Exception:
            pass
        await referral_program_handler(callback)

    _REF_STATUS_LABELS = {
        "new": "🕓 На рассмотрении",
        "processing": "⏳ В обработке",
        "paid": "✅ Выплачено",
        "rejected": "❌ Отклонено",
    }

    @user_router.callback_query(F.data == "referral_withdraw_requests")
    @catch_callback_errors
    async def referral_withdraw_requests(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        user_id = cb.from_user.id
        requests = list_referral_withdrawal_requests(user_id=user_id) or []
        lines = ["📋 <b>Запросы на вывод</b>", ""]
        if not requests:
            lines.append("У вас пока нет заявок на вывод средств.")
        else:
            for r in requests[:20]:
                status = _REF_STATUS_LABELS.get(r.get("status"), r.get("status"))
                amount = float(r.get("amount") or 0.0)
                label = _REF_METHOD_LABELS.get(r.get("method_type"), r.get("method_type"))
                masked = _ref_mask(str(r.get("requisite_value") or ""))
                extra = f" ({r.get('bank_name')})" if r.get("bank_name") else ""
                created = r.get("created_at") or ""
                lines.append(
                    f"• <b>{amount:.2f} ₽</b> — {label}{extra} •{masked}\n"
                    f"  Статус: {status}\n"
                    f"  Дата: {created}"
                )
                if r.get("status") == "rejected" and r.get("reject_reason"):
                    lines.append(f"  Причина: {html_escape(str(r.get('reject_reason')))}")
        b = InlineKeyboardBuilder()
        b.button(text="⬅️ Назад", callback_data="show_referral_program")
        b.adjust(1)
        await cb.message.edit_text("\n".join(lines), reply_markup=b.as_markup(), disable_web_page_preview=True)
        await fast_callback_answer(cb)


    @user_router.callback_query(F.data == "referral_transfer_start")
    @catch_callback_errors
    async def referral_transfer_start(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        user_id = cb.from_user.id
        balance = float(get_referral_balance(user_id) or 0.0)
        if balance <= 0:
            await cb.answer("На реферальном балансе нет средств.", show_alert=True)
            return
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="referral_my_balance")
        b.adjust(1)
        await state.set_state(ReferralWithdraw.waiting_transfer_amount)
        await cb.message.edit_text(
            f"🔄 <b>Перевод на основной баланс</b>\n\nДоступно на реферальном балансе: <b>{balance:.2f} ₽</b>\n\n"
            f"Введите сумму для перевода (например: <code>{balance:.0f}</code>), "
            f"минимальная сумма не ограничена:",
            reply_markup=b.as_markup(),
        )
        await fast_callback_answer(cb)

    @user_router.message(ReferralWithdraw.waiting_transfer_amount)
    @registration_required
    async def referral_transfer_amount(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer("Не понял сумму. Пришлите число, например 100.")
            return
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
        current = float(get_referral_balance(user_id) or 0.0)
        if amount > current:
            await message.answer(f"На реферальном балансе недостаточно средств. Доступно: {current:.2f} ₽.")
            return
        if not deduct_from_referral_balance(user_id, amount):
            await message.answer("❌ Не удалось списать средства с реферального баланса. Попробуйте позже.")
            return
        ok = add_to_balance(user_id, amount)
        if not ok:
            # Откатываем списание, если зачисление не удалось
            try:
                add_to_referral_balance(user_id, amount)
            except Exception:
                logger.error(f"Не удалось откатить перевод реферального баланса для {user_id} после неудачного зачисления.")
            await message.answer("❌ Не удалось зачислить средства на основной баланс. Попробуйте позже.")
            return
        try:
            log_username = message.from_user.username or f"@{user_id}"
            log_transaction(
                username=log_username,
                transaction_id=None,
                payment_id=str(uuid.uuid4()),
                user_id=user_id,
                status='paid',
                amount_rub=amount,
                amount_currency=None,
                currency_name=None,
                payment_method='ReferralTransfer',
                metadata=json.dumps({"action": "referral_transfer"})
            )
        except Exception as e:
            logger.warning(f"Не удалось залогировать перевод реферального баланса для {user_id}: {e}")
        try:
            await state.clear()
        except Exception:
            pass
        new_ref_balance = float(get_referral_balance(user_id) or 0.0)
        new_main_balance = float(get_balance(user_id) or 0.0)
        withdraw_enabled_now = _ref_withdraw_enabled()
        min_withdraw_now = _ref_float_setting("minimum_withdrawal", 100.0)
        await message.answer(
            f"✅ Переведено {amount:.2f} ₽ на основной баланс.\n\n"
            f"Реферальный баланс: {new_ref_balance:.2f} ₽\n"
            f"Основной баланс: {new_main_balance:.2f} ₽",
            reply_markup=_kb_my_balance(withdraw_enabled_now, new_ref_balance >= min_withdraw_now)
        )

    def _kb_payout_methods(items: list[dict], withdraw_enabled: bool) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        if withdraw_enabled:
            b.button(text="➕ Добавить способ", callback_data="referral_payout_method_add")
        for m in items[:20]:
            mid = int(m.get("id") or 0)
            if mid <= 0:
                continue
            label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
            masked = _ref_mask(str(m.get("requisite_value") or ""))
            extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
            b.button(text=f"🗑 {label}{extra} •{masked}", callback_data=f"rpm_delete:{mid}")
        b.button(text="⬅️ Назад", callback_data="referral_my_balance")
        b.adjust(1)
        return b.as_markup()

    @user_router.callback_query(F.data == "referral_payout_methods")
    @catch_callback_errors
    async def referral_payout_methods(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        withdraw_enabled = _ref_withdraw_enabled()
        if not withdraw_enabled:
            await cb.answer("Вывод средств временно недоступен.", show_alert=True)
            return
        user_id = cb.from_user.id
        items = list_referral_payout_methods(user_id) or []
        lines = ["🧾 <b>Способы получения</b>", ""]
        if not items:
            lines.append("Пока нет сохранённых способов получения.\nНажмите «Добавить способ».")
        else:
            for i, m in enumerate(items, 1):
                label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
                masked = _ref_mask(str(m.get("requisite_value") or ""))
                extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
                lines.append(f"{i}. {label}{extra}: <code>{masked}</code>")
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=_kb_payout_methods(items, withdraw_enabled), disable_web_page_preview=True
        )
        await fast_callback_answer(cb)

    def _kb_method_types() -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        if _ref_method_enabled("sbp"):
            b.button(text="🏦 СБП", callback_data="rpm_add_type:sbp")
        if _ref_method_enabled("card"):
            b.button(text="💳 Номер карты", callback_data="rpm_add_type:card")
        if _ref_method_enabled("usdt_trc20"):
            b.button(text="💵 USDT TRC20", callback_data="rpm_add_type:usdt_trc20")
        b.button(text="❌ Отмена", callback_data="referral_payout_methods")
        b.adjust(1)
        return b.as_markup()

    @user_router.callback_query(F.data == "referral_payout_method_add")
    @catch_callback_errors
    async def referral_payout_method_add(cb: types.CallbackQuery, state: FSMContext):
        if not _ref_withdraw_enabled():
            await cb.answer("Недоступно.", show_alert=True)
            return
        if not (_ref_method_enabled("sbp") or _ref_method_enabled("card") or _ref_method_enabled("usdt_trc20")):
            await cb.answer("Администратор пока не подключил ни одного способа получения.", show_alert=True)
            return
        await cb.message.edit_text(
            "Выберите способ получения:", reply_markup=_kb_method_types()
        )
        await fast_callback_answer(cb)

    def _kb_bank_choice(banks: list[str]) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        for i, bank in enumerate(banks[:30]):
            b.button(text=bank, callback_data=f"rpm_bank:{i}")
        b.button(text="❌ Отмена", callback_data="referral_payout_methods")
        b.adjust(2)
        return b.as_markup()

    @user_router.callback_query(F.data.startswith("rpm_add_type:"))
    @catch_callback_errors
    async def referral_payout_method_add_type(cb: types.CallbackQuery, state: FSMContext):
        method_type = (cb.data or "").split(":", 1)[1]
        if not _ref_method_enabled(method_type):
            await cb.answer("Этот способ временно недоступен.", show_alert=True)
            return
        await state.update_data(rpm_type=method_type)
        if method_type == "sbp":
            banks = _ref_sbp_banks()
            if not banks:
                await cb.answer("Список банков не настроен администратором.", show_alert=True)
                return
            await state.update_data(rpm_banks=banks)
            await state.set_state(ReferralWithdraw.waiting_method_bank)
            await cb.message.edit_text("🏦 Выберите банк:", reply_markup=_kb_bank_choice(banks))
        else:
            await state.set_state(ReferralWithdraw.waiting_method_value)
            prompt = "💳 Введите номер карты:" if method_type == "card" else "💵 Введите адрес кошелька USDT TRC20:"
            await cb.message.edit_text(prompt, reply_markup=_kb_payout_methods([], True))
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data.startswith("rpm_bank:"), ReferralWithdraw.waiting_method_bank)
    @catch_callback_errors
    async def referral_payout_method_bank_choice(cb: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        banks = data.get("rpm_banks") or []
        try:
            idx = int((cb.data or "").split(":", 1)[1])
            bank = banks[idx]
        except Exception:
            await cb.answer("Некорректный выбор.", show_alert=True)
            return
        await state.update_data(rpm_bank=bank)
        await state.set_state(ReferralWithdraw.waiting_method_value)
        await cb.message.edit_text(
            f"🏦 Банк: <b>{html_escape(bank)}</b>\n\nВведите номер телефона (СБП):",
        )
        await fast_callback_answer(cb)

    @user_router.message(ReferralWithdraw.waiting_method_value)
    @registration_required
    async def referral_payout_method_value(message: types.Message, state: FSMContext):
        data = await state.get_data()
        method_type = data.get("rpm_type")
        bank = data.get("rpm_bank")
        value = (message.text or "").strip()
        if not value:
            await message.answer("Значение не может быть пустым. Попробуйте снова.")
            return
        ok, msg, _new_id = add_referral_payout_method(message.from_user.id, method_type, value, bank_name=bank)
        await message.answer(("✅ " if ok else "❌ ") + msg)
        try:
            await state.clear()
        except Exception:
            pass
        items = list_referral_payout_methods(message.from_user.id) or []
        withdraw_enabled = _ref_withdraw_enabled()
        lines = ["🧾 <b>Способы получения</b>", ""]
        for i, m in enumerate(items, 1):
            label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
            masked = _ref_mask(str(m.get("requisite_value") or ""))
            extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
            lines.append(f"{i}. {label}{extra}: <code>{masked}</code>")
        await message.answer("\n".join(lines), reply_markup=_kb_payout_methods(items, withdraw_enabled))

    @user_router.callback_query(F.data.startswith("rpm_delete:"))
    @catch_callback_errors
    async def referral_payout_method_delete(cb: types.CallbackQuery, state: FSMContext):
        try:
            mid = int((cb.data or "").split(":", 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        ok, msg = delete_referral_payout_method(mid, cb.from_user.id)
        await cb.answer(("✅ " if ok else "❌ ") + msg, show_alert=not ok)
        items = list_referral_payout_methods(cb.from_user.id) or []
        withdraw_enabled = _ref_withdraw_enabled()
        lines = ["🧾 <b>Способы получения</b>", ""]
        if not items:
            lines.append("Пока нет сохранённых способов получения.")
        else:
            for i, m in enumerate(items, 1):
                label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
                masked = _ref_mask(str(m.get("requisite_value") or ""))
                extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
                lines.append(f"{i}. {label}{extra}: <code>{masked}</code>")
        await cb.message.edit_text(
            "\n".join(lines), reply_markup=_kb_payout_methods(items, withdraw_enabled), disable_web_page_preview=True
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data == "referral_withdraw_start")
    @catch_callback_errors
    async def referral_withdraw_start(cb: types.CallbackQuery, state: FSMContext):
        try:
            await state.clear()
        except Exception:
            pass
        if not _ref_withdraw_enabled():
            await cb.answer("Вывод средств временно недоступен.", show_alert=True)
            return
        user_id = cb.from_user.id
        balance = float(get_referral_balance(user_id) or 0.0)
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        if balance < min_withdraw:
            await cb.answer(
                f"Минимальная сумма для вывода {min_withdraw:.0f} ₽. У вас {balance:.2f} ₽.", show_alert=True
            )
            return
        items = [
            m for m in (list_referral_payout_methods(user_id) or [])
            if _ref_method_enabled((m.get("method_type") or "").strip().lower())
        ]
        if not items:
            await cb.message.edit_text(
                "🧾 Сначала добавьте способ получения средств.",
                reply_markup=_kb_payout_methods([], True),
            )
            await fast_callback_answer(cb)
            return
        b = InlineKeyboardBuilder()
        for m in items[:20]:
            mid = int(m.get("id") or 0)
            label = _REF_METHOD_LABELS.get(m.get("method_type"), m.get("method_type"))
            masked = _ref_mask(str(m.get("requisite_value") or ""))
            extra = f" ({m.get('bank_name')})" if m.get("bank_name") else ""
            b.button(text=f"{label}{extra} •{masked}", callback_data=f"rwd_method:{mid}")
        b.button(text="❌ Отмена", callback_data="referral_my_balance")
        b.adjust(1)
        await state.set_state(ReferralWithdraw.waiting_withdraw_choose_method)
        await cb.message.edit_text(
            f"💸 <b>Вывод средств</b>\n\nДоступно: <b>{balance:.2f} ₽</b>\n\nВыберите способ получения:",
            reply_markup=b.as_markup(),
        )
        await fast_callback_answer(cb)

    @user_router.callback_query(F.data.startswith("rwd_method:"), ReferralWithdraw.waiting_withdraw_choose_method)
    @catch_callback_errors
    async def referral_withdraw_choose_method(cb: types.CallbackQuery, state: FSMContext):
        try:
            mid = int((cb.data or "").split(":", 1)[1])
        except Exception:
            await cb.answer("Некорректные данные.", show_alert=True)
            return
        method = get_referral_payout_method(mid, cb.from_user.id)
        if not method:
            await cb.answer("Способ получения не найден.", show_alert=True)
            return
        balance = float(get_referral_balance(cb.from_user.id) or 0.0)
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        await state.update_data(rwd_method_id=mid)
        await state.set_state(ReferralWithdraw.waiting_withdraw_amount)
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="referral_withdraw_start")
        b.adjust(1)
        await cb.message.edit_text(
            f"Доступно: <b>{balance:.2f} ₽</b>\nМинимум: <b>{min_withdraw:.0f} ₽</b>\n\n"
            f"Введите сумму для вывода числом (например: <code>{min_withdraw:.0f}</code>):",
            reply_markup=b.as_markup(),
        )
        await fast_callback_answer(cb)

    @user_router.message(ReferralWithdraw.waiting_withdraw_amount)
    @registration_required
    async def referral_withdraw_amount(message: types.Message, state: FSMContext):
        if not _ref_withdraw_enabled():
            await message.answer("Вывод средств временно недоступен.")
            try:
                await state.clear()
            except Exception:
                pass
            return
        data = await state.get_data()
        method_id = data.get("rwd_method_id")
        min_withdraw = _ref_float_setting("minimum_withdrawal", 100.0)
        raw = (message.text or "").replace(",", ".").strip()
        try:
            amount = float(raw)
        except Exception:
            await message.answer(f"Не понял сумму. Пришлите число, например {min_withdraw:.0f}.")
            return
        if amount < min_withdraw:
            await message.answer(f"Минимальная сумма для вывода: {min_withdraw:.0f} ₽.")
            return
        ok, msg, new_id = create_referral_withdrawal_request(message.from_user.id, amount, int(method_id))
        await message.answer(("✅ " if ok else "❌ ") + msg)
        if ok and new_id:
            method = get_referral_payout_method(int(method_id))
            admin_text = rw_repo.format_referral_withdrawal_admin_notice(
                request_id=new_id,
                user_id=message.from_user.id,
                username=message.from_user.username,
                amount=amount,
                method_type=(method or {}).get("method_type"),
                bank_name=(method or {}).get("bank_name"),
                requisite_value=(method or {}).get("requisite_value"),
            )
            for admin_id in (rw_repo.get_admin_ids() or set()):
                try:
                    await message.bot.send_message(int(admin_id), admin_text, parse_mode="HTML")
                except Exception:
                    logger.warning(
                        "Не удалось уведомить администратора %s о заявке на вывод",
                        admin_id,
                        exc_info=True,
                    )
        try:
            await state.clear()
        except Exception:
            pass
        withdraw_enabled = _ref_withdraw_enabled()
        balance = float(get_referral_balance(message.from_user.id) or 0.0)
        min_withdraw_now = _ref_float_setting("minimum_withdrawal", 100.0)
        lines = ["💼 <b>Мой баланс</b>", "", f"Реферальный баланс: <b>{balance:.2f} ₽</b>"]
        await message.answer("\n".join(lines), reply_markup=_kb_my_balance(withdraw_enabled, balance >= min_withdraw_now))
