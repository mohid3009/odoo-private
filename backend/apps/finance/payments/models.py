from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.accounts.scoping import scoped_manager
from apps.core.billing.models import Invoice
from apps.core.catalog.models import MONEY


class Payment(models.Model):
    """One row per payment *attempt*. Only `completed` rows count toward Invoice.amount_paid; failed attempts and
    reversed payments stay as history. Rows are never edited or deleted (the API has no such endpoints)."""

    class Method(models.TextChoices):
        CASH = "cash"
        BANK_TRANSFER = "bank_transfer"
        UPI = "upi"
        CARD = "card"
        CHEQUE = "cheque"
        OTHER = "other"

    class Status(models.TextChoices):
        COMPLETED = "completed"
        FAILED = "failed"
        REVERSED = "reversed"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    method = models.CharField(max_length=14, choices=Method.choices)
    payment_date = models.DateField()
    note = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.COMPLETED)
    attempt_number = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    retry_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="retries")
    failure_reason = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reversal_reason = models.TextField(blank=True)
    odoo_payment_id = models.PositiveIntegerField(null=True, blank=True)
    odoo_sync_status = models.CharField(max_length=10, default="skipped")  # Odoo mirroring is optional and not implemented

    objects = scoped_manager("invoice__customer")

    class Meta:
        ordering = ["-id"]
        constraints = [
            # a failed attempt can be retried at most once, even under concurrent requests
            models.UniqueConstraint(fields=["retry_of"], condition=Q(retry_of__isnull=False), name="uniq_payment_retry_of"),
        ]
        indexes = [models.Index(fields=["invoice", "status"]), models.Index(fields=["payment_date"])]

    def __str__(self):
        return f"{self.invoice_id}#{self.attempt_number} {self.status} {self.amount}"


class PaymentEvent(models.Model):
    """Append-only audit trail for the payment lifecycle of an invoice."""

    class Kind(models.TextChoices):
        RECORDED = "recorded"
        FAILED = "failed"
        RETRIED = "retried"
        REVERSED = "reversed"
        ATTENTION_FLAGGED = "attention_flagged"
        ATTENTION_RESET = "attention_reset"

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payment_events")
    payment = models.ForeignKey(Payment, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    by_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ["at", "id"]
        indexes = [models.Index(fields=["invoice", "at"])]
