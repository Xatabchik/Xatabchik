"""Мониторинг ресурсов: локально, по хостам и по SSH-целям.

Выделено из bot/admin_handlers.py: тела блоков перенесены побайтово,
порядок регистрации хендлеров сохранён.
"""

import hashlib
import json

from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager import resource_monitor
from shop_bot.data_manager import remnawave_repository as rw_repo
from shop_bot.data_manager.remnawave_repository import (
    get_all_hosts,
    get_all_ssh_targets,
    is_admin,
)


# Этот модуль ничего не отдаёт соседям: всё, что в нём есть, кроме
# register_*, — вложенные хендлеры (см. __init__.py).
__all__: list[str] = []


def register_monitor(admin_router: Router) -> None:
    """Регистрирует блок хендлеров в порядке исходного файла."""


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
