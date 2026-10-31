"""Discount selection and redemption for the billing engine (contract: apps/core/billing/discount_hooks.py).

pick_discounts -> reserve -> record run inside the billing transaction, so a rolled-back invoice also rolls back the
usage count. Stacking (D-010): at most one rule per line (largest saving) plus at most one subscription rule per invoice."""
from decimal import Decimal

from django.db.models import F, Q

from apps.core.billing.engine import DiscountLine
from apps.core.subscriptions.services import q2

from .models import Discount, DiscountRedemption

ZERO = Decimal("0.00")


def usable(qs, as_of):
    """Rules that are active, inside their date window on `as_of`, and not exhausted."""
    return (
        qs.filter(is_active=True)
        .filter(Q(start_date__isnull=True) | Q(start_date__lte=as_of))
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=as_of))
        .filter(Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit")))
    )


def saving(rule, base):
    """percent: value% of base; fixed: value, capped at base."""
    if base <= 0:
        return ZERO
    amount = q2(base * rule.value / 100) if rule.type == Discount.Type.PERCENT else q2(rule.value)
    return min(amount, base)


def label(rule):
    v = f"{rule.value:f}".rstrip("0").rstrip(".") or "0"
    return f"{rule.name} ({v}% off)" if rule.type == Discount.Type.PERCENT else f"{rule.name} (₹{v} off)"


def pick_discounts(sub, product_lines, period_start, period_end, as_of):
    picks, nets = [], []
    rules = list(usable(Discount.objects.filter(scope=Discount.Scope.PRODUCT), as_of).prefetch_related("products"))
    rule_products = {r.pk: {p.pk for p in r.products.all()} for r in rules}

    # step 1: product rules, one per line, largest saving wins (ties: lowest id)
    for l in product_lines:
        base = q2(l["quantity"] * l["unit_price"])
        best = None
        for r in rules:
            if l["product"] is None or l["product"].pk not in rule_products[r.pk]:
                continue
            if r.min_quantity and l["quantity"] < r.min_quantity:
                continue
            if r.min_purchase_amount is not None and base < r.min_purchase_amount:
                continue
            s = saving(r, base)
            if s > 0 and (best is None or s > best[0] or (s == best[0] and r.pk < best[1].pk)):
                best = (s, r)
        if best:
            picks.append(DiscountLine(f"{label(best[1])} – {l['description']}", best[0], l["tax_rate"], l["taxes"], best[1]))
        nets.append(base - (best[0] if best else ZERO))

    # step 2: the attached subscription rule, on the subtotal after step 1, spread over the lines by value
    rule = usable(Discount.objects.filter(pk=sub.discount_id, scope=Discount.Scope.SUBSCRIPTION), as_of).first() if sub.discount_id else None
    subtotal = sum(nets, ZERO)
    if rule and subtotal > 0:
        quantity = sum(l["quantity"] for l in product_lines)
        if (not rule.min_quantity or quantity >= rule.min_quantity) and (rule.min_purchase_amount is None or subtotal >= rule.min_purchase_amount):
            total = saving(rule, subtotal)
            idxs = [i for i, n in enumerate(nets) if n > 0]
            left = total
            for k, i in enumerate(idxs):
                share = left if k == len(idxs) - 1 else q2(total * nets[i] / subtotal)
                share = min(share, nets[i])
                left -= share
                if share > 0:
                    l = product_lines[i]
                    picks.append(DiscountLine(f"{label(rule)} – {l['description']}", share, l["tax_rate"], l["taxes"], rule))
    return picks


def reserve(picks):
    """Count one use per distinct rule with a single conditional UPDATE (race-safe: two invoices can never both take the
    last use). A rule that lost the race is dropped from this invoice."""
    won, tried = set(), set()
    for pick in sorted(picks, key=lambda p: p.discount.pk):  # stable lock order across concurrent runs
        pk = pick.discount.pk
        if pk in tried:
            continue
        tried.add(pk)
        updated = (
            Discount.objects.filter(pk=pk, is_active=True)
            .filter(Q(usage_limit__isnull=True) | Q(used_count__lt=F("usage_limit")))
            .update(used_count=F("used_count") + 1)
        )
        if updated:
            won.add(pk)
    return [p for p in picks if p.discount.pk in won]


def record(invoice, picks):
    totals = {}
    for p in picks:
        d, amount = totals.get(p.discount.pk, (p.discount, ZERO))
        totals[p.discount.pk] = (d, amount + p.amount)
    for discount, amount in totals.values():
        DiscountRedemption.objects.get_or_create(discount=discount, invoice=invoice, defaults={"amount": amount})
