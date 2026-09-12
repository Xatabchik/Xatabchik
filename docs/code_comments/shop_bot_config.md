# Комментарии: `src/shop_bot/config.py`

Тексты HTML для Telegram (профиль, статус VPN, карточка ключа). Модульного docstring нет. Константы — готовые строки без функций.

## Блоки уровня модуля

| Строки | Имя | Зачем |
|--------|-----|--------|
| 4 | `CHOOSE_PLAN_MESSAGE` | Подпись экрана выбора тарифа |
| 5 | `CHOOSE_PAYMENT_METHOD_MESSAGE` | Подпись экрана выбора оплаты |
| 6 | `VPN_INACTIVE_TEXT` | Статус в профиле, если срок ключа истёк |
| 7 | `VPN_NO_DATA_TEXT` | Статус в профиле, если ключей нет |

## `get_profile_text` (9–15)

**Docstring в коде:** нет

```
"""Собрать HTML профиля: username, total_spent как целые RUB, total_months и переданный vpn_status_text."""
```

`username` подставляется как есть (без html_escape в этой функции).

## `get_vpn_active_text` (17–21)

**Docstring в коде:** нет

```
"""HTML активного VPN: осталось days_left дней и hours_left часов."""
```

## `get_key_info_text` (23–113)

**Docstring в коде:** нет. В теле уже есть `#` про `.get()`, парсинг дат, название, ссылки подарка.

```
"""HTML карточки ключа: номер, имя, email, даты, connection string, устройства, тариф, опционально трафик и ссылки подарка.

Даты из key['expiry_date']/['created_date']: ISO-строка или datetime; при ошибке — datetime.now().
Тексты пользователя и connection string прогоняются через html_escape.
Ссылки подарка добавляются только если is_gift_activated ложно и передана хотя бы одна ссылка.
"""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 46–52 / 54–60 | try parse dates | fromisoformat или уже datetime; except → now |
| 75–76 | if user_key_name | строка названия с escape |
| 87–97 | if not activated and links | блок «ссылки активации» app + Telegram |
| 108–109 | if traffic_info_text | строка трафика |

## `get_purchase_success_text` (115–124)

**Docstring в коде:** нет

```
"""HTML успеха покупки/продления: «обновлен» если action=='extend', иначе «готов»; дата и escaped connection string."""
```
