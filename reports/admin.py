from django.contrib import admin
from .models import Category, Purchase

# --- Category Admin ---
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

# --- Purchase Admin ---
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'category', 'unit_price', 'purchase_date', 'short_notes')
    list_filter = ('category', 'purchase_date')
    search_fields = ('item_name', 'notes')
    ordering = ('-purchase_date',)
    date_hierarchy = 'purchase_date'

    # Shorten notes display in list view
    def short_notes(self, obj):
        return obj.notes[:50] if obj.notes else "-"
    short_notes.short_description = 'Notes'
