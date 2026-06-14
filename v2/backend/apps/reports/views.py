"""Feature #18 — Reports.

Each dataset is exposed in two forms:
- GET /reports/<name>.xlsx  → streams xlsx download
- GET /reports/data/?type=<name> → JSON for inline rendering

Both accept optional ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD.

Special structured endpoints:
- GET /reports/cos/   → COS breakdown per product (live ingredient prices)
- GET /reports/sofp/  → Financial position snapshot
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import OuterRef, Subquery, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.utils.timezone import get_current_timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import GeneralExpense, KassaAccount, Payment
from apps.inventory.models import Ingredient, Purchase
from apps.orders.models import Order, OrderItem
from apps.production.models import Production
from apps.products.models import Product
from apps.salary.models import SalaryPayment
from apps.shops.models import Shop

from .excel import make_workbook


# ────────────────── helpers ──────────────────
def _parse_range(request):
    p = request.query_params
    return p.get("date_from"), p.get("date_to")


def _xlsx_response(buf, filename: str) -> HttpResponse:
    resp = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _dec(v) -> float:
    return float(v) if v is not None else 0.0


# ────────────────── dataset builders (shared by xlsx + JSON) ──────────────────
def build_payments(date_from=None, date_to=None):
    qs = Payment.objects.select_related("shop", "account", "collected_by").order_by("-received_at")
    if date_from:
        qs = qs.filter(received_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(received_at__date__lte=date_to)

    headers = [
        "Sana", "Do'kon", "Tur", "Valyuta", "Summa", "Skidka",
        "Kassa", "Qabul qiluvchi", "Buyurtma kuni", "Izoh",
    ]
    rows = []
    total_uzs = total_usd = 0.0
    for p in qs:
        amount = _dec(p.amount)
        if p.currency == "UZS":
            total_uzs += amount
        else:
            total_usd += amount
        rows.append([
            timezone.localtime(p.received_at).strftime("%Y-%m-%d %H:%M"),
            p.shop.name,
            p.get_payment_type_display(),
            p.currency,
            amount,
            _dec(p.discount),
            p.account.name,
            p.collected_by.display_name if p.collected_by_id else "",
            p.order_date.strftime("%Y-%m-%d") if p.order_date else "",
            p.note or "",
        ])
    summary = {"total_uzs": total_uzs, "total_usd": total_usd, "count": len(rows)}
    return headers, rows, summary


def build_production(date_from=None, date_to=None, product=None, products=None):
    qs = Production.objects.select_related("product", "nonvoy", "group").order_by("-occurred_at")
    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)
    if products:
        qs = qs.filter(product_id__in=products)
    elif product:
        qs = qs.filter(product_id=product)

    headers = ["Sana", "Mahsulot", "Nonvoy", "Qop", "Dona", "Izoh"]
    rows = []
    meshok = units = 0.0
    for p in qs:
        meshok += _dec(p.meshok_count)
        units += _dec(p.unit_count)
        rows.append([
            timezone.localtime(p.occurred_at).strftime("%Y-%m-%d"),
            p.product.name,
            p.actor_name,
            _dec(p.meshok_count),
            _dec(p.unit_count),
            p.note or "",
        ])
    return headers, rows, {"total_meshok": meshok, "total_units": units, "count": len(rows)}


def build_expenses(date_from=None, date_to=None):
    purchases = Purchase.objects.select_related("ingredient", "account")
    expenses = GeneralExpense.objects.select_related("category", "account")
    if date_from:
        purchases = purchases.filter(occurred_at__date__gte=date_from)
        expenses = expenses.filter(occurred_at__date__gte=date_from)
    if date_to:
        purchases = purchases.filter(occurred_at__date__lte=date_to)
        expenses = expenses.filter(occurred_at__date__lte=date_to)

    headers = ["Sana", "Tur", "Nomi", "Valyuta", "Miqdor", "Kassa", "Izoh"]
    rows = []
    total_uzs = total_usd = 0.0
    for p in purchases:
        amt = _dec(p.total_price)
        if p.currency == "UZS":
            total_uzs += amt
        else:
            total_usd += amt
        rows.append([
            timezone.localtime(p.occurred_at).strftime("%Y-%m-%d"),
            "Xomashyo",
            p.ingredient.name,
            p.currency,
            amt,
            p.account.name,
            p.note or "",
        ])
    for e in expenses:
        amt = _dec(e.amount)
        if e.currency == "UZS":
            total_uzs += amt
        else:
            total_usd += amt
        rows.append([
            timezone.localtime(e.occurred_at).strftime("%Y-%m-%d"),
            e.category.name if e.category_id else "Umumiy xarajat",
            e.title,
            e.currency,
            amt,
            e.account.name,
            e.note or "",
        ])
    rows.sort(key=lambda r: r[0], reverse=True)
    return headers, rows, {"total_uzs": total_uzs, "total_usd": total_usd, "count": len(rows)}


def build_salary(date_from=None, date_to=None):
    qs = SalaryPayment.objects.select_related("user", "account").order_by("-occurred_at")
    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)

    headers = ["Sana", "Xodim", "Tur", "Valyuta", "Miqdor", "Kassa", "Davr", "Izoh"]
    rows = []
    total_uzs = total_usd = 0.0
    for p in qs:
        amt = _dec(p.amount)
        if p.currency == "UZS":
            total_uzs += amt
        else:
            total_usd += amt
        period = ""
        if p.period_start and p.period_end:
            period = f"{p.period_start} → {p.period_end}"
        rows.append([
            timezone.localtime(p.occurred_at).strftime("%Y-%m-%d"),
            p.user.display_name,
            p.get_kind_display(),
            p.currency,
            amt,
            p.account.name,
            period,
            p.note or "",
        ])
    return headers, rows, {"total_uzs": total_uzs, "total_usd": total_usd, "count": len(rows)}


def build_shop_debts():
    shops = Shop.objects.filter(is_archived=False).select_related("region").order_by("name")
    headers = [
        "Do'kon", "Region", "UZS qarz", "UZS limit",
        "USD qarz", "USD limit", "Oshgan?",
    ]
    rows = []
    total_uzs_debt = total_usd_debt = 0.0
    over_count = 0
    for s in shops:
        over = False
        if s.loan_limit_uzs and s.loan_balance_uzs > s.loan_limit_uzs:
            over = True
        if s.loan_limit_usd and s.loan_balance_usd > s.loan_limit_usd:
            over = True
        if over:
            over_count += 1
        total_uzs_debt += _dec(s.loan_balance_uzs)
        total_usd_debt += _dec(s.loan_balance_usd)
        rows.append([
            s.name,
            s.region.name if s.region_id else "",
            _dec(s.loan_balance_uzs),
            _dec(s.loan_limit_uzs),
            _dec(s.loan_balance_usd),
            _dec(s.loan_limit_usd),
            "Ha" if over else "",
        ])
    return headers, rows, {
        "total_uzs_debt": total_uzs_debt,
        "total_usd_debt": total_usd_debt,
        "over_count": over_count,
        "count": len(rows),
    }


def build_orders(date_from=None, date_to=None):
    qs = Order.objects.select_related("shop").prefetch_related("items").order_by("-order_date")
    if date_from:
        qs = qs.filter(order_date__gte=date_from)
    if date_to:
        qs = qs.filter(order_date__lte=date_to)

    headers = [
        "Sana", "Do'kon", "Status", "Prioritet", "Valyuta",
        "Jami summa", "Yetkazilgan summa",
    ]
    rows = []
    total_uzs = total_usd = 0.0
    for o in qs:
        total = sum((i.total_price for i in o.items.all()), Decimal("0"))
        delivered = sum((i.delivered_price for i in o.items.all()), Decimal("0"))
        if o.currency == "UZS":
            total_uzs += float(total)
        else:
            total_usd += float(total)
        rows.append([
            o.order_date.strftime("%Y-%m-%d"),
            o.shop.name,
            o.get_status_display(),
            o.get_priority_display(),
            o.currency,
            float(total),
            float(delivered),
        ])
    return headers, rows, {"total_uzs": total_uzs, "total_usd": total_usd, "count": len(rows)}


# ─────────────────── COS helpers ───────────────────

def _build_price_map() -> dict:
    """Return {ingredient_id: last_unit_price_float} built in a single DB query."""
    last_price_sub = (
        Purchase.objects
        .filter(ingredient=OuterRef("pk"))
        .order_by("-occurred_at")
        .values("unit_price")[:1]
    )
    rows = Ingredient.objects.annotate(last_price=Subquery(last_price_sub)).values("id", "last_price")
    return {r["id"]: float(r["last_price"] or 0) for r in rows}


def _compute_product_cos(product, price_map: dict) -> dict:
    """COS per meshok for a product using last purchase prices."""
    ing_rows = []
    ing_total = 0.0
    missing_prices = []

    for item in product.recipe_items.all():
        price = price_map.get(item.ingredient_id, 0.0)
        qty = float(item.amount_per_meshok)
        cost = qty * price
        ing_total += cost
        # An ingredient with no recorded purchase price silently contributes 0
        # to the cost, understating COS. Flag it so the report can warn.
        if price == 0.0 and qty > 0:
            missing_prices.append(item.ingredient.name)
        ing_rows.append({
            "name": item.ingredient.name,
            "unit": item.ingredient.unit.short,
            "qty": qty,
            "price_per_unit": price,
            "cost": cost,
            "missing_price": price == 0.0 and qty > 0,
        })

    meshok_size = float(product.meshok_size or 160)
    labour = float(product.production_salary_per_unit_uzs) * meshok_size
    cos = round(ing_total + labour, 2)
    sale_price = float(product.default_price_uzs)
    cos_per_unit = round(cos / meshok_size, 2) if meshok_size else 0.0
    margin = round(sale_price - cos_per_unit, 2)

    return {
        "product_id": product.id,
        "product": product.name,
        "meshok_size": meshok_size,
        "sale_price_uzs": sale_price,
        "ingredients": ing_rows,
        "ingredient_total": ing_total,
        "labour": labour,
        "cos_per_meshok": cos,
        "cos_per_unit": cos_per_unit,
        "margin_per_unit": margin,
        "margin_pct": (margin / sale_price * 100) if sale_price else 0.0,
        "missing_prices": missing_prices,
    }


# ─────────────────── Daily P&L builder ───────────────────

def _collect_pnl_data(start, end, tz):
    """Shared data collection for pnl_daily and gross_overall.

    Cost of sales is cash-basis: the actual UZS spent buying ingredients in the
    period (matching the dashboard's cash-basis "net income today"), not a
    production-derived theoretical cost.
    """
    # Cash-basis cost of goods: actual ingredient purchase outflow per day.
    pur_qs = (
        Purchase.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d")
        .annotate(total=Sum("total_price"))
    )
    cos_by_date = {r["d"]: float(r["total"] or 0) for r in pur_qs}

    # Revenue = net delivered (delivered_qty - returned_qty).
    # Using ordered quantity inflates P&L with pending/cancelled orders.
    items_qs = (
        OrderItem.objects
        .filter(order__order_date__gte=start, order__order_date__lte=end, order__currency="UZS")
        .exclude(order__status="cancelled")
        .values("order__order_date", "unit_price", "delivered_quantity", "returned_quantity")
    )
    sales_by_date: dict = {}
    for item in items_qs:
        d = item["order__order_date"]
        net = max(0, item["delivered_quantity"] - item["returned_quantity"])
        sales_by_date[d] = sales_by_date.get(d, 0.0) + float(item["unit_price"]) * net

    exp_qs = (
        GeneralExpense.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d")
        .annotate(total=Sum("amount"))
    )
    exp_by_date = {r["d"]: float(r["total"] or 0) for r in exp_qs}

    sal_qs = (
        SalaryPayment.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d")
        .annotate(total=Sum("amount"))
    )
    sal_by_date = {r["d"]: float(r["total"] or 0) for r in sal_qs}

    # Build per-day tuples for all days in range that have activity
    day_data = []
    t = dict(sales=0.0, cos=0.0, exp=0.0, sal=0.0)
    current = start
    while current <= end:
        sales = sales_by_date.get(current, 0.0)
        cos = cos_by_date.get(current, 0.0)
        exp = exp_by_date.get(current, 0.0)
        sal = sal_by_date.get(current, 0.0)
        if sales or cos or exp or sal:
            day_data.append((current, sales, cos, exp, sal))
        t["sales"] += sales
        t["cos"] += cos
        t["exp"] += exp
        t["sal"] += sal
        current += timedelta(days=1)

    return day_data, t


def build_pnl_daily(date_from=None, date_to=None):
    """Daily P&L: flat rows, one per active day."""
    today = timezone.localdate()
    start = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today.replace(day=1)
    end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    tz = get_current_timezone()

    day_data, t = _collect_pnl_data(start, end, tz)

    headers = ["Sana", "Savdo", "Tan narxi", "Yalpi foyda", "Xarajatlar", "Op. foyda", "Oylik", "Sof foyda"]
    rows = []
    for d, sales, cos, exp, sal in day_data:
        gp = sales - cos
        op = gp - exp
        np_v = op - sal
        rows.append([d.strftime("%Y-%m-%d"), sales, cos, gp, exp, op, sal, np_v])

    gp_t = t["sales"] - t["cos"]
    op_t = gp_t - t["exp"]
    np_t = op_t - t["sal"]
    return headers, rows, {
        "total_sales": t["sales"], "total_cos": t["cos"],
        "total_gross_profit": gp_t, "total_expenses": t["exp"] + t["sal"],
        "total_net_profit": np_t, "count": len(rows),
    }


def build_gross_overall(date_from=None, date_to=None):
    """Weekly P&L summary — one row per ISO-week, plus a period total.

    Deliberately different from build_pnl_daily (which shows every day):
    this gives a compact week-by-week overview suitable for management review.

    Rows have 9 elements: [label, sales, cos, gp, expenses, op_profit, salary, net, row_type]
    row_type: 1=week_row, 2=period_total
    Column order matches Excel: GP → Expenses → Op.profit → Salary → Net
    """
    today = timezone.localdate()
    start = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today.replace(day=1)
    end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    tz = get_current_timezone()

    day_data, t = _collect_pnl_data(start, end, tz)

    headers = ["Hafta", "Savdo", "Tan narxi", "Yalpi foyda", "Xarajatlar", "Op. foyda", "Oylik", "Sof foyda"]
    rows = []

    # Aggregate by ISO week — emit one summary row per week
    current_week = None
    w = dict(sales=0.0, cos=0.0, exp=0.0, sal=0.0)
    week_num = 0
    week_first_day = None

    def _flush_week(wn, first_day, last_day, w):
        wgp = w["sales"] - w["cos"]
        wop = wgp - w["exp"]
        wnet = wop - w["sal"]
        label = f"Hafta {wn}  ({first_day.strftime('%-d %b')} – {last_day.strftime('%-d %b')})"
        return [label, w["sales"], w["cos"], wgp, w["exp"], wop, w["sal"], wnet, 1]

    last_day_seen = None
    for d, sales, cos, exp, sal in day_data:
        iso_week = d.isocalendar()[:2]  # (year, week_number)

        if current_week is None:
            current_week = iso_week
            week_num = 1
            week_first_day = d
        elif iso_week != current_week:
            rows.append(_flush_week(week_num, week_first_day, last_day_seen, w))
            current_week = iso_week
            week_num += 1
            week_first_day = d
            w = dict(sales=0.0, cos=0.0, exp=0.0, sal=0.0)

        w["sales"] += sales; w["cos"] += cos; w["exp"] += exp; w["sal"] += sal
        last_day_seen = d

    # Final week
    if day_data:
        rows.append(_flush_week(week_num, week_first_day, last_day_seen, w))

    # Period total — label adapts to range span
    gp_t = t["sales"] - t["cos"]
    op_t = gp_t - t["exp"]
    np_t = op_t - t["sal"]
    is_single_month = (start.year == end.year and start.month == end.month)
    total_label = "Oy jami" if is_single_month else f"Jami ({start.strftime('%d %b')} – {end.strftime('%d %b')})"
    rows.append([total_label, t["sales"], t["cos"], gp_t, t["exp"], op_t, t["sal"], np_t, 2])

    return headers, rows, {
        "total_sales": t["sales"], "total_cos": t["cos"],
        "total_gross_profit": gp_t, "total_expenses": t["exp"] + t["sal"],
        "total_net_profit": np_t, "count": len([r for r in rows if r[8] == 1]),
    }


# Map of report type → (builder_fn, uses_date_range, sheet_title, filename_prefix)
REPORT_TYPES = {
    "payments":      (build_payments,      True,  "Kirim",              "kirim"),
    "orders":        (build_orders,        True,  "Buyurtmalar",        "buyurtmalar"),
    "production":    (build_production,    True,  "Ishlab chiqarish",   "production"),
    "expenses":      (build_expenses,      True,  "Xarajatlar",         "xarajatlar"),
    "salary":        (build_salary,        True,  "Oylik",              "oylik"),
    "shop_debts":    (build_shop_debts,    False, "Qarzdor do'konlar",  "qarzdor_doconlar"),
    "pnl_daily":     (build_pnl_daily,     True,  "Kunlik P&L",         "pnl_kunlik"),
    "gross_overall": (build_gross_overall, True,  "Umumiy P&L",         "gross_overall"),
}


# ────────────────── JSON endpoint (inline rendering) ──────────────────
class ReportsDataView(APIView):
    """GET /reports/data/?type=<name>[&date_from=&date_to=] — JSON data for inline rendering."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        r_type = request.query_params.get("type")
        if r_type not in REPORT_TYPES:
            return Response(
                {"detail": f"Unknown type. Choices: {list(REPORT_TYPES)}"},
                status=400,
            )
        builder, uses_range, title, _ = REPORT_TYPES[r_type]
        date_from, date_to = _parse_range(request)
        if uses_range:
            extra_kwargs = {}
            if r_type == "production":
                products = request.query_params.getlist("products[]")
                if products:
                    extra_kwargs["products"] = [int(p) for p in products if p.isdigit()]
                else:
                    product = request.query_params.get("product")
                    if product:
                        extra_kwargs["product"] = product
            headers, rows, summary = builder(date_from, date_to, **extra_kwargs)
        else:
            headers, rows, summary = builder()
        return Response({
            "type": r_type,
            "title": title,
            "headers": headers,
            "rows": rows,
            "summary": summary,
        })


# ────────────────── XLSX views ──────────────────
class _BaseXlsxView(APIView):
    permission_classes = [IsAuthenticated]
    report_type: str = ""

    def get(self, request):
        builder, uses_range, title, prefix = REPORT_TYPES[self.report_type]
        date_from, date_to = _parse_range(request)
        if uses_range:
            extra_kwargs = {}
            if self.report_type == "production":
                products = request.query_params.getlist("products[]")
                if products:
                    extra_kwargs["products"] = [int(p) for p in products if p.isdigit()]
                else:
                    product = request.query_params.get("product")
                    if product:
                        extra_kwargs["product"] = product
            headers, rows, _ = builder(date_from, date_to, **extra_kwargs)
        else:
            headers, rows, _ = builder()
        buf = make_workbook(title, headers, rows)
        return _xlsx_response(buf, f"{prefix}_{datetime.now().strftime('%Y%m%d')}.xlsx")


class PaymentsExportView(_BaseXlsxView):
    report_type = "payments"


class OrdersExportView(_BaseXlsxView):
    report_type = "orders"


class ProductionExportView(_BaseXlsxView):
    report_type = "production"


class ExpensesExportView(_BaseXlsxView):
    report_type = "expenses"


class SalaryExportView(_BaseXlsxView):
    report_type = "salary"


class ShopDebtsExportView(_BaseXlsxView):
    report_type = "shop_debts"


class PnlDailyExportView(_BaseXlsxView):
    report_type = "pnl_daily"


class GrossOverallExportView(_BaseXlsxView):
    report_type = "gross_overall"


# ────────────────── Gross Daily detail endpoint ──────────────────
class GrossDailyView(APIView):
    """GET /reports/gross-daily/?date=YYYY-MM-DD

    Per-client × per-product sales cross-tab for a single day,
    plus production batches and P&L summary.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date") or timezone.localdate().isoformat()
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # ── Order items for this date (only delivered, excluding cancelled) ──
        items = (
            OrderItem.objects
            .filter(order__order_date=date, order__currency="UZS")
            .exclude(order__status="cancelled")
            .select_related("order__shop", "product")
            .order_by("order__shop__name", "product__sort_order", "product__name")
        )

        # Build products list and client × product matrix
        products_map = {}   # product_id → {"id", "name"}
        shops_map = {}      # shop_id → {"shop", "cells": {product_id: {qty, price, total}}, "total"}

        for item in items:
            pid = item.product_id
            sid = item.order.shop_id

            # Use net_delivered: delivered - returned (0 for pending/undelivered items)
            net_qty = max(0, item.delivered_quantity - item.returned_quantity)
            if net_qty == 0:
                continue  # Skip items with nothing delivered

            if pid not in products_map:
                products_map[pid] = {"id": pid, "name": item.product.name, "sort": item.product.sort_order}

            if sid not in shops_map:
                shops_map[sid] = {"shop": item.order.shop.name, "cells": {}, "total": 0.0}

            qty = net_qty
            price = float(item.unit_price)
            total = qty * price

            if pid in shops_map[sid]["cells"]:
                shops_map[sid]["cells"][pid]["qty"] += qty
                shops_map[sid]["cells"][pid]["total"] += total
            else:
                shops_map[sid]["cells"][pid] = {"qty": qty, "price": price, "total": total}
            shops_map[sid]["total"] += total

        # Sort products by sort_order then name
        products_list = sorted(products_map.values(), key=lambda p: (p["sort"], p["name"]))

        # Build column totals
        col_totals = {}
        for sd in shops_map.values():
            for pid, cell in sd["cells"].items():
                ct = col_totals.setdefault(pid, {"qty": 0, "total": 0.0})
                ct["qty"] += cell["qty"]
                ct["total"] += cell["total"]

        grand_total_sales = sum(sd["total"] for sd in shops_map.values())

        # Normalise: each client gets a list of cells aligned to products_list
        clients = []
        for sd in sorted(shops_map.values(), key=lambda x: x["shop"]):
            cells = [sd["cells"].get(p["id"], {"qty": 0, "price": 0.0, "total": 0.0}) for p in products_list]
            clients.append({"shop": sd["shop"], "cells": cells, "total": sd["total"]})

        column_totals = [col_totals.get(p["id"], {"qty": 0, "total": 0.0}) for p in products_list]

        # ── Production batches for this day ───────────────────────────────
        price_map = _build_price_map()
        product_objs = (
            Product.objects
            .filter(is_archived=False)
            .prefetch_related("recipe_items__ingredient__unit")
        )
        cos_map = {p.id: _compute_product_cos(p, price_map) for p in product_objs}

        prod_qs = (
            Production.objects
            .filter(occurred_at__date=date)
            .select_related("product")
            .values("product_id", "product__name")
            .annotate(total_meshoks=Sum("meshok_count"))
            .order_by("product__sort_order", "product__name")
        )
        production = []
        total_cos = 0.0
        for pr in prod_qs:
            pid = pr["product_id"]
            meshoks = float(pr["total_meshoks"] or 0)
            cos_info = cos_map.get(pid, {})
            cos_per_meshok = cos_info.get("cos_per_meshok", 0.0)
            cos_total = meshoks * cos_per_meshok
            total_cos += cos_total
            production.append({
                "product": pr["product__name"],
                "meshoks": meshoks,
                "cos_per_meshok": cos_per_meshok,
                "cos_total": cos_total,
            })

        # ── Expenses & salary for this day ────────────────────────────────
        exp_total = float(
            GeneralExpense.objects
            .filter(occurred_at__date=date, currency="UZS")
            .aggregate(t=Sum("amount"))["t"] or 0
        )
        sal_total = float(
            SalaryPayment.objects
            .filter(occurred_at__date=date, currency="UZS")
            .aggregate(t=Sum("amount"))["t"] or 0
        )

        # Cash-basis cost of sales: actual ingredient purchase outflow this day.
        # (The `production` table above still shows theoretical per-product cost
        # as context, but the P&L is cash-basis to match the daily P&L report.)
        cash_cos = float(
            Purchase.objects
            .filter(occurred_at__date=date, currency="UZS")
            .aggregate(t=Sum("total_price"))["t"] or 0
        )

        gp = grand_total_sales - cash_cos
        op = gp - exp_total
        net = op - sal_total

        return Response({
            "date": date.isoformat(),
            "products": [{"id": p["id"], "name": p["name"]} for p in products_list],
            "clients": clients,
            "column_totals": column_totals,
            "grand_total_sales": grand_total_sales,
            "production": production,
            "pnl": {
                "sales": grand_total_sales,
                "cos": cash_cos,
                "gross_profit": gp,
                "expenses": exp_total,
                "salary": sal_total,
                "op_profit": op,
                "net_profit": net,
            },
        })


# ────────────────── COS breakdown endpoint ──────────────────
class CosBreakdownView(APIView):
    """GET /reports/cos/ — COS per product using last ingredient purchase prices."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        price_map = _build_price_map()

        last_price_sub = (
            Purchase.objects
            .filter(ingredient=OuterRef("pk"))
            .order_by("-occurred_at")
            .values("unit_price")[:1]
        )
        last_date_sub = (
            Purchase.objects
            .filter(ingredient=OuterRef("pk"))
            .order_by("-occurred_at")
            .values("occurred_at")[:1]
        )
        ingredients = (
            Ingredient.objects
            .filter(is_archived=False)
            .select_related("unit")
            .annotate(last_price=Subquery(last_price_sub), last_date=Subquery(last_date_sub))
            .order_by("name")
        )
        ingredient_prices = [
            {
                "id": ing.id,
                "name": ing.name,
                "unit": ing.unit.short,
                "stock": float(ing.quantity),
                "last_price": float(ing.last_price or 0),
                "last_date": ing.last_date.date().isoformat() if ing.last_date else None,
            }
            for ing in ingredients
        ]

        products = (
            Product.objects
            .filter(is_archived=False)
            .prefetch_related("recipe_items__ingredient__unit")
            .order_by("sort_order", "name")
        )
        return Response({
            "ingredient_prices": ingredient_prices,
            "products": [_compute_product_cos(p, price_map) for p in products],
        })


# ────────────────── SOFP endpoint ──────────────────
class SofpView(APIView):
    """GET /reports/sofp/ — Statement of financial position (assets snapshot)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        price_map = _build_price_map()

        # Cash — kassa balances
        accounts = list(KassaAccount.objects.all())
        cash_items = [
            {"name": a.name, "uzs": float(a.balance_uzs), "usd": float(a.balance_usd)}
            for a in accounts
        ]
        total_cash_uzs = sum(float(a.balance_uzs) for a in accounts)
        total_cash_usd = sum(float(a.balance_usd) for a in accounts)

        # Receivables — outstanding shop debts (UZS and USD kept separate)
        shops = Shop.objects.filter(is_archived=False).order_by("name")
        recv_items = [
            {"name": s.name, "uzs": float(s.loan_balance_uzs), "usd": float(s.loan_balance_usd)}
            for s in shops
            if s.loan_balance_uzs > 0 or s.loan_balance_usd > 0
        ]
        total_recv_uzs = sum(float(s.loan_balance_uzs) for s in shops)
        total_recv_usd = sum(float(s.loan_balance_usd) for s in shops)

        # Inventory — current stock valued at last purchase price
        ingredients = Ingredient.objects.filter(is_archived=False).select_related("unit")
        inv_items = []
        total_inv = 0.0
        for ing in ingredients:
            qty = float(ing.quantity)
            price = price_map.get(ing.id, 0.0)
            val = qty * price
            total_inv += val
            if qty > 0:
                inv_items.append({
                    "name": ing.name,
                    "unit": ing.unit.short,
                    "qty": qty,
                    "price": price,
                    "value": val,
                })
        inv_items.sort(key=lambda x: x["value"], reverse=True)

        return Response({
            "as_of": timezone.localdate().isoformat(),
            "cash": {"items": cash_items, "total_uzs": total_cash_uzs, "total_usd": total_cash_usd},
            "receivables": {
                "items": recv_items,
                "total_uzs": total_recv_uzs,
                "total_usd": total_recv_usd,
            },
            # Inventory is valued from last purchase price (UZS only).
            "inventory": {"items": inv_items, "total_uzs": total_inv},
            "total_assets_uzs": total_cash_uzs + total_recv_uzs + total_inv,
            "total_assets_usd": total_cash_usd + total_recv_usd,
        })
