from rest_framework import serializers

from .models import BakeryProductStock, Production


class ProductionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    nonvoy_name = serializers.CharField(source="nonvoy.display_name", read_only=True, default="")
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Production
        fields = [
            "id", "product", "product_name",
            "nonvoy", "nonvoy_name",
            "group", "group_name",
            "actor_name",
            "meshok_count", "unit_count",
            "occurred_at", "note", "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_actor_name(self, obj):
        if obj.nonvoy_id:
            return obj.nonvoy.display_name
        if obj.group_id:
            return obj.group.name
        return "—"

    def validate(self, data):
        nonvoy = data.get("nonvoy") or getattr(self.instance, "nonvoy", None)
        group = data.get("group") or getattr(self.instance, "group", None)
        if not nonvoy and not group and not self.instance:
            raise serializers.ValidationError(
                {"nonvoy": "Nonvoy yoki guruh tanlanishi kerak."}
            )
        # A run belongs to EITHER one baker OR one group — never both, otherwise
        # the baker would be credited individually AND as a group member (double pay).
        if nonvoy and group:
            raise serializers.ValidationError(
                {"group": "Faqat bittasini tanlang: nonvoy yoki guruh."}
            )
        return data


class BakeryProductStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    is_archived = serializers.BooleanField(source="product.is_archived", read_only=True)

    class Meta:
        model = BakeryProductStock
        fields = ["id", "product", "product_name", "quantity", "pinned", "is_archived", "updated_at"]
        read_only_fields = ["updated_at"]
