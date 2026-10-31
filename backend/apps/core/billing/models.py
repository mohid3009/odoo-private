from django.conf import settings
from django.db import models

from apps.core.accounts.scoping import scoped_manager
from apps.core.catalog.models import MONEY, Product, Tax
from apps.core.subscriptions.models import Subscription


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        CONFIRMED = "confirmed"
        PAID = "paid"
        CANCELLED = "cancelled"

    number = models.CharField(max_length=20, null=True, blank=True, unique=True)  # assigned at confirm
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="invoices")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="invoices")  # denormalised for scoping
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    invoice_date = models.DateField()  # the billing-run date
    due_date = models.DateField()  # invoice_date + payment term days (D-013)
    period_start = models.DateField()
    period_end = models.DateField()
    subtotal = models.DecimalField(**MONEY)
    discount_total = models.DecimalField(**MONEY)  # positive amount saved
    tax_total = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    amount_paid = models.DecimalField(**MONEY, default=0)  # kept in step with payments by apps.finance.payments
    amount_due = models.DecimalField(**MONEY)
    # Phase 6 (D-041): both maintained only by apps.finance.payments.services, under the invoice row lock
    failed_attempts = models.PositiveSmallIntegerField(default=0)  # failed payment attempts since the last completed payment / admin reset
    payment_needs_attention = models.BooleanField(default=False)  # failed_attempts reached PAYMENT_MAX_ATTEMPTS
    odoo_move_id = models.PositiveIntegerField(null=True, blank=True)
    odoo_sync_status = models.CharField(max_length=10, default="skipped")
    odoo_error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = scoped_manager("customer")

    class Meta:
        constraints = [
            # The last safety net for "nothing billed twice": even a bug or a race cannot insert a second row.
            models.UniqueConstraint(fields=["subscription", "period_start"], name="uniq_invoice_period"),
        ]
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["invoice_date"]),
            models.Index(fields=["payment_needs_attention"]),
        ]

    def __str__(self):
        return self.number or f"draft #{self.pk}"


class InvoiceLine(models.Model):
    class Kind(models.TextChoices):
        PRODUCT = "product"
        DISCOUNT = "discount"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PRODUCT)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=300)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(**MONEY)  # negative for discount lines
    tax_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # sum of the line's tax rates, frozen
    line_subtotal = models.DecimalField(**MONEY)
    line_tax = models.DecimalField(**MONEY)
    line_total = models.DecimalField(**MONEY)
    taxes = models.ManyToManyField(Tax, blank=True)  # which Tax rows applied (for the Odoo mapping)

    class Meta:
        ordering = ["id"]


class BillingRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    as_of_date = models.DateField()
    created_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
