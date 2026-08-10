"""Тесты снятия реферальной связи (unlink) из админки."""
from conftest import temp_db  # noqa: F401


def test_unlink_referral_clears_referred_by(temp_db):
    database = temp_db
    REFERRER = 7001
    INVITEE = 7002
    database.register_user_if_not_exists(REFERRER, "referrer", None)
    database.register_user_if_not_exists(INVITEE, "invitee", REFERRER)

    assert database.get_user(INVITEE)["referred_by"] == REFERRER
    assert database.unlink_referral(INVITEE, REFERRER) == "unlinked"
    assert database.get_user(INVITEE)["referred_by"] is None
    assert database.get_referrals_for_user(REFERRER) == []


def test_unlink_referral_wrong_referrer(temp_db):
    database = temp_db
    REFERRER = 7011
    OTHER = 7012
    INVITEE = 7013
    database.register_user_if_not_exists(REFERRER, "referrer", None)
    database.register_user_if_not_exists(OTHER, "other", None)
    database.register_user_if_not_exists(INVITEE, "invitee", REFERRER)

    assert database.unlink_referral(INVITEE, OTHER) == "not_linked"
    assert database.get_user(INVITEE)["referred_by"] == REFERRER


def test_unlink_referral_not_found(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7021, "referrer", None)
    assert database.unlink_referral(999999, 7021) == "not_found"


def test_unlink_all_referrals(temp_db):
    database = temp_db
    REFERRER = 7031
    database.register_user_if_not_exists(REFERRER, "referrer", None)
    for i, uid in enumerate((7032, 7033, 7034)):
        database.register_user_if_not_exists(uid, f"invitee{i}", REFERRER)

    ok, removed = database.unlink_all_referrals(REFERRER)
    assert ok is True
    assert removed == 3
    assert database.get_referrals_for_user(REFERRER) == []
    for uid in (7032, 7033, 7034):
        assert database.get_user(uid)["referred_by"] is None


def test_unlink_all_referrals_empty(temp_db):
    database = temp_db
    database.register_user_if_not_exists(7041, "referrer", None)
    ok, removed = database.unlink_all_referrals(7041)
    assert ok is True
    assert removed == 0
