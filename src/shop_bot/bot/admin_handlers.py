import logging
import asyncio
import time
import uuid
import re
import html as html_escape
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Router, F, types, BaseMiddleware
from aiogram.filters import Command, StateFilter, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot import keyboards
from shop_bot.bot.callback_safety import fast_callback_answer, catch_callback_errors
from shop_bot.modules import telegram_reachability
from shop_bot.data_manager import speedtest_runner
from shop_bot.data_manager import resource_monitor
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager import database
from shop_bot.data_manager.remnawave_repository import (
    get_all_users,
    get_setting,
    get_user,
    get_keys_for_user,
    create_gift_key,
    get_all_hosts,
    get_all_ssh_targets,
    add_to_balance,
    deduct_from_balance,
    ban_user,
    unban_user,
    delete_key_by_email,
    get_admin_stats,
    get_keys_for_host,
    is_admin,
    get_referral_count,
    get_referral_balance_all,
    get_referrals_for_user,
    create_promo_code,
    list_promo_codes,
    update_promo_code_status,
    # hosts
    create_host,
    delete_host,
    get_host,
    update_host_url,
    update_host_name,
    update_host_subscription_url,
    update_host_remnawave_settings,
    update_host_ssh_settings,
    get_host_squads,
    add_host_squad,
    set_host_squad_active,
    delete_host_squad,
)
from shop_bot.data_manager.database import (
    update_key_email,
    set_balance,
    set_referral_balance,
    set_referral_balance_all,
    delete_user_completely,
    create_plan,
    get_plans_for_host,
    get_plan_by_id,
    update_plan,
    update_plan_metadata,
    delete_plan,
    set_plan_active,

    # traffic packages (докупка ГБ)
    create_traffic_package,
    get_traffic_packages_for_plan,
    get_traffic_package_by_id,
    update_traffic_package,
    delete_traffic_package,

    # Button constructor (dynamic keyboards)
    get_button_configs_admin,
    get_button_config_by_db_id,
    create_button_config,
    update_button_config,
    delete_button_config,
)
from shop_bot.data_manager import backup_manager
from shop_bot.bot.handlers import show_main_menu
from shop_bot.webhook_server.app import franchise_settings, toggle_franchise_settings
from shop_bot.modules.remnawave_api import create_or_update_key_on_host, delete_client_on_host
from shop_bot.core.module_loader import get_global_module_loader

logger = logging.getLogger(__name__)


def _is_true(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "on", "yes", "y")


def _mask_secret(value: str | None) -> str:
    v = (value or "").strip()
    if not v:
        return "—"
    if len(v) <= 6:
        return "•" * len(v)
    return f"{v[:2]}•••{v[-2:]}"

class AdminSettings(StatesGroup):
    waiting_for_captcha_attempts = State()
    waiting_for_captcha_timeout = State()
    waiting_for_captcha_message = State()

class AdminModules(StatesGroup):
    browsing = State()

class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_parse_mode = State()
    waiting_for_button_option = State()
    waiting_for_button_type = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_action_select = State()
    waiting_for_confirmation = State()


class IsAdminFilter(BaseFilter):
    """Router-level gate for admin_router (aiogram 3.x BaseFilter).

    Only telegram_ids from admin_telegram_id / admin_telegram_ids pass.
    """

    async def __call__(
        self,
        event: types.TelegramObject,
        event_from_user: types.User | None = None,
    ) -> bool:
        user = event_from_user or getattr(event, "from_user", None)
        if user is None:
            return False
        try:
            return bool(is_admin(user.id))
        except Exception:
            return False


class AdminAccessMiddleware(BaseMiddleware):
    """When a non-admin hits admin_router, answer the callback the same way
    existing handlers do (`У вас нет прав.`) instead of leaving Telegram spinning.
    Messages are ignored silently (same as a failed router filter).
    """

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user") or getattr(event, "from_user", None)
        uid = getattr(user, "id", None)
        try:
            allowed = bool(uid is not None and is_admin(uid))
        except Exception:
            allowed = False
        if not allowed:
            if isinstance(event, types.CallbackQuery):
                try:
                    await event.answer("У вас нет прав.", show_alert=True)
                except Exception:
                    pass
            return None
        return await handler(event, data)


def get_admin_router() -> Router:
    admin_router = Router(name="admin_router")
    admin_router.message.filter(IsAdminFilter())
    admin_router.callback_query.filter(IsAdminFilter())
    admin_router.message.outer_middleware(AdminAccessMiddleware())
    admin_router.callback_query.outer_middleware(AdminAccessMiddleware())


    def _format_user_mention(u: types.User) -> str:
        try:
            if u.username:
                uname = u.username.lstrip('@')
                return f"@{uname}"

            full_name = (u.full_name or u.first_name or "Администратор").strip()

            try:
                safe_name = html_escape.escape(full_name)
            except Exception:
                safe_name = full_name
            return f"<a href='tg://user?id={u.id}'>{safe_name}</a>"
        except Exception:
            return str(getattr(u, 'id', '—'))


    def _resolve_target_from_hash(cb_data: str) -> str | None:
        try:
            digest = cb_data.split(':', 1)[1]
        except Exception:
            return None
        try:
            targets = get_all_ssh_targets() or []
        except Exception:
            targets = []
        for t in targets:
            name = t.get('target_name')
            try:
                h = hashlib.sha1((name or '').encode('utf-8', 'ignore')).hexdigest()
            except Exception:
                h = hashlib.sha1(str(name).encode('utf-8', 'ignore')).hexdigest()
            if h == digest:
                return name
        return None

    async def show_admin_menu(message: types.Message, edit_message: bool = False):

        stats = get_admin_stats() or {}
        today_new = stats.get('today_new_users', 0)
        today_income = float(stats.get('today_income', 0) or 0)
        today_keys = stats.get('today_issued_keys', 0)
        total_users = stats.get('total_users', 0)
        total_income = float(stats.get('total_income', 0) or 0)
        total_keys = stats.get('total_keys', 0)
        active_keys = stats.get('active_keys', 0)

        text = (
            "📊 <b>Панель Администратора</b>\n\n"
            "<b>За сегодня:</b>\n"
            f"👥 Новых пользователей: {today_new}\n"
            f"💰 Доход: {today_income:.2f} RUB\n"
            f"🔑 Выдано ключей: {today_keys}\n\n"
            "<b>За все время:</b>\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"💰 Общий доход: {total_income:.2f} RUB\n"
            f"🔑 Всего ключей: {total_keys}\n\n"
            "<b>Состояние ключей:</b>\n"
            f"✅ Активных: {active_keys}"
        )

        try:
            keyboard = keyboards.create_dynamic_admin_menu_keyboard()
        except Exception as e:
            logger.warning(f"Не удалось создать динамическую админ-клавиатуру, используем статическую: {e}")
            keyboard = keyboards.create_admin_menu_keyboard()
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except Exception:
                pass
        else:
            await message.answer(text, reply_markup=keyboard)

    async def show_admin_promo_menu(message: types.Message, edit_message: bool = False):
        text = (
            "🎟 <b>Управление промокодами</b>\n\n"
            "Здесь можно создавать новые промокоды, просматривать список и отключать их."
        )
        keyboard = keyboards.create_admin_promo_menu_keyboard()
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except Exception:
                await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)

    def _parse_datetime_input(raw: str) -> datetime | None:
        value = (raw or "").strip()
        if not value or value.lower() in {"skip", "нет", "не", "none"}:
            return None
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                continue
        raise ValueError("Неверный формат даты. Используйте 'ГГГГ-ММ-ДД' или 'ГГГГ-ММ-ДД ЧЧ:ММ'.")

    def _format_promo_line(promo: dict) -> str:
        code = promo.get("code") or "—"
        discount_percent = promo.get("discount_percent")
        discount_amount = promo.get("discount_amount")
        try:
            if discount_percent:
                discount_text = f"{float(discount_percent):.2f}%"
            else:
                discount_text = f"{float(discount_amount or 0):.2f} RUB"
        except Exception:
            discount_text = str(discount_percent or discount_amount or "—")

        status_parts: list[str] = []
        is_active = bool(promo.get("is_active"))
        status_parts.append("🟢 активен" if is_active else "🔴 отключён")

        try:
            usage_limit_total = int(promo.get("usage_limit_total") or 0)
        except Exception:
            usage_limit_total = 0
        used_total = int(promo.get("used_total") or 0)
        if usage_limit_total:
            status_parts.append(f"{used_total}/{usage_limit_total}")
            if used_total >= usage_limit_total:
                status_parts.append("лимит исчерпан")

        try:
            usage_limit_per_user = int(promo.get("usage_limit_per_user") or 0)
        except Exception:
            usage_limit_per_user = 0
        if usage_limit_per_user:
            status_parts.append(f"пользователь ≤ {usage_limit_per_user}")

        valid_until = promo.get("valid_until")
        if valid_until:
            status_parts.append(f"до {str(valid_until)[:16]}")

        plan_ids = promo.get("applicable_plan_ids")
        if plan_ids:
            status_parts.append(f"тарифы {plan_ids}")
        segment_type = (promo.get("segment_type") or "").strip()
        if segment_type == "no_active_subscription":
            status_parts.append("нет активной подписки")
        elif segment_type == "min_total_spent":
            try:
                status_parts.append(f"сумма ≥ {float(promo.get('segment_value') or 0):.0f} ₽")
            except Exception:
                status_parts.append("мин. сумма покупок")

        status_text = ", ".join(status_parts)
        return f"• <code>{code}</code> — скидка: {discount_text} | статус: {status_text}"

    def _build_promo_list_keyboard(codes: list[dict], page: int = 0, page_size: int = 10) -> types.InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        total = len(codes)
        start = page * page_size
        end = start + page_size
        page_items = codes[start:end]
        if not page_items:
            builder.button(text="Промокодов нет", callback_data="noop")
        for promo in page_items:
            code = promo.get("code") or "—"
            is_active = bool(promo.get("is_active"))
            label = f"{'🟢' if is_active else '🔴'} {code}"
            builder.button(text=label, callback_data=f"admin_promo_toggle_{code}")
        have_prev = start > 0
        have_next = end < total
        if have_prev:
            builder.button(text="⬅️ Назад", callback_data=f"admin_promo_page_{page-1}")
        if have_next:
            builder.button(text="Вперёд ➡️", callback_data=f"admin_promo_page_{page+1}")
        builder.button(text="⬅️ В меню", callback_data="admin_promo_menu")
        rows = [1] * len(page_items)
        tail: list[int] = []
        if have_prev or have_next:
            tail.append(2 if (have_prev and have_next) else 1)
        tail.append(1)
        builder.adjust(*(rows + tail if rows else tail))
        return builder.as_markup()

    async def show_admin_system_menu(message: types.Message, edit_message: bool = False):
        text = "🖥 <b>Система</b>\n\nВыберите действие:"
        try:
            keyboard = keyboards.create_dynamic_admin_system_menu_keyboard()
        except Exception as e:
            logger.warning(f"Не удалось создать динамическую клавиатуру 'Система', используем статическую: {e}")
            keyboard = keyboards.create_admin_system_menu_keyboard()
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except Exception:
                pass
        else:
            await message.answer(text, reply_markup=keyboard)


    async def show_admin_settings_menu(message: types.Message, edit_message: bool = False):
        text = "⚙️ <b>Настройки</b>\n\nВыберите раздел:"
        try:
            keyboard = keyboards.create_dynamic_admin_settings_menu_keyboard()
        except Exception as e:
            logger.warning(f"Не удалось создать динамическую клавиатуру 'Настройки', используем статическую: {e}")
            keyboard = keyboards.create_admin_settings_menu_keyboard()
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except Exception:
                pass
        else:
            await message.answer(text, reply_markup=keyboard)


    def _build_modules_keyboard(modules: list[dict]) -> types.InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        for mod in modules:
            module_id = mod.get("id") or ""
            name = mod.get("name") or module_id
            status = mod.get("status") or "disabled"
            if status == "enabled":
                builder.button(text=f"❌ {name}", callback_data=f"admin_module_disable:{module_id}")
            else:
                builder.button(text=f"✅ {name}", callback_data=f"admin_module_enable:{module_id}")
        builder.button(text="🔄 Обновить", callback_data="admin_modules_refresh")
        builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
        if modules:
            builder.adjust(*([1] * len(modules)), 1, 1)
        else:
            builder.adjust(1, 1)
        return builder.as_markup()

    async def show_admin_modules_menu(message: types.Message, edit_message: bool = False):
        module_loader = get_global_module_loader()
        modules = module_loader.list_modules()
        if not modules:
            text = "🧩 <b>Модули</b>\n\nМодули не найдены."
        else:
            lines = ["🧩 <b>Модули</b>", ""]
            for mod in modules:
                status = mod.get("status") or "disabled"
                if status == "enabled":
                    status_icon = "🟢"
                    status_label = "включен"
                elif status == "error":
                    status_icon = "🔴"
                    status_label = "ошибка"
                else:
                    status_icon = "🟡"
                    status_label = "отключен"
                name = html_escape.escape(mod.get("name") or mod.get("id") or "—")
                module_id = html_escape.escape(mod.get("id") or "")
                line = f"{status_icon} <b>{name}</b> <code>{module_id}</code> — {status_label}"
                error_message = (mod.get("error_message") or "").strip()
                if error_message:
                    error_safe = html_escape.escape(error_message)
                    line += f"\n   ⚠️ {error_safe}"
                lines.append(line)
            text = "\n".join(lines)

        keyboard = _build_modules_keyboard(modules)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except Exception:
                await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)


    @admin_router.callback_query(F.data == "admin_menu")
    async def open_admin_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_menu(callback.message, edit_message=True)
    @admin_router.callback_query(F.data == "admin_system_menu")
    async def open_admin_system_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_system_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_settings_menu")
    async def open_admin_settings_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_settings_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_modules")
    async def open_admin_modules_menu_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminModules.browsing)
        await show_admin_modules_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_modules_refresh")
    async def refresh_admin_modules_menu_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_modules_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data.startswith("admin_module_enable:"))
    async def admin_module_enable_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        module_id = callback.data.split(":", 1)[1]
        module_loader = get_global_module_loader()
        ok, message = module_loader.enable_module(module_id)
        await callback.answer(message, show_alert=not ok)
        await show_admin_modules_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data.startswith("admin_module_disable:"))
    async def admin_module_disable_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        module_id = callback.data.split(":", 1)[1]
        module_loader = get_global_module_loader()
        ok, message = module_loader.disable_module(module_id)
        await callback.answer(message, show_alert=not ok)
        await show_admin_modules_menu(callback.message, edit_message=True)



    # === Button constructor (manage dynamic keyboards from bot admin) ===

    class ButtonConstructor(StatesGroup):
        adding_button_id = State()
        adding_text = State()
        adding_action_value = State()
        adding_row = State()
        adding_col = State()
        adding_width = State()
        adding_sort = State()
        adding_active = State()
        editing_value = State()

    _BTN_MENUS: list[tuple[str, str]] = [
        ("main_menu", "🏠 Главное меню"),
        ("profile_menu", "👤 Меню профиля"),
        ("support_menu", "🆘 Меню поддержки"),
        ("admin_menu", "🛠 Админ-меню"),
        ("admin_system_menu", "🖥 Админ: Система"),
        ("admin_settings_menu", "⚙️ Админ: Настройки"),
    ]

    def _btnc_menu_label(menu_type: str) -> str:
        for k, v in _BTN_MENUS:
            if k == menu_type:
                return v
        return menu_type

    def _btnc_cancel_kb(back_cb: str = "admin_settings_menu") -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="❌ Отмена", callback_data="btnc_cancel")
        b.button(text="⬅️ Назад", callback_data=back_cb)
        b.adjust(1, 1)
        return b.as_markup()

    async def _btnc_show_menu_types(message: types.Message, *, edit: bool = True) -> None:
        text = (
            "🧩 <b>Конструктор кнопок</b>\n\n"
            "Выберите, для какого меню вы хотите управлять кнопками:" 
        )
        builder = InlineKeyboardBuilder()
        for menu_type, title in _BTN_MENUS:
            builder.button(text=title, callback_data=f"btnc_mt:{menu_type}")
        builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
        builder.adjust(2, 2, 2, 1)
        kb = builder.as_markup()
        if edit:
            try:
                await message.edit_text(text, reply_markup=kb)
            except Exception:
                await message.answer(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)

    def _btnc_build_list_kb(menu_type: str, configs: list[dict], page: int, page_size: int = 10) -> types.InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        total = len(configs)
        start = page * page_size
        end = start + page_size
        page_items = configs[start:end]

        if not page_items:
            builder.button(text="(пусто)", callback_data="noop")
        else:
            for cfg in page_items:
                try:
                    db_id = int(cfg.get("id"))
                except Exception:
                    continue
                is_active = bool(cfg.get("is_active"))
                icon = "🟢" if is_active else "🔴"
                txt = (cfg.get("text") or "").strip() or (cfg.get("button_id") or "—")
                if len(txt) > 28:
                    txt = txt[:28] + "…"
                row = cfg.get("row_position")
                col = cfg.get("column_position")
                builder.button(text=f"{icon} {txt}  ({row},{col})", callback_data=f"btnc_edit:{menu_type}:{db_id}")

        have_prev = start > 0
        have_next = end < total
        if have_prev:
            builder.button(text="⬅️", callback_data=f"btnc_list:{menu_type}:{page-1}")
        if have_next:
            builder.button(text="➡️", callback_data=f"btnc_list:{menu_type}:{page+1}")

        builder.button(text="➕ Добавить", callback_data=f"btnc_add:{menu_type}")
        builder.button(text="📋 Другое меню", callback_data="admin_btn_constructor")
        builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")

        rows: list[int] = [1] * len(page_items)
        tail: list[int] = []
        if have_prev or have_next:
            tail.append(2 if (have_prev and have_next) else 1)
        tail.extend([2, 1])
        builder.adjust(*(rows + tail if rows else tail))
        return builder.as_markup()

    async def _btnc_show_list(message: types.Message, menu_type: str, *, page: int = 0, edit: bool = True) -> None:
        configs = get_button_configs_admin(menu_type, include_inactive=True) or []
        text = (
            "🧩 <b>Конструктор кнопок</b>\n\n"
            f"Меню: <b>{html_escape.escape(_btnc_menu_label(menu_type))}</b>\n"
            f"Всего кнопок: <b>{len(configs)}</b>\n\n"
            "Выберите кнопку для редактирования или нажмите «Добавить»."
        )
        kb = _btnc_build_list_kb(menu_type, configs, page)
        if edit:
            try:
                await message.edit_text(text, reply_markup=kb)
            except Exception:
                await message.answer(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)

    def _btnc_build_details_kb(menu_type: str, db_id: int, is_active: bool) -> types.InlineKeyboardMarkup:
        b = InlineKeyboardBuilder()
        b.button(text="✏️ Текст", callback_data=f"btnc_setfield:text:{menu_type}:{db_id}")
        b.button(text="🔗 Действие", callback_data=f"btnc_action_menu:{menu_type}:{db_id}")
        b.button(text="📍 Позиция", callback_data=f"btnc_setfield:rowcol:{menu_type}:{db_id}")
        b.button(text="↔️ Ширина", callback_data=f"btnc_setfield:width:{menu_type}:{db_id}")
        b.button(text="🔢 Сортировка", callback_data=f"btnc_setfield:sort:{menu_type}:{db_id}")
        b.button(text=("🚫 Выключить" if is_active else "✅ Включить"), callback_data=f"btnc_toggle:{menu_type}:{db_id}")
        b.button(text="🗑 Удалить", callback_data=f"btnc_del:{menu_type}:{db_id}")
        b.button(text="⬅️ К списку", callback_data=f"btnc_list:{menu_type}:0")
        b.button(text="⚙️ Настройки", callback_data="admin_settings_menu")
        b.adjust(2, 2, 2, 1, 1, 1)
        return b.as_markup()

    async def _btnc_show_details(message: types.Message, menu_type: str, db_id: int, *, edit: bool = True) -> None:
        cfg = get_button_config_by_db_id(db_id)
        if not cfg or str(cfg.get("menu_type")) != str(menu_type):
            await message.answer("Кнопка не найдена или была удалена.")
            await _btnc_show_list(message, menu_type, page=0, edit=False)
            return

        btn_id = cfg.get("button_id")
        text_val = cfg.get("text") or ""
        callback_data = cfg.get("callback_data")
        url_val = cfg.get("url")
        row = cfg.get("row_position")
        col = cfg.get("column_position")
        width = cfg.get("button_width")
        sort = cfg.get("sort_order")
        is_active = bool(cfg.get("is_active"))

        action_type = "URL" if url_val else "Callback"
        action_value = url_val or callback_data or "—"

        text = (
            "🧩 <b>Конструктор кнопок</b>\n\n"
            f"Меню: <b>{html_escape.escape(_btnc_menu_label(menu_type))}</b>\n"
            f"ID (в БД): <code>{db_id}</code>\n"
            f"button_id: <code>{html_escape.escape(str(btn_id or '—'))}</code>\n\n"
            f"Текст: <b>{html_escape.escape(str(text_val))}</b>\n"
            f"Действие: <b>{action_type}</b>\n"
            f"Значение: <code>{html_escape.escape(str(action_value))}</code>\n\n"
            f"Позиция: row=<code>{row}</code>, col=<code>{col}</code>, width=<code>{width}</code>\n"
            f"sort_order: <code>{sort}</code>\n"
            f"Статус: <b>{'🟢 активна' if is_active else '🔴 выключена'}</b>\n\n"
            "Выберите, что хотите изменить."
        )
        kb = _btnc_build_details_kb(menu_type, db_id, is_active)
        if edit:
            try:
                await message.edit_text(text, reply_markup=kb)
            except Exception:
                await message.answer(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)


    @admin_router.callback_query(F.data == "admin_btn_constructor")
    @catch_callback_errors
    @fast_callback_answer
    async def admin_button_constructor_root(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.clear()
        await _btnc_show_menu_types(callback.message, edit=True)

    @admin_router.callback_query(F.data.startswith("btnc_mt:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_select_menu_type(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        menu_type = (callback.data or "").split(":", 1)[1]
        await _btnc_show_list(callback.message, menu_type, page=0, edit=True)

    @admin_router.callback_query(F.data.startswith("btnc_list:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_open_list(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        menu_type = parts[1] if len(parts) > 1 else "main_menu"
        try:
            page = int(parts[2]) if len(parts) > 2 else 0
        except Exception:
            page = 0
        await _btnc_show_list(callback.message, menu_type, page=page, edit=True)

    @admin_router.callback_query(F.data.startswith("btnc_edit:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_open_details(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) < 3:
            return
        menu_type = parts[1]
        try:
            db_id = int(parts[2])
        except Exception:
            return
        await _btnc_show_details(callback.message, menu_type, db_id, edit=True)

    @admin_router.callback_query(F.data.startswith("btnc_toggle:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_toggle_active(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) < 3:
            return
        menu_type = parts[1]
        try:
            db_id = int(parts[2])
        except Exception:
            return
        cfg = get_button_config_by_db_id(db_id) or {}
        current = bool(cfg.get("is_active"))
        update_button_config(db_id, is_active=(not current))
        await _btnc_show_details(callback.message, menu_type, db_id, edit=True)

    @admin_router.callback_query(F.data.startswith("btnc_del:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_delete_confirm(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) < 3:
            return
        menu_type = parts[1]
        try:
            db_id = int(parts[2])
        except Exception:
            return
        b = InlineKeyboardBuilder()
        b.button(text="🗑 Да, удалить", callback_data=f"btnc_del_ok:{menu_type}:{db_id}")
        b.button(text="⬅️ Отмена", callback_data=f"btnc_edit:{menu_type}:{db_id}")
        b.adjust(1, 1)
        await callback.message.edit_text(
            "⚠️ <b>Удалить кнопку?</b>\n\nЭто действие нельзя отменить.",
            reply_markup=b.as_markup(),
        )

    @admin_router.callback_query(F.data.startswith("btnc_del_ok:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_delete_do(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) < 3:
            return
        menu_type = parts[1]
        try:
            db_id = int(parts[2])
        except Exception:
            return
        delete_button_config(db_id)
        await _btnc_show_list(callback.message, menu_type, page=0, edit=True)

    @admin_router.callback_query(F.data == "btnc_cancel")
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_cancel_any(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await show_admin_settings_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data.startswith("btnc_action_menu:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_action_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) < 3:
            return
        menu_type = parts[1]
        try:
            db_id = int(parts[2])
        except Exception:
            return
        b = InlineKeyboardBuilder()
        b.button(text="⚙️ Callback", callback_data=f"btnc_setfield:callback:{menu_type}:{db_id}")
        b.button(text="🔗 URL", callback_data=f"btnc_setfield:url:{menu_type}:{db_id}")
        b.button(text="⬅️ Назад", callback_data=f"btnc_edit:{menu_type}:{db_id}")
        b.adjust(2, 1)
        await callback.message.edit_text(
            "🔗 <b>Тип действия</b>\n\nВыберите, что хотите задать для кнопки:",
            reply_markup=b.as_markup(),
        )

    @admin_router.callback_query(F.data.startswith("btnc_setfield:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_edit_field_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        if len(parts) < 4:
            return
        field = parts[1]
        menu_type = parts[2]
        try:
            db_id = int(parts[3])
        except Exception:
            return

        await state.clear()
        await state.set_state(ButtonConstructor.editing_value)
        await state.update_data(btnc_field=field, btnc_menu_type=menu_type, btnc_db_id=db_id)

        prompts = {
            "text": "Отправьте новый <b>текст</b> для кнопки:",
            "callback": "Отправьте новое <b>callback_data</b> (внутреннее действие):",
            "url": "Отправьте новый <b>URL</b> (например https://example.com):",
            "rowcol": "Отправьте новую позицию в формате: <code>row col</code> (например <code>2 1</code>):",
            "width": "Отправьте ширину (1 или 2).",
            "sort": "Отправьте <b>sort_order</b> (целое число):",
        }
        prompt = prompts.get(field, "Отправьте новое значение:")
        await callback.message.edit_text(prompt, reply_markup=_btnc_cancel_kb(f"btnc_edit:{menu_type}:{db_id}"))

    @admin_router.message(StateFilter(ButtonConstructor.editing_value))
    async def btnc_edit_field_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        field = data.get("btnc_field")
        menu_type = data.get("btnc_menu_type")
        try:
            db_id = int(data.get("btnc_db_id"))
        except Exception:
            await state.clear()
            return

        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Пустое значение не принято.")
            return

        try:
            if field == "text":
                update_button_config(db_id, text=raw)
            elif field == "callback":
                # When setting callback action, clear URL
                update_button_config(db_id, callback_data=raw, url=None)
            elif field == "url":
                update_button_config(db_id, url=raw, callback_data=None)
            elif field == "rowcol":
                parts = re.split(r"\s+|,", raw)
                if len(parts) < 2:
                    raise ValueError("Нужно 2 числа: row и col")
                row = int(parts[0])
                col = int(parts[1])
                update_button_config(db_id, row_position=row, column_position=col)
            elif field == "width":
                w = int(raw)
                if w not in (1, 2, 3):
                    raise ValueError("Ширина должна быть 1, 2 или 3")
                update_button_config(db_id, button_width=w)
            elif field == "sort":
                s = int(raw)
                update_button_config(db_id, sort_order=s)
            else:
                update_button_config(db_id, metadata=raw)
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
            return

        await state.clear()
        await _btnc_show_details(message, menu_type, db_id, edit=False)


    # --- Add new button flow ---

    @admin_router.callback_query(F.data.startswith("btnc_add:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_add_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        menu_type = (callback.data or "").split(":", 1)[1]
        await state.clear()
        await state.update_data(btnc_menu_type=menu_type, btnc_new={})
        await state.set_state(ButtonConstructor.adding_button_id)
        await callback.message.edit_text(
            "➕ <b>Новая кнопка</b>\n\n"
            f"Меню: <b>{html_escape.escape(_btnc_menu_label(menu_type))}</b>\n\n"
            "Отправьте <b>button_id</b> (латиница/цифры/подчёркивание).\n"
            "Пример: <code>promo</code>",
            reply_markup=_btnc_cancel_kb(f"btnc_list:{menu_type}:0"),
        )

    @admin_router.message(StateFilter(ButtonConstructor.adding_button_id))
    async def btnc_add_button_id(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        raw = (message.text or "").strip()
        if not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", raw):
            await message.answer("Неверный button_id. Разрешено: a-z A-Z 0-9 _ - (до 64 символов).")
            return
        new = dict(data.get("btnc_new") or {})
        new["button_id"] = raw
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_text)
        await message.answer("Отправьте <b>текст кнопки</b>:", reply_markup=_btnc_cancel_kb(f"btnc_list:{menu_type}:0"))

    @admin_router.message(StateFilter(ButtonConstructor.adding_text))
    async def btnc_add_text(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Текст не должен быть пустым.")
            return
        new = dict(data.get("btnc_new") or {})
        new["text"] = raw
        await state.update_data(btnc_new=new)
        # Ask action type
        b = InlineKeyboardBuilder()
        b.button(text="⚙️ Callback", callback_data="btnc_add_action:callback")
        b.button(text="🔗 URL", callback_data="btnc_add_action:url")
        b.button(text="❌ Отмена", callback_data="btnc_cancel")
        b.adjust(2, 1)
        await message.answer("Выберите <b>тип действия</b>:", reply_markup=b.as_markup())

    @admin_router.callback_query(StateFilter(ButtonConstructor.adding_text), F.data.startswith("btnc_add_action:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_add_action_type(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        action_type = (callback.data or "").split(":", 1)[1]
        new = dict(data.get("btnc_new") or {})
        new["action_type"] = action_type
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_action_value)
        if action_type == "url":
            prompt = "Отправьте <b>URL</b> (например https://example.com):"
        else:
            prompt = "Отправьте <b>callback_data</b> (например <code>show_profile</code>):"
        await callback.message.edit_text(prompt, reply_markup=_btnc_cancel_kb(f"btnc_list:{menu_type}:0"))

    @admin_router.message(StateFilter(ButtonConstructor.adding_action_value))
    async def btnc_add_action_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Значение не должно быть пустым.")
            return
        new = dict(data.get("btnc_new") or {})
        action_type = new.get("action_type") or "callback"
        if action_type == "url":
            new["url"] = raw
            new["callback_data"] = None
        else:
            new["callback_data"] = raw
            new["url"] = None
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_row)

        # suggest defaults based on existing items
        try:
            existing = get_button_configs_admin(menu_type, include_inactive=True) or []
            max_row = max(int(x.get("row_position", 0) or 0) for x in existing) if existing else 0
        except Exception:
            max_row = 0
        await state.update_data(btnc_default_row=max_row + 1)
        await message.answer(
            "Отправьте <b>row_position</b> (целое число)\n"
            f"Или напишите <code>skip</code>, чтобы поставить по умолчанию: <code>{max_row + 1}</code>",
            reply_markup=_btnc_cancel_kb(f"btnc_list:{menu_type}:0"),
        )

    @admin_router.message(StateFilter(ButtonConstructor.adding_row))
    async def btnc_add_row(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        raw = (message.text or "").strip().lower()
        if raw in {"skip", "-", "—"}:
            row = int(data.get("btnc_default_row") or 0)
        else:
            try:
                row = int(raw)
            except Exception:
                await message.answer("Нужно целое число (или skip).")
                return
        new = dict(data.get("btnc_new") or {})
        new["row_position"] = row
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_col)
        await message.answer("Отправьте <b>column_position</b> (целое число, обычно 0 или 1):", reply_markup=_btnc_cancel_kb(f"btnc_list:{menu_type}:0"))

    @admin_router.message(StateFilter(ButtonConstructor.adding_col))
    async def btnc_add_col(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        raw = (message.text or "").strip()
        try:
            col = int(raw)
        except Exception:
            await message.answer("Нужно целое число.")
            return
        new = dict(data.get("btnc_new") or {})
        new["column_position"] = col
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_width)
        b = InlineKeyboardBuilder()
        b.button(text="1", callback_data="btnc_add_width:1")
        b.button(text="2", callback_data="btnc_add_width:2")
        b.button(text="3", callback_data="btnc_add_width:3")
        b.button(text="❌ Отмена", callback_data="btnc_cancel")
        b.adjust(3, 1)
        await message.answer("Выберите <b>ширину</b> кнопки:", reply_markup=b.as_markup())

    @admin_router.callback_query(StateFilter(ButtonConstructor.adding_width), F.data.startswith("btnc_add_width:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_add_width(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        try:
            w = int((callback.data or "").split(":", 1)[1])
        except Exception:
            w = 1
        new = dict(data.get("btnc_new") or {})
        new["button_width"] = w
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_sort)
        try:
            existing = get_button_configs_admin(menu_type, include_inactive=True) or []
            max_sort = max(int(x.get("sort_order", 0) or 0) for x in existing) if existing else 0
        except Exception:
            max_sort = 0
        await state.update_data(btnc_default_sort=max_sort + 1)
        await callback.message.edit_text(
            "Отправьте <b>sort_order</b> (целое число)\n"
            f"Или <code>skip</code>, чтобы поставить по умолчанию: <code>{max_sort + 1}</code>",
            reply_markup=_btnc_cancel_kb(f"btnc_list:{menu_type}:0"),
        )

    @admin_router.message(StateFilter(ButtonConstructor.adding_sort))
    async def btnc_add_sort(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        raw = (message.text or "").strip().lower()
        if raw in {"skip", "-", "—"}:
            sort = int(data.get("btnc_default_sort") or 0)
        else:
            try:
                sort = int(raw)
            except Exception:
                await message.answer("Нужно целое число (или skip).")
                return
        new = dict(data.get("btnc_new") or {})
        new["sort_order"] = sort
        await state.update_data(btnc_new=new)
        await state.set_state(ButtonConstructor.adding_active)
        b = InlineKeyboardBuilder()
        b.button(text="✅ Активна", callback_data="btnc_add_active:1")
        b.button(text="🔴 Выключена", callback_data="btnc_add_active:0")
        b.button(text="❌ Отмена", callback_data="btnc_cancel")
        b.adjust(2, 1)
        await message.answer("Статус кнопки:", reply_markup=b.as_markup())

    @admin_router.callback_query(StateFilter(ButtonConstructor.adding_active), F.data.startswith("btnc_add_active:"))
    @catch_callback_errors
    @fast_callback_answer
    async def btnc_add_finish(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        menu_type = data.get("btnc_menu_type")
        try:
            active_val = int((callback.data or "").split(":", 1)[1])
        except Exception:
            active_val = 1

        new = dict(data.get("btnc_new") or {})
        try:
            ok = create_button_config(
                menu_type=menu_type,
                button_id=str(new.get("button_id")),
                text=str(new.get("text")),
                callback_data=new.get("callback_data"),
                url=new.get("url"),
                row_position=int(new.get("row_position", 0) or 0),
                column_position=int(new.get("column_position", 0) or 0),
                button_width=int(new.get("button_width", 1) or 1),
                is_active=active_val,
                sort_order=int(new.get("sort_order", 0) or 0),
                metadata=new.get("metadata"),
            )
        except Exception as e:
            ok = False
            logger.exception("Failed to create button config: %s", e)

        await state.clear()
        if ok:
            await callback.message.edit_text("✅ Кнопка создана.")
        else:
            await callback.message.edit_text("❌ Не удалось создать кнопку.")
        await _btnc_show_list(callback.message, menu_type, page=0, edit=False)




    # === Payments settings management ===

    class AdminPayments(StatesGroup):
        waiting_for_value = State()


    def _get_payments_status_for_admin() -> dict:
        yookassa_shop_id = (get_setting('yookassa_shop_id') or '').strip()
        yookassa_secret_key = (get_setting('yookassa_secret_key') or '').strip()
        yookassa_enabled = bool(yookassa_shop_id and yookassa_secret_key)

        cryptobot_token = (get_setting('cryptobot_token') or '').strip()
        cryptobot_enabled = bool(cryptobot_token)

        heleket_merchant_id = (get_setting('heleket_merchant_id') or '').strip()
        heleket_api_key = (get_setting('heleket_api_key') or '').strip()
        heleket_enabled = bool(heleket_merchant_id and heleket_api_key)

        platega_merchant_id = (get_setting('platega_merchant_id') or '').strip()
        platega_secret = (get_setting('platega_secret') or '').strip()
        platega_enabled = bool(platega_merchant_id and platega_secret)

        ton_wallet_address = (get_setting('ton_wallet_address') or '').strip()
        tonapi_key = (get_setting('tonapi_key') or '').strip()
        tonconnect_enabled = bool(ton_wallet_address and tonapi_key)

        yoomoney_enabled = _is_true(get_setting('yoomoney_enabled') or 'false')
        yoomoney_wallet = (get_setting('yoomoney_wallet') or '').strip()
        yoomoney_secret = (get_setting('yoomoney_secret') or '').strip()
        yoomoney_ready = bool(yoomoney_wallet and yoomoney_secret)
        yoomoney_active = bool(yoomoney_enabled and yoomoney_ready)

        stars_enabled = _is_true(get_setting('stars_enabled') or 'false')
        try:
            stars_ratio = float(str(get_setting('stars_per_rub') or '0').replace(',', '.'))
        except Exception:
            stars_ratio = 0.0
        stars_active = bool(stars_enabled and stars_ratio > 0)

        return {
            'yookassa': yookassa_enabled,
            'cryptobot': cryptobot_enabled,
            'heleket': heleket_enabled,
            'platega': platega_enabled,
            'tonconnect': tonconnect_enabled,
            'yoomoney': yoomoney_active,
            'stars': stars_active,
        }


    async def show_admin_payments_menu(message: types.Message, *, edit_message: bool = False):
        status = _get_payments_status_for_admin()
        text = "💳 <b>Платежки</b>\n\nВыберите платежную систему для настройки:" 
        kb = keyboards.create_admin_payments_menu_keyboard(status)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    def _payment_detail_text(provider: str) -> tuple[str, dict]:
        provider = (provider or '').strip().lower()
        flags: dict = {}
        if provider == 'yookassa':
            receipt_email = (get_setting('receipt_email') or '').strip()
            shop_id = (get_setting('yookassa_shop_id') or '').strip()
            secret_key = (get_setting('yookassa_secret_key') or '').strip()
            sbp_enabled = _is_true(get_setting('sbp_enabled') or 'false')
            flags['sbp_enabled'] = sbp_enabled
            active = bool(shop_id and secret_key)
            text = (
                "💳 <b>YooKassa</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Почта для чеков: <code>{html_escape.escape(receipt_email) if receipt_email else '—'}</code>\n"
                f"Shop ID: <code>{html_escape.escape(shop_id) if shop_id else '—'}</code>\n"
                f"Secret Key: <code>{_mask_secret(secret_key)}</code>\n"
                f"СБП: <b>{'включено' if sbp_enabled else 'выключено'}</b>"
            )
            return text, flags

        if provider == 'cryptobot':
            token = (get_setting('cryptobot_token') or '').strip()
            active = bool(token)
            text = (
                "💳 <b>CryptoBot</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Token: <code>{_mask_secret(token)}</code>"
            )
            return text, flags

        if provider == 'heleket':
            merchant_id = (get_setting('heleket_merchant_id') or '').strip()
            api_key = (get_setting('heleket_api_key') or '').strip()
            domain = (get_setting('domain') or '').strip()
            active = bool(merchant_id and api_key)
            text = (
                "💳 <b>Heleket</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Merchant ID: <code>{html_escape.escape(merchant_id) if merchant_id else '—'}</code>\n"
                f"API Key: <code>{_mask_secret(api_key)}</code>\n"
                f"Домен: <code>{html_escape.escape(domain) if domain else '—'}</code>"
            )
            return text, flags


        if provider == 'platega':
            base_url = (get_setting('platega_base_url') or 'https://app.platega.io').strip()
            merchant_id = (get_setting('platega_merchant_id') or '').strip()
            secret = (get_setting('platega_secret') or '').strip()
            methods = (get_setting('platega_active_methods') or '').strip()
            active = bool(merchant_id and secret)
            text = (
                "💳 <b>Platega</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Base URL: <code>{html_escape.escape(base_url) if base_url else '—'}</code>\n"
                f"Merchant ID: <code>{html_escape.escape(merchant_id) if merchant_id else '—'}</code>\n"
                f"Secret: <code>{_mask_secret(secret)}</code>\n"
                f"Методы: <code>{html_escape.escape(methods) if methods else '—'}</code>"
            )
            return text, flags

        if provider == 'tonconnect':
            wallet = (get_setting('ton_wallet_address') or '').strip()
            tonapi_key = (get_setting('tonapi_key') or '').strip()
            active = bool(wallet and tonapi_key)
            text = (
                "💳 <b>TonConnect</b>\n\n"
                f"Статус: {'🟢 Включена' if active else '🔴 Не настроена'}\n"
                f"Ton Wallet: <code>{html_escape.escape(wallet) if wallet else '—'}</code>\n"
                f"TonAPI Key: <code>{_mask_secret(tonapi_key)}</code>"
            )
            return text, flags

        if provider == 'stars':
            enabled = _is_true(get_setting('stars_enabled') or 'false')
            flags['stars_enabled'] = enabled
            try:
                ratio = float(str(get_setting('stars_per_rub') or '0').replace(',', '.'))
            except Exception:
                ratio = 0.0
            active = bool(enabled and ratio > 0)
            text = (
                "💳 <b>Telegram Stars</b>\n\n"
                f"Включено: <b>{'да' if enabled else 'нет'}</b>\n"
                f"Коэффициент: <code>{ratio:g}</code> (⭐ за 1 RUB)\n"
                f"Статус: {'🟢 Активно' if active else '🔴 Не активно'}"
            )
            return text, flags

        if provider == 'yoomoney':
            enabled = _is_true(get_setting('yoomoney_enabled') or 'false')
            flags['yoomoney_enabled'] = enabled
            wallet = (get_setting('yoomoney_wallet') or '').strip()
            secret = (get_setting('yoomoney_secret') or '').strip()
            api_token = (get_setting('yoomoney_api_token') or '').strip()
            client_id = (get_setting('yoomoney_client_id') or '').strip()
            client_secret = (get_setting('yoomoney_client_secret') or '').strip()
            redirect_uri = (get_setting('yoomoney_redirect_uri') or '').strip()
            ready = bool(wallet and secret)
            active = bool(enabled and ready)
            text = (
                "💳 <b>YooMoney</b>\n\n"
                f"Включено: <b>{'да' if enabled else 'нет'}</b>\n"
                f"Статус: {'🟢 Активно' if active else '🔴 Не активно'}\n\n"
                f"Кошелёк: <code>{html_escape.escape(wallet) if wallet else '—'}</code>\n"
                f"Секрет уведомлений: <code>{_mask_secret(secret)}</code>\n"
                f"API Token: <code>{_mask_secret(api_token)}</code>\n"
                f"client_id: <code>{html_escape.escape(client_id) if client_id else '—'}</code>\n"
                f"client_secret: <code>{_mask_secret(client_secret)}</code>\n"
                f"redirect_uri: <code>{html_escape.escape(redirect_uri) if redirect_uri else '—'}</code>"
            )
            return text, flags

        return "💳 <b>Платежки</b>\n\nНеизвестная платежная система.", flags


    async def show_admin_payment_detail(message: types.Message, provider: str, *, edit_message: bool = False):
        text, flags = _payment_detail_text(provider)
        kb = keyboards.create_admin_payment_detail_keyboard(provider, flags=flags)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_payments_menu")
    async def admin_payments_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        await state.clear()
        await show_admin_payments_menu(callback.message, edit_message=True)


    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_payments_open:"))
    async def admin_payments_open(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        provider = callback.data.split("admin_payments_open:", 1)[-1].strip()
        await state.clear()
        await state.update_data(payments_provider=provider)
        await show_admin_payment_detail(callback.message, provider, edit_message=True)


    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_payments_toggle:"))
    async def admin_payments_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        what = callback.data.split("admin_payments_toggle:", 1)[-1].strip()
        if what == 'sbp':
            cur = _is_true(get_setting('sbp_enabled') or 'false')
            rw_repo.update_setting('sbp_enabled', 'false' if cur else 'true')
            provider = 'yookassa'
        elif what == 'stars':
            cur = _is_true(get_setting('stars_enabled') or 'false')
            rw_repo.update_setting('stars_enabled', 'false' if cur else 'true')
            provider = 'stars'
        elif what == 'yoomoney':
            cur = _is_true(get_setting('yoomoney_enabled') or 'false')
            rw_repo.update_setting('yoomoney_enabled', 'false' if cur else 'true')
            provider = 'yoomoney'
        else:
            provider = (await state.get_data()).get('payments_provider') or 'yookassa'
        await show_admin_payment_detail(callback.message, provider, edit_message=True)


    _PAYMENT_FIELD_MAP = {
        # provider -> field -> setting key
        ('yookassa', 'receipt_email'): 'receipt_email',
        ('yookassa', 'shop_id'): 'yookassa_shop_id',
        ('yookassa', 'secret_key'): 'yookassa_secret_key',
        ('cryptobot', 'token'): 'cryptobot_token',
        ('heleket', 'merchant_id'): 'heleket_merchant_id',
        ('heleket', 'api_key'): 'heleket_api_key',
        ('heleket', 'domain'): 'domain',
        ('platega', 'base_url'): 'platega_base_url',
        ('platega', 'merchant_id'): 'platega_merchant_id',
        ('platega', 'secret'): 'platega_secret',
        ('platega', 'active_methods'): 'platega_active_methods',
        ('tonconnect', 'wallet'): 'ton_wallet_address',
        ('tonconnect', 'tonapi'): 'tonapi_key',
        ('stars', 'ratio'): 'stars_per_rub',
        ('yoomoney', 'wallet'): 'yoomoney_wallet',
        ('yoomoney', 'secret'): 'yoomoney_secret',
        ('yoomoney', 'api_token'): 'yoomoney_api_token',
        ('yoomoney', 'client_id'): 'yoomoney_client_id',
        ('yoomoney', 'client_secret'): 'yoomoney_client_secret',
        ('yoomoney', 'redirect_uri'): 'yoomoney_redirect_uri',
    }


    def _payment_prompt(provider: str, field: str) -> str:
        if provider == 'yookassa' and field == 'receipt_email':
            return "Введите почту для чеков (receipt_email) или '-' чтобы очистить:"
        if provider == 'yookassa' and field == 'shop_id':
            return "Введите YooKassa Shop ID или '-' чтобы очистить:"
        if provider == 'yookassa' and field == 'secret_key':
            return "Введите YooKassa Secret Key или '-' чтобы очистить:"
        if provider == 'cryptobot':
            return "Введите CryptoBot Token или '-' чтобы очистить:"
        if provider == 'heleket' and field == 'merchant_id':
            return "Введите Heleket Merchant ID или '-' чтобы очистить:"
        if provider == 'heleket' and field == 'api_key':
            return "Введите Heleket API Key или '-' чтобы очистить:"
        if provider == 'heleket' and field == 'domain':
            return "Введите домен (например my-shop.com) или '-' чтобы очистить:"
        if provider == 'platega' and field == 'base_url':
            return "Введите Platega Base URL (например https://app.platega.io) или '-' чтобы очистить:"
        if provider == 'platega' and field == 'merchant_id':
            return "Введите Platega Merchant ID или '-' чтобы очистить:"
        if provider == 'platega' and field == 'secret':
            return "Введите Platega Secret или '-' чтобы очистить:"
        if provider == 'platega' and field == 'active_methods':
            return "Введите коды методов Platega через запятую (например 2,10,11,12,13) или '-' чтобы очистить:"
        if provider == 'tonconnect' and field == 'wallet':
            return "Введите Ton Wallet address или '-' чтобы очистить:"
        if provider == 'tonconnect' and field == 'tonapi':
            return "Введите TonAPI Key или '-' чтобы очистить:"
        if provider == 'stars' and field == 'ratio':
            return "Введите коэффициент ⭐ за 1 RUB (например 1.0). 0 — отключит оплату звездами:"
        if provider == 'yoomoney' and field == 'wallet':
            return "Введите номер кошелька YooMoney или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'secret':
            return "Введите секрет HTTP-уведомлений YooMoney или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'api_token':
            return "Введите YooMoney API Token (OAuth access_token) или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'client_id':
            return "Введите YooMoney client_id или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'client_secret':
            return "Введите YooMoney client_secret или '-' чтобы очистить:"
        if provider == 'yoomoney' and field == 'redirect_uri':
            return "Введите redirect_uri для OAuth или '-' чтобы очистить:"
        return "Введите значение или '-' чтобы очистить:"


    def _normalize_payment_input(value: str) -> str:
        raw = (value or '').strip()
        if raw in {'-', '—', 'clear', 'clr', 'нет'}:
            return ''
        return raw


    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_payments_set:"))
    async def admin_payments_set(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        try:
            _, provider, field = callback.data.split(":", 2)
        except Exception:
            await callback.answer("Некорректная команда", show_alert=True)
            return
        provider = provider.strip()
        field = field.strip()
        setting_key = _PAYMENT_FIELD_MAP.get((provider, field))
        if not setting_key:
            await callback.answer("Неизвестный параметр", show_alert=True)
            return
        await state.set_state(AdminPayments.waiting_for_value)
        await state.update_data(payments_provider=provider, payments_field=field, payments_key=setting_key)
        await callback.message.answer(
            "✏️ <b>Платежки</b>\n\n" + _payment_prompt(provider, field),
            parse_mode="HTML",
            reply_markup=keyboards.create_admin_payments_cancel_keyboard(f"admin_payments_open:{provider}"),
        )


    @admin_router.message(AdminPayments.waiting_for_value)
    async def admin_payments_set_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        provider = (data.get('payments_provider') or '').strip().lower()
        field = (data.get('payments_field') or '').strip().lower()
        setting_key = (data.get('payments_key') or '').strip()
        if not provider or not field or not setting_key:
            await state.clear()
            await show_admin_payments_menu(message, edit_message=False)
            return

        raw = message.text or ''
        value = _normalize_payment_input(raw)

        # validators
        if (provider, field) == ('stars', 'ratio'):
            try:
                rr = float(value.replace(',', '.')) if value else 0.0
            except Exception:
                await message.answer("❌ Введите число, например 1.0")
                return
            if rr < 0 or rr > 1000:
                await message.answer("❌ Некорректное значение. Допустимо 0..1000")
                return
            value = str(rr)

        # save
        try:
            rw_repo.update_setting(setting_key, value)
        except Exception as e:
            logger.error(f"Не удалось обновить настройку {setting_key}: {e}", exc_info=True)
            await message.answer("❌ Не удалось сохранить настройку")
            return

        await state.clear()
        await message.answer("✅ Сохранено.")
        await show_admin_payment_detail(message, provider, edit_message=False)


    @admin_router.callback_query(F.data == "admin_payments_yoomoney_check")
    async def admin_payments_yoomoney_check(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await fast_callback_answer(callback)
        token = (get_setting('yoomoney_api_token') or '').strip()
        if not token:
            await callback.message.answer("YooMoney: токен не задан.")
            await show_admin_payment_detail(callback.message, 'yoomoney', edit_message=False)
            return

        import aiohttp
        ok = False
        account = None
        err = None
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post('https://yoomoney.ru/api/account-info', headers={'Authorization': f'Bearer {token}'}) as resp:
                    text = await resp.text()
                    status = resp.status
                if status != 200:
                    err = f"account-info HTTP {status}."
                else:
                    try:
                        data = json.loads(text)
                    except Exception:
                        data = {}
                    account = data.get('account') or data.get('account_number')
                    ok = True
        except Exception as e:
            err = str(e)

        if ok:
            await callback.message.answer(f"✅ YooMoney: токен валиден. Кошелёк: {account or '—'}")
        else:
            await callback.message.answer(f"❌ YooMoney: ошибка проверки токена: {err}")

        await show_admin_payment_detail(callback.message, 'yoomoney', edit_message=False)






    
    # === Referral settings management ===

    class AdminReferral(StatesGroup):
        menu = State()
        waiting_for_percent = State()
        waiting_for_fixed_amount = State()
        waiting_for_start_bonus = State()
        waiting_for_min_withdrawal = State()
        waiting_for_discount = State()


    def _get_bool_setting(key: str, default: bool = False) -> bool:
        raw = str(get_setting(key) or ("true" if default else "false")).strip().lower()
        return raw in {"1", "true", "yes", "on"}


    def _get_float_setting(key: str, default: float = 0.0) -> float:
        raw = str(get_setting(key) or str(default))
        try:
            raw = raw.replace(",", ".")
            return float(raw)
        except Exception:
            return float(default)


    def _get_referral_settings_for_admin() -> dict:
        reward_type = (get_setting("referral_reward_type") or "percent_purchase").strip() or "percent_purchase"
        return {
            "enabled": _get_bool_setting("enable_referrals", default=True),
            "days_bonus": _get_bool_setting("enable_referral_days_bonus", default=True),
            "reward_type": reward_type,
            "percentage": _get_float_setting("referral_percentage", 10.0),
            "fixed_amount": _get_float_setting("fixed_referral_bonus_amount", 50.0),
            "start_bonus": _get_float_setting("referral_on_start_referrer_amount", 20.0),
            "min_withdrawal": _get_float_setting("minimum_withdrawal", 100.0),
            "discount": _get_float_setting("referral_discount", 5.0),
        }


    def _format_reward_type_human(reward_type: str) -> str:
        if reward_type == "percent_purchase":
            return "Процент от каждой покупки реферала"
        if reward_type == "fixed_purchase":
            return "Фиксированная сумма за покупку реферала"
        if reward_type == "fixed_start_referrer":
            return "Стартовый бонус пригласившему при старте по реферальной ссылке"
        return reward_type or "—"


    async def show_admin_referral_menu(message: types.Message, edit_message: bool = False):
        ref = _get_referral_settings_for_admin()
        status = "🟢 включена" if ref["enabled"] else "🔴 выключена"
        bonus_day = "✅ да" if ref["days_bonus"] else "❌ нет"

        text_out = (
            "👥 <b>Реферальная программа</b>\n\n"
            f"Статус: <b>{status}</b>\n"
            f"Бонус +1 день к подписке пригласившему: <b>{bonus_day}</b>\n"
            f"Тип начисления: <b>{_format_reward_type_human(ref['reward_type'])}</b>\n\n"
            f"Процент за покупку: <b>{ref['percentage']:.2f}%</b>\n"
            f"Фикс. сумма за покупку: <b>{ref['fixed_amount']:.2f} ₽</b>\n"
            f"Стартовый бонус пригласившему: <b>{ref['start_bonus']:.2f} ₽</b>\n"
            f"Скидка новому пользователю: <b>{ref['discount']:.2f}%</b>\n"
            f"Минимальная сумма для вывода: <b>{ref['min_withdrawal']:.2f} ₽</b>"
        )

        kb = keyboards.create_admin_referral_settings_keyboard(
            enabled=ref["enabled"],
            days_bonus_enabled=ref["days_bonus"],
            reward_type=ref["reward_type"],
        )

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_referral")
    async def admin_referral_menu_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_toggle")
    async def admin_referral_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_referral_settings_for_admin()["enabled"]
        rw_repo.update_setting("enable_referrals", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_toggle_days_bonus")
    async def admin_referral_toggle_days_bonus(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_referral_settings_for_admin()["days_bonus"]
        rw_repo.update_setting("enable_referral_days_bonus", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_set_type")
    async def admin_referral_set_type(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current_type = _get_referral_settings_for_admin()["reward_type"]
        kb = keyboards.create_admin_referral_type_keyboard(current_type)
        text = (
            "🎁 <b>Тип начисления реферального вознаграждения</b>\n\n"
            "Выберите, как начислять бонусы пригласившему:"
        )
        await callback.answer()
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data.startswith("admin_referral_type:"))
    async def admin_referral_type_chosen(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            _, value = (callback.data or "").split(":", 1)
        except Exception:
            await callback.answer("Некорректные данные.", show_alert=True)
            return
        value = (value or "").strip()
        if value not in {"percent_purchase", "fixed_purchase", "fixed_start_referrer"}:
            await callback.answer("Некорректный тип.", show_alert=True)
            return
        rw_repo.update_setting("referral_reward_type", value)
        rw_repo.update_setting("enable_fixed_referral_bonus", "true" if value == "fixed_start_referrer" else "false")
        await callback.answer("Тип обновлён.")
        await state.set_state(AdminReferral.menu)
        await show_admin_referral_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_referral_set_percent")
    async def admin_referral_set_percent(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_percent)
        await callback.answer()
        await callback.message.edit_text(
            "📊 <b>Процент вознаграждения</b>\n\n"
            "Введите процент для пригласившего (0–100):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_percent)
    async def admin_referral_percent_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число от 0 до 100.")
            return
        if val < 0 or val > 100:
            await message.answer("❌ Процент должен быть в диапазоне 0–100.")
            return
        rw_repo.update_setting("referral_percentage", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Процент вознаграждения обновлён.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_fixed_amount")
    async def admin_referral_set_fixed_amount(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_fixed_amount)
        await callback.answer()
        await callback.message.edit_text(
            "💵 <b>Фиксированная сумма за покупку</b>\n\n"
            "Введите сумму в рублях (0–100000):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_fixed_amount)
    async def admin_referral_fixed_amount_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100000).")
            return
        if val < 0 or val > 100000:
            await message.answer("❌ Некорректное значение (0–100000).")
            return
        rw_repo.update_setting("fixed_referral_bonus_amount", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Фиксированная сумма за покупку обновлена.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_start_bonus")
    async def admin_referral_set_start_bonus(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_start_bonus)
        await callback.answer()
        await callback.message.edit_text(
            "💰 <b>Стартовый бонус пригласившему</b>\n\n"
            "Введите сумму в рублях (0–100000):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_start_bonus)
    async def admin_referral_start_bonus_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100000).")
            return
        if val < 0 or val > 100000:
            await message.answer("❌ Некорректное значение (0–100000).")
            return
        rw_repo.update_setting("referral_on_start_referrer_amount", f"{val:.2f}")
        # Если задан стартовый бонус, то включаем флаг фиксированного бонуса
        rw_repo.update_setting("enable_fixed_referral_bonus", "true" if val > 0 else "false")
        await state.clear()
        await message.answer("✅ Стартовый бонус обновлён.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_min_withdrawal")
    async def admin_referral_set_min_withdrawal(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_min_withdrawal)
        await callback.answer()
        await callback.message.edit_text(
            "💳 <b>Минимальная сумма для вывода</b>\n\n"
            "Введите сумму в рублях (0–100000):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_min_withdrawal)
    async def admin_referral_min_withdrawal_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100000).")
            return
        if val < 0 or val > 100000:
            await message.answer("❌ Некорректное значение (0–100000).")
            return
        rw_repo.update_setting("minimum_withdrawal", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Минимальная сумма для вывода обновлена.")
        await show_admin_referral_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_referral_set_discount")
    async def admin_referral_set_discount(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await state.set_state(AdminReferral.waiting_for_discount)
        await callback.answer()
        await callback.message.edit_text(
            "🎟 <b>Скидка для нового пользователя</b>\n\n"
            "Введите процент скидки на первую покупку (0–100):",
            reply_markup=keyboards.create_cancel_keyboard("admin_referral"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminReferral.waiting_for_discount)
    async def admin_referral_discount_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (0–100).")
            return
        if val < 0 or val > 100:
            await message.answer("❌ Процент должен быть в диапазоне 0–100.")
            return
        rw_repo.update_setting("referral_discount", f"{val:.2f}")
        await state.clear()
        await message.answer("✅ Скидка для нового пользователя обновлена.")
        await show_admin_referral_menu(message, edit_message=False)


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
    
    # === End Franchise settings ===


    # === Hosts settings management ===

    class AdminHosts(StatesGroup):
        menu = State()
        host_menu = State()

        waiting_add_name = State()
        waiting_add_base_url = State()
        waiting_add_api_token = State()
        waiting_add_squad_uuid = State()

        waiting_rename = State()
        waiting_set_url = State()
        waiting_set_subscription = State()
        waiting_set_rmw_url = State()
        waiting_set_rmw_token = State()
        waiting_set_squad = State()
        waiting_set_ssh = State()

        squads_menu = State()
        waiting_add_squad2_uuid = State()
        waiting_add_squad2_label = State()


    def _resolve_host_from_digest(digest: str) -> str | None:
        try:
            hosts = get_all_hosts() or []
        except Exception:
            hosts = []
        for h in hosts:
            name = str(h.get('host_name') or '')
            try:
                full = hashlib.sha1((name or '').encode('utf-8', 'ignore')).hexdigest()
            except Exception:
                full = hashlib.sha1(str(name).encode('utf-8', 'ignore')).hexdigest()

            # We use a short digest in callback_data to fit Telegram's 64-byte limit.
            # Accept both the full digest (legacy) and the short prefix (current).
            if full == digest or full.startswith(digest):
                return name
        return None


    def _safe(s: str | None) -> str:
        return html_escape.escape(str(s or '—'))


    def _format_host_card(host: dict) -> str:
        name = host.get('host_name') or '—'
        host_url = host.get('host_url')
        sub_url = host.get('subscription_url')
        rmw_url = host.get('remnawave_base_url')
        squad_uuid = host.get('squad_uuid')

        ssh_host = host.get('ssh_host')
        ssh_port = host.get('ssh_port')
        ssh_user = host.get('ssh_user')
        ssh_key_path = host.get('ssh_key_path')
        ssh_password = host.get('ssh_password')
        ssh_pwd_mask = "✅ задан" if (ssh_password or '').strip() else "—"

        # Фактическое состояние LTE-биллинга определяется host_squads, а не node_class —
        # показываем его явно, чтобы недонастроенная premium-нода была видна сразу.
        try:
            lte_squad = database.get_squad_by_class(name, 'lte') if name and name != '—' else None
        except Exception:
            lte_squad = None
        lte_squad_txt = "✅ настроен" if lte_squad else "— не настроен"

        lines = [
            f"🖥 <b>Хост:</b> <b>{_safe(name)}</b>",
            "",
            f"🌐 URL панели: {_safe(host_url)}",
            f"🔗 Ссылка подписки: {_safe(sub_url)}",
            "",
            f"⚙️ Remnawave URL: {_safe(rmw_url)}",
            f"🧩 Squad UUID: {_safe(squad_uuid)}",
            f"💰 LTE-сквад: {lte_squad_txt}",
            "",
            "🔌 <b>SSH (speedtest)</b>",
            f"Host: {_safe(ssh_host)}",
            f"Port: {_safe(ssh_port)}",
            f"User: {_safe(ssh_user)}",
            f"Key path: {_safe(ssh_key_path)}",
            f"Password: {_safe(ssh_pwd_mask)}",
        ]
        return "\n".join(lines)


    async def show_admin_hosts_menu(message: types.Message, *, edit_message: bool = False):
        hosts = get_all_hosts() or []
        text = "🖥 <b>Хосты</b>\n\nВыберите хост или добавьте новый."
        kb = keyboards.create_admin_hosts_menu_keyboard(hosts)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    async def show_admin_host_detail(message: types.Message, host_name: str, *, edit_message: bool = False):
        host = get_host(host_name) or {}
        try:
            digest = hashlib.sha1((str(host_name) or '').encode('utf-8', 'ignore')).hexdigest()[:12]
        except Exception:
            digest = hashlib.sha1(str(host_name).encode('utf-8', 'ignore')).hexdigest()[:12]
        text = _format_host_card(host)
        try:
            node_class = database.get_host_class(host_name)
        except Exception:
            node_class = 'unlim'
        kb = keyboards.create_admin_host_manage_keyboard(digest, node_class)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    async def show_admin_host_squads(message: types.Message, host_name: str, host_digest: str, *, edit_message: bool = False):
        try:
            squads = get_host_squads(host_name)
        except Exception:
            squads = []
        text = (
            f"🧬 <b>Сквады хоста «{_safe(host_name)}»</b>\n\n"
            "Двухпуловая схема: <b>Base</b> (♾ безлимит) и <b>LTE</b> (💰 отдельный лимит трафика). "
            "У хоста может быть максимум один активный сквад класса Base и один — LTE."
        )
        kb = keyboards.create_admin_host_squads_keyboard(host_digest, squads)
        if edit_message:
            try:
                await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_hosts_menu")
    async def admin_hosts_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.menu)
        await show_admin_hosts_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_hosts_add")
    async def admin_hosts_add(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminHosts.waiting_add_name)
        await callback.message.edit_text(
            "➕ <b>Добавление хоста</b>\n\nВведите <b>название хоста</b>:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard("admin_hosts_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_add_name)
    async def admin_hosts_add_name(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        name = (message.text or '').strip()
        if not name:
            await message.answer("❌ Название не может быть пустым.")
            return
        await state.update_data(add_host_name=name)
        await state.set_state(AdminHosts.waiting_add_base_url)
        await message.answer(
            "Введите <b>базовый URL Remnawave</b> (например: <code>https://panel.example.com</code>):",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard("admin_hosts_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_add_base_url)
    async def admin_hosts_add_base_url(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        base_url = (message.text or '').strip()
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            await message.answer("❌ Укажите корректный URL, начинающийся с http:// или https://")
            return
        await state.update_data(add_base_url=base_url)
        await state.set_state(AdminHosts.waiting_add_api_token)
        await message.answer(
            "Введите <b>API Token</b> Remnawave:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard("admin_hosts_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_add_api_token)
    async def admin_hosts_add_api_token(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        token = (message.text or '').strip()
        if not token:
            await message.answer("❌ API Token не может быть пустым.")
            return
        await state.update_data(add_api_token=token)
        await state.set_state(AdminHosts.waiting_add_squad_uuid)
        await message.answer(
            "Введите <b>Squad UUID</b> (или отправьте <code>-</code>, чтобы пропустить):",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard("admin_hosts_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_add_squad_uuid)
    async def admin_hosts_add_squad_uuid(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        squad_uuid = (message.text or '').strip()
        if squad_uuid == '-':
            squad_uuid = ''
        data = await state.get_data()
        name = (data.get('add_host_name') or '').strip()
        base_url = (data.get('add_base_url') or '').strip()
        token = (data.get('add_api_token') or '').strip()

        # Create host like in web panel
        try:
            create_host(
                name=name,
                url=base_url,
                user='',
                passwd='',
                inbound=0,
                subscription_url=None,
            )
        except Exception:
            pass

        ok_rmw = False
        try:
            ok_rmw = bool(update_host_remnawave_settings(
                name,
                remnawave_base_url=base_url,
                remnawave_api_token=token,
                squad_uuid=squad_uuid or None,
            ))
        except Exception:
            ok_rmw = False

        created = get_host(name) is not None
        await state.clear()

        if not created:
            await message.answer("❌ Не удалось создать хост. Проверьте логи/БД.")
            await show_admin_hosts_menu(message, edit_message=False)
            return

        if ok_rmw:
            await message.answer("✅ Хост добавлен и Remnawave-настройки сохранены.")
        else:
            await message.answer("✅ Хост добавлен, но Remnawave-настройки сохранить не удалось.")
        await show_admin_hosts_menu(message, edit_message=False)


    # NOTE: Use plain lambda filter for maximum compatibility across aiogram versions.
    @admin_router.callback_query(lambda c: isinstance(getattr(c, "data", None), str) and c.data.startswith("admin_hosts_open:"))
    @catch_callback_errors
    @fast_callback_answer
    async def admin_hosts_open(callback: types.CallbackQuery, state: FSMContext):
        """Открыть карточку выбранного хоста.

        В некоторых окружениях фильтр startswith может не срабатывать стабильно,
        поэтому используем строгий regexp по SHA1-дайджесту.
        Также отвечаем на callback максимально быстро.
        """
        if not is_admin(callback.from_user.id):
            try:
                await callback.answer("У вас нет прав.", show_alert=True)
            except Exception:
                pass
            return

        data = callback.data or ""
        digest = data.split("admin_hosts_open:", 1)[-1].strip()

        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            try:
                await callback.answer("Хост не найден.", show_alert=True)
            except Exception:
                pass
            await show_admin_hosts_menu(callback.message, edit_message=True)
            return

        await state.set_state(AdminHosts.host_menu)
        await state.update_data(host_digest=digest, host_name=host_name)
        await show_admin_host_detail(callback.message, host_name, edit_message=True)


    @admin_router.callback_query(F.data.startswith("admin_hosts_squads:"))
    @catch_callback_errors
    @fast_callback_answer
    async def admin_hosts_squads_open(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = (callback.data or "").split("admin_hosts_squads:", 1)[-1].strip()
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            await show_admin_hosts_menu(callback.message, edit_message=True)
            return
        await state.set_state(AdminHosts.squads_menu)
        await state.update_data(host_digest=digest, host_name=host_name)
        await show_admin_host_squads(callback.message, host_name, digest, edit_message=True)


    @admin_router.callback_query(F.data.startswith("admin_hosts_squad_toggle:"))
    @catch_callback_errors
    @fast_callback_answer
    async def admin_hosts_squad_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        # admin_hosts_squad_toggle:{squad_id}:{digest}
        try:
            squad_id = int(parts[1])
        except (IndexError, ValueError):
            await callback.answer("Некорректный ID сквада.", show_alert=True)
            return
        digest = parts[2] if len(parts) > 2 else ""
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return

        squads = get_host_squads(host_name)
        current = next((s for s in squads if s.get('id') == squad_id), None)
        new_active = not bool(current.get('is_active')) if current else True
        try:
            ok = set_host_squad_active(squad_id, new_active)
        except Exception:
            ok = False
        if not ok:
            await callback.answer("Не удалось изменить статус сквада.", show_alert=True)
        await show_admin_host_squads(callback.message, host_name, digest, edit_message=True)


    @admin_router.callback_query(F.data.startswith("admin_hosts_squad_delete:"))
    @catch_callback_errors
    @fast_callback_answer
    async def admin_hosts_squad_delete(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        parts = (callback.data or "").split(":")
        try:
            squad_id = int(parts[1])
        except (IndexError, ValueError):
            await callback.answer("Некорректный ID сквада.", show_alert=True)
            return
        digest = parts[2] if len(parts) > 2 else ""
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        try:
            ok = delete_host_squad(squad_id)
        except Exception:
            ok = False
        if not ok:
            await callback.answer("Не удалось удалить сквад.", show_alert=True)
        await show_admin_host_squads(callback.message, host_name, digest, edit_message=True)


    @admin_router.callback_query(F.data.startswith("admin_hosts_squad_add:"))
    async def admin_hosts_squad_add(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        digest = (callback.data or "").split("admin_hosts_squad_add:", 1)[-1].strip()
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "🧬 <b>Добавление сквада</b>\n\nВыберите класс сквада:",
            reply_markup=keyboards.create_admin_squad_class_keyboard(digest),
            parse_mode="HTML",
        )


    @admin_router.callback_query(F.data.startswith("admin_hosts_squad_add_class:"))
    async def admin_hosts_squad_add_class(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        payload = (callback.data or "").split("admin_hosts_squad_add_class:", 1)[-1]
        digest, _, squad_class = payload.partition(":")
        squad_class = (squad_class or 'base').strip().lower()
        if squad_class not in ('base', 'lte', 'other'):
            squad_class = 'base'
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await state.update_data(host_digest=digest, host_name=host_name, add_squad_class=squad_class)
        await state.set_state(AdminHosts.waiting_add_squad2_uuid)
        await callback.message.edit_text(
            f"🧬 Класс: <b>{squad_class}</b>\n\nВведите <b>Squad UUID</b>:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_squads:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_add_squad2_uuid)
    async def admin_hosts_squad2_uuid(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        squad_uuid = (message.text or '').strip()
        if not squad_uuid:
            await message.answer("❌ Squad UUID не может быть пустым.")
            return
        await state.update_data(add_squad_uuid=squad_uuid)
        await state.set_state(AdminHosts.waiting_add_squad2_label)
        data = await state.get_data()
        digest = data.get('host_digest') or ''
        await message.answer(
            "Введите <b>метку</b> сквада (или отправьте <code>-</code>, чтобы пропустить):",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_squads:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_add_squad2_label)
    async def admin_hosts_squad2_label(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        label = (message.text or '').strip()
        if label == '-':
            label = ''
        data = await state.get_data()
        host_name = data.get('host_name') or ''
        digest = data.get('host_digest') or ''
        squad_class = data.get('add_squad_class') or 'base'
        squad_uuid = data.get('add_squad_uuid') or ''

        squad_id = None
        try:
            squad_id = add_host_squad(host_name, squad_uuid, squad_class, label or None)
        except Exception:
            squad_id = None

        await state.set_state(AdminHosts.squads_menu)
        if squad_id:
            await message.answer("✅ Сквад добавлен.")
        else:
            await message.answer(
                "❌ Не удалось добавить сквад (возможно, уже есть активный сквад этого класса или дубликат UUID)."
            )
        await show_admin_host_squads(message, host_name, digest, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_delete:"))
    async def admin_hosts_delete(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_delete:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            f"🗑 <b>Удалить хост</b> <b>{_safe(host_name)}</b>?\n\n"
            "Будут удалены также все тарифы этого хоста.",
            reply_markup=keyboards.create_admin_hosts_delete_confirm_keyboard(digest),
            parse_mode="HTML",
        )


    @admin_router.callback_query(F.data.startswith("admin_hosts_delete_confirm:"))
    async def admin_hosts_delete_confirm(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_delete_confirm:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            await show_admin_hosts_menu(callback.message, edit_message=True)
            return
        await callback.answer()
        try:
            delete_host(host_name)
        except Exception:
            pass
        await state.set_state(AdminHosts.menu)
        await callback.message.edit_text("✅ Хост удалён.", parse_mode="HTML")
        await show_admin_hosts_menu(callback.message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_rename:"))
    async def admin_hosts_rename(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_rename:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_rename)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            f"✏️ <b>Переименовать хост</b>\n\nТекущее имя: <b>{_safe(host_name)}</b>\n\n"
            "Введите новое имя:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.callback_query(F.data.startswith("admin_hosts_toggle_class:"))
    async def admin_hosts_toggle_class(callback: types.CallbackQuery, state: FSMContext):
        """Переключение класса ноды: ♾ Unlimited <-> 💰 Premium (LTE)."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_toggle_class:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        try:
            current_class = database.get_host_class(host_name)
        except Exception:
            current_class = 'unlim'
        new_class = 'unlim' if current_class == 'premium' else 'premium'
        try:
            database.set_host_class(host_name, new_class)
        except Exception:
            pass
        label = "Premium (LTE) 💰" if new_class == 'premium' else "Unlimited ♾"
        # Источник истины для LTE-биллинга — host_squads(squad_class='lte'), а node_class
        # остаётся признаком/значком ноды. Автоматически создать LTE-сквад нельзя (нужен
        # squad_uuid из панели), поэтому явно предупреждаем админа о недонастройке —
        # раньше он считал ноду настроенной, а докупка LTE у пользователей не работала.
        try:
            lte_squad = database.get_squad_by_class(host_name, 'lte')
        except Exception:
            lte_squad = None
        note = ""
        if new_class == 'premium' and not lte_squad:
            note = (
                "\n\n⚠️ У хоста нет активного сквада класса LTE — докупка и учёт LTE работать не будут. "
                "Добавьте его в «🧬 Сквады хоста»."
            )
        elif new_class == 'unlim' and lte_squad:
            note = "\n\n💰 У хоста остаётся активный LTE-сквад: учёт LTE продолжит работать."
        await callback.answer(f"Класс ноды изменён: {label}{note}", show_alert=bool(note))
        await show_admin_host_detail(callback.message, host_name, edit_message=True)


    @admin_router.message(AdminHosts.waiting_rename)
    async def admin_hosts_rename_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        new_name = (message.text or '').strip()
        if not new_name:
            await message.answer("❌ Имя не может быть пустым.")
            return
        data = await state.get_data()
        old_name = data.get('host_name')
        digest = data.get('host_digest')
        ok = False
        try:
            ok = bool(update_host_name(old_name, new_name))
        except Exception:
            ok = False
        await state.clear()
        if not ok:
            await message.answer("❌ Не удалось переименовать хост (возможно, имя занято).")
            await show_admin_hosts_menu(message, edit_message=False)
            return
        await message.answer("✅ Имя хоста обновлено.")
        await show_admin_hosts_menu(message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_set_url:"))
    async def admin_hosts_set_url(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_set_url:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_set_url)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "🌐 <b>URL панели</b>\n\nВведите новый URL (http/https):",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_set_url)
    async def admin_hosts_set_url_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        new_url = (message.text or '').strip()
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            await message.answer("❌ URL должен начинаться с http:// или https://")
            return
        data = await state.get_data()
        host_name = data.get('host_name')
        digest = data.get('host_digest')
        ok = False
        try:
            ok = bool(update_host_url(host_name, new_url))
        except Exception:
            ok = False
        await state.clear()
        await message.answer("✅ URL обновлён." if ok else "❌ Не удалось обновить URL.")
        if host_name:
            await show_admin_host_detail(message, host_name, edit_message=False)
        else:
            await show_admin_hosts_menu(message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_set_sub:"))
    async def admin_hosts_set_sub(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_set_sub:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_set_subscription)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "🔗 <b>Ссылка подписки</b>\n\n"
            "Отправьте ссылку или <code>-</code> чтобы очистить:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_set_subscription)
    async def admin_hosts_set_sub_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        value = None if raw == '-' or raw == '' else raw
        data = await state.get_data()
        host_name = data.get('host_name')
        ok = False
        try:
            ok = bool(update_host_subscription_url(host_name, value))
        except Exception:
            ok = False
        await state.clear()
        await message.answer("✅ Ссылка подписки обновлена." if ok else "❌ Не удалось обновить ссылку.")
        if host_name:
            await show_admin_host_detail(message, host_name, edit_message=False)
        else:
            await show_admin_hosts_menu(message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_set_rmw_url:"))
    async def admin_hosts_set_rmw_url(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_set_rmw_url:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_set_rmw_url)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "⚙️ <b>Remnawave URL</b>\n\nВведите новый URL или <code>-</code> чтобы очистить:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_set_rmw_url)
    async def admin_hosts_set_rmw_url_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        value = None if raw == '-' or raw == '' else raw
        if value and not (value.startswith("http://") or value.startswith("https://")):
            await message.answer("❌ URL должен начинаться с http:// или https://")
            return
        data = await state.get_data()
        host_name = data.get('host_name')
        ok = False
        try:
            ok = bool(update_host_remnawave_settings(host_name, remnawave_base_url=value))
        except Exception:
            ok = False
        await state.clear()
        await message.answer("✅ Remnawave URL обновлён." if ok else "❌ Не удалось обновить Remnawave URL.")
        if host_name:
            await show_admin_host_detail(message, host_name, edit_message=False)
        else:
            await show_admin_hosts_menu(message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_set_rmw_token:"))
    async def admin_hosts_set_rmw_token(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_set_rmw_token:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_set_rmw_token)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "🔐 <b>Remnawave API Token</b>\n\n"
            "Введите новый токен или <code>-</code> чтобы очистить:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_set_rmw_token)
    async def admin_hosts_set_rmw_token_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        value = None if raw == '-' or raw == '' else raw
        data = await state.get_data()
        host_name = data.get('host_name')
        ok = False
        try:
            ok = bool(update_host_remnawave_settings(host_name, remnawave_api_token=value))
        except Exception:
            ok = False
        await state.clear()
        await message.answer("✅ Token обновлён." if ok else "❌ Не удалось обновить token.")
        if host_name:
            await show_admin_host_detail(message, host_name, edit_message=False)
        else:
            await show_admin_hosts_menu(message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_set_squad:"))
    async def admin_hosts_set_squad(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_set_squad:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_set_squad)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "🧩 <b>Squad UUID</b>\n\nВведите UUID или <code>-</code> чтобы очистить:",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_set_squad)
    async def admin_hosts_set_squad_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        value = None if raw == '-' or raw == '' else raw
        data = await state.get_data()
        host_name = data.get('host_name')
        ok = False
        try:
            ok = bool(update_host_remnawave_settings(host_name, squad_uuid=value))
        except Exception:
            ok = False
        await state.clear()
        await message.answer("✅ Squad UUID обновлён." if ok else "❌ Не удалось обновить Squad UUID.")
        if host_name:
            await show_admin_host_detail(message, host_name, edit_message=False)
        else:
            await show_admin_hosts_menu(message, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_set_ssh:"))
    async def admin_hosts_set_ssh(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_set_ssh:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminHosts.waiting_set_ssh)
        await state.update_data(host_digest=digest, host_name=host_name)
        await callback.message.edit_text(
            "🔌 <b>SSH для speedtest</b>\n\n"
            "Отправьте параметры в формате (каждое с новой строки):\n"
            "<code>ssh_host</code>\n<code>ssh_port</code>\n<code>ssh_user</code>\n<code>ssh_password</code>\n<code>ssh_key_path</code>\n\n"
            "Пароль или key_path можно оставить <code>-</code>.\n"
            "Если хотите очистить ВСЁ — отправьте <code>clear</code>.",
            reply_markup=keyboards.create_admin_hosts_cancel_keyboard(f"admin_hosts_open:{digest}"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminHosts.waiting_set_ssh)
    async def admin_hosts_set_ssh_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        data = await state.get_data()
        host_name = data.get('host_name')
        if not host_name:
            await state.clear()
            await show_admin_hosts_menu(message, edit_message=False)
            return

        if raw.lower() == 'clear':
            ok = False
            try:
                ok = bool(update_host_ssh_settings(host_name, None, None, None, None, None))
            except Exception:
                ok = False
            await state.clear()
            await message.answer("✅ SSH-настройки очищены." if ok else "❌ Не удалось очистить SSH-настройки.")
            await show_admin_host_detail(message, host_name, edit_message=False)
            return

        parts = [p.strip() for p in raw.splitlines() if p.strip() != '']
        if len(parts) < 3:
            await message.answer("❌ Нужно минимум 3 строки: host, port, user (остальные можно '-')")
            return
        ssh_host = parts[0]
        ssh_port = parts[1]
        ssh_user = parts[2]
        ssh_password = parts[3] if len(parts) > 3 else '-'
        ssh_key_path = parts[4] if len(parts) > 4 else '-'

        try:
            port_int = int(ssh_port)
        except Exception:
            await message.answer("❌ Порт должен быть числом.")
            return

        def _n(v: str) -> str | None:
            v = (v or '').strip()
            return None if v in {'', '-'} else v

        ok = False
        try:
            ok = bool(update_host_ssh_settings(
                host_name,
                ssh_host=_n(ssh_host),
                ssh_port=port_int,
                ssh_user=_n(ssh_user),
                ssh_password=_n(ssh_password) if ssh_password != '-' else None,
                ssh_key_path=_n(ssh_key_path),
            ))
        except Exception:
            ok = False

        await state.clear()
        await message.answer("✅ SSH-настройки сохранены." if ok else "❌ Не удалось сохранить SSH-настройки.")
        await show_admin_host_detail(message, host_name, edit_message=False)


    @admin_router.callback_query(F.data.startswith("admin_hosts_to_plans:"))
    async def admin_hosts_to_plans(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        digest = callback.data.split("admin_hosts_to_plans:", 1)[-1]
        host_name = _resolve_host_from_digest(digest)
        if not host_name:
            await callback.answer("Хост не найден.", show_alert=True)
            return
        await callback.answer()
        # Reuse plans UI but jump straight into host menu
        await state.update_data(plans_host=host_name)
        try:
            await state.set_state(AdminPlans.host_menu)
        except Exception:
            pass
        await callback.message.edit_text(
            _format_plans_for_host(host_name),
            reply_markup=keyboards.create_admin_plans_host_menu_keyboard(get_plans_for_host(host_name) or []),
            parse_mode='HTML'
        )


# === Trial settings management ===

    class AdminTrial(StatesGroup):
        menu = State()
        waiting_for_days = State()
        waiting_for_traffic = State()
        waiting_for_devices = State()


    def _get_trial_enabled() -> bool:
        return str(get_setting("trial_enabled") or "false").strip().lower() == "true"


    def _format_trial_value_gb(raw: str | None) -> str:
        s = (raw or "0").strip()
        try:
            gb = float(s.replace(",", "."))
        except Exception:
            gb = 0.0
        if gb <= 0:
            return "без лимита"
        if abs(gb - int(gb)) < 1e-9:
            return f"{int(gb)} ГБ"
        return f"{gb} ГБ"


    def _format_trial_value_int(raw: str | None) -> str:
        s = (raw or "0").strip()
        try:
            val = int(float(s.replace(",", ".")))
        except Exception:
            val = 0
        return "без лимита" if val <= 0 else str(val)


    def _get_trial_days() -> int:
        raw = (get_setting("trial_duration_days") or "3").strip()
        try:
            days = int(float(raw.replace(",", ".")))
        except Exception:
            days = 3
        if days < 1:
            days = 1
        if days > 365:
            days = 365
        return days



    async def show_admin_trial_menu(message: types.Message, edit_message: bool = False):
        enabled = _get_trial_enabled()
        days = _get_trial_days()
        traffic_txt = _format_trial_value_gb(get_setting("trial_traffic_limit_gb"))
        devices_txt = _format_trial_value_int(get_setting("trial_device_limit"))
        default_host = (get_setting("trial_default_host") or "").strip()

        status = "🟢 включён" if enabled else "🔴 выключен"
        host_line = (
            f"Группа тарифов: <b>{default_host}</b>"
            if default_host
            else "Группа тарифов: <b>авто (все доступные)</b>"
        )
        text_out = (
            "🎁 <b>Пробный период (Trial)</b>\n\n"
            f"Статус: {status}\n"
            f"Длительность: <b>{days}</b> дн.\n"
            f"Лимит трафика: <b>{traffic_txt}</b>\n"
            f"Лимит устройств: <b>{devices_txt}</b>\n"
            f"{host_line}\n\n"
            "Подсказка: 0 = без лимита (для трафика и устройств)."
        )

        kb = keyboards.create_admin_trial_settings_keyboard(
            trial_enabled=enabled,
            days=days,
            traffic_text=traffic_txt,
            devices_text=devices_txt,
            default_host=default_host,
        )

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_trial")
    async def admin_trial_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminTrial.menu)
        await show_admin_trial_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_trial_toggle")
    async def admin_trial_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_trial_enabled()
        rw_repo.update_setting("trial_enabled", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminTrial.menu)
        await show_admin_trial_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_trial_set_days")
    async def admin_trial_set_days(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.waiting_for_days)
        await callback.message.edit_text(
            "⏳ <b>Длительность триала</b>\n\n"
            "Введите количество дней (1–365):",
            reply_markup=keyboards.create_cancel_keyboard("admin_trial"),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data == "admin_trial_set_traffic")
    async def admin_trial_set_traffic(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.waiting_for_traffic)
        await callback.message.edit_text(
            "📶 <b>Лимит трафика на триал</b>\n\n"
            "Введите лимит в ГБ (например 1 или 0.5).\n"
            "0 — без лимита:",
            reply_markup=keyboards.create_cancel_keyboard("admin_trial"),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data == "admin_trial_set_devices")
    async def admin_trial_set_devices(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.waiting_for_devices)
        await callback.message.edit_text(
            "📱 <b>Лимит устройств на триал (HWID)</b>\n\n"
            "Введите максимальное число устройств.\n"
            "0 — без лимита:",
            reply_markup=keyboards.create_cancel_keyboard("admin_trial"),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data == "admin_trial_set_host")
    async def admin_trial_set_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminTrial.menu)
        hosts = get_all_hosts()
        await callback.message.edit_text(
            "🖥 <b>Группа тарифов по умолчанию для триала</b>\n\n"
            "Выберите группу тарифов, в которой будут создаваться пробные ключи.\n"
            "<b>Авто</b> — пользователь выбирает сам (или берётся единственная доступная).",
            reply_markup=keyboards.create_admin_trial_host_keyboard(hosts),
            parse_mode="HTML",
        )

    @admin_router.callback_query(F.data.startswith("admin_trial_select_host_"))
    async def admin_trial_select_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        host_name = callback.data[len("admin_trial_select_host_"):]
        rw_repo.update_setting("trial_default_host", host_name)
        label = f"«{host_name}»" if host_name else "авто"
        await callback.answer(f"✅ Группа тарифов триала: {label}", show_alert=True)
        await state.set_state(AdminTrial.menu)
        await show_admin_trial_menu(callback.message, edit_message=True)

    @admin_router.message(AdminTrial.waiting_for_days)
    async def admin_trial_days_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            days = int(float(raw.replace(",", ".")))
        except Exception:
            await message.answer("❌ Введите целое число дней (1–365).")
            return
        if days < 1 or days > 365:
            await message.answer("❌ Значение должно быть в диапазоне 1–365.")
            return
        rw_repo.update_setting("trial_duration_days", str(days))
        await state.clear()
        await message.answer("✅ Длительность триала обновлена.")
        await show_admin_trial_menu(message, edit_message=False)


    @admin_router.message(AdminTrial.waiting_for_traffic)
    async def admin_trial_traffic_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            gb = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число (например 1 или 0.5), либо 0.")
            return
        if gb < 0 or gb > 10000:
            await message.answer("❌ Слишком большое/некорректное значение.")
            return
        if gb == 0:
            val_str = "0"
        else:
            val_str = ("%s" % gb).rstrip("0").rstrip(".")
        rw_repo.update_setting("trial_traffic_limit_gb", val_str)
        await state.clear()
        await message.answer("✅ Лимит трафика триала обновлён.")
        await show_admin_trial_menu(message, edit_message=False)


    @admin_router.message(AdminTrial.waiting_for_devices)
    async def admin_trial_devices_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            val = int(float(raw.replace(",", ".")))
        except Exception:
            await message.answer("❌ Введите целое число, либо 0.")
            return
        if val < 0 or val > 1000:
            await message.answer("❌ Некорректное значение (0–1000).")
            return
        rw_repo.update_setting("trial_device_limit", str(val))
        await state.clear()
        await message.answer("✅ Лимит устройств триала обновлён.")
        await show_admin_trial_menu(message, edit_message=False)


    # === LTE / dual traffic pool settings ===

    class AdminLteSettings(StatesGroup):
        menu = State()
        waiting_for_interval = State()


    def _get_dual_limit_interval() -> int:
        try:
            val = int(float(get_setting("dual_limit_interval_sec") or 120))
        except Exception:
            val = 120
        return val if val > 0 else 120


    async def show_admin_lte_settings_menu(message: types.Message, edit_message: bool = False):
        interval = _get_dual_limit_interval()
        text_out = (
            "💰 <b>LTE / Сброс основного трафика</b>\n\n"
            f"Интервал проверки лимитов (сек): <b>{interval}</b>\n\n"
            "Класс ноды (♾/💰) настраивается в карточке хоста: «🖥 Хосты» → выбрать хост.\n"
            "LTE-лимит, LTE-пакеты и цена сброса основного трафика настраиваются в карточке тарифа: "
            "«🧾 Тарифы» → выбрать тариф. Цена сброса уникальна для каждого тарифа и доступна только "
            "тарифам с лимитом трафика."
        )
        kb = keyboards.create_admin_lte_settings_keyboard(dual_limit_interval_sec=interval)
        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_lte_settings_menu")
    async def admin_lte_settings_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminLteSettings.menu)
        await show_admin_lte_settings_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_lte_set_interval")
    async def admin_lte_set_interval_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminLteSettings.waiting_for_interval)
        await callback.message.edit_text(
            "⏱ <b>Интервал проверки двойных лимитов трафика</b>\n\n"
            "Введите интервал в секундах (например, 120):",
            reply_markup=keyboards.create_cancel_keyboard("admin_lte_settings_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminLteSettings.waiting_for_interval)
    async def admin_lte_set_interval_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            interval = int(float(raw.replace(",", ".")))
            if interval <= 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите положительное целое число секунд, например: 120")
            return
        rw_repo.update_setting("dual_limit_interval_sec", str(interval))
        await state.set_state(AdminLteSettings.menu)
        await message.answer("✅ Интервал проверки обновлён.")
        await show_admin_lte_settings_menu(message, edit_message=False)


    

    # === Notifications (inactive usage reminders) ===

    class AdminNotifications(StatesGroup):
        menu = State()
        waiting_for_interval = State()
        waiting_for_support_url = State()

    def _get_inactive_reminder_enabled() -> bool:
        return _is_true(get_setting("inactive_usage_reminder_enabled") or "true")

    def _get_inactive_reminder_interval_hours() -> float:
        raw = (get_setting("inactive_usage_reminder_interval_hours") or "8").strip()
        try:
            val = float(raw.replace(",", "."))
        except Exception:
            val = 8.0
        if val < 1:
            val = 1.0
        if val > 168:
            val = 168.0
        return val

    def _get_inactive_reminder_support_url() -> str:
        raw = (get_setting("inactive_usage_reminder_support_url") or "").strip()
        return raw

    async def show_admin_notifications_menu(message: types.Message, edit_message: bool = False):
        enabled = _get_inactive_reminder_enabled()
        interval_h = _get_inactive_reminder_interval_hours()

        status = "🟢 включены" if enabled else "🔴 выключены"
        support_url = _get_inactive_reminder_support_url()
        support_part = support_url if support_url else "по умолчанию"

        text_out = (
            "🔔 <b>Уведомления</b>\n\n"
            "Напоминания пользователям, которые получили ключ, но ни разу не использовали трафик.\n\n"
            f"Статус: {status}\n"
            f"Интервал: <b>{interval_h:g}</b> ч.\n"
            f"Ссылка поддержки в уведомлении: <b>{html_escape.escape(support_part)}</b>\n\n"
            "Интервал применяется и к первому уведомлению после выдачи ключа."
        )

        kb = keyboards.create_admin_notifications_settings_keyboard(
            enabled=enabled,
            interval_hours=interval_h,
            support_url=support_url,
        )

        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")


    @admin_router.callback_query(F.data == "admin_notifications_menu")
    async def admin_notifications_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminNotifications.menu)
        await show_admin_notifications_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_inactive_reminder_toggle")
    async def admin_inactive_reminder_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _get_inactive_reminder_enabled()
        rw_repo.update_setting("inactive_usage_reminder_enabled", "false" if current else "true")
        await callback.answer("Обновлено")
        await state.set_state(AdminNotifications.menu)
        await show_admin_notifications_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_inactive_reminder_set_interval")
    async def admin_inactive_reminder_set_interval(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminNotifications.waiting_for_interval)
        await callback.message.edit_text(
            "⏱ <b>Интервал уведомлений</b>\n\n"
            "Введите интервал в часах (1–168).\n"
            "Пример: 8\n\n"
            "Подсказка: интервал также используется как задержка перед первым уведомлением.",
            reply_markup=keyboards.create_cancel_keyboard("admin_notifications_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminNotifications.waiting_for_interval)
    async def admin_inactive_reminder_interval_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        try:
            hours = float(raw.replace(",", "."))
        except Exception:
            await message.answer("❌ Введите число часов (например 8).")
            return
        if hours < 1 or hours > 168:
            await message.answer("❌ Значение должно быть в диапазоне 1–168 часов.")
            return
        # store compact
        val_str = ("%s" % hours).rstrip("0").rstrip(".")
        rw_repo.update_setting("inactive_usage_reminder_interval_hours", val_str)
        await state.clear()
        await message.answer("✅ Интервал уведомлений обновлён.")
        await show_admin_notifications_menu(message, edit_message=False)


    @admin_router.callback_query(F.data == "admin_inactive_reminder_set_support_url")
    async def admin_inactive_reminder_set_support_url(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminNotifications.waiting_for_support_url)
        current = _get_inactive_reminder_support_url().strip()
        hint = f"\n\nТекущее значение: <code>{html_escape.escape(current)}</code>" if current else ""
        await callback.message.edit_text(
            "🆘 <b>Ссылка поддержки для уведомлений</b>\n\n"
            "Введите ссылку (например https://t.me/your_support или t.me/your_support).\n"
            "Чтобы вернуть значение по умолчанию — отправьте 0." + hint,
            reply_markup=keyboards.create_cancel_keyboard("admin_notifications_menu"),
            parse_mode="HTML",
        )


    @admin_router.message(AdminNotifications.waiting_for_support_url)
    async def admin_inactive_reminder_support_url_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip()
        if raw in {"0", "-", "нет", "off"}:
            rw_repo.update_setting("inactive_usage_reminder_support_url", "")
            await state.clear()
            await message.answer("✅ Ссылка поддержки сброшена (будет использоваться значение по умолчанию).")
            await show_admin_notifications_menu(message, edit_message=False)
            return

        # minimal normalization: allow t.me/... or @user
        url = raw
        if url.startswith("@"):
            url = "https://t.me/" + url.lstrip("@")
        elif not url.startswith(("http://", "https://", "tg://")):
            url = "https://" + url.lstrip("/")

        rw_repo.update_setting("inactive_usage_reminder_support_url", url)
        await state.clear()
        await message.answer("✅ Ссылка поддержки обновлена.")
        await show_admin_notifications_menu(message, edit_message=False)


# === Plans (тарифы) management ===

    class AdminPlans(StatesGroup):
        picking_host = State()
        host_menu = State()

        plan_menu = State()
        edit_name = State()
        edit_duration_type = State()
        edit_months = State()
        edit_days = State()
        edit_price = State()
        edit_traffic = State()
        edit_devices = State()
        edit_lte_limit = State()
        edit_main_reset_price = State()
        confirm_delete = State()

        # создание нового тарифа
        waiting_for_plan_name = State()
        waiting_for_duration_type = State()
        waiting_for_months = State()
        waiting_for_days = State()
        waiting_for_traffic = State()
        waiting_for_devices = State()
        waiting_for_price = State()

        # управление пакетами докупки трафика (ГБ)
        packages_menu = State()
        package_menu = State()
        waiting_for_package_size = State()
        waiting_for_package_price = State()
        edit_package_size = State()
        edit_package_price = State()





    def _format_plan_duration(plan: dict) -> str:
        """Человекочитаемый срок тарифа."""
        try:
            dd = int(plan.get('duration_days') or 0)
        except Exception:
            dd = 0
        if dd and dd > 0:
            return f"{dd} дн."
        try:
            mm = int(plan.get('months') or 0)
        except Exception:
            mm = 0
        return f"{mm} мес." if mm else "—"

    def _format_traffic_gb(plan: dict) -> str:
        try:
            b = plan.get('traffic_limit_bytes')
            if b is None:
                return "без лимита"
            b = int(b)
            if b <= 0:
                return "без лимита"
            gb = b / (1024*1024*1024)
            # красивое округление
            if gb.is_integer():
                return f"{int(gb)} ГБ"
            return f"{gb:.2f} ГБ".rstrip('0').rstrip('.')
        except Exception:
            return "—"

    def _format_devices(plan: dict) -> str:
        try:
            d = plan.get('hwid_device_limit')
            if d is None:
                return "без лимита"
            d = int(d)
            if d <= 0:
                return "без лимита"
            return str(d)
        except Exception:
            return "—"

    def _plan_show_name_enabled(plan: dict) -> bool:
        try:
            meta_raw = plan.get("metadata")
            meta = json.loads(meta_raw) if meta_raw else {}
            return bool(meta.get("show_name_in_tariffs"))
        except Exception:
            return False

    def _format_plans_for_host(host_name: str) -> str:
        plans = get_plans_for_host(host_name) or []
        if not plans:
            return f"🧾 <b>Тарифы для хоста:</b> <b>{html_escape.escape(host_name)}</b>\n\n❌ Тарифы не настроены."
        lines = [
            f"🧾 <b>Тарифы для хоста:</b> <b>{html_escape.escape(host_name)}</b>",
            "",
        ]
        for p in plans:
            pid = p.get('plan_id')
            pname = html_escape.escape(str(p.get('plan_name') or '—'))
            price = p.get('price')
            duration_txt = _format_plan_duration(p)
            try:
                price_txt = f"{float(price):.2f} RUB"
            except Exception:
                price_txt = str(price or '—')
            status = "✅" if int(p.get('is_active', 1) or 0) == 1 else "🚫"
            traffic_txt = _format_traffic_gb(p)
            devices_txt = _format_devices(p)
            lines.append(f"{status} <b>#{pid}</b> — {pname} — {duration_txt} — {price_txt} — 📶 {traffic_txt} — 📱 {devices_txt}")
        return "\n".join(lines)


    @admin_router.callback_query(F.data == "admin_plans")
    async def admin_plans_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminPlans.picking_host)
        hosts = get_all_hosts() or []
        await callback.message.edit_text(
            "🧾 <b>Тарифы</b>\n\nВыберите хост, для которого нужно управлять тарифами:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="plans"),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.picking_host, F.data == "admin_plans_back_to_users")
    async def admin_plans_back_to_admin(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await show_admin_menu(callback.message, edit_message=True)


    @admin_router.callback_query(AdminPlans.picking_host, F.data.startswith("admin_plans_pick_host_"))
    async def admin_plans_pick_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        host_name = callback.data.split("admin_plans_pick_host_", 1)[-1]
        await state.update_data(plans_host=host_name)
        await state.set_state(AdminPlans.host_menu)
        await callback.message.edit_text(
            _format_plans_for_host(host_name),
            reply_markup=keyboards.create_admin_plans_host_menu_keyboard(get_plans_for_host(host_name) or []),
            parse_mode='HTML'
        )


    def _format_plan_detail(plan: dict, host_name: str | None = None) -> str:
        pid = plan.get('plan_id')
        pname = html_escape.escape(str(plan.get('plan_name') or '—'))
        duration_txt = _format_plan_duration(plan)
        price = plan.get('price')
        is_active = int(plan.get('is_active', 1) or 0) == 1

        try:
            price_txt = f"{float(price):.2f} RUB"
        except Exception:
            price_txt = str(price or '—')

        traffic_txt = _format_traffic_gb(plan)
        devices_txt = _format_devices(plan)

        status_txt = "✅ Активен" if is_active else "🚫 Скрыт"
        host_part = f"<b>{html_escape.escape(host_name)}</b>" if host_name else "—"

        return (
            "🧾 <b>Тариф</b>\n\n"
            f"ID: <b>#{pid}</b>\n"
            f"Хост: {host_part}\n"
            f"Название: <b>{pname}</b>\n"
            f"Срок: <b>{html_escape.escape(duration_txt)}</b>\n"
            f"Цена: <b>{html_escape.escape(price_txt)}</b>\n"
            f"Лимит трафика: <b>{html_escape.escape(traffic_txt)}</b>\n"
            f"Лимит устройств: <b>{html_escape.escape(devices_txt)}</b>\n"
            f"Статус: <b>{status_txt}</b>\n"
            f"Название в тарифах при покупке: <b>{'✅' if _plan_show_name_enabled(plan) else '❌'}</b>\n\n"
            "Выберите действие:"
        )


    @admin_router.callback_query(AdminPlans.host_menu, F.data.startswith("admin_plans_open_"))
    @admin_router.callback_query(AdminPlans.packages_menu, F.data.startswith("admin_plans_open_"))
    @admin_router.callback_query(AdminPlans.package_menu, F.data.startswith("admin_plans_open_"))
    async def admin_plans_open_plan(callback: types.CallbackQuery, state: FSMContext):
        """Открыть конкретный тариф из списка тарифов хоста."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return

        try:
            plan_id = int(callback.data.split("admin_plans_open_", 1)[-1])
        except Exception:
            await callback.answer("Некорректный тариф.", show_alert=True)
            return

        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.answer("Тариф не найден.", show_alert=True)
            return

        data = await state.get_data()
        host_name = data.get('plans_host')
        # safety: if host was changed or stale
        if host_name and str(plan.get('host_name') or '') != str(host_name):
            await callback.answer("Тариф относится к другому хосту.", show_alert=True)
            return

        await callback.answer()
        await state.update_data(current_plan_id=plan_id)
        await state.set_state(AdminPlans.plan_menu)
        await callback.message.edit_text(
            _format_plan_detail(plan, host_name),
            reply_markup=keyboards.create_admin_plan_manage_keyboard(plan),
            parse_mode='HTML'
        )


    def _format_traffic_package_detail(pkg: dict) -> str:
        pkg_id = pkg.get('package_id')
        try:
            size_gb = float(pkg.get('size_gb') or 0)
        except Exception:
            size_gb = 0.0
        try:
            price = float(pkg.get('price') or 0)
        except Exception:
            price = 0.0
        is_active = int(pkg.get('is_active', 1) or 0) == 1
        size_txt = f"{size_gb:.0f}" if size_gb == int(size_gb) else f"{size_gb:g}"
        status_txt = "✅ Активен" if is_active else "🚫 Скрыт"
        return (
            "📶 <b>Пакет докупки трафика</b>\n\n"
            f"ID: <b>#{pkg_id}</b>\n"
            f"Объём: <b>{size_txt} ГБ</b>\n"
            f"Цена: <b>{price:.2f} RUB</b>\n"
            f"Статус: <b>{status_txt}</b>\n\n"
            "Выберите действие:"
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data.startswith("admin_plan_packages_"))
    async def admin_plan_packages_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            plan_id = int(callback.data.split("admin_plan_packages_", 1)[-1])
        except Exception:
            await callback.answer("Некорректный тариф.", show_alert=True)
            return
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.answer("Тариф не найден.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(current_plan_id=plan_id, current_pkg_pool='main')
        await state.set_state(AdminPlans.packages_menu)
        packages = get_traffic_packages_for_plan(plan_id, pool='main')
        pname = html_escape.escape(str(plan.get('plan_name') or '—'))
        text = (
            f"📶 <b>Пакеты докупки трафика для тарифа «{pname}»</b>\n\n"
            "Пользователи смогут докупить один из этих пакетов ГБ поверх лимита тарифа.\n"
            "Действует до ближайшего ежемесячного сброса трафика."
        )
        if not packages:
            text += "\n\n❌ Пакеты пока не настроены."
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_admin_traffic_packages_keyboard(plan_id, packages, pool='main'),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data.startswith("admin_lte_packages_"))
    async def admin_lte_packages_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            plan_id = int(callback.data.split("admin_lte_packages_", 1)[-1])
        except Exception:
            await callback.answer("Некорректный тариф.", show_alert=True)
            return
        plan = get_plan_by_id(plan_id)
        if not plan:
            await callback.answer("Тариф не найден.", show_alert=True)
            return
        if int(plan.get('lte_limit_bytes') or 0) <= 0:
            await callback.answer("Сначала задайте LTE-лимит тарифа.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(current_plan_id=plan_id, current_pkg_pool='lte')
        await state.set_state(AdminPlans.packages_menu)
        packages = database.get_traffic_packages_for_plan(plan_id, pool='lte')
        pname = html_escape.escape(str(plan.get('plan_name') or '—'))
        text = (
            f"💰 <b>LTE-пакеты докупки для тарифа «{pname}»</b>\n\n"
            "Пользователи смогут докупить один из этих пакетов ГБ в независимый LTE-пул (premium-ноды)."
        )
        if not packages:
            text += "\n\n❌ Пакеты пока не настроены."
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_admin_traffic_packages_keyboard(plan_id, packages, pool='lte'),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_lte_limit")
    async def admin_plan_edit_lte_limit_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_lte_limit)
        await callback.message.edit_text(
            "💰 Введите лимит независимого LTE-пула в ГБ для этого тарифа (0 — отключить LTE-пул):",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard()
        )


    @admin_router.message(AdminPlans.edit_lte_limit)
    async def admin_plan_edit_lte_limit_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or "").replace(",", ".").strip()
        try:
            size_gb = float(text)
            if size_gb < 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите корректное неотрицательное число ГБ, например: 20")
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        if not plan_id:
            await message.answer("❌ Ошибка данных. Начните заново.")
            await state.clear()
            return
        lte_limit_bytes = int(size_gb * 1024 * 1024 * 1024)
        current_plan = get_plan_by_id(int(plan_id))
        if not current_plan:
            await message.answer("❌ Тариф не найден.")
            return
        try:
            update_plan(
                int(plan_id),
                current_plan.get('plan_name'),
                current_plan.get('months'),
                current_plan.get('price'),
                lte_limit_bytes=lte_limit_bytes,
            )
        except Exception as e:
            logger.error(f"admin_plan_edit_lte_limit: не удалось обновить план {plan_id}: {e}", exc_info=True)
            await message.answer("❌ Не удалось сохранить лимит.")
            return
        await state.set_state(AdminPlans.plan_menu)
        plan = get_plan_by_id(int(plan_id))
        data2 = await state.get_data()
        host_name = data2.get('plans_host')
        await message.answer(
            _format_plan_detail(plan, host_name),
            reply_markup=keyboards.create_admin_plan_manage_keyboard(plan),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_main_reset_price")
    async def admin_plan_edit_main_reset_price_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_main_reset_price)
        await callback.message.edit_text(
            "♻️ Введите цену досрочного сброса основного трафика для этого тарифа в рублях "
            "(например, 99). 0 — отключить возможность сброса для пользователей:",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard()
        )


    @admin_router.message(AdminPlans.edit_main_reset_price)
    async def admin_plan_edit_main_reset_price_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or "").replace(",", ".").strip()
        try:
            price = float(text)
            if price < 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите корректное неотрицательное число, например: 99")
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        if not plan_id:
            await message.answer("❌ Ошибка данных. Начните заново.")
            await state.clear()
            return
        current_plan = get_plan_by_id(int(plan_id))
        if not current_plan:
            await message.answer("❌ Тариф не найден.")
            return
        try:
            update_plan(
                int(plan_id),
                current_plan.get('plan_name'),
                current_plan.get('months'),
                current_plan.get('price'),
                main_reset_price_rub=price,
            )
        except Exception as e:
            logger.error(f"admin_plan_edit_main_reset_price: не удалось обновить план {plan_id}: {e}", exc_info=True)
            await message.answer("❌ Не удалось сохранить цену.")
            return
        await state.set_state(AdminPlans.plan_menu)
        plan = get_plan_by_id(int(plan_id))
        data2 = await state.get_data()
        host_name = data2.get('plans_host')
        await message.answer(
            _format_plan_detail(plan, host_name),
            reply_markup=keyboards.create_admin_plan_manage_keyboard(plan),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.packages_menu, F.data.startswith("admin_pkg_add_"))
    async def admin_pkg_add_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        rest = callback.data.split("admin_pkg_add_", 1)[-1]
        pool = 'main'
        plan_id_str = rest
        if rest.endswith('_lte'):
            pool = 'lte'
            plan_id_str = rest[:-len('_lte')]
        elif rest.endswith('_main'):
            pool = 'main'
            plan_id_str = rest[:-len('_main')]
        try:
            plan_id = int(plan_id_str)
        except Exception:
            await callback.answer("Некорректный тариф.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(current_plan_id=plan_id, current_pkg_pool=pool)
        await state.set_state(AdminPlans.waiting_for_package_size)
        await callback.message.edit_text(
            "📶 Введите объём пакета в ГБ (например, 5 или 10):",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard()
        )


    @admin_router.message(AdminPlans.waiting_for_package_size)
    async def admin_pkg_size_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or "").replace(",", ".").strip()
        try:
            size_gb = float(text)
            if size_gb <= 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите корректное положительное число ГБ, например: 10")
            return
        await state.update_data(new_package_size=size_gb)
        await state.set_state(AdminPlans.waiting_for_package_price)
        await message.answer("💰 Теперь введите цену пакета в рублях (например, 99):")


    @admin_router.message(AdminPlans.waiting_for_package_price)
    async def admin_pkg_price_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or "").replace(",", ".").strip()
        try:
            price = float(text)
            if price <= 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите корректную положительную цену, например: 99")
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        size_gb = data.get('new_package_size')
        pool = data.get('current_pkg_pool') or 'main'
        if not plan_id or not size_gb:
            await message.answer("❌ Ошибка данных. Начните заново.")
            await state.clear()
            return
        create_traffic_package(int(plan_id), float(size_gb), float(price), pool=pool)
        await state.set_state(AdminPlans.packages_menu)
        packages = get_traffic_packages_for_plan(int(plan_id), pool=pool)
        await message.answer(
            "✅ Пакет добавлен.",
            reply_markup=keyboards.create_admin_traffic_packages_keyboard(int(plan_id), packages, pool=pool)
        )


    @admin_router.callback_query(AdminPlans.packages_menu, F.data.startswith("admin_pkg_open_"))
    async def admin_pkg_open(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            pkg_id = int(callback.data.split("admin_pkg_open_", 1)[-1])
        except Exception:
            await callback.answer("Некорректный пакет.", show_alert=True)
            return
        pkg = get_traffic_package_by_id(pkg_id)
        if not pkg:
            await callback.answer("Пакет не найден.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(current_package_id=pkg_id, current_plan_id=pkg.get('plan_id'))
        await state.set_state(AdminPlans.package_menu)
        is_active = int(pkg.get('is_active', 1) or 0) == 1
        await callback.message.edit_text(
            _format_traffic_package_detail(pkg),
            reply_markup=keyboards.create_admin_traffic_package_manage_keyboard(pkg_id, pkg.get('plan_id'), is_active),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.package_menu, F.data.startswith("admin_pkg_edit_size_"))
    async def admin_pkg_edit_size_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_package_size)
        await callback.message.edit_text(
            "📶 Введите новый объём пакета в ГБ:",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard()
        )


    @admin_router.message(AdminPlans.edit_package_size)
    async def admin_pkg_edit_size_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or "").replace(",", ".").strip()
        try:
            size_gb = float(text)
            if size_gb <= 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите корректное положительное число ГБ.")
            return
        data = await state.get_data()
        pkg_id = data.get('current_package_id')
        plan_id = data.get('current_plan_id')
        update_traffic_package(int(pkg_id), size_gb=size_gb)
        await state.set_state(AdminPlans.package_menu)
        pkg = get_traffic_package_by_id(int(pkg_id))
        is_active = int(pkg.get('is_active', 1) or 0) == 1
        await message.answer(
            _format_traffic_package_detail(pkg),
            reply_markup=keyboards.create_admin_traffic_package_manage_keyboard(int(pkg_id), plan_id, is_active),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.package_menu, F.data.startswith("admin_pkg_edit_price_"))
    async def admin_pkg_edit_price_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_package_price)
        await callback.message.edit_text(
            "💰 Введите новую цену пакета в рублях:",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard()
        )


    @admin_router.message(AdminPlans.edit_package_price)
    async def admin_pkg_edit_price_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or "").replace(",", ".").strip()
        try:
            price = float(text)
            if price <= 0:
                raise ValueError
        except Exception:
            await message.answer("❌ Введите корректную положительную цену.")
            return
        data = await state.get_data()
        pkg_id = data.get('current_package_id')
        plan_id = data.get('current_plan_id')
        update_traffic_package(int(pkg_id), price=price)
        await state.set_state(AdminPlans.package_menu)
        pkg = get_traffic_package_by_id(int(pkg_id))
        is_active = int(pkg.get('is_active', 1) or 0) == 1
        await message.answer(
            _format_traffic_package_detail(pkg),
            reply_markup=keyboards.create_admin_traffic_package_manage_keyboard(int(pkg_id), plan_id, is_active),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.package_menu, F.data.startswith("admin_pkg_toggle_"))
    async def admin_pkg_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            pkg_id = int(callback.data.split("admin_pkg_toggle_", 1)[-1])
        except Exception:
            await callback.answer("Некорректный пакет.", show_alert=True)
            return
        pkg = get_traffic_package_by_id(pkg_id)
        if not pkg:
            await callback.answer("Пакет не найден.", show_alert=True)
            return
        is_active = int(pkg.get('is_active', 1) or 0) == 1
        update_traffic_package(pkg_id, is_active=not is_active)
        await callback.answer("Статус изменён.")
        pkg = get_traffic_package_by_id(pkg_id)
        is_active = int(pkg.get('is_active', 1) or 0) == 1
        await callback.message.edit_text(
            _format_traffic_package_detail(pkg),
            reply_markup=keyboards.create_admin_traffic_package_manage_keyboard(pkg_id, pkg.get('plan_id'), is_active),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.package_menu, F.data.startswith("admin_pkg_delete_"))
    async def admin_pkg_delete(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        try:
            pkg_id = int(callback.data.split("admin_pkg_delete_", 1)[-1])
        except Exception:
            await callback.answer("Некорректный пакет.", show_alert=True)
            return
        pkg = get_traffic_package_by_id(pkg_id)
        plan_id = pkg.get('plan_id') if pkg else None
        delete_traffic_package(pkg_id)
        await callback.answer("Пакет удалён.")
        await state.set_state(AdminPlans.packages_menu)
        packages = get_traffic_packages_for_plan(plan_id) if plan_id else []
        await callback.message.edit_text(
            "📶 Пакеты обновлены.",
            reply_markup=keyboards.create_admin_traffic_packages_keyboard(plan_id, packages)
        )



    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_name")
    async def admin_plan_edit_name(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_name)
        await callback.message.edit_text(
            "✏️ <b>Редактирование тарифа</b>\n\nВведите новое <b>название</b> тарифа:",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_months")
    async def admin_plan_edit_months(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        # backward compatibility: open duration selector
        await state.set_state(AdminPlans.edit_duration_type)
        await callback.message.edit_text(
            "⏳ <b>Срок тарифа</b>\n\nВыберите, в каких единицах указать срок:",
            reply_markup=keyboards.create_admin_plan_duration_type_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_price")
    async def admin_plan_edit_price(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_price)
        await callback.message.edit_text(
            "💰 <b>Редактирование тарифа</b>\n\nВведите новую цену (например: 199 или 199.99):",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard(),
            parse_mode='HTML'
        )



    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_duration")
    async def admin_plan_edit_duration(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_duration_type)
        await callback.message.edit_text(
            "⏳ <b>Срок тарифа</b>\n\nВыберите, в каких единицах указать срок:",
            reply_markup=keyboards.create_admin_plan_duration_type_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.edit_duration_type, F.data == "admin_plan_duration_months")
    async def admin_plan_duration_months(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.set_state(AdminPlans.edit_months)
        await callback.message.edit_text(
            "⏳ <b>Редактирование тарифа</b>\n\nВведите срок тарифа в <b>месяцах</b> (1–120):",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.edit_duration_type, F.data == "admin_plan_duration_days")
    async def admin_plan_duration_days(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await state.set_state(AdminPlans.edit_days)
        await callback.message.edit_text(
            "⏳ <b>Редактирование тарифа</b>\n\nВведите срок тарифа в <b>днях</b> (1–3650):",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_traffic")
    async def admin_plan_edit_traffic(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_traffic)
        await callback.message.edit_text(
            "📶 <b>Лимит трафика</b>\n\nВведите лимит в <b>ГБ</b>.\n0 — без лимита.",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_edit_devices")
    async def admin_plan_edit_devices(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.edit_devices)
        await callback.message.edit_text(
            "📱 <b>Лимит устройств</b>\n\nВведите целое число.\n0 — без лимита.",
            reply_markup=keyboards.create_admin_plan_edit_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_toggle_active")
    async def admin_plan_toggle_active(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await callback.answer("Не удалось определить тариф.", show_alert=True)
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await callback.answer("Тариф не найден.", show_alert=True)
            return
        is_active = int(plan.get('is_active', 1) or 0) == 1
        ok = set_plan_active(int(plan_id), not is_active)
        if not ok:
            await callback.answer("Не удалось изменить статус.", show_alert=True)
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await callback.message.edit_text(
            _format_plan_detail(plan, host_name=host_name),
            reply_markup=keyboards.create_admin_plan_manage_keyboard(plan),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_toggle_show_name")
    async def admin_plan_toggle_show_name(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await callback.answer("Не удалось определить тариф.", show_alert=True)
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await callback.answer("Тариф не найден.", show_alert=True)
            return

        # Toggle metadata flag
        try:
            meta_raw = plan.get('metadata')
            meta = json.loads(meta_raw) if meta_raw else {}
        except Exception:
            meta = {}

        current = bool(meta.get('show_name_in_tariffs'))
        meta['show_name_in_tariffs'] = (not current)
        update_plan_metadata(int(plan_id), meta)

        plan = get_plan_by_id(int(plan_id)) or plan
        await callback.message.edit_text(
            _format_plan_detail(plan, host_name=host_name),
            reply_markup=keyboards.create_admin_plan_manage_keyboard(plan),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.plan_menu, F.data == "admin_plan_delete")
    async def admin_plan_delete_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.confirm_delete)
        await callback.message.edit_text(
            "🗑 <b>Удаление тарифа</b>\n\nТочно удалить этот тариф? Действие необратимо.",
            reply_markup=keyboards.create_admin_plan_delete_confirm_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.confirm_delete, F.data == "admin_plan_delete_cancel")
    async def admin_plan_delete_cancel(callback: types.CallbackQuery, state: FSMContext):
        # возвращаемся в меню тарифа
        await admin_plan_back(callback, state)


    @admin_router.callback_query(AdminPlans.confirm_delete, F.data == "admin_plan_delete_confirm")
    async def admin_plan_delete_confirm(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await callback.answer("Не удалось определить тариф.", show_alert=True)
            return
        try:
            delete_plan(int(plan_id))
        except Exception:
            logger.exception("Failed to delete plan")
            await callback.answer("Ошибка при удалении тарифа.", show_alert=True)
            return

        await state.set_state(AdminPlans.host_menu)
        if not host_name:
            host_name = data.get('plans_host')

        if host_name:
            await callback.message.edit_text(
                "✅ Тариф удален.\n\n" + _format_plans_for_host(host_name),
                reply_markup=keyboards.create_admin_plans_host_menu_keyboard(get_plans_for_host(host_name) or []),
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text("✅ Тариф удален.", reply_markup=keyboards.create_admin_cancel_keyboard())


    @admin_router.message(AdminPlans.edit_name)
    async def admin_plan_edit_name_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        name = (message.text or '').strip()
        if not name or len(name) < 2 or len(name) > 64:
            await message.answer("❌ Название должно быть от 2 до 64 символов.", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await message.answer("❌ Не удалось определить тариф.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await message.answer("❌ Тариф не найден.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        ok = update_plan(int(plan_id), name, int(plan.get('months') or 1), float(plan.get('price') or 0))
        if not ok:
            await message.answer("❌ Не удалось сохранить изменения.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await state.set_state(AdminPlans.plan_menu)
        await message.answer("✅ Название обновлено.")
        await message.answer(_format_plan_detail(plan, host_name=host_name), reply_markup=keyboards.create_admin_plan_manage_keyboard(plan), parse_mode='HTML')


    @admin_router.message(AdminPlans.edit_months)
    async def admin_plan_edit_months_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            months = int(raw)
        except Exception:
            await message.answer("❌ Введите целое число (1–120).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        if months <= 0 or months > 120:
            await message.answer("❌ Некорректный срок. Введите число от 1 до 120.", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await message.answer("❌ Не удалось определить тариф.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await message.answer("❌ Тариф не найден.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        ok = update_plan(int(plan_id), str(plan.get('plan_name') or '—'), months, float(plan.get('price') or 0), duration_days=None)
        if not ok:
            await message.answer("❌ Не удалось сохранить изменения.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await state.set_state(AdminPlans.plan_menu)
        await message.answer("✅ Срок обновлен.")
        await message.answer(_format_plan_detail(plan, host_name=host_name), reply_markup=keyboards.create_admin_plan_manage_keyboard(plan), parse_mode='HTML')


    @admin_router.message(AdminPlans.edit_price)
    async def admin_plan_edit_price_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().replace(",", ".")
        try:
            price = float(raw)
        except Exception:
            await message.answer("❌ Введите число (например 199 или 199.99).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        if price <= 0 or price > 1000000:
            await message.answer("❌ Некорректная цена.", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await message.answer("❌ Не удалось определить тариф.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await message.answer("❌ Тариф не найден.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        ok = update_plan(int(plan_id), str(plan.get('plan_name') or '—'), int(plan.get('months') or 1), price)
        if not ok:
            await message.answer("❌ Не удалось сохранить изменения.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await state.set_state(AdminPlans.plan_menu)
        await message.answer("✅ Цена обновлена.")
        await message.answer(_format_plan_detail(plan, host_name=host_name), reply_markup=keyboards.create_admin_plan_manage_keyboard(plan), parse_mode='HTML')



    @admin_router.message(AdminPlans.edit_days)
    async def admin_plan_edit_days_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            days = int(raw)
        except Exception:
            await message.answer("❌ Введите целое число (1–3650).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        if days <= 0 or days > 3650:
            await message.answer("❌ Некорректный срок. Введите число от 1 до 3650.", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await message.answer("❌ Не удалось определить тариф.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await message.answer("❌ Тариф не найден.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return

        ok = update_plan(
            int(plan_id),
            str(plan.get('plan_name') or '—'),
            None,  # months -> NULL, т.к. теперь срок в днях
            float(plan.get('price') or 0),
            duration_days=int(days),
        )
        if not ok:
            await message.answer("❌ Не удалось сохранить изменения.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await state.set_state(AdminPlans.plan_menu)
        await message.answer("✅ Срок обновлен.")
        await message.answer(_format_plan_detail(plan, host_name=host_name), reply_markup=keyboards.create_admin_plan_manage_keyboard(plan), parse_mode='HTML')


    @admin_router.message(AdminPlans.edit_traffic)
    async def admin_plan_edit_traffic_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().replace(',', '.')
        try:
            gb = float(raw)
        except Exception:
            await message.answer("❌ Введите число (например 10 или 10.5).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        if gb < 0 or gb > 100000:
            await message.answer("❌ Некорректное значение (0–100000).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return

        limit_bytes = 0
        if gb > 0:
            limit_bytes = int(gb * 1024 * 1024 * 1024)

        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await message.answer("❌ Не удалось определить тариф.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await message.answer("❌ Тариф не найден.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return

        ok = update_plan(
            int(plan_id),
            str(plan.get('plan_name') or '—'),
            plan.get('months'),
            float(plan.get('price') or 0),
            traffic_limit_bytes=limit_bytes,
        )
        if not ok:
            await message.answer("❌ Не удалось сохранить изменения.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await state.set_state(AdminPlans.plan_menu)
        await message.answer("✅ Лимит трафика обновлён.")
        await message.answer(_format_plan_detail(plan, host_name=host_name), reply_markup=keyboards.create_admin_plan_manage_keyboard(plan), parse_mode='HTML')


    @admin_router.message(AdminPlans.edit_devices)
    async def admin_plan_edit_devices_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().replace(',', '.')
        try:
            val = int(float(raw))
        except Exception:
            await message.answer("❌ Введите целое число (например 1 или 3).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return
        if val < 0 or val > 1000:
            await message.answer("❌ Некорректное значение (0–1000).", reply_markup=keyboards.create_admin_plan_edit_flow_keyboard())
            return

        limit = None if val <= 0 else val

        data = await state.get_data()
        plan_id = data.get('current_plan_id')
        host_name = data.get('plans_host')
        if not plan_id:
            await message.answer("❌ Не удалось определить тариф.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id))
        if not plan:
            await message.answer("❌ Тариф не найден.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return

        ok = update_plan(
            int(plan_id),
            str(plan.get('plan_name') or '—'),
            plan.get('months'),
            float(plan.get('price') or 0),
            hwid_device_limit=limit,
        )
        if not ok:
            await message.answer("❌ Не удалось сохранить изменения.", reply_markup=keyboards.create_admin_cancel_keyboard())
            return
        plan = get_plan_by_id(int(plan_id)) or plan
        await state.set_state(AdminPlans.plan_menu)
        await message.answer("✅ Лимит устройств обновлён.")
        await message.answer(_format_plan_detail(plan, host_name=host_name), reply_markup=keyboards.create_admin_plan_manage_keyboard(plan), parse_mode='HTML')


    @admin_router.callback_query(AdminPlans.host_menu, F.data == "admin_plans_back_to_hosts")
    async def admin_plans_back_to_hosts(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminPlans.picking_host)
        hosts = get_all_hosts() or []
        await callback.message.edit_text(
            "🧾 <b>Тарифы</b>\n\nВыберите хост, для которого нужно управлять тарифами:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="plans"),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.host_menu, F.data == "admin_plans_add")
    async def admin_plans_add_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        host_name = data.get('plans_host')
        if not host_name:
            await callback.message.edit_text(
                "❌ Не удалось определить хост. Вернитесь и выберите хост заново.",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            await state.set_state(AdminPlans.picking_host)
            return
        await state.set_state(AdminPlans.waiting_for_plan_name)
        await callback.message.edit_text(
            f"🧾 Добавление тарифа\n\nХост: <b>{html_escape.escape(host_name)}</b>\n\nВведите <b>название тарифа</b>:",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )



    @admin_router.callback_query(AdminPlans.waiting_for_duration_type, F.data == "admin_plans_duration_months")
    async def admin_plans_new_duration_months(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(new_plan_duration_unit="months")
        await state.set_state(AdminPlans.waiting_for_months)
        await callback.message.edit_text(
            "⏳ <b>Создание тарифа</b>\n\nВведите срок тарифа в <b>месяцах</b> (1–120):",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.callback_query(AdminPlans.waiting_for_duration_type, F.data == "admin_plans_duration_days")
    async def admin_plans_new_duration_days(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(new_plan_duration_unit="days")
        await state.set_state(AdminPlans.waiting_for_days)
        await callback.message.edit_text(
            "⏳ <b>Создание тарифа</b>\n\nВведите срок тарифа в <b>днях</b> (1–3650):",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )

    @admin_router.callback_query(StateFilter(AdminPlans), F.data == "admin_plans_back_to_host_menu")
    async def admin_plans_back_to_host_menu(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        host_name = data.get('plans_host')
        if not host_name:
            await state.set_state(AdminPlans.picking_host)
            hosts = get_all_hosts() or []
            await callback.message.edit_text(
                "🧾 <b>Тарифы</b>\n\nВыберите хост, для которого нужно управлять тарифами:",
                reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="plans"),
                parse_mode='HTML'
            )
            return

        await state.set_state(AdminPlans.host_menu)
        await callback.message.edit_text(
            _format_plans_for_host(host_name),
            reply_markup=keyboards.create_admin_plans_host_menu_keyboard(get_plans_for_host(host_name) or []),
            parse_mode='HTML'
        )


    @admin_router.message(AdminPlans.waiting_for_plan_name)
    async def admin_plans_plan_name_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        plan_name = (message.text or '').strip()
        if not plan_name:
            await message.answer(
                "❌ Название тарифа не может быть пустым. Введите название тарифа:",
                reply_markup=keyboards.create_admin_plans_flow_keyboard()
            )
            return
        if len(plan_name) > 64:
            await message.answer(
                "❌ Слишком длинное название (макс. 64 символа). Введите короче:",
                reply_markup=keyboards.create_admin_plans_flow_keyboard()
            )
            return
        await state.update_data(new_plan_name=plan_name)
        await state.set_state(AdminPlans.waiting_for_duration_type)
        await message.answer(
            "⏳ <b>Создание тарифа</b>\n\nВыберите, в чём указывать срок тарифа:",
            reply_markup=keyboards.create_admin_plans_duration_type_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.message(AdminPlans.waiting_for_months)
    async def admin_plans_months_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            months = int(raw)
        except Exception:
            await message.answer(
                "❌ Введите целое число — срок в месяцах:",
                reply_markup=keyboards.create_admin_plans_flow_keyboard()
            )
            return
        if months <= 0 or months > 120:
            await message.answer(
                "❌ Некорректный срок. Введите число от 1 до 120:",
                reply_markup=keyboards.create_admin_plans_flow_keyboard()
            )
            return
        # Для тарифов в месяцах тоже собираем лимиты (ГБ/устройства) как и для тарифов в днях.
        await state.update_data(new_plan_months=months, new_plan_days=None)
        await state.set_state(AdminPlans.waiting_for_traffic)
        await message.answer(
            "📶 Теперь введите <b>лимит трафика</b> в ГБ.\n0 — без лимита.",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )


    
    @admin_router.message(AdminPlans.waiting_for_days)
    async def admin_plan_add_days_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            days = int(raw)
        except Exception:
            await message.answer("❌ Введите целое число (1–3650).", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return
        if days <= 0 or days > 3650:
            await message.answer("❌ Некорректный срок. Введите число от 1 до 3650.", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return

        await state.update_data(new_plan_days=days, new_plan_months=None)
        await state.set_state(AdminPlans.waiting_for_traffic)
        await message.answer(
            "📶 Теперь введите <b>лимит трафика</b> в ГБ.\n0 — без лимита.",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.message(AdminPlans.waiting_for_traffic)
    async def admin_plan_add_traffic_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().replace(',', '.')
        try:
            gb = float(raw)
        except Exception:
            await message.answer("❌ Введите число (например 10 или 10.5).", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return
        if gb < 0 or gb > 100000:
            await message.answer("❌ Некорректное значение (0–100000).", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return

        limit_bytes = 0
        if gb > 0:
            limit_bytes = int(gb * 1024 * 1024 * 1024)

        await state.update_data(new_plan_traffic_limit_bytes=limit_bytes)
        await state.set_state(AdminPlans.waiting_for_devices)
        await message.answer(
            "📱 Теперь введите <b>лимит устройств</b> (HWID).\n0 — без лимита.",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )


    @admin_router.message(AdminPlans.waiting_for_devices)
    async def admin_plan_add_devices_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().replace(',', '.')
        try:
            val = int(float(raw))
        except Exception:
            await message.answer("❌ Введите целое число (например 1 или 3).", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return
        if val < 0 or val > 1000:
            await message.answer("❌ Некорректное значение (0–1000).", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return
        limit = None if val <= 0 else val

        await state.update_data(new_plan_hwid_device_limit=limit)
        await state.set_state(AdminPlans.waiting_for_price)
        await message.answer(
            "💰 Теперь введите цену тарифа (например: 199 или 199.99):",
            reply_markup=keyboards.create_admin_plans_flow_keyboard(),
            parse_mode='HTML'
        )

    @admin_router.message(AdminPlans.waiting_for_price)
    async def admin_plans_price_received(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().replace(",", ".")
        try:
            price = float(raw)
        except Exception:
            await message.answer("❌ Введите число (например 199 или 199.99).", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return
        if price <= 0 or price > 1000000:
            await message.answer("❌ Некорректная цена.", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return

        data = await state.get_data()
        host_name = data.get('plans_host')
        plan_name = data.get('new_plan_name')
        months = data.get('new_plan_months')
        days = data.get('new_plan_days')
        traffic_limit_bytes = data.get('new_plan_traffic_limit_bytes')
        hwid_device_limit = data.get('new_plan_hwid_device_limit')

        if not host_name or not plan_name or ((months is None or int(months) <= 0) and (days is None or int(days) <= 0)):
            await message.answer(
                "❌ Не удалось собрать данные тарифа (хост/название/срок). Начните заново.",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            await state.clear()
            return

        try:
            create_plan(
                host_name=str(host_name),
                plan_name=str(plan_name),
                months=int(months) if months is not None else None,
                duration_days=int(days) if days is not None else None,
                price=float(price),
                traffic_limit_bytes=traffic_limit_bytes,
                hwid_device_limit=hwid_device_limit,
            )
        except Exception as e:
            logger.error(f"Admin plans: failed to create plan for host '{host_name}': {e}")
            await message.answer(f"❌ Не удалось создать тариф: {e}", reply_markup=keyboards.create_admin_plans_flow_keyboard())
            return

        # Return to host menu with refreshed list
        await state.update_data(
            new_plan_name=None,
            new_plan_months=None,
            new_plan_days=None,
            new_plan_traffic_limit_bytes=None,
            new_plan_hwid_device_limit=None,
        )
        await state.set_state(AdminPlans.host_menu)
        await message.answer("✅ Тариф добавлен.")
        await message.answer(
            _format_plans_for_host(host_name),
            reply_markup=keyboards.create_admin_plans_host_menu_keyboard(get_plans_for_host(host_name) or []),
            parse_mode='HTML'
        )


    class AdminPromoCreate(StatesGroup):
        waiting_for_code = State()
        waiting_for_discount_type = State()
        waiting_for_discount_value = State()
        waiting_for_total_limit = State()
        waiting_for_per_user_limit = State()
        waiting_for_valid_from = State()
        waiting_for_valid_until = State()
        waiting_for_description = State()
        waiting_for_segment = State()
        waiting_for_segment_value = State()
        waiting_for_plans = State()
        confirming = State()

    @admin_router.callback_query(F.data == "admin_promo_menu")
    async def admin_promo_menu_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await show_admin_promo_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_promo_create")
    async def admin_promo_create_start(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminPromoCreate.waiting_for_code)
        await callback.message.edit_text(
            "🔐 Создание промокода\n\nВыберите способ указания кода:",
            reply_markup=keyboards.create_admin_promo_code_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_code,
        F.data == "admin_promo_code_auto"
    )
    async def admin_promo_code_auto(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        code = uuid.uuid4().hex[:8].upper()
        await state.update_data(promo_code=code)
        await state.set_state(AdminPromoCreate.waiting_for_discount_type)
        try:
            await callback.message.edit_text(
                f"Код: <code>{code}</code>\n\nВыберите тип скидки:",
                reply_markup=keyboards.create_admin_promo_discount_keyboard(),
                parse_mode='HTML'
            )
        except Exception:
            await callback.message.answer(
                f"Код: <code>{code}</code>\n\nВыберите тип скидки:",
                reply_markup=keyboards.create_admin_promo_discount_keyboard(),
                parse_mode='HTML'
            )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_code,
        F.data == "admin_promo_code_custom"
    )
    async def admin_promo_code_custom(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            "Введите желаемый код (только латиница/цифры) или напишите <b>авто</b> для генерации:",
            reply_markup=keyboards.create_admin_cancel_keyboard(),
            parse_mode='HTML'
        )

    @admin_router.message(AdminPromoCreate.waiting_for_code)
    async def admin_promo_create_code(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        if not raw:
            await message.answer("❌ Введите код или напишите 'авто'.")
            return
        code = uuid.uuid4().hex[:8].upper() if raw.lower() == 'авто' or raw.lower() == 'auto' else raw.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_-]{3,32}", code):
            await message.answer("❌ Код должен состоять из латиницы/цифр и быть длиной 3-32 символа.")
            return
        await state.update_data(promo_code=code)
        await state.set_state(AdminPromoCreate.waiting_for_discount_type)
        await message.answer(
            "Выберите тип скидки:",
            reply_markup=keyboards.create_admin_promo_discount_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_discount_type,
        F.data.in_({"admin_promo_discount_percent", "admin_promo_discount_amount"})
    )
    async def admin_promo_set_discount_type(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        discount_type = 'percent' if callback.data.endswith('percent') else 'amount'
        await state.update_data(discount_type=discount_type)
        await state.set_state(AdminPromoCreate.waiting_for_discount_value)
        prompt = "Введите процент скидки (например, 10.5):" if discount_type == 'percent' else "Введите размер скидки в RUB (например, 150):"
        await callback.message.edit_text(prompt, reply_markup=keyboards.create_admin_cancel_keyboard())

    @admin_router.message(AdminPromoCreate.waiting_for_discount_value)
    async def admin_promo_set_discount_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        discount_type = data.get('discount_type')
        raw = (message.text or '').strip().replace(',', '.')
        try:
            value = float(raw)
        except Exception:
            await message.answer("❌ Введите число.")
            return
        if value <= 0:
            await message.answer("❌ Значение должно быть положительным.")
            return
        if discount_type == 'percent' and value >= 100:
            await message.answer("❌ Процент скидки должен быть меньше 100.")
            return
        await state.update_data(discount_value=value)
        await state.set_state(AdminPromoCreate.waiting_for_total_limit)
        await message.answer(
            "Введите общий лимит активаций или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_limit_keyboard("total")
        )

    @admin_router.message(AdminPromoCreate.waiting_for_total_limit)
    async def admin_promo_set_total_limit(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().lower()
        limit_total: int | None
        if raw in {'0', '∞', 'inf', 'infinity', 'безлимит', 'нет'} or not raw:
            limit_total = None
        else:
            try:
                limit_total = int(raw)
            except Exception:
                await message.answer("❌ Введите целое число или 0 для безлимита.")
                return
            if limit_total <= 0:
                limit_total = None
        await state.update_data(usage_limit_total=limit_total)
        await state.set_state(AdminPromoCreate.waiting_for_per_user_limit)
        await message.answer(
            "Введите лимит на пользователя или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_limit_keyboard("user")
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_total_limit,
        F.data.startswith("admin_promo_limit_total_")
    )
    async def admin_promo_total_limit_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        tail = callback.data.replace("admin_promo_limit_total_", "", 1)
        if tail == "custom":
            await callback.message.edit_text(
                "Введите общий лимит активаций (целое число) или 0/∞ для безлимита:",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        limit_total = None if tail == "inf" else int(tail)
        await state.update_data(usage_limit_total=limit_total)
        await state.set_state(AdminPromoCreate.waiting_for_per_user_limit)
        await callback.message.edit_text(
            "Введите лимит на пользователя или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_limit_keyboard("user")
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_per_user_limit,
        F.data.startswith("admin_promo_limit_user_")
    )
    async def admin_promo_user_limit_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        tail = callback.data.replace("admin_promo_limit_user_", "", 1)
        if tail == "custom":
            await callback.message.edit_text(
                "Введите лимит на пользователя (целое число) или 0/∞ для безлимита:",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        limit_user = None if tail == "inf" else int(tail)
        await state.update_data(usage_limit_per_user=limit_user)
        await state.set_state(AdminPromoCreate.waiting_for_valid_from)
        await callback.message.edit_text(
            "Укажите дату начала действия или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_valid_from_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_per_user_limit)
    async def admin_promo_set_per_user_limit(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip().lower()
        limit_user: int | None
        if raw in {'0', '∞', 'inf', 'infinity', 'безлимит', 'нет'} or not raw:
            limit_user = None
        else:
            try:
                limit_user = int(raw)
            except Exception:
                await message.answer("❌ Введите целое число или 0 для безлимита.")
                return
            if limit_user <= 0:
                limit_user = None
        await state.update_data(usage_limit_per_user=limit_user)
        await state.set_state(AdminPromoCreate.waiting_for_valid_from)
        await message.answer(
            "Укажите дату начала действия (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ). Напишите 'skip', чтобы пропустить:",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_valid_from)
    async def admin_promo_set_valid_from(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            valid_from = _parse_datetime_input(raw)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            return
        await state.update_data(valid_from=valid_from)
        await state.set_state(AdminPromoCreate.waiting_for_valid_until)
        await message.answer(
            "Укажите дату окончания действия или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_valid_until_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_valid_from,
        F.data.in_({
            "admin_promo_valid_from_now",
            "admin_promo_valid_from_today",
            "admin_promo_valid_from_tomorrow",
            "admin_promo_valid_from_skip",
            "admin_promo_valid_from_custom",
        })
    )
    async def admin_promo_valid_from_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        now = datetime.now()
        if callback.data.endswith("custom"):
            await callback.message.edit_text(
                "Укажите дату начала (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ):",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        if callback.data.endswith("skip"):
            valid_from = None
        elif callback.data.endswith("today"):
            valid_from = datetime(now.year, now.month, now.day)
        elif callback.data.endswith("tomorrow"):
            valid_from = datetime(now.year, now.month, now.day) + timedelta(days=1)
        else:
            valid_from = now
        await state.update_data(valid_from=valid_from)
        await state.set_state(AdminPromoCreate.waiting_for_valid_until)
        await callback.message.edit_text(
            "Укажите дату окончания действия или выберите на кнопках:",
            reply_markup=keyboards.create_admin_promo_valid_until_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_valid_until)
    async def admin_promo_set_valid_until(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        try:
            valid_until = _parse_datetime_input(raw)
        except ValueError as e:
            await message.answer(f"❌ {e}")
            return
        data = await state.get_data()
        valid_from = data.get('valid_from')
        if valid_from and valid_until and valid_until <= valid_from:
            await message.answer("❌ Дата окончания должна быть позже даты начала.")
            return
        await state.update_data(valid_until=valid_until)
        await state.set_state(AdminPromoCreate.waiting_for_description)
        await message.answer(
            "Добавьте описание/комментарий или пропустите:",
            reply_markup=keyboards.create_admin_promo_description_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_valid_until,
        F.data.in_({
            "admin_promo_valid_until_plus1d",
            "admin_promo_valid_until_plus7d",
            "admin_promo_valid_until_plus30d",
            "admin_promo_valid_until_skip",
            "admin_promo_valid_until_custom",
        })
    )
    async def admin_promo_valid_until_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("custom"):
            await callback.message.edit_text(
                "Укажите дату окончания (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ):",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return
        if callback.data.endswith("skip"):
            valid_until = None
        else:
            data = await state.get_data()
            base = data.get('valid_from') or datetime.now()
            if callback.data.endswith("plus1d"):
                valid_until = base + timedelta(days=1)
            elif callback.data.endswith("plus7d"):
                valid_until = base + timedelta(days=7)
            else:
                valid_until = base + timedelta(days=30)
        await state.update_data(valid_until=valid_until)
        await state.set_state(AdminPromoCreate.waiting_for_description)
        await callback.message.edit_text(
            "Добавьте описание/комментарий или пропустите:",
            reply_markup=keyboards.create_admin_promo_description_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_description)
    async def admin_promo_description(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        desc = (message.text or '').strip()
        description = None if not desc or desc.lower() in {'skip', 'пропустить', 'нет'} else desc
        await state.update_data(description=description)
        await state.set_state(AdminPromoCreate.waiting_for_segment)
        await message.answer(
            "Ограничить промокод сегментом пользователей?",
            reply_markup=keyboards.create_admin_promo_segment_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_description,
        F.data.in_({"admin_promo_desc_skip", "admin_promo_desc_custom"})
    )
    async def admin_promo_desc_buttons(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("custom"):
            await callback.message.edit_text(
                "Введите описание промокода (опционально) или нажмите Отмена:",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return

        await state.update_data(description=None)
        await state.set_state(AdminPromoCreate.waiting_for_segment)
        await callback.message.edit_text(
            "Ограничить промокод сегментом пользователей?",
            reply_markup=keyboards.create_admin_promo_segment_keyboard()
        )

    async def _show_promo_confirm(message_or_callback, state: FSMContext):
        data = await state.get_data()
        code = data.get('promo_code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        total_limit = data.get('usage_limit_total')
        per_user_limit = data.get('usage_limit_per_user')
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        description = data.get('description')
        segment_type = data.get('segment_type')
        segment_value = data.get('segment_value')
        plan_ids = data.get('applicable_plan_ids')
        if not segment_type:
            segment_text = "без ограничения"
        elif segment_type == "no_active_subscription":
            segment_text = "нет активной подписки"
        elif segment_type == "min_total_spent":
            segment_text = f"сумма покупок ≥ {float(segment_value or 0):.0f} ₽"
        else:
            segment_text = str(segment_type)
        plans_text = "все тарифы" if not plan_ids else ", ".join(str(i) for i in plan_ids)
        summary_lines = [
            "Проверьте данные промокода:",
            f"Код: <code>{code}</code>",
            f"Тип скидки: {'процент' if discount_type == 'percent' else 'фиксированная'}",
            f"Значение: {discount_value:.2f}{'%' if discount_type == 'percent' else ' RUB'}",
            f"Лимит всего: {total_limit if total_limit is not None else 'без ограничений'}",
            f"Лимит на пользователя: {per_user_limit if per_user_limit is not None else 'без ограничений'}",
            f"Действует с: {valid_from.isoformat(' ') if valid_from else '—'}",
            f"Действует до: {valid_until.isoformat(' ') if valid_until else '—'}",
            f"Описание: {description or '—'}",
            f"Тарифы: {plans_text}",
            f"Сегмент: {segment_text}",
        ]
        summary_text = "\n".join(summary_lines)
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Создать", callback_data="admin_promo_confirm")
        builder.button(text="❌ Отмена", callback_data="admin_cancel")
        builder.adjust(1, 1)
        await state.set_state(AdminPromoCreate.confirming)
        target = message_or_callback.message if hasattr(message_or_callback, "message") and hasattr(message_or_callback, "data") else message_or_callback
        edit = getattr(target, "edit_text", None)
        if edit and hasattr(message_or_callback, "data"):
            await target.edit_text(summary_text, reply_markup=builder.as_markup(), parse_mode='HTML')
        else:
            await target.answer(summary_text, reply_markup=builder.as_markup(), parse_mode='HTML')

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_segment,
        F.data.in_({
            "admin_promo_segment_none",
            "admin_promo_segment_no_sub",
            "admin_promo_segment_min_spent",
        })
    )
    async def admin_promo_set_segment(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("none"):
            await state.update_data(segment_type=None, segment_value=None)
            await state.set_state(AdminPromoCreate.waiting_for_plans)
            await callback.message.edit_text(
                "Ограничить промокод тарифами?",
                reply_markup=keyboards.create_admin_promo_plans_keyboard()
            )
            return
        if callback.data.endswith("no_sub"):
            await state.update_data(segment_type="no_active_subscription", segment_value=None)
            await state.set_state(AdminPromoCreate.waiting_for_plans)
            await callback.message.edit_text(
                "Ограничить промокод тарифами?",
                reply_markup=keyboards.create_admin_promo_plans_keyboard()
            )
            return
        await state.update_data(segment_type="min_total_spent")
        await state.set_state(AdminPromoCreate.waiting_for_segment_value)
        await callback.message.edit_text(
            "Введите минимальную сумму покупок в рублях (только оплаченные транзакции, без pending):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_segment_value)
    async def admin_promo_set_segment_value(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or "").strip().replace(",", ".")
        try:
            value = float(raw)
        except Exception:
            await message.answer("❌ Введите число больше 0.")
            return
        if value <= 0:
            await message.answer("❌ Сумма должна быть больше 0.")
            return
        await state.update_data(segment_value=value)
        await state.set_state(AdminPromoCreate.waiting_for_plans)
        await message.answer(
            "Ограничить промокод тарифами?",
            reply_markup=keyboards.create_admin_promo_plans_keyboard()
        )

    @admin_router.callback_query(
        AdminPromoCreate.waiting_for_plans,
        F.data.in_({"admin_promo_plans_all", "admin_promo_plans_custom"})
    )
    async def admin_promo_set_plans(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        if callback.data.endswith("all"):
            await state.update_data(applicable_plan_ids=None)
            await _show_promo_confirm(callback, state)
            return
        await callback.message.edit_text(
            "Введите ID тарифов через запятую (например: 1, 3, 5):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminPromoCreate.waiting_for_plans)
    async def admin_promo_set_plans_custom(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        parts = [p.strip() for p in (message.text or "").replace(";", ",").split(",") if p.strip()]
        if not parts:
            await message.answer("❌ Укажите хотя бы один plan_id или вернитесь и выберите «Все тарифы».")
            return
        ids: list[int] = []
        for part in parts:
            try:
                ids.append(int(part))
            except Exception:
                await message.answer(f"❌ «{part}» не является числом.")
                return
        await state.update_data(applicable_plan_ids=ids)
        await _show_promo_confirm(message, state)

    @admin_router.callback_query(AdminPromoCreate.confirming, F.data == "admin_promo_confirm")
    async def admin_promo_confirm(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        code = data.get('promo_code')
        discount_type = data.get('discount_type')
        discount_value = data.get('discount_value')
        total_limit = data.get('usage_limit_total')
        per_user_limit = data.get('usage_limit_per_user')
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        description = data.get('description')
        kwargs = {
            'code': code,
            'discount_percent': discount_value if discount_type == 'percent' else None,
            'discount_amount': discount_value if discount_type == 'amount' else None,
            'usage_limit_total': total_limit,
            'usage_limit_per_user': per_user_limit,
            'valid_from': valid_from,
            'valid_until': valid_until,
            'created_by': callback.from_user.id,
            'description': description,
            'applicable_plan_ids': data.get('applicable_plan_ids'),
            'segment_type': data.get('segment_type'),
            'segment_value': data.get('segment_value'),
        }
        try:
            ok = create_promo_code(**kwargs)
        except ValueError as e:
            await callback.message.edit_text(f"❌ Не удалось создать промокод: {e}", reply_markup=keyboards.create_admin_promo_menu_keyboard())
            await state.clear()
            return
        if not ok:
            await callback.message.edit_text(
                "❌ Не удалось создать промокод (возможно, код уже существует).",
                reply_markup=keyboards.create_admin_promo_menu_keyboard()
            )
            await state.clear()
            return
        await state.clear()
        await callback.message.edit_text(
            f"✅ Промокод <code>{code}</code> создан!\n\nПередайте его пользователю или опубликуйте в канале.",
            reply_markup=keyboards.create_admin_promo_menu_keyboard(),
            parse_mode='HTML'
        )

    @admin_router.callback_query(F.data == "admin_promo_list")
    async def admin_promo_list(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.update_data(promo_page=0)
        codes = list_promo_codes(include_inactive=True) or []
        text_lines = ["🎟 <b>Доступные промокоды</b>"]
        if not codes:
            text_lines.append("Пока нет созданных промокодов.")
        else:
            for promo in codes[:10]:
                text_lines.append(_format_promo_line(promo))
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=_build_promo_list_keyboard(codes, page=0),
            parse_mode='HTML'
        )

    @admin_router.callback_query(F.data.startswith("admin_promo_page_"))
    async def admin_promo_change_page(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        await callback.answer()
        try:
            page = int(callback.data.split('_')[-1])
        except Exception:
            page = 0
        codes = list_promo_codes(include_inactive=True) or []
        await state.update_data(promo_page=page)
        text_lines = ["🎟 <b>Доступные промокоды</b>"]
        if not codes:
            text_lines.append("Пока нет созданных промокодов.")
        else:
            start = page * 10
            for promo in codes[start:start + 10]:
                text_lines.append(_format_promo_line(promo))
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=_build_promo_list_keyboard(codes, page=page),
            parse_mode='HTML'
        )

    @admin_router.callback_query(F.data.startswith("admin_promo_toggle_"))
    async def admin_promo_toggle(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.")
            return
        code = callback.data.split("admin_promo_toggle_")[-1]
        codes = list_promo_codes(include_inactive=True) or []
        target = next((p for p in codes if (p.get('code') or '').upper() == code.upper()), None)
        if not target:
            await callback.answer("Промокод не найден", show_alert=True)
            return
        new_status = not bool(target.get('is_active'))
        update_promo_code_status(code, is_active=new_status)
        await callback.answer("Статус обновлён")
        page = (await state.get_data()).get('promo_page', 0)
        codes = list_promo_codes(include_inactive=True) or []
        text_lines = ["🎟 <b>Доступные промокоды</b>"]
        if not codes:
            text_lines.append("Пока нет созданных промокодов.")
        else:
            start = page * 10
            for promo in codes[start:start + 10]:
                text_lines.append(_format_promo_line(promo))
        await callback.message.edit_text(
            "\n".join(text_lines),
            reply_markup=_build_promo_list_keyboard(codes, page=page),
            parse_mode='HTML'
        )


    @admin_router.callback_query(F.data == "admin_speedtest")
    async def admin_speedtest_entry(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()

        targets = get_all_ssh_targets() or []
        try:
            await callback.message.edit_text(
                "🔌 <b>SSH цели для Speedtest</b>\nВыберите цель:",
                reply_markup=keyboards.create_admin_ssh_targets_keyboard(targets)
            )
        except Exception:
            await callback.message.answer(
                "🔌 <b>SSH цели для Speedtest</b>\nВыберите цель:",
                reply_markup=keyboards.create_admin_ssh_targets_keyboard(targets)
            )


    @admin_router.callback_query(F.data == "admin_speedtest_ssh_targets")
    async def admin_speedtest_ssh_targets(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        targets = get_all_ssh_targets() or []
        try:
            await callback.message.edit_text(
                "🔌 <b>SSH цели для Speedtest</b>\nВыберите цель:",
                reply_markup=keyboards.create_admin_ssh_targets_keyboard(targets)
            )
        except Exception:
            await callback.message.answer(
                "🔌 <b>SSH цели для Speedtest</b>\nВыберите цель:",
                reply_markup=keyboards.create_admin_ssh_targets_keyboard(targets)
            )


    @admin_router.callback_query(F.data.startswith("admin_speedtest_pick_host_"))
    async def admin_speedtest_run(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        host_name = callback.data.replace("admin_speedtest_pick_host_", "", 1)


        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids
            admin_ids = list({*(get_admin_ids() or []), int(callback.from_user.id)})
        except Exception:
            admin_ids = [int(callback.from_user.id)]
        initiator = _format_user_mention(callback.from_user)
        start_text = f"🚀 Запущен тест скорости для хоста: <b>{host_name}</b>\n(инициатор: {initiator})"
        for aid in admin_ids:
            try:
                await callback.bot.send_message(aid, start_text)
            except Exception:
                pass


        try:
            wait_msg = await callback.message.answer(f"⏳ Выполняю тест скорости для <b>{host_name}</b>…")
        except Exception:
            wait_msg = None


        try:
            result = await speedtest_runner.run_both_for_host(host_name)
        except Exception as e:
            result = {"ok": False, "error": str(e), "details": {}}


        def fmt_part(title: str, d: dict | None) -> str:
            if not d:
                return f"<b>{title}:</b> —"
            if not d.get("ok"):
                return f"<b>{title}:</b> ❌ {d.get('error') or 'ошибка'}"
            ping = d.get('ping_ms')
            down = d.get('download_mbps')
            up = d.get('upload_mbps')
            srv = d.get('server_name') or '—'
            return (f"<b>{title}:</b> ✅\n"
                    f"• ping: {ping if ping is not None else '—'} ms\n"
                    f"• ↓ {down if down is not None else '—'} Mbps\n"
                    f"• ↑ {up if up is not None else '—'} Mbps\n"
                    f"• сервер: {srv}")

        details = result.get('details') or {}
        text_res = (
            f"🏁 Тест скорости завершён для <b>{host_name}</b>\n\n"
            + fmt_part("SSH", details.get('ssh')) + "\n\n"
            + fmt_part("NET", details.get('net'))
        )



        if result.get('ok'):
            logger.info(f"Bot/Admin: спидтест для SSH-цели '{host_name}' завершён успешно")
        else:
            logger.warning(f"Bot/Admin: спидтест для SSH-цели '{host_name}' завершился с ошибкой: {result.get('error')}")


        if result.get('ok'):
            logger.info(f"Bot/Admin: спидтест (legacy) для SSH-цели '{host_name}' завершён успешно")
        else:
            logger.warning(f"Bot/Admin: спидтест (legacy) для SSH-цели '{host_name}' завершился с ошибкой: {result.get('error')}")

        if wait_msg:
            try:
                await wait_msg.edit_text(text_res)
            except Exception:
                await callback.message.answer(text_res)
        else:
            await callback.message.answer(text_res)


        for aid in admin_ids:
            if wait_msg and aid == callback.from_user.id:
                continue
            try:
                await callback.bot.send_message(aid, text_res)
            except Exception:
                pass


    @admin_router.callback_query(F.data.startswith("stt:"))
    async def admin_speedtest_run_target_hashed(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        target_name = _resolve_target_from_hash(callback.data)
        if not target_name:
            await callback.message.answer("❌ Цель не найдена")
            return


        logger.info(f"Bot/Admin: запуск спидтеста для SSH-цели '{target_name}' (инициатор id={callback.from_user.id})")
        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids
            admin_ids = list({*(get_admin_ids() or []), int(callback.from_user.id)})
        except Exception:
            admin_ids = [int(callback.from_user.id)]
        initiator = _format_user_mention(callback.from_user)
        start_text = f"🚀 Запущен тест скорости (SSH-цель): <b>{target_name}</b>\n(инициатор: {initiator})"
        for aid in admin_ids:
            try:
                await callback.bot.send_message(aid, start_text)
            except Exception:
                pass


        try:
            wait_msg = await callback.message.answer(f"⏳ Выполняю тест скорости для SSH-цели <b>{target_name}</b>…")
        except Exception:
            wait_msg = None


        try:
            result = await speedtest_runner.run_and_store_ssh_speedtest_for_target(target_name)
        except Exception as e:
            result = {"ok": False, "error": str(e)}

        if not result.get("ok"):
            text_res = f"🏁 Тест скорости (SSH-цель) завершён для <b>{target_name}</b>\n❌ {result.get('error') or 'ошибка'}"
        else:
            ping = result.get('ping_ms')
            down = result.get('download_mbps')
            up = result.get('upload_mbps')
            srv = result.get('server_name') or '—'
            text_res = (
                f"🏁 Тест скорости (SSH-цель) завершён для <b>{target_name}</b>\n\n"
                f"<b>SSH:</b> ✅\n"
                f"• ping: {ping if ping is not None else '—'} ms\n"
                f"• ↓ {down if down is not None else '—'} Mbps\n"
                f"• ↑ {up if up is not None else '—'} Mbps\n"
                f"• сервер: {srv}"
            )

        if wait_msg:
            try:
                await wait_msg.edit_text(text_res)
            except Exception:
                await callback.message.answer(text_res)
        else:
            await callback.message.answer(text_res)

        for aid in admin_ids:
            if wait_msg and aid == callback.from_user.id:
                continue
            try:
                await callback.bot.send_message(aid, text_res)
            except Exception:
                pass


    @admin_router.callback_query(F.data.startswith("admin_speedtest_pick_target_"))
    async def admin_speedtest_run_target(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        target_name = callback.data.replace("admin_speedtest_pick_target_", "", 1)


        logger.info(f"Bot/Admin: запуск спидтеста (legacy) для SSH-цели '{target_name}' (инициатор id={callback.from_user.id})")
        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids
            admin_ids = list({*(get_admin_ids() or []), int(callback.from_user.id)})
        except Exception:
            admin_ids = [int(callback.from_user.id)]
        initiator = _format_user_mention(callback.from_user)
        start_text = f"🚀 Запущен тест скорости (SSH-цель): <b>{target_name}</b>\n(инициатор: {initiator})"
        for aid in admin_ids:
            try:
                await callback.bot.send_message(aid, start_text)
            except Exception:
                pass


        try:
            wait_msg = await callback.message.answer(f"⏳ Выполняю тест скорости для SSH-цели <b>{target_name}</b>…")
        except Exception:
            wait_msg = None


        try:
            result = await speedtest_runner.run_and_store_ssh_speedtest_for_target(target_name)
        except Exception as e:
            result = {"ok": False, "error": str(e)}


        if not result.get("ok"):
            text_res = f"🏁 Тест скорости (SSH-цель) завершён для <b>{target_name}</b>\n❌ {result.get('error') or 'ошибка'}"
        else:
            ping = result.get('ping_ms')
            down = result.get('download_mbps')
            up = result.get('upload_mbps')
            srv = result.get('server_name') or '—'
            text_res = (
                f"🏁 Тест скорости (SSH-цель) завершён для <b>{target_name}</b>\n\n"
                f"<b>SSH:</b> ✅\n"
                f"• ping: {ping if ping is not None else '—'} ms\n"
                f"• ↓ {down if down is not None else '—'} Mbps\n"
                f"• ↑ {up if up is not None else '—'} Mbps\n"
                f"• сервер: {srv}"
            )


        if wait_msg:
            try:
                await wait_msg.edit_text(text_res)
            except Exception:
                await callback.message.answer(text_res)
        else:
            await callback.message.answer(text_res)


        for aid in admin_ids:
            if wait_msg and aid == callback.from_user.id:
                continue
            try:
                await callback.bot.send_message(aid, text_res)
            except Exception:
                pass


    @admin_router.callback_query(F.data == "admin_speedtest_back_to_users")
    async def admin_speedtest_back(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_menu(callback.message, edit_message=True)


    @admin_router.callback_query(F.data == "admin_speedtest_run_all")
    async def admin_speedtest_run_all(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()

        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids
            admin_ids = list({*(get_admin_ids() or []), int(callback.from_user.id)})
        except Exception:
            admin_ids = [int(callback.from_user.id)]
        initiator = _format_user_mention(callback.from_user)
        start_text = f"🚀 Запущен тест скорости для всех хостов\n(инициатор: {initiator})"
        for aid in admin_ids:
            try:
                await callback.bot.send_message(aid, start_text)
            except Exception:
                pass

        hosts = get_all_hosts() or []
        summary_lines = []
        for h in hosts:
            name = h.get('host_name')
            try:
                res = await speedtest_runner.run_both_for_host(name)
                ok = res.get('ok')
                det = res.get('details') or {}
                dm = det.get('ssh', {}).get('download_mbps') or det.get('net', {}).get('download_mbps')
                um = det.get('ssh', {}).get('upload_mbps') or det.get('net', {}).get('upload_mbps')
                summary_lines.append(f"• {name}: {'✅' if ok else '❌'} ↓ {dm or '—'} ↑ {um or '—'}")
            except Exception as e:
                summary_lines.append(f"• {name}: ❌ {e}")
        text = "🏁 Тест для всех завершён:\n" + "\n".join(summary_lines)
        await callback.message.answer(text)
        for aid in admin_ids:

            if aid == callback.from_user.id or aid == callback.message.chat.id:
                continue
            try:
                await callback.bot.send_message(aid, text)
            except Exception:
                pass


    @admin_router.callback_query(F.data == "admin_speedtest_run_all_targets")
    async def admin_speedtest_run_all_targets(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()

        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids
            admin_ids = list({*(get_admin_ids() or []), int(callback.from_user.id)})
        except Exception:
            admin_ids = [int(callback.from_user.id)]
        initiator = _format_user_mention(callback.from_user)
        start_text = f"🚀 Запущен тест скорости для всех SSH-целей\n(инициатор: {initiator})"
        logger.info(f"Bot/Admin: запуск спидтеста ДЛЯ ВСЕХ SSH-целей (инициатор id={callback.from_user.id})")
        for aid in admin_ids:
            try:
                await callback.bot.send_message(aid, start_text)
            except Exception:
                pass

        targets = get_all_ssh_targets() or []
        summary_lines = []
        ok_total = 0
        for t in targets:
            name = (t.get('target_name') or '').strip()
            if not name:
                continue
            try:
                res = await speedtest_runner.run_and_store_ssh_speedtest_for_target(name)
                ok = bool(res.get('ok'))
                dm = res.get('download_mbps')
                um = res.get('upload_mbps')
                summary_lines.append(f"• {name}: {'✅' if ok else '❌'} ↓ {dm or '—'} ↑ {um or '—'}")
                if ok:
                    ok_total += 1
            except Exception as e:
                summary_lines.append(f"• {name}: ❌ {e}")
        text = "🏁 SSH-цели: тест для всех завершён:\n" + ("\n".join(summary_lines) if summary_lines else "(нет целей)")
        logger.info(f"Bot/Admin: завершён спидтест ДЛЯ ВСЕХ SSH-целей: ок={ok_total}, всего={len(targets)}")
        await callback.message.answer(text)
        for aid in admin_ids:
            if aid == callback.from_user.id or aid == callback.message.chat.id:
                continue
            try:
                await callback.bot.send_message(aid, text)
            except Exception:
                pass


    @admin_router.callback_query(F.data == "admin_backup_db")
    async def admin_backup_db(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            wait = await callback.message.answer("⏳ Создаю бэкап базы данных…")
        except Exception:
            wait = None
        zip_path = backup_manager.create_backup_file()
        if not zip_path:
            if wait:
                await wait.edit_text("❌ Не удалось создать бэкап БД")
            else:
                await callback.message.answer("❌ Не удалось создать бэкап БД")
            return

        try:
            sent = await backup_manager.send_backup_to_admins(callback.bot, zip_path)
        except Exception:
            sent = 0
        txt = f"✅ Бэкап создан: <b>{zip_path.name}</b>\nОтправлено администраторам: {sent}"
        if wait:
            try:
                await wait.edit_text(txt)
            except Exception:
                await callback.message.answer(txt)
        else:
            await callback.message.answer(txt)


    class AdminRestoreDB(StatesGroup):
        waiting_file = State()

    @admin_router.callback_query(F.data == "admin_restore_db")
    async def admin_restore_db_prompt(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminRestoreDB.waiting_file)
        kb = InlineKeyboardBuilder()
        kb.button(text="❌ Отмена", callback_data="admin_cancel")
        kb.adjust(1)
        text = (
            "⚠️ <b>Восстановление базы данных</b>\n\n"
            "Отправьте файл <code>.zip</code> с бэкапом или файл <code>.db</code> в ответ на это сообщение.\n"
            "Текущая БД предварительно будет сохранена."
        )
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())

    @admin_router.message(AdminRestoreDB.waiting_file)
    async def admin_restore_db_receive(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        doc = message.document
        if not doc:
            await message.answer("❌ Пришлите файл .zip или .db")
            return
        filename = (doc.file_name or "uploaded.db").lower()
        if not (filename.endswith('.zip') or filename.endswith('.db')):
            await message.answer("❌ Поддерживаются только файлы .zip или .db")
            return
        try:
            ts = datetime.now().strftime('%Y%m%d-%H%M%S')
            dest = backup_manager.BACKUPS_DIR / f"uploaded-{ts}-{filename}"
            dest.parent.mkdir(parents=True, exist_ok=True)
            await message.bot.download(doc, destination=dest)
        except Exception as e:
            await message.answer(f"❌ Не удалось скачать файл: {e}")
            return
        ok = backup_manager.restore_from_file(dest)
        await state.clear()
        if ok:
            await message.answer("✅ Восстановление выполнено успешно.\nБот и панель продолжают работу с новой БД.")
        else:
            await message.answer("❌ Восстановление не удалось. Проверьте файл и повторите.")


    @admin_router.callback_query(F.data.startswith("admin_speedtest_autoinstall_"))
    async def admin_speedtest_autoinstall(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        host_name = callback.data.replace("admin_speedtest_autoinstall_", "", 1)
        try:
            wait = await callback.message.answer(f"🛠 Пытаюсь установить speedtest на <b>{host_name}</b>…")
        except Exception:
            wait = None
        from shop_bot.data_manager.speedtest_runner import auto_install_speedtest_on_host
        try:
            res = await auto_install_speedtest_on_host(host_name)
        except Exception as e:
            res = {"ok": False, "log": f"Ошибка: {e}"}
        text = ("✅ Автоустановка завершена успешно" if res.get("ok") else "❌ Автоустановка завершилась с ошибкой")
        text += f"\n<pre>{(res.get('log') or '')[:3500]}</pre>"
        if wait:
            try:
                await wait.edit_text(text)
            except Exception:
                await callback.message.answer(text)


    @admin_router.callback_query(F.data.startswith("admin_speedtest_autoinstall_target_"))
    async def admin_speedtest_autoinstall_target(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        target_name = callback.data.replace("admin_speedtest_autoinstall_target_", "", 1)
        try:
            wait = await callback.message.answer(f"🛠 Пытаюсь установить speedtest на SSH-цели <b>{target_name}</b>…")
        except Exception:
            wait = None
        from shop_bot.data_manager.speedtest_runner import auto_install_speedtest_on_target
        logger.info(f"Bot/Admin: автоустановка speedtest на SSH-цели '{target_name}' (инициатор id={callback.from_user.id})")
        try:
            res = await auto_install_speedtest_on_target(target_name)
        except Exception as e:
            res = {"ok": False, "log": f"Ошибка: {e}"}
        text = ("✅ Автоустановка завершена успешно" if res.get("ok") else "❌ Автоустановка завершилась с ошибкой")
        text += f"\n<pre>{(res.get('log') or '')[:3500]}</pre>"
        if res.get('ok'):
            logger.info(f"Bot/Admin: автоустановка завершена успешно для '{target_name}'")
        else:
            logger.warning(f"Bot/Admin: автоустановка завершилась с ошибкой для '{target_name}'")
        if wait:
            try:
                await wait.edit_text(text)
            except Exception:
                await callback.message.answer(text)
        else:
            await callback.message.answer(text)


    @admin_router.callback_query(F.data.startswith("stti:"))
    async def admin_speedtest_autoinstall_target_hashed(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        target_name = _resolve_target_from_hash(callback.data)
        if not target_name:
            await callback.message.answer("❌ Цель не найдена")
            return
        try:
            wait = await callback.message.answer(f"🛠 Пытаюсь установить speedtest на SSH-цели <b>{target_name}</b>…")
        except Exception:
            wait = None
        from shop_bot.data_manager.speedtest_runner import auto_install_speedtest_on_target
        try:
            res = await auto_install_speedtest_on_target(target_name)
        except Exception as e:
            res = {"ok": False, "log": f"Ошибка: {e}"}
        text = ("✅ Автоустановка завершена успешно" if res.get("ok") else "❌ Автоустановка завершилась с ошибкой")
        text += f"\n<pre>{(res.get('log') or '')[:3500]}</pre>"
        if wait:
            try:
                await wait.edit_text(text)
            except Exception:
                await callback.message.answer(text)
        else:
            await callback.message.answer(text)



    

    class AdminUserSearch(StatesGroup):
        waiting_for_query = State()

    @admin_router.callback_query(F.data.startswith("admin_users"))
    async def admin_users_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()

        # Обработка кнопки поиска пользователя
        if callback.data == "admin_users_search":
            await state.set_state(AdminUserSearch.waiting_for_query)
            await callback.message.edit_text(
                "Введите ID пользователя или его @username для поиска:\n\n"
                "Примеры: 123456789 или @username",
                reply_markup=keyboards.create_admin_cancel_keyboard()
            )
            return

        # Открытие списка пользователей / переключение страниц
        await state.clear()
        users = get_all_users()
        page = 0
        if callback.data.startswith("admin_users_page_"):
            try:
                page = int(callback.data.split("_")[-1])
            except Exception:
                page = 0
        await callback.message.edit_text(
            "👥 <b>Пользователи</b>",
            reply_markup=keyboards.create_admin_users_keyboard(users, page=page)
        )


    @admin_router.message(AdminUserSearch.waiting_for_query)
    async def admin_users_search_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        raw = (message.text or "").strip()
        if not raw:
            await message.answer("Введите ID пользователя или его @username, либо нажмите Отмена.")
            return

        users = get_all_users() or []
        matches: list[dict] = []

        # Поиск по числовому ID
        if raw.isdigit():
            try:
                target_id = int(raw)
            except Exception:
                target_id = None
            else:
                if target_id is not None:
                    user = get_user(target_id)
                    if user:
                        matches = [user]

        # Поиск по username
        if not matches and not raw.isdigit():
            uname = raw.lstrip("@").lower()
            for u in users:
                uname_u = (u.get("username") or "").lstrip("@").lower()
                if uname_u and (uname_u == uname or uname in uname_u):
                    matches.append(u)

        # Дополнительный поиск по части ID
        if not matches and not raw.isdigit():
            for u in users:
                uid = str(u.get("telegram_id") or u.get("user_id") or u.get("id") or "")
                if uid and raw in uid:
                    matches.append(u)

        if not matches:
            await message.answer("❌ Пользователь не найден. Отправьте другой ID/username или нажмите Отмена.")
            return

        await state.clear()

        # Если найден один пользователь — показываем карточку
        if len(matches) == 1:
            u = matches[0]
            user_id = int(u.get("telegram_id") or u.get("user_id") or u.get("id"))
            user = get_user(user_id) or u

            if user.get("username"):
                uname = user.get("username").lstrip("@")
                user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
            else:
                user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"

            is_banned = user.get("is_banned", False)
            total_spent = user.get("total_spent", 0)
            balance = user.get("balance", 0)
            referral_balance = user.get("referral_balance", 0)
            referred_by = user.get("referred_by")
            keys = get_keys_for_user(user_id)
            keys_count = len(keys)

            text = (
                f"👤 <b>Пользователь {user_id}</b>\n\n"
                f"Имя пользователя: {user_tag}\n"
                f"Всего потратил: {float(total_spent):.2f} RUB\n"
                f"Баланс: {float(balance):.2f} RUB\n"
                f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
                f"Забанен: {'да' if is_banned else 'нет'}\n"
                f"Приглашён: {referred_by if referred_by else '—'}\n"
                f"Ключей: {keys_count}"
            )

            await message.answer(
                text,
                reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=is_banned)
            )
        else:
            # Если найдено несколько пользователей — показываем список с кнопками
            await message.answer(
                f"Найдено пользователей: {len(matches)}",
                reply_markup=keyboards.create_admin_users_keyboard(matches, page=0)
            )

    @admin_router.callback_query(F.data.startswith("admin_view_user_"))
    async def admin_view_user_handler(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        user = get_user(user_id)
        if not user:
            await callback.message.answer("❌ Пользователь не найден")
            return

        username = user.get('username') or '—'

        if user.get('username'):
            uname = user.get('username').lstrip('@')
            user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
        else:
            user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"
        is_banned = user.get('is_banned', False)
        total_spent = user.get('total_spent', 0)
        balance = user.get('balance', 0)
        referral_balance = user.get('referral_balance', 0)
        referred_by = user.get('referred_by')
        keys = get_keys_for_user(user_id)
        keys_count = len(keys)
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"Имя пользователя: {user_tag}\n"
            f"Всего потратил: {float(total_spent):.2f} RUB\n"
            f"Баланс: {float(balance):.2f} RUB\n"
            f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
            f"Забанен: {'да' if is_banned else 'нет'}\n"
            f"Приглашён: {referred_by if referred_by else '—'}\n"
            f"Ключей: {keys_count}"
        )
        await callback.message.edit_text(
            text,
            reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=is_banned)
        )


    @admin_router.callback_query(F.data.startswith("admin_ban_user_"))
    async def admin_ban_user(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        try:
            ban_user(user_id)
            await callback.message.answer(f"🚫 Пользователь {user_id} забанен")
            try:

                from shop_bot.data_manager.remnawave_repository import get_setting as _get_setting
                support = (_get_setting("support_bot_username") or _get_setting("support_user") or "").strip()
                kb = InlineKeyboardBuilder()
                url = None
                if support:
                    if support.startswith("@"):
                        url = f"tg://resolve?domain={support[1:]}"
                    elif support.startswith("tg://"):
                        url = support
                    elif support.startswith("http://") or support.startswith("https://"):
                        try:
                            part = support.split("/")[-1].split("?")[0]
                            if part:
                                url = f"tg://resolve?domain={part}"
                        except Exception:
                            url = support
                    else:
                        url = f"tg://resolve?domain={support}"
                if url:
                    kb.button(text="🆘 Написать в поддержку", url=url)
                else:
                    kb.button(text="🆘 Поддержка", callback_data="show_help")
                await callback.bot.send_message(
                    user_id,
                    "🚫 Ваш аккаунт заблокирован администратором. Если это ошибка — напишите в поддержку.",
                    reply_markup=kb.as_markup()
                )
            except Exception:
                pass
        except Exception as e:
            await callback.message.answer(f"❌ Не удалось забанить пользователя: {e}")
            return

        user = get_user(user_id) or {}
        username = user.get('username') or '—'
        if user.get('username'):
            uname = user.get('username').lstrip('@')
            user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
        else:
            user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"
        total_spent = user.get('total_spent', 0)
        balance = user.get('balance', 0)
        referral_balance = user.get('referral_balance', 0)
        referred_by = user.get('referred_by')
        keys = get_keys_for_user(user_id)
        keys_count = len(keys)
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"Имя пользователя: {user_tag}\n"
            f"Всего потратил: {float(total_spent):.2f} RUB\n"
            f"Баланс: {float(balance):.2f} RUB\n"
            f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
            f"Забанен: да\n"
            f"Приглашён: {referred_by if referred_by else '—'}\n"
            f"Ключей: {keys_count}"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=True)
            )
        except Exception:
            pass


    @admin_router.callback_query(F.data == "admin_admins_menu")
    async def admin_admins_menu_entry(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            "👮 <b>Управление администраторами</b>",
            reply_markup=keyboards.create_admins_menu_keyboard()
        )

    @admin_router.callback_query(F.data == "admin_view_admins")
    async def admin_view_admins(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids
            ids = list(get_admin_ids() or [])
        except Exception:
            ids = []
        if not ids:
            text = "📋 Список администраторов пуст."
        else:
            lines = []
            for aid in ids:
                try:
                    u = get_user(int(aid)) or {}
                except Exception:
                    u = {}
                uname = (u.get('username') or '').strip()
                if uname:
                    uname_clean = uname.lstrip('@')
                    tag = f"<a href='https://t.me/{uname_clean}'>@{uname_clean}</a>"
                else:
                    tag = f"<a href='tg://user?id={aid}'>Профиль</a>"
                lines.append(f"• ID: {aid} — {tag}")
            text = "📋 <b>Администраторы</b>:\n" + "\n".join(lines)

        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Назад", callback_data="admin_admins_menu")
        kb.button(text="⬅️ В админ-меню", callback_data="admin_menu")
        kb.adjust(1, 1)
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())

    @admin_router.callback_query(F.data.startswith("admin_unban_user_"))
    async def admin_unban_user(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        try:
            unban_user(user_id)
            await callback.message.answer(f"✅ Пользователь {user_id} разбанен")
            try:

                kb = InlineKeyboardBuilder()
                kb.row(keyboards.get_main_menu_button())
                await callback.bot.send_message(
                    user_id,
                    "✅ Доступ к аккаунту восстановлен администратором.",
                    reply_markup=kb.as_markup()
                )
            except Exception:
                pass
        except Exception as e:
            await callback.message.answer(f"❌ Не удалось разбанить пользователя: {e}")
            return

        user = get_user(user_id) or {}
        username = user.get('username') or '—'

        if user.get('username'):
            uname = user.get('username').lstrip('@')
            user_tag = f"<a href='https://t.me/{uname}'>@{uname}</a>"
        else:
            user_tag = f"<a href='tg://user?id={user_id}'>Профиль</a>"
        total_spent = user.get('total_spent', 0)
        balance = user.get('balance', 0)
        referral_balance = user.get('referral_balance', 0)
        referred_by = user.get('referred_by')
        keys = get_keys_for_user(user_id)
        keys_count = len(keys)
        text = (
            f"👤 <b>Пользователь {user_id}</b>\n\n"
            f"Имя пользователя: {user_tag}\n"
            f"Всего потратил: {float(total_spent):.2f} RUB\n"
            f"Баланс: {float(balance):.2f} RUB\n"
            f"Реф. баланс (заработок): {float(referral_balance or 0):.2f} RUB\n"
            f"Забанен: нет\n"
            f"Приглашён: {referred_by if referred_by else '—'}\n"
            f"Ключей: {keys_count}"
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboards.create_admin_user_actions_keyboard(user_id, is_banned=False)
            )
        except Exception:
            pass



    @admin_router.callback_query(F.data.startswith("admin_delete_user_"))
    async def admin_delete_user(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return

        try:
            success = delete_user_completely(user_id)
        except Exception:
            logger.exception("Failed to delete user %s completely", user_id)
            success = False

        if success:
            await callback.message.answer(f"🗑 Пользователь {user_id} и все связанные с ним данные удалены.")
        else:
            await callback.message.answer("❌ Не удалось удалить пользователя. Подробности см. в логах сервера.")

    @admin_router.callback_query(F.data.startswith("admin_user_keys_"))
    async def admin_user_keys(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        await callback.answer()
        
        # Разбираем callback_data. Формат может быть:
        # 1. admin_user_keys_12345 (открытие списка)
        # 2. admin_user_keys_12345_1 (переход по страницам)
        parts = callback.data.split("_")
        try:
            user_id = int(parts[3]) # Индекс 3 — это ID пользователя
            page = int(parts[4]) if len(parts) > 4 else 0 # Индекс 4 — это страница
        except (IndexError, ValueError):
            await callback.message.answer("❌ Ошибка в данных запроса")
            return

        keys = get_keys_for_user(user_id)
        
        # Редактируем сообщение, подставляя новую страницу
        await callback.message.edit_text(
            f"🔑 Ключи пользователя {user_id}:" if keys else f"У пользователя {user_id} нет ключей.",
            reply_markup=keyboards.create_admin_user_keys_keyboard(user_id, keys, page=page)
        )

    @admin_router.callback_query(F.data.startswith("admin_user_referrals_"))
    async def admin_user_referrals(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        inviter = get_user(user_id)
        if not inviter:
            await callback.message.answer("❌ Пользователь не найден")
            return
        refs = get_referrals_for_user(user_id) or []
        ref_count = len(refs)
        try:
            total_ref_earned = float(get_referral_balance_all(user_id) or 0)
        except Exception:
            total_ref_earned = 0.0

        max_items = 30
        lines = []
        for r in refs[:max_items]:
            rid = r.get('telegram_id')
            uname = r.get('username') or '—'
            rdate = r.get('registration_date') or '—'
            spent = float(r.get('total_spent') or 0)
            lines.append(f"• @{uname} (ID: {rid}) — рег: {rdate}, потратил: {spent:.2f} RUB")
        more_suffix = "\n… и ещё {}".format(ref_count - max_items) if ref_count > max_items else ""
        text = (
            f"🤝 <b>Рефералы пользователя {user_id}</b>\n\n"
            f"Всего приглашено: {ref_count}\n"
            f"Заработано по рефералке (всего): {total_ref_earned:.2f} RUB\n\n"
            + ("\n".join(lines) if lines else "Пока нет рефералов")
            + more_suffix
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ К пользователю", callback_data=f"admin_view_user_{user_id}")
        kb.button(text="⬅️ В админ-меню", callback_data="admin_menu")
        kb.adjust(1, 1)
        try:
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())

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


    class AdminAddAdmin(StatesGroup):
        waiting_for_input = State()

    @admin_router.callback_query(F.data == "admin_add_admin")
    async def admin_add_admin_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminAddAdmin.waiting_for_input)
        await callback.message.edit_text(
            "Введите ID пользователя или его @username, которого нужно сделать администратором:\n\n"
            "Примеры: 123456789 или @username",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminAddAdmin.waiting_for_input)
    async def admin_add_admin_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        target_id: int | None = None

        if raw.isdigit():
            try:
                target_id = int(raw)
            except Exception:
                target_id = None

        if target_id is None and raw.startswith('@'):
            uname = raw.lstrip('@')

            try:
                chat = await message.bot.get_chat(raw)
                target_id = int(chat.id)
            except Exception:
                target_id = None

            if target_id is None:
                try:
                    chat = await message.bot.get_chat(uname)
                    target_id = int(chat.id)
                except Exception:
                    target_id = None

            if target_id is None:
                try:
                    users = get_all_users() or []
                    uname_low = uname.lower()
                    for u in users:
                        u_un = (u.get('username') or '').lstrip('@').lower()
                        if u_un and u_un == uname_low:
                            target_id = int(u.get('telegram_id') or u.get('user_id') or u.get('id'))
                            break
                except Exception:
                    target_id = None
        if target_id is None:
            await message.answer("❌ Не удалось распознать ID/username. Отправьте корректное значение или нажмите Отмена.")
            return

        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids, update_setting
            ids = set(get_admin_ids())
            ids.add(int(target_id))

            ids_str = ",".join(str(i) for i in sorted(ids))
            update_setting("admin_telegram_ids", ids_str)
            await message.answer(f"✅ Пользователь {target_id} добавлен в администраторы.")
        except Exception as e:
            await message.answer(f"❌ Ошибка при сохранении: {e}")
        await state.clear()

        try:
            await show_admin_menu(message)
        except Exception:
            pass


    class AdminRemoveAdmin(StatesGroup):
        waiting_for_input = State()

    @admin_router.callback_query(F.data == "admin_remove_admin")
    async def admin_remove_admin_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminRemoveAdmin.waiting_for_input)
        await callback.message.edit_text(
            "Введите ID пользователя или его @username, которого нужно снять из админов:\n\n"
            "Примеры: 123456789 или @username",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminRemoveAdmin.waiting_for_input)
    async def admin_remove_admin_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        raw = (message.text or '').strip()
        target_id: int | None = None

        if raw.isdigit():
            try:
                target_id = int(raw)
            except Exception:
                target_id = None

        if target_id is None:
            uname = raw.lstrip('@')

            try:
                chat = await message.bot.get_chat(raw)
                target_id = int(chat.id)
            except Exception:
                target_id = None

            if target_id is None and uname:
                try:
                    chat = await message.bot.get_chat(uname)
                    target_id = int(chat.id)
                except Exception:
                    target_id = None

            if target_id is None and uname:
                try:
                    users = get_all_users() or []
                    uname_low = uname.lower()
                    for u in users:
                        u_un = (u.get('username') or '').lstrip('@').lower()
                        if u_un and u_un == uname_low:
                            target_id = int(u.get('telegram_id') or u.get('user_id') or u.get('id'))
                            break
                except Exception:
                    target_id = None
        if target_id is None:
            await message.answer("❌ Не удалось распознать ID/username. Отправьте корректное значение или нажмите Отмена.")
            return

        try:
            from shop_bot.data_manager.remnawave_repository import get_admin_ids, update_setting
            ids = set(get_admin_ids())
            if target_id not in ids:
                await message.answer(f"ℹ️ Пользователь {target_id} не является администратором.")
                await state.clear()
                try:
                    await show_admin_menu(message)
                except Exception:
                    pass
                return
            if len(ids) <= 1:
                await message.answer("❌ Нельзя снять последнего администратора.")
                return
            ids.discard(int(target_id))
            ids_str = ",".join(str(i) for i in sorted(ids))
            update_setting("admin_telegram_ids", ids_str)
            await message.answer(f"✅ Пользователь {target_id} снят с администраторов.")
        except Exception as e:
            await message.answer(f"❌ Ошибка при сохранении: {e}")
        await state.clear()

        try:
            await show_admin_menu(message)
        except Exception:
            pass


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




    class AdminGiftKey(StatesGroup):
        picking_user = State()
        picking_host = State()
        picking_days = State()

    @admin_router.callback_query(F.data == "admin_gift_key")
    async def admin_gift_key_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        users = get_all_users()
        await state.clear()
        await state.set_state(AdminGiftKey.picking_user)
        await callback.message.edit_text(
            "🎁 Выдача подарочного ключа\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=0, action="gift")
        )


    @admin_router.callback_query(F.data.startswith("admin_gift_key_"))
    async def admin_gift_key_for_user(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        await state.clear()
        await state.update_data(target_user_id=user_id)
        hosts = get_all_hosts()
        await state.set_state(AdminGiftKey.picking_host)
        await callback.message.edit_text(
            f"👤 Пользователь {user_id}. Выберите сервер:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="gift")
        )

    @admin_router.callback_query(AdminGiftKey.picking_user, F.data.startswith("admin_gift_pick_user_page_"))
    async def admin_gift_pick_user_page(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            page = int(callback.data.split("_")[-1])
        except Exception:
            page = 0
        users = get_all_users()
        await callback.message.edit_text(
            "🎁 Выдача подарочного ключа\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=page, action="gift")
        )

    @admin_router.callback_query(AdminGiftKey.picking_user, F.data.startswith("admin_gift_pick_user_"))
    async def admin_gift_pick_user(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        await state.update_data(target_user_id=user_id)
        hosts = get_all_hosts()
        await state.set_state(AdminGiftKey.picking_host)
        await callback.message.edit_text(
            f"👤 Пользователь {user_id}. Выберите сервер:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="gift")
        )

    @admin_router.callback_query(AdminGiftKey.picking_host, F.data == "admin_gift_back_to_users")
    async def admin_gift_back_to_users(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        users = get_all_users()
        await state.set_state(AdminGiftKey.picking_user)
        await callback.message.edit_text(
            "🎁 Выдача подарочного ключа\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=0, action="gift")
        )

    @admin_router.callback_query(AdminGiftKey.picking_host, F.data.startswith("admin_gift_pick_host_"))
    async def admin_gift_pick_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        host_name = callback.data.split("admin_gift_pick_host_")[-1]
        await state.update_data(host_name=host_name)
        await state.set_state(AdminGiftKey.picking_days)
        await callback.message.edit_text(
            f"🌍 Сервер: {host_name}. Введите срок действия ключа в днях (целое число):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.callback_query(AdminGiftKey.picking_days, F.data == "admin_gift_back_to_hosts")
    async def admin_gift_back_to_hosts(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        user_id = int(data.get('target_user_id'))
        hosts = get_all_hosts()
        await state.set_state(AdminGiftKey.picking_host)
        await callback.message.edit_text(
            f"👤 Пользователь {user_id}. Выберите сервер:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="gift")
        )
    @admin_router.message(AdminGiftKey.picking_days)
    async def admin_gift_pick_days(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        user_id = int(data.get('target_user_id'))
        host_name = data.get('host_name')
        try:
            days = int(message.text.strip())
        except Exception:
            await message.answer("❌ Введите целое число дней")
            return
        if days <= 0:
            await message.answer("❌ Срок должен быть положительным")
            return

        user = get_user(user_id) or {}
        try:
            generated_email = rw_repo.generate_key_email_for_user(user_id)
        except Exception:
            generated_email = f"{user_id}-{int(time.time())}@bot.local"


        try:
            host_resp = await create_or_update_key_on_host(host_name, generated_email, days_to_add=days)
        except Exception as e:
            host_resp = None
            logging.error(f"Gift flow: failed to create client on host '{host_name}' for user {user_id}: {e}")

        if not host_resp or not host_resp.get("client_uuid") or not host_resp.get("expiry_timestamp_ms"):
            await message.answer("❌ Не удалось выдать ключ на сервере. Проверьте настройки хоста и доступность панели.")
            await state.clear()
            await show_admin_menu(message)
            return

        client_uuid = host_resp["client_uuid"]
        expiry_ms = int(host_resp["expiry_timestamp_ms"])
        connection_link = host_resp.get("connection_string")

        key_id = rw_repo.record_key_from_payload(
            user_id=user_id,
            payload=host_resp,
            host_name=host_name,
        )
        if key_id:
            username_readable = (user.get('username') or '').strip()
            user_part = f"{user_id} (@{username_readable})" if username_readable else f"{user_id}"
            text_admin = (
                f"✅ 🎁 Подарочный ключ #{key_id} выдан пользователю {user_part} (сервер: {host_name}, {days} дн.)\n"
                f"Email: {generated_email}"
            )
            await message.answer(text_admin)
            try:
                notify_text = (
                    f"🎁 Администратор выдал вам подарочный ключ #{key_id}\n"
                    f"Сервер: {host_name}\n"
                    f"Срок: {days} дн.\n"
                )
                if connection_link:
                    cs = html_escape.escape(connection_link)
                    notify_text += f"\n🔗 Подписка:\n<pre><code>{cs}</code></pre>"
                await message.bot.send_message(user_id, notify_text, parse_mode='HTML', disable_web_page_preview=True)
            except Exception:
                pass
        else:
            await message.answer("❌ Не удалось сохранить ключ в базе данных.")
        await state.clear()
        await show_admin_menu(message)




    class AdminMainRefill(StatesGroup):
        waiting_for_pair = State()
        waiting_for_amount = State()

    @admin_router.callback_query(F.data == "admin_add_balance")
    async def admin_add_balance_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        users = get_all_users()
        await callback.message.edit_text(
            "➕ Начисление баланса\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=0, action="add_balance")
        )

    @admin_router.callback_query(F.data.startswith("admin_add_balance_"))
    async def admin_add_balance_user(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        await state.update_data(target_user_id=user_id)
        await state.set_state(AdminMainRefill.waiting_for_amount)
        await callback.message.edit_text(
            f"Пользователь {user_id}. Введите сумму начисления (в рублях):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )


    @admin_router.callback_query(F.data.startswith("admin_add_balance_pick_user_page_"))
    async def admin_add_balance_pick_user_page(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            page = int(callback.data.split("_")[-1])
        except Exception:
            page = 0
        users = get_all_users()
        await callback.message.edit_text(
            "➕ Начисление баланса\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=page, action="add_balance")
        )


    @admin_router.callback_query(F.data.startswith("admin_add_balance_pick_user_"))
    async def admin_add_balance_pick_user(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        await state.update_data(target_user_id=user_id)
        await state.set_state(AdminMainRefill.waiting_for_amount)
        await callback.message.edit_text(
            f"Пользователь {user_id}. Введите сумму начисления (в рублях):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminMainRefill.waiting_for_amount)
    async def handle_main_amount(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        user_id = int(data.get('target_user_id'))
        try:
            amount = float(message.text.strip().replace(',', '.'))
        except Exception:
            await message.answer("❌ Введите число — сумму в рублях")
            return
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        try:
            ok = add_to_balance(user_id, amount)
            if ok:
                await message.answer(f"✅ Начислено {amount:.2f} RUB на баланс пользователю {user_id}")
                try:
                    await message.bot.send_message(user_id, f"💰 Вам начислено {amount:.2f} RUB на баланс администратором.")
                except Exception:
                    pass
            else:
                await message.answer("❌ Пользователь не найден или ошибка БД")
        except Exception as e:
            await message.answer(f"❌ Ошибка начисления: {e}")
        await state.clear()
        await show_admin_menu(message)


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


    @admin_router.callback_query(F.data == "noop")
    async def admin_noop(callback: types.CallbackQuery):
        await callback.answer()

    @admin_router.callback_query(F.data == "admin_cancel")
    async def admin_cancel_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Отменено")
        await state.clear()
        await show_admin_menu(callback.message, edit_message=True)


    class AdminMainDeduct(StatesGroup):
        waiting_for_amount = State()


    @admin_router.callback_query(F.data == "admin_deduct_balance")
    async def admin_deduct_balance_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        users = get_all_users()
        await callback.message.edit_text(
            "➖ Списание баланса\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=0, action="deduct_balance")
        )


    @admin_router.callback_query(F.data.startswith("admin_deduct_balance_"))
    async def admin_deduct_balance_user(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        await state.update_data(target_user_id=user_id)
        await state.set_state(AdminMainDeduct.waiting_for_amount)
        await callback.message.edit_text(
            f"Пользователь {user_id}. Введите сумму списания (в рублях):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )


    @admin_router.callback_query(F.data.startswith("admin_deduct_balance_pick_user_page_"))
    async def admin_deduct_balance_pick_user_page(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            page = int(callback.data.split("_")[-1])
        except Exception:
            page = 0
        users = get_all_users()
        await callback.message.edit_text(
            "➖ Списание баланса\n\nВыберите пользователя:",
            reply_markup=keyboards.create_admin_users_pick_keyboard(users, page=page, action="deduct_balance")
        )


    @admin_router.callback_query(F.data.startswith("admin_deduct_balance_pick_user_"))
    async def admin_deduct_balance_pick_user(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            user_id = int(callback.data.split("_")[-1])
        except Exception:
            await callback.message.answer("❌ Неверный формат user_id")
            return
        await state.update_data(target_user_id=user_id)
        await state.set_state(AdminMainDeduct.waiting_for_amount)
        await callback.message.edit_text(
            f"Пользователь {user_id}. Введите сумму списания (в рублях):",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminMainDeduct.waiting_for_amount)
    async def handle_deduct_amount(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await state.get_data()
        user_id = int(data.get('target_user_id'))
        try:
            amount = float(message.text.strip().replace(',', '.'))
        except Exception:
            await message.answer("❌ Введите число — сумму в рублях")
            return
        if amount <= 0:
            await message.answer("❌ Сумма должна быть положительной")
            return
        try:
            ok = deduct_from_balance(user_id, amount)
            if ok:
                await message.answer(f"✅ Списано {amount:.2f} RUB с баланса пользователя {user_id}")
                try:
                    await message.bot.send_message(
                        user_id,
                        f"➖ С вашего баланса списано {amount:.2f} RUB администратором.\nЕсли это ошибка — напишите в поддержку.",
                        reply_markup=keyboards.create_support_keyboard()
                    )
                except Exception:
                    pass
            else:
                await message.answer("❌ Пользователь не найден или недостаточно средств")
        except Exception as e:
            await message.answer(f"❌ Ошибка списания: {e}")
        await state.clear()
        await show_admin_menu(message)


    class AdminHostKeys(StatesGroup):
        picking_host = State()

    @admin_router.callback_query(F.data == "admin_host_keys")
    async def admin_host_keys_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await state.set_state(AdminHostKeys.picking_host)
        hosts = get_all_hosts()
        await callback.message.edit_text(
            "🌍 Выберите хост для просмотра ключей:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="hostkeys")
        )

    @admin_router.callback_query(AdminHostKeys.picking_host, F.data.startswith("admin_hostkeys_pick_host_"))
    async def admin_host_keys_pick_host(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        host_name = callback.data.split("admin_hostkeys_pick_host_")[-1]

        try:
            await state.update_data(hostkeys_host=host_name)
        except Exception:
            pass
        keys = get_keys_for_host(host_name)
        await callback.message.edit_text(
            f"🔑 Ключи на хосте {host_name}:",
            reply_markup=keyboards.create_admin_keys_for_host_keyboard(host_name, keys)
        )

    @admin_router.callback_query(AdminHostKeys.picking_host, F.data.startswith("admin_hostkeys_page_"))
    async def admin_hostkeys_page(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        try:
            page = int(callback.data.split("_")[-1])
        except Exception:
            page = 0
        data = await state.get_data()
        host_name = data.get('hostkeys_host')
        if not host_name:

            hosts = get_all_hosts()
            await callback.message.edit_text(
                "🌍 Выберите хост для просмотра ключей:",
                reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="hostkeys")
            )
            return
        keys = get_keys_for_host(host_name)
        await callback.message.edit_text(
            f"🔑 Ключи на хосте {host_name}:",
            reply_markup=keyboards.create_admin_keys_for_host_keyboard(host_name, keys, page=page)
        )

    @admin_router.callback_query(AdminHostKeys.picking_host, F.data == "admin_hostkeys_back_to_hosts")
    async def admin_hostkeys_back_to_hosts(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()

        try:
            await state.update_data(hostkeys_host=None)
        except Exception:
            pass
        hosts = get_all_hosts()
        await callback.message.edit_text(
            "🌍 Выберите хост для просмотра ключей:",
            reply_markup=keyboards.create_admin_hosts_pick_keyboard(hosts, action="hostkeys")
        )

    @admin_router.callback_query(F.data == "admin_hostkeys_back_to_users")
    async def admin_hostkeys_back_to_users(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await show_admin_menu(callback.message, edit_message=True)


    class AdminQuickDeleteKey(StatesGroup):
        waiting_for_identifier = State()

    @admin_router.callback_query(F.data == "admin_delete_key")
    async def admin_delete_key_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminQuickDeleteKey.waiting_for_identifier)
        await callback.message.edit_text(
            "🗑 Введите <code>key_id</code> или <code>email</code> ключа для удаления:",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminQuickDeleteKey.waiting_for_identifier)
    async def admin_delete_key_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        text = (message.text or '').strip()
        key = None

        try:
            key_id = int(text)
            key = rw_repo.get_key_by_id(key_id)
        except Exception:

            key = rw_repo.get_key_by_email(text)
        if not key:
            await message.answer("❌ Ключ не найден. Пришлите корректный key_id или email.")
            return
        key_id = int(key.get('key_id'))
        email = key.get('key_email') or '—'
        host = key.get('host_name') or '—'
        await state.clear()
        await message.answer(
            f"Подтвердите удаление ключа #{key_id}\nEmail: {email}\nСервер: {host}",
            reply_markup=keyboards.create_admin_delete_key_confirm_keyboard(key_id)
        )


    class AdminExtendKey(StatesGroup):
        waiting_for_pair = State()

    @admin_router.callback_query(F.data == "admin_extend_key")
    async def admin_extend_key_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminExtendKey.waiting_for_pair)
        await callback.message.edit_text(
            "➕ Введите: <code>key_id дни</code> (сколько дней добавить к ключу)",
            reply_markup=keyboards.create_admin_cancel_keyboard()
        )

    @admin_router.message(AdminExtendKey.waiting_for_pair)
    async def admin_extend_key_process(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        parts = (message.text or '').strip().split()
        if len(parts) != 2:
            await message.answer("❌ Формат: <code>key_id дни</code>")
            return
        try:
            key_id = int(parts[0])
            days = int(parts[1])
        except Exception:
            await message.answer("❌ Оба значения должны быть числами")
            return
        if days <= 0:
            await message.answer("❌ Количество дней должно быть положительным")
            return
        key = rw_repo.get_key_by_id(key_id)
        if not key:
            await message.answer("❌ Ключ не найден")
            return
        host = key.get('host_name')
        email = key.get('key_email')
        if not host or not email:
            await message.answer("❌ У ключа отсутствуют данные о хосте или email")
            return

        resp = None
        try:
            resp = await create_or_update_key_on_host(host, email, days_to_add=days)
        except Exception as e:
            logger.error(f"Поток продления: не удалось обновить клиента на хосте '{host}' для ключа #{key_id}: {e}")
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
        await message.answer(f"✅ Ключ #{key_id} продлён на {days} дн.")

        try:
            await message.bot.send_message(int(key.get('user_id')), f"ℹ️ Администратор продлил ваш ключ #{key_id} на {days} дн.")
        except Exception:
            pass

    @admin_router.callback_query(F.data == "start_broadcast")
    async def start_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.edit_text(
            "Пришлите сообщение, которое вы хотите разослать всем пользователям.\n"
            "Вы можете использовать форматирование (<b>жирный</b>, <i>курсив</i>).\n"
            "Также поддерживаются фото, видео и документы.\n",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_message)

    @admin_router.message(Broadcast.waiting_for_message)
    async def broadcast_message_received_handler(message: types.Message, state: FSMContext):
        import datetime
        from enum import Enum

        def _msg_json_default(o):
            if isinstance(o, Enum):
                return o.value
            if isinstance(o, (datetime.datetime, datetime.date)):
                return o.isoformat()
            return None  # aiogram Default sentinel and other unknown types

        import re

        def _detect_parse_mode(text: str) -> str | None:
            """Auto-detect parse mode: HTML tags → HTML, Markdown links/bold/etc → MarkdownV2."""
            if re.search(r'<(?:a|b|i|s|u|code|pre|tg-spoiler)\b', text, re.IGNORECASE):
                return 'HTML'
            if re.search(r'\[.+?\]\(https?://', text) or re.search(r'\*\*.+?\*\*|__.+?__|~~.+?~~|`[^`\n]+`|\|\|.+?\|\|', text):
                return 'MarkdownV2'
            return None

        msg_json = json.dumps(message.model_dump(), default=_msg_json_default)
        await state.update_data(message_to_send=msg_json)
        if message.text:
            auto_pm = _detect_parse_mode(message.text)
            if auto_pm:
                await state.update_data(parse_mode=auto_pm)
                await message.answer(
                    f"Сообщение получено. Обнаружена разметка — формат <b>{auto_pm}</b> применён автоматически.\n"
                    "Хотите добавить к нему кнопку со ссылкой?",
                    reply_markup=keyboards.create_broadcast_options_keyboard(),
                    parse_mode="HTML",
                )
                await state.set_state(Broadcast.waiting_for_button_option)
            else:
                await message.answer(
                    "Сообщение получено.\n\n"
                    "<b>Выберите формат</b> (нужен если в тексте есть ссылки или разметка):\n"
                    "• <b>Без форматирования</b> — текст как есть\n"
                    "• <b>HTML</b> — <code>&lt;b&gt;жирный&lt;/b&gt;</code>, <code>&lt;a href='url'&gt;текст&lt;/a&gt;</code>\n"
                    "• <b>MarkdownV2</b> — <code>[текст](url)</code> → кликабельная ссылка",
                    reply_markup=keyboards.create_broadcast_parse_mode_keyboard(),
                    parse_mode="HTML",
                )
                await state.set_state(Broadcast.waiting_for_parse_mode)
        else:
            await state.update_data(parse_mode=None)
            await message.answer(
                "Сообщение получено. Хотите добавить к нему кнопку со ссылкой?",
                reply_markup=keyboards.create_broadcast_options_keyboard()
            )
            await state.set_state(Broadcast.waiting_for_button_option)

    @admin_router.callback_query(
        Broadcast.waiting_for_parse_mode,
        F.data.in_({"broadcast_pm_none", "broadcast_pm_html", "broadcast_pm_md2"}),
    )
    async def broadcast_parse_mode_handler(callback: types.CallbackQuery, state: FSMContext):
        pm_map = {"broadcast_pm_none": None, "broadcast_pm_html": "HTML", "broadcast_pm_md2": "MarkdownV2"}
        parse_mode = pm_map[callback.data]
        await state.update_data(parse_mode=parse_mode)
        await callback.answer()
        await callback.message.edit_text(
            "Хотите добавить к нему кнопку со ссылкой?",
            reply_markup=keyboards.create_broadcast_options_keyboard(),
        )
        await state.set_state(Broadcast.waiting_for_button_option)

    
    @admin_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_add_button")
    async def add_button_choose_type(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Выберите тип кнопки для рассылки:",
            reply_markup=keyboards.create_broadcast_button_type_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_type)

    @admin_router.callback_query(Broadcast.waiting_for_button_type, F.data == "broadcast_btn_type_url")
    async def add_button_prompt_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Хорошо. Теперь отправьте мне текст для кнопки.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_text)

    @admin_router.callback_query(Broadcast.waiting_for_button_type, F.data == "broadcast_btn_type_action")
    async def add_functional_button_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        await callback.message.edit_text(
            "Выберите действие из функционала бота, к которому привяжем кнопку:",
            reply_markup=keyboards.create_broadcast_actions_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_action_select)

    @admin_router.callback_query(Broadcast.waiting_for_action_select, F.data.startswith("broadcast_action:"))
    async def functional_button_selected(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer()
        data_key = callback.data.split(":",1)[1]
        label = keyboards.BROADCAST_ACTIONS_MAP.get(data_key, data_key)
        await state.update_data(button_text=label, button_callback=data_key, button_url=None)
        await show_broadcast_preview(callback.message, state, callback.bot)


    @admin_router.message(Broadcast.waiting_for_button_text)
    async def button_text_received_handler(message: types.Message, state: FSMContext):
        await state.update_data(button_text=message.text)
        await message.answer(
            "Текст кнопки получен. Теперь отправьте ссылку (URL), куда она будет вести.",
            reply_markup=keyboards.create_broadcast_cancel_keyboard()
        )
        await state.set_state(Broadcast.waiting_for_button_url)

    @admin_router.message(Broadcast.waiting_for_button_url)
    async def button_url_received_handler(message: types.Message, state: FSMContext, bot: Bot):
        url_to_check = message.text

        if not (url_to_check.startswith("http://") or url_to_check.startswith("https://")):
            await message.answer(
                "❌ Ссылка должна начинаться с http:// или https://. Попробуйте еще раз.")
            return
        await state.update_data(button_url=url_to_check)
        await show_broadcast_preview(message, state, bot)

    @admin_router.callback_query(Broadcast.waiting_for_button_option, F.data == "broadcast_skip_button")
    async def skip_button_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.answer()
        await state.update_data(button_text=None, button_url=None)
        await show_broadcast_preview(callback.message, state, bot)

    def _escape_md2(text: str) -> str:
        """Escape MarkdownV2 special chars in plain-text parts, leaving inline entities intact."""
        import re as _re

        # Match valid MarkdownV2 entities to keep as-is
        ENTITY_RE = _re.compile(
            r'(\[(?:[^\[\]\\]|\\.)*\]\((?:[^()\\]|\\.)*\))'  # [text](url)
            r'|(\*\*(?:[^*\\]|\\.|\*(?!\*))*\*\*)'  # **bold**
            r'|(__(?:[^_\\]|\\.)*__)'  # __italic__
            r'|(~~(?:[^~\\]|\\.)*~~)'  # ~~strike~~
            r'|(`[^`\n]+`)'  # `code`
            r'|(\|\|(?:[^|\\]|\\.)*\|\|)',  # ||spoiler||
        )

        def _esc(s: str) -> str:
            return _re.sub(r'([_*\[\]()~`>#+=|{}.!\-\\])', r'\\\1', s)

        parts, last = [], 0
        for m in ENTITY_RE.finditer(text):
            parts.append(_esc(text[last:m.start()]))
            parts.append(m.group(0))
            last = m.end()
        parts.append(_esc(text[last:]))
        return ''.join(parts)

    async def _send_broadcast_to(bot: Bot, chat_id: int, msg: types.Message, keyboard, parse_mode: str | None = None) -> None:
        """Send broadcast, using specific send methods for media so reply_markup is applied correctly."""
        kw = dict(reply_markup=keyboard)
        # When parse_mode is set, use it instead of entities (they are mutually exclusive)
        if parse_mode:
            ckw = dict(caption=msg.caption, parse_mode=parse_mode, **kw)
        else:
            ckw = dict(caption=msg.caption, caption_entities=msg.caption_entities, **kw)
        if msg.photo:
            await bot.send_photo(chat_id=chat_id, photo=msg.photo[-1].file_id, **ckw)
        elif msg.video:
            await bot.send_video(chat_id=chat_id, video=msg.video.file_id, **ckw)
        elif msg.animation:
            await bot.send_animation(chat_id=chat_id, animation=msg.animation.file_id, **ckw)
        elif msg.document:
            await bot.send_document(chat_id=chat_id, document=msg.document.file_id, **ckw)
        elif msg.audio:
            await bot.send_audio(chat_id=chat_id, audio=msg.audio.file_id, **ckw)
        elif msg.voice:
            await bot.send_voice(chat_id=chat_id, voice=msg.voice.file_id, **kw)
        elif msg.sticker:
            await bot.send_sticker(chat_id=chat_id, sticker=msg.sticker.file_id, **kw)
        elif msg.text:
            no_preview = types.LinkPreviewOptions(is_disabled=True)
            if parse_mode:
                text = _escape_md2(msg.text) if parse_mode == 'MarkdownV2' else msg.text
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode, link_preview_options=no_preview, **kw)
            else:
                await bot.send_message(chat_id=chat_id, text=msg.text, entities=msg.entities, link_preview_options=no_preview, **kw)
        else:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=msg.chat.id,
                message_id=msg.message_id,
                **kw,
            )

    async def show_broadcast_preview(message: types.Message, state: FSMContext, bot: Bot):
        data = await state.get_data()
        message_json = data.get('message_to_send')
        original_message = types.Message.model_validate_json(message_json)
        parse_mode = data.get('parse_mode')

        button_text = data.get('button_text')
        button_url = data.get('button_url')
        button_callback = data.get('button_callback')

        preview_builder = InlineKeyboardBuilder()
        if button_text and (button_url or button_callback):
            if button_url:
                preview_builder.button(text=button_text, url=button_url)
            else:
                preview_builder.button(text=button_text, callback_data=button_callback)
        preview_builder.button(
            text=(get_setting("btn_back_to_menu_text") or "⬅️ Главное меню"),
            callback_data="open_main_menu",
        )
        preview_builder.adjust(1)
        preview_keyboard = preview_builder.as_markup()

        await message.answer(
            "Вот так будет выглядеть ваше сообщение. Отправляем?",
            reply_markup=keyboards.create_broadcast_confirmation_keyboard()
        )

        await _send_broadcast_to(bot, message.chat.id, original_message, preview_keyboard, parse_mode=parse_mode)

        await state.set_state(Broadcast.waiting_for_confirmation)

    @admin_router.callback_query(Broadcast.waiting_for_confirmation, F.data == "confirm_broadcast")
    async def confirm_broadcast_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
        await callback.message.edit_text("⏳ Начинаю рассылку... Это может занять некоторое время.")

        data = await state.get_data()
        message_json = data.get('message_to_send')
        original_message = types.Message.model_validate_json(message_json)
        parse_mode = data.get('parse_mode')

        button_text = data.get('button_text')
        button_url = data.get('button_url')
        button_callback = data.get('button_callback')

        final_builder = InlineKeyboardBuilder()
        if button_text and (button_url or button_callback):
            if button_url:
                final_builder.button(text=button_text, url=button_url)
            else:
                final_builder.button(text=button_text, callback_data=button_callback)
        final_builder.button(
            text=(get_setting("btn_back_to_menu_text") or "⬅️ Главное меню"),
            callback_data="open_main_menu",
        )
        final_builder.adjust(1)
        final_keyboard = final_builder.as_markup()

        await state.clear()

        users = get_all_users()
        logger.info(f"Рассылка: Начинаем итерацию по {len(users)} пользователями.")

        sent_count = 0
        failed_count = 0
        banned_count = 0
        unreachable_count = 0
        email_only_count = 0

        for user in users:
            user_id = user['telegram_id']
            if user.get('is_banned'):
                banned_count += 1
                continue
            if user.get('is_unreachable'):
                unreachable_count += 1
                continue
            # Email-регистрация без авторизации через Telegram — боту некуда писать.
            if database.is_email_only_user(user_id):
                email_only_count += 1
                continue
            try:
                await _send_broadcast_to(bot, user_id, original_message, final_keyboard, parse_mode=parse_mode)
                sent_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed_count += 1
                if telegram_reachability.handle_send_exception(user_id, e):
                    unreachable_count += 1
                else:
                    logger.warning(f"Не удалось отправить сообщение рассылки пользователю {user_id}: {e}")

        await callback.message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"👍 Отправлено: {sent_count}\n"
            f"👎 Не удалось отправить: {failed_count}\n"
            f"🚫 Пропущено (забанены): {banned_count}\n"
            f"📵 Недоступны (блок/деактивация): {unreachable_count}\n"
            f"📧 Пропущено (email без Telegram): {email_only_count}"
        )
        await show_admin_menu(callback.message)

    @admin_router.callback_query(StateFilter(Broadcast), F.data == "cancel_broadcast")
    async def cancel_broadcast_handler(callback: types.CallbackQuery, state: FSMContext):
        await callback.answer("Рассылка отменена.")
        await state.clear()
        await show_admin_menu(callback.message, edit_message=True)


    @admin_router.message(Command(commands=["approve_withdraw"]))
    async def approve_withdraw_handler(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            user_id = int(message.text.split("_")[-1])
            user = get_user(user_id)
            balance = user.get('referral_balance', 0)
            if balance < 100:
                await message.answer("Баланс пользователя менее 100 руб.")
                return
            set_referral_balance(user_id, 0)
            set_referral_balance_all(user_id, 0)
            await message.answer(f"✅ Выплата {balance:.2f} RUB пользователю {user_id} подтверждена.")
            await message.bot.send_message(
                user_id,
                f"✅ Ваша заявка на вывод {balance:.2f} RUB одобрена. Деньги будут переведены в ближайшее время."
            )
        except Exception as e:
            await message.answer(f"Ошибка: {e}")

    @admin_router.message(Command(commands=["decline_withdraw"]))
    async def decline_withdraw_handler(message: types.Message):
        if not is_admin(message.from_user.id):
            return
        try:
            user_id = int(message.text.split("_")[-1])
            await message.answer(f"❌ Заявка пользователя {user_id} отклонена.")
            await message.bot.send_message(
                user_id,
                "❌ Ваша заявка на вывод отклонена. Проверьте корректность реквизитов и попробуйте снова."
            )
        except Exception as e:
            await message.answer(f"Ошибка: {e}")


    @admin_router.callback_query(F.data == "admin_monitor")
    async def admin_monitor_menu(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ только для админов", show_alert=True)
            return
        try:
            hosts = get_all_hosts() or []
            targets = get_all_ssh_targets() or []
        except Exception:
            hosts, targets = [], []
        kb = InlineKeyboardBuilder()
        kb.button(text="📟 Панель (локально)", callback_data="admin_monitor_local")
        for h in hosts:
            name = h.get('host_name')
            if name:
                kb.button(text=f"🖥 {name}", callback_data=f"rmh:{name}")
        for t in targets:
            tname = t.get('target_name')
            if not tname:
                continue
            try:
                digest = hashlib.sha1((tname or '').encode('utf-8','ignore')).hexdigest()
            except Exception:
                digest = hashlib.sha1(str(tname).encode('utf-8','ignore')).hexdigest()
            kb.button(text=f"🔌 {tname}", callback_data=f"rmt:{digest}")
        kb.button(text="⬅️ В админ-меню", callback_data="admin_menu")
        rows = [1]
        total_items = len(hosts) + len(targets)
        if total_items > 0:
            rows.extend([2] * ((total_items + 1) // 2))
        rows.append(1)
        kb.adjust(*rows)
        await callback.message.edit_text("<b>Мониторинг ресурсов</b>\nВыберите объект:", reply_markup=kb.as_markup())

    @admin_router.callback_query(F.data == "admin_monitor_local")
    async def admin_monitor_local(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ только для админов", show_alert=True)
            return
        
        await callback.answer("🔄 Получение данных...")
        

        try:
            hosts = get_all_hosts() or []
            if hosts and len(hosts) > 0:

                current_host = hosts[0]
                data = resource_monitor.get_remote_metrics_for_host(current_host.get('host_name'))
                is_remote = True
            else:

                data = resource_monitor.get_local_metrics()
                is_remote = False
        except Exception:

            data = resource_monitor.get_local_metrics()
            is_remote = False
        
        try:
            if is_remote:

                cpu_p = data.get('cpu_percent')
                mem_p = data.get('memory_percent')
                disk_p = data.get('disk_percent')
                load1 = (data.get('loadavg') or [None])[0] if data.get('loadavg') else None
                net_sent = data.get('network_sent', 0)
                net_recv = data.get('network_recv', 0)
                scope = 'host'
                name = current_host.get('host_name')
            else:

                cpu_p = (data.get('cpu') or {}).get('percent')
                mem_p = (data.get('memory') or {}).get('percent')
                disks = data.get('disks') or []
                disk_p = max((d.get('percent') or 0) for d in disks) if disks else None
                load1 = (data.get('cpu') or {}).get('loadavg',[None])[0] if (data.get('cpu') or {}).get('loadavg') else None
                net_sent = (data.get('net') or {}).get('bytes_sent', 0)
                net_recv = (data.get('net') or {}).get('bytes_recv', 0)
                scope = 'local'
                name = 'panel'
            
            rw_repo.insert_resource_metric(
                scope, name,
                cpu_percent=cpu_p, mem_percent=mem_p, disk_percent=disk_p,
                load1=load1,
                net_bytes_sent=net_sent,
                net_bytes_recv=net_recv,
                raw_json=json.dumps(data, ensure_ascii=False)
            )
        except Exception:
            pass
        
        if not data.get('ok'):
            host_name = current_host.get('host_name') if is_remote else 'локально'
            txt = [
                f"🚨 <b>Панель ({host_name}) - ОШИБКА</b>",
                "",
                f"❌ <code>{data.get('error', 'Неизвестная ошибка')}</code>"
            ]
        else:
            if is_remote:

                cpu = {'percent': data.get('cpu_percent', 0), 'count_logical': data.get('cpu_count', '—')}
                mem = {
                    'percent': data.get('memory_percent', 0),
                    'used': (data.get('memory_used_mb', 0)) * 1024 * 1024,
                    'total': (data.get('memory_total_mb', 0)) * 1024 * 1024
                }
                net = {
                    'bytes_sent': data.get('network_sent', 0),
                    'bytes_recv': data.get('network_recv', 0),
                    'packets_sent': data.get('network_packets_sent', 0),
                    'packets_recv': data.get('network_packets_recv', 0)
                }
                sw = {}
                disks = []
                hostname = data.get('uname', '—')
                platform = '—'
            else:

                cpu = data.get('cpu') or {}
                mem = data.get('memory') or {}
                sw = data.get('swap') or {}
                net = data.get('net') or {}
                disks = data.get('disks', [])
                hostname = data.get('hostname', '—')
                platform = data.get('platform', '—')
            

            cpu_percent = cpu.get('percent', 0) or 0
            mem_percent = mem.get('percent', 0) or 0
            disk_percent = disk_p or 0
            
            def get_status_emoji(value, warning=70, critical=90):
                if value >= critical:
                    return "🔴"
                elif value >= warning:
                    return "🟡"
                else:
                    return "🟢"
            
            def format_bytes(bytes_val):
                if bytes_val is None:
                    return "—"
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if bytes_val < 1024.0:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024.0
                return f"{bytes_val:.1f} PB"
            
            def format_uptime(seconds):
                if not seconds:
                    return "—"
                days = int(seconds // 86400)
                hours = int((seconds % 86400) // 3600)
                minutes = int((seconds % 3600) // 60)
                if days > 0:
                    return f"{days}д {hours}ч {minutes}м"
                elif hours > 0:
                    return f"{hours}ч {minutes}м"
                else:
                    return f"{minutes}м"
            
            host_name = current_host.get('host_name') if is_remote else 'локально'
            txt = [
                f"🖥️ <b>Панель ({host_name})</b>",
                "",
                f"🖥 <b>Хост:</b> <code>{hostname}</code>",
                f"⏱ <b>Время работы:</b> <code>{format_uptime(data.get('uptime_sec'))}</code>",
                f"🖥 <b>Платформа:</b> <code>{platform}</code>",
                "",
                "📊 <b>Производительность:</b>",
                f"{get_status_emoji(cpu_percent)} <b>Процессор:</b> {cpu_percent}% ({cpu.get('count_logical', '—')} логич, {cpu.get('count_physical', '—')} физич)",
                f"{get_status_emoji(mem_percent)} <b>Память:</b> {mem_percent}% ({format_bytes(mem.get('used'))} / {format_bytes(mem.get('total'))})",
                f"{get_status_emoji(disk_percent)} <b>Диск:</b> {disk_percent}%",
                f"🔄 <b>Swap:</b> {sw.get('percent', '—')}% ({format_bytes(sw.get('used'))} / {format_bytes(sw.get('total'))})" if sw else "",
                "",
                "🌐 <b>Сеть:</b>",
                f"⬆️ Отправлено: <code>{format_bytes(net.get('bytes_sent', 0))}</code>",
                f"⬇️ Получено: <code>{format_bytes(net.get('bytes_recv', 0))}</code>",
            ]
            

            if disks:
                txt.append("")
                txt.append("💾 <b>Диски:</b>")
                for disk in disks[:3]:
                    mountpoint = disk.get('mountpoint') or disk.get('device', '—')
                    percent = disk.get('percent', 0) or 0
                    used = format_bytes(disk.get('used'))
                    total = format_bytes(disk.get('total'))
                    txt.append(f"  {get_status_emoji(percent, 80, 95)} <code>{mountpoint}</code>: {percent}% ({used} / {total})")
                if len(disks) > 3:
                    txt.append(f"  ... и еще {len(disks) - 3} дисков")
        

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Обновить", callback_data="admin_monitor_local")
        kb.button(text="📊 Полная статистика", callback_data="admin_monitor_detailed")
        kb.button(text="⬅️ Назад", callback_data="admin_monitor")
        kb.adjust(2, 1)
        
        await callback.message.edit_text("\n".join(txt), parse_mode='HTML', reply_markup=kb.as_markup())

    @admin_router.callback_query(F.data.startswith("rmh:"))
    async def admin_monitor_host(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ только для админов", show_alert=True)
            return
        
        host_name = (callback.data or '').split(':',1)[1]
        await callback.answer("🔄 Подключение к хосту...")
        data = resource_monitor.get_remote_metrics_for_host(host_name)
        
        try:
            mem_p = (data.get('memory') or {}).get('percent')
            disks = data.get('disks') or []
            disk_p = max((d.get('percent') or 0) for d in disks) if disks else None
            rw_repo.insert_resource_metric(
                'host', host_name,
                mem_percent=mem_p,
                disk_percent=disk_p,
                load1=(data.get('loadavg') or [None])[0],
                raw_json=json.dumps(data, ensure_ascii=False)
            )
        except Exception:
            pass
        
        if not data.get('ok'):
            txt = [
                f"🖥️ <b>Хост: {host_name}</b>",
                "",
                "🚨 <b>ОШИБКА ПОДКЛЮЧЕНИЯ</b>",
                f"❌ <code>{data.get('error', 'Неизвестная ошибка')}</code>"
            ]
        else:
            mem = data.get('memory') or {}
            loadavg = data.get('loadavg') or []
            cpu_count = data.get('cpu_count', 1)
            

            cpu_percent = None
            if loadavg and cpu_count:
                cpu_percent = min((loadavg[0] / cpu_count) * 100, 100)
            
            mem_percent = mem.get('percent', 0) or 0
            disk_percent = max((d.get('percent') or 0) for d in data.get('disks', [])) if data.get('disks') else 0
            
            def get_status_emoji(value, warning=70, critical=90):
                if value is None:
                    return "⚪"
                if value >= critical:
                    return "🔴"
                elif value >= warning:
                    return "🟡"
                else:
                    return "🟢"
            
            def format_uptime(seconds):
                if not seconds:
                    return "—"
                days = int(seconds // 86400)
                hours = int((seconds % 86400) // 3600)
                minutes = int((seconds % 3600) // 60)
                if days > 0:
                    return f"{days}д {hours}ч {minutes}м"
                elif hours > 0:
                    return f"{hours}ч {minutes}м"
                else:
                    return f"{minutes}м"
            
            def format_loadavg(loads):
                if not loads:
                    return "—"
                return " / ".join(f"{load:.2f}" for load in loads)
            
            txt = [
                f"🖥️ <b>Хост: {host_name}</b>",
                "",
                f"🖥 <b>Система:</b> <code>{data.get('uname', '—')}</code>",
                f"⏱ <b>Время работы:</b> <code>{format_uptime(data.get('uptime_sec'))}</code>",
                f"🔢 <b>Ядер процессора:</b> <code>{cpu_count}</code>",
                "",
                "📊 <b>Производительность:</b>",
                f"{get_status_emoji(cpu_percent)} <b>Процессор:</b> {cpu_percent:.1f}%" if cpu_percent is not None else "⚪ <b>Процессор:</b> —",
                f"📈 <b>Средняя загрузка:</b> <code>{format_loadavg(loadavg)}</code>",
                f"{get_status_emoji(mem_percent)} <b>Память:</b> {mem_percent}% ({mem.get('used_mb', '—')} / {mem.get('total_mb', '—')} МБ)",
                f"{get_status_emoji(disk_percent)} <b>Диск:</b> {disk_percent}%",
            ]
            

            disks = data.get('disks', [])
            if disks:
                txt.append("")
                txt.append("💾 <b>Диски:</b>")
                for disk in disks[:3]:
                    device = disk.get('device') or disk.get('mountpoint', '—')
                    percent = disk.get('percent', 0) or 0
                    used = disk.get('used', '—')
                    size = disk.get('size', '—')
                    txt.append(f"  {get_status_emoji(percent, 80, 95)} <code>{device}</code>: {percent}% ({used} / {size})")
                if len(disks) > 3:
                    txt.append(f"  ... и еще {len(disks) - 3} дисков")
        

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Обновить", callback_data=callback.data)
        kb.button(text="⬅️ Назад", callback_data="admin_monitor")
        kb.adjust(2)
        
        await callback.message.edit_text("\n".join(txt), parse_mode='HTML', reply_markup=kb.as_markup())

    @admin_router.callback_query(F.data.startswith("rmt:"))
    async def admin_monitor_target(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ только для админов", show_alert=True)
            return
        

        try:
            digest = callback.data.split(':',1)[1]
        except Exception:
            digest = ''
        tname = None
        try:
            for t in get_all_ssh_targets() or []:
                name = t.get('target_name')
                if not name:
                    continue
                try:
                    h = hashlib.sha1((name or '').encode('utf-8','ignore')).hexdigest()
                except Exception:
                    h = hashlib.sha1(str(name).encode('utf-8','ignore')).hexdigest()
                if h == digest:
                    tname = name; break
        except Exception:
            tname = None
        if not tname:
            await callback.answer("Цель не найдена", show_alert=True)
            return
        
        await callback.answer("🔄 Подключение по SSH...")
        data = resource_monitor.get_remote_metrics_for_target(tname)
        
        try:
            mem_p = (data.get('memory') or {}).get('percent')
            disks = data.get('disks') or []
            disk_p = max((d.get('percent') or 0) for d in disks) if disks else None
            rw_repo.insert_resource_metric(
                'target', tname,
                mem_percent=mem_p,
                disk_percent=disk_p,
                load1=(data.get('loadavg') or [None])[0],
                raw_json=json.dumps(data, ensure_ascii=False)
            )
        except Exception:
            pass
        
        if not data.get('ok'):
            txt = [
                f"🔌 <b>SSH-цель: {tname}</b>",
                "",
                "🚨 <b>ОШИБКА ПОДКЛЮЧЕНИЯ</b>",
                f"❌ <code>{data.get('error', 'Неизвестная ошибка')}</code>"
            ]
        else:
            mem = data.get('memory') or {}
            loadavg = data.get('loadavg') or []
            cpu_count = data.get('cpu_count', 1)
            

            cpu_percent = None
            if loadavg and cpu_count:
                cpu_percent = min((loadavg[0] / cpu_count) * 100, 100)
            
            mem_percent = mem.get('percent', 0) or 0
            disk_percent = max((d.get('percent') or 0) for d in data.get('disks', [])) if data.get('disks') else 0
            
            def get_status_emoji(value, warning=70, critical=90):
                if value is None:
                    return "⚪"
                if value >= critical:
                    return "🔴"
                elif value >= warning:
                    return "🟡"
                else:
                    return "🟢"
            
            def format_uptime(seconds):
                if not seconds:
                    return "—"
                days = int(seconds // 86400)
                hours = int((seconds % 86400) // 3600)
                minutes = int((seconds % 3600) // 60)
                if days > 0:
                    return f"{days}д {hours}ч {minutes}м"
                elif hours > 0:
                    return f"{hours}ч {minutes}м"
                else:
                    return f"{minutes}м"
            
            def format_loadavg(loads):
                if not loads:
                    return "—"
                return " / ".join(f"{load:.2f}" for load in loads)
            
            txt = [
                f"🔌 <b>SSH-цель: {tname}</b>",
                "",
                f"🖥 <b>Система:</b> <code>{data.get('uname', '—')}</code>",
                f"⏱ <b>Время работы:</b> <code>{format_uptime(data.get('uptime_sec'))}</code>",
                f"🔢 <b>Ядер процессора:</b> <code>{cpu_count}</code>",
                "",
                "📊 <b>Производительность:</b>",
                f"{get_status_emoji(cpu_percent)} <b>Процессор:</b> {cpu_percent:.1f}%" if cpu_percent is not None else "⚪ <b>Процессор:</b> —",
                f"📈 <b>Средняя загрузка:</b> <code>{format_loadavg(loadavg)}</code>",
                f"{get_status_emoji(mem_percent)} <b>Память:</b> {mem_percent}% ({mem.get('used_mb', '—')} / {mem.get('total_mb', '—')} МБ)",
                f"{get_status_emoji(disk_percent)} <b>Диск:</b> {disk_percent}%",
            ]
            

            disks = data.get('disks', [])
            if disks:
                txt.append("")
                txt.append("💾 <b>Диски:</b>")
                for disk in disks[:3]:
                    device = disk.get('device') or disk.get('mountpoint', '—')
                    percent = disk.get('percent', 0) or 0
                    used = disk.get('used', '—')
                    size = disk.get('size', '—')
                    txt.append(f"  {get_status_emoji(percent, 80, 95)} <code>{device}</code>: {percent}% ({used} / {size})")
                if len(disks) > 3:
                    txt.append(f"  ... и еще {len(disks) - 3} дисков")
        

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Обновить", callback_data=callback.data)
        kb.button(text="⬅️ Назад", callback_data="admin_monitor")
        kb.adjust(2)
        
        await callback.message.edit_text("\n".join(txt), parse_mode='HTML', reply_markup=kb.as_markup())

    @admin_router.callback_query(F.data == "admin_monitor_detailed")
    async def admin_monitor_detailed(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ только для админов", show_alert=True)
            return
        
        await callback.answer("🔄 Получение детальной статистики...")
        data = resource_monitor.get_local_metrics()
        
        if not data.get('ok'):
            txt = [
                "🚨 <b>Детальная статистика - ОШИБКА</b>",
                "",
                f"❌ <code>{data.get('error', 'Неизвестная ошибка')}</code>"
            ]
        else:
            cpu = data.get('cpu') or {}
            mem = data.get('memory') or {}
            sw = data.get('swap') or {}
            net = data.get('net') or {}
            disks = data.get('disks') or []
            
            def format_bytes(bytes_val):
                if bytes_val is None:
                    return "—"
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if bytes_val < 1024.0:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024.0
                return f"{bytes_val:.1f} PB"
            
            def format_uptime(seconds):
                if not seconds:
                    return "—"
                days = int(seconds // 86400)
                hours = int((seconds % 86400) // 3600)
                minutes = int((seconds % 3600) // 60)
                if days > 0:
                    return f"{days}д {hours}ч {minutes}м"
                elif hours > 0:
                    return f"{hours}ч {minutes}м"
                else:
                    return f"{minutes}м"
            
            txt = [
                "📊 <b>Детальная статистика панели</b>",
                "",
                "🖥️ <b>Системная информация:</b>",
                f"• <b>Хост:</b> <code>{data.get('hostname', '—')}</code>",
                f"• <b>Платформа:</b> <code>{data.get('platform', '—')}</code>",
                f"• <b>Python:</b> <code>{data.get('python', '—')}</code>",
                f"• <b>Время работы:</b> <code>{format_uptime(data.get('uptime_sec'))}</code>",
                "",
                "⚙️ <b>Процессор:</b>",
                f"• <b>Загрузка:</b> {cpu.get('percent', '—')}%",
                f"• <b>Логических ядер:</b> {cpu.get('count_logical', '—')}",
                f"• <b>Физических ядер:</b> {cpu.get('count_physical', '—')}",
                f"• <b>Средняя загрузка:</b> {', '.join(map(str, cpu.get('loadavg', []))) or '—'}",
                "",
                "🧠 <b>Память:</b>",
                f"• <b>Загрузка памяти:</b> {mem.get('percent', '—')}%",
                f"• <b>Использовано:</b> {format_bytes(mem.get('used'))}",
                f"• <b>Доступно:</b> {format_bytes(mem.get('available'))}",
                f"• <b>Всего:</b> {format_bytes(mem.get('total'))}",
                f"• <b>Загрузка swap:</b> {sw.get('percent', '—')}%",
                f"• <b>Swap использовано:</b> {format_bytes(sw.get('used'))}",
                f"• <b>Swap всего:</b> {format_bytes(sw.get('total'))}",
                "",
                "🌐 <b>Сеть:</b>",
                f"• <b>Отправлено:</b> {format_bytes(net.get('bytes_sent'))} ({net.get('packets_sent', 0):,} пакетов)",
                f"• <b>Получено:</b> {format_bytes(net.get('bytes_recv'))} ({net.get('packets_recv', 0):,} пакетов)",
                f"• <b>Ошибки входящие:</b> {net.get('errin', 0):,}",
                f"• <b>Ошибки исходящие:</b> {net.get('errout', 0):,}",
                f"• <b>Потеряно входящих:</b> {net.get('dropin', 0):,}",
                f"• <b>Потеряно исходящих:</b> {net.get('dropout', 0):,}",
            ]
            

            temps = data.get('temperatures', {})
            if temps:
                txt.append("")
                txt.append("🌡️ <b>Температура:</b>")
                for sensor_name, temp_info in temps.items():
                    current = temp_info.get('current', 0)
                    high = temp_info.get('high', 0)
                    critical = temp_info.get('critical', 0)
                    status_emoji = "🔴" if current >= critical else "🟡" if current >= high else "🟢"
                    txt.append(f"• {status_emoji} <b>{sensor_name}:</b> {current:.1f}°C (критично: {critical:.1f}°C)")
            

            top_processes = data.get('top_processes', [])
            if top_processes:
                txt.append("")
                txt.append("🔄 <b>Топ процессов по процессору:</b>")
                for i, proc in enumerate(top_processes[:5], 1):
                    name = proc.get('name', '—')
                    cpu_p = proc.get('cpu_percent', 0)
                    mem_p = proc.get('memory_percent', 0)
                    pid = proc.get('pid', '—')
                    txt.append(f"  {i}. <code>{name}</code> (PID: {pid})")
                    txt.append(f"     Процессор: {cpu_p:.1f}%, Память: {mem_p:.1f}%")
            

            if disks:
                txt.append("")
                txt.append("💾 <b>Диски:</b>")
                for i, disk in enumerate(disks, 1):
                    mountpoint = disk.get('mountpoint') or disk.get('device', '—')
                    fstype = disk.get('fstype', '—')
                    percent = disk.get('percent', 0) or 0
                    used = format_bytes(disk.get('used'))
                    free = format_bytes(disk.get('free'))
                    total = format_bytes(disk.get('total'))
                    
                    status_emoji = "🔴" if percent >= 95 else "🟡" if percent >= 80 else "🟢"
                    
                    txt.append(f"  {i}. {status_emoji} <code>{mountpoint}</code>")
                    txt.append(f"     Тип: {fstype}")
                    txt.append(f"     Использовано: {percent}% ({used} / {total})")
                    txt.append(f"     Свободно: {free}")
                    if i < len(disks):
                        txt.append("")
        

        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Обновить", callback_data="admin_monitor_detailed")
        kb.button(text="⬅️ К мониторингу", callback_data="admin_monitor")
        kb.adjust(2)
        
        await callback.message.edit_text("\n".join(txt), parse_mode='HTML', reply_markup=kb.as_markup())

    # =============================
    # Captcha settings (Admin)
    # =============================
    
    @admin_router.callback_query(F.data == "admin_captcha_settings")
    async def admin_captcha_settings_handler(callback: types.CallbackQuery):
        """Показать страницу настроек капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        captcha_enabled = get_setting("captcha_enabled") == "true"
        captcha_type = get_setting("captcha_type") or "math"
        max_attempts = get_setting("captcha_max_attempts") or "3"
        timeout = get_setting("captcha_timeout_minutes") or "15"
        
        text = (
            "🤖 <b>Система капчи</b>\n\n"
            f"<b>Статус:</b> {'✅ Включена' if captcha_enabled else '❌ Отключена'}\n"
            f"<b>Тип:</b> {captcha_type}\n"
            f"<b>Макс. попыток:</b> {max_attempts}\n"
            f"<b>Timeout (мин):</b> {timeout}\n\n"
            "Выберите действие:"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text=f"{'✅ Отключить' if captcha_enabled else '❌ Включить'}", 
                      callback_data="admin_captcha_toggle")
        builder.button(text="📝 Тип капчи", callback_data="admin_captcha_type")
        builder.button(text="🔢 Макс. попыток", callback_data="admin_captcha_attempts")
        builder.button(text="⏱️ Timeout", callback_data="admin_captcha_timeout")
        builder.button(text="💬 Сообщение", callback_data="admin_captcha_message")
        builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
        builder.adjust(2)
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup())
    
    @admin_router.callback_query(F.data == "admin_captcha_toggle")
    async def admin_captcha_toggle_handler(callback: types.CallbackQuery):
        """Включить/отключить капчу."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        current = get_setting("captcha_enabled") == "true"
        new_value = "false" if current else "true"
        rw_repo.update_setting("captcha_enabled", new_value)
        
        await callback.answer(f"✅ Капча {'отключена' if not current else 'включена'}", show_alert=True)
        await admin_captcha_settings_handler(callback)
    
    @admin_router.callback_query(F.data == "admin_captcha_type")
    async def admin_captcha_type_handler(callback: types.CallbackQuery):
        """Выбрать тип капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_type") or "math"
        
        text = "📝 <b>Выберите тип капчи:</b>\n\n1️⃣ <b>Математическая</b> - решение примера (45+27=?)\n2️⃣ <b>Кнопочная</b> - выбор правильного смайлика"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Математическая" if current == "math" else "❌ Математическая", 
                      callback_data="admin_captcha_type_set:math")
        builder.button(text="✅ Кнопочная" if current == "button" else "❌ Кнопочная", 
                      callback_data="admin_captcha_type_set:button")
        builder.button(text="⬅️ Назад", callback_data="admin_captcha_settings")
        builder.adjust(2)
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup())
    
    @admin_router.callback_query(F.data.startswith("admin_captcha_type_set:"))
    async def admin_captcha_type_set_handler(callback: types.CallbackQuery):
        """Установить тип капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        
        captcha_type = callback.data.split(":", 1)[1]
        rw_repo.update_setting("captcha_type", captcha_type)
        
        type_name = "математическая" if captcha_type == "math" else "кнопочная"
        await callback.answer(f"✅ Тип капчи установлен: {type_name}", show_alert=True)
        await admin_captcha_settings_handler(callback)
    
    @admin_router.callback_query(F.data == "admin_captcha_attempts")
    async def admin_captcha_attempts_handler(callback: types.CallbackQuery, state: FSMContext):
        """Установить максимальное количество попыток."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_max_attempts") or "3"
        text = f"🔢 <b>Текущее значение:</b> {current} попыток\n\n<b>Введите новое значение (целое число от 1 до 10):</b>"
        
        await state.set_state(AdminSettings.waiting_for_captcha_attempts)
        await callback.message.edit_text(text, reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="admin_captcha_settings").as_markup())
    
    @admin_router.message(AdminSettings.waiting_for_captcha_attempts)
    async def admin_captcha_attempts_input_handler(message: types.Message, state: FSMContext):
        """Обработать ввод количества попыток."""
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        try:
            value = int(message.text.strip())
            if value < 1 or value > 10:
                await message.answer("Значение должно быть от 1 до 10.")
                return
            
            rw_repo.update_setting("captcha_max_attempts", str(value))
            await message.answer(f"✅ Максимум попыток установлено: {value}")
            await state.clear()
        except ValueError:
            await message.answer("Пожалуйста, введите целое число.")
    
    @admin_router.callback_query(F.data == "admin_captcha_timeout")
    async def admin_captcha_timeout_handler(callback: types.CallbackQuery, state: FSMContext):
        """Установить timeout капчи."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_timeout_minutes") or "15"
        text = f"⏱️ <b>Текущее значение:</b> {current} минут\n\n<b>Введите новое значение (от 5 до 120 минут):</b>"
        
        await state.set_state(AdminSettings.waiting_for_captcha_timeout)
        await callback.message.edit_text(text, reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="admin_captcha_settings").as_markup())
    
    @admin_router.message(AdminSettings.waiting_for_captcha_timeout)
    async def admin_captcha_timeout_input_handler(message: types.Message, state: FSMContext):
        """Обработать ввод timeout."""
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        try:
            value = int(message.text.strip())
            if value < 5 or value > 120:
                await message.answer("Значение должно быть от 5 до 120 минут.")
                return
            
            rw_repo.update_setting("captcha_timeout_minutes", str(value))
            await message.answer(f"✅ Timeout капчи установлено: {value} минут")
            await state.clear()
        except ValueError:
            await message.answer("Пожалуйста, введите целое число.")
    
    @admin_router.callback_query(F.data == "admin_captcha_message")
    async def admin_captcha_message_handler(callback: types.CallbackQuery, state: FSMContext):
        """Установить кастомное сообщение к капче."""
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        
        current = get_setting("captcha_message") or "👤 Привет! Ты выглядишь как бот. Пройди простую капчу..."
        text = f"💬 <b>Текущее сообщение:</b>\n{current}\n\n<b>Введите новое сообщение (до 200 символов):</b>"
        
        await state.set_state(AdminSettings.waiting_for_captcha_message)
        await callback.message.edit_text(text, reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="admin_captcha_settings").as_markup())
    
    @admin_router.message(AdminSettings.waiting_for_captcha_message)
    async def admin_captcha_message_input_handler(message: types.Message, state: FSMContext):
        """Обработать ввод сообщения."""
        if not is_admin(message.from_user.id):
            await message.answer("У вас нет прав.")
            return
        
        msg = message.text.strip()
        if len(msg) > 200:
            await message.answer("Сообщение должно быть не более 200 символов.")
            return
        
        rw_repo.update_setting("captcha_message", msg)
        await message.answer("✅ Сообщение капчи обновлено")
        await state.clear()

    # =========================================================
    # Автопродление (глобальные настройки)
    # =========================================================

    class AdminAutoRenew(StatesGroup):
        waiting_for_hours = State()

    async def show_admin_auto_renew_menu(message: types.Message, edit_message: bool = False):
        enabled = _is_true(rw_repo.get_setting("auto_renew_globally_enabled") or "false")
        try:
            hours_before = int(rw_repo.get_setting("auto_renew_hours_before") or 24)
        except Exception:
            hours_before = 24
        status = "🟢 включено" if enabled else "🔴 выключено"
        text_out = (
            "🔄 <b>Автопродление подписок</b>\n\n"
            f"Статус: <b>{status}</b>\n"
            f"Окно срабатывания: <b>{hours_before} ч.</b> до окончания\n\n"
            "Когда включено, бот автоматически списывает с баланса пользователя "
            "стоимость тарифа и продлевает ключ. Функция работает только для ключей, "
            "у которых включено автопродление на карточке ключа."
        )
        kb = keyboards.create_admin_auto_renew_keyboard(enabled=enabled)
        if edit_message:
            try:
                await message.edit_text(text_out, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await message.answer(text_out, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(text_out, reply_markup=kb, parse_mode="HTML")

    @admin_router.callback_query(F.data == "admin_auto_renew")
    async def admin_auto_renew_entry(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminAutoRenew.waiting_for_hours)
        await state.clear()
        await show_admin_auto_renew_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_auto_renew_toggle")
    async def admin_auto_renew_toggle(callback: types.CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        current = _is_true(rw_repo.get_setting("auto_renew_globally_enabled") or "false")
        new_val = "false" if current else "true"
        rw_repo.update_setting("auto_renew_globally_enabled", new_val)
        status_text = "включено ✅" if not current else "выключено ❌"
        await callback.answer(f"Автопродление {status_text}")
        await show_admin_auto_renew_menu(callback.message, edit_message=True)

    @admin_router.callback_query(F.data == "admin_auto_renew_set_hours")
    async def admin_auto_renew_set_hours(callback: types.CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer("У вас нет прав.", show_alert=True)
            return
        await callback.answer()
        await callback.message.answer(
            "⏰ Укажите, за сколько часов до окончания срока начинать автопродление (например: 24):"
        )
        await state.set_state(AdminAutoRenew.waiting_for_hours)

    @admin_router.message(AdminAutoRenew.waiting_for_hours)
    async def admin_auto_renew_hours_input(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await message.answer("❌ У вас нет прав.")
            return
        try:
            hours = int(message.text.strip())
            if hours < 1 or hours > 168:
                await message.answer("❌ Укажите значение от 1 до 168 часов.")
                return
            rw_repo.update_setting("auto_renew_hours_before", str(hours))
            await message.answer(f"✅ Окно срабатывания установлено: <b>{hours} ч.</b>", parse_mode="HTML")
            await state.clear()
            await show_admin_auto_renew_menu(message, edit_message=False)
        except ValueError:
            await message.answer("❌ Введите целое число часов (например: 24).")

    return admin_router
