from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.core.accounts.models import Role
from apps.core.catalog.models import PaymentTerm, Plan, Tax

from . import services
from .models import QuotationTemplate, QuotationTemplateLine, StatusLog, Subscription, SubscriptionLine

User = get_user_model()


def check_variant(attrs):
    variant, product = attrs.get("variant"), attrs.get("product")
    if variant and product and variant.product_id != product.pk:
        raise serializers.ValidationError({"variant": f"{variant.attribute}={variant.value} does not belong to {product.name}."})
    return attrs


# --- templates ---------------------------------------------------------------------------

class TemplateLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = QuotationTemplateLine
        fields = ["id", "product", "product_name", "variant", "quantity"]

    def validate(self, attrs):
        return check_variant(attrs)


class QuotationTemplateSerializer(serializers.ModelSerializer):
    lines = TemplateLineSerializer(many=True, required=False)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = QuotationTemplate
        fields = ["id", "name", "plan", "plan_name", "validity_days", "is_active", "lines"]

    @staticmethod
    def _set_lines(template, lines):
        template.lines.all().delete()
        QuotationTemplateLine.objects.bulk_create(QuotationTemplateLine(template=template, **l) for l in lines)

    @transaction.atomic
    def create(self, validated):
        lines = validated.pop("lines", [])
        template = QuotationTemplate.objects.create(**validated)
        self._set_lines(template, lines)
        return template

    @transaction.atomic
    def update(self, instance, validated):
        lines = validated.pop("lines", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        if lines is not None:
            self._set_lines(instance, lines)
        return instance


# --- subscriptions -----------------------------------------------------------------------

class LineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    variant_label = serializers.SerializerMethodField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)
    taxes = serializers.PrimaryKeyRelatedField(many=True, queryset=Tax.objects.all(), required=False)

    class Meta:
        model = SubscriptionLine
        fields = ["id", "product", "product_name", "variant", "variant_label", "description", "quantity", "unit_price", "amount", "taxes"]
        read_only_fields = ["amount"]
        extra_kwargs = {"description": {"required": False}}

    def get_variant_label(self, line):
        return f"{line.variant.attribute}={line.variant.value}" if line.variant else ""

    def validate(self, attrs):
        return check_variant(attrs)


class StatusLogSerializer(serializers.ModelSerializer):
    by_user_email = serializers.CharField(source="by_user.email", default="system", read_only=True)

    class Meta:
        model = StatusLog
        fields = ["from_status", "to_status", "by_user_email", "at"]


class SubscriptionListSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    payment_term_name = serializers.CharField(source="payment_term.name", read_only=True)
    lines_total = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id", "number", "customer", "customer_email", "plan", "plan_name", "status", "start_date", "expiry_date",
            "payment_term", "payment_term_name", "next_invoice_date", "lines_total", "created_at",
        ]
        read_only_fields = ["number", "status", "next_invoice_date", "created_at"]  # server-owned

    def get_lines_total(self, sub):
        total = getattr(sub, "total_amount", None)  # annotated by the view: no per-row query
        return str(services.q2(total if total is not None else 0))


class SubscriptionSerializer(SubscriptionListSerializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.CUSTOMER),
        error_messages={"does_not_exist": "Customer not found (the user must have the customer role)."},
    )
    plan = serializers.PrimaryKeyRelatedField(queryset=Plan.objects.filter(is_active=True).select_related("product"))
    payment_term = serializers.PrimaryKeyRelatedField(queryset=PaymentTerm.objects.all(), required=False)
    lines = LineSerializer(many=True, required=False)
    status_log = StatusLogSerializer(many=True, read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta(SubscriptionListSerializer.Meta):
        fields = SubscriptionListSerializer.Meta.fields + [
            "template", "quotation_valid_until", "notes", "created_by", "lines", "status_log", "actions",
        ]
        read_only_fields = SubscriptionListSerializer.Meta.read_only_fields + ["template", "quotation_valid_until", "created_by"]

    def get_lines_total(self, sub):
        return str(services.q2(sum((l.amount for l in sub.lines.all()), services.ZERO)))

    def get_actions(self, sub):
        return services.actions_for(sub, self.context["request"].user)

    def validate(self, attrs):
        inst = self.instance
        plan = attrs.get("plan", inst.plan if inst else None)
        start = attrs.get("start_date", inst.start_date if inst else None)
        end = attrs.get("expiry_date", inst.expiry_date if inst else None)
        errors = {}
        if start and end and end < start:
            errors["expiry_date"] = "Expiry date must be on or after the start date."
        if plan and start and not plan.is_available_on(start):
            errors["start_date"] = f"Plan '{plan.name}' is not available on {start}."
        if plan and "lines" in attrs:
            problem = services.primary_qty_problem(plan, [(l["product"].pk, l["quantity"]) for l in attrs["lines"]])
            if problem:
                errors["lines"] = problem
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    @staticmethod
    def _set_lines(sub, lines):
        sub.lines.all().delete()
        for l in lines:
            product, variant = l["product"], l.get("variant")
            unit = l.get("unit_price")
            unit = services.q2(unit) if unit is not None else services.line_price(sub.plan, product, variant)
            line = SubscriptionLine.objects.create(
                subscription=sub, product=product, variant=variant, quantity=l["quantity"], unit_price=unit,
                amount=services.q2(unit * l["quantity"]),
                description=l.get("description") or (f"{product.name} ({variant.attribute}={variant.value})" if variant else product.name),
            )
            line.taxes.set(l["taxes"] if "taxes" in l else product.taxes.all())

    @transaction.atomic
    def create(self, validated):
        lines = validated.pop("lines", None)
        validated.setdefault("payment_term", PaymentTerm.objects.filter(is_default=True).first() or PaymentTerm.objects.first())
        if validated["payment_term"] is None:
            raise serializers.ValidationError({"payment_term": "Create a payment term first."})
        sub = Subscription.objects.create(number=services.next_number(), created_by=self.context["request"].user, **validated)
        if lines is None:  # D-001: a subscription from a plan starts with its primary product
            lines = [{"product": sub.plan.product, "quantity": sub.plan.min_quantity}]
        self._set_lines(sub, lines)
        return sub

    @transaction.atomic
    def update(self, instance, validated):
        if instance.status != Subscription.Status.DRAFT:
            raise services.TransitionError("not_editable", "Only draft subscriptions can be edited; move it back to draft first.")
        lines = validated.pop("lines", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        if lines is not None:
            self._set_lines(instance, lines)
        return instance


class TransitionSerializer(serializers.Serializer):
    to = serializers.ChoiceField(choices=Subscription.Status.choices)


class FromTemplateSerializer(serializers.Serializer):
    template = serializers.PrimaryKeyRelatedField(queryset=QuotationTemplate.objects.select_related("plan__product").prefetch_related("lines"))
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=Role.CUSTOMER))
    start_date = serializers.DateField()
    expiry_date = serializers.DateField(required=False, allow_null=True)
    payment_term = serializers.PrimaryKeyRelatedField(queryset=PaymentTerm.objects.all(), required=False)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_template(self, template):
        if not template.is_active:
            raise serializers.ValidationError("This template is inactive.")
        return template


def template_to_subscription_data(template, cleaned):
    """Input for SubscriptionSerializer built from a template (prices are computed server-side)."""
    data = {k: v for k, v in cleaned.items() if k != "template"}
    data["plan"] = template.plan_id
    data["customer"] = cleaned["customer"].pk
    if "payment_term" in cleaned:
        data["payment_term"] = cleaned["payment_term"].pk
    data["lines"] = [{"product": l.product_id, "variant": l.variant_id, "quantity": l.quantity} for l in template.lines.all()]
    return data


def quotation_valid_until(template):
    return timezone.localdate() + timedelta(days=template.validity_days)
