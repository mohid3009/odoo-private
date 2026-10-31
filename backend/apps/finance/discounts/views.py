from rest_framework.decorators import action

from apps.core.catalog.views import CatalogViewSet  # same rules: staff+admin read, admin write, 409 when in use

from .models import Discount, DiscountRedemption
from .serializers import DiscountSerializer, RedemptionSerializer


class DiscountViewSet(CatalogViewSet):
    queryset = Discount.objects.prefetch_related("products").order_by("-id")
    serializer_class = DiscountSerializer
    filterset_fields = ["scope", "type", "is_active"]
    search_fields = ["name", "code"]
    ordering_fields = ["name", "id", "end_date", "used_count"]

    @action(detail=True, methods=["get"])
    def redemptions(self, request, pk=None):
        rows = (
            DiscountRedemption.objects.filter(discount=self.get_object())
            .select_related("invoice__subscription", "invoice__customer").order_by("-id")
        )
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(RedemptionSerializer(page, many=True).data)
