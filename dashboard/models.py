from django.db import models
from shops.models import Shop
from django.conf import settings


class LoanRepayment(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.shop.name} - {self.amount} so'm ({self.date.date()})"
    

class Payment(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ("collection", "Collection (driver)"),
        ("repayment", "Loan Repayment"),
        ("other", "Other"),
    ]

    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL)
    shop = models.ForeignKey("shops.Shop", null=True, blank=True, on_delete=models.SET_NULL)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default="collection")
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        who = self.shop.name if self.shop else (self.order.shop.name if self.order else "—")
        return f"{self.get_payment_type_display()} {self.amount} — {who} ({self.date.date()})"