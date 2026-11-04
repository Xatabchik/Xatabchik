"""Маркеры этапов платежа PAYMENT_FLOW: формат, санитизация, исход Future, точки в выдаче."""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re

import pytest

from conftest import temp_db  # noqa: F401
from shop_bot.data_manager import payment_flow_log as pfl

LOGGER = "shop_bot.data_manager.payment_flow_log"
_SAFE_LINE = re.compile(r"^PAYMENT_FLOW( [A-Za-z0-9_.:?\-]+=[A-Za-z0-9_.:?\-]+(\.\.\.)?)+$")


def _lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


def test_marker_format_and_defaults(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_payment_stage("handler_start", "pid-1", None, action="new")
        pfl.log_payment_stage("webhook_received", None, "", mode="")
    assert _lines(caplog) == [
        "PAYMENT_FLOW stage=handler_start payment_id=pid-1 provider_id=- action=new",
        "PAYMENT_FLOW stage=webhook_received payment_id=- provider_id=- mode=-",
    ]
    assert all(r.levelno == logging.INFO for r in caplog.records if r.name == LOGGER)


@pytest.mark.parametrize(
    "untrusted",
    [
        "2f1c\nPAYMENT_FLOW stage=delivered payment_id=evil",
        "abc\r\ndef",
        "id with spaces",
        "a=b=c",
        "идентификатор😀",
        "x" * 10_000,
        "\x00\x1b[31mred",
    ],
)
def test_untrusted_provider_id_is_sanitized(caplog, untrusted):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_payment_stage("webhook_received", None, untrusted)
    (line,) = _lines(caplog)
    assert "\n" not in line and "\r" not in line
    assert _SAFE_LINE.match(line), line
    value = line.split("provider_id=", 1)[1]
    assert " " not in value
    assert len(value) <= 64 + 3
    assert line.count("stage=") == 1
    assert line.count("payment_id=") == 1


def test_long_value_is_marked_as_truncated(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_payment_stage("webhook_received", "p" * 64, "q" * 65)
    (line,) = _lines(caplog)
    assert f"payment_id={'p' * 64} " in line
    assert line.endswith(f"provider_id={'q' * 64}...")


def test_helper_never_raises(caplog):
    class _Bad:
        def __str__(self):
            raise RuntimeError("boom")

    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_payment_stage("x", _Bad(), _Bad(), extra=_Bad())
    pfl.log_payment_stage(None, None)


def _done_future(*, result=None, exc=None) -> concurrent.futures.Future:
    fut: concurrent.futures.Future = concurrent.futures.Future()
    if exc is not None:
        fut.set_exception(exc)
    else:
        fut.set_result(result)
    return fut


@pytest.mark.parametrize("result, outcome", [(True, "ok"), (False, "failed"), (None, "no_result")])
def test_dispatch_done_outcome(caplog, result, outcome):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_dispatch_done(_done_future(result=result), payment_id="pid-1", provider_id="prov-1")
    assert _lines(caplog) == [f"PAYMENT_FLOW stage=dispatch_done payment_id=pid-1 provider_id=prov-1 outcome={outcome}"]


def test_dispatch_done_exception_logs_class_only(caplog):
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_dispatch_done(_done_future(exc=ValueError("secret metadata here")), payment_id="pid-1")
    (line,) = _lines(caplog)
    assert line == "PAYMENT_FLOW stage=dispatch_done payment_id=pid-1 provider_id=- outcome=error error=ValueError"
    assert "secret" not in line


def test_dispatch_done_cancelled_does_not_call_exception(caplog):
    class _CancelledFuture:
        def __init__(self):
            self.exception_called = False
            self.result_called = False

        def cancelled(self):
            return True

        def exception(self):
            self.exception_called = True
            raise concurrent.futures.CancelledError()

        def result(self):
            self.result_called = True
            raise concurrent.futures.CancelledError()

    fut = _CancelledFuture()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_dispatch_done(fut, payment_id="pid-1")
    assert not fut.exception_called and not fut.result_called
    assert _lines(caplog) == ["PAYMENT_FLOW stage=dispatch_done payment_id=pid-1 provider_id=- outcome=cancelled"]


def test_dispatch_done_real_cancelled_future(caplog):
    fut: concurrent.futures.Future = concurrent.futures.Future()
    assert fut.cancel()
    with caplog.at_level(logging.INFO, logger=LOGGER):
        pfl.log_dispatch_done(fut, payment_id="pid-1")
    assert _lines(caplog)[-1].endswith("outcome=cancelled")


def test_dispatch_done_never_raises():
    class _Broken:
        def cancelled(self):
            raise RuntimeError("boom")

    pfl.log_dispatch_done(_Broken(), payment_id="pid-1")


def test_dispatch_done_as_callback_on_real_loop(caplog):
    async def _work():
        return None

    loop = asyncio.new_event_loop()
    try:
        with caplog.at_level(logging.INFO, logger=LOGGER):
            fut = asyncio.run_coroutine_threadsafe(_work(), loop)
            fut.add_done_callback(lambda f: pfl.log_dispatch_done(f, payment_id="pid-2"))
            loop.run_until_complete(asyncio.sleep(0.05))
            fut.result(timeout=1)
    finally:
        loop.close()
    assert _lines(caplog) == ["PAYMENT_FLOW stage=dispatch_done payment_id=pid-2 provider_id=- outcome=no_result"]


# --- маркеры в process_successful_payment ----------------------------------------

def test_fulfillment_markers_for_new_key(temp_db, monkeypatch, caplog):
    from test_fulfillment_unreachable_chat import _buy_with_balance, _fake_bot_class, _stub_panel

    _fake_bot_class(monkeypatch, send_raises=False)
    _stub_panel(monkeypatch, email_marker="flowlog")
    with caplog.at_level(logging.INFO, logger=LOGGER):
        resp = _buy_with_balance(monkeypatch, user_id=4545, host_name="FlowHost", username="flowbuyer")
    assert resp.json().get("paid") is True, resp.json()
    lines = _lines(caplog)
    stages = [re.search(r"stage=(\S+)", line).group(1) for line in lines]
    assert stages == ["handler_start", "claim_taken", "delivered", "tx_logged"], lines
    pids = {re.search(r"payment_id=(\S+)", line).group(1) for line in lines}
    assert len(pids) == 1 and "-" not in pids
    assert "action=new" in lines[0]
    assert lines[-1].endswith("ok=True")
    joined = "\n".join(lines)
    for leaked in ("flowbuyer", "@", "http", "FlowHost", "price", "metadata"):
        assert leaked not in joined


def test_fulfillment_marker_claim_duplicate(temp_db, monkeypatch, caplog):
    from shop_bot.bot.user_router import fulfillment
    from shop_bot.data_manager import database

    assert database.claim_processed_payment("dup-pid")
    meta = {"action": "new", "user_id": 4646, "price": 100.0, "payment_id": "dup-pid", "yookassa_payment_id": "yk-1"}
    with caplog.at_level(logging.INFO, logger=LOGGER):
        assert asyncio.run(fulfillment.process_successful_payment(object(), meta)) is True
    assert _lines(caplog) == [
        "PAYMENT_FLOW stage=handler_start payment_id=dup-pid provider_id=yk-1 action=new",
        "PAYMENT_FLOW stage=claim_duplicate payment_id=dup-pid provider_id=yk-1",
    ]
