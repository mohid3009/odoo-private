from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import status, viewsets
from rest_framework.response import Response

from apps.core.accounts.permissions import ReadOnlyOrAdmin
from integrations.odoo import sync

from .models import PaymentTerm, Plan, Product, Tax
from .serializers import PaymentTermSerializer, PlanSerializer, ProductSerializer, TaxSerializer


class CatalogViewSet(viewsets.ModelViewSet):
    """Read: staff+admin. Write: admin. In-use rows answer 409 instead of 500 on delete."""

    permission_classes = [ReadOnlyOrAdmin]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        try:
            obj.delete()
        except ProtectedError:
            return Response(
                {"detail": f"'{obj}' is in use and cannot be deleted. Deactivate it instead."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MirroredViewSet(CatalogViewSet):
    """Saves are mirrored to Odoo after commit; the mirror never affects the response (rule 7)."""

    mirror = None  # callable(pk)

    def _mirror(self, serializer):
        pk = serializer.instance.pk
        transaction.on_commit(lambda: self.mirror(pk))

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._mirror(serializer)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._mirror(serializer)


class TaxViewSet(MirroredViewSet):
    queryset = Tax.objects.order_by("name")
    serializer_class = TaxSerializer
    filterset_fields = ["is_active"]
    mirror = staticmethod(sync.sync_tax)


class ProductViewSet(MirroredViewSet):
    queryset = Product.objects.prefetch_related("variants", "taxes").order_by("name")
    serializer_class = ProductSerializer
    filterset_fields = ["type", "is_active"]
    mirror = staticmethod(sync.sync_product)


class PaymentTermViewSet(CatalogViewSet):
    queryset = PaymentTerm.objects.order_by("days", "name")
    serializer_class = PaymentTermSerializer


class PlanViewSet(CatalogViewSet):
    queryset = Plan.objects.select_related("product").order_by("name")
    serializer_class = PlanSerializer
    filterset_fields = ["billing_period", "is_active", "product"]
