"""Salary auto-calculation — v2 port of v1's calculate_auto_salary with per-user linkage.

Production-based salary credits BOTH:
  - individual productions (Production.nonvoy == user), counted in full, and
  - group productions (a group the user belongs to), ALSO counted in full.

The quantity is never split among group members — each member earns their own
salary tariff on the whole batch, because the per-member rate already encodes
their role/pay level (e.g. master baker vs helper).

Rates are EFFECTIVE-DATED (SalaryRatePeriod): earnings are priced piecewise at
the rate that was in effect on each production date / month / week, so editing
someone's rate never retroactively re-prices past periods — the new rate only
applies from its effective_from forward.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime, timedelta

# Rate types whose earnings come from production records (dated events) rather
# than elapsed time.
PRODUCTION_TYPES = ("per_meshok", "per_unit", "per_product")
EPOCH = date(2000, 1, 1)


def _count_weekly_periods(start: date, end: date, week_start_day: int) -> int:
    """Completed pay-weeks between *start* and *end*, each week ending on
    *week_start_day* (Mon=0…Sun=6): the number of `week_start_day` weekdays
    strictly after start, up to and including end."""
    if end <= start:
        return 0
    days_ahead = (week_start_day - start.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # strictly after start
    first = start + timedelta(days=days_ahead)
    if first > end:
        return 0
    return (end - first).days // 7 + 1


def _parse_date(d) -> date | None:
    """Accept a date object, a 'YYYY-MM-DD' string, None, or an empty string.

    An empty/blank string (a cleared date input arriving as ?date_from=) is
    treated as "no bound" instead of raising ValueError — otherwise the whole
    salary summary 500s until the field is re-filled.
    """
    if d is None:
        return None
    if isinstance(d, date):
        return d
    s = str(d).strip()
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _production_contributions(user, d_from=None, d_to=None, reset_date=None):
    """Yield (meshok, units, product) credited to *user*.

    Both individual productions (nonvoy=user) AND group productions (a group the
    user belongs to) count the FULL quantity for this user. The qop/dona is NOT
    split among group members — every member earns their own salary tariff on the
    whole batch, because the rate already encodes each person's role/pay level
    (e.g. a master baker on 130 000/qop vs a helper on 20 000/qop).

    *reset_date* is a hard lower bound: production before it is never counted
    (period close / fresh start), so historical runs don't resurface as salary.
    """
    from apps.production.models import Production

    # reset_date wins over d_from when it's later — it's a floor that can't be
    # crossed even if the caller asks for an earlier date range.
    if reset_date and (d_from is None or reset_date > d_from):
        d_from = reset_date

    # A run is credited either individually (nonvoy) or to a group — never both.
    # Guarding the group query with nonvoy__isnull=True makes the two sets disjoint
    # even if a legacy row accidentally has both set, so nobody is paid twice.
    individual = Production.objects.filter(nonvoy=user).select_related("product")
    group = (
        Production.objects.filter(group__members=user, nonvoy__isnull=True)
        .select_related("product", "group")
    )
    if d_from:
        individual = individual.filter(occurred_at__date__gte=d_from)
        group = group.filter(occurred_at__date__gte=d_from)
    if d_to:
        individual = individual.filter(occurred_at__date__lte=d_to)
        group = group.filter(occurred_at__date__lte=d_to)

    for p in individual:
        yield Decimal(p.meshok_count or 0), Decimal(p.unit_count or 0), p.product

    for p in group:
        # Full quantity — no division by member count.
        yield Decimal(p.meshok_count or 0), Decimal(p.unit_count or 0), p.product


def _earned_from_production(user, rate_type, rate, d_from=None, d_to=None, reset_date=None) -> Decimal:
    """Sum a user's production-based earnings (individual + group, full quantity)."""
    from .models import RateType

    total = Decimal("0.00")
    for meshok, units, product in _production_contributions(user, d_from, d_to, reset_date):
        if rate_type == RateType.PER_MESHOK:
            total += meshok * rate
        elif rate_type == RateType.PER_UNIT:
            total += units * rate
        elif rate_type == RateType.PER_PRODUCT:
            total += units * Decimal(product.production_salary_per_unit_uzs or 0)
    return total.quantize(Decimal("0.01"))


# ─────────────────── Effective-dated rate timeline ───────────────────

def _rate_timeline(user, rate_obj):
    """The user's rate history as a sorted list of
    (effective_from, rate, rate_type, week_start_day).

    Falls back to a single epoch-dated period built from the current rate_obj
    when no SalaryRatePeriod rows exist yet (pre-migration safety), so the whole
    of history is priced at today's rate exactly like the old behaviour.
    """
    from .models import SalaryRatePeriod

    rows = list(SalaryRatePeriod.objects.filter(user=user).order_by("effective_from", "id"))
    if rows:
        return [(r.effective_from, Decimal(r.rate or 0), r.rate_type, r.week_start_day) for r in rows]
    return [(EPOCH, Decimal(rate_obj.rate or 0), rate_obj.rate_type,
             getattr(rate_obj, "week_start_day", None))]


def _rate_on(timeline, d):
    """The timeline entry in effect on date *d* — the last period whose
    effective_from <= d (or the first period when d precedes all of them)."""
    chosen = timeline[0]
    for row in timeline:
        if row[0] <= d:
            chosen = row
        else:
            break
    return chosen


def _last_day_of_month(y: int, m: int) -> date:
    import calendar
    return date(y, m, calendar.monthrange(y, m)[1])


def _iter_year_months(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def _seg_bounds(timeline, i, end):
    """Half-open segment [effective_from, next_effective_from) for period *i*,
    expressed as an inclusive (seg_from, seg_to) with seg_to = day before the
    next period starts (or *end* for the last period)."""
    seg_from = timeline[i][0]
    seg_to = (timeline[i + 1][0] - timedelta(days=1)) if i + 1 < len(timeline) else end
    return seg_from, seg_to


def _earned_production_piecewise(user, timeline, floor, end, win_from=None, win_to=None):
    """Production earnings, each segment priced at its own rate. *floor* =
    reset_date (production before it never counts); *win_from/win_to* clip to a
    display date range when given."""
    total = Decimal("0.00")
    for i in range(len(timeline)):
        _eff, rate, rt, _wsd = timeline[i]
        if rt not in PRODUCTION_TYPES:
            continue
        seg_from, seg_to = _seg_bounds(timeline, i, end)
        if floor and seg_from < floor:
            seg_from = floor
        if win_from and seg_from < win_from:
            seg_from = win_from
        if win_to and seg_to > win_to:
            seg_to = win_to
        if seg_to > end:
            seg_to = end
        if seg_to < seg_from:
            continue
        total += _earned_from_production(user, rt, rate, d_from=seg_from, d_to=seg_to)
    return total.quantize(Decimal("0.01"))


def _earned_month_piecewise(timeline, start, end):
    """Fixed-monthly: one rate per calendar month from *start* to *end*, priced
    at the rate effective during that month (a mid-month change applies to the
    whole month). Single-period timeline → months × rate, exactly as before."""
    if end < start:
        return Decimal("0.00")
    total = Decimal("0.00")
    for y, m in _iter_year_months(start, end):
        total += _rate_on(timeline, _last_day_of_month(y, m))[1]
    return total.quantize(Decimal("0.01"))


def _earned_week_piecewise(timeline, start, end, wsd_default, inclusive_end=False):
    """Per-week: each segment's weeks (aligned to week_start_day, else the
    days÷7 fraction) priced at its rate."""
    if end < start:
        return Decimal("0.00")
    total = Decimal("0.00")
    for i in range(len(timeline)):
        _eff, rate, _rt, wsd = timeline[i]
        seg_from, seg_to = _seg_bounds(timeline, i, end)
        if seg_from < start:
            seg_from = start
        if seg_to > end:
            seg_to = end
        if seg_to < seg_from:
            continue
        wsd_use = wsd if wsd is not None else wsd_default
        if wsd_use is not None:
            weeks = Decimal(_count_weekly_periods(seg_from, seg_to, wsd_use))
        else:
            days = max((seg_to - seg_from).days + (1 if inclusive_end else 0), 0)
            weeks = Decimal(str(days)) / Decimal("7")
        total += weeks * rate
    return total.quantize(Decimal("0.01"))


def calculate_earned_period(user, rate_obj, date_from=None, date_to=None) -> Decimal:
    """Earned salary for *user* within [date_from, date_to], priced at the rate
    in effect on each date (effective-dated). No range → all-time earned.

    For production rates only production inside the range counts; for time-based
    rates the months/weeks inside the range are counted.
    """
    if rate_obj is None:
        return Decimal("0.00")

    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)
    if d_from is None and d_to is None:
        return calculate_earned(user, rate_obj)

    today = date.today()
    reset = getattr(rate_obj, "reset_date", None)
    timeline = _rate_timeline(user, rate_obj)
    rt = rate_obj.rate_type

    if rt in PRODUCTION_TYPES:
        return _earned_production_piecewise(user, timeline, reset, today, win_from=d_from, win_to=d_to)

    # ── Time-based rates ──────────────────────────────────────────────────────
    effective_from = d_from or today
    effective_to = d_to or today
    if effective_to > today:
        effective_to = today
    if reset and reset > effective_from:
        effective_from = reset
    if effective_to < effective_from:
        return Decimal("0.00")

    if rt == "per_week":
        return _earned_week_piecewise(timeline, effective_from, effective_to,
                                      getattr(rate_obj, "week_start_day", None), inclusive_end=True)
    if rt == "fixed_monthly":
        return _earned_month_piecewise(timeline, effective_from, effective_to)
    return Decimal("0.00")


def salary_outstanding(user, rate_obj=None) -> Decimal:
    """True outstanding salary balance for *user* — mirrors the Oylik page Qoldiq
    and SalaryEmployeeSummaryView.remaining.

    remaining = earned since reset − unsettled non-bonus payments since reset.
    Positive = we owe the employee (liability); negative = they owe us (net
    advances, an asset). initial_balance is intentionally excluded (see the note
    in SalaryEmployeeSummaryView).
    """
    from django.db.models import Sum
    from .models import SalaryPayment

    if rate_obj is None:
        rate_obj = getattr(user, "salary_rate", None)
    if rate_obj is None:
        return Decimal("0.00")
    reset = getattr(rate_obj, "reset_date", None)
    earned_total = calculate_earned(user, rate_obj)
    owed_pay = SalaryPayment.objects.filter(user=user, settled=False).exclude(kind="bonus")
    if reset:
        owed_pay = owed_pay.filter(occurred_at__date__gte=reset)
    paid_total = owed_pay.aggregate(t=Sum("amount"))["t"] or Decimal("0.00")
    return earned_total - paid_total


def calculate_earned(user, rate_obj) -> Decimal:
    """All-time earned salary for `user`, priced at the effective-dated rate for
    each period. Returns Decimal("0.00") if rate is null or type unknown.
    """
    if rate_obj is None:
        return Decimal("0.00")

    today = date.today()
    reset = getattr(rate_obj, "reset_date", None)
    timeline = _rate_timeline(user, rate_obj)
    rt = rate_obj.rate_type

    # ── Production-based rates (individual + group share) ──────────────────────
    if rt in PRODUCTION_TYPES:
        return _earned_production_piecewise(user, timeline, reset, today)

    # ── Time-based rates: accrue from hire (or the reset floor) to today ───────
    start = user.date_joined.date() if getattr(user, "date_joined", None) else today
    if reset and reset > start:
        start = reset  # nothing accrues before the reset date

    if rt == "per_week":
        return _earned_week_piecewise(timeline, start, today,
                                      getattr(rate_obj, "week_start_day", None))
    if rt == "fixed_monthly":
        if today < start:
            return Decimal("0.00")
        return _earned_month_piecewise(timeline, start, today)
    return Decimal("0.00")
