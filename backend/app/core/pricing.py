"""Shared pricing rules (spec §9.1, §9.2) — used identically by the checkout preview and the
final order-creation transaction so the two can never disagree. Zone/weight-based shipping and
per-line tax_class rates are simplified to flat settings-driven values (no zones/weights modelled
yet); documented in done.MD."""

from decimal import ROUND_HALF_UP, Decimal

from app.core.config import get_settings

settings = get_settings()


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_shipping_fee(*, subtotal: Decimal, payment_method: str, free_shipping: bool) -> Decimal:
    if free_shipping:
        return Decimal("0")
    if subtotal >= Decimal(settings.free_shipping_threshold):
        return Decimal("0")
    fee = Decimal(settings.shipping_flat_fee)
    if payment_method == "cod":
        fee += Decimal(settings.cod_surcharge)
    return q2(fee)


def compute_tax(taxable_base: Decimal) -> Decimal:
    rate = Decimal(settings.tax_rate_percent) / Decimal(100)
    return q2(taxable_base * rate)
