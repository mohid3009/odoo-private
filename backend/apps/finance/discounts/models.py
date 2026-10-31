from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.catalog.models import MONEY, Product


class Discount(models.Model):
    class Type(models.TextChoices):
        FIXED = "fixed"
        PERCENT = "percent"

    class Scope(models.TextChoices):
        PRODUCT = "product"  # applies by itself to lines of the listed products
        SUBSCRIPTION = "subscription"  # applies only when attached to a subscription

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=40, null=True, blank=True, unique=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    value = models.DecimalField(**MONEY)  # percent (0-100) or a fixed amount
    scope = models.CharField(max_length=14, choices=Scope.choices)
    products = models.ManyToManyField(Product, blank=True, related_name="discounts")
    min_purchase_amount = models.DecimalField(**MONEY, null=True, blank=True, validators=[MinValueValidator(0)])
    min_quantity = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    used_count = models.PositiveIntegerField(default=0)  # only ever changed by an atomic UPDATE (services.reserve)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def state(self, today=None):
        today = today or timezone.localdate()
        if not self.is_active:
            return "inactive"
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return "exhausted"
        if self.end_date and today > self.end_date:
            return "expired"
        if self.start_date and today < self.start_date:
            return "scheduled"
        return "active"

    def __str__(self):
        return self.name


class DiscountRedemption(models.Model):
    """One row per (discount, invoice): the rule counts once per invoice even if it reduced several lines."""

    discount = models.ForeignKey(Discount, on_delete=models.PROTECT, related_name="redemptions")
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.PROTECT, related_name="redemptions")
    amount = models.DecimalField(**MONEY)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["discount", "invoice"], name="uniq_redemption")]
        ordering = ["-id"]
