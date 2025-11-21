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
    3. Updates shop loan balance incrementally (preserving manual adjustments)

    All operations are idempotent and use proper Decimal precision.
    IMPORTANT: Uses INCREMENTAL updates to preserve manual balance adjustments!
    """
    logger.info(
        f"[PROCESS] Starting payment process for order #{order.id}, "
        f"status={order.status}, received={order.received_amount}"
    )

    shop = order.shop
    received = quantize_money(order.received_amount or 0)

    # Calculate total order value (delivered items)
    delivered_total = sum(
        quantize_money(item.delivered_quantity or 0) * quantize_money(item.unit_price or 0)
        for item in order.items.all()
    )

    # Check if payment already exists to avoid double-counting
    try:
        existing_payment = Payment.objects.get(order=order)
        old_amount = quantize_money(existing_payment.amount)

        # Only update if amount changed
        if old_amount != received:
            amount_difference = received - old_amount
            existing_payment.amount = received
            # Update date to match order date (not today!)
            from datetime import datetime, time
            order_datetime = timezone.make_aware(datetime.combine(order.order_date, time.min))
            existing_payment.date = order_datetime
            existing_payment.save(update_fields=["amount", "date"])

            # Adjust BakeryBalance by the difference only
            balance = BakeryBalance.get_instance()
            balance.amount += amount_difference
            balance.save(update_fields=["amount"])

            # Adjust shop loan by the difference (payment increased = loan decreased)
            shop.loan_balance -= amount_difference
            shop.loan_balance = max(Decimal("0.00"), shop.loan_balance)
            shop.save(update_fields=["loan_balance"])

            logger.info(
                f"[PROCESS] Payment updated: #{existing_payment.id}, "
                f"old={old_amount}, new={received}, diff={amount_difference}, "
                f"bakery_balance={balance.amount}, shop_loan={shop.loan_balance}"
            )
        else:
            logger.info(f"[PROCESS] Payment unchanged: #{existing_payment.id}, amount={received}")

    except Payment.DoesNotExist:
        # Create new payment and update balances incrementally
        # IMPORTANT: Use order's date, not today's date!
        # Convert order_date (date) to datetime for Payment.date field
        from datetime import datetime, time
        order_datetime = timezone.make_aware(datetime.combine(order.order_date, time.min))

        payment = Payment.objects.create(
            order=order,
            shop=shop,
            amount=received,
            payment_type="collection",
            date=order_datetime,
        )

        # Increment BakeryBalance (preserves manual adjustments and purchases!)
        balance = BakeryBalance.get_instance()
        balance.amount += received
        balance.save(update_fields=["amount"])

        # Update shop loan incrementally: add delivered value, subtract payment
        # This preserves any manual adjustments the user made!
        loan_change = delivered_total - received
        shop.loan_balance += loan_change
        shop.loan_balance = max(Decimal("0.00"), shop.loan_balance)
        shop.save(update_fields=["loan_balance"])

        logger.info(
            f"[PROCESS] Payment created: #{payment.id}, amount={received}, "
            f"delivered={delivered_total}, loan_change={loan_change}, "
            f"bakery_balance={balance.amount}, shop_loan={shop.loan_balance}"
        )
