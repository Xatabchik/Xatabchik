"""F-08: SSH-клиент speedtest не принимает чужой host key молча.

StoredHostKeyPolicy отклоняет несовпадение и неизвестный ключ без
подтверждения оператора; при accept_new сохраняет предъявленный ключ.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import paramiko
import pytest

from conftest import temp_db  # noqa: F401


def _rsa_key() -> paramiko.RSAKey:
    return paramiko.RSAKey.generate(1024)


def test_mismatch_host_key_is_rejected(temp_db):
    from shop_bot.data_manager.speedtest_runner import StoredHostKeyPolicy

    expected = _rsa_key()
    presented = _rsa_key()
    assert expected.get_base64() != presented.get_base64()

    policy = StoredHostKeyPolicy(expected.get_base64(), accept_new=False)
    client = paramiko.SSHClient()
    with pytest.raises(paramiko.SSHException, match="host key mismatch"):
        policy.missing_host_key(client, "vpn.example", presented)
    assert client.get_host_keys().lookup("vpn.example") is None


def test_unknown_host_key_rejected_without_operator_confirm(temp_db):
    from shop_bot.data_manager.speedtest_runner import StoredHostKeyPolicy

    presented = _rsa_key()
    policy = StoredHostKeyPolicy(None, accept_new=False)
    client = paramiko.SSHClient()
    with pytest.raises(paramiko.SSHException, match="unknown SSH host key"):
        policy.missing_host_key(client, "vpn.example", presented)


def test_first_connect_saves_key_when_operator_confirms(temp_db):
    from shop_bot.data_manager.speedtest_runner import StoredHostKeyPolicy

    presented = _rsa_key()
    saved: list[tuple[str, str]] = []

    def _on_save(key_type: str, key_b64: str) -> None:
        saved.append((key_type, key_b64))

    policy = StoredHostKeyPolicy(None, accept_new=True, on_save=_on_save)
    client = paramiko.SSHClient()
    policy.missing_host_key(client, "vpn.example", presented)
    assert saved == [(presented.get_name(), presented.get_base64())]
    assert client.get_host_keys().lookup("vpn.example") is not None


def test_matching_stored_key_is_accepted(temp_db):
    from shop_bot.data_manager.speedtest_runner import StoredHostKeyPolicy

    key = _rsa_key()
    policy = StoredHostKeyPolicy(key.get_base64(), accept_new=False)
    client = paramiko.SSHClient()
    policy.missing_host_key(client, "vpn.example", key)
    assert client.get_host_keys().lookup("vpn.example") is not None


def test_apply_policy_uses_stored_key_and_rejects_mismatch(temp_db):
    from shop_bot.data_manager import database
    from shop_bot.data_manager.speedtest_runner import (
        StoredHostKeyPolicy,
        _apply_ssh_host_key_policy,
    )

    stored = _rsa_key()
    other = _rsa_key()
    database.save_ssh_known_host_key("10.1.2.3", 22, stored.get_name(), stored.get_base64())

    ssh = paramiko.SSHClient()
    _apply_ssh_host_key_policy(ssh, "10.1.2.3", 22, accept_new_host_key=False)
    policy = ssh._policy
    assert isinstance(policy, StoredHostKeyPolicy)
    with pytest.raises(paramiko.SSHException, match="host key mismatch"):
        policy.missing_host_key(MagicMock(), "10.1.2.3", other)


def test_speedtest_connect_paths_do_not_use_auto_add():
    from pathlib import Path

    src = Path("src/shop_bot/data_manager/speedtest_runner.py").read_text(encoding="utf-8")
    assert "AutoAddPolicy" not in src
    assert "RejectPolicy" not in src or "StoredHostKeyPolicy" in src
    assert "StoredHostKeyPolicy" in src
