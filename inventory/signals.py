from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from reports.models import BakeryBalance
from .models import Purchase
from dashboard.models import LoanRepayment


# ========================
# 💰 LOAN REPAYMENT BALANCE UPDATES
# ========================

@receiver(post_save, sender=LoanRepayment)
def update_balance_on_loan(sender, instance, created, **kwargs):
    """
    Add repayment amount to BakeryBalance when a loan is repaid.
    """
    if created and instance.amount:
        balance = BakeryBalance.get_instance()
        balance.amount += Decimal(instance.amount)
        balance.save(update_fields=["amount"])


@receiver(post_delete, sender=LoanRepayment)
def restore_balance_on_loan_delete(sender, instance, **kwargs):
    """
    Subtract repayment amount if a LoanRepayment record is deleted.
    """
    if instance.amount:
        balance = BakeryBalance.get_instance()
        balance.amount -= Decimal(instance.amount)
        balance.save(update_fields=["amount"])


# ========================
# 📦 INVENTORY STOCK & BALANCE UPDATES
# ========================

@receiver(post_save, sender=Purchase)
def handle_purchase_creation(sender, instance, created, **kwargs):
    """
    Handles both ingredient stock increase and bakery balance decrease.
    Called only once when a purchase is created.
    """
    if created:
        # Update ingredient stock
        ing = instance.ingredient
        ing.quantity += instance.quantity
        ing.save(update_fields=["quantity"])

        # Update bakery balance (decrease by purchase cost)
        if instance.price:
            balance = BakeryBalance.get_instance()
            balance.amount -= Decimal(instance.price)
            balance.save(update_fields=["amount"])


@receiver(post_delete, sender=Purchase)
def handle_purchase_deletion(sender, instance, **kwargs):
    """
    Revert ingredient stock and bakery balance when purchase is deleted.
    """
    # Revert ingredient stock
    ing = instance.ingredient
    ing.quantity -= instance.quantity
    ing.save(update_fields=["quantity"])

    # Revert bakery balance (add back purchase cost)
    if instance.price:
        balance = BakeryBalance.get_instance()
        balance.amount += Decimal(instance.price)
        balance.save(update_fields=["amount"])