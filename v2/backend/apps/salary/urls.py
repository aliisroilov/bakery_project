from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ProductionBreakdownView,
    SalaryEmployeeSummaryView,
    SalaryPaymentViewSet,
    SalaryRateViewSet,
)

app_name = "salary"

router = DefaultRouter()
router.register(r"rates", SalaryRateViewSet, basename="rate")
router.register(r"payments", SalaryPaymentViewSet, basename="payment")

urlpatterns = [
    path("employees/", SalaryEmployeeSummaryView.as_view(), name="employees-summary"),
    path(
        "production-breakdown/",
        ProductionBreakdownView.as_view(),
        name="production-breakdown",
    ),
    *router.urls,
]
