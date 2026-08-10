"""Тесты живого поиска админки (пользователи + ключи, в т.ч. по key_id)."""
from conftest import temp_db  # noqa: F401


def test_get_keys_paginated_matches_key_id(temp_db):
    database = temp_db
    database.register_user_if_not_exists(8001, "searchuser", None)
    key_id = database.add_new_key(
        user_id=8001,
        host_name="test-host",
        remnawave_user_uuid="uuid-search-1",
        key_email="search-key@example.com",
        expiry_timestamp_ms=1_900_000_000_000,
    )
    assert key_id is not None

    keys, total = database.get_keys_paginated(page=1, per_page=10, search=str(key_id))
    assert total >= 1
    assert any(int(k["key_id"]) == int(key_id) for k in keys)


def test_get_keys_paginated_matches_email(temp_db):
    database = temp_db
    database.register_user_if_not_exists(8002, "emailuser", None)
    key_id = database.add_new_key(
        user_id=8002,
        host_name="test-host",
        remnawave_user_uuid="uuid-search-2",
        key_email="unique-live-search@example.com",
        expiry_timestamp_ms=1_900_000_000_000,
    )
    assert key_id is not None

    keys, total = database.get_keys_paginated(page=1, per_page=10, search="unique-live-search")
    assert total >= 1
    assert any(int(k["key_id"]) == int(key_id) for k in keys)


def test_get_users_paginated_matches_username(temp_db):
    database = temp_db
    database.register_user_if_not_exists(8003, "topbar_live_user", None)
    users, total = database.get_users_paginated(page=1, per_page=10, q="topbar_live")
    assert total >= 1
    assert any(int(u["telegram_id"]) == 8003 for u in users)
