"""
Finance app — the money layer.

Replaces v1's BakeryBalance singleton with two named KassaAccounts (Seyf, Rizoxon — feature #23).
All money is tracked per-currency (UZS + USD separately — feature #9).

Models here:
- KassaAccount         — named cash account (Seyf / Rizoxon)
- KassaTransaction     — append-only ledger of every money movement
- Payment              — cash received from a shop ("kirim") — feature #1, #16
- LoanRepayment        — explicit debt repayment (subset of Payment via payment_type)
- ExpenseCategory      — category for general (non-inventory) expenses
- GeneralExpense       — non-inventory purchases (utilities, rent, etc.)
- CashHandover         — driver handing cash to office — feature #25
"""
from django.conf import settings
from django.db import models

from apps.core.constants import (
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
    Currency,
)
from apps.core.models import ArchivableModel, TimestampedModel


# ────────────────── Kassa (cash accounts) ──────────────────
class KassaAccount(TimestampedModel):
    """Named cash account. Seyf and Rizoxon are seeded via data migration."""

    SEYF = "seyf"
    RIZOXON = "rizoxon"

    slug = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    # Current balance per currency (derived from KassaTransaction ledger; cached here for speed).
    balance_uzs = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )
    balance_usd = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class KassaTransactionType(models.TextChoices):
    PAYMENT_IN = "payment_in", "Kirim (to'lov)"
    LOAN_REPAYMENT = "loan_repayment", "Qarz to'lovi"
    INVENTORY_PURCHASE = "inventory_purchase", "Xomashyo xarid"
    GENERAL_EXPENSE = "general_expense", "Umumiy xarajat"
    SALARY = "salary", "Oylik"
    ADVANCE = "advance", "Avans"
    BONUS = "bonus", "Bonus"
    CASH_HANDOVER = "cash_handover", "Pul topshirish"
    ADJUSTMENT = "adjustment", "Qo'lda tuzatish"
    TRANSFER = "transfer", "Kassalar orasida"


class KassaTransaction(TimestampedModel):
    """Append-only ledger of every money movement into/out of a kassa.

    Positive amounts = money in. Negative = money out.
    Each transaction touches exactly ONE currency (per-currency separation).
    """

    account = models.ForeignKey(
        KassaAccount, on_delete=models.PROTECT, related_name="transactions"
    )
    kind = models.CharField(max_length=32, choices=KassaTransactionType.choices)
    currency = models.CharField(max_length=3, choices=Currency.CHOICES)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES,
        help_text="Positive = in, negative = out",
    )

    # Loose references — any record type can link here. We avoid GenericFK because
    # we want typed, queryable links.
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    reference_model = models.CharField(max_length=64, blank=True)

    note = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kassa_transactions",
    )

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["account", "-occurred_at"]),
            models.Index(fields=["kind", "-occurred_at"]),
            models.Index(fields=["reference_model", "reference_id"]),
        ]

    def __str__(self) -> str:
        sign = "+" if self.amount >= 0 else "−"
        return f"[{self.account.slug}] {sign}{abs(self.amount)} {self.currency} · {self.get_kind_display()}"


# ────────────────── Payments (Kirim) ──────────────────
class PaymentType(models.TextChoices):
    COLLECTION = "collection", "Kirim (delivery payment)"
    LOAN_REPAYMENT = "loan_repayment", "Qarz to'lovi"
    OTHER = "other", "Boshqa"


class Payment(TimestampedModel):
    """
    Cash received from a shop.

    Feature #1: user selects the shop AND the specific order (or date) the payment applies to.
    Feature #16: discount (skidka/bonus) recorded separately from the cash amount.
    Feature #9: currency split — each payment is in exactly one currency.
    """

    shop = models.ForeignKey(
        "shops.Shop", on_delete=models.PROTECT, related_name="payments"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    # Feature #1 — optional "for this specific day's orders" shortcut when order isn't chosen.
    order_date = models.DateField(null=True, blank=True, db_index=True)

    payment_type = models.CharField(
        max_length=20, choices=PaymentType.choices, default=PaymentType.COLLECTION
    )
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    # Feature #16: discount applied on top of cash (closes the loan by amount + discount).
    discount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES, default=0
    )

    account = models.ForeignKey(
        KassaAccount,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="Which kassa received this money",
    )

    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collected_payments",
        help_text="Feature #20 — who received the cash (driver/cashier)",
    )

    received_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["shop", "-received_at"]),
            models.Index(fields=["collected_by", "-received_at"]),
            models.Index(fields=["payment_type", "-received_at"]),
        ]

    def closes_loan_by(self):
        """Total amount that reduces shop debt: cash + discount."""
        return self.amount + self.discount

    def __str__(self) -> str:
        return f"{self.shop.name} · {self.amount} {self.currency}"


# ────────────────── Expense categories + general expenses ──────────────────
class ExpenseCategory(TimestampedModel, ArchivableModel):
    """Categorize non-inventory expenses (utilities, rent, transport, ...)."""

    name = models.CharField(max_length=120, unique=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class GeneralExpense(TimestampedModel):
    """Non-inventory expense (utilities, fuel, packaging, etc.)."""

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    title = models.CharField(max_length=200)
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    account = models.ForeignKey(
        KassaAccount, on_delete=models.PROTECT, related_name="general_expenses"
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="general_expenses",
    )

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.title} · {self.amount} {self.currency}"


# ────────────────── Kassa Transfer (account → account) ──────────────────
class KassaTransfer(TimestampedModel):
    """
    Money moved from one KassaAccount to another (e.g. Rizoxon → Seyf).

    Creates two KassaTransaction rows (debit + credit) and adjusts both
    account cached balances atomically.
    """

    from_account = models.ForeignKey(
        KassaAccount,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_account = models.ForeignKey(
        KassaAccount,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kassa_transfers",
    )

    class Meta:
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.from_account.name} → {self.to_account.name}: {self.amount} {self.currency}"


# ────────────────── Cash handover (driver → office) ──────────────────
class CashHandover(TimestampedModel):
    """
    Feature #25: driver hands cash to office/cashier.

    Creates an out-of-driver / in-to-kassa transaction. Links the payments
    that comprised this handover (for audit trail).
    """

    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="handovers_made",
        limit_choices_to={"role": "driver"},
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="handovers_received",
    )
    to_account = models.ForeignKey(
        KassaAccount, on_delete=models.PROTECT, related_name="handovers"
    )
    currency = models.CharField(max_length=3, choices=Currency.CHOICES, default=Currency.UZS)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS, decimal_places=MONEY_DECIMAL_PLACES
    )
    occurred_at = models.DateTimeField(db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["driver", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.driver.display_name} → {self.to_account.name}: {self.amount} {self.currency}"
