from decimal import Decimal

from app.services.yookassa_apply import credits_pack_allowed_amounts_rub


def test_credits_pack_allowed_amounts_full_price():
    allowed = credits_pack_allowed_amounts_rub(Decimal("990.00"))
    assert allowed == {Decimal("990.00")}


def test_credits_pack_allowed_amounts_partner_discount():
    allowed = credits_pack_allowed_amounts_rub(
        Decimal("990.00"),
        discounted_pay_rub=891,
        meta_partner_discount_rub=99,
    )
    assert Decimal("990.00") in allowed
    assert Decimal("891.00") in allowed


def test_discounted_payment_accepted_not_rejected():
    """Регрессия: оплата со скидкой должна входить в allowed, а не падать как mismatch."""
    expected = Decimal("990.00")
    paid = Decimal("891.00")
    allowed = credits_pack_allowed_amounts_rub(
        expected,
        discounted_pay_rub=891,
        meta_partner_discount_rub=99,
    )
    paid_q = paid.quantize(Decimal("0.01"))
    assert paid_q in allowed
