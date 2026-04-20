"""Salary auto-calculation — v2 port of v1's calculate_auto_salary with per-user linkage."""
from __future__ import annotations

from decimal import Decimal
from datetime import date

from django.db.models import Sum


def calculate_earned(user, rate_obj) -> Decimal:
    """Compute earned salary for `user` based on their SalaryRate.

    Handles all v2 rate types. Returns Decimal("0.00") if rate is null or type unknown.
    """
    from apps.production.models import Production
    from .models import RateType, SalaryPayment

    if rate_obj is None:
        return Decimal("0.00")

    rate = Decimal(rate_obj.rate or 0)
    rt = rate_obj.rate_type

    if rt == RateType.PER_MESHOK:
        total = (
            Production.objects.filter(nonvoy=user)
            .aggregate(s=Sum("meshok_count"))
            .get("s") or 0
        )
        return Decimal(total) * rate

    if rt == RateType.PER_UNIT:
        total = (
            Production.objects.filter(nonvoy=user)
            .aggregate(s=Sum("unit_count"))
            .get("s") or 0
        )
        return Decimal(total) * rate

    if rt == RateType.PER_PRODUCT:
        # Sum(unit_count * product.production_salary_per_unit_uzs) for this user.
        total = Decimal("0.00")
        productions = Production.objects.filter(nonvoy=user).select_related("product")
        for p in productions:
            total += Decimal(p.unit_count or 0) * Decimal(
                p.product.production_salary_per_unit_uzs or 0
            )
        return total

    if rt == RateType.PER_WEEK:
        last = (
            SalaryPayment.objects.filter(user=user, kind="salary")
            .order_by("-occurred_at")
            .first()
        )
        start = last.occurred_at.date() if last else (
            user.date_joined.date() if hasattr(user, "date_joined") else date.today()
        )
        days = (date.today() - start).days
        weeks = max(days // 7, 0)
        return Decimal(weeks) * rate

    if rt == RateType.FIXED_MONTHLY:
        return rate

    return Decimal("0.00")
