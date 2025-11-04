from django.contrib import admin
from .models import Unit, Ingredient, Purchase, Production, ProductRecipe, ProductionIngredientUsage, DailyBakeryProduction, BakeryProductStock

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'short')

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit', 'low_stock_threshold', 'is_low_stock_display')
    list_filter = ('unit',)
    search_fields = ('name',)

    @admin.display(boolean=True, description="Low stock?")
    def is_low_stock_display(self, obj):
        return obj.quantity <= obj.low_stock_threshold
    
    
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


@admin.register(DailyBakeryProduction)
class DailyBakeryProductionAdmin(admin.ModelAdmin):
    list_display = ("product", "date", "quantity_produced", "confirmed")
    list_filter = ("date", "product", "confirmed")
    ordering = ("-date",)
    readonly_fields = ()
    # Because save() updates stock, admin edit will work. But prevent deletion in admin if confirmed:
    def has_delete_permission(self, request, obj=None):
        if obj and obj.confirmed:
            return False
        return super().has_delete_permission(request, obj)