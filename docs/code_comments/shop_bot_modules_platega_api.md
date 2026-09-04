# Комментарии: `src/shop_bot/modules/platega_api.md`

Файл: `src/shop_bot/modules/platega_api.py`.

Модульный docstring есть (клиент Platega; утверждает идентичность `_platega_request` в handlers).

`_TX_ID_RE`: id только `[A-Za-z0-9._-]{1,80}`.

## `get_transaction_sync` (26–58)

**Docstring в коде:** есть

```
Синхронный GET /transaction/{id} для Flask-вебхука. Телу колбэка не доверяем.
```

Пустые mid/secret/txid или невалидный txid → None. base_url по умолчанию `https://app.platega.io`. urllib, не aiohttp.

## `PlategaAPI` (61–137)

**Docstring в коде:** есть (пример create_payment).

### `__init__`

```
"""Сохранить merchant_id, secret и base_url (default app.platega.io) без пробелов по краям."""
```

Нет отдельного docstring в коде.

### `_request` (76–99)

**Docstring в коде:** нет

```
"""HTTP method+endpoint с заголовками X-MerchantId/X-Secret; JSON или None при HTTP>=400, пустом теле, битом JSON, исключении."""
```

Timeout: total=25, connect=10, sock_read=20.

### `create_payment` (101–128)

**Docstring в коде:** есть

```
Создать платёж в Platega.

Возвращает кортеж (redirect_url, transaction_id) — именно в таком порядке,
чтобы соответствовать историческому поведению `bot/handlers.py::_create_platega_payment_link`.
```

description режется до 64 символов; amount round(..., 2); payload=payment_id.

### `get_transaction` (131–137)

**Docstring в коде:** есть

```
GET /transaction/{id} — сверка статуса по provider transaction ID.
```

Пустой txid → None.
