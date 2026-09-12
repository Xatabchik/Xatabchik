"""Профиль пользователя и полученные подарки.
"""

from html import escape as html_escape
from datetime import datetime
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import (
    get_user,
    get_user_keys,
    get_balance,
    get_referral_count,
    get_referral_balance_all,
)
from shop_bot.config import (
    get_profile_text,
    get_vpn_active_text,
    VPN_INACTIVE_TEXT,
    VPN_NO_DATA_TEXT,
    get_key_info_text,
)
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.modules import remnawave_api

# Имя нужно уже на этапе импорта (декоратор применяется при
# определении функции), поэтому импортируется явно, а не через
# связывание пространств имён в __init__.
from .menu import registration_required

__all__ = [
    "profile_handler_callback",
]

@registration_required
async def profile_handler_callback(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user_db_data = get_user(user_id)
    user_keys = get_user_keys(user_id)
    if not user_db_data:
        await callback.answer("Не удалось получить данные профиля.", show_alert=True)
        return
    username = html_escape(str(user_db_data.get('username', 'Пользователь') or 'Пользователь'))
    total_spent, total_months = user_db_data.get('total_spent', 0), user_db_data.get('total_months', 0)
    now = datetime.now()
    active_keys = [key for key in user_keys if datetime.fromisoformat(key['expiry_date']) > now]
    if active_keys:
        latest_key = max(active_keys, key=lambda k: datetime.fromisoformat(k['expiry_date']))
        latest_expiry_date = datetime.fromisoformat(latest_key['expiry_date'])
        time_left = latest_expiry_date - now
        vpn_status_text = get_vpn_active_text(time_left.days, time_left.seconds // 3600)
    elif user_keys: vpn_status_text = VPN_INACTIVE_TEXT
    else: vpn_status_text = VPN_NO_DATA_TEXT
    final_text = get_profile_text(username, total_spent, total_months, vpn_status_text)

    try:
        main_balance = get_balance(user_id)
    except Exception:
        main_balance = 0.0
    final_text += f"\n\n💼 <b>Основной баланс:</b> {main_balance:.0f} RUB"

    try:
        referral_count = get_referral_count(user_id)
    except Exception:
        referral_count = 0
    try:
        total_ref_earned = float(get_referral_balance_all(user_id))
    except Exception:
        total_ref_earned = 0.0
    final_text += (
        f"\n🤝 <b>Рефералы:</b> {referral_count}"
        f"\n💰 <b>Заработано по рефералке (всего):</b> {total_ref_earned:.2f} RUB"
    )
    
    # Показываем кнопку уведомлений только если ключей больше 10
    show_notification_toggle = len(user_keys) > 10 if user_keys else False
    try:
        gifts_count = len(rw_repo.get_user_inactive_gifts(user_id) or [])
    except Exception:
        gifts_count = len(
            [k for k in (user_keys or []) if str(k.get('tag') or '').strip().lower() in ('user_gift', 'gift')]
        )
    notifications_enabled = True
    if show_notification_toggle:
        try:
            notifications_enabled = rw_repo.is_subscription_expiry_notifications_enabled(user_id)
        except Exception:
            notifications_enabled = True

    # Автопродление: показываем переключатель если у пользователя есть хотя бы один ключ с тарифом
    non_gift_keys = [k for k in user_keys if str(k.get("tag") or "").strip().lower() not in ("user_gift", "gift")]
    show_auto_renew_toggle = bool(non_gift_keys)
    auto_renew_any_enabled = any(bool(int(k.get("auto_renew") or 0)) for k in non_gift_keys)

    await _safe_edit_or_answer(
        callback.message,
        final_text,
        reply_markup=keyboards.create_profile_keyboard(
            show_notification_toggle=show_notification_toggle,
            notifications_enabled=notifications_enabled,
            gifts_count=gifts_count,
            show_auto_renew_toggle=show_auto_renew_toggle,
            auto_renew_any_enabled=auto_renew_any_enabled,
        )
    )


def register_profile_gifts(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    user_router.callback_query(F.data == 'show_profile')(profile_handler_callback)

    @user_router.callback_query(F.data == "toggle_expiry_notifications")
    @registration_required
    async def toggle_expiry_notifications_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        try:
            new_state = rw_repo.toggle_subscription_expiry_notifications(user_id)
            state_text = "✅ Уведомления включены" if new_state else "❌ Уведомления отключены"
            await callback.answer(state_text, show_alert=True)
            # Обновляем профиль пользователя
            await profile_handler_callback(callback)
        except Exception as e:
            logger.error(f"Ошибка при переключении уведомлений для {user_id}: {e}")
            await callback.answer("❌ Ошибка при переключении уведомлений", show_alert=True)

    @user_router.callback_query(F.data == "show_inactive_gifts")
    @registration_required
    async def show_inactive_gifts_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        
        try:
            gifts = rw_repo.get_user_inactive_gifts(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении неактивных подарков для {user_id}: {e}")
            await callback.answer("❌ Ошибка при получении списка подарков", show_alert=True)
            return
        
        if not gifts:
            await callback.message.edit_text(
                "🎁 У вас нет неактивных подарков.\n\nВы можете купить подарок в главном меню.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        
        await callback.message.edit_text(
            "🎁 <b>Ваши неактивные подарки:</b>",
            reply_markup=keyboards.create_gifts_management_keyboard(gifts, page=0)
        )

    @user_router.callback_query(F.data.startswith("gifts_page_"))
    @registration_required
    async def gifts_page_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        
        # Получаем номер страницы
        try:
            page = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        try:
            gifts = rw_repo.get_user_inactive_gifts(user_id)
        except Exception as e:
            logger.error(f"Ошибка при получении подарков для страницы {page}: {e}")
            await callback.answer("❌ Ошибка при получении списка подарков", show_alert=True)
            return
        
        if not gifts:
            await callback.message.edit_text(
                "🎁 У вас нет неактивных подарков.",
                reply_markup=keyboards.create_back_to_menu_keyboard()
            )
            return
        
        await callback.message.edit_reply_markup(
            reply_markup=keyboards.create_gifts_management_keyboard(gifts, page=page)
        )

    @user_router.callback_query(F.data.startswith("show_gift_"))
    @registration_required
    async def show_gift_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        
        try:
            gift_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных подарка", show_alert=True)
            return
        
        await callback.message.edit_text("Загружаю информацию о подарке...")
        
        try:
            # Получаем информацию о подарке
            gift = rw_repo.get_user_gift(gift_id)
            if not gift:
                await callback.message.edit_text("❌ Подарок не найден")
                return
            
            # Проверяем что подарок принадлежит пользователю
            if gift.get('from_user_id') != user_id:
                await callback.answer("❌ Это не ваш подарок", show_alert=True)
                return
            
            key_id = gift.get('key_id')
            gift_code = gift.get('gift_code')
            is_activated = gift.get('is_activated', False)
            
            # Получаем ключ из БД
            if not key_id:
                await callback.message.edit_text("❌ Ключ для этого подарка не найден")
                return
            
            key_data = rw_repo.get_key_by_id(key_id)
            if not key_data:
                await callback.message.edit_text("❌ Данные ключа не найдены")
                return
            
            # Получаем детали ключа с сервера (как в show_key_handler)
            try:
                details = await remnawave_api.get_key_details_from_host(key_data)
                if not details or not details.get('connection_string'):
                    await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                    return
            except Exception as e:
                logger.error(f"Error getting key details for gift {gift_id}: {e}")
                await callback.message.edit_text("❌ Ошибка на сервере. Не удалось получить данные ключа.")
                return

            connection_string = details['connection_string']
            
            # Получаем информацию о тарифе
            user_payload = details.get('user') if isinstance(details, dict) else None
            devices_connected = await _get_connected_devices_count(key_data, user_payload)
            devices_list = await _get_devices_list(key_data, user_payload)
            plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
            
            # Формируем ссылки активации подарка — и в webapp, и в Telegram, как в мини-приложении
            gift_link, gift_telegram_link = None, None
            if gift_code and not is_activated:
                gift_link, gift_telegram_link = _build_gift_links(gift_code)
            
            # Выводим ключ как обычно
            gift_text = get_key_info_text(
                key_data,
                key_number=1,
                devices_connected=devices_connected,
                plan_group=plan_group,
                plan_name=plan_name,
                device_limit=device_limit,
                gift_code=gift_code,
                is_gift_activated=is_activated,
                gift_link=gift_link,
                gift_telegram_link=gift_telegram_link,
            )
            
            await callback.message.edit_text(
                gift_text,
                reply_markup=keyboards.create_gift_info_keyboard(
                    gift_id, key_id, is_activated, connection_string, devices_list, gift_link
                ),
                disable_web_page_preview=True
            )
        
        except Exception as e:
            logger.error(f"Error showing gift {gift_id}: {e}", exc_info=True)
            await callback.message.edit_text("❌ Произошла ошибка при получении информации о подарке.")

    @user_router.callback_query(F.data.startswith("send_gift_link_"))
    @registration_required
    async def send_gift_link_handler(callback: types.CallbackQuery):
        """Отправка ссылки подарка пользователю."""
        await callback.answer()
        user_id = callback.from_user.id
        
        try:
            gift_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных подарка", show_alert=True)
            return
        
        try:
            # Получаем информацию о подарке
            gift = rw_repo.get_user_gift(gift_id)
            if not gift:
                await callback.answer("❌ Подарок не найден", show_alert=True)
                return
            
            # Проверяем что подарок принадлежит пользователю
            if gift.get('from_user_id') != user_id:
                await callback.answer("❌ Это не ваш подарок", show_alert=True)
                return
            
            gift_code = gift.get('gift_code')
            
            if not gift_code:
                await callback.answer("❌ Не удалось сформировать ссылку подарка", show_alert=True)
                return
            
            # Формируем обе ссылки подарка — в мини-приложении и в Telegram
            gift_link, gift_telegram_link = _build_gift_links(gift_code)
            
            if not gift_link and not gift_telegram_link:
                await callback.answer("❌ Не удалось сформировать ссылку подарка", show_alert=True)
                return
            
            share_text = _gift_share_text()
            
            text_parts = ["🎁 <b>Ссылки активации подарка</b> (нажмите, чтобы скопировать):\n"]
            builder = InlineKeyboardBuilder()
            if gift_link:
                text_parts.append(f"<i>В приложении:</i>\n<code>{html_escape(gift_link)}</code>\n")
                builder.button(
                    text="📤 Поделиться (в приложении)",
                    url=_telegram_share_url(gift_link, share_text),
                )
            if gift_telegram_link:
                text_parts.append(f"<i>В Telegram:</i>\n<code>{html_escape(gift_telegram_link)}</code>\n")
                builder.button(
                    text="📤 Поделиться (в Telegram)",
                    url=_telegram_share_url(gift_telegram_link, share_text),
                )
            builder.button(text="⬅️ Назад", callback_data=f"show_gift_{gift_id}")
            builder.adjust(1)
            
            await callback.message.edit_text(
                "".join(text_parts),
                reply_markup=builder.as_markup()
            )
            
        except Exception as e:
            logger.error(f"Error sending gift link {gift_id}: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при отправке ссылки", show_alert=True)

    @user_router.callback_query(F.data.startswith("activate_own_gift_"))
    @registration_required
    async def activate_own_gift_handler(callback: types.CallbackQuery):
        """Активировать собственный неактивированный подарок себе (аналог webapp-кнопки 'Активировать себе')."""
        await callback.answer()
        user_id = callback.from_user.id

        try:
            gift_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных подарка", show_alert=True)
            return

        try:
            gift = rw_repo.get_user_gift(gift_id)
            if not gift:
                await callback.answer("❌ Подарок не найден", show_alert=True)
                return

            if gift.get('from_user_id') != user_id:
                await callback.answer("❌ Это не ваш подарок", show_alert=True)
                return

            if gift.get('is_activated'):
                await callback.answer("⚠️ Этот подарок уже был активирован", show_alert=True)
                return

            gift_code = gift.get('gift_code')
            if not gift_code:
                await callback.answer("❌ Не удалось активировать подарок", show_alert=True)
                return

            await _activate_gift_directly(callback.message, callback.bot, user_id, gift_code, is_new_user=False)
        except Exception as e:
            logger.error(f"Error activating own gift {gift_id} for user {user_id}: {e}", exc_info=True)
            await callback.answer("❌ Произошла ошибка при активации подарка", show_alert=True)
