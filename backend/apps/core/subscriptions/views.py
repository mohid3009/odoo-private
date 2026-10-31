from django.db.models import Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.accounts.permissions import IsStaffOrAdmin
from apps.finance.discounts.serializers import AttachSerializer

from . import services
from .models import QuotationTemplate, Subscription
from .serializers import (
    FromTemplateSerializer, QuotationTemplateSerializer, SubscriptionListSerializer, SubscriptionSerializer,
    TransitionSerializer, quotation_valid_until, template_to_subscription_data,
)


class QuotationTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffOrAdmin]
    serializer_class = QuotationTemplateSerializer
    queryset = QuotationTemplate.objects.select_related("plan").prefetch_related("lines__product").order_by("name")
    filterset_fields = ["plan", "is_active"]
    search_fields = ["name"]
    ordering_fields = ["name", "id"]


class SubscriptionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """Everyone may read (customers only their own rows, via for_user); only staff/admin write."""

    filterset_fields = ["status", "customer", "plan"]
    search_fields = ["number", "customer__email"]
    ordering_fields = ["number", "start_date", "created_at", "next_invoice_date", "id"]

    def get_permissions(self):
        return [IsAuthenticated()] if self.action in ("list", "retrieve") else [IsStaffOrAdmin()]

    def get_serializer_class(self):
        return SubscriptionListSerializer if self.action == "list" else SubscriptionSerializer

    def get_queryset(self):
        qs = (
            Subscription.objects.for_user(self.request.user)
            .select_related("customer", "plan__product", "payment_term")
            .annotate(total_amount=Sum("lines__amount"))
            .order_by("-id")
        )
        if self.action != "list":
            qs = qs.prefetch_related("lines__product", "lines__variant", "lines__taxes", "status_log__by_user")
        return qs

    def _detail(self, pk):
        return Response(SubscriptionSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        s = TransitionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.transition(self.get_object(), s.validated_data["to"], request.user)
        return self._detail(pk)

    @action(detail=True, methods=["post", "delete"])
    def discount(self, request, pk=None):
        """Attach (POST {discount}) or detach (DELETE) the subscription-scope discount; it applies from the next invoice."""
        sub = self.get_object()
        if sub.status == Subscription.Status.CLOSED:
            raise services.TransitionError("guard_failed", "A closed subscription cannot be changed.")
        if request.method == "DELETE":
            sub.discount = None
        else:
            s = AttachSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            sub.discount = s.validated_data["discount"]
        sub.save(update_fields=["discount"])
        return self._detail(pk)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        services.renew(self.get_object(), request.user)
        return self._detail(pk)

    @action(detail=False, methods=["post"], url_path="from-template")
    def from_template(self, request):
        s = FromTemplateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        template = s.validated_data["template"]
        out = SubscriptionSerializer(data=template_to_subscription_data(template, s.validated_data), context=self.get_serializer_context())
        out.is_valid(raise_exception=True)
        # FR-SUB-01: valid-until is pre-set from the template (recomputed when sent as a quotation)
        sub = out.save(template=template, quotation_valid_until=quotation_valid_until(template))
        return Response(self._detail(sub.pk).data, status=status.HTTP_201_CREATED)
