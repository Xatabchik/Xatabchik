"""Активация подарочного кода без участия дарителя.
"""

from aiogram import (
    Bot,
    types,
)
from shop_bot.bot import keyboards
from shop_bot.data_manager import remnawave_repository as rw_repo

__all__ = [
    "_activate_gift_directly",
]

async def _activate_gift_directly(
    message: types.Message, bot: Bot, user_id: int, gift_code: str,
    *, is_new_user: bool = False
) -> None:
    """Активировать подарок для пользователя."""
    try:
        gift = rw_repo.get_gift_by_code(gift_code)
        if not gift:
            await message.answer(
                "❌ Подарок не найден. Возможно, срок его действия истёк или код неверный.",
                reply_markup=keyboards.main_reply_keyboard
            )
            return
        
        if gift.get('is_activated'):
            await message.answer(
                "⚠️ Этот подарок уже был активирован.",
                reply_markup=keyboards.main_reply_keyboard
            )
            return
        
        # Активируем подарок
        success, activated_gift = rw_repo.activate_user_gift(gift_code, user_id)
        if not success:
            await message.answer(
                "❌ Не удалось активировать подарок. Попробуйте позже.",
                reply_markup=keyboards.main_reply_keyboard
            )
            return

        # Привязываем нового пользователя к отправителю подарка как реферала
        if is_new_user:
            try:
                from_user_id = int((activated_gift or gift or {}).get("from_user_id") or 0)
                if from_user_id > 0:
                    rw_repo.set_referred_by_from_gift(user_id, from_user_id)
            except Exception:
                pass
        
        # Получаем информацию о ключе
        key_id = gift.get('key_id')
        if key_id:
            key_data = rw_repo.get_key_by_id(key_id)
            if key_data:
                # Переассоциируем ключ на нового пользователя
                try:
                    # Генерируем новый email для пользователя
                    new_email = rw_repo.generate_key_email_for_user(user_id)
                    
                    # Обновляем ключ в БД
                    rw_repo.update_key(
                        key_id,
                        user_id=user_id,
                        email=new_email,
                        tag="",  # Убираем тег "user_gift" чтобы ключ появился в списке ключей
                    )
                    
                    success_msg = (
                        "🎁 <b>Подарок успешно активирован!</b>\n\n"
                        f"✅ Ключ добавлен в ваш профиль\n"
                        f"🖥️ Сервер: {key_data.get('host_name', 'Unknown')}\n"
                        f"📅 Истекает: {key_data.get('expiry_date', 'Unknown')}"
                    )
                    await message.answer(success_msg, reply_markup=keyboards.main_reply_keyboard)
                    await show_main_menu(message)
                    
                except Exception as e:
                    logger.error(f"Error reassigning gift key {key_id} to user {user_id}: {e}")
                    await message.answer(
                        "⚠️ Подарок активирован, но произошла ошибка при привязке ключа. Свяжитесь с поддержкой.",
                        reply_markup=keyboards.main_reply_keyboard
                    )
            else:
                await message.answer(
                    "⚠️ Подарок активирован, но ключ не найден. Свяжитесь с поддержкой.",
                    reply_markup=keyboards.main_reply_keyboard
                )
        else:
            await message.answer(
                "⚠️ Подарок активирован, но информация о ключе недоступна.",
                reply_markup=keyboards.main_reply_keyboard
            )
    
    except Exception as e:
        logger.error(f"Error activating gift {gift_code} for user {user_id}: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при активации подарка. Попробуйте позже.",
            reply_markup=keyboards.main_reply_keyboard
        )
