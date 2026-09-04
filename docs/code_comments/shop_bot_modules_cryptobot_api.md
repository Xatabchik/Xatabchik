# Комментарии: `src/shop_bot/modules/cryptobot_api.py`

**Модульный docstring в коде** (1–7, дословно):

```
Клиент для платёжного провайдера Crypto Pay (CryptoBot).

Вынесен в отдельный переиспользуемый модуль (не трогая bot/handlers.py), на основе
логики, которая ранее существовала только внутри `bot/handlers.py`
(`_create_cryptobot_invoice`). Используется Telegram Mini App (shop_bot.webapp.handlers).
```

По графу импортов **этот файл никто не импортирует**; Mini App вызывает одноимённую функцию из `bot/handlers.py`. Утверждение в docstring модуля про Mini App к *этому файлу* не выполняется.

`CRYPTOBOT_API_URL` = `https://pay.crypt.bot/api/createInvoice`.

## `create_cryptobot_api_invoice` (23–69)

**Docstring в коде:** есть

```
Создать инвойс в Crypto Pay (CryptoBot) в фиате RUB.

Возвращает (bot_invoice_url, invoice_id) при успехе, иначе None.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 32–35 | нет токена | error-лог, None |
| 37 | quantize 0.01 | сумма как строка Decimal |
| 51–66 | POST timeout=20 | HTTP≠200 или не ok/result → None; url из bot_invoice_url или invoice_url |
| 67–69 | except | лог, None |
