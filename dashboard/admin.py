from django.contrib import admin
from .models import Payment, LoanRepayment  # if LoanRepayment exists

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("date", "payment_type", "shop", "order", "amount", "collected_by")
    list_filter = ("payment_type", "date")
    search_fields = ("shop__name", "order__id", "notes")
