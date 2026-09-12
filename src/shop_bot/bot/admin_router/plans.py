"""Тарифы и пакеты трафика: создание, правка, удаление, лимиты LTE.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import html as html_escape
import json

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.data_manager import database
from shop_bot.data_manager.remnawave_repository import (
    get_all_hosts,
    is_admin,
)
from shop_bot.data_manager.database import (
    create_plan,
    get_plans_for_host,
    get_plan_by_id,
    update_plan,
    update_plan_metadata,
    delete_plan,
    set_plan_active,
    create_traffic_package,
    get_traffic_packages_for_plan,
    get_traffic_package_by_id,
    update_traffic_package,
    delete_traffic_package,
)


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


# __all__ — имена, которые пакет раскладывает по остальным модулям (см. __init__.py).
__all__ = [
    "AdminPlans",
    "_format_plan_duration",
    "_format_traffic_gb",
    "_format_devices",
    "_format_plans_for_host",
]


def register_plans(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""

    def _plan_show_name_enabled(plan: dict) -> bool:
        try:
            meta_raw = plan.get("metadata")
            meta = json.loads(meta_raw) if meta_raw else {}
            return bool(meta.get("show_name_in_tariffs"))
        except Exception:
            return False


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
