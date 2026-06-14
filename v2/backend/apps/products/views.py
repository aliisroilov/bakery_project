from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product
from .pricing import recalc_product_cost
from .serializers import ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "default_price_uzs", "created_at"]

    def get_queryset(self):
        qs = Product.objects.select_related("stock")
        archived = self.request.query_params.get("archived")
        if archived in ("1", "true"):
            qs = qs.filter(is_archived=True)
        elif archived in ("0", "false"):
            qs = qs.filter(is_archived=False)
        return qs

    def perform_destroy(self, instance):
        instance.archive()

    @action(detail=True, methods=["post"])
    def unarchive(self, request, pk=None):
        """Restore an archived product."""
        product = self.get_object()
        product.unarchive()
        return Response(ProductSerializer(product).data)

    @action(detail=True, methods=["post"], url_path="recalc-cost")
    def recalc_cost(self, request, pk=None):
        """Feature #24 — recompute cost_price_uzs from the current recipe."""
        product = self.get_object()
        recalc_product_cost(product)
        product.refresh_from_db()
        return Response(ProductSerializer(product).data)

    @action(detail=False, methods=["post"], url_path="recalc-costs")
    def recalc_all_costs(self, request):
        """Recompute cost for every active product — useful after a price shift."""
        updated = 0
        for p in Product.objects.filter(is_archived=False):
            recalc_product_cost(p)
            updated += 1
        return Response({"updated": updated})
