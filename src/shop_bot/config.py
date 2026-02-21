from html import escape as html_escape
from datetime import datetime

CHOOSE_PLAN_MESSAGE = "Выберите подходящий тариф:"
CHOOSE_PAYMENT_METHOD_MESSAGE = "Выберите удобный способ оплаты:"
VPN_INACTIVE_TEXT = "❌ <b>Статус VPN:</b> Неактивен (срок истек)"
VPN_NO_DATA_TEXT = "ℹ️ <b>Статус VPN:</b> У вас пока нет активных ключей."

def get_profile_text(username, total_spent, total_months, vpn_status_text):
    return (
        f"👤 <b>Профиль:</b> {username}\n\n"
        f"💰 <b>Потрачено всего:</b> {total_spent:.0f} RUB\n"
        f"📅 <b>Приобретено месяцев:</b> {total_months}\n\n"
        f"{vpn_status_text}"
    )

def get_vpn_active_text(days_left, hours_left):
    return (
        f"✅ <b>Статус VPN:</b> Активен\n"
        f"⏳ <b>Осталось:</b> {days_left} д. {hours_left} ч."
    )

def get_key_info_text(
    key,
    key_number: int = 0,
    *,
    devices_connected: int | None = None,
    plan_group: str | None = None,
    plan_name: str | None = None,
    device_limit: int | None = None,
    gift_code: str | None = None,
    domain: str | None = None,
    is_gift_activated: bool = False,
    gift_link: str | None = None,
):
    # Получаем все данные из объекта ключа через .get()
    expiry_date_str = key.get('expiry_date')
    created_date_str = key.get('created_date')
    connection_string = key.get('connection_string') or key.get('subscription_url') or ""
    key_email = key.get('key_email') or "—"
    user_key_name = key.get('user_key_name')  # Пользовательское название
    
    # Парсим даты если они строки
    try:
        if isinstance(expiry_date_str, str):
            expiry_date = datetime.fromisoformat(expiry_date_str)
        else:
            expiry_date = expiry_date_str
    except Exception:
        expiry_date = datetime.now()
    
    try:
        if isinstance(created_date_str, str):
            created_date = datetime.fromisoformat(created_date_str)
        else:
            created_date = created_date_str
    except Exception:
        created_date = datetime.now()
    
    expiry_formatted = expiry_date.strftime('%d.%m.%Y в %H:%M')
    created_formatted = created_date.strftime('%d.%m.%Y в %H:%M')

    dc = devices_connected if devices_connected is not None else 0
    group = plan_group or (f"{device_limit} устройств📡" if device_limit is not None else "—")
    tariff = plan_name or "—"
    limit = device_limit if device_limit is not None else "—"

    text_parts = [
        f"<b>🔑 Ваш ключ: #{key_number}</b>\n",
    ]
    
    # Добавляем название если задано
    if user_key_name:
        text_parts.append(f"<b>📝 Название:</b> {html_escape(user_key_name)}\n")
    
    text_parts.append("\n")
    
    text_parts.extend([
        f"<blockquote><b>📧 Email:</b> {key_email}\n",
        f"<b>➕ Приобретён:</b> {created_formatted}\n",
        f"<b>⏳ Действителен до:</b> {expiry_formatted}</blockquote>\n\n",
    ])
    
    # Добавляем ссылку активации подарка отдельным блоком
    if gift_link and not is_gift_activated:
        text_parts.append(
            f"🎁 <b>Ссылка активации подарка:</b>\n"
            f"<code>{html_escape(gift_link)}</code>\n\n"
        )
    
    text_parts.extend([
        f"<code>{html_escape(connection_string)}</code>\n\n",
        f"📱 <b>Вы подключили:</b> {dc}\n\n",
        f"📦 <b>Тариф ключа:</b>\n",
        f"<blockquote>📁 <b>Группа:</b> {group}\n",
        f"🕒 <b>Тариф:</b> {tariff}\n",
        f"📱 <b>Лимит устройств:</b> {limit}</blockquote>\n\n",
        f"<i>Подключите свое устройство по кнопкам ниже👇</i>\n\n",
    ])
    
    return "".join(text_parts)

def get_purchase_success_text(action: str, key_number: int, expiry_date, connection_string: str):
    action_text = "обновлен" if action == "extend" else "готов"
    expiry_formatted = expiry_date.strftime('%d.%m.%Y в %H:%M')
    safe_connection_string = html_escape(connection_string or "")

    return (
        f"🎉 <b>Ваш ключ #{key_number} {action_text}!</b>\n\n"
        f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
        f"<code>{safe_connection_string}</code>"
    )
