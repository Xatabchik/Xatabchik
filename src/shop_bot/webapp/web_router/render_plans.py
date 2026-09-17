"""HTML-сетка тарифов и серверов.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


import html as html_lib

from shop_bot.data_manager.remnawave_repository import get_all_hosts, get_plans_for_host


def _esc_attr(value) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def _duration_label(months: int | None, duration_days: int | None) -> str:
    try:
        dd = int(duration_days or 0)
    except Exception:
        dd = 0
    if dd > 0:
        if dd % 30 == 0:
            mm = dd // 30
            return f"{mm} месяц" if mm == 1 else (f"{mm} месяца" if 1 < mm < 5 else f"{mm} месяцев")
        if dd % 7 == 0:
            ww = dd // 7
            return f"{ww} неделя" if ww == 1 else (f"{ww} недели" if 1 < ww < 5 else f"{ww} недель")
        return f"{dd} день" if dd == 1 else (f"{dd} дня" if 1 < dd < 5 else f"{dd} дней")
    try:
        mm = int(months or 0)
    except Exception:
        mm = 0
    if mm <= 0:
        mm = 1
    return f"{mm} месяц" if mm == 1 else (f"{mm} месяца" if 1 < mm < 5 else f"{mm} месяцев")


def _days_from_plan(plan: dict) -> int:
    try:
        dd = int(plan.get("duration_days") or 0)
    except Exception:
        dd = 0
    if dd > 0:
        return dd
    try:
        mm = int(plan.get("months") or 0)
    except Exception:
        mm = 0
    return max(1, mm or 1) * 30


def _billing_months_for_plan(plan: dict) -> float:
    return max(1.0 / 30.0, _days_from_plan(plan) / 30.0)


def _build_plans_grid_html(host_name: str, user_id: int | None, container_id: str, display_style: str = "grid") -> str:
    import re
    try:
        hosts = get_all_hosts()
        host = next((h for h in (hosts or []) if h['host_name'] == host_name), None)
    except:
        host = None

    desc = ""
    if host:
        desc = host.get('description') or "Выберите подходящий тариф:"
        desc = re.sub(r'(\s*\n\s*){2,}', '\n', desc).strip()

    try:
        plans = get_plans_for_host(host_name)
    except:
        plans = []

    active_plans = [p for p in plans if p.get('is_active')]
    if not active_plans:
        try:
            fallback_plans = []
            for fallback_host in (get_all_hosts() or []):
                fallback_host_name = fallback_host.get('host_name')
                for fp in get_plans_for_host(fallback_host_name):
                    if fp.get('is_active'):
                        fp = dict(fp)
                        fp['_purchase_host_name'] = fallback_host_name
                        fallback_plans.append(fp)
            active_plans = fallback_plans
        except Exception:
            active_plans = []

    html = f'<div id="{container_id}" class="server-plans-container grid grid-cols-2 gap-2 mt-1" style="display: {display_style};">'

    if not active_plans:
        html += '<div class="col-span-2 text-center text-[10px] text-gray-500 py-3 glass-card border border-white/5 rounded-xl">Нет доступных тарифов</div>'
    else:
        plan_count = len(active_plans)
        for plan_idx, plan in enumerate(active_plans):
            try:
                raw_price = float(plan.get('price', 0))
                final_price = int(calculate_webapp_price(raw_price, user_id))
                months = int(plan.get('months') or 0)
                duration_days = int(plan.get('duration_days') or 0)
                duration_label = _duration_label(months, duration_days)
            except (ValueError, TypeError):
                continue

            is_last_odd = (plan_idx == plan_count - 1) and (plan_count % 2 == 1)
            span_class = " col-span-2" if is_last_odd else ""

            html += f"""
            <button type="button"
                class="plan-btn glass-card border border-white/10 rounded-2xl p-3.5 flex flex-col items-center justify-center text-center transition-all active:scale-95 hover:border-primary/40 hover:bg-white/5 group{span_class}"
                data-host="{_esc_attr(plan.get('_purchase_host_name', host_name))}" data-plan-id="{_esc_attr(plan['plan_id'])}" data-price="{final_price}" data-plan-name="{_esc_attr(plan.get('plan_name', ''))}"
                data-months="{months or 0}" data-duration-days="{duration_days or 0}">
                <span
                    class="plan-label text-[9px] font-bold text-gray-500 uppercase tracking-widest mb-0.5 group-hover:text-gray-300 transition-colors">{_esc_attr(duration_label)}</span>
                <div class="flex items-baseline gap-0.5">
                    <span class="plan-price text-xl font-bold text-white">{final_price}</span>
                    <span class="text-xs font-medium text-gray-400">₽</span>
                </div>
            </button>
            """
    html += '</div>'

    return desc, html


def _get_servers_and_plans_html(user_id: int | None = None):
    try:
        hosts = get_all_hosts()
    except:
        hosts = []
        
    if not hosts:
        return "", '<div class="col-span-2 text-center text-xs text-gray-500 py-4 glass-card border border-white/5 rounded-xl">Нет доступных серверов</div>'
        
    server_options_html = '<div class="p-1 flex flex-col gap-0.5">'
    plans_html = ""
    
    for index, host in enumerate(hosts):
        host_name = host['host_name']
        
        is_selected = (index == 0)
            
        check_class = "text-primary" if is_selected else "text-transparent"
        text_color = "text-white" if is_selected else "text-gray-300"
        icon_color = "text-primary" if is_selected else "text-gray-500"
        
        server_options_html += f"""
        <button type="button"
            class="server-option w-full p-2.5 flex items-center justify-between rounded-lg hover:bg-white/5 transition-colors"
            data-server="{_esc_attr(host_name)}" data-index="{index}">
            <div class="flex items-center gap-2.5">
                <span class="material-symbols-rounded {icon_color} text-sm">public</span>
                <div class="text-left">
                    <div class="text-xs font-bold {text_color}">{_esc_attr(host_name)}</div>
                </div>
            </div>
            <span class="material-symbols-rounded {check_class} text-xs server-selected-icon">check</span>
        </button>
        """
        
        display_style = "grid" if is_selected else "none"
        desc, grid_html = _build_plans_grid_html(host_name, user_id, f"plans-{index}", display_style)
        
        plans_html += f'<div id="desc-content-{index}" style="display: none;">{desc}</div>'
        plans_html += grid_html

    server_options_html += '</div>'
    
    return server_options_html, plans_html


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_duration_label",
    "_days_from_plan",
    "_billing_months_for_plan",
    "_build_plans_grid_html",
    "_get_servers_and_plans_html",
]
