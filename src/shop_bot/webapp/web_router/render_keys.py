"""Форматирование и HTML-карточки ключей и профиля.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.
"""


from typing import Any
import html as html_lib
from shop_bot.data_manager.remnawave_repository import get_setting, get_msk_time
from datetime import datetime, timedelta
import json
from shop_bot.data_manager.remnawave_repository import (
    get_plan_by_id,
    get_key_by_id,
)
import shop_bot.data_manager.remnawave_repository as rw_repo
from shop_bot.data_manager.database import (
    format_next_traffic_reset_display,
    get_squad_by_class,
    should_account_lte_traffic,
    get_key_lte_state,
    resolve_lte_limit_bytes,
    squad_display_label,
)


def _esc_text(value) -> str:
    """Экранировать значение для HTML-текста и атрибутов.

    Старые заметки/имена в БД могут содержать разметку и кавычки — их нельзя
    вставлять в карточку или в onclick как есть. Экранирование здесь не замена
    нормализации ввода: вредоносная строка остаётся в базе, но становится текстом.
    """
    return html_lib.escape("" if value is None else str(value), quote=True)


def _format_remaining_details(remaining: timedelta) -> str:
    total_seconds = int(remaining.total_seconds())
    if total_seconds <= 0:
        return "0мин"

    minutes = (total_seconds // 60) % 60
    hours = (total_seconds // 3600) % 24
    days = remaining.days % 365
    years = remaining.days // 365

    parts = []
    if years > 0:
        parts.append(f"{years}г.")
    if days > 0:
        parts.append(f"{days}д.")
    if hours > 0:
        parts.append(f"{hours}ч.")
    if minutes > 0:
        parts.append(f"{minutes}мин")

    # Берем только первые две значимые части для краткости
    result_parts = parts[:2]
    return " ".join(result_parts) if result_parts else "меньше минуты"


def _format_bytes(size: Any) -> str:
    if size is None: return "0 B"
    if isinstance(size, str):
        if any(x in size for x in ['B', 'KB', 'MB', 'GB', 'TB', 'iB']):
            return size
        try: size = float(size)
        except: return "0 B"
    
    if size <= 0: return "0 B"
    power = 1024
    n = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"


def _process_template_placeholders(html: str, user_id: int, webapp_settings: dict, context_data: dict) -> str:
    title = webapp_settings.get("webapp_title") or get_setting("panel_brand_title") or "Xatab VPN"
    support_username = get_setting("support_contact_username") or get_setting("support_bot_username") or ""
    bot_username = get_setting("telegram_bot_username") or ""
    webapp_domain = (get_setting("webapp_domain") or "").rstrip("/")

    replacements = {
        "{{ panel_brand_title }}": title,
        "{{ user_profile_card }}": context_data.get("profile_card", ""),
        "{{ key_info_section }}": context_data.get("key_section", ""),
        "{{ profile_keys_list }}": context_data.get("profile_keys_list", ""),
        "{{ setup_keys_list }}": context_data.get("setup_keys_list", ""),
        "{{ renew_keys_dropdown_options }}": context_data.get("renew_keys_options", ""),
        "{{ renew_plans_grid }}": context_data.get("renew_plans_html_data", ""),
        "{{ support_bot_username }}": support_username,
        "{{ min_price }}": context_data.get("min_price", "0 ₽"),
        "{{ webapp_logo }}": context_data.get("webapp_logo", ""),
        "{{ webapp_icon }}": context_data.get("webapp_icon", ""),
        "{{ app_css_href }}": APP_CSS_HREF,
        "{{ app_js_href }}": APP_JS_HREF,
        "{{ store_js_href }}": STORE_JS_HREF,
        "{{ logo_hidden }}": "hidden" if not context_data.get("webapp_logo") else "",
        "{{ user_id }}": str(user_id),
        "{{ bot_username }}": bot_username,
        "{{ webapp_domain }}": webapp_domain,
        "{{ tg_fullscreen_css }}": """
    <style>
        .tg-miniapp #main-page,
        .tg-miniapp #purchase-page,
        .tg-miniapp #renew-page,
        .tg-miniapp #setup-page,
        .tg-miniapp #profile-page,
        .tg-miniapp #support-page {
            padding-top: max(env(safe-area-inset-top), 70px) !important;
        }
    </style>
        """ if webapp_settings.get("tg_fullscreen") else "",
    }
    
    # Selected key display variants
    display_val = context_data.get("renew_selected_display", "Нет активных ключей")
    replacements["{{ renew_selected_key_display }}"] = display_val
    replacements["{{\n                                renew_selected_key_display }}"] = display_val

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)
    
    server_options, server_plans = _get_servers_and_plans_html(user_id)
    html = html.replace("{{ server_dropdown_options }}", server_options)
    html = html.replace("{{ server_plans_grid }}", server_plans)
    
    return html


def _format_bytes_gb(num_bytes) -> str:
    """Тот же формат ГБ, что в карточке ключа бота."""
    try:
        gb = int(num_bytes or 0) / (1024 ** 3)
        txt = f"{gb:.2f}"
        return txt.rstrip("0").rstrip(".") if "." in txt else txt
    except (TypeError, ValueError):
        return "0"


def _format_gb_amount(size_gb) -> str:
    try:
        val = float(size_gb or 0)
    except (TypeError, ValueError):
        val = 0.0
    return f"{val:.0f}" if val == int(val) else f"{val:g}"


def _is_key_without_billing_plan(key_data: dict) -> bool:
    """Триал/подарок: биллингового тарифа нет — докупка LTE недоступна (как в боте)."""
    try:
        tag = str((key_data or {}).get("tag") or "").strip().lower()
    except Exception:
        tag = ""
    if tag in {"trial", "триал"} or "gift" in tag:
        return True
    try:
        desc = (key_data or {}).get("description")
        if isinstance(desc, str) and desc.strip().startswith("{"):
            meta = json.loads(desc)
            if isinstance(meta, dict):
                if meta.get("is_trial"):
                    return True
                if str(meta.get("source") or "").strip().lower() in {"trial", "gift"}:
                    return True
    except Exception:
        pass
    return False


def _resolve_plan_id_for_key(key_data: dict) -> int | None:
    """plan_id из description JSON, иначе первый активный тариф хоста (как в боте)."""
    try:
        desc = (key_data or {}).get("description")
        if isinstance(desc, str) and desc.strip().startswith("{"):
            meta = json.loads(desc)
            if isinstance(meta, dict) and meta.get("plan_id") is not None:
                return int(meta.get("plan_id"))
    except Exception:
        pass
    if _is_key_without_billing_plan(key_data):
        return None
    host_name = (key_data or {}).get("host_name")
    if not host_name:
        return None
    try:
        plans = rw_repo.get_active_plans_for_host(host_name) or []
    except Exception:
        plans = []
    if not plans:
        return None
    try:
        return int(plans[0].get("plan_id"))
    except (TypeError, ValueError):
        return None


def _lte_card_state(key: dict) -> dict:
    """Условия и цифры LTE-пула — те же, что в карточке ключа бота.

    Показываем блок и кнопку докупки только если:
      1) у тарифа ключа задан lte_limit_bytes > 0;
      2) на хосте ключа есть активный сквад класса lte.
    Лимит = plans.lte_limit_bytes + докупленный буст (resolve_lte_limit_bytes).
    """
    empty = {
        "show_lte": False,
        "show_lte_topup": False,
        "lte_info": "",
        "lte_label": "LTE",
        "lte_used_bytes": 0,
        "lte_total_bytes": 0,
        "plan": None,
    }
    try:
        plan_id = _resolve_plan_id_for_key(key)
        if not plan_id:
            return empty
        plan = get_plan_by_id(plan_id)
        plan_lte_limit = int((plan or {}).get("lte_limit_bytes") or 0)
        host_name = key.get("host_name")
        if not should_account_lte_traffic(plan, host_name):
            return empty
        lte_squad = get_squad_by_class(host_name, "lte") if host_name else None
        if not lte_squad:
            return empty
        key_id = int(key.get("key_id") or 0)
        lte_state = get_key_lte_state(key_id) if key_id else {}
        lte_used = int((lte_state or {}).get("lte_used_bytes") or 0)
        lte_total = resolve_lte_limit_bytes(lte_state, plan_lte_limit)
        used_txt = _format_bytes_gb(lte_used)
        total_txt = _format_bytes_gb(lte_total)
        lte_label = squad_display_label(lte_squad)
        line = f"{used_txt} ГБ / {total_txt} ГБ"
        reset_txt = format_next_traffic_reset_display(key.get("next_traffic_reset_at"))
        if reset_txt:
            line += f" (сброс {reset_txt})"
        return {
            "show_lte": True,
            "show_lte_topup": True,
            "lte_info": line,
            "lte_label": lte_label,
            "lte_used_bytes": lte_used,
            "lte_total_bytes": lte_total,
            "plan": plan,
        }
    except Exception:
        return empty


def _owned_lte_key_and_plan(user_id: int, key_id: int):
    """Ключ принадлежит user_id и доступен для LTE-докупки. Иначе (None, None)."""
    try:
        key = get_key_by_id(int(key_id))
    except Exception:
        key = None
    if not key or int(key.get("user_id") or 0) != int(user_id):
        return None, None
    state = _lte_card_state(key)
    if not state.get("show_lte_topup") or not state.get("plan"):
        return None, None
    return key, state["plan"]


def _process_key_data(key: dict) -> dict:
    # 1. Calculate expiry
    try:
        expire_dt = datetime.strptime(key['expiry_date'], "%Y-%m-%d %H:%M:%S")
        created_dt = datetime.strptime(key.get('created_at', key['expiry_date']), "%Y-%m-%d %H:%M:%S")
        expire_date_str = expire_dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        expire_dt = datetime.now()
        created_dt = datetime.now()
        expire_date_str = "Unknown"
    
    now = get_msk_time().replace(tzinfo=None)
    
    # 2. Days left & Detailed remaining
    delta = expire_dt - now
    days_left = delta.days
    if days_left < 0:
        days_left = 0
        
    remaining_str = _format_remaining_details(delta) if delta.total_seconds() > 0 else "Истёк"

    # 3. Progress
    total_duration = (expire_dt - created_dt).total_seconds()
    elapsed_delta = now - created_dt
    elapsed = elapsed_delta.total_seconds()
    elapsed_str = _format_remaining_details(elapsed_delta) if elapsed > 0 else "0мин"
    
    if total_duration > 0:
        percent = (elapsed / total_duration) * 100
    else:
        percent = 100
        
    percent = max(0, min(100, percent))
    percent_str = f"{percent:.1f}%"
    
    # 4. Display Name (prefer user-set name, fall back to email/uuid)
    key_name = key.get('user_key_name') or key.get('name')
    if not key_name:
        # User requested: Key #email_username (sannilo@bot.local -> Ключ #sannilo)
        email = key.get('email') or key.get('key_email') or ""
        if email.endswith("@bot.local"):
            email = email[:-10]
        
        if email:
            key_name = f"Ключ #{email}"
        elif key.get('short_uuid'):
            key_name = f"Ключ #{key.get('short_uuid')}"
        else:
            key_name = f"Ключ #{key.get('key_id')}"
        
    # 5. Subscription URL
    sub_url = key.get('subscription_url') or key.get('key') or ""

    # 6. Limits
    traffic_limit = key.get('limit_bytes')
    traffic_used = key.get('used_bytes', 0)
    
    formatted_used = _format_bytes(traffic_used)
    
    traffic_str = "∞"
    if traffic_limit:
        try:
            t_lim_float = float(traffic_limit)
            if t_lim_float > 0:
                traffic_str = _format_bytes(t_lim_float)
            else:
                traffic_str = "∞"
        except (ValueError, TypeError):
            traffic_str = "∞"
    
    hwid_limit = key.get('limit_ips')
    hwid_usage = key.get('used_ips', 0)
    
    limit_display = "∞"
    if hwid_limit is not None:
        try:
            limit_val = int(hwid_limit)
            if limit_val > 0 and limit_val < 99:
                 limit_display = str(limit_val)
            else:
                 limit_display = "∞"
        except (ValueError, TypeError):
            limit_display = "∞"

    hwid_str = f"{hwid_usage} / {limit_display}"
    
    # Safety: Created Date String
    created_date_str = created_dt.strftime("%d.%m.%Y")

    if days_left > 5:
        status_text = "Активен"
        status_color = "text-emerald-500"
        status_bg = "bg-emerald-500/10"
    elif days_left > 0:
        status_text = "Скоро"
        status_color = "text-yellow-500"
        status_bg = "bg-yellow-500/10"
    else:
        status_text = "Истёк"
        status_color = "text-red-500"
        status_bg = "bg-red-500/10"

    lte_state = _lte_card_state(key)

    return {
        "key_id": key.get('key_id'),
        "name": key_name,
        "expire_date_str": expire_date_str,
        "days_left": days_left,
        "percent_str": percent_str,
        "sub_url": sub_url,
        "expiry_dt": expire_dt,
        "remaining_str": remaining_str,
        "created_date_str": created_date_str,
        "elapsed_str": elapsed_str,
        "traffic_info": f"{formatted_used} / {traffic_str}" + (
            f" (сброс {reset_txt})" if (reset_txt := format_next_traffic_reset_display(key.get("next_traffic_reset_at"))) else ""
        ), 
        "hwid_info": f"{hwid_str} уст.",
        "status_text": status_text,
        "status_color": status_color,
        "status_bg": status_bg,
        "comment_key": key.get('comment_key') or "",
        "host_name": key.get('host_name') or "",
        "user_key_name": key.get('user_key_name') or "",
        "auto_renew": bool(int(key.get('auto_renew') or 0)),
        "lte_info": lte_state.get("lte_info") or "",
        "lte_label": lte_state.get("lte_label") or "LTE",
        "show_lte": bool(lte_state.get("show_lte")),
        "show_lte_topup": bool(lte_state.get("show_lte_topup")),
    }


def _get_key_html(key: dict) -> str:
    data = _process_key_data(key)
    
    html = f"""
        <section
            class="bg-white dark:bg-surface-dark border border-gray-200 dark:border-surface-highlight-dark rounded-2xl p-5 shadow-sm relative overflow-hidden group">
            <div class="absolute -top-10 -right-10 w-32 h-32 bg-primary/20 rounded-full blur-3xl dark:block hidden">
            </div>
            <div class="flex flex-col gap-1 mb-4">
                <!-- Row 1: Status & Date -->
                <div class="flex justify-between items-center h-6">
                    <div class="flex items-center gap-2">
                        <span class="relative flex h-3 w-3">
                            <span
                                class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                            <span class="relative inline-flex rounded-full h-3 w-3 bg-primary"></span>
                        </span>
                        <span class="font-bold text-lg text-gray-900 dark:text-white leading-none">Активна</span>
                    </div>
                    <div class="font-semibold text-sm leading-none text-right">{data['expire_date_str']}</div>
                </div>

                <!-- Row 2: Key Name & Days Left Badge -->
                <div class="flex justify-between items-center h-6">
                    <div class="flex items-center gap-1.5 text-gray-500 dark:text-gray-400 text-sm">
                        <span class="material-symbols-rounded text-base">key</span>
                        <span>{_esc_text(data.get('name'))}</span>
                    </div>
                    <div
                        class="bg-surface-highlight-dark/10 dark:bg-surface-highlight-dark px-2 py-0.5 rounded text-[10px] font-medium text-gray-600 dark:text-gray-300">
                        {data['days_left']} дн.
                    </div>
                </div>
            </div>
            <div class="mt-6">
                <div class="flex justify-between text-xs mb-2">
                    <span class="text-gray-500 dark:text-gray-400">Использовано</span>
                    <span class="font-bold text-primary">{data['percent_str']}</span>
                </div>
                <div class="w-full bg-gray-100 dark:bg-black rounded-full h-2 overflow-hidden">
                    <div class="bg-primary h-2 rounded-full progress-bar shadow-[0_0_10px_rgba(16,185,129,0.5)]" style="width: {data['percent_str']}"></div>
                </div>
            </div>
        </section>
    """
    return html


def _get_profile_card_html(user: dict | None, referral_count: int, keys_count: int, referral_earned: float = 0.0) -> str:
    if not user:
        return ""
        
    user_id = user.get("telegram_id")
    balance = user.get("balance") or 0.0
    reg_date = user.get("registration_date")
    
    # Format currency: 1 240,50 ₽
    balance_str = f"{balance:,.2f}".replace(",", " ").replace(".", ",") + " ₽"
    earned_str = f"{referral_earned:,.2f}".replace(",", " ").replace(".", ",") + " ₽"
    
    # Format date and calculate time since
    reg_date_str = "Unknown"
    time_since_str = ""
    if reg_date:
        try:
             if isinstance(reg_date, str):
                 try:
                    dt = datetime.strptime(reg_date, "%Y-%m-%d %H:%M:%S")
                 except ValueError:
                    dt = datetime.fromisoformat(reg_date)
             else:
                 dt = reg_date
                 
             reg_date_str = dt.strftime("%d.%m.%Y")
             
             # Calculate relative time
             now = get_msk_time().replace(tzinfo=None)
             diff = now - dt.replace(tzinfo=None)
             days = max(0, diff.days)
             
             if days < 31:
                 time_since_str = f"{days} д."
             elif days < 365:
                 m = days // 30
                 d = days % 30
                 time_since_str = f"{m}м. {d}д." if d > 0 else f"{m}м."
             else:
                 y = days // 365
                 rem = days % 365
                 m = rem // 30
                 d = rem % 30
                 bits = [f"{y}г."]
                 if m > 0: bits.append(f"{m}м.")
                 if d > 0: bits.append(f"{d}д.")
                 time_since_str = " ".join(bits)
        except:
             pass

    sync_btn_html = ""
    if isinstance(user_id, int) and str(user_id).startswith("999"):
         bot_username = get_setting("telegram_bot_username") or "bot"
         sync_btn_html = f'''
                    <button type="button" data-sync-telegram="1" data-bot-username="{_esc_text(bot_username)}" class="mt-2 w-full bg-[#0088cc]/20 hover:bg-[#0088cc]/30 text-[#00aaff] border border-[#0088cc]/30 font-bold py-3 rounded-xl text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 shadow-sm">
                        <span class="material-symbols-rounded text-base">sync</span>
                        <span>Синхронизировать с Telegram</span>
                    </button>
         '''

    # also show available referral balance separately if present
    available_ref = user.get("referral_balance") or 0.0
    available_str = f"{available_ref:,.2f}".replace(",", " ").replace(".", ",") + " ₽"

    return f"""
            <!-- Modern Balanced User Card -->
            <div class="glass-card border border-white/10 rounded-[2rem] p-6 relative overflow-hidden shadow-xl">
                <!-- Decoration -->
                <div class="absolute -top-10 -right-10 w-32 h-32 bg-primary/5 rounded-full blur-3xl"></div>

                <div class="flex flex-col gap-5 relative z-10">
                    <!-- Top: ID and Status -->
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div
                                class="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center border border-primary/20">
                                <span class="material-symbols-rounded text-primary">person</span>
                            </div>
                            <div>
                                <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest">ID
                                    пользователя</div>
                                <div class="text-base font-black text-white tracking-tight">#{user_id}</div>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest">Баланс</div>
                            <div id="home-balance" data-balance-display class="text-lg font-black text-primary tracking-tighter">{balance_str}</div>
                        </div>
                    </div>

                    <!-- Middle: Main Stats -->
                    <div class="grid grid-cols-3 gap-2">
                        <div
                            class="bg-white/5 border border-white/5 rounded-2xl p-2.5 flex flex-col items-center justify-center text-center transition-all hover:bg-white/[0.08]">
                            <span class="material-symbols-rounded text-emerald-400 text-sm mb-1 opacity-80">group</span>
                            <div class="text-[9px] text-gray-400 uppercase font-black tracking-tight leading-none mb-1">Рефералы</div>
                            <div class="text-[11px] font-black text-white">{referral_count} чел.</div>
                        </div>
                        <div
                            class="bg-white/5 border border-white/5 rounded-2xl p-2.5 flex flex-col items-center justify-center text-center transition-all hover:bg-white/[0.08]">
                            <span class="material-symbols-rounded text-yellow-400 text-sm mb-1 opacity-80">payments</span>
                            <div class="text-[9px] text-gray-400 uppercase font-black tracking-tight leading-none mb-1">Всего заработано</div>
                            <div class="text-[11px] font-black text-white truncate w-full px-1">{earned_str}</div>
                        </div>
                        <div
                            class="bg-white/5 border border-white/5 rounded-2xl p-2.5 flex flex-col items-center justify-center text-center transition-all hover:bg-white/[0.08]">
                            <span class="material-symbols-rounded text-primary text-sm mb-1 opacity-80">key</span>
                            <div class="text-[9px] text-gray-400 uppercase font-black tracking-tight leading-none mb-1">Ключи</div>
                            <div class="text-[11px] font-black text-white">{keys_count} шт.</div>
                        </div>
                    </div>

                    <!-- Referral available -->
                    <div class="mt-3 text-center">
                        <div class="text-[10px] text-gray-400 uppercase font-black tracking-tight">Доступно к выводу</div>
                        <div class="text-sm font-black text-white">{available_str}</div>
                    </div>

                    <!-- Bottom: Meta Info -->
                    <div class="flex items-center justify-center gap-2 pt-1">
                        <span class="material-symbols-rounded text-[12px] text-gray-600">calendar_today</span>
                        <span class="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Дата
                            регистрации:</span>
                        <span class="text-[10px] text-gray-300 font-black">{reg_date_str} ({time_since_str})</span>
                    </div>

                    {sync_btn_html}
                </div>
            </div>
    """


def _get_key_card_html(key: dict, badge_html: str = "", extra_content_html: str = "") -> str:
    """Render the full key-card block (used for regular keys and, with an extra
    badge/CTA, for not-yet-activated gift keys so both share the same UI)."""
    data = _process_key_data(key)
    kid = int(data["key_id"])
    name = _esc_text(data.get("name"))
    comment = _esc_text(data.get("comment_key") or "")
    sub_url = _esc_text(data.get("sub_url") or "")
    host_name = _esc_text(data.get("host_name") or "")
    expire = _esc_text(data.get("expire_date_str") or "")
    remaining = _esc_text(data.get("remaining_str") or "")
    has_comment = bool(data.get("comment_key"))

    return f"""
        <div class="glass-card border border-white/10 rounded-2xl relative overflow-hidden shadow-lg transition-all hover:border-primary/30 group mb-3" data-key-id="{kid}" data-key-name="{name}">
            <div class="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 pointer-events-none"></div>

            <button class="key-toggle w-full p-3 flex items-center justify-between relative z-10 transition-colors hover:bg-white/5">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 bg-white/5 rounded-xl flex items-center justify-center group-hover:bg-primary/10 transition-colors shrink-0">
                        <span class="material-symbols-rounded text-gray-400 group-hover:text-primary transition-colors text-lg">key</span>
                    </div>
                    
                    <div class="text-left overflow-hidden">
                        <div class="text-xs font-bold text-white group-hover:text-primary transition-colors truncate">{name}</div>
                        <div class="text-[9px] text-gray-500 font-medium uppercase tracking-wider truncate">
                           До {expire} ({remaining})
                        </div>
                    </div>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                     {badge_html}
                     <span class="text-[9px] {data['status_bg']} {data['status_color']} px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">{data['status_text']}</span>
                     <div class="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <span class="material-symbols-rounded text-gray-500 text-sm group-hover:text-white transition-colors rotate-icon">expand_more</span>
                     </div>
                </div>
            </button>

            <div class="key-content px-3 relative z-10 transition-all duration-300"> 
                 <div class="pb-3 pt-2 flex flex-col gap-2 border-t border-white/5">
                 
                     <!-- KEY INFO BLOCK -->
                     <div class="flex flex-col gap-1 px-1 py-1 text-[10px]">
                        <!-- Row 1: Time -->
                        <div class="flex flex-wrap justify-between items-center gap-x-2 gap-y-1 border-b border-white/5 pb-1.5 mb-1.5 opacity-90">
                            <div class="flex items-center gap-1">
                                <span class="text-gray-500 font-medium shrink-0">⏳ Осталось:</span>
                                <span class="text-gray-200 font-mono tracking-tight whitespace-nowrap">{data['remaining_str']}</span>
                            </div>
                            <div class="w-px h-3 bg-white/10"></div>
                            <div class="flex items-center gap-1">
                                <span class="text-gray-500 font-medium shrink-0">➕ Куплен:</span>
                                <span class="text-gray-200 font-mono tracking-tight whitespace-nowrap">{data['elapsed_str']}</span>
                            </div>
                        </div>
                        
                        <!-- Row 2: Limits -->
                        <div class="flex justify-between items-center opacity-90">
                            <div class="flex items-center gap-1.5">
                                <span class="text-gray-500 whitespace-nowrap">🛰 Лимит:</span>
                                <span class="text-gray-300 font-mono whitespace-nowrap">{data['traffic_info']}</span>
                            </div>
                            <div class="w-px h-3 bg-white/10 mx-1"></div>
                            <div class="flex items-center gap-1.5">
                                <span class="text-gray-500 whitespace-nowrap">📱 Лимит:</span>
                                <span class="text-gray-300 font-mono whitespace-nowrap">{data['hwid_info']}</span>
                            </div>
                        </div>
                        {f'''<div class="flex items-center gap-1.5 pt-1 opacity-90">
                            <span class="text-amber-400/80 whitespace-nowrap">💰 {_esc_text(data.get("lte_label") or "LTE")}:</span>
                            <span class="text-gray-300 font-mono whitespace-nowrap">{data["lte_info"]}</span>
                        </div>''' if data.get('show_lte') and data.get('lte_info') else ''}
                     </div>
                 
                     <!-- COMMENTS BLOCK -->
                     <div id="comment-block-{kid}" class="{'hidden' if not has_comment else 'flex'} items-start gap-2 bg-amber-500/8 border border-amber-500/20 rounded-xl px-3 py-2 mb-1 mt-1">
                         <span class="material-symbols-rounded text-amber-400/70 text-sm mt-0.5 shrink-0">sticky_note_2</span>
                         <span id="comment-text-{kid}" class="text-[10px] text-amber-200/80 leading-relaxed break-words">{comment}</span>
                     </div>

                     <div class="flex items-center gap-2 bg-black/20 rounded-xl p-2 border border-white/5 group/copy hover:border-primary/30 transition-colors">
                         <div class="flex-1 min-w-0">
                             <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mb-0.5">Ссылка</div>
                             <div class="text-[10px] text-gray-300 font-mono truncate transition-colors group-hover/copy:text-white">{sub_url}</div>
                         </div>
                         <button type="button" data-key-action="copy-key" data-url="{sub_url}"
                            class="w-7 h-7 rounded-lg bg-white/5 text-white flex items-center justify-center hover:bg-white/10 transition-all active:scale-95 shrink-0 shadow-sm">
                             <span class="material-symbols-rounded text-sm">content_copy</span>
                         </button>
                     </div>

                     <button type="button" data-key-action="open-key" data-url="{sub_url}"
                        class="w-full bg-white text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider shadow-[0_4px_15px_rgba(255,255,255,0.1)] hover:shadow-[0_6px_20px_rgba(255,255,255,0.2)] active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                         <span class="material-symbols-rounded text-sm">bolt</span>
                         <span>Подключить</span>
                     </button>
                     
                     <div class="grid grid-cols-3 gap-2 mt-1">
                         <button type="button" data-key-action="devices" data-key-id="{kid}" data-host="{host_name}"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">devices</span>
                             <span>Устройства</span>
                         </button>
                         <button type="button" data-key-action="rename" data-key-id="{kid}"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit</span>
                             <span>Название</span>
                         </button>
                         <button type="button" data-key-action="comment" data-key-id="{kid}"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit_note</span>
                             <span>Заметка</span>
                         </button>
                     </div>
                     <div class="grid grid-cols-2 gap-2 mt-1">
                         <button type="button" data-key-action="renew" data-key-id="{kid}"
                             class="w-full bg-primary/10 border border-primary/20 text-primary py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-primary/20 active:scale-[0.98] transition-all flex items-center justify-center gap-1">
                             <span class="material-symbols-rounded text-sm">autorenew</span>
                             <span>Продлить</span>
                         </button>
                         <button type="button" id="auto-renew-btn-{kid}" data-key-action="auto-renew" data-key-id="{kid}" data-auto-renew="{'true' if data['auto_renew'] else 'false'}"
                             class="w-full py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider active:scale-[0.98] transition-all flex items-center justify-center gap-1 border {'border-primary/30 text-primary bg-primary/10' if data['auto_renew'] else 'border-white/5 text-white bg-white/5 hover:bg-white/10'}">
                             <span class="material-symbols-rounded text-sm">{'update' if data['auto_renew'] else 'pause_circle'}</span>
                             <span class="auto-renew-label">{'Авто: ВКЛ' if data['auto_renew'] else 'Авто: ВЫКЛ'}</span>
                         </button>
                     </div>
                     {f'''<button type="button" data-key-action="lte-topup" data-key-id="{kid}"
                        class="w-full bg-amber-500/10 border border-amber-500/20 text-amber-300 py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-amber-500/20 active:scale-[0.98] transition-all flex items-center justify-center gap-1 mt-1">
                         <span class="material-symbols-rounded text-sm">bolt</span>
                         <span>Докупить {_esc_text(data.get("lte_label") or "LTE")}</span>
                     </button>''' if data.get('show_lte_topup') else ''}
                     {extra_content_html}
                </div>
            </div>
        </div>
        """


def _key_created_sort_tuple(key: dict) -> tuple:
    """Sort key for newest-purchased-first: created_at desc, then key_id desc."""
    raw = key.get("created_at") or key.get("created_date") or ""
    try:
        created = datetime.strptime(str(raw)[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        created = datetime.min
    try:
        key_id = int(key.get("key_id") or 0)
    except (ValueError, TypeError):
        key_id = 0
    return (created, key_id)


def _sort_keys_newest_first(keys: list) -> list:
    return sorted(keys, key=_key_created_sort_tuple, reverse=True)


def _get_profile_keys_html(keys: list) -> str:
    if not keys:
        return _get_no_key_html()

    html = ""
    for key in keys:
        html += _get_key_card_html(key)
    return html


def _get_setup_keys_html(keys: list) -> str:
    if not keys:
        return _get_no_key_html()
        
    html = ""
    for key in keys:
        data = _process_key_data(key)
        
        if data['days_left'] <= 0:
            continue
        kid = int(data["key_id"])
        name = _esc_text(data.get("name"))
        comment = _esc_text(data.get("comment_key") or "")
        sub_url = _esc_text(data.get("sub_url") or "")
        host_name = _esc_text(data.get("host_name") or "")
        expire = _esc_text(data.get("expire_date_str") or "")
        remaining = _esc_text(data.get("remaining_str") or "")
        has_comment = bool(data.get("comment_key"))
            
        html += f"""
        <div class="glass-card border border-white/10 rounded-2xl relative overflow-hidden shadow-lg transition-all hover:border-primary/30 group mb-3" data-key-id="{kid}" data-key-name="{name}">
            <div class="absolute inset-0 bg-gradient-to-r from-primary/0 via-primary/5 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700 pointer-events-none"></div>

            <button class="key-toggle w-full p-3 flex items-center justify-between relative z-10 transition-colors hover:bg-white/5">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 bg-white/5 rounded-xl flex items-center justify-center group-hover:bg-primary/10 transition-colors shrink-0">
                        <span class="material-symbols-rounded text-gray-400 group-hover:text-primary transition-colors text-lg">key</span>
                    </div>
                    
                    <div class="text-left overflow-hidden">
                        <div class="text-xs font-bold text-white group-hover:text-primary transition-colors truncate">{name}</div>
                        <div class="text-[9px] text-gray-500 font-medium uppercase tracking-wider truncate">
                           До {expire} ({remaining})
                        </div>
                    </div>
                </div>

                <div class="flex items-center gap-2 shrink-0">
                     <span class="text-[9px] {data['status_bg']} {data['status_color']} px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">{data['status_text']}</span>
                     <div class="w-7 h-7 rounded-full bg-white/5 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                        <span class="material-symbols-rounded text-gray-500 text-sm group-hover:text-white transition-colors rotate-icon">expand_more</span>
                     </div>
                </div>
            </button>

            <div class="key-content px-3 relative z-10 transition-all duration-300"> 
                 <div class="pb-3 pt-2 flex flex-col gap-2 border-t border-white/5">
                 
                     <!-- COMMENTS BLOCK -->
                     <div id="comment-block-{kid}" class="{'hidden' if not has_comment else 'flex'} items-start gap-2 bg-amber-500/8 border border-amber-500/20 rounded-xl px-3 py-2 mb-1 mt-1">
                         <span class="material-symbols-rounded text-amber-400/70 text-sm mt-0.5 shrink-0">sticky_note_2</span>
                         <span id="comment-text-{kid}" class="text-[10px] text-amber-200/80 leading-relaxed break-words">{comment}</span>
                     </div>

                     <div class="flex items-center gap-2 bg-black/20 rounded-xl p-2 border border-white/5 group/copy hover:border-primary/30 transition-colors">
                         <div class="flex-1 min-w-0">
                             <div class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mb-0.5">Ссылка</div>
                             <div class="text-[10px] text-gray-300 font-mono truncate transition-colors group-hover/copy:text-white">{sub_url}</div>
                         </div>
                         <button type="button" data-key-action="copy-key" data-url="{sub_url}"
                            class="w-7 h-7 rounded-lg bg-white/5 text-white flex items-center justify-center hover:bg-white/10 transition-all active:scale-95 shrink-0 shadow-sm">
                             <span class="material-symbols-rounded text-sm">content_copy</span>
                         </button>
                     </div>

                     <button type="button" data-key-action="open-key" data-url="{sub_url}"
                        class="w-full bg-white text-black py-2.5 rounded-xl font-bold text-[10px] uppercase tracking-wider shadow-[0_4px_15px_rgba(255,255,255,0.1)] hover:shadow-[0_6px_20px_rgba(255,255,255,0.2)] active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                         <span class="material-symbols-rounded text-sm">bolt</span>
                         <span>Открыть инструкцию</span>
                     </button>
                     
                     <div class="grid grid-cols-3 gap-2 mt-1">
                         <button type="button" data-key-action="devices" data-key-id="{kid}" data-host="{host_name}"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">devices</span>
                             <span>Устройства</span>
                         </button>
                         <button type="button" data-key-action="rename" data-key-id="{kid}"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit</span>
                             <span>Название</span>
                         </button>
                         <button type="button" data-key-action="comment" data-key-id="{kid}"
                             class="w-full bg-white/5 text-white py-2 rounded-xl font-bold text-[10px] uppercase tracking-wider hover:bg-white/10 active:scale-[0.98] transition-all flex items-center justify-center gap-1 border border-white/5 hover:border-white/10">
                             <span class="material-symbols-rounded text-sm">edit_note</span>
                             <span>Заметка</span>
                         </button>
                     </div>
                </div>
            </div>
        </div>
        """
    return html


def _get_renew_keys_html(keys: list, user_id: int | None = None) -> tuple[str, str, str]:
    if not keys:
        return "", "Нет активных ключей", _get_no_key_html()
        
    options_html = '<div class="p-1 flex flex-col gap-0.5">'
    selected_text = ""
    renew_plans_html = ""
    
    for index, key in enumerate(keys):
        data = _process_key_data(key)
        host_name = key.get('host_name', '')
        name = _esc_text(data.get("name"))
        expire = _esc_text(data.get("expire_date_str") or "")
        host_attr = _esc_text(host_name)
        
        is_selected = (index == 0)
        check_class = "text-primary" if is_selected else "text-transparent"
        text_color = "text-white" if is_selected else "text-gray-300"
        icon_color = "text-primary" if is_selected else "text-gray-500"
        
        if is_selected:
            selected_text = f"{name} • До {expire}"

        options_html += f"""
        <button
            class="dropdown-option w-full p-2.5 flex items-center justify-between rounded-lg hover:bg-white/5 transition-colors"
            data-key="#{data['key_id']}" data-name="{name}" data-date="{expire}" data-host="{host_attr}" data-index="{index}">
            <div class="flex items-center gap-2.5 overflow-hidden">
                <span class="material-symbols-rounded {icon_color} text-sm shrink-0">key</span>
                <div class="text-left overflow-hidden">
                    <div class="text-xs font-bold {text_color} truncate">{name}</div>
                    <div class="flex items-center gap-2">
                        <div class="text-[9px] text-gray-400">До {expire}</div>
                        <span class="text-[8px] {data['status_bg']} {data['status_color']} px-1.5 py-0.5 rounded-full font-bold uppercase tracking-wider shrink-0">{data['status_text']}</span>
                    </div>
                </div>
            </div>
            <span class="material-symbols-rounded {check_class} text-xs selected-icon shrink-0">check</span>
        </button>
        """
        
        display_style = "grid" if is_selected else "none"
        desc, grid_html = _build_plans_grid_html(host_name, user_id, f"renew-plans-{index}", display_style)
        
        renew_plans_html += f'<div id="renew-desc-content-{index}" style="display: none;">{desc}</div>'
        renew_plans_html += grid_html
    
    options_html += '</div>'
    
    return options_html, selected_text, renew_plans_html


def _get_no_key_html() -> str:
    return """
        <div class="glass-card border border-white/10 rounded-[2rem] p-5 flex flex-col items-center justify-center text-center shadow-lg mb-3">
            <div class="w-12 h-12 bg-white/5 rounded-2xl flex items-center justify-center mb-3">
                <span class="material-symbols-rounded text-2xl text-gray-500">key_off</span>
            </div>
            <h3 class="text-sm font-black text-white mb-1 tracking-tight">Нет активных ключей</h3>
            <p class="text-[10px] text-gray-400 font-medium leading-tight max-w-[180px]">
                Купите ключ, чтобы начать пользоваться VPN
            </p>
        </div>
    """


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_format_remaining_details",
    "_format_bytes",
    "_process_template_placeholders",
    "_format_bytes_gb",
    "_format_gb_amount",
    "_is_key_without_billing_plan",
    "_resolve_plan_id_for_key",
    "_lte_card_state",
    "_owned_lte_key_and_plan",
    "_process_key_data",
    "_get_key_html",
    "_get_profile_card_html",
    "_get_key_card_html",
    "_key_created_sort_tuple",
    "_sort_keys_newest_first",
    "_get_profile_keys_html",
    "_get_setup_keys_html",
    "_get_renew_keys_html",
    "_get_no_key_html",
]
