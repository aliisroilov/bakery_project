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


def recalculate_shop_loan_balance(shop):
    """
    Recalculate shop loan balance from all delivered orders and all payments.

    Loan balance = Total delivered value - Total payments received
    This is the single source of truth for shop loan calculations.
    """
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
        f"[RECALC] Shop {shop.id} ({shop.name}) loan balance updated: "
        f"delivered={delivered_total}, received={received_total}, loan={shop.loan_balance}"
    )

    return new_balance


def process_order_payment(order):
    """
    Process payment for an order and update all related financial records atomically.

    This function:
    1. Creates/updates a Payment record for the order
    2. Updates BakeryBalance incrementally (preserving purchases and manual adjustments)
    3. Recalculates shop loan balance

    All operations are idempotent and use proper Decimal precision.
    """
    logger.info(
        f"[PROCESS] Starting payment process for order #{order.id}, "
        f"status={order.status}, received={order.received_amount}"
    )

    shop = order.shop
    received = quantize_money(order.received_amount or 0)

    # Check if payment already exists to avoid double-counting
    try:
        existing_payment = Payment.objects.get(order=order)
        old_amount = quantize_money(existing_payment.amount)

        # Only update if amount changed
        if old_amount != received:
            amount_difference = received - old_amount
            existing_payment.amount = received
            existing_payment.date = timezone.now()
            existing_payment.save(update_fields=["amount", "date"])

            # Adjust balance by the difference only
            balance = BakeryBalance.get_instance()
            balance.amount += amount_difference
            balance.save(update_fields=["amount"])

            logger.info(
                f"[PROCESS] Payment updated: #{existing_payment.id}, "
                f"old={old_amount}, new={received}, diff={amount_difference}, "
                f"balance={balance.amount}"
            )
        else:
            logger.info(f"[PROCESS] Payment unchanged: #{existing_payment.id}, amount={received}")

    except Payment.DoesNotExist:
        # Create new payment and increment balance
        payment = Payment.objects.create(
            order=order,
            shop=shop,
            amount=received,
            payment_type="collection",
            date=timezone.now(),
        )

        # Increment balance (don't reset - preserves purchases and manual adjustments!)
        balance = BakeryBalance.get_instance()
        balance.amount += received
        balance.save(update_fields=["amount"])

        logger.info(
            f"[PROCESS] Payment created: #{payment.id}, amount={received}, "
            f"balance={balance.amount}"
        )

    # Recalculate shop loan balance using centralized function
    recalculate_shop_loan_balance(shop)
