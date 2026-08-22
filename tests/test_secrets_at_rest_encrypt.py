"""F-02: секреты панели/хостов хранятся at-rest тем же enc1$, что и токены клонов.

get_setting / get_host / get_ssh_target отдают plaintext для рабочего кода.
Сырой SELECT не содержит исходного секрета. Legacy без префикса читается как есть.
Форма /settings не кладёт ssh_password в HTML.
"""
from __future__ import annotations

import sqlite3

from conftest import temp_db  # noqa: F401

YOOKASSA_SECRET = "yookassa-live-secret-value-001"
CRYPTOBOT_TOKEN = "123456:AACryptoBotToken______________"
HELEKET_KEY = "heleket-api-key-value-002"
TONAPI_KEY = "tonapi-key-value-003"
REMNATOKEN = "remnawave-api-token-value-004"
SSH_PASSWORD = "ssh-root-password-NOT-FOR-HTML"


def _raw_setting(database, key: str) -> str | None:
    with sqlite3.connect(database.DB_FILE) as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def test_secret_settings_encrypted_at_rest_and_roundtrip(temp_db):
    database = temp_db
    pairs = {
        "yookassa_secret_key": YOOKASSA_SECRET,
        "cryptobot_token": CRYPTOBOT_TOKEN,
        "heleket_api_key": HELEKET_KEY,
        "tonapi_key": TONAPI_KEY,
        "remnawave_api_token": REMNATOKEN,
    }
    for key, plain in pairs.items():
        database.update_setting(key, plain)
        stored = _raw_setting(database, key)
        assert stored != plain
        assert stored.startswith(database.MANAGED_BOT_TOKEN_PREFIX)
        assert plain not in stored
        assert database.get_setting(key) == plain
        assert database.get_all_settings().get(key) == plain
        # already-encrypted value is a no-op
        database.update_setting(key, stored)
        assert _raw_setting(database, key) == stored
        assert database.get_setting(key) == plain


def test_legacy_plaintext_secret_setting_still_reads(temp_db):
    database = temp_db
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
            ("yookassa_secret_key", YOOKASSA_SECRET),
        )
        conn.commit()
    assert database.get_setting("yookassa_secret_key") == YOOKASSA_SECRET


def test_ssh_password_and_host_token_encrypted_on_write(temp_db):
    database = temp_db
    database.create_host("alpha", "https://panel.example", "", "", 0)
    assert database.update_host_ssh_settings(
        "alpha",
        ssh_host="1.2.3.4",
        ssh_port=22,
        ssh_user="root",
        ssh_password=SSH_PASSWORD,
        ssh_key_path=None,
    )
    assert database.update_host_remnawave_settings(
        "alpha",
        remnawave_base_url="https://panel.example",
        remnawave_api_token=REMNATOKEN,
    )

    with sqlite3.connect(database.DB_FILE) as conn:
        row = conn.execute(
            "SELECT ssh_password, remnawave_api_token FROM xui_hosts WHERE host_name = ?",
            ("alpha",),
        ).fetchone()
    assert row[0] != SSH_PASSWORD
    assert row[0].startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert SSH_PASSWORD not in row[0]
    assert row[1] != REMNATOKEN
    assert row[1].startswith(database.MANAGED_BOT_TOKEN_PREFIX)

    host = database.get_host("alpha")
    assert host["ssh_password"] == SSH_PASSWORD
    assert host["remnawave_api_token"] == REMNATOKEN
    listed = next(h for h in database.get_all_hosts() if h["host_name"] == "alpha")
    assert listed["ssh_password"] == SSH_PASSWORD
    assert listed["remnawave_api_token"] == REMNATOKEN

    from shop_bot.data_manager import remnawave_repository as rw_repo
    from shop_bot.modules import remnawave_api

    squad = rw_repo.get_squad("alpha")
    assert squad["remnawave_api_token"] == REMNATOKEN
    assert not squad["remnawave_api_token"].startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert any(
        s["host_name"] == "alpha" and s["remnawave_api_token"] == REMNATOKEN
        for s in rw_repo.list_squads()
    )
    cfg = remnawave_api._load_config_for_host("alpha")
    assert cfg["token"] == REMNATOKEN


def test_ssh_target_password_encrypted_and_legacy_reads(temp_db):
    database = temp_db
    assert database.create_ssh_target(
        "probe",
        ssh_host="10.0.0.8",
        ssh_port=22,
        ssh_user="root",
        ssh_password=SSH_PASSWORD,
    )
    with sqlite3.connect(database.DB_FILE) as conn:
        stored = conn.execute(
            "SELECT ssh_password FROM speedtest_ssh_targets WHERE target_name = ?",
            ("probe",),
        ).fetchone()[0]
    assert stored != SSH_PASSWORD
    assert stored.startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert database.get_ssh_target("probe")["ssh_password"] == SSH_PASSWORD

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO speedtest_ssh_targets (target_name, ssh_host, ssh_password) VALUES (?, ?, ?)",
            ("legacy", "10.0.0.9", SSH_PASSWORD),
        )
        conn.commit()
    assert database.get_ssh_target("legacy")["ssh_password"] == SSH_PASSWORD


def test_backfill_encrypts_existing_plaintext_secrets(temp_db):
    database = temp_db
    database.create_host("beta", "https://old.example", "", "", 0)
    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)",
            ("cryptobot_token", CRYPTOBOT_TOKEN),
        )
        conn.execute(
            "UPDATE xui_hosts SET ssh_password = ?, remnawave_api_token = ? WHERE host_name = ?",
            (SSH_PASSWORD, REMNATOKEN, "beta"),
        )
        conn.commit()

    database._backfill_encrypt_secrets_at_rest()

    assert _raw_setting(database, "cryptobot_token").startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert database.get_setting("cryptobot_token") == CRYPTOBOT_TOKEN
    with sqlite3.connect(database.DB_FILE) as conn:
        row = conn.execute(
            "SELECT ssh_password, remnawave_api_token FROM xui_hosts WHERE host_name = ?",
            ("beta",),
        ).fetchone()
    assert row[0].startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    assert row[1].startswith(database.MANAGED_BOT_TOKEN_PREFIX)
    host = database.get_host("beta")
    assert host["ssh_password"] == SSH_PASSWORD
    assert host["remnawave_api_token"] == REMNATOKEN


def test_settings_html_does_not_contain_ssh_password(temp_db, monkeypatch, tmp_path):
    database = temp_db
    database.create_ssh_target(
        "shown",
        ssh_host="203.0.113.10",
        ssh_port=22,
        ssh_user="root",
        ssh_password=SSH_PASSWORD,
    )
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr("shop_bot.data_manager.backup_manager.BACKUPS_DIR", backups)
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

    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert SSH_PASSWORD not in body
    assert "пароль задан" in body
