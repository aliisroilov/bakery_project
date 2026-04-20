from rest_framework.routers import DefaultRouter

from .views import BakeryProductStockViewSet, ProductionViewSet

app_name = "production"

router = DefaultRouter()
router.register(r"stock", BakeryProductStockViewSet, basename="stock")
router.register(r"", ProductionViewSet, basename="production")

urlpatterns = router.urls
