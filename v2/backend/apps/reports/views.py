"""Feature #18 — Reports.

Each dataset is exposed in two forms:
- GET /reports/<name>.xlsx → streams xlsx download
- GET /reports/data/?type=<name> → JSON for inline rendering

Both accept optional ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD.
"""
from datetime import datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finance.models import GeneralExpense, Payment
from apps.inventory.models import Purchase
from apps.orders.models import Order
from apps.production.models import Production
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


def build_production(date_from=None, date_to=None):
    qs = Production.objects.select_related("product", "nonvoy").order_by("-occurred_at")
    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)

    headers = ["Sana", "Mahsulot", "Nonvoy", "Qop", "Dona", "Izoh"]
    rows = []
    meshok = units = 0.0
    for p in qs:
        meshok += _dec(p.meshok_count)
        units += _dec(p.unit_count)
        rows.append([
            timezone.localtime(p.occurred_at).strftime("%Y-%m-%d"),
            p.product.name,
            p.nonvoy.display_name,
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


# Map of report type -> (builder_fn, uses_date_range, sheet_title, filename_prefix)
REPORT_TYPES = {
    "payments":   (build_payments,   True,  "Kirim",           "kirim"),
    "orders":     (build_orders,     True,  "Buyurtmalar",     "buyurtmalar"),
    "production": (build_production, True,  "Ishlab chiqarish", "production"),
    "expenses":   (build_expenses,   True,  "Xarajatlar",      "xarajatlar"),
    "salary":     (build_salary,     True,  "Oylik",           "oylik"),
    "shop_debts": (build_shop_debts, False, "Qarzdor do'konlar", "qarzdor_doconlar"),
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
            headers, rows, summary = builder(date_from, date_to)
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
            headers, rows, _ = builder(date_from, date_to)
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
