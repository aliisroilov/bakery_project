from django.db import models
from shops.models import Shop
from products.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Kutilmoqda"),
        ("Partially Delivered", "Qisman yetkazilgan"),
        ("Delivered", "Yetkazilgan"),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Pending")
    
    def __str__(self):
        return f"Order #{self.id} - {self.shop.name}"

    def update_status(self):
        items = self.items.all()
        if all(item.delivered_quantity == 0 for item in items):
            self.status = "Pending"
        elif all(item.delivered_quantity >= item.ordered_quantity for item in items):
            self.status = "Delivered"
        else:
            self.status = "Partially Delivered"
        self.save()



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
        if self.unit_price is None or self.quantity is None:
            return 0
        return self.unit_price * self.quantity

