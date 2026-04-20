from decimal import Decimal

from django.db import transaction
from django.db.models import F
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.inventory.models import Ingredient
from apps.products.models import Product

from .models import (
    BakeryProductStock,
    Production,
    ProductionIngredientUsage,
)
from .serializers import BakeryProductStockSerializer, ProductionSerializer


class ProductionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "meshok_count"]

    def get_queryset(self):
        qs = Production.objects.select_related("product", "nonvoy")
        p = self.request.query_params
        if product := p.get("product"):
            qs = qs.filter(product_id=product)
        if nonvoy := p.get("nonvoy"):
            qs = qs.filter(nonvoy_id=nonvoy)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        """
        Ported from v1 `Production.apply_consumption()`:
          1) save Production,
          2) bump finished-goods stock by meshok_count × product.meshok_size,
          3) deduct each recipe ingredient (amount_per_meshok × meshok_count) from inventory,
             creating an audit row in ProductionIngredientUsage.

        All three steps happen inside one atomic transaction so a failure anywhere
        rolls back — we never end up with half-deducted ingredients.
        """
        with transaction.atomic():
            prod = serializer.save()
            product = Product.objects.get(pk=prod.product_id)
            meshok = Decimal(str(prod.meshok_count))

            # (2) bump finished-goods stock
            unit_count = meshok * product.meshok_size
            prod.unit_count = unit_count
            prod.save(update_fields=["unit_count"])
            stock, _ = BakeryProductStock.objects.get_or_create(product=product)
            BakeryProductStock.objects.filter(pk=stock.pk).update(
                quantity=F("quantity") + unit_count
            )

            # (3) deduct recipe ingredients + audit usage rows
            recipe_items = list(
                product.recipe_items.select_related("ingredient").all()
            )
            usages = []
            for item in recipe_items:
                needed = Decimal(str(item.amount_per_meshok)) * meshok
                ing = Ingredient.objects.select_for_update().get(
                    pk=item.ingredient_id
                )
                ing.quantity = ing.quantity - needed
                ing.save(update_fields=["quantity"])
                usages.append(
                    ProductionIngredientUsage(
                        production=prod,
                        ingredient=ing,
                        quantity_used=needed,
                    )
                )
            if usages:
                ProductionIngredientUsage.objects.bulk_create(usages)


class BakeryProductStockViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BakeryProductStockSerializer
    queryset = BakeryProductStock.objects.select_related("product")
