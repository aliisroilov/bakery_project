from django.contrib import admin
from .models import Product
from inventory.admin import ProductRecipeInline

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "description")
    inlines = [ProductRecipeInline]
    ordering = ("name",)
    list_per_page = 20

    fieldsets = (
        (None, {
            "fields": ("name", "description", "is_active")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("created_at", "updated_at")
