from rest_framework.routers import DefaultRouter

from .views import (
    IngredientViewSet,
    InventoryRevisionViewSet,
    ProductRecipeViewSet,
    PurchaseViewSet,
    UnitViewSet,
)

app_name = "inventory"

router = DefaultRouter()
router.register(r"units", UnitViewSet, basename="unit")
router.register(r"ingredients", IngredientViewSet, basename="ingredient")
router.register(r"purchases", PurchaseViewSet, basename="purchase")
router.register(r"recipes", ProductRecipeViewSet, basename="recipe")
router.register(r"revisions", InventoryRevisionViewSet, basename="revision")

urlpatterns = router.urls
