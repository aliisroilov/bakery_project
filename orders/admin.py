# orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem
from .utils import process_order_payment

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ("total_price",)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "order_date", "status", "received_amount", "created_at")
    list_filter = ("status", "order_date")
    search_fields = ("shop__name",)
    ordering = ("-order_date", "-created_at")
    date_hierarchy = "order_date"
    fields = ("shop", "order_date", "status", "received_amount")
    inlines = [OrderItemInline]
    list_per_page = 20

    def save_related(self, request, form, formsets, change):
        """Called *after* inline items are saved."""
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.status in ["Delivered", "Partially Delivered"]:
            process_order_payment(obj)
