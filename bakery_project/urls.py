from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('', include('dashboard.urls')),
    path('orders/', include('orders.urls')),
    path("dashboard/", include("dashboard.urls")),
    path("reports/", include("reports.urls", namespace="reports")),  # reports app
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path("salary/", include("salary.urls", namespace="salary")),
]
