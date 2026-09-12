"""Франшиза: включение, процент партнёра, минимум вывода.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import is_admin

from shop_bot.webhook_server.app import franchise_settings, toggle_franchise_settings


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_franchise(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


    # === Franchise settings management ===

    class AdminFranchise(StatesGroup):
        menu = State()
        waiting_for_percent = State()
        waiting_for_min_withdraw = State()

    
    def _get_franchise_settings_for_admin() -> dict:
        """Получает текущие настройки франшизы (только для админа)"""
        from shop_bot.data_manager.database import get_franchise_percent_default, get_franchise_min_withdraw
        return {
            "enabled": franchise_settings(),
            "commission_percent": get_franchise_percent_default(),
            "min_withdraw": get_franchise_min_withdraw(),
        }

    
    async def show_admin_franchise_menu(message: types.Message, edit_message: bool = False):
        """Отображает меню настроек франшизы (только для админа)"""
        settings = _get_franchise_settings_for_admin()
        status = "🟢 включена" if settings["enabled"] else "🔴 выключена"

        text_out = (
            "🏢 <b>Франшиза (клонирование ботов)</b>\n\n"
            f"Статус: <b>{status}</b>\n"
            f"Комиссия: <b>{settings['commission_percent']:.1f}%</b>\n"
            f"Минимум вывода: <b>{settings['min_withdraw']:.0f} ₽</b>\n\n"
            "Когда франшиза включена, пользователи могут создавать свои клоны бота через кнопку «🤖 Создать бота»."
        )

        kb = keyboards.create_admin_franchise_settings_keyboard(enabled=settings["enabled"])

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")

    
    @admin_router.callback_query(F.data == "admin_franchise")
    async def admin_franchise_menu_entry(callback: types.CallbackQuery, state: FSMContext):
        """Точка входа в меню франшизы - ТОЛЬКО ДЛЯ АДМИНА"""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        await state.set_state(AdminFranchise.menu)
        await show_admin_franchise_menu(callback.message, edit_message=True)

    
    @admin_router.callback_query(F.data == "admin_franchise_toggle")
    async def admin_franchise_toggle(callback: types.CallbackQuery, state: FSMContext):
        """Переключает франшизу ВКЛ/ВЫКЛ - ТОЛЬКО ДЛЯ АДМИНА"""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        # Переключаем и получаем новое состояние (БД + запуск/остановка клонов)
        is_enabled = toggle_franchise_settings()

        try:
            from shop_bot.factory_bot.runtime import get_service
            svc = get_service()
            if svc:
                if is_enabled:
                    await svc.start_all()
                else:
                    await svc.stop_all()
        except Exception as _e:
            logger.warning(f"Не удалось применить клоны ботов при переключении франшизы: {_e}")

        status_text = "включена ✅" if is_enabled else "выключена ❌"
        await callback.answer(f"Франшиза {status_text}")
        
        await state.set_state(AdminFranchise.menu)
        await show_admin_franchise_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_franchise_set_percent")
    async def admin_franchise_set_percent(callback: types.CallbackQuery, state: FSMContext):
        """Установить процент комиссии франшизы"""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        await callback.message.answer("💰 Укажите процент комиссии для франшизников (0-100, например 35):")
        await state.set_state(AdminFranchise.waiting_for_percent)

    @admin_router.message(AdminFranchise.waiting_for_percent)
    async def admin_franchise_percent_input(message: types.Message, state: FSMContext):
        """Обработка ввода процента комиссии"""
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав.")
            return

        try:
            percent = float(message.text.strip())
            if percent < 0 or percent > 100:
                await message.answer("❌ Процент должен быть от 0 до 100.")
                return
            
            rw_repo.update_setting("franchise_commission_percent", f"{percent:.1f}")
            await message.answer(f"✅ Процент комиссии установлен на <b>{percent:.1f}%</b>", parse_mode="HTML")
            
            await state.set_state(AdminFranchise.menu)
            await show_admin_franchise_menu(message, edit_message=False)
        except ValueError:
            await message.answer("❌ Некорректное значение. Используйте число (например 35 или 35.5)")

    @admin_router.callback_query(F.data == "admin_franchise_set_min_withdraw")
    async def admin_franchise_set_min_withdraw(callback: types.CallbackQuery, state: FSMContext):
        """Установить минимум для вывода франшизников"""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        await callback.message.answer("💳 Укажите минимум для вывода денег франшизниками в рублях (например 1500):")
        await state.set_state(AdminFranchise.waiting_for_min_withdraw)

    @admin_router.message(AdminFranchise.waiting_for_min_withdraw)
    async def admin_franchise_min_withdraw_input(message: types.Message, state: FSMContext):
        """Обработка ввода минимума для вывода"""
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав.")
            return

        try:
            amount = float(message.text.strip())
            if amount < 1:
                await message.answer("❌ Минимум должен быть больше 0.")
                return
            
            rw_repo.update_setting("franchise_min_withdraw_rub", f"{amount:.0f}")
            await message.answer(f"✅ Минимум для вывода установлен на <b>{amount:.0f} ₽</b>", parse_mode="HTML")
            
            await state.set_state(AdminFranchise.menu)
            await show_admin_franchise_menu(message, edit_message=False)
        except ValueError:
            await message.answer("❌ Некорректное значение. Используйте число (например 1500)")
