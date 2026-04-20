from rest_framework import serializers

from .models import BakeryProductStock, Production


class ProductionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    nonvoy_name = serializers.CharField(source="nonvoy.display_name", read_only=True)

    class Meta:
        model = Production
        fields = [
            "id", "product", "product_name",
            "nonvoy", "nonvoy_name",
            "meshok_count", "unit_count",
            "occurred_at", "note", "created_at",
        ]
        read_only_fields = ["unit_count", "created_at"]


class BakeryProductStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = BakeryProductStock
        fields = ["id", "product", "product_name", "quantity", "pinned", "updated_at"]
        read_only_fields = ["updated_at"]
