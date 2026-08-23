"""Метка сквада вместо «LTE» в карточках и в настройках Хосты/тарифы."""
from conftest import temp_db  # noqa: F401

GB = 1024 ** 3


def test_squad_display_label_uses_label_or_lte_fallback(temp_db):
    from shop_bot.data_manager.database import squad_display_label

    assert squad_display_label({"label": "  5G Premium  "}) == "5G Premium"
    assert squad_display_label({"label": ""}) == "LTE"
    assert squad_display_label({"label": None, "squad_class": "lte"}) == "LTE"
    assert squad_display_label(None) == "LTE"
    assert squad_display_label({"label": "x" * 80}) == "x" * 48
    assert squad_display_label({"label": "", "squad_class": "base"}) == "BASE"


def test_get_lte_squad_display_label_from_host(temp_db):
    from shop_bot.data_manager import database

    database.create_host("Alpha", "https://panel.example", "", "", 0)
    database.add_host_squad("Alpha", "uuid-lte", "lte", "Мой 5G")
    assert database.get_lte_squad_display_label("Alpha") == "Мой 5G"
    assert database.get_lte_squad_display_label("Missing") == "LTE"


def test_key_card_keyboard_uses_squad_label():
    from shop_bot.bot.keyboards import create_key_info_keyboard, create_lte_packages_keyboard

    kb = create_key_info_keyboard(7, show_lte_topup=True, lte_label="5G Premium")
    texts = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "💰 Докупить 5G Premium" in texts
    assert "💰 Докупить LTE" not in texts

    pkg_kb = create_lte_packages_keyboard(7, [{"package_id": 1, "size_gb": 5, "price": 149}], lte_label="5G Premium")
    pkg_texts = [btn.text for row in pkg_kb.inline_keyboard for btn in row]
    assert "💰 5 ГБ 5G Premium — 149 RUB" in pkg_texts


def _settings_client(monkeypatch, temp_db):
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
    return client


def test_settings_hosts_tariffs_show_squad_label(temp_db, monkeypatch):
    from shop_bot.data_manager import database

    database.create_host("Gamma", "https://panel.example", "", "", 0)
    database.add_remnawave_squad("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "lte", "5G Premium")
    database.add_host_squad("Gamma", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "lte", "5G Premium")
    database.create_plan(
        "Gamma", "С меткой", 1, 100.0,
        traffic_limit_bytes=50 * GB,
        lte_limit_bytes=20 * GB,
    )

    html = _settings_client(monkeypatch, temp_db).get("/settings").get_data(as_text=True)
    assert "5G Premium 💰" in html
    assert "💰 5G Premium 20.0 ГБ" in html or "💰 5G Premium 20 ГБ" in html
    assert "5G Premium пул, ГБ" in html
    assert "Пакеты докупки ГБ — пул 5G Premium" in html
    assert "LTE 💰" not in html or "5G Premium 💰" in html
