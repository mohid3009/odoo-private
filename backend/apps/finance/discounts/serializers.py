from rest_framework import serializers

from apps.core.catalog.models import Product

from .models import Discount, DiscountRedemption


class DiscountSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.all(), required=False)
    code = serializers.CharField(max_length=40, required=False, allow_null=True, allow_blank=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = Discount
        fields = [
            "id", "name", "code", "type", "value", "scope", "products", "min_purchase_amount", "min_quantity",
            "start_date", "end_date", "usage_limit", "is_active", "used_count", "state", "created_by", "created_at",
        ]
        read_only_fields = ["used_count", "created_by", "created_at"]

    def get_state(self, d):
        return d.state()

    def validate_code(self, value):
        value = (value or "").strip()
        if value and Discount.objects.filter(code__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("A discount with this code already exists.")
        return value or None  # blank means "no code" (the column is unique, so it must be NULL, not "")

    def validate(self, attrs):
        inst, errors = self.instance, {}
        get = lambda k, default=None: attrs.get(k, getattr(inst, k, default) if inst else default)
        kind, value, scope = get("type"), get("value"), get("scope")
        if value is not None and kind == Discount.Type.PERCENT and not (0 < value <= 100):
            errors["value"] = "A percentage must be above 0 and at most 100."
        elif value is not None and kind == Discount.Type.FIXED and value <= 0:
            errors["value"] = "A fixed amount must be above 0."
        start, end = get("start_date"), get("end_date")
        if start and end and end < start:
            errors["end_date"] = "End date must be on or after the start date."
        products = attrs["products"] if "products" in attrs else (list(inst.products.all()) if inst else [])
        if scope == Discount.Scope.PRODUCT and not products:
            errors["products"] = "Choose at least one product for a product discount."
        if scope == Discount.Scope.SUBSCRIPTION and products:
            errors["products"] = "A subscription discount applies to the whole subscription; leave products empty."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated):
        products = validated.pop("products", [])
        discount = Discount.objects.create(created_by=self.context["request"].user, **validated)
        discount.products.set(products)
        return discount

    def update(self, instance, validated):
        products = validated.pop("products", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        if products is not None:
            instance.products.set(products)
        return instance


class RedemptionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", default=None, read_only=True)
    subscription_number = serializers.CharField(source="invoice.subscription.number", read_only=True)
    customer_email = serializers.CharField(source="invoice.customer.email", read_only=True)

    class Meta:
        model = DiscountRedemption
        fields = ["id", "invoice", "invoice_number", "subscription_number", "customer_email", "amount", "created_at"]


class AttachSerializer(serializers.Serializer):
    discount = serializers.PrimaryKeyRelatedField(queryset=Discount.objects.all())

    def validate_discount(self, d):
        if d.scope != Discount.Scope.SUBSCRIPTION:
            raise serializers.ValidationError("Only a subscription-scope discount can be attached; product discounts apply by themselves.")
        if not d.is_active:
            raise serializers.ValidationError("This discount is inactive.")
        return d
