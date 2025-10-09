from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ("total_price",)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "order_date", "status", "created_at")  # show order_date
    list_filter = ("status", "order_date")  # filter by order_date
    search_fields = ("shop__name",)
    ordering = ("-order_date", "-created_at")
    date_hierarchy = "order_date"  # navigate by order_date
    fields = ("shop", "order_date", "status")  # allow selecting order_date when creating/editing
    inlines = [OrderItemInline]
    list_per_page = 20
