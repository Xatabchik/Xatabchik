# Комментарии: `src/shop_bot/modules/platega_fulfillment.py`

Модульный docstring в коде: `Общая идемпотентная финализация Platega-платежа (webhook и WebApp verify).`

`PLATEGA_METHODS = ("Platega", "Platega Crypto")`.  
`_TERMINAL_CANCELED = CANCELED/CANCELLED/CHARGEBACKED/FAILED/EXPIRED`.

## `is_platega_payment_method` (18–22)

**Docstring в коде:** нет

```
"""True, если pending_meta — dict и payment_method совпадает с Platega / Platega Crypto (без регистра)."""
```

Не-dict → False.

## `provider_transaction_id_from_meta` (25–30)

**Docstring в коде:** нет

```
"""Строка platega_transaction_id или transaction_id из meta; иначе ''."""
```

## `normalize_platega_status` (33–39)

**Docstring в коде:** нет

```
"""CONFIRMED → 'confirmed'; статусы _TERMINAL_CANCELED → 'canceled'; всё остальное → 'pending'."""
```

## `extract_platega_amount` (42–50)

**Docstring в коде:** нет

```
"""amount с корня payload или из paymentDetails/payment_details; иначе None. Не-dict → None."""
```

## `remote_is_canceled` (53–63)

**Docstring в коде:** есть

```
True только если API провайдера подтвердил отмену этого счёта.
```

Если в remote.payload есть значение и оно ≠ payment_id — False (чужой счёт).

## `mark_pending_canceled` (66–87)

**Docstring в коде:** есть

```
Пометить счёт отменённым в pending и в истории транзакций.
```

Пустой payment_id → False. Опционально пишет platega_transaction_id через patch_pending_metadata, затем `cancel_pending_transaction`.

## `complete_pending_platega_payment` (90–111)

**Docstring в коде:** есть

```
Атомарно закрыть pending и вернуть metadata.

None — заказа нет или он уже оплачен (второй вызов безопасен).
```

setdefault payment_method Platega; при наличии provider id кладёт в metadata (без повторной записи в БД в этой функции).
