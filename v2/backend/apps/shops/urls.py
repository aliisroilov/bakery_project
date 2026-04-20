from rest_framework.routers import DefaultRouter

from .views import RegionViewSet, ShopViewSet

app_name = "shops"

# Shops router: mounted at /api/v1/shops/
shops_router = DefaultRouter()
shops_router.register(r"", ShopViewSet, basename="shop")

# Regions router: mounted at /api/v1/regions/ (see config/urls.py).
# Kept in this app because regions live in shops/models.py.
regions_router = DefaultRouter()
regions_router.register(r"", RegionViewSet, basename="region")

urlpatterns = shops_router.urls
regions_urlpatterns = regions_router.urls
