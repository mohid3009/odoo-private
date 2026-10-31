"""Extension point for the discounts app (Phase 5, person B). Until then billing runs with no discounts.

Contract, called by `engine.build_invoice` inside the billing transaction, in this order:

1. `pick_discounts(sub, product_lines, period_start, period_end)` -> list[engine.DiscountLine]
   Eligible rules (D-010/D-011): at most one per line (largest saving wins) plus at most one subscription-level rule.
   `product_lines` is a list of dicts: description, quantity, unit_price, tax_rate, taxes, product.
2. `reserve(picks)` -> the subset that could actually be redeemed. Must be race-safe:
   `UPDATE discounts_discount SET used_count = used_count + 1 WHERE id=%s AND (usage_limit IS NULL OR used_count < usage_limit)`;
   0 rows updated -> drop that discount from this invoice. Running inside the billing transaction means a rollback undoes the increment.
3. `record(invoice, picks)` -> insert `DiscountRedemption(discount, invoice, amount)` rows (UNIQUE (discount, invoice)).

A `DiscountLine` carries the tax rate/taxes of the line it reduces, so tax is computed on the post-discount amount.
"""


def pick_discounts(sub, product_lines, period_start, period_end):
    return []


def reserve(picks):
    return picks


def record(invoice, picks):
    return None
