# Комментарии: `src/shop_bot/bot/callback_safety.py`

## `fast_callback_answer` (14–49)

**Docstring в коде:** есть (дословно):

```
Fast ACK for callback queries.

This helper is intentionally *dual-mode* for backward compatibility:
- As a decorator:  @fast_callback_answer
- As an awaitable: await fast_callback_answer(callback)
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 23–34 | isinstance CallbackQuery | вернуть корутину `_ack`: answer(cache_time=1), BadRequest/прочее игнор |
| 36–49 | иначе decorator | wrapper сначала ACK, затем исходный handler |

## `catch_callback_errors` (51–63)

**Docstring в коде:** нет

```
"""Декоратор: исключение handler → alert «Произошла ошибка…», exception-лог с callback.data, return None."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 54–55 | try | вернуть результат func |
| 56–62 | except | answer show_alert; вложенный except глотает сбой answer |

## `handle_unknown_callback` (65–73)

**Docstring в коде:** нет. Декораторы: `@catch_callback_errors` затем `@fast_callback_answer`.

```
"""Заглушка неизвестного callback_data: warning в лог и текст «Эта кнопка пока недоступна…»."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 70–73 | try message.answer | ошибка отправки игнорируется |
