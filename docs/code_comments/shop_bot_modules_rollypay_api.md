# Комментарии: `src/shop_bot/modules/rollypay_api.py`

Модульный docstring в коде (дословно): клиент RollyPay; BASE_URL зафиксирован; выводы USDT не входят.

`BASE_URL = https://api.rollypay.io/api/v1`  
`WEBHOOK_TIMESTAMP_TOLERANCE_SEC = 300`  
`_PAYMENT_ID_RE` — тот же класс символов, что у Platega tx id.

## `_safe_id` (27–31)

**Docstring в коде:** нет

```
"""Вернуть id, если он непустой и совпадает с _PAYMENT_ID_RE; иначе None."""
```

## `verify_webhook_signature` (34–58)

**Docstring в коде:** есть

```
HMAC-SHA256(`{unix_ts}.{raw_body}`) в заголовке X-Signature, как в SDK RollyPay.
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 46–47 | пустые secret/sig | False |
| 48–51 | timestamp не int | False |
| 53–54 | \|now-ts\| > tolerance | False (tolerance=None отключает окно) |
| 57–58 | compare_digest hex | без приведения регистра подписи |

## `get_payment_sync` (61–82)

**Docstring в коде:** есть

```
Синхронный GET /payments/{id} для Flask-вебхука. Не доверяем телу колбэка.
```

Заголовок X-Nonce = uuid4. Невалидный id или ключ → None.

## `RollyPayAPI`

**Docstring класса в коде:** нет

```
"""Async-клиент: create_payment и get_payment на фиксированном BASE_URL."""
```

### `__init__` / `_headers`

```
"""Сохранить api_key и terminal_id. Заголовки: X-API-Key, новый X-Nonce на каждый вызов."""
```

### `create_payment` (98–159)

**Docstring в коде:** есть

```
Возвращает (pay_url, provider_payment_id) или (None, None).
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 109–115 | нет key / плохой order_id | None, None |
| 117–133 | payload | amount `:.2f`, RUB; optional terminal, method, customer_id[:80], redirect URLs |
| 138–150 | POST /payments | HTTP>=400 или exception → None |
| 156–158 | нет pay_url | None |

### `get_payment` (161–180)

**Docstring в коде:** нет

```
"""GET /payments/{id} тем же ключом; невалидный id или HTTP>=400 → None."""
```
