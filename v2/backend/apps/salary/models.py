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


class Weekday(models.IntegerChoices):
    """Python weekday() convention: Monday=0 … Sunday=6."""
    MONDAY = 0, "Dushanba"
    TUESDAY = 1, "Seshanba"
    WEDNESDAY = 2, "Chorshanba"
    THURSDAY = 3, "Payshanba"
    FRIDAY = 4, "Juma"
    SATURDAY = 5, "Shanba"
    SUNDAY = 6, "Yakshanba"


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
    # Salary accrues only from this date forward. Production and time-based pay
    # before this date are NOT counted (used for a period close / fresh start so
    # historical production doesn't resurface as unpaid salary). Null = count all.
    reset_date = models.DateField(null=True, blank=True)
    # For Haftalik (per_week) workers: which weekday begins a pay-week. When set,
    # weekly pay accrues one rate per completed week aligned to this day instead
    # of the day-fraction default. Null = fractional (days ÷ 7).
    week_start_day = models.IntegerField(
        null=True, blank=True, choices=Weekday.choices,
        help_text="Haftalik ish haqi uchun hafta boshlanadigan kun.",
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
    # UZS per 1 USD at payout time. Only meaningful when currency == USD: nonvoy
    # wages fold into Tan narxi in the UZS P&L, so a dollar payout is restated at
    # this rate. 0 = row recorded before the field existed → DEFAULT_USD_RATE.
    exchange_rate = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=0,
        help_text="1 USD = ? UZS. Faqat USD to'lov uchun.",
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
    # When True, the payment is kept as a historical record but no longer counts
    # toward the running salary balance (earned/paid/remaining). Used to "close"
    # a period and reset everyone's outstanding balance to zero without deleting
    # any payment data.
    settled = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["user", "-occurred_at"]),
            models.Index(fields=["kind", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.display_name} · {self.get_kind_display()} · {self.amount} {self.currency}"
