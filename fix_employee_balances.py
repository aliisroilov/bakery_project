#!/usr/bin/env python
"""
Fix employee salary balances:
1. Delete incorrect payment records
2. Set rate to 0 to prevent auto-calculation
3. Keep only initial balance

Run this script to fix all employees at once.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bakery_project.settings')
django.setup()

from decimal import Decimal
from users.models import User
from salary.models import SalaryRate, SalaryPayment
from salary.utils import calculate_auto_salary
from django.db.models import Sum


def fix_employee_balance(username, initial_balance, delete_payments=True, set_rate_to_zero=True):
    """
    Fix an employee's balance by:
    1. Setting initial balance
    2. Optionally deleting all payments
    3. Optionally setting rate to 0 to prevent auto-calculation
    """
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"❌ User '{username}' does not exist")
        return False

    print(f"\n{'='*70}")
    print(f"FIXING: {username}")
    print(f"{'='*70}")

    # Get or create SalaryRate
    try:
        sr = user.salary_rate
        print(f"📊 Current configuration:")
        print(f"   Initial Balance: {sr.initial_balance:,}")
        print(f"   Rate: {sr.rate:,} ({sr.get_rate_type_display()})")
    except SalaryRate.DoesNotExist:
        sr = SalaryRate.objects.create(
            user=user,
            rate=0,
            rate_type='fixed',
            initial_balance=initial_balance
        )
        print(f"✓ Created new SalaryRate")

    # Delete payments if requested
    if delete_payments:
        payments = SalaryPayment.objects.filter(user=user)
        payment_count = payments.count()
        total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        if payment_count > 0:
            print(f"\n💸 Deleting {payment_count} payment(s) totaling {total_paid:,}")
            for p in payments:
                print(f"   - {p.created_at.strftime('%Y-%m-%d')}: {p.amount:,} ({p.note or 'no note'})")
            payments.delete()
            print(f"✓ Deleted all payments")
        else:
            print(f"\n💸 No payments to delete")

    # Set rate to zero if requested
    if set_rate_to_zero:
        old_rate = sr.rate
        old_type = sr.rate_type
        sr.rate = 0
        sr.rate_type = 'fixed'
        print(f"\n⚙️  Changing rate:")
        print(f"   Old: {old_rate:,} ({old_type})")
        print(f"   New: 0 (fixed)")

    # Set initial balance
    old_balance = sr.initial_balance
    sr.initial_balance = Decimal(str(initial_balance))
    sr.save()

    print(f"\n💰 Setting initial balance:")
    print(f"   Old: {old_balance:,}")
    print(f"   New: {sr.initial_balance:,}")

    # Verify final balance
    total_earned = calculate_auto_salary(user)
    total_paid = user.salary_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    balance = total_earned - total_paid

    print(f"\n✅ FINAL RESULT:")
    print(f"   Initial Balance: {sr.initial_balance:,}")
    print(f"   Auto-calculated: {total_earned - sr.initial_balance:,}")
    print(f"   Total Earned: {total_earned:,}")
    print(f"   Total Paid: {total_paid:,}")
    print(f"   BALANCE DUE: {balance:,}")

    if balance == sr.initial_balance:
        print(f"\n🎉 SUCCESS! Balance equals initial balance")
    else:
        print(f"\n⚠️  WARNING: Balance ({balance:,}) != Initial Balance ({sr.initial_balance:,})")

    return True


def main():
    print("\n" + "="*70)
    print("EMPLOYEE BALANCE FIX SCRIPT")
    print("="*70)

    # Define employees to fix with their initial balances
    employees_to_fix = [
        ('Umarxon', 3210000),
        ('Ziyoxon', 260000),
        # Add more employees here as needed:
        # ('EmployeeName', 1000000),
    ]

    print(f"\nThis script will:")
    print(f"1. Delete all existing payment records")
    print(f"2. Set rate to 0 (fixed type) to prevent auto-calculation")
    print(f"3. Set initial balance to specified amount")
    print(f"\nEmployees to fix: {len(employees_to_fix)}")
    for name, amount in employees_to_fix:
        print(f"  - {name}: {amount:,}")

    response = input("\nContinue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Cancelled")
        return

    # Fix each employee
    for username, initial_balance in employees_to_fix:
        fix_employee_balance(
            username=username,
            initial_balance=initial_balance,
            delete_payments=True,
            set_rate_to_zero=True
        )

    print("\n" + "="*70)
    print("VERIFICATION - Run check_balance on all employees")
    print("="*70)

    for username, _ in employees_to_fix:
        print(f"\nTo verify {username}:")
        print(f"  python manage.py check_balance {username}")

    print("\n✅ Script complete!")


if __name__ == '__main__':
    main()
