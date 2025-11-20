from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, DecimalField, Value
from django.db.models.functions import Coalesce
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from decimal import Decimal
from django.db import connection

from orders.models import Order, OrderItem
from shops.models import Shop, Region
from .forms import LoanRepaymentForm
from .models import Payment
from reports.models import Purchase, BakeryBalance
from users.decorators import viewer_required

try:
    from dashboard.models import LoanRepayment
except Exception:
    LoanRepayment = None


# --- Utility: check DB engine ---
def db_check(request):
    return JsonResponse({"db_engine": connection.vendor})


# --- VIEWER DASHBOARD ---
@login_required
def viewer_dashboard(request):
    """Simple dashboard for viewer users (read-only)."""
    if request.user.role != "viewer":
        return HttpResponseForbidden("You are not allowed to view this page.")

    today = timezone.now().date()
    # Filter by order_date instead of created_at
    orders = Order.objects.filter(order_date=today)

    stats = {
        "today_orders": orders.count(),
        "pending": orders.filter(status="Pending").count(),
        "partial": orders.filter(status="Partially Delivered").count(),
        "delivered": orders.filter(status="Delivered").count(),
    }

    purchases_total = Purchase.objects.filter(purchase_date=today).aggregate(
        total=Coalesce(Sum("unit_price"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    shop_loans = {shop.id: shop.loan_balance for shop in Shop.objects.all()}
    total_loan = sum(shop_loans.values()) or Decimal(0)

    received_money = Payment.objects.filter(
        date__date=today, payment_type="collection"
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"] or Decimal(0)

    bakery_balance = BakeryBalance.get_instance().amount

    context = {
        "stats": stats,
        "total_loan": total_loan,
        "received_money": received_money,
        "purchases_total": purchases_total,
        "bakery_balance": bakery_balance,
    }
    return render(request, "dashboard/admins/dashboard.html", context)


# --- MANAGER/ADMIN DASHBOARD ---
@login_required
def dashboard_view(request):
    """Full dashboard with financial summaries."""
    today = timezone.now().date()
    orders = Order.objects.filter(order_date=today)

    stats = {
        "today_orders": orders.count(),
        "pending": orders.filter(status="Pending").count(),
        "partial": orders.filter(status="Partially Delivered").count(),
        "delivered": orders.filter(status="Delivered").count(),
    }

    purchases_total = Purchase.objects.filter(purchase_date=today).aggregate(
        total=Coalesce(Sum("unit_price"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    shop_loans = {shop.id: shop.loan_balance for shop in Shop.objects.all()}
    total_loan = sum(shop_loans.values()) or Decimal(0)

    received_money = Payment.objects.filter(
        date__date=today, payment_type="collection"
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"] or Decimal(0)

    repayments_today = Payment.objects.filter(
        date__date=today, payment_type="repayment"
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"] or Decimal(0)

    bakery_balance = BakeryBalance.get_instance().amount

    context = {
        "orders": orders,
        "stats": stats,
        "shop_loans": shop_loans,
        "total_loan": total_loan,
        "received_money": received_money,
        "purchases_total": purchases_total,
        "repayments_today": repayments_today,
        "bakery_balance": bakery_balance,
    }
    return render(request, "dashboard/dashboard.html", context)


# --- DISTRICTS OVERVIEW ---
@login_required
def districts_view(request):
    """Show per-district delivery statistics for today."""
    today = timezone.now().date()
    districts = Region.objects.all()

    district_list = []
    for district in districts:
        orders = Order.objects.filter(shop__region=district, order_date=today)
        district_list.append({
            "district": district,
            "total": orders.count(),
            "partial": orders.filter(status="Partially Delivered").count(),
            "delivered": orders.filter(status="Delivered").count(),
        })

    return render(request, "dashboard/districts.html", {
        "district_list": district_list,
    })


# --- DISTRICT DETAIL ---
@login_required
def district_detail_view(request, district_id):
    """Show all shops and orders in a specific district (today only)."""
    district = get_object_or_404(Region, id=district_id)
    today = timezone.now().date()

    orders = Order.objects.filter(
        shop__region=district, order_date=today
    ).order_by("shop__name")

    shop_loans = {}
    shops_in_orders = set(order.shop for order in orders)
    for shop in shops_in_orders:
        # planned_loan still sums all past orders (all dates)
        past_orders = shop.orders.exclude(id__in=[o.id for o in orders])
        planned_loan = sum(
            item.total_price for o in past_orders for item in o.items.all()
        )
        shop_loans[shop.id] = planned_loan

    return render(request, "dashboard/district_detail.html", {
        "district": district,
        "orders": orders,
        "shop_loans": shop_loans,
    })


# --- LOAN REPAYMENT ---
@login_required
def loan_repayment_view(request):
    if request.method == "POST":
        form = LoanRepaymentForm(request.POST)
        if form.is_valid():
            shop = form.cleaned_data["shop"]
            amount = Decimal(form.cleaned_data["amount"])

            # Use atomic transaction to prevent race conditions
            from django.db import transaction
            from orders.utils import recalculate_shop_loan_balance

            with transaction.atomic():
                # Lock shop row for update
                shop = Shop.objects.select_for_update().get(pk=shop.pk)

                # Create LoanRepayment (signal will handle BakeryBalance)
                LoanRepayment.objects.create(shop=shop, amount=amount)

                # Create Payment record for the loan repayment
                Payment.objects.create(
                    shop=shop,
                    amount=amount,
                    payment_type="loan_repayment",
                    date=timezone.now()
                )

                # Recalculate shop loan balance correctly from ALL orders and payments
                recalculate_shop_loan_balance(shop)

            messages.success(request, f"{shop.name} uchun {amount} so'm qarz to'landi.")
            return redirect("dashboard:loan_repayment")
    else:
        form = LoanRepaymentForm()

    return render(request, "dashboard/loan_repayment.html", {
        "form": form,
        "shops": Shop.objects.all()
    })