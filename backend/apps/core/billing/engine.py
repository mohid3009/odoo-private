"""Billing engine (docs/BILLING_ENGINE.md). Exactly-once: UNIQUE(subscription, period_start) + row lock + a cursor that
moves in the same transaction as the invoice insert. One failing subscription never stops a run."""
import calendar
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from functools import partial

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.subscriptions import services as sub_services
from apps.core.subscriptions.models import Subscription
from integrations.odoo import sync

from . import discount_hooks
from .models import BillingRun, Invoice, InvoiceLine

log = logging.getLogger(__name__)
q2 = sub_services.q2
S = Subscription.Status
MAX_CATCHUP = 12  # D-015: periods billed per subscription per run


# --- period arithmetic -----------------------------------------------------------------------

def add_months(d, n, anchor_day):
    """d + n months, landing on `anchor_day` when the month is long enough (31 Jan -> 28 Feb -> 31 Mar: no drift)."""
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    m += 1
    return date(y, m, min(anchor_day, calendar.monthrange(y, m)[1]))


def next_period_start(start, period, anchor):
    """Start of the period after the one beginning on `start`; `anchor` is the subscription's start date."""
    if period == "daily":
        return start + timedelta(days=1)
    if period == "weekly":
        return start + timedelta(days=7)
    if period == "monthly":
        return add_months(start, 1, anchor.day)
    if period == "yearly":
        return add_months(start, 12, anchor.day)
    raise ValueError(f"unknown billing period {period!r}")


# --- pricing (pure) --------------------------------------------------------------------------

@dataclass
class DiscountLine:
    description: str
    amount: Decimal  # positive: how much is taken off
    tax_rate: Decimal  # rate of the line it reduces
    taxes: list = field(default_factory=list)
    discount: object = None  # the rule (set by the discounts app)


def price_lines(product_lines, discount_lines=()):
    """Pure money math. Tax is computed per line on the post-discount amount: a discount line carries the tax rate of
    the line it reduces, so its (negative) tax cancels the matching part of the product line's tax.
    Totals are sums of rounded line values."""
    rows = []
    for l in product_lines:
        sub = q2(l["quantity"] * l["unit_price"])
        tax = q2(sub * l["tax_rate"] / 100)
        rows.append({**l, "kind": "product", "line_subtotal": sub, "line_tax": tax, "line_total": sub + tax})
    for d in discount_lines:
        sub = -q2(d.amount)
        tax = q2(sub * d.tax_rate / 100)
        rows.append({"kind": "discount", "description": d.description, "quantity": 1, "unit_price": sub, "tax_rate": d.tax_rate,
                     "taxes": d.taxes, "product": None, "line_subtotal": sub, "line_tax": tax, "line_total": sub + tax})
    subtotal = sum((r["line_subtotal"] for r in rows if r["kind"] == "product"), Decimal("0.00"))
    discount_total = -sum((r["line_subtotal"] for r in rows if r["kind"] == "discount"), Decimal("0.00"))
    tax_total = sum((r["line_tax"] for r in rows), Decimal("0.00"))
    return {"lines": rows, "subtotal": subtotal, "discount_total": discount_total, "tax_total": tax_total,
            "total": subtotal - discount_total + tax_total}


def product_lines_for(sub):
    out = []
    for l in sub.lines.select_related("product").prefetch_related("taxes"):
        taxes = list(l.taxes.all())
        out.append({"description": l.description, "quantity": l.quantity, "unit_price": l.unit_price,
                    "tax_rate": sum((t.rate for t in taxes), Decimal("0.00")), "taxes": taxes, "product": l.product})
    return out


def build_invoice(sub, start, end, as_of, hooks=discount_hooks):
    """Create the draft invoice for one period (call inside the billing transaction)."""
    product_lines = product_lines_for(sub)
    if not product_lines:
        raise ValueError(f"{sub.number} has no lines to bill")
    picks = hooks.reserve(hooks.pick_discounts(sub, product_lines, start, end))
    priced = price_lines(product_lines, picks)
    invoice = Invoice.objects.create(
        subscription=sub, customer_id=sub.customer_id, status=Invoice.Status.DRAFT, invoice_date=as_of,
        due_date=as_of + timedelta(days=sub.payment_term.days), period_start=start, period_end=end,
        subtotal=priced["subtotal"], discount_total=priced["discount_total"], tax_total=priced["tax_total"],
        total=priced["total"], amount_paid=Decimal("0.00"), amount_due=priced["total"],
    )
    for r in priced["lines"]:
        line = InvoiceLine.objects.create(
            invoice=invoice, kind=r["kind"], product=r["product"], description=r["description"], quantity=r["quantity"],
            unit_price=r["unit_price"], tax_rate_snapshot=r["tax_rate"], line_subtotal=r["line_subtotal"],
            line_tax=r["line_tax"], line_total=r["line_total"],
        )
        line.taxes.set(r["taxes"])
    hooks.record(invoice, picks)
    return invoice


# --- the run ---------------------------------------------------------------------------------

def bill_subscription(sub_id, as_of, stats, hooks=discount_hooks):
    """Bill every period due up to `as_of` (cap MAX_CATCHUP). Each period is its own transaction, so a failure
    on period 3 keeps periods 1-2. `stats` is a BillingRun (or any object with created_count / skipped_count)."""
    for _ in range(MAX_CATCHUP):
        with transaction.atomic():
            sub = (
                Subscription.objects.select_for_update(skip_locked=True)
                .select_related("plan", "payment_term").filter(pk=sub_id).first()
            )
            if sub is None or sub.status != S.ACTIVE or not sub.next_invoice_date:
                return  # gone, locked by another run, paused/closed meanwhile
            start = sub.next_invoice_date
            if sub.expiry_date and start > sub.expiry_date:  # nothing left to bill
                if sub.plan.auto_close and sub.expiry_date < as_of:
                    sub_services.transition(sub, S.CLOSED, None, today=as_of)
                return
            if start > as_of:
                return
            nxt = next_period_start(start, sub.plan.billing_period, sub.start_date)
            if Invoice.objects.filter(subscription=sub, period_start=start).exists():
                # cursor was behind the data (e.g. a crash, or a cancelled period): repair it, never re-bill
                sub.next_invoice_date = nxt
                sub.save(update_fields=["next_invoice_date"])
                stats.skipped_count += 1
                continue
            invoice = build_invoice(sub, start, nxt - timedelta(days=1), as_of, hooks)
            sub.next_invoice_date = nxt
            sub.save(update_fields=["next_invoice_date"])
            stats.created_count += 1
            transaction.on_commit(partial(sync.create_draft_invoice, invoice.pk))  # Odoo failure -> 'pending', never a rollback


def run_billing(as_of=None, user=None, hooks=discount_hooks):
    as_of = as_of or timezone.localdate()
    run = BillingRun.objects.create(as_of_date=as_of, triggered_by=user if getattr(user, "is_authenticated", False) else None)
    problems = []
    try:
        sub_services.activate_due(as_of)
    except Exception as e:  # activation trouble must not stop invoicing of already-active subscriptions
        log.exception("activate_due failed")
        run.error_count += 1
        problems.append(f"activate_due: {type(e).__name__}: {e}")
    ids = (
        Subscription.objects.filter(status=S.ACTIVE)
        .filter(Q(next_invoice_date__lte=as_of) | Q(expiry_date__lt=as_of))
        .order_by("next_invoice_date", "id").values_list("id", flat=True)
    )
    for sid in list(ids):
        try:
            bill_subscription(sid, as_of, run, hooks)
        except Exception as e:  # isolation: log, count, carry on
            log.exception("billing failed for subscription %s", sid)
            run.error_count += 1
            problems.append(f"subscription {sid}: {type(e).__name__}: {e}")
    run.log = "\n".join(problems)
    run.finished_at = timezone.now()
    run.save()
    # TODO(phase 7): run_notifications() here, so reminders follow every billing run
    return run
