"""Регрессия: недоступный Telegram-чат не должен отменять выдачу оплаченного.

`process_successful_payment` начинался с `await bot.send_message(...)` вне
try/except, и это сообщение было чисто информационным («Обрабатываю ваш
запрос…»). Но `claim_processed_payment` к этому моменту уже помечал платёж
обработанным, поэтому исключение от Telegram означало: деньги списаны, ключ не
создан, повторная попытка невозможна, возврата нет.

Чат недоступен в двух совершенно обычных случаях:

* пользователь зарегистрировался по email — `telegram_id` у него синтетический
  (см. `is_email_only_user`), и бот в этот диапазон писать не может;
* пользователь заблокировал бота.

Ключ обязан быть создан в обоих случаях: он доступен пользователю в Mini App
через `/api/user-status`.
"""
from conftest import insert_user, issue_auth_token, temp_db  # noqa: F401


def _client():
    from fastapi.testclient import TestClient
    from shop_bot.webapp import handlers

    return TestClient(handlers.app)


class _UnreachableChat(Exception):
    """То, чем Telegram отвечает на синтетический chat_id."""

    def __init__(self):
        super().__init__("Telegram server says - Bad Request: chat not found")


def _fake_bot_class(monkeypatch, *, send_raises):
    """Подменяет aiogram-овый Bot там, где его создаёт платёжный код."""

    class _FakeMessage:
        def __init__(self):
            self.edited_to = None
            self.deleted = False

        async def edit_text(self, text, **kwargs):
            self.edited_to = text

        async def delete(self):
            self.deleted = True

    class _FakeBot:
        id = 777

        def __init__(self, *args, **kwargs):
            self.session = self
            self.sent = []

        async def send_message(self, *args, **kwargs):
            if send_raises:
                raise _UnreachableChat()
            self.sent.append(kwargs.get("text") or (args[1] if len(args) > 1 else None))
            return _FakeMessage()

        async def delete_message(self, *args, **kwargs):
            return None

        async def close(self):
            return None

    from shop_bot.webapp import handlers

    monkeypatch.setattr(handlers, "Bot", _FakeBot)
    monkeypatch.setattr("shop_bot.bot.user_router.fulfillment.Bot", _FakeBot)
    return _FakeBot


def _stub_panel(monkeypatch, *, email_marker):
    """Панель Remnawave отвечает успехом, ключ должен осесть в базе."""

    sub_url = f"https://vpn.example/sub/{email_marker}"

    async def fake_create(*args, **kwargs):
        # Форма ответа повторяет реальную create_or_update_key_on_host.
        return {
            "client_uuid": f"uuid-{email_marker}",
            "short_uuid": f"short-{email_marker}",
            "email": kwargs.get("email") or f"{email_marker}@bot.local",
            "host_name": kwargs.get("host_name"),
            "squad_uuid": "squad-1",
            "subscription_url": sub_url,
            "connection_string": sub_url,
            "traffic_limit_bytes": None,
            "traffic_limit_strategy": None,
            "expiry_timestamp_ms": 1893456000000,
        }

    monkeypatch.setattr(
        "shop_bot.modules.remnawave_api.create_or_update_key_on_host", fake_create
    )


def _buy_with_balance(monkeypatch, *, user_id, host_name, username):
    from shop_bot.data_manager import database

    insert_user(database.DB_FILE, telegram_id=user_id, username=username, balance=500.0)
    token = issue_auth_token(user_id)
    database.update_setting("telegram_bot_token", "123456:FAKE_BOT_TOKEN_FOR_TESTS")
    database.create_plan(host_name, "1 месяц", 1, 100.0)
    plan_id = database.get_plans_for_host(host_name)[0]["plan_id"]

    return _client().post(
        "/api/create-payment",
        json={
            "token": token,
            "payment_method": "pay_balance",
            "plan_id": plan_id,
            "host_name": host_name,
            "action": "new",
        },
    )


def test_email_only_user_gets_the_key_although_bot_cannot_write(temp_db, monkeypatch):
    """Главный сценарий из баг-репорта: оплата email-аккаунтом."""
    from shop_bot.data_manager import database

    user_id = database.EMAIL_ONLY_TELEGRAM_ID_MIN + 3
    assert database.is_email_only_user(user_id)

    _fake_bot_class(monkeypatch, send_raises=True)
    _stub_panel(monkeypatch, email_marker="emailonly")

    resp = _buy_with_balance(
        monkeypatch, user_id=user_id, host_name="MailHost", username="mailuser"
    )
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("paid") is True, data

    keys = database.get_user_keys(user_id)
    assert len(keys) == 1, "ключ должен быть создан, несмотря на недоступный чат"
    assert keys[0]["subscription_url"] == "https://vpn.example/sub/emailonly"

    # Деньги списаны один раз и не возвращены компенсирующей транзакцией.
    assert float(database.get_user(user_id)["balance"]) == 400.0


def test_telegram_user_who_blocked_the_bot_still_gets_the_key(temp_db, monkeypatch):
    """Та же поломка срабатывала и на обычном пользователе, заблокировавшем бота."""
    from shop_bot.data_manager import database

    user_id = 4242
    assert not database.is_email_only_user(user_id)

    _fake_bot_class(monkeypatch, send_raises=True)
    _stub_panel(monkeypatch, email_marker="blocked")

    resp = _buy_with_balance(
        monkeypatch, user_id=user_id, host_name="BlockHost", username="blockeduser"
    )
    data = resp.json()
    assert data.get("ok") is True, data
    assert data.get("paid") is True, data

    keys = database.get_user_keys(user_id)
    assert len(keys) == 1, "ключ должен быть создан, несмотря на блокировку бота"
    assert float(database.get_user(user_id)["balance"]) == 400.0


def test_reachable_user_still_receives_the_key_message(temp_db, monkeypatch):
    """Контроль: для доступного чата поведение не изменилось — сообщение уходит."""
    from shop_bot.data_manager import database

    user_id = 4343
    bot_cls = _fake_bot_class(monkeypatch, send_raises=False)
    _stub_panel(monkeypatch, email_marker="reachable")

    sent: list[str] = []
    original_send = bot_cls.send_message

    async def spy_send(self, *args, **kwargs):
        result = await original_send(self, *args, **kwargs)
        text = kwargs.get("text") or (args[1] if len(args) > 1 else None)
        if text:
            sent.append(text)
        return result

    monkeypatch.setattr(bot_cls, "send_message", spy_send)

    resp = _buy_with_balance(
        monkeypatch, user_id=user_id, host_name="OkHost", username="okuser"
    )
    assert resp.json().get("paid") is True, resp.json()
    assert len(database.get_user_keys(user_id)) == 1

    joined = "\n".join(sent)
    assert "Обрабатываю ваш запрос" in joined, sent
    assert "https://vpn.example/sub/reachable" in joined, sent


def test_email_only_user_is_not_pinged_over_telegram_at_all(temp_db, monkeypatch):
    """Для синтетического id запрос к Telegram бессмысленен — его не делаем.

    Иначе каждая покупка по email писала бы в лог «chat not found».
    """
    from shop_bot.data_manager import database

    user_id = database.EMAIL_ONLY_TELEGRAM_ID_MIN + 7
    bot_cls = _fake_bot_class(monkeypatch, send_raises=False)
    _stub_panel(monkeypatch, email_marker="nopings")

    chat_ids: list[object] = []
    original_send = bot_cls.send_message

    async def spy_send(self, *args, **kwargs):
        chat_ids.append(kwargs.get("chat_id", args[0] if args else None))
        return await original_send(self, *args, **kwargs)

    monkeypatch.setattr(bot_cls, "send_message", spy_send)

    resp = _buy_with_balance(
        monkeypatch, user_id=user_id, host_name="QuietHost", username="quietuser"
    )
    assert resp.json().get("paid") is True, resp.json()
    assert len(database.get_user_keys(user_id)) == 1
    assert user_id not in chat_ids, (
        "боту не следует писать на синтетический telegram_id: " f"{chat_ids}"
    )
