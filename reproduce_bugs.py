#!/usr/bin/env python
"""
Bug Reproduction & Testing Script for Bakery ERP
Run with: python reproduce_bugs.py
"""
import os
import django
import sys
from decimal import Decimal, ROUND_HALF_UP

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bakery_project.settings')
django.setup()

from django.db import transaction
from orders.models import Order, OrderItem
from dashboard.models import Payment
from reports.models import BakeryBalance
from shops.models import Shop, Region
from products.models import Product
from inventory.models import BakeryProductStock

def quantize_money(value):
    """Helper to round money to 2 decimal places"""
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

print("=" * 80)
print("BAKERY ERP - BUG REPRODUCTION SCRIPT")
print("=" * 80)

# ============================================================================
# BUG 1: Decimal precision issues in order totals
# ============================================================================
print("\n[BUG 1] Testing Decimal precision in order calculations...")

try:
    order = Order.objects.filter(items__isnull=False).first()
    if order:
        # Check total_amount calculation
        total = order.total_amount()
        print(f"  Order #{order.id} total_amount(): {total}")
        print(f"  Type: {type(total)}")
        
        # Manual calculation with proper Decimal
        manual_total = sum(
            Decimal(str(item.unit_price)) * Decimal(str(item.quantity))
            for item in order.items.all()
        )
        print(f"  Manual calculation (Decimal): {manual_total}")
        print(f"  Difference: {abs(total - manual_total)}")
        
        if abs(total - manual_total) > Decimal('0.01'):
            print("  ❌ FAIL: Precision loss detected!")
        else:
            print("  ✓ PASS")
    else:
        print("  ⚠ No orders with items found")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ============================================================================
# BUG 2: Race condition in payment creation
# ============================================================================
print("\n[BUG 2] Testing payment creation idempotency...")

try:
    order = Order.objects.filter(status='Delivered').first()
    if order:
        initial_payment_count = Payment.objects.filter(order=order).count()
        print(f"  Order #{order.id} has {initial_payment_count} payment(s)")
        
        # Simulate calling process_order_payment twice (race condition)
        from orders.utils import process_order_payment
        
        with transaction.atomic():
            process_order_payment(order)
        
        payment_count_after_1 = Payment.objects.filter(order=order).count()
        
        with transaction.atomic():
            process_order_payment(order)
        
        payment_count_after_2 = Payment.objects.filter(order=order).count()
        
        print(f"  After call 1: {payment_count_after_1} payment(s)")
        print(f"  After call 2: {payment_count_after_2} payment(s)")
        
        if payment_count_after_1 == payment_count_after_2:
            print("  ✓ PASS: Idempotent (uses update_or_create)")
        else:
            print("  ❌ FAIL: Multiple payments created!")
    else:
        print("  ⚠ No delivered orders found")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ============================================================================
# BUG 3: Shop loan balance consistency
# ============================================================================
print("\n[BUG 3] Testing shop loan balance calculations...")

try:
    shops = Shop.objects.filter(orders__isnull=False).distinct()[:3]
    
    for shop in shops:
        # Calculate what loan should be
        from django.db.models import Sum, F
        delivered_total = (
            OrderItem.objects.filter(
                order__shop=shop,
                order__status__in=["Delivered", "Partially Delivered"]
            )
            .aggregate(total=Sum(F("delivered_quantity") * F("unit_price")))
            .get("total") or Decimal("0.00")
        )
        
        received_total = (
            Payment.objects.filter(shop=shop)
            .aggregate(total=Sum("amount"))
            .get("total") or Decimal("0.00")
        )
        
        expected_loan = max(Decimal("0.00"), delivered_total - received_total)
        actual_loan = shop.loan_balance
        
        print(f"\n  Shop: {shop.name}")
        print(f"    Delivered total: {delivered_total}")
        print(f"    Received total: {received_total}")
        print(f"    Expected loan: {expected_loan}")
        print(f"    Actual loan: {actual_loan}")
        print(f"    Difference: {abs(expected_loan - actual_loan)}")
        
        if abs(expected_loan - actual_loan) > Decimal('0.01'):
            print("    ❌ FAIL: Loan balance mismatch!")
        else:
            print("    ✓ PASS")
            
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ============================================================================
# BUG 4: BakeryBalance vs actual payments
# ============================================================================
print("\n[BUG 4] Testing BakeryBalance consistency...")

try:
    balance = BakeryBalance.get_instance()
    total_payments = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    
    print(f"  BakeryBalance.amount: {balance.amount}")
    print(f"  Sum of all payments: {total_payments}")
    print(f"  Difference: {abs(balance.amount - total_payments)}")
    
    if abs(balance.amount - total_payments) > Decimal('0.01'):
        print("  ❌ FAIL: BakeryBalance doesn't match sum of payments!")
    else:
        print("  ✓ PASS")
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ============================================================================
# BUG 5: Stock deduction in delivery
# ============================================================================
print("\n[BUG 5] Testing inventory stock deductions...")

try:
    # Check if any products have negative stock
    negative_stocks = BakeryProductStock.objects.filter(quantity__lt=0)
    
    if negative_stocks.exists():
        print("  ❌ FAIL: Found products with negative stock:")
        for stock in negative_stocks[:5]:
            print(f"    - {stock.product.name}: {stock.quantity}")
    else:
        print("  ✓ PASS: No negative stock found")
        
    # Check stock totals
    total_stock = BakeryProductStock.objects.aggregate(
        total=Sum("quantity")
    )["total"] or Decimal("0.000")
    print(f"  Total stock across all products: {total_stock}")
    
except Exception as e:
    print(f"  ❌ ERROR: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("REPRODUCTION COMPLETE")
print("=" * 80)
print("\nNext steps:")
print("1. Review the failures above")
print("2. Run tests with: pytest tests/")
print("3. Check detailed bug report in BUGS_FOUND.md")
