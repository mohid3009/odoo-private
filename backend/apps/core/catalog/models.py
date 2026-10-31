from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

MONEY = {"max_digits": 12, "decimal_places": 2}
ZERO = Decimal("0.00")


class OdooMirror(models.Model):
    """Mixin for records mirrored to Odoo; status values: skipped | pending | synced | error."""

    odoo_sync_status = models.CharField(max_length=10, default="skipped")
    odoo_error = models.TextField(blank=True)

    class Meta:
        abstract = True


class Tax(OdooMirror):
    name = models.CharField(max_length=100, unique=True)
    rate = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)
    odoo_tax_id = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class PaymentTerm(models.Model):
    name = models.CharField(max_length=100, unique=True)
    days = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not PaymentTerm.objects.exclude(pk=self.pk).filter(is_default=True).exists():
            self.is_default = True  # there is always a default (invoice due dates need one)
        super().save(*args, **kwargs)
        if self.is_default:
            PaymentTerm.objects.exclude(pk=self.pk).update(is_default=False)  # pk is set now

    def __str__(self):
        return self.name


class Product(OdooMirror):
    class Type(models.TextChoices):
        SERVICE = "service"
        SOFTWARE = "software"
        ADDON = "addon"
        PHYSICAL = "physical"

    name = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.SERVICE)
    sales_price = models.DecimalField(**MONEY, validators=[MinValueValidator(ZERO)])
    cost_price = models.DecimalField(**MONEY, default=ZERO, validators=[MinValueValidator(ZERO)])
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    taxes = models.ManyToManyField(Tax, blank=True, related_name="products")
    odoo_product_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self):
        return self.name


class Variant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attribute = models.CharField(max_length=100)
    value = models.CharField(max_length=100)
    extra_price = models.DecimalField(**MONEY, default=ZERO)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "attribute", "value"], name="uniq_variant")]

    @property
    def effective_unit_price(self):
        """Add-on price (D-001): product sales price + variant extra."""
        return self.product.sales_price + self.extra_price

    def __str__(self):
        return f"{self.product.name} / {self.attribute}={self.value}"


class Plan(models.Model):
    class Period(models.TextChoices):
        DAILY = "daily"
        WEEKLY = "weekly"
        MONTHLY = "monthly"
        YEARLY = "yearly"

    name = models.CharField(max_length=200)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="plans")  # primary product
    price = models.DecimalField(**MONEY, validators=[MinValueValidator(ZERO)])  # per unit, per period (D-001)
    billing_period = models.CharField(max_length=10, choices=Period.choices, default=Period.MONTHLY)
    min_quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    available_from = models.DateField(null=True, blank=True)
    available_to = models.DateField(null=True, blank=True)
    auto_close = models.BooleanField(default=False)
    allow_early_close = models.BooleanField(default=False)
    allow_pause = models.BooleanField(default=False)
    allow_renew = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["is_active"])]

    def is_available_on(self, day):
        return (self.available_from is None or self.available_from <= day) and (
            self.available_to is None or day <= self.available_to
        )

    def unit_price(self, variant=None):
        """First-line price of a subscription from this plan (D-001)."""
        return self.price + (variant.extra_price if variant else ZERO)

    def __str__(self):
        return self.name
