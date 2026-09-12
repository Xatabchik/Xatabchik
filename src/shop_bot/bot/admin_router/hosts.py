"""Хосты: добавление, правка, сквады, SSH-доступ, переход к тарифам.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import html as html_escape
import hashlib

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from shop_bot.bot import keyboards
from shop_bot.bot.callback_safety import fast_callback_answer, catch_callback_errors
from shop_bot.data_manager import database
from shop_bot.data_manager.remnawave_repository import (
    get_all_hosts,
    is_admin,
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
from shop_bot.data_manager.database import get_plans_for_host
from shop_bot.modules import remnawave_api


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_hosts(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""
    
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
        try:
            overlap = database.get_host_squad_overlap(name) if name and name != '—' else []
        except Exception:
            overlap = []
        if overlap:
            lte_squad_txt += f" ⚠️ пересечение с base: {len(overlap)} нод(ы)"

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
            # Пересечение нод LTE- и base-сквада не блокирует сохранение, но о нём нужно знать:
            # трафик пересекающихся нод попадёт в LTE-пул, хотя они же отдаются base-сквадом.
            try:
                overlap = await remnawave_api.refresh_host_squad_overlap(host_name)
            except Exception as e:
                overlap = []
                logger.warning(f"Проверка пересечения сквадов хоста '{host_name}' не удалась: {e}")
            if overlap:
                nodes_txt = "\n".join(
                    f"• {_safe(n.get('node_name') or '—')} (<code>{_safe(n.get('uuid'))}</code>)"
                    for n in overlap
                )
                await message.answer(
                    "⚠️ <b>Ноды доступны и через LTE-, и через base-сквад</b>\n\n"
                    f"{nodes_txt}\n\n"
                    "Их трафик будет засчитываться в LTE-пул, хотя те же ноды отдаёт безлимитный "
                    "сквад. Исправляется только правкой inbound'ов сквадов в Remnawave.",
                    parse_mode="HTML",
                )
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
