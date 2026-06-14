from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name", "default_price_uzs", "default_price_usd",
        "cost_price_uzs", "meshok_size", "is_archived",
    ]
    list_filter = ["is_archived"]
    search_fields = ["name"]
    ordering = ["name"]
    readonly_fields = ["cost_price_uzs", "cost_price_updated_at", "created_at", "updated_at"]
