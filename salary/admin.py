from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from .models import SalaryPayment, SalaryRate


@admin.register(SalaryRate)
class SalaryRateAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "rate", "rate_type", "initial_balance_formatted", "current_balance")
    list_filter = ("rate_type", "user__role")
    search_fields = ("user__username",)
    fields = ("user", "rate", "rate_type", "initial_balance", "production_start_date", "notes", "get_balance_info")
    readonly_fields = ("get_balance_info",)

    def role(self, obj):
        """Show user role"""
        return obj.user.get_role_display()
    role.short_description = "Role"
    role.admin_order_field = "user__role"

    def initial_balance_formatted(self, obj):
        """Format initial balance with color coding"""
        balance = obj.initial_balance
        # Format the number first, then pass to format_html
        formatted_balance = f'{balance:,.0f}'
        if balance > 0:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', formatted_balance)
        elif balance < 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', formatted_balance)
        return format_html('<span style="color: gray;">0</span>')
    initial_balance_formatted.short_description = "Initial Balance"
    initial_balance_formatted.admin_order_field = "initial_balance"

    def current_balance(self, obj):
        """Show current balance due"""
        balance = SalaryPayment.get_balance_due(obj.user)
        # Format the number first, then pass to format_html
        if balance > 0:
            formatted = f'{balance:,.0f}'
            return format_html('<span style="color: green; font-weight: bold;">{} owe</span>', formatted)
        elif balance < 0:
            formatted = f'{abs(balance):,.0f}'
            return format_html('<span style="color: red; font-weight: bold;">{} overpaid</span>', formatted)
        return format_html('<span style="color: gray;">Settled</span>')
    current_balance.short_description = "Current Balance"

    def get_balance_info(self, obj):
        """Detailed balance information in the form"""
        from salary.utils import calculate_auto_salary
        from django.db.models import Sum

        total_earned = calculate_auto_salary(obj.user)
        total_paid = obj.user.salary_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        balance = total_earned - total_paid

        # Format all numbers first
        initial_balance_fmt = f'{obj.initial_balance:,.0f}'
        auto_calculated_fmt = f'{total_earned - obj.initial_balance:,.0f}'
        total_earned_fmt = f'{total_earned:,.0f}'
        total_paid_fmt = f'{total_paid:,.0f}'
        balance_fmt = f'{balance:,.0f}'
        bg_color = '#d4edda' if balance >= 0 else '#f8d7da'

        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">💰 Salary Summary</h3>'
            '<table style="width: 100%; border-collapse: collapse;">'
            '<tr><td style="padding: 5px;"><strong>Initial Balance:</strong></td><td style="padding: 5px; text-align: right;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>Auto-calculated Earnings:</strong></td><td style="padding: 5px; text-align: right;">{}</td></tr>'
            '<tr style="border-top: 2px solid #dee2e6;"><td style="padding: 5px;"><strong>Total Earned:</strong></td><td style="padding: 5px; text-align: right;">{}</td></tr>'
            '<tr><td style="padding: 5px;"><strong>Total Paid:</strong></td><td style="padding: 5px; text-align: right;">{}</td></tr>'
            '<tr style="border-top: 2px solid #dee2e6; background: {};">'
            '<td style="padding: 5px;"><strong>Balance Due:</strong></td>'
            '<td style="padding: 5px; text-align: right; font-size: 16px; font-weight: bold;">{}</td></tr>'
            '</table>'
            '</div>',
            initial_balance_fmt,
            auto_calculated_fmt,
            total_earned_fmt,
            total_paid_fmt,
            bg_color,
            balance_fmt
        )
    get_balance_info.short_description = "Balance Information"

@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "processed", "created_at")
    readonly_fields = ("processed", "processed_at", "created_at")
    # By default admin adds record without calling create_and_process, so no bakery balance change will occur.
