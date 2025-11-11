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
from django.db import models, transaction
def order_detail(request, order_id):
    """
    Display details of a single order.
    - planned_loan sums all past orders (all time) for this shop.
    - Only the current order is shown explicitly in the page.
    """
    from orders.models import quantize_money
    
    # Get the order and related shop
    order = get_object_or_404(Order, id=order_id)
    shop = order.shop

    # Total value of the current order (use Order method)
    total_order = order.total_amount()

    # Use Uzbekistan timezone explicitly
    uz_tz = ZoneInfo("Asia/Tashkent")
    today = timezone.now().astimezone(uz_tz).date()

    # All past orders excluding current one (for planned loan calculation)
    past_orders = shop.orders.exclude(id=order.id)

    # Planned loan = sum of all items in past orders with proper Decimal handling
    planned_loan = Decimal('0.00')
    for o in past_orders:
        planned_loan += o.total_amount()

    context = {
        "order": order,
        "shop": shop,
        "total_order": total_order,
        "planned_loan": planned_loan,
        "today": today,  # optional if template wants to display today
    }

    return render(request, "orders/order_detail.html", context)

logger = logging.getLogger(__name__)


def _is_ajax(request):
    """Helper function to check if request is AJAX"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


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
                if _is_ajax(request):
                    return JsonResponse({"success": False, "error": str(e)}, status=500)
                messages.error(request, f"Xatolik yuz berdi: {str(e)}")
                return redirect("orders:order_detail", order_id=order.id)
        else:
            # Form is not valid
            if _is_ajax(request):
                return JsonResponse({"success": False, "errors": form.errors}, status=400)
            messages.error(request, "Iltimos, maydonlarni to'g'ri to'ldiring.")
    else:
        # GET request
        form = ConfirmDeliveryForm(order=order)
    
    # Prepare fields for template - pair each item with its form field
    fields = []
    for item in order.items.all():
        field_name = f"delivered_{item.id}"
        if field_name in form.fields:
            fields.append((item, form[field_name]))
    
    return render(request, "orders/confirm_delivery.html", {
        "form": form, 
        "order": order,
        "fields": fields
    })


def mark_fully_delivered(request, order_id):
    """
    Mark an order as fully delivered and recalculate shop loan balance atomically.
    """
    from orders.models import quantize_money
    
    order = get_object_or_404(Order, id=order_id)

    with transaction.atomic():
        # Lock the order and shop to prevent race conditions
        order = Order.objects.select_for_update().get(pk=order_id)
        shop = order.shop
        shop = type(shop).objects.select_for_update().get(pk=shop.pk)
        
        # Calculate total delivered for this order
        total_delivered = Decimal('0.00')
        for item in order.items.all():
            delivered_value = quantize_money(
                Decimal(str(item.delivered_quantity or 0)) * Decimal(str(item.unit_price or 0))
            )
            total_delivered += delivered_value
        
        # Calculate total paid for this order
        total_paid = Payment.objects.filter(order=order).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal('0.00')
        
        remaining = max(total_delivered - total_paid, Decimal('0.00'))

        # Update order status
        order.status = "Delivered"
        order.save(update_fields=["status"])

        # Recalculate shop loan balance from scratch (single source of truth)
        from orders.models import OrderItem
        delivered_total_all = Decimal('0.00')
        order_items = OrderItem.objects.filter(order__shop=shop).select_related('order')
        
        for item in order_items:
            item_value = quantize_money(
                Decimal(str(item.delivered_quantity or 0)) * Decimal(str(item.unit_price or 0))
            )
            delivered_total_all += item_value
        
        received_total_all = Payment.objects.filter(shop=shop).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal('0.00')
        
        shop.loan_balance = max(Decimal("0.00"), quantize_money(delivered_total_all - received_total_all))
        shop.save(update_fields=["loan_balance"])
        
        logger.info(
            f"[MARK_DELIVERED] Order #{order.id} marked fully delivered. "
            f"Shop {shop.id} loan balance: {shop.loan_balance}"
        )
    
    return redirect("dashboard:district_detail", region_id=shop.region.id)