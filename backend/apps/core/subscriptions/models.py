from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.accounts.scoping import scoped_manager
from apps.core.catalog.models import MONEY, PaymentTerm, Plan, Product, Tax, Variant


class Counter(models.Model):
    """Named sequence behind SUB-000001; incremented under a row lock (services.next_number)."""

    name = models.CharField(max_length=50, unique=True)
    value = models.PositiveIntegerField(default=0)


class QuotationTemplate(models.Model):
    name = models.CharField(max_length=200)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="templates")
    validity_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class QuotationTemplateLine(models.Model):
    template = models.ForeignKey(QuotationTemplate, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])


class Subscription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft"
        QUOTATION = "quotation"
        CONFIRMED = "confirmed"
        ACTIVE = "active"
        PAUSED = "paused"
        CLOSED = "closed"

    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    template = models.ForeignKey(QuotationTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name="subscriptions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    payment_term = models.ForeignKey(PaymentTerm, on_delete=models.PROTECT, related_name="subscriptions")
    next_invoice_date = models.DateField(null=True, blank=True)  # billing cursor, set on confirm (Phase 4 advances it)
    quotation_valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    # the attached subscription-scope discount rule (Phase 5); product-scope rules apply by themselves
    discount = models.ForeignKey("discounts.Discount", null=True, blank=True, on_delete=models.SET_NULL, related_name="subscriptions")

    objects = scoped_manager("customer")

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["customer"]),
            models.Index(fields=["status", "next_invoice_date"]),
        ]

    def __str__(self):
        return self.number


class SubscriptionLine(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=300, blank=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(**MONEY)
    amount = models.DecimalField(**MONEY)  # quantity * unit_price, pre-tax
    taxes = models.ManyToManyField(Tax, blank=True)

    class Meta:
        ordering = ["id"]


class StatusLog(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="status_log")
    from_status = models.CharField(max_length=10)
    to_status = models.CharField(max_length=10)
    by_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "id"]
