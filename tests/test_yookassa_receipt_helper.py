from shop_bot.bot.user_router.formatting import build_yookassa_receipt


def test_receipt_built_for_valid_email():
    receipt = build_yookassa_receipt(" shop@example.com ", "Докупка 5 ГБ трафика", "99.00")
    assert receipt == {
        "customer": {"email": "shop@example.com"},
        "items": [{
            "description": "Докупка 5 ГБ трафика",
            "quantity": "1.00",
            "amount": {"value": "99.00", "currency": "RUB"},
            "vat_code": "1",
            "payment_subject": "service",
            "payment_mode": "full_payment",
        }],
    }


def test_receipt_rejected_for_missing_or_invalid_email():
    for email in (None, "", "   ", "not-an-email", "a@b", "a b@example.com", "a@example.com\nBcc: x@y.z"):
        assert build_yookassa_receipt(email, "desc", "10.00") is None
