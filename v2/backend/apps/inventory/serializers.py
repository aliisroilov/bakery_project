from rest_framework import serializers

from .models import Ingredient, ProductRecipe, Purchase, Unit
from apps.production.models import InventoryRevisionReport


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "short", "created_at"]
        read_only_fields = ["created_at"]


class IngredientSerializer(serializers.ModelSerializer):
    unit_short = serializers.CharField(source="unit.short", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Ingredient
        fields = [
            "id", "name", "unit", "unit_short",
            "quantity", "low_stock_threshold",
            "avg_cost_uzs",
            "is_low_stock", "is_archived",
            "created_at",
        ]
        read_only_fields = ["avg_cost_uzs", "is_low_stock", "created_at"]


class PurchaseSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    account_name = serializers.CharField(source="account.name", read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id", "ingredient", "ingredient_name",
            "quantity", "currency", "total_price", "unit_price",
            "account", "account_name",
            "occurred_at", "note",
            "created_by", "created_at",
        ]
        read_only_fields = ["unit_price", "created_at"]


class ProductRecipeSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True)
    ingredient_unit = serializers.CharField(source="ingredient.unit.short", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductRecipe
        fields = [
            "id", "product", "product_name",
            "ingredient", "ingredient_name", "ingredient_unit",
            "amount_per_meshok", "created_at",
        ]
        read_only_fields = ["created_at"]


class InventoryRevisionSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name", read_only=True, default="")
    ingredient_unit = serializers.CharField(source="ingredient.unit.short", read_only=True, default="")
    user_name = serializers.CharField(source="user.display_name", read_only=True, default="")
    diff = serializers.SerializerMethodField()

    class Meta:
        model = InventoryRevisionReport
        fields = [
            "id", "item_type", "ingredient", "ingredient_name", "ingredient_unit",
            "old_quantity", "new_quantity", "diff",
            "note", "batch_id", "user", "user_name", "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_diff(self, obj):
        return str(obj.new_quantity - obj.old_quantity)
