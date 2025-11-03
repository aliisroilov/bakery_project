from django.shortcuts import render, get_object_or_404, redirect
from .models import Order
from django.contrib import messages
from .forms import ConfirmDeliveryForm
from dashboard.models import Payment
from datetime import datetime, timedelta, time
from django.utils import timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from django.http import JsonResponse
from django.urls import reverse
import logging
from django.conf import settings
from inventory.models import BakeryProductStock
from .utils import process_order_payment

def order_detail(request, order_id):
    """
    Display details of a single order.
    - planned_loan sums all past orders (all time) for this shop.
    - Only the current order is shown explicitly in the page.
    """
    # Get the order and related shop
    order = get_object_or_404(Order, id=order_id)
    shop = order.shop

    # Total value of the current order
    total_order = sum(item.total_price for item in order.items.all())

    # Use Uzbekistan timezone explicitly
    uz_tz = ZoneInfo("Asia/Tashkent")
    today = timezone.now().astimezone(uz_tz).date()

    # All past orders excluding current one (for planned loan calculation)
    past_orders = shop.orders.exclude(id=order.id)

    # Planned loan = sum of all items in past orders
    planned_loan = sum(item.total_price for o in past_orders for item in o.items.all())

    context = {
        "order": order,
        "shop": shop,
        "total_order": total_order,
        "planned_loan": planned_loan,
        "today": today,  # optional if template wants to display today
    }

    return render(request, "orders/order_detail.html", context)

logger = logging.getLogger(__name__)


def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # permission checks (keep as-is)...

    if request.method == "POST":
        form = ConfirmDeliveryForm(request.POST, order=order)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1) save form (updates delivered quantities + order.received_amount + status)
                    received = form.save(user=request.user)

                    # 2) Deduct delivered products from stock
                    for item in order.items.all():
                        delivered_qty = Decimal(item.delivered_quantity or 0)
                        if delivered_qty > 0:
                            stock, _ = BakeryProductStock.objects.get_or_create(
                                product=item.product,
                                defaults={"quantity": Decimal("0.000"), "pinned": True}
                            )
                            stock.quantity -= delivered_qty
                            stock.save(update_fields=["quantity"])

                    # 3) Process payments / bakery balance / recalc loan in one place
                    process_order_payment(order)

                # redirect / messages (same as before)
                redirect_url = reverse("dashboard:district_detail", args=[order.shop.region.id])
                if _is_ajax(request):
                    return JsonResponse({"success": True, "redirect_url": redirect_url})
                messages.success(request, "Buyurtma tasdiqlandi va balans yangilandi!")
                return redirect(redirect_url)

            except Exception as e:
                logger.exception("Error during delivery confirmation: %s", e)
                # handle AJAX / messages as before...


def mark_fully_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    total_delivered = sum(
        Decimal(item.delivered_quantity or 0) * Decimal(item.unit_price or 0)
        for item in order.items.all()
    )
    total_paid = sum(p.amount for p in Payment.objects.filter(order=order))
    remaining = max(total_delivered - total_paid, Decimal(0))

    order.status = "Delivered"
    order.save(update_fields=["status"])

    # SET shop loan to recalculated value (not +=)
    # Recalculate across shop to be safe:
    from orders.models import OrderItem
    delivered_total_all = sum(
        Decimal(it.delivered_quantity or 0) * Decimal(it.unit_price or 0)
        for it in OrderItem.objects.filter(order__shop=order.shop)
    )
    received_total_all = sum(Decimal(p.amount or 0) for p in Payment.objects.filter(shop=order.shop))
    order.shop.loan_balance = max(Decimal("0.00"), delivered_total_all - received_total_all)
    order.shop.save(update_fields=["loan_balance"])