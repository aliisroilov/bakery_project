from django.contrib import admin

from .models import BakeryProductStock, InventoryRevisionReport, Production, ProductionIngredientUsage


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = ["product", "actor_name", "meshok_count", "unit_count", "occurred_at"]
    list_filter = ["product"]
    ordering = ["-occurred_at"]
    readonly_fields = ["created_at"]


@admin.register(BakeryProductStock)
class BakeryProductStockAdmin(admin.ModelAdmin):
    list_display = ["product", "quantity", "pinned"]
    list_editable = ["quantity", "pinned"]
    ordering = ["product__name"]


@admin.register(ProductionIngredientUsage)
class ProductionIngredientUsageAdmin(admin.ModelAdmin):
    list_display = ["production", "ingredient", "quantity_used", "recorded_at"]
    readonly_fields = ["recorded_at"]
    ordering = ["-recorded_at"]


@admin.register(InventoryRevisionReport)
class InventoryRevisionReportAdmin(admin.ModelAdmin):
    list_display = ["item_type", "ingredient", "product", "old_quantity", "new_quantity", "user", "created_at"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
