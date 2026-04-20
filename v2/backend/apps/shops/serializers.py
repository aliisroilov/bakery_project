from rest_framework import serializers

from .models import Region, Shop, ShopProductPrice


class RegionSerializer(serializers.ModelSerializer):
    shop_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Region
        fields = ["id", "name", "note", "is_archived", "shop_count", "created_at"]
        read_only_fields = ["shop_count", "created_at"]


class ShopProductPriceSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ShopProductPrice
        fields = [
            "id", "shop", "product", "product_name",
            "currency", "price", "note", "created_at",
        ]
        read_only_fields = ["created_at"]


class ShopListSerializer(serializers.ModelSerializer):
    region_name = serializers.CharField(source="region.name", read_only=True)
    assigned_driver_name = serializers.CharField(
        source="assigned_driver.display_name", read_only=True
    )
    limit_exceeded_uzs = serializers.SerializerMethodField()
    limit_exceeded_usd = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            "id", "name", "owner_name", "phone", "address",
            "region", "region_name",
            "assigned_driver", "assigned_driver_name",
            "loan_balance_uzs", "loan_balance_usd",
            "loan_limit_uzs", "loan_limit_usd",
            "limit_exceeded_uzs", "limit_exceeded_usd",
            "is_archived", "created_at",
        ]
        read_only_fields = ["created_at", "loan_balance_uzs", "loan_balance_usd"]

    def get_limit_exceeded_uzs(self, obj: Shop) -> bool:
        return obj.loan_limit_exceeded()["uzs"]

    def get_limit_exceeded_usd(self, obj: Shop) -> bool:
        return obj.loan_limit_exceeded()["usd"]


class ShopDetailSerializer(ShopListSerializer):
    product_prices = ShopProductPriceSerializer(many=True, read_only=True)

    class Meta(ShopListSerializer.Meta):
        fields = ShopListSerializer.Meta.fields + ["product_prices"]
