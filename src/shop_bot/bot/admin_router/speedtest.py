"""Speedtest: запуск по хостам и SSH-целям, автоустановка утилиты.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

from aiogram import Router, F, types

from shop_bot.bot import keyboards
from shop_bot.data_manager import speedtest_runner
from shop_bot.data_manager.remnawave_repository import (
    get_all_hosts,
    get_all_ssh_targets,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_speedtest_1(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


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


def register_speedtest_2(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


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
