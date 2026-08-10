"""Перезапуск обоих ботов одной кнопкой (stop → wait → start)."""
from conftest import temp_db  # noqa: F401


class _FakeController:
    def __init__(self, running: bool = True):
        self.running = running
        self.ops: list[str] = []

    def get_status(self):
        return {"is_running": self.running}

    def stop(self):
        self.ops.append("stop")
        self.running = False
        return {"status": "success", "message": "stopped"}

    def start(self):
        self.ops.append("start")
        self.running = True
        return {"status": "success", "message": "started"}


def test_restart_both_bots_stops_then_starts(temp_db, monkeypatch):
    from shop_bot.webhook_server import app as wh_mod

    main = _FakeController(running=True)
    support = _FakeController(running=False)  # уже остановлен — soft-stop не зовёт stop()

    flask_app = wh_mod.create_webhook_app(main)
    monkeypatch.setattr(wh_mod, "_support_bot_controller", support)
    monkeypatch.setattr(wh_mod.time, "sleep", lambda *_a, **_k: None)
    flask_app.config["WTF_CSRF_ENABLED"] = False

    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True

    resp = client.post("/restart-both-bots", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert main.ops == ["stop", "start"]
    assert support.ops == ["start"]
    assert main.running is True
    assert support.running is True


def test_restart_button_present_in_base_template():
    from pathlib import Path

    html = Path("src/shop_bot/webhook_server/templates/base.html").read_text(encoding="utf-8")
    assert "restart_both_bots_route" in html
    assert "Перезапустить" in html
