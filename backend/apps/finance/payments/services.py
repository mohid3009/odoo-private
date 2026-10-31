"""Payment lifecycle (docs/STATE_MACHINES.md, D-041).

Every function takes the invoice row lock first (always invoice, then payment: one lock order, no deadlocks), so two
requests on the same invoice are serialised: the balance, the attempt counter and the Paid flip can never be raced.
Only `completed` payments count toward the balance. Rows are never edited or deleted; a mistake is a reversal."""
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.billing.models import Invoice
from apps.core.subscriptions.services import TransitionError, is_staff, q2
from apps.finance.notifications.services import notify

from .models import Payment, PaymentEvent

ZERO = Decimal("0.00")
PS, IS, EK = Payment.Status, Invoice.Status, PaymentEvent.Kind


def max_attempts():
    return settings.PAYMENT_MAX_ATTEMPTS


def _lock_invoice(invoice_id):
    # of=("self",): only the invoice row is the lock; the joined customer/subscription rows must stay free for other work
    return Invoice.objects.select_for_update(of=("self",)).select_related("customer", "subscription").get(pk=invoice_id)


def _event(inv, kind, user, payment=None, detail=""):
    PaymentEvent.objects.create(invoice=inv, payment=payment, kind=kind, by_user=user, detail=detail)


def recompute(inv):
    """Balance = total − Σ completed payments, and the Paid/Confirmed flip that follows from it."""
    paid = Payment.objects.filter(invoice=inv, status=PS.COMPLETED).aggregate(s=Sum("amount"))["s"] or ZERO
    inv.amount_paid = q2(paid)
    inv.amount_due = q2(inv.total - paid)
    if inv.status == IS.CONFIRMED and inv.amount_due <= 0:
        inv.status = IS.PAID  # exactly when the completed payments reach the total
    elif inv.status == IS.PAID and inv.amount_due > 0:
        inv.status = IS.CONFIRMED  # a reversal reopened the balance
    inv.save(update_fields=["amount_paid", "amount_due", "status"])


def invoice_state(inv):
    return {"status": inv.status, "amount_paid": str(inv.amount_paid), "amount_due": str(inv.amount_due),
            "failed_attempts": inv.failed_attempts, "payment_needs_attention": inv.payment_needs_attention}


def _require_staff(user):
    if not is_staff(user):
        raise PermissionDenied("Only staff or admin can record payments.")


def _require_admin(user):
    if getattr(user, "role", None) != "admin":
        raise PermissionDenied("Only an admin can do this.")


def _clean_reason(reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "A reason is required."})
    return reason


def _record(inv, user, data, retry_of=None):
    """The shared body of record + retry; `inv` is already locked."""
    if inv.status != IS.CONFIRMED:
        why = {IS.DRAFT: "Confirm the invoice before recording a payment.", IS.PAID: "This invoice is already paid in full.",
               IS.CANCELLED: "This invoice is cancelled."}[inv.status]
        raise TransitionError("illegal_transition", why)
    if inv.failed_attempts >= max_attempts():
        raise TransitionError(
            "max_attempts_reached",
            f"{inv.failed_attempts} payment attempts have failed (the limit is {max_attempts()}). An admin must review and reset the invoice before more attempts.",
        )
    amount = q2(data["amount"])
    if amount > inv.amount_due:
        raise ValidationError({"amount": f"The amount (₹{amount}) is more than the balance due (₹{inv.amount_due}). Overpayments are not accepted."})

    payment = Payment.objects.create(
        invoice=inv, amount=amount, method=data["method"], payment_date=data.get("payment_date") or timezone.localdate(),
        note=data.get("note", ""), status=data.get("status", PS.COMPLETED), attempt_number=inv.failed_attempts + 1,
        retry_of=retry_of, failure_reason=data.get("failure_reason", "") if data.get("status") == PS.FAILED else "", recorded_by=user,
    )
    if retry_of:
        _event(inv, EK.RETRIED, user, payment, f"retry of payment #{retry_of.pk} (attempt {retry_of.attempt_number})")

    if payment.status == PS.FAILED:
        inv.failed_attempts += 1
        _event(inv, EK.FAILED, user, payment, payment.failure_reason)
        if inv.failed_attempts >= max_attempts():
            inv.payment_needs_attention = True
            _event(inv, EK.ATTENTION_FLAGGED, user, payment, f"{inv.failed_attempts} failed attempts; further attempts are blocked")
        inv.save(update_fields=["failed_attempts", "payment_needs_attention"])
    else:
        inv.failed_attempts, inv.payment_needs_attention = 0, False  # a success ends the streak
        inv.save(update_fields=["failed_attempts", "payment_needs_attention"])
        _event(inv, EK.RECORDED, user, payment, "")
        recompute(inv)
        note = "Your invoice is now paid in full." if inv.amount_due <= 0 else f"Remaining balance: ₹{inv.amount_due}."
        notify(
            "PAYMENT_RECEIVED", inv.customer, inv, variant=str(payment.pk),  # one message per payment; never raises
            context={"customer_name": inv.customer.name or inv.customer.email, "invoice_number": inv.number or "",
                     "amount": str(payment.amount), "balance_note": note},
        )
    return payment, inv


@transaction.atomic
def record_payment(invoice, user, data):
    _require_staff(user)
    return _record(_lock_invoice(invoice.pk), user, data)


@transaction.atomic
def retry_payment(payment_id, user, data):
    _require_staff(user)
    inv = _lock_invoice(Payment.objects.values_list("invoice_id", flat=True).get(pk=payment_id))
    failed = Payment.objects.select_for_update().get(pk=payment_id)
    if failed.status != PS.FAILED:
        raise TransitionError("illegal_transition", f"Only a failed attempt can be retried (this one is {failed.status}).")
    if failed.retries.exists():
        raise TransitionError("guard_failed", "This attempt was already retried; retry the newest attempt instead.")
    return _record(inv, user, data, retry_of=failed)


@transaction.atomic
def reverse_payment(payment_id, user, reason):
    """Undo a completed payment: the row is kept as `reversed`, the balance is restored, Paid goes back to Confirmed."""
    _require_admin(user)
    reason = _clean_reason(reason)
    inv = _lock_invoice(Payment.objects.values_list("invoice_id", flat=True).get(pk=payment_id))
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if payment.status != PS.COMPLETED:
        raise TransitionError("illegal_transition", f"Only a completed payment can be reversed (this one is {payment.status}).")
    if inv.status not in (IS.CONFIRMED, IS.PAID):
        raise TransitionError("illegal_transition", f"The invoice is {inv.status}; its payments cannot be reversed.")
    payment.status, payment.reversed_at, payment.reversed_by, payment.reversal_reason = PS.REVERSED, timezone.now(), user, reason
    payment.save(update_fields=["status", "reversed_at", "reversed_by", "reversal_reason"])
    _event(inv, EK.REVERSED, user, payment, reason)
    recompute(inv)
    return payment, inv


@transaction.atomic
def reset_attempts(invoice, user, reason):
    """Admin review after the attempt limit: clears the counter and the flag so payments can be tried again."""
    _require_admin(user)
    reason = _clean_reason(reason)
    inv = _lock_invoice(invoice.pk)
    if inv.status != IS.CONFIRMED or not (inv.payment_needs_attention or inv.failed_attempts):
        raise TransitionError("guard_failed", "Only a confirmed invoice with failed payment attempts can be reset.")
    inv.failed_attempts, inv.payment_needs_attention = 0, False
    inv.save(update_fields=["failed_attempts", "payment_needs_attention"])
    _event(inv, EK.ATTENTION_RESET, user, None, reason)
    return inv
