from django.contrib import admin

from .models import SalaryPayment, SalaryRate


@admin.register(SalaryRate)
class SalaryRateAdmin(admin.ModelAdmin):
    list_display = ["user", "rate_type", "rate", "currency", "initial_balance"]
    ordering = ["user__username"]


@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "amount", "currency", "account", "occurred_at"]
    list_filter = ["kind", "currency"]
    ordering = ["-occurred_at"]
    readonly_fields = ["created_by", "created_at"]
