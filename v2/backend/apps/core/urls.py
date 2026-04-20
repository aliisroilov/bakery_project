from django.urls import path

from .views import DashboardSummaryView, NotificationsView

app_name = "core"

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
]
