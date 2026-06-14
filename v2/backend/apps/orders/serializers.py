from rest_framework import serializers

from .models import Order, OrderItem, OrderPriority, OrderStatus


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    total_price = serializers.SerializerMethodField()
    delivered_price = serializers.SerializerMethodField()
    net_delivered = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id", "order", "product", "product_name",
            "unit_price", "quantity",
            "delivered_quantity", "returned_quantity",
            "net_delivered", "total_price", "delivered_price",
        ]
        read_only_fields = ["order"]

    def get_total_price(self, obj):
        return str(obj.total_price)

    def get_delivered_price(self, obj):
        return str(obj.delivered_price)

    def get_net_delivered(self, obj):
        return obj.net_delivered


class OrderListSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_amount = serializers.SerializerMethodField()
    delivered_amount = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "shop", "shop_name",
            "order_date", "delivery_time",
            "priority", "priority_display",
            "status", "status_display",
            "currency",
            "created_at",
            "total_amount", "delivered_amount",
            "item_count",
        ]
        read_only_fields = ["created_at"]

    def get_total_amount(self, obj):
        return str(obj.total_amount())

    def get_delivered_amount(self, obj):
        return str(obj.delivered_amount())

    def get_item_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.display_name", read_only=True, default=""
    )
    note = serializers.CharField(required=False, allow_blank=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + [
            "items", "note", "created_by", "created_by_name",
        ]


class OrderItemCreateSerializer(serializers.Serializer):
    product = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=16, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    # Optional — how much of this line was delivered on creation (partial/delivered
    # orders entered inline). Omitted/None means "use the status default".
    delivered_quantity = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class OrderCreateSerializer(serializers.Serializer):
    shop = serializers.IntegerField()
    order_date = serializers.DateField()
    delivery_time = serializers.DateTimeField(required=False, allow_null=True)
    priority = serializers.ChoiceField(
        choices=OrderPriority.choices, default=OrderPriority.NORMAL
    )
    status = serializers.ChoiceField(
        choices=OrderStatus.choices, default=OrderStatus.PENDING, required=False
    )
    currency = serializers.ChoiceField(choices=[("UZS", "UZS"), ("USD", "USD")], default="UZS")
    note = serializers.CharField(required=False, allow_blank=True)
    items = OrderItemCreateSerializer(many=True)


class ConfirmDeliveryItemSerializer(serializers.Serializer):
    item_id = serializers.IntegerField()
    delivered_quantity = serializers.IntegerField(min_value=0)
    returned_quantity = serializers.IntegerField(min_value=0, default=0)
