"""Регрессия: перехват владельца франшизного бота через create_managed_bot.

Старый код при совпадении telegram_bot_user_id делал
``UPDATE ... SET owner_telegram_id = ?`` без проверки текущего владельца.
Любой, кто прислал уже зарегистрированный токен клона (factory или
franchise_receive_token), становился owner — кабинет, баланс, выводы.

Новый код: чужой токен отклоняется; тот же владелец по-прежнему может
обновить токен (ротация в BotFather).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from conftest import temp_db  # noqa: F401

OWNER_A = 91001
OWNER_B = 91002
TG_BOT_ID = 555000111
TOKEN_A = "555000111:AAOwnerAToken________________"
TOKEN_B = "555000111:AAOwnerBToken________________"
TOKEN_ROTATED = "555000111:AAOwnerARotated______________"


def test_create_managed_bot_inserts_new_row(temp_db):
    database = temp_db
    ok, msg, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_a_bot",
        owner_telegram_id=OWNER_A,
        referrer_bot_id=0,
    )
    assert ok is True
    assert bot_id is not None
    assert "создан" in msg.lower()
    row = database.get_managed_bot(bot_id)
    assert row["owner_telegram_id"] == OWNER_A
    assert row["token"] == TOKEN_A
    assert row["telegram_bot_user_id"] == TG_BOT_ID


def test_other_user_cannot_take_over_existing_managed_bot(temp_db):
    """Старый код: второй create_managed_bot с тем же telegram_bot_user_id
    перезаписывал owner_telegram_id. Этот тест на нём падал бы."""
    database = temp_db
    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_a_bot",
        owner_telegram_id=OWNER_A,
    )
    assert ok is True

    stolen, msg, stolen_id = database.create_managed_bot(
        token=TOKEN_B,
        telegram_bot_user_id=TG_BOT_ID,
        username="stolen_bot",
        owner_telegram_id=OWNER_B,
        referrer_bot_id=99,
    )
    assert stolen is False
    assert stolen_id is None
    assert "другим владельцем" in msg

    row = database.get_managed_bot(bot_id)
    assert row["owner_telegram_id"] == OWNER_A
    assert row["token"] == TOKEN_A
    assert row["username"] == "clone_a_bot"
    assert int(row["referrer_bot_id"] or 0) == 0


def test_same_owner_can_rotate_token(temp_db):
    database = temp_db
    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_a_bot",
        owner_telegram_id=OWNER_A,
        referrer_bot_id=3,
    )
    assert ok is True

    ok2, msg, bot_id2 = database.create_managed_bot(
        token=TOKEN_ROTATED,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_a_renamed_bot",
        owner_telegram_id=OWNER_A,
        referrer_bot_id=3,
    )
    assert ok2 is True
    assert bot_id2 == bot_id
    assert "обновлён" in msg.lower()

    row = database.get_managed_bot(bot_id)
    assert row["owner_telegram_id"] == OWNER_A
    assert row["token"] == TOKEN_ROTATED
    assert row["username"] == "clone_a_renamed_bot"
    assert int(row["is_active"] or 0) == 1


def test_takeover_does_not_leak_owner_id_in_error(temp_db):
    database = temp_db
    database.create_managed_bot(
        token=TOKEN_A,
        telegram_bot_user_id=TG_BOT_ID,
        username="clone_a_bot",
        owner_telegram_id=OWNER_A,
    )
    _, msg, _ = database.create_managed_bot(
        token=TOKEN_B,
        telegram_bot_user_id=TG_BOT_ID,
        username="x",
        owner_telegram_id=OWNER_B,
    )
    assert str(OWNER_A) not in msg
    assert TOKEN_A not in msg


def test_concurrent_create_same_bot_id_keeps_single_owner(temp_db):
    """Два разных владельца одновременно регистрируют один telegram_bot_user_id —
    победитель один, owner не должен flip-flop'иться."""
    database = temp_db

    def _one(owner: int, token: str):
        return database.create_managed_bot(
            token=token,
            telegram_bot_user_id=TG_BOT_ID,
            username=f"bot_{owner}",
            owner_telegram_id=owner,
        )

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = []
        for i in range(8):
            owner = OWNER_A if i % 2 == 0 else OWNER_B
            token = TOKEN_A if owner == OWNER_A else TOKEN_B
            futs.append(pool.submit(_one, owner, token))
        for fut in as_completed(futs):
            results.append(fut.result())

    wins = [r for r in results if r[0]]
    losses = [r for r in results if not r[0]]
    assert len(wins) >= 1
    assert len(wins) + len(losses) == 8

    row = database.get_managed_bot_by_telegram_id(TG_BOT_ID)
    assert row is not None
    assert row["owner_telegram_id"] in (OWNER_A, OWNER_B)
    # Ни один проигравший не должен был сменить владельца на себя после победы другого.
    winner_owner = int(row["owner_telegram_id"])
    for ok, _msg, bot_id in wins:
        if bot_id is not None:
            assert database.get_managed_bot(bot_id)["owner_telegram_id"] == winner_owner
