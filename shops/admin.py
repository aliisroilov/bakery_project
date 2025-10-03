from django.contrib import admin
from .models import Shop, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("name", "owner_name", "phone", "region", "loan_balance")
    list_filter = ("region",)
    search_fields = ("name", "owner_name", "phone", "address")
    ordering = ("name",)
    list_per_page = 20
