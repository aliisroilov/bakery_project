from django.contrib import admin

from .models import Region, Shop, ShopProductPrice


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["name", "is_archived"]
    list_filter = ["is_archived"]
    search_fields = ["name"]


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = [
        "name", "region", "assigned_driver",
        "loan_balance_uzs", "loan_balance_usd",
        "loan_limit_uzs", "loan_limit_usd", "is_archived",
    ]
    list_filter = ["region", "is_archived"]
    search_fields = ["name", "owner_name", "phone"]
    ordering = ["name"]
    fields = [
        "name", "owner_name", "phone", "address",
        "region", "assigned_driver",
        "loan_balance_uzs", "loan_balance_usd",
        "loan_limit_uzs", "loan_limit_usd",
        "is_archived",
    ]


@admin.register(ShopProductPrice)
class ShopProductPriceAdmin(admin.ModelAdmin):
    list_display = ["shop", "product", "price", "currency"]
    list_filter = ["currency"]
    ordering = ["shop__name", "product__name"]
