"""Список ключей, поиск по ним и переименование.
"""

from html import escape as html_escape
from aiogram import (
    Router,
    F,
    types,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from shop_bot.bot import keyboards
from shop_bot.data_manager.remnawave_repository import get_user_keys
from shop_bot.config import get_key_info_text
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.modules import remnawave_api

__all__: list[str] = []


def register_key_manage(user_router: Router) -> None:
    """Регистрирует хендлеры блока в порядке исходного файла."""

    @user_router.callback_query(F.data.in_({"manage_keys"}) | F.data.startswith("keys_page_"))
    @registration_required
    async def manage_keys_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        page = 0
        if callback.data.startswith("keys_page_"):
            page = int(callback.data.split("_")[-1])

        if page == 0:
            try:
                await sync_user_keys_with_remnawave(user_id)
            except Exception:
                pass

        all_user_keys = get_user_keys(user_id)
        user_keys = [key for key in all_user_keys if str(key.get('tag') or '').strip().lower() not in ('user_gift', 'gift')]
        gift_keys = [key for key in all_user_keys if str(key.get('tag') or '').strip().lower() in ('user_gift', 'gift')]

        has_any = bool(user_keys or gift_keys)
        await callback.message.edit_text(
            "Ваши ключи:" if has_any else "У вас пока нет ключей.",
            reply_markup=keyboards.create_keys_management_keyboard(user_keys, page=page, gift_keys=gift_keys)
        )

    @user_router.callback_query(F.data.in_({"sent_gifts"}) | F.data.startswith("gift_keys_page_"))
    @registration_required
    async def sent_gifts_handler(callback: types.CallbackQuery):
        await callback.answer()
        user_id = callback.from_user.id
        page = 0
        if callback.data.startswith("gift_keys_page_"):
            page = int(callback.data.split("_")[-1])

        all_user_keys = get_user_keys(user_id)
        gift_keys = [key for key in all_user_keys if str(key.get('tag') or '').strip().lower() in ('user_gift', 'gift')]

        await callback.message.edit_text(
            "🎁 Отправленные подарки:" if gift_keys else "У вас нет отправленных подарков.",
            reply_markup=keyboards.create_sent_gifts_keyboard(gift_keys, page=page)
        )

    @user_router.callback_query(F.data == "search_my_keys")
    @registration_required
    async def search_my_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.set_state("search_keys_state")
        await callback.message.edit_text(
            "🔍 Введите название или email ключа для поиска:",
            reply_markup=keyboards.create_search_keys_cancel_keyboard()
        )

    @user_router.message(StateFilter("search_keys_state"))
    @registration_required
    async def search_keys_input_handler(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        search_query = message.text.strip()
        
        if not search_query:
            await message.answer("❌ Пожалуйста, введите email для поиска")
            return
        
        # Импортируем функцию поиска
        from shop_bot.data_manager.remnawave_repository import search_user_keys_by_email
        
        found_keys = search_user_keys_by_email(user_id, search_query)
        
        if not found_keys:
            await message.answer(
                "❌ Ключи не найдены. Попробуйте другой email.",
                reply_markup=keyboards.create_search_keys_cancel_keyboard()
            )
            return
        
        # Сохраняем результаты в state
        await state.update_data(search_results=found_keys)
        
        await message.answer(
            f"🔍 Найдено {len(found_keys)} ключ(ей):",
            reply_markup=keyboards.create_search_keys_results_keyboard(found_keys, page=0)
        )

    @user_router.callback_query(F.data.startswith("search_keys_page_"))
    @registration_required
    async def search_keys_page_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        
        # Получаем номер страницы
        try:
            page = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        # Получаем результаты из state
        data = await state.get_data()
        search_results = data.get('search_results', [])
        
        if not search_results:
            await callback.answer("❌ Результаты поиска потеряны. Попробуйте снова.", show_alert=True)
            return
        
        await callback.message.edit_reply_markup(
            reply_markup=keyboards.create_search_keys_results_keyboard(search_results, page=page)
        )

    @user_router.callback_query(F.data == "cancel_search_keys")
    @registration_required
    async def cancel_search_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.clear()
        
        user_id = callback.from_user.id
        user_keys = get_user_keys(user_id)
        
        await callback.message.edit_text(
            "Ваши ключи:" if user_keys else "У вас пока нет ключей.",
            reply_markup=keyboards.create_keys_management_keyboard(user_keys, page=0)
        )

    # =============================
    # Переименование ключей
    # =============================

    @user_router.callback_query(F.data.startswith("rename_key_"))
    @registration_required
    async def rename_key_start(callback: types.CallbackQuery, state: FSMContext):
        """Начало процесса переименования ключа."""
        await callback.answer()
        
        try:
            key_id = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id)
        
        # Проверка прав доступа
        if not key_data or key_data.get('user_id') != user_id:
            await callback.answer("❌ Ключ не найден или не принадлежит вам", show_alert=True)
            return
        
        # Сохраняем key_id в state
        await state.update_data(key_id=key_id)
        await state.set_state(KeyManagement.waiting_for_rename)
        
        current_name = key_data.get('user_key_name')
        has_name = bool(current_name)
        
        message_text = "📝 <b>Переименование ключа</b>\n\n"
        if current_name:
            message_text += f"<b>Текущее название:</b> {html_escape(current_name)}\n\n"
        
        message_text += (
            "Введите новое название для ключа.\n\n"
            "⚠️ <b>Ограничения:</b>\n"
            "• Максимум 30 символов\n"
            "• Можно использовать emoji ✨\n\n"
            "Используйте кнопки ниже для отмены или удаления названия."
        )
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboards.create_rename_key_keyboard(key_id, has_name=has_name)
        )

    @user_router.message(StateFilter(KeyManagement.waiting_for_rename))
    @registration_required
    async def rename_key_process(message: types.Message, state: FSMContext):
        """Обработка ввода нового названия ключа."""
        user_id = message.from_user.id
        new_name = message.text.strip()
        
        # Получаем key_id из state
        data = await state.get_data()
        key_id = data.get('key_id')
        
        if not key_id:
            await message.answer("❌ Ошибка: ключ не найден. Попробуйте снова.")
            await state.clear()
            return
        
        # Проверка прав доступа
        key_data = rw_repo.get_key_by_id(key_id)
        if not key_data or key_data.get('user_id') != user_id:
            await message.answer("❌ Ключ не найден или не принадлежит вам")
            await state.clear()
            return
        
        # Валидация длины
        if len(new_name) > 30:
            await message.answer(
                f"❌ Название слишком длинное ({len(new_name)} символов).\n"
                f"Максимум 30 символов. Попробуйте короче."
            )
            return
        
        if not new_name:
            await message.answer("❌ Название не может быть пустым. Введите текст или используйте кнопку 'Удалить название'.")
            return
        
        # Обновление названия в БД
        from shop_bot.data_manager.database import update_key_name
        
        success = update_key_name(key_id, new_name)
        
        if not success:
            await message.answer("❌ Не удалось обновить название. Попробуйте ещё раз.")
            await state.clear()
            return
        
        await state.clear()
        
        # Показываем обновлённую карточку ключа
        await message.answer("✅ Название ключа обновлено!")
        
        # Получаем обновлённые данные ключа и показываем карточку
        try:
            key_data = rw_repo.get_key_by_id(key_id)
            details = await remnawave_api.get_key_details_from_host(key_data)
            
            if details and details.get('connection_string'):
                connection_string = details['connection_string']
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
                
                user_payload = details.get('user') if isinstance(details, dict) else None
                devices_connected = await _get_connected_devices_count(key_data, user_payload)
                devices_list = await _get_devices_list(key_data, user_payload)
                plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                
                gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                
                final_text = get_key_info_text(
                    key_data,
                    key_number,
                    devices_connected=devices_connected,
                    plan_group=plan_group,
                    plan_name=plan_name,
                    device_limit=device_limit,
                    gift_code=gift_code,
                )
                
                await message.answer(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                )
            else:
                await message.answer(
                    "Название обновлено, но не удалось загрузить детали ключа.",
                    reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
                )
        except Exception as e:
            logger.error(f"Error showing updated key {key_id}: {e}")
            await message.answer(
                "Название обновлено!",
                reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
            )

    @user_router.callback_query(F.data.startswith("remove_key_name_"))
    @registration_required
    async def remove_key_name(callback: types.CallbackQuery, state: FSMContext):
        """Удаление названия ключа."""
        await callback.answer()
        
        try:
            key_id = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id)
        
        # Проверка прав доступа
        if not key_data or key_data.get('user_id') != user_id:
            await callback.answer("❌ Ключ не найден или не принадлежит вам", show_alert=True)
            return
        
        # Удаление названия (устанавливаем None)
        from shop_bot.data_manager.database import update_key_name
        
        success = update_key_name(key_id, None)
        
        if not success:
            await callback.answer("❌ Не удалось удалить название", show_alert=True)
            return
        
        await state.clear()
        await callback.message.edit_text("✅ Название ключа удалено!")
        
        # Показываем обновлённую карточку ключа
        try:
            key_data = rw_repo.get_key_by_id(key_id)
            details = await remnawave_api.get_key_details_from_host(key_data)
            
            if details and details.get('connection_string'):
                connection_string = details['connection_string']
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
                
                user_payload = details.get('user') if isinstance(details, dict) else None
                devices_connected = await _get_connected_devices_count(key_data, user_payload)
                devices_list = await _get_devices_list(key_data, user_payload)
                plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                
                gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                
                final_text = get_key_info_text(
                    key_data,
                    key_number,
                    devices_connected=devices_connected,
                    plan_group=plan_group,
                    plan_name=plan_name,
                    device_limit=device_limit,
                    gift_code=gift_code,
                )
                
                await callback.message.answer(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                )
            else:
                await callback.message.answer(
                    "Название удалено!",
                    reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
                )
        except Exception as e:
            logger.error(f"Error showing updated key {key_id}: {e}")
            await callback.message.answer(
                "Название удалено!",
                reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
            )

    @user_router.callback_query(F.data.startswith("cancel_rename_key_"))
    @registration_required
    async def cancel_rename_key(callback: types.CallbackQuery, state: FSMContext):
        """Отмена переименования ключа."""
        await callback.answer()
        await state.clear()
        
        try:
            key_id = int(callback.data.split("_")[-1])
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        user_id = callback.from_user.id
        key_data = rw_repo.get_key_by_id(key_id)
        
        # Проверка прав доступа
        if not key_data or key_data.get('user_id') != user_id:
            await callback.answer("❌ Ключ не найден", show_alert=True)
            return
        
        # Показываем карточку ключа
        try:
            details = await remnawave_api.get_key_details_from_host(key_data)
            
            if details and details.get('connection_string'):
                connection_string = details['connection_string']
                all_user_keys = get_user_keys(user_id)
                key_number = next((i + 1 for i, key in enumerate(all_user_keys) if key['key_id'] == key_id), 0)
                
                user_payload = details.get('user') if isinstance(details, dict) else None
                devices_connected = await _get_connected_devices_count(key_data, user_payload)
                devices_list = await _get_devices_list(key_data, user_payload)
                plan_group, plan_name, device_limit = _get_tariff_info_for_key(key_data, user_payload)
                
                gift_id, gift_code = rw_repo.get_gift_info_by_key_id(key_id)
                
                final_text = get_key_info_text(
                    key_data,
                    key_number,
                    devices_connected=devices_connected,
                    plan_group=plan_group,
                    plan_name=plan_name,
                    device_limit=device_limit,
                    gift_code=gift_code,
                )
                
                await callback.message.edit_text(
                    text=final_text,
                    reply_markup=keyboards.create_key_info_keyboard(key_id, connection_string, devices_list=devices_list, gift_code=gift_code, gift_id=gift_id)
                )
            else:
                await callback.message.edit_text(
                    "❌ Не удалось загрузить данные ключа",
                    reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
                )
        except Exception as e:
            logger.error(f"Error showing key {key_id}: {e}")
            await callback.message.edit_text(
                "⬅️ Отменено",
                reply_markup=keyboards.create_keys_management_keyboard(get_user_keys(user_id), page=0)
            )
