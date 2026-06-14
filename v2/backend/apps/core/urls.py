from django.urls import path

from .views import DashboardSummaryView, NetIncomeHistoryView, NotificationsView

app_name = "core"

urlpatterns = [
    path("dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/net-income-history/", NetIncomeHistoryView.as_view(), name="net-income-history"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
]
