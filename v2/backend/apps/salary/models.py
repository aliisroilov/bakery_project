"""Salary rates + payments. Feature #4: separate salary from advance/bonus."""
from django.conf import settings
from django.db import models

from apps.core.constants import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    Currency,
)
from apps.core.models import TimestampedModel


class RateType(models.TextChoices):
    PER_UNIT = "per_unit", "Dona boshi"           # nonvoy: paid per produced unit
    PER_MESHOK = "per_meshok", "Meshok boshi"     # nonvoy: paid per batch
    PER_WEEK = "per_week", "Haftalik"             # driver: paid weekly
    FIXED_MONTHLY = "fixed_monthly", "Oylik qat'iy"
    # Feature #14: per-product rate — handled by Product.production_salary_per_unit_uzs.
    PER_PRODUCT = "per_product", "Mahsulot bo'yicha"


class SalaryRate(TimestampedModel):
    """Per-user salary configuration."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salary_rate",
    )
    rate_type = models.CharField(max_length=20, choices=RateType.choices)
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    # Amount per unit — interpretation depends on rate_type.
    # Ignored when rate_type=PER_PRODUCT (that uses Product.production_salary_per_unit_uzs).
    rate = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )
    initial_balance = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0,
        help_text="Pre-system debt owed to or by employee (positive = we owe them).",
    )
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user.display_name}: {self.rate} {self.currency} ({self.get_rate_type_display()})"


class PaymentKind(models.TextChoices):
    """Feature #4: keep these visually and logically separate."""

    SALARY = "salary", "Oylik"
    ADVANCE = "advance", "Avans (oldindan)"
    BONUS = "bonus", "Bonus / ustama"
    DEDUCTION = "deduction", "Ushlab qolish"


class SalaryPayment(TimestampedModel):
    """A payment to an employee. `kind` keeps salary vs advance vs bonus separate."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="salary_payments",
    )
    kind = models.CharField(max_length=20, choices=PaymentKind.choices, default=PaymentKind.SALARY)
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    account = models.ForeignKey(
        "finance.KassaAccount",
        on_delete=models.PROTECT,
        related_name="salary_payments",
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="salary_payments_created",
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["user", "-occurred_at"]),
            models.Index(fields=["kind", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.display_name} · {self.get_kind_display()} · {self.amount} {self.currency}"
