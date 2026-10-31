"""Reminder scan (docs/NOTIFICATIONS.md §5): due soon, overdue day 1 / 7, subscription expiring.
Idempotent: notify()'s dedupe_key (event:object:channel:variant) means a rerun creates nothing."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.core.billing.models import Invoice
from apps.core.billing.services import invoice_context
from apps.core.subscriptions.models import Subscription

from .services import notify


def _invoices(due_dates):
    return (
        Invoice.objects.filter(status="confirmed", amount_due__gt=0, due_date__in=due_dates)
        .select_related("customer__profile", "subscription")  # profile is read for every message: no N+1
    )


def _send_invoice_reminders(code, days_to_due_date, variant_prefix):
    """days_to_due_date: {n: due_date}. Returns how many invoices got a new message."""
    sent = 0
    for inv in _invoices(list(days_to_due_date.values())):
        n = next(n for n, d in days_to_due_date.items() if d == inv.due_date)
        ctx = {**invoice_context(inv), "amount": str(inv.amount_due)}  # remind about what is still owed
        sent += bool(notify(code, inv.customer, inv, context=ctx, variant=f"{variant_prefix}{n}"))
    return sent


def run_reminders(as_of=None):
    as_of = as_of or timezone.localdate()
    due_soon = _send_invoice_reminders("INVOICE_DUE_SOON", {settings.NOTIFY_DUE_SOON_DAYS: as_of + timedelta(days=settings.NOTIFY_DUE_SOON_DAYS)}, "d")
    overdue = _send_invoice_reminders("INVOICE_OVERDUE", {n: as_of - timedelta(days=n) for n in settings.NOTIFY_OVERDUE_DAYS}, "d")
    expiring = 0
    n = settings.NOTIFY_EXPIRING_DAYS
    for sub in Subscription.objects.filter(status="active", expiry_date=as_of + timedelta(days=n)).select_related("customer__profile"):
        ctx = {"customer_name": sub.customer.name or sub.customer.email, "subscription_number": sub.number, "expiry_date": str(sub.expiry_date)}
        expiring += bool(notify("SUBSCRIPTION_EXPIRING", sub.customer, sub, context=ctx, variant=f"exp{n}"))
    return {"as_of": as_of, "due_soon": due_soon, "overdue": overdue, "expiring": expiring}
