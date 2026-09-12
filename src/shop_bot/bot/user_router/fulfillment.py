"""Выдача оплаченного: уведомление администраторов и единая обработка
успешного платежа для всех сценариев покупки.
"""

import uuid
import math
import json
import asyncio
import time
from html import escape as html_escape
from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    add_to_balance,
    get_setting,
    get_user,
    claim_processed_payment,
    unclaim_processed_payment,
    get_user_keys,
    get_balance,
    get_plan_by_id,
    redeem_promo_code,
    reserve_promo_code,
    check_promo_code_available,
    update_promo_code_status,
    add_to_referral_balance_all,
    add_to_referral_balance,
    get_all_users,
    update_user_stats,
    log_transaction,
    is_admin,
)
from shop_bot.config import get_purchase_success_text
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.modules import remnawave_api

__all__ = [
    "notify_admin_of_purchase",
    "process_successful_payment",
]

async def notify_admin_of_purchase(bot: Bot, metadata: dict):
    try:
        admin_id_raw = get_setting("admin_telegram_id")
        if not admin_id_raw:
            return
        admin_id = int(admin_id_raw)
        user_id = metadata.get('user_id')
        host_name = metadata.get('host_name')
        months = metadata.get('months')
        price = metadata.get('price')
        action = metadata.get('action')
        payment_method = metadata.get('payment_method') or 'Unknown'

        payment_method_map = {
            'Balance': 'Баланс',
            'ReferralBalance': 'Реферальный баланс',
            'Card': 'Карта',
            'Crypto': 'Крипто',
            'USDT': 'USDT',
            'TON': 'TON',
        }
        payment_method_display = payment_method_map.get(payment_method, payment_method)
        plan_id = metadata.get('plan_id')
        try:
            plan_id_int = int(plan_id) if plan_id not in (None, '', 'None') else 0
        except Exception:
            plan_id_int = 0
        plan = get_plan_by_id(plan_id_int) if plan_id_int else None
        plan_name = plan.get('plan_name', 'Unknown') if plan else 'Unknown'

        duration_label = None
        if plan:
            duration_label = _format_duration_label(plan.get("months"), plan.get("duration_days"))
        else:
            duration_label = _format_duration_label(months, metadata.get("duration_days"))

        text = (
            "📥 Новая оплата\n"
            f"👤 Пользователь: {user_id}\n"
            f"🗺️ Хост: {host_name}\n"
            f"📦 Тариф: {plan_name} ({duration_label})\n"
            f"💳 Метод: {payment_method_display}\n"
            f"💰 Сумма: {float(price):.2f} RUB\n"
            f"⚙️ Действие: {'Новый ключ' if action == 'new' else 'Подарок' if action == 'gift' else 'Продление'}"
        )

        promo_code = (metadata.get('promo_code') or '').strip() if isinstance(metadata, dict) else ''
        if promo_code:
            try:
                applied_amount = float(metadata.get('promo_applied_amount') or metadata.get('promo_discount') or 0)
            except Exception:
                applied_amount = 0.0
            text += f"\n🎟 Промокод: {promo_code} (-{applied_amount:.2f} RUB)"

            def _to_int(val):
                try:
                    if val in (None, '', 'None'):
                        return None
                    return int(val)
                except Exception:
                    return None

            total_limit = _to_int(metadata.get('promo_usage_total_limit'))
            total_used = _to_int(metadata.get('promo_usage_total_used'))
            per_user_limit = _to_int(metadata.get('promo_usage_per_user_limit'))
            per_user_used = _to_int(metadata.get('promo_usage_per_user_used'))

            extra_lines = []
            if total_limit:
                extra_lines.append(f"Общий лимит: {total_used or 0}/{total_limit}")
            elif total_used is not None:
                extra_lines.append(f"Общий использований: {total_used}")

            if per_user_limit:
                extra_lines.append(f"Лимит на пользователя: {per_user_used or 0}/{per_user_limit}")

            status_parts = []
            if metadata.get('promo_disabled'):
                reason = (metadata.get('promo_disabled_reason') or '').strip()
                reason_map = {
                    'total_limit': 'исчерпан общий лимит',
                    'expired': 'истёк срок действия'
                }
                status_parts.append(f"Промокод отключён ({reason_map.get(reason, reason or 'причина неизвестна')})")
            else:
                if metadata.get('promo_user_limit_reached'):
                    status_parts.append('Достигнут лимит на пользователя')
                if metadata.get('promo_expired'):
                    status_parts.append('Срок действия истёк')
                availability_err = metadata.get('promo_availability_error')
                if availability_err:
                    status_parts.append(f"Статус доступности: {availability_err}")

            if metadata.get('promo_disable_failed'):
                status_parts.append('Не удалось отключить код (проверьте вручную)')
            if metadata.get('promo_redeem_failed'):
                status_parts.append('Redeem не выполнен — проверьте вручную')

            if extra_lines:
                text += "\n📊 " + " | ".join(extra_lines)
            if status_parts:
                text += "\n⚠️ " + " | ".join(status_parts)

        await bot.send_message(admin_id, text)
    except Exception as e:
        logger.warning(f"notify_admin_of_purchase failed: {e}")


def _telegram_chat_reachable(user_id: int) -> bool:
    """False, если писать в этот чат заведомо бессмысленно.

    У аккаунтов, зарегистрированных только по email, `telegram_id`
    синтетический (см. `is_email_only_user`): Telegram на такой chat_id всегда
    отвечает «chat not found». Запрос к API в этом случае не делаем, чтобы не
    сорить ошибками в логе на каждой покупке.
    """
    try:
        return not database.is_email_only_user(user_id)
    except Exception:
        return True


async def _deliver_to_user(bot: Bot, user_id: int, text: str, *, edit=None, **kwargs) -> bool:
    """Доставить текст пользователю, не прерывая выдачу уже оплаченного.

    Чат может быть недоступен по причинам, к оплате не относящимся: аккаунт
    зарегистрирован только по email, либо пользователь заблокировал бота. К
    моменту выдачи платёж уже принят, а `claim_processed_payment` пометил его
    обработанным, поэтому повторной попытки не будет. Значит ошибка доставки не
    должна отменять выдачу: ключ остаётся доступен в Mini App.

    Если передан `edit`, сначала пробуем отредактировать это сообщение, а при
    неудаче отправляем новое — прежнее сообщение могло оказаться нетекстовым
    или недоступным для правки.
    """
    if edit is not None:
        try:
            await edit.edit_text(text, **kwargs)
            return True
        except Exception as e:
            logger.warning(f"Не удалось отредактировать сообщение пользователю {user_id}: {e}")
    if not _telegram_chat_reachable(user_id):
        return False
    try:
        await bot.send_message(chat_id=user_id, text=text, **kwargs)
        return True
    except Exception as e:
        logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        return False


async def process_successful_payment(bot: Bot, metadata: dict) -> bool:
    """Обработать успешную оплату и выдать услугу.

    Returns:
        True — услуга выдана (или платёж уже был обработан ранее).
        False — выдача не удалась; для Balance/ReferralBalance/внешних методов
        средства возвращены через ``refund_payment_once`` (идемпотентно).
    """
    candidate_email = None  # default for gift flow
    logger.info("💳 Обрабатываем успешный платеж")

    def _provider_ids_for_log(meta: dict) -> dict:
        """Извлекает ID транзакции/инвойса на стороне платёжного провайдера из исходных
        metadata, чтобы не потерять их при пересборке metadata для log_transaction."""
        out = {}
        if not isinstance(meta, dict):
            return out
        for k in ("platega_transaction_id", "cryptobot_invoice_id", "heleket_uuid", "yookassa_payment_id", "rollypay_payment_id"):
            v = meta.get(k)
            if v:
                out[k] = v
        return out

    try:
        action = metadata.get('action')
        user_id = int(metadata.get('user_id'))
        price = float(metadata.get('price'))
        logger.info(f"📊 Детали платежа: действие={action}, пользователь={user_id}, сумма={price:.2f} RUB")
        

        def _to_int(val, default=0):
            try:
                if val in (None, '', 'None', 'null'):
                    return default
                return int(val)
            except (ValueError, TypeError):
                return default

        months = _to_int(metadata.get('months'), 0)
        key_id = _to_int(metadata.get('key_id'), 0)
        host_name = metadata.get('host_name', '')
        plan_id = _to_int(metadata.get('plan_id'), 0)
        duration_days_meta = _to_int(metadata.get('duration_days'), 0)
        customer_email = metadata.get('customer_email')
        payment_method = metadata.get('payment_method')

        payment_id = (metadata.get("payment_id") or metadata.get("transaction_id") or "").strip()
        if not payment_id:
            logger.error(f"process_successful_payment: missing payment_id in metadata; refusing to process: {metadata}")
            return False
        try:
            if not claim_processed_payment(payment_id):
                logger.info(f"process_successful_payment: duplicate payment ignored: {payment_id}")
                return True
        except Exception as e:
            logger.error(f"process_successful_payment: idempotency check failed for {payment_id}: {e}", exc_info=True)
            return False

        promo_code_early = ""
        try:
            promo_code_early = (metadata.get("promo_code") or "").strip()
        except Exception:
            promo_code_early = ""
        if promo_code_early:
            try:
                applied_early = float(metadata.get("promo_discount") or 0)
            except Exception:
                applied_early = 0.0
            promo_ok, promo_err = reserve_promo_code(
                promo_code_early,
                user_id,
                payment_id,
                applied_amount=applied_early,
                plan_id=metadata.get("plan_id") if isinstance(metadata, dict) else None,
            )
            if promo_err or not promo_ok:
                logger.warning(
                    "process_successful_payment: promo reserve failed code=%s payment_id=%s err=%s",
                    promo_code_early,
                    payment_id,
                    promo_err,
                )
                try:
                    unclaim_processed_payment(payment_id)
                except Exception:
                    pass
                return False

                # Franchise: accrue partner commission for payments made through a managed clone bot.
        try:
            factory_bot_id = int((metadata or {}).get("factory_bot_id") or 0)
        except Exception:
            factory_bot_id = 0
        if factory_bot_id <= 0:
            try:
                factory_bot_id = rw_repo.resolve_factory_bot_id(getattr(bot, "id", None))
            except Exception:
                factory_bot_id = 0
        if factory_bot_id > 0:
            try:
                rw_repo.accrue_partner_commission(factory_bot_id, str(payment_id), int(user_id), float(price), payment_method, 35.0)
            except Exception:
                pass

        chat_id_to_delete = metadata.get('chat_id')
        message_id_to_delete = metadata.get('message_id')
        
    except (ValueError, TypeError) as e:
        logger.error(f"FATAL: Could not parse metadata. Error: {e}. Metadata: {metadata}")
        return False

    if chat_id_to_delete and message_id_to_delete:
        try:
            await bot.delete_message(chat_id=chat_id_to_delete, message_id=message_id_to_delete)
        except TelegramBadRequest as e:
            logger.warning(f"Could not delete payment message: {e}")

    if action == "traffic_gb_topup":
        key_id_tg = _to_int(metadata.get('key_id'), 0)
        package_id_tg = _to_int(metadata.get('package_id'), 0)
        logger.info(f"📶 Обрабатываем докупку трафика: пользователь={user_id}, key_id={key_id_tg}, package_id={package_id_tg}")
        try:
            key_data = rw_repo.get_key_by_id(key_id_tg) if key_id_tg else None
            package = database.get_traffic_package_by_id(package_id_tg) if package_id_tg else None
            if not key_data or not package:
                logger.error(f"traffic_gb_topup: ключ или пакет не найден (key_id={key_id_tg}, package_id={package_id_tg})")
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="traffic_gb_topup",
                    reason=f"key_or_package_not_found(key_id={key_id_tg}, package_id={package_id_tg})",
                )
                return

            size_gb = float(package.get('size_gb') or 0)
            add_bytes = int(size_gb * 1024 * 1024 * 1024)

            host_name = key_data.get('host_name')
            user_uuid = key_data.get('remnawave_user_uuid')
            current_boost = int(key_data.get('traffic_boost_bytes') or 0)

            user_payload = None
            try:
                if user_uuid:
                    user_payload = await remnawave_api.get_user_by_uuid(user_uuid, host_name=host_name)
                if not user_payload:
                    email = key_data.get('key_email') or key_data.get('email')
                    if email:
                        user_payload = await remnawave_api.get_user_by_email(email, host_name=host_name)
                        if user_payload and not user_uuid:
                            user_uuid = user_payload.get('uuid')
            except Exception as e:
                logger.error(f"traffic_gb_topup: не удалось получить пользователя Remnawave: {e}", exc_info=True)

            current_limit = None
            if isinstance(user_payload, dict):
                current_limit = user_payload.get('trafficLimitBytes')
            if current_limit is None:
                current_limit = key_data.get('traffic_limit_bytes') or 0

            new_limit = int(current_limit or 0) + add_bytes
            new_boost = current_boost + add_bytes

            ok_remote = False
            if user_uuid:
                try:
                    ok_remote = await remnawave_api.update_user_traffic_limit(user_uuid, new_limit, host_name=host_name)
                except Exception as e:
                    logger.error(f"traffic_gb_topup: ошибка обновления лимита в Remnawave: {e}", exc_info=True)
                    ok_remote = False

            if not ok_remote:
                # Лимит на сервере не изменён — состояние консистентно, можно вернуть деньги
                # и позволить повторить попытку (в т.ч. ретраем вебхука).
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="traffic_gb_topup",
                    reason="remnawave_limit_update_failed" if user_uuid else "no_remote_user",
                )
                return

            # Лимит на сервере уже поднят: возврат средств здесь был бы неверным (услуга
            # оказана), поэтому локальную запись пишем с повторами, а при устойчивом сбое
            # поднимаем алерт админам вместо тихого расхождения БД и панели.
            local_write_error: Exception | None = None
            for attempt in range(3):
                try:
                    rw_repo.update_key(key_id_tg, traffic_limit_bytes=new_limit, traffic_boost_bytes=new_boost)
                    local_write_error = None
                    break
                except Exception as e:
                    local_write_error = e
                    logger.error(
                        f"traffic_gb_topup: не удалось обновить локальную запись ключа {key_id_tg} "
                        f"(попытка {attempt + 1}/3): {e}",
                        exc_info=True,
                    )
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
            if local_write_error is not None:
                await _notify_admins_topup_desync(
                    bot,
                    user_id=user_id,
                    action_label="traffic_gb_topup",
                    payment_id=payment_id,
                    detail=(
                        f"key_id={key_id_tg} лимит на сервере={new_limit} "
                        f"boost={new_boost} ошибка={local_write_error}"
                    ),
                )

            try:
                log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
                if not log_username:
                    user_info = get_user(user_id)
                    log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=payment_id,
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price),
                    amount_currency=None,
                    currency_name=None,
                    payment_method=payment_method or 'Unknown',
                    metadata=json.dumps({"action": "traffic_gb_topup", "key_id": key_id_tg, "size_gb": size_gb, **_provider_ids_for_log(metadata)})
                )
            except Exception:
                pass

            try:
                update_user_stats(user_id, float(price), 0)
            except Exception:
                pass

            size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"
            try:
                await bot.send_message(
                    user_id,
                    f"✅ Оплата получена! К вашему тарифу добавлено {size_txt} ГБ трафика.\n"
                    f"Новый лимит трафика действует до ближайшего ежемесячного сброса, после чего вернётся к базовому значению тарифа."
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"traffic_gb_topup: непредвиденная ошибка обработки платежа: {e}", exc_info=True)
        return

    if action == "lte_gb_topup":
        key_id_lte = _to_int(metadata.get('key_id'), 0)
        package_id_lte = _to_int(metadata.get('package_id'), 0)
        logger.info(f"💰 Обрабатываем докупку LTE: пользователь={user_id}, key_id={key_id_lte}, package_id={package_id_lte}")
        try:
            key_data = rw_repo.get_key_by_id(key_id_lte) if key_id_lte else None
            package = database.get_traffic_package_by_id(package_id_lte) if package_id_lte else None
            if not key_data or not package:
                logger.error(f"lte_gb_topup: ключ или пакет не найден (key_id={key_id_lte}, package_id={package_id_lte})")
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="lte_gb_topup",
                    reason=f"key_or_package_not_found(key_id={key_id_lte}, package_id={package_id_lte})",
                )
                return

            size_gb = float(package.get('size_gb') or 0)
            add_bytes = int(size_gb * 1024 * 1024 * 1024)

            # Докупка строго аддитивна: +N ГБ к остатку. Инкремент атомарный (одна транзакция),
            # иначе две параллельные оплаты теряли одну из покупок (read-modify-write).
            # Точку отсчёта расхода (baseline) здесь НЕ сдвигаем: вместе с учётом буста в
            # энфорсинге это выдавало бы полный лимит тарифа заново за цену минимального пакета.
            # Буст начисляется КОНКРЕТНОМУ ключу, который выбрал пользователь: LTE-пул живёт
            # на ключе, и докупка на одном ключе не должна расходоваться на другом.
            new_boost = database.add_key_lte_boost_bytes(key_id_lte, add_bytes)
            if new_boost is None:
                # Ничего не начислено и на сервере ничего не менялось — состояние
                # консистентно, возвращаем деньги и снимаем idempotency-lock.
                logger.error(
                    f"lte_gb_topup: не удалось начислить LTE-буст ключу {key_id_lte} "
                    f"(user_id={user_id}, add_bytes={add_bytes})"
                )
                await _abort_topup_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label="lte_gb_topup",
                    reason="lte_boost_update_failed",
                )
                return

            # Возвращаем доступ на premium-нодах ТОЛЬКО оплаченному ключу: докупка на одном
            # ключе не должна включать premium-ноды на других ключах пользователя.
            try:
                host_name_uk = key_data.get('host_name')
                try:
                    lte_squad_uk = database.get_squad_by_class(host_name_uk, 'lte')
                except Exception:
                    lte_squad_uk = None
                is_premium_uk = database.get_host_class(host_name_uk) == 'premium'
                uuid_uk = key_data.get('remnawave_user_uuid')
                state_uk = key_data.get('remote_access_state')
                if (
                    uuid_uk
                    and (is_premium_uk or lte_squad_uk)
                    and state_uk in ('disabled_premium', 'disabled_premium_squad')
                ):
                    if state_uk == 'disabled_premium_squad' and lte_squad_uk:
                        ok = await remnawave_api.add_squad_to_user(
                            uuid_uk, lte_squad_uk['squad_uuid'], host_name=host_name_uk
                        )
                    else:
                        ok = await remnawave_api.enable_user(uuid_uk, host_name=host_name_uk)
                    if ok:
                        database.update_key_fields(key_id_lte, remote_access_state='enabled')
                    else:
                        logger.error(
                            f"lte_gb_topup: не удалось вернуть доступ ключу {key_id_lte} "
                            f"(host '{host_name_uk}', состояние {state_uk})"
                        )
            except Exception as e:
                logger.error(f"lte_gb_topup: ошибка восстановления доступа ключа {key_id_lte}: {e}", exc_info=True)

            try:
                log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
                if not log_username:
                    user_info = get_user(user_id)
                    log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=payment_id,
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price),
                    amount_currency=None,
                    currency_name=None,
                    payment_method=payment_method or 'Unknown',
                    metadata=json.dumps({"action": "lte_gb_topup", "key_id": key_id_lte, "size_gb": size_gb, **_provider_ids_for_log(metadata)})
                )
            except Exception:
                pass

            try:
                update_user_stats(user_id, float(price), 0)
            except Exception:
                pass

            size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"
            lte_label_html = html_escape(database.get_lte_squad_display_label(key_data.get("host_name")))
            try:
                await bot.send_message(
                    user_id,
                    f"✅ Оплата получена! К вашему пулу {lte_label_html} (💰 premium-ноды) добавлено {size_txt} ГБ.\n"
                    f"Доступ на premium-нодах восстановлен."
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"lte_gb_topup: непредвиденная ошибка обработки платежа: {e}", exc_info=True)
        return

    if action == "main_traffic_reset":
        key_id_mr = _to_int(metadata.get('key_id'), 0)
        logger.info(f"♻️ Обрабатываем сброс основного пула: пользователь={user_id}, key_id={key_id_mr}")
        try:
            key_data = rw_repo.get_key_by_id(key_id_mr) if key_id_mr else None
            if not key_data:
                logger.error(f"main_traffic_reset: ключ не найден (key_id={key_id_mr})")
                await bot.send_message(user_id, "⚠️ Оплата получена, но не удалось найти ключ для сброса. Обратитесь в поддержку.")
                return

            reset_errors = 0
            try:
                user_keys = get_user_keys(user_id)
            except Exception:
                user_keys = [key_data]

            for uk in (user_keys or [key_data]):
                try:
                    uuid_uk = uk.get('remnawave_user_uuid')
                    host_name_uk = uk.get('host_name')
                    if not uuid_uk:
                        continue
                    ok = await remnawave_api.reset_user_traffic_on_host(uuid_uk, host_name=host_name_uk)
                    if not ok:
                        reset_errors += 1
                        continue
                    try:
                        await remnawave_api.enable_user(uuid_uk, host_name=host_name_uk)
                    except Exception:
                        pass
                    try:
                        database.update_key_fields(uk.get('key_id'), traffic_boost_bytes=0, remote_access_state='enabled')
                    except Exception:
                        pass
                except Exception as e:
                    reset_errors += 1
                    logger.error(f"main_traffic_reset: ошибка сброса ключа {uk.get('key_id')}: {e}", exc_info=True)

            try:
                log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
                if not log_username:
                    user_info = get_user(user_id)
                    log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
                log_transaction(
                    username=log_username,
                    transaction_id=None,
                    payment_id=payment_id,
                    user_id=user_id,
                    status='paid',
                    amount_rub=float(price),
                    amount_currency=None,
                    currency_name=None,
                    payment_method=payment_method or 'Unknown',
                    metadata=json.dumps({"action": "main_traffic_reset", "key_id": key_id_mr, **_provider_ids_for_log(metadata)})
                )
            except Exception:
                pass

            try:
                update_user_stats(user_id, float(price), 0)
            except Exception:
                pass

            if reset_errors == 0:
                try:
                    await bot.send_message(user_id, "✅ Оплата получена! Основной пул трафика сброшен, доступ восстановлен на всех нодах.")
                except Exception:
                    pass
            else:
                try:
                    await bot.send_message(user_id, "⚠️ Оплата получена, но часть узлов не удалось сбросить. Обратитесь в поддержку, если доступ не восстановился.")
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"main_traffic_reset: непредвиденная ошибка обработки платежа: {e}", exc_info=True)
        return

    if action == "top_up":
        logger.info(f"💰 Обрабатываем пополнение баланса для пользователя {user_id}: {float(price):.2f} RUB")
        ok = False
        try:
            ok = add_to_balance(user_id, float(price))
            if ok:
                logger.info(f"✅ Баланс успешно обновлен для пользователя {user_id}: +{float(price):.2f} RUB")
            else:
                logger.error(f"❌ Не удалось обновить баланс для пользователя {user_id}")
        except Exception as e:
            logger.error(f"💥 Ошибка при пополнении баланса для пользователя {user_id}: {e}", exc_info=True)
            ok = False
        
        # Обновляем total_spent при пополнении баланса (учитываем как инвестицию в сервис)
        try:
            update_user_stats(user_id, float(price), 0)  # Добавляем потраченные деньги, 0 месяцев
            logger.info(f"📊 Обновлены статистика пользователя {user_id}: +{float(price):.2f} RUB в total_spent")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить статистику пользователя {user_id}: {e}")

        try:

            log_username = (metadata.get('tg_username') or '').strip() if isinstance(metadata, dict) else ''
            if not log_username:
                user_info = get_user(user_id)
                log_username = (user_info.get('username') if user_info else '') or f"@{user_id}"
            logged_ok = log_transaction(
                username=log_username,
                transaction_id=None,
                payment_id=payment_id,
                user_id=user_id,
                status='paid',
                amount_rub=float(price),
                amount_currency=None,
                currency_name=None,
                payment_method=payment_method or 'Unknown',
                metadata=json.dumps({"action": "top_up", **_provider_ids_for_log(metadata)})
            )
            if logged_ok:
                logger.info(
                    f"🧾 Транзакция пополнения баланса записана в 'transactions': user={user_id}, "
                    f"amount={float(price):.2f} RUB, payment_method={payment_method or 'Unknown'}"
                )
            else:
                logger.error(
                    f"💥 Не удалось записать транзакцию пополнения баланса в 'transactions' для user={user_id}, "
                    f"amount={float(price):.2f} RUB, payment_method={payment_method or 'Unknown'}. "
                    f"Это пополнение НЕ попадёт в доходы/аналитику! Подробности см. выше в логе "
                    f"('Failed to log transaction for user...')."
                )
        except Exception as e:
            logger.error(
                f"💥 Непредвиденная ошибка при записи транзакции пополнения баланса для user={user_id}, "
                f"amount={float(price):.2f} RUB: {e}. Это пополнение НЕ попадёт в доходы/аналитику!",
                exc_info=True,
            )



        try:
            pm_for_ref = (payment_method or '').strip().lower()
            if pm_for_ref in ('balance', 'referralbalance'):
                logger.info(f"Referral(top_up): skip accrual for user {user_id} because top-up was made from internal balance.")
            else:
                user_data = get_user(user_id) or {}
                referrer_id = user_data.get('referred_by')
                if referrer_id:
                    try:
                        referrer_id = int(referrer_id)
                    except Exception:
                        logger.warning(f"Referral(top_up): invalid referrer_id={referrer_id} for user {user_id}")
                        referrer_id = None
                if referrer_id:
                    try:
                        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
                    except Exception:
                        reward_type = "percent_purchase"
                    reward = Decimal("0")
                    if reward_type == "fixed_start_referrer":
                        reward = Decimal("0")
                    elif reward_type == "fixed_purchase":
                        try:
                            amount_raw = get_setting("fixed_referral_bonus_amount") or "50"
                            reward = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
                        except Exception:
                            reward = Decimal("50.00")
                    else:

                        try:
                            percentage = Decimal(get_setting("referral_percentage") or "0")
                        except Exception:
                            percentage = Decimal("0")
                        reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
                    logger.info(f"Referral(top_up): user={user_id}, referrer={referrer_id}, type={reward_type}, reward={float(reward):.2f}")
                    if float(reward) > 0:
                        try:
                            ok_ref = add_to_referral_balance(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Referral(top_up): add_to_referral_balance failed for referrer {referrer_id}: {e}")
                            ok_ref = False
                        try:
                            add_to_referral_balance_all(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Referral(top_up): failed to increment referral_balance_all for {referrer_id}: {e}")
                        referrer_username = user_data.get('username', 'пользователь')
                        if ok_ref:
                            try:
                                await bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        "💰 Вам начислено реферальное вознаграждение за пополнение баланса!\n"
                                        f"Пользователь: {referrer_username} (ID: {user_id})\n"
                                        f"Сумма: {float(reward):.2f} RUB"
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"Referral(top_up): could not send reward notification to {referrer_id}: {e}")
        except Exception as e:
            logger.warning(f"Referral(top_up): unexpected error while processing reward for user {user_id}: {e}")


        try:
            current_balance = 0.0
            try:
                current_balance = float(get_balance(user_id))
            except Exception:
                pass
            try:
                gifts_count = len(rw_repo.get_user_inactive_gifts(user_id) or [])
            except Exception:
                gifts_count = 0
            if ok:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ Оплата получена!\n"
                        f"💼 Баланс пополнен на {float(price):.2f} RUB.\n"
                        f"Текущий баланс: {current_balance:.2f} RUB."
                    ),
                    reply_markup=keyboards.create_profile_keyboard(gifts_count=gifts_count)
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        "⚠️ Оплата получена, но не удалось обновить баланс. "
                        "Обратитесь в поддержку."
                    ),
                    reply_markup=keyboards.create_support_keyboard()
                )
        except Exception as e:
            logger.error(f"Failed to send top-up notification to user {user_id}: {e}")
        

        try:
            admins = [u for u in (get_all_users() or []) if is_admin(u.get('telegram_id') or 0)]
            for a in admins:
                admin_id = a.get('telegram_id')
                if admin_id:
                    await bot.send_message(admin_id, f"📥 Пополнение: пользователь {user_id}, сумма {float(price):.2f} RUB")
        except Exception:
            pass
        return

    # Сообщение «обрабатываю запрос» — вспомогательное, и недоступность чата не
    # должна отменять выдачу: платёж уже принят, а claim_processed_payment выше
    # уже пометил его обработанным, так что повторной попытки не будет.
    processing_message = None
    if _telegram_chat_reachable(user_id):
        try:
            processing_message = await bot.send_message(
                chat_id=user_id,
                text=f"✅ Оплата получена! Обрабатываю ваш запрос на сервере \"{host_name}\"..."
            )
        except Exception as e:
            logger.warning(
                f"Не удалось сообщить пользователю {user_id} о начале обработки: {e}"
            )
    key_issued = False
    try:
        email = ""

        price = float(metadata.get('price'))
        result = None

        if action == "new":
            try:
                candidate_email = rw_repo.generate_key_email_for_user(user_id)
            except Exception:
                candidate_email = f"{user_id}-{int(time.time())}@bot.local"
        elif action == "gift":
            # Генерируем временный email для подарка (он будет использован, пока подарок не активирован)
            # uuid уже импортирован на уровне модуля (см. верх файла) — НЕ импортируем повторно здесь:
            # локальный `import uuid` делает имя `uuid` локальным для ВСЕЙ функции
            # process_successful_payment, из-за чего более ранние ветки (top_up и т.д.)
            # падали с UnboundLocalError на uuid.uuid4().
            gift_code = str(uuid.uuid4())[:12]
            candidate_email = f"gift-{gift_code}@bot.local"
        else:

            existing_key = rw_repo.get_key_by_id(key_id)
            if not existing_key or not existing_key.get('key_email'):
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=key_id),
                    exc=RuntimeError("key not found for extend"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось найти ключ для продления.",
                )
                return False
            candidate_email = existing_key['key_email']

        # plan-based duration & limits
        plan = get_plan_by_id(plan_id) if plan_id else None
        plan_months = months
        plan_days = duration_days_meta
        traffic_limit_bytes = None
        traffic_limit_strategy = None
        hwid_device_limit = None
        if plan:
            try:
                plan_months = int(plan.get('months') or 0)
            except Exception:
                plan_months = months
            try:
                plan_days = int(plan.get('duration_days') or 0)
            except Exception:
                plan_days = duration_days_meta
            traffic_limit_bytes = plan.get('traffic_limit_bytes')
            traffic_limit_strategy = plan.get('traffic_limit_strategy')
            hwid_device_limit = plan.get('hwid_device_limit')

            # Ensure numeric type for Remnawave (SQLite may store numbers as TEXT)
            try:
                if hwid_device_limit is not None:
                    hwid_device_limit = int(hwid_device_limit)
            except Exception:
                hwid_device_limit = None

            # In admin UI, 0 values are stored as NULL. For Remnawave we must send 0 to explicitly remove an existing cap.
            # Traffic: 0 means unlimited.
            if traffic_limit_bytes is None:
                traffic_limit_bytes = 0
            # Devices: 0 means unlimited.
            if hwid_device_limit is None:
                hwid_device_limit = 0

        # normalize limits (traffic_limit_bytes=0 means "no limit" and must be sent to Remnawave to clear an existing cap)
        try:
            if traffic_limit_bytes is not None and int(traffic_limit_bytes) < 0:
                traffic_limit_bytes = 0
        except Exception:
            pass
        try:
            if hwid_device_limit is not None and int(hwid_device_limit) < 0:
                hwid_device_limit = 0
        except Exception:
            pass

        # Remnawave MONTH_ROLLING — только при лимите ОСНОВНОГО пула. LTE-лимит
        # крутит бот сам; для безлимитного основного явно шлём NO_RESET, чтобы
        # не унаследовать дефолт сквада и не оставить None (панель подставила бы
        # squad.default_traffic_strategy).
        traffic_limit_strategy = database.remnawave_traffic_limit_strategy_for_plan(plan)

        days_to_add = _compute_days_to_add(plan_months, plan_days)
        if days_to_add <= 0:
            days_to_add = _compute_days_to_add(months, duration_days_meta)
        if days_to_add <= 0:
            days_to_add = int(months * 30) if months else 30

        # Store tariff origin in key.description so the subscription page shows correct "🕒 Тариф".
        try:
            plan_id_int = int(plan_id) if plan_id not in (None, '', 'None') else None
        except Exception:
            plan_id_int = None
        plan_name_meta = plan.get('plan_name') if isinstance(plan, dict) else None
        origin_desc = _build_key_origin_meta(
            source="extend" if action == "extend" else "purchase",
            plan_id=plan_id_int,
            plan_name=plan_name_meta,
            months=int(plan_months or 0),
            duration_days=int(plan_days or 0),
            is_trial=False,
        )
        origin_tag = "paid"

        # For renewals: extend from current expiry (if it's in the future) so we don't lose remaining days.
        expiry_timestamp_ms = None
        if action == "extend" and key_id:
            try:
                exp_str = None
                try:
                    existing_key = rw_repo.get_key_by_id(key_id) or {}
                    exp_str = existing_key.get('expire_at') or existing_key.get('expiry_date')
                except Exception:
                    exp_str = None

                exp_ms = None
                if exp_str:
                    exp_norm = str(exp_str).replace('Z', '+00:00').replace(' ', 'T').replace('/', '-')
                    try:
                        exp_dt = datetime.fromisoformat(exp_norm)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                        exp_ms = int(exp_dt.timestamp() * 1000)
                    except Exception:
                        exp_ms = None

                now_ms = int(time.time() * 1000)
                base_ms = max(exp_ms or 0, now_ms)
                expiry_timestamp_ms = base_ms + int(days_to_add) * 86400000
            except Exception:
                expiry_timestamp_ms = None

        try:
            result = await remnawave_api.create_or_update_key_on_host(
                host_name=host_name,
                email=candidate_email,
                days_to_add=int(days_to_add),
                expiry_timestamp_ms=expiry_timestamp_ms,
                traffic_limit_bytes=traffic_limit_bytes,
                traffic_limit_strategy=traffic_limit_strategy,
                hwid_device_limit=hwid_device_limit,
                plan_id=plan_id_int,
                raise_on_error=True,
            )
        except Exception as exc:
            action_label = _format_key_action_label(action, price=price, key_id=key_id)
            await _abort_key_fulfillment(
                bot,
                payment_id=payment_id,
                user_id=user_id,
                price=price,
                payment_method=payment_method,
                action_label=action_label,
                exc=exc,
                factory_bot_id=factory_bot_id,
                processing_message=processing_message,
            )
            return False
        if action != "gift" and not result:
            action_label = _format_key_action_label(action, price=price, key_id=key_id)
            await _abort_key_fulfillment(
                bot,
                payment_id=payment_id,
                user_id=user_id,
                price=price,
                payment_method=payment_method,
                action_label=action_label,
                exc=RuntimeError("key creation returned empty response"),
                factory_bot_id=factory_bot_id,
                processing_message=processing_message,
            )
            return False

        if action == "new":
            key_id = rw_repo.record_key_from_payload(
                user_id=user_id,
                payload=result,
                host_name=host_name,
                tag=origin_tag,
                description=origin_desc,
            )
            if not key_id:
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=0),
                    exc=RuntimeError("failed to persist key after Remnawave create"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось сохранить ключ. Попробуйте позже.",
                )
                return False
            try:
                database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
            except Exception:
                logger.warning(f"Не удалось установить дату сброса трафика для нового ключа {key_id}", exc_info=True)
            key_issued = True
        
        elif action == "gift":
            # Создаём запись о неактивированном подарке
            # uuid уже импортирован на уровне модуля — см. комментарий выше по функции.
            gift_code_unique = str(uuid.uuid4())[:16]
            
            # Использовуем candidate_email для получения key_id (ключ был создан на хосте)
            if result:
                try:
                    # Сохраняем ключ в БД с информацией о подарке
                    key_id = rw_repo.record_key_from_payload(
                        user_id=user_id,
                        payload=result,
                        host_name=host_name,
                        tag="user_gift",  # Специальный тег для подарков
                        description=origin_desc,
                    )
                    
                    if  key_id:
                        # Создаём запись в user_gifts
                        gift_result = rw_repo.create_user_gift(
                            from_user_id=user_id,
                            host_name=host_name,
                            plan_id=plan_id,
                            gift_code=gift_code_unique,
                        )
                        try:
                            database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=True)
                        except Exception:
                            logger.warning(f"Не удалось установить дату сброса трафика для подарочного ключа {key_id}", exc_info=True)
                        
                        if gift_result:
                            # Обновляем связь между подарком и ключом
                            rw_repo.link_key_to_gift(gift_result['gift_id'], key_id)
                            
                            # Формируем ссылку для активации подарка
                            domain = (get_setting("domain") or "").strip()
                            if domain:
                                gift_link = f"{domain.rstrip('/')}/start?start=gift_{gift_code_unique}"
                            else:
                                gift_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=gift_{gift_code_unique}" if TELEGRAM_BOT_USERNAME else None
                            
                            # Отправляем информацию пользователю
                            gift_message = (
                                "🎁 <b>Подарок успешно куплен!</b>\n\n"
                                f"Тип: Подарок на {days_to_add} дней\n"
                                f"Сервер: {host_name}\n"
                                f"Цена: {price:.2f} RUB\n\n"
                                "<b>Вы можете:</b>\n"
                                "1️⃣ Использовать подарок сами (подарочный ключ будет добавлен в ваш профиль)\n"
                                f"2️⃣ Поделиться ссылкой: <code>{gift_link}</code>\n\n"
                                "Ссылка активируется один раз - первый переходящий по ней получит ключ.\n"
                                "Пока подарок не активирован, вы можете его использовать или видеть в разделе 'Неактивные подарки'."
                            )
                            
                            # Формируем клавиатуру с кнопкой поделиться
                            share_keyboard_builder = InlineKeyboardBuilder()
                            if gift_link:
                                share_text = _gift_share_text()
                                share_url = _telegram_share_url(gift_link, share_text)
                                share_keyboard_builder.button(text="📤 Поделиться подарком", url=share_url)
                            share_keyboard_builder.button(text="⬅️ Назад в меню", callback_data="back_to_main_menu")
                            share_keyboard_builder.adjust(1)
                            
                            await _deliver_to_user(
                                bot,
                                user_id,
                                gift_message,
                                edit=processing_message,
                                reply_markup=share_keyboard_builder.as_markup(),
                            )
                            key_issued = True
                        else:
                            await _abort_key_fulfillment(
                                bot,
                                payment_id=payment_id,
                                user_id=user_id,
                                price=price,
                                payment_method=payment_method,
                                action_label=_format_key_action_label(action, price=price, key_id=key_id),
                                exc=RuntimeError("failed to create gift record"),
                                factory_bot_id=factory_bot_id,
                                processing_message=processing_message,
                                fail_text="❌ Не удалось создать запись о подарке.",
                            )
                            return False
                    else:
                        await _abort_key_fulfillment(
                            bot,
                            payment_id=payment_id,
                            user_id=user_id,
                            price=price,
                            payment_method=payment_method,
                            action_label=_format_key_action_label(action, price=price, key_id=0),
                            exc=RuntimeError("failed to persist gift key"),
                            factory_bot_id=factory_bot_id,
                            processing_message=processing_message,
                            fail_text="❌ Не удалось сохранить ключ подарка.",
                        )
                        return False
                        
                except Exception as e:
                    logger.error(f"Gift creation error: {e}", exc_info=True)
                    await _abort_key_fulfillment(
                        bot,
                        payment_id=payment_id,
                        user_id=user_id,
                        price=price,
                        payment_method=payment_method,
                        action_label=_format_key_action_label(action, price=price, key_id=0),
                        exc=e,
                        factory_bot_id=factory_bot_id,
                        processing_message=processing_message,
                        fail_text="❌ Ошибка при создании подарка.",
                    )
                    return False
            else:
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=0),
                    exc=RuntimeError("gift key creation returned empty response"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось создать ключ подарка.",
                )
                return False

        elif action == "extend":
            if not rw_repo.update_key(
                key_id,
                remnawave_user_uuid=result['client_uuid'],
                expire_at_ms=result['expiry_timestamp_ms'],
                traffic_limit_bytes=result.get('traffic_limit_bytes'),
                traffic_limit_strategy=result.get('traffic_limit_strategy'),
                tag=origin_tag,
                description=origin_desc,
            ):
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=key_id),
                    exc=RuntimeError("failed to update key after Remnawave extend"),
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Не удалось обновить информацию о ключе. Попробуйте позже.",
                )
                return False
            try:
                # Продление покупает срок, а не сбрасывает трафик: rolling-окно
                # остаётся от дня покупки. Если даты ещё не было (старые ключи) —
                # выравниваем по created_at. Безлимитный основной + LTE-лимит
                # дату сохраняет; полностью безлимитный — очищает.
                database.apply_key_monthly_reset_fields(key_id, plan, restart_cycle=False)
            except Exception:
                logger.warning(f"Не удалось обновить дату сброса трафика при продлении ключа {key_id}", exc_info=True)
            key_issued = True


        try:
            pm_for_ref = (payment_method or '').strip().lower()
            if pm_for_ref in ('balance', 'referralbalance'):
                logger.info(f"Referral: skip accrual for user {user_id} because payment was made from internal balance.")
            else:
                user_data = get_user(user_id) or {}
                referrer_id = user_data.get('referred_by')
                if referrer_id:
                    try:
                        referrer_id = int(referrer_id)
                    except Exception:
                        logger.warning(f"Referral: invalid referrer_id={referrer_id} for user {user_id}")
                        referrer_id = None
                if referrer_id:

                    try:
                        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip()
                    except Exception:
                        reward_type = "percent_purchase"
                    reward = Decimal("0")
                    if reward_type == "fixed_start_referrer":
                        reward = Decimal("0")
                    elif reward_type == "fixed_purchase":
                        try:
                            amount_raw = get_setting("fixed_referral_bonus_amount") or "50"
                            reward = Decimal(str(amount_raw)).quantize(Decimal("0.01"))
                        except Exception:
                            reward = Decimal("50.00")
                    else:

                        try:
                            percentage = Decimal(get_setting("referral_percentage") or "0")
                        except Exception:
                            percentage = Decimal("0")
                        reward = (Decimal(str(price)) * percentage / 100).quantize(Decimal("0.01"))
                    logger.info(f"Referral: user={user_id}, referrer={referrer_id}, type={reward_type}, reward={float(reward):.2f}")
                    if float(reward) > 0:
                        try:
                            ok = add_to_referral_balance(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Referral: add_to_referral_balance failed for referrer {referrer_id}: {e}")
                            ok = False
                        try:
                            add_to_referral_balance_all(referrer_id, float(reward))
                        except Exception as e:
                            logger.warning(f"Failed to increment referral_balance_all for {referrer_id}: {e}")
                        referrer_username = user_data.get('username', 'пользователь')
                        if ok:
                            try:
                                await bot.send_message(
                                    chat_id=referrer_id,
                                    text=(
                                        "💰 Вам начислено реферальное вознаграждение!\n"
                                        f"Пользователь: {referrer_username} (ID: {user_id})\n"
                                        f"Сумма: {float(reward):.2f} RUB"
                                    )
                                )
                            except Exception as e:
                                logger.warning(f"Could not send referral reward notification to {referrer_id}: {e}")
        except Exception as e:
            logger.warning(f"Referral: unexpected error while processing reward for user {user_id}: {e}")


        pm = (payment_method or '').strip().lower()
        spent_for_stats = 0.0 if pm in ('balance', 'referralbalance') else price
        # статистика в месяцах: для тарифов в днях округляем вверх до месяцев
        months_for_stats = months
        try:
            if months_for_stats <= 0:
                eff_days = _compute_days_to_add(plan_months if 'plan_months' in locals() else months, plan_days if 'plan_days' in locals() else duration_days_meta)
                months_for_stats = int(math.ceil(eff_days / 30)) if eff_days > 0 else 0
        except Exception:
            months_for_stats = months
        update_user_stats(user_id, spent_for_stats, months_for_stats)
        
        user_info = get_user(user_id)

        log_username = user_info.get('username', 'N/A') if user_info else 'N/A'
        log_status = 'paid'
        log_amount_rub = float(price)
        log_method = metadata.get('payment_method', 'Unknown')
        
        log_metadata = json.dumps({
            "action": action,
            "key_id": key_id,
            "plan_id": metadata.get('plan_id'),
            "plan_name": get_plan_by_id(metadata.get('plan_id')).get('plan_name', 'Unknown') if get_plan_by_id(metadata.get('plan_id')) else 'Unknown',
            "host_name": metadata.get('host_name'),
            "customer_email": metadata.get('customer_email'),
            **_provider_ids_for_log(metadata),
        })


        payment_id_for_log = metadata.get('payment_id') or str(uuid.uuid4())

        log_transaction(
            username=log_username,
            transaction_id=None,
            payment_id=payment_id_for_log,
            user_id=user_id,
            status=log_status,
            amount_rub=log_amount_rub,
            amount_currency=None,
            currency_name=None,
            payment_method=log_method,
            metadata=log_metadata
        )
        
        try:
            promo_code_val = (metadata.get('promo_code') or '').strip()
        except Exception:
            promo_code_val = ''
        if promo_code_val:
            try:
                applied_amount = float(metadata.get('promo_discount') or 0)
            except Exception:
                applied_amount = 0.0
            promo_info = None
            availability_error = None
            try:
                promo_info = redeem_promo_code(
                    promo_code_val,
                    user_id,
                    applied_amount=applied_amount,
                    order_id=payment_id_for_log
                )
            except Exception as e:
                logger.warning(f"Promo: redeem failed for code {promo_code_val}: {e}")
            should_disable = False
            disable_reason = None
            if promo_info:
                try:
                    limit_user = promo_info.get('usage_limit_per_user') or 0
                    user_used = promo_info.get('user_used_count') or 0
                    metadata['promo_usage_per_user_limit'] = limit_user
                    metadata['promo_usage_per_user_used'] = user_used
                    if limit_user and user_used >= limit_user:
                        metadata['promo_user_limit_reached'] = True
                except Exception:
                    pass
                try:
                    limit_total = promo_info.get('usage_limit_total') or 0
                    used_total = promo_info.get('used_total') or 0
                    metadata['promo_usage_total_limit'] = limit_total
                    metadata['promo_usage_total_used'] = used_total
                    if limit_total and used_total >= limit_total:
                        should_disable = True
                        disable_reason = 'total_limit'
                except Exception:
                    pass
            else:
                metadata['promo_redeem_failed'] = True
                try:
                    _, availability_error = check_promo_code_available(
                        promo_code_val,
                        user_id,
                        plan_id=(metadata.get("plan_id") if isinstance(metadata, dict) else None),
                    )
                except Exception as e:
                    logger.warning(f"Promo: availability check failed for code {promo_code_val}: {e}")
                    availability_error = None
                if availability_error:
                    metadata['promo_availability_error'] = availability_error
                if availability_error == 'user_limit_reached':
                    metadata['promo_user_limit_reached'] = True
                if availability_error == 'total_limit_reached':
                    should_disable = True
                    disable_reason = 'total_limit'
                if availability_error == 'expired':
                    should_disable = True
                    disable_reason = 'expired'
                    metadata['promo_expired'] = True
            if should_disable:
                try:
                    if update_promo_code_status(promo_code_val, is_active=False):
                        metadata['promo_disabled'] = True
                        metadata['promo_disabled_reason'] = disable_reason
                    else:
                        metadata['promo_disable_failed'] = True
                except Exception as e:
                    logger.warning(f"Promo: failed to deactivate code {promo_code_val}: {e}")
                    metadata['promo_disable_failed'] = True
            metadata['promo_applied_amount'] = applied_amount
        
        if processing_message is not None:
            try:
                await processing_message.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение о начале обработки: {e}")

        connection_string = None
        new_expiry_date = None
        try:
            connection_string = result.get('connection_string') if isinstance(result, dict) else None
            new_expiry_date = datetime.fromtimestamp(result['expiry_timestamp_ms'] / 1000) if isinstance(result, dict) and 'expiry_timestamp_ms' in result else None
        except Exception:
            connection_string = None
            new_expiry_date = None
        
        all_user_keys = get_user_keys(user_id)
        key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), len(all_user_keys))

        # Получаем информацию о подарке для этого ключа, если это подарок
        if action == 'gift':
            gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
        else:
            gift_id, gift_code = None, None
        domain = (get_setting("domain") or "").strip()

        final_text = get_purchase_success_text(
            action="extend" if action == "extend" else "new",
            key_number=key_number,
            expiry_date=new_expiry_date or datetime.now(),
            connection_string=connection_string or ""
        )
        
        # Для подарков добавляем ссылку активации выше ссылки подписки
        if gift_code:
            if domain:
                gift_activation_link = f"{domain.rstrip('/')}/start?start=gift_{gift_code}"
            else:
                gift_activation_link = f"https://t.me/{TELEGRAM_BOT_USERNAME}?start=gift_{gift_code}" if TELEGRAM_BOT_USERNAME else None
            
            if gift_activation_link:
                # Добавляем ссылку активации перед ссылкой подписки
                final_text = final_text.replace(
                    f"<code>{html_escape(connection_string or '')}</code>",
                    f"🎁 <b>Ссылка активации подарка:</b>\n<code>{gift_activation_link}</code>\n\n"
                    f"📱 <b>Ссылка подписки:</b>\n<code>{html_escape(connection_string or '')}</code>"
                )
        
        await _deliver_to_user(
            bot,
            user_id,
            final_text,
            reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, gift_code=gift_code, gift_id=gift_id)
        )

        try:
            await notify_admin_of_purchase(bot, metadata)
        except Exception as e:
            logger.warning(f"Failed to notify admin of purchase: {e}")

        return True
        
    except Exception as e:
        logger.error(f"Error processing payment for user {user_id} on host {host_name}: {e}", exc_info=True)
        if not key_issued:
            try:
                await _abort_key_fulfillment(
                    bot,
                    payment_id=payment_id,
                    user_id=user_id,
                    price=price,
                    payment_method=payment_method,
                    action_label=_format_key_action_label(action, price=price, key_id=key_id),
                    exc=e,
                    factory_bot_id=factory_bot_id,
                    processing_message=processing_message,
                    fail_text="❌ Ошибка при выдаче ключа.",
                )
            except Exception:
                await _deliver_to_user(
                    bot, user_id, "❌ Ошибка при выдаче ключа.", edit=processing_message
                )
            return False
        await _deliver_to_user(
            bot, user_id, "❌ Ошибка при выдаче ключа.", edit=processing_message
        )
        # Ключ уже выдан — считаем оплату успешной, несмотря на ошибку нотификации/пост-обработки.
        return True
