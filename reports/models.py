from django.db import models
from django.utils import timezone
from decimal import Decimal

class BakeryBalance(models.Model):
    """
    Tracks the bakery's current cash balance.
    Only one record is used (id=1).
    """
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.amount} so‘m"

    @classmethod
    def get_instance(cls):
        """Return the singleton BakeryBalance object."""
        obj, _ = cls.objects.get_or_create(id=1, defaults={"amount": Decimal("0.00")})
        return obj

    @classmethod
    def reset(cls):
        obj = cls.get_instance()
        obj.amount = 0
        obj.save()
        return obj.amount


    

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Purchase(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    item_name = models.CharField(max_length=255, verbose_name="Nomi")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Narxi (so‘mda)")
    purchase_date = models.DateField(default=timezone.now, verbose_name="Sana")
    notes = models.TextField(blank=True, null=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchase_date"]
        verbose_name = "Xarid"
        verbose_name_plural = "Xaridlar"

    def __str__(self):
        return f"{self.item_name} ({self.category.name if self.category else 'No category'})"
