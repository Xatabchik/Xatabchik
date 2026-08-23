"""Массовое изменение срока ключей: selected (bulk-extend) и all (bulk-extend-all)."""
from datetime import datetime, timedelta

from conftest import temp_db  # noqa: F401


def _insert_key(database, key_id: int, user_id: int = 100, *, days_ahead: int = 10):
    expire = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
    created = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO vpn_keys (
              key_id, user_id, host_name, remnawave_user_uuid, email, key_email,
              expire_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key_id,
                user_id,
                "test-host",
                f"uuid-{key_id}",
                f"{user_id}-{key_id}@bot.local",
                f"{user_id}-{key_id}@bot.local",
                expire,
                created,
                created,
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


def test_bulk_extend_selected_calls_extend_for_each_id(temp_db, monkeypatch):
    _insert_key(temp_db, 1)
    _insert_key(temp_db, 2)
    _insert_key(temp_db, 3)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[tuple[int, int]] = []

    def fake_extend(key_id, days):
        called.append((int(key_id), int(days)))
        return True, None

    monkeypatch.setattr(wh_mod, "extend_key", fake_extend)

    resp = client.post(
        "/admin/keys/bulk-extend",
        data={"mode": "days", "days": "7", "key_ids": ["1", "3"]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert sorted(called) == [(1, 7), (3, 7)]


def test_bulk_extend_all_ignores_key_ids_and_uses_all(temp_db, monkeypatch):
    _insert_key(temp_db, 10)
    _insert_key(temp_db, 11)
    _insert_key(temp_db, 12)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[int] = []

    def fake_extend(key_id, days):
        called.append(int(key_id))
        return True, None

    monkeypatch.setattr(wh_mod, "extend_key", fake_extend)

    # Передаём «чужие» key_ids — роут должен их игнорировать и взять все из БД
    resp = client.post(
        "/admin/keys/bulk-extend-all",
        data={"mode": "days", "days": "5", "key_ids": ["999"]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert sorted(called) == [10, 11, 12]


def test_bulk_extend_continues_after_one_failure(temp_db, monkeypatch):
    _insert_key(temp_db, 1)
    _insert_key(temp_db, 2)
    _insert_key(temp_db, 3)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[int] = []

    def fake_extend(key_id, days):
        kid = int(key_id)
        called.append(kid)
        if kid == 2:
            return False, "remnawave_update_failed"
        return True, None

    monkeypatch.setattr(wh_mod, "extend_key", fake_extend)

    with client.session_transaction() as sess:
        sess["_flashes"] = []
    resp = client.post(
        "/admin/keys/bulk-extend",
        data={"mode": "days", "days": "1", "key_ids": ["1", "2", "3"]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert called == [1, 2, 3]
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes") or []
    joined = " ".join(msg for _cat, msg in flashes)
    assert "Успешно: 2" in joined
    assert "Ошибок: 1" in joined


def test_bulk_extend_empty_key_ids_is_noop(temp_db, monkeypatch):
    _insert_key(temp_db, 1)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[int] = []
    monkeypatch.setattr(wh_mod, "extend_key", lambda *a, **k: called.append(1) or (True, None))

    resp = client.post(
        "/admin/keys/bulk-extend",
        data={"mode": "days", "days": "3"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert called == []
    html = resp.data.decode("utf-8", errors="ignore")
    assert "Не выбрано" in html


def test_bulk_extend_all_uses_set_key_expiry_for_date_mode(temp_db, monkeypatch):
    _insert_key(temp_db, 5)
    _insert_key(temp_db, 6)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[tuple[int, str]] = []

    def fake_set(key_id, new_expire_at):
        called.append((int(key_id), str(new_expire_at)))
        return True, None

    monkeypatch.setattr(wh_mod, "set_key_expiry", fake_set)
    monkeypatch.setattr(wh_mod, "extend_key", lambda *a, **k: (_ for _ in ()).throw(AssertionError("extend_key must not be called")))

    resp = client.post(
        "/admin/keys/bulk-extend-all",
        data={"mode": "date", "expire_at": "2030-01-15 12:00"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert sorted(called) == [(5, "2030-01-15 12:00"), (6, "2030-01-15 12:00")]


def test_admin_keys_page_has_bulk_ui():
    from pathlib import Path

    html = Path("src/shop_bot/webhook_server/templates/admin_keys.html").read_text(encoding="utf-8")
    assert "bulk_extend_keys_route" in html
    assert "bulk_extend_all_keys_route" in html
    assert "Изменить срок ВСЕМ ключам" in html
    assert "keys-select-all" in html
    assert "key-select-cb" in html
    assert "bulkExtendModal" in html


def test_user_card_keys_tab_has_checkbox_and_bulk_ui():
    from pathlib import Path

    pane = Path("src/shop_bot/webhook_server/templates/partials/user_card_keys_pane.html").read_text(encoding="utf-8")
    assert "uk-select-all" in pane
    assert "Изменить срок ВСЕМ" in pane
    assert "uk-bulk-extend-selected-btn" in pane
    assert "ti-hash" in pane
    assert "Пользователь" in pane
    assert "Хост" in pane
    assert "Email" in pane
    assert "Истекает" in pane
    assert "Создан" in pane

    users = Path("src/shop_bot/webhook_server/templates/users.html").read_text(encoding="utf-8")
    assert "user_card_keys_pane.html" in users
    assert "user_card_bulk_extend_modal.html" in users
    assert "user_card_keys_bulk_js.html" in users

    shared = Path("src/shop_bot/webhook_server/templates/partials/admin_details_modals.html").read_text(encoding="utf-8")
    assert "user_card_keys_pane.html" in shared
    assert "user_card_bulk_extend_modal.html" in shared

    rows = Path("src/shop_bot/webhook_server/templates/partials/admin_keys_table.html").read_text(encoding="utf-8")
    assert "key-select-cb" in rows
    assert rows.count("<td") == 7


def test_bulk_extend_user_only_touches_that_users_keys(temp_db, monkeypatch):
    from conftest import insert_user

    insert_user(temp_db.DB_FILE, telegram_id=100, username="owner")
    insert_user(temp_db.DB_FILE, telegram_id=200, username="other")
    _insert_key(temp_db, 1, user_id=100)
    _insert_key(temp_db, 2, user_id=100)
    _insert_key(temp_db, 3, user_id=200)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[int] = []

    def fake_extend(key_id, days):
        called.append(int(key_id))
        return True, None

    monkeypatch.setattr(wh_mod, "extend_key", fake_extend)

    resp = client.post(
        "/admin/keys/bulk-extend-user",
        data={"mode": "days", "days": "10", "user_id": "100", "key_ids": ["3"]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert sorted(called) == [1, 2]


def test_bulk_extend_user_requires_user_id(temp_db, monkeypatch):
    _insert_key(temp_db, 1, user_id=100)
    client, wh_mod = _client(monkeypatch, temp_db)

    called: list[int] = []
    monkeypatch.setattr(wh_mod, "extend_key", lambda *a, **k: called.append(1) or (True, None))

    resp = client.post(
        "/admin/keys/bulk-extend-user",
        data={"mode": "days", "days": "10"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert called == []
    html = resp.data.decode("utf-8", errors="ignore")
    assert "Не указан пользователь" in html
