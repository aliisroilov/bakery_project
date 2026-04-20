from rest_framework.routers import DefaultRouter

from .views import RegionViewSet, ShopViewSet

app_name = "shops"

router = DefaultRouter()
router.register(r"regions", RegionViewSet, basename="region")
router.register(r"", ShopViewSet, basename="shop")

urlpatterns = router.urls
