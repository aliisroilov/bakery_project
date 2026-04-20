from django.db.models import Count, F, Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Region, Shop, ShopProductPrice
from .serializers import (
    RegionSerializer,
    ShopDetailSerializer,
    ShopListSerializer,
    ShopProductPriceSerializer,
)


class RegionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = RegionSerializer

    def get_queryset(self):
        return Region.objects.annotate(shop_count=Count("shops")).order_by("name")


class ShopViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "owner_name", "phone"]
    ordering_fields = ["name", "loan_balance_uzs", "loan_balance_usd", "created_at"]

    def get_queryset(self):
        qs = Shop.objects.select_related("region", "assigned_driver")
        region = self.request.query_params.get("region")
        driver = self.request.query_params.get("assigned_driver")
        archived = self.request.query_params.get("archived")
        over_limit = self.request.query_params.get("over_limit")
        if region:
            qs = qs.filter(region_id=region)
        if driver:
            qs = qs.filter(assigned_driver_id=driver)
        if archived in ("1", "true"):
            qs = qs.filter(is_archived=True)
        elif archived in ("0", "false"):
            qs = qs.filter(is_archived=False)
        if over_limit in ("1", "true"):
            qs = qs.filter(
                Q(loan_limit_uzs__gt=0, loan_balance_uzs__gt=F("loan_limit_uzs"))
                | Q(loan_limit_usd__gt=0, loan_balance_usd__gt=F("loan_limit_usd"))
            )
        return qs

    def get_serializer_class(self):
        if self.action in ("retrieve",):
            return ShopDetailSerializer
        return ShopListSerializer

    @action(detail=True, methods=["get", "post"])
    def prices(self, request, pk=None):
        """GET → list per-shop prices. POST → upsert a price for (product, currency)."""
        shop = self.get_object()
        if request.method == "GET":
            prices = shop.product_prices.select_related("product").all()
            return Response(ShopProductPriceSerializer(prices, many=True).data)

        data = dict(request.data)
        data["shop"] = shop.id
        existing = ShopProductPrice.objects.filter(
            shop=shop,
            product_id=data.get("product"),
            currency=data.get("currency", "UZS"),
        ).first()
        if existing:
            ser = ShopProductPriceSerializer(existing, data=data, partial=True)
        else:
            ser = ShopProductPriceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="prices/(?P<price_id>[^/.]+)")
    def delete_price(self, request, pk=None, price_id=None):
        shop = self.get_object()
        ShopProductPrice.objects.filter(shop=shop, id=price_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
