# Комментарии: `src/shop_bot/modules/telegram_reachability.py`

Модульный docstring в коде: классификация 403, mark unreachable, снятие в BanMiddleware.

`REASON_BLOCKED = "blocked"`, `REASON_DEACTIVATED = "deactivated"`.

## `classify_unreachable_error` (30–46)

**Docstring в коде:** есть (blocked/deactivated/None; не сеть и не rate limit).

| Строки | Блок | Зачем |
|--------|------|--------|
| 37–38 | не TelegramForbiddenError | None |
| 40–41 | "deactivated" в тексте | REASON_DEACTIVATED |
| 42–43 | "blocked" | REASON_BLOCKED |
| 44–46 | прочий 403 | REASON_BLOCKED (в коде `#` про initiate conversation) |

## `handle_send_exception` (49–66)

**Docstring в коде:** есть (помечает в БД, return True если помечен, не бросает).

По коду: `return True` если reason непустой, **даже если** `mark_user_unreachable` вернул False или бросил (после except всё равно True). Если reason нет — False.
