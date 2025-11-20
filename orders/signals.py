from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from .utils import process_order_payment

@receiver(post_save, sender=Order)
def update_balance_and_loan(sender, instance, created, **kwargs):
    """
    When an Order is saved and marked as Delivered or Partially Delivered,
    process payment and update all financial records correctly.

    Uses process_order_payment() as single source of truth to avoid double-counting.
    """
    # Skip for newly created empty orders
    if created:
        return

    order = instance

    # Only apply when a delivery is confirmed
    if order.status in ["Delivered", "Partially Delivered"] and order.received_amount > 0:
        # Use process_order_payment as single source of truth
        # This function handles:
        # 1. Creating/updating Payment record
        # 2. Recalculating BakeryBalance from ALL payments (no double-counting)
        # 3. Recalculating shop loan balance correctly
        process_order_payment(order)
