"""PR-A: замок записи ключа, дельта и идемпотентность по payment_id.

Панель Remnawave заменена заглушкой с задержкой, как в
tests/test_remnawave_ensure_user_username.py: срок читается, спустя задержку
записывается, и параллельные продления реально гоняются друг с другом.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from conftest import temp_db  # noqa: F401
from shop_bot.data_manager import key_write_guard as guard
from shop_bot.modules import remnawave_api as api

DAY_MS = 86400000
HOST = "h1"
EMAIL = "1001-1@bot.local"
SQUAD = {"host_name": HOST, "squad_uuid": "11111111-1111-4111-8111-111111111111"}


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class FakePanel:
    """Одна панель на все вызовы. PATCH применяется спустя `patch_delay`."""

    def __init__(self, expire_ms: int | None, *, patch_delay: float = 0.0, get_delay: float = 0.0):
        self.user = None
        if expire_ms is not None:
            self.user = {"id": 7, "uuid": "u-7", "username": "1001-1", "expireAt": _iso(expire_ms), "shortUuid": "s1"}
        self.patch_delay = patch_delay
        self.get_delay = get_delay
        self.modes: list[str | None] = []
        self.patches: list[int] = []
        self.guard = threading.Lock()

    def expire_ms(self) -> int | None:
        with self.guard:
            return _ms(self.user["expireAt"]) if self.user else None

    async def transport(self, host_name, method, path, **kw):
        if method == "GET":
            await asyncio.sleep(self.get_delay)
            with self.guard:
                if self.user is None:
                    return _Resp({}, 404)
                return _Resp({"response": dict(self.user)}, 200)
        payload = kw.get("json_payload") or {}
        mode = self.modes.pop(0) if self.modes else None
        if mode == "code":
            raise api.RemnawaveAPIError("Remnawave API request failed: 400 {'errorCode': 'A001'}")
        if mode == "timeout":
            await asyncio.sleep(self.patch_delay)
            raise api.RemnawaveAmbiguousError("Remnawave API timeout: read")
        await asyncio.sleep(self.patch_delay)
        with self.guard:
            if self.user is None:
                self.user = {"id": 7, "uuid": "u-7", "username": payload.get("username"), "shortUuid": "s1"}
            self.user["expireAt"] = payload["expireAt"]
            self.patches.append(_ms(payload["expireAt"]))
            body = dict(self.user)
        if mode == "lost":
            raise api.RemnawaveAmbiguousError("Remnawave API timeout: response lost")
        return _Resp({"response": body}, 200)


@pytest.fixture()
def panel_env(temp_db, monkeypatch):
    monkeypatch.setattr(api.rw_repo, "get_squad", lambda host: dict(SQUAD))
    monkeypatch.setattr(api.rw_repo, "get_squad_by_class", lambda host, cls: None)

    def make(expire_ms, **kw):
        panel = FakePanel(expire_ms, **kw)
        monkeypatch.setattr(api, "_request_for_host", panel.transport)
        return panel

    return temp_db, make


def _set(database, lock="off", delta="off"):
    database.update_setting("key_write_lock_scope", lock)
    database.update_setting("key_extension_delta_scope", delta)


def _call(pid=None, days=30, abs_ms=None, email=EMAIL):
    return api.create_or_update_key_on_host(
        HOST, email, days_to_add=days, expiry_timestamp_ms=abs_ms, payment_id=pid, raise_on_error=True
    )


def _abs_from(db_expire_ms: int, days: int) -> int:
    """Абсолютная дата, как её считает fulfillment: max(срок в БД, сейчас) + дни."""
    return max(db_expire_ms, int(time.time() * 1000)) + days * DAY_MS


def _now_ms() -> int:
    return int(time.time() * 1000)


def _tables(database):
    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        locks = conn.execute("SELECT COUNT(*) FROM key_write_locks").fetchone()[0]
        ext = conn.execute("SELECT COUNT(*) FROM key_extension_applied").fetchone()[0]
    return locks, ext


# --- режим off и прежнее поведение ------------------------------------------------

def test_flags_default_to_off(temp_db):
    assert guard.get_lock_scope() == "off"
    assert guard.get_delta_scope() == "off"
    temp_db.update_setting("key_write_lock_scope", "garbage")
    assert guard.get_lock_scope() == "off"


def test_off_mode_matches_current_behaviour_and_loses_a_period(panel_env):
    database, make = panel_env
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.15)

    async def run():
        return await asyncio.gather(_call(days=30), _call(days=30))

    asyncio.run(run())
    assert panel.expire_ms() == e + 30 * DAY_MS, "без замка вторая запись затирает первую"
    assert _tables(database) == (0, 0)


def test_off_mode_with_payment_id_uses_absolute_date_and_writes_nothing(panel_env):
    database, make = panel_env
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    abs_ms = _abs_from(e, 30)
    asyncio.run(_call(pid="pay-1", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == abs_ms
    assert _tables(database) == (0, 0)


def test_delta_without_payment_id_keeps_old_behaviour(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    abs_ms = _abs_from(e, 30)
    asyncio.run(_call(pid=None, days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == abs_ms
    assert _tables(database) == (0, 0)


def test_delta_without_days_keeps_old_behaviour(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    abs_ms = e + 5 * DAY_MS
    asyncio.run(_call(pid="pay-x", days=None, abs_ms=abs_ms))
    assert panel.expire_ms() == abs_ms
    assert _tables(database)[1] == 0


# --- замок -------------------------------------------------------------------------

def test_lock_all_serializes_days_only_calls(panel_env):
    database, make = panel_env
    _set(database, lock="all")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.1)

    async def run():
        return await asyncio.gather(_call(days=30), _call(days=30))

    asyncio.run(run())
    assert panel.expire_ms() == e + 60 * DAY_MS
    assert _tables(database)[0] == 0, "замок должен быть освобождён"


def test_lock_payments_scope_ignores_calls_without_payment_id(panel_env):
    database, make = panel_env
    _set(database, lock="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.15)

    async def run():
        return await asyncio.gather(_call(days=30), _call(days=30))

    asyncio.run(run())
    assert panel.expire_ms() == e + 30 * DAY_MS


def test_lock_payments_scope_covers_days_only_calls_with_payment_id(panel_env):
    database, make = panel_env
    _set(database, lock="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.1)

    async def run():
        return await asyncio.gather(_call(pid="a", days=30), _call(pid="b", days=30))

    asyncio.run(run())
    assert panel.expire_ms() == e + 60 * DAY_MS


def test_lock_acquire_ttl_takeover_and_foreign_release(temp_db):
    now = 1_000_000.0
    assert guard.try_acquire_lock("k", "owner-a", ttl=300, now=now)
    assert not guard.try_acquire_lock("k", "owner-b", ttl=300, now=now + 10)
    assert not guard.release_lock("k", "owner-b"), "чужой владелец замок не освобождает"
    assert not guard.try_acquire_lock("k", "owner-b", ttl=300, now=now + 299)
    assert guard.try_acquire_lock("k", "owner-b", ttl=300, now=now + 301), "просроченный замок перехватывается"
    assert not guard.release_lock("k", "owner-a")
    assert guard.release_lock("k", "owner-b")
    assert guard.try_acquire_lock("k", "owner-c", now=now + 302)


def test_lock_wait_timeout_logs_marker_alerts_and_proceeds(panel_env, caplog):
    database, make = panel_env
    _set(database, lock="all")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    lock_key = guard.make_lock_key(HOST, api._normalize_email_for_remnawave(EMAIL))
    assert guard.try_acquire_lock(lock_key, "other-process")

    async def run():
        orig = guard.acquire_lock

        async def short(key, **kw):
            kw["wait"] = 0.6
            kw["poll"] = 0.05
            return await orig(key, **kw)

        guard.acquire_lock = short
        try:
            return await _call(days=30)
        finally:
            guard.acquire_lock = orig

    with caplog.at_level(logging.ERROR):
        asyncio.run(run())
    assert any(guard.LOCK_TIMEOUT_MARKER in r.getMessage() for r in caplog.records)
    alerts = guard.fetch_unsent_alerts()
    assert [a["kind"] for a in alerts] == ["key_write_lock_timeout"]
    assert panel.expire_ms() == e + 30 * DAY_MS, "платёж принят: выполняется без замка"
    assert not guard.try_acquire_lock(lock_key, "x"), "чужой замок остался нетронутым"


def test_clear_stale_locks_of_service_keeps_own_boot(temp_db, monkeypatch):
    monkeypatch.setenv("SHOPBOT_SERVICE_NAME", "bot")
    guard.try_acquire_lock("k1", f"bot:oldboot:abc")
    guard.try_acquire_lock("k2", f"bot:{guard.BOOT_ID}:abc")
    guard.try_acquire_lock("k3", "webapp:oldboot:abc")
    assert guard.clear_stale_locks_of_service() == 1
    assert not guard.try_acquire_lock("k2", "z")
    assert not guard.try_acquire_lock("k3", "z")
    assert guard.try_acquire_lock("k1", "z")


# --- дельта ------------------------------------------------------------------------

def test_delta_two_payments_in_one_loop_add_both_periods(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.1)
    abs_ms = _abs_from(e, 30)

    async def run():
        return await asyncio.gather(
            _call(pid="pay-a", days=30, abs_ms=abs_ms), _call(pid="pay-b", days=30, abs_ms=abs_ms)
        )

    asyncio.run(run())
    assert panel.expire_ms() == e + 60 * DAY_MS
    locks, ext = _tables(database)
    assert (locks, ext) == (0, 2)


def test_delta_payments_in_separate_threads(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.1)
    abs_ms = _abs_from(e, 30)
    errors = []

    def worker(pid):
        try:
            asyncio.run(_call(pid=pid, days=30, abs_ms=abs_ms))
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(f"pay-{i}",)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert panel.expire_ms() == e + 90 * DAY_MS


def test_delta_mixed_sources_payment_and_admin(panel_env):
    database, make = panel_env
    _set(database, lock="all", delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=0.1)
    abs_ms = _abs_from(e, 30)

    async def run():
        return await asyncio.gather(_call(pid="pay-a", days=30, abs_ms=abs_ms), _call(days=10))

    asyncio.run(run())
    assert panel.expire_ms() == e + 40 * DAY_MS


def test_delta_expired_key_counts_from_now(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    panel = make(_now_ms() - 5 * DAY_MS)
    before = _now_ms()
    asyncio.run(_call(pid="pay-e", days=30, abs_ms=before + 30 * DAY_MS))
    got = panel.expire_ms()
    assert before + 30 * DAY_MS <= got <= _now_ms() + 30 * DAY_MS


def test_delta_stale_database_expiry_does_not_lose_days(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 40 * DAY_MS
    panel = make(e)
    stale_db_expiry = _now_ms() + 5 * DAY_MS
    asyncio.run(_call(pid="pay-s", days=30, abs_ms=_abs_from(stale_db_expiry, 30)))
    assert panel.expire_ms() == e + 30 * DAY_MS


def test_delta_absolute_date_larger_than_panel_wins(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 5 * DAY_MS
    panel = make(e)
    abs_ms = e + 90 * DAY_MS
    asyncio.run(_call(pid="pay-big", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == abs_ms


def test_delta_email_only_key(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    asyncio.run(_call(pid="pay-m", days=30, abs_ms=_abs_from(e, 30), email="someone@example.com"))
    assert panel.expire_ms() == e + 30 * DAY_MS


def test_delta_new_key_without_panel_user(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    panel = make(None)
    before = _now_ms()
    asyncio.run(_call(pid="pay-n", days=30))
    assert before + 30 * DAY_MS <= panel.expire_ms() <= _now_ms() + 30 * DAY_MS


# --- идемпотентность ------------------------------------------------------------------

def _record(pid):
    return guard.extension_get(pid)


def test_redelivery_after_success_adds_exactly_one_period(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    abs_ms = _abs_from(e, 30)
    asyncio.run(_call(pid="pay-r", days=30, abs_ms=abs_ms))
    asyncio.run(_call(pid="pay-r", days=30, abs_ms=abs_ms))
    asyncio.run(_call(pid="pay-r", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == e + 30 * DAY_MS
    assert _record("pay-r")["state"] == "done"
    assert _record("pay-r")["days"] == 30 and _record("pay-r")["source"] == "payment"


def test_failure_after_patch_then_redelivery_extends_exactly_once(panel_env):
    """Ответ потерян, но PATCH применился: повтор не должен добавить дни ещё раз."""
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    panel.modes = ["lost"]
    abs_ms = _abs_from(e, 30)
    with pytest.raises(api.RemnawaveAPIError) as exc:
        asyncio.run(_call(pid="pay-l", days=30, abs_ms=abs_ms))
    assert exc.value.ambiguous
    assert panel.expire_ms() == e + 30 * DAY_MS
    assert _record("pay-l")["state"] == "started"
    asyncio.run(_call(pid="pay-l", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == e + 30 * DAY_MS
    assert _record("pay-l")["state"] == "done"


def test_timeout_without_apply_then_retry_applies_once(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    panel.modes = ["timeout"]
    abs_ms = _abs_from(e, 30)
    with pytest.raises(api.RemnawaveAPIError):
        asyncio.run(_call(pid="pay-t", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == e
    assert _record("pay-t")["state"] == "started"
    asyncio.run(_call(pid="pay-t", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == e + 30 * DAY_MS


def test_panel_error_with_code_deletes_record_and_retry_applies(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    panel.modes = ["code"]
    abs_ms = _abs_from(e, 30)
    with pytest.raises(api.RemnawaveAPIError) as exc:
        asyncio.run(_call(pid="pay-c", days=30, abs_ms=abs_ms))
    assert not exc.value.ambiguous
    assert _record("pay-c") is None
    asyncio.run(_call(pid="pay-c", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == e + 30 * DAY_MS


def test_a_failed_b_applied_retry_a_gives_both_periods(panel_env):
    """A не применился (таймаут), B применился, повтор A: итог E + dA + dB."""
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    abs_a, abs_b = _abs_from(e, 30), _abs_from(e, 10)
    panel.modes = ["timeout"]
    with pytest.raises(api.RemnawaveAPIError):
        asyncio.run(_call(pid="pay-A", days=30, abs_ms=abs_a))
    asyncio.run(_call(pid="pay-B", days=10, abs_ms=abs_b))
    assert panel.expire_ms() == e + 10 * DAY_MS
    assert _record("pay-A") is None, "B закрыл неприменённую запись A"
    asyncio.run(_call(pid="pay-A", days=30, abs_ms=abs_a))
    assert panel.expire_ms() == e + 40 * DAY_MS


def test_a_applied_but_unconfirmed_b_applied_retry_a_does_not_add_again(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    abs_a, abs_b = _abs_from(e, 30), _abs_from(e, 10)
    panel.modes = ["lost"]
    with pytest.raises(api.RemnawaveAPIError):
        asyncio.run(_call(pid="pay-A", days=30, abs_ms=abs_a))
    asyncio.run(_call(pid="pay-B", days=10, abs_ms=abs_b))
    assert panel.expire_ms() == e + 40 * DAY_MS
    assert _record("pay-A")["state"] == "done"
    asyncio.run(_call(pid="pay-A", days=30, abs_ms=abs_a))
    assert panel.expire_ms() == e + 40 * DAY_MS


def test_crash_between_started_and_patch_then_retry_applies_once(panel_env, monkeypatch):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e)
    real_ensure = api.ensure_user

    async def boom(**kw):
        raise RuntimeError("процесс упал")

    monkeypatch.setattr(api, "ensure_user", boom)
    abs_ms = _abs_from(e, 30)
    with pytest.raises(RuntimeError):
        asyncio.run(_call(pid="pay-x", days=30, abs_ms=abs_ms))
    assert _record("pay-x")["state"] == "started"
    assert panel.expire_ms() == e
    monkeypatch.setattr(api, "ensure_user", real_ensure)
    asyncio.run(_call(pid="pay-x", days=30, abs_ms=abs_ms))
    assert panel.expire_ms() == e + 30 * DAY_MS


def test_cancellation_leaves_started_record_and_releases_lock(panel_env, monkeypatch):
    database, make = panel_env
    _set(database, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel = make(e, patch_delay=5.0)

    async def run():
        task = asyncio.ensure_future(_call(pid="pay-cancel", days=30, abs_ms=_abs_from(e, 30)))
        await asyncio.sleep(0.4)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert _record("pay-cancel")["state"] == "started"
    assert _tables(database)[0] == 0, "замок освобождён при отмене"
    assert panel.expire_ms() == e


def test_transaction_label_is_written_when_row_exists_and_is_optional(panel_env):
    database, make = panel_env
    _set(database, delta="payments")
    import sqlite3

    with sqlite3.connect(database.DB_FILE) as conn:
        conn.execute(
            "INSERT INTO transactions (payment_id, user_id, status, amount_rub, metadata) VALUES (?, ?, ?, ?, ?)",
            ("pay-lbl", 1001, "pending", 100.0, json.dumps({"action": "extend"})),
        )
    e = _now_ms() + 10 * DAY_MS
    make(e)
    asyncio.run(_call(pid="pay-lbl", days=30, abs_ms=_abs_from(e, 30)))
    with sqlite3.connect(database.DB_FILE) as conn:
        meta = json.loads(conn.execute("SELECT metadata FROM transactions WHERE payment_id='pay-lbl'").fetchone()[0])
    assert meta["action"] == "extend"
    assert meta["extension"]["state"] == "done" and meta["extension"]["days"] == 30
    asyncio.run(_call(pid="pay-no-row", days=30, abs_ms=_abs_from(e, 30)))


def test_cleanup_old_extensions_removes_only_old_done_records(temp_db):
    guard.extension_start("old-done", "k", 1, "payment", 30)
    guard.extension_done("old-done", 1)
    guard.extension_start("old-started", "k", 1, "payment", 30)
    guard.extension_start("fresh-done", "k", 1, "payment", 30)
    guard.extension_done("fresh-done", 1)
    future = time.time() + 91 * 86400
    import sqlite3

    with sqlite3.connect(temp_db.DB_FILE) as conn:
        conn.execute("UPDATE key_extension_applied SET created_at = ? WHERE payment_id IN ('old-done','old-started')", (time.time() - 100 * 86400,))
    assert guard.cleanup_old_extensions() == 1
    assert guard.extension_get("old-done") is None
    assert guard.extension_get("old-started") is not None
    assert guard.extension_get("fresh-done") is not None
    assert guard.cleanup_old_extensions(now=future) == 1


def test_ops_alerts_dedupe_and_sent_flag(temp_db):
    first = guard.add_ops_alert("k", "t", dedupe_seconds=60)
    assert first
    assert guard.add_ops_alert("k", "t", dedupe_seconds=60) is None
    guard.add_ops_alert("k", "other")
    alerts = guard.fetch_unsent_alerts()
    assert len(alerts) == 2
    guard.mark_alerts_sent([a["id"] for a in alerts])
    assert guard.fetch_unsent_alerts() == []


def test_wait_inflight_waits_for_running_writes():
    assert guard.wait_inflight(0.1) is True
    finished = []

    def work():
        with guard.track_inflight():
            time.sleep(0.4)
            finished.append(1)

    t = threading.Thread(target=work)
    t.start()
    time.sleep(0.1)
    assert guard.inflight_count() == 1
    assert guard.wait_inflight(0.05) is False
    assert guard.wait_inflight(5) is True and finished
    t.join()


def test_wal_check_reports_mode(temp_db):
    assert guard.check_wal_mode() == "wal"


# --- два процесса с общей БД ----------------------------------------------------------

_CHILD = textwrap.dedent(
    """
    import asyncio, fcntl, json, sys
    from datetime import datetime, timezone
    from pathlib import Path
    sys.path.insert(0, sys.argv[3])
    from shop_bot.data_manager import database
    database.DB_FILE = Path(sys.argv[1])
    from shop_bot.modules import remnawave_api as api
    panel_file, pid, abs_ms = sys.argv[2], sys.argv[4], int(sys.argv[5])
    api.rw_repo.get_squad = lambda host: {"host_name": "h1", "squad_uuid": "sq"}
    api.rw_repo.get_squad_by_class = lambda host, cls: None

    def _iso(ms):
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    class R:
        def __init__(self, p, s=200): self.p, self.status_code = p, s
        def json(self): return self.p

    async def transport(host, method, path, **kw):
        with open(panel_file, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            data = json.load(f)
            if method == "GET":
                return R({"response": data})
            await asyncio.sleep(0.3)
            data["expireAt"] = kw["json_payload"]["expireAt"]
            f.seek(0); f.truncate(); json.dump(data, f)
            return R({"response": data})

    api._request_for_host = transport
    asyncio.run(api.create_or_update_key_on_host("h1", "1001-1@bot.local", days_to_add=30,
                expiry_timestamp_ms=abs_ms, payment_id=pid, raise_on_error=True))
    """
)


def test_two_processes_with_shared_database_add_both_periods(temp_db, tmp_path):
    _set(temp_db, delta="payments")
    e = _now_ms() + 10 * DAY_MS
    panel_file = tmp_path / "panel.json"
    panel_file.write_text(json.dumps({"id": 7, "uuid": "u", "username": "1001-1", "expireAt": _iso(e), "shortUuid": "s"}))
    root = str(Path(__file__).resolve().parents[1] / "src")
    abs_ms = _abs_from(e, 30)
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", _CHILD, str(temp_db.DB_FILE), str(panel_file), root, pid, str(abs_ms)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "SHOPBOT_SERVICE_NAME": "t"},
        )
        for pid in ("proc-a", "proc-b")
    ]
    outs = [p.communicate(timeout=120) for p in procs]
    for p, (out, err) in zip(procs, outs):
        assert p.returncode == 0, err.decode()[-2000:]
    final = _ms(json.loads(panel_file.read_text())["expireAt"])
    assert final == e + 60 * DAY_MS
    assert _tables(temp_db) == (0, 2)
