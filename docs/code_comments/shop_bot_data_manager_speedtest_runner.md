# Комментарии: `src/shop_bot/data_manager/speedtest_runner.py`

SSH-speedtest (Ookla / speedtest-cli), TCP+HTTP probe до `host_url`, автоустановка CLI, запись в `host_speedtests`. Модульного docstring нет. Планировщик гоняет только SSH-цели; админ-бот и панель — вручную.

| Имя | Значение | Зачем |
|-----|----------|--------|
| `_ALLOWED_PROBE_SCHEMES` | `frozenset({"http", "https"})` | SSRF: иные схемы probe запрещены |

`_parse_host_port_from_url` объявлена дважды (67–77 и 83–93); вторая перекрывает первую, тела совпадают.

## `StoredHostKeyPolicy` (18–46)

**Docstring в коде:** есть

```
Принимает host key только если он совпадает с сохранённым, либо
(при явном подтверждении оператора) сохраняет ключ при первом подключении.
Несовпадающий ключ отклоняется — молчаливого AutoAdd нет.
```

Наследует `paramiko.MissingHostKeyPolicy`.

## `StoredHostKeyPolicy.__init__` (24–33)

**Docstring в коде:** нет

```
"""Запомнить expected_b64 (пусто→None), accept_new и колбэк on_save."""
```

## `StoredHostKeyPolicy.missing_host_key` (35–46)

**Docstring в коде:** нет

```
"""Сверить presented key с expected (hmac.compare_digest); иначе accept_new+on_save или SSHException."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 38–41 | есть expected | mismatch → `SSH host key mismatch`; совпало → add в host_keys |
| 42–43 | not accept_new | `unknown SSH host key` |
| 44–46 | accept_new | on_save(type, b64), add |

## `_apply_ssh_host_key_policy` (49–64)

**Docstring в коде:** нет

```
"""Поставить StoredHostKeyPolicy: ключ из get_ssh_known_host_key; on_save пишет save_ssh_known_host_key."""
```

## `_apply_ssh_host_key_policy._save` (59–60)

**Docstring в коде:** нет

```
"""Сохранить новый host key в БД для (ssh_host, ssh_port)."""
```

## `_parse_host_port_from_url` (67–77)

**Docstring в коде:** нет

```
"""Первое объявление: hostname/port/is_https из URL; порт по умолчанию 443/80; ошибка → (None, None, False)."""
```

Перекрыто копией на 83–93; из прод-кода вызывается только вторая.

## `_parse_host_port_from_url` (83–93)

**Docstring в коде:** нет

```
"""hostname, port и флаг https из URL; порт None → 443 или 80; ошибка разбора → (None, None, False)."""
```

## `_is_blocked_probe_ip` (96–104)

**Docstring в коде:** нет

```
"""True, если IP private/loopback/link_local/reserved/multicast/unspecified."""
```

## `_probe_target_error` (107–132)

**Docstring в коде:** есть

```
Return an error string if the probe URL must not be contacted.
```

None — можно коннектиться.

| Строки | Блок | Зачем |
|--------|------|--------|
| 113–114 | scheme не http/https | Unsupported URL scheme |
| 116–117 | нет host/port | Invalid host_url |
| 120–123 | getaddrinfo пусто/OSError | DNS resolution failed |
| 128–129 | плохой IP | Invalid resolved address |
| 130–131 | _is_blocked_probe_ip | Blocked destination address |

## `net_probe_for_host` (135–200)

**Docstring в коде:** есть

```
Lightweight network probe from panel to host_url: TCP connect + HTTP GET / (HEAD).
Returns dict with ok, ping_ms (TCP connect time), http_ms, error (if any).
```

Сначала `_probe_target_error`. TCP `open_connection` timeout 10 с → `ping_ms`. Затем aiohttp HEAD 10 с; ошибка → GET и чтение `text()`. HEAD/GET успех → `ok=True` даже если TCP уже измерен. Поля jitter/download/upload/server всегда None.

## `_ssh_exec_json` (203–226)

**Docstring в коде:** есть

```
Try commands sequentially; expect JSON on stdout. Returns (json_obj, error).
```

Из stdout вырезается `{...}` (regex `\{.*\}$`, DOTALL). Нет JSON → `(None, 'No JSON output from speedtest commands')`.

## `_parse_ookla_json` (229–246)

**Docstring в коде:** нет

```
"""Разобрать JSON Ookla CLI: ping.latency/jitter, bandwidth*8 → Mbps, server name/id; ошибка → {}."""
```

## `_parse_speedtest_cli_json` (249–266)

**Docstring в коде:** нет

```
"""Разобрать JSON speedtest-cli: ping, download/upload как bps → Mbps; jitter всегда None; ошибка → {}."""
```

## `ssh_speedtest_for_host` (269–342)

**Docstring в коде:** есть

```
Run speedtest on remote host via SSH. Tries Ookla CLI first, then speedtest-cli.
Returns dict with ok, metrics, error.
```

Нет `ssh_host` или `ssh_user` → error «SSH settings are not configured for host». Само подключение в executor через `_run_ssh`.

## `ssh_speedtest_for_host._run_ssh` (294–333)

**Docstring в коде:** нет

```
"""Подключиться (ключ RSA/Ed25519 или пароль), выполнить цепочку speedtest JSON, закрыть SSH."""
```

`accept_new_host_key` или флаг в host_row. Команды: Ookla `--accept-license --accept-gdpr -f json` / `--format=json`, затем без флагов, затем `speedtest-cli --json`. Сначала `_parse_ookla_json`; если нет `download_mbps` и в data есть `download` — `_parse_speedtest_cli_json`.

## `run_and_store_net_probe` (345–362)

**Docstring в коде:** нет

```
"""get_host → net_probe_for_host и insert_host_speedtest(method='net'); нет хоста → ok=False."""
```

## `run_and_store_ssh_speedtest` (365–382)

**Docstring в коде:** нет

```
"""get_host → ssh_speedtest_for_host и insert_host_speedtest(method='ssh'); нет хоста → ok=False."""
```

## `run_both_for_host` (385–407)

**Docstring в коде:** нет

```
"""Последовательно SSH-тест и net-probe; ok=False если любой не ok или исключение; details+склейка error."""
```

## `_ssh_connect` (410–435)

**Docstring в коде:** нет

```
"""Новый SSHClient с host-key policy; RSA/Ed25519 из ssh_key_path или пароль; timeout=20. Нет host/user → RuntimeError."""
```

## `_ssh_exec` (438–443)

**Docstring в коде:** нет

```
"""exec_command: вернуть (exit_status, stdout, stderr) как str; timeout по умолчанию 180."""
```

## `auto_install_speedtest_on_host` (446–588)

**Docstring в коде:** есть

```
Attempt to auto-install Ookla speedtest or speedtest-cli on remote host via SSH.
Tries package manager scripts, falls back to pip speedtest-cli. Returns {'ok', 'log'}.
```

Нет хоста → `{'ok': False, 'log': 'host not found'}`. Работа в executor.

## `auto_install_speedtest_on_host._install` (454–585)

**Docstring в коде:** нет

```
"""SSH: если уже Ookla 1.2.0 — ок; иначе tarball 1.2.0, затем packagecloud deb/rpm, затем pip speedtest-cli."""
```

| Строки | Блок | Зачем |
|--------|------|--------|
| 462–478 | уже есть binary и «1.2.0» в version | return ok |
| 479–480 | другая версия | reinstall tarball |
| 492–499 | arch | x86_64/amd64, aarch64/arm64, armv7l→armhf, иначе x86_64 |
| 500–522 | tarball install.speedtest.net 1.2.0 | успех только если version содержит 1.2.0 |
| 537–546 | debian/ubuntu или centos/rhel/fedora/alma/rocky | script.deb.sh / script.rpm.sh |
| 559–575 | pip | speedtest-cli |
| 580 | всё мимо | ok=False + лог |
| 581–585 | finally | ssh.close |

## `_target_to_host_row` (593–600)

**Docstring в коде:** нет

```
"""Словарь ssh_host/port/user/password/key_path из строки SSH-цели (port default 22)."""
```

## `run_and_store_ssh_speedtest_for_target` (603–622)

**Docstring в коде:** есть

```
Выполнить SSH-спидтест для отдельной цели (speedtest_ssh_targets) и сохранить результат как host_speedtests с именем цели.
```

Нет цели → `'target not found'`. `insert_host_speedtest(host_name=target_name, method='ssh')`.

## `auto_install_speedtest_on_target` (625–750)

**Docstring в коде:** есть

```
Автоустановка speedtest на отдельной SSH-цели.
```

Нет цели → `{'ok': False, 'log': 'target not found'}`.

## `auto_install_speedtest_on_target._install` (631–747)

**Docstring в коде:** нет

```
"""Тот же сценарий, что auto_install_speedtest_on_host._install, но SSH через _target_to_host_row."""
```
