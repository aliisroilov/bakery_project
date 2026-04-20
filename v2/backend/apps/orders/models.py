"""Orders + OrderItems."""
from django.conf import settings
from django.db import models

from apps.core.constants import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    QTY_DECIMAL_PLACES,
    QTY_MAX_DIGITS,
    Currency,
)
from apps.core.money import quantize_money
from apps.core.models import TimestampedModel


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Kutilmoqda"
    PARTIALLY_DELIVERED = "partial", "Qisman yetkazildi"
    DELIVERED = "delivered", "Yetkazildi"
    CANCELLED = "cancelled", "Bekor qilindi"


class OrderPriority(models.TextChoices):
    """Feature #6 — delivery priority."""

    LOW = "low", "Past"
    NORMAL = "normal", "Oddiy"
    HIGH = "high", "Yuqori"
    URGENT = "urgent", "Shoshilinch"


class Order(TimestampedModel):
    """Delivery order for a shop."""

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="orders"
    )
    order_date = models.DateField(db_index=True)

    # Feature #6: delivery time window.
    delivery_time = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(
        max_length=10, choices=OrderPriority.choices, default=OrderPriority.NORMAL
    )

    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING
    )
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_orders",
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-order_date", "-id"]
        indexes = [
            models.Index(fields=["shop", "-order_date"]),
            models.Index(fields=["status", "-order_date"]),
            models.Index(fields=["priority", "-order_date"]),
        ]

    def total_amount(self):
        """Sum of all items' total_price — expects items prefetched."""
        total = sum(
            (item.total_price for item in self.items.all()),
            start=0,
        )
        return quantize_money(total)

    def delivered_amount(self):
        total = sum(
            (item.delivered_price for item in self.items.all()),
            start=0,
        )
        return quantize_money(total)

    def __str__(self) -> str:
        return f"Order #{self.id} · {self.shop.name} · {self.order_date}"


class OrderItem(models.Model):
    """Line item — product + quantity + locked unit price."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="order_items"
    )

    # Unit price is locked at order creation — usually taken from ShopProductPrice
    # (feature #2) but the value is cached here for historical accuracy.
    unit_price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    quantity = models.PositiveIntegerField()
    delivered_quantity = models.PositiveIntegerField(default=0)
    # Feature #17: vozvrat — units returned by the customer.
    returned_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    @property
    def net_delivered(self) -> int:
        return max(self.delivered_quantity - self.returned_quantity, 0)

    @property
    def total_price(self):
        return quantize_money(self.unit_price * self.quantity)

    @property
    def delivered_price(self):
        return quantize_money(self.unit_price * self.net_delivered)

    def __str__(self) -> str:
        return f"{self.product.name} × {self.quantity}"
