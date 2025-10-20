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

    # 🔒 Permission check
    if request.user.role not in ['driver', 'manager'] and not request.user.is_superuser:
        if _is_ajax(request):
            return JsonResponse({"success": False, "error": "permission_denied"}, status=403)
        messages.error(request, "Sizda ruxsat yo‘q")
        return redirect("dashboard")

    if request.method == "POST":
        form = ConfirmDeliveryForm(request.POST, order=order)
        if form.is_valid():
            try:
                form.save(user=request.user)

                # 🥐 Deduct delivered products from bakery stock
                for item in order.items.all():
                    delivered_qty = Decimal(item.delivered_quantity or 0)
                    if delivered_qty > 0:
                        stock, _ = BakeryProductStock.objects.get_or_create(
                            product=item.product,
                            defaults={"quantity": Decimal("0.000"), "pinned": True}
                        )
                        stock.quantity -= delivered_qty
                        stock.save(update_fields=["quantity"])

                redirect_url = reverse("dashboard:district_detail", args=[order.shop.region.id])

                if _is_ajax(request):
                    return JsonResponse({"success": True, "redirect_url": redirect_url})
                messages.success(request, "Buyurtma tasdiqlandi!")
                return redirect(redirect_url)

            except Exception as e:
                logger.exception("Error during delivery confirmation")
                if _is_ajax(request):
                    resp = {"success": False, "error": "server_exception"}
                    if settings.DEBUG:
                        resp["exception"] = str(e)
                    return JsonResponse(resp, status=500)
                messages.error(request, "Server xatosi yuz berdi.")
                return redirect(request.path)

        # Form invalid
        if _is_ajax(request):
            return JsonResponse({
                "success": False,
                "error": "invalid_form",
                "form_errors": form.errors.get_json_data()
            }, status=400)
    else:
        form = ConfirmDeliveryForm(order=order)

    fields = [(item, form[f"delivered_{item.id}"]) for item in order.items.all()]

    return render(request, "orders/confirm_delivery.html", {
        "order": order,
        "form": form,
        "fields": fields,
    })


def mark_fully_delivered(request, order_id):
    """
    Marks an order as fully completed (yopilgan),
    without changing delivered quantities.
    Also adjusts shop loan balance accordingly.
    """
    order = get_object_or_404(Order, id=order_id)

    total_delivered = sum(
        Decimal(item.delivered_quantity or 0) * Decimal(item.unit_price or 0)
        for item in order.items.all()
    )
    total_paid = sum(p.amount for p in Payment.objects.filter(order=order))
    remaining = max(total_delivered - total_paid, Decimal(0))

    order.status = "Delivered"
    order.save(update_fields=["status"])

    order.shop.loan_balance += remaining
    order.shop.save(update_fields=["loan_balance"])

    messages.success(
        request,
        f"{order.shop.name} uchun buyurtma yopildi (To‘liq yetkazilgan deb belgilandi)."
    )

    return redirect("order_detail", order_id=order.id)


# 🧩 Helper
def _is_ajax(request):
    """Detect AJAX requests consistently."""
    return (
        request.headers.get("x-requested-with") == "XMLHttpRequest" or
        request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
    )