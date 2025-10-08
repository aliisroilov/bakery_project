from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from .models import BakeryBalance, Purchase
from dashboard.models import Payment

def update_balance():
    """Recalculate and sync BakeryBalance with all transactions."""
    from django.db.models import Sum
    total_inflows = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_outflows = Purchase.objects.aggregate(total=Sum("unit_price"))["total"] or Decimal("0.00")
    balance = total_inflows - total_outflows

    obj = BakeryBalance.get_instance()
    obj.amount = balance
    obj.save(update_fields=["amount"])


@receiver([post_save, post_delete], sender=Payment)
@receiver([post_save, post_delete], sender=Purchase)
def sync_balance(sender, **kwargs):
    update_balance()
