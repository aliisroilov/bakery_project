from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from reports.models import BakeryBalance
from .models import Purchase
from dashboard.models import LoanRepayment

# ---------------- PURCHASE ----------------
@receiver(post_save, sender=Purchase)
def decrease_balance_on_purchase(sender, instance, created, **kwargs):
    """Subtract purchase amount from BakeryBalance when a purchase is created."""
    if created and instance.price:
        balance = BakeryBalance.get_instance()  # returns model instance
        balance.amount -= Decimal(instance.price)
        balance.save(update_fields=["amount"])

@receiver(post_delete, sender=Purchase)
def restore_balance_on_purchase_delete(sender, instance, **kwargs):
    """Restore balance when a purchase is deleted."""
    if instance.price:
        balance = BakeryBalance.get_instance()
        balance.amount += Decimal(instance.price)
        balance.save(update_fields=["amount"])

# ---------------- LOAN REPAYMENT ----------------
@receiver(post_save, sender=LoanRepayment)
def update_balance_on_loan(sender, instance, created, **kwargs):
    """Add repayment amount to BakeryBalance."""
    if created:
        balance = BakeryBalance.get_instance()
        balance.amount += Decimal(instance.amount)
        balance.save(update_fields=["amount"])

@receiver(post_delete, sender=LoanRepayment)
def restore_balance_on_loan_delete(sender, instance, **kwargs):
    """Subtract repayment amount if LoanRepayment is deleted."""
    balance = BakeryBalance.get_instance()
    balance.amount -= Decimal(instance.amount)
    balance.save(update_fields=["amount"])
