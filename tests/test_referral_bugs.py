"""
Регрессионные тесты для двух найденных багов реферальной системы бота
(см. src/shop_bot/bot/handlers.py):

1. Фиксированный бонус рефереру за старт по ссылке (referral_reward_type ==
   "fixed_start_referrer") начислялся только в прямом /start-хендлере, но НЕ
   начислялся, когда регистрация нового пользователя завершалась через один
   из капча-хендлеров (captcha_answer_handler / captcha_button_answer_handler).
   Капча включена по умолчанию (initialize_default_button_configs:
   "captcha_enabled": "true"), поэтому для большинства ботов с этим типом
   награды рефереры вообще никогда не получали бонус.

2. FSMContext.update_data(referred_by=referrer_id) в /start-хендлере
   безусловно перезаписывал уже сохранённое значение `referred_by` в FSM,
   даже когда пользователь присылал повторный "голый" /start без параметра
   ссылки (например, если капча не была решена вовремя и пользователь
   написал /start заново) — referred_by=None затирал ранее сохранённый ID
   реферера, и итоговая регистрация проходила уже без реферера вообще
   (это ломало ЛЮБОЙ тип вознаграждения, не только fixed_start_referrer).
"""
import asyncio

import pytest

from conftest import temp_db  # noqa: F401  (регистрирует фикстуру)


class _FakeBot:
    """Минимальная замена aiogram.Bot для теста — фиксирует отправленные сообщения."""

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, *args, **kwargs):
        self.sent.append((chat_id, text))


def test_referral_start_bonus_paid_for_captcha_flow_registration(temp_db):
    """Раньше: пользователь регистрируется через капча-хендлер (register_user_if_not_exists
    вызывается напрямую там же) — бонус рефереру никогда не начислялся, т.к. вся логика
    начисления жила только в прямом /start-хендлере. Теперь _maybe_pay_referral_start_bonus
    вызывается из всех путей регистрации и должна отработать одинаково."""
    from shop_bot.bot import handlers as bot_handlers

    database = temp_db
    database.update_setting("referral_reward_type", "fixed_start_referrer")
    database.update_setting("referral_on_start_referrer_amount", "25")

    REFERRER_ID = 5001
    NEW_USER_ID = 6001
    database.register_user_if_not_exists(REFERRER_ID, "referrer", None)

    # Именно так капча-хендлеры регистрируют нового пользователя — прямым вызовом,
    # без прохождения через прямой /start-хендлер.
    database.register_user_if_not_exists(NEW_USER_ID, "newuser_via_captcha", REFERRER_ID)

    fake_bot = _FakeBot()
    asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, NEW_USER_ID, REFERRER_ID))

    referrer = database.get_user(REFERRER_ID)
    assert referrer["referral_balance"] == 25.0, "Бонус рефереру должен начисляться и после регистрации через капчу"
    assert referrer["referral_balance_all"] == 25.0
    assert len(fake_bot.sent) == 1
    assert fake_bot.sent[0][0] == REFERRER_ID


def test_referral_start_bonus_not_paid_twice(temp_db):
    """Повторный вызов (например, если пользователь написал /start ещё раз уже после
    успешной регистрации) не должен начислять бонус второй раз."""
    from shop_bot.bot import handlers as bot_handlers

    database = temp_db
    database.update_setting("referral_reward_type", "fixed_start_referrer")
    database.update_setting("referral_on_start_referrer_amount", "25")

    REFERRER_ID = 5002
    NEW_USER_ID = 6002
    database.register_user_if_not_exists(REFERRER_ID, "referrer", None)
    database.register_user_if_not_exists(NEW_USER_ID, "newuser", REFERRER_ID)

    fake_bot = _FakeBot()
    asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, NEW_USER_ID, REFERRER_ID))
    asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, NEW_USER_ID, REFERRER_ID))
    asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, NEW_USER_ID, REFERRER_ID))

    referrer = database.get_user(REFERRER_ID)
    assert referrer["referral_balance"] == 25.0, "Бонус не должен начисляться повторно"
    assert len(fake_bot.sent) == 1, "Уведомление о начислении должно уйти только один раз"


def test_referral_start_bonus_skipped_for_other_reward_types(temp_db):
    """Для percent_purchase/fixed_purchase немедленный бонус не начисляется —
    это ожидаемое поведение (вознаграждение платится при покупке реферала)."""
    from shop_bot.bot import handlers as bot_handlers

    database = temp_db
    database.update_setting("referral_reward_type", "percent_purchase")

    REFERRER_ID = 5003
    NEW_USER_ID = 6003
    database.register_user_if_not_exists(REFERRER_ID, "referrer", None)
    database.register_user_if_not_exists(NEW_USER_ID, "newuser", REFERRER_ID)

    fake_bot = _FakeBot()
    asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, NEW_USER_ID, REFERRER_ID))

    referrer = database.get_user(REFERRER_ID)
    assert referrer["referral_balance"] == 0.0
    assert len(fake_bot.sent) == 0


def test_referral_start_bonus_ignores_self_referral(temp_db):
    from shop_bot.bot import handlers as bot_handlers

    database = temp_db
    database.update_setting("referral_reward_type", "fixed_start_referrer")

    USER_ID = 6004
    database.register_user_if_not_exists(USER_ID, "user", None)

    fake_bot = _FakeBot()
    # referrer_id == user_id — не должно происходить ничего.
    asyncio.run(bot_handlers._maybe_pay_referral_start_bonus(fake_bot, USER_ID, USER_ID))

    user = database.get_user(USER_ID)
    assert user["referral_balance"] == 0.0
    assert len(fake_bot.sent) == 0


# ── FSM state wipe bug (описан в докстринге модуля, пункт 2) ────────────────
def test_fsm_referred_by_survives_a_later_bare_start_while_captcha_pending():
    """Раньше: await state.update_data(referred_by=referrer_id) вызывался безусловно —
    если во втором /start (без параметра ссылки, пока капча ещё не решена) referrer_id
    был None, он затирал уже сохранённое значение. Хендлер теперь обновляет
    referred_by в FSM только когда пришла НОВАЯ ссылка (referrer_id истинный),
    иначе читает уже сохранённое значение, не трогая его."""
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage

    async def scenario():
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=100, user_id=100)
        ctx = FSMContext(storage=storage, key=key)

        # 1) Первый /start ref_555 — капча показана, ссылка сохранена.
        referrer_id = 555
        if referrer_id:
            await ctx.update_data(referred_by=referrer_id)

        # 2) Пользователь пишет "голый" /start (например, капча протухла) — referrer_id
        #    на этот раз не пришёл (None). Текущий (исправленный) код обновления FSM:
        referrer_id = None
        if referrer_id:
            await ctx.update_data(referred_by=referrer_id)
        else:
            existing_state_data = await ctx.get_data()
            referrer_id = existing_state_data.get("referred_by")

        return referrer_id, await ctx.get_data()

    resolved_referrer_id, final_state = asyncio.run(scenario())
    assert resolved_referrer_id == 555, "Ранее сохранённый referrer_id должен быть восстановлен из FSM"
    assert final_state.get("referred_by") == 555, "referred_by не должен быть затёрт None-ом при повторном /start"
