# utils.py
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from dashboard.models import Payment
from reports.models import BakeryBalance
from orders.models import OrderItem

def process_order_payment(order):
    """
    Handle all financial updates:
    - Create or update Payment for this order
    - Update Bakery balance
    - Recalculate shop loan accurately
    """
    shop = order.shop
    received = Decimal(order.received_amount or 0)

    # ✅ Create or update Payment for this order
    payment, created = Payment.objects.update_or_create(
        order=order,
        defaults={
            "shop": shop,
            "amount": received,
            "payment_type": "collection",
            "date": timezone.now()
        }
    )

    # ✅ Update Bakery balance (recompute from all payments)
    total_received = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    try:
        balance = BakeryBalance.get_instance()
        balance.amount = total_received
        balance.save(update_fields=["amount"])
    except Exception:
        pass

    # ✅ Calculate total delivered value (only for delivered or partial orders)
    delivered_orders = shop.orders.filter(status__in=["Delivered", "Partially Delivered"])
    delivered_total = Decimal("0.00")
    for o in delivered_orders:
        for i in o.items.all():
            delivered_total += (Decimal(i.delivered_quantity or 0) * Decimal(i.unit_price or 0))

    # ✅ Calculate total received for this shop
    received_total = Payment.objects.filter(shop=shop).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    # ✅ New loan = delivered_total - received_total
    new_balance = delivered_total - received_total
    if new_balance < 0:
        new_balance = Decimal("0.00")

    shop.loan_balance = new_balance
    shop.save(update_fields=["loan_balance"])
