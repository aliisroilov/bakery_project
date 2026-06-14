from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmployeeGroup, NonvoyProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "full_name", "role", "phone", "is_archived", "is_active"]
    list_filter = ["role", "is_archived"]
    search_fields = ["username", "full_name", "phone"]
    fieldsets = BaseUserAdmin.fieldsets + (  # type: ignore[operator]
        ("Qo'shimcha", {"fields": ("role", "phone", "full_name", "produced_product", "is_archived")}),
    )


@admin.register(NonvoyProfile)
class NonvoyProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "hired_date"]
    ordering = ["user__username"]


@admin.register(EmployeeGroup)
class EmployeeGroupAdmin(admin.ModelAdmin):
    list_display = ["name"]
    filter_horizontal = ["members"]
