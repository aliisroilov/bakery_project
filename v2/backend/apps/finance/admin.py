from django.contrib import admin

from .models import (
    CashHandover,
    ExpenseCategory,
    GeneralExpense,
    KassaAccount,
    KassaTransaction,
    Payment,
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "include_in_pnl", "note", "created_at"]
    list_editable = ["include_in_pnl"]
    list_filter = ["include_in_pnl"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(KassaAccount)
class KassaAccountAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "balance_uzs", "balance_usd"]
    fields = ["name", "slug", "description", "balance_uzs", "balance_usd"]
    search_fields = ["name", "slug"]


@admin.register(KassaTransaction)
class KassaTransactionAdmin(admin.ModelAdmin):
    list_display = ["account", "kind", "currency", "amount", "occurred_at", "created_by"]
    list_filter = ["account", "kind", "currency"]
    search_fields = ["note"]
    ordering = ["-occurred_at"]
    readonly_fields = ["occurred_at", "created_by", "reference_model", "reference_id"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["shop", "amount", "currency", "payment_type", "collected_by", "received_at"]
    list_filter = ["currency", "payment_type"]
    search_fields = ["shop__name"]
    ordering = ["-received_at"]
    readonly_fields = ["collected_by", "created_at"]


@admin.register(GeneralExpense)
class GeneralExpenseAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "amount", "currency", "occurred_at"]
    list_filter = ["currency", "category"]
    search_fields = ["title"]
    ordering = ["-occurred_at"]


@admin.register(CashHandover)
class CashHandoverAdmin(admin.ModelAdmin):
    list_display = ["driver", "amount", "currency", "to_account", "occurred_at"]
    list_filter = ["currency"]
    ordering = ["-occurred_at"]
