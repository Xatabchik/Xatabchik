"""Регрессия: токен клона франшизы хранился в managed_bots.token открытым текстом.

SELECT * / админка получали полный BotFather-токен. Теперь at-rest
enc1$nonce$cipher$mac (stdlib HMAC-XOR), get_managed_bot отдаёт
plaintext для запуска. Legacy без префикса читается как есть.
Админский список не кладёт token в контекст шаблона.
"""
from __future__ import annotations

import sqlite3

from conftest import temp_db  # noqa: F401

OWNER = 92001
TG_BOT_ID = 555000222
TOKEN = "555000222:AASecretCloneToken______________"


def test_create_managed_bot_does_not_store_plaintext_token(temp_db):
    """На старом коде raw SQL возвращал тот же TOKEN."""
    database = temp_db
    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN,
        telegram_bot_user_id=TG_BOT_ID,
        username="enc_bot",
        owner_telegram_id=OWNER,
    )
    assert ok is True
    with sqlite3.connect(database.DB_FILE) as conn:
        stored = conn.execute(
            "SELECT token FROM managed_bots WHERE id = ?", (bot_id,)
        ).fetchone()[0]
    assert stored != TOKEN
    assert stored.startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert TOKEN not in stored


def test_get_managed_bot_returns_decrypted_plaintext(temp_db):
    database = temp_db
    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN,
        telegram_bot_user_id=TG_BOT_ID,
        username="enc_bot",
        owner_telegram_id=OWNER,
    )
    assert ok is True
    row = database.get_managed_bot(bot_id)
    assert row["token"] == TOKEN
    listed = database.list_active_managed_bots()
    assert listed[0]["token"] == TOKEN


def test_legacy_plaintext_token_still_reads(temp_db):
    database = temp_db
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO managed_bots (telegram_bot_user_id, username, token, owner_telegram_id, is_active)
            VALUES (?, 'legacy', ?, ?, 1)
            """,
            (TG_BOT_ID, TOKEN, OWNER),
        )
        conn.commit()
        bot_id = conn.execute("SELECT id FROM managed_bots").fetchone()[0]
    row = database.get_managed_bot(bot_id)
    assert row["token"] == TOKEN


def test_tampered_ciphertext_does_not_reveal_token(temp_db):
    database = temp_db
    ok, _, bot_id = database.create_managed_bot(
        token=TOKEN,
        telegram_bot_user_id=TG_BOT_ID,
        username="enc_bot",
        owner_telegram_id=OWNER,
    )
    assert ok is True
    with sqlite3.connect(database.DB_FILE) as conn:
        stored = conn.execute(
            "SELECT token FROM managed_bots WHERE id = ?", (bot_id,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE managed_bots SET token = ? WHERE id = ?",
            (stored[:-2] + "ff", bot_id),
        )
        conn.commit()
    row = database.get_managed_bot(bot_id)
    assert row["token"] != TOKEN
    assert row["token"] == ""


def test_encrypt_roundtrip_and_already_encrypted_noop(temp_db):
    database = temp_db
    enc = database.encrypt_managed_bot_token(TOKEN)
    assert enc.startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert database.decrypt_managed_bot_token(enc) == TOKEN
    assert database.encrypt_managed_bot_token(enc) == enc
