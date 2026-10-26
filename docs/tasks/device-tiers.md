# Задача: ступени устройств (`device_mode = 'tiers'`) не работают

Статус: не начата. Код в рамках PR-0/PR-IP не менялся.

## Что найдено (проверено по коду `main`)

- В схеме `xui_hosts` нет колонок `device_mode` и `tier_lock_extend`. Читающий код
  (`webapp/web_router/account_sync.py:61-62`, `webapp/web_router/payments_create.py:193`)
  всегда получает значения по умолчанию (`'plan'` и `0`).
- `get_device_tiers` (`data_manager/db/plans.py:366`) возвращает обычные активные тарифы хоста,
  отсортированные по `hwid_device_limit`. Полей `tier_id` и `device_count`, которые ожидает
  `account_sync.py:68`, в них нет.
- Фронтенд всегда отправляет `tier_device_count` и `tier_price`
  (`webapp/static/js/app.js:1969-1970`), но слайдер ступеней скрыт: `/api/device-tiers`
  никогда не возвращает режим `tiers` (`app.js:1404`).
- `process_successful_payment` (`bot/user_router/fulfillment.py`) не читает `tier_device_count`,
  то есть даже доплата за ступень не приводит к изменению лимита устройств на панели.
- После PR-0 сервер игнорирует клиентский `tier_price` и считает доплату сам, но
  только для хостов с `device_mode == 'tiers'`, которых сейчас не бывает.

## Что нужно решить

1. Нужна ли функция вообще. Если нет, удалить мёртвый код (поля в моделях, ветки в
   `payments_create.py`, слайдер и поля в `app.js`).
2. Если нужна: добавить колонки `device_mode`, `tier_lock_extend` в `xui_hosts` (миграция),
   отдельную сущность ступеней (`tier_id`, `device_count`, `price`), чтение
   `tier_device_count` в fulfillment и установку `hwidDeviceLimit` на панели.
3. Тесты: покупка и продление со ступенью, `tier_lock_extend`, подмена `tier_price` клиентом.
