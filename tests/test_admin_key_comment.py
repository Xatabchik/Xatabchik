"""Заметка к ключу (comment_key) в карточке деталей админки."""
import sqlite3
from datetime import datetime, timedelta

from conftest import temp_db  # noqa: F401


def _insert_key(database, key_id: int, user_id: int = 100, *, comment_key: str | None = None):
    expire = (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    created = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
              key_id, user_id, host_name, remnawave_user_uuid, email, key_email,
              expire_at, created_at, updated_at, comment_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                user_id,
                "test-host",
                None,
                f"{user_id}-{key_id}@bot.local",
                f"{user_id}-{key_id}@bot.local",
                expire,
                created,
                created,
                comment_key,
            ),
        )
        conn.commit()


def _client(monkeypatch, temp_db):
    from shop_bot.webhook_server import app as wh_mod

    class _FakeBot:
        def get_status(self):
            return {"is_running": False}

        def get_bot_instance(self):
            return None

        def get_loop(self):
            return None

    flask_app = wh_mod.create_webhook_app(_FakeBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
    return client, wh_mod


def test_key_details_returns_comment_key(temp_db, monkeypatch):
    _insert_key(temp_db, 42, comment_key="Моя заметка из webapp")
    client, _ = _client(monkeypatch, temp_db)

    resp = client.get("/admin/keys/42/details")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["key"]["comment"] == "Моя заметка из webapp"
    assert data["key"]["comment_key"] == "Моя заметка из webapp"


def test_key_details_empty_comment_when_missing(temp_db, monkeypatch):
    _insert_key(temp_db, 7, comment_key=None)
    client, _ = _client(monkeypatch, temp_db)

    resp = client.get("/admin/keys/7/details")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["key"]["comment"] == ""
    assert data["key"]["comment_key"] == ""


def test_update_key_comment_persists_comment_key(temp_db, monkeypatch):
    _insert_key(temp_db, 9, comment_key="")
    client, _ = _client(monkeypatch, temp_db)

    resp = client.post("/admin/keys/9/comment", data={"comment": "Новая заметка"})
    assert resp.status_code in (200, 302, 303)

    details = client.get("/admin/keys/9/details").get_json()
    assert details["key"]["comment"] == "Новая заметка"
    assert details["key"]["comment_key"] == "Новая заметка"
    assert temp_db.get_key_by_id(9).get("comment_key") == "Новая заметка"
