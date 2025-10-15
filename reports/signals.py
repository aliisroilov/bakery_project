from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from .models import BakeryBalance, Purchase
from dashboard.models import Payment

@receiver(post_save, sender=Purchase)
def decrease_balance_on_purchase(sender, instance, created, **kwargs):
    """Reduce balance only when a new purchase is made."""
    balance = BakeryBalance.get_instance()

    if created:  # only subtract when new purchase is added
        balance.amount -= instance.unit_price
        balance.save(update_fields=["amount"])
    else:
        # when purchase is edited, we can optionally handle that later
        pass


@receiver(post_delete, sender=Purchase)
def restore_balance_on_purchase_delete(sender, instance, **kwargs):
    """Restore balance if a purchase is deleted."""
    balance = BakeryBalance.get_instance()
    balance.amount += instance.unit_price
    balance.save(update_fields=["amount"])


@receiver(post_save, sender=Payment)
def increase_balance_on_payment(sender, instance, created, **kwargs):
    """Increase balance when money is collected."""
    if created:
        balance = BakeryBalance.get_instance()
        balance.amount += instance.amount
        balance.save(update_fields=["amount"])
