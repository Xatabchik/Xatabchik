"""
Реферальные ссылки в боте: веб-ссылка только при включённом Mini App.
"""
from conftest import temp_db  # noqa: F401


def test_build_referral_links_without_webapp(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "false")
    database.update_setting("webapp_domain", "app.example.com")
    database.update_setting("telegram_bot_username", "TestVpnBot")

    web, tg = handlers._build_referral_links(42, "TestVpnBot")
    assert tg == "https://t.me/TestVpnBot?start=ref_42"
    assert web is None


def test_build_referral_links_with_webapp_enabled(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    database.update_setting("webapp_domain", "app.example.com")
    database.update_setting("telegram_bot_username", "TestVpnBot")

    web, tg = handlers._build_referral_links(42, "TestVpnBot")
    assert tg == "https://t.me/TestVpnBot?start=ref_42"
    assert web == "https://app.example.com/ref/42"


def test_build_referral_links_webapp_enabled_but_no_domain(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    database.update_setting("webapp_domain", "")

    web, tg = handlers._build_referral_links(7, "MyBot")
    assert tg == "https://t.me/MyBot?start=ref_7"
    assert web is None


def test_webapp_public_base_keeps_existing_scheme(temp_db):
    from shop_bot.bot import handlers
    from shop_bot.data_manager import database

    database.update_setting("webapp_enabled", "true")
    database.update_setting("webapp_domain", "https://vpn.example.org/")

    assert handlers._webapp_public_base() == "https://vpn.example.org"
