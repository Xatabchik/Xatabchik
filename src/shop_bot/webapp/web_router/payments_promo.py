"""Применение промокода.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import ApplyPromoRequest


from fastapi import Request


import shop_bot.data_manager.remnawave_repository as rw_repo


@app.post("/api/apply-promo")
async def api_apply_promo(req: ApplyPromoRequest, request: Request):
    """Проверить промокод и посчитать цену со скидкой.

    Промокоды в этом проекте — это ИСКЛЮЧИТЕЛЬНО скидка на покупку/продление
    ключа (см. таблицу `promo_codes`: только discount_percent/discount_amount,
    без какого-либо понятия "начислить на баланс"). Раньше здесь была мёртвая
    ветка на несуществующее поле `promo_type` ("balance"/"universal"), которая
    физически не могла сработать (в БД такой колонки никогда не было — из-за
    этого скидочная ветка тоже была недостижима: promo.get('promo_type')
    всегда возвращал None). Заодно эта мёртвая ветка теоретически позволяла бы
    напрямую зачислять баланс по промокоду, что недопустимо: активация
    промокода должна быть возможна только при покупке/продлении ключа, а не
    при пополнении баланса.
    """
    try:
        user = _require_authenticated_user(
            request, token=req.token, init_data=req.init_data
        )
        if not user:
            return _unauthorized()
        user_id = int(user["telegram_id"])
        code = req.promo_code.strip().upper()

        promo, error = rw_repo.check_promo_code_available(code, user_id, plan_id=req.plan_id)
        if not promo:
            return {"ok": False, "error": rw_repo.promo_error_message(error)}

        if req.price is None:
            return {"ok": False, "error": "Промокод действителен только при покупке или продлении ключа"}

        new_price = float(req.price)
        if promo.get('discount_percent'):
            new_price -= new_price * (float(promo['discount_percent']) / 100)
        elif promo.get('discount_amount'):
            new_price -= float(promo['discount_amount'])
        else:
            return {"ok": False, "error": "Промокод не даёт скидку"}

        return {
            "ok": True,
            "promo_type": "discount",
            "new_price": max(0, round(new_price, 2))
        }
    except Exception as e:
        logger.error(f"API apply-promo error: {e}")
        return {"ok": False, "error": str(e)}


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "api_apply_promo",
]
