"""Ключи: поиск, карточка, правка email, продление, удаление.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import html as html_escape

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import (
    get_keys_for_user,
    delete_key_by_email,
    get_keys_for_host,
    is_admin,
)
from shop_bot.data_manager.database import update_key_email
from shop_bot.modules.remnawave_api import create_or_update_key_on_host, delete_client_on_host


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_keys_1(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""

    @admin_router.callback_query(F.data.startswith("admin_search_user_keys_"))
    async def admin_search_user_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        
        try:
            user_id = int(callback.data.split("_")[-1])
        except (IndexError, ValueError):
            await callback.answer("❌ Ошибка в данных", show_alert=True)
            return
        
        # Сохраняем user_id в state для использования в обработчике ввода
        await state.update_data(search_user_id=user_id)
        await state.set_state("admin_search_user_keys_state")
        
        await callback.message.edit_text(
            "🔍 Введите название или email ключа для поиска:",
            reply_markup=keyboards.create_admin_search_keys_cancel_keyboard()
        )

    @admin_router.message(StateFilter("admin_search_user_keys_state"))
    async def admin_search_user_keys_input_handler(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        search_query = message.text.strip()
        
        if not search_query:
            await message.answer("❌ Пожалуйста, введите email для поиска")
            return
        
        # Получаем user_id из state
        data = await state.get_data()
        user_id = data.get('search_user_id')
        
        if not user_id:
            await message.answer("❌ Ошибка. Попробуйте снова.")
            await state.clear()
            return
        
        # Импортируем функцию поиска
        from shop_bot.data_manager.remnawave_repository import search_user_keys_by_email
        
        found_keys = search_user_keys_by_email(user_id, search_query)
        
        if not found_keys:
            await message.answer(
                "❌ Ключи не найдены. Попробуйте другой email.",
                reply_markup=keyboards.create_admin_search_keys_cancel_keyboard()
            )
            return
        
        # Сохраняем результаты в state
        await state.update_data(search_results=found_keys)
        
        await message.answer(
            f"🔍 Найдено {len(found_keys)} ключ(ей):",
            reply_markup=keyboards.create_admin_search_keys_results_keyboard(found_keys, page=0, user_id=user_id)
        )

    @admin_router.callback_query(F.data.startswith("admin_search_keys_page_"))
    async def admin_search_keys_page_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
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
        user_id = data.get('search_user_id')
        
        if not search_results:
            await callback.answer("❌ Результаты поиска потеряны. Попробуйте снова.", show_alert=True)
            return
        
        await callback.message.edit_reply_markup(
            reply_markup=keyboards.create_admin_search_keys_results_keyboard(search_results, page=page, user_id=user_id)
        )

    @admin_router.callback_query(F.data == "admin_search_all_keys")
    async def admin_search_all_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        
        # Для общего поиска не сохраняем user_id
        await state.set_state("admin_search_all_keys_state")
        
        await callback.message.edit_text(
            "🔍 Введите название или email ключа для поиска во всех ключах:",
            reply_markup=keyboards.create_admin_search_keys_cancel_keyboard()
        )

    @admin_router.message(StateFilter("admin_search_all_keys_state"))
    async def admin_search_all_keys_input_handler(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        search_query = message.text.strip()
        
        if not search_query:
            await message.answer("❌ Пожалуйста, введите email для поиска")
            return
        
        # Импортируем функцию поиска
        from shop_bot.data_manager.remnawave_repository import search_all_keys_by_email
        
        found_keys = search_all_keys_by_email(search_query)
        
        if not found_keys:
            await message.answer(
                "❌ Ключи не найдены. Попробуйте другой email.",
                reply_markup=keyboards.create_admin_search_keys_cancel_keyboard()
            )
            return
        
        # Сохраняем результаты в state
        await state.update_data(search_results=found_keys)
        
        await message.answer(
            f"🔍 Найдено {len(found_keys)} ключ(ей):",
            reply_markup=keyboards.create_admin_search_keys_results_keyboard(found_keys, page=0, user_id=None)
        )

    @admin_router.callback_query(F.data == "admin_cancel_search_keys")
    async def admin_cancel_search_keys_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        await state.clear()
        
        await callback.message.edit_text(
            "❌ Поиск отменён.",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.callback_query(F.data.startswith("admin_edit_key_"))
    async def admin_edit_key(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат key_id")
            return
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            await callback.message.answer("❌ Ключ не найден")
            return
        conn_str = key.get('subscription_url') or key.get('connection_string') or '—'
        text = (
            f"🔑 <b>Ключ #{key_id}</b>\n"
            f"Хост: {key.get('host_name') or '—'}\n"
            f"Email: {key.get('key_email') or '—'}\n"
            f"Истекает: {key.get('expiry_date') or '—'}\n\n"
            f"<code>{html_escape.escape(conn_str)}</code>\n\n"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_admin_key_actions_keyboard(key_id, int(key.get('user_id')) if key and key.get('user_id') else None)
            )
        except Exception as e:
            logger.debug(f"edit_text не удался в отмене удаления для ключа #{key_id}: {e}")
            await callback.message.answer(
                text,
                reply_markup=keyboards.create_admin_key_actions_keyboard(key_id, int(key.get('user_id')) if key and key.get('user_id') else None)
            )



    @admin_router.callback_query(F.data.regexp(r"^admin_key_delete_\d+$"))
    async def admin_key_delete_prompt(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        logger.info(f"Получен запрос на удаление ключа: data='{callback.data}' от {callback.from_user.id}")
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат key_id")
            return
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            await callback.message.answer("❌ Ключ не найден")
            return
        email = key.get('key_email') or '—'
        host = key.get('host_name') or '—'
        try:
            await callback.message.edit_text(
                f"Вы уверены, что хотите удалить ключ #{key_id}?\nEmail: {email}\nСервер: {host}",
                reply_markup=keyboards.create_admin_delete_key_confirm_keyboard(key_id)
            )
        except Exception as e:
            logger.debug(f"edit_text не удался в запросе удаления для ключа #{key_id}: {e}")
            await callback.message.answer(
                f"Вы уверены, что хотите удалить ключ #{key_id}?\nEmail: {email}\nСервер: {host}",
                reply_markup=keyboards.create_admin_delete_key_confirm_keyboard(key_id)
            )


    class AdminExtendSingleKey(StatesGroup):
        waiting_days = State()

    @admin_router.callback_query(F.data.startswith("admin_key_extend_"))
    async def admin_key_extend_prompt(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат key_id")
            return
        await state.update_data(extend_key_id=key_id)
        await state.set_state(AdminExtendSingleKey.waiting_days)
        await callback.message.edit_text(
            f"Укажите, на сколько дней изменить срок ключа #{key_id}\n"
            "Положительное — продление, отрицательное — уменьшение срока:",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminExtendSingleKey.waiting_days)
    async def admin_key_extend_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        key_id = int(data.get("extend_key_id", 0))
        if not key_id:
            await state.clear()
            await message.answer("❌ Не удалось определить ключ.")
            return
        try:
            days = int((message.text or '').strip())
        except Exception:
            await message.answer("❌ Введите целое число дней (можно отрицательное)")
            return
        if days == 0:
            await message.answer("❌ Введите ненулевое значение")
            return
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            await message.answer("❌ Ключ не найден")
            await state.clear()
            return
        host = key.get('host_name')
        email = key.get('key_email')
        if not host or not email:
            await message.answer("❌ У ключа отсутствует сервер или email")
            await state.clear()
            return

        try:
            resp = await create_or_update_key_on_host(host, email, days_to_add=days)
        except Exception as e:
            logger.error(f"Продление ключа админом: не удалось обновить хост для ключа #{key_id}: {e}")
            resp = None
        if not resp or not resp.get('client_uuid') or not resp.get('expiry_timestamp_ms'):
            await message.answer("❌ Не удалось продлить ключ на сервере")
            return

        if not rw_repo.update_key(
            key_id,
            remnawave_user_uuid=resp['client_uuid'],
            expire_at_ms=int(resp['expiry_timestamp_ms']),
        ):
            await message.answer("❌ Не удалось обновить информацию о ключе.")
            return
        await state.clear()

        new_key = rw_repo.get_key_by_id(key_id)
        conn_str = new_key.get('subscription_url') or new_key.get('connection_string') or '—'
        text = (
            f"🔑 <b>Ключ #{key_id}</b>\n"
            f"Хост: {new_key.get('host_name') or '—'}\n"
            f"Email: {new_key.get('key_email') or '—'}\n"
            f"Истекает: {new_key.get('expiry_date') or '—'}\n\n"
            f"<code>{html_escape.escape(conn_str)}</code>\n\n"
        )
        await message.answer(f"✅ Ключ продлён на {days} дн.")
        await message.answer(text, reply_markup=keyboards.create_admin_key_actions_keyboard(key_id, int(new_key.get('user_id')) if new_key and new_key.get('user_id') else None))


def register_keys_2(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    @admin_router.callback_query(F.data.startswith("admin_key_delete_cancel_"))
    async def admin_key_delete_cancel(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            await callback.answer("Отменено")
        except Exception:
            pass
        logger.info(f"Получена отмена удаления ключа: data='{callback.data}' от {callback.from_user.id}")
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            return
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            return
        conn_str = key.get('subscription_url') or key.get('connection_string') or '—'
        text = (
            f"🔑 <b>Ключ #{key_id}</b>\n"
            f"Хост: {key.get('host_name') or '—'}\n"
            f"Email: {key.get('key_email') or '—'}\n"
            f"Истекает: {key.get('expiry_date') or '—'}\n\n"
            f"<code>{html_escape.escape(conn_str)}</code>\n\n"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_admin_key_actions_keyboard(key_id, int(key.get('user_id')) if key and key.get('user_id') else None)
            )
        except Exception as e:
            logger.debug(f"edit_text не удался в отмене удаления для ключа #{key_id}: {e}")
            await callback.message.answer(
                text,
                reply_markup=keyboards.create_admin_key_actions_keyboard(key_id, int(key.get('user_id')) if key and key.get('user_id') else None)
            )


    @admin_router.callback_query(F.data.startswith("admin_key_delete_confirm_"))
    async def admin_key_delete_confirm(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            await callback.answer("Удаляю…")
        except Exception:
            pass
        logger.info(f"Получено подтверждение удаления ключа: data='{callback.data}' от {callback.from_user.id}")
        try:
            key_id = int(callback.data.split('_')[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат key_id")
            return
        try:
            key = rw_repo.get_key_by_id(key_id)
        except Exception as e:
            logger.error(f"БД get_key_by_id не удался для #{key_id}: {e}")
            key = None
        if not key:
            await callback.message.answer("❌ Ключ не найден")
            return
        try:
            user_id = int(key.get('user_id'))
        except Exception as e:
            logger.error(f"Неверный user_id для ключа #{key_id}: {key.get('user_id')}, err={e}")
            await callback.message.answer("❌ Ошибка данных ключа: некорректный пользователь")
            return
        host = key.get('host_name')
        email = key.get('key_email')
        ok_host = True
        if host and email:
            try:
                ok_host = await delete_client_on_host(host, email)
            except Exception as e:
                ok_host = False
                logger.error(f"Не удалось удалить клиента на хосте '{host}' для ключа #{key_id}: {e}")
        ok_db = False
        try:
            ok_db = delete_key_by_email(email)
        except Exception as e:
            logger.error(f"Не удалось удалить ключ в БД для email '{email}': {e}")
        if ok_db:
            await callback.message.answer("✅ Ключ удалён" + (" (с хоста тоже)" if ok_host else " (но удалить на хосте не удалось)"))

            keys = get_keys_for_user(user_id)
            try:
                await callback.message.edit_text(
                    f"🔑 Ключи пользователя {user_id}:",
                    reply_markup=keyboards.create_admin_user_keys_keyboard(user_id, keys)
                )
            except Exception as e:
                logger.debug(f"edit_text не удался в обновлении списка подтверждения удаления для пользователя {user_id}: {e}")
                await callback.message.answer(
                    f"🔑 Ключи пользователя {user_id}:",
                    reply_markup=keyboards.create_admin_user_keys_keyboard(user_id, keys)
                )

            try:
                await callback.bot.send_message(
                    user_id,
                    "ℹ️ Администратор удалил один из ваших ключей. Если это ошибка — напишите в поддержку.",
                    reply_markup=keyboards.create_support_keyboard()
                )
            except Exception:
                pass
        else:
            await callback.message.answer("❌ Не удалось удалить ключ из базы данных")

    class AdminEditKeyEmail(StatesGroup):
        waiting_for_email = State()

    @admin_router.callback_query(F.data.startswith("admin_key_edit_email_"))
    async def admin_key_edit_email_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат key_id")
            return
        await state.update_data(edit_key_id=key_id)
        await state.set_state(AdminEditKeyEmail.waiting_for_email)
        await callback.message.edit_text(
            f"Введите новый email для ключа #{key_id}",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminEditKeyEmail.waiting_for_email)
    async def admin_key_edit_email_commit(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        key_id = int(data.get('edit_key_id'))
        new_email = (message.text or '').strip()
        if not new_email:
            await message.answer("❌ Введите корректный email")
            return
        ok = update_key_email(key_id, new_email)
        if ok:
            await message.answer("✅ Email обновлён")
        else:
            await message.answer("❌ Не удалось обновить email (возможно, уже занят)")
        await state.clear()


def register_keys_3(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    @admin_router.callback_query(F.data.startswith("admin_key_back_"))
    async def admin_key_back(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            key_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат key_id")
            return
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            await callback.message.answer("❌ Ключ не найден")
            return

        host_from_state = None
        try:
            data = await state.get_data()
            host_from_state = (data or {}).get('hostkeys_host')
        except Exception:
            host_from_state = None

        if host_from_state:
            host_name = host_from_state
            keys = get_keys_for_host(host_name)
            await callback.message.edit_text(
                f"🔑 Ключи на хосте {host_name}:",
                reply_markup=keyboards.create_admin_keys_for_host_keyboard(host_name, keys)
            )
        else:
            user_id = int(key.get('user_id'))
            keys = get_keys_for_user(user_id)
            await callback.message.edit_text(
                f"🔑 Ключи пользователя {user_id}:",
                reply_markup=keyboards.create_admin_user_keys_keyboard(user_id, keys)
            )
