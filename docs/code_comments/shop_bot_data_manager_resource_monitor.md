# Комментарии: `src/shop_bot/data_manager/resource_monitor.py`

Локальные метрики панели (psutil) и удалённые по SSH (хост `xui_hosts` или SSH-цель). Модульного docstring нет. Планировщик пишет в `insert_resource_metric`; панель читает `/monitor/*.json`.

`psutil` импортируется в try; при ошибке `psutil = None`.

## `_safe_percent` (19–26)

**Docstring в коде:** нет

```
"""Процент numerator/denominator с округлением до 2 знаков; знаменатель ≤0 или ошибка → None."""
```

## `get_local_metrics` (29–212)

**Docstring в коде:** есть

```
Собрать базовые метрики локальной системы (панели).
Требует psutil. Если psutil недоступен, возвращает ограниченную информацию.
```

Всегда стартует с `ok=True`, hostname/platform/python. Любой внешний except → `ok=False`, `error=str(e)`.

| Строки | Блок | Зачем |
|--------|------|--------|
| 47–56 | psutil is None | ok=False, error «psutil not installed»; `boot_time` не вызывается (`if psutil else None`); return |
| 59–62 | uptime | time - boot_time |
| 65–77 | cpu | percent interval=0.2, loadavg через os.getloadavg |
| 80–100 | memory / swap | virtual_memory / swap_memory |
| 103–124 | disks | disk_partitions; пропуск tmpfs/devtmpfs/squashfs/overlay |
| 127–131 | disk_percent | max percent по дискам |
| 134–149 | net | net_io_counters |
| 152–172 | top_processes | cpu>0 или mem>1, топ-10 по cpu |
| 175–207 | load_avg / temperatures / boot_time | если есть методы psutil |

## `_parse_free_m` (215–242)

**Docstring в коде:** нет

```
"""Разобрать вывод `free -m`: первая строка Mem: → total/used/free/available_mb и percent."""
```

Нужно ≥7 полей; `available` — `parts[6]`. Иначе `{}`.

## `_parse_loadavg` (245–250)

**Docstring в коде:** нет

```
"""Три float из первых трёх токенов текста `/proc/loadavg`; ошибка → None."""
```

## `_parse_df_h` (253–278)

**Docstring в коде:** нет

```
"""Разобрать строки df: пропуск заголовка Filesystem/Source/Size; ≥6 полей → device/mount/size/used/avail/percent."""
```

`pcent` без `%` → int, иначе None.

## `_compute_cpu_percent` (281–291)

**Docstring в коде:** нет

```
"""(loadavg[0] / cpu_count) * 100; нет данных или cpu_count≤0 → None; отрицательное → 0.0."""
```

## `get_remote_metrics_for_host` (294–416)

**Docstring в коде:** есть

```
Собрать базовые метрики по SSH для хоста из xui_hosts.
Требует настроенный SSH у хоста в БД (`ssh_host`, `ssh_user`, и т.п.).
```

`rw_repo.get_host` → None: `{"ok": False, "error": "host not found"}`. SSH через `speedtest_runner._ssh_connect` / `_ssh_exec`. `finally` закрывает ssh.

| Строки | Блок | Зачем |
|--------|------|--------|
| 311–315 | uname | `uname -srmo \|\| uname -a` |
| 317–329 | uptime | первое число `/proc/uptime` |
| 331–347 | loadavg / nproc | cpu_percent через _compute_cpu_percent |
| 349–367 | free -m / df | mem_percent, disk_percent=max |
| 370–378 | aliases | memory_percent/used/total_mb; disk_mountpoint первого диска |
| 381–409 | /proc/net/dev | eth0\|ens\|enp\|wlan0, иначе не lo/docker/veth; иначе нули |

## `get_remote_metrics_for_target` (419–531)

**Docstring в коде:** нет

```
"""Те же SSH-метрики, что get_remote_metrics_for_host, для строки speedtest_ssh_targets."""
```

`get_ssh_target` → None: `"target not found"`. Хост-словарь через `_target_to_host_row`. Набор команд и разбор совпадают с хостом.
