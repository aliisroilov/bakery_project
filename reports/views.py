from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, FloatField
from orders.models import OrderItem
from datetime import datetime
from django.contrib import messages
from .forms import CategoryForm, PurchaseForm
from orders.models import OrderItem
from .models import Purchase, Category
from dashboard.models import LoanRepayment
from shops.models import Shop


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
    reports = []

    # ---------------- Sales (Приход) ----------------
    for item in OrderItem.objects.select_related("order__shop", "product"):
        reports.append({
            "date": item.order.created_at.date(),
            "category": "Приход",
            "description": f"Sotuv - {item.product.name}",
            "counterparty": item.order.shop.name,
            "income": float(item.total_price),
            "expense": None,
        })

    # ---------------- Purchases (Расход) ----------------
    for p in Purchase.objects.select_related("category"):
        reports.append({
            "date": p.purchase_date,
            "category": "Расход",
            "description": f"Xarid - {p.item_name}",
            "counterparty": p.category.name,
            "income": None,
            "expense": float(p.unit_price),
        })

    # ---------------- Loan Repayments (Приход) ----------------
    for r in LoanRepayment.objects.select_related("shop"):
        reports.append({
            "date": r.date.date(),
            "category": "Приход",
            "description": "Qarz to‘lovi",
            "counterparty": r.shop.name,
            "income": float(r.amount),
            "expense": None,
        })

    # ---------------- Sort by Date ----------------
    reports = sorted(reports, key=lambda x: x["date"])

    # ---------------- Running Balance ----------------
    balance = 0
    for r in reports:
        if r["income"]:
            balance += r["income"]
        if r["expense"]:
            balance -= r["expense"]
        r["balance"] = balance

    return render(request, "reports/all_reports.html", {
        "reports": reports
    })