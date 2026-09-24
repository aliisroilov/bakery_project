from django import forms
from django.contrib import admin

from .models import BakeryProductStock, InventoryRevisionReport, Production, ProductionIngredientUsage


class ProductionAdminForm(forms.ModelForm):
    """Hands the picked ad-hoc crew to Production.clean() before the row exists.

    Model.clean() runs while the instance is still unsaved, when its M2M rows
    can't be queried yet — without this the "exactly one attribution" check
    wouldn't see an individuals-only run and would reject it.
    """

    class Meta:
        model = Production
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        self.instance._pending_individuals = list(cleaned.get("individuals") or [])
        return cleaned


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    form = ProductionAdminForm
    list_display = ["product", "actor_name", "meshok_count", "unit_count", "occurred_at"]
    list_filter = ["product"]
    filter_horizontal = ["individuals"]
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
