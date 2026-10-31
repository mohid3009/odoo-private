from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Payment, PaymentEvent


class PaymentInputSerializer(serializers.Serializer):
    """Body of record / retry. `reversed` can never be requested: only a reversal produces it."""

    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=Payment.Method.choices)
    status = serializers.ChoiceField(choices=[Payment.Status.COMPLETED, Payment.Status.FAILED], default=Payment.Status.COMPLETED)
    failure_reason = serializers.CharField(required=False, allow_blank=True, default="")
    payment_date = serializers.DateField(required=False)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_payment_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("The payment date cannot be in the future.")
        return value

    def validate(self, attrs):
        if attrs["status"] == Payment.Status.FAILED and not attrs["failure_reason"].strip():
            raise serializers.ValidationError({"failure_reason": "Say why the attempt failed (e.g. card declined)."})
        return attrs


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=True, required=False, default="")


class EventSerializer(serializers.ModelSerializer):
    by_user_email = serializers.CharField(source="by_user.email", default="system", read_only=True)

    class Meta:
        model = PaymentEvent
        fields = ["kind", "by_user_email", "at", "detail"]


class PaymentSerializer(serializers.ModelSerializer):
    """Staff/admin view of a payment attempt."""

    invoice_number = serializers.CharField(source="invoice.number", default=None, read_only=True)
    customer_email = serializers.CharField(source="invoice.customer.email", read_only=True)
    recorded_by_email = serializers.CharField(source="recorded_by.email", default=None, read_only=True)
    reversed_by_email = serializers.CharField(source="reversed_by.email", default=None, read_only=True)
    retried_by = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "invoice_number", "customer_email", "amount", "method", "payment_date", "note", "status",
            "attempt_number", "retry_of", "retried_by", "failure_reason", "recorded_by_email", "created_at", "reversed_at",
            "reversed_by_email", "reversal_reason", "odoo_sync_status",
        ]

    def get_retried_by(self, p):
        retry = next(iter(p.retries.all()), None)  # prefetched by the views: no query per row
        return retry.pk if retry else None


class PaymentDetailSerializer(PaymentSerializer):
    events = EventSerializer(many=True, read_only=True)

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ["events"]


class CustomerPaymentSerializer(serializers.ModelSerializer):
    """What a customer may see of their own payments: no staff notes, reasons, audit trail or who recorded it."""

    invoice_number = serializers.CharField(source="invoice.number", default=None, read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "invoice", "invoice_number", "amount", "method", "payment_date", "status", "attempt_number", "created_at"]


def payment_serializer_for(user):
    return CustomerPaymentSerializer if getattr(user, "role", None) == "customer" else PaymentSerializer
