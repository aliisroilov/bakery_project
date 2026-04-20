"""
Production app — what gets baked, by whom, consuming what.

Feature #13: dashboard needs today/month production counts → use Production.
Feature #14: per-product production salary → Production tracks nonvoy + product.
Feature #21: per-nonvoy salary history (per-day qop count) → Production aggregation.
"""
from django.conf import settings
from django.db import models

from apps.core.constants import QTY_DECIMAL_PLACES, QTY_MAX_DIGITS
from apps.core.models import TimestampedModel


class Production(TimestampedModel):
    """
    One production run — a nonvoy produced N units of a product on a given date.

    Unlike v1 (which used `meshok` globally), v2 links each run to a specific
    nonvoy staff so we can pay per-nonvoy per-product rates (feature #14).
    """

    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="productions"
    )
    nonvoy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="productions",
        limit_choices_to={"role": "nonvoy"},
    )
    # Quantity in "meshok" (batch). One batch = product.meshok_size units.
    meshok_count = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    # Total units produced (meshok_count × product.meshok_size), cached for queries.
    unit_count = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=0
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["product", "-occurred_at"]),
            models.Index(fields=["nonvoy", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.name} · {self.meshok_count} meshok · {self.nonvoy.display_name}"


class ProductionIngredientUsage(models.Model):
    """Audit trail — which ingredients were consumed for a Production."""

    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="ingredient_usages"
    )
    ingredient = models.ForeignKey(
        "inventory.Ingredient",
        on_delete=models.PROTECT,
        related_name="usages",
    )
    quantity_used = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]


class BakeryProductStock(TimestampedModel):
    """Finished goods inventory — quantity ready to deliver."""

    product = models.OneToOneField(
        "products.Product", on_delete=models.CASCADE, related_name="stock"
    )
    quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=0
    )
    pinned = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.product.name}: {self.quantity}"


class InventoryRevisionReport(TimestampedModel):
    """Manual stock adjustment audit log (ingredient OR product)."""

    class ItemType(models.TextChoices):
        INGREDIENT = "ingredient", "Xomashyo"
        PRODUCT = "product", "Tayyor mahsulot"

    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    ingredient = models.ForeignKey(
        "inventory.Ingredient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions",
    )
    old_quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    new_quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    note = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revisions_made",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        target = self.ingredient or self.product
        return f"{target} : {self.old_quantity} → {self.new_quantity}"
