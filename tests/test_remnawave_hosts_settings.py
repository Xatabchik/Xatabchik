"""Глобальные настройки Remnawave + каталог сквадов и галочки на хостах."""
from datetime import datetime

from conftest import temp_db  # noqa: F401


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


def test_remnawave_settings_sync_to_hosts(temp_db, monkeypatch):
    database = temp_db
    database.create_host("alpha", "https://old.example", "", "", 0, subscription_url="https://old-sub")
    database.update_host_remnawave_settings(
        "alpha",
        remnawave_base_url="https://old.example",
        remnawave_api_token="old-token",
    )
    client, _ = _client(monkeypatch, temp_db)

    resp = client.post(
        "/settings/remnawave",
        data={
            "remnawave_base_url": "https://panel.example",
            "remnawave_api_token": "new-token",
            "remnawave_subscription_url": "https://sub.example",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert database.get_setting("remnawave_base_url") == "https://panel.example"
    assert database.get_setting("remnawave_api_token") == "new-token"
    assert database.get_setting("remnawave_subscription_url") == "https://sub.example"

    host = next(h for h in database.get_all_hosts() if h["host_name"] == "alpha")
    assert host.get("remnawave_base_url") == "https://panel.example"
    assert host.get("remnawave_api_token") == "new-token"
    assert host.get("subscription_url") == "https://sub.example"


def test_remnawave_token_empty_keeps_existing(temp_db, monkeypatch):
    database = temp_db
    database.update_setting("remnawave_api_token", "keep-me")
    database.update_setting("remnawave_base_url", "https://panel.example")
    client, _ = _client(monkeypatch, temp_db)

    resp = client.post(
        "/settings/remnawave",
        data={
            "remnawave_base_url": "https://panel.example",
            "remnawave_api_token": "",
            "remnawave_subscription_url": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert database.get_setting("remnawave_api_token") == "keep-me"


def test_squad_catalog_and_host_checkbox_selection(temp_db, monkeypatch):
    database = temp_db
    database.create_host("beta", "https://panel.example", "", "", 0)
    database.update_setting("remnawave_base_url", "https://panel.example")
    database.update_setting("remnawave_api_token", "tok")

    base_id = database.add_remnawave_squad("11111111-1111-1111-1111-111111111111", "base", "Base pool")
    lte_id = database.add_remnawave_squad("22222222-2222-2222-2222-222222222222", "lte", "LTE pool")
    assert base_id and lte_id

    client, _ = _client(monkeypatch, temp_db)
    resp = client.post(
        "/update-host-squad-selection",
        data={"host_name": "beta", "squad_ids": [str(base_id), str(lte_id)]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    selected = set(database.get_host_selected_squad_catalog_ids("beta"))
    assert selected == {base_id, lte_id}
    host_squads = database.get_host_squads("beta")
    assert {s["squad_class"] for s in host_squads} == {"base", "lte"}
    host = next(h for h in database.get_all_hosts() if h["host_name"] == "beta")
    assert host.get("squad_uuid") == "11111111-1111-1111-1111-111111111111"

    # Uncheck LTE
    resp = client.post(
        "/update-host-squad-selection",
        data={"host_name": "beta", "squad_ids": [str(base_id)]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    host_squads = database.get_host_squads("beta")
    assert len(host_squads) == 1
    assert host_squads[0]["squad_class"] == "base"


def test_add_host_inherits_global_remnawave(temp_db, monkeypatch):
    database = temp_db
    database.update_setting("remnawave_base_url", "https://panel.example")
    database.update_setting("remnawave_api_token", "tok")
    database.update_setting("remnawave_subscription_url", "https://sub.example")
    squad_id = database.add_remnawave_squad("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "base", "Main")
    client, _ = _client(monkeypatch, temp_db)

    resp = client.post(
        "/add-host",
        data={"host_name": "gamma", "squad_ids": [str(squad_id)]},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    host = next(h for h in database.get_all_hosts() if h["host_name"] == "gamma")
    assert host.get("remnawave_base_url") == "https://panel.example"
    assert host.get("remnawave_api_token") == "tok"
    assert host.get("subscription_url") == "https://sub.example"
    assert host.get("squad_uuid") == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
