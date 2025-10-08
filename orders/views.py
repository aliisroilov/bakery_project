from django.shortcuts import render, get_object_or_404, redirect
from .models import Order
from django.contrib import messages
from .forms import ConfirmDeliveryForm
from dashboard.models import Payment
from datetime import datetime, timedelta, time
from django.utils import timezone
from zoneinfo import ZoneInfo

def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    shop = order.shop

    # Sum of current order
    total_order = sum([item.total_price for item in order.items.all()])

    # Use Uzbekistan timezone explicitly
    uz_tz = ZoneInfo("Asia/Tashkent")
    now = timezone.now().astimezone(uz_tz)
    yesterday = now.date() - timedelta(days=1)
    cutoff = datetime.combine(yesterday, time(17, 0), tzinfo=uz_tz)

    # Past orders excluding current order, but only after cutoff
    past_orders = shop.orders.exclude(id=order.id).filter(created_at__gt=cutoff)

    # Planned loan (sum of past orders items)
    planned_loan = sum([item.total_price for o in past_orders for item in o.items.all()])

    return render(request, "orders/order_detail.html", {
        "order": order,
        "shop": shop,
        "total_order": total_order,
        "planned_loan": planned_loan,
    })

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


