"""The engine's discount extension point; the implementation is `apps.finance.discounts.services` (Phase 5).

Called by `engine.build_invoice` inside the billing transaction, in this order:

1. `pick_discounts(sub, product_lines, period_start, period_end, as_of)` -> list[engine.DiscountLine]
   `product_lines`: dicts with description, quantity, unit_price, tax_rate, taxes, product. `as_of` is the billing date.
2. `reserve(picks)` -> the picks that could really be redeemed (race-safe conditional UPDATE of `used_count`).
3. `record(invoice, picks)` -> one `DiscountRedemption` per distinct discount.

Tests substitute a stub with the same three functions (see tests/test_billing_engine.py). Imports are lazy so the billing app
does not depend on the discounts app at import time.
"""


def pick_discounts(sub, product_lines, period_start, period_end, as_of):
    from apps.finance.discounts import services

    return services.pick_discounts(sub, product_lines, period_start, period_end, as_of)


def reserve(picks):
    from apps.finance.discounts import services

    return services.reserve(picks) if picks else picks


def record(invoice, picks):
    from apps.finance.discounts import services

    if picks:
        services.record(invoice, picks)
