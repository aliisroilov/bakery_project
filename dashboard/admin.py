from django.contrib import admin
from .models import LoanRepayment, Payment


# --- Loan Repayment Admin ---
@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ("shop", "amount", "date")
    list_filter = ("shop",)
    search_fields = ("shop__name",)
    ordering = ("-date",)
    date_hierarchy = "date"

    # ✅ Inline edit amount directly
    list_editable = ("amount",)

    readonly_fields = ("date",)


# --- Payment Admin ---
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("payment_type", "amount", "shop", "collected_by", "date", "short_notes")
    list_display_links = ("shop",)  # ✅ specify clickable field
    list_filter = ("payment_type", "shop", "collected_by", "date")
    search_fields = ("shop__name", "collected_by__username", "notes")
    ordering = ("-date",)
    date_hierarchy = "date"

    # ✅ Inline edit key fields
    list_editable = ("amount", "payment_type")

    readonly_fields = ("date",)

    def short_notes(self, obj):
        return obj.notes[:50] if obj.notes else "-"
    short_notes.short_description = "Notes"