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

from django.db.models import OuterRef, Q, Subquery, Sum
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
    # Include archived shops that still carry a balance — archiving a customer
    # must not erase the money they owe (or that we owe them).
    shops = (
        Shop.objects
        .filter(Q(is_archived=False) | ~Q(loan_balance_uzs=0) | ~Q(loan_balance_usd=0))
        .select_related("region")
        .order_by("name")
    )
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
        # Only positive balances are debt; a negative balance is a customer
        # credit (we owe them) and must not reduce the total owed to us.
        total_uzs_debt += max(0.0, _dec(s.loan_balance_uzs))
        total_usd_debt += max(0.0, _dec(s.loan_balance_usd))
        rows.append([
            s.name + (" (arxiv)" if s.is_archived else ""),
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
    # Cancelled orders are voided — exclude them from the report and its totals.
    qs = (
        Order.objects
        .exclude(status="cancelled")
        .select_related("shop")
        .prefetch_related("items")
        .order_by("-order_date")
    )
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
    deliv_uzs = deliv_usd = 0.0
    for o in qs:
        total = sum((i.total_price for i in o.items.all()), Decimal("0"))
        delivered = sum((i.delivered_price for i in o.items.all()), Decimal("0"))
        if o.currency == "UZS":
            total_uzs += float(total)
            deliv_uzs += float(delivered)
        else:
            total_usd += float(total)
            deliv_usd += float(delivered)
        rows.append([
            o.order_date.strftime("%Y-%m-%d"),
            o.shop.name,
            o.get_status_display(),
            o.get_priority_display(),
            o.currency,
            float(total),
            float(delivered),
        ])
    # "Jami summa" = ordered value (order intake); "Yetkazilgan" = delivered
    # value (the real sales figure). Both are surfaced so neither is mistaken
    # for the other.
    return headers, rows, {
        "total_uzs": total_uzs, "total_usd": total_usd,
        "total_delivered_uzs": deliv_uzs, "total_delivered_usd": deliv_usd,
        "count": len(rows),
    }


# ─────────────────── COS helpers ───────────────────

def _build_price_map() -> dict:
    """Return {ingredient_id: unit_price_float}.

    Price source is Ingredient.avg_cost_uzs — the per-unit price entered by hand
    on the Ombor (inventory) page ("Narx (1 birlik)", set via the set-price
    action). This is the authoritative cost used across ALL reports (COS,
    inventory valuation, P&L). We deliberately do NOT use the last purchase
    price: it can be a stray/adjustment value (e.g. a 1 UZS correction) and is
    currency-blind, which silently corrupts every downstream number.
    """
    rows = Ingredient.objects.values("id", "avg_cost_uzs")
    return {r["id"]: float(r["avg_cost_uzs"] or 0) for r in rows}


def _build_labour_map(days: int = 90) -> dict:
    """Return {product_id: production_labour_per_meshok_float}.

    Ish haqi (nonvoy) per meshok = the per-meshok wage of the product's PRIMARY
    producer — the group (or baker) that actually makes most of that product over
    the window. This is the standard/canonical labour cost, so the figure is the
    clean group rate (e.g. Sushka group = 98 000/qop, Non group = 180 000/qop)
    rather than a volume-weighted average that gets diluted (and turned into an
    odd fraction) by the occasional one-off run by a different baker.

    Per-producer per-meshok wage, mirroring the salary app's
    _earned_from_production:
      - per_meshok baker → rate per meshok
      - per_unit baker   → rate × units produced (÷ meshoks)
      - per_product      → Product.production_salary_per_unit_uzs × units
      - group run        → sum of each member's production wage (every member
                           earns their full tariff on the batch)
      - time-based (per_week / fixed_monthly) bakers contribute 0 to unit COS
        (their pay is period overhead, not per-meshok direct labour)

    Runs with no baker AND no group are skipped (unknown labour). A product with
    no attributed runs in the window is absent from the map, and
    _compute_product_cos falls back to the per-product manual rate.
    """
    from datetime import timedelta

    from apps.salary.models import RateType, SalaryRate
    from apps.users.models import EmployeeGroup

    rates = {r.user_id: (r.rate_type, float(r.rate or 0)) for r in SalaryRate.objects.all()}
    group_members = {
        g.id: list(g.members.values_list("id", flat=True))
        for g in EmployeeGroup.objects.prefetch_related("members")
    }

    def _unit_labour(rate_type, rate, meshok, units, psu):
        if rate_type == RateType.PER_MESHOK:
            return meshok * rate
        if rate_type == RateType.PER_UNIT:
            return units * rate
        if rate_type == RateType.PER_PRODUCT:
            return units * psu
        return 0.0  # time-based rates are not per-meshok direct labour

    cutoff = timezone.localdate() - timedelta(days=days)
    # product_id → { producer_key: [labour_sum, meshok_sum] }
    by_producer: dict = {}
    runs = (
        Production.objects
        .filter(occurred_at__date__gte=cutoff)
        .values(
            "product_id", "nonvoy_id", "group_id", "meshok_count", "unit_count",
            "product__production_salary_per_unit_uzs",
        )
    )
    for r in runs:
        meshok = float(r["meshok_count"] or 0)
        units = float(r["unit_count"] or 0)
        psu = float(r["product__production_salary_per_unit_uzs"] or 0)
        if r["nonvoy_id"] and r["nonvoy_id"] in rates:
            key = ("n", r["nonvoy_id"])
            rt, rate = rates[r["nonvoy_id"]]
            labour = _unit_labour(rt, rate, meshok, units, psu)
        elif r["group_id"]:
            key = ("g", r["group_id"])
            labour = sum(
                _unit_labour(*rates[uid], meshok, units, psu)
                for uid in group_members.get(r["group_id"], [])
                if uid in rates
            )
        else:
            continue  # unattributed run — unknown labour
        prod = by_producer.setdefault(r["product_id"], {})
        acc = prod.setdefault(key, [0.0, 0.0])
        acc[0] += labour
        acc[1] += meshok

    labour_map = {}
    for pid, producers in by_producer.items():
        # Primary producer = the one who baked the most meshoks of this product.
        labour_sum, meshok_sum = max(producers.values(), key=lambda v: v[1])
        if meshok_sum:
            labour_map[pid] = round(labour_sum / meshok_sum, 2)
    return labour_map


def _compute_product_cos(product, price_map: dict, labour_map: dict | None = None) -> dict:
    """Full unit cost (tan narxi) per meshok for a product.

    Ingredients are valued at the manual Ombor price (price_map). Labour (ish
    haqi) per meshok comes from labour_map (actual production wages), falling
    back to the per-product manual rate when the product has no recent
    attributed production. Returns both the full cost (ingredients + labour, for
    the COS/pricing tab) and the ingredient-only unit cost (for P&L material
    cost of goods sold, where wages live in the salary expense line).
    """
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
    # Labour per meshok: prefer the data-driven map; else the manual per-unit rate.
    if labour_map is not None and product.id in labour_map:
        labour = round(labour_map[product.id], 2)
    else:
        labour = round(float(product.production_salary_per_unit_uzs) * meshok_size, 2)
    # Communal (gas/electricity) attributed per unit → per meshok, folded into
    # tan narxi alongside materials and labour.
    communal_per_unit = float(product.communal_cost_per_unit_uzs)
    communal = round(communal_per_unit * meshok_size, 2)
    cos = round(ing_total + labour + communal, 2)
    sale_price = float(product.default_price_uzs)
    ingredient_per_unit = round(ing_total / meshok_size, 2) if meshok_size else 0.0
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
        "communal": communal,
        "communal_per_unit": round(communal_per_unit, 2),
        "cos_per_meshok": cos,
        "cos_per_unit": cos_per_unit,
        "ingredient_per_unit": ingredient_per_unit,
        "margin_per_unit": margin,
        "margin_pct": (margin / sale_price * 100) if sale_price else 0.0,
        "missing_prices": missing_prices,
    }


# ─────────────────── Daily P&L builder ───────────────────

def _collect_pnl_data(start, end, tz):
    """Accrual-matched P&L inputs for pnl_daily and gross_overall.

    Revenue = net delivered value (delivered − returned) at the locked unit
        price, bucketed by order date. Cancelled orders excluded.
    Cost of sales = MATERIAL recipe cost of those delivered units, ingredients
        valued at the Ombor manual price (avg_cost_uzs). This matches revenue on
        an accrual basis (cost of what was actually sold), unlike the old
        cash-basis "ingredients bought this day" which swung wildly with
        purchase timing. Returned as the material component only; callers add the
        nonvoy production wage bucket below to get the displayed Tan narxi.
    Salary is split into two buckets, both EXCLUDING advances (a prepayment /
        employee receivable, not a period expense) and with deductions subtracted:
        - prod_sal: nonvoy (baker) wages = direct production labour, folded into
          Tan narxi so gross profit reflects the true cost of making the goods.
        - other_sal: all other roles = period overhead, kept on the Oylik line.
    """
    # Material + communal cost per unit for every product: materials at the manual
    # Ombor price, plus the per-unit communal (gas/electricity) rate. Both are
    # folded into Tan narxi (COGS); nonvoy labour is added separately below.
    price_map = _build_price_map()
    mat_per_unit = {}
    for p in Product.objects.prefetch_related("recipe_items__ingredient__unit"):
        info = _compute_product_cos(p, price_map)
        mat_per_unit[p.id] = info["ingredient_per_unit"] + info["communal_per_unit"]

    # Revenue + material COGS from net-delivered order items (accrual, matched).
    items_qs = (
        OrderItem.objects
        .filter(order__order_date__gte=start, order__order_date__lte=end, order__currency="UZS")
        .exclude(order__status="cancelled")
        .values("order__order_date", "product_id", "unit_price", "delivered_quantity", "returned_quantity")
    )
    sales_by_date: dict = {}
    cos_by_date: dict = {}
    for item in items_qs:
        net = max(0, item["delivered_quantity"] - item["returned_quantity"])
        if net == 0:
            continue
        d = item["order__order_date"]
        sales_by_date[d] = sales_by_date.get(d, 0.0) + float(item["unit_price"]) * net
        cos_by_date[d] = cos_by_date.get(d, 0.0) + mat_per_unit.get(item["product_id"], 0.0) * net

    # Expenses — categories flagged include_in_pnl=False are left out of the P&L.
    exp_qs = (
        GeneralExpense.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
        .exclude(category__include_in_pnl=False)
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d")
        .annotate(total=Sum("amount"))
    )
    exp_by_date = {r["d"]: float(r["total"] or 0) for r in exp_qs}

    # Salary line: real labour cost. Advances are prepayments (excluded);
    # deductions reduce the expense (subtracted). Split by role: NONVOY (baker)
    # wages are DIRECT PRODUCTION labour, so they fold into Tan narxi (cost of
    # goods) — matching the standalone Tan narxi report, which already prices in
    # nonvoy pay. Every other role (manager, driver, accountant) is period
    # overhead and stays on the separate Oylik line. Each payment lands in
    # exactly one bucket, so nothing is double-counted and Sof foyda is unchanged.
    sal_rows = (
        SalaryPayment.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
        .exclude(kind="advance")
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d", "kind", "user__role")
        .annotate(total=Sum("amount"))
    )
    prod_sal_by_date: dict = {}   # nonvoy → Tan narxi (cost of goods)
    other_sal_by_date: dict = {}  # everyone else → Oylik line
    for r in sal_rows:
        amt = float(r["total"] or 0)
        if r["kind"] == "deduction":
            amt = -amt
        bucket = prod_sal_by_date if r["user__role"] == "nonvoy" else other_sal_by_date
        bucket[r["d"]] = bucket.get(r["d"], 0.0) + amt

    # Build per-day tuples for all days in range that have activity
    day_data = []
    t = dict(sales=0.0, cos=0.0, exp=0.0, prod_sal=0.0, other_sal=0.0)
    current = start
    while current <= end:
        sales = sales_by_date.get(current, 0.0)
        cos = cos_by_date.get(current, 0.0)
        exp = exp_by_date.get(current, 0.0)
        prod_sal = prod_sal_by_date.get(current, 0.0)
        other_sal = other_sal_by_date.get(current, 0.0)
        if sales or cos or exp or prod_sal or other_sal:
            day_data.append((current, sales, cos, exp, prod_sal, other_sal))
        t["sales"] += sales
        t["cos"] += cos
        t["exp"] += exp
        t["prod_sal"] += prod_sal
        t["other_sal"] += other_sal
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
    for d, sales, mat_cos, exp, prod_sal, other_sal in day_data:
        cos = mat_cos + prod_sal          # Tan narxi = materials + nonvoy (production) pay
        gp = sales - cos
        op = gp - exp
        np_v = op - other_sal
        rows.append([d.strftime("%Y-%m-%d"), sales, cos, gp, exp, op, other_sal, np_v])

    cos_t = t["cos"] + t["prod_sal"]
    gp_t = t["sales"] - cos_t
    op_t = gp_t - t["exp"]
    np_t = op_t - t["other_sal"]
    return headers, rows, {
        "total_sales": t["sales"], "total_cos": cos_t,
        "total_gross_profit": gp_t, "total_expenses": t["exp"] + t["other_sal"],
        "total_net_profit": np_t, "count": len(rows),
    }


def build_gross_overall(date_from=None, date_to=None):
    """Weekly P&L summary — one row per ISO-week, plus a period total.

    Deliberately different from build_pnl_daily (which shows every day):
    this gives a compact week-by-week overview suitable for management review.

    Rows have 11 elements: [label, sales, cos, gp, expenses, op_profit, salary,
    net, row_type, range_start_iso, range_end_iso]
    row_type: 1=week_row, 2=period_total. The trailing date range powers the
    frontend drill-down (click a cell → detail for that week). Columns beyond the
    8 headers are hidden in the table and stripped from the Excel export.
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
    w = dict(sales=0.0, cos=0.0, exp=0.0, prod_sal=0.0, other_sal=0.0)
    week_num = 0
    week_first_day = None

    def _flush_week(wn, first_day, last_day, w):
        cos = w["cos"] + w["prod_sal"]          # Tan narxi = materials + nonvoy pay
        wgp = w["sales"] - cos
        wop = wgp - w["exp"]
        wnet = wop - w["other_sal"]
        label = f"Hafta {wn}  ({first_day.strftime('%-d %b')} – {last_day.strftime('%-d %b')})"
        return [label, w["sales"], cos, wgp, w["exp"], wop, w["other_sal"], wnet, 1,
                first_day.isoformat(), last_day.isoformat()]

    last_day_seen = None
    for d, sales, mat_cos, exp, prod_sal, other_sal in day_data:
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
            w = dict(sales=0.0, cos=0.0, exp=0.0, prod_sal=0.0, other_sal=0.0)

        w["sales"] += sales; w["cos"] += mat_cos; w["exp"] += exp
        w["prod_sal"] += prod_sal; w["other_sal"] += other_sal
        last_day_seen = d

    # Final week
    if day_data:
        rows.append(_flush_week(week_num, week_first_day, last_day_seen, w))

    # Period total — label adapts to range span
    cos_t = t["cos"] + t["prod_sal"]
    gp_t = t["sales"] - cos_t
    op_t = gp_t - t["exp"]
    np_t = op_t - t["other_sal"]
    is_single_month = (start.year == end.year and start.month == end.month)
    total_label = "Oy jami" if is_single_month else f"Jami ({start.strftime('%d %b')} – {end.strftime('%d %b')})"
    rows.append([total_label, t["sales"], cos_t, gp_t, t["exp"], op_t, t["other_sal"], np_t, 2,
                 start.isoformat(), end.isoformat()])

    return headers, rows, {
        "total_sales": t["sales"], "total_cos": cos_t,
        "total_gross_profit": gp_t, "total_expenses": t["exp"] + t["other_sal"],
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

        # ── Cost maps (shared by cost-of-sales + production table) ──────────
        price_map = _build_price_map()
        labour_map = _build_labour_map()
        product_objs = (
            Product.objects
            .filter(is_archived=False)
            .prefetch_related("recipe_items__ingredient__unit")
        )
        cos_map = {p.id: _compute_product_cos(p, price_map, labour_map) for p in product_objs}

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
        cost_of_sales = 0.0  # material recipe cost of goods delivered today

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
            _cinfo = cos_map.get(pid, {})
            cost_of_sales += (
                _cinfo.get("ingredient_per_unit", 0.0) + _cinfo.get("communal_per_unit", 0.0)
            ) * net_qty

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
        prod_qs = (
            Production.objects
            .filter(occurred_at__date=date)
            .select_related("product")
            .values("product_id", "product__name")
            .annotate(total_meshoks=Sum("meshok_count"))
            .order_by("product__sort_order", "product__name")
        )
        # Production table shows cost of goods PRODUCED (full tan narxi incl.
        # labour). Its total is a separate figure from the P&L cost of goods
        # SOLD below — the two measure different things, but each is internally
        # consistent (rows sum to their own total).
        production = []
        production_cos_total = 0.0
        for pr in prod_qs:
            pid = pr["product_id"]
            meshoks = float(pr["total_meshoks"] or 0)
            cos_info = cos_map.get(pid, {})
            cos_per_meshok = cos_info.get("cos_per_meshok", 0.0)
            cos_total = meshoks * cos_per_meshok
            production_cos_total += cos_total
            production.append({
                "product": pr["product__name"],
                "meshoks": meshoks,
                "cos_per_meshok": cos_per_meshok,
                "cos_total": cos_total,
            })

        # ── Expenses & salary for this day ────────────────────────────────
        # Categories flagged include_in_pnl=False are left out of the P&L.
        exp_total = float(
            GeneralExpense.objects
            .filter(occurred_at__date=date, currency="UZS")
            .exclude(category__include_in_pnl=False)
            .aggregate(t=Sum("amount"))["t"] or 0
        )
        # Salary: exclude advances (prepayments); subtract deductions. Split by
        # role — nonvoy (production) pay folds into Tan narxi below; the rest is
        # the Oylik line — mirroring the P&L tables.
        prod_sal_total = 0.0
        other_sal_total = 0.0
        for r in (
            SalaryPayment.objects
            .filter(occurred_at__date=date, currency="UZS")
            .exclude(kind="advance")
            .values("kind", "user__role")
            .annotate(t=Sum("amount"))
        ):
            amt = float(r["t"] or 0)
            if r["kind"] == "deduction":
                amt = -amt
            if r["user__role"] == "nonvoy":
                prod_sal_total += amt
            else:
                other_sal_total += amt

        # Tan narxi = MATERIAL recipe cost of goods delivered today (accrual,
        # matched to sales) PLUS today's nonvoy (production) wages — the direct
        # cost of making the goods. Remaining wages sit on the Oylik line below.
        cos_display = cost_of_sales + prod_sal_total
        gp = grand_total_sales - cos_display
        op = gp - exp_total
        net = op - other_sal_total

        return Response({
            "date": date.isoformat(),
            "products": [{"id": p["id"], "name": p["name"]} for p in products_list],
            "clients": clients,
            "column_totals": column_totals,
            "grand_total_sales": grand_total_sales,
            "production": production,
            "production_cos_total": production_cos_total,
            "pnl": {
                "sales": grand_total_sales,
                "cos": cos_display,
                "cos_materials": cost_of_sales,
                "production_salary": prod_sal_total,
                "gross_profit": gp,
                "expenses": exp_total,
                "salary": other_sal_total,
                "op_profit": op,
                "net_profit": net,
            },
        })


# ────────────────── P&L detail (drill-down) endpoint ──────────────────
class PnlDetailView(APIView):
    """GET /reports/pnl-detail/?date_from=&date_to=

    Line-item breakdown of every P&L metric for a date range — powers the Gross
    Overall drill-down (click a cell → see exactly what makes up that number).
    Uses the same accrual basis as the P&L: material COGS on net-delivered goods,
    salary excluding advances with deductions subtracted.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if not date_from or not date_to:
            return Response({"detail": "date_from and date_to are required."}, status=400)
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d").date()
            end = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date. Use YYYY-MM-DD."}, status=400)

        price_map = _build_price_map()
        ing_per_unit, communal_per_unit, names = {}, {}, {}
        for p in Product.objects.prefetch_related("recipe_items__ingredient__unit"):
            info = _compute_product_cos(p, price_map)
            ing_per_unit[p.id] = info["ingredient_per_unit"]
            communal_per_unit[p.id] = info["communal_per_unit"]
            names[p.id] = p.name

        # Sales + material/communal COGS by product (net delivered, cancelled excluded).
        items = (
            OrderItem.objects
            .filter(order__order_date__gte=start, order__order_date__lte=end, order__currency="UZS")
            .exclude(order__status="cancelled")
            .values("product_id", "unit_price", "delivered_quantity", "returned_quantity")
        )
        sales_by_p, cos_by_p, communal_by_p, qty_by_p = {}, {}, {}, {}
        for it in items:
            net = max(0, it["delivered_quantity"] - it["returned_quantity"])
            if net == 0:
                continue
            pid = it["product_id"]
            sales_by_p[pid] = sales_by_p.get(pid, 0.0) + float(it["unit_price"]) * net
            cos_by_p[pid] = cos_by_p.get(pid, 0.0) + ing_per_unit.get(pid, 0.0) * net
            communal_by_p[pid] = communal_by_p.get(pid, 0.0) + communal_per_unit.get(pid, 0.0) * net
            qty_by_p[pid] = qty_by_p.get(pid, 0) + net
        sales_items = sorted(
            [{"name": names.get(pid, "?"), "qty": qty_by_p[pid], "amount": sales_by_p[pid]}
             for pid in sales_by_p],
            key=lambda x: -x["amount"],
        )
        cos_items = sorted(
            [{"name": names.get(pid, "?"), "qty": qty_by_p[pid],
              "unit_cost": ing_per_unit.get(pid, 0.0), "amount": cos_by_p[pid]}
             for pid in cos_by_p],
            key=lambda x: -x["amount"],
        )
        communal_items = sorted(
            [{"name": names.get(pid, "?"), "qty": qty_by_p[pid],
              "unit_cost": communal_per_unit.get(pid, 0.0), "amount": communal_by_p[pid]}
             for pid in communal_by_p if communal_by_p[pid] > 0],
            key=lambda x: -x["amount"],
        )
        total_sales = sum(sales_by_p.values())
        total_cos = sum(cos_by_p.values())
        total_communal = sum(communal_by_p.values())

        # Expenses — line items (categories flagged include_in_pnl=False excluded).
        exp_qs = (
            GeneralExpense.objects
            .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
            .exclude(category__include_in_pnl=False)
            .select_related("category").order_by("-occurred_at")
        )
        exp_items = [{
            "date": timezone.localtime(e.occurred_at).strftime("%Y-%m-%d"),
            "title": e.title,
            "category": e.category.name if e.category_id else "—",
            "amount": _dec(e.amount),
        } for e in exp_qs]
        total_exp = sum(i["amount"] for i in exp_items)

        # Salary — line items (advances excluded, deductions subtracted). Split by
        # role, mirroring _collect_pnl_data so the modal reconciles with the
        # tables: nonvoy (production) pay folds into Tan narxi (cost of goods),
        # every other role stays on the Oylik line.
        sal_qs = (
            SalaryPayment.objects
            .filter(occurred_at__date__gte=start, occurred_at__date__lte=end, currency="UZS")
            .exclude(kind="advance").select_related("user").order_by("-occurred_at")
        )
        prod_sal_items, other_sal_items = [], []
        total_prod_sal = 0.0
        total_other_sal = 0.0
        for s in sal_qs:
            amt = _dec(s.amount)
            if s.kind == "deduction":
                amt = -amt
            row = {
                "date": timezone.localtime(s.occurred_at).strftime("%Y-%m-%d"),
                "user": s.user.display_name,
                "kind": s.get_kind_display(),
                "amount": amt,
            }
            if s.user.role == "nonvoy":
                total_prod_sal += amt
                prod_sal_items.append(row)
            else:
                total_other_sal += amt
                other_sal_items.append(row)

        # Tan narxi = materials + communal (gas/electricity) + production pay.
        tan = total_cos + total_communal + total_prod_sal
        gp = total_sales - tan
        op = gp - total_exp
        net = op - total_other_sal
        return Response({
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "sales": {"total": total_sales, "items": sales_items},
            "cos": {
                "total": tan,
                "materials_total": total_cos,
                "items": cos_items,
                "communal_total": total_communal,
                "communal_items": communal_items,
                "salary_total": total_prod_sal,
                "salary_items": prod_sal_items,
            },
            "expenses": {"total": total_exp, "items": exp_items},
            "salary": {"total": total_other_sal, "items": other_sal_items},
            "gross_profit": gp,
            "op_profit": op,
            "net_profit": net,
        })


# ────────────────── COS breakdown endpoint ──────────────────
class CosBreakdownView(APIView):
    """GET /reports/cos/ — COS per product using last ingredient purchase prices."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        price_map = _build_price_map()
        labour_map = _build_labour_map()

        # Reference table shows the price actually used in costing — the manual
        # Ombor price (avg_cost_uzs) — plus the last purchase date for context.
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
            .annotate(last_date=Subquery(last_date_sub))
            .order_by("name")
        )
        ingredient_prices = [
            {
                "id": ing.id,
                "name": ing.name,
                "unit": ing.unit.short,
                "stock": float(ing.quantity),
                "price": float(ing.avg_cost_uzs or 0),
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
            "products": [_compute_product_cos(p, price_map, labour_map) for p in products],
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

        # Receivables (asset) = shops that OWE us (positive balance). Credits
        # (negative balance = we owe the shop) are a liability, shown separately
        # so items always reconcile to the total. Archived shops with a balance
        # are included — archiving must not erase money owed.
        shops = (
            Shop.objects
            .filter(Q(is_archived=False) | ~Q(loan_balance_uzs=0) | ~Q(loan_balance_usd=0))
            .order_by("name")
        )
        recv_items = []
        credit_items = []  # customer prepayments / credits (liabilities)
        total_recv_uzs = total_recv_usd = 0.0
        total_credit_uzs = total_credit_usd = 0.0
        for s in shops:
            bal_uzs = float(s.loan_balance_uzs)
            bal_usd = float(s.loan_balance_usd)
            name = s.name + (" (arxiv)" if s.is_archived else "")
            if bal_uzs > 0 or bal_usd > 0:
                recv_items.append({"name": name, "uzs": max(0.0, bal_uzs), "usd": max(0.0, bal_usd)})
            total_recv_uzs += max(0.0, bal_uzs)
            total_recv_usd += max(0.0, bal_usd)
            if bal_uzs < 0 or bal_usd < 0:
                credit_items.append({"name": name, "uzs": max(0.0, -bal_uzs), "usd": max(0.0, -bal_usd)})
            total_credit_uzs += max(0.0, -bal_uzs)
            total_credit_usd += max(0.0, -bal_usd)

        # Inventory — current stock valued at the manual Ombor price (avg_cost_uzs)
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
            # Inventory is valued from the manual Ombor price (avg_cost_uzs, UZS only).
            "inventory": {"items": inv_items, "total_uzs": total_inv},
            # Liabilities — customer credits (shops that overpaid / prepaid).
            "liabilities": {
                "customer_credits": {
                    "items": credit_items,
                    "total_uzs": total_credit_uzs,
                    "total_usd": total_credit_usd,
                },
                "total_uzs": total_credit_uzs,
                "total_usd": total_credit_usd,
            },
            "total_assets_uzs": total_cash_uzs + total_recv_uzs + total_inv,
            "total_assets_usd": total_cash_usd + total_recv_usd,
            # Net worth after subtracting liabilities (a simple equity proxy).
            "net_worth_uzs": total_cash_uzs + total_recv_uzs + total_inv - total_credit_uzs,
            "net_worth_usd": total_cash_usd + total_recv_usd - total_credit_usd,
        })
