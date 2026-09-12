# Комментарии: `src/shop_bot/modules/heleket_api.py`

**Модульный docstring в коде** утверждает использование ботом и Mini App. По импортам файл берёт только `webapp/handlers.py`. Основной бот держит свой `_create_heleket_payment_request`.

## `create_heleket_payment_request` (26–109)

**Docstring в коде:** есть

```
Создать инвойс в Heleket.

`order_id` — это идентификатор платежа (должен совпадать с payment_id, под которым
заказ сохранён через create_payload_pending, иначе вебхук не сможет сопоставить оплату).
`description` — произвольный текст описания заказа, отображается в кабинете Heleket.

Возвращает dict вида {"payment_url": str, "raw": dict} при успехе, иначе None.
```

(В успешном return также есть ключ `uuid`.)

| Строки | Блок | Зачем |
|--------|------|--------|
| 44–48 | нет merchant/api_key | None |
| 61–69 | domain / return_url | url_callback `{domain}/heleket-webhook`; url_success и url_return |
| 71–73 | подпись | JSON compact → base64 → md5(base64+api_key) |
| 81–106 | POST | state==0 и url; patch_pending_metadata heleket_uuid |
| 107–109 | except | None |
