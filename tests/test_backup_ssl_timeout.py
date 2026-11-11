"""Отправка бэкапа: SSL shutdown timeout не должен порождать повторные рассылки."""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from aiogram.exceptions import TelegramNetworkError

from shop_bot.data_manager import backup_manager


class _FakeSession:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _FakeBot:
    def __init__(self, send_side_effect=None):
        self.token = "123:FAKE"
        self.session = _FakeSession()
        self.calls = 0
        self._side_effect = send_side_effect

    async def send_document(self, **kwargs):
        self.calls += 1
        if self._side_effect:
            effect = self._side_effect
            if callable(effect):
                raise effect()
            raise effect


def test_ssl_shutdown_timeout_is_detected():
    err = TelegramNetworkError(
        method=MagicMock(),
        message="HTTP Client says - ClientOSError: SSL shutdown timed out",
    )
    assert backup_manager._is_ssl_shutdown_timeout(err) is True
    other = TelegramNetworkError(method=MagicMock(), message="Connection reset by peer")
    assert backup_manager._is_ssl_shutdown_timeout(other) is False


def test_ssl_shutdown_counts_as_success_without_retry(monkeypatch, tmp_path):
    zip_path = tmp_path / "db-backup-test.zip"
    zip_path.write_bytes(b"zip")
    err = TelegramNetworkError(
        method=MagicMock(),
        message="HTTP Client says - ClientOSError: SSL shutdown timed out",
    )
    fake = _FakeBot(send_side_effect=err)

    async def _use_source(source, timeout):
        return source, False

    monkeypatch.setattr(backup_manager, "_upload_bot", _use_source)
    monkeypatch.setattr(backup_manager.rw_repo, "get_admin_ids", lambda: [175654617])

    sent = asyncio.run(backup_manager.send_backup_to_admins(fake, zip_path, max_attempts=3))
    assert sent == 1
    assert fake.calls == 1


def test_generic_network_error_retries(monkeypatch, tmp_path):
    zip_path = tmp_path / "db-backup-test.zip"
    zip_path.write_bytes(b"zip")
    err = TelegramNetworkError(method=MagicMock(), message="Connection reset by peer")
    fake = _FakeBot(send_side_effect=err)

    async def _use_source(source, timeout):
        return source, False

    monkeypatch.setattr(backup_manager, "_upload_bot", _use_source)
    monkeypatch.setattr(backup_manager.rw_repo, "get_admin_ids", lambda: [1])

    async def _no_sleep(_delay):
        return None

    monkeypatch.setattr(backup_manager.asyncio, "sleep", _no_sleep)

    sent = asyncio.run(backup_manager.send_backup_to_admins(fake, zip_path, max_attempts=3))
    assert sent == 0
    assert fake.calls == 3
