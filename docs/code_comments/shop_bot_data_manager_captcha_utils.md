# Комментарии: `src/shop_bot/data_manager/captcha_utils.py`

Модульный docstring в коде: `Утилиты для работы с системой капчи.`

Путь к БД — `database.DB_FILE` (не импорт имени): в коде длинный `#` (стр. 12–18), чтобы тесты с monkeypatch видели актуальный файл. Вызывается из `bot/handlers.py`.

## `_now_str` (21–22)

**Docstring в коде:** нет

```
"""Вернуть utcnow() строкой YYYY-MM-DD HH:MM:SS."""
```

## `_expire_time_str` (25–28)

**Docstring в коде:** есть

```
Возвращает время истечения капчи (через N минут).
```

Формат тот же, что у `_now_str`.

## `generate_math_captcha` (31–52)

**Docstring в коде:** есть

```
Генерирует математическую задачу и правильный ответ.

Возвращает: (вопрос, правильный_ответ)
```

`a,b` ∈ [1, 99]; операция случайно `+` / `-` / `*`. Если `result < 0` — один обмен `a,b` и пересчёт (для вычитания даёт неотрицательный ответ).

## `generate_button_captcha` (55–72)

**Docstring в коде:** есть

```
Генерирует капчу с нажатием на кнопку.

Возвращает: (вопрос, правильный_ответ)
```

Случайная пара из восьми (вопрос, эмодзи).

## `create_captcha_challenge` (75–115)

**Docstring в коде:** есть

```
Создаёт новый капча-вызов для пользователя.

Args:
    user_id: ID пользователя Telegram
    challenge_type: тип капчи ("math" или "button")
    timeout_minutes: время истечения капчи в минутах

Возвращает: словарь с данными капчи или None при ошибке
```

Неизвестный `challenge_type` → warning и задача math, но в INSERT пишется исходный тип. INSERT в `captcha_challenges`; в ответе нет `expired_at`.

## `check_captcha_answer` (118–181)

**Docstring в коде:** есть

```
Проверяет ответ на капчу.

Возвращает: (успешно_ли, сообщение)
```

В коде `#`: успех не пишет `user_captcha_status` — это делает вызывающий `mark_user_passed_captcha`. Параметр `max_attempts` в теле не используется: лимит берётся из колонки `max_attempts` строки.

| Строки | Блок | Зачем |
|--------|------|--------|
| 134–135 | нет строки | False, «не найдена» |
| 139–140 | passed | False, «уже пройдена» |
| 142–145 | utcnow > expired_at | False, истекла |
| 147–148 | attempts >= cap_max_attempts | False, попытки исчерпаны |
| 152–164 | ответ равен (strip, lower) | UPDATE passed=1, True |
| 165–177 | иначе | UPDATE attempts; remaining>0 или исчерпаны |

## `get_active_captcha_challenge` (184–230)

**Docstring в коде:** есть

```
Получает активный капча-вызов для пользователя.

Возвращает: словарь с данными капчи или None
```

Последняя (`ORDER BY created_at DESC`) строка с `passed = 0`. В возвращаемом dict нет `correct_answer` (хотя колонка читается).

| Строки | Блок | Зачем |
|--------|------|--------|
| 211–217 | истекла | UPDATE `passed = 0` (уже 0), None |

## `has_passed_captcha` (233–248)

**Docstring в коде:** есть

```
Проверяет, прошла ли капчу пользователь при регистрации.

Возвращает: True если капча пройдена, False иначе
```

True, если есть строка в `user_captcha_status`. Ошибка БД → False.

## `mark_user_passed_captcha` (251–267)

**Docstring в коде:** есть

```
Помечает пользователя как прошедшего капчу.

Возвращает: True если успешно, False при ошибке
```

`INSERT OR REPLACE` в `user_captcha_status` (`user_id`, `passed_at`=`_now_str()`, `challenge_id`).
