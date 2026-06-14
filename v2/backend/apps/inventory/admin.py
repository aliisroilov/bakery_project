from django.contrib import admin

from .models import Ingredient, ProductRecipe, Purchase, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["name", "short"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name", "unit", "quantity", "low_stock_threshold", "avg_cost_uzs", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(ProductRecipe)
class ProductRecipeAdmin(admin.ModelAdmin):
    list_display = ["product", "ingredient", "amount_per_meshok"]
    list_filter = ["product"]
    ordering = ["product__name", "ingredient__name"]


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "quantity", "total_price", "currency", "account", "occurred_at"]
    list_filter = ["currency"]
    ordering = ["-occurred_at"]
    readonly_fields = ["unit_price", "created_at"]
