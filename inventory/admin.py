from django.contrib import admin
from .models import Unit, Ingredient, Purchase, Production, ProductRecipe, ProductionIngredientUsage

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'short')

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit')
    search_fields = ('name',)

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('ingredient', 'quantity', 'price', 'date')
    list_filter = ('date',)
    readonly_fields = ('date',)

class ProductRecipeInline(admin.TabularInline):
    model = ProductRecipe
    extra = 1
    fk_name = 'product'
    autocomplete_fields = ('ingredient',)
    verbose_name = "Recipe item (per meshok)"

@admin.register(ProductRecipe)
class ProductRecipeAdmin(admin.ModelAdmin):
    list_display = ('product', 'ingredient', 'amount_per_meshok')
    search_fields = ('product__name', 'ingredient__name')

@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = ('product', 'meshok', 'date')
    readonly_fields = ('date',)
    inlines = []  # don't inline usages by default

@admin.register(ProductionIngredientUsage)
class ProductionIngredientUsageAdmin(admin.ModelAdmin):
    list_display = ('production', 'ingredient', 'quantity_used')
