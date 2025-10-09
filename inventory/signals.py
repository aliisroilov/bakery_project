from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from reports.models import BakeryBalance
from .models import Purchase
from dashboard.models import LoanRepayment


# ========================
# 💰 BALANCE UPDATES
# ========================

@receiver(post_save, sender=Purchase)
def decrease_balance_on_purchase(sender, instance, created, **kwargs):
    """
    Subtract the total purchase cost from BakeryBalance when a Purchase is created.
    """
    if created and instance.price:
        balance = BakeryBalance.get_instance()
        balance.amount -= Decimal(instance.price)
        balance.save(update_fields=["amount"])


@receiver(post_delete, sender=Purchase)
def restore_balance_on_purchase_delete(sender, instance, **kwargs):
    """
    Add back the purchase cost to BakeryBalance when the Purchase is deleted.
    """
    if instance.price:
        balance = BakeryBalance.get_instance()
        balance.amount += Decimal(instance.price)
        balance.save(update_fields=["amount"])


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
# 📦 INVENTORY STOCK UPDATES
# ========================

@receiver(post_save, sender=Purchase)
def handle_purchase_creation(sender, instance, created, **kwargs):
    """Handles both ingredient stock and bakery balance"""
    if created:
        # Update stock
        ing = instance.ingredient
        ing.quantity += instance.quantity
        ing.save(update_fields=["quantity"])

        # Update bakery balance
        if instance.price:
            balance = BakeryBalance.get_instance()
            balance.amount -= Decimal(instance.price)
            balance.save(update_fields=["amount"])

@receiver(post_delete, sender=Purchase)
def handle_purchase_deletion(sender, instance, **kwargs):
    """Revert stock and balance on delete"""
    # Revert stock
    ing = instance.ingredient
    ing.quantity -= instance.quantity
    ing.save(update_fields=["quantity"])

    # Revert bakery balance
    if instance.price:
        balance = BakeryBalance.get_instance()
        balance.amount += Decimal(instance.price)
        balance.save(update_fields=["amount"])