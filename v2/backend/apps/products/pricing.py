"""Cost price (tan narx) calculation — feature #24.

per-unit cost = sum(recipe.amount_per_meshok * ingredient.avg_cost_uzs) / product.meshok_size
"""
from decimal import Decimal

from django.utils import timezone

from .models import Product


def recalc_product_cost(product: Product) -> Decimal:
    """Recompute and persist cost_price_uzs for a single product."""
    total = Decimal("0")
    for item in product.recipe_items.select_related("ingredient").all():
        total += Decimal(item.amount_per_meshok) * Decimal(item.ingredient.avg_cost_uzs)
    meshok = Decimal(product.meshok_size or 0)
    per_unit = (total / meshok) if meshok > 0 else Decimal("0")
    product.cost_price_uzs = per_unit
    product.cost_price_updated_at = timezone.now()
    product.save(update_fields=["cost_price_uzs", "cost_price_updated_at"])
    return per_unit


def recalc_products_using_ingredient(ingredient_id: int) -> int:
    """Recompute cost for every product whose recipe references this ingredient."""
    products = (
        Product.objects
        .filter(recipe_items__ingredient_id=ingredient_id)
        .distinct()
    )
    n = 0
    for p in products:
        recalc_product_cost(p)
        n += 1
    return n
