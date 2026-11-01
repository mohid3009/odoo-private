import django_filters
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.accounts.permissions import IsAdmin, IsCustomer, IsStaffOrAdmin
from apps.core.billing.models import Invoice

from . import services
from .models import Payment
from .serializers import (
    PaymentDetailSerializer, PaymentInputSerializer, PaymentSerializer, ReasonSerializer, payment_serializer_for,
)


class PaymentFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="invoice__customer_id")
    payment_date_after = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    payment_date_before = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    needs_attention = django_filters.BooleanFilter(field_name="invoice__payment_needs_attention")

    class Meta:
        model = Payment
        fields = ["invoice", "status", "method"]


def payments_queryset(user):
    return (
        Payment.objects.for_user(user)
        .select_related("invoice__customer", "recorded_by", "reversed_by")
        .prefetch_related("retries")
        .order_by("-id")
    )


def result(payment, inv, request, http_status=status.HTTP_201_CREATED):
    data = PaymentSerializer(payments_queryset(request.user).get(pk=payment.pk), context={"request": request}).data
    return Response({**data, "invoice_state": services.invoice_state(inv)}, status=http_status)


def invoice_payments(request, inv, view):
    """GET (any role, scoped) / POST (staff, admin) for /invoices/{id}/payments/; called by the invoice viewset."""
    if request.method == "POST":
        s = PaymentInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        payment, locked = services.record_payment(inv, request.user, s.validated_data)
        return result(payment, locked, request)
    rows = payments_queryset(request.user).filter(invoice=inv)
    page = view.paginate_queryset(rows)
    return view.get_paginated_response(payment_serializer_for(request.user)(page, many=True, context={"request": request}).data)


ONLINE_METHODS = (Payment.Method.CARD, Payment.Method.UPI, Payment.Method.BANK_TRANSFER)


class CustomerPayView(APIView):
    """POST /invoices/{id}/pay/ {method}: a customer pays the whole balance of their own invoice (demo gateway).
    404 for someone else's invoice (rule 8) and while DEMO_PAYMENTS_ENABLED is off; 409 if it is not payable."""

    permission_classes = [IsCustomer]

    def post(self, request, pk):
        if not settings.DEMO_PAYMENTS_ENABLED:
            return Response({"detail": "Online payment is not enabled on this server."}, status=status.HTTP_404_NOT_FOUND)
        inv = get_object_or_404(Invoice.objects.for_user(request.user).exclude(status=Invoice.Status.DRAFT), pk=pk)
        method = request.data.get("method")
        if method not in ONLINE_METHODS:
            return Response({"method": f"Choose one of: {', '.join(ONLINE_METHODS)}."}, status=status.HTTP_400_BAD_REQUEST)
        payment, locked = services.pay_online(inv, request.user, method)
        return Response(
            {"payment": {"id": payment.pk, "amount": str(payment.amount), "method": payment.method, "payment_date": payment.payment_date.isoformat()},
             "invoice_state": services.invoice_state(locked)},
            status=status.HTTP_201_CREATED,
        )


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Staff/admin: all payments. Customers: only those on their own invoices (and fewer fields). No edit, no delete."""

    filterset_class = PaymentFilter
    search_fields = ["invoice__number", "invoice__customer__email", "note"]
    ordering_fields = ["payment_date", "amount", "id", "attempt_number"]

    def get_permissions(self):
        if self.action == "reverse":
            return [IsAdmin()]
        return [IsStaffOrAdmin()] if self.action == "retry" else [IsAuthenticated()]

    def get_queryset(self):
        qs = payments_queryset(self.request.user)
        return qs.prefetch_related("events__by_user") if self.action == "retrieve" else qs

    def get_serializer_class(self):
        if getattr(self.request.user, "role", None) == "customer":
            return payment_serializer_for(self.request.user)
        return PaymentDetailSerializer if self.action == "retrieve" else PaymentSerializer

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        self.get_object()  # 404 for ids the caller cannot see
        s = PaymentInputSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        payment, inv = services.retry_payment(int(pk), request.user, s.validated_data)
        return result(payment, inv, request)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        self.get_object()
        s = ReasonSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        payment, inv = services.reverse_payment(int(pk), request.user, s.validated_data["reason"])
        return result(payment, inv, request, status.HTTP_200_OK)
