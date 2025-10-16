from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from .forms import SalaryPaymentForm
from .models import SalaryPayment
from reports.models import BakeryBalance
from users.models import User
from salary.utils import calculate_auto_salary  # ✅ important
from django.contrib.auth import get_user_model

def manager_or_admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.role == "driver":
            messages.error(request, "Sizda ruxsat yo‘q")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@manager_or_admin_required
def employee_list(request):
    balance_obj = BakeryBalance.get_instance()
    bakery_balance = balance_obj.amount

    employees = []

    # ✅ Show only nonvoy and driver
    for user in User.objects.filter(role__in=["nonvoy", "driver"]):
        # ✅ Calculate total possible salary (hisoblangan)
        total_earned = calculate_auto_salary(user)

        # ✅ All previous payments
        payments = SalaryPayment.objects.filter(user=user)
        total_paid = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        # ✅ Remaining salary = calculated - paid
        remaining_salary = total_earned - total_paid

        # ✅ Last payment info
        last_payment = payments.order_by("-created_at").first()

        employees.append({
            "user": user,
            "earned": remaining_salary,  # hisoblangan, reduced by paid
            "last_paid": last_payment.amount if last_payment else Decimal("0.00"),
            "last_paid_date": last_payment.created_at.date() if last_payment else None,
        })

    return render(request, "salary/employee_list.html", {
        "balance": bakery_balance,
        "employees": employees,
    })

@login_required
@manager_or_admin_required
def pay_salary(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = SalaryPaymentForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            note = form.cleaned_data.get('note')
            try:
                SalaryPayment.create_and_process(user=user, amount=amount, note=note)
                messages.success(request, f"{user.username} ga {amount:,} so‘m to‘landi.")
            except Exception as e:
                messages.error(request, f"To‘lovni bajarishda xatolik: {e}")
            return redirect("salary:employee_list")
    else:
        form = SalaryPaymentForm(initial={"user_id": user.id})

    return render(request, "salary/pay_salary.html", {"form": form, "employee": user})


User = get_user_model()


def salary_history(request, user_id):
    """
    Show all salary payment records for a specific employee.
    """
    user = get_object_or_404(User, id=user_id)

    payments = SalaryPayment.objects.filter(user=user).order_by("-created_at")

    total_paid = sum([p.amount for p in payments])
    total_count = payments.count()

    context = {
        "user": user,
        "payments": payments,
        "total_paid": total_paid,
        "total_count": total_count,
    }
    return render(request, "salary/salary_history.html", context)