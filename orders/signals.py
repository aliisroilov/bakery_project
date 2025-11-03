from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from django.utils import timezone
from .models import Order
from reports.models import BakeryBalance
from dashboard.models import Payment

@receiver(post_save, sender=Order)
def update_balance_and_loan(sender, instance, created, **kwargs):
    """
    When an Order is saved and marked as Delivered or Partially Delivered,
    update BakeryBalance, create Payment, and adjust shop loan balance.
    """
    # Skip for newly created empty orders
    if created:
        return

    order = instance
    shop = order.shop

    # Only apply when a delivery is confirmed
    if order.status in ["Delivered", "Partially Delivered"] and order.received_amount > 0:
        # Calculate total order value
        total_due = sum(item.total_price for item in order.items.all())
        received = Decimal(order.received_amount or 0)

        # ✅ Update or create payment
        Payment.objects.get_or_create(
            shop=shop,
            order=order,
            payment_type="collection",
            defaults={"amount": received, "date": timezone.now()},
        )

        # ✅ Update bakery balance
        balance = BakeryBalance.get_instance()
        balance.amount += received
        balance.save(update_fields=["amount"])

        # ✅ Update shop loan balance
        remaining = total_due - received
        shop.loan_balance = max(Decimal("0.00"), remaining)
        shop.save(update_fields=["loan_balance"])
