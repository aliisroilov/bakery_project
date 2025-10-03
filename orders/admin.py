from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = ("total_price",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "shop", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("shop__name",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    list_per_page = 20
