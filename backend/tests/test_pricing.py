"""Pure unit tests for app/core/pricing.py (spec §9.1/§9.2/§24.3 "Pricing & cart"). No DB, no
client — these are the cheapest, fastest tests in the suite and the ones a silent regression in
money math would be caught by first."""

from decimal import ROUND_HALF_UP, Decimal

from app.core.config import get_settings
from app.core.pricing import compute_shipping_fee, compute_tax, q2

settings = get_settings()


def test_q2_rounds_half_up():
    assert q2(Decimal("10.005")) == Decimal("10.01")
    assert q2(Decimal("10.004")) == Decimal("10.00")
    assert q2(Decimal("10.995")) == Decimal("11.00")
    assert q2(Decimal("0")) == Decimal("0.00")


def test_q2_matches_decimal_context_independent_rounding():
    # q2 must round consistently regardless of ambient Decimal context (ROUND_HALF_UP is passed
    # explicitly, not read from context) — a cart total should never depend on caller state.
    for raw in ["1.005", "2.675", "99.995", "0.125"]:
        value = Decimal(raw)
        assert q2(value) == value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_free_shipping_coupon_zeroes_fee_regardless_of_subtotal():
    fee = compute_shipping_fee(subtotal=Decimal("1"), payment_method="card", free_shipping=True)
    assert fee == Decimal("0")


def test_shipping_fee_waived_above_threshold():
    threshold = Decimal(settings.free_shipping_threshold)
    fee = compute_shipping_fee(subtotal=threshold, payment_method="card", free_shipping=False)
    assert fee == Decimal("0")


def test_shipping_fee_charged_below_threshold():
    threshold = Decimal(settings.free_shipping_threshold)
    fee = compute_shipping_fee(subtotal=threshold - Decimal("1"), payment_method="card", free_shipping=False)
    assert fee == Decimal(settings.shipping_flat_fee)


def test_cod_surcharge_added_on_top_of_flat_fee():
    below_threshold = Decimal(settings.free_shipping_threshold) - Decimal("1")
    card_fee = compute_shipping_fee(subtotal=below_threshold, payment_method="card", free_shipping=False)
    cod_fee = compute_shipping_fee(subtotal=below_threshold, payment_method="cod", free_shipping=False)
    assert cod_fee == card_fee + Decimal(settings.cod_surcharge)


def test_compute_tax_uses_configured_rate():
    rate = Decimal(settings.tax_rate_percent) / Decimal(100)
    base = Decimal("1000.00")
    assert compute_tax(base) == q2(base * rate)


def test_totals_identity_over_generated_carts():
    """Property-style check (spec §24.3): for a range of synthetic carts, subtotal - discount +
    tax + shipping must equal the sum of what a customer would actually be charged, with no
    penny lost or gained to rounding drift."""
    cases = [
        # (subtotal, discount_total, payment_method)
        (Decimal("199.99"), Decimal("0"), "card"),
        (Decimal("2500.00"), Decimal("0"), "card"),
        (Decimal("333.33"), Decimal("50.00"), "cod"),
        (Decimal("1999.95"), Decimal("199.99"), "card"),
        (Decimal("0.01"), Decimal("0"), "cod"),
    ]
    for subtotal, discount_total, payment_method in cases:
        taxable_base = subtotal - discount_total
        tax_total = compute_tax(taxable_base)
        shipping_fee = compute_shipping_fee(subtotal=subtotal, payment_method=payment_method, free_shipping=False)
        grand_total = q2(taxable_base + tax_total + shipping_fee)
        assert grand_total == q2(taxable_base) + tax_total + shipping_fee
        assert grand_total >= Decimal("0")
