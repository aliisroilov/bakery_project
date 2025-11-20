from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, FloatField
from orders.models import OrderItem
from datetime import datetime
from django.contrib import messages
from .forms import CategoryForm, PurchaseForm
from orders.models import OrderItem
from .models import Purchase, Category, BakeryBalance
from dashboard.models import LoanRepayment, Payment
from salary.models import SalaryPayment
from shops.models import Shop
from decimal import Decimal
from orders.models import Order
 # add BakeryBalance


def manager_or_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role == "driver":
            messages.error(request, "Sizda ruxsat yo‘q")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


@manager_or_admin_required
def reports_home(request):
    return render(request, 'reports/home.html')

def contragents_report(request):
    shops = Shop.objects.all().order_by("name")
    return render(request, "reports/contragents_report.html", {
        "shops": shops
    })

def shop_history(request, shop_id):
    shop = get_object_or_404(Shop, id=shop_id)

    # 🧾 Fetch all related data
    orders = Order.objects.filter(shop=shop).select_related("shop")
    payments = Payment.objects.filter(shop=shop)

    # 📋 Create unified history list (orders + payments combined)
    history = []

    # Add orders to history
    for order in orders:
        history.append({
            "date": order.order_date,
            "type": "order",
            "status": order.status,
            "description": f"Buyurtma #{order.id}",
            "total_amount": order.total_amount(),
            "received_amount": order.received_amount,
            "order_id": order.id,
        })

    # Add payments to history
    for payment in payments:
        history.append({
            "date": payment.date.date() if hasattr(payment.date, 'date') else payment.date,
            "type": "payment",
            "status": None,
            "description": f"To'lov - {payment.get_payment_type_display()}",
            "amount": payment.amount,
            "notes": payment.notes,
        })

    # Sort by date (most recent first)
    history.sort(key=lambda x: x["date"], reverse=True)

    context = {
        "shop": shop,
        "history": history,
    }
    return render(request, "reports/shop_history.html", context)


def sales_report(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # ✅ Include both lowercase and capitalized forms
    valid_statuses = ['delivered', 'Delivered', 'partially_delivered', 'Partially Delivered']

    # ✅ Query only relevant orders
    order_items = (
        OrderItem.objects
        .select_related('product', 'order', 'order__shop')
        .filter(order__status__in=valid_statuses)
    )

    # ✅ Apply optional date filtering
    if start_date and end_date:
        order_items = order_items.filter(order__created_at__date__range=[start_date, end_date])
    elif start_date:
        order_items = order_items.filter(order__created_at__date__gte=start_date)
    elif end_date:
        order_items = order_items.filter(order__created_at__date__lte=end_date)

    # ✅ Use delivered_quantity if exists, else quantity
    qty_field = 'delivered_quantity' if hasattr(OrderItem, 'delivered_quantity') else 'quantity'

    # ✅ Annotate by product and shop
    product_sales = order_items.values(
        'product__name',
        'order__shop__name',
        'order__status',
        'order__created_at'
    ).annotate(quantity_sold=Sum(qty_field)).order_by('-order__created_at')

    total_qty = order_items.aggregate(total=Sum(qty_field))['total'] or 0

    context = {
        'report_title': 'Sotuvlar hisobotlari',
        'product_sales': product_sales,
        'total': total_qty,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'reports/sales_report.html', context)


@manager_or_admin_required
def financial_report(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    order_items = OrderItem.objects.select_related('order')
    if start_date and end_date:
        order_items = order_items.filter(order__created_at__date__range=[start_date, end_date])

    total_sales = order_items.aggregate(total=Sum(F('unit_price') * F('quantity')))['total'] or 0

    context = {
        'report_title': 'Financial Report',
        'total_sales': total_sales,
        'total_purchase': 0,  # no purchase data included
        'net_profit': total_sales,
        'start_date': start_date,
        'end_date': end_date,
        'show_filter': True,
    }
    return render(request, 'reports/financial_report.html', context)


def category_list(request):
    categories = Category.objects.all()
    return render(request, "reports/categories/list.html", {"categories": categories})

def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("reports:category_list")
    else:
        form = CategoryForm()
    return render(request, "reports/categories/form.html", {"form": form})

def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect("reports:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(request, "reports/categories/form.html", {"form": form})

def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
        return redirect("reports:category_list")
    return render(request, "reports/categories/confirm_delete.html", {"category": category})


# Purchase CRUD
def purchase_list(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    purchases = Purchase.objects.select_related("category").all()

    if start_date and end_date:
        purchases = purchases.filter(purchase_date__range=[start_date, end_date])

    # Group purchases by category
    purchases_by_category = {}
    for p in purchases:
        category_name = p.category.name if p.category else "Kategoriya belgilanmagan"
        if category_name not in purchases_by_category:
            purchases_by_category[category_name] = []
        purchases_by_category[category_name].append(p)

    # Total cost (sum of unit_price)
    total_cost = purchases.aggregate(total=Sum('unit_price'))['total'] or 0

    context = {
        "purchases_by_category": purchases_by_category,
        "total_cost": total_cost,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "reports/purchase_report.html", context)

def purchase_create(request):
    if request.method == "POST":
        form = PurchaseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("reports:purchase_list")
    else:
        form = PurchaseForm()
    return render(request, "reports/form.html", {
        "form": form,
        "title": "Add Purchase"
    })


def purchase_update(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == "POST":
        form = PurchaseForm(request.POST, instance=purchase)
        if form.is_valid():
            form.save()
            return redirect("reports:purchase_list")
    else:
        form = PurchaseForm(instance=purchase)
    return render(request, "reports/form.html", {
        "form": form,
        "title": "Edit Purchase"
    })



def purchase_delete(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    if request.method == "POST":
        purchase.delete()
        return redirect("reports:purchase_list")
    return render(request, "reports/confirm_delete.html", {"purchase": purchase})



def all_reports(request):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    # Base querysets
    purchases = Purchase.objects.all()
    repayments = LoanRepayment.objects.all()
    payments = Payment.objects.filter(payment_type="collection")
    salary_payments = SalaryPayment.objects.all()

    # Apply date filters
    if start_date:
        purchases = purchases.filter(purchase_date__gte=start_date)
        repayments = repayments.filter(date__gte=start_date)
        payments = payments.filter(date__gte=start_date)
        salary_payments = salary_payments.filter(created_at__date__gte=start_date)

    if end_date:
        purchases = purchases.filter(purchase_date__lte=end_date)
        repayments = repayments.filter(date__lte=end_date)
        payments = payments.filter(date__lte=end_date)
        salary_payments = salary_payments.filter(created_at__date__lte=end_date)

    # Collect all reports (money-related only)
    reports = []

    # Purchases (expenses)
    for p in purchases:
        reports.append({
            "date": p.purchase_date,
            "category": "Xarid (Purchase)",
            "description": p.notes or p.item_name,
            "counterparty": "-",
            "income": None,
            "expense": p.unit_price or Decimal("0"),
        })

    # Loan repayments (income)
    for r in repayments:
        reports.append({
            "date": r.date,
            "category": "Qarz to‘lovi (Loan Repayment)",
            "description": f"{r.shop.name} dan to‘lov",
            "counterparty": r.shop.name,
            "income": r.amount or Decimal("0"),
            "expense": None,
        })

    # Payment collections (income)
    for pay in payments:
        reports.append({
            "date": pay.date,
            "category": "To‘lov yig‘imi (Payment Collection)",
            "description": f"{pay.shop.name} dan to‘lov",
            "counterparty": pay.shop.name,
            "income": pay.amount or Decimal("0"),
            "expense": None,
        })

    # Salary / Advance (expenses)
    for s in salary_payments:
        reports.append({
            "date": s.created_at.date(),
            "category": "Ish haqi (Salary / Advance)",
            "description": s.note or f"{s.user.get_full_name() if hasattr(s.user, 'get_full_name') else s.user.username} oylik",
            "counterparty": s.user.username,
            "income": None,
            "expense": s.amount,
        })

    # Normalize and sort
    for r in reports:
        if isinstance(r["date"], datetime):
            r["date"] = r["date"].date()
    reports.sort(key=lambda x: x["date"], reverse=True)

    # Current bakery balance
    current_balance = BakeryBalance.get_instance().amount

    return render(request, "reports/all_reports.html", {
        "reports": reports,
        "current_balance": current_balance,
    })
