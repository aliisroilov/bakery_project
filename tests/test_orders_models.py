"""
Unit tests for Order models and calculations
Testing BUG-001 and BUG-002 fixes
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from orders.models import Order, OrderItem, quantize_money
from shops.models import Shop, Region
from products.models import Product

User = get_user_model()


@pytest.mark.django_db
class TestDecimalPrecision:
    """Test BUG-002: Decimal precision in calculations"""
    
    def test_quantize_money_rounds_correctly(self):
        """Test that quantize_money rounds to 2 decimal places"""
        assert quantize_money("10.123") == Decimal("10.12")
        assert quantize_money("10.125") == Decimal("10.13")  # ROUND_HALF_UP
        assert quantize_money("10.999") == Decimal("11.00")
        assert quantize_money(10) == Decimal("10.00")
        assert quantize_money(Decimal("10.12345")) == Decimal("10.12")
    
    def test_order_item_total_price_uses_decimal(self):
        """Test that OrderItem.total_price returns properly quantized Decimal"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop)
        
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=3,
            unit_price=Decimal("10.50")
        )
        
        total = item.total_price
        assert isinstance(total, Decimal)
        assert total == Decimal("31.50")
        
    def test_order_item_total_price_with_large_quantity(self):
        """Test precision with large quantities"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop)
        
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=100,
            unit_price=Decimal("5000.00")
        )
        
        total = item.total_price
        assert total == Decimal("500000.00")
        assert isinstance(total, Decimal)
    
    def test_order_total_amount_sums_correctly(self):
        """Test that Order.total_amount() sums items correctly"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        order = Order.objects.create(shop=shop)
        
        product1 = Product.objects.create(name="Product 1")
        product2 = Product.objects.create(name="Product 2")
        
        OrderItem.objects.create(
            order=order,
            product=product1,
            quantity=2,
            unit_price=Decimal("10.50")
        )
        OrderItem.objects.create(
            order=order,
            product=product2,
            quantity=3,
            unit_price=Decimal("20.75")
        )
        
        total = order.total_amount()
        expected = Decimal("10.50") * 2 + Decimal("20.75") * 3
        assert total == quantize_money(expected)
        assert isinstance(total, Decimal)
    
    def test_order_total_amount_with_no_items(self):
        """Test that total_amount returns 0.00 for orders with no items"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        order = Order.objects.create(shop=shop)
        
        total = order.total_amount()
        assert total == Decimal("0.00")


@pytest.mark.django_db
class TestOrderStatusUpdates:
    """Test order status update logic"""
    
    def test_update_status_pending_when_no_deliveries(self):
        """Order should be Pending when nothing delivered"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop, status="Pending")
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=10,
            unit_price=Decimal("10.00"),
            delivered_quantity=0
        )
        
        order.update_status()
        assert order.status == "Pending"
    
    def test_update_status_partially_delivered(self):
        """Order should be Partially Delivered when some delivered"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop, status="Pending")
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=10,
            unit_price=Decimal("10.00"),
            delivered_quantity=5
        )
        
        order.update_status()
        assert order.status == "Partially Delivered"
    
    def test_update_status_delivered_when_all_delivered(self):
        """Order should be Delivered when all items delivered"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        product = Product.objects.create(name="Test Product")
        order = Order.objects.create(shop=shop, status="Pending")
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=10,
            unit_price=Decimal("10.00"),
            delivered_quantity=10
        )
        
        order.update_status()
        assert order.status == "Delivered"


@pytest.mark.django_db
class TestOrderReceivedAmount:
    """Test BUG-001: received_amount field handling"""
    
    def test_received_amount_defaults_to_zero(self):
        """New orders should have received_amount = 0.00"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        order = Order.objects.create(shop=shop)
        
        assert order.received_amount == Decimal("0.00")
    
    def test_received_amount_can_be_set(self):
        """received_amount should be settable and persist"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        order = Order.objects.create(shop=shop)
        
        order.received_amount = Decimal("1000.50")
        order.save()
        
        # Reload from DB
        order_reloaded = Order.objects.get(pk=order.pk)
        assert order_reloaded.received_amount == Decimal("1000.50")
    
    def test_received_amount_precision(self):
        """received_amount should maintain 2 decimal places"""
        region = Region.objects.create(name="Test Region")
        shop = Shop.objects.create(name="Test Shop", region=region)
        order = Order.objects.create(shop=shop)
        
        order.received_amount = Decimal("99.99")
        order.save()
        
        order_reloaded = Order.objects.get(pk=order.pk)
        assert order_reloaded.received_amount == Decimal("99.99")
        # Check it's exactly 2 decimal places
        assert len(str(order_reloaded.received_amount).split('.')[-1]) == 2
