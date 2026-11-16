"""Получение подарка по Telegram-ссылке `?start=gift_<code>`.

Получатель открывает ссылку один раз, проходит капчу / согласие / подписку —
и подарок оказывается у него без повторного перехода по ссылке. Вызовы идут
через настоящий Dispatcher и пользовательский роутер (см. gift_claim_harness).
"""
import asyncio

from aiogram.fsm.storage.memory import MemoryStorage

from conftest import insert_user, temp_db  # noqa: F401
from gift_claim_harness import (
    BotHarness,
    assert_subscription_preserved,
    configure_onboarding,
    gift_row,
    insert_full_gift,
    key_row,
    keys_count,
    latest_captcha_answer,
)

SENDER = 7100
RECIPIENT = 7200


def _assert_received(db_path, gift_id, key_id, recipient, before_key):
    key = key_row(db_path, key_id)
    assert key["user_id"] == recipient, "ключ должен принадлежать получателю"
    assert (key["tag"] or "") == "", "подарочный тег снимается, ключ попадает в обычный список"
    gift = gift_row(db_path, gift_id)
    assert gift["is_activated"] == 1
    assert gift["activated_by_user_id"] == recipient
    assert_subscription_preserved(before_key, key)


def _assert_not_received(db_path, gift_id, key_id):
    key = key_row(db_path, key_id)
    assert key["user_id"] == SENDER
    assert key["tag"] == "user_gift"
    assert gift_row(db_path, gift_id)["is_activated"] == 0


# 1. Новый пользователь, капча выключена
def test_new_user_no_captcha_receives_gift_in_one_open(temp_db):
    db = temp_db
    configure_onboarding(db, captcha=None)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="NOCAP1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()
    asyncio.run(h.send_text(RECIPIENT, "/start gift_NOCAP1"))

    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert "Подарок успешно активирован" in h.joined()
    assert db.get_user(RECIPIENT)["referred_by"] == SENDER


# 2. Новый пользователь, математическая капча
def test_new_user_math_captcha_receives_gift_after_answer(temp_db):
    db = temp_db
    configure_onboarding(db, captcha="math")
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="MATH1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()

    async def scenario():
        await h.send_text(RECIPIENT, "/start gift_MATH1")
        _assert_not_received(db.DB_FILE, gift_id, key_id)
        await h.send_text(RECIPIENT, latest_captcha_answer(db.DB_FILE, RECIPIENT))

    asyncio.run(scenario())
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert db.get_user(RECIPIENT)["referred_by"] == SENDER


# 3. Новый пользователь, кнопочная капча; message.from_user у callback — это бот
def test_new_user_button_captcha_uses_callback_identity(temp_db):
    db = temp_db
    configure_onboarding(db, captcha="button")
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="BTN1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()

    async def scenario():
        await h.send_text(RECIPIENT, "/start gift_BTN1")
        _assert_not_received(db.DB_FILE, gift_id, key_id)
        answer = latest_captcha_answer(db.DB_FILE, RECIPIENT)
        await h.press(RECIPIENT, f"captcha_answer:{answer}")

    asyncio.run(scenario())
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert keys_count(db.DB_FILE, 123456) == 0, "ключ не должен уйти боту"


# 4. Согласие с условиями и обязательная подписка выполняются ДО получения
def test_terms_and_forced_subscription_are_required_before_claim(temp_db):
    db = temp_db
    configure_onboarding(db, captcha="math", terms=True, channel=True)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="TERMS1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()

    async def scenario():
        await h.send_text(RECIPIENT, "/start gift_TERMS1")
        await h.send_text(RECIPIENT, latest_captcha_answer(db.DB_FILE, RECIPIENT))
        # Капча пройдена, но условия ещё не приняты — подарок не выдан.
        _assert_not_received(db.DB_FILE, gift_id, key_id)
        assert not db.get_user(RECIPIENT)["agreed_to_terms"]

        # Не подписан на канал — кнопка не пропускает.
        h.session.chat_member_status = "left"
        await h.press(RECIPIENT, "check_subscription_and_agree")
        _assert_not_received(db.DB_FILE, gift_id, key_id)

        h.session.chat_member_status = "member"
        await h.press(RECIPIENT, "check_subscription_and_agree")

    asyncio.run(scenario())
    assert db.get_user(RECIPIENT)["agreed_to_terms"]
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert "Подарок успешно активирован" in h.joined()


# 5. /start без аргументов во время незавершённого получения
def test_bare_start_during_captcha_keeps_pending_gift_and_captcha(temp_db):
    db = temp_db
    configure_onboarding(db, captcha="math", terms=True)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="BARE1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()

    async def scenario():
        await h.send_text(RECIPIENT, "/start gift_BARE1")
        captchas_before = h.joined().count("Введите ответ")
        # Пользователь жмёт /start ещё раз, не решив капчу.
        await h.send_text(RECIPIENT, "/start")
        assert h.joined().count("Введите ответ") > captchas_before, "капча не должна обходиться голым /start"
        _assert_not_received(db.DB_FILE, gift_id, key_id)
        await h.send_text(RECIPIENT, latest_captcha_answer(db.DB_FILE, RECIPIENT))
        await h.send_text(RECIPIENT, "/start")
        await h.press(RECIPIENT, "check_subscription_and_agree")

    asyncio.run(scenario())
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)


def test_cancelled_captcha_then_bare_start_still_delivers_gift(temp_db):
    db = temp_db
    configure_onboarding(db, captcha="math", terms=True)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="CANCEL1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()

    async def scenario():
        await h.send_text(RECIPIENT, "/start gift_CANCEL1")
        await h.press(RECIPIENT, "cancel_captcha")
        await h.send_text(RECIPIENT, "/start")
        _assert_not_received(db.DB_FILE, gift_id, key_id)
        await h.send_text(RECIPIENT, latest_captcha_answer(db.DB_FILE, RECIPIENT))
        await h.press(RECIPIENT, "check_subscription_and_agree")

    asyncio.run(scenario())
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)


def test_pending_gift_survives_bot_restart(temp_db):
    """FSM у бота в памяти (MemoryStorage): перезапуск процесса теряет его целиком."""
    db = temp_db
    configure_onboarding(db, captcha="math", terms=True)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="RESTART1")
    before = key_row(db.DB_FILE, key_id)

    first = BotHarness(storage=MemoryStorage())
    asyncio.run(first.send_text(RECIPIENT, "/start gift_RESTART1"))

    second = BotHarness(storage=MemoryStorage())

    async def scenario():
        await second.send_text(RECIPIENT, "/start")
        await second.send_text(RECIPIENT, latest_captcha_answer(db.DB_FILE, RECIPIENT))
        await second.press(RECIPIENT, "check_subscription_and_agree")

    asyncio.run(scenario())
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert db.get_user(RECIPIENT)["referred_by"] == SENDER, "признак нового пользователя сохраняется"


# 6. Существующий пользователь
def test_existing_user_receives_gift_and_is_not_rebound_as_referral(temp_db):
    db = temp_db
    configure_onboarding(db, captcha="math", terms=True)
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, RECIPIENT, "old", registration_date="2020-01-01 00:00:00")
    from shop_bot.data_manager.captcha_utils import create_captcha_challenge, mark_user_passed_captcha

    challenge = create_captcha_challenge(RECIPIENT, "math", 15)
    mark_user_passed_captcha(RECIPIENT, challenge["id"])
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="EXIST1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()
    asyncio.run(h.send_text(RECIPIENT, "/start gift_EXIST1"))

    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert db.get_user(RECIPIENT)["referred_by"] is None


# 10. Повторное получение тем же пользователем
def test_repeat_link_open_by_same_user_changes_nothing(temp_db):
    db = temp_db
    configure_onboarding(db, captcha=None)
    db.update_setting("referral_reward_type", "fixed_start_referrer")
    db.update_setting("referral_on_start_referrer_amount", "25")
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="REPEAT1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()
    asyncio.run(h.send_text(RECIPIENT, "/start gift_REPEAT1"))
    after_first = key_row(db.DB_FILE, key_id)
    gift_first = gift_row(db.DB_FILE, gift_id)
    sender_first = db.get_user(SENDER)

    async def again():
        for _ in range(3):
            await h.send_text(RECIPIENT, "/start gift_REPEAT1")

    asyncio.run(again())
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert key_row(db.DB_FILE, key_id) == after_first
    assert gift_row(db.DB_FILE, gift_id) == gift_first
    assert keys_count(db.DB_FILE, RECIPIENT) == 1
    sender_final = db.get_user(SENDER)
    assert sender_final["referral_balance"] == sender_first["referral_balance"]
    assert sender_final["referral_balance_all"] == sender_first["referral_balance_all"]
    assert "уже активирован на ваш аккаунт" in h.joined()


# 12. Истёкший, несуществующий и полученный другим подарок
def test_expired_missing_and_foreign_gifts_are_final_refusals(temp_db):
    db = temp_db
    configure_onboarding(db, captcha=None)
    insert_user(db.DB_FILE, SENDER, "sender")
    insert_user(db.DB_FILE, 7300, "other")
    exp_gift, exp_key = insert_full_gift(
        db.DB_FILE, from_user_id=SENDER, gift_code="EXPIRED1", expires_at="2000-01-01T00:00:00"
    )
    foreign_gift, foreign_key = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="FOREIGN1")

    other = BotHarness()
    asyncio.run(other.send_text(7300, "/start gift_FOREIGN1"))
    assert key_row(db.DB_FILE, foreign_key)["user_id"] == 7300

    h = BotHarness()

    async def scenario():
        await h.send_text(RECIPIENT, "/start gift_EXPIRED1")
        await h.send_text(RECIPIENT, "/start gift_NOSUCHCODE")
        await h.send_text(RECIPIENT, "/start gift_FOREIGN1")
        # Отказы окончательные: следующий /start не повторяет попытки.
        await h.send_text(RECIPIENT, "/start")

    asyncio.run(scenario())
    text = h.joined()
    assert "истёк" in text
    assert "не найден" in text
    assert "уже был активирован" in text
    assert "успешно" not in text
    _assert_not_received(db.DB_FILE, exp_gift, exp_key)
    assert key_row(db.DB_FILE, foreign_key)["user_id"] == 7300
    assert keys_count(db.DB_FILE, RECIPIENT) == 0
    assert text.count("истёк") == 1
    assert db.get_open_pending_gift_actions(RECIPIENT) == []


# 14. Сбой отправки уведомления после успешной передачи
def test_notification_failure_after_commit_keeps_transfer(temp_db):
    db = temp_db
    configure_onboarding(db, captcha=None)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="NOTIFY1")
    before = key_row(db.DB_FILE, key_id)

    h = BotHarness()
    h.session.fail_text_substrings = ["Подарок успешно активирован"]
    try:
        asyncio.run(h.send_text(RECIPIENT, "/start gift_NOTIFY1"))
    except Exception:
        pass
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    after_first = key_row(db.DB_FILE, key_id)

    h.session.fail_text_substrings = []
    asyncio.run(h.send_text(RECIPIENT, "/start"))
    asyncio.run(h.send_text(RECIPIENT, "/start gift_NOTIFY1"))
    assert key_row(db.DB_FILE, key_id) == after_first
    assert keys_count(db.DB_FILE, RECIPIENT) == 1
    assert db.get_open_pending_gift_actions(RECIPIENT) == []


# 15 + 16 (бот): сохранность подписки и реферальная привязка после передачи
def test_failed_transfer_in_bot_does_not_bind_referral_or_lose_gift(temp_db):
    from gift_claim_harness import drop_trigger, install_failing_trigger

    db = temp_db
    configure_onboarding(db, captcha=None)
    insert_user(db.DB_FILE, SENDER, "sender")
    gift_id, key_id = insert_full_gift(db.DB_FILE, from_user_id=SENDER, gift_code="FAILBOT1")
    before = key_row(db.DB_FILE, key_id)
    install_failing_trigger(db.DB_FILE, "vpn_keys", "user_id")

    h = BotHarness()
    asyncio.run(h.send_text(RECIPIENT, "/start gift_FAILBOT1"))
    _assert_not_received(db.DB_FILE, gift_id, key_id)
    assert "успешно" not in h.joined()
    assert db.get_user(RECIPIENT)["referred_by"] is None, "реферал не привязывается без передачи ключа"
    assert [g["gift_id"] for g in db.get_user_inactive_gifts(SENDER)] == [gift_id]

    # Временная ошибка — действие сохраняется и доводится до конца на следующем /start.
    drop_trigger(db.DB_FILE)
    asyncio.run(h.send_text(RECIPIENT, "/start"))
    _assert_received(db.DB_FILE, gift_id, key_id, RECIPIENT, before)
    assert db.get_user(RECIPIENT)["referred_by"] == SENDER
