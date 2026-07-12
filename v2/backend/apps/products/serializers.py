from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    stock_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "description",
            "default_price_uzs", "default_price_usd",
            "production_salary_per_unit_uzs",
            "communal_cost_per_unit_uzs",
            "cost_price_uzs", "cost_price_updated_at",
            "meshok_size",
            "sort_order",
            "stock_quantity",
            "is_archived", "created_at",
        ]
        read_only_fields = [
            "cost_price_uzs", "cost_price_updated_at",
            "stock_quantity", "created_at",
        ]

    def get_stock_quantity(self, obj: Product):
        stock = getattr(obj, "stock", None)
        return str(stock.quantity) if stock else "0"
