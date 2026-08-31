"""Кнопка «Удалить тикет» на странице тикета не должна жить внутри формы ответа.

Вложенный <form> браузер выкидывает: клик шлёт POST на /support/<id>, confirm
не показывается, тикет остаётся.
"""
from __future__ import annotations

from conftest import temp_db  # noqa: F401


class _PanelBot:
    def get_status(self):
        return {"is_running": False}

    def get_loop(self):
        return None


def _client(temp_db):
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["TESTING"] = True
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["logged_in"] = True
        sess["username"] = "admin"
    return client


def _open_ticket(database, *, user_id: int = 100001, subject: str = "Тестовая тема"):
    ticket_id = database.create_support_ticket(user_id, subject)
    database.add_support_message(ticket_id, "user", "Сообщение пользователя")
    return ticket_id


def test_ticket_page_delete_form_is_not_nested_in_reply_form(temp_db):
    ticket_id = _open_ticket(temp_db)
    client = _client(temp_db)

    resp = client.get(f"/support/{ticket_id}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert 'id="reply-form"' in html
    assert 'id="delete-ticket-form"' in html
    assert f'action="/support/{ticket_id}/delete"' in html
    assert "Удалить тикет" in html
    assert "Это действие необратимо" in html

    reply_at = html.find('id="reply-form"')
    delete_at = html.find('id="delete-ticket-form"')
    assert 0 <= reply_at < delete_at
    assert "</form>" in html[reply_at:delete_at]

    assert 'form="reply-form"' in html
    assert 'name="action" value="reply"' in html


def test_post_to_ticket_page_without_action_does_not_delete(temp_db):
    """Старый клик по вложенной кнопке: POST на /support/<id> без action."""
    ticket_id = _open_ticket(temp_db)
    client = _client(temp_db)

    resp = client.post(f"/support/{ticket_id}", data={"message": ""}, follow_redirects=False)
    assert resp.status_code == 200
    assert temp_db.get_ticket(ticket_id) is not None


def test_delete_route_removes_ticket_and_redirects_to_list(temp_db):
    ticket_id = _open_ticket(temp_db)
    client = _client(temp_db)

    resp = client.post(f"/support/{ticket_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    location = resp.headers.get("Location") or ""
    assert location.endswith("/support")
    assert f"/support/{ticket_id}" not in location.rstrip("/")
    assert temp_db.get_ticket(ticket_id) is None

    follow = client.get("/support", follow_redirects=True)
    assert follow.status_code == 200
    body = follow.get_data(as_text=True)
    assert "Обращений пока нет" in body
    assert "Тестовая тема" not in body


def test_delete_route_requires_login(temp_db):
    ticket_id = _open_ticket(temp_db)
    from shop_bot.webhook_server import app as wh_mod

    flask_app = wh_mod.create_webhook_app(_PanelBot())
    flask_app.config["WTF_CSRF_ENABLED"] = False
    client = flask_app.test_client()

    resp = client.post(f"/support/{ticket_id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in (resp.headers.get("Location") or "")
    assert temp_db.get_ticket(ticket_id) is not None
