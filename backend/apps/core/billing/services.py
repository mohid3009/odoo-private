"""Invoice workflow (docs/STATE_MACHINES.md): draft -> confirmed -> paid, cancel from draft/confirmed.
Views never set `status`; Paid is set by the payments app when the balance reaches zero (Phase 6)."""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.core.subscriptions.services import TransitionError, is_staff, next_sequence
from apps.finance.notifications.services import notify
from integrations.odoo import sync

from .models import Invoice

S = Invoice.Status


def _staff_only(user):
    if not is_staff(user):
        raise PermissionDenied("Only staff or admin can do this.")


def actions_for(invoice, user):
    """Buttons the current user may see; the server re-checks everything when one is used."""
    if not is_staff(user):
        return []
    out = []
    if invoice.status == S.DRAFT:
        out += ["confirm", "cancel"]
    elif invoice.status == S.CONFIRMED:
        out.append("send")
        if invoice.amount_due > 0 and invoice.failed_attempts < settings.PAYMENT_MAX_ATTEMPTS:
            out.append("pay")  # record / retry a payment attempt
        if user.role == "admin" and invoice.payment_needs_attention:
            out.append("reset_attempts")
        if user.role == "admin" and invoice.amount_paid == 0:
            out.append("cancel")
    elif invoice.status == S.PAID:
        out.append("send")
    return out


def invoice_context(invoice):
    return {
        "customer_name": invoice.customer.name or invoice.customer.email,
        "invoice_number": invoice.number or "",
        "subscription_number": invoice.subscription.number,
        "amount": str(invoice.total),
        "due_date": str(invoice.due_date),
        "link": f"{settings.SITE_URL}/portal/invoices/{invoice.pk}",
    }


@transaction.atomic
def confirm(invoice, user):
    _staff_only(user)
    inv = Invoice.objects.select_for_update(of=("self",)).select_related("customer", "subscription").get(pk=invoice.pk)
    if inv.status != S.DRAFT:
        raise TransitionError("illegal_transition", f"Only a draft invoice can be confirmed (this one is {inv.status}).")
    if not inv.lines.filter(kind="product").exists():
        raise TransitionError("guard_failed", "An invoice needs at least one product line.")
    inv.number = next_sequence("invoice", "INV-")
    inv.status = S.PAID if inv.amount_due <= 0 else S.CONFIRMED  # nothing to collect on a zero invoice
    inv.save(update_fields=["number", "status"])
    transaction.on_commit(lambda: sync.post_invoice(inv.pk))  # Odoo down -> 'pending'; never undoes the confirm
    notify("INVOICE_READY", inv.customer, inv, context=invoice_context(inv))  # never raises, never blocks
    return inv


@transaction.atomic
def cancel(invoice, user):
    _staff_only(user)
    inv = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status == S.CONFIRMED:
        if user.role != "admin":
            raise PermissionDenied("Only an admin can cancel a confirmed invoice.")
        if inv.amount_paid != 0:
            raise TransitionError("guard_failed", "This invoice already has payments; it cannot be cancelled.")
    elif inv.status != S.DRAFT:
        raise TransitionError("illegal_transition", f"A {inv.status} invoice cannot be cancelled.")
    inv.status = S.CANCELLED  # the (subscription, period_start) slot stays used: the engine will not re-bill it (D-019)
    inv.save(update_fields=["status"])
    return inv


def send(invoice, user, channels=None):
    """Manual send: a forced notification (it goes out again even if the invoice was already sent)."""
    _staff_only(user)
    inv = Invoice.objects.select_related("customer", "subscription").get(pk=invoice.pk)
    if inv.status not in (S.CONFIRMED, S.PAID):
        raise TransitionError("illegal_transition", "Only a confirmed or paid invoice can be sent.")
    notify("INVOICE_READY", inv.customer, inv, context=invoice_context(inv), force=True, channels=channels)
    Invoice.objects.filter(pk=inv.pk).update(sent_at=timezone.now())
    inv.refresh_from_db()
    return inv
