from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import F
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.finance.models import KassaAccount, KassaTransaction, KassaTransactionType
from apps.products.pricing import recalc_products_using_ingredient

from .models import Ingredient, ProductRecipe, Purchase, Unit
from .serializers import (
    IngredientSerializer,
    ProductRecipeSerializer,
    PurchaseSerializer,
    UnitSerializer,
)


class UnitViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UnitSerializer
    queryset = Unit.objects.all()


class IngredientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = IngredientSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "quantity"]

    def get_queryset(self):
        qs = Ingredient.objects.select_related("unit")
        archived = self.request.query_params.get("archived")
        low = self.request.query_params.get("low_stock")
        if archived in ("1", "true"):
            qs = qs.filter(is_archived=True)
        elif archived in ("0", "false"):
            qs = qs.filter(is_archived=False)
        if low in ("1", "true"):
            qs = qs.filter(quantity__lte=F("low_stock_threshold"))
        return qs

    @action(detail=True, methods=["post"], url_path="adjust")
    def adjust_stock(self, request, pk=None):
        """Manual stock adjustment — sets new absolute quantity. Logs an
        InventoryRevisionReport row so the change is auditable (old/new/user/note).
        """
        from apps.production.models import InventoryRevisionReport

        ing = self.get_object()
        raw = request.data.get("new_quantity")
        note = request.data.get("note", "")
        try:
            new_qty = Decimal(str(raw))
        except (InvalidOperation, TypeError):
            return Response(
                {"detail": "new_quantity noto'g'ri"}, status=status.HTTP_400_BAD_REQUEST
            )
        if new_qty < 0:
            return Response(
                {"detail": "new_quantity manfiy bo'lishi mumkin emas"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            locked = Ingredient.objects.select_for_update().get(pk=ing.pk)
            old_qty = locked.quantity
            locked.quantity = new_qty
            locked.save(update_fields=["quantity"])
            InventoryRevisionReport.objects.create(
                item_type=InventoryRevisionReport.ItemType.INGREDIENT,
                ingredient=locked,
                old_quantity=old_qty,
                new_quantity=new_qty,
                note=note,
                user=request.user if request.user.is_authenticated else None,
            )
        return Response(IngredientSerializer(locked).data)


class PurchaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = PurchaseSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["occurred_at", "total_price"]

    def get_queryset(self):
        qs = Purchase.objects.select_related("ingredient", "account", "created_by")
        p = self.request.query_params
        if ing := p.get("ingredient"):
            qs = qs.filter(ingredient_id=ing)
        if currency := p.get("currency"):
            qs = qs.filter(currency=currency)
        if date_from := p.get("date_from"):
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to := p.get("date_to"):
            qs = qs.filter(occurred_at__date__lte=date_to)
        return qs

    def perform_create(self, serializer):
        with transaction.atomic():
            qty = Decimal(str(serializer.validated_data["quantity"]))
            total = Decimal(str(serializer.validated_data["total_price"]))
            unit_price = (total / qty) if qty else Decimal("0")
            purchase = serializer.save(
                unit_price=unit_price,
                created_by=self.request.user,
            )
            # Increment ingredient stock + update rolling avg cost.
            ing = Ingredient.objects.select_for_update().get(pk=purchase.ingredient_id)
            old_qty = ing.quantity
            new_qty = old_qty + purchase.quantity
            if purchase.currency == "UZS" and new_qty > 0:
                # Weighted average for UZS only (USD purchases left untouched for now).
                ing.avg_cost_uzs = (
                    (ing.avg_cost_uzs * old_qty) + (purchase.unit_price * purchase.quantity)
                ) / new_qty
            ing.quantity = new_qty
            ing.save(update_fields=["quantity", "avg_cost_uzs"])

            # Deduct from kassa + log.
            account = KassaAccount.objects.select_for_update().get(pk=purchase.account_id)
            if purchase.currency == "UZS":
                account.balance_uzs = F("balance_uzs") - purchase.total_price
            else:
                account.balance_usd = F("balance_usd") - purchase.total_price
            account.save(update_fields=["balance_uzs", "balance_usd"])

            KassaTransaction.objects.create(
                account=purchase.account,
                kind=KassaTransactionType.INVENTORY_PURCHASE,
                currency=purchase.currency,
                amount=-purchase.total_price,
                reference_model="inventory.Purchase",
                reference_id=purchase.id,
                note=f"Xomashyo · {purchase.ingredient.name}",
                occurred_at=purchase.occurred_at,
                created_by=self.request.user,
            )

            # Feature #24: avg_cost_uzs changed → recompute cost for every product using this ingredient.
            if purchase.currency == "UZS":
                recalc_products_using_ingredient(purchase.ingredient_id)


class ProductRecipeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductRecipeSerializer

    def get_queryset(self):
        qs = ProductRecipe.objects.select_related("product", "ingredient", "ingredient__unit")
        if product := self.request.query_params.get("product"):
            qs = qs.filter(product_id=product)
        return qs

    def perform_create(self, serializer):
        from apps.products.pricing import recalc_product_cost
        item = serializer.save()
        recalc_product_cost(item.product)

    def perform_update(self, serializer):
        from apps.products.pricing import recalc_product_cost
        item = serializer.save()
        recalc_product_cost(item.product)

    def perform_destroy(self, instance):
        from apps.products.pricing import recalc_product_cost
        product = instance.product
        instance.delete()
        recalc_product_cost(product)
