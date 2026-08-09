"""
Общие фикстуры для тестов единого сценария pending action (подарок/реферальная
ссылка, вход через Telegram или email).

Каждый тест получает свежую SQLite БД во временном файле, поэтому тесты не
зависят друг от друга и не требуют реального бота/SMTP-сервера.
"""
import hashlib
import hmac
import json
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest

SRC_DIR = str(Path(__file__).resolve().parents[1] / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

FAKE_BOT_TOKEN = "123456:FAKE_BOT_TOKEN_FOR_TESTS"


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Свежая БД во временном файле для каждого теста; заодно настраивает
    telegram_bot_token, чтобы можно было подписывать тестовые Telegram init_data."""
    from shop_bot.data_manager import database

    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_FILE", db_path)
    database.initialize_db()
    database.update_setting("telegram_bot_token", FAKE_BOT_TOKEN)
    database.update_setting("telegram_bot_username", "TestVpnBot")
    yield database


@pytest.fixture()
def app_client(temp_db):
    """FastAPI TestClient поверх свежей БД. Импортируем handlers лениво (после
    того как database.DB_FILE уже переопределён), чтобы избежать обращений к
    несуществующей боевой БД на этапе импорта модуля."""
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


@pytest.fixture()
def no_smtp(monkeypatch):
    """Подменяет отправку письма активации email — тесты не должны требовать
    настоящего SMTP-сервера. Возвращает dict {email: code} с "отправленными" кодами.

    handlers.py делает `from shop_bot.modules import email_sender` внутри функции
    (не на уровне модуля), но т.к. Python кеширует модули в sys.modules, патчинг
    атрибута прямо на самом модуле email_sender корректно перехватывает и этот
    поздний локальный импорт."""
    from shop_bot.modules import email_sender

    sent_codes: dict[str, str] = {}

    def _fake_send(to_email: str, code: str) -> bool:
        sent_codes[to_email] = code
        return True

    monkeypatch.setattr(email_sender, "send_activation_code", _fake_send)
    monkeypatch.setattr(email_sender, "is_smtp_configured", lambda: True)
    return sent_codes


def make_telegram_init_data(user_id: int, *, username: str = "tguser", first_name: str = "Test") -> str:
    """Собрать корректно подписанный Telegram WebApp init_data для тестового
    бота (см. FAKE_BOT_TOKEN), как это делает сам Telegram-клиент."""
    user_json = json.dumps(
        {"id": user_id, "first_name": first_name, "username": username},
        separators=(",", ":"),
    )
    params = {"auth_date": str(int(time.time())), "query_id": "AAA", "user": user_json}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", FAKE_BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    params["hash"] = signature
    return urlencode(params)


def insert_user(db_path: Path, telegram_id: int, username: str = "user", **extra) -> None:
    columns = ["telegram_id", "username", "agreed_to_terms"] + list(extra.keys())
    values = [telegram_id, username, 1] + list(extra.values())
    placeholders = ", ".join("?" for _ in values)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()


def insert_gift_key(db_path: Path, *, from_user_id: int, gift_code: str, host_name: str = "TestHost") -> tuple[int, int]:
    """Создать vpn_keys-запись (tag=user_gift) + user_gifts-запись, связанные
    друг с другом — как это делает реальный флоу покупки подарка в боте.
    Возвращает (gift_id, key_id)."""
    from shop_bot.data_manager import database

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (user_id, host_name, email, key_email, subscription_url, expire_at, created_at, tag)
            VALUES (?, ?, ?, ?, 'vless://sub-url', datetime('now', '+30 days'), CURRENT_TIMESTAMP, 'user_gift')
            """,
            (from_user_id, host_name, f"{gift_code}@example.com", f"{gift_code}@example.com"),
        )
        key_id = cur.lastrowid
        conn.commit()

    gift = database.create_user_gift(from_user_id=from_user_id, host_name=host_name, plan_id=1, gift_code=gift_code)
    database.link_key_to_gift(gift["gift_id"], key_id)
    return gift["gift_id"], key_id


def register_and_verify_email_user(app_client, temp_db_path: Path, email: str, password: str = "Passw0rd!") -> str:
    """Зарегистрировать пользователя по email, сымитировать подтверждение
    почты (минуя реальную отправку письма) и залогиниться. Возвращает auth token."""
    from shop_bot.data_manager import database

    resp = app_client.post("/api/auth/email/register", json={"email": email, "password": password})
    assert resp.json().get("ok") is True, resp.json()

    user = database.get_user_by_email(email)
    database.mark_email_verified(user["telegram_id"])

    login_resp = app_client.post("/api/auth/email/login", json={"email": email, "password": password})
    data = login_resp.json()
    assert data.get("ok") is True and data.get("token"), data
    return data["token"], user["telegram_id"]
