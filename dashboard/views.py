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
    orders = Order.objects.filter(created_at__date=today)

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

    # ✅ Unified Bakery Balance
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
    orders = Order.objects.filter(created_at__date=today)

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

    # ✅ Unified Bakery Balance — always correct and synced via signals
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
        orders = Order.objects.filter(shop__region=district, created_at__date=today)
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
        shop__region=district, created_at__date=today
    ).order_by("shop__name")

    shop_loans = {}
    shops_in_orders = set(order.shop for order in orders)
    for shop in shops_in_orders:
        past_orders = shop.orders.exclude(created_at__date=today)
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
    """Form for managers to register loan repayments."""
    if request.method == "POST":
        form = LoanRepaymentForm(request.POST)
        if form.is_valid():
            shop = form.cleaned_data["shop"]
            amount = Decimal(form.cleaned_data["amount"])

            # Reduce loan balance
            if shop.loan_balance >= amount:
                shop.loan_balance -= amount
            else:
                shop.loan_balance = 0
            shop.save()

            # Record repayment entry
            if LoanRepayment:
                LoanRepayment.objects.create(shop=shop, amount=amount)

            # Record Payment so it appears in reports & updates balance
            Payment.objects.create(
                shop=shop,
                amount=amount,
                payment_type="repayment",
                collected_by=request.user,
                notes="Loan repayment via form"
            )

            # ✅ BakeryBalance auto-updated via signals (no manual update needed)

            messages.success(request, f"{shop.name} uchun {amount} so‘m qarz to‘landi.")
            return redirect("loan_repayment")
    else:
        form = LoanRepaymentForm()

    return render(request, "dashboard/loan_repayment.html", {
        "form": form,
        "shops": Shop.objects.all()
    })
