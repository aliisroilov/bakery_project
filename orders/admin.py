from django.contrib import admin
from django.db import transaction
from django.forms import ModelForm
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from .models import Order, OrderItem
from .utils import process_order_payment
from inventory.models import BakeryProductStock
import logging

logger = logging.getLogger(__name__)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ("total_price",)


class OrderAdminForm(ModelForm):
    """Custom form for Order admin with tomorrow as default date."""

    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default order_date to tomorrow if creating new order
        if not self.instance.pk:
            tomorrow = timezone.now().date() + timedelta(days=1)
            self.fields['order_date'].initial = tomorrow

    class Media:
        js = ('admin/js/order_date_tomorrow.js',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ("id", "shop", "order_date", "status", "received_amount", "created_at")
    list_filter = ("status", "order_date")
    search_fields = ("shop__name",)
    ordering = ("-order_date", "-created_at")
    date_hierarchy = "order_date"
    fields = ("shop", "order_date", "status", "received_amount")
    inlines = [OrderItemInline]
    list_per_page = 20

    def save_model(self, request, obj, form, change):
        """Save order model - store previous status for comparison."""
        if change:
            # Store old status before saving
            old_order = Order.objects.get(pk=obj.pk)
            obj._old_status = old_order.status
        else:
            obj._old_status = None
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """
        Save related objects (OrderItems) and handle stock deduction + payment processing.
        This is called after save_model and after all inlines are saved.
        """
        super().save_related(request, form, formsets, change)
        obj = form.instance

        # Check if order status changed to delivered/partially delivered
        old_status = getattr(obj, '_old_status', None)
        new_status = obj.status

        if new_status in ["Delivered", "Partially Delivered"]:
            with transaction.atomic():
                # Track which items were delivered (to avoid duplicate deductions)
                items_to_process = []

                # If status just changed to delivered, deduct stock
                if old_status not in ["Delivered", "Partially Delivered"]:
                    logger.info(
                        f"[ADMIN] Order #{obj.id} status changed from '{old_status}' to '{new_status}'. "
                        f"Processing stock deduction."
                    )

                    # Deduct stock for all delivered items
                    for item in obj.items.all():
                        delivered_qty = Decimal(item.delivered_quantity or 0)
                        if delivered_qty > 0:
                            try:
                                # Get or create stock entry
                                stock, created = BakeryProductStock.objects.get_or_create(
                                    product=item.product,
                                    defaults={"quantity": Decimal("0.000"), "pinned": True}
                                )

                                # Deduct delivered quantity from stock
                                old_stock_qty = stock.quantity
                                stock.quantity -= delivered_qty
                                stock.save(update_fields=["quantity"])

                                logger.info(
                                    f"[ADMIN] Stock deducted: {item.product.name} "
                                    f"{old_stock_qty} - {delivered_qty} = {stock.quantity}"
                                )
                                items_to_process.append(item.product.name)

                            except Exception as e:
                                logger.error(
                                    f"[ADMIN] Error deducting stock for {item.product.name}: {e}"
                                )
                                raise

                    if items_to_process:
                        logger.info(
                            f"[ADMIN] Stock deducted for {len(items_to_process)} items: "
                            f"{', '.join(items_to_process)}"
                        )
                else:
                    logger.info(
                        f"[ADMIN] Order #{obj.id} was already in '{old_status}' status. "
                        f"Skipping stock deduction (already processed)."
                    )

                # Process payment and balance updates (always do this for delivered orders)
                process_order_payment(obj)
                logger.info(f"[ADMIN] Payment processed for order #{obj.id}")
