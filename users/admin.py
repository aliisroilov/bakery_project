from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import User, UserActivityLog


class SalaryRateInline(admin.StackedInline):
    """Inline editor for employee salary rate and initial balance"""
    from salary.models import SalaryRate
    model = SalaryRate
    can_delete = False
    verbose_name = 'Salary Configuration'
    verbose_name_plural = 'Salary Configuration'
    fields = ('rate', 'rate_type', 'initial_balance', 'production_start_date', 'notes')
    extra = 0

    def get_formset(self, request, obj=None, **kwargs):
        """Show inline only for nonvoy and driver roles"""
        formset = super().get_formset(request, obj, **kwargs)
        # If user exists and is not employee, don't show inline
        if obj and obj.role not in ['nonvoy', 'driver']:
            formset.max_num = 0
        return formset


@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    list_display = ('username', 'role', 'is_staff', 'is_superuser', 'get_initial_balance')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username',)
    ordering = ('username',)
    inlines = [SalaryRateInline]

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )

    def get_initial_balance(self, obj):
        """Display initial balance in list view"""
        try:
            return f'{obj.salary_rate.initial_balance:,.0f}'
        except:
            return '-'
    get_initial_balance.short_description = 'Initial Balance'
    get_initial_balance.admin_order_field = 'salary_rate__initial_balance'



@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "path", "method", "timestamp", "ip")
    list_filter = ("user", "method", "timestamp")
    search_fields = ("path", "ip")
