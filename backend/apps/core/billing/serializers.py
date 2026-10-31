from django.utils import timezone
from rest_framework import serializers

from . import services
from .models import BillingRun, Invoice, InvoiceLine


class InvoiceLineSerializer(serializers.ModelSerializer):
    tax_rate = serializers.DecimalField(source="tax_rate_snapshot", max_digits=5, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ["id", "kind", "description", "quantity", "unit_price", "tax_rate", "line_subtotal", "line_tax", "line_total"]


class InvoiceListSerializer(serializers.ModelSerializer):
    subscription_number = serializers.CharField(source="subscription.number", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    days_overdue = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id", "number", "subscription", "subscription_number", "customer", "customer_email", "status", "invoice_date",
            "due_date", "period_start", "period_end", "subtotal", "discount_total", "tax_total", "total", "amount_paid",
            "amount_due", "days_overdue", "is_overdue", "odoo_sync_status", "failed_attempts", "payment_needs_attention",
        ]

    def to_representation(self, inv):
        data = super().to_representation(inv)
        request = self.context.get("request")
        if getattr(getattr(request, "user", None), "role", None) == "customer":
            for internal in ("failed_attempts", "payment_needs_attention", "max_payment_attempts"):
                data.pop(internal, None)  # collections signals: not for the customer
        return data

    def get_days_overdue(self, inv):  # D-013: confirmed, balance > 0, due date passed
        if inv.status == Invoice.Status.CONFIRMED and inv.amount_due > 0 and inv.due_date < timezone.localdate():
            return (timezone.localdate() - inv.due_date).days
        return 0

    def get_is_overdue(self, inv):
        return self.get_days_overdue(inv) > 0


class InvoiceDetailSerializer(InvoiceListSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    actions = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()
    max_payment_attempts = serializers.SerializerMethodField()

    class Meta(InvoiceListSerializer.Meta):
        fields = InvoiceListSerializer.Meta.fields + [
            "lines", "odoo_move_id", "odoo_error", "sent_at", "created_at", "actions", "payments", "max_payment_attempts",
        ]

    def get_max_payment_attempts(self, inv):
        from django.conf import settings

        return settings.PAYMENT_MAX_ATTEMPTS

    def get_actions(self, inv):
        return services.actions_for(inv, self.context["request"].user)

    def get_payments(self, inv):
        from apps.finance.payments.serializers import payment_serializer_for  # lazy: payments depends on billing, not the reverse

        user = self.context["request"].user
        return payment_serializer_for(user)(inv.payments.all(), many=True, context=self.context).data


class InvoicePrintSerializer(InvoiceDetailSerializer):
    seller = serializers.SerializerMethodField()
    customer_details = serializers.SerializerMethodField()

    class Meta(InvoiceDetailSerializer.Meta):
        fields = InvoiceDetailSerializer.Meta.fields + ["seller", "customer_details"]

    def get_seller(self, inv):
        return {"name": "Brightloop Software"}

    def get_customer_details(self, inv):
        c, p = inv.customer, getattr(inv.customer, "profile", None)
        return {"name": c.name, "email": c.email, "company_name": p.company_name if p else "",
                "phone": p.phone if p else "", "address": p.address if p else ""}


class SendSerializer(serializers.Serializer):
    channels = serializers.ListField(child=serializers.ChoiceField(choices=["email", "whatsapp"]), required=False, allow_empty=False)


class RunRequestSerializer(serializers.Serializer):
    as_of = serializers.DateField(required=False)


class BillingRunSerializer(serializers.ModelSerializer):
    triggered_by_email = serializers.CharField(source="triggered_by.email", default="", read_only=True)

    class Meta:
        model = BillingRun
        fields = ["id", "started_at", "finished_at", "as_of_date", "triggered_by_email", "created_count", "skipped_count", "error_count"]


class BillingRunDetailSerializer(BillingRunSerializer):
    class Meta(BillingRunSerializer.Meta):
        fields = BillingRunSerializer.Meta.fields + ["log"]
