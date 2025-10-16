from django.contrib import admin
from .models import SalaryPayment, SalaryRate

@admin.register(SalaryRate)
class SalaryRateAdmin(admin.ModelAdmin):
    list_display = ("user", "rate", "rate_type", "initial_balance")
    fields = ("user", "rate", "rate_type", "initial_balance", "notes")

@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "processed", "created_at")
    readonly_fields = ("processed", "processed_at", "created_at")
    # By default admin adds record without calling create_and_process, so no bakery balance change will occur.
