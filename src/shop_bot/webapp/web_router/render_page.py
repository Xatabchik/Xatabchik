"""Сборка главной страницы Mini App и корневой маршрут.

Выделено из webapp/handlers.py: определения перенесены побайтово,
порядок регистрации маршрутов сохранён.

Пути к шаблонам и статике считаются от `__file__` на один каталог выше,
чем в исходнике: файл переехал в подпакет, а каталог `webapp/` остался
прежним. Это единственное место, где текст определений изменён.
"""


# Импорт значением, а не через _link_namespace(): эти имена нужны уже в
# момент импорта — в декораторах маршрутов, аннотациях и значениях по
# умолчанию, то есть раньше, чем пакет успевает связать пространства имён.
# Модули-владельцы маршрутов не регистрируют, поэтому их ранний импорт
# порядок маршрутов не сдвигает.
from shop_bot.webapp.web_router._app import app


from fastapi import Request
from fastapi.responses import HTMLResponse
from shop_bot.data_manager.remnawave_repository import (
    get_setting,
    get_user_keys,
    get_msk_time,
    get_webapp_settings,
    get_user,
    get_referral_count,
    get_all_hosts,
    get_plans_for_host,
)
import os
from datetime import datetime
import asyncio
import traceback
from shop_bot.modules import remnawave_api


def _render_banned_page(webapp_settings: dict):
    title = webapp_settings.get("webapp_title") or get_setting("panel_brand_title") or "Xatab VPN"
    logo = webapp_settings.get("webapp_logo") or ""
    icon = webapp_settings.get("webapp_icon") or ""
    
    html = f"""<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>{title}</title>
    <link rel="stylesheet" href="/static/css/app.css">
    <style>
        body {{ font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; }}
        .glass {{ background: rgba(30, 30, 30, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.05); }}
    </style>
</head>
<body class="bg-surface-dark text-white h-screen flex flex-col items-center justify-center p-6 select-none overflow-hidden">
    <div class="fixed inset-0 pointer-events-none">
        <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-primary/10 rounded-full blur-[120px]"></div>
        <div class="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-primary/5 rounded-full blur-[120px]"></div>
    </div>

    <div class="relative z-10 flex flex-col items-center text-center max-w-sm w-full">
        {f'<img src="{logo}" class="h-20 mb-8 drop-shadow-[0_0_20px_rgba(16,185,129,0.3)]">' if logo else f'<div class="w-20 h-20 bg-primary/20 rounded-3xl flex items-center justify-center mb-8 border border-primary/30 shadow-[0_0_30px_rgba(16,185,129,0.2)]"><span class="material-symbols-rounded text-primary text-4xl">block</span></div>'}
        
        <h1 class="text-3xl font-black mb-3 tracking-tight">Доступ ограничен</h1>
        <p class="text-gray-400 font-medium leading-relaxed mb-8">
            Ваш аккаунт был заблокирован за нарушение правил сервиса. Использование функций WebApp временно недоступно.
        </p>

        <div class="glass rounded-[2rem] p-6 w-full border border-red-500/20 shadow-2xl">
            <div class="flex items-center gap-4 text-left">
                <div class="w-12 h-12 bg-red-500/10 rounded-2xl flex items-center justify-center shrink-0 border border-red-500/20">
                    <span class="material-symbols-rounded text-red-500">lock_person</span>
                </div>
                <div>
                    <div class="text-[10px] text-gray-500 uppercase font-black tracking-widest mb-1">Статус аккаунта</div>
                    <div class="text-lg font-black text-red-500 leading-none">ЗАБЛОКИРОВАН</div>
                </div>
            </div>
            
            <div class="mt-6 pt-6 border-t border-white/5">
                <p class="text-[11px] text-gray-500 font-semibold mb-4 text-center">Если вы считаете, что это ошибка, обратитесь в нашу поддержку</p>
                <a href="https://t.me/{get_setting('support_bot_username')}" target="_blank"
                   class="flex items-center justify-center gap-2 w-full bg-white text-black py-4 rounded-2xl font-black text-sm uppercase tracking-wider hover:opacity-90 active:scale-[0.98] transition-all shadow-xl">
                    <span class="material-symbols-rounded text-lg">support_agent</span>
                    <span>Написать в поддержку</span>
                </a>
            </div>
        </div>

        <div class="mt-8 opacity-40 text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
            <span>{title}</span>
            <span class="w-1 h-1 bg-gray-600 rounded-full"></span>
            <span>Security Module</span>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=403)


async def _render_main_page(user_id: int):
    webapp_settings = get_webapp_settings()
    
    # 1. Check if Webapp is enabled
    if not webapp_settings.get("webapp_enabled"):
         return HTMLResponse(content="<h1>Webapp is disabled</h1>", status_code=403)
         
    # 2. Check if user is banned
    user = get_user(user_id)
    if user and user.get('is_banned'):
         return _render_banned_page(webapp_settings)
         
    # Можно использовать webapp_domen для проверок или редиректов если нужно
    # current_domain = webapp_settings.get("webapp_domen")

    key_section = _get_no_key_html()
    profile_card = ""
    profile_keys_list = _get_no_key_html()
    setup_keys_list = _get_no_key_html()
    renew_keys_options = ""
    renew_selected_key = "Нет активных ключей"
    renew_plans_html_data = _get_no_key_html()
    keys = []
    
    if user_id:
        keys = get_user_keys(user_id)
        keys_newest_first = _sort_keys_newest_first(list(keys))
        # Home / renew / setup: soonest expiry first. Keys page: newest purchase first.
        keys_by_expiry = list(keys)
        try:
            keys_by_expiry.sort(key=lambda k: datetime.strptime(k['expiry_date'], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass
            
        now = get_msk_time().replace(tzinfo=None)
        
        # --- FETCH LIVE DATA ONLY FOR ACTIVE KEYS ---
        active_keys = []
        for k in keys_by_expiry:
            try:
                exp = datetime.strptime(k['expiry_date'], "%Y-%m-%d %H:%M:%S")
                if exp > now:
                    active_keys.append(k)
            except: pass

        if active_keys:
            try:
                # --- 1. Fetch Key Details (User info from Host) ---
                details_tasks = []
                for k in active_keys:
                    details_tasks.append(remnawave_api.get_key_details_from_host(k))
                
                details_results = await remnawave_api.gather_limited(details_tasks)
                
                # --- 2. Fetch Subscription Info (Traffic Stats) using UUID from Details ---
                sub_tasks = []
                # Map results to keys to keep order
                key_details_map = {}
                
                for k, res in zip(active_keys, details_results):
                    if isinstance(res, Exception) or not res or not res.get('user'):
                        sub_tasks.append(asyncio.sleep(0, None)) # Skip
                        continue
                        
                    u = res['user']
                    key_details_map[k['key_id']] = u
                    
                    # Update limits from user object immediately
                    if u.get('trafficLimitBytes') is not None:
                        k['limit_bytes'] = u.get('trafficLimitBytes')
                    if u.get('hwidDeviceLimit') is not None:
                        k['limit_ips'] = u.get('hwidDeviceLimit')

                    if not k.get('email') and not k.get('key_email'):
                        api_email = u.get('username') or u.get('email') or ''
                        if api_email:
                            k['email'] = api_email
                            k['key_email'] = api_email
                        
                    # Determine UUID for subscription check
                    # BOT PRIORITY: Use DB UUID first, then API response
                    target_uuid = k.get('remnawave_user_uuid') or u.get('uuid')
                    host = k.get('host_name')
                    
                    if target_uuid:
                        sub_tasks.append(remnawave_api.get_user_by_uuid(str(target_uuid), host_name=host))
                    else:
                        sub_tasks.append(asyncio.sleep(0, None))

                sub_results = await remnawave_api.gather_limited(sub_tasks)
                
                # --- 3. Process Subscription Results ---
                for k, sub_res in zip(active_keys, sub_results):
                    # Try to find traffic in subscription response
                    found_traffic = None
                    if not isinstance(sub_res, Exception) and sub_res and isinstance(sub_res, dict):
                        for key_name in ['usedTrafficBytes', 'trafficUsedBytes', 'traffic_used_bytes', 'usedBytes', 'trafficUsed', 'traffic', 'used_traffic']:
                            val = sub_res.get(key_name)
                            if val is not None:
                                found_traffic = val
                                break
                    
                    if found_traffic is not None:
                        k['used_bytes'] = found_traffic
                    
                    # Fallback: check User Details (u)
                    if 'used_bytes' not in k:
                        u = key_details_map.get(k['key_id'])
                        if u:
                             # Check keys in user object
                             for key_name in ['traffic', 'trafficUsed', 'used_traffic']:
                                 if u.get(key_name) is not None:
                                     try: k['used_bytes'] = int(u.get(key_name)); break
                                     except: pass
                             
                             # Final fallback: sum upload + download
                             if 'used_bytes' not in k:
                                 uploaded = int(u.get('upload') or 0)
                                 downloaded = int(u.get('download') or 0)
                                 k['used_bytes'] = uploaded + downloaded

                    # HWID Usage
                    u = key_details_map.get(k['key_id'])
                    target_uuid = remnawave_api.panel_user_ref_from_payload(u) if u else None
                    if not target_uuid:
                         target_uuid = k.get('remnawave_user_uuid')
                         
                    host = k.get('host_name')
                    email = k.get('key_email') or k.get('email')

                    if target_uuid and host:
                         try:
                              devs = await remnawave_api.get_connected_devices_count(
                                  target_uuid, host_name=host, email=email
                              )
                              if devs and 'total' in devs:
                                   k['used_ips'] = int(devs['total'])
                         except: pass
            except Exception as e:
                logger.error(f"Error fetching live stats: {e}")

        # --- CALCULATE MIN PRICE ---
        min_price_val = 0.0
        try:
            all_hosts = get_all_hosts()
            prices = []
            for h in all_hosts:
                plans = get_plans_for_host(h['host_name'])
                for p in plans:
                    if p.get('is_active'):
                        try:
                            raw_p = float(p.get('price', 0))
                            final_p = calculate_webapp_price(raw_p, user_id)
                            prices.append(final_p)
                        except: continue
            if prices:
                min_price_val = min(prices)
        except Exception as e:
            logger.error(f"Error calculating min price: {e}")

        # --- GENERATE SECTIONS ---
        if keys:
            # For the main monitoring section, show only the soonest active key
            if active_keys:
                key_section = _get_key_html(active_keys[0])
            
            # Renew, Profile and Setup sections get the full list of keys
            # (Setup will filter internally, Profile shows all, Renew now shows all)
            renew_keys_options, renew_selected_key, renew_plans_html_data = _get_renew_keys_html(keys_by_expiry, user_id)
            renew_selected_display = renew_selected_key
            
            profile_keys_list = _get_profile_keys_html(keys_newest_first)
            setup_keys_list = _get_setup_keys_html(keys_by_expiry)
            
        # Profile Stats
        user = get_user(user_id)
        ref_count = get_referral_count(user_id)
        ref_earned = user.get("referral_balance_all") or 0.0
        profile_card = _get_profile_card_html(user, ref_count, len(keys), ref_earned)
    
    p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app.html")
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    
    context = {
        "profile_card": profile_card,
        "key_section": key_section,
        "profile_keys_list": profile_keys_list,
        "setup_keys_list": setup_keys_list,
        "renew_keys_options": renew_keys_options,
        "renew_plans_html_data": renew_plans_html_data,
        "renew_selected_display": renew_selected_display if 'renew_selected_display' in locals() else renew_selected_key,
        "min_price": f"{int(min_price_val)} ₽" if min_price_val > 0 else "0 ₽",
        "webapp_logo": webapp_settings.get("webapp_logo") or "",
        "webapp_icon": webapp_settings.get("webapp_icon") or ""
    }
    
    content = _process_template_placeholders(content, user_id, webapp_settings, context)
    return HTMLResponse(content=content)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user_id: int | None = None, token: str | None = None):
    try:
        # 1. Authorize by Token only (query param / cookie). Never trust bare
        # user_id from the query string — that was an IDOR (CWE-639): anyone
        # could open /?user_id=<victim> and get a rendered session for them.
        resolved_user_id = None
        if token:
            from shop_bot.data_manager import database
            user = database.get_user_by_auth_token(token)
            if user:
                resolved_user_id = user['telegram_id']
        user_id = resolved_user_id

        # 2. If no valid token, serve login.html
        if user_id is None:
            p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "login.html")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Process placeholders for login page too
                webapp_settings = get_webapp_settings()
                context = {
                    "webapp_logo": webapp_settings.get("webapp_logo") or "",
                    "webapp_icon": webapp_settings.get("webapp_icon") or ""
                }
                content = _process_template_placeholders(content, 0, webapp_settings, context)
                return HTMLResponse(content=content)
            else:
                return HTMLResponse(content="<h1>Login page not found</h1>", status_code=404)

        webapp_settings = get_webapp_settings()
        user = get_user(user_id)
        if user and user.get('is_banned'):
            return _render_banned_page(webapp_settings)

        return await _render_main_page(user_id)

    except Exception as e:
        error_details = traceback.format_exc()
        return HTMLResponse(content=f"<h1>500 Internal Server Error</h1><pre>{error_details}</pre>", status_code=500)


# __all__ — имена, которые пакет раскладывает по остальным модулям, чтобы
# обращение по имени внутри функций разрешалось как до разделения
# (см. __init__.py). Значение берётся из текущей привязки модуля, поэтому
# затенение импортом воспроизводится само.
__all__ = [
    "_render_banned_page",
    "_render_main_page",
    "index",
]
