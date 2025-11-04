from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, F
from dashboard.models import Payment
from reports.models import BakeryBalance
from orders.models import OrderItem

def process_order_payment(order):
    print(f"[PROCESS] Starting process for order #{order.id}, status={order.status}, received={order.received_amount}")

    shop = order.shop
    received = Decimal(order.received_amount or 0)

    payment, created = Payment.objects.update_or_create(
        order=order,
        defaults={
            "shop": shop,
            "amount": received,
            "payment_type": "collection",
            "date": timezone.now(),
        },
    )
    print(f"[PROCESS] Payment {'created' if created else 'updated'}: {payment.amount}")

    total_received = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    print(f"[PROCESS] Total bakery received: {total_received}")

    balance = BakeryBalance.get_instance()
    balance.amount = total_received
    balance.save(update_fields=["amount"])
    print(f"[PROCESS] BakeryBalance updated to {balance.amount}")

    delivered_total = (
        OrderItem.objects.filter(order__shop=shop, order__status__in=["Delivered", "Partially Delivered"])
        .aggregate(total=Sum(F("delivered_quantity") * F("unit_price")))
        .get("total") or Decimal("0.00")
    )

    received_total = (
        Payment.objects.filter(shop=shop)
        .aggregate(total=Sum("amount"))
        .get("total") or Decimal("0.00")
    )

    new_balance = delivered_total - received_total
    if new_balance < 0:
        new_balance = Decimal("0.00")

    shop.loan_balance = new_balance
    shop.save(update_fields=["loan_balance"])
    print(f"[PROCESS] Shop {shop.id} loan updated → {shop.loan_balance}")
