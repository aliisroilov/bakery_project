from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from reports.models import BakeryBalance

class SalaryRate(models.Model):
    RATE_TYPE_CHOICES = [
        ("per_qop", "Per Qop (meshok)"),
        ("per_week", "Per Week"),
        ("fixed", "Fixed amount"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salary_rate')
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    rate_type = models.CharField(max_length=20, choices=RATE_TYPE_CHOICES, default="fixed")
    notes = models.TextField(blank=True, null=True)

    # 🆕 Add this new field
    initial_balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Oldindan hisoblangan maosh (sistemadan oldingi qarzdorlik)"
    )

    # 🆕 Add cutoff date for production counting
    production_start_date = models.DateField(
        blank=True,
        null=True,
        help_text="Only count production from this date forward. Leave blank to count all production."
    )

    def __str__(self):
        return f"{self.user.username} — {self.rate} ({self.rate_type})"


class SalaryPayment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='salary_payments')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='created_salary_payments')
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.amount} on {self.created_at.date()}"

    @classmethod
    def create_and_process(cls, user, amount, created_by=None, note=None):
        """
        Create a salary payment and deduct from bakery balance atomically.
        """
        with transaction.atomic():
            payment = cls.objects.create(user=user, amount=amount, created_by=created_by, note=note)

            balance = BakeryBalance.get_instance()
            balance.amount -= Decimal(amount)
            balance.save(update_fields=['amount', 'updated_at'])

            payment.processed = True
            payment.processed_at = timezone.now()
            payment.save(update_fields=['processed', 'processed_at'])

            return payment

    @staticmethod
    def get_balance_due(user):
        """
        Returns remaining salary owed to user. Can be negative if overpaid.
        """
        from salary.utils import calculate_auto_salary
        total_earned = calculate_auto_salary(user)
        total_paid = user.salary_payments.aggregate(total=models.Sum("amount"))['total'] or Decimal("0.00")
        return total_earned - total_paid
