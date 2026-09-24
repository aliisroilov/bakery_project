from rest_framework import serializers

from .models import BakeryProductStock, Production


class ProductionSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    nonvoy_name = serializers.CharField(source="nonvoy.display_name", read_only=True, default="")
    group_name = serializers.CharField(source="group.name", read_only=True, default="")
    individuals_display = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Production
        fields = [
            "id", "product", "product_name",
            "nonvoy", "nonvoy_name",
            "group", "group_name",
            "individuals", "individuals_display",
            "actor_name",
            "meshok_count", "unit_count",
            "occurred_at", "note", "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_individuals_display(self, obj):
        return [
            {"id": u.id, "display_name": u.display_name}
            for u in obj.individuals.all()
        ]

    def get_actor_name(self, obj):
        if obj.nonvoy_id:
            return obj.nonvoy.display_name
        if obj.group_id:
            return obj.group.name
        names = [u.display_name for u in obj.individuals.all()]
        if names:
            return ", ".join(names)
        return "—"

    def _submitted(self, data, field):
        """What the row will end up with after this create/update: the request's
        value when the key was sent (an explicit null means "clear it"), else what
        the row already has. A plain `data.get(x) or instance.x` reads a cleared
        field as still-set, which would reject every switch between the
        nonvoy / guruh / nonvoylar modes on an existing record."""
        if field in data:
            return data[field]
        if self.instance is None:
            return None
        value = getattr(self.instance, field, None)
        # M2M descriptors aren't values — resolve to the current selection.
        return list(value.all()) if hasattr(value, "all") else value

    def validate(self, data):
        nonvoy = self._submitted(data, "nonvoy")
        group = self._submitted(data, "group")
        individuals = self._submitted(data, "individuals")

        # A run belongs to EITHER one baker OR one group OR one ad-hoc set of
        # bakers — never a combination, otherwise somebody would be credited
        # individually AND as a member of the batch (double pay).
        chosen = [bool(nonvoy), bool(group), bool(individuals)]
        if not any(chosen) and not self.instance:
            raise serializers.ValidationError(
                {"nonvoy": "Nonvoy, guruh yoki nonvoylar tanlanishi kerak."}
            )
        if sum(chosen) > 1:
            raise serializers.ValidationError(
                {"group": "Faqat bittasini tanlang: nonvoy, guruh yoki nonvoylar."}
            )
        return data


class BakeryProductStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    is_archived = serializers.BooleanField(source="product.is_archived", read_only=True)

    class Meta:
        model = BakeryProductStock
        fields = ["id", "product", "product_name", "quantity", "pinned", "is_archived", "updated_at"]
        read_only_fields = ["updated_at"]
