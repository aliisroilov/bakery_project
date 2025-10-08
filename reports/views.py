from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, FloatField
from orders.models import OrderItem
from datetime import datetime
from django.contrib import messages
from .forms import CategoryForm, PurchaseForm
from orders.models import OrderItem
from .models import Purchase, Category, BakeryBalance
from dashboard.models import LoanRepayment, Payment
from shops.models import Shop
from decimal import Decimal
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

@manager_or_admin_required
def sales_report(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    order_items = OrderItem.objects.select_related('product', 'order')

    if start_date and end_date:
        order_items = order_items.filter(
            order__created_at__date__range=[start_date, end_date]
        )

    # Aggregate total sales
    total_sales = order_items.aggregate(total=Sum(F('unit_price') * F('quantity')))['total'] or 0

    # Product-wise sales
    product_sales = order_items.values('product__name').annotate(
        quantity_sold=Sum('quantity'),
        revenue=Sum(F('unit_price') * F('quantity'))
    ).order_by('-revenue')

    context = {
        'report_title': 'Sales Report',
        'total': total_sales,
        'total_label': 'Total Sales',
        'product_sales': product_sales,
        'start_date': start_date,
        'end_date': end_date,
        'show_filter': True,
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
        category = p.category.name
        if category not in purchases_by_category:
            purchases_by_category[category] = []
        purchases_by_category[category].append(p)

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

    # Ma'lumotlarni olish
    purchases = Purchase.objects.all()
    repayments = LoanRepayment.objects.all()
    payments = Payment.objects.filter(payment_type="collection")

    # Faqat tasdiqlangan yoki yetkazilgan buyurtmalarni olish
    delivered_items = OrderItem.objects.select_related("order", "product", "order__shop") \
                                       .filter(order__status__in=["Delivered", "confirmed"])

    # Sana bo‘yicha filtrlash
    if start_date:
        purchases = purchases.filter(purchase_date__gte=start_date)
        repayments = repayments.filter(date__gte=start_date)
        payments = payments.filter(date__gte=start_date)
        delivered_items = delivered_items.filter(order__created_at__date__gte=start_date)

    if end_date:
        purchases = purchases.filter(purchase_date__lte=end_date)
        repayments = repayments.filter(date__lte=end_date)
        payments = payments.filter(date__lte=end_date)
        delivered_items = delivered_items.filter(order__created_at__date__lte=end_date)

    # Barcha hisobot yozuvlarini jamlash
    reports = []

    # === Xaridlar (Purchases) ===
    for p in purchases:
        reports.append({
            "date": p.purchase_date,
            "category": "Xarid",
            "description": p.notes or p.item_name or "Mahsulot xaridi",
            "counterparty": "-",
            "income": None,
            "expense": p.unit_price or Decimal("0")
        })

    # === Qarz to‘lovlari (Loan repayments) ===
    for r in repayments:
        reports.append({
            "date": r.date,
            "category": "Qarz to‘lovi",
            "description": f"{r.shop.name} dan to‘lov",
            "counterparty": r.shop.name,
            "income": r.amount or Decimal("0"),
            "expense": None
        })

    # === To‘lov yig‘imlari (Payment collections) ===
    for pay in payments:
        reports.append({
            "date": pay.date,
            "category": "To‘lov yig‘imi",
            "description": f"{pay.shop.name} dan to‘lov",
            "counterparty": pay.shop.name,
            "income": pay.amount or Decimal("0"),
            "expense": None
        })

    # === Sotuvlar (Sales) — faqat tasdiqlangan buyurtmalardan ===
    for item in delivered_items:
        reports.append({
            "date": item.order.created_at.date() if isinstance(item.order.created_at, datetime) else item.order.created_at,
            "category": "Sotuv",
            "description": f"{item.product.name} x {item.delivered_quantity}",
            "counterparty": item.order.shop.name,
            "income": item.unit_price * item.delivered_quantity,
            "expense": None
        })

    # Sana formatlarini bir xil qilish
    for r in reports:
        if isinstance(r["date"], datetime):
            r["date"] = r["date"].date()

    # Sana bo‘yicha tartiblash
    reports.sort(key=lambda x: x["date"])

    # Hozirgi balansni olish
    current_balance = BakeryBalance.get_instance().amount

    # Hisobot sahifasini qaytarish
    return render(request, "reports/all_reports.html", {
        "reports": reports,
        "current_balance": current_balance,
    })