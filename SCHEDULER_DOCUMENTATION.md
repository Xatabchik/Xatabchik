# Планировщик фоновых задач

Модуль: `src/shop_bot/data_manager/scheduler.py`.

Запуск: `__main__.py` кладёт `periodic_subscription_check(bot_controller)` в event loop **основного бота** (`BotController.get_loop`). Если loop ещё не готов — в лог warning, задачи не стартуют.

Тик цикла: **300 секунд**. Часть работ троттлится внутри цикла.

Нужен живой `Bot` основного бота: уведомления пользователям и админам идут через него. Support-бот планировщик не крутит (кроме follow-up автозакрытия тикетов через `SupportBotController`).

---

## Задачи

| Функция | Интервал | Что делает | Кого вызывает |
|---------|----------|------------|---------------|
| `check_expiring_subscriptions` | каждый тик | Напоминания за 72/48/24/1 ч до конца ключа | `Bot.send_message`, `telegram_reachability` |
| `check_auto_renewals` | каждый тик | Ключи с `auto_renew`, списать баланс, продлить на панели | `get_keys_for_auto_renew`, `create_or_update_key_on_host` |
| `check_broadcast_campaigns` | каждый тик | Плановые рассылки неактивным | `get_pending_broadcast_recipients`, `handle_send_exception` |
| `check_inactive_usage_reminders` | каждый тик | Ключ без трафика — напомнить | `key_usage_monitor` |
| `check_device_limit_violations` | каждый тик | HWID больше лимита — админам | `get_hwid_devices_for_user` |
| `check_traffic_boost_resets` | каждый тик | Месячный сброс основного пула / boost | `apply_key_monthly_reset_fields`, Remnawave reset |
| `_maybe_enforce_dual_traffic_limits` | `dual_limit_interval_sec` (по умолчанию 120 с) | LTE: снять/вернуть сквад, disable | `enforce_dual_traffic_limits` → `remnawave_api` |
| `_maybe_sync_keys_with_panels` | 30 мин | Сверить ключи с `list_users`, orphan/missing | `remnawave_api.list_users` |
| `_maybe_run_periodic_speedtests` | 8 ч | SSH-speedtest по всем `speedtest_ssh_targets` | `run_and_store_ssh_speedtest_for_target` |
| `_maybe_run_daily_backup` | `backup_interval_days` | ZIP `users.db` админам | `backup_manager.create_backup_file`, `send_backup_to_admins` |
| `_maybe_collect_resource_metrics` | `monitoring_interval_sec` | CPU/RAM/диск панели и SSH-хостов, алерты | `resource_monitor`, `insert_resource_metric` |
| `_maybe_auto_close_idle_tickets` | каждый тик | Автозакрытие тикетов | `idle_close.maybe_auto_close_idle_tickets` |
| `_maybe_purge_closed_ticket_media` | 1 ч | Удалить вложения закрытых тикетов старше TTL | `ticket_media.purge_expired_closed_ticket_media` |

Публичная точка входа одна: `periodic_subscription_check`. Остальные функции — внутренние шаги цикла (в каталоге они перечислены с префиксом `_` и без).

---

## Связанные модули

### `backup_manager.py`

`create_backup_file`, `send_backup_to_admins`, `cleanup_old_backups`, `validate_db_file`, `restore_from_file`.

Ещё вызываются вручную: админ-бот (`admin_backup_db` / `admin_restore_db`) и панель (`POST /admin/db/backup`, `/admin/db/restore`).

### `resource_monitor.py`

`get_local_metrics` (psutil), `get_remote_metrics_for_host`, `get_remote_metrics_for_target` (SSH через хелперы `speedtest_runner`). Панель читает те же функции на `/monitor/*.json`.

### `speedtest_runner.py`

`net_probe_for_host` (SSRF-ограничения), `ssh_speedtest_for_host`, `run_and_store_*`, `auto_install_speedtest_on_*`, `StoredHostKeyPolicy`. Админ-бот и панель запускают тесты вручную; планировщик — только SSH-цели по расписанию.

### `telegram_reachability.py`

`classify_unreachable_error`, `handle_send_exception` → `mark_user_unreachable`. Рассылки и напоминания не долбят заблокировавших бота. Обратный сброс: `BanMiddleware` → `mark_user_reachable` при любом апдейте.

---

## LTE / dual pool

Воркер `enforce_dual_traffic_limits` читает `key_lte_state` / `key_node_usage_snapshots`, считает расход по нодам LTE-сквада (`get_user_node_usage_for_squad`) и:

- снимает LTE-сквад (`remove_squad_from_user`), если лимит исчерпан;
- возвращает сквад после докупки ГБ;
- не трогает unlimited-тарифы (`should_account_lte_traffic`).

Контекст лимитов: [SQUAD_DUAL_LIMIT_PROMPT.md](SQUAD_DUAL_LIMIT_PROMPT.md), [VPN_KEYS_DOCUMENTATION.md](VPN_KEYS_DOCUMENTATION.md).
