"""Кнопки «Проверить оплату» для всех провайдеров.
"""

import aiohttp
import json
from yookassa import (
    Payment,
    Configuration,
)
from decimal import Decimal
from aiogram import (
    Router,
    F,
    Bot,
    types,
)
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    cancel_pending_transaction,
    get_pending_status,
    get_pending_metadata,
    find_and_complete_pending_transaction,
)
from shop_bot.data_manager.database import _get_pending_metadata

__all__: list[str] = []


def register_payment_checks(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    
    @user_router.callback_query(F.data.startswith("check_platega:"))
    async def check_platega_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return

        # сначала проверим локально
        try:
            status = (get_pending_status(pid) or "").lower()
        except Exception:
            status = ""
        if status == "paid":
            await callback.answer("✅ Оплата уже получена и обработана.", show_alert=True)
            return

        meta = None
        try:
            meta = _get_pending_metadata(pid)
        except Exception:
            meta = None
        txid = None
        if isinstance(meta, dict):
            txid = meta.get("platega_transaction_id") or meta.get("transaction_id")

        if not txid:
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        remote = await _get_platega_transaction(str(txid))
        if not remote:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return

        remote_status = str(remote.get("status") or "").upper()
        if remote_status == "CONFIRMED":
            metadata = find_and_complete_pending_transaction(pid)
            if not metadata:
                await callback.answer("✅ Оплата подтверждена, но транзакция уже обработана.", show_alert=True)
                return
            try:
                await process_successful_payment(bot, metadata)
                await callback.answer("✅ Оплата получена! Обрабатываю…", show_alert=True)
            except Exception as e:
                logger.error(f"Platega manual check: process_successful_payment failed: {e}", exc_info=True)
                await callback.answer("⚠️ Оплата получена, но обработка не завершена. Напишите в поддержку.", show_alert=True)
            return

        if remote_status in {"FAILED", "CANCELED", "CANCELLED", "EXPIRED", "CHARGEBACKED"}:
            cancel_pending_transaction(pid)
            await callback.answer(f"❌ Платеж завершился со статусом: {remote_status}", show_alert=True)
            return

        await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)

    @user_router.callback_query(F.data.startswith("check_rollypay:"))
    async def check_rollypay_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return

        try:
            status = (get_pending_status(pid) or "").lower()
        except Exception:
            status = ""
        if status == "paid":
            await callback.answer("✅ Оплата уже получена и обработана.", show_alert=True)
            return

        meta = None
        try:
            meta = _get_pending_metadata(pid)
        except Exception:
            meta = None
        if not isinstance(meta, dict) or str(meta.get("payment_method") or "") != "RollyPay":
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        txid = meta.get("rollypay_payment_id")
        if not txid:
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        from shop_bot.modules.rollypay_api import RollyPayAPI

        api_key = (get_setting("rollypay_api_key") or "").strip()
        if not api_key:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return
        remote = await RollyPayAPI(api_key, get_setting("rollypay_terminal_id") or "").get_payment(str(txid))
        if not remote:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return

        remote_status = str(remote.get("status") or "").strip().lower()
        if remote_status != "paid":
            if remote_status in {"expired", "canceled", "cancelled", "chargeback"}:
                cancel_pending_transaction(pid)
                await callback.answer(f"❌ Платеж завершился со статусом: {remote_status}", show_alert=True)
                return
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        if str(remote.get("order_id") or "").strip() != str(pid):
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        try:
            expected = Decimal(str(meta.get("price")))
            got = Decimal(str(remote.get("amount")))
        except Exception:
            await callback.answer("⏳ Не удалось проверить статус. Попробуйте позже.", show_alert=True)
            return
        if got.quantize(Decimal("0.01")) != expected.quantize(Decimal("0.01")):
            logger.warning("RollyPay manual check: amount mismatch payment_id=%s got=%s expected=%s", pid, got, expected)
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        metadata = find_and_complete_pending_transaction(pid)
        if not metadata:
            await callback.answer("✅ Оплата подтверждена, но транзакция уже обработана.", show_alert=True)
            return
        metadata.setdefault("payment_method", "RollyPay")
        metadata["rollypay_payment_id"] = str(txid)
        try:
            await process_successful_payment(bot, metadata)
            await callback.answer("✅ Оплата получена! Обрабатываю…", show_alert=True)
        except Exception as e:
            logger.error(f"RollyPay manual check: process_successful_payment failed: {e}", exc_info=True)
            await callback.answer("⚠️ Оплата получена, но обработка не завершена. Напишите в поддержку.", show_alert=True)

    @user_router.callback_query(F.data.startswith("check_yookassa:"))
    async def check_yookassa_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return

        status = ""
        try:
            status = (get_pending_status(pid) or "").lower()
        except Exception as e:
            logger.error(f"YooKassa manual check: failed to read local status for {pid}: {e}")
        if status == "paid":
            await callback.answer("✅ Оплата уже подтверждена. Профиль/баланс скоро обновится.", show_alert=True)
            return

        pending_meta = None
        try:
            pending_meta = get_pending_metadata(pid)
        except Exception as e:
            logger.error(f"YooKassa manual check: failed to read pending metadata for {pid}: {e}")

        if not pending_meta:
            await callback.answer("❌ Платёж не найден. Попробуйте позже.", show_alert=True)
            return

        provider_payment_id = (pending_meta.get("yookassa_payment_id") or "").strip()
        if not provider_payment_id:
            await callback.answer("⚠️ Не удалось проверить оплату. Попробуйте позже.", show_alert=True)
            return

        shop_id = (get_setting("yookassa_shop_id") or "").strip()
        secret_key = (get_setting("yookassa_secret_key") or "").strip()
        if not shop_id or not secret_key:
            await callback.answer("⚠️ YooKassa не настроен. Обратитесь к администратору.", show_alert=True)
            return

        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

        try:
            payment = Payment.find_one(provider_payment_id)
        except Exception as e:
            logger.error(f"YooKassa manual check: failed to fetch payment {provider_payment_id}: {e}", exc_info=True)
            await callback.answer("⚠️ Не удалось проверить оплату через YooKassa. Попробуйте позже.", show_alert=True)
            return

        remote_status = (getattr(payment, "status", "") or "").lower()
        if remote_status != "succeeded":
            if remote_status == "canceled":
                cancel_pending_transaction(pid)
                await callback.answer("❌ Платёж отменён.", show_alert=True)
                return
            await callback.answer("⏳ Платеж ещё не подтверждён. Попробуйте позже.", show_alert=True)
            return

        amount_obj = getattr(payment, "amount", None)
        if isinstance(amount_obj, dict):
            value_str = amount_obj.get("value")
            currency = (amount_obj.get("currency") or "").upper()
        else:
            value_str = getattr(amount_obj, "value", None)
            currency = (getattr(amount_obj, "currency", "") or "").upper()

        try:
            expected_amount = Decimal(str(pending_meta.get('price') or pending_meta.get('amount_rub') or '0')).quantize(Decimal('0.01'))
            got_amount = Decimal(str(value_str or '0')).quantize(Decimal('0.01'))
        except Exception as e:
            logger.warning(f"YooKassa manual check: amount parse error for {pid}: value={value_str} error={e}")
            await callback.answer("⚠️ Не удалось проверить сумму оплаты. Попробуйте позже.", show_alert=True)
            return

        if currency and currency != "RUB":
            logger.warning(f"YooKassa manual check: currency mismatch for {pid}: got={currency}, expected=RUB")
            await callback.answer("❌ Валюта платежа не совпадает. Обратитесь в поддержку.", show_alert=True)
            return
        if got_amount != expected_amount:
            logger.warning(f"YooKassa manual check: amount mismatch for {pid}: got={got_amount}, expected={expected_amount}")
            await callback.answer("❌ Сумма платежа не совпадает. Обратитесь в поддержку.", show_alert=True)
            return

        metadata = find_and_complete_pending_transaction(pid)
        if not metadata:
            await callback.answer("✅ Оплата подтверждена, но транзакция уже обработана.", show_alert=True)
            return
        try:
            await process_successful_payment(bot, metadata)
            await callback.answer("✅ Оплата получена! Обрабатываю…", show_alert=True)
        except Exception as e:
            logger.error(f"YooKassa manual check: process_successful_payment failed: {e}", exc_info=True)
            await callback.answer("⚠️ Оплата получена, но обработка не завершена. Напишите в поддержку.", show_alert=True)

    @user_router.callback_query(F.data.startswith("check_pending:"))
    async def check_pending_payment_handler(callback: types.CallbackQuery, bot: Bot):
        try:
            pid = callback.data.split(":", 1)[1]
        except Exception:
            await callback.answer("Некорректный идентификатор платежа.", show_alert=True)
            return
        
        logger.info(f"🔍 Проверяем статус платежа: {pid}")
        
        try:
            status = get_pending_status(pid) or ""
            logger.info(f"📊 Локальный статус: {status}")
        except Exception as e:
            logger.error(f"❌ Ошибка проверки локального статуса для {pid}: {e}")
            status = ""
        if status and status.lower() == 'paid':
            logger.info(f"✅ Платеж уже обработан локально: {pid}")
            await callback.answer("✅ Оплата получена! Профиль/баланс скоро обновится.", show_alert=True)
            return


        token = (get_setting('yoomoney_api_token') or '').strip()
        if not token:
            logger.warning(f"⚠️ Нет токена API ЮMoney для платежа {pid}")
            if not status:
                await callback.answer("❌ Платёж не найден. Проверьте позже.", show_alert=True)
            else:
                await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)
            return

        try:
            logger.info(f"🌐 Проверяем платеж через API ЮMoney: {pid}")
            async with aiohttp.ClientSession() as session:
                data = {"label": pid, "records": "10"}
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                async with session.post("https://yoomoney.ru/api/operation-history", data=data, headers=headers, timeout=15) as resp:
                    text = await resp.text()
                    logger.info(f"📡 Ответ API: статус={resp.status}")
                    if resp.status != 200:
                        await callback.answer("⚠️ Не удалось проверить оплату через YooMoney. Попробуйте позже.", show_alert=True)
                        return
        except Exception as e:
            logger.error(f"💥 Ошибка проверки API для {pid}: {e}")
            await callback.answer("⚠️ Ошибка связи с YooMoney. Попробуйте позже.", show_alert=True)
            return
        try:
            payload = json.loads(text)
        except Exception as e:
            logger.error(f"💥 Не удалось разобрать ответ API: {e}")
            payload = {}
        ops = payload.get('operations') or []
        logger.info(f"📋 Найдено операций: {len(ops)}")
        paid = False
        for op in ops:
            try:
                op_label = str(op.get('label'))
                op_status = str(op.get('status','')).lower()
                if op_label == pid and op_status in {"success","done"}:
                    paid = True
                    logger.info(f"✅ Найдена оплаченная операция: {op_label} | {op_status}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Ошибка обработки операции: {e}")
                continue
        if paid:
            logger.info(f"🎉 Платеж подтвержден через API, обрабатываем: {pid}")
            try:
                metadata = find_and_complete_pending_transaction(pid)
            except Exception as e:
                logger.error(f"💥 Ошибка поиска ожидающей транзакции: {e}")
                metadata = None
            if metadata:
                try:
                    await process_successful_payment(bot, metadata)
                except Exception as e:
                    logger.error(f"💥 Ошибка в process_successful_payment: {e}")
            await callback.answer("✅ Оплата получена! Профиль/баланс скоро обновится.", show_alert=True)
            return

        logger.info(f"⏳ Платеж не найден или еще не оплачен: {pid}")
        await callback.answer("⏳ Оплата ещё не поступила. Попробуйте через минуту.", show_alert=True)
