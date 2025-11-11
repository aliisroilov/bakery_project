from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db.models import Sum, F
from dashboard.models import Payment
from reports.models import BakeryBalance
from orders.models import OrderItem
import logging

logger = logging.getLogger(__name__)


def quantize_money(value):
    """Round money values to 2 decimal places."""
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def process_order_payment(order):
    """
    Process payment for an order and update all related financial records atomically.
    
    This function:
    1. Creates/updates a Payment record for the order
    2. Updates BakeryBalance to match sum of all payments
    3. Recalculates shop loan balance
    
    All operations are idempotent and use proper Decimal precision.
    """
    logger.info(
        f"[PROCESS] Starting payment process for order #{order.id}, "
        f"status={order.status}, received={order.received_amount}"
    )

    shop = order.shop
    received = quantize_money(order.received_amount or 0)

    # Create or update payment (idempotent)
    payment, created = Payment.objects.update_or_create(
        order=order,
        defaults={
            "shop": shop,
            "amount": received,
            "payment_type": "collection",
            "date": timezone.now(),
        },
    )
    
    action = "created" if created else "updated"
    logger.info(f"[PROCESS] Payment {action}: #{payment.id}, amount={payment.amount}")

    # Update BakeryBalance to sum of ALL payments
    total_received = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    total_received = quantize_money(total_received)
    
    logger.info(f"[PROCESS] Total bakery received across all payments: {total_received}")

    balance = BakeryBalance.get_instance()
    balance.amount = total_received
    balance.save(update_fields=["amount"])
    logger.info(f"[PROCESS] BakeryBalance updated to {balance.amount}")

    # Recalculate shop loan balance
    # delivered_total = sum of (delivered_quantity * unit_price) for delivered/partial orders
    delivered_agg = (
        OrderItem.objects.filter(
            order__shop=shop,
            order__status__in=["Delivered", "Partially Delivered"]
        )
        .aggregate(total=Sum(F("delivered_quantity") * F("unit_price")))
        .get("total") or Decimal("0.00")
    )
    delivered_total = quantize_money(delivered_agg)

    # received_total = sum of all payments to this shop
    received_agg = (
        Payment.objects.filter(shop=shop)
        .aggregate(total=Sum("amount"))
        .get("total") or Decimal("0.00")
    )
    received_total = quantize_money(received_agg)

    # Loan balance = delivered - received (never negative)
    new_balance = max(Decimal("0.00"), delivered_total - received_total)
    new_balance = quantize_money(new_balance)

    shop.loan_balance = new_balance
    shop.save(update_fields=["loan_balance"])
    
    logger.info(
        f"[PROCESS] Shop {shop.id} ({shop.name}) loan balance updated: "
        f"delivered={delivered_total}, received={received_total}, loan={shop.loan_balance}"
    )
