# Комментарии: `src/shop_bot/modules/email_sender.py`

Модульный docstring в коде: SMTP из bot_settings; From/Subject из webapp_title / panel_brand_title.

`_APP_PASSWORD_HINTS` — mail.ru / yandex.ru / gmail.com (комментарий в коде, строки 25–26).

## `_get_service_name` (36–42)

**Docstring в коде:** есть

```
Название сервиса для From/Subject писем (не хардкод репозитория).
```

Первый непустой из webapp_title, panel_brand_title, иначе `"Сервис"`.

## `_get_smtp_settings` (45–64)

**Docstring в коде:** нет

```
"""Считать smtp_host/port/user/password/from_email/use_tls; порт не-int → 587; from_email fallback на user; use_tls default true."""
```

## `_auth_hint_for_host` (67–72)

**Docstring в коде:** нет

```
"""Подсказка из _APP_PASSWORD_HINTS, если domain входит в host; иначе общая фраза про логин/SMTP."""
```

## `is_smtp_configured` (75–78)

**Docstring в коде:** есть

```
Проверить, заполнены ли минимально необходимые настройки SMTP.
```

True только если host, user и password непустые.

## `_send_once` (81–96)

**Docstring в коде:** нет. В коде `#` про порт 465 = SMTPS без STARTTLS.

```
"""Одна SMTP-отправка: 465 → SMTP_SSL; иначе SMTP + опциональный STARTTLS; login и sendmail от settings['user']."""
```

## `send_activation_code` (99–165)

**Docstring в коде:** есть (попытки, не ретраить auth, return bool, не пробрасывать).

| Строки | Блок | Зачем |
|--------|------|--------|
| 113–119 | SMTP не настроен | False |
| 136–164 | for attempt | _send_once timeout=10 |
| 140–146 | SMTPAuthenticationError | hint, False без повтора |
| 147–161 | connect/timeout | sleep retry_delay, после max — False |
| 162–164 | прочее | False сразу |
| 165 | конец цикла | False |
