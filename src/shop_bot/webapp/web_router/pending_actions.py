"""Отложенные действия: подарок и реферальная ссылка.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app
from shop_bot.webapp.web_router.models import PendingActionCompleteRequest


from fastapi import Request
from shop_bot.data_manager.remnawave_repository import get_setting
from datetime import datetime
import shop_bot.data_manager.remnawave_repository as rw_repo


def _apply_pending_referral(user_id: int, referrer_id: int) -> dict:
    """Привязать пользователя к рефереру и, если применимо, выплатить
    существующий стартовый бонус рефереру (тот же механизм и те же настройки,
    что использует бот при обычной регистрации по `/start ref_<id>` —
    см. reward_type == "fixed_start_referrer" в bot/handlers.py).

    Возвращает {"ok": bool, "status": str, "message": str}, где status один из:
    linked, already_linked, self_referral_forbidden, invalid_referrer, not_eligible.
    """
    from shop_bot.data_manager import database

    status = database.link_referrer_if_eligible(user_id, referrer_id, max_age_seconds=1800)
    message = _REFERRAL_LINK_MESSAGES.get(status, "Не удалось применить реферальную ссылку.")
    ok = status == "linked"

    if ok:
        try:
            reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
        except Exception:
            reward_type = "percent_purchase"

        if reward_type == "fixed_start_referrer":
            try:
                from decimal import Decimal
                amount_raw = get_setting("referral_on_start_referrer_amount") or "20"
                start_bonus = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
            except Exception:
                start_bonus = None
            if start_bonus and start_bonus > 0:
                try:
                    if rw_repo.claim_referral_start_bonus(user_id):
                        rw_repo.add_to_referral_balance(int(referrer_id), float(start_bonus))
                        rw_repo.add_to_referral_balance_all(int(referrer_id), float(start_bonus))
                except Exception as e:
                    logger.warning(f"Referral start bonus failed for referrer {referrer_id}: {e}")

    return {"ok": ok, "status": status, "message": message}


def _pending_action_public_info(pending: dict) -> dict:
    """Собрать безопасный (без лишних деталей) ответ для UI по pending action —
    для GET .../info (до входа) и как основа для complete (после входа)."""
    from shop_bot.data_manager import database

    action_type = pending.get("action_type")
    now = datetime.utcnow()
    try:
        expires_at = datetime.strptime(str(pending["expires_at"]), "%Y-%m-%d %H:%M:%S")
    except Exception:
        expires_at = None

    if pending.get("consumed_at"):
        return {"ok": False, "valid": False, "action_type": action_type, "error": "already_used",
                "message": "Эта ссылка уже была использована."}
    if expires_at and expires_at < now:
        return {"ok": False, "valid": False, "action_type": action_type, "error": "expired",
                "message": "Срок действия ссылки истёк."}

    if action_type == "gift":
        gift = database.get_gift_by_code(pending.get("gift_code") or "")
        if not gift:
            return {"ok": False, "valid": False, "action_type": action_type, "error": "not_found",
                    "message": "Подарок не найден."}
        if gift.get("is_activated"):
            return {"ok": False, "valid": False, "action_type": action_type, "error": "already_activated",
                    "message": "Этот подарок уже был активирован."}
        return {
            "ok": True, "valid": True, "action_type": "gift",
            "message": "Вам доступен подарок — VPN-ключ будет активирован на ваш аккаунт после входа.",
            "host_name": gift.get("host_name"),
        }

    if action_type == "referral":
        return {
            "ok": True, "valid": True, "action_type": "referral",
            "message": "Вы переходите по приглашению в сервис — после входа/регистрации вы станете рефералом.",
        }

    return {"ok": False, "valid": False, "action_type": action_type, "error": "invalid",
            "message": "Ссылка недействительна."}


@app.get("/api/webapp/pending-actions/info")
async def api_pending_action_info(pending_token: str):
    from shop_bot.data_manager import database
    pending = database.get_pending_action(pending_token)
    if not pending:
        return {"ok": False, "valid": False, "error": "invalid", "message": "Ссылка недействительна."}
    return _pending_action_public_info(pending)


@app.post("/api/webapp/pending-actions/complete")
async def api_pending_action_complete(req: PendingActionCompleteRequest, request: Request):
    """Единая точка завершения pending action ПОСЛЕ успешной авторизации.

    Безопасность:
      - пользователь определяется ИСКЛЮЧИТЕЛЬНО через _resolve_authenticated_user
        (доверенный persistent auth-токен ИЛИ подписанные Telegram init_data) —
        `user_id` в теле запроса не принимается и не может быть подменён клиентом;
      - gift_code/referrer_id/action_type берутся только из серверной записи
        auth_pending_actions по pending_token — клиент не может их переопределить;
      - claim_pending_action атомарно "забирает" токен ровно один раз, поэтому
        параллельные/повторные запросы не могут применить действие дважды
        (см. database.claim_pending_action, database.activate_user_gift,
        database.link_referrer_if_eligible — везде решение по cursor.rowcount).
    """
    from shop_bot.data_manager import database

    data = req.model_dump()
    user = _resolve_authenticated_user(data, request)
    if not user:
        return {"ok": False, "error": "unauthorized", "message": "Требуется авторизация."}
    if user.get("is_banned"):
        return {"ok": False, "error": "access_denied", "message": "Доступ запрещён."}

    user_id = int(user["telegram_id"])

    pending = database.get_pending_action(req.pending_token)
    if not pending:
        return {"ok": False, "error": "invalid", "message": "Ссылка недействительна."}

    action_type = pending.get("action_type")

    # Уже использован именно этим пользователем ранее — идемпотентно возвращаем
    # тот же результат, не выполняя бизнес-логику повторно.
    if pending.get("consumed_at"):
        if int(pending.get("consumed_by_user_id") or 0) == user_id:
            stored_status = pending.get("result_status") or "done"
            return {
                "ok": True,
                "already_completed": True,
                "action_type": action_type,
                "status": stored_status,
                "message": "Действие уже было применено к вашему аккаунту ранее.",
            }
        return {"ok": False, "error": "already_used", "message": "Эта ссылка уже была использована."}

    # Просрочен?
    try:
        expires_at = datetime.strptime(str(pending["expires_at"]), "%Y-%m-%d %H:%M:%S")
        if expires_at < datetime.utcnow():
            return {"ok": False, "error": "expired", "message": "Срок действия ссылки истёк."}
    except Exception:
        pass

    # Атомарно "забираем" токен для этого пользователя. Если не получилось —
    # значит кто-то (или этот же клиент параллельным запросом) уже успел его
    # обработать между нашими проверками выше и этим вызовом.
    if not database.claim_pending_action(req.pending_token, user_id):
        pending_after = database.get_pending_action(req.pending_token) or {}
        if int(pending_after.get("consumed_by_user_id") or 0) == user_id:
            stored_status = pending_after.get("result_status") or "done"
            return {
                "ok": True,
                "already_completed": True,
                "action_type": action_type,
                "status": stored_status,
                "message": "Действие уже было применено к вашему аккаунту ранее.",
            }
        return {"ok": False, "error": "expired", "message": "Ссылка недействительна или уже использована."}

    if action_type == "gift":
        result = _activate_gift_for_user(user_id, pending.get("gift_code") or "")
    elif action_type == "referral":
        try:
            referrer_id = int(pending.get("referrer_id") or 0)
        except (TypeError, ValueError):
            referrer_id = 0
        result = _apply_pending_referral(user_id, referrer_id)
    else:
        result = {"ok": False, "status": "invalid", "message": "Неизвестный тип действия."}

    try:
        database.set_pending_action_result(req.pending_token, result.get("status") or ("ok" if result.get("ok") else "error"))
    except Exception:
        pass

    return {
        "ok": bool(result.get("ok")),
        "action_type": action_type,
        "status": result.get("status"),
        "message": result.get("message"),
    }


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_apply_pending_referral",
    "_pending_action_public_info",
    "api_pending_action_info",
    "api_pending_action_complete",
]
