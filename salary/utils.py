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
        earned = calculate_auto_salary_for_baker(rate)
    elif rate_obj.rate_type == "per_week":
        earned = calculate_auto_salary_for_driver(user, rate)
    elif rate_obj.rate_type == "fixed":
        earned = rate
    else:
        earned = Decimal("0.00")

    # 🧮 include the old debt in total earned
    return earned + initial_balance


def calculate_auto_salary_for_baker(rate):
    """
    Calculate total salary for bakers (shared per_qop rate).
    Counts total qops produced globally (since there’s no user link).
    """
    from inventory.models import Production

    total_qops = (
        Production.objects.aggregate(total=Sum("meshok")).get("total") or 0
    )

    if total_qops <= 0:
        return Decimal("0.00")

    return Decimal(total_qops) * rate


def calculate_auto_salary_for_driver(user, rate):
    """
    Calculate driver salary — only if at least one full week passed since last payment.
    """
    last_payment = SalaryPayment.objects.filter(user=user).order_by("-created_at").first()

    if last_payment:
        start_date = last_payment.created_at.date()
    else:
        start_date = user.date_joined.date() if hasattr(user, "date_joined") else date.today()
    
    days_since = (date.today() - start_date).days
    weeks_worked = days_since // 7

    if weeks_worked < 1:
        return Decimal("0.00")

    return Decimal(weeks_worked) * rate
