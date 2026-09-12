"""Конструктор кнопок: меню, список, карточка, добавление и правка.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import re
import html as html_escape

from aiogram import Router, F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.bot.callback_safety import fast_callback_answer, catch_callback_errors
from shop_bot.data_manager.remnawave_repository import is_admin
from shop_bot.data_manager.database import (
    get_button_configs_admin,
    get_button_config_by_db_id,
    create_button_config,
    update_button_config,
    delete_button_config,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_button_constructor(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""



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
