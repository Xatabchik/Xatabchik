from html import escape as html_escape

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
    key_number,
    expiry_date,
    created_date,
    connection_string,
    *,
    devices_connected: int | None = None,
    plan_group: str | None = None,
    plan_name: str | None = None,
    device_limit: int | None = None,
):
    expiry_formatted = expiry_date.strftime('%d.%m.%Y в %H:%M')
    created_formatted = created_date.strftime('%d.%m.%Y в %H:%M')

    dc = devices_connected if devices_connected is not None else 0
    group = plan_group or (f"{device_limit} устройств📡" if device_limit is not None else "—")
    tariff = plan_name or "—"
    limit = device_limit if device_limit is not None else "—"

    return (
        f"<b>🔑 Ваша подписка: #{key_number}</b>\n\n"
        f"<blockquote><b>➕ Приобретён:</b> {created_formatted}\n"
        f"<b>⏳ Действителен до:</b> {expiry_formatted}</blockquote>\n\n"
        f"<code>{connection_string}</code>\n\n"
        f"📱 <b>Вы подключили:</b> {dc}\n\n"
        f"📦 <b>Тариф подписки:</b>\n"
        f"<blockquote>📁 <b>Группа:</b> {group}\n"
        f"🕒 <b>Тариф:</b> {tariff}\n"
        f"📱 <b>Лимит устройств:</b> {limit}</blockquote>\n\n"
        f"<i>Подключите свое устройство по кнопкам ниже👇</i>\n\n"
    )

def get_purchase_success_text(action: str, key_number: int, expiry_date, connection_string: str):
    action_text = "обновлен" if action == "extend" else "готов"
    expiry_formatted = expiry_date.strftime('%d.%m.%Y в %H:%M')
    safe_connection_string = html_escape(connection_string or "")

    return (
        f"🎉 <b>Ваша подписка #{key_number} {action_text}!</b>\n\n"
        f"⏳ <b>Он будет действовать до:</b> {expiry_formatted}\n\n"
        f"<code>{safe_connection_string}</code>"
    )
