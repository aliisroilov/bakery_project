from decimal import Decimal
from datetime import timedelta, date
from django.db.models import Sum
from salary.models import SalaryRate, SalaryPayment

def calculate_auto_salary(user):
    """
    Calculate salary for a user based on SalaryRate type.
    Uses only real data (produced qops, elapsed time, etc.)
    """
    try:
        rate_obj = SalaryRate.objects.get(user=user)
    except SalaryRate.DoesNotExist:
        return Decimal("0.00")

    rate = Decimal(rate_obj.rate)
    initial_balance = Decimal(rate_obj.initial_balance or 0)  # 🆕 include this

    if rate_obj.rate_type == "per_qop":
        earned = calculate_auto_salary_for_baker(rate, rate_obj.production_start_date)
    elif rate_obj.rate_type == "per_week":
        earned = calculate_auto_salary_for_driver(user, rate, rate_obj.production_start_date)
    elif rate_obj.rate_type == "fixed":
        earned = rate
    else:
        earned = Decimal("0.00")

    # 🧮 include the old debt in total earned
    return earned + initial_balance


def calculate_auto_salary_for_baker(rate, production_start_date=None):
    """
    Calculate total salary for bakers (shared per_qop rate).
    Counts total qops produced globally (since there's no user link).

    Args:
        rate: Rate per qop
        production_start_date: Only count production from this date forward (optional)
    """
    from inventory.models import Production

    # Filter production by date if specified
    queryset = Production.objects.all()
    if production_start_date:
        queryset = queryset.filter(date__gte=production_start_date)

    total_qops = queryset.aggregate(total=Sum("meshok")).get("total") or 0

    if total_qops <= 0:
        return Decimal("0.00")

    return Decimal(total_qops) * rate


def calculate_auto_salary_for_driver(user, rate, production_start_date=None):
    """
    Calculate driver salary — only if at least one full week passed since last payment.

    Args:
        user: The driver user
        rate: Weekly rate
        production_start_date: Only count weeks from this date forward (optional)
    """
    last_payment = SalaryPayment.objects.filter(user=user).order_by("-created_at").first()

    if last_payment:
        start_date = last_payment.created_at.date()
    else:
        start_date = user.date_joined.date() if hasattr(user, "date_joined") else date.today()

    # Use production_start_date if it's later than the calculated start_date
    if production_start_date and production_start_date > start_date:
        start_date = production_start_date

    days_since = (date.today() - start_date).days
    weeks_worked = days_since // 7

    if weeks_worked < 1:
        return Decimal("0.00")

    return Decimal(weeks_worked) * rate
