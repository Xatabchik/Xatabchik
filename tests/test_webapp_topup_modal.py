"""Окно пополнения баланса доводит платёж до видимого результата.

Раньше оно этого не делало, и после оплаты выглядело так, будто платежа не
было. Причин было две, и обе видны в коде окна:

1. Незакрытый счёт нигде не сохранялся. Счёт за ключ кладётся в localStorage
   (`pendingPayment`) и восстанавливается в `openPaymentModal`, поэтому уход на
   страницу оплаты и возврат в Mini App его не теряет. У пополнения такого не
   было: после перезагрузки окно открывалось на шаге ввода суммы.
2. При успехе окно просто закрывалось (`closeActionModal`) с всплывающим
   уведомлением, а его содержимое так и оставалось на «Ожидаем оплату».
   Покупка ключа в этом месте показывает отдельный экран результата
   (`showSuccessScreen` → `changePaymentStep('success')`).

Плюс третье, появившееся вместе с честным /api/check-payment: между
подтверждением платежа и выдачей услуги ответ содержит `processing: true` и
`paid: false`, а окно реагировало только на `paid` — и продолжало писать
«Ожидаем оплату».

Тесты структурные: JS-раннера в проекте нет, поэтому проверяется тот же способ,
что и в test_webapp_payment_poll.py — наличие поведения в коде окна.
"""
from pathlib import Path

from webapp_frontend_src import mini_app_frontend_source

HTML = mini_app_frontend_source()


def _body(start: str, end: str) -> str:
    """Текст между двумя объявлениями — тело интересующей функции."""
    assert start in HTML, f"не найдено объявление {start!r}"
    start_idx = HTML.index(start)
    end_idx = HTML.index(end, start_idx)
    return HTML[start_idx:end_idx]


def test_topup_invoice_is_remembered_so_it_survives_a_reload():
    waiting = _body("function _renderTopUpWaiting(", "function _markTopUpProcessing(")
    assert "_rememberPendingTopUp({ paymentId" in waiting
    remember = _body("function _rememberPendingTopUp(", "function _forgetPendingTopUp(")
    assert "localStorage.setItem(TOPUP_PENDING_KEY" in remember
    assert "timestamp: Date.now()" in remember


def test_unfinished_topup_invoice_is_restored_when_the_window_opens():
    opener = _body("function openTopUpModal(", "function _renderTopUpAmountStep(")
    assert "_readPendingTopUp()" in opener
    assert "_renderTopUpWaiting(" in opener
    # Шаг ввода суммы остаётся поведением по умолчанию — только если счёта нет.
    assert opener.index("_readPendingTopUp()") < opener.index("_renderTopUpAmountStep(contentEl)")

    reader = _body("function _readPendingTopUp(", "function _stopTrackingTopUp(")
    assert "TOPUP_PENDING_TTL_MS" in reader, "просроченный счёт должен отбрасываться"
    assert "!data.paymentId" in reader


def test_paid_topup_shows_the_result_instead_of_silently_closing():
    polling = _body("function _startTopUpPolling(", "function openReferralMethodsModal(")
    assert "_renderTopUpSuccess(amount, data)" in polling
    assert "closeActionModal()" not in polling, "окно снова закрывается вместо показа результата"
    assert "_forgetPendingTopUp()" in polling
    # Результат рисуется раньше обновления остального интерфейса, чтобы сбой в
    # обновлении не оставил окно на «ожидаем оплату».
    assert polling.index("_renderTopUpSuccess(") < polling.index("_refreshBalanceAfterTopUp()")


def test_success_screen_shows_credited_amount_and_new_balance():
    success = _body("function _renderTopUpSuccess(", "async function _refreshBalanceAfterTopUp(")
    assert "Баланс пополнен" in success
    assert "Зачислено" in success
    assert "Текущий баланс" in success
    assert "topup-success-balance" in success
    assert "data.balance" in success


def test_window_says_the_payment_arrived_while_the_service_is_still_running():
    poll = _body("async function _tickPaymentPoll(", "function startStatusPolling(")
    assert "data.processing" in poll
    assert "_paymentPollOnProcessing" in poll

    starter = _body("function startStatusPolling(", "async function refreshAppData(")
    assert "onProcessing" in starter

    marker = _body("function _markTopUpProcessing(", "function _renderTopUpSuccess(")
    assert "Оплата получена" in marker
    assert "topup-waiting-title" in marker


def test_tracking_of_an_abandoned_invoice_can_be_stopped():
    stop = _body("function _stopTrackingTopUp(", "function _renderTopUpWaiting(")
    assert "_forgetPendingTopUp()" in stop
    assert "_stopStatusPolling()" in stop
    assert "_renderTopUpAmountStep(contentEl)" in stop

    waiting = _body("function _renderTopUpWaiting(", "function _markTopUpProcessing(")
    assert 'data-topup-action="stop-tracking"' in waiting, "из окна ожидания нет выхода к новому счёту"
    # Кнопка не должна обещать отмену: счёт у провайдера остаётся действующим и
    # поздняя оплата по нему по-прежнему будет обработана вебхуком.
    assert "Отменить счёт" not in HTML
    assert "Вернуться к вводу суммы" in waiting


def test_platega_verification_also_ends_on_the_result_screen():
    verify = _body("async function verifyPlategaTopUp(", "function _reopenTopUpPaymentLink(")
    assert "_renderTopUpSuccess(window._topUpAmount, data)" in verify
    assert "_forgetPendingTopUp()" in verify
