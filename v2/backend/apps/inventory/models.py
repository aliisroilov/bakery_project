"""Inventory: units, ingredients, purchases, recipes."""
from django.conf import settings
from django.db import models

from apps.core.constants import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    QTY_DECIMAL_PLACES,
    QTY_MAX_DIGITS,
    Currency,
)
from apps.core.models import ArchivableModel, TimestampedModel


class Unit(TimestampedModel):
    """Measurement unit (kg, litr, dona)."""

    name = models.CharField(max_length=50, unique=True)
    short = models.CharField(max_length=10)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.short or self.name


class Ingredient(TimestampedModel, ArchivableModel):
    """Raw material."""

    name = models.CharField(max_length=120, unique=True)
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="ingredients")
    quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=0
    )
    low_stock_threshold = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES, default=0
    )
    # Rolling average cost per unit (used to compute product cost — feature #24).
    avg_cost_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    class Meta:
        ordering = ["name"]

    @property
    def is_low_stock(self) -> bool:
        return self.quantity <= self.low_stock_threshold

    def __str__(self) -> str:
        return self.name


class Purchase(TimestampedModel):
    """
    Ingredient purchase — unifies v1's two Purchase models (inventory + reports).

    Feature #9: currency is explicit. Feature #23: account tells which kassa paid.
    """

    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="purchases"
    )
    quantity = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    total_price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    unit_price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES,
        help_text="total_price / quantity — cached for cost calculations",
    )
    account = models.ForeignKey(
        "finance.KassaAccount", on_delete=models.PROTECT, related_name="ingredient_purchases"
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingredient_purchases",
    )

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["ingredient", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.ingredient.name} × {self.quantity} @ {self.unit_price} {self.currency}"


class ProductRecipe(TimestampedModel):
    """How much of each ingredient goes into one meshok of a product."""

    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="recipe_items"
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="used_in_recipes"
    )
    amount_per_meshok = models.DecimalField(
        max_digits=QTY_MAX_DIGITS, decimal_places=QTY_DECIMAL_PLACES
    )

    class Meta:
        unique_together = ("product", "ingredient")
        ordering = ["product", "ingredient"]

    def __str__(self) -> str:
        return f"{self.product.name} ← {self.amount_per_meshok} {self.ingredient.unit.short} {self.ingredient.name}"
