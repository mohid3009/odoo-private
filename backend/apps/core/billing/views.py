import django_filters
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.accounts.permissions import IsAdmin, IsStaffOrAdmin

from . import engine, services
from .models import BillingRun, Invoice
from .serializers import (
    BillingRunDetailSerializer, BillingRunSerializer, InvoiceDetailSerializer, InvoiceListSerializer,
    InvoicePrintSerializer, RunRequestSerializer, SendSerializer,
)


class InvoiceFilter(django_filters.FilterSet):
    overdue = django_filters.BooleanFilter(method="filter_overdue")
    needs_attention = django_filters.BooleanFilter(field_name="payment_needs_attention")  # staff: failed-payment limit reached

    class Meta:
        model = Invoice
        fields = ["status", "customer", "subscription"]

    def filter_overdue(self, qs, name, value):  # D-013
        if not value:
            return qs
        return qs.filter(status=Invoice.Status.CONFIRMED, amount_due__gt=0, due_date__lt=timezone.localdate())


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """Everyone reads (customers: their own, never drafts). Staff/admin act. Invoices are created only by the engine."""

    filterset_class = InvoiceFilter
    search_fields = ["number", "subscription__number", "customer__email"]
    ordering_fields = ["invoice_date", "due_date", "total", "number", "id"]

    def get_permissions(self):
        if self.action == "reset_payment_attempts":
            return [IsAdmin()]
        if self.action in ("confirm", "cancel", "send") or (self.action == "payments" and self.request.method == "POST"):
            return [IsStaffOrAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return InvoiceListSerializer if self.action == "list" else InvoiceDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.for_user(user).select_related("customer__profile", "subscription").order_by("-id")
        if getattr(user, "role", None) == "customer":
            qs = qs.exclude(status=Invoice.Status.DRAFT)  # a draft is not issued yet
        if self.action != "list":
            qs = qs.prefetch_related("lines", "payments")
        return qs

    def _detail(self, invoice):
        return Response(InvoiceDetailSerializer(self.get_queryset().get(pk=invoice.pk), context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._detail(services.confirm(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._detail(services.cancel(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        s = SendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._detail(services.send(self.get_object(), request.user, s.validated_data.get("channels")))

    @action(detail=True, methods=["get", "post"], url_path="payments")
    def payments(self, request, pk=None):
        from apps.finance.payments.views import invoice_payments  # lazy: the payments app builds on billing

        return invoice_payments(request, self.get_object(), self)

    @action(detail=True, methods=["post"], url_path="reset-payment-attempts")
    def reset_payment_attempts(self, request, pk=None):
        from apps.finance.payments import services as payment_services

        reason = request.data.get("reason", "") if hasattr(request.data, "get") else ""
        return self._detail(payment_services.reset_attempts(self.get_object(), request.user, reason))

    @action(detail=True, methods=["get"], url_path="print")
    def print_data(self, request, pk=None):
        return Response(InvoicePrintSerializer(self.get_object(), context=self.get_serializer_context()).data)


class BillingRunViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsStaffOrAdmin]
    queryset = BillingRun.objects.select_related("triggered_by").order_by("-id")

    def get_serializer_class(self):
        return BillingRunSerializer if self.action == "list" else BillingRunDetailSerializer


class RunBillingView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def post(self, request):
        s = RunRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        run = engine.run_billing(s.validated_data.get("as_of"), request.user)
        d = BillingRunSerializer(run).data
        return Response({
            "run_id": run.pk, "as_of_date": d["as_of_date"], "created": run.created_count, "skipped": run.skipped_count,
            "errors": run.error_count, "started_at": d["started_at"], "finished_at": d["finished_at"],
        }, status=status.HTTP_200_OK)
