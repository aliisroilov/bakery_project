"""Shops + Regions + per-shop pricing + loan limits."""
from django.conf import settings
from django.db import models

from apps.core.constants import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
)
from apps.core.models import ArchivableModel, TimestampedModel


class Region(TimestampedModel, ArchivableModel):
    """Geographical region (hudud)."""

    name = models.CharField(max_length=120, unique=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Shop(TimestampedModel, ArchivableModel):
    """Customer shop (do'kon)."""

    name = models.CharField(max_length=200, db_index=True)
    owner_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)

    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="shops"
    )

    # Feature #19: assigned driver
    assigned_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_shops",
        limit_choices_to={"role": "driver"},
    )

    # Feature #9: currency split — loan balance per currency.
    # Single source of truth = SUM(delivered_value_<cur>) - SUM(payments_<cur>)
    loan_balance_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )
    loan_balance_usd = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    # Feature #5: loan limit per currency. 0 means no limit enforced.
    loan_limit_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )
    loan_limit_usd = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["region", "is_archived"]),
            models.Index(fields=["assigned_driver"]),
        ]

    def __str__(self) -> str:
        return self.name

    def loan_limit_exceeded(self) -> dict[str, bool]:
        """Return which currency limits are exceeded (only when a limit is set)."""
        return {
            "uzs": bool(self.loan_limit_uzs) and self.loan_balance_uzs > self.loan_limit_uzs,
            "usd": bool(self.loan_limit_usd) and self.loan_balance_usd > self.loan_limit_usd,
        }


class ShopProductPrice(TimestampedModel):
    """Custom per-shop product price (feature #2).

    When creating an order for a shop, the UI recommends these prices.
    If no override exists, the product's default price is used.
    """

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="product_prices"
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="shop_prices"
    )
    # Currency matches the shop's primary currency at order time; kept per-row for flexibility.
    currency = models.CharField(max_length=3, default="UZS")
    price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("shop", "product", "currency")
        ordering = ["shop", "product"]

    def __str__(self) -> str:
        return f"{self.shop.name} · {self.product.name}: {self.price} {self.currency}"
