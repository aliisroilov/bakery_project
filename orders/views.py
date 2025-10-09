from django.shortcuts import render, get_object_or_404, redirect
from .models import Order
from django.contrib import messages
from .forms import ConfirmDeliveryForm
from dashboard.models import Payment
from datetime import datetime, timedelta, time
from django.utils import timezone
from zoneinfo import ZoneInfo

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
    order = get_object_or_404(Order, id=order_id)

    # Only allow partially delivered orders
    if order.status != "Partially Delivered":
        return redirect('order_detail', order_id=order.id)

    # Update all items delivered quantity to planned quantity
    for item in order.items.all():
        item.delivered_quantity = item.quantity
        item.save()

    # Update order status to delivered
    order.status = "Delivered"
    order.save()

    return redirect('order_detail', order_id=order.id)


