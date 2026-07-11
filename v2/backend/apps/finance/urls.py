from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CashHandoverViewSet,
    DriverHandoverReportView,
    ExpenseCategoryViewSet,
    GeneralExpenseViewSet,
    KassaAccountViewSet,
    KassaExchangeViewSet,
    KassaTransactionViewSet,
    KassaTransferViewSet,
    PaymentViewSet,
)

app_name = "finance"

router = DefaultRouter()
router.register(r"accounts", KassaAccountViewSet, basename="account")
router.register(r"transactions", KassaTransactionViewSet, basename="transaction")
router.register(r"payments", PaymentViewSet, basename="payment")
router.register(r"expense-categories", ExpenseCategoryViewSet, basename="expense-category")
router.register(r"expenses", GeneralExpenseViewSet, basename="expense")
router.register(r"handovers", CashHandoverViewSet, basename="handover")
router.register(r"transfers", KassaTransferViewSet, basename="transfer")
router.register(r"exchanges", KassaExchangeViewSet, basename="exchange")

urlpatterns = [
    path(
        "driver-handover-report/",
        DriverHandoverReportView.as_view(),
        name="driver-handover-report",
    ),
    *router.urls,
]
