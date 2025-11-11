"""
Integration tests for order delivery and payment processing
Testing BUG-001 fix: Payment creation with correct amounts
"""
import pytest
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction

from orders.models import Order, OrderItem
from orders.forms import ConfirmDeliveryForm
from orders.utils import process_order_payment, quantize_money
from dashboard.models import Payment
from reports.models import BakeryBalance
from shops.models import Shop, Region
from products.models import Product
from inventory.models import BakeryProductStock

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.integration
class TestPaymentProcessing:
    """Test the complete payment processing flow"""
    
    def test_process_order_payment_creates_payment(self):
        """Test that process_order_payment creates a payment record"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop, received_amount=Decimal("50.00"))
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            unit_price=Decimal("100.00"),
            delivered_quantity=1
        )
        
        # Execute
        process_order_payment(order)
        
        # Assert
        payment = Payment.objects.get(order=order)
        assert payment.amount == Decimal("50.00")
        assert payment.shop == shop
        assert payment.payment_type == "collection"
    
    def test_process_order_payment_updates_bakery_balance(self):
        """Test that BakeryBalance is updated correctly"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        
        # Create first order
        order1 = Order.objects.create(shop=shop, received_amount=Decimal("100.00"))
        OrderItem.objects.create(
            order=order1,
            product=product,
            quantity=1,
            unit_price=Decimal("100.00"),
            delivered_quantity=1
        )
        process_order_payment(order1)
        
        # Create second order
        order2 = Order.objects.create(shop=shop, received_amount=Decimal("200.00"))
        OrderItem.objects.create(
            order=order2,
            product=product,
            quantity=2,
            unit_price=Decimal("100.00"),
            delivered_quantity=2
        )
        process_order_payment(order2)
        
        # Assert
        balance = BakeryBalance.get_instance()
        assert balance.amount == Decimal("300.00")
    
    def test_process_order_payment_calculates_shop_loan(self):
        """Test that shop loan balance is calculated correctly"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region, loan_balance=Decimal("0.00"))
        product = Product.objects.create(name="Test Product")
        
        order = Order.objects.create(shop=shop, received_amount=Decimal("50.00"), status="Delivered")
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            unit_price=Decimal("100.00"),
            delivered_quantity=2
        )
        
        # Execute
        process_order_payment(order)
        
        # Reload shop
        shop.refresh_from_db()
        
        # Assert: delivered 200, paid 50, loan should be 150
        assert shop.loan_balance == Decimal("150.00")
    
    def test_process_order_payment_idempotent(self):
        """Test that calling process_order_payment multiple times is safe"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop, received_amount=Decimal("100.00"))
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            unit_price=Decimal("100.00"),
            delivered_quantity=1
        )
        
        # Execute multiple times
        process_order_payment(order)
        process_order_payment(order)
        process_order_payment(order)
        
        # Assert: should still have only 1 payment
        payments = Payment.objects.filter(order=order)
        assert payments.count() == 1
        assert payments.first().amount == Decimal("100.00")
        
        # BakeryBalance should also be correct (not triple-counted)
        balance = BakeryBalance.get_instance()
        assert balance.amount == Decimal("100.00")


@pytest.mark.django_db
@pytest.mark.integration
class TestConfirmDeliveryForm:
    """Test the ConfirmDeliveryForm with fixed user parameter"""
    
    def test_form_save_accepts_user_parameter(self):
        """Test BUG-001 fix: form.save(user=...) should work"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop)
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=10,
            unit_price=Decimal("100.00")
        )
        
        user = User.objects.create_user(username="testuser", password="testpass")
        
        # Execute
        form_data = {
            f'delivered_{item.id}': 5,
            'received_amount': Decimal("250.00")
        }
        form = ConfirmDeliveryForm(data=form_data, order=order)
        assert form.is_valid()
        
        # This should not raise an error (BUG-001 fix)
        result = form.save(user=user)
        
        # Assert
        assert result == order
        order.refresh_from_db()
        assert order.received_amount == Decimal("250.00")
        assert order.status == "Partially Delivered"
        
        item.refresh_from_db()
        assert item.delivered_quantity == 5
    
    def test_form_updates_received_amount(self):
        """Test that form properly updates received_amount field"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop, received_amount=Decimal("0.00"))
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=10,
            unit_price=Decimal("100.00")
        )
        
        # Execute
        form_data = {
            f'delivered_{item.id}': 10,
            'received_amount': Decimal("1000.00")
        }
        form = ConfirmDeliveryForm(data=form_data, order=order)
        assert form.is_valid()
        form.save()
        
        # Assert
        order.refresh_from_db()
        assert order.received_amount == Decimal("1000.00")
        assert order.status == "Delivered"


@pytest.mark.django_db
@pytest.mark.integration
class TestCompleteDeliveryFlow:
    """Test the complete flow from order to delivery to payment"""
    
    def test_full_delivery_workflow(self):
        """Test complete workflow: create order → deliver → verify financials"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region, loan_balance=Decimal("0.00"))
        product = Product.objects.create(name="Test Product")
        user = User.objects.create_user(username="driver", password="pass")
        
        # Create stock
        stock = BakeryProductStock.objects.create(product=product, quantity=Decimal("100.000"))
        
        # 1. Create order
        order = Order.objects.create(shop=shop)
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=10,
            unit_price=Decimal("50.00")
        )
        
        # Verify initial state
        assert order.status == "Pending"
        assert order.received_amount == Decimal("0.00")
        assert shop.loan_balance == Decimal("0.00")
        
        # 2. Confirm delivery via form
        form_data = {
            f'delivered_{item.id}': 10,
            'received_amount': Decimal("300.00")  # Partial payment
        }
        form = ConfirmDeliveryForm(data=form_data, order=order)
        assert form.is_valid()
        form.save(user=user)
        
        # 3. Deduct stock (normally done in view during delivery confirmation)
        with transaction.atomic():
            for order_item in order.items.all():
                delivered_qty = Decimal(order_item.delivered_quantity or 0)
                if delivered_qty > 0:
                    stock.quantity -= delivered_qty
                    stock.save()
        
        # 4. Process payment
        with transaction.atomic():
            process_order_payment(order)
        
        # 5. Verify final state
        order.refresh_from_db()
        shop.refresh_from_db()
        stock.refresh_from_db()
        
        # Order should be delivered with correct received amount
        assert order.status == "Delivered"
        assert order.received_amount == Decimal("300.00")
        
        # Payment should exist with correct amount
        payment = Payment.objects.get(order=order)
        assert payment.amount == Decimal("300.00")
        assert payment.shop == shop
        
        # Shop loan should be: delivered (500) - received (300) = 200
        assert shop.loan_balance == Decimal("200.00")
        
        # BakeryBalance should match total payments
        balance = BakeryBalance.get_instance()
        assert balance.amount == Decimal("300.00")
        
        # Stock should be reduced
        assert stock.quantity == Decimal("90.000")
    
    def test_multiple_partial_deliveries(self):
        """Test multiple partial deliveries to same shop"""
        # Setup
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region, loan_balance=Decimal("0.00"))
        product = Product.objects.create(name="Test Product")
        user = User.objects.create_user(username="driver", password="pass")
        
        BakeryProductStock.objects.create(product=product, quantity=Decimal("1000.000"))
        
        # Order 1: Deliver 5, pay 300
        order1 = Order.objects.create(shop=shop)
        item1 = OrderItem.objects.create(
            order=order1,
            product=product,
            quantity=10,
            unit_price=Decimal("100.00")
        )
        form_data1 = {
            f'delivered_{item1.id}': 5,
            'received_amount': Decimal("300.00")
        }
        form1 = ConfirmDeliveryForm(data=form_data1, order=order1)
        form1.is_valid()
        form1.save(user=user)
        process_order_payment(order1)
        
        # Order 2: Deliver 8, pay 500
        order2 = Order.objects.create(shop=shop)
        item2 = OrderItem.objects.create(
            order=order2,
            product=product,
            quantity=8,
            unit_price=Decimal("100.00")
        )
        form_data2 = {
            f'delivered_{item2.id}': 8,
            'received_amount': Decimal("500.00")
        }
        form2 = ConfirmDeliveryForm(data=form_data2, order=order2)
        form2.is_valid()
        form2.save(user=user)
        process_order_payment(order2)
        
        # Verify
        shop.refresh_from_db()
        
        # Delivered total: 5*100 + 8*100 = 1300
        # Received total: 300 + 500 = 800
        # Loan should be: 1300 - 800 = 500
        assert shop.loan_balance == Decimal("500.00")
        
        # BakeryBalance should be sum of all payments
        balance = BakeryBalance.get_instance()
        assert balance.amount == Decimal("800.00")
