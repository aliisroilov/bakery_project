from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from orders.models import Order
from shops.models import Shop, Region
from django.db.models import Sum, DecimalField, Value
from django.utils import timezone
from .forms import LoanRepaymentForm
from django.contrib import messages
from .models import LoanRepayment, Payment
from django.db.models.functions import Coalesce
from orders.models import Order, OrderItem
from shops.models import Shop
from reports.models import Purchase
from decimal import Decimal
from users.decorators import viewer_required
from django.http import HttpResponseForbidden

try:
    from dashboard.models import LoanRepayment
except Exception:
    LoanRepayment = None



@login_required
def viewer_dashboard(request):
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

    # Purchases today (sum of unit_price)
    purchases_total = Purchase.objects.filter(purchase_date=today).aggregate(
        total=Coalesce(Sum("unit_price"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    # Shop loans
    shop_loans = {shop.id: shop.loan_balance for shop in Shop.objects.all()}
    total_loan = sum(shop_loans.values()) or Decimal(0)

    # Today’s received money
    received_money = Payment.objects.filter(
        date__date=today, payment_type="collection"
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"] or Decimal(0)

    # Bakery balance (all-time) = all inflows - purchases
    total_payments_all = Payment.objects.aggregate(
        total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    total_purchases_all = Purchase.objects.aggregate(
        total=Coalesce(Sum("unit_price"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    bakery_balance = Decimal(total_payments_all) - Decimal(total_purchases_all)

    context = {
        "stats": stats,
        "total_loan": total_loan,
        "received_money": received_money,
        "purchases_total": purchases_total,
        "bakery_balance": bakery_balance,
    }

    # 🔑 Different template: only stats (6 blocks, no orders list)
    return render(request, "dashboard/admins/dashboard.html", context)


@login_required
def dashboard_view(request):
    today = timezone.now().date()
    orders = Order.objects.filter(created_at__date=today)

    stats = {
        "today_orders": orders.count(),
        "pending": orders.filter(status="Pending").count(),
        "partial": orders.filter(status="Partially Delivered").count(),
        "delivered": orders.filter(status="Delivered").count(),
    }

    # Purchases today (sum of unit_price)
    purchases_total = Purchase.objects.filter(purchase_date=today).aggregate(
        total=Coalesce(Sum("unit_price"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    # Shop loans
    shop_loans = {shop.id: shop.loan_balance for shop in Shop.objects.all()}
    total_loan = sum(shop_loans.values()) or Decimal(0)

    # --- TODAY driver-collected money (Bugungi tushum) ---
    received_money = Payment.objects.filter(
        date__date=today, payment_type="collection"
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"] or Decimal(0)

    # optional: repayments today (show separately)
    repayments_today = Payment.objects.filter(
        date__date=today, payment_type="repayment"
    ).aggregate(total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField()))["total"] or Decimal(0)

    # --- Bakery balance (all-time) = all inflows (payments) - purchases (expenses) ---
    total_payments_all = Payment.objects.aggregate(
        total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    total_purchases_all = Purchase.objects.aggregate(
        total=Coalesce(Sum("unit_price"), Value(0), output_field=DecimalField())
    )["total"] or Decimal(0)

    bakery_balance = Decimal(total_payments_all) - Decimal(total_purchases_all)

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


@login_required
def districts_view(request):
    today = timezone.now().date()
    districts = Region.objects.all()

    # Prepare stats for each district as list of tuples
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


@login_required
def district_detail_view(request, district_id):
    """Show all shops and orders in a district (today only)."""
    district = get_object_or_404(Region, id=district_id)
    today = timezone.now().date()
    
    # Orders in the district, today only
    orders = Order.objects.filter(
        shop__region=district,
        created_at__date=today
    ).order_by("shop__name")
    
    # Optional: Calculate planned loan per shop excluding today
    shop_loans = {}
    shops_in_orders = set(order.shop for order in orders)
    for shop in shops_in_orders:
        past_orders = shop.orders.exclude(created_at__date=today)
        planned_loan = 0
        for o in past_orders:
            for item in o.items.all():
                planned_loan += item.total_price
        shop_loans[shop.id] = planned_loan

    return render(request, "dashboard/district_detail.html", {
        "district": district,
        "orders": orders,
        "shop_loans": shop_loans
    })


@login_required
def loan_repayment_view(request):
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

            # Record repayment model (if you keep it)
            LoanRepayment.objects.create(shop=shop, amount=amount)

            # ALSO record a Payment so dashboard/tushum can use it if desired
            Payment.objects.create(
                shop=shop,
                amount=amount,
                payment_type="repayment",
                collected_by=request.user,
                notes="Loan repayment via form"
            )

            messages.success(request, f"{shop.name} uchun {amount} so‘m qarz to‘landi.")
            return redirect("loan_repayment")
    else:
        form = LoanRepaymentForm()

    return render(request, "dashboard/loan_repayment.html", {
        "form": form,
        "shops": Shop.objects.all()
    })