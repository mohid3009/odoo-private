from django.db import transaction
from rest_framework import serializers

from .models import PaymentTerm, Plan, Product, Tax, Variant

MIRROR_RO = ["odoo_sync_status", "odoo_error"]


class TaxSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tax
        fields = ["id", "name", "rate", "is_active", "odoo_tax_id", *MIRROR_RO]
        read_only_fields = ["odoo_tax_id", *MIRROR_RO]


class PaymentTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTerm
        fields = ["id", "name", "days", "is_default"]


class VariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    effective_unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Variant
        fields = ["id", "attribute", "value", "extra_price", "effective_unit_price"]


class ProductSerializer(serializers.ModelSerializer):
    variants = VariantSerializer(many=True, required=False)
    taxes = serializers.PrimaryKeyRelatedField(many=True, queryset=Tax.objects.all(), required=False)

    class Meta:
        model = Product
        fields = [
            "id", "name", "type", "sales_price", "cost_price", "notes", "is_active", "taxes", "variants",
            "odoo_product_id", *MIRROR_RO,
        ]
        read_only_fields = ["odoo_product_id", *MIRROR_RO]

    def validate_variants(self, items):
        seen = set()
        for v in items:
            key = (v["attribute"].strip().lower(), v["value"].strip().lower())
            if key in seen:
                raise serializers.ValidationError(f"Duplicate variant: {v['attribute']} = {v['value']}.")
            seen.add(key)
        return items

    def _sync_variants(self, product, items):
        keep = []
        for v in items:
            vid = v.pop("id", None)
            if vid and product.variants.filter(pk=vid).exists():
                product.variants.filter(pk=vid).update(**v)
                keep.append(vid)
            else:
                keep.append(Variant.objects.create(product=product, **v).pk)
        product.variants.exclude(pk__in=keep).delete()

    @transaction.atomic
    def create(self, validated):
        variants = validated.pop("variants", [])
        taxes = validated.pop("taxes", [])
        product = Product.objects.create(**validated)
        product.taxes.set(taxes)
        self._sync_variants(product, variants)
        return product

    @transaction.atomic
    def update(self, instance, validated):
        variants = validated.pop("variants", None)
        taxes = validated.pop("taxes", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        instance.save()
        if taxes is not None:
            instance.taxes.set(taxes)
        if variants is not None:
            self._sync_variants(instance, variants)
        return instance


class PlanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Plan
        fields = [
            "id", "name", "product", "product_name", "price", "billing_period", "min_quantity",
            "available_from", "available_to", "auto_close", "allow_early_close", "allow_pause",
            "allow_renew", "is_active",
        ]

    def validate(self, attrs):
        inst = self.instance
        start = attrs.get("available_from", inst.available_from if inst else None)
        end = attrs.get("available_to", inst.available_to if inst else None)
        if start and end and end < start:
            raise serializers.ValidationError({"available_to": "Available-to date must be on or after available-from."})
        return attrs
