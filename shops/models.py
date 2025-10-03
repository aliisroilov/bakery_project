from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Hudud"
        verbose_name_plural = "Hududlar"

    def __str__(self):
        return self.name


class Shop(models.Model):
    name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="shops")

    # Financial tracking
    loan_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Shop’s outstanding debt (qarzdorlik)"
    )

    class Meta:
        verbose_name = "Do‘kon"
        verbose_name_plural = "Do‘konlar"

    def __str__(self):
        return f"{self.name} ({self.region.name})"
