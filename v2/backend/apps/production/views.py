from decimal import Decimal

from django.db import transaction
from django.db.models import F
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
        qs = Production.objects.select_related("product", "nonvoy", "group")
        p = self.request.query_params
        if product := p.get("product"):
            qs = qs.filter(product_id=product)
        if nonvoy := p.get("nonvoy"):
            qs = qs.filter(nonvoy_id=nonvoy)
        if group := p.get("group"):
            qs = qs.filter(group_id=group)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        """
        Create production run:
          1) Save Production with the submitted unit_count (NOT auto-calculated).
          2) If unit_count > 0, bump finished-goods stock.
          3) Deduct recipe ingredients based on meshok_count.
        All steps in one atomic transaction.
        """
        with transaction.atomic():
            prod = serializer.save()
            product = Product.objects.get(pk=prod.product_id)
            meshok = Decimal(str(prod.meshok_count))
            unit_count = Decimal(str(prod.unit_count))

            # (2) bump finished-goods stock by submitted unit_count (may be 0)
            if unit_count > 0:
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

    def perform_update(self, serializer):
        """
        When unit_count is updated, adjust the stock delta.
        """
        with transaction.atomic():
            old_unit_count = Decimal(str(serializer.instance.unit_count))
            prod = serializer.save()
            new_unit_count = Decimal(str(prod.unit_count))
            delta = new_unit_count - old_unit_count
            if delta != 0:
                product = Product.objects.get(pk=prod.product_id)
                stock, _ = BakeryProductStock.objects.get_or_create(product=product)
                BakeryProductStock.objects.filter(pk=stock.pk).update(
                    quantity=F("quantity") + delta
                )

    def perform_destroy(self, instance):
        """
        Reverse the stock bump from perform_create, then delete.
        Ingredient deductions are NOT reversed (physically consumed).
        """
        with transaction.atomic():
            unit_count = Decimal(str(instance.unit_count))
            if unit_count > 0:
                stock = BakeryProductStock.objects.filter(
                    product_id=instance.product_id
                ).first()
                if stock:
                    BakeryProductStock.objects.filter(pk=stock.pk).update(
                        quantity=F("quantity") - unit_count
                    )
            instance.delete()


class BakeryProductStockViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BakeryProductStockSerializer

    def get_queryset(self):
        qs = BakeryProductStock.objects.select_related("product")
        show_archived = self.request.query_params.get("archived")
        if show_archived in ("1", "true"):
            pass  # show all
        else:
            qs = qs.filter(product__is_archived=False)
        return qs

    @action(detail=True, methods=["post"], url_path="adjust")
    def adjust_stock(self, request, pk=None):
        """Manually adjust product stock quantity."""
        from apps.production.models import InventoryRevisionReport

        stock = self.get_object()
        raw = request.data.get("new_quantity")
        note = request.data.get("note", "")
        try:
            from decimal import Decimal, InvalidOperation
            new_qty = Decimal(str(raw))
        except (Exception,):
            return Response({"detail": "new_quantity noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST)
        if new_qty < 0:
            return Response({"detail": "Manfiy bo'lishi mumkin emas"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            locked = BakeryProductStock.objects.select_for_update().get(pk=stock.pk)
            old_qty = locked.quantity
            locked.quantity = new_qty
            locked.save(update_fields=["quantity"])
            InventoryRevisionReport.objects.create(
                item_type=InventoryRevisionReport.ItemType.PRODUCT,
                product=locked.product,
                old_quantity=old_qty,
                new_quantity=new_qty,
                note=note,
                user=request.user if request.user.is_authenticated else None,
            )
        return Response(BakeryProductStockSerializer(locked).data)
