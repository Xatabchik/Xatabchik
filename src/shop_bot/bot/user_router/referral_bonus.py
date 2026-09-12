"""Начисление реферальных бонусов: день за пробный период приглашённого
и стартовый бонус за переход по ссылке.
"""

from datetime import (
    datetime,
    timezone,
)
from aiogram import Bot
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user,
    get_user_keys,
    get_all_hosts,
    record_key_from_payload,
    set_referral_trial_day_bonus_received,
)
from shop_bot.modules import remnawave_api

__all__ = [
    "grant_referrer_day_bonus_for_trial",
]

async def grant_referrer_day_bonus_for_trial(*, referred_user_id: int, bot: Bot) -> None:
    """Начислить рефереру +1 день только в момент активации триала рефералом."""
    try:
        referred_user_id_i = int(referred_user_id or 0)
    except Exception:
        return
    if not referred_user_id_i:
        return

    try:
        user_data = get_user(referred_user_id_i) or {}
    except Exception:
        user_data = {}

    referrer_id = user_data.get("referred_by")
    if not referrer_id:
        return

    # чтобы не начислять дважды
    if user_data.get("referral_trial_day_bonus_received"):
        return

    # глобальный тумблер (оставляем для обратной совместимости)
    try:
        enabled = (get_setting("enable_referral_days_bonus") or "false").strip().lower() == "true"
    except Exception:
        enabled = False
    if not enabled:
        return

    try:
        referrer_id_i = int(referrer_id)
    except Exception:
        return
    if referrer_id_i <= 0 or referrer_id_i == referred_user_id_i:
        return

    # выбираем ключ реферера для продления: активный с максимальным сроком, иначе самый дальний
    ref_keys = []
    try:
        ref_keys = get_user_keys(referrer_id_i) or []
    except Exception:
        ref_keys = []

    now_utc = datetime.now(timezone.utc)

    def _parse_exp_dt(v) -> datetime | None:
        if not v:
            return None
        s = str(v).strip()
        if not s:
            return None
        try:
            # нормализуем ISO
            ss = s.replace("Z", "+00:00")
            if " " in ss and "T" not in ss:
                ss = ss.replace(" ", "T", 1)
            dt = datetime.fromisoformat(ss)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            # запасной парсер
            formats = [
                ("%Y-%m-%d %H:%M:%S", 19),
                ("%Y-%m-%d %H:%M", 16),
                ("%Y-%m-%d", 10),
            ]
            for fmt, n in formats:
                try:
                    dt = datetime.strptime(s[:n], fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except Exception:
                    continue
        return None

    scored = []
    for k in ref_keys:
        exp_dt = _parse_exp_dt(k.get("expiry_date") or k.get("expire_at"))
        if exp_dt:
            scored.append((exp_dt, k))

    active = [pair for pair in scored if pair[0] > now_utc]
    chosen = None
    if active:
        chosen = max(active, key=lambda x: x[0])[1]
    elif scored:
        chosen = max(scored, key=lambda x: x[0])[1]

    # host для бонуса
    bonus_host = None
    if chosen and chosen.get("host_name"):
        bonus_host = chosen.get("host_name")
    if not bonus_host:
        bonus_host = get_setting("referral_days_bonus_host") or None
    if not bonus_host:
        hosts = get_all_hosts() or []
        if hosts:
            bonus_host = hosts[0].get("host_name")
    if not bonus_host:
        return

    target_email = None
    if chosen:
        target_email = chosen.get("key_email") or chosen.get("email")
    if not target_email:
        target_email = f"tg{referrer_id_i}+trialref{int(now_utc.timestamp())}@ref.local"

    try:
        result = await remnawave_api.create_or_update_key_on_host(
            host_name=str(bonus_host),
            email=str(target_email),
            days_to_add=1,
            description="Бонус за активацию триала рефералом (+1 день)",
        )
    except Exception:
        result = None

    if not result:
        return

    try:
        record_key_from_payload(
            user_id=referrer_id_i,
            payload=result,
            host_name=str(bonus_host),
            description="Referral trial bonus +1 day",
        )
    except Exception:
        pass

    try:
        set_referral_trial_day_bonus_received(referred_user_id_i)
    except Exception:
        pass

    try:
        await bot.send_message(referrer_id_i, "🎁 Вам начислен бонус: +1 день к подписке за то, что ваш реферал активировал триал.")
    except Exception:
        pass
