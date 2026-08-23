"""Окно ожидания оплаты не молотит /api/check-payment каждые 3 секунды."""
from pathlib import Path

HTML = Path("src/shop_bot/webapp/app.html").read_text(encoding="utf-8")


def test_waiting_window_does_not_poll_every_3s():
    assert "PAYMENT_POLL_MIN_MS = 8000" in HTML
    assert "PAYMENT_POLL_MAX_MS = 20000" in HTML
    assert "/api/check-payment" in HTML
    assert "setInterval(async () => {" not in HTML
    assert "setInterval(async () => {\n                    const response = await fetch('/api/check-payment'" not in HTML


def test_close_waiting_window_stops_polling():
    assert "function closePaymentModal()" in HTML
    close_idx = HTML.index("function closePaymentModal()")
    next_fn = HTML.index("function restorePendingPayment()", close_idx)
    body = HTML[close_idx:next_fn]
    assert "_stopStatusPolling()" in body


def test_poll_skips_hidden_tab_and_inflight():
    assert "document.hidden || _paymentPollInFlight" in HTML
    assert "_tickPaymentPoll" in HTML
    assert "startStatusPolling" in HTML
    assert "_startTopUpPolling" in HTML
    assert "startStatusPolling(paymentId," in HTML
