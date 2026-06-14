"""Salary auto-calculation — v2 port of v1's calculate_auto_salary with per-user linkage.

Production-based salary credits BOTH:
  - individual productions (Production.nonvoy == user), counted in full, and
  - group productions (a group the user belongs to), ALSO counted in full.

The quantity is never split among group members — each member earns their own
salary tariff on the whole batch, because the per-member rate already encodes
their role/pay level (e.g. master baker vs helper).
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime


def _parse_date(d) -> date | None:
    """Accept a date object, a 'YYYY-MM-DD' string, or None."""
    if d is None:
        return None
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d), "%Y-%m-%d").date()


def _production_contributions(user, d_from=None, d_to=None):
    """Yield (meshok, units, product) credited to *user*.

    Both individual productions (nonvoy=user) AND group productions (a group the
    user belongs to) count the FULL quantity for this user. The qop/dona is NOT
    split among group members — every member earns their own salary tariff on the
    whole batch, because the rate already encodes each person's role/pay level
    (e.g. a master baker on 130 000/qop vs a helper on 20 000/qop).
    """
    from apps.production.models import Production

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


def _earned_from_production(user, rate_type, rate, d_from=None, d_to=None) -> Decimal:
    """Sum a user's production-based earnings (individual + group, full quantity)."""
    from .models import RateType

    total = Decimal("0.00")
    for meshok, units, product in _production_contributions(user, d_from, d_to):
        if rate_type == RateType.PER_MESHOK:
            total += meshok * rate
        elif rate_type == RateType.PER_UNIT:
            total += units * rate
        elif rate_type == RateType.PER_PRODUCT:
            total += units * Decimal(product.production_salary_per_unit_uzs or 0)
    return total.quantize(Decimal("0.01"))


def calculate_earned_period(user, rate_obj, date_from=None, date_to=None) -> Decimal:
    """Compute earned salary for *user* within the given date range.

    For production-based rates (per_meshok / per_unit / per_product) only
    production records that fall inside [date_from, date_to] are counted.

    For time-based rates (per_week / fixed_monthly) the number of days /
    calendar months inside the range is used, so the number is meaningful
    even when viewing a single month.

    Falls back to calculate_earned (all-time) when no date bounds are given.
    """
    from .models import RateType

    if rate_obj is None:
        return Decimal("0.00")

    d_from = _parse_date(date_from)
    d_to = _parse_date(date_to)

    # No range — delegate to the all-time function
    if d_from is None and d_to is None:
        return calculate_earned(user, rate_obj)

    rate = Decimal(rate_obj.rate or 0)
    rt = rate_obj.rate_type

    # ── Production-based rates (individual + group share) ──────────────────────
    if rt in (RateType.PER_MESHOK, RateType.PER_UNIT, RateType.PER_PRODUCT):
        return _earned_from_production(user, rt, rate, d_from, d_to)

    # ── Time-based rates ──────────────────────────────────────────────────────
    today = date.today()
    effective_from = d_from or today
    effective_to = d_to or today

    if rt == RateType.PER_WEEK:
        days = max((effective_to - effective_from).days + 1, 0)
        weeks = Decimal(str(days)) / Decimal("7")
        return (weeks * rate).quantize(Decimal("0.01"))

    if rt == RateType.FIXED_MONTHLY:
        # Count distinct calendar months touched by the range.
        months = (
            (effective_to.year - effective_from.year) * 12
            + (effective_to.month - effective_from.month)
            + 1
        )
        return (Decimal(max(months, 1)) * rate).quantize(Decimal("0.01"))

    return Decimal("0.00")


def calculate_earned(user, rate_obj) -> Decimal:
    """Compute earned salary for `user` based on their SalaryRate.

    Handles all v2 rate types. Returns Decimal("0.00") if rate is null or type unknown.
    """
    from .models import RateType

    if rate_obj is None:
        return Decimal("0.00")

    rate = Decimal(rate_obj.rate or 0)
    rt = rate_obj.rate_type

    # ── Production-based rates (individual + group share) ──────────────────────
    if rt in (RateType.PER_MESHOK, RateType.PER_UNIT, RateType.PER_PRODUCT):
        return _earned_from_production(user, rt, rate)

    if rt == RateType.PER_WEEK:
        # Count total days since hire ÷ 7 = fractional weeks accumulated.
        # Using last-payment date caused earned to show 0 for 6 days after each payment.
        start = user.date_joined.date() if hasattr(user, "date_joined") else date.today()
        days = max((date.today() - start).days, 0)
        weeks = Decimal(str(days)) / Decimal("7")
        return (weeks * rate).quantize(Decimal("0.01"))

    if rt == RateType.FIXED_MONTHLY:
        # Count total months worked since hire (including current partial month).
        # Returning just `rate` caused remaining to go negative after month 1 was paid.
        start = user.date_joined.date() if hasattr(user, "date_joined") else date.today()
        today = date.today()
        months = (today.year - start.year) * 12 + (today.month - start.month) + 1
        return (Decimal(max(months, 1)) * rate).quantize(Decimal("0.01"))

    return Decimal("0.00")
