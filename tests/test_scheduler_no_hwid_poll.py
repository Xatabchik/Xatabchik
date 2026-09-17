"""Scheduler больше не делает фоновый массовый опрос HWID.

Лимит устройств соблюдает Remnawave. Xatabchik запрашивает HWID только
по действию пользователя: карточка ключа в Telegram-боте и Mini App.
"""
from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

from conftest import insert_user, issue_auth_token

SCHEDULER_PY = Path("src/shop_bot/data_manager/scheduler.py")
KEY_INFO_PY = Path("src/shop_bot/bot/user_router/key_info.py")
KEY_DEVICES_PY = Path("src/shop_bot/webapp/web_router/key_devices.py")
KEY_ACTIONS_PY = Path("src/shop_bot/webapp/web_router/key_actions.py")
REMOVED_NAMES = (
    "check_device_limit_violations",
    "_resolve_hwid_device_limit_for_key",
    "_extract_device_ids",
)
TICK_ORDER = (
    "await check_expiring_subscriptions(bot)",
    "await check_auto_renewals(bot)",
    "await check_broadcast_campaigns(bot)",
    "await check_inactive_usage_reminders(bot)",
    "await check_traffic_boost_resets(bot)",
)


def test_periodic_subscription_check_does_not_call_device_limit_violations():
    from shop_bot.data_manager import scheduler

    src = inspect.getsource(scheduler.periodic_subscription_check)
    assert "check_device_limit_violations" not in src
    for stmt in TICK_ORDER:
        assert stmt in src, stmt
    positions = [src.index(stmt) for stmt in TICK_ORDER]
    assert positions == sorted(positions)
    assert scheduler.CHECK_INTERVAL_SECONDS == 300


def test_removed_hwid_helpers_are_gone():
    from shop_bot.data_manager import scheduler

    text = SCHEDULER_PY.read_text(encoding="utf-8")
    for name in REMOVED_NAMES:
        assert f"def {name}" not in text, name
        assert name not in text, name
        assert not hasattr(scheduler, name), name


def test_telegram_key_card_still_fetches_hwid_live(monkeypatch):
    import asyncio

    from shop_bot.bot.user_router import key_info
    from shop_bot.modules import remnawave_api

    text = KEY_INFO_PY.read_text(encoding="utf-8")
    assert "await remnawave_api.get_hwid_devices_for_user(" in text

    calls = []

    async def fake_hwid(user_uuid, host_name=None, email=None):
        calls.append({"user_uuid": user_uuid, "host_name": host_name, "email": email})
        return [{"hwid": "dev-live-1", "userAgent": "TestPhone"}]

    monkeypatch.setattr(remnawave_api, "get_hwid_devices_for_user", fake_hwid)

    key_data = {
        "host_name": "test",
        "email": "key@bot.local",
        "key_email": "key@bot.local",
    }
    payload = {"id": 42, "uuid": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"}

    devices = asyncio.run(key_info._get_devices_list(key_data, payload))
    count = asyncio.run(key_info._get_connected_devices_count(key_data, payload))

    assert calls, "карточка ключа должна запросить HWID у Remnawave"
    assert all(c["host_name"] == "test" for c in calls)
    assert any(d.get("hwid") == "dev-live-1" for d in devices)
    assert count >= 1


def test_miniapp_devices_list_and_delete_still_live(temp_db, app_client, monkeypatch):
    from shop_bot.data_manager import database
    from shop_bot.modules import remnawave_api

    devices_src = KEY_DEVICES_PY.read_text(encoding="utf-8")
    actions_src = KEY_ACTIONS_PY.read_text(encoding="utf-8")
    assert "await remnawave_api.get_connected_devices_count(" in devices_src
    assert "await remnawave_api.delete_user_device(" in devices_src
    assert "await remnawave_api.get_connected_devices_count(" in actions_src
    assert "await remnawave_api.delete_user_device(" in actions_src

    user_id = 991001
    insert_user(database.DB_FILE, telegram_id=user_id, username="hwid-live")
    token = issue_auth_token(user_id)
    with sqlite3.connect(database.DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO vpn_keys (
                user_id, host_name, email, key_email, remnawave_user_uuid,
                subscription_url, expire_at, created_at
            ) VALUES (?, 'test', 'live@bot.local', 'live@bot.local', '42',
                      'vless://x', datetime('now', '+30 days'), CURRENT_TIMESTAMP)
            """,
            (user_id,),
        )
        key_id = cur.lastrowid
        conn.commit()

    live_calls = []
    devices_store = [{"hwid": "dev-a", "userAgent": "Phone-A"}]

    async def fake_count(user_uuid, host_name=None, email=None):
        live_calls.append(("list", user_uuid, host_name, email))
        return {"devices": list(devices_store)}

    async def fake_delete(user_uuid, device_id, host_name=None, email=None, user_id=None):
        live_calls.append(("delete", user_uuid, device_id, host_name, email))
        devices_store[:] = [d for d in devices_store if d.get("hwid") != device_id]
        return True

    monkeypatch.setattr(remnawave_api, "get_connected_devices_count", fake_count)
    monkeypatch.setattr(remnawave_api, "delete_user_device", fake_delete)

    listed = app_client.post(
        "/api/key/devices",
        json={"token": token, "key_id": key_id, "host_name": "test"},
    )
    assert listed.status_code == 200
    assert listed.json()["ok"] is True
    assert listed.json()["devices"][0]["hwid"] == "dev-a"

    deleted = app_client.post(
        "/api/key/device/delete",
        json={
            "token": token,
            "key_id": key_id,
            "device_id": "dev-a",
            "host_name": "test",
        },
    )
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    devices_store.append({"hwid": "dev-b", "userAgent": "Phone-B"})
    deleted_all = app_client.post(
        "/api/key/devices/delete-all",
        json={"token": token, "key_id": key_id, "host_name": "test"},
    )
    assert deleted_all.status_code == 200
    body = deleted_all.json()
    assert body["ok"] is True
    assert body["deleted"] >= 1

    kinds = [c[0] for c in live_calls]
    assert kinds.count("list") >= 2
    assert "delete" in kinds
    assert all(c[1] == "42" for c in live_calls)
