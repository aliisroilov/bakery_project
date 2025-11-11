#!/usr/bin/env python
"""
Data Migration Script: Fix Zero-Payment Orders
This script recalculates and fixes all orders that have zero payments but were delivered.
"""
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bakery_project.settings')
django.setup()

from django.db import transaction
from orders.models import Order, OrderItem
from dashboard.models import Payment
from orders.utils import process_order_payment, quantize_money

print("=" * 80)
print("DATA MIGRATION: Fix Zero-Payment Orders")
print("=" * 80)

# Find all delivered orders with zero received_amount
problematic_orders = Order.objects.filter(
    status__in=['Delivered', 'Partially Delivered'],
    received_amount=0
)

print(f"\nFound {problematic_orders.count()} orders with zero received_amount")

if problematic_orders.count() == 0:
    print("✓ No problematic orders found. Database is clean!")
    exit(0)

print("\nDETAILS:")
for order in problematic_orders:
    total_delivered_value = Decimal('0.00')
    for item in order.items.all():
        item_value = quantize_money(
            Decimal(str(item.delivered_quantity)) * Decimal(str(item.unit_price))
        )
        total_delivered_value += item_value
        print(f"  Order #{order.id} - {order.shop.name}")
        print(f"    Delivered value: {total_delivered_value}")

print("\n" + "-" * 80)
print("MIGRATION STRATEGY:")
print("-" * 80)
print("""
Since these orders have been delivered but no payment was recorded,
we have two options:

1. ASSUME FULL PAYMENT: Set received_amount = delivered_amount
   - Use this if deliveries were paid in full but not recorded
   
2. KEEP AS DEBT: Leave received_amount = 0
   - Use this if payment hasn't been collected yet
   
For this migration, we'll choose Option 2 (keep as debt).
This maintains data integrity and allows manual correction later.
""")

user_input = input("\nProceed with migration? (yes/no): ").strip().lower()

if user_input != 'yes':
    print("Migration cancelled.")
    exit(0)

print("\nStarting migration...")

with transaction.atomic():
    for order in problematic_orders:
        print(f"\n  Processing Order #{order.id}...")
        
        # Recalculate and process payment
        # Since received_amount is 0, this will create a 0-amount payment
        # and correctly update shop loan balance
        process_order_payment(order)
        
        print(f"    ✓ Processed")

print("\n" + "=" * 80)
print("MIGRATION COMPLETE")
print("=" * 80)

# Verify results
from reports.models import BakeryBalance

total_payments = Payment.objects.aggregate(total=django.db.models.Sum("amount"))["total"] or Decimal("0.00")
bakery_balance = BakeryBalance.get_instance().amount

print(f"\nFINAL STATE:")
print(f"  Total payments in DB: {total_payments}")
print(f"  BakeryBalance: {bakery_balance}")
print(f"  Match: {'✓' if abs(total_payments - bakery_balance) < Decimal('0.01') else '✗'}")

# Check shop balances
from shops.models import Shop
print(f"\nSHOP LOAN BALANCES:")
for shop in Shop.objects.filter(orders__isnull=False).distinct()[:10]:
    print(f"  {shop.name}: {shop.loan_balance} so'm")
