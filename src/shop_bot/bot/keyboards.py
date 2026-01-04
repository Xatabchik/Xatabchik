import logging
import hashlib

from datetime import datetime

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shop_bot.data_manager.remnawave_repository import get_setting
from shop_bot.data_manager.database import get_button_configs

logger = logging.getLogger(__name__)

SUPPORT_URL = "https://t.me/uprav_softmaster95vpn_bot"


def _ru_days(n: int) -> str:
    """Русское склонение слова "день".

    1 день, 2/3/4 дня, 5-20 дней, 21 день, 22 дня, 25 дней, ...
    """
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return "день"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "дня"
    return "дней"

main_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
    resize_keyboard=True
)

def create_main_menu_keyboard(user_keys: list, trial_available: bool, is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if trial_available:
        builder.button(text=(get_setting("btn_trial_text") or "🎁 Попробовать бесплатно"), callback_data="get_trial")
    
    builder.button(text=(get_setting("btn_profile_text") or "👤 Мой профиль"), callback_data="show_profile")

    keys_count = len(user_keys) if user_keys else 0
    buy_text = (get_setting("btn_buy_key_text") or "🛒 Купить ключ")

    # Если у пользователя нет ни одного ключа, вместо «Мои ключи» показываем «Купить ключ».
    # Если ключи есть (активные или неактивные) — показываем «Мои ключи» со счётчиком, как раньше.
    add_separate_buy_button = True
    if keys_count > 0:
        base_my_keys = (get_setting("btn_my_keys_text") or "🔑 Мои ключи")
        builder.button(text=f"{base_my_keys} ({keys_count})", callback_data="manage_keys")
    else:
        builder.button(text=buy_text, callback_data="buy_new_key")
        add_separate_buy_button = False

    if add_separate_buy_button:
        builder.button(text=buy_text, callback_data="buy_new_key")
    builder.button(text=(get_setting("btn_gift_key_text") or "🎁 Подарить"), callback_data="gift_new_key")
    builder.button(text=(get_setting("btn_topup_text") or "💳 Пополнить баланс"), callback_data="top_up_start")
    
    builder.button(text=(get_setting("btn_referral_text") or "🤝 Реферальная программа"), callback_data="show_referral_program")
    

    builder.button(text=(get_setting("btn_support_text") or "🆘 Поддержка"), callback_data="show_help")
    builder.button(text=(get_setting("btn_about_text") or "ℹ️ О проекте"), callback_data="show_about")
    

    builder.button(text=(get_setting("btn_speed_text") or "⚡ Скорость"), callback_data="user_speedtest_last")
    builder.button(text=(get_setting("btn_howto_text") or "❓ Как использовать"), callback_data="howto_vless")
    

    if is_admin:
        builder.button(text=(get_setting("btn_admin_text") or "⚙️ Админка"), callback_data="admin_menu")
    

    # Делаем адаптивную сетку: 2 кнопки в ряд, одиночные — отдельной строкой.
    buttons_total = len(builder.buttons)
    if trial_available:
        buttons_total -= 1
    if is_admin:
        buttons_total -= 1

    layout: list[int] = []
    if trial_available:
        layout.append(1)

    if buttons_total > 0:
        layout.extend([2] * (buttons_total // 2))
        if buttons_total % 2:
            layout.append(1)

    if is_admin:
        layout.append(1)

    builder.adjust(*layout)
    
    return builder.as_markup()

def create_admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="🎁 Выдать ключ", callback_data="admin_gift_key")
    builder.button(text="🌍 Ключи на хосте", callback_data="admin_host_keys")
    builder.button(text="🎟 Промокоды", callback_data="admin_promo_menu")

    # Группы
    builder.button(text="🖥 Система", callback_data="admin_system_menu")
    builder.button(text="⚙️ Настройки", callback_data="admin_settings_menu")

    builder.button(text="📢 Рассылка", callback_data="start_broadcast")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")

    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def create_admin_system_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Тест скорости", callback_data="admin_speedtest")
    builder.button(text="📊 Мониторинг", callback_data="admin_monitor")
    builder.button(text="🗄 Бэкап БД", callback_data="admin_backup_db")
    builder.button(text="♻️ Восстановить БД", callback_data="admin_restore_db")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()



def create_admin_settings_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👮 Администраторы", callback_data="admin_admins_menu")
    builder.button(text="🧾 Тарифы", callback_data="admin_plans")
    builder.button(text="🖥 Хосты", callback_data="admin_hosts_menu")
    builder.button(text="💳 Платежки", callback_data="admin_payments_menu")
    builder.button(text="👥 Рефералка", callback_data="admin_referral")
    builder.button(text="🎁 Триал", callback_data="admin_trial")
    builder.button(text="🔔 Уведомления", callback_data="admin_notifications_menu")
    builder.button(text="🧩 Конструктор кнопок", callback_data="admin_btn_constructor")
    builder.button(text="⬅️ Назад", callback_data="admin_menu")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def create_admin_payments_menu_keyboard(status: dict) -> InlineKeyboardMarkup:
    """Меню выбора платежной системы."""
    def _mark(key: str) -> str:
        return "🟢" if bool(status.get(key)) else "🔴"

    builder = InlineKeyboardBuilder()
    builder.button(text=f"{_mark('yookassa')} YooKassa", callback_data="admin_payments_open:yookassa")
    builder.button(text=f"{_mark('heleket')} Heleket", callback_data="admin_payments_open:heleket")
    builder.button(text=f"{_mark('platega')} Platega", callback_data="admin_payments_open:platega")
    builder.button(text=f"{_mark('cryptobot')} CryptoBot", callback_data="admin_payments_open:cryptobot")
    builder.button(text=f"{_mark('tonconnect')} TonConnect", callback_data="admin_payments_open:tonconnect")
    builder.button(text=f"{_mark('stars')} Telegram Stars", callback_data="admin_payments_open:stars")
    builder.button(text=f"{_mark('yoomoney')} YooMoney", callback_data="admin_payments_open:yoomoney")
    builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def create_admin_payment_detail_keyboard(provider: str, *, flags: dict | None = None) -> InlineKeyboardMarkup:
    """Клавиатура управления конкретной платежкой."""
    flags = flags or {}
    builder = InlineKeyboardBuilder()

    if provider == "yookassa":
        builder.button(text="📧 Почта для чеков", callback_data="admin_payments_set:yookassa:receipt_email")
        builder.button(text="🆔 Shop ID", callback_data="admin_payments_set:yookassa:shop_id")
        builder.button(text="🔑 Secret Key", callback_data="admin_payments_set:yookassa:secret_key")
        sbp_on = bool(flags.get("sbp_enabled"))
        builder.button(text=("🔴 СБП: выключить" if sbp_on else "🟢 СБП: включить"), callback_data="admin_payments_toggle:sbp")
        builder.adjust(2, 1, 1)
    elif provider == "cryptobot":
        builder.button(text="🔑 Token", callback_data="admin_payments_set:cryptobot:token")
        builder.adjust(1)
    elif provider == "heleket":
        builder.button(text="🆔 Merchant ID", callback_data="admin_payments_set:heleket:merchant_id")
        builder.button(text="🔑 API Key", callback_data="admin_payments_set:heleket:api_key")
        builder.button(text="🌐 Домен", callback_data="admin_payments_set:heleket:domain")
        builder.adjust(2, 1)
    elif provider == "platega":
        builder.button(text="🌐 Base URL", callback_data="admin_payments_set:platega:base_url")
        builder.button(text="🆔 Merchant ID", callback_data="admin_payments_set:platega:merchant_id")
        builder.button(text="🔑 Secret", callback_data="admin_payments_set:platega:secret")
        builder.button(text="⚙️ Active methods", callback_data="admin_payments_set:platega:active_methods")
        builder.adjust(2, 2)
    elif provider == "tonconnect":
        builder.button(text="👛 TON Wallet", callback_data="admin_payments_set:tonconnect:wallet")
        builder.button(text="🔑 TonAPI Key", callback_data="admin_payments_set:tonconnect:tonapi")
        builder.adjust(2)
    elif provider == "stars":
        stars_on = bool(flags.get("stars_enabled"))
        builder.button(text=("🔴 Stars: выключить" if stars_on else "🟢 Stars: включить"), callback_data="admin_payments_toggle:stars")
        builder.button(text="⭐ Коэф. (⭐ за 1₽)", callback_data="admin_payments_set:stars:ratio")
        builder.adjust(1, 1)
    elif provider == "yoomoney":
        ym_on = bool(flags.get("yoomoney_enabled"))
        builder.button(text=("🔴 YooMoney: выключить" if ym_on else "🟢 YooMoney: включить"), callback_data="admin_payments_toggle:yoomoney")
        builder.button(text="👛 Кошелёк", callback_data="admin_payments_set:yoomoney:wallet")
        builder.button(text="🔐 Секрет уведомлений", callback_data="admin_payments_set:yoomoney:secret")
        builder.button(text="🔑 API Token", callback_data="admin_payments_set:yoomoney:api_token")
        builder.button(text="🆔 client_id", callback_data="admin_payments_set:yoomoney:client_id")
        builder.button(text="🔑 client_secret", callback_data="admin_payments_set:yoomoney:client_secret")
        builder.button(text="↩️ redirect_uri", callback_data="admin_payments_set:yoomoney:redirect_uri")
        builder.button(text="✅ Проверить токен", callback_data="admin_payments_yoomoney_check")
        builder.adjust(1, 2, 2, 2, 1)

    builder.button(text="⬅️ Назад", callback_data="admin_payments_menu")
    return builder.as_markup()


def create_admin_payments_cancel_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=back_callback)
    return builder.as_markup()


def create_admin_referral_settings_keyboard(
    *,
    enabled: bool,
    days_bonus_enabled: bool,
    reward_type: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    toggle_text = "🔴 Выключить рефералку" if enabled else "🟢 Включить рефералку"
    builder.button(text=toggle_text, callback_data="admin_referral_toggle")

    days_text = "⏳ Отключить бонус +1 день" if days_bonus_enabled else "⏳ Включить бонус +1 день"
    builder.button(text=days_text, callback_data="admin_referral_toggle_days_bonus")

    reward_titles = {
        "percent_purchase": "💹 Тип: % от покупки",
        "fixed_purchase": "💰 Тип: фикс. сумма за покупку",
        "fixed_start_referrer": "🎁 Тип: стартовый бонус при старте",
    }
    builder.button(
        text=reward_titles.get(reward_type, "🎁 Тип начисления"),
        callback_data="admin_referral_set_type",
    )

    builder.button(text="📊 Изменить % за покупку", callback_data="admin_referral_set_percent")
    builder.button(text="💵 Изменить фикс. сумму", callback_data="admin_referral_set_fixed_amount")
    builder.button(text="💰 Изменить стартовый бонус", callback_data="admin_referral_set_start_bonus")
    builder.button(text="🎟 Изменить скидку новому", callback_data="admin_referral_set_discount")
    builder.button(text="💳 Мин. сумма для вывода", callback_data="admin_referral_set_min_withdrawal")

    builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")

    builder.adjust(2, 1, 2, 2, 1, 1)
    return builder.as_markup()


def create_admin_referral_type_keyboard(current_type: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = [
        ("percent_purchase", "💹 % от покупки"),
        ("fixed_purchase", "💰 Фикс. сумма за покупку"),
        ("fixed_start_referrer", "🎁 Стартовый бонус при старте"),
    ]
    for value, title in options:
        prefix = "✅ " if value == current_type else ""
        builder.button(
            text=f"{prefix}{title}",
            callback_data=f"admin_referral_type:{value}",
        )
    builder.button(text="⬅️ Назад", callback_data="admin_referral")
    builder.adjust(1)
    return builder.as_markup()


# === Hosts management (admin) ===

def _host_digest(host_name: str) -> str:
    """Safe stable digest for callback_data."""
    try:
        # Telegram callback_data limit is 64 bytes. Some action prefixes are long,
        # so we keep the digest short enough to always fit.
        return hashlib.sha1((host_name or '').encode('utf-8', 'ignore')).hexdigest()[:12]
    except Exception:
        return hashlib.sha1(str(host_name).encode('utf-8', 'ignore')).hexdigest()[:12]


def create_admin_hosts_menu_keyboard(hosts: list[dict]) -> InlineKeyboardMarkup:
    """Hosts list + add button."""
    builder = InlineKeyboardBuilder()

    if hosts:
        for h in hosts:
            name = h.get('host_name') or '—'
            digest = _host_digest(str(name))
            builder.button(text=f"🖥 {name}", callback_data=f"admin_hosts_open:{digest}")
    else:
        builder.button(text="Хостов нет", callback_data="noop")

    builder.button(text="➕ Добавить хост", callback_data="admin_hosts_add")
    builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")

    rows = [1] * (len(hosts) if hosts else 1)
    rows.extend([1, 1])
    builder.adjust(*rows)
    return builder.as_markup()


def create_admin_host_manage_keyboard(host_digest: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Переименовать", callback_data=f"admin_hosts_rename:{host_digest}")
    builder.button(text="🌐 URL панели", callback_data=f"admin_hosts_set_url:{host_digest}")
    builder.button(text="🔗 Ссылка подписки", callback_data=f"admin_hosts_set_sub:{host_digest}")

    builder.button(text="⚙️ Remnawave (URL)", callback_data=f"admin_hosts_set_rmw_url:{host_digest}")
    builder.button(text="🔐 Remnawave (Token)", callback_data=f"admin_hosts_set_rmw_token:{host_digest}")
    builder.button(text="🧩 Squad UUID", callback_data=f"admin_hosts_set_squad:{host_digest}")

    builder.button(text="🔌 SSH (speedtest)", callback_data=f"admin_hosts_set_ssh:{host_digest}")
    builder.button(text="🧾 Тарифы", callback_data=f"admin_hosts_to_plans:{host_digest}")

    builder.button(text="🗑 Удалить хост", callback_data=f"admin_hosts_delete:{host_digest}")
    builder.button(text="⬅️ К списку хостов", callback_data="admin_hosts_menu")

    builder.adjust(2, 1, 2, 1, 1, 1)
    return builder.as_markup()


def create_admin_hosts_cancel_keyboard(back_cb: str = "admin_hosts_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=back_cb)
    builder.adjust(1)
    return builder.as_markup()


def create_admin_hosts_delete_confirm_keyboard(host_digest: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"admin_hosts_delete_confirm:{host_digest}")
    builder.button(text="❌ Отмена", callback_data=f"admin_hosts_open:{host_digest}")
    builder.adjust(1)
    return builder.as_markup()



def create_admin_trial_settings_keyboard(
    trial_enabled: bool,
    *,
    days: int | None = None,
    traffic_text: str | None = None,
    devices_text: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔴 Выключить" if trial_enabled else "🟢 Включить"
    builder.button(text=f"{toggle_text} триал", callback_data="admin_trial_toggle")

    days_label = f"⏳ Дни: {days}" if days is not None else "⏳ Дни"
    traffic_label = f"📶 Трафик: {traffic_text}" if traffic_text else "📶 Лимит трафика (ГБ)"
    devices_label = f"📱 Устройства: {devices_text}" if devices_text else "📱 Лимит устройств"

    builder.button(text=days_label, callback_data="admin_trial_set_days")
    builder.button(text=traffic_label, callback_data="admin_trial_set_traffic")
    builder.button(text=devices_label, callback_data="admin_trial_set_devices")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")
    builder.adjust(1, 2, 1, 1)
    return builder.as_markup()

def create_admin_notifications_settings_keyboard(
    *,
    enabled: bool,
    interval_hours: float,
) -> InlineKeyboardMarkup:
    """Настройки уведомлений о неиспользовании трафика."""
    builder = InlineKeyboardBuilder()

    toggle_text = "🔕 Выключить уведомления" if enabled else "🔔 Включить уведомления"
    builder.button(text=toggle_text, callback_data="admin_inactive_reminder_toggle")

    interval_label = f"⏱ Интервал: {interval_hours:g} ч"
    builder.button(text=interval_label, callback_data="admin_inactive_reminder_set_interval")

    builder.button(text="⬅️ Назад", callback_data="admin_settings_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()



def create_admin_plans_host_menu_keyboard(plans: list[dict] | None = None) -> InlineKeyboardMarkup:
    """Меню тарифов для выбранного хоста (админка).

    Если переданы планы — отображает их как inline-кнопки.
    """
    builder = InlineKeyboardBuilder()

    if plans:
        for p in plans:
            try:
                pid = int(p.get("plan_id"))
            except Exception:
                continue
            name = str(p.get("plan_name") or "—")
            months = p.get("months")
            duration_days = p.get("duration_days")
            price = p.get("price")
            is_active = int(p.get("is_active", 1) or 0) == 1

            # duration label
            dur_txt = "—"
            try:
                dd = int(duration_days) if duration_days is not None else 0
            except Exception:
                dd = 0
            if dd and dd > 0:
                dur_txt = f"{dd}д"
            else:
                try:
                    dur_txt = f"{int(months)}м" if months is not None else "—"
                except Exception:
                    dur_txt = str(months or "—")

            try:
                price_txt = f"{float(price):.0f}₽"
            except Exception:
                price_txt = str(price or "—")

            prefix = "✅" if is_active else "🚫"
            text = f"{prefix} {name} • {dur_txt} • {price_txt}"
            builder.button(text=text, callback_data=f"admin_plans_open_{pid}")

        builder.adjust(1)

    builder.button(text="➕ Добавить тариф", callback_data="admin_plans_add")
    builder.button(text="⬅️ К выбору хоста", callback_data="admin_plans_back_to_hosts")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def create_admin_plan_manage_keyboard(plan: dict) -> InlineKeyboardMarkup:
    plan_id = plan.get("plan_id")
    is_active = int(plan.get("is_active", 1) or 0) == 1
    toggle_text = "🚫 Скрыть" if is_active else "✅ Активировать"

    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Название", callback_data="admin_plan_edit_name")
    builder.button(text="⏳ Срок", callback_data="admin_plan_edit_duration")
    builder.button(text="💰 Цена", callback_data="admin_plan_edit_price")
    builder.button(text="📶 Трафик (ГБ)", callback_data="admin_plan_edit_traffic")
    builder.button(text="📱 Устройства", callback_data="admin_plan_edit_devices")
    builder.button(text=toggle_text, callback_data="admin_plan_toggle_active")
    builder.button(text="🗑 Удалить", callback_data="admin_plan_delete")
    builder.button(text="⬅️ Назад", callback_data="admin_plans_back_to_host_menu")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()



def create_admin_plans_duration_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор единиц срока тарифа при создании."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 В месяцах", callback_data="admin_plans_duration_months")
    builder.button(text="📆 В днях", callback_data="admin_plans_duration_days")
    builder.button(text="⬅️ Назад", callback_data="admin_plans_back_to_host_menu")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 2)
    return builder.as_markup()


def create_admin_plan_duration_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор единиц срока тарифа при редактировании."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 В месяцах", callback_data="admin_plan_duration_months")
    builder.button(text="📆 В днях", callback_data="admin_plan_duration_days")
    builder.button(text="⬅️ Назад", callback_data="admin_plan_back")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 2)
    return builder.as_markup()

def create_admin_plan_delete_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data="admin_plan_delete_confirm")
    builder.button(text="❌ Отмена", callback_data="admin_plan_delete_cancel")
    builder.adjust(2)
    return builder.as_markup()



def create_admin_plan_edit_flow_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_plan_back")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2)
    return builder.as_markup()


def create_admin_plans_flow_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="admin_plans_back_to_host_menu")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2)
    return builder.as_markup()

def create_admins_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить админа", callback_data="admin_add_admin")
    builder.button(text="➖ Снять админа", callback_data="admin_remove_admin")
    builder.button(text="📋 Список админов", callback_data="admin_view_admins")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")
    builder.adjust(2, 2)
    return builder.as_markup()

def create_admin_users_keyboard(users: list[dict], page: int = 0, page_size: int = 10) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size
    for u in users[start:end]:
        user_id = u.get('telegram_id') or u.get('user_id') or u.get('id')
        username = u.get('username') or '—'
        title = f"{user_id} • @{username}" if username != '—' else f"{user_id}"
        builder.button(text=title, callback_data=f"admin_view_user_{user_id}")

    total = len(users)
    have_prev = page > 0
    have_next = end < total
    if have_prev:
        builder.button(text="⬅️ Назад", callback_data=f"admin_users_page_{page-1}")
    if have_next:
        builder.button(text="Вперёд ➡️", callback_data=f"admin_users_page_{page+1}")
    builder.button(text="🔍 Поиск", callback_data="admin_users_search")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")

    rows = [1] * len(users[start:end])
    tail = []
    if have_prev or have_next:
        tail.append(2 if (have_prev and have_next) else 1)
    tail.append(2)
    builder.adjust(*(rows + tail if rows else ([2] if (have_prev or have_next) else []) + [2]))
    return builder.as_markup()

def create_admin_user_actions_keyboard(user_id: int, is_banned: bool | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Начислить баланс", callback_data=f"admin_add_balance_{user_id}")
    builder.button(text="➖ Списать баланс", callback_data=f"admin_deduct_balance_{user_id}")
    builder.button(text="🎁 Выдать ключ", callback_data=f"admin_gift_key_{user_id}")
    builder.button(text="🤝 Рефералы пользователя", callback_data=f"admin_user_referrals_{user_id}")
    if is_banned is True:
        builder.button(text="✅ Разбанить", callback_data=f"admin_unban_user_{user_id}")
    else:
        builder.button(text="🚫 Забанить", callback_data=f"admin_ban_user_{user_id}")
    builder.button(text="✏️ Ключи пользователя", callback_data=f"admin_user_keys_{user_id}")
    builder.button(text="🗑 Удалить пользователя", callback_data=f"admin_delete_user_{user_id}")
    builder.button(text="⬅️ К списку", callback_data="admin_users")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")

    builder.adjust(2, 2, 2, 1, 2)
    return builder.as_markup()

def create_admin_user_keys_keyboard(user_id: int, keys: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if keys:
        for k in keys:
            kid = k.get('key_id')
            host = k.get('host_name') or '—'
            email = k.get('key_email') or '—'
            title = f"#{kid} • {host} • {email[:20]}"
            builder.button(text=title, callback_data=f"admin_edit_key_{kid}")
    else:
        builder.button(text="Ключей нет", callback_data="noop")
    builder.button(text="⬅️ Назад", callback_data=f"admin_view_user_{user_id}")
    builder.adjust(1)
    return builder.as_markup()

def create_admin_key_actions_keyboard(key_id: int, user_id: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить дни", callback_data=f"admin_key_extend_{key_id}")
    builder.button(text="🗑 Удалить ключ", callback_data=f"admin_key_delete_{key_id}")
    builder.button(text="⬅️ Назад к ключам", callback_data=f"admin_key_back_{key_id}")
    if user_id is not None:
        builder.button(text="👤 Перейти к пользователю", callback_data=f"admin_view_user_{user_id}")
        builder.adjust(2, 2)
    else:
        builder.adjust(2, 1)
    return builder.as_markup()

def create_admin_delete_key_confirm_keyboard(key_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить удаление", callback_data=f"admin_key_delete_confirm_{key_id}")
    builder.button(text="❌ Отмена", callback_data=f"admin_key_delete_cancel_{key_id}")
    builder.adjust(1)
    return builder.as_markup()

def create_cancel_keyboard(callback: str = "admin_cancel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=callback)
    return builder.as_markup()


def create_admin_cancel_keyboard() -> InlineKeyboardMarkup:
    return create_cancel_keyboard("admin_cancel")


def create_admin_promo_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать промокод", callback_data="admin_promo_create")
    builder.button(text="📋 Список промокодов", callback_data="admin_promo_list")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()


def create_admin_promo_discount_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="% Процент", callback_data="admin_promo_discount_percent")
    builder.button(text="₽ Фиксированная", callback_data="admin_promo_discount_amount")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()

def create_admin_promo_code_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Сгенерировать автоматически", callback_data="admin_promo_code_auto")
    builder.button(text="✍️ Ввести вручную", callback_data="admin_promo_code_custom")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1, 1, 1)
    return builder.as_markup()

def create_admin_promo_limit_keyboard(kind: str) -> InlineKeyboardMarkup:

    prefix = "admin_promo_limit_total_" if kind == "total" else "admin_promo_limit_user_"
    builder = InlineKeyboardBuilder()
    builder.button(text="♾ Без лимита", callback_data=f"{prefix}inf")
    for v in (1, 5, 10, 50, 100):
        builder.button(text=str(v), callback_data=f"{prefix}{v}")
    builder.button(text="✍️ Другое число", callback_data=f"{prefix}custom")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 3, 1, 1)
    return builder.as_markup()

def create_admin_promo_valid_from_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ Сейчас", callback_data="admin_promo_valid_from_now")
    builder.button(text="🗓 Сегодня 00:00", callback_data="admin_promo_valid_from_today")
    builder.button(text="🗓 Завтра 00:00", callback_data="admin_promo_valid_from_tomorrow")
    builder.button(text="➡️ Пропустить", callback_data="admin_promo_valid_from_skip")
    builder.button(text="✍️ Другая дата", callback_data="admin_promo_valid_from_custom")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def create_admin_promo_valid_until_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="+1 день", callback_data="admin_promo_valid_until_plus1d")
    builder.button(text="+7 дней", callback_data="admin_promo_valid_until_plus7d")
    builder.button(text="+30 дней", callback_data="admin_promo_valid_until_plus30d")
    builder.button(text="➡️ Пропустить", callback_data="admin_promo_valid_until_skip")
    builder.button(text="✍️ Другая дата", callback_data="admin_promo_valid_until_custom")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(3, 2, 1)
    return builder.as_markup()

def create_admin_promo_description_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Пропустить", callback_data="admin_promo_desc_skip")
    builder.button(text="✍️ Ввести текст", callback_data="admin_promo_desc_custom")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    return builder.as_markup()

def create_broadcast_options_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить кнопку", callback_data="broadcast_add_button")
    builder.button(text="➡️ Пропустить", callback_data="broadcast_skip_button")
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    builder.adjust(2, 1)
    return builder.as_markup()

def create_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить всем", callback_data="confirm_broadcast")
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    builder.adjust(2)
    return builder.as_markup()

def create_broadcast_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    return builder.as_markup()

def create_about_keyboard(channel_url: str | None, terms_url: str | None, privacy_url: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if channel_url:
        builder.button(text="📰 Наш канал", url=channel_url)
    if terms_url:
        builder.button(text="📄 Условия использования", url=terms_url)
    if privacy_url:
        builder.button(text="🔒 Политика конфиденциальности", url=privacy_url)
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()
    
def create_support_keyboard(support_user: str | None = None) -> InlineKeyboardMarkup:
    """Кнопка техподдержки (всегда ведёт на фиксированный URL)."""
    builder = InlineKeyboardBuilder()
    builder.button(text=(get_setting("btn_support_text") or "🆘 Поддержка"), url=SUPPORT_URL)
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_support_bot_link_keyboard(support_bot_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🆘 Открыть поддержку", url=SUPPORT_URL)
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_inactive_usage_reminder_keyboard(connection_string: str | None) -> InlineKeyboardMarkup:
    """Клавиатура для напоминания, если пользователь не подключил устройство."""
    builder = InlineKeyboardBuilder()

    if connection_string:
        builder.button(text="🔗 Подключить устройство", url=connection_string)
    else:
        # fallback: открыть список ключей
        builder.button(text="🔗 Подключить устройство", callback_data="manage_keys")

    builder.button(text="🆘 Поддержка", url=SUPPORT_URL)
    builder.button(text="🏠 Личный кабинет", callback_data="back_to_main_menu")

    builder.adjust(1)
    return builder.as_markup()

def create_support_menu_keyboard(has_external: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Новое обращение", callback_data="support_new_ticket")
    builder.button(text="📨 Мои обращения", callback_data="support_my_tickets")
    if has_external:
        builder.button(text="🆘 Внешняя поддержка", callback_data="support_external")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_tickets_list_keyboard(tickets: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if tickets:
        for t in tickets:
            title = f"#{t['ticket_id']} • {t.get('status','open')}"
            if t.get('subject'):
                title += f" • {t['subject'][:20]}"
            builder.button(text=title, callback_data=f"support_view_{t['ticket_id']}")
    builder.button(text="⬅️ Назад", callback_data="support_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_ticket_actions_keyboard(ticket_id: int, is_open: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_open:
        builder.button(text="💬 Ответить", callback_data=f"support_reply_{ticket_id}")
        builder.button(text="✅ Закрыть", callback_data=f"support_close_{ticket_id}")
    builder.button(text="⬅️ К списку", callback_data="support_my_tickets")
    builder.adjust(1)
    return builder.as_markup()

def create_host_selection_keyboard(hosts: list, action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for host in hosts:
        callback_data = f"select_host_{action}_{host['host_name']}"
        builder.button(text=host['host_name'], callback_data=callback_data)
    builder.button(text="⬅️ Назад", callback_data="manage_keys" if action == 'new' else "back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_plans_keyboard(plans: list[dict], action: str, host_name: str, key_id: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        callback_data = f"buy_{host_name}_{plan['plan_id']}_{action}_{key_id}"

        # Показываем только дни (duration_days, иначе months*30)
        days = 0
        try:
            days = int(plan.get('duration_days') or 0)
        except Exception:
            days = 0

        if not days:
            try:
                months = int(plan.get('months') or 0)
            except Exception:
                months = 0
            if months:
                days = months * 30

        dur_txt = f"{days} {_ru_days(days)}" if days else "—"

        try:
            price_val = float(plan.get('price') or 0)
        except Exception:
            price_val = 0.0

        # Без названия тарифа, разделитель '-'
        builder.button(text=f"{dur_txt} - {price_val:.0f} RUB", callback_data=callback_data)

    back_callback = "manage_keys" if action == "extend" else "buy_new_key"
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def create_skip_email_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➡️ Продолжить без почты", callback_data="skip_email")
    builder.button(text="⬅️ Назад к тарифам", callback_data="back_to_plans")
    builder.adjust(1)
    return builder.as_markup()

def create_payment_method_keyboard(
    payment_methods: dict,
    action: str,
    key_id: int,
    show_balance: bool | None = None,
    main_balance: float | None = None,
    price: float | None = None,
    promo_applied: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()


    pm = {
        "yookassa": bool((get_setting("yookassa_shop_id") or "") and (get_setting("yookassa_secret_key") or "")),
        "heleket": bool((get_setting("heleket_merchant_id") or "") and (get_setting("heleket_api_key") or "")),
        "platega": bool((get_setting("platega_merchant_id") or "") and (get_setting("platega_secret") or "")),
        "cryptobot": bool(get_setting("cryptobot_token") or ""),
        "tonconnect": bool((get_setting("ton_wallet_address") or "") and (get_setting("tonapi_key") or "")),
        "yoomoney": ((get_setting("yoomoney_enabled") or "false").strip().lower() == "true"),

        "stars": ((get_setting("stars_enabled") or "false").strip().lower() == "true"),
    }


    if show_balance:
        label = "💼 Оплатить с баланса"
        if main_balance is not None:
            try:
                label += f" ({main_balance:.0f} RUB)"
            except Exception:
                pass
        builder.button(text=label, callback_data="pay_balance")


    if pm.get("yookassa"):
        if (get_setting("sbp_enabled") or '').strip().lower() in ('true','1','on','yes','y'):
            builder.button(text="🏦 СБП / Банковская карта", callback_data="pay_yookassa")
        else:
            builder.button(text="🏦 Банковская карта", callback_data="pay_yookassa")

    if pm.get("platega"):
        builder.button(text="💳 Platega", callback_data="pay_platega")



    if pm.get("cryptobot"):
        builder.button(text="💎 Криптовалюта", callback_data="pay_cryptobot")
    elif pm.get("heleket"):
        builder.button(text="💎 Криптовалюта", callback_data="pay_heleket")
    if pm.get("tonconnect"):
        callback_data_ton = "pay_tonconnect"
        logger.info(f"Creating TON button with callback_data: '{callback_data_ton}'")
        builder.button(text="🪙 TON Connect", callback_data=callback_data_ton)
    if pm.get("stars"):
        builder.button(text="⭐ Telegram Stars", callback_data="pay_stars")
    if pm.get("yoomoney"):
        builder.button(text="🏦 Банковская карта", callback_data="pay_yoomoney")


    if not promo_applied:
        builder.button(text="🎟 Ввести промокод", callback_data="enter_promo_code")

    builder.button(text="⬅️ Назад", callback_data="back_to_email_prompt")
    builder.adjust(1)
    return builder.as_markup()

def create_ton_connect_keyboard(connect_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Открыть кошелек", url=connect_url)
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", url=payment_url)
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_yoomoney_payment_keyboard(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", url=payment_url)
    builder.button(text="🔄 Проверить оплату", callback_data=f"check_pending:{payment_id}")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_platega_payment_keyboard(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", url=payment_url)
    builder.button(text="🔄 Проверить оплату", callback_data=f"check_platega:{payment_id}")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()


def create_cryptobot_payment_keyboard(payment_url: str, invoice_id: int | str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Перейти к оплате", url=payment_url)
    builder.button(text="🔄 Проверить оплату", callback_data=f"check_crypto_invoice:{invoice_id}")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_topup_payment_method_keyboard(payment_methods: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    pm = {
        "yookassa": bool((get_setting("yookassa_shop_id") or "") and (get_setting("yookassa_secret_key") or "")),
        "heleket": bool((get_setting("heleket_merchant_id") or "") and (get_setting("heleket_api_key") or "")),
        "platega": bool((get_setting("platega_merchant_id") or "") and (get_setting("platega_secret") or "")),
        "cryptobot": bool(get_setting("cryptobot_token") or ""),
        "tonconnect": bool((get_setting("ton_wallet_address") or "") and (get_setting("tonapi_key") or "")),
        "yoomoney": ((get_setting("yoomoney_enabled") or "false").strip().lower() == "true"),
        "stars": ((get_setting("stars_enabled") or "false").strip().lower() == "true"),
    }

    if pm.get("yookassa"):
        if (get_setting("sbp_enabled") or '').strip().lower() in ('true','1','on','yes','y'):
            builder.button(text="🏦 СБП / Банковская карта", callback_data="topup_pay_yookassa")
        else:
            builder.button(text="🏦 Банковская карта", callback_data="topup_pay_yookassa")
    if pm.get("platega"):
        builder.button(text="💳 Platega", callback_data="topup_pay_platega")


    if pm.get("cryptobot"):
        builder.button(text="💎 Криптовалюта", callback_data="topup_pay_cryptobot")
    elif pm.get("heleket"):
        builder.button(text="💎 Криптовалюта", callback_data="topup_pay_heleket")
    if pm.get("tonconnect"):
        builder.button(text="🪙 TON Connect", callback_data="topup_pay_tonconnect")
    if pm.get("stars"):
        builder.button(text="⭐ Telegram Stars", callback_data="topup_pay_stars")
    if pm.get("yoomoney"):
        builder.button(text="🏦 Банковская карта", callback_data="topup_pay_yoomoney")

    builder.button(text="⬅️ Назад", callback_data="show_profile")
    builder.adjust(1)
    return builder.as_markup()

def create_keys_management_keyboard(keys: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if keys:
        for i, key in enumerate(keys):
            expiry_date = datetime.fromisoformat(key['expiry_date'])
            status_icon = "✅" if expiry_date > datetime.now() else "❌"
            host_name = key.get('host_name', 'Неизвестный хост')
            button_text = f"{status_icon} Ключ #{i+1} ({host_name}) (до {expiry_date.strftime('%d.%m.%Y')})"
            builder.button(text=button_text, callback_data=f"show_key_{key['key_id']}")
    builder.button(text=(get_setting("btn_buy_key_text") or "🛒 Купить ключ"), callback_data="buy_new_key")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_key_info_keyboard(key_id: int, connection_string: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Продлить этот ключ", callback_data=f"extend_key_{key_id}")
    if connection_string:
        builder.button(text="🔗 Подключить устройство", url=connection_string)
    builder.button(text="📱 Показать QR-код", callback_data=f"show_qr_{key_id}")
    builder.button(text="⬅️ Назад к списку ключей", callback_data="manage_keys")
    builder.adjust(1)
    return builder.as_markup()
def create_howto_vless_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Android", callback_data="howto_android")
    builder.button(text="📱 iOS", callback_data="howto_ios")
    builder.button(text="💻 Windows", callback_data="howto_windows")
    builder.button(text="🐧 Linux", callback_data="howto_linux")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def create_howto_vless_keyboard_key(key_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Android", callback_data="howto_android")
    builder.button(text="📱 iOS", callback_data="howto_ios")
    builder.button(text="💻 Windows", callback_data="howto_windows")
    builder.button(text="🐧 Linux", callback_data="howto_linux")
    builder.button(text="⬅️ Назад к ключу", callback_data=f"show_key_{key_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def create_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    return builder.as_markup()

def create_profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=(get_setting("btn_topup_text") or "💳 Пополнить баланс"), callback_data="top_up_start")
    builder.button(text=(get_setting("btn_referral_text") or "🤝 Реферальная программа"), callback_data="show_referral_program")
    builder.button(text=(get_setting("btn_back_to_menu_text") or "⬅️ Назад в меню"), callback_data="back_to_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def create_welcome_keyboard(channel_url: str | None, is_subscription_forced: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if channel_url and is_subscription_forced:
        builder.button(text="📢 Перейти в канал", url=channel_url)
        builder.button(text="✅ Я подписался", callback_data="check_subscription_and_agree")
    elif channel_url:
        builder.button(text="📢 Наш канал (не обязательно)", url=channel_url)
        builder.button(text="✅ Принимаю условия", callback_data="check_subscription_and_agree")
    else:
        builder.button(text="✅ Принимаю условия", callback_data="check_subscription_and_agree")
        
    builder.adjust(1)
    return builder.as_markup()

def get_main_menu_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="🏠 В главное меню", callback_data="show_main_menu")

def get_buy_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_vpn")


def create_admin_users_pick_keyboard(users: list[dict], page: int = 0, page_size: int = 10, action: str = "gift") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size
    for u in users[start:end]:
        user_id = u.get('telegram_id') or u.get('user_id') or u.get('id')
        username = u.get('username') or '—'
        title = f"{user_id} • @{username}" if username != '—' else f"{user_id}"
        builder.button(text=title, callback_data=f"admin_{action}_pick_user_{user_id}")
    total = len(users)
    have_prev = page > 0
    have_next = end < total
    if have_prev:
        builder.button(text="⬅️ Назад", callback_data=f"admin_{action}_pick_user_page_{page-1}")
    if have_next:
        builder.button(text="Вперёд ➡️", callback_data=f"admin_{action}_pick_user_page_{page+1}")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")
    rows = [1] * len(users[start:end])
    tail = []
    if have_prev or have_next:
        tail.append(2 if (have_prev and have_next) else 1)
    tail.append(1)
    builder.adjust(*(rows + tail if rows else ([2] if (have_prev or have_next) else []) + [1]))
    return builder.as_markup()

def create_admin_hosts_pick_keyboard(hosts: list[dict], action: str = "gift") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if hosts:
        for h in hosts:
            name = h.get('host_name')
            if action == "speedtest":

                builder.button(text=name, callback_data=f"admin_{action}_pick_host_{name}")
                builder.button(text="🛠 Автоустановка", callback_data=f"admin_speedtest_autoinstall_{name}")
            else:
                builder.button(text=name, callback_data=f"admin_{action}_pick_host_{name}")
    else:
        builder.button(text="Хостов нет", callback_data="noop")

    if action == "speedtest":
        builder.button(text="🚀 Запустить для всех", callback_data="admin_speedtest_run_all")
        builder.button(text="🔌 SSH цели", callback_data="admin_speedtest_ssh_targets")
    builder.button(text="⬅️ Назад", callback_data=f"admin_{action}_back_to_users")

    if action == "speedtest":
        rows = [2] * (len(hosts) if hosts else 1)

        tail = [2, 1]
    else:
        rows = [1] * (len(hosts) if hosts else 1)
        tail = [1]
    builder.adjust(*(rows + tail))
    return builder.as_markup()


def create_admin_ssh_targets_keyboard(ssh_targets: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if ssh_targets:
        for t in ssh_targets:
            name = t.get('target_name')

            try:
                digest = hashlib.sha1((name or '').encode('utf-8', 'ignore')).hexdigest()
            except Exception:
                digest = hashlib.sha1(str(name).encode('utf-8', 'ignore')).hexdigest()

            builder.button(text=name, callback_data=f"stt:{digest}")
            builder.button(text="🛠 Автоустановка", callback_data=f"stti:{digest}")
    else:
        builder.button(text="SSH-целей нет", callback_data="noop")

    builder.button(text="🚀 Запустить для всех", callback_data="admin_speedtest_run_all_targets")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")

    rows = [2] * (len(ssh_targets) if ssh_targets else 1)
    rows.extend([1, 1])
    builder.adjust(*rows)
    return builder.as_markup()

def create_admin_keys_for_host_keyboard(
    host_name: str,
    keys: list[dict],
    page: int = 0,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    total = len(keys or [])
    if not keys:
        builder.button(text="Ключей на хосте нет", callback_data="noop")
        builder.button(text="⬅️ К выбору хоста", callback_data="admin_hostkeys_back_to_hosts")
        builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")
        builder.adjust(1)
        return builder.as_markup()

    start = max(page, 0) * page_size
    end = start + page_size
    page_items = keys[start:end]

    for k in page_items:
        kid = k.get('key_id')
        email = (k.get('key_email') or '—')
        expiry_raw = k.get('expiry_date') or '—'

        try:
            dt = datetime.fromisoformat(str(expiry_raw))
            expiry = dt.strftime('%d.%m.%Y')
        except Exception:
            expiry = str(expiry_raw)[:10]

        title = f"#{kid} • {email[:18]} • {expiry}"
        builder.button(text=title, callback_data=f"admin_edit_key_{kid}")

    have_prev = start > 0
    have_next = end < total
    if have_prev:
        builder.button(text="⬅️ Назад", callback_data=f"admin_hostkeys_page_{page-1}")
    if have_next:
        builder.button(text="Вперёд ➡️", callback_data=f"admin_hostkeys_page_{page+1}")

    builder.button(text="⬅️ К выбору хоста", callback_data="admin_hostkeys_back_to_hosts")
    builder.button(text="⬅️ В админ-меню", callback_data="admin_menu")

    rows = [1] * len(page_items)
    tail = []
    if have_prev or have_next:
        tail.append(2 if (have_prev and have_next) else 1)
    tail.append(2)
    builder.adjust(*(rows + tail if rows else tail))
    return builder.as_markup()

def create_admin_months_pick_keyboard(action: str = "gift") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for m in (1, 3, 6, 12):
        builder.button(text=f"{m} мес.", callback_data=f"admin_{action}_pick_months_{m}")
    builder.button(text="⬅️ Назад", callback_data=f"admin_{action}_back_to_hosts")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def create_dynamic_keyboard(menu_type: str, user_keys: list = None, trial_available: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Create a keyboard based on database configuration"""
    try:
        button_configs = get_button_configs(menu_type)

        # Группировка админ-меню:
        # - «Система» -> тест скорости / мониторинг / бэкап / восстановление
        # - «Настройки» -> администраторы / тарифы / триал
        if menu_type == "admin_menu" and button_configs:
            system_actions = {"admin_speedtest", "admin_monitor", "admin_backup_db", "admin_restore_db"}
            settings_actions = {"admin_admins_menu", "admin_plans", "admin_trial"}
            # Удаляем старые кнопки из главного админ-меню
            removed_rows = [cfg.get("row_position", 2) for cfg in button_configs if cfg.get("callback_data") in (system_actions | settings_actions)]
            target_row = min(removed_rows) if removed_rows else 2

            filtered = [cfg for cfg in button_configs if cfg.get("callback_data") not in (system_actions | settings_actions)]

            # Не дублируем, если пользователь уже добавил свои кнопки
            existing_callbacks = {cfg.get("callback_data") for cfg in filtered}
            if "admin_system_menu" not in existing_callbacks:
                filtered.append({
                    "button_id": "system_menu",
                    "text": "🖥 Система",
                    "callback_data": "admin_system_menu",
                    "url": None,
                    "row_position": target_row,
                    "column_position": 0,
                    "sort_order": 100,
                    "button_width": 1,
                    "is_active": 1,
                })
            if "admin_settings_menu" not in existing_callbacks:
                filtered.append({
                    "button_id": "settings_menu",
                    "text": "⚙️ Настройки",
                    "callback_data": "admin_settings_menu",
                    "url": None,
                    "row_position": target_row,
                    "column_position": 1,
                    "sort_order": 101,
                    "button_width": 1,
                    "is_active": 1,
                })
            button_configs = filtered


        # Ensure inactive-usage reminders (notifications) are reachable from the admin settings menu.
        if menu_type == "admin_settings_menu" and button_configs:
            existing_callbacks = {cfg.get("callback_data") for cfg in button_configs}
            if "admin_notifications_menu" not in existing_callbacks:
                try:
                    max_row = max(int(cfg.get("row_position", 0) or 0) for cfg in button_configs)
                except Exception:
                    max_row = 0
                button_configs = list(button_configs) + [
                    {
                        "button_id": "notifications",
                        "text": "🔔 Уведомления",
                        "callback_data": "admin_notifications_menu",
                        "url": None,
                        "row_position": max_row + 1,
                        "column_position": 0,
                        "sort_order": 998,
                        "button_width": 1,
                        "is_active": 1,
                    }
                ]

        # Ensure the button constructor is always reachable from the admin settings menu.
        if menu_type == "admin_settings_menu" and button_configs:
            existing_callbacks = {cfg.get("callback_data") for cfg in button_configs}
            if "admin_btn_constructor" not in existing_callbacks:
                try:
                    max_row = max(int(cfg.get("row_position", 0) or 0) for cfg in button_configs)
                except Exception:
                    max_row = 0
                button_configs = list(button_configs) + [
                    {
                        "button_id": "button_constructor",
                        "text": "🧩 Конструктор кнопок",
                        "callback_data": "admin_btn_constructor",
                        "url": None,
                        "row_position": max_row + 1,
                        "column_position": 0,
                        "sort_order": 999,
                        "button_width": 1,
                        "is_active": 1,
                    }
                ]

        
        if not button_configs:
            logger.warning(f"No button configs found for {menu_type}, using fallback")

            if menu_type == "main_menu":
                return create_main_menu_keyboard(user_keys or [], trial_available, is_admin)
            elif menu_type == "admin_menu":
                return create_admin_menu_keyboard()
            elif menu_type == "profile_menu":
                return create_profile_keyboard()
            elif menu_type == "support_menu":
                return create_support_menu_keyboard()
            elif menu_type == "admin_system_menu":
                return create_admin_system_menu_keyboard()
            elif menu_type == "admin_settings_menu":
                return create_admin_settings_menu_keyboard()
            else:
                return create_back_to_menu_keyboard()

        builder = InlineKeyboardBuilder()

        # Главный нюанс главного меню:
        # - если у пользователя 0 ключей, показываем «Купить ключ» вместо «Мои ключи»
        # - чтобы не было дубля, скрываем отдельную кнопку покупки (если она есть в конфиге)
        keys_count = len(user_keys) if user_keys else 0
        buy_text_setting = (get_setting("btn_buy_key_text") or "🛒 Купить ключ")
        replaced_my_keys_with_buy = False
        

        rows: dict[int, list[dict]] = {}
        for config in button_configs:
            row_pos = config.get('row_position', 0)
            rows.setdefault(row_pos, []).append(config)


        layout: list[int] = []
        for row_pos in sorted(rows.keys()):
            original_row = sorted(rows[row_pos], key=lambda x: x.get('column_position', 0))
            included_row: list[dict] = []
            row_buttons_objs: list[InlineKeyboardButton] = []



            for cfg in original_row:
                text = cfg.get('text', '')
                callback_data = cfg.get('callback_data')
                url = cfg.get('url')
                button_id = cfg.get('button_id', '')


                if menu_type == "main_menu" and button_id == "trial" and not trial_available:

                    continue
                

                if menu_type == "main_menu" and button_id == "admin" and not is_admin:

                    continue


                # Если ключей нет — меняем «Мои ключи» (по id или по action) на «Купить ключ»
                # (т.к. кнопки могут быть переименованы в админ-панели)
                if menu_type == "main_menu" and user_keys is not None:
                    is_my_keys_btn = (button_id == "my_keys") or (callback_data == "manage_keys")
                    is_buy_btn = (button_id == "buy_key") or (callback_data == "buy_new_key")

                    if is_my_keys_btn and keys_count == 0:
                        text = buy_text_setting
                        callback_data = "buy_new_key"
                        url = None
                        replaced_my_keys_with_buy = True

                    # Если «Мои ключи» уже заменили на покупку — скрываем отдельную кнопку покупки
                    if is_buy_btn and keys_count == 0 and replaced_my_keys_with_buy:
                        continue


                if menu_type == "main_menu" and user_keys is not None and "({len(user_keys)})" in text:
                    text = text.replace("({len(user_keys)})", f"({keys_count})")

                if url:
                    row_buttons_objs.append(InlineKeyboardButton(text=text, url=url))
                    included_row.append(cfg)
                elif callback_data:
                    row_buttons_objs.append(InlineKeyboardButton(text=text, callback_data=callback_data))
                    included_row.append(cfg)


            if not included_row:
                continue

            has_wide = any(int(b.get('button_width', 1) or 1) > 1 for b in included_row)
            if has_wide and row_buttons_objs:

                builder.row(row_buttons_objs[0])
                layout.append(1)
            else:

                if len(row_buttons_objs) >= 2:
                    builder.row(row_buttons_objs[0], row_buttons_objs[1])
                    layout.append(2)
                else:
                    builder.row(*row_buttons_objs)
                    layout.append(len(row_buttons_objs))




        return builder.as_markup()
        
    except Exception as e:
        logger.error(f"Error creating dynamic keyboard for {menu_type}: {e}")

        if menu_type == "main_menu":
            return create_main_menu_keyboard(user_keys or [], trial_available, is_admin)
        else:
            return create_back_to_menu_keyboard()

def create_dynamic_main_menu_keyboard(user_keys: list, trial_available: bool, is_admin: bool) -> InlineKeyboardMarkup:
    """Create main menu keyboard using dynamic configuration"""
    return create_dynamic_keyboard("main_menu", user_keys, trial_available, is_admin)

def create_dynamic_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Create admin menu keyboard using dynamic configuration"""
    return create_dynamic_keyboard("admin_menu")
def create_dynamic_admin_system_menu_keyboard() -> InlineKeyboardMarkup:
    """Create admin system submenu keyboard using dynamic configuration"""
    return create_dynamic_keyboard("admin_system_menu")


def create_dynamic_admin_settings_menu_keyboard() -> InlineKeyboardMarkup:
    """Create admin settings submenu keyboard using dynamic configuration"""
    return create_dynamic_keyboard("admin_settings_menu")


def create_dynamic_profile_keyboard() -> InlineKeyboardMarkup:
    """Create profile keyboard using dynamic configuration"""
    return create_dynamic_keyboard("profile_menu")

def create_dynamic_support_menu_keyboard() -> InlineKeyboardMarkup:
    """Create support menu keyboard using dynamic configuration"""
    return create_dynamic_keyboard("support_menu")


# === Broadcast additions: button type & action pickers ===
BROADCAST_ACTIONS_MAP = {
    "show_profile": "👤 Профиль",
    "manage_keys": "🔑 Мои ключи",
    "buy_new_key": "🛒 Купить",
    "gift_new_key": "🎁 Подарить ключ",
    "top_up_start": "💳 Пополнить баланс",
    "show_referral_program": "👥 Рефералка",
    "show_help": "🆘 Поддержка",
    "show_about": "ℹ️ О боте",
    "admin_menu": "🛠 Админ-панель",
}

def create_broadcast_button_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Кнопка-ссылка", callback_data="broadcast_btn_type_url")
    builder.button(text="⚙️ Кнопка из функционала", callback_data="broadcast_btn_type_action")
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    builder.adjust(2, 1)
    return builder.as_markup()

def create_broadcast_actions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cb, title in BROADCAST_ACTIONS_MAP.items():
        builder.button(text=title, callback_data=f"broadcast_action:{cb}")
    builder.button(text="⬅️ Назад (ссылка)", callback_data="broadcast_btn_type_url")
    builder.button(text="❌ Отмена", callback_data="cancel_broadcast")
    builder.adjust(2)
    return builder.as_markup()
