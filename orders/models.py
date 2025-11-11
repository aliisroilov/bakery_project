from django.db import models
from shops.models import Shop
from products.models import Product
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from dashboard.models import Payment
from reports.models import BakeryBalance


def quantize_money(value):
    """Round money values to 2 decimal places using half-up rounding."""
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class Order(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Kutilmoqda"),
        ("Partially Delivered", "Qisman yetkazilgan"),
        ("Delivered", "Yetkazilgan"),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    order_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Pending")

    # 💰 New field: how much was received from this order
    received_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        verbose_name="Olingan summa"
    )

    def __str__(self):
        return f"Order #{self.id} - {self.shop.name}"

    def total_amount(self):
        """Sum of all ordered items with proper Decimal precision."""
        total = Decimal('0.00')
        for item in self.items.all():
            total += quantize_money(item.total_price)
        return total

    def update_status(self):
        items = self.items.all()
        if all(item.delivered_quantity == 0 for item in items):
            self.status = "Pending"
        elif all(item.delivered_quantity >= item.quantity for item in items):
            self.status = "Delivered"
        else:
            self.status = "Partially Delivered"
        self.save(update_fields=["status"])

    def save(self, *args, **kwargs):
        """
        Keep save() simple: do not perform side-effects here.
        Financial side-effects (Payment/BakeryBalance/shop.loan_balance)
        are handled centrally elsewhere (process_order_payment).
        """
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    # Price locked when order is created (per unit)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivered_quantity = models.PositiveIntegerField(default=0)
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def total_price(self):
        """Total price for this line item with proper Decimal precision."""
        if self.unit_price is None or self.quantity is None:
            return Decimal('0.00')
        return quantize_money(Decimal(str(self.unit_price)) * Decimal(str(self.quantity)))

