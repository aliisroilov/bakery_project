from django.shortcuts import render, get_object_or_404, redirect
from .models import Order
from django.contrib import messages
from .forms import ConfirmDeliveryForm
from dashboard.models import Payment
from datetime import datetime, timedelta, time
from django.utils import timezone
from zoneinfo import ZoneInfo
from decimal import Decimal

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


def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # Permission check
    if request.user.role not in ['driver', 'manager'] and not request.user.is_superuser:
        messages.error(request, "Sizda ruxsat yo‘q")
        return redirect("dashboard")

    if request.method == "POST":
        form = ConfirmDeliveryForm(request.POST, order=order)
        if form.is_valid():
            form.save(user=request.user)
            messages.success(request, "Buyurtma tasdiqlandi!")
            return redirect("district_detail", district_id=order.shop.region.id)
    else:
        form = ConfirmDeliveryForm(order=order)

    # Prepare fields for table
    fields = [(item, form[f"delivered_{item.id}"]) for item in order.items.all()]

    return render(request, "orders/confirm_delivery.html", {
        "order": order,
        "form": form,
        "fields": fields,
    })



def mark_fully_delivered(request, order_id):
    """
    Marks an order as fully completed (yopilgan), 
    keeping already delivered quantities as final.
    Does NOT change delivered quantities.
    """
    order = get_object_or_404(Order, id=order_id)

    # ✅ Calculate total based on already delivered quantities
    total_delivered = sum(
        Decimal(item.delivered_quantity) * Decimal(item.unit_price)
        for item in order.items.all()
    )

    # ✅ Calculate total paid for this order
    total_paid = sum(p.amount for p in Payment.objects.filter(order=order))

    # ✅ Remaining debt = delivered - paid
    remaining = total_delivered - total_paid
    if remaining < 0:
        remaining = Decimal(0)

    # ✅ Update order and shop loan
    order.status = "Delivered"
    order.save(update_fields=["status"])

    order.shop.loan_balance += remaining
    order.shop.save(update_fields=["loan_balance"])

    messages.success(
        request,
        f"{order.shop.name} uchun buyurtma yopildi (To‘liq yetkazilgan deb belgilandi)."
    )

    return redirect("order_detail", order_id=order.id)