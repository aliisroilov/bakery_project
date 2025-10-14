from django.contrib import admin
from .models import Category, Purchase, BakeryBalance

# --- Category Admin ---
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)
    ordering = ("name",)
    list_editable = ("description",)  # ✅ Editable directly in list view


# --- Purchase Admin ---
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("item_name", "category", "unit_price", "purchase_date", "short_notes")
    list_filter = ("category", "purchase_date")
    search_fields = ("item_name", "notes")
    ordering = ("-purchase_date",)
    date_hierarchy = "purchase_date"

    # ✅ Make certain fields editable directly in list view
    list_editable = ("unit_price", "category", "purchase_date")

    # Shorten notes display in list view
    def short_notes(self, obj):
        return obj.notes[:50] if obj.notes else "-"
    short_notes.short_description = "Notes"


# --- Bakery Balance Admin ---
@admin.register(BakeryBalance)
class BakeryBalanceAdmin(admin.ModelAdmin):
    list_display = ("amount", "updated_at")
    fields = ("amount",)
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # ❌ Prevent adding multiple balances
        return not BakeryBalance.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # ❌ Prevent deleting the main balance
        return False

    # ✅ Custom admin action to reset balance to zero
    actions = ["reset_to_zero"]

    def reset_to_zero(self, request, queryset):
        BakeryBalance.reset()
        self.message_user(request, "✅ Bakery balance has been reset to zero.")
    reset_to_zero.short_description = "Reset balance to zero"
