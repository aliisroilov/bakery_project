"""Root URL config for bakery v2."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.shops.urls import regions_urlpatterns

api_v1 = [
    # Auth
    path("auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Apps
    path("", include("apps.core.urls")),
    path("users/", include("apps.users.urls")),
    path("shops/", include("apps.shops.urls")),
    # Regions live in the shops app but are exposed at the root level.
    path("regions/", include(regions_urlpatterns)),
    path("products/", include("apps.products.urls")),
    path("orders/", include("apps.orders.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("production/", include("apps.production.urls")),
    path("salary/", include("apps.salary.urls")),
    path("finance/", include("apps.finance.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("reports/", include("apps.reports.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),  # superuser bootstrap only
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
