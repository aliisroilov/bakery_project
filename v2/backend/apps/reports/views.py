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

from apps.core.money import to_uzs, uzs_amount_expr
from apps.finance.models import GeneralExpense, KassaAccount, Payment
from apps.inventory.models import Ingredient, Purchase
from apps.orders.models import Order, OrderItem
from apps.production.models import InventoryRevisionReport, Production
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


def _uzs(amount, currency, rate=None) -> float:
    """Row amount restated in UZS — USD rows converted at their booked rate.

    Hisobotlar is a single-currency (UZS) statement: leaving USD rows out of the
    sums, as the reports used to, silently understated every expense line.
    """
    return float(to_uzs(amount, currency, rate))


def _rate_cell(currency, rate):
    """Kurs column value — blank for UZS rows, the applied rate for USD rows."""
    if currency != "USD":
        return ""
    from apps.core.money import effective_rate

    return float(effective_rate(rate))


# ────────────────── dataset builders (shared by xlsx + JSON) ──────────────────
def build_payments(date_from=None, date_to=None):
    qs = Payment.objects.select_related("shop", "account", "collected_by").order_by("-received_at")
    if date_from:
        qs = qs.filter(received_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(received_at__date__lte=date_to)

    headers = [
        "Sana", "Do'kon", "Tur", "Valyuta", "Summa", "Skidka",
        "Kurs", "UZS ekvivalent",
        "Kassa", "Qabul qiluvchi", "Buyurtma kuni", "Izoh",
    ]
    rows = []
    total_uzs = total_usd = 0.0
    total_eq = 0.0
    for p in qs:
        amount = _dec(p.amount)
        if p.currency == "UZS":
            total_uzs += amount
        else:
            total_usd += amount
        eq = _uzs(p.amount, p.currency, p.exchange_rate)
        total_eq += eq
        rows.append([
            timezone.localtime(p.received_at).strftime("%Y-%m-%d %H:%M"),
            p.shop.name,
            p.get_payment_type_display(),
            p.currency,
            amount,
            _dec(p.discount),
            _rate_cell(p.currency, p.exchange_rate),
            eq,
            p.account.name,
            p.collected_by.display_name if p.collected_by_id else "",
            p.order_date.strftime("%Y-%m-%d") if p.order_date else "",
            p.note or "",
        ])
    summary = {
        "total_uzs": total_uzs, "total_usd": total_usd,
        "total_uzs_equivalent": total_eq, "count": len(rows),
    }
    return headers, rows, summary


def build_production(date_from=None, date_to=None, product=None, products=None):
    qs = (
        Production.objects
        .select_related("product", "nonvoy", "group")
        # actor_name lists the whole ad-hoc crew for individuals-attributed runs.
        .prefetch_related("individuals")
        .order_by("-occurred_at")
    )
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

    # "UZS ekvivalent" restates USD rows at the rate they were booked at, so the
    # footer totals one comparable number instead of two currencies that can't
    # be added. UZS rows pass through unchanged.
    headers = [
        "Sana", "Tur", "Nomi", "Valyuta", "Miqdor",
        "Kurs", "UZS ekvivalent", "Kassa", "Izoh",
    ]
    rows = []
    total_uzs = total_usd = 0.0
    total_eq = 0.0
    for p in purchases:
        amt = _dec(p.total_price)
        if p.currency == "UZS":
            total_uzs += amt
        else:
            total_usd += amt
        eq = _uzs(p.total_price, p.currency, p.exchange_rate)
        total_eq += eq
        rows.append([
            timezone.localtime(p.occurred_at).strftime("%Y-%m-%d"),
            "Xomashyo",
            p.ingredient.name,
            p.currency,
            amt,
            _rate_cell(p.currency, p.exchange_rate),
            eq,
            p.account.name,
            p.note or "",
        ])
    for e in expenses:
        amt = _dec(e.amount)
        if e.currency == "UZS":
            total_uzs += amt
        else:
            total_usd += amt
        eq = _uzs(e.amount, e.currency, e.exchange_rate)
        total_eq += eq
        rows.append([
            timezone.localtime(e.occurred_at).strftime("%Y-%m-%d"),
            e.category.name if e.category_id else "Umumiy xarajat",
            e.title,
            e.currency,
            amt,
            _rate_cell(e.currency, e.exchange_rate),
            eq,
            e.account.name,
            e.note or "",
        ])
    rows.sort(key=lambda r: r[0], reverse=True)
    return headers, rows, {
        "total_uzs": total_uzs, "total_usd": total_usd,
        "total_uzs_equivalent": total_eq, "count": len(rows),
    }


def build_salary(date_from=None, date_to=None):
    qs = SalaryPayment.objects.select_related("user", "account").order_by("-occurred_at")
    if date_from:
        qs = qs.filter(occurred_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__date__lte=date_to)

    headers = [
        "Sana", "Xodim", "Tur", "Valyuta", "Miqdor",
        "Kurs", "UZS ekvivalent", "Kassa", "Davr", "Izoh",
    ]
    rows = []
    total_uzs = total_usd = 0.0
    total_eq = 0.0
    for p in qs:
        amt = _dec(p.amount)
        if p.currency == "UZS":
            total_uzs += amt
        else:
            total_usd += amt
        eq = _uzs(p.amount, p.currency, p.exchange_rate)
        total_eq += eq
        period = ""
        if p.period_start and p.period_end:
            period = f"{p.period_start} → {p.period_end}"
        rows.append([
            timezone.localtime(p.occurred_at).strftime("%Y-%m-%d"),
            p.user.display_name,
            p.get_kind_display(),
            p.currency,
            amt,
            _rate_cell(p.currency, p.exchange_rate),
            eq,
            p.account.name,
            period,
            p.note or "",
        ])
    return headers, rows, {
        "total_uzs": total_uzs, "total_usd": total_usd,
        "total_uzs_equivalent": total_eq, "count": len(rows),
    }


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
      - per_product      → this worker's OWN qop rate for that product
                           (UserProductRate), 0 when they have none configured
      - group run        → sum of each member's production wage (every member
                           earns their full tariff on the batch)
      - ad-hoc crew run  → same as a group run, summed over the bakers ticked on
                           that run; identical crews count as one producer
      - time-based (per_week / fixed_monthly) bakers contribute 0 to unit COS
        (their pay is period overhead, not per-meshok direct labour)

    Runs with no baker, no group AND no ad-hoc crew are skipped (unknown labour).
    A product with no attributed runs in the window is absent from the map, and
    _compute_product_cos falls back to the per-product manual rate.
    """
    from datetime import timedelta

    from apps.salary.models import RateType, SalaryRate, UserProductRate
    from apps.users.models import EmployeeGroup

    rates = {r.user_id: (r.rate_type, float(r.rate or 0)) for r in SalaryRate.objects.all()}
    group_members = {
        g.id: list(g.members.values_list("id", flat=True))
        for g in EmployeeGroup.objects.prefetch_related("members")
    }
    # (user, product) → that worker's own qop rate, for per_product bakers.
    product_rates = {
        (r.user_id, r.product_id): float(r.rate_per_meshok_uzs or 0)
        for r in UserProductRate.objects.all()
    }

    def _unit_labour(user_id, product_id, rate_type, rate, meshok, units):
        if rate_type == RateType.PER_MESHOK:
            return meshok * rate
        if rate_type == RateType.PER_UNIT:
            return units * rate
        if rate_type == RateType.PER_PRODUCT:
            return meshok * product_rates.get((user_id, product_id), 0.0)
        return 0.0  # time-based rates are not per-meshok direct labour

    cutoff = timezone.localdate() - timedelta(days=days)
    # run id → [user ids ticked on it], for individuals-attributed runs. Read from
    # the M2M through table in one query — .values() above can't span an M2M.
    adhoc_members: dict = {}
    for run_id, uid in (
        Production.individuals.through.objects
        .filter(production__occurred_at__date__gte=cutoff)
        .values_list("production_id", "user_id")
    ):
        adhoc_members.setdefault(run_id, []).append(uid)

    # product_id → { producer_key: [labour_sum, meshok_sum] }
    by_producer: dict = {}
    runs = (
        Production.objects
        .filter(occurred_at__date__gte=cutoff)
        .values("id", "product_id", "nonvoy_id", "group_id", "meshok_count", "unit_count")
    )
    for r in runs:
        pid_run = r["product_id"]
        meshok = float(r["meshok_count"] or 0)
        units = float(r["unit_count"] or 0)
        crew = adhoc_members.get(r["id"])
        if r["nonvoy_id"] and r["nonvoy_id"] in rates:
            key = ("n", r["nonvoy_id"])
            rt, rate = rates[r["nonvoy_id"]]
            labour = _unit_labour(r["nonvoy_id"], pid_run, rt, rate, meshok, units)
        elif r["group_id"]:
            key = ("g", r["group_id"])
            labour = sum(
                _unit_labour(uid, pid_run, *rates[uid], meshok, units)
                for uid in group_members.get(r["group_id"], [])
                if uid in rates
            )
        elif crew:
            # The crew itself is the producer — keyed by its exact membership, so
            # the same set of bakers accumulates as one producer across runs.
            key = ("a", tuple(sorted(crew)))
            labour = sum(
                _unit_labour(uid, pid_run, *rates[uid], meshok, units)
                for uid in crew
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
    # Communal (gas/electricity) and other misc costs — entered per meshok (qop),
    # folded into tan narxi alongside materials and labour.
    communal = round(float(product.communal_cost_per_meshok_uzs), 2)
    other = round(float(product.other_cost_per_meshok_uzs), 2)
    cos = round(ing_total + labour + communal + other, 2)
    sale_price = float(product.default_price_uzs)
    ingredient_per_unit = round(ing_total / meshok_size, 2) if meshok_size else 0.0
    communal_per_unit = round(communal / meshok_size, 2) if meshok_size else 0.0
    other_per_unit = round(other / meshok_size, 2) if meshok_size else 0.0
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
        "communal_per_unit": communal_per_unit,
        "other": other,
        "other_per_unit": other_per_unit,
        "cos_per_meshok": cos,
        "cos_per_unit": cos_per_unit,
        "ingredient_per_unit": ingredient_per_unit,
        "margin_per_unit": margin,
        "margin_pct": (margin / sale_price * 100) if sale_price else 0.0,
        "missing_prices": missing_prices,
    }


# ─────────────────── Daily P&L builder ───────────────────

def _rate_timelines(user_ids) -> dict:
    """{user_id: [(effective_from, rate, rate_type, week_start_day, currency), …]}

    The salary app's effective-dated rate history (salary.utils._rate_timeline)
    loaded for many users in two queries, carrying the currency so a USD rate is
    restated in UZS. Only users with a SalaryRate get one — like the salary app,
    which earns nothing without it; users with no period rows fall back to their
    current rate as a single epoch-dated period.
    """
    from apps.salary.models import SalaryRate, SalaryRatePeriod
    from apps.salary.utils import EPOCH

    periods: dict = {}
    for p in SalaryRatePeriod.objects.filter(user_id__in=user_ids).order_by("effective_from", "id"):
        periods.setdefault(p.user_id, []).append(
            (p.effective_from, float(p.rate or 0), p.rate_type, p.week_start_day, p.currency)
        )
    return {
        r.user_id: periods.get(r.user_id)
        or [(EPOCH, float(r.rate or 0), r.rate_type, r.week_start_day, r.currency)]
        for r in SalaryRate.objects.filter(user_id__in=user_ids)
    }


def _nonvoy_wages(start, end, tz) -> list:
    """Nonvoy (baker) wages EARNED in [start, end] — the labour part of Tan narxi.

    Accrual: pay lands on the day the work was done, not on payday. (Counting
    payouts dropped a whole week of wages on each Thursday, and a month with
    five Thursdays carried five weeks of pay.) Mirrors the salary app's earned
    calculation (salary.utils), so it ties out with the Oylik page:
      - production rates (per_meshok / per_unit / per_product): each run credits
        its baker, else every member of its group, else every baker ticked on
        it — the full quantity to each — at the rate in effect on the run's day;
      - time rates (per_week / fixed_monthly): accrue per calendar day (rate ÷ 7,
        rate ÷ days in the month) from the hire date, up to today;
      - bonuses add on their payment date — they are paid on top of the rate,
        and are the whole wage of a worker with no rate set up;
      - deductions subtract on their date.
    Salary and advance payouts are NOT counted: they settle these earnings.
    A worker archived before a day earns nothing from it.

    Returns one dict per credited run, accrued day, bonus and deduction:
    {date, user, kind, product_id, product, rate, qop, units, amount (UZS)};
    only production rows carry a product. Bonus and deduction rows add note +
    the payout's currency fields for display.
    """
    import calendar

    from django.contrib.auth import get_user_model

    from apps.salary.models import RateType, SalaryPayment, UserProductRate
    from apps.salary.utils import _rate_on
    from apps.users.models import EmployeeGroup

    bakers = {u.id: u for u in get_user_model().objects.filter(role="nonvoy")}
    timelines = _rate_timelines(list(bakers))
    product_rates = {
        (r.user_id, r.product_id): float(r.rate_per_meshok_uzs or 0)
        for r in UserProductRate.objects.filter(user_id__in=list(bakers))
    }
    names = dict(Product.objects.values_list("id", "name"))

    def gone(uid, d):
        u = bakers[uid]
        return u.is_archived and (u.archived_at is None or timezone.localtime(u.archived_at).date() < d)

    rows = []

    # Production pay. Crew per run follows salary.utils._production_contributions:
    # the run's baker, else its group's members, else its ad-hoc crew.
    group_members = {
        g.id: list(g.members.values_list("id", flat=True)) for g in EmployeeGroup.objects.all()
    }
    crews: dict = {}
    for run_id, uid in (
        Production.individuals.through.objects
        .filter(production__occurred_at__date__gte=start, production__occurred_at__date__lte=end)
        .values_list("production_id", "user_id")
    ):
        crews.setdefault(run_id, []).append(uid)
    runs = (
        Production.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("id", "d", "product_id", "nonvoy_id", "group_id", "meshok_count", "unit_count")
    )
    for r in runs:
        if r["nonvoy_id"]:
            crew = [r["nonvoy_id"]]
        elif r["group_id"]:
            crew = group_members.get(r["group_id"], [])
        else:
            crew = crews.get(r["id"], [])
        qop = float(r["meshok_count"] or 0)
        units = float(r["unit_count"] or 0)
        for uid in crew:
            if uid not in timelines or gone(uid, r["d"]):
                continue
            _eff, rate, rt, _wsd, cur = _rate_on(timelines[uid], r["d"])
            if rt == RateType.PER_MESHOK:
                amount = qop * rate
            elif rt == RateType.PER_UNIT:
                amount = units * rate
            elif rt == RateType.PER_PRODUCT:
                rate = product_rates.get((uid, r["product_id"]), 0.0)
                amount = qop * rate
            else:
                continue  # time rates accrue per day below
            if amount:
                rows.append({
                    "date": r["d"], "user": bakers[uid].display_name, "kind": rt,
                    "product_id": r["product_id"], "product": names.get(r["product_id"], "?"),
                    "rate": rate, "qop": qop, "units": units, "amount": _uzs(amount, cur),
                })

    # Time-rate pay, accrued day by day — never past today.
    d = start
    while d <= min(end, timezone.localdate()):
        month_days = calendar.monthrange(d.year, d.month)[1]
        for uid, timeline in timelines.items():
            if timezone.localtime(bakers[uid].date_joined).date() > d or gone(uid, d):
                continue
            _eff, rate, rt, _wsd, cur = _rate_on(timeline, d)
            if rt == RateType.PER_WEEK:
                amount = rate / 7
            elif rt == RateType.FIXED_MONTHLY:
                amount = rate / month_days
            else:
                continue
            if amount:
                rows.append({
                    "date": d, "user": bakers[uid].display_name, "kind": rt,
                    "product_id": None, "product": "", "rate": rate, "qop": 0.0, "units": 0.0,
                    "amount": _uzs(amount, cur),
                })
        d += timedelta(days=1)

    # Bonuses (+) and deductions (−), on the day they were booked.
    for s in (
        SalaryPayment.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end,
                user__role="nonvoy", kind__in=("bonus", "deduction"))
        .select_related("user").order_by("occurred_at")
    ):
        sign = -1 if s.kind == "deduction" else 1
        rows.append({
            "date": timezone.localtime(s.occurred_at).date(), "user": s.user.display_name,
            "kind": s.kind, "product_id": None, "product": "", "rate": 0.0, "qop": 0.0, "units": 0.0,
            "amount": sign * _uzs(s.amount, s.currency, s.exchange_rate),
            "note": s.note, "currency": s.currency,
            "original_amount": sign * _dec(s.amount),
            "exchange_rate": _rate_cell(s.currency, s.exchange_rate),
        })
    return rows


def _staff_pay(start, end) -> list:
    """Pay to everyone who is not a baker (driver, manager, accountant, …) —
    counted in Tan narxi on the day it is handed over: salary, advance and
    bonus are the cash that left. A deduction moves no cash, so it is skipped.
    Same row shape as _nonvoy_wages (kind="staff", pay_kind = the payout kind).
    """
    return [
        {
            "date": timezone.localtime(s.occurred_at).date(), "user": s.user.display_name,
            "kind": "staff", "pay_kind": s.get_kind_display(),
            "product_id": None, "product": "", "rate": 0.0, "qop": 0.0, "units": 0.0,
            "amount": _uzs(s.amount, s.currency, s.exchange_rate),
            "note": s.note, "currency": s.currency, "original_amount": _dec(s.amount),
            "exchange_rate": _rate_cell(s.currency, s.exchange_rate),
        }
        for s in SalaryPayment.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
        .exclude(user__role="nonvoy").exclude(kind="deduction")
        .select_related("user").order_by("occurred_at")
    ]


def _labour(start, end, tz) -> list:
    """Every wage row that lands in Tan narxi: bakers as earned (on the day of
    the work), everyone else as paid (on the day of the payout)."""
    return _nonvoy_wages(start, end, tz) + _staff_pay(start, end)


def _direct_sales_by_date(start, end, tz) -> dict:
    """{date: UZS} — kirim booked as "Buyurtmasiz sotuv": goods sold for cash
    with no order in the system. The money is the sale, so it joins Savdo on the
    day it was received (USD restated at its rate). Ordinary kirim never does —
    it pays for orders already counted in Savdo."""
    return {
        r["d"]: float(r["t"] or 0)
        for r in Payment.objects
        .filter(payment_type="direct_sale",
                received_at__date__gte=start, received_at__date__lte=end)
        .annotate(d=TruncDate("received_at", tzinfo=tz))
        .values("d")
        .annotate(t=Sum(uzs_amount_expr()))
    }


def _collect_pnl_data(start, end, tz):
    """Accrual-matched P&L inputs for pnl_daily and gross_overall.

    Revenue = net delivered value (delivered − returned) at the locked unit
        price, bucketed by order date, plus direct sales (buyurtmasiz sotuv
        kirim) on the day received. Cancelled orders excluded.
    Cost of sales = MATERIAL recipe cost of those delivered units, ingredients
        valued at the Ombor manual price (avg_cost_uzs). This matches revenue on
        an accrual basis (cost of what was actually sold), unlike the old
        cash-basis "ingredients bought this day" which swung wildly with
        purchase timing. Returned as the material component only; callers add the
        nonvoy production wage bucket below to get the displayed Tan narxi.
    Expenses are split by ExpenseCategory.below_op_profit:
        - exp:  operating costs → the Xarajatlar line, above Op. foyda.
        - draw: owner draws (Rizoxon, Bahodir) → the Harajatlar line, below
          Op. foyda. Op. foyda therefore reflects the business only.
    Salary folds into Tan narxi as prod_sal (see _labour): bakers' wages as
        EARNED on the day of the work, every other worker's pay as PAID on
        the day of the payout.
    """
    # Material + communal + other cost PER MESHOK (qop) for every product — the
    # recipe cost of one batch at the manual Ombor price, plus the per-meshok
    # communal (gas/electricity) and other rates. Tan narxi is computed by meshok
    # (batches PRODUCED), not by piece sold; nonvoy labour is added separately.
    price_map = _build_price_map()
    mat_per_meshok = {}
    for p in Product.objects.prefetch_related("recipe_items__ingredient__unit"):
        info = _compute_product_cos(p, price_map)
        mat_per_meshok[p.id] = info["ingredient_total"] + info["communal"] + info["other"]

    # Revenue from net-delivered order items (accrual, by order date).
    items_qs = (
        OrderItem.objects
        .filter(order__order_date__gte=start, order__order_date__lte=end, order__currency="UZS")
        .exclude(order__status="cancelled")
        .values("order__order_date", "unit_price", "delivered_quantity", "returned_quantity")
    )
    sales_by_date: dict = {}
    for item in items_qs:
        net = max(0, item["delivered_quantity"] - item["returned_quantity"])
        if net == 0:
            continue
        d = item["order__order_date"]
        sales_by_date[d] = sales_by_date.get(d, 0.0) + float(item["unit_price"]) * net
    for d, amt in _direct_sales_by_date(start, end, tz).items():
        sales_by_date[d] = sales_by_date.get(d, 0.0) + amt

    # Tan narxi (material component) = meshoks PRODUCED that day × per-meshok cost.
    cos_by_date: dict = {}
    prod_rows = (
        Production.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d", "product_id")
        .annotate(m=Sum("meshok_count"))
    )
    for r in prod_rows:
        cos_by_date[r["d"]] = cos_by_date.get(r["d"], 0.0) + mat_per_meshok.get(r["product_id"], 0.0) * float(r["m"] or 0)

    # Expenses — categories flagged include_in_pnl=False are left out of the P&L.
    # The rest split into operating (Xarajatlar) vs owner draws (Harajatlar).
    # BOTH currencies count: a USD expense is restated in UZS at the rate it was
    # booked at (uzs_amount_expr), never dropped.
    exp_qs = (
        GeneralExpense.objects
        .filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
        .exclude(category__include_in_pnl=False)
        .annotate(d=TruncDate("occurred_at", tzinfo=tz))
        .values("d", "category__below_op_profit")
        .annotate(total=Sum(uzs_amount_expr()))
    )
    exp_by_date: dict = {}
    draw_by_date: dict = {}
    for r in exp_qs:
        bucket = draw_by_date if r["category__below_op_profit"] else exp_by_date
        bucket[r["d"]] = bucket.get(r["d"], 0.0) + float(r["total"] or 0)

    # Wages fold into Tan narxi (cost of goods): bakers as EARNED, on the day
    # of the work (see _nonvoy_wages); everyone else as PAID, on the day of the
    # payout (see _staff_pay).
    prod_sal_by_date: dict = {}
    for w in _labour(start, end, tz):
        prod_sal_by_date[w["date"]] = prod_sal_by_date.get(w["date"], 0.0) + w["amount"]

    # Reviziya (inventory recount) variance folds into Tan narxi — a NON-CASH
    # adjustment. +value = shortage (kamomad, adds to COGS); −value = surplus
    # (ortiqcha, reduces it). Snapshotted per row as value_uzs at revision time,
    # bucketed by the day the recount happened.
    rev_by_date: dict = {}
    rev_rows = (
        InventoryRevisionReport.objects
        .filter(item_type="ingredient", value_uzs__isnull=False,
                created_at__date__gte=start, created_at__date__lte=end)
        .annotate(d=TruncDate("created_at", tzinfo=tz))
        .values("d")
        .annotate(total=Sum("value_uzs"))
    )
    for r in rev_rows:
        rev_by_date[r["d"]] = rev_by_date.get(r["d"], 0.0) + float(r["total"] or 0)

    # Build per-day tuples for all days in range that have activity
    day_data = []
    t = dict(sales=0.0, cos=0.0, exp=0.0, prod_sal=0.0, draw=0.0, rev=0.0)
    current = start
    while current <= end:
        sales = sales_by_date.get(current, 0.0)
        cos = cos_by_date.get(current, 0.0)
        exp = exp_by_date.get(current, 0.0)
        prod_sal = prod_sal_by_date.get(current, 0.0)
        draw = draw_by_date.get(current, 0.0)
        rev = rev_by_date.get(current, 0.0)
        if sales or cos or exp or prod_sal or draw or rev:
            day_data.append((current, sales, cos, exp, prod_sal, draw, rev))
        t["sales"] += sales
        t["cos"] += cos
        t["exp"] += exp
        t["prod_sal"] += prod_sal
        t["draw"] += draw
        t["rev"] += rev
        current += timedelta(days=1)

    return day_data, t


def build_pnl_daily(date_from=None, date_to=None):
    """Daily P&L: flat rows, one per active day."""
    today = timezone.localdate()
    start = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today.replace(day=1)
    end = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
    tz = get_current_timezone()

    day_data, t = _collect_pnl_data(start, end, tz)

    headers = ["Sana", "Savdo", "Tan narxi", "Yalpi foyda", "Xarajatlar", "Op. foyda", "Harajatlar", "Sof foyda"]
    rows = []
    for d, sales, mat_cos, exp, prod_sal, draw, rev in day_data:
        cos = mat_cos + prod_sal + rev    # Tan narxi = materials + nonvoy pay + reviziya
        gp = sales - cos
        op = gp - exp
        np_v = op - draw
        rows.append([d.strftime("%Y-%m-%d"), sales, cos, gp, exp, op, draw, np_v])

    cos_t = t["cos"] + t["prod_sal"] + t["rev"]
    gp_t = t["sales"] - cos_t
    op_t = gp_t - t["exp"]
    np_t = op_t - t["draw"]
    return headers, rows, {
        "total_sales": t["sales"], "total_cos": cos_t,
        "total_gross_profit": gp_t, "total_expenses": t["exp"] + t["draw"],
        "total_net_profit": np_t, "count": len(rows),
    }


def build_gross_overall(date_from=None, date_to=None):
    """Weekly P&L summary — one row per ISO-week, plus a period total.

    Deliberately different from build_pnl_daily (which shows every day):
    this gives a compact week-by-week overview suitable for management review.

    Rows have 11 elements: [label, sales, cos, gp, expenses, op_profit, draw,
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

    headers = ["Hafta", "Savdo", "Tan narxi", "Yalpi foyda", "Xarajatlar", "Op. foyda", "Harajatlar", "Sof foyda"]
    rows = []

    # Aggregate by ISO week — emit one summary row per week
    current_week = None
    w = dict(sales=0.0, cos=0.0, exp=0.0, prod_sal=0.0, draw=0.0, rev=0.0)
    week_num = 0
    week_first_day = None

    def _flush_week(wn, first_day, last_day, w):
        cos = w["cos"] + w["prod_sal"] + w["rev"]   # Tan narxi = materials + nonvoy pay + reviziya
        wgp = w["sales"] - cos
        wop = wgp - w["exp"]
        wnet = wop - w["draw"]
        label = f"Hafta {wn}  ({first_day.strftime('%-d %b')} – {last_day.strftime('%-d %b')})"
        return [label, w["sales"], cos, wgp, w["exp"], wop, w["draw"], wnet, 1,
                first_day.isoformat(), last_day.isoformat()]

    last_day_seen = None
    for d, sales, mat_cos, exp, prod_sal, draw, rev in day_data:
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
            w = dict(sales=0.0, cos=0.0, exp=0.0, prod_sal=0.0, draw=0.0, rev=0.0)

        w["sales"] += sales; w["cos"] += mat_cos; w["exp"] += exp
        w["prod_sal"] += prod_sal; w["draw"] += draw; w["rev"] += rev
        last_day_seen = d

    # Final week
    if day_data:
        rows.append(_flush_week(week_num, week_first_day, last_day_seen, w))

    # Period total — label adapts to range span
    cos_t = t["cos"] + t["prod_sal"] + t["rev"]
    gp_t = t["sales"] - cos_t
    op_t = gp_t - t["exp"]
    np_t = op_t - t["draw"]
    is_single_month = (start.year == end.year and start.month == end.month)
    total_label = "Oy jami" if is_single_month else f"Jami ({start.strftime('%d %b')} – {end.strftime('%d %b')})"
    rows.append([total_label, t["sales"], cos_t, gp_t, t["exp"], op_t, t["draw"], np_t, 2,
                 start.isoformat(), end.isoformat()])

    return headers, rows, {
        "total_sales": t["sales"], "total_cos": cos_t,
        "total_gross_profit": gp_t, "total_expenses": t["exp"] + t["draw"],
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
                _cinfo.get("ingredient_per_unit", 0.0)
                + _cinfo.get("communal_per_unit", 0.0)
                + _cinfo.get("other_per_unit", 0.0)
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
        production_material_total = 0.0  # material+communal+other per meshok × meshoks
        for pr in prod_qs:
            pid = pr["product_id"]
            meshoks = float(pr["total_meshoks"] or 0)
            cos_info = cos_map.get(pid, {})
            cos_per_meshok = cos_info.get("cos_per_meshok", 0.0)
            cos_total = meshoks * cos_per_meshok
            production_cos_total += cos_total
            production_material_total += meshoks * (
                cos_info.get("ingredient_total", 0.0)
                + cos_info.get("communal", 0.0)
                + cos_info.get("other", 0.0)
            )
            production.append({
                "product": pr["product__name"],
                "meshoks": meshoks,
                "cos_per_meshok": cos_per_meshok,
                "cos_total": cos_total,
            })

        # ── Expenses & salary for this day ────────────────────────────────
        # Categories flagged include_in_pnl=False are left out of the P&L; the
        # rest split into operating (Xarajatlar) vs owner draws (Harajatlar),
        # mirroring _collect_pnl_data.
        exp_total = 0.0
        draw_total = 0.0
        for r in (
            GeneralExpense.objects
            .filter(occurred_at__date=date)
            .exclude(category__include_in_pnl=False)
            .values("category__below_op_profit")
            .annotate(t=Sum(uzs_amount_expr()))
        ):
            if r["category__below_op_profit"]:
                draw_total += float(r["t"] or 0)
            else:
                exp_total += float(r["t"] or 0)

        # Wages, folded into Tan narxi below: bakers' pay earned today, other
        # staff's pay handed over today.
        prod_sal_total = sum(w["amount"] for w in _labour(date, date, get_current_timezone()))

        # Reviziya (inventory recount) variance for this day folds into Tan narxi
        # — a non-cash adjustment (+shortage / −surplus). Same avg-cost basis as
        # the material cost above.
        rev_total = float(
            InventoryRevisionReport.objects
            .filter(item_type="ingredient", value_uzs__isnull=False, created_at__date=date)
            .aggregate(t=Sum("value_uzs"))["t"] or 0
        )

        # Tan narxi = material cost of goods PRODUCED today (meshoks × per-meshok
        # material/communal/other cost) PLUS today's nonvoy (production) wages PLUS
        # today's reviziya variance.
        cos_display = production_material_total + prod_sal_total + rev_total
        # Savdo = today's deliveries (the cross-tab) + today's buyurtmasiz sotuv.
        direct = _direct_sales_by_date(date, date, get_current_timezone()).get(date, 0.0)
        sales = grand_total_sales + direct
        gp = sales - cos_display
        op = gp - exp_total
        net = op - draw_total

        return Response({
            "date": date.isoformat(),
            "products": [{"id": p["id"], "name": p["name"]} for p in products_list],
            "clients": clients,
            "column_totals": column_totals,
            "grand_total_sales": grand_total_sales,
            "production": production,
            "production_cos_total": production_cos_total,
            "pnl": {
                "sales": sales,
                "direct_sales": direct,
                "cos": cos_display,
                "cos_materials": production_material_total,
                "production_salary": prod_sal_total,
                "cos_revision": rev_total,
                "gross_profit": gp,
                "expenses": exp_total,
                "draw": draw_total,
                "op_profit": op,
                "net_profit": net,
            },
        })


# ────────────────── P&L detail (drill-down) endpoint ──────────────────
class PnlDetailView(APIView):
    """GET /reports/pnl-detail/?date_from=&date_to=[&product=<id>]

    Line-item breakdown of every P&L metric for a date range — powers the Gross
    Overall drill-down (click a cell → see exactly what makes up that number).
    Uses the same accrual basis as the P&L: material COGS on net-delivered goods,
    salary excluding advances with deductions subtracted.

    With ?product= every row narrows to that product: its sales and the
    material/kommunal/boshqa cost of its own qop, plus its Savdo share of the
    costs that belong to no single product — nonvoy pay (counted when paid),
    reviziya, Xarajatlar, Harajatlar. "allocation" carries the share and the
    whole-business totals it was applied to.
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
        product = request.query_params.get("product")
        product = int(product) if product and product.isdigit() else None

        price_map = _build_price_map()
        ing_per_meshok, communal_per_meshok, other_per_meshok, names = {}, {}, {}, {}
        for p in Product.objects.prefetch_related("recipe_items__ingredient__unit"):
            info = _compute_product_cos(p, price_map)
            ing_per_meshok[p.id] = info["ingredient_total"]
            communal_per_meshok[p.id] = info["communal"]
            other_per_meshok[p.id] = info["other"]
            names[p.id] = p.name

        # Savdo drill-down = revenue bucketed by order date (one row per day),
        # plus a per-product breakdown so the frontend can filter by product.
        items = (
            OrderItem.objects
            .filter(order__order_date__gte=start, order__order_date__lte=end, order__currency="UZS")
            .exclude(order__status="cancelled")
            .values("order__order_date", "product_id", "unit_price",
                    "delivered_quantity", "returned_quantity")
        )
        sales_by_day: dict = {}
        sales_by_pd: dict = {}   # (product_id, date) → amount
        prod_had_sales = set()
        all_sales = 0.0          # every product — the base of a product's share
        for it in items:
            net = max(0, it["delivered_quantity"] - it["returned_quantity"])
            if net == 0:
                continue
            d = it["order__order_date"]
            pid = it["product_id"]
            amt = float(it["unit_price"]) * net
            all_sales += amt
            if not product or pid == product:
                sales_by_day[d] = sales_by_day.get(d, 0.0) + amt
            sales_by_pd[(pid, d)] = sales_by_pd.get((pid, d), 0.0) + amt
            prod_had_sales.add(pid)
        # Buyurtmasiz sotuv joins Savdo per day; it names no product, so a
        # product view leaves it out (and says how much it left out).
        direct_by_day = _direct_sales_by_date(start, end, get_current_timezone())
        total_direct = sum(direct_by_day.values())
        if not product:
            for d, amt in direct_by_day.items():
                sales_by_day[d] = sales_by_day.get(d, 0.0) + amt
        sales_items = [
            {"date": d.isoformat(), "amount": sales_by_day[d]}
            for d in sorted(sales_by_day)
        ]
        sales_rows = [
            {"product_id": pid, "date": d.isoformat(), "amount": amt}
            for (pid, d), amt in sales_by_pd.items()
        ]
        sales_products = sorted(
            ({"id": pid, "name": names.get(pid, "?")} for pid in prod_had_sales),
            key=lambda x: x["name"],
        )

        # Tan narxi by product = meshoks PRODUCED in the range × per-meshok cost.
        cos_by_p, communal_by_p, other_by_p, meshok_by_p = {}, {}, {}, {}
        prod_rows = list(
            Production.objects
            .filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
            .values("product_id").annotate(m=Sum("meshok_count"))
        )
        # The product selector offers every product sold or baked in the range.
        products = sorted(
            ({"id": pid, "name": names.get(pid, "?")}
             for pid in prod_had_sales | {r["product_id"] for r in prod_rows}),
            key=lambda x: x["name"],
        )
        if product:
            prod_rows = [r for r in prod_rows if r["product_id"] == product]
        for r in prod_rows:
            pid = r["product_id"]
            m = float(r["m"] or 0)
            meshok_by_p[pid] = meshok_by_p.get(pid, 0.0) + m
            cos_by_p[pid] = cos_by_p.get(pid, 0.0) + ing_per_meshok.get(pid, 0.0) * m
            communal_by_p[pid] = communal_by_p.get(pid, 0.0) + communal_per_meshok.get(pid, 0.0) * m
            other_by_p[pid] = other_by_p.get(pid, 0.0) + other_per_meshok.get(pid, 0.0) * m
        cos_items = sorted(
            [{"name": names.get(pid, "?"), "qty": meshok_by_p[pid],
              "unit_cost": ing_per_meshok.get(pid, 0.0), "amount": cos_by_p[pid]}
             for pid in cos_by_p if cos_by_p[pid] > 0],
            key=lambda x: -x["amount"],
        )
        communal_items = sorted(
            [{"name": names.get(pid, "?"), "qty": meshok_by_p[pid],
              "unit_cost": communal_per_meshok.get(pid, 0.0), "amount": communal_by_p[pid]}
             for pid in communal_by_p if communal_by_p[pid] > 0],
            key=lambda x: -x["amount"],
        )
        other_items = sorted(
            [{"name": names.get(pid, "?"), "qty": meshok_by_p[pid],
              "unit_cost": other_per_meshok.get(pid, 0.0), "amount": other_by_p[pid]}
             for pid in other_by_p if other_by_p[pid] > 0],
            key=lambda x: -x["amount"],
        )
        total_sales = sum(sales_by_day.values())
        total_cos = sum(cos_by_p.values())
        total_communal = sum(communal_by_p.values())
        total_other = sum(other_by_p.values())

        # Expenses — line items (categories flagged include_in_pnl=False excluded),
        # split into operating (Xarajatlar, above Op. foyda) and owner draws
        # (Harajatlar, below it) exactly like _collect_pnl_data.
        exp_qs = (
            GeneralExpense.objects
            .filter(occurred_at__date__gte=start, occurred_at__date__lte=end)
            .exclude(category__include_in_pnl=False)
            .select_related("category").order_by("-occurred_at")
        )
        exp_items, draw_items = [], []
        for e in exp_qs:
            # `amount` is always UZS so the modal foots to the table; USD rows
            # additionally carry what was actually paid, for the "$100 × 12 000"
            # hint next to the converted figure.
            row = {
                "date": timezone.localtime(e.occurred_at).strftime("%Y-%m-%d"),
                "title": e.title,
                "category": e.category.name if e.category_id else "—",
                "amount": _uzs(e.amount, e.currency, e.exchange_rate),
                "currency": e.currency,
                "original_amount": _dec(e.amount),
                "exchange_rate": _rate_cell(e.currency, e.exchange_rate),
            }
            if e.category_id and e.category.below_op_profit:
                draw_items.append(row)
            else:
                exp_items.append(row)
        total_exp = sum(i["amount"] for i in exp_items)
        total_draw = sum(i["amount"] for i in draw_items)

        # Wages in Tan narxi — the same rows _collect_pnl_data sums, so the
        # modal reconciles with the tables. Bakers' production pay is grouped
        # per worker × product × rate and time pay per worker × rate (days
        # accrued); bonuses, deductions and other staff's payouts stay one row
        # per payment. One product: only its own production pay is direct, the
        # rest is shared (allocated by Savdo share below).
        earned: dict = {}
        payouts = []
        shared_labour = 0.0
        for w in _labour(start, end, get_current_timezone()):
            if product and w["product_id"] != product:
                if w["product_id"] is None:
                    shared_labour += w["amount"]
                continue
            if w["kind"] in ("bonus", "deduction", "staff"):
                label = {"bonus": "Bonus", "deduction": "Ushlab qolish"}.get(w["kind"]) or w["pay_kind"]
                payouts.append({
                    "date": w["date"].isoformat(),
                    "user": w["user"],
                    "kind": f"{label} — {w['note']}" if w["note"] else label,
                    "amount": w["amount"],
                    "currency": w["currency"],
                    "original_amount": w["original_amount"],
                    "exchange_rate": w["exchange_rate"],
                })
                continue
            # per_meshok and per_product both pay per qop — one row per rate.
            kind = "qop" if w["kind"] in ("per_meshok", "per_product") else w["kind"]
            acc = earned.setdefault(
                (w["user"], kind, w["product"], w["rate"]),
                {"qop": 0.0, "units": 0.0, "days": 0, "amount": 0.0},
            )
            acc["qop"] += w["qop"]
            acc["units"] += w["units"]
            acc["days"] += 1
            acc["amount"] += w["amount"]

        def _n(v):
            return f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", " ")

        prod_sal_items = []
        for (user, kind, prod_name, rate), acc in earned.items():
            if kind == "per_unit":
                label = f"{prod_name}: {_n(acc['units'])} dona × {_n(rate)}"
            elif kind == "per_week":
                label = f"Haftalik: {acc['days']} kun × {_n(rate)}/hafta"
            elif kind == "fixed_monthly":
                label = f"Oylik: {acc['days']} kun × {_n(rate)}/oy"
            else:
                label = f"{prod_name}: {_n(acc['qop'])} qop × {_n(rate)}"
            prod_sal_items.append({"date": None, "user": user, "kind": label,
                                   "amount": acc["amount"], "currency": "UZS"})
        prod_sal_items.sort(key=lambda i: (i["user"], -i["amount"]))
        prod_sal_items += payouts
        total_prod_sal = sum(i["amount"] for i in prod_sal_items)

        # Reviziya (inventory recount) variance — a non-cash adjustment that folds
        # into Tan narxi. Each row is an ingredient recount: +value = shortage
        # (kamomad, adds to COGS), −value = surplus (ortiqcha, reduces it).
        rev_qs = (
            InventoryRevisionReport.objects
            .filter(item_type="ingredient", value_uzs__isnull=False,
                    created_at__date__gte=start, created_at__date__lte=end)
            .exclude(value_uzs=0)
            .select_related("ingredient").order_by("-created_at")
        )
        revision_items = [
            {
                "date": timezone.localtime(r.created_at).strftime("%Y-%m-%d"),
                "name": r.ingredient.name if r.ingredient else "—",
                "qty_delta": float(r.old_quantity - r.new_quantity),
                "amount": _dec(r.value_uzs),
            }
            for r in rev_qs
        ]
        total_revision = sum(i["amount"] for i in revision_items)

        # One product: costs that belong to no single product — wages not tied
        # to its runs (time rates, bonuses, deductions, other staff), the
        # ingredient recount, Xarajatlar, Harajatlar — are allocated by the
        # product's share of Savdo. An estimate (the UI says so), but every
        # waterfall row narrows to the product and the products add back up to
        # the whole-business total.
        allocation = None
        if product:
            share = total_sales / all_sales if all_sales else 0.0
            allocation = {
                "share": share, "sales_all": all_sales, "direct_sales": total_direct,
                "labour": shared_labour, "revision": total_revision,
                "expenses": total_exp, "draw": total_draw,
            }
            if shared_labour:
                prod_sal_items.append({
                    "date": None, "user": "Umumiy (savdo ulushi)",
                    "kind": f"Mahsulotga bog'lanmagan ish haqi: {_n(shared_labour)} × {share * 100:.1f}%",
                    "amount": share * shared_labour, "currency": "UZS",
                })
                total_prod_sal += share * shared_labour
            total_revision, revision_items = share * total_revision, []
            total_exp *= share   # items stay whole: the drill-down lists them at 100%
            total_draw *= share

        # Tan narxi = materials + communal + other (boshqa) + production pay + reviziya.
        tan = total_cos + total_communal + total_other + total_prod_sal + total_revision
        gp = total_sales - tan
        op = gp - total_exp
        net = op - total_draw
        return Response({
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "product": product,
            "products": products,
            # products/rows stay for bundles that still filter Savdo themselves.
            "sales": {"total": total_sales, "items": sales_items,
                      "direct": 0.0 if product else total_direct,
                      "products": sales_products, "rows": sales_rows},
            "cos": {
                "total": tan,
                "materials_total": total_cos,
                "items": cos_items,
                "communal_total": total_communal,
                "communal_items": communal_items,
                "other_total": total_other,
                "other_items": other_items,
                "salary_total": total_prod_sal,
                "salary_items": prod_sal_items,
                "revision_total": total_revision,
                "revision_items": revision_items,
            },
            "expenses": {"total": total_exp, "items": exp_items},
            "draw": {"total": total_draw, "items": draw_items},
            # Deprecated alias for the removed Oylik line — keeps a browser tab
            # still running a pre-Harajatlar bundle from throwing on
            # `data.salary.total`.
            "salary": {"total": 0.0, "items": []},
            "gross_profit": gp,
            "op_profit": op,
            "net_profit": net,
            "allocation": allocation,
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

        # Salary payable (liability) — Oylik qarzdorligi: what we still owe staff.
        # Uses the same outstanding-balance formula as the Oylik page Qoldiq, so
        # the total matches the salary page's "Jami Qoldiq". Net of advances
        # (negative balances where a worker owes us). UZS salaries only (USD rates
        # are excluded to keep the UZS liability clean).
        from django.contrib.auth import get_user_model
        from apps.salary.utils import salary_outstanding
        User = get_user_model()
        payable_users = (
            User.objects
            .filter(role__in=["nonvoy", "driver", "accountant", "manager"], is_archived=False)
            .select_related("salary_rate")
        )
        salary_items = []
        total_salary_owed = 0.0
        for u in payable_users:
            rate = getattr(u, "salary_rate", None)
            if rate is not None and rate.currency == "USD":
                continue
            rem = float(salary_outstanding(u, rate))
            total_salary_owed += rem
            if rem > 0.5:
                salary_items.append({"name": u.display_name, "uzs": rem})
        salary_items.sort(key=lambda x: -x["uzs"])
        total_salary_owed = round(total_salary_owed, 2)
        total_liab_uzs = total_credit_uzs + total_salary_owed

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
            # Liabilities — customer credits (overpaid shops) + salary owed to staff.
            "liabilities": {
                "customer_credits": {
                    "items": credit_items,
                    "total_uzs": total_credit_uzs,
                    "total_usd": total_credit_usd,
                },
                "salary_payable": {
                    "items": salary_items,
                    "total_uzs": total_salary_owed,
                },
                "total_uzs": total_liab_uzs,
                "total_usd": total_credit_usd,
            },
            "total_assets_uzs": total_cash_uzs + total_recv_uzs + total_inv,
            "total_assets_usd": total_cash_usd + total_recv_usd,
            # Net worth after subtracting liabilities (a simple equity proxy).
            "net_worth_uzs": total_cash_uzs + total_recv_uzs + total_inv - total_liab_uzs,
            "net_worth_usd": total_cash_usd + total_recv_usd - total_credit_usd,
        })
